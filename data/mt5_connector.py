"""
================================================================
  CONNECTEUR METATRADER 5 — Interface avec la plateforme
================================================================
  Récupère les données de marché en temps réel depuis MT5.
  Gère la connexion, les bougies, les niveaux clés.
================================================================
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import matplotlib.pyplot as plt
import pandas as pd

# Import MT5 (avec gestion d'erreur si non installé)
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    print("[ATTENTION] MetaTrader5 non installée. Mode simulation activé.")
    print("            Pour installer : pip install MetaTrader5")


class MT5Connector:
    """
    Interface avec MetaTrader 5.
    Fournit les données de marché aux agents.
    Si MT5 n'est pas disponible, utilise des données simulées pour test.
    """
    
    def __init__(self):
        self.connected = False
        self.simulation_mode = not MT5_AVAILABLE
        # Cache get_market_data() par paire (TTL 30s)
        self._data_cache = {}       # {pair: dict}
        self._cache_ts   = {}       # {pair: float (timestamp)}
        self._cache_ttl  = 30       # secondes
        
        if not self.simulation_mode:
            self.connect()
        else:
            self.connected = True
            self._log("Mode Simulation : Données fictives pour les tests", "INFO")
            # Ajout temporaire pour deboguer la source de l'appel sur Mac
            import traceback
            stack = "".join(traceback.format_stack())
            self._log(f"DEBUG STACK TRACE:\n{stack}", "INFO")

    def _log(self, message, level="INFO"):
        """Affiche un log dans la console et tente de l'envoyer au dashboard."""
        try:
            target = None
            if 'dashboard' in sys.modules:
                target = sys.modules['dashboard']
            elif '__main__' in sys.modules and hasattr(sys.modules['__main__'], 'log'):
                target = sys.modules['__main__']
                
            if target and hasattr(target, 'log'):
                target.log(message, level)
            else:
                print(f"[{level}] {message}")
        except:
            print(f"[{level}] {message}")
            
    def connect(self) -> bool:
        """Etablit la connexion à MT5."""
        self._log("Tentative de connexion à MetaTrader 5...", "INFO")
        
        if not MT5_AVAILABLE:
            self._log("[ERREUR] Librairie MetaTrader5 non installée.", "ERROR")
            self.simulation_mode = True
            return False

        # Paramètres de connexion depuis config.py
        connect_params = {}
        if hasattr(config, "MT5_ACCOUNT") and config.MT5_ACCOUNT:
            connect_params["login"] = config.MT5_ACCOUNT
        if hasattr(config, "MT5_PASSWORD") and config.MT5_PASSWORD:
            connect_params["password"] = config.MT5_PASSWORD
        if hasattr(config, "MT5_SERVER") and config.MT5_SERVER:
            connect_params["server"] = config.MT5_SERVER
        if hasattr(config, "MT5_PATH") and config.MT5_PATH:
            connect_params["path"] = config.MT5_PATH
        
        # Shutdown if already initialized to clean up state
        mt5.shutdown()
        
        if not mt5.initialize(**connect_params):
            error = mt5.last_error()
            self._log(f"[ECHEC] Connexion MT5 : {error}", "ERROR")
            self._log("  -> Vérifiez que MetaTrader 5 est ouvert sur votre PC", "WARNING")
            self._log("  -> Vérifiez vos identifiants dans config.py", "WARNING")
            self.simulation_mode = True
            self.connected = False 
            return False
        
        # Infos du compte
        account_info = mt5.account_info()
        if account_info:
            self._log(f"[OK] Connecté à MT5 ! Compte: {account_info.login} ({account_info.company})", "SUCCESS")
            # Vérifier si Algo Trading est activé
            terminal_info = mt5.terminal_info()
            if terminal_info and not terminal_info.trade_allowed:
                self._log("⚠️ [ATTENTION] Algo Trading est DESACTIVE dans MT5 !", "WARNING")
                self._log("  -> Activez 'Algo Trading' (bouton vert) dans MetaTrader 5", "WARNING")
            
            self.simulation_mode = False
            self.connected = True
            return True
        
        self.simulation_mode = True
        return False
    
    def get_market_data(self, pair: str) -> dict:
        """
        Récupère toutes les données nécessaires pour l'analyse d'une paire.
        Résultat mis en cache 30s pour éviter les appels répétés.
        """
        import time as _time
        now_ts = _time.time()
        # Retourner le cache si encore frais
        if (pair in self._data_cache and
                now_ts - self._cache_ts.get(pair, 0) < self._cache_ttl):
            return self._data_cache[pair]

        if self.simulation_mode:
            result = self._get_simulation_data(pair)
        else:
            result = self._get_real_data(pair)

        # Mettre en cache
        self._data_cache[pair] = result
        self._cache_ts[pair]   = now_ts
        return result
    
    def _get_real_data(self, pair: str) -> dict:
        """Récupère les vraies données depuis MT5."""
        try:
            # Recherche du symbole réel sur le broker (suffixes .m, _p, etc.)
            real_symbol = self._find_broker_symbol(pair)
            if not real_symbol:
                self._log(f"❌ [SÉCURITÉ] {pair} introuvable sur le broker. Analyse annulée.", "ERROR")
                return {"status": "ERROR", "message": f"Symbole {pair} introuvable", "pair": pair}

            mt5.symbol_select(real_symbol, True)
            
            # Prix actuel
            tick = mt5.symbol_info_tick(real_symbol)
            if not tick:
                self._log(f"❌ [SÉCURITÉ] Pas de signal (tick) pour {real_symbol}. Analyse annulée.", "ERROR")
                return {"status": "ERROR", "message": "MT5_NO_TICK", "pair": pair}

            current_price = (tick.ask + tick.bid) / 2
            
            # Heure New York avec gestion DST
            ny_tz = ZoneInfo("America/New_York")
            ny_now = datetime.now(ny_tz)
            
            # Bougies
            def get_candles(timeframe, count=50):
                rates = mt5.copy_rates_from_pos(pair, timeframe, 0, count)
                if rates is None:
                    return []
                return [
                    {
                        "time": datetime.fromtimestamp(r['time']).strftime("%Y-%m-%d %H:%M"),
                        "open": round(float(r['open']), 5),
                        "high": round(float(r['high']), 5),
                        "low": round(float(r['low']), 5),
                        "close": round(float(r['close']), 5),
                        "volume": int(r['tick_volume'])
                    }
                    for r in rates
                ]
            
            return {
                "pair": pair,
                "current_price": round(current_price, 5),
                "ny_time": ny_now.strftime("%H:%M"),
                "date": ny_now.strftime("%Y-%m-%d"),
                "midnight_open": self._get_midnight_open(pair),
                "daily_high": self._get_daily_high_low(pair)[0],
                "daily_low": self._get_daily_high_low(pair)[1],
                "prev_day_high": self._get_prev_day_hl(pair)[0],
                "prev_day_low": self._get_prev_day_hl(pair)[1],
                "prev_week_high": self._get_prev_week_hl(pair)[0],
                "prev_week_low": self._get_prev_week_hl(pair)[1],
                "dxy_price": self._get_current_price("DXY.cash", "USDX", "USDIndex"),
                "gbpusd_price": self._get_current_price("GBPUSD"),
                "candles_m1":  get_candles(mt5.TIMEFRAME_M1,  50),
                "candles_m5":  get_candles(mt5.TIMEFRAME_M5,  100),
                "candles_m15": get_candles(mt5.TIMEFRAME_M15, 150),
                "candles_h1":  get_candles(mt5.TIMEFRAME_H1,  200),
                "candles_h4":  get_candles(mt5.TIMEFRAME_H4,  200),
                "candles_d1":  get_candles(mt5.TIMEFRAME_D1,  200),
                "candles_w1":  get_candles(mt5.TIMEFRAME_W1,  100),
                "candles_mn1": get_candles(mt5.TIMEFRAME_MN1, 60),
                "source": "MT5_LIVE",
                "status": "OK"
            }
        
        except Exception as e:
            self._log(f"❌ [ERREUR] {pair} : {e}", "ERROR")
            return {"status": "ERROR", "message": str(e), "pair": pair}

    def get_ohlcv(self, pair: str, timeframe: str, count: int = 50) -> list:
        """Alias de compatibilité pour retourner les bougies."""
        data = self.get_market_data(pair)
        tf_map = {
            "M1": "candles_m1", "M5": "candles_m5", "M15": "candles_m15",
            "H1": "candles_h1", "H4": "candles_h4", "D1": "candles_d1",
            "W1": "candles_w1", "MN1": "candles_mn1", "MN": "candles_mn1"
        }
        key = tf_map.get(timeframe.upper(), "candles_h1")
        candles = data.get(key, [])
        return candles[-count:] if count and len(candles) > count else candles

    def _get_midnight_open(self, pair: str) -> float:
        """Récupère le prix d'ouverture à minuit New York."""
        try:
            ny_tz = ZoneInfo("America/New_York")
            rates = mt5.copy_rates_from_pos(pair, mt5.TIMEFRAME_H1, 0, 24)
            if rates is not None:
                for r in reversed(rates):
                    dt_nyc = datetime.fromtimestamp(r['time'], tz=timezone.utc).astimezone(ny_tz)
                    if dt_nyc.hour == 0:
                        return round(float(r['open']), 5)
        except Exception:
            pass
        return 0.0

    def _get_daily_high_low(self, pair: str) -> tuple:
        """Récupère le H/L du jour actuel."""
        try:
            rates = mt5.copy_rates_from_pos(pair, mt5.TIMEFRAME_D1, 0, 1)
            if rates is not None and len(rates) > 0:
                return round(float(rates[0]['high']), 5), round(float(rates[0]['low']), 5)
        except Exception:
            pass
        return 0.0, 0.0

    def _get_prev_day_hl(self, pair: str) -> tuple:
        """Récupère le PDH/PDL."""
        try:
            rates = mt5.copy_rates_from_pos(pair, mt5.TIMEFRAME_D1, 1, 1)
            if rates is not None and len(rates) > 0:
                return round(float(rates[0]['high']), 5), round(float(rates[0]['low']), 5)
        except Exception:
            pass
        return 0.0, 0.0

    def _get_prev_week_hl(self, pair: str) -> tuple:
        """Récupère le PWH/PWL."""
        try:
            rates = mt5.copy_rates_from_pos(pair, mt5.TIMEFRAME_W1, 1, 1)
            if rates is not None and len(rates) > 0:
                return round(float(rates[0]['high']), 5), round(float(rates[0]['low']), 5)
        except Exception:
            pass
        return 0.0, 0.0

    def _get_current_price(self, *symbols) -> float:
        """Tente d'obtenir le prix d'un symbole."""
        for symbol in symbols:
            # On tente le symbole brut puis avec normalisation
            s = self._find_broker_symbol(symbol) if not self.simulation_mode else symbol
            if not s: continue
            tick = mt5.symbol_info_tick(s)
            if tick:
                return round((tick.ask + tick.bid) / 2, 5)
        return 0.0

    def _find_broker_symbol(self, pair: str) -> str:
        """Trouve le symbole exact utilisé par le broker (ajoute .m, _p, Pro, etc.)"""
        if self.simulation_mode: return pair
        
        # 1. Test direct
        info = mt5.symbol_info(pair)
        if info: return pair
        
        # 2. Test suffixes courants
        suffixes = [".m", "_p", "Pro", ".pro", ".x", "_i", "micro"]
        for s in suffixes:
            test_sym = pair + s
            info = mt5.symbol_info(test_sym)
            if info: return test_sym
            
        # 3. Test variantes spécifiques (Crypto, Or, etc.)
        p_up = pair.upper()
        
        def is_valid_price(sym, min_p=None, max_p=None):
            info = mt5.symbol_info(sym)
            if not info: return False
            tick = mt5.symbol_info_tick(sym)
            if not tick: return False
            price = (tick.ask + tick.bid) / 2
            if min_p and price < min_p: return False
            if max_p and price > max_p: return False
            return True

        if "BTC" in p_up:
            # On cherche le VRAI Bitcoin (> 10,000$) OU l'exact match si c'est un ETF (> 10$)
            for v in ["BTCUSD", "BTCUSDT", "BITCOIN", "BTCUSD.m", "BTCUSD_p", "BTCUSD.pro", "BTC"]:
                if v == "BTC" and is_valid_price(v, min_p=10): return v
                if mt5.symbol_info(v) and is_valid_price(v, min_p=10000): 
                    return v
        
        if "XAU" in p_up or "GOLD" in p_up:
            # L'or doit valoir > 500$ sauf match exact
            for v in ["XAUUSD", "GOLD", "XAUUSD.m", "XAUUSD_p", "GOLD.m"]:
                if v in ["GOLD", "XAUUSD"] and is_valid_price(v, min_p=10): return v
                if mt5.symbol_info(v) and is_valid_price(v, min_p=500): 
                    return v

        if "XAG" in p_up or "SILVER" in p_up:
            for v in ["XAGUSD", "SILVER", "XAGUSD.m", "XAGUSD_p"]:
                if mt5.symbol_info(v): return v

        if "OIL" in p_up or "WTI" in p_up or "CL" in p_up:
            # Pétrole : Variantes courantes (WTI, CL, USOIL, Crude)
            for v in ["USOIL", "WTI", "WTICrude", "CL", "CL_p", "USOIL.m", "CrudeOil", "WTI_p"]:
                if mt5.symbol_info(v): return v
        
        return ""

    def _get_simulation_data(self, pair: str) -> dict:
        """Retourne des données de simulation."""
        import random
        ny_tz = ZoneInfo("America/New_York")
        ny_now = datetime.now(ny_tz)
        
        # Prix de simulation réalistes selon l'actif
        if "BTC" in pair.upper():
            price = 68000.0
        elif "XAU" in pair.upper() or "GOLD" in pair.upper():
            price = 2880.0
        elif "EURUSD" in pair.upper():
            price = 1.0850
        elif "GBPUSD" in pair.upper():
            price = 1.2650
        else:
            price = 1.0000
            
        price += random.uniform(-price*0.001, price*0.001)
        
        def make_candles(base, count, volatility):
            candles = []
            for i in range(count):
                o = base + random.uniform(-volatility, volatility)
                c = base + random.uniform(-volatility, volatility)
                candles.append({
                    "time": (datetime.now() - timedelta(minutes=i*15)).strftime("%H:%M"),
                    "open": round(o, 5), "high": round(max(o, c) + 0.0001, 5),
                    "low": round(min(o, c) - 0.0001, 5), "close": round(c, 5)
                })
            return candles

        return {
            "pair": pair, "current_price": price, "ny_time": ny_now.strftime("%H:%M"),
            "date": ny_now.strftime("%Y-%m-%d"), "midnight_open": round(price - 0.0020, 5),
            "daily_high": round(price + 0.0050, 5), "daily_low": round(price - 0.0050, 5),
            "prev_day_high": round(price + 0.0100, 5), "prev_day_low": round(price - 0.0100, 5),
            "prev_week_high": round(price + 0.0200, 5), "prev_week_low": round(price - 0.0200, 5),
            "dxy_price": 104.50, "gbpusd_price": 1.2650,
            "candles_m1": make_candles(price, 50,  0.00005),
            "candles_m5": make_candles(price, 100, 0.0001),
            "candles_m15": make_candles(price, 150, 0.00015),
            "candles_h1": make_candles(price, 200, 0.0005),
            "candles_h4": make_candles(price, 200, 0.0015),
            "candles_d1": make_candles(price, 200, 0.0050),
            "candles_w1": make_candles(price, 100, 0.0100),
            "candles_mn1": make_candles(price, 60, 0.0300),
            "source": "SIMULATION"
        }

    def save_chart_as_image(self, pair: str, timeframe: str = "H1", count: int = 50, markers: dict = None) -> str:
        """
        Génère une image du graphique à partir des données OHLCV.
        Peut inclure des marqueurs ICT (Midnight Open, PDH, PDL, etc.)
        """
        try:
            candles = self.get_ohlcv(pair, timeframe, count)
            if not candles:
                return ""
            
            df = pd.DataFrame(candles)
            df['time'] = pd.to_datetime(df['time'])
            
            plt.figure(figsize=(12, 6))
            plt.style.use('dark_background')
            
            # Dessin des bougies
            for idx, row in df.iterrows():
                color = 'green' if row['close'] >= row['open'] else 'red'
                plt.vlines(idx, row['low'], row['high'], color=color, linewidth=1)
                plt.vlines(idx, row['open'], row['close'], color=color, linewidth=4)
            
            # Ajout des marqueurs ICT (si fournis)
            if markers:
                # On ne les trace que s'ils sont dans la plage de prix visible
                y_min, y_max = df['low'].min(), df['high'].max()
                
                # Midnight Open (Bleu)
                mo = markers.get('midnight_open')
                if mo and y_min <= mo <= y_max:
                    plt.axhline(y=mo, color='cyan', linestyle='--', alpha=0.6, label='Midnight Open')
                
                # Previous Day High/Low (Gris/Or)
                pdh = markers.get('prev_day_high')
                pdl = markers.get('prev_day_low')
                if pdh and y_min <= pdh <= y_max:
                    plt.axhline(y=pdh, color='orange', linestyle='-', alpha=0.5, label='PDH')
                if pdl and y_min <= pdl <= y_max:
                    plt.axhline(y=pdl, color='orange', linestyle='-', alpha=0.5, label='PDL')
                
                # Previous Week High/Low (Jaune)
                pwh = markers.get('prev_week_high')
                pwl = markers.get('prev_week_low')
                if pwh and y_min <= pwh <= y_max:
                    plt.axhline(y=pwh, color='yellow', linestyle='-', alpha=0.4, label='PWH')
                if pwl and y_min <= pwl <= y_max:
                    plt.axhline(y=pwl, color='yellow', linestyle='-', alpha=0.4, label='PWL')

            plt.title(f"Chart {pair} - {timeframe}")
            plt.grid(True, alpha=0.2)
            plt.legend(loc='upper left', fontsize='small', framealpha=0.3)
            
            # Dossier temp pour les images
            img_dir = os.path.join(config.BASE_DIR, "data", "charts")
            os.makedirs(img_dir, exist_ok=True)
            
            filename = os.path.join(img_dir, f"{pair}_{timeframe}.png")
            plt.savefig(filename)
            plt.close()
            
            return filename
        except Exception as e:
            print(f"[ERROR] Erreur lors de la génération du graphique : {e}")
            return ""

    def capture_multi_timeframe_charts(self, pair: str, tfs: list = ["D1", "H4", "H1", "M15"]) -> dict:
        """Capture les graphiques pour plusieurs timeframes."""
        results = {}
        # Récupérer les marqueurs une fois
        data = self.get_market_data(pair)
        markers = {
            'midnight_open': data.get('midnight_open'),
            'prev_day_high': data.get('prev_day_high'),
            'prev_day_low': data.get('prev_day_low'),
            'prev_week_high': data.get('prev_week_high'),
            'prev_week_low': data.get('prev_week_low')
        }
        
        for tf in tfs:
            path = self.save_chart_as_image(pair, tf, count=60, markers=markers)
            if path:
                results[tf] = path
        return results

    def get_pip_size(self, pair: str) -> float:
        """Retourne la taille d'un pip."""
        if self.simulation_mode or not self.connected:
            return 0.0001
        info = mt5.symbol_info(pair)
        if not info: return 0.0001
        if info.digits in [3, 5]: return info.point * 10
        if info.digits == 2: return info.point * 10 if pair.upper() != "BTCUSD" else 1.0
        return info.point * 10 if info.point > 0 else 0.0001

    def get_tick_info(self, pair: str) -> tuple[float, float]:
        """Retourne (tick_value, tick_size)."""
        if self.simulation_mode or not self.connected:
            return 0.0, 0.0
        info = mt5.symbol_info(pair)
        if not info: return 0.0, 0.0
        return info.trade_tick_value, info.trade_tick_size

    def test_connection(self) -> bool:
        """Affiche un diagnostic de connexion."""
        if self.simulation_mode: return True
        if not self.connected: return False
        print(f"[OK] Connecté à MT5. Balance: {mt5.account_info().balance}")
        return True

    def disconnect(self):
        """Ferme la connexion proprement."""
        if MT5_AVAILABLE and not self.simulation_mode and self.connected:
            try:
                mt5.shutdown()
                self.connected = False
                print("[MT5] Déconnecté proprement du terminal MetaTrader 5.")
            except:
                pass

if __name__ == "__main__":
    c = MT5Connector()
    c.test_connection()
    print(c.get_market_data("EURUSD"))
