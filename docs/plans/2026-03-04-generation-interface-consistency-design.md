# Generation Pipeline Interface Consistency Design

**Date:** 2026-03-04
**Scope:** Fix interface mismatches between `src/api/services/generation.py` and `src/api_craft/models/input.py`

## Problem

The generation service (`generation.py`) bridges DB models to `api_craft`'s `InputAPI` format, but several mappings are broken or lossy:

1. `_to_pascal_case()` uses `str.capitalize()` which mangles multi-word PascalCase names: `"CreateItemRequest"` → `"Createitemrequest"`
2. API name construction collapses spaces before splitting: `"User Management API"` → `"Usermanagementapi"`
3. Type mapping is hardcoded and missing 3 of 11 seeded types (Decimal, date, time fall back to `"str"`)
4. `SUPPORTED_TYPE_IDENTIFIERS` in api_craft validators is too restrictive for the types the DB can produce
5. `_build_endpoint_name()` doesn't sanitize hyphens in path segments, producing invalid PascalCase names
6. UUID type maps to `"str"`, losing format validation

## Decisions

- **API title**: Enforce `PascalCaseName` on `ApiCreate.title` / `ApiUpdate.title` at the REST boundary. No conversion needed in generation.
- **Type mapping**: Use `field.field_type.python_type` from DB instead of hardcoded dict. Data-driven, automatically handles all types.
- **Object names**: Pass through directly — already PascalCase from REST enforcement.
- **Endpoint names**: Fix derivation to sanitize non-alnum chars in path segments.
- **UUID**: Map to `uuid.UUID` (via python_type from DB) instead of `"str"`.

## Changes

### 1. Enforce PascalCase on API Title

**File:** `src/api/schemas/api.py`

- Change `ApiCreate.title: str` → `title: PascalCaseName`
- Change `ApiUpdate.title: str | None` → `title: PascalCaseName | None`
- Import `PascalCaseName` from `api_craft.models.types`

### 2. Data-Driven Type Mapping

**File:** `src/api/services/generation.py`

- Remove `_map_field_type()` hardcoded dict
- Replace with direct use of `field.field_type.python_type` and `field.container`
- Update call sites to pass the field model instead of just the type name string

**File:** `src/api_craft/models/validators.py`

- Expand `SUPPORTED_TYPE_IDENTIFIERS` to include: `EmailStr`, `HttpUrl`, `Decimal`, `date`, `time`, `uuid`, `UUID`

### 3. Object Name Pass-Through

**File:** `src/api/services/generation.py`

- Remove `_to_pascal_case(obj.name)` calls (lines ~208, 275, 281)
- Pass `obj.name` directly — already validated PascalCase

### 4. Endpoint Name Sanitization

**File:** `src/api/services/generation.py`

- Fix `_build_endpoint_name()` to split path segments on non-alphanumeric chars
- Each word gets capitalized independently
- Example: `/user-profiles/{id}` → segments split to `["user", "profiles"]` → `"GetUserProfiles"`

### 5. API Name Pass-Through + Dead Code Removal

**File:** `src/api/services/generation.py`

- Replace `_to_pascal_case(api.title.replace(" ", ""))` with `api.title` directly
- Remove the `_to_pascal_case()` function entirely

### 6. Test Updates

- Update E2E tests if API titles need to be PascalCase
- Add test cases for multi-word object names and hyphenated paths
