.DEFAULT_GOAL := help
SHELL := /bin/bash
COMPOSE := docker compose
RUN := uv run

.PHONY: help env install up buckets down reset logs ps psql data lint format typecheck test test-int check clean

help: ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

env: ## Crée .env à partir de .env.example s'il n'existe pas
	@test -f .env || (cp .env.example .env && echo ".env créé — pense à changer les mots de passe")

install: ## Installe les dépendances et les hooks pre-commit
	uv sync
	$(RUN) pre-commit install

up: env ## Démarre Postgres+pgvector et SeaweedFS (S3), attend qu'ils soient sains
	$(COMPOSE) up -d --wait postgres seaweedfs
	@echo "Postgres : localhost:5432 · S3 : http://localhost:8333 · fichiers : http://localhost:8888"

buckets: ## Liste les buckets S3 de SeaweedFS
	echo "s3.bucket.list" | $(COMPOSE) exec -T seaweedfs weed shell

down: ## Arrête les services (garde les volumes)
	$(COMPOSE) down

reset: ## Arrête les services ET supprime les volumes (repart de zéro)
	$(COMPOSE) down -v

logs: ## Suit les logs des services
	$(COMPOSE) logs -f

ps: ## État des services
	$(COMPOSE) ps

psql: ## Ouvre un shell psql
	$(COMPOSE) exec postgres sh -c 'psql -U $$POSTGRES_USER -d $$POSTGRES_DB'

data: ## Génère les données fictives dans data/ (graine fixe => reproductible)
	$(RUN) shopfloorpilot-datagen --out data --seed 42

lint: ## Lint (ruff)
	$(RUN) ruff check .
	$(RUN) ruff format --check .

format: ## Formate le code
	$(RUN) ruff check --fix .
	$(RUN) ruff format .

typecheck: ## Typage strict (mypy)
	$(RUN) mypy

test: ## Tests unitaires
	$(RUN) pytest -m "not integration" --cov=shopfloorpilot --cov-report=term-missing

test-int: ## Tests d'intégration (nécessite make up)
	$(RUN) pytest -m integration

check: lint typecheck test ## Tout ce que la CI vérifie

clean: ## Supprime caches et données générées
	rm -rf .mypy_cache .ruff_cache .pytest_cache .coverage htmlcov
	find data -mindepth 1 ! -name .gitkeep -delete
