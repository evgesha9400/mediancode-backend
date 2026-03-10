# PK/FK on Field-Object Associations — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `is_pk`, `fk_object_id`, and `on_delete` columns to `ObjectFieldAssociation` so the generation pipeline can produce correct database-enabled projects.

**Architecture:** The field-object association (`fields_on_objects`) gains three columns that track whether a field is a primary key, a foreign key (pointing to another object), or has a delete action. These flow through the API schema → service → generation pipeline → api_craft templates. A validation gate in `transform_api()` rejects database generation when no object has a PK field.

**Tech Stack:** SQLAlchemy 2.x, FastAPI, Pydantic v2, Alembic (migration modified in-place), pytest

**Design doc:** `docs/plans/2026-03-10-pk-fk-on-field-associations-design.md`

---

### Task 1: Schema — Add columns to migration (in-place)

**Files:**
- Modify: `src/api/migrations/versions/4141ad7f2255_initial_schema.py:310-338`

**Step 1: Add three columns to `fields_on_objects` table in the migration**

In the `upgrade()` function, find the `op.create_table("fields_on_objects", ...)` block and add three columns after the existing `position` column:

```python
        sa.Column("is_pk", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("fk_object_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("on_delete", sa.Text(), nullable=True),
```

Add a FK constraint inside the same `create_table` call:

```python
        sa.ForeignKeyConstraint(["fk_object_id"], ["objects.id"]),
```

Add a CHECK constraint:

```python
        sa.CheckConstraint(
            "on_delete IN ('cascade', 'restrict', 'set_null')",
            name="ck_fields_on_objects_on_delete",
        ),
```

**Step 2: Commit**

```
feat(models): add is_pk, fk_object_id, on_delete to fields_on_objects

- Add is_pk boolean column (default false) to mark primary key fields
- Add fk_object_id UUID column referencing objects.id for foreign keys
- Add on_delete text column with CHECK constraint (cascade/restrict/set_null)
```

---

### Task 2: ORM Model — Add mapped columns

**Files:**
- Modify: `src/api/models/database.py` — `ObjectFieldAssociation` class (~line 452-483)

**Step 1: Add three mapped columns to `ObjectFieldAssociation`**

After the existing `position` column, add:

```python
    is_pk: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    fk_object_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("objects.id"), nullable=True
    )
    on_delete: Mapped[str | None] = mapped_column(Text, nullable=True)
```

Add a relationship for `fk_object` after the existing relationships:

```python
    fk_object: Mapped["ObjectDefinition | None"] = relationship(
        foreign_keys=[fk_object_id]
    )
```

Also add a `__table_args__` with the CHECK constraint:

```python
    __table_args__ = (
        CheckConstraint(
            "on_delete IN ('cascade', 'restrict', 'set_null')",
            name="ck_fields_on_objects_on_delete",
        ),
    )
```

Ensure `CheckConstraint` is imported from `sqlalchemy` (it may already be — check the existing imports at the top of the file).

**Step 2: Run `poetry run black src/`**

**Step 3: Commit**

```
feat(models): add is_pk, fk_object_id, on_delete to ObjectFieldAssociation ORM

- Add is_pk, fk_object_id, on_delete mapped columns
- Add fk_object relationship for resolving target object
- Add CHECK constraint for on_delete values
```

---

### Task 3: API Schema — Expose new fields

**Files:**
- Modify: `src/api/schemas/object.py` — `ObjectFieldReferenceSchema` class (lines 11-23)

**Step 1: Add imports**

Add at the top of the file:

```python
from api.schemas.literals import OnDeleteAction
```

**Step 2: Add fields to `ObjectFieldReferenceSchema`**

After the existing `optional` field, add:

```python
    is_pk: bool = Field(default=False, alias="isPk", examples=[False])
    fk_object_id: UUID | None = Field(
        default=None, alias="fkObjectId", examples=[None]
    )
    on_delete: OnDeleteAction | None = Field(
        default=None, alias="onDelete", examples=[None]
    )
```

