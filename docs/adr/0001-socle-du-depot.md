# ADR 0001 — Socle du dépôt : stockage local et outillage

- **Date** : 2026-11-23
- **Statut** : proposée (à finaliser en fin de semaine 1)

## Contexte
ShopFloorPilot doit se lancer en une commande (`make up`), sans compte cloud, et préfigurer
la stack de production : SQL + plein texte + vecteurs, et un stockage objet S3 pour les fichiers bruts.
Incident rencontré en semaine 1 : l'image `minio/minio` n'est plus disponible sur Docker Hub
(`pull access denied`), MinIO ayant cessé de distribuer ses images communautaires.

## Options envisagées
1. **Base** : Postgres + pgvector vs base vectorielle dédiée (Qdrant, Weaviate) — À COMPLÉTER
2. **Stockage objet** :
   - MinIO : de facto standard, mais images retirées → plus maintenable.
   - SeaweedFS : Apache 2.0, actif, un seul conteneur (`weed mini`), API S3. Console plus sommaire.
   - Garage : léger, mais mise en place plus longue (configuration + layout).
   - Aucun en local (fichiers dans `data/`) : simple, mais s'éloigne de l'architecture cible.
3. **Outillage Python** : uv + ruff + mypy strict vs Poetry + black + flake8 — À COMPLÉTER

## Décision
Stockage objet : **SeaweedFS**, accédé uniquement via l'API S3 standard (boto3).
Le reste : À COMPLÉTER.

## Conséquences
- Le code ne dépend que de l'API S3 : passer à AWS S3 ou Azure Blob (semaine 10) = changer
  `S3_ENDPOINT` et les identifiants, pas le code.
- Image encore en `latest` : Image figée sur chrislusf/seaweedfs:4.55.
- Leçon : épingler les versions et prévoir un plan B pour chaque dépendance externe.
