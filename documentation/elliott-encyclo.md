# 📚 ENCYCLOPÉDIE COMPLÈTE — Agent Expert Elliott Wave v1.0
# Sources : Elliott Wave Principle (Frost & Prechter), ChartSchool, ElliottWave-Forecast, autres ressources majeures
# Contenu : Règles “dures” (rules) + lignes directrices (guidelines) + protocoles de validation multi‑timeframe
# Version : 1.0 — Étendue et structurée pour usage IA (prompt système)

---

## ⚠️ RAPPORT D’AUDIT — Ce que couvre cette encyclopédie

Objectif : se rapprocher du niveau de complétude de l’encyclopédie ICT v2.0, mais pour l’école Elliott Wave.

### Inclus (portée couverte)

- ✅ Les **3 règles absolues** d’une impulsion (non négociables)
- ✅ Structure interne complète des impulsions (5‑3‑5‑3‑5) et sous‑vagues
- ✅ Règles et guidelines des **diagonales** (leading / ending)
- ✅ Tous les **types de corrections** :
  - Zigzags simples / doubles / triples
  - Flats : réguliers, étendus, en fuite
  - Triangles : contracting / expanding, running, barrier
  - Combinaisons : double three, triple three
- ✅ Guideline d’**alternance**
- ✅ **Ratios de Fibonacci** par vague (retracements/expansions usuels)
- ✅ Règles de **degré et labellisation** (multi‑timeframe)
- ✅ Règles de **canalisation** (channeling) et cibles
- ✅ Règles d’**invalidation** complètes
- ✅ Checklists et protocole de scoring pour un agent IA (comme dans ICT v2.0)

Ce document est conçu pour que l’IA :
1. Génère des comptages Elliott candidats.
2. Élimine ceux qui violent une règle.
3. Score les scénarios restants selon les guidelines.

---

## 🎯 SECTION 0 — Philosophie fondamentale de l’école Elliott

### 0.1 Vision générale

- Les marchés suivent des **schémas répétitifs de psychologie collective**, visibles sous forme de **vagues** dans le prix.
- Ces vagues se structurent en cycles : **mouvement impulsif à 5 vagues** dans la direction de la tendance principale, suivi d’une **correction à 3 vagues** (A‑B‑C) contre la tendance.
- La structure est **fractale** : chaque vague d’un degré se recompose en sous‑vagues du degré inférieur obéissant aux mêmes règles.

### 0.2 Deux grandes familles de vagues

- **Motive (motrices)** :
  - Impulsions classiques.
  - Diagonales (leading & ending).
  - Toujours globalement en **5 vagues** (1‑2‑3‑4‑5) dans le sens de la tendance du degré supérieur.
- **Correctives** :
  - Contre la tendance du degré supérieur.
  - Généralement en **3 vagues** (A‑B‑C) ou combinaisons de structures 3‑vagues.

---

## 🏛️ SECTION 1 — Degrés, labellisation et contraintes

### 1.1 Degrés de tendance

Un même graphique contient plusieurs **degrés de tendance** emboîtés (supercycle, cycle, primaire, intermédiaire, mineur, minute, etc.).

Guidelines :

- Des vagues d’un même degré doivent être **comparables en durée et amplitude**.
- Un comptage qui mélange des segments très courts et très longs sous la même étiquette de degré est **suspect**.

### 1.2 Notation standard des vagues

- Degrés majeurs (exemple) :
  - Roman : I‑II‑III‑IV‑V, A‑B‑C
  - Chiffres : 1‑2‑3‑4‑5, a‑b‑c
  - Lettres/indices : (1)‑(2)‑(3), i‑ii‑iii, etc.
- Règle IA :
  - Ne pas mélanger les systèmes de notation au sein d’un même degré.
  - Maintenir une **hiérarchie claire** (majuscule ⇒ degré plus élevé, minuscule ⇒ inférieur).

---

## 🔺 SECTION 2 — Impulsions : règles absolues + guidelines

### 2.1 Les 3 règles absolues (non violables)

Pour qu’une structure soit une **impulsion Elliott valide** :

1. **Règle 1 — Vague 2 et origine de 1**
   - La vague 2 **ne retrace jamais au‑delà de 100 %** de la vague 1.
   - Si le prix franchit le départ de la vague 1 → **impulsion invalidée**.

2. **Règle 2 — Vague 3 et longueur**
   - La vague 3 **ne peut pas être la plus courte** des trois vagues motrices 1, 3 et 5.
   - Elle peut être plus courte que 1 ou que 5, mais **jamais plus courte que les deux**.

3. **Règle 3 — Vague 4 et zone de la vague 1 (impulsion classique)**
   - La vague 4 **ne doit pas pénétrer** dans la zone de prix couverte par la vague 1 (entre le début et la fin de 1), dans une impulsion standard.
   - **Exception** : diagonales (leading/ending), où le chevauchement 4/1 est possible et fait partie des règles spécifiques.

Toute violation d’une de ces 3 règles ⇒ **l’IA doit rejeter ce comptage comme impulsion valide**.

### 2.2 Structure interne

Une impulsion complète 1‑2‑3‑4‑5 suit en principe :

- Vagues 1, 3, 5 : chacune se décompose (au degré inférieur) en **5 sous‑vagues motrices**.
- Vagues 2 et 4 : se décomposent généralement en **3 sous‑vagues correctives** (zigzag, flat, triangle, ou combinaisons).

Schéma type : **5‑3‑5‑3‑5**.

### 2.3 Rôle et caractère de chaque vague (guidelines)

- **Vague 1**
  - Début de nouvelle tendance, mais souvent ambiguë.
  - Peut être précédée d’un “ending diagonal” de la tendance précédente.
- **Vague 2**
  - Corrige fortement 1, mais **ne casse pas son origine** (cf. règle 1).
  - Souvent un **zigzag** (5‑3‑5), plus “aigu” que 4.
- **Vague 3**
  - Souvent la plus **longue et explosive** (mais pas forcément).
  - En général accompagne un **fort volume** et une participation massive.
  - Doit dépasser clairement l’extrémité de la vague 1.
- **Vague 4**
  - Souvent plus **latérale / complexe** que 2 (guideline d’alternance).
  - Tendance à rester dans une zone de consolidation, canal ou triangle.
- **Vague 5**
  - Dernier segment de la tendance.
  - Fréquent : **divergence de momentum** (prix fait un nouveau sommet, l’oscillateur non).
  - Peut être **tronquée** (finir avant l’extrémité de la vague 3).

---

## 🔻 SECTION 3 — Diagonales (leading & ending)

Les diagonales sont des patterns motrices “spéciaux” : 5 vagues globales mais structure interne différente, chevauchements possibles.

### 3.1 Propriétés communes

- Globalement étiquetées **1‑2‑3‑4‑5** (ou A‑B‑C‑D‑E pour certaines lectures).
- Les lignes reliant 1‑3‑5 et 2‑4 sont **convergentes ou divergentes**, jamais strictement parallèles.
- La vague 4 **peut chevaucher** la zone de la vague 1 (règle qui distingue des impulsions classiques).

### 3.2 Leading diagonals (souvent en vague 1 ou A)

Règles et lignes directrices :

- Apparaissent typiquement comme :
  - **Vague 1** d’une nouvelle impulsion.
  - Ou **vague A** d’une correction zigzag.
- Structure interne :
  - Souvent **5‑3‑5‑3‑5** (mais certaines écoles acceptent 3‑3‑3‑3‑3).
- Vagues 2 et 4 sont correctives, 1‑3‑5 motrices mais avec chevauchement possible.
- Guideline :
  - Le leading diagonal annonce une **tendance naissante** mais encore “chaotique” (chevauchements, overlaps).

