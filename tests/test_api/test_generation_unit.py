# tests/test_api/test_generation_unit.py
"""Unit tests for generation service helper functions."""

import io
import os
import tempfile
import zipfile

import pytest

from unittest.mock import MagicMock

import inspect

from api.schemas.api import GenerateOptions
from api.services.generation import (
    _build_endpoint_name,
    _build_field_type,
    _convert_to_input_api,
    generate_api_zip,
)


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
            ("GET", "/users/{user_id}", "GetUsersByUserId"),
            ("DELETE", "/users/{user_id}", "DeleteUsersByUserId"),
            ("GET", "/users/{user_id}/orders", "GetUsersByUserIdOrders"),
            ("GET", "/user-profiles/{profile_id}", "GetUserProfilesByProfileId"),
            ("GET", "/api/v1/users", "GetApiV1Users"),
            ("PUT", "/order-items/{item_id}/status", "PutOrderItemsByItemIdStatus"),
            ("GET", "/", "GetRoot"),
            ("GET", "/{id}", "GetById"),
        ],
    )
    def test_endpoint_name(self, method: str, path: str, expected: str):
        assert _build_endpoint_name(method, path) == expected

    def test_endpoint_name_differentiates_with_path_param(self):
        """GET /products and GET /products/{id} must produce different names."""
        list_name = _build_endpoint_name("GET", "/products")
        detail_name = _build_endpoint_name("GET", "/products/{tracking_id}")
        assert list_name != detail_name


class TestGenerateOptions:
    def test_defaults(self):
        opts = GenerateOptions()
        assert opts.healthcheck == "/health"
        assert opts.response_placeholders is True
        assert opts.database_enabled is False

    def test_override_all_fields(self):
        opts = GenerateOptions(
            healthcheck=None,
            response_placeholders=False,
            database_enabled=True,
        )
        assert opts.healthcheck is None
        assert opts.response_placeholders is False
        assert opts.database_enabled is True

    def test_camel_case_alias(self):
        opts = GenerateOptions.model_validate(
            {
                "responsePlaceholders": False,
                "databaseEnabled": True,
            }
        )
        assert opts.response_placeholders is False
        assert opts.database_enabled is True

    def test_empty_body_uses_defaults(self):
        opts = GenerateOptions.model_validate({})
        assert opts.healthcheck == "/health"
        assert opts.response_placeholders is True
        assert opts.database_enabled is False

    def test_custom_healthcheck_path(self):
        opts = GenerateOptions(healthcheck="/status")
        assert opts.healthcheck == "/status"


class TestConvertToInputApiOptions:
    def _make_api_model(self):
        """Create a minimal mock ApiModel for testing."""
        api = MagicMock()
        api.title = "TestApi"
        api.version = "1.0.0"
        api.description = "Test"
        api.endpoints = []
        return api

    def test_default_options_match_current_behavior(self):
        api = self._make_api_model()
        opts = GenerateOptions()
        result = _convert_to_input_api(api, {}, {}, opts)
        assert result.config.healthcheck == "/health"
        assert result.config.response_placeholders is True
        assert result.config.database.enabled is False

    def test_database_enabled_passed_through(self):
        api = self._make_api_model()
        field = MagicMock()
        field.name = "id"
        field.field_type = MagicMock()
        field.field_type.python_type = "int"
        field.description = None
        field.default_value = None
        field.container = None
        field.constraint_values = []
        field.validators = []
        assoc = MagicMock()
        assoc.field_id = "field-1"
        assoc.optional = False
        assoc.position = 0
        assoc.is_pk = True
        obj = MagicMock()
        obj.id = "obj-1"
        obj.name = "Item"
        obj.description = "Test item"
        obj.field_associations = [assoc]
        obj.validators = []
        opts = GenerateOptions(database_enabled=True, response_placeholders=False)
        result = _convert_to_input_api(api, {"obj-1": obj}, {"field-1": field}, opts)
        assert result.config.database.enabled is True

    def test_healthcheck_none_disables_it(self):
        api = self._make_api_model()
        opts = GenerateOptions(healthcheck=None)
        result = _convert_to_input_api(api, {}, {}, opts)
        assert result.config.healthcheck is None

    def test_response_placeholders_false_passed_through(self):
        api = self._make_api_model()
        opts = GenerateOptions(response_placeholders=False)
        result = _convert_to_input_api(api, {}, {}, opts)
        assert result.config.response_placeholders is False


class TestGenerateApiZipSignature:
    def test_accepts_options_parameter(self):
        """generate_api_zip must accept an 'options' parameter."""
        sig = inspect.signature(generate_api_zip)
        assert "options" in sig.parameters
        param = sig.parameters["options"]
        assert (
            param.default is not inspect.Parameter.empty
        ), "options must have a default value"


def test_zip_excludes_pycache():
    """Generated ZIP must not contain __pycache__ files."""
    with tempfile.TemporaryDirectory() as tmp:
        project = os.path.join(tmp, "test-api")
        src = os.path.join(project, "src")
        pycache = os.path.join(src, "__pycache__")
        os.makedirs(pycache)

        with open(os.path.join(src, "main.py"), "w") as f:
            f.write("# main")
        with open(os.path.join(pycache, "main.cpython-313.pyc"), "wb") as f:
            f.write(b"\x00")

        # Simulate the zip logic from generate_api_zip
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(project):
                dirs[:] = [d for d in dirs if d != "__pycache__"]
                for file in files:
                    file_path = os.path.join(root, file)
                    arc_name = os.path.relpath(file_path, project)
                    zf.write(file_path, arc_name)

        zip_buffer.seek(0)
        with zipfile.ZipFile(zip_buffer, "r") as zf:
            names = zf.namelist()
            assert not any("__pycache__" in n for n in names)
            assert any("main.py" in n for n in names)


class TestConvertToInputApiPk:
    """Tests that pk flows from associations to InputField."""

    def _make_api_with_objects(self, *, is_pk=False):
        """Create mocks simulating the DB models with field associations."""
        field = MagicMock()
        field.name = "id"
        field.field_type = MagicMock()
        field.field_type.python_type = "int"
        field.description = None
        field.default_value = None
        field.container = None
        field.constraint_values = []
        field.validators = []

        assoc = MagicMock()
        assoc.field_id = "field-1"
        assoc.optional = False
        assoc.position = 0
        assoc.is_pk = is_pk

        obj = MagicMock()
        obj.id = "obj-1"
        obj.name = "Item"
        obj.description = "Test item"
        obj.field_associations = [assoc]
        obj.validators = []

        api = MagicMock()
        api.title = "TestApi"
        api.version = "1.0.0"
        api.description = "Test"
        api.endpoints = []

        objects_map = {"obj-1": obj}
        fields_map = {"field-1": field}
        return api, objects_map, fields_map

    def test_pk_passed_through(self):
        api, objects_map, fields_map = self._make_api_with_objects(is_pk=True)
        opts = GenerateOptions(database_enabled=True, response_placeholders=False)
        result = _convert_to_input_api(api, objects_map, fields_map, opts)
        item_obj = next(o for o in result.objects if o.name == "Item")
        id_field = next(f for f in item_obj.fields if f.name == "id")
        assert id_field.pk is True

    def test_pk_false_by_default(self):
        api, objects_map, fields_map = self._make_api_with_objects(is_pk=False)
        opts = GenerateOptions()
        result = _convert_to_input_api(api, objects_map, fields_map, opts)
        item_obj = next(o for o in result.objects if o.name == "Item")
        id_field = next(f for f in item_obj.fields if f.name == "id")
        assert id_field.pk is False