Since `ObjectCreate`, `ObjectUpdate`, and `ObjectResponse` all use `ObjectFieldReferenceSchema` for their `fields` array, these changes propagate automatically.

**Step 3: Run `poetry run black src/`**

**Step 4: Commit**

```
feat(api): expose isPk, fkObjectId, onDelete on object field references

- Add is_pk, fk_object_id, on_delete to ObjectFieldReferenceSchema
- These propagate to ObjectCreate, ObjectUpdate, ObjectResponse via composition
```

---

### Task 4: Router + Service — Wire new fields through

**Files:**
- Modify: `src/api/routers/objects.py` — `_to_response()` function (lines 28-57)
- Modify: `src/api/services/object.py` — `_set_field_associations()` method (lines 169-195)

**Step 1: Update `_to_response()` in `routers/objects.py`**

Change the `fields` list comprehension (line 35-37) to pass the new columns:

```python
    fields = [
        ObjectFieldReferenceSchema(
            field_id=fa.field_id,
            optional=fa.optional,
            is_pk=fa.is_pk,
            fk_object_id=fa.fk_object_id,
            on_delete=fa.on_delete,
        )
        for fa in sorted(obj.field_associations, key=lambda x: x.position)
    ]
```

**Step 2: Update `_set_field_associations()` in `services/object.py`**

Change the `ObjectFieldAssociation(...)` constructor (line 187-191) to pass the new fields:

```python
            assoc = ObjectFieldAssociation(
                object_id=obj.id,
                field_id=field_ref.field_id,
                optional=field_ref.optional,
                is_pk=field_ref.is_pk,
                fk_object_id=field_ref.fk_object_id,
                on_delete=field_ref.on_delete,
                position=position,
            )
```

**Step 3: Run `poetry run black src/`**

**Step 4: Commit**

```
feat(api): wire is_pk, fk_object_id, on_delete through router and service

- Pass new fields from schema to ORM model during create/update
- Include new fields in response serialization
```

---

### Task 5: Tests — API round-trip for PK/FK fields

**Files:**
- Modify: `tests/test_api/test_generation_unit.py`

**Step 1: Write test for `_convert_to_input_api` passing PK through**

Add a new test class at the bottom of `test_generation_unit.py`:

```python
class TestConvertToInputApiPkFk:
    """Tests that pk/fk/on_delete flow from associations to InputField."""

    def _make_api_with_objects(self, *, is_pk=False, fk_object_id=None, on_delete=None):
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
        assoc.fk_object_id = fk_object_id
        assoc.on_delete = on_delete

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
        opts = GenerateOptions(database_enabled=True)
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

    def test_fk_resolved_to_object_name(self):
        api, objects_map, fields_map = self._make_api_with_objects(
            fk_object_id="obj-1", on_delete="cascade"
        )
        opts = GenerateOptions()
        result = _convert_to_input_api(api, objects_map, fields_map, opts)
        item_obj = next(o for o in result.objects if o.name == "Item")
        id_field = next(f for f in item_obj.fields if f.name == "id")
        assert id_field.fk == "Item"
        assert id_field.on_delete == "cascade"

    def test_fk_none_when_not_set(self):
        api, objects_map, fields_map = self._make_api_with_objects()
        opts = GenerateOptions()
        result = _convert_to_input_api(api, objects_map, fields_map, opts)
        item_obj = next(o for o in result.objects if o.name == "Item")
        id_field = next(f for f in item_obj.fields if f.name == "id")
        assert id_field.fk is None
```

**Step 2: Run the tests to verify they fail**

Run: `poetry run pytest tests/test_api/test_generation_unit.py::TestConvertToInputApiPkFk -v`
Expected: FAIL — `_convert_to_input_api` doesn't pass `pk`/`fk`/`on_delete` yet.

