# Median Code Backend - Makefile
# Run 'make help' to see all available commands

PYTHON := python3
POETRY := poetry
PORT ?= 8001

.DEFAULT_GOAL := help

# =============================================================================
#  LOCAL DEVELOPMENT
#  Use these commands for day-to-day development on your machine
# =============================================================================

.PHONY: setup
setup: ## First-time setup: install deps, start DB, run migrations
	@echo "Installing dependencies..."
	@$(POETRY) install
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
test: ## Run tests
	@$(POETRY) run pytest tests/ -v

.PHONY: test-codegen
test-codegen: ## Run codegen tests (fast, no DB needed)
	@$(POETRY) run pytest -m codegen

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

.PHONY: docker-build
docker-build: ## Build Docker image locally (prunes old layers)
	@docker build -t median-code-backend .
	@docker image prune -f

.PHONY: docker-run
docker-run: ## Run Docker image locally (port $(PORT))
	@docker run -p $(PORT):80 median-code-backend

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
	@echo ""
	@echo "LOCAL DATABASE MIGRATIONS (runs against local Docker PostgreSQL):"
	@echo "  make migrate-up      Apply pending migrations"
	@echo "  make migrate-down    Rollback last migration"
	@echo "  make migrate-history Show migration history"
	@echo "  make migration msg=\"...\"  Create new migration file"
	@echo ""
	@echo "UTILITIES:"
	@echo "  make clean           Remove Python caches"
	@echo "  make docker-build    Build Docker image"
	@echo "  make docker-run      Run Docker image locally"
	@echo ""
