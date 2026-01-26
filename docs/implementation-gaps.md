# Backend Implementation Gaps Analysis

This document compares the current backend implementation against the API specification at `api-spec.yaml`.

## Executive Summary

The current backend (`median_code_backend`) is a **code generation library** that transforms JSON API specifications into FastAPI project scaffolds. However, the API specification defines a **full REST API service** with entity management (CRUD operations) and Clerk JWT authentication. **The backend does not currently implement any HTTP endpoints** - it is purely a local code generation tool.

---

## Current Implementation Status

### What Exists

The backend contains a code generation library (`median_code_backend`) with the following components:

| Component | File | Purpose |
|-----------|------|---------|
| `main.py` | `src/median_code_backend/main.py` | `APIGenerator` class and `generate_fastapi()` function |
| `models/input.py` | `src/median_code_backend/models/input.py` | Input Pydantic models for code generation |
| `models/template.py` | `src/median_code_backend/models/template.py` | Template-ready Pydantic models |
| `models/types.py` | `src/median_code_backend/models/types.py` | Custom `Name` type with case conversions |
| `models/validators.py` | `src/median_code_backend/models/validators.py` | Validation helpers for input models |
| `transformers.py` | `src/median_code_backend/transformers.py` | Input-to-template transformation logic |
| `extractors.py` | `src/median_code_backend/extractors.py` | Component extraction from template API |
| `renderers.py` | `src/median_code_backend/renderers.py` | Mako template rendering |
| `placeholders.py` | `src/median_code_backend/placeholders.py` | Placeholder value generation |
| `utils.py` | `src/median_code_backend/utils.py` | File I/O and string utilities |
| `templates/*.mako` | `src/median_code_backend/templates/` | Mako templates for code generation |

### What Does NOT Exist

1. **No FastAPI HTTP Application** - No `app = FastAPI()` in the codebase
2. **No REST API Endpoints** - No routers or endpoint handlers
3. **No Database Layer** - No ORM, no database models, no migrations
4. **No Authentication Middleware** - No Clerk JWT verification
5. **No Entity CRUD Operations** - No persistence layer for any entities

---

## Required Endpoints vs Implementation Status

### Namespaces (`/namespaces`)

| Method | Endpoint | Operation ID | Status |
|--------|----------|--------------|--------|
| GET | `/namespaces` | `listNamespaces` | NOT IMPLEMENTED |
| POST | `/namespaces` | `createNamespace` | NOT IMPLEMENTED |
| GET | `/namespaces/{id}` | `getNamespace` | NOT IMPLEMENTED |
| PUT | `/namespaces/{id}` | `updateNamespace` | NOT IMPLEMENTED |
| DELETE | `/namespaces/{id}` | `deleteNamespace` | NOT IMPLEMENTED |

**Schema Required:** `Namespace` (id, name, description, locked)

---

### APIs (`/apis`)

| Method | Endpoint | Operation ID | Status |
|--------|----------|--------------|--------|
| GET | `/apis` | `listApis` | NOT IMPLEMENTED |
| POST | `/apis` | `createApi` | NOT IMPLEMENTED |
| GET | `/apis/{id}` | `getApi` | NOT IMPLEMENTED |
| PUT | `/apis/{id}` | `updateApi` | NOT IMPLEMENTED |
| DELETE | `/apis/{id}` | `deleteApi` | NOT IMPLEMENTED |
| POST | `/apis/{id}/generate` | `generateApiCode` | **PARTIALLY EXISTS** |

**Schema Required:** `Api` (id, namespaceId, title, version, description, baseUrl, serverUrl, createdAt, updatedAt)

**Notes:**
- The code generation logic exists in `median_code_backend.main.generate_fastapi()` but is not exposed via HTTP
- The existing generation expects `InputAPI` format, not the new `Api` schema
- Needs adapter to convert persisted entities into `InputAPI` for generation

---

### Types (`/types`)

