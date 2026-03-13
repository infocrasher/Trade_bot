"""
Telegram Notifier — Module indépendant pour l'envoi des alertes.
"""

import requests
import logging
from datetime import datetime
import config

log = logging.getLogger("TelegramNotifier")

class TelegramNotifier:
    def __init__(self):
        self.token = getattr(config, "TELEGRAM_BOT_TOKEN", "").strip()
        self.chat_id = getattr(config, "TELEGRAM_CHAT_ID", "").strip()
        self.enabled = bool(self.token) and bool(self.chat_id)

    def send_message(self, text: str) -> bool:
        """Envoie un message texte simple."""
        if not self.enabled:
            return False

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        try:
            resp = requests.post(url, json=payload, timeout=5)
            if resp.status_code == 200:
                return True
            else:
                log.error(f"[Telegram] Échec de l'envoi : {resp.status_code} - {resp.text}")
                return False
        except Exception as e:
            log.error(f"[Telegram] Erreur de communication : {e}")
            return False

    def notify_trade_opened(self, pair: str, direction: str, entry: float, sl: float, tp: float, score: int, reasons: list):
        """Notifie l'ouverture d'un trade ou la décision."""
        emoji = "🟢" if direction.upper() in ["BUY", "LONG"] else "🔴"
        
        msg = (
            f"<b>{emoji} SIGNAL {direction.upper()} - {pair}</b>\n\n"
            f"🎯 <b>Entry</b> : {entry}\n"
            f"🛡️ <b>Stop Loss</b> : {sl}\n"
            f"💰 <b>Take Profit</b> : {tp}\n\n"
            f"🏅 <b>Score</b> : {score}/100\n"
            f"📝 <b>Raisons</b> :\n"
        )
        
        for r in reasons[:3]:
            msg += f"- {r}\n"
            
        return self.send_message(msg)

# Instance globale si besoin
notifier = TelegramNotifier()
