"""
Elliott Wave Counter — Détection algorithmique des vagues Elliott
=================================================================
Approche : 100% algorithmique, zéro LLM.
Basé sur l'Encyclopédie Elliott Wave v1.0 (1193 lignes)

Le wave counter :
1. Détecte les pivots (zigzag filter) sur les données OHLCV
2. Identifie les séquences 5-vagues (impulsions) candidates
3. Identifie les séquences 3-vagues (corrections ABC) candidates
4. Retourne les comptages triés par score pour validation ultérieure
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


# ============================================================
# ENUMS & DATACLASSES
# ============================================================

class WaveType(Enum):
    IMPULSE = "impulse"       # 5 vagues motrices
    CORRECTION = "correction" # 3 vagues correctives (ABC)
    DIAGONAL = "diagonal"     # 5 vagues diagonales (leading/ending)
    UNKNOWN = "unknown"


class WaveDirection(Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"


class CorrectionType(Enum):
    ZIGZAG = "zigzag"         # 5-3-5
    FLAT = "flat"             # 3-3-5
    TRIANGLE = "triangle"     # 3-3-3-3-3
    DOUBLE_ZIGZAG = "double_zigzag"  # W-X-Y
    UNKNOWN = "unknown"


@dataclass
class Pivot:
    """Un point pivot (swing high ou swing low)."""
    index: int          # Index dans le DataFrame
    price: float        # Prix du pivot
    time: str           # Timestamp
    pivot_type: str     # "high" ou "low"
    bar_index: int = 0  # Index de la barre dans le DF


@dataclass
class Wave:
    """Une vague individuelle dans un comptage."""
    label: str          # "1", "2", "3", "4", "5" ou "A", "B", "C"
    start: Pivot        # Pivot de début
    end: Pivot          # Pivot de fin
    direction: str      # "up" ou "down"
    price_range: float  # |end.price - start.price|
    duration: int       # Nombre de barres
    sub_waves: int = 0  # Nombre de sous-vagues détectées


@dataclass
class WaveCount:
    """Un comptage complet (impulsion ou correction)."""
    wave_type: WaveType
    direction: WaveDirection
    waves: List[Wave]           # Liste des vagues [W1, W2, W3, W4, W5] ou [A, B, C]
    pivots: List[Pivot]         # Les pivots utilisés (6 pour impulsion, 4 pour ABC)
    score: float = 0.0          # Score /100
    valid: bool = True          # Passe les règles absolues
    invalidation_reasons: List[str] = field(default_factory=list)
    details: Dict = field(default_factory=dict)


# ============================================================
# HYPERPARAMÈTRES (Section M de l'encyclopédie)
# ============================================================

PARAMS = {
    # Règles absolues (Sec 2.1 — inchangé)
    "MAX_RETRACE_W2": 0.999,
    "W3_NOT_SHORTEST": True,
    "W4_NO_OVERLAP_W1": True,
    
    # Fibonacci prix (Sec 7)
    "W2_RETRACE_TYPICAL": (0.50, 0.618),
    "W2_RETRACE_EXTENDED": (0.236, 0.786),
    "W4_RETRACE_TYPICAL": (0.236, 0.382),
    "W4_RETRACE_EXTENDED": (0.146, 0.50),
    "W3_EXTENSION_MIN": 1.382,
    "W5_TARGET_IF_W3_EXT": (0.618, 1.0),
    
    # Corrections (Sec 13)
    "FLAT_B_MIN_RETRACE": 0.90,
    "ZIGZAG_B_MAX_RETRACE": 0.99,
    "ZIGZAG_B_TYPICAL": (0.382, 0.786),
    
    # Temps (Sec 15/E)
    "MIN_TIME_RATIO_W2_W1": 0.10,
    "MAX_TIME_DISP_SAME_DEG": 8.0,    # Assoupli de 5.0 à 8.0
    
    # Scoring
    "MIN_SCORE_TO_TRADE": 65,
    
    # Pivot detection (inchangé)
    "ZIGZAG_PCT_DEFAULT": 0.005,
    "ZIGZAG_PCT_ADAPTIVE": True,
    "ATR_PERIOD": 14,
    "MIN_PIVOTS_FOR_IMPULSE": 6,
    "MIN_PIVOTS_FOR_CORRECTION": 4,
}


# ============================================================
# DÉTECTION DES PIVOTS (Zigzag Filter)
# ============================================================

def detect_pivots(df: pd.DataFrame, 
                  zigzag_pct: float = None,
                  atr_multiplier: float = 0.5) -> List[Pivot]:
    """
    Détecte les pivots significatifs avec un filtre zigzag adaptatif.
    
    Le zigzag filtre les mouvements < X% (ou X * ATR) pour ne garder
    que les pivots significatifs. C'est la base du comptage Elliott.
    
    Args:
        df: DataFrame avec colonnes ['time', 'open', 'high', 'low', 'close']
        zigzag_pct: Pourcentage minimum de mouvement (None = adaptatif via ATR)
        atr_multiplier: Multiplicateur ATR pour le seuil adaptatif
    
    Returns:
        Liste de Pivot triés chronologiquement
    """
    if len(df) < 20:
        return []
    
    highs = df['high'].values.astype(float)
    lows = df['low'].values.astype(float)
    times = df['time'].dt.strftime('%Y-%m-%d %H:%M').values if hasattr(df['time'], 'dt') else df['time'].values
    
    # Calculer le seuil adaptatif via ATR si pas de zigzag_pct fixe
    if zigzag_pct is None:
        atr = _calculate_atr(df, PARAMS["ATR_PERIOD"])
        avg_price = df['close'].mean()
        zigzag_pct = max(atr * atr_multiplier / avg_price, 0.002)  # Min 0.2%
    
    # Algorithme Zigzag
    pivots = []
    
    # Trouver le premier pivot (plus haut ou plus bas des N premières barres)
    lookback = min(10, len(df) // 4)
    first_high_idx = int(np.argmax(highs[:lookback]))
    first_low_idx = int(np.argmin(lows[:lookback]))
    
    # Commencer par le plus ancien des deux
    if first_high_idx <= first_low_idx:
        # Premier pivot est un high
        current_type = "high"
        current_idx = first_high_idx
        current_price = highs[first_high_idx]
    else:
        current_type = "low"
        current_idx = first_low_idx
        current_price = lows[first_low_idx]
    
    pivots.append(Pivot(
        index=len(pivots),
        price=current_price,
        time=str(times[current_idx]),
        pivot_type=current_type,
        bar_index=current_idx
    ))
    
    # Parcourir les barres
    for i in range(current_idx + 1, len(df)):
        if current_type == "high":
            # On cherche un low significatif
            if lows[i] < current_price * (1 - zigzag_pct):
                # Mouvement significatif vers le bas → nouveau low
                current_type = "low"
                current_idx = i
                current_price = lows[i]
                pivots.append(Pivot(
                    index=len(pivots),
                    price=current_price,
                    time=str(times[current_idx]),
                    pivot_type="low",
                    bar_index=current_idx
                ))
            elif highs[i] > current_price:
                # Extension du high actuel
                current_price = highs[i]
                current_idx = i
                pivots[-1] = Pivot(
                    index=pivots[-1].index,
                    price=current_price,
                    time=str(times[current_idx]),
                    pivot_type="high",
                    bar_index=current_idx
                )
        else:  # current_type == "low"
            # On cherche un high significatif
            if highs[i] > current_price * (1 + zigzag_pct):
                # Mouvement significatif vers le haut → nouveau high
                current_type = "high"
                current_idx = i
                current_price = highs[i]
                pivots.append(Pivot(
                    index=len(pivots),
                    price=current_price,
                    time=str(times[current_idx]),
                    pivot_type="high",
                    bar_index=current_idx
                ))
            elif lows[i] < current_price:
                # Extension du low actuel
                current_price = lows[i]
                current_idx = i
                pivots[-1] = Pivot(
                    index=pivots[-1].index,
                    price=current_price,
                    time=str(times[current_idx]),
                    pivot_type="low",
                    bar_index=current_idx
                )
    
    return pivots


def _calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
    """Calcule l'Average True Range."""
    if len(df) < period + 1:
        return (df['high'] - df['low']).mean()
    
    high = df['high'].values
    low = df['low'].values
    close = df['close'].values
    
    tr = np.zeros(len(df))
    tr[0] = high[0] - low[0]
    for i in range(1, len(df)):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i-1]),
            abs(low[i] - close[i-1])
        )
    
    return float(np.mean(tr[-period:]))


