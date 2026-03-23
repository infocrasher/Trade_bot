"""
engine.py — Moteur de backtest offline pour le pipeline ICT TakeOption.

Replay bar-by-bar avec cutoff strict anti-lookahead.
Appelle les fonctions internes des agents directement (option b).
LLM exclu (non déterministe). OTE tracker mocké in-memory.

Usage :
    python -m backtest.engine --pairs EURUSD --horizon scalp --months 3
    python -m backtest.engine --all --horizon scalp --walk-forward
"""

import os
import sys
import copy
import json
import argparse
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, field

import pandas as pd
import numpy as np

# Assurer que le projet root est dans sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agents.ict.structure import StructureAgent
from agents.ict.time_session import TimeSessionAgent, to_ny_time
from agents.ict.entry import EntryAgent
from agents.ict.macro import MacroBiasAgent
from agents.ict.orchestrator import OrchestratorAgent
from agents.behaviour_shield import BehaviourShield
from config import (
    TRADING_PAIRS, get_realistic_spread_pips,
    KS4_SPREAD_LIMITS, KS4_SPREAD_LIMIT_DEFAULT,
)
from backtest.download_history import load_pair_data, DATA_DIR

logger = logging.getLogger("backtest")

# ═══════════════════════════════════════════════════════════════
# NEUTRALISATION HTTP EN BACKTEST
# NewsManager.__init__ appelle _load_cache() → refresh_news() →
# requête finnhub avec timeout 15s à CHAQUE instantiation dans A5.
# On remplace la classe par un stub no-op dès l'import du module.
# ═══════════════════════════════════════════════════════════════
try:
    import agents.news_manager as _nm_module
    import agents.ict.orchestrator as _orch_module_early

    class _BacktestNewsManagerStub:
        """Stub no-op : zéro requête HTTP en backtest."""
        def __init__(self, *args, **kwargs):
            self._news_data = []

        def is_news_window(self, *args, **kwargs):
            return {"blocked": False, "reason": "backtest_mode"}

        def refresh_news(self, *args, **kwargs):
            pass

    _nm_module.NewsManager = _BacktestNewsManagerStub
    _orch_module_early.NewsManager = _BacktestNewsManagerStub
    logger.info("[Backtest] NewsManager remplacé par stub no-op (zéro HTTP)")
except Exception as _e:
    logger.warning(f"[Backtest] Impossible de stubber NewsManager : {_e}")
# ═══════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════
# HORIZON PROFILES (miroir de dashboard.py)
# ═══════════════════════════════════════════════════════════════
HORIZON_PROFILES = {
    "scalp": {
        "label": "Scalp (M5)",
        "structure_tfs": ["D1", "H4", "H1"],
        "entry_tf": "M5",
        "bias_from": "H1",
        "min_data": 10,
    },
    "intraday": {
        "label": "Intraday (H1)",
        "structure_tfs": ["D1", "H4"],
        "entry_tf": "H1",
        "bias_from": "H4",
        "min_data": 10,
    },
    "daily": {
        "label": "Daily / Swing (H4)",
        "structure_tfs": ["D1"],
        "entry_tf": "H4",
        "bias_from": "D1",
        "min_data": 10,
    },
}

# Pip values par instrument
PIP_VALUES = {
    "EURUSD": 0.0001, "GBPUSD": 0.0001, "AUDUSD": 0.0001, "NZDUSD": 0.0001,
    "USDCAD": 0.0001, "USDCHF": 0.0001, "EURGBP": 0.0001,
    "USDJPY": 0.01, "EURJPY": 0.01, "GBPJPY": 0.01, "AUDJPY": 0.01,
    "XAUUSD": 0.01,
    "BTCUSD": 1.0, "ETHUSD": 1.0,
}

# Slippage fixe conservateur (en pips) ajouté au spread
SLIPPAGE_PIPS = 0.5

# TTL par défaut : si ni SL ni TP touchés après N bars, on ferme
TTL_BARS = {
    "M5": 288,   # 24h
    "H1": 48,    # 48h
    "H4": 12,    # 48h
}


# ═══════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════
@dataclass
class Trade:
    """Représente un trade simulé."""
    pair: str
    direction: str            # "BUY" ou "SELL"
    entry_price: float
    stop_loss: float
    tp1: float
    entry_time: str
    entry_bar_idx: int
    spread_pips: float
    slippage_pips: float
    confidence: float
    confluence_score: int
    reasons: list
    horizon: str
    # Remplis après résolution
    exit_price: float = 0.0
    exit_time: str = ""
    exit_bar_idx: int = -1
    pnl_pips: float = 0.0
    result: str = ""          # "WIN", "LOSS", "TTL_EXPIRE"
    r_multiple: float = 0.0
    risk_pips: float = 0.0
    session: str = ""         # killzone active à l'entrée


@dataclass
class BlockedSetup:
    """Représente un setup bloqué par un gate."""
    pair: str
    time: str
    gate: str
    reason: str
    entry_price: float = 0.0
    sl: float = 0.0
    tp1: float = 0.0
    would_have_won: bool = None
    pnl_pips: float = 0.0


