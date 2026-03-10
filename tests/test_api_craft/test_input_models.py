# tests/test_api_craft/test_input_models.py
"""Tests for input model changes: pk, database config."""

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


class TestPrimaryKeyValidation:
    def test_optional_pk_rejected(self):
        """PK field must not be optional."""
        with pytest.raises(ValueError, match="cannot be optional"):
            InputAPI(
                name="PkTest",
                endpoints=[
                    InputEndpoint(
                        name="GetItems", path="/items", method="GET", response="Item"
                    )
                ],
                objects=[
                    InputModel(
                        name="Item",
                        fields=[
                            InputField(name="id", type="int", pk=True, optional=True)
                        ],
                    ),
                ],
            )

    def test_multiple_pks_rejected(self):
        """Only one PK field per model is allowed."""
        with pytest.raises(ValueError, match="multiple primary key"):
            InputAPI(
                name="PkTest",
                endpoints=[
                    InputEndpoint(
                        name="GetItems", path="/items", method="GET", response="Item"
                    )
                ],
                objects=[
                    InputModel(
                        name="Item",
                        fields=[
                            InputField(name="id", type="int", pk=True),
                            InputField(name="uuid", type="uuid", pk=True),
                        ],
                    ),
                ],
            )


from api_craft.models.template import (
    TemplateORMField,
    TemplateORMModel,
    TemplateDatabaseConfig,
)


class TestTemplateORMModels:
    def test_orm_field_creation(self):
        field = TemplateORMField(
            name="id",
            python_type="int",
            column_type="Integer",
            primary_key=True,
            autoincrement=True,
        )
        assert field.primary_key is True
        assert field.nullable is False

    def test_orm_model_creation(self):
        model = TemplateORMModel(
            class_name="ItemRecord",
            table_name="items",
            source_model="Item",
            fields=[
                TemplateORMField(
                    name="id",
                    python_type="int",
                    column_type="Integer",
                    primary_key=True,
                ),
                TemplateORMField(name="name", python_type="str", column_type="Text"),
            ],
        )
        assert model.class_name == "ItemRecord"
        assert model.table_name == "items"
        assert len(model.fields) == 2

    def test_database_config(self):
        config = TemplateDatabaseConfig(
            enabled=True,
            seed_data=True,
            default_url="postgresql+asyncpg://postgres:postgres@localhost:5432/test",
        )
        assert config.enabled is True
