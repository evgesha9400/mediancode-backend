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

# Start PostgreSQL and run migrations
make dev-setup

# Start the backend (in a separate terminal)
make dev
```

Backend runs at http://localhost:8000
- API Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

### Local Commands

```bash
make dev-setup      # Start DB + run migrations (first time)
make dev            # Start backend with hot reload
make db-start       # Start PostgreSQL only
make db-stop        # Stop PostgreSQL
make db-reset       # Stop and delete database data
make db-upgrade     # Run migrations
make test           # Run tests
```

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Vercel         │     │  Railway        │     │  Railway        │
│  Frontend       │────▶│  Backend        │────▶│  PostgreSQL     │
│  (Next.js)      │     │  (FastAPI)      │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                       │
        └───────────────────────┘
                  │
            Clerk Auth
```

## Project Structure

```
src/
├── api/                # FastAPI service
│   ├── main.py         # App entry point
│   ├── routers/        # API endpoints
│   ├── services/       # Business logic
│   ├── schemas/        # Pydantic models
│   ├── models/         # SQLAlchemy models
│   └── migrations/     # Alembic migrations
│
└── api_craft/          # Code generation library
    ├── main.py         # APIGenerator class
    ├── models/         # Input/output models
    ├── templates/      # Mako templates
    └── ...
```

## Environment Files

| File | Purpose | Gitignored |
|------|---------|------------|
| `.env.local` | Local development | Yes |
| `.env.development` | Railway dev secrets | Yes |
| `.env.production` | Railway prod secrets | Yes |
| `.env.*.example` | Templates | No |

## Development Workflow

```
Local (.env.local)
    │
    ▼
Development Branch (develop)
    │  make railway-deploy-dev
    ▼
Railway Development Environment
    │
    ▼
Main Branch (main)
    │  make railway-deploy-prod
    ▼
Railway Production Environment
```

## Deployment

See [deploy/railway/README.md](deploy/railway/README.md) for Railway deployment.

```bash
# Deploy to development
make railway-deploy-dev

# Deploy to production
make railway-deploy-prod
```

## Code Generation Pipeline

1. **Transform**: Convert InputAPI → TemplateAPI with computed name variants
2. **Extract**: Pull models, views, path/query parameters
3. **Render**: Apply Mako templates to extracted components
4. **Write**: Output generated FastAPI project files

## API Endpoints

All endpoints require Clerk JWT authentication.

| Endpoint | Description |
|----------|-------------|
| `GET /v1/namespaces` | List namespaces |
| `GET /v1/apis` | List APIs |
| `POST /v1/apis/{id}/generate` | Generate FastAPI project |
| `GET /v1/types` | List types |
| `GET /v1/validators` | List validators |
| `GET /v1/fields` | List fields |
| `GET /v1/objects` | List objects |
| `GET /v1/endpoints` | List endpoints |

## Security

- Clerk JWT authentication on all API endpoints
- Rate limiting (100/min standard, 10/min for code generation)
- CORS restricted to configured frontend URL
- Security headers (X-Frame-Options, HSTS, CSP, etc.)
