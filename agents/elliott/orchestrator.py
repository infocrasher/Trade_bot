"""
Elliott Wave Orchestrator
==========================
Orchestre le pipeline complet :
1. Détection des pivots (wave_counter)
2. Identification des impulsions et corrections
3. Validation des règles (rules_validator)
4. Scoring (scorer)
5. Génération du signal
"""

import sys
import os
import pandas as pd
from typing import Dict, List, Optional

from .wave_counter import (
    detect_pivots, count_waves, detect_current_wave_position,
    WaveCount, WaveType, WaveDirection, PARAMS
)
from .rules_validator import validate_absolute_rules, validate_correction_rules, check_guidelines
from .scorer import score_wave_count


class ElliottOrchestrator:
    """
    Agent Elliott Wave — retourne un signal au format standard multi-école.
    """
    
    def __init__(self):
        self.min_score = PARAMS["MIN_SCORE_TO_TRADE"]
    
    def analyze(self, dataframes: Dict[str, pd.DataFrame], 
                pair: str = "", 
                timeframe: str = "H4") -> Dict:
        """
        Analyse les données et retourne un signal Elliott Wave.
        
        Args:
            dataframes: Dict de DataFrames par timeframe {"H4": df, "D1": df, ...}
            pair: Nom de la paire (ex: "EURUSD")
            timeframe: Timeframe principal d'analyse
        
        Returns:
            Signal au format standard multi-école :
            {
                "school": "elliott",
                "pair": "EURUSD",
                "signal": "BUY" / "SELL" / "NO_TRADE",
                "score": 0-100,
                "confidence": 0.0-1.0,
                "entry": prix,
                "sl": prix,
                "tp1": prix,
                "reasons": ["..."],
                "warnings": ["..."],
                "details": {...}
            }
        """
        result = {
            "school": "elliott",
            "pair": pair,
            "signal": "NO_TRADE",
            "score": 0,
            "confidence": 0.0,
            "entry": 0,
            "sl": 0,
            "tp1": 0,
            "reasons": [],
            "warnings": [],
            "details": {},
        }
        
        # Obtenir le DataFrame principal
        df = dataframes.get(timeframe)
        if df is None:
            # Essayer les timeframes disponibles
            for tf in ["H4", "D1", "H1", "W1"]:
                if tf in dataframes:
                    df = dataframes[tf]
                    timeframe = tf
                    break
        
        if df is None or len(df) < 50:
            result["reasons"].append("Données insuffisantes pour l'analyse Elliott")
            return result
        
        try:
            # ═══ ÉTAPE 1 : Détection des pivots et comptage ═══
            position = detect_current_wave_position(df)
            
            result["details"]["position"] = {
                "status": position.get("status", "unknown"),
                "direction": position.get("direction", "unknown"),
                "current_wave": position.get("current_wave"),
                "next_expected": position.get("next_expected"),
            }
            
            # ═══ ÉTAPE 2 : Scorer les meilleurs comptages ═══
            best_impulse = position.get("best_impulse")
            best_correction = position.get("best_correction")
            
            scored_counts = []
            
            if best_impulse:
                scored_impulse = score_wave_count(best_impulse)
                scored_counts.append(scored_impulse)
                result["details"]["impulse_score"] = scored_impulse.score
                result["details"]["impulse_valid"] = scored_impulse.valid
                if scored_impulse.invalidation_reasons:
                    result["warnings"].extend(scored_impulse.invalidation_reasons)
            
            if best_correction:
                scored_correction = score_wave_count(best_correction)
                scored_counts.append(scored_correction)
                result["details"]["correction_score"] = scored_correction.score
                result["details"]["correction_valid"] = scored_correction.valid
                if scored_correction.invalidation_reasons:
                    result["warnings"].extend(scored_correction.invalidation_reasons)
            
            # ═══ ÉTAPE 3 : Prendre le meilleur comptage valide ═══
            valid_counts = [wc for wc in scored_counts if wc.valid and wc.score > 0]
            
            if not valid_counts:
                result["reasons"].append("Aucun comptage Elliott valide trouvé")
                return result
            
            # Trier par score
            valid_counts.sort(key=lambda wc: wc.score, reverse=True)
            best = valid_counts[0]
            
            # ═══ ÉTAPE 4 : Score final = score du scorer + bonus position ═══
            trade_signal = position.get("trade_signal", "NO_TRADE")
            position_confidence = position.get("confidence", 0)
            
            # Le score du scorer v2.0 EST le score de base
            # Le positionnement ajoute un bonus/malus léger
            # (remplace l'ancien mixage 60/40 qui diluait le score)
            base_score = int(best.score)
            
            # Bonus position : début de W3 = +15, début de W5 = +5, etc.
            position_bonus = 0
            status = position.get("status", "")
            if "w3_start" in status:
                position_bonus = 15  # Meilleur trade Elliott
            elif "w5_start" in status:
                position_bonus = 5   # Trade acceptable mais W5 = dernière vague
            elif "correction_complete" in status:
                position_bonus = 10  # Reprise de tendance
            elif "impulse_complete" in status:
                position_bonus = 5   # Attente de correction
            
            final_score = max(0, min(100, base_score + position_bonus))
            result["score"] = final_score
            result["confidence"] = round(final_score / 100.0, 2)
            
            if final_score >= self.min_score and trade_signal != "NO_TRADE":
                result["signal"] = trade_signal
                
                # Calculer entry, SL, TP1
                self._calculate_levels(result, position, best, df)
                
                # Raisons
                result["reasons"] = self._build_reasons(position, best)
            else:
                result["signal"] = "NO_TRADE"
                if final_score < self.min_score:
                    result["reasons"].append(
                        f"Score insuffisant ({final_score} < {self.min_score})"
                    )
                if trade_signal == "NO_TRADE":
                    result["reasons"].append("Pas de signal tradeable dans le comptage actuel")

            
            # ═══ ÉTAPE 5 : Multi-timeframe confirmation ═══
            mtf_bonus = self._check_mtf_alignment(dataframes, result["signal"], timeframe)
            if mtf_bonus != 0:
                result["score"] = max(0, min(100, result["score"] + mtf_bonus))
                result["confidence"] = round(result["score"] / 100.0, 2)
                if mtf_bonus > 0:
                    result["reasons"].append(f"Confirmation multi-TF (+{mtf_bonus})")
                else:
                    result["warnings"].append(f"Conflit multi-TF ({mtf_bonus})")
        
        except Exception as e:
            result["reasons"].append(f"Erreur analyse Elliott: {str(e)}")
            result["warnings"].append(str(e))
        
        return result
    
    def _calculate_levels(self, result: Dict, position: Dict,
                          best: WaveCount, df: pd.DataFrame):
        """
        Calcule les niveaux entry, SL, TP1 avec garantie R:R ≥ 2.0.
        
        Logique :
        1. Entry = milieu de la zone d'entrée ou prix courant
        2. SL candidat = invalidation théorique de la vague
        3. TP candidat = projection Fibonacci (W1 * 1.618 pour W3, W1 pour W5)
        4. Guard R:R : si R:R < 2.0, on recalcule TP = entry ± (SL_distance * 2.0)
        5. Guard SL inversé : si SL du mauvais côté → SL = entry ± ATR * 1.5
        6. Guard TP invalide : si TP du mauvais côté → TP = entry ± SL_distance * 2.0
        """
        import numpy as np

        current_price = float(df['close'].iloc[-1])
        signal = result["signal"]

        # ── ATR(14) pour calibrer les distances ──
        highs  = df['high'].values[-20:]
        lows   = df['low'].values[-20:]
        closes = df['close'].values[-20:]
        tr = np.maximum(highs[1:] - lows[1:],
             np.maximum(abs(highs[1:] - closes[:-1]),
                        abs(lows[1:]  - closes[:-1])))
        atr = float(np.mean(tr)) if len(tr) > 0 else current_price * 0.003

        # ── Entry ──
        entry_zone = position.get("entry_zone")
        if entry_zone:
            result["entry"] = round((entry_zone[0] + entry_zone[1]) / 2, 5)
        else:
            result["entry"] = round(current_price, 5)
        entry = result["entry"]

        # ── SL candidat ──
        invalidation = position.get("invalidation")
        if invalidation:
            sl_candidate = round(float(invalidation), 5)
        else:
            last_wave = best.waves[-1]
            sl_dist_raw = last_wave.price_range * 0.5
            sl_candidate = round(entry - sl_dist_raw, 5) if signal == "BUY" else round(entry + sl_dist_raw, 5)

        # Guard SL inversé : SL doit être sous entry (BUY) ou au-dessus (SELL)
        if signal == "BUY" and sl_candidate >= entry:
            sl_candidate = round(entry - atr * 1.5, 5)
        elif signal == "SELL" and sl_candidate <= entry:
            sl_candidate = round(entry + atr * 1.5, 5)

        # Guard SL trop large : max 3× ATR
        sl_distance = abs(entry - sl_candidate)
        if sl_distance > atr * 3.0:
            sl_distance = atr * 2.0
            sl_candidate = round(entry - sl_distance, 5) if signal == "BUY" else round(entry + sl_distance, 5)

        result["sl"] = sl_candidate
        sl_distance = abs(entry - result["sl"])  # recalcul après ajustements

        # ── TP candidat depuis projections Fibonacci ──
        tp_candidate = None
        if best.wave_type == WaveType.IMPULSE and len(best.waves) >= 3:
            w1 = best.waves[0]
            status = position.get("status", "")
            if "w3_start" in status:
                fib_dist = w1.price_range * 1.618
            elif "w5_start" in status:
                fib_dist = w1.price_range * 1.0
            else:
                fib_dist = sl_distance * 2.5  # fallback R:R 2.5

            tp_candidate = round(entry + fib_dist, 5) if signal == "BUY" else round(entry - fib_dist, 5)

        elif best.wave_type == WaveType.CORRECTION and len(best.waves) >= 1:
            wa = best.waves[0]
            fib_dist = wa.price_range * 0.618
            tp_candidate = round(entry + fib_dist, 5) if signal == "BUY" else round(entry - fib_dist, 5)

        # ── Guard TP du mauvais côté ──
        if tp_candidate is not None:
            if signal == "BUY" and tp_candidate <= entry:
                tp_candidate = None
            elif signal == "SELL" and tp_candidate >= entry:
                tp_candidate = None

        # ── Guard R:R minimum 2.0 ──
        MIN_RR = 2.0
        if tp_candidate is not None:
            tp_distance = abs(tp_candidate - entry)
            actual_rr = tp_distance / sl_distance if sl_distance > 0 else 0
            if actual_rr < MIN_RR:
                # TP trop proche → l'allonger pour atteindre R:R 2.0
                tp_candidate = round(entry + sl_distance * MIN_RR, 5) if signal == "BUY" else round(entry - sl_distance * MIN_RR, 5)
        else:
            # Pas de TP Fibonacci valide → R:R 2.5 par défaut
            tp_candidate = round(entry + sl_distance * 2.5, 5) if signal == "BUY" else round(entry - sl_distance * 2.5, 5)

        result["tp1"] = tp_candidate

        # ── Log de diagnostic ──
        actual_rr_final = round(abs(result["tp1"] - entry) / sl_distance, 2) if sl_distance > 0 else 0
        result["warnings"].append(f"Elliott R:R={actual_rr_final} | Entry:{entry} SL:{result['sl']} TP1:{result['tp1']}")
    
    def _build_reasons(self, position: Dict, best: WaveCount) -> List[str]:
        """Construit la liste des raisons pour le signal."""
        reasons = []
        
        status = position.get("status", "unknown")
        direction = position.get("direction", "unknown")
        
        if "w3_start" in status:
            reasons.append(f"Début de vague 3 {direction} détecté (signal fort)")
        elif "w5_start" in status:
            reasons.append(f"Début de vague 5 {direction} (dernier mouvement)")
        elif "impulse_complete" in status:
            reasons.append(f"Impulsion {direction} terminée → correction attendue")
        elif "correction_complete" in status:
            reasons.append(f"Correction terminée → reprise de tendance")
        
        # Ajouter le score et les détails
        reasons.append(f"Score Elliott: {best.score}/100")
        
        # Guidelines
        g = best.details.get("guidelines", {})
        if g.get("w3_extended"):
            reasons.append(f"V3 étendue ({g.get('w3_extension', 0)}x)")
        if g.get("has_extension"):
            reasons.append(f"Extension V{g.get('extended_wave', '?')} confirmée")
        if g.get("alternation_depth"):
            reasons.append("Alternance V2/V4 correcte")
        
        return reasons
    
    def _check_mtf_alignment(self, dataframes: Dict[str, pd.DataFrame],
                              signal: str, main_tf: str) -> int:
        """
        Vérifie l'alignement multi-timeframe.
        Retourne un bonus/malus de score.
        """
        if signal == "NO_TRADE":
            return 0
        
        bonus = 0
        
        # Hiérarchie des timeframes
        tf_hierarchy = ["M5", "M15", "H1", "H4", "D1", "W1", "MN"]
        
        try:
            main_idx = tf_hierarchy.index(main_tf)
        except ValueError:
            return 0
        
        # Vérifier le timeframe supérieur
        for higher_tf in tf_hierarchy[main_idx + 1:]:
            if higher_tf in dataframes:
                htf_df = dataframes[higher_tf]
                if len(htf_df) >= 50:
                    htf_position = detect_current_wave_position(htf_df)
                    htf_signal = htf_position.get("trade_signal", "NO_TRADE")
                    
                    if htf_signal == signal:
                        bonus += 10  # Aligné → bonus
                    elif htf_signal != "NO_TRADE" and htf_signal != signal:
                        bonus -= 15  # Conflit → malus
                break  # Un seul TF supérieur suffit
        
        return bonus


# ============================================================
# FONCTION STANDALONE pour le méta-orchestrateur
# ============================================================

def run_elliott_analysis(dataframes: Dict[str, pd.DataFrame],
                          pair: str = "",
                          timeframe: str = "H4") -> Dict:
    """
    Point d'entrée pour le méta-orchestrateur.
    
    Usage:
        from agents.elliott.orchestrator import run_elliott_analysis
        signal = run_elliott_analysis(dataframes, pair="EURUSD", timeframe="H4")
    """
    orchestrator = ElliottOrchestrator()
    return orchestrator.analyze(dataframes, pair, timeframe)