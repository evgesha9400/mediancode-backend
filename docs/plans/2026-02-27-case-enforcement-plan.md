# Case Enforcement Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enforce strict PascalCase and snake_case naming rules via two symmetric custom types, applied at both the REST API boundary and the code generation input layer.

**Architecture:** Rename `Name` → `PascalCaseName`, add `SnakeCaseName` — both in `api_craft/models/types.py`. Both are `str` subclasses with validation in `__new__` and derived case-variant properties. Apply them to input models and API schemas.

**Tech Stack:** Python 3.13, Pydantic v2, FastAPI, pytest

**Design doc:** `docs/plans/2026-02-27-case-enforcement-design.md`

---

### Task 1: Add `validate_snake_case_name` validator

**Files:**
- Modify: `src/api_craft/models/validators.py`
- Create: `tests/test_api_craft/test_name_types.py`

**Step 1: Create test file with failing tests for the new validator**

```python
# tests/test_api_craft/test_name_types.py
"""Tests for PascalCaseName and SnakeCaseName types."""

import pytest

from api_craft.models.validators import validate_snake_case_name


class TestValidateSnakeCaseName:
    """Tests for validate_snake_case_name."""

    @pytest.mark.parametrize(
        "value",
        ["email", "user_email", "created_at", "field2", "a", "x1_y2_z3"],
    )
    def test_valid_snake_case(self, value: str):
        validate_snake_case_name(value)  # should not raise

    @pytest.mark.parametrize(
        "value,reason",
        [
            ("", "empty string"),
            ("Email", "starts with uppercase"),
            ("userEmail", "camelCase"),
            ("UserEmail", "PascalCase"),
            ("user__email", "double underscore"),
            ("_email", "leading underscore"),
            ("email_", "trailing underscore"),
            ("user-email", "contains hyphen"),
            ("user email", "contains space"),
            ("123field", "starts with digit"),
            ("user_Email", "uppercase after underscore"),
        ],
    )
    def test_invalid_snake_case(self, value: str, reason: str):
        with pytest.raises(ValueError):
            validate_snake_case_name(value)
```

**Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/test_api_craft/test_name_types.py::TestValidateSnakeCaseName -v`
Expected: FAIL — `ImportError: cannot import name 'validate_snake_case_name'`

**Step 3: Implement `validate_snake_case_name` in validators.py**

Add to `src/api_craft/models/validators.py`:

```python
SNAKE_CASE_PATTERN = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")


def validate_snake_case_name(value: str) -> None:
    """Validate that ``value`` is a snake_case identifier.

    :param value: Candidate identifier to validate.
    :raises ValueError: If ``value`` is empty or not valid snake_case.
    """
    if not value:
        raise ValueError("SnakeCaseName cannot be empty")

    if not SNAKE_CASE_PATTERN.match(value):
        raise ValueError(
            f"SnakeCaseName must be lowercase letters, digits, and single underscores, got: {value}"
        )
```

**Step 4: Run test to verify it passes**

Run: `poetry run pytest tests/test_api_craft/test_name_types.py::TestValidateSnakeCaseName -v`
Expected: All PASS

**Step 5: Format and commit**

```bash
poetry run black src/api_craft/models/validators.py tests/test_api_craft/test_name_types.py
git add src/api_craft/models/validators.py tests/test_api_craft/test_name_types.py
git commit -m "feat(models): add validate_snake_case_name validator

- Add SNAKE_CASE_PATTERN regex for strict snake_case validation
- Add validate_snake_case_name() alongside existing validate_pascal_case_name()
- Add comprehensive tests for valid and invalid snake_case names"
```

---

### Task 2: Create `SnakeCaseName` type

**Files:**
- Modify: `src/api_craft/models/types.py`
- Modify: `tests/test_api_craft/test_name_types.py`

**Step 1: Add failing tests for the SnakeCaseName type**

Append to `tests/test_api_craft/test_name_types.py`:

```python
from api_craft.models.types import SnakeCaseName


