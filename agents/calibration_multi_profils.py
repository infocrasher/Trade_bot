"""
CALIBRATION MULTI-PROFILS — Paramètres ajustés selon ICT & Elliott Wave
========================================================================
Basé sur l'analyse croisée de :
  - Encyclopédie ICT v2.0 (Sections 2, 5, 10, 11, 12)
  - Encyclopédie Elliott Wave v1.0 (Sections 2, 7, 15, J, K, L)

4 calibrations demandées :
  1. TTL par profil
  2. Seuil d'activation
  3. Règle SL/TP en convergence
  4. Règle de conflit directionnel
"""

import time
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from enum import Enum


# =============================================================================
# 1. TTL PAR PROFIL — CALIBRATION JUSTIFIÉE
# =============================================================================
#
# PRINCIPE : le TTL doit correspondre à la durée de vie NATURELLE du setup
# dans chaque école, pas à un chiffre arbitraire.
#
# ┌─────────────┬─────────┬──────────┬──────────────────────────────────────┐
# │ Profil      │ Ancien  │ Nouveau  │ Justification                        │
# ├─────────────┼─────────┼──────────┼──────────────────────────────────────┤
# │ ICT Strict  │ 4h      │ 3h       │ Voir ci-dessous                      │
# │ Elliott     │ 12h     │ 24h      │ Voir ci-dessous                      │
# │ VSA/Wyckoff │ 8h      │ 8h       │ Correct, cohérent D1/H4             │
# │ Pure PA     │ 10 min  │ 30 min   │ Voir ci-dessous                      │
# │ Custom      │ 6h      │ 6h       │ Valeur médiane acceptable            │
# └─────────────┴─────────┴──────────┴──────────────────────────────────────┘
#
# ── ICT : 4h → 3h ──
#
# Pourquoi BAISSER :
# L'encyclopédie ICT Section 2.2 définit les Killzones :
#   - London KZ : 02:00-05:00 (3h)
#   - NY AM KZ  : 07:00-10:00 (3h)
#   - London Close : 10:00-12:00 (2h)
#
# Un setup ICT est LIÉ À SA KILLZONE. Un MSS + FVG détecté dans la London KZ
# à 03:30 n'est plus pertinent à 07:30 dans la NY KZ — c'est une SESSION
# DIFFÉRENTE avec sa propre logique AMD (Section 5.1).
#
# Le Judas Swing dure 15-45 minutes (Section 5.3). Le cycle AMD complet
# (Accumulation → Manipulation → Distribution) dure ~2-3h au maximum.
# Un signal ICT qui n'a pas été exécuté en 3h a RATÉ son timing.
#
# Exception : les Silver Bullet windows sont 1h seulement (Section 2.4),
# mais le profil ICT Strict englobe plus que le SB.
#
# VALEUR RETENUE : 3h (10800s)
# Variante agressive : 2h pour les Silver Bullet purs
#
#
# ── Elliott Wave : 12h → 24h ──
#
# Pourquoi AUGMENTER :
# L'encyclopédie Elliott Section 15 (contraintes temporelles) montre que
# les relations temporelles entre vagues respectent des ratios Fibonacci :
#   - T(V2)/T(V1) = 0.382-0.618
#   - T(V5)/T(V1) = 0.618-1.0
#
# Section K.2 : les zones temporelles de retournement sont calculées sur
# des projections multi-bougies H4/D1. Un comptage Elliott identifiant
# "début de vague 3" sur H4 reste valide pendant PLUSIEURS bougies H4.
#
# Section J.2 : la confirmation post-impulsion exige un retracement de
# 38.2% en MOINS DE TEMPS que l'impulsion entière → on parle de cycles
# de plusieurs heures à plusieurs jours.
#
# Un comptage H4 produit un signal qui reste structurellement valide
# tant que le "Point of No Return" (Section J.4) n'est pas atteint.
# 12h = seulement 3 bougies H4, ce qui est TROP COURT pour un comptage
# qui opère sur des structures de 8-20 bougies H4.
#
# VALEUR RETENUE : 24h (86400s)
# Condition d'invalidation PRÉCOCE : si le prix touche le niveau
# d'invalidation Elliott (origine de vague 1 ou zone de vague 1),
# le signal est IMMÉDIATEMENT annulé, indépendamment du TTL restant.
#
#
# ── Pure Price Action : 10 min → 30 min ──
#
# Pourquoi AUGMENTER :
# 10 minutes est TROP COURT même pour du M5. Un MSS + FVG sur M5
# nécessite un retour dans le FVG pour l'entrée (ICT Section 5.5,
# étape 4 : "retrait dans le FVG"). Ce retour prend souvent 3-6
# bougies M5, soit 15-30 minutes.
#
# L'encyclopédie ICT Section 2.3 montre que même les Macros
# algorithmiques durent 20 minutes chacune. Un signal PA sur M5
# doit survivre au moins à une Macro complète.
#
# VALEUR RETENUE : 30 min (1800s)
# Pour du M15 : 45 min (2700s)
#

