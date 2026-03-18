# tests/test_api_craft/test_input_models.py
"""Tests for input model changes: pk, database config."""

import pytest
from api_craft.models.input import (
    InputDatabaseConfig,
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

    def test_database_enabled(self):
        config = InputApiConfig(database={"enabled": True})
        assert config.database.enabled is True


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
            default_url="postgresql+asyncpg://postgres:postgres@localhost:5433/test",
        )
        assert config.enabled is True
        assert config.db_port == 5433


class TestPrimaryKeyTypeRestriction:
    """Only int and uuid types are allowed for primary key fields."""

    def test_int_pk_accepted(self):
        api = InputAPI(
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
                        InputField(name="name", type="str"),
                    ],
                ),
            ],
        )
        assert api.objects[0].fields[0].pk is True

    def test_uuid_pk_accepted(self):
        api = InputAPI(
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
                        InputField(name="id", type="uuid", pk=True),
                        InputField(name="name", type="str"),
                    ],
                ),
            ],
        )
        assert api.objects[0].fields[0].pk is True

    def test_uuid_dotted_pk_accepted(self):
        api = InputAPI(
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
                        InputField(name="id", type="uuid.UUID", pk=True),
                        InputField(name="name", type="str"),
                    ],
                ),
            ],
        )
        assert api.objects[0].fields[0].pk is True

    @pytest.mark.parametrize(
        "bad_type",
        ["str", "datetime", "bool", "float", "date", "Decimal", "EmailStr"],
    )
    def test_unsupported_pk_type_rejected(self, bad_type):
        with pytest.raises(ValueError, match="unsupported type"):
            InputAPI(
                name="PkTest",
                endpoints=[
                    InputEndpoint(
                        name="GetItems",
                        path="/items",
                        method="GET",
                        response="Item",
                    )
                ],
                objects=[
                    InputModel(
                        name="Item",
                        fields=[InputField(name="id", type=bad_type, pk=True)],
                    ),
                ],
            )

    def test_non_pk_field_any_type_allowed(self):
        """Non-PK fields should not be restricted by PK type rules."""
        api = InputAPI(
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
                        InputField(name="created_at", type="datetime"),
                        InputField(name="email", type="EmailStr"),
                    ],
                ),
            ],
        )
        assert len(api.objects[0].fields) == 3


class TestDatabaseConfigValidation:
    """Validation rules for database generation configuration."""

    def test_database_with_placeholders_passes(self):
        """Database enabled + response_placeholders=True is now valid (mixed mode)."""
        api = InputAPI(
            name="TestApi",
            objects=[
                InputModel(
                    name="Item",
                    fields=[InputField(name="id", type="int", pk=True)],
                ),
            ],
            endpoints=[
                InputEndpoint(
                    name="GetItems", path="/items", method="GET", response="Item"
                ),
            ],
            config=InputApiConfig(
                response_placeholders=True,
                database=InputDatabaseConfig(enabled=True),
            ),
        )
        assert api.config.database.enabled is True
        assert api.config.response_placeholders is True

    def test_database_without_placeholders_passes(self):
        """Database enabled + response_placeholders=False must succeed."""
        api = InputAPI(
            name="TestApi",
            objects=[
                InputModel(
                    name="Item",
                    fields=[InputField(name="id", type="int", pk=True)],
                ),
            ],
            endpoints=[
                InputEndpoint(
                    name="GetItems", path="/items", method="GET", response="Item"
                ),
            ],
            config=InputApiConfig(
                response_placeholders=False,
                database=InputDatabaseConfig(enabled=True),
            ),
        )
        assert api.config.database.enabled is True

    def test_placeholders_without_database_passes(self):
        """Placeholders enabled without database must succeed."""
        api = InputAPI(
            name="TestApi",
            objects=[
                InputModel(
                    name="Item",
                    fields=[InputField(name="name", type="str")],
                ),
            ],
            endpoints=[
                InputEndpoint(
                    name="GetItems", path="/items", method="GET", response="Item"
                ),
            ],
            config=InputApiConfig(
                response_placeholders=True,
                database=InputDatabaseConfig(enabled=False),
            ),
        )
        assert api.config.response_placeholders is True

    def test_database_without_pk_raises(self):
        """Database enabled with no PK on any object must raise."""
        with pytest.raises(ValueError, match="at least one object with a primary key"):
            InputAPI(
                name="TestApi",
                objects=[
                    InputModel(
                        name="Item",
                        fields=[InputField(name="name", type="str")],
                    ),
                ],
                endpoints=[
                    InputEndpoint(
                        name="GetItems", path="/items", method="GET", response="Item"
                    ),
                ],
                config=InputApiConfig(
                    database=InputDatabaseConfig(enabled=True),
                ),
            )

    def test_database_with_pk_passes(self):
        """Database enabled with a PK on at least one object must succeed."""
        api = InputAPI(
            name="TestApi",
            objects=[
                InputModel(
                    name="Item",
                    fields=[
                        InputField(name="id", type="int", pk=True),
                        InputField(name="name", type="str"),
                    ],
                ),
            ],
            endpoints=[
                InputEndpoint(
                    name="GetItems", path="/items", method="GET", response="Item"
                ),
            ],
            config=InputApiConfig(
                database=InputDatabaseConfig(enabled=True),
            ),
        )
        assert api.config.database.enabled is True


