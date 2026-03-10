# Mutual Exclusivity: Database Generation vs Response Placeholders

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enforce that database generation and response placeholders cannot be enabled simultaneously, and that database generation requires at least one object with a primary key — validated at all three layers (api_craft, api, frontend).

**Architecture:** Add a new `validate_database_config()` validator in `api_craft/models/validators.py` for the mutual exclusivity + PK requirement checks. Wire it into `InputAPI._validate_references()`. Add a Pydantic model validator on `GenerateOptions` for the API layer. Move the existing PK check from `transformers.py` into the new validator (it currently lives in `transform_api()` but belongs in model validation). Provide frontend instructions as a prompt file.

**Tech Stack:** Pydantic v2 model validators, pytest

---

### Task 1: Add `validate_database_config` to validators.py (test-first)

**Files:**
- Test: `tests/test_api_craft/test_input_models.py`
- Modify: `src/api_craft/models/validators.py:172-189`

**Step 1: Write the failing tests**

Add a new test class at the end of `tests/test_api_craft/test_input_models.py`:

```python
class TestDatabaseConfigValidation:
    """Validation rules for database generation configuration."""

    def test_database_with_placeholders_raises(self):
        """Database enabled + response_placeholders=True must raise."""
        with pytest.raises(ValueError, match="Response placeholders cannot be enabled"):
            InputAPI(
                name="TestApi",
                objects=[
                    InputModel(
                        name="Item",
                        fields=[InputField(name="id", type="int", pk=True)],
                    ),
                ],
                endpoints=[
                    InputEndpoint(
                        name="GetItems", path="/items", method="GET", response="Item"
                    ),
                ],
                config=InputApiConfig(
                    response_placeholders=True,
                    database=InputDatabaseConfig(enabled=True),
                ),
            )

    def test_database_without_placeholders_passes(self):
        """Database enabled + response_placeholders=False must succeed."""
        api = InputAPI(
            name="TestApi",
            objects=[
                InputModel(
                    name="Item",
                    fields=[InputField(name="id", type="int", pk=True)],
                ),
            ],
            endpoints=[
                InputEndpoint(
                    name="GetItems", path="/items", method="GET", response="Item"
                ),
            ],
            config=InputApiConfig(
                response_placeholders=False,
                database=InputDatabaseConfig(enabled=True),
            ),
        )
        assert api.config.database.enabled is True

    def test_placeholders_without_database_passes(self):
        """Placeholders enabled without database must succeed."""
        api = InputAPI(
            name="TestApi",
            objects=[
                InputModel(
                    name="Item",
                    fields=[InputField(name="name", type="str")],
                ),
            ],
            endpoints=[
                InputEndpoint(
                    name="GetItems", path="/items", method="GET", response="Item"
                ),
            ],
            config=InputApiConfig(
                response_placeholders=True,
                database=InputDatabaseConfig(enabled=False),
            ),
        )
        assert api.config.response_placeholders is True

    def test_database_without_pk_raises(self):
        """Database enabled with no PK on any object must raise."""
        with pytest.raises(ValueError, match="at least one object with a primary key"):
            InputAPI(
                name="TestApi",
                objects=[
                    InputModel(
                        name="Item",
                        fields=[InputField(name="name", type="str")],
                    ),
                ],
                endpoints=[
                    InputEndpoint(
                        name="GetItems", path="/items", method="GET", response="Item"
                    ),
                ],
                config=InputApiConfig(
                    response_placeholders=False,
                    database=InputDatabaseConfig(enabled=True),
                ),
            )

    def test_database_with_pk_passes(self):
        """Database enabled with a PK on at least one object must succeed."""
        api = InputAPI(
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
                response_placeholders=False,
                database=InputDatabaseConfig(enabled=True),
            ),
        )
        assert api.config.database.enabled is True
```

**Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/test_api_craft/test_input_models.py::TestDatabaseConfigValidation -v`
Expected: `test_database_with_placeholders_raises` and `test_database_without_pk_raises` FAIL (no validation exists yet)

**Step 3: Implement `validate_database_config` in validators.py**

Add after `validate_primary_keys` (after line 189 in `src/api_craft/models/validators.py`):

```python
def validate_database_config(
    config: "InputApiConfig",
    objects: Iterable["InputModel"],
) -> None:
    """Validate database generation configuration constraints.

    :param config: API configuration containing database and placeholder settings.
    :param objects: Collection of declared objects.
    :raises ValueError: If database is enabled with response placeholders,
        or if database is enabled but no object has a primary key.
    """
    if not config.database.enabled:
        return

    if config.response_placeholders:
        raise ValueError(
            "Response placeholders cannot be enabled when database generation is active. "
            "Disable response placeholders or disable database generation."
        )

    has_any_pk = any(
        any(field.pk for field in obj.fields)
        for obj in objects
    )
    if not has_any_pk:
        raise ValueError(
            "Database generation requires at least one object with a primary key field. "
            "Mark a field as PK on your objects, or disable database generation."
        )
```

Update the `TYPE_CHECKING` import block (line 9-10) to also import `InputApiConfig`:

```python
if TYPE_CHECKING:  # pragma: no cover - imports used for type checking only
    from api_craft.models.input import InputApiConfig, InputEndpoint, InputModel
```

**Step 4: Wire into InputAPI model validator**

In `src/api_craft/models/input.py`, add `validate_database_config` to the import (line 11-17):

```python
from api_craft.models.validators import (
    validate_database_config,
    validate_endpoint_references,
    validate_model_field_types,
    validate_path_parameters,
    validate_primary_keys,
    validate_unique_object_names,
)
```

Add the call in `_validate_references` (after line 233):

```python
validate_database_config(self.config, self.objects)
```

**Step 5: Run tests to verify they pass**

Run: `poetry run pytest tests/test_api_craft/test_input_models.py::TestDatabaseConfigValidation -v`
Expected: All 5 tests PASS

**Step 6: Commit**

```
feat(generation): add mutual exclusivity validation for database and placeholders
```

---

### Task 2: Remove duplicate PK check from transformers.py

**Files:**
- Modify: `src/api_craft/transformers.py:344-350`
- Test: `tests/test_api_craft/test_transformers.py:326-370`

The PK check now runs in `InputAPI` model validation (Task 1), so the duplicate in `transform_api()` is unreachable. Remove it.

**Step 1: Remove the PK guard from transform_api()**

In `src/api_craft/transformers.py`, replace lines 344-350:

```python
    if input_api.config.database.enabled:
        orm_models = transform_orm_models(input_api.objects)
        if not orm_models:
            raise ValueError(
                "Database generation requires at least one object with a primary key field. "
                "Mark a field as PK on your objects, or disable database generation."
            )
        snake_name = camel_to_snake(input_api.name)
```

With:

```python
    if input_api.config.database.enabled:
        orm_models = transform_orm_models(input_api.objects)
        snake_name = camel_to_snake(input_api.name)
```

**Step 2: Update transformer tests**

In `tests/test_api_craft/test_transformers.py`, the test `test_database_enabled_without_pk_raises` (line 326) now gets the error from `InputAPI` validation rather than `transform_api()`. Update the test to construct `InputAPI` directly (which will raise):

```python
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
                config=InputApiConfig(database={"enabled": True}, response_placeholders=False),
            )
```

Note: `response_placeholders=False` is needed because the default is `True`, which would now trigger the mutual exclusivity error instead of the PK error.

**Step 3: Update test_database_enabled_with_pk_succeeds**

At line 348, add `response_placeholders=False` to the config:

```python
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
            config=InputApiConfig(database={"enabled": True}, response_placeholders=False),
        )
        result = transform_api(api_input)
        assert result.database_config is not None
        assert len(result.orm_models) == 1