# Valeurs implémentables
PROFILE_TTL_SECONDS = {
    "ict_strict":   10800,   # 3h — durée d'une Killzone
    "elliott":      86400,   # 24h — cycle H4/D1 complet
    "vsa_wyckoff":  28800,   # 8h — inchangé, cohérent D1
    "pure_pa":      1800,    # 30 min — M5/M15 avec retour FVG
    "custom":       21600,   # 6h — inchangé
}

# Variantes par sous-type de setup ICT
ICT_TTL_BY_SETUP = {
    "silver_bullet":    7200,   # 2h — fenêtre SB = 1h, extension 1h
    "model_2022":       10800,  # 3h — cycle AMD complet
    "judas_swing":      5400,   # 1.5h — le Judas est rapide
    "unicorn":          10800,  # 3h — rare mais valide sur la KZ
    "turtle_soup":      7200,   # 2h — réintégration rapide attendue
}

# Variantes par position Elliott dans le comptage
ELLIOTT_TTL_BY_WAVE = {
    "wave_3_start":     86400,  # 24h — la plus longue, la plus fiable
    "wave_5_start":     43200,  # 12h — fin de tendance, plus urgent
    "correction_end":   57600,  # 16h — ABC terminé, impulsion attendue
    "wave_c_terminal":  28800,  # 8h — ending diagonal, retournement rapide
}

# Invalidation précoce Elliott (indépendante du TTL)
# Si le prix atteint ces niveaux → signal tué immédiatement
ELLIOTT_KILL_LEVELS = {
    "in_wave_3":   "origin_wave_1",    # Si prix < début V1 → comptage mort
    "in_wave_5":   "end_wave_1",       # Si prix < fin V1 → overlap V4/V1
    "post_abc":    "end_wave_c",       # Si prix repasse C → correction continue
}


# =============================================================================
# 2. SEUIL D'ACTIVATION — CALIBRATION PAR PHASE
# =============================================================================
#
# 0.45 sur [-1, +1] est un seuil RAISONNABLE mais pas optimal pour
# toutes les situations. Voici pourquoi et comment l'ajuster.
#
# PROBLÈME avec un seuil fixe :
# - En paper trading initial, tu veux MAXIMISER le nombre de trades
#   pour collecter des données pour le Meta-Learner (Problème 4).
#   Un seuil trop strict = pas assez de samples en 3 mois.
# - En live trading, tu veux MINIMISER les faux positifs.
#
# SOLUTION : seuil dynamique par phase + par régime
#

ACTIVATION_THRESHOLDS = {
    # Phase 1 : Paper trading (collecte de données)
    # Objectif : 8-12 trades/semaine pour avoir 100+ samples en 3 mois
    "paper_trading": {
        "base_threshold": 0.35,          # Plus laxiste pour collecter
        "min_profiles_aligned": 2,        # Au moins 2 profils (pas 3)
        "crowding_override": False,       # Log le crowding mais ne bloque pas
    },

    # Phase 2 : Paper trading avancé (après 80+ samples, Meta-Learner actif)
    "paper_advanced": {
        "base_threshold": 0.42,
        "min_profiles_aligned": 2,
        "crowding_override": True,        # Le crowding bloque maintenant
    },

    # Phase 3 : Live trading
    "live": {
        "base_threshold": 0.50,           # Plus strict
        "min_profiles_aligned": 3,        # Minimum 3 profils
        "crowding_override": True,
    },
}

