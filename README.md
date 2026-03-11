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

## Deployment

Deployed on a Digital Ocean droplet via [Coolify](https://coolify.io/). Pushing to `develop` or `main` triggers CI, and on success a webhook triggers Coolify to build and deploy. See [deploy/coolify/COOLIFY_DEPLOYMENT.md](deploy/coolify/COOLIFY_DEPLOYMENT.md) for setup details.
