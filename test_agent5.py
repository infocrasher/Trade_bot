import pandas as pd
from agent_orchestrator import OrchestratorAgent

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

def test_fusion_decision(results: TestResults):
    agent = OrchestratorAgent()
    
    print("\n--- AGENT 5 : PARTIE A — Fusion & Décision ---\n")

    # Mock Data de base
    struct_ok = {"bias": "bullish"}
    time_ok = {"can_trade": True, "trade_quality": "high", "po3_phase": {"suggested_bias": "bullish"}}
    signal_ok = {"signal": "BUY", "confidence": 0.85, "entry_price": 1.0862, "stop_loss": 1.0798, "tp1": 1.1000, "tp2": 1.1054, "tp3": 1.1124, "rr_ratio": 2.1}
    macro_ok = {"can_trade": True, "macro_bias": "bullish", "confidence": 0.8}

    # Test E1 : EXECUTE_BUY — 4/4 alignés
    try:
        res = agent.calculate_decision(struct_ok, time_ok, signal_ok, macro_ok)
        results.check("E1 : Execute Buy 4/4", res['decision'] == "EXECUTE_BUY" and res['aligned_count'] == 4)
    except Exception as e:
        results.check("E1 : Execute Buy 4/4", False, f"Exception: {e}")

    # Test E2 : EXECUTE_SELL — 3/4 alignés
    try:
        s_bear = {"bias": "bearish"}
        t_neut = {"can_trade": True, "trade_quality": "medium", "po3_phase": {"suggested_bias": "neutral"}}
        sig_bear = {"signal": "SELL", "confidence": 0.8, "entry_price": 1.0900, "stop_loss": 1.1000, "tp1": 1.0800, "tp2": 1.0750, "tp3": 1.0600, "rr_ratio": 2.0}
        m_bear = {"can_trade": True, "macro_bias": "bearish", "confidence": 0.7}
        
        res = agent.calculate_decision(s_bear, t_neut, sig_bear, m_bear)
        # aligned: structure(bear), entry(bear), macro(bear) -> 3/4
        results.check("E2 : Execute Sell 3/4", res['decision'] == "EXECUTE_SELL" and res['aligned_count'] == 3)
    except Exception as e:
        results.check("E2 : Execute Sell 3/4", False, f"Exception: {e}")

    # Test E3 : NO_TRADE — seulement 2/4 alignés
    try:
        # structure bull, macro bear, entry buy (bull), time bear
        s_bull = {"bias": "bullish"}
        m_bear = {"can_trade": True, "macro_bias": "bearish", "confidence": 0.7}
        t_bear = {"can_trade": True, "trade_quality": "medium", "po3_phase": {"suggested_bias": "bearish"}}
        res = agent.calculate_decision(s_bull, t_bear, signal_ok, m_bear)
        results.check("E3 : No Trade Consensus", res['decision'] == "NO_TRADE")
    except Exception as e:
        results.check("E3 : No Trade Consensus", False, f"Exception: {e}")

    # Test E4 : NO_TRADE — signal NO_TRADE
    try:
        sig_no = {"signal": "NO_TRADE"}
        res = agent.calculate_decision(struct_ok, time_ok, sig_no, macro_ok)
        results.check("E4 : No Trade Entry Signal", res['decision'] == "NO_TRADE")
    except Exception as e:
        results.check("E4 : No Trade Entry Signal", False, f"Exception: {e}")

    # Test E5 : NO_TRADE — macro danger
    try:
        m_danger = {"can_trade": False, "detail": "News Danger"}
        res = agent.calculate_decision(struct_ok, time_ok, signal_ok, m_danger)
        results.check("E5 : No Trade Macro Danger", res['decision'] == "NO_TRADE")
    except Exception as e:
         results.check("E5 : No Trade Macro Danger", False, f"Exception: {e}")

    # Test E6 : NO_TRADE — hors killzone
    try:
        t_off = {"can_trade": False}
        res = agent.calculate_decision(struct_ok, t_off, signal_ok, macro_ok)
        results.check("E6 : No Trade Out of Killzone", res['decision'] == "NO_TRADE")
    except Exception as e:
        results.check("E6 : No Trade Out of Killzone", False, f"Exception: {e}")

    # Test E7 : Confidence score
    try:
        res = agent.calculate_decision(struct_ok, time_ok, signal_ok, macro_ok)
        # s(0.3) + t(0.15*1.0) + e(0.3*0.85) + m(0.25*0.8) = 0.3 + 0.15 + 0.255 + 0.2 = 0.905
        # confidence should be around 0.90
        results.check("E7 : Confidence Score accurate", 0.85 <= res['global_confidence'] <= 0.95)
    except Exception as e:
        results.check("E7 : Confidence Score accurate", False, f"Exception: {e}")

