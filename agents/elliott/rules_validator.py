"""
Elliott Wave Rules Validator v2.0
==================================
Vérifie les 3 règles absolues et les guidelines pour chaque comptage candidat.
Toute violation d'une règle absolue → score = 0, comptage rejeté.

Sections de référence encyclopédie :
  - Sec 2.1 / Sec G : Règles absolues (R1, R2, R3)
  - Sec 13          : Corrections (zigzag, flat, expanded)
  - Sec 6 / Sec C   : Alternance (sharp vs sideways)
  - Sec 7           : Fibonacci (guidelines)
  - Sec 14 / Sec D  : Extensions et égalité
  - Sec 15 / Sec E  : Temps et proportions
"""

from typing import List, Dict, Tuple
from .wave_counter import WaveCount, WaveType, WaveDirection, PARAMS


# ============================================================
# RÈGLES ABSOLUES (Section 2.1 / Section G de l'encyclopédie)
# ============================================================

def validate_absolute_rules(wc: WaveCount) -> WaveCount:
    """
    Vérifie les 3 règles absolues pour une impulsion.
    Si une règle est violée → wc.valid = False, wc.score = 0.
    
    R1: V2 ne retrace jamais au-delà de 100% de V1
    R2: V3 ne peut pas être la plus courte des 3 vagues motrices (1, 3, 5)
    R3: V4 ne pénètre pas dans la zone de prix de V1 (sauf diagonale)
    """
    if wc.wave_type != WaveType.IMPULSE:
        return wc  # Les règles absolues sont pour les impulsions
    
    waves = wc.waves
    if len(waves) != 5:
        wc.valid = False
        wc.invalidation_reasons.append("Nombre de vagues != 5")
        return wc
    
    w1, w2, w3, w4, w5 = waves
    direction = wc.direction
    
    # ═══ R1 : V2 ne retrace pas 100% de V1 (Sec 2.1 rule 1) ═══
    if direction == WaveDirection.BULLISH:
        if w2.end.price <= w1.start.price:
            wc.valid = False
            wc.score = 0
            wc.invalidation_reasons.append(
                f"R1 VIOLÉE: V2 ({w2.end.price:.5f}) retrace au-delà de l'origine de V1 ({w1.start.price:.5f})"
            )
            return wc
    else:  # BEARISH
        if w2.end.price >= w1.start.price:
            wc.valid = False
            wc.score = 0
            wc.invalidation_reasons.append(
                f"R1 VIOLÉE: V2 ({w2.end.price:.5f}) retrace au-delà de l'origine de V1 ({w1.start.price:.5f})"
            )
            return wc
    
    # ═══ R2 : V3 n'est pas la plus courte (Sec 2.1 rule 2) ═══
    len_w1 = w1.price_range
    len_w3 = w3.price_range
    len_w5 = w5.price_range
    
    if len_w3 < len_w1 and len_w3 < len_w5:
        wc.valid = False
        wc.score = 0
        wc.invalidation_reasons.append(
            f"R2 VIOLÉE: V3 ({len_w3:.5f}) est la plus courte (V1={len_w1:.5f}, V5={len_w5:.5f})"
        )
        return wc
    
    # ═══ R3 : V4 ne chevauche pas V1 (Sec 2.1 rule 3, sauf diagonale) ═══
    if wc.wave_type == WaveType.IMPULSE:
        if direction == WaveDirection.BULLISH:
            w1_end_price = w1.end.price  # Le high de W1
            if w4.end.price < w1_end_price:
                wc.valid = False
                wc.score = 0
                wc.invalidation_reasons.append(
                    f"R3 VIOLÉE: V4 ({w4.end.price:.5f}) pénètre dans la zone de V1 (fin V1={w1_end_price:.5f})"
                )
                return wc
        else:  # BEARISH
            w1_end_price = w1.end.price  # Le low de W1
            if w4.end.price > w1_end_price:
                wc.valid = False
                wc.score = 0
                wc.invalidation_reasons.append(
                    f"R3 VIOLÉE: V4 ({w4.end.price:.5f}) pénètre dans la zone de V1 (fin V1={w1_end_price:.5f})"
                )
                return wc
    
    # Toutes les règles passent
    wc.valid = True
    return wc


# ============================================================
# VALIDATION DES CORRECTIONS (Sec 13)
# ============================================================

