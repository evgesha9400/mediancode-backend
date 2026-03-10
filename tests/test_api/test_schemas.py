"""Tests for API schema validation."""

import pytest
from api.schemas.api import GenerateOptions


class TestGenerateOptionsValidation:
    """Validation rules for GenerateOptions schema."""

    def test_database_with_placeholders_raises(self):
        """database_enabled + response_placeholders must raise."""
        with pytest.raises(ValueError, match="Response placeholders cannot be enabled"):
            GenerateOptions(
                database_enabled=True,
                response_placeholders=True,
            )

    def test_database_without_placeholders_passes(self):
        """database_enabled + no placeholders must succeed."""
        opts = GenerateOptions(
            database_enabled=True,
            response_placeholders=False,
        )
        assert opts.database_enabled is True
        assert opts.response_placeholders is False

    def test_placeholders_without_database_passes(self):
        """Placeholders without database must succeed."""
        opts = GenerateOptions(
            database_enabled=False,
            response_placeholders=True,
        )
        assert opts.response_placeholders is True

    def test_default_values_pass(self):
        """Default values (database=False, placeholders=True) must succeed."""
        opts = GenerateOptions()
        assert opts.database_enabled is False
        assert opts.response_placeholders is True
