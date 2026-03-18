import os
import json
import time
import requests
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

logger = logging.getLogger("ict_bot")

class NewsManager:
    """
    Gestionnaire d'annonces économiques via Finnhub API.
    Filtre les fenêtres de volatilité (±15 min) pour les news HIGH impact.
    """
    
    CACHE_FILE = "data/news_cache.json"
    CACHE_TTL = 6 * 3600  # 6 heures
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("FINNHUB_API_KEY", "")
        self.base_url = "https://finnhub.io/api/v1"
        self._news_data = []
        self._load_cache()

    def _load_cache(self):
        """Charge le cache JSON si valide, sinon fetch API."""
        if os.path.exists(self.CACHE_FILE):
            try:
                mtime = os.path.getmtime(self.CACHE_FILE)
                if time.time() - mtime < self.CACHE_TTL:
                    with open(self.CACHE_FILE, 'r') as f:
                        data = json.load(f)
                        self._news_data = data.get("economicCalendar", [])
                        logger.info(f"[NewsManager] Cache chargé : {len(self._news_data)} news")
                        return
            except Exception as e:
                logger.error(f"[NewsManager] Erreur lecture cache : {e}")

        self.refresh_news()

    def refresh_news(self):
        """Fetch le calendrier économique Finnhub pour les 7 prochains jours."""
        if not self.api_key:
            logger.warning("[NewsManager] Aucune FINNHUB_API_KEY. News désactivées.")
            return

        try:
            # On prend large (de hier à +7 jours)
            start_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            end_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
            
            params = {
                "token": self.api_key,
                "from": start_date,
                "to": end_date
            }
            
            r = requests.get(f"{self.base_url}/calendar/economic", params=params, timeout=15)
            r.raise_for_status()
            data = r.json()
            
            self._news_data = data.get("economicCalendar", [])
            
            # Sauvegarde cache
            os.makedirs("data", exist_ok=True)
            with open(self.CACHE_FILE, 'w') as f:
                json.dump(data, f)
                
            logger.info(f"[NewsManager] Calendrier mis à jour via Finnhub : {len(self._news_data)} news")
        except Exception as e:
            logger.error(f"[NewsManager] Erreur mise à jour API : {e}")

    def _get_pair_currencies(self, pair: str) -> List[str]:
        """Extrait les devises filtrables selon l'actif."""
        pair = pair.upper()
        # Crypto : pas de filtre selon directive
        if any(c in pair for c in ["BTC", "ETH"]):
            return []
        
        # Métaux : on filtre le USD (XAUUSD -> USD)
        if "XAU" in pair or "XAG" in pair:
            return ["USD"]
            
        # Forex : on filtre les deux devises (ex: EURUSD -> EUR, USD)
        if len(pair) == 6:
            return [pair[:3], pair[3:]]
        if "/" in pair:
            return pair.split("/")
            
        return []

    def is_news_window(self, pair: str, now_utc: Optional[datetime] = None) -> Dict:
        """
        Vérifie si on est dans une fenêtre de ±15 min d'une news HIGH impact.
        now_utc : datetime timezone-aware en UTC.
        """
        if now_utc is None:
            now_utc = datetime.now(timezone.utc)
            
        # S'assurer que now_utc est aware pour la comparaison
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=timezone.utc)

        currencies = self._get_pair_currencies(pair)
        if not currencies:
            return {"blocked": False, "reason": "", "news": []}

        relevant_high_news = []
        for n in self._news_data:
            # Check impact
            impact = n.get("impact", "").lower()
            if impact != "high":
                continue
                
            # Check currency match
            n_unit = n.get("unit", "").upper()
            if n_unit not in currencies:
                continue
                
            # Check time proximity (Finnhub time is usually UTC strings 'YYYY-MM-DD HH:MM:SS')
            n_time_str = n.get("time", "")
            if not n_time_str:
                continue
                
            try:
                # Format Finnhub : '2024-03-19 12:30:00' (UTC)
                n_time = datetime.strptime(n_time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                
                diff = abs((now_utc - n_time).total_seconds())
                if diff <= 15 * 60: # ±15 min
                    relevant_high_news.append(n)
            except Exception:
                continue

        if relevant_high_news:
            events = [n.get("event", "Unknown") for n in relevant_high_news]
            return {
                "blocked": True,
                "reason": f"HIGH IMPACT NEWS ({', '.join(events)}) dans la fenêtre ±15min",
                "news": relevant_high_news
            }
            
        return {"blocked": False, "reason": "", "news": []}

    def get_next_news(self, pair: str) -> Optional[Dict]:
        """Retourne la prochaine news HIGH impact pour les devises de la paire."""
        currencies = self._get_pair_currencies(pair)
        if not currencies:
            return None
            
        now = datetime.now(timezone.utc)
        upcoming = []
        
        for n in self._news_data:
            if n.get("impact", "").lower() != "high":
                continue
            if n.get("unit", "").upper() not in currencies:
                continue
            
            try:
                n_time = datetime.strptime(n.get("time", ""), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                if n_time > now:
                    upcoming.append((n_time, n))
            except:
                continue
                
        if upcoming:
            upcoming.sort(key=lambda x: x[0])
            return upcoming[0][1]
            
        return None
