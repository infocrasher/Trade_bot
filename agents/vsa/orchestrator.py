"""
VSA Orchestrator
Point d'entrée unique de l'agent VSA.
Coordonne VolumeAnalyzer → ChartGenerator → GeminiAnalyzer → Scorer.
Interface compatible avec le MetaOrchestrator existant.

Mode : OBSERVATION (ne modifie pas les décisions ICT, log uniquement)
       Activation possible via config.py → VSA_ACTIVE = True
"""

import logging
import traceback
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from .volume_analyzer import VolumeAnalyzer, VSAAnalysis
from .chart_generator  import ChartGenerator
from .gemini_analyzer  import GeminiVSAAnalyzer
from .scorer           import VSAScorer, VSAScore

logger = logging.getLogger(__name__)

# Mapping timeframe VSA → timeframe TwelveDataProvider
TF_MAP = {
    'scalp':    'M5',
    'intraday': 'H1',
    'daily':    'D1',
    'weekly':   'W1',
}

# Nombre de bougies par timeframe
TF_BARS = {
    'scalp':    288,
    'intraday': 200,
    'daily':    200,
    'weekly':   100,
}


class VSAOrchestrator:
    """
    Orchestre l'analyse VSA complète pour une paire et un timeframe.
    Utilisé par le MetaOrchestrator en observation mode.
    """

    OBSERVATION_MODE = True      # passe à False quand validé en production
    MIN_SCORE_LOG    = 30        # score minimum pour logger le résultat
    N_CANDLES_CHART  = 60        # bougies affichées dans le graphique

    def __init__(self,
                 gemini_api_key: Optional[str] = None,
                 enable_charts: bool = True):
        """
        gemini_api_key : clé API Gemini (ou None pour désactiver la vision)
        enable_charts  : si False, saute la génération PNG (plus rapide, moins de RAM)
        """
        self.volume_analyzer = VolumeAnalyzer()
        self.chart_generator = ChartGenerator(n_candles=self.N_CANDLES_CHART) if enable_charts else None
        self.gemini_analyzer = GeminiVSAAnalyzer(api_key=gemini_api_key)
        self.scorer          = VSAScorer()
        self.enable_charts   = enable_charts

        # Data provider
        try:
            from data.twelve_data_provider import TwelveDataProvider
            self._data_provider = TwelveDataProvider()
        except Exception:
            self._data_provider = None

        mode = "OBSERVATION" if self.OBSERVATION_MODE else "ACTIF"
        logger.info(f"[VSAOrchestrator] Initialisé — mode {mode} | "
                    f"Gemini: {'✓' if self.gemini_analyzer.enabled else '✗'} | "
                    f"Charts: {'✓' if enable_charts else '✗'}")

    # ──────────────────────────────────────────
    # POINT D'ENTRÉE PRINCIPAL
    # ──────────────────────────────────────────

    def analyze(self,
                symbol: str,
                timeframe: str,
                df: Optional[pd.DataFrame] = None) -> Optional[VSAScore]:
        """
        Lance l'analyse VSA complète.

        symbol    : ex. "EURUSD"
        timeframe : "scalp" | "intraday" | "daily" | "weekly"
        df        : DataFrame OHLCV optionnel (si None → téléchargé via yfinance)

        Retourne un VSAScore ou None en cas d'erreur.
        """
        try:
            # 1. Données OHLCV
            if df is None:
                df = self._fetch_data(symbol, timeframe)
            if df is None or len(df) < 30:
                logger.warning(f"[VSAOrch] {symbol}/{timeframe} — données insuffisantes")
                return None

            # 2. Analyse algorithmique pure
            analysis = self.volume_analyzer.analyze(df, symbol, timeframe)

            # 3. Génération graphique (si activé)
            image_b64 = None
            if self.enable_charts and self.chart_generator:
                df_with_indicators = self.volume_analyzer._compute_indicators(df.copy())
                image_b64 = self.chart_generator.generate(df_with_indicators, analysis)

            # 4. Analyse Gemini Vision
            gemini_result = None
            if self.gemini_analyzer.enabled and image_b64:
                gemini_result = self.gemini_analyzer.analyze(image_b64, analysis)
            else:
                gemini_result = self.gemini_analyzer._empty_response()

            # 5. Score final fusionné
            vsa_score = self.scorer.score(analysis, gemini_result)

            # 6. Log
            self._log_result(vsa_score)

            return vsa_score

        except Exception as e:
            logger.error(f"[VSAOrch] Erreur {symbol}/{timeframe} : {e}\n{traceback.format_exc()}")
            return None

    # ──────────────────────────────────────────
    # INTERFACE METAORCHESTRATOR
    # ──────────────────────────────────────────

    def get_signal_for_meta(self,
                             symbol: str,
                             timeframe: str,
                             df: Optional[pd.DataFrame] = None) -> dict:
        """
        Interface standardisée pour le MetaOrchestrator.
        Retourne un dict compatible avec le format des autres agents.

        Exemple de retour :
        {
            'agent': 'VSA',
            'symbol': 'EURUSD',
            'timeframe': 'daily',
            'score': 72.5,
            'direction': 'BUY',
            'action': 'EXECUTE',
            'signal': 'SELLING_CLIMAX',
            'wyckoff_phase': 'ACCUMULATION_C',
            'observation_mode': True,
            'timestamp': '2026-03-07T08:00:00Z'
        }
        """
        vsa_score = self.analyze(symbol, timeframe, df)

        if vsa_score is None:
            return {
                'agent':            'VSA',
                'symbol':           symbol,
                'timeframe':        timeframe,
                'score':            0,
                'direction':        'NEUTRAL',
                'action':           'IGNORE',
                'signal':           'ERROR',
                'wyckoff_phase':    'UNDEFINED',
                'observation_mode': self.OBSERVATION_MODE,
                'timestamp':        datetime.now(timezone.utc).isoformat(),
                'error':            True,
            }

        return {
            'agent':             'VSA',
            'symbol':            vsa_score.symbol,
            'timeframe':         vsa_score.timeframe,
            'score':             vsa_score.score_total,
            'score_algo':        vsa_score.score_algo,
            'score_visuel':      vsa_score.score_visuel,
            'direction':         vsa_score.direction,
            'action':            vsa_score.action,
            'signal':            vsa_score.signal_name,
            'wyckoff_phase':     vsa_score.wyckoff_phase,
            'wyckoff_cycle':     vsa_score.wyckoff_cycle,
            'balance':           vsa_score.balance,
            'absorption':        vsa_score.absorption,
            'confiance':         vsa_score.confiance,
            'invalidations':     vsa_score.invalidations,
            'confluences':       vsa_score.confluences,
            'commentaire':       vsa_score.commentaire_algo,
            'commentaire_gemini':vsa_score.commentaire_gemini,
            'observation_mode':  self.OBSERVATION_MODE,
            'gemini_available':  vsa_score.gemini_available,
            'timestamp':         datetime.now(timezone.utc).isoformat(),
        }

    def analyze_all_pairs(self,
                           symbols: list,
                           timeframe: str = 'daily',
                           df_map: Optional[dict] = None) -> list[dict]:
        """
        Analyse toutes les paires en séquence.
        df_map : dict optionnel {symbol: DataFrame} pour éviter des re-téléchargements.
        Retourne la liste des signaux triés par score décroissant.
        """
        results = []
        for symbol in symbols:
            df = df_map.get(symbol) if df_map else None
            signal = self.get_signal_for_meta(symbol, timeframe, df)
            results.append(signal)

        # Trier par score décroissant
        results.sort(key=lambda x: x.get('score', 0), reverse=True)

        # Log résumé
        executed = [r for r in results if r['action'] == 'EXECUTE']
        logger.info(f"[VSAOrch] {len(symbols)} paires analysées | "
                    f"{len(executed)} signaux EXECUTE | "
                    f"TF: {timeframe}")

        return results

    # ──────────────────────────────────────────
    # FETCH DONNÉES
    # ──────────────────────────────────────────

    def _fetch_data(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """Télécharge les données OHLCV via TwelveDataProvider."""
        td_tf   = TF_MAP.get(timeframe, 'D1')
        n_bars  = TF_BARS.get(timeframe, 200)

        if self._data_provider and self._data_provider.connected:
            try:
                df = self._data_provider.get_ohlcv(symbol, td_tf, n_bars)
                if df.empty:
                    logger.warning(f"[VSAOrch] TwelveData — aucune donnée {symbol}/{timeframe}")
                    return None

                # Normaliser les noms de colonnes en majuscules (compatibilité VolumeAnalyzer)
                df.columns = [c.capitalize() for c in df.columns]
                if 'Volume' not in df.columns and 'Tick_volume' in df.columns:
                    df.rename(columns={'Tick_volume': 'Volume'}, inplace=True)

                df.dropna(inplace=True)
                df = df[df['Volume'] > 0]
                return df

            except Exception as e:
                logger.error(f"[VSAOrch] TwelveData erreur {symbol}/{timeframe} : {e}")
                return None
        else:
            logger.warning(f"[VSAOrch] TwelveData non connecté — {symbol}/{timeframe} ignoré")
            return None

    # ──────────────────────────────────────────
    # LOGGING
    # ──────────────────────────────────────────

    def _log_result(self, score: VSAScore):
        """Log le résultat si score suffisant."""
        if score.score_total < self.MIN_SCORE_LOG and score.action == 'IGNORE':
            return

        obs = "[OBS]" if self.OBSERVATION_MODE else "[LIVE]"
        gemini_str = f"G:{score.score_visuel:.0f}" if score.gemini_available else "G:N/A"

        logger.info(
            f"[VSA]{obs} {score.symbol}/{score.timeframe} | "
            f"Score: {score.score_total:.1f}/100 "
            f"(A:{score.score_algo:.1f} + {gemini_str}) | "
            f"{score.direction} | {score.action} | "
            f"Signal: {score.signal_name} | "
            f"Phase: {score.wyckoff_phase} | "
            f"Balance: {score.balance:+.1f}"
        )

        if score.invalidations:
            for inv in score.invalidations:
                logger.debug(f"[VSA]   ↳ Invalidation: {inv}")
