<%doc>
- Template Parameters:
- api: TemplateApi
</%doc>\
-include .env
export

% if api.database_config:
.PHONY: install run-local build clean run-container swagger db-up db-down db-migrate db-upgrade db-downgrade db-reset run-stack
% else:
.PHONY: install run-local build clean run-container swagger
% endif

PROJECT_NAME=${api.snake_name}
APP_PORT ?= ${api.app_port}
% if api.database_config:
DB_PORT ?= ${api.database_config.db_port}
% endif

install:
	@poetry install

% if api.database_config:
run-local: install db-up db-upgrade
% else:
run-local: install
% endif
	@PYTHONPATH=src poetry run uvicorn main:app --reload --port $(APP_PORT)

build:
	@docker build -t $(PROJECT_NAME) .

clean:
	-@docker stop $(PROJECT_NAME) 2>/dev/null || true
	-@docker rm $(PROJECT_NAME) 2>/dev/null || true
	-@docker rmi $(PROJECT_NAME) 2>/dev/null || true

run-container: install clean build
	@docker run --name $(PROJECT_NAME) -p $(APP_PORT):80 -d $(PROJECT_NAME):latest

swagger: install
	@PYTHONPATH=src poetry run python swagger.py
% if api.database_config:

db-up:
	@docker compose up -d db
	@echo "Waiting for PostgreSQL..."
	@sleep 2

db-down:
	@docker compose down

db-migrate: db-up
	@test -n "$(DESC)" || (echo "Usage: make db-migrate DESC=\"description\""; exit 1)
	@NEXT=$$(printf '%04d' $$(($$(ls -1 migrations/versions/[0-9]*.py 2>/dev/null | wc -l) + 1))); \
	PYTHONPATH=src poetry run alembic revision --autogenerate --rev-id "$$NEXT" -m "$(DESC)"

db-upgrade: db-up
	@PYTHONPATH=src poetry run alembic upgrade head

db-downgrade:
	@PYTHONPATH=src poetry run alembic downgrade -1

db-reset: db-down db-up
	@PYTHONPATH=src poetry run alembic upgrade head

run-stack:
	@docker compose up --build
% endif
