"""
VSA Volume Analyzer — Agent Expert Wyckoff v3.0
Détections 100% mathématiques, zéro LLM, zéro subjectivité.
Sources : Richard D. Wyckoff, Tom Williams (Master the Markets)
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


# ─────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────

class VolumeLevel(Enum):
    LOW        = "LOW"
    AVERAGE    = "AVERAGE"
    HIGH       = "HIGH"
    ULTRA_HIGH = "ULTRA_HIGH"

class SpreadLevel(Enum):
    ULTRA_NARROW = "ULTRA_NARROW"
    NARROW       = "NARROW"
    AVERAGE      = "AVERAGE"
    WIDE         = "WIDE"
    ULTRA_WIDE   = "ULTRA_WIDE"

class ClosePosition(Enum):
    LOW    = "LOW"      # 0–33%
    MIDDLE = "MIDDLE"   # 34–66%
    HIGH   = "HIGH"     # 67–100%

class VSASignal(Enum):
    # Signs of Strength (SOS) — Haussiers
    NO_SUPPLY           = "NO_SUPPLY"
    TEST_SUCCESS        = "TEST_SUCCESS"
    STOPPING_VOLUME     = "STOPPING_VOLUME"
    SELLING_CLIMAX      = "SELLING_CLIMAX"
    PUSH_THROUGH_SUPPLY = "PUSH_THROUGH_SUPPLY"
    BOTTOM_REVERSAL     = "BOTTOM_REVERSAL"
    REVERSE_UPTHRUST    = "REVERSE_UPTHRUST"
    SHAKE_AND_RALLY     = "SHAKE_AND_RALLY"
    SQUAT_BULLISH       = "SQUAT_BULLISH"
    BAG_HOLDING_BULL    = "BAG_HOLDING_BULL"
    SHAKEOUT            = "SHAKEOUT"

    # Signs of Weakness (SOW) — Baissiers
    NO_DEMAND           = "NO_DEMAND"
    UPTHRUST            = "UPTHRUST"
    HIDDEN_UPTHRUST     = "HIDDEN_UPTHRUST"
    BUYING_CLIMAX       = "BUYING_CLIMAX"
    END_RISING_MARKET   = "END_RISING_MARKET"
    TOP_REVERSAL        = "TOP_REVERSAL"
    PSEUDO_UPTHRUST     = "PSEUDO_UPTHRUST"
    SQUAT_BEARISH       = "SQUAT_BEARISH"
    INVERSE_SQUAT       = "INVERSE_SQUAT"
    BAG_HOLDING_BEAR    = "BAG_HOLDING_BEAR"

    NEUTRAL             = "NEUTRAL"

class WyckoffPhase(Enum):
    ACCUMULATION_A = "ACCUMULATION_A"
    ACCUMULATION_B = "ACCUMULATION_B"
    ACCUMULATION_C = "ACCUMULATION_C"
    ACCUMULATION_D = "ACCUMULATION_D"
    MARKUP         = "MARKUP"
    DISTRIBUTION_A = "DISTRIBUTION_A"
    DISTRIBUTION_B = "DISTRIBUTION_B"
    DISTRIBUTION_C = "DISTRIBUTION_C"
    DISTRIBUTION_D = "DISTRIBUTION_D"
    MARKDOWN       = "MARKDOWN"
    UNDEFINED      = "UNDEFINED"

class WyckoffCycle(Enum):
    ACCUMULATION = "ACCUMULATION"
    MARKUP       = "MARKUP"
    DISTRIBUTION = "DISTRIBUTION"
    MARKDOWN     = "MARKDOWN"
    UNDEFINED    = "UNDEFINED"


# ─────────────────────────────────────────────
# DATACLASSES
# ─────────────────────────────────────────────

@dataclass
class BarMetrics:
    """Métriques calculées pour une bougie."""
    index: int
    volume_ratio: float       # Volume / SMA(Volume,20)
    spread_ratio: float       # Spread / ATR(14)
    close_pos: float          # (Close-Low)/(High-Low)
    divergence_score: float   # volume_ratio / spread_ratio
    volume_level: VolumeLevel
    spread_level: SpreadLevel
    close_position: ClosePosition
    upper_wick_ratio: float   # mèche haute / spread
    lower_wick_ratio: float   # mèche basse / spread
    is_bullish: bool
    spread: float
    volume: float

@dataclass
class VSAResult:
    """Résultat d'analyse VSA d'une bougie."""
    signal: VSASignal
    direction: str            # "BULL", "BEAR", "NEUTRAL"
    strength: float           # 0.0–1.0
    description: str
    is_sos: bool
    is_sow: bool
    metrics: BarMetrics

@dataclass
class WyckoffState:
    """État courant du cycle de Wyckoff."""
    cycle: WyckoffCycle
    phase: WyckoffPhase
    sc_level: Optional[float]   # niveau du Selling Climax
    bc_level: Optional[float]   # niveau du Buying Climax
    ar_level: Optional[float]   # niveau de l'Automatic Rally/Reaction
    creek_level: Optional[float]
    ice_level: Optional[float]
    spring_detected: bool = False
    utad_detected: bool = False
    supply_score: float = 0.0
    demand_score: float = 0.0

@dataclass
class VSAAnalysis:
    """Analyse VSA complète sur un ensemble de bougies."""
    symbol: str
    timeframe: str
    last_bar_result: VSAResult
    wyckoff_state: WyckoffState
    recent_signals: list = field(default_factory=list)   # 10 derniers signaux
    demand_zones: list = field(default_factory=list)
    supply_zones: list = field(default_factory=list)
    balance: float = 0.0          # Demand - Supply balance
    absorption_detected: bool = False
    multi_signal_count: int = 0
    raw_score: float = 0.0        # score algo brut avant Gemini


# ─────────────────────────────────────────────
# VOLUME ANALYZER
# ─────────────────────────────────────────────

class VolumeAnalyzer:
    """
    Analyse VSA/Wyckoff purement algorithmique.
    Implémente l'intégralité de l'encyclopédie VSA v3.0.
    """

    def __init__(self):
        self.SMA_PERIOD   = 20
        self.ATR_PERIOD   = 14
        self.VOLUME_LOOKBACK = 50   # pour ultra-high (max 50 bougies)

    # ──────────────────────────────────────────
    # POINT D'ENTRÉE PRINCIPAL
    # ──────────────────────────────────────────

    def analyze(self, df: pd.DataFrame, symbol: str, timeframe: str) -> VSAAnalysis:
        """
        Analyse complète VSA/Wyckoff sur un DataFrame OHLCV.
        df doit contenir : Open, High, Low, Close, Volume (index datetime)
        Retourne un objet VSAAnalysis complet.
        """
        if len(df) < self.SMA_PERIOD + 5:
            return self._empty_analysis(symbol, timeframe)

        df = df.copy()
        df = self._compute_indicators(df)

        # 1. Métriques barre par barre
        metrics_list = self._compute_bar_metrics(df)

        # 2. Signaux VSA sur les N dernières bougies
        signals = self._detect_signals(df, metrics_list)

        # 3. Phase et cycle Wyckoff
        wyckoff = self._detect_wyckoff_phase(df, metrics_list, signals)

        # 4. Zones de Supply/Demand
        demand_zones, supply_zones = self._detect_zones(df, signals)

        # 5. Balance offre/demande
        balance = self._compute_balance(signals)

        # 6. Absorption multi-barres
        absorption = self._detect_absorption(df, metrics_list)

        # 7. Multi-signal count (dernier signal confirmé plusieurs fois)
        multi_count = self._count_multi_signals(signals)

        # 8. Score brut algo
        last_signal = signals[-1] if signals else self._neutral_result(metrics_list[-1])
        raw_score = self._compute_raw_score(
            last_signal, wyckoff, multi_count,
            demand_zones, supply_zones, df, timeframe
        )

        return VSAAnalysis(
            symbol=symbol,
            timeframe=timeframe,
            last_bar_result=last_signal,
            wyckoff_state=wyckoff,
            recent_signals=signals[-10:],
            demand_zones=demand_zones[-5:],
            supply_zones=supply_zones[-5:],
            balance=balance,
            absorption_detected=absorption,
            multi_signal_count=multi_count,
            raw_score=raw_score,
        )

    # ──────────────────────────────────────────
    # INDICATEURS DE BASE
    # ──────────────────────────────────────────

    def _compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcule SMA volume, ATR, et métriques de base."""
        # Normalisation forcée des colonnes (yfinance lowercase fix)
        new_cols = []
        for c in df.columns:
            if c.lower() in ('open','high','low','close','volume'):
                new_cols.append(c.capitalize())
            else:
                new_cols.append(c)
        df.columns = new_cols

        # Fallback si Volume manque ou est à 0
        if 'Volume' not in df.columns:
            df['Volume'] = 1.0
        df['Volume'] = df['Volume'].replace(0, 1.0).fillna(1.0)

        df['sma_vol'] = df['Volume'].rolling(self.SMA_PERIOD).mean()
        df['vol_ratio'] = df['Volume'] / df['sma_vol']

        # ATR(14)
        high_low   = df['High'] - df['Low']
        high_close = (df['High'] - df['Close'].shift(1)).abs()
        low_close  = (df['Low']  - df['Close'].shift(1)).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = tr.rolling(self.ATR_PERIOD).mean()

        df['spread']    = df['High'] - df['Low']
        df['spread_ratio'] = df['spread'] / df['atr']
        df['close_pos'] = (df['Close'] - df['Low']) / (df['spread'].replace(0, np.nan))
        df['is_bullish'] = df['Close'] >= df['Open']

        # Mèches
        df['upper_wick'] = df['High'] - df[['Open','Close']].max(axis=1)
        df['lower_wick'] = df[['Open','Close']].min(axis=1) - df['Low']
        df['upper_wick_ratio'] = df['upper_wick'] / df['spread'].replace(0, np.nan)
        df['lower_wick_ratio'] = df['lower_wick'] / df['spread'].replace(0, np.nan)

        return df.fillna(0)

    # ──────────────────────────────────────────
    # MÉTRIQUES PAR BARRE
    # ──────────────────────────────────────────

    def _compute_bar_metrics(self, df: pd.DataFrame) -> list[BarMetrics]:
        metrics = []
        for i in range(len(df)):
            row = df.iloc[i]
            vr  = row['vol_ratio']
            sr  = row['spread_ratio']
            cp  = row['close_pos']

            metrics.append(BarMetrics(
                index           = i,
                volume_ratio    = vr,
                spread_ratio    = sr,
                close_pos       = cp,
                divergence_score= vr / sr if sr > 0 else 0,
                volume_level    = self._classify_volume(vr),
                spread_level    = self._classify_spread(sr),
                close_position  = self._classify_close(cp),
                upper_wick_ratio= row['upper_wick_ratio'],
                lower_wick_ratio= row['lower_wick_ratio'],
                is_bullish      = bool(row['is_bullish']),
                spread          = row['spread'],
                volume          = row['Volume'],
            ))
        return metrics

    def _classify_volume(self, vr: float) -> VolumeLevel:
        if vr < 0.8:   return VolumeLevel.LOW
        if vr < 1.5:   return VolumeLevel.AVERAGE
        if vr < 2.5:   return VolumeLevel.HIGH
        return VolumeLevel.ULTRA_HIGH

    def _classify_spread(self, sr: float) -> SpreadLevel:
        if sr < 0.4:   return SpreadLevel.ULTRA_NARROW
        if sr < 0.75:  return SpreadLevel.NARROW
        if sr < 1.5:   return SpreadLevel.AVERAGE
        if sr < 2.0:   return SpreadLevel.WIDE
        return SpreadLevel.ULTRA_WIDE

    def _classify_close(self, cp: float) -> ClosePosition:
        if cp <= 0.33: return ClosePosition.LOW
        if cp <= 0.67: return ClosePosition.MIDDLE
        return ClosePosition.HIGH

    # ──────────────────────────────────────────
    # DÉTECTION DES SIGNAUX VSA (barre courante)
    # ──────────────────────────────────────────

    def _detect_signals(self, df: pd.DataFrame, metrics: list[BarMetrics]) -> list[VSAResult]:
        """Détecte les signaux VSA sur toutes les bougies disponibles."""
        results = []
        n = len(metrics)
        for i in range(2, n):   # minimum 2 bougies précédentes
            m     = metrics[i]
            m_p1  = metrics[i-1]
            m_p2  = metrics[i-2]
            row   = df.iloc[i]
            row_p1= df.iloc[i-1]
            row_p2= df.iloc[i-2]

            result = self._classify_bar(m, m_p1, m_p2, row, row_p1, row_p2)
            results.append(result)
        return results

    def _classify_bar(self, m, m_p1, m_p2, row, row_p1, row_p2) -> VSAResult:
        """
        Classifie une barre selon les règles de l'encyclopédie VSA v3.0.
        Ordre de priorité : patterns 2-barres > signaux principaux > neutres.
        """

        # ── PATTERNS 2 BARRES (priorité haute) ──

        # Bottom Reversal (SOS) — Sec.3 §6
        if (not m_p1.is_bullish and
            m_p1.spread_level in (SpreadLevel.WIDE, SpreadLevel.ULTRA_WIDE) and
            m_p1.volume_level in (VolumeLevel.HIGH, VolumeLevel.ULTRA_HIGH) and
            m_p1.close_position == ClosePosition.LOW and
            m.is_bullish and
            m.spread_level in (SpreadLevel.WIDE, SpreadLevel.ULTRA_WIDE) and
            m.volume_level in (VolumeLevel.HIGH, VolumeLevel.ULTRA_HIGH) and
            m.close_position == ClosePosition.HIGH and
            row['Low'] <= row_p1['Low']):
            return VSAResult(VSASignal.BOTTOM_REVERSAL, "BULL", 0.90,
                             "Bottom Reversal : 2 barres, capitulation puis reprise immédiate",
                             True, False, m)

        # Top Reversal (SOW) — Sec.4 §6
        if (m_p1.is_bullish and
            m_p1.spread_level in (SpreadLevel.WIDE, SpreadLevel.ULTRA_WIDE) and
            m_p1.volume_level in (VolumeLevel.HIGH, VolumeLevel.ULTRA_HIGH) and
            m_p1.close_position == ClosePosition.HIGH and
            not m.is_bullish and
            m.spread_level in (SpreadLevel.WIDE, SpreadLevel.ULTRA_WIDE) and
            m.volume_level in (VolumeLevel.HIGH, VolumeLevel.ULTRA_HIGH) and
            m.close_position == ClosePosition.LOW and
            row['High'] >= row_p1['High']):
            return VSAResult(VSASignal.TOP_REVERSAL, "BEAR", 0.90,
                             "Top Reversal : euphorie puis distribution immédiate",
                             False, True, m)

        # Shake and Rally (SOS) — Sec.8 §7
        if (not m_p1.is_bullish and
            m_p1.spread_level in (SpreadLevel.WIDE, SpreadLevel.ULTRA_WIDE) and
            m_p1.volume_level == VolumeLevel.ULTRA_HIGH and
            m_p1.close_position in (ClosePosition.LOW, ClosePosition.MIDDLE) and
            m.is_bullish and
            m.spread_level in (SpreadLevel.WIDE, SpreadLevel.ULTRA_WIDE) and
            m.volume_level in (VolumeLevel.HIGH, VolumeLevel.ULTRA_HIGH) and
            m.close_position == ClosePosition.HIGH):
            return VSAResult(VSASignal.SHAKE_AND_RALLY, "BULL", 0.95,
                             "Shake and Rally : purge puis reprise explosive",
                             True, False, m)

        # Bag Holding Haussier (SOS) — Sec.8 §5
        if (not m_p1.is_bullish and
            m_p1.spread_level in (SpreadLevel.WIDE, SpreadLevel.ULTRA_WIDE) and
            m_p1.volume_level in (VolumeLevel.HIGH, VolumeLevel.ULTRA_HIGH) and
            m_p1.close_position == ClosePosition.LOW and
            m.close_position == ClosePosition.HIGH and
            row['Close'] > row_p1['High']):
            return VSAResult(VSASignal.BAG_HOLDING_BULL, "BULL", 0.88,
                             "Bag Holding Bull : vendeurs piégés, short squeeze",
                             True, False, m)

        # Bag Holding Baissier (SOW) — Sec.8 §5
        if (m_p1.is_bullish and
            m_p1.spread_level in (SpreadLevel.WIDE, SpreadLevel.ULTRA_WIDE) and
            m_p1.volume_level in (VolumeLevel.HIGH, VolumeLevel.ULTRA_HIGH) and
            m_p1.close_position == ClosePosition.HIGH and
            m.close_position == ClosePosition.LOW and
            row['Close'] < row_p1['Low']):
            return VSAResult(VSASignal.BAG_HOLDING_BEAR, "BEAR", 0.88,
                             "Bag Holding Bear : acheteurs piégés, long squeeze",
                             False, True, m)

        # ── SIGNAUX PRINCIPAUX HAUSSIERS (SOS) ──

        # Selling Climax — Sec.3 §4
        if (not m.is_bullish and
            m.spread_level in (SpreadLevel.WIDE, SpreadLevel.ULTRA_WIDE) and
            m.volume_level == VolumeLevel.ULTRA_HIGH and
            m.close_position in (ClosePosition.MIDDLE, ClosePosition.HIGH)):
            return VSAResult(VSASignal.SELLING_CLIMAX, "BULL", 0.92,
                             "Selling Climax : capitulation finale, absorption institutionnelle",
                             True, False, m)

        # Stopping Volume — Sec.3 §3
        if (not m.is_bullish and
            m.spread_level in (SpreadLevel.WIDE, SpreadLevel.ULTRA_WIDE) and
            m.volume_level in (VolumeLevel.HIGH, VolumeLevel.ULTRA_HIGH) and
            m.close_position in (ClosePosition.MIDDLE, ClosePosition.HIGH)):
            return VSAResult(VSASignal.STOPPING_VOLUME, "BULL", 0.80,
                             "Stopping Volume : freinage institutionnel de la baisse",
                             True, False, m)

        # Shakeout — Sec.8 §6
        if (not m.is_bullish and
            m.spread_level in (SpreadLevel.WIDE, SpreadLevel.ULTRA_WIDE) and
            m.volume_level == VolumeLevel.ULTRA_HIGH and
            row['Low'] < row_p1['Low'] and
            m.close_position in (ClosePosition.LOW, ClosePosition.MIDDLE)):
            return VSAResult(VSASignal.SHAKEOUT, "BULL", 0.85,
                             "Shakeout : purge agressive des stops, continuation haussière probable",
                             True, False, m)

        # No Supply — Sec.3 §1
        if (not m.is_bullish and
            m.spread_level in (SpreadLevel.ULTRA_NARROW, SpreadLevel.NARROW) and
            m.volume_level == VolumeLevel.LOW and
            m.close_position in (ClosePosition.MIDDLE, ClosePosition.HIGH)):
            return VSAResult(VSASignal.NO_SUPPLY, "BULL", 0.75,
                             "No Supply : absence de vendeurs, marché libre de monter",
                             True, False, m)

        # Test / Successful Test — Sec.3 §2
        if (row['Low'] < row_p1['Low'] and
            m.close_position == ClosePosition.HIGH and
            m.lower_wick_ratio > 0.40 and
            m.volume_level == VolumeLevel.LOW):
            return VSAResult(VSASignal.TEST_SUCCESS, "BULL", 0.82,
                             "Test réussi : cassure support + clôture haute + faible volume",
                             True, False, m)

        # Reverse Upthrust — Sec.8 §2
        if (row['Low'] < row_p1['Low'] and
            m.close_position == ClosePosition.HIGH and
            m.volume_level == VolumeLevel.LOW and
            m.lower_wick_ratio > 0.40):
            return VSAResult(VSASignal.REVERSE_UPTHRUST, "BULL", 0.72,
                             "Reverse Upthrust : percée support + clôture haute + volume faible",
                             True, False, m)

        # Push Through Supply — Sec.3 §5
        if (m.is_bullish and
            row['High'] > row_p1['High'] and
            m.spread_level in (SpreadLevel.WIDE, SpreadLevel.ULTRA_WIDE) and
            m.volume_level in (VolumeLevel.HIGH, VolumeLevel.ULTRA_HIGH) and
            m.close_position == ClosePosition.HIGH):
            return VSAResult(VSASignal.PUSH_THROUGH_SUPPLY, "BULL", 0.85,
                             "Push Through Supply : cassure résistance avec force institutionnelle",
                             True, False, m)

        # Squat Haussier — Sec.8 §3 (en bas de range → haussier)
        if (m.spread_level in (SpreadLevel.ULTRA_NARROW, SpreadLevel.NARROW) and
            m.volume_level in (VolumeLevel.HIGH, VolumeLevel.ULTRA_HIGH) and
            not m.is_bullish):
            return VSAResult(VSASignal.SQUAT_BULLISH, "BULL", 0.70,
                             "Squat : volume élevé sur spread étroit — absorption de l'offre finale",
                             True, False, m)

        # ── SIGNAUX PRINCIPAUX BAISSIERS (SOW) ──

        # Buying Climax — Sec.4 §4
        if (m.is_bullish and
            m.spread_level in (SpreadLevel.WIDE, SpreadLevel.ULTRA_WIDE) and
            m.volume_level == VolumeLevel.ULTRA_HIGH and
            m.close_position in (ClosePosition.LOW, ClosePosition.MIDDLE)):
            return VSAResult(VSASignal.BUYING_CLIMAX, "BEAR", 0.92,
                             "Buying Climax : euphorie retail, distribution institutionnelle",
                             False, True, m)

        # Upthrust — Sec.4 §2
        if (row['High'] > row_p1['High'] and
            m.close_position == ClosePosition.LOW and
            m.upper_wick_ratio > 0.40 and
            m.volume_level in (VolumeLevel.HIGH, VolumeLevel.ULTRA_HIGH)):
            return VSAResult(VSASignal.UPTHRUST, "BEAR", 0.88,
                             "Upthrust : cassure résistance + clôture basse + volume fort",
                             False, True, m)

        # Hidden Upthrust — Sec.4 §3
        if (not m.is_bullish and
            row['High'] > row_p1['High'] and
            m.close_position == ClosePosition.LOW and
            m.volume_level in (VolumeLevel.HIGH, VolumeLevel.ULTRA_HIGH)):
            return VSAResult(VSASignal.HIDDEN_UPTHRUST, "BEAR", 0.80,
                             "Hidden Upthrust : nouveau high puis clôture basse, volume fort",
                             False, True, m)

        # Pseudo Upthrust — Sec.8 §1
        if (row['High'] > row_p1['High'] and
            m.close_position == ClosePosition.LOW and
            m.upper_wick_ratio > 0.40 and
            m.volume_level not in (VolumeLevel.HIGH, VolumeLevel.ULTRA_HIGH)):
            return VSAResult(VSASignal.PSEUDO_UPTHRUST, "BEAR", 0.65,
                             "Pseudo Upthrust : faiblesse masquée, absence d'acheteurs",
                             False, True, m)

        # End of Rising Market — Sec.4 §5
        if (m.is_bullish and
            m.spread_level in (SpreadLevel.ULTRA_NARROW, SpreadLevel.NARROW) and
            m.volume_level == VolumeLevel.ULTRA_HIGH):
            return VSAResult(VSASignal.END_RISING_MARKET, "BEAR", 0.85,
                             "End of Rising Market : mur de vendeurs, effort sans résultat",
                             False, True, m)

        # No Demand — Sec.4 §1
        if (m.is_bullish and
            m.spread_level in (SpreadLevel.ULTRA_NARROW, SpreadLevel.NARROW) and
            m.volume_level == VolumeLevel.LOW and
            m.close_position in (ClosePosition.LOW, ClosePosition.MIDDLE)):
            return VSAResult(VSASignal.NO_DEMAND, "BEAR", 0.75,
                             "No Demand : absence d'acheteurs, hausse va s'effondrer",
                             False, True, m)

        # Inverse Squat — Sec.8 §4
        if (m.spread_level in (SpreadLevel.WIDE, SpreadLevel.ULTRA_WIDE) and
            m.volume_level == VolumeLevel.LOW):
            direction = "BEAR" if m.is_bullish else "BULL"
            return VSAResult(VSASignal.INVERSE_SQUAT, direction, 0.60,
                             "Inverse Squat : mouvement non soutenu, retournement probable",
                             not m.is_bullish, m.is_bullish, m)

        # Squat Baissier — (en haut de range → baissier)
        if (m.spread_level in (SpreadLevel.ULTRA_NARROW, SpreadLevel.NARROW) and
            m.volume_level in (VolumeLevel.HIGH, VolumeLevel.ULTRA_HIGH) and
            m.is_bullish):
            return VSAResult(VSASignal.SQUAT_BEARISH, "BEAR", 0.70,
                             "Squat : volume élevé sur spread étroit — absorption de la demande finale",
                             False, True, m)

        # NEUTRAL
        return self._neutral_result(m)

    def _neutral_result(self, m: BarMetrics) -> VSAResult:
        return VSAResult(VSASignal.NEUTRAL, "NEUTRAL", 0.0,
                         "Activité normale, pas de signal VSA", False, False, m)

    # ──────────────────────────────────────────
    # DÉTECTION PHASE WYCKOFF
    # ──────────────────────────────────────────

    def _detect_wyckoff_phase(self, df, metrics, signals) -> WyckoffState:
        """
        Détecte la phase Wyckoff courante en analysant les 50 dernières bougies.
        Suit les transitions cycle selon l'encyclopédie Section 9.4.
        """
        state = WyckoffState(
            cycle=WyckoffCycle.UNDEFINED,
            phase=WyckoffPhase.UNDEFINED,
            sc_level=None, bc_level=None,
            ar_level=None, creek_level=None, ice_level=None,
        )

        if len(signals) < 5:
            return state

        recent = signals[-50:] if len(signals) >= 50 else signals
        recent_df = df.iloc[-len(recent):]

        # Chercher SC ou BC récent (les 2 derniers)
        sc_idx = bc_idx = None
        for i, s in enumerate(recent):
            if s.signal == VSASignal.SELLING_CLIMAX:
                sc_idx = i
                state.sc_level = recent_df.iloc[i]['Low']
            elif s.signal == VSASignal.BUYING_CLIMAX:
                bc_idx = i
                state.bc_level = recent_df.iloc[i]['High']

        # Accumuler scores offre/demande pondérés volume
        for s in recent:
            w = s.metrics.volume_ratio
            if s.is_sos:
                state.demand_score += w
            elif s.is_sow:
                state.supply_score += w

        # Détecter Spring (Sec. 19.1)
        for i, s in enumerate(recent):
            if s.signal in (VSASignal.SHAKEOUT, VSASignal.SELLING_CLIMAX):
                if i + 3 < len(recent):
                    recovery = recent[i+1:i+4]
                    if any(r.is_sos for r in recovery):
                        state.spring_detected = True

        # Détecter UTAD (Sec. 19.3)
        for i, s in enumerate(recent):
            if s.signal == VSASignal.UPTHRUST and bc_idx is not None and i > bc_idx:
                state.utad_detected = True

        # Déterminer le cycle
        last_price = df.iloc[-1]['Close']

        if sc_idx is not None and bc_idx is None:
            # SC détecté sans BC → contexte d'Accumulation
            if state.spring_detected:
                state.cycle = WyckoffCycle.ACCUMULATION
                state.phase = WyckoffPhase.ACCUMULATION_C
            elif state.demand_score > state.supply_score * 1.5:
                state.cycle = WyckoffCycle.ACCUMULATION
                state.phase = WyckoffPhase.ACCUMULATION_D
            else:
                state.cycle = WyckoffCycle.ACCUMULATION
                state.phase = WyckoffPhase.ACCUMULATION_B

        elif bc_idx is not None and sc_idx is None:
            # BC détecté sans SC → contexte de Distribution
            if state.utad_detected:
                state.cycle = WyckoffCycle.DISTRIBUTION
                state.phase = WyckoffPhase.DISTRIBUTION_C
            elif state.supply_score > state.demand_score * 1.5:
                state.cycle = WyckoffCycle.DISTRIBUTION
                state.phase = WyckoffPhase.DISTRIBUTION_D
            else:
                state.cycle = WyckoffCycle.DISTRIBUTION
                state.phase = WyckoffPhase.DISTRIBUTION_B

        elif state.demand_score > state.supply_score * 2.0:
            state.cycle = WyckoffCycle.MARKUP
            state.phase = WyckoffPhase.MARKUP

        elif state.supply_score > state.demand_score * 2.0:
            state.cycle = WyckoffCycle.MARKDOWN
            state.phase = WyckoffPhase.MARKDOWN

        else:
            state.cycle = WyckoffCycle.UNDEFINED
            state.phase = WyckoffPhase.UNDEFINED

        return state

    # ──────────────────────────────────────────
    # ZONES SUPPLY / DEMAND
    # ──────────────────────────────────────────

    def _detect_zones(self, df, signals):
        """Détecte les zones de Supply et Demand actives (Sec. 13)."""
        demand_zones = []
        supply_zones = []

        for i, s in enumerate(signals):
            row = df.iloc[i + 2]  # offset de 2 (on démarre à i=2 dans detect_signals)
            if s.is_sos and s.signal in (VSASignal.SELLING_CLIMAX, VSASignal.STOPPING_VOLUME,
                                          VSASignal.SHAKEOUT, VSASignal.BOTTOM_REVERSAL):
                demand_zones.append({
                    'low': row['Low'], 'high': row['High'],
                    'signal': s.signal.value, 'strength': s.strength
                })
            elif s.is_sow and s.signal in (VSASignal.BUYING_CLIMAX, VSASignal.UPTHRUST,
                                            VSASignal.END_RISING_MARKET, VSASignal.TOP_REVERSAL):
                supply_zones.append({
                    'low': row['Low'], 'high': row['High'],
                    'signal': s.signal.value, 'strength': s.strength
                })

        return demand_zones, supply_zones

    # ──────────────────────────────────────────
    # BALANCE OFFRE/DEMANDE
    # ──────────────────────────────────────────

    def _compute_balance(self, signals) -> float:
        """Balance = Demand_Score - Supply_Score (Sec.13.4)."""
        demand = sum(s.metrics.volume_ratio for s in signals[-20:] if s.is_sos)
        supply = sum(s.metrics.volume_ratio for s in signals[-20:] if s.is_sow)
        return round(demand - supply, 2)

    # ──────────────────────────────────────────
    # ABSORPTION MULTI-BARRES
    # ──────────────────────────────────────────

    def _detect_absorption(self, df, metrics) -> bool:
        """
        Détecte une absorption multi-barres (2–5 bougies) — Sec.8 §8.
        Condition : volume cumulé élevé + progression prix quasi nulle.
        """
        if len(metrics) < 5:
            return False

        for n in range(2, 6):
            window_m  = metrics[-n:]
            window_df = df.iloc[-n:]
            cum_vol   = sum(m.volume_ratio for m in window_m)
            price_move = abs(window_df.iloc[-1]['Close'] - window_df.iloc[0]['Open'])
            atr_val    = df.iloc[-1]['atr']

            if (cum_vol > n * 1.5 and
                atr_val > 0 and
                price_move < atr_val * 0.5):
                return True
        return False

    # ──────────────────────────────────────────
    # MULTI-SIGNAL COUNT
    # ──────────────────────────────────────────

    def _count_multi_signals(self, signals) -> int:
        """Compte combien de signaux dans la même direction sur les 5 dernières barres (Sec.17)."""
        if len(signals) < 2:
            return 0
        recent = signals[-5:]
        bull = sum(1 for s in recent if s.is_sos)
        bear = sum(1 for s in recent if s.is_sow)
        return max(bull, bear)

    # ──────────────────────────────────────────
    # SCORE BRUT ALGORITHMIQUE
    # ──────────────────────────────────────────

    def _compute_raw_score(self, signal: VSAResult, wyckoff: WyckoffState,
                           multi_count: int, demand_zones, supply_zones,
                           df, timeframe) -> float:
        """
        Calcule le score brut sur 50 points (partie algo).
        L'autre 50 pts viennent de Gemini Vision (scorer.py).
        Basé sur Sec.17 + Sec.25 de l'encyclopédie.
        """
        score = 0.0

        # 1. Score base signal (max 15 pts)
        if signal.signal != VSASignal.NEUTRAL:
            score += signal.strength * 15

        # 2. Contexte Wyckoff (max 10 pts)
        phase_bonus = self._get_phase_bonus(signal, wyckoff)
        score += phase_bonus

        # 3. Confluence zones (max 10 pts)
        last_close = df.iloc[-1]['Close']
        for zone in demand_zones[-3:]:
            if zone['low'] <= last_close <= zone['high'] * 1.005:
                score += 4
                break
        for zone in supply_zones[-3:]:
            if zone['low'] * 0.995 <= last_close <= zone['high']:
                score += 4
                break

        # 4. Multi-signal (max 8 pts)
        if multi_count >= 3:
            score += 8
        elif multi_count == 2:
            score += 4

        # 5. Timing session (max 4 pts)
        score += self._get_timing_bonus(df)

        # 6. Effort vs Résultat (max 3 pts)
        div = signal.metrics.divergence_score
        if div > 3.0:
            score += 3
        elif div > 2.0:
            score += 2

        # 7. Pénalités
        if wyckoff.cycle == WyckoffCycle.UNDEFINED:
            score -= 3
        if signal.signal == VSASignal.NEUTRAL:
            score -= 5

        return max(0.0, min(50.0, round(score, 1)))

    def _get_phase_bonus(self, signal: VSAResult, wyckoff: WyckoffState) -> float:
        """
        Bonus/malus selon la matrice Contexte × Signal (Sec.15.1).
        """
        s = signal.signal
        phase = wyckoff.phase

        # Signaux haussiers dans phases haussières
        if signal.is_sos:
            if phase in (WyckoffPhase.ACCUMULATION_C, WyckoffPhase.ACCUMULATION_D):
                return 10.0 if s in (VSASignal.SHAKEOUT, VSASignal.TEST_SUCCESS,
                                     VSASignal.SHAKE_AND_RALLY, VSASignal.NO_SUPPLY) else 7.0
            if phase == WyckoffPhase.MARKUP:
                return 8.0
            if phase == WyckoffPhase.ACCUMULATION_B:
                return 5.0
            if phase in (WyckoffPhase.DISTRIBUTION_C, WyckoffPhase.DISTRIBUTION_D,
                         WyckoffPhase.MARKDOWN):
                return -5.0  # signal contre la tendance

        # Signaux baissiers dans phases baissières
        if signal.is_sow:
            if phase in (WyckoffPhase.DISTRIBUTION_C, WyckoffPhase.DISTRIBUTION_D):
                return 10.0 if s in (VSASignal.UPTHRUST, VSASignal.BUYING_CLIMAX,
                                     VSASignal.END_RISING_MARKET) else 7.0
            if phase == WyckoffPhase.MARKDOWN:
                return 8.0
            if phase == WyckoffPhase.DISTRIBUTION_B:
                return 5.0
            if phase in (WyckoffPhase.ACCUMULATION_C, WyckoffPhase.ACCUMULATION_D,
                         WyckoffPhase.MARKUP):
                return -5.0

        return 0.0

    def _get_timing_bonus(self, df) -> float:
        """Bonus de timing session (Sec.16.5)."""
        try:
            last_ts = df.index[-1]
            if hasattr(last_ts, 'hour'):
                h = last_ts.hour
                # London Open 03–06 UTC / NY Open 13–16 UTC
                if 3 <= h <= 6 or 13 <= h <= 16:
                    return 2.0
                # Macros algorithmiques ICT
                if h in (8, 10):
                    return 1.0
        except Exception:
            pass
        return 0.0

    # ──────────────────────────────────────────
    # HELPER — analyse vide
    # ──────────────────────────────────────────

    def _empty_analysis(self, symbol, timeframe) -> VSAAnalysis:
        empty_metrics = BarMetrics(0, 0, 0, 0.5, 0,
                                   VolumeLevel.AVERAGE, SpreadLevel.AVERAGE,
                                   ClosePosition.MIDDLE, 0, 0, True, 0, 0)
        empty_result  = self._neutral_result(empty_metrics)
        empty_state   = WyckoffState(WyckoffCycle.UNDEFINED, WyckoffPhase.UNDEFINED,
                                     None, None, None, None, None)
        return VSAAnalysis(symbol, timeframe, empty_result, empty_state)