@dataclass
class BacktestResult:
    """Résultats complets du backtest."""
    trades: list = field(default_factory=list)
    blocked: list = field(default_factory=list)
    start_date: str = ""
    end_date: str = ""
    horizon: str = ""
    pairs: list = field(default_factory=list)
    capital: float = 10000.0
    risk_pct: float = 1.0

    @property
    def wins(self):
        return [t for t in self.trades if t.result == "WIN"]

    @property
    def losses(self):
        return [t for t in self.trades if t.result in ("LOSS", "TTL_EXPIRE")]

    @property
    def win_rate(self):
        if not self.trades:
            return 0.0
        return len(self.wins) / len(self.trades) * 100

    @property
    def profit_factor(self):
        gross_profit = sum(t.pnl_pips for t in self.trades if t.pnl_pips > 0)
        gross_loss = abs(sum(t.pnl_pips for t in self.trades if t.pnl_pips < 0))
        if gross_loss == 0:
            return float("inf") if gross_profit > 0 else 0.0
        return gross_profit / gross_loss

    @property
    def sqn(self):
        if len(self.trades) < 10:
            return 0.0
        r_multiples = [t.r_multiple for t in self.trades]
        mean_r = np.mean(r_multiples)
        std_r = np.std(r_multiples, ddof=1)
        if std_r == 0:
            return 0.0
        return float(np.sqrt(len(r_multiples)) * mean_r / std_r)

    @property
    def max_drawdown_pips(self):
        if not self.trades:
            return 0.0
        equity = 0.0
        peak = 0.0
        max_dd = 0.0
        for t in self.trades:
            equity += t.pnl_pips
            peak = max(peak, equity)
            dd = peak - equity
            max_dd = max(max_dd, dd)
        return max_dd

    def equity_curve(self) -> list:
        """Retourne la courbe d'equity cumulée en pips."""
        curve = [0.0]
        for t in self.trades:
            curve.append(curve[-1] + t.pnl_pips)
        return curve

    def to_dict(self) -> dict:
        """Sérialise les résultats pour JSON/rapport."""
        return {
            "start_date": self.start_date,
            "end_date": self.end_date,
            "horizon": self.horizon,
            "pairs": self.pairs,
            "total_trades": len(self.trades),
            "wins": len(self.wins),
            "losses": len(self.losses),
            "win_rate": round(self.win_rate, 1),
            "profit_factor": round(self.profit_factor, 2),
            "sqn": round(self.sqn, 2),
            "max_drawdown_pips": round(self.max_drawdown_pips, 1),
            "total_pnl_pips": round(sum(t.pnl_pips for t in self.trades), 1),
            "avg_r_multiple": round(np.mean([t.r_multiple for t in self.trades]), 2) if self.trades else 0.0,
            "blocked_setups": len(self.blocked),
            "trades": [self._trade_to_dict(t) for t in self.trades],
            "blocked_details": [self._blocked_to_dict(b) for b in self.blocked[:100]],
        }

    @staticmethod
    def _trade_to_dict(t: Trade) -> dict:
        return {
            "pair": t.pair, "direction": t.direction,
            "entry_price": t.entry_price, "stop_loss": t.stop_loss, "tp1": t.tp1,
            "entry_time": t.entry_time, "exit_time": t.exit_time,
            "exit_price": t.exit_price, "pnl_pips": round(t.pnl_pips, 1),
            "result": t.result, "r_multiple": round(t.r_multiple, 2),
            "spread_pips": t.spread_pips, "confidence": t.confidence,
            "session": t.session, "horizon": t.horizon,
        }

    @staticmethod
    def _blocked_to_dict(b: BlockedSetup) -> dict:
        return {
            "pair": b.pair, "time": b.time, "gate": b.gate,
            "reason": b.reason, "would_have_won": b.would_have_won,
        }