| Method | Endpoint | Operation ID | Status |
|--------|----------|--------------|--------|
| GET | `/types` | `listTypes` | NOT IMPLEMENTED |

**Schema Required:** `Type` (name, category, pythonType, description, validatorCategories)

**Notes:**
- Types are read-only in the spec
- The backend has `SUPPORTED_TYPE_IDENTIFIERS` in `validators.py` but no Type entity model
- Need to serve static type definitions (str, int, float, bool, datetime, uuid)

---

### Validators (`/validators`)

| Method | Endpoint | Operation ID | Status |
|--------|----------|--------------|--------|
| GET | `/validators` | `listValidators` | NOT IMPLEMENTED |

**Schema Required:** `ValidatorBase` (name, namespaceId, type, description, category, parameterType, exampleUsage, pydanticDocsUrl)

**Notes:**
- Validators are read-only in the spec
- Need to define and serve validator definitions for field validation

---

### Fields (`/fields`)

| Method | Endpoint | Operation ID | Status |
|--------|----------|--------------|--------|
| GET | `/fields` | `listFields` | NOT IMPLEMENTED |
| POST | `/fields` | `createField` | NOT IMPLEMENTED |
| GET | `/fields/{id}` | `getField` | NOT IMPLEMENTED |
| PUT | `/fields/{id}` | `updateField` | NOT IMPLEMENTED |
| DELETE | `/fields/{id}` | `deleteField` | NOT IMPLEMENTED |

**Schema Required:** `Field` (id, namespaceId, name, type, description, defaultValue, validators, usedInApis)

**Notes:**
- `InputField` in current backend has different schema (type, name, required)
- New schema adds: id, namespaceId, description, defaultValue, validators array, usedInApis tracking

---

### Objects (`/objects`)

| Method | Endpoint | Operation ID | Status |
|--------|----------|--------------|--------|
| GET | `/objects` | `listObjects` | NOT IMPLEMENTED |
| POST | `/objects` | `createObject` | NOT IMPLEMENTED |
| GET | `/objects/{id}` | `getObject` | NOT IMPLEMENTED |
| PUT | `/objects/{id}` | `updateObject` | NOT IMPLEMENTED |
| DELETE | `/objects/{id}` | `deleteObject` | NOT IMPLEMENTED |

**Schema Required:** `ObjectDefinition` (id, namespaceId, name, description, fields[], usedInApis)

**Notes:**
- `InputModel` in current backend has: name, fields[]
- New schema uses `ObjectFieldReference` (fieldId, required) instead of inline field definitions
- This is a significant architectural difference - objects reference fields by ID

---

### Tags (`/tags`)

| Method | Endpoint | Operation ID | Status |
|--------|----------|--------------|--------|
| GET | `/tags` | `listTags` | NOT IMPLEMENTED |
| POST | `/tags` | `createTag` | NOT IMPLEMENTED |
| GET | `/tags/{id}` | `getTag` | NOT IMPLEMENTED |
| PUT | `/tags/{id}` | `updateTag` | NOT IMPLEMENTED |
| DELETE | `/tags/{id}` | `deleteTag` | NOT IMPLEMENTED |

**Schema Required:** `EndpointTag` (id, namespaceId, apiId, name, description)

**Notes:**
- Tags are new entities not present in current backend
- Used for OpenAPI grouping of endpoints

---

### Endpoints (`/endpoints`)

| Method | Endpoint | Operation ID | Status |
|--------|----------|--------------|--------|
| GET | `/endpoints` | `listEndpoints` | NOT IMPLEMENTED |
| POST | `/endpoints` | `createEndpoint` | NOT IMPLEMENTED |
| GET | `/endpoints/{id}` | `getEndpoint` | NOT IMPLEMENTED |
| PUT | `/endpoints/{id}` | `updateEndpoint` | NOT IMPLEMENTED |
| DELETE | `/endpoints/{id}` | `deleteEndpoint` | NOT IMPLEMENTED |

