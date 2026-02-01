# Deployment

This directory contains deployment configurations for different providers.

## Providers

| Provider | Directory | Command | Notes |
|----------|-----------|---------|-------|
| **Railway** | `railway/` | `make railway-deploy` | PaaS, simple, managed PostgreSQL |
| **AWS** | `aws/` | `make cdk-deploy` | Full IaC, ECS Fargate |

## Quick Start

### Railway (Recommended)

```bash
# Install CLI
npm install -g @railway/cli

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
