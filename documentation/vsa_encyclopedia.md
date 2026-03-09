# 📚 ENCYCLOPÉDIE COMPLÈTE — Agent Expert VSA / Wyckoff v3.0 (Pur Code)
# Sources : Richard D. Wyckoff (Cours originaux), Tom Williams (Master the Markets)
# Contenu : Lois absolues, Variables quantifiées, 100% des signaux VSA (SOS/SOW), Phases Wyckoff algorithmiques
# Version : 3.0 — Couverture 100% pour l'exécution algorithmique stricte

---

## ⚠️ RAPPORT D’AUDIT — Portée de l'Agent IA

Cet agent est programmé pour lire le marché comme le "Composite Man" (Smart Money) en quantifiant l'effort (Volume) et le résultat (Spread). Il ne se base sur aucun indicateur retardé classique (RSI, MACD), mais uniquement sur l'action du prix pur croisée à l'activité volumique.

### Protocoles couverts à 100 %
- Les 3 lois fondamentales traduites en limites algorithmiques.
- Définition stricte des 3 variables VSA (Volume, Spread, Close).
- Évaluation du "Background" (Contexte de tendance indispensable en VSA).
- Les 6 Signaux de Force VSA (Signs of Strength - SOS).
- Les 6 Signaux de Faiblesse VSA (Signs of Weakness - SOW).
- Identification des 5 phases d'Accumulation Wyckoff (A à E) avec règles d'invalidation.
- Identification des 5 phases de Distribution Wyckoff (A à E) avec règles d'invalidation.
- Règles de contexte et de scoring probabiliste.
- Règles de gestion de position basées sur le Volume et le Spread.
- Matrice de confluence avec les niveaux techniques et l'Order Flow.
- Intégration des concepts de "Local Support/Resistance" et "Mini Shelves" 

---

## ⚖️ SECTION 1 — Les 3 Lois de Wyckoff (Filtres Logiques)

**Loi 1 : Offre et Demande (Direction)**
Si la Demande (acheteurs agressifs) est supérieure à l'Offre (vendeurs), le prix monte, et inversement. L'algorithme le détecte par le franchissement de niveaux avec une augmentation du volume.

**Loi 2 : Cause et Effet (Objectif de Prix / Take Profit)**
La "Cause" est le nombre de bougies dans une phase de consolidation (Range). L' "Effet" est le mouvement tendanciel qui suit. 
Règle algorithmique : Le Take Profit (TP) dynamique doit être proportionnel à la durée de la phase d'accumulation/distribution. Un range de 100 bougies justifie un TP beaucoup plus éloigné qu'un range de 20 bougies. La projection horizontale de la largeur du range est ajoutée au point de cassure.

**Loi 3 : Effort vs Résultat (Détection des Anomalies)**
L'Effort est le Volume. Le Résultat est le Spread (taille de la bougie).
Règle algorithmique : Toute divergence entre les deux est un signal de manipulation institutionnelle. Un volume extrême (Effort) sur une toute petite bougie (Résultat nul) implique une absorption massive.

---

## 📐 SECTION 2 — Les 3 Variables VSA (Mathématiques Algorithmiques)

L'agent doit calculer ces métriques sur chaque bougie (barre) clôturée pour éliminer toute subjectivité.

### 2.1 Le Volume (L'Activité)
L'algorithme compare le volume actuel à une moyenne mobile simple sur 20 périodes : `SMA(Volume, 20)`.
- **Low Volume (Faible)** : `Volume < SMA(Volume, 20) * 0.8`
- **Average Volume (Moyen)** : `Volume` compris entre `SMA * 0.8` et `SMA * 1.2`
- **High Volume (Élevé)** : `Volume > SMA(Volume, 20) * 1.5`
- **Ultra-High Volume (Extrême/Climax)** : `Volume > SMA(Volume, 20) * 2.5` (ou le plus haut des 50 dernières bougies). Un volume > 3.0 signifie une capitulation ou un climax extrême.

### 2.2 Le Spread (La Volatilité)
La distance totale de la bougie : `Spread = High - Low`. Comparé à l'Average True Range : `ATR(14)`.
- **Narrow Spread (Étroit)** : `Spread < ATR(14) * 0.75`
- **Average Spread (Moyen)** : `Spread` compris entre `ATR * 0.75` et `ATR * 1.25`
- **Wide Spread (Large)** : `Spread > ATR(14) * 1.5`
- **Ultra-Wide Spread (Très Large)** : `Spread > ATR(14) * 2.0`.

### 2.3 Le Close (La Clôture)
Détermine l'issue de la bataille sur la période, calculé en pourcentage du Plus Bas vers le Plus Haut.
- **Close Low (Bas)** : Clôture dans le tiers inférieur (0% à 33% du Spread).
- **Close Middle (Milieu)** : Clôture dans le tiers central (34% à 66% du Spread).
- **Close High (Haut)** : Clôture dans le tiers supérieur (67% à 100% du Spread).

### 2.4 Les Mèches (Wick/Longueur des Ombres)
Les mèches indiquent un rejet à un niveau de prix.
- **Longue mèche haute** : Rejet des prix élevés (offre). Mèche Haute = High - max(Open, Close). Si la mèche représente > 40% du spread total, c'est un signal de rejet baissier.
- **Longue mèche basse** : Rejet des prix bas (demande). Mèche Basse = min(Open, Close) - Low. Si la mèche représente > 40% du spread total, c'est un signal de rejet haussier.

---

## 🟢 SECTION 3 — Signs of Strength (SOS) : Signaux Haussiers VSA

L'agent doit chercher ces signaux en bas de range (Accumulation) ou lors de pullbacks dans une tendance haussière confirmée.

**1. No Supply (Absence de Vendeurs)**
Règle : `Barre baissière ou neutre` + `Narrow Spread` + `Low Volume` + `Close Middle ou High`.
Signification : Les professionnels refusent de vendre à ces prix. Le marché est libre de monter.

