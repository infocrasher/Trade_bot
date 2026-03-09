"""
Test Elliott Wave Agent — Données synthétiques
"""
import sys
sys.path.insert(0, '/home/claude/elliott')

import numpy as np
import pandas as pd
from wave_counter import detect_pivots, count_waves, detect_current_wave_position, WaveDirection
from rules_validator import validate_absolute_rules, check_guidelines
from scorer import score_wave_count
from orchestrator import run_elliott_analysis


def generate_impulse_data(n_bars=200, direction="bullish"):
    """Génère des données OHLCV avec une impulsion Elliott 5 vagues."""
    np.random.seed(42)
    
    prices = [100.0]
    
    if direction == "bullish":
        # W1: monte de 100 à 110 (barres 0-30)
        for i in range(30):
            prices.append(prices[-1] + np.random.uniform(0.1, 0.5))
        # W2: descend de 110 à 105 (barres 30-50)
        for i in range(20):
            prices.append(prices[-1] - np.random.uniform(0.05, 0.35))
        # W3: monte de 105 à 125 (barres 50-100) — la plus longue
        for i in range(50):
            prices.append(prices[-1] + np.random.uniform(0.15, 0.6))
        # W4: descend de 125 à 120 (barres 100-120)
        for i in range(20):
            prices.append(prices[-1] - np.random.uniform(0.05, 0.3))
        # W5: monte de 120 à 130 (barres 120-160)
        for i in range(40):
            prices.append(prices[-1] + np.random.uniform(0.05, 0.35))
        # Post: consolide (barres 160-200)
        for i in range(n_bars - 160):
            prices.append(prices[-1] + np.random.uniform(-0.3, 0.3))
    
    prices = prices[:n_bars]
    
    # Construire le DataFrame OHLCV
    data = []
    for i, p in enumerate(prices):
        noise = abs(np.random.normal(0, 0.3))
        data.append({
            'time': pd.Timestamp('2025-01-01') + pd.Timedelta(hours=i*4),
            'open': p - noise/2,
            'high': p + noise,
            'low': p - noise,
            'close': p + noise/2,
            'tick_volume': int(np.random.uniform(1000, 5000)),
        })
    
    df = pd.DataFrame(data)
    return df


def test_pivot_detection():
    """Test 1 : Détection des pivots."""
    print("=" * 60)
    print("TEST 1 : Détection des pivots")
    print("=" * 60)
    
    df = generate_impulse_data()
    pivots = detect_pivots(df, zigzag_pct=0.02)
    
    print(f"Nombre de pivots détectés : {len(pivots)}")
    for p in pivots[:10]:
        print(f"  [{p.pivot_type:4s}] bar={p.bar_index:3d} prix={p.price:.2f}")
    
    if len(pivots) >= 6:
        print("✅ Assez de pivots pour un comptage")
    else:
        print("⚠️ Pas assez de pivots")
    
    return pivots


def test_wave_counting():
    """Test 2 : Comptage des vagues."""
    print("\n" + "=" * 60)
    print("TEST 2 : Comptage des vagues")
    print("=" * 60)
    
    df = generate_impulse_data()
    counts = count_waves(df)
    
    impulses = counts["impulses"]
    corrections = counts["corrections"]
    
    print(f"Impulsions trouvées : {len(impulses)}")
    print(f"Corrections trouvées : {len(corrections)}")
    
    for i, imp in enumerate(impulses[:3]):
        print(f"\n  Impulsion #{i+1} ({imp.direction.value}):")
        for w in imp.waves:
            print(f"    V{w.label}: {w.start.price:.2f} → {w.end.price:.2f} "
                  f"({w.direction}) range={w.price_range:.2f} dur={w.duration}")
    
    return counts


def test_rules_validation():
    """Test 3 : Validation des règles absolues."""
    print("\n" + "=" * 60)
    print("TEST 3 : Validation des règles absolues")
    print("=" * 60)
    
    df = generate_impulse_data()
    counts = count_waves(df)
    
    for imp in counts["impulses"][:5]:
        imp = validate_absolute_rules(imp)
        status = "✅ VALIDE" if imp.valid else "❌ INVALIDE"
        print(f"  {status} ({imp.direction.value})", end="")
        if imp.invalidation_reasons:
            print(f" — {imp.invalidation_reasons[0]}")
        else:
            print()


def test_scoring():
    """Test 4 : Scoring."""
    print("\n" + "=" * 60)
    print("TEST 4 : Scoring")
    print("=" * 60)
    
    df = generate_impulse_data()
    counts = count_waves(df)
    
    for imp in counts["impulses"][:3]:
        imp = score_wave_count(imp)
        if imp.valid:
            print(f"\n  Score: {imp.score}/100 ({imp.direction.value})")
            breakdown = imp.details.get("scoring_breakdown", {})
            for key, val in breakdown.items():
                print(f"    {key}: {val}")
            guidelines = imp.details.get("guidelines", {})
            print(f"    --- Guidelines ---")
            for key, val in guidelines.items():
                print(f"    {key}: {val}")


def test_orchestrator():
    """Test 5 : Orchestrateur complet."""
    print("\n" + "=" * 60)
    print("TEST 5 : Orchestrateur — Signal final")
    print("=" * 60)
    
    df = generate_impulse_data()
    
    dataframes = {"H4": df}
    signal = run_elliott_analysis(dataframes, pair="EURUSD", timeframe="H4")
    
    print(f"\n  Signal: {signal['signal']}")
    print(f"  Score: {signal['score']}/100")
    print(f"  Confiance: {signal['confidence']}")
    print(f"  Entry: {signal['entry']}")
    print(f"  SL: {signal['sl']}")
    print(f"  TP1: {signal['tp1']}")
    print(f"  Raisons: {signal['reasons']}")
    print(f"  Warnings: {signal['warnings']}")
    print(f"  Position: {signal['details'].get('position', {})}")


if __name__ == "__main__":
    test_pivot_detection()
    test_wave_counting()
    test_rules_validation()
    test_scoring()
    test_orchestrator()
    
    print("\n" + "=" * 60)
    print("TOUS LES TESTS TERMINÉS")
    print("=" * 60)