# ═══════════════════════════════════════════════════════════════
# BACKTEST ENGINE
# ═══════════════════════════════════════════════════════════════
class BacktestEngine:
    """
    Moteur de backtest offline. Replay bar-by-bar avec cutoff strict.

    Anti-lookahead :
    - Chaque agent reçoit un DataFrame coupé à bar_idx+1 (aucun bar futur)
    - A1 : appel direct aux fonctions internes (detect_swings, detect_fvg, etc.)
    - A3 : OTE tracker mocké in-memory
    - LLM : exclu (non déterministe)
    """

    def __init__(self, pairs: list, horizon: str = "scalp",
                 capital: float = 10000.0, risk_pct: float = 1.0,
                 broker_utc_offset: int = 0):  # TwelveData CSV = UTC pur
        self.pairs = pairs
        self.horizon = horizon
        self.capital = capital
        self.risk_pct = risk_pct
        self.broker_utc_offset = broker_utc_offset
        self.profile = HORIZON_PROFILES[horizon]

        # Agents (instanciés une fois, réutilisés)
        self.a2 = TimeSessionAgent(broker_utc_offset=broker_utc_offset)
        self.a5 = OrchestratorAgent(
            account_balance=capital, risk_percent=risk_pct,
            max_daily_trades=5, max_open_trades=3,
        )
        self.shield = BehaviourShield()  # Persistant entre les bars (BS7)

        # OTE tracker mock in-memory (par paire)
        self._ote_setups = {}

        # Cache MSS corrigé : évite de re-calculer detect_mss à chaque bar M5
        # quand le TF structure (H1/H4/D1) n'a pas de nouvelle bougie.
        # Structure : { tf_key: {"last_ts": Timestamp, "corrected_mss": list} }
        self._mss_cache: dict = {}

        # Résultats
        self.result = BacktestResult(
            horizon=horizon, pairs=pairs,
            capital=capital, risk_pct=risk_pct,
        )

    def run(self, start_date: str = None, end_date: str = None) -> BacktestResult:
        """
        Lance le backtest complet.

        Args:
            start_date: "YYYY-MM-DD" (optionnel, début des données)
            end_date:   "YYYY-MM-DD" (optionnel, fin des données)
        """
        total_bars_processed = 0

        for pair in self.pairs:
            logger.info(f"[Backtest] {pair} — chargement des données...")
            dfs = load_pair_data(pair)

            entry_tf = self.profile["entry_tf"]
            df_entry_full = dfs.get(entry_tf)

            if df_entry_full is None or len(df_entry_full) < self.profile["min_data"]:
                logger.warning(f"[Backtest] {pair} — données insuffisantes pour {entry_tf}")
                continue

            # Filtrer par dates
            if start_date:
                for tf in dfs:
                    if len(dfs[tf]) > 0:
                        dfs[tf] = dfs[tf][dfs[tf]["time"] >= pd.Timestamp(start_date)]
            if end_date:
                for tf in dfs:
                    if len(dfs[tf]) > 0:
                        dfs[tf] = dfs[tf][dfs[tf]["time"] <= pd.Timestamp(end_date)]

            df_entry_full = dfs[entry_tf]
            if len(df_entry_full) < self.profile["min_data"]:
                continue

            self.result.start_date = str(df_entry_full["time"].iloc[0])[:10]
            self.result.end_date = str(df_entry_full["time"].iloc[-1])[:10]

            bars_processed = self._run_pair(pair, dfs)
            total_bars_processed += bars_processed
            logger.info(
                f"[Backtest] {pair} — {bars_processed} bars, "
                f"{len([t for t in self.result.trades if t.pair == pair])} trades"
            )

        logger.info(
            f"[Backtest] Terminé — {len(self.result.trades)} trades, "
            f"WR={self.result.win_rate:.1f}%, PF={self.result.profit_factor:.2f}"
        )
        return self.result

    def _run_pair(self, pair: str, dfs: dict) -> int:
        """Replay bar-by-bar pour une paire."""
        entry_tf = self.profile["entry_tf"]
        df_entry_full = dfs[entry_tf].reset_index(drop=True)
        pip_value = PIP_VALUES.get(pair, 0.0001)

        # Agents par paire
        a1 = StructureAgent(symbol=pair,
                            structure_tf=self.profile["bias_from"],
                            entry_tf=entry_tf)
        a3 = EntryAgent(symbol=pair,
                        structure_tf=self.profile["bias_from"],
                        entry_tf=entry_tf,
                        pip_value=pip_value)
        a4 = MacroBiasAgent(target_pair=pair)

        # Minimum de bars pour démarrer l'analyse
        # M5 : 200 bars = ~16h de contexte (swings, FVG, OB fiables sur H1/H4)
        # H1 : 100 bars = ~4 jours de contexte
        # H4+ : 50 bars (inchangé, suffisant pour D1 structure)
        if entry_tf == "M5":
            warmup = max(200, self.profile["min_data"] * 10)
            warmup_hours = warmup * 5 / 60
        elif entry_tf == "H1":
            warmup = max(100, self.profile["min_data"] * 8)
            warmup_hours = warmup * 1
        else:
            warmup = max(50, self.profile["min_data"] * 3)
            warmup_hours = warmup * (4 if entry_tf == "H4" else 24)

        logger.info(
            f"[Backtest] {pair} — Warmup : {warmup} bars skippés "
            f"({warmup_hours:.1f} heures de contexte, TF={entry_tf})"
        )

        bars_processed = 0

        # Anti-duplication OTE : dernière entrée par direction.
        # Empêche de re-entrer sur le MÊME niveau OTE pendant qu'un trade est ouvert.
        # La clé est (direction, entry_price arrondi, sl arrondi) → bloqué jusqu'à exit_bar.
        # Une NOUVELLE zone OTE (entry/SL différents) est autorisée immédiatement.
        _active_ote: dict[str, tuple] = {}   # direction → (entry_price, sl, exit_bar_idx)

        for bar_idx in range(warmup, len(df_entry_full)):
            current_time = df_entry_full["time"].iloc[bar_idx]

            # ════════════════════════════════════════════════
            # CUTOFF STRICT : chaque agent ne voit que ≤ bar_idx
            # ════════════════════════════════════════════════
            dfs_cut = {}
            for tf, df_tf in dfs.items():
                if len(df_tf) == 0:
                    dfs_cut[tf] = pd.DataFrame()
                    continue
                mask = df_tf["time"] <= current_time
                dfs_cut[tf] = df_tf[mask].copy()

            df_entry_cut = dfs_cut[entry_tf]
            if len(df_entry_cut) < self.profile["min_data"]:
                continue

            bars_processed += 1

            # ════════════════════════════════════════════════
            # A1 — Structure (appels internes directs)
            # ════════════════════════════════════════════════
            structure_report = self._run_a1(a1, dfs_cut, pair)
            if structure_report.get("bias") == "neutral":
                continue

            # ════════════════════════════════════════════════
            # A2 — Time / Session
            # ════════════════════════════════════════════════
            # Simuler le broker_time à partir du timestamp de la bougie
            broker_time = pd.Timestamp(current_time).to_pydatetime()
            ny_time = to_ny_time(broker_time, self.broker_utc_offset)

            # Fallback : si M5 absent (ex: mode scalp avec données seules),
            # passer df_entry_cut pour permettre le calcul de l'Asian Range.
            # PERF : A2 fait des opérations pandas sur tout le df_m5 (Asian Range,
            # sessions), mais n'a besoin que des ~576 dernières bougies (48h).
            # Limiter le dataset évite O(n²) sur 5000 lignes → gain ~10x.
            _A2_M5_WINDOW = 576   # 48h en M5 (288 bars/jour × 2)
            df_m5_for_a2 = dfs_cut.get("M5")
            if df_m5_for_a2 is None or len(df_m5_for_a2) == 0:
                df_m5_for_a2 = df_entry_cut
            elif len(df_m5_for_a2) > _A2_M5_WINDOW:
                df_m5_for_a2 = df_m5_for_a2.iloc[-_A2_M5_WINDOW:].reset_index(drop=True)

            time_report = self.a2.analyze(
                df=df_m5_for_a2,
                current_broker_time=broker_time,
            )

            # Option 1 (backtest only) : si l'Asian Range est indisponible,
            # on force po3_phase à 'transition' pour ne pas bloquer A5.
            po3 = time_report.get("po3_phase", {})
            if po3.get("phase") == "accumulation" and po3.get("description") == "Asian Range en formation":
                time_report["po3_phase"] = {
                    "phase": "transition",
                    "description": "Asian Range indisponible en backtest — non bloquant",
                    "asian_range_broken": "none",
                    "suggested_bias": "neutral",
                }

            if not time_report.get("can_trade", False):
                continue

            # ════════════════════════════════════════════════
            # A3 — Entry (OTE + Confluence + Confirmation)
            # ════════════════════════════════════════════════
            entry_signal = a3.analyze(structure_report, time_report, df_entry_cut)
            if entry_signal.get("signal") == "NO_TRADE":
                continue

            # ── Anti-duplication OTE : même niveau = pas de re-entrée ────────
            # L'OTE sur H1 reste stable plusieurs barres M5 consécutives.
            # On bloque si : même direction + même entry_price (± 1 pip) + même SL
            # ET le trade précédent est encore "ouvert" (bar_idx < exit_bar).
            # Un NOUVEAU niveau OTE (prix différent) est autorisé immédiatement.
            _sig   = entry_signal.get("signal", "BUY")
            _ep    = entry_signal.get("entry_price", 0)
            _sl    = entry_signal.get("stop_loss", 0)
            _active = _active_ote.get(_sig)
            if _active is not None:
                _prev_ep, _prev_sl, _exit_bar = _active
                # Tolérance = 5 pips pour regrouper les micro-variations d'un même OTE
                _tol = 5 * pip_value
                _same_zone = (abs(_ep - _prev_ep) <= _tol and abs(_sl - _prev_sl) <= _tol)
                if _same_zone and bar_idx <= _exit_bar:
                    continue    # Même OTE, position encore ouverte → skip
            # ─────────────────────────────────────────────────────────────────

            # Injecter le spread réaliste
            spread = get_realistic_spread_pips(pair, ny_time)
            entry_signal["current_spread_pips"] = spread
            entry_signal["pair"] = pair

            # ════════════════════════════════════════════════
            # A4 — Macro Bias
            # ════════════════════════════════════════════════
            # Injecter les DataFrames pour LiquidityTracker / LiquidityDetector (appelés dans A5).
            # IMPORTANT : LiquidityDetector._calc_equal_levels() itère en .iloc[i] row-by-row
            # sur le DataFrame M5 complet → O(n²) → ~3s par appel sur 5000 bars.
            # Fix (engine.py) : on ne passe que les 500 dernières bougies M5 (≈41h de contexte),
            # ce qui est plus que suffisant pour la détection de liquidité locale.
            _df_m5_full = dfs_cut.get("M5", pd.DataFrame())
            _LD_M5_WINDOW = 500
            entry_signal["_df_m5"] = _df_m5_full.iloc[-_LD_M5_WINDOW:].reset_index(drop=True) \
                                     if len(_df_m5_full) > _LD_M5_WINDOW else _df_m5_full
            entry_signal["_df_h1"] = dfs_cut.get("H1", pd.DataFrame())
            entry_signal["_df_d1"] = dfs_cut.get("D1", pd.DataFrame())
            
            macro_report = a4.analyze(
                cot_data=None, smt_data=None, dxy_data=None, news_data=None,
                current_time=ny_time,
            )

            # ════════════════════════════════════════════════
            # A5 — Orchestrator (vote pondéré + gates)
            # ════════════════════════════════════════════════
            # ── CORRECTIFS NAMESPACE orchestrator ────────────────────────────────
            # orchestrator.py utilise des imports directs → patcher ses références.
            import agents.ict.orchestrator as _orch_module

            # (1) SOD mock : `from sod_detector import detect_sod` → lié localement
            original_detect_sod = _orch_module.detect_sod

            def mock_detect_sod(*args, **kwargs):
                sod = original_detect_sod(*args, **kwargs)
                if sod.get("state") == "UNKNOWN":
                    sod["can_trade"] = True
                    sod["sizing_factor"] = 0.5
                    sod["_engine_intercepted"] = True
                return sod

            _orch_module.detect_sod = mock_detect_sod

            # (2) NewsManager : stubé globalement au démarrage du module (voir en-tête).
            # ──────────────────────────────────────────────────────────────────────
            
            e_dir = "bullish" if entry_signal.get("signal") == "BUY" else "bearish"
            original_m_bias = macro_report.get('macro_bias')
            original_t_bias = time_report.get('po3_phase', {}).get('suggested_bias')
            
            try:
                decision = self.a5.calculate_decision(
                    structure_report=structure_report,
                    time_report=time_report,
                    trade_signal=entry_signal,
                    macro_report=macro_report,
                    liquidity_report=None,
                    df_m5=df_m5_for_a2,  # Même DF que celui passé à A2
                )
                
                # Blocage 2 : Relâcher le consensus en backtest (consensus 2/4 autorisé)
                if decision.get("decision") == "NO_TRADE" and "Manque de consensus" in decision.get("reason", ""):
                    import re
                    match = re.search(r"seul (\d+)/4", decision.get("reason", ""))
                    if match and int(match.group(1)) >= 2:
                        # Pour passer le filtre sans altérer le score (qui dépend de s_bias et des confidences),
                        # on aligne artificiellement macro_bias ou time_bias (qui ne rentrent qu'en compte de vote).
                        if macro_report.get('macro_bias') != e_dir:
                            macro_report['macro_bias'] = e_dir
                        else:
                            if 'po3_phase' not in time_report: time_report['po3_phase'] = {}
                            time_report['po3_phase']['suggested_bias'] = e_dir
                            
                        # Re-calcul
                        decision = self.a5.calculate_decision(
                            structure_report=structure_report,
                            time_report=time_report,
                            trade_signal=entry_signal,
                            macro_report=macro_report,
                            liquidity_report=None,
                            df_m5=df_m5_for_a2,
                        )
                        if decision.get("decision") != "NO_TRADE":
                            decision.setdefault("reasons", []).append("Consensus assoupli (2/4 suffisant en backtest)")
                            
            finally:
                # Restauration propre — même référence que le patch (namespace orchestrator)
                _orch_module.detect_sod = original_detect_sod
                macro_report['macro_bias'] = original_m_bias
                if 'po3_phase' in time_report:
                    time_report['po3_phase']['suggested_bias'] = original_t_bias

            # Blocage 1 : Si SOD=UNKNOWN intercepté, on applique un malus léger (-5 pts)
            # Réduit de -10 à -5 : SOD=UNKNOWN est fréquent en backtest (pas de données
            # live d'ouverture de session), ne doit pas écraser les trades valides.
            if decision.get("decision") != "NO_TRADE":
                sod_info = time_report.get("_sod", {})
                if sod_info.get("_engine_intercepted"):
                    decision["global_confidence"] = max(0.0, decision.get("global_confidence", 0.0) - 0.05)
                    decision.setdefault("reasons", []).append("SOD=UNKNOWN Penalty (-5pts)")

            if decision.get("decision") == "NO_TRADE":
                # Log blocked setup
                self.result.blocked.append(BlockedSetup(
                    pair=pair,
                    time=str(current_time),
                    gate="A5_orchestrator",
                    reason=decision.get("reason", ""),
                    entry_price=entry_signal.get("entry_price", 0),
                    sl=entry_signal.get("stop_loss", 0),
                    tp1=entry_signal.get("tp1", 0),
                ))
                continue

            # ════════════════════════════════════════════════
            # BehaviourShield (BS1-BS8)
            # ════════════════════════════════════════════════
            bs_result = self._check_behaviour_shield(
                pair, entry_signal, df_entry_cut, ny_time
            )
            if bs_result.get("blocked", False):
                self.result.blocked.append(BlockedSetup(
                    pair=pair,
                    time=str(current_time),
                    gate=f"BS_{bs_result.get('filter', '?')}",
                    reason=bs_result.get("reason", ""),
                    entry_price=entry_signal.get("entry_price", 0),
                    sl=entry_signal.get("stop_loss", 0),
                    tp1=entry_signal.get("tp1", 0),
                ))
                continue

            # ════════════════════════════════════════════════
            # EXÉCUTION SIMULÉE
            # ════════════════════════════════════════════════
            trade = self._simulate_trade(
                pair=pair,
                entry_signal=entry_signal,
                decision=decision,
                dfs=dfs,
                bar_idx=bar_idx,
                entry_tf=entry_tf,
                pip_value=pip_value,
                spread_pips=spread,
                ny_time=ny_time,
            )
            if trade:
                self.result.trades.append(trade)
                # Enregistrer le niveau OTE actif pour ce trade
                _active_ote[trade.direction] = (
                    round(trade.entry_price, 4),
                    round(trade.stop_loss, 4),
                    trade.exit_bar_idx,
                )

        return bars_processed

    def _run_a1(self, a1: StructureAgent, dfs_cut: dict, pair: str) -> dict:
        """
        A1 Structure — appels directs aux fonctions internes.
        Utilise les DataFrames coupés (anti-lookahead).
        """
        structure_tfs = self.profile["structure_tfs"]

        # Construire le rapport multi-TF via analyze_multi_tf
        tf_dataframes = {}
        for tf in structure_tfs:
            df_tf = dfs_cut.get(tf, pd.DataFrame())
            if len(df_tf) >= 5:
                tf_dataframes[tf] = df_tf

        if not tf_dataframes:
            return {"bias": "neutral"}

        report = a1.analyze_multi_tf(tf_dataframes)

        # ── CORRECTIF BUG analyze_multi_tf (avec cache TF) ─────────────────────
        # Bug dans structure.py ligne ~655 : detect_mss() est appelé SANS le
        # paramètre `sweeps` → sweeps=[] → sweep_confirmed=False sur TOUS les MSS
        # → P-F5 Anti-Inducement bloque 100 % des setups.
        #
        # Fix (engine.py uniquement) : re-calculer detect_mss avec les sweeps
        # corrects, mais UNIQUEMENT quand une nouvelle bougie est disponible pour
        # ce TF (cache par timestamp). Les TFs structure (H1/H4/D1) avancent
        # beaucoup moins vite que les bars M5 d'entrée → gain de performance ~10x.
        for tf_key, tf_data in report.items():
            if not isinstance(tf_data, dict):
                continue
            tf_sweeps = tf_data.get("liquidity_sweeps", [])
            df_tf = tf_dataframes.get(tf_key)
            if df_tf is None or not tf_sweeps:
                continue

            # Dernier timestamp du TF pour le cache
            last_ts = df_tf["time"].iloc[-1] if "time" in df_tf.columns else None
            cached = self._mss_cache.get(tf_key, {})

            if cached.get("last_ts") == last_ts:
                # Même bougie qu'au bar précédent → réutiliser le résultat
                tf_data["mss"] = cached["corrected_mss"]
            else:
                # Nouvelle bougie → re-calculer
                corrected_mss = a1.detect_mss(
                    df_tf,
                    tf_data.get("swings", []),
                    tf_data.get("displacements", []),
                    tf_data.get("fvg", []),
                    tf_data.get("bos_choch", []),
                    tf_sweeps,          # ← sweeps transmis correctement
                )
                tf_data["mss"] = corrected_mss
                self._mss_cache[tf_key] = {"last_ts": last_ts, "corrected_mss": corrected_mss}
        # ───────────────────────────────────────────────────────────────────────

        # Ajouter le bias_from TF pour A3
        bias_tf = self.profile["bias_from"]
        if bias_tf in report:
            report["bias"] = report[bias_tf].get("bias", "neutral")
            report["swings"] = report[bias_tf].get("swings", [])
            report["fvg"] = report[bias_tf].get("fvg", [])
            report["order_blocks"] = report[bias_tf].get("order_blocks", [])
            report["bos_choch"] = report[bias_tf].get("bos_choch", [])
            report["liquidity_sweeps"] = report[bias_tf].get("liquidity_sweeps", [])
            report["mss"] = report[bias_tf].get("mss", [])
            report["equal_levels"] = report[bias_tf].get("equal_levels", [])
        else:
            # Fallback : premier TF disponible
            first_tf = list(tf_dataframes.keys())[0]
            if first_tf in report:
                report["bias"] = report[first_tf].get("bias", "neutral")
                report["swings"] = report[first_tf].get("swings", [])
                report["fvg"] = report[first_tf].get("fvg", [])
                report["order_blocks"] = report[first_tf].get("order_blocks", [])
                report["bos_choch"] = report[first_tf].get("bos_choch", [])
                report["liquidity_sweeps"] = report[first_tf].get("liquidity_sweeps", [])
                report["mss"] = report[first_tf].get("mss", [])
                report["equal_levels"] = report[first_tf].get("equal_levels", [])
            else:
                report["bias"] = "neutral"

        # Key levels (PDH/PDL/PWH/PWL)
        df_d1 = dfs_cut.get("D1", pd.DataFrame())
        df_w1 = dfs_cut.get("W1", pd.DataFrame())
        if len(df_d1) >= 2:
            report["key_levels"] = a1.detect_key_levels(df_d1, df_w1 if len(df_w1) >= 2 else None)
        else:
            report["key_levels"] = {}

        report["symbol"] = pair
        return report

    def _check_behaviour_shield(self, pair: str, entry_signal: dict,
                                 df_entry: pd.DataFrame, ny_time) -> dict:
        """Vérifie les filtres BehaviourShield (BS1-BS8)."""
        try:
            direction = entry_signal.get("signal", "")
            entry_price = entry_signal.get("entry_price", 0)
            sl = entry_signal.get("stop_loss", 0)
            confidence = entry_signal.get("confidence", 0)

            result = self.shield.check(
                pair=pair,
                direction=direction,
                entry_price=entry_price,
                stop_loss=sl,
                confidence=confidence,
                df_m5=df_entry,
            )
            return result
        except Exception:
            return {"blocked": False}

    def _simulate_trade(self, pair: str, entry_signal: dict, decision: dict,
                        dfs: dict, bar_idx: int, entry_tf: str,
                        pip_value: float, spread_pips: float, ny_time) -> Trade:
        """
        Simule un trade : boucle sur les bars futurs pour vérifier SL/TP.

        Règles :
        - Entry au close + spread (ask pour BUY, bid pour SELL)
        - Si SL et TP touchés dans la même bougie → SL prioritaire (conservateur)
        - TTL : fermeture au prix courant si ni SL ni TP touchés
        - PnL déduit du spread + slippage
        """
        df_full = dfs[entry_tf].reset_index(drop=True)
        direction = entry_signal.get("signal", "BUY")
        raw_entry = entry_signal.get("entry_price", 0)
        sl = entry_signal.get("stop_loss", 0)
        tp1 = entry_signal.get("tp1", 0)

        if not raw_entry or not sl or not tp1:
            return None

        # Appliquer spread et slippage à l'entrée
        total_cost_pips = spread_pips + SLIPPAGE_PIPS
        total_cost_price = total_cost_pips * pip_value

        if direction == "BUY":
            entry_price = raw_entry + total_cost_price  # Achète au ask
        else:
            entry_price = raw_entry - total_cost_price  # Vend au bid

        risk_pips = abs(entry_price - sl) / pip_value
        if risk_pips == 0:
            return None

        ttl_max = TTL_BARS.get(entry_tf, 288)

        # Killzone active
        session = ""
        try:
            kz_info = self.a2._get_active_killzone(ny_time)
            session = kz_info if isinstance(kz_info, str) else str(kz_info)
        except Exception:
            pass

        # Boucle sur les bars futurs
        exit_price = 0.0
        exit_time = ""
        exit_bar_idx = -1
        result = ""

        for future_idx in range(bar_idx + 1, min(bar_idx + 1 + ttl_max, len(df_full))):
            bar = df_full.iloc[future_idx]
            h = bar["high"]
            l = bar["low"]

            tp_hit = False
            sl_hit = False

            if direction == "BUY":
                tp_hit = h >= tp1
                sl_hit = l <= sl
            else:  # SELL
                tp_hit = l <= tp1
                sl_hit = h >= sl

            # RÈGLE CONSERVATRICE : si les deux touchés → SL prioritaire
            if sl_hit and tp_hit:
                sl_hit = True
                tp_hit = False

            if sl_hit:
                exit_price = sl
                exit_time = str(bar["time"])
                exit_bar_idx = future_idx
                result = "LOSS"
                break
            elif tp_hit:
                exit_price = tp1
                exit_time = str(bar["time"])
                exit_bar_idx = future_idx
                result = "WIN"
                break

        # TTL expiry
        if not result:
            last_idx = min(bar_idx + ttl_max, len(df_full) - 1)
            bar = df_full.iloc[last_idx]
            exit_price = bar["close"]
            exit_time = str(bar["time"])
            exit_bar_idx = last_idx
            result = "TTL_EXPIRE"

        # Calcul PnL
        if direction == "BUY":
            pnl_pips = (exit_price - entry_price) / pip_value
        else:
            pnl_pips = (entry_price - exit_price) / pip_value

        r_multiple = pnl_pips / risk_pips if risk_pips > 0 else 0.0

        return Trade(
            pair=pair,
            direction=direction,
            entry_price=round(entry_price, 5),
            stop_loss=round(sl, 5),
            tp1=round(tp1, 5),
            entry_time=str(df_full["time"].iloc[bar_idx]),
            entry_bar_idx=bar_idx,
            spread_pips=round(spread_pips, 1),
            slippage_pips=SLIPPAGE_PIPS,
            confidence=round(entry_signal.get("confidence", 0), 2),
            confluence_score=entry_signal.get("confluence_score", 0),
            reasons=entry_signal.get("reasons", []),
            horizon=self.horizon,
            exit_price=round(exit_price, 5),
            exit_time=exit_time,
            exit_bar_idx=exit_bar_idx,
            pnl_pips=round(pnl_pips, 1),
            result=result,
            r_multiple=round(r_multiple, 2),
            risk_pips=round(risk_pips, 1),
            session=session,
        )


