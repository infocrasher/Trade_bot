import pandas as pd
import numpy as np
from datetime import datetime
from agents.agent_structure import StructureAgent
from agents.agent_time_session import TimeSessionAgent, to_ny_time
from agents.news_manager import NewsManager
from unittest.mock import patch

class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def check(self, test_name: str, condition: bool, detail: str = ""):
        if condition:
            self.passed += 1
            print(f"  ✅ PASS : {test_name}")
        else:
            self.failed += 1
            self.errors.append(test_name)
            print(f"  ❌ FAIL : {test_name} — {detail}")
    
    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*50}")
        print(f"RÉSULTATS : {self.passed}/{total} tests passés")
        if self.errors:
            print(f"Tests échoués :")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*50}")


def make_candle(time_str, o, h, l, c, vol=100):
    """Helper pour créer une bougie OHLCV."""
    body = abs(c - o)
    rng = h - l
    return {
        "time": pd.Timestamp(time_str),
        "open": float(o), "high": float(h), "low": float(l), "close": float(c),
        "tick_volume": int(vol),
        "body": float(body),
        "range": float(rng),
        "body_ratio": float(body / rng if rng > 0 else 0)
    }

# ============================================================
# PARTIE A — Tests Agent 1
# ============================================================
def test_agent1(results: TestResults):
    agent = StructureAgent(symbol="EURUSD")
    
    print("\n--- AGENT 1 : Structure & Liquidity ---\n")
    
    # Test A1 : Détection Strong Swing High (3 bougies)
    try:
        # Création de 20 bougies, index 10 = swing high
        candles = []
        for i in range(20):
            h = 1.0950
            if i == 10: h = 1.1000
            elif i in [9, 11]: h = 1.0980
            elif i in [8, 12]: h = 1.0960
            elif i in [7, 13]: h = 1.0930
            # Utiliser des minutes au lieu d'heures pour éviter de dépasser 23h
            candles.append(make_candle(f"2025-01-15 08:{i:02d}", 1.0900, h, 1.0850, 1.0900))
        
        df = pd.DataFrame(candles)
        swings = agent.detect_swing_points(df, lookback=3)
        sh_10 = [s for s in swings if s['index'] == 10 and s['type'] == 'swing_high']
        
        results.check("A1 : Détection Strong Swing High", len(sh_10) == 1 and sh_10[0]['price'] == 1.1000, "Swing High non détecté ou prix incorrect")
    except Exception as e:
        results.check("A1 : Détection Strong Swing High", False, f"Exception: {e}")

    # Test A2 : Détection Strong Swing Low
    try:
        candles = []
        for i in range(20):
            l = 1.0950
            if i == 10: l = 1.0800
            elif i in [9, 11]: l = 1.0820
            elif i in [8, 12]: l = 1.0850
            elif i in [7, 13]: l = 1.0880
            candles.append(make_candle(f"2025-01-15 08:{i:02d}", 1.0900, 1.1000, l, 1.0900))
        
        df = pd.DataFrame(candles)
        swings = agent.detect_swing_points(df, lookback=3)
        sl_10 = [s for s in swings if s['index'] == 10 and s['type'] == 'swing_low']
        
        results.check("A2 : Détection Strong Swing Low", len(sl_10) == 1 and sl_10[0]['price'] == 1.0800, "Swing Low non détecté")
    except Exception as e:
        results.check("A2 : Détection Strong Swing Low", False, f"Exception: {e}")

    # Test A3 : Détection FVG Bullish
    try:
        c0 = make_candle("2025-01-15 08:00", 1.0880, 1.0900, 1.0850, 1.0890)
        c1 = make_candle("2025-01-15 09:00", 1.0895, 1.0980, 1.0890, 1.0970)
        c2 = make_candle("2025-01-15 10:00", 1.0970, 1.1050, 1.0920, 1.1000)
        df = pd.DataFrame([c0, c1, c2])
        
        fvgs = agent.detect_fvg(df)
        fvg = fvgs[0] if fvgs else None
        
        ok = fvg and fvg['type'] == 'bullish_fvg' and fvg['bottom'] == 1.0900 and fvg['top'] == 1.0920 and fvg['status'] == 'open'
        results.check("A3 : Détection FVG Bullish", ok, "FVG Bullish non détecté ou zones fausses")
    except Exception as e:
        results.check("A3 : Détection FVG Bullish", False, f"Exception: {e}")

    # Test A4 : Détection FVG Bearish
    try:
        c0 = make_candle("2025-01-15 08:00", 1.1020, 1.1050, 1.1000, 1.1010)
        c1 = make_candle("2025-01-15 09:00", 1.1000, 1.1010, 1.0920, 1.0930)
        c2 = make_candle("2025-01-15 10:00", 1.0930, 1.0980, 1.0900, 1.0910)
        df = pd.DataFrame([c0, c1, c2])
        
        fvgs = agent.detect_fvg(df)
        fvg = fvgs[0] if fvgs else None
        
        ok = fvg and fvg['type'] == 'bearish_fvg' and fvg['top'] == 1.1000 and fvg['bottom'] == 1.0980 and fvg['status'] == 'open'
        results.check("A4 : Détection FVG Bearish", ok, "FVG Bearish non détecté ou fausses zones")
    except Exception as e:
        results.check("A4 : Détection FVG Bearish", False, f"Exception: {e}")

    # Test A5 : FVG status "filled"
    try:
        c0 = make_candle("2025-01-15 08:00", 1.0880, 1.0900, 1.0850, 1.0890)
        c1 = make_candle("2025-01-15 09:00", 1.0895, 1.0980, 1.0890, 1.0970) # Disp
        c2 = make_candle("2025-01-15 10:00", 1.0970, 1.1050, 1.0920, 1.1000) # FVG créé: [1.09, 1.092]
        c3 = make_candle("2025-01-15 11:00", 1.1000, 1.1010, 1.0880, 1.0950) # Low < 1.09 -> Filled
        df = pd.DataFrame([c0, c1, c2, c3])
        
        fvgs = agent.detect_fvg(df)
        results.check("A5 : FVG status filled", fvgs[0]['status'] == 'filled', "FVG non marqué comme filled")
    except Exception as e:
         results.check("A5 : FVG status filled", False, f"Exception: {e}")

    # Test A6 : Détection Order Block Bullish
    try:
        candles = []
        # Bougies 0-20 : tendance lente (petits corps)
        for i in range(21):
            candles.append(make_candle(f"2025-01-15 08:{i:02d}", 1.1000, 1.1000, 1.0950, 1.0980))
            
        # Création Swing High à casser (idx 10)
        candles[10] = make_candle(f"2025-01-15 08:10", 1.1000, 1.1100, 1.0950, 1.0980)
            
        # 21: Dernière bougie baissière (OB)
        candles.append(make_candle(f"2025-01-15 08:21", 1.0980, 1.0990, 1.0850, 1.0860))
        # 22: Displacement qui casse le high de l'id 10
        candles.append(make_candle(f"2025-01-15 08:22", 1.0860, 1.1200, 1.0850, 1.1150))
        # 23: Bougie pour confirmer le FVG 
        candles.append(make_candle(f"2025-01-15 08:23", 1.1150, 1.1300, 1.1100, 1.1250))
        
        df = pd.DataFrame(candles)
        swings = agent.detect_swing_points(df, lookback=3)
        fvgs = agent.detect_fvg(df)
        displacements = agent.detect_displacement(df, swings, avg_period=10)
        obs = agent.detect_order_blocks(df, displacements, fvgs)
        
        ob = [o for o in obs if o['index'] == 21]
        ok = len(ob) > 0 and ob[0]['type'] == 'bullish_ob' and ob[0]['has_fvg_confluence']
        results.check("A6 : Détection OB Bullish", ok, "Bullish OB non détecté ou sans confluence")
    except Exception as e:
         results.check("A6 : Détection OB Bullish", False, f"Exception: {e}")

    # Test A7 : Détection BOS Bullish
    try:
        candles = []
        for i in range(15):
             h = 1.0900 if i == 5 else 1.0850
             l = 1.0800 if i == 2 else 1.0820
             candles.append(make_candle(f"2025-01-15 08:{i:02d}", 1.0850, h, l, 1.0860))
             
        # Idx 5 est swing_high (1.09), on le casse
        candles.append(make_candle(f"2025-01-15 08:15", 1.0860, 1.0950, 1.0850, 1.0920)) # Close > 1.09
        df = pd.DataFrame(candles)
        swings = agent.detect_swing_points(df, lookback=2)
        events = agent.detect_bos_choch(df, swings)
        
        bos = [e for e in events if e['type'] == 'bullish_bos' and e['broken_level'] == 1.09]
        results.check("A7 : Détection BOS Bullish", len(bos) > 0, "BOS Bullish non détecté")
    except Exception as e:
         results.check("A7 : Détection BOS Bullish", False, f"Exception: {e}")

    # Test A8 : Détection CHoCH Bearish
    try:
        candles = []
        # On construit manuellement une séquence bullish claire avec lookback=2
        # Besoin : swing_low PUIS swing_high (trend = bullish), puis casser le swing_low
        
        # Bougies 0-4 : descente vers swing low à idx 2
        candles.append(make_candle("2025-01-15 08:00", 1.0900, 1.0920, 1.0880, 1.0890))  # 0
        candles.append(make_candle("2025-01-15 08:01", 1.0890, 1.0900, 1.0870, 1.0880))  # 1
        candles.append(make_candle("2025-01-15 08:02", 1.0880, 1.0890, 1.0800, 1.0850))  # 2 = SWING LOW (1.0800)
        candles.append(make_candle("2025-01-15 08:03", 1.0850, 1.0900, 1.0840, 1.0890))  # 3
        candles.append(make_candle("2025-01-15 08:04", 1.0890, 1.0920, 1.0870, 1.0910))  # 4
        
        # Bougies 5-9 : montée vers swing high à idx 7
        candles.append(make_candle("2025-01-15 08:05", 1.0910, 1.0950, 1.0900, 1.0940))  # 5
        candles.append(make_candle("2025-01-15 08:06", 1.0940, 1.0980, 1.0930, 1.0970))  # 6
        candles.append(make_candle("2025-01-15 08:07", 1.0970, 1.1050, 1.0960, 1.1000))  # 7 = SWING HIGH (1.1050)
        candles.append(make_candle("2025-01-15 08:08", 1.1000, 1.1020, 1.0950, 1.0970))  # 8
        candles.append(make_candle("2025-01-15 08:09", 1.0970, 1.0990, 1.0940, 1.0960))  # 9
        
        # Bougies 10-14 : retrace vers higher low à idx 12
        candles.append(make_candle("2025-01-15 08:10", 1.0960, 1.0970, 1.0920, 1.0930))  # 10
        candles.append(make_candle("2025-01-15 08:11", 1.0930, 1.0940, 1.0900, 1.0910))  # 11
        candles.append(make_candle("2025-01-15 08:12", 1.0910, 1.0920, 1.0880, 1.0900))  # 12 = HIGHER LOW (1.0880)
        candles.append(make_candle("2025-01-15 08:13", 1.0900, 1.0930, 1.0890, 1.0920))  # 13
        candles.append(make_candle("2025-01-15 08:14", 1.0920, 1.0950, 1.0910, 1.0940))  # 14
        
        # Bougie 15 : CASSE le higher low (1.0880) -> CHoCH bearish
        candles.append(make_candle("2025-01-15 08:15", 1.0940, 1.0940, 1.0820, 1.0850))  # 15: close 1.085 < 1.088
        
        df = pd.DataFrame(candles)
        swings = agent.detect_swing_points(df, lookback=2)
        events = agent.detect_bos_choch(df, swings)
        
        choch = [e for e in events if 'bearish_choch' in e['type']]
        results.check("A8 : Détection CHoCH Bearish", len(choch) > 0, f"CHoCH non détecté. Swings: {[(s['index'],s['type'],s['price']) for s in swings]} Events: {events}")
    except Exception as e:
        results.check("A8 : Détection CHoCH Bearish", False, f"Exception: {e}")

    # Test A9 : Détection Liquidity Sweep Buyside
    try:
        candles = []
        for i in range(15):
            h = 1.1000 if i == 5 else 1.0900
            candles.append(make_candle(f"2025-01-15 08:{i:02d}", 1.0850, h, 1.0800, 1.0860))
        # Bougie pour balayer le high 1.100 (Wick à 1.1015, close 1.0980)
        candles.append(make_candle(f"2025-01-15 08:15", 1.0900, 1.1015, 1.0900, 1.0980))
        
        df = pd.DataFrame(candles)
        swings = agent.detect_swing_points(df, lookback=2)
        sweeps = agent.detect_liquidity_sweeps(df, swings)
        
        res = [s for s in sweeps if s['type'] == 'buyside_sweep' and s['swept_level'] == 1.1000]
        results.check("A9 : Détection Liquidity Sweep Buyside", len(res) > 0, "Sweep non détecté")
    except Exception as e:
        results.check("A9 : Détection Liquidity Sweep Buyside", False, f"Exception: {e}")

    # Test A10 : Détection Liquidity Sweep Sellside
    try:
        candles = []
        for i in range(15):
            l = 1.0800 if i == 5 else 1.0900
            candles.append(make_candle(f"2025-01-15 08:{i:02d}", 1.0950, 1.1000, l, 1.0920))
        # Bougie pour balayer le low 1.080 (Wick à 1.0780, close 1.0820)
        candles.append(make_candle(f"2025-01-15 08:15", 1.0900, 1.0950, 1.0780, 1.0820))
        
        df = pd.DataFrame(candles)
        swings = agent.detect_swing_points(df, lookback=2)
        sweeps = agent.detect_liquidity_sweeps(df, swings)
        
        res = [s for s in sweeps if s['type'] == 'sellside_sweep' and s['swept_level'] == 1.0800]
        results.check("A10 : Détection Liquidity Sweep Sellside", len(res) > 0, "Sweep non détecté")
    except Exception as e:
        results.check("A10 : Détection Liquidity Sweep Sellside", False, f"Exception: {e}")

    # Test A11 : Displacement force et propreté (Valide)
    try:
        candles = [make_candle(f"2025-01-15 08:{i:02d}", 1.100, 1.102, 1.099, 1.102) for i in range(10)]
        # Creation Swing (index 5) = 1.105
        candles[5] = make_candle(f"2025-01-15 08:05", 1.100, 1.105, 1.095, 1.100)
        # Avg body ~ 0.002
        # Candle 10: Disp -> body=0.006 (3x avg ✓), ratio=0.006/0.0075=0.80 ✓, close > 1.105 ✓
        candles.append(make_candle(f"2025-01-15 08:10", 1.1000, 1.1075, 1.1000, 1.1060)) 
        
        df = pd.DataFrame(candles)
        swings = agent.detect_swing_points(df, lookback=2)
        disp = agent.detect_displacement(df, swings, avg_period=10)
        
        ok = len(disp) > 0 and disp[0]['type'] == 'bullish_displacement'
        results.check("A11 : Displacement - force et propreté ✓", ok, "Displacement non détecté")
    except Exception as e:
        results.check("A11 : Displacement - force et propreté ✓", False, f"Exception: {e}")

    # Test A12 : Displacement rejeté — corps trop petit
    try:
        candles = [make_candle(f"2025-01-15 08:{i:02d}", 1.100, 1.102, 1.099, 1.102) for i in range(10)]
        candles[5] = make_candle(f"2025-01-15 08:05", 1.100, 1.105, 1.095, 1.100)
        # body 0.0022 -> invalide
        candles.append(make_candle(f"2025-01-15 08:10", 1.1030, 1.1060, 1.1000, 1.1052))
        
        df = pd.DataFrame(candles)
        swings = agent.detect_swing_points(df, lookback=2)
        disp = agent.detect_displacement(df, swings, avg_period=10)
        results.check("A12 : Displacement rejeté (corps petit)", len(disp) == 0, "Faux positif")
    except Exception as e:
         results.check("A12 : Displacement rejeté (corps petit)", False, f"Exception: {e}")

    # Test A13 : Displacement rejeté — trop de mèche
    try:
        candles = [make_candle(f"2025-01-15 08:{i:02d}", 1.100, 1.102, 1.099, 1.102) for i in range(10)]
        candles[5] = make_candle(f"2025-01-15 08:05", 1.100, 1.105, 1.095, 1.100)
        # Ratio faible: gros range(0.012), body(0.005) -> ratio = 0.41 < 0.70
        candles.append(make_candle(f"2025-01-15 08:10", 1.1010, 1.1130, 1.1010, 1.1060))
        
        df = pd.DataFrame(candles)
        swings = agent.detect_swing_points(df, lookback=2)
        disp = agent.detect_displacement(df, swings, avg_period=10)
        results.check("A13 : Displacement rejeté (mèches)", len(disp) == 0, "Faux positif")
    except Exception as e:
        results.check("A13 : Displacement rejeté (mèches)", False, f"Exception: {e}")


