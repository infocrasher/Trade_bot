"""
================================================================
  PERFORMANCE TRACKER — Journal de Performance des Plans ICT
================================================================
  Enregistre les résultats réels de chaque plan.
  Calcule Win Rate, R:R moyen, Drawdown max par setup/paire.
  Génère un rapport hebdomadaire automatique.
================================================================
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from .mt5_connector import MT5Connector

logger = logging.getLogger("PerformanceTracker")


class PerformanceTracker:
    """
    Enregistre et analyse la performance des plans ICT.
    Fichier : data/journal/performance.json
    """

    def __init__(self):
        self.journal_dir = os.path.join(config.BASE_DIR, "data", "journal")
        os.makedirs(self.journal_dir, exist_ok=True)
        self.journal_path = os.path.join(self.journal_dir, "performance.json")
        self._data = self._load()
        logger.info(f"[OK] PerformanceTracker initialisé → {self.journal_path}")

    # -------------------------------------------------------
    # Chargement / Sauvegarde
    # -------------------------------------------------------
    def _load(self) -> dict:
        if not os.path.exists(self.journal_path):
            return {"trades": [], "stats": {}}
        try:
            with open(self.journal_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"trades": [], "stats": {}}

    def _save(self):
        with open(self.journal_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=4, ensure_ascii=False)

    # -------------------------------------------------------
    # Enregistrement d'un plan et de son résultat
    # -------------------------------------------------------

    def log_plan_outcome(
        self,
        pair: str,
        horizon: str,
        setup: str,
        direction: str,
        entry: float,
        sl: float,
        tp1: float,
        tp2: float,
        score: int,
        actual_result: str,
        actual_pips: float,
        actual_money: float = 0.0,
        plan_date: str = None,
    ):
        """Enregistre le résultat final d'un setup pris."""
        # ✅ FIX AUDIT-09 : Taille du pip dynamique depuis MT5
        connector = MT5Connector()
        pip_size = connector.get_pip_size(pair)
        sl_distance_pips = abs(entry - sl) / pip_size if sl != entry and pip_size > 0 else 1
        rr = round(actual_pips / sl_distance_pips, 2) if sl_distance_pips > 0 else 0

        entry_data = {
            "id": len(self._data["trades"]) + 1,
            "date": plan_date or datetime.now().strftime("%Y-%m-%d"),
            "time": datetime.now().strftime("%H:%M"),
            "pair": pair,
            "horizon": horizon,
            "setup": setup,
            "direction": direction,
            "entry": entry,
            "sl": sl,
            "tp1": tp1,
            "tp2": tp2,
            "score_ict": score,
            "result": actual_result,
            "pips": actual_pips,
            "money": actual_money,
            "rr_achieved": rr,
            "is_win": actual_pips > 0,
        }
        self._data["trades"].append(entry_data)
        self._recalculate_stats()
        self._save()
        logger.info(f"[JOURNAL] {pair} {setup} → {actual_result} ({actual_pips:+.1f} pips | {actual_money:+.2f}€ | R:R={rr})")
        return entry_data

    # -------------------------------------------------------
    # Calcul des statistiques
    # -------------------------------------------------------
    def _recalculate_stats(self):
        """Recalcule toutes les statistiques après chaque ajout."""
        trades = self._data["trades"]
        if not trades:
            return

        total = len(trades)
        wins = [t for t in trades if t["is_win"]]
        losses = [t for t in trades if not t["is_win"]]

        # Stats globales
        self._data["stats"]["global"] = {
            "total_trades": total,
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(len(wins) / total * 100, 1),
            "total_pips": round(sum(t["pips"] for t in trades), 1),
            "total_money": round(sum(t.get("money", 0) for t in trades), 2),
            "avg_win_pips": round(sum(t["pips"] for t in wins) / len(wins), 1) if wins else 0,
            "avg_loss_pips": round(sum(t["pips"] for t in losses) / len(losses), 1) if losses else 0,
            "max_drawdown_pips": self._calculate_max_drawdown(trades),
            "avg_rr": round(sum(t["rr_achieved"] for t in wins) / len(wins), 2) if wins else 0,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }

        # Stats par setup
        setups = {}
        for t in trades:
            s = t["setup"]
            if s not in setups:
                setups[s] = {"total": 0, "wins": 0, "pips": 0}
            setups[s]["total"] += 1
            if t["is_win"]:
                setups[s]["wins"] += 1
            setups[s]["pips"] += t["pips"]

        self._data["stats"]["by_setup"] = {
            s: {
                "win_rate": round(v["wins"] / v["total"] * 100, 1),
                "total_pips": round(v["pips"], 1),
                "total_trades": v["total"],
            }
            for s, v in setups.items()
        }

        # Stats par paire
        pairs = {}
        for t in trades:
            p = t["pair"]
            if p not in pairs:
                pairs[p] = {"total": 0, "wins": 0, "pips": 0}
            pairs[p]["total"] += 1
            if t["is_win"]:
                pairs[p]["wins"] += 1
            pairs[p]["pips"] += t["pips"]

        self._data["stats"]["by_pair"] = {
            p: {
                "win_rate": round(v["wins"] / v["total"] * 100, 1),
                "total_pips": round(v["pips"], 1),
                "total_trades": v["total"],
            }
            for p, v in pairs.items()
        }

    def _calculate_max_drawdown(self, trades: list) -> float:
        """Calcule le drawdown maximum en pips."""
        cumulative = 0
        peak = 0
        max_dd = 0
        for t in sorted(trades, key=lambda x: x["date"]):
            cumulative += t["pips"]
            if cumulative > peak:
                peak = cumulative
            dd = peak - cumulative
            if dd > max_dd:
                max_dd = dd
        return round(max_dd, 1)

    # -------------------------------------------------------
    # Rapports
    # -------------------------------------------------------
    def get_weekly_report(self) -> str:
        """Génère un rapport de performance de la semaine passée."""
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        recent = [t for t in self._data["trades"] if t["date"] >= week_ago]

        if not recent:
            return "Aucun trade enregistré cette semaine."

        wins = [t for t in recent if t["is_win"]]
        pips = sum(t["pips"] for t in recent)
        wr = len(wins) / len(recent) * 100

        lines = [
            "=== RAPPORT PERFORMANCE HEBDOMADAIRE ===",
            f"Période : {week_ago} → {datetime.now().strftime('%Y-%m-%d')}",
            f"Trades  : {len(recent)} | Wins: {len(wins)} | Losses: {len(recent)-len(wins)}",
            f"Win Rate: {wr:.1f}%",
            f"Total P&L: {pips:+.1f} pips",
            "",
            "Meilleur setup:",
        ]

        if self._data["stats"].get("by_setup"):
            best_setup = max(
                self._data["stats"]["by_setup"].items(),
                key=lambda x: x[1]["win_rate"]
            )
            lines.append(f"  {best_setup[0]} → {best_setup[1]['win_rate']}% WR ({best_setup[1]['total_trades']} trades)")

        return "\n".join(lines)

    def get_summary(self) -> dict:
        """Retourne un résumé des stats pour le dashboard."""
        return self._data.get("stats", {}).get("global", {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0,
            "total_pips": 0,
            "avg_win_pips": 0,
            "avg_loss_pips": 0,
            "max_drawdown_pips": 0,
            "avg_rr": 0
        })

    def get_daily_pnl_pct(self, capital: float = None) -> float:
        """
        Calcule la P&L journalière en % du capital.
        ✅ FIX AUDIT-05 : Tente d'abord de lire le vrai capital MT5 si disponible.
        """
        # Tenter de lire le vrai capital depuis MT5
        if capital is None:
            try:
                import MetaTrader5 as mt5
                if mt5.initialize():
                    info = mt5.account_info()
                    capital = info.balance if info else 10000.0
                else:
                    capital = 10000.0
            except Exception:
                capital = 10000.0

        today = datetime.now().strftime("%Y-%m-%d")
        today_trades = [t for t in self._data["trades"] if t["date"] == today]
        total_money_today = sum(t.get("money", 0) for t in today_trades)
        return (total_money_today / capital) * 100


if __name__ == "__main__":
    tracker = PerformanceTracker()
    tracker.log_plan_outcome(
        "XAUUSD", "scalp", "Silver Bullet NY AM", "ACHAT",
        2890.00, 2875.00, 2920.00, 2950.00, 85,
        "WIN_TP1", 30.0
    )
    print(tracker.get_weekly_report())
    print(f"P&L journalière: {tracker.get_daily_pnl_pct():.2f}%")
