# PK/FK Support on Field-Object Associations

## Problem

When database generation is enabled via the API service, the generated project is broken:

1. `_convert_to_input_api()` builds `InputField` without `pk`, `fk`, or `on_delete` because these columns don't exist on `ObjectFieldAssociation`
2. `transform_orm_models()` skips all objects (none have PK fields) and returns `[]`
3. The `if database_config and orm_models:` guard in `render_components()` is falsy — database dependencies and files are never generated
4. But templates like `main.mako` and `views.mako` check `database_config` independently and emit database imports (`from database import engine`, `from database import get_session`)
5. Result: generated project imports from non-existent modules and references uninstalled packages

The YAML-based test specs work because they set `pk: true` directly. The bug only manifests through the API service flow.

## Solution

Add `is_pk`, `fk_object_id`, and `on_delete` columns to `ObjectFieldAssociation`. Wire them through the full stack: schema, service, API response, generation pipeline. Add validation so database generation fails loudly when no object has a PK field.

## Changes

### 1. Database Schema (modify migration in-place)

**File:** `src/api/migrations/versions/4141ad7f2255_initial_schema.py`

Add to `fields_on_objects` table:

| Column | Type | Default | Notes |
|---|---|---|---|
| `is_pk` | `Boolean` | `False` | Whether this field is the primary key in this object |
| `fk_object_id` | `UUID` | `NULL` | FK to `objects.id` — the target entity this field references |
| `on_delete` | `Text` | `NULL` | One of `cascade`, `restrict`, `set_null`. Only meaningful when `fk_object_id` is set |

Constraints:
- CHECK: `on_delete IN ('cascade', 'restrict', 'set_null')`
- FK: `fk_object_id` references `objects.id`
- No index on `fk_object_id` (low-cardinality lookups, not queried at scale)

### 2. ORM Model

**File:** `src/api/models/database.py` — `ObjectFieldAssociation`

Add three mapped columns matching the migration. Add relationship for `fk_object`.

### 3. API Schema

**File:** `src/api/schemas/object.py` — `ObjectFieldReferenceSchema`

Add:
- `is_pk: bool = Field(default=False, alias="isPk")`
- `fk_object_id: UUID | None = Field(default=None, alias="fkObjectId")`
- `on_delete: OnDeleteAction | None = Field(default=None, alias="onDelete")`

These flow through `ObjectCreate`, `ObjectUpdate`, and `ObjectResponse` unchanged since they all use `ObjectFieldReferenceSchema` for the `fields` array.

### 4. Router Response Builder

**File:** `src/api/routers/objects.py` — `_to_response()`

Pass `is_pk`, `fk_object_id`, and `on_delete` from the association to `ObjectFieldReferenceSchema`.

### 5. Service Layer

**File:** `src/api/services/object.py` — `_set_field_associations()`

Pass `is_pk`, `fk_object_id`, and `on_delete` from the schema to `ObjectFieldAssociation` during creation.

### 6. Generation Pipeline — Wiring

**File:** `src/api/services/generation.py` — `_convert_to_input_api()`

When building `InputField` from database entities, resolve the association's fields:

```python
input_field = InputField(
    ...,
    pk=assoc.is_pk,
    fk=objects_map[assoc.fk_object_id].name if assoc.fk_object_id else None,
    on_delete=assoc.on_delete or "restrict",
)
```

The `fk` field on `InputField` expects the target object's name (not UUID), so we resolve through `objects_map`. This requires `_fetch_objects` to also include FK-target objects (objects referenced by `fk_object_id` but not directly by endpoints).

### 7. Generation Pipeline — Validation

**File:** `src/api_craft/transformers.py` — `transform_api()`

After `transform_orm_models()`, validate:

```python
if input_api.config.database.enabled and not orm_models:
    raise ValueError(
        "Database generation requires at least one object with a primary key field. "
        "Mark a field as PK on your objects, or disable database generation."
    )
```

This ensures the pipeline fails loudly instead of silently producing broken output.

### 8. Seed SQL Update

**File:** `docs/seed-shop-api.sql`

Add `is_pk`, `fk_object_id`, `on_delete` values to the seed SQL field association inserts so the Shop API seed data has proper PK markings.

### 9. Tests

**Existing tests that should continue passing:**
- `test_db_codegen.py` — uses YAML specs with `pk: true`, unaffected
- `test_transformers.py` — tests ORM model creation with PK fields, unaffected
- `test_input_models.py` — tests PK/FK validation, unaffected

**New/updated tests:**
- `test_generation_unit.py` — test that `_convert_to_input_api` passes `pk`/`fk`/`on_delete` from associations
- `test_transformers.py` — test that `transform_api` raises `ValueError` when `database.enabled` and no PKs
- `test_api/test_objects.py` — test that `is_pk`, `fk_object_id`, `on_delete` round-trip through create/get/update

## Out of Scope

- Frontend changes to expose PK/FK UI controls (separate task, requires instructions to frontend Claude)
- Composite primary keys (explicitly not supported, validated against)
- Auto-PK inference heuristics
