"""
download_history.py — Télécharge des données historiques OHLCV via TwelveData.

Stocke les résultats en Parquet dans backtest/data/.
Utilise le TwelveDataProvider existant avec rate limiting et key rotation.

Usage :
    python -m backtest.download_history --pairs EURUSD GBPUSD --months 6
    python -m backtest.download_history --all --months 6
"""

import os
import sys
import time
import argparse
import pandas as pd
from datetime import datetime, timedelta

# Assurer que le projet root est dans sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from data.twelve_data_provider import TwelveDataProvider, SYMBOL_MAP, TF_MAP
import config

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# TwelveData free plan : max 5000 bars par requête
MAX_BARS_PER_REQUEST = 5000

# Nombre de bars M5 par mois (~8640 = 30 jours × 24h × 12 bars/h)
# Forex réel: ~8640 bars/mois (5 jours/semaine × 4.3 semaines × 24h × 12)
BARS_PER_MONTH = {
    "M5":  8640,
    "H1":  720,
    "H4":  180,
    "D1":  22,
    "W1":  4,
}

TIMEFRAMES = ["M5", "H1", "H4", "D1"]


def _candles_to_dataframe(candles: list) -> pd.DataFrame:
    """Convertit une liste de dicts OHLCV en DataFrame avec colonnes dérivées."""
    if not candles:
        return pd.DataFrame()

    df = pd.DataFrame(candles)
    df["time"] = pd.to_datetime(df["time"])
    df = df.sort_values("time").reset_index(drop=True)

    # Colonnes dérivées (identiques au pipeline live)
    df["body"] = (df["close"] - df["open"]).abs()
    rng = df["high"] - df["low"]
    df["range"] = rng
    df["body_ratio"] = df["body"] / rng.replace(0, float("nan"))
    df["body_ratio"] = df["body_ratio"].fillna(0.0)
    df["upper_wick"] = df["high"] - df[["open", "close"]].max(axis=1)
    df["lower_wick"] = df[["open", "close"]].min(axis=1) - df["low"]

    return df


def _detect_gaps(df: pd.DataFrame, tf: str) -> list:
    """Détecte les gaps temporels anormaux dans les données."""
    if len(df) < 2:
        return []

    expected_minutes = {"M5": 5, "H1": 60, "H4": 240, "D1": 1440}
    expected = timedelta(minutes=expected_minutes.get(tf, 5))
    threshold = expected * 3  # 3× l'intervalle attendu = gap

    gaps = []
    times = df["time"].values
    for i in range(1, len(times)):
        delta = pd.Timestamp(times[i]) - pd.Timestamp(times[i - 1])
        if delta > threshold:
            # Exclure les weekends (vendredi → lundi) pour D1
            t_prev = pd.Timestamp(times[i - 1])
            t_curr = pd.Timestamp(times[i])
            if t_prev.weekday() == 4 and t_curr.weekday() == 0:
                continue  # Gap weekend normal
            gaps.append({
                "index": i,
                "from": str(t_prev),
                "to": str(t_curr),
                "delta_hours": delta.total_seconds() / 3600,
            })
    return gaps


def download_pair(provider: TwelveDataProvider, symbol: str, months: int = 6,
                  verbose: bool = True) -> dict:
    """
    Télécharge toutes les timeframes pour une paire et sauvegarde en Parquet.

    Returns:
        dict avec les stats de download par TF
    """
    td_symbol = SYMBOL_MAP.get(symbol)
    if not td_symbol:
        print(f"[Download] ❌ Symbole inconnu : {symbol}")
        return {}

    os.makedirs(DATA_DIR, exist_ok=True)
    stats = {}

    for tf in TIMEFRAMES:
        total_bars_needed = BARS_PER_MONTH.get(tf, 5000) * months
        output_path = os.path.join(DATA_DIR, f"{symbol}_{tf}.parquet")

        if verbose:
            print(f"[Download] {symbol} {tf} — {total_bars_needed} bars demandées...", end=" ")

        all_candles = []

        if total_bars_needed <= MAX_BARS_PER_REQUEST:
            # Une seule requête suffit
            candles = provider._fetch_candles(td_symbol, tf, total_bars_needed)
            all_candles.extend(candles)
        else:
            # Pagination : plusieurs requêtes de 5000 bars
            # TwelveData ne supporte pas la pagination native en mode gratuit,
            # donc on télécharge le max (5000) et on prend ce qu'on peut.
            candles = provider._fetch_candles(td_symbol, tf, MAX_BARS_PER_REQUEST)
            all_candles.extend(candles)

            if verbose and len(candles) < total_bars_needed:
                print(f"({len(candles)}/{total_bars_needed} récupérées — limite API)", end=" ")

        if not all_candles:
            if verbose:
                print("❌ Aucune donnée")
            stats[tf] = {"bars": 0, "gaps": 0, "status": "empty"}
            continue

        df = _candles_to_dataframe(all_candles)

        # Dédupliquer sur le timestamp
        df = df.drop_duplicates(subset=["time"]).sort_values("time").reset_index(drop=True)

        # Détecter les gaps
        gaps = _detect_gaps(df, tf)

        # Sauvegarder en Parquet
        df.to_parquet(output_path, index=False)

        date_range = f"{df['time'].iloc[0].strftime('%Y-%m-%d')} → {df['time'].iloc[-1].strftime('%Y-%m-%d')}"

        if verbose:
            gap_msg = f" ({len(gaps)} gaps détectés)" if gaps else ""
            print(f"✅ {len(df)} bars [{date_range}]{gap_msg}")

        stats[tf] = {
            "bars": len(df),
            "gaps": len(gaps),
            "gap_details": gaps[:5],  # Max 5 premiers gaps pour le log
            "date_range": date_range,
            "file": output_path,
            "status": "ok",
        }

    return stats