# ============================================================
# IDENTIFICATION DES IMPULSIONS (5 vagues)
# ============================================================

def find_impulse_candidates(pivots: List[Pivot], 
                            direction: WaveDirection = None) -> List[WaveCount]:
    """
    Cherche toutes les séquences de 6 pivots consécutifs qui pourraient
    former une impulsion Elliott 5 vagues.
    
    Pour une impulsion BULLISH : L-H-L-H-L-H (bas→haut→bas→haut→bas→haut)
    Pour une impulsion BEARISH : H-L-H-L-H-L (haut→bas→haut→bas→haut→bas)
    
    Args:
        pivots: Liste de pivots détectés
        direction: Filtrer par direction (None = chercher les deux)
    
    Returns:
        Liste de WaveCount candidates (non validées)
    """
    candidates = []
    
    if len(pivots) < 6:
        return candidates
    
    # Chercher des séquences de 6 pivots alternés
    for start_idx in range(len(pivots) - 5):
        p = pivots[start_idx:start_idx + 6]
        
        # Vérifier l'alternance high/low
        types = [pv.pivot_type for pv in p]
        
        # Pattern bullish : L-H-L-H-L-H
        if types == ["low", "high", "low", "high", "low", "high"]:
            if direction is not None and direction != WaveDirection.BULLISH:
                continue
            candidate = _build_impulse(p, WaveDirection.BULLISH)
            if candidate:
                candidates.append(candidate)
        
        # Pattern bearish : H-L-H-L-H-L
        elif types == ["high", "low", "high", "low", "high", "low"]:
            if direction is not None and direction != WaveDirection.BEARISH:
                continue
            candidate = _build_impulse(p, WaveDirection.BEARISH)
            if candidate:
                candidates.append(candidate)
    
    return candidates