# Ajustement par régime de marché
THRESHOLD_REGIME_ADJUSTMENT = {
    "trending":   -0.05,   # Trending = plus facile, on peut être plus laxiste
    "ranging":    +0.08,   # Ranging = dangereux, on exige plus de convergence
    "volatile":   +0.10,   # Volatile = très dangereux, seuil élevé
}

# Ajustement par session
THRESHOLD_SESSION_ADJUSTMENT = {
    "london_kz":      -0.03,   # Haute liquidité = bons signaux
    "ny_am_kz":       -0.03,   # Idem
    "ny_lunch":       +0.05,   # London Close/NY Lunch = chop
    "asia":           +0.08,   # Faible liquidité = signaux moins fiables
    "off_session":    +0.12,   # Hors session = méfiance maximale
}


def compute_dynamic_threshold(
    phase: str,
    regime: str,
    session: str,
) -> float:
    """
    Calcule le seuil d'activation dynamique.

    Exemple :
      paper_trading + trending + london_kz = 0.35 - 0.05 - 0.03 = 0.27
      live + volatile + asia = 0.50 + 0.10 + 0.08 = 0.68
    """
    base = ACTIVATION_THRESHOLDS[phase]["base_threshold"]
    regime_adj = THRESHOLD_REGIME_ADJUSTMENT.get(regime, 0)
    session_adj = THRESHOLD_SESSION_ADJUSTMENT.get(session, 0)

    threshold = base + regime_adj + session_adj

    # Clamp entre 0.20 et 0.75
    return max(0.20, min(0.75, round(threshold, 3)))


# =============================================================================
# 3. RÈGLE SL/TP EN CONVERGENCE MULTI-PROFILS
# =============================================================================
#
# PROBLÈME : ICT dit SL sous l'OB, Elliott dit SL sous l'origine de V1,
# Pure PA dit SL sous le FVG. Lequel prendre ?
#
# RÉPONSE : AUCUN ne "gagne" — on applique la règle du SL STRUCTUREL
# LE PLUS LARGE avec une logique défendable.
#
# ── Raisonnement ──
#
# L'encyclopédie ICT Section 10.1 dit :
#   "SL sous le Low de l'Order Block — si l'OB est cassé → Setup invalide"
#   "SL sous le bas du FVG — si le FVG est comblé vers le bas → Trade invalide"
#
# L'encyclopédie Elliott Section J.4 dit :
#   "Pour chaque comptage, définir un niveau d'invalidation :
#    Si vague 2 supposée terminée → invalidation = origine de vague 1"
#
# ICT Section 14.6 (erreur n°7 de la communauté) :
#   "Placer le SL trop près — Le prix revient toujours respirer
#    dans les zones avant de partir"
#
# ── RÈGLE IMPLÉMENTABLE ──
#
# 1. Collecter les 3 niveaux SL de chaque profil actif
# 2. Prendre le SL le plus éloigné du prix d'entrée (le plus large)
# 3. Ajouter un buffer de 2-3 pips (spread + respiration)
# 4. Vérifier que le R:R résultant ≥ 1:2 minimum (ICT Section 12, Étape 5)
# 5. Si R:R < 1:2 → RÉDUIRE LA TAILLE, pas le SL
#
# POURQUOI LE PLUS LARGE ?
#
# a) L'invalidation Elliott (origine V1) est le niveau où TOUTE la thèse
#    est morte. Si le prix touche ça, les 3 profils sont faux.
#    C'est le "point of no return" (Elliott Section J.4).
#
# b) ICT Section 11.2 note que les institutions manipulent les stops
#    proches. Le SL large survit au "stop hunt" que le SL sous FVG ne
#    survit pas.
#
# c) Le SL sous l'OB est souvent ENTRE le SL FVG et le SL Elliott.
#    C'est le compromis naturel.
#
# d) Prendre le plus serré = risquer d'être stoppé par un Judas Swing
#    (Section 5.3 : 15-45 minutes de manipulation) alors que la thèse
#    reste intacte.
#
# ── EXCEPTION : Le SL le plus large ne doit pas excéder 2× ATR(14) ──
# Si c'est le cas, le trade n'a pas un bon profil risque → skip.
#