# ============================================================
# PARTIE B — Tests Agent 2
# ============================================================
def test_agent2(results: TestResults):
    agent = TimeSessionAgent(broker_utc_offset=2)
    
    print("\n--- AGENT 2 : Time & Session ---\n")
    
    # B1 : Killzone London active
    try:
        t = datetime(2025, 1, 15, 3, 30) # 03:30 NY
        kz = agent.get_active_killzone(t)
        results.check("B1 : Killzone London", kz and kz['id'] == 'london' and abs(kz['minutes_remaining']-90) <= 1, "Mauvaise KZ ou time")
    except Exception as e: results.check("B1", False, f"Exception: {e}")

    # B2 : Killzone NY AM active
    try:
        t = datetime(2025, 1, 15, 8, 0)
        kz = agent.get_active_killzone(t)
        results.check("B2 : Killzone NY AM", kz and kz['id'] == 'ny_am', "Mauvaise KZ")
    except Exception as e: results.check("B2", False, f"Exception: {e}")

    # B3 : Hors killzone
    try:
        t = datetime(2025, 1, 15, 6, 0)
        kz = agent.get_active_killzone(t)
        results.check("B3 : Hors KZ", kz is None, "KZ inattendue détectée")
    except Exception as e: results.check("B3", False, f"Exception: {e}")

    # B4 : Killzone Asian (passage minuit)
    try:
        t1 = datetime(2025, 1, 14, 20, 0)
        t2 = datetime(2025, 1, 14, 23, 30)
        kz1 = agent.get_active_killzone(t1)
        kz2 = agent.get_active_killzone(t2)
        results.check("B4 : Killzone Asian (minuit)", kz1['id'] == 'asian' and kz2['id'] == 'asian', "Asian KZ manquée")
    except Exception as e: results.check("B4", False, f"Exception: {e}")

    # B5 : Silver Bullet NY AM
    try:
        t = datetime(2025, 1, 15, 10, 30)
        sb = agent.get_active_silver_bullet(t)
        results.check("B5 : SB NY AM", sb and sb['id'] == 'ny_am_sb', "SB NY AM non détectée")
    except Exception as e: results.check("B5", False, f"Exception: {e}")

    # B6 : Silver Bullet edge cases
    try:
        t1 = datetime(2025, 1, 15, 10, 0)
        t2 = datetime(2025, 1, 15, 11, 0)
        sb1 = agent.get_active_silver_bullet(t1)
        sb2 = agent.get_active_silver_bullet(t2)
        results.check("B6 : SB Bornes", sb1 and sb1['id'] == 'ny_am_sb' and sb2 is None, "Erreur bornes SB")
    except Exception as e: results.check("B6", False, f"Exception: {e}")

    # B7 : Day filter Mardi
    try:
        t = datetime(2025, 1, 14, 10, 0) # Mardi
        df = agent.get_day_filter(t)
        results.check("B7 : Day Filter Mardi", df['quality'] == 'prime' and df['can_trade'], "Mauvais filter")
    except Exception as e: results.check("B7", False, f"Exception: {e}")

    # B8 : Day filter Vendredi
    try:
        t = datetime(2025, 1, 17, 10, 0) # Vendredi
        df = agent.get_day_filter(t)
        results.check("B8 : Day Filter Vendredi", df['quality'] == 'caution' and not df['can_trade'], "Mauvais filter")
    except Exception as e: results.check("B8", False, f"Exception: {e}")

    # B9 : Day filter Samedi
    try:
        t = datetime(2025, 1, 18, 10, 0) # Samedi
        df = agent.get_day_filter(t)
        results.check("B9 : Day Filter Samedi", df['quality'] == 'closed' and not df['can_trade'], "Mauvais filter")
    except Exception as e: results.check("B9", False, f"Exception: {e}")

    # B10 : PO3 Phase Manipulation
    try:
        ar = {"high": 1.0900, "low": 1.0850, "is_complete": True}
        # Broker time (offset 2) -> 2025-01-15 03:00 NY = 10:00 Broker (3h+5h NY offset + 2h broker)
        # Mais pour pas s'embrouiller, utilisons directement les broker times correspondants aux cassures
        candles = [make_candle("2025-01-15 10:00", 1.0900, 1.0910, 1.0850, 1.0860)] # NY=03:00, High=1.091>1.09
        df = pd.DataFrame(candles)
        
        t_ny = datetime(2025, 1, 15, 3, 0)
        po3 = agent.get_po3_phase(t_ny, df, ar)
        ok = po3['phase'] == 'manipulation' and po3['suggested_bias'] == 'bearish' and po3['asian_range_broken'] == 'high'
        results.check("B10 : PO3 Manipulation", ok, "Mauvaise phase PO3/Biais")
    except Exception as e: results.check("B10", False, f"Exception: {e}")

    # B11 : PO3 Phase Accumulation
    try:
        t_ny = datetime(2025, 1, 14, 20, 0)
        ar = {"is_complete": False}
        po3 = agent.get_po3_phase(t_ny, pd.DataFrame(), ar)
        results.check("B11 : PO3 Accumulation", po3['phase'] == 'accumulation', "Mauvaise phase")
    except Exception as e: results.check("B11", False, f"Exception: {e}")

    # B12 : Conversion Time NY
    try:
        bt = datetime(2025, 1, 15, 9, 30) # 09:30 Broker (UTC+2) -> 07:30 UTC -> 02:30 NY (UTC-5)
        nyt = to_ny_time(bt, 2)
        results.check("B12 : Conversion Heure NY", nyt.hour == 2 and nyt.minute == 30, "Mise à l'heure fausse")
    except Exception as e: results.check("B12", False, f"Exception: {e}")

    # B13 : Trade Quality High
    try:
        # Fausser les dates/data pour trigger le high
        t_ny = datetime(2025, 1, 15, 3, 30) # Mercredi (prime), London KZ (3h-4h=SB) => high
        
        # ar OK
        ar = {"high": 1.0900, "low": 1.0850, "is_complete": True}
        # Un fake sweep en London (Broker time = NY(3h30)+7 = 10:30)
        c0 = make_candle("2025-01-15 09:00", 1.0880, 1.0890, 1.0860, 1.0880) # Pre
        c1 = make_candle("2025-01-15 10:00", 1.0900, 1.0920, 1.0890, 1.0910) # Sweep le ar_high (1.0900)
        c2 = make_candle("2025-01-15 10:30", 1.0910, 1.0910, 1.0850, 1.0880) # Revient sous le AR (Close<Ar_high)
        df = pd.DataFrame([c0, c1, c2])
        
        judas = agent.detect_judas_swing(df, ar, t_ny)
        # On a London SB (03:00-04:00 NY), prime day, judas-> True
        sb = agent.get_active_silver_bullet(t_ny)
        df_f = agent.get_day_filter(t_ny)
        
        ok = judas['detected'] and sb and df_f['quality'] == 'prime'
        results.check("B13 : Trade Quality High", ok, f"Conditions pas atteintes: J={judas['detected']} S={sb is not None}")
    except Exception as e: results.check("B13", False, f"Exception: {e}")
    
    # B14 : Trade Quality No Trade
    try:
        bt = datetime(2025, 1, 15, 13, 0) # 13:00 Broker -> 06:00 NY (Hors KZ)
        df = pd.DataFrame([make_candle("2025-01-15 13:00", 1, 1, 1, 1)])
        report = agent.analyze(df, bt)
        results.check("B14 : Trade Quality None", report['trade_quality'] == 'no_trade', "Mouvement autorisé à tort")
    except Exception as e: results.check("B14", False, f"Exception: {e}")

