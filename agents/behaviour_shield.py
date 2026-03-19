"""
BehaviourShield (P-F1) — Dernier filtre avant création d'un Paper Trade
========================================================================
8 filtres comportementaux protégeant contre les erreurs d'exécution :

BS1 — Stop Hunt       : Mèche > 3× corps + retour sur niveau clé
BS2 — Fake Breakout   : Cassure sans confirmation H1
BS3 — Liquidity Grab  : EQH/EQL purgés, prix pas encore réintégré
BS4 — News Spike      : Mouvement > 2×ATR dans les 3 dernières minutes
BS5 — Overextension   : > 3×ATR depuis la zone d'entrée
BS6 — Revenge Trade   : 3 SL consécutifs même paire même direction
BS7 — Duplicate       : Même signal < 10 minutes
BS8 — Staleness       : Setup calculé il y a > 5 minutes
"""

import logging
import time
from datetime import datetime, timezone
from typing import Optional, List
import pandas as pd

logger = logging.getLogger("ict_bot")


class BehaviourShield:
    """
    Dernier filtre comportemental avant la création d'un paper trade.
    Méthode principale : check() → dict {blocked, reason, filter}
    """

    def __init__(self):
        # Registre interne pour BS7 Duplicate
        # Format: { "EURUSD_BUY": timestamp_last_signal }
        self._signal_registry: dict = {}
        # Registre pour BS6 (géré par caller ou passé via context)

    # ─────────────────────────────────────────────────────────────────────────
    # POINT D'ENTRÉE PRINCIPAL
    # ─────────────────────────────────────────────────────────────────────────

    def check(
        self,
        pair: str,
        direction: str,
        entry_price: float,
        sl: float,
        df_m5: Optional[pd.DataFrame] = None,
        context: Optional[dict] = None
    ) -> dict:
        """
        Exécute les 8 filtres dans l'ordre et retourne dès le premier blocage.

        Args:
            pair        : Paire (ex: 'EURUSD')
            direction   : 'BUY' ou 'SELL'
            entry_price : Prix d'entrée théorique
            sl          : Stop loss
            df_m5       : DataFrame M5 recent (OHLCV)
            context     : dict optionnel avec clés supplémentaires :
                          - 'df_h1'       : DataFrame H1
                          - 'key_levels'  : dict {pdh, pdl, eqh, eql}
                          - 'recent_trades': liste de trades récents (BS6)
                          - 'entry_time'  : datetime du signal (BS8)
                          - 'atr'         : ATR précalculé (optionnel)

        Returns:
            dict : {'blocked': bool, 'reason': str, 'filter': str}
        """
        ctx = context or {}

        # BS1 — Stop Hunt
        res = self._bs1_stop_hunt(df_m5, ctx)
        if res["blocked"]:
            return res

        # BS2 — Fake Breakout
        res = self._bs2_fake_breakout(entry_price, direction, df_m5, ctx)
        if res["blocked"]:
            return res

        # BS3 — Liquidity Grab
        res = self._bs3_liquidity_grab(entry_price, direction, ctx)
        if res["blocked"]:
            return res

        # BS4 — News Spike
        res = self._bs4_news_spike(df_m5, ctx)
        if res["blocked"]:
            return res

        # BS5 — Overextension
        res = self._bs5_overextension(entry_price, df_m5, ctx)
        if res["blocked"]:
            return res

        # BS6 — Revenge Trade
        res = self._bs6_revenge_trade(pair, direction, ctx)
        if res["blocked"]:
            return res

        # BS7 — Duplicate Signal
        res = self._bs7_duplicate(pair, direction)
        if res["blocked"]:
            return res

        # BS8 — Staleness
        res = self._bs8_staleness(ctx)
        if res["blocked"]:
            return res

        # Tout est passé → enregistrer le signal pour BS7
        self._register_signal(pair, direction)

        return {"blocked": False, "reason": "", "filter": "PASS"}

    # ─────────────────────────────────────────────────────────────────────────
    # BS1 — Stop Hunt
    # Mèche > 3× corps ET retour vers un niveau clé
    # ─────────────────────────────────────────────────────────────────────────

    def _bs1_stop_hunt(self, df_m5: Optional[pd.DataFrame], ctx: dict) -> dict:
        """Bougie précédente avec mèche > 3× corps → potentiel stop hunt."""
        try:
            if df_m5 is None or len(df_m5) < 2:
                return self._pass()

            prev = df_m5.iloc[-2]
            o, h, l, c = float(prev["open"]), float(prev["high"]), float(prev["low"]), float(prev["close"])

            body  = abs(c - o)
            upper_wick = h - max(o, c)
            lower_wick = min(o, c) - l

            # Mèche dominante > 3× corps
            dominant_wick = max(upper_wick, lower_wick)
            if body <= 0 or dominant_wick <= 3 * body:
                return self._pass()

            # Vérifier si le prix (actuel OU précédent) est proche d'un niveau clé
            # Tolérance : 2 × dominant_wick (zone de retour après spike)
            current = float(df_m5.iloc[-1]["close"])
            tolerance = dominant_wick * 2
            key_levels = ctx.get("key_levels", {})

            for k, v in key_levels.items():
                if not v:
                    continue
                # Si le spike a atteint ou dépassé le niveau (bougie spike proche du level)
                if abs(h - v) <= tolerance or abs(l - v) <= tolerance:
                    return {
                        "blocked": True,
                        "reason": f"Stop Hunt détecté — mèche {dominant_wick / body:.1f}× corps vers {k} ({v:.5f})",
                        "filter": "BS1_STOP_HUNT"
                    }
        except Exception:
            pass

        return self._pass()

    # ─────────────────────────────────────────────────────────────────────────
    # BS2 — Fake Breakout
    # Cassure d'un niveau clé sans confirmation H1
    # ─────────────────────────────────────────────────────────────────────────

    def _bs2_fake_breakout(
        self, entry_price: float, direction: str,
        df_m5: Optional[pd.DataFrame], ctx: dict
    ) -> dict:
        """Cassure M5 d'un PDH/PDL sans confirmation de clôture H1 au-dessus."""
        try:
            df_h1 = ctx.get("df_h1")
            key_levels = ctx.get("key_levels", {})
            if df_m5 is None or df_h1 is None or len(df_h1) < 2:
                return self._pass()

            # Dernière clôture H1
            last_h1_close = float(df_h1.iloc[-1]["close"])
            last_h1_high  = float(df_h1.iloc[-1]["high"])
            last_h1_low   = float(df_h1.iloc[-1]["low"])

            for level_name in ["pdh", "pwh"]:
                level = key_levels.get(level_name, 0)
                if not level:
                    continue
                # M5 a cassé le niveau (entry au-dessus)
                if direction in ("BUY", "ACHAT") and entry_price > level:
                    # H1 n'a pas clôturé au-dessus
                    if last_h1_close <= level:
                        return {
                            "blocked": True,
                            "reason": f"Fake Breakout sans confirmation H1 — M5 au dessus du {level_name.upper()} ({level}) mais H1 close {last_h1_close:.5f} en dessous",
                            "filter": "BS2_FAKE_BREAKOUT"
                        }

            for level_name in ["pdl", "pwl"]:
                level = key_levels.get(level_name, 0)
                if not level:
                    continue
                if direction in ("SELL", "VENTE") and entry_price < level:
                    if last_h1_close >= level:
                        return {
                            "blocked": True,
                            "reason": f"Fake Breakout sans confirmation H1 — M5 sous le {level_name.upper()} ({level}) mais H1 close {last_h1_close:.5f} au-dessus",
                            "filter": "BS2_FAKE_BREAKOUT"
                        }

        except Exception:
            pass

        return self._pass()

    # ─────────────────────────────────────────────────────────────────────────
    # BS3 — Liquidity Grab
    # EQH/EQL purgés mais prix pas réintégré
    # ─────────────────────────────────────────────────────────────────────────

    def _bs3_liquidity_grab(self, entry_price: float, direction: str, ctx: dict) -> dict:
        """Sweep EQH/EQL récent détecté mais réintégration pas encore confirmée."""
        try:
            sweeps = ctx.get("recent_sweeps", [])
            key_levels = ctx.get("key_levels", {})
            if not sweeps:
                return self._pass()

            for sweep in sweeps[-3:]:  # Regarder les 3 derniers sweeps
                sweep_type = sweep.get("type", "")
                swept_lvl  = sweep.get("swept_level", 0)
                bar_idx    = sweep.get("bar_index", 999)

                # Sweep récent (dans les 5 dernières bougies)
                if bar_idx > 5:
                    continue

                if sweep_type == "buyside_sweep" and direction in ("BUY", "ACHAT"):
                    # Sweep BSL + on veut BUY → prix a purgé les acheteurs, attendre réintégration
                    if entry_price < swept_lvl:
                        return {
                            "blocked": True,
                            "reason": f"Liquidity Grab en cours — EQH ({swept_lvl}) sweepé, attendre réintégration avant BUY",
                            "filter": "BS3_LIQUIDITY_GRAB"
                        }
                elif sweep_type == "sellside_sweep" and direction in ("SELL", "VENTE"):
                    if entry_price > swept_lvl:
                        return {
                            "blocked": True,
                            "reason": f"Liquidity Grab en cours — EQL ({swept_lvl}) sweepé, attendre réintégration avant SELL",
                            "filter": "BS3_LIQUIDITY_GRAB"
                        }
        except Exception:
            pass

        return self._pass()

    # ─────────────────────────────────────────────────────────────────────────
    # BS4 — News Spike
    # Mouvement > 2×ATR dans les 3 dernières bougies M5
    # ─────────────────────────────────────────────────────────────────────────

    def _bs4_news_spike(self, df_m5: Optional[pd.DataFrame], ctx: dict) -> dict:
        """Mouvement violent > 2×ATR sur les 3 dernières bougies M5 = news spike."""
        try:
            if df_m5 is None or len(df_m5) < 20:
                return self._pass()

            atr = ctx.get("atr") or self._calc_atr(df_m5, 14)
            if not atr or atr <= 0:
                return self._pass()

            # Regarde les 3 dernières bougies
            last_3 = df_m5.tail(3)
            for _, row in last_3.iterrows():
                candle_range = abs(float(row["high"]) - float(row["low"]))
                if candle_range > 2 * atr:
                    return {
                        "blocked": True,
                        "reason": f"News Spike détecté — bougie de {candle_range:.5f} > 2×ATR ({2*atr:.5f}) — entrée < 3 bougies après mouvement violent",
                        "filter": "BS4_NEWS_SPIKE"
                    }

        except Exception:
            pass

        return self._pass()

    # ─────────────────────────────────────────────────────────────────────────
    # BS5 — Overextension
    # Prix > 3×ATR(14) depuis la zone d'entrée (OB/FVG)
    # ─────────────────────────────────────────────────────────────────────────

    def _bs5_overextension(
        self, entry_price: float, df_m5: Optional[pd.DataFrame], ctx: dict
    ) -> dict:
        """Prix trop loin de la zone d'entrée = overextension."""
        try:
            if df_m5 is None or len(df_m5) < 20 or not entry_price:
                return self._pass()

            atr = ctx.get("atr") or self._calc_atr(df_m5, 14)
            if not atr or atr <= 0:
                return self._pass()

            current = float(df_m5.iloc[-1]["close"])
            dist = abs(current - entry_price)

            if dist > 3 * atr:
                return {
                    "blocked": True,
                    "reason": f"Prix surextensé — {dist:.5f} > 3×ATR ({3*atr:.5f}) depuis la zone d'entrée {entry_price}",
                    "filter": "BS5_OVEREXTENSION"
                }

        except Exception:
            pass

        return self._pass()

    # ─────────────────────────────────────────────────────────────────────────
    # BS6 — Revenge Trade
    # 3 SL consécutifs même paire même direction
    # ─────────────────────────────────────────────────────────────────────────

    def _bs6_revenge_trade(self, pair: str, direction: str, ctx: dict) -> dict:
        """Bloque si les 3 derniers trades fermés sur cette paire/direction sont des SL."""
        try:
            recent_trades = ctx.get("recent_trades", [])
            if not recent_trades:
                return self._pass()

            # Filtrer par paire et direction
            dir_norm = "BUY" if direction in ("BUY", "ACHAT") else "SELL"
            matching = [
                t for t in recent_trades
                if t.get("pair", "") == pair and
                (t.get("direction", "BUY") in (dir_norm, "ACHAT" if dir_norm == "BUY" else "VENTE"))
                and t.get("status") == "sl_hit"
            ][-3:]  # Derniers 3 correspondants

            if len(matching) >= 3:
                return {
                    "blocked": True,
                    "reason": f"Revenge Trade — 3 pertes consécutives sur {pair} {dir_norm}. Attendre reset.",
                    "filter": "BS6_REVENGE_TRADE"
                }

        except Exception:
            pass

        return self._pass()

    # ─────────────────────────────────────────────────────────────────────────
    # BS7 — Duplicate Signal
    # Même paire + même direction dans les 10 dernières minutes
    # ─────────────────────────────────────────────────────────────────────────

    def _bs7_duplicate(self, pair: str, direction: str) -> dict:
        """Bloque si un signal identique a été généré < 10 minutes."""
        try:
            dir_norm = "BUY" if direction in ("BUY", "ACHAT") else "SELL"
            key = f"{pair}_{dir_norm}"
            last_ts = self._signal_registry.get(key, 0)
            now = time.time()

            if now - last_ts < 600:  # 10 minutes
                elapsed = int(now - last_ts)
                return {
                    "blocked": True,
                    "reason": f"Signal dupliqué — même setup {pair} {dir_norm} il y a {elapsed}s (< 10min)",
                    "filter": "BS7_DUPLICATE"
                }

        except Exception:
            pass

        return self._pass()

    # ─────────────────────────────────────────────────────────────────────────
    # BS8 — Staleness
    # Signal calculé il y a > 5 minutes
    # ─────────────────────────────────────────────────────────────────────────

    def _bs8_staleness(self, ctx: dict) -> dict:
        """Bloque si le setup a été calculé il y a plus de 5 minutes."""
        try:
            entry_time = ctx.get("entry_time")
            if entry_time is None:
                return self._pass()

            # Accepte datetime ou timestamp float
            if isinstance(entry_time, datetime):
                if entry_time.tzinfo is None:
                    entry_time = entry_time.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                age_seconds = (now - entry_time).total_seconds()
            elif isinstance(entry_time, (int, float)):
                age_seconds = time.time() - entry_time
            else:
                return self._pass()

            if age_seconds > 300:  # 5 minutes
                return {
                    "blocked": True,
                    "reason": f"Setup périmé — calculé il y a {int(age_seconds)}s (max 300s) — recalculer",
                    "filter": "BS8_STALENESS"
                }

        except Exception:
            pass

        return self._pass()

    # ─────────────────────────────────────────────────────────────────────────
    # UTILITAIRES
    # ─────────────────────────────────────────────────────────────────────────

    def _register_signal(self, pair: str, direction: str):
        """Enregistre le signal dans le registre BS7."""
        dir_norm = "BUY" if direction in ("BUY", "ACHAT") else "SELL"
        self._signal_registry[f"{pair}_{dir_norm}"] = time.time()

    def _pass(self) -> dict:
        return {"blocked": False, "reason": "", "filter": ""}

    def _calc_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """ATR(14) depuis un DataFrame OHLCV."""
        try:
            if len(df) < period + 1:
                return float((df["high"] - df["low"]).mean())
            tr = pd.concat([
                df["high"] - df["low"],
                (df["high"] - df["close"].shift()).abs(),
                (df["low"]  - df["close"].shift()).abs(),
            ], axis=1).max(axis=1)
            return float(tr.tail(period).mean())
        except Exception:
            return 0.0