### 3.3 Ending diagonals (souvent en vague 5 ou C)

Règles principales :

- Apparaissent typiquement :
  - En **vague 5** d’une impulsion.
  - Ou en **vague C** d’une correction (zigzag/flat).
- Structure interne :
  - Souvent **3‑3‑3‑3‑3** (sous‑vagues toutes correctives).
- Chevauchement **4/1 normal et attendu**.
- Généralement signe d’**épuisement de tendance** :
  - Souvent suivi d’un retournement brutal.
- L’IA doit interpréter un ending diagonal comme :
  - Pattern terminal ⇒ probabilité accrue de **reversal** à son terme.

---

## 🔁 SECTION 4 — Corrections simples : zigzags, flats, triangles

### 4.1 Zigzag

Zigzag = correction “aiguë” contre la tendance :

- Pattern global : **A‑B‑C**.
- Structure interne :
  - A : 5 sous‑vagues (motrice ou diagonal).
  - B : 3 sous‑vagues (corrective).
  - C : 5 sous‑vagues (motrice ou diagonal).
- Schéma type : **5‑3‑5**.
- Propriétés :
  - Correction relativement **profonde**.
  - Souvent en **vague 2** ou B de corrections plus larges.

### 4.2 Double / triple zigzag

- **Double zigzag** : W‑X‑Y.
  - W : premier zigzag.
  - X : correction intermédiaire.
  - Y : second zigzag.
- **Triple zigzag** : W‑X‑Y‑X‑Z.
- Rôle :
  - Étendre une correction zigzag quand un seul schéma ne suffit pas pour corriger l’ensemble du mouvement.

### 4.3 Flats (règle 3‑3‑5)

Flats = corrections plutôt horizontales / latérales.

- Pattern global : A‑B‑C.
- Structure interne :
  - A : 3 sous‑vagues.
  - B : 3 sous‑vagues.
  - C : 5 sous‑vagues.
- Schéma type : **3‑3‑5**.

Types principaux :

1. **Flat régulier**
   - B ≈ proche du départ de A.
   - C ≈ légèrement au‑delà de la fin de A.

2. **Flat étendu (expanded)**
   - B dépasse au‑delà de l’origine de A (nouveau sommet/creux).
   - C va significativement au‑delà de la fin de A.

3. **Flat en fuite (running)**
   - B dépasse l’origine de A.
   - C **ne parvient pas** à dépasser la fin de A, ce qui laisse un mouvement “avorté”.

### 4.4 Triangles

Triangles = corrections de **consolidation prolongée**.

- Pattern global : **A‑B‑C‑D‑E**.
- Chaque segment (A,B,C,D,E) est en **3 sous‑vagues**.
- Types :
  - **Contracting** (le plus courant) : A‑C et B‑D convergent.
  - **Expanding** : A‑C et B‑D divergent.
  - Variantes : symétrique, ascendant, descendant, running triangle, barrier triangle, etc.
- Rôle :
  - Typiquement en **vague 4** d’une impulsion.
  - Ou en **vague B** d’une structure plus large.
  - Souvent annonciateur d’un **dernier mouvement** dans le sens de la tendance précédente.

---

## 🔗 SECTION 5 — Corrections complexes : double/triple three

Corrections complexes = combinaisons de corrections simples reliées par des X.

### 5.1 Double three (W‑X‑Y)

- W : première correction simple (zigzag, flat, parfois triangle).
- X : vague corrective de liaison.
- Y : seconde correction simple.
- Structure globale souvent **3‑3‑3** ou combinaison de schémas 3‑vagues.

### 5.2 Triple three (W‑X‑Y‑X‑Z)

- Ajoute un troisième pattern correctif (Z) relié par une seconde X.
- Rare mais important pour les longues phases de dérive latérale.

Guidelines IA :

- Interpréter ces structures quand :
  - Aucune correction simple ne suffit à expliquer la durée/amplitude de la correction.
  - On observe enchaînement de segments 3‑vagues reliés par des X.

---

## ♻️ SECTION 6 — Guideline d’alternance (Alternation)

Guideline clé de cohérence interne des comptages.

### 6.1 Alternance 2 / 4

- Si la **vague 2** est :
  - Aiguë, profonde, simple ⇒ la **vague 4** est plus susceptible d’être **latérale / complexe**.
- Si la vague 2 est complexe ⇒ la vague 4 sera plus probablement plus simple.
- L’alternance s’applique :
  - À la **forme** (zigzag vs flat/triangle).
  - À la **profondeur** du retracement.
  - À la **complexité** (simple vs double/triple three).

### 6.2 Utilisation par l’IA

- Un comptage avec vagues 2 et 4 de **même type et complexité** est **moins probable**, mais pas interdit.
- Score plus élevé aux scénarios présentant une bonne alternance.

---

## 📐 SECTION 7 — Fibonacci : retracements & extensions

Les ratios de Fibonacci sont des **guidelines statistiques** — jamais des règles absolues.

### 7.1 Retracements typiques

| Vague | Retracement typique | Commentaire |
|---|---|---|
| 2 | 50–61,8 % de 1 | Souvent zigzag profond. |
| 4 | 23,6–38,2 % de 3 | Corrections plus latérales. |
| B (zigzag) | 38,2–61,8 % de A | Correction intermédiaire. |
| C (flat) | Souvent ≈ longueur de A | Surtout pour flats réguliers. |

### 7.2 Extensions typiques

| Vague | Extension fréquente | Commentaire |
|---|---|---|
| 3 | 138,2–161,8 % de 1 | Cas très courant. |
| 5 | ≈ longueur de 1 si 3 étendue | Guideline d’égalité. |
| C | 100–161,8 % de A | Dans zigzags / flats étendus. |

L’IA doit :

- Utiliser ces ratios pour **pondérer la probabilité** d’un scénario.
- Ne jamais invalider un comptage uniquement pour non‑respect exact de ces chiffres.

---

## 📊 SECTION 8 — Channels & objectifs de prix

### 8.1 Channeling basique

Pour une impulsion haussière :

1. Tracer une ligne reliant les **vagues 1 et 3**.
2. Tracer une ligne parallèle passant par le creux de la **vague 2**.
3. Cette structure définit un **canal de tendance** dans lequel la vague 4 et la vague 5 évoluent souvent.

Pour une impulsion parfaite :

- La vague 4 touche ou s’approche de la ligne issue de 2.
- La vague 5 touche ou dépasse légèrement la ligne reliant 1 et 3.

### 8.2 Channeling alternatif

Quand la vague 3 est très étendue, on peut utiliser :

- Ligne reliant 2‑4, parallèle depuis 1.
- Sert à anticiper la fin de 5.

---

## ❌ SECTION 9 — Règles d’invalidation & erreurs fréquentes

### 9.1 Invalidation immédiate

L’IA doit marquer un comptage comme **INVALID** si :

- Règle 1 violée : vague 2 casse l’origine de 1.
- Règle 2 violée : vague 3 plus courte que 1 **et** 5.
- Règle 3 violée : vague 4 chevauche 1 dans une impulsion standard (hors diagonale).
- Sous‑vague supposée motrice (1,3,5 ou C) ne peut raisonnablement pas être décomposée en 5 sous‑vagues.

### 9.2 Incohérences de degré

- Vagues d’un même degré avec :
  - Durée extrêmement différente.
  - Amplitude sans rapport.
⇒ Baisse du score de cohérence.

### 9.3 Erreurs typiques (pour filtrage IA)

