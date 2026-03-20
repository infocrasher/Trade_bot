"""
META-CONVERGENCE ENGINE — Multi-Profile Trading Architecture
=============================================================
Résout 4 problèmes architecturaux :
  1. Scoring pondéré dynamique (remplacement du vote ≥3)
  2. Risk Governor portfolio (exposition agrégée multi-instruments)
  3. Détection crowding vs convergence authentique
  4. Meta-Learner léger (RandomForest post paper-trading)

Auteur : Architecture proposée pour système de trading algorithmique
Dépendances : numpy, scipy, sklearn (toutes CPU-only)
"""

import json
import time
import math
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple
from enum import Enum

import numpy as np
from scipy import stats


# =============================================================================
# PROBLÈME 1 — SCORING PONDÉRÉ DYNAMIQUE
# =============================================================================
# 
# Formule de convergence :
#
#   S_meta = Σᵢ [ wᵢ · dᵢ · αᵢ(t) · ρᵢ ]
#
# Où pour chaque profil i :
#   wᵢ     = poids de performance = sharpe_glissant_i / Σⱼ sharpe_glissant_j  (normalisé)
#   dᵢ     = direction du signal (+1 long, -1 short, 0 neutre)
#   αᵢ(t)  = facteur de fraîcheur = max(0, 1 - (t_now - t_signal) / TTL_i)²
#             → décroissance quadratique, pas linéaire : un signal vieux de 80% de sa TTL
#               ne vaut que 4% de son poids initial
#   ρᵢ     = facteur d'indépendance = 1 - mean(|corr(signaux_i, signaux_j)|) pour j ≠ i
#             → un profil qui dit la même chose que tous les autres est downweighted
#
# Score final normalisé entre -1 (short unanime) et +1 (long unanime)
# Seuil d'activation : |S_meta| > θ (configurable, default 0.45)
#


class Direction(Enum):
    LONG = 1
    SHORT = -1
    NEUTRAL = 0


@dataclass
class ProfileSignal:
    """Signal émis par un profil d'analyse."""
    profile_id: str           # "ict", "elliott", "vsa", "pure_pa", "custom"
    direction: Direction
    confidence: float         # 0.0 à 1.0 — confiance interne du profil
    timestamp: float          # time.time() de l'émission
    ttl_seconds: float        # durée de validité en secondes
    instrument: str           # "EURUSD", "XAUUSD", etc.
    metadata: dict = field(default_factory=dict)


@dataclass 
class ProfileStats:
    """Statistiques glissantes d'un profil."""
    profile_id: str
    sharpe_rolling: float = 0.0       # Sharpe sur fenêtre glissante (ex: 30 derniers trades)
    win_rate: float = 0.5
    total_signals: int = 0
    signal_history: List[int] = field(default_factory=list)  # +1/-1 pour corrélation


