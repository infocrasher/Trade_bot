import os
import json
import logging
from datetime import datetime

# Import config pour les chemins
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

logger = logging.getLogger("MemoryManager")

class MemoryManager:
    """
    Gère la persistence de la narration et des zones ICT entre les sessions.
    Stocke les donnees sous forme de fichiers JSON dans le dossier memory/.
    """
    
    def __init__(self, memory_dir=None):
        if memory_dir is None:
            self.memory_dir = os.path.join(config.BASE_DIR, "memory")
        else:
            self.memory_dir = memory_dir
            
        if not os.path.exists(self.memory_dir):
            os.makedirs(self.memory_dir)
            
    def _get_file_path(self, pair: str) -> str:
        """Retourne le chemin du fichier de memoire pour une paire donnee."""
        clean_pair = pair.replace("/", "").replace("\\", "").upper()
        return os.path.join(self.memory_dir, f"{clean_pair}_state.json")

    def load_memory(self, pair: str) -> dict:
        """
        Charge la memoire d'une paire depuis le disque.
        Si le fichier n'existe pas, retourne une structure initiale vide.
        """
        path = self._get_file_path(pair)
        if not os.path.exists(path):
            return self._get_initial_state(pair)
            
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data
        except Exception as e:
            logger.error(f"Erreur lors du chargement de la memoire pour {pair}: {e}")
            return self._get_initial_state(pair)

    def save_memory(self, pair: str, state: dict):
        """Sauvegarde l'etat actuel d'une paire sur le disque."""
        path = self._get_file_path(pair)
        try:
            state["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde de la memoire pour {pair}: {e}")
            return False

    def _get_initial_state(self, pair: str) -> dict:
        """Retourne une structure vide par defaut pour une nouvelle paire."""
        return {
            "pair": pair,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "narrative_status": "Initialisation du systeme. Aucune narration passee.",
            "active_pois": {
                "fvg": [],      # {timeframe, type, price_range, state: 'open'|'filled', date_detected}
                "order_blocks": [],
                "breakers": []
            },
            "liquidity_levels": {
                "eqh_eql": [],
                "pdh_pdl": {"pdh": None, "pdl": None, "pwh": None, "pwl": None},
                "major_sweeps": []
            },
            "scenario_history": [], # Historique des derniers scenarios generes {date, type, outcome}
            "trade_journal": []      # Notes sur les derniers trades pris sur cette paire
        }

    def update_narrative(self, pair: str, new_narrative: str):
        """Met a jour uniquement la partie narrative de la memoire."""
        state = self.load_memory(pair)
        state["narrative_status"] = new_narrative
        # ✅ FIX AUDIT-11 : Limiter scenario_history à 100 entrées
        if "scenario_history" in state and len(state["scenario_history"]) > 100:
            state["scenario_history"] = state["scenario_history"][-100:]
        # ✅ FIX AUDIT-11 : Limiter trade_journal à 50 entrées
        if "trade_journal" in state and len(state["trade_journal"]) > 50:
            state["trade_journal"] = state["trade_journal"][-50:]
        self.save_memory(pair, state)

    def add_poi(self, pair: str, poi_type: str, poi_data: dict):
        """Ajoute un Point of Interest (FVG, OB, etc.) a la memoire."""
        state = self.load_memory(pair)
        valid_types = ["fvg", "order_blocks", "breakers"]
        if poi_type in valid_types:
            state["active_pois"][poi_type].append(poi_data)
            # Optionnel : Limiter le nombre de POIs stockes
            if len(state["active_pois"][poi_type]) > 50:
                state["active_pois"][poi_type].pop(0)
            self.save_memory(pair, state)

# --- Test Rapide ---
if __name__ == "__main__":
    print("Test MemoryManager")
    manager = MemoryManager()
    
    # Test chargement/sauvegarde
    pair = "EURUSD"
    state = manager.load_memory(pair)
    print(f"Charge memoire {pair} : {state['narrative_status']}")
    
    manager.update_narrative(pair, "Le marche est en expansion baissiere vers le SSL mensuel.")
    state_v2 = manager.load_memory(pair)
    print(f"Mis a jour : {state_v2['narrative_status']}")
    
    manager.add_poi(pair, "fvg", {"timeframe": "H4", "type": "bearish", "price": "1.0850-1.0860"})
    print("POI ajoute.")
