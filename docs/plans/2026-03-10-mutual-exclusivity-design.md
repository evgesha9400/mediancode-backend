# Design: Mutual Exclusivity — Database Generation vs Response Placeholders

**Date:** 2026-03-10

## Rules

1. **Database + Placeholders are mutually exclusive:** When `database.enabled=True`, `response_placeholders` must be `False`. Error if both are `True`.
2. **Database requires at least one PK:** When `database.enabled=True`, at least one object must have a field with `pk=True`. Error otherwise.

## Enforcement Layers

### Layer 1 — `api_craft` (validators.py + InputAPI)

New validator function `validate_database_config(config, objects)` in `validators.py`:

- If `config.database.enabled` and `config.response_placeholders` → raise `ValueError("Response placeholders cannot be enabled when database generation is active")`
- If `config.database.enabled` and no object has any field with `pk=True` → raise `ValueError("Database generation requires at least one object with a primary key field")`

Called from `InputAPI._validate_references()` alongside existing validators.

### Layer 2 — `api` (GenerateOptions schema)

Pydantic `@model_validator(mode="after")` on `GenerateOptions` in `src/api/schemas/api.py`:

- If `database_enabled` and `response_placeholders` → raise `ValueError` with same message
- PK check cannot happen here (no access to objects), so only the mutual exclusivity check lives at this layer

### Layer 3 — Frontend

Instructions for the frontend Claude instance:

- When "Seed Data" (database) is toggled on → auto-uncheck "Response Placeholders" and disable the checkbox
- When "Response Placeholders" is toggled on → auto-uncheck "Seed Data" and disable database seed checkbox
- Visual indication that these are mutually exclusive (tooltip or note)

## Tests

- `test_database_enabled_with_placeholders_raises` — both on → error
- `test_database_enabled_without_pk_raises` — database on, no PK → error
- `test_database_enabled_with_pk_passes` — database on, PK present → ok
- `test_placeholders_without_database_passes` — placeholders on, no DB → ok
- `test_generate_options_mutual_exclusivity` — API schema validation
