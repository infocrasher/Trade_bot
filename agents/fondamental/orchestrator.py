"""
École Fondamentale — Placeholder
Retourne NO_TRADE en attendant l'implémentation complète.
"""

class FondamentalOrchestrator:
    """Orchestrateur Fondamental/News — À implémenter."""

    def analyze(self, pair, market_data=None, news=None):
        """
        Analyse une paire selon les fondamentaux et news.

        Args:
            pair: symbole (ex: "EURUSD")
            market_data: données de marché
            news: news récentes (optionnel)

        Returns:
            dict au format standard des écoles
        """
        return {
            "school": "fondamental",
            "pair": pair,
            "signal": "NO_TRADE",
            "score": 0,
            "confidence": 0.0,
            "entry": 0,
            "sl": 0,
            "tp1": 0,
            "reasons": ["Analyse fondamentale non implémentée"],
            "warnings": [],
            "details": {},
        }
