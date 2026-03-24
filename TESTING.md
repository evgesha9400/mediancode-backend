# Testing Strategy

This document defines the testing taxonomy, directory structure, and expectations for the Median Code Backend project.

## Test Categories

### Unit Tests (`pytest.mark.unit`)

Tests that verify a single function or class in complete isolation. No database, no HTTP, no filesystem I/O, no network calls.

**Should cover:**
- Pure functions (transformers, extractors, placeholders, utilities)
- Pydantic schema validation
- Business logic that does not require a database session

**Speed:** Fast. No infrastructure required.

---

### Integration Tests (`pytest.mark.integration`)

Tests that verify HTTP endpoint behavior through an in-process ASGI client against the FastAPI application. Authentication is overridden via dependency injection. These verify the full backend request/response cycle: routing, dependency injection, serialization, error formatting, and status codes.

**Should cover:**
- Catalog contract (seed data matches runtime responses)
- CRUD lifecycle (namespace, field, object, API, endpoint)
- Validation and error handling (400, 404, 422)
- Relationships and FK auto-creation
- Field roles and server defaults
- Name validation (PascalCase/snake_case)
- API generation (ZIP structure, ORM models, Pydantic constraints)

**Speed:** Medium. Requires a running PostgreSQL instance (Docker).

---

### Codegen Tests (`pytest.mark.codegen`)

Tests that verify the `api_craft` code generation pipeline: input validation, transform pipeline, generated project structure, and in-process runtime behavior of generated apps.

**Should cover:**
- Input model validation (PascalCase, DB config, response shapes)
- Transform/prepare pipeline (models, views, ORM, imports)
- Filter inference, path/query params, relationship codegen
- Generated project file presence, `compile()` checks, content assertions
- In-process runtime: boot generated app with TestClient + SQLite and verify constraints, validators, CRUD, response shapes

**Speed:** Medium. No database, but generates files to disk and boots apps.

---

### E2E Tests (`pytest.mark.e2e`)

Full-stack tests that generate a project, build it with Docker Compose, and run HTTP requests against a real PostgreSQL-backed API container.

**Should cover:**
- CRUD round-trip against a real database
- Constraint and validator enforcement at runtime
- Timezone-aware datetime handling
- Docker/poetry/Alembic integration

**Speed:** Slow. Requires Docker and builds containers.

---

## Directory Structure

```
tests/
├── conftest.py              # Shared fixtures (DB, HTTP client, user provisioning)
├── support/                 # Shared test utilities (not test files)
│   ├── api_client.py        # Auth override, cleanup, ASGI transport
│   ├── catalog_contract.py  # Seed migration constants (source of truth)
│   ├── shop_contract.py     # Canonical Shop domain + seed_shop/clean_shop
│   └── generated_app.py     # Generated app loader + SQLite harness
├── catalog/                 # [integration] Catalog contract tests
│   └── test_system_catalog.py
├── http/                    # [integration] HTTP endpoint tests
│   ├── test_happy_path_and_seeding.py
│   ├── test_validation_and_errors.py
│   └── test_relationships_and_fields.py
├── codegen/                 # [codegen] Code generation pipeline tests
│   ├── test_input_and_transform.py
│   ├── test_codegen_domains.py
│   └── test_generated_project.py
├── runtime/                 # [codegen/e2e] Generated app runtime tests
│   ├── test_generated_runtime.py   # [codegen] In-process with SQLite
│   └── test_generated_stack.py     # [e2e] Docker Compose + PostgreSQL
└── specs/                   # YAML spec files for codegen tests
    ├── items_api.yaml
    ├── items_api_db.yaml
    ├── items_api_db_uuid.yaml
    ├── products_api_filters.yaml
    └── shop_api.yaml
```

---

## Running Tests

```bash
# All tests (skips e2e if Docker unavailable, skips integration if DB unavailable)
make test

# By layer
poetry run pytest tests/catalog tests/http -m integration -v     # Needs PostgreSQL
poetry run pytest tests/codegen tests/runtime/test_generated_runtime.py -m codegen -v
poetry run pytest tests/runtime/test_generated_stack.py -m e2e -v   # Needs Docker

# Quick codegen-only smoke
poetry run pytest tests/codegen -v

# Single test
poetry run pytest tests/codegen/test_input_and_transform.py::TestNameTypes -v
```

---

## Pytest Markers

Defined in `pyproject.toml`:

| Marker | Description | Requires DB |
|--------|-------------|-------------|
| `unit` | Pure logic tests, no external dependencies | No |
| `integration` | Catalog + HTTP endpoint tests | Yes |
| `codegen` | Code generation pipeline + in-process runtime | No |
| `e2e` | Full Docker Compose stack tests | Yes (Docker) |

---

## Conventions

1. **One marker per file.** Set `pytestmark = pytest.mark.<category>` at module level.
2. **Each HTTP test module defines `TEST_CLERK_ID`** at module level for user isolation.
3. **Fixtures go in `conftest.py`** at the root level. Shared utilities go in `tests/support/`.
4. **Cleanup after yourself.** The root `client` fixture auto-cleans DB data for the module's `TEST_CLERK_ID`.
5. **One canonical Shop definition** in `tests/support/shop_contract.py`. Never duplicate field/object definitions in test files.
6. **Format before committing.** Run `poetry run black src/ tests/` after any test changes.
