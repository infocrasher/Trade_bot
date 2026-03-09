import pandas as pd
from datetime import datetime

# Mapping des paires et leurs relations avec le USD
PAIR_USD_RELATION = {
    "EURUSD": "usd_quote",    # USD est la devise de cotation → DXY inverse
    "GBPUSD": "usd_quote",
    "AUDUSD": "usd_quote",
    "NZDUSD": "usd_quote",
    "USDJPY": "usd_base",     # USD est la devise de base → DXY direct
    "USDCAD": "usd_base",
    "USDCHF": "usd_base",
    "EURJPY": "no_usd",       # Pas de USD direct
    "GBPJPY": "no_usd",
    "EURGBP": "no_usd",
    "XAUUSD": "inverse",      # Or : corrélation inverse avec USD
    "USOIL": "inverse",       # Pétrole : corrélation inverse modérée
    "US100": "weak",           # Indices : corrélation faible/variable
    "US500": "weak",
}

# Paires corrélées pour SMT
SMT_PAIRS = {
    "EURUSD": [("GBPUSD", "positive"), ("DXY", "negative")],
    "GBPUSD": [("EURUSD", "positive"), ("DXY", "negative")],
    "USDJPY": [("USDCAD", "positive"), ("DXY", "positive")],
    "AUDUSD": [("NZDUSD", "positive"), ("DXY", "negative")],
    "NZDUSD": [("AUDUSD", "positive"), ("DXY", "negative")],
    "USDCAD": [("USDJPY", "positive"), ("DXY", "positive")],
    "USDCHF": [("USDJPY", "positive"), ("DXY", "positive")],
    "XAUUSD": [("DXY", "negative")],
    "US100":  [("US500", "positive")],
    "US500":  [("US100", "positive")],
}