**Step 3: Commit the failing tests**

```
test(generation): add tests for pk/fk/on_delete pass-through in _convert_to_input_api
```

---

### Task 6: Generation Pipeline — Wire PK/FK through `_convert_to_input_api`

**Files:**
- Modify: `src/api/services/generation.py` — `_convert_to_input_api()` function (lines 181-329)

**Step 1: Update field construction in `_convert_to_input_api`**

Find the loop that builds `InputField` objects (around line 197-215). Change the `InputField(...)` constructor to pass the new association fields.

The association object is `assoc` from the loop `for assoc in sorted(obj.field_associations, ...)`. Add:

```python
                input_field = InputField(
                    name=field.name,
                    type=_build_field_type(
                        field.field_type.python_type, field.container
                    ),
                    optional=assoc.optional,
                    description=field.description,
                    default_value=field.default_value,
                    validators=_build_field_validators(field),
                    field_validators=[
                        InputResolvedFieldValidator(**rv)
                        for rv in _build_resolved_field_validators(field)
                    ],
                    pk=assoc.is_pk,
                    fk=objects_map[assoc.fk_object_id].name if assoc.fk_object_id else None,
                    on_delete=assoc.on_delete or "restrict",
                )
```

**Important:** The `fk` field on `InputField` expects the target object's **name** (a string like `"Order"`), not a UUID. We resolve it through `objects_map`. If `fk_object_id` points to an object not in `objects_map` (i.e., not referenced by any endpoint), we need to fetch it.

**Step 2: Update `_fetch_objects` to also fetch FK-target objects**

The current `_fetch_objects` only fetches objects referenced by endpoints. FK targets might not be endpoint objects. We need a two-pass approach:

After the existing `_fetch_objects` call in `generate_api_zip` (line 62), add a second pass. Actually, it's cleaner to handle this inside `_convert_to_input_api` itself — if `assoc.fk_object_id` is not in `objects_map`, the FK is unresolvable and should be skipped (set `fk=None`). This is safe because the FK target must be an object the user created, and if it's not used in any endpoint, it won't have an ORM model to reference anyway.

So the safe version:

```python
                    fk=(
                        objects_map[assoc.fk_object_id].name
                        if assoc.fk_object_id and assoc.fk_object_id in objects_map
                        else None
                    ),
```

**Step 3: Run the tests to verify they pass**

Run: `poetry run pytest tests/test_api/test_generation_unit.py::TestConvertToInputApiPkFk -v`
Expected: PASS

**Step 4: Run `poetry run black src/`**

**Step 5: Commit**

```
feat(generation): wire pk/fk/on_delete from associations into InputField

- Pass is_pk, fk_object_id, on_delete from ObjectFieldAssociation to InputField
- Resolve fk_object_id UUID to object name via objects_map
- Skip FK resolution when target object is not in endpoints
```

---

### Task 7: Validation — Reject database generation without PK

**Files:**
- Modify: `src/api_craft/transformers.py` — `transform_api()` function (line 358-367)
- Modify: `tests/test_api_craft/test_transformers.py`

**Step 1: Write failing test**

Add to `tests/test_api_craft/test_transformers.py`:

```python
class TestDatabaseValidation:
    def test_database_enabled_without_pk_raises(self):
        """Database generation with no PK fields must raise ValueError."""
        api_input = InputAPI(
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
                InputEndpoint(name="GetItems", path="/items", method="GET", response="Item"),
            ],
            config=InputApiConfig(database={"enabled": True}),
        )
        with pytest.raises(ValueError, match="primary key"):
            transform_api(api_input)

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
                InputEndpoint(name="GetItems", path="/items", method="GET", response="Item"),
            ],
            config=InputApiConfig(database={"enabled": True}),
        )
        result = transform_api(api_input)
        assert result.database_config is not None
        assert len(result.orm_models) == 1
```

