# Environment Configuration

Quick-reference for the backend's three runtime contexts. See [deploy/coolify/COOLIFY_DEPLOYMENT.md](deploy/coolify/COOLIFY_DEPLOYMENT.md) for full Coolify setup instructions.

## Environments

| Environment | Branch | Backend URL | Frontend URL | Clerk App |
|-------------|--------|-------------|--------------|-----------|
| **Local** | any | `localhost:8000` | `localhost:5173` | Development |
| **Coolify Dev** | `develop` | `dev.api.mediancode.com` | `dev.mediancode.com` | Development |
| **Coolify Prod** | `main` | `api.mediancode.com` | `app.mediancode.com` | Production |

## Master Variable Table

| Variable | Local (`.env.local`) | Coolify Dev | Coolify Prod | Purpose |
|---|---|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/median_code` | Postgres internal URL (from Coolify) | Postgres internal URL (from Coolify) | PostgreSQL connection |
| `ENVIRONMENT` | `development` (default) | `development` | `production` | Controls API docs visibility |
| `CLERK_FRONTEND_API_URL` | `https://accurate-lion-1.clerk.accounts.dev` | Same (dev Clerk app) | Production Clerk app URL | JWT validation (JWKS endpoint) |
| `FRONTEND_URL` | `http://localhost:5173` (default) | `https://dev.mediancode.com` | `https://app.mediancode.com` | CORS allowed origin |
| `SYSTEM_NAMESPACE_ID` | `00000000-0000-0000-0000-000000000001` | `00000000-0000-0000-0000-000000000001` | `00000000-0000-0000-0000-000000000001` | System namespace UUID for seed data |
| `CLERK_JWT_AUDIENCE` | *(empty)* | *(empty)* | *(empty)* | Optional JWT audience claim |

### Notes

- **`DATABASE_URL` format**: Hosting providers may inject `postgres://` or `postgresql://`. The `settings.py` validator auto-converts to `postgresql+asyncpg://` for SQLAlchemy async. You do **not** need to manually adjust the scheme.
- **`DATABASE_URL` in Coolify**: Set this as an environment variable on each application resource, using the **Postgres URL (internal)** from the database resource.
- **`ENVIRONMENT` in Coolify**: Set manually to `development` or `production` per environment.
- **Migrations**: The `entrypoint.sh` runs `alembic upgrade head` automatically on every deploy -- no manual migration step needed after initial setup.

## Local Development

Local dev uses `.env.local` (loaded by `settings.py`). Copy from `.env.local.example`:

```bash
cp .env.local.example .env.local
# Edit .env.local with your actual Clerk dev URL
```

All variables have sensible defaults in `settings.py` except `CLERK_FRONTEND_API_URL` -- this must be set to your actual Clerk Frontend API URL for JWT validation to work.

## Configuration Checklist

When setting up or auditing a Coolify environment:

- [ ] `DATABASE_URL` is set to the Postgres internal URL from the database resource
- [ ] `ENVIRONMENT` is set to `development` or `production`
- [ ] `CLERK_FRONTEND_API_URL` points to the correct Clerk app (dev vs prod)
- [ ] `FRONTEND_URL` matches the frontend domain for that environment
- [ ] `SYSTEM_NAMESPACE_ID` is set to `00000000-0000-0000-0000-000000000001`
- [ ] Healthcheck path is `/health` on port `8080`
- [ ] Branch is set correctly (`develop` for dev, `main` for prod)
