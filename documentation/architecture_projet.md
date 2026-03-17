# Architecture du Projet — Fée Maison Trade Bot

Ce document décrit l'architecture complète du projet de trading algorithmique, incluant sa structure de dossiers, ses modules principaux, et le flux logique du processus de décision.

## 📁 Structure Physique de l'Application

```text
Trading_Bot_Project/
│
├── config.py                 # Configuration globale (paires, risques, rotation 7 clés API TwelveData via .env)
├── dashboard.py              # Dashboard V0 (TakeOption) : Serveur Flask, UI temps réel, API et boucle de trading
├── main.py                   # (Alternative CLI) Point d'entrée sans interface web
├── requirements.txt          # Dépendances Python
├── .env                      # Clés API sensibles (JAMAIS committé sur Git)
│
├── agents/                   # Intelligence Artificielle et Trading Logics
│   ├── ict/                  # École de trading ICT (Inner Circle Trader)
│   │   ├── structure.py      # A1 : Analyse de structure HTF (Order Blocks, FVGs, Sweeps)
│   │   ├── ob_scorer.py      # (Helper A1) Évalue la qualité d'un OB sur 5 critères (A++)
│   │   ├── time_session.py   # A2 : Analyse temporelle (Killzones, Macros, PO3, AMD Weekly)
│   │   ├── entry.py          # A3 : Points d'entrée (OTE 62-79%, confluences, R:R ≥ 2.0)
│   │   ├── macro.py          # A4 : Contexte Macro (DXY, COT, IPDA Ranges, T-20)
│   │   ├── enigma.py         # (Helper A5) Niveaux algorithmiques (.00, .20, .50, .80)
│   │   ├── sod_detector.py   # (Helper A5) State of Delivery 5 états (STRONG/WEAK/ACC/MANIP)
│   │   ├── liquidity_tracker.py # LRLR/HRLR — compte les obstacles entre prix et cible
│   │   ├── ote_tracker.py    # State Machine OTE (WAITING/TRIGGERED/INVALIDATED) — persistant
│   │   └── orchestrator.py   # A5 : Orchestrateur ICT (fusion A1+A2+A3+A4, scoring KB4 + Bonus P-B1)
│   │
│   ├── elliott/              # École de trading Elliott Waves
│   │   ├── wave_counter.py   # Compteur de vagues (Impulsion/Correction)
│   │   ├── scorer.py         # Score basé sur Fibonacci, Alternance, Momentum
│   │   └── orchestrator.py   # Validation et filtrage des signaux Elliott
│   │
│   ├── vsa/                  # Volume Spread Analysis (optionnel)
│   │
│   ├── gate_logger.py        # Logs des refus par école (ICT/Elliott/Meta) → data/gate_logs/
│   ├── post_mortem.py        # Analyse quotidienne des setups bloqués (Gate Regret Rate)
│   ├── telegram_notifier.py  # Alertes Telegram en temps réel (via TakeOptionBot)
│   ├── agent_llm_validator.py # A6 : Validation LLM Claude Haiku avec Prompt Caching
│   ├── llm_validator.py      # Logique métier et facturation Claude
│   └── meta_orchestrator.py  # Fusion ICT vs Elliott, décision finale OUVRIR/RESTER_DEHORS
│
├── data/                     # Données persistantes (hors logs)
│   ├── gate_logs/            # JSON par date : ict_blocked, elliott_blocked, meta_blocked
│   │   └── post_mortem_YYYY-MM-DD.json  # Rapport quotidien (Gate Regret %)
│   ├── ote_setups.json       # State machine OTE — setups WAITING en cours
│   └── circuit_breaker_state.json  # État du Circuit Breaker (pertes consécutives)
│
├── documentation/            # Documentation métier et technique
│   ├── architecture_projet.md  # Ce fichier
│   ├── Task.md               # Suivi des tâches (Checklist globale)
│   ├── a_retenir.md          # Analyse KB4 vs notre bot — concepts manquants et priorités
│   └── avis_ia/              # Avis des différents LLMs sur le bot (ChatGPT, Gemini, Grok...)
│
├── logs/                     # Fichiers de journalisation rotatifs
│   ├── bot.log               # Événements système (DEBUG)
│   ├── trades.log            # Décisions de trading (INFO)
│   └── sessions/SESSION__YYYY-MM-DD_HH-MM-SS/
│
├── tests/                    # Tests unitaires et d'intégration
│   └── run_all_tests.sh      # Script global dynamique d'exécution de tous les tests du projet
│
└── paper_trading/            # Environnement de simulation (exclu de Git)
    └── paper_trades.json
```

