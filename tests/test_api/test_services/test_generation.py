# tests/test_api/test_services/test_generation.py
"""Unit tests for generation service helper functions and related schemas."""

import pytest
from pydantic import ValidationError

from api.schemas.field import FieldCreate, FieldUpdate
from api.services.generation import _map_field_type


class TestMapFieldType:
    """Tests for _map_field_type with container support."""

    def test_base_types(self):
        """Base types map correctly without container."""
        assert _map_field_type("str") == "str"
        assert _map_field_type("int") == "int"
        assert _map_field_type("float") == "float"
        assert _map_field_type("bool") == "bool"
        assert _map_field_type("datetime") == "datetime.datetime"
        assert _map_field_type("uuid") == "str"
        assert _map_field_type("EmailStr") == "EmailStr"
        assert _map_field_type("HttpUrl") == "HttpUrl"

    def test_unknown_type_defaults_to_str(self):
        """Unknown types default to str."""
        assert _map_field_type("unknown") == "str"

    def test_container_none_returns_base(self):
        """Explicit None container returns base type."""
        assert _map_field_type("str", container=None) == "str"

    def test_list_container_wraps_type(self):
        """List container wraps the base type."""
        assert _map_field_type("str", container="List") == "List[str]"
        assert _map_field_type("int", container="List") == "List[int]"
        assert (
            _map_field_type("datetime", container="List") == "List[datetime.datetime]"
        )
        assert _map_field_type("EmailStr", container="List") == "List[EmailStr]"


class TestContainerSchemaValidation:
    """Tests for container field validation on FieldCreate/FieldUpdate schemas."""

    def test_field_create_with_list_container(self):
        """FieldCreate accepts container='List'."""
        data = FieldCreate.model_validate(
            {
                "namespaceId": "00000000-0000-0000-0000-000000000001",
                "name": "tags",
                "typeId": "00000000-0000-0000-0001-000000000001",
                "container": "List",
            }
        )
        assert data.container == "List"

    def test_field_create_with_null_container(self):
        """FieldCreate accepts container=None (default)."""
        data = FieldCreate.model_validate(
            {
                "namespaceId": "00000000-0000-0000-0000-000000000001",
                "name": "email",
                "typeId": "00000000-0000-0000-0001-000000000001",
            }
        )
        assert data.container is None

    def test_field_create_with_invalid_container_rejects(self):
        """FieldCreate rejects invalid container values."""
        with pytest.raises(ValidationError):
            FieldCreate.model_validate(
                {
                    "namespaceId": "00000000-0000-0000-0000-000000000001",
                    "name": "bad",
                    "typeId": "00000000-0000-0000-0001-000000000001",
                    "container": "Set",
                }
            )

    def test_field_update_with_list_container(self):
        """FieldUpdate accepts container='List'."""
        data = FieldUpdate.model_validate({"container": "List"})
        assert data.container == "List"

    def test_field_update_with_invalid_container_rejects(self):
        """FieldUpdate rejects invalid container values."""
        with pytest.raises(ValidationError):
            FieldUpdate.model_validate({"container": "Dict"})
