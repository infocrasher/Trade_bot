"""
=============================================================
  CONFIGURATION CENTRALE - Systme Multi-Agent Trading Forex
=============================================================
  Ne modifiez que les valeurs entre guillemets " "
  Les lignes commenant par # sont des commentaires (ignores)
=============================================================
"""

# 
# 1. CLÉS API (Cerveaux de vos agents IA)
# 
# Stratégie : "auto" (fallback sur Gemini/Ollama), "groq_only", "gemini_only", "ollama_only"
LLM_STRATEGY = "auto"

# 🦙 LLM LOCAL (Ollama - Optionnel)
OLLAMA_ENABLED  = False
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL    = "llama3"

# 1.1 GROQ (Ultra-rapide, gratuit 14K req/jour)
GROQ_API_KEY = ""
GROQ_MODEL   = "llama-3.1-8b-instant"

# 1.2 GEMINI (Google AI Studio - 1500 req/jour gratuit)
import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL   = "gemini-2.5-flash"

# Clé spécifique pour la vision (optionnelle si GEMINI_API_KEY est déjà remplie)
GEMINI_VISION_API_KEY = os.getenv("GEMINI_VISION_API_KEY", "")


# 1.3 ANTHROPIC (Claude - Optionnel)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL   = "claude-3-5-sonnet-20241022"

# Clé TwelveData (Rotation de 4 clés)
TWELVE_DATA_API_KEYS = [
    os.getenv("TWELVE_DATA_API_KEY_1", ""),
    os.getenv("TWELVE_DATA_API_KEY_2", ""),
    os.getenv("TWELVE_DATA_API_KEY_3", ""),
    os.getenv("TWELVE_DATA_API_KEY_4", ""),
]
# Rétrocompatibilité
TWELVE_DATA_API_KEY = TWELVE_DATA_API_KEYS[0] if TWELVE_DATA_API_KEYS else ""

# 
# 2. CONNEXION METATRADER 5
# 
# Renseignez les infos de votre compte de DMONSTRATION d'abord !
MT5_ACCOUNT   = 103490093   # Numro de compte
MT5_PASSWORD  = os.getenv("MT5_PASSWORD", "")  # Mot de passe du compte
MT5_SERVER    = "MetaQuotes-Demo" # Serveur broker
MT5_PATH      = ""          # Laisser vide = dtection automatique


# 
# 3. PAIRES DE TRADING (Activer = True)
# 
TRADING_PAIRS = [
    "EURUSD",
    "GBPUSD",
    "AUDUSD",
    "NZDUSD",
    "USDJPY",
    "USDCAD",
    "USDCHF",
    "BTCUSD",
]


# 
# 4. PARAMTRES DE RISQUE ET PHILOSOPHIE
# 
# Mode PURE ICT (Focus exclusif sur ICT)
# True  = Utilise uniquement l'Expert ICT (autres experts en standby)
# False = Systme multi-agent complet
PURE_ICT_MODE = True

# Score minimum requis pour ouvrir un trade (entre 0 et 100)
MIN_CONFIDENCE_SCORE = 70    # Rehausse pour plus de qualite

# Ratio Risque/Rcompense minimum (1:2 = pour chaque 1$ risqu, on vise 2$)
MIN_RISK_REWARD       = 2.0

# Risque maximum par trade (% de votre capital)
RISK_PER_TRADE_PCT    = 1.0   # 1% recommand pour dmarrer

# Mode de trading :
# "alert_only"  = l'IA vous envoie une alerte, vous cliquez vous-mme
# "semi_auto"   = alerte + confirmation manuelle requise
# "full_auto"   = l'IA ouvre le trade automatiquement (AVANC)
TRADING_MODE = "full_auto"

# Mode Paper Trading (simulation sans capital réel)
# True  = Aucun vrai trade — Enregistré dans data/journal/
# False = Trading réel (ou alert_only)
PAPER_TRADING = True


# L'influence de chaque expert sur la dcision finale
if PURE_ICT_MODE:
    AGENT_WEIGHTS = {
        "ict":          100,   # Focus total sur ICT
        "footprint":    0,     # Standby
        "fundamental":  0,     # Standby
        "elliott":      0,     # Standby
    }
else:
    AGENT_WEIGHTS = {
        "ict":          35,
        "footprint":    30,
        "fundamental":  20,
        "elliott":      15,
    }


# 
# 6. SESSIONS DE TRADING (Heure New York - EST)
# 
SESSIONS = {
    "asia_killzone":    {"start": "20:00", "end": "22:00"},
    "london_killzone":  {"start": "02:00", "end": "05:00"},
    "ny_am_killzone":   {"start": "07:00", "end": "10:00"},
    "ny_pm_killzone":   {"start": "10:00", "end": "12:00"},
    "silver_bullet_1":  {"start": "03:00", "end": "04:00"},
    "silver_bullet_2":  {"start": "10:00", "end": "11:00"},
    "silver_bullet_3":  {"start": "14:00", "end": "15:00"},
}

# Force analyze (bypass le filtre Killzone pour tester 24/7)
FORCE_ANALYZE = False

# Macros algorithmiques (fentres de 20 minutes prcises)
ALGO_MACROS = [
    {"start": "08:30", "end": "08:50"},
    {"start": "09:50", "end": "10:10"},
    {"start": "10:50", "end": "11:10"},
    {"start": "12:10", "end": "12:30"},
]


# 
# 7. FICHIERS DU SYSTME
# 
import os
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
KNOWLEDGE_DIR = os.path.join(BASE_DIR, "knowledge")
REPORTS_DIR   = os.path.join(BASE_DIR, "reports")
ICT_RULES_DOC = os.path.join(KNOWLEDGE_DIR, "ict_rules.md")


# 
# 8. TELEGRAM NOTIFICATIONS
# 
# Créer un bot via @BotFather → Copier le token ici
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")
# Seuil de score minimum pour envoyer une alerte Telegram
TELEGRAM_MIN_SCORE = 70         # Alertes uniquement si score ICT >= 70/100


# 
# 9. GESTION DU CAPITAL & CIRCUIT BREAKER
# 
ACCOUNT_BALANCE = 500.0   # capital réel paper trading
RISK_PERCENT    = 1.0     # risque par trade en %

# Arrêt automatique du trading si la perte journalière dépasse ce seuil
CIRCUIT_BREAKER_MAX_DAILY_LOSS_PCT = 3.0    # -3% du capital = STOP total
CIRCUIT_BREAKER_MAX_TRADES_PER_DAY = 5      # Max 5 trades/jour/paire
CIRCUIT_BREAKER_COOLDOWN_HOURS     = 4      # Pause de 4h après déclenchement
CIRCUIT_BREAKER_MAX_STOPLOSS_COUNT = 3      # 3 SL en série = pause auto


# 
# 10. CORRÉLATION DES PAIRES
# 
# Groupes de paires fortement corrélées (même exposition dollar)
# Le système refusera d'ouvrir plus de MAX_CORRELATED_TRADES dans un même groupe
CORRELATION_GROUPS = [
    ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD"],  # Corrélés positifs (USD faible)
    ["USDCHF", "USDJPY", "USDCAD"],             # Corrélés positifs (USD fort)
    ["XAUUSD"],                                  # Or — traité séparément
    ["BTCUSD"],                                  # Crypto
]
MAX_CORRELATED_TRADES = 2  # Max 2 trades dans la même direction dans un groupe
