"""
VSA Chart Generator
Génère un graphique PNG annoté (bougies + volume + signaux VSA)
pour analyse visuelle par Gemini Flash Vision.
"""

import io
import base64
import logging
from typing import Optional

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')   # pas de display — mode serveur
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Rectangle
from matplotlib.gridspec import GridSpec

from .volume_analyzer import VSAAnalysis, VSASignal, VolumeLevel, WyckoffCycle

logger = logging.getLogger(__name__)


# Couleurs du thème dark (lisible par Gemini)
COLORS = {
    'bg':          '#0d1117',
    'bg_panel':    '#161b22',
    'grid':        '#21262d',
    'text':        '#e6edf3',
    'bull_candle': '#26a641',
    'bear_candle': '#f85149',
    'volume_bull': '#26a64166',
    'volume_bear': '#f8514966',
    'sos_marker':  '#58a6ff',
    'sow_marker':  '#f78166',
    'demand_zone': '#26a64120',
    'supply_zone': '#f8514920',
    'sma_vol':     '#d29922',
    'phase_label': '#ffa657',
}

# Signaux SOS → flèche montante bleue
SOS_SIGNALS = {
    VSASignal.NO_SUPPLY, VSASignal.TEST_SUCCESS, VSASignal.STOPPING_VOLUME,
    VSASignal.SELLING_CLIMAX, VSASignal.PUSH_THROUGH_SUPPLY, VSASignal.BOTTOM_REVERSAL,
    VSASignal.REVERSE_UPTHRUST, VSASignal.SHAKE_AND_RALLY, VSASignal.SQUAT_BULLISH,
    VSASignal.BAG_HOLDING_BULL, VSASignal.SHAKEOUT,
}

# Signaux SOW → flèche descendante rouge
SOW_SIGNALS = {
    VSASignal.NO_DEMAND, VSASignal.UPTHRUST, VSASignal.HIDDEN_UPTHRUST,
    VSASignal.BUYING_CLIMAX, VSASignal.END_RISING_MARKET, VSASignal.TOP_REVERSAL,
    VSASignal.PSEUDO_UPTHRUST, VSASignal.SQUAT_BEARISH, VSASignal.INVERSE_SQUAT,
    VSASignal.BAG_HOLDING_BEAR,
}


