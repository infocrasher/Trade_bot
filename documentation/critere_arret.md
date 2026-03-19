# Critère d'Arrêt — TakeOption Bot

**Date de rédaction : 2026-03-19**
**Statut : ACTIF — applicable dès le premier trade paper avec spread simulé**

---

## Règles d'arrêt non négociables

### 1. Profit Factor insuffisant après 200 trades
**Condition** : Si après 200 trades paper avec spread réaliste simulé, le Profit Factor est < 1.1
**Action** : Arrêt total du bot. Re-évaluation complète depuis zéro (fondamentaux ICT, seuils, architecture).
**Justification** : PF < 1.1 sur 200 trades = pas d'edge exploitable. Les frais réels (commissions, slippage) ramèneraient le PF sous 1.0.

### 2. SQN trop bas après 100 trades
**Condition** : Si le System Quality Number (SQN) est < 0.5 après 100 trades
**Action** : Arrêt total. Même re-évaluation que le critère 1.
**Justification** : SQN < 0.5 = système non tradeable selon Van Tharp. Le signal est indistinguable du bruit.
**Formule** : SQN = sqrt(N) × (moyenne des R-multiples) / (écart-type des R-multiples)

### 3. Max Drawdown excessif
**Condition** : Si le drawdown cumulé dépasse 25% du capital initial à n'importe quel moment
**Action** : Arrêt immédiat sans attendre 200 trades.
**Justification** : Un drawdown de 25% nécessite un gain de 33% pour revenir à l'équilibre. Au-delà de ce seuil, la probabilité de recovery diminue exponentiellement.

---

## Comment mesurer

- **Profit Factor** = somme des gains / somme des pertes (en pips, spread inclus)
- **SQN** = sqrt(N) × mean(R) / std(R) où R = PnL / risque initial par trade
- **Drawdown** = (pic de capital - creux) / pic de capital × 100

## Ce document est un engagement

Ces critères ne doivent pas être modifiés rétroactivement pour justifier la continuation du bot.
Si un critère est atteint, l'action correspondante est exécutée sans discussion.
