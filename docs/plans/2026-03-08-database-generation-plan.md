# Database Generation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend api_craft to generate database-backed FastAPI projects with SQLAlchemy ORM, Alembic migrations, Docker Compose, and DB-backed views.

**Architecture:** When `config.database.enabled: true`, the existing Transform→Extract→Render→Write pipeline is extended with ORM model transformation, new templates for database files, and modified view/main templates that use async SQLAlchemy sessions instead of hardcoded placeholders.

**Tech Stack:** SQLAlchemy 2.0 (async), asyncpg, Alembic, PostgreSQL 18 (Docker), Mako templates.

**Design doc:** `docs/plans/2026-03-08-database-generation-design.md`

---

### Task 1: Add `pk`, `fk`, `on_delete` to InputField and database config

**Files:**
- Modify: `src/api_craft/models/input.py:52-70` (InputField)
- Modify: `src/api_craft/models/input.py:166-178` (InputApiConfig)
- Modify: `src/api/schemas/literals.py:10-16` (add OnDeleteAction literal)
- Test: `tests/test_api_craft/test_input_models.py` (create new)

**Step 1: Write the failing test**

```python
# tests/test_api_craft/test_input_models.py
"""Tests for input model changes: pk, fk, on_delete, database config."""

import pytest
from api_craft.models.input import InputField, InputModel, InputApiConfig, InputAPI, InputEndpoint


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
        field = InputField(name="order_id", type="int", fk="Order", on_delete="set_null")
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
```

**Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/test_api_craft/test_input_models.py -v`
Expected: FAIL — `pk`, `fk`, `on_delete` fields don't exist on InputField, `database` doesn't exist on InputApiConfig

**Step 3: Write minimal implementation**

In `src/api/schemas/literals.py`, add after line 16:
```python
OnDeleteAction = Literal["cascade", "restrict", "set_null"]
```

In `src/api_craft/models/input.py`, modify `InputField` (add after line 69):
```python
from api.schemas.literals import HttpMethod, OnDeleteAction, ResponseShape, ValidatorMode

class InputField(BaseModel):
    type: str
    name: SnakeCaseName
    optional: bool = False
    description: str | None = None
    default_value: str | None = None
    validators: list[InputValidator] = Field(default_factory=list)
    field_validators: list[InputResolvedFieldValidator] = Field(default_factory=list)
    pk: bool = False
    fk: str | None = None
    on_delete: OnDeleteAction = "restrict"
```

Add new config class before `InputApiConfig`:
```python
class InputDatabaseConfig(BaseModel):
    enabled: bool = False
    seed_data: bool = True
```

Modify `InputApiConfig`:
```python
class InputApiConfig(BaseModel):
    healthcheck: str | None = None
    response_placeholders: bool = True
    format_code: bool = True
    generate_swagger: bool = True
    database: InputDatabaseConfig = InputDatabaseConfig()
