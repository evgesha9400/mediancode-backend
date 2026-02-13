# Schema Migration Phases

> **Strategy**: We are replacing the initial migration (`4141ad7f2255`) and seed data migration (`b1a2c3d4e5f6`) in-place. The product is not shipped — no incremental migrations needed. We have a DB_RESET environment variable set to true, so on each push the database is reset and re-seeded.

> **Workflow per phase**: (1) Apply backend prompt → (2) Verify backend works → (3) Apply frontend prompt → (4) Move to next phase.

---

## Phase 1: TEXT normalization (`namespaces` + `fields` + `objects`)

All three tables need the same trivial change: VARCHAR/String → TEXT. No logic changes, no schema/service/router impact. Safe to batch.

### Changes

**`namespaces`**
| Column | Before | After |
|--------|--------|-------|
| `user_id` | `String(255)` | `Text` |
| `name` | `String(255)` | `Text` |

**`fields`**
| Column | Before | After |
|--------|--------|-------|
| `user_id` | `String(255)` | `Text` |
| `name` | `String(255)` | `Text` |

**`objects`**
| Column | Before | After |
|--------|--------|-------|
| `user_id` | `String(255)` | `Text` |
| `name` | `String(255)` | `Text` |

Note: The dbdiagram shows `objects.user_id` as UUID, but we use TEXT to be consistent with all other tables (Clerk user IDs are strings). Intentional deviation from the diagram.

### Impact
- Minimal. Purely column type normalization. No schema/service/router logic changes.

### Backend Prompt
```
CONTEXT:
We are normalizing all VARCHAR/String columns to TEXT across the database. This is phase 1 of a multi-phase schema migration. We are editing the existing migration files in-place (product not shipped yet). This phase covers three tables with identical changes.

FILES TO MODIFY:
1. src/api/models/database.py — Namespace, FieldModel, ObjectDefinition models
2. src/api/migrations/versions/4141ad7f2255_initial_schema.py — namespaces, fields, objects tables

CHANGES:

In database.py:
- Namespace model: Change `user_id` from `String(255)` to `Text`, change `name` from `String(255)` to `Text`
- FieldModel: Change `user_id` from `String(255)` to `Text`, change `name` from `String(255)` to `Text`
- ObjectDefinition: Change `user_id` from `String(255)` to `Text`, change `name` from `String(255)` to `Text`

In the initial migration (4141ad7f2255):
- For namespaces, fields, and objects tables: change all `sa.Column("user_id", sa.String(length=255), ...)` → `sa.Column("user_id", sa.Text(), ...)`
- Same for `name` columns: `sa.String(length=255)` → `sa.Text()`

DO NOT change any other tables in this phase.
DO NOT change schemas, services, or routers (no logic changes needed).
DO NOT create new migration files — edit the existing ones in-place.
Run `make test` after changes to verify nothing breaks.

FINAL STEP: No frontend changes needed for this phase (column types are internal to PostgreSQL, API response types are unchanged). Confirm this in your summary.
```

---

## Phase 2: `types`

### Changes
| Column | Before | After | Reason |
|--------|--------|-------|--------|
| `name` | `String(50)` | `Text, not null` | TEXT standard |
| `category` | `String(50), not null` | **DROPPED** | primitive/abstract distinction serves no purpose |
| `python_type` | `String(100)` | `Text, not null` | TEXT standard |
| `description` | `Text, not null` | `Text, not null, default=''` | Add default |
| `compatible_types` | `JSONB, not null` | **DROPPED** | Compatibility now lives on constraints table |
| `import_path` | — | `Text, nullable` | **NEW**: stores import statement (e.g., `from pydantic import EmailStr`) |
| `user_id` | — | `Text, nullable` | **NEW**: for future custom user-defined types |
| `parent_type_id` | — | `UUID FK → types.id, nullable` | **NEW**: self-referential FK for constrained types (EmailStr → str) |

### Impact
- **Heavy**. Affects: `TypeModel` in database.py, TypeResponse schema, types router, seed data, generation service.
- `compatible_types` removal means the types API no longer returns this field.
- `category` removal means the types API no longer returns this field.
- `parent_type_id` addition means the types API should return this field.
- Seed data must be updated: remove `category` and `compatible_types` from type seeds. Add `import_path` where applicable.