def test_safety_overrides(results: TestResults):
    agent = OrchestratorAgent(max_daily_trades=3, max_open_trades=3, max_daily_loss_pct=3.0)
    print("\n--- AGENT 5 : PARTIE B — Safety Overrides ---\n")
    
    decision_ok = {"decision": "EXECUTE_BUY", "entry_price": 1.0862, "stop_loss": 1.0798}
    
    # Test E8 : Block — max daily trades
    try:
        state = {"balance": 10000, "daily_trades": 3}
        res = agent.check_safety_overrides(dict(decision_ok), state)
        results.check("E8 : Block Max Daily Trades", res['decision'] == "NO_TRADE")
    except Exception as e:
        results.check("E8 : Block Max Daily Trades", False, f"Exception: {e}")

    # Test E9 : Block — daily loss limit
    try:
        state = {"balance": 10000, "daily_pnl": -350.0} # 3.5%
        res = agent.check_safety_overrides(dict(decision_ok), state)
        results.check("E9 : Block Daily Loss Limit", res['decision'] == "NO_TRADE")
    except Exception as e:
        results.check("E9 : Block Daily Loss Limit", False, f"Exception: {e}")

    # Test E10 : Block — drawdown protection
    try:
        state = {"balance": 10000, "equity": 9400.0} # Drawdown 6%
        res = agent.check_safety_overrides(dict(decision_ok), state)
        results.check("E10 : Block Drawdown Protection", res['decision'] == "NO_TRADE")
    except Exception as e:
        results.check("E10 : Block Drawdown Protection", False, f"Exception: {e}")

    # Test E11 : Pass — Safety OK
    try:
        state = {"balance": 10000, "equity": 10050, "daily_trades": 1, "open_trades": 1, "daily_pnl": 50.0}
        res = agent.check_safety_overrides(dict(decision_ok), state)
        results.check("E11 : Pass Safety Overrides", res['decision'] == "EXECUTE_BUY")
    except Exception as e:
        results.check("E11 : Pass Safety Overrides", False, f"Exception: {e}")