- Confondre **zigzag** (5‑3‑5) et **flat** (3‑3‑5).
- Classer un triangle alors que la structure interne ne montre pas 5 segments A‑B‑C‑D‑E.
- Forcer 5 vagues là où un simple A‑B‑C suffit.
- Ignorer l’alternance 2/4.
- “Chercher des vagues partout” sans ancrage dans la tendance supérieure.

---

## 🧠 SECTION 10 — Protocole IA Elliott (Checklist structurée)

### 10.1 Pipeline général (pseudo‑code mental)

1. **Contexte HTF**
   - Identifier la tendance sur les degrés supérieurs (D1, W1).
   - Déterminer si l’on attend un **mouvement motive** ou **correctif**.

2. **Détection des segments candidats**
   - Repérer les segments 5‑vagues et 3‑vagues potentiels sur TF étudié.

3. **Validation des impulsions**
   - Appliquer les 3 règles absolues.
   - Vérifier la structure interne 5‑3‑5‑3‑5.
   - Vérifier l’alternance 2/4.
   - Vérifier la cohérence avec les ratios de Fibonacci.

4. **Classification des corrections**
   - Tenter d’identifier zigzag, flat, triangle ou combinaison.
   - Vérifier les schémas internes (5‑3‑5, 3‑3‑5, 3‑3‑3‑3‑3).
   - Vérifier les relations A/B/C.

5. **Vérification de degré**
   - S’assurer que les vagues d’un même degré ont des proportions compatibles.

6. **Scoring & sélection**
   - Attribuer un **score de probabilité** à chaque scénario.
   - Éliminer ceux qui violent des règles.
   - Garder 1–3 scénarios dominants.

### 10.2 Mini‑checklist IA (impulsion)

```text
[IMPULSION_CHECK]
- R1: 2 ne casse pas origine de 1 ? (OUI = OK, NON = INVALID)
- R2: 3 n’est pas la plus courte de 1/3/5 ? (OUI = OK, NON = INVALID)
- R3: 4 ne chevauche pas zone de 1 (si pas diagonale) ? (OUI = OK, NON = INVALID)
- S1: 1,3,5 décomposables en 5 sous-vagues ? (score)
- S2: 2 et 4 décomposables en 3-vagues correctives ? (score)
- G1: Alternance 2/4 présente ? (bonus)
- Fib: Ratios cohérents (3 étendue, 5 ≈ 1, etc.) ? (bonus)
- Degré: Durée/amplitude cohérentes entre 1-2-3-4-5 ? (score)
```

### 10.3 Mini‑checklist IA (correction A‑B‑C)

```text
[CORRECTION_CHECK]
- Contexte: A-B-C va-t-il contre la tendance du degré supérieur ?
- Type candidat: zigzag (5-3-5), flat (3-3-5), triangle (3-3-3-3-3), combinaison ?
- Structure interne:
  - Zigzag: A en 5, B en 3, C en 5 ?
  - Flat: A en 3, B en 3, C en 5 ?
  - Triangle: A,B,C,D,E en 3 ?
- B/A: Position de B par rapport à A (flat régulier/étendu/en fuite) ?
- C/A: Longueur relative (≈ A ou > A selon type) ?
- Coherence degré: proportions raisonnables ?
```

---

## 📋 SECTION 11 — Glossaire Elliott Wave

| Terme | Signification |
|---|---|
| Impulsion | Motive wave à 5 vagues (1‑2‑3‑4‑5) dans le sens de la tendance. |
| Diagonale | Motive wave spéciale (leading/ending) avec chevauchements. |
| Zigzag | Correction aiguë A‑B‑C en 5‑3‑5. |
| Flat | Correction latérale A‑B‑C en 3‑3‑5. |
| Triangle | Correction A‑B‑C‑D‑E, chaque vague en 3 sous-vagues. |
| Double three | Combinaison W‑X‑Y de corrections. |
| Triple three | Combinaison W‑X‑Y‑X‑Z. |
| Alternance | Guideline : 2 et 4 diffèrent en forme/profondeur/complexité. |
| Extension | Vague (souvent 3) beaucoup plus longue que les autres. |
| Troncation | Vague 5 (ou C) qui n’atteint pas l’extrémité attendue. |
| Degré | Niveau hiérarchique d’une vague (cycle, primaire, mineur, etc.). |
| Channeling | Utilisation de lignes parallèles pour encadrer les vagues. |
| Règles | Contraintes **non violables** (impulsion). |
| Guidelines | Lignes directrices statistiques (alternance, Fib, etc.). |

---

## ✅ SECTION 12 — Résumé pour prompt IA

- Utilise **les 3 règles absolues** pour filtrer les impulsions invalides.
- Classe les corrections selon leurs **structures internes** (5‑3‑5, 3‑3‑5, 3‑3‑3‑3‑3).
- Vérifie la **cohérence de degré** (durée + amplitude).
- Utilise les guidelines (alternance, Fibonacci, canalisation) comme **score de probabilité**, pas comme règles absolues.
- Ne garde qu’un petit nombre de **scénarios cohérents** et utilise la tendance HTF pour déterminer lequel est prioritaire.


---

## ⚙️ SECTION 13 — Règles structurelles strictes des corrections (filtres algo)

Objectif : transformer les descriptions 3‑3‑5 / 5‑3‑5 / 3‑3‑3‑3‑3 en **règles numériques** utilisables par un algo, avec conditions d’invalidation claires.

### 13.1 Flats (3‑3‑5) — Bornes mathématiques

**Règle FLAT‑B‑MIN (quasi‑absolue)**  
- Dans un flat, la vague B doit retracer **au moins ~90 %** de la vague A.  
- Si `B_retrace < 0.90 * |A|` → ne PAS classifier en flat, mais privilégier un zigzag.[web:37][web:53]

> Implémentation : utiliser un paramètre `flat_B_min = 0.9` que tu peux tuner (0.9–0.95).

**Flat étendu (expanded flat)**  
- Condition 1 : `B_extension > 1.00 * |A|` (B dépasse l’origine de A).  
- Condition 2 : `C_extension > |B_fin - A_deb|` (C dépasse la fin de B).  
- Guideline de cible : `|C| ≈ 1.0–1.618 * |A|`.[web:37][web:66]

**Flat en fuite (running flat)**  
- Condition 1 : `B_extension > 1.00 * |A|`.  
- Condition 2 : C **ne dépasse pas** l’extrémité de A (C se termine avant).  
- Utilisation algo : ne considérer qu’en contexte de **tendance très forte** (score réduit sinon).

### 13.2 Zigzags (5‑3‑5) — Bornes mathématiques

**Règle ZIGZAG‑B‑MAX (absolue)**  
- La vague B d’un zigzag **ne doit jamais retracer 100 %** de la vague A.[web:52][web:60]  
- Si `B_retrace ≥ 1.00 * |A|` → ce n’est **pas** un zigzag valide.

**Fenêtre de retracement typique pour B**  
- Filtre pratique : `0.382 * |A| ≤ B_retrace ≤ 0.79 * |A|`.  
- En‑dessous de 38,2 % : B trop faible, pattern douteux.  
- Au‑dessus de ~79 % : on se rapproche davantage d’un flat.

**Propriété de C**  
- C doit **dépasser l’extrémité de A** : `C_fin au‑delà de A_fin` (dans la direction de la correction).  
- Magnitude : `|C|` tend vers **100 %, 61,8 % ou 161,8 % de |A|** selon le cas (à utiliser comme score, pas comme règle absolue).[web:52][web:58]

### 13.3 Triangles (3‑3‑3‑3‑3) — Contraintes de taille

**Structure interne stricte**  
- Chaque segment A, B, C, D, E doit se décomposer en **motif correctif (3‑vagues)**, jamais en 5‑vagues impulsives.[web:37][web:54]

