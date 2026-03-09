"""
Elliott Wave Scorer v2.0 — Score /100 recalibré
================================================
Recalibration basée sur l'Encyclopédie Elliott Wave v1.0 complète.

Sections de référence :
  - Sec 2.1  : Règles absolues (éliminatoires)
  - Sec 7    : Fibonacci prix (guidelines, PAS des règles)
  - Sec 2.2  : Structure interne 5-3-5-3-5
  - Sec 6/C  : Alternance (sharp vs sideways)
  - Sec 14/D : Extensions et règle d'égalité
  - Sec 15/E : Contraintes temporelles
  - Sec 21   : Momentum & divergences
  - Sec 22   : Classification Sharp vs Sideways

Budget /100 :
  FIBONACCI PRIX           /25
  STRUCTURE INTERNE        /25
  ALTERNANCE               /15
  PROPORTIONS TEMPORELLES  /15
  MOMENTUM / DIVERGENCE    /10
  RIGHT LOOK & EXTENSIONS  /10
  
  PÉNALITÉS possibles : -5 (disproportion extrême)
"""

from typing import Dict
from .wave_counter import WaveCount, WaveType, PARAMS
from .rules_validator import validate_absolute_rules, validate_correction_rules, check_guidelines


def score_wave_count(wc: WaveCount) -> WaveCount:
    """
    Score un comptage Elliott Wave /100.
    
    [RÈGLES ABSOLUES — Éliminatoires]
    R1: V2 ne casse pas l'origine de V1      → Si violé: SCORE = 0
    R2: V3 pas la plus courte                 → Si violé: SCORE = 0
    R3: V4 ne chevauche pas V1 (non-diag)     → Si violé: SCORE = 0
    
    [GUIDELINES — Scoring /100]
    Chaque catégorie attribue des points proportionnels à la qualité du comptage.
    Ref: "Ne jamais invalider un comptage uniquement pour non-respect exact
         de ces chiffres" (Encyclopédie Sec 7)
    """
    if wc.wave_type == WaveType.IMPULSE:
        return _score_impulse(wc)
    elif wc.wave_type == WaveType.CORRECTION:
        return _score_correction(wc)
    return wc