class MacroBiasAgent:
    def __init__(self, target_pair: str):
        """
        target_pair : la paire sur laquelle on trade (ex: "EURUSD")
        """
        self.target_pair = target_pair
        self.usd_relation = PAIR_USD_RELATION.get(target_pair, "unknown")
        self.smt_correlated = SMT_PAIRS.get(target_pair, [])
        
    def analyze_cot(self, cot_data: dict) -> dict:
        """
        Analyse le positionnement institutionnel via les données COT.
        """
        if not cot_data:
            return {"cot_bias": "neutral", "confidence": 0.0, "details": "No COT data"}
            
        nc_net = cot_data.get("non_commercial_net", 0)
        prev_nc_net = cot_data.get("previous_non_commercial_net", 0)
        c_net = cot_data.get("commercial_net", 0)
        oi = cot_data.get("open_interest", 1) # Evite devision par 0
        
        net_change = nc_net - prev_nc_net
        net_change_direction = "flat"
        cot_bias = "neutral"
        
        if net_change > 0:
            net_change_direction = "increasing_longs"
            cot_bias = "bullish"
        elif net_change < 0:
            net_change_direction = "increasing_shorts"
            cot_bias = "bearish"
            
        positioning_ratio = abs(nc_net) / float(oi)
        positioning_level = "normal"
        if positioning_ratio > 0.40:
            positioning_level = "extreme"
        elif positioning_ratio > 0.20:
             positioning_level = "elevated"
             
        comm_div = False
        comm_div_signal = "neutral"
        
        if c_net < 0 and nc_net > 0:
             comm_div = True
             comm_div_signal = "bearish"
        elif c_net > 0 and nc_net < 0:
             comm_div = True
             comm_div_signal = "bullish"
             
        confidence = 0.50
        if comm_div: confidence += 0.15
        if positioning_level == "extreme": confidence -= 0.10 # Reversal risk
        
        details = f"Speculators {net_change_direction} ({net_change}), pos {positioning_level}, comm_div {comm_div_signal}"
        
        return {
            "cot_bias": cot_bias,
            "net_change": net_change,
            "net_change_direction": net_change_direction,
            "positioning_level": positioning_level,
            "commercial_divergence": comm_div,
            "commercial_divergence_signal": comm_div_signal,
            "confidence": min(1.0, max(0.0, confidence)),
            "details": details
        }

    def analyze_smt(self, primary_data: dict, correlated_data: dict, correlation_type: str = "positive") -> dict:
        """
        Détecte les divergences SMT entre deux marchés corrélés.
        """
        if not primary_data or not correlated_data:
             return {"smt_detected": False, "smt_type": None, "confidence": 0.0}
             
        p_new_high = primary_data.get("made_new_high", False)
        p_new_low = primary_data.get("made_new_low", False)
        
        c_new_high = correlated_data.get("made_new_high", False)
        c_new_low = correlated_data.get("made_new_low", False)
        
        smt_detected = False
        smt_type = None
        detail = ""
        
        if correlation_type == "positive":
            if p_new_high and not c_new_high:
                 smt_detected = True
                 smt_type = "bearish_smt"
                 detail = f"{primary_data.get('symbol')} made new high but {correlated_data.get('symbol')} did not"
            elif p_new_low and not c_new_low:
                 smt_detected = True
                 smt_type = "bullish_smt"
                 detail = f"{primary_data.get('symbol')} made new low but {correlated_data.get('symbol')} did not"
        elif correlation_type == "negative":
             if p_new_high and c_new_high:
                 smt_detected = True
                 smt_type = "bearish_smt"
                 detail = f"{primary_data.get('symbol')} made new high and {correlated_data.get('symbol')} also made new high"
             elif p_new_low and c_new_low:
                 smt_detected = True
                 smt_type = "bullish_smt"
                 detail = f"{primary_data.get('symbol')} made new low and {correlated_data.get('symbol')} also made new low"
                 
        return {
            "smt_detected": smt_detected,
            "smt_type": smt_type,
            "primary_symbol": primary_data.get("symbol"),
            "correlated_symbol": correlated_data.get("symbol"),
            "divergence_detail": detail,
            "confidence": 0.70 if smt_detected else 0.0
        }

    def analyze_dxy(self, dxy_data: dict, target_pair: str) -> dict:
        """
        Analyse le DXY pour déterminer le biais directionnel de la target_pair.
        """
        if not dxy_data:
             return {"dxy_bias_for_pair": "neutral", "correlation_strength": "none", "confidence": 0.0}
             
        dxy_bias = dxy_data.get("bias", "neutral")
        dxy_trend = dxy_data.get("trend", "ranging")
        
        relation = self.usd_relation
        pair_bias = "neutral"
        strength = "weak"
        
        if relation == "usd_base":
             pair_bias = dxy_bias
             strength = "strong"
        elif relation == "usd_quote" or relation == "inverse":
             pair_bias = "bearish" if dxy_bias == "bullish" else "bullish" if dxy_bias == "bearish" else "neutral"
             strength = "strong" if relation == "usd_quote" else "moderate"
        elif relation == "no_usd":
             pair_bias = "neutral"
             strength = "weak"
             
        conf_map = {"strong": 0.75, "moderate": 0.50, "weak": 0.20, "none": 0.0}
        
        return {
            "dxy_bias_for_pair": pair_bias,
            "dxy_trend": dxy_trend,
            "correlation_strength": strength,
            "confidence": conf_map.get(strength, 0.0),
            "detail": f"DXY {dxy_bias} → {target_pair} {pair_bias} ({relation})"
        }

    def analyze_news_calendar(self, upcoming_news: list[dict], current_time_str: str) -> dict:
        """
        Vérifie si des news danger/volatiles arrivent ou viennent de passer.
        """
        if not upcoming_news or not current_time_str:
            return {"news_status": "clear", "relevant_news_count": 0, "can_trade": True}
            
        current_dt = datetime.strptime(current_time_str, "%Y-%m-%d %H:%M")
        
        # Identifier les devises pertinentes pour filter
        # Si target = EURUSD -> pertinents : EUR, USD
        pertinent_currencies = ["USD"] # USD affecte presque tout
        if len(self.target_pair) == 6:
             pertinent_currencies.append(self.target_pair[:3])
             pertinent_currencies.append(self.target_pair[3:])

        status = "clear"
        nearest_high = None
        relevant_count = 0
        detail = "Clear"
        
        for news in upcoming_news:
            if news.get("currency") not in pertinent_currencies:
                 continue
                 
            news_dt = datetime.strptime(news["time"], "%Y-%m-%d %H:%M")
            delta_min = (news_dt - current_dt).total_seconds() / 60.0
            
            # On ne regarde que la fenêtre -15 à +120 minutes
            if -15 <= delta_min <= 120:
                relevant_count += 1
                
                if news.get("impact") == "high":
                    if nearest_high is None or abs(delta_min) < abs((datetime.strptime(nearest_high["time"], "%Y-%m-%d %H:%M") - current_dt).total_seconds()/60):
                        nearest_high = news.copy()
                        nearest_high["minutes_until"] = int(delta_min)
                        
                    if 0 <= delta_min <= 30:
                        status = "danger"
                        detail = f"{news.get('currency')} {news.get('event')} in {int(delta_min)} min (DANGER)"
                    elif 30 < delta_min <= 60 and status != "danger":
                        status = "caution"
                        if detail == "Clear": detail = f"Caution: {news.get('event')} in {int(delta_min)} min"
                    elif -15 <= delta_min < 0 and status != "danger":
                        status = "volatile"
                        if detail == "Clear": detail = f"Volatile: {news.get('event')} passed {int(abs(delta_min))} min ago"
                        
                elif news.get("impact") == "medium" and 0 <= delta_min <= 15 and status == "clear":
                     status = "caution"
                     detail = f"Medium impact news in {int(delta_min)} min"
                     
        return {
            "news_status": status,
            "nearest_high_impact": nearest_high,
            "relevant_news_count": relevant_count,
            "can_trade": status != "danger",
            "detail": detail
        }

    def synthesize_macro_bias(self, cot_result: dict, smt_result: dict, dxy_result: dict, news_result: dict) -> dict:
        """
        Fusionne les 4 analyses en un consensus macro directionnel.
        """
        news_status = news_result.get("news_status", "clear") if news_result else "clear"
        
        if news_status == "danger":
            return {
                "macro_bias": "no_trade",
                "bullish_score": 0.0,
                "bearish_score": 0.0,
                "confidence": 0.0,
                "news_status": "danger",
                "can_trade": False,
                "details": ["News: DANGER (High impact)"]
            }
            
        bull_score = 0.0
        bear_score = 0.0
        details = []
        
        # 1. COT Bias (Weight = 0.25)
        if cot_result:
            w = 0.25 * cot_result.get("confidence", 0)
            cot_bias = cot_result.get("cot_bias", "neutral")
            if cot_bias == "bullish": bull_score += w
            elif cot_bias == "bearish": bear_score += w
            details.append(f"COT: {cot_result.get('details')}")
            
        # 2. SMT Bias (Weight = 0.30)
        if smt_result and smt_result.get("smt_detected"):
             w = 0.30 * smt_result.get("confidence", 0)
             smt_t = smt_result.get("smt_type")
             if smt_t == "bullish_smt": bull_score += w
             elif smt_t == "bearish_smt": bear_score += w
             details.append(f"SMT: {smt_result.get('divergence_detail')}")
             
        # 3. DXY Bias (Weight = 0.25)
        if dxy_result:
             w = 0.25 * dxy_result.get("confidence", 0)
             d_bias = dxy_result.get("dxy_bias_for_pair", "neutral")
             if d_bias == "bullish": bull_score += w
             elif d_bias == "bearish": bear_score += w
             details.append(f"DXY: {dxy_result.get('detail')}")
             
             
        macro_bias = "neutral"
        if bull_score > bear_score * 1.2 and bull_score > 0.10: # threshold to avoid random low conf noise
            macro_bias = "bullish"
        elif bear_score > bull_score * 1.2 and bear_score > 0.10:
            macro_bias = "bearish"
            
        # Overall Confidence
        total_valid_weight = 0.80 # Max 0.25 + 0.30 + 0.25
        confidence = max(bull_score, bear_score) / total_valid_weight if total_valid_weight > 0 else 0
        
        if news_status == "caution":
            confidence *= 0.80
            details.append("News: Caution - confidence reduced")
            
        return {
            "macro_bias": macro_bias,
            "bullish_score": round(bull_score, 3),
            "bearish_score": round(bear_score, 3),
            "confidence": round(min(1.0, confidence), 2),
            "cot_signal": cot_result.get("cot_bias") if cot_result else None,
            "smt_signal": smt_result.get("smt_type") if smt_result else None,
            "dxy_signal": dxy_result.get("dxy_bias_for_pair") if dxy_result else None,
            "news_status": news_status,
            "can_trade": True,
            "details": details
        }

    def analyze(self, cot_data: dict = None, smt_data: dict = None, 
                dxy_data: dict = None, news_data: list[dict] = None, 
                current_time: str = None) -> dict:
        """
        Wrapper global pour l'analyse
        """
        # COT
        cot_res = self.analyze_cot(cot_data) if cot_data is not None else None
        
        # SMT
        smt_res = None
        if smt_data and "primary" in smt_data and "correlated" in smt_data:
            smt_res = self.analyze_smt(smt_data["primary"], smt_data["correlated"], smt_data.get("correlation_type", "positive"))
            
        # DXY
        dxy_res = self.analyze_dxy(dxy_data, self.target_pair) if dxy_data is not None else None
        
        # News
        news_res = self.analyze_news_calendar(news_data, current_time) if news_data is not None else None
        
        return self.synthesize_macro_bias(cot_res, smt_res, dxy_res, news_res)

    def analyze_ipda_ranges(self, df_daily: pd.DataFrame) -> dict:
        """
        Identifie les cibles de l'algorithme IPDA (20, 40, 60 jours).
        """
        if df_daily is None or len(df_daily) < 60:
            return {}
            
        # Prendre au maximum les 60 derniers jours
        df_60 = df_daily.tail(60)
        df_40 = df_daily.tail(40)
        df_20 = df_daily.tail(20)
        
        range_20 = {"high": float(df_20['high'].max()), "low": float(df_20['low'].min()), "days": 20}
        range_40 = {"high": float(df_40['high'].max()), "low": float(df_40['low'].min()), "days": 40}
        range_60 = {"high": float(df_60['high'].max()), "low": float(df_60['low'].min()), "days": 60}
        
        current_price = float(df_daily.iloc[-1]['close'])
        
        targets_above = [t for t in [range_20["high"], range_40["high"], range_60["high"]] if t > current_price]
        targets_below = [t for t in [range_20["low"], range_40["low"], range_60["low"]] if t < current_price]
        
        nearest_target_above = min(targets_above) if targets_above else None
        nearest_target_below = max(targets_below) if targets_below else None
        
        return {
            "range_20": range_20,
            "range_40": range_40,
            "range_60": range_60,
            "nearest_target_above": nearest_target_above,
            "nearest_target_below": nearest_target_below
        }

    def get_quarterly_context(self, current_date: str) -> dict:
        """
        Identifie le trimestre et le contexte saisonnier.
        """
        from datetime import datetime
        if isinstance(current_date, str):
            dt = datetime.strptime(current_date, "%Y-%m-%d %H:%M")
        else:
            dt = current_date
            
        q = (dt.month - 1) // 3 + 1
        
        quarter = f"Q{q}"
        year = dt.year
        
        start_month = (q - 1) * 3 + 1
        start_date = f"{year}-{start_month:02d}-01"
        
        seasonality = {
            "Q1": {"usd": "bullish", "eurusd": "bearish", "detail": "Q1: USD typically strong (risk-off, new year flows)"},
            "Q2": {"usd": "neutral", "eurusd": "neutral", "detail": "Q2: Transitional quarter, mixed flows"},
            "Q3": {"usd": "bearish", "eurusd": "bullish", "detail": "Q3: USD typically weak (summer doldrums, risk-on)"},
            "Q4": {"usd": "bullish", "eurusd": "bearish", "detail": "Q4: USD safe haven flows, year-end repatriation"}
        }
        
        bias_usd = seasonality[quarter]["usd"]
        bias_eurusd = seasonality[quarter]["eurusd"]
        detail = seasonality[quarter]["detail"]
        
        return {
            "quarter": quarter,
            "quarter_start": start_date,
            "seasonal_bias_usd": bias_usd,
            "seasonal_bias_eurusd": bias_eurusd,
            "detail": detail
        }