```

**Step 4: Fix any other tests that enable database + default placeholders**

Search for `database.*enabled.*True` or `database_enabled.*True` across all test files. Any test that sets `database.enabled=True` without explicitly setting `response_placeholders=False` will now fail. Fix each by adding `response_placeholders=False`.

Key files to check:
- `tests/test_api_craft/test_transformers.py` — all tests in `TestDatabaseGeneration` class
- `tests/test_api_craft/test_db_codegen.py` — the `db_project` fixture and any inline `InputAPI` construction

Run: `poetry run pytest tests/test_api_craft/ -v`
Expected: All tests PASS

**Step 5: Commit**

```
refactor(generation): move PK validation from transformers to model validators
```

---

### Task 3: Add mutual exclusivity validation to GenerateOptions schema

**Files:**
- Test: `tests/test_api/test_schemas.py` (create if needed, or add to existing test file)
- Modify: `src/api/schemas/api.py:91-109`

**Step 1: Find or create the test file**

Check if `tests/test_api/test_schemas.py` exists. If not, create it. Add tests:

```python
import pytest
from api.schemas.api import GenerateOptions


class TestGenerateOptionsValidation:
    """Validation rules for GenerateOptions schema."""

    def test_database_with_placeholders_raises(self):
        """database_enabled + response_placeholders must raise."""
        with pytest.raises(ValueError, match="Response placeholders cannot be enabled"):
            GenerateOptions(
                database_enabled=True,
                response_placeholders=True,
            )

    def test_database_without_placeholders_passes(self):
        """database_enabled + no placeholders must succeed."""
        opts = GenerateOptions(
            database_enabled=True,
            response_placeholders=False,
        )
        assert opts.database_enabled is True
        assert opts.response_placeholders is False

    def test_placeholders_without_database_passes(self):
        """Placeholders without database must succeed."""
        opts = GenerateOptions(
            database_enabled=False,
            response_placeholders=True,
        )
        assert opts.response_placeholders is True

    def test_default_values_pass(self):
        """Default values (database=False, placeholders=True) must succeed."""
        opts = GenerateOptions()
        assert opts.database_enabled is False
        assert opts.response_placeholders is True
```

**Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/test_api/test_schemas.py::TestGenerateOptionsValidation -v`
Expected: `test_database_with_placeholders_raises` FAILS

**Step 3: Add model validator to GenerateOptions**

In `src/api/schemas/api.py`, add imports at the top:

```python
from typing import Self
from pydantic import BaseModel, ConfigDict, Field, model_validator
```

Add the validator to `GenerateOptions` (after `model_config` at line 109):

```python
    @model_validator(mode="after")
    def _validate_mutual_exclusivity(self) -> Self:
        """Validate that database and response placeholders are not both enabled.

        :returns: The validated options instance.
        :raises ValueError: If both database and response placeholders are enabled.
        """
        if self.database_enabled and self.response_placeholders:
            raise ValueError(
                "Response placeholders cannot be enabled when database generation is active. "
                "Disable response placeholders or disable database generation."
            )
        return self
```

**Step 4: Run tests to verify they pass**

Run: `poetry run pytest tests/test_api/test_schemas.py::TestGenerateOptionsValidation -v`
Expected: All 4 tests PASS

**Step 5: Run full test suite**

Run: `poetry run pytest tests/ -v`
Expected: All tests PASS

**Step 6: Commit**

```
feat(api): add mutual exclusivity validation to GenerateOptions schema
```

---

### Task 4: Write frontend instructions

**Files:**
- Create: `docs/plans/2026-03-10-mutual-exclusivity-frontend.md`

**Step 1: Write the frontend prompt**

Create `docs/plans/2026-03-10-mutual-exclusivity-frontend.md` with instructions for the frontend Claude instance describing the UI behavior changes needed:

- When "Database Enabled" is toggled ON → set `responsePlaceholders` to `false` and disable the checkbox (greyed out with tooltip: "Response placeholders are not available when database generation is enabled")
- When "Database Enabled" is toggled OFF → re-enable the `responsePlaceholders` checkbox (restore to previous value or default `true`)
- The backend now returns a 422 if both `databaseEnabled=true` and `responsePlaceholders=true` are sent together — the frontend should prevent this from being possible via UI, but also handle the 422 gracefully if it occurs

**Step 2: Commit**

```
docs: add frontend instructions for mutual exclusivity UI behavior
```

---

### Task 5: Format and verify

**Step 1: Format code**

Run: `poetry run black src/ tests/`

**Step 2: Run full test suite**

Run: `poetry run pytest tests/ -v`
Expected: All tests PASS

**Step 3: Final commit (if formatting changed anything)**

```
style: format code with black
```