class DynamicScorer:
    """
    Problème 1 : Calcule le score de méta-convergence pondéré.
    
    Remplace le vote binaire ≥3 par un score continu [-1, +1]
    qui intègre performance, fraîcheur, et indépendance.
    """

    def __init__(
        self,
        activation_threshold: float = 0.45,
        correlation_window: int = 50,     # Nombre de signaux pour calculer la corrélation
        min_sharpe_weight: float = 0.05,  # Poids minimum même si Sharpe = 0
    ):
        self.activation_threshold = activation_threshold
        self.correlation_window = correlation_window
        self.min_sharpe_weight = min_sharpe_weight
        self.stats: Dict[str, ProfileStats] = {}

    def _freshness_factor(self, signal: ProfileSignal) -> float:
        """
        Décroissance quadratique de la fraîcheur.
        
        α(t) = max(0, 1 - elapsed/TTL)²
        
        Pourquoi quadratique et pas linéaire ?
        → Un signal à 50% de sa TTL garde 25% de poids (pas 50%)
        → Force la convergence à se produire sur des signaux FRAIS
        → Évite les faux alignements sur des signaux moribonds
        """
        elapsed = time.time() - signal.timestamp
        ratio = elapsed / signal.ttl_seconds
        if ratio >= 1.0:
            return 0.0
        return (1.0 - ratio) ** 2

    def _compute_independence_factors(self) -> Dict[str, float]:
        """
        Calcule ρᵢ = 1 - mean(|corr(i, j)|) pour chaque profil.
        
        Utilise l'historique des directions de signal (+1/-1).
        Un profil qui corrèle fortement avec les autres est downweighted
        car il n'apporte pas d'information indépendante.
        """
        profile_ids = list(self.stats.keys())
        n = len(profile_ids)
        
        if n < 2:
            return {pid: 1.0 for pid in profile_ids}
        
        # Construire la matrice de signaux alignés (padding à 0 si longueurs différentes)
        max_len = min(
            self.correlation_window,
            max(len(self.stats[pid].signal_history) for pid in profile_ids)
        )
        
        if max_len < 10:  # Pas assez de données → tout le monde à 1.0
            return {pid: 1.0 for pid in profile_ids}
        
        signals_matrix = np.zeros((n, max_len))
        for i, pid in enumerate(profile_ids):
            hist = self.stats[pid].signal_history[-max_len:]
            signals_matrix[i, -len(hist):] = hist
        
        # Matrice de corrélation
        corr_matrix = np.corrcoef(signals_matrix)
        
        independence = {}
        for i, pid in enumerate(profile_ids):
            # Moyenne des |corrélations| avec les AUTRES profils
            abs_corrs = [abs(corr_matrix[i, j]) for j in range(n) if j != i]
            mean_abs_corr = np.mean(abs_corrs) if abs_corrs else 0.0
            # ρ = 1 quand totalement indépendant, ~0 quand corrélé à tout
            independence[pid] = max(0.1, 1.0 - mean_abs_corr)  # floor à 0.1
        
        return independence

    def _compute_performance_weights(self) -> Dict[str, float]:
        """
        Poids basé sur le Sharpe ratio glissant, normalisé.
        
        wᵢ = max(sharpe_i, min_weight) / Σⱼ max(sharpe_j, min_weight)
        """
        raw = {}
        for pid, st in self.stats.items():
            raw[pid] = max(st.sharpe_rolling, self.min_sharpe_weight)
        
        total = sum(raw.values())
        if total == 0:
            n = len(raw)
            return {pid: 1.0 / n for pid in raw}
        
        return {pid: v / total for pid, v in raw.items()}

    def compute_meta_score(
        self, signals: List[ProfileSignal], sqn_multipliers: Dict[str, float] = None
    ) -> Tuple[float, Dict[str, dict]]:
        """
        Calcule le score de méta-convergence.
        
        Returns:
            (score_meta, details) où score_meta ∈ [-1, +1]
            et details contient la décomposition par profil.
        """
        if not signals:
            return 0.0, {}
        
        # Filtrer les signaux expirés
        active_signals = [s for s in signals if self._freshness_factor(s) > 0]
        if not active_signals:
            return 0.0, {}
        
        perf_weights = self._compute_performance_weights()
        indep_factors = self._compute_independence_factors()
        
        weighted_sum = 0.0
        weight_total = 0.0
        details = {}
        
        for sig in active_signals:
            pid = sig.profile_id
            w = perf_weights.get(pid, self.min_sharpe_weight)
            if sqn_multipliers:
                w *= sqn_multipliers.get(pid, 1.0)
            alpha = self._freshness_factor(sig)
            rho = indep_factors.get(pid, 1.0)
            d = sig.direction.value
            
            # Contribution de ce profil
            contribution = w * d * alpha * rho * sig.confidence
            weighted_sum += contribution
            weight_total += w * alpha * rho * sig.confidence
            
            details[pid] = {
                "direction": sig.direction.name,
                "perf_weight": round(w, 4),
                "freshness": round(alpha, 4),
                "independence": round(rho, 4),
                "confidence": round(sig.confidence, 4),
                "contribution": round(contribution, 4),
            }
        
        # Normaliser par les poids totaux pour rester dans [-1, +1]
        if weight_total > 0:
            score = weighted_sum / weight_total
        else:
            score = 0.0
        
        return round(score, 4), details

    def should_activate(self, signals: List[ProfileSignal], sqn_multipliers: Dict[str, float] = None) -> Tuple[bool, float, dict]:
        """Point d'entrée principal : faut-il trader ?"""
        score, details = self.compute_meta_score(signals, sqn_multipliers)
        activated = abs(score) >= self.activation_threshold
        return activated, score, details

    def update_profile_stats(
        self, profile_id: str, direction: int, trade_pnl: float,
        rolling_returns: List[float]
    ):
        """Met à jour les stats après un trade résolu."""
        if profile_id not in self.stats:
            self.stats[profile_id] = ProfileStats(profile_id=profile_id)
        
        st = self.stats[profile_id]
        st.signal_history.append(direction)
        st.total_signals += 1
        
        # Sharpe glissant
        if len(rolling_returns) >= 10:
            arr = np.array(rolling_returns[-30:])  # Fenêtre 30 trades
            mean_r = np.mean(arr)
            std_r = np.std(arr, ddof=1)
            st.sharpe_rolling = (mean_r / std_r * np.sqrt(252)) if std_r > 0 else 0.0
        
        # Win rate glissant
        wins = sum(1 for r in rolling_returns[-30:] if r > 0)
        st.win_rate = wins / len(rolling_returns[-30:]) if rolling_returns else 0.5


# =============================================================================
# PROBLÈME 2 — RISK GOVERNOR PORTFOLIO
# =============================================================================
#
# Architecture : fichier JSON unique comme "state store"
# Métriques :
#   1. Exposition directionnelle nette par devise (decomposition des paires)
#   2. VaR paramétrique portfolio (variance-covariance)
#   3. Corrélation implicite et limite de concentration
#
# Pas de DB relationnelle → tout en JSON + numpy
#


# Matrice de corrélation pré-calculée (à actualiser périodiquement via API)
# Valeurs approximatives typiques — en production, calculer sur données récentes
DEFAULT_CORRELATION_MATRIX = {
    ("EURUSD", "GBPUSD"): 0.85,
    ("EURUSD", "USDJPY"): -0.30,
    ("EURUSD", "USDCAD"): -0.75,
    ("EURUSD", "XAUUSD"): 0.40,
    ("EURUSD", "XAGUSD"): 0.35,
    ("EURUSD", "UKOIL"):  0.25,
    ("GBPUSD", "USDJPY"): -0.25,
    ("GBPUSD", "USDCAD"): -0.65,
    ("GBPUSD", "XAUUSD"): 0.35,
    ("GBPUSD", "XAGUSD"): 0.30,
    ("GBPUSD", "UKOIL"):  0.20,
    ("USDJPY", "USDCAD"):  0.40,
    ("USDJPY", "XAUUSD"): -0.50,
    ("USDJPY", "XAGUSD"): -0.45,
    ("USDJPY", "UKOIL"):  -0.10,
    ("USDCAD", "XAUUSD"): -0.35,
    ("USDCAD", "XAGUSD"): -0.30,
    ("USDCAD", "UKOIL"):  -0.55,
    ("XAUUSD", "XAGUSD"):  0.92,
    ("XAUUSD", "UKOIL"):   0.30,
    ("XAGUSD", "UKOIL"):   0.25,
}

