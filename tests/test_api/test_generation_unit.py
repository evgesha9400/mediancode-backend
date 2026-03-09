# tests/test_api/test_generation_unit.py
"""Unit tests for generation service helper functions."""

import io
import os
import tempfile
import zipfile

import pytest

from api.schemas.api import GenerateOptions
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
        assert opts.format_code is True
        assert opts.generate_swagger is True
        assert opts.database_enabled is False
        assert opts.database_seed_data is True

    def test_override_all_fields(self):
        opts = GenerateOptions(
            healthcheck=None,
            response_placeholders=False,
            format_code=False,
            generate_swagger=False,
            database_enabled=True,
            database_seed_data=False,
        )
        assert opts.healthcheck is None
        assert opts.response_placeholders is False
        assert opts.format_code is False
        assert opts.generate_swagger is False
        assert opts.database_enabled is True
        assert opts.database_seed_data is False

    def test_camel_case_alias(self):
        opts = GenerateOptions.model_validate(
            {
                "responsePlaceholders": False,
                "formatCode": False,
                "generateSwagger": False,
                "databaseEnabled": True,
                "databaseSeedData": False,
            }
        )
        assert opts.response_placeholders is False
        assert opts.format_code is False
        assert opts.generate_swagger is False
        assert opts.database_enabled is True
        assert opts.database_seed_data is False

    def test_empty_body_uses_defaults(self):
        opts = GenerateOptions.model_validate({})
        assert opts.healthcheck == "/health"
        assert opts.response_placeholders is True
        assert opts.format_code is True
        assert opts.generate_swagger is True
        assert opts.database_enabled is False
        assert opts.database_seed_data is True

    def test_custom_healthcheck_path(self):
        opts = GenerateOptions(healthcheck="/status")
        assert opts.healthcheck == "/status"


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
