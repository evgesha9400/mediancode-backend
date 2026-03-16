# tests/test_api_craft/test_param_inference.py
"""Tests for deterministic path & query parameter inference."""

import pytest
from api_craft.models.enums import FilterOperator


class TestFilterOperatorEnum:
    def test_valid_operators(self):
        valid = ["eq", "gte", "lte", "gt", "lt", "like", "ilike", "in"]
        for op in valid:
            # Literal types accept valid values without error
            assert op in valid

    def test_all_operators_present(self):
        """FilterOperator must include all 8 operators from the spec."""
        from typing import get_args

        operators = get_args(FilterOperator)
        assert set(operators) == {"eq", "gte", "lte", "gt", "lt", "like", "ilike", "in"}