# Volatilité journalière approximative (en %) pour VaR paramétrique
DEFAULT_DAILY_VOL = {
    "EURUSD": 0.55, "GBPUSD": 0.65, "USDJPY": 0.60,
    "USDCAD": 0.50, "XAUUSD": 1.20, "XAGUSD": 2.00, "UKOIL": 2.50,
}


@dataclass
class OpenPosition:
    instrument: str
    direction: int        # +1 long, -1 short
    size_usd: float       # Taille en USD notionnel
    profile_id: str
    entry_time: float
    entry_price: float


class RiskGovernor:
    """
    Problème 2 : Gestion du risque portfolio en temps réel.
    
    Tout le state est sérialisable en JSON.
    Aucune base de données requise.
    """

    def __init__(
        self,
        max_portfolio_var_pct: float = 2.0,    # VaR max en % du capital
        max_single_instrument_pct: float = 30,  # Max % exposition sur 1 instrument
        max_correlated_group_pct: float = 50,   # Max % pour un groupe corrélé (corr > 0.7)
        max_net_directional_pct: float = 60,    # Max % exposition directionnelle nette
        capital_usd: float = 10000,
        state_path: str = "risk_state.json",
    ):
        self.max_portfolio_var_pct = max_portfolio_var_pct
        self.max_single_instrument_pct = max_single_instrument_pct
        self.max_correlated_group_pct = max_correlated_group_pct
        self.max_net_directional_pct = max_net_directional_pct
        self.capital = capital_usd
        self.state_path = Path(state_path)
        self.positions: List[OpenPosition] = []
        self.correlations = DEFAULT_CORRELATION_MATRIX
        self.daily_vol = DEFAULT_DAILY_VOL
        self._load_state()

    def _load_state(self):
        if self.state_path.exists():
            data = json.loads(self.state_path.read_text())
            self.positions = [OpenPosition(**p) for p in data.get("positions", [])]
            self.capital = data.get("capital", self.capital)

    def _save_state(self):
        data = {
            "positions": [asdict(p) for p in self.positions],
            "capital": self.capital,
            "updated_at": datetime.now().isoformat(),
        }
        self.state_path.write_text(json.dumps(data, indent=2))

    def _get_correlation(self, inst_a: str, inst_b: str) -> float:
        if inst_a == inst_b:
            return 1.0
        key = tuple(sorted([inst_a, inst_b]))
        return self.correlations.get(key, 0.0)

    def compute_portfolio_var(self, confidence: float = 0.95) -> float:
        """
        VaR paramétrique (variance-covariance) du portfolio.
        
        VaR = Z_α * √(w' · Σ · w) * capital
        
        Où w = vecteur des expositions signées normalisées
            Σ = matrice de variance-covariance
        """
        if not self.positions:
            return 0.0
        
        instruments = list(set(p.instrument for p in self.positions))
        n = len(instruments)
        inst_idx = {inst: i for i, inst in enumerate(instruments)}
        
        # Vecteur d'exposition signée (direction * taille) normalisé par capital
        w = np.zeros(n)
        for pos in self.positions:
            i = inst_idx[pos.instrument]
            w[i] += pos.direction * pos.size_usd / self.capital
        
        # Matrice de variance-covariance (daily)
        cov = np.zeros((n, n))
        for i, inst_i in enumerate(instruments):
            for j, inst_j in enumerate(instruments):
                vol_i = self.daily_vol.get(inst_i, 1.0) / 100
                vol_j = self.daily_vol.get(inst_j, 1.0) / 100
                corr = self._get_correlation(inst_i, inst_j)
                cov[i, j] = vol_i * vol_j * corr
        
        # VaR
        portfolio_variance = w @ cov @ w
        portfolio_std = math.sqrt(max(0, portfolio_variance))
        z_score = stats.norm.ppf(confidence)  # 1.645 pour 95%
        var_pct = z_score * portfolio_std * 100
        
        return round(var_pct, 4)

    def compute_net_directional_exposure(self) -> Dict[str, float]:
        """
        Décompose l'exposition par devise sous-jacente.
        
        EURUSD long → long EUR, short USD
        XAUUSD long → long XAU, short USD
        """
        currency_exposure = {}
        
        decomposition = {
            "EURUSD": ("EUR", "USD"), "GBPUSD": ("GBP", "USD"),
            "USDJPY": ("USD", "JPY"), "USDCAD": ("USD", "CAD"),
            "XAUUSD": ("XAU", "USD"), "XAGUSD": ("XAG", "USD"),
            "UKOIL":  ("OIL", "USD"),
        }
        
        for pos in self.positions:
            base, quote = decomposition.get(pos.instrument, ("UNK", "UNK"))
            signed_size = pos.direction * pos.size_usd
            currency_exposure[base] = currency_exposure.get(base, 0) + signed_size
            currency_exposure[quote] = currency_exposure.get(quote, 0) - signed_size
        
        # Normaliser en % du capital
        return {
            ccy: round(exp / self.capital * 100, 2)
            for ccy, exp in currency_exposure.items()
        }

    def check_new_trade(
        self, instrument: str, direction: int, size_usd: float
    ) -> Tuple[bool, List[str]]:
        """
        Vérifie si un nouveau trade respecte toutes les limites.
        
        Returns:
            (autorisé, [liste des raisons de refus])
        """
        violations = []
        
        # Simuler l'ajout
        hypothetical = OpenPosition(
            instrument=instrument, direction=direction, size_usd=size_usd,
            profile_id="check", entry_time=time.time(), entry_price=0
        )
        self.positions.append(hypothetical)
        
        try:
            # 1. VaR portfolio
            var = self.compute_portfolio_var()
            if var > self.max_portfolio_var_pct:
                violations.append(
                    f"VaR portfolio {var:.2f}% > limite {self.max_portfolio_var_pct}%"
                )
            
            # 2. Concentration sur un instrument
            inst_exposure = sum(
                p.size_usd for p in self.positions if p.instrument == instrument
            )
            inst_pct = inst_exposure / self.capital * 100
            if inst_pct > self.max_single_instrument_pct:
                violations.append(
                    f"Concentration {instrument} {inst_pct:.1f}% > {self.max_single_instrument_pct}%"
                )
            
            # 3. Groupe corrélé (corr > 0.7)
            correlated_group_exposure = size_usd
            for pos in self.positions:
                if pos is hypothetical:
                    continue
                corr = abs(self._get_correlation(instrument, pos.instrument))
                if corr > 0.7:
                    correlated_group_exposure += pos.size_usd
            
            corr_pct = correlated_group_exposure / self.capital * 100
            if corr_pct > self.max_correlated_group_pct:
                violations.append(
                    f"Groupe corrélé {corr_pct:.1f}% > {self.max_correlated_group_pct}%"
                )
            
            # 4. Exposition directionnelle nette
            dir_exp = self.compute_net_directional_exposure()
            max_dir = max(abs(v) for v in dir_exp.values()) if dir_exp else 0
            if max_dir > self.max_net_directional_pct:
                violations.append(
                    f"Exposition directionnelle max {max_dir:.1f}% > {self.max_net_directional_pct}%"
                )
        finally:
            self.positions.pop()  # Retirer le trade hypothétique
        
        return len(violations) == 0, violations

    def add_position(self, position: OpenPosition) -> Tuple[bool, List[str]]:
        """Ajoute une position si elle passe les checks."""
        allowed, reasons = self.check_new_trade(
            position.instrument, position.direction, position.size_usd
        )
        if allowed:
            self.positions.append(position)
            self._save_state()
        return allowed, reasons

    def get_portfolio_summary(self) -> dict:
        """Snapshot complet du portfolio pour le dashboard."""
        total_exposure = sum(p.size_usd for p in self.positions)
        return {
            "total_positions": len(self.positions),
            "total_exposure_usd": total_exposure,
            "exposure_pct": round(total_exposure / self.capital * 100, 2),
            "var_95_pct": self.compute_portfolio_var(0.95),
            "var_99_pct": self.compute_portfolio_var(0.99),
            "directional_exposure": self.compute_net_directional_exposure(),
            "positions_by_instrument": {
                inst: sum(p.size_usd for p in self.positions if p.instrument == inst)
                for inst in set(p.instrument for p in self.positions)
            },
        }


