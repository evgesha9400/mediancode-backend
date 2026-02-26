# Enum Check Constraints Design

Consolidate enforcement for all ENUM-like fields across three layers (DB, API, UI) using a single source of truth pattern.

## Decision Record

- **PG ENUMs → CHECK constraints.** PostgreSQL ENUM types are hard to evolve (can't remove values, can't ALTER in a transaction). CHECK constraints provide equal enforcement with simpler migrations.
- **Literal types as source of truth.** No Python `Enum` classes. `Literal` is already the codebase pattern, works natively with Pydantic, and `get_args()` enables runtime extraction.
- **Canonical definitions in `src/api/schemas/literals.py`.** The `api` package owns the DB and is the authority. `api_craft` imports from it.
- **OpenAPI spec as frontend contract.** Pydantic `Literal` types produce `enum` arrays in OpenAPI JSON schema automatically. No runtime endpoint or codegen needed.
- **Clean migration rewrite.** Development stage with no users — rewrite the initial migration in-place, DB resets on deploy.

## Inventory of ENUM-like Fields

| Table | Column | Current Enforcement | Allowed Values |
|---|---|---|---|
| `api_endpoints` | `method` | PG ENUM `http_method` | GET, POST, PUT, PATCH, DELETE |
| `api_endpoints` | `response_shape` | PG ENUM `response_shape` | object, list |
| `fields` | `container` | CHECK constraint | List (or NULL) |
| `field_validator_templates` | `mode` | None | before, after |
| `model_validator_templates` | `mode` | None | before, after |

## Source of Truth: `src/api/schemas/literals.py`

New file defining 4 canonical Literal types:

```python
from typing import Literal, get_args

HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
ResponseShape = Literal["object", "list"]
Container = Literal["List"]
ValidatorMode = Literal["before", "after"]

def check_constraint_sql(column: str, literal_type: type) -> str:
    values = ", ".join(f"'{v}'" for v in get_args(literal_type))
    return f"{column} IN ({values})"
```

## Layer 1: Database (Migration)

Rewrite `4141ad7f2255_initial_schema.py` in-place.

### `api_endpoints` table

Replace `sa.Enum(...)` columns with `sa.String()` + `sa.CheckConstraint(...)`:

```python
# method
sa.Column("method", sa.String(), nullable=False),
sa.CheckConstraint(
    "method IN ('GET', 'POST', 'PUT', 'PATCH', 'DELETE')",
    name="ck_api_endpoints_method",
),

# response_shape
sa.Column("response_shape", sa.String(), nullable=False),
sa.CheckConstraint(
    "response_shape IN ('object', 'list')",
    name="ck_api_endpoints_response_shape",
),
```

### `field_validator_templates` table

Add CHECK constraint:

```python
sa.CheckConstraint(
    "mode IN ('before', 'after')",
    name="ck_field_validator_templates_mode",
),
```

### `model_validator_templates` table

Add CHECK constraint:

```python
sa.CheckConstraint(
    "mode IN ('before', 'after')",
    name="ck_model_validator_templates_mode",
),
```

### `fields` table

No change — `ck_fields_container` already exists.

### Downgrade

Remove the two `DROP TYPE` statements for `http_method` and `response_shape` (no longer exist).

### CHECK constraint naming convention

`ck_{table}_{column}` — consistent with existing `ck_fields_container`.

## Layer 2: API (Pydantic Schemas + SQLAlchemy Models)

### `src/api/models/database.py`

- `ApiEndpoint.method`: `Enum("GET", ..., name="http_method")` → `String`
- `ApiEndpoint.response_shape`: `Enum("object", "list", name="response_shape")` → `String`
- Remove `Enum` from the sqlalchemy imports (no longer used)

### `src/api/schemas/endpoint.py`

- Import `HttpMethod`, `ResponseShape` from `literals.py`
- `ApiEndpointCreate.method`: `Literal["GET", ...]` → `HttpMethod`
- `ApiEndpointCreate.response_shape`: `Literal["object", "list"]` → `ResponseShape`
- `ApiEndpointUpdate.method`: `Literal[...] | None` → `HttpMethod | None`
- `ApiEndpointUpdate.response_shape`: `Literal[...] | None` → `ResponseShape | None`
- `ApiEndpointResponse.method`: `str` → `HttpMethod` (fix: was missing Literal)
- `ApiEndpointResponse.response_shape`: `str` → `ResponseShape` (fix: was missing Literal)
- Remove `from typing import Literal` (no longer used directly)

### `src/api/schemas/field.py`

- Import `Container` from `literals.py`
- `FieldCreate.container`: `str | None` → `Container | None`; delete `validate_container` method
- `FieldUpdate.container`: `str | None` → `Container | None`; delete `validate_container` method
- `FieldResponse.container`: `str | None` → `Container | None`
- Remove `field_validator` from pydantic imports (no longer used)

## Layer 3: UI (via OpenAPI)

No backend code changes needed. Pydantic `Literal` types automatically produce `enum` arrays in the OpenAPI JSON schema. The frontend reads these to populate dropdowns and client-side validation.

## api_craft Package Updates

### `src/api_craft/models/input.py`

- `InputEndpoint.method`: `str` → `HttpMethod` (was unvalidated)
- `InputEndpoint.response_shape`: `Literal["object", "list"]` → `ResponseShape`
- `InputResolvedFieldValidator.mode`: `str` → `ValidatorMode`
- `InputResolvedModelValidator.mode`: `str` → `ValidatorMode`

### `src/api_craft/models/template.py`

- `TemplateView.method`: `str` → `HttpMethod`
- `TemplateView.response_shape`: `Literal["object", "list"]` → `ResponseShape`
- `TemplateResolvedFieldValidator.mode`: `str` → `ValidatorMode`
- `TemplateResolvedModelValidator.mode`: `str` → `ValidatorMode`

## Change Summary

| Layer | File | Change |
|---|---|---|
| Source of truth | `src/api/schemas/literals.py` | New file — 4 Literal types + helper |
| Migration | `4141ad7f2255_initial_schema.py` | ENUM → String + CHECK; add CHECK for mode; remove ENUM drops |
| DB models | `src/api/models/database.py` | `Enum(...)` → `String`; remove `Enum` import |
| API schemas | `src/api/schemas/endpoint.py` | Inline `Literal` → imported types; fix response schema |
| API schemas | `src/api/schemas/field.py` | `str` + validator → `Container` Literal; delete validators |
| api_craft | `src/api_craft/models/input.py` | `str` → typed Literals |
| api_craft | `src/api_craft/models/template.py` | `str` → typed Literals |

## Not Included (YAGNI)

- No runtime `/meta/enums` endpoint
- No Python `Enum` classes
- No frontend codegen pipeline