class TestResponseShapeForPath:
    """Endpoints ending with a path parameter must use response_shape 'object'."""

    def test_path_ending_with_param_and_object_passes(self):
        """Path ending with {param} + response_shape 'object' is valid."""
        endpoint = InputEndpoint(
            name="GetProduct",
            path="/products/{product_id}",
            method="GET",
            response="Product",
            response_shape="object",
            path_params=[{"name": "product_id", "type": "int"}],
        )
        assert endpoint.response_shape == "object"

    def test_path_ending_with_param_and_list_raises(self):
        """Path ending with {param} + response_shape 'list' is invalid."""
        with pytest.raises(ValueError, match="response_shape 'object'"):
            InputEndpoint(
                name="GetProduct",
                path="/products/{product_id}",
                method="GET",
                response="Product",
                response_shape="list",
                path_params=[{"name": "product_id", "type": "int"}],
            )

    def test_path_ending_with_collection_and_list_passes(self):
        """Path ending with collection name + response_shape 'list' is valid."""
        endpoint = InputEndpoint(
            name="GetProducts",
            path="/products",
            method="GET",
            response="ProductList",
            response_shape="list",
        )
        assert endpoint.response_shape == "list"

    def test_path_ending_with_collection_and_object_passes(self):
        """Path ending with collection name + response_shape 'object' is valid."""
        endpoint = InputEndpoint(
            name="GetProduct",
            path="/products",
            method="GET",
            response="Product",
            response_shape="object",
        )
        assert endpoint.response_shape == "object"

    def test_nested_path_ending_with_param_and_object_passes(self):
        """Nested path like /stores/{store_id}/products/{product_id} + 'object' is valid."""
        endpoint = InputEndpoint(
            name="GetStoreProduct",
            path="/stores/{store_id}/products/{product_id}",
            method="GET",
            response="Product",
            response_shape="object",
            path_params=[
                {"name": "store_id", "type": "int"},
                {"name": "product_id", "type": "int"},
            ],
        )
        assert endpoint.response_shape == "object"

    def test_nested_path_ending_with_collection_and_list_passes(self):
        """Nested path like /stores/{store_id}/products + 'list' is valid."""
        endpoint = InputEndpoint(
            name="GetStoreProducts",
            path="/stores/{store_id}/products",
            method="GET",
            response="ProductList",
            response_shape="list",
            path_params=[{"name": "store_id", "type": "int"}],
        )
        assert endpoint.response_shape == "list"


class TestResponseShapeForMethod:
    """Only GET endpoints may use response_shape 'list'."""

    def test_get_with_list_passes(self):
        """GET + response_shape 'list' is valid."""
        endpoint = InputEndpoint(
            name="GetProducts",
            path="/products",
            method="GET",
            response="Product",
            response_shape="list",
        )
        assert endpoint.response_shape == "list"

    def test_get_with_object_passes(self):
        """GET + response_shape 'object' is valid."""
        endpoint = InputEndpoint(
            name="GetProduct",
            path="/products/{product_id}",
            method="GET",
            response="Product",
            response_shape="object",
            path_params=[{"name": "product_id", "type": "int"}],
        )
        assert endpoint.response_shape == "object"

    def test_post_with_object_passes(self):
        """POST + response_shape 'object' is valid."""
        endpoint = InputEndpoint(
            name="CreateProduct",
            path="/products",
            method="POST",
            response="Product",
            response_shape="object",
        )
        assert endpoint.response_shape == "object"

    @pytest.mark.parametrize(
        "method",
        ["POST", "PUT", "PATCH", "DELETE"],
    )
    def test_non_get_with_list_raises(self, method):
        """Non-GET methods with response_shape 'list' are invalid."""
        with pytest.raises(
            ValueError, match="list response shape is only valid for GET"
        ):
            InputEndpoint(
                name="MutateProducts",
                path="/products",
                method=method,
                response="Product",
                response_shape="list",
            )

    def test_post_default_response_shape_passes(self):
        """POST with default response_shape ('object') is valid."""
        endpoint = InputEndpoint(
            name="CreateProduct",
            path="/products",
            method="POST",
            response="Product",
        )
        assert endpoint.response_shape == "object"


class TestServerDefaultField:
    """Tests for the server_default and default_literal fields on InputField."""

    def test_server_default_accepts_valid_strategies(self):
        for strategy in ("uuid4", "now", "now_on_update", "auto_increment", "literal"):
            field = InputField(name="test_field", type="str", server_default=strategy)
            assert field.server_default == strategy

    def test_server_default_defaults_to_none(self):
        field = InputField(name="test_field", type="str")
        assert field.server_default is None

    def test_default_literal_stored(self):
        field = InputField(
            name="status",
            type="str",
            server_default="literal",
            default_literal="active",
        )
        assert field.default_literal == "active"

    def test_no_default_value_field(self):
        """default_value was removed — verify it's not stored."""
        field = InputField(name="test_field", type="str")
        assert "default_value" not in InputField.model_fields
