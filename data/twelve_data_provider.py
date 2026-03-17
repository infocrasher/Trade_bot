"""
TwelveDataProvider — Connecteur Twelve Data API
Remplace YFinanceProvider avec la même interface que MT5Connector.

Interface publique (compatible dashboard.py / main.py) :
    provider.connected          → bool
    provider.simulation_mode    → bool
    provider.get_market_data(symbol) → dict
    provider.disconnect()

Clé API : variable d'env TWELVE_DATA_API_KEY ou config.TWELVE_DATA_API_KEY
Inscription gratuite : https://twelvedata.com (800 req/jour, 8 req/min)
"""

import os
import time
import requests
import pandas as pd
from datetime import datetime, timezone
from typing import Optional

# ─────────────────────────────────────────────────────────────────
# MAPPING SYMBOLES  YFinance/MT5 → Twelve Data
# ─────────────────────────────────────────────────────────────────
SYMBOL_MAP = {
    # Forex
    "EURUSD":  "EUR/USD",
    "GBPUSD":  "GBP/USD",
    "AUDUSD":  "AUD/USD",
    "NZDUSD":  "NZD/USD",
    "USDJPY":  "USD/JPY",
    "USDCAD":  "USD/CAD",
    "USDCHF":  "USD/CHF",
    "EURGBP":  "EUR/GBP",
    "EURJPY":  "EUR/JPY",
    "GBPJPY":  "GBP/JPY",
    "AUDJPY":  "AUD/JPY",
    # Métaux
    "XAUUSD":  "XAU/USD",
    "XAGUSD":  "XAG/USD",
    # Crypto
    "BTCUSD":  "BTC/USD",
    "ETHUSD":  "ETH/USD",
}

# ─────────────────────────────────────────────────────────────────
# MAPPING TIMEFRAMES
# ─────────────────────────────────────────────────────────────────
TF_MAP = {
    "M1":  "1min",
    "M5":  "5min",
    "M15": "15min",
    "M30": "30min",
    "H1":  "1h",
    "H4":  "4h",
    "D1":  "1day",
    "W1":  "1week",
    "MN":  "1month",
}

# Nombre de bougies demandées par timeframe
TF_BARS = {
    "M5":  288,   # ~1 jour de M5
    "H1":  200,
    "H4":  200,
    "D1":  200,
    "W1":  100,
    "MN":  60,
}

# Timeframes récupérés pour chaque appel get_market_data
REQUIRED_TFS = ["M5", "H1", "H4", "D1"]

# Clé dans le dict market_data retourné
TF_TO_KEY = {
    "M5":  "candles_m5",
    "H1":  "candles_h1",
    "H4":  "candles_h4",
    "D1":  "candles_d1",
    "W1":  "candles_w1",
    "MN":  "candles_mn1",
}

# ─────────────────────────────────────────────────────────────────
# RATE LIMITER  (8 req/min sur le plan gratuit)
# ─────────────────────────────────────────────────────────────────
class _RateLimiter:
    """Garantit qu'on ne dépasse pas max_per_min requêtes/minute."""

    def __init__(self, max_per_min: int = 7):
        self._max = max_per_min
        self._timestamps: list[float] = []

    def wait(self):
        now = time.time()
        # Nettoyer les timestamps de plus de 60s
        self._timestamps = [t for t in self._timestamps if now - t < 60]
        if len(self._timestamps) >= self._max:
            sleep_for = 60 - (now - self._timestamps[0]) + 0.1
            if sleep_for > 0:
                time.sleep(sleep_for)
        self._timestamps.append(time.time())