# ============================================================
# PARTIE C — Tests News Manager (Phase F)
# ============================================================
def test_news_manager(results: TestResults):
    print("\n--- PHASE F : News Manager (Finnhub) ---\n")
    
    # Simuler des news dans le manager
    fake_news = [
        {"time": "2026-03-19 12:30:00", "unit": "USD", "impact": "high", "event": "CPI m/m"},
        {"time": "2026-03-19 14:00:00", "unit": "EUR", "impact": "medium", "event": "German ZEW"},
        {"time": "2026-03-19 16:00:00", "unit": "USD", "impact": "high", "event": "FOMC"}
    ]
    
    nm = NewsManager(api_key="fake")
    nm._news_data = fake_news # Mock manuel
    
    # C1 : Bloqué si news HIGH ±15 min (ex: 12:35 UTC pour news à 12:30)
    try:
        now_utc = datetime(2026, 3, 19, 12, 35, tzinfo=timezone.utc if hasattr(datetime, "timezone") else None)
        # S'assurer de gérer l'import de timezone si nécessaire (fait dans news_manager)
        from datetime import timezone
        now_utc = datetime(2026, 3, 19, 12, 35, tzinfo=timezone.utc)
        
        res = nm.is_news_window("EURUSD", now_utc)
        results.check("C1 : News HIGH ±15 min (Bloqué)", res["blocked"] == True and "CPI" in res["reason"], f"Résultat: {res}")
    except Exception as e: results.check("C1", False, f"Exception: {e}")

    # C2 : Pass si news MEDIUM (même si ±5 min)
    try:
        now_utc = datetime(2026, 3, 19, 14, 0, tzinfo=timezone.utc)
        res = nm.is_news_window("EURUSD", now_utc)
        results.check("C2 : News MEDIUM (Pass)", res["blocked"] == False, f"Résultat: {res}")
    except Exception as e: results.check("C2", False, f"Exception: {e}")

    # C3 : Pass si news HIGH hors fenêtre (ex: 13:00 pour 12:30)
    try:
        now_utc = datetime(2026, 3, 19, 13, 0, tzinfo=timezone.utc)
        res = nm.is_news_window("EURUSD", now_utc)
        results.check("C3 : News HIGH hors fenêtre (Pass)", res["blocked"] == False, f"Résultat: {res}")
    except Exception as e: results.check("C3", False, f"Exception: {e}")

    # C4 : Pas de filtre pour Crypto (BTCUSD)
    try:
        now_utc = datetime(2026, 3, 19, 12, 30, tzinfo=timezone.utc)
        res = nm.is_news_window("BTCUSD", now_utc)
        results.check("C4 : Pas de filtre Crypto", res["blocked"] == False, f"Résultat: {res}")
    except Exception as e: results.check("C4", False, f"Exception: {e}")

if __name__ == "__main__":
    print("="*50)
    print("TESTS UNITAIRES — Trading Bot ICT")
    print("="*50)
    
    results = TestResults()
    test_agent1(results)
    test_agent2(results)
    test_news_manager(results)
    results.summary()