### Backend Prompt
```
CONTEXT:
Phase 2 of schema migration. We are restructuring the `types` table. We are editing existing migration files in-place (product not shipped).

FILES TO MODIFY:
1. src/api/models/database.py — TypeModel class
2. src/api/migrations/versions/4141ad7f2255_initial_schema.py — types table creation
3. src/api/migrations/versions/b1a2c3d4e5f6_seed_global_data.py — types seed data
4. src/api/schemas/type.py — TypeResponse schema
5. src/api/routers/types.py — types router (list_types handler)

CHANGES FOR `types` TABLE:

1. database.py TypeModel:
   - REMOVE `category` column entirely
   - REMOVE `compatible_types` column entirely
   - CHANGE `name` from `String(50)` to `Text`
   - CHANGE `python_type` from `String(100)` to `Text`
   - CHANGE `description` to `Text, nullable=False, default=""`
   - ADD `import_path: Mapped[str | None] = mapped_column(Text, nullable=True)`
   - ADD `user_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)`
   - ADD `parent_type_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("types.id"), nullable=True)`
   - ADD relationship: `parent_type: Mapped["TypeModel | None"] = relationship(remote_side=[id])`
   - ADD relationship: `children: Mapped[list["TypeModel"]] = relationship(back_populates="parent_type")`
   - Update the docstring to reflect new columns

2. Initial migration (4141ad7f2255) — types table:
   - Remove `category` column
   - Remove `compatible_types` column
   - Change `name` to `sa.Text()`
   - Change `python_type` to `sa.Text()`
   - Add `sa.Column("import_path", sa.Text(), nullable=True)`
   - Add `sa.Column("user_id", sa.Text(), nullable=True)`
   - Add `sa.Column("parent_type_id", postgresql.UUID(as_uuid=True), nullable=True)`
   - Add FK constraint: `sa.ForeignKeyConstraint(["parent_type_id"], ["types.id"])`
   - Add index on `user_id`

3. Seed data (b1a2c3d4e5f6) — TYPES_DATA:
   - Remove `category` key from all type entries
   - Remove `compatible_types` key from all type entries
   - Add `import_path` key: null for primitives (str, int, float, bool), `"from datetime import datetime"` for datetime, `"from uuid import UUID"` for uuid
   - Add `user_id` key: null for all (these are global/system types)
   - Add `parent_type_id` key: null for all base types
   - Update the sa.table() column definitions to match the new columns

4. schemas/type.py TypeResponse:
   - REMOVE `category` field
   - REMOVE `compatible_types` field
   - ADD `import_path: str | None = Field(default=None, alias="importPath")`
   - ADD `parent_type_id: UUID | None = Field(default=None, alias="parentTypeId")`
   - Keep `used_in_fields` as-is

5. routers/types.py:
   - Remove references to `category` and `compatible_types` in the TypeResponse construction
   - Add `import_path=t.import_path` and `parent_type_id=t.parent_type_id` to TypeResponse construction

6. services/generation.py:
   - In `_fetch_fields`, the code accesses `field.field_type.name` — this still works.
   - In `_map_field_type`, no changes needed — it maps by type name.
   - No changes needed in generation service for this phase.

Run `make test` after changes.

FINAL STEP: After all backend changes are verified, write a detailed frontend prompt for this phase. The frontend prompt must:
- Be a self-contained instruction for a separate Claude agent working on the frontend repo at /Users/evgesha/Documents/Projects/median-code-frontend
- List the exact API response changes (fields removed, fields added, type changes)
- Specify which TypeScript interfaces, API calls, and components need updating
- Include the before/after shape of the types API response
- The frontend agent should search the codebase for all usages of the changed fields before making changes
Output the frontend prompt in a clearly marked section at the end of your response.
```

---

## Phase 3: `validators` → `constraints`

### Changes
| Column | Before | After | Reason |
|--------|--------|-------|--------|
| Table name | `validators` | `constraints` | Better reflects purpose — these are field constraints, not arbitrary validators |
| `name` | `String(255)` | `Text, not null` | TEXT standard |
| `type` | `String(50), not null` | **DROPPED** | Replaced by `compatible_types` array |
| `category` | `String(50), not null` | **DROPPED** | Was always "inline" — serves no purpose |
| `parameter_type` | `String(50)` | `Text, not null` | TEXT standard |
| `example_usage` | `String(255), not null` | **DROPPED** | Not essential for the schema |
| `docs_url` | `String(500), not null` | `Text, nullable` | TEXT standard, made nullable |
| `compatible_types` | — | `Text[], not null` | **NEW**: array of type names this constraint applies to (e.g., `["str", "uuid"]` for string constraints) |

### Impact
- **Heavy**. Table rename affects: model name, all imports, all references in services/routers/schemas.
- `ValidatorModel` → `ConstraintModel`, `validators` → `constraints` throughout.
- Seed data must be restructured: old `type` field values become entries in `compatible_types` array.
- The old `type: "string"` becomes `compatible_types: ["str", "uuid"]` (because uuid has string-like constraints).
- The old `type: "numeric"` becomes `compatible_types: ["int", "float"]`.

