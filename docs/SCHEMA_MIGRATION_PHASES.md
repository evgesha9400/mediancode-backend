```
CONTEXT:
The backend has completed a major schema migration. This prompt documents every API endpoint, its current request/response shapes, and exactly how each entity should be displayed on the frontend.

The frontend codebase is at: /Users/evgesha/Documents/Projects/median-code-frontend
All API endpoints are under the base path: /v1/
Authentication: All endpoints require a Clerk JWT in the Authorization header.

YOUR WORKFLOW:
1. Read this ENTIRE prompt first — do not start coding until you understand all entities
2. Search the frontend codebase for every existing interface, API call, component, store, and route related to each entity listed below
3. For EACH PHASE below, create a plan listing:
   - Which files need modification, deletion, or creation
   - Which pages need modification, deletion, or creation
   - Exact interface/type changes
4. Present the plan for review before executing
5. Execute phase by phase — verify each phase works before moving to the next

IMPORTANT: Before making ANY changes, search the entire codebase for all references to each entity. Use grep/search for field names, interface names, API paths, route paths, component names. Miss nothing.

========================================================================
PHASE 1: TYPES + FIELD CONSTRAINTS (Reference Data)
========================================================================

Types and Field Constraints are READ-ONLY global reference data seeded by the backend.
They are not created/edited by users — only listed and used as references by other entities.
These two entities should share a page (e.g., a "Reference Data" or "Building Blocks" page with two tabs or two sections).

------------------------------------------------------------------------
ENTITY: Types
------------------------------------------------------------------------

API: GET /v1/types?namespaceId={optional}

Response shape (array of):
{
  "id": "uuid",
  "namespaceId": "uuid",
  "name": "str",
  "pythonType": "str",
  "description": "String type for text data",
  "importPath": "from datetime import datetime" | null,
  "parentTypeId": "uuid" | null,
  "usedInFields": 5
}

TABLE COLUMNS (list view):
| Column        | Field          | Display                                          |
|---------------|----------------|--------------------------------------------------|
| Name          | name           | Text, primary column                             |
| Python Type   | pythonType     | Code/monospace text                              |
| Import        | importPath     | Code/monospace if non-null, dash or empty if null |
| Description   | description    | Text, truncated if long                          |
| Used in Fields| usedInFields   | Numeric badge/count                              |

NOTES:
- parentTypeId links constrained types to their parent (e.g., EmailStr → str, HttpUrl → str).
  Consider displaying a "Parent" column or grouping child types under their parent.
- This table is read-only: no create/edit/delete actions.
- Rows are not clickable (no detail view needed).
- The 8 seed types are:
  Base: str, int, float, bool, datetime, uuid
  Constrained (parent=str): EmailStr, HttpUrl

MIGRATION — fields REMOVED from old interface:
- category (string) — DELETE all references
- compatibleTypes (string[]) — DELETE all references (this concept moved to Field Constraints)

MIGRATION — fields ADDED to interface:
- importPath: string | null
- parentTypeId: string | null

------------------------------------------------------------------------
ENTITY: Field Constraints (was "Validators")
------------------------------------------------------------------------

THE FRONTEND CURRENTLY HAS A "VALIDATORS" PAGE. This page must be renamed to "FIELD CONSTRAINTS".
The backend entity "validators" has been fully renamed to "field constraints" — table, model,
schema, router, API path, everything. The frontend must match: rename the page, its route,
all interfaces, stores, API calls, and UI labels.

IMPORTANT — this is a TWO-STEP rename:
  1. "validators" → "field-constraints" (the old entity name is gone)
  2. The concept is specifically "Field Constraints" (Pydantic Field() keyword arguments),
     NOT "type constraints" (those are now actual types like EmailStr, HttpUrl).

API: GET /v1/field-constraints?namespaceId={optional}
(old paths that no longer exist: GET /v1/validators, GET /v1/constraints)

Response shape (array of):
{
  "id": "uuid",
  "namespaceId": "uuid",
  "name": "max_length",
  "description": "Validates that string length does not exceed maximum",
  "parameterType": "int",
  "docsUrl": "https://docs.pydantic.dev/..." | null,
  "compatibleTypes": ["str", "uuid"],
  "usedInFields": 3
}

TABLE COLUMNS (list view):
| Column          | Field            | Display                                          |
|-----------------|------------------|--------------------------------------------------|
| Name            | name             | Text/code, primary column                        |
| Description     | description      | Text, truncated if long                          |
| Parameter Type  | parameterType    | Code/badge (int, number, str, None)              |
| Applies To      | compatibleTypes  | Chips/tags (e.g., "str", "uuid" as small badges) |
| Docs            | docsUrl          | Icon link if non-null, hidden if null            |
| Used in Fields  | usedInFields     | Numeric badge/count                              |

NOTES:
- Read-only: no create/edit/delete actions.
- Rows are not clickable (no detail view needed).
- The 8 seed field constraints are:
  String: max_length, min_length, pattern
  Numeric: gt, ge, lt, le, multiple_of
- email_format and url_format NO LONGER EXIST as constraints.
  EmailStr and HttpUrl are now TYPES (see Types above).

MIGRATION — entity rename:
- Rename ALL of: validator → fieldConstraint, Validator → FieldConstraint, validators → fieldConstraints, Validators → FieldConstraints
- API path: /validators → /field-constraints
- Interface: ValidatorResponse → FieldConstraintResponse
- Route paths: any route containing "validator" → "field-constraint"
- Store/state: any validator store → fieldConstraint store
- Labels/headings in UI: "Validators" → "Field Constraints"

MIGRATION — fields REMOVED from old validator interface:
- type (string — was "string" or "numeric") — DELETE (replaced by compatibleTypes)
- category (string — was always "inline") — DELETE
- exampleUsage (string) — DELETE

MIGRATION — seed data removed:
- email_format — NO LONGER A CONSTRAINT. Now the type "EmailStr" (see Types).
- url_format — NO LONGER A CONSTRAINT. Now the type "HttpUrl" (see Types).
- If the frontend had any special handling for these, remove it.

MIGRATION — fields ADDED:
- compatibleTypes: string[]

MIGRATION — fields CHANGED:
- docsUrl: was required string → now string | null

========================================================================
PHASE 2: FIELDS
========================================================================

Fields are user-created entities that define individual data points (like "email", "age", "username").
Each field has a type (from Phase 1) and optional field constraints (from Phase 1).
Fields are the building blocks used to compose Objects (Phase 3).

------------------------------------------------------------------------
ENTITY: Fields
------------------------------------------------------------------------

APIs:
- GET    /v1/fields?namespaceId={optional}     — list
- GET    /v1/fields/{id}                       — get by ID
- POST   /v1/fields                            — create
- PUT    /v1/fields/{id}                       — update
- DELETE /v1/fields/{id}                       — delete

Create request shape:
{
  "namespaceId": "uuid",
  "name": "email",
  "typeId": "uuid",
  "description": "User email address" | null,
  "defaultValue": "None" | null,
  "constraints": [
    {"constraintId": "uuid", "value": "255"},
    {"constraintId": "uuid", "value": null}
  ]
}

Update request shape:
{
  "name": "updated_email" | null,
  "description": "Updated description" | null,
  "defaultValue": "new_default" | null,
  "constraints": [{"constraintId": "uuid", "value": "255"}] | null
}
Note: constraints=null means "don't touch", constraints=[] means "clear all".

Response shape:
{
  "id": "uuid",
  "namespaceId": "uuid",
  "name": "email",
  "typeId": "uuid",
  "description": "User email address" | null,
  "defaultValue": "None" | null,
  "usedInApis": ["endpoint-uuid-1", "endpoint-uuid-2"],
  "constraints": [
    {"constraintId": "uuid", "name": "max_length", "value": "255"},
    {"constraintId": "uuid", "name": "pattern", "value": "^[a-z]+$"}
  ]
}

TABLE COLUMNS (list view):
| Column       | Field              | Display                                                         |
|--------------|--------------------|-----------------------------------------------------------------|
| Name         | name               | Text, primary column, clickable to edit                         |
| Type         | typeId             | Resolve to type name from the types list (e.g., "str", "int")  |
| Description  | description        | Text, truncated if long. Dash if null                           |
| Default      | defaultValue       | Code/monospace if non-null. Dash if null                        |
| Constraints  | constraints        | Count badge, or comma-separated names (e.g., "max_length, pattern") |
| Used In      | usedInApis         | Count badge (number of endpoints using this field)              |

FORM (create/edit):
- name: text input (required)
- typeId: dropdown/select populated from GET /v1/types (show type name, send UUID)
- description: textarea (optional)
- defaultValue: text input (optional)
- constraints section:
  - When user selects a type, filter available field constraints by checking if the type's
    name (e.g., "str") is in each field constraint's compatibleTypes array
  - Show applicable field constraints as a list/checklist
  - All 8 seed field constraints take a parameter — show a value input for each
  - On submit, send array of {constraintId, value} pairs for selected constraints
  - Fetch field constraints from GET /v1/field-constraints

DELETE:
- Cannot delete if usedInApis is non-empty (backend returns 400)
- Show confirmation dialog

MIGRATION — fields REMOVED from old interface (if any):
- validators (the old field→validator attachment) — REPLACE with constraints

MIGRATION — fields ADDED:
- constraints: Array<{constraintId: string, name: string, value: string | null}> on response
- constraints: Array<{constraintId: string, value: string | null}> on create/update request
- usedInApis: string[] on response

========================================================================
PHASE 3: OBJECTS
========================================================================

Objects are user-created Pydantic model definitions composed of field references.
They define the shape of request/response bodies (e.g., "UserCreate", "ProductResponse").

------------------------------------------------------------------------
ENTITY: Objects
------------------------------------------------------------------------

APIs:
- GET    /v1/objects?namespaceId={optional}    — list
- GET    /v1/objects/{id}                      — get by ID
- POST   /v1/objects                           — create
- PUT    /v1/objects/{id}                      — update
- DELETE /v1/objects/{id}                      — delete

Create request shape:
{
  "namespaceId": "uuid",
  "name": "UserCreate",
  "description": "User creation payload" | null,
  "fields": [
    {"fieldId": "uuid", "required": true},
    {"fieldId": "uuid", "required": false}
  ]
}

Update request shape:
{
  "name": "UpdatedName" | null,
  "description": "Updated description" | null,
  "fields": [{"fieldId": "uuid", "required": true}] | null
}

Response shape:
{
  "id": "uuid",
  "namespaceId": "uuid",
  "name": "UserCreate",
  "description": "User creation payload" | null,
  "fields": [
    {"fieldId": "uuid", "required": true},
    {"fieldId": "uuid", "required": false}
  ],
  "usedInApis": ["endpoint-uuid-1"]
}

TABLE COLUMNS (list view):
| Column       | Field       | Display                                                            |
|--------------|-------------|--------------------------------------------------------------------|
| Name         | name        | Text, primary column, clickable to edit                            |
| Description  | description | Text, truncated. Dash if null                                      |
| Fields       | fields      | Count badge (e.g., "3 fields")                                     |
| Used In      | usedInApis  | Count badge (number of endpoints using this object)                |

FORM (create/edit):
- name: text input (required) — should be PascalCase (the backend expects it)
- description: textarea (optional)
- fields section:
  - A sortable list of field references
  - Each row: field selector dropdown (from GET /v1/fields, show field name, send UUID) + required checkbox/toggle
  - Add/remove buttons for rows
  - Drag-to-reorder (position is determined by array order)

DELETE:
- Cannot delete if usedInApis is non-empty (backend returns 400)
- Show confirmation dialog

MIGRATION:
- No schema changes to objects. But verify the interface matches the response shape above.

========================================================================
PHASE 4: APIs + ENDPOINTS
========================================================================

APIs are the top-level entity. Each API has child endpoints.
These should be displayed on a single page: the API list view shows all APIs,
and clicking an API navigates to its detail view which shows its endpoints.

------------------------------------------------------------------------
ENTITY: APIs
------------------------------------------------------------------------

APIs:
- GET    /v1/apis?namespaceId={optional}       — list
- GET    /v1/apis/{id}                         — get by ID
- POST   /v1/apis                              — create
- PUT    /v1/apis/{id}                         — update
- DELETE /v1/apis/{id}                         — delete (cascades to endpoints)
- POST   /v1/apis/{id}/generate                — generate code (returns ZIP)

Create request shape:
{
  "namespaceId": "uuid",
  "title": "User Management API",
  "version": "1.0.0",
  "description": "API for managing users" | null,
  "baseUrl": "/api/v1" | null,
  "serverUrl": "https://api.example.com" | null
}

Update request shape:
{
  "title": "Updated Title" | null,
  "version": "2.0.0" | null,
  "description": "Updated" | null,
  "baseUrl": "/api/v2" | null,
  "serverUrl": "https://new.example.com" | null
}

Response shape:
{
  "id": "uuid",
  "namespaceId": "uuid",
  "title": "User Management API",
  "version": "1.0.0",
  "description": "API for managing user accounts",
  "baseUrl": "/api/v1",
  "serverUrl": "https://api.example.com",
  "createdAt": "2026-01-25T10:30:00Z",
  "updatedAt": "2026-01-25T10:30:00Z"
}

TABLE COLUMNS (list view):
| Column      | Field       | Display                                                         |
|-------------|-------------|-----------------------------------------------------------------|
| Title       | title       | Text, primary column, clickable to navigate to API detail       |
| Version     | version     | Badge/code text                                                 |
| Base URL    | baseUrl     | Code/monospace                                                  |
| Description | description | Text, truncated                                                 |
| Tags        | (derived)   | Derive from endpoints: fetch endpoints for this API, collect unique tagName values, display as chips. Alternatively, show this only on the detail page. |
| Endpoints   | (derived)   | Count badge — requires fetching endpoints for this API, or show on detail page only |
| Updated     | updatedAt   | Relative time (e.g., "2 hours ago")                             |

FORM (create/edit):
- title: text input (required)
- version: text input (required, e.g., "1.0.0")
- description: textarea (optional)
- baseUrl: text input (optional)
- serverUrl: text input (optional)

DETAIL PAGE:
The API detail page should show:
- API metadata (title, version, description, baseUrl, serverUrl, timestamps)
- Tags derived from endpoints (collect unique tagName values, show as chips)
- Endpoints table (see below)
- "Generate Code" button that calls POST /v1/apis/{id}/generate and downloads the ZIP

DELETE:
- Cascades to all endpoints — warn user
- Show confirmation dialog

MIGRATION — fields REMOVED:
- tags: was Array<{name: string, description: string}> on create/update/response — DELETE
- TagSchema / Tag interface — DELETE the file/interface entirely
- Remove tags from create/edit forms
- Tags are now derived client-side from endpoint tagName values (display only, not editable on the API)

------------------------------------------------------------------------
ENTITY: Endpoints (child of API)
------------------------------------------------------------------------

Endpoints are always scoped to a parent API. They should be displayed as a table
within the API detail page, not as a standalone page.

APIs:
- GET    /v1/endpoints?namespaceId={optional}  — list all
- GET    /v1/endpoints/{id}                    — get by ID
- POST   /v1/endpoints                         — create
- PUT    /v1/endpoints/{id}                    — update
- DELETE /v1/endpoints/{id}                    — delete

Create request shape:
{
  "apiId": "uuid",
  "method": "GET",
  "path": "/users/{user_id}",
  "description": "Get user by ID",
  "tagName": "Users" | null,
  "pathParams": [{"name": "user_id", "fieldId": "uuid"}],
  "queryParamsObjectId": "uuid" | null,
  "requestBodyObjectId": "uuid" | null,
  "responseBodyObjectId": "uuid" | null,
  "useEnvelope": true,
  "responseShape": "object"
}

Update request shape:
{
  "apiId": "uuid" | null,
  "method": "POST" | null,
  "path": "/users" | null,
  "description": "Updated" | null,
  "tagName": "Users" | null,
  "pathParams": [{"name": "user_id", "fieldId": "uuid"}] | null,
  "queryParamsObjectId": "uuid" | null,
  "requestBodyObjectId": "uuid" | null,
  "responseBodyObjectId": "uuid" | null,
  "useEnvelope": true | null,
  "responseShape": "list" | null
}

Response shape:
{
  "id": "uuid",
  "apiId": "uuid",
  "method": "GET",
  "path": "/users/{user_id}",
  "description": "Retrieve user by ID",
  "tagName": "Users" | null,
  "pathParams": [{"name": "user_id", "fieldId": "uuid"}],
  "queryParamsObjectId": "uuid" | null,
  "requestBodyObjectId": "uuid" | null,
  "responseBodyObjectId": "uuid" | null,
  "useEnvelope": true,
  "responseShape": "object"
}

TABLE COLUMNS (within API detail page):
| Column         | Field                  | Display                                                     |
|----------------|------------------------|-------------------------------------------------------------|
| Method         | method                 | Colored badge (GET=green, POST=blue, PUT=orange, DELETE=red)|
| Path           | path                   | Code/monospace, primary column, clickable to edit           |
| Description    | description            | Text, truncated                                             |
| Tag            | tagName                | Chip/badge if non-null, dash if null                        |
| Path Params    | pathParams             | Count or comma-separated names (e.g., "user_id, item_id")  |
| Query Params   | queryParamsObjectId    | Object name (resolve from objects list) or dash             |
| Request Body   | requestBodyObjectId    | Object name (resolve from objects list) or dash             |
| Response Body  | responseBodyObjectId   | Object name (resolve from objects list) or dash             |
| Envelope       | useEnvelope            | Check icon or badge                                         |
| Shape          | responseShape          | Badge: "object" or "list"                                   |

FORM (create/edit):
- apiId: pre-filled from parent API (hidden or read-only)
- method: dropdown (GET, POST, PUT, PATCH, DELETE)
- path: text input (required)
- description: text input (required)
- tagName: text input (optional) — free text, used for grouping in OpenAPI spec
- pathParams section:
  - For each {parameter} in the path, show a row with:
    - name: text (auto-extracted from path, e.g., "user_id" from "/users/{user_id}")
    - fieldId: dropdown/select populated from GET /v1/fields (show field name, send UUID)
  - Ideally auto-detect params from path input and create rows automatically
- queryParamsObjectId: dropdown from GET /v1/objects (optional)
- requestBodyObjectId: dropdown from GET /v1/objects (optional)
- responseBodyObjectId: dropdown from GET /v1/objects (optional)
- useEnvelope: checkbox/toggle (default true)
- responseShape: dropdown ("object" or "list")

MIGRATION — fields REMOVED:
- namespaceId: was on create request and response — DELETE (derived through apiId)

MIGRATION — pathParams schema CHANGED:
OLD: [{"id": "uuid", "name": "str", "type": "str", "description": "str", "required": bool}]
NEW: [{"name": "str", "fieldId": "uuid"}]
- Remove id, type, description, required from path param interface
- Add fieldId
- Update path param UI: instead of manual type/description/required inputs, use a field selector dropdown

========================================================================
PHASE 5: NAMESPACES
========================================================================

Namespaces are the organizational container for all user entities.
Every API, field, object, etc. belongs to a namespace.
The "Global" namespace is locked and contains the seed types/constraints.

------------------------------------------------------------------------
ENTITY: Namespaces
------------------------------------------------------------------------

APIs:
- GET    /v1/namespaces                        — list
- GET    /v1/namespaces/{id}                   — get by ID
- POST   /v1/namespaces                        — create
- PUT    /v1/namespaces/{id}                   — update
- DELETE /v1/namespaces/{id}                   — delete

Create request shape:
{
  "name": "my-api-project",
  "description": "My API project namespace" | null
}

Update request shape:
{
  "name": "updated-name" | null,
  "description": "Updated description" | null
}

Response shape:
{
  "id": "uuid",
  "name": "Global",
  "description": "Built-in types and constraints" | null,
  "locked": true,
  "isDefault": false
}

TABLE COLUMNS (list view — or sidebar/dropdown, depending on current UI):
| Column      | Field       | Display                                         |
|-------------|-------------|-------------------------------------------------|
| Name        | name        | Text, primary column                            |
| Description | description | Text, truncated. Dash if null                   |
| Locked      | locked      | Lock icon or badge if true, hidden if false     |
| Default     | isDefault   | Star icon or badge if true, hidden if false     |

NOTES:
- Locked namespaces (the Global namespace) cannot be edited or deleted.
- The Global namespace is system-created and contains seed types and constraints.
- User namespaces are where users create their fields, objects, APIs, etc.
- Namespaces serve as the scoping mechanism — most list endpoints accept a namespaceId query param to filter.
- A user typically works within one namespace at a time (their default).

MIGRATION:
- No API contract changes. Verify the interface matches the shape above.

========================================================================
BACKEND-ONLY TABLES (NO FRONTEND IMPACT YET)
========================================================================

These tables exist in the database but have NO API endpoints yet.
Do NOT build any UI for these. They are listed here for awareness only.

- field_validators: Custom field validator function definitions (future feature)
- field_validator_associations: Links custom field validators to fields
- model_validators: Custom model-level validator function definitions (future feature)
- object_model_validator_associations: Links model validators to objects

========================================================================
COMPREHENSIVE SEARCH CHECKLIST
========================================================================

Before making any changes, run these searches across the entire frontend codebase:

ENTITY RENAMES:
- [ ] validator / Validator / validators / Validators → fieldConstraint / FieldConstraint / fieldConstraints / FieldConstraints
- [ ] /validators API path → /field-constraints
- [ ] ValidatorResponse → FieldConstraintResponse
- [ ] Any route path containing "validator" → "field-constraint"
- [ ] Any store/state named "validator" → "fieldConstraint"

REMOVED FIELDS:
- [ ] category on types (DELETE)
- [ ] compatibleTypes on types (DELETE — now on field constraints)
- [ ] type field on validators/constraints (DELETE — replaced by compatibleTypes)
- [ ] category on validators/constraints (DELETE)
- [ ] exampleUsage on validators/constraints (DELETE)
- [ ] tags on APIs — create, update, response (DELETE)
- [ ] TagSchema / Tag interface (DELETE file)
- [ ] namespaceId on endpoints — create and response (DELETE — still on API/field/object)
- [ ] Old path param fields: id, type, description, required on endpoint path params (DELETE)
- [ ] email_format / url_format references — these are now TYPES (EmailStr, HttpUrl), not constraints

ADDED FIELDS:
- [ ] importPath on types (string | null)
- [ ] parentTypeId on types (string | null)
- [ ] compatibleTypes on field constraints (string[])
- [ ] constraints on field create/update request ({constraintId, value}[])
- [ ] constraints on field response ({constraintId, name, value}[])
- [ ] usedInApis on field response (string[])
- [ ] fieldId on path params (replaces old schema)

CHANGED FIELDS:
- [ ] docsUrl on field constraints — now nullable
- [ ] pathParams on endpoints — schema changed from {id, name, type, description, required} to {name, fieldId}

SEED DATA CHANGES:
- [ ] Types now include: EmailStr (parent=str), HttpUrl (parent=str) — these are NEW types
- [ ] Field constraints reduced from 10 to 8 — email_format and url_format REMOVED
```

