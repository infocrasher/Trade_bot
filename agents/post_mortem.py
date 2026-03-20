"""
Post-Mortem Agent — Analyse les setups bloqués a posteriori.
Tourne une fois par jour, remplit would_have_won et pnl_pips
dans les fichiers gate_logs de la journée.
"""

import json
import os
from datetime import datetime, timezone

GATE_LOG_DIR = "data/gate_logs"


def _pip_size(pair: str) -> float:
    if any(x in pair.upper() for x in ["JPY", "XAU", "GOLD"]):
        return 0.01
    if any(x in pair.upper() for x in ["BTC", "ETH"]):
        return 1.0
    return 0.0001


def _get_spread_cost(pair: str) -> float:
    """Retourne le coût du spread aller-retour en pips pour le PnL réaliste."""
    try:
        from config import get_realistic_spread_pips
        return get_realistic_spread_pips(pair, None)  # spread 'default'
    except ImportError:
        return 1.5  # fallback conservateur


def _evaluate(record: dict, current_price: float) -> dict:
    """
    Remplit would_have_won et pnl_pips pour un record donné.
    Logique : si le prix a atteint TP1 avant SL → gagné.
    On compare juste le prix actuel vs entry/sl/tp1.
    Le spread est déduit du PnL pour refléter le coût réel.
    """
    entry = record.get("entry") or record.get("entry_price")
    sl    = record.get("sl") or record.get("stop_loss")
    tp1   = record.get("tp1")

    if not entry or not sl or not tp1:
        return record

    pair     = record.get("pair", "")
    pip      = _pip_size(pair)
    signal   = record.get("ict_signal") or record.get("signal") or ""
    bias     = record.get("bias") or record.get("a1_bias") or ""
    spread   = _get_spread_cost(pair)

    # Déterminer la direction
    is_long = "BUY" in signal.upper() or "bullish" in bias.lower()
    is_short = "SELL" in signal.upper() or "bearish" in bias.lower()

    if not is_long and not is_short:
        return record

    if is_long:
        # Prix actuel >= TP1 → aurait gagné
        if current_price >= tp1:
            record["would_have_won"] = True
            record["pnl_pips"] = round((tp1 - entry) / pip - spread, 1)
        # Prix actuel <= SL → aurait perdu
        elif current_price <= sl:
            record["would_have_won"] = False
            record["pnl_pips"] = round((sl - entry) / pip - spread, 1)
        else:
            record["would_have_won"] = None  # encore en cours
            record["pnl_pips"] = round((current_price - entry) / pip - spread, 1)
    else:  # short
        if current_price <= tp1:
            record["would_have_won"] = True
            record["pnl_pips"] = round((entry - tp1) / pip - spread, 1)
        elif current_price >= sl:
            record["would_have_won"] = False
            record["pnl_pips"] = round((entry - sl) / pip - spread, 1)
        else:
            record["would_have_won"] = None
            record["pnl_pips"] = round((entry - current_price) / pip - spread, 1)

    record["spread_cost_pips"] = spread
    return record


