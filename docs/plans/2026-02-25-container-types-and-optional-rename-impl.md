# Container Types & Required→Optional Rename — Backend Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `List` container support to fields and rename the `required` boolean to `optional` (inverted semantics) on object-field references. Backend only — DB model, API schemas, service layer, codegen.

**Architecture:** Two changes sharing one migration update. Part A adds a nullable `container` column with CHECK constraint to `FieldModel`. Part B renames `required` → `optional` on `ObjectFieldAssociation` and inverts the boolean semantics. Both flow through schemas → service → codegen.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, Pydantic v2, Alembic, Mako templates, pytest

**Design doc:** See `docs/plans/2026-02-25-container-types-and-optional-rename-design.md` in the frontend repo for full design rationale and decision record.

---

## Part A: Container Types (List)

### Task 1: Add `container` column to FieldModel and migration

**Files:**
- Modify: `src/api/models/database.py` (FieldModel class, ~line 311-356)
- Modify: `src/api/migrations/versions/4141ad7f2255_initial_schema.py` (fields table, ~line 217-241)

**Step 1: Add column to FieldModel with CHECK constraint**

In `database.py`, add to `FieldModel` after the `default_value` column:

```python
from sqlalchemy import CheckConstraint

container: Mapped[str | None] = mapped_column(String, nullable=True, default=None)

__table_args__ = (
    CheckConstraint("container IN ('List')", name="ck_fields_container"),
)
```

Note: If `FieldModel` already has a `__table_args__`, merge the new `CheckConstraint` into the existing tuple.

**Step 2: Add column and CHECK constraint to migration**

In the initial schema migration, inside the `fields` table definition, add:

```python
sa.Column("container", sa.String(), nullable=True),
sa.CheckConstraint("container IN ('List')", name="ck_fields_container"),
```

**Step 3: Run tests to verify model loads**

```bash
python -m pytest tests/test_api/test_models/ -v --timeout=10
```

**Step 4: Commit**

```bash
git add src/api/models/database.py src/api/migrations/versions/4141ad7f2255_initial_schema.py
git commit -m "feat(fields): add container column to FieldModel"
```

---

### Task 2: Add `container` to field API schemas

**Files:**
- Modify: `src/api/schemas/field.py` (FieldCreate ~line 65, FieldUpdate ~line 90, FieldResponse ~line 109)

**Step 1: Add `container` field to all three schemas**

Add to `FieldCreate`:
```python
container: str | None = Field(default=None, alias="container", examples=["List"])
```

Add to `FieldUpdate`:
```python
container: str | None = Field(default=None, alias="container", examples=["List"])
```

Add to `FieldResponse`:
```python
container: str | None = Field(default=None, alias="container")
```

**Step 2: Add container validation to FieldCreate and FieldUpdate**

Add a Pydantic validator to both schemas that rejects values other than `None` or `"List"`:

```python
from pydantic import field_validator

@field_validator("container")
@classmethod
def validate_container(cls, v: str | None) -> str | None:
    if v is not None and v not in ("List",):
        raise ValueError(f'Invalid container "{v}". Must be null or "List".')
    return v
```

**Step 3: Run schema tests**

```bash
python -m pytest tests/test_api/test_schemas/ -v --timeout=10
```

**Step 4: Commit**

```bash
git add src/api/schemas/field.py
git commit -m "feat(fields): add container field to field API schemas"
```

---

### Task 3: Pass `container` through field service layer

**Files:**
- Modify: `src/api/services/field.py` (create_for_user ~line 92, update_field ~line 122)

**Step 1: Pass `container` in create_for_user**

In the `FieldModel(...)` constructor call inside `create_for_user`, add:

```python
container=data.container,
```

**Step 2: Pass `container` in update_field**

In `update_field`, add container to the fields being updated:

```python
if data.container is not None:
    field.container = data.container
```

Note: Since `container` can legitimately be `None` (meaning "remove container"), use a sentinel or always set it. Check how other nullable fields are handled in this method. If the method uses `exclude_unset=True` pattern, `container` will only be set when explicitly provided.

**Step 3: Run field service tests**

```bash
python -m pytest tests/test_api/test_services/test_field.py -v --timeout=30
```

