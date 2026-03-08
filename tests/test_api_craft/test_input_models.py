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


class TestForeignKeyValidation:
    def test_fk_to_valid_entity_accepted(self):
        """FK referencing an entity with a PK field is valid."""
        api = InputAPI(
            name="FkTest",
            endpoints=[
                InputEndpoint(
                    name="GetOrders", path="/orders", method="GET", response="Order"
                ),
            ],
            objects=[
                InputModel(
                    name="Order",
                    fields=[InputField(name="id", type="int", pk=True)],
                ),
                InputModel(
                    name="OrderItem",
                    fields=[
                        InputField(name="id", type="int", pk=True),
                        InputField(name="order_id", type="int", fk="Order"),
                    ],
                ),
            ],
        )
        assert len(api.objects) == 2

    def test_fk_to_nonexistent_entity_rejected(self):
        """FK referencing an entity that doesn't exist raises ValueError."""
        with pytest.raises(ValueError, match="not a persisted entity"):
            InputAPI(
                name="FkTest",
                endpoints=[
                    InputEndpoint(
                        name="GetItems", path="/items", method="GET", response="Item"
                    ),
                ],
                objects=[
                    InputModel(
                        name="Item",
                        fields=[
                            InputField(name="id", type="int", pk=True),
                            InputField(name="order_id", type="int", fk="Order"),
                        ],
                    ),
                ],
            )

    def test_fk_to_entity_without_pk_rejected(self):
        """FK referencing a model without a PK field raises ValueError."""
        with pytest.raises(ValueError, match="not a persisted entity"):
            InputAPI(
                name="FkTest",
                endpoints=[
                    InputEndpoint(
                        name="GetOrders",
                        path="/orders",
                        method="GET",
                        response="Order",
                    ),
                ],
                objects=[
                    InputModel(
                        name="Order",
                        fields=[InputField(name="status", type="str")],
                    ),
                    InputModel(
                        name="OrderItem",
                        fields=[
                            InputField(name="id", type="int", pk=True),
                            InputField(name="order_id", type="int", fk="Order"),
                        ],
                    ),
                ],
            )

    def test_set_null_requires_optional_fk(self):
        """on_delete=set_null requires the FK field to be optional."""
        with pytest.raises(ValueError, match="must be optional"):
            InputAPI(
                name="FkTest",
                endpoints=[
                    InputEndpoint(
                        name="GetOrders",
                        path="/orders",
                        method="GET",
                        response="Order",
                    ),
                ],
                objects=[
                    InputModel(
                        name="Order",
                        fields=[InputField(name="id", type="int", pk=True)],
                    ),
                    InputModel(
                        name="OrderItem",
                        fields=[
                            InputField(name="id", type="int", pk=True),
                            InputField(
                                name="order_id",
                                type="int",
                                fk="Order",
                                on_delete="set_null",
                            ),
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
        assert field.foreign_key is None

    def test_orm_field_with_fk(self):
        field = TemplateORMField(
            name="order_id",
            python_type="int",
            column_type="Integer",
            foreign_key="orders.id",
            on_delete="CASCADE",
        )
        assert field.foreign_key == "orders.id"
        assert field.on_delete == "CASCADE"

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
