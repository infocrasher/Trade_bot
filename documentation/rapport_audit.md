# RAPPORT D'AUDIT TECHNIQUE : Fateh_trade_bot (TradingAI)

## SECTION 1 — Architecture

Le projet est structuré comme un **Système Multi-Agent** piloté par une intelligence artificielle (LLM) et des déclencheurs temporels.

### Principaux Fichiers et Rôles
1. **`main.py`** (277 lignes) : Point d'entrée principal pour l'exécution en ligne de commande. Il orchestre la collecte de données MT5, lance l'analyse via l'Expert ICT et termine par la décision du Chef d'Orchestre.
2. **`scheduler.py`** (395 lignes) : Cœur de la planification temporelle (Cron-like). Il lance les plannings hebdomadaires, quotidiens (DailyPlanner), le scalp monitor (toutes les 5 min) et les triggers (toutes les 1 min).
3. **`dashboard.py`** (1451+ lignes) : Serveur web Flask pour le monitoring en temps réel.
4. **`config.py`** (168 lignes) : Fichier central contenant les clés API (Groq/Gemini), les paires tradées, les seuils de risque et les modes opératoires.
5. **`agents/`** : Dossier contenant les experts (ICT, Auditeur, Fondamental, Elliott, Footprint, Chef d'Orchestre).
6. **`data/`** : Dossier gérant les interactions (MT5Connector, TradeManager, MemoryManager, Planner).

### Arbre de Dépendances (Flux Principal)
`main.py` -> `data/mt5_connector.py` -> `agents/ict_expert.py` (qui appelle `gemini_client.py` et lit `knowledge/`) -> `agents/ict_auditor.py` -> `agents/conductor.py`.

---

## SECTION 2 — Agents / Logique de trading

1. **`agents/ict_expert.py` (`ICTExpertAgent` / `KnowledgeManager`)**
   - **Méthodes :** `analyze()`, `_build_analysis_prompt()`, `_summarize_tl()`, `_extract_score()`, `_extract_direction()`
   - **Logique :** Extrait le contexte de marché (OHLCV, MTF) et injecte le savoir de l'encyclopédie ICT dans un prompt pour Gemini/Groq. La décision est purement générée par le LLM (texte vers JSON/variables).
   - **Timeframes :** Analyse Multi-TF (W1, D1, H4, H1, M15).

2. **`agents/conductor.py` (`ConductorAgent`)**
   - **Méthodes :** `decide()`, `_build_decision_prompt()`, `_save_to_log()`
   - **Logique :** Récolte les rapports des différents experts, applique les poids (définis dans `config.py`), vérifie le seuil minimal de confiance, et prend la décision finale (`OUVRIR`, `ATTENDRE`, etc.).

3. **`agents/strategy_trigger.py` (`StrategyTrigger`)**
   - **Méthodes :** `scan_minute()`, `_in_silver_bullet()`, `_in_macro_window()`, `_detect_eqh_eql_sweep()`, `_detect_opening_range_break()`
   - **Logique :** Agent 100% mathématique (sans IA) qui scanne le marché chaque minute pour détecter des horaires précis (Killzones, Macros) et des sweep de liquidité.

4. **Experts Secondaires (`FundamentalExpertAgent`, `ElliottExpertAgent`, `FootprintExpertAgent`)**
   - Conçus pour rajouter de la validation, mais mis "en veille" si `PURE_ICT_MODE = True`.

---

## SECTION 3 — Données et APIs

- **Market Data :** Directement depuis le broker via l'API locale `MetaTrader5` (fichier `data/mt5_connector.py`). Possibilité de récupérer des ticks, de l'historique OHLCV, et des screenshots (`capture_multi_timeframe_charts`).
- **LLM APIs :** Connexion multiple via `gemini_client.py`.
  - **Groq** (Llama 3.1) défini par défaut pour la vitesse.
  - **Gemini 2.0 Flash** pour les requêtes complexes ou la vision informatique.
  - **Ollama** pour de l'inférence locale hors ligne.
- **Dashboard :** Serveur Web basé sur **Flask**.
- **Notifications :** Intégration **Telegram** (`notifications/telegram_notifier.py`).

---

## SECTION 4 — Configuration et paramètres

Fichier pertinent : `config.py`
- **Instruments :** Forex (EURUSD, GBPUSD, AUDUSD, NZDUSD, USDJPY, USDCAD, USDCHF) et Crypto (BTCUSD). Configuration groupée par corrélations pour éviter de surexposer le capital.
- **Risque :** 
   - `RISK_PER_TRADE_PCT` = 1.0 (1% par trade)
   - `MIN_RISK_REWARD` = 2.0 (RR Min 1:2)
   - Système de "Circuit Breaker" bloquant la journée si max perte journalière (-3%) ou 3 Stop-Loss d'affilée.
- **Modes :** `PAPER_TRADING` (True/False) permet d'enregistrer des trades fictifs dans des JSON plutôt que l'exécution réelle MT5.

---

## SECTION 5 — Concepts ICT couverts

La grande majorité des concepts est **injectée via la base de connaissance MD au LLM**, et non pas programmée mathématiquement dans le code.

- [x] Swing Highs / Lows *(Via IA)*
- [x] BOS (Break of Structure) *(Via IA)*
- [x] CHoCH (Change of Character) *(Via IA)*
- [x] MSS (Market Structure Shift) *(Via IA)*
- [x] FVG (Fair Value Gap) *(Via IA)*
- [x] Order Blocks *(Via IA)*
- [x] Breaker Blocks *(Via IA)*
- [x] Displacement *(Via IA)*
- [x] Liquidity Sweeps *(Via math dans strategy_trigger.py)*
- [x] Equal Highs / Equal Lows (EQH/EQL) *(Via IA)*
- [x] Killzones (Asian, London, NY AM, NY PM) *(Via math dans config.py / strategy_trigger.py)*
- [x] Silver Bullet Windows *(Via math dans strategy_trigger.py)*
- [x] 12 Macros Algorithmiques *(Via math dans strategy_trigger.py)*
- [x] Midnight Open *(Calculé dans mt5_connector.py)*
- [ ] Asian Range *(Seulement conceptuel pour le prompt)*
- [x] Power of 3 (AMD) *(Via IA)*
- [ ] Judas Swing
- [ ] Seek & Destroy (lundi)
- [ ] Weekly Profile (5 types)
- [x] OTE (Optimal Trade Entry) Fibonacci 62-79% *(Via IA)*
- [x] Premium / Discount zones *(Via IA / MT5 data)*
- [x] Confluence scoring (OB + FVG + OTE) *(Via logiques de Scoring IA)*
- [x] Draw on Liquidity (PDH/PDL, PWH/PWL, EQH/EQL) *(Via IA)*
- [ ] Standard Deviation projections
- [ ] IPDA Data Ranges (20/40/60 jours)
- [ ] Quarterly Shifts
- [ ] Saisonnalité
- [ ] COT Report
- [x] SMT Divergence *(Via IA + paires corrélées)*
- [x] DXY corrélation *(Via IA + config.py)*
- [ ] Calendrier économique / News filter
- [ ] NWOG / NDOG
- [ ] Smooth High / Jagged High
- [ ] Unicorn Model
- [ ] Market Maker Models (MMBM/MMSM)
- [ ] London Protractor
- [ ] LRLR / HRLR
- [x] Position Sizing (formule lots) *(via dashboard.py & ordonnanceur)*
- [ ] Break-even management
- [ ] Partial profits
- [ ] Trailing stop
- [x] Multi-timeframe analysis (MN, W1, D1, H4, H1, M15, M5) *(Via mt5_connector.py)*

*(Note: Le code source du dossier parent contient des tests pour des algos mathématiques stricts (ex: detect_mss), mais ils ne sont pas activement branchés dans la boucle LLM `TradingAI/`)*.

---

## SECTION 6 — Base de connaissances

- **`knowledge/`** (Environs 60 Ko) : Contient la Bible ICT pour l'IA. `ict_encyclopedia.md`, `ict_detection_rules.md`, `ict_strategy_triggers.md`. L'outil `ict_knowledge_index.json` cartographie les lignes pour ne charget que le contexte pertinent via `KnowledgeManager`.
- **`memory/`** : Stocke un JSON de "Mémoire Narrative" par paire (ex: "Hier, nous avons sweep le PDL. J'attends une continuation..."). Permet au chatbot de se souvenir de l'historique D-1.
- **`plans/`** : L'ordonnanceur stocke ici les plans journaliers et scalp (Générés par le `DailyPlannerAgent`).

---

## SECTION 7 — Dashboard et interface

- **Serveur :** Flask (Port 5000). Route principale `/` + route API `/api/data` via Server Sent Events (SSE).
- **Frontend :** Dossier `dashboard/templates/index.html`. Un frontend riche (style Exness/Terminal), construit en HTML/CSS/JS vanille, écoutant les flux SSE (`/api/stream`) pour rafraîchir en direct le statut de MT5, les ordres (Actifs, Pending, Clos), et les logs IA sans rechargement de page.

---

## SECTION 8 — Tests

- **Framework :** Scripts Python nus (pas de pytest, pas d'unittest natif). Exécution directe de méthodes.
- **Couverture (Très faible dans `TradingAI`)** :
  - `test_ict_real.py` : Test l'endpoint Groq avec de l'OHLCV mocké.
  - `test_keys.py` : Test la validité des API Keys.
  - `test_mt5.py` : Test la connexion au terminal MT5 virtuel.
- Note : Les **96 tests robustes** écrits à l'étape précédente sont situés dans le dossier parent du bot, mais n'évaluent pas l'interpréteur LLM.

---

## SECTION 9 — Points forts et points faibles

### Points Forts
1. **Architecture Agentique Élégante :** Séparation claire entre Experts (ICT, Fondamental), Auditeurs, et Chef d'Orchestre.
2. **Mémoire Narrative (RAG) :** L'historique permet à l'IA d'avoir un suivi institutionnel continu, éliminant "l'amnésie" des requêtes isolées.
3. **Tableau de Bord SSE :** Interface propre, professionnelle et mis-à-jour en temps réel rendant le bot transparent.
4. **Circuit Breaker Intégré :** Logique défensive solide avec cooldown et killswitches quotidiens (anti-tilt).
5. **Couche Multimodale :** Support embarqué de l'analyse via Vision API (Graphiques M15, H1, H4, D1 envoyés à Gemini).

### Points Faibles
1. **Dépendance massive à la nature stochastique du LLM :** Toute la logique repose sur la bonne compréhension verbale de Gemini/Groq. Le parsing du `_extract_score` via Regex est très fragile.
2. **Latence d'exécution :** Le pipeline (Graphique -> Base 64 -> Requête Groq -> Réponse -> Conductor) pour le scalping M5 n'est pas viable pour un High Frequency Trading.
3. **Absence de tests natifs (Pytest) pour le parser textuel** : Les réponses LLM étant aléatoires, des tests de non-régression seraient cruciaux.
4. **Calcul ICT Non Mathématique :** Bien que le Prompt précise les concepts d'OTE, FVG, l'IA "hallucine" souvent l'emplacement des blocs. Le manque des algorithmes stricts (conçus au préalable) dans la boucle affaiblit la précision.
5. **Manque de Gestion Active du Trade :** Le code gère bien le Pending/Active, mais a très peu d'options de Trailing Stop, Break Even, ou de fermetures partielles intelligentes implémentées.

---

## SECTION 10 — Code brut des fonctions clés

### 1. `run_analysis` (depuis `main.py`)
Le pipeline principal de demande d'analyse :

```python
def run_analysis(pair: str, mt5: MT5Connector, agents: dict, use_vision: bool = False) -> dict:
    """Lance l'analyse complète pour une paire de devises."""
    market_data = mt5.get_market_data(pair)
    
    image_paths = None
    if use_vision:
        tf_images = mt5.capture_multi_timeframe_charts(pair)
        if tf_images: image_paths = list(tf_images.values())
            
    # ÉTAPE 2 : Expert ICT (Injection avec Mémoire)
    ict_report = agents["ict_expert"].analyze(market_data, image_paths=image_paths)
    ict_direction = ict_report.get("ict_direction", "NEUTRE")
    
    # ÉTAPE 3 : Auditeur (Check sécurité)
    ict_audit = agents["ict_auditor"].audit(ict_report)
    
    # Autres experts... (coupé pour la brièveté)
    fundamental_report = {"confidence_score": 50}
    elliott_report     = {"confidence_score": 50}
    footprint_report   = {"confidence_score": 50}
    
    # ÉTAPE 7 : Chef d'Orchestre (Décision pondérée)
    all_reports = {
        "ict_report": ict_report,
        "ict_audit": ict_audit,
        "fundamental_report": fundamental_report,
        "elliott_report": elliott_report,
        "footprint_report": footprint_report,
        "market_data": market_data,
    }
    
    final_decision = agents["conductor"].decide(all_reports)
    return final_decision
```

### 2. `ICTExpertAgent.analyze` (depuis `agents/ict_expert.py`)
Génère le texte source du LLM. Remarquez l'usage de `KnowledgeManager` :

```python
def analyze(self, market_data: dict, **kwargs) -> dict:
    # Récupération Contexte & RAG
    image_path = kwargs.get('image_path')
    pair = market_data.get('pair', 'N/A')
    memory = self.memory_manager.load_memory(pair)
    
    context_keywords = [pair, market_data.get('ny_time', '')]
    knowledge_context = self.km.get_relevant_sections(context_keywords)
    detection_rules = self.km.get_full_rules()
    
    analysis_prompt = self._build_analysis_prompt(market_data, memory)
    current_images = kwargs.get('image_paths') or ([image_path] if image_path else [])
    
    # Requête Multimodale ou Textuelle API
    if current_images:
        full_system_prompt = f"{ICT_SYSTEM_PROMPT_TEMPLATE.format(knowledge_context=knowledge_context, detection_rules=detection_rules)}\n\nINSTRUCTIONS VISION:\n{ICT_VISION_PROMPT_TEMPLATE.format(pair=pair, count=len(current_images))}"
        raw_analysis = generate(system_prompt=full_system_prompt, user_prompt=analysis_prompt, images=valid_pil_images)
    else:
        system_prompt = ICT_SYSTEM_PROMPT_TEMPLATE.format(knowledge_context=knowledge_context, detection_rules=detection_rules)
        raw_analysis = generate(system_prompt=system_prompt, user_prompt=analysis_prompt)
    
    # Parsing risqué par expressions régulières
    score = self._extract_score(raw_analysis)
    ict_direction = self._extract_direction(raw_analysis)
    comment = self._extract_comment(raw_analysis)
    
    if comment:
        self.memory_manager.update_narrative(pair, comment)

    return {
        "score": score,  
        "ict_direction": ict_direction,
        "raw_analysis": raw_analysis,
        "status": "success"
    }
```

### 3. `ConductorAgent.decide` (depuis `agents/conductor.py`)
Prise de décision mathématique combinée à une validation LLM de l'action à mener.

```python
def decide(self, all_reports: dict) -> dict:
    ict_score = all_reports.get("ict_report", {}).get("confidence_score", 0)
    ict_approved = all_reports.get("ict_audit", {}).get("approved", False)
    w = config.AGENT_WEIGHTS
    
    scores = {
        "ict":         ict_score,
        "fundamental": all_reports.get("fundamental_report", {}).get("confidence_score", 50),
        "elliott":     all_reports.get("elliott_report", {}).get("confidence_score", 50),
        "footprint":   all_reports.get("footprint_report", {}).get("confidence_score", 50),
    }
    
    # Somme pondérée
    weighted_score = sum((scores[k] * w.get(k, 0) / 100) for k in scores)
    weighted_score = min(100, weighted_score)
    
    # Veto Auditeur
    if not ict_approved and weighted_score > 40:
        weighted_score = 40

    min_score = getattr(config, "MIN_CONFIDENCE_SCORE", 75)
    
    # Fast Fail
    if weighted_score < min_score:
        return {"agent": self.name, "final_decision": "ATTENDRE", "global_score": round(weighted_score, 1), "should_trade": False}

    # Validation Finale LLM via appel texte
    decision_prompt = self._build_decision_prompt(all_reports, weighted_score, ict_score, ict_approved)
    raw_decision = generate_text(user_prompt=f"Verdict final", system=decision_prompt)
    
    if "VERDICT TECHNIQUE : [ACHAT]" in raw_decision.upper() or "VERDICT TECHNIQUE : [VENTE]" in raw_decision.upper():
        final_decision = "OUVRIR"
        trade_open = True
    else:
        final_decision = "ATTENDRE"
        trade_open = False
        
    return {
        "final_decision": final_decision,
        "global_score": round(weighted_score, 1),
        "should_trade": trade_open,
        "raw_decision": raw_decision
    }
```
