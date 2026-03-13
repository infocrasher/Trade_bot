"""
Méta-Orchestrateur — Compare les signaux de toutes les écoles.
Chaque école retourne un signal indépendant, le méta-orchestrateur
les fusionne et prend la décision finale.
"""


class MetaOrchestrator:
    """Compare les signaux des différentes écoles de trading."""

    # Poids par école (ajustables)
    # Mode actuel : ICT dominant (70%) + Elliott observateur (30%) + VSA inactif (0%)
    WEIGHTS = {
        "ict":      0.70,   # ICT = école principale
        "elliott":  0.30,   # Elliott Wave
        "vsa":      0.00,   # VSA/Wyckoff — observation seulement
    }

    def compare(self, signals):
        """
        Compare les signaux de toutes les écoles.

        Args:
            signals: list de dicts au format standard
                     [{"school": "ict", "signal": "BUY", "score": 72, ...}, ...]

        Returns:
            dict avec la décision finale
        """
        if not signals:
            return self._no_trade("Aucun signal reçu")

        # Filtrer les NO_TRADE
        active_signals = [s for s in signals if s.get("signal") not in ("NO_TRADE", None)]

        # ── VETO ICT — règle absolue ─────────────────────────────────────────────────
        # Si ICT a dit NO_TRADE, aucune autre école ne peut surchargé sa décision.
        # ICT contient les gates de sécurité (SOD, KS4, KS8, SL minimum, etc.)
        ict_raw = next((s for s in signals if s.get("school") == "ict"), None)
        if ict_raw and ict_raw.get("signal") == "NO_TRADE":
            return self._no_trade(
                "ICT veto — école principale a bloqué le trade "
                "(les autres écoles ne peuvent pas surchargé les gates de sécurité ICT)"
            )
        # ─────────────────────────────────────────────────────────────────────────────

        if not active_signals:
            return self._no_trade("Toutes les écoles disent NO_TRADE")

        # Si une seule école a un signal → on le prend directement
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

        # Vérifier l'alignement directionnel
        directions = {}
        for sig in active_signals:
            d = sig["signal"]  # BUY ou SELL
            if d not in directions:
                directions[d] = []
            directions[d].append(sig)

        if len(directions) > 1:
            # Conflit entre écoles — ICT prend la direction, Elliott réduit le score
            best_dir = None
            best_weight = 0
            for direction, sigs in directions.items():
                total_weight = sum(self.WEIGHTS.get(s["school"], 0.1) for s in sigs)
                if total_weight > best_weight:
                    best_weight = total_weight
                    best_dir = direction

            aligned    = directions[best_dir]
            conflicting = [s for d, sigs in directions.items() if d != best_dir for s in sigs]

            # ── Fix : score pondéré avec pénalité des écoles conflictuelles ──────
            # Avant : on ignorait les écoles conflictuelles → score artificiel
            # Après : score = Σ(poids_aligné × score) - Σ(poids_conflit × score)
            score_positif = sum(
                s["score"] * self.WEIGHTS.get(s["school"], 0.1) for s in aligned
            )
            score_negatif = sum(
                s["score"] * self.WEIGHTS.get(s["school"], 0.1) for s in conflicting
            )
            weighted_score = score_positif - score_negatif
            weighted_score = max(0, weighted_score)  # floor à 0, jamais négatif
            # ─────────────────────────────────────────────────────────────────────

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
            # Toutes les écoles actives sont alignées
            direction = list(directions.keys())[0]
            aligned = directions[direction]

            total_w = sum(self.WEIGHTS.get(s["school"], 0.1) for s in aligned)
            weighted_score = sum(
                s["score"] * self.WEIGHTS.get(s["school"], 0.1) for s in aligned
            ) / total_w

            # Bonus pour consensus inter-écoles
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