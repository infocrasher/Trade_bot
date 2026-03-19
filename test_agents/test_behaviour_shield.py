"""
Tests unitaires — BehaviourShield (P-F1)
=========================================
BS1 : Mèche > 3× corps → Stop Hunt
BS6 : 3 SL consécutifs même direction → Revenge Trade bloqué
BS7 : Signal dupliqué < 10min → bloqué
BS8 : Setup > 5min → périmé bloqué
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from datetime import datetime, timezone, timedelta
import pandas as pd
from agents.behaviour_shield import BehaviourShield


class TestResults:
    def __init__(self):
        self.passed   = 0
        self.failed   = 0
        self.failures = []

    def check(self, name: str, condition: bool, detail: str = ""):
        if condition:
            self.passed += 1
            print(f"  ✅ PASS : {name}")
        else:
            self.failed += 1
            self.failures.append(name)
            print(f"  ❌ FAIL : {name} — {detail}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*52}")
        print(f"RÉSULTATS : {self.passed}/{total} tests passés")
        if self.failures:
            print("Tests échoués :")
            for f in self.failures:
                print(f"  - {f}")
        print(f"{'='*52}")
        return self.failed == 0


def make_df_m5(n: int = 30, close: float = 1.1000) -> pd.DataFrame:
    """DataFrame M5 générique stable (pas de spike)."""
    rows = []
    for i in range(n):
        rows.append({
            "time":  pd.Timestamp(f"2026-03-19 {8 + i // 12:02d}:{(i % 12) * 5:02d}:00"),
            "open":  close,
            "high":  close + 0.0010,
            "low":   close - 0.0010,
            "close": close,
        })
    return pd.DataFrame(rows)


def make_df_m5_stop_hunt(wick_ratio: float = 4.0, close: float = 1.1000) -> pd.DataFrame:
    """DataFrame M5 avec avant-dernière bougie ayant une mèche dominante = wick_ratio × corps."""
    rows = []
    body = 0.0010
    upper_wick = body * wick_ratio
    rows = [
        # Bougies normales (28)
        {"time": pd.Timestamp(f"2026-03-19 08:{i:02d}:00"), "open": close, "high": close + 0.0010,
         "low": close - 0.0010, "close": close}
        for i in range(28)
    ]
    # Avant-dernière : grosse mèche haute (4× corps)
    rows.append({
        "time":  pd.Timestamp("2026-03-19 08:28:00"),
        "open":  close,
        "high":  close + upper_wick + body,  # mèche = 4× corps
        "low":   close - 0.0002,
        "close": close + body,               # corps = body
    })
    # Dernière bougie : retour vers le level (PDH)
    rows.append({
        "time":  pd.Timestamp("2026-03-19 08:29:00"),
        "open":  close + body,
        "high":  close + body + 0.0005,
        "low":   close + body - 0.0003,
        "close": close + body + 0.0001,
    })
    return pd.DataFrame(rows)


def run_behaviour_shield_tests() -> bool:
    tr = TestResults()
    print("\n" + "="*52)
    print("TESTS UNITAIRES — BehaviourShield (P-F1)")
    print("="*52)

    bs = BehaviourShield()

    # ── BS1 : Stop Hunt (mèche > 3× corps) ─────────────────────────────────
    print("\n--- BS1 : Stop Hunt ---\n")
    try:
        CLOSE = 1.1000
        df = make_df_m5_stop_hunt(wick_ratio=4.0, close=CLOSE)

        # Tester directement _bs1_stop_hunt pour isoler du reste des filtres
        ctx = {
            "key_levels": {
                # Level juste sous le high de la bougie spike
                "pdh": float(df.iloc[-2]["high"]) - 0.0002,
            }
        }
        res = bs._bs1_stop_hunt(df, ctx)

        tr.check("BS1a : Stop Hunt détecté (blocked=True)",
                 res["blocked"] == True,
                 f"Résultat: {res}")
        tr.check("BS1b : Filtre identifié BS1",
                 res.get("filter", "").startswith("BS1"),
                 f"Filter: {res.get('filter')}")
        tr.check("BS1c : Raison contient 'Stop Hunt'",
                 "Stop Hunt" in res.get("reason", ""),
                 f"Reason: {res.get('reason')}")
    except Exception as e:
        tr.check("BS1 : Stop Hunt", False, f"Exception: {e}")

    # ── BS6 : Revenge Trade (3 SL consécutifs) ──────────────────────────────
    print("\n--- BS6 : Revenge Trade ---\n")
    try:
        bs6 = BehaviourShield()
        df = make_df_m5()

        # 3 trades SL consécutifs même paire même direction
        ctx = {
            "recent_trades": [
                {"pair": "EURUSD", "direction": "BUY", "status": "sl_hit"},
                {"pair": "EURUSD", "direction": "BUY", "status": "sl_hit"},
                {"pair": "EURUSD", "direction": "BUY", "status": "sl_hit"},
            ]
        }
        res = bs6.check("EURUSD", "BUY", 1.1000, 1.0980, df_m5=df, context=ctx)

        tr.check("BS6a : Revenge Trade bloqué",
                 res["blocked"] == True,
                 f"Résultat: {res}")
        tr.check("BS6b : Filtre BS6",
                 res.get("filter", "").startswith("BS6"),
                 f"Filter: {res.get('filter')}")

        # Vérifier que 2 SL ne bloque pas
        ctx2 = {
            "recent_trades": [
                {"pair": "EURUSD", "direction": "BUY", "status": "sl_hit"},
                {"pair": "EURUSD", "direction": "BUY", "status": "sl_hit"},
            ]
        }
        res2 = bs6.check("EURUSD", "SELL", 1.1000, 1.1020, df_m5=df, context=ctx2)
        tr.check("BS6c : 2 SL ne bloque pas",
                 res2["blocked"] == False,
                 f"Résultat: {res2}")
    except Exception as e:
        tr.check("BS6 : Revenge Trade", False, f"Exception: {e}")

    # ── BS7 : Duplicate Signal (< 10 min) ───────────────────────────────────
    print("\n--- BS7 : Duplicate Signal ---\n")
    try:
        bs7 = BehaviourShield()
        df = make_df_m5()

        # Enregistrer un premier signal (sans bloquer)
        ctx_noblock = {"entry_time": datetime.now(timezone.utc) - timedelta(seconds=600)}
        res_first = bs7.check("GBPUSD", "SELL", 1.2700, 1.2720, df_m5=df, context=ctx_noblock)
        # Le premier passe (registry vide ou > 10min)
        # → on force l'enregistrement
        bs7._signal_registry["GBPUSD_SELL"] = time.time()

        # Deuxième signal identique < 10 min → bloqué
        res_dup = bs7._bs7_duplicate("GBPUSD", "SELL")
        tr.check("BS7a : Duplicate bloqué",
                 res_dup["blocked"] == True,
                 f"Résultat: {res_dup}")
        tr.check("BS7b : Filtre BS7",
                 res_dup.get("filter", "").startswith("BS7"),
                 f"Filter: {res_dup.get('filter')}")

        # Signal différent (autre direction) → doit passer
        res_diff = bs7._bs7_duplicate("GBPUSD", "BUY")
        tr.check("BS7c : Direction différente passe",
                 res_diff["blocked"] == False,
                 f"Résultat: {res_diff}")
    except Exception as e:
        tr.check("BS7 : Duplicate Signal", False, f"Exception: {e}")

    # ── BS8 : Staleness (> 5 min) ───────────────────────────────────────────
    print("\n--- BS8 : Staleness ---\n")
    try:
        bs8 = BehaviourShield()

        # Signal périmé : entry_time = il y a 7 minutes — tester directement
        ctx_stale = {
            "entry_time": datetime.now(timezone.utc) - timedelta(minutes=7)
        }
        res_stale = bs8._bs8_staleness(ctx_stale)

        tr.check("BS8a : Setup périmé bloqué",
                 res_stale["blocked"] == True,
                 f"Résultat: {res_stale}")
        tr.check("BS8b : Filtre BS8",
                 res_stale.get("filter", "").startswith("BS8"),
                 f"Filter: {res_stale.get('filter')}")

        # Signal récent (il y a 2 minutes) → doit passer
        ctx_fresh = {
            "entry_time": datetime.now(timezone.utc) - timedelta(minutes=2),
        }
        res_fresh = bs8._bs8_staleness(ctx_fresh)
        tr.check("BS8c : Signal récent (2min) passe",
                 res_fresh["blocked"] == False,
                 f"Résultat: {res_fresh}")
    except Exception as e:
        tr.check("BS8 : Staleness", False, f"Exception: {e}")

    tr.summary()
    return tr.failed == 0


def test_behaviour_shield():
    """Wrapper pour pytest."""
    success = run_behaviour_shield_tests()
    assert success, "BehaviourShield tests failed"


if __name__ == "__main__":
    run_behaviour_shield_tests()
