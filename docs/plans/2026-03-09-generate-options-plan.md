# Generate Options Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `GenerateOptions` request body to `POST /v1/apis/{api_id}/generate` so healthcheck, response_placeholders, and database settings are caller-controlled instead of hardcoded.

**Architecture:** Add a Pydantic schema (`GenerateOptions`) with sensible defaults, accept it as an optional request body on the generate endpoint, thread it through `generate_api_zip` → `_convert_to_input_api` → `InputApiConfig`. All fields default to current behavior, so existing callers (including the frontend) are unaffected.

**Tech Stack:** FastAPI, Pydantic, pytest.

---

### Task 1: Add `GenerateOptions` schema

**Files:**
- Modify: `src/api/schemas/api.py`
- Test: `tests/test_api/test_generation_unit.py`

**Step 1: Write the failing test**

Append to `tests/test_api/test_generation_unit.py`:

```python
from api.schemas.api import GenerateOptions


class TestGenerateOptions:
    def test_defaults(self):
        opts = GenerateOptions()
        assert opts.healthcheck == "/health"
        assert opts.response_placeholders is True
        assert opts.database_enabled is False
        assert opts.database_seed_data is True

    def test_database_enabled(self):
        opts = GenerateOptions(database_enabled=True)
        assert opts.database_enabled is True

    def test_camel_case_alias(self):
        opts = GenerateOptions.model_validate(
            {"responsePlaceholders": False, "databaseEnabled": True}
        )
        assert opts.response_placeholders is False
        assert opts.database_enabled is True

    def test_empty_body_uses_defaults(self):
        opts = GenerateOptions.model_validate({})
        assert opts.healthcheck == "/health"
        assert opts.database_enabled is False
```

**Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/test_api/test_generation_unit.py::TestGenerateOptions -v`
Expected: FAIL — `GenerateOptions` does not exist

**Step 3: Write minimal implementation**

Append to `src/api/schemas/api.py` (after `ApiResponse`):

```python
class GenerateOptions(BaseModel):
    """Options for code generation.

    :ivar healthcheck: Path for the healthcheck endpoint.
    :ivar response_placeholders: Generate placeholder response bodies.
    :ivar database_enabled: Generate database support (SQLAlchemy, Alembic, Docker Compose).
    :ivar database_seed_data: Generate seed data helpers.
    """

    healthcheck: str | None = Field(default="/health")
    response_placeholders: bool = Field(default=True, alias="responsePlaceholders")
    database_enabled: bool = Field(default=False, alias="databaseEnabled")
    database_seed_data: bool = Field(default=True, alias="databaseSeedData")

    model_config = ConfigDict(populate_by_name=True)
```

**Step 4: Run test to verify it passes**

Run: `poetry run pytest tests/test_api/test_generation_unit.py::TestGenerateOptions -v`
Expected: PASS

**Step 5: Run all tests**

Run: `poetry run pytest tests/test_api_craft/ -v`
Expected: All pass

**Step 6: Format and commit**

```bash
poetry run black src/ tests/
git add src/api/schemas/api.py tests/test_api/test_generation_unit.py
git commit -m "feat(api): add GenerateOptions schema for code generation endpoint"
```

---

### Task 2: Wire `GenerateOptions` into the generate endpoint and service

**Files:**
- Modify: `src/api/routers/apis.py:188-246` (generate endpoint)
- Modify: `src/api/services/generation.py:50-85` (`generate_api_zip`)
- Modify: `src/api/services/generation.py:175-316` (`_convert_to_input_api`)
- Test: `tests/test_api/test_generation_unit.py`

**Step 1: Write the failing test**

Append to `tests/test_api/test_generation_unit.py`:

```python
from unittest.mock import MagicMock
from api.services.generation import _convert_to_input_api


