# Claude CLI — Mémoire de Travail (Trading Bot ICT)

> Mis à jour : 2026-03-13

---

## État Actuel du Bot

- **Mode** : Paper Trading actif, local Mac
- **Paires** : 11-14 paires (Forex, Crypto, Métaux)
- **Horizons** : M5 / H1 / H4 / D1 (4 horizons)
- **Cycle** : toutes les 5 minutes
- **LLM Validateur** : Claude Haiku (gate 60% confiance, prompt caching)

---

## Ce Qui Est Fonctionnel ✅

| Composant | Fichier | État |
|---|---|---|
| Pipeline 5 agents ICT (A1–A5) | `agents/ict/` | ✅ 107 tests OK |
| Dashboard Flask + SSE | `dashboard.py` | ✅ |
| Paper Trading | JSON interne | ✅ SL/TP, PnL flottant |
| Gate Logger | `agents/gate_logger.py` | ✅ 3 fichiers JSON par école |
| Post-Mortem Agent | `agents/post_mortem.py` | ✅ tourne à 23h00 UTC |
| OTE Tracker (State Machine) | `agents/ict/ote_tracker.py` | ✅ WAITING/TRIGGERED/INVALIDATED |
| Elliott Wave Agent | `agents/elliott/` | ✅ Observation mode, score /100 |
| VSA/Wyckoff Agent | `agents/vsa/` | ✅ Observation mode |
| Telegram Notifier | `agents/telegram_notifier.py` | ✅ Alerte ICT ≥ 70/100 |
| OB Scorer (P-A1) | `agents/ict/ob_scorer.py` | ✅ 5 critères |
| Enigma (niveaux .00/.50/.80) | `agents/ict/enigma.py` | ✅ |
| SOD Detector (P-A4) | `agents/ict/sod_detector.py` | ✅ gate timeframe-aware |
| Distance guard | dans `dashboard.py` | ✅ bloqué > 30 pips |

### KB4 Phase A — Scoring Fixes (5 règles)
| ID | Règle | État |
|---|---|---|
| P-A1 | OB Scoring graduel (`ob_scorer.py`) | ✅ Fait |
| P-A2 | FVG Scoring (fraîcheur, taille, context) | ⏳ À faire |
| P-A3 | Displacement scoring | ⏳ À faire |
| P-A4 | SOD gate timeframe-aware | ✅ Fait |
| P-A5 | HTF alignment scoring graduel | ⏳ À faire |

---

## Fixes Appliqués dans la Dernière Session (13 mars 2026)

1. **Fix `ict_raw` KeyError** — `dashboard.py` ~ligne 1526
   - Avant : accès direct `result_holder["ict_raw"]` plantait si clé absente
   - Après : vérification des clés + `.get()` avec fallback

2. **Fix NoneType Elliott** — `agents/elliott/orchestrator.py`, méthode `_build_reasons()`
   - `status`/`direction` : `or "unknown"` ajouté
   - `best.score` : conversion `int()` avec guard None
   - Filtre final : `reasons = [r for r in reasons if r is not None]`

3. **OTE Tracker complet** — `agents/ict/ote_tracker.py`
   - 6 fonctions : `save_setup`, `get_waiting_setup`, `invalidate_setup`, `tick_cycle`, `clear_triggered`, `get_all_waiting`
   - Stockage : `data/ote_setups.json` (persistant)
   - Expiration : 288 cycles M5 = 24h
   - Branché dans `entry.py` (save au lieu de jeter) et `dashboard.py` (réinjection OBs/FVGs)

4. **Fix `result_horizon`** — `dashboard.py`
   - `result_horizon` n'existait pas dans le scope de `_analyze()`
   - Remplacé par `horizon` (variable de boucle, accessible via closure)

---

## Ce Qui Reste À Faire 🔴

### Priorité 1 — Fix rapide
- **Brancher `clear_triggered()`** ✅ FAIT (13 mars 2026)
  - Inséré après `_save_paper_trade(order)` ligne 1790, conditionné à `action == "new"`
  - Bias dérivé de `order["direction"]` : BUY/ACHAT → "bullish", SELL/VENTE → "bearish"

### Priorité 2 — Validation en cours
- **Analyser `data/ote_setups.json`** + logs d'un cycle complet pour confirmer que l'OTE Tracker fonctionne correctement (session coupée avant qu'on puisse valider)

### Priorité 3 — KB4 Phase B (Signal Rules)
- **1st Presented FVG** : bonus +5 pts si FVG dans fenêtre 09:30–10:00 NY + priorité absolue
- **Sweep ERL Anti-Inducement** : gate dur avant le MSS
- **CISD** (Change in State of Delivery) : signal d'entrée 10–20 pips avant le MSS

### Priorité 4 — KB4 Phase A (Scoring restant)
- P-A2 : FVG Scoring (fraîcheur, taille, context)
- P-A3 : Displacement scoring
- P-A5 : HTF alignment scoring graduel

### Priorité 5 — KB4 Phase C (Refinements avancés)
*Gated sur 30+ trades propres avec win rate ≥ 50%*
- Suspension Block — +2 pts vs OB
- Weekly Template probabilités — +5 pts
- Magnetic Force Score — score attraction niveaux 0–100
- CISD, Grail, Unicorn, Flout

---

## Principes Architecturaux (Lignes Rouges)

1. **Ne jamais modifier la détection existante** — 107 tests = ligne rouge dure
2. **Nouvelle fonctionnalité = module séparé** importé, jamais embedded dans `structure.py` ou `dashboard.py`
3. **Le LLM valide uniquement** — il ne génère aucun signal
4. **SOD gate timeframe-aware** — défini par Fateh, implémenté
5. **ICT dit NON → pas d'override** — règle absolue du méta-orchestrateur
6. **Ne pas improviser** — toujours lire le fichier avant de proposer un fix

---

## Partenaires & Outils

- **AntiG (Antigravity)** : partenaire coding, reçoit les prompts et applique les modifications
- **TwelveData** : 4 clés API en rotation (données temps réel)
- **MT5** : source de données primaire (quand connecté)
- **VPS** : déployement prévu, pas encore fait

---

## Investigations Ouvertes

- Trades à 50/100 passés en paper trading (AUDUSD, ETHUSD) — en-dessous du seuil attendu. Pourquoi Haiku a validé à 60%+ ?
- Gate Regret Rate réel des 3 écoles (Post-Mortem pas encore analysé en profondeur)