def _score_impulse(wc: WaveCount) -> WaveCount:
    """
    Score une impulsion 5 vagues — /100.
    
    Budget :
      FIBONACCI PRIX           /25  (Sec 7 + Sec 20)
      STRUCTURE INTERNE        /25  (Sec 2.2 + Sec 14)
      ALTERNANCE               /15  (Sec 6 + Sec C/22)
      PROPORTIONS TEMPORELLES  /15  (Sec 15 + Sec E)
      MOMENTUM / DIVERGENCE    /10  (Sec 21)
      RIGHT LOOK & EXTENSIONS  /10  (Sec 14 + Sec D)
    """
    
    # ═══ ÉTAPE 1 : Règles absolues (Sec 2.1 / Sec G) ═══
    wc = validate_absolute_rules(wc)
    if not wc.valid:
        wc.score = 0
        return wc
    
    # ═══ ÉTAPE 2 : Guidelines ═══
    g = check_guidelines(wc)
    wc.details["guidelines"] = g
    
    score = 0
    breakdown = {}
    w1, w2, w3, w4, w5 = wc.waves
    
    # ═══════════════════════════════════════════
    # FIBONACCI PRIX — /25 points (Sec 7 + 20)
    # ═══════════════════════════════════════════
    fib_score = 0
    
    # F1: V2 retrace dans le range Fibonacci de V1 — /6
    # Sec 7.1 : "50–61.8% de 1" (typique), 23.6–78.6% (étendu)
    w2_ret = g.get("w2_retrace", 0)
    if 0.50 <= w2_ret <= 0.618:
        fib_score += 6
        breakdown["F1_w2_retrace"] = f"+6 (typique {w2_ret:.1%})"
    elif 0.382 <= w2_ret <= 0.786:
        fib_score += 4
        breakdown["F1_w2_retrace"] = f"+4 (bon {w2_ret:.1%})"
    elif 0.236 <= w2_ret <= 0.99:
        fib_score += 2
        breakdown["F1_w2_retrace"] = f"+2 (acceptable {w2_ret:.1%})"
    else:
        breakdown["F1_w2_retrace"] = f"+0 ({w2_ret:.1%} hors range)"
    
    # F2: V3 extension par rapport à V1 — /6
    # Sec 7.2 : "138.2–161.8% de 1" (fréquent), ≥ 100% (minimum)
    w3_ext = g.get("w3_extension", 0)
    if w3_ext >= 1.618:
        fib_score += 6
        breakdown["F2_w3_ext"] = f"+6 (forte extension {w3_ext:.3f}x)"
    elif w3_ext >= 1.382:
        fib_score += 5
        breakdown["F2_w3_ext"] = f"+5 (extension typique {w3_ext:.3f}x)"
    elif w3_ext >= 1.0:
        fib_score += 3
        breakdown["F2_w3_ext"] = f"+3 (W3 > W1, {w3_ext:.3f}x)"
    elif w3_ext >= 0.8:
        fib_score += 1
        breakdown["F2_w3_ext"] = f"+1 (W3 proche W1, {w3_ext:.3f}x)"
    else:
        breakdown["F2_w3_ext"] = f"+0 (W3 trop courte {w3_ext:.3f}x)"
    
    # F3: V4 retrace dans le range Fibonacci de V3 — /5
    # Sec 7.1 : "23.6–38.2% de 3" (typique)
    w4_ret = g.get("w4_retrace", 0)
    if 0.236 <= w4_ret <= 0.382:
        fib_score += 5
        breakdown["F3_w4_retrace"] = f"+5 (typique {w4_ret:.1%})"
    elif 0.146 <= w4_ret <= 0.50:
        fib_score += 3
        breakdown["F3_w4_retrace"] = f"+3 (acceptable {w4_ret:.1%})"
    elif 0.10 <= w4_ret <= 0.618:
        fib_score += 1
        breakdown["F3_w4_retrace"] = f"+1 (étendu {w4_ret:.1%})"
    else:
        breakdown["F3_w4_retrace"] = f"+0 ({w4_ret:.1%} hors range)"
    
    # F4: V5 ≈ V1 — Règle d'Égalité — /4
    # Sec D.1 : "Si W1 et W3 normales, W5 tend vers W1"
    # + "Si W3 étendue, W5 ≈ W1 ou W5 ≈ 0.618*W1"
    # IMPORTANT : Ne plus bloquer sur "W3 étendue uniquement"
    w5_w1_ratio = g.get("w5_w1_ratio", 0)
    if 0.80 <= w5_w1_ratio <= 1.20:
        fib_score += 4
        breakdown["F4_w5_eq_w1"] = f"+4 (W5≈W1 {w5_w1_ratio:.3f})"
    elif 0.618 <= w5_w1_ratio <= 1.618:
        fib_score += 2
        breakdown["F4_w5_eq_w1"] = f"+2 (W5 Fib de W1 {w5_w1_ratio:.3f})"
    else:
        breakdown["F4_w5_eq_w1"] = f"+0 ({w5_w1_ratio:.3f})"
    
    # F5: Cluster Fibonacci — /4
    # Sec 20.1 : Zone de convergence prix → signal fort
    # Approximation : W5 atteint une projection Fibonacci de W1-W3
    f5_pts = 0
    if w1.price_range > 0 and w3.price_range > 0:
        # W5 ≈ 0.618 * (W1+W3 net) → cluster
        net_13 = w1.price_range + w3.price_range
        if net_13 > 0:
            w5_cluster_ratio = w5.price_range / (0.618 * net_13)
            if 0.7 <= w5_cluster_ratio <= 1.3:
                f5_pts = 4
                breakdown["F5_cluster"] = f"+4 (W5 dans cluster Fib)"
            elif 0.5 <= w5_cluster_ratio <= 1.8:
                f5_pts = 2
                breakdown["F5_cluster"] = f"+2 (W5 proche cluster)"
            else:
                breakdown["F5_cluster"] = f"+0 (hors cluster)"
        else:
            breakdown["F5_cluster"] = "+0 (pas de données)"
    else:
        breakdown["F5_cluster"] = "+0 (pas de données)"
    fib_score += f5_pts
    
    score += fib_score
    breakdown["_FIBONACCI_TOTAL"] = f"{fib_score}/25"
    
    # ═══════════════════════════════════════════
    # STRUCTURE INTERNE — /25 points (Sec 2.2)
    # ═══════════════════════════════════════════
    struct_score = 0
    
    # S1: Vagues bien formées (durée raisonnable) — /10
    # Sec E : "nombre de barres cohérent avec le degré"
    # Adaptatif : minimum = max(2, duration_moyenne * 0.2)
    avg_duration = sum(w.duration for w in wc.waves) / 5
    min_bars = max(2, int(avg_duration * 0.15))
    well_formed = sum(1 for w in wc.waves if w.duration >= min_bars)
    s1_pts = min(well_formed * 2, 10)
    struct_score += s1_pts
    breakdown["S1_well_formed"] = f"+{s1_pts} ({well_formed}/5 vagues ≥ {min_bars} barres)"
    
    # S2: Vagues motrices > correctives en prix — /10
    # Sec 2.2 : "5-3-5-3-5" → motrices dominent
    motive_ok = 0
    if w1.price_range > w2.price_range:
        motive_ok += 1
    if w3.price_range > w2.price_range:
        motive_ok += 1
    if w3.price_range > w4.price_range:
        motive_ok += 1
    if w5.price_range > w4.price_range:
        motive_ok += 1
    # 4/4 = parfait, 3/4 = bon, 2/4 = moyen
    s2_pts = {4: 10, 3: 7, 2: 4, 1: 2, 0: 0}[motive_ok]
    struct_score += s2_pts
    breakdown["S2_motive_dominance"] = f"+{s2_pts} ({motive_ok}/4 conditions)"
    
    # S3: W3 la plus longue en prix — /5
    # Sec 2.3 : "Souvent la plus longue et explosive"
    # C'est une propriété structurelle (déplacé de TEMPS)
    if w3.price_range >= w1.price_range and w3.price_range >= w5.price_range:
        struct_score += 5
        breakdown["S3_w3_longest"] = "+5 (W3 la plus longue)"
    elif w3.price_range >= max(w1.price_range, w5.price_range) * 0.8:
        struct_score += 3
        breakdown["S3_w3_longest"] = "+3 (W3 proche de la plus longue)"
    else:
        breakdown["S3_w3_longest"] = "+0 (W3 pas dominante)"
    
    score += struct_score
    breakdown["_STRUCTURE_TOTAL"] = f"{struct_score}/25"
    
    # ═══════════════════════════════════════════
    # ALTERNANCE — /15 points (Sec 6 + Sec C/22)
    # ═══════════════════════════════════════════
    alt_score = 0
    
    # A1: Alternance en profondeur (Sharp vs Sideways) — /10
    # Sec C : classification Sharp/Sideways
    # Sharp = retrace profond (> 50%), rapide
    # Sideways = retrace peu profond (< 50%), lent
    # Sec C pénalité : "si même famille → score -= 50%"
    w2_ret = g.get("w2_retrace", 0)
    w4_ret = g.get("w4_retrace", 0)
    
    # Classification : Sharp si retrace > 45%, Sideways si < 45%
    # (seuil assoupli vs 50% pour mieux capturer la réalité)
    w2_sharp = w2_ret > 0.45
    w4_sharp = w4_ret > 0.45
    
    if w2_sharp != w4_sharp:
        # Parfaite alternance Sharp/Sideways
        alt_score += 10
        breakdown["A1_alternation"] = f"+10 (W2={'sharp' if w2_sharp else 'sideways'}, W4={'sharp' if w4_sharp else 'sideways'})"
    else:
        # Même famille → pénaliser mais pas à zéro
        # Vérifier si au moins la profondeur est différente (> 10% écart)
        depth_diff = abs(w2_ret - w4_ret)
        if depth_diff > 0.15:
            alt_score += 6
            breakdown["A1_alternation"] = f"+6 (même famille mais écart {depth_diff:.1%})"
        elif depth_diff > 0.05:
            alt_score += 3
            breakdown["A1_alternation"] = f"+3 (alternance faible, écart {depth_diff:.1%})"
        else:
            breakdown["A1_alternation"] = f"+0 (pas d'alternance, écart {depth_diff:.1%})"
    
    # A2: Alternance en durée — /5
    # Sec 6.1 : "complexité" → durée différente = bonne alternance
    if w2.duration > 0 and w4.duration > 0:
        time_ratio_24 = w4.duration / w2.duration
        if time_ratio_24 > 1.5 or time_ratio_24 < 0.67:
            alt_score += 5
            breakdown["A2_time_alt"] = f"+5 (ratio W4/W2 = {time_ratio_24:.2f})"
        elif time_ratio_24 > 1.2 or time_ratio_24 < 0.83:
            alt_score += 3
            breakdown["A2_time_alt"] = f"+3 (ratio W4/W2 = {time_ratio_24:.2f})"
        else:
            breakdown["A2_time_alt"] = f"+0 (durées similaires {time_ratio_24:.2f})"
    else:
        breakdown["A2_time_alt"] = "+0 (données manquantes)"
    
    score += alt_score
    breakdown["_ALTERNANCE_TOTAL"] = f"{alt_score}/15"
    
    # ═══════════════════════════════════════════
    # PROPORTIONS TEMPORELLES — /15 (Sec 15 + E)
    # ═══════════════════════════════════════════
    time_score = 0
    
    # T1: T(W2)/T(W1) raisonnable — /5
    # Sec 15.1 : "T2 ≥ min_time_ratio * T1" (min 10-20%)
    if w1.duration > 0:
        w2_w1_time = w2.duration / w1.duration
        if w2_w1_time >= 0.20:
            time_score += 5
            breakdown["T1_w2_w1_time"] = f"+5 (T2/T1 = {w2_w1_time:.2f})"
        elif w2_w1_time >= 0.10:
            time_score += 3
            breakdown["T1_w2_w1_time"] = f"+3 (T2/T1 = {w2_w1_time:.2f} borderline)"
        else:
            breakdown["T1_w2_w1_time"] = f"+0 (T2/T1 = {w2_w1_time:.2f} trop court)"
    
    # T2: W3 pas la plus courte en temps — /5
    # Sec E : "La W3 ne doit pas être la plus courte en temps non plus"
    durations = [w.duration for w in wc.waves]
    w3_dur = w3.duration
    if w3_dur > min(durations):
        time_score += 5
        breakdown["T2_w3_time"] = f"+5 (W3 pas la plus courte en temps)"
    elif w3_dur == min(durations) and durations.count(w3_dur) > 1:
        time_score += 3
        breakdown["T2_w3_time"] = f"+3 (W3 à égalité avec une autre)"
    else:
        breakdown["T2_w3_time"] = "+0 (W3 la plus courte en temps)"
    
    # T3: Cohérence globale de degré — /5
    # Sec E : "nombre de barres comparable entre vagues du même degré"
    # Ratio max/min < 8 = OK, < 5 = bon, < 3 = excellent
    if durations and min(durations) > 0:
        time_disp = max(durations) / max(min(durations), 1)
        g["time_disproportion"] = round(time_disp, 1)
        if time_disp <= 3.0:
            time_score += 5
            breakdown["T3_coherence"] = f"+5 (excellent, ratio {time_disp:.1f})"
        elif time_disp <= 5.0:
            time_score += 4
            breakdown["T3_coherence"] = f"+4 (bon, ratio {time_disp:.1f})"
        elif time_disp <= 8.0:
            time_score += 2
            breakdown["T3_coherence"] = f"+2 (acceptable, ratio {time_disp:.1f})"
        else:
            breakdown["T3_coherence"] = f"+0 (disproportion {time_disp:.1f})"
    
    score += time_score
    breakdown["_TEMPS_TOTAL"] = f"{time_score}/15"
    
    # ═══════════════════════════════════════════
    # MOMENTUM / DIVERGENCE — /10 (Sec 21)
    # ═══════════════════════════════════════════
    # Sec 21 : "L'Elliott Oscillator — W3 pic max, W5 divergence"
    # Pour l'instant, pas d'oscillateur dans le pipeline
    # Score neutre = 5/10 en attendant l'intégration RSI/MACD
    mom_score = 5
    breakdown["M_momentum"] = "+5 (neutre — oscillateur non intégré)"
    score += mom_score
    breakdown["_MOMENTUM_TOTAL"] = f"{mom_score}/10"
    
    # ═══════════════════════════════════════════
    # RIGHT LOOK & EXTENSIONS — /10 (Sec 14 + D)
    # ═══════════════════════════════════════════
    ext_score = 0
    
    # E1: Extension identifiable (une vague 1.382x+ la 2ème) — /5
    # Sec 14.1 : GUIDELINE, pas obligatoire
    ext_ratio = g.get("extension_ratio", 0)
    if ext_ratio >= 1.618:
        ext_score += 5
        breakdown["E1_extension"] = f"+5 (extension forte {ext_ratio:.3f}x, V{g.get('extended_wave', '?')})"
    elif ext_ratio >= 1.382:
        ext_score += 4
        breakdown["E1_extension"] = f"+4 (extension typique {ext_ratio:.3f}x)"
    elif ext_ratio >= 1.2:
        ext_score += 2
        breakdown["E1_extension"] = f"+2 (extension légère {ext_ratio:.3f}x)"
    else:
        breakdown["E1_extension"] = f"+0 (pas d'extension claire {ext_ratio:.3f}x)"
    
    # E2: Right look global — /5
    # Le comptage a-t-il l'apparence d'une impulsion Elliott ?
    # Sec 2.3 : W1 début, W3 explosive, W5 épuisement
    right_look = 0
    # W3 est la plus explosive (prix) 
    if w3.price_range == max(w1.price_range, w3.price_range, w5.price_range):
        right_look += 1
    # W5 < W3 (épuisement)
    if w5.price_range < w3.price_range:
        right_look += 1
    # W2 < W1 en prix (correction ne domine pas)
    if w2.price_range < w1.price_range:
        right_look += 1
    # Tendance globale claire (dernier point éloigné du premier)
    total_range = abs(wc.pivots[-1].price - wc.pivots[0].price)
    sum_ranges = sum(w.price_range for w in wc.waves)
    if sum_ranges > 0 and total_range / sum_ranges > 0.3:
        right_look += 1
    
    e2_pts = {4: 5, 3: 4, 2: 3, 1: 1, 0: 0}[right_look]
    ext_score += e2_pts
    breakdown["E2_right_look"] = f"+{e2_pts} ({right_look}/4 critères)"
    
    score += ext_score
    breakdown["_EXTENSIONS_TOTAL"] = f"{ext_score}/10"
    
    # ═══════════════════════════════════════════
    # PÉNALITÉS (légères)
    # ═══════════════════════════════════════════
    
    # Disproportion temporelle extrême > 10 — -5
    time_disp = g.get("time_disproportion", 0)
    if time_disp > 10.0:
        penalty = -5
        score += penalty
        breakdown["PENALTY_time_extreme"] = f"{penalty} (ratio temps {time_disp:.1f})"
    
    # ═══ SCORE FINAL ═══
    score = max(0, min(100, score))
    
    wc.score = score
    wc.details["scoring_breakdown"] = breakdown
    wc.details["raw_score"] = score
    wc.details["scorer_version"] = "2.0"
    
    return wc


