# Enum Check Constraints Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Consolidate all ENUM-like fields to use Literal types as the single source of truth, with CHECK constraints at the DB level, Pydantic Literal validation at the API level, and OpenAPI enum arrays for the UI.

**Architecture:** A new `literals.py` module defines canonical Literal types. Pydantic schemas import these types for validation. The initial migration is rewritten in-place to use String + CHECK constraints instead of PG ENUMs. No new migration files.

**Tech Stack:** Python 3.13, SQLAlchemy, Alembic, Pydantic v2, FastAPI, PostgreSQL

**Design doc:** `docs/plans/2026-02-26-enum-check-constraints-design.md`

---

### Task 1: Create `literals.py` — Single Source of Truth

**Files:**
- Create: `src/api/schemas/literals.py`
- Test: `tests/test_api/test_literals.py`

**Step 1: Write the test file**

```python
# tests/test_api/test_literals.py
"""Unit tests for canonical Literal type definitions."""

from typing import get_args

from api.schemas.literals import (
    Container,
    HttpMethod,
    ResponseShape,
    ValidatorMode,
    check_constraint_sql,
)


class TestLiteralValues:
    """Verify each Literal type exposes the expected values."""

    def test_http_method_values(self):
        assert get_args(HttpMethod) == ("GET", "POST", "PUT", "PATCH", "DELETE")

    def test_response_shape_values(self):
        assert get_args(ResponseShape) == ("object", "list")

    def test_container_values(self):
        assert get_args(Container) == ("List",)

    def test_validator_mode_values(self):
        assert get_args(ValidatorMode) == ("before", "after")


class TestCheckConstraintSql:
    """Verify SQL generation from Literal types."""

    def test_http_method_sql(self):
        sql = check_constraint_sql("method", HttpMethod)
        assert sql == "method IN ('GET', 'POST', 'PUT', 'PATCH', 'DELETE')"

    def test_response_shape_sql(self):
        sql = check_constraint_sql("response_shape", ResponseShape)
        assert sql == "response_shape IN ('object', 'list')"

    def test_container_sql(self):
        sql = check_constraint_sql("container", Container)
        assert sql == "container IN ('List')"

    def test_validator_mode_sql(self):
        sql = check_constraint_sql("mode", ValidatorMode)
        assert sql == "mode IN ('before', 'after')"
```

**Step 2: Run tests — verify they fail**

Run: `poetry run pytest tests/test_api/test_literals.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.schemas.literals'`

**Step 3: Create `literals.py`**

```python
# src/api/schemas/literals.py
"""Canonical Literal types for all ENUM-like fields.

Single source of truth consumed by:
- Pydantic schemas (type annotations)
- SQLAlchemy models (column types reference these indirectly)
- Alembic migrations (CHECK constraint SQL values must match)
- OpenAPI spec (Pydantic auto-generates enum arrays from Literals)
"""

from typing import Literal, get_args

HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
ResponseShape = Literal["object", "list"]
Container = Literal["List"]
ValidatorMode = Literal["before", "after"]


def check_constraint_sql(column: str, literal_type: type) -> str:
    """Generate a CHECK constraint SQL clause from a Literal type.

    :param column: The database column name.
    :param literal_type: A Literal type alias (e.g. HttpMethod).
    :returns: SQL string like "column IN ('val1', 'val2')".
    """
    values = ", ".join(f"'{v}'" for v in get_args(literal_type))
    return f"{column} IN ({values})"
```

**Step 4: Run tests — verify they pass**

Run: `poetry run pytest tests/test_api/test_literals.py -v`
Expected: All 8 tests PASS

**Step 5: Format and commit**

```bash
poetry run black src/api/schemas/literals.py tests/test_api/test_literals.py
git add src/api/schemas/literals.py tests/test_api/test_literals.py
git commit -m "feat(models): add canonical Literal types in literals.py

- Define HttpMethod, ResponseShape, Container, ValidatorMode
- Add check_constraint_sql helper for generating CHECK SQL
- Add unit tests for all Literal values and SQL generation"
```

---

### Task 2: Update Pydantic Schemas — `endpoint.py`

**Files:**
- Modify: `src/api/schemas/endpoint.py`

**Step 1: Replace inline Literals with canonical imports**

In `src/api/schemas/endpoint.py`:

- Replace `from typing import Literal` with `from api.schemas.literals import HttpMethod, ResponseShape`
- `ApiEndpointCreate.method`: `Literal["GET", "POST", "PUT", "PATCH", "DELETE"]` → `HttpMethod`
- `ApiEndpointCreate.response_shape`: `Literal["object", "list"]` → `ResponseShape`
- `ApiEndpointUpdate.method`: `Literal["GET", "POST", "PUT", "PATCH", "DELETE"] | None` → `HttpMethod | None`
- `ApiEndpointUpdate.response_shape`: `Literal["object", "list"] | None` → `ResponseShape | None`
- `ApiEndpointResponse.method`: `str` → `HttpMethod` (fix: was missing enum in OpenAPI)
- `ApiEndpointResponse.response_shape`: `str` → `ResponseShape` (fix: was missing enum in OpenAPI)

