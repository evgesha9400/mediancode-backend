# Deployment

This directory contains deployment configurations for different providers.

## Providers

| Provider | Directory / Docs | Command | Notes |
|----------|------------------|---------|-------|
| **Coolify** | [`docs/COOLIFY_DEPLOYMENT.md`](../docs/COOLIFY_DEPLOYMENT.md) | Dashboard | Self-hosted PaaS on DO droplet, $6-12/mo |
| **Railway** | `railway/` | `make railway-deploy` | PaaS, simple, managed PostgreSQL |
| **AWS** | `aws/` | `make cdk-deploy` | Full IaC, ECS Fargate |

## Quick Start

### Coolify on Digital Ocean (Recommended)

See full setup guide: [`docs/COOLIFY_DEPLOYMENT.md`](../docs/COOLIFY_DEPLOYMENT.md)

Self-hosted Coolify on a DO droplet with auto-deploy from GitHub. Two environments (dev/prod) each with their own Postgres database for ~$6-12/mo total.

### Railway

```bash
# Install CLI
npm install -g @railway/cli

# Or
brew install railway

# Login and initialize
railway login
railway init

# Add PostgreSQL database
railway add --plugin postgresql

# Set required environment variables
railway variables set CLERK_ISSUER_URL=https://your-clerk.clerk.accounts.dev

# Deploy
make railway-deploy
```

Or use the Railway dashboard: https://railway.app/new

### AWS

```bash
make cdk-install
cd deploy/aws && cdk bootstrap
make cdk-deploy
```

## Adding New Providers

Create a new directory (e.g., `render/`, `fly/`) with:
1. Provider-specific config file
2. README with setup instructions
3. Makefile targets in root `Makefile`
