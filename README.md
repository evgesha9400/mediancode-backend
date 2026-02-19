# Median Code Backend

FastAPI backend for Median Code - API code generation and entity management.

## Quick Start (Local Development)

### Prerequisites

- Python 3.13+
- Docker (for PostgreSQL)
- Poetry

### Setup

```bash
# Install dependencies
poetry install

# Create local environment file
cp .env.local.example .env.local
# Edit .env.local with your Clerk credentials

# First-time setup: start DB + run migrations
make setup

# Start the backend (in a separate terminal)
make dev
```

Backend runs at http://localhost:8000
- API Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

### Local Commands

```bash
make setup          # First-time setup: install deps, start DB, run migrations
make dev            # Start backend with hot reload
make db             # Start PostgreSQL only
make db-stop        # Stop PostgreSQL
make db-reset       # Reset database: delete data, restart, re-migrate
make test           # Run all tests
make test-codegen   # Run codegen tests only (no DB needed)
make clean          # Remove Python caches and test output
```

### Database Migrations (Local)

```bash
make migrate-up             # Apply all pending migrations
make migrate-down           # Rollback last migration
make migrate-history        # Show migration history
make migrate-current        # Show current migration version
make migration msg="..."    # Create new migration file
```

## Architecture

```
┌─────────────────┐     ┌───────────────────────────────────────────────┐
│  Vercel         │     │  Digital Ocean Droplet (Coolify)               │
│  Frontend       │     │                                               │
│  (Next.js)      │────>│  ┌─────────────┐     ┌─────────────────────┐  │
└─────────────────┘     │  │  Backend     │────>│  PostgreSQL         │  │
        │               │  │  (FastAPI)   │     │                     │  │
        │               │  └─────────────┘     └─────────────────────┘  │
        │               └───────────────────────────────────────────────┘
        │                       │
        └───────────────────────┘
                  │
            Clerk Auth
```

## Project Structure

```
src/
├── api/                    # FastAPI service
│   ├── main.py             # App entry point, router registration
│   ├── auth.py             # Clerk JWT authentication
│   ├── database.py         # Async SQLAlchemy engine and session
│   ├── deps.py             # Shared dependencies (DbSession, ProvisionedUser)
│   ├── middleware.py        # Security headers middleware
│   ├── rate_limit.py       # Rate limiting configuration (slowapi)
│   ├── settings.py         # Environment-based settings (pydantic-settings)
│   ├── routers/            # API endpoint handlers
│   │   ├── namespaces.py
│   │   ├── apis.py
│   │   ├── types.py
│   │   ├── field_constraints.py
│   │   ├── fields.py
│   │   ├── objects.py
│   │   └── endpoints.py
│   ├── services/           # Business logic layer
│   │   ├── base.py         # Base service class
│   │   ├── namespace.py
│   │   ├── api.py
│   │   ├── type.py
│   │   ├── field_constraint.py
│   │   ├── field.py
│   │   ├── object.py
│   │   ├── endpoint.py
│   │   ├── generation.py   # Code generation orchestration
│   │   └── user.py         # User provisioning and generation limits
│   ├── schemas/            # Pydantic request/response models
│   ├── models/             # SQLAlchemy ORM models
│   ├── migrations/         # Alembic migrations
│   └── data/               # Reference configuration (global_config.yaml)
│
└── api_craft/              # Code generation library
    ├── main.py             # APIGenerator class, generate_fastapi()
    ├── transformers.py     # InputAPI -> TemplateAPI conversion
    ├── extractors.py       # Extract models, views, parameters
    ├── renderers.py        # Apply Mako templates to components
    ├── placeholders.py     # Placeholder data generation
    ├── utils.py            # Shared utilities
    ├── models/             # Pydantic models (input, template, types, validators)
    └── templates/          # Mako templates (*.mako) and static files
```

## Environment Files