def test_position_sizing(results: TestResults):
    agent = OrchestratorAgent()
    print("\n--- AGENT 5 : PARTIE C — Position Sizing ---\n")

    # Test E12 : Lot size EURUSD (10k bal, 1% risk, 64 pips SL)
    try:
        # risk = 100$. Dist = 0.0064. Lots = 100 / (0.0064 * 100k) = 0.156 -> 0.15
        res = agent.calculate_position_size("EURUSD", 1.0862, 1.0798, 10000.0, 1.0)
        results.check("E12 : Lot Size EURUSD", res['lot_size'] == 0.15, f"Lot={res.get('lot_size')}")
    except Exception as e:
        results.check("E12 : Lot Size EURUSD", False, f"Exception: {e}")

    # Test E13 : Lot size USDJPY
    try:
        # 10k, 1% = 100$. SL dist = 1000 ticks. tick_val=0.67 -> Risk/Lot = 670$
        # Lot = 100 / 670 = 0.1492 -> floor to 0.14
        res = agent.calculate_position_size("USDJPY", 145.00, 144.00, 10000.0, 1.0)
        results.check("E13 : Lot Size USDJPY", res['lot_size'] == 0.14, f"Lot={res.get('lot_size')}")
    except Exception as e:
        results.check("E13 : Lot Size USDJPY", False, f"Exception: {e}")

    # Test E14 : Lot size XAUUSD
    try:
        # 10k, 1% = 100$. SL dist = 5$ (1.00 ticks = 0.01). 500 ticks. tick_val = 1.
        # Loss = 100 / (500 * 1) = 0.20 lots
        res = agent.calculate_position_size("XAUUSD", 2050.0, 2045.0, 10000.0, 1.0)
        results.check("E14 : Lot Size XAUUSD", res['lot_size'] == 0.20, f"Lot={res.get('lot_size')}")
    except Exception as e:
        results.check("E14 : Lot Size XAUUSD", False, f"Exception: {e}")

    # Test E15 : Lot Size Minimum
    try:
        # Bal 100, risk 1$ SL 100 pips. 1 / 10 = 0.1 lot raw. But min lot 0.01.
        res = agent.calculate_position_size("EURUSD", 1.1000, 1.0900, 100.0, 1.0)
        results.check("E15 : Lot Size Minimum", res['lot_size'] >= 0.01)
    except Exception as e:
        results.check("E15 : Lot Size Minimum", False, f"Exception: {e}")

def test_trade_management(results: TestResults):
    agent = OrchestratorAgent()
    print("\n--- AGENT 5 : PARTIE D — Trade Management ---\n")

    # Test E16 : Break-even trigger
    try:
        res = agent.check_break_even(entry_price=1.0862, current_price=1.0926, stop_loss=1.0798, direction="bullish", be_trigger_rr=1.0)
        results.check("E16 : Break-even Triggered", res['should_move_to_be'] == True)
    except Exception as e:
        results.check("E16 : Break-even Triggered", False, f"Exception: {e}")

    # Test E17 : Break-even NOT triggered
    try:
        res = agent.check_break_even(1.0862, 1.0880, 1.0798, "bullish")
        results.check("E17 : Break-even Not Yet", res['should_move_to_be'] == False)
    except Exception as e:
         results.check("E17 : Break-even Not Yet", False, f"Exception: {e}")

    # Test E18 : Partial Close TP1
    try:
        res = agent.check_partial_close(1.0862, 1.1005, 1.1000, 1.1050, 1.1100, "bullish", 0.20, [])
        results.check("E18 : Partial Close TP1Reached", res['should_close_partial'] and res['trigger'] == "tp1" and res['close_percent'] == 50)
    except Exception as e:
        results.check("E18 : Partial Close TP1", False, f"Exception: {e}")

    # Test E19 : Partial Close TP2 (TP1 already done)
    try:
        res = agent.check_partial_close(1.0862, 1.1060, 1.1000, 1.1050, 1.1100, "bullish", 0.10, ["tp1"])
        results.check("E19 : Partial Close TP2Reached", res['should_close_partial'] and res['trigger'] == "tp2")
    except Exception as e:
        results.check("E19 : Partial Close TP2", False, f"Exception: {e}")

    # Test E20 : Trailing stop (no backward move)
    try:
        # Buy. Current stop 1.0900. New swing low 1.0880. Price 1.0950.
        res = agent.calculate_trailing_stop("bullish", current_price=1.0950, current_stop=1.0900, entry_price=1.0862, 
                                            recent_swings=[{"type": "swing_low", "price": 1.0880}])
        results.check("E20 : Trailing No Backward", res['should_update'] == False)
    except Exception as e:
        results.check("E20 : Trailing No Backward", False, f"Exception: {e}")

if __name__ == "__main__":
    print("="*50)
    print("TESTS UNITAIRES — Agent 5 (Orchestrator)")
    print("="*50)
    
    results = TestResults()
    test_fusion_decision(results)
    test_safety_overrides(results)
    test_position_sizing(results)
    test_trade_management(results)
    results.summary()
