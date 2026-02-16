# Testing Strategy

This document defines the testing taxonomy, directory structure, and expectations for the Median Code Backend project.

## Test Categories

### Unit Tests (`pytest.mark.unit`)

Tests that verify a single function or class in complete isolation. No database, no HTTP, no filesystem I/O, no network calls.

**Should cover:**
- Pure functions (transformers, extractors, placeholders, utilities)
- Pydantic schema validation
- Business logic that does not require a database session

**Should NOT cover:**
- Anything requiring a database connection
- Anything requiring an HTTP request/response cycle

**Speed:** Fast. No infrastructure required.

---

### Integration Tests (`pytest.mark.integration`)

Tests that verify service-layer business logic with a real database. Services are instantiated directly (not through HTTP). Authentication is bypassed. Tests use real async database sessions.

**Should cover:**
- Service CRUD operations (create, read, update, delete)
- Business rules (locked namespace enforcement, cascade deletes, user isolation)
- Cross-service interactions (e.g., provisioning + field creation)
- Database constraint enforcement (unique indexes, foreign keys)
- Correct SQLAlchemy query behavior (joins, OR clauses, eager loading)

**Should NOT cover:**
- HTTP request/response serialization
- Authentication/authorization flow
- Middleware behavior
- Route path correctness

**Speed:** Medium. Requires a running PostgreSQL instance (Docker).

---

### Codegen Tests (`pytest.mark.codegen`)

Tests that verify the `api_craft` code generation pipeline end-to-end: load a YAML spec, generate a complete FastAPI project, dynamically import and boot it, then make HTTP requests against the generated app to verify correctness.

**Should cover:**
- Generated code is syntactically valid (imports succeed)
- Generated Pydantic models enforce validators correctly
- Generated FastAPI routes respond with correct shapes
- Different spec configurations produce correct output

**Should NOT cover:**
- The `api` service endpoints
- Database interactions
- Authentication

**Speed:** Medium. No database, but generates files to disk and boots an app.

---

### API Tests (`pytest.mark.api`) -- Future

Tests that verify HTTP endpoint behavior by making requests through `TestClient` against the `api` FastAPI application. Authentication is overridden via dependency injection. These verify the full backend request/response cycle: routing, dependency injection, serialization, error formatting, and status codes.

This category does not exist yet. When implemented, it should cover:
- Every router endpoint (correct status codes, response shapes)
- Request validation (422 for invalid input)
- Authentication enforcement (401 without token)
- Authorization (403/404 for resources owned by other users)
- Error response format consistency

---

## Why Not "E2E" in the Backend?

"E2E" (end-to-end) in the industry most commonly refers to browser-based tests that verify the full user journey: frontend UI through API to database and back. For a backend-only service, the equivalent is **API tests** (HTTP in, HTTP out). We use the term "API tests" to avoid confusion with frontend E2E tests (Playwright/Cypress) that live in the frontend repository.

The `api_craft` generation pipeline tests were previously labeled `e2e` because they test the full generation pipeline. They are now labeled `codegen` to accurately describe what they verify.

---

## Directory Structure

```
tests/
├── conftest.py                          # Shared fixtures (DB sessions, user provisioning)
├── test_api_craft/                      # Tests for the code generation library
│   ├── __init__.py
│   ├── conftest.py                      # api_craft fixtures (YAML loading, TestClient for generated apps)
│   ├── test_codegen.py                  # [codegen] Generation pipeline tests
│   └── test_placeholders.py             # [unit] Placeholder generation tests
├── test_api/                            # Tests for the FastAPI API service
│   ├── __init__.py
│   └── test_services/                   # [integration] Service-layer with real DB
│       ├── __init__.py
│       ├── test_namespace.py
│       ├── test_field.py
│       ├── test_type.py
│       ├── test_field_constraint.py
│       └── test_user_provisioning.py
└── specs/                               # Test input specifications
    └── items_api.yaml
```

---

## Running Tests

```bash
# All tests (excludes manual)
make test

# By category
poetry run pytest -m unit              # Fast, no DB needed
poetry run pytest -m integration       # Needs PostgreSQL (Docker)
poetry run pytest -m codegen           # No DB, tests generation pipeline

# Quick smoke test (codegen only)
make test-quick

# Single test
poetry run pytest tests/test_api/test_services/test_namespace.py::test_create_namespace -v
```

---

## Pytest Markers

Defined in `pyproject.toml`:

| Marker | Description | Requires DB |
|--------|-------------|-------------|
| `unit` | Pure logic tests, no external dependencies | No |
| `integration` | Service + database tests | Yes |
| `codegen` | Code generation pipeline tests | No |
| `api` | HTTP endpoint tests (future) | Yes |
| `manual` | Generate output for manual inspection | No |

---

## Conventions

1. **One marker per file.** Set `pytestmark = pytest.mark.<category>` at module level.
2. **Fixtures go in `conftest.py`** at the appropriate level (root for shared, subdirectory for scoped).
3. **Integration tests use services directly.** Instantiate the service class with a real `db_session`, not via HTTP.
4. **Cleanup after yourself.** Use fixture teardown (after `yield`) to delete test data.
5. **Test user IDs** are defined in `conftest.py` (`TEST_USER_ID`). Never use real Clerk user IDs.
6. **Format before committing.** Run `poetry run black src/ tests/` after any test changes.