# =============================================================================
# PROBLÈME 3 — CONVERGENCE vs CROWDING
# =============================================================================
#
# Insight clé : le crowding se manifeste quand :
#   a) Tous les signaux arrivent dans un intervalle serré (clustering temporel)
#   b) La volatilité est anormalement basse (compression avant expansion)
#   c) Le mouvement récent a déjà consommé l'essentiel du potentiel
#   d) Les volumes/momentum divergent de la direction du consensus
#
# Approche : 5 détecteurs indépendants → score de crowding [0, 1]
# Si score crowding > 0.6 → alerte même si convergence = forte
#


@dataclass
class MarketSnapshot:
    """État du marché au moment de l'évaluation."""
    instrument: str
    current_price: float
    atr_14: float                   # ATR(14) sur le timeframe principal
    atr_14_avg_20: float            # Moyenne mobile 20 périodes de l'ATR(14)
    recent_move_pct: float          # Mouvement depuis le dernier swing (en % de l'ATR)
    volume_current: float           # Volume de la bougie/période courante
    volume_avg_20: float            # Volume moyen 20 périodes
    rsi_14: float                   # RSI(14)
    consecutive_candles_same_dir: int  # Nombre de bougies consécutives dans la même direction
    time_since_last_reversal_hours: float  # Heures depuis le dernier swing significatif