def _build_impulse(pivots: List[Pivot], direction: WaveDirection) -> Optional[WaveCount]:
    """
    Construit un WaveCount à partir de 6 pivots.
    
    Bullish: p[0]=W1_start, p[1]=W1_end/W2_start, p[2]=W2_end/W3_start, 
             p[3]=W3_end/W4_start, p[4]=W4_end/W5_start, p[5]=W5_end
    """
    p = pivots
    
    if direction == WaveDirection.BULLISH:
        # Vérifier la tendance globale : le dernier high > premier low
        if p[5].price <= p[0].price:
            return None
        
        waves = [
            Wave("1", p[0], p[1], "up", abs(p[1].price - p[0].price), 
                 p[1].bar_index - p[0].bar_index),
            Wave("2", p[1], p[2], "down", abs(p[1].price - p[2].price),
                 p[2].bar_index - p[1].bar_index),
            Wave("3", p[2], p[3], "up", abs(p[3].price - p[2].price),
                 p[3].bar_index - p[2].bar_index),
            Wave("4", p[3], p[4], "down", abs(p[3].price - p[4].price),
                 p[4].bar_index - p[3].bar_index),
            Wave("5", p[4], p[5], "up", abs(p[5].price - p[4].price),
                 p[5].bar_index - p[4].bar_index),
        ]
    else:  # BEARISH
        if p[5].price >= p[0].price:
            return None
        
        waves = [
            Wave("1", p[0], p[1], "down", abs(p[0].price - p[1].price),
                 p[1].bar_index - p[0].bar_index),
            Wave("2", p[1], p[2], "up", abs(p[2].price - p[1].price),
                 p[2].bar_index - p[1].bar_index),
            Wave("3", p[2], p[3], "down", abs(p[2].price - p[3].price),
                 p[3].bar_index - p[2].bar_index),
            Wave("4", p[3], p[4], "up", abs(p[4].price - p[3].price),
                 p[4].bar_index - p[3].bar_index),
            Wave("5", p[4], p[5], "down", abs(p[4].price - p[5].price),
                 p[5].bar_index - p[4].bar_index),
        ]
    
    # Vérifier durées > 0
    for w in waves:
        if w.duration <= 0 or w.price_range <= 0:
            return None
    
    return WaveCount(
        wave_type=WaveType.IMPULSE,
        direction=direction,
        waves=waves,
        pivots=list(pivots),
        score=0.0,
        valid=True,
    )


# ============================================================
# IDENTIFICATION DES CORRECTIONS (ABC)
# ============================================================

