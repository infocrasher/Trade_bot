import pandas as pd
import numpy as np
from datetime import datetime

try:
    from agents.ict.ob_scorer import score_order_block
    _OB_SCORER_AVAILABLE = True
except ImportError:
    _OB_SCORER_AVAILABLE = False

class StructureAgent:
    def __init__(self, symbol: str, structure_tf: str = "H1", entry_tf: str = "M5"):
        self.symbol = symbol
        self.structure_tf = structure_tf
        self.entry_tf = entry_tf

    def detect_swing_points(self, df: pd.DataFrame, lookback: int = 3) -> list[dict]:
        """
        Détecte les Strong Swing Highs et Lows.
        Un point est un swing s'il est le plus haut/bas sur (lookback * 2 + 1) bougies.
        """
        swings = []
        if len(df) < 2 * lookback + 1:
            return swings
        
        highs = df['high'].values
        lows = df['low'].values
        times = df['time'].dt.strftime('%Y-%m-%d %H:%M').values
        
        for i in range(lookback, len(df) - lookback):
            # Vérification Swing High
            is_swing_high = True
            for j in range(1, lookback + 1):
                if highs[i] <= highs[i-j] or highs[i] <= highs[i+j]:
                    is_swing_high = False
                    break
            if is_swing_high:
                swings.append({
                    "index": i,
                    "type": "swing_high",
                    "price": float(highs[i]),
                    "time": times[i]
                })
                
            # Vérification Swing Low
            is_swing_low = True
            for j in range(1, lookback + 1):
                if lows[i] >= lows[i-j] or lows[i] >= lows[i+j]:
                    is_swing_low = False
                    break
            if is_swing_low:
                swings.append({
                    "index": i,
                    "type": "swing_low",
                    "price": float(lows[i]),
                    "time": times[i]
                })
        return swings

    def detect_displacement(self, df: pd.DataFrame, swings: list[dict], avg_period: int = 10) -> list[dict]:
        """
        Détecte les bougies de Displacement (très forte impulsion).
        """
        displacements = []
        if len(df) < avg_period + 1:
            return displacements
            
        bodies = df['body'].values
        body_ratios = df['body_ratio'].values
        closes = df['close'].values
        opens = df['open'].values
        times = df['time'].dt.strftime('%Y-%m-%d %H:%M').values
        
        for i in range(avg_period, len(df)):
            avg_body = np.mean(bodies[i-avg_period:i])
            if avg_body == 0:
                continue
                
            candle_body = bodies[i]
            body_ratio = body_ratios[i]
            
            # Force (corps >= 1.3x moyenne) et Propreté (ratio corps/range >= 0.70)
            if candle_body >= 1.3 * avg_body and body_ratio >= 0.70:
                is_bullish = closes[i] > opens[i]
                
                # Vérifie si la bougie casse une structure (swing précédent)
                broken_swing = None
                past_swings = [s for s in swings if s['index'] < i]
                
                if is_bullish:
                    # Casse d'un swing high : clôture au-dessus alors qu'avant c'était en-dessous
                    recent_highs = [s for s in past_swings if s['type'] == 'swing_high' and closes[i-1] <= s['price']]
                    if recent_highs:
                        last_high = recent_highs[-1]
                        if closes[i] > last_high['price']:
                            broken_swing = last_high
                else:
                    # Casse d'un swing low : clôture en-dessous alors qu'avant c'était au-dessus
                    recent_lows = [s for s in past_swings if s['type'] == 'swing_low' and closes[i-1] >= s['price']]
                    if recent_lows:
                        last_low = recent_lows[-1]
                        if closes[i] < last_low['price']:
                            broken_swing = last_low
                            
                if broken_swing is not None:
                    displacements.append({
                        "index": i,
                        "type": "bullish_displacement" if is_bullish else "bearish_displacement",
                        "candle_body": float(candle_body),
                        "avg_body": float(avg_body),
                        "body_ratio": float(body_ratio),
                        "broke_swing": {
                            "index": broken_swing["index"],
                            "price": broken_swing["price"]
                        },
                        "time": times[i]
                    })

        return displacements


    def detect_fvg(self, df: pd.DataFrame) -> list[dict]:
        """
        Détecte les Fair Value Gaps (déséquilibres de prix entre 3 bougies).
        """
        fvgs = []
        if len(df) < 3:
            return fvgs
            
        highs = df['high'].values
        lows = df['low'].values
        times = df['time'].dt.strftime('%Y-%m-%d %H:%M').values
        
        for i in range(2, len(df)):
            # Bullish FVG (Bougie 1 High < Bougie 3 Low)
            if lows[i] > highs[i-2]:
                top = float(lows[i])
                bottom = float(highs[i-2])
                fvgs.append({
                    "index": i, # Confirmé à l'index i
                    "displacement_index": i-1, # La bougie centrale
                    "type": "bullish_fvg",
                    "top": top,
                    "bottom": bottom,
                    "midpoint": (top + bottom) / 2.0,
                    "status": "open",
                    "time": times[i]
                })
                
            # Bearish FVG (Bougie 1 Low > Bougie 3 High)
            elif highs[i] < lows[i-2]:
                top = float(lows[i-2])
                bottom = float(highs[i])
                fvgs.append({
                    "index": i,
                    "displacement_index": i-1,
                    "type": "bearish_fvg",
                    "top": top,
                    "bottom": bottom,
                    "midpoint": (top + bottom) / 2.0,
                    "status": "open",
                    "time": times[i]
                })

        # Mise à jour du statut mitigé / partiellement comblé
        for fvg in fvgs:
            idx = fvg['index']
            is_bullish = fvg['type'] == 'bullish_fvg'
            for j in range(idx + 1, len(df)):
                if is_bullish:
                    if lows[j] <= fvg['bottom']:
                        fvg['status'] = 'filled'
                        break
                    elif lows[j] < fvg['top'] and fvg['status'] == 'open':
                        fvg['status'] = 'partially_filled'
                else:
                    if highs[j] >= fvg['top']:
                        fvg['status'] = 'filled'
                        break
                    elif highs[j] > fvg['bottom'] and fvg['status'] == 'open':
                        fvg['status'] = 'partially_filled'
                        
        return fvgs


    def detect_order_blocks(self, df: pd.DataFrame, displacements: list[dict], fvgs: list[dict],
                            equal_levels: list = None) -> list[dict]:
        """
        Détecte les Order Blocks (OB) avant un grand mouvement (displacement).
        """
        obs = []
        opens = df['open'].values
        closes = df['close'].values
        highs = df['high'].values
        lows = df['low'].values
        times = df['time'].dt.strftime('%Y-%m-%d %H:%M').values
        
        # Pour vérifier rapidement la confluence avec un FVG (on vérifie si le déplacement a créé un FVG)
        fvg_disp_indices = set(f['displacement_index'] for f in fvgs)
        
        for disp in displacements:
            disp_idx = disp['index']
            disp_type = disp['type']
            has_fvg = disp_idx in fvg_disp_indices
            
            if disp_type == 'bullish_displacement':
                # Dernière bougie baissière avant l'impulsion
                ob_idx = -1
                for j in range(disp_idx - 1, -1, -1):
                    if closes[j] < opens[j]:
                        ob_idx = j
                        break
                        
                if ob_idx != -1:
                    obs.append({
                        "index": ob_idx,
                        "type": "bullish_ob",
                        "top": float(highs[ob_idx]),
                        "bottom": float(lows[ob_idx]),
                        "has_fvg_confluence": has_fvg,
                        "displacement_index": disp_idx,
                        "status": "unmitigated",
                        "time": times[ob_idx],
                        # Défauts si scorer indisponible
                        "ob_score": 3, "ob_grade": "OK",
                        "ob_details": ["scorer_unavailable"], "ob_valid": True
                    })
                    
            elif disp_type == 'bearish_displacement':
                # Dernière bougie haussière avant l'impulsion
                ob_idx = -1
                for j in range(disp_idx - 1, -1, -1):
                    if closes[j] > opens[j]:
                        ob_idx = j
                        break
                        
                if ob_idx != -1:
                    obs.append({
                        "index": ob_idx,
                        "type": "bearish_ob",
                        "top": float(highs[ob_idx]),
                        "bottom": float(lows[ob_idx]),
                        "has_fvg_confluence": has_fvg,
                        "displacement_index": disp_idx,
                        "status": "unmitigated",
                        "time": times[ob_idx],
                        # Défauts si scorer indisponible
                        "ob_score": 3, "ob_grade": "OK",
                        "ob_details": ["scorer_unavailable"], "ob_valid": True
                    })

        # Vérification de la mitigation
        for ob in obs:
            start_check = ob['displacement_index'] + 1
            is_bullish = ob['type'] == 'bullish_ob'
            for j in range(start_check, len(df)):
                if is_bullish:
                    if lows[j] <= ob['top'] and lows[j] >= ob['bottom']:
                        ob['status'] = 'mitigated'
                        break
                else:
                    if highs[j] >= ob['bottom'] and highs[j] <= ob['top']:
                        ob['status'] = 'mitigated'
                        break

        # ── Scoring OB (après mitigation connue) ─────────────────────────────────
        if _OB_SCORER_AVAILABLE:
            for ob in obs:
                scoring = score_order_block(
                    ob_idx       = ob['index'],
                    opens        = opens,
                    closes       = closes,
                    highs        = highs,
                    lows         = lows,
                    has_fvg      = ob['has_fvg_confluence'],
                    is_mitigated = ob['status'] == 'mitigated',
                    equal_levels = equal_levels
                )
                ob.update(scoring)
                        
        return obs


    def detect_bos_choch(self, df: pd.DataFrame, swings: list[dict]) -> list[dict]:
        """
        Détecte les Break of Structure (BOS) et Change of Character (CHoCH).
        """
        events = []
        if not swings:
            return events
            
        closes = df['close'].values
        times = df['time'].dt.strftime('%Y-%m-%d %H:%M').values
        
        last_high = None
        last_low = None
        trend = "neutral" 
        
        # Initialisation de la tendance sur les premiers swings alternés
        if len(swings) >= 2:
            for k in range(len(swings) - 1):
                s1 = swings[k]
                s2 = swings[k + 1]
                if s1['type'] == 'swing_low' and s2['type'] == 'swing_high':
                    if s2['price'] > s1['price']:  # HL → HH = bullish
                        trend = "bullish"
                        break
                elif s1['type'] == 'swing_high' and s2['type'] == 'swing_low':
                    if s2['price'] < s1['price']:  # LH → LL = bearish
                        trend = "bearish"
                        break
                
        swing_idx = 0
        broken_highs = set()
        broken_lows = set()
        
        for i in range(len(df)):
            # Mettre à jour les swings actifs jusqu'à la bougie i
            while swing_idx < len(swings) and swings[swing_idx]['index'] <= i:
                if swings[swing_idx]['type'] == 'swing_high':
                    last_high = swings[swing_idx]
                else:
                    last_low = swings[swing_idx]
                swing_idx += 1
                
            c_price = float(closes[i])
            
            # Cassure à la hausse (Clôture au-dessus du dernier swing_high)
            if last_high is not None and c_price > last_high['price'] and last_high['index'] not in broken_highs:
                broken_highs.add(last_high['index'])
                if trend == "bullish":
                    events.append({
                        "index": i,
                        "type": "bullish_bos",
                        "broken_level": last_high['price'],
                        "close_price": c_price,
                        "time": times[i]
                    })
                elif trend == "bearish":
                    events.append({
                        "index": i,
                        "type": "bullish_choch",
                        "broken_level": last_high['price'],
                        "close_price": c_price,
                        "time": times[i]
                    })
                    trend = "bullish"
                elif trend == "neutral":
                    trend = "bullish"
                    
            # Cassure à la baisse (Clôture en-dessous du dernier swing_low)
            if last_low is not None and c_price < last_low['price'] and last_low['index'] not in broken_lows:
                broken_lows.add(last_low['index'])
                if trend == "bearish":
                    events.append({
                        "index": i,
                        "type": "bearish_bos",
                        "broken_level": last_low['price'],
                        "close_price": c_price,
                        "time": times[i]
                    })
                elif trend == "bullish":
                    events.append({
                        "index": i,
                        "type": "bearish_choch",
                        "broken_level": last_low['price'],
                        "close_price": c_price,
                        "time": times[i]
                    })
                    trend = "bearish"
                elif trend == "neutral":
                    trend = "bearish"
                    
        return events


    def detect_liquidity_sweeps(self, df: pd.DataFrame, swings: list[dict]) -> list[dict]:
        """
        Détecte les prises de liquidité (mèches qui dépassent un swing mais clôturent en-dessous/au-dessus).
        """
        sweeps = []
        highs = df['high'].values
        lows = df['low'].values
        closes = df['close'].values
        times = df['time'].dt.strftime('%Y-%m-%d %H:%M').values
        
        swing_highs = [s for s in swings if s['type'] == 'swing_high']
        swing_lows = [s for s in swings if s['type'] == 'swing_low']
        
        # Pour éviter de signaler plusieurs fois la même mèche pour le même swing, on mémorise
        logged_pairs = set() 
        
        for i in range(len(df)):
            h = highs[i]
            l = lows[i]
            c = closes[i]
            
            # Buyside sweep : mèche au-dessus d'un Swing High, mais clôture en-dessous
            for sh in reversed(swing_highs):
                if sh['index'] < i:
                    if h > sh['price'] and c < sh['price']:
                        pair_id = f"buy_{i}_{sh['index']}"
                        if pair_id not in logged_pairs:
                            sweeps.append({
                                "index": i,
                                "type": "buyside_sweep",
                                "swept_level": sh['price'],
                                "wick_extreme": float(h),
                                "close": float(c),
                                "time": times[i]
                            })
                            logged_pairs.add(pair_id)
                        break # On s'arrête au premier swing balayé pour cette bougie
                        
            # Sellside sweep : mèche en-dessous d'un Swing Low, mais clôture au-dessus
            for sl in reversed(swing_lows):
                if sl['index'] < i:
                    if l < sl['price'] and c > sl['price']:
                        pair_id = f"sell_{i}_{sl['index']}"
                        if pair_id not in logged_pairs:
                            sweeps.append({
                                "index": i,
                                "type": "sellside_sweep",
                                "swept_level": sl['price'],
                                "wick_extreme": float(l),
                                "close": float(c),
                                "time": times[i]
                            })
                            logged_pairs.add(pair_id)
                        break
                        
        return sweeps


    def _determine_bias(self, bos_choch: list[dict], swings: list[dict]) -> str:
        """
        Détermine le biais directionnel (bullish, bearish, neutral) basé sur les récents CHoCH/BOS.
        """
        if not bos_choch:
            return "neutral"
        last_event = bos_choch[-1]['type']
        if 'bullish' in last_event:
            return "bullish"
        elif 'bearish' in last_event:
            return "bearish"
        return "neutral"


    def analyze(self) -> dict:
        """
        Lance l'analyse complète et retourne un rapport structuré.
        """
        from mt5_data import get_candles, TIMEFRAMES
        
        try:
            # 1. Récupérer les données sur le timeframe principal de structure
            df_struct = get_candles(self.symbol, TIMEFRAMES[self.structure_tf], count=500)
            # df_entry sera utilisé par l'Agent 3 (Entry Precision) dans une prochaine itération
            # df_entry = get_candles(self.symbol, TIMEFRAMES[self.entry_tf], count=500)
        except Exception as e:
            return {"error": f"Failed to get data: {str(e)}"}
            
        # 2. Détecter les swings sur le TF structure
        swings = self.detect_swing_points(df_struct)
        
        # 3. Détecter les displacements
        displacements = self.detect_displacement(df_struct, swings)
        
        # 4. Détecter les FVG
        fvgs = self.detect_fvg(df_struct)
        
        # Amélioration 6 : Filtrer les displacements pour ne garder que ceux qui ont créé un FVG
        fvg_displacement_indices = set(f['displacement_index'] for f in fvgs)
        displacements = [d for d in displacements if d['index'] in fvg_displacement_indices]
        
        # 5. Détecter les OB
        obs = self.detect_order_blocks(df_struct, displacements, fvgs)
        
        # 6. Détecter les BOS/CHoCH
        bos_choch = self.detect_bos_choch(df_struct, swings)
        
        # 7. Détecter les liquidity sweeps
        sweeps = self.detect_liquidity_sweeps(df_struct, swings)
        
        # 8. Compiler le rapport
        bias = self._determine_bias(bos_choch, swings)
        
        return {
            "symbol": self.symbol,
            "structure_tf": self.structure_tf,
            "entry_tf": self.entry_tf,
            "timestamp": datetime.now().isoformat(),
            "swings": swings,
            "displacements": displacements,
            "fvg": fvgs,
            "order_blocks": obs,
            "bos_choch": bos_choch,
            "liquidity_sweeps": sweeps,
            "bias": bias
        }

    def detect_mss(self, df: pd.DataFrame, swings: list, displacements: list, 
                   fvgs: list, bos_choch: list) -> list[dict]:
        """
        MSS = BOS/CHoCH + Displacement + FVG créé, tous dans le même mouvement.
        """
        mss_events = []
        df_times = df['time'].dt.strftime('%Y-%m-%d %H:%M').values
        
        fvg_disp_indices = set(f['displacement_index'] for f in fvgs)
        
        for event in bos_choch:
            event_idx = event['index']
            # Chercher un displacement proche (±2 bougies de la cassure)
            close_displacements = [d for d in displacements if abs(d['index'] - event_idx) <= 2]
            
            for d in close_displacements:
                d_idx = d['index']
                if d_idx in fvg_disp_indices:
                    # Trouver le FVG correspondant
                    fvg_idx = next((f['index'] for f in fvgs if f['displacement_index'] == d_idx), d_idx + 1)
                    
                    is_bullish = 'bullish' in event['type']
                    mss_type = "bullish_mss" if is_bullish else "bearish_mss"
                    
                    mss_events.append({
                        "type": mss_type,
                        "bos_index": event_idx,
                        "displacement_index": d_idx,
                        "fvg_index": fvg_idx,
                        "broken_level": event['broken_level'],
                        "confidence": "high",
                        "time": df_times[event_idx]
                    })
                    break # Un seul MSS pour cet event
                    
        return mss_events

    def detect_equal_levels(self, swings: list[dict], tolerance_pips: float = 3.0, 
                             pip_value: float = 0.0001) -> list[dict]:
        """
        Détecte les swing highs/lows qui sont au même niveau (± tolérance).
        """
        equal_levels = []
        tolerance = tolerance_pips * pip_value
        
        highs = [s for s in swings if s['type'] == 'swing_high']
        lows = [s for s in swings if s['type'] == 'swing_low']
        
        def group_swings(swing_list, level_type, liquidity_type):
            groups = [] # liste de dicts {price_avg, swings: []}
            for s in swing_list:
                matched = False
                for g in groups:
                    if abs(s['price'] - g['price_avg']) <= tolerance:
                        g['swings'].append(s)
                        # Recalculer la moyenne
                        g['price_avg'] = sum(x['price'] for x in g['swings']) / len(g['swings'])
                        matched = True
                        break
                if not matched:
                    groups.append({'price_avg': s['price'], 'swings': [s]})
            
            for g in groups:
                count = len(g['swings'])
                if count >= 2:
                    strength = "strong" if count >= 3 else "moderate"
                    equal_levels.append({
                        "type": level_type,
                        "level": round(g['price_avg'], 5),
                        "count": count,
                        "indices": [x['index'] for x in g['swings']],
                        "strength": strength,
                        "liquidity_type": liquidity_type
                    })
                    
        group_swings(highs, "EQH", "buyside")
        group_swings(lows, "EQL", "sellside")
        return equal_levels

    def detect_key_levels(self, df_daily: pd.DataFrame, df_weekly: pd.DataFrame = None,
                           df_monthly: pd.DataFrame = None) -> dict:
        """
        Identifie les niveaux clés institutionnels.
        """
        levels = {}
        
        if df_daily is not None and len(df_daily) >= 2:
            # Avant-dernière bougie = yesterday (index -2) si le marché est ouvert aujourd'hui
            prev_day = df_daily.iloc[-2]
            levels["PDH"] = float(prev_day['high'])
            levels["PDL"] = float(prev_day['low'])
            
        if df_weekly is not None and len(df_weekly) >= 2:
            prev_week = df_weekly.iloc[-2]
            levels["PWH"] = float(prev_week['high'])
            levels["PWL"] = float(prev_week['low'])
            
        if df_monthly is not None and len(df_monthly) >= 2:
            prev_month = df_monthly.iloc[-2]
            levels["PMH"] = float(prev_month['high'])
            levels["PML"] = float(prev_month['low'])
            
        return levels

    def analyze_multi_tf(self, dataframes: dict[str, pd.DataFrame]) -> dict:
        """
        Analyse plusieurs timeframes et retourne un rapport hiérarchique.
        """
        report = {}
        biases = {}
        
        for tf, df_tf in dataframes.items():
            if df_tf is None or len(df_tf) == 0:
                continue
                
            swings = self.detect_swing_points(df_tf)
            displacements = self.detect_displacement(df_tf, swings)
            fvgs = self.detect_fvg(df_tf)
            
            fvg_disp_indices = set(f['displacement_index'] for f in fvgs)
            valid_disps = [d for d in displacements if d['index'] in fvg_disp_indices]
            
            eq_levels = self.detect_equal_levels(swings)
            obs = self.detect_order_blocks(df_tf, valid_disps, fvgs, equal_levels=eq_levels)
            bos_choch = self.detect_bos_choch(df_tf, swings)
            sweeps = self.detect_liquidity_sweeps(df_tf, swings)
            mss = self.detect_mss(df_tf, swings, valid_disps, fvgs, bos_choch)
            
            bias = self._determine_bias(bos_choch, swings)
            last_event = bos_choch[-1]['type'] if bos_choch else "none"
            
            report[tf] = {
                "bias": bias,
                "swings": swings,
                "fvg": fvgs,
                "bos_choch": bos_choch,
                "last_bos_type": last_event,
                "mss": mss,
                "equal_levels": eq_levels,
                "order_blocks": obs,
                "liquidity_sweeps": sweeps,
                "displacements": valid_disps
            }
            biases[tf] = bias
            
        # Vote majoritaire pour HTF alignment (indépendant des TFs hardcodés)
        bias_counts = {}
        for tf_key, tf_data in report.items():
            if isinstance(tf_data, dict) and "bias" in tf_data:
                b = tf_data["bias"]
                if b in ("bullish", "bearish"):
                    bias_counts[b] = bias_counts.get(b, 0) + 1

        total_tfs = sum(bias_counts.values())
        if total_tfs == 0:
            htf_alignment = "unknown"
            modifier = 0.5
        elif len(bias_counts) == 1:
            # Tous les TFs avec un biais s'accordent
            htf_alignment = list(bias_counts.keys())[0]
            modifier = 1.0
        else:
            dominant = max(bias_counts, key=bias_counts.get)
            if bias_counts[dominant] >= 2:
                # Majorité (2/3 ou plus) → on prend le biais dominant
                htf_alignment = dominant
                modifier = 0.85
            else:
                # Parfaite égalité (ex: 1 bullish / 1 bearish)
                htf_alignment = "conflicting"
                modifier = 0.0

        report["htf_alignment"] = htf_alignment
        report["htf_alignment_detail"] = biases
        report["htf_confidence_modifier"] = modifier
        
        return report

