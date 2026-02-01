# Railway Deployment

Deploy the Median Code Backend to Railway.

## Prerequisites

- Railway account (https://railway.app)
- Railway CLI (optional): `npm install -g @railway/cli`

## Quick Start (Dashboard)

1. Go to https://railway.app/new
2. Select "Deploy from GitHub repo"
3. Connect your repository
4. Add PostgreSQL: Click "New" → "Database" → "PostgreSQL"
5. Set environment variables (see below)

## Quick Start (CLI)

```bash
# Login
railway login

# Initialize in project root
railway init

# Add PostgreSQL
railway add --plugin postgresql

# Set environment variables
railway variables set CLERK_ISSUER_URL=https://your-clerk.clerk.accounts.dev

# Deploy
railway up
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Auto | Automatically set when PostgreSQL is added |
| `CLERK_ISSUER_URL` | Yes | Your Clerk issuer URL |
| `CLERK_AUDIENCE` | No | Optional JWT audience validation |

## Commands

```bash
# Deploy
make railway-deploy

# View logs
make railway-logs

# Open dashboard
make railway-open
```

## Configuration

The `railway.toml` configures:
- Dockerfile path for builds
- Health check endpoint (`/health`)
- Restart policy on failure

## Database

Railway automatically provisions PostgreSQL and injects `DATABASE_URL`.

To connect locally:
```bash
railway connect postgresql
```

## Costs (Starter Plan)

- Base: $5/month
- Usage: ~$0.000231/min for compute
- PostgreSQL: ~$5-10/month depending on size

Estimated total for low traffic: ~$10-15/month
