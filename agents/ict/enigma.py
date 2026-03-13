"""
ENIGMA — Niveaux Algorithmiques ICT KB4
========================================
Les niveaux algorithmiques sont les niveaux de prix où la Smart Money
place ses ordres : les chiffres ronds et leurs subdivisions.

Hiérarchie :
  .00 / .50  → niveaux primaires   (ex: 1.0800, 1.0850)
  .20 / .80  → niveaux secondaires (ex: 1.0820, 1.0880)

Règles KB4 :
  +10 pts si TP sur niveau ENIGMA
  +10 pts si entry sur niveau ENIGMA (± ENTRY_TOLERANCE pips)
  -15 pts si TP hors niveau ENIGMA (malus permanent)
"""

# ── Constantes ────────────────────────────────────────────────────────────────
ENIGMA_LEVELS   = [0.00, 0.20, 0.50, 0.80]   # subdivision du chiffre de 2ème décimale
SNAP_TOLERANCE  = 5    # pips : si TP est à < 5 pips d'un niveau → on snappe
ENTRY_TOLERANCE = 2    # pips : bonus entry si on est à ± 2 pips d'un niveau
PIP             = 0.0001


def _get_enigma_levels_near(price: float, pip_value: float = PIP) -> list:
    """
    Retourne tous les niveaux ENIGMA dans une fenêtre de ± 100 pips autour du prix.
    """
    base = round(price, 2)            # ex: 1.0847 → 1.08
    levels = []
    for offset in range(-3, 4):       # quelques figures autour
        figure = round(base + offset * 0.01, 2)
        for frac in ENIGMA_LEVELS:
            # frac = 0.20 = 20 pips
            level = round(figure + frac / 100, 5)
            if abs(level - price) <= 100 * pip_value:
                levels.append(level)
    return sorted(levels)


def find_nearest_enigma(price: float, direction: str,
                         pip_value: float = PIP) -> dict:
    """
    Trouve le prochain niveau ENIGMA dans la direction du trade.

    Args:
        price     : Prix de référence (TP brut ou entry)
        direction : 'bullish' ou 'bearish'
        pip_value : Valeur d'un pip (0.0001 pour forex, 0.01 pour JPY/Gold)

    Returns:
        dict avec 'level' (float), 'distance_pips' (float), 'is_primary' (bool)
    """
    levels = _get_enigma_levels_near(price, pip_value)
    if not levels:
        return {"level": price, "distance_pips": 0.0, "is_primary": False}

    if direction == 'bullish':
        # On veut le niveau au-dessus ou égal
        candidates = [l for l in levels if l >= price]
    else:
        # On veut le niveau en-dessous ou égal
        candidates = [l for l in levels if l <= price]

    if not candidates:
        # Fallback : niveau le plus proche
        candidates = levels

    best = min(candidates, key=lambda l: abs(l - price)) \
        if direction != 'bullish' else \
        min(candidates, key=lambda l: abs(l - price))

    dist_pips = abs(best - price) / pip_value
    # Niveau primaire = .00 ou .50
    frac = round((best % 0.01) / pip_value)  # 0, 20, 50, 80
    is_primary = frac in (0, 50)

    return {
        "level":        round(best, 5),
        "distance_pips": round(dist_pips, 1),
        "is_primary":    is_primary
    }


def snap_to_enigma(tp_raw: float, direction: str,
                    pip_value: float = PIP,
                    snap_tolerance_pips: float = SNAP_TOLERANCE) -> dict:
    """
    Snappe un TP sur le niveau ENIGMA le plus proche si dans la tolérance.
    Si hors tolérance → prend le prochain niveau ENIGMA dans la direction.

    Returns:
        dict avec 'tp_adjusted' (float), 'snapped' (bool),
                  'enigma_level' (float), 'distance_pips' (float)
    """
    levels = _get_enigma_levels_near(tp_raw, pip_value)
    if not levels:
        return {"tp_adjusted": tp_raw, "snapped": False, "enigma_level": tp_raw, "distance_pips": 0.0, "is_primary": False}

    absolute_nearest = min(levels, key=lambda l: abs(l - tp_raw))
    dist_to_nearest = abs(absolute_nearest - tp_raw) / pip_value

    if dist_to_nearest <= snap_tolerance_pips:
        frac = round((round(absolute_nearest, 5) % 0.01) / pip_value)
        return {
            "tp_adjusted":   round(absolute_nearest, 5),
            "snapped":       True,
            "enigma_level":  round(absolute_nearest, 5),
            "distance_pips": round(dist_to_nearest, 1),
            "is_primary":    frac in (0, 50)
        }
    else:
        # Pas de snap → retourner le prochain niveau dans la direction pour le scoring
        nearest_dir = find_nearest_enigma(tp_raw, direction, pip_value)
        return {
            "tp_adjusted":   tp_raw,
            "snapped":       False,
            "enigma_level":  nearest_dir['level'],
            "distance_pips": nearest_dir['distance_pips'],
            "is_primary":    nearest_dir['is_primary']
        }


def score_enigma(entry_price: float, tp: float, direction: str,
                  pip_value: float = PIP) -> dict:
    """
    Calcule le bonus/malus ENIGMA pour le scoring KB4.

    Règles :
      +10 si TP sur niveau ENIGMA (distance ≤ SNAP_TOLERANCE pips)
      +10 si entry sur niveau ENIGMA (distance ≤ ENTRY_TOLERANCE pips)
      -15 si TP hors niveau ENIGMA (distance > SNAP_TOLERANCE pips)

    Returns:
        dict avec 'score_delta' (int), 'tp_on_enigma' (bool),
                  'entry_on_enigma' (bool), 'details' (list[str])
    """
    details      = []
    score_delta  = 0

    # ── TP check ─────────────────────────────────────────────────────────────
    tp_result = snap_to_enigma(tp, direction, pip_value)
    if tp_result['snapped']:
        score_delta     += 10
        tp_on_enigma     = True
        details.append(f"ENIGMA_TP:+10(niveau {tp_result['enigma_level']}, {tp_result['distance_pips']}pips)")
    else:
        score_delta     -= 15
        tp_on_enigma     = False
        details.append(f"ENIGMA_TP:-15(hors niveau, plus proche={tp_result['enigma_level']}, {tp_result['distance_pips']}pips)")

    # ── Entry check ──────────────────────────────────────────────────────────
    entry_result = find_nearest_enigma(entry_price, direction, pip_value)
    if entry_result['distance_pips'] <= ENTRY_TOLERANCE:
        score_delta      += 10
        entry_on_enigma   = True
        details.append(f"ENIGMA_ENTRY:+10(niveau {entry_result['level']}, {entry_result['distance_pips']}pips)")
    else:
        entry_on_enigma   = False
        details.append(f"ENIGMA_ENTRY:0(hors ±{ENTRY_TOLERANCE}pips, dist={entry_result['distance_pips']}pips)")

    return {
        "score_delta":     score_delta,
        "tp_on_enigma":    tp_on_enigma,
        "entry_on_enigma": entry_on_enigma,
        "tp_adjusted":     tp_result['tp_adjusted'],
        "tp_snapped":      tp_result['snapped'],
        "enigma_details":  details
    }
