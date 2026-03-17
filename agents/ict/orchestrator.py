import math

try:
    from agents.ict.liquidity_tracker import LiquidityTracker
    _LIQUIDITY_TRACKER_AVAILABLE = True
except ImportError:
    _LIQUIDITY_TRACKER_AVAILABLE = False

try:
    from agents.ict.enigma import score_enigma, snap_to_enigma
    _ENIGMA_AVAILABLE = True
except ImportError:
    _ENIGMA_AVAILABLE = False
try:
    from agents.ict.sod_detector import detect_sod, get_sod_sizing_factor
    _SOD_DETECTOR_AVAILABLE = True
except ImportError:
    _SOD_DETECTOR_AVAILABLE = False

# Agent Weights for Fusion
AGENT_WEIGHTS = {
    "structure": 0.30,    # Agent 1 : Price action (BOS/CHOCH/FVG/OB)
    "time": 0.15,         # Agent 2 : Killzones & Session
    "entry": 0.30,        # Agent 3 : OTE & Entry confirmation
    "macro": 0.25,        # Agent 4 : COT & DXY context
}

# Propriétés des symboles pour le calcul des lots
SYMBOL_PROPERTIES = {
    "EURUSD": {"contract_size": 100000, "tick_size": 0.00001, "tick_value": 1.0, "min_lot": 0.01, "max_lot": 100.0, "lot_step": 0.01},
    "USDJPY": {"contract_size": 100000, "tick_size": 0.001, "tick_value": 0.67, "min_lot": 0.01, "max_lot": 100.0, "lot_step": 0.01},
    "GBPUSD": {"contract_size": 100000, "tick_size": 0.00001, "tick_value": 1.0, "min_lot": 0.01, "max_lot": 100.0, "lot_step": 0.01},
    "XAUUSD": {"contract_size": 100, "tick_size": 0.01, "tick_value": 1.0, "min_lot": 0.01, "max_lot": 100.0, "lot_step": 0.01},
    "US100":  {"contract_size": 1, "tick_size": 0.1, "tick_value": 0.10, "min_lot": 0.1, "max_lot": 500.0, "lot_step": 0.1},
    "US500":  {"contract_size": 1, "tick_size": 0.1, "tick_value": 0.10, "min_lot": 0.1, "max_lot": 500.0, "lot_step": 0.1},
    "AUDUSD": {"contract_size": 100000, "tick_size": 0.00001, "tick_value": 1.0, "min_lot": 0.01, "max_lot": 100.0, "lot_step": 0.01},
    "USDCAD": {"contract_size": 100000, "tick_size": 0.00001, "tick_value": 0.74, "min_lot": 0.01, "max_lot": 100.0, "lot_step": 0.01},
    "USDCHF": {"contract_size": 100000, "tick_size": 0.00001, "tick_value": 1.12, "min_lot": 0.01, "max_lot": 100.0, "lot_step": 0.01},
    "NZDUSD": {"contract_size": 100000, "tick_size": 0.00001, "tick_value": 1.0, "min_lot": 0.01, "max_lot": 100.0, "lot_step": 0.01},
    "EURJPY": {"contract_size": 100000, "tick_size": 0.001, "tick_value": 0.67, "min_lot": 0.01, "max_lot": 100.0, "lot_step": 0.01},
    "GBPJPY": {"contract_size": 100000, "tick_size": 0.001, "tick_value": 0.67, "min_lot": 0.01, "max_lot": 100.0, "lot_step": 0.01},
    "EURGBP": {"contract_size": 100000, "tick_size": 0.00001, "tick_value": 1.27, "min_lot": 0.01, "max_lot": 100.0, "lot_step": 0.01},
    "USOIL":  {"contract_size": 1000, "tick_size": 0.01, "tick_value": 10.0, "min_lot": 0.01, "max_lot": 500.0, "lot_step": 0.01},
}

