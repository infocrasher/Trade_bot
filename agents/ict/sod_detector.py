"""
SOD Detector — State of Delivery KB4
======================================
Détecte l'état de livraison du marché sur 5 états.
Chaque état détermine si on peut trader et avec quelle taille.

États :
  STRONG_DISTRIBUTION  → sizing 100% — mouvement directionnel propre
  WEAK_DISTRIBUTION    → sizing 50%  — mouvement présent mais hésitant
  ACCUMULATION         → sizing 0%   — range asiatique, pas de direction
  MANIPULATION         → sizing 0%   — Judas Swing actif, piège probable
  UNKNOWN              → sizing 0%   — contexte insuffisant pour décider

Sources d'entrée :
  - po3_phase     : phase Power of 3 (time_session.py)
  - amd_phase     : phase AMD Weekly (time_session.py)
  - df_h1         : bougies H1 pour analyse du mouvement
"""

import numpy as np

# Sizing par état
SOD_SIZING = {
    "STRONG_DISTRIBUTION": 1.00,
    "WEAK_DISTRIBUTION":   0.50,
    "ACCUMULATION":        0.00,
    "MANIPULATION":        0.00,
    "UNKNOWN":             0.00,
}


# TF considérés comme "HTF" — le gate ACCUMULATION est absolu dessus
_HTF_SET = {"D1", "H4", "W1", "MN"}

def detect_sod(po3_phase: str, amd_phase: str,
               df_h1=None, analysis_tf: str = "M5") -> dict:
    """
    Détermine le State of Delivery à partir des phases connues + analyse H1.

    Règle Fateh (P-A4b) :
      - Sur D1/H4 : ACCUMULATION = gate absolu (NO_TRADE)
      - Sur M5/H1 : ACCUMULATION = autorisation conditionnelle si contexte M5 propre
                    → WEAK_DISTRIBUTION (sizing 50%) au lieu de NO_TRADE

    Args:
        po3_phase   : 'accumulation' | 'manipulation' | 'distribution' | 'transition'
        amd_phase   : 'accumulation' | 'manipulation' | 'distribution' | 'closing' | 'closed'
        df_h1       : DataFrame H1 optionnel pour affiner la qualité du mouvement
        analysis_tf : timeframe d'analyse du signal ('M5', 'H1', 'H4', 'D1', ...)

    Returns:
        dict avec 'state', 'sizing_factor', 'can_trade', 'reason'
    """
    is_htf = analysis_tf in _HTF_SET

    # ── Cas 1 : ACCUMULATION ─────────────────────────────────────────────────
    if po3_phase == "accumulation":
        if is_htf:
            # Gate absolu sur D1/H4 — on ne trade jamais en accumulation HTF
            return _make(
                "ACCUMULATION",
                f"PO3 ACCUMULATION sur {analysis_tf} — Asian range en formation, "
                f"aucune entrée HTF autorisée"
            )
        else:
            # Règle Fateh : M5/H1 peuvent avoir des entrées valides pendant l'accumulation
            # Le range asiatique se forme sur HTF, mais M5 peut avoir sa propre structure
            # → WEAK_DISTRIBUTION : autorisé mais sizing réduit 50%, contexte à surveiller
            return _make(
                "WEAK_DISTRIBUTION",
                f"PO3 ACCUMULATION (HTF) mais analyse sur {analysis_tf} — "
                f"entrée M5 conditionnelle autorisée, sizing réduit 50%"
            )

    # ── Cas 2 : MANIPULATION ─────────────────────────────────────────────────
    if po3_phase == "manipulation":
        return _make(
            "MANIPULATION",
            f"PO3 en manipulation — Judas Swing actif sur {analysis_tf}, "
            f"risque de piège institutionnel"
        )

    if amd_phase == "manipulation":
        return _make(
            "MANIPULATION",
            "AMD Weekly en manipulation (Mardi) — stop hunt hebdomadaire probable"
        )

    # ── Cas 3 : UNKNOWN (contexte insuffisant) ───────────────────────────────
    if po3_phase == "transition" and amd_phase not in ("distribution", "closing"):
        return _make(
            "UNKNOWN",
            f"Hors horaires ICT principaux et hors phase de distribution "
            f"(tf={analysis_tf}) — contexte insuffisant"
        )

    # ── Cas 4 : STRONG vs WEAK DISTRIBUTION ──────────────────────────────────
    if df_h1 is not None and len(df_h1) >= 10:
        strength = _measure_distribution_strength(df_h1)
    else:
        strength = "weak"

    if strength == "strong":
        return _make(
            "STRONG_DISTRIBUTION",
            f"Distribution propre (po3={po3_phase}, amd={amd_phase}, "
            f"tf={analysis_tf}) — sizing plein"
        )
    else:
        return _make(
            "WEAK_DISTRIBUTION",
            f"Distribution présente mais hésitante (po3={po3_phase}, "
            f"amd={amd_phase}, tf={analysis_tf}) — sizing réduit 50%"
        )


def _measure_distribution_strength(df_h1) -> str:
    """
    Mesure la qualité du mouvement H1 sur les 10 dernières bougies.

    STRONG si :
      - Corps moyen > 40% de l'ATR H1 (bougies directionnelles)
      - Ratio bougies dans la direction ≥ 60%
      - ATR non erratique (std < 50% de la moyenne)

    WEAK sinon.
    """
    try:
        closes = df_h1['close'].values[-10:]
        opens  = df_h1['open'].values[-10:]
        highs  = df_h1['high'].values[-10:]
        lows   = df_h1['low'].values[-10:]

        # ATR simplifié (True Range moyen)
        trs    = highs - lows
        atr    = float(np.mean(trs)) if len(trs) > 0 else 0.001
        atr_std = float(np.std(trs))

        # Corps moyen
        bodies  = np.abs(closes - opens)
        avg_body = float(np.mean(bodies))

        # Ratio directionnel : combien de bougies ont un corps > 40% ATR
        directional = np.sum(bodies > atr * 0.40)
        ratio        = directional / len(bodies)

        # Critères STRONG
        body_ok  = avg_body > atr * 0.40
        ratio_ok = ratio >= 0.60
        atr_ok   = atr_std < atr * 0.50   # ATR stable = mouvement régulier

        if body_ok and ratio_ok and atr_ok:
            return "strong"
        return "weak"

    except Exception:
        return "weak"


def _make(state: str, reason: str) -> dict:
    sizing = SOD_SIZING.get(state, 0.0)
    return {
        "state":          state,
        "sizing_factor":  sizing,
        "can_trade":      sizing > 0,
        "reason":         reason,
    }


def get_sod_sizing_factor(sod_result: dict) -> float:
    """Retourne simplement le factor de sizing (0.0, 0.5 ou 1.0)."""
    return sod_result.get("sizing_factor", 0.0)
