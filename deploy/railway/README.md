# Railway Deployment

Deploy the Median Code Backend to Railway with dev/prod environment separation.

## Prerequisites

- Railway account (https://railway.app)
- Railway CLI: `brew install railway` or `npm install -g @railway/cli`
- Two Railway environments: `production` (linked to `main`) and `development` (linked to `develop`)

## Environment Files

Create your environment files from the examples:

```bash
# Development
cp .env.development.example .env.development
# Edit with your dev values

# Production
cp .env.production.example .env.production
# Edit with your prod values
```

These files are gitignored - secrets stay local and get synced to Railway on deploy.

## Quick Start

```bash
# Login and link project
railway login
railway link

# Switch to the environment you want to deploy
railway environment development  # or: production

# Add PostgreSQL (first time only)
railway add -d postgres

# Deploy development
make railway-deploy-dev

# Deploy production
make railway-deploy-prod
```

## Deploy Commands

| Command | Description |
|---------|-------------|
| `make railway-deploy-prod` | Deploy to production (syncs `.env.production`) |
| `make railway-deploy-dev` | Deploy to development (syncs `.env.development`) |
| `make railway-deploy-prod-dry` | Preview production deploy |
| `make railway-deploy-dev-dry` | Preview development deploy |
| `make railway-deploy-prod-quick` | Production deploy, skip migrations |
| `make railway-deploy-dev-quick` | Development deploy, skip migrations |

## What the Deploy Script Does

```
[1/7] Check prerequisites (Railway CLI, login, project link)
[2/7] Load .env.{environment} file
[3/7] Get Railway project info
[4/7] Sync variables from .env file to Railway
[5/7] Check PostgreSQL database
[6/7] Run Alembic migrations
[7/7] Deploy application & health check
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Auto | Railway manages this automatically |
| `CLERK_ISSUER_URL` | Yes | Your Clerk issuer URL |
| `CLERK_AUDIENCE` | No | Optional JWT audience |
| `FRONTEND_URL` | Yes | Vercel frontend URL (for CORS) |
| `GLOBAL_NAMESPACE_ID` | No | Default: `namespace-global` |

## Railway Environment Setup

Railway supports multiple environments per project. Set this up once:

1. Go to Railway dashboard → Your project → Settings → Environments
2. Create `development` environment linked to `develop` branch
3. Create `production` environment linked to `main` branch
4. Each environment gets its own PostgreSQL instance and variables

Switch environments locally:
```bash
railway environment development
railway environment production
```

## Branch → Environment Flow

```
develop branch  →  make railway-deploy-dev   →  development environment
main branch     →  make railway-deploy-prod  →  production environment
```

When you merge `develop` into `main`, deploy production:
```bash
git checkout main
git merge develop
git push
make railway-deploy-prod
```

## Database

Each environment has its own PostgreSQL database.

```bash
# Run migrations manually
railway run alembic upgrade head

# Connect to database
railway connect postgres

# View migration history
railway run alembic history
```

## Vercel Integration

After deploying, set the backend URL in Vercel:

**Development (Preview deployments):**
```
NEXT_PUBLIC_API_URL=https://your-dev-backend.up.railway.app
```

**Production:**
```
NEXT_PUBLIC_API_URL=https://your-prod-backend.up.railway.app
```

## Security

Deployments include:
- HTTPS via Railway's automatic TLS
- CORS restricted to `FRONTEND_URL`
- Rate limiting (100/min standard, 10/min for code generation)
- Security headers (X-Frame-Options, HSTS, CSP)
- Clerk JWT authentication

## Other Commands

```bash
railway logs           # View logs
railway open           # Open dashboard
railway variables      # View/set variables
railway domain         # Manage domains
railway environment    # Switch environments
```

## Costs (Starter Plan)

- Base: $5/month
- Compute: ~$0.000231/min
- PostgreSQL: ~$5-10/month per environment

Estimated: ~$15-25/month for dev + prod