class TestSnakeCaseName:
    """Tests for SnakeCaseName type."""

    def test_valid_creation(self):
        name = SnakeCaseName("user_email")
        assert name == "user_email"

    def test_single_word(self):
        name = SnakeCaseName("email")
        assert name == "email"

    def test_camel_name_single_word(self):
        name = SnakeCaseName("email")
        assert name.camel_name == "Email"

    def test_camel_name_multi_word(self):
        name = SnakeCaseName("user_email")
        assert name.camel_name == "UserEmail"

    def test_pascal_name(self):
        name = SnakeCaseName("user_email")
        assert name.pascal_name == "UserEmail"

    def test_kebab_name(self):
        name = SnakeCaseName("user_email")
        assert name.kebab_name == "user-email"

    def test_kebab_name_single_word(self):
        name = SnakeCaseName("email")
        assert name.kebab_name == "email"

    def test_rejects_camel_case(self):
        with pytest.raises(ValueError):
            SnakeCaseName("userEmail")

    def test_rejects_pascal_case(self):
        with pytest.raises(ValueError):
            SnakeCaseName("UserEmail")

    def test_rejects_empty(self):
        with pytest.raises(ValueError):
            SnakeCaseName("")

    def test_is_str_subclass(self):
        name = SnakeCaseName("email")
        assert isinstance(name, str)
```

**Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/test_api_craft/test_name_types.py::TestSnakeCaseName -v`
Expected: FAIL — `ImportError: cannot import name 'SnakeCaseName'`

**Step 3: Implement `SnakeCaseName` in types.py**

Add to `src/api_craft/models/types.py`, below the existing `Name` class:

```python
from api_craft.models.validators import validate_snake_case_name


class SnakeCaseName(str):
    """A string that must be in snake_case and provides derived naming variants.

    This type validates that the input is a valid snake_case identifier and
    automatically provides camelCase, PascalCase, and kebab-case variants.
    """

    def __new__(cls, value: str) -> "SnakeCaseName":
        validate_snake_case_name(value)
        return super().__new__(cls, value)

    @property
    def camel_name(self) -> str:
        """Return the camelCase version of the name.

        Note: For snake_case, camelCase capitalizes each segment, producing
        PascalCase. This matches the existing snake_to_camel utility behavior.
        """
        return "".join(segment.capitalize() for segment in self.split("_"))

    @property
    def pascal_name(self) -> str:
        """Return the PascalCase version of the name."""
        return "".join(segment.capitalize() for segment in self.split("_"))

    @property
    def kebab_name(self) -> str:
        """Return the kebab-case version of the name."""
        return self.replace("_", "-")

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: type, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls,
            core_schema.str_schema(),
            serialization=core_schema.to_string_ser_schema(),
        )
```

**Step 4: Run test to verify it passes**

Run: `poetry run pytest tests/test_api_craft/test_name_types.py::TestSnakeCaseName -v`
Expected: All PASS

**Step 5: Format and commit**

```bash
poetry run black src/api_craft/models/types.py tests/test_api_craft/test_name_types.py
git add src/api_craft/models/types.py tests/test_api_craft/test_name_types.py
git commit -m "feat(models): add SnakeCaseName type with derived case variants

- SnakeCaseName validates strict snake_case and provides .camel_name, .pascal_name, .kebab_name
- Pydantic core schema support for use in BaseModel fields
- Comprehensive tests for creation, validation, and all property variants"
```

---

### Task 3: Rename `Name` → `PascalCaseName`

**Files:**
- Modify: `src/api_craft/models/types.py` (rename class)
- Modify: `src/api_craft/models/input.py` (update import)
- Modify: `tests/test_api_craft/test_name_types.py` (add regression tests)

**Step 1: Add regression tests for PascalCaseName**

Append to `tests/test_api_craft/test_name_types.py`:

