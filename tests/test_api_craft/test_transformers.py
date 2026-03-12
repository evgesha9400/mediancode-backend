# tests/test_api_craft/test_transformers.py
"""Tests for ORM model transformation."""

import pytest
from api_craft.models.input import InputField, InputModel
from api_craft.models.template import TemplateORMModel
from api_craft.transformers import transform_orm_models


def _make_model(name, fields):
    return InputModel(name=name, fields=[InputField(**f) for f in fields])


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

    def test_int_pk_has_autoincrement(self):
        models = [
            _make_model(
                "Item",
                [
                    {"name": "id", "type": "int", "pk": True},
                ],
            )
        ]
        result = transform_orm_models(models)
        pk_field = result[0].fields[0]
        assert pk_field.primary_key is True
        assert pk_field.autoincrement is True

    def test_uuid_pk_has_uuid_default(self):
        models = [
            _make_model(
                "Item",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                ],
            )
        ]
        result = transform_orm_models(models)
        pk_field = result[0].fields[0]
        assert pk_field.primary_key is True
        assert pk_field.autoincrement is False
        assert pk_field.uuid_default is True
        assert pk_field.column_type == "Uuid"

    def test_int_pk_no_uuid_default(self):
        models = [
            _make_model(
                "Item",
                [
                    {"name": "id", "type": "int", "pk": True},
                ],
            )
        ]
        result = transform_orm_models(models)
        pk_field = result[0].fields[0]
        assert pk_field.uuid_default is False

    def test_non_pk_uuid_no_uuid_default(self):
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
        assert uuid_field.uuid_default is False


class TestTypeMapping:
    """Test Python type -> SQLAlchemy column type mapping."""

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

    def test_optional_field_is_nullable(self):
        models = [
            _make_model(
                "Item",
                [
                    {"name": "id", "type": "int", "pk": True},
                    {"name": "description", "type": "str", "optional": True},
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
        assert len(result[0].fields) == 1  # only id, tags skipped


class TestSnakeToPlural:
    """Test table name pluralization."""

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
        from api_craft.utils import snake_to_plural, camel_to_snake

        assert snake_to_plural(camel_to_snake(input_name)) == expected


from api_craft.extractors import collect_orm_imports, collect_database_dependencies
from api_craft.models.template import TemplateORMField, TemplateORMModel


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


from api_craft.models.input import InputAPI, InputEndpoint, InputApiConfig
from api_craft.transformers import transform_api


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
                        {"name": "id", "type": "int", "pk": True},
                        {"name": "name", "type": "str"},
                    ],
                )
            ],
            config=InputApiConfig(database={"enabled": False}),
        )
        result = transform_api(api)
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
                        {"name": "id", "type": "int", "pk": True},
                        {"name": "name", "type": "str"},
                    ],
                )
            ],
            config=InputApiConfig(
                database={"enabled": True}, response_placeholders=False
            ),
        )
        result = transform_api(api)
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
                        {"name": "id", "type": "int", "pk": True},
                        {"name": "name", "type": "str"},
                    ],
                )
            ],
            config=InputApiConfig(
                database={"enabled": True}, response_placeholders=False
            ),
        )
        result = transform_api(api)
        assert "shop_api" in result.database_config.default_url


class TestDatabaseValidation:
    def test_database_enabled_without_pk_raises(self):
        """Database generation with no PK fields must raise ValueError."""
        with pytest.raises(ValueError, match="primary key"):
            InputAPI(
                name="TestApi",
                objects=[
                    InputModel(
                        name="Item",
                        fields=[
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

    def test_database_enabled_with_pk_succeeds(self):
        """Database generation with a PK field must succeed."""
        api_input = InputAPI(
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
                database={"enabled": True}, response_placeholders=False
            ),
        )
        result = transform_api(api_input)
        assert result.database_config is not None
        assert len(result.orm_models) == 1
