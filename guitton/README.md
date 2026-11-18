# GUITTON — XAUUSD

Logiciel de trading de l'or (XAUUSD) uniquement.

```bash
python3 guitton/server.py      # puis ouvrir http://localhost:8800
```

Python 3.9+ suffit, rien à installer.

## Utilisation

1. Renseigne ton capital, ton risque par trade (%) et le levier de ton broker.
2. **Lancer une analyse** : 11 agents tournent (horloge, contexte, actualités, macro dollar/taux, entrée,
   sortie, Time Machine, budget, risque, ticket, alertes) et proposent un trade :
   fourchette d'entrée, stop loss, TP1 (50 %), TP2, lots, perte max.
3. Tu passes l'ordre toi-même chez ton broker, puis tu cliques sur **Je suis rentré sur le marché**.
4. La courbe XAUUSD s'affiche en temps réel et GUITTON te donne les actions à faire pendant le trade :

| Instruction | Quand |
| --- | --- |
| CLÔTUREZ TP1 + METTEZ BE | +1R : ferme 50 %, stop au prix d'entrée |
| SÉCURISEZ 75 % + DÉPLACEZ SL | +1,5R : ferme encore 25 %, stop à +0,5R |
| TP OPEN | TP2 atteint avec un fort élan et plus de 45 min de session : laisse courir, stop au TP1 |
| DÉPLACEZ SL À … | en TP OPEN, à chaque +0,5R supplémentaire |
| OUT / CLOSE ALL | TP2 sans élan, essoufflement en TP OPEN, 1 h sans progression, ou 15 min avant la fin de session |
| TRADE INVALIDE | avant l'entrée : cassure annulée, prix trop loin (+0,5R) ou au stop |
| PROCHE DU STOP | à -0,7R : rappel de ne jamais éloigner le stop |

## Données

- **Cours en direct** : flux public XAU/USD de Swissquote (bid/ask, toutes les secondes).
- **Analyse et historique** : COMEX GC=F sur Yahoo (5 min sur 60 jours, différé d'environ 10 min).
  Les niveaux sont recalés sur le spot avec l'écart mesuré entre les deux.
- Sessions : Londres (range 08:00–08:15 Londres, entrées jusqu'à 12:00) et New York
  (range 08:20–08:35 New York, entrées jusqu'à 12:00), sortie forcée à 16:30.

Aucun ordre n'est envoyé : GUITTON ne se connecte à aucun broker.
Outil éducatif, pas un conseil financier.
