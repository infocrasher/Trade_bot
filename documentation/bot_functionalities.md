# Documentation des Fonctionnalités du Bot de Trading ICT

Ce document détaille l'architecture et les capacités techniques du bot de trading basé sur les concepts ICT (Inner Circle Trader). Le système est conçu de manière modulaire avec 5 agents spécialisés collaborant pour identifier des setups à haute probabilité.

## 1. Architecture Multi-Agents

Le bot repose sur une séparation stricte des responsabilités entre 5 composants (agents) :

### 🤖 Agent 1 : Structure & Liquidity (`agent_structure.py`)
**Rôle :** Identifie le "Market Framework" (Cadre de Marché).
- **Structure :** Détection automatique des **BOS** (Break of Structure) et **CHoCH** (Change of Character).
- **Zones d'Intérêt :** Identification des **Order Blocks (OB)** et des **Fair Value Gaps (FVG)**.
- **Liquidité :** Repérage des **Liquidity Sweeps** (Buyside/Sellside) et des niveaux de liquidité résiduelle (**EQH/EQL**).
- **Multi-TF :** Analyse de l'alignement entre le High Timeframe (HTF) et le Low Timeframe (LTF).

### 🤖 Agent 2 : Time & Sessions (`agent_time_session.py`)
**Rôle :** Filtre temporel (Quand trader).
- **Killzones :** Gestion précise des sessions Asian, London, NY AM et NY PM.
- **Macros :** Détection des fenêtres "Macro" algorithmiques de 20 minutes (ex: 09:50-10:10 NY).
- **Midnight Open :** Calcul du prix d'ouverture de minuit pour définir le **Premium/Discount** journalier.
- **Profils de Trading :** Identification des phases **PO3 (AMD)** (Accumulation, Manipulation, Distribution) et des profils spécifiques comme le **Seek & Destroy** (Lundi matin).

### 🤖 Agent 3 : Entry Precision & DOL (`agent_entry.py`)
**Rôle :** Précision de l'entrée et cibles de sortie.
- **Draw on Liquidity (DOL) :** Algorithme de tri des cibles potentielles (PDH/PDL, PWH/PWL, EQH/EQL) par proximité et pertinence.
- **Premium/Discount :** Vérification mathématique que les achats se font en zone Discount et les ventes en zone Premium.
- **Standard Deviation (SD) :** Calcul des projections de déviation standard pour définir les Take Profits (TP1, TP2, TP3).

### 🤖 Agent 4 : Macro Bias & Sentiment (`agent_macro.py`)
**Rôle :** Analyse du narratif global et des corrélations.
- **COT Data :** Analyse du positionnement des gros institutionnels (Commitment of Traders).
- **SMT Divergence :** Détection des divergences "Smart Money Technique" entre paires corrélées (ex: EURUSD vs GBPUSD vs DXY).
- **Seasonal Bias :** Prise en compte des tendances saisonnières par trimestre (Q1, Q2, Q3, Q4).
- **News Filter :** Protection contre la volatilité des annonces économiques majeures.
- **IPDA Ranges :** Identification des ranges de données IPDA (20, 40, 60 jours).

### 🤖 Agent 5 : Orchestrator (`agent_orchestrator.py`)
**Rôle :** Le "Cerveau" final.
- **Synthèse :** Agrège les signaux des 4 autres agents.
- **Confidence Scoring :** Calcule un score de confiance global (0-100%). Un bonus est accordé si une Macro est active.
- **Verdict :** Émet la décision finale (`EXECUTE_BUY`, `EXECUTE_SELL`, `NO_TRADE`).
- **Filtrage :** Bloque les trades en cas de conflit HTF ou si le prix est dans la mauvaise zone Premium/Discount.

---

## 2. Infrastructure de Données & Exécution

### 🔌 MT5 Connector (`data/mt5_connector.py`)
Gère la communication bidirectionnelle avec le terminal MetaTrader 5 :
- Récupération des prix en temps réel.
- Historique des bougies (Backtest & Analyse).
- Capture d'images de graphiques pour l'analyse visuelle (optionnelle).

### 🛡️ Trade Manager (`data/trade_manager.py`)
Responsable de la sécurité du compte :
- **Position Sizing :** Calcul automatique des lots en fonction du risque par trade (ex: 1%).
- **Circuit Breaker :** Arrêt automatique en cas de perte journalière maximale ou de séries de pertes consécutives.
- **Suivi des Performances :** Journalisation des résultats.

---

## 3. Validation Technique (Tests)

Le système dispose d'une suite de tests complète (`test_agents/`) validant **plus de 125 points de contrôle**, incluant :
- **30 Tests de Phase 1 :** Validant l'intégration des concepts avancés (MSS, Macros, DOL, SD, IPDA).
- **Tests Unitaires par Agent :** Pour garantir la fiabilité de chaque module indépendamment.

---
*Date du rapport : 26 Février 2026*
