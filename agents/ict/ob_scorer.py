"""
OB Scorer — KB4 Sentinel Pro
Scoring des Order Blocks sur 5 critères.

Score 5/5 = A++  →  utiliser
Score 4/5 = A    →  utiliser
Score 3/5 = OK   →  utiliser (taille réduite recommandée)
Score < 3 = INVALIDE → rejeter l'OB
"""

PIP = 0.0001
LIQUIDITY_TOLERANCE_PIPS = 10


def score_order_block(ob_idx: int,
                      opens, closes, highs, lows,
                      has_fvg: bool,
                      is_mitigated: bool,
                      equal_levels: list = None) -> dict:
    """
    Score un Order Block sur 5 critères KB4.

    Critère 1 : Dernière bougie opposée avant le déplacement (toujours True — garanti par structure.py)
    Critère 2 : Corps > 50% du range de la bougie OB
    Critère 3 : Le déplacement a créé un FVG (Displacement → Imbalance)
    Critère 4 : Coïncide avec un niveau de liquidité EQH/EQL (± 10 pips)
    Critère 5 : Frais — jamais revisité depuis le déplacement

    Returns:
        dict avec ob_score (0-5), ob_grade (A++/A/OK/WEAK/INVALID), ob_details (liste)
    """
    score = 0
    details = []

    # ── C1 : Bougie opposée avant le déplacement ─────────────────────────────
    # Toujours True : detect_order_blocks() ne sélectionne que des bougies opposées
    score += 1
    details.append("C1:OK(bougie_opposee)")

    # ── C2 : Corps > 50% du range ────────────────────────────────────────────
    ob_body  = abs(closes[ob_idx] - opens[ob_idx])
    ob_range = highs[ob_idx] - lows[ob_idx]
    if ob_range > 0 and (ob_body / ob_range) >= 0.50:
        score += 1
        details.append("C2:OK(corps>50%)")
    else:
        details.append("C2:FAIL(corps<50%)")

    # ── C3 : FVG créé par le déplacement ─────────────────────────────────────
    if has_fvg:
        score += 1
        details.append("C3:OK(FVG)")
    else:
        details.append("C3:FAIL(noFVG)")

    # ── C4 : Coïncidence avec liquidité EQH/EQL ──────────────────────────────
    ob_mid = (highs[ob_idx] + lows[ob_idx]) / 2
    tolerance = LIQUIDITY_TOLERANCE_PIPS * PIP
    near_liq = any(
        abs(ob_mid - eq['level']) <= tolerance + 1e-8
        for eq in (equal_levels or [])
    )
    if near_liq:
        score += 1
        details.append("C4:OK(EQH/EQL)")
    else:
        details.append("C4:FAIL(noLiq)")

    # ── C5 : Frais (non mitigé) ───────────────────────────────────────────────
    if not is_mitigated:
        score += 1
        details.append("C5:OK(fresh)")
    else:
        details.append("C5:FAIL(mitigated)")

    # ── Grade final ───────────────────────────────────────────────────────────
    grade_map = {5: "A++", 4: "A", 3: "OK", 2: "WEAK", 1: "INVALID", 0: "INVALID"}
    grade = grade_map.get(score, "INVALID")

    return {
        "ob_score": score,
        "ob_grade": grade,
        "ob_details": details,
        "ob_valid": score >= 3
    }
