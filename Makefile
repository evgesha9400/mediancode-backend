# Median Code Backend - Makefile
# Run 'make help' to see all available commands

PYTHON := python3
POETRY := poetry
PORT ?= 8001
SEED_USER_EMAIL := aleshiner@mail.ru

.DEFAULT_GOAL := help

# =============================================================================
#  LOCAL DEVELOPMENT
#  Use these commands for day-to-day development on your machine
# =============================================================================

.PHONY: setup
setup: ## First-time setup: install deps, hooks, start DB, run migrations
	@echo "Installing dependencies..."
	@$(POETRY) install
	@$(MAKE) install-hooks
	@echo "Starting PostgreSQL..."
	@docker compose up -d
	@echo "Waiting for database..."
	@sleep 3
	@echo "Running migrations..."
	@$(POETRY) run alembic upgrade head
	@echo ""
	@echo "✓ Setup complete! Run 'make dev' to start the backend."

.PHONY: dev
dev: ## Start backend server with hot reload (localhost:$(PORT))
	@PYTHONPATH=src $(POETRY) run uvicorn api.main:app --reload --host 0.0.0.0 --port $(PORT)

.PHONY: db
db: ## Start PostgreSQL database (Docker)
	@docker compose up -d
	@echo "PostgreSQL running on localhost:5432"

.PHONY: db-stop
db-stop: ## Stop PostgreSQL database
	@docker compose down

.PHONY: db-reset
db-reset: ## Reset database: delete all data, restart, re-migrate
	@docker compose down -v
	@docker compose up -d
	@echo "Waiting for database..."
	@sleep 3
	@$(POETRY) run alembic upgrade head
	@echo "Database reset complete"

.PHONY: test
test: ## Run tests (mirrors CI — all markers, DB tests skipped if no PostgreSQL)
	@$(POETRY) run pytest tests/ -v

.PHONY: test-e2e
test-e2e: ## Run end-to-end tests (requires Docker)
	@$(POETRY) run pytest -m e2e -v

.PHONY: test-codegen
test-codegen: ## Run codegen tests (fast, no DB needed)
	@$(POETRY) run pytest -m codegen

.PHONY: lint
lint: ## Same Ruff checks as CI / git pre-commit (.pre-commit-config.yaml)
	@$(POETRY) run pre-commit run --all-files

# =============================================================================
#  LOCAL DATABASE MIGRATIONS
#  Run against your local PostgreSQL (from docker-compose)
# =============================================================================

.PHONY: migration
migration: ## Create new migration: make migration msg="add users table"
	@$(POETRY) run alembic revision --autogenerate -m "$(msg)"

.PHONY: migrate-up
migrate-up: ## Apply all pending migrations (local)
	@$(POETRY) run alembic upgrade head

.PHONY: migrate-down
migrate-down: ## Rollback last migration (local)
	@$(POETRY) run alembic downgrade -1

.PHONY: migrate-history
migrate-history: ## Show migration history (local)
	@$(POETRY) run alembic history

.PHONY: migrate-current
migrate-current: ## Show current migration version (local)
	@$(POETRY) run alembic current

# =============================================================================
#  SEEDING
#  Seed the Shop API structure into a running backend (requires auth)
# =============================================================================

.PHONY: seed-local
seed-local: ## Seed Shop data into local backend (localhost:$(PORT))
	@PYTHONPATH=src:tests $(POETRY) run python -m seeding --target local --user-email $(SEED_USER_EMAIL)

.PHONY: seed-dev
seed-dev: ## Seed Shop data into dev backend (api.dev.mediancode.com)
	@PYTHONPATH=src:tests $(POETRY) run python -m seeding --target dev --user-email $(SEED_USER_EMAIL)

.PHONY: seed-prod
seed-prod: ## Seed Shop data into prod backend (api.mediancode.com)
	@PYTHONPATH=src:tests $(POETRY) run python -m seeding --target prod --user-email $(SEED_USER_EMAIL)

# =============================================================================
#  UTILITIES
# =============================================================================

.PHONY: clean
clean: ## Remove Python caches and test output
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -name "*.pyc" -delete 2>/dev/null || true
	@find . -name "*.pyo" -delete 2>/dev/null || true
	@find . -name ".pytest_cache" -type d -exec rm -rf {} + 2>/dev/null || true
	@rm -rf tests/output/ 2>/dev/null || true
	@echo "Cleaned"

.PHONY: install-hooks
install-hooks: ## Install git pre-commit hooks (same checks as CI; requires: poetry install)
	@test -d .git || (echo "install-hooks: not a git checkout" >&2 && exit 1)
	@$(POETRY) run pre-commit install --install-hooks
	@echo "Pre-commit installed (see .pre-commit-config.yaml)."

.PHONY: docker-build
docker-build: ## Build Docker image locally (prunes old layers)
	@docker build -t mediancode-backend .
	@docker image prune -f

.PHONY: docker-run
docker-run: ## Run Docker image locally (port $(PORT))
	@docker run -p $(PORT):80 mediancode-backend

# =============================================================================
#  HELP
# =============================================================================

.PHONY: help
help: ## Show this help message
	@echo ""
	@echo "Median Code Backend"
	@echo "==================="
	@echo ""
	@echo "LOCAL DEVELOPMENT:"
	@echo "  make setup           First-time setup: install deps, start DB, run migrations"
	@echo "  make dev             Start backend server with hot reload (localhost:$(PORT))"
	@echo "  make db              Start PostgreSQL database (Docker)"
	@echo "  make db-stop         Stop PostgreSQL database"
	@echo "  make db-reset        Reset database: delete data, restart, re-migrate"
	@echo "  make test            Run tests"
	@echo "  make lint            Ruff format + lint (same as CI)"
	@echo ""
	@echo "LOCAL DATABASE MIGRATIONS (runs against local Docker PostgreSQL):"
	@echo "  make migrate-up      Apply pending migrations"
	@echo "  make migrate-down    Rollback last migration"
	@echo "  make migrate-history Show migration history"
	@echo "  make migration msg=\"...\"  Create new migration file"
	@echo ""
	@echo "SEEDING (SEED_USER_EMAIL=$(SEED_USER_EMAIL)):"
	@echo "  make seed-local      Seed Shop data into local backend"
	@echo "  make seed-dev        Seed Shop data into dev backend"
	@echo "  make seed-prod       Seed Shop data into prod backend"
	@echo ""
	@echo "UTILITIES:"
	@echo "  make install-hooks   Install pre-commit hooks (Ruff; same as CI)"
	@echo "  make clean           Remove Python caches"
	@echo "  make docker-build    Build Docker image"
	@echo "  make docker-run      Run Docker image locally"
	@echo ""