def is_first_presented_fvg(fvg_list: list, current_fvg: dict, bias: str) -> bool:
    """
    Retourne True si current_fvg est le PREMIER FVG apparu après 09h29 NY
    (= 14h29 UTC, "HH:MM" dans fvg['time']) dans la direction du biais HTF.
    """
    NY_OPEN_TIME = "14:29"  # 09h29 NY = 14h29 UTC

    def matches_bias(fvg, bias):
        if bias == "bullish":
            return fvg.get("type") == "bullish_fvg"
        if bias == "bearish":
            return fvg.get("type") == "bearish_fvg"
        return False

    if not matches_bias(current_fvg, bias):
        return False

    # Filtrer les FVGs dans la bonne direction, apparus à 14:29 UTC ou après
    candidates = [
        f for f in fvg_list
        if matches_bias(f, bias) and len(f.get("time", "")) >= 5 and f.get("time", "")[-5:] >= NY_OPEN_TIME
    ]

    if not candidates:
        return False

    # Trier chronologiquement selon le champ 'time'
    candidates_sorted = sorted(candidates, key=lambda x: x.get("time", ""))

    # Le current_fvg est-il le premier ?
    first_fvg_time = candidates_sorted[0].get("time")
    current_time = current_fvg.get("time")
    
    return first_fvg_time == current_time and current_time is not None