---

## Verification Summary

| Phase | Table(s) | Status |
|-------|----------|--------|
| 1 | namespaces + fields + objects (TEXT normalization) | DONE |
| 2 | types (major restructure) | DONE |
| 3 | validators → field_constraints (rename + restructure) | DONE |
| 4 | apis (drop tags + TEXT) | DONE |
| 5 | api_endpoints + endpoint_parameters (restructure + delete) | DONE |
| 6 | field_validators + field_validator_associations (complete replacement + new) | DONE |
| 7 | model_validators + object_model_validator_associations (new tables) | DONE |
| 8 | field_constraint_values (new table) | DONE |

### Integration Tasks (Post-Migration)

| Task | Status |
|------|--------|
| Wire `field_constraint_values` into field CRUD | DONE |
| Wire `field_constraint_values` into generation service | DONE |
| Wire `field_constraint_values` into field constraints router (`usedInFields`) | DONE |
| Update generation service to use path_params field references for type resolution | DONE |
| Build field_validators CRUD endpoints (custom validator management) | NOT YET — structural tables exist, no API |
| Build model_validators CRUD endpoints (custom model validator management) | NOT YET — structural tables exist, no API |

---

## Archived: Original Phase-by-Phase Backend Prompts

<details>
<summary>Click to expand original backend execution prompts (for reference only)</summary>

