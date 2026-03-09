import pandas as pd
from datetime import datetime

from agents.agent_structure import StructureAgent
from agents.agent_time_session import TimeSessionAgent
from agents.agent_entry import EntryAgent
from agents.agent_macro import MacroBiasAgent
from agents.agent_orchestrator import OrchestratorAgent

def make_candle(time_str: str, o: float, h: float, l: float, c: float) -> dict:
    body = abs(c - o)
    rng = h - l
    return {
        "time": pd.to_datetime(time_str),
        "open": o, "high": h, "low": l, "close": c,
        "tick_volume": 100,
        "body": body,
        "range": rng,
        "body_ratio": body / rng if rng > 0 else 0,
        "upper_wick": h - max(o, c),
        "lower_wick": min(o, c) - l
    }

def make_df(candles: list) -> pd.DataFrame:
    df = pd.DataFrame(candles)
    return df

class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.total = 0

    def assert_true(self, condition: bool, name: str):
        self.total += 1
        if condition:
            print(f"  ✅ PASS : {name}")
            self.passed += 1
        else:
            print(f"  ❌ FAIL : {name}")
            self.failed += 1

def run_tests():
    tr = TestResults()
    print("=" * 50)
    print("TESTS UNITAIRES — Phase 1 (Concepts Avancés)")
    print("=" * 50)

    # ---------------------------------------------------------
    # AGENT 1 : STRUCTURE & MULTI-TF
    # ---------------------------------------------------------
    print("\n--- AGENT 1 : Structure & Multi-TF ---")
    a1 = StructureAgent(symbol="EURUSD")

    swings = [
        {"type": "swing_high", "price": 1.1000, "index": 10},
        {"type": "swing_high", "price": 1.1002, "index": 20},
        {"type": "swing_high", "price": 1.0500, "index": 30},
    ]
    eqh = a1.detect_equal_levels(swings, tolerance_pips=5.0)
    tr.assert_true(len(eqh) == 1 and eqh[0]['type'] == 'EQH' and eqh[0]['count'] == 2, "P1 : Détection EQH (2 touches)")

    df_daily = make_df([
        make_candle("2024-01-01 00:00", 1.0, 1.1, 0.9, 1.05),
        make_candle("2024-01-02 00:00", 1.0, 1.15, 0.95, 1.05), # yesterday
        make_candle("2024-01-03 00:00", 1.0, 1.05, 0.98, 1.00), # today
    ])
    kl = a1.detect_key_levels(df_daily=df_daily)
    tr.assert_true(kl.get("PDH") == 1.15 and kl.get("PDL") == 0.95, "P2 : PDH / PDL corrects")

    df_d1 = make_df([make_candle("2024-01-01 00:00", 1.0, 1.1, 0.9, 1.05) for _ in range(50)])
    df_h1 = make_df([make_candle("2024-01-01 00:00", 1.0, 1.1, 0.9, 1.05) for _ in range(50)])
    res_mtf = a1.analyze_multi_tf({"D1": df_d1, "H1": df_h1})
    tr.assert_true("htf_alignment" in res_mtf, "P3 : Analyze Multi-TF renvoie htf_alignment")

    # ---------------------------------------------------------
    # AGENT 2 : MACROS & TIME
    # ---------------------------------------------------------
    print("\n--- AGENT 2 : Time & Session ---")
    a2 = TimeSessionAgent(broker_utc_offset=0)

    ny_11am = datetime(2024, 1, 2, 11, 0)
    kz = a2.get_active_killzone(ny_11am)
    tr.assert_true(kz is not None and kz['id'] == 'london_close', "P4 : London Close Killzone")

    ny_10am = datetime(2024, 1, 2, 10, 0)
    macro = a2.get_active_macro(ny_10am)
    tr.assert_true(macro is not None and macro['id'] == 'ny_am_2', "P5 : Détection Macro algorithmique")

    df_m5 = make_df([
        make_candle("2024-01-02 04:55", 1.0500, 1.0510, 1.0490, 1.0505),
        make_candle("2024-01-02 05:00", 1.0505, 1.0520, 1.0500, 1.0515), 
        make_candle("2024-01-02 13:00", 1.0515, 1.0530, 1.0510, 1.0490), 
    ])
    mo = a2.calculate_midnight_open(df_m5)
    tr.assert_true(mo['midnight_open'] == 1.0505 and mo['current_vs_midnight'] == 'discount', "P6 : Midnight Open & Discount")

    ny_mon_8am = datetime(2024, 1, 1, 8, 0)
    df_mon = a2.get_day_filter(ny_mon_8am)
    tr.assert_true(df_mon['quality'] == 'seek_destroy', "P7 : Profil Seek & Destroy (Lundi avant 10h)")

    ny_mon_11am = datetime(2024, 1, 1, 11, 0)
    df_mon_setup = a2.get_day_filter(ny_mon_11am)
    tr.assert_true(df_mon_setup['quality'] == 'setup', "P8 : Profil Setup (Lundi après 10h)")

    # ---------------------------------------------------------
    # AGENT 3 : PREMIUM/DISCOUNT & DOL
    # ---------------------------------------------------------
    print("\n--- AGENT 3 : Entry Precision ---")
    a3 = EntryAgent(symbol="EURUSD")

    pd_buy = a3.check_premium_discount(1.0200, swing_high=1.0600, swing_low=1.0000, direction="bullish")
    tr.assert_true(pd_buy['is_valid'] == True and pd_buy['zone'] == 'discount', "P9 : Buy in discount is valid")

    pd_buy_inv = a3.check_premium_discount(1.0400, swing_high=1.0600, swing_low=1.0000, direction="bullish")
    tr.assert_true(pd_buy_inv['is_valid'] == False and pd_buy_inv['zone'] == 'premium', "P10 : Buy in premium is invalid")

    kl_dol = {"PDH": 1.0600, "PMH": 1.0700}
    eq_dol = [{"type": "EQH", "level": 1.0550, "strength": "strong"}]
    fvgs = [{"type": "bearish_fvg", "top": 1.0800, "bottom": 1.0750}]
    
    dol = a3.find_draw_on_liquidity("bullish", 1.0200, kl_dol, eq_dol, fvgs)
    tr.assert_true(len(dol) == 4 and dol[0]['type'] == 'EQH' and dol[-1]['type'] == 'HTF_FVG', "P11 : Tri correct Draw on Liquidity cibles")

    sd = a3.calculate_std_dev_targets(1.0000, 0.9900, "bearish")
    tr.assert_true(sd['sd_2']['price'] == 0.9700, "P12 : Projections Standard Deviation correctes")

    # ---------------------------------------------------------
    # AGENT 4 : MACRO EXTENDED
    # ---------------------------------------------------------
    print("\n--- AGENT 4 : Macro Extended ---")
    a4 = MacroBiasAgent(target_pair="EURUSD")

    df_ipda = make_df([make_candle("2024-01-01 00:00", 1.0, 1.1 + (i*0.001), 0.9, 1.05) for i in range(100)])
    ipda = a4.analyze_ipda_ranges(df_ipda)
    tr.assert_true("range_20" in ipda and ipda["range_60"]["days"] == 60, "P13 : IPDA ranges 20/40/60")

    q1 = a4.get_quarterly_context("2024-02-15 10:00")
    tr.assert_true(q1['quarter'] == 'Q1' and q1['seasonal_bias_usd'] == 'bullish', "P14 : Q1 saisonnalité USD Bullish")

    q3 = a4.get_quarterly_context("2024-08-15 10:00")
    tr.assert_true(q3['quarter'] == 'Q3' and q3['seasonal_bias_usd'] == 'bearish', "P15 : Q3 saisonnalité USD Bearish")

    # ---------------------------------------------------------
    # AGENT 5 : ORCHESTRATOR UPDATES
    # ---------------------------------------------------------
    print("\n--- AGENT 5 : Orchestrator (Phase 1) ---")
    a5 = OrchestratorAgent()

    s_rep = {"bias": "bullish", "htf_alignment": "bullish", "htf_confidence_modifier": 1.0}
    t_rep = {"can_trade": True, "trade_quality": "high", "active_macro": None}
    ts_sig = {"signal": "BUY", "entry_price": 1.0, "stop_loss": 0.9, "tp1": 1.1, "tp2": 1.2, "tp3": 1.3, "rr_ratio": 2.0, "premium_discount": {"is_valid": True}}
    m_rep = {"can_trade": True, "macro_bias": "bullish", "confidence": 0.8}

    dec1 = a5.calculate_decision(s_rep, t_rep, ts_sig, m_rep)
    tr.assert_true(dec1['decision'] == "EXECUTE_BUY", "P16 : Décision de base valide")

    ts_sig_inv = ts_sig.copy()
    ts_sig_inv['premium_discount'] = {"is_valid": False, "detail": "Test invalid"}
    dec2 = a5.calculate_decision(s_rep, t_rep, ts_sig_inv, m_rep)
    tr.assert_true(dec2['decision'] == "NO_TRADE" and "Wrong zone" in dec2['reason'], "P17 : Blocage par Premium/Discount")

    s_rep_conf = {"bias": "bullish", "htf_alignment": "conflicting", "htf_confidence_modifier": 0.0}
    dec3 = a5.calculate_decision(s_rep_conf, t_rep, ts_sig, m_rep)
    tr.assert_true(dec3['decision'] == "NO_TRADE" and "HTF conflict" in dec3['reason'], "P18 : Blocage par HTF Conflicting")

    t_rep_macro = {"can_trade": True, "trade_quality": "high", "active_macro": {"id": "ny_am_1"}}
    dec4 = a5.calculate_decision(s_rep, t_rep, ts_sig, m_rep)
    conf_base = dec4['global_confidence']
    
    dec5 = a5.calculate_decision(s_rep, t_rep_macro, ts_sig, m_rep)
    tr.assert_true(dec5['global_confidence'] > conf_base or dec5['global_confidence'] == 1.0, "P19 : Bonus de confiance avec Macro active")

    # ---------------------------------------------------------
    # NOUVEAUX TESTS DEMANDES (P20 - P30)
    # ---------------------------------------------------------

    # --- Agent 1 : Nouveaux Tests ---
    
    # P20 : detect_mss — BOS + Displacement + FVG = MSS confirmé
    try:
        df_mss = make_df([
            make_candle("2024-01-01 10:00", 1.0000, 1.0100, 0.9900, 1.0050),
            make_candle("2024-01-01 10:15", 1.0050, 1.0400, 1.0000, 1.0350), # Displacement (index 1)
            make_candle("2024-01-01 10:30", 1.0350, 1.0500, 1.0200, 1.0450)
        ])
        swings_mss = [{"type": "swing_high", "price": 1.0200, "index": 0}]
        displacements_mss = [{"index": 1, "type": "bullish"}]
        fvgs_mss = [{"index": 2, "type": "bullish_fvg", "displacement_index": 1, "top": 1.0200, "bottom": 1.0100}]
        bos_choch_mss = [{"index": 1, "type": "bullish_bos", "broken_level": 1.0200, "broken_index": 0}]
        
        mss = a1.detect_mss(df_mss, swings_mss, displacements_mss, fvgs_mss, bos_choch_mss)
        tr.assert_true(len(mss) == 1 and mss[0]['type'] == 'bullish_mss', "P20 : detect_mss — BOS + Displacement + FVG = MSS confirmé")
    except Exception as e:
        tr.assert_true(False, f"P20 : Erreur - {str(e)}")

    # P21 : detect_mss — BOS sans Displacement → pas de MSS
    try:
        mss_empty = a1.detect_mss(df_mss, swings_mss, [], fvgs_mss, bos_choch_mss)
        tr.assert_true(len(mss_empty) == 0, "P21 : detect_mss — BOS sans Displacement -> pas de MSS")
    except Exception as e:
        tr.assert_true(False, f"P21 : Erreur - {str(e)}")

    # P22 : detect_equal_levels — swings trop éloignés → aucun EQH
    try:
        swings_far = [
            {"type": "swing_high", "price": 1.1000, "index": 10},
            {"type": "swing_high", "price": 1.1100, "index": 20},
            {"type": "swing_high", "price": 1.1200, "index": 30},
        ]
        eqh_empty = a1.detect_equal_levels(swings_far, tolerance_pips=3.0)
        tr.assert_true(len(eqh_empty) == 0, "P22 : detect_equal_levels — swings trop éloignés -> aucun EQH")
    except Exception as e:
        tr.assert_true(False, f"P22 : Erreur - {str(e)}")

    # P23 : detect_equal_levels — 3 swing lows au même niveau → EQL strong
    try:
        swings_close = [
            {"type": "swing_low", "price": 1.0800, "index": 10},
            {"type": "swing_low", "price": 1.0801, "index": 20},
            {"type": "swing_low", "price": 1.0802, "index": 30},
        ]
        eql_strong = a1.detect_equal_levels(swings_close, tolerance_pips=3.0)
        tr.assert_true(len(eql_strong) == 1 and eql_strong[0]['type'] == 'EQL' and eql_strong[0]['count'] == 3 and eql_strong[0]['strength'] == 'strong', "P23 : detect_equal_levels — 3 swing lows -> EQL strong")
    except Exception as e:
        tr.assert_true(False, f"P23 : Erreur - {str(e)}")

    # P24 : detect_key_levels — PWH/PWL avec df_weekly
    try:
        df_weekly = make_df([
            make_candle("2024-01-01 00:00", 1.0, 1.1, 0.9, 1.05),
            make_candle("2024-01-08 00:00", 1.0, 1.2, 0.8, 1.10),
            make_candle("2024-01-15 00:00", 1.0, 1.05, 0.98, 1.00),
        ])
        kl_weekly = a1.detect_key_levels(df_daily=None, df_weekly=df_weekly, df_monthly=None)
        tr.assert_true(kl_weekly.get("PWH") == 1.2 and kl_weekly.get("PWL") == 0.8, "P24 : detect_key_levels — PWH/PWL avec df_weekly")
    except Exception as e:
        tr.assert_true(False, f"P24 : Erreur - {str(e)}")

    # P25 : detect_key_levels — pas de df_monthly → PMH/PML absents
    try:
        kl_no_monthly = a1.detect_key_levels(df_daily=df_daily, df_monthly=None)
        tr.assert_true("PMH" not in kl_no_monthly and "PML" not in kl_no_monthly, "P25 : detect_key_levels — pas de df_monthly -> PMH/PML absents")
    except Exception as e:
        tr.assert_true(False, f"P25 : Erreur - {str(e)}")

    # --- Agent 2 : Nouveaux Tests ---
    
    # P26 : get_active_macro — hors macro (08:30 NY)
    try:
        ny_0830am = datetime(2024, 1, 2, 8, 30)
        macro_none = a2.get_active_macro(ny_0830am)
        tr.assert_true(macro_none is None, "P26 : get_active_macro — hors macro (08:30 NY)")
    except Exception as e:
        tr.assert_true(False, f"P26 : Erreur - {str(e)}")

    # P27 : get_active_macro — Midnight Open Macro (23:55 NY)
    try:
        ny_2355 = datetime(2024, 1, 1, 23, 55)
        macro_midnight = a2.get_active_macro(ny_2355)
        tr.assert_true(macro_midnight is not None and macro_midnight['id'] == 'midnight_open', "P27 : get_active_macro — Midnight Open Macro (23:55 NY)")
    except Exception as e:
        tr.assert_true(False, f"P27 : Erreur - {str(e)}")

    # --- Agent 3 : Nouveaux Tests ---
    
    # P28 : find_draw_on_liquidity — bearish, PDL et EQL en dessous
    try:
        kl_bearish = {"PDL": 1.0400}
        eq_bearish = [{"type": "EQL", "level": 1.0350, "strength": "moderate"}]
        dol_bearish = a3.find_draw_on_liquidity("bearish", 1.0500, kl_bearish, eq_bearish, [])
        tr.assert_true(len(dol_bearish) == 2 and dol_bearish[0]['type'] == 'PDL' and dol_bearish[1]['type'] == 'EQL', "P28 : find_draw_on_liquidity — bearish, PDL et EQL en dessous")
    except Exception as e:
        tr.assert_true(False, f"P28 : Erreur - {str(e)}")

    # P29 : find_draw_on_liquidity — rien devant → liste vide
    try:
        kl_bullish_empty = {"PDH": 1.0900}
        dol_empty = a3.find_draw_on_liquidity("bullish", 1.1000, kl_bullish_empty, [], [])
        tr.assert_true(len(dol_empty) == 0, "P29 : find_draw_on_liquidity — rien devant -> liste vide")
    except Exception as e:
        tr.assert_true(False, f"P29 : Erreur - {str(e)}")

    # --- Agent 5 : Nouveaux Tests ---
    
    # P30 : Pipeline complet — tout aligné → EXECUTE avec confiance élevée
    try:
        s_rep_full = {
            "bias": "bullish", 
            "htf_alignment": "bullish", 
            "htf_confidence_modifier": 1.0
        }
        t_rep_full = {
            "can_trade": True, 
            "trade_quality": "high", 
            "active_macro": {"id": "ny_am_1"}, 
            "po3_phase": {"suggested_bias": "bullish"}
        }
        ts_sig_full = {
            "signal": "BUY", 
            "confidence": 0.85, 
            "rr_ratio": 3.0, 
            "premium_discount": {"is_valid": True}, 
            "entry_price": 1.1000, 
            "stop_loss": 1.0950, 
            "tp1": 1.1100, 
            "tp2": 1.1150, 
            "tp3": 1.1200
        }
        m_rep_full = {
            "can_trade": True, 
            "macro_bias": "bullish", 
            "confidence": 0.80
        }
        
        dec_full = a5.calculate_decision(s_rep_full, t_rep_full, ts_sig_full, m_rep_full)
        tr.assert_true(dec_full['decision'] == "EXECUTE_BUY" and dec_full['aligned_count'] == 4 and dec_full['global_confidence'] >= 0.85, "P30 : Pipeline complet — tout aligné -> EXECUTE avec confiance élevée")
    except Exception as e:
        tr.assert_true(False, f"P30 : Erreur - {str(e)}")

    print("\n" + "="*50)
    print(f"RÉSULTATS : {tr.passed}/{tr.total} tests passés")
    print("="*50)

if __name__ == "__main__":
    run_tests()
