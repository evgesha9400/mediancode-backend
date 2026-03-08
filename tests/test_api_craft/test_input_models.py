# tests/test_api_craft/test_input_models.py
"""Tests for input model changes: pk, fk, on_delete, database config."""

import pytest
from api_craft.models.input import (
    InputField,
    InputModel,
    InputApiConfig,
    InputAPI,
    InputEndpoint,
)


class TestPrimaryKeyField:
    def test_field_pk_defaults_false(self):
        field = InputField(name="name", type="str")
        assert field.pk is False

    def test_field_pk_true(self):
        field = InputField(name="id", type="int", pk=True)
        assert field.pk is True


class TestForeignKeyField:
    def test_field_fk_defaults_none(self):
        field = InputField(name="name", type="str")
        assert field.fk is None

    def test_field_fk_set(self):
        field = InputField(name="order_id", type="int", fk="Order")
        assert field.fk == "Order"

    def test_field_on_delete_defaults_restrict(self):
        field = InputField(name="order_id", type="int", fk="Order")
        assert field.on_delete == "restrict"

    def test_field_on_delete_cascade(self):
        field = InputField(name="order_id", type="int", fk="Order", on_delete="cascade")
        assert field.on_delete == "cascade"

    def test_field_on_delete_set_null(self):
        field = InputField(
            name="order_id", type="int", fk="Order", on_delete="set_null"
        )
        assert field.on_delete == "set_null"

    def test_field_on_delete_invalid_rejected(self):
        with pytest.raises(Exception):
            InputField(name="order_id", type="int", fk="Order", on_delete="delete")


class TestDatabaseConfig:
    def test_database_config_defaults(self):
        config = InputApiConfig()
        assert config.database.enabled is False
        assert config.database.seed_data is True

    def test_database_enabled(self):
        config = InputApiConfig(database={"enabled": True})
        assert config.database.enabled is True

    def test_database_seed_disabled(self):
        config = InputApiConfig(database={"enabled": True, "seed_data": False})
        assert config.database.seed_data is False
