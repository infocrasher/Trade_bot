"""
================================================================
  TRADE MANAGER — Gestionnaire des Trades Ouverts MT5
================================================================
  VERSION 2.0 — Avec Circuit Breaker + Corrélation + Paper Mode
  
  Nouvelles fonctionnalités vs v1 :
  - Circuit Breaker : Stop trading si perte journalière > X%
  - Garde Corrélation : Max N trades dans le même groupe de paires
  - Paper Trading : Log les trades simulés sans MT5
  - Telegram : Notifie chaque action sur trade
================================================================
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo  # ✅ Timezone correcte (Lacune #2)

from .performance_tracker import PerformanceTracker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

logger = logging.getLogger("TradeManager")

NYC_TZ = ZoneInfo("America/New_York")


# ================================================================
# CIRCUIT BREAKER
# ================================================================
class CircuitBreaker:
    """
    Interrupteur de sécurité automatique.
    Arrête le trading si les seuils de perte sont franchis.
    Compatible avec Freqtrade MaxDrawdown Protection.
    """

    def __init__(self):
        self._state_file = os.path.join(config.BASE_DIR, "data", "circuit_breaker_state.json")
        self._state = self._load_state()
        self._max_daily_loss = getattr(config, "CIRCUIT_BREAKER_MAX_DAILY_LOSS_PCT", 3.0)
        self._max_trades     = getattr(config, "CIRCUIT_BREAKER_MAX_TRADES_PER_DAY", 5)
        self._cooldown_hours = getattr(config, "CIRCUIT_BREAKER_COOLDOWN_HOURS", 4)
        self._max_sl_streak  = getattr(config, "CIRCUIT_BREAKER_MAX_STOPLOSS_COUNT", 3)

    def _load_state(self) -> dict:
        if os.path.exists(self._state_file):
            try:
                with open(self._state_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"[CB] Erreur chargement state : {e}")
        return {
            "triggered": False,
            "triggered_at": None,
            "reason": "",
            "trades_today": 0,
            "sl_streak": 0,
            "last_reset": datetime.now().strftime("%Y-%m-%d"),
        }

    def _save_state(self):
        os.makedirs(os.path.dirname(self._state_file), exist_ok=True)
        with open(self._state_file, "w") as f:
            json.dump(self._state, f, indent=2)

    def _reset_daily_if_needed(self):
        today = datetime.now().strftime("%Y-%m-%d")
        if self._state.get("last_reset") != today:
            self._state["trades_today"] = 0
            self._state["sl_streak"] = 0
            self._state["last_reset"] = today
            # Réinitialiser le circuit breaker au début d'une nouvelle journée
            if self._state["triggered"]:
                logger.info("[CB] Nouvelle journée — Circuit breaker réinitialisé.")
                self._state["triggered"] = False
                self._state["triggered_at"] = None
                self._state["reason"] = ""
            self._save_state()

    def is_trading_allowed(self, daily_pnl_pct: float = 0.0) -> tuple[bool, str]:
        """
        Retourne (True, "") si le trading est autorisé.
        Retourne (False, raison) si le circuit breaker est déclenché.
        """
        self._reset_daily_if_needed()

        # 1. Circuit déjà déclenché → Vérifier cooldown
        if self._state["triggered"]:
            triggered_at = datetime.fromisoformat(self._state["triggered_at"])
            cooldown_end = triggered_at + timedelta(hours=self._cooldown_hours)
            if datetime.now() < cooldown_end:
                remaining = int((cooldown_end - datetime.now()).total_seconds() / 60)
                return False, f"Circuit Breaker actif — {remaining} min restantes ({self._state['reason']})"
            else:
                logger.info("[CB] Cooldown terminé — Circuit breaker levé.")
                self._state["triggered"] = False
                self._save_state()

        # 2. Vérifier perte journalière
        if daily_pnl_pct <= -self._max_daily_loss:
            return self._trigger(f"Perte journalière {daily_pnl_pct:.1f}% ≥ seuil {self._max_daily_loss}%")

        # 3. Vérifier nombre de trades/jour
        if self._state["trades_today"] >= self._max_trades:
            return self._trigger(f"Max trades/jour atteint ({self._max_trades})")

        # 4. Vérifier streak de SL consécutifs
        if self._state["sl_streak"] >= self._max_sl_streak:
            return self._trigger(f"{self._max_sl_streak} SL consécutifs — Pause recommandée")

        return True, ""

    def _trigger(self, reason: str) -> tuple[bool, str]:
        """Déclenche le circuit breaker."""
        self._state["triggered"] = True
        self._state["triggered_at"] = datetime.now().isoformat()
        self._state["reason"] = reason
        self._save_state()
        logger.critical(f"🚨 [CIRCUIT BREAKER] {reason}")
        try:
            from notifications.telegram_notifier import get_notifier
            get_notifier().alert_circuit_breaker(0.0, reason)
        except Exception as e:
            logger.warning(f"[CB] Erreur de notification Telegram : {e}")
        return False, reason

    def record_trade(self, is_win: bool):
        """Enregistre le résultat d'un trade fermé."""
        self._reset_daily_if_needed()
        if is_win:
            self._state["sl_streak"] = 0
        else:
            self._state["sl_streak"] += 1
        self._save_state()

    def record_trade_opened(self):
        """Incrémente le compteur de trades du jour à l'ouverture."""
        self._reset_daily_if_needed()
        self._state["trades_today"] += 1
        self._save_state()

    def reset(self):
        """Réinitialise manuellement le circuit breaker."""
        self._state["triggered"] = False
        self._state["triggered_at"] = None
        self._state["reason"] = ""
        self._state["trades_today"] = 0
        self._state["sl_streak"] = 0
        self._save_state()
        logger.info("[CB] Réinitialisation manuelle effectuée.")

    def update_config(self, daily_loss_pct=None, max_trades=None, sl_streak=None):
        """Met à jour les seuils de sécurité."""
        if daily_loss_pct is not None: self._max_daily_loss = float(daily_loss_pct)
        if max_trades is not None:     self._max_trades = int(max_trades)
        if sl_streak is not None:      self._max_sl_streak = int(sl_streak)
        logger.info(f"[CB] Paramètres mis à jour : Loss {self._max_daily_loss}%, Trades {self._max_trades}, SL Streak {self._max_sl_streak}")

    def get_status(self) -> dict:
        """Retourne le statut complet du circuit breaker."""
        self._reset_daily_if_needed()
        return {
            "active": self._state["triggered"],
            "reason": self._state.get("reason", ""),
            "trades_today": self._state["trades_today"],
            "sl_streak": self._state["sl_streak"],
            "max_daily_loss_pct": self._max_daily_loss,
            "max_trades": self._max_trades,
            "max_sl_streak": self._max_sl_streak
        }