### Phase 1: TEXT normalization (namespaces + fields + objects)

All three tables: VARCHAR/String → TEXT. No logic changes.

**Tables**: namespaces, fields, objects
**Columns changed**: `user_id`, `name` → Text in each
**Frontend impact**: None (internal column types only)

### Phase 2: types

**Removed**: `category` (String), `compatible_types` (JSONB)
**Added**: `import_path` (Text nullable), `user_id` (Text nullable), `parent_type_id` (UUID FK nullable)
**Changed**: `name`, `python_type` → Text; `description` default added
**Frontend impact**: TypeResponse schema changed

### Phase 3: validators → constraints

**Renamed**: table `validators` → `constraints`, model `ValidatorModel` → `ConstraintModel`
**Removed**: `type`, `category`, `example_usage`
**Added**: `compatible_types` (Text[] array)
**Changed**: `name`, `parameter_type` → Text; `docs_url` → nullable
**Files renamed**: `validator.py` → `constraint.py`, `validators.py` → `constraints.py`
**Endpoint renamed**: `/validators` → `/constraints`
**Frontend impact**: Full entity rename + response schema changes

### Phase 4: apis

**Removed**: `tags` (JSONB)
**Changed**: `user_id`, `title`, `version`, `base_url`, `server_url` → Text
**Deleted**: `src/api/schemas/tag.py`
**Frontend impact**: tags removed from API create/update/response

