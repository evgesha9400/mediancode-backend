# tests/test_api/test_generation_unit.py
"""Unit tests for generation service helper functions."""

import pytest

from api.services.generation import _build_endpoint_name, _build_field_type


class TestBuildFieldType:
    """Tests for _build_field_type (replaces _map_field_type)."""

    @pytest.mark.parametrize(
        "python_type,container,expected",
        [
            ("str", None, "str"),
            ("int", None, "int"),
            ("float", None, "float"),
            ("bool", None, "bool"),
            ("datetime.datetime", None, "datetime.datetime"),
            ("datetime.date", None, "datetime.date"),
            ("datetime.time", None, "datetime.time"),
            ("uuid.UUID", None, "uuid.UUID"),
            ("EmailStr", None, "EmailStr"),
            ("HttpUrl", None, "HttpUrl"),
            ("Decimal", None, "Decimal"),
            ("str", "List", "List[str]"),
            ("int", "List", "List[int]"),
            ("datetime.datetime", "List", "List[datetime.datetime]"),
            ("uuid.UUID", "List", "List[uuid.UUID]"),
        ],
    )
    def test_type_mapping(self, python_type: str, container: str | None, expected: str):
        assert _build_field_type(python_type, container) == expected


class TestBuildEndpointName:
    """Tests for _build_endpoint_name with path sanitization."""

    @pytest.mark.parametrize(
        "method,path,expected",
        [
            ("GET", "/users", "GetUsers"),
            ("POST", "/users", "PostUsers"),
            ("GET", "/users/{user_id}", "GetUsers"),
            ("DELETE", "/users/{user_id}", "DeleteUsers"),
            ("GET", "/users/{user_id}/orders", "GetUsersOrders"),
            ("GET", "/user-profiles/{profile_id}", "GetUserProfiles"),
            ("GET", "/api/v1/users", "GetApiV1Users"),
            ("PUT", "/order-items/{item_id}/status", "PutOrderItemsStatus"),
            ("GET", "/", "GetRoot"),
            ("GET", "/{id}", "GetRoot"),
        ],
    )
    def test_endpoint_name(self, method: str, path: str, expected: str):
        assert _build_endpoint_name(method, path) == expected
