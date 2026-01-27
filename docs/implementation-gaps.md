# Backend Implementation Gaps

This document tracks remaining implementation gaps against the API specification at `api-spec.yaml`.

---

## 1. Database Migrations

Alembic migrations are not set up. Required for:
- Initial schema creation
- Future schema changes

**To implement:**
```bash
poetry add alembic
alembic init migrations
alembic revision --autogenerate -m "Initial schema"
```

---

## 2. Integration Tests

No test coverage exists for the API service. Tests needed for:
- All CRUD endpoints (namespaces, APIs, fields, objects, tags, endpoints)
- Authentication flows (valid JWT, expired JWT, missing token)
- Code generation endpoint (`/apis/{id}/generate`)
- Cascade delete behavior (API → endpoints/tags)
- Entity-in-use protection (prevent delete of fields used in objects, etc.)
- Namespace locking (prevent modification of global namespace)

---

## 3. Global Namespace Seeding

The global namespace (`namespace-global`) is not created automatically. On application startup:
- Create global namespace if it doesn't exist
- Set `locked=True`
- Set `user_id=None` (accessible to all users)

**Location:** Add to `lifespan` context manager in `src/api/main.py`

---

## 4. `usedInApis` Computed Field

The API spec requires `usedInApis` array in Field and Object responses. This field should be computed by querying:
- **Fields:** Which objects contain this field → which endpoints use those objects
- **Objects:** Which endpoints reference this object (query params, request body, response body)

**Current state:** Field returns empty array; needs query logic in services.

---

## 5. Error Response Consistency

Verify all error responses match the spec format:
```json
{"detail": "Error message here"}
```

Areas to audit:
- Validation errors (Pydantic)
- Database constraint violations
- Authentication failures
- Not found responses

---

## 6. OpenAPI Spec Alignment

Verify generated OpenAPI matches `api-spec.yaml`:
- Operation IDs match spec
- Response schemas match spec
- Query parameter names use camelCase
- Request body schemas match spec

**To verify:**
```bash
# Start server and compare
curl http://localhost:8000/openapi.json | diff - docs/api-spec.yaml
```