### Phase 5: api_endpoints + delete endpoint_parameters

**Removed from api_endpoints**: `namespace_id`, `user_id`
**Added to api_endpoints**: `path_params` (JSONB, format: `[{name, fieldId}]`)
**Changed**: `path`, `tag_name` → Text
**Deleted**: `endpoint_parameters` table and `EndpointParameter` model
**Schema changed**: `EndpointParameterSchema` → `PathParamSchema` (simpler: just name + fieldId)
**Frontend impact**: namespaceId removed from endpoints, path params schema completely changed

### Phase 6: field_validators (complete replacement) + field_validator_associations

**Replaced**: Old `FieldValidator` join table (field_id, name, params) → New `FieldValidatorModel` entity (custom validator functions: namespace_id, function_name, mode, function_body, description)
**Added**: `FieldValidatorAssociation` table
**Frontend impact**: Old validator-on-field concept replaced by constraint-on-field (via constraint_field_values_associations)

### Phase 7: model_validators + object_model_validator_associations

**Added**: Two new tables for model-level custom validator functions
**Frontend impact**: None (no API endpoints yet)

### Phase 8: constraint_field_values_associations

**Added**: New join table linking constraints to fields with parameter values
**Frontend impact**: None directly (integration was done as separate work — see field schema changes above)

### Post-Migration Integration (also completed)

- constraint_field_values_associations wired into field CRUD (FieldCreate/FieldUpdate accept constraints, FieldService manages associations)
- constraint_field_values_associations wired into generation service (_build_validators reads constraint_values for code generation)
- constraint_field_values_associations wired into constraints router (usedInFields counts via ConstraintFieldValueAssociation)
- Field schema now includes FieldConstraintInput, FieldConstraintResponse, and constraints field
- Field response now includes usedInApis (endpoint IDs where field is used through objects)

</details>
