"""
LiquidityTracker — Agent ICT de Liquidité Enrichi
===================================================
Enrichit les données de liquidité brutes de structure.py avec :

1. ERL / IRL Mapping
   - ERL (External Range Liquidity) = BSL/SSL aux extrêmes du range (100 bougies)
   - IRL (Internal Range Liquidity) = FVG/imbalances internes non comblés
   - Statut SWEPT / INTACT sur chaque niveau

2. DOL Directionnel (Draw On Liquidity)
   - dol_bull = premier BSL intact au-dessus du prix
   - dol_bear = premier SSL intact en-dessous du prix
   - Priorité : EQH SMOOTH > EQH JAGGED > PDH > PWH > BSL MAX

3. Anti-Inducement — Validation Sweep ERL avant MSS
   - Un MSS est valide SEULEMENT si un sweep ERL l'a précédé
   - Règle : SWH ou SWL dans les 5% de l'extrême ERL
   - Résultat : VALIDATED / INDUCEMENT_RISK / NO_MSS

4. LRLR / HRLR (Low/High Resistance Liquidity Run)
   - Compte les FVG non comblés entre prix actuel et DOL
   - 0-1 obstacle → LRLR (chemin dégagé ✅)
   - 2+ obstacles → HRLR (résistance probable ⚠️)

5. CBDR (Central Bank Dealers Range)
   - Range 14h-20h EST de la session précédente
   - Si range < 40 pips → CBDR Explosive → déploiement tendanciel probable
   - Projections SD x1.0 / x2.0 / x2.5 depuis les extrêmes CBDR

6. Boolean Sweep ERL
   - Variable d'état : sweep ERL récent confirmé ou non
   - Pénalité -15pts si False (pas de sweep ERL préalable)

Input  : df OHLCV + structure_report de StructureAgent (EQH/EQL, PDH/PDL, sweeps, FVG, MSS)
Output : dict liquidity_report consommable par orchestrator.py

Sources : ICT Mentorship 2022-2024, Bible ICT §4, §5, §15, §18
"""

import logging
import pandas as pd
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