# ─────────────────────────────────────────────────────────────────
# PROVIDER PRINCIPAL
# ─────────────────────────────────────────────────────────────────
class TwelveDataProvider:
    """
    Connecteur Twelve Data — interface identique à YFinanceProvider / MT5Connector.
    Utilisé comme fallback quand MT5 n'est pas disponible (Mac, Linux sans MT5).
    """

    BASE_URL = "https://api.twelvedata.com"
    
    _cache: dict = {}
    
    CACHE_TTL = {
        "M5":  300,    # 5 min
        "H1":  3600,   # 1 heure
        "H4":  14400,  # 4 heures
        "D1":  86400,  # 24 heures
    }

    def __init__(self, api_keys: Optional[list] = None):
        
        # Initialisation du pool de clés API
        self._api_keys = api_keys
        if not self._api_keys:
            try:
                import config
                self._api_keys = getattr(config, "TWELVE_DATA_API_KEYS", [])
            except ImportError:
                pass
                
        # Fallback pour une clé unique (env) si aucune liste
        if not self._api_keys:
            fallback_key = os.environ.get("TWELVE_DATA_API_KEY", "")
            if fallback_key:
                self._api_keys = [fallback_key]
                
        if not self._api_keys:
            self._api_keys = []
            
        self._current_key_index = 0
        self._key_credits = {i: 0 for i in range(len(self._api_keys))}
        self._key_exhausted = {i: False for i in range(len(self._api_keys))}
        self._all_keys_exhausted = False
        
        self._daily_credits_limit = 780
        self._credit_reset_date = None

        self._rate_limiter = _RateLimiter(max_per_min=7)
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "TakeOptionBot/1.0"})

        # Test de connectivité
        self._connected = self._test_connection()
        self.simulation_mode = not self._connected

    # ─────────────────────────────────────────────────
    # PROPRIÉTÉS PUBLIQUES (interface MT5Connector)
    # ─────────────────────────────────────────────────
    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def api_key(self) -> str:
        if not self._api_keys or self._all_keys_exhausted:
            return ""
        return self._api_keys[self._current_key_index]
        
    def _rotate_key(self, logger=None):
        if not self._api_keys:
            return
            
        self._key_exhausted[self._current_key_index] = True
        
        for i in range(len(self._api_keys)):
            next_idx = (self._current_key_index + 1 + i) % len(self._api_keys)
            if not self._key_exhausted[next_idx]:
                self._current_key_index = next_idx
                msg = f"[TwelveData] 🔄 Rotation clé → clé #{next_idx + 1} ({self._key_credits[next_idx]} crédits utilisés)"
                if logger: logger.info(msg)
                else: print(msg)
                return
                
        msg = "[TwelveData] 🔴 Toutes les clés API sont épuisées pour aujourd'hui"
        if logger: logger.error(msg)
        else: print(msg)
        self._all_keys_exhausted = True

    # ─────────────────────────────────────────────────
    # TEST DE CONNEXION
    # ─────────────────────────────────────────────────
    def _test_connection(self) -> bool:
        if not self.api_key:
            print("[TwelveData] ⚠️  Aucune clé API — mode simulation activé")
            print("[TwelveData]    → Définir TWELVE_DATA_API_KEYS dans config.py")
            return False
        try:
            r = self._session.get(
                f"{self.BASE_URL}/api_usage",
                params={"apikey": self.api_key},
                timeout=10,
            )
            data = r.json()
            if "current_usage" in data:
                used  = data["current_usage"]
                limit = data.get("plan_limit", 800)
                print(f"[TwelveData] ✅ Connecté — {used}/{limit} requêtes utilisées aujourd'hui")
                return True
            else:
                print(f"[TwelveData] ❌ Clé API invalide : {data.get('message', data)}")
                return False
        except Exception as e:
            print(f"[TwelveData] ❌ Erreur connexion : {e}")
            return False

    # ─────────────────────────────────────────────────
    # RÉCUPÉRATION D'UN TIMEFRAME
    # ─────────────────────────────────────────────────
    def _fetch_candles(self, td_symbol: str, tf: str, n_bars: int) -> list[dict]:
        """
        Appelle l'endpoint /time_series de Twelve Data.
        Retourne une liste de dicts [{"time", "open", "high", "low", "close", "volume"}, ...]
        triée du plus ancien au plus récent.
        """
    def _fetch_candles(self, td_symbol: str, tf: str, n_bars: int) -> list[dict]:
        """
        Appelle l'endpoint /time_series de Twelve Data.
        Retourne une liste de dicts [{"time", "open", "high", "low", "close", "volume"}, ...]
        triée du plus ancien au plus récent.
        """
        td_interval = TF_MAP.get(tf)
        if not td_interval:
            return []

        # Interception directe vers le cache pour économiser _fetch_candles
        # (seulement si _rate_limiter n'est pas appelé)
        
        self._rate_limiter.wait()

        params = {
            "symbol":     td_symbol,
            "interval":   td_interval,
            "outputsize": min(n_bars, 5000),
            "apikey":     self.api_key,
            "order":      "ASC",   # plus ancien → plus récent
        }

        try:
            r = self._session.get(
                f"{self.BASE_URL}/time_series",
                params=params,
                timeout=15,
            )
            j = r.json()

            if j.get("status") == "error":
                msg = j.get("message", "Erreur inconnue")
                # Détection épuisement passif
                if "run out of api credits" in msg.lower() or "limit" in msg.lower():
                    import logging
                    logger = logging.getLogger("ict_bot")
                    logger.warning(f"[TwelveData] ⚠️ Clé #{self._current_key_index + 1} épuisée signalée par l'API")
                    self._rotate_key(logger)
                    # Relancer la requête avec la nouvelle clé si disponible (récursion simple)
                    if not self._all_keys_exhausted:
                        return self._fetch_candles(td_symbol, tf, n_bars)
                        
                # Silencieux pour les paires non supportées (ex: USOIL/UKOIL)
                elif "not found" not in msg.lower():
                    print(f"[TwelveData] ⚠️  {td_symbol} {tf}: {msg}")
                return []

            values = j.get("values", [])
            if not values:
                return []

            candles = []
            for v in values:
                candles.append({
                    "time":        v.get("datetime", ""),
                    "open":        float(v.get("open",   0)),
                    "high":        float(v.get("high",   0)),
                    "low":         float(v.get("low",    0)),
                    "close":       float(v.get("close",  0)),
                    "tick_volume": float(v.get("volume", 0)),
                    "volume":      float(v.get("volume", 0)),
                })
            return candles

        except requests.exceptions.Timeout:
            print(f"[TwelveData] ⏱️  Timeout {td_symbol} {tf}")
            return []
        except Exception as e:
            print(f"[TwelveData] ❌ Erreur {td_symbol} {tf}: {e}")
            return []

    # ─────────────────────────────────────────────────
    # PRIX COURANT
    # ─────────────────────────────────────────────────
    def _fetch_price(self, td_symbol: str) -> dict:
        """
        Récupère le dernier prix (bid/ask/close) via /price ou /quote.
        Retourne {"bid": float, "ask": float, "current_price": float}
        """
        self._rate_limiter.wait()
        try:
            r = self._session.get(
                f"{self.BASE_URL}/quote",
                params={"symbol": td_symbol, "apikey": self.api_key},
                timeout=10,
            )
            j = r.json()
            if j.get("status") == "error":
                return {"bid": 0, "ask": 0, "current_price": 0}

            close = float(j.get("close", 0))
            # Twelve Data ne fournit pas bid/ask sur le plan gratuit
            # On reconstruit un spread fictif minimal (0.5 pip pour FX)
            spread = close * 0.00005
            return {
                "bid":           round(close - spread, 6),
                "ask":           round(close + spread, 6),
                "current_price": close,
            }
        except Exception as e:
            print(f"[TwelveData] ❌ Prix {td_symbol}: {e}")
            return {"bid": 0, "ask": 0, "current_price": 0}

    # ─────────────────────────────────────────────────
    # MÉTHODE PRINCIPALE — Interface MT5Connector
    # ─────────────────────────────────────────────────
    def get_market_data(self, symbol: str) -> dict:
        """
        Retourne un dict compatible avec le format attendu par dashboard.py :
        {
            "status":        "OK" | "ERROR",
            "symbol":        str,
            "current_price": float,
            "bid":           float,
            "ask":           float,
            "candles_m5":    list[dict],
            "candles_h1":    list[dict],
            "candles_h4":    list[dict],
            "candles_d1":    list[dict],
            "candles_w1":    list[dict],   # vide si non requis
            "candles_mn1":   list[dict],   # vide si non requis
            "timestamp":     str,
        }
        """
        td_symbol = SYMBOL_MAP.get(symbol.upper())
        if not td_symbol:
            return {
                "status":  "ERROR",
                "message": f"Symbole {symbol} non mappé dans TwelveDataProvider",
                "symbol":  symbol,
            }

        if not self._connected:
            return self._simulation_data(symbol)

        market_data: dict = {
            "status":        "OK",
            "symbol":        symbol,
            "current_price": 0,
            "bid":           0,
            "ask":           0,
            "candles_m5":    [],
            "candles_h1":    [],
            "candles_h4":    [],
            "candles_d1":    [],
            "candles_w1":    [],
            "candles_mn1":   [],
            "timestamp":     datetime.now(timezone.utc).isoformat(),
        }

        # Récupérer les bougies pour chaque TF requis
        for tf in REQUIRED_TFS:
            n_bars  = TF_BARS.get(tf, 200)
            key     = TF_TO_KEY[tf]
            candles = self._fetch_candles(td_symbol, tf, n_bars)
            market_data[key] = candles

        # Prix courant depuis la dernière bougie H1 (économise 1 req)
        h1_candles = market_data.get("candles_h1", [])
        if h1_candles:
            last = h1_candles[-1]
            close = last.get("close", 0)
            spread = close * 0.00005
            market_data["current_price"] = close
            market_data["bid"]           = round(close - spread, 6)
            market_data["ask"]           = round(close + spread, 6)
        else:
            # Fallback : appel dédié au prix
            price_data = self._fetch_price(td_symbol)
            market_data.update(price_data)

        # Vérification finale : au moins H1 ou H4 doit avoir des données
        if not market_data["candles_h1"] and not market_data["candles_h4"]:
            return {
                "status":  "ERROR",
                "message": f"Aucune donnée reçue pour {symbol} ({td_symbol})",
                "symbol":  symbol,
            }

        return market_data

    # ─────────────────────────────────────────────────
    # MÉTHODE UTILITAIRE — Récupérer un seul TF (CACHE INTELLIGENT)
    # ─────────────────────────────────────────────────
    def get_ohlcv(self, symbol: str, timeframe: str, n_bars: int = 200) -> pd.DataFrame:
        """
        Interface simplifiée avec CACHE INTELLIGENT.
        Retourne un DataFrame pandas avec colonnes : time, open, high, low, close, volume, tick_volume
        """
        import logging
        logger = logging.getLogger("ict_bot")
        
        # Reset journalier
        today = datetime.utcnow().date()
        if self._credit_reset_date != today:
            self._credit_reset_date = today
            self._key_credits = {i: 0 for i in range(len(self._api_keys))}
            self._key_exhausted = {i: False for i in range(len(self._api_keys))}
            self._current_key_index = 0
            self._all_keys_exhausted = False
            logger.info(f"[TwelveData] 🌅 Reset journalier — {len(self._api_keys)} clés disponibles")

        cache_key = f"{symbol}_{timeframe}"

        # Hard stop si limite atteinte globalement
        if self._all_keys_exhausted:
            logger.warning(f"[TwelveData] 🔴 Toutes les clés épuisées ({len(self._api_keys)} clés) — retour cache ou None")
            if cache_key in self._cache:
                logger.info(f"[TwelveData] 📦 Cache expiré utilisé (urgence) pour {cache_key}")
                return self._cache[cache_key]["df"]
            return pd.DataFrame()

        # Vérifier cache valide
        ttl = self.CACHE_TTL.get(timeframe, 300)
        now = time.time()

        if cache_key in self._cache:
            age = now - self._cache[cache_key]["timestamp"]
            if age < ttl:
                return self._cache[cache_key]["df"]  # cache hit, 0 crédit

        # Rotation préventive si limite atteinte sur la clé actuelle
        if self._key_credits.get(self._current_key_index, 0) >= self._daily_credits_limit:
            self._rotate_key(logger)
            if self._all_keys_exhausted:
                if cache_key in self._cache:
                    return self._cache[cache_key]["df"]
                return pd.DataFrame()

        # Cache miss → appel API
        df = self._fetch_from_api(symbol, timeframe, n_bars)
        if df is not None and not df.empty:
            self._cache[cache_key] = {"df": df, "timestamp": now}
            self._key_credits[self._current_key_index] += 1
            logger.debug(f"[TwelveData] 📡 API call (Clé #{self._current_key_index + 1}) — {cache_key}")

        return df

    def _fetch_from_api(self, symbol: str, timeframe: str, n_bars: int) -> pd.DataFrame:
        """Logique originelle de get_ohlcv() encapsulée ici pour appel réel HTTP"""
        td_symbol = SYMBOL_MAP.get(symbol.upper())
        if not td_symbol:
            return pd.DataFrame()

        td_interval = TF_MAP.get(timeframe)
        if not td_interval:
            return pd.DataFrame()
            
        candles = self._fetch_candles(td_symbol, timeframe, n_bars)
        
        if not candles:
            return pd.DataFrame()

        df = pd.DataFrame(candles)
        df["time"] = pd.to_datetime(df["time"])
        df = df.sort_values("time").reset_index(drop=True)

        # Colonnes dérivées (compatibles candles_to_dataframe de dashboard.py)
        df["body"]       = (df["close"] - df["open"]).abs()
        df["range"]      = df["high"] - df["low"]
        df["body_ratio"] = df.apply(
            lambda r: r["body"] / r["range"] if r["range"] > 0 else 0, axis=1
        )
        df["upper_wick"] = df["high"] - df[["open", "close"]].max(axis=1)
        df["lower_wick"] = df[["open", "close"]].min(axis=1) - df["low"]

        return df

    # ─────────────────────────────────────────────────
    # STATUTS DU CRÉDIT
    # ─────────────────────────────────────────────────
    def get_credits_status(self) -> dict:
        """Retourne l'usage actuel des crédits pour la journée."""
        total_used = sum(self._key_credits.values()) if self._key_credits else 0
        total_limit = self._daily_credits_limit * len(self._api_keys) if self._api_keys else 0
        return {
            "current_key": self._current_key_index + 1 if self._api_keys else 0,
            "total_keys": len(self._api_keys) if self._api_keys else 0,
            "credits_per_key": self._key_credits,
            "exhausted_keys": self._key_exhausted,
            "total_used": total_used,
            "total_limit": total_limit,
            "remaining": total_limit - total_used,
        }

    # ─────────────────────────────────────────────────
    # MODE SIMULATION (pas de clé API)
    # ─────────────────────────────────────────────────
    def _simulation_data(self, symbol: str) -> dict:
        """Retourne un dict vide mais valide pour le mode simulation."""
        return {
            "status":        "OK",
            "symbol":        symbol,
            "current_price": 0,
            "bid":           0,
            "ask":           0,
            "candles_m5":    [],
            "candles_h1":    [],
            "candles_h4":    [],
            "candles_d1":    [],
            "candles_w1":    [],
            "candles_mn1":   [],
            "timestamp":     datetime.now(timezone.utc).isoformat(),
            "simulation":    True,
        }

    # ─────────────────────────────────────────────────
    # DÉCONNEXION (interface MT5Connector)
    # ─────────────────────────────────────────────────
    def disconnect(self):
        """Ferme la session HTTP proprement."""
        try:
            self._session.close()
        except Exception:
            pass
        self._connected = False
        print("[TwelveData] Déconnecté.")


# ─────────────────────────────────────────────────────────────────
# TEST RAPIDE (python data/twelve_data_provider.py)
# ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json

    provider = TwelveDataProvider()
    print(f"\nConnecté : {provider.connected}")
    print(f"Simulation : {provider.simulation_mode}")

    if provider.connected:
        print("\n--- Test get_market_data(EURUSD) ---")
        md = provider.get_market_data("EURUSD")
        print(f"Status        : {md['status']}")
        print(f"Prix courant  : {md['current_price']}")
        print(f"Bid/Ask       : {md['bid']} / {md['ask']}")
        print(f"Bougies M5    : {len(md['candles_m5'])} bougies")
        print(f"Bougies H1    : {len(md['candles_h1'])} bougies")
        print(f"Bougies H4    : {len(md['candles_h4'])} bougies")
        print(f"Bougies D1    : {len(md['candles_d1'])} bougies")
        if md["candles_h1"]:
            print(f"\nDernière H1   : {md['candles_h1'][-1]}")

        print("\n--- Test get_ohlcv(XAUUSD, H1, 10) ---")
        df = provider.get_ohlcv("XAUUSD", "H1", 10)
        print(df[["time", "open", "high", "low", "close"]].tail(5).to_string())

    provider.disconnect()