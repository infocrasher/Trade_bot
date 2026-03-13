import pandas as pd

class EntryAgent:
    def __init__(self, symbol: str, structure_tf: str = "H1", entry_tf: str = "M5", pip_value: float = 0.0001):
        """
        pip_value : valeur d'un pip pour le symbole
        - 0.0001 pour EUR/USD, GBP/USD, etc.
        - 0.01 pour USD/JPY, EUR/JPY, etc.
        - 0.01 pour XAUUSD
        - 1.0 pour US100, US500
        """
        self.symbol = symbol
        self.structure_tf = structure_tf
        self.entry_tf = entry_tf
        self.pip_value = pip_value
    
    def price_to_pips(self, price_diff: float) -> float:
        """Convertit une différence de prix en pips."""
        return abs(price_diff) / self.pip_value

    def calculate_ote_zone(self, swing_start: float, swing_end: float, direction: str) -> dict:
        """
        Calcule la zone OTE entre 62% et 79% de retracement Fibonacci.
        """
        swing_range = abs(swing_end - swing_start)
        
        if direction == "bullish":
            fib_50 = swing_end - 0.50 * swing_range
            fib_705 = swing_end - 0.705 * swing_range
            fib_79 = swing_end - 0.786 * swing_range
            ote_top = fib_50
            ote_bottom = fib_79
        elif direction == "bearish":
            fib_50 = swing_end + 0.50 * swing_range
            fib_705 = swing_end + 0.705 * swing_range
            fib_79 = swing_end + 0.786 * swing_range
            ote_top = fib_79
            ote_bottom = fib_50
        else:
            return {}

        return {
            "direction": direction,
            "swing_start": float(swing_start),
            "swing_end": float(swing_end),
            "fib_50": float(fib_50),
            "fib_705": float(fib_705),
            "fib_79": float(fib_79),
            "ote_top": float(ote_top),
            "ote_bottom": float(ote_bottom),
            "swing_range": float(swing_range)
        }

    def _is_overlapping(self, a_top: float, a_bottom: float, b_top: float, b_bottom: float) -> bool:
        """Vérifie si deux zones [top, bottom] se chevauchent."""
        return a_top >= b_bottom and b_top >= a_bottom

    def find_confluence_zones(self, ote: dict, order_blocks: list[dict], fvgs: list[dict],
                               candle_high: float = None, candle_low: float = None) -> list[dict]:
        """
        Cherche OBs et FVGs qui se superposent dans la zone OTE.

        Fix ICT : on ne vérifie plus si le prix instantané est dans l'OTE.
        On vérifie si la bougie courante (high/low) intersecte la zone OTE,
        ce qui capture les wicks et les entrées intra-bougie.
        Si candle_high/candle_low ne sont pas fournis, on accepte toute confluence
        OB/FVG dans l'OTE (mode setup en attente).
        """
        if not ote:
            return []

        direction = ote['direction']
        confluences = []

        ote_top = ote['ote_top']
        ote_bottom = ote['ote_bottom']

        # ── Vérification intersection bougie × zone OTE ─────────────────────────
        # Si on a les données de la bougie courante, on vérifie que la bougie
        # a visité la zone OTE (high >= ote_bottom ET low <= ote_top).
        # Sinon (mode setup en attente), on laisse passer.
        if candle_high is not None and candle_low is not None:
            candle_touches_ote = (candle_high >= ote_bottom) and (candle_low <= ote_top)
            if not candle_touches_ote:
                return []  # La bougie n'a pas touché la zone OTE ce cycle
        # ────────────────────────────────────────────────────────────────────────
        
        # Filtre selon direction et statut
        if direction == "bullish":
            valid_obs = [ob for ob in order_blocks if ob['type'] == 'bullish_ob' and ob['status'] == 'unmitigated']
            valid_fvgs = [fvg for fvg in fvgs if fvg['type'] == 'bullish_fvg' and fvg['status'] in ['open', 'partially_filled']]
        else:
            valid_obs = [ob for ob in order_blocks if ob['type'] == 'bearish_ob' and ob['status'] == 'unmitigated']
            valid_fvgs = [fvg for fvg in fvgs if fvg['type'] == 'bearish_fvg' and fvg['status'] in ['open', 'partially_filled']]
            
        # Chercher les combinaisons (OB + OTE) ou (FVG + OTE) ou (OB + FVG + OTE)
        # Par simplicité on crée une confluence pour chaque OB ou FVG dans l'OTE, 
        # puis on essaie de fusionner/scorer ceux qui encerclent la même zone.
        
        for ob in valid_obs:
            if self._is_overlapping(ob['top'], ob['bottom'], ote_top, ote_bottom):
                # OTE + OB confluence
                c_top = min(ob['top'], ote_top)
                c_bot = max(ob['bottom'], ote_bottom)
                confluences.append({
                    "type": "ob_ote",
                    "zone_top": float(c_top),
                    "zone_bottom": float(c_bot),
                    "midpoint": float((c_top + c_bot) / 2),
                    "elements": [ob['type'], "ote"],
                    "score": 2,
                    "ob_detail": ob,
                    "fvg_detail": None
                })
                
        for fvg in valid_fvgs:
            if self._is_overlapping(fvg['top'], fvg['bottom'], ote_top, ote_bottom):
                c_top = min(fvg['top'], ote_top)
                c_bot = max(fvg['bottom'], ote_bottom)
                
                # Chercher si cette zone FVG d'OTE chevauche déjà une confluence OB_OTE
                merged = False
                for c in confluences:
                    if c['type'] == 'ob_ote' and self._is_overlapping(c['zone_top'], c['zone_bottom'], c_top, c_bot):
                        # Grosse confluence : OB + FVG + OTE
                        c['type'] = "ob_fvg_ote"
                        c['zone_top'] = min(c['zone_top'], c_top)
                        c['zone_bottom'] = max(c['zone_bottom'], c_bot)
                        c['midpoint'] = float((c['zone_top'] + c['zone_bottom']) / 2)
                        c['elements'].append(fvg['type'])
                        c['score'] = 3
                        c['fvg_detail'] = fvg
                        merged = True
                        break
                        
                if not merged:
                    confluences.append({
                        "type": "fvg_ote",
                        "zone_top": float(c_top),
                        "zone_bottom": float(c_bot),
                        "midpoint": float((c_top + c_bot) / 2),
                        "elements": [fvg['type'], "ote"],
                        "score": 2,
                        "ob_detail": None,
                        "fvg_detail": fvg
                    })
                    
        # On trie par score (les plus fortes confluences en premier)
        confluences.sort(key=lambda x: x['score'], reverse=True)
        return confluences

    def calculate_stop_loss(self, direction: str, ote: dict, entry_price: float, 
                             liquidity_sweeps: list[dict] = None, buffer_pips: float = 2.0) -> dict:
        """
        Calcule le stop loss selon la hiérarchie ICT.
        """
        buffer = buffer_pips * self.pip_value
        swing_start = ote['swing_start']
        
        sl_price = None
        method = "swing_start"
        
        if direction == "bullish":
            # SL de base = sous le swing low
            sl_price = swing_start - buffer
            
            # Priorité 1 : Sweep récent
            if liquidity_sweeps:
                # Chercher un sweep récent qui a balayé sous notre swing_start
                recent_sweeps = [s for s in liquidity_sweeps if s['type'] == 'sellside_sweep' and s['wick_extreme'] <= swing_start]
                if recent_sweeps:
                    method = "sweep_extreme"
                    sl_price = recent_sweeps[-1]['wick_extreme'] - buffer
                    
        elif direction == "bearish":
            sl_price = swing_start + buffer
            
            if liquidity_sweeps:
                recent_sweeps = [s for s in liquidity_sweeps if s['type'] == 'buyside_sweep' and s['wick_extreme'] >= swing_start]
                if recent_sweeps:
                    method = "sweep_extreme"
                    sl_price = recent_sweeps[-1]['wick_extreme'] + buffer

        return {
            "stop_loss": float(sl_price),
            "method": method,
            "risk_pips": float(self.price_to_pips(abs(entry_price - sl_price))),
            "entry_price": float(entry_price)
        }

    def calculate_take_profits(self, direction: str, entry_price: float, 
                                ote: dict, opposite_liquidity: list[dict] = None) -> dict:
        """
        Calcule les niveaux de take profit.
        """
        swing_end = ote['swing_end']
        swing_range = ote['swing_range']
        
        tp1_price = swing_end
        
        if direction == "bullish":
            tp2_price = swing_end + 0.27 * swing_range
            tp3_price = swing_end + 0.62 * swing_range
        else:
            tp2_price = swing_end - 0.27 * swing_range
            tp3_price = swing_end - 0.62 * swing_range
            
        loss_dist = abs(entry_price - tp1_price) # Just used to ensure we have positive distances to calc ratio cleanly later

        return {
            "tp1": {"price": float(tp1_price), "method": "swing_end"},
            "tp2": {"price": float(tp2_price), "method": "fib_-27"},
            "tp3": {"price": float(tp3_price), "method": "fib_-62"}
        }
        
    def _add_rr_to_tps(self, tps: dict, entry_price: float, stop_loss: float) -> dict:
        risk = abs(entry_price - stop_loss)
        if risk == 0:
            risk = 0.00000001
            
        for key in ['tp1', 'tp2', 'tp3']:
            reward = abs(tps[key]['price'] - entry_price)
            tps[key]['rr_ratio'] = round(reward / risk, 2)
            
        tps['best_rr'] = tps['tp3']['rr_ratio']
        return tps

    def find_entry_confirmation(self, df_entry: pd.DataFrame, direction: str, confluence_zone: dict) -> dict:
        """
        Cherche une bougie de confirmation sur le M5 dans la zone de confluence.
        """
        if df_entry is None or len(df_entry) == 0:
            return {"confirmed": False, "reason": "No entry data"}
            
        z_top = confluence_zone['zone_top']
        z_bot = confluence_zone['zone_bottom']
        mid = confluence_zone['midpoint']
        
        closes = df_entry['close'].values
        opens = df_entry['open'].values
        highs = df_entry['high'].values
        lows = df_entry['low'].values
        times = df_entry['time'].dt.strftime('%Y-%m-%d %H:%M').values
        
        in_zone = False
        
        for i in range(len(df_entry)):
            c, o, h, l = closes[i], opens[i], highs[i], lows[i]
            
            if direction == "bullish":
                # Le prix pénètre dans la zone (ou était déjà dedans)
                if l <= z_top:
                    in_zone = True
                    
                if in_zone and c > o and c > mid:
                    return {
                        "confirmed": True,
                        "entry_price": float(c),
                        "confirmation_type": "bullish_candle_in_zone",
                        "candle_index": i,
                        "time": times[i]
                    }
                    
            elif direction == "bearish":
                if h >= z_bot:
                    in_zone = True
                    
                if in_zone and c < o and c < mid:
                    return {
                        "confirmed": True,
                        "entry_price": float(c),
                        "confirmation_type": "bearish_candle_in_zone",
                        "candle_index": i,
                        "time": times[i]
                    }
                    
        return {"confirmed": False, "reason": "Price not in zone yet" if not in_zone else "No confirmation candle"}

    def generate_trade_signal(self, confluence: dict, stop_loss: dict, 
                               take_profits: dict, confirmation: dict,
                               time_quality: str = "medium") -> dict:
        """
        Compile toutes les informations en un signal.
        """
        signal = "NO_TRADE"
        confidence = 0.50
        
        if not confluence or confluence['score'] < 2:
            return {"signal": "NO_TRADE", "reason": "Not enough confluences (score < 2)"}
            
        if not confirmation.get('confirmed', False):
             return {"signal": "NO_TRADE", "reason": "No confirmation on entry TF"}
             
        # Add confluence score bits
        confidence += min(0.30, 0.10 * confluence.get('score', 0))
        
        # Confirmation
        confidence += 0.10
        
        # Time
        if time_quality == "high":
            confidence += 0.10
        elif time_quality == "medium":
            confidence += 0.05
        elif time_quality == "no_trade":
            return {"signal": "NO_TRADE", "reason": "Time quality is NO_TRADE"}
            
        confidence = min(0.95, confidence)
        
        rr_tp1 = take_profits.get('tp1', {}).get('rr_ratio', 0)
        if rr_tp1 < 2.0:
            try:
                from agents.gate_logger import log_ict_blocked
                log_ict_blocked(
                    pair=self.symbol, horizon="unknown",
                    reason=f"R:R ratio too low ({rr_tp1} < 2.0)",
                    bias=bias if 'bias' in dir() else "unknown",
                    htf_alignment="unknown",
                    entry=stop_loss.get("entry_price", 0),
                    sl=stop_loss.get("stop_loss", 0),
                    tp1=take_profits.get("tp1", {}).get("price", 0),
                    rr=rr_tp1,
                )
            except Exception:
                pass
            return {"signal": "NO_TRADE", "reason": f"R:R ratio too low ({rr_tp1} < 2.0)"}
            
        # Determiner SENS
        direction = "bullish" if stop_loss['stop_loss'] < stop_loss['entry_price'] else "bearish"
        signal = "BUY" if direction == "bullish" else "SELL"
        
        reasons = [
            f"OTE zone reached in {direction} direction",
            f"Confluences: {', '.join(confluence.get('elements', []))}",
            f"Confirmation candle found at {confirmation.get('time')}"
        ]
        
        return {
            "signal": signal,
            "confidence": round(confidence, 2),
            "entry_price": stop_loss['entry_price'],
            "stop_loss": stop_loss['stop_loss'],
            "tp1": take_profits['tp1']['price'],
            "tp2": take_profits['tp2']['price'],
            "tp3": take_profits['tp3']['price'],
            "risk_pips": round(stop_loss['risk_pips'], 1),
            "reward_pips_tp1": round(self.price_to_pips(abs(take_profits['tp1']['price'] - stop_loss['entry_price'])), 1),
            "rr_ratio": rr_tp1,
            "best_rr": take_profits['best_rr'],
            "confluence_score": confluence['score'],
            "time_quality": time_quality,
            "reasons": reasons
        }

    def analyze(self, structure_report: dict, time_report: dict, df_entry: pd.DataFrame) -> dict:
        """
        Analyse complète pour générer le signal.
        """
        bias = structure_report.get('bias', 'neutral')
        if bias == 'neutral':
            return {"signal": "NO_TRADE", "reason": "Neutral structural bias"}
            
        time_q = time_report.get('trade_quality', 'no_trade')
        if time_q == 'no_trade':
             return {"signal": "NO_TRADE", "reason": "Out of Killzone or Closed day"}

        # Chercher le mvt de ref. On prend le dernier BOS ou CHOCH du biais actuel
        # Pour simplifier, on prendra juste le biais et on cherchera le mvt entre les deux derniers swings
        swings = structure_report.get('swings', [])
        if len(swings) < 2:
            return {"signal": "NO_TRADE", "reason": "Not enough swings"}
            
        # Trouver dernier move aligné
        t_highs = [s for s in swings if s['type'] == 'swing_high']
        t_lows = [s for s in swings if s['type'] == 'swing_low']
        
        if not t_highs or not t_lows:
            return {"signal": "NO_TRADE", "reason": "Missing swings highs/lows"}
            
        s_start, s_end = None, None
        
        if bias == "bullish":
            # Chercher le dernier mouvement Low → High (parcourir depuis la fin)
            for i in range(len(swings) - 1, 0, -1):
                if swings[i]['type'] == 'swing_high' and swings[i-1]['type'] == 'swing_low':
                    s_start, s_end = swings[i-1]['price'], swings[i]['price']
                    break
            # Fallback : dernier low avant dernier high
            if s_start is None and t_lows and t_highs:
                # Prendre le dernier high et le low le plus récent avant lui
                last_high = t_highs[-1]
                candidates = [l for l in t_lows if l['index'] < last_high['index']]
                if candidates:
                    s_start, s_end = candidates[-1]['price'], last_high['price']
        else:  # bearish
            # Chercher le dernier mouvement High → Low
            for i in range(len(swings) - 1, 0, -1):
                if swings[i]['type'] == 'swing_low' and swings[i-1]['type'] == 'swing_high':
                    s_start, s_end = swings[i-1]['price'], swings[i]['price']
                    break
            # Fallback : dernier high avant dernier low
            if s_start is None and t_highs and t_lows:
                last_low = t_lows[-1]
                candidates = [h for h in t_highs if h['index'] < last_low['index']]
                if candidates:
                    s_start, s_end = candidates[-1]['price'], last_low['price']
                     
        if s_start is None or s_end is None:
             return {"signal": "NO_TRADE", "reason": "No valid swing movement matching bias"}
             
        ote = self.calculate_ote_zone(s_start, s_end, bias)

        _ote_top    = ote.get("ote_top")
        _ote_bottom = ote.get("ote_bottom")
        
        obs = structure_report.get('order_blocks', [])
        fvgs = structure_report.get('fvg', [])
        
        # ── Fix ICT : intersection bougie × OTE ────────────────────────────────
        # On passe le high/low de la dernière bougie du TF d'entrée pour vérifier
        # si la bougie a visité la zone OTE (wick compris), pas seulement le close.
        candle_high = None
        candle_low  = None
        if df_entry is not None and len(df_entry) > 0:
            last_candle = df_entry.iloc[-1]
            candle_high = float(last_candle["high"])
            candle_low  = float(last_candle["low"])
        # ────────────────────────────────────────────────────────────────────────

        confluences = self.find_confluence_zones(ote, obs, fvgs,
                                                  candle_high=candle_high,
                                                  candle_low=candle_low)
        if not confluences:
            try:
                from agents.gate_logger import log_ict_blocked
                _price = float(df_entry["close"].iloc[-1]) if df_entry is not None and len(df_entry) > 0 else 0
                log_ict_blocked(
                    pair=self.symbol, horizon="unknown",
                    reason="No Confluence in OTE",
                    bias=bias,
                    htf_alignment=structure_report.get("htf_alignment", "unknown"),
                    entry=_price, sl=0, tp1=0,
                    ote_top=_ote_top, ote_bottom=_ote_bottom,
                    candle_high=candle_high, candle_low=candle_low,
                )
            except Exception:
                pass
            return {"signal": "NO_TRADE", "reason": "No Confluence in OTE"}
            
        best_confluence = confluences[0]
        
        confirmation = self.find_entry_confirmation(df_entry, bias, best_confluence)
        if not confirmation.get('confirmed'):
            return {"signal": "NO_TRADE", "reason": confirmation.get('reason')}
            
        entry_price = confirmation['entry_price']
        
        # Nouvelles fonctions Phase 1
        # Pour Premium/Discount, il nous faut le high et low du dernier move
        if bias == "bullish":
            swing_high = s_end
            swing_low = s_start
        else:
            swing_high = s_start
            swing_low = s_end
            
        pd_check = self.check_premium_discount(entry_price, swing_high, swing_low, bias)
        if not pd_check['is_valid']:
            return {"signal": "NO_TRADE", "reason": pd_check["detail"]}
            
        key_levels = structure_report.get('key_levels', {})
        eq_levels = structure_report.get('equal_levels', [])
        
        dol_targets = self.find_draw_on_liquidity(bias, entry_price, key_levels, eq_levels, fvgs)
        
        judas = time_report.get("judas_swing", {})
        sd_targets = {}
        if judas.get("detected"):
            sd_targets = self.calculate_std_dev_targets(judas.get("sweep_level", 0.0), judas.get("sweep_extreme", 0.0), bias)
        
        # Stop loss & TPs
        sl_data = self.calculate_stop_loss(bias, ote, entry_price, structure_report.get('liquidity_sweeps', []), buffer_pips=2.0)
        


        tps = self.calculate_take_profits(bias, entry_price, ote)
        tps = self._add_rr_to_tps(tps, entry_price, sl_data['stop_loss'])
        
        # Final Signal
        signal_output = self.generate_trade_signal(best_confluence, sl_data, tps, confirmation, time_q)
        
        if signal_output['signal'] != "NO_TRADE":
            signal_output['premium_discount'] = pd_check
            signal_output['dol_targets'] = dol_targets
            signal_output['sd_targets'] = sd_targets
            
        signal_output["ote_top"]     = _ote_top if '_ote_top' in dir() else None
        signal_output["ote_bottom"]  = _ote_bottom if '_ote_bottom' in dir() else None
        signal_output["candle_high"] = candle_high if 'candle_high' in dir() else None
        signal_output["candle_low"]  = candle_low if 'candle_low' in dir() else None
        return signal_output

    def check_premium_discount(self, current_price: float, swing_high: float, 
                                swing_low: float, direction: str) -> dict:
        """
        Vérifie que l'entrée est dans la bonne zone.
        """
        equilibrium = (swing_high + swing_low) / 2
        is_valid = False
        zone = "equilibrium"
        detail = ""
        
        if direction == "bullish":
            if current_price < equilibrium:
                is_valid = True
                zone = "discount"
                detail = f"Price {current_price} is in Discount (below {round(equilibrium, 5)}) — valid for BUY"
            else:
                zone = "premium"
                detail = f"Price {current_price} is in Premium (above {round(equilibrium, 5)}) — INVALID for BUY"
        elif direction == "bearish":
            if current_price > equilibrium:
                is_valid = True
                zone = "premium"
                detail = f"Price {current_price} is in Premium (above {round(equilibrium, 5)}) — valid for SELL"
            else:
                zone = "discount"
                detail = f"Price {current_price} is in Discount (below {round(equilibrium, 5)}) — INVALID for SELL"
                
        return {
            "equilibrium": float(equilibrium),
            "zone": zone,
            "is_valid": is_valid,
            "detail": detail
        }

    def find_draw_on_liquidity(self, direction: str, entry_price: float,
                                key_levels: dict, equal_levels: list[dict],
                                htf_fvgs: list[dict] = None) -> list[dict]:
        """
        Identifie les cibles institutionnelles réelles.
        """
        targets = []
        if not htf_fvgs: htf_fvgs = []
        
        if direction == "bullish":
            if "PDH" in key_levels and key_levels["PDH"] > entry_price:
                targets.append({"level": key_levels["PDH"], "type": "PDH", "distance_pips": self.price_to_pips(key_levels["PDH"] - entry_price)})
            if "PWH" in key_levels and key_levels["PWH"] > entry_price:
                targets.append({"level": key_levels["PWH"], "type": "PWH", "distance_pips": self.price_to_pips(key_levels["PWH"] - entry_price)})
            if "PMH" in key_levels and key_levels["PMH"] > entry_price:
                targets.append({"level": key_levels["PMH"], "type": "PMH", "distance_pips": self.price_to_pips(key_levels["PMH"] - entry_price)})
                
            for eq in equal_levels:
                if eq["type"] == "EQH" and eq["level"] > entry_price:
                    targets.append({"level": eq["level"], "type": "EQH", "distance_pips": self.price_to_pips(eq["level"] - entry_price), "strength": eq["strength"]})
                    
            for f in htf_fvgs:
                if f["type"] == "bearish_fvg" and f["bottom"] > entry_price:
                    targets.append({"level": f["bottom"], "type": "HTF_FVG", "distance_pips": self.price_to_pips(f["bottom"] - entry_price)})
                    
        else: # bearish
            if "PDL" in key_levels and key_levels["PDL"] < entry_price:
                targets.append({"level": key_levels["PDL"], "type": "PDL", "distance_pips": self.price_to_pips(entry_price - key_levels["PDL"])})
            if "PWL" in key_levels and key_levels["PWL"] < entry_price:
                targets.append({"level": key_levels["PWL"], "type": "PWL", "distance_pips": self.price_to_pips(entry_price - key_levels["PWL"])})
            if "PML" in key_levels and key_levels["PML"] < entry_price:
                targets.append({"level": key_levels["PML"], "type": "PML", "distance_pips": self.price_to_pips(entry_price - key_levels["PML"])})
                
            for eq in equal_levels:
                if eq["type"] == "EQL" and eq["level"] < entry_price:
                    targets.append({"level": eq["level"], "type": "EQL", "distance_pips": self.price_to_pips(entry_price - eq["level"]), "strength": eq["strength"]})
                    
            for f in htf_fvgs:
                if f["type"] == "bullish_fvg" and f["top"] < entry_price:
                    targets.append({"level": f["top"], "type": "HTF_FVG", "distance_pips": self.price_to_pips(entry_price - f["top"])})
                    
        targets.sort(key=lambda x: x["distance_pips"])
        return targets

    def calculate_std_dev_targets(self, judas_start: float, judas_end: float, 
                                   direction: str) -> dict:
        """
        Calcule les projections Standard Deviation à partir de la jambe Judas.
        """
        judas_range = abs(judas_end - judas_start)
        
        if judas_range == 0:
            return {}
            
        if direction == "bullish":
            sd_1 = judas_end + 1.0 * judas_range
            sd_2 = judas_end + 2.0 * judas_range
            sd_2_5 = judas_end + 2.5 * judas_range
        else: # bearish
            sd_1 = judas_end - 1.0 * judas_range
            sd_2 = judas_end - 2.0 * judas_range
            sd_2_5 = judas_end - 2.5 * judas_range
            
        return {
            "sd_1": {"price": float(sd_1), "label": "SD -1.0 (partiel scalp)"},
            "sd_2": {"price": float(sd_2), "label": "SD -2.0 (target principal)"},
            "sd_2_5": {"price": float(sd_2_5), "label": "SD -2.5 (target algorithmique)"}
        }