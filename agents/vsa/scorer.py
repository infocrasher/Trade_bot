"""
VSA Scorer
Fusionne le score algorithmique (50 pts) du VolumeAnalyzer
avec le score visuel (50 pts) de Gemini Vision.
Retourne un score final /100 et une recommandation d'action.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from .volume_analyzer import (
    VSAAnalysis, VSASignal, WyckoffCycle, WyckoffPhase,
    VolumeLevel, SpreadLevel
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# RÉSULTAT FINAL DU SCORER
# ─────────────────────────────────────────────

@dataclass
class VSAScore:
    """Score VSA complet fusionné."""
    symbol:            str
    timeframe:         str
    score_algo:        float       # 0–50 (VolumeAnalyzer)
    score_visuel:      float       # 0–50 (Gemini Vision)
    score_total:       float       # 0–100
    direction:         str         # "BUY", "SELL", "NEUTRAL"
    confiance:         float       # 0.0–1.0
    action:            str         # "EXECUTE", "OBSERVE", "IGNORE"
    signal_name:       str
    wyckoff_phase:     str
    wyckoff_cycle:     str
    balance:           float
    absorption:        bool
    invalidations:     list
    confluences:       list
    commentaire_algo:  str
    commentaire_gemini:str
    gemini_available:  bool

    def to_dict(self) -> dict:
        return {
            'symbol':             self.symbol,
            'timeframe':          self.timeframe,
            'score_algo':         self.score_algo,
            'score_visuel':       self.score_visuel,
            'score_total':        self.score_total,
            'direction':          self.direction,
            'confiance':          round(self.confiance, 3),
            'action':             self.action,
            'signal_name':        self.signal_name,
            'wyckoff_phase':      self.wyckoff_phase,
            'wyckoff_cycle':      self.wyckoff_cycle,
            'balance':            self.balance,
            'absorption':         self.absorption,
            'invalidations':      self.invalidations,
            'confluences':        self.confluences,
            'commentaire_algo':   self.commentaire_algo,
            'commentaire_gemini': self.commentaire_gemini,
            'gemini_available':   self.gemini_available,
        }


# ─────────────────────────────────────────────
# SCORER PRINCIPAL
# ─────────────────────────────────────────────

class VSAScorer:
    """
    Fusionne les deux sources de score :
      - score_algo   : sortie de VolumeAnalyzer.raw_score (0–50)
      - score_visuel : sortie de GeminiVSAAnalyzer (0–50)

    Applique les règles d'invalidation de l'encyclopédie (Sec.18)
    avant de retourner la décision finale.
    """

    # Seuils d'action (Sec.25 enrichi)
    try:
        from config import PAPER_TRADING
        THRESHOLD_EXECUTE = 55 if PAPER_TRADING else 65
    except ImportError:
        THRESHOLD_EXECUTE = 65   # >= 65/100 → signal actif en observation mode
        
    THRESHOLD_OBSERVE = 40   # >= 40/100 → loggé mais pas tradé
    # < 40 → ignoré silencieusement

    def score(self,
              analysis: VSAAnalysis,
              gemini_result: Optional[dict] = None) -> VSAScore:
        """
        Calcule le score final VSA.

        analysis      : VSAAnalysis du VolumeAnalyzer
        gemini_result : dict retourné par GeminiVSAAnalyzer (peut être None)
        """
        sig     = analysis.last_bar_result
        wyckoff = analysis.wyckoff_state

        # ── 1. Score algo (déjà calculé dans VolumeAnalyzer) ──
        score_algo = analysis.raw_score

        # ── 2. Score visuel Gemini ──
        gemini_available = gemini_result is not None and gemini_result.get('_source') not in ('disabled', None)
        score_visuel     = float(gemini_result.get('score_visuel', 0)) if gemini_result else 0.0
        gemini_direction = gemini_result.get('direction', 'NEUTRAL') if gemini_result else 'NEUTRAL'
        gemini_confiance = float(gemini_result.get('confiance', 0.0)) if gemini_result else 0.0
        commentaire_g    = gemini_result.get('commentaire', '') if gemini_result else ''
        confluences_g    = gemini_result.get('confluences_visuelles', []) if gemini_result else []
        invalidations_g  = gemini_result.get('invalidations_visuelles', []) if gemini_result else []

        # ── 3. Score brut fusionné ──
        score_raw = score_algo + score_visuel

        # ── 4. Déterminer direction unifiée ──
        direction = self._unify_direction(sig, gemini_direction, wyckoff)

        # ── 5. Appliquer les kill-switches (Sec.18) ──
        kill_reasons = self._check_kill_switches(analysis, gemini_result)
        if kill_reasons:
            score_raw = 0.0
            direction = "NEUTRAL"

        # ── 6. Bonus/malus supplémentaires scorer ──
        score_raw = self._apply_scorer_adjustments(score_raw, analysis, gemini_direction, direction)

        # ── 7. Clamp final ──
        score_total = max(0.0, min(100.0, round(score_raw, 1)))

        # ── 8. Décision d'action ──
        action = self._decide_action(score_total, direction, kill_reasons)

        # ── 9. Confiance fusionnée ──
        confiance_algo   = sig.strength
        confiance_finale = round((confiance_algo + gemini_confiance) / 2, 3) if gemini_available else confiance_algo

        return VSAScore(
            symbol            = analysis.symbol,
            timeframe         = analysis.timeframe,
            score_algo        = score_algo,
            score_visuel      = score_visuel,
            score_total       = score_total,
            direction         = direction,
            confiance         = confiance_finale,
            action            = action,
            signal_name       = sig.signal.value,
            wyckoff_phase     = wyckoff.phase.value,
            wyckoff_cycle     = wyckoff.cycle.value,
            balance           = analysis.balance,
            absorption        = analysis.absorption_detected,
            invalidations     = kill_reasons + invalidations_g,
            confluences       = confluences_g,
            commentaire_algo  = sig.description,
            commentaire_gemini= commentaire_g,
            gemini_available  = gemini_available,
        )

    # ─────────────────────────────────────────
    # DIRECTION UNIFIÉE
    # ─────────────────────────────────────────

    def _unify_direction(self, sig, gemini_dir: str, wyckoff) -> str:
        """
        Unifie la direction algo + Gemini.
        L'algo prime si Gemini est indisponible.
        En cas de contradiction forte → NEUTRAL.
        """
        # Normaliser direction algo
        algo_dir = sig.direction
        if algo_dir == "BULL":  algo_dir = "BUY"
        if algo_dir == "BEAR":  algo_dir = "SELL"

        # Gemini non dispo → direction algo pure
        if gemini_dir == "NEUTRAL" and algo_dir != "NEUTRAL":
            return algo_dir

        # Contradiction → NEUTRAL sauf si signal très fort
        if algo_dir != gemini_dir and algo_dir != "NEUTRAL" and gemini_dir != "NEUTRAL":
            if sig.strength >= 0.85:
                return algo_dir   # signal algo très fort, on lui fait confiance
            logger.debug(f"[VSAScorer] Contradiction direction : algo={algo_dir} / gemini={gemini_dir}")
            return "NEUTRAL"

        # Accord ou l'un est NEUTRAL
        return algo_dir if algo_dir != "NEUTRAL" else gemini_dir

    # ─────────────────────────────────────────
    # KILL-SWITCHES (Sec.18)
    # ─────────────────────────────────────────

    def _check_kill_switches(self, analysis: VSAAnalysis,
                              gemini_result: Optional[dict]) -> list:
        """
        Vérifie les règles d'invalidation absolues (Sec.18.1).
        Retourne une liste de raisons. Si vide → pas d'invalidation.
        """
        reasons = []
        sig     = analysis.last_bar_result
        wyckoff = analysis.wyckoff_state

        # Kill 1 : signal SOS dans un Mark-Down actif sans SC préalable
        if (sig.is_sos and
            wyckoff.cycle == WyckoffCycle.MARKDOWN and
            wyckoff.sc_level is None):
            reasons.append("Kill-switch : SOS contre Mark-Down actif sans SC préalable")

        # Kill 2 : signal SOW dans un Mark-Up actif sans BC préalable
        if (sig.is_sow and
            wyckoff.cycle == WyckoffCycle.MARKUP and
            wyckoff.bc_level is None):
            reasons.append("Kill-switch : SOW contre Mark-Up actif sans BC préalable")

        # Kill 3 : Gemini invalide visuellement le signal algo
        if gemini_result:
            inv_list = gemini_result.get('invalidations_visuelles', [])
            if any('kill' in i.lower() or 'invalide' in i.lower() for i in inv_list):
                reasons.append(f"Kill-switch Gemini : {inv_list[0]}")

        # Kill 4 : signal NEUTRAL → pas de trade
        if sig.signal == VSASignal.NEUTRAL:
            reasons.append("Signal NEUTRAL — aucune anomalie VSA détectée")

        return reasons

    # ─────────────────────────────────────────
    # AJUSTEMENTS SCORER
    # ─────────────────────────────────────────

    def _apply_scorer_adjustments(self, score: float,
                                   analysis: VSAAnalysis,
                                   gemini_dir: str,
                                   unified_dir: str) -> float:
        """Bonus/malus supplémentaires au niveau du scorer (Sec.25)."""
        sig = analysis.last_bar_result

        # Bonus confirmation : algo et Gemini d'accord sur la direction
        algo_dir = "BUY" if sig.is_sos else ("SELL" if sig.is_sow else "NEUTRAL")
        if algo_dir == gemini_dir and algo_dir != "NEUTRAL":
            score += 5.0  # accord parfait

        # Bonus absorption multi-barres confirmée
        if analysis.absorption_detected:
            score += 3.0

        # Bonus signaux très forts (strength >= 0.90)
        if sig.strength >= 0.90:
            score += 4.0
        elif sig.strength >= 0.80:
            score += 2.0

        # Pénalité cycle UNDEFINED
        if analysis.wyckoff_state.cycle == WyckoffCycle.UNDEFINED:
            score -= 5.0

        # Pénalité balance neutre (marché en range sans direction)
        if abs(analysis.balance) < 0.5:
            score -= 2.0

        return score

    # ─────────────────────────────────────────
    # DÉCISION D'ACTION
    # ─────────────────────────────────────────

    def _decide_action(self, score: float,
                        direction: str,
                        kill_reasons: list) -> str:
        """
        Retourne l'action recommandée.
        En observation mode (intégration initiale), EXECUTE = loggé pour stats,
        pas encore routé vers l'orchestrateur ICT.
        """
        if kill_reasons or direction == "NEUTRAL":
            return "IGNORE"

        if score >= self.THRESHOLD_EXECUTE:
            return "EXECUTE"    # signal fort → transmission MetaOrchestrator
        if score >= self.THRESHOLD_OBSERVE:
            return "OBSERVE"    # signal modéré → loggé uniquement
        return "IGNORE"