class ChartGenerator:
    """
    Génère un graphique en chandeliers annotés VSA/Wyckoff.
    Sortie : image PNG encodée en base64 (pour Gemini Vision API).
    """

    def __init__(self, n_candles: int = 60):
        """
        n_candles : nombre de bougies à afficher (défaut 60).
        """
        self.n_candles = n_candles

    def generate(self, df: pd.DataFrame, analysis: VSAAnalysis) -> Optional[str]:
        """
        Génère le graphique et retourne l'image en base64.
        Retourne None en cas d'erreur.

        df     : DataFrame OHLCV complet (avec indicateurs calculés)
        analysis : VSAAnalysis retourné par VolumeAnalyzer
        """
        try:
            df_plot = df.tail(self.n_candles).copy().reset_index(drop=False)
            signals = analysis.recent_signals[-self.n_candles:]

            fig = self._build_figure(df_plot, signals, analysis)
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=100,
                        bbox_inches='tight', facecolor=COLORS['bg'])
            plt.close(fig)
            buf.seek(0)
            return base64.b64encode(buf.read()).decode('utf-8')

        except Exception as e:
            logger.error(f"[ChartGenerator] Erreur génération graphique : {e}")
            return None

    # ─────────────────────────────────────────
    # CONSTRUCTION DU GRAPHIQUE
    # ─────────────────────────────────────────

    def _build_figure(self, df_plot, signals, analysis: VSAAnalysis):
        fig = plt.figure(figsize=(16, 9), facecolor=COLORS['bg'])
        gs  = GridSpec(3, 1, figure=fig,
                       height_ratios=[3, 1, 0.3],
                       hspace=0.05)

        ax_price  = fig.add_subplot(gs[0])
        ax_volume = fig.add_subplot(gs[1], sharex=ax_price)
        ax_info   = fig.add_subplot(gs[2])

        self._style_ax(ax_price)
        self._style_ax(ax_volume)
        ax_info.axis('off')
        ax_info.set_facecolor(COLORS['bg'])

        # Tracés
        self._draw_candles(ax_price, df_plot)
        self._draw_demand_supply_zones(ax_price, analysis, df_plot)
        self._draw_signal_markers(ax_price, df_plot, signals)
        self._draw_volume_bars(ax_volume, df_plot)
        self._draw_sma_volume(ax_volume, df_plot)

        # Labels
        self._draw_price_labels(ax_price, df_plot)
        self._draw_title(ax_price, analysis)
        self._draw_info_bar(ax_info, analysis)

        # Masquer les x-ticks du panneau prix
        plt.setp(ax_price.get_xticklabels(), visible=False)
        self._draw_x_labels(ax_volume, df_plot)

        return fig

    # ─────────────────────────────────────────
    # BOUGIES
    # ─────────────────────────────────────────

    def _draw_candles(self, ax, df):
        for i, row in df.iterrows():
            color = COLORS['bull_candle'] if row['Close'] >= row['Open'] else COLORS['bear_candle']
            # Corps
            body_bot = min(row['Open'], row['Close'])
            body_h   = abs(row['Close'] - row['Open'])
            ax.add_patch(Rectangle((i - 0.4, body_bot), 0.8, body_h,
                                   facecolor=color, edgecolor=color, linewidth=0.5))
            # Mèches
            ax.plot([i, i], [row['Low'], body_bot],     color=color, linewidth=0.8)
            ax.plot([i, i], [body_bot + body_h, row['High']], color=color, linewidth=0.8)

        ax.set_xlim(-1, len(df))
        prices = pd.concat([df['High'], df['Low']])
        margin = (prices.max() - prices.min()) * 0.05
        ax.set_ylim(prices.min() - margin, prices.max() + margin)

    # ─────────────────────────────────────────
    # ZONES DEMAND / SUPPLY
    # ─────────────────────────────────────────

    def _draw_demand_supply_zones(self, ax, analysis: VSAAnalysis, df_plot):
        x_max = len(df_plot)
        last_close = df_plot.iloc[-1]['Close']

        for zone in analysis.demand_zones[-3:]:
            if zone['low'] < last_close * 1.02:  # zone active sous le prix
                ax.axhspan(zone['low'], zone['high'],
                           facecolor=COLORS['demand_zone'],
                           edgecolor=COLORS['bull_candle'],
                           linewidth=0.5, alpha=0.4, label='Demand Zone')

        for zone in analysis.supply_zones[-3:]:
            if zone['high'] > last_close * 0.98:  # zone active au-dessus
                ax.axhspan(zone['low'], zone['high'],
                           facecolor=COLORS['supply_zone'],
                           edgecolor=COLORS['bear_candle'],
                           linewidth=0.5, alpha=0.4, label='Supply Zone')

    # ─────────────────────────────────────────
    # MARQUEURS SIGNAUX VSA
    # ─────────────────────────────────────────

    def _draw_signal_markers(self, ax, df_plot, signals):
        """
        Place les flèches et étiquettes sur les bougies signalées.
        Offset calculé dynamiquement selon la plage de prix.
        """
        price_range = df_plot['High'].max() - df_plot['Low'].min()
        offset = price_range * 0.015

        # Les signaux sont indexés depuis i=2 dans df original
        # On aligne les derniers N signaux avec les N dernières bougies
        n = min(len(signals), len(df_plot))
        signals_aligned = signals[-n:]
        df_aligned      = df_plot.tail(n).reset_index(drop=True)

        for i, (sig, row) in enumerate(zip(signals_aligned, df_aligned.itertuples())):
            if sig.signal == VSASignal.NEUTRAL:
                continue

            label = self._short_label(sig.signal)

            if sig.signal in SOS_SIGNALS:
                y_pos = row.Low - offset * 2
                ax.annotate('▲', xy=(i, row.Low - offset),
                            fontsize=10, color=COLORS['sos_marker'],
                            ha='center', va='top', fontweight='bold')
                ax.annotate(label, xy=(i, y_pos),
                            fontsize=5.5, color=COLORS['sos_marker'],
                            ha='center', va='top', rotation=45)

            elif sig.signal in SOW_SIGNALS:
                y_pos = row.High + offset * 2
                ax.annotate('▼', xy=(i, row.High + offset),
                            fontsize=10, color=COLORS['sow_marker'],
                            ha='center', va='bottom', fontweight='bold')
                ax.annotate(label, xy=(i, y_pos),
                            fontsize=5.5, color=COLORS['sow_marker'],
                            ha='center', va='bottom', rotation=45)

    def _short_label(self, signal: VSASignal) -> str:
        labels = {
            VSASignal.NO_SUPPLY:           'NO_SUP',
            VSASignal.TEST_SUCCESS:        'TEST',
            VSASignal.STOPPING_VOLUME:     'STP_VOL',
            VSASignal.SELLING_CLIMAX:      'SC',
            VSASignal.PUSH_THROUGH_SUPPLY: 'PTS',
            VSASignal.BOTTOM_REVERSAL:     'BOT_REV',
            VSASignal.REVERSE_UPTHRUST:    'REV_UT',
            VSASignal.SHAKE_AND_RALLY:     'S&R',
            VSASignal.SQUAT_BULLISH:       'SQUAT↑',
            VSASignal.BAG_HOLDING_BULL:    'BAG↑',
            VSASignal.SHAKEOUT:            'SHAKEOUT',
            VSASignal.NO_DEMAND:           'NO_DEM',
            VSASignal.UPTHRUST:            'UT',
            VSASignal.HIDDEN_UPTHRUST:     'HID_UT',
            VSASignal.BUYING_CLIMAX:       'BC',
            VSASignal.END_RISING_MARKET:   'ERM',
            VSASignal.TOP_REVERSAL:        'TOP_REV',
            VSASignal.PSEUDO_UPTHRUST:     'PSE_UT',
            VSASignal.SQUAT_BEARISH:       'SQUAT↓',
            VSASignal.INVERSE_SQUAT:       'INV_SQT',
            VSASignal.BAG_HOLDING_BEAR:    'BAG↓',
        }
        return labels.get(signal, signal.value[:7])

    # ─────────────────────────────────────────
    # VOLUME
    # ─────────────────────────────────────────

    def _draw_volume_bars(self, ax, df):
        for i, row in df.iterrows():
            color = COLORS['volume_bull'] if row['Close'] >= row['Open'] else COLORS['volume_bear']
            ax.bar(i, row['Volume'], color=color, width=0.8, linewidth=0)
        ax.set_ylabel('Volume', color=COLORS['text'], fontsize=8)

    def _draw_sma_volume(self, ax, df):
        if 'sma_vol' in df.columns:
            ax.plot(df.index, df['sma_vol'],
                    color=COLORS['sma_vol'], linewidth=1.0,
                    linestyle='--', label='SMA Vol(20)')
            ax.legend(loc='upper left', fontsize=7,
                      facecolor=COLORS['bg_panel'], labelcolor=COLORS['text'])

    # ─────────────────────────────────────────
    # LABELS & COSMÉTIQUE
    # ─────────────────────────────────────────

    def _draw_price_labels(self, ax, df):
        last_close = df.iloc[-1]['Close']
        ax.axhline(last_close, color=COLORS['text'],
                   linewidth=0.5, linestyle=':', alpha=0.6)
        ax.annotate(f'{last_close:.5f}',
                    xy=(len(df) - 1, last_close),
                    xytext=(5, 0), textcoords='offset points',
                    fontsize=7, color=COLORS['text'],
                    va='center')

    def _draw_title(self, ax, analysis: VSAAnalysis):
        signal_name = analysis.last_bar_result.signal.value
        phase_name  = analysis.wyckoff_state.phase.value
        balance_str = f"Balance: {analysis.balance:+.1f}"
        title = (f"{analysis.symbol} | {analysis.timeframe} | "
                 f"Signal: {signal_name} | Phase: {phase_name} | {balance_str}")
        ax.set_title(title, color=COLORS['phase_label'],
                     fontsize=9, loc='left', pad=8)

    def _draw_info_bar(self, ax, analysis: VSAAnalysis):
        """Barre d'info textuelle en bas du graphique."""
        sig    = analysis.last_bar_result
        cycle  = analysis.wyckoff_state.cycle.value
        score  = analysis.raw_score
        absorb = "✓ ABSORPTION" if analysis.absorption_detected else ""
        multi  = f"Multi-signal: {analysis.multi_signal_count}x" if analysis.multi_signal_count >= 2 else ""

        info = (f"Direction: {sig.direction}  |  "
                f"Strength: {sig.strength:.0%}  |  "
                f"Cycle: {cycle}  |  "
                f"Score algo: {score:.1f}/50  |  "
                f"{absorb}  {multi}")
        ax.text(0.01, 0.5, info,
                transform=ax.transAxes,
                fontsize=7.5, color=COLORS['text'],
                va='center', ha='left')

    def _draw_x_labels(self, ax, df):
        step = max(1, len(df) // 10)
        ticks = range(0, len(df), step)
        if 'index' in df.columns and hasattr(df['index'].iloc[0], 'strftime'):
            labels = [df['index'].iloc[i].strftime('%m/%d %H:%M')
                      if i < len(df) else '' for i in ticks]
        else:
            labels = [str(df.index[i]) if i < len(df) else '' for i in ticks]
        ax.set_xticks(list(ticks))
        ax.set_xticklabels(labels, rotation=30, ha='right',
                           fontsize=6.5, color=COLORS['text'])

    def _style_ax(self, ax):
        ax.set_facecolor(COLORS['bg_panel'])
        ax.tick_params(colors=COLORS['text'], labelsize=7)
        ax.yaxis.label.set_color(COLORS['text'])
        for spine in ax.spines.values():
            spine.set_edgecolor(COLORS['grid'])
        ax.grid(True, color=COLORS['grid'], linewidth=0.4, alpha=0.5)
