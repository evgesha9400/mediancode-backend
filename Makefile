# Default python and poetry paths - can be overridden
PYTHON := python3
POETRY := poetry

test:
	@$(POETRY) run pytest tests/test_generate.py