**Schema Required:** `ApiEndpoint` (id, namespaceId, apiId, method, path, description, tagId, pathParams[], queryParamsObjectId, requestBodyObjectId, responseBodyObjectId, useEnvelope, responseShape, expanded)

**Notes:**
- `InputView` in current backend has: name, path, method, tag, response, request, query_params[], path_params[]
- New schema references objects by ID instead of by name
- Adds envelope and responseShape concepts

---

## Schema Discrepancies

### 1. Field Definition

**Current (`InputField`):**
```python
class InputField(BaseModel):
    type: str
    name: str
    required: bool = False
```

**Spec (`Field`):**
```yaml
Field:
  required: [id, namespaceId, name, type, validators, usedInApis]
  properties:
    id: string
    namespaceId: string
    name: string
    type: enum [str, int, float, bool, datetime, uuid]
    description: string
    defaultValue: string
    validators: array of FieldValidator
    usedInApis: array of string
```

**Gap:** Current implementation embeds field definitions in objects. Spec requires fields as standalone entities referenced by ID.

---

### 2. Object Definition

**Current (`InputModel`):**
```python
class InputModel(BaseModel):
    name: Name
    fields: list[InputField]
```

**Spec (`ObjectDefinition`):**
```yaml
ObjectDefinition:
  required: [id, namespaceId, name, fields, usedInApis]
  properties:
    id: string
    namespaceId: string
    name: string
    description: string
    fields: array of ObjectFieldReference
    usedInApis: array of string
```

**Gap:** Current implementation uses inline field definitions. Spec uses field references (fieldId + required flag).

---

### 3. Endpoint Definition

**Current (`InputView`):**
```python
class InputView(BaseModel):
    name: Name
    path: str
    method: str
    tag: str | None = None
    response: str | None = None
    request: str | None = None
    query_params: list[InputQueryParam] | None = None
    path_params: list[InputPathParam] | None = None
```

**Spec (`ApiEndpoint`):**
```yaml
ApiEndpoint:
  required: [id, namespaceId, apiId, method, path, description, pathParams, useEnvelope, responseShape]
  properties:
    id: string
    namespaceId: string
    apiId: string
    method: enum [GET, POST, PUT, PATCH, DELETE]
    path: string
    description: string
    tagId: string (nullable)
    pathParams: array of EndpointParameter
    queryParamsObjectId: string (nullable)
    requestBodyObjectId: string (nullable)
    responseBodyObjectId: string (nullable)
    useEnvelope: boolean
    responseShape: enum [object, list]
```

**Gaps:**
- Spec uses object IDs for query params, request body, response body
- Spec adds `useEnvelope` and `responseShape` for response formatting
- Spec uses `tagId` reference instead of tag name string

---

## Authentication Gaps

**Spec Requirement:**
- All endpoints require `BearerAuth` (Clerk JWT)
- Authentication scheme: `type: http`, `scheme: bearer`, `bearerFormat: JWT`

**Current Implementation:**
- No authentication middleware
- No Clerk integration
- No JWT verification

**Required:**
- Add Clerk Python SDK or manual JWT verification
- Add authentication dependency to all routes
- Extract user context from JWT for multi-tenancy

---

## Database/Persistence Gaps

**Spec Requirement:**
- CRUD operations on all entities
- Entity relationships (namespace -> apis -> endpoints/tags)
- Cascade delete behavior (delete API -> delete endpoints and tags)
- Reference integrity checks (cannot delete field if used in objects)

**Current Implementation:**
- No database
- No ORM (SQLAlchemy, Tortoise, etc.)
- No entity storage

**Required:**
- Database selection (PostgreSQL recommended)
- ORM setup and entity models
- Migration system (Alembic)
- Repository pattern for data access

---

## Sequential Implementation Steps

### Phase 1: Foundation

1. **Add FastAPI Application**
   - Create `src/median_code_backend/server/main.py` with FastAPI app
   - Configure CORS, middleware, error handlers
   - Add health check endpoint

