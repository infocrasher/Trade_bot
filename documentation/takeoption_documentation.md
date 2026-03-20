# TakeOption Bot — Documentation Complète
## Bot de Trading Algorithmique ICT Multi-Profils

> **Version** : 2.4.1 — Mars 2026  
> **Auteurs** : Sofiane (Lead Dev) & Fateh (Expert ICT/Trading)  
> **Repo** : github.com/tchedler/newbot  
> **Stack** : Python 3.13 · Flask · TwelveData API · Claude Haiku · Gemini Flash

---

## 📋 Table des Matières

1. [C'est quoi TakeOption ?](#cest-quoi-takeoption)
2. [Philosophie & Principes](#philosophie--principes)
3. [Architecture Générale](#architecture-générale)
4. [Les 5 Agents ICT](#les-5-agents-ict)
5. [Les Profils de Trading](#les-profils-de-trading)
6. [Le Pipeline de Décision](#le-pipeline-de-décision)
7. [Infrastructure Technique](#infrastructure-technique)
8. [Dashboard & Interface](#dashboard--interface)
9. [Système de Tests](#système-de-tests)
10. [Roadmap & État Actuel](#roadmap--état-actuel)
11. [Glossaire ICT](#glossaire-ict)

---

## C'est quoi TakeOption ?

TakeOption est un **bot de trading algorithmique** qui analyse les marchés financiers en temps réel et génère des signaux d'entrée/sortie basés sur la méthodologie **ICT (Inner Circle Trader)**.

### En termes simples

Imagine un analyste financier expert qui :
- Surveille **14 paires** de devises, métaux et cryptos **24h/24**
- Analyse le prix toutes les **5 minutes**
- Applique des **règles mathématiques précises** pour détecter des opportunités
- Décide en **moins de 2 secondes** si on trade ou non
- **Ne se trompe jamais de calcul** (contrairement à un humain)

### Ce que le bot fait concrètement

```
Chaque 5 minutes :
  ├── Télécharge les données de marché (TwelveData)
  ├── Analyse la structure du prix sur 4 timeframes (M5/H1/H4/D1)
  ├── Détecte les zones institutionnelles (Order Blocks, FVG, OTE)
  ├── Calcule un score de confluence sur 100 points
  ├── Si score ≥ 65 → valide avec IA (Claude Haiku)
  └── Si approuvé → crée un paper trade avec SL/TP automatiques
```

### Les marchés analysés

| Catégorie | Paires |
|-----------|--------|
| **Forex Majeures** | EURUSD, GBPUSD, AUDUSD, NZDUSD, USDCAD, USDCHF, USDJPY |
| **Forex Croisées** | EURGBP, EURJPY, GBPJPY, AUDJPY |
| **Métaux** | XAUUSD (Or) |
| **Crypto** | BTCUSD, ETHUSD |

---

## Philosophie & Principes

### Règle d'Or : L'IA valide, elle ne décide pas

```
FAUX  ❌ : L'IA détecte un setup → elle trade
VRAI  ✅ : Les maths détectent un setup → l'IA valide → on trade
```

Les agents A1-A5 sont **100% mathématiques et déterministes**. Claude Haiku intervient uniquement comme validateur final, jamais comme détecteur.

### Les 5 Principes Inviolables

1. **Tests sacrés** — 258 tests unitaires ne régressent jamais
2. **Séparation stricte** — chaque nouvelle règle = nouveau fichier
3. **IA = validateur uniquement** — jamais décideur
4. **MSS + FVG jamais désactivés simultanément** dans Pure PA
5. **Clés API dans .env uniquement** — jamais dans le code

### Pourquoi ICT ?

ICT (Inner Circle Trader) est une méthodologie de trading institutionnel qui explique comment les grandes banques et hedge funds manipulent le prix pour accumuler des positions. En comprenant leur logique, on peut anticiper leurs mouvements.

Concepts clés ICT utilisés :
- **Order Blocks (OB)** — zones d'accumulation institutionnelle
- **Fair Value Gaps (FVG)** — déséquilibres de prix à combler
- **OTE (Optimal Trade Entry)** — zone d'entrée optimale 62-79% Fibonacci
- **Killzones** — heures où les institutions sont les plus actives
- **Market Structure Shift (MSS)** — changement de tendance confirmé
- **Liquidity Sweeps** — purge des stops retail avant le vrai move

---

## Architecture Générale

```
┌─────────────────────────────────────────────────────────────┐
│                    TakeOption Bot                           │
│                                                             │
│  ┌──────────────┐    ┌──────────────────────────────────┐  │
│  │  TwelveData  │───▶│         dashboard.py             │  │
│  │  9 clés API  │    │   Flask Server + Trading Loop    │  │
│  │  7020 req/j  │    └──────────────┬───────────────────┘  │
│  └──────────────┘                   │                       │
│                          ┌──────────▼──────────┐           │
│                          │   14 PAIRES × M5    │           │
│                          │   Cycle toutes 5min │           │
│                          └──────────┬──────────┘           │
│                                     │                       │
│              ┌──────────────────────▼───────────────────┐  │
│              │           PIPELINE MULTI-PROFILS          │  │
│              │                                           │  │
│              │  ┌────────────┐  ┌────────────────────┐  │  │
│              │  │ ICT Strict │  │    Pure PA         │  │  │
│              │  │  55% poids │  │    (MSS+FVG)       │  │  │
│              │  │  A1→A5     │  │    30 min TTL      │  │  │
│              │  └─────┬──────┘  └────────┬───────────┘  │  │
│              │        │                  │               │  │
│              │  ┌─────▼──────┐  ┌────────▼───────────┐  │  │
│              │  │  Elliott   │  │       VSA          │  │  │
│              │  │  30% poids │  │    15% poids       │  │  │
│              │  │  24h TTL   │  │    Gemini Vision   │  │  │
│              │  └─────┬──────┘  └────────┬───────────┘  │  │
│              │        └──────────┬────────┘               │  │
│              │                   │                         │  │
│              │  ┌────────────────▼──────────────────────┐ │  │
│              │  │      MetaConvergenceEngine            │ │  │
│              │  │   Score pondéré + résolution conflits │ │  │
│              │  └────────────────┬──────────────────────┘ │  │
│              └───────────────────┼───────────────────────┘  │
│                                  │                           │
│                    ┌─────────────▼──────────────┐           │
│                    │    LLM Validator            │           │
│                    │    Claude Haiku             │           │
│                    │    (si score ≥ 65/100)      │           │
│                    └─────────────┬──────────────┘           │
│                                  │                           │
│                    ┌─────────────▼──────────────┐           │
│                    │     Paper Trade JSON        │           │
│                    │  SL/TP/Profile/Gates/Score  │           │
│                    └─────────────┬──────────────┘           │
│                                  │                           │
│          ┌───────────────────────▼─────────────────────┐    │
│          │  Dashboard Flask · Telegram · Gate Logger   │    │
│          └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## Les 5 Agents ICT

Le cœur du bot est constitué de 5 agents qui s'exécutent en séquence. Chaque agent est une barrière — si l'un dit NON, on s'arrête là.

### A1 — Structure Agent (`agents/ict/structure.py`)

**Rôle** : Comprendre le contexte du marché sur plusieurs timeframes

**Ce qu'il fait** :
- Détecte les **Swing Highs/Lows** (points pivots du marché)
- Identifie les **BOS** (Break of Structure) et **CHoCH** (Change of Character)
- Repère les **Order Blocks** — zones où les institutions ont tradé
- Identifie les **FVG** (Fair Value Gaps) — espaces de prix sans échanges
- Analyse les **Liquidity Sweeps** — purges de liquidité retail
- Détermine le **biais directionnel** (bullish / bearish / conflicting)

**Entrée** : DataFrame OHLCV sur D1, H4, H1  
**Sortie** : `{bias, swings[], order_blocks[], fvg[], bos_choch[], sweeps[]}`

**Scoring Phase B intégré** :
- P-B1 : Premier FVG post-09h29 NY → +5 pts
- P-B2 : CISD (changement de livraison) → +5 pts
- P-B3 : Flout Pattern (faux breakout) → +5 pts
- P-B4 : Suspension Block → +2 pts
- P-B5 : Weekly Template → ±5 pts
- P-B6 : Magnetic Force Score → +3 à +5 pts

---

### A2 — Time Session Agent (`agents/ict/time_session.py`)

**Rôle** : S'assurer qu'on trade aux bonnes heures

**Ce qu'il fait** :
- Vérifie si on est dans une **Killzone active**
- Détecte les fenêtres **Silver Bullet** (précision maximale)
- Analyse le **Power of 3** (Accumulation/Manipulation/Distribution)
- Filtre les **jours de faible liquidité** (lundi/vendredi)
- Détecte le **Judas Swing** (faux move initial de session)

**Killzones actives** (heure Alger, UTC+1) :

| Killzone | Horaire Alger | Équivalent NY |
|----------|---------------|---------------|
| Asia | 00h00 - 04h00 | 19h-23h |
| London | 03h00 - 06h00 | 02h-05h |
| NY AM | 12h00 - 15h00 | 07h-10h |
| NY PM | 18h30 - 21h00 | 13h30-16h |

**Sortie** : `{can_trade: bool, killzone, trade_quality, po3_phase}`

---

### A3 — Entry Agent (`agents/ict/entry.py`)

**Rôle** : Trouver le point d'entrée précis

**Ce qu'il fait** :
- Calcule la **zone OTE** (Optimal Trade Entry) : 62%-79% du dernier swing
- Cherche les **confluences** OB + FVG dans la zone OTE
- Vérifie la **bougie de confirmation** d'entrée
- Calcule le **SL** (Stop Loss) sous/au-dessus du swing
- Calcule les **TP** (Take Profits) sur les niveaux Fibonacci
- Vérifie que le **R:R ≥ 1.5**

**Zone OTE expliquée** :
```
Swing Low  ──────────────────────────────── Swing High
  1.0800                                      1.1000
              │←──── Zone OTE ────→│
           1.0876 (62%)          1.0924 (79%)
           
Si le prix retourne dans cette zone + confluence OB/FVG → ENTRÉE
```

**Buffer ATR** : ±0.5× ATR(14) autour de la zone pour tolérance institutionnelle  
**Sortie** : `{signal: BUY/SELL/NO_TRADE, entry_price, stop_loss, tp1, tp2, tp3, rr_ratio}`

---

### A4 — Macro Agent (`agents/ict/macro.py`)

**Rôle** : Contexte macroéconomique

**Ce qu'il fait** :
- Analyse la **corrélation DXY** avec les paires Forex
- Vérifie le **T-20 Premium** (malus si on est dans une zone premium HTF) : -20 pts
- Filtre les **news HIGH** (blocage 15 min avant/après)
- Analyse les données **COT** (Commitment of Traders)

**Sortie** : `{can_trade: bool, macro_bias, t20_active, news_danger}`

---

### A5 — Orchestrateur ICT (`agents/ict/orchestrator.py`)

**Rôle** : Fusion et scoring final ICT

**Ce qu'il fait** :
- Fusionne les résultats A1+A2+A3+A4
- Applique les **gates KB4** (critères d'acceptation/rejet)
- Calcule le **score de confiance** final (0.0 à 1.0 → 0 à 100 pts)
- Applique les **bonus Phase B** (P-B1 à P-B6)
- Logue les blocages dans le **Gate Logger**

**Gates KB4 actifs** :

| Gate | Valeur | Description |
|------|--------|-------------|
| KS4 | Spread ≤ 3 pips | Coût de transaction maximum |
| KS8 | CBDR non explosif | Pas de mouvement pré-macro |
| R:R | ≥ 1.5 | Rapport Gain/Risque minimum |
| OB Score | ≥ 60/100 | Qualité de l'Order Block |
| SL Minimum | ≥ 8 pips | Stop Loss pas trop serré |
| T-20 Malus | -20 pts | Zone premium/discount HTF |
| SOD Gate | 0%/50%/100% sizing | État de livraison de session |
| HTF Alignment | D1+H4+H1 | Alignement multi-timeframes |

**Sortie** : `{global_confidence: float, reasons[], warnings[], gates_passed[]}`

---

## Les Profils de Trading

TakeOption utilise 4 profils simultanés qui s'exécutent en parallèle sur les mêmes données.

### Profil 1 : ICT Strict (55% du poids méta)

```
Pipeline complet : A1 → A2 → A3 → A4 → A5 → LLM
TTL : 3 heures
Seuil paper : 65/100
Spécialité : Setups institutionnels haute précision
```

C'est le profil le plus sélectif. Il suit rigoureusement la méthodologie ICT complète avec tous les gates actifs. Génère peu de trades mais de haute qualité.

---

### Profil 2 : Elliott Wave (30% du poids méta)

```
Fichiers : agents/elliott/wave_counter.py, scorer.py, orchestrator.py
TTL : 24 heures
Seuil : 65/100
Spécialité : Détection des vagues de Wyckoff/Elliott
```

Analyse la structure des vagues 1-2-3-4-5 et A-B-C. Un signal Elliott est généré quand une vague 3 ou 5 est détectée avec confirmation Fibonacci.

**Règles absolues Elliott** :
- La vague 2 ne dépasse jamais l'origine de la vague 1
- La vague 3 n'est jamais la plus courte
- La vague 4 ne pénètre pas dans le territoire de la vague 1

---

### Profil 3 : VSA/Wyckoff (15% du poids méta)

```
Fichiers : agents/vsa/ (5 fichiers)
TTL : 8 heures
Seuil paper : 55/100 (live : 65/100)
Scoring : Algo 50pts + Gemini Flash Vision 50pts
```

VSA (Volume Spread Analysis) analyse la relation volume/spread pour détecter l'accumulation et la distribution institutionnelle.

**Phases Wyckoff** :
- **Accumulation** : Les institutions achètent discrètement
- **Markup** : Tendance haussière
- **Distribution** : Les institutions vendent discrètement
- **Markdown** : Tendance baissière

**Gemini Flash Vision** est utilisé pour scorer visuellement le graphique annoté. Guard : si score algo = 0 → pas d'appel Gemini.

---

### Profil 4 : Pure Price Action

```
Fichier : agents/pure_pa/orchestrator.py
TTL : 30 minutes
Seuil : R:R ≥ 1.0 (guard ATR)
Spécialité : Entrées rapides MSS+FVG sur crypto/forex
```

Plus simple et plus rapide que ICT Strict. Détecte un **MSS** (Market Structure Shift) suivi d'un **FVG frais** dans la direction du MSS. Exécute rapidement avec un TTL court de 30 minutes.

**Guard prix aberrant** :
- Forex : écart ≤ 2% vs last_close M5
- Métaux (XAU) : écart ≤ 3%
- Crypto (BTC/ETH) : écart ≤ 5%

---

### MetaConvergenceEngine

```
Fichier : agents/meta_convergence.py
```

Le moteur de méta-convergence fusionne les 4 profils en une décision finale.

**Pondérations** :
```
ICT Strict  : 55%
Elliott     : 30%
VSA         : 15%
Pure PA     : indépendant (trade seul si signal fort)
```

**Résolution des conflits** :
- HTF bat LTF en cas de conflit directionnel
- Même TF en conflit → annulation mutuelle
- SL convergent : le plus conservateur (plus éloigné) gagne

---

## Le Pipeline de Décision

```
Données TwelveData (9 clés, 7020 req/jour)
              │
              ▼
    ┌─────────────────┐
    │  Scheduler KZ   │  ← Analyse seulement pendant les Killzones
    │  5 min en KZ    │    ou 1h/heure hors KZ (crypto uniquement)
    │  60 min hors KZ │
    └────────┬────────┘
             │
    ┌────────▼────────────────────────────────────────┐
    │              Pour chaque paire                  │
    │                                                 │
    │  A2 : Killzone active ? ──── NON ──▶ SKIP       │
    │                │                                │
    │                OUI                              │
    │                │                                │
    │  A1 : Structure HTF bullish/bearish/conflicting │
    │                │                                │
    │  A3 : Prix dans OTE 62-79% + confluence OB/FVG  │
    │       ──── NON ──▶ Sauvegarder en WAITING       │
    │                │   (OTE State Machine 24h max)  │
    │                OUI                              │
    │                │                                │
    │  A4 : Macro OK, pas de news HIGH, T-20 check    │
    │                │                                │
    │  A5 : Score KB4 + Bonus Phase B                 │
    │       ──── < 65 ──▶ RESTER_DEHORS               │
    │                │                                │
    │  LLM : Claude Haiku valide le contexte          │
    │        ──── rejected ──▶ RESTER_DEHORS          │
    │                │                                │
    │        PAPER TRADE CRÉÉ ✅                       │
    └─────────────────────────────────────────────────┘
             │
    ┌────────▼──────────────────────────────────────┐
    │         Paper Trade Monitor V2               │
    │  Check SL/TP toutes les minutes              │
    │  Ferme automatiquement quand atteint         │
    │  Expire après TTL (30min/3h/8h/24h)          │
    └───────────────────────────────────────────────┘
```

### OTE State Machine

Quand A3 ne trouve pas de confluence mais que le biais est bon, le setup n'est pas jeté — il est **sauvegardé en WAITING** :

```
Nouveau cycle M5
      │
      ▼
 Setup existe          ┌──────────────┐
 en WAITING ? ──OUI──▶│  Récupérer   │──▶ Réinjecter dans A3
      │                │  OB/FVG zone │
      NON               └──────────────┘
      │
      ▼
 Créer nouveau WAITING
      │
      ▼
 Timeout 288 cycles    ──▶ INVALIDATED (24h max)
 ou Biais changé
```

Fichier de persistance : `data/ote_setups.json`

---

## Infrastructure Technique

### Stack Technologique

| Composant | Technologie | Rôle |
|-----------|-------------|------|
| Backend | Python 3.13 + Flask | Serveur web + logique trading |
| Données marché | TwelveData API (9 clés) | OHLCV temps réel |
| LLM Validateur | Claude Haiku (Anthropic) | Validation finale signaux |
| Vision IA | Gemini Flash (Google) | Scoring visuel VSA |
| Notifications | Telegram Bot | Alertes trades en temps réel |
| Frontend | HTML/CSS/JS + Chart.js | Dashboard temps réel |
| Stockage | JSON flat files | Paper trades, logs, settings |
| Tests | Python unittest | 258 tests unitaires |

### Fichiers Principaux

```
Trading_Bot_Project/
├── dashboard.py              # Point d'entrée Flask + loop trading
├── config.py                 # Config globale (paires, KZ, 9 clés API)
├── .env                      # Clés API (jamais dans Git)
│
├── agents/
│   ├── ict/
│   │   ├── structure.py      # A1 : Analyse structure HTF
│   │   ├── ob_scorer.py      # Helper A1 : Score OB 5 critères
│   │   ├── time_session.py   # A2 : Killzones, Silver Bullet, PO3
│   │   ├── entry.py          # A3 : OTE 62-79%, confluences, R:R
│   │   ├── macro.py          # A4 : DXY, COT, T-20, News
│   │   ├── enigma.py         # Helper : Niveaux .00/.20/.50/.80
│   │   ├── sod_detector.py   # Helper : State of Delivery 5 états
│   │   ├── ote_tracker.py    # State Machine OTE (WAITING/TRIGGERED)
│   │   └── orchestrator.py   # A5 : Fusion + scoring KB4 + Phase B
│   │
│   ├── elliott/
│   │   ├── wave_counter.py   # Compteur vagues 1-5, A-B-C
│   │   ├── scorer.py         # Score Fibonacci, Alternance, Momentum
│   │   └── orchestrator.py   # Validation et filtrage Elliott
│   │
│   ├── vsa/
│   │   ├── volume_analyzer.py
│   │   ├── scorer.py         # Score algo 50pts
│   │   ├── gemini_analyzer.py# Score visuel Gemini 50pts
│   │   └── orchestrator.py
│   │
│   ├── pure_pa/
│   │   └── orchestrator.py   # MSS + FVG + R:R + guard prix
│   │
│   ├── meta_convergence.py   # MetaConvergenceEngine
│   ├── gate_logger.py        # Logs refus par profil → JSON
│   ├── post_mortem.py        # Gate Regret Rate quotidien
│   ├── telegram_notifier.py  # Alertes Telegram
│   └── agent_llm_validator.py# Claude Haiku avec Prompt Caching
│
├── data/
│   ├── gate_logs/            # Blocages par date et profil
│   ├── ote_setups.json       # Setups WAITING en cours
│   └── profiles/settings.json# Réglages dashboard persistants
│
├── paper_trading/
│   └── paper_YYYY-MM-DD.json # Trades du jour
│
├── static/css/ + static/js/  # Dashboard CSS/JS
├── templates/                # 6 templates HTML Flask
└── tests/
    └── run_all_tests.sh      # Script dynamique 258 tests
```

### TwelveData — Gestion des Clés

```
9 clés × 780 req/jour = 7020 requêtes/jour total

Rotation intelligente :
  ├── Limite journalière dépassée → rotation vers clé suivante
  ├── Limite par minute (8 req/min) → rotation immédiate + cooldown 60s
  └── Toutes les clés épuisées → sleep(60) + retry automatique
```

### Circuit Breaker

Protection contre les pertes excessives :
- **Max 5 trades/jour/paire**
- **Arrêt à -3% capital/jour**
- **Cooldown 4h après 3 pertes consécutives**

---

## Dashboard & Interface

Le dashboard Flask temps réel accessible sur `http://localhost:5000` comprend 5 pages :

### Page 1 : Dashboard Principal
- **Trades actifs** : table avec PnL en temps réel, SL/TP, profil
- **Signaux récents** : historique avec badge profil + décision IA
- **KPI cards** : trades ouverts, PnL du jour, profils actifs, taux de réussite
- **Panneau slide-in** : au clic sur un trade → gates actifs, scores, narrative, décision LLM

### Page 2 : Performance
- Métriques par profil : Win Rate, Expectancy, Profit Factor, Max Drawdown, SQN
- Courbe de Capital par profil (Chart.js)
- Historique complet avec Décision LLM

### Page 3 : Réglages
- Tous les gates en toggle persistant (settings.json)
- Scoring (seuils full/half/telegram)
- ICT Gates (R:R, OB Score, Spread, SL, T-20, ENIGMA, SOD, HTF)
- Timing (Killzones, Seek & Destroy Monday)
- Sizing (Risk%, SOD Sizing)
- Pure PA (MSS Required, FVG Required + guard anti-désactivation simultanée)

### Page 4 : Post-Mortem
- **Gate Regret Rate** par profil : % des setups bloqués qui auraient gagné
- Barres colorées : vert < 20%, orange 20-40%, rouge > 40%
- Table des setups bloqués avec raison, résultat réel, regret Oui/Non
- Sélecteur de date — chargement automatique sur aujourd'hui

### Page 5 : Logs
- Logs temps réel avec polling 2 secondes
- Couleurs par niveau : DEBUG gris, INFO blanc, WARNING orange, ERROR rouge
- Filtres par niveau et par paire
- Auto-scroll avec toggle

### Boutons de Contrôle
- **Démarrer** (vert) — visible si arrêté
- **Pause** (orange) — visible si en cours
- **Arrêter** (rouge) — avec confirmation

---

## Système de Tests

### Philosophie des Tests

```
Règle absolue : 258 tests passent toujours.
Si un test casse → rollback immédiat avant de continuer.
```

### Couverture par Module

| Fichier de test | Tests | Module couvert |
|-----------------|-------|----------------|
| test_agents/test_agent3.py | 26 | A3 Entry (OTE, confluences, R:R) |
| test_agents/test_agent4.py | 34 | A4 Macro (COT, DXY, News) |
| test_agents/test_agent5.py | 40 | A5 Orchestrateur + Safety |
| test_agents/test_phase1.py | 96 | Pipeline complet Phase A |
| test_agents/test_pure_pa.py | 8 | Pure PA + guard prix |
| test_agents/test_units.py | 9 | Utilitaires |
| test_enigma.py | 15 | Niveaux ENIGMA |
| test_ks4_ks8.py | 7 | Gates KS4/KS8 |
| test_e7.py | 12 | Bonus Phase B (P-B1 à P-B6) |
| test_ob_scorer.py | 1 | OB Scorer 5 critères |
| test_sod_detector.py | 1 | SOD 5 états |
| agents/elliott/test_elliott.py | 1 | Elliott Wave |
| test_vsa_script.py | 1 | VSA Pipeline |

**Script de lancement** :
```bash
cd Trading_Bot_Project
bash tests/run_all_tests.sh
# Attendu : 258 PASS / 0 FAIL / Exit code 0
```

---

## Roadmap & État Actuel

### État au 18 Mars 2026

```
Phase A  ✅  KB4 Scoring (OB, ENIGMA, SOD, KS4/KS8, T-20)
Phase P  ✅  Multi-profils + Pure PA + Dashboard V0 + 258 tests
Phase B  🟡  P-B1→P-B6 codés, en attente validation live ICT
Phase F  ⏳  Modules Fateh (BehaviourShield, LiquidityDetector, NewsManager)
Phase C  ⏳  KB4 Finesse (Grail, Unicorn, Terminus) — après 30 trades
Phase I  ⏳  IA Interprète (Gemini Vision + Claude enrichi)
Phase M  ⏳  Méta-orchestrateur adaptatif — après 30 trades
Phase D  🔮  Profils avancés (Trend/MR) — futur conditionnel
```

### Conditions de Passage

| De → Vers | Condition |
|-----------|-----------|
| Phase B → Phase F | 10 trades avec Phase B actif |
| Phase F → Phase C | WR ≥ 40% sur 15 trades |
| Phase C → Phase I | 30 trades sur ≥ 2 profils |
| Phase I → Phase M | Expectancy positive sur ≥ 2 profils |
| Phase M → Phase D | WR ≥ 50% sur 50 trades |

### Phase F — Apports de Fateh (Sentinel KB5)

| Module | Priorité | Contenu |
|--------|----------|---------|
| P-F1 BehaviourShield | 🔴 CRITIQUE | 8 filtres anti-manipulation |
| P-F2 LiquidityDetector | 🔴 CRITIQUE | PDH/PDL/PWH/DOL/Sweeps complets |
| P-F3 NewsManager | 🔴 CRITIQUE | API Finnhub temps réel |
| P-F4 AMDDetector | 🟠 IMPORTANT | PO3 structurel (remplace horaire fixe) |
| P-F5 PADetector | 🟠 IMPORTANT | Chiffres ronds, trendlines, engulfing |
| P-F6 Encyclopédies v5 | 🟠 IMPORTANT | LLM mis à jour |
| P-F7 Pyramide MN+W1 | 🟡 MOYEN | Timeframes Monthly et Weekly |

---

## Glossaire ICT

| Terme | Définition |
|-------|------------|
| **OB (Order Block)** | Dernière bougie opposée avant un fort mouvement directionnel |
| **FVG (Fair Value Gap)** | Espace de prix entre 3 bougies où aucun échange n'a eu lieu |
| **OTE (Optimal Trade Entry)** | Zone d'entrée optimale entre 62% et 79% de retracement Fibonacci |
| **MSS (Market Structure Shift)** | Cassure du dernier point pivot — changement de tendance confirmé |
| **BOS (Break of Structure)** | Cassure dans le sens de la tendance actuelle |
| **CHoCH (Change of Character)** | Cassure contre la tendance — signal de retournement |
| **Killzone** | Fenêtre horaire où les institutions sont les plus actives |
| **Silver Bullet** | Fenêtre de 1h de haute précision (ex: 10h-11h NY) |
| **PD Array** | Premium/Discount Array — niveaux institutionnels de référence |
| **SOD** | State of Delivery — état de livraison du prix en session |
| **T-20** | Zone Premium à éviter (last 20% avant target HTF) |
| **DOL** | Draw on Liquidity — prochaine cible institutionnelle |
| **PDH/PDL** | Previous Day High/Low — niveaux de référence journaliers |
| **PWH/PWL** | Previous Week High/Low — niveaux de référence hebdomadaires |
| **CISD** | Change In State of Delivery — signal de retournement de livraison |
| **Flout Pattern** | Faux breakout institutionnel avec réintégration immédiate |
| **HTF/LTF** | Higher TimeFrame / Lower TimeFrame |
| **SQN** | System Quality Number (Van Tharp) — métrique de qualité système |
| **Gate Regret Rate** | % des setups bloqués qui auraient été gagnants |

---

*TakeOption Bot — Documentation v2.4.1 — Mars 2026*  
*Sofiane & Fateh — github.com/tchedler/newbot*
