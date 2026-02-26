import math

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
                           trade_signal: dict, macro_report: dict) -> dict:
        """
        Fusionne les 4 rapports et prend la décision finale via un vote pondéré.
        """
        reasons = []
        warnings = []
        
        # 1. ÉLIMINATIONS DIRECTES
        if trade_signal.get('signal') == "NO_TRADE":
            return {"decision": "NO_TRADE", "reason": "Agent d'entrée (A3) ne voit pas d'opportunité."}
        
        if not time_report.get('can_trade', False):
            return {"decision": "NO_TRADE", "reason": "Agent Temporel (A2) bloque le trade (Killzone/Jour)."}
            
        if not macro_report.get('can_trade', True):
            return {"decision": "NO_TRADE", "reason": f"Agent Macro (A4) bloque : {macro_report.get('detail')}"}
            
        if macro_report.get('macro_bias') == "no_trade":
            return {"decision": "NO_TRADE", "reason": "Biais Macro est trop instable (no_trade)."}

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
                "reason": f"Manque de consensus : seul {aligned_count}/4 agents sont alignés sur {final_direction}."
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
        
        # 4. VALIDATION R:R FINALE
        rr = trade_signal.get('rr_ratio', 0.0)
        if rr < 1.5:
             return {"decision": "NO_TRADE", "reason": f"R:R trop faible ({rr} < 1.5)."}
        
        if rr >= 3.0:
            conf_score += 0.05
            reasons.append("Bonus R:R élevé (>= 3.0)")

        if conf_score < 0.55:
            return {"decision": "NO_TRADE", "reason": f"Confiance globale trop faible ({conf_score:.2f} < 0.55)."}

        # Détails des raisons
        reasons.append(f"Structure: {s_bias}")
        reasons.append(f"Time: {t_quality} ({time_report.get('active_killzone', {}).get('name', 'N/A')})")
        reasons.append(f"Entry: Confiance {trade_signal.get('confidence')} - OTE zone")
        reasons.append(f"Macro: {m_bias} (Confiance {macro_report.get('confidence')})")

        # Warnings
        for k, v in alignment.items():
            if v != final_direction and v != "neutral":
                warnings.append(f"Divergence {k}: signal {v} vs trade {final_direction}")

        decision_label = "EXECUTE_BUY" if final_direction == "bullish" else "EXECUTE_SELL"
        
        return {
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
            "warnings": warnings
        }

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
            "risk_amount": sizing['estimated_loss'],
            "risk_percent_actual": sizing['actual_risk_pct'],
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