Ensure the necessary imports are present at the top of the test file (`InputField`, `InputModel`, `InputEndpoint`, `InputApiConfig`, `InputAPI` from `api_craft.models.input`, and `transform_api` from `api_craft.transformers`).

**Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/test_api_craft/test_transformers.py::TestDatabaseValidation -v`
Expected: FAIL — `transform_api` doesn't raise on missing PKs yet.

**Step 3: Add validation to `transform_api()` in `transformers.py`**

In `transform_api()`, after line 361 (`orm_models = transform_orm_models(input_api.objects)`), add:

```python
        if not orm_models:
            raise ValueError(
                "Database generation requires at least one object with a primary key field. "
                "Mark a field as PK on your objects, or disable database generation."
            )
```

**Step 4: Run tests to verify they pass**

Run: `poetry run pytest tests/test_api_craft/test_transformers.py::TestDatabaseValidation -v`
Expected: PASS

**Step 5: Run the full test suite to check for regressions**

Run: `poetry run pytest tests/test_api_craft/ -v`
Expected: All existing tests pass.

**Step 6: Run `poetry run black src/ tests/`**

**Step 7: Commit**

```
feat(generation): validate at least one PK exists when database is enabled

- Raise ValueError in transform_api when database.enabled but no object has PK
- Add tests for both the rejection and success cases
```

---

### Task 8: Tests — Database codegen dependency verification

**Files:**
- Modify: `tests/test_api_craft/test_db_codegen.py`

**Step 1: Add test verifying database dependencies appear in pyproject.toml**

Add a new test class to `test_db_codegen.py`:

```python
class TestDatabaseDependencies:
    """Verify database dependencies are included in pyproject.toml."""

    def test_sqlalchemy_in_dependencies(self, db_project: Path):
        content = (db_project / "pyproject.toml").read_text()
        assert "sqlalchemy" in content

    def test_asyncpg_in_dependencies(self, db_project: Path):
        content = (db_project / "pyproject.toml").read_text()
        assert "asyncpg" in content

    def test_alembic_in_dependencies(self, db_project: Path):
        content = (db_project / "pyproject.toml").read_text()
        assert "alembic" in content

    def test_no_db_deps_when_disabled(self, tmp_path):
        api_input = load_input("items_api.yaml")
        APIGenerator().generate(api_input, path=str(tmp_path))
        content = (tmp_path / "items-api" / "pyproject.toml").read_text()
        assert "sqlalchemy" not in content
        assert "asyncpg" not in content
        assert "alembic" not in content
```

**Step 2: Run to verify they pass** (these should pass with the existing `items_api_db.yaml` spec since it has `pk: true`)

Run: `poetry run pytest tests/test_api_craft/test_db_codegen.py::TestDatabaseDependencies -v`
Expected: PASS

**Step 3: Commit**

```
test(generation): add dependency verification tests for database codegen
```

---

### Task 9: Update seed SQL

**Files:**
- Modify: `docs/seed-shop-api.sql`

**Step 1: Update the `fields_on_objects` INSERT statements**

The seed SQL inserts field-object associations. Add `is_pk` column to these inserts. For the Shop API, at minimum the `id`-like fields should be marked as PK (if any exist — check the seed SQL to see which fields are used).

If the current seed SQL doesn't have fields that should be PKs, this task is informational only — the seed data just needs the new columns with defaults.

Since the new `is_pk` column has a `server_default=false`, the existing seed SQL will work without changes. However, if you want to demonstrate PK marking, you can add `is_pk` to specific rows.

**Step 2: Commit (if changes made)**

```
docs: add is_pk values to seed shop API field associations
```

---

### Task 10: Full regression test

**Step 1: Run the complete test suite**

Run: `make test`
Expected: All tests pass.

**Step 2: Run `poetry run black src/ tests/`**

**Step 3: If any tests fail, debug and fix before proceeding.**

**Step 4: Final commit if any formatting was needed**

```
style: format code with black
```