def download_all(pairs: list = None, months: int = 6, verbose: bool = True) -> dict:
    """Télécharge les données pour toutes les paires spécifiées."""
    if pairs is None:
        pairs = config.TRADING_PAIRS

    provider = TwelveDataProvider()
    if not provider.connected:
        print("[Download] ❌ TwelveData non connecté — vérifiez les clés API dans config.py")
        return {}

    all_stats = {}
    total_pairs = len(pairs)

    for i, symbol in enumerate(pairs, 1):
        print(f"\n{'='*60}")
        print(f"[{i}/{total_pairs}] {symbol}")
        print(f"{'='*60}")

        stats = download_pair(provider, symbol, months, verbose)
        all_stats[symbol] = stats

        # Pause entre les paires pour ménager le rate limiter
        if i < total_pairs:
            time.sleep(2)

    # Résumé
    print(f"\n{'='*60}")
    print(f"RÉSUMÉ — {total_pairs} paires × {len(TIMEFRAMES)} TF = {total_pairs * len(TIMEFRAMES)} fichiers")
    print(f"{'='*60}")
    for symbol, stats in all_stats.items():
        m5_bars = stats.get("M5", {}).get("bars", 0)
        m5_gaps = stats.get("M5", {}).get("gaps", 0)
        status = "✅" if m5_bars > 0 else "❌"
        print(f"  {status} {symbol:8s} — M5: {m5_bars:>5} bars, {m5_gaps} gaps")

    return all_stats


def load_pair_data(symbol: str) -> dict:
    """
    Charge les données Parquet d'une paire en mémoire.

    Returns:
        dict {"M5": DataFrame, "H1": DataFrame, "H4": DataFrame, "D1": DataFrame}
    """
    dfs = {}
    for tf in TIMEFRAMES:
        path = os.path.join(DATA_DIR, f"{symbol}_{tf}.parquet")
        if os.path.exists(path):
            dfs[tf] = pd.read_parquet(path)
        else:
            dfs[tf] = pd.DataFrame()
    return dfs


def list_available_data() -> dict:
    """Liste les données disponibles dans backtest/data/."""
    available = {}
    if not os.path.exists(DATA_DIR):
        return available

    for f in sorted(os.listdir(DATA_DIR)):
        if f.endswith(".parquet"):
            parts = f.replace(".parquet", "").split("_")
            if len(parts) >= 2:
                symbol = parts[0]
                tf = parts[1]
                path = os.path.join(DATA_DIR, f)
                size_mb = os.path.getsize(path) / (1024 * 1024)
                df = pd.read_parquet(path)
                if symbol not in available:
                    available[symbol] = {}
                available[symbol][tf] = {
                    "bars": len(df),
                    "size_mb": round(size_mb, 2),
                    "from": str(df["time"].iloc[0]) if len(df) > 0 else "N/A",
                    "to": str(df["time"].iloc[-1]) if len(df) > 0 else "N/A",
                }
    return available


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(
        description="Télécharge des données historiques OHLCV via TwelveData"
    )
    parser.add_argument("--pairs", nargs="+", help="Paires à télécharger (ex: EURUSD GBPUSD)")
    parser.add_argument("--all", action="store_true", help="Toutes les 14 paires de config.py")
    parser.add_argument("--months", type=int, default=6, help="Nombre de mois (défaut: 6)")
    parser.add_argument("--list", action="store_true", help="Lister les données disponibles")

    args = parser.parse_args()

    if args.list:
        available = list_available_data()
        if not available:
            print("Aucune donnée disponible dans backtest/data/")
            return
        for symbol, tfs in available.items():
            print(f"\n{symbol}:")
            for tf, info in tfs.items():
                print(f"  {tf}: {info['bars']:>5} bars ({info['size_mb']:.1f} MB) "
                      f"[{info['from'][:10]} → {info['to'][:10]}]")
        return

    if args.all:
        pairs = config.TRADING_PAIRS
    elif args.pairs:
        pairs = [p.upper() for p in args.pairs]
    else:
        parser.print_help()
        return

    download_all(pairs, args.months)


if __name__ == "__main__":
    main()