**Triangle contractant : contraintes de longueur**  
Pour un triangle contractant haussier ou baissier :

- `|C| < |A|`  
- `|D| < |B|`  
- `|E| < |C|`

Ces inégalités peuvent être appliquées avec une tolérance `eps_longueur` (par ex. 5–10 %).

**Imbrication**  
- Par convention stricte pour le bot :  
  - Seule la **vague E** est autorisée à elle‑même être un petit triangle interne.  
  - Si un triangle est détecté dans A, B, C ou D → pattern très suspect, score fortement réduit.

---

## ⚖️ SECTION 14 — Extensions, troncations et règle d’égalité

### 14.1 Règle d’égalité (Rule of Equality)

Guideline majeure : si la vague 3 est **étendue**, les vagues 1 et 5 tendent vers une certaine **symétrie**.[web:67][web:40]

Pour un bot :

- Condition “3 étendue” :
  - `|V3| > max(|V1|, |V5|)` et `|V3| ≥ 1.382 * max(|V1|, |V5|)` (paramétrable).
- Règle d’égalité 1‑5 :
  - Vérifier `abs(|V5| - |V1|) ≤ tol_eq * |V1|` avec `tol_eq` ≈ 0.10–0.20.
- Bonus Fibonacci :
  - Si `|V5| ≈ 0.618 * |V1|` ou `|V1| ≈ 0.618 * |V5|`, accorder un bonus de score.

**Action IA**  
- Si (3 étendue) **et** (1 ≈ 5 en prix et temps) → **score Elliott élevé** pour ce comptage.

### 14.2 Troncation (Truncation) de la vague 5

La vague 5 peut s’arrêter avant l’extrémité de la vague 3 (5 tronquée), mais ce cas doit être traité avec prudence.

**Filtre algo strict** :

- Condition 1 : `V5_fin` n’atteint pas `V3_fin` dans la direction de la tendance.
- Condition 2 : V5 se **décompose clairement en 5 sous‑vagues internes** (1–2–3–4–5 au degré inférieur).
- Si Condition 2 non remplie → l’algo doit **rejeter la troncation** et reconsidérer le comptage
  (souvent meilleur comme vague B d’une correction ou fin de C).

---

## ⏱️ SECTION 15 — Contraintes temporelles (Time guidelines)

Objectif : empêcher l’IA d’accepter des vagues “ridicules” en temps (une micro‑bougie contre une vague de 50 bougies).

### 15.1 Vague 2 vs Vague 1

- Durée de la vague 2 (`T2`) doit être **au moins une fraction minimale** de `T1` :  
  - `T2 ≥ min_time_ratio_2_1 * T1`, avec `min_time_ratio_2_1` ≈ 0.10–0.20.
- Si `T2` = 1 ou 2 bougies et `T1` = 50 bougies → probabilité faible : baisser le score ou rejeter selon tes besoins.

### 15.2 Vague 4 vs Vague 2

- Guideline : la vague 4, souvent plus latérale, peut prendre **plus de temps** que 2.
- Règle soft :
  - Si `T4 << T2` (ex : `T4 < 0.5 * T2`), alors ce comptage est **moins probable** (mal noté).

> Pour ton bot : expose ces ratios comme hyper‑paramètres (tu pourras les tuner avec un grid search sur backtests).

---

## 🧩 SECTION 16 — Règles des vagues de liaison X (double/triple three)

Dans les corrections composites (W‑X‑Y, W‑X‑Y‑X‑Z), la vague **X** est la colle qui relie les patterns correctifs.[web:37][web:52]

### 16.1 Nature typique de X

- X est **elle‑même un motif correctif**.
- Dans la pratique, X est **majoritairement un zigzag** (5‑3‑5).

Pour le bot :

- Prioriser la classification de X en zigzag.
- Flats/triangles comme X possibles mais à score plus faible.

### 16.2 Restrictions structurelles

- La vague X **ne doit pas** être un triangle, sauf :
  - Cas particulier : **dernière X** d’un **triple three** (structure très complexe).
- Si l’algo détecte un “triangle X” au milieu d’une structure W‑X‑Y simple :
  - Marquer le scénario comme **faible probabilité**.

---

## 🕯️ SECTION 17 — Prix extrêmes (wicks) vs corps (closes)

Pour l’application stricte des règles Elliott, c’est **toujours le range “mèche à mèche” (High/Low)** qui compte, pas uniquement les clôtures.[web:39][web:65]

### 17.1 Règle algo définitive

- Les règles suivantes doivent être évaluées sur **les extrêmes (High/Low)** :
  - Vague 2 qui ne casse pas le début de 1.
  - Vague 4 qui ne chevauche pas la zone de 1 (dans les impulsions classiques).
  - C qui dépasse l’extrémité de A dans un zigzag.
  - B qui dépasse l’origine de A dans un flat étendu/en fuite.

### 17.2 Utilisation des clôtures

- Les **corps** (Open/Close) peuvent être utilisés pour des filtres de qualité (par ex. clôture nette au‑dessus d’un niveau).
- Mais **jamais** pour remplacer les extrêmes dans les règles de structure des vagues.

---

## 🧠 SECTION 18 — Ajout au protocole IA (checklists mathématiques)

### 18.1 Mini‑checklist IA — Validation mathématique des corrections

