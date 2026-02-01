# Default python and poetry paths - can be overridden
PYTHON := python3
POETRY := poetry

test:
	@$(POETRY) run pytest tests/test_e2e.py

generate:
	@$(POETRY) run pytest -m manual -v -s

clean:
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@find . -name "*.pyc" -delete
	@find . -name "*.pyo" -delete
	@find . -name "*.pyd" -delete
	@find . -name ".pytest_cache" -type d -exec rm -rf {} +
	@rm -rf tests/output/
	@rm -rf cdk.out/
	@echo "Cleaned all Python caches and test output"

# AWS CDK commands
cdk-install:
	@cd deploy/aws && pip install -r requirements.txt

cdk-synth:
	@cd deploy/aws && cdk synth

cdk-deploy:
	@cd deploy/aws && cdk deploy --require-approval never

cdk-destroy:
	@cd deploy/aws && cdk destroy --force

cdk-diff:
	@cd deploy/aws && cdk diff

# Railway commands
railway-deploy:
	@railway up

railway-logs:
	@railway logs

railway-open:
	@railway open

# Database migrations
db-upgrade:
	@$(POETRY) run alembic upgrade head

db-downgrade:
	@$(POETRY) run alembic downgrade -1

db-migrate:
	@$(POETRY) run alembic revision --autogenerate -m "$(msg)"

db-history:
	@$(POETRY) run alembic history

db-current:
	@$(POETRY) run alembic current

# Docker commands
docker-build:
	@docker build -t median-code-backend .

docker-run:
	@docker run -p 8000:80 median-code-backend