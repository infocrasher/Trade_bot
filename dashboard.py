"""
================================================================
  DASHBOARD FLASK — ICT Algorithmic Trading Bot
  5 Agents: Structure / Time / Entry / Macro / Orchestrator
  Lancez avec : python3 dashboard.py
  Puis ouvrez : http://localhost:5000
================================================================
"""

import sys, os, json, time, threading, queue, uuid, re, atexit, signal
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template, jsonify, request, Response
import logging
from logging.handlers import RotatingFileHandler

# ── Import conditionnel MT5 (Mac/Linux compatible) ──────────────
try:
    import MetaTrader5 as mt5_mod
except ImportError:
    mt5_mod = None

# ── Chemin racine du projet (ce fichier EST à la racine) ─────────
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

import config
from agents.post_mortem import run_post_mortem
from agents.telegram_notifier import notifier

# ── Logger fichier — garde tout l'historique ──────────────────────
os.makedirs(os.path.join(PROJECT_ROOT, "logs"), exist_ok=True)

# Créer un dossier de session spécifique pour ce démarrage
from datetime import datetime
_session_dir_name = "SESSION__" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
_session_path = os.path.join(PROJECT_ROOT, "logs", "sessions", _session_dir_name)
os.makedirs(_session_path, exist_ok=True)

file_logger = logging.getLogger("ict_bot")
file_logger.setLevel(logging.DEBUG)

# Handler principal (logs/bot.log)
handler = RotatingFileHandler(
    os.path.join(PROJECT_ROOT, "logs", "bot.log"),
    maxBytes=10 * 1024 * 1024,  # 10 MB par fichier
    backupCount=30,              # Garde 30 fichiers = ~300 MB max
    encoding="utf-8"
)
bot_formatter = logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
handler.setFormatter(bot_formatter)
file_logger.addHandler(handler)

# Handler de session (logs/sessions/.../bot.log)
session_bot_handler = RotatingFileHandler(os.path.join(_session_path, "bot.log"), maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
session_bot_handler.setFormatter(bot_formatter)
file_logger.addHandler(session_bot_handler)


# ── Logger séparé pour les événements trades ──────────────────────
trade_logger = logging.getLogger("ict_trades")
trade_logger.setLevel(logging.INFO)

# ── Circuit Breaker Init — isolé PAR PROFIL ──────────────────────
# Chaque profil a son propre CB : un déclenchement sur ICT ne bloque pas Pure PA
try:
    from data.trade_manager import CircuitBreaker
    _circuit_breaker            = CircuitBreaker()  # ICT Strict
    _circuit_breaker_pure_pa    = CircuitBreaker()  # Pure PA
    _CB_AVAILABLE = True
except Exception as e:
    file_logger.error(f"Erreur init CircuitBreaker : {e}")
    _CB_AVAILABLE = False
    _circuit_breaker         = None
    _circuit_breaker_pure_pa = None

# Handler principal (logs/trades.log)
trade_handler = RotatingFileHandler(
    os.path.join(PROJECT_ROOT, "logs", "trades.log"),
    maxBytes=5 * 1024 * 1024,
    backupCount=30,
    encoding="utf-8"
)
trade_formatter = logging.Formatter("%(asctime)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
trade_handler.setFormatter(trade_formatter)
trade_logger.addHandler(trade_handler)

# Handler de session (logs/sessions/.../trades.log)
session_trade_handler = RotatingFileHandler(os.path.join(_session_path, "trades.log"), maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
session_trade_handler.setFormatter(trade_formatter)
trade_logger.addHandler(session_trade_handler)

# ── Agents algorithmiques (Architecture multi-écoles) ─────────────
# École ICT (principale)
from agents.ict import StructureAgent, TimeSessionAgent, EntryAgent, MacroBiasAgent, OrchestratorAgent
# École Pure PA (Étape 4 — profil 2 en parallèle)
try:
    from agents.pure_pa.orchestrator import PurePAOrchestrator
    _PURE_PA_AVAILABLE = True
except ImportError:
    _PURE_PA_AVAILABLE = False
    PurePAOrchestrator = None
# Écoles supplémentaires (placeholders — en cours d'implémentation)
from agents.elliott import ElliottOrchestrator
from agents.fondamental import FondamentalOrchestrator
from agents.meta_orchestrator import MetaOrchestrator
from agents.elliott.orchestrator import run_elliott_analysis
from agents.vsa.orchestrator import VSAOrchestrator
from agents.llm_validator import LLMValidatorAgent

# ── Profils d'horizon (adapte les TFs selon le style de trading) ─
HORIZON_PROFILES = {
    "scalp": {
        "label": "Scalp (M5)",
        "structure_tfs": ["D1", "H4", "H1"],    # HTF pour le biais
        "entry_tf": "M5",                         # TF d'entrée
        "bias_from": "H1",                        # TF principal pour le biais
        "min_data": 10,
        "force_kz": False,                         # respecte les Killzones
    },
    "intraday": {
        "label": "Intraday (H1)",
        "structure_tfs": ["W1", "D1", "H4"],
        "entry_tf": "H1",
        "bias_from": "H4",
        "min_data": 10,
        "force_kz": False,
    },
    "daily": {
        "label": "Daily / Swing (H4)",
        "structure_tfs": ["W1", "D1", "H4"],
        "entry_tf": "H4",
        "bias_from": "D1",
        "min_data": 10,
        "force_kz": True,                          # pas de KZ pour du swing
    },
    "weekly": {
        "label": "Weekly / Position (D1)",
        "structure_tfs": ["MN", "W1", "D1"],
        "entry_tf": "D1",
        "bias_from": "W1",
        "min_data": 5,
        "force_kz": True,                          # pas de KZ pour du position
    },
}

# ── Instances globales ───────────────────────────────────────────
mt5_conn  = None
trade_mgr = None

app = Flask(__name__, template_folder='dashboard/templates', static_folder='dashboard/static')

# ── PAIRES DISPONIBLES ───────────────────────────────────────────
ALL_PAIRS = {
    "forex":   ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDJPY", "USDCAD", "USDCHF", "EURGBP", "EURJPY", "GBPJPY", "AUDJPY"],
    "metals":  ["XAUUSD"],  # XAGUSD retiré — non disponible sur TwelveData Basic
    "crypto":  ["BTCUSD", "ETHUSD"],
    "energy":  []
}

# ── ÉTAT GLOBAL ──────────────────────────────────────────────────
# Cooldown pour signaux périmés/obsolètes — clé = "PAIRE_HORIZON"
# valeur = timestamp epoch d'expiration du cooldown
signal_cooldowns = {}
COOLDOWNS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                              "paper_trading", "cooldowns.json")

SETTINGS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "paper_trading", "settings_override.json"
)

PROFILES_SETTINGS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "data", "profiles", "settings.json"
)

DEFAULT_PROFILES_SETTINGS = {
    # Scoring
    "score_min_exec": 65,
    "score_min_half": 65,
    "telegram_threshold": 70,
    
    # Gates ICT
    "gate_rr_active": True,
    "gate_rr_value": 2.0,
    "gate_ob_active": True,
    "gate_ob_value": 3,
    "gate_spread_ks4_active": True,
    "gate_spread_ks4_value": 3.0,
    "gate_sl_min_active": True,
    "gate_sl_min_value": 3.0,
    "gate_t20_malus_active": True,
    "gate_enigma_mandatory_active": False,
    "gate_sod_active": True,
    "gate_htf_strict_active": True,
    "gate_htf_strict_mode": "D1+H4+H1",
    
    # Temporel
    "time_killzones_mandatory": True,
    "time_seek_destroy_monday": True,
    
    # Pure PA
    "pa_mss_mandatory": True,
    "pa_fvg_mandatory": True,
    
    # Sizing
    "size_risk_pct": 1.0,
    "size_sod_active": True,
    
    # Meta
    "profile_version": "v1.0"
}

profiles_settings = DEFAULT_PROFILES_SETTINGS.copy()

def _load_profiles_settings():
    global profiles_settings
    try:
        os.makedirs(os.path.dirname(PROFILES_SETTINGS_FILE), exist_ok=True)
        if os.path.exists(PROFILES_SETTINGS_FILE):
            with open(PROFILES_SETTINGS_FILE, "r") as f:
                loaded = json.load(f)
            # Fusion avec les valeurs par défaut
            profiles_settings.update(loaded)
        else:
            _save_profiles_settings()
    except Exception as e:
        print(f"[Profiles] Erreur chargement settings.json: {e}")

def _save_profiles_settings():
    try:
        os.makedirs(os.path.dirname(PROFILES_SETTINGS_FILE), exist_ok=True)
        with open(PROFILES_SETTINGS_FILE, "w") as f:
            json.dump(profiles_settings, f, indent=4)
    except Exception as e:
        print(f"[Profiles] Erreur sauvegarde settings.json: {e}")

def _load_settings_override():
    """Charge les overrides de settings depuis le disque et les applique."""
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r") as f:
                overrides = json.load(f)
            # Appliquer les overrides sur config
            for key, value in overrides.items():
                if hasattr(config, key):
                    setattr(config, key, value)
            print(f"[Settings] {len(overrides)} override(s) chargé(s)")
    except Exception as e:
        print(f"[Settings] Erreur chargement: {e}")

def _save_settings_override(overrides):
    """Sauvegarde les overrides sur disque."""
    try:
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        with open(SETTINGS_FILE, "w") as f:
            json.dump(overrides, f, indent=2)
    except Exception as e:
        print(f"[Settings] Erreur sauvegarde: {e}")

def _save_cooldowns():
    """Persiste les cooldowns actifs sur disque."""
    try:
        os.makedirs(os.path.dirname(COOLDOWNS_FILE), exist_ok=True)
        # Ne sauvegarder que les cooldowns non expirés
        active = {k: v for k, v in signal_cooldowns.items() 
                  if v > time.time()}
        with open(COOLDOWNS_FILE, "w") as f:
            json.dump(active, f, indent=2)
    except Exception as e:
        print(f"[Cooldown] Erreur sauvegarde: {e}")

def _load_cooldowns():
    """Recharge les cooldowns depuis le disque au démarrage."""
    try:
        if os.path.exists(COOLDOWNS_FILE):
            with open(COOLDOWNS_FILE, "r") as f:
                data = json.load(f)
            # Filtrer les cooldowns expirés
            now = time.time()
            active = {k: v for k, v in data.items() if v > now}
            signal_cooldowns.update(active)
            if active:
                print(f"[Cooldown] {len(active)} cooldown(s) rechargé(s) depuis le disque")
    except Exception as e:
        print(f"[Cooldown] Erreur chargement: {e}")


# Durée du cooldown par horizon (en secondes)
COOLDOWN_DURATIONS = {
    "scalp": 30 * 60,       # 30 min
    "intraday": 2 * 3600,   # 2h
    "daily": 8 * 3600,      # 8h
    "weekly": 24 * 3600,    # 24h
}

# ── Intervalles minimum entre deux analyses HTF ──────────────────────────────
# H4/D1 n'ont pas besoin de tourner à chaque cycle M5 (toutes les 5 min)
# Ces horizons ont leur propre rythme naturel
HTF_MIN_INTERVALS = {
    "daily":  3600,      # H4  — 1 analyse par heure maximum
    "weekly": 14400,     # D1  — 1 analyse toutes les 4 heures maximum
}
# Timestamp du dernier passage par horizon — clé = f"{pair}_{horizon}"
_htf_last_run = {}
# ─────────────────────────────────────────────────────────────────────────────

bot_state = {
    "status":             "stopped",
    "current_pair":       None,
    "last_analysis_time": None,
    "cycle_count":        0,
    "orders":             [],
    "last_reports":       {},
    "log_messages":       [],
    "start_time":         None,
    "circuit_breaker":    {"active": False, "reason": "", "trades_today": 0},
    "min_score":          getattr(config, "MIN_CONFIDENCE_SCORE", 70),
    "mt5_status":         "DISCONNECTED",
    "mt5_connected":      False,
    "current_api":        "Algo (5 Agents)",
    "horizon":            "scalp",
}

bot_thread  = None
stop_event  = threading.Event()
pause_event = threading.Event()
state_lock  = threading.Lock()
sse_clients = []
sse_lock    = threading.Lock()
llm_validator = None


# ─────────────────────────────────────────────────────────────────
# MODÈLE D'ORDRE
# ─────────────────────────────────────────────────────────────────
def get_pip_size_safe(pair):
    pair_upper = pair.upper()
    if any(c in pair_upper for c in ["BTC", "ETH"]):
        return 1.0        # Crypto : 1 pip = 1$
    elif "XAU" in pair_upper:
        return 0.1         # Or : 1 pip = 0.1$
    elif "XAG" in pair_upper:
        return 0.01        # Argent : 1 pip = 0.01$
    elif "OIL" in pair_upper:
        return 0.01        # Pétrole : 1 pip = 0.01$
    elif "JPY" in pair_upper:
        return 0.01        # Paires JPY : 1 pip = 0.01
    else:
        return 0.0001      # Forex standard : 1 pip = 0.0001

def make_order(pair, school, direction, entry, sl, tp1, tp2, score, narrative, checklist,
               pending_conditions=None, status="pending", volume=0.10,
               pnl_pips=0.0, pnl_money=0.0, timeframe="M15",
               profile_id=None, active_gates=None, convergence_state=None, ttl_seconds=None):
    pip_size = get_pip_size_safe(pair)
    montant  = round(volume * abs(entry - sl) / pip_size * 10, 2) if entry and sl and pip_size > 0 else 0.0
    return {
        "id":               f"{pair}_{str(uuid.uuid4())[:8]}",
        "pair":             pair,
        "school":           school,
        "status":           status,
        "direction":        direction,
        "timeframe":        timeframe,
        "entry":            float(entry or 0),
        "sl":               float(sl or 0),
        "tp1":              float(tp1 or 0),
        "tp2":              float(tp2 or 0),
        "rr":               round(abs(float(tp1 or 0) - float(entry or 0)) / abs(float(entry or 0) - float(sl or 0)), 2)
                            if entry and sl and abs(float(entry or 0) - float(sl or 0)) > 0 else 0,
        "score":            int(score or 50),
        "pnl_pips":         float(pnl_pips or 0),
        "pnl_money":        float(pnl_money or 0),
        "volume":           float(volume or 0.1),
        "montant_risque":   montant,
        "opened_at":        datetime.now().strftime("%Y-%m-%d %H:%M"),
        "closed_at":        None,
        "checklist":        checklist or [],
        "narrative":        narrative or "",
        "pending_conditions": pending_conditions or [],
        "raw_plan":         "",
        "profile_id":       profile_id or school,
        "active_gates":     active_gates or [],
        "convergence_state": convergence_state or "independent",
        "ttl_seconds":      ttl_seconds or 1800
    }


# ─────────────────────────────────────────────────────────────────
# LOGGING & SSE
# ─────────────────────────────────────────────────────────────────
def log(message, level="INFO"):
    entry = {
        "time":    datetime.now().strftime("%H:%M:%S"),
        "level":   level,
        "message": message,
    }
    with state_lock:
        bot_state["log_messages"].append(entry)
        if len(bot_state["log_messages"]) > 300:
            bot_state["log_messages"] = bot_state["log_messages"][-300:]
    broadcast("log", entry)
    
    # Écrire dans le fichier log
    level_map = {
        "DEBUG": file_logger.debug,
        "INFO": file_logger.info,
        "WARNING": file_logger.warning,
        "ERROR": file_logger.error,
        "SUCCESS": file_logger.info,  # SUCCESS → INFO dans le fichier
    }
    writer = level_map.get(level.upper(), file_logger.info)
    writer(message)
    
    # Logger les événements trades dans trades.log
    if any(keyword in message for keyword in [
        "PAPER TRADE", "PAPER CLOSE", "PENDING", "ACTIF", 
        "Signal périmé", "Signal obsolète", "EXPIRED",
        "Cooldown", "OUVRIR", "RESTER_DEHORS"
    ]):
        trade_logger.info(message)


def broadcast(event_type, data):
    payload = f"data: {json.dumps({'type': event_type, 'data': data})}\n\n"
    with sse_lock:
        dead = []
        for q in sse_clients:
            try:
                q.put_nowait(payload)
            except:
                dead.append(q)
        for q in dead:
            sse_clients.remove(q)


# ─────────────────────────────────────────────────────────────────
# INITIALISATION ASYNC
# ─────────────────────────────────────────────────────────────────
def init_system_async():
    global mt5_conn, trade_mgr

    print("[INIT] Démarrage du moteur algorithmique ICT...")
    try:
        # Data Provider : MT5 > YFinance > Simulation
        try:
            from data.mt5_connector import MT5Connector
            mt5_conn = MT5Connector()
        except Exception:
            mt5_conn = None

        if mt5_conn is None or getattr(mt5_conn, 'simulation_mode', True):
            try:
                import sys, os
                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                from data.twelve_data_provider import TwelveDataProvider
                td = TwelveDataProvider()
                if td.connected:
                    mt5_conn = td
                    print(f"[INIT] TwelveData connecté — données temps réel actives")
                    log("TwelveData connecté — données temps réel (Twelve Data API).", "SUCCESS")
                else:
                    print("[INIT] TwelveData initialisé mais non connecté — mode simulation")
                    log("TwelveData hors ligne — mode SIMULATION.", "WARNING")
            except Exception as e:
                print(f"[INIT] TwelveData import/init échoué: {e} — mode simulation")
                log(f"TwelveData erreur: {e} — mode SIMULATION.", "ERROR")

        if mt5_conn is None:
            from data.mt5_connector import MT5Connector
            mt5_conn = MT5Connector()

        with state_lock:
            bot_state["mt5_connected"] = mt5_conn.connected
            if hasattr(mt5_conn, "simulation_mode"):
                bot_state["mt5_status"] = "SIMU" if mt5_conn.simulation_mode else "LIVE"
            else:
                bot_state["mt5_status"] = "TWELVEDATA"
            bot_state["current_api"] = "Algorithmique (5 Agents)"

        # Trade Manager
        from data.trade_manager import TradeManager
        trade_mgr = TradeManager()

        print("[INIT] Système algorithmique ICT prêt (5 agents, 107 tests).")
        log("Système algorithmique ICT prêt — 5 agents, 0 LLM.", "SUCCESS")
        
        # Recharger les paper trades actifs depuis les fichiers JSON
        _reload_paper_trades()
        
        # LLM Validateur (optionnel)
        global llm_validator
        api_key = getattr(config, "ANTHROPIC_API_KEY", "") or os.environ.get("ANTHROPIC_API_KEY", "")
        llm_validator = LLMValidatorAgent(api_key=api_key)
        if llm_validator.enabled:
            log("🧠 LLM Validateur ICT activé (Claude Sonnet)", "SUCCESS")
        else:
            log("⚠️ LLM Validateur désactivé (ANTHROPIC_API_KEY manquante)", "WARNING")
    except Exception as e:
        print(f"[INIT] Erreur critique : {e}")
        log(f"Erreur initialisation : {str(e)}", "ERROR")


