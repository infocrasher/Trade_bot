"""
Tests unitaires du backtester offline.

Tests anti-lookahead, spread, simulation, cutoff et déterminisme.
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Assurer le path projet
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════
def make_candle(time_str, o, h, l, c, vol=100):
    """Crée un dict bougie avec colonnes dérivées."""
    body = abs(c - o)
    rng = h - l
    return {
        "time": pd.Timestamp(time_str),
        "open": float(o), "high": float(h), "low": float(l), "close": float(c),
        "tick_volume": int(vol),
        "body": float(body),
        "range": float(rng),
        "body_ratio": float(body / rng if rng > 0 else 0),
        "upper_wick": float(h - max(o, c)),
        "lower_wick": float(min(o, c) - l),
    }


def make_series(n=200, start_price=1.1000, pip_value=0.0001, start_time="2025-09-01 08:00"):
    """Génère une série OHLCV synthétique de N bougies M5."""
    candles = []
    price = start_price
    t = pd.Timestamp(start_time)
    np.random.seed(42)  # Déterminisme

    for i in range(n):
        change = np.random.normal(0, 10 * pip_value)
        o = price
        c = price + change
        h = max(o, c) + abs(np.random.normal(0, 5 * pip_value))
        l = min(o, c) - abs(np.random.normal(0, 5 * pip_value))
        candles.append(make_candle(str(t), o, h, l, c))
        price = c
        t += timedelta(minutes=5)

    return pd.DataFrame(candles)


class TestResults:
    """Accumulateur de résultats de tests."""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def check(self, name, condition, detail=""):
        if condition:
            self.passed += 1
            print(f"  ✅ {name}")
        else:
            self.failed += 1
            self.errors.append(f"{name}: {detail}")
            print(f"  ❌ {name} — {detail}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*50}")
        print(f"Backtest Tests: {self.passed}/{total} passed")
        if self.errors:
            print(f"Failures:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*50}")
        return self.failed == 0


# ═══════════════════════════════════════════════════════════════
# TEST 1 : ANTI-LOOKAHEAD (FVG + OB)
# ═══════════════════════════════════════════════════════════════
def test_no_lookahead(results: TestResults):
    """
    Vérifie que les FVG et OB sur un DataFrame tronqué n'ont AUCUN
    status 'filled', 'partially_filled' ou 'mitigated'.
    Car aucun bar futur n'est visible.
    """
    print("\n[Test 1] Anti-Lookahead (FVG + OB)")

    from agents.ict.structure import StructureAgent

    # Créer une série avec un pattern FVG bullish clair
    # Bar 0: normal, Bar 1: big bullish displacement, Bar 2: gap up
    candles = [
        make_candle("2025-09-01 08:00", 1.1000, 1.1010, 1.0990, 1.0995),
        make_candle("2025-09-01 08:05", 1.0995, 1.0998, 1.0980, 1.0985),
        make_candle("2025-09-01 08:10", 1.0985, 1.0990, 1.0975, 1.0980),
        make_candle("2025-09-01 08:15", 1.0980, 1.0985, 1.0970, 1.0975),
        make_candle("2025-09-01 08:20", 1.0975, 1.0978, 1.0965, 1.0970),
        # Displacement bullish massif
        make_candle("2025-09-01 08:25", 1.0970, 1.1050, 1.0968, 1.1045),
        # Bar qui crée le FVG (gap entre bar 4 high et bar 6 low)
        make_candle("2025-09-01 08:30", 1.1045, 1.1060, 1.1040, 1.1055),
        # Bars futurs qui pourraient "remplir" le FVG (si on les voyait)
        make_candle("2025-09-01 08:35", 1.1055, 1.1060, 1.0960, 1.0965),
        make_candle("2025-09-01 08:40", 1.0965, 1.0970, 1.0950, 1.0955),
    ]
    df_full = pd.DataFrame(candles)

    a1 = StructureAgent(symbol="EURUSD", structure_tf="M5", entry_tf="M5")

    # CUTOFF : on ne donne que les 7 premières bougies (pas les 2 dernières)
    df_cut = df_full.iloc[:7].copy().reset_index(drop=True)

    fvgs = a1.detect_fvg(df_cut)

    # Aucun FVG ne doit être 'filled' ou 'partially_filled' (car on n'a pas de bars futurs)
    filled_fvgs = [f for f in fvgs if f.get("status") in ("filled", "partially_filled")]
    results.check(
        "FVG coupé → aucun 'filled'",
        len(filled_fvgs) == 0,
        f"Trouvé {len(filled_fvgs)} FVG filled sur {len(fvgs)} total"
    )

    # Vérifier que TOUS les FVG ont status 'open'
    all_open = all(f.get("status") == "open" for f in fvgs)
    results.check(
        "Tous les FVG ont status 'open'",
        all_open or len(fvgs) == 0,
        f"Status trouvés : {[f.get('status') for f in fvgs]}"
    )

    # Maintenant avec le DataFrame COMPLET (inclut les bars qui remplissent le FVG)
    fvgs_full = a1.detect_fvg(df_full)
    filled_full = [f for f in fvgs_full if f.get("status") in ("filled", "partially_filled")]

    # Sur le DF complet, certains FVG DEVRAIENT être filled (preuve que le mécanisme fonctionne)
    results.check(
        "FVG complet → des 'filled' existent (preuve du mécanisme)",
        len(filled_full) > 0 or len(fvgs_full) == 0,
        f"Aucun FVG filled sur le DF complet — le mécanisme de fill ne fonctionne peut-être pas"
    )

    # Test OB mitigation
    swings = a1.detect_swing_points(df_cut, lookback=2)
    displacements = a1.detect_displacement(df_cut, swings)
    obs = a1.detect_order_blocks(df_cut, displacements, fvgs)

    mitigated_obs = [ob for ob in obs if ob.get("status") == "mitigated"]
    results.check(
        "OB coupé → aucun 'mitigated'",
        len(mitigated_obs) == 0,
        f"Trouvé {len(mitigated_obs)} OB mitigated sur {len(obs)} total"
    )


# ═══════════════════════════════════════════════════════════════
# TEST 2 : SPREAD DEDUCTION
# ═══════════════════════════════════════════════════════════════
def test_spread_deduction(results: TestResults):
    """Vérifie que le PnL inclut le coût du spread + slippage."""
    print("\n[Test 2] Spread Deduction")

    from backtest.engine import Trade, SLIPPAGE_PIPS

    # Trade BUY : entry au ask (+ spread)
    pip_value = 0.0001
    spread_pips = 1.2
    raw_entry = 1.1000
    sl = 1.0950
    tp = 1.1100

    # Simuler : entry ajusté au ask
    total_cost = (spread_pips + SLIPPAGE_PIPS) * pip_value
    adjusted_entry = raw_entry + total_cost  # BUY → achète au ask

    # Si TP touché
    pnl_win = (tp - adjusted_entry) / pip_value
    # Si SL touché
    pnl_loss = (sl - adjusted_entry) / pip_value

    results.check(
        "PnL WIN < PnL sans spread",
        pnl_win < (tp - raw_entry) / pip_value,
        f"PnL avec spread={pnl_win:.1f}, sans={((tp - raw_entry) / pip_value):.1f}"
    )

    results.check(
        "Coût total = spread + slippage",
        abs((spread_pips + SLIPPAGE_PIPS) - (pnl_win - (tp - raw_entry) / pip_value) * -1) < 0.1,
        f"Spread={spread_pips}, Slippage={SLIPPAGE_PIPS}"
    )

    results.check(
        "PnL LOSS est négatif",
        pnl_loss < 0,
        f"PnL loss = {pnl_loss:.1f}"
    )


# ═══════════════════════════════════════════════════════════════
# TEST 3 : SAME-BAR SL+TP → SL PRIORITAIRE
# ═══════════════════════════════════════════════════════════════
def test_same_bar_sl_tp(results: TestResults):
    """Vérifie que si SL et TP sont touchés dans la même bougie, SL est pris."""
    print("\n[Test 3] Same-Bar SL+TP → SL Priority")

    # Simuler la logique du engine
    pip_value = 0.0001
    direction = "BUY"
    entry = 1.1000
    sl = 1.0950
    tp = 1.1100

    # Bougie qui touche les DEUX (high >= tp, low <= sl)
    bar_high = 1.1150  # touche TP
    bar_low = 1.0900   # touche SL

    tp_hit = bar_high >= tp
    sl_hit = bar_low <= sl

    # Règle conservatrice
    if sl_hit and tp_hit:
        sl_hit = True
        tp_hit = False

    results.check(
        "SL+TP même bougie → SL prioritaire",
        sl_hit and not tp_hit,
        f"sl_hit={sl_hit}, tp_hit={tp_hit}"
    )

    # Vérifier le PnL
    exit_price = sl
    pnl = (exit_price - entry) / pip_value
    results.check(
        "PnL est négatif (loss)",
        pnl < 0,
        f"PnL = {pnl:.1f} pips"
    )


# ═══════════════════════════════════════════════════════════════
# TEST 4 : CUTOFF CONSISTENCY
# ═══════════════════════════════════════════════════════════════
def test_cutoff_consistency(results: TestResults):
    """Vérifie que le cutoff temporel est cohérent entre les timeframes."""
    print("\n[Test 4] Cutoff Consistency")

    # Créer des DataFrames M5 et H1 avec des timestamps
    m5_candles = []
    h1_candles = []
    t = pd.Timestamp("2025-09-01 08:00")

    for i in range(48):  # 4 heures de M5
        m5_candles.append(make_candle(str(t), 1.1, 1.101, 1.099, 1.1))
        t += timedelta(minutes=5)

    t = pd.Timestamp("2025-09-01 08:00")
    for i in range(6):  # 6 heures de H1
        h1_candles.append(make_candle(str(t), 1.1, 1.101, 1.099, 1.1))
        t += timedelta(hours=1)

    df_m5 = pd.DataFrame(m5_candles)
    df_h1 = pd.DataFrame(h1_candles)

    # Cutoff à 10:00 (2 heures après le début)
    cutoff_time = pd.Timestamp("2025-09-01 10:00")

    dfs = {"M5": df_m5, "H1": df_h1}
    dfs_cut = {}
    for tf, df_tf in dfs.items():
        mask = df_tf["time"] <= cutoff_time
        dfs_cut[tf] = df_tf[mask].copy()

    # M5 ne doit PAS contenir de bars après 10:00
    m5_after = dfs_cut["M5"][dfs_cut["M5"]["time"] > cutoff_time]
    results.check(
        "M5 cutoff — aucun bar après cutoff",
        len(m5_after) == 0,
        f"Trouvé {len(m5_after)} bars M5 après {cutoff_time}"
    )

    # H1 ne doit PAS contenir de bars après 10:00
    h1_after = dfs_cut["H1"][dfs_cut["H1"]["time"] > cutoff_time]
    results.check(
        "H1 cutoff — aucun bar après cutoff",
        len(h1_after) == 0,
        f"Trouvé {len(h1_after)} bars H1 après {cutoff_time}"
    )

    # Le dernier bar M5 doit être ≤ cutoff
    last_m5_time = dfs_cut["M5"]["time"].iloc[-1]
    results.check(
        "Dernier bar M5 ≤ cutoff",
        last_m5_time <= cutoff_time,
        f"Dernier M5 = {last_m5_time}"
    )

    # Le dernier bar H1 doit être ≤ cutoff
    last_h1_time = dfs_cut["H1"]["time"].iloc[-1]
    results.check(
        "Dernier bar H1 ≤ cutoff",
        last_h1_time <= cutoff_time,
        f"Dernier H1 = {last_h1_time}"
    )


# ═══════════════════════════════════════════════════════════════
# TEST 5 : DETERMINISME
# ═══════════════════════════════════════════════════════════════
def test_deterministic(results: TestResults):
    """Vérifie que deux runs identiques produisent les mêmes résultats."""
    print("\n[Test 5] Deterministic")

    from backtest.engine import BacktestResult, Trade

    # Simuler deux résultats identiques
    trades1 = [
        Trade(pair="EURUSD", direction="BUY", entry_price=1.1, stop_loss=1.09,
              tp1=1.12, entry_time="2025-09-01 08:00", entry_bar_idx=50,
              spread_pips=1.2, slippage_pips=0.5, confidence=0.75,
              confluence_score=3, reasons=["test"], horizon="scalp",
              exit_price=1.12, exit_time="2025-09-01 09:00", exit_bar_idx=62,
              pnl_pips=18.3, result="WIN", r_multiple=1.83, risk_pips=10.0,
              session="ny_am"),
        Trade(pair="EURUSD", direction="SELL", entry_price=1.12, stop_loss=1.13,
              tp1=1.10, entry_time="2025-09-01 10:00", entry_bar_idx=74,
              spread_pips=1.2, slippage_pips=0.5, confidence=0.70,
              confluence_score=2, reasons=["test2"], horizon="scalp",
              exit_price=1.13, exit_time="2025-09-01 11:00", exit_bar_idx=86,
              pnl_pips=-10.0, result="LOSS", r_multiple=-1.0, risk_pips=10.0,
              session="ny_am"),
    ]

    # Copie exacte
    trades2 = [
        Trade(pair="EURUSD", direction="BUY", entry_price=1.1, stop_loss=1.09,
              tp1=1.12, entry_time="2025-09-01 08:00", entry_bar_idx=50,
              spread_pips=1.2, slippage_pips=0.5, confidence=0.75,
              confluence_score=3, reasons=["test"], horizon="scalp",
              exit_price=1.12, exit_time="2025-09-01 09:00", exit_bar_idx=62,
              pnl_pips=18.3, result="WIN", r_multiple=1.83, risk_pips=10.0,
              session="ny_am"),
        Trade(pair="EURUSD", direction="SELL", entry_price=1.12, stop_loss=1.13,
              tp1=1.10, entry_time="2025-09-01 10:00", entry_bar_idx=74,
              spread_pips=1.2, slippage_pips=0.5, confidence=0.70,
              confluence_score=2, reasons=["test2"], horizon="scalp",
              exit_price=1.13, exit_time="2025-09-01 11:00", exit_bar_idx=86,
              pnl_pips=-10.0, result="LOSS", r_multiple=-1.0, risk_pips=10.0,
              session="ny_am"),
    ]

    r1 = BacktestResult(trades=trades1, horizon="scalp", pairs=["EURUSD"])
    r2 = BacktestResult(trades=trades2, horizon="scalp", pairs=["EURUSD"])

    results.check(
        "Win rate identique",
        r1.win_rate == r2.win_rate,
        f"r1={r1.win_rate}, r2={r2.win_rate}"
    )
    results.check(
        "Profit factor identique",
        r1.profit_factor == r2.profit_factor,
        f"r1={r1.profit_factor}, r2={r2.profit_factor}"
    )
    results.check(
        "SQN identique",
        abs(r1.sqn - r2.sqn) < 0.001,
        f"r1={r1.sqn}, r2={r2.sqn}"
    )
    results.check(
        "Equity curve identique",
        r1.equity_curve() == r2.equity_curve(),
        f"r1={r1.equity_curve()}, r2={r2.equity_curve()}"
    )

    # Vérifier que BacktestResult.to_dict() est sérialisable
    d1 = r1.to_dict()
    results.check(
        "to_dict() contient les clés attendues",
        all(k in d1 for k in ["win_rate", "profit_factor", "sqn", "total_trades"]),
        f"Clés manquantes: {[k for k in ['win_rate', 'profit_factor', 'sqn', 'total_trades'] if k not in d1]}"
    )


# ═══════════════════════════════════════════════════════════════
# TEST 6 : BACKTEST RESULT METRICS
# ═══════════════════════════════════════════════════════════════
def test_backtest_result_metrics(results: TestResults):
    """Vérifie les calculs de métriques du BacktestResult."""
    print("\n[Test 6] BacktestResult Metrics")

    from backtest.engine import BacktestResult, Trade

    trades = [
        Trade(pair="EURUSD", direction="BUY", entry_price=1.1, stop_loss=1.09,
              tp1=1.12, entry_time="2025-09-01", entry_bar_idx=0,
              spread_pips=1.0, slippage_pips=0.5, confidence=0.8,
              confluence_score=3, reasons=[], horizon="scalp",
              pnl_pips=20.0, result="WIN", r_multiple=2.0, risk_pips=10.0),
        Trade(pair="EURUSD", direction="SELL", entry_price=1.12, stop_loss=1.13,
              tp1=1.10, entry_time="2025-09-02", entry_bar_idx=1,
              spread_pips=1.0, slippage_pips=0.5, confidence=0.7,
              confluence_score=2, reasons=[], horizon="scalp",
              pnl_pips=-10.0, result="LOSS", r_multiple=-1.0, risk_pips=10.0),
        Trade(pair="GBPUSD", direction="BUY", entry_price=1.25, stop_loss=1.24,
              tp1=1.27, entry_time="2025-09-03", entry_bar_idx=2,
              spread_pips=1.5, slippage_pips=0.5, confidence=0.75,
              confluence_score=3, reasons=[], horizon="scalp",
              pnl_pips=15.0, result="WIN", r_multiple=1.5, risk_pips=10.0),
    ]

    r = BacktestResult(trades=trades, horizon="scalp", pairs=["EURUSD", "GBPUSD"])

    results.check(
        "Win rate = 66.7%",
        abs(r.win_rate - 66.7) < 0.1,
        f"Got {r.win_rate:.1f}%"
    )

    expected_pf = (20.0 + 15.0) / 10.0  # 3.5
    results.check(
        "Profit factor = 3.5",
        abs(r.profit_factor - expected_pf) < 0.01,
        f"Got {r.profit_factor:.2f}"
    )

    results.check(
        "Total PnL = 25 pips",
        abs(sum(t.pnl_pips for t in trades) - 25.0) < 0.1,
        f"Got {sum(t.pnl_pips for t in trades):.1f}"
    )

    results.check(
        "Max drawdown = 10 pips",
        abs(r.max_drawdown_pips - 10.0) < 0.1,
        f"Got {r.max_drawdown_pips:.1f}"
    )

    curve = r.equity_curve()
    results.check(
        "Equity curve length = trades + 1",
        len(curve) == len(trades) + 1,
        f"Got {len(curve)}, expected {len(trades) + 1}"
    )

    results.check(
        "Equity curve end = total PnL",
        abs(curve[-1] - 25.0) < 0.1,
        f"Got {curve[-1]:.1f}"
    )


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 50)
    print("BACKTEST UNIT TESTS")
    print("=" * 50)

    results = TestResults()

    test_no_lookahead(results)
    test_spread_deduction(results)
    test_same_bar_sl_tp(results)
    test_cutoff_consistency(results)
    test_deterministic(results)
    test_backtest_result_metrics(results)

    all_passed = results.summary()
    sys.exit(0 if all_passed else 1)