### Backend Prompt
```
CONTEXT:
Phase 3 of schema migration. We are renaming the `validators` table to `constraints` and restructuring its columns. The current table stores Pydantic Field() constraints like max_length, min_length, gt, ge, etc. The rename better reflects their purpose.

We are editing existing migration files in-place (product not shipped).

FILES TO MODIFY:
1. src/api/models/database.py — rename ValidatorModel → ConstraintModel, update columns
2. src/api/migrations/versions/4141ad7f2255_initial_schema.py — rename table, update columns
3. src/api/migrations/versions/b1a2c3d4e5f6_seed_global_data.py — update seed data
4. src/api/schemas/validator.py — rename to src/api/schemas/constraint.py, update schemas
5. src/api/routers/validators.py — rename to src/api/routers/constraints.py, update router
6. src/api/main.py — update router imports if routers are registered there

CHANGES:

1. database.py:
   - Rename class `ValidatorModel` → `ConstraintModel`
   - Change `__tablename__` from `"validators"` to `"constraints"`
   - REMOVE columns: `type`, `category`, `example_usage`
   - CHANGE `name` from `String(255)` to `Text`
   - CHANGE `parameter_type` from `String(50)` to `Text`
   - CHANGE `description` from `Text, not null` to `Text, nullable=False, default=""`
   - CHANGE `docs_url` from `String(500), not null` to `Text, nullable=True`
   - ADD: `compatible_types: Mapped[list] = mapped_column(postgresql.ARRAY(sa.Text), nullable=False)`
     (import ARRAY from sqlalchemy.dialects.postgresql)
   - In Namespace model: rename relationship `validators` → `constraints`, update back_populates
   - In ConstraintModel: update relationship to `namespace: Mapped["Namespace"] = relationship(back_populates="constraints")`

2. Initial migration (4141ad7f2255):
   - Rename table creation from "validators" to "constraints"
   - Remove columns: type, category, example_usage
   - Change name to sa.Text()
   - Change parameter_type to sa.Text()
   - Change description default to ''
   - Change docs_url to sa.Text(), nullable=True
   - Add: sa.Column("compatible_types", postgresql.ARRAY(sa.Text()), nullable=False)
   - Update all index names from ix_validators_* to ix_constraints_*
   - Update downgrade() to drop "constraints" instead of "validators"

3. Seed data (b1a2c3d4e5f6):
   - Rename VALIDATORS_DATA → CONSTRAINTS_DATA
   - For each entry:
     - REMOVE keys: `type`, `category`, `example_usage`
     - ADD `compatible_types` key:
       - String constraints (max_length, min_length, pattern, email_format, url_format): `["str", "uuid"]`
         (Note: email_format and url_format are actually type-level validators, not Field constraints.
          Keep them as constraints for now but set compatible_types to ["str"])
       - Numeric constraints (gt, ge, lt, le, multiple_of): `["int", "float"]`
   - Update sa.table() definition: table name "constraints", remove old columns, add compatible_types
   - Update downgrade: DELETE FROM constraints WHERE ...

4. Rename src/api/schemas/validator.py → src/api/schemas/constraint.py:
   - Rename `ValidatorResponse` → `ConstraintResponse`
   - REMOVE fields: `type`, `category`, `example_usage`
   - ADD: `compatible_types: list[str] = Field(..., alias="compatibleTypes")`
   - Change `docs_url` to allow None: `docs_url: str | None = Field(default=None, alias="docsUrl")`
   - Keep `FieldReferenceSchema` (rename file reference in imports)
   - Keep `used_in_fields` and `fields_using_validator` (rename latter to `fields_using_constraint` / alias `fieldsUsingConstraint`)

5. Rename src/api/routers/validators.py → src/api/routers/constraints.py:
   - Update router prefix from "/validators" to "/constraints"
   - Update tags from ["Validators"] to ["Constraints"]
   - Update all imports: ValidatorModel → ConstraintModel, ValidatorResponse → ConstraintResponse
   - Rename function `list_validators` → `list_constraints`
   - Update internal variable names accordingly
   - The logic for get_fields_by_validator should still work — it queries FieldValidator (the join table) by name, and those names still match constraint names

6. Update imports everywhere:
   - src/api/main.py: update router import
   - src/api/routers/__init__.py if applicable
   - Any other file importing from validators

DO NOT modify the field_validators table or its related code in this phase.
Run `make test` after changes.

FINAL STEP: After all backend changes are verified, write a detailed frontend prompt for this phase. The frontend prompt must:
- Be a self-contained instruction for a separate Claude agent working on the frontend repo at /Users/evgesha/Documents/Projects/median-code-frontend
- List the exact API changes: endpoint renamed from /validators to /constraints, response schema changes
- Specify all fields removed (type, category, exampleUsage) and added (compatibleTypes)
- Instruct renaming all "validator" references to "constraint" in interfaces, API calls, components, store/state
- Include the before/after shape of the constraints API response
- The frontend agent should search the codebase for all usages of the changed fields before making changes
Output the frontend prompt in a clearly marked section at the end of your response.
```

---

## Phase 4: `apis`

### Changes
| Column | Before | After | Reason |
|--------|--------|-------|--------|
| `user_id` | `String(255)` | `Text` | TEXT standard |
| `title` | `String(255)` | `Text` | TEXT standard |
| `version` | `String(50)` | `Text` | TEXT standard |
| `base_url` | `String(255)` | `Text` | TEXT standard |
| `server_url` | `String(255)` | `Text` | TEXT standard |
| `tags` | `JSONB, not null, default=[]` | **DROPPED** | Tags are now derived from endpoint `tag_name` values — no need to store redundant data on the API |

### Impact
- **Medium**. Drop tags column and remove `TagSchema` dependency.
- API create/update schemas no longer accept tags.
- API response schema no longer returns tags.
- Generation service must derive tags from endpoints instead of reading `api.tags`.
- Delete `src/api/schemas/tag.py` entirely.

