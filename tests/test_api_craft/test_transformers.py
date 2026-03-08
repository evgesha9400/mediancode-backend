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

    def test_uuid_pk_no_autoincrement(self):
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
        assert pk_field.column_type == "Uuid"


class TestTypeMapping:
    """Test Python type -> SQLAlchemy column type mapping."""

    @pytest.mark.parametrize(
        "py_type,expected_col",
        [
            ("int", "Integer"),
            ("float", "Float"),
            ("bool", "Boolean"),
            ("datetime", "DateTime"),
            ("date", "Date"),
            ("time", "Time"),
            ("uuid", "Uuid"),
            ("Decimal", "Numeric"),
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


class TestForeignKeyTransform:
    def test_fk_field_resolved(self):
        models = [
            _make_model(
                "Order",
                [
                    {"name": "id", "type": "int", "pk": True},
                ],
            ),
            _make_model(
                "OrderItem",
                [
                    {"name": "id", "type": "int", "pk": True},
                    {
                        "name": "order_id",
                        "type": "int",
                        "fk": "Order",
                        "on_delete": "cascade",
                    },
                ],
            ),
        ]
        result = transform_orm_models(models)
        order_item = next(m for m in result if m.class_name == "OrderItemRecord")
        fk_field = next(f for f in order_item.fields if f.name == "order_id")
        assert fk_field.foreign_key == "orders.id"
        assert fk_field.on_delete == "CASCADE"

    def test_fk_on_delete_restrict(self):
        models = [
            _make_model("Order", [{"name": "id", "type": "int", "pk": True}]),
            _make_model(
                "OrderItem",
                [
                    {"name": "id", "type": "int", "pk": True},
                    {
                        "name": "order_id",
                        "type": "int",
                        "fk": "Order",
                        "on_delete": "restrict",
                    },
                ],
            ),
        ]
        result = transform_orm_models(models)
        order_item = next(m for m in result if m.class_name == "OrderItemRecord")
        fk_field = next(f for f in order_item.fields if f.name == "order_id")
        assert fk_field.on_delete == "RESTRICT"

    def test_fk_on_delete_set_null(self):
        models = [
            _make_model("Order", [{"name": "id", "type": "int", "pk": True}]),
            _make_model(
                "OrderItem",
                [
                    {"name": "id", "type": "int", "pk": True},
                    {
                        "name": "order_id",
                        "type": "int",
                        "fk": "Order",
                        "on_delete": "set_null",
                    },
                ],
            ),
        ]
        result = transform_orm_models(models)
        order_item = next(m for m in result if m.class_name == "OrderItemRecord")
        fk_field = next(f for f in order_item.fields if f.name == "order_id")
        assert fk_field.on_delete == "SET NULL"


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