def run_post_mortem(price_fetcher=None) -> dict:
    """
    Analyse tous les gate logs du jour.
    price_fetcher : callable(pair) -> float (prix actuel)
    Si None, utilise yfinance comme fallback.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    report = {
        "date": today,
        "ict":     {"total": 0, "won": 0, "lost": 0, "pending": 0, "gate_regret_rate": 0},
        "elliott": {"total": 0, "won": 0, "lost": 0, "pending": 0, "gate_regret_rate": 0},
        "meta":    {"total": 0, "won": 0, "lost": 0, "pending": 0, "gate_regret_rate": 0},
    }

    schools = {
        "ict":     f"ict_blocked_{today}.json",
        "elliott": f"elliott_blocked_{today}.json",
        "meta":    f"meta_blocked_{today}.json",
    }

    for school, filename in schools.items():
        filepath = os.path.join(GATE_LOG_DIR, filename)
        if not os.path.exists(filepath):
            continue

        with open(filepath, "r") as f:
            records = json.load(f)

        updated = []
        for rec in records:
            pair = rec.get("pair", "")
            if not pair:
                updated.append(rec)
                continue

            # Récupérer le prix actuel
            current_price = None
            if price_fetcher:
                try:
                    current_price = price_fetcher(pair)
                except Exception:
                    pass

            if current_price is None:
                try:
                    import yfinance as yf
                    sym = pair.replace("USDT", "-USD").replace("USD", "=X")
                    if "BTC" in pair:
                        sym = "BTC-USD"
                    elif "ETH" in pair:
                        sym = "ETH-USD"
                    ticker = yf.Ticker(sym)
                    hist = ticker.history(period="1d", interval="1m")
                    if not hist.empty:
                        current_price = float(hist["Close"].iloc[-1])
                except Exception:
                    pass

            if current_price:
                rec = _evaluate(rec, current_price)

            updated.append(rec)

        # Stats
        total   = len(updated)
        won     = sum(1 for r in updated if r.get("would_have_won") is True)
        lost    = sum(1 for r in updated if r.get("would_have_won") is False)
        pending = sum(1 for r in updated if r.get("would_have_won") is None)
        regret  = round(won / total * 100, 1) if total > 0 else 0

        report[school] = {
            "total":             total,
            "won":               won,
            "lost":              lost,
            "pending":           pending,
            "gate_regret_rate":  regret,
        }

        # Sauvegarder les records mis à jour
        with open(filepath, "w") as f:
            json.dump(updated, f, indent=2)

    # Sauvegarder le rapport
    report_path = os.path.join(GATE_LOG_DIR, f"post_mortem_{today}.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    return report


# ─────────────────────────────────────────────────────────────────
# ENRICHISSEMENT RÉTROACTIF — Option B simplifiée
# ─────────────────────────────────────────────────────────────────
def _fetch_m5_range(pair: str, start_iso: str, n_bars: int = 48) -> list:
    """
    Appelle TwelveData /time_series en M5 depuis start_iso (ISO 8601 UTC).
    Retourne une liste de bougies [{time, high, low}, ...] triees ASC.
    Limite aux n_bars bougies (48 bougies M5 ≈ 4 heures).
    Délai intégré pour respecter le rate-limiter TwelveData (8 req/min).
    """
    import time
    import requests

    try:
        import config
        api_keys = getattr(config, "TWELVE_DATA_API_KEYS", [])
    except ImportError:
        api_keys = []

    api_key = next((k for k in api_keys if k), None) if api_keys else None
    if not api_key:
        import os
        api_key = os.environ.get("TWELVE_DATA_API_KEY", "")

    if not api_key:
        return []

    # Mapping paire → symbole TwelveData
    SYM_MAP = {
        "EURUSD": "EUR/USD", "GBPUSD": "GBP/USD", "AUDUSD": "AUD/USD",
        "NZDUSD": "NZD/USD", "USDJPY": "USD/JPY", "USDCAD": "USD/CAD",
        "USDCHF": "USD/CHF", "EURGBP": "EUR/GBP", "EURJPY": "EUR/JPY",
        "GBPJPY": "GBP/JPY", "AUDJPY": "AUD/JPY", "XAUUSD": "XAU/USD",
        "BTCUSD": "BTC/USD", "ETHUSD": "ETH/USD",
    }
    td_symbol = SYM_MAP.get(pair.upper())
    if not td_symbol:
        return []

    # Respect du rate-limiter (8 req/min)
    time.sleep(8)

    try:
        r = requests.get(
            "https://api.twelvedata.com/time_series",
            params={
                "symbol":     td_symbol,
                "interval":   "5min",
                "start_date": start_iso[:16].replace("T", " "),  # "YYYY-MM-DD HH:MM"
                "outputsize": n_bars,
                "order":      "ASC",
                "apikey":     api_key,
            },
            timeout=15,
        )
        j = r.json()
        if j.get("status") == "error":
            print(f"[PostMortem] TwelveData error {pair}: {j.get('message','')}")
            return []
        candles = []
        for v in j.get("values", []):
            candles.append({
                "time":  v.get("datetime", ""),
                "high":  float(v.get("high", 0)),
                "low":   float(v.get("low", 0)),
            })
        return candles
    except Exception as e:
        print(f"[PostMortem] _fetch_m5_range exception {pair}: {e}")
        return []


def _simulate_outcome(record: dict, candles: list) -> dict:
    """
    Parcourt les bougies M5 de façon chronologique.
    Direction déduite à partir du champ 'signal' ou 'bias'.
    - BUY  : TP atteint si high >= tp1 | SL atteint si low <= sl
    - SELL : TP atteint si low  <= tp1 | SL atteint si high >= sl
    """
    entry = float(record.get("entry") or record.get("entry_price") or 0)
    sl    = float(record.get("sl")    or record.get("stop_loss")   or 0)
    tp1   = float(record.get("tp1",   0))

    if not entry or not sl or not tp1:
        return record

    pair = record.get("pair", "")
    pip  = _pip_size(pair)

    sig  = (record.get("signal") or record.get("ict_signal") or "").upper()
    bias = (record.get("bias")   or record.get("a1_bias")    or "").lower()
    is_long = "BUY" in sig or "bullish" in bias
    is_short = "SELL" in sig or "bearish" in bias

    if not is_long and not is_short:
        # Fallback : deviner d'après tp1 vs entry
        is_long = tp1 > entry

    for c in candles:
        h = c["high"]
        l = c["low"]
        if is_long:
            if h >= tp1:
                record["would_have_won"] = True
                record["pnl_pips"]       = round((tp1 - entry) / pip, 1)
                return record
            if l <= sl:
                record["would_have_won"] = False
                record["pnl_pips"]       = round((sl - entry) / pip, 1)
                return record
        else:  # short
            if l <= tp1:
                record["would_have_won"] = True
                record["pnl_pips"]       = round((entry - tp1) / pip, 1)
                return record
            if h >= sl:
                record["would_have_won"] = False
                record["pnl_pips"]       = round((entry - sl) / pip, 1)
                return record

    # Ni TP ni SL atteints dans la fenêtre de 4h
    record["would_have_won"] = None
    record["pnl_pips"]       = 0
    return record


def enrich_gate_logs_retroactive(target_date: str = None, gate_log_dir: str = None) -> dict:
    """
    Enrichit les gate_logs d'une journée dont pnl_pips est null.
    Pour chaque entrée dont tp1 et sl sont présents, récupère 4h de bougies
    M5 TwelveData depuis l'heure du blocage et simule TP vs SL.

    Paramètres :
      target_date  : str "YYYY-MM-DD" (défaut = aujourd'hui UTC)
      gate_log_dir : chemin du dossier gate_logs (défaut = data/gate_logs)

    Retourne un dictionnaire de bilan par profil.
    """
    import time as _time

    if not target_date:
        target_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if not gate_log_dir:
        gate_log_dir = GATE_LOG_DIR

    profiles = ["ict", "elliott", "vsa", "meta", "pure_pa"]
    bilan = {}

    for profile in profiles:
        filepath = os.path.join(gate_log_dir, f"{profile}_blocked_{target_date}.json")
        if not os.path.exists(filepath):
            continue

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                records = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        enriched  = 0
        skipped   = 0
        updated   = []

        for rec in records:
            # Sauter si déjà enrichi (pnl_pips rempli)
            if rec.get("pnl_pips") is not None:
                updated.append(rec)
                skipped += 1
                continue

            # Vérifier que les données nécessaires sont présentes
            if not rec.get("tp1") or not rec.get("sl"):
                updated.append(rec)
                skipped += 1
                continue

            pair      = rec.get("pair", "")
            timestamp = rec.get("timestamp", "")  # ISO 8601

            if not pair or not timestamp:
                updated.append(rec)
                skipped += 1
                continue

            # Récupérer les bougies M5 (48 bougies ≈ 4 heures)
            candles = _fetch_m5_range(pair, timestamp, n_bars=48)
            if candles:
                rec = _simulate_outcome(rec, candles)
                enriched += 1
            else:
                skipped += 1

            updated.append(rec)

        # Sauvegarder les résultats enrichis
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(updated, f, indent=2, ensure_ascii=False)
        except OSError as e:
            print(f"[PostMortem] Erreur sauvegarde {filepath}: {e}")

        total = len(updated)
        won   = sum(1 for r in updated if r.get("would_have_won") is True)
        bilan[profile] = {
            "total":    total,
            "enriched": enriched,
            "skipped":  skipped,
            "won":      won,
            "regret":   round(won / total * 100, 1) if total else 0,
        }
        print(f"[PostMortem] {profile} — {enriched} enrichis, {skipped} skippés, regret={bilan[profile]['regret']}%")

    return bilan


if __name__ == "__main__":

    result = run_post_mortem()
    print("\n═══ POST-MORTEM REPORT ═══")
    for school, stats in result.items():
        if school == "date":
            continue
        print(f"\n{school.upper()}")
        print(f"  Total bloqués  : {stats['total']}")
        print(f"  Auraient gagné : {stats['won']}")
        print(f"  Auraient perdu : {stats['lost']}")
        print(f"  En cours       : {stats['pending']}")
        print(f"  Gate Regret    : {stats['gate_regret_rate']}%")
    print("\n══════════════════════════")