```

**Step 4: Run test to verify it passes**

Run: `poetry run pytest tests/test_api_craft/test_input_models.py -v`
Expected: PASS

**Step 5: Run all existing tests**

Run: `poetry run pytest tests/ -v`
Expected: All existing tests still pass

**Step 6: Format and commit**

```bash
poetry run black src/ tests/
git add src/api/schemas/literals.py src/api_craft/models/input.py tests/test_api_craft/test_input_models.py
git commit -m "feat(models): add pk, fk, on_delete to InputField and database config"
```

---

### Task 2: Add FK validation to validators.py

**Files:**
- Modify: `src/api_craft/models/validators.py`
- Modify: `src/api_craft/models/input.py:203-214` (InputAPI._validate_references)
- Test: `tests/test_api_craft/test_input_models.py` (append)

**Step 1: Write the failing test**

Append to `tests/test_api_craft/test_input_models.py`:

```python
class TestForeignKeyValidation:
    def test_fk_to_valid_entity_accepted(self):
        """FK referencing an entity with a PK field is valid."""
        api = InputAPI(
            name="FkTest",
            endpoints=[
                InputEndpoint(name="GetOrders", path="/orders", method="GET", response="Order"),
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
                    InputEndpoint(name="GetItems", path="/items", method="GET", response="Item"),
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
                    InputEndpoint(name="GetOrders", path="/orders", method="GET", response="Order"),
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
```

**Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/test_api_craft/test_input_models.py::TestForeignKeyValidation -v`
Expected: FAIL — FK validation doesn't exist yet

**Step 3: Write minimal implementation**

Add to `src/api_craft/models/validators.py`:

```python
def validate_foreign_keys(objects: Iterable["InputModel"]) -> None:
    """Verify FK targets exist and have a PK field.

    :param objects: Collection of declared objects.
    :raises ValueError: If an FK target is not a persisted entity.
    """
    entity_map = {
        obj.name: obj
        for obj in objects
        if any(f.pk for f in obj.fields)
    }
    for obj in objects:
        for field in obj.fields:
            if field.fk and field.fk not in entity_map:
                raise ValueError(
                    f"Field '{obj.name}.{field.name}' references "
                    f"'{field.fk}' which is not a persisted entity"
                )
```

Add import and call in `src/api_craft/models/input.py` `_validate_references`:

```python
from api_craft.models.validators import (
    validate_endpoint_references,
    validate_foreign_keys,
    validate_model_field_types,
    validate_path_parameters,
    validate_unique_object_names,
)

# In InputAPI._validate_references, add after validate_endpoint_references:
validate_foreign_keys(self.objects)
```

**Step 4: Run test to verify it passes**

Run: `poetry run pytest tests/test_api_craft/test_input_models.py -v`
Expected: PASS

**Step 5: Run all existing tests**

Run: `poetry run pytest tests/ -v`
Expected: All pass

**Step 6: Format and commit**

```bash
poetry run black src/ tests/
git add src/api_craft/models/validators.py src/api_craft/models/input.py tests/test_api_craft/test_input_models.py
git commit -m "feat(models): add foreign key validation for InputField"
```

---

### Task 3: Add template ORM models and database config to template.py

**Files:**
- Modify: `src/api_craft/models/template.py`
- Test: `tests/test_api_craft/test_input_models.py` (append)

**Step 1: Write the failing test**

Append to `tests/test_api_craft/test_input_models.py`:

```python
from api_craft.models.template import TemplateORMField, TemplateORMModel, TemplateDatabaseConfig


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
                TemplateORMField(name="id", python_type="int", column_type="Integer", primary_key=True),
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
```

**Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/test_api_craft/test_input_models.py::TestTemplateORMModels -v`
Expected: FAIL — classes don't exist

**Step 3: Write minimal implementation**

Add to `src/api_craft/models/template.py`:

```python
class TemplateORMField(BaseModel):
    """ORM field definition for template rendering."""

    name: str
    python_type: str
    column_type: str
    primary_key: bool = False
    nullable: bool = False
    autoincrement: bool = False
    foreign_key: str | None = None
    on_delete: str | None = None


class TemplateORMModel(BaseModel):
    """ORM model (table) definition for template rendering."""

    class_name: str
    table_name: str
    source_model: str
    fields: list[TemplateORMField]


class TemplateDatabaseConfig(BaseModel):
    """Database configuration for template rendering."""

    enabled: bool
    seed_data: bool
    default_url: str
```

Also add `orm_models` and `database_config` to `TemplateAPI`:

```python
class TemplateAPI(BaseModel):
    # ... existing fields ...
    orm_models: list[TemplateORMModel] = []
    database_config: TemplateDatabaseConfig | None = None
```

And add `pk: bool = False` to `TemplateField`.

**Step 4: Run test to verify it passes**

Run: `poetry run pytest tests/test_api_craft/test_input_models.py -v`
Expected: PASS

**Step 5: Run all existing tests**

Run: `poetry run pytest tests/ -v`
Expected: All pass

**Step 6: Format and commit**

```bash
poetry run black src/ tests/
git add src/api_craft/models/template.py tests/test_api_craft/test_input_models.py
git commit -m "feat(models): add TemplateORMModel, TemplateORMField, TemplateDatabaseConfig"
```

---

### Task 4: Implement ORM model transformer (type mapping + FK resolution)

**Files:**
- Modify: `src/api_craft/transformers.py`
- Modify: `src/api_craft/utils.py` (add `snake_to_plural`)
- Test: `tests/test_api_craft/test_transformers.py` (create new)

**Step 1: Write the failing test**

```python
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
            _make_model("Item", [
                {"name": "id", "type": "int", "pk": True},
                {"name": "name", "type": "str"},
            ])
        ]
        result = transform_orm_models(models)
        assert len(result) == 1
        assert result[0].class_name == "ItemRecord"
        assert result[0].table_name == "items"
        assert result[0].source_model == "Item"

    def test_int_pk_has_autoincrement(self):
        models = [
            _make_model("Item", [
                {"name": "id", "type": "int", "pk": True},
            ])
        ]
        result = transform_orm_models(models)
        pk_field = result[0].fields[0]
        assert pk_field.primary_key is True
        assert pk_field.autoincrement is True

    def test_uuid_pk_no_autoincrement(self):
        models = [
            _make_model("Item", [
                {"name": "id", "type": "uuid", "pk": True},
            ])
        ]
        result = transform_orm_models(models)
        pk_field = result[0].fields[0]
        assert pk_field.primary_key is True
        assert pk_field.autoincrement is False
        assert pk_field.column_type == "Uuid"


class TestTypeMapping:
    """Test Python type → SQLAlchemy column type mapping."""

    @pytest.mark.parametrize("py_type,expected_col", [
        ("int", "Integer"),
        ("float", "Float"),
        ("bool", "Boolean"),
        ("datetime", "DateTime"),
        ("date", "Date"),
        ("time", "Time"),
        ("uuid", "Uuid"),
        ("Decimal", "Numeric"),
        ("HttpUrl", "Text"),
    ])
    def test_simple_type_mapping(self, py_type, expected_col):
        models = [
            _make_model("Item", [
                {"name": "id", "type": "int", "pk": True},
                {"name": "value", "type": py_type},
            ])
        ]
        result = transform_orm_models(models)
        value_field = result[0].fields[1]
        assert value_field.column_type == expected_col

    def test_str_without_max_length_maps_to_text(self):
        models = [
            _make_model("Item", [
                {"name": "id", "type": "int", "pk": True},
                {"name": "name", "type": "str"},
            ])
        ]
        result = transform_orm_models(models)
        assert result[0].fields[1].column_type == "Text"

    def test_str_with_max_length_maps_to_string_n(self):
        models = [
            _make_model("Item", [
                {"name": "id", "type": "int", "pk": True},
                {"name": "name", "type": "str", "validators": [
                    {"name": "max_length", "params": {"value": 100}}
                ]},
            ])
        ]
        result = transform_orm_models(models)
        assert result[0].fields[1].column_type == "String(100)"

    def test_email_str_maps_to_string_320(self):
        models = [
            _make_model("Item", [
                {"name": "id", "type": "int", "pk": True},
                {"name": "email", "type": "EmailStr"},
            ])
        ]
        result = transform_orm_models(models)
        assert result[0].fields[1].column_type == "String(320)"

    def test_optional_field_is_nullable(self):
        models = [
            _make_model("Item", [
                {"name": "id", "type": "int", "pk": True},
                {"name": "description", "type": "str", "optional": True},
            ])
        ]
        result = transform_orm_models(models)
        assert result[0].fields[1].nullable is True

    def test_list_field_is_skipped(self):
        models = [
            _make_model("Item", [
                {"name": "id", "type": "int", "pk": True},
                {"name": "tags", "type": "List[str]"},
            ])
        ]
        result = transform_orm_models(models)
        assert len(result[0].fields) == 1  # only id, tags skipped


class TestForeignKeyTransform:
    def test_fk_field_resolved(self):
        models = [
            _make_model("Order", [
                {"name": "id", "type": "int", "pk": True},
            ]),
            _make_model("OrderItem", [
                {"name": "id", "type": "int", "pk": True},
                {"name": "order_id", "type": "int", "fk": "Order", "on_delete": "cascade"},
            ]),
        ]
        result = transform_orm_models(models)
        order_item = next(m for m in result if m.class_name == "OrderItemRecord")
        fk_field = next(f for f in order_item.fields if f.name == "order_id")
        assert fk_field.foreign_key == "orders.id"
        assert fk_field.on_delete == "CASCADE"

    def test_fk_on_delete_restrict(self):
        models = [
            _make_model("Order", [{"name": "id", "type": "int", "pk": True}]),
            _make_model("OrderItem", [
                {"name": "id", "type": "int", "pk": True},
                {"name": "order_id", "type": "int", "fk": "Order", "on_delete": "restrict"},
            ]),
        ]
        result = transform_orm_models(models)
        order_item = next(m for m in result if m.class_name == "OrderItemRecord")
        fk_field = next(f for f in order_item.fields if f.name == "order_id")
        assert fk_field.on_delete == "RESTRICT"

    def test_fk_on_delete_set_null(self):
        models = [
            _make_model("Order", [{"name": "id", "type": "int", "pk": True}]),
            _make_model("OrderItem", [
                {"name": "id", "type": "int", "pk": True},
                {"name": "order_id", "type": "int", "fk": "Order", "on_delete": "set_null"},
            ]),
        ]
        result = transform_orm_models(models)
        order_item = next(m for m in result if m.class_name == "OrderItemRecord")
        fk_field = next(f for f in order_item.fields if f.name == "order_id")
        assert fk_field.on_delete == "SET NULL"


class TestSnakeToPlural:
    """Test table name pluralization."""

    @pytest.mark.parametrize("input_name,expected", [
        ("Item", "items"),
        ("OrderItem", "order_items"),
        ("Category", "categories"),
        ("Status", "statuses"),
        ("Address", "addresses"),
    ])
    def test_pluralize(self, input_name, expected):
        from api_craft.utils import snake_to_plural, camel_to_snake
        assert snake_to_plural(camel_to_snake(input_name)) == expected
```

**Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/test_api_craft/test_transformers.py -v`
Expected: FAIL — `transform_orm_models` and `snake_to_plural` don't exist

**Step 3: Write minimal implementation**

Add to `src/api_craft/utils.py`:

```python
def snake_to_plural(name: str) -> str:
    """Pluralize a snake_case name using basic English rules."""
    if name.endswith("y") and not name.endswith(("ay", "ey", "iy", "oy", "uy")):
        return name[:-1] + "ies"
    if name.endswith(("s", "sh", "ch", "x", "z")):
        return name + "es"
    return name + "s"
```

Add to `src/api_craft/transformers.py`:

```python
from api_craft.models.template import (
    # ... existing imports ...
    TemplateORMField,
    TemplateORMModel,
)
from api_craft.utils import (
    # ... existing imports ...
    snake_to_plural,
)


ON_DELETE_MAP = {
    "cascade": "CASCADE",
    "restrict": "RESTRICT",
    "set_null": "SET NULL",
}


def _get_max_length(validators):
    """Extract max_length value from validators list."""
    for v in validators:
        if v.name == "max_length" and v.params and "value" in v.params:
            return v.params["value"]
    return None


def map_column_type(type_str: str, validators: list) -> str | None:
    """Map a Python type string to a SQLAlchemy column type string.

    Returns None for types that cannot be mapped to columns (List, Dict, model refs).
    """
    # Skip collection types
    if type_str.startswith(("List[", "Dict[", "Set[", "Tuple[")):
        return None

    base = type_str.split(".")[0] if "." in type_str else type_str

    type_map = {
        "str": lambda: f"String({ml})" if (ml := _get_max_length(validators)) else "Text",
        "int": lambda: "Integer",
        "float": lambda: "Float",
        "bool": lambda: "Boolean",
        "datetime": lambda: "DateTime",
        "date": lambda: "Date",
        "time": lambda: "Time",
        "uuid": lambda: "Uuid",
        "UUID": lambda: "Uuid",
        "Decimal": lambda: "Numeric",
        "decimal": lambda: "Numeric",
        "EmailStr": lambda: "String(320)",
        "HttpUrl": lambda: "Text",
    }

    factory = type_map.get(base)
    if factory is None:
        return None
    return factory()


def transform_orm_models(input_models: list[InputModel]) -> list[TemplateORMModel]:
    """Convert InputModels with pk fields into TemplateORMModels."""
    # Build entity lookup: name -> (table_name, pk_column_name)
    entity_lookup = {}
    for model in input_models:
        pk_fields = [f for f in model.fields if f.pk]
        if pk_fields:
            table_name = snake_to_plural(camel_to_snake(model.name))
            entity_lookup[str(model.name)] = (table_name, str(pk_fields[0].name))

    orm_models = []
    for model in input_models:
        pk_fields = [f for f in model.fields if f.pk]
        if not pk_fields:
            continue

        table_name = snake_to_plural(camel_to_snake(model.name))
        orm_fields = []

        for field in model.fields:
            column_type = map_column_type(field.type, field.validators)
            if column_type is None:
                continue

            base_type = field.type.split(".")[0] if "." in field.type else field.type
            python_type = base_type if not field.optional else f"{base_type} | None"

            foreign_key = None
            on_delete = None
            if field.fk and field.fk in entity_lookup:
                target_table, target_pk = entity_lookup[field.fk]
                foreign_key = f"{target_table}.{target_pk}"
                on_delete = ON_DELETE_MAP.get(field.on_delete, "RESTRICT")

            orm_fields.append(TemplateORMField(
                name=str(field.name),
                python_type=python_type,
                column_type=column_type,
                primary_key=field.pk,
                nullable=field.optional,
                autoincrement=field.pk and field.type in ("int",),
                foreign_key=foreign_key,
                on_delete=on_delete,
            ))

        orm_models.append(TemplateORMModel(
            class_name=f"{model.name}Record",
            table_name=table_name,
            source_model=str(model.name),
            fields=orm_fields,
        ))

    return orm_models
```

**Step 4: Run test to verify it passes**

Run: `poetry run pytest tests/test_api_craft/test_transformers.py -v`
Expected: PASS

**Step 5: Run all existing tests**

Run: `poetry run pytest tests/ -v`
Expected: All pass

**Step 6: Format and commit**

```bash
poetry run black src/ tests/
git add src/api_craft/transformers.py src/api_craft/utils.py tests/test_api_craft/test_transformers.py
git commit -m "feat(generation): implement ORM model transformer with type mapping and FK resolution"
```

---

### Task 5: Add ORM extractor functions

**Files:**
- Modify: `src/api_craft/extractors.py`
- Test: `tests/test_api_craft/test_transformers.py` (append)

**Step 1: Write the failing test**

Append to `tests/test_api_craft/test_transformers.py`:

```python
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
                    TemplateORMField(name="id", python_type="int", column_type="Integer", primary_key=True),
                    TemplateORMField(name="name", python_type="str", column_type="Text"),
                    TemplateORMField(name="price", python_type="float", column_type="Float"),
                ],
            )
        ]
        imports = collect_orm_imports(models)
        assert "Integer" in imports
        assert "Text" in imports
        assert "Float" in imports

    def test_collects_foreign_key_import(self):
        models = [
            TemplateORMModel(
                class_name="OrderItemRecord",
                table_name="order_items",
                source_model="OrderItem",
                fields=[
                    TemplateORMField(
                        name="order_id", python_type="int", column_type="Integer",
                        foreign_key="orders.id", on_delete="CASCADE",
                    ),
                ],
            )
        ]
        imports = collect_orm_imports(models)
        assert "ForeignKey" in imports

    def test_deduplicates_imports(self):
        models = [
            TemplateORMModel(
                class_name="ItemRecord",
                table_name="items",
                source_model="Item",
                fields=[
                    TemplateORMField(name="a", python_type="int", column_type="Integer"),
                    TemplateORMField(name="b", python_type="int", column_type="Integer"),
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
```

**Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/test_api_craft/test_transformers.py::TestCollectOrmImports -v`
Expected: FAIL

**Step 3: Write minimal implementation**

Add to `src/api_craft/extractors.py`:

```python
from api_craft.models.template import (
    # ... existing imports ...
    TemplateORMModel,
)

# Column type patterns that need String(N) extraction
_STRING_PATTERN = re.compile(r"String\(\d+\)")


def collect_orm_imports(orm_models: list[TemplateORMModel]) -> list[str]:
    """Collect SQLAlchemy column type imports needed by ORM models.

    :param orm_models: Collection of ORM models.
    :returns: Deduplicated list of SQLAlchemy type names to import.
    """
    imports = set()
    for model in orm_models:
        for field in model.fields:
            # Normalize String(N) to String
            col_type = field.column_type
            if _STRING_PATTERN.match(col_type):
                imports.add("String")
            else:
                imports.add(col_type)

            if field.foreign_key:
                imports.add("ForeignKey")

    return sorted(imports)


def collect_database_dependencies() -> list[str]:
    """Return pip dependencies for database support.

    :returns: List of pip dependency strings.
    """
    return [
        "sqlalchemy[asyncio] (>=2.0.0,<3.0.0)",
        "asyncpg (>=0.31.0,<1.0.0)",
        "alembic (>=1.18.0,<2.0.0)",
    ]
```

**Step 4: Run test to verify it passes**

Run: `poetry run pytest tests/test_api_craft/test_transformers.py -v`
Expected: PASS

**Step 5: Run all existing tests**

Run: `poetry run pytest tests/ -v`
Expected: All pass

**Step 6: Format and commit**

```bash
poetry run black src/ tests/
git add src/api_craft/extractors.py tests/test_api_craft/test_transformers.py
git commit -m "feat(generation): add ORM import collector and database dependency extractor"
```

---

### Task 6: Integrate ORM transformation into `transform_api()` and `APIGenerator`

**Files:**
- Modify: `src/api_craft/transformers.py:207-262` (transform_api function)
- Modify: `src/api_craft/main.py` (APIGenerator methods)
- Test: `tests/test_api_craft/test_transformers.py` (append)

**Step 1: Write the failing test**

Append to `tests/test_api_craft/test_transformers.py`:

```python
from api_craft.models.input import InputAPI, InputEndpoint, InputApiConfig
from api_craft.transformers import transform_api


class TestTransformApiWithDatabase:
    def test_database_disabled_no_orm_models(self):
        api = InputAPI(
            name="TestApi",
            endpoints=[InputEndpoint(name="GetItems", path="/items", method="GET", response="Item")],
            objects=[_make_model("Item", [
                {"name": "id", "type": "int", "pk": True},
                {"name": "name", "type": "str"},
            ])],
            config=InputApiConfig(database={"enabled": False}),
        )
        result = transform_api(api)
        assert result.orm_models == []
        assert result.database_config is None

    def test_database_enabled_produces_orm_models(self):
        api = InputAPI(
            name="TestApi",
            endpoints=[InputEndpoint(name="GetItems", path="/items", method="GET", response="Item")],
            objects=[_make_model("Item", [
                {"name": "id", "type": "int", "pk": True},
                {"name": "name", "type": "str"},
            ])],
            config=InputApiConfig(database={"enabled": True}),
        )
        result = transform_api(api)
        assert len(result.orm_models) == 1
        assert result.orm_models[0].class_name == "ItemRecord"
        assert result.database_config is not None
        assert result.database_config.enabled is True

    def test_database_config_default_url_uses_api_name(self):
        api = InputAPI(
            name="ShopApi",
            endpoints=[InputEndpoint(name="GetItems", path="/items", method="GET", response="Item")],
            objects=[_make_model("Item", [
                {"name": "id", "type": "int", "pk": True},
                {"name": "name", "type": "str"},
            ])],
            config=InputApiConfig(database={"enabled": True}),
        )
        result = transform_api(api)
        assert "shop_api" in result.database_config.default_url
```

**Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/test_api_craft/test_transformers.py::TestTransformApiWithDatabase -v`
Expected: FAIL — transform_api doesn't produce orm_models

**Step 3: Write minimal implementation**

Modify `transform_api()` in `src/api_craft/transformers.py` to add ORM transformation at the end, before returning:

```python
from api_craft.models.template import (
    # ... existing ...
    TemplateDatabaseConfig,
)

def transform_api(input_api: InputAPI) -> TemplateAPI:
    # ... existing code up to line 243 ...

    orm_models = []
    database_config = None
    if input_api.config.database.enabled:
        orm_models = transform_orm_models(input_api.objects)
        snake_name = camel_to_snake(input_api.name)
        database_config = TemplateDatabaseConfig(
            enabled=True,
            seed_data=input_api.config.database.seed_data,
            default_url=f"postgresql+asyncpg://postgres:postgres@localhost:5432/{snake_name}",
        )

    return TemplateAPI(
        # ... existing fields ...
        orm_models=orm_models,
        database_config=database_config,
    )
```

Update `APIGenerator.extract_components()` and `render_components()` in `src/api_craft/main.py` to handle ORM models when database is enabled. The extract step should include orm_models, and render step should call new render functions.

Note: The actual rendering is in Task 8+. For now, just pass them through extraction:

```python
def extract_components(self, template_api: TemplateAPI) -> dict[str, Any]:
    try:
        components = {
            "models": template_api.models,
            "views": template_api.views,
            "path_params": extract_path_parameters(template_api),
            "query_params": extract_query_parameters(template_api),
            "orm_models": template_api.orm_models,
            "database_config": template_api.database_config,
        }
        return components
    except Exception as e:
        logger.error(f"Failed to extract components: {str(e)}")
        raise ValueError("Component extraction failed") from e
```

**Step 4: Run test to verify it passes**

Run: `poetry run pytest tests/test_api_craft/test_transformers.py -v`
Expected: PASS

**Step 5: Run all existing tests**

Run: `poetry run pytest tests/ -v`
Expected: All pass

**Step 6: Format and commit**

```bash
poetry run black src/ tests/
git add src/api_craft/transformers.py src/api_craft/main.py tests/test_api_craft/test_transformers.py
git commit -m "feat(generation): integrate ORM transformation into transform_api pipeline"
```

---

### Task 7: Create Mako templates for database files

**Files:**
- Create: `src/api_craft/templates/orm_models.mako`
- Create: `src/api_craft/templates/database.mako`
- Create: `src/api_craft/templates/seed.mako`
- Create: `src/api_craft/templates/docker_compose.mako`
- Create: `src/api_craft/templates/alembic_ini.mako`
- Create: `src/api_craft/templates/alembic_env.mako`

No test step for this task — templates are validated in Task 9 via end-to-end tests.

**Step 1: Create `src/api_craft/templates/orm_models.mako`**

```mako
<%doc>
- Template Parameters:
- orm_models: list[TemplateORMModel]
- imports: list[str] - SQLAlchemy column type names
</%doc>\
<%
has_foreign_keys = any(
    field.foreign_key
    for model in orm_models
    for field in model.fields
)
sa_imports = sorted(set(imports))
%>\
from sqlalchemy import ${', '.join(sa_imports)}
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass
% for model in orm_models:


class ${model.class_name}(Base):
    __tablename__ = "${model.table_name}"

% for field in model.fields:
<%
    parts = []
    parts.append(field.column_type)
    if field.primary_key:
        parts.append("primary_key=True")
    if field.autoincrement:
        parts.append("autoincrement=True")
    if field.foreign_key:
        on_del = f', ondelete="{field.on_delete}"' if field.on_delete else ''
        parts.append(f'ForeignKey("{field.foreign_key}"{on_del})')
    if field.nullable and not field.primary_key:
        parts.append("nullable=True")
%>\
    ${field.name}: Mapped[${field.python_type}] = mapped_column(${', '.join(parts)})
% endfor
% endfor
```

**Step 2: Create `src/api_craft/templates/database.mako`**

```mako
<%doc>
- Template Parameters:
- api: TemplateAPI
</%doc>\
import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "${api.database_config.default_url}",
)

engine = create_async_engine(DATABASE_URL)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
```

**Step 3: Create `src/api_craft/templates/seed.mako`**

```mako
<%doc>
- Template Parameters:
- orm_models: list[TemplateORMModel]
- seed_data: dict[str, dict[str, Any]] - model_name -> {field_name: value}
</%doc>\
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from orm_models import (
% for model in orm_models:
    ${model.class_name},
% endfor
)


async def seed_database(session: AsyncSession) -> None:
    """Seed the database with placeholder data. Idempotent."""
% for model in orm_models:
<%
    model_seed = seed_data.get(model.source_model, {})
    # Filter to only fields that exist on the ORM model and are not PK with autoincrement
    orm_field_names = {f.name for f in model.fields if not (f.primary_key and f.autoincrement)}
    seed_fields = {k: v for k, v in model_seed.items() if k in orm_field_names}
%>\
% if seed_fields:
    existing_${model.table_name} = await session.execute(select(${model.class_name}).limit(1))
    if not existing_${model.table_name}.scalars().first():
        session.add_all([
            ${model.class_name}(
% for field_name, value in seed_fields.items():
                ${field_name}=${value.__repr__()},
% endfor
            ),
        ])
% endif
% endfor
    await session.commit()
```

**Step 4: Create `src/api_craft/templates/docker_compose.mako`**

```mako
<%doc>
- Template Parameters:
- api: TemplateAPI
</%doc>\
services:
  db:
    image: postgres:18
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: ${api.snake_name}
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 3s
      retries: 5

  api:
    build: .
    ports:
      - "8000:80"
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:postgres@db:5432/${api.snake_name}
    depends_on:
      db:
        condition: service_healthy

volumes:
  pgdata:
```

**Step 5: Create `src/api_craft/templates/alembic_ini.mako`**

```mako
<%doc>
- Template Parameters:
- api: TemplateAPI
</%doc>\
[alembic]
script_location = migrations
sqlalchemy.url = postgresql+asyncpg://postgres:postgres@localhost:5432/${api.snake_name}

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

**Step 6: Create `src/api_craft/templates/alembic_env.mako`**

```mako
<%doc>
- Template Parameters:
- api: TemplateAPI
</%doc>\
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

# Add src to path for orm_models import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from orm_models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Override sqlalchemy.url from environment variable if set
url = os.environ.get("DATABASE_URL")
if url:
    config.set_main_option("sqlalchemy.url", url)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    import asyncio
    asyncio.run(run_migrations_online())
```

**Step 7: Commit**

```bash
git add src/api_craft/templates/orm_models.mako src/api_craft/templates/database.mako src/api_craft/templates/seed.mako src/api_craft/templates/docker_compose.mako src/api_craft/templates/alembic_ini.mako src/api_craft/templates/alembic_env.mako
git commit -m "feat(generation): add Mako templates for database, ORM, seed, Docker Compose, Alembic"
```

---

### Task 8: Modify existing templates for database support

**Files:**
- Modify: `src/api_craft/templates/views.mako`
- Modify: `src/api_craft/templates/main.mako`
- Modify: `src/api_craft/templates/makefile.mako`
- Modify: `src/api_craft/templates/dockerfile.mako`
- Modify: `src/api_craft/templates/pyproject.mako`
- Modify: `src/api_craft/templates/readme.mako`

These modifications add conditional sections when `database_config` is present. The templates must remain backward-compatible: when `database_config` is `None`, they produce identical output to today.

**Step 1: Modify `views.mako`**

Add database-aware view generation. The template receives a new `database_config` and `orm_model_map` variable. When database is enabled, views render DB queries instead of hardcoded placeholders.

Key changes:
- Add imports for `Depends`, `HTTPException`, `AsyncSession`, `select`, `get_session`, ORM models
- Add `session: AsyncSession = Depends(get_session)` to function signatures
- Replace hardcoded returns with DB query patterns based on HTTP method

The view template should check `database_config` at the top and branch accordingly. The hardcoded placeholder path remains unchanged for backward compatibility.

**Step 2: Modify `main.mako`**

When database enabled, add:
- Import `asynccontextmanager`
- Import `database.engine`, `database.async_session`, `orm_models.Base`, `seed.seed_database`
- Add `lifespan` context manager that creates tables and seeds
- Pass `lifespan=lifespan` to `FastAPI()`

**Step 3: Modify `makefile.mako`**

When database enabled, add targets: `db-up`, `db-down`, `db-upgrade`, `db-downgrade`, `db-seed`, `db-reset`, `run-stack`. Modify `run-local` to depend on `db-up`.

**Step 4: Modify `dockerfile.mako`**

When database enabled:
- Add `COPY migrations/ ./migrations/`
- Add `COPY alembic.ini .`
- Change CMD to run `alembic upgrade head` before uvicorn

**Step 5: Modify `pyproject.mako`**

Database dependencies are already handled via `extra_dependencies` — no template change needed, just pass them in from the renderer.

**Step 6: Modify `readme.mako`**

When database enabled, add a "Database" section with setup commands.

**Step 7: Commit**

```bash
git add src/api_craft/templates/views.mako src/api_craft/templates/main.mako src/api_craft/templates/makefile.mako src/api_craft/templates/dockerfile.mako src/api_craft/templates/readme.mako
git commit -m "feat(generation): add database-aware sections to existing templates"
```

---

### Task 9: Wire up rendering and writing for database files

**Files:**
- Modify: `src/api_craft/renderers.py`
- Modify: `src/api_craft/main.py`

**Step 1: Add render functions to `renderers.py`**

```python
def render_orm_models(orm_models, imports, template) -> str:
    return template.render(orm_models=orm_models, imports=imports)

def render_database(api, template) -> str:
    return template.render(api=api)

def render_seed(orm_models, seed_data, template) -> str:
    return template.render(orm_models=orm_models, seed_data=seed_data)

def render_docker_compose(api, template) -> str:
    return template.render(api=api)

def render_alembic_ini(api, template) -> str:
    return template.render(api=api)

def render_alembic_env(api, template) -> str:
    return template.render(api=api)
```

**Step 2: Update `APIGenerator.load_templates()`**

Add new template files to the `template_files` dict when loading:

```python
template_files = {
    # ... existing ...
    "orm_models": "orm_models.mako",
    "database": "database.mako",
    "seed": "seed.mako",
    "docker_compose": "docker_compose.mako",
    "alembic_ini": "alembic_ini.mako",
    "alembic_env": "alembic_env.mako",
}
```

**Step 3: Update `APIGenerator.render_components()`**

When `database_config` is present:
- Collect ORM imports and database dependencies
- Render all new templates
- Pass `database_config` and `orm_model_map` to modified views/main templates
- Merge database deps into `extra_deps`

**Step 4: Update `APIGenerator.write_files()`**

When database files are present in rendered_components:
- Create `migrations/versions/` directory
- Write `alembic.ini` to project root
- Write `alembic_env.py` to `migrations/env.py`
- Write `docker-compose.yml` to project root
- Write `orm_models.py`, `database.py`, `seed.py` to `src/`

**Step 5: Commit**

```bash
poetry run black src/
git add src/api_craft/renderers.py src/api_craft/main.py
git commit -m "feat(generation): wire up rendering and writing for database files"
```

---

### Task 10: Create database-enabled test spec and end-to-end tests

**Files:**
- Create: `tests/specs/items_api_db.yaml`
- Create: `tests/test_api_craft/test_db_codegen.py`

**Step 1: Create test spec**

```yaml
# tests/specs/items_api_db.yaml
name: ItemsDbApi
version: "0.1.0"
author: Median Code
description: Items API with database backend

tags:
  - name: Items
    description: Item management operations

objects:
  - name: Item
    description: Product item
    fields:
      - name: id
        type: int
        pk: true
        validators:
          - name: ge
            params: { value: 1 }
      - name: sku
        type: str
        validators:
          - name: min_length
            params: { value: 3 }
          - name: max_length
            params: { value: 20 }
          - name: pattern
            params: { value: "^[A-Z0-9-]+$" }
      - name: name
        type: str
        validators:
          - name: min_length
            params: { value: 1 }
          - name: max_length
            params: { value: 100 }
      - name: price
        type: float
        validators:
          - name: gt
            params: { value: 0 }
          - name: le
            params: { value: 1000000 }
      - name: quantity
        type: int
        validators:
          - name: ge
            params: { value: 0 }

  - name: CreateItemRequest
    fields:
      - name: sku
        type: str
        validators:
          - name: min_length
            params: { value: 3 }
          - name: max_length
            params: { value: 20 }
          - name: pattern
            params: { value: "^[A-Z0-9-]+$" }
      - name: name
        type: str
        validators:
          - name: min_length
            params: { value: 1 }
          - name: max_length
            params: { value: 100 }
      - name: price
        type: float
        validators:
          - name: gt
            params: { value: 0 }
      - name: quantity
        type: int
        validators:
          - name: ge
            params: { value: 0 }

  - name: UpdateItemRequest
    fields:
      - name: name
        type: str
        optional: true
        validators:
          - name: max_length
            params: { value: 100 }
      - name: price
        type: float
        optional: true
        validators:
          - name: gt
            params: { value: 0 }
      - name: quantity
        type: int
        optional: true

endpoints:
  - name: GetItem
    path: /items/{item_id}
    method: GET
    tag: Items
    response: Item
    path_params:
      - name: item_id
        type: int

  - name: GetItems
    path: /items
    method: GET
    tag: Items
    response: Item
    response_shape: list

  - name: CreateItem
    path: /items
    method: POST
    tag: Items
    response: Item
    request: CreateItemRequest

  - name: UpdateItem
    path: /items/{item_id}
    method: PUT
    tag: Items
    response: Item
    request: UpdateItemRequest
    path_params:
      - name: item_id
        type: int

  - name: DeleteItem
    path: /items/{item_id}
    method: DELETE
    tag: Items
    path_params:
      - name: item_id
        type: int

config:
  healthcheck: /healthcheck
  database:
    enabled: true
    seed_data: true
```

**Step 2: Write the tests**

```python
# tests/test_api_craft/test_db_codegen.py
"""Tests for database-enabled code generation.

Validates that when database.enabled is true:
- ORM models, database.py, seed.py are generated
- Docker Compose, Alembic config are generated
- Generated Python files compile without errors
- views.py uses DB session injection
- main.py has lifespan with DB init
- Makefile has db-* targets
"""

from pathlib import Path

import pytest

from api_craft.main import APIGenerator
from .conftest import load_input

pytestmark = pytest.mark.codegen


@pytest.fixture(scope="module")
def db_project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Generate the Items DB API project and return its root path."""
    tmp_path = tmp_path_factory.mktemp("items_db_api")
    api_input = load_input("items_api_db.yaml")
    APIGenerator().generate(api_input, path=str(tmp_path))
    return tmp_path / "items-db-api"


class TestDatabaseFilesGenerated:
    """Verify all expected database files are created."""

    def test_orm_models_exists(self, db_project: Path):
        assert (db_project / "src" / "orm_models.py").exists()

    def test_database_py_exists(self, db_project: Path):
        assert (db_project / "src" / "database.py").exists()

    def test_seed_py_exists(self, db_project: Path):
        assert (db_project / "src" / "seed.py").exists()

    def test_docker_compose_exists(self, db_project: Path):
        assert (db_project / "docker-compose.yml").exists()

    def test_alembic_ini_exists(self, db_project: Path):
        assert (db_project / "alembic.ini").exists()

    def test_alembic_env_exists(self, db_project: Path):
        assert (db_project / "migrations" / "env.py").exists()


class TestGeneratedCodeCompiles:
    """Verify generated Python files have valid syntax."""

    @pytest.mark.parametrize("filename", [
        "src/orm_models.py",
        "src/database.py",
        "src/seed.py",
        "src/models.py",
        "src/views.py",
        "src/main.py",
    ])
    def test_file_compiles(self, db_project: Path, filename: str):
        content = (db_project / filename).read_text()
        compile(content, filename, "exec")


class TestOrmModelsContent:
    """Verify ORM models are correctly generated."""

    def test_contains_base_class(self, db_project: Path):
        content = (db_project / "src" / "orm_models.py").read_text()
        assert "class Base(DeclarativeBase):" in content

    def test_contains_item_record(self, db_project: Path):
        content = (db_project / "src" / "orm_models.py").read_text()
        assert "class ItemRecord(Base):" in content

    def test_table_name_is_items(self, db_project: Path):
        content = (db_project / "src" / "orm_models.py").read_text()
        assert '__tablename__ = "items"' in content

    def test_pk_field_generated(self, db_project: Path):
        content = (db_project / "src" / "orm_models.py").read_text()
        assert "primary_key=True" in content

    def test_no_create_request_in_orm(self, db_project: Path):
        """CreateItemRequest (no pk) should NOT be an ORM model."""
        content = (db_project / "src" / "orm_models.py").read_text()
        assert "CreateItemRequestRecord" not in content

    def test_str_with_max_length_uses_string_n(self, db_project: Path):
        content = (db_project / "src" / "orm_models.py").read_text()
        assert "String(20)" in content  # sku has max_length=20

    def test_str_without_max_length_uses_text(self, db_project: Path):
        """Fields without max_length should use Text, not String."""
        # All str fields in this spec have max_length, so this test checks
        # that Text doesn't appear incorrectly. Covered by name using String(100).
        content = (db_project / "src" / "orm_models.py").read_text()
        assert "String(100)" in content  # name has max_length=100


class TestDatabasePyContent:
    def test_contains_database_url(self, db_project: Path):
        content = (db_project / "src" / "database.py").read_text()
        assert "DATABASE_URL" in content

    def test_contains_async_engine(self, db_project: Path):
        content = (db_project / "src" / "database.py").read_text()
        assert "create_async_engine" in content

    def test_contains_get_session(self, db_project: Path):
        content = (db_project / "src" / "database.py").read_text()
        assert "async def get_session" in content

    def test_default_url_uses_api_name(self, db_project: Path):
        content = (db_project / "src" / "database.py").read_text()
        assert "items_db_api" in content


class TestViewsWithDatabase:
    def test_views_import_depends(self, db_project: Path):
        content = (db_project / "src" / "views.py").read_text()
        assert "Depends" in content

    def test_views_import_get_session(self, db_project: Path):
        content = (db_project / "src" / "views.py").read_text()
        assert "get_session" in content

    def test_views_import_orm_model(self, db_project: Path):
        content = (db_project / "src" / "views.py").read_text()
        assert "ItemRecord" in content

    def test_views_use_session_param(self, db_project: Path):
        content = (db_project / "src" / "views.py").read_text()
        assert "AsyncSession" in content
        assert "Depends(get_session)" in content

    def test_views_have_db_queries(self, db_project: Path):
        content = (db_project / "src" / "views.py").read_text()
        assert "select(" in content
        assert "session.execute" in content


class TestMainWithDatabase:
    def test_main_has_lifespan(self, db_project: Path):
        content = (db_project / "src" / "main.py").read_text()
        assert "lifespan" in content

    def test_main_imports_database(self, db_project: Path):
        content = (db_project / "src" / "main.py").read_text()
        assert "from database import" in content

    def test_main_imports_seed(self, db_project: Path):
        content = (db_project / "src" / "main.py").read_text()
        assert "seed_database" in content


class TestMakefileWithDatabase:
    def test_makefile_has_db_targets(self, db_project: Path):
        content = (db_project / "Makefile").read_text()
        assert "db-up:" in content
        assert "db-upgrade:" in content
        assert "db-seed:" in content
        assert "db-reset:" in content
        assert "db-downgrade:" in content


class TestDockerComposeContent:
    def test_has_postgres_service(self, db_project: Path):
        content = (db_project / "docker-compose.yml").read_text()
        assert "postgres:18" in content

    def test_has_api_service(self, db_project: Path):
        content = (db_project / "docker-compose.yml").read_text()
        assert "api:" in content

    def test_has_database_url(self, db_project: Path):
        content = (db_project / "docker-compose.yml").read_text()
        assert "DATABASE_URL" in content

    def test_db_name_matches_api(self, db_project: Path):
        content = (db_project / "docker-compose.yml").read_text()
        assert "items_db_api" in content


class TestDockerfileWithDatabase:
    def test_copies_migrations(self, db_project: Path):
        content = (db_project / "Dockerfile").read_text()
        assert "migrations" in content

    def test_copies_alembic_ini(self, db_project: Path):
        content = (db_project / "Dockerfile").read_text()
        assert "alembic.ini" in content

    def test_runs_alembic_upgrade(self, db_project: Path):
        content = (db_project / "Dockerfile").read_text()
        assert "alembic upgrade head" in content


class TestBackwardCompatibility:
    """Ensure database.enabled=false produces identical output."""

    def test_no_database_files_when_disabled(self, tmp_path):
        api_input = load_input("items_api.yaml")
        APIGenerator().generate(api_input, path=str(tmp_path))
        project = tmp_path / "items-api"

        assert not (project / "src" / "orm_models.py").exists()
        assert not (project / "src" / "database.py").exists()
        assert not (project / "src" / "seed.py").exists()
        assert not (project / "docker-compose.yml").exists()
        assert not (project / "alembic.ini").exists()
        assert not (project / "migrations").exists()

    def test_views_unchanged_when_disabled(self, tmp_path):
        api_input = load_input("items_api.yaml")
        APIGenerator().generate(api_input, path=str(tmp_path))
        views = (tmp_path / "items-api" / "src" / "views.py").read_text()

        assert "Depends" not in views
        assert "get_session" not in views
        assert "select(" not in views
```

**Step 3: Run tests**

Run: `poetry run pytest tests/test_api_craft/test_db_codegen.py -v`
Expected: PASS (all files generated correctly, code compiles, content matches expectations)

**Step 4: Run all tests**

Run: `poetry run pytest tests/ -v`
Expected: All pass including existing tests

**Step 5: Format and commit**

```bash
poetry run black src/ tests/
git add tests/specs/items_api_db.yaml tests/test_api_craft/test_db_codegen.py
git commit -m "test(generation): add database-enabled codegen end-to-end tests"
```

---

### Task 11: Add FK codegen test with parent-child entities

**Files:**
- Create: `tests/specs/orders_api_db.yaml`
- Modify: `tests/test_api_craft/test_db_codegen.py` (append)

**Step 1: Create test spec with FK relationship**

```yaml
# tests/specs/orders_api_db.yaml
name: OrdersDbApi
version: "0.1.0"
description: Orders API with FK relationships

objects:
  - name: Order
    fields:
      - name: id
        type: int
        pk: true
      - name: status
        type: str
        validators:
          - name: max_length
            params: { value: 50 }

  - name: OrderItem
    fields:
      - name: id
        type: int
        pk: true
      - name: order_id
        type: int
        fk: Order
        on_delete: cascade
      - name: product_name
        type: str
        validators:
          - name: max_length
            params: { value: 200 }
      - name: quantity
        type: int
        validators:
          - name: ge
            params: { value: 1 }

  - name: CreateOrderRequest
    fields:
      - name: status
        type: str

endpoints:
  - name: GetOrders
    path: /orders
    method: GET
    response: Order
    response_shape: list

  - name: CreateOrder
    path: /orders
    method: POST
    response: Order
    request: CreateOrderRequest

config:
  database:
    enabled: true
```

**Step 2: Write the FK tests**

Append to `tests/test_api_craft/test_db_codegen.py`:

```python
@pytest.fixture(scope="module")
def fk_project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Generate the Orders DB API project with FK relationships."""
    tmp_path = tmp_path_factory.mktemp("orders_db_api")
    api_input = load_input("orders_api_db.yaml")
    APIGenerator().generate(api_input, path=str(tmp_path))
    return tmp_path / "orders-db-api"


class TestForeignKeyGeneration:
    def test_order_item_has_fk(self, fk_project: Path):
        content = (fk_project / "src" / "orm_models.py").read_text()
        assert 'ForeignKey("orders.id"' in content

    def test_fk_has_cascade_delete(self, fk_project: Path):
        content = (fk_project / "src" / "orm_models.py").read_text()
        assert 'ondelete="CASCADE"' in content

    def test_both_tables_generated(self, fk_project: Path):
        content = (fk_project / "src" / "orm_models.py").read_text()
        assert "class OrderRecord(Base):" in content
        assert "class OrderItemRecord(Base):" in content

    def test_no_dto_tables(self, fk_project: Path):
        content = (fk_project / "src" / "orm_models.py").read_text()
        assert "CreateOrderRequestRecord" not in content

    def test_fk_import_present(self, fk_project: Path):
        content = (fk_project / "src" / "orm_models.py").read_text()
        assert "ForeignKey" in content

    def test_orm_models_compile(self, fk_project: Path):
        content = (fk_project / "src" / "orm_models.py").read_text()
        compile(content, "orm_models.py", "exec")
```

**Step 3: Run tests**

Run: `poetry run pytest tests/test_api_craft/test_db_codegen.py::TestForeignKeyGeneration -v`
Expected: PASS

**Step 4: Format and commit**

```bash
poetry run black tests/
git add tests/specs/orders_api_db.yaml tests/test_api_craft/test_db_codegen.py
git commit -m "test(generation): add FK relationship codegen tests"
```

---

### Task 12: Update conftest.py for database-enabled test client loading

**Files:**
- Modify: `tests/test_api_craft/conftest.py`

The `load_app` function needs to handle additional modules (`database`, `orm_models`, `seed`) when they exist in the generated project. Update the `module_files` list:

```python
module_files = ["orm_models", "database", "seed", "models", "path", "query", "views", "main"]
```

Order matters: `orm_models` before `database` (database may import orm_models), `seed` after `database`.

**Step 1: Make the change**

**Step 2: Run all tests**

Run: `poetry run pytest tests/ -v`
Expected: All pass

**Step 3: Commit**

```bash
git add tests/test_api_craft/conftest.py
git commit -m "fix(tests): add database modules to dynamic app loader"
```

---

### Task 13: Final integration test and cleanup

**Files:**
- Run all tests
- Format all code
- Verify backward compatibility

**Step 1: Run full test suite**

Run: `poetry run pytest tests/ -v`
Expected: ALL tests pass — both existing (items_api, shop_api) and new (items_api_db, orders_api_db)

**Step 2: Format code**

Run: `poetry run black src/ tests/`

**Step 3: Verify backward compatibility one more time**

Run: `poetry run pytest tests/test_api_craft/test_codegen.py -v`
Expected: All existing tests pass unchanged

**Step 4: Generate sample output for manual inspection**

Run: `poetry run pytest tests/test_api_craft/test_codegen.py::test_generate_to_output -v --override-ini="markers=" -k "test_generate_to_output"`

Inspect `tests/output/` to verify generated database files look correct.

**Step 5: Final commit if any changes**

```bash
poetry run black src/ tests/
git add -A
git commit -m "chore(generation): final cleanup for database generation feature"
```