class CrowdingDetector:
    """
    Problème 3 : Distingue convergence authentique vs crowding.
    
    5 détecteurs indépendants, chacun retourne un score [0, 1].
    Le score agrégé pondéré détermine le risque de crowding.
    """

    def __init__(
        self,
        crowding_threshold: float = 0.55,
        weights: Optional[Dict[str, float]] = None,
    ):
        self.threshold = crowding_threshold
        self.weights = weights or {
            "temporal_clustering": 0.20,   # Signaux trop synchronisés
            "volatility_compression": 0.25, # Vol basse → expansion imminente
            "move_exhaustion": 0.25,        # Le move a déjà eu lieu
            "volume_divergence": 0.15,      # Volume ne confirme pas
            "momentum_extremes": 0.15,      # RSI/momentum en zone extrême
        }

    def _temporal_clustering_score(self, signals: List[ProfileSignal]) -> float:
        """
        Détecte si les signaux sont trop groupés temporellement.
        
        Convergence saine : les profils convergent GRADUELLEMENT
        (Elliott détecte en premier, puis ICT confirme 2h après, etc.)
        
        Crowding : tout le monde détecte en même temps = même input
        → information redondante, pas indépendante.
        """
        if len(signals) < 2:
            return 0.0
        
        timestamps = sorted(s.timestamp for s in signals)
        spread = timestamps[-1] - timestamps[0]
        
        # Si tous les signaux tombent en < 5 minutes → très suspect
        # Si spread > 2h → convergence progressive (sain)
        if spread < 300:       # < 5 min
            return 0.95
        elif spread < 900:     # < 15 min
            return 0.70
        elif spread < 3600:    # < 1h
            return 0.40
        elif spread < 7200:    # < 2h
            return 0.20
        else:
            return 0.05

    def _volatility_compression_score(self, snapshot: MarketSnapshot) -> float:
        """
        Volatilité compressée = bombe à retardement.
        
        Quand ATR courant < 60% de sa moyenne → le marché accumule
        de l'énergie. Une convergence dans cette zone est souvent
        un faux signal : le breakout peut aller dans n'importe quelle direction.
        """
        if snapshot.atr_14_avg_20 == 0:
            return 0.0
        
        ratio = snapshot.atr_14 / snapshot.atr_14_avg_20
        
        if ratio < 0.5:
            return 0.90  # Compression extrême
        elif ratio < 0.65:
            return 0.65
        elif ratio < 0.80:
            return 0.35
        else:
            return 0.10  # Volatilité normale ou élevée → pas de compression

    def _move_exhaustion_score(self, snapshot: MarketSnapshot) -> float:
        """
        Le mouvement récent a-t-il déjà consommé le potentiel ?
        
        Si le prix a déjà bougé de > 2.5 ATR depuis le dernier swing,
        un signal de continuation est probablement du crowding :
        les profils détectent un trend qui est déjà épuisé.
        """
        move_in_atr = abs(snapshot.recent_move_pct)
        
        if move_in_atr > 3.0:
            return 0.90  # Mouvement extrême → épuisement probable
        elif move_in_atr > 2.5:
            return 0.70
        elif move_in_atr > 1.8:
            return 0.45
        elif move_in_atr > 1.0:
            return 0.20
        else:
            return 0.05  # Peu de mouvement → potentiel intact

    def _volume_divergence_score(self, snapshot: MarketSnapshot) -> float:
        """
        Le volume confirme-t-il la direction du consensus ?
        
        Volume décroissant pendant un move directionnel = distribution.
        Les smart money sortent pendant que les algos détectent un signal.
        """
        if snapshot.volume_avg_20 == 0:
            return 0.0
        
        vol_ratio = snapshot.volume_current / snapshot.volume_avg_20
        
        # Volume faible + bougies consécutives dans la même direction = red flag
        consecutive_factor = min(snapshot.consecutive_candles_same_dir / 8.0, 1.0)
        
        if vol_ratio < 0.6:
            return 0.80 * (0.5 + 0.5 * consecutive_factor)
        elif vol_ratio < 0.8:
            return 0.50 * (0.5 + 0.5 * consecutive_factor)
        else:
            return 0.10  # Volume sain

    def _momentum_extremes_score(self, snapshot: MarketSnapshot) -> float:
        """
        RSI en zone extrême = risque de retournement.
        
        Une convergence bullish avec RSI > 78 est suspecte :
        les profils voient un trend fort, mais le momentum est épuisé.
        """
        rsi = snapshot.rsi_14
        
        if rsi > 82 or rsi < 18:
            return 0.90
        elif rsi > 75 or rsi < 25:
            return 0.60
        elif rsi > 70 or rsi < 30:
            return 0.35
        else:
            return 0.05

    def evaluate(
        self,
        signals: List[ProfileSignal],
        snapshot: MarketSnapshot,
    ) -> Tuple[float, bool, Dict[str, float]]:
        """
        Évalue le risque de crowding.
        
        Returns:
            (crowding_score, is_crowding, détails_par_détecteur)
        """
        scores = {
            "temporal_clustering": self._temporal_clustering_score(signals),
            "volatility_compression": self._volatility_compression_score(snapshot),
            "move_exhaustion": self._move_exhaustion_score(snapshot),
            "volume_divergence": self._volume_divergence_score(snapshot),
            "momentum_extremes": self._momentum_extremes_score(snapshot),
        }
        
        # Score pondéré
        crowding = sum(
            self.weights[k] * scores[k] for k in scores
        )
        crowding = round(crowding, 4)
        
        return crowding, crowding > self.threshold, scores

    def adjusted_meta_score(
        self,
        meta_score: float,
        crowding_score: float,
    ) -> float:
        """
        Ajuste le score de convergence par le risque de crowding.
        
        S_adjusted = S_meta * (1 - crowding²)
        
        Quadratique : crowding à 0.5 réduit de 25%, à 0.7 réduit de 51%
        → Pénalise fortement le crowding élevé sans tuer les signaux modérés.
        """
        dampening = 1.0 - crowding_score ** 2
        return round(meta_score * dampening, 4)


# =============================================================================
# PROBLÈME 4 — META-LEARNER LÉGER
# =============================================================================
#
# Architecture :
#   - RandomForest avec max 200 arbres, profondeur max 8
#   - Features structurées en 4 groupes
#   - Réentraînement hebdomadaire glissant (fenêtre 60 jours)
#   - Walk-forward validation (pas de look-ahead bias)
#   - Tourne confortablement sur un VPS 2 vCPU / 4 GB RAM
#