```python
from api_craft.models.types import PascalCaseName


class TestPascalCaseName:
    """Regression tests for PascalCaseName (renamed from Name)."""

    def test_valid_creation(self):
        name = PascalCaseName("UserEmail")
        assert name == "UserEmail"

    def test_snake_name(self):
        name = PascalCaseName("UserEmail")
        assert name.snake_name == "user_email"

    def test_camel_name(self):
        name = PascalCaseName("UserEmail")
        assert name.camel_name == "userEmail"

    def test_kebab_name(self):
        name = PascalCaseName("UserEmail")
        assert name.kebab_name == "user-email"

    def test_pascal_name_returns_self(self):
        name = PascalCaseName("UserEmail")
        assert name.pascal_name == "UserEmail"

    def test_rejects_snake_case(self):
        with pytest.raises(ValueError):
            PascalCaseName("user_email")

    def test_rejects_lowercase_start(self):
        with pytest.raises(ValueError):
            PascalCaseName("userEmail")

    def test_is_str_subclass(self):
        name = PascalCaseName("User")
        assert isinstance(name, str)
```

**Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/test_api_craft/test_name_types.py::TestPascalCaseName -v`
Expected: FAIL — `ImportError: cannot import name 'PascalCaseName'`

**Step 3: Rename `Name` → `PascalCaseName` in types.py and add `.pascal_name` property**

In `src/api_craft/models/types.py`, rename the class:

```python
class PascalCaseName(str):
    """A string that must be in PascalCase and provides derived naming variants.
    ...
    """

    def __new__(cls, value: str) -> "PascalCaseName":
        ...

    @property
    def pascal_name(self) -> str:
        """Return self (already PascalCase), for symmetry with SnakeCaseName."""
        return str(self)

    # ... existing snake_name, camel_name, kebab_name unchanged ...
```

**Step 4: Update the import in `src/api_craft/models/input.py`**

Change:
```python
from api_craft.models.types import Name
```
To:
```python
from api_craft.models.types import PascalCaseName
```

And update all three usages of `Name` in `input.py`:
- `InputModel.name: Name` → `InputModel.name: PascalCaseName`
- `InputEndpoint.name: Name` → `InputEndpoint.name: PascalCaseName`
- `InputAPI.name: Name` → `InputAPI.name: PascalCaseName`

**Step 5: Run tests to verify everything passes**

Run: `poetry run pytest tests/test_api_craft/ -v`
Expected: All PASS (including existing codegen tests — they use PascalCase names in the YAML spec)

**Step 6: Format and commit**

```bash
poetry run black src/api_craft/models/types.py src/api_craft/models/input.py tests/test_api_craft/test_name_types.py
git add src/api_craft/models/types.py src/api_craft/models/input.py tests/test_api_craft/test_name_types.py
git commit -m "refactor(models): rename Name to PascalCaseName

- Rename Name → PascalCaseName for explicit intent
- Add .pascal_name property for symmetry with SnakeCaseName
- Update import in input.py (only consumer)
- Add regression tests for PascalCaseName"
```

---

### Task 4: Apply `SnakeCaseName` to api_craft input models

**Files:**
- Modify: `src/api_craft/models/input.py`
- Modify: `tests/test_api_craft/test_name_types.py`

**Step 1: Add integration test verifying InputField rejects bad case**

Append to `tests/test_api_craft/test_name_types.py`:

```python
from api_craft.models.input import InputField, InputQueryParam, InputPathParam


class TestInputModelCaseEnforcement:
    """Tests that api_craft input models enforce case rules."""

    def test_input_field_accepts_snake_case(self):
        field = InputField(type="str", name="user_email")
        assert field.name == "user_email"

    def test_input_field_rejects_camel_case(self):
        with pytest.raises(ValueError):
            InputField(type="str", name="userEmail")

    def test_input_field_rejects_pascal_case(self):
        with pytest.raises(ValueError):
            InputField(type="str", name="UserEmail")

    def test_input_query_param_accepts_snake_case(self):
        param = InputQueryParam(name="page_size", type="int")
        assert param.name == "page_size"

    def test_input_query_param_rejects_camel_case(self):
        with pytest.raises(ValueError):
            InputQueryParam(name="pageSize", type="int")

    def test_input_path_param_accepts_snake_case(self):
        param = InputPathParam(name="item_id", type="int")
        assert param.name == "item_id"

    def test_input_path_param_rejects_camel_case(self):
        with pytest.raises(ValueError):
            InputPathParam(name="itemId", type="int")
