# Case Enforcement for Names

## Problem

Field names, query param names, and path param names have no case enforcement. Users can send any case through the API, and invalid casing could produce broken generated code. Object names and API names enforce PascalCase via the `Name` type, but it has a generic name that doesn't communicate its purpose.

## Decision

Enforce strict case rules at both the REST API boundary and the code generation input layer. Reject invalid casing early with clear error messages. The frontend prettifies stored names for display (e.g., `user_email` → "User Email").

## Design

### Two Custom Types

**`PascalCaseName`** (renamed from `Name` in `api_craft/models/types.py`):
- Validation: starts with uppercase, only letters + digits, no consecutive uppercase (unchanged rules)
- Properties: `.snake_name`, `.camel_name`, `.kebab_name` (unchanged)
- Added: `.pascal_name` (returns `self`, for symmetry)

**`SnakeCaseName`** (new in `api_craft/models/types.py`):
- Validation regex: `^[a-z][a-z0-9]*(_[a-z0-9]+)*$`
- Valid: `email`, `user_email`, `created_at`, `field2`
- Invalid: `Email`, `user__email`, `_email`, `user-email`, `userEmail`
- Properties: `.camel_name` → `userEmail`, `.pascal_name` → `UserEmail`, `.kebab_name` → `user-email`

### Type Assignments

| Layer | Field | Before | After |
|-------|-------|--------|-------|
| api_craft | `InputAPI.name` | `Name` | `PascalCaseName` |
| api_craft | `InputModel.name` | `Name` | `PascalCaseName` |
| api_craft | `InputEndpoint.name` | `Name` | `PascalCaseName` |
| api_craft | `InputField.name` | `str` | `SnakeCaseName` |
| api_craft | `InputQueryParam.name` | `str` | `SnakeCaseName` |
| api_craft | `InputPathParam.name` | `str` | `SnakeCaseName` |
| API schema | `ObjectCreate.name` | `str` | `PascalCaseName` |
| API schema | `ObjectUpdate.name` | `str` | `PascalCaseName` |
| API schema | `FieldCreate.name` | `str` | `SnakeCaseName` |
| API schema | `FieldUpdate.name` | `str` | `SnakeCaseName` |
| API schema | `PathParamSchema.name` | `str` | `SnakeCaseName` |

### Not Changed

- `ApiCreate.title` — human-readable string, not a code identifier
- `InputTag.name` / `TemplateTag.name` — display strings for OpenAPI grouping
- `TemplateField.name` — stays `str`, templates receive already-validated data

### Validators

In `api_craft/models/validators.py`:
- `validate_pascal_case_name()` — unchanged
- `validate_snake_case_name()` — new, raises `ValueError` with message: `"SnakeCaseName must be lowercase letters, digits, and underscores, got: {value}"`

### Transformer Impact

`transform_field`, `transform_query_params`, `transform_path_params` can use `.camel_name` from `SnakeCaseName` instead of calling `snake_to_camel()` utility. This is optional cleanup — the existing approach also works since the type is a `str` subclass.

### Test Plan

- Update existing `Name` type tests → `PascalCaseName`
- Add `SnakeCaseName` validation tests (valid, invalid, properties)
- Update test data in `InputField`, `InputQueryParam`, `InputPathParam` tests to use valid snake_case
- Update API schema tests (`FieldCreate`, `ObjectCreate`, `PathParamSchema`) to use valid case
- Add new tests: 422 response when sending wrong case to REST endpoints
- Update E2E tests if test data uses non-compliant names

### Frontend Impact

- Must send `snake_case` for field names and `PascalCase` for object names
- Can display prettified names in UI (`user_email` → "User Email", `UserAccount` → "User Account")
- Will receive 422 errors if sending wrong case — coordinated frontend update needed

### No Database Migration

Names are stored as text. Validation is enforced on write only. Existing data assumed to be correct case.
