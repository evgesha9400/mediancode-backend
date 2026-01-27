# Default python and poetry paths - can be overridden
PYTHON := python3
POETRY := poetry

test:
	@$(POETRY) run pytest tests/test_generate.py

generate:
	@$(POETRY) run pytest -m manual -v -s

clean:
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@find . -name "*.pyc" -delete
	@find . -name "*.pyo" -delete
	@find . -name "*.pyd" -delete
	@find . -name ".pytest_cache" -type d -exec rm -rf {} +
	@rm -rf tests/output/
	@echo "Cleaned all Python caches and test output"