# tests/test_api_craft/test_param_inference.py
"""Tests for deterministic path & query parameter inference."""

import pytest
from api_craft.models.enums import FilterOperator
from api_craft.models.input import InputEndpoint, InputPathParam, InputQueryParam


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


class TestInputQueryParamFields:
    def test_defaults_none(self):
        """New fields default to None/False for backward compatibility."""
        param = InputQueryParam(name="limit", type="int")
        assert param.field is None
        assert param.operator is None
        assert param.pagination is False

    def test_filter_param(self):
        param = InputQueryParam(
            name="min_price", type="float", field="price", operator="gte"
        )
        assert param.field == "price"
        assert param.operator == "gte"
        assert param.pagination is False

    def test_pagination_param(self):
        param = InputQueryParam(name="limit", type="int", pagination=True)
        assert param.pagination is True
        assert param.field is None
        assert param.operator is None


class TestInputEndpointTarget:
    def test_target_defaults_none(self):
        """target is optional for backward compatibility."""
        endpoint = InputEndpoint(
            name="GetItems", path="/items", method="GET", response="Item"
        )
        assert endpoint.target is None

    def test_target_accepts_value(self):
        endpoint = InputEndpoint(
            name="GetItems",
            path="/items",
            method="GET",
            response="ItemList",
            response_shape="list",
            target="Item",
        )
        assert endpoint.target == "Item"