```

**Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/test_api_craft/test_name_types.py::TestInputModelCaseEnforcement -v`
Expected: FAIL — tests expecting rejection will pass (they currently accept any string)

**Step 3: Update `src/api_craft/models/input.py`**

Update the import:
```python
from api_craft.models.types import PascalCaseName, SnakeCaseName
```

Change field types:
- `InputField.name: str` → `InputField.name: SnakeCaseName`
- `InputQueryParam.name: str` → `InputQueryParam.name: SnakeCaseName`
- `InputPathParam.name: str` → `InputPathParam.name: SnakeCaseName`

**Step 4: Run all api_craft tests**

Run: `poetry run pytest tests/test_api_craft/ -v`
Expected: All PASS (the YAML spec already uses valid snake_case field names)

**Step 5: Format and commit**

```bash
poetry run black src/api_craft/models/input.py tests/test_api_craft/test_name_types.py
git add src/api_craft/models/input.py tests/test_api_craft/test_name_types.py
git commit -m "feat(models): enforce snake_case for field and param names in api_craft

- InputField.name now requires SnakeCaseName
- InputQueryParam.name now requires SnakeCaseName
- InputPathParam.name now requires SnakeCaseName
- Add integration tests verifying rejection of camelCase/PascalCase"
```

---

### Task 5: Apply types to REST API schemas

**Files:**
- Modify: `src/api/schemas/field.py`
- Modify: `src/api/schemas/object.py`
- Modify: `src/api/schemas/endpoint.py`

**Step 1: Update `src/api/schemas/object.py`**

Add import and change types:
```python
from api_craft.models.types import PascalCaseName
```

- `ObjectCreate.name: str` → `ObjectCreate.name: PascalCaseName`
- `ObjectUpdate.name: str | None` → `ObjectUpdate.name: PascalCaseName | None`

**Step 2: Update `src/api/schemas/field.py`**

Add import and change types:
```python
from api_craft.models.types import SnakeCaseName
```

- `FieldCreate.name: str` → `FieldCreate.name: SnakeCaseName`
- `FieldUpdate.name: str | None` → `FieldUpdate.name: SnakeCaseName | None`

Update examples to use valid snake_case:
- `FieldCreate.name` examples: `["email"]` (already valid)
- `FieldUpdate.name` examples: `["updated_field_name"]` (already valid)

**Step 3: Update `src/api/schemas/endpoint.py`**

Add import and change type:
```python
from api_craft.models.types import SnakeCaseName
```

- `PathParamSchema.name: str` → `PathParamSchema.name: SnakeCaseName`

Example `["user_id"]` is already valid snake_case.

**Step 4: Run all tests**

Run: `poetry run pytest tests/ -v`
Expected: All PASS. E2E tests already use compliant names.

**Step 5: Format and commit**

```bash
poetry run black src/api/schemas/field.py src/api/schemas/object.py src/api/schemas/endpoint.py
git add src/api/schemas/field.py src/api/schemas/object.py src/api/schemas/endpoint.py
git commit -m "feat(api): enforce case rules in REST API schemas

- ObjectCreate/ObjectUpdate.name now requires PascalCaseName
- FieldCreate/FieldUpdate.name now requires SnakeCaseName
- PathParamSchema.name now requires SnakeCaseName
- Invalid case names return 422 at the API boundary"
```

---

### Task 6: Run full test suite and verify

**Files:** None (verification only)

**Step 1: Run full test suite**

Run: `poetry run pytest tests/ -v`
Expected: All PASS

**Step 2: Run black formatting check**

Run: `poetry run black --check src/ tests/`
Expected: All files formatted correctly

**Step 3: Verify manually with a quick smoke test**

Run: `python -c "from api_craft.models.types import PascalCaseName, SnakeCaseName; print(SnakeCaseName('user_email').pascal_name, PascalCaseName('UserEmail').snake_name)"`
Expected: `UserEmail user_email`
