# Validator Template Catalogues — Backend Design

**Date:** 2026-02-24
**Status:** Approved

## Problem

The frontend currently hardcodes validator templates in JavaScript and generates Python function bodies client-side before sending raw `functionBody` to the backend. The backend stores this raw code as-is. This is fragile, non-deterministic, and gives the frontend code generation responsibilities it shouldn't have.

## Decision

Move validator templates to **backend-registered, database-seeded catalogue resources** (like field constraints and types). The API accepts only `templateId` + parameters/fieldMappings — no raw `functionBody`. Jinja2 rendering of templates into final Python code happens only at generation time (when the user generates the API and spends credits). Frontend performs simple `{{ }}` string substitution for preview display only.

## Design

### Storage Model

Templates are database-seeded rows in the system namespace, following the same pattern as field constraints and types. Two new catalogue tables, two modified junction tables.

### Database Schema

**`field_validator_templates`** (new catalogue table):

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | Fixed UUIDs, range `0003-*` |
| `name` | Text NOT NULL | Display name (e.g. "Strip & Normalize Case") |
| `description` | Text NOT NULL | Template description |
| `compatible_types` | ARRAY(Text) NOT NULL | Type names this applies to (e.g. `["str"]`) |
| `mode` | Text NOT NULL | `"before"` or `"after"` |
| `parameters` | JSONB NOT NULL | Array of `TemplateParameter` objects |
| `body_template` | Text NOT NULL | Jinja2 template for the function body |

**`model_validator_templates`** (new catalogue table):

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | Fixed UUIDs, range `0004-*` |
| `name` | Text NOT NULL | Display name |
| `description` | Text NOT NULL | Template description |
| `mode` | Text NOT NULL | `"before"` or `"after"` |
| `parameters` | JSONB NOT NULL | Array of `TemplateParameter` objects |
| `field_mappings` | JSONB NOT NULL | Array of `FieldMappingDefinition` objects |
| `body_template` | Text NOT NULL | Jinja2 template with `{{ }}` placeholders |

**`applied_field_validators`** (renamed from `field_validators`):

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `field_id` | UUID FK → fields (CASCADE) | |
| `template_id` | UUID FK → field_validator_templates NOT NULL | |
| `parameters` | JSONB nullable | User-configured parameter values |
| `position` | int NOT NULL default 0 | Execution order |

**`applied_model_validators`** (renamed from `model_validators`):

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `object_id` | UUID FK → objects (CASCADE) | |
| `template_id` | UUID FK → model_validator_templates NOT NULL | |
| `parameters` | JSONB nullable | User-configured parameter values |
| `field_mappings` | JSONB NOT NULL | Maps template keys to actual field names |
| `position` | int NOT NULL default 0 | Execution order |

**Renamed existing tables** (columns unchanged):

| Old Name | New Name |
|----------|----------|
| `field_constraint_field_associations` | `applied_constraints` |
| `object_field_associations` | `fields_on_objects` |

### Junction Table Naming Convention

Two conventions based on semantics:
- **`applied_{thing}`** — user attaches a catalogue item to an entity (constraints, validators)
- **`{thing}_on_{entity}`** — structural composition between entities (fields on objects)

### JSONB Structures

**TemplateParameter:**
```json
{
  "key": "case",
  "label": "Case normalization",
  "type": "text | number | select",
  "placeholder": "value hint",
  "options": [{"value": "lower", "label": "lowercase"}],
  "required": true
}
```

`options` is present only when `type` is `"select"`. The `select` type renders as a dropdown on the frontend, and the selected `value` is substituted into `{{ }}` placeholders just like text/number parameters.

**FieldMappingDefinition:**
```json
{
  "key": "password_field",
  "label": "Password field",
  "compatibleTypes": ["str"],
  "required": true
}
```

**SelectOption:**
```json
{"value": "lower", "label": "lowercase"}
```

### API Endpoints

**New read-only catalogue endpoints** (auth required via `ProvisionedUser`):

```
GET /v1/field-validator-templates  → list[FieldValidatorTemplateResponse]
GET /v1/model-validator-templates  → list[ModelValidatorTemplateResponse]
```

**FieldValidatorTemplateResponse:**
```json
{
  "id": "uuid",
  "name": "Strip & Normalize Case",
  "description": "...",
  "compatibleTypes": ["str"],
  "mode": "before",
  "parameters": [{"key": "case", "type": "select", "options": [...], ...}],
  "bodyTemplate": "    v = v.strip().{{case}}()\n    return v"
}
```

**ModelValidatorTemplateResponse:**
```json
{
  "id": "uuid",
  "name": "Password Confirmation",
  "description": "...",
  "mode": "after",
  "parameters": [],
  "fieldMappings": [{"key": "password_field", "label": "Password field", ...}],
  "bodyTemplate": "    if self.{{password_field}} != self.{{confirm_field}}:..."
}
```

### Modified Input Schemas

**FieldValidatorInput** (replaces current):
```json
{
  "templateId": "uuid",
  "parameters": {"case": "lower"}
}
```

Drops `functionName`, `mode`, `functionBody`, `description` — all derived from the template.

**ModelValidatorInput** (replaces current):
```json
{
  "templateId": "uuid",
  "parameters": {},
  "fieldMappings": {"password_field": "password", "confirm_field": "password_confirm"}
}
```