def find_correction_candidates(pivots: List[Pivot],
                                direction: WaveDirection = None) -> List[WaveCount]:
    """
    Cherche les séquences de 4 pivots formant une correction ABC.
    
    Correction bearish (après tendance haussière) : H-L-H-L
    Correction bullish (après tendance baissière) : L-H-L-H
    """
    candidates = []
    
    if len(pivots) < 4:
        return candidates
    
    for start_idx in range(len(pivots) - 3):
        p = pivots[start_idx:start_idx + 4]
        types = [pv.pivot_type for pv in p]
        
        # Correction bearish (descend) : H-L-H-L
        if types == ["high", "low", "high", "low"]:
            if direction is not None and direction != WaveDirection.BEARISH:
                continue
            candidate = _build_correction(p, WaveDirection.BEARISH)
            if candidate:
                candidates.append(candidate)
        
        # Correction bullish (monte) : L-H-L-H
        elif types == ["low", "high", "low", "high"]:
            if direction is not None and direction != WaveDirection.BULLISH:
                continue
            candidate = _build_correction(p, WaveDirection.BULLISH)
            if candidate:
                candidates.append(candidate)
    
    return candidates


def _build_correction(pivots: List[Pivot], direction: WaveDirection) -> Optional[WaveCount]:
    """
    Construit un WaveCount ABC à partir de 4 pivots.
    """
    p = pivots
    
    if direction == WaveDirection.BEARISH:
        # H-L-H-L : A descend, B monte, C descend
        waves = [
            Wave("A", p[0], p[1], "down", abs(p[0].price - p[1].price),
                 p[1].bar_index - p[0].bar_index),
            Wave("B", p[1], p[2], "up", abs(p[2].price - p[1].price),
                 p[2].bar_index - p[1].bar_index),
            Wave("C", p[2], p[3], "down", abs(p[2].price - p[3].price),
                 p[3].bar_index - p[2].bar_index),
        ]
    else:  # BULLISH correction (rebound)
        # L-H-L-H : A monte, B descend, C monte
        waves = [
            Wave("A", p[0], p[1], "up", abs(p[1].price - p[0].price),
                 p[1].bar_index - p[0].bar_index),
            Wave("B", p[1], p[2], "down", abs(p[1].price - p[2].price),
                 p[2].bar_index - p[1].bar_index),
            Wave("C", p[2], p[3], "up", abs(p[3].price - p[2].price),
                 p[3].bar_index - p[2].bar_index),
        ]
    
    for w in waves:
        if w.duration <= 0 or w.price_range <= 0:
            return None
    
    return WaveCount(
        wave_type=WaveType.CORRECTION,
        direction=direction,
        waves=waves,
        pivots=list(pivots),
        score=0.0,
        valid=True,
    )


# ============================================================
# COMPTAGE MULTI-DEGRÉ (chercher sur différentes échelles)
# ============================================================

def count_waves(df: pd.DataFrame, 
                max_candidates: int = 10) -> Dict[str, List[WaveCount]]:
    """
    Fonction principale — détecte les pivots à plusieurs niveaux de sensibilité
    et retourne les comptages candidats (impulsions + corrections).
    
    Args:
        df: DataFrame OHLCV avec colonnes time, open, high, low, close
        max_candidates: Nombre max de candidats à retourner par catégorie
    
    Returns:
        {
            "impulses": [WaveCount, ...],
            "corrections": [WaveCount, ...],
            "pivots": {"fine": [...], "medium": [...], "coarse": [...]}
        }
    """
    results = {
        "impulses": [],
        "corrections": [],
        "pivots": {},
    }
    
    if len(df) < 30:
        return results
    
    # Calculer ATR pour les seuils adaptatifs
    atr = _calculate_atr(df, PARAMS["ATR_PERIOD"])
    avg_price = df['close'].mean()
    
    # 3 niveaux de sensibilité (multi-degré simplifié)
    levels = {
        "fine": max(atr * 0.3 / avg_price, 0.001),     # Petits mouvements
        "medium": max(atr * 0.7 / avg_price, 0.003),    # Mouvements moyens
        "coarse": max(atr * 1.5 / avg_price, 0.008),    # Grands mouvements
    }
    
    all_impulses = []
    all_corrections = []
    
    for level_name, zigzag_pct in levels.items():
        pivots = detect_pivots(df, zigzag_pct=zigzag_pct)
        results["pivots"][level_name] = pivots
        
        if len(pivots) < 4:
            continue
        
        # Chercher les impulsions sur les DERNIERS pivots
        # (on s'intéresse à ce qui se passe maintenant)
        recent_pivots = pivots[-20:] if len(pivots) > 20 else pivots
        
        impulses = find_impulse_candidates(recent_pivots)
        for imp in impulses:
            imp.details["level"] = level_name
            imp.details["zigzag_pct"] = zigzag_pct
        all_impulses.extend(impulses)
        
        corrections = find_correction_candidates(recent_pivots)
        for corr in corrections:
            corr.details["level"] = level_name
            corr.details["zigzag_pct"] = zigzag_pct
        all_corrections.extend(corrections)
    
    # Trier par récence (le comptage le plus récent d'abord)
    all_impulses.sort(key=lambda wc: wc.pivots[-1].bar_index, reverse=True)
    all_corrections.sort(key=lambda wc: wc.pivots[-1].bar_index, reverse=True)
    
    results["impulses"] = all_impulses[:max_candidates]
    results["corrections"] = all_corrections[:max_candidates]
    
    return results


