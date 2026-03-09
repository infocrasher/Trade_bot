"""
================================================================
  YFINANCE DATA PROVIDER — Données Réelles Sans MT5
================================================================
  Remplace MT5Connector quand MetaTrader5 n'est pas disponible.
  Utilise yfinance (Yahoo Finance) pour des données OHLCV réelles.
  
  Paires supportées : Forex (EURUSD=X), Or (GC=F), BTC (BTC-USD), 
                      Indices (DX-Y.NYB pour DXY)
  
  Limites yfinance :
  - M1/M5 : 7 derniers jours max
  - M15/H1 : 60 jours max
  - H4/D1/W1 : illimité
  - Délai : ~15-20 min de retard vs temps réel
  
  Installation : pip install yfinance
================================================================
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import numpy as np

logger = logging.getLogger("YFinanceProvider")
NYC_TZ = ZoneInfo("America/New_York")

# ================================================================
# MAPPING des symboles MT5 → yfinance
# ================================================================
SYMBOL_MAP = {
    # Forex (ajouter =X pour yfinance)
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "AUDUSD": "AUDUSD=X",
    "NZDUSD": "NZDUSD=X",
    "USDJPY": "USDJPY=X",
    "USDCAD": "USDCAD=X",
    "USDCHF": "USDCHF=X",
    "EURGBP": "EURGBP=X",
    "EURJPY": "EURJPY=X",
    "GBPJPY": "GBPJPY=X",
    
    # Métaux
    "XAUUSD": "GC=F",       # Gold Futures
    "XAGUSD": "SI=F",       # Silver Futures
    
    # Crypto
    "BTCUSD":  "BTC-USD",
    "BTCUSDT": "BTC-USD",
    "ETHUSD":  "ETH-USD",
    
    # Pétrole
    "USOIL": "CL=F",
    "UKOIL": "BZ=F",
    
    # Indices
    "DXY":    "DX-Y.NYB",   # Dollar Index
    "US500":  "ES=F",       # S&P 500 Futures
    "US30":   "YM=F",       # Dow Futures
    "NAS100": "NQ=F",       # Nasdaq Futures
}

# Timeframes yfinance
TF_MAP = {
    "M1":  {"interval": "1m",  "period": "5d"},
    "M5":  {"interval": "5m",  "period": "5d"},
    "M15": {"interval": "15m", "period": "60d"},
    "H1":  {"interval": "1h",  "period": "60d"},
    "H4":  {"interval": "1h",  "period": "60d"},   # yfinance n'a pas H4 natif → on resample
    "D1":  {"interval": "1d",  "period": "365d"},
    "W1":  {"interval": "1wk", "period": "2y"},
    "MN":  {"interval": "1mo", "period": "5y"},
    "MN1": {"interval": "1mo", "period": "5y"},
}


class YFinanceProvider:
    """
    Fournisseur de données de marché via yfinance.
    Interface compatible avec MT5Connector (même format de sortie).
    """

    def __init__(self):
        self.connected = False
        self.simulation_mode = False
        self._yf = None
        self._cache = {}          # {key: df}
        self._cache_ts = {}       # {key: timestamp}
        self._cache_ttl = 60      # 60s de cache (yfinance a du délai de toute façon)
        
        try:
            import yfinance as yf
            self._yf = yf
            self.connected = True
            logger.info("[OK] YFinance Provider initialisé — Données réelles actives.")
        except ImportError:
            logger.error("[ERREUR] yfinance non installé. pip install yfinance")
            self.simulation_mode = True

    def _get_yf_symbol(self, pair: str) -> str:
        """Convertit un symbole MT5 en symbole yfinance."""
        return SYMBOL_MAP.get(pair.upper(), pair + "=X")

    def _fetch_candles(self, pair: str, timeframe: str, count: int = 50) -> pd.DataFrame:
        """
        Récupère les bougies via yfinance avec cache.
        """
        import time as _time
        
        cache_key = f"{pair}_{timeframe}"
        now_ts = _time.time()
        
        # Cache
        if (cache_key in self._cache and 
                now_ts - self._cache_ts.get(cache_key, 0) < self._cache_ttl):
            df = self._cache[cache_key]
            return df.tail(count) if len(df) > count else df
        
        yf_symbol = self._get_yf_symbol(pair)
        tf_config = TF_MAP.get(timeframe.upper(), TF_MAP["H1"])
        
        try:
            ticker = self._yf.Ticker(yf_symbol)
            df = ticker.history(
                period=tf_config["period"],
                interval=tf_config["interval"],
                auto_adjust=True,
            )
            
            if df.empty:
                logger.warning(f"[YF] Pas de données pour {yf_symbol} ({timeframe})")
                return pd.DataFrame()
            
            # Renommer les colonnes pour compatibilité
            df = df.rename(columns={
                "Open": "open", "High": "high", "Low": "low",
                "Close": "close", "Volume": "tick_volume"
            })
            
            # Garder seulement les colonnes utiles
            df = df[["open", "high", "low", "close", "tick_volume"]].copy()
            df["time"] = df.index
            df = df.reset_index(drop=True)
            
            # Arrondir
            decimals = 2 if pair.upper() in ("XAUUSD", "XAGUSD", "USOIL", "UKOIL") else 5
            if pair.upper() in ("BTCUSD", "BTCUSDT", "ETHUSD"):
                decimals = 2
            if "JPY" in pair.upper():
                decimals = 3
                
            for col in ["open", "high", "low", "close"]:
                df[col] = df[col].round(decimals)
            
            # Resample H4 si nécessaire
            if timeframe.upper() == "H4":
                df = self._resample_h4(df)
            
            # Cache
            self._cache[cache_key] = df
            self._cache_ts[cache_key] = now_ts
            
            return df.tail(count) if len(df) > count else df
            
        except Exception as e:
            logger.error(f"[YF] Erreur {yf_symbol} ({timeframe}): {e}")
            return pd.DataFrame()

    def _resample_h4(self, df_h1: pd.DataFrame) -> pd.DataFrame:
        """Resample H1 → H4."""
        if df_h1.empty:
            return df_h1
        
        df = df_h1.copy()
        # S'assurer que la colonne time est bien un DatetimeIndex (tz-naïf)
        df["time"] = pd.to_datetime(df["time"]).dt.tz_localize(None)
        df = df.set_index("time")
        
        resampled = df.resample("4h").agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "tick_volume": "sum"
        }).dropna()
        
        resampled["time"] = resampled.index
        return resampled.reset_index(drop=True)

    def _candles_to_list(self, df: pd.DataFrame) -> list[dict]:
        """Convertit un DataFrame en list de dicts (format MT5Connector)."""
        if df.empty:
            return []
        
        records = []
        for _, row in df.iterrows():
            t = row["time"]
            if isinstance(t, pd.Timestamp):
                t_str = t.strftime("%Y-%m-%d %H:%M")
            else:
                t_str = str(t)
            
            records.append({
                "time": t_str,
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": int(row.get("tick_volume", 0)),
            })
        return records

    # ================================================================
    # Interface compatible MT5Connector
    # ================================================================
    def get_market_data(self, pair: str) -> dict:
        """
        Retourne les données de marché au même format que MT5Connector.
        """
        if self.simulation_mode:
            return {"status": "ERROR", "message": "yfinance non installé", "pair": pair}
        
        ny_now = datetime.now(NYC_TZ)
        
        # Récupérer toutes les timeframes (Minimum ~100 bougies pour StructureAgent)
        df_d1  = self._fetch_candles(pair, "D1",  200)
        df_h4  = self._fetch_candles(pair, "H4",  200)
        df_h1  = self._fetch_candles(pair, "H1",  200)
        df_m15 = self._fetch_candles(pair, "M15", 150)
        df_m5  = self._fetch_candles(pair, "M5",  100)
        df_w1  = self._fetch_candles(pair, "W1",  100)
        df_mn  = self._fetch_candles(pair, "MN",  60)
        
        # Prix actuel = dernier close M5 (ou H1 si M5 vide)
        current_price = 0
        for df in [df_m5, df_h1, df_d1]:
            if not df.empty:
                current_price = float(df.iloc[-1]["close"])
                break
        
        # PDH / PDL
        prev_day_high, prev_day_low = 0.0, 0.0
        if len(df_d1) >= 2:
            prev_day_high = float(df_d1.iloc[-2]["high"])
            prev_day_low  = float(df_d1.iloc[-2]["low"])
        
        # Daily high/low (aujourd'hui)
        daily_high, daily_low = 0.0, 0.0
        if not df_d1.empty:
            daily_high = float(df_d1.iloc[-1]["high"])
            daily_low  = float(df_d1.iloc[-1]["low"])
        
        # PWH / PWL
        prev_week_high, prev_week_low = 0.0, 0.0
        if len(df_w1) >= 2:
            prev_week_high = float(df_w1.iloc[-2]["high"])
            prev_week_low  = float(df_w1.iloc[-2]["low"])
        
        # Midnight Open (approx: open de la bougie D1 du jour)
        midnight_open = 0.0
        if not df_d1.empty:
            midnight_open = float(df_d1.iloc[-1]["open"])
        
        # DXY (essayer de récupérer)
        dxy_price = 0.0
        try:
            dxy_df = self._fetch_candles("DXY", "D1", 1)
            if not dxy_df.empty:
                dxy_price = float(dxy_df.iloc[-1]["close"])
        except:
            pass
        
        return {
            "pair": pair,
            "current_price": current_price,
            "ny_time": ny_now.strftime("%H:%M"),
            "date": ny_now.strftime("%Y-%m-%d"),
            "midnight_open": midnight_open,
            "daily_high": daily_high,
            "daily_low": daily_low,
            "prev_day_high": prev_day_high,
            "prev_day_low": prev_day_low,
            "prev_week_high": prev_week_high,
            "prev_week_low": prev_week_low,
            "dxy_price": dxy_price,
            "candles_m5":  self._candles_to_list(df_m5),
            "candles_m15": self._candles_to_list(df_m15),
            "candles_h1":  self._candles_to_list(df_h1),
            "candles_h4":  self._candles_to_list(df_h4),
            "candles_d1":  self._candles_to_list(df_d1),
            "candles_w1":  self._candles_to_list(df_w1),
            "candles_mn1": self._candles_to_list(df_mn),
            "source": "YFINANCE",
            "status": "OK",
        }

    def get_ohlcv(self, pair: str, timeframe: str, count: int = 50) -> list:
        """Alias compatible MT5Connector."""
        df = self._fetch_candles(pair, timeframe, count)
        return self._candles_to_list(df)

    def test_connection(self) -> bool:
        """Teste la connexion yfinance."""
        if self.simulation_mode:
            print("[ERREUR] yfinance non installé.")
            return False
        
        try:
            test = self._yf.Ticker("EURUSD=X")
            data = test.history(period="1d")
            if not data.empty:
                price = data["Close"].iloc[-1]
                print(f"[OK] YFinance connecté — EURUSD: {price:.5f}")
                return True
            else:
                print("[WARN] YFinance: pas de données pour EURUSD")
                return False
        except Exception as e:
            print(f"[ERREUR] YFinance test: {e}")
            return False

    def disconnect(self):
        """Rien à fermer pour yfinance."""
        self._cache.clear()
        logger.info("[YF] Cache vidé, provider fermé.")

    def get_pip_size(self, pair: str) -> float:
        """Retourne la taille d'un pip."""
        p = pair.upper()
        if "JPY" in p: return 0.01
        if p in ("XAUUSD",): return 0.10
        if p in ("BTCUSD", "BTCUSDT"): return 1.0
        if p in ("USOIL", "UKOIL"): return 0.01
        return 0.0001

    def get_tick_info(self, pair: str) -> tuple:
        """Retourne (tick_value, tick_size) approximatifs."""
        pip = self.get_pip_size(pair)
        return pip * 10, pip


