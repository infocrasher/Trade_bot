"""
OTE Tracker — State Machine pour le suivi des setups en attente.

États possibles par setup :
  WAITING    → OTE calculé, prix pas encore dans la zone
  TRIGGERED  → Prix a touché la zone OTE ce cycle
  INVALIDATED → Structure cassée (nouveau BOS contraire)

Stockage : data/ote_setups.json (persistant entre cycles)
"""

import json
import os
from datetime import datetime, timezone
from typing import Optional

OTE_FILE = "data/ote_setups.json"
os.makedirs("data", exist_ok=True)


def _load() -> dict:
    if os.path.exists(OTE_FILE):
        try:
            with open(OTE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save(setups: dict) -> None:
    with open(OTE_FILE, "w") as f:
        json.dump(setups, f, indent=2)


def _key(pair: str, horizon: str, bias: str) -> str:
    return f"{pair}_{horizon}_{bias}"


def save_setup(pair: str, horizon: str, bias: str,
               ote_top: float, ote_bottom: float,
               s_start: float, s_end: float,
               obs: list, fvgs: list) -> None:
    """
    Sauvegarde un setup OTE en état WAITING.
    Appelé quand le prix n'est pas encore dans la zone.
    """
    setups = _load()
    k = _key(pair, horizon, bias)
    setups[k] = {
        "pair":       pair,
        "horizon":    horizon,
        "bias":       bias,
        "ote_top":    ote_top,
        "ote_bottom": ote_bottom,
        "s_start":    s_start,
        "s_end":      s_end,
        "obs":        obs,
        "fvgs":       fvgs,
        "state":      "WAITING",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "cycles_waited": 0,
    }
    _save(setups)


def get_waiting_setup(pair: str, horizon: str, bias: str) -> Optional[dict]:
    """
    Retourne le setup WAITING pour ce pair/horizon/bias s'il existe.
    """
    setups = _load()
    k = _key(pair, horizon, bias)
    setup = setups.get(k)
    if setup and setup.get("state") == "WAITING":
        return setup
    return None


def invalidate_setup(pair: str, horizon: str, bias: str, reason: str = "") -> None:
    """
    Invalide un setup (nouveau BOS contraire, bias changé, etc.)
    """
    setups = _load()
    k = _key(pair, horizon, bias)
    if k in setups:
        setups[k]["state"] = "INVALIDATED"
        setups[k]["invalidated_at"] = datetime.now(timezone.utc).isoformat()
        setups[k]["invalidation_reason"] = reason
        _save(setups)


def tick_cycle(pair: str, horizon: str, bias: str) -> int:
    """
    Incrémente le compteur de cycles d'attente.
    Retourne le nombre de cycles attendus.
    Invalide automatiquement après 288 cycles (24h en M5).
    """
    setups = _load()
    k = _key(pair, horizon, bias)
    if k not in setups:
        return 0
    setups[k]["cycles_waited"] = setups[k].get("cycles_waited", 0) + 1
    setups[k]["updated_at"] = datetime.now(timezone.utc).isoformat()
    cycles = setups[k]["cycles_waited"]
    # Expiration : 24h = 288 cycles M5
    if cycles > 288:
        setups[k]["state"] = "INVALIDATED"
        setups[k]["invalidation_reason"] = "Timeout 24h"
    _save(setups)
    return cycles


def clear_triggered(pair: str, horizon: str, bias: str) -> None:
    """
    Supprime un setup après qu'un trade a été exécuté ou refusé sur ce setup.
    """
    setups = _load()
    k = _key(pair, horizon, bias)
    if k in setups:
        del setups[k]
        _save(setups)


def get_all_waiting() -> list:
    """
    Retourne tous les setups en état WAITING (pour le dashboard).
    """
    setups = _load()
    return [s for s in setups.values() if s.get("state") == "WAITING"]