class MetaLearner:
    """
    Problème 4 : Apprend quand la convergence est fiable.
    
    Input  : features structurées extraites de chaque décision
    Output : probabilité que le trade soit gagnant
    
    Cycle :
      1. Paper trading → collecte les features + résultat (TP/SL)
      2. Chaque dimanche → réentraîne sur fenêtre glissante 60j
      3. Walk-forward : train sur semaines 1-8, test sur semaine 9
      4. Si accuracy walk-forward < 52% → ne pas utiliser, fallback au scoring pur
    """

    # Définition des features
    FEATURE_NAMES = [
        # Groupe 1 : Scores des profils (5 features)
        "score_ict", "score_elliott", "score_vsa", "score_pure_pa", "score_custom",
        
        # Groupe 2 : Méta-convergence (6 features)
        "meta_score",              # Score du DynamicScorer
        "n_aligned_profiles",      # Nombre de profils alignés
        "freshness_min",           # Fraîcheur minimum (profil le plus vieux)
        "freshness_spread",        # Écart fraîcheur max - min
        "independence_avg",        # Indépendance moyenne des profils actifs
        "crowding_score",          # Score du CrowdingDetector
        
        # Groupe 3 : Contexte de marché (7 features)
        "atr_ratio",              # ATR courant / ATR moyen
        "rsi_14",
        "volume_ratio",           # Volume courant / Volume moyen
        "recent_move_atr",        # Mouvement récent en multiple d'ATR
        "consecutive_candles",
        "spread_pips",            # Spread au moment du signal
        "hour_of_day",            # Heure UTC (cyclicité intraday)
        
        # Groupe 4 : Validateurs externes (2 features)
        "gemini_vision_score",    # Score de la validation Gemini
        "claude_decision_score",  # Score de la décision Claude (1=go, 0=no-go)
        
        # Groupe 5 : Régime de marché (3 features encodées)
        "regime_trending",        # One-hot : trending
        "regime_ranging",         # One-hot : ranging
        "regime_volatile",        # One-hot : volatile/news
    ]

    def __init__(
        self,
        data_path: str = "meta_learner_data.json",
        model_path: str = "meta_learner_model.pkl",
        training_window_days: int = 60,
        min_samples_to_train: int = 80,
        walk_forward_weeks: int = 8,
    ):
        self.data_path = Path(data_path)
        self.model_path = Path(model_path)
        self.training_window_days = training_window_days
        self.min_samples = min_samples_to_train
        self.walk_forward_weeks = walk_forward_weeks
        self.model = None
        self.feature_importances = {}
        self.last_walk_forward_accuracy = 0.0
        self.samples: List[dict] = []
        self._load_data()

    def _load_data(self):
        if self.data_path.exists():
            self.samples = json.loads(self.data_path.read_text())

    def _save_data(self):
        self.data_path.write_text(json.dumps(self.samples, indent=2))

    def log_trade(self, features: Dict[str, float], outcome: int):
        """
        Enregistre un trade résolu.
        
        outcome : 1 = TP atteint (gagnant), 0 = SL touché (perdant)
        """
        record = {
            "features": features,
            "outcome": outcome,
            "timestamp": datetime.now().isoformat(),
        }
        self.samples.append(record)
        self._save_data()

    def extract_features(
        self,
        profile_scores: Dict[str, float],
        meta_score: float,
        signals: List[ProfileSignal],
        crowding_score: float,
        snapshot: MarketSnapshot,
        gemini_score: float,
        claude_decision: int,
        market_regime: str,   # "trending", "ranging", "volatile"
        spread_pips: float,
    ) -> Dict[str, float]:
        """
        Construit le vecteur de features à partir de l'état courant.
        
        Cette fonction est le CONTRAT entre le trading engine et le ML.
        Toute modification ici nécessite un réentraînement.
        """
        # Profils
        feat = {
            "score_ict": profile_scores.get("ict", 0),
            "score_elliott": profile_scores.get("elliott", 0),
            "score_vsa": profile_scores.get("vsa", 0),
            "score_pure_pa": profile_scores.get("pure_pa", 0),
            "score_custom": profile_scores.get("custom", 0),
        }
        
        # Méta-convergence
        active = [s for s in signals if s.direction != Direction.NEUTRAL]
        directions = [s.direction.value for s in active]
        majority_dir = np.sign(sum(directions)) if directions else 0
        n_aligned = sum(1 for d in directions if np.sign(d) == majority_dir)
        
        freshnesses = []
        scorer = DynamicScorer()
        for s in active:
            freshnesses.append(scorer._freshness_factor(s))
        
        feat.update({
            "meta_score": meta_score,
            "n_aligned_profiles": n_aligned,
            "freshness_min": min(freshnesses) if freshnesses else 0,
            "freshness_spread": (max(freshnesses) - min(freshnesses)) if len(freshnesses) > 1 else 0,
            "independence_avg": 0.5,  # Placeholder — rempli par le scorer en prod
            "crowding_score": crowding_score,
        })
        
        # Marché
        feat.update({
            "atr_ratio": snapshot.atr_14 / snapshot.atr_14_avg_20 if snapshot.atr_14_avg_20 > 0 else 1.0,
            "rsi_14": snapshot.rsi_14,
            "volume_ratio": snapshot.volume_current / snapshot.volume_avg_20 if snapshot.volume_avg_20 > 0 else 1.0,
            "recent_move_atr": abs(snapshot.recent_move_pct),
            "consecutive_candles": snapshot.consecutive_candles_same_dir,
            "spread_pips": spread_pips,
            "hour_of_day": datetime.now().hour,  # Idéalement UTC en prod
        })
        
        # Validateurs
        feat.update({
            "gemini_vision_score": gemini_score,
            "claude_decision_score": float(claude_decision),
        })
        
        # Régime one-hot
        feat.update({
            "regime_trending": 1.0 if market_regime == "trending" else 0.0,
            "regime_ranging": 1.0 if market_regime == "ranging" else 0.0,
            "regime_volatile": 1.0 if market_regime == "volatile" else 0.0,
        })
        
        return feat

    def train(self) -> Dict[str, any]:
        """
        Entraîne le modèle avec walk-forward validation.
        
        Architecture RandomForest :
          - n_estimators=150 (bon compromis perf/speed sur CPU)
          - max_depth=8 (évite l'overfitting sur petit dataset)
          - min_samples_leaf=5 (régularisation supplémentaire)
          - class_weight='balanced' (gère le déséquilibre TP/SL)
        
        Walk-forward :
          Train sur semaines 1→N-1, test sur semaine N.
          On itère sur les dernières fenêtres pour estimer la robustesse.
        """
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
        from sklearn.model_selection import TimeSeriesSplit
        import pickle
        
        if len(self.samples) < self.min_samples:
            return {
                "status": "insufficient_data",
                "current_samples": len(self.samples),
                "required": self.min_samples,
            }
        
        # Filtrer fenêtre glissante
        cutoff = (datetime.now() - timedelta(days=self.training_window_days)).isoformat()
        recent = [s for s in self.samples if s["timestamp"] >= cutoff]
        
        if len(recent) < self.min_samples:
            recent = self.samples[-self.min_samples:]
        
        # Construire X, y
        X = np.array([
            [s["features"].get(f, 0) for f in self.FEATURE_NAMES]
            for s in recent
        ])
        y = np.array([s["outcome"] for s in recent])
        
        # Walk-forward validation
        tscv = TimeSeriesSplit(n_splits=min(5, len(recent) // 20))
        wf_scores = []
        
        for train_idx, test_idx in tscv.split(X):
            X_train, X_test = X[train_idx], X[test_idx]
            y_train, y_test = y[train_idx], y[test_idx]
            
            rf = RandomForestClassifier(
                n_estimators=150,
                max_depth=8,
                min_samples_leaf=5,
                class_weight="balanced",
                random_state=42,
                n_jobs=-1,  # Utilise tous les CPU
            )
            rf.fit(X_train, y_train)
            wf_scores.append(accuracy_score(y_test, rf.predict(X_test)))
        
        self.last_walk_forward_accuracy = np.mean(wf_scores)
        
        # Entraîner le modèle final sur toutes les données récentes
        self.model = RandomForestClassifier(
            n_estimators=150,
            max_depth=8,
            min_samples_leaf=5,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )
        self.model.fit(X, y)
        
        # Feature importances
        self.feature_importances = dict(
            sorted(
                zip(self.FEATURE_NAMES, self.model.feature_importances_),
                key=lambda x: -x[1],
            )
        )
        
        # Sauvegarder
        with open(self.model_path, "wb") as f:
            pickle.dump(self.model, f)
        
        # Métriques finales
        y_pred = self.model.predict(X)
        return {
            "status": "trained",
            "n_samples": len(recent),
            "walk_forward_accuracy": round(self.last_walk_forward_accuracy, 4),
            "in_sample_accuracy": round(accuracy_score(y, y_pred), 4),
            "precision": round(precision_score(y, y_pred, zero_division=0), 4),
            "recall": round(recall_score(y, y_pred, zero_division=0), 4),
            "f1": round(f1_score(y, y_pred, zero_division=0), 4),
            "top_features": dict(list(self.feature_importances.items())[:8]),
            "model_usable": self.last_walk_forward_accuracy > 0.52,
        }

    def predict(self, features: Dict[str, float]) -> Tuple[float, bool]:
        """
        Prédit la probabilité de succès d'un trade.
        
        Returns:
            (probability, model_is_reliable)
            
        Si walk-forward accuracy < 52%, retourne (0.5, False)
        → le système fallback sur le scoring pur du DynamicScorer.
        """
        import pickle
        
        if self.model is None:
            if self.model_path.exists():
                with open(self.model_path, "rb") as f:
                    self.model = pickle.load(f)
            else:
                return 0.5, False
        
        reliable = self.last_walk_forward_accuracy > 0.52
        
        X = np.array([[features.get(f, 0) for f in self.FEATURE_NAMES]])
        proba = self.model.predict_proba(X)[0][1]  # P(win)
        
        return round(proba, 4), reliable


# =============================================================================
# ORCHESTRATEUR — Intègre les 4 composants
# =============================================================================

class MetaConvergenceEngine:
    """
    Point d'entrée unique qui orchestre :
    1. DynamicScorer  → score de convergence
    2. CrowdingDetector → filtre les faux signaux
    3. RiskGovernor → valide l'exposition
    4. MetaLearner → probabilité ML (si disponible)
    """

    def __init__(self, config: dict = None):
        config = config or {}
        self.scorer = DynamicScorer(
            activation_threshold=config.get("activation_threshold", 0.45)
        )
        self.crowding = CrowdingDetector(
            crowding_threshold=config.get("crowding_threshold", 0.55)
        )
        self.risk = RiskGovernor(
            capital_usd=config.get("capital_usd", 10000),
            max_portfolio_var_pct=config.get("max_var_pct", 2.0),
        )
        self.learner = MetaLearner()

    def evaluate_opportunity(
        self,
        signals: List[ProfileSignal],
        snapshot: MarketSnapshot,
        instrument: str,
        proposed_size_usd: float,
        gemini_score: float = 0.5,
        claude_decision: int = 1,
        market_regime: str = "trending",
        spread_pips: float = 1.0,
    ) -> dict:
        """
        Pipeline complet d'évaluation.
        
        Returns un dict avec la décision et toute la traçabilité.
        """
        # 1. Score de convergence
        activated, meta_score, score_details = self.scorer.should_activate(signals)
        
        # 2. Détection crowding
        crowd_score, is_crowding, crowd_details = self.crowding.evaluate(signals, snapshot)
        
        # 3. Score ajusté
        adjusted = self.crowding.adjusted_meta_score(meta_score, crowd_score)
        
        # 4. Direction
        direction = 1 if adjusted > 0 else -1
        
        # 5. Risk check
        risk_ok, risk_violations = self.risk.check_new_trade(
            instrument, direction, proposed_size_usd
        )
        
        # 6. ML prediction (si modèle disponible)
        profile_scores = {
            s.profile_id: s.confidence * s.direction.value for s in signals
        }
        features = self.learner.extract_features(
            profile_scores, meta_score, signals, crowd_score,
            snapshot, gemini_score, claude_decision, market_regime, spread_pips,
        )
        ml_proba, ml_reliable = self.learner.predict(features)
        
        # 7. Décision finale
        go_trade = (
            activated
            and not is_crowding
            and risk_ok
            and abs(adjusted) >= self.scorer.activation_threshold
        )
        
        # Si ML est fiable, l'utiliser comme filtre supplémentaire
        if ml_reliable and go_trade:
            go_trade = ml_proba >= 0.55  # Seuil ML
        
        return {
            "decision": "GO" if go_trade else "NO-GO",
            "instrument": instrument,
            "direction": "LONG" if direction > 0 else "SHORT",
            "meta_score_raw": meta_score,
            "meta_score_adjusted": adjusted,
            "crowding": {
                "score": crowd_score,
                "is_crowding": is_crowding,
                "details": crowd_details,
            },
            "risk": {
                "approved": risk_ok,
                "violations": risk_violations,
                "portfolio": self.risk.get_portfolio_summary(),
            },
            "ml": {
                "probability": ml_proba,
                "reliable": ml_reliable,
            },
            "profile_details": score_details,
            "features": features,
            "timestamp": datetime.now().isoformat(),
        }


# =============================================================================
# EXEMPLE D'UTILISATION
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("META-CONVERGENCE ENGINE — Demo")
    print("=" * 70)
    
    engine = MetaConvergenceEngine(config={
        "capital_usd": 10000,
        "activation_threshold": 0.45,
        "crowding_threshold": 0.55,
        "max_var_pct": 2.0,
    })
    
    # Simuler des stats de profils
    for pid in ["ict", "elliott", "vsa", "pure_pa", "custom"]:
        engine.scorer.stats[pid] = ProfileStats(
            profile_id=pid,
            sharpe_rolling=np.random.uniform(0.3, 1.8),
            win_rate=np.random.uniform(0.45, 0.65),
            total_signals=50,
            signal_history=list(np.random.choice([-1, 1], size=50)),
        )
    
    # Simuler des signaux
    now = time.time()
    signals = [
        ProfileSignal("ict", Direction.LONG, 0.82, now - 1800, 14400, "XAUUSD"),     # 30 min ago, TTL 4h
        ProfileSignal("elliott", Direction.LONG, 0.71, now - 7200, 43200, "XAUUSD"),  # 2h ago, TTL 12h
        ProfileSignal("vsa", Direction.LONG, 0.65, now - 3600, 28800, "XAUUSD"),      # 1h ago, TTL 8h
        ProfileSignal("pure_pa", Direction.SHORT, 0.45, now - 120, 600, "XAUUSD"),    # 2 min ago, TTL 10min
        ProfileSignal("custom", Direction.LONG, 0.55, now - 5400, 14400, "XAUUSD"),   # 1.5h ago, TTL 4h
    ]
    
    snapshot = MarketSnapshot(
        instrument="XAUUSD",
        current_price=2650.0,
        atr_14=18.5,
        atr_14_avg_20=22.0,
        recent_move_pct=1.4,
        volume_current=1200,
        volume_avg_20=1500,
        rsi_14=62.0,
        consecutive_candles_same_dir=3,
        time_since_last_reversal_hours=6.0,
    )
    
    result = engine.evaluate_opportunity(
        signals=signals,
        snapshot=snapshot,
        instrument="XAUUSD",
        proposed_size_usd=500,
        gemini_score=0.72,
        claude_decision=1,
        market_regime="trending",
        spread_pips=2.5,
    )
    
    print(f"\nDécision : {result['decision']}")
    print(f"Direction : {result['direction']}")
    print(f"Meta Score (raw) : {result['meta_score_raw']}")
    print(f"Meta Score (adjusted) : {result['meta_score_adjusted']}")
    print(f"Crowding : {result['crowding']['score']} ({'⚠️ CROWDING' if result['crowding']['is_crowding'] else '✅ OK'})")
    print(f"Risk : {'✅ Approved' if result['risk']['approved'] else '❌ Blocked'}")
    if result['risk']['violations']:
        for v in result['risk']['violations']:
            print(f"  → {v}")
    print(f"ML Proba : {result['ml']['probability']} ({'fiable' if result['ml']['reliable'] else 'non fiable'})")
    print(f"\nProfile Details:")
    for pid, det in result['profile_details'].items():
        print(f"  {pid}: {det['direction']} | w={det['perf_weight']} α={det['freshness']} ρ={det['independence']} → {det['contribution']}")
    
    print(f"\nPortfolio VaR 95% : {result['risk']['portfolio']['var_95_pct']}%")
    print(f"Exposition directionnelle : {result['risk']['portfolio']['directional_exposure']}")