---

## ⚙️ Flux de Décision Algorithmique (Pipeline)

```
Données MT5 / TwelveData
        ↓
   A1 — Structure (HTF/LTF)
        ↓
   A2 — Timing (Killzone + Macro)
        ↓
   A3 — Entry (OTE + OTE Tracker)  ←── setup WAITING récupéré si prix pas encore dans zone
        ↓
   A4 — Macro (IPDA, T-20, DXY)
        ↓
   A5 — Orchestrateur ICT (KB4 Scoring)
        │    Gates : KS4 (spread), KS8 (CBDR), SOD, SL min, R:R, ENIGMA malus...
        ↓
Elliott Wave Orchestrateur (parallèle)
        ↓
   Meta-Orchestrateur
        │    Consensus ICT+Elliott → Score fusion
        ↓
   LLM Validateur (Claude Haiku) ← si score ≥ 70/100
        ↓
   Décision finale
        │
        ├── OUVRIR → Paper Trade créé + clear_triggered() + Alerte Telegram
        └── RESTER_DEHORS → log_meta_blocked() + Gate Log JSON
```

---

## 🔔 Système de Logging & Observabilité

### Gate Logger (`agents/gate_logger.py`)
Chaque refus d'entrée est enregistré dans `data/gate_logs/` :
- `ict_blocked_YYYY-MM-DD.json` — rejets Agent ICT (OTE, R:R, confluence)
- `elliott_blocked_YYYY-MM-DD.json` — rejets Elliott (score, vague ambiguë)
- `meta_blocked_YYYY-MM-DD.json` — rejets du Meta-Orchestrateur (désaccord, score insuffisant)

### Post-Mortem (`agents/post_mortem.py` & UI TakeOption)
Lance chaque soir à 23h00 UTC via le scheduler de `dashboard.py`.
Compare Entry/SL/TP1 des setups bloqués avec le prix réel (calcul du **Gate Regret Rate**).
Affiché dynamiquement sur le Dashboard V0 via `/api/paper_history?date=YYYY-MM-DD`.
```bash
python3 agents/post_mortem.py  # Lancement manuel
```

### Alertes Telegram
- Bot : **TakeOptionBot**
- Config dans `.env` : `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- Seuil : uniquement signaux ≥ 70/100 (configurable dans `config.py`)

---

## 🧠 OTE Tracker — State Machine

Gère les setups en attente (prix pas encore dans la zone OTE) entre les cycles M5.

| Fonction | Déclencheur |
|---|---|
| `save_setup()` | Pas de confluence en OTE → sauvegarde en WAITING |
| `tick_cycle()` | Chaque cycle M5 sur un setup WAITING |
| `invalidate_setup()` | Bias changé ou timeout 24h (288 cycles) |
| `get_waiting_setup()` | Avant chaque appel agent3 → réinjection OBs/FVGs |
| `clear_triggered()` | Après création d'un trade (action == "new") |

Stockage persistant : `data/ote_setups.json`

---

## 🔒 Principes de Conception (Sécurité / Stabilité)

1. **Clés API dans `.env` uniquement** — jamais hardcodées dans `config.py` ou commitées sur Git.
2. **Pas de DB relationnelle** — tout est en JSON léger pour une portabilité maximale.
3. **Rotating Logs** — `bot.log` et `trades.log` limités à 10MB (30 fichiers max).
4. **Optimisation LLM** — Prompt Caching Anthropic, modèle Haiku → -90% de coût (~$0.001/appel).
5. **Circuit Breaker** — Arrêt automatique à -3% capital/jour, max 5 trades/jour/paire, 4h cooldown.
6. **OTE Tracker** — Expiration automatique à 288 cycles (24h en M5) pour éviter les setups périmés.
7. **Suite de Tests Isolés** — Validation continue via `tests/run_all_tests.sh` (> 240 tests natifs).