class OrchestratorAgent:
    def __init__(self, account_balance: float = 10000.0, risk_percent: float = 1.0,
                 max_daily_trades: int = 3, max_open_trades: int = 3,
                 max_daily_loss_pct: float = 3.0):
        self.account_balance = account_balance
        self.risk_percent = risk_percent
        self.max_daily_trades = max_daily_trades
        self.max_open_trades = max_open_trades
        self.max_daily_loss_pct = max_daily_loss_pct

    def calculate_decision(self, structure_report: dict, time_report: dict,
                           trade_signal: dict, macro_report: dict,
                           liquidity_report: dict = None, df_m5=None) -> dict:
        """
        Fusionne les 4 rapports et prend la décision finale via un vote pondéré.
        """
        reasons = []
        warnings = []
        
        # 1. ÉLIMINATIONS DIRECTES
        if trade_signal.get('signal') == "NO_TRADE":
            return {"decision": "NO_TRADE", "reason": "Agent d'entrée (A3) ne voit pas d'opportunité."}
            
        pd_check = trade_signal.get('premium_discount', {})
        if pd_check.get('is_valid') == False:
            return {"decision": "NO_TRADE", "reason": f"Wrong zone: {pd_check.get('detail')}"}
        
        if not time_report.get('can_trade', False):
            return {"decision": "NO_TRADE", "reason": "Agent Temporel (A2) bloque le trade (Killzone/Jour)."}
            
        po3 = time_report.get("po3_phase", {})
        po3_phase = po3.get("phase", "transition")
        if po3_phase == "accumulation":
            return {
                "decision": "NO_TRADE",
                "reason": f"PO3 Phase ACCUMULATION — Asian range en formation, "
                          f"attente manipulation/distribution. "
                          f"({po3.get('description', '')})"
            }

        if not macro_report.get('can_trade', True):
            return {"decision": "NO_TRADE", "reason": f"Agent Macro (A4) bloque : {macro_report.get('detail')}"}
            
        if macro_report.get('macro_bias') == "no_trade":
            return {"decision": "NO_TRADE", "reason": "Biais Macro est trop instable (no_trade)."}
            
        htf_alignment = structure_report.get('htf_alignment', 'unknown')
        if htf_alignment == "conflicting":
            return {"decision": "NO_TRADE", "reason": "Biais HTF contradictoire (Rule 11.1.10 - Daily Bias incertain)"}

        # ── SOD — State of Delivery (5 états KB4) ────────────────────────────────────
        if _SOD_DETECTOR_AVAILABLE:
            po3_dict = time_report.get("po3_phase", {})
            po3_ph   = po3_dict.get("phase")
            # Tolérance backward-compatibility pour anciens tests / logs
            if not po3_ph:
                po3_ph = "distribution"
                
            amd_ph  = time_report.get("day_filter", {}).get("amd_phase", "unknown")
            df_h1   = trade_signal.get("_df_h1")

            analysis_tf = trade_signal.get("entry_tf", "M5")
            sod = detect_sod(po3_ph, amd_ph, df_h1, analysis_tf=analysis_tf)

            if not sod["can_trade"]:
                return {
                    "decision": "NO_TRADE",
                    "reason":   f"SOD={sod['state']} — {sod['reason']}"
                }

            # Stocker pour le sizing adaptatif
            time_report["_sod"] = sod
            warnings.append(f"SOD={sod['state']} (sizing_factor={sod['sizing_factor']})")
        # ─────────────────────────────────────────────────────────────────────────────

        # ── EARLY LIQUIDITY TRACKER (pour KS8 et la suite) ───────────────────────────
        if liquidity_report is None and _LIQUIDITY_TRACKER_AVAILABLE:
            try:
                symbol = trade_signal.get("symbol") or structure_report.get("symbol", "EURUSD")
                import pandas as pd
                df_h1 = trade_signal.get("_df_h1") or structure_report.get("_df_h1") or pd.DataFrame()
                tf_data = structure_report.get("H1", structure_report)
                liq_tracker = LiquidityTracker(symbol=symbol)
                liquidity_report = liq_tracker.analyze(df_h1, tf_data, tf="H1")
            except Exception as _liq_err:
                import logging as _log
                _log.getLogger(__name__).warning(f"[OrchestratorAgent] LiquidityTracker erreur : {_liq_err}")
                liquidity_report = None
        # ─────────────────────────────────────────────────────────────────────────────

        # ── KS4 — Spread excessif (> 3 pips) ─────────────────────────────────────────
        # Règle KB4 : spread > 3 pips = coût de transaction trop élevé = NO_TRADE
        # Le spread est fourni par dashboard.py dans trade_signal['current_spread_pips']
        # Si non disponible, le gate est inactif (fail-safe silencieux)
        ks4_spread = trade_signal.get("current_spread_pips")
        if ks4_spread is not None:
            ks4_limit = 3.0
            if ks4_spread > ks4_limit:
                return {
                    "decision": "NO_TRADE",
                    "reason":   f"KS4 — Spread trop élevé : {ks4_spread:.1f} pips "
                                f"(max={ks4_limit} pips). Coût prohibitif."
                }
            else:
                warnings.append(f"KS4 OK — spread={ks4_spread:.1f} pips")
        # ─────────────────────────────────────────────────────────────────────────────

        # ── KS8 — CBDR Explosive + Macros 1/2/8 bloquées ────────────────────────────
        # Règle KB4 : si CBDR en mode explosif, les 3 macros NY morning sont interdites.
        # Macro 1 = ny_open (07:50-08:10)
        # Macro 2 = ny_am_1 (08:50-09:10)
        # Macro 8 = ny_am_2 (09:50-10:10)
        # Raison : mouvement déjà amorcé avant les macros → piège institutionnel probable.
        KS8_BLOCKED_MACROS = {"ny_open", "ny_am_1", "ny_am_2"}
        cbdr_explosive = False
        if liquidity_report:
            cbdr_explosive = liquidity_report.get("cbdr", {}).get("cbdr_explosive", False)

        if cbdr_explosive:
            active_macro = time_report.get("active_macro") or {}
            macro_id     = active_macro.get("id", "")
            if macro_id in KS8_BLOCKED_MACROS:
                return {
                    "decision": "NO_TRADE",
                    "reason":   f"KS8 — CBDR Explosif + Macro bloquée "
                                f"({macro_id} / {active_macro.get('name', '')}). "
                                f"Mouvement pré-macro déjà amorcé."
                }
            else:
                warnings.append(f"KS8 — CBDR Explosif détecté (macro={macro_id or 'hors-macro'} non bloquée)")
        # ─────────────────────────────────────────────────────────────────────────────

        # 2. ALIGNEMENT DIRECTIONNEL
        s_bias = structure_report.get('bias', 'neutral')
        t_bias = time_report.get('po3_phase', {}).get('suggested_bias', 'neutral')
        e_direction = "bullish" if trade_signal['signal'] == "BUY" else "bearish"
        m_bias = macro_report.get('macro_bias', 'neutral')
        
        alignment = {
            "structure": s_bias,
            "time": t_bias,
            "entry": e_direction,
            "macro": m_bias
        }
        
        # On définit la direction principale par le signal d'entrée (Agent 3)
        final_direction = e_direction
        
        # Comptage des votes alignés avec final_direction
        aligned_count = sum(1 for v in alignment.values() if v == final_direction)
        
        if aligned_count < 3:
            return {
                "decision": "NO_TRADE", 
                "reason": f"Manque de consensus : seul {aligned_count}/4 agents sont alignés sur {final_direction} (minimum 3 requis)."
            }
            
        reasons.append(f"{aligned_count}/4 agents alignés {final_direction}")

        # 3. SCORE DE CONFIANCE GLOBAL
        # Poids : s=0.30, t=0.15, e=0.30, m=0.25
        t_quality = time_report.get('trade_quality', 'low')
        t_q_score_map = {"high": 1.0, "medium": 0.70, "low": 0.30, "no_trade": 0.0}
        t_q_score = t_q_score_map.get(t_quality, 0.0)
        
        conf_score = (
            AGENT_WEIGHTS['structure'] * (1.0 if s_bias == final_direction else 0.0) +
            AGENT_WEIGHTS['time'] * t_q_score +
            AGENT_WEIGHTS['entry'] * trade_signal.get('confidence', 0.0) +
            AGENT_WEIGHTS['macro'] * macro_report.get('confidence', 0.0)
        )
        
        # NEW V2 - HTF Modifier
        htf_mod = structure_report.get('htf_confidence_modifier', 1.0)
        conf_score *= htf_mod

        # NEW V2 - Macro active bonus
        if time_report.get('active_macro'):
            conf_score += 0.10
            reasons.append("Algorithmic Macro active (+10% conf)")

        # ── LIQUIDITY TRACKER PENALTIES ───────────────────────────────
        # Analyse ERL/IRL, DOL, Anti-Inducement, LRLR/HRLR, CBDR
        # Pénalité appliquée sur conf_score (en proportion : -15pts = -0.15)
        if liquidity_report:
            liq_penalty      = liquidity_report.get("score_penalty", 0)
            conf_score       = max(0.0, conf_score + liq_penalty / 100.0)
            if liq_penalty < 0:
                warnings.append(
                    f"Liquidité: pénalité {liq_penalty}pts "
                    f"({liquidity_report.get('anti_inducement', {}).get('message', '')})"
                )
        elif _LIQUIDITY_TRACKER_AVAILABLE:
            # Pénalité conservatrice si LiquidityTracker indisponible
            # On ne peut pas vérifier l'Anti-Inducement → on pénalise
            conf_score = max(0.0, conf_score - 0.15)
            warnings.append(
                "⚠️ LiquidityTracker indisponible — pénalité conservatrice "
                "-15% appliquée (Anti-Inducement non vérifiable)."
            )
        # ─────────────────────────────────────────────────────────────

        # ── HRLR Gate ─────────────────────────────────────────────
        lrlr_status = liquidity_report.get("lrlr_hrlr", {}).get("status", "UNKNOWN") \
                      if liquidity_report else "UNKNOWN"
        if lrlr_status == "HRLR":
            if conf_score < 0.70:
                return {
                    "decision": "NO_TRADE",
                    "reason": f"HRLR détecté — 2+ FVG bloquants entre prix et DOL. "
                              f"Confiance insuffisante ({conf_score:.0%}) pour forcer le passage."
                }
            else:
                warnings.append(
                    f"⚠️ HRLR — chemin vers DOL obstrué par FVG. "
                    f"Confiance élevée ({conf_score:.0%}) — trade maintenu avec prudence."
                )
        # ─────────────────────────────────────────────────────────

        # ── GATE SL MINIMUM — distance absolue ───────────────────────────────────────
        # Un SL < 3 pips = aberration (le spread seul va le déclencher).
        _entry = trade_signal.get('entry_price', 0)
        _sl    = trade_signal.get('stop_loss', 0)
        _sym   = (trade_signal.get('symbol') or structure_report.get('symbol') or '').upper()
        _is_jpy = any(_sym.endswith(s) for s in ('JPY',)) or _sym in ('XAUUSD', 'BTCUSD', 'ETHUSD')
        _pip   = 0.01 if _is_jpy else 0.0001
        _sl_pips = abs(_entry - _sl) / _pip if _pip > 0 else 0

        MIN_SL_PIPS = 3.0
        if 0 < _sl_pips < MIN_SL_PIPS:
            return {
                "decision": "NO_TRADE",
                "reason":   f"SL trop serré : {_sl_pips:.1f} pips (min={MIN_SL_PIPS} pips). "
                            f"Le spread seul déclencherait le SL."
            }
        # ─────────────────────────────────────────────────────────────────────────────

        # 4. VALIDATION R:R FINALE
        rr = trade_signal.get('rr_ratio', 0.0)
        if rr < 1.2:
             return {"decision": "NO_TRADE", "reason": f"R:R trop faible ({rr} < 1.2)."}
        
        if rr >= 3.0:
            conf_score += 0.05
            reasons.append("Bonus R:R élevé (>= 3.0)")

        if conf_score < 0.25:
            return {"decision": "NO_TRADE", "reason": f"Confiance globale trop faible ({conf_score:.2f} < 0.25)."}

        # Détails des raisons
        reasons.append(f"Structure: {s_bias}")
        reasons.append(f"Time: {t_quality} ({time_report.get('active_killzone', {}).get('name', 'N/A')})")
        reasons.append(f"Entry: Confiance {trade_signal.get('confidence')} - OTE zone")
        reasons.append(f"Macro: {m_bias} (Confiance {macro_report.get('confidence')})")

        # Warnings
        for k, v in alignment.items():
            if v != final_direction and v != "neutral":
                warnings.append(f"Divergence {k}: signal {v} vs trade {final_direction}")

        # ── ENIGMA — Niveaux Algorithmiques ──────────────────────────────────────────
        if _ENIGMA_AVAILABLE:
            pip_value = 0.01 if any(x in trade_signal.get('symbol','') 
                                    for x in ['JPY','XAU','GOLD']) else 0.0001
            enigma = score_enigma(
                entry_price = trade_signal['entry_price'],
                tp          = trade_signal['tp1'],
                direction   = final_direction,
                pip_value   = pip_value
            )
            # Appliquer le delta sur conf_score (converti : 10pts = +0.10)
            conf_score = max(0.0, min(1.0, conf_score + enigma['score_delta'] / 100.0))
            
            # Snapper le TP1 sur le niveau ENIGMA si applicable
            if enigma['tp_snapped']:
                trade_signal['tp1'] = enigma['tp_adjusted']
                reasons.append(f"ENIGMA TP1 snappé → {enigma['tp_adjusted']}")
            
            warnings.extend(enigma['enigma_details'])
            
        # ── P-B1 — First Presented FVG Bonus ────────────────────────────────────────
        # Règle : le 1er FVG post-09h29 NY dans la direction du biais HTF = +5pts (+0.05)
        try:
            from agents.ict.structure import is_first_presented_fvg
            _fvg_list = structure_report.get("fvg", [])
            _current_fvg = trade_signal.get("fvg_detail")
            if _current_fvg and _fvg_list:
                if is_first_presented_fvg(_fvg_list, _current_fvg, final_direction):
                    conf_score = min(1.0, conf_score + 0.05)
                    reasons.append("P-B1 — 1st Presented FVG post-09h29 NY (+5pts)")
        except Exception:
            pass  # fail-safe silencieux
        # ─────────────────────────────────────────────────────────────────────────────
        
        # ── P-B2 — CISD 2026 Bonus ───────────────────────────────────────────────────
        # Règle : Change In State of Delivery sur M5 dans la direction du trade = +5pts (+0.05)
        try:
            from agents.ict.structure import detect_cisd
            if df_m5 is not None and not df_m5.empty and len(df_m5) >= 3:
                # Convertir les 3 dernières bougies en liste de dicts
                last_candles = df_m5.tail(3).to_dict('records')
                cisd_res = detect_cisd(last_candles, final_direction)
                if cisd_res.get('detected') and cisd_res.get('direction') == final_direction:
                    conf_score = min(1.0, conf_score + 0.05)
                    reasons.append(f"P-B2 — CISD M5 {final_direction.upper()} (+5pts, str={round(cisd_res.get('strength',0),1)})")
        except Exception:
            pass  # fail-safe silencieux
        # ─────────────────────────────────────────────────────────────────────────────

        # ── P-B3 — Flout Pattern Bonus ────────────────────────────────────────────────
        # Règle : faux breakout institutionnel sur un OB/FVG = +5pts (+0.05)
        try:
            from agents.ict.structure import detect_flout_pattern
            if df_m5 is not None and not df_m5.empty and len(df_m5) >= 2:
                last2 = df_m5.tail(2).to_dict('records')
                _obs  = structure_report.get('order_blocks', [])
                _fvgs = structure_report.get('fvg', [])
                flout_res = detect_flout_pattern(last2, _obs, _fvgs)
                if flout_res.get('detected'):
                    conf_score = min(1.0, conf_score + 0.05)
                    reasons.append(f"P-B3 — Flout Pattern ({flout_res.get('type')}, lvl={flout_res.get('level')} +5pts)")
        except Exception:
            pass  # fail-safe silencieux
        # ─────────────────────────────────────────────────────────────────────────────

        # ── P-B4 — Suspension Block Bonus ─────────────────────────────────────────────
        # Règle : bougie isolée entre deux FVGs ouverts (above + below) = +2pts (+0.02)
        try:
            from agents.ict.structure import detect_suspension_block
            if df_m5 is not None and not df_m5.empty:
                last_candle = df_m5.iloc[-1].to_dict()
                _fvgs_sb = structure_report.get('fvg', [])
                sb_res = detect_suspension_block(last_candle, _fvgs_sb)
                if sb_res.get('detected'):
                    conf_score = min(1.0, conf_score + 0.02)
                    reasons.append("P-B4 — Suspension Block (+2pts)")
        except Exception:
            pass  # fail-safe silencieux
        # ─────────────────────────────────────────────────────────────────────────────

        # ── P-B5 — Weekly Template Bonus/Malus ───────────────────────────────────────
        # Règle : Alignment setup actuel avec le template ICT weekly = +5pts / Piège Mercredi = -5pts
        try:
            from agents.ict.structure import detect_weekly_template
            import datetime
            _weekly_candles = structure_report.get('weekly_candles', [])
            _daily_candles  = structure_report.get('daily_candles', [])
            if _weekly_candles and _daily_candles:
                _current_day = datetime.datetime.now().weekday()  # 0=Lundi … 4=Vendredi
                wt_res = detect_weekly_template(_weekly_candles, _daily_candles, _current_day)
                wt_bonus  = wt_res.get('bonus', 0)
                wt_template = wt_res.get('template', 'UNKNOWN')
                wt_dir = wt_res.get('direction', 'neutral')
                if wt_bonus != 0 and wt_template != 'UNKNOWN':
                    # Appliquer uniquement si le setup est dans la bonne direction
                    if wt_template == 'PIEGE_MERCREDI' and wt_dir == final_direction:
                        # Trade dans le sens du faux move → malus
                        conf_score = max(0.0, conf_score + wt_bonus / 100.0)
                        reasons.append(f"P-B5 — Piège Mercredi (-5pts)")
                    elif wt_template != 'PIEGE_MERCREDI' and wt_dir == final_direction:
                        # Template aligné avec le trade → bonus
                        conf_score = min(1.0, conf_score + wt_bonus / 100.0)
                        reasons.append(f"P-B5 — Weekly Template {wt_template} (+5pts)")
        except Exception:
            pass  # fail-safe silencieux
        # ─────────────────────────────────────────────────────────────────────────────

        decision_label = "EXECUTE_BUY" if final_direction == "bullish" else "EXECUTE_SELL"

        result = {
            "decision": decision_label,
            "direction": final_direction,
            "global_confidence": round(min(1.0, conf_score), 2),
            "alignment": alignment,
            "aligned_count": aligned_count,
            "total_votes": 4,
            "entry_price": trade_signal['entry_price'],
            "stop_loss": trade_signal['stop_loss'],
            "tp1": trade_signal['tp1'],
            "tp2": trade_signal['tp2'],
            "tp3": trade_signal['tp3'],
            "rr_ratio": rr,
            "reasons": reasons,
            "warnings": warnings,
        }

        # Enrichissement Liquidity (si disponible)
        if liquidity_report and not liquidity_report.get("error"):
            result["liquidity_report"]  = liquidity_report
            result["dol_bull"]          = liquidity_report["dol_bull"]
            result["dol_bear"]          = liquidity_report["dol_bear"]
            result["lrlr_hrlr"]         = liquidity_report["lrlr_hrlr"]
            result["cbdr_explosive"]    = liquidity_report["cbdr"]["cbdr_explosive"]
            result["anti_inducement"]   = liquidity_report["anti_inducement"]["status"]
            result["boolean_sweep_erl"] = liquidity_report["boolean_sweep_erl"]["value"]

        if _ENIGMA_AVAILABLE and 'enigma' in locals():
            result['enigma'] = enigma

        # ── T-20 LOOKBACK — Malus Premium HTF ────────────────────────────────────────
        # Règle KB4 §1.2 : Long interdit en zone Premium T-20.
        # Agent3 bloque déjà les cas extrêmes (gate dur Premium/Discount).
        # Ce bloc applique un malus scoring pour les cas limites où le gate laisse passer.
        ipda = macro_report.get("ipda_ranges", {})
        t20  = ipda.get("t20", {}) if isinstance(ipda, dict) else {}
        t20_eq = t20.get("equilibrium") or t20.get("eq") or t20.get("midpoint")

        if t20_eq and final_direction == "bullish":
            current_price = trade_signal.get("entry_price", 0)
            if current_price and current_price > t20_eq:
                # Update conf_score in result and log warning
                conf_score = max(0.0, result["global_confidence"] - 0.20)
                result["global_confidence"] = round(conf_score, 2)
                
                warning_msg = (
                    f"⚠️ T-20 PREMIUM — prix ({current_price:.5f}) > EQ T-20 ({t20_eq:.5f})"
                    f" → malus -20pts appliqué (zone défavorable aux Longs)"
                )
                warnings.append(warning_msg)
                result['warnings'].append(warning_msg)
                result['t20_malus'] = True
            else:
                result['t20_malus'] = False
        # ─────────────────────────────────────────────────────────────────────────────

        return result

    def check_safety_overrides(self, decision: dict, account_state: dict) -> dict:
        """
        Vérifie les limites de risque du compte.
        """
        if decision['decision'] == "NO_TRADE":
            return decision

        balance = account_state.get('balance', self.account_balance)
        equity = account_state.get('equity', balance)
        daily_trades = account_state.get('daily_trades', 0)
        max_daily = account_state.get('max_daily_trades', self.max_daily_trades)
        open_trades = account_state.get('open_trades', 0)
        max_open = account_state.get('max_open_trades', self.max_open_trades)
        daily_pnl = account_state.get('daily_pnl', 0.0)
        max_loss_pct = account_state.get('max_daily_loss_pct', self.max_daily_loss_pct)

        # 1. Max daily trades
        if daily_trades >= max_daily:
            decision['decision'] = "NO_TRADE"
            decision['reason'] = f"Safety: Max daily trades reached ({max_daily})."
            return decision

        # 2. Max open trades
        if open_trades >= max_open:
            decision['decision'] = "NO_TRADE"
            decision['reason'] = f"Safety: Max open trades reached ({max_open})."
            return decision

        # 3. Daily loss limit
        if abs(daily_pnl) / balance > max_loss_pct / 100.0 and daily_pnl < 0:
            decision['decision'] = "NO_TRADE"
            decision['reason'] = f"Safety: Daily loss limit hit ({max_loss_pct}%)."
            return decision

        # 4. Drawdown protection
        if equity < balance * 0.95:
            decision['decision'] = "NO_TRADE"
            decision['reason'] = "Safety: Equity below 95% of balance (Drawdown Protection)."
            return decision

        return decision

    def calculate_position_size(self, symbol: str, entry_price: float, stop_loss: float,
                                 account_balance: float, risk_percent: float = 1.0) -> dict:
        """
        Calcule la taille de position exacte en lots.
        """
        props = SYMBOL_PROPERTIES.get(symbol)
        if not props:
            return {"error": f"Symbole {symbol} inconnu dans SYMBOL_PROPERTIES"}
            
        risk_amount = account_balance * (risk_percent / 100.0)
        sl_distance = abs(entry_price - stop_loss)
        
        if sl_distance == 0:
            return {"error": "Distance Stop Loss est nulle."}

        # Conversion simplifiée pour lot size
        # risk_per_lot = (sl_distance / tick_size) * tick_value
        # On utilise la formule complète pour précision multi-actifs
        tick_size = props['tick_size']
        tick_value = props['tick_value']
        contract_size = props['contract_size']
        
        # Ticks de risque
        sl_ticks = sl_distance / tick_size
        
        # Valeur monétaire du risque pour 1 lot standard
        # (ticks * tick_value) * (contract_size / 100000) -> for forex 100k
        # Standard: Lots * contract * sl_dist = loss
        # On va simplifier selon le standard MT5 : Lot = Risk / (SL_Dist * ContractSize * TickValue/TickSize)
        # Mais TickValue est souvent déjà ajusté par point sur MT5.
        
        # Base calculus formula standard 
        lot_size = risk_amount / (sl_ticks * tick_value)
        
        # Round to 2 decimals
        lot_size = round(lot_size, 2)
        min_lot = 0.01
        
        sizing = {
            "lot_size": max(min_lot, lot_size),
            "risk_amount": round(risk_amount, 2),
            "sl_distance_points": round(sl_distance / tick_size, 0)
        }

        # Formule robuste : 
        # Risk = Lots * sl_distance * contract_size * (tick_value / (tick_size * contract_size))
        # Simplifiée : Risk = Lots * sl_ticks * tick_value
        risk_per_lot = sl_ticks * tick_value
        
        lot_size_raw = risk_amount / risk_per_lot
        
        # Arrondis et Clamps
        lot_step = props['lot_step']
        lot_size = math.floor(lot_size_raw / lot_step) * lot_step
        
        lot_size = max(props['min_lot'], min(props['max_lot'], lot_size))
        
        # Calcul du risque réel
        estimated_loss = lot_size * risk_per_lot
        actual_risk_pct = (estimated_loss / account_balance) * 100.0
        
        return {
            "lot_size": round(lot_size, 2),
            "risk_amount": round(risk_amount, 2),
            "risk_percent": risk_percent,
            "sl_distance": round(sl_distance, 5),
            "risk_per_lot": round(risk_per_lot, 2),
            "estimated_loss": round(estimated_loss, 2),
            "actual_risk_pct": round(actual_risk_pct, 2)
        }

    def evaluate_trade(self, structure_report: dict, time_report: dict,
                        trade_signal: dict, macro_report: dict,
                        account_state: dict, symbol: str) -> dict:
        """
        Analyse complète : Fusion -> Sécurité -> Sizing.
        """
        # 1. Décision orchestrée
        decision = self.calculate_decision(structure_report, time_report, trade_signal, macro_report)
        
        # 2. Filtres de sécurité compte
        decision = self.check_safety_overrides(decision, account_state)
        
        if decision['decision'] == "NO_TRADE":
            return {
                "action": "NO_TRADE",
                "symbol": symbol,
                "reason": decision.get('reason', 'Unknown'),
                "decision": decision
            }

        # 3. Calcul de la taille de la position
        balance = account_state.get('balance', self.account_balance)
        risk_pct = self.risk_percent
        sizing = self.calculate_position_size(symbol, decision['entry_price'], decision['stop_loss'], balance, risk_pct)
        
        if "error" in sizing:
             return {"action": "NO_TRADE", "reason": sizing['error']}

        # ── SOD Sizing Factor ─────────────────────────────────────────────────────────
        sod = time_report.get("_sod", {})
        sod_factor = get_sod_sizing_factor(sod) if _SOD_DETECTOR_AVAILABLE else 1.0
        if sod_factor < 1.0 and sod_factor > 0.0:
            original_lots = sizing['lot_size']
            sizing['lot_size']       = round(sizing['lot_size'] * sod_factor, 2)
            sizing['lot_size']       = max(sizing.get('min_lot', 0.01), sizing['lot_size'])
            sizing['sod_factor']     = sod_factor
            sizing['lot_size_full']  = original_lots
            warnings.append(
                f"SOD WEAK_DISTRIBUTION — lot réduit à {(sod_factor*100):.0f}% "
                f"({original_lots} → {sizing['lot_size']})"
            )
        # ─────────────────────────────────────────────────────────────────────────────

        return {
            "action": decision['decision'],
            "symbol": symbol,
            "decision": decision,
            "position_size": sizing,
            "entry_price": decision['entry_price'],
            "stop_loss": decision['stop_loss'],
            "tp1": decision['tp1'],
            "tp2": decision['tp2'],
            "tp3": decision['tp3'],
            "risk_amount": sizing.get('estimated_loss', sizing.get('risk_amount')),
            "risk_percent_actual": sizing.get('actual_risk_pct', risk_pct),
            "lot_size": sizing['lot_size'],
            "global_confidence": decision['global_confidence'],
            "warnings": decision.get('warnings', []),
            "reasons": decision.get('reasons', [])
        }

    def check_break_even(self, entry_price: float, current_price: float, stop_loss: float,
                          direction: str, be_trigger_rr: float = 1.0) -> dict:
        """
        Déplace le SL au prix d'entrée après 1:1.
        """
        risk_dist = abs(entry_price - stop_loss)
        if risk_dist == 0: return {"should_move_to_be": False}
        
        current_pnl = current_price - entry_price if direction == "bullish" else entry_price - current_price
        current_rr = current_pnl / risk_dist
        
        if current_rr >= be_trigger_rr:
            # Buffer de 1 pip (0.0001 ou 0.01 selon pip_value, on va arbitrer sur 10 ticks)
            # Pour simplifier, on prend juste entry_price
            new_sl = entry_price 
            return {
                "should_move_to_be": True,
                "current_rr": round(current_rr, 2),
                "new_stop_loss": float(new_sl),
                "reason": f"Price reached {be_trigger_rr}:1 R:R — moving SL to break-even"
            }
            
        return {"should_move_to_be": False, "current_rr": round(current_rr, 2)}

    def check_partial_close(self, entry_price: float, current_price: float, 
                             tp1: float, tp2: float, tp3: float,
                             direction: str, current_lot_size: float,
                             partials_taken: list[str] = None) -> dict:
        """
        Prend des profits partiels.
        """
        if partials_taken is None: partials_taken = []
        
        is_bullish = direction == "bullish"
        
        # TP3
        if "tp3" not in partials_taken:
            if (is_bullish and current_price >= tp3) or (not is_bullish and current_price <= tp3):
                return {
                    "should_close_partial": True,
                    "close_percent": 100,
                    "close_lot_size": current_lot_size,
                    "remaining_lot_size": 0.0,
                    "trigger": "tp3",
                    "reason": "Price reached TP3 — FULL EXIT"
                }

        # TP2
        if "tp2" not in partials_taken:
            if (is_bullish and current_price >= tp2) or (not is_bullish and current_price <= tp2):
                close_lots = round(current_lot_size * 0.5, 2) # On ferme 50% du RESTE (qui est 50% de l'initial si TP1 pris)
                # Mais les specs demandent % de la position INITIALE.
                # Simplifions : 25% de l'initiale au TP2.
                return {
                    "should_close_partial": True,
                    "close_percent": 25, 
                    "close_lot_size": close_lots,
                    "remaining_lot_size": round(current_lot_size - close_lots, 2),
                    "trigger": "tp2",
                    "reason": "Price reached TP2 — closing extra 25%"
                }

        # TP1
        if "tp1" not in partials_taken:
            if (is_bullish and current_price >= tp1) or (not is_bullish and current_price <= tp1):
                close_lots = round(current_lot_size * 0.5, 2)
                return {
                    "should_close_partial": True,
                    "close_percent": 50,
                    "close_lot_size": close_lots,
                    "remaining_lot_size": round(current_lot_size - close_lots, 2),
                    "trigger": "tp1",
                    "reason": "Price reached TP1 — closing 50%"
                }
                
        return {"should_close_partial": False}

    def calculate_trailing_stop(self, direction: str, current_price: float, 
                                  current_stop: float, entry_price: float,
                                  recent_swings: list[dict] = None,
                                  trailing_method: str = "structure") -> dict:
        """
        Déplace dynamiquement le SL.
        """
        new_sl = current_stop
        reason = "No structural update"
        
        if trailing_method == "structure" and recent_swings:
            if direction == "bullish":
                # Chercher le plus haut des derniers swing lows sous le prix
                lows = [s['price'] for s in recent_swings if s['type'] == 'swing_low' and s['price'] < current_price]
                if lows:
                    target_sl = max(lows)
                    if target_sl > current_stop:
                        new_sl = target_sl
                        reason = f"Trailing to last swing low at {new_sl}"
            else: # bearish
                highs = [s['price'] for s in recent_swings if s['type'] == 'swing_high' and s['price'] > current_price]
                if highs:
                    target_sl = min(highs)
                    if target_sl < current_stop:
                        new_sl = target_sl
                        reason = f"Trailing to last swing high at {new_sl}"
                        
        if new_sl != current_stop:
            return {"should_update": True, "new_stop_loss": new_sl, "method": trailing_method, "reason": reason}
            
        return {"should_update": False}

    def manage_open_trade(self, trade_state: dict, current_price: float,
                           recent_swings: list[dict] = None) -> dict:
        """
        Synthèse pour gérer un trade ouvert.
        """
        actions = []
        
        # 1. Break-even
        if not trade_state.get('be_activated', False):
            be_check = self.check_break_even(trade_state['entry_price'], current_price, trade_state['current_stop'], trade_state['direction'])
            if be_check['should_move_to_be']:
                actions.append({"type": "move_sl", "new_sl": be_check['new_stop_loss'], "reason": be_check['reason']})
                
        # 2. Partials
        p_check = self.check_partial_close(
            trade_state['entry_price'], current_price, 
            trade_state['tp1'], trade_state['tp2'], trade_state['tp3'],
            trade_state['direction'], trade_state['current_lot_size'],
            trade_state.get('partials_taken', [])
        )
        if p_check['should_close_partial']:
             actions.append({"type": "partial_close", "lots": p_check['close_lot_size'], "trigger": p_check['trigger'], "reason": p_check['reason']})
             
        # 3. Trailing
        t_check = self.calculate_trailing_stop(trade_state['direction'], current_price, trade_state['current_stop'], trade_state['entry_price'], recent_swings)
        if t_check['should_update']:
             actions.append({"type": "trailing_stop", "new_sl": t_check['new_stop_loss'], "reason": t_check['reason']})
             
        return {"actions": actions}
