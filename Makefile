

claude-update:
	@echo "Updating Claude project..."
	$(POETRY) run python -m claude-pyrojects.cli update