### Backend Prompt
```
CONTEXT:
Phase 4 of schema migration. We are simplifying the `apis` table by removing the `tags` JSONB column. Tags are now derived from endpoint `tag_name` values at query time — storing them redundantly on the API was a sync bug waiting to happen.

We are editing existing migration files in-place (product not shipped).

FILES TO MODIFY:
1. src/api/models/database.py — ApiModel class
2. src/api/migrations/versions/4141ad7f2255_initial_schema.py — apis table
3. src/api/schemas/api.py — ApiCreate, ApiUpdate, ApiResponse
4. src/api/schemas/tag.py — DELETE this file entirely
5. src/api/services/api.py — remove tags handling from create/update
6. src/api/services/generation.py — derive tags from endpoints instead of api.tags
7. src/api/routers/apis.py — no logic changes needed (uses schema)

CHANGES:

1. database.py ApiModel:
   - REMOVE `tags` column entirely
   - CHANGE `user_id` from `String(255)` to `Text`
   - CHANGE `title` from `String(255)` to `Text`
   - CHANGE `version` from `String(50)` to `Text`
   - CHANGE `base_url` from `String(255)` to `Text`
   - CHANGE `server_url` from `String(255)` to `Text`
   - Update docstring (remove tags ivar)

2. Initial migration (4141ad7f2255):
   - Remove the `tags` JSONB column from apis table creation
   - Change all String columns to sa.Text()

3. schemas/api.py:
   - REMOVE `from api.schemas.tag import TagSchema` import
   - ApiCreate: REMOVE `tags` field
   - ApiUpdate: REMOVE `tags` field
   - ApiResponse: REMOVE `tags` field

4. DELETE src/api/schemas/tag.py entirely

5. services/api.py:
   - create_for_user: Remove `tags=tags_data` and the `tags_data` list comprehension
   - update_api: Remove the `if data.tags is not None:` block

6. services/generation.py:
   - In `_convert_to_input_api`:
     - Remove the tags conversion from `api.tags`:
       ```python
       # OLD: input_tags = [InputTag(name=tag["name"], description=tag["description"]) for tag in api.tags]
       ```
     - Replace with deriving tags from endpoints:
       ```python
       # Derive tags from endpoint tag_names
       tag_names = {ep.tag_name for ep in api.endpoints if ep.tag_name}
       input_tags = [InputTag(name=name, description="") for name in sorted(tag_names)]
       ```
     - The InputTag still needs a description — use empty string since we no longer store tag descriptions

Run `make test` after changes.

FINAL STEP: After all backend changes are verified, write a detailed frontend prompt for this phase. The frontend prompt must:
- Be a self-contained instruction for a separate Claude agent working on the frontend repo at /Users/evgesha/Documents/Projects/median-code-frontend
- List the exact API changes: tags field removed from API create/update request and response schemas
- Instruct removing tags from API create/edit forms and API detail/list views
- If the frontend currently displays tags on APIs, explain that tags should now be derived by aggregating unique tagName values from the API's endpoints (client-side)
- Include the before/after shape of the APIs API response
- The frontend agent should search the codebase for all usages of tags and TagSchema before making changes
Output the frontend prompt in a clearly marked section at the end of your response.
```

---

## Phase 5: `api_endpoints` + delete `endpoint_parameters`

### Changes for `api_endpoints`
| Column | Before | After | Reason |
|--------|--------|-------|--------|
| `namespace_id` | `UUID FK, not null` | **DROPPED** | Redundant — derive through `api_id → apis.namespace_id` |
| `user_id` | `String(255), not null` | **DROPPED** | Redundant — derive through `api_id → apis.user_id` |
| `path` | `String(500)` | `Text` | TEXT standard |
| `tag_name` | `String(255)` | `Text` | TEXT standard |
| `path_params` | — | `JSONB, not null, default=[]` | **NEW**: replaces endpoint_parameters table. Format: `[{"name": "user_id", "fieldId": "<uuid>"}]` |

### Changes for `endpoint_parameters`
| Action | Reason |
|--------|--------|
| **DELETE entire table** | Replaced by `path_params` JSONB column on `api_endpoints` |

### Impact
- **Heavy**. Major restructure of endpoint handling.
- `EndpointParameter` model deleted entirely.
- `EndpointService` rewritten — no more `_set_path_params` method, no more `selectinload(ApiEndpoint.path_params)`.
- Endpoint schemas simplified — `EndpointParameterSchema` replaced with simpler `PathParamSchema`.
- Endpoint router simplified — `_to_response` helper simplified.
- Namespace relationship removed from `ApiEndpoint`.
- Namespace model's `endpoints` relationship removed.
- Endpoint queries that filter by namespace must now join through `ApiModel`.

### Backend Prompt
```
CONTEXT:
Phase 5 of schema migration. We are simplifying `api_endpoints` by:
1. Removing `namespace_id` and `user_id` (redundant — derive through api)
2. Replacing the `endpoint_parameters` table with a `path_params` JSONB column
3. Converting remaining String columns to Text

This is the most impactful single phase. Take care with the service layer query changes.

We are editing existing migration files in-place (product not shipped).

FILES TO MODIFY:
1. src/api/models/database.py — ApiEndpoint, delete EndpointParameter, update Namespace
2. src/api/migrations/versions/4141ad7f2255_initial_schema.py — update api_endpoints, delete endpoint_parameters
3. src/api/schemas/endpoint.py — simplify schemas
4. src/api/services/endpoint.py — rewrite service
5. src/api/routers/endpoints.py — update router

CHANGES:

1. database.py:
   - ApiEndpoint model:
     - REMOVE `namespace_id` column and FK
     - REMOVE `user_id` column
     - REMOVE `namespace` relationship
     - REMOVE `path_params` relationship (to EndpointParameter)
     - ADD `path_params: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)`
       This stores: [{"name": "user_id", "fieldId": "<uuid-string>"}]
     - CHANGE `path` from `String(500)` to `Text`
     - CHANGE `tag_name` from `String(255)` to `Text`
     - Keep all object FK relationships (query_params_object_id, etc.)
     - Update docstring

   - DELETE `EndpointParameter` class entirely

   - Namespace model:
     - REMOVE the `endpoints` relationship (no longer has direct FK)

2. Initial migration (4141ad7f2255):
   - api_endpoints table:
     - Remove `namespace_id` column and its FK constraint
     - Remove `user_id` column
     - Remove indexes: ix_api_endpoints_namespace_id, ix_api_endpoints_user_id
     - Change `path` to sa.Text()
     - Change `tag_name` to sa.Text()
     - Add: `sa.Column("path_params", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]")`

   - DELETE entire endpoint_parameters table creation block
   - DELETE endpoint_parameters indexes
   - Update downgrade(): remove endpoint_parameters drops, remove namespace_id/user_id index drops from api_endpoints

