# Deployment

This directory contains deployment configurations for different providers.

## Providers

| Provider | Directory / Docs | Notes |
|----------|------------------|-------|
| **Coolify** | [`coolify/COOLIFY_DEPLOYMENT.md`](coolify/COOLIFY_DEPLOYMENT.md) | Self-hosted PaaS on DO droplet, $6-12/mo (recommended) |
| **AWS** | `aws/` | Full IaC, ECS Fargate |

## Quick Start

### Coolify on Digital Ocean (Recommended)

See full setup guide: [`coolify/COOLIFY_DEPLOYMENT.md`](coolify/COOLIFY_DEPLOYMENT.md)

Self-hosted Coolify on a DO droplet with auto-deploy from GitHub. Two environments (dev/prod) each with their own Postgres database for ~$6-12/mo total.

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
