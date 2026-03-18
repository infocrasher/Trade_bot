import json
import os
from typing import Dict, Any
import pandas as pd

from agents.ict.structure import StructureAgent
from agents.calibration_multi_profils import PROFILE_TTL_SECONDS
from agents.gate_logger import log_pure_pa_blocked

class PurePAOrchestrator:
    """
    Agent Pure Price Action.
    Profile ID: pure_pa
    
    Règles :
    1. MSS confirmé : BOS + displacement (via agents/ict/structure.py)
    2. FVG frais dans la direction du MSS
    3. R:R minimum 1.5 (configurable via data/profiles/settings.json)
    4. Killzones : toggle via settings.json (si actif, applique les KZ, sinon ignore)
    5. Pas de score minimum — exécute dès que 1, 2, 3 sont alignés
    """
    def __init__(self, symbol: str, timeframe: str = "M5"):
        self.symbol = symbol
        self.timeframe = timeframe
        self.profile_id = "pure_pa"
        self.ttl = PROFILE_TTL_SECONDS.get("pure_pa", 1800)
        self.settings_path = "data/profiles/settings.json"

    def load_settings(self) -> dict:
        default_settings = {
            "pure_pa": {
                "min_rr": 1.0,
                "use_killzones": False
            }
        }
        if os.path.exists(self.settings_path):
            try:
                with open(self.settings_path, "r") as f:
                    data = json.load(f)
                    if "pure_pa" in data:
                        return data["pure_pa"]
            except Exception:
                pass
        return default_settings["pure_pa"]

    def _no_trade(self, reason: str, entry: float = 0.0, sl: float = 0.0, tp: float = 0.0, rr: float = 0.0) -> dict:
        log_pure_pa_blocked(
            pair=self.symbol,
            horizon=self.timeframe,
            reason=reason,
            entry=entry,
            sl=sl,
            tp=tp,
            rr=rr
        )
        return {
            "action": "NO_TRADE",
            "direction": "neutral",
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "score": 0.0,
            "profile_id": self.profile_id,
            "ttl_seconds": 0,
            "active_gates": [],
            "rationale": reason
        }

    def _calc_atr(self, df, period: int = 14) -> float:
        if len(df) < period + 1:
            return float((df["high"] - df["low"]).mean())
        tr = pd.concat([
            df["high"] - df["low"],
            (df["high"] - df["close"].shift()).abs(),
            (df["low"]  - df["close"].shift()).abs(),
        ], axis=1).max(axis=1)
        return float(tr.tail(period).mean())

    def _get_price_threshold(self) -> float:
        """Retourne le seuil de cohérence de prix selon l'actif."""
        forex_pairs = ["EURUSD", "GBPUSD", "USDJPY", "USDCAD", "USDCHF", "EURGBP", 
                       "AUDUSD", "NZDUSD", "EURJPY", "GBPJPY", "AUDJPY"]
        if self.symbol in forex_pairs:
            return 0.02  # 2% pour le Forex
        if self.symbol == "XAUUSD":
            return 0.03  # 3% pour l'Or
        if self.symbol in ["BTCUSD", "ETHUSD"]:
            return 0.05  # 5% pour la Crypto
        return 0.05      # 5% par défaut

    def evaluate(self, df: pd.DataFrame, time_report: dict = None) -> dict:
        settings = self.load_settings()
        min_rr = settings.get("min_rr", 1.0)
        use_kz = settings.get("use_killzones", False)
        
        active_gates = []
        
        # 1. Killzones Check
        # Si activé, on demande que Agent 2 (time) autorise le trade.
        if use_kz:
            active_gates.append("killzones_enabled")
            if time_report and not time_report.get("can_trade", True):
                return self._no_trade("Hors Killzone (Killzones activées)")

        # 2. Structure Analysis (MSS)
        sa = StructureAgent(self.symbol, structure_tf=self.timeframe, entry_tf=self.timeframe)
        swings = sa.detect_swing_points(df)
        displacements = sa.detect_displacement(df, swings)
        fvgs = sa.detect_fvg(df)
        
        # Filtrer les déplacements pertinents pour le FVG
        fvg_disp_indices = set(f['displacement_index'] for f in fvgs)
        valid_disps = [d for d in displacements if d['index'] in fvg_disp_indices]
        
        bos_choch = sa.detect_bos_choch(df, swings)
        mss_events = sa.detect_mss(df, swings, valid_disps, fvgs, bos_choch)
        
        if not mss_events:
            return self._no_trade("Pas de MSS détecté")
            
        last_mss = mss_events[-1]
        is_bullish = "bullish" in last_mss["type"]
        direction = "buy" if is_bullish else "sell"
        
        # 3. FVG Frais dans la direction du MSS
        fresh_fvgs = []
        for f in fvgs:
            if f["status"] in ["open", "partially_filled"]:
                if is_bullish and f["type"] == "bullish_fvg":
                    if f["index"] >= last_mss["bos_index"] or f["displacement_index"] == last_mss["displacement_index"]:
                        fresh_fvgs.append(f)
                elif not is_bullish and f["type"] == "bearish_fvg":
                    if f["index"] >= last_mss["bos_index"] or f["displacement_index"] == last_mss["displacement_index"]:
                        fresh_fvgs.append(f)
                        
        if not fresh_fvgs:
            return self._no_trade("Pas de FVG frais valide dans la direction du MSS")
            
        target_fvg = fresh_fvgs[-1]  # Le plus récent
        
        # 4. R:R Calculation & ATR Margin (Correction 2)
        atr = self._calc_atr(df, 14)
        
        # Entry dans le FVG
        entry = target_fvg["top"] if is_bullish else target_fvg["bottom"]
        
        # Guard de cohérence de prix (PRIX_ABERRANT)
        last_close = float(df["close"].iloc[-1])
        if last_close > 0:
            ecart_pct = abs(entry - last_close) / last_close
            threshold = self._get_price_threshold()
            if ecart_pct > threshold:
                return self._no_trade(f"PRIX_ABERRANT — écart {ecart_pct * 100:.1f}% vs dernier close (seuil {threshold*100:.0f}%)", entry=entry)

        # SL initial en dessous (ou au-dessus) du FVG
        sl_initial = target_fvg["bottom"] if is_bullish else target_fvg["top"]
        
        # Appliquer la marge minimale de 1x ATR
        dist_initial = abs(entry - sl_initial)
        sl = sl_initial
        
        if dist_initial < atr:
            sl = entry - atr if is_bullish else entry + atr
            # log(f"[{self.symbol}] SL ajusté pour marge ATR (dist initial {dist_initial:.5f} < ATR {atr:.5f})", "DEBUG")
        
        # Buffer de sécurité pour éviter div/0
        if abs(entry - sl) < 1e-6:
            sl = sl - 0.0001 if is_bullish else sl + 0.0001

        # Trouver le swing le plus proche dans la direction opposée pour le TP
        tp = None
        if is_bullish:
            highs = [s["price"] for s in swings if s["type"] == "swing_high" and s["price"] > entry]
            if highs:
                tp = min(highs)
            else:
                tp = entry + (entry - sl) * max(min_rr, 1.5)
        else:
            lows = [s["price"] for s in swings if s["type"] == "swing_low" and s["price"] < entry]
            if lows:
                tp = max(lows)
            else:
                tp = entry - (sl - entry) * max(min_rr, 1.5)
                
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        rr = reward / risk if risk > 0 else 0
        
        active_gates.append(f"rr_{min_rr}")
        if dist_initial < atr:
            active_gates.append("atr_sl_margin")
        
        if rr < min_rr:
            reason = f"R:R insuffisant ({rr:.2f} < {min_rr})"
            if dist_initial < atr:
                reason = f"SL trop serré — marge ATR insuffisante (R:R {rr:.2f} < {min_rr})"
            return self._no_trade(reason, entry, sl, tp, rr)
            
        # 5. ALL GOOD!
        return {
            "action": "new",
            "direction": direction,
            "entry": float(round(entry, 5)),
            "sl": float(round(sl, 5)),
            "tp": float(round(tp, 5)),
            "score": 100.0,
            "profile_id": self.profile_id,
            "ttl_seconds": self.ttl,
            "active_gates": active_gates,
            "rationale": f"MSS {direction} avec FVG frais. R:R = {rr:.2f}."
        }