class StopLossLevel:
    """Niveau SL proposé par un profil."""
    def __init__(self, profile_id: str, sl_price: float, reason: str):
        self.profile_id = profile_id
        self.sl_price = sl_price
        self.reason = reason


def compute_convergence_sl(
    entry_price: float,
    direction: int,               # +1 long, -1 short
    sl_proposals: List[StopLossLevel],
    atr_14: float,
    spread_pips: float = 2.0,
    pip_value: float = 0.0001,    # 0.0001 pour forex, 0.01 pour XAUUSD
    max_sl_atr_multiple: float = 2.0,
    min_rr_ratio: float = 2.0,
) -> dict:
    """
    Calcule le SL de convergence multi-profils.

    Règle : prendre le SL le plus large (le plus protecteur),
    avec un cap à 2× ATR(14) et un minimum R:R de 1:2.

    Returns:
        {
            "sl_price": float,
            "source_profile": str,
            "reason": str,
            "distance_pips": float,
            "atr_multiple": float,
            "valid": bool,
            "rejection_reason": str or None,
        }
    """
    if not sl_proposals:
        return {"valid": False, "rejection_reason": "Aucun SL proposé"}

    # Trier : pour un LONG, le SL le plus bas est le plus large
    # Pour un SHORT, le SL le plus haut est le plus large
    if direction == 1:  # LONG
        widest = min(sl_proposals, key=lambda s: s.sl_price)
    else:  # SHORT
        widest = max(sl_proposals, key=lambda s: s.sl_price)

    sl_price = widest.sl_price

    # Buffer spread + respiration
    buffer = spread_pips * pip_value + 3 * pip_value  # +3 pips de marge
    if direction == 1:
        sl_price -= buffer
    else:
        sl_price += buffer

    # Distance en pips
    distance = abs(entry_price - sl_price) / pip_value
    atr_pips = atr_14 / pip_value
    atr_multiple = distance / atr_pips if atr_pips > 0 else 99

    # Check : SL ne doit pas excéder max_sl_atr_multiple × ATR
    if atr_multiple > max_sl_atr_multiple:
        return {
            "valid": False,
            "rejection_reason": (
                f"SL trop large : {atr_multiple:.1f}× ATR > {max_sl_atr_multiple}× ATR. "
                f"Distance = {distance:.1f} pips. Skip ce trade."
            ),
            "sl_price": sl_price,
            "source_profile": widest.profile_id,
            "distance_pips": round(distance, 1),
            "atr_multiple": round(atr_multiple, 2),
        }

    return {
        "valid": True,
        "sl_price": round(sl_price, 5),
        "source_profile": widest.profile_id,
        "reason": widest.reason,
        "distance_pips": round(distance, 1),
        "atr_multiple": round(atr_multiple, 2),
        "rejection_reason": None,
        "all_proposals": [
            {
                "profile": s.profile_id,
                "sl_price": s.sl_price,
                "reason": s.reason,
            }
            for s in sl_proposals
        ],
    }


# ── TP EN CONVERGENCE ──
#
# Pour le TP, c'est l'INVERSE : on prend le TP le plus CONSERVATEUR
# (le plus proche), car c'est le premier obstacle.
#
# Logique :
# - ICT TP = prochain Draw on Liquidity (PDH, EQH, Std Dev -2.0)
# - Elliott TP = cible de vague (ex: V3 = 138-162% de V1)
# - Pure PA TP = prochain swing high/low
#
# Si ICT vise PDH à 1.0950 et Elliott vise V3 cible à 1.0920,
# le premier obstacle est 1.0920 → c'est le TP1.
#
# Stratégie de prise de profits partiels (calquée sur ICT Section 10.3) :
#   - TP1 (33%) = TP le plus conservateur (premier obstacle)
#   - TP2 (33%) = TP médian
#   - TP3 (34%) = TP le plus ambitieux
#   - Move SL to break-even après TP1