class LiquidityTracker:
    """
    Agent de liquidité ICT enrichi.
    Reçoit les données déjà calculées par StructureAgent et les enrichit.
    Ne recalcule jamais ce que structure.py a déjà calculé.
    """

    ANTI_INDUCEMENT_PCT  = 0.05   # 5% — proximité SWH/SWL vs extrême ERL
    LRLR_MAX_OBSTACLES   = 1      # Seuil LRLR : 0 ou 1 obstacle = chemin dégagé
    CBDR_EXPLOSIVE_PIPS  = 40     # CBDR < 40 pips = explosif
    ERL_LOOKBACK         = 100    # Fenêtre ERL en bougies
    SWEEP_SCAN_WINDOW    = 30     # Bougies scannées pour _is_swept
    BOOL_SWEEP_TOLERANCE = 10     # Tolérance pips pour Boolean_Sweep_ERL

    def __init__(self, symbol: str):
        self.symbol    = symbol
        self._pip_size = self._get_pip_size(symbol)

    # ─────────────────────────────────────────────────────────────
    # POINT D'ENTRÉE PRINCIPAL
    # ─────────────────────────────────────────────────────────────

    def analyze(
        self,
        df: pd.DataFrame,
        structure_report: dict,
        tf: str = "H1"
    ) -> dict:
        """
        Lance l'analyse complète de liquidité enrichie.

        Args:
            df               : DataFrame OHLCV colonnes minuscules (open/high/low/close)
            structure_report : dict d'un seul TF retourné par StructureAgent.analyze_multi_tf()[tf]
                               Doit contenir : equal_levels, liquidity_sweeps, fvg, mss,
                               swings, key_levels (optionnel)
            tf               : timeframe en cours d'analyse

        Returns:
            dict liquidity_report avec toutes les données enrichies
        """
        if df is None or len(df) < 50:
            logger.warning(
                f"[LiqTracker] {self.symbol}/{tf} — données insuffisantes "
                f"({len(df) if df is not None else 0} bougies)"
            )
            return self._empty_report()

        # Normaliser colonnes
        df = df.copy()
        df.columns = [c.lower() for c in df.columns]

        current_price = float(df["close"].iloc[-1])
        atr           = self._calc_atr(df, 14)

        # Extraire depuis structure_report
        eq_levels  = structure_report.get("equal_levels", [])
        key_levels = structure_report.get("key_levels", {})
        fvgs       = structure_report.get("fvg", [])
        sweeps     = structure_report.get("liquidity_sweeps", [])
        swings     = structure_report.get("swings", [])
        mss_events = structure_report.get("mss", [])

        # 1. ERL / IRL
        erl = self._compute_erl(df, current_price)
        irl = self._compute_irl(fvgs, current_price)

        # 2. Niveaux temporels enrichis
        temporal = self._enrich_temporal_levels(key_levels, df, current_price)

        # 3. EQH / EQL enrichis
        eqh = self._enrich_eq_levels(eq_levels, df, current_price, atr, "EQH")
        eql = self._enrich_eq_levels(eq_levels, df, current_price, atr, "EQL")

        # 4. DOL directionnel
        dol_bull = self._find_dol(current_price, eqh, erl, temporal, "BULL")
        dol_bear = self._find_dol(current_price, eql, erl, temporal, "BEAR")

        # 5. Anti-Inducement
        anti_inducement = self._check_anti_inducement(mss_events, swings, erl)

        # 6. LRLR / HRLR
        lrlr_hrlr = self._compute_lrlr_hrlr(current_price, dol_bull, dol_bear, fvgs)

        # 7. CBDR
        cbdr = self._compute_cbdr(df)

        # 8. Boolean Sweep ERL
        boolean_sweep_erl = self._compute_boolean_sweep_erl(sweeps, erl)

        # 9. Pénalité score agrégée
        score_penalty = self._compute_score_penalty(
            anti_inducement, boolean_sweep_erl, lrlr_hrlr
        )

        return {
            "symbol":             self.symbol,
            "tf":                 tf,
            "current_price":      round(current_price, 6),
            "atr":                round(atr, 6),
            "erl":                erl,
            "irl":                irl,
            "eqh":                eqh,
            "eql":                eql,
            "temporal_levels":    temporal,
            "dol_bull":           dol_bull,
            "dol_bear":           dol_bear,
            "anti_inducement":    anti_inducement,
            "lrlr_hrlr":          lrlr_hrlr,
            "cbdr":               cbdr,
            "boolean_sweep_erl":  boolean_sweep_erl,
            "score_penalty":      score_penalty,
            "timestamp":          datetime.now(timezone.utc).isoformat(),
        }

    # ─────────────────────────────────────────────────────────────
    # 1. ERL — External Range Liquidity
    # Bible §15.1 — extrêmes des 100 dernières bougies, statut SWEPT/INTACT
    # ─────────────────────────────────────────────────────────────

    def _compute_erl(self, df: pd.DataFrame, current_price: float) -> dict:
        window   = df.tail(self.ERL_LOOKBACK)
        erl_high = float(window["high"].max())
        erl_low  = float(window["low"].min())

        return {
            "high":        round(erl_high, 6),
            "low":         round(erl_low,  6),
            "high_swept":  self._is_swept(df, erl_high, "BSL"),
            "low_swept":   self._is_swept(df, erl_low,  "SSL"),
            "high_status": "SWEPT" if self._is_swept(df, erl_high, "BSL") else "INTACT",
            "low_status":  "SWEPT" if self._is_swept(df, erl_low,  "SSL") else "INTACT",
        }

    # ─────────────────────────────────────────────────────────────
    # 2. IRL — Internal Range Liquidity
    # Bible §15.1 — FVG non comblés = liquidité interne restante
    # ─────────────────────────────────────────────────────────────

    def _compute_irl(self, fvgs: list, current_price: float) -> list:
        irl = []
        for fvg in fvgs:
            if fvg.get("status") not in ("open", "partially_filled"):
                continue
            top    = fvg.get("top", 0)
            bottom = fvg.get("bottom", 0)
            ce     = fvg.get("midpoint", (top + bottom) / 2)
            irl.append({
                "type":   fvg.get("type", ""),
                "top":    round(top, 6),
                "bottom": round(bottom, 6),
                "ce":     round(ce, 6),
                "status": fvg.get("status", "open"),
                "side":   "ABOVE" if ce > current_price else "BELOW",
            })
        return irl

    # ─────────────────────────────────────────────────────────────
    # 3. Niveaux temporels enrichis — PDH/PDL/PWH/PWL
    # Bible §4.2 — annotés SWEPT/INTACT + position vs prix
    # ─────────────────────────────────────────────────────────────

    def _enrich_temporal_levels(
        self, key_levels: dict, df: pd.DataFrame, current_price: float
    ) -> dict:
        mapping = {
            "PDH": "BSL", "PDL": "SSL",
            "PWH": "BSL", "PWL": "SSL",
            "PMH": "BSL", "PML": "SSL",
        }
        temporal = {}
        for key, sweep_dir in mapping.items():
            price = key_levels.get(key, 0)
            if not price or price <= 0:
                continue
            swept = self._is_swept(df, price, sweep_dir)
            temporal[key] = {
                "price":  round(price, 6),
                "status": "SWEPT" if swept else "INTACT",
                "side":   "ABOVE" if price > current_price else "BELOW",
            }
        return temporal

    # ─────────────────────────────────────────────────────────────
    # 4. EQH / EQL enrichis
    # Bible §14.1 — SMOOTH/JAGGED + SWEPT/INTACT + PROXIMAL/DISTAL
    # ─────────────────────────────────────────────────────────────

    def _enrich_eq_levels(
        self,
        eq_levels: list,
        df: pd.DataFrame,
        current_price: float,
        atr: float,
        level_type: str   # "EQH" ou "EQL"
    ) -> list:
        sweep_dir = "BSL" if level_type == "EQH" else "SSL"
        result    = []

        for lvl in eq_levels:
            if lvl.get("type") != level_type:
                continue

            price   = lvl["level"]
            count   = lvl.get("count", 2)
            swept   = self._is_swept(df, price, sweep_dir)
            quality = "SMOOTH" if (lvl.get("strength") == "strong" or count >= 3) else "JAGGED"

            result.append({
                "price":     round(price, 6),
                "count":     count,
                "quality":   quality,
                "swept":     swept,
                "status":    "SWEPT" if swept else "INTACT",
                "proximity": "PROXIMAL" if abs(price - current_price) < atr * 3 else "DISTAL",
                "side":      "ABOVE" if price > current_price else "BELOW",
            })

        # Intact en premier, puis du plus proche au plus loin
        intact  = sorted([x for x in result if not x["swept"]],
                         key=lambda x: abs(x["price"] - current_price))
        swept_l = sorted([x for x in result if x["swept"]],
                         key=lambda x: abs(x["price"] - current_price))
        return (intact + swept_l)[:6]

    # ─────────────────────────────────────────────────────────────
    # 5. DOL Directionnel
    # Bible §4.1 — Draw On Liquidity, priorité EQH SMOOTH > PDH > PWH > BSL MAX
    # ─────────────────────────────────────────────────────────────

    def _find_dol(
        self,
        current_price: float,
        eq_levels: list,
        erl: dict,
        temporal: dict,
        direction: str
    ) -> dict:
        candidates = []

        if direction == "BULL":
            for e in eq_levels:
                if e["price"] > current_price and not e["swept"]:
                    prio = 1 if e["quality"] == "SMOOTH" else 2
                    candidates.append({"name": f"EQH_{e['quality']}", "price": e["price"],
                                       "type": "BSL", "priority": prio})

            for key, prio in [("PDH", 3), ("PWH", 4), ("PMH", 5)]:
                lvl = temporal.get(key, {})
                if lvl.get("status") == "INTACT" and lvl.get("price", 0) > current_price:
                    candidates.append({"name": key, "price": lvl["price"],
                                       "type": "BSL", "priority": prio})

            if not erl.get("high_swept") and erl.get("high", 0) > current_price:
                candidates.append({"name": "BSL_MAX", "price": erl["high"],
                                   "type": "BSL", "priority": 6})

            fallback_price = erl.get("high", current_price)
            fallback = {"name": "N/A", "price": round(fallback_price, 6),
                        "type": "BSL", "dist_pips": 0, "priority": 99}

        else:  # BEAR
            for e in eq_levels:
                if e["price"] < current_price and not e["swept"]:
                    prio = 1 if e["quality"] == "SMOOTH" else 2
                    candidates.append({"name": f"EQL_{e['quality']}", "price": e["price"],
                                       "type": "SSL", "priority": prio})

            for key, prio in [("PDL", 3), ("PWL", 4), ("PML", 5)]:
                lvl = temporal.get(key, {})
                if lvl.get("status") == "INTACT" and lvl.get("price", 0) < current_price:
                    candidates.append({"name": key, "price": lvl["price"],
                                       "type": "SSL", "priority": prio})

            if not erl.get("low_swept") and erl.get("low", 0) < current_price:
                candidates.append({"name": "SSL_MIN", "price": erl["low"],
                                   "type": "SSL", "priority": 6})

            fallback_price = erl.get("low", current_price)
            fallback = {"name": "N/A", "price": round(fallback_price, 6),
                        "type": "SSL", "dist_pips": 0, "priority": 99}

        if not candidates:
            return fallback

        candidates.sort(key=lambda x: (x["priority"], abs(x["price"] - current_price)))
        best = candidates[0]
        best["dist_pips"] = round(abs(best["price"] - current_price) / self._pip_size, 1)
        best["price"]     = round(best["price"], 6)
        best.pop("priority", None)
        return best

    # ─────────────────────────────────────────────────────────────
    # 6. Anti-Inducement — Sweep ERL avant MSS
    # Bible §18.2 — MSS valide seulement si sweep ERL préalable confirmé
    # ─────────────────────────────────────────────────────────────

    def _check_anti_inducement(
        self,
        mss_events: list,
        swings: list,
        erl: dict,
    ) -> dict:
        if not mss_events:
            return {
                "status":        "NO_MSS",
                "mss_type":      "NONE",
                "message":       "Aucun MSS récent — pas d'entrée possible",
                "score_penalty": 0,
            }

        erl_high  = erl.get("high", 0)
        erl_low   = erl.get("low",  0)
        erl_range = (erl_high - erl_low) if erl_high != erl_low else 1

        last_mss  = mss_events[-1]
        mss_type  = last_mss.get("type", "")
        bos_idx   = last_mss.get("bos_index", 0)

        swing_highs = [s for s in swings if s["type"] == "swing_high" and s["index"] <= bos_idx]
        swing_lows  = [s for s in swings if s["type"] == "swing_low"  and s["index"] <= bos_idx]

        confirmed = False

        if "bullish" in mss_type and swing_lows:
            swl_price = swing_lows[-1]["price"]
            confirmed = abs(swl_price - erl_low) / erl_range < self.ANTI_INDUCEMENT_PCT

        elif "bearish" in mss_type and swing_highs:
            swh_price = swing_highs[-1]["price"]
            confirmed = abs(swh_price - erl_high) / erl_range < self.ANTI_INDUCEMENT_PCT

        if confirmed:
            return {
                "status":        "VALIDATED",
                "mss_type":      mss_type,
                "message":       "Sweep ERL confirmé avant MSS — entrée valide ✅",
                "score_penalty": 0,
            }
        else:
            return {
                "status":        "INDUCEMENT_RISK",
                "mss_type":      mss_type,
                "message":       "MSS sans sweep ERL préalable — risque inducement ⚠️",
                "score_penalty": -15,
            }

    # ─────────────────────────────────────────────────────────────
    # 7. LRLR / HRLR
    # Bible ICT — compte les FVG entre prix et DOL
    # ─────────────────────────────────────────────────────────────

    def _compute_lrlr_hrlr(
        self,
        current_price: float,
        dol_bull: dict,
        dol_bear: dict,
        fvgs: list,
    ) -> dict:
        bull_target = dol_bull.get("price", current_price)
        bear_target = dol_bear.get("price", current_price)

        bull_obs = self._count_fvg_obstacles(fvgs, current_price, bull_target)
        bear_obs = self._count_fvg_obstacles(fvgs, current_price, bear_target)

        def _build(obstacles, target):
            t = "LRLR" if obstacles <= self.LRLR_MAX_OBSTACLES else "HRLR"
            icon = "✅" if t == "LRLR" else "⚠️"
            obs_str = f"{obstacles} obstacle{'s' if obstacles != 1 else ''}"
            return {
                "type":      t,
                "obstacles": obstacles,
                "target":    round(target, 6),
                "label":     f"{t} {icon} vers {round(target, 6)} ({obs_str})",
            }

        return {
            "bull": _build(bull_obs, bull_target),
            "bear": _build(bear_obs, bear_target),
        }

    def _count_fvg_obstacles(
        self, fvgs: list, price_from: float, price_to: float
    ) -> int:
        if price_from == price_to:
            return 0
        lo, hi = min(price_from, price_to), max(price_from, price_to)
        count  = 0
        for fvg in fvgs:
            if fvg.get("status") not in ("open", "partially_filled"):
                continue
            top    = fvg.get("top", 0)
            bottom = fvg.get("bottom", 0)
            ce     = fvg.get("midpoint", (top + bottom) / 2)
            if lo <= ce <= hi:
                count += 1
        return count

    # ─────────────────────────────────────────────────────────────
    # 8. CBDR — Central Bank Dealers Range
    # Bible §5 — range 14h-20h EST, explosif si < 40 pips
    # ─────────────────────────────────────────────────────────────

    def _compute_cbdr(self, df: pd.DataFrame) -> dict:
        empty = {
            "cbdr_high": 0, "cbdr_low": 0,
            "cbdr_range_pips": 0, "cbdr_explosive": False,
            "projections_bull": {}, "projections_bear": {},
            "label": "CBDR non calculé",
        }

        try:
            # Préparer l'index datetime
            work_df = df.copy()
            if "time" in work_df.columns and not hasattr(work_df.index, "hour"):
                work_df = work_df.set_index("time")

            if not hasattr(work_df.index, "hour"):
                # Fallback : 12 dernières bougies ≈ session 14h-20h
                window = work_df.tail(12)
                cbdr_h = float(window["high"].max())
                cbdr_l = float(window["low"].min())
            else:
                import pytz
                ny_tz = pytz.timezone("America/New_York")

                if work_df.index.tzinfo is None:
                    work_df.index = work_df.index.tz_localize("UTC").tz_convert(ny_tz)
                else:
                    work_df.index = work_df.index.tz_convert(ny_tz)

                mask = (work_df.index.hour >= 14) & (work_df.index.hour < 20)
                cbdr_data = work_df[mask]

                if len(cbdr_data) == 0:
                    window = work_df.tail(12)
                    cbdr_h = float(window["high"].max())
                    cbdr_l = float(window["low"].min())
                else:
                    last_date = cbdr_data.index[-1].date()
                    window    = cbdr_data[cbdr_data.index.date == last_date]
                    cbdr_h    = float(window["high"].max())
                    cbdr_l    = float(window["low"].min())

            cbdr_range      = cbdr_h - cbdr_l
            cbdr_range_pips = round(cbdr_range / self._pip_size, 1)
            explosive       = cbdr_range_pips < self.CBDR_EXPLOSIVE_PIPS

            return {
                "cbdr_high":        round(cbdr_h, 6),
                "cbdr_low":         round(cbdr_l, 6),
                "cbdr_range_pips":  cbdr_range_pips,
                "cbdr_explosive":   explosive,
                "projections_bull": {
                    "sd_1_0": round(cbdr_h + cbdr_range * 1.0, 6),
                    "sd_2_0": round(cbdr_h + cbdr_range * 2.0, 6),
                    "sd_2_5": round(cbdr_h + cbdr_range * 2.5, 6),
                },
                "projections_bear": {
                    "sd_1_0": round(cbdr_l - cbdr_range * 1.0, 6),
                    "sd_2_0": round(cbdr_l - cbdr_range * 2.0, 6),
                    "sd_2_5": round(cbdr_l - cbdr_range * 2.5, 6),
                },
                "label": f"{'💥 EXPLOSIF' if explosive else '📊 NORMAL'} — {cbdr_range_pips} pips",
            }

        except Exception as e:
            logger.warning(f"[LiqTracker] CBDR erreur {self.symbol}: {e}")
            return empty

    # ─────────────────────────────────────────────────────────────
    # 9. Boolean Sweep ERL
    # Variable d'état persistante : sweep ERL récent confirmé ?
    # ─────────────────────────────────────────────────────────────

    def _compute_boolean_sweep_erl(
        self, sweeps: list, erl: dict
    ) -> dict:
        """
        Vérifie si un des sweeps récents de structure.py correspond
        aux extrêmes ERL (tolérance 10 pips).

        ICT : Sweep ERL (externe) → chercher IRL (interne) = direction du trade.
        Si pas de sweep ERL récent → on attend la manipulation.
        """
        erl_high  = erl.get("high", 0)
        erl_low   = erl.get("low",  0)
        tolerance = self._pip_size * self.BOOL_SWEEP_TOLERANCE

        bsl_swept = False
        ssl_swept = False

        for sw in sweeps[-20:]:
            lvl = sw.get("swept_level", 0)
            if sw.get("type") == "buyside_sweep" and abs(lvl - erl_high) <= tolerance:
                bsl_swept = True
            elif sw.get("type") == "sellside_sweep" and abs(lvl - erl_low) <= tolerance:
                ssl_swept = True

        if bsl_swept:
            return {
                "value":          True,
                "direction":      "BSL",
                "message":        "BSL (ERL High) sweepé — chercher retour vers IRL ✅",
                "score_modifier": 0,
            }
        elif ssl_swept:
            return {
                "value":          True,
                "direction":      "SSL",
                "message":        "SSL (ERL Low) sweepé — chercher retour vers IRL ✅",
                "score_modifier": 0,
            }
        else:
            return {
                "value":          False,
                "direction":      "NONE",
                "message":        "Pas de sweep ERL récent — attendre manipulation ⚠️",
                "score_modifier": -15,
            }

    # ─────────────────────────────────────────────────────────────
    # SCORE PENALTY AGRÉGÉE
    # ─────────────────────────────────────────────────────────────

    def _compute_score_penalty(
        self,
        anti_inducement: dict,
        boolean_sweep_erl: dict,
        lrlr_hrlr: dict,
    ) -> int:
        """
        Calcule la pénalité totale à soustraire du score ICT dans orchestrator.py.

        Règles :
        - Anti-Inducement INDUCEMENT_RISK  → -15 pts
        - Boolean_Sweep_ERL False          → -15 pts
        - HRLR dans les deux sens          →  -5 pts (range bloqué)
        Max pénalité combinée : -35 pts (pour éviter d'écraser le score)
        """
        penalty = 0
        penalty += anti_inducement.get("score_penalty", 0)
        penalty += boolean_sweep_erl.get("score_modifier", 0)

        bull_hrlr = lrlr_hrlr.get("bull", {}).get("type") == "HRLR"
        bear_hrlr = lrlr_hrlr.get("bear", {}).get("type") == "HRLR"
        if bull_hrlr and bear_hrlr:
            penalty -= 5

        return max(penalty, -35)

    # ─────────────────────────────────────────────────────────────
    # UTILITAIRES
    # ─────────────────────────────────────────────────────────────

    def _is_swept(self, df: pd.DataFrame, level: float, direction: str) -> bool:
        """
        BSL sweepé : High >= level ET Close < level
        SSL sweepé : Low  <= level ET Close > level
        Scan les N dernières bougies (SWEEP_SCAN_WINDOW).
        """
        scan = df.tail(self.SWEEP_SCAN_WINDOW)
        if direction == "BSL":
            return len(scan[(scan["high"] >= level * 0.9999) & (scan["close"] < level)]) > 0
        else:
            return len(scan[(scan["low"] <= level * 1.0001) & (scan["close"] > level)]) > 0

    def _calc_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        if len(df) < period + 1:
            return float((df["high"] - df["low"]).mean())
        tr = pd.concat([
            df["high"] - df["low"],
            (df["high"] - df["close"].shift()).abs(),
            (df["low"]  - df["close"].shift()).abs(),
        ], axis=1).max(axis=1)
        return float(tr.tail(period).mean())

    def _get_pip_size(self, symbol: str) -> float:
        s = symbol.upper()
        if "JPY" in s:                                    return 0.01
        if "XAU" in s or "GOLD" in s:                    return 0.01
        if "XAG" in s:                                    return 0.001
        if "BTC" in s:                                    return 1.0
        if "ETH" in s:                                    return 0.1
        if "OIL" in s or "WTI" in s or "BRENT" in s:     return 0.01
        return 0.0001

    def _empty_report(self) -> dict:
        return {
            "symbol":            self.symbol,
            "error":             True,
            "erl":               {"high": 0, "low": 0, "high_swept": False, "low_swept": False,
                                  "high_status": "INTACT", "low_status": "INTACT"},
            "irl":               [],
            "eqh":               [],
            "eql":               [],
            "temporal_levels":   {},
            "dol_bull":          {"name": "N/A", "price": 0, "type": "BSL", "dist_pips": 0},
            "dol_bear":          {"name": "N/A", "price": 0, "type": "SSL", "dist_pips": 0},
            "anti_inducement":   {"status": "NO_MSS", "score_penalty": 0,
                                  "message": "Données insuffisantes"},
            "lrlr_hrlr":         {"bull": {"type": "LRLR", "obstacles": 0, "target": 0, "label": "N/A"},
                                  "bear": {"type": "LRLR", "obstacles": 0, "target": 0, "label": "N/A"}},
            "cbdr":              {"cbdr_high": 0, "cbdr_low": 0, "cbdr_range_pips": 0,
                                  "cbdr_explosive": False, "projections_bull": {},
                                  "projections_bear": {}, "label": "N/A"},
            "boolean_sweep_erl": {"value": False, "direction": "NONE",
                                  "score_modifier": -15,
                                  "message": "Données insuffisantes"},
            "score_penalty":     0,
            "timestamp":         datetime.now(timezone.utc).isoformat(),
        }