**Step 2: Run existing tests**

Run: `poetry run pytest tests/ -v --ignore=tests/output -k "not manual"`
Expected: All tests PASS (no behavioral change, same Literal values)

**Step 3: Format and commit**

```bash
poetry run black src/api/schemas/endpoint.py
git add src/api/schemas/endpoint.py
git commit -m "refactor(models): use canonical Literal types in endpoint schemas

- Import HttpMethod and ResponseShape from literals.py
- Fix ApiEndpointResponse to use Literal types instead of plain str
- OpenAPI spec now emits enum arrays for response schemas too"
```

---

### Task 3: Update Pydantic Schemas — `field.py`

**Files:**
- Modify: `src/api/schemas/field.py`

**Step 1: Replace custom validator with Literal type**

In `src/api/schemas/field.py`:

- Add import: `from api.schemas.literals import Container`
- `FieldCreate.container`: `str | None` → `Container | None`
- Delete `FieldCreate.validate_container` method entirely (lines 90-95)
- `FieldUpdate.container`: `str | None` → `Container | None`
- Delete `FieldUpdate.validate_container` method entirely (lines 117-122)
- `FieldResponse.container`: `str | None` → `Container | None`
- Remove `field_validator` from `from pydantic import BaseModel, ConfigDict, Field, field_validator` (no longer used)

**Step 2: Run existing tests**

Run: `poetry run pytest tests/ -v --ignore=tests/output -k "not manual"`
Expected: All tests PASS. The Literal type rejects the same invalid values the custom validator did, but with Pydantic's standard error format instead of the custom message.

**Step 3: Format and commit**

```bash
poetry run black src/api/schemas/field.py
git add src/api/schemas/field.py
git commit -m "refactor(models): use Container Literal type in field schemas

- Replace custom @field_validator with Literal['List'] type
- Pydantic now validates container values natively
- OpenAPI spec emits enum array for container field"
```

---

### Task 4: Update `api_craft` Models

**Files:**
- Modify: `src/api_craft/models/input.py`
- Modify: `src/api_craft/models/template.py`

**Step 1: Update `input.py`**

In `src/api_craft/models/input.py`:

- Add import: `from api.schemas.literals import HttpMethod, ResponseShape, ValidatorMode`
- Remove `Literal` from the `from typing import ...` line (keep `Any`, `Self`)
- `InputEndpoint.method`: `str` → `HttpMethod`
- `InputEndpoint.response_shape`: `Literal["object", "list"]` → `ResponseShape`
- `InputResolvedFieldValidator.mode`: `str` → `ValidatorMode`
- `InputResolvedModelValidator.mode`: `str` → `ValidatorMode`

**Step 2: Update `template.py`**

In `src/api_craft/models/template.py`:

- Add import: `from api.schemas.literals import HttpMethod, ResponseShape, ValidatorMode`
- Remove `Literal` from the `from typing import ...` line (keep `Any`)
- `TemplateView.method`: `str` → `HttpMethod`
- `TemplateView.response_shape`: `Literal["object", "list"]` → `ResponseShape`
- `TemplateResolvedFieldValidator.mode`: `str` → `ValidatorMode`
- `TemplateResolvedModelValidator.mode`: `str` → `ValidatorMode`

**Step 3: Run codegen tests**

Run: `poetry run pytest tests/test_api_craft/ -v -k "not manual"`
Expected: All tests PASS. The existing YAML specs use valid values (GET, POST, object, list, before, after), so no test data changes needed.

**Step 4: Format and commit**

```bash
poetry run black src/api_craft/models/input.py src/api_craft/models/template.py
git add src/api_craft/models/input.py src/api_craft/models/template.py
git commit -m "refactor(generation): use canonical Literal types in api_craft models

- InputEndpoint.method now validated (was plain str)
- All mode fields now validated as before/after
- Import from api.schemas.literals as single source of truth"
```

---

### Task 5: Update SQLAlchemy Model — `database.py`

**Files:**
- Modify: `src/api/models/database.py`

**Step 1: Replace Enum columns with String**

In `src/api/models/database.py`:

- Remove `Enum` from the sqlalchemy imports line (line 13)
- `ApiEndpoint.method` (line 580-583): Replace `Enum("GET", "POST", "PUT", "PATCH", "DELETE", name="http_method")` with `String`
- `ApiEndpoint.response_shape` (line 598-602): Replace `Enum("object", "list", name="response_shape")` with `String, default="object"`

The result for `ApiEndpoint`:

```python
method: Mapped[str] = mapped_column(String, nullable=False)
```

```python
response_shape: Mapped[str] = mapped_column(String, default="object", nullable=False)
```

**Step 2: Run existing tests**

Run: `poetry run pytest tests/ -v --ignore=tests/output -k "not manual"`
Expected: All tests PASS

**Step 3: Format and commit**

```bash
poetry run black src/api/models/database.py
git add src/api/models/database.py
git commit -m "refactor(models): replace SQLAlchemy Enum with String columns

- ApiEndpoint.method and response_shape now use String type
- Remove Enum import from sqlalchemy (no longer used)
- CHECK constraints enforced at migration level, not ORM level"
```