### Modified Response Schemas

**FieldValidatorResponse:**
```json
{
  "id": "uuid",
  "templateId": "uuid",
  "parameters": {"case": "lower"}
}
```

**ModelValidatorResponse:**
```json
{
  "id": "uuid",
  "templateId": "uuid",
  "parameters": {},
  "fieldMappings": {"password_field": "password", "confirm_field": "password_confirm"}
}
```

### Validation Rules (on field/object create/update)

1. `templateId` must exist in the appropriate catalogue table → 404
2. All required parameters must be present → 422
3. No unknown parameter keys → 422
4. For model validators: all required fieldMapping keys must be present → 422
5. No unknown fieldMapping keys → 422

### Code Preview

**Frontend only.** Simple `{{ }}` string replacement in JavaScript:

```javascript
function preview(bodyTemplate, mappings) {
  return bodyTemplate.replace(/\{\{(\w+)\}\}/g, (_, key) => mappings[key] ?? `{{${key}}}`);
}
```

No backend preview endpoint. No rendering during CRUD. The frontend receives `bodyTemplate` from the catalogue endpoint and does client-side substitution for display.

### Generation-Time Resolution

Jinja2 rendering happens only during `generate_fastapi()` — when the user generates the API and spends credits.

**Flow:**
1. Read field/object from DB with applied validators (`template_id`, `parameters`, `field_mappings`)
2. Look up template from catalogue table (`body_template`, `mode`)
3. Render `body_template` with Jinja2, passing `parameters` + `field_mappings` as context
4. Generate `function_name`: `{template_id}_{field.name}` for field validators, `validate_{template_id}` for model validators
5. Pass resolved `function_name` + `function_body` + `mode` to existing Mako templates

Jinja2 rendering is only invoked during the generation flow, never during CRUD.

### Seed Data — Field Validator Templates (9)

| ID | Name | Mode | Types | Parameters |
|---|---|---|---|---|
| `strip_and_normalize` | Strip & Normalize Case | before | `str` | `case` (select: lower/upper/title) |
| `normalize_whitespace` | Normalize Whitespace | before | `str` | none |
| `default_if_empty` | Default If Empty | before | `str` | `default_value` (text, required) |
| `trim_to_length` | Trim To Length | before | `str` | `max_length` (number, required) |
| `sanitize_html` | Strip HTML Tags | before | `str` | none |
| `round_decimal` | Round Decimal | before | `float, Decimal` | `places` (number, required) |
| `slug_format` | Slug Format | after | `str` | none |
| `future_date` | Future Date Only | after | `datetime, date` | none |
| `past_date` | Past Date Only | after | `datetime, date` | none |

### Seed Data — Model Validator Templates (6)

| ID | Name | Mode | Field Mappings | Parameters |
|---|---|---|---|---|
| `password_confirm` | Password Confirmation | after | `password_field` (str), `confirm_field` (str) | none |
| `date_range` | Date Range | after | `start_field` (datetime/date), `end_field` (datetime/date) | `comparison` (select: strict/inclusive) |
| `mutual_exclusivity` | Mutual Exclusivity | after | `field_a` (any), `field_b` (any) | none |
| `conditional_required` | Conditional Required | after | `trigger_field` (any), `required_field` (any) | `condition` (select: equals/not_equals/is_truthy), `trigger_value` (text, required when condition=equals/not_equals) |
| `numeric_comparison` | Numeric Comparison | after | `lesser_field` (int/float), `greater_field` (int/float) | `comparison` (select: strict/inclusive) |
| `at_least_one` | At Least One Required | before | `field_a` (any), `field_b` (any) | none |

### Migration Strategy

**Pre-launch project — clean break.**

Modify initial schema migration (`4141ad7f2255`):
- Add `field_validator_templates` and `model_validator_templates` tables
- Rename `field_validators` → `applied_field_validators`, drop code columns, add template reference columns
- Rename `model_validators` → `applied_model_validators`, drop code columns, add template reference columns
- Rename `field_constraint_field_associations` → `applied_constraints`
- Rename `object_field_associations` → `fields_on_objects`

Extend seed migration (`b1a2c3d4e5f6`):
- Add 9 field validator templates (UUIDs `0003-000000000001` through `0003-000000000009`)
- Add 6 model validator templates (UUIDs `0004-000000000001` through `0004-000000000006`)

Reset local DB after migration edits.

### What Gets Removed

- `FieldValidatorInput.function_name`, `.function_body`, `.mode`, `.description` — replaced by `templateId` + `parameters`
- `ModelValidatorInput.function_name`, `.function_body`, `.mode`, `.description` — replaced by `templateId` + `parameters` + `fieldMappings`
- Raw `functionBody` acceptance in the API — validators are created exclusively by template reference

## Philosophy Alignment

- **Structural, not behavioral:** Templates encode common patterns as configuration. No code authoring.
- **Deterministic:** Same templateId + parameters + fieldMappings always produces the same Python.
- **Templates-only:** No raw functionBody accepted. Guarantees working generated code.
- **Generate structure, leave behavior to post-generation:** If a user's validation doesn't fit a template, they add it after deployment.
- **CRUD is CRUD, generation is generation:** The API stores references. Jinja2 rendering only happens when the user generates and spends credits.