# ================================================================
# FACTORY — Choisir automatiquement le bon provider
# ================================================================
def get_data_provider():
    """
    Retourne le meilleur data provider disponible :
    1. MT5Connector si MetaTrader5 est installé et connecté
    2. YFinanceProvider sinon
    """
    # Essayer MT5 d'abord
    try:
        import MetaTrader5
        from data.mt5_connector import MT5Connector
        mt5 = MT5Connector()
        if mt5.connected and not mt5.simulation_mode:
            logger.info("[PROVIDER] MetaTrader5 disponible — données live.")
            return mt5
    except ImportError:
        pass
    
    # Fallback yfinance
    provider = YFinanceProvider()
    if provider.connected:
        logger.info("[PROVIDER] YFinance actif — données réelles (délai ~15min).")
        return provider
    
    # Dernier recours : MT5 en simulation
    logger.warning("[PROVIDER] Aucun provider réel disponible — simulation activée.")
    try:
        from data.mt5_connector import MT5Connector
        return MT5Connector()
    except:
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    provider = YFinanceProvider()
    if provider.test_connection():
        print("\n--- Test EURUSD ---")
        data = provider.get_market_data("EURUSD")
        print(f"Prix: {data['current_price']}")
        print(f"PDH: {data['prev_day_high']} | PDL: {data['prev_day_low']}")
        print(f"Bougies H1: {len(data['candles_h1'])}")
        print(f"Bougies D1: {len(data['candles_d1'])}")
        print(f"Source: {data['source']}")
        
        print("\n--- Test XAUUSD ---")
        gold = provider.get_market_data("XAUUSD")
        print(f"Gold: {gold['current_price']}")
        
        print("\n--- Test BTCUSD ---")
        btc = provider.get_market_data("BTCUSD")
        print(f"BTC: {btc['current_price']}")