def _score_correction(wc: WaveCount) -> WaveCount:
    """
    Score une correction ABC — /100.
    
    Budget :
      FIBONACCI PRIX     /30  (B/A, C/A ratios)
      STRUCTURE          /30  (vagues bien formées, A/C même direction)
      TEMPS              /20  (cohérence temporelle)
      CLASSIFICATION     /20  (type correctif identifié + bonus)
    """
    
    # Valider les règles de correction
    wc = validate_correction_rules(wc)
    if not wc.valid:
        wc.score = 0
        return wc
    
    g = check_guidelines(wc)
    wc.details["guidelines"] = g
    
    score = 0
    breakdown = {}
    
    wa, wb, wc_wave = wc.waves
    correction_type = wc.details.get("correction_type", "unknown")
    
    # ═══════════════════════════════════════════
    # FIBONACCI — /30 points (Sec 13)
    # ═══════════════════════════════════════════
    fib_score = 0
    
    # B/A ratio — /15
    b_ratio = g.get("b_a_ratio", 0)
    if correction_type == "zigzag":
        # Sec 13.2 : fenêtre typique 38.2%–79%
        if 0.382 <= b_ratio <= 0.786:
            fib_score += 15
            breakdown["F_b_ratio"] = f"+15 (zigzag typique B/A={b_ratio:.3f})"
        elif 0.236 <= b_ratio <= 0.90:
            fib_score += 10
            breakdown["F_b_ratio"] = f"+10 (zigzag étendu B/A={b_ratio:.3f})"
        elif b_ratio < 0.99:
            fib_score += 5
            breakdown["F_b_ratio"] = f"+5 (zigzag limite B/A={b_ratio:.3f})"
        else:
            breakdown["F_b_ratio"] = f"+0 (B/A={b_ratio:.3f} hors range zigzag)"
    elif correction_type == "flat":
        # Sec 13.1 : B retrace ≥ 90% de A
        if 0.90 <= b_ratio <= 1.05:
            fib_score += 15
            breakdown["F_b_ratio"] = f"+15 (flat régulier B/A={b_ratio:.3f})"
        elif 0.85 <= b_ratio <= 1.10:
            fib_score += 10
            breakdown["F_b_ratio"] = f"+10 (flat étendu B/A={b_ratio:.3f})"
        else:
            fib_score += 5
            breakdown["F_b_ratio"] = f"+5 (flat? B/A={b_ratio:.3f})"
    elif correction_type == "expanded_flat":
        if b_ratio > 1.0:
            fib_score += 12
            breakdown["F_b_ratio"] = f"+12 (expanded flat B/A={b_ratio:.3f})"
        else:
            fib_score += 5
            breakdown["F_b_ratio"] = f"+5 (expanded? B/A={b_ratio:.3f})"
    else:
        # Type inconnu — donner des points partiels si B/A dans un range raisonnable
        if 0.30 <= b_ratio <= 1.20:
            fib_score += 8
            breakdown["F_b_ratio"] = f"+8 (type inconnu, B/A={b_ratio:.3f} raisonnable)"
        else:
            breakdown["F_b_ratio"] = f"+0 (B/A={b_ratio:.3f})"
    
    # C/A ratio — /15
    # Sec 13.2 : |C| tend vers 100%, 61.8% ou 161.8% de |A|
    c_ratio = g.get("c_a_ratio", 0)
    # Vérifier proximité avec les ratios Fibonacci
    fib_targets = [0.618, 1.0, 1.272, 1.618]
    best_fib_dist = min(abs(c_ratio - t) for t in fib_targets) if c_ratio > 0 else 99
    
    if best_fib_dist < 0.05:
        fib_score += 15
        breakdown["F_c_a"] = f"+15 (C/A={c_ratio:.3f} pile sur un Fib)"
    elif best_fib_dist < 0.15:
        fib_score += 10
        breakdown["F_c_a"] = f"+10 (C/A={c_ratio:.3f} proche d'un Fib)"
    elif 0.50 <= c_ratio <= 2.0:
        fib_score += 6
        breakdown["F_c_a"] = f"+6 (C/A={c_ratio:.3f} dans le range)"
    elif 0.30 <= c_ratio <= 2.618:
        fib_score += 3
        breakdown["F_c_a"] = f"+3 (C/A={c_ratio:.3f} étendu)"
    else:
        breakdown["F_c_a"] = f"+0 (C/A={c_ratio:.3f} hors range)"
    
    score += fib_score
    breakdown["_FIBONACCI_TOTAL"] = f"{fib_score}/30"
    
    # ═══════════════════════════════════════════
    # STRUCTURE — /30 points
    # ═══════════════════════════════════════════
    struct_score = 0
    
    # Vagues bien formées — /15
    avg_dur = sum(w.duration for w in wc.waves) / 3
    min_bars = max(2, int(avg_dur * 0.15))
    well_formed = sum(1 for w in wc.waves if w.duration >= min_bars)
    s_pts = {3: 15, 2: 10, 1: 5, 0: 0}[well_formed]
    struct_score += s_pts
    breakdown["S_well_formed"] = f"+{s_pts} ({well_formed}/3 vagues ≥ {min_bars} barres)"
    
    # A et C dans la même direction — /10
    if wa.direction == wc_wave.direction:
        struct_score += 10
        breakdown["S_a_c_dir"] = "+10 (A et C même direction)"
    else:
        breakdown["S_a_c_dir"] = "+0 (A et C directions différentes)"
    
    # B dans la direction opposée — /5
    if wb.direction != wa.direction:
        struct_score += 5
        breakdown["S_b_opposite"] = "+5 (B direction opposée à A)"
    else:
        breakdown["S_b_opposite"] = "+0"
    
    score += struct_score
    breakdown["_STRUCTURE_TOTAL"] = f"{struct_score}/30"
    
    # ═══════════════════════════════════════════
    # TEMPS — /20 points
    # ═══════════════════════════════════════════
    time_score = 0
    
    # C/A temps cohérent — /10
    if wa.duration > 0 and wc_wave.duration > 0:
        time_ratio = wc_wave.duration / wa.duration
        if 0.5 <= time_ratio <= 2.0:
            time_score += 10
            breakdown["T_c_a"] = f"+10 (C/A temps={time_ratio:.2f})"
        elif 0.25 <= time_ratio <= 4.0:
            time_score += 6
            breakdown["T_c_a"] = f"+6 (C/A temps={time_ratio:.2f} étendu)"
        else:
            time_score += 2
            breakdown["T_c_a"] = f"+2 (C/A temps={time_ratio:.2f} déséquilibré)"
    
    # B/A temps — /10
    if wa.duration > 0 and wb.duration > 0:
        b_time = wb.duration / wa.duration
        if 0.30 <= b_time <= 1.5:
            time_score += 10
            breakdown["T_b_a"] = f"+10 (B/A temps={b_time:.2f})"
        elif 0.15 <= b_time <= 3.0:
            time_score += 6
            breakdown["T_b_a"] = f"+6 (B/A temps={b_time:.2f} étendu)"
        else:
            time_score += 2
            breakdown["T_b_a"] = f"+2 (B/A temps={b_time:.2f} déséquilibré)"
    
    score += time_score
    breakdown["_TEMPS_TOTAL"] = f"{time_score}/20"
    
    # ═══════════════════════════════════════════
    # CLASSIFICATION — /20 points
    # ═══════════════════════════════════════════
    class_score = 0
    
    # Type correctement identifié — /10
    if correction_type in ("zigzag", "flat", "expanded_flat"):
        class_score += 10
        breakdown["CL_type"] = f"+10 (type: {correction_type})"
    else:
        class_score += 3
        breakdown["CL_type"] = f"+3 (type incertain: {correction_type})"
    
    # C dépasse A (requis pour zigzag, bon signe pour flat) — /10
    if wc.direction.value == "bearish":
        c_exceeds = wc_wave.end.price < wa.end.price
    else:
        c_exceeds = wc_wave.end.price > wa.end.price
    
    if c_exceeds:
        class_score += 10
        breakdown["CL_c_exceeds"] = "+10 (C dépasse A)"
    elif correction_type in ("flat", "expanded_flat"):
        # Pour un flat en fuite, C peut ne pas dépasser A
        class_score += 5
        breakdown["CL_c_exceeds"] = f"+5 (C ne dépasse pas A, acceptable pour {correction_type})"
    else:
        breakdown["CL_c_exceeds"] = "+0 (C ne dépasse pas A)"
    
    score += class_score
    breakdown["_CLASSIFICATION_TOTAL"] = f"{class_score}/20"
    
    # ═══ SCORE FINAL ═══
    score = max(0, min(100, score))
    
    wc.score = score
    wc.details["scoring_breakdown"] = breakdown
    wc.details["scorer_version"] = "2.0"
    
    return wc