# ─────────────────────────────────────────────────────────────────
# SHUTDOWN PROPRE
# ─────────────────────────────────────────────────────────────────
def shutdown_handler():
    stop_event.set()
    if mt5_mod:
        try:
            mt5_mod.shutdown()
        except:
            pass

atexit.register(shutdown_handler)

def _sig_handler(sig, frame):
    shutdown_handler()
    sys.exit(0)

signal.signal(signal.SIGINT,  _sig_handler)
signal.signal(signal.SIGTERM, _sig_handler)


# ─────────────────────────────────────────────────────────────────
# BRIDGE : MT5 data → DataFrames pandas (copié de main.py)
# ─────────────────────────────────────────────────────────────────
import pandas as pd
import numpy as np

def candles_to_dataframe(candles: list) -> pd.DataFrame:
    if not candles:
        return pd.DataFrame()
    df = pd.DataFrame(candles)
    if 'time' in df.columns:
        df['time'] = pd.to_datetime(df['time'], format='mixed', dayfirst=False)
    df['body'] = (df['close'] - df['open']).abs()
    df['range'] = df['high'] - df['low']
    df['body_ratio'] = df.apply(lambda r: r['body'] / r['range'] if r['range'] > 0 else 0, axis=1)
    df['upper_wick'] = df['high'] - df[['open', 'close']].max(axis=1)
    df['lower_wick'] = df[['open', 'close']].min(axis=1) - df['low']
    if 'tick_volume' not in df.columns:
        df['tick_volume'] = df.get('volume', 100)
    return df

def extract_dataframes(market_data: dict) -> dict:
    tf_mapping = {
        "D1": "candles_d1", "H4": "candles_h4", "H1": "candles_h1",
        "M15": "candles_m15", "M5": "candles_m5", "W1": "candles_w1", "MN": "candles_mn1",
    }
    dataframes = {}
    for tf_key, candle_key in tf_mapping.items():
        candles = market_data.get(candle_key, [])
        if candles:
            dataframes[tf_key] = candles_to_dataframe(candles)
    return dataframes


# ─────────────────────────────────────────────────────────────────
# SCHEDULER — Killzones ICT (Heures Alger UTC+1)
# ─────────────────────────────────────────────────────────────────

from datetime import datetime, time as dtime
import pytz

KILLZONE_SCHEDULE = [
    {
        "name": "Asia Killzone",
        "start": dtime(21, 0),
        "end":   dtime(23, 0),
        "pairs": ["USDJPY", "AUDUSD", "NZDUSD", "XAUUSD"],
        "horizons": ["H1", "M5"],
    },
    {
        "name": "London Killzone",
        "start": dtime(3, 0),
        "end":   dtime(6, 0),
        "pairs": ["EURUSD", "GBPUSD", "EURGBP", "XAUUSD", "USDCHF"],
        "horizons": ["H1", "M5"],
    },
    {
        "name": "Silver Bullet London",
        "start": dtime(4, 0),
        "end":   dtime(5, 0),
        "pairs": ["EURUSD", "GBPUSD", "XAUUSD"],
        "horizons": ["M5"],
    },
    {
        "name": "NY AM Killzone",
        "start": dtime(8, 0),
        "end":   dtime(11, 0),
        "pairs": None,   # None = toutes les paires actives
        "horizons": ["H1", "M5", "H4"],
    },
    {
        "name": "Silver Bullet NY",
        "start": dtime(11, 0),
        "end":   dtime(12, 0),
        "pairs": ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"],
        "horizons": ["M5"],
    },
    {
        "name": "NY PM Killzone",
        "start": dtime(11, 0),
        "end":   dtime(13, 0),
        "pairs": ["EURUSD", "GBPUSD", "USDJPY", "USDCAD"],
        "horizons": ["H1", "M5"],
    },
]

# Paires crypto et énergie : actives 24h/24 — analysées toutes les heures
ALWAYS_ON_PAIRS = ["BTCUSD", "ETHUSD"]
ALWAYS_ON_INTERVAL_MINUTES = 60

ALGER_TZ = pytz.timezone("Africa/Algiers")


def get_active_killzones(now_alger=None):
    """
    Retourne la liste des Killzones actives à l'instant T (heure Alger).
    Chaque élément contient name, pairs, horizons.
    """
    if now_alger is None:
        now_alger = datetime.now(ALGER_TZ)
    current_time = now_alger.time().replace(second=0, microsecond=0)

    active = []
    for kz in KILLZONE_SCHEDULE:
        start = kz["start"]
        end   = kz["end"]
        # Gérer le cas minuit (ex: 23h → 01h)
        if start <= end:
            in_window = start <= current_time < end
        else:
            in_window = current_time >= start or current_time < end

        if in_window:
            active.append(kz)

    return active


def get_scheduler_decision(all_pairs, all_horizons, force_analyze=False):
    """
    Décide quelles paires/horizons analyser maintenant.
    
    Retourne:
        dict avec:
            "should_run": bool — True si on doit lancer un cycle
            "pairs": list — paires à analyser
            "horizons": list — horizons à utiliser
            "reason": str — explication pour les logs
            "next_check_seconds": int — combien de secondes attendre avant le prochain check
    """
    if force_analyze:
        return {
            "should_run": True,
            "pairs": all_pairs,
            "horizons": all_horizons,
            "reason": "FORCE_ANALYZE activé",
            "next_check_seconds": 300,
        }

    now_alger = datetime.now(ALGER_TZ)
    active_kzs = get_active_killzones(now_alger)

    # Toujours analyser les paires 24/7 (crypto/énergie)
    always_on = [p for p in all_pairs if p in ALWAYS_ON_PAIRS]

    if not active_kzs:
        # Hors Killzone — calcul du temps jusqu'à la prochaine
        minutes_until_next = _minutes_until_next_killzone(now_alger)
        # Si on a des paires 24/7, on tourne quand même mais moins souvent
        if always_on:
            return {
                "should_run": True,
                "pairs": always_on,
                "horizons": [h for h in all_horizons if h in ["H1", "H4", "D1"]],
                "reason": f"Hors KZ — crypto/énergie uniquement (prochaine KZ dans {minutes_until_next}min)",
                "next_check_seconds": ALWAYS_ON_INTERVAL_MINUTES * 60,
            }
        return {
            "should_run": False,
            "pairs": [],
            "horizons": [],
            "reason": f"Hors Killzone — prochaine ouverture dans {minutes_until_next}min",
            "next_check_seconds": min(minutes_until_next * 60, 300),
        }

    # Construire la liste des paires/horizons depuis toutes les KZ actives
    active_pairs = set(always_on)
    active_horizons = set()
    kz_names = []

    for kz in active_kzs:
        kz_names.append(kz["name"])
        if kz["pairs"] is None:
            active_pairs.update(all_pairs)
        else:
            active_pairs.update(p for p in kz["pairs"] if p in all_pairs)
        active_horizons.update(kz["horizons"])

    # Filtrer pour ne garder que les horizons sélectionnés par l'utilisateur
    filtered_horizons = [h for h in all_horizons if h in active_horizons]
    if not filtered_horizons:
        filtered_horizons = all_horizons  # fallback

    return {
        "should_run": True,
        "pairs": list(active_pairs),
        "horizons": filtered_horizons,
        "reason": f"KZ active: {', '.join(kz_names)}",
        "next_check_seconds": 300,  # cycle toutes les 5min en KZ
    }


def _minutes_until_next_killzone(now_alger):
    """Calcule les minutes jusqu'à la prochaine Killzone."""
    current_time = now_alger.time()
    min_wait = 24 * 60  # max 24h

    for kz in KILLZONE_SCHEDULE:
        start = kz["start"]
        start_dt = now_alger.replace(
            hour=start.hour, minute=start.minute, second=0, microsecond=0
        )
        if start_dt.time() <= current_time:
            # Déjà passé aujourd'hui → demain
            start_dt = start_dt.replace(day=start_dt.day + 1)
        diff = int((start_dt - now_alger).total_seconds() / 60)
        if 0 < diff < min_wait:
            min_wait = diff

    return min_wait