# ================================================================
# CORRÉLATION DE PAIRES
# ================================================================
class CorrelationGuard:
    """
    Empêche l'ouverture de trop de trades corrélés simultanément.
    Évite la surexposition à une devise (ex: trop USD Short).
    """

    def __init__(self):
        self._groups = getattr(config, "CORRELATION_GROUPS", [
            ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD"],
            ["USDCHF", "USDJPY", "USDCAD"],
            ["XAUUSD"],
        ])
        self._max = getattr(config, "MAX_CORRELATED_TRADES", 2)

    def _get_group(self, pair: str) -> list | None:
        for g in self._groups:
            if pair in g:
                return g
        return None

    def can_open_trade(self, pair: str, direction: str, open_positions: list[dict]) -> tuple[bool, str]:
        """
        Vérifie si on peut ouvrir un trade sur `pair` dans `direction`.
        Returns (True, "") ou (False, raison).
        """
        group = self._get_group(pair)
        if not group:
            return True, ""  # Paire hors groupe → pas de restriction

        # Compter les trades dans le même groupe et même direction
        count = sum(
            1 for p in open_positions
            if p["pair"] in group and p["direction"] == direction
        )

        if count >= self._max:
            same_pairs = [p["pair"] for p in open_positions if p["pair"] in group and p["direction"] == direction]
            return False, (
                f"Corrélation max atteinte ({count}/{self._max}) "
                f"dans le groupe {group} direction {direction}: {same_pairs}"
            )
        return True, ""

    def get_exposure_summary(self, open_positions: list[dict]) -> str:
        """Résumé de l'exposition par groupe de paires."""
        lines = ["=== EXPOSITION CORRÉLATION ==="]
        for group in self._groups:
            longs  = [p["pair"] for p in open_positions if p["pair"] in group and p["direction"] == "ACHAT"]
            shorts = [p["pair"] for p in open_positions if p["pair"] in group and p["direction"] == "VENTE"]
            if longs or shorts:
                lines.append(f"  {group}: LONG={longs} VENTE={shorts}")
        return "\n".join(lines) if len(lines) > 1 else "Aucune exposition corrélée."