# ============================================================
# DÉTECTION DE L'ÉTAT ACTUEL (où en est-on dans le comptage ?)
# ============================================================

def detect_current_wave_position(df: pd.DataFrame) -> Dict:
    """
    Analyse les données et retourne l'état actuel du marché en termes Elliott :
    - Sommes-nous dans une impulsion ? Si oui, quelle vague ?
    - Sommes-nous dans une correction ? Si oui, quelle phase ?
    - Quel est le prochain mouvement attendu ?
    
    Returns:
        {
            "status": "impulse_w3" / "correction_b" / "unknown",
            "direction": "bullish" / "bearish",
            "current_wave": "3" / "B" / etc.,
            "next_expected": "W4 down" / "C down" / etc.,
            "best_impulse": WaveCount or None,
            "best_correction": WaveCount or None,
            "trade_signal": "BUY" / "SELL" / "NO_TRADE",
            "confidence": 0-100,
            "entry_zone": (low, high) or None,
            "invalidation": price or None,
        }
    """
    result = {
        "status": "unknown",
        "direction": "unknown",
        "current_wave": None,
        "next_expected": None,
        "best_impulse": None,
        "best_correction": None,
        "trade_signal": "NO_TRADE",
        "confidence": 0,
        "entry_zone": None,
        "invalidation": None,
        "details": {},
    }
    
    # Obtenir les comptages candidats
    counts = count_waves(df)
    
    impulses = counts.get("impulses", [])
    corrections = counts.get("corrections", [])
    
    if not impulses and not corrections:
        result["details"]["reason"] = "Pas assez de pivots pour un comptage"
        return result
    
    # Chercher le meilleur comptage qui touche le prix actuel
    current_price = df['close'].iloc[-1]
    current_bar = len(df) - 1
    
    best_impulse = None
    best_correction = None
    
    # Filtrer les comptages qui incluent des données récentes
    # (le dernier pivot doit être dans les 20% dernières barres)
    recent_threshold = int(len(df) * 0.8)
    
    for imp in impulses:
        last_bar = imp.pivots[-1].bar_index
        if last_bar >= recent_threshold:
            best_impulse = imp
            break
    
    for corr in corrections:
        last_bar = corr.pivots[-1].bar_index
        if last_bar >= recent_threshold:
            best_correction = corr
            break
    
    result["best_impulse"] = best_impulse
    result["best_correction"] = best_correction
    
    # Analyser l'impulsion si trouvée
    if best_impulse:
        _analyze_impulse_position(best_impulse, current_price, current_bar, result)
    
    # Analyser la correction si trouvée
    if best_correction:
        _analyze_correction_position(best_correction, current_price, current_bar, result)
    
    # Si on a les deux, choisir le plus pertinent
    if best_impulse and best_correction:
        # Le comptage le plus récent (dernier pivot) a priorité
        imp_last = best_impulse.pivots[-1].bar_index
        corr_last = best_correction.pivots[-1].bar_index
        if corr_last > imp_last:
            # La correction est plus récente → on est probablement en correction
            result["status"] = f"correction_{result.get('current_wave', '?').lower()}"
    
    return result