# ─────────────────────────────────────────────────────────────────
# BOUCLE PRINCIPALE DU BOT
# ─────────────────────────────────────────────────────────────────
def run_bot_loop(pairs, interval_minutes, paper_mode, horizons=None):
    global mt5_conn

    if horizons is None:
        horizons = ["scalp"]
    if isinstance(horizons, str):
        horizons = [horizons]
    # Valider chaque horizon
    horizons = [h for h in horizons if h in HORIZON_PROFILES] or ["scalp"]

    with state_lock:
        bot_state["status"]     = "running"
        bot_state["start_time"] = datetime.now().isoformat()
        bot_state["horizon"]    = "+".join(horizons)
    broadcast("status", {"status": "running", "cycle": 0,
                         "mt5_connected": bot_state["mt5_connected"],
                         "mt5_status":    bot_state["mt5_status"]})

    try:
        # ── Helper killzone ──────────────────────────────────────
        def in_killzone():
            from zoneinfo import ZoneInfo
            NYC = ZoneInfo("America/New_York")
            now = datetime.now(NYC)
            t = now.hour * 60 + now.minute
            kzs = [(20*60, 22*60), (2*60, 5*60), (7*60, 10*60), (10*60, 12*60)]
            for s, e in kzs:
                if s > e:
                    if t >= s or t <= e: return True
                else:
                    if s <= t <= e: return True
            return False

        log("Mode algorithmique — 5 Agents ICT.", "INFO")

        # Thread Paper Monitor — vérifie SL/TP toutes les 30 secondes
        if paper_mode:
            def paper_monitor():
                """
                Paper Monitor V2 — Check adaptatif par horizon.
                - Scalp (M5/M15)  : check toutes les 30s
                - Intraday (H1)   : check toutes les 2 min
                - Daily (H4)      : check toutes les 15 min
                - Weekly (D1+)    : check toutes les 60 min
                Gère: PENDING → ACTIVE, expirations, SL/TP.
                """
                CHECK_INTERVALS = {"scalp": 30, "intraday": 120, "daily": 900, "weekly": 3600}
                EXPIRATION = {
                    "scalp":     2 * 3600,
                    "intraday": 12 * 3600,
                    "daily":    48 * 3600,
                    "weekly":    7 * 24 * 3600,
                }
                log("📝 Paper Monitor V2 démarré — check adaptatif par horizon", "INFO")

                while not stop_event.is_set():
                    try:
                        now = time.time()
                        with state_lock:
                            papers = [o for o in bot_state["orders"] if o["status"] in ("active", "pending")]

                        for order in papers:
                            try:
                                horizon = order.get("horizon", "daily")
                                interval = CHECK_INTERVALS.get(horizon, 900)
                                if now - order.get("last_checked", 0) < interval:
                                    continue

                                md = mt5_conn.get_market_data(order["pair"])
                                if md.get("status") == "ERROR":
                                    continue
                                current_price = md.get("current_price") or md.get("bid", 0)
                                if not current_price:
                                    continue

                                with state_lock:
                                    order["last_checked"] = now

                                pair     = order["pair"]
                                entry    = order["entry"]
                                sl       = order["sl"]
                                tp1      = order["tp1"]
                                direction = order["direction"]

                                # ── PENDING : attendre que le prix touche l'entrée ──
                                if order["status"] == "pending":
                                    # Vérifier expiration
                                    sig_t = order.get("signal_time", "")
                                    if sig_t:
                                        try:
                                            sig_dt = datetime.strptime(sig_t, "%Y-%m-%d %H:%M:%S")
                                            elapsed = (datetime.now() - sig_dt).total_seconds()
                                            if elapsed > EXPIRATION.get(horizon, 48 * 3600):
                                                with state_lock:
                                                    order["status"] = "expired"
                                                    order["closed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                                                    order["close_reason"] = "EXPIRED"
                                                log(f"[{pair}] ⏰ PENDING expiré ({elapsed/3600:.1f}h / {EXPIRATION.get(horizon,48*3600)/3600:.0f}h max)", "INFO")
                                                broadcast("order_update", {"action": "update", "order": order})
                                                _update_paper_trade(order)
                                                continue
                                        except Exception:
                                            pass

                                    # Activation si le prix atteint l'entrée
                                    activated = (direction in ("ACHAT", "BUY") and current_price <= entry) or \
                                                (direction not in ("ACHAT", "BUY") and current_price >= entry)
                                    if activated:
                                        # ── CHECK DISTANCE MAX (empêcher activation trop loin de l'entry) ──
                                        pip_size_pending = get_pip_size_safe(pair)
                                        distance_pips = abs(current_price - entry) / pip_size_pending
                                        
                                        # Seuils par horizon : scalp=20, intraday=40, daily=60, weekly=100
                                        MAX_DIST = {"scalp": 20, "intraday": 40, "daily": 60, "weekly": 100}
                                        max_dist = MAX_DIST.get(order.get("horizon", "daily"), 60)
                                        
                                        if distance_pips > max_dist:
                                            log(f"[{pair}] ⚠️ PENDING rejeté — distance {distance_pips:.0f} pips > max {max_dist} (prix {current_price} vs entry {entry})", "WARNING")
                                            with state_lock:
                                                order["status"] = "expired"
                                                order["closed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                                                order["close_reason"] = "TROP_LOIN"
                                            broadcast("order_update", {"action": "update", "order": order})
                                            _update_paper_trade(order)
                                            continue
                                        
                                        # ── CHECK R:R RÉEL à l'activation ──
                                        if direction in ("ACHAT", "BUY"):
                                            real_profit = tp1 - current_price
                                            real_risk = current_price - sl
                                        else:
                                            real_profit = current_price - tp1
                                            real_risk = sl - current_price
                                        
                                        real_rr = round(real_profit / real_risk, 2) if real_risk > 0 else 0
                                        
                                        if real_rr < 1.0:
                                            log(f"[{pair}] ⚠️ PENDING rejeté — R:R réel {real_rr} < 1.0 (profit {real_profit:.5f} vs risque {real_risk:.5f})", "WARNING")
                                            with state_lock:
                                                order["status"] = "expired"
                                                order["closed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                                                order["close_reason"] = "RR_TROP_BAS"
                                            broadcast("order_update", {"action": "update", "order": order})
                                            _update_paper_trade(order)
                                            continue
                                        
                                        # ── Activation OK ──
                                        with state_lock:
                                            order["status"] = "active"
                                            order["activated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                            order["activated_price"] = current_price
                                            order["real_rr"] = real_rr
                                        log(f"[{pair}] ✅ PENDING → ACTIF — prix ({current_price}) entry ({entry}) | Dist:{distance_pips:.0f} pips | R:R réel:{real_rr}", "SUCCESS")
                                        broadcast("order_update", {"action": "update", "order": order})
                                        _update_paper_trade(order)
                                    continue  # Ne vérifier SL/TP que si ACTIVE

                                # ── ACTIVE : vérifier SL et TP ──
                                pip_size = get_pip_size_safe(pair)
                                hit = None
                                close_price = current_price
                                real_entry = order.get("activated_price", entry)

                                if direction in ("ACHAT", "BUY"):
                                    pnl_pips = round((current_price - real_entry) / pip_size, 1)
                                    if current_price <= sl:   hit = "SL";  close_price = sl
                                    elif current_price >= tp1: hit = "TP1"; close_price = tp1
                                else:
                                    pnl_pips = round((real_entry - current_price) / pip_size, 1)
                                    if current_price >= sl:   hit = "SL";  close_price = sl
                                    elif current_price <= tp1: hit = "TP1"; close_price = tp1

                                if hit:
                                    final_pips = round(((close_price - real_entry) if direction in ("ACHAT","BUY") else (real_entry - close_price)) / pip_size, 1)
                                    pnl_money  = round(final_pips * 10 * order.get("volume", 0.1), 2)
                                    with state_lock:
                                        order["status"]       = "closed"
                                        order["closed_at"]    = datetime.now().strftime("%Y-%m-%d %H:%M")
                                        order["pnl_pips"]     = final_pips
                                        order["pnl_money"]    = pnl_money
                                        order["close_reason"] = hit
                                        order["close_price"]  = close_price
                                    emoji = "✅" if final_pips > 0 else "❌"
                                    log(f"{emoji} PAPER CLOSE {pair} — {hit} @ {close_price:.5f} | Entry théo:{entry} Réelle:{real_entry} | PnL:{final_pips:+.1f} pips ({pnl_money:+.2f}$) | {horizon}", "SUCCESS" if final_pips > 0 else "WARNING")
                                    broadcast("order_update", {"action": "update", "order": order})
                                    _update_paper_trade(order)
                                else:
                                    floating_money = round(pnl_pips * 10 * order.get("volume", 0.1), 2)
                                    with state_lock:
                                        order["pnl_pips"]  = pnl_pips
                                        order["pnl_money"] = floating_money
                                    broadcast("order_update", {"action": "update", "order": order})

                            except Exception as e:
                                log(f"Paper monitor erreur {order.get('pair')}: {e}", "WARNING")

                    except Exception as e:
                        log(f"Paper monitor erreur globale: {e}", "WARNING")

                    for _ in range(30):
                        if stop_event.is_set(): return
                        time.sleep(1)

            threading.Thread(target=paper_monitor, daemon=True).start()
            log("📝 Paper Trading Monitor V2 activé — check adaptatif par horizon", "INFO")
            _load_settings_override()
            _load_profiles_settings()
            _load_cooldowns()
            log(f"[Cooldown] {len(signal_cooldowns)} cooldown(s) actif(s) rechargés", "INFO")


        # ── Boucle HTF ─────────────────────────────────────────
        while not stop_event.is_set():
            if pause_event.is_set():
                if bot_state["status"] != "paused":
                    with state_lock: bot_state["status"] = "paused"
                    broadcast("status", {"status": "paused",
                                         "mt5_connected": bot_state["mt5_connected"],
                                         "mt5_status":    bot_state["mt5_status"]})
                time.sleep(1)
                continue

            # ── Décision Scheduler ──────────────────────────────
            from config import FORCE_ANALYZE
            sched = get_scheduler_decision(pairs, horizons, force_analyze=FORCE_ANALYZE)

            if not sched["should_run"]:
                with state_lock: bot_state["status"] = "waiting"
                broadcast("status", {
                    "status": "waiting",
                    "scheduler_reason": sched["reason"],
                    "mt5_connected": bot_state["mt5_connected"],
                    "mt5_status":    bot_state["mt5_status"],
                })
                log(f"⏳ Scheduler — {sched['reason']}", "INFO")
                for _ in range(sched["next_check_seconds"]):
                    if stop_event.is_set() or pause_event.is_set(): break
                    time.sleep(1)
                continue

            # On est en Killzone — lancer le cycle
            active_pairs    = sched["pairs"]
            active_horizons = sched["horizons"]
            log(f"🟢 {sched['reason']}", "INFO")

            # ── Alignement fermeture bougie M5 ──────────────────────
            _now = datetime.now()
            _seconds_past_minute = _now.second
            _minute_mod5 = _now.minute % 5
            # Secondes jusqu'à la prochaine minute ronde multiple de 5
            _wait_secs = (
                (5 - _minute_mod5) * 60 - _seconds_past_minute
                if _minute_mod5 != 0 or _seconds_past_minute > 2
                else 0
            )
            if _wait_secs > 240:
                _wait_secs = 0

            if _wait_secs > 0 and not stop_event.is_set():
                log(f"⏱️ Alignement bougie M5 — attente {_wait_secs}s "
                    f"(prochaine clôture: {(_now + timedelta(seconds=_wait_secs)).strftime('%H:%M:%S')})",
                    "DEBUG")
                for _ in range(_wait_secs):
                    if stop_event.is_set() or pause_event.is_set():
                        break
                    time.sleep(1)
            # ── Fin alignement ────────────────────────────────────────

            with state_lock:
                bot_state["status"] = "running"
                bot_state["cycle_count"] += 1
                cycle = bot_state["cycle_count"]
                if hasattr(mt5_conn, "simulation_mode"):
                    bot_state["mt5_status"] = "SIMU" if mt5_conn.simulation_mode else "LIVE"
                bot_state["mt5_connected"] = mt5_conn.connected

            broadcast("status", {"status": "running", "cycle": cycle,
                                  "mt5_status":    bot_state["mt5_status"],
                                  "mt5_connected": bot_state["mt5_connected"],
                                  "min_score":     bot_state["min_score"]})
            log(f"Cycle #{cycle} — {len(pairs)} paires × {len(horizons)} horizon(s)", "INFO")

            for pair in active_pairs:
                # Anti-doublon : si un trade actif ou pending existe déjà pour cette paire,
                # on skip TOUS les horizons de cette paire et on passe à la suivante.
                with state_lock:
                    existing_pair_orders = [o for o in bot_state["orders"] if o["pair"] == pair and o["status"] in ("active", "pending")]
                if existing_pair_orders:
                    log(f"[{pair}] Skip — trade déjà actif ({existing_pair_orders[0].get('timeframe', '?')})", "DEBUG")
                    continue

                for horizon in active_horizons:
                    if stop_event.is_set() or pause_event.is_set():
                        break
                    
                    # Vérifier cooldown signal périmé
                    horizon_key = horizon
                    cooldown_key = f"{pair}_{horizon_key}"
                    
                    if cooldown_key in signal_cooldowns:
                        if time.time() < signal_cooldowns[cooldown_key]:
                            remaining = int((signal_cooldowns[cooldown_key] - time.time()) / 60)
                            log(f"[{pair}] ⏸️ Cooldown {horizon_key} — {remaining}min restantes", "DEBUG")
                            continue  # Passer à l'horizon/paire suivant
                        else:
                            # Cooldown expiré, supprimer
                            del signal_cooldowns[cooldown_key]
                            _save_cooldowns()

                    # ── Gate HTF — éviter les analyses redondantes ───────────────────────────────
                    # H4 : max 1 fois/heure | D1 : max 1 fois/4h
                    # Permet au M5/H1 de tourner librement sans attendre H4/D1
                    if horizon in HTF_MIN_INTERVALS:
                        _htf_key = f"{pair}_{horizon}"
                        _last = _htf_last_run.get(_htf_key, 0)
                        _min_interval = HTF_MIN_INTERVALS[horizon]
                        if time.time() - _last < _min_interval:
                            _remaining_min = int((_min_interval - (time.time() - _last)) / 60)
                            log(f"[{pair}] ⏭️ Skip {horizon} — analysé il y a moins de "
                                f"{_min_interval//3600}h ({_remaining_min}min restantes)", "DEBUG")
                            continue
                        # Marquer le passage
                        _htf_last_run[_htf_key] = time.time()
                    # ─────────────────────────────────────────────────────────────────────────────

                    profile = HORIZON_PROFILES.get(horizon, HORIZON_PROFILES["scalp"])
                    try:
                        with state_lock: bot_state["current_pair"] = pair
                        broadcast("status", {"status": "running", "cycle": cycle,
                                              "current_pair": pair,
                                              "mt5_connected": bot_state["mt5_connected"],
                                              "mt5_status":    bot_state["mt5_status"],
                                              "current_api":   bot_state["current_api"]})
                        log(f"Analyse {pair} [{profile['label']}]...", "INFO")

                        result_holder = {}

                        def _analyze(p, rh):
                            try:

                                md = mt5_conn.get_market_data(p)

                                if md.get("status") == "ERROR":
                                    rh["error"] = md.get("message", "Données indisponibles")
                                    return

                                dfs = extract_dataframes(md)
                                
                                # ── Sélection des TFs selon le profil d'horizon ──
                                entry_tf = profile["entry_tf"]
                                bias_tf  = profile["bias_from"]
                                
                                df_entry = dfs.get(entry_tf, pd.DataFrame())
                                if df_entry.empty:
                                    rh["error"] = f"Pas de données {entry_tf} pour {p}"
                                    return

                                # ── Agent 2 : Time (gate immédiat — avant A1) ────────────────────
                                # Fix pipeline : A2 vérifie la Killzone EN PREMIER.
                                # Si hors KZ, on court-circuite tout le pipeline A1/A3/A4
                                # et on évite les requêtes API inutiles.
                                with state_lock: bot_state["current_api"] = "Agent 2 Time"
                                broadcast("status", {"current_api": bot_state["current_api"]})

                                broker_offset = getattr(config, "BROKER_UTC_OFFSET", 2)
                                agent2      = TimeSessionAgent(broker_utc_offset=broker_offset)
                                time_report = agent2.analyze(df_entry)

                                # Bypass Killzone pour les horizons longs (Daily/Weekly)
                                # ou si Force Analyze est activé
                                if profile["force_kz"] or getattr(config, "FORCE_ANALYZE", False):
                                    time_report["can_trade"] = True
                                    if time_report.get("trade_quality") == "no_trade":
                                        time_report["trade_quality"] = "medium"

                                # Gate KZ : si hors killzone et pas de bypass → sortie immédiate
                                if not time_report.get("can_trade", False):
                                    rh["entry_signal"] = {"signal": "NO_TRADE", "reason": "Out of Killzone or Closed day"}
                                    rh["diag"] = f"A2 can_trade=False | quality={time_report.get('trade_quality')} | A3 signal=NO_TRADE | reason=Out of Killzone or Closed day"
                                    return
                                # ─────────────────────────────────────────────────────────────────

                                # ── Agent 1 : Structure (multi-TF adaptatif) ──
                                with state_lock: bot_state["current_api"] = f"Agent 1 Structure ({'/'.join(profile['structure_tfs'])})"
                                broadcast("status", {"current_api": bot_state["current_api"]})

                                agent1   = StructureAgent(symbol=p)
                                mtf_data = {}
                                for tf in profile["structure_tfs"]:
                                    df_tf = dfs.get(tf, pd.DataFrame())
                                    if not df_tf.empty and len(df_tf) >= profile["min_data"]:
                                        mtf_data[tf] = df_tf

                                log(f"[{p}] MTF disponibles: {list(mtf_data.keys())} | DataFrames: {list(dfs.keys())}", "DEBUG")

                                if not mtf_data:
                                    rh["error"] = f"Données insuffisantes pour les TFs {profile['structure_tfs']}"
                                    return

                                structure_report = agent1.analyze_multi_tf(mtf_data)
                                structure_report["horizon"] = horizon  # OTE Tracker: clé de setup
                                
                                # Extraire le biais depuis le TF principal du profil
                                bias_data = structure_report.get(bias_tf, {})
                                # Fallback : prendre le premier TF disponible
                                if not bias_data:
                                    for tf in profile["structure_tfs"]:
                                        bias_data = structure_report.get(tf, {})
                                        if bias_data:
                                            break
                                
                                structure_report["bias"]             = bias_data.get("bias", structure_report.get("htf_alignment", "neutral"))
                                structure_report["swings"]           = bias_data.get("swings", [])
                                structure_report["fvg"]              = bias_data.get("fvg", [])
                                structure_report["order_blocks"]     = bias_data.get("order_blocks", [])
                                structure_report["bos_choch"]        = bias_data.get("bos_choch", [])
                                structure_report["liquidity_sweeps"] = bias_data.get("liquidity_sweeps", [])
                                structure_report["displacements"]    = bias_data.get("displacements", [])
                                structure_report["equal_levels"]     = bias_data.get("equal_levels", [])

                                key_levels = {}
                                if md.get("prev_day_high"):
                                    key_levels["PDH"] = md["prev_day_high"]
                                    key_levels["PDL"] = md["prev_day_low"]
                                if md.get("prev_week_high"):
                                    key_levels["PWH"] = md["prev_week_high"]
                                    key_levels["PWL"] = md["prev_week_low"]
                                structure_report["key_levels"] = key_levels

                                # ── Agent 3 : Entry (sur le TF d'entrée du profil) ──
                                with state_lock: bot_state["current_api"] = f"Agent 3 Entry ({entry_tf})"
                                broadcast("status", {"current_api": bot_state["current_api"]})

                                agent3 = EntryAgent(symbol=p)

                                # ── OTE Tracker : vérifier si un setup WAITING existe déjà ──
                                # Si oui, on réinjecte ses OBs/FVGs sauvegardés dans structure_report
                                # pour que agent3 puisse réévaluer avec les données persistées.
                                try:
                                    from agents.ict.ote_tracker import get_waiting_setup, invalidate_setup
                                    _current_bias = structure_report.get("bias", "neutral")
                                    _waiting = get_waiting_setup(p, horizon, _current_bias)
                                    if _waiting:
                                        # Le bias a changé → invalider le setup
                                        _saved_bias = _waiting.get("bias", "neutral")
                                        if _saved_bias != _current_bias:
                                            invalidate_setup(p, horizon, _saved_bias, reason="Bias changed")
                                            log(f"[{p}] OTE setup INVALIDATED — bias changé ({_saved_bias}→{_current_bias})", "DEBUG")
                                        else:
                                            # Réinjecter les OBs/FVGs sauvegardés si structure actuelle en manque
                                            if not structure_report.get("order_blocks"):
                                                structure_report["order_blocks"] = _waiting.get("obs", [])
                                            if not structure_report.get("fvg"):
                                                structure_report["fvg"] = _waiting.get("fvgs", [])
                                            log(f"[{p}] OTE setup WAITING récupéré ({_waiting.get('cycles_waited',0)} cycles)", "DEBUG")
                                except Exception as _ote_ex:
                                    log(f"[{p}] OTE Tracker erreur: {_ote_ex}", "DEBUG")

                                entry_signal = agent3.analyze(structure_report, time_report, df_entry)
                                entry_signal["_df_h1"] = dfs.get("H1", pd.DataFrame())
                                entry_signal["entry_tf"] = entry_tf   # P-A4b : timeframe d'analyse pour SOD

                                # ── DIAGNOSTIC DÉTAILLÉ ──────────────
                                diag_lines = []
                                diag_lines.append(f"A1 Bias={bias_data.get('bias','?')} | HTF={structure_report.get('htf_alignment','?')}")
                                diag_lines.append(f"   Swings={len(bias_data.get('swings',[]))} | FVG={len(bias_data.get('fvg',[]))} | OB={len(bias_data.get('order_blocks',[]))}")
                                diag_lines.append(f"   BOS/CHoCH={len(bias_data.get('bos_choch',[]))} | Sweeps={len(bias_data.get('liquidity_sweeps',[]))}")
                                diag_lines.append(f"A2 can_trade={time_report.get('can_trade')} | quality={time_report.get('trade_quality')}")
                                diag_lines.append(f"A3 signal={entry_signal.get('signal')} | reason={entry_signal.get('reason','OK')}")
                                if entry_signal.get('signal') != 'NO_TRADE':
                                    diag_lines.append(f"   entry={entry_signal.get('entry_price')} | sl={entry_signal.get('stop_loss')} | rr={entry_signal.get('rr_ratio')}")
                                
                                log(f"[{p}] {' | '.join(diag_lines[:3])}", "DEBUG")
                                log(f"[{p}] {' | '.join(diag_lines[3:])}", "DEBUG")

                                # ── Agent 4 : Macro ──────────────────
                                with state_lock: bot_state["current_api"] = "Agent 4 Macro"
                                broadcast("status", {"current_api": bot_state["current_api"]})

                                agent4   = MacroBiasAgent(target_pair=p)
                                dxy_data = None
                                if md.get("dxy_price"):
                                    dxy_data = {"trend": "unknown", "current_price": md["dxy_price"]}
                                macro_report = agent4.analyze(dxy_data=dxy_data, current_time=md.get("ny_time"))
                                df_d1 = dfs.get("D1", pd.DataFrame())
                                if not df_d1.empty and len(df_d1) >= 60:
                                    macro_report["ipda_ranges"] = agent4.analyze_ipda_ranges(df_d1)
                                macro_report["quarterly"] = agent4.get_quarterly_context(
                                    md.get("date", "2026-01-01") + " 10:00"
                                )

                                # ── Agent 5 : Orchestrator ───────────
                                with state_lock: bot_state["current_api"] = "Agent 5 Decision"
                                broadcast("status", {"current_api": bot_state["current_api"]})

                                agent5       = OrchestratorAgent(
                                    account_balance = getattr(config, "ACCOUNT_BALANCE", 500.0),
                                    risk_percent    = getattr(config, "RISK_PERCENT", 1.0),
                                )
                                
                                # ── KS4 : injecter le spread dans entry_signal ───────────────────────────────
                                # TwelveData ne fournit pas le spread bid/ask en temps réel sur le plan Basic.
                                # On estime le spread depuis la dernière bougie M5 : spread ≈ open - close de
                                # la bougie la plus récente (approximation grossière mais cohérente pour le gate).
                                # Si les données sont insuffisantes, on laisse current_spread_pips absent → gate inactif.
                                try:
                                    df_m5_ks4 = dfs.get("M5", pd.DataFrame())
                                    if not df_m5_ks4.empty and len(df_m5_ks4) >= 1:
                                        last = df_m5_ks4.iloc[-1]
                                        raw_spread = abs(float(last['high']) - float(last['low']))
                                        # Convertir en pips selon la paire
                                        is_jpy_pair = p.endswith("JPY") or p in ("XAUUSD", "BTCUSD", "ETHUSD")
                                        pip_divisor = 0.01 if is_jpy_pair else 0.0001
                                        spread_pips = raw_spread / pip_divisor
                                        # Guard : si spread_pips > 50, c'est le range M5, pas un spread → ignorer
                                        if spread_pips <= 50:
                                            entry_signal["current_spread_pips"] = round(spread_pips, 1)
                                except Exception:
                                    pass  # gate KS4 inactif si erreur
                                # ─────────────────────────────────────────────────────────────────────────────

                                decision_obj = agent5.calculate_decision(
                                    structure_report, time_report, entry_signal, macro_report
                                )

                                dec  = decision_obj.get("decision", "NO_TRADE")
                                conf = decision_obj.get("global_confidence", 0)

                                # ── Agent 6 : LLM Validateur (si activé et si EXECUTE et score >= 60) ──
                                llm_result = None
                                meta_decision = "NO_TRADE"  # initialisé ici, mis à jour après meta.compare()
                                meta_score = 0
                                if llm_validator and llm_validator.enabled and dec.startswith("EXECUTE") and conf >= 0.60:
                                    with state_lock: bot_state["current_api"] = "Agent 6 LLM Validator"
                                    broadcast("status", {"current_api": bot_state["current_api"]})
                                    log(f"[{p}] 🧠 Validation LLM en cours...", "INFO")

                                    llm_result = llm_validator.validate(
                                        structure_report, time_report, entry_signal,
                                        macro_report, decision_obj, p, horizon
                                    )

                                    if not llm_result.get("skipped"):
                                        verdict = llm_result.get("verdict", "SKIP")
                                        llm_score = llm_result.get("total", 0)
                                        llm_conf = llm_result.get("confiance_llm", 0.5)
                                        cost = llm_result.get("cost_usd", 0)

                                        log(f"[{p}] 🧠 LLM: {verdict} | Score: {llm_score}/100 | Coût: ${cost:.4f}", "INFO")

                                        # Guard : VALIDÉ avec score < 40 = incohérence → traiter comme REJETÉ
                                        if verdict != "REJETÉ" and llm_score < 40:
                                            verdict = "REJETÉ"
                                            log(f"[{p}] ⚠️ LLM score trop bas ({llm_score}/100) malgré verdict VALIDÉ → forcé REJETÉ", "WARNING")

                                        if verdict == "REJETÉ":
                                            # LLM dit NON → bloquer complètement le trade
                                            decision_obj["global_confidence"] = 0.0
                                            conf = 0.0
                                            dec = "NO_TRADE"
                                            log(f"[{p}] 🚫 LLM a rejeté le signal — trade BLOQUÉ: {', '.join(llm_result.get('red_flags', llm_result.get('raisons', [])))}", "WARNING")
                                        else:
                                            algo_conf = decision_obj.get("global_confidence", 0)
                                            blended = algo_conf * 0.7 + llm_conf * 0.3
                                            decision_obj["global_confidence"] = blended
                                            conf = blended
                                            log(f"[{p}] ✅ Signal VALIDÉ par le LLM (confiance ajustée: {blended:.0%})", "SUCCESS")

                                        llm_warnings = llm_result.get("red_flags", [])
                                    else:
                                        log(f"[{p}] 🧠 LLM skip: {llm_result['raisons'][0]}", "DEBUG")

                                elif llm_validator and llm_validator.enabled and dec.startswith("EXECUTE") and conf < 0.60:
                                    log(f"[{p}] 🧠 LLM skip — score trop bas ({conf:.0%} < 60%)", "DEBUG")

                                # ── Agent Elliott Wave (école 2) ─────
                                elliott_signal = {"school": "elliott", "pair": p, "signal": "NO_TRADE", "score": 0, "confidence": 0.0, "reasons": [], "warnings": []}
                                try:
                                    with state_lock: bot_state["current_api"] = "Elliott Wave"
                                    broadcast("status", {"current_api": bot_state["current_api"]})
                                    elliott_signal = run_elliott_analysis(dfs, pair=p, timeframe=entry_tf)
                                    e_sig = elliott_signal.get("signal", "NO_TRADE")
                                    e_score = elliott_signal.get("score", 0)
                                    if e_sig != "NO_TRADE":
                                        log(f"[{p}] 📊 Elliott: {e_sig} | Score: {e_score}/100 | {'; '.join(elliott_signal.get('reasons', [])[:2])}", "INFO")
                                    elif e_score > 0:
                                        log(f"[{p}] 📊 Elliott: NO_TRADE (score {e_score}) | {'; '.join(elliott_signal.get('reasons', [])[:1])}", "DEBUG")
                                except Exception as e_err:
                                    log(f"[{p}] Elliott erreur: {e_err}", "DEBUG")

                                # ── Agent VSA / Wyckoff (école 3) ────
                                vsa_signal = {"school": "vsa", "pair": p, "signal": "NO_TRADE", "score": 0, "confidence": 0.0, "reasons": [], "warnings": []}
                                try:
                                    with state_lock: bot_state["current_api"] = "VSA Wyckoff"
                                    broadcast("status", {"current_api": bot_state["current_api"]})
                                    from config import GEMINI_API_KEY
                                    vsa_orchestrator = VSAOrchestrator(gemini_api_key=GEMINI_API_KEY, enable_charts=True)
                                    vsa_res = vsa_orchestrator.get_signal_for_meta(symbol=p, timeframe=entry_tf, df=dfs[entry_tf])
                                    
                                    v_sig = vsa_res.get("direction", "NEUTRAL")
                                    v_action = vsa_res.get("action", "IGNORE")
                                    
                                    if v_action == "IGNORE" or v_sig == "NEUTRAL":
                                        vsa_std_sig = "NO_TRADE"
                                    elif v_sig == "LONG":
                                        vsa_std_sig = "BUY"
                                    elif v_sig == "SHORT":
                                        vsa_std_sig = "SELL"
                                    else:
                                        vsa_std_sig = "NO_TRADE"
                                        
                                    v_score = vsa_res.get("score", 0)
                                    v_phase = vsa_res.get("wyckoff_phase", "?")
                                    vsa_signal = {
                                        "school": "vsa",
                                        "pair": p,
                                        "signal": vsa_std_sig,
                                        "score": v_score,
                                        "confidence": v_score / 100,
                                        "reasons": [f"Signal: {vsa_res.get('signal', '?')} (Phase {v_phase})"],
                                        "warnings": vsa_res.get("invalidations", []),
                                        "details": vsa_res
                                    }
                                    if vsa_std_sig != "NO_TRADE":
                                        log(f"[{p}] 📈 VSA: {vsa_std_sig} | Score: {v_score}/100 | Phase: {v_phase}", "INFO")
                                    elif v_score > 0:
                                        log(f"[{p}] 📈 VSA: NO_TRADE (score {v_score}) | Phase: {v_phase}", "DEBUG")
                                except Exception as v_err:
                                    log(f"[{p}] VSA erreur: {v_err}", "DEBUG")

                                # ── Méta-Orchestrateur (fusion des écoles) ──
                                # Construire le signal ICT au format standard
                                ict_signal = {
                                    "school": "ict",
                                    "pair": p,
                                    "signal": "BUY" if dec == "EXECUTE_BUY" else ("SELL" if dec == "EXECUTE_SELL" else "NO_TRADE"),
                                    "score": int(conf * 100) if conf <= 1.0 else int(conf),
                                    "confidence": conf if conf <= 1.0 else conf / 100,
                                    "entry": decision_obj.get("entry_price", 0),
                                    "sl": decision_obj.get("stop_loss", 0),
                                    "tp1": decision_obj.get("tp1", 0),
                                    "reasons": decision_obj.get("reasons", []),
                                    "warnings": [],
                                }

                                # Comparer avec le méta-orchestrateur
                                meta = MetaOrchestrator()
                                meta_result = meta.compare([ict_signal, elliott_signal, vsa_signal])

                                # Logger le résultat méta
                                meta_decision = meta_result.get("decision", "NO_TRADE")
                                meta_score = meta_result.get("score", 0)
                                meta_alignment = meta_result.get("alignment", "")
                                if meta_decision != "NO_TRADE" and elliott_signal.get("signal") != "NO_TRADE":
                                    log(f"[{p}] 🔀 Méta: {meta_decision} | Score: {meta_score} | {meta_alignment}", "INFO")

                                # ── Gate LLM méta : ICT=NO_TRADE mais méta ≥ 60 → LLM valide ──
                                # Placée ICI, après meta.compare(), pour avoir meta_decision réel
                                if (llm_validator and llm_validator.enabled
                                        and llm_result is None          # LLM ICT n'a pas déjà tourné
                                        and meta_decision in ("BUY", "SELL")
                                        and meta_score >= 60):
                                    with state_lock: bot_state["current_api"] = "Agent 6 LLM Validator"
                                    broadcast("status", {"current_api": bot_state["current_api"]})
                                    log(f"[{p}] 🧠 Validation LLM (MetaSignal) en cours...", "INFO")
                                    try:
                                        llm_result = llm_validator.validate(
                                            structure_report, time_report, entry_signal,
                                            macro_report, decision_obj, p, horizon
                                        )
                                        if not llm_result.get("skipped"):
                                            verdict = llm_result.get("verdict", "SKIP")
                                            llm_score = llm_result.get("total", 0)
                                            llm_conf  = llm_result.get("confiance_llm", 0.5)
                                            cost      = llm_result.get("cost_usd", 0)
                                            log(f"[{p}] 🧠 LLM: {verdict} | Score: {llm_score}/100 | Coût: ${cost:.4f}", "INFO")
                                            # Guard : VALIDÉ avec score < 40 → forcer REJETÉ
                                            if verdict != "REJETÉ" and llm_score < 40:
                                                verdict = "REJETÉ"
                                                log(f"[{p}] ⚠️ LLM méta score trop bas ({llm_score}/100) → forcé REJETÉ", "WARNING")

                                            if verdict == "REJETÉ":
                                                meta_decision = "NO_TRADE"
                                                meta_score    = 0
                                                dec           = "NO_TRADE"
                                                conf          = 0.0
                                                log(f"[{p}] 🚫 LLM a rejeté le signal méta — trade BLOQUÉ: {', '.join(llm_result.get('red_flags', []))}", "WARNING")
                                    except Exception as llm_err:
                                        log(f"[{p}] LLM méta erreur: {llm_err}", "DEBUG")

                                # ── Narrative ────────────────────────
                                bias     = structure_report.get("bias", "neutral")
                                htf      = structure_report.get("htf_alignment", "unknown")
                                kz       = time_report.get("killzone", {})
                                kz_name  = kz.get("name", "Hors KZ") if isinstance(kz, dict) else "Hors KZ"
                                quality  = time_report.get("trade_quality", "no_trade")
                                n_swings = len(structure_report.get("swings", []))
                                n_fvg    = len(structure_report.get("fvg", []))
                                n_ob     = len(structure_report.get("order_blocks", []))
                                signal   = entry_signal.get("signal", "NO_TRADE")
                                rr       = entry_signal.get("rr_ratio", 0)

                                narrative = (
                                    f"**{p} — {profile['label']}**\n\n"
                                    f"Structure ({bias_tf}): {bias.upper()} | HTF: {htf} | "
                                    f"Swings: {n_swings} | FVG: {n_fvg} | OB: {n_ob}\n\n"
                                    f"Timing: {kz_name} | Qualité: {quality}\n\n"
                                    f"Signal ({entry_tf}): {signal} | R:R: {rr} | Confiance: {conf:.0%}\n\n"
                                )
                                # Diagnostic détaillé
                                narrative += "--- DIAGNOSTIC ---\n"
                                for dl in diag_lines:
                                    narrative += f"{dl}\n"
                                narrative += "\n"

                                # Ajouter Elliott à la narrative
                                if elliott_signal.get("signal") != "NO_TRADE" or elliott_signal.get("score", 0) > 0:
                                    narrative += f"\n--- ELLIOTT WAVE ---\n"
                                    narrative += f"Signal: {elliott_signal.get('signal')} | Score: {elliott_signal.get('score')}/100\n"
                                    ew_pos = elliott_signal.get("details", {}).get("position", {})
                                    if ew_pos:
                                        narrative += f"Position: {ew_pos.get('status', '?')} | Direction: {ew_pos.get('direction', '?')}\n"
                                        if ew_pos.get('next_expected'):
                                            narrative += f"Attendu: {ew_pos['next_expected']}\n"
                                    ew_reasons = elliott_signal.get("reasons", [])
                                    if ew_reasons:
                                        narrative += f"Raisons: {'; '.join(ew_reasons[:3])}\n"
                                    ew_warnings = elliott_signal.get("warnings", [])
                                    if ew_warnings:
                                        narrative += f"Warnings: {'; '.join(ew_warnings[:2])}\n"

                                # Ajouter VSA à la narrative
                                if vsa_signal.get("signal") != "NO_TRADE" or vsa_signal.get("score", 0) > 0:
                                    narrative += f"\n--- VSA / WYCKOFF ---\n"
                                    narrative += f"Signal: {vsa_signal.get('signal')} | Score: {vsa_signal.get('score')}/100\n"
                                    vsa_det = vsa_signal.get("details", {})
                                    if vsa_det:
                                        narrative += f"Phase Wyckoff: {vsa_det.get('wyckoff_phase', '?')} ({vsa_det.get('wyckoff_cycle', '?')})\n"
                                        narrative += f"Détection: {vsa_det.get('signal', '?')} (Confiance: {vsa_det.get('confiance', '?')})\n"
                                        if vsa_det.get("commentaire"):
                                            narrative += f"Analyse Algo: {vsa_det['commentaire']}\n"
                                    vsa_warn = vsa_signal.get("warnings", [])
                                    if vsa_warn:
                                        narrative += f"Warnings: {'; '.join(vsa_warn[:2])}\n"

                                # Ajouter le résultat LLM à la narrative
                                if llm_result and not llm_result.get("skipped"):
                                    narrative += f"\n--- LLM VALIDATEUR ---\n"
                                    narrative += f"Verdict: {llm_result.get('verdict')} | Score LLM: {llm_result.get('total')}/100\n"
                                    narrative += f"Timing: {llm_result.get('score_timing',0)}/20 | Structure: {llm_result.get('score_structure',0)}/20 | "
                                    narrative += f"Entrée: {llm_result.get('score_entree',0)}/20 | Cible: {llm_result.get('score_cible',0)}/20 | SMT: {llm_result.get('score_smt',0)}/20\n"
                                    if llm_result.get("narrative_ict"):
                                        narrative += f"Narrative ICT: {llm_result['narrative_ict']}\n"
                                    if llm_result.get("red_flags"):
                                        narrative += f"Red Flags: {', '.join(llm_result['red_flags'])}\n"
                                    narrative += f"Coût: ${llm_result.get('cost_usd', 0):.4f}\n"

                                if dec != "NO_TRADE":
                                    narrative += (
                                        f"DÉCISION: {dec}\n"
                                        f"Entry: {decision_obj.get('entry_price')} | "
                                        f"SL: {decision_obj.get('stop_loss')} | "
                                        f"TP1: {decision_obj.get('tp1')}\n"
                                        f"Raisons: {', '.join(decision_obj.get('reasons', []))}"
                                    )
                                else:
                                    narrative += f"NO TRADE: {decision_obj.get('reason', 'Pas de setup valide')}"

                                # ── Décision finale : MetaScore prime sur ICT seul ──
                                dashboard_decision = "RESTER_DEHORS"
                                score = 0
                                
                                # S'assurer que dec et conf sont valides
                                dec_str = str(dec) if dec else "NO_TRADE"
                                conf_val = float(conf) if conf is not None else 0.0

                                if dec_str.startswith("EXECUTE") and conf_val >= 0.70:
                                    score = int(conf_val * 100) if conf_val <= 1.0 else int(conf_val)
                                    dashboard_decision = "OUVRIR"
                                    log(f"[{p}] ✅ ICT EXECUTE ≥ 70% → OUVRIR ({score}/100)", "DEBUG")
                                elif meta_decision in ("BUY", "SELL") and meta_score >= 70 and dec_str == "NO_TRADE":
                                    # ICT dit NO_TRADE mais méta (Elliott) donne un signal fort
                                    score = meta_score
                                    dashboard_decision = "OUVRIR"
                                    log(f"[{p}] ✅ MetaScore {meta_score}/100 ≥ 70 → OUVRIR ({meta_decision})", "DEBUG")
                                    # Injecter les niveaux méta dans decision_obj si ICT n'en a pas
                                    if not decision_obj.get("entry_price"):
                                        # meta_result retourne entry/sl/tp1 directement
                                        meta_entry = meta_result.get("entry") or 0
                                        meta_sl    = meta_result.get("sl") or 0
                                        meta_tp1   = meta_result.get("tp1") or 0
                                        if meta_entry and meta_sl and meta_tp1:
                                            decision_obj["entry_price"] = meta_entry
                                            decision_obj["stop_loss"]   = meta_sl
                                            decision_obj["tp1"]         = meta_tp1
                                            decision_obj["decision"]    = f"EXECUTE_{meta_decision}"
                                            decision_obj["direction"]   = meta_decision.lower() if meta_decision else "unknown"
                                            log(f"[{p}] 📌 Niveaux méta utilisés — Entry:{meta_entry} SL:{meta_sl} TP1:{meta_tp1}", "DEBUG")
                                        else:
                                            dashboard_decision = "RESTER_DEHORS"
                                            log(f"[{p}] ⚠️ MetaScore ≥ 70 mais niveaux méta absents — RESTER_DEHORS", "WARNING")
                                else:
                                    score = int(conf_val * 100) if conf_val <= 1.0 else int(conf_val)
                                    dashboard_decision = "RESTER_DEHORS"
                                    # Gate Logger Meta — toutes écoles confondues
                                    try:
                                        from agents.gate_logger import log_meta_blocked
                                        _ict_e = (entry_signal or {}).get("entry_price") or 0
                                        _ict_s = (entry_signal or {}).get("stop_loss") or 0
                                        _ict_t = (entry_signal or {}).get("tp1") or 0
                                        _ell_e = (elliott_signal or {}).get("entry") or 0
                                        _ell_s = (elliott_signal or {}).get("sl") or 0
                                        _ell_t = (elliott_signal or {}).get("tp1") or 0
                                        _entry = _ict_e or _ell_e
                                        _sl    = _ict_s or _ell_s
                                        _tp1   = _ict_t or _ell_t
                                        if _entry and _sl and _tp1:
                                            log_meta_blocked(
                                                pair=p,
                                                horizon=horizon,
                                                final_gate="RESTER_DEHORS",
                                                ict_signal=(entry_signal or {}).get("signal", "NO_TRADE"),
                                                ict_score=score,
                                                ict_reason=(entry_signal or {}).get("reason", ""),
                                                elliott_signal=(elliott_signal or {}).get("signal", "NO_TRADE"),
                                                elliott_score=(elliott_signal or {}).get("score", 0),
                                                meta_score=meta_score,
                                                meta_direction=meta_decision or "NO_TRADE",
                                                entry=_entry, sl=_sl, tp1=_tp1,
                                                a1_bias=(structure_report or {}).get("bias"),
                                                htf_alignment=(structure_report or {}).get("htf_alignment"),
                                            )
                                    except Exception:
                                        pass

                                # ── Pure PA Profile — Parallèle et Indépendant ──────────────────
                                # Tourne quelle que soit la décision ICT.
                                # Utilise les MÊMES données de marché (dfs) — 0 appel API supplémentaire.
                                pure_pa_result = None
                                if _PURE_PA_AVAILABLE:
                                    try:
                                        with state_lock: bot_state["current_api"] = "Pure PA Profile"
                                        broadcast("status", {"current_api": bot_state["current_api"]})
                                        pa_agent = PurePAOrchestrator(symbol=p, timeframe=entry_tf)
                                        df_pa = dfs.get(entry_tf, pd.DataFrame())
                                        if not df_pa.empty:
                                            pure_pa_result = pa_agent.evaluate(df_pa, time_report=time_report)
                                            pa_action = pure_pa_result.get("action", "NO_TRADE")
                                            if pa_action == "new":
                                                log(f"[{p}] 🎯 Pure PA: {pure_pa_result.get('direction','?').upper()} | R:R {pure_pa_result.get('rationale','')[:50]}", "INFO")
                                            else:
                                                log(f"[{p}] 🎯 Pure PA: NO_TRADE — {pure_pa_result.get('rationale','')[:60]}", "DEBUG")
                                    except Exception as pa_err:
                                        log(f"[{p}] Pure PA erreur (non bloquant): {pa_err}", "DEBUG")

                                # ── Convergence State — ICT + Pure PA sur la même paire ───────
                                ict_direction = ("buy" if dec == "EXECUTE_BUY" else ("sell" if dec == "EXECUTE_SELL" else None))
                                pa_direction  = pure_pa_result.get("direction") if pure_pa_result and pure_pa_result.get("action") == "new" else None
                                convergence_state = "independent"
                                if ict_direction and pa_direction and ict_direction == pa_direction:
                                    convergence_state = "aligned"
                                    log(f"[{p}] ✨ CONVERGENCE ICT+PurePA — tous deux {ict_direction.upper()}", "INFO")

                                profile_version = profiles_settings.get("profile_version", "v1.0")

                                with state_lock:
                                    bot_state["current_api"] = f"Algo ({profile['label']})"

                                rh.update({
                                    "ict_raw":      narrative,
                                    "ict_analyzed": {"approved": dec != "NO_TRADE", "confidence_score": score},
                                    "final": {
                                        "global_score":      score,
                                        "vsa_score":         meta_result.get("vsa_score", 0),
                                        "elliott_score":     meta_result.get("elliott_score", 0),
                                        "final_decision":    dashboard_decision,
                                        "raw":               narrative,
                                        "rationale":         decision_obj.get("reason", ""),
                                        "should_trade":      dec.startswith("EXECUTE"),
                                        # Tags multi-profils (Étape 4)
                                        "profile_id":        "ict_strict",
                                        "profile_version":   profile_version,
                                        "active_gates":      decision_obj.get("active_gates", []),
                                        "convergence_state": convergence_state,
                                    },
                                    "market_data":    md,
                                    "decision_obj":   decision_obj,
                                    "pure_pa_result": pure_pa_result,  # Pure PA disponible dans le résultat
                                })
                            except Exception as ex:
                                import traceback
                                rh["error"] = f"{ex}\n{traceback.format_exc()}"

                        t = threading.Thread(target=_analyze, args=(pair, result_holder), daemon=True)
                        t.start()

                        # Attente réactive — timeout 120s (algorithmes, pas LLM)
                        max_wait, waited = 120, 0
                        while t.is_alive() and waited < max_wait:
                            if stop_event.is_set():
                                log(f"Arrêt forcé pendant l'analyse de {pair}.", "INFO")
                                return
                            time.sleep(1)
                            waited += 1

                        if t.is_alive():
                            log(f"{pair} timeout 2min — paire ignorée", "WARNING")
                            continue

                        time.sleep(1)

                        # ── Traitement du résultat ───────────────────
                        if "error" in result_holder:
                            err_msg = result_holder["error"]
                            log(f"Erreur {pair}: {err_msg[:200]}", "ERROR")
                            error_report = {
                                "pair":         pair,
                                "global_score": 0,
                                "score":        0,
                                "decision":     "ERREUR",
                                "direction":    "NEUTRE",
                                "school":       "ict",
                                "opened_at":    datetime.now().strftime("%H:%M:%S"),
                                "scores":       {},
                                "ict_bias":     "ERREUR",
                                "ict_dol":      "INCONNU",
                                "ict_scenario": f"L'analyse a échoué:\n{err_msg[:300]}",
                                "narrative":    f"### Erreur d'analyse ###\n\n{err_msg[:300]}",
                            }
                            broadcast("analysis_report", error_report)
                            with state_lock:
                                bot_state["last_reports"][pair] = error_report
                            continue

                        if "ict_raw" not in result_holder or "final" not in result_holder:
                            # ── Bypass pour le hors Killzone sans logger une grosse erreur ──
                            diag = result_holder.get("diag", "")
                            if "Out of Killzone" in diag or "Closed day" in diag:
                                log(f"{pair} [{horizon}] ⏭️ SKIP — Hors Killzone ou marché fermé", "INFO")
                                continue
                                
                            missing_keys = [k for k in ["ict_raw", "final"] if k not in result_holder]
                            found_keys = list(result_holder.keys())
                            log(f"Erreur {pair} [{horizon}]: résultat incomplet (clés manquantes: {missing_keys}). Clés présentes: {found_keys}", "ERROR")
                            continue

                        ict_raw      = result_holder.get("ict_raw", "")
                        ict_analyzed = result_holder.get("ict_analyzed", {"approved": False, "confidence_score": 0})
                        final        = result_holder.get("final", {})
                        score        = final.get("global_score", 0)
                        decision     = final.get("final_decision", "RESTER_DEHORS")

                        log(f"{pair} [{horizon}] → {decision} | Score: {score}/100", "INFO")

                        report = {
                            "pair":         pair,
                            "global_score": score,
                            "score":        score,
                            "decision":     decision,
                            "direction":    decision,
                            "school":       "ict",
                            "opened_at":    datetime.now().strftime("%H:%M:%S"),
                            "scores":       {},
                            "ict_bias":     result_holder.get("market_data", {}).get("bias", "N/A"),
                            "ict_dol":      "N/A",
                            "ict_pd_arrays": "N/A",
                            "ict_scenario": ict_raw[:200],
                            "ict_model":    "Algo ICT 5 Agents",
                            "checklist":    _build_algo_checklist(decision_obj=result_holder.get("decision_obj")),
                            "narrative":    ict_raw,
                            "status":       "closed" if decision == "RESTER_DEHORS" else "pending",
                            "pnl_money":    0.0,
                            "pnl_pips":     0.0,
                            "raw_ict":      ict_raw,
                        }

                        broadcast("analysis_report", report)
                        with state_lock:
                            bot_state["last_reports"][pair] = report
                            bot_state["last_analysis_time"] = datetime.now().isoformat()
                        broadcast("report", report)

                        decision_obj = result_holder.get("decision_obj")
                        # Créer un trade seulement si la décision finale est OUVRIR
                        # ET que les niveaux sont présents (entry/sl/tp1 non nuls)
                        _can_open = (
                            decision == "OUVRIR"
                            and decision_obj
                            and decision_obj.get("entry_price", 0) != 0
                            and decision_obj.get("stop_loss", 0) != 0
                            and decision_obj.get("tp1", 0) != 0
                        )
                        if _can_open:
                            direction_str = "ACHAT" if "bullish" in decision_obj.get("direction", "").lower() or "BUY" in decision_obj.get("decision", "").upper() else "VENTE"
                            
                            # ── Circuit Breaker Gate ──────────────────────────────────
                            if _CB_AVAILABLE and _circuit_breaker:
                                cb_status = _circuit_breaker.get_status()
                                if cb_status.get("active", False):
                                    log(f"[{pair}] 🔴 Circuit Breaker ACTIF — {cb_status.get('reason', '')} "
                                        f"| Trades aujourd'hui: {cb_status.get('trades_today', 0)}", "WARNING")
                                    continue  # skip ce symbole, passer au suivant
                                # Notifier le CB qu'un trade va être ouvert/enregistré
                                if hasattr(_circuit_breaker, "record_trade_opened"):
                                    _circuit_breaker.record_trade_opened()
                            # ── Fin Circuit Breaker Gate ──────────────────────────────

                            # Correction 3 : Blocage R:R Aberrant sur M5
                            _rr_check = round(abs(float(decision_obj.get("tp1", 0)) - float(decision_obj.get("entry_price", 0))) / abs(float(decision_obj.get("entry_price", 0)) - float(decision_obj.get("stop_loss", 0))), 2) if decision_obj.get("entry_price", 0) and decision_obj.get("stop_loss", 0) and abs(float(decision_obj.get("entry_price", 0)) - float(decision_obj.get("stop_loss", 0))) > 0 else 0
                            if profile["entry_tf"] == "M5" and _rr_check > 8:
                                log(f"[{pair}] 🚫 ICT R:R aberrant ({_rr_check} > 8) sur M5 — Bloqué (Correction 3)", "WARNING")
                                continue

                            new_order = make_order(
                                pair=pair, school="ict", direction=direction_str,
                                entry=decision_obj.get("entry_price", 0),
                                sl=decision_obj.get("stop_loss", 0),
                                tp1=decision_obj.get("tp1", 0),
                                tp2=decision_obj.get("tp2", 0),
                                score=score, narrative=ict_raw,
                                checklist=_build_algo_checklist(decision_obj=decision_obj),
                                status="pending", timeframe=profile["entry_tf"],
                                profile_id="ict_strict",
                                active_gates=decision_obj.get("active_gates", []),
                                convergence_state=convergence_state,
                                ttl_seconds=1800
                            )

                            action = None
                            with state_lock:
                                active_or_recent = any(
                                    o["pair"] == pair and
                                    (o["status"] == "active" or
                                     (o["status"] == "cancelled" and
                                      (datetime.now() - datetime.strptime(
                                          o.get("opened_at", "2000-01-01 00:00"), "%Y-%m-%d %H:%M"
                                      )).total_seconds() < 3600))
                                    for o in bot_state["orders"]
                                )

                                if not active_or_recent:
                                    existing = next(
                                        (o for o in bot_state["orders"] if o["pair"] == pair and o["status"] == "pending"),
                                        None
                                    )
                                    if existing:
                                        for key in ["direction","entry","sl","tp1","tp2","score","narrative","checklist"]:
                                            existing[key] = new_order[key]
                                        order = existing
                                        action = "update"
                                    else:
                                        bot_state["orders"].append(new_order)
                                        order = new_order
                                        action = "new"
                                else:
                                    order = None

                            # Paper Trading : PENDING vs ACTIVE selon le prix live
                            if paper_mode and order and order["status"] == "pending":
                                # Métadonnées horizon
                                horizon_map = {
                                    "M5": "scalp", "M15": "scalp",
                                    "H1": "intraday",
                                    "H4": "daily",
                                    "D1": "weekly", "W1": "weekly", "MN": "weekly"
                                }
                                tf = order.get("timeframe", "H4")
                                order["horizon"]      = horizon_map.get(tf, "daily")
                                cooldown_key = f"{pair}_{order['horizon']}"
                                order["signal_time"]  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                order["last_checked"] = 0
                                order["activated_at"] = None

                                # Récupérer le prix live
                                try:
                                    md_live = mt5_conn.get_market_data(pair)
                                    sp = md_live.get("current_price") or md_live.get("bid", 0)
                                except Exception:
                                    sp = 0
                                order["signal_price"] = sp

                                entry = order["entry"]
                                tp1   = order["tp1"]
                                sl    = order["sl"]
                                
                                # Déterminer PENDING ou ACTIVE direct, ou signal obsolète
                                cancel = False
                                if sp and sp > 0:
                                    if order["direction"] in ("ACHAT", "BUY"):
                                        if sp >= tp1:
                                            log(f"[{pair}] ⚠️ Signal obsolète — prix ({sp}) déjà au-dessus du TP1 ({tp1})", "WARNING")
                                            signal_cooldowns[cooldown_key] = time.time() + COOLDOWN_DURATIONS.get(order["horizon"], 8 * 3600)
                                            _save_cooldowns()
                                            log(f"[{pair}] ⏸️ Cooldown activé ({order['horizon']}) — prochaine analyse dans {COOLDOWN_DURATIONS.get(order['horizon'], 8 * 3600) // 60}min", "DEBUG")
                                            cancel = True
                                        elif sp <= sl:
                                            log(f"[{pair}] ⚠️ Signal obsolète — prix ({sp}) déjà sous le SL ({sl})", "WARNING")
                                            signal_cooldowns[cooldown_key] = time.time() + COOLDOWN_DURATIONS.get(order["horizon"], 8 * 3600)
                                            _save_cooldowns()
                                            log(f"[{pair}] ⏸️ Cooldown activé ({order['horizon']}) — prochaine analyse dans {COOLDOWN_DURATIONS.get(order['horizon'], 8 * 3600) // 60}min", "DEBUG")
                                            cancel = True
                                        else:
                                            # ── CHECK DISTANCE MAX (activation directe BUY) ──
                                            pip_size_check = get_pip_size_safe(pair)
                                            dist_pips = abs(sp - entry) / pip_size_check
                                            MAX_DIST_DIRECT = {"scalp": 15, "intraday": 30, "daily": 50, "weekly": 80}
                                            max_d = MAX_DIST_DIRECT.get(order.get("horizon", "daily"), 50)
                                            if dist_pips > max_d:
                                                log(f"[{pair}] ⚠️ Signal trop loin — {dist_pips:.0f} pips d'écart (max {max_d}) — ANNULÉ", "WARNING")
                                                signal_cooldowns[cooldown_key] = time.time() + COOLDOWN_DURATIONS.get(order["horizon"], 8 * 3600)
                                                _save_cooldowns()
                                                log(f"[{pair}] ⏸️ Cooldown activé ({order['horizon']}) — prochaine analyse dans {COOLDOWN_DURATIONS.get(order['horizon'], 8 * 3600) // 60}min", "DEBUG")
                                                cancel = True
                                            elif entry <= sp < tp1:
                                                # Vérifier le R:R RÉEL depuis le prix live
                                                real_profit = tp1 - sp
                                                real_risk = sp - sl
                                                real_rr = round(real_profit / real_risk, 2) if real_risk > 0 else 0
                                                
                                                if real_rr < 1.0:
                                                    log(f"[{pair}] ⚠️ Signal périmé — R:R réel {real_rr} (profit {real_profit:.5f} vs risque {real_risk:.5f})", "WARNING")
                                                    signal_cooldowns[cooldown_key] = time.time() + COOLDOWN_DURATIONS.get(order["horizon"], 8 * 3600)
                                                    _save_cooldowns()
                                                    log(f"[{pair}] ⏸️ Cooldown activé ({order['horizon']}) — prochaine analyse dans {COOLDOWN_DURATIONS.get(order['horizon'], 8 * 3600) // 60}min", "DEBUG")
                                                    cancel = True
                                                else:
                                                    order["status"] = "active"
                                                    order["activated_at"] = order["signal_time"]
                                                    order["activated_price"] = sp
                                                    order["real_rr"] = real_rr
                                                    log(f"[{pair}] 📝 Paper Trade ACTIF direct — prix ({sp}) | R:R réel: {real_rr} | TP1:{tp1} SL:{sl}", "SUCCESS")
                                            # sinon sp < entry → PENDING (on attend pullback vers entry)
                                    else:  # VENTE / SELL
                                        if sp <= tp1:
                                            log(f"[{pair}] ⚠️ Signal obsolète — prix ({sp}) déjà sous le TP1 ({tp1})", "WARNING")
                                            signal_cooldowns[cooldown_key] = time.time() + COOLDOWN_DURATIONS.get(order["horizon"], 8 * 3600)
                                            _save_cooldowns()
                                            log(f"[{pair}] ⏸️ Cooldown activé ({order['horizon']}) — prochaine analyse dans {COOLDOWN_DURATIONS.get(order['horizon'], 8 * 3600) // 60}min", "DEBUG")
                                            cancel = True
                                        elif sp >= sl:
                                            log(f"[{pair}] ⚠️ Signal obsolète — prix ({sp}) déjà au-dessus du SL ({sl})", "WARNING")
                                            signal_cooldowns[cooldown_key] = time.time() + COOLDOWN_DURATIONS.get(order["horizon"], 8 * 3600)
                                            _save_cooldowns()
                                            log(f"[{pair}] ⏸️ Cooldown activé ({order['horizon']}) — prochaine analyse dans {COOLDOWN_DURATIONS.get(order['horizon'], 8 * 3600) // 60}min", "DEBUG")
                                            cancel = True
                                        else:
                                            # ── CHECK DISTANCE MAX (activation directe SELL) ──
                                            pip_size_check = get_pip_size_safe(pair)
                                            dist_pips = abs(sp - entry) / pip_size_check
                                            MAX_DIST_DIRECT = {"scalp": 15, "intraday": 30, "daily": 50, "weekly": 80}
                                            max_d = MAX_DIST_DIRECT.get(order.get("horizon", "daily"), 50)
                                            if dist_pips > max_d:
                                                log(f"[{pair}] ⚠️ Signal trop loin — {dist_pips:.0f} pips d'écart (max {max_d}) — ANNULÉ", "WARNING")
                                                signal_cooldowns[cooldown_key] = time.time() + COOLDOWN_DURATIONS.get(order["horizon"], 8 * 3600)
                                                _save_cooldowns()
                                                log(f"[{pair}] ⏸️ Cooldown activé ({order['horizon']}) — prochaine analyse dans {COOLDOWN_DURATIONS.get(order['horizon'], 8 * 3600) // 60}min", "DEBUG")
                                                cancel = True
                                            elif tp1 < sp <= entry:
                                                # Vérifier le R:R RÉEL depuis le prix live
                                                real_profit = sp - tp1
                                                real_risk = sl - sp
                                                real_rr = round(real_profit / real_risk, 2) if real_risk > 0 else 0
                                                
                                                if real_rr < 1.0:
                                                    log(f"[{pair}] ⚠️ Signal périmé — R:R réel {real_rr} (profit {real_profit:.5f} vs risque {real_risk:.5f})", "WARNING")
                                                    signal_cooldowns[cooldown_key] = time.time() + COOLDOWN_DURATIONS.get(order["horizon"], 8 * 3600)
                                                    _save_cooldowns()
                                                    log(f"[{pair}] ⏸️ Cooldown activé ({order['horizon']}) — prochaine analyse dans {COOLDOWN_DURATIONS.get(order['horizon'], 8 * 3600) // 60}min", "DEBUG")
                                                    cancel = True
                                                else:
                                                    order["status"] = "active"
                                                    order["activated_at"] = order["signal_time"]
                                                    order["activated_price"] = sp
                                                    order["real_rr"] = real_rr
                                                    log(f"[{pair}] 📝 Paper Trade ACTIF direct — prix ({sp}) | R:R réel: {real_rr} | TP1:{tp1} SL:{sl}", "SUCCESS")
                                            # sinon sp > entry → PENDING
                                else:
                                    # Pas de prix live → ACTIVE direct (fallback)
                                    order["status"] = "active"
                                    order["activated_at"] = order["signal_time"]
                                    order["activated_price"] = order.get("entry")  # fallback sur entry théorique

                                if cancel:
                                    with state_lock:
                                        bot_state["orders"] = [o for o in bot_state["orders"] if o["id"] != order["id"]]
                                    broadcast("order_update", {"action": "delete", "id": order["id"]})
                                    order = None
                                else:
                                    status_emoji = "📝" if order["status"] == "active" else "⏳"
                                    log(f"{status_emoji} PAPER TRADE {order['status'].upper()}: {pair} {order['direction']} @ {entry} | SL:{sl} TP1:{tp1} | Prix:{sp} | Horizon:{order['horizon']}", "SUCCESS" if order["status"] == "active" else "INFO")
                                    broadcast("order_update", {"action": "update", "order": order})
                                    _save_paper_trade(order)

                                    # ── OTE Tracker : nettoyer le setup après exécution du trade ──
                                    if action == "new":
                                        try:
                                            from agents.ict.ote_tracker import clear_triggered
                                            _bias = "bullish" if order.get("direction", "") in ("BUY", "ACHAT") else "bearish"
                                            clear_triggered(pair, order.get("horizon", "unknown"), _bias)
                                            log(f"[{pair}] OTE setup nettoyé après trade {order.get('direction')}", "DEBUG")
                                        except Exception as _ote_clear_ex:
                                            log(f"[{pair}] OTE clear_triggered erreur: {_ote_clear_ex}", "DEBUG")
                                    
                                    # Notification Telegram
                                    if action == "new" and order.get("score", 0) >= getattr(config, "TELEGRAM_MIN_SCORE", 70):
                                        try:
                                            notifier.notify_trade_opened(
                                                pair=order["pair"],
                                                direction=order["direction"],
                                                entry=order["entry"],
                                                sl=order["sl"],
                                                tp=order["tp1"],
                                                score=order["score"],
                                                reasons=order.get("reasons", [])
                                            )
                                        except Exception as _t_err:
                                            log(f"Erreur notification Telegram: {_t_err}", "DEBUG")
                                
                            # Logs & Broadcast (Hors lock pour éviter deadlock)
                            if order:
                                if action == "update":
                                    log(f"Mise à jour signal {pair} — Score: {order['score']}/100", "DEBUG")
                                    broadcast("order_update", {"action": "update", "order": order})
                                elif action == "new":
                                    log(f"NOUVEAU SIGNAL AFFICHE {pair} — {order['direction']} | Score {order['score']}/100", "DEBUG")
                                    broadcast("order_update", {"action": "new", "order": order})

                            # ── Exécution auto ───────────────────
                            if order and order["status"] == "pending" and decision in ("OUVRIR", "OUVRIR_LIMIT") and getattr(config, "TRADING_MODE", "") == "full_auto":
                                if order["score"] >= bot_state["min_score"]:
                                    if getattr(mt5_conn, "simulation_mode", True):
                                        log(f"{pair}: Pas d'exécution (Mode SIMULATION actif).", "WARNING")
                                    else:
                                        log(f"EXECUTION AUTO {pair} (Score {order['score']} >= {bot_state['min_score']})...", "SUCCESS")
                                        res = trade_mgr.execute_trade(
                                            pair=order["pair"], direction=order["direction"],
                                            entry=order["entry"], sl=order["sl"], tp=order["tp1"],
                                            comment=f"ICT {order['id']}"
                                        )
                                        if res.get("ok"):
                                            with state_lock:
                                                order["status"] = "active"
                                                order["ticket"] = res["ticket"]
                                                order["volume"] = res["volume"]
                                            log(f"Trade ouvert! Ticket: {res['ticket']}", "SUCCESS")
                                            broadcast("order_update", {"action": "update", "order": order})
                                        else:
                                            log(f"Échec exécution MT5: {res.get('message')}", "ERROR")
                                else:
                                    log(f"{pair}: Score {order['score']} insuffisant pour EXÉCUTION (seuil {bot_state['min_score']})", "INFO")

                        # ── Pure PA — Trade Paper Indépendant ────────────────────────────
                        # Son propre circuit breaker, ses propres tags, totalement isolé d'ICT.
                        pure_pa_result = result_holder.get("pure_pa_result")
                        if paper_mode and pure_pa_result and pure_pa_result.get("action") == "new":
                            try:
                                # Circuit Breaker Pure PA (indépendant d'ICT)
                                pa_cb_blocked = False
                                if _CB_AVAILABLE and _circuit_breaker_pure_pa:
                                    pa_cb_status = _circuit_breaker_pure_pa.get_status()
                                    if pa_cb_status.get("active", False):
                                        log(f"[{pair}] 🔴 Pure PA CB ACTIF — {pa_cb_status.get('reason', '')}",  "WARNING")
                                        pa_cb_blocked = True
                                    elif hasattr(_circuit_breaker_pure_pa, "record_trade_opened"):
                                        _circuit_breaker_pure_pa.record_trade_opened()

                                if not pa_cb_blocked:
                                    pa_dir_raw = pure_pa_result.get("direction", "neutral")
                                    pa_dir_str = "ACHAT" if pa_dir_raw == "buy" else "VENTE"
                                    pa_sl = pure_pa_result.get("sl", 0)
                                    pa_tp = pure_pa_result.get("tp", 0)
                                    pa_entry = pure_pa_result.get("entry", 0)

                                    if pa_entry and pa_sl and pa_tp:
                                        # Vérifier qu'aucun trade Pure PA n'est déjà actif sur cette paire
                                        with state_lock:
                                            pa_already_active = any(
                                                o.get("pair") == pair and
                                                o.get("profile_id") == "pure_pa" and
                                                o.get("status") in ("active", "pending")
                                                for o in bot_state["orders"]
                                            )

                                        if not pa_already_active:
                                            pa_convergence = result_holder.get("final", {}).get("convergence_state", "independent")
                                            
                                            # Correction 3 : Blocage R:R Aberrant sur M5 (Pure PA)
                                            _pa_rr_check = round(abs(pa_tp - pa_entry) / abs(pa_entry - pa_sl), 2) if pa_entry and pa_sl and abs(pa_entry - pa_sl) > 0 else 0
                                            if profile["entry_tf"] == "M5" and _pa_rr_check > 8:
                                                log(f"[{pair}] 🚫 Pure PA R:R aberrant ({_pa_rr_check} > 8) sur M5 — Bloqué (Correction 3)", "WARNING")
                                                continue

                                            pa_order = make_order(
                                                pair=pair, school="pure_pa", direction=pa_dir_str,
                                                entry=pa_entry, sl=pa_sl,
                                                tp1=pa_tp, tp2=0,
                                                score=100, narrative=pure_pa_result.get("rationale", "Pure PA signal"),
                                                checklist=[], status="pending",
                                                timeframe=profile["entry_tf"],
                                                profile_id="pure_pa",
                                                active_gates=pure_pa_result.get("active_gates", []),
                                                convergence_state=pa_convergence,
                                                ttl_seconds=pure_pa_result.get("ttl_seconds", 1800)
                                            )
                                            pa_order["horizon"] = "scalp"

                                            with state_lock:
                                                bot_state["orders"].append(pa_order)
                                            _save_paper_trade(pa_order)
                                            broadcast("order_update", {"action": "new", "order": pa_order})
                                            log(f"📝 PAPER TRADE PURE PA {pair} {pa_dir_str} @ {pa_entry} | SL:{pa_sl} TP:{pa_tp} | Convergence:{pa_convergence}", "SUCCESS")
                            except Exception as _pa_trade_err:
                                log(f"[{pair}] Pure PA trade paper erreur (non bloquant): {_pa_trade_err}", "DEBUG")
                        # ── Fin Pure PA Trade Paper ───────────────────────────────────────

                        _sync_mt5_history()
                        _clean_old_orders()
                        time.sleep(1)

                    except Exception as e:
                        log(f"Erreur {pair} [{horizon}]: {e}", "ERROR")
                        continue

            log(f"Prochain cycle dans {sched['next_check_seconds'] // 60} min...", "INFO")

            # Post-Mortem quotidien — tourne à minuit UTC
            _now_utc = datetime.now(timezone.utc)
            if _now_utc.hour == 23 and _now_utc.minute < 5:
                try:
                    pm_report = run_post_mortem()
                    log(f"📊 Post-Mortem — ICT regret: {pm_report['ict']['gate_regret_rate']}% | "
                        f"Elliott regret: {pm_report['elliott']['gate_regret_rate']}% | "
                        f"Meta regret: {pm_report['meta']['gate_regret_rate']}%", "INFO")
                except Exception as _pm_err:
                    log(f"Post-Mortem erreur: {_pm_err}", "DEBUG")
            for _ in range(sched["next_check_seconds"]):
                if stop_event.is_set(): return
                time.sleep(1)

    except Exception as e:
        log(f"Erreur fatale boucle : {e}", "ERROR")
    finally:
        with state_lock: bot_state["status"] = "stopped"
        broadcast("status", {"status": "stopped"})


# ─────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────
def _build_algo_checklist(structure_report=None, time_report=None,
                           entry_signal=None, decision_obj=None):
    """Checklist structurée depuis les données algorithmiques."""
    checklist = []
    if decision_obj:
        alignment = decision_obj.get("alignment", {})
        direction = decision_obj.get("direction", "")
        warnings  = decision_obj.get("warnings", [])

        for agent, value in alignment.items():
            status = "pass" if value == direction else "fail"
            checklist.append({"item": f"{agent.capitalize()}: {value}", "status": status})

        rr   = decision_obj.get("rr_ratio", 0)
        conf = decision_obj.get("global_confidence", 0)
        checklist.append({"item": f"R:R = {rr:.1f}", "status": "pass" if rr >= 1.5 else "fail"})
        checklist.append({"item": f"Confiance: {conf:.0%}", "status": "pass" if conf >= 0.55 else "fail"})

        for w in warnings:
            checklist.append({"item": w, "status": "fail"})

    return checklist if checklist else [{"item": "Analyse algorithmique OK", "status": "pass"}]


def _save_paper_trade(order):
    """Sauvegarde un paper trade dans un fichier JSON quotidien."""
    today = datetime.now().strftime("%Y-%m-%d")
    filepath = os.path.join(PROJECT_ROOT, "paper_trades", f"paper_{today}.json")
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    trades = []
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            trades = json.load(f)
    
    trades.append({
        "id": order["id"],
        "pair": order["pair"],
        "direction": order["direction"],
        "entry": order["entry"],
        "sl": order["sl"],
        "tp1": order["tp1"],
        "tp2": order.get("tp2", 0),
        "score": order["score"],
        "timeframe": order.get("timeframe", "H1"),
        "opened_at": order["opened_at"],
        "status": "active",
        "closed_at": None,
        "close_price": None,
        "pnl_money": 0.0,
        "pnl_pips": 0.0,
        "profile_id": order.get("profile_id", "legacy"),
        "active_gates": order.get("active_gates", []),
        "convergence_state": order.get("convergence_state", "independent"),
        "ttl_seconds": order.get("ttl_seconds", 1800),
        "close_reason": None,
        "narrative": order.get("narrative", ""),
        "checklist": order.get("checklist", []),
    })
    
    with open(filepath, "w") as f:
        json.dump(trades, f, indent=2)


def _update_paper_trade(order):
    """Met à jour un paper trade dans le fichier JSON."""
    today = datetime.now().strftime("%Y-%m-%d")
    filepath = os.path.join(PROJECT_ROOT, "paper_trades", f"paper_{today}.json")
    if not os.path.exists(filepath):
        return
    
    with open(filepath, "r") as f:
        trades = json.load(f)
    
    for t in trades:
        if t["id"] == order["id"]:
            t["status"] = order["status"]
            t["closed_at"] = order.get("closed_at")
            t["close_price"] = order.get("sl") if order.get("close_reason") == "SL" else order.get("tp1")
            t["pnl_pips"] = order.get("pnl_pips", 0)
            t["pnl_money"] = order.get("pnl_money", 0)
            t["close_reason"] = order.get("close_reason")
            if "narrative" in order: t["narrative"] = order["narrative"]
            if "checklist" in order: t["checklist"] = order["checklist"]
            break
    
    with open(filepath, "w") as f:
        json.dump(trades, f, indent=2)


def _reload_paper_trades():
    """Recharge les paper trades actifs depuis les fichiers JSON au démarrage."""
    paper_dir = os.path.join(PROJECT_ROOT, "paper_trades")
    if not os.path.exists(paper_dir):
        return
    
    reloaded = 0
    checked = 0
    closed_count = 0
    
    for filename in sorted(os.listdir(paper_dir)):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(paper_dir, filename)
        try:
            with open(filepath, "r") as f:
                trades = json.load(f)
        except:
            continue
        
        updated = False
        for trade in trades:
            # Ne recharger que les trades encore actifs
            if trade.get("status") not in ("active", "closed"):
                continue
            
            # Ne pas recharger les trades fermés de plus de 48h
            if trade.get("status") == "closed" and trade.get("closed_at"):
                try:
                    closed_dt = datetime.strptime(trade["closed_at"], "%Y-%m-%d %H:%M")
                    if (datetime.now() - closed_dt).total_seconds() > 48 * 3600:
                        continue  # Trop ancien, ne pas recharger
                except Exception:
                    pass
            
            checked += 1
            
            # Vérifier si SL/TP a été touché pendant que le bot était éteint
            try:
                md = mt5_conn.get_market_data(trade["pair"])
                current_price = md.get("current_price") or md.get("bid", 0)
                if current_price and current_price > 0:
                    pip_size = get_pip_size_safe(trade["pair"])
                    direction = trade["direction"]
                    entry = trade["entry"]
                    sl = trade["sl"]
                    tp1 = trade["tp1"]
                    
                    hit = None
                    close_price = current_price
                    
                    if direction in ("ACHAT", "BUY"):
                        if current_price <= sl:
                            hit = "SL"
                            close_price = sl
                        elif current_price >= tp1:
                            hit = "TP1"
                            close_price = tp1
                    else:
                        if current_price >= sl:
                            hit = "SL"
                            close_price = sl
                        elif current_price <= tp1:
                            hit = "TP1"
                            close_price = tp1
                    
                    if hit:
                        # Trade touché pendant l'absence
                        if direction in ("ACHAT", "BUY"):
                            pnl_pips = round((close_price - entry) / pip_size, 1)
                        else:
                            pnl_pips = round((entry - close_price) / pip_size, 1)
                        pnl_money = round(pnl_pips * 10 * trade.get("volume", 0.1), 2)
                        
                        trade["status"] = "closed"
                        trade["closed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                        trade["pnl_pips"] = pnl_pips
                        trade["pnl_money"] = pnl_money
                        trade["close_reason"] = f"{hit} (offline)"
                        updated = True
                        closed_count += 1
                        log(f"📋 Paper trade rechargé et FERMÉ: {trade['pair']} {hit} → {pnl_pips:+.1f} pips", "INFO")
                    else:
                        # Trade encore actif — calculer PnL flottant
                        if direction in ("ACHAT", "BUY"):
                            trade["pnl_pips"] = round((current_price - entry) / pip_size, 1)
                        else:
                            trade["pnl_pips"] = round((entry - current_price) / pip_size, 1)
                        trade["pnl_money"] = round(trade["pnl_pips"] * 10 * trade.get("volume", 0.1), 2)
            except Exception as e:
                log(f"Erreur vérification paper {trade['pair']}: {e}", "WARNING")
            
            # Reconstruire l'ordre pour bot_state
            order = {
                "id": trade["id"],
                "pair": trade["pair"],
                "school": "ict",
                "status": trade["status"],
                "direction": trade["direction"],
                "timeframe": trade.get("timeframe", "H1"),
                "entry": float(trade["entry"]),
                "sl": float(trade["sl"]),
                "tp1": float(trade["tp1"]),
                "tp2": float(trade.get("tp2", 0)),
                "rr": round(abs(float(trade["tp1"]) - float(trade["entry"])) / abs(float(trade["entry"]) - float(trade["sl"])), 2) if abs(float(trade["entry"]) - float(trade["sl"])) > 0 else 0,
                "score": trade.get("score", 50),
                "pnl_pips": float(trade.get("pnl_pips", 0)),
                "pnl_money": float(trade.get("pnl_money", 0)),
                "volume": float(trade.get("volume", 0.1)),
                "montant_risque": 0,
                "opened_at": trade.get("opened_at", ""),
                "closed_at": trade.get("closed_at"),
                "checklist": trade.get("checklist", []),
                "narrative": trade.get("narrative", ""),
                "pending_conditions": [],
                "raw_plan": "",
                "close_reason": trade.get("close_reason"),
            }
            
            with state_lock:
                # Éviter les doublons
                existing = next((o for o in bot_state["orders"] if o["id"] == trade["id"]), None)
                if not existing:
                    bot_state["orders"].append(order)
                    reloaded += 1
        
        # Sauvegarder les mises à jour (trades fermés offline)
        if updated:
            with open(filepath, "w") as f:
                json.dump(trades, f, indent=2)
    
    if reloaded > 0 or closed_count > 0:
        log(f"📋 Paper trades rechargés: {reloaded} actifs, {closed_count} fermés (SL/TP offline)", "SUCCESS")


def _sync_mt5_history():
    """Synchronise les ordres actifs avec l'historique MT5 réel."""
    if mt5_mod is None: return
    if not mt5_mod.initialize(): return

    with state_lock:
        active_orders = [o for o in bot_state["orders"] if o["status"] == "active" and o.get("ticket")]
    if not active_orders: return

    from_date = datetime.now() - timedelta(hours=24)
    history   = mt5_mod.history_deals_get(from_date, datetime.now())
    if history is None or len(history) == 0: return

    for order in active_orders:
        ticket  = order["ticket"]
        closure = next((d for d in history if d.position_id == ticket and d.entry == 1), None)
        if closure:
            with state_lock:
                order["status"]     = "closed"
                order["closed_at"]  = datetime.now().strftime("%Y-%m-%d %H:%M")
                order["pnl_money"]  = closure.profit + closure.commission + closure.swap
            log(f"Position {order['pair']} (Ticket {ticket}) fermée — PnL: {order['pnl_money']:.2f}$", "SUCCESS")
            broadcast("order_update", {"action": "update", "order": order})


def _clean_old_orders():
    """Supprime les ordres closed/cancelled de plus de 24h."""
    cutoff = datetime.now() - timedelta(hours=24)
    with state_lock:
        bot_state["orders"] = [
            o for o in bot_state["orders"]
            if not (o["status"] in ("closed", "cancelled") and
                    o.get("closed_at") and
                    datetime.strptime(o["closed_at"], "%Y-%m-%d %H:%M") < cutoff)
        ]


def _compute_stats():
    """Calcule les stats globales (PnL journalier, trades ouverts, etc.)."""
    with state_lock:
        orders = list(bot_state["orders"])

    today = datetime.now().date()
    daily_closed = [o for o in orders if o["status"] == "closed" and
                    o.get("closed_at") and
                    datetime.strptime(o["closed_at"], "%Y-%m-%d %H:%M").date() == today]

    day_pnl  = sum(o.get("pnl_money", 0) for o in daily_closed)
    wins     = sum(1 for o in daily_closed if o.get("pnl_money", 0) > 0)
    losses   = sum(1 for o in daily_closed if o.get("pnl_money", 0) < 0)
    wr       = round(wins / len(daily_closed) * 100, 1) if daily_closed else 0
    n_active = sum(1 for o in orders if o["status"] == "active")
    n_open   = sum(1 for o in orders if o["status"] in ("active", "pending"))

    return {
        "day_pnl":    round(day_pnl, 2),
        "win_rate":   wr,
        "wins":       wins,
        "losses":     losses,
        "n_active":   n_active,
        "n_open":     n_open,
        "n_closed":   len(daily_closed),
    }


# ─────────────────────────────────────────────────────────────────
# ROUTES FLASK
# ─────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    with state_lock:
        running = bot_state.get("status") in ("running", "waiting", "paused")
    return render_template(
        "dashboard.html",
        pairs_by_group=ALL_PAIRS,
        bot_running=running,
    )

@app.route("/postmortem")
def page_postmortem():
    """Page Post-Mortem (historique avancé)."""
    return render_template("postmortem.html")

@app.route("/performance")
def page_performance():
    """Page des statistiques de performance du bot."""
    return render_template("performance.html")

@app.route("/logs")
def page_logs():
    """Page de visualisation des logs temps réel."""
    return render_template("logs.html")

@app.route("/api/performance_stats")
def api_performance_stats():
    """Calcule et retourne les statistiques complètes depuis tous les paper trades.
    Étape 5 — enrichi avec métriques par profil (by_profile) et alertes expectancy.
    """
    paper_dir = os.path.join(PROJECT_ROOT, "paper_trades")
    all_trades = []

    if os.path.exists(paper_dir):
        for filename in sorted(os.listdir(paper_dir)):
            if filename.startswith("paper_") and filename.endswith(".json"):
                filepath = os.path.join(paper_dir, filename)
                try:
                    with open(filepath, "r") as f:
                        trades = json.load(f)
                        all_trades.extend(trades)
                except Exception:
                    continue

    # Séparer trades fermés et actifs
    closed = [t for t in all_trades if t.get("status") == "closed"]
    active = [t for t in all_trades if t.get("status") in ("active", "pending")]

    # ── Helper : calcul métriques pour un sous-ensemble de trades ────────────
    def _compute_stats(trades_subset):
        if not trades_subset:
            return {
                "closed_trades": 0, "winners": 0, "losers": 0,
                "win_rate": 0, "total_pnl_pips": 0, "total_pnl_money": 0,
                "avg_pnl_pips": 0, "best_trade": None, "worst_trade": None,
                "profit_factor": 0, "expectancy": 0, "max_drawdown": 0,
                "rr_avg": 0, "equity_curve": [], "by_pair": {},
                "by_direction": {"BUY": 0, "SELL": 0}, "by_reason": {},
                "recent_trades": [],
            }
        winners = [t for t in trades_subset if t.get("pnl_pips", 0) > 0]
        losers  = [t for t in trades_subset if t.get("pnl_pips", 0) <= 0]
        n = len(trades_subset)
        win_rate = round(len(winners) / n * 100, 1)
        total_pnl_pips  = round(sum(t.get("pnl_pips", 0) for t in trades_subset), 1)
        total_pnl_money = round(sum(t.get("pnl_money", 0) for t in trades_subset), 2)
        avg_pnl_pips    = round(total_pnl_pips / n, 1)

        # Expectancy
        avg_win  = (sum(t.get("pnl_pips", 0) for t in winners) / len(winners)) if winners else 0
        avg_loss = (sum(t.get("pnl_pips", 0) for t in losers)  / len(losers))  if losers  else 0
        wr = len(winners) / n
        lr = len(losers)  / n
        expectancy = round((wr * avg_win) + (lr * avg_loss), 2)

        # Profit Factor
        gross_gain = sum(t.get("pnl_pips", 0) for t in winners)
        gross_loss = abs(sum(t.get("pnl_pips", 0) for t in losers))
        profit_factor = round(gross_gain / gross_loss, 2) if gross_loss > 0 else 0

        # Max Drawdown
        cumul, peak, max_dd = 0, 0, 0
        for t in sorted(trades_subset, key=lambda x: x.get("closed_at", "")):
            cumul = round(cumul + t.get("pnl_pips", 0), 1)
            if cumul > peak:
                peak = cumul
            dd = peak - cumul
            if dd > max_dd:
                max_dd = dd
        max_drawdown = round(max_dd, 1)

        # R:R moyen
        rr_values = [t.get("rr_ratio", t.get("real_rr", 0)) for t in trades_subset if t.get("rr_ratio", t.get("real_rr", 0))]
        rr_avg = round(sum(rr_values) / len(rr_values), 2) if rr_values else 0

        best  = max(trades_subset, key=lambda t: t.get("pnl_pips", 0))
        worst = min(trades_subset, key=lambda t: t.get("pnl_pips", 0))

        by_pair = {}
        for t in trades_subset:
            p = t.get("pair", "?")
            if p not in by_pair:
                by_pair[p] = {"trades": 0, "wins": 0, "pnl_pips": 0, "pnl_money": 0}
            by_pair[p]["trades"] += 1
            by_pair[p]["pnl_pips"]  = round(by_pair[p]["pnl_pips"]  + t.get("pnl_pips", 0), 1)
            by_pair[p]["pnl_money"] = round(by_pair[p]["pnl_money"] + t.get("pnl_money", 0), 2)
            if t.get("pnl_pips", 0) > 0:
                by_pair[p]["wins"] += 1
        for p in by_pair:
            by_pair[p]["win_rate"] = round(by_pair[p]["wins"] / by_pair[p]["trades"] * 100, 1)

        by_direction = {
            "BUY":  len([t for t in trades_subset if t.get("direction") == "BUY"]),
            "SELL": len([t for t in trades_subset if t.get("direction") == "SELL"]),
        }
        by_reason = {}
        for t in trades_subset:
            r = t.get("close_reason", "?")
            by_reason[r] = by_reason.get(r, 0) + 1

        equity_curve = []
        cumul_eq = 0
        for t in sorted(trades_subset, key=lambda x: x.get("closed_at", "")):
            cumul_eq = round(cumul_eq + t.get("pnl_pips", 0), 1)
            equity_curve.append({
                "date": t.get("closed_at", "")[:10],
                "cumul_pips": cumul_eq,
                "pair": t.get("pair"),
                "pnl": t.get("pnl_pips", 0),
            })

        recent = sorted(trades_subset, key=lambda x: x.get("closed_at", ""), reverse=True)[:20]

        return {
            "closed_trades": n, "winners": len(winners), "losers": len(losers),
            "win_rate": win_rate, "total_pnl_pips": total_pnl_pips,
            "total_pnl_money": total_pnl_money, "avg_pnl_pips": avg_pnl_pips,
            "best_trade": best, "worst_trade": worst,
            "profit_factor": profit_factor, "expectancy": expectancy,
            "max_drawdown": max_drawdown, "rr_avg": rr_avg,
            "equity_curve": equity_curve, "by_pair": by_pair,
            "by_direction": by_direction, "by_reason": by_reason,
            "recent_trades": recent,
        }
    # ── Fin helper ─────────────────────────────────────────────────────────

    if not closed:
        return jsonify({
            "total_trades": 0, "closed_trades": 0, "active_trades": len(active),
            "win_rate": 0, "total_pnl_pips": 0, "total_pnl_money": 0,
            "avg_pnl_pips": 0, "profit_factor": 0, "expectancy": 0,
            "max_drawdown": 0, "rr_avg": 0, "best_trade": None, "worst_trade": None,
            "by_pair": {}, "by_direction": {"BUY": 0, "SELL": 0},
            "by_reason": {}, "recent_trades": [], "equity_curve": [],
            "by_profile": {}, "expectancy_alerts": [],
        })

    # ── Stats globales (tous profils) ─────────────────────────────────────
    global_stats = _compute_stats(closed)

    # ── Stats par profil ──────────────────────────────────────────────────
    PROFILES = ["ict_strict", "pure_pa", "legacy"]
    by_profile = {}
    for pid in PROFILES:
        if pid == "legacy":
            subset = [t for t in closed if not t.get("profile_id")]
        else:
            subset = [t for t in closed if t.get("profile_id") == pid]
        if subset:
            by_profile[pid] = _compute_stats(subset)

    # ── Alertes expectancy négative sur 20 derniers trades par profil ─────
    expectancy_alerts = []
    all_profile_ids = list(set(t.get("profile_id", "legacy") or "legacy" for t in closed))
    for pid in all_profile_ids:
        if pid == "legacy":
            recent20 = sorted(
                [t for t in closed if not t.get("profile_id")],
                key=lambda x: x.get("closed_at", ""), reverse=True
            )[:20]
        else:
            recent20 = sorted(
                [t for t in closed if t.get("profile_id") == pid],
                key=lambda x: x.get("closed_at", ""), reverse=True
            )[:20]
        if len(recent20) >= 5:  # Minimum 5 trades pour déclencher l'alerte
            w20 = [t for t in recent20 if t.get("pnl_pips", 0) > 0]
            l20 = [t for t in recent20 if t.get("pnl_pips", 0) <= 0]
            aw = (sum(t.get("pnl_pips", 0) for t in w20) / len(w20)) if w20 else 0
            al = (sum(t.get("pnl_pips", 0) for t in l20) / len(l20)) if l20 else 0
            exp20 = round((len(w20) / len(recent20)) * aw + (len(l20) / len(recent20)) * al, 2)
            if exp20 < 0:
                expectancy_alerts.append({
                    "profile_id": pid,
                    "expectancy_20": exp20,
                    "trades_count": len(recent20),
                    "message": f"⚠️ Expectancy négative sur 20 derniers trades : {exp20:+.1f} pips/trade",
                })

    return jsonify({
        "total_trades":        len(all_trades),
        "closed_trades":       global_stats["closed_trades"],
        "active_trades":       len(active),
        "winners":             global_stats["winners"],
        "losers":              global_stats["losers"],
        "win_rate":            global_stats["win_rate"],
        "total_pnl_pips":      global_stats["total_pnl_pips"],
        "total_pnl_money":     global_stats["total_pnl_money"],
        "avg_pnl_pips":        global_stats["avg_pnl_pips"],
        "profit_factor":       global_stats["profit_factor"],
        "expectancy":          global_stats["expectancy"],
        "max_drawdown":        global_stats["max_drawdown"],
        "rr_avg":              global_stats["rr_avg"],
        "best_trade":          global_stats["best_trade"],
        "worst_trade":         global_stats["worst_trade"],
        "by_pair":             global_stats["by_pair"],
        "by_direction":        global_stats["by_direction"],
        "by_reason":           global_stats["by_reason"],
        "recent_trades":       global_stats["recent_trades"],
        "equity_curve":        global_stats["equity_curve"],
        "by_profile":          by_profile,
        "expectancy_alerts":   expectancy_alerts,
    })

@app.route("/analysis/<order_id>")
def page_analysis(order_id):
    """Page d'analyse détaillée d'un trade."""
    return render_template("analysis.html", order_id=order_id)

@app.route("/api/analysis/<order_id>")
def api_analysis(order_id):
    """Retourne les données complètes d'un ordre pour la page analyse."""
    # Chercher dans bot_state (trades actifs/pending)
    with state_lock:
        order = next(
            (o for o in bot_state["orders"] if o["id"] == order_id),
            None
        )

    # Si pas trouvé en mémoire → chercher dans les fichiers paper_trades
    if not order:
        paper_dir = os.path.join(PROJECT_ROOT, "paper_trades")
        if os.path.exists(paper_dir):
            for filename in sorted(os.listdir(paper_dir), reverse=True):
                if filename.endswith(".json"):
                    filepath = os.path.join(paper_dir, filename)
                    try:
                        with open(filepath, "r") as f:
                            trades = json.load(f)
                        found = next((t for t in trades if t.get("id") == order_id), None)
                        if found:
                            order = found
                            break
                    except Exception:
                        continue

    if not order:
        return jsonify({"error": "Order not found"}), 404

    return jsonify(order)

@app.route("/settings")
def page_settings():
    return render_template("settings.html", profiles=profiles_settings)

@app.route("/api/settings", methods=["GET"])
def api_get_settings():
    """Retourne les paramètres actuels du bot."""
    return jsonify({
        # Bot Core
        "MIN_CONFIDENCE_SCORE":           getattr(config, "MIN_CONFIDENCE_SCORE", 70),
        "FORCE_ANALYZE":                  getattr(config, "FORCE_ANALYZE", False),
        "PAPER_TRADING":                  getattr(config, "PAPER_TRADING", True),
        # Risque
        "RISK_PER_TRADE_PCT":             getattr(config, "RISK_PER_TRADE_PCT", 1.0),
        "MIN_RISK_REWARD":                getattr(config, "MIN_RISK_REWARD", 2.0),
        "CIRCUIT_BREAKER_MAX_DAILY_LOSS_PCT":  getattr(config, "CIRCUIT_BREAKER_MAX_DAILY_LOSS_PCT", 3.0),
        "CIRCUIT_BREAKER_MAX_TRADES_PER_DAY":  getattr(config, "CIRCUIT_BREAKER_MAX_TRADES_PER_DAY", 5),
        "CIRCUIT_BREAKER_MAX_STOPLOSS_COUNT":  getattr(config, "CIRCUIT_BREAKER_MAX_STOPLOSS_COUNT", 3),
        # Paires actives
        "TRADING_PAIRS":                  getattr(config, "TRADING_PAIRS", []),
        "ALL_PAIRS":                      ALL_PAIRS,
        # Telegram
        "TELEGRAM_BOT_TOKEN":             getattr(config, "TELEGRAM_BOT_TOKEN", ""),
        "TELEGRAM_CHAT_ID":               getattr(config, "TELEGRAM_CHAT_ID", ""),
        "TELEGRAM_MIN_SCORE":             getattr(config, "TELEGRAM_MIN_SCORE", 70),
        # Scheduler - Killzones (depuis KILLZONE_SCHEDULE si défini)
        "killzone_schedule":              [
            {"name": kz["name"], "start": kz["start"].strftime("%H:%M"),
             "end": kz["end"].strftime("%H:%M"),
             "enabled": kz.get("enabled", True)}
            for kz in KILLZONE_SCHEDULE
        ] if 'KILLZONE_SCHEDULE' in globals() else [],
        # Profiles Settings
        "profiles_settings": profiles_settings,
    })

@app.route("/api/settings/save", methods=["POST"])
def api_settings_save_single():
    """Sauvegarde un paramètre unitaire envoyé depuis l'UI (Settings)."""
    data = request.get_json(silent=True)
    if not data or "key" not in data:
        return jsonify({"ok": False, "error": "Missing key"}), 400

    key = str(data["key"])
    value = data.get("value")

    # Mises à jour des profils ou du config
    if key.startswith("ict_") or key.startswith("pa_"):
        profiles_settings[key] = value
        _save_profiles_settings()
    else:
        setattr(config, key, value)
        _save_settings_override({key: value})
        if key == "MIN_CONFIDENCE_SCORE":
            with state_lock:
                bot_state["min_score"] = value

    return jsonify({"ok": True, "key": key, "value": value})

@app.route("/api/settings", methods=["POST"])
def api_save_settings():
    """Applique et sauvegarde les paramètres modifiés."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data"}), 400

    # Liste des clés autorisées à être modifiées
    ALLOWED_KEYS = [
        "MIN_CONFIDENCE_SCORE", "FORCE_ANALYZE", "PAPER_TRADING",
        "RISK_PER_TRADE_PCT", "MIN_RISK_REWARD",
        "CIRCUIT_BREAKER_MAX_DAILY_LOSS_PCT",
        "CIRCUIT_BREAKER_MAX_TRADES_PER_DAY",
        "CIRCUIT_BREAKER_MAX_STOPLOSS_COUNT",
        "TRADING_PAIRS",
        "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "TELEGRAM_MIN_SCORE",
    ]

    applied = {}
    for key in ALLOWED_KEYS:
        if key in data:
            value = data[key]
            setattr(config, key, value)
            applied[key] = value
            # Mettre à jour bot_state si nécessaire
            if key == "MIN_CONFIDENCE_SCORE":
                with state_lock:
                    bot_state["min_score"] = value

    # Modification des Profiles Settings
    if "profiles_settings" in data:
        new_ps = data["profiles_settings"]
        # Contrainte métier absolue : on ne peut pas désactiver MSS ET FVG
        pa_mss = new_ps.get("pa_mss_mandatory", True)
        pa_fvg = new_ps.get("pa_fvg_mandatory", True)
        if not pa_mss and not pa_fvg:
            return jsonify({"success": False, "error": "MSS et FVG ne peuvent pas être désactivés ensemble"}), 400
        
        profiles_settings.update(new_ps)
        _save_profiles_settings()
        applied["profiles_settings"] = True

    # Sauvegarder sur disque les autres paramètres (config global)
    if applied and any(k != "profiles_settings" for k in applied):
        _save_settings_override({k: v for k, v in applied.items() if k != "profiles_settings"})
        
    log(f"[Settings] {len(applied)} paramètre(s) mis à jour", "SUCCESS")
    return jsonify({"success": True, "applied": applied})


@app.route("/api/stream")
def stream():
    q = queue.Queue()
    with sse_lock:
        sse_clients.append(q)

    def generate():
        # Envoi état initial (attention: pas de lock imbriqué)
        with state_lock:
            snap = {
                "status":       bot_state["status"],
                "orders":       list(bot_state["orders"]),
                "logs":         bot_state["log_messages"][-50:],
                "mt5_status":   bot_state["mt5_status"],
                "mt5_connected":bot_state["mt5_connected"],
                "current_api":  bot_state["current_api"],
                "min_score":    bot_state["min_score"],
            }
        # _compute_stats prend son propre lock, donc on l'appelle HORS du lock
        snap["stats"] = _compute_stats()
        initial = {"type": "init", "data": snap}
        yield f"data: {json.dumps(initial)}\n\n"

        try:
            while True:
                try:
                    msg = q.get(timeout=30)
                    yield msg
                except queue.Empty:
                    yield "data: {\"type\":\"ping\"}\n\n"
        except GeneratorExit:
            return
        except Exception as e:
            file_logger.error(f"SSE stream error: {e}")
            return

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache",
                             "X-Accel-Buffering": "no"})


@app.route("/api/start", methods=["POST"])
def api_start():
    global bot_thread
    data       = request.json or {}
    pairs      = data.get("pairs") or getattr(config, "TRADING_PAIRS", ["EURUSD"])
    interval   = int(data.get("interval", 15))
    paper_mode = data.get("paper", getattr(config, "PAPER_TRADING", True))

    # Support multi-horizon (nouveau) et rétrocompatibilité (ancien paramètre horizon singulier)
    horizons = data.get("horizons", [data.get("horizon", "scalp")])
    if isinstance(horizons, str):
        horizons = [horizons]
    horizons = [h for h in horizons if h in HORIZON_PROFILES] or ["scalp"]

    if bot_state["status"] not in ("stopped", "paused"):
        return jsonify({"ok": False, "message": "Bot déjà en cours."})

    stop_event.clear()
    pause_event.clear()

    bot_thread = threading.Thread(
        target=run_bot_loop, args=(pairs, interval, paper_mode, horizons), daemon=True
    )
    bot_thread.start()
    labels = " + ".join(HORIZON_PROFILES[h]["label"] for h in horizons)
    log(f"Bot démarré sur {len(pairs)} paires | Horizons: {labels} | Intervalle: {interval} min", "SUCCESS")
    return jsonify({"ok": True, "horizons": horizons})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    stop_event.set()
    pause_event.clear()
    with state_lock: bot_state["status"] = "stopped"
    broadcast("status", {"status": "stopped"})
    log("Bot arrêté.", "INFO")
    return jsonify({"ok": True})


@app.route("/api/pause", methods=["POST"])
def api_pause():
    if bot_state["status"] == "paused":
        pause_event.clear()
        log("Bot repris.", "INFO")
    else:
        pause_event.set()
        log("Bot mis en pause.", "INFO")
    return jsonify({"ok": True, "paused": pause_event.is_set()})


@app.route("/api/state")
def api_state():
    with state_lock:
        snap = {
            "status":       bot_state["status"],
            "mt5_status":   bot_state["mt5_status"],
            "mt5_connected":bot_state["mt5_connected"],
            "current_pair": bot_state["current_pair"],
            "cycle_count":  bot_state["cycle_count"],
            "current_api":  bot_state["current_api"],
            "min_score":    bot_state["min_score"],
        }
    snap["stats"] = _compute_stats()
    return jsonify(snap)


@app.route("/api/paper_history")
def api_paper_history():
    """Retourne les paper trades. Paramètre optionnel ?date=YYYY-MM-DD."""
    paper_dir = os.path.join(PROJECT_ROOT, "paper_trades")
    if not os.path.exists(paper_dir):
        return jsonify([])

    # Si une date est passée en paramètre, on charge ce fichier précis
    requested_date = request.args.get("date", "").strip()
    if requested_date:
        target_file = os.path.join(paper_dir, f"paper_{requested_date}.json")
        if os.path.exists(target_file):
            try:
                with open(target_file, "r") as f:
                    return jsonify(json.load(f))
            except Exception:
                pass
        return jsonify([])  # date demandée mais fichier absent ou illisible

    # Sans paramètre : Priorité 1 = fichier du jour
    today = datetime.now().strftime("%Y-%m-%d")
    today_file = os.path.join(paper_dir, f"paper_{today}.json")
    if os.path.exists(today_file):
        try:
            with open(today_file, "r") as f:
                trades = json.load(f)
            if trades:
                return jsonify(trades)
        except Exception:
            pass

    # Priorité 2 : fichier le plus récent disponible
    candidates = sorted(
        [f for f in os.listdir(paper_dir) if f.startswith("paper_") and f.endswith(".json")],
        reverse=True
    )
    for filename in candidates:
        filepath = os.path.join(paper_dir, filename)
        try:
            with open(filepath, "r") as f:
                trades = json.load(f)
            if trades:
                return jsonify(trades)
        except Exception:
            continue

    return jsonify([])



@app.route("/api/paper_clear", methods=["POST"])
def api_paper_clear():
    """Supprime tous les paper trades (fichiers JSON + mémoire)."""
    paper_dir = os.path.join(PROJECT_ROOT, "paper_trades")
    deleted = 0
    if os.path.exists(paper_dir):
        for f in os.listdir(paper_dir):
            if f.endswith(".json"):
                os.remove(os.path.join(paper_dir, f))
                deleted += 1
    
    with state_lock:
        bot_state["orders"] = [o for o in bot_state["orders"] if o.get("status") == "active" and not o.get("close_reason")]
    
    log(f"🗑️ Paper trades supprimés ({deleted} fichiers)", "SUCCESS")
    broadcast("order_update", {"action": "clear"})
    return jsonify({"ok": True, "deleted": deleted})


@app.route("/api/paper_delete/<order_id>", methods=["DELETE"])
def api_paper_delete(order_id):
    """Supprime un paper trade spécifique."""
    # Retirer de la mémoire
    with state_lock:
        bot_state["orders"] = [o for o in bot_state["orders"] if o["id"] != order_id]
    
    # Retirer des fichiers JSON
    paper_dir = os.path.join(PROJECT_ROOT, "paper_trades")
    if os.path.exists(paper_dir):
        for filename in os.listdir(paper_dir):
            if not filename.endswith(".json"):
                continue
            filepath = os.path.join(paper_dir, filename)
            try:
                with open(filepath, "r") as f:
                    trades = json.load(f)
                new_trades = [t for t in trades if t["id"] != order_id]
                if len(new_trades) != len(trades):
                    with open(filepath, "w") as f:
                        json.dump(new_trades, f, indent=2)
            except:
                continue
    
    broadcast("order_update", {"action": "delete", "id": order_id})
    log(f"🗑️ Paper trade {order_id} supprimé", "INFO")
    return jsonify({"ok": True})


@app.route("/api/orders")
def api_orders():
    status = request.args.get("status")
    pair   = request.args.get("pair")
    with state_lock:
        orders = list(bot_state["orders"])
    if status:
        orders = [o for o in orders if o["status"] == status]
    if pair:
        orders = [o for o in orders if o["pair"] == pair]
    return jsonify(orders)


@app.route("/api/orders/<order_id>", methods=["PATCH"])
def api_update_order(order_id):
    data = request.json or {}
    new_status = data.get("status")
    with state_lock:
        for o in bot_state["orders"]:
            if o["id"] == order_id:
                if new_status:
                    o["status"] = new_status
                    if new_status == "closed":
                        o["closed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                broadcast("order_update", {"action": "update", "order": o})
                return jsonify({"ok": True, "order": o})
    return jsonify({"ok": False, "message": "Ordre non trouvé"}), 404


@app.route("/api/orders/<order_id>", methods=["DELETE"])
def api_delete_order(order_id):
    with state_lock:
        bot_state["orders"] = [o for o in bot_state["orders"] if o["id"] != order_id]
    broadcast("order_update", {"action": "delete", "id": order_id})
    return jsonify({"ok": True})


@app.route("/api/logs")
def api_logs():
    n = int(request.args.get("n", 100))
    with state_lock:
        return jsonify(bot_state["log_messages"][-n:])


@app.route("/api/reports")
def api_reports():
    pair = request.args.get("pair")
    with state_lock:
        reports = dict(bot_state["last_reports"])
    if pair:
        return jsonify(reports.get(pair, {}))
    return jsonify(reports)


@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    if request.method == "POST":
        data = request.json or {}
        if "min_score" in data:
            with state_lock:
                bot_state["min_score"] = int(data["min_score"])
        return jsonify({"ok": True})
    with state_lock:
        return jsonify({
            "min_score":       bot_state["min_score"],
            "trading_mode":    getattr(config, "TRADING_MODE", "paper"),
            "pairs":           getattr(config, "TRADING_PAIRS", []),
            "risk_per_trade":  getattr(config, "RISK_PER_TRADE_PCT", 1.0),
        })


@app.route("/api/stats")
def api_stats():
    return jsonify(_compute_stats())


@app.route("/api/force_analyze", methods=["GET", "POST"])
def api_force_analyze():
    if request.method == "POST":
        val = (request.json or {}).get("value", False)
        config.FORCE_ANALYZE = bool(val)
        log(f"Force Analyze: {'ON — Killzone bypass actif' if val else 'OFF — Mode normal'}", "SUCCESS")
        return jsonify({"ok": True, "value": config.FORCE_ANALYZE})
    return jsonify({"value": getattr(config, "FORCE_ANALYZE", False)})


@app.route("/api/horizons")
def api_horizons():
    return jsonify({k: v["label"] for k, v in HORIZON_PROFILES.items()})


# ─────────────────────────────────────────────────────────────────
# ROUTES DASHBOARD V2
# ─────────────────────────────────────────────────────────────────

@app.route("/api/setup/<pair>/<horizon>")
def api_setup(pair, horizon):
    """Retourne la dernière carte d'analyse en cache pour une paire et un horizon."""
    with state_lock:
        reports = bot_state.get("last_reports", {})
        
    # Actuellement, last_reports stocke une seule analyse (souvent le dernier horizon checké)
    # Si disponible, on la retourne.
    report = reports.get(pair)
    if not report:
        return jsonify({"error": "Aucune analyse en cache", "status": 404}), 404
        
    return jsonify(report)


@app.route("/api/sessions")
def api_sessions():
    """Liste les sessions historiques disponibles."""
    sessions_dir = os.path.join(PROJECT_ROOT, "logs", "sessions")
    if not os.path.exists(sessions_dir):
        return jsonify([])
        
    sessions = []
    for d in sorted(os.listdir(sessions_dir), reverse=True):
        p = os.path.join(sessions_dir, d)
        if os.path.isdir(p):
            # Analyser trades.log pour extraire KPIs rapides (Win Rate, PNL, nb analyses)
            trades_file = os.path.join(p, "trades.log")
            
            trade_count = 0
            win_count = 0
            pnl_money = 0.0
            analysis_count = 0
            
            if os.path.exists(trades_file):
                with open(trades_file, "r") as f:
                    for line in f:
                        if "Analyse" in line and "[scalp]" in line or "[intraday]" in line or "[daily]" in line or "[weekly]" in line:
                            analysis_count += 1
                        if "Trade exécuté" in line:
                            trade_count += 1
                        if "WIN" in line or ("+" in line and "€" in line and "Trade" not in line and "exécuté" not in line):
                             pass # Extraction plus pousee dans session/<date>
            
            sessions.append({
                "id": d,
                "name": d.replace("SESSION__", "").replace("_", " "),
                "date": d.split("__")[-1][:10] if "__" in d else d,
                "analysis_count": analysis_count,
                "trade_count": trade_count,
            })
            
    return jsonify(sessions)


@app.route("/api/session/<date_str>")
def api_session_detail(date_str):
    """Retourne les logs et KPI d'une session spécifique."""
    sessions_dir = os.path.join(PROJECT_ROOT, "logs", "sessions")
    session_path = os.path.join(sessions_dir, date_str)
    
    if not os.path.exists(session_path):
        return jsonify({"error": "Session introuvable"}), 404
        
    trades_log = os.path.join(session_path, "trades.log")
    bot_log = os.path.join(session_path, "bot.log")
    
    logs = []
    trades = []
    
    if os.path.exists(trades_log):
        with open(trades_log, "r") as f:
            for line in f:
                logs.append(line.strip())
                # Extraction basique pour l'UI
                if "Trade exécuté" in line or "NOUVEAU SIGNAL AFFICHE" in line:
                    trades.append({"raw": line.strip()})
                    
    return jsonify({
        "id": date_str,
        "logs": logs[-200:], # Limiter pour perf
        "trades": trades
    })


@app.route("/api/chat", methods=["POST"])
def api_chat():
    """Chat avec IA concernant une session spécifique."""
    data = request.json or {}
    question = data.get("question", "")
    session_id = data.get("session_id", "")
    
    if not question:
        return jsonify({"error": "Question manquante"}), 400
        
    session_path = os.path.join(PROJECT_ROOT, "logs", "sessions", session_id)
    trades_log = os.path.join(session_path, "trades.log")
    
    context = ""
    if os.path.exists(trades_log):
        with open(trades_log, "r") as f:
            lines = f.readlines()
            # Prendre les 100 dernières lignes pour le contexte Haiku
            context = "".join(lines[-100:])
            
    import anthropic
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
         return jsonify({"answer": "Clé API Anthropic non configurée. Impossible d'analyser l'historique."})
         
    try:
        client = anthropic.Anthropic(api_key=api_key)
        prompt = f"Voici les logs de trading récents de la session {session_id} :\n\n{context}\n\nL'utilisateur te pose cette question : {question}\nRéponds de manière concise (max 3 phrases) en te basant UNIQUEMENT sur ces logs. Si l'information n'y figure pas, dis-le poliment. Ne dis pas 'd'après les logs'."
        
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        return jsonify({"answer": response.content[0].text})
        
    except Exception as e:
        return jsonify({"error": str(e), "answer": f"Erreur lors de la communication avec l'IA: {e}"})

# ─────────────────────────────────────────────────────────────────
# ROUTES MANQUANTES (requises par l'ancien index.html)
# ─────────────────────────────────────────────────────────────────
@app.route("/api/pairs")
def api_pairs():
    return jsonify(ALL_PAIRS)


@app.route("/api/demo_orders")
def api_demo_orders():
    """Ordres de démonstration pour visualiser l'interface."""
    demo = [
        make_order(
            pair="XAUUSD", school="ict", direction="ACHAT",
            entry=2888.0, sl=2870.0, tp1=2922.0, tp2=2955.0, score=84, volume=0.10,
            pnl_pips=12.4, pnl_money=124.0, status="active", timeframe="M15",
            checklist=[
                {"item": "Killzone active (NY AM)", "status": "pass"},
                {"item": "MSS M15 bullish + Displacement", "status": "pass"},
                {"item": "FVG frais en Discount H1", "status": "pass"},
                {"item": "R:R ≥ 1.5", "status": "pass"},
            ],
            narrative="**Or — ACHAT Silver Bullet NY AM**\n\nMSS M15 bullish. FVG entre 2882-2894. TP1=2922, SL=2870. R:R=1.9",
        ),
        make_order(
            pair="EURUSD", school="ict", direction="VENTE",
            entry=1.0832, sl=1.0855, tp1=1.0802, tp2=1.0770, score=77, volume=0.05,
            pnl_pips=-8.0, pnl_money=-40.0, status="active", timeframe="H1",
            checklist=[
                {"item": "Killzone London", "status": "pass"},
                {"item": "MSS H1 bearish", "status": "pass"},
                {"item": "OB H1 non revisité", "status": "pass"},
                {"item": "News haute impact", "status": "fail"},
            ],
            narrative="**EURUSD — VENTE London**\n\nStructure H4 bearish. OB H1 à 1.0830-1.0845.",
        ),
        make_order(
            pair="GBPUSD", school="ict", direction="ACHAT",
            entry=1.2640, sl=1.2610, tp1=1.2690, tp2=1.2740, score=79, volume=0.05,
            status="pending", timeframe="M15",
            checklist=[
                {"item": "Killzone NY AM", "status": "pass"},
                {"item": "FVG M15 disponible", "status": "pass"},
                {"item": "MSS M5 bullish attendu", "status": "fail"},
            ],
            narrative="**GBPUSD — ACHAT en attente**\n\nFVG M15 entre 1.2630-1.2650. Attente MSS M5.",
            pending_conditions=["MSS M5 bullish dans le FVG", "Confirmation SMT EUR/GBP"],
        ),
        make_order(
            pair="EURUSD", school="ict", direction="ACHAT",
            entry=1.0755, sl=1.0730, tp1=1.0790, tp2=1.0825, score=81, volume=0.10,
            pnl_pips=77.0, pnl_money=770.0, status="closed", timeframe="M15",
            checklist=[
                {"item": "Killzone London", "status": "pass"},
                {"item": "MSS H1 bullish", "status": "pass"},
                {"item": "FVG M15 en Discount", "status": "pass"},
                {"item": "R:R ≥ 1.5", "status": "pass"},
            ],
            narrative="Setup Silver Bullet London. TP2 atteint. +77 pips.",
        ),
    ]
    status_filter = request.args.get("status")
    if status_filter and status_filter != "all":
        demo = [o for o in demo if o["status"] == status_filter]
    return jsonify(demo)


@app.route("/api/circuit_breaker")
def api_circuit_breaker():
    try:
        from data.trade_manager import CircuitBreaker
        cb = CircuitBreaker()
        return jsonify(cb.get_status())
    except Exception:
        return jsonify({"active": False, "reason": "", "trades_today": 0, "sl_streak": 0})


@app.route("/api/circuit_breaker/reset", methods=["POST"])
def api_circuit_breaker_reset():
    try:
        from data.trade_manager import CircuitBreaker
        cb = CircuitBreaker()
        cb.reset()
        log("Circuit Breaker réinitialisé.", "SUCCESS")
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 500


@app.route("/api/circuit_breaker/config", methods=["POST"])
def api_circuit_breaker_config():
    try:
        data = request.json or {}
        from data.trade_manager import CircuitBreaker
        cb = CircuitBreaker()
        cb.update_config(
            daily_loss_pct=data.get("daily_loss_pct"),
            max_trades=data.get("max_trades"),
            sl_streak=data.get("sl_streak")
        )
        log("Paramètres Circuit Breaker mis à jour.", "SUCCESS")
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 500


@app.route("/api/config/min_score", methods=["GET", "POST"])
def api_config_min_score():
    if request.method == "POST":
        try:
            val = int((request.json or {}).get("value", 75))
            val = max(0, min(100, val))
            with state_lock:
                bot_state["min_score"] = val
            broadcast("status", {"min_score": val})
            log(f"Baromètre confiance: {val}/100", "SUCCESS")
            return jsonify({"status": "success", "value": val})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 400
    with state_lock:
        return jsonify({"value": bot_state["min_score"]})


@app.route("/api/close_order", methods=["POST"])
def api_close_order():
    order_id = (request.json or {}).get("id")
    with state_lock:
        for o in bot_state["orders"]:
            if o["id"] == order_id and o["status"] == "active":
                o["status"] = "closed"
                o["closed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                broadcast("order_update", {"action": "update", "order": o})
                return jsonify({"ok": True})
    return jsonify({"ok": False, "message": "Ordre non trouvé ou déjà fermé"})


@app.route("/api/close_mt5", methods=["POST"])
def api_close_mt5():
    data = request.json or {}
    ticket = data.get("ticket")
    order_id = data.get("id")
    if not ticket:
        return jsonify({"ok": False, "message": "Ticket MT5 manquant"}), 400
    if trade_mgr:
        res = trade_mgr.close_position(int(ticket))
        if res.get("ok"):
            with state_lock:
                for o in bot_state["orders"]:
                    if o.get("id") == order_id or o.get("ticket") == ticket:
                        o["status"] = "closed"
                        o["closed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                        broadcast("order_update", {"action": "update", "order": o})
            return jsonify({"ok": True})
        return jsonify({"ok": False, "message": res.get("message")}), 500
    return jsonify({"ok": False, "message": "Trade Manager non initialisé"}), 500


@app.route("/api/cancel_pending", methods=["POST"])
def api_cancel_pending():
    order_id = (request.json or {}).get("id")
    with state_lock:
        for o in bot_state["orders"]:
            if o["id"] == order_id and o["status"] == "pending":
                o["status"] = "cancelled"
                o["closed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                broadcast("order_update", {"action": "update", "order": o})
                return jsonify({"ok": True})
    return jsonify({"ok": False, "message": "Ordre non trouvé ou non pending"})


@app.route("/api/exit", methods=["POST"])
def api_exit():
    log("Arrêt total de l'application...", "WARNING")
    stop_event.set()
    pause_event.clear()
    if mt5_conn:
        mt5_conn.disconnect()

    def kill_server():
        time.sleep(1)
        os.kill(os.getpid(), signal.SIGINT)

    threading.Thread(target=kill_server, daemon=True).start()
    return jsonify({"ok": True, "message": "Serveur en cours d'arrêt."})


@app.route("/api/force_stop", methods=["POST"])
def api_force_stop():
    stop_event.set()
    pause_event.clear()
    with state_lock:
        bot_state["status"] = "stopped"
        bot_state["current_pair"] = None
    broadcast("status", {"status": "stopped"})
    log("Bot arrêté de force.", "INFO")
    return jsonify({"ok": True})


# ─────────────────────────────────────────────────────────────────
# POINT D'ENTRÉE
# ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║     ICT ALGORITHMIC TRADING BOT — Dashboard v1.0        ║")
    print("║     5 Agents | 0 LLM | Algorithmes Purs ICT             ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()
    print("  Ouvrir : http://localhost:5000")
    print()

    # Init système en arrière-plan (ne bloque pas Flask)
    threading.Thread(target=init_system_async, daemon=True).start()

    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)