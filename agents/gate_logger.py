"""
Gate Logger — Module indépendant.
Chaque école loggue ses blocages séparément.
Le meta-orchestrateur loggue la décision de fusion finale.
"""

import json
import os
from datetime import datetime

GATE_LOG_DIR = "data/gate_logs"
os.makedirs(GATE_LOG_DIR, exist_ok=True)


def _write(filepath: str, record: dict) -> None:
    existing = []
    if os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                existing = json.load(f)
        except Exception:
            existing = []
    existing.append(record)
    with open(filepath, "w") as f:
        json.dump(existing, f, indent=2)


def log_ict_blocked(
    pair: str, horizon: str, reason: str,
    bias: str, htf_alignment: str,
    entry: float, sl: float, tp1: float,
    ote_top: float = None, ote_bottom: float = None,
    candle_high: float = None, candle_low: float = None,
    rr: float = None,
) -> None:
    """Loggue un setup bloqué par un gate ICT."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    _write(
        os.path.join(GATE_LOG_DIR, f"ict_blocked_{today}.json"),
        {
            "timestamp":     datetime.utcnow().isoformat(),
            "pair":          pair,
            "horizon":       horizon,
            "gate_reason":   reason,
            "bias":          bias,
            "htf_alignment": htf_alignment,
            "entry":         round(entry, 6) if entry else None,
            "sl":            round(sl, 6) if sl else None,
            "tp1":           round(tp1, 6) if tp1 else None,
            "rr":            round(rr, 2) if rr else None,
            "ote_top":       round(ote_top, 6) if ote_top else None,
            "ote_bottom":    round(ote_bottom, 6) if ote_bottom else None,
            "candle_high":   round(candle_high, 6) if candle_high else None,
            "candle_low":    round(candle_low, 6) if candle_low else None,
            "would_have_won": None,
            "pnl_pips":      None,
        }
    )


def log_elliott_blocked(
    pair: str, horizon: str, reason: str,
    signal: str, score: int,
    entry: float, sl: float, tp1: float,
    wave_status: str = None,
) -> None:
    """Loggue un setup bloqué par Elliott (score < seuil ou NO_TRADE)."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    _write(
        os.path.join(GATE_LOG_DIR, f"elliott_blocked_{today}.json"),
        {
            "timestamp":    datetime.utcnow().isoformat(),
            "pair":         pair,
            "horizon":      horizon,
            "gate_reason":  reason,
            "signal":       signal,
            "score":        score,
            "wave_status":  wave_status,
            "entry":        round(entry, 6) if entry else None,
            "sl":           round(sl, 6) if sl else None,
            "tp1":          round(tp1, 6) if tp1 else None,
            "would_have_won": None,
            "pnl_pips":     None,
        }
    )


def log_meta_blocked(
    pair: str, horizon: str, final_gate: str,
    ict_signal: str, ict_score: int, ict_reason: str,
    elliott_signal: str, elliott_score: int,
    meta_score: int, meta_direction: str,
    entry: float, sl: float, tp1: float,
    a1_bias: str = None, htf_alignment: str = None,
) -> None:
    """Loggue la décision finale du meta-orchestrateur quand elle est NO_TRADE."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    _write(
        os.path.join(GATE_LOG_DIR, f"meta_blocked_{today}.json"),
        {
            "timestamp":      datetime.utcnow().isoformat(),
            "pair":           pair,
            "horizon":        horizon,
            "final_gate":     final_gate,
            "ict_signal":     ict_signal,
            "ict_score":      ict_score,
            "ict_reason":     ict_reason,
            "elliott_signal": elliott_signal,
            "elliott_score":  elliott_score,
            "meta_score":     meta_score,
            "meta_direction": meta_direction,
            "entry":          round(entry, 6) if entry else None,
            "sl":             round(sl, 6) if sl else None,
            "tp1":            round(tp1, 6) if tp1 else None,
            "a1_bias":        a1_bias,
            "htf_alignment":  htf_alignment,
            "would_have_won": None,
            "pnl_pips":       None,
        }
    )
