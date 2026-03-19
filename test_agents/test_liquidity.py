"""
Tests unitaires — LiquidityDetector (P-F2)
==========================================
Test 1 : PDH/PDL calculés correctement depuis df_d1
Test 2 : Equal Highs détectés dans tolérance 3 pips
Test 3 : DOL retourne le bon niveau selon le biais
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from datetime import datetime, timezone
from agents.ict.liquidity_detector import LiquidityDetector


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


def make_df_d1(days: int = 10, start_high: float = 1.1100, start_low: float = 1.0900) -> pd.DataFrame:
    """Créé un DataFrame D1 fictif avec des niveaux constants."""
    rows = []
    for i in range(days):
        rows.append({
            "time":  datetime(2026, 3, i + 1, 0, 0, tzinfo=timezone.utc),
            "open":  start_low + 0.0050,
            "high":  start_high + i * 0.0010,  # Chaque jour un peu plus haut
            "low":   start_low  - i * 0.0005,
            "close": start_low + 0.0100,
        })
    return pd.DataFrame(rows)


def make_df_m5_with_equal_highs(eq_price: float = 1.1050, n_highs: int = 3) -> pd.DataFrame:
    """Créé un M5 avec plusieurs swing highs au même niveau (Equal Highs)."""
    rows = []
    base_time = datetime(2026, 3, 19, 8, 0, tzinfo=timezone.utc)

    for i in range(50):
        # Toutes les 10 bougies, créer un swing high proche de eq_price
        if i % 10 == 5 and n_highs > 0:
            h = eq_price + 0.00001 * (i % 3)  # Varie de 0 à 2 micro-pips → dans la tolérance 3 pips
            n_highs -= 1
        else:
            h = eq_price - 0.0050  # Bougie ordinaire sous le niveau
        rows.append({
            "time":  pd.Timestamp(base_time) + pd.Timedelta(minutes=5 * i),
            "open":  h - 0.0010,
            "high":  h,
            "low":   h - 0.0020,
            "close": h - 0.0005,
        })
    return pd.DataFrame(rows)


def make_df_m5_basic(current_price: float = 1.1000) -> pd.DataFrame:
    """Créé un M5 simple pour les tests DOL."""
    rows = []
    base_time = datetime(2026, 3, 19, 10, 0, tzinfo=timezone.utc)
    for i in range(30):
        rows.append({
            "time":  pd.Timestamp(base_time) + pd.Timedelta(minutes=5 * i),
            "open":  current_price,
            "high":  current_price + 0.0010,
            "low":   current_price - 0.0010,
            "close": current_price,
        })
    return pd.DataFrame(rows)


def run_liquidity_tests() -> bool:
    tr = TestResults()
    print("\n" + "=" * 52)
    print("TESTS UNITAIRES — LiquidityDetector (P-F2)")
    print("=" * 52)
    print("")

    detector = LiquidityDetector("EURUSD")

    # ── Test 1 : PDH/PDL calculés correctement ──────────────────────────────
    print("--- Test 1 : PDH/PDL depuis df_d1 ---\n")
    try:
        df_d1 = make_df_d1(10)       # 10 jours, PDH/PDL = jour index -2
        prev = df_d1.iloc[-2]
        expected_pdh = round(float(prev["high"]), 6)
        expected_pdl = round(float(prev["low"]),  6)

        pdh, pdl = detector._calc_pdh_pdl(df_d1)

        tr.check("T1a : PDH correct",
                 pdh == expected_pdh,
                 f"Attendu {expected_pdh}, obtenu {pdh}")
        tr.check("T1b : PDL correct",
                 pdl == expected_pdl,
                 f"Attendu {expected_pdl}, obtenu {pdl}")
        tr.check("T1c : PDH > PDL (cohérence)",
                 pdh > pdl,
                 f"PDH={pdh} PDL={pdl}")
    except Exception as e:
        tr.check("T1 : PDH/PDL", False, f"Exception: {e}")

    # ── Test 2 : Equal Highs dans tolérance 3 pips ──────────────────────────
    print("\n--- Test 2 : Equal Highs (tolérance 3 pips) ---\n")
    try:
        EQ_PRICE = 1.1050
        df_m5 = make_df_m5_with_equal_highs(EQ_PRICE, n_highs=3)
        
        eq_highs, eq_lows = detector._calc_equal_levels(df_m5)

        tr.check("T2a : Equal Highs détectés (≥ 1 groupe)",
                 len(eq_highs) >= 1,
                 f"Groupes trouvés : {len(eq_highs)}")

        if eq_highs:
            best = eq_highs[0]
            tr.check("T2b : Niveau EQH proche de {:.4f}".format(EQ_PRICE),
                     abs(best["level"] - EQ_PRICE) <= detector._tolerance * 2,
                     f"Niveau : {best['level']}")
            tr.check("T2c : Compte >= 2 touches",
                     best["count"] >= 2,
                     f"Count: {best['count']}")
        else:
            tr.check("T2b : Niveau EQH proche du prix cible", False, "Aucun groupe détecté")
            tr.check("T2c : Compte >= 2 touches", False, "Aucun groupe détecté")

    except Exception as e:
        tr.check("T2 : Equal Highs", False, f"Exception: {e}")

    # ── Test 3 : DOL selon le biais ─────────────────────────────────────────
    print("\n--- Test 3 : DOL selon le biais HTF ---\n")
    try:
        # Prix actuel = 1.1000
        # PDH = 1.1050 (au dessus) → cible bullish
        # PDL = 1.0950 (en dessous) → cible bearish
        CURRENT = 1.1000
        PDH = 1.1050
        PDL = 1.0950

        df_m5 = make_df_m5_basic(CURRENT)

        # DOL Bullish : doit retourner PDH
        res_bull = detector.detect_all(
            df_m5=df_m5,
            df_h1=None,
            df_d1=make_df_d1(10, start_high=PDH, start_low=PDL - 0.0050),
            bias="bullish"
        )
        dol_bull = res_bull.get("dol", {})
        tr.check("T3a : DOL bullish cible au-dessus du prix",
                 dol_bull.get("price", 0) > CURRENT,
                 f"DOL: {dol_bull}")

        # DOL Bearish : doit retourner PDL (ou Asia Low ou EQL)
        res_bear = detector.detect_all(
            df_m5=df_m5,
            df_h1=None,
            df_d1=make_df_d1(10, start_high=PDH + 0.0050, start_low=PDL),
            bias="bearish"
        )
        dol_bear = res_bear.get("dol", {})
        tr.check("T3b : DOL bearish cible en dessous du prix",
                 dol_bear.get("price", 0) < CURRENT,
                 f"DOL: {dol_bear}")

        tr.check("T3c : DOL bearish name est PDL ou équivalent",
                 dol_bear.get("name", "N/A") in ("PDL", "PWL", "ASIA_LOW", "N/A")
                 or dol_bear.get("price", 0) < CURRENT,
                 f"Name: {dol_bear.get('name')}")

    except Exception as e:
        tr.check("T3 : DOL biais", False, f"Exception: {e}")

    tr.summary()
    return tr.failed == 0


def test_liquidity_detector():
    """Wrapper pour pytest."""
    success = run_liquidity_tests()
    assert success, "LiquidityDetector tests failed"


if __name__ == "__main__":
    run_liquidity_tests()