**Step 4: Commit**

```bash
git add src/api/services/field.py
git commit -m "feat(fields): pass container through field service layer"
```

---

### Task 4: Update generation service to compose container types

**Files:**
- Modify: `src/api/services/generation.py` (~line 316 `_map_field_type`, ~line 196 where InputField is built)

**Step 1: Update `_map_field_type` to accept container**

Change the function signature and logic:

```python
def _map_field_type(field_type: str, container: str | None = None) -> str:
    type_mapping = {
        "str": "str",
        "int": "int",
        "float": "float",
        "bool": "bool",
        "datetime": "datetime.datetime",
        "uuid": "str",
        "EmailStr": "EmailStr",
        "HttpUrl": "HttpUrl",
    }
    base = type_mapping.get(field_type, "str")
    if container:
        return f"{container}[{base}]"
    return base
```

**Step 2: Pass container from field model to `_map_field_type`**

Where `InputField` is constructed (~line 196), update the `type` argument:

```python
type=_map_field_type(field.field_type.name, field.container),
```

**Step 3: Run generation tests**

```bash
python -m pytest tests/test_api/test_services/test_generation.py -v --timeout=30
```

**Step 4: Commit**

```bash
git add src/api/services/generation.py
git commit -m "feat(codegen): compose container types in field type mapping"
```

---

### Task 5: Add/update backend tests for container feature

**Files:**
- Modify: `tests/test_api/test_services/test_field.py`
- Modify: `tests/test_api/test_services/test_generation.py`

**Step 1: Add test for creating a field with container**

```python
async def test_create_field_with_list_container(self, ...):
    # Create a field with container="List"
    field_data = FieldCreate(
        namespace_id=ns_id,
        name="tags",
        type_id=str_type_id,
        container="List"
    )
    field = await field_service.create_for_user(user_id, field_data)
    assert field.container == "List"
```

**Step 2: Add test for container validation**

```python
async def test_create_field_with_invalid_container_rejects(self, ...):
    with pytest.raises(ValidationError):
        FieldCreate(
            namespace_id=ns_id,
            name="bad",
            type_id=str_type_id,
            container="Set"  # Not allowed
        )
```

**Step 3: Add test for generation with container**

```python
async def test_generation_with_list_field(self, ...):
    # Create field with container="List", type=str
    # Generate code
    # Assert generated type string contains "List[str]"
```

**Step 4: Run all tests**

```bash
python -m pytest tests/ -v --timeout=60
```

**Step 5: Commit**

```bash
git add tests/
git commit -m "test(fields): add tests for container type support"
```

---

## Part B: Required → Optional Rename

### Task 6: Rename `required` → `optional` on ObjectFieldAssociation model and migration

**Files:**
- Modify: `src/api/models/database.py` (ObjectFieldAssociation ~line 454)
- Modify: `src/api/migrations/versions/4141ad7f2255_initial_schema.py` (fields_on_objects table ~line 307)

**Step 1: Rename column in model**

Change:
```python
required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
```
To:
```python
optional: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
```

Update the docstring to reflect: `optional: Whether this field is optional in the object (default False = required).`

**Step 2: Rename column in migration**

Change:
```python
sa.Column("required", sa.Boolean(), nullable=False),
```
To:
```python
sa.Column("optional", sa.Boolean(), nullable=False),
```

**Step 3: Commit**

```bash
git add src/api/models/database.py src/api/migrations/versions/4141ad7f2255_initial_schema.py
git commit -m "refactor(objects): rename required to optional on ObjectFieldAssociation"
```

---

### Task 7: Rename `required` → `optional` in object API schemas

**Files:**
- Modify: `src/api/schemas/object.py` (ObjectFieldReferenceSchema ~line 19)

**Step 1: Rename field**

Change:
```python
required: bool = Field(..., examples=[True])
```
To:
```python
optional: bool = Field(default=False, examples=[False])
```

Update the docstring: `:ivar optional: Whether this field is optional in the object.`

**Step 2: Commit**

```bash
git add src/api/schemas/object.py
git commit -m "refactor(objects): rename required to optional in object schemas"
```

---

