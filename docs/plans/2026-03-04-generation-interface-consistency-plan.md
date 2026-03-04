# Generation Pipeline Interface Consistency Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix 6 interface mismatches between `src/api/services/generation.py` and `src/api_craft/models/input.py` so the generation pipeline correctly maps all DB entities to InputAPI format.

**Architecture:** The generation service bridges SQLAlchemy DB models to api_craft's `InputAPI` Pydantic model. We fix the bridge layer: enforce PascalCase on API titles at the REST boundary, replace the hardcoded type mapping with data-driven `python_type` from the DB, remove broken `_to_pascal_case()` calls on already-PascalCase names, fix endpoint name derivation, and expand the api_craft type validator to accept all seeded types.

**Tech Stack:** Python 3.13+, FastAPI, Pydantic, SQLAlchemy, pytest

---

### Task 1: Expand SUPPORTED_TYPE_IDENTIFIERS in api_craft validators

**Files:**
- Modify: `src/api_craft/models/validators.py:22-29`
- Test: `tests/test_api_craft/test_name_types.py`

**Step 1: Write the failing test**

Add to `tests/test_api_craft/test_name_types.py`:

```python
from api_craft.models.validators import validate_type_annotation


class TestValidateTypeAnnotation:
    """Tests that type annotation validator accepts all supported types."""

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
        """All DB-seeded types must pass validation."""
        validate_type_annotation(type_str, set(), context="test")

    @pytest.mark.parametrize(
        "type_str",
        ["UnknownType", "FooBar", "numpy.ndarray"],
    )
    def test_rejects_unknown_type(self, type_str: str):
        """Unknown types must be rejected unless declared as objects."""
        with pytest.raises(ValueError, match="Unknown type reference"):
            validate_type_annotation(type_str, set(), context="test")

    def test_accepts_declared_object_name(self):
        """Declared object names pass validation."""
        validate_type_annotation("MyObject", {"MyObject"}, context="test")
```

**Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/test_api_craft/test_name_types.py::TestValidateTypeAnnotation -v`
Expected: FAIL — `datetime.date`, `datetime.time`, `uuid.UUID`, `EmailStr`, `HttpUrl`, `Decimal` will fail with "Unknown type reference"

**Step 3: Write minimal implementation**

In `src/api_craft/models/validators.py`, replace lines 22-29:

```python
SUPPORTED_TYPE_IDENTIFIERS = {
    "str",
    "int",
    "bool",
    "float",
    "datetime",
    "date",
    "time",
    "uuid",
    "UUID",
    "EmailStr",
    "HttpUrl",
    "Decimal",
    "List",
}
```

Update the comment above it (lines 14-21) to:

```python
# Supported type identifiers for validation. These are the tokens that appear
# when type annotation strings are tokenized by TYPE_IDENTIFIER_PATTERN:
#   - "datetime.datetime" becomes tokens {"datetime"}
#   - "datetime.date" becomes tokens {"datetime", "date"}
#   - "uuid.UUID" becomes tokens {"uuid", "UUID"}
#   - "List[T]" becomes tokens {"List", "T"}
# Includes all primitive types, module names, and pydantic special types.
```

**Step 4: Run test to verify it passes**

Run: `poetry run pytest tests/test_api_craft/test_name_types.py -v`
Expected: ALL PASS

**Step 5: Run full test suite**

Run: `poetry run pytest tests/test_api_craft/ -v`
Expected: ALL PASS

**Step 6: Format and commit**

```bash
poetry run black src/api_craft/models/validators.py tests/test_api_craft/test_name_types.py
git add src/api_craft/models/validators.py tests/test_api_craft/test_name_types.py
git commit -m "feat(models): expand supported type identifiers for all DB-seeded types