class TestConvertToInputApiOptions:
    def _make_api_model(self):
        api = MagicMock()
        api.title = "TestApi"
        api.version = "1.0.0"
        api.description = "Test"
        api.endpoints = []
        return api

    def test_default_options_match_current_behavior(self):
        api = self._make_api_model()
        opts = GenerateOptions()
        result = _convert_to_input_api(api, {}, {}, opts)
        assert result.config.healthcheck == "/health"
        assert result.config.response_placeholders is True
        assert result.config.database.enabled is False

    def test_database_enabled_passed_through(self):
        api = self._make_api_model()
        opts = GenerateOptions(database_enabled=True, database_seed_data=False)
        result = _convert_to_input_api(api, {}, {}, opts)
        assert result.config.database.enabled is True
        assert result.config.database.seed_data is False

    def test_healthcheck_none_passed_through(self):
        api = self._make_api_model()
        opts = GenerateOptions(healthcheck=None)
        result = _convert_to_input_api(api, {}, {}, opts)
        assert result.config.healthcheck is None

    def test_response_placeholders_false_passed_through(self):
        api = self._make_api_model()
        opts = GenerateOptions(response_placeholders=False)
        result = _convert_to_input_api(api, {}, {}, opts)
        assert result.config.response_placeholders is False
```

**Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/test_api/test_generation_unit.py::TestConvertToInputApiOptions -v`
Expected: FAIL — `_convert_to_input_api` does not accept `options` parameter

**Step 3: Write minimal implementation**

In `src/api/services/generation.py`, modify `_convert_to_input_api` signature (line 175) to accept options:

```python
from api.schemas.api import GenerateOptions

def _convert_to_input_api(
    api: ApiModel,
    objects_map: dict[str, ObjectDefinition],
    fields_map: dict[str, FieldModel],
    options: GenerateOptions,
) -> InputAPI:
```

Replace the hardcoded `InputApiConfig` block (lines 312-315) with:

```python
        config=InputApiConfig(
            healthcheck=options.healthcheck,
            response_placeholders=options.response_placeholders,
            database={"enabled": options.database_enabled, "seed_data": options.database_seed_data},
        ),
```

Modify `generate_api_zip` signature (line 50) to accept and pass through options:

```python
async def generate_api_zip(api: ApiModel, db: AsyncSession, options: GenerateOptions) -> io.BytesIO:
```

Update the call to `_convert_to_input_api` inside `generate_api_zip` (line 62):

```python
    input_api = _convert_to_input_api(api, objects_map, fields_map, options)
```

In `src/api/routers/apis.py`, add the import and parameter:

```python
from api.schemas.api import ApiCreate, ApiResponse, ApiUpdate, GenerateOptions
```

Add `options` parameter to the endpoint function signature (after `db`):

```python
async def generate_api_code(
    request: Request,
    api_id: str,
    user: ProvisionedUser,
    db: DbSession,
    options: GenerateOptions = GenerateOptions(),
) -> StreamingResponse:
```

Update the call (line 234):

```python
    zip_buffer = await generate_api_zip(api, db, options)
```

**Step 4: Run test to verify it passes**

Run: `poetry run pytest tests/test_api/test_generation_unit.py -v`
Expected: PASS

**Step 5: Run all tests**

Run: `poetry run pytest tests/test_api_craft/ -v`
Expected: All pass

**Step 6: Format and commit**

```bash
poetry run black src/ tests/
git add src/api/routers/apis.py src/api/services/generation.py tests/test_api/test_generation_unit.py
git commit -m "feat(api): wire GenerateOptions into generate endpoint and service"
```

---

### Task 3: Verify full stack and clean up

**Step 1: Run all api_craft tests**

Run: `poetry run pytest tests/test_api_craft/ -v`
Expected: All pass (263 tests)

**Step 2: Run generation unit tests**

Run: `poetry run pytest tests/test_api/test_generation_unit.py -v`
Expected: All pass

**Step 3: Format code**

Run: `poetry run black src/ tests/`

**Step 4: Verify the endpoint shows up in OpenAPI**

Run: `PYTHONPATH=src poetry run python -c "from api.main import app; import json; schema = app.openapi(); ep = schema['paths']['/v1/apis/{api_id}/generate']['post']; body = ep.get('requestBody', {}); print(json.dumps(body, indent=2))"`

Expected: Shows `GenerateOptions` schema with `healthcheck`, `responsePlaceholders`, `databaseEnabled`, `databaseSeedData` fields.

**Step 5: Commit if any final changes**

```bash
poetry run black src/ tests/
git add -A
git commit -m "chore(api): final cleanup for generate options"
```