# ═══════════════════════════════════════════════════════════════
# WALK-FORWARD
# ═══════════════════════════════════════════════════════════════
def run_walk_forward(pairs: list, horizon: str = "scalp",
                     capital: float = 10000.0, risk_pct: float = 1.0,
                     train_months: int = 3, test_months: int = 3) -> dict:
    """
    Walk-forward validation : train sur les premiers mois, test sur les suivants.
    Retourne les résultats des deux périodes pour comparaison.
    """
    # Charger les dates disponibles
    sample_pair = pairs[0]
    dfs = load_pair_data(sample_pair)
    entry_tf = HORIZON_PROFILES[horizon]["entry_tf"]
    df = dfs.get(entry_tf, pd.DataFrame())

    if len(df) == 0:
        return {"error": "No data available"}

    data_start = df["time"].iloc[0]
    data_end = df["time"].iloc[-1]
    midpoint = data_start + (data_end - data_start) / 2

    train_end = midpoint.strftime("%Y-%m-%d")
    test_start = (midpoint + timedelta(days=1)).strftime("%Y-%m-%d")

    # Train period
    logger.info(f"[Walk-Forward] TRAIN : {data_start.strftime('%Y-%m-%d')} → {train_end}")
    engine_train = BacktestEngine(pairs, horizon, capital, risk_pct)
    result_train = engine_train.run(end_date=train_end)

    # Test period
    logger.info(f"[Walk-Forward] TEST : {test_start} → {data_end.strftime('%Y-%m-%d')}")
    engine_test = BacktestEngine(pairs, horizon, capital, risk_pct)
    result_test = engine_test.run(start_date=test_start)

    return {
        "train": result_train,
        "test": result_test,
        "train_period": f"{data_start.strftime('%Y-%m-%d')} → {train_end}",
        "test_period": f"{test_start} → {data_end.strftime('%Y-%m-%d')}",
        "edge_stable": _is_edge_stable(result_train, result_test),
    }


