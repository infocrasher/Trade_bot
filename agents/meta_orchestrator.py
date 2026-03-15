"""
Méta-Orchestrateur — Compare les signaux de toutes les écoles.
Chaque école retourne un signal indépendant, le méta-orchestrateur
les fusionne et prend la décision finale.

Étape 4 — Remplacement du vote binaire par MetaConvergenceEngine.
"""

import time
from typing import List

try:
    from agents.meta_convergence import MetaConvergenceEngine, ProfileSignal, Direction
    _MCE_AVAILABLE = True
except ImportError:
    _MCE_AVAILABLE = False


class MetaOrchestrator:
    """Compare les signaux des différentes écoles de trading.

    ── Phase paper_trading ──
    Seuil activation = 0.35 (conservateur — favorise les trades pédagogiques)
    Seuil live       = 0.45 (à relever après 100 trades confirmés en paper)
    """

    # Poids par école (utilisés en fallback si MetaConvergenceEngine absent)
    WEIGHTS = {
        "ict":      0.55,
        "elliott":  0.30,
        "vsa":      0.15,
    }

    # Seuil d'activation MetaConvergenceEngine — phase paper_trading
    MCE_THRESHOLD = 0.35

    def __init__(self):
        if _MCE_AVAILABLE:
            self._mce = MetaConvergenceEngine(config={
                "activation_threshold": self.MCE_THRESHOLD,
                "crowding_threshold": 0.55,
            })
        else:
            self._mce = None

    # ── Point d'entrée principal ─────────────────────────────────────────────
    def compare(self, signals: list) -> dict:
        """
        Compare les signaux de toutes les écoles.
        Utilise MetaConvergenceEngine si disponible.
        Sinon, fallback sur le vote pondéré classique.

        Args:
            signals: list de dicts format standard
                     [{"school": "ict", "signal": "BUY", "score": ..., ...}, ...]

        Returns:
            dict avec la décision finale.
        """
        if not signals:
            return self._no_trade("Aucun signal reçu")

        # ── VETO ICT — règle absolue ─────────────────────────────────────────
        ict_raw = next((s for s in signals if s.get("school") == "ict"), None)
        if ict_raw and ict_raw.get("signal") == "NO_TRADE":
            return self._no_trade(
                "ICT veto — école principale a bloqué le trade "
                "(les autres écoles ne peuvent pas surchargé les gates de sécurité ICT)"
            )

        # Filtrer les NO_TRADE
        active_signals = [s for s in signals if s.get("signal") not in ("NO_TRADE", None)]

        if not active_signals:
            return self._no_trade("Toutes les écoles disent NO_TRADE")

        # ── MetaConvergenceEngine — scoring pondéré dynamique ────────────────
        if self._mce and len(active_signals) >= 1:
            try:
                profile_signals = []
                for s in active_signals:
                    sig_str = s.get("signal", "NO_TRADE")
                    if sig_str == "BUY":
                        direction = Direction.LONG
                    elif sig_str == "SELL":
                        direction = Direction.SHORT
                    else:
                        continue
                    ps = ProfileSignal(
                        profile_id=s.get("school", "unknown"),
                        direction=direction,
                        confidence=s.get("confidence", s.get("score", 0) / 100),
                        timestamp=time.time(),
                        ttl_seconds=1800,
                        instrument=s.get("pair", "UNKNOWN"),
                    )
                    profile_signals.append(ps)

                if profile_signals:
                    activated, meta_score, details = self._mce.scorer.should_activate(profile_signals)

                    # Dériver la direction dominante (poids net)
                    net_dir = sum(
                        (1 if s.direction == Direction.LONG else -1) * s.confidence
                        for s in profile_signals
                    )
                    direction = "BUY" if net_dir >= 0 else "SELL"

                    # Trouver le signal dominant (plus fort poids configuré)
                    dominant_school = max(active_signals, key=lambda s: self.WEIGHTS.get(s.get("school", ""), 0.1))

                    return {
                        "decision": direction if activated else "NO_TRADE",
                        "score": int(abs(meta_score) * 100),
                        "confidence": abs(meta_score),
                        "entry": dominant_school.get("entry", 0),
                        "sl": dominant_school.get("sl", 0),
                        "tp1": dominant_school.get("tp1", 0),
                        "pair": dominant_school.get("pair", ""),
                        "dominant_school": dominant_school.get("school", ""),
                        "alignment": f"MCE meta_score={meta_score:.3f} | seuil={self.MCE_THRESHOLD}",
                        "all_signals": signals,
                        "reasons": [f"{pid}: {d.get('direction')} w={d.get('perf_weight'):.2f}" for pid, d in details.items()],
                        "warnings": [] if activated else [f"MCE score {abs(meta_score):.3f} < seuil {self.MCE_THRESHOLD}"],
                        "mce_score": meta_score,
                        "mce_details": details,
                    }
            except Exception as mce_err:
                # Fallback silencieux en cas d'erreur MCE
                pass

        # ── Fallback — vote pondéré classique (sans MetaConvergenceEngine) ──
        return self._weighted_vote(signals, active_signals)

    # ── Vote pondéré classique (fallback) ────────────────────────────────────
    def _weighted_vote(self, signals, active_signals):
        if len(active_signals) == 1:
            sig = active_signals[0]
            return {
                "decision": sig["signal"],
                "score": sig["score"],
                "confidence": sig["confidence"],
                "entry": sig.get("entry", 0),
                "sl": sig.get("sl", 0),
                "tp1": sig.get("tp1", 0),
                "pair": sig["pair"],
                "dominant_school": sig["school"],
                "alignment": f"1 école ({sig['school']})",
                "all_signals": signals,
                "reasons": sig.get("reasons", []),
                "warnings": ["Signal unique — pas de confirmation inter-écoles"],
            }

        directions = {}
        for sig in active_signals:
            d = sig["signal"]
            directions.setdefault(d, []).append(sig)

        if len(directions) > 1:
            best_dir, best_weight = None, 0
            for direction, sigs in directions.items():
                total_weight = sum(self.WEIGHTS.get(s["school"], 0.1) for s in sigs)
                if total_weight > best_weight:
                    best_weight = total_weight
                    best_dir = direction

            aligned     = directions[best_dir]
            conflicting = [s for d, sigs in directions.items() if d != best_dir for s in sigs]
            score_positif = sum(s["score"] * self.WEIGHTS.get(s["school"], 0.1) for s in aligned)
            score_negatif = sum(s["score"] * self.WEIGHTS.get(s["school"], 0.1) for s in conflicting)
            weighted_score = max(0, score_positif - score_negatif)
            dominant = max(aligned, key=lambda s: self.WEIGHTS.get(s["school"], 0))

            return {
                "decision": best_dir,
                "score": int(weighted_score),
                "confidence": weighted_score / 100,
                "entry": dominant.get("entry", 0),
                "sl": dominant.get("sl", 0),
                "tp1": dominant.get("tp1", 0),
                "pair": dominant["pair"],
                "dominant_school": dominant["school"],
                "alignment": f"{len(aligned)}/{len(active_signals)} alignés ({best_dir})",
                "all_signals": signals,
                "reasons": [f"{s['school']}: {', '.join(s.get('reasons', []))}" for s in aligned],
                "warnings": [
                    f"CONFLIT: {s['school']} dit {s['signal']} ({s['score']}/100) "
                    f"[pénalité -{round(s['score'] * self.WEIGHTS.get(s['school'], 0.1), 1)}pts]"
                    for s in conflicting
                ],
            }
        else:
            direction = list(directions.keys())[0]
            aligned   = directions[direction]
            total_w   = sum(self.WEIGHTS.get(s["school"], 0.1) for s in aligned)
            weighted_score = sum(s["score"] * self.WEIGHTS.get(s["school"], 0.1) for s in aligned) / total_w
            if len(aligned) >= 2:
                weighted_score *= 1.10
            if len(aligned) >= 3:
                weighted_score *= 1.05
            weighted_score = min(100, weighted_score)
            dominant = max(aligned, key=lambda s: self.WEIGHTS.get(s["school"], 0))

            return {
                "decision": direction,
                "score": int(weighted_score),
                "confidence": weighted_score / 100,
                "entry": dominant.get("entry", 0),
                "sl": dominant.get("sl", 0),
                "tp1": dominant.get("tp1", 0),
                "pair": dominant["pair"],
                "dominant_school": dominant["school"],
                "alignment": f"{len(aligned)}/{len(aligned)} alignés ({direction}) ✅",
                "all_signals": signals,
                "reasons": [f"{s['school']}: {', '.join(s.get('reasons', []))}" for s in aligned],
                "warnings": [],
            }

    def _no_trade(self, reason):
        return {
            "decision": "NO_TRADE",
            "score": 0,
            "confidence": 0.0,
            "reasons": [reason],
            "warnings": [],
            "all_signals": [],
        }