# ================================================================
# TRADE MANAGER PRINCIPAL
# ================================================================
class TradeManager:
    """
    Analyse les positions MT5 ouvertes et fournit le contexte
    pour les décisions de gestion (Be / TP partiel / Close).
    VERSION 2.0 : + Circuit Breaker + Corrélation + Paper Trading.
    """

    def __init__(self):
        self.circuit_breaker   = CircuitBreaker()
        self.correlation_guard = CorrelationGuard()
        self.performance       = PerformanceTracker()
        self._mt5_available = False
        try:
            import MetaTrader5 as mt5
            self._mt5 = mt5
            self._mt5_available = True
        except ImportError:
            logger.warning("[WARN] MetaTrader5 non disponible — mode simulation.")
            self._mt5 = None

    # -------------------------------------------------------
    # Vérification de sécurité AVANT chaque trade
    # -------------------------------------------------------
    def pre_trade_check(self, pair: str, direction: str, daily_pnl_pct: float = 0.0) -> tuple[bool, str]:
        """
        À appeler AVANT d'ouvrir un trade.
        Vérifie Circuit Breaker + Corrélation + Paper Mode.
        Returns (True, "") si OK, (False, raison) si refusé.
        """
        # 1. Paper Trading actif
        if getattr(config, "PAPER_TRADING", False):
            logger.info(f"[PAPER] Trade {pair} {direction} — enregistré en paper mode.")
            return True, "PAPER_TRADE"

        # 2. Circuit Breaker
        allowed, reason = self.circuit_breaker.is_trading_allowed(daily_pnl_pct)
        if not allowed:
            logger.warning(f"[BLOCKED] Circuit Breaker: {reason}")
            return False, reason

        # 3. Corrélation
        open_pos = self.get_open_positions()
        corr_ok, corr_reason = self.correlation_guard.can_open_trade(pair, direction, open_pos)
        if not corr_ok:
            logger.warning(f"[BLOCKED] Corrélation: {corr_reason}")
            return False, corr_reason

        return True, ""

    # -------------------------------------------------------
    # EXÉCUTION RÉELLE MT5
    # -------------------------------------------------------
    def execute_trade(self, pair: str, direction: str, entry: float, sl: float, tp: float, comment: str = "") -> dict:
        """
        Ouvre un trade réel sur MT5.
        Gère le Lot Sizing automatique basé sur le risque (config.RISK_PER_TRADE_PCT).
        """
        if not self._mt5_available:
            return {"ok": False, "message": "MT5 non disponible"}

        # 0. Vérification Sécurité (Circuit Breaker + Corrélation)
        # On tente de récupérer le PnL du jour pour le circuit breaker
        daily_pnl = 0.0
        try:
            daily_pnl = self.performance.get_daily_pnl_pct()
        except Exception as e:
            logger.warning(f"[TRADE] Erreur recuperation PnL journalier: {e}")

        ok, reason = self.pre_trade_check(pair, direction, daily_pnl)
        if not ok:
            return {"ok": False, "message": f"Sécurité refusée : {reason}"}

        # 1. Calculer le volume (Lots)
        volume = self._calculate_lots(pair, entry, sl)
        if volume <= 0:
            return {"ok": False, "message": f"Volume calculé invalide: {volume}"}

        # 2. Décider du type d'ordre (Market vs Limit)
        tick = self._mt5.symbol_info_tick(pair)
        if not tick:
            return {"ok": False, "message": f"Impossible de récupérer le tick pour {pair}"}
            
        current_price = tick.ask if direction == "ACHAT" else tick.bid
        
        # Détection du type d'ordre
        # Si entry est 0 ou tres proche du prix actuel (ex: < 3 pips), on execute au marche.
        # Sinon on place un ordre Limit.
        info = self._mt5.symbol_info(pair)
        digits = info.digits if info else 5
        point = info.point if info else 0.00001
        
        is_limit = False
        if entry > 0:
            dist_points = abs(entry - current_price) / point
            # Si plus de 30 points (3 pips) de distance -> Ordre Limit
            if dist_points > 30:
                is_limit = True

        if is_limit:
            # Action PENDING (Limit)
            order_type = self._mt5.ORDER_TYPE_BUY_LIMIT if direction == "ACHAT" else self._mt5.ORDER_TYPE_SELL_LIMIT
            request = {
                "action": self._mt5.TRADE_ACTION_PENDING,
                "symbol": pair,
                "volume": float(volume),
                "type": order_type,
                "price": float(entry),
                "sl": float(sl),
                "tp": float(tp),
                "magic": 2026,
                "comment": f"LIMIT {comment[:25]}",
                "type_time": self._mt5.ORDER_TIME_GTC,
                "type_filling": self._mt5.ORDER_FILLING_IOC,
            }
        else:
            # Action DEAL (Market)
            order_type = self._mt5.ORDER_TYPE_BUY if direction == "ACHAT" else self._mt5.ORDER_TYPE_SELL
            request = {
                "action": self._mt5.TRADE_ACTION_DEAL,
                "symbol": pair,
                "volume": float(volume),
                "type": order_type,
                "price": current_price,
                "sl": float(sl),
                "tp": float(tp),
                "deviation": 20,
                "magic": 2026,
                "comment": comment[:31],
                "type_time": self._mt5.ORDER_TIME_GTC,
                "type_filling": self._mt5.ORDER_FILLING_IOC,
            }

        # 3. Envoyer
        if not self._ensure_connected():
            return {"ok": False, "message": "Connexion MT5 perdue"}

        result = self._mt5.order_send(request)
        if result is None:
            return {"ok": False, "message": "order_send a retourné None"}
        
        if result.retcode != self._mt5.TRADE_RETCODE_DONE:
            logger.error(f"[MT5] Échec exécution: {result.retcode} - {result.comment}")
            return {"ok": False, "message": f"Erreur MT5: {result.comment} (Code {result.retcode})", "retcode": result.retcode}

        order_type_str = "LIMIT" if is_limit else "MARKET"
        logger.info(f"✅ [MT5] {order_type_str} EXECUTE: {pair} {direction} {volume} lots. Ticket: {result.order}")
        
        # Enregistrement de l'ouverture pour le Circuit Breaker
        self.circuit_breaker.record_trade_opened()
        
        return {"ok": True, "ticket": result.order, "volume": volume, "type": order_type_str}

    def close_position(self, ticket: int) -> dict:
        """Ferme une position ouverte via son ticket."""
        if not self._ensure_connected():
            return {"ok": False, "message": "MT5 non disponible"}

        positions = self._mt5.positions_get(ticket=ticket)
        if not positions:
            return {"ok": False, "message": f"Position {ticket} introuvable"}

        pos = positions[0]
        symbol = pos.symbol
        tick = self._mt5.symbol_info_tick(symbol)
        
        request = {
            "action": self._mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": pos.volume,
            "type": self._mt5.ORDER_TYPE_SELL if pos.type == self._mt5.ORDER_TYPE_BUY else self._mt5.ORDER_TYPE_BUY,
            "position": ticket,
            "price": tick.bid if pos.type == self._mt5.ORDER_TYPE_BUY else tick.ask,
            "deviation": 20,
            "magic": 2026,
            "comment": "Bot Closure",
            "type_time": self._mt5.ORDER_TIME_GTC,
            "type_filling": self._mt5.ORDER_FILLING_IOC,
        }

        result = self._mt5.order_send(request)
        if result.retcode != self._mt5.TRADE_RETCODE_DONE:
            return {"ok": False, "message": f"Erreur fermeture: {result.comment}"}

        # 4. Enregistrement résultat pour le Circuit Breaker (Win/Loss)
        # On calcule si c'est un gain ou une perte pour le streak
        profit = pos.profit
        self.circuit_breaker.record_trade(is_win=(profit > 0))

        logger.info(f"🔒 [MT5] Position fermée: {ticket} ({symbol}) | P&L: {profit:.2f}")
        return {"ok": True}

    def _calculate_lots(self, pair: str, entry: float, sl: float) -> float:
        """
        Calcule le volume (lots) basé sur le risque % spécifié dans config.
        Formule: Risk_Money / (Distance_SL * LotValuePerPoint)
        """
        try:
            if not self._ensure_connected(): return 0.01
            
            account_info = self._mt5.account_info()
            if not account_info: return 0.01
            
            balance = account_info.balance
            risk_pct = getattr(config, "RISK_PER_TRADE_PCT", 1.0)
            risk_money = balance * (risk_pct / 100.0)
            
            if entry == 0 or sl == 0: return 0.01 # Fallback
            
            # Distance absolue
            distance = abs(entry - sl)
            if distance == 0: return 0.1
            
            symbol_info = self._mt5.symbol_info(pair)
            if not symbol_info: return 0.01
            
            # Formule simplifiée pour Forex (1 lot = 100 000 unités)
            # Pour l'Or (1 lot = 100 oz), etc.
            # Tick value est la valeur d'un tick de profit pour 1 lot
            tick_value = symbol_info.trade_tick_value
            tick_size = symbol_info.trade_tick_size
            
            if tick_value == 0 or tick_size == 0: return 0.01
            
            # Lots = Risque_en_Argent / (Distance_en_points * Valeur_du_point_par_lot)
            lots = risk_money / ( (distance / tick_size) * tick_value )
            
            # Arrondi par palier (0.01) et limites broker
            lots = round(lots, 2)
            lots = max(symbol_info.volume_min, min(symbol_info.volume_max, lots))
            
            return lots
        except Exception as e:
            logger.error(f"[LOTS] Erreur calcul: {e}")
            return 0.01

    # -------------------------------------------------------
    # Connexion MT5
    # -------------------------------------------------------
    def _ensure_connected(self) -> bool:
        if not self._mt5_available:
            return False
        if not self._mt5.initialize():
            logger.error("[ERR] Impossible de se connecter à MT5.")
            return False
        return True

    # -------------------------------------------------------
    # Récupération des positions ouvertes
    # -------------------------------------------------------
    def get_open_positions(self, pair: str = None) -> list[dict]:
        """Retourne la liste des positions ouvertes."""
        if not self._ensure_connected():
            return self._get_mock_positions(pair)

        positions = self._mt5.positions_get(symbol=pair) if pair else self._mt5.positions_get()

        if positions is None or len(positions) == 0:
            return []

        result = []
        for pos in positions:
            current_price = self._get_current_price(pos.symbol, pos.type)
            pnl_pips = self._calculate_pnl_pips(pos, current_price)
            result.append({
                "ticket": pos.ticket,
                "pair": pos.symbol,
                "direction": "ACHAT" if pos.type == 0 else "VENTE",
                "volume": pos.volume,
                "open_price": pos.price_open,
                "current_price": current_price,
                "sl": pos.sl,
                "tp": pos.tp,
                "pnl_pips": pnl_pips,
                "pnl_money": pos.profit,
                "open_time": datetime.fromtimestamp(pos.time).strftime("%Y-%m-%d %H:%M"),
                "comment": pos.comment,
            })
        return result

    def _get_current_price(self, symbol: str, direction: int) -> float:
        if not self._mt5_available:
            return 0.0
        tick = self._mt5.symbol_info_tick(symbol)
        if tick is None:
            return 0.0
        return tick.bid if direction == 0 else tick.ask

    def _calculate_pnl_pips(self, pos, current_price: float) -> float:
        # Simplification pips (1 point = 10^-4 ou 10^-2 pour JPY)
        info = self._mt5.symbol_info(pos.symbol)
        digits = info.digits if info else 5
        multiplier = 100 if digits <= 3 else 10000
        
        if pos.type == 0:
            return (current_price - pos.price_open) * multiplier
        else:
            return (pos.price_open - current_price) * multiplier

    # -------------------------------------------------------
    # Résumé formaté pour les Agents IA
    # -------------------------------------------------------
    def get_positions_summary_for_agent(self, pair: str = None) -> str:
        """Texte résumé des positions, prêt à être injecté dans le prompt."""
        positions = self.get_open_positions(pair)
        cb_status = self.circuit_breaker.get_status()

        lines = []

        # Statut Circuit Breaker
        if cb_status["active"]:
            lines.append(f"⛔ CIRCUIT BREAKER ACTIF: {cb_status['reason']}")
        else:
            lines.append(
                f"✅ Circuit Breaker: OK "
                f"({cb_status['trades_today']}/{cb_status['max_trades']} trades aujourd'hui, "
                f"{cb_status['sl_streak']} SL consécutifs)"
            )

        # Exposition corrélation
        lines.append(self.correlation_guard.get_exposure_summary(positions))
        lines.append("")

        if not positions:
            lines.append("TRADES OUVERTS : Aucune position ouverte actuellement.")
            return "\n".join(lines)

        lines.append("=== TRADES OUVERTS ===")
        for p in positions:
            status = self._assess_position_status(p)
            lines.append(
                f"  [{p['pair']}] {p['direction']} {p['volume']} lots | "
                f"Entrée: {p['open_price']} | Actuel: {p['current_price']} | "
                f"SL: {p['sl']} | TP: {p['tp']} | "
                f"P&L: {p['pnl_pips']:+.1f} pips ({p['pnl_money']:+.2f}€) | "
                f"Statut: {status}"
            )

        lines.append("")
        lines.append("INSTRUCTION : Pour chaque trade ouvert, décide :")
        lines.append("  HOLD    → Trade valide, conserver tel quel")
        lines.append("  MOVE_BE → Déplacer SL au Break-Even (trade > +15 pips en profit)")
        lines.append("  PARTIAL → Prendre profit partiel (25% à SD -1.0)")
        lines.append("  MODIFY  → Ajuster TP ou SL selon nouveau contexte")
        lines.append("  CLOSE   → Fermer le trade (setup invalidé par le marché)")

        return "\n".join(lines)

    def _assess_position_status(self, pos: dict) -> str:
        # FIX AUDIT-09 : Seuils adaptes par type d'actif (Or, BTC, Forex different)
        pair = pos.get("pair", "")
        pips = pos["pnl_pips"]
        if pair in ("XAUUSD", "XAGUSD"):
            high, mid, neg = 300, 100, -200   # Or / Argent
        elif pair in ("BTCUSD", "ETHUSD"):
            high, mid, neg = 500, 150, -300   # Crypto
        elif pair in ("USOIL", "UKOIL"):
            high, mid, neg = 50, 15, -30      # Petrole
        else:
            high, mid, neg = 30, 10, -25      # Forex standard
        if pips > high:
            return f"PROFIT +{pips:.0f} -> Envisager BE ou Partiel"
        elif pips > mid:
            return f"EN ZONE +{pips:.0f} -> Surveiller"
        elif pips > -10:
            return f"NEUTRE {pips:.0f} -> HOLD"
        elif pips > neg:
            return f"PERTE {pips:.0f} -> Verifier invalidation"
        else:
            return f"SL PROCHE {pips:.0f} -> Decision urgente"

    # -------------------------------------------------------
    # Mode simulation (sans MT5)
    # -------------------------------------------------------
    def _get_mock_positions(self, pair: str = None) -> list[dict]:
        mock = [
            {
                "ticket": 12345,
                "pair": "XAUUSD",
                "direction": "ACHAT",
                "volume": 0.1,
                "open_price": 2850.00,
                "current_price": 2890.50,
                "sl": 2820.00,
                "tp": 2950.00,
                "pnl_pips": 40.5,
                "pnl_money": 40.50,
                "open_time": "2026-02-25 10:15",
                "comment": "Silver Bullet NY AM",
            }
        ]
        if pair:
            return [p for p in mock if p["pair"] == pair]
        return mock


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    mgr = TradeManager()

    # Test Circuit Breaker
    ok, reason = mgr.pre_trade_check("EURUSD", "ACHAT", daily_pnl_pct=-1.5)
    print(f"Pre-trade check: {'OK' if ok else 'BLOCKED - ' + reason}")

    # Test positions
    print(mgr.get_positions_summary_for_agent())
