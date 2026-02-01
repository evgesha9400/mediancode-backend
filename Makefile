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

# CDK commands
cdk-install:
	@cd infra && pip install -r requirements.txt

cdk-synth:
	@cd infra && cdk synth

cdk-deploy:
	@cd infra && cdk deploy --require-approval never

cdk-destroy:
	@cd infra && cdk destroy --force

cdk-diff:
	@cd infra && cdk diff

# Docker commands
docker-build:
	@docker build -t median-code-backend .

docker-run:
	@docker run -p 8000:80 median-code-backend