def _analyze_impulse_position(impulse: WaveCount, current_price: float, 
                               current_bar: int, result: Dict):
    """Détermine où on en est dans une impulsion et quel signal en tirer."""
    waves = impulse.waves
    last_pivot = impulse.pivots[-1]
    direction = impulse.direction
    
    # Le dernier pivot est la fin de W5
    # Si on est APRÈS le dernier pivot → l'impulsion est terminée
    # → On attend une correction
    if current_bar > last_pivot.bar_index + 5:
        result["status"] = "impulse_complete"
        result["direction"] = direction.value
        result["current_wave"] = "post-5"
        
        if direction == WaveDirection.BULLISH:
            result["next_expected"] = "Correction A-B-C bearish attendue"
            result["trade_signal"] = "SELL"
            result["entry_zone"] = None  # Attendre le setup
            result["invalidation"] = last_pivot.price  # Au-dessus de W5
        else:
            result["next_expected"] = "Correction A-B-C bullish attendue"
            result["trade_signal"] = "BUY"
            result["invalidation"] = last_pivot.price
        
        result["confidence"] = 40  # Faible car on attend encore le setup
        return
    
    # Si on est PENDANT l'impulsion → chercher où exactement
    # Vérifier si le prix est entre W4_end et W5_end
    w4_end = waves[3].end.price
    w5_end = waves[4].end.price
    w2_end = waves[1].end.price
    w3_end = waves[2].end.price
    
    result["direction"] = direction.value
    
    # Signal le plus tradeable : début de W3 (après fin de W2)
    # ou début de W5 (après fin de W4)
    w1_range = waves[0].price_range
    w3_range = waves[2].price_range
    
    if direction == WaveDirection.BULLISH:
        # Si le prix est proche de la fin de W2 → début de W3 → BUY
        if abs(current_price - w2_end) / w1_range < 0.15:
            result["status"] = "impulse_w3_start"
            result["current_wave"] = "2→3"
            result["next_expected"] = "Vague 3 haussière (la plus forte)"
            result["trade_signal"] = "BUY"
            result["entry_zone"] = (w2_end, w2_end + w1_range * 0.1)
            result["invalidation"] = waves[0].start.price  # Origine de W1
            result["confidence"] = 70
        
        # Si le prix est proche de la fin de W4 → début de W5 → BUY
        elif abs(current_price - w4_end) / w3_range < 0.15:
            result["status"] = "impulse_w5_start"
            result["current_wave"] = "4→5"
            result["next_expected"] = "Vague 5 haussière (dernière)"
            result["trade_signal"] = "BUY"
            result["entry_zone"] = (w4_end, w4_end + w1_range * 0.1)
            result["invalidation"] = waves[0].end.price  # Fin de W1 (overlap)
            result["confidence"] = 55
    else:  # BEARISH
        if abs(current_price - w2_end) / w1_range < 0.15:
            result["status"] = "impulse_w3_start"
            result["current_wave"] = "2→3"
            result["next_expected"] = "Vague 3 baissière (la plus forte)"
            result["trade_signal"] = "SELL"
            result["entry_zone"] = (w2_end - w1_range * 0.1, w2_end)
            result["invalidation"] = waves[0].start.price
            result["confidence"] = 70
        
        elif abs(current_price - w4_end) / w3_range < 0.15:
            result["status"] = "impulse_w5_start"
            result["current_wave"] = "4→5"
            result["next_expected"] = "Vague 5 baissière (dernière)"
            result["trade_signal"] = "SELL"
            result["entry_zone"] = (w4_end, w4_end + w1_range * 0.1)
            result["invalidation"] = waves[0].end.price
            result["confidence"] = 55


def _analyze_correction_position(correction: WaveCount, current_price: float,
                                  current_bar: int, result: Dict):
    """Détermine où on en est dans une correction ABC."""
    waves = correction.waves
    last_pivot = correction.pivots[-1]
    direction = correction.direction
    
    # Si la correction est terminée (on est après le dernier pivot)
    if current_bar > last_pivot.bar_index + 5:
        result["status"] = "correction_complete"
        result["current_wave"] = "post-C"
        
        # Après une correction bearish → BUY (reprise de tendance)
        if direction == WaveDirection.BEARISH:
            result["next_expected"] = "Reprise haussière attendue (nouvelle impulsion)"
            result["trade_signal"] = "BUY"
            result["invalidation"] = last_pivot.price  # Sous la fin de C
            result["confidence"] = 60
        else:
            result["next_expected"] = "Reprise baissière attendue (nouvelle impulsion)"
            result["trade_signal"] = "SELL"
            result["invalidation"] = last_pivot.price
            result["confidence"] = 60
