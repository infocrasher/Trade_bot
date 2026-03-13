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


def _evaluate(record: dict, current_price: float) -> dict:
    """
    Remplit would_have_won et pnl_pips pour un record donné.
    Logique : si le prix a atteint TP1 avant SL → gagné.
    On compare juste le prix actuel vs entry/sl/tp1.
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

    # Déterminer la direction
    is_long = "BUY" in signal.upper() or "bullish" in bias.lower()
    is_short = "SELL" in signal.upper() or "bearish" in bias.lower()

    if not is_long and not is_short:
        return record

    if is_long:
        # Prix actuel >= TP1 → aurait gagné
        if current_price >= tp1:
            record["would_have_won"] = True
            record["pnl_pips"] = round((tp1 - entry) / pip, 1)
        # Prix actuel <= SL → aurait perdu
        elif current_price <= sl:
            record["would_have_won"] = False
            record["pnl_pips"] = round((sl - entry) / pip, 1)
        else:
            record["would_have_won"] = None  # encore en cours
            record["pnl_pips"] = round((current_price - entry) / pip, 1)
    else:  # short
        if current_price <= tp1:
            record["would_have_won"] = True
            record["pnl_pips"] = round((entry - tp1) / pip, 1)
        elif current_price >= sl:
            record["would_have_won"] = False
            record["pnl_pips"] = round((entry - sl) / pip, 1)
        else:
            record["would_have_won"] = None
            record["pnl_pips"] = round((entry - current_price) / pip, 1)

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