- Add date, time, uuid, UUID, EmailStr, HttpUrl, Decimal to SUPPORTED_TYPE_IDENTIFIERS
- Add tests for type annotation validation with all supported types"
```

---

### Task 2: Enforce PascalCase on API title at REST boundary

**Files:**
- Modify: `src/api/schemas/api.py:1-52`
- Test: `tests/test_api/test_e2e_shop.py` (update existing titles)
- Test: `tests/test_api/test_e2e_shop_errors.py` (update existing titles)

**Step 1: Modify the schema**

In `src/api/schemas/api.py`, add the import and change the title fields:

```python
# src/api/schemas/api.py
"""Pydantic schemas for Api entity."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from api_craft.models.types import PascalCaseName


class ApiCreate(BaseModel):
    """Request schema for creating an API.

    :ivar namespace_id: Namespace this API belongs to.
    :ivar title: API title in PascalCase (used as project identifier).
    :ivar version: Semantic version string.
    :ivar description: API description.
    :ivar base_url: Base path for all endpoints.
    :ivar server_url: Full server URL.
    """

    namespace_id: UUID = Field(
        ..., alias="namespaceId", examples=["00000000-0000-0000-0000-000000000002"]
    )
    title: PascalCaseName = Field(..., examples=["UserManagementApi"])
    version: str = Field(..., examples=["1.0.0"])
    description: str | None = Field(
        default="", examples=["API for managing user accounts"]
    )
    base_url: str | None = Field(default="", alias="baseUrl", examples=["/api/v1"])
    server_url: str | None = Field(
        default="", alias="serverUrl", examples=["https://api.example.com"]
    )


class ApiUpdate(BaseModel):
    """Request schema for updating an API.

    :ivar title: Updated API title in PascalCase.
    :ivar version: Updated version string.
    :ivar description: Updated API description.
    :ivar base_url: Updated base path.
    :ivar server_url: Updated server URL.
    """

    title: PascalCaseName | None = Field(
        default=None, examples=["UpdatedApiTitle"]
    )
    version: str | None = Field(default=None, examples=["2.0.0"])
    description: str | None = Field(default=None, examples=["Updated API description"])
    base_url: str | None = Field(default=None, alias="baseUrl", examples=["/api/v2"])
    server_url: str | None = Field(
        default=None, alias="serverUrl", examples=["https://api.example.com"]
    )
```

`ApiResponse.title` stays as `str` — it's output only and the DB stores the validated value.

**Step 2: Update E2E test titles**

In `tests/test_api/test_e2e_shop.py`, line 583:
```python
# Change:
"title": "Shop API",
# To:
"title": "ShopApi",
```

And line 590:
```python
# Change:
assert api["title"] == "Shop API"
# To:
assert api["title"] == "ShopApi"
```

In `tests/test_api/test_e2e_shop_errors.py`, line 222:
```python
# Change:
"title": "Blog API",
# To:
"title": "BlogApi",
```

And line 499:
```python
# Change:
"title": "Phantom API",
# To:
"title": "PhantomApi",
```

**Step 3: Run E2E tests (requires Docker Desktop running)**

Run: `poetry run pytest tests/test_api/ -v`
Expected: ALL PASS (if DB is available), or SKIP (if DB is not running)

**Step 4: Format and commit**

```bash
poetry run black src/api/schemas/api.py tests/test_api/
git add src/api/schemas/api.py tests/test_api/test_e2e_shop.py tests/test_api/test_e2e_shop_errors.py
git commit -m "feat(api): enforce PascalCase on API title in REST schemas

- Change ApiCreate.title and ApiUpdate.title to PascalCaseName type
- Update E2E test API titles to PascalCase (ShopApi, BlogApi, PhantomApi)
- Invalid API titles now return 422 at the API boundary"
```

---

### Task 3: Replace hardcoded type mapping with data-driven python_type

**Files:**
- Modify: `src/api/services/generation.py:174-336`

**Step 1: Write the unit test**

Create `tests/test_api/test_generation_unit.py`:

```python
# tests/test_api/test_generation_unit.py
"""Unit tests for generation service helper functions."""

import pytest

from api.services.generation import _build_field_type, _build_endpoint_name


class TestBuildFieldType:
    """Tests for _build_field_type (replaces _map_field_type)."""

    @pytest.mark.parametrize(
        "python_type,container,expected",
        [
            ("str", None, "str"),
            ("int", None, "int"),
            ("float", None, "float"),
            ("bool", None, "bool"),
            ("datetime.datetime", None, "datetime.datetime"),
            ("datetime.date", None, "datetime.date"),
            ("datetime.time", None, "datetime.time"),
            ("uuid.UUID", None, "uuid.UUID"),
            ("EmailStr", None, "EmailStr"),
            ("HttpUrl", None, "HttpUrl"),
            ("Decimal", None, "Decimal"),
            ("str", "List", "List[str]"),
            ("int", "List", "List[int]"),
            ("datetime.datetime", "List", "List[datetime.datetime]"),
            ("uuid.UUID", "List", "List[uuid.UUID]"),
        ],
    )
    def test_type_mapping(self, python_type: str, container: str | None, expected: str):
        assert _build_field_type(python_type, container) == expected
```

**Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/test_api/test_generation_unit.py -v`
Expected: FAIL — `_build_field_type` does not exist yet

**Step 3: Implement the changes in generation.py**

Replace `_map_field_type` (lines 316-336) with:

```python
def _build_field_type(python_type: str, container: str | None = None) -> str:
    """Build a Python type annotation from the DB python_type and optional container.

    :param python_type: The python_type value from the TypeModel (e.g. 'str', 'datetime.datetime').
    :param container: Optional container type (e.g. 'List').
    :returns: Python type string, e.g. 'str' or 'List[datetime.datetime]'.
    """
    if container:
        return f"{container}[{python_type}]"
    return python_type
```

Update all call sites in `_convert_to_input_api`:

Line 195 — change:
```python
type=_map_field_type(field.field_type.name, field.container),
```
to:
```python
type=_build_field_type(field.field_type.python_type, field.container),
```

Line 240 — change:
```python
field_type = _map_field_type(field.field_type.name) if field else "str"
```
to:
```python
field_type = _build_field_type(field.field_type.python_type) if field else "str"
```

Line 264 — change:
```python
type=_map_field_type(field.field_type.name),
```
to:
```python
type=_build_field_type(field.field_type.python_type),
```

**Step 4: Run test to verify it passes**

Run: `poetry run pytest tests/test_api/test_generation_unit.py -v`
Expected: ALL PASS

**Step 5: Format and commit**

```bash
poetry run black src/api/services/generation.py tests/test_api/test_generation_unit.py
git add src/api/services/generation.py tests/test_api/test_generation_unit.py
git commit -m "feat(generation): replace hardcoded type mapping with data-driven python_type

- Replace _map_field_type() with _build_field_type() using TypeModel.python_type
- All 11 seeded types now correctly map to their Python representations
- UUID fields now generate as uuid.UUID instead of str
- Add unit tests for all type mappings including containers"
```

---

### Task 4: Fix endpoint name derivation and remove _to_pascal_case

**Files:**
- Modify: `src/api/services/generation.py:174-384`
- Test: `tests/test_api/test_generation_unit.py`

**Step 1: Write the failing test**

Add to `tests/test_api/test_generation_unit.py`:

```python
class TestBuildEndpointName:
    """Tests for _build_endpoint_name with path sanitization."""

    @pytest.mark.parametrize(
        "method,path,expected",
        [
            ("GET", "/users", "GetUsers"),
            ("POST", "/users", "PostUsers"),
            ("GET", "/users/{user_id}", "GetUsers"),
            ("DELETE", "/users/{user_id}", "DeleteUsers"),
            ("GET", "/users/{user_id}/orders", "GetUsersOrders"),
            ("GET", "/user-profiles/{profile_id}", "GetUserProfiles"),
            ("GET", "/api/v1/users", "GetApiV1Users"),
            ("PUT", "/order-items/{item_id}/status", "PutOrderItemsStatus"),
            ("GET", "/", "GetRoot"),
            ("GET", "/{id}", "GetRoot"),
        ],
    )
    def test_endpoint_name(self, method: str, path: str, expected: str):
        assert _build_endpoint_name(method, path) == expected
```

**Step 2: Run test to verify failures**

Run: `poetry run pytest tests/test_api/test_generation_unit.py::TestBuildEndpointName -v`
Expected: FAIL for hyphenated paths like `/user-profiles/{profile_id}`

**Step 3: Fix _build_endpoint_name**

Replace `_build_endpoint_name` (lines 362-383) in `src/api/services/generation.py`:

```python
def _build_endpoint_name(method: str, path: str) -> str:
    """Build a PascalCase endpoint name from HTTP method and path.

    Splits path segments on non-alphanumeric characters and capitalizes
    each word to produce valid PascalCase names.

    :param method: HTTP method (GET, POST, etc.).
    :param path: URL path.
    :returns: PascalCase endpoint name.
    """
    import re

    segments = []
    for segment in path.strip("/").split("/"):
        if not segment.startswith("{"):
            # Split segment on non-alphanumeric boundaries
            words = re.split(r"[^a-zA-Z0-9]+", segment)
            segments.extend(w for w in words if w)

    method_prefix = method.lower().capitalize()
    if segments:
        path_part = "".join(word.capitalize() for word in segments)
        return f"{method_prefix}{path_part}"
    return f"{method_prefix}Root"
```

**Step 4: Remove _to_pascal_case and update call sites**

Delete the `_to_pascal_case` function (lines 339-359).

Update `_convert_to_input_api`:

Line 207-208 — change:
```python
        # Ensure object name is PascalCase
        obj_name = _to_pascal_case(obj.name)
```
to:
```python
        obj_name = obj.name
```

Line 211 stays the same (`name=obj_name`).

Lines 274-275 — change:
```python
                request_name = _to_pascal_case(req_obj.name)
```
to:
```python
                request_name = req_obj.name
```

Lines 280-281 — change:
```python
                response_name = _to_pascal_case(resp_obj.name)
```
to:
```python
                response_name = resp_obj.name
```

Lines 298-299 — change:
```python
    # Build API name in PascalCase
    api_name = _to_pascal_case(api.title.replace(" ", ""))
```
to:
```python
    api_name = api.title
```

Line 302 stays the same (`name=api_name`).

**Step 5: Run tests**

Run: `poetry run pytest tests/test_api/test_generation_unit.py -v`
Expected: ALL PASS

Run: `poetry run pytest tests/test_api_craft/ -v`
Expected: ALL PASS

**Step 6: Format and commit**

```bash
poetry run black src/api/services/generation.py tests/test_api/test_generation_unit.py
git add src/api/services/generation.py tests/test_api/test_generation_unit.py
git commit -m "fix(generation): fix endpoint name derivation and remove dead _to_pascal_case

- Sanitize path segments by splitting on non-alnum chars before capitalizing
- Remove _to_pascal_case() — object names and API title are already PascalCase
- Pass obj.name and api.title directly instead of re-converting
- Add unit tests for endpoint name derivation with hyphenated paths"
```

---

### Task 5: Final verification — full test suite

**Files:** None (verification only)

**Step 1: Run all api_craft tests**

Run: `poetry run pytest tests/test_api_craft/ -v`
Expected: ALL PASS

**Step 2: Run all API tests (if DB available)**

Run: `poetry run pytest tests/test_api/ -v`
Expected: ALL PASS or SKIP (if DB is not running)

**Step 3: Run full suite**

Run: `poetry run pytest tests/ -v`
Expected: ALL PASS

**Step 4: Format check**

Run: `poetry run black --check src/ tests/`
Expected: All files formatted correctly