def detect_cisd(candles: list, bias: str) -> dict:
    """
    Règle P-B2 : Détecte un CISD (Change In State of Delivery) sur les dernières bougies.
    Condition : Le corps de la bougie actuelle est plus grand que les corps des 2 bougies précédentes
    ET elle clôture dans la direction du biais HTF.
    """
    if len(candles) < 3:
        return {'detected': False, 'direction': 'none', 'strength': 0.0}
        
    c0 = candles[-1] # Actuelle
    c1 = candles[-2] # Précédente
    c2 = candles[-3] # Encore avant
    
    # Calcul des corps (valeur absolue)
    body0 = abs(c0['close'] - c0['open'])
    body1 = abs(c1['close'] - c1['open'])
    body2 = abs(c2['close'] - c2['open'])
    
    # Direction de la bougie actuelle
    c0_dir = "bullish" if c0['close'] > c0['open'] else "bearish" if c0['close'] < c0['open'] else "neutral"
    
    # Vérification des conditions
    is_engulfing_body = body0 > body1 and body0 > body2
    matches_bias = c0_dir == bias
    
    if is_engulfing_body and matches_bias:
        # Mesure de la force (ratio du corps par rapport à la moyenne des 2 précédents)
        avg_prev_body = (body1 + body2) / 2.0
        strength = body0 / avg_prev_body if avg_prev_body > 0 else 99.0
        return {'detected': True, 'direction': c0_dir, 'strength': strength}
        
    return {'detected': False, 'direction': 'none', 'strength': 0.0}
