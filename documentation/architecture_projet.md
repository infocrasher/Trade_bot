# Architecture du Projet — Fée Maison Trade Bot

Ce document décrit l'architecture complète du projet de trading algorithmique, incluant sa structure de dossiers, ses modules principaux, et le flux logique du processus de décision.

## 📁 Structure Physique de l'Application

```text
Trading_Bot_Project/
│
├── config.py                 # Configuration globale (paires, risques, intervalles)
├── dashboard.py              # Point d'entrée principal : Serveur Flask, UI, et boucle de trading (Paper Monitor)
├── main.py                   # (Alternative CLI) Point d'entrée pour exécution sans interface web
├── requirements.txt          # Dépendances Python (pandas, numpy, flask, anthropic, etc.)
│
├── agents/                   # Intelligence Artificielle et Trading Logics
│   ├── ict/                  # École de trading ICT (Inner Circle Trader)
│   │   ├── structure.py      # A1 : Analyse de structure HTF (Order Blocks, FVGs, Sweeps)
│   │   ├── time.py           # A2 : Analyse temporelle (Killzones, Macros algorithmiques)
│   │   ├── entry.py          # A3 : Points d'entrée (OTE, Confirmations M5, SL/TP dynamiques)
│   │   ├── macro.py          # A4 : Contexte Macro (DXY, COT, IPDA Ranges)
│   │   └── orchestrator.py   # A5 : Orchestrateur ICT (Fusion des analyses A1+A2+A3+A4)
│   │
│   ├── elliott/              # École de trading Elliott Waves (Vagues d'Elliott)
│   │   ├── wave_counter.py   # Compteur de vagues et reconnaissance de patterns (Impulsion/Correction)
│   │   ├── scorer.py         # Calcul du score basé sur les règles de Fibonacci, Alternance, Momentum
│   │   └── orchestrator.py   # Validation et filtrage des signaux Elliott
│   │
│   ├── agent_llm_validator.py # A6 : Wrapper pour l'API Claude (Validation finale des setups)
│   ├── llm_validator.py       # Configuration et logique métier de facturation pour Claude Haiku
│   └── meta_orchestrator.py   # Fusion inter-écoles (Confrontation des signaux ICT vs Elliott)
│
├── documentation/            # Documentation métier et technique
│   ├── architecture_projet.md # Ce fichier
│   ├── ict_encyclopedia.md   # Base de connaissances rigoureuse des concepts ICT (Règles, Killzones, Setup Grail)
│   ├── rapport_audit.md      # Rapport détaillé sur l'état du code, forces, et faiblesses
│   ├── Task.md               # Suivi des tâches (Checklist globale)
│   └── bot_functionalities.md# Liste détaillée des fonctionnalités du dashboard et du bot
│
├── logs/                     # Fichiers de journalisation (Rotatifs)
│   ├── bot.log               # Événements système, erreurs, et analyses détaillées (DEBUG)
│   ├── trades.log            # Historique condensé des décisions de trading (INFO)
│   └── sessions/             # Logs découpés dynamiquement par session d'exécution
│       └── SESSION__YYYY-MM-DD_HH-MM-SS/
│           ├── bot.log       # Débogage limité à cette session précise
│           └── trades.log    # Décisions de trading de cette session
│
├── paper_trading/            # Environnement de simulation
│   └── paper_trades.json     # Base de données locale persistant les positions ouvertes, PnL, et historiques
│
└── templates/                # (Optionnel si Flask Server-Side Rendered) Fichiers HTML pour le Dashboard
```

---

## ⚙️ Flux de Décision Algorithmique (Pipeline)

Le bot analyse les graphiques selon l'approche "Multi-Agents" pour garantir une précision maximale. L'architecture est profondément calquée sur la stricte **Encyclopédie ICT**.

1. **Extraction de Données (MT5)**
   ↳ Le bot télécharge l'historique complet (M5 à Daily) via `MetaTrader5` pour chaque paire définie dans `config.py`.

2. **Évaluation Multi-Timeframes (ICT Agents)**
   - **A1 — Structure :** Biais directionnel (Daily/H4), détection des Order Blocks (OB) et Fair Value Gaps (FVG).
   - **A2 — Temporalité :** Vérifie si on est dans une *Killzone* ou une *Macro* algorithmique valide. Si hors fenêtre → `NO_TRADE`.
   - **A3 — Zones d'Entrée :** Cherche une *Optimal Trade Entry* (OTE 62-79%). Applique **strictement R:R ≥ 2.0**.
   - **A4 — Contexte Macro :** Vérifie la corrélation DXY (Dollar Index) et la saisonnalité institutionnelle.

3. **Orchestrateur Local (ICT)**
   ↳ Fusionne A1+A2+A3+A4. Si le système valide un Signal "EXECUTE" avec la condition stricte **HTF Concordant**, il calcule un score de confiance `/100`.

4. **Évaluation Alternative (Elliott Waves)**
   ↳ Parallèlement, le module Elliott compte les vagues (1-2-3-4-5, A-B-C) et émet un signal indépendant.

5. **Méta-Orchestrateur**
   ↳ Confronte le Signal ICT et le Signal Elliott. Un consensus renforce le setup.

6. **Agent Validateur LLM (Claude Haiku - Le Superviseur)**
   ↳ Si le Signal ICT est `EXECUTE` avec un score **≥ 70/100**, la narrative complète du trade, le contexte Macro, la Structure, et le Timing sont envoyés au LLM. 
   - Le LLM lit le setup et le confronte à l'encyclopédie ICT.
   - Si le LLM détecte un "*Red Flag*" majeur → Pénalise de 15% (Le score retombe sous les 70/100, le bot décide de `RESTER_DEHORS`).
   - S'il valide → le bot passe à l'action.

7. **Paper Monitor (Exécution et Gestion de Position)**
   - **Ouverture :** Création d'un trade formel simulé dans `paper_trades.json`.
   - **Suivi (Monitor) :** Calcul en temps réel du PnL flottant, vérification si Target (TP1, TP2, TP3) ou Stop-Loss (SL) est touché.
   - **Trailing :** Gère le déplacement au *Break-Even* si le ratio atteint 1:1, et ferme partiellement des lots (Partial Profits).

---

## 🔒 Principes de Conception Sensibles (Sécurité / Stabilité)

1. **Pas de base de données relationnelle complexe :** 
   Le bot tourne de manière autonome via `paper_trades.json`, très léger en I/O.
2. **Rotating Logs :**
   Les logs (`bot.log` et `trades.log`) limitent eux-mêmes leur taille (max 10MB) pour empêcher un blocage de l'espace disque sur le VPS.
3. **Optimisation Tarifaire de l'API :**
   Intégration drastique du **Prompt Caching d'Anthropic**. En combinant le modèle *Haiku* et le cache du système, le coût LLM a été réduit de plus de 90% (~$0.001 par appel), le rendant hautement soutenable pour un monitoring continu.
4. **Isolations Horaires Horizontales :**
   Chaque "horizon" (Scalp, Intraday, Daily, Weekly) de chaque devise possède ses propres règles (ex. `max_distance_pips`). Les rejets d'une paire génèrent un verrouillage logique (Cooldown) empêchant le spam d'API et l'overtrading.
