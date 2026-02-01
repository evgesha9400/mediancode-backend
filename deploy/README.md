# Deployment

This directory contains deployment configurations for different providers.

## Providers

| Provider | Directory | Command | Notes |
|----------|-----------|---------|-------|
| **Fly.io** | `fly/` | `make fly-deploy` | PaaS, simple, scale-to-zero |
| **AWS** | `aws/` | `make cdk-deploy` | Full IaC, ECS Fargate |

## Quick Start

### Fly.io (Recommended for getting started)

```bash
fly auth login
fly apps create median-code-backend --config deploy/fly/fly.toml
make fly-deploy
```

### AWS

```bash
make cdk-install
cd deploy/aws && cdk bootstrap
make cdk-deploy
```

## Adding New Providers

Create a new directory (e.g., `railway/`, `render/`) with:
1. Provider-specific config file
2. README with setup instructions
3. Makefile targets in root `Makefile`