def validate_correction_rules(wc: WaveCount) -> WaveCount:
    """
    Vérifie les règles pour une correction ABC.
    
    Sec 13.1 : Flat — B retrace ≥ 90% de A
    Sec 13.2 : Zigzag — B < 100% de A, C dépasse A
    """
    if wc.wave_type != WaveType.CORRECTION:
        return wc
    
    waves = wc.waves
    if len(waves) != 3:
        wc.valid = False
        wc.invalidation_reasons.append("Correction doit avoir 3 vagues (A, B, C)")
        return wc
    
    wa, wb, wc_wave = waves
    
    # Ratio B/A
    if wa.price_range > 0:
        b_retrace = wb.price_range / wa.price_range
    else:
        wc.valid = False
        return wc
    
    # Classifier le type de correction (Sec 13)
    correction_type = "unknown"
    
    # Expanded flat d'abord (B > 100% de A)
    if b_retrace >= 1.0:
        correction_type = "expanded_flat"
    # Flat régulier (B ≥ 90% de A) — Sec 13.1
    elif b_retrace >= PARAMS["FLAT_B_MIN_RETRACE"]:
        correction_type = "flat"
    # Zigzag (B < 100% de A) — Sec 13.2
    elif b_retrace < PARAMS["ZIGZAG_B_MAX_RETRACE"]:
        correction_type = "zigzag"
        
        # Vérifier que C dépasse A (Sec 13.2 propriété de C)
        if wc.direction == WaveDirection.BEARISH:
            if wc_wave.end.price >= wa.end.price:
                wc.details["correction_warning"] = "C ne dépasse pas A (zigzag incomplet)"
        else:
            if wc_wave.end.price <= wa.end.price:
                wc.details["correction_warning"] = "C ne dépasse pas A (zigzag incomplet)"
    
    wc.details["correction_type"] = correction_type
    wc.details["b_retrace_ratio"] = round(b_retrace, 3)
    
    return wc


# ============================================================
# GUIDELINES (non éliminatoires, affectent le score)
# ============================================================

def check_guidelines(wc: WaveCount) -> Dict[str, any]:
    """
    Vérifie les guidelines Elliott et retourne les résultats pour le scoring.
    """
    guidelines = {}
    
    if wc.wave_type == WaveType.IMPULSE:
        guidelines = _check_impulse_guidelines(wc)
    elif wc.wave_type == WaveType.CORRECTION:
        guidelines = _check_correction_guidelines(wc)
    
    return guidelines


def _check_impulse_guidelines(wc: WaveCount) -> Dict:
    """
    Vérifie les guidelines pour une impulsion.
    Retourne un dict de métriques utilisées par le scorer v2.0.
    """
    w1, w2, w3, w4, w5 = wc.waves
    g = {}
    
    # ═══ FIBONACCI — Retracement de V2 (Sec 7.1) ═══
    if w1.price_range > 0:
        w2_retrace = w2.price_range / w1.price_range
        g["w2_retrace"] = round(w2_retrace, 4)
    else:
        g["w2_retrace"] = 0
    
    # ═══ FIBONACCI — Extension de V3 (Sec 7.2) ═══
    if w1.price_range > 0:
        w3_extension = w3.price_range / w1.price_range
        g["w3_extension"] = round(w3_extension, 4)
        g["w3_extended"] = w3_extension >= PARAMS["W3_EXTENSION_MIN"]
    else:
        g["w3_extension"] = 0
        g["w3_extended"] = False
    
    # ═══ FIBONACCI — Retracement de V4 (Sec 7.1) ═══
    if w3.price_range > 0:
        w4_retrace = w4.price_range / w3.price_range
        g["w4_retrace"] = round(w4_retrace, 4)
    else:
        g["w4_retrace"] = 0
    
    # ═══ FIBONACCI — V5/V1 ratio (Sec D.1 — Règle d'Égalité) ═══
    if w1.price_range > 0:
        w5_w1_ratio = w5.price_range / w1.price_range
        g["w5_w1_ratio"] = round(w5_w1_ratio, 4)
    else:
        g["w5_w1_ratio"] = 0
    
    # ═══ EXTENSION — Identification (Sec 14) ═══
    motive_ranges = sorted([w1.price_range, w3.price_range, w5.price_range], reverse=True)
    if len(motive_ranges) >= 2 and motive_ranges[1] > 0:
        extension_ratio = motive_ranges[0] / motive_ranges[1]
        g["extension_ratio"] = round(extension_ratio, 4)
        g["has_extension"] = extension_ratio >= 1.382  # Seuil assoupli pour v2.0
        
        # Identifier quelle vague est étendue
        if w3.price_range == motive_ranges[0]:
            g["extended_wave"] = "3"
        elif w5.price_range == motive_ranges[0]:
            g["extended_wave"] = "5"
        elif w1.price_range == motive_ranges[0]:
            g["extended_wave"] = "1"
        else:
            g["extended_wave"] = "?"
    else:
        g["extension_ratio"] = 0
        g["has_extension"] = False
        g["extended_wave"] = "?"
    
    return g


def _check_correction_guidelines(wc: WaveCount) -> Dict:
    """Vérifie les guidelines pour une correction ABC."""
    wa, wb, wc_wave = wc.waves
    g = {}
    
    # Ratio B/A
    if wa.price_range > 0:
        g["b_a_ratio"] = round(wb.price_range / wa.price_range, 4)
    else:
        g["b_a_ratio"] = 0
    
    # Ratio C/A
    if wa.price_range > 0:
        g["c_a_ratio"] = round(wc_wave.price_range / wa.price_range, 4)
    else:
        g["c_a_ratio"] = 0
    
    # Temps
    if wa.duration > 0:
        g["b_a_time_ratio"] = round(wb.duration / wa.duration, 3)
        g["c_a_time_ratio"] = round(wc_wave.duration / wa.duration, 3)
    else:
        g["b_a_time_ratio"] = 0
        g["c_a_time_ratio"] = 0
    
    return g