2. **Add Database Layer**
   - Choose ORM (SQLAlchemy 2.0 recommended)
   - Create database models for all entities
   - Set up Alembic migrations
   - Configure database connection (async recommended)

3. **Add Clerk Authentication**
   - Install Clerk Python SDK or use PyJWT
   - Create authentication dependency
   - Configure JWKS validation
   - Extract user ID from token

### Phase 2: Entity CRUD

4. **Implement Namespaces**
   - DB model with (id, name, description, locked, user_id)
   - Router with all CRUD endpoints
   - Business logic for lock checking
   - Seed global namespace on startup

5. **Implement Types** (read-only)
   - Define static type definitions
   - GET endpoint to return types

6. **Implement Validators** (read-only)
   - Define validator definitions
   - GET endpoint with namespace filter

7. **Implement Fields**
   - DB model matching spec schema
   - Full CRUD with namespace filtering
   - Validation for type enum
   - Track `usedInApis` on query

8. **Implement Objects**
   - DB model with field references (many-to-many)
   - Full CRUD with namespace filtering
   - Validate field references exist
   - Track `usedInApis` on query

9. **Implement APIs**
   - DB model with timestamps
   - Full CRUD with namespace filtering
   - Cascade delete for tags and endpoints

10. **Implement Tags**
    - DB model with API reference
    - Full CRUD with namespace filtering
    - Check for endpoint usage on delete

11. **Implement Endpoints**
    - DB model with all references
    - Full CRUD with namespace filtering
    - Validate path parameter consistency
    - Validate object references exist

### Phase 3: Code Generation Integration

12. **Adapt Generation Endpoint**
    - Create `/apis/{id}/generate` endpoint
    - Fetch API with all related entities
    - Transform entities to `InputAPI` format
    - Call existing `generate_fastapi()` logic
    - Create zip in memory and stream response

### Phase 4: Testing & Documentation

13. **Add Integration Tests**
    - Test all CRUD operations
    - Test authentication flows
    - Test generation endpoint

14. **Add OpenAPI Documentation**
    - Ensure FastAPI generates matching spec
    - Add response examples

---

## Estimated Effort

| Phase | Components | Estimated Time |
|-------|------------|----------------|
| Phase 1 | Foundation (FastAPI, DB, Auth) | 2-3 days |
| Phase 2 | Entity CRUD (8 entity types) | 5-7 days |
| Phase 3 | Code Generation Integration | 1-2 days |
| Phase 4 | Testing & Documentation | 2-3 days |
| **Total** | | **10-15 days** |

---

## File Structure Recommendation

```
src/
  median_code_backend/
    # Existing code generation
    main.py
    transformers.py
    extractors.py
    renderers.py
    placeholders.py
    utils.py
    models/
      input.py
      template.py
      types.py
      validators.py
    templates/
      *.mako

    # New API server
    server/
      __init__.py
      main.py           # FastAPI app
      config.py         # Settings, environment
      dependencies.py   # Auth, DB session

    # Database layer
    db/
      __init__.py
      base.py           # SQLAlchemy base
      session.py        # Database connection
      models/
        __init__.py
        namespace.py
        api.py
        field.py
        object.py
        tag.py
        endpoint.py

    # API routes
    routes/
      __init__.py
      namespaces.py
      apis.py
      types.py
      validators.py
      fields.py
      objects.py
      tags.py
      endpoints.py

    # Business logic
    services/
      __init__.py
      namespace_service.py
      api_service.py
      field_service.py
      object_service.py
      tag_service.py
      endpoint_service.py
      generation_service.py

    # Pydantic schemas for API
    schemas/
      __init__.py
      namespace.py
      api.py
      field.py
      object.py
      tag.py
      endpoint.py
      common.py
```

---

## Conclusion

The current backend is a solid foundation for **code generation** but requires significant work to become the **REST API service** defined in the specification. The core generation logic can be reused, but the entire HTTP layer, database persistence, and authentication need to be built from scratch.
