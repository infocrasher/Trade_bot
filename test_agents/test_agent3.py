import pandas as pd
from datetime import datetime
from agents.agent_entry import EntryAgent

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

def make_candle(time_str: str, o: float, h: float, l: float, c: float):
    return {
        "time": pd.Timestamp(time_str),
        "open": float(o), "high": float(h), "low": float(l), "close": float(c)
    }

def test_agent3(results: TestResults):
    agent = EntryAgent(symbol="EURUSD", pip_value=0.0001)
    
    print("\n--- AGENT 3 : Entry Precision ---\n")

    # Test C1 : OTE Zone Bullish
    try:
        ote = agent.calculate_ote_zone(swing_start=1.0800, swing_end=1.1000, direction="bullish")
        
        ok = round(ote['ote_top'], 5) == 1.09 and round(ote['ote_bottom'], 5) == 1.08428
        results.check("C1 : OTE Zone Bullish", ok, f"Valeurs: top={ote.get('ote_top')}, bot={ote.get('ote_bottom')}")
    except Exception as e:
        results.check("C1 : OTE Zone Bullish", False, f"Exception: {e}")

    # Test C2 : OTE Zone Bearish
    try:
        ote = agent.calculate_ote_zone(swing_start=1.1000, swing_end=1.0800, direction="bearish")
        ok = round(ote['ote_top'], 5) == 1.09572 and round(ote['ote_bottom'], 5) == 1.09
        results.check("C2 : OTE Zone Bearish", ok, f"Valeurs: top={ote.get('ote_top')}, bot={ote.get('ote_bottom')}")
    except Exception as e:
        results.check("C2 : OTE Zone Bearish", False, f"Exception: {e}")

    # Test C3 : Confluence OB + FVG + OTE
    try:
        ote = agent.calculate_ote_zone(1.0800, 1.1000, "bullish")
        
        obs = [{"type": "bullish_ob", "status": "unmitigated", "top": 1.0870, "bottom": 1.0850}]
        fvgs = [{"type": "bullish_fvg", "status": "open", "top": 1.0860, "bottom": 1.0840}]
        
        confluences = agent.find_confluence_zones(ote, obs, fvgs)
        ok = len(confluences) > 0 and confluences[0]['score'] == 3
        results.check("C3 : Confluence OB + FVG + OTE", ok, "Confluence triple manquée")
    except Exception as e:
        results.check("C3 : Confluence OB + FVG + OTE", False, f"Exception: {e}")

    # Test C4 : Pas de confluence — OB hors zone OTE
    try:
        ote = agent.calculate_ote_zone(1.0800, 1.1000, "bullish") # ote: 1.0876 -> 1.0843
        obs = [{"type": "bullish_ob", "status": "unmitigated", "top": 1.0950, "bottom": 1.0940}]
        
        confluences = agent.find_confluence_zones(ote, obs, [])
        results.check("C4 : OB hors zone OTE", len(confluences) == 0, "Fake confluence détectée")
    except Exception as e:
         results.check("C4 : OB hors zone OTE", False, f"Exception: {e}")

    # Test C5 : Stop Loss — méthode swing_start
    try:
        ote = agent.calculate_ote_zone(1.0800, 1.1000, "bullish")
        sl = agent.calculate_stop_loss("bullish", ote, entry_price=1.0860, buffer_pips=2.0)
        
        results.check("C5 : Stop Loss swing_start", sl['stop_loss'] == 1.0798, f"SL: {sl.get('stop_loss')}")
    except Exception as e:
        results.check("C5 : Stop Loss swing_start", False, f"Exception: {e}")

    # Test C6 : Take Profits — calculs Fibonacci
    try:
        ote = agent.calculate_ote_zone(1.0800, 1.1000, "bullish")
        sl = agent.calculate_stop_loss("bullish", ote, entry_price=1.0860, buffer_pips=2.0)
        
        tps = agent.calculate_take_profits("bullish", entry_price=1.0860, ote=ote)
        tps = agent._add_rr_to_tps(tps, 1.0860, sl['stop_loss'])
        
        ok = round(tps['tp1']['price'], 4) == 1.1000 and round(tps['tp2']['price'], 4) == 1.1054 and round(tps['tp3']['price'], 4) == 1.1124 and tps['tp1']['rr_ratio'] > 1.0
        results.check("C6 : Take Profits Fibonacci calculés", ok, f"TP1: {tps.get('tp1')}")
    except Exception as e:
         results.check("C6 : Take Profits Fibonacci", False, f"Exception: {e}")

    # Test C7 : Signal BUY complet
    try:
        report1 = {
             "bias": "bullish",
             "swings": [
                 {"type": "swing_low", "price": 1.0800, "index": 10},
                 {"type": "swing_high", "price": 1.1000, "index": 20}
             ],
             "order_blocks": [{"type": "bullish_ob", "status": "unmitigated", "top": 1.0870, "bottom": 1.0850}],
             "fvg": [{"type": "bullish_fvg", "status": "open", "top": 1.0860, "bottom": 1.0840}],
             "liquidity_sweeps": []
        }
        report2 = {"trade_quality": "medium"}
        
        # Le prix pénètre et clôture > mid (1.0855) => confirmation
        c1 = make_candle("2025-01-15 08:35", 1.0860, 1.0865, 1.0845, 1.0862)  
        df_entry = pd.DataFrame([c1])
        
        sig = agent.analyze(report1, report2, df_entry)
        results.check("C7 : Signal BUY complet", sig['signal'] == 'BUY' and sig['confidence'] > 0.60, f"Signal = {sig}")
    except Exception as e:
         results.check("C7 : Signal BUY complet", False, f"Exception: {e}")

    # Test C8 : Signal NO_TRADE — pas de biais
    try:
        report1 = {"bias": "neutral"}
        sig = agent.analyze(report1, {}, pd.DataFrame())
        results.check("C8 : NO_TRADE (bias neutral)", sig['signal'] == 'NO_TRADE', "Le trade n'a pas été ignoré")
    except Exception as e:
         results.check("C8 : NO_TRADE (bias neutral)", False, f"Exception: {e}")

    # Test C9 : Signal NO_TRADE — R:R insuffisant
    try:
         confluence = {"score": 3, "zone_top": 1.0870, "zone_bottom": 1.0850}
         sl = {"stop_loss": 1.0600, "entry_price": 1.0860, "risk_pips": 260}  # SL trop large
         tps = {"tp1": {"price": 1.0900}, "tp2": {"price": 1.0950}, "tp3": {"price": 1.1000}}
         tps = agent._add_rr_to_tps(tps, 1.0860, 1.0600)  # TP1 reward = 40, RR = 40/260 = ~0.15
         
         sig = agent.generate_trade_signal(confluence, sl, tps, {"confirmed": True}, "high")
         results.check("C9 : NO_TRADE (RR faible)", sig['signal'] == 'NO_TRADE', f"Erreur de filtre R:R {sig}")
    except Exception as e:
         results.check("C9 : NO_TRADE (RR faible)", False, f"Exception: {e}")

    # Test C10 : Signal NO_TRADE — hors killzone
    try:
        report1 = {
             "bias": "bullish",
             "swings": [
                 {"type": "swing_low", "price": 1.0800, "index": 10},
                 {"type": "swing_high", "price": 1.1000, "index": 20}
             ],
        }
        report2 = {"trade_quality": "no_trade"}
        sig = agent.analyze(report1, report2, pd.DataFrame())
        results.check("C10 : NO_TRADE (hors killzone)", sig['signal'] == "NO_TRADE", "Le killzone filter a foiré")
    except Exception as e:
        results.check("C10 : NO_TRADE (hors killzone)", False, f"Exception: {e}")

    # Test C11 : Pip value correcte pour JPY
    try:
        agent_jpy = EntryAgent(symbol="USDJPY", pip_value=0.01)
        pips = agent_jpy.price_to_pips(0.50)
        results.check("C11 : Pip value JPY", pips == 50.0, "Conversion pips JPY incorrecte")
    except Exception as e:
        results.check("C11 : Pip value JPY", False, f"Exception: {e}")

    # Test C12 : Confirmation candle trouvée
    try:
        cz = {"zone_top": 1.0870, "zone_bottom": 1.0850, "midpoint": 1.0860}
        df_entry = pd.DataFrame([
             make_candle("2025-01-15 08:30", 1.0880, 1.0890, 1.0845, 1.0855),  # Descend dans zone, clôture < mid
             make_candle("2025-01-15 08:35", 1.0855, 1.0870, 1.0850, 1.0865)   # Ouvre < mid, clôture > mid & haussière
        ])
        c = agent.find_entry_confirmation(df_entry, "bullish", cz)
        results.check("C12 : Confirmation Candle trouvée", c['confirmed'] and c['entry_price'] == 1.0865, "Confirmation manquée")
    except Exception as e:
         results.check("C12 : Confirmation Candle trouvée", False, f"Exception: {e}")

    # Test C13 : Confirmation candle non trouvée
    try:
        cz = {"zone_top": 1.0830, "zone_bottom": 1.0810, "midpoint": 1.0820}
        df_entry = pd.DataFrame([
             make_candle("2025-01-15 08:30", 1.0880, 1.0890, 1.0850, 1.0860),  # Loin de CZ (1.0830)
        ])
        c = agent.find_entry_confirmation(df_entry, "bullish", cz)
        results.check("C13 : Confirmation Candle non trouvée", not c['confirmed'], "Faux positif")
    except Exception as e:
         results.check("C13 : Confirmation Candle non trouvée", False, f"Exception: {e}")

if __name__ == "__main__":
    print("="*50)
    print("TESTS UNITAIRES — Agent 3 (Entry Precision)")
    print("="*50)
    
    results = TestResults()
    test_agent3(results)
    results.summary()