---

### Task 6: Rewrite Migration — Replace ENUMs with CHECK Constraints

**Files:**
- Modify: `src/api/migrations/versions/4141ad7f2255_initial_schema.py`

**Step 1: Update `api_endpoints` table in upgrade()**

Replace (lines 404-407):
```python
sa.Column(
    "method",
    sa.Enum("GET", "POST", "PUT", "PATCH", "DELETE", name="http_method"),
    nullable=False,
),
```
With:
```python
sa.Column("method", sa.String(), nullable=False),
```

Replace (lines 428-432):
```python
sa.Column(
    "response_shape",
    sa.Enum("object", "list", name="response_shape"),
    nullable=False,
),
```
With:
```python
sa.Column("response_shape", sa.String(), nullable=False),
```

Add CHECK constraints inside the `create_table("api_endpoints", ...)` call, after the `sa.PrimaryKeyConstraint`:
```python
sa.CheckConstraint(
    "method IN ('GET', 'POST', 'PUT', 'PATCH', 'DELETE')",
    name="ck_api_endpoints_method",
),
sa.CheckConstraint(
    "response_shape IN ('object', 'list')",
    name="ck_api_endpoints_response_shape",
),
```

**Step 2: Add CHECK constraint to `field_validator_templates` table**

Add inside the `create_table("field_validator_templates", ...)` call, after the `sa.PrimaryKeyConstraint`:
```python
sa.CheckConstraint(
    "mode IN ('before', 'after')",
    name="ck_field_validator_templates_mode",
),
```

**Step 3: Add CHECK constraint to `model_validator_templates` table**

Add inside the `create_table("model_validator_templates", ...)` call, after the `sa.PrimaryKeyConstraint`:
```python
sa.CheckConstraint(
    "mode IN ('before', 'after')",
    name="ck_model_validator_templates_mode",
),
```

**Step 4: Update downgrade()**

Remove lines 512-513:
```python
op.execute("DROP TYPE IF EXISTS http_method")
op.execute("DROP TYPE IF EXISTS response_shape")
```

Also remove the `sa.Enum` import if it was explicitly imported (check the migration's imports — it uses `sa.Enum(...)` via the `sa` namespace, so no separate import to remove).

**Step 5: Format and commit**

```bash
poetry run black src/api/migrations/versions/4141ad7f2255_initial_schema.py
git add src/api/migrations/versions/4141ad7f2255_initial_schema.py
git commit -m "feat(models): replace PG ENUMs with CHECK constraints in migration

- api_endpoints.method: ENUM → String + CHECK (ck_api_endpoints_method)
- api_endpoints.response_shape: ENUM → String + CHECK (ck_api_endpoints_response_shape)
- field_validator_templates.mode: add CHECK (ck_field_validator_templates_mode)
- model_validator_templates.mode: add CHECK (ck_model_validator_templates_mode)
- Remove DROP TYPE statements from downgrade (ENUMs no longer exist)"
```

---

### Task 7: Reset Local Database and Run Full Test Suite

**Step 1: Reset the local database**

The migration was edited in-place, so the local DB schema is stale. Reset it:

```bash
cd /Users/evgesha/Documents/Projects/median-code-backend
poetry run alembic downgrade base
poetry run alembic upgrade head
```

If downgrade fails (because the old ENUM types don't exist), drop and recreate:
```bash
docker exec -i median-code-backend-db-1 psql -U median_user -d median_db -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
poetry run alembic upgrade head
```

**Step 2: Run the full test suite**

Run: `poetry run pytest tests/ -v --ignore=tests/output -k "not manual"`
Expected: All tests PASS

**Step 3: Verify CHECK constraints exist in the database**

```bash
docker exec -i median-code-backend-db-1 psql -U median_user -d median_db -c "\d api_endpoints"
```

Expected output should show:
- `method` column as `character varying` (not an enum)
- `response_shape` column as `character varying` (not an enum)
- CHECK constraints listed: `ck_api_endpoints_method`, `ck_api_endpoints_response_shape`

```bash
docker exec -i median-code-backend-db-1 psql -U median_user -d median_db -c "SELECT conname FROM pg_constraint WHERE conname LIKE 'ck_%';"
```

Expected: 5 rows:
- `ck_fields_container`
- `ck_api_endpoints_method`
- `ck_api_endpoints_response_shape`
- `ck_field_validator_templates_mode`
- `ck_model_validator_templates_mode`

**Step 4: Verify no PG ENUMs remain**

```bash
docker exec -i median-code-backend-db-1 psql -U median_user -d median_db -c "SELECT typname FROM pg_type WHERE typtype = 'e';"
```

Expected: 0 rows (no enum types)

---

### Task 8: Final Formatting and Cleanup

**Step 1: Run Black on all modified files**

```bash
poetry run black src/ tests/
```

**Step 2: Run full test suite one final time**

Run: `poetry run pytest tests/ -v --ignore=tests/output -k "not manual"`
Expected: All tests PASS

**Step 3: Final commit if any formatting changes**

```bash
git add -A
git status
# Only commit if there are changes
git commit -m "style: format all files with Black"
```