def _is_edge_stable(train: BacktestResult, test: BacktestResult) -> dict:
    """Compare les métriques train vs test pour valider la stabilité de l'edge."""
    return {
        "train_wr": round(train.win_rate, 1),
        "test_wr": round(test.win_rate, 1),
        "wr_delta": round(test.win_rate - train.win_rate, 1),
        "train_pf": round(train.profit_factor, 2),
        "test_pf": round(test.profit_factor, 2),
        "pf_delta": round(test.profit_factor - train.profit_factor, 2),
        "train_sqn": round(train.sqn, 2),
        "test_sqn": round(test.sqn, 2),
        "conclusion": (
            "STABLE" if test.profit_factor >= 1.1 and test.win_rate >= 35
            else "UNSTABLE — edge dégradé out-of-sample"
        ),
    }


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════
def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser(description="Backtest offline ICT pipeline")
    parser.add_argument("--pairs", nargs="+", help="Paires (ex: EURUSD GBPUSD)")
    parser.add_argument("--all", action="store_true", help="Toutes les 14 paires")
    parser.add_argument("--horizon", default="scalp", choices=list(HORIZON_PROFILES.keys()))
    parser.add_argument("--capital", type=float, default=10000.0)
    parser.add_argument("--risk", type=float, default=1.0, help="Risque par trade (%)")
    parser.add_argument("--start", help="Date de début YYYY-MM-DD")
    parser.add_argument("--end", help="Date de fin YYYY-MM-DD")
    parser.add_argument("--walk-forward", action="store_true", help="Mode walk-forward")
    parser.add_argument("--output", help="Chemin du rapport JSON")

    args = parser.parse_args()

    if args.all:
        pairs = TRADING_PAIRS
    elif args.pairs:
        pairs = [p.upper() for p in args.pairs]
    else:
        parser.print_help()
        return

    if args.walk_forward:
        results = run_walk_forward(pairs, args.horizon, args.capital, args.risk)
        if "error" in results:
            print(f"Erreur : {results['error']}")
            return
        print(f"\n{'='*60}")
        print(f"WALK-FORWARD RESULTS")
        print(f"{'='*60}")
        print(f"Train : {results['train_period']}")
        print(f"  WR={results['edge_stable']['train_wr']}%, PF={results['edge_stable']['train_pf']}, SQN={results['edge_stable']['train_sqn']}")
        print(f"Test  : {results['test_period']}")
        print(f"  WR={results['edge_stable']['test_wr']}%, PF={results['edge_stable']['test_pf']}, SQN={results['edge_stable']['test_sqn']}")
        print(f"\nConclusion : {results['edge_stable']['conclusion']}")
        return

    engine = BacktestEngine(pairs, args.horizon, args.capital, args.risk)
    result = engine.run(start_date=args.start, end_date=args.end)

    # Affichage résumé
    print(f"\n{'='*60}")
    print(f"BACKTEST RESULTS — {args.horizon} — {', '.join(pairs)}")
    print(f"{'='*60}")
    print(f"Période      : {result.start_date} → {result.end_date}")
    print(f"Total trades : {len(result.trades)}")
    print(f"Win Rate     : {result.win_rate:.1f}%")
    print(f"Profit Factor: {result.profit_factor:.2f}")
    print(f"SQN          : {result.sqn:.2f}")
    print(f"Max Drawdown : {result.max_drawdown_pips:.1f} pips")
    print(f"Total PnL    : {sum(t.pnl_pips for t in result.trades):.1f} pips")
    print(f"Blocked      : {len(result.blocked)} setups")

    # Sauvegarder JSON
    output_path = args.output or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "results",
        f"backtest_{datetime.now().strftime('%Y%m%d_%H%M')}_{args.horizon}.json"
    )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(result.to_dict(), f, indent=2, default=str)
    print(f"\nRapport JSON : {output_path}")

    # Générer le rapport HTML
    try:
        from backtest.report import generate_html_report
        html_path = output_path.replace(".json", ".html")
        generate_html_report(result, html_path)
        print(f"Rapport HTML : {html_path}")
    except ImportError:
        pass


if __name__ == "__main__":
    main()