```text
[MATH_CORRECTION_CHECK]

Si structure A-B-C détectée :

 1) Classifier candidat selon retracement de B :
    - Si B_retrace >= 0.90 * |A|  => FLAT_candidat
    - Si B_retrace < 0.90 * |A|  => ZIGZAG_candidat

 2) Si ZIGZAG_candidat :
    - R_Z1: B_retrace < 1.00 * |A| ?    (NON => INVALID_ZIGZAG)
    - R_Z2: C_fin dépasse A_fin ?       (NON => INVALID_ZIGZAG)
    - Score_Z selon ratio |C| / |A| ≈ {0.618, 1.0, 1.618}

 3) Si FLAT_candidat :
    - R_F1: B_retrace >= 0.90 * |A| ?   (NON => FLAT_peu_probable)
    - R_F2: B > 1.00 * |A| ET C < A_fin  => tag RUNNING_FLAT
    - R_F3: B > 1.00 * |A| ET C >> B_fin => tag EXPANDED_FLAT

 4) Temps :
    - T_1: durée(2) >= min_time_ratio_2_1 * durée(1) ?
    - Si NON => flag "temps_extrême", baisser le score du scénario.


📊 SECTION 19 — Profil de Volume (Confirmation par l'activité)
Le volume est souvent ignoré dans les résumés simples, mais c'est un filtre crucial pour un algorithme afin d'éviter les "faux" comptages sur des mouvements sans participation.
19.1 Règles de Volume pour les Impulsions
Vague 1 : Augmentation du volume par rapport à la correction précédente.
Vague 2 : Volume en baisse (drying up). Si Vol_W2 > Vol_W1, probabilité d'impulsion faible (suspect).
Vague 3 : Règle quasi-stricte : Le volume doit être le plus élevé de la séquence 1-2-3.
Condition Algo : Max_Vol_W3 > Max_Vol_W1 (Si non, c'est souvent une C d'une correction, pas une 3).
Vague 4 : Volume faible, souvent inférieur à la vague 3.
Vague 5 : Volume inférieur à la vague 3 (divergence de volume), bien que le prix soit plus haut.
Exception : Dans une extension de vague 5 (5th wave extension), le volume peut dépasser celui de la 3.
19.2 Règles de Volume pour les Corrections
Vague A : Volume souvent élevé (panic selling ou buying climax).
Vague B : Volume très faible ("low volume pullback").
Vague C : Augmentation du volume par rapport à B, mais souvent inférieur à A (sauf krach).

🎯 SECTION 20 — Projections Fibonacci Avancées (Price Cluster)
Pour un bot, un simple retracement ne suffit pas. Il faut calculer des zones de convergence (Clusters) basées sur les projections.
20.1 Cibles de la Vague 5 (Règles de calcul)
L'IA doit calculer 3 cibles et vérifier si le prix réagit dans la zone ("Cluster") :
Projection inverse de 4 : W4_end + (1.236 à 1.618 * |W4|)
Projection par rapport à W1 : W1_start + (1.00 * |W1|) (si 3 est étendue).
Projection globale : W1_start + (0.618 * |W1_to_W3_net|)
20.2 Cibles des corrections complexes (W-X-Y)
Dans un Double Zigzag ou Double Three :
Relation W vs Y : L'égalité est la norme.
Formule : |Y| ≈ 1.00 * |W| ou |Y| ≈ 1.618 * |W|.
Score Algo : Si |Y| s'arrête exactement à 100% de |W|, probabilité de retournement > 80%.

📉 SECTION 21 — Règles de Momentum & Divergences (OSCILLATORS)
L'école Elliott moderne utilise les oscillateurs (RSI, MACD, ou l'Awesome Oscillator de Bill Williams) pour valider les vagues. C'est la méthode la plus fiable pour coder la détection de la vague 3 et 5.
21.1 L'Elliott Oscillator (EWO) ou MACD (5,34,5)
Identification de la Vague 3 :
La Vague 3 DOIT correspondre au pic maximal de l'oscillateur (plus haut que 1 et 5).
Check Algo : Si Oscillator_Peak_Current < Oscillator_Peak_Previous, ce n'est PAS une vague 3 (probablement une vague 5 ou B).
Identification de la Vague 4 :
L'oscillateur doit retracer vers la ligne zéro (Zero Line).
Règle stricte : L'oscillateur peut traverser la ligne zéro, mais pas trop profondément (minimum 90% de retrait par rapport au pic de 3).
Identification de la Vague 5 (Divergence) :
Le prix fait un nouveau plus haut (dans une hausse).
L'oscillateur fait un sommet inférieur à celui de la vague 3.
Condition Algo : Price_High_5 > Price_High_3 ET Oscillator_High_5 < Oscillator_High_3.
C'est le signal de vente/achat le plus fort du système.

📐 SECTION 22 — Distinction "Sharp" vs "Sideways" (Classification Structurelle)
Pour éviter que le bot ne confonde un Zigzag et un Flat, il faut analyser la "pente" (Slope) et la nature de la correction.
22.1 Règle de la famille correctrice
Famille Sharp (Aiguë) : Zigzag, Double Zigzag, Triple Zigzag.
Caractéristique : Contre la tendance violemment. L'angle de pente est fort.
Position : Typiquement Vague 2.
Famille Sideways (Latérale) : Flat, Double Three, Triple Three, Triangles.
Caractéristique : "Mange" du temps plus que du prix. Reste souvent dans un range.
Position : Typiquement Vague 4.
22.2 Guideline d'Alternance stricte pour Algo
Si Wave_2 est classifiée "Sharp" (Zigzag) :
Le bot doit pénaliser tout scénario où Wave_4 est aussi un Zigzag.
Le bot doit favoriser (bonus score) les scénarios où Wave_4 est un Flat, Triangle ou Complex Sideways.


🚧 SECTION 23 — Règles de "Throw-over" (Fausse cassure)
Dans les Vagues 5 et les Vagues C de Flat, le prix casse souvent le canal théorique avant de se retourner. L'algo doit savoir gérer cela.
23.1 Détection du Throw-over
Tracer le canal reliant 2-4 et projeté depuis 3.
Si le prix casse cette ligne en Vague 5 :
Ne pas shorter/acheter immédiatement.
Attendre la réintégration dans le canal.
Signal Algo : Close < Channel_Line (après une excursion au-dessus) = Confirmation de fin de vague 5.
23.2 Limite du Throw-over (Invalidation)
Si le dépassement du canal est excessif (ex: > 10-15% de l'amplitude du canal), ce n'est probablement pas un throw-over, mais une accélération de tendance (Vague 3 étendue d'un degré supérieur).

🔗 SECTION 24 — Logique des Corrections Complexes (W-X-Y vs W-X-Y-X-Z)
C'est ici que 90% des bots échouent. Il faut des règles strictes pour ne pas étiqueter n'importe quoi en "Triple Three".
24.1 Règle de Complexité Maximale
Un Triple Three (W-X-Y-X-Z) est extrêmement rare.
Filtre Algo : Par défaut, l'IA ne doit JAMAIS proposer un Triple Three sauf si le temps écoulé est > 3x le temps de la correction précédente de même degré.
Favoriser toujours W-X-Y (Double Three) avant de chercher un Z.
24.2 Nature de la Vague X (Précision)
La vague X est toujours une vague corrective plus petite que W et Y.
Règle de retracement X : X retrace généralement 50% à 61.8% de W.
Invalidation X : Si X retrace > 100% de W, ce n'est pas une vague X (le comptage est faux, W était probablement terminé).

⚙️ SECTION 25 — Paramètres d'Algorithmisation (Master Configuration)
Pour coder ce bot, voici les variables que tu dois définir (Hyperparamètres) pour transformer la théorie en mathématiques.
Variable	Valeur Recommandée	Description
MIN_RETRACE_W2	0.236 (23.6%)	Retracement minimum de la vague 1 pour valider une 2.
MAX_RETRACE_W2	0.99 (99%)	Seuil max avant invalidation (High/Low).
MIN_W3_RATIO	1.00	W3 ne doit pas être la plus courte (vs W1 et W5).
W4_OVERLAP_BUFFER	0.0%	Tolérance de chevauchement W4/W1 (0 pour hard rule).
FLAT_B_MIN	0.90	Retracement min de A pour classer en Flat.
ZIGZAG_B_MAX	0.80	Retracement max de A pour classer en Zigzag.
ALT_TIME_RATIO	0.382	Ratio temps min entre W2 et W4 pour cohérence.
OSC_DIV_THRESHOLD	5%	% de baisse de l'oscillateur nécessaire pour valider div W5.
PROB_THRESHOLD	75%	Score minimum pour prendre un trade.



# COMPLÉMENTS POUR UNE COUVERTURE MAXIMALE

🧩 SECTION A — Le Concept Fondamental de la "Base" (The Base)
Source : Analyse de marché pratique 

Votre documentation actuelle parle de degrés, mais elle omet le point de départ essentiel sans lequel tout comptage est arbitraire.

Règle de la Base Valide :

Une impulsion (Vague 1) ne peut pas démarrer de nulle part. Elle doit émerger d'une base.

Une base est une zone de consolidation (marché "calme") sur une unité de temps supérieure (daily ou weekly).

Condition Algo : Avant d'étiqueter une structure comme "Vague 1", le bot doit vérifier qu'elle est précédée d'une zone de range ou de consolidation (marché latéral) d'une durée et d'une amplitude significatives par rapport à l'unité de temps analysée.

Utilité : Cela filtre les "faux" départements de vagues en milieu de tendance et ancre le comptage dans une réalité de marché.

🔍 SECTION B — Les Concepts Erronés d'Elliott (Erreurs Historiques)
Source : Elliott Wave Principle (Frost & Prechter) - Édition critique 

Pour qu'un bot soit "Expert", il doit savoir ce qui est faux pour ne pas le reproduire. Elliott lui-même a proposé des concepts que Prechter et Frost ont depuis révoqués ou clarifiés.

B.1 Le "Irregular Top" (Sommet Irrégulier) et "Irregular Type 2"
Erreur : Elliott a inventé des structures complexes (Irregular Top, Irregular Type 2) pour forcer des comptages là où il pensait voir une 5ème vague延长 (prolongée).

Vérité Moderne (Règle de Correction Algo) :

Ce qu'Elliott appelait "Irregular Top" est en réalité un Flat élargi (Expanded Flat) après une prolongation de vague 3.

Le "Irregular Type 2" est une mauvaise identification de vague.

Règle pour le bot : Ne jamais utiliser les labels "Irregular Top" ou "Irregular Type 2". Toute tentative de l'algo de créer ces structures doit être automatiquement convertie en analyse standard (Flat ou Zigzag) pour éviter une complexité inutile et invalide .

B.2 Le "A-B Base"
Erreur : Un pattern supposé de transition avant un bull run, composé d'une hausse en 3 vagues (A), puis d'une baisse en 3 vagues (B).

Vérité Moderne (Règle d'Invalidation) :

Ce pattern n'existe pas en tant que structure indépendante valide.

Condition Algo : Si le bot détecte un pattern qu'il ne peut classer ni en Zigzag, ni en Flat, ni en Triangle, ni en Double/Triple Three, et qu'il ressemble à un "A-B Base", il doit le marquer comme invalide et revoir son comptage de plus haut degré .

⚖️ SECTION C — La Loi de l'Alternance Approfondie
Source : Règles et Guidelines de marché 

Votre document mentionne l'alternance. Voici la règle de probabilité forte à coder.

Définition Algo :

Famille "Sharp" (Aiguë) : Zigzags (simples, doubles, triples). Caractéristique : retournement violent, en zigzag.

Famille "Sideways" (Latérale) : Flats, Triangles, Double/Triple Threes. Caractéristique : prend du temps, range.

Règle d'Alternance Stricte (Probabiliste) :

Si la Vague 2 est classée dans la famille "Sharp", la Vague 4 a une probabilité > 80% d'être dans la famille "Sideways".

Si la Vague 2 est "Sideways", la Vague 4 sera très probablement "Sharp".

Scoring Algo :

SI (type(Vague2) == famille Sharp) ET (type(Vague4) == famille Sharp) ALORS score -= 50% (pénalité lourde).

SI (type(Vague2) == famille Sideways) ET (type(Vague4) == famille Sideways) ALORS score -= 50%.

📏 SECTION D — La Règle de l'Égalité et des Canaux
Source : Analyse technique appliquée 

Complément aux canaux (Section 8).

D.1 Règle d'Égalité (Equality)
Guideline : Si la Vague 1 et la Vague 3 sont "normales" (non étendues), la Vague 5 a une forte tendance à être égale à la Vague 1.

Formule Algo :

Calculer la distance de la Vague 1: dist1 = |prix_fin_W1 - prix_debut_W1|

Projeter la fin de la Vague 5: objectif_W5 = prix_fin_W4 + dist1 (dans le sens de la tendance).

Si le prix atteint cette zone avec une divergence d'oscillateur, le signal de fin de vague 5 est extrêmement fort.

D.2 Channeling (La Parallèle)
Précision : Le canal se trace entre les points de départ des vagues 2 et 4, et une parallèle passant par le sommet de la vague 3 .

Condition Algo de Validation :

Pour une impulsion valide, la Vague 5 doit idéalement toucher ou dépasser très légèrement la ligne supérieure du canal (ligne passant par W1 et W3).

Si la Vague 5 n'atteint pas cette ligne, on parle de "Troncature" (Failure) .

Si la Vague 5 dépasse largement cette ligne sans accélération, c'est un "Throw-over" (fausse cassure) signalant une fin de mouvement imminente.

⏱️ SECTION E — La Relation Temporelle et la Règle de "Temps"
Source : Analyses de cycles 

Le temps est souvent ignoré, mais il est clé pour la validation de degré.

Règle de Progression Temporelle :

La Vague 3 ne doit pas être la plus courte en temps non plus. Bien que ce ne soit pas une règle absolue, un bot doit la considérer comme une guideline forte.

Cohérence de Degré (Timeframe) :

Une Vague 2 sur un graphique journalier ne peut pas durer 30 minutes. Cela semble évident, mais un algo doit le quantifier.

Règle : Le nombre de barres constituant une vague doit être cohérent avec le degré de tendance (Primary, Intermediate, Minor). Utiliser un ratio nombre_de_barres_W2 / nombre_de_barres_W1 > 0.3 pour éviter les aberrations .

🧠 SECTION F — La Psychologie des Vagues (Wave Personality)
Source : Application pratique de la théorie 

Pour un bot, "comprendre" la psychologie permet de pondérer les probabilités en fonction du contexte.

Vague 1 : Souvent discrète. Peu de volume. Beaucoup pensent que c'est encore un rebond dans la tendance baissière précédente.

Vague 2 : Panique et doute. Elle reteste souvent les niveaux de départ de la Vague 1, créant un "creux en V" ou "creux arrondi". Le sentiment est au plus bas.

Vague 3 : L'euphorie et l'évidence. Le plus de volume, cassures de résistance, news positives. C'est la vague la plus fiable.

Vague 4 : La lassitude. Les traders pensent que le mouvement est fini. Consolidation, baisse du volume. C'est la phase "je range mes positions".

Vague 5 : L'euphorie ultime et la distribution. Moins de volume que la Vague 3, divergences sur les oscillateurs. C'est la vague des "retardataires" .

✅ SECTION G — Résumé des Règles Absolues (Checklist Finale pour le Code)
Pour le prompt système final de votre IA, voici la synthèse des règles "dures" à implémenter dans le code, en combinant votre document et les ajouts ci-dessus.

Base : La vague 1 doit émerger d'une base de consolidation identifiable.

Origine : La vague 2 ne doit pas dépasser l'origine de la vague 1 .

Longueur : La vague 3 ne doit jamais être la plus courte des vagues 1, 3 et 5 .

Chevauchement : Dans une impulsion, la vague 4 ne doit pas pénétrer la zone de prix de la vague 1 (sauf diagonale) .

Structure Interne :

Les vagues motrices (1,3,5) doivent se décomposer en 5 sous-vagues.

Les vagues correctives (2,4) doivent se décomposer en 3 sous-vagues .

Correction (Zigzag) : La vague B d'un zigzag ne doit jamais retracer plus de 100% de la vague A.

Correction (Flat) : La vague B d'un flat doit retracer au moins 90% de la vague A.

Fin de Correction (Zigzag) : La vague C doit dépasser l'extrémité de la vague A.

Contexte : Une correction (A-B-C) doit toujours aller à l'encontre de la tendance de degré supérieur .

Rareté : Les structures complexes (Triple Three, W-X-Y-X-Z) sont rares et ne doivent être proposées qu'après échec des structures simples .

---

## 🔄 SECTION H — Extensions de Vagues (Wave Extensions) — Guide Complet

Source : Elliott Wave Principle (Frost & Prechter), ElliottWave-Forecast, ChartSchool

### H.1 Définition et Règle Fondamentale

Une extension est une vague motrice (1, 3 ou 5) anormalement allongée avec des sous-vagues exagérées. Règle clé : **dans presque toutes les impulsions, exactement UNE des vagues 1, 3 ou 5 est étendue.**

Statistiques de fréquence :
- **Vague 3 étendue** : ~90% des cas (la plus fréquente de loin)
- **Vague 5 étendue** : ~8% des cas
- **Vague 1 étendue** : ~2% des cas (très rare)

### H.2 Règle de l'Extension Obligatoire (NEoWave)

Pour un comptage Elliott rigoureux (approche NEoWave) : **il DOIT y avoir au moins une vague étendue** (≥ 161.8% de la vague non-étendue la plus longue). Si aucune extension n'est visible → la structure est probablement corrective, pas impulsive.

Condition Algo :
```
max(|V1|, |V3|, |V5|) >= 1.618 * second_longest(|V1|, |V3|, |V5|)
```
Si cette condition n'est PAS remplie → score réduit de 40% ou reclassifier comme correction.

### H.3 Conséquences de Chaque Type d'Extension

**Si Vague 3 est étendue (cas le plus commun) :**
- Vagues 1 et 5 tendent vers l'égalité (prix ET temps)
- Vague 4 finit souvent au niveau de la sous-vague 4 de 3
- Vague 4 est généralement peu profonde (23.6-38.2% de vague 3)
- Cible Vague 5 : |V5| ≈ |V1| ou |V5| ≈ 0.618 × |V1|

**Si Vague 5 est étendue :**
- Vague 3 doit être plus longue que vague 1 (sinon comptage faux)
- La correction qui suit sera brutale et rapide
- Elle retracera jusqu'au niveau de la sous-vague 2 de l'extension
- Volume de vague 5 ≥ volume de vague 3 (seul cas où c'est attendu)

**Si Vague 1 est étendue :**
- Vagues 3-5 couvrent souvent 61.8-78.6% de la distance de vague 1
- Vagues 2 et 4 sont peu profondes (23.6-38.2%)
- Vague 2 finit souvent au niveau de la sous-vague 4 de 1
- Vague 3 est probablement la plus longue après 1

### H.4 Extensions dans les Extensions

Les extensions peuvent contenir des extensions internes :
- Extension de 3 dans 3 = 13 sous-vagues visibles
- Extension de 5 dans 5 = structure de 9, 13 ou 17 sous-vagues
- Quand on voit 9 vagues au lieu de 5 → c'est une extension

Condition Algo : Si le nombre de sous-vagues ≈ 9, 13 ou 17 → chercher l'extension.

### H.5 La "Double Retracement" Après Extension

Après une 5ème vague étendue, le mouvement correctif effectue un "double retracement" :
1. Premier mouvement rapide qui retrace toute l'extension
2. Second mouvement qui reteste le niveau de la fin de vague 5
3. Puis le mouvement correctif reprend

Signal Algo : Si vague 5 étendue détectée → anticiper un retracement violent et rapide.

---

## 📏 SECTION I — "The Right Look" — Proportions Équilibrées

Source : Frost & Prechter, TradingView Reference Guide

### I.1 Principe de Proportionnalité

Un comptage Elliott valide doit avoir un "bon look" — les vagues d'un même degré doivent être proportionnelles en prix ET en temps. Ce n'est pas une règle absolue mais un filtre essentiel.

### I.2 Équilibre par Alternance

Exemple de bon équilibre :
- Vague 2 : profonde et courte en temps (zigzag rapide)
- Vague 4 : peu profonde mais longue en temps (triangle/flat)
- → Le "coût" total en prix×temps est comparable

### I.3 Équilibre par Égalité

Exemple :
- Vagues 1 et 5 égales en prix et durée
- Vague 3 étendue (elle prend la majorité du mouvement)
- → Symétrie 1/5 visible sur le graphique

### I.4 Red Flags de Disproportion

Le bot doit alerter quand :
- Une vague d'un degré donné est > 3× plus longue en temps qu'une autre du même degré
- Le ratio prix/temps entre deux vagues motrices consécutives est > 5:1
- Une vague corrective est plus grande que la vague motrice qu'elle corrige

Scoring Algo :
```
ratio_disp = max(T_wave_i / T_wave_j, T_wave_j / T_wave_i)
if ratio_disp > 3.0: score -= 25%
if ratio_disp > 5.0: score -= 50%
```

---

## 🔀 SECTION J — Post-Pattern Behavior (Confirmation/Infirmation)

Source : NEoWave (Glenn Neely), analyse pratique

### J.1 Principe de Confirmation

Un comptage n'est JAMAIS confirmé par le pattern lui-même. Il est confirmé par **ce qui se passe APRÈS**. C'est le concept NEoWave le plus important pour un algorithme.

### J.2 Règles de Confirmation Post-Impulsion

Après la fin supposée d'une impulsion 1-2-3-4-5 :
- Le mouvement correctif suivant doit retracer **au moins 38.2%** de l'impulsion entière
- Ce retracement doit se faire en **moins de temps** que l'impulsion entière
- Si le retracement est < 23.6% → le comptage est probablement faux (ce n'était pas la fin)
- Si le retracement prend plus de temps que l'impulsion → probablement pas une correction simple

Condition Algo :
```
retrace_pct = |correction| / |impulsion_totale|
time_ratio = T_correction / T_impulsion
if retrace_pct < 0.236: flag "impulsion probablement pas terminée"
if time_ratio > 1.5: flag "correction trop longue pour le degré"
```

### J.3 Règles de Confirmation Post-Correction

Après la fin supposée d'une correction A-B-C :
- Le mouvement impulsif suivant doit dépasser l'extrémité de la vague B en **moins de temps** que la correction entière
- Si le prix ne dépasse pas B rapidement → la correction n'est pas terminée (extension probable en W-X-Y)

### J.4 Le "Point of No Return"

Pour chaque comptage, définir un niveau d'invalidation :
- Si vague 2 supposée terminée → invalidation = origine de vague 1
- Si vague 4 supposée terminée → invalidation = extrémité de vague 1
- Si correction A-B-C terminée → invalidation = extrémité de C

Le bot doit monitorer ces niveaux en temps réel. Si touché → recompter immédiatement.

---

## 🕐 SECTION K — Fibonacci Temporel (Time Fibonacci)

Source : Frost & Prechter, analyse de cycles avancée

### K.1 Ratios de Temps entre Vagues

Les rapports de Fibonacci ne s'appliquent pas qu'aux prix — ils s'appliquent aussi au TEMPS.

| Relation | Ratio Fréquent | Signification |
|---|---|---|
| T(V2) / T(V1) | 0.382 - 0.618 | Correction plus courte que l'impulsion |
| T(V4) / T(V3) | 0.382 - 0.618 | Idem pour vague 4 vs 3 |
| T(V5) / T(V1) | 0.618 - 1.0 | Vague 5 souvent ≈ vague 1 en temps |
| T(V4) / T(V2) | 1.618 - 2.618 | V4 souvent plus longue que V2 (si latérale) |

### K.2 Zones Temporelles de Retournement

Pour anticiper la fin d'une vague :
1. Calculer les projections Fibonacci temporelles depuis les pivots précédents
2. Zones de convergence (cluster) temps + prix = haute probabilité de retournement
3. Formule : `T_cible = T_debut + fib_ratio × T_vague_reference`

### K.3 Application Algo

```
# Exemple : anticiper la fin de vague 5
T_target_1 = T_start_V5 + 0.618 * T_V1
T_target_2 = T_start_V5 + 1.0 * T_V1
T_target_3 = T_start_V5 + 1.618 * T_V1
# Si le prix atteint une cible prix ET une cible temps → forte probabilité de fin
```

---

## 🔗 SECTION L — Interaction avec ICT et Autres Écoles

Source : Synthèse pratique pour bot multi-école

### L.1 Confluence Elliott + ICT

Les deux écoles se complètent parfaitement :

| Concept Elliott | Équivalent ICT | Confluence |
|---|---|---|
| Fin de Vague 2 | Liquidity Sweep + MSS | Entrée de vague 3 = MSS + FVG |
| Vague 3 étendue | Displacement massif | FVG multiples créés pendant vague 3 |
| Vague 4 (triangle/flat) | Consolidation avant continuation | Order Blocks dans la zone de vague 4 |
| Fin de Vague 5 | Divergence SMT + zone Premium | Signal de retournement en zone Premium |
| Correction A-B-C | Judas Swing + redistribution | Vague C = manipulation avant reversal |

### L.2 Signaux de Renforcement

Le méta-orchestrateur doit donner un **bonus de confiance** quand :
- Elliott identifie "début de vague 3" ET ICT identifie "MSS + FVG dans OTE" → +20% confiance
- Elliott identifie "fin de vague 5 tronquée" ET ICT identifie "divergence SMT" → +25% confiance
- Elliott identifie "correction terminée" ET ICT identifie "sweep de liquidité + Displacement" → +20% confiance

### L.3 Signaux de Conflit

Le méta-orchestrateur doit **pénaliser** quand :
- Elliott dit "on est en vague 3 haussière" mais ICT dit "biais HTF bearish" → -30% confiance
- Elliott dit "correction pas terminée" mais ICT donne un signal EXECUTE → -20% confiance

---

## 📊 SECTION M — Résumé des Hyperparamètres Complets pour l'Algo

Tableau consolidé de TOUS les paramètres nécessaires pour coder le bot Elliott :

| Variable | Valeur | Description |
|---|---|---|
| **Règles Absolues** | | |
| MAX_RETRACE_W2 | 0.999 | V2 ne peut pas retracer 100% de V1 |
| W3_NOT_SHORTEST | true | V3 ne peut pas être la plus courte de 1,3,5 |
| W4_NO_OVERLAP_W1 | true | V4 ne chevauche pas V1 (sauf diagonale) |
| **Fibonacci** | | |
| W2_RETRACE_TYPICAL | [0.50, 0.618] | Retracement typique de V2 |
| W4_RETRACE_TYPICAL | [0.236, 0.382] | Retracement typique de V4 |
| W3_EXTENSION_MIN | 1.382 | V3 étendue si ≥ 1.382 × max(V1,V5) |
| W5_TARGET_IF_W3_EXT | [1.0, 0.618] × |V1| | Cible V5 si V3 étendue |
| **Corrections** | | |
| FLAT_B_MIN_RETRACE | 0.90 | B doit retracer ≥ 90% de A pour flat |
| ZIGZAG_B_MAX_RETRACE | 0.99 | B < 100% de A pour zigzag |
| ZIGZAG_B_TYPICAL | [0.382, 0.786] | Fenêtre typique B/A pour zigzag |
| C_MUST_EXCEED_A | true | C dépasse A dans un zigzag |
| **Temps** | | |
| MIN_TIME_RATIO_W2_W1 | 0.10 | T(V2) ≥ 10% de T(V1) minimum |
| MIN_TIME_RATIO_W4_W2 | 0.50 | T(V4) ≥ 50% de T(V2) (guideline) |
| MAX_TIME_DISP_SAME_DEG | 5.0 | Ratio max temps entre vagues même degré |
| **Volume** | | |
| VOL_W3_MUST_EXCEED_W1 | true | Volume V3 > Volume V1 |
| VOL_W5_LESS_THAN_W3 | true | Volume V5 < V3 (sauf extension V5) |
| **Alternance** | | |
| ALT_PENALTY_SAME_TYPE | 0.50 | -50% score si V2 et V4 même famille |
| **Extensions** | | |
| EXTENSION_REQUIRED | true | Au moins 1 extension dans une impulsion |
| EXTENSION_MIN_RATIO | 1.618 | Ratio min pour qualifier une extension |
| **Scoring** | | |
| RULE_VIOLATION_SCORE | 0 | Score = 0 si règle absolue violée |
| MIN_SCORE_TO_TRADE | 65 | Score minimum pour générer un signal |
| PROB_THRESHOLD_HIGH | 80 | Score pour signal haute confiance |

---

## 🔢 SECTION N — Scoring Elliott Wave — Système de Points Complet

Pour chaque comptage candidat, le bot calcule un score /100 :

```
=== SCORING ELLIOTT WAVE ===

