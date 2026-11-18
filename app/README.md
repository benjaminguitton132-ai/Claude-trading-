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
