"""
LiquidityDetector — Détecteur de Niveaux de Liquidité Institutionnelle (P-F2)
===============================================================================
Détecte 7 types de niveaux ICT directement depuis les DataFrames bruts :

1. PDH/PDL    — Previous Day High/Low (df_d1)
2. PWH/PWL    — Previous Week High/Low (df_d1)
3. Asia Range — High/Low 21h00-00h00 UTC (df_m5 ou df_h1)
4. Midnight   — Open 00h00 UTC (bougie M5/H1 la plus proche)
5. EQH/EQL    — Equal Highs/Lows en tolérance 3 pips
6. Sweeps     — Turtle Soup : dépasse puis referme (PDH/PDL/EQH/EQL)
7. DOL        — Draw On Liquidity : prochain niveau non sweepé selon bias

Interface : detect_all(df_m5, df_h1, df_d1, bias) -> dict
"""

import logging
import pandas as pd
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


class LiquidityDetector:
    """
    Détecteur de niveaux de liquidité institutionnelle ICT.
    Calcule directement depuis les OHLCV bruts (M5, H1, D1).
    """

    # Constantes
    EQUAL_TOLERANCE_PIPS = 3   # Tolérance EQH/EQL en pips
    ASIA_SESSION_START_H = 21  # 21h00 UTC = début session Asia
    ASIA_SESSION_END_H   = 0   # 00h00 UTC = fin session Asia

    def __init__(self, symbol: str):
        self.symbol    = symbol
        self._pip_size = self._get_pip_size(symbol)
        self._tolerance = self.EQUAL_TOLERANCE_PIPS * self._pip_size

    # ─────────────────────────────────────────────────────────────────────────
    # POINT D'ENTRÉE PRINCIPAL
    # ─────────────────────────────────────────────────────────────────────────

    def detect_all(
        self,
        df_m5: Optional[pd.DataFrame],
        df_h1: Optional[pd.DataFrame],
        df_d1: Optional[pd.DataFrame],
        bias: str = "bullish"
    ) -> dict:
        """
        Lance la détection complète de tous les niveaux de liquidité.

        Args:
            df_m5  : DataFrame OHLCV M5 (colonnes minuscules open/high/low/close/time)
            df_h1  : DataFrame OHLCV H1
            df_d1  : DataFrame OHLCV D1
            bias   : Biais HTF (bullish/bearish/neutral)

        Returns:
            dict avec pdh, pdl, pwh, pwl, asia_high, asia_low,
                      midnight_open, equal_highs, equal_lows,
                      sweeps, dol
        """
        # Nettoyer les DataFrames
        df_m5 = self._clean_df(df_m5)
        df_h1 = self._clean_df(df_h1)
        df_d1 = self._clean_df(df_d1)

        # 1. PDH/PDL — Previous Day High/Low
        pdh, pdl = self._calc_pdh_pdl(df_d1)

        # 2. PWH/PWL — Previous Week High/Low
        pwh, pwl = self._calc_pwh_pwl(df_d1)

        # 3. Asia Range — 21h-00h UTC
        asia_high, asia_low = self._calc_asia_range(df_m5 if df_m5 is not None else df_h1)

        # 4. Midnight Open — 00h00 UTC
        midnight_open = self._calc_midnight_open(df_m5 if df_m5 is not None else df_h1)

        # 5. Equal Highs/Lows
        intraday_df = df_m5 if df_m5 is not None else df_h1
        equal_highs, equal_lows = self._calc_equal_levels(intraday_df)

        # 6. Liquidity Sweeps — Turtle Soup
        all_levels = {
            "pdh": pdh, "pdl": pdl, "pwh": pwh, "pwl": pwl,
            "equal_highs": equal_highs, "equal_lows": equal_lows
        }
        sweeps = self._calc_sweeps(intraday_df, all_levels)

        # 7. DOL — Draw On Liquidity
        current_price = self._get_current_price(intraday_df)
        dol = self._calc_dol(
            current_price, bias,
            pdh, pdl, pwh, pwl,
            asia_high, asia_low,
            equal_highs, equal_lows,
            sweeps
        )

        return {
            "symbol":        self.symbol,
            "pdh":           pdh,
            "pdl":           pdl,
            "pwh":           pwh,
            "pwl":           pwl,
            "asia_high":     asia_high,
            "asia_low":      asia_low,
            "midnight_open": midnight_open,
            "equal_highs":   equal_highs,
            "equal_lows":    equal_lows,
            "sweeps":        sweeps,
            "dol":           dol,
            "bias":          bias,
            "current_price": current_price,
            "timestamp":     datetime.now(timezone.utc).isoformat(),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # 1. PDH / PDL — Previous Day High/Low
    # ─────────────────────────────────────────────────────────────────────────

    def _calc_pdh_pdl(self, df_d1: Optional[pd.DataFrame]) -> tuple:
        """Retourne (PDH, PDL) depuis le D1 précédent."""
        if df_d1 is None or len(df_d1) < 2:
            return None, None

        prev_day = df_d1.iloc[-2]  # Avant-dernière bougie = jour précédent
        pdh = round(float(prev_day["high"]), 6)
        pdl = round(float(prev_day["low"]),  6)
        return pdh, pdl

    # ─────────────────────────────────────────────────────────────────────────
    # 2. PWH / PWL — Previous Week High/Low
    # ─────────────────────────────────────────────────────────────────────────

    def _calc_pwh_pwl(self, df_d1: Optional[pd.DataFrame]) -> tuple:
        """Retourne (PWH, PWL) depuis les 5 dernières bougies D1 (semaine précédente)."""
        if df_d1 is None or len(df_d1) < 6:
            return None, None

        # On prend les 5 bougies D1 précédant aujourd'hui (5 jours ouvrables)
        prev_week = df_d1.iloc[-6:-1]
        pwh = round(float(prev_week["high"].max()), 6)
        pwl = round(float(prev_week["low"].min()),  6)
        return pwh, pwl

    # ─────────────────────────────────────────────────────────────────────────
    # 3. Asia Range — 21h00-00h00 UTC
    # ─────────────────────────────────────────────────────────────────────────

    def _calc_asia_range(self, df: Optional[pd.DataFrame]) -> tuple:
        """Retourne (asia_high, asia_low) depuis les bougies entre 21h-00h UTC."""
        if df is None or len(df) < 3:
            return None, None

        try:
            work = df.copy()
            if "time" in work.columns:
                time_col = pd.to_datetime(work["time"], utc=True)
            elif hasattr(work.index, "hour"):
                time_col = pd.Series(work.index)
            else:
                return None, None

            # Normaliser en UTC
            if hasattr(time_col, "dt"):
                if time_col.dt.tz is None:
                    time_col = time_col.dt.tz_localize("UTC")
                else:
                    time_col = time_col.dt.tz_convert("UTC")
                hours = time_col.dt.hour
            else:
                return None, None

            # Bougies 21h-23h59 UTC (ASIA_SESSION_START = 21, END = 0)
            mask = hours >= self.ASIA_SESSION_START_H  # 21, 22, 23
            asia = work[mask.values]

            if len(asia) == 0:
                return None, None

            # Prendre seulement les dernières 24h d'Asia (évite les anciennes sessions)
            asia = asia.tail(3 * 12)  # ≈ 3h × 12 bougies M5

            asia_high = round(float(asia["high"].max()), 6)
            asia_low  = round(float(asia["low"].min()),  6)
            return asia_high, asia_low

        except Exception as e:
            logger.warning(f"[LiquidityDetector] Asia range erreur : {e}")
            return None, None

    # ─────────────────────────────────────────────────────────────────────────
    # 4. Midnight Open — bougie la plus proche de 00h00 UTC
    # ─────────────────────────────────────────────────────────────────────────

    def _calc_midnight_open(self, df: Optional[pd.DataFrame]) -> Optional[float]:
        """Retourne le prix open de la bougie la plus proche de 00h00 UTC."""
        if df is None or len(df) < 3:
            return None

        try:
            work = df.copy()
            if "time" in work.columns:
                time_col = pd.to_datetime(work["time"], utc=True)
                if time_col.dt.tz is None:
                    time_col = time_col.dt.tz_localize("UTC")
                else:
                    time_col = time_col.dt.tz_convert("UTC")
                # Cherche les bougies avec hour==0 dans les dernières 48h
                mask = time_col.dt.hour == 0
                midnight_candles = work[mask.values]
                if len(midnight_candles) > 0:
                    return round(float(midnight_candles.iloc[-1]["open"]), 6)

            return None

        except Exception as e:
            logger.warning(f"[LiquidityDetector] Midnight open erreur : {e}")
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # 5. Equal Highs / Equal Lows — tolérance 3 pips
    # ─────────────────────────────────────────────────────────────────────────

    def _calc_equal_levels(self, df: Optional[pd.DataFrame]) -> tuple:
        """Détecte les EQH/EQL (2+ points dans une tolérance de 3 pips)."""
        if df is None or len(df) < 10:
            return [], []

        # Détecter les swing highs/lows simples (lookback=3)
        highs = self._detect_swing_highs(df)
        lows  = self._detect_swing_lows(df)

        equal_highs = self._group_equal_levels(highs)
        equal_lows  = self._group_equal_levels(lows)

        return equal_highs, equal_lows

    def _detect_swing_highs(self, df: pd.DataFrame, lookback: int = 3) -> list:
        """Détecte les swing highs avec lookback donné."""
        highs = []
        for i in range(lookback, len(df) - lookback):
            window = df.iloc[i - lookback: i + lookback + 1]
            if float(df["high"].iloc[i]) == float(window["high"].max()):
                highs.append(round(float(df["high"].iloc[i]), 6))
        return highs

    def _detect_swing_lows(self, df: pd.DataFrame, lookback: int = 3) -> list:
        """Détecte les swing lows avec lookback donné."""
        lows = []
        for i in range(lookback, len(df) - lookback):
            window = df.iloc[i - lookback: i + lookback + 1]
            if float(df["low"].iloc[i]) == float(window["low"].min()):
                lows.append(round(float(df["low"].iloc[i]), 6))
        return lows

    def _group_equal_levels(self, prices: list) -> list:
        """Regroupe les niveaux proches (< tolérance) en EQH/EQL."""
        if not prices:
            return []

        groups = []
        used   = set()

        for i, p in enumerate(prices):
            if i in used:
                continue
            group = [p]
            for j, q in enumerate(prices[i+1:], start=i+1):
                if abs(p - q) <= self._tolerance:
                    group.append(q)
                    used.add(j)
            if len(group) >= 2:
                avg_level = round(sum(group) / len(group), 6)
                groups.append({
                    "level": avg_level,
                    "count": len(group),
                    "type":  "equal_level",
                })

        return groups

    # ─────────────────────────────────────────────────────────────────────────
    # 6. Liquidity Sweeps — Turtle Soup
    # ─────────────────────────────────────────────────────────────────────────

    def _calc_sweeps(self, df: Optional[pd.DataFrame], levels: dict) -> list:
        """
        Détecte les Turtle Soup : bougie qui dépasse un niveau
        puis referme en-dessous (BSL) ou au-dessus (SSL).
        """
        if df is None or len(df) < 5:
            return []

        sweeps = []
        target_levels = []

        # Niveaux BSL (Buyside)— on peut les balayer par le haut
        for k in ["pdh", "pwh"]:
            v = levels.get(k)
            if v:
                target_levels.append({"price": v, "name": k.upper(), "side": "BSL"})

        for eqh in levels.get("equal_highs", []):
            target_levels.append({"price": eqh["level"], "name": "EQH", "side": "BSL"})

        # Niveaux SSL (Sellside) — on peut les balayer par le bas
        for k in ["pdl", "pwl"]:
            v = levels.get(k)
            if v:
                target_levels.append({"price": v, "name": k.upper(), "side": "SSL"})

        for eql in levels.get("equal_lows", []):
            target_levels.append({"price": eql["level"], "name": "EQL", "side": "SSL"})

        # Scan les 50 dernières bougies pour les sweeps récents
        scan_df = df.tail(50)

        for lvl in target_levels:
            price = lvl["price"]
            side  = lvl["side"]

            for i in range(1, len(scan_df)):
                candle = scan_df.iloc[i]

                if side == "BSL":
                    # High dépasse le niveau ET close en dessous → BSL Sweep
                    if float(candle["high"]) > price and float(candle["close"]) < price:
                        sweeps.append({
                            "type":          "buyside_sweep",
                            "swept_level":   price,
                            "level_name":    lvl["name"],
                            "bar_index":     i,
                            "candle_high":   round(float(candle["high"]), 6),
                            "candle_close":  round(float(candle["close"]), 6),
                        })
                else:  # SSL
                    # Low dépasse le niveau ET close au dessus → SSL Sweep
                    if float(candle["low"]) < price and float(candle["close"]) > price:
                        sweeps.append({
                            "type":          "sellside_sweep",
                            "swept_level":   price,
                            "level_name":    lvl["name"],
                            "bar_index":     i,
                            "candle_low":    round(float(candle["low"]), 6),
                            "candle_close":  round(float(candle["close"]), 6),
                        })

        # Dédupliquer : garder le plus récent par niveau
        seen = {}
        for s in sweeps:
            key = f"{s['swept_level']}_{s['type']}"
            if key not in seen or s["bar_index"] > seen[key]["bar_index"]:
                seen[key] = s

        return list(seen.values())

    # ─────────────────────────────────────────────────────────────────────────
    # 7. DOL — Draw On Liquidity
    # ─────────────────────────────────────────────────────────────────────────

    def _calc_dol(
        self,
        current_price: float,
        bias: str,
        pdh, pdl, pwh, pwl,
        asia_high, asia_low,
        equal_highs, equal_lows,
        sweeps
    ) -> dict:
        """
        DOL = prochain niveau de liquidité non encore sweepé
        dans la direction du biais HTF.
        """
        swept_levels = {s["swept_level"] for s in sweeps}
        candidates   = []

        if bias == "bullish":
            # Cherche les niveaux BSL au-dessus du prix
            if pdh and pdh > current_price and pdh not in swept_levels:
                candidates.append({"name": "PDH", "price": pdh, "priority": 1})
            if pwh and pwh > current_price and pwh not in swept_levels:
                candidates.append({"name": "PWH", "price": pwh, "priority": 2})
            if asia_high and asia_high > current_price and asia_high not in swept_levels:
                candidates.append({"name": "ASIA_HIGH", "price": asia_high, "priority": 3})
            for eqh in equal_highs:
                if eqh["level"] > current_price and eqh["level"] not in swept_levels:
                    candidates.append({"name": f"EQH×{eqh['count']}", "price": eqh["level"], "priority": 4})

        elif bias == "bearish":
            # Cherche les niveaux SSL en dessous du prix
            if pdl and pdl < current_price and pdl not in swept_levels:
                candidates.append({"name": "PDL", "price": pdl, "priority": 1})
            if pwl and pwl < current_price and pwl not in swept_levels:
                candidates.append({"name": "PWL", "price": pwl, "priority": 2})
            if asia_low and asia_low < current_price and asia_low not in swept_levels:
                candidates.append({"name": "ASIA_LOW", "price": asia_low, "priority": 3})
            for eql in equal_lows:
                if eql["level"] < current_price and eql["level"] not in swept_levels:
                    candidates.append({"name": f"EQL×{eql['count']}", "price": eql["level"], "priority": 4})

        if not candidates:
            return {"name": "N/A", "price": 0, "dist_pips": 0, "bias": bias}

        # Tri : priorité ICT d'abord, puis le plus proche
        candidates.sort(key=lambda x: (x["priority"], abs(x["price"] - current_price)))
        best = candidates[0]
        best["dist_pips"] = round(abs(best["price"] - current_price) / self._pip_size, 1)
        best["bias"]      = bias
        best.pop("priority", None)
        return best

    # ─────────────────────────────────────────────────────────────────────────
    # UTILITAIRES
    # ─────────────────────────────────────────────────────────────────────────

    def _get_current_price(self, df: Optional[pd.DataFrame]) -> float:
        if df is not None and len(df) > 0:
            return round(float(df["close"].iloc[-1]), 6)
        return 0.0

    def _clean_df(self, df: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
        if df is None or len(df) == 0:
            return None
        df = df.copy()
        df.columns = [c.lower() for c in df.columns]
        # S'assurer que les colonnes essentielles existent
        for col in ["open", "high", "low", "close"]:
            if col not in df.columns:
                return None
        return df

    def _get_pip_size(self, symbol: str) -> float:
        s = symbol.upper()
        if "JPY"  in s:                                    return 0.01
        if "XAU"  in s or "GOLD" in s:                    return 0.01
        if "XAG"  in s:                                    return 0.001
        if "BTC"  in s:                                    return 1.0
        if "ETH"  in s:                                    return 0.1
        if "OIL"  in s or "WTI" in s or "BRENT" in s:    return 0.01
        return 0.0001