3. schemas/endpoint.py:
   - Replace `EndpointParameterSchema` with a simpler schema:
     ```python
     class PathParamSchema(BaseModel):
         name: str = Field(..., examples=["user_id"])
         field_id: UUID = Field(..., alias="fieldId", examples=["00000000-0000-0000-0003-000000000001"])
     ```
   - ApiEndpointCreate:
     - REMOVE `namespace_id` field
     - Change `path_params` type from `list[EndpointParameterSchema]` to `list[PathParamSchema]`
   - ApiEndpointUpdate:
     - Change `path_params` type from `list[EndpointParameterSchema] | None` to `list[PathParamSchema] | None`
   - ApiEndpointResponse:
     - REMOVE `namespace_id` field
     - Change `path_params` type from `list[EndpointParameterSchema]` to `list[PathParamSchema]`

4. services/endpoint.py:
   - Remove import of EndpointParameter and EndpointParameterSchema
   - Import ApiModel (needed for namespace/user joins)

   - list_for_user:
     - Remove `selectinload(ApiEndpoint.path_params)`
     - Change the join: instead of `.join(Namespace)`, join through ApiModel:
       `.join(ApiModel, ApiEndpoint.api_id == ApiModel.id).join(Namespace, ApiModel.namespace_id == Namespace.id)`
     - For namespace_id filter: change `ApiEndpoint.namespace_id == namespace_id` to `ApiModel.namespace_id == namespace_id`

   - get_by_id_for_user:
     - Remove `selectinload(ApiEndpoint.path_params)`
     - Same join change as list_for_user

   - create_for_user:
     - Remove `namespace_id=data.namespace_id` from ApiEndpoint constructor
     - Remove `user_id=user_id` from constructor
     - Set `path_params` directly: `path_params=[p.model_dump(mode="json") for p in data.path_params]`
       (Convert PathParamSchema objects to dicts with camelCase keys for JSONB storage.
        Use model_dump(by_alias=True) to get {"name": ..., "fieldId": ...})
     - Remove the `await self._set_path_params(endpoint, data.path_params)` call

   - update_endpoint:
     - For path_params update: `endpoint.path_params = [p.model_dump(mode="json") for p in data.path_params]`
       instead of calling _set_path_params
     - Remove `namespace_id` update logic if any

   - DELETE `_set_path_params` method entirely

5. routers/endpoints.py:
   - Remove import of EndpointParameterSchema
   - Import PathParamSchema instead
   - Simplify `_to_response`: since path_params is now JSONB on the model, use:
     ```python
     def _to_response(endpoint) -> ApiEndpointResponse:
         return ApiEndpointResponse(
             id=endpoint.id,
             api_id=endpoint.api_id,
             method=endpoint.method,
             path=endpoint.path,
             description=endpoint.description,
             tag_name=endpoint.tag_name,
             path_params=[PathParamSchema(**p) for p in (endpoint.path_params or [])],
             query_params_object_id=endpoint.query_params_object_id,
             request_body_object_id=endpoint.request_body_object_id,
             response_body_object_id=endpoint.response_body_object_id,
             use_envelope=endpoint.use_envelope,
             response_shape=endpoint.response_shape,
         )
     ```
     (Note: no more namespace_id in response)
   - For ownership checks in update/delete: instead of `endpoint.user_id != user_id`, we need
     to check ownership through the API. Load the API or pass user_id check through service.
     Simplest approach: add a method to EndpointService that loads endpoint with its API and
     checks api.user_id. OR, since the endpoint was fetched with a user access check already
     (join through Namespace), and the namespace join ensures the user has access, the ownership
     check can be done by loading the parent API:
     ```python
     # In the router, after fetching endpoint:
     api = await api_service.get_by_id_for_user(endpoint.api_id, user_id)
     if api.user_id != user_id:
         raise HTTPException(...)
     ```
     Import and instantiate ApiService for this.

