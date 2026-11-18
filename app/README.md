# Trading Desk

Interface locale qui enchaîne les 11 skills `trader-*` du dossier `.claude/skills/`.

```bash
python3 app/server.py        # puis ouvrir http://localhost:8765
```

Python 3.8+ suffit, rien à installer. Chaque analyse tourne dans son propre dossier `app/runs/…/trader/`.
Les réglages (capital, risque, levier) sont enregistrés dans `app/settings.json` (non commité).

**Ordre des étapes :** horloge NYSE → scanner → news → signal d'entrée (cassure du range d'ouverture) →
plan de sortie → Time Machine → taille de position → contrôle du risque → ticket → alertes → analyste SEC.

- Marché fermé : l'analyse est une *répétition* sur la dernière séance à 10h15. Il faut la relancer après 9h50 New York.
- Achat uniquement, actions et ETF américains (or = GLD, argent = SLV, pétrole = USO, bitcoin = IBIT).
- Le levier est un plafond : la taille vient toujours de la perte max au stop.
- Aucun ordre n'est envoyé depuis l'interface. Un ordre passe par Claude (`/trader-broker`), en paper trading, après un « oui » explicite.

Outil éducatif, pas un conseil financier.

## XAUUSD (or spot)

La puce **Or spot XAUUSD** utilise un moteur dédié (`app/xau.py`), parce que les skills `trader-*`
sont prévus pour des actions sur les horaires du NYSE :

- **Données** : contrat à terme or COMEX `GC=F` (Yahoo, 5 min sur 60 jours). Yahoo ne fournit pas
  l'or spot. Entre le prix XAUUSD affiché par ton broker et tous les niveaux sont décalés de l'écart.
- **Sessions** : Londres (range 08:00–08:15 Londres) ou New York COMEX (range 08:20–08:35 New York).
  Entrées jusqu'à 12:00 heure locale, sortie forcée à 16:30.
- **Signal** : première clôture 5 min au-dessus du range → achat ; en dessous → vente.
  Sans signal : deux ordres stop en attente (OCO).
- **Taille** : en lots (1 lot = 100 oz, minimum 0,01). La perte au stop, spread compris, reste sous ton
  risque par trade. La marge (prix × oz / levier broker) est plafonnée à 50 % du capital.
- **Contrôles** : R:R ≥ 1, fenêtre d'entrée, marché ouvert, et en direct un signal ancien est bloqué
  s'il a déjà touché son stop ou son objectif, ou si le cours s'est éloigné de plus de 0,5R.
- **Ticket** : au format MT4/MT5, à saisir toi-même. Rien n'est envoyé.