| File | Purpose | Gitignored |
|------|---------|------------|
| `.env.local` | Local development | Yes |
| `.env.development` | Deployed dev secrets | Yes |
| `.env.production` | Deployed prod secrets | Yes |
| `.env.*.example` | Templates | No |

## Development Workflow

```
Local (.env.local)
    │
    v
Development Branch (develop)
    │  git push → CI → Coolify webhook
    v
Coolify Development Environment (dev.api.mediancode.com)
    │
    v
Main Branch (main)
    │  git push → CI → Coolify webhook
    v
Coolify Production Environment (api.mediancode.com)
```

## Deployment

Deployed on a Digital Ocean droplet via [Coolify](https://coolify.io/) (self-hosted PaaS).
See [deploy/coolify/COOLIFY_DEPLOYMENT.md](deploy/coolify/COOLIFY_DEPLOYMENT.md) for full setup instructions.

Deployments are CI-gated: pushing to `develop` or `main` triggers GitHub Actions (lint + test), and on success a webhook triggers Coolify to build and deploy automatically. Migrations run on every deploy via `entrypoint.sh`.

## Code Generation Pipeline

```
InputAPI (JSON) -> Transform -> Extract -> Render -> Write
```

1. **Transform** (`transformers.py`): Convert InputAPI models to TemplateAPI models with computed name variants
2. **Extract** (`extractors.py`): Pull models, views, path/query parameters from transformed API
3. **Render** (`renderers.py`): Apply Mako templates to extracted components
4. **Write** (`main.py`): Output generated FastAPI project files to filesystem

## API Endpoints

All endpoints require Clerk JWT authentication (except `/health`).

### Namespaces (`/v1/namespaces`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/v1/namespaces` | List all namespaces |
| `POST` | `/v1/namespaces` | Create a new namespace |
| `GET` | `/v1/namespaces/{id}` | Get namespace by ID |
| `PUT` | `/v1/namespaces/{id}` | Update namespace |
| `DELETE` | `/v1/namespaces/{id}` | Delete namespace |

### APIs (`/v1/apis`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/v1/apis` | List all APIs |
| `POST` | `/v1/apis` | Create a new API |
| `GET` | `/v1/apis/{id}` | Get API by ID |
| `PUT` | `/v1/apis/{id}` | Update API |
| `DELETE` | `/v1/apis/{id}` | Delete API |
| `POST` | `/v1/apis/{id}/generate` | Generate FastAPI project (ZIP) |

### Types (`/v1/types`) -- read-only

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/v1/types` | List all types |

### Field Constraints (`/v1/field-constraints`) -- read-only

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/v1/field-constraints` | List all field constraints |

### Fields (`/v1/fields`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/v1/fields` | List all fields |
| `POST` | `/v1/fields` | Create a new field |
| `GET` | `/v1/fields/{id}` | Get field by ID |
| `PUT` | `/v1/fields/{id}` | Update field |
| `DELETE` | `/v1/fields/{id}` | Delete field |

### Objects (`/v1/objects`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/v1/objects` | List all objects |
| `POST` | `/v1/objects` | Create a new object |
| `GET` | `/v1/objects/{id}` | Get object by ID |
| `PUT` | `/v1/objects/{id}` | Update object |
| `DELETE` | `/v1/objects/{id}` | Delete object |

### Endpoints (`/v1/endpoints`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/v1/endpoints` | List all endpoints |
| `POST` | `/v1/endpoints` | Create a new endpoint |
| `GET` | `/v1/endpoints/{id}` | Get endpoint by ID |
| `PUT` | `/v1/endpoints/{id}` | Update endpoint |
| `DELETE` | `/v1/endpoints/{id}` | Delete endpoint |

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check (no auth required) |

## Security

- Clerk JWT authentication on all API endpoints
- Automatic user provisioning on first authenticated request
- Rate limiting (100/min standard, 10/min for code generation)
- CORS restricted to configured frontend URLs
- Security headers (X-Frame-Options, HSTS, CSP, Permissions-Policy, etc.)
- API docs disabled in production
