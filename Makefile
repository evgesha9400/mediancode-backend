# Median Code Backend - Makefile
# Run 'make help' to see all available commands

PYTHON := python3
POETRY := poetry

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
dev: ## Start backend server with hot reload (localhost:8000)
	@PYTHONPATH=src $(POETRY) run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

.PHONY: db
db: ## Start PostgreSQL database (Docker)
	@docker compose up -d
	@echo "PostgreSQL running on localhost:5432"

.PHONY: db-stop
db-stop: ## Stop PostgreSQL database
	@docker compose down

.PHONY: db-reset
db-reset: ## Stop PostgreSQL and DELETE all data
	@docker compose down -v
	@echo "Database data deleted"

.PHONY: test
test: ## Run tests
	@$(POETRY) run pytest tests/ -v

.PHONY: test-quick
test-quick: ## Run tests (fast, less verbose)
	@$(POETRY) run pytest tests/test_e2e.py

# =============================================================================
#  DEPLOY TO RAILWAY
#  Deploy backend to Railway environments
# =============================================================================

.PHONY: deploy-dev
deploy-dev: ## Deploy to DEVELOPMENT (reads .env.development)
	@$(PYTHON) deploy/railway/deploy.py --env development

.PHONY: deploy-prod
deploy-prod: ## Deploy to PRODUCTION (reads .env.production)
	@$(PYTHON) deploy/railway/deploy.py --env production

.PHONY: deploy-dev-dry
deploy-dev-dry: ## Preview development deploy (no changes)
	@$(PYTHON) deploy/railway/deploy.py --env development --dry-run

.PHONY: deploy-prod-dry
deploy-prod-dry: ## Preview production deploy (no changes)
	@$(PYTHON) deploy/railway/deploy.py --env production --dry-run

.PHONY: logs
logs: ## View Railway logs (current environment)
	@railway logs

.PHONY: dashboard
dashboard: ## Open Railway dashboard
	@railway open

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
#  RAILWAY DATABASE MIGRATIONS
#  Run against Railway PostgreSQL (without full deploy)
# =============================================================================

.PHONY: migrate-dev
migrate-dev: ## Run migrations on Railway DEVELOPMENT
	@echo "Running migrations on Railway development..."
	@railway run -e development alembic upgrade head

.PHONY: migrate-prod
migrate-prod: ## Run migrations on Railway PRODUCTION
	@echo "Running migrations on Railway production..."
	@railway run -e production alembic upgrade head

.PHONY: migrate-dev-status
migrate-dev-status: ## Show migration status on Railway DEVELOPMENT
	@railway run -e development alembic current

.PHONY: migrate-prod-status
migrate-prod-status: ## Show migration status on Railway PRODUCTION
	@railway run -e production alembic current

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
docker-build: ## Build Docker image locally
	@docker build -t median-code-backend .

.PHONY: docker-run
docker-run: ## Run Docker image locally (port 8000)
	@docker run -p 8000:80 median-code-backend

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
	@echo "  make dev             Start backend server with hot reload (localhost:8000)"
	@echo "  make db              Start PostgreSQL database (Docker)"
	@echo "  make db-stop         Stop PostgreSQL database"
	@echo "  make db-reset        Stop PostgreSQL and DELETE all data"
	@echo "  make test            Run tests"
	@echo ""
	@echo "DEPLOY TO RAILWAY:"
	@echo "  make deploy-dev      Deploy to DEVELOPMENT (reads .env.development)"
	@echo "  make deploy-prod     Deploy to PRODUCTION (reads .env.production)"
	@echo "  make deploy-dev-dry  Preview development deploy (no changes)"
	@echo "  make deploy-prod-dry Preview production deploy (no changes)"
	@echo "  make logs            View Railway logs"
	@echo "  make dashboard       Open Railway dashboard"
	@echo ""
	@echo "LOCAL DATABASE MIGRATIONS (runs against local Docker PostgreSQL):"
	@echo "  make migrate-up      Apply pending migrations"
	@echo "  make migrate-down    Rollback last migration"
	@echo "  make migrate-history Show migration history"
	@echo "  make migration msg=\"...\"  Create new migration file"
	@echo ""
	@echo "RAILWAY DATABASE MIGRATIONS (runs against Railway PostgreSQL):"
	@echo "  make migrate-dev     Run migrations on DEVELOPMENT"
	@echo "  make migrate-prod    Run migrations on PRODUCTION"
	@echo "  make migrate-dev-status   Show migration status on DEVELOPMENT"
	@echo "  make migrate-prod-status  Show migration status on PRODUCTION"
	@echo ""
	@echo "UTILITIES:"
	@echo "  make clean           Remove Python caches"
	@echo "  make docker-build    Build Docker image"
	@echo "  make docker-run      Run Docker image locally"
	@echo ""