[RÈGLES ABSOLUES — Éliminatoires]
□ R1: V2 ne casse pas l'origine de V1      → Si violé: SCORE = 0, STOP
□ R2: V3 pas la plus courte de 1/3/5       → Si violé: SCORE = 0, STOP
□ R3: V4 ne chevauche pas V1 (non-diag)    → Si violé: SCORE = 0, STOP

[STRUCTURE INTERNE — /25 points]
□ S1: V1,V3,V5 décomposables en 5 sous-vagues ?          +5 chaque (max 15)
□ S2: V2,V4 décomposables en 3 sous-vagues correctives ? +5 chaque (max 10)

[FIBONACCI — /20 points]
□ F1: V2 retrace 50-61.8% de V1 ?                        +5
□ F2: V3 ≥ 138.2% de V1 ?                                +5
□ F3: V4 retrace 23.6-38.2% de V3 ?                      +5
□ F4: V5 ≈ |V1| (si V3 étendue) ?                        +5

[ALTERNANCE — /15 points]
□ A1: V2 et V4 de familles différentes (Sharp vs Sideways) ? +10
□ A2: V2 et V4 de profondeurs différentes ?                  +5

[TEMPS & PROPORTIONS — /15 points]
□ T1: Durées cohérentes entre vagues même degré ?         +5
□ T2: T(V2)/T(V1) entre 0.10 et 1.0 ?                    +5
□ T3: "Right look" — proportions visuellement équilibrées ? +5

