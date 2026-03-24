# tests/codegen/test_input_and_transform.py
# tests/codegen/test_input_and_transform.py
"""Tests for input models, name types, validation catalog, preparation,
ORM transforms, schema splitting, placeholders, generate options, and
enum consistency.

Merges legacy tests from:
- test_input_models, test_name_types, test_validation_catalog, test_prepare,
  test_transformers, test_appears, test_placeholders, test_schemas,
  test_enum_check_consistency
"""

from typing import get_args

import pytest

from api.schemas.api import GenerateOptions
from api_craft.extractors import collect_database_dependencies, collect_orm_imports
from api_craft.models.enums import (
    Cardinality,
    Container,
    FieldRole,
    FilterOperator,
    GeneratedStrategy,
    HttpMethod,
    ResponseShape,
    ValidatorMode,
    check_constraint_sql,
)
from api_craft.models.input import (
    InputAPI,
    InputApiConfig,
    InputDatabaseConfig,
    InputEndpoint,
    InputField,
    InputModel,
    InputPathParam,
    InputQueryParam,
    InputValidator,
)
from api_craft.models.orm_types import (
    TemplateDatabaseConfig,
    TemplateORMField,
    TemplateORMModel,
)
from api_craft.models.types import PascalCaseName, SnakeCaseName
from api_craft.models.validation_catalog import (
    ALLOWED_PK_TYPES,
    OPERATOR_VALID_TYPES,
    PASCAL_CASE_PATTERN,
    SERVER_DEFAULT_VALID_TYPES,
    SNAKE_CASE_PATTERN,
)
from api_craft.models.validators import (
    validate_snake_case_name,
    validate_type_annotation,
)
from api_craft.orm_builder import transform_orm_models
from api_craft.placeholders import (
    PlaceholderGenerator,
    extract_constraints,
    generate_bool,
    generate_date,
    generate_datetime,
    generate_float,
    generate_int,
    generate_string,
    generate_uuid,
    parse_type,
)
from api_craft.prepare import prepare_api
from api_craft.schema_splitter import split_model_schemas
from api_craft.utils import camel_to_snake, snake_to_plural
from support.generated_app import load_input

TemplateField = InputField
TemplateValidator = InputValidator


def _make_model(name, fields):
    return InputModel(name=name, fields=[InputField(**f) for f in fields])


def _make_field(name: str, type_: str = "str", **kwargs) -> InputField:
    return InputField(name=name, type=type_, **kwargs)


# ---------------------------------------------------------------------------
# Input API Validation (from test_input_models)
# ---------------------------------------------------------------------------


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


class TestPascalCaseValidation:
    """PascalCase name validation must reject underscores."""

    def test_rejects_underscores(self):
        with pytest.raises(ValueError, match="PascalCaseName"):
            InputAPI(
                name="User_Profile",
                endpoints=[
                    InputEndpoint(
                        name="GetUsers",
                        path="/users",
                        method="GET",
                        response="User",
                    )
                ],
                objects=[
                    InputModel(
                        name="User",
                        fields=[InputField(name="id", type="int")],
                    )
                ],
            )

    def test_accepts_valid_pascal_case(self):
        api = InputAPI(
            name="UserProfile",
            endpoints=[
                InputEndpoint(
                    name="GetUsers",
                    path="/users",
                    method="GET",
                    response="User",
                )
            ],
            objects=[
                InputModel(
                    name="User",
                    fields=[InputField(name="id", type="int")],
                )
            ],
        )
        assert api.name == "UserProfile"


class TestPrimaryKeyValidation:
    def test_nullable_pk_rejected(self):
        with pytest.raises(ValueError, match="cannot be nullable"):
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
                            InputField(
                                name="id",
                                type="int",
                                pk=True,
                                nullable=True,
                                exposure="read_only",
                            )
                        ],
                    ),
                ],
            )

    def test_multiple_pks_rejected(self):
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
                            InputField(
                                name="id",
                                type="int",
                                pk=True,
                                exposure="read_only",
                            ),
                            InputField(
                                name="uuid",
                                type="uuid",
                                pk=True,
                                exposure="read_only",
                            ),
                        ],
                    ),
                ],
            )