def compute_convergence_tp(
    entry_price: float,
    direction: int,
    tp_proposals: List[dict],  # [{"profile": str, "tp_price": float}]
) -> dict:
    """
    Calcule les niveaux TP en convergence.

    Règle : split en 3 partiels, du plus conservateur au plus ambitieux.
    """
    if not tp_proposals:
        return {"valid": False}

    prices = [t["tp_price"] for t in tp_proposals]

    if direction == 1:  # LONG → TP = prix au-dessus de l'entrée
        prices = sorted([p for p in prices if p > entry_price])
    else:  # SHORT → TP = prix en-dessous
        prices = sorted([p for p in prices if p < entry_price], reverse=True)

    if not prices:
        return {"valid": False}

    if len(prices) == 1:
        return {
            "valid": True,
            "tp1": {"price": prices[0], "pct": 100},
            "tp2": None,
            "tp3": None,
        }

    if len(prices) == 2:
        return {
            "valid": True,
            "tp1": {"price": prices[0], "pct": 50},
            "tp2": {"price": prices[1], "pct": 50},
            "tp3": None,
        }

    return {
        "valid": True,
        "tp1": {"price": prices[0], "pct": 33},
        "tp2": {"price": prices[len(prices) // 2], "pct": 33},
        "tp3": {"price": prices[-1], "pct": 34},
        "move_sl_to_be_after_tp1": True,
    }


# =============================================================================
# 4. RÈGLE DE CONFLIT DIRECTIONNEL
# =============================================================================
#
# PROBLÈME : ICT dit BUY (MSS haussier dans FVG, London KZ) et Elliott
# dit SELL (fin de vague 5, divergence oscillateur).
#
# Le signal le plus récent écrase-t-il l'ancien ?
# → NON. Aucun des deux ne "gagne" par ancienneté.
#
# ── Raisonnement depuis les encyclopédies ──
#
# L'encyclopédie Elliott Section L.3 (Signaux de Conflit) est explicite :
#   "Elliott dit 'on est en vague 3 haussière' mais ICT dit 'biais HTF
#    bearish' → -30% confiance"
#   "Elliott dit 'correction pas terminée' mais ICT donne un signal
#    EXECUTE → -20% confiance"
#
# L'encyclopédie ICT Section 14.6 (erreur n°4 de la communauté) :
#   "Ignorer le HTF — Si D1 est bearish, ne jamais acheter sur M5
#    parce que c'est beau"
#
# Ces deux règles convergent vers un même principe : le TIMEFRAME
# SUPÉRIEUR A PRIORITÉ sur le timeframe inférieur.
#
# ── RÈGLE IMPLÉMENTABLE (3 cas) ──
#
# CAS 1 — Conflit HTF vs LTF (cas le plus fréquent)
#   Elliott (H4/D1) dit SELL, ICT/Pure PA (M5/M15) dit BUY
#   → Le HTF gagne. Le signal LTF est un CONTRE-TENDANCE.
#   → Action : NO-GO. Ne pas trader contre la structure HTF.
#
# CAS 2 — Conflit même timeframe (rare)
#   Elliott et ICT sont sur le même horizon et en désaccord.
#   → Les deux s'ANNULENT. Score de convergence → ~0.
#   → Action : NO-GO. Attendre que le conflit se résolve.
#
# CAS 3 — Conflit "timing" (le plus nuancé)
#   Elliott dit "on est en fin de vague 3" (=bientôt correction)
#   ICT dit "MSS haussier frais" (=continuation)
#   → Ce n'est pas un conflit de DIRECTION mais de TIMING.
#   → Le score de convergence pénalise naturellement (Elliott tire
#     vers neutre, ICT tire vers long → score dilué).
#   → Action : GO seulement si score > seuil ÉLEVÉ (0.55+).
#
# IMPORTANT : on ne fait JAMAIS "le plus récent gagne" parce que
# l'ancienneté n'a AUCUNE signification structurelle.
# Un comptage Elliott émis il y a 8h sur H4 est plus valide
# qu'un MSS émis il y a 30 secondes sur M1 si le HTF le contredit.
#

class ConflictType(Enum):
    NO_CONFLICT = "no_conflict"
    HTF_VS_LTF = "htf_vs_ltf"           # HTF gagne toujours
    SAME_TF = "same_tf_conflict"          # Annulation mutuelle
    TIMING_MISMATCH = "timing_mismatch"   # Pénalité score
    PARTIAL_AGREEMENT = "partial"         # Certains alignés, d'autres non


# Hiérarchie des timeframes par profil
PROFILE_TF_HIERARCHY = {
    # Profil → timeframe de la DÉCISION (pas de l'entrée)
    "elliott":      4,   # H4/D1 = niveau 4 (le plus haut)
    "vsa_wyckoff":  3,   # H4/D1 contexte = niveau 3
    "custom":       2,   # Variable, on assume H1 = niveau 2
    "ict_strict":   2,   # Structure H1, entrée M5 = niveau 2
    "pure_pa":      1,   # M5/M15 = niveau 1 (le plus bas)
}


def resolve_directional_conflict(
    signals: List[dict],  # [{"profile_id": str, "direction": +1/-1, "tf_level": int}]
) -> dict:
    """
    Résout les conflits directionnels entre profils.

    Règle :
    1. Grouper par direction
    2. Si tous alignés → NO_CONFLICT
    3. Si conflit HTF vs LTF → HTF gagne, LTF est ignoré
    4. Si même TF → annulation
    5. Si timing mismatch → pénalité

    Returns:
        {
            "conflict_type": ConflictType,
            "recommended_direction": int or None,
            "confidence_penalty": float,  # 0.0 à 1.0 (multiplicateur)
            "explanation": str,
            "htf_direction": int or None,
            "ltf_direction": int or None,
        }
    """
    if not signals:
        return {
            "conflict_type": ConflictType.NO_CONFLICT,
            "recommended_direction": None,
            "confidence_penalty": 0.0,
            "explanation": "Aucun signal actif",
        }

    directions = set(s["direction"] for s in signals)

    # Cas trivial : tous alignés
    if len(directions) == 1:
        return {
            "conflict_type": ConflictType.NO_CONFLICT,
            "recommended_direction": signals[0]["direction"],
            "confidence_penalty": 1.0,  # Pas de pénalité
            "explanation": "Tous les profils alignés",
        }

    # Séparer HTF et LTF
    htf_signals = [s for s in signals if s["tf_level"] >= 3]  # H4/D1
    ltf_signals = [s for s in signals if s["tf_level"] <= 2]   # H1/M5/M15

    htf_dirs = set(s["direction"] for s in htf_signals) if htf_signals else set()
    ltf_dirs = set(s["direction"] for s in ltf_signals) if ltf_signals else set()

    # CAS 1 — Conflit HTF vs LTF
    if htf_dirs and ltf_dirs and htf_dirs != ltf_dirs:
        if len(htf_dirs) == 1:
            htf_dir = htf_signals[0]["direction"]
            return {
                "conflict_type": ConflictType.HTF_VS_LTF,
                "recommended_direction": htf_dir,
                "confidence_penalty": 0.50,  # -50% confiance
                "explanation": (
                    f"Conflit HTF vs LTF. HTF = {'LONG' if htf_dir > 0 else 'SHORT'}, "
                    f"LTF = direction opposée. HTF prévaut mais confiance réduite de 50%. "
                    f"Recommandation : NO-GO sauf score très élevé."
                ),
                "htf_direction": htf_dir,
                "ltf_direction": list(ltf_dirs - htf_dirs)[0] if ltf_dirs - htf_dirs else None,
            }

    # CAS 2 — Conflit au même niveau TF
    # Si les signaux HTF eux-mêmes sont en conflit
    if len(htf_dirs) > 1:
        return {
            "conflict_type": ConflictType.SAME_TF,
            "recommended_direction": None,  # Annulation
            "confidence_penalty": 0.0,  # Score = 0
            "explanation": (
                "Conflit entre profils HTF (ex: Elliott vs VSA sur H4). "
                "Annulation mutuelle. Action : NO-GO, attendre résolution."
            ),
        }

    # CAS 3 — Conflit limité aux LTF (HTF unanime ou absent)
    if htf_dirs and len(htf_dirs) == 1:
        htf_dir = htf_signals[0]["direction"]
        return {
            "conflict_type": ConflictType.PARTIAL_AGREEMENT,
            "recommended_direction": htf_dir,
            "confidence_penalty": 0.70,  # -30% confiance
            "explanation": (
                f"HTF unanime {'LONG' if htf_dir > 0 else 'SHORT'}, "
                f"LTF en conflit. Suivre le HTF avec confiance réduite."
            ),
        }

    # CAS 4 — Pas de HTF, conflit LTF seulement
    return {
        "conflict_type": ConflictType.TIMING_MISMATCH,
        "recommended_direction": None,
        "confidence_penalty": 0.30,  # Très faible confiance
        "explanation": (
            "Conflit LTF sans guidance HTF. "
            "Recommandation : attendre un signal HTF pour trancher."
        ),
    }


# =============================================================================
# MATRICE DE CONFLUENCE ICT × ELLIOTT (bonus/malus)
# =============================================================================
# Directement tirée de l'encyclopédie Elliott Section L.1 et L.2
#

CONFLUENCE_BONUSES = {
    # (contexte_elliott, contexte_ict) → multiplicateur de confiance
    ("wave_3_start", "mss_fvg_in_ote"):          1.25,  # +25% — Section L.2
    ("wave_5_truncated", "smt_divergence"):        1.30,  # +30% — Section L.2
    ("correction_ended", "sweep_displacement"):    1.25,  # +25% — Section L.2
    ("wave_4_triangle", "consolidation_ob"):       1.15,  # +15% — convergence naturelle
    ("wave_2_zigzag", "judas_swing_reversal"):     1.20,  # +20% — fin de manipulation
}

CONFLUENCE_PENALTIES = {
    # (contexte_elliott, contexte_ict) → multiplicateur de confiance
    ("wave_3_bullish", "htf_bearish_bias"):        0.70,  # -30% — Section L.3
    ("correction_not_done", "execute_signal"):      0.80,  # -20% — Section L.3
    ("wave_5_ending", "continuation_signal"):       0.60,  # -40% — épuisement vs continuation
    ("ending_diagonal", "breakout_signal"):         0.50,  # -50% — diagonal = fin imminente
}


# =============================================================================
# INTÉGRATION : FONCTION D'ÉVALUATION COMPLÈTE
# =============================================================================

def evaluate_with_calibration(
    signals: List[dict],
    phase: str = "paper_trading",
    regime: str = "trending",
    session: str = "ny_am_kz",
    elliott_context: str = None,
    ict_context: str = None,
) -> dict:
    """
    Point d'entrée calibré qui intègre les 4 calibrations.

    Workflow :
    1. Vérifier les conflits directionnels
    2. Calculer le seuil dynamique
    3. Appliquer les bonus/malus de confluence
    4. Décision GO/NO-GO
    """
    # 1. Conflits
    conflict = resolve_directional_conflict(signals)

    if conflict["conflict_type"] == ConflictType.SAME_TF:
        return {
            "decision": "NO-GO",
            "reason": "Conflit HTF non résolu — annulation",
            "conflict": conflict,
        }

    # 2. Seuil dynamique
    threshold = compute_dynamic_threshold(phase, regime, session)

    # 3. Confluence bonus/malus
    confluence_multiplier = 1.0
    if elliott_context and ict_context:
        key = (elliott_context, ict_context)
        if key in CONFLUENCE_BONUSES:
            confluence_multiplier = CONFLUENCE_BONUSES[key]
        elif key in CONFLUENCE_PENALTIES:
            confluence_multiplier = CONFLUENCE_PENALTIES[key]

    # 4. Score effectif
    # (dans la vraie implémentation, ce score vient du DynamicScorer)
    # Ici on montre la logique d'intégration
    effective_penalty = conflict["confidence_penalty"] * confluence_multiplier

    return {
        "threshold": threshold,
        "conflict": conflict,
        "confluence_multiplier": confluence_multiplier,
        "effective_confidence_penalty": round(effective_penalty, 3),
        "phase": phase,
        "regime": regime,
        "session": session,
        "note": (
            "Le score du DynamicScorer est multiplié par "
            f"effective_penalty ({effective_penalty:.3f}) avant comparaison "
            f"au seuil ({threshold:.3f})"
        ),
    }


# =============================================================================
# DEMO
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("CALIBRATION MULTI-PROFILS — Tests")
    print("=" * 70)

    # Test 1 : TTL
    print("\n── 1. TTL par profil ──")
    for profile, ttl in PROFILE_TTL_SECONDS.items():
        hours = ttl / 3600
        print(f"  {profile:15s} : {ttl:6d}s = {hours:.1f}h")

    # Test 2 : Seuils dynamiques
    print("\n── 2. Seuils dynamiques ──")
    test_cases = [
        ("paper_trading", "trending", "london_kz"),
        ("paper_trading", "ranging", "asia"),
        ("live", "trending", "ny_am_kz"),
        ("live", "volatile", "off_session"),
    ]
    for phase, regime, session in test_cases:
        t = compute_dynamic_threshold(phase, regime, session)
        print(f"  {phase:20s} + {regime:10s} + {session:15s} → seuil = {t:.3f}")

    # Test 3 : SL convergence
    print("\n── 3. SL convergence (XAUUSD LONG entry @ 2650) ──")
    proposals = [
        StopLossLevel("ict_strict", 2641.50, "SL sous OB H1"),
        StopLossLevel("elliott",    2635.00, "SL sous origine vague 1"),
        StopLossLevel("pure_pa",    2644.20, "SL sous FVG M15"),
    ]
    result = compute_convergence_sl(
        entry_price=2650.0,
        direction=1,
        sl_proposals=proposals,
        atr_14=18.5,
        pip_value=0.01,  # XAUUSD pip = 0.01
        spread_pips=2.5,
    )
    print(f"  SL retenu    : {result.get('sl_price')}")
    print(f"  Source       : {result.get('source_profile')} — {result.get('reason')}")
    print(f"  Distance     : {result.get('distance_pips')} pips")
    print(f"  ATR multiple : {result.get('atr_multiple')}×")
    print(f"  Valide       : {result.get('valid')}")
    if result.get("all_proposals"):
        print(f"  Tous les SL  :")
        for p in result["all_proposals"]:
            print(f"    {p['profile']:15s} : {p['sl_price']} ({p['reason']})")

    # Test 4 : Conflit directionnel
    print("\n── 4. Conflit directionnel ──")

    # Cas : Elliott H4 SELL vs ICT M15 BUY
    conflict = resolve_directional_conflict([
        {"profile_id": "elliott", "direction": -1, "tf_level": 4},
        {"profile_id": "vsa_wyckoff", "direction": -1, "tf_level": 3},
        {"profile_id": "ict_strict", "direction": 1, "tf_level": 2},
        {"profile_id": "pure_pa", "direction": 1, "tf_level": 1},
    ])
    print(f"  Type         : {conflict['conflict_type'].value}")
    print(f"  Direction    : {conflict['recommended_direction']}")
    print(f"  Pénalité     : {conflict['confidence_penalty']}")
    print(f"  Explication  : {conflict['explanation']}")

    # Test 5 : Évaluation calibrée complète
    print("\n── 5. Évaluation calibrée ──")
    eval_result = evaluate_with_calibration(
        signals=[
            {"profile_id": "elliott", "direction": 1, "tf_level": 4},
            {"profile_id": "ict_strict", "direction": 1, "tf_level": 2},
            {"profile_id": "pure_pa", "direction": 1, "tf_level": 1},
        ],
        phase="paper_trading",
        regime="trending",
        session="ny_am_kz",
        elliott_context="wave_3_start",
        ict_context="mss_fvg_in_ote",
    )
    print(f"  Seuil        : {eval_result['threshold']}")
    print(f"  Confluence   : ×{eval_result['confluence_multiplier']}")
    print(f"  Pénalité eff : {eval_result['effective_confidence_penalty']}")
    print(f"  Note         : {eval_result['note']}")
