# Environment Configuration

Quick-reference for the backend's three runtime contexts. See `deploy/railway/README.md` for full Railway setup instructions.

## Environments

| Environment | Branch | Backend URL | Frontend URL | Clerk App |
|-------------|--------|-------------|--------------|-----------|
| **Local** | any | `localhost:8000` | `localhost:5173` | Development |
| **Railway Dev** | `develop` | `api.dev.mediancode.com` | `dev.mediancode.com` | Development |
| **Railway Prod** | `main` | `api.mediancode.com` | `app.mediancode.com` | Production |

## Master Variable Table

| Variable | Local (`.env.local`) | Railway Dev | Railway Prod | Purpose |
|---|---|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/median_code` | `${{Postgres.DATABASE_URL}}` (reference) | `${{Postgres.DATABASE_URL}}` (reference) | PostgreSQL connection |
| `ENVIRONMENT` | `development` (default) | `${{RAILWAY_ENVIRONMENT_NAME}}` (reference) | `${{RAILWAY_ENVIRONMENT_NAME}}` (reference) | Controls API docs visibility |
| `CLERK_FRONTEND_API_URL` | `https://accurate-lion-1.clerk.accounts.dev` | Same (dev Clerk app) | Production Clerk app URL | JWT validation (JWKS endpoint) |
| `FRONTEND_URL` | `http://localhost:5173` (default) | `https://dev.mediancode.com` | `https://app.mediancode.com` | CORS allowed origin |
| `SYSTEM_NAMESPACE_ID` | `00000000-0000-0000-0000-000000000001` | `00000000-0000-0000-0000-000000000001` | `00000000-0000-0000-0000-000000000001` | System namespace UUID for seed data |
| `CLERK_JWT_AUDIENCE` | *(empty)* | *(empty)* | *(empty)* | Optional JWT audience claim |

### Notes

- **`DATABASE_URL` format**: Railway provides `postgres://` or `postgresql://`. The `settings.py` validator auto-converts to `postgresql+asyncpg://` for SQLAlchemy async. You do **not** need to manually adjust the scheme.
- **`DATABASE_URL` on Railway**: Railway does **not** auto-inject this variable. You must add it as a reference variable (`${{Postgres.DATABASE_URL}}`) in the backend service's Variables tab.
- **`ENVIRONMENT` on Railway**: Use the reference variable `${{RAILWAY_ENVIRONMENT_NAME}}` so the value automatically matches the Railway environment name (`development` or `production`).
- **Migrations**: The `preDeployCommand` in `railway.toml` runs `alembic upgrade head` automatically on every deploy — no manual migration step needed after initial setup.

## Local Development

Local dev uses `.env.local` (loaded by `settings.py`). Copy from `.env.local.example`:

```bash
cp .env.local.example .env.local
# Edit .env.local with your actual Clerk dev URL
```

All variables have sensible defaults in `settings.py` except `CLERK_FRONTEND_API_URL` — this must be set to your actual Clerk Frontend API URL for JWT validation to work.

## Railway Variable Types

| Type | Syntax | Description |
|------|--------|-------------|
| **Reference** | `${{ServiceName.VARIABLE}}` | Dynamically resolved from another service (e.g., Postgres) |
| **Reference** | `${{RAILWAY_ENVIRONMENT_NAME}}` | Built-in Railway variable (resolves to environment name) |
| **Manual** | Plain string value | Static value you enter directly |

## Configuration Checklist

When setting up or auditing a Railway environment:

- [ ] `DATABASE_URL` is set as reference variable `${{Postgres.DATABASE_URL}}`
- [ ] `ENVIRONMENT` is set as reference variable `${{RAILWAY_ENVIRONMENT_NAME}}`
- [ ] `CLERK_FRONTEND_API_URL` points to the correct Clerk app (dev vs prod)
- [ ] `FRONTEND_URL` matches the frontend domain for that environment
- [ ] `SYSTEM_NAMESPACE_ID` is set to `00000000-0000-0000-0000-000000000001`
- [ ] Healthcheck path is `/health`
- [ ] Branch is set correctly (`develop` for dev, `main` for prod)