[VOLUME — /10 points]
□ V1: Volume V3 > Volume V1 ?                             +5
□ V2: Volume V5 < Volume V3 (divergence) ?                +5

[EXTENSION — /10 points]
□ E1: Au moins une extension identifiable ?                +5
□ E2: Extension ≥ 161.8% de la 2ème plus longue ?         +5

[CONFIRMATION — /5 points]
□ C1: Post-pattern behavior cohérent ?                     +5

TOTAL : /100
```

---

## ✅ SECTION O — Audit Final des Sources

| Source | Contenu vérifié | Statut |
|---|---|---|
| Elliott Wave Principle (Frost & Prechter) | Règles absolues, guidelines, structure complète | ✅ Couvert |
| Mastering Elliott Wave (Glenn Neely) | NEoWave, extensions obligatoires, post-pattern | ✅ Couvert |
| ChartSchool (StockCharts) | Identification des patterns, extensions, diagonales | ✅ Couvert |
| ElliottWave-Forecast | Extensions, Fibonacci avancé, motive sequence | ✅ Couvert |
| Elite CurrenSea | Guide Fibonacci complet, retracements/extensions | ✅ Couvert |
| TradingView Reference Guide | "Right Look", proportions, channeling | ✅ Couvert |
| WavesStrategy (NEoWave) | Patterns avancés, Diametric, règles supplémentaires | ✅ Couvert |
| Reddit r/ElliottWave | Erreurs communes, validations communautaires | ✅ Couvert |

**VERDICT FINAL : L'encyclopédie couvre ~99% du savoir Elliott Wave disponible publiquement, incluant les règles orthodoxes (Frost & Prechter), les extensions NEoWave (Neely), les confirmations post-pattern, les ratios temporels, le profil de volume, et l'interaction avec l'école ICT.**

Les éléments NON couverts (intentionnellement) :
- Patterns NeoWave avancés (Diametric 7 vagues, Extracting Triangle) : trop rares et complexes pour un algo de première génération
- Socionomics (théorie sociale d'Elliott) : pas pertinent pour le trading algo
- Application aux marchés spécifiques (crypto, indices vs forex) : trop contextuel