6. services/generation.py:
   - Update path params conversion in _convert_to_input_api:
     - endpoint.path_params is now a list of dicts [{"name": ..., "fieldId": ...}]
     - Convert to InputPathParam:
       ```python
       if endpoint.path_params:
           path_params = []
           for p in endpoint.path_params:
               # Look up the field to get its type
               field = fields_map.get(p["fieldId"])
               field_type_name = field.field_type.name if field else "str"
               path_params.append(InputPathParam(
                   name=p["name"],
                   type=_map_field_type(field_type_name),
                   description=field.description or "" if field else "",
               ))
       ```
     - This means we also need to fetch fields referenced by path params.
       Update `_fetch_objects` or add a separate step to collect fieldIds from path_params
       and include them in the fields_map.
     - In `_fetch_fields`, add path param field IDs:
       ```python
       # Also collect field IDs from path params
       for endpoint in api.endpoints:
           for p in (endpoint.path_params or []):
               if "fieldId" in p:
                   field_ids.add(p["fieldId"])
       ```
       Wait — _fetch_fields takes objects_map, not api. Restructure: pass api to _fetch_fields as well,
       or collect path param field IDs separately. Simplest: update _fetch_fields signature to also accept api.

Run `make test` after changes.

FINAL STEP: After all backend changes are verified, write a detailed frontend prompt for this phase. The frontend prompt must:
- Be a self-contained instruction for a separate Claude agent working on the frontend repo at /Users/evgesha/Documents/Projects/median-code-frontend
- List the exact API changes: namespaceId removed from endpoint create/update/response, path_params schema changed from {id, name, type, description, required} to {name, fieldId}
- Instruct removing namespaceId from endpoint forms and interfaces
- Instruct replacing the path params UI: instead of manual type/description/required inputs, use a name field + a field selector dropdown (referencing existing fields by UUID)
- Include the before/after shape of the endpoint API request/response
- The frontend agent should search the codebase for all usages of namespaceId on endpoints and EndpointParameterSchema before making changes
Output the frontend prompt in a clearly marked section at the end of your response.
```

---

## Phase 6: `field_validators` (complete replacement) + `field_validator_associations` (new)

### Current `field_validators` (codebase)
```
id UUID PK
field_id UUID FK → fields.id (CASCADE)
name String(255)
params JSONB nullable
```
This is a join table: "field X uses constraint named Y with params Z."

### Target `field_validators` (new standalone entity)
```
id UUID PK
namespace_id UUID FK → namespaces.id
user_id TEXT nullable
function_name TEXT
mode TEXT
function_body TEXT
description TEXT
```
This is a custom validator function definition (user-written Python validation logic).

### Target `field_validator_associations` (new join table)
```
id UUID PK
validator_id UUID FK → field_validators.id
field_id UUID FK → fields.id
```

### Impact
- **CRITICAL**. The old `field_validators` was a join table between fields and constraints (by name). The new `field_validators` is a completely different entity — custom validator functions.
- The old join-table functionality (tracking which constraints are applied to which fields with what params) is now handled by `constraint_field_values_associations` (Phase 8).
- All existing code that uses `FieldValidator` model needs to be rewritten or removed.
- The field creation/update flow that adds validators to fields needs to be reworked.

### Backend Prompt
```
CONTEXT:
Phase 6 of schema migration. This is a COMPLETE REPLACEMENT of the `field_validators` table. The current table is a join table tracking "field X uses constraint Y with params Z." The new table is a standalone entity for user-defined custom validator functions.

Additionally, we are creating a new `field_validator_associations` join table.

IMPORTANT: The old field_validators join-table functionality (constraint application) will be handled by `constraint_field_values_associations` in a later phase. For now, we are just restructuring the tables.

FILES TO MODIFY:
1. src/api/models/database.py — replace FieldValidator, add FieldValidatorAssociation
2. src/api/migrations/versions/4141ad7f2255_initial_schema.py — replace field_validators table, add field_validator_associations
3. src/api/schemas/field.py — remove validator-related fields from FieldResponse for now
4. src/api/services/field.py — remove validator handling from field create/update
5. src/api/services/generation.py — temporarily remove validator conversion (will be re-added when constraint_field_values_associations is implemented)
6. src/api/routers/fields.py — remove validator-related logic
7. src/api/routers/constraints.py — update fields_using_constraint logic (the query against old field_validators table)

CHANGES:

1. database.py:
   - REPLACE FieldValidator class entirely:
     ```python
     class FieldValidatorModel(Base):
         """Custom field validator function definition.

         User-defined Python validation functions that can be attached to fields.
         """
         __tablename__ = "field_validators"

         id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=generate_uuid)
         namespace_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("namespaces.id"), nullable=False, index=True)
         user_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
         function_name: Mapped[str] = mapped_column(Text, nullable=False)
         mode: Mapped[str] = mapped_column(Text, nullable=False)  # "before", "after", "wrap", "plain"
         function_body: Mapped[str] = mapped_column(Text, nullable=False)
         description: Mapped[str | None] = mapped_column(Text, nullable=True)

         # Relationships
         namespace: Mapped["Namespace"] = relationship()
         field_associations: Mapped[list["FieldValidatorAssociation"]] = relationship(
             back_populates="validator", cascade="all, delete-orphan"
         )
     ```

   - ADD new class:
     ```python
     class FieldValidatorAssociation(Base):
         """Association between a custom field validator and a field."""
         __tablename__ = "field_validator_associations"

         id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=generate_uuid)
         validator_id: Mapped[UUID] = mapped_column(
             PgUUID(as_uuid=True), ForeignKey("field_validators.id", ondelete="CASCADE"), nullable=False, index=True
         )
         field_id: Mapped[UUID] = mapped_column(
             PgUUID(as_uuid=True), ForeignKey("fields.id", ondelete="CASCADE"), nullable=False, index=True
         )

         # Relationships
         validator: Mapped["FieldValidatorModel"] = relationship(back_populates="field_associations")
         field: Mapped["FieldModel"] = relationship()
     ```

   - FieldModel:
     - REMOVE: `validators` relationship (old FieldValidator join)
     - This will be re-added later when we wire up constraint_field_values_associations

   - Namespace model:
     - ADD: `field_validators: Mapped[list["FieldValidatorModel"]] = relationship(back_populates="namespace", cascade="all, delete-orphan")`
       (if you want namespace to manage these)

2. Initial migration (4141ad7f2255):
   - REPLACE field_validators table:
     - New columns: id, namespace_id (FK → namespaces.id), user_id (Text nullable), function_name (Text), mode (Text), function_body (Text), description (Text nullable)
     - Add indexes on namespace_id, user_id
   - ADD field_validator_associations table:
     - Columns: id, validator_id (FK → field_validators.id CASCADE), field_id (FK → fields.id CASCADE)
     - Add indexes on validator_id, field_id

3. schemas/field.py:
   - Check current FieldCreate/FieldUpdate/FieldResponse schemas
   - If they reference validators, remove those references for now
   - Validator attachment to fields will be re-implemented in a later phase

4. services/field.py:
   - Remove any code that creates/manages FieldValidator instances during field create/update
   - Remove selectinload(FieldModel.validators) from queries

5. services/generation.py:
   - The code currently does:
     ```python
     validators = [InputValidator(name=v.name, params=v.params) for v in field.validators]
     ```
   - Remove this for now. Set validators=[] in InputField construction.
   - Remove selectinload(FieldModel.validators) from _fetch_fields query.
   - TODO comment: "Constraint application will be re-added with constraint_field_values_associations"

6. routers/constraints.py (was validators.py):
   - The `get_fields_by_validator` function queries the OLD field_validators table by name.
   - This logic no longer applies (old table is gone).
   - Remove `get_fields_by_validator` function.
   - Remove `used_in_fields` and `fields_using_validator` from constraint response construction.
   - These usage statistics will be re-implemented when constraint_field_values_associations exists.

Run `make test` after changes.

FINAL STEP: After all backend changes are verified, write a detailed frontend prompt for this phase. The frontend prompt must:
- Be a self-contained instruction for a separate Claude agent working on the frontend repo at /Users/evgesha/Documents/Projects/median-code-frontend
- Explain that field_validators is now a completely different entity (custom validator functions, not constraint applications)
- Instruct removing any validator attachment UI from field create/edit forms (temporarily — will return in a different form)
- Instruct removing "used in fields" / "fields using validator" display from constraints list (temporarily)
- Note that these features will return when constraint_field_values_associations is wired up
- The frontend agent should search the codebase for all usages of field validators before making changes
Output the frontend prompt in a clearly marked section at the end of your response.
```

---

## Phase 7: `model_validators` + `object_model_validator_associations`

### New tables (do not exist in codebase yet)

**`model_validators`** — Custom model-level validator function definitions (Pydantic `@model_validator`).
```
id UUID PK
namespace_id UUID FK → namespaces.id
user_id TEXT nullable
function_name TEXT
mode TEXT          -- "before", "after", "wrap"
function_body TEXT
description TEXT
```

**`object_model_validator_associations`** — Links model validators to objects.
```
id UUID PK
validator_id UUID FK → model_validators.id
object_id UUID FK → objects.id
```

### Impact
- **Additive only**. No existing code changes — just new models, migration entries, schemas, and potentially a new router.
- No frontend impact until the UI is built for this feature.

### Backend Prompt
```
CONTEXT:
Phase 7 of schema migration. Adding two new tables: `model_validators` (custom model-level validator functions) and `object_model_validator_associations` (links validators to objects). These are new entities with no existing code.

FILES TO MODIFY:
1. src/api/models/database.py — add ModelValidatorModel, ObjectModelValidatorAssociation
2. src/api/migrations/versions/4141ad7f2255_initial_schema.py — add both tables

CHANGES:

1. database.py — ADD:
   ```python
   class ModelValidatorModel(Base):
       """Custom model validator function definition.

       User-defined Python validation functions that run on entire Pydantic models.
       """
       __tablename__ = "model_validators"

       id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=generate_uuid)
       namespace_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("namespaces.id"), nullable=False, index=True)
       user_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
       function_name: Mapped[str] = mapped_column(Text, nullable=False)
       mode: Mapped[str] = mapped_column(Text, nullable=False)  # "before", "after", "wrap"
       function_body: Mapped[str] = mapped_column(Text, nullable=False)
       description: Mapped[str | None] = mapped_column(Text, nullable=True)

       # Relationships
       namespace: Mapped["Namespace"] = relationship()
       object_associations: Mapped[list["ObjectModelValidatorAssociation"]] = relationship(
           back_populates="validator", cascade="all, delete-orphan"
       )


   class ObjectModelValidatorAssociation(Base):
       """Association between a model validator and an object."""
       __tablename__ = "object_model_validator_associations"

       id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=generate_uuid)
       validator_id: Mapped[UUID] = mapped_column(
           PgUUID(as_uuid=True), ForeignKey("model_validators.id", ondelete="CASCADE"), nullable=False, index=True
       )
       object_id: Mapped[UUID] = mapped_column(
           PgUUID(as_uuid=True), ForeignKey("objects.id", ondelete="CASCADE"), nullable=False, index=True
       )

       # Relationships
       validator: Mapped["ModelValidatorModel"] = relationship(back_populates="object_associations")
       object: Mapped["ObjectDefinition"] = relationship()
   ```

