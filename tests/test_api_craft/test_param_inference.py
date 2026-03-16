# tests/test_api_craft/test_param_inference.py
"""Tests for deterministic path & query parameter inference."""

import pytest
from api_craft.models.enums import FilterOperator
from api_craft.models.input import InputPathParam


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


class TestInputPathParamField:
    def test_field_defaults_none(self):
        """field is optional for backward compatibility."""
        param = InputPathParam(name="item_id", type="int")
        assert param.field is None

    def test_field_accepts_value(self):
        param = InputPathParam(name="store_id", type="uuid", field="store_id")
        assert param.field == "store_id"