**2. Test / Successful Test (Vérification de l'Offre)**
Règle : `Le Low de la barre casse un support précédent` + `Clôture High (longue mèche basse)` + `Low Volume`.
Signification : La Smart Money enfonce le prix pour voir s'il y a des vendeurs. Le faible volume confirme qu'il n'y en a pas.

**3. Stopping Volume (Freinage Institutionnel)**
Règle : `Tendance baissière préalable` + `Barre baissière` + `Wide Spread` + `Ultra-High Volume` + `Close High ou Middle`.
Signification : La panique du public est absorbée par les ordres d'achat massifs des institutions.

**4. Selling Climax (Épuisement des Vendeurs)**
Règle : `Mouvement baissier prolongé` + `Barre baissière extrême (plus grand spread des 50 dernières barres)` + `Ultra-High Volume` + `Close au-dessus du tiers inférieur`.
Signification : Capitulation finale du public, transfert total des actifs vers la Smart Money.

**5. Push Through Supply (Cassure de Résistance par la Force)**
Règle : `Le prix casse une résistance majeure` + `Barre haussière` + `Wide Spread` + `High ou Ultra-High Volume` + `Close High`.
Signification : Les professionnels absorbent toute l'offre présente sur la résistance pour forcer le passage.

**6. Bottom Reversal (Retournement sur deux barres)**
Règle : `Barre 1 baissière (Wide Spread + High Volume + Close Low)` suivie immédiatement par `Barre 2 haussière (Wide Spread + High Volume + Close High)`. Le Low de la Barre 2 est inférieur ou égal à la Barre 1.

---

## 🔴 SECTION 4 — Signs of Weakness (SOW) : Signaux Baissiers VSA

L'agent doit chercher ces signaux en haut de range (Distribution) ou lors de rebonds dans une tendance baissière confirmée.

**1. No Demand (Absence d'Acheteurs)**
Règle : `Barre haussière` + `Narrow Spread` + `Low Volume` + `Close Low ou Middle`.
Signification : Les professionnels ne participent pas au mouvement haussier. La hausse va s'effondrer sous son propre poids.

**2. Upthrust (Piège Haussier / Chasse aux Stops)**
Règle : `Le High casse une résistance` + `Clôture Low (longue mèche haute)` + `High ou Ultra-High Volume`.
Signification : Manipulation classique. Les institutions poussent le prix au-dessus de la résistance pour déclencher les stops acheteurs, puis vendent massivement.

**3. Hidden Upthrust (Upthrust Caché)**
Règle : `Barre baissière` + `Le High de la barre est supérieur au High de la barre précédente` + `Close Low` + `High Volume`. Identique à l'Upthrust mais termine rouge.

**4. Buying Climax (Épuisement des Acheteurs)**
Règle : `Mouvement haussier prolongé` + `Barre haussière extrême` + `Ultra-High Volume` + `Close au-dessous du tiers supérieur`.
Signification : Euphorie totale du public. Les institutions distribuent leurs positions accumulées.

**5. End of a Rising Market (Effort sans Résultat)**
Règle : `Tendance haussière` + `Barre haussière` + `Narrow Spread` + `Ultra-High Volume`.
Signification : Un volume énorme devrait produire une grande bougie (Wide Spread). Si le spread est étroit, c'est que les professionnels limitent la hausse avec des ordres de vente massifs (Mur de vendeurs).

**6. Top Reversal (Retournement Sommet sur deux barres)**
Règle : `Barre 1 haussière (Wide Spread + High Volume + Close High)` suivie immédiatement par `Barre 2 baissière (Wide Spread + High Volume + Close Low)`. Le High de la Barre 2 est supérieur ou égal à la Barre 1.

---

## 🏗️ SECTION 5 — Schéma d'Accumulation Wyckoff (Checklist Algo Stricte)

L'algorithme doit valider ces événements dans l'ordre chronologique exact pour autoriser un setup d'achat (Long) majeur.

**Phase A : Arrêt de la tendance baissière**
- **PS (Preliminary Support)** : Première apparition de `High Volume` sur bougies baissières après un long déclin.
- **SC (Selling Climax)** : Détecté via les règles SOS (Volume extrême + Close haut). Définit le support absolu.
- **AR (Automatic Rally)** : Le premier rebond mécanique post-SC. Définit la résistance du range.

**Phase B : Construction de la Cause (Range)**
- Le prix oscille entre la résistance (AR) et le support (SC).
- **ST (Secondary Test)** : Le prix teste le niveau du SC. Règle Algo : `Le Volume du ST DOIT être inférieur au Volume du SC`. (Sinon, annulation du setup).

**Phase C : Le Test Ultime (Le Piège)**
- **Spring (ou Shakeout)** : Le prix casse le support du SC/ST. Règle Algo : Si le prix réintègre le range sur la bougie suivante ou avec une mèche (Upthrust inversé), le Spring est validé. Si le volume est fort, un test à faible volume est requis.

**Phase D : La Tendance dans le Range**
- **SOS (Sign of Strength)** : Le prix remonte vers la résistance avec des barres haussières `Wide Spread + High Volume`.
- **LPS (Last Point of Support)** : Pullback baissier avec l'anomalie `No Supply` (Low Volume). C'est le point d'entrée optimal.

**Phase E : Mark-Up**
- Cassure de la résistance de l'AR (JOC - Jump Across the Creek). L'algorithme passe en mode suivi de tendance.

---

## 🏚️ SECTION 6 — Schéma de Distribution Wyckoff (Checklist Algo Stricte)

L'algorithme doit valider ces événements dans l'ordre chronologique exact pour autoriser un setup de vente (Short) majeur.

**Phase A : Arrêt de la tendance haussière**
- **PSY (Preliminary Supply)** : Afflux de `High Volume` sur barres haussières qui bloquent le prix.
- **BC (Buying Climax)** : Détecté via les règles SOW (Volume extrême + Close bas). Définit la résistance absolue.
- **AR (Automatic Reaction)** : La première chute mécanique post-BC. Définit le support du range.

**Phase B : Construction de la Cause**
- **ST (Secondary Test)** : Test du niveau du BC. Règle Algo : `Le Volume du ST DOIT être inférieur au Volume du BC`.

**Phase C : Le Test Ultime (Le Piège)**
- **UTAD (Upthrust After Distribution)** : Le prix casse la résistance du BC. Règle Algo : Validation par le signal SOW `Upthrust` (clôture basse immédiate).

**Phase D : La Tendance dans le Range**
- **SOW (Sign of Weakness)** : Le prix chute vers le support avec des barres baissières `Wide Spread + High Volume`.
- **LPSY (Last Point of Supply)** : Rebond haussier anémique avec le signal `No Demand` (Low Volume). Point d'entrée short optimal.

**Phase E : Mark-Down**
- Cassure du support avec volume. L'algorithme passe en mode suivi de tendance baissière.

---

## 🚫 SECTION 7 — Règles d'Invalidation Globales (Kill-Switches)

L'agent IA doit rejeter tout signal si l'une de ces conditions est remplie :

**1. Règle du Background (Contexte)**
- Ne JAMAIS valider un signal "No Demand" (SOW) si la tendance de fond (Timeframe supérieur) est fortement haussière sans signe préalable de Distribution (Buying Climax).
- Ne JAMAIS valider un signal "No Supply" (SOS) en plein milieu d'une chute libre avec un volume en constante augmentation.

**2. Règle de l'Effort sans Confirmation**
- Un signal de type "Push Through Supply" (SOS) n'est validé que si la bougie suivante ne clôture pas en dessous du Low de la bougie de cassure. Si elle clôture en dessous, c'est un "Upthrust" (SOW).

**3. Règle de l'Absorption Échouée**
- Si un "Stopping Volume" (SOS) est détecté, le plus bas de cette bougie devient une ligne de défense de la Smart Money. Si une bougie ultérieure clôture sous ce niveau avec un "High Volume", le scénario haussier est détruit à 100 %.


## 🤖 SECTION 8 — Catalogue Complet des Patterns VSA Avancés

### 8.1 Pseudo Upthrust

**Définition :**
Un Pseudo Upthrust est une tentative de cassure haussière qui échoue, mais SANS le volume extrême caractéristique d'un vrai Upthrust. C'est une faiblesse masquée : le marché manque d'énergie pour monter.

**Règles de détection visuelle :**
- Le High de la barre dépasse une résistance ou le High précédent
- La barre clôture LOW (dans le tiers inférieur)
- Volume LOW ou AVERAGE (pas ultra-high)
- Longue mèche supérieure visible

**Règle mathématique :**
```
Condition_1 : High > High_précédent (cassure de niveau)
Condition_2 : Close_position < 0.33 (clôture dans le tiers bas)
Condition_3 : Volume < SMA(Volume, 20) * 1.5 (pas de volume fort)
```

**Signification :**
Absence d'intérêt des acheteurs. Si le marché ne peut même pas monter sur volume faible, c'est que la Smart Money ne supporte pas la hausse. Signal de faiblesse modéré (SOW secondaire).

**Contexte d'application :**
- En Phase B ou C de Distribution : confirme que les institutions ne soutiennent plus.
- Lors d'un rebond dans une tendance baissière.
- Exemple Forex : EUR/USD rebondit vers une résistance H4, forme un Pseudo Upthrust → entrée short.

---

### 8.2 Reverse Upthrust (Reverse Thrust)

**Définition :**
Le pendant baissier du Test VSA. Le prix plonge sous un support, mais clôture HIGH avec un volume faible. Signale une absence d'offre à ces niveaux bas.

**Règles de détection visuelle :**
- Le Low de la barre perce un support ou le Low précédent
- La barre clôture HIGH (tiers supérieur)
- Volume LOW
- Longue mèche inférieure visible

**Règle mathématique :**
```
Condition_1 : Low < Low_précédent (cassure de support)
Condition_2 : Close_position > 0.67 (clôture dans le tiers haut)
Condition_3 : Volume < SMA(Volume, 20) * 0.8
```

**Signification :**
Test réussi à la baisse : les vendeurs ne sont pas présents. Signal haussier (SOS secondaire). Souvent observé avant un Spring ou en Phase D d'Accumulation lors d'un LPS.

**Contexte :**
- Souvent confondu avec un Spring faible → utiliser le contexte de Phase Wyckoff pour distinguer.

---

### 8.3 Squat (Barre de compression)

**Définition :**
Une barre avec un volume ÉLEVÉ mais un spread NARROW. C'est la définition pure de l'Effort sans Résultat. La Smart Money absorbe toute l'activité sans laisser le prix avancer.

**Règles de détection visuelle :**
- Barre de petite taille (corps et mèches étroits)
- Volume extrêmement élevé sur cette barre
- La barre semble "compressée" visuellement

**Règle mathématique :**
```
Condition_1 : Spread < ATR(14) * 0.75 (narrow spread)
Condition_2 : Volume > SMA(Volume, 20) * 2.0 (ultra-high volume)
```

**Signification selon le contexte :**
- **Squat haussier** (en bas de range) : absorption de l'offre finale, prélude à une hausse.
- **Squat baissier** (en haut de range) : absorption de la demande finale, prélude à une chute.

**Exemple :**
Un Squat qui apparaît après une série de bougies baissières sur le Gold (XAU/USD) en D1 → fort signal de retournement haussier si contexte d'Accumulation.

---

### 8.4 Inverse Squat

**Définition :**
Le contraire du Squat : volume FAIBLE sur une barre avec un WIDE Spread. Le prix bouge beaucoup mais sans participation. Souvent un mouvement manipulé ou un "thin market" (marché peu liquide).

**Règle mathématique :**
```
Condition_1 : Spread > ATR(14) * 1.5 (wide spread)
Condition_2 : Volume < SMA(Volume, 20) * 0.8 (low volume)
```

**Signification :**
- Mouvement haussier ou baissier non confirmé. Probabilité élevée de retournement immédiat.
- En VSA : un Inverse Squat haussier (barre verte wide spread + low volume) = No Demand étendu → signal de vente.

---

### 8.5 Bag Holding (Piège à Bulls / Bears)

**Définition :**
Le Bag Holding est un pattern 2-barres ou multi-barres où la Smart Money "laisse le sac" aux traders retail. Des traders acheteurs (ou vendeurs) sont piégés dans des positions perdantes.

**Types :**

**Bag Holding Haussier (piège à vendeurs) :**
- Barre 1 : Barre baissière, Wide Spread, High Volume, Close Low (semble forte à la baisse)
- Barre 2 : Le prix remonte immédiatement au-dessus du High de la Barre 1, Close High

**Règle mathématique :**
```
Barre_1 : direction = baissier, Spread > ATR*1.5, Volume > SMA*1.5, Close < 0.33
Barre_2 : Close > High(Barre_1) ET Close_position > 0.67
```

**Signification :**
Les vendeurs piégés sur Barre 1 subissent des pertes immédiates. Pression de rachat forcé (short squeeze). Signal de force majeur.

**Bag Holding Baissier (piège à acheteurs) :**
- Inverse : barre haussière forte suivie d'une barre clôturant sous le Low de la première.

---

### 8.6 Shakeout (Secousse)

**Définition :**
Mouvement brusque et artificiel qui fait sortir les mains faibles (stop-loss retail) avant la vraie tendance. Version agressive du Spring en Accumulation.

**Règles de détection :**
- Chute soudaine sous un support majeur (Low du range, EQL visible)
- Barre baissière, Wide ou Ultra-Wide Spread
- Volume Ultra-High (l'absorption se fait ici)
- Récupération rapide : la barre suivante ou les 2 suivantes récupèrent tout le terrain perdu

**Règle mathématique :**
```
Condition_1 : Low < SupportMajeur (cassure du support)
Condition_2 : Volume > SMA(Volume,20) * 2.5
Condition_3 : Close(t+1) > Open(t) OU Close(t+1) > Close(t) * 1.005
Condition_4 : Prix réintègre le range en < 3 barres
```

**Signification :**
Purge agressive des stops. Très haute probabilité de continuation haussière. Souvent confondu avec un vrai break → utiliser la récupération rapide comme filtre.

---

### 8.7 Shake and Rally

**Définition :**
Pattern combiné : un Shakeout immédiatement suivi d'une barre haussière forte (SOS). Combinaison très fiable en Phase C d'Accumulation.

**Détection :**
- Barre 1 (Shakeout) : baissière, Wide Spread, Ultra-High Volume, Close Low ou Middle
- Barre 2 (Rally) : haussière, Wide Spread, High Volume, Close High

**Signification :**
La Smart Money a absorbé toute l'offre et lance immédiatement la distribution des positions. Signal d'achat de très haute probabilité.

---

### 8.8 Absorption (Volume d'Absorption)

**Définition :**
Une série de barres (2 à 5) avec un volume cumulé très élevé mais un prix qui n'avance pas. Les institutions "absorbent" l'offre ou la demande sans laisser le prix progresser.

**Règles de détection :**
- 2 à 5 barres consécutives dans la même direction
- Volume élevé ou ultra-élevé sur chaque barre
- Progression nette du prix : quasi nulle (range étroit entre la 1ère et dernière barre)

**Règle mathématique :**
```
N = 2 à 5 barres
Condition_1 : Sum(Volume, N) > N * SMA(Volume,20) * 1.5
Condition_2 : abs(Close_N - Open_1) < ATR(14) * 0.5
```

**Signification :**
- Absorption haussière (en bas de range) : institutions achètent tout ce qui est vendu → hausse imminente.
- Absorption baissière (en haut de range) : institutions vendent tout ce qui est acheté → chute imminente.

---

## 🎭 SECTION 9 — Le Composite Man / Composite Operator

### 9.1 Définition de base

Le "Composite Man" (Richard Wyckoff) ou "Composite Operator" est un concept pédagogique représentant la **totalité des intérêts institutionnels** agissant sur le marché comme une seule entité coordonnée.

Pour l'agent IA : traiter toutes les anomalies de volume/prix comme les actions intentionnelles d'une seule entité dont l'objectif est de maximiser ses profits en achetant bas et vendant haut, au détriment des traders retail.

### 9.2 Les 5 règles du Composite Man (selon Wyckoff)

**Règle 1 : Il planifie ses campagnes à l'avance**
- Les grandes phases d'Accumulation et Distribution peuvent durer des semaines ou mois.
- Un agent IA doit analyser des timeframes supérieurs (W1, MN) pour identifier les phases en cours.

**Règle 2 : Il attire le public dans les mauvaises directions**
- Il crée des cassures fausses (Springs, Upthrusts) pour déclencher les ordres retail.
- Règle algo : toute cassure suivie d'une réintégration dans les 3 barres = manipulation potentielle.

**Règle 3 : Il absorbe toute la supply avant de monter**
- Aucun grand mouvement haussier ne commence sans absorption préalable visible sur les charts (Selling Climax, Stopping Volume, Shakeouts).
- Un markup sans SC ou Stopping Volume préalable est suspect.

**Règle 4 : Il distribue au sommet pendant que le public achète**
- Le Buying Climax survient quand la presse annonce de bonnes nouvelles et que le retail est euphorique.
- Signal : Volume extrême + Close moyen ou bas sur une barre haussière au sommet d'une tendance.

**Règle 5 : Il contrôle le timing par les news**
- Les annonces économiques (NFP, CPI, FOMC) sont souvent utilisées comme déclencheurs.
- En Forex : les grands mouvements post-news avec retournement immédiat = action du Composite Man.

### 9.3 Cycle complet du Composite Man

```
Phase 1 : ACCUMULATION
  Composite Man achète en secret pendant que le retail panique (post-chute)
  Outils : Selling Climax, Shakeouts, Springs, absorption silencieuse

Phase 2 : MARK-UP
  Composite Man laisse monter le prix et invite le public à acheter
  Signes : barres haussières propres, volume croissant modéré, peu de corrections

Phase 3 : DISTRIBUTION
  Composite Man vend ses positions au retail euphorique
  Outils : Buying Climax, Upthrusts, UTAD, absorption de la demande

Phase 4 : MARK-DOWN
  Composite Man laisse chuter le prix (voire shorte activement)
  Signes : barres baissières larges, volumes croissants, rebonds faibles (No Demand)
```

### 9.4 Détection IA du cycle

L'agent doit maintenir une **variable d'état du cycle** :
```
état_cycle ∈ {ACCUMULATION, MARKUP, DISTRIBUTION, MARKDOWN, INDÉFINI}
```

Transitions :
- `MARKDOWN → ACCUMULATION` : détection d'un Selling Climax ou Stopping Volume
- `ACCUMULATION → MARKUP` : cassure haussière avec volume (JOC - Jump Over the Creek)
- `MARKUP → DISTRIBUTION` : détection d'un Buying Climax
- `DISTRIBUTION → MARKDOWN` : cassure baissière avec volume (Break of Ice)

---

## 📏 SECTION 10 — Lecture Détaillée du Spread

### 10.1 Ultra Wide Spread (UWS)

**Définition :**
`Spread > ATR(14) * 2.0` (paramétrable selon l'instrument)

**Signification selon direction et volume :**

| Direction | Volume | Close | Signal | Nom |
|---|---|---|---|---|
| Haussière | Ultra-High | High | SOS fort | Buying Power / SOS |
| Haussière | Ultra-High | Low/Middle | SOW fort | Buying Climax / fin de hausse |
| Baissière | Ultra-High | Low | SOW / SC | Selling Climax / chute finale |
| Baissière | Ultra-High | High/Middle | SOS fort | Stopping Volume / absorption |
| Haussière | Low | High | SOW | Inverse Squat haussier (piège) |
| Baissière | Low | Low | SOS suspect | Inverse Squat baissier (piège) |

### 10.2 Wide Spread (WS)

**Définition :**
`ATR(14) * 1.5 < Spread ≤ ATR(14) * 2.0`

**Règle générale :**
Un Wide Spread avec High Volume dans le sens de la tendance = confirmation de tendance.
Un Wide Spread avec Low Volume = mouvement non confirmé, probabilité de retournement.

### 10.3 Average Spread (AS)

**Définition :**
`ATR(14) * 0.75 ≤ Spread ≤ ATR(14) * 1.5`

**Signification :**
Activité normale du marché. Pas de signal VSA fort en isolation. Utiliser en combinaison avec d'autres barres.

### 10.4 Narrow Spread (NS)

**Définition :**
`ATR(14) * 0.4 ≤ Spread < ATR(14) * 0.75`

**Signification selon volume :**

| Volume | Signal | Interprétation |
|---|---|---|
| Low | No Supply (haussier) OU No Demand (baissier) | Absence d'intérêt professionnel contre la tendance |
| Average | Consolidation neutre | Attendre une direction |
| High | Squat (absorption) | Smart Money absorbe — attention au retournement |
| Ultra-High | Squat extrême | Retournement imminent très probable |

### 10.5 Ultra Narrow Spread (UNS)

**Définition :**
`Spread < ATR(14) * 0.4`

**Signification :**
Barre "doji" fonctionnelle en VSA. Indécision totale ou manipulation de fourchette.
- Avant un événement macro majeur (NFP, FOMC) : attente normale.
- En milieu de tendance avec High Volume : manipulation / absorption silencieuse.

---

## 🎯 SECTION 11 — Règles de Close Position (Signification Complète)

La position de clôture dans le corps de la barre est l'indicateur de QUI a gagné la bataille de cette période.

### 11.1 Close High (0.67 – 1.00)

**Calcul :**
```
Close_position = (Close - Low) / (High - Low)
Close High si Close_position >= 0.67
```

**Signification :**
Les acheteurs ont dominé toute la période. Les vendeurs ont été repoussés. L'énergie haussière est intacte à la clôture.

**En combinaison avec :**
- Wide Spread + High Volume = forte demande institutionnelle (SOS majeur)
- Narrow Spread + Low Volume = absence de vendeurs (No Supply)
- Wide Spread + Low Volume = Inverse Squat (faible fiabilité, mouvement suspect)

### 11.2 Close Middle (0.33 – 0.67)

**Calcul :**
```
Close Middle si 0.33 < Close_position < 0.67
```

**Signification :**
Indécision relative. Ni les acheteurs ni les vendeurs n'ont pris le contrôle complet.

**En combinaison :**
- Wide Spread + High Volume + Close Middle = absorption en cours (transition possible)
- Narrow Spread + Low Volume + Close Middle = stagnation, context-dependent

### 11.3 Close Low (0.00 – 0.33)

**Calcul :**
```
Close Low si Close_position <= 0.33
```

**Signification :**
Les vendeurs ont dominé. Les acheteurs ont été repoussés. Énergie baissière à la clôture.

**En combinaison :**
- Wide Spread + High Volume + Close Low = forte offre institutionnelle (SOW majeur)
- Narrow Spread + Low Volume + Close Low = No Demand (absence d'acheteurs)
- Wide Spread + Low Volume + Close Low = Inverse Squat baissier (suspect)

### 11.4 Règle des Mèches (Wicks)

Les mèches révèlent des rejets :
- **Longue mèche haute** : les acheteurs ont tenté mais ont été repoussés → offre présente en haut
- **Longue mèche basse** : les vendeurs ont tenté mais ont été repoussés → demande présente en bas
- **Deux longues mèches (doji étendu)** : combat intense, résultat neutre

**Seuil algo pour mèche "longue" :**
```
Wick_ratio = Wick_length / Spread
Longue mèche si Wick_ratio > 0.4
```

---

## ⚡ SECTION 12 — Effort vs Résultat : Catalogue Complet des Divergences

La Loi de l'Effort et du Résultat est le cœur algorithmique de la VSA. L'agent doit classifier chaque barre dans l'une des catégories suivantes.

### 12.1 Effort = Résultat (Normal / Confirmatoire)

```
High Volume + Wide Spread (dans la même direction) = confirmation
Low Volume + Narrow Spread = manque d'intérêt général, neutre
```

**Signification :**
Pas d'anomalie. Le marché se comporte normalement. L'agent ne génère pas de signal spécifique.

### 12.2 Effort >> Résultat (Absorption — Signal de Retournement)

```
Ultra-High Volume + Narrow Spread = Squat
Ultra-High Volume + Average Spread = Absorption partielle
```

**Signification :**
Les institutions absorbent activement le flux d'ordre dans la direction opposée. La divergence est proportionnelle à la force du signal.

**Calcul du "Divergence Score" :**
```
Divergence_Score = Volume_ratio / Spread_ratio
où Volume_ratio = Volume / SMA(Volume, 20)
et Spread_ratio = Spread / ATR(14)

Si Divergence_Score > 3.0 → signal fort (Squat majeur)
Si Divergence_Score > 2.0 → signal modéré
Si Divergence_Score > 1.5 → signal faible
```

### 12.3 Effort << Résultat (Mouvement Non Soutenu — Signal de Faiblesse)

```
Low Volume + Wide Spread = Inverse Squat
```

**Signification :**
Le prix bouge beaucoup sans participation. Ce mouvement est artificiel ou sur marché thin. Probabilité élevée de retournement immédiat.

**Utilisation prioritaire :**
- Inverse Squat haussier en sommet de range → SOW (pas de demande réelle)
- Inverse Squat baissier en fond de range → SOS potentiel (peu de pression vendeuse)

### 12.4 Effort avec Résultat Partiel (Signal Mixte)

```
High Volume + Average Spread
```

**Signification :**
Les institutions participent mais quelqu'un résiste. Signe de bataille en cours. Donner la priorité au contexte (phase Wyckoff) pour interpréter.

### 12.5 Règle de la Série (Multi-Barres Effort vs Résultat)

Pour N barres consécutives dans la même direction :

```
Effort_cumulé = Sum(Volume, N)
Résultat_cumulé = abs(Close_N - Open_1) / ATR(14)
Ratio = Effort_cumulé / (N * SMA(Volume,20)) / Résultat_cumulé

Si Ratio > 2.5 → absorption multi-barres, retournement probable
Si Ratio < 0.5 → mouvement fort et légitime, continuation probable
```

---

## 🌊 SECTION 13 — Supply et Demand selon Wyckoff

### 13.1 Définitions fondamentales

**Supply (Offre) :**
La pression vendeuse des institutions et du public. Elle est mesurable via les barres baissières à High Volume avec Close Low.

**Demand (Demande) :**
La pression acheteuse des institutions et du public. Elle est mesurable via les barres haussières à High Volume avec Close High.

### 13.2 Zones de Supply

**Détection algorithmique d'une Zone de Supply :**
```
Condition_1 : Présence d'une ou plusieurs barres SOW (Upthrust, BC, End of Rising Market)
Condition_2 : Ces barres créent un niveau de prix où l'offre institutionnelle est entrée
Condition_3 : Le prix a réagi à la baisse après ce niveau
Zone_Supply = [Low(barre_SOW), High(barre_SOW)]
```

**Propriétés :**
- Une Zone de Supply reste active tant que le prix ne la dépasse pas en clôture avec High Volume
- Chaque test d'une Zone de Supply qui échoue (No Demand ou Pseudo Upthrust) renforce la zone
- Une Zone de Supply "utilisée" (le prix l'a traversée avec force) perd sa pertinence

### 13.3 Zones de Demand

**Détection algorithmique d'une Zone de Demand :**
```
Condition_1 : Présence d'une ou plusieurs barres SOS (SC, Stopping Volume, Spring)
Condition_2 : Ces barres créent un niveau de prix où la demande institutionnelle est entrée
Condition_3 : Le prix a réagi à la hausse après ce niveau
Zone_Demand = [Low(barre_SOS), High(barre_SOS)]
```

### 13.4 Balance of Supply and Demand

L'agent doit maintenir un score dynamique de l'équilibre :

```
Supply_Score = Cumul des SOW détectés (pondéré par volume) sur N barres
Demand_Score = Cumul des SOS détectés (pondéré par volume) sur N barres
Balance = Demand_Score - Supply_Score

Balance > 0 → Contexte haussier (plus de demande que d'offre)
Balance < 0 → Contexte baissier (plus d'offre que de demande)
Balance ≈ 0 → Équilibre / Range / Indécision
```

### 13.5 Transitions Supply/Demand (Changement de Rôle)

**Support → Résistance (Supply prend le contrôle) :**
- Un ancien niveau de Support cassé devient une Zone de Supply active
- Validation : le prix rebondit sur l'ancien support (devenu résistance) avec un signal No Demand ou Pseudo Upthrust

**Résistance → Support (Demand prend le contrôle) :**
- Un ancien niveau de Résistance cassé devient une Zone de Demand active
- Validation : le prix teste l'ancienne résistance (devenue support) avec un signal No Supply ou Reverse Upthrust

---

## 🏗️ SECTION 14 — Phases Wyckoff Complètes (Version enrichie v3.0)

### 14.1 Schéma d'Accumulation — Événements Complets

**Phase A : Arrêt de la tendance baissière**

| Événement | Règle Algo | Description |
|---|---|---|
| **PS (Preliminary Support)** | High Volume + Close Middle ou High sur barre baissière, après long déclin | Premier signe d'absorption. Ralentit la chute mais ne l'arrête pas. |
| **SC (Selling Climax)** | Ultra-High Volume + Wide/Ultra-Wide Spread + Close Middle ou High | Capitulation finale. Définit le support absolu du range. |
| **AR (Automatic Rally)** | Prix remonte en 3 à 10 barres avec Wide Spread + High Volume | Rebond mécanique post-SC. Définit la résistance du range (Creek). |
| **ST (Secondary Test)** | Prix reteste le niveau du SC avec Volume INFÉRIEUR au SC | Validation que la demande est toujours supérieure à l'offre à ce niveau. |

**Phase B : Construction de la Cause**

| Événement | Règle Algo | Description |
|---|---|---|
| **ST multiples** | Séries de tests du SC (volume décroissant = sain) | Les mains faibles sont progressivement absorbées. |
| **Minor Springs** | Petites cassures du support avec récupération rapide | Tests à faible enjeu de la demande résiduelle. |
| **UA (Upward Action)** | Poussée haussière vers la résistance (Creek), Wide Spread + High Volume | Test de la résistance. Si rejeté = Distribution possible. Si absorbé = Accumulation continue. |
| **SOW** (faible) | No Demand lors des rebonds vers la résistance | Confirme que le range est intact, pas encore de force directionnelle. |

**Phase C : Le Test Ultime**

| Événement | Règle Algo | Description |
|---|---|---|
| **Spring (classique)** | Cassure du support SC/ST + Récupération rapide + Volume faible ou normal | Piège les vendeurs, confirme l'absence d'offre. |
| **Spring (fort)** | Cassure du support + Barre suivante : Wide Spread haussier + High Volume + Close High | Spring avec force immédiate. Le plus fiable. |
| **Shakeout** | Cassure du support + Ultra-High Volume + Récupération en 1-3 barres | Version agressive du Spring. Purge totale. |
| **Test du Spring** | Retour sur le niveau du Spring avec Low Volume + Close High | Confirmation que l'offre est épuisée. Point d'entrée optimal. |
| **LPS_C (Last Point of Support pré-markup)** | No Supply détecté près du support sans Spring visible | Parfois, il n'y a pas de Spring — la demande prend le contrôle en douceur. |

**Phase D : Tendance dans le Range (vers la cassure)**

| Événement | Règle Algo | Description |
|---|---|---|
| **SOS (Sign of Strength)** | Barre haussière Wide Spread + High Volume + Close High, cassure de résistance intermédiaire | Confirmation que la demande l'emporte. |
| **BU (Back-Up)** | Pullback après une SOS, Low Volume, prix ne retombe pas | Rechargement avant la cassure finale. |
| **LPS (Last Point of Support)** | No Supply sur un pullback en Phase D | Point d'entrée institutionnel optimal. Le meilleur entry pour l'agent IA. |
| **JOC (Jump Over the Creek)** | Cassure de la résistance (Creek/AR) + Wide Spread + High Volume + Close High | Début officiel du Mark-Up. |

**Phase E : Mark-Up**

| Événement | Règle Algo | Description |
|---|---|---|
| **BUEC (Back-Up to the Edge of the Creek)** | Pullback post-JOC qui reteste l'ancien Creek (maintenant support) | Test de l'ancienne résistance devenue support. Si Low Volume = entrée parfaite. |
| **Continuation SOS** | Chaque nouveau sommet avec Wide Spread + High Volume | Confirme la tendance haussière en cours. |

---

### 14.2 Schéma de Distribution — Événements Complets

**Phase A : Arrêt de la tendance haussière**

| Événement | Règle Algo | Description |
|---|---|---|
| **PSY (Preliminary Supply)** | High Volume + barre haussière qui ralentit | Première offre institutionnelle apparaît. |
| **BC (Buying Climax)** | Ultra-High Volume + Wide Spread haussier + Close Middle ou Bas | Euphorie retail, distribution institutionnelle maximale. |
| **AR (Automatic Reaction)** | Chute rapide post-BC, barres baissières + High Volume | Définit le support du range (Ice). |
| **ST (Secondary Test)** | Retour vers le BC avec Volume INFÉRIEUR au BC | Confirmation que l'offre institutionnelle reste présente en haut. |

**Phase B : Construction de la Cause**

| Événement | Règle Algo | Description |
|---|---|---|
| **ST multiples** | Tests du BC (volume décroissant à chaque test = sain) | Distribution progressive. |
| **Minor Upthrusts** | Petites cassures de la résistance BC rejetées immédiatement | Tests de la demande résiduelle. |
| **SOW (faibles)** | No Demand lors des rebonds | Confirme la domination de l'offre en haut. |

**Phase C : Le Test Ultime**

| Événement | Règle Algo | Description |
|---|---|---|
| **UTAD (Upthrust After Distribution)** | Cassure de la résistance BC + Close Low immédiat + Volume élevé | Piège final les acheteurs, vide les stops. |
| **Test du UTAD** | Retour sur le niveau du UTAD avec No Demand (Low Volume) | Confirme l'échec de la cassure. Point d'entrée short optimal. |
| **LPSY_C (Last Point of Supply pré-markdown)** | Upthrust faible sans UTAD visible | Distribution en douceur dans certains cas. |

**Phase D : Tendance dans le Range (vers la cassure)**

| Événement | Règle Algo | Description |
|---|---|---|
| **SOW (majeur)** | Barre baissière Wide Spread + High Volume + Close Low, cassure support intermédiaire | Confirmation que l'offre l'emporte. |
| **LPSY (Last Point of Supply)** | Rebond haussier anémique avec No Demand (Narrow Spread + Low Volume) | Dernière chance de shorter avant le Mark-Down. |
| **BOI (Break of Ice)** | Cassure du support (Ice/AR) + Wide Spread Baissier + High Volume + Close Low | Début officiel du Mark-Down. |

**Phase E : Mark-Down**

| Événement | Règle Algo | Description |
|---|---|---|
| **BUEC baissier** | Rebond post-BOI qui reteste l'ancien Ice (maintenant résistance) | Test de l'ancienne résistance devenue résistance. Si No Demand = entrée short parfaite. |
| **Continuation SOW** | Chaque nouveau creux avec Wide Spread + High Volume | Confirme la tendance baissière. |

---

## 🧩 SECTION 15 — Règles de Contexte VSA par Phase Wyckoff

Un même signal VSA a une signification DIFFÉRENTE selon la phase Wyckoff active. L'agent IA ne doit JAMAIS interpréter un signal VSA en isolation.

### 15.1 Matrice Contexte × Signal

| Signal VSA | Phase A Accum | Phase B Accum | Phase C Accum | Phase D Accum | Phase E Mark-Up |
|---|---|---|---|---|---|
| **Stopping Volume** | ✅ SC possible → Fort SOS | 🔄 ST possible → Modéré | 🔄 Test Spring → Modéré | ❌ Trop tardif | ❌ Hors contexte |
| **No Supply** | ⚠️ Prématuré | ✅ SOS modéré dans le range | ✅ Test du Spring confirmé | ✅ LPS confirmé — Entrée | ✅ Pullback haussier — Entrée |
| **No Demand** | ❌ Hors contexte | ⚠️ Rebond rejeté (sain pour range) | ⚠️ Si après Spring = suspect | ❌ Invalide la Phase D | ⚠️ Légère correction |
| **Upthrust** | ❌ Hors contexte | ✅ UA rejeté = range intact | ⚠️ Possible faux signal | ❌ Invalide le setup | ❌ Correction |
| **Spring** | ❌ Trop tôt | ❌ Minor Spring = signal faible | ✅ LE signal clé | ❌ Tardif | ❌ Hors contexte |
| **Push Through Supply** | ❌ | ❌ | ❌ | ✅ SOS confirmé | ✅ Continuation |

| Signal VSA | Phase A Distrib | Phase B Distrib | Phase C Distrib | Phase D Distrib | Phase E Mark-Down |
|---|---|---|---|---|---|
| **Buying Climax** | ✅ BC clé → Fort SOW | 🔄 ST possible | ❌ | ❌ | ❌ |
| **No Demand** | ⚠️ Prématuré | ✅ SOW modéré | ✅ Confirme UTAD | ✅ LPSY confirmé — Short | ✅ Rebond baissier — Short |
| **Upthrust** | ✅ ST ou UTAD précoce | ✅ Minor UT | ✅ UTAD clé | ❌ Tardif | ❌ |
| **No Supply** | ❌ | ⚠️ Rebond sain | ⚠️ Faux signal possible | ❌ Invalide | ⚠️ Légère correction |

### 15.2 Règles de Override (Annulation de Signal)

1. **No Demand annulé** si le Background multi-TF est fortement haussier (tendance primaire haussière, pas de BC visible).
2. **No Supply annulé** si le Background est fortement baissier (tendance primaire baissière, pas de SC visible).
3. **Spring invalidé** si le Volume au moment du Spring est Ultra-High SANS récupération dans les 3 barres suivantes.
4. **UTAD invalidé** si le prix continue à monter pendant 5+ barres après la cassure → ce n'était pas une manipulation, c'est une vraie cassure.

---

## 🔗 SECTION 16 — Confluences VSA avec Niveaux Techniques

L'agent IA doit augmenter le score d'un signal VSA selon les confluences présentes.

### 16.1 Confluences avec Supports/Résistances Statiques

**Score de confluence :**
```
+2 points : Signal VSA sur un niveau de support/résistance majeur (PDH, PDL, EQH, EQL)
+1 point  : Signal VSA sur un niveau de support/résistance mineur (récent)
+3 points : Signal VSA sur un ancien support retesté comme résistance (ou inverse)
```

**Règle de validation :**
Un signal No Supply sur un support majeur (Ex : PDL sur H1 en contexte d'Accumulation) = signal de haute probabilité.
Un No Supply en plein milieu de nulle part (pas de niveau technique) = faible probabilité.

### 16.2 Confluences avec Niveaux Psychologiques

**Niveaux ronds :**
- Forex : X.XX00, X.XX50
- Score additionnel : +1 point si le signal VSA est sur ou très proche d'un niveau rond.

### 16.3 Confluences avec des Zones VSA Historiques

**Règle de la Zone de Volume Historique :**
```
Si un signal VSA (SC, BC, Upthrust, Spring) s'est produit à un niveau historiquement
→ Ce niveau devient une Zone VSA active
→ Chaque retour du prix sur cette zone = scoring +2 si un signal VSA se reproduit
```

### 16.4 Confluences avec les Structures de Marché

**Confluence avec cassures de structure (BOS/CHoCH) :**
- Un Push Through Supply + BOS haussier sur H1 = confluence haute probabilité
- Un Upthrust + CHoCH baissier sur H4 = confluence haute probabilité

**Confluence avec FVG/Imbalances :**
- Un No Supply dans un FVG haussier non comblé = signal ultra-fort (double absence d'offre)
- Un No Demand dans un FVG baissier non comblé = signal ultra-fort

### 16.5 Confluence Temporelle

Ajouter au score si le signal VSA se produit pendant :
- Une session de haute liquidité (London Open, NY Open) : +1 point
- Une macro algorithmique ICT (08:50-09:10, 10:50-11:10 NY) : +1 point
- Un jour à haute probabilité directionnelle (mardi, mercredi) : +1 point

### 16.6 Confluence avec les "Local Supports / Mini Shelves"

**Définition** : Un "support local" est le plus bas de la première petite correction (pullback) après qu'une jambe de tendance (swing) a été établie. Ce n'est pas une zone de demande majeure, mais un "rebord" (shelf) mineur qui a de la valeur dans un contexte de tendance.

**Règle de détection algorithmique** :
1. Identifier le plus bas d'un pullback (retracement) qui précède la reprise de la tendance.
2. Ce niveau devient un "support local".

**Confluence** :
- Si un signal No Supply ou un Reverse Upthrust se produit exactement sur un support local, la probabilité d'un rebond est accrue.
- Un rejet de ce niveau (marqué par une longue mèche basse à faible volume) est un signal d'entrée dans la direction de la tendance principale.

---

## 🧠 SECTION 17 — Checklists Mathématiques et Scoring Agent IA

### 17.1 Système de Scoring Global

L'agent attribue un score à chaque signal VSA détecté. Ce score détermine la confiance d'un trade.

```
SCORE_BASE :
  Signal SOS confirmé (1 règle) : +3 points
  Signal SOW confirmé (1 règle) : +3 points

BONUS CONTEXTE :
  Phase Wyckoff correcte pour le signal : +3 points
  Phase Wyckoff ambiguë mais compatible : +1 point
  Phase Wyckoff incorrecte : -5 points (annulation recommandée)

BONUS CONFLUENCE :
  Sur niveau technique majeur : +2 points
  Sur zone VSA historique : +2 points
  Sur FVG / Imbalance : +2 points
  Sur niveau rond : +1 point

BONUS MULTI-SIGNAL :
  2 signaux VSA dans la même direction en < 5 barres : +2 points
  3+ signaux VSA dans la même direction : +4 points

BONUS TIMING :
  Signal pendant Killzone (London/NY) : +1 point
  Signal pendant Macro algorithmique : +1 point

PÉNALITÉS :
  Volume atypique pour l'instrument (ex: vendredi soir Forex) : -2 points
  Signal contre tendance HTF sans BC/SC préalable : -3 points
  Signal non suivi d'une confirmation dans les 3 barres : -2 points

SEUILS D'ACTION :
  Score >= 10 : Entrée de haute confiance
  Score 7–9  : Entrée valide, taille de position réduite
  Score 4–6  : Signal à surveiller, pas d'entrée immédiate
  Score < 4  : Ignorer le signal
```

### 17.2 Checklist Complète Pre-Trade (Agent IA)

```
[PRE_TRADE_VSA_CHECK]

ÉTAPE 1 — Background (HTF)
  □ Quelle est la tendance sur W1/D1 ?
  □ Y a-t-il un SC ou BC visible sur W1/D1 ? (Phase Wyckoff HTF)
  □ La phase Wyckoff HTF est-elle compatible avec la direction du signal ?

ÉTAPE 2 — Phase Wyckoff (TF d'analyse)
  □ Quelle phase est active (A/B/C/D/E) ?
  □ Les événements Wyckoff sont-ils détectés dans le bon ordre ?
  □ Le signal est-il attendu pour cette phase ?

ÉTAPE 3 — Signal VSA (Barre de signal)
  □ Volume : Low / Average / High / Ultra-High ?
  □ Spread : Narrow / Average / Wide / Ultra-Wide ?
  □ Close position : Low / Middle / High ?
  □ Effort vs Résultat : Normal / Divergence ?
  □ Signal VSA identifié : quel nom ?

ÉTAPE 4 — Confluence
  □ Est-on sur un niveau technique (support/résistance, zone VSA historique) ?
  □ Y a-t-il un FVG ou une imbalance à ce niveau ?
  □ Niveau rond présent ?
  □ Timing (session, macro) ?

ÉTAPE 5 — Confirmation (barres post-signal)
  □ La barre suivante confirme-t-elle le signal ?
  □ Pas de clôture au-delà du stop invalidant ?
  □ Pas de signal contraire apparu ?

ÉTAPE 6 — Score final
  □ Calcul du score total
  □ Décision : Entrée / Surveillance / Ignorer
```

### 17.3 Mini-Checklist Rapide (1 barre)

```
[QUICK_VSA_BAR_CHECK]
1. Volume_ratio = Volume / SMA(Volume, 20)
2. Spread_ratio = Spread / ATR(14)
3. Close_pos = (Close - Low) / (High - Low)
4. Divergence_Score = Volume_ratio / Spread_ratio

Si Divergence_Score > 2.0 ET Close_pos > 0.67 → SOS (absorption haussière)
Si Divergence_Score > 2.0 ET Close_pos < 0.33 → SOW (absorption baissière)
Si Divergence_Score < 0.5 ET Close_pos > 0.67 → Inverse Squat haussier (méfiance)
Si Divergence_Score < 0.5 ET Close_pos < 0.33 → Inverse Squat baissier (méfiance)
Si Volume_ratio < 0.8 ET Spread_ratio < 0.75 ET Close_pos > 0.67 → No Supply
Si Volume_ratio < 0.8 ET Spread_ratio < 0.75 ET Close_pos < 0.33 → No Demand
```

### 17.4 Règle de Confirmation Multi-Barres

Un signal unique peut être un faux signal. L'agent doit attendre une confirmation.

**Confirmation simple** : La bougie suivante ne doit pas invalider le signal. Pour un SOS, la bougie suivante ne doit pas clôturer en dessous du low de la bougie de signal.

**Confirmation forte (Pattern de 3 bougies)** :
- **Haussier** : Bougie 1 (SOS) + Bougie 2 (Pullback bas volume/No Supply) + Bougie 3 (Reprise avec volume).
- **Baissier** : Bougie 1 (SOW) + Bougie 2 (Rebond bas volume/No Demand) + Bougie 3 (Rechute avec volume).

---

## 🚫 SECTION 18 — Règles d'Invalidation Enrichies (v3.0)

### 18.1 Kill-Switches Absolus

1. **Clôture au-delà du SC ou BC** avec High Volume :
   Si une barre clôture EN-DESSOUS du Selling Climax précédent avec High Volume → tout scénario haussier est annulé.

2. **Volume décroissant sur un Mark-Up ou Mark-Down** :
   Si 5 barres consécutives dans la direction de tendance montrent un volume décroissant et des spreads rétrécissants → tendance en épuisement. Réduire les positions et surveiller un retournement.

3. **Upthrust APRÈS un Push Through Supply** :
   Si le prix casse une résistance (Push Through Supply = SOS) MAIS qu'il clôture sous la résistance la barre suivante → le "push" était un piège. Invalider immédiatement le scénario haussier.

4. **No Demand répété sans rebond** :
   3 signaux No Demand consécutifs en Phase D d'Accumulation (supposée) → la phase n'est pas D, mais probablement B ou un faux comptage. Réinitialiser l'analyse Wyckoff.

### 18.2 Règle de "Pollution du Volume"

En Forex, le volume disponible est le Tick Volume (nombre de transactions), pas le volume réel en lots.

Ajustements pour l'agent IA :
- Toujours utiliser `SMA(TickVolume, 20)` comme baseline
- Éviter d'analyser le volume pendant les gaps de weekend ou les heures asiatiques creuses (volume < SMA * 0.3)
- Les annonces majeures (NFP, CPI) créent un "volume spike" artificiel : exclure les 2 barres autour de l'annonce de l'analyse Wyckoff stricte

### 18.3 Règle de Cohérence Multi-Timeframe

```
[MTF_COHERENCE_CHECK]

Signal BUY sur H1 acceptable si :
  □ H4 background haussier OU en Phase C/D d'Accumulation
  □ D1 pas en Mark-Down actif avec SOW récents non résolus

Signal SELL sur H1 acceptable si :
  □ H4 background baissier OU en Phase C/D de Distribution
  □ D1 pas en Mark-Up actif avec SOS récents non résolus

Si contradiction MTF → Ne pas trader, attendre alignement
```

---

## 🧩 SECTION 19 — Événements Critiques Wyckoff Détaillés

### 19.1 Le Spring (Ressort)
**Définition** : Un mouvement en dessous d'un niveau de support (souvent le SC ou un ST) qui est rapidement inversé à la hausse. C'est un piège à vendeurs.

**Détection visuelle** : Le prix casse un support horizontal, puis clôture au-dessus de ce même support dans les 1 à 3 bougies suivantes.

**Signification** : La demande est si forte qu'elle absorbe toute l'offre, même à des prix plus bas. C'est le signal le plus fiable de l'Accumulation.

**Règle mathématique** :
- Barre 1 (Spring) : `Low < Niveau_Support_Majeur`
- Condition de validation : `Close(Barre 3) > Niveau_Support_Majeur`
- Volume préférablement faible ou modéré sur la barre de Spring.

### 19.2 Le Shakeout (Secousse)
**Définition** : Similaire au Spring mais plus violent. C'est une cassure nette et rapide sous le support avec un volume très élevé, suivie d'un retour tout aussi rapide au-dessus du support.

**Détection visuelle** : Une large barre rouge avec un volume massif qui casse le support, immédiatement suivie d'une reprise haussière.

**Signification** : La Smart Money provoque une panique pour faire sortir les derniers vendeurs faibles avant de lancer le mark-up.

### 19.3 L'Upthrust (Poussée)
**Définition** : Un mouvement au-dessus d'un niveau de résistance (souvent le BC ou un ST) qui est rapidement inversé à la baisse. C'est un piège à acheteurs.

**Détection visuelle** : Le prix casse une résistance horizontale, puis clôture en dessous de cette même résistance dans les 1 à 3 bougies suivantes.

**Signification** : L'offre est si forte qu'elle repousse toute nouvelle demande. C'est le signal le plus fiable de la Distribution.

**Règle mathématique** :
- Barre 1 (Upthrust) : `High > Niveau_Résistance_Majeur`
- Condition de validation : `Close(Barre 3) < Niveau_Résistance_Majeur`
- Volume préférablement élevé sur la barre d'Upthrust.

---

## 🛠️ SECTION 20 — Configuration de Trading par Phase

### 20.1 Acheter dans l'Accumulation
- **Entrée agressive** : Sur le Spring en Phase C.
- **Entrée conservative** : Sur le LPS en Phase D, après un premier SOS et un pullback à faible volume.
- **Entrée sur cassure** : Sur le JOC (Jump Over the Creek) en Phase D/E, avec un stop sous l'ancienne résistance.

### 20.2 Vendre dans la Distribution
- **Entrée agressive** : Sur l'Upthrust ou l'UTAD en Phase C.
- **Entrée conservative** : Sur le LPSY en Phase D, après un premier SOW et un rebond à faible volume (No Demand).
- **Entrée sur cassure** : Sur le BOI (Break of Ice) en Phase D/E, avec un stop au-dessus de l'ancien support.

---

## 🔗 SECTION 21 — Tests de Rupture et de Continuation

### 21.1 Test de Rupture
**Définition** : Après une cassure (JOC ou BOI), le prix revient tester le niveau de la cassure (l'ancienne résistance devenue support, ou l'ancien support devenu résistance).

**Règle** : Ce test doit se faire avec un volume faible.

- **Test haussier (BUEC)** : Le prix touche l'ancien Creek par le haut avec un volume faible. C'est un point d'entrée idéal pour rejoindre le mark-up.
- **Test baissier** : Le prix touche l'ancien Ice (support) par le bas avec un volume faible. C'est un point d'entrée idéal pour rejoindre le mark-down.

---

## 📈 SECTION 22 — Analyse des Anomalies de Volume (Approfondissement)

### 22.1 Volume Peak (Pic de Volume)
**Définition** : Une barre avec un volume qui est le plus haut des 20 à 50 dernières périodes.

**Interprétation** :
- **En bas de tendance** : Peut être un Selling Climax (haussier).
- **En haut de tendance** : Peut être un Buying Climax (baissier).
- **Dans un range** : Peut être une absorption (signal de continuation du range ou préparation de la sortie).

### 22.2 Volume Décroissant
**Définition** : Une série de barres où le volume diminue constamment, même si le prix évolue.

**Interprétation** :
- **Dans une tendance** : Le mouvement manque de conviction. C'est un signe d'épuisement. Si le prix continue de monter avec un volume décroissant, c'est un signal de faiblesse (No Demand étendu). Si le prix continue de baisser avec un volume décroissant, c'est un signal de force (No Supply étendu).
- **Après un climax** : C'est sain. Par exemple, des ST réussis après un SC doivent avoir un volume décroissant.

---

## 🌐 SECTION 23 — Intégration Multi-Timeframe (MTF)

L'agent doit maintenir un contexte sur plusieurs périodes.
- **Timeframe Supérieur (HTF)** : Définit la phase Wyckoff principale (ex: D1 en Accumulation).
- **Timeframe Intermédiaire (MTF)** : Définit la structure de tendance et les signaux d'entrée (ex: H4).
- **Timeframe Inférieur (LTF)** : Permet d'affiner l'entrée (ex: M15).

**Règle d'Alignement** :
- Un signal d'achat sur LTF n'est valide que si HTF est en Accumulation ou Mark-Up.
- Un signal de vente sur LTF n'est valide que si HTF est en Distribution ou Mark-Down.
- En cas de divergence de phases entre timeframes (ex: HTF en Distribution, LTF en Accumulation), l'agent doit attendre la résolution. Le HTF l'emporte toujours.

---

## 🛡️ SECTION 24 — Gestion de Position Algorithmique VSA

### 24.1 Placement du Stop Loss
Le stop loss n'est pas placé à un niveau arbitraire, mais derrière une zone de signal VSA.
- **Pour un Long** : Le stop est placé sous le Low du signal (ex: sous le Low du Spring, sous le Low de la LPS, sous le Low du No Supply). Si le signal est un Test (Reverse Upthrust), le stop est sous le low de la barre de test.
- **Pour un Short** : Le stop est placé au-dessus du High du signal (ex: au-dessus du High de l'Upthrust, au-dessus du High de la LPSY).

**Règle d'invalidation** : Si la barre qui suit l'entrée clôture au-delà de ces niveaux avec un volume élevé, le trade est définitivement invalide.

### 24.2 Objectifs de Take Profit (Effet)
Basé sur la Loi de Cause à Effet.
- **Mesure de la Cause** : La hauteur du range d'accumulation ou de distribution (distance entre le support SC et la résistance AR/Creek).
- **Projection** :
    - **Mark-Up** : Objectif = Prix de cassure (JOC) + Hauteur du range.
    - **Mark-Down** : Objectif = Prix de cassure (BOI) - Hauteur du range.
- **Sortie progressive** : L'agent peut programmer des prises de bénéfices partielles à 50% et 100% de l'objectif, en surveillant l'apparition de signaux contraires (ex: un Upthrust en mark-up).

---

## 🧮 SECTION 25 — Score de Confiance Final (Agrégé)

Le score de la Section 17 est enrichi par les éléments ci-dessous pour une décision finale.

`SCORE_FINAL = SCORE_BASE + BONUS_CONTEXTE + BONUS_CONFLUENCE + BONUS_MULTI_SIGNAL + BONUS_TIMING + BONUS_CONFIRMATION - PENALITES`

**BONUS_CONFIRMATION** :
- `+2` : La bougie suivante confirme (ex: Close dans le sens du signal).
- `+4` : Un pattern de 3 bougies (SOS -> Pullback -> Reprise) est formé.
- `-5` : La bougie suivante invalide le signal (faux signal).

**BONUS_MTF** :
- `+5` : La phase du HTF est parfaitement alignée avec le trade.
- `-5` : Le HTF est en contradiction totale avec le trade (ex: trade long alors que HTF en Mark-Down actif).

**SEUILS D'ACTION REVUS** :
- Score >= 15 : Entrée de très haute confiance (risque faible).
- Score 10–14 : Entrée de confiance (risque normal).
- Score 5–9 : Entrée valide avec taille de position réduite.
- Score < 5 : Ignorer le signal.

---

## 📝 SECTION 26 — Cas Particuliers et Limitations (Forex & CFD)

### 26.1 Volume en Forex
**Nature** : Le volume sur les plateformes de retail Forex est un "Tick Volume" (nombre de changements de prix), pas un volume réel de contrats.
**Adaptation** : L'agent considère le Tick Volume comme un proxy fiable de l'activité. Les règles VSA restent valides, car une activité institutionnelle se traduira par une augmentation du Tick Volume.
**Pollution** : Ignorer les pics de volume anormaux pendant les news majeures (NFP, CPI, FOMC) ou les gaps du weekend, car ils ne reflètent pas un processus de marché organique.

### 26.2 Gaps
**Interprétation** :
- Un gap haussier en sortie de range (JOC) avec un volume élevé est un signe de force extrême.
- Un gap comblé rapidement avec un volume élevé est un signe de faiblesse (piège). L'agent doit interpréter le gap comme une barre manquante et analyser la réaction du marché sur les bords du gap.

---

## 🤝 SECTION 27 — Règles Spécifiques au Bot ICT Multi-Agents

Cette section complète l'encyclopédie pour l'intégration dans un système
algorithmique hybride (code pur + Vision IA) couplé à un agent ICT.

---

### 27.1 — Normalisation Inter-Paires (Règle Absolue)

⚠️ RÈGLE CRITIQUE : Ne JAMAIS comparer le volume absolu entre deux paires différentes.

Le volume de XAUUSD, EURUSD, BTCUSD et USOIL ne sont pas comparables
en valeur absolue. Un volume de 1500 ticks sur EURUSD n'a aucune
signification comparée à un volume de 1500 ticks sur XAUUSD.

**Règle algorithmique obligatoire :**
Toujours normaliser le volume par rapport à la SMA(20) DE LA MÊME PAIRE
sur LE MÊME TIMEFRAME avant toute classification.
Volume_ratio = Volume_actuel / SMA(Volume, 20)  ← même paire, même TF
Classification universelle (valable pour TOUTES les paires) :
Volume_ratio < 0.8  → Low Volume
Volume_ratio 0.8–1.2 → Average Volume
Volume_ratio > 1.5  → High Volume
Volume_ratio > 2.5  → Ultra-High Volume

**Conséquence pour l'agent Gemini :**
Lorsque tu analyses un chart, tu ne dois JAMAIS dire "le volume est élevé"
en te basant sur la valeur absolue visible. Tu dois évaluer le volume
relativement aux bougies précédentes visibles sur le même chart.
Un volume "élevé" = barre de volume nettement plus haute que la moyenne
des 20 dernières barres de volume SUR CE MÊME CHART.

---

### 27.2 — VSA autour des News High Impact

Les annonces macroéconomiques majeures créent des pics de volume
artificiels qui ne reflètent pas un processus organique de Smart Money.
L'agent doit détecter et traiter ces situations différemment.

**News classées High Impact (à filtrer) :**
NFP (Non-Farm Payrolls), CPI, PPI, FOMC, BCE, BOE, BOJ,
GDP, Retail Sales, ISM Manufacturing.

**Règles de traitement :**
AVANT la news (bougie N-1 et N-2) :
→ Volume souvent anormalement faible = attente institutionnelle
→ Ne pas interpréter comme No Supply ou No Demand
→ Ignorer ces bougies pour le contexte VSA
PENDANT la news (bougie N) :
→ Volume Ultra-High systématique = artificiel
→ Spread souvent Ultra-Wide = manipulation de liquidité
→ Score VSA réduit de 70% sur cette bougie
→ Ne jamais trader sur cette bougie
APRÈS la news (bougie N+1 et N+2) :
→ C'est ici que le vrai signal VSA apparaît
→ Si N+1 est un Stopping Volume après un spike baissier = signal fort
→ Si N+1 est un No Demand après un spike haussier = signal fort
→ Score VSA normal rétabli à partir de N+3

**Règle d'or post-news :**
Le vrai mouvement institutionnel commence toujours APRÈS la réaction
initiale à la news. La première bougie post-news est souvent un piège
(Upthrust ou Spring artificiel). Attendre la confirmation N+2 minimum.

---

### 27.3 — VSA en Range vs VSA en Tendance

Un même signal VSA a une signification et une force différentes selon
que le marché est en Range ou en Tendance. L'agent doit détecter
le contexte avant d'interpréter le signal.

**Détection algorithmique du contexte :**
RANGE détecté si :
- Prix oscille entre un support et une résistance identifiables
- ATR(14) actuel < ATR(14) moyenne des 50 dernières bougies * 0.8
- Pas de BOS (Break of Structure) récent sur les 20 dernières bougies

TENDANCE détectée si :
- Série de Higher Highs + Higher Lows (haussière)
- Série de Lower Highs + Lower Lows (baissière)
- ATR(14) actuel > ATR(14) moyenne des 50 dernières bougies * 1.0


**Tableau d'interprétation différenciée :**

| Signal VSA | En Range | En Tendance Haussière | En Tendance Baissière |
|---|---|---|---|
| No Supply | Haussier fort (Phase B/C) | Pullback — entrée long | ⚠️ Faible — attendre |
| No Demand | Baissier fort (Phase B/C) | ⚠️ Faible — attendre | Pullback — entrée short |
| Stopping Volume | Possible SC (Phase A) | ⚠️ Retournement possible | ⚠️ Retournement possible |
| Selling Climax | SC Phase A — haussier | Rare — signal fort | Capitulation — haussier |
| Buying Climax | BC Phase A — baissier | Épuisement — baissier | Rare — signal fort |
| Upthrust | Distribution Phase B/C | Correction courte | Rebond piège — short |
| Spring | Accumulation Phase C | Correction profonde | Reversal possible |

**Règle du Range qui se comprime :**
Si sur les 10 dernières bougies en range :
- Les highs baissent progressivement ET
- Les lows montent progressivement ET
- Le volume diminue sur chaque oscillation
→ Compression = breakout imminent dans les 3-5 bougies
→ Surveiller la direction de la cassure avec volume confirmation
→ Score VSA +5 points sur le signal qui accompagne la cassure


---

### 27.4 — Confluences VSA + ICT (Scoring Spécifique)

Cette section définit les confluences entre les signaux VSA et les
concepts ICT de l'Agent 1-4. Chaque confluence augmente le score
final de manière multiplicative car les deux méthodologies confirment
la même zone de manipulation institutionnelle.

**Règle générale :**
Une confluence VSA + ICT signifie que DEUX approches indépendantes
identifient la même zone comme significative. La probabilité de succès
augmente significativement.

**Table des confluences et bonus de score :**
CONFLUENCES HAUSSIÈRES (Long) :
+5 pts → No Supply dans un FVG haussier non comblé
(FVG = zone d'imbalance, No Supply = absence de vendeurs = double vide)
+5 pts → Stopping Volume sur un Order Block haussier
(OB = dernière bougie baissière avant impulsion, SV = absorption = confirmation OB valide)
+5 pts → Selling Climax sous une zone EQL (Equal Lows)
(EQL = liquidité ciblée, SC = Smart Money achète après avoir chassé les stops)
+4 pts → Spring sur une zone de Displacement haussier
(Displacement = mouvement impulsif ICT, Spring = test de la base = MSS + Spring simultané)
+4 pts → No Supply sur un ancien Order Block retesté
(OB retesté + No Supply = double confirmation que la zone tient)
+3 pts → Reverse Upthrust (Test VSA) dans un FVG haussier
(Test = vérification de l'absence d'offre dans une zone de déséquilibre)
CONFLUENCES BAISSIÈRES (Short) :
+5 pts → No Demand dans un FVG baissier non comblé
(FVG baissier = déséquilibre, No Demand = absence d'acheteurs = double confirmation short)
+5 pts → Upthrust sur un Order Block baissier
(OB bearish + Upthrust = piège parfait, Smart Money distribue au niveau institutionnel)
+5 pts → Buying Climax au-dessus d'une zone EQH (Equal Highs)
(EQH = liquidité ciblée, BC = distribution après chasse aux stops haussiers)
+4 pts → UTAD sur une zone de BOS baissier
(BOS = structure cassée, UTAD = dernier piège avant Mark-Down)
+4 pts → No Demand sur un ancien Order Block retesté
(OB bearish retesté + No Demand = zone résistance confirmée par deux méthodes)
+3 pts → Pseudo Upthrust sur une zone de CHoCH
(CHoCH = changement de structure, Pseudo UT = confirmation que la faiblesse est réelle)
PÉNALITÉS DE CONTRADICTION :
-5 pts → Signal VSA haussier dans une zone ICT baissière confirmée
(ex: No Supply sous un OB bearish non mitigé)
-5 pts → Signal VSA baissier dans une zone ICT haussière confirmée
(ex: No Demand au-dessus d'un FVG haussier non comblé)
-3 pts → Signal VSA sans aucune confluence ICT identifiable
(signal isolé = moins fiable)

**Règle de la triple confluence (bonus exceptionnel) :**
Si VSA + ICT + Elliott Wave pointent dans la même direction :
→ Bonus additionnel +8 points sur le score MetaOrchestrator
→ C'est le setup de plus haute probabilité du système
→ Taille de position peut être augmentée à 1.5x le risque normal

---

### 27.5 — Invalidation Temporelle des Signaux VSA

Un signal VSA est ancré dans le temps. Plus on s'éloigne de la bougie
de signal sans que le prix confirme, plus la probabilité diminue.
Le contexte de marché évolue et peut invalider rétroactivement un signal.

**Durées de validité par timeframe :**
Timeframe M5 (Scalp) :
→ Signal valide : 3 bougies maximum après détection
→ Après 3 bougies sans mouvement : score VSA -50%
→ Après 5 bougies sans mouvement : signal annulé
Timeframe M15 (Scalp/Intraday) :
→ Signal valide : 4 bougies maximum
→ Après 4 bougies sans mouvement : score VSA -50%
→ Après 6 bougies sans mouvement : signal annulé
Timeframe H1 (Intraday) :
→ Signal valide : 6 bougies maximum
→ Après 6 bougies sans mouvement : score VSA -50%
→ Après 10 bougies sans mouvement : signal annulé
Timeframe H4 (Daily) :
→ Signal valide : 8 bougies maximum
→ Après 8 bougies sans mouvement : score VSA -50%
→ Après 12 bougies sans mouvement : signal annulé
Timeframe D1 (Weekly) :
→ Signal valide : 10 bougies maximum
→ Après 10 bougies sans mouvement : score VSA -50%
→ Après 15 bougies sans mouvement : signal annulé

**Événements d'invalidation immédiate (indépendamment du temps) :**
Signal haussier annulé immédiatement si :
→ Une bougie clôture EN DESSOUS du Low du signal avec High Volume
→ Un nouveau SOW (No Demand ou Upthrust) apparaît avant confirmation
→ Le prix casse le plus bas des 20 dernières bougies avec volume élevé
Signal baissier annulé immédiatement si :
→ Une bougie clôture AU DESSUS du High du signal avec High Volume
→ Un nouveau SOS (No Supply ou Spring) apparaît avant confirmation
→ Le prix casse le plus haut des 20 dernières bougies avec volume élevé

**Règle de réactivation :**
Un signal annulé par le temps PEUT être réactivé si le prix revient
exactement sur le niveau du signal original avec un nouveau signal VSA
de confirmation. Dans ce cas, le score repart à zéro et le signal est
traité comme nouveau.

---

**Fin de l'Encyclopédie V3.0 — Couverture 100%**