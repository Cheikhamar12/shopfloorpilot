# ShopFloorPilot

[![CI](https://github.com/<ton-compte>/shopfloorpilot/actions/workflows/ci.yml/badge.svg)](https://github.com/<ton-compte>/shopfloorpilot/actions/workflows/ci.yml)

Copilote agentique pour un industriel multi-sites : il répond en langage naturel aux questions
de performance (TRS) et de supply chain, à partir de l'entrepôt de données et de la
documentation technique.

> Statut : semaine 1/10 — socle du dépôt. Données 100 % fictives.

## Démarrage rapide

**Sous Windows : suis le guide pas à pas [`docs/demarrage-windows.md`](docs/demarrage-windows.md)**
(WSL2, Docker Desktop, uv, Make, puis chaque étape avec sa vérification).

Sous Linux ou macOS, avec Docker, [uv](https://docs.astral.sh/uv/) et Make installés :

```bash
uv lock        # 1. fige les versions des dépendances (à commiter)
make install   # 2. installe l'environnement Python et les hooks pre-commit
make up        # 3. démarre Postgres 17 + pgvector et SeaweedFS (S3) ; crée .env au premier lancement
make data      # 4. génère les CSV fictifs dans data/
make check     # 5. ruff + mypy strict + pytest, comme la CI
make help      # toutes les commandes
```

## Données générées

Trois usines (Lyon, Valenciennes, Toulouse), 21 machines, 6 mois de production (janv.–juin 2026).

| Table | Contenu |
| --- | --- |
| `plants`, `machines`, `suppliers` | Référentiels |
| `production_orders` | Un OF par machine et par jour : temps planifié, arrêts, marche, pièces totales et bonnes |
| `downtimes` | Arrêts avec code, catégorie et commentaire opérateur — ~15 % saisis « Autre » |
| `downtime_labels` | Vraie catégorie des arrêts « Autre » (vérité terrain pour le classifieur, semaine 9) |
| `purchase_orders` | Commandes fournisseurs : date promise, date livrée, commandes encore ouvertes |

**Scénario injecté** : le TRS de Lyon chute en mars (~67 % contre ~77 %) parce qu'Aciers du Rhône
livre en retard (manques matière) et que la presse 3 cumule des pannes E-214. C'est la question
de démonstration de l'agent SQL.

Graine fixe : même graine ⇒ mêmes fichiers, octet pour octet (testé).

## Architecture

À venir (semaine 2+). Décisions : [`docs/adr/`](docs/adr/). Journal : [`docs/journal.md`](docs/journal.md).
