# Validator Template Catalogues — Backend Design Prompt

I need to brainstorm and design an implementation plan for backend support of validator template catalogues. This is a cross-cutting change where the frontend is being redesigned to show validator templates as reference catalogues (like field constraints) instead of showing attached validator instances. Here's the approved frontend design that defines the contract the backend needs to fulfill.

## Context

The frontend currently hardcodes validator templates in JavaScript and generates Python function bodies client-side before sending raw `functionBody` to the backend. We're moving to a model where:

1. Templates are **backend-registered resources** (like field constraints — seeded, read-only)
2. The API **only accepts `templateId` + parameters/fieldMappings** — no raw `functionBody`
3. The **backend generates the Python code** from templates at save time

## Philosophy (from `docs/PHILOSOPHY.md`)

- **Generate structure, leave behavior to post-generation.** Templates encode common validation patterns as configuration. If a user's validation doesn't fit a template, they add it after deployment.
- **Deterministic:** Same inputs always produce the same code.
- **Templates are the sweet spot** between configuration and code authoring — no code editors, no raw code input.

## Required Backend Resources

### Two new read-only endpoints:

```
GET /v1/field-validator-templates    → FieldValidatorTemplate[]
GET /v1/model-validator-templates    → ModelValidatorTemplate[]
```

### Field Validator Template shape:

```json
{
  "id": "strip_lowercase",
  "name": "Strip & Lowercase",
  "description": "Strips whitespace and converts to lowercase",
  "compatibleTypes": ["str"],
  "mode": "before",
  "parameters": [],
  "bodyTemplate": "    if isinstance(v, str):\n        v = v.strip().lower()\n    return v"
}
```

### Model Validator Template shape:

```json
{
  "id": "password_confirm",
  "name": "Password Confirmation",
  "description": "Ensures password and confirmation fields match",
  "mode": "after",
  "parameters": [],
  "fieldMappings": [
    { "key": "password_field", "label": "Password field", "compatibleTypes": ["str"], "required": true },
    { "key": "confirm_field", "label": "Confirmation field", "compatibleTypes": ["str"], "required": true }
  ],
  "bodyTemplate": "    if self.{{password_field}} != self.{{confirm_field}}:\n        raise ValueError(\"Password and confirmation do not match\")\n    return self"
}
```

### TemplateParameter (shared):

```json
{ "key": "pattern", "label": "Regex Pattern", "type": "text", "placeholder": "^[a-z]+$", "required": true }
```

Field mappings use `{{placeholder}}` syntax in `bodyTemplate`. Parameters also use `{{placeholder}}` syntax (e.g., a regex template's body contains `{{pattern}}`).

## API Contract Change — Attaching Validators

### Current contract (to be replaced):

```json
// In field/object create/update requests:
"validators": [{ "functionName": "...", "mode": "before", "functionBody": "...", "description": "..." }]
```

### New contract — field validators (on field create/update):

```json
"validators": [{ "templateId": "strip_lowercase", "parameters": {} }]
```

### New contract — model validators (on object create/update):

```json
"validators": [{ "templateId": "password_confirm", "parameters": {}, "fieldMappings": { "password_field": "password", "confirm_field": "password_confirm" } }]
```

Note: field validators and model validators have **separate payload shapes**. Field validators have no `fieldMappings` (they operate on `v`, the single field value). Model validators require `fieldMappings` (they reference multiple fields on the object by name).

### Backend response (on GET fields/objects) must include `templateId` for traceability:

```json
"validators": [{
  "id": "uuid",
  "templateId": "strip_lowercase",
  "functionName": "strip_lowercase_email",
  "mode": "before",
  "functionBody": "    if isinstance(v, str):\n        v = v.strip().lower()\n    return v",
  "description": "Strips whitespace and converts to lowercase"
}]
```

## Code Generation Responsibility

The backend is responsible for:
1. Resolving `templateId` to a template
2. Substituting `{{placeholder}}` values from `parameters` and `fieldMappings` into `bodyTemplate`
3. Generating `functionName` (field validators incorporate the parent field name, e.g., `strip_lowercase_email`; model validators use a fixed name from the template, e.g., `validate_password_confirmation`)
4. Storing the resolved `functionBody` alongside the `templateId`
5. Rejecting requests with unknown `templateId` or missing required parameters/fieldMappings

## Existing Templates to Seed

### Field Validator Templates (11):

| ID | Name | Compatible Types | Mode | Parameters |
|---|---|---|---|---|
| `strip_lowercase` | Strip & Lowercase | `str` | before | none |
| `email_format` | Email Format | `str` | after | none |
| `url_format` | URL Format | `str` | after | none |
| `slug_format` | Slug Format | `str` | after | none |
| `regex_match` | Regex Match | `str` | after | `pattern` (text, required) |
| `string_length` | String Length Check | `str` | after | `min` (number), `max` (number) |
| `number_range` | Number Range | `int, float` | after | `min` (number), `max` (number) |
| `must_be_positive` | Must Be Positive | `int, float` | after | none |
| `future_date` | Future Date Only | `datetime` | after | none |
| `not_empty` | Not Empty / Whitespace | `str` | after | none |

### Model Validator Templates (6):

| ID | Name | Mode | Field Mappings | Parameters |
|---|---|---|---|---|
| `password_confirm` | Password Confirmation | after | `password_field` (str), `confirm_field` (str) | none |
| `date_range` | Date Range | after | `start_field` (datetime), `end_field` (datetime) | none |
| `mutual_exclusivity` | Mutual Exclusivity | after | `field_a` (any), `field_b` (any) | none |
| `conditional_required` | Conditional Required | after | `trigger_field` (any), `required_field` (any) | `trigger_value` (text, required) |
| `numeric_comparison` | Numeric Comparison | after | `lesser_field` (int/float), `greater_field` (int/float) | none |
| `at_least_one` | At Least One Required | before | `field_a` (any), `field_b` (any) | none |

## Key Design Decisions to Brainstorm

1. **Storage model**: Should templates be database-seeded rows or hardcoded in application code? They're read-only reference data that changes only with deployments — similar to field constraints. What's the existing pattern for field constraints?

2. **Template substitution engine**: Simple `{{placeholder}}` string replacement, or something more sophisticated? Consider: do any templates need conditional logic in their bodies (e.g., the `string_length` template generates different code depending on whether `min`, `max`, or both are provided)?

3. **Function name generation**: Field validators need the parent field name to generate function names (e.g., `strip_lowercase_email`). How should this be handled? The field name is known at attachment time.

4. **Migration path**: Existing validators in the database have raw `functionBody` but no `templateId`. How do we handle migration? Can we reverse-match existing bodies to templates, or do we need a migration that tags them?

5. **Validation**: When a validator is attached, the backend must validate that all required parameters and fieldMappings are provided, that fieldMapping keys match the template's fieldMappings definitions, and that the templateId exists.

6. **The `string_length` / `number_range` problem**: These templates have conditional code generation — different output depending on which optional parameters are provided. The simple `{{placeholder}}` substitution won't work here. The backend needs to handle this. Options: (a) Jinja2-style templates with conditionals, (b) small Python generator functions per template, (c) restructure these templates to avoid conditionals.

Please refer to the project's `docs/PHILOSOPHY.md` for the guiding principles. Brainstorm these decisions with me before writing an implementation plan.
