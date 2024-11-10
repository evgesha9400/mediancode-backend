# Default python and poetry paths - can be overridden
PYTHON := python3
POETRY := poetry

claude-update:
	@echo "Updating Claude project..."
	@$(POETRY) run python -m claude-pyrojects.cli update