"""
================================================================
  PLAN STORAGE — Gestionnaire de Persistance des Plans ICT
================================================================
  Stocke et charge les plans générés par les 4 niveaux.
  Format JSON dans le dossier plans/.
  Structure : plans/{PAIR}_{horizon}_{date}.json
================================================================
"""

import os
import json
import logging
from datetime import datetime

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

logger = logging.getLogger("PlanStorage")


class PlanStorage:
    """
    Gestionnaire de stockage des plans ICT multi-horizon.
    Horizons : weekly | daily | scalp
    """

    HORIZONS = ["weekly", "daily", "scalp"]

    def __init__(self):
        self.plans_dir = os.path.join(config.BASE_DIR, "plans")
        os.makedirs(self.plans_dir, exist_ok=True)
        logger.info(f"[OK] PlanStorage initialisé → {self.plans_dir}")

    # -------------------------------------------------------
    # Sauvegarde
    # -------------------------------------------------------
    def save_plan(self, pair: str, horizon: str, plan_text: str, metadata: dict = None) -> str:
        """
        Sauvegarde un plan en JSON.
        Retourne le chemin du fichier créé.
        """
        assert horizon in self.HORIZONS, f"Horizon invalide : {horizon}"

        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        filename = f"{pair.replace('/', '')}_{horizon}_{date_str}.json"
        filepath = os.path.join(self.plans_dir, filename)

        data = {
            "pair": pair,
            "horizon": horizon,
            "date": date_str,
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
            "plan": plan_text,
            "metadata": metadata or {},
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        logger.info(f"[SAVE] Plan {horizon} pour {pair} sauvegardé → {filename}")
        return filepath

    # -------------------------------------------------------
    # Chargement du dernier plan
    # -------------------------------------------------------
    def load_latest_plan(self, pair: str, horizon: str) -> dict | None:
        """
        Charge le plan le plus récent pour une paire + horizon donnés.
        Retourne None si aucun plan trouvé.
        """
        assert horizon in self.HORIZONS, f"Horizon invalide : {horizon}"

        pair_clean = pair.replace("/", "")
        prefix = f"{pair_clean}_{horizon}_"

        # Trouver tous les fichiers correspondants et prendre le plus récent
        matching = sorted(
            [f for f in os.listdir(self.plans_dir) if f.startswith(prefix) and f.endswith(".json")],
            reverse=True
        )

        if not matching:
            logger.warning(f"[MISS] Aucun plan {horizon} trouvé pour {pair}")
            return None

        filepath = os.path.join(self.plans_dir, matching[0])
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.info(f"[LOAD] Plan {horizon} pour {pair} chargé → {matching[0]}")
            return data
        except Exception as e:
            logger.error(f"[ERR] Erreur chargement plan {filepath}: {e}")
            return None

    # -------------------------------------------------------
    # Chargement de tous les plans actifs (dashboard)
    # -------------------------------------------------------
    def get_all_active_plans(self, pair: str) -> dict:
        """
        Retourne un dict avec le dernier plan de chaque horizon pour une paire.
        Utilisé par le dashboard pour afficher l'état global.
        """
        return {
            horizon: self.load_latest_plan(pair, horizon)
            for horizon in self.HORIZONS
        }

    # -------------------------------------------------------
    # Mise à jour de la décision sur un trade (escalade)
    # -------------------------------------------------------
    def flag_escalation(self, pair: str, from_horizon: str, reason: str):
        """
        Marque un plan comme nécessitant une révision par l'horizon supérieur.
        Ex: Daily détecte un CHoCH contraire au plan Weekly → flag escalation.
        """
        plan = self.load_latest_plan(pair, from_horizon)
        if plan:
            plan["metadata"]["escalation_needed"] = True
            plan["metadata"]["escalation_reason"] = reason
            plan["metadata"]["escalation_timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # Réécrire le fichier
            date_str = plan["date"]
            pair_clean = pair.replace("/", "")
            filename = f"{pair_clean}_{from_horizon}_{date_str}.json"
            filepath = os.path.join(self.plans_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(plan, f, indent=4, ensure_ascii=False)
            logger.warning(f"[ESCALADE] {from_horizon} → niveau supérieur. Raison: {reason}")


if __name__ == "__main__":
    storage = PlanStorage()
    storage.save_plan("EURUSD", "weekly", "Test plan hebdo EURUSD", {"bias": "HAUSSIER"})
    latest = storage.load_latest_plan("EURUSD", "weekly")
    print("Plan chargé:", latest["plan"])