class TestTemplateORMModels:
    def test_orm_field_creation(self):
        field = TemplateORMField(
            name="id",
            python_type="int",
            column_type="Integer",
            primary_key=True,
            server_default="auto_increment",
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
                        InputField(
                            name="id", type="int", pk=True, exposure="read_only"
                        ),
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
                        InputField(
                            name="id", type="uuid", pk=True, exposure="read_only"
                        ),
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
                        InputField(
                            name="id",
                            type="uuid.UUID",
                            pk=True,
                            exposure="read_only",
                        ),
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
                        fields=[
                            InputField(
                                name="id",
                                type=bad_type,
                                pk=True,
                                exposure="read_only",
                            )
                        ],
                    ),
                ],
            )

    def test_pk_rejects_uppercase_uuid(self):
        """PK type 'UUID' (uppercase) should be rejected — only 'uuid' is valid."""
        with pytest.raises(ValueError, match="unsupported type"):
            InputAPI(
                name="PkTypeTest",
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
                        fields=[
                            InputField(
                                name="id",
                                type="UUID",
                                pk=True,
                                exposure="read_only",
                            )
                        ],
                    )
                ],
            )

    def test_non_pk_field_any_type_allowed(self):
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
                        InputField(
                            name="id", type="int", pk=True, exposure="read_only"
                        ),
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
        api = InputAPI(
            name="TestApi",
            objects=[
                InputModel(
                    name="Item",
                    fields=[
                        InputField(name="id", type="int", pk=True, exposure="read_only")
                    ],
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
        api = InputAPI(
            name="TestApi",
            objects=[
                InputModel(
                    name="Item",
                    fields=[
                        InputField(name="id", type="int", pk=True, exposure="read_only")
                    ],
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
        api = InputAPI(
            name="TestApi",
            objects=[
                InputModel(
                    name="Item",
                    fields=[
                        InputField(
                            name="id", type="int", pk=True, exposure="read_only"
                        ),
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
        endpoint = InputEndpoint(
            name="GetProducts",
            path="/products",
            method="GET",
            response="ProductList",
            response_shape="list",
        )
        assert endpoint.response_shape == "list"

    def test_path_ending_with_collection_and_object_passes(self):
        endpoint = InputEndpoint(
            name="GetProduct",
            path="/products",
            method="GET",
            response="Product",
            response_shape="object",
        )
        assert endpoint.response_shape == "object"

    def test_nested_path_ending_with_param_and_object_passes(self):
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
        endpoint = InputEndpoint(
            name="GetProducts",
            path="/products",
            method="GET",
            response="Product",
            response_shape="list",
        )
        assert endpoint.response_shape == "list"

    def test_get_with_object_passes(self):
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
        endpoint = InputEndpoint(
            name="CreateProduct",
            path="/products",
            method="POST",
            response="Product",
        )
        assert endpoint.response_shape == "object"


class TestFieldDefault:
    """Tests for the default field (FieldDefault union) on InputField."""

    def test_generated_strategies_accepted(self):
        from api_craft.models.input import FieldDefaultGenerated

        for strategy in ("uuid4", "now", "now_on_update", "auto_increment"):
            field = InputField(
                name="test_field",
                type="str",
                default={"kind": "generated", "strategy": strategy},
            )
            assert field.default.kind == "generated"
            assert field.default.strategy == strategy

    def test_default_defaults_to_none(self):
        field = InputField(name="test_field", type="str")
        assert field.default is None

    def test_literal_default_stored(self):
        field = InputField(
            name="status",
            type="str",
            default={"kind": "literal", "value": "active"},
        )
        assert field.default.kind == "literal"
        assert field.default.value == "active"

    def test_old_fields_removed(self):
        assert "server_default" not in InputField.model_fields
        assert "default_literal" not in InputField.model_fields


class TestDefaultValidation:
    """Tests for validate_server_defaults() triggered via InputAPI construction."""

    def _make_api(self, fields, db_enabled=True):
        return InputAPI(
            name="TestApi",
            objects=[InputModel(name="Thing", fields=fields)],
            endpoints=[
                InputEndpoint(
                    name="GetThings",
                    path="/things",
                    method="GET",
                    response="Thing",
                )
            ],
            config=InputApiConfig(
                database=InputDatabaseConfig(enabled=db_enabled),
            ),
        )

    def test_read_only_no_default_raises(self):
        with pytest.raises(ValueError, match="read_only field"):
            self._make_api(
                fields=[
                    InputField(name="id", type="int", pk=True, exposure="read_only"),
                    InputField(
                        name="created_at", type="datetime", exposure="read_only"
                    ),
                ]
            )

    def test_read_only_with_default_passes(self):
        api = self._make_api(
            fields=[
                InputField(name="id", type="int", pk=True, exposure="read_only"),
                InputField(
                    name="created_at",
                    type="datetime",
                    exposure="read_only",
                    default={"kind": "generated", "strategy": "now"},
                ),
            ]
        )
        assert api is not None

    def test_pk_field_exempt(self):
        api = self._make_api(
            fields=[
                InputField(name="id", type="uuid", pk=True, exposure="read_only"),
            ]
        )
        assert api is not None

    def test_database_disabled_skips_validation(self):
        api = self._make_api(
            fields=[
                InputField(name="created_at", type="datetime", exposure="read_only"),
            ],
            db_enabled=False,
        )
        assert api is not None

    def test_read_write_no_default_passes(self):
        api = self._make_api(
            fields=[
                InputField(name="id", type="int", pk=True, exposure="read_only"),
                InputField(name="name", type="str"),
            ]
        )
        assert api is not None

    def test_pk_not_read_only_raises(self):
        with pytest.raises(ValueError, match="primary key must be read_only"):
            self._make_api(
                fields=[
                    InputField(name="id", type="int", pk=True),
                ]
            )

    def test_uuid4_valid_for_uuid(self):
        api = self._make_api(
            fields=[
                InputField(name="id", type="int", pk=True, exposure="read_only"),
                InputField(
                    name="ref_id",
                    type="uuid",
                    exposure="read_only",
                    default={"kind": "generated", "strategy": "uuid4"},
                ),
            ]
        )
        assert api is not None

    def test_uuid4_invalid_for_str(self):
        with pytest.raises(ValueError, match="not compatible with type"):
            self._make_api(
                fields=[
                    InputField(name="id", type="int", pk=True, exposure="read_only"),
                    InputField(
                        name="name",
                        type="str",
                        exposure="read_only",
                        default={"kind": "generated", "strategy": "uuid4"},
                    ),
                ]
            )

    def test_now_valid_for_datetime(self):
        api = self._make_api(
            fields=[
                InputField(name="id", type="int", pk=True, exposure="read_only"),
                InputField(
                    name="created_at",
                    type="datetime",
                    exposure="read_only",
                    default={"kind": "generated", "strategy": "now"},
                ),
            ]
        )
        assert api is not None

    def test_now_on_update_valid_for_datetime(self):
        api = self._make_api(
            fields=[
                InputField(name="id", type="int", pk=True, exposure="read_only"),
                InputField(
                    name="updated_at",
                    type="datetime",
                    exposure="read_only",
                    default={"kind": "generated", "strategy": "now_on_update"},
                ),
            ]
        )
        assert api is not None

    def test_now_invalid_for_int(self):
        with pytest.raises(ValueError, match="not compatible with type"):
            self._make_api(
                fields=[
                    InputField(name="id", type="int", pk=True, exposure="read_only"),
                    InputField(
                        name="count",
                        type="int",
                        exposure="read_only",
                        default={"kind": "generated", "strategy": "now"},
                    ),
                ]
            )

    def test_auto_increment_valid_for_int(self):
        api = self._make_api(
            fields=[
                InputField(name="id", type="uuid", pk=True, exposure="read_only"),
                InputField(
                    name="seq",
                    type="int",
                    exposure="read_only",
                    default={"kind": "generated", "strategy": "auto_increment"},
                ),
            ]
        )
        assert api is not None

    def test_auto_increment_invalid_for_str(self):
        with pytest.raises(ValueError, match="not compatible with type"):
            self._make_api(
                fields=[
                    InputField(name="id", type="int", pk=True, exposure="read_only"),
                    InputField(
                        name="name",
                        type="str",
                        exposure="read_only",
                        default={"kind": "generated", "strategy": "auto_increment"},
                    ),
                ]
            )

    def test_literal_valid_for_str(self):
        api = self._make_api(
            fields=[
                InputField(name="id", type="int", pk=True, exposure="read_only"),
                InputField(
                    name="status",
                    type="str",
                    exposure="read_only",
                    default={"kind": "literal", "value": "active"},
                ),
            ]
        )
        assert api is not None

    def test_generated_on_read_write_field_validates_type_compat(self):
        with pytest.raises(ValueError, match="not compatible with type"):
            self._make_api(
                fields=[
                    InputField(name="id", type="int", pk=True, exposure="read_only"),
                    InputField(
                        name="name",
                        type="str",
                        default={"kind": "generated", "strategy": "now"},
                    ),
                ]
            )


# ---------------------------------------------------------------------------
# Name Types (from test_name_types)
# ---------------------------------------------------------------------------


class TestValidateSnakeCaseName:
    @pytest.mark.parametrize(
        "value",
        ["email", "user_email", "created_at", "field2", "a", "x1_y2_z3"],
    )
    def test_valid_snake_case(self, value: str):
        validate_snake_case_name(value)

    @pytest.mark.parametrize(
        "value,reason",
        [
            ("", "empty string"),
            ("Email", "starts with uppercase"),
            ("userEmail", "camelCase"),
            ("UserEmail", "PascalCase"),
            ("user__email", "double underscore"),
            ("_email", "leading underscore"),
            ("email_", "trailing underscore"),
            ("user-email", "contains hyphen"),
            ("user email", "contains space"),
            ("123field", "starts with digit"),
            ("user_Email", "uppercase after underscore"),
        ],
    )
    def test_invalid_snake_case(self, value: str, reason: str):
        with pytest.raises(ValueError):
            validate_snake_case_name(value)


class TestSnakeCaseName:
    def test_valid_creation(self):
        name = SnakeCaseName("user_email")
        assert name == "user_email"

    def test_single_word(self):
        name = SnakeCaseName("email")
        assert name == "email"

    def test_camel_name_single_word(self):
        name = SnakeCaseName("email")
        assert name.camel_name == "Email"

    def test_camel_name_multi_word(self):
        name = SnakeCaseName("user_email")
        assert name.camel_name == "UserEmail"

    def test_pascal_name(self):
        name = SnakeCaseName("user_email")
        assert name.pascal_name == "UserEmail"

    def test_kebab_name(self):
        name = SnakeCaseName("user_email")
        assert name.kebab_name == "user-email"

    def test_kebab_name_single_word(self):
        name = SnakeCaseName("email")
        assert name.kebab_name == "email"

    def test_rejects_camel_case(self):
        with pytest.raises(ValueError):
            SnakeCaseName("userEmail")

    def test_rejects_pascal_case(self):
        with pytest.raises(ValueError):
            SnakeCaseName("UserEmail")

    def test_rejects_empty(self):
        with pytest.raises(ValueError):
            SnakeCaseName("")

    def test_is_str_subclass(self):
        name = SnakeCaseName("email")
        assert isinstance(name, str)


class TestPascalCaseName:
    """Regression tests for PascalCaseName (renamed from Name)."""

    def test_valid_creation(self):
        name = PascalCaseName("UserEmail")
        assert name == "UserEmail"

    def test_snake_name(self):
        name = PascalCaseName("UserEmail")
        assert name.snake_name == "user_email"

    def test_camel_name(self):
        name = PascalCaseName("UserEmail")
        assert name.camel_name == "userEmail"

    def test_kebab_name(self):
        name = PascalCaseName("UserEmail")
        assert name.kebab_name == "user-email"

    def test_pascal_name_returns_self(self):
        name = PascalCaseName("UserEmail")
        assert name.pascal_name == "UserEmail"

    def test_rejects_snake_case(self):
        with pytest.raises(ValueError):
            PascalCaseName("user_email")

    def test_rejects_lowercase_start(self):
        with pytest.raises(ValueError):
            PascalCaseName("userEmail")

    def test_spaced_name(self):
        name = PascalCaseName("ShopApi")
        assert name.spaced_name == "Shop Api"

    def test_spaced_name_single_word(self):
        name = PascalCaseName("User")
        assert name.spaced_name == "User"

    def test_spaced_name_multi_word(self):
        name = PascalCaseName("UserEmailAddress")
        assert name.spaced_name == "User Email Address"

    def test_is_str_subclass(self):
        name = PascalCaseName("User")
        assert isinstance(name, str)


class TestValidateTypeAnnotation:
    @pytest.mark.parametrize(
        "type_str",
        [
            "str",
            "int",
            "float",
            "bool",
            "datetime.datetime",
            "datetime.date",
            "datetime.time",
            "uuid.UUID",
            "EmailStr",
            "HttpUrl",
            "Decimal",
            "List[str]",
            "List[datetime.date]",
            "List[uuid.UUID]",
        ],
    )
    def test_accepts_supported_type(self, type_str: str):
        validate_type_annotation(type_str, set(), context="test")

    @pytest.mark.parametrize(
        "type_str",
        ["UnknownType", "FooBar", "numpy.ndarray"],
    )
    def test_rejects_unknown_type(self, type_str: str):
        with pytest.raises(ValueError, match="Unknown type reference"):
            validate_type_annotation(type_str, set(), context="test")

    def test_accepts_declared_object_name(self):
        validate_type_annotation("MyObject", {"MyObject"}, context="test")


class TestInputModelCaseEnforcement:
    def test_input_field_accepts_snake_case(self):
        field = InputField(type="str", name="user_email")
        assert field.name == "user_email"

    def test_input_field_rejects_camel_case(self):
        with pytest.raises(ValueError):
            InputField(type="str", name="userEmail")

    def test_input_field_rejects_pascal_case(self):
        with pytest.raises(ValueError):
            InputField(type="str", name="UserEmail")

    def test_input_query_param_accepts_snake_case(self):
        param = InputQueryParam(name="page_size", type="int")
        assert param.name == "page_size"

    def test_input_query_param_rejects_camel_case(self):
        with pytest.raises(ValueError):
            InputQueryParam(name="pageSize", type="int")

    def test_input_path_param_accepts_snake_case(self):
        param = InputPathParam(name="item_id", type="int")
        assert param.name == "item_id"

    def test_input_path_param_rejects_camel_case(self):
        with pytest.raises(ValueError):
            InputPathParam(name="itemId", type="int")


# ---------------------------------------------------------------------------
# Validation Catalog (from test_validation_catalog)
# ---------------------------------------------------------------------------


class TestNamePatterns:
    def test_snake_case_accepts_valid(self):
        valid = ["user", "user_name", "a1", "field_1_value"]
        for name in valid:
            assert SNAKE_CASE_PATTERN.match(name), f"Should accept: {name}"

    def test_snake_case_rejects_invalid(self):
        invalid = [
            "User",
            "userName",
            "_user",
            "user_",
            "user__name",
            "1user",
            "user-name",
        ]
        for name in invalid:
            assert not SNAKE_CASE_PATTERN.match(name), f"Should reject: {name}"

    def test_pascal_case_accepts_valid(self):
        valid = ["User", "UserProfile", "A", "Ab", "Item1"]
        for name in valid:
            assert PASCAL_CASE_PATTERN.match(name), f"Should accept: {name}"

    def test_pascal_case_rejects_invalid(self):
        invalid = ["user", "userProfile", "UserAPI", "User_Name", "123"]
        for name in invalid:
            assert not PASCAL_CASE_PATTERN.match(name), f"Should reject: {name!r}"
        assert not PASCAL_CASE_PATTERN.match("")


class TestServerDefaultCoverage:
    def test_all_generated_strategies_have_valid_types(self):
        for sd in get_args(GeneratedStrategy):
            assert sd in SERVER_DEFAULT_VALID_TYPES, (
                f"GeneratedStrategy '{sd}' missing from SERVER_DEFAULT_VALID_TYPES"
            )


class TestOperatorCoverage:
    def test_all_operators_have_valid_types(self):
        for op in get_args(FilterOperator):
            assert op in OPERATOR_VALID_TYPES, (
                f"FilterOperator '{op}' missing from OPERATOR_VALID_TYPES"
            )


class TestPkTypes:
    def test_pk_types_are_expected(self):
        assert ALLOWED_PK_TYPES == {"int", "uuid"}


# ---------------------------------------------------------------------------
# Prepare API (from test_prepare)
# ---------------------------------------------------------------------------


@pytest.mark.codegen
class TestPrepareApi:
    @pytest.fixture(
        params=["items_api.yaml", "shop_api.yaml", "products_api_filters.yaml"]
    )
    def api_input(self, request):
        return load_input(request.param)

    def test_name_variants_are_consistent(self, api_input):
        prepared = prepare_api(api_input)
        assert prepared.snake_name == prepared.camel_name[0].lower() + "".join(
            "_" + c.lower() if c.isupper() else c for c in prepared.camel_name[1:]
        )
        assert "-" not in prepared.snake_name
        assert "_" not in prepared.kebab_name

    def test_models_non_empty(self, api_input):
        prepared = prepare_api(api_input)
        assert len(prepared.models) > 0

    def test_views_non_empty(self, api_input):
        prepared = prepare_api(api_input)
        assert len(prepared.views) > 0

    def test_view_methods_lowercase(self, api_input):
        prepared = prepare_api(api_input)
        for view in prepared.views:
            assert view.method == view.method.lower()

    def test_view_names_non_empty(self, api_input):
        prepared = prepare_api(api_input)
        for view in prepared.views:
            assert view.snake_name
            assert view.camel_name


@pytest.mark.codegen
class TestPrepareApiShop:
    def test_split_produces_six_models(self):
        api_input = load_input("shop_api.yaml")
        prepared = prepare_api(api_input)
        assert len(prepared.models) == 6

    def test_split_model_names(self):
        api_input = load_input("shop_api.yaml")
        prepared = prepare_api(api_input)
        names = [str(m.name) for m in prepared.models]
        assert "ProductCreate" in names
        assert "ProductUpdate" in names
        assert "ProductResponse" in names
        assert "CustomerCreate" in names

    def test_nine_views(self):
        api_input = load_input("shop_api.yaml")
        prepared = prepare_api(api_input)
        assert len(prepared.views) == 9

    def test_database_config_present(self):
        api_input = load_input("shop_api.yaml")
        prepared = prepare_api(api_input)
        assert prepared.database_config is not None
        assert prepared.database_config.enabled is True

    def test_orm_models_present(self):
        api_input = load_input("shop_api.yaml")
        prepared = prepare_api(api_input)
        assert len(prepared.orm_models) > 0


# ---------------------------------------------------------------------------
# Transformers (from test_transformers)
# ---------------------------------------------------------------------------


class TestTransformOrmModels:
    def test_model_without_pk_is_skipped(self):
        models = [_make_model("Item", [{"name": "name", "type": "str"}])]
        result = transform_orm_models(models)
        assert result == []

    def test_model_with_pk_is_included(self):
        models = [
            _make_model(
                "Item",
                [
                    {"name": "id", "type": "int", "pk": True},
                    {"name": "name", "type": "str"},
                ],
            )
        ]
        result = transform_orm_models(models)
        assert len(result) == 1
        assert result[0].class_name == "ItemRecord"
        assert result[0].table_name == "items"
        assert result[0].source_model == "Item"

    def test_int_pk_has_auto_increment(self):
        models = [
            _make_model(
                "Item",
                [{"name": "id", "type": "int", "pk": True}],
            )
        ]
        result = transform_orm_models(models)
        pk_field = result[0].fields[0]
        assert pk_field.primary_key is True
        assert pk_field.server_default == "auto_increment"

    def test_uuid_pk_has_uuid4_server_default(self):
        models = [
            _make_model(
                "Item",
                [{"name": "id", "type": "uuid", "pk": True}],
            )
        ]
        result = transform_orm_models(models)
        pk_field = result[0].fields[0]
        assert pk_field.primary_key is True
        assert pk_field.server_default == "uuid4"
        assert pk_field.column_type == "Uuid"

    def test_int_pk_no_uuid4_server_default(self):
        models = [
            _make_model(
                "Item",
                [{"name": "id", "type": "int", "pk": True}],
            )
        ]
        result = transform_orm_models(models)
        pk_field = result[0].fields[0]
        assert pk_field.server_default == "auto_increment"

    def test_non_pk_uuid_no_server_default(self):
        models = [
            _make_model(
                "Item",
                [
                    {"name": "id", "type": "int", "pk": True},
                    {"name": "external_id", "type": "uuid"},
                ],
            )
        ]
        result = transform_orm_models(models)
        uuid_field = result[0].fields[1]
        assert uuid_field.server_default is None


class TestTypeMapping:
    @pytest.mark.parametrize(
        "py_type,expected_col",
        [
            ("int", "Integer"),
            ("float", "Float"),
            ("bool", "Boolean"),
            ("datetime", "DateTime(timezone=True)"),
            ("datetime.date", "Date"),
            ("datetime.time", "Time"),
            ("uuid", "Uuid"),
            ("decimal", "Numeric"),
            ("HttpUrl", "Text"),
        ],
    )
    def test_simple_type_mapping(self, py_type, expected_col):
        models = [
            _make_model(
                "Item",
                [
                    {"name": "id", "type": "int", "pk": True},
                    {"name": "value", "type": py_type},
                ],
            )
        ]
        result = transform_orm_models(models)
        value_field = result[0].fields[1]
        assert value_field.column_type == expected_col

    @pytest.mark.parametrize(
        "input_type,expected_python_type",
        [
            ("int", "int"),
            ("str", "str"),
            ("float", "float"),
            ("bool", "bool"),
            ("datetime", "datetime.datetime"),
            ("datetime.date", "datetime.date"),
            ("datetime.time", "datetime.time"),
            ("uuid", "uuid.UUID"),
            ("uuid.UUID", "uuid.UUID"),
            ("decimal", "decimal.Decimal"),
            ("decimal.Decimal", "decimal.Decimal"),
        ],
    )
    def test_orm_python_type_annotation(self, input_type, expected_python_type):
        models = [
            _make_model(
                "Item",
                [
                    {"name": "id", "type": "int", "pk": True},
                    {"name": "value", "type": input_type},
                ],
            )
        ]
        result = transform_orm_models(models)
        value_field = result[0].fields[1]
        assert value_field.python_type == expected_python_type

    def test_str_without_max_length_maps_to_text(self):
        models = [
            _make_model(
                "Item",
                [
                    {"name": "id", "type": "int", "pk": True},
                    {"name": "name", "type": "str"},
                ],
            )
        ]
        result = transform_orm_models(models)
        assert result[0].fields[1].column_type == "Text"

    def test_str_with_max_length_maps_to_string_n(self):
        models = [
            _make_model(
                "Item",
                [
                    {"name": "id", "type": "int", "pk": True},
                    {
                        "name": "name",
                        "type": "str",
                        "validators": [
                            {"name": "max_length", "params": {"value": 100}}
                        ],
                    },
                ],
            )
        ]
        result = transform_orm_models(models)
        assert result[0].fields[1].column_type == "String(100)"

    def test_email_str_maps_to_string_320(self):
        models = [
            _make_model(
                "Item",
                [
                    {"name": "id", "type": "int", "pk": True},
                    {"name": "email", "type": "EmailStr"},
                ],
            )
        ]
        result = transform_orm_models(models)
        assert result[0].fields[1].column_type == "String(320)"

    def test_nullable_field_is_nullable(self):
        models = [
            _make_model(
                "Item",
                [
                    {"name": "id", "type": "int", "pk": True},
                    {"name": "description", "type": "str", "nullable": True},
                ],
            )
        ]
        result = transform_orm_models(models)
        assert result[0].fields[1].nullable is True

    def test_list_field_is_skipped(self):
        models = [
            _make_model(
                "Item",
                [
                    {"name": "id", "type": "int", "pk": True},
                    {"name": "tags", "type": "List[str]"},
                ],
            )
        ]
        result = transform_orm_models(models)
        assert len(result[0].fields) == 1


class TestSnakeToPlural:
    @pytest.mark.parametrize(
        "input_name,expected",
        [
            ("Item", "items"),
            ("OrderItem", "order_items"),
            ("Category", "categories"),
            ("Status", "statuses"),
            ("Address", "addresses"),
        ],
    )
    def test_pluralize(self, input_name, expected):
        assert snake_to_plural(camel_to_snake(input_name)) == expected


class TestCollectOrmImports:
    def test_collects_column_types(self):
        models = [
            TemplateORMModel(
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
                    TemplateORMField(
                        name="name", python_type="str", column_type="Text"
                    ),
                    TemplateORMField(
                        name="price", python_type="float", column_type="Float"
                    ),
                ],
            )
        ]
        imports = collect_orm_imports(models)
        assert "Integer" in imports
        assert "Text" in imports
        assert "Float" in imports

    def test_deduplicates_imports(self):
        models = [
            TemplateORMModel(
                class_name="ItemRecord",
                table_name="items",
                source_model="Item",
                fields=[
                    TemplateORMField(
                        name="a", python_type="int", column_type="Integer"
                    ),
                    TemplateORMField(
                        name="b", python_type="int", column_type="Integer"
                    ),
                ],
            )
        ]
        imports = collect_orm_imports(models)
        assert imports.count("Integer") == 1


class TestCollectDatabaseDependencies:
    def test_returns_required_deps(self):
        deps = collect_database_dependencies()
        dep_names = [d.split(" ")[0] for d in deps]
        assert "sqlalchemy[asyncio]" in dep_names
        assert "asyncpg" in dep_names
        assert "alembic" in dep_names


class TestOrmBuilderServerDefaults:
    def test_uuid_pk_sets_uuid4_server_default(self):
        model = InputModel(
            name="Thing",
            fields=[InputField(name="id", type="uuid", pk=True)],
        )
        orm_models = transform_orm_models([model])
        id_field = orm_models[0].fields[0]
        assert id_field.server_default == "uuid4"
        assert id_field.on_update is None

    def test_int_pk_sets_auto_increment_server_default(self):
        model = InputModel(
            name="Thing",
            fields=[InputField(name="id", type="int", pk=True)],
        )
        orm_models = transform_orm_models([model])
        id_field = orm_models[0].fields[0]
        assert id_field.server_default == "auto_increment"
        assert id_field.on_update is None

    def test_now_generated_default(self):
        model = InputModel(
            name="Thing",
            fields=[
                InputField(name="id", type="int", pk=True),
                InputField(
                    name="created_at",
                    type="datetime",
                    exposure="read_only",
                    default={"kind": "generated", "strategy": "now"},
                ),
            ],
        )
        orm_models = transform_orm_models([model])
        created_field = orm_models[0].fields[1]
        assert created_field.server_default == "now"
        assert created_field.on_update is None

    def test_now_on_update_splits_into_server_default_and_on_update(self):
        model = InputModel(
            name="Thing",
            fields=[
                InputField(name="id", type="int", pk=True),
                InputField(
                    name="updated_at",
                    type="datetime",
                    exposure="read_only",
                    default={"kind": "generated", "strategy": "now_on_update"},
                ),
            ],
        )
        orm_models = transform_orm_models([model])
        updated_field = orm_models[0].fields[1]
        assert updated_field.server_default == "now"
        assert updated_field.on_update == "now"

    def test_literal_default(self):
        model = InputModel(
            name="Thing",
            fields=[
                InputField(name="id", type="int", pk=True),
                InputField(
                    name="status",
                    type="str",
                    exposure="read_only",
                    default={"kind": "literal", "value": "active"},
                ),
            ],
        )
        orm_models = transform_orm_models([model])
        status_field = orm_models[0].fields[1]
        assert status_field.server_default == "literal"
        assert status_field.default_literal == "'active'"

    def test_auto_increment_non_pk(self):
        model = InputModel(
            name="Thing",
            fields=[
                InputField(name="id", type="uuid", pk=True),
                InputField(
                    name="seq",
                    type="int",
                    exposure="read_only",
                    default={"kind": "generated", "strategy": "auto_increment"},
                ),
            ],
        )
        orm_models = transform_orm_models([model])
        seq_field = orm_models[0].fields[1]
        assert seq_field.server_default == "auto_increment"

    def test_no_default_for_regular_field(self):
        model = InputModel(
            name="Thing",
            fields=[
                InputField(name="id", type="int", pk=True),
                InputField(name="name", type="str"),
            ],
        )
        orm_models = transform_orm_models([model])
        name_field = orm_models[0].fields[1]
        assert name_field.server_default is None
        assert name_field.on_update is None
        assert name_field.default_literal is None


@pytest.mark.codegen
class TestTransformApiWithDatabase:
    def test_database_disabled_no_orm_models(self):
        api = InputAPI(
            name="TestApi",
            endpoints=[
                InputEndpoint(
                    name="GetItems", path="/items", method="GET", response="Item"
                )
            ],
            objects=[
                _make_model(
                    "Item",
                    [
                        {
                            "name": "id",
                            "type": "int",
                            "pk": True,
                            "exposure": "read_only",
                        },
                        {"name": "name", "type": "str"},
                    ],
                )
            ],
            config=InputApiConfig(database={"enabled": False}),
        )
        result = prepare_api(api)
        assert result.orm_models == []
        assert result.database_config is None

    def test_database_enabled_produces_orm_models(self):
        api = InputAPI(
            name="TestApi",
            endpoints=[
                InputEndpoint(
                    name="GetItems", path="/items", method="GET", response="Item"
                )
            ],
            objects=[
                _make_model(
                    "Item",
                    [
                        {
                            "name": "id",
                            "type": "int",
                            "pk": True,
                            "exposure": "read_only",
                        },
                        {"name": "name", "type": "str"},
                    ],
                )
            ],
            config=InputApiConfig(
                database={"enabled": True}, response_placeholders=False
            ),
        )
        result = prepare_api(api)
        assert len(result.orm_models) == 1
        assert result.orm_models[0].class_name == "ItemRecord"
        assert result.database_config is not None
        assert result.database_config.enabled is True

    def test_database_config_default_url_uses_api_name(self):
        api = InputAPI(
            name="ShopApi",
            endpoints=[
                InputEndpoint(
                    name="GetItems", path="/items", method="GET", response="Item"
                )
            ],
            objects=[
                _make_model(
                    "Item",
                    [
                        {
                            "name": "id",
                            "type": "int",
                            "pk": True,
                            "exposure": "read_only",
                        },
                        {"name": "name", "type": "str"},
                    ],
                )
            ],
            config=InputApiConfig(
                database={"enabled": True}, response_placeholders=False
            ),
        )
        result = prepare_api(api)
        assert "shop_api" in result.database_config.default_url

    def test_mixed_mode_only_uses_placeholders_for_non_orm_views(self):
        api = InputAPI(
            name="MixedApi",
            endpoints=[
                InputEndpoint(
                    name="GetItems",
                    path="/items",
                    method="GET",
                    response="Item",
                    response_shape="list",
                ),
                InputEndpoint(
                    name="GetStatus",
                    path="/status",
                    method="GET",
                    response="StatusResponse",
                ),
            ],
            objects=[
                _make_model(
                    "Item",
                    [
                        {
                            "name": "id",
                            "type": "int",
                            "pk": True,
                            "exposure": "read_only",
                        },
                        {"name": "name", "type": "str"},
                    ],
                ),
                _make_model(
                    "StatusResponse",
                    [
                        {"name": "status", "type": "str"},
                        {"name": "version", "type": "str"},
                    ],
                ),
            ],
            config=InputApiConfig(
                database={"enabled": True},
                response_placeholders=True,
            ),
        )

        result = prepare_api(api)
        items_view = next(view for view in result.views if view.snake_name == "get_items")
        status_view = next(
            view for view in result.views if view.snake_name == "get_status"
        )

        assert items_view.has_orm is True
        assert items_view.response_placeholders is None
        assert "    session: AsyncSession = Depends(get_session)," in (
            items_view.signature_lines
        )

        assert status_view.has_orm is False
        assert status_view.response_placeholders is not None
        assert set(status_view.response_placeholders) == {"status", "version"}
        assert "    session: AsyncSession = Depends(get_session)," not in (
            status_view.signature_lines
        )


@pytest.mark.codegen
class TestDatabaseValidation:
    def test_database_enabled_without_pk_raises(self):
        with pytest.raises(ValueError, match="primary key"):
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
                    database={"enabled": True}, response_placeholders=False
                ),
            )

    def test_database_enabled_with_pk_succeeds(self):
        api_input = InputAPI(
            name="TestApi",
            objects=[
                InputModel(
                    name="Item",
                    fields=[
                        InputField(
                            name="id", type="int", pk=True, exposure="read_only"
                        ),
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
                database={"enabled": True}, response_placeholders=False
            ),
        )
        result = prepare_api(api_input)
        assert result.database_config is not None
        assert len(result.orm_models) == 1


# ---------------------------------------------------------------------------
# Appears / Schema Splitting (from test_appears)
# ---------------------------------------------------------------------------


class TestSplitModelSchemas:
    def test_basic_split_produces_three_schemas(self):
        model = InputModel(
            name="User",
            fields=[
                _make_field("email"),
                _make_field("password", exposure="write_only"),
                _make_field("created_at", type_="datetime", exposure="read_only"),
                _make_field("id", type_="int", pk=True, exposure="read_only"),
            ],
        )
        schemas = split_model_schemas(model)
        assert len(schemas) == 3
        assert schemas[0].name == "UserCreate"
        assert schemas[1].name == "UserUpdate"
        assert schemas[2].name == "UserResponse"

    def test_pk_excluded_from_create_and_update(self):
        model = InputModel(
            name="Item",
            fields=[
                _make_field("id", type_="int", pk=True, exposure="read_only"),
                _make_field("name"),
            ],
        )
        schemas = split_model_schemas(model)
        create_names = [f.name for f in schemas[0].fields]
        update_names = [f.name for f in schemas[1].fields]
        response_names = [f.name for f in schemas[2].fields]

        assert "id" not in create_names
        assert "id" not in update_names
        assert "id" in response_names

    def test_write_only_field_excluded_from_response(self):
        model = InputModel(
            name="Account",
            fields=[
                _make_field("username"),
                _make_field("password", exposure="write_only"),
            ],
        )
        schemas = split_model_schemas(model)
        response_names = [f.name for f in schemas[2].fields]
        create_names = [f.name for f in schemas[0].fields]

        assert "password" in create_names
        assert "password" not in response_names

    def test_read_only_field_excluded_from_create(self):
        model = InputModel(
            name="Post",
            fields=[
                _make_field("title"),
                _make_field("created_at", type_="datetime", exposure="read_only"),
            ],
        )
        schemas = split_model_schemas(model)
        create_names = [f.name for f in schemas[0].fields]
        response_names = [f.name for f in schemas[2].fields]

        assert "created_at" not in create_names
        assert "created_at" in response_names

    def test_update_fields_are_all_nullable(self):
        model = InputModel(
            name="Product",
            fields=[
                _make_field("name"),
                _make_field("price", type_="float"),
            ],
        )
        schemas = split_model_schemas(model)
        update_schema = schemas[1]
        for field in update_schema.fields:
            assert field.nullable is True, (
                f"Update field '{field.name}' should be nullable"
            )

    def test_read_write_appears_in_all_schemas(self):
        model = InputModel(
            name="Tag",
            fields=[
                _make_field("label", exposure="read_write"),
            ],
        )
        schemas = split_model_schemas(model)
        assert len(schemas[0].fields) == 1
        assert len(schemas[1].fields) == 1
        assert len(schemas[2].fields) == 1


@pytest.mark.codegen
class TestTransformApiWithAppears:
    def _make_api(self, objects, endpoints):
        return InputAPI(
            name="TestApi",
            objects=objects,
            endpoints=endpoints,
        )

    def test_split_mode_activates_when_pk_present(self):
        api = self._make_api(
            objects=[
                InputModel(
                    name="Widget",
                    fields=[
                        _make_field("id", type_="int", pk=True, exposure="read_only"),
                        _make_field("name"),
                    ],
                )
            ],
            endpoints=[
                InputEndpoint(
                    name="GetWidgets",
                    path="/widgets",
                    method="GET",
                    response="Widget",
                )
            ],
        )
        prepared = prepare_api(api)
        model_names = [str(m.name) for m in prepared.models]
        assert "WidgetCreate" in model_names
        assert "WidgetUpdate" in model_names
        assert "WidgetResponse" in model_names
        assert "Widget" not in model_names

    def test_response_model_remapped_to_response_schema(self):
        api = self._make_api(
            objects=[
                InputModel(
                    name="Item",
                    fields=[
                        _make_field("id", type_="int", pk=True, exposure="read_only"),
                        _make_field("title"),
                    ],
                )
            ],
            endpoints=[
                InputEndpoint(
                    name="GetItems",
                    path="/items",
                    method="GET",
                    response="Item",
                )
            ],
        )
        prepared = prepare_api(api)
        view = prepared.views[0]
        assert view.response_model == "ItemResponse"

    def test_post_request_uses_create_schema(self):
        api = self._make_api(
            objects=[
                InputModel(
                    name="Task",
                    fields=[
                        _make_field("id", type_="int", pk=True, exposure="read_only"),
                        _make_field("title"),
                    ],
                )
            ],
            endpoints=[
                InputEndpoint(
                    name="CreateTask",
                    path="/tasks",
                    method="POST",
                    request="Task",
                    response="Task",
                )
            ],
        )
        prepared = prepare_api(api)
        view = prepared.views[0]
        assert view.request_model == "TaskCreate"
        assert view.response_model == "TaskResponse"

    def test_put_request_uses_update_schema(self):
        api = self._make_api(
            objects=[
                InputModel(
                    name="Task",
                    fields=[
                        _make_field("id", type_="int", pk=True, exposure="read_only"),
                        _make_field("title"),
                    ],
                )
            ],
            endpoints=[
                InputEndpoint(
                    name="UpdateTask",
                    path="/tasks/{id}",
                    method="PUT",
                    request="Task",
                    response="Task",
                    path_params=[{"name": "id", "type": "int"}],
                )
            ],
        )
        prepared = prepare_api(api)
        view = prepared.views[0]
        assert view.request_model == "TaskUpdate"

    def test_patch_request_uses_update_schema(self):
        api = self._make_api(
            objects=[
                InputModel(
                    name="Task",
                    fields=[
                        _make_field("id", type_="int", pk=True, exposure="read_only"),
                        _make_field("title"),
                    ],
                )
            ],
            endpoints=[
                InputEndpoint(
                    name="PatchTask",
                    path="/tasks/{id}",
                    method="PATCH",
                    request="Task",
                    response="Task",
                    path_params=[{"name": "id", "type": "int"}],
                )
            ],
        )
        prepared = prepare_api(api)
        view = prepared.views[0]
        assert view.request_model == "TaskUpdate"

    def test_no_split_when_no_exposure_or_pk(self):
        api = self._make_api(
            objects=[
                InputModel(
                    name="Simple",
                    fields=[_make_field("name")],
                )
            ],
            endpoints=[
                InputEndpoint(
                    name="GetSimple",
                    path="/simple",
                    method="GET",
                    response="Simple",
                )
            ],
        )
        prepared = prepare_api(api)
        model_names = [str(m.name) for m in prepared.models]
        assert "Simple" in model_names
        assert "SimpleCreate" not in model_names


# ---------------------------------------------------------------------------
# Placeholders (from test_placeholders)
# ---------------------------------------------------------------------------


class TestParseType:
    def test_simple_types(self):
        assert parse_type("str") == ("str", [])
        assert parse_type("int") == ("int", [])
        assert parse_type("float") == ("float", [])
        assert parse_type("bool") == ("bool", [])

    def test_list_types(self):
        assert parse_type("List[str]") == ("List", ["str"])
        assert parse_type("List[int]") == ("List", ["int"])
        assert parse_type("List[Item]") == ("List", ["Item"])

    def test_nested_list_types(self):
        assert parse_type("List[List[str]]") == ("List", ["List[str]"])
        assert parse_type("List[List[List[int]]]") == ("List", ["List[List[int]]"])

    def test_dict_types(self):
        assert parse_type("Dict[str, int]") == ("Dict", ["str", "int"])
        assert parse_type("Dict[str, List[int]]") == ("Dict", ["str", "List[int]"])

    def test_optional_types(self):
        assert parse_type("Optional[str]") == ("Optional", ["str"])
        assert parse_type("Optional[Item]") == ("Optional", ["Item"])

    def test_union_syntax(self):
        assert parse_type("str | None") == ("Optional", ["str"])
        assert parse_type("None | str") == ("Optional", ["str"])
        assert parse_type("Item | None") == ("Optional", ["Item"])

    def test_complex_nested(self):
        assert parse_type("Dict[str, Dict[str, int]]") == (
            "Dict",
            ["str", "Dict[str, int]"],
        )
        assert parse_type("List[Dict[str, int]]") == ("List", ["Dict[str, int]"])


class TestExtractConstraints:
    def test_empty_validators(self):
        assert extract_constraints([]) == {}

    def test_single_constraint(self):
        validators = [TemplateValidator(name="min_length", params={"value": 3})]
        assert extract_constraints(validators) == {"min_length": 3}

    def test_multiple_constraints(self):
        validators = [
            TemplateValidator(name="ge", params={"value": 0}),
            TemplateValidator(name="le", params={"value": 100}),
            TemplateValidator(name="multiple_of", params={"value": 5}),
        ]
        assert extract_constraints(validators) == {"ge": 0, "le": 100, "multiple_of": 5}

    def test_validator_without_value(self):
        validators = [TemplateValidator(name="some_validator", params=None)]
        assert extract_constraints(validators) == {}


class TestGenerateString:
    def test_basic_string(self):
        result = generate_string(1, {})
        assert isinstance(result, str)
        assert len(result) >= 1

    def test_min_length(self):
        result = generate_string(1, {"min_length": 20})
        assert len(result) >= 20

    def test_max_length(self):
        result = generate_string(1, {"max_length": 5})
        assert len(result) <= 5

    def test_pattern_sku(self):
        result = generate_string(1, {"pattern": "^[A-Z0-9-]+$"})
        assert result.isupper() or "-" in result or result.isalnum()

    def test_pattern_email(self):
        result = generate_string(1, {"pattern": "email"})
        assert "@" in result


class TestGenerateInt:
    def test_basic_int(self):
        result = generate_int(1, {})
        assert isinstance(result, int)

    def test_ge_constraint(self):
        result = generate_int(1, {"ge": 10})
        assert result >= 10

    def test_gt_constraint(self):
        result = generate_int(1, {"gt": 10})
        assert result > 10

    def test_le_constraint(self):
        result = generate_int(1, {"le": 5})
        assert result <= 5

    def test_lt_constraint(self):
        result = generate_int(1, {"lt": 5})
        assert result < 5

    def test_multiple_of(self):
        result = generate_int(1, {"multiple_of": 5})
        assert result % 5 == 0

    def test_multiple_of_with_range(self):
        result = generate_int(1, {"ge": 0, "le": 100, "multiple_of": 5})
        assert result >= 0
        assert result <= 100
        assert result % 5 == 0


class TestGenerateFloat:
    def test_basic_float(self):
        result = generate_float(1, {})
        assert isinstance(result, float)

    def test_ge_constraint(self):
        result = generate_float(1, {"ge": 10.0})
        assert result >= 10.0

    def test_gt_constraint(self):
        result = generate_float(1, {"gt": 0})
        assert result > 0

    def test_le_constraint(self):
        result = generate_float(1, {"le": 5.0})
        assert result <= 5.0


class TestGenerateBool:
    def test_alternates(self):
        assert generate_bool(1) is True
        assert generate_bool(2) is False
        assert generate_bool(3) is True


class TestGenerateDatetime:
    def test_format(self):
        result = generate_datetime(1)
        assert "T" in result
        assert len(result) == 19


class TestGenerateDate:
    def test_format(self):
        result = generate_date(1)
        assert "-" in result
        assert len(result) == 10


class TestGenerateUUID:
    def test_format(self):
        result = generate_uuid(1)
        parts = result.split("-")
        assert len(parts) == 5
        assert len(result) == 36


class TestPlaceholderGenerator:
    @pytest.fixture
    def simple_models(self):
        return {
            "Item": [
                TemplateField(
                    type="int",
                    name="id",
                    nullable=False,
                    validators=[TemplateValidator(name="ge", params={"value": 1})],
                ),
                TemplateField(
                    type="str",
                    name="name",
                    nullable=False,
                    validators=[
                        TemplateValidator(name="min_length", params={"value": 1})
                    ],
                ),
                TemplateField(
                    type="float",
                    name="price",
                    nullable=False,
                    validators=[TemplateValidator(name="gt", params={"value": 0})],
                ),
                TemplateField(
                    type="str", name="description", nullable=True, validators=[]
                ),
            ]
        }

    @pytest.fixture
    def nested_models(self):
        return {
            "Address": [
                TemplateField(type="str", name="street", nullable=False, validators=[]),
                TemplateField(type="str", name="city", nullable=False, validators=[]),
            ],
            "Person": [
                TemplateField(type="str", name="name", nullable=False, validators=[]),
                TemplateField(
                    type="Address", name="address", nullable=False, validators=[]
                ),
            ],
        }

    @pytest.fixture
    def list_models(self):
        return {
            "Tag": [
                TemplateField(type="str", name="name", nullable=False, validators=[]),
            ],
            "Article": [
                TemplateField(type="str", name="title", nullable=False, validators=[]),
                TemplateField(
                    type="List[Tag]", name="tags", nullable=False, validators=[]
                ),
            ],
        }

    def test_simple_model(self, simple_models):
        generator = PlaceholderGenerator(simple_models)
        result = generator.generate_for_model("Item")

        assert "id" in result
        assert "name" in result
        assert "price" in result
        assert "description" not in result

        assert isinstance(result["id"], int)
        assert result["id"] >= 1

        assert isinstance(result["name"], str)
        assert len(result["name"]) >= 1

        assert isinstance(result["price"], float)
        assert result["price"] > 0

    def test_nested_model(self, nested_models):
        generator = PlaceholderGenerator(nested_models)
        result = generator.generate_for_model("Person")

        assert "name" in result
        assert "address" in result
        assert isinstance(result["address"], dict)
        assert "street" in result["address"]
        assert "city" in result["address"]

    def test_list_field(self, list_models):
        generator = PlaceholderGenerator(list_models)
        result = generator.generate_for_model("Article")

        assert "title" in result
        assert "tags" in result
        assert isinstance(result["tags"], list)
        assert len(result["tags"]) == 2
        assert isinstance(result["tags"][0], dict)
        assert "name" in result["tags"][0]

    def test_unknown_model(self, simple_models):
        generator = PlaceholderGenerator(simple_models)
        result = generator.generate_for_model("Unknown")
        assert result == {}

    def test_circular_reference(self):
        circular_models = {
            "Node": [
                TemplateField(type="str", name="value", nullable=False, validators=[]),
                TemplateField(type="Node", name="child", nullable=False, validators=[]),
            ]
        }
        generator = PlaceholderGenerator(circular_models)
        result = generator.generate_for_model("Node")

        assert "value" in result
        assert "child" in result
        assert result["child"] == {}


class TestComplexTypes:
    def test_list_of_primitives(self):
        models = {
            "Numbers": [
                TemplateField(
                    type="List[int]", name="values", nullable=False, validators=[]
                ),
            ]
        }
        generator = PlaceholderGenerator(models)
        result = generator.generate_for_model("Numbers")

        assert isinstance(result["values"], list)
        assert all(isinstance(v, int) for v in result["values"])

    def test_dict_type(self):
        models = {
            "Config": [
                TemplateField(
                    type="Dict[str, int]",
                    name="settings",
                    nullable=False,
                    validators=[],
                ),
            ]
        }
        generator = PlaceholderGenerator(models)
        result = generator.generate_for_model("Config")

        assert isinstance(result["settings"], dict)
        assert len(result["settings"]) == 1

    def test_optional_type(self):
        models = {
            "Item": [
                TemplateField(
                    type="str | None", name="value", nullable=False, validators=[]
                ),
            ]
        }
        generator = PlaceholderGenerator(models)
        result = generator.generate_for_model("Item")

        assert isinstance(result["value"], str)

    def test_nested_list(self):
        models = {
            "Matrix": [
                TemplateField(
                    type="List[List[int]]", name="rows", nullable=False, validators=[]
                ),
            ]
        }
        generator = PlaceholderGenerator(models)
        result = generator.generate_for_model("Matrix")

        assert isinstance(result["rows"], list)
        assert isinstance(result["rows"][0], list)
        assert isinstance(result["rows"][0][0], int)


# ---------------------------------------------------------------------------
# Generate Options Schema (from test_schemas + test_generation_unit)
# ---------------------------------------------------------------------------


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


class TestGenerateOptionsSchema:
    def test_database_with_placeholders_passes(self):
        opts = GenerateOptions(
            database_enabled=True,
            response_placeholders=True,
        )
        assert opts.database_enabled is True
        assert opts.response_placeholders is True

    def test_database_without_placeholders_passes(self):
        opts = GenerateOptions(
            database_enabled=True,
            response_placeholders=False,
        )
        assert opts.database_enabled is True
        assert opts.response_placeholders is False

    def test_placeholders_without_database_passes(self):
        opts = GenerateOptions(
            database_enabled=False,
            response_placeholders=True,
        )
        assert opts.response_placeholders is True

    def test_default_values_pass(self):
        opts = GenerateOptions()
        assert opts.database_enabled is False
        assert opts.response_placeholders is True


# ---------------------------------------------------------------------------
# Enum Check Consistency (from test_enum_check_consistency)
# ---------------------------------------------------------------------------

ENUM_CHECK_PAIRS = [
    (Container, "container", "fields"),
    (FieldRole, "role", "fields_on_objects"),
    (Cardinality, "cardinality", "object_relationships"),
    (HttpMethod, "method", "api_endpoints"),
    (ResponseShape, "response_shape", "api_endpoints"),
    (ValidatorMode, "mode", "field_validator_templates"),
]


class TestEnumCheckConsistency:
    @pytest.mark.parametrize(
        "literal_type,column,table",
        ENUM_CHECK_PAIRS,
        ids=[f"{t[2]}.{t[1]}" for t in ENUM_CHECK_PAIRS],
    )
    def test_check_constraint_sql_produces_valid_output(
        self, literal_type, column, table
    ):
        sql = check_constraint_sql(column, literal_type)
        values = get_args(literal_type)
        for val in values:
            assert f"'{val}'" in sql, (
                f"Value '{val}' missing from CHECK SQL for {table}.{column}"
            )
        assert sql.startswith(f"{column} IN (")

    def test_field_role_check_contains_all_values(self):
        sql = check_constraint_sql("role", FieldRole)
        assert "role IN (" in sql
        for value in (
            "pk",
            "fk",
            "writable",
            "write_only",
            "read_only",
            "created_timestamp",
            "updated_timestamp",
            "generated_uuid",
        ):
            assert f"'{value}'" in sql