2. Initial migration — ADD after object_field_associations table:
   - model_validators table with all columns and indexes
   - object_model_validator_associations table with FKs and indexes
   - Update downgrade() to drop both tables

DO NOT create schemas, services, or routers for these yet — they are structural placeholders.
The schemas and API endpoints for managing model validators will be built when the feature is needed.

Run `make test` after changes.

FINAL STEP: No frontend changes needed for this phase (new backend-only tables with no API endpoints yet). Confirm this in your summary.
```

---

## Phase 8: `constraint_field_values_associations`

### New table (does not exist in codebase yet)

**`constraint_field_values_associations`** — Links constraints to fields with a value parameter.
This is the replacement for the old `field_validators` join-table functionality.
```
id UUID PK
constraint_id UUID FK → constraints.id
field_id UUID FK → fields.id
value TEXT            -- the parameter value (e.g., "255" for max_length=255)
```

### Impact
- **Additive**. New table that enables constraint application to fields.
- After this phase, the system can track "field X has constraint max_length with value 255."
- Eventually, generation service and field CRUD should use this instead of the old field_validators.

### Backend Prompt
```
CONTEXT:
Phase 8 of schema migration. Adding `constraint_field_values_associations` table. This replaces the old field_validators join-table functionality. It links constraints (max_length, min_length, gt, etc.) to fields with a parameter value.

Example: field "email" has constraint "max_length" with value "255"
→ constraint_field_values_associations row: {constraint_id: <max_length_uuid>, field_id: <email_uuid>, value: "255"}

FILES TO MODIFY:
1. src/api/models/database.py — add ConstraintFieldValueAssociation
2. src/api/migrations/versions/4141ad7f2255_initial_schema.py — add table

CHANGES:

1. database.py — ADD:
   ```python
   class ConstraintFieldValueAssociation(Base):
       """Association between a constraint and a field, with parameter value.

       Tracks which constraints are applied to which fields and with what value.
       Example: max_length constraint applied to email field with value "255".
       """
       __tablename__ = "constraint_field_values_associations"

       id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=generate_uuid)
       constraint_id: Mapped[UUID] = mapped_column(
           PgUUID(as_uuid=True), ForeignKey("constraints.id", ondelete="CASCADE"), nullable=False, index=True
       )
       field_id: Mapped[UUID] = mapped_column(
           PgUUID(as_uuid=True), ForeignKey("fields.id", ondelete="CASCADE"), nullable=False, index=True
       )
       value: Mapped[str | None] = mapped_column(Text, nullable=True)  # null for constraints that take no params

       # Relationships
       constraint: Mapped["ConstraintModel"] = relationship()
       field: Mapped["FieldModel"] = relationship()
   ```

   - Optionally add reverse relationship to FieldModel:
     ```python
     constraint_values: Mapped[list["ConstraintFieldValueAssociation"]] = relationship(
         back_populates="field", cascade="all, delete-orphan"
     )
     ```

2. Initial migration — ADD table:
   - constraint_field_values_associations with all columns, FKs (CASCADE), and indexes
   - Update downgrade()

DO NOT wire this into field CRUD, generation service, or constraints router yet.
That integration should be a follow-up task after all structural phases are complete.

Run `make test` after changes.

FINAL STEP: No frontend changes needed for this phase (new backend-only table with no API endpoints yet). Confirm this in your summary.
```

---

## Post-Migration Checklist

After ALL phases are complete:

1. **Drop and recreate the database**:
   ```bash
   # If using Railway:
   railway run alembic downgrade base
   railway run alembic upgrade head
   # Or drop/recreate the database entirely
   ```

2. **Run full test suite**: `make test`

3. **Verify seed data**: Ensure types and constraints are seeded correctly with new column structures.

4. **Integration tasks** (separate from schema migration):
   - [ ] Wire `constraint_field_values_associations` into field CRUD (create/update fields with constraints)
   - [ ] Wire `constraint_field_values_associations` into generation service (read applied constraints for code gen)
   - [ ] Wire `constraint_field_values_associations` into constraints router (show usage stats)
   - [ ] Build field_validators CRUD endpoints (custom validator management)
   - [ ] Build model_validators CRUD endpoints (custom model validator management)
   - [ ] Update generation service to use path_params field references for type resolution

---

## Summary Table

| Phase | Table(s) | Change Type | Impact |
|-------|----------|-------------|--------|
| 1 | namespaces + fields + objects | TEXT normalization | Minimal |
| 2 | types | Major restructure | Heavy |
| 3 | validators → constraints | Rename + restructure | Heavy |
| 4 | apis | Drop tags + TEXT | Medium |
| 5 | api_endpoints + endpoint_parameters | Restructure + delete | Heavy |
| 6 | field_validators + field_validator_associations | Complete replacement + new | Critical |
| 7 | model_validators + object_model_validator_associations | New tables | Additive |
| 8 | constraint_field_values_associations | New table | Additive |