### Task 8: Update object service to use `optional`

**Files:**
- Modify: `src/api/services/object.py` (_set_field_associations ~line 190)

**Step 1: Change field reference**

Change:
```python
required=field_ref.required,
```
To:
```python
optional=field_ref.optional,
```

**Step 2: Run object service tests**

```bash
python -m pytest tests/test_api/test_services/test_object.py -v --timeout=30
```

**Step 3: Commit**

```bash
git add src/api/services/object.py
git commit -m "refactor(objects): update service to use optional field"
```

---

### Task 9: Update generation service and codegen to use `optional`

**Files:**
- Modify: `src/api/services/generation.py` (~line 196 where `required=assoc.required`)
- Modify: `src/api_craft/models/input.py` (InputField ~line 65, InputQueryParam ~line 98)
- Modify: `src/api_craft/transformers.py` (~line 91 and ~line 128)
- Modify: `src/api_craft/templates/models.mako` (~line 49, 54)
- Modify: `src/api_craft/templates/views.mako` (~line 39)

**Step 1: Rename in InputField and InputQueryParam**

In `input.py`, change both classes:
```python
# InputField
optional: bool = False  # was: required: bool = False

# InputQueryParam
optional: bool = False  # was: required: bool = False
```

Update docstrings accordingly.

**Step 2: Update generation service**

Where InputField is constructed (~line 196), change:
```python
required=assoc.required,
```
To:
```python
optional=assoc.optional,
```

Similarly for InputQueryParam construction (~line 268).

**Step 3: Update transformers**

In `transformers.py`, update `transform_field` and `transform_query_params` to pass `optional` instead of `required`.

**Step 4: Update Mako templates**

In `models.mako`, change:
```mako
# Was: if field.required:
if not field.optional:
    return f'{field.name}: {type_annotation} = Field(...)'
else:
    return f'{field.name}: {type_annotation} | None = Field(default=None, ...)'
```

In `views.mako`, change:
```mako
# Was: suffix = "" if q_param.required else " = None"
suffix = " = None" if q_param.optional else ""
```

**Step 5: Run all backend tests**

```bash
python -m pytest tests/ -v --timeout=60
```

**Step 6: Commit**

```bash
git add src/api/services/generation.py src/api_craft/
git commit -m "refactor(codegen): rename required to optional across generation pipeline"
```

---

### Task 10: Update backend tests for required→optional rename

**Files:**
- Modify: `tests/test_api/test_services/test_object.py` (~line 121)
- Modify: Any other test files referencing `required` on object-field associations

**Step 1: Search and replace in tests**

Search all test files for `"required":` in object field reference contexts and replace with `"optional":`, inverting the boolean values:
- `"required": True` → `"optional": False`
- `"required": False` → `"optional": True`

**Step 2: Run all tests**

```bash
python -m pytest tests/ -v --timeout=60
```

**Step 3: Commit**

```bash
git add tests/
git commit -m "test(objects): update tests for required→optional rename"
```

---

## Final Verification

### Task 11: Full backend test suite

**Step 1: Run all tests**

```bash
python -m pytest tests/ -v --timeout=120
```

Expected: All pass, 0 failures.

**Step 2: Commit any remaining fixes**

```bash
git add -A && git commit -m "fix: address test failures from container and optional rename"
```

---

## Expected API Contract After Implementation

### Field Response (GET/POST/PUT /fields)

```json
{
  "id": "uuid",
  "namespaceId": "uuid",
  "name": "tags",
  "typeId": "uuid-of-str",
  "container": "List",
  "description": "User tags",
  "defaultValue": null,
  "usedInApis": [],
  "constraints": [],
  "validators": []
}
```

`container`: `"List"` or `null` (new field).

### Object Response (GET/POST/PUT /objects)

```json
{
  "id": "uuid",
  "namespaceId": "uuid",
  "name": "User",
  "description": "User account",
  "fields": [
    { "fieldId": "uuid", "optional": false },
    { "fieldId": "uuid", "optional": true }
  ],
  "usedInApis": [],
  "validators": []
}
```

`optional`: replaces `required` with inverted semantics. `false` = required (default), `true` = optional.
