# Fly.io Deployment

Deploy the Median Code Backend to Fly.io.

## Prerequisites

- Fly CLI (`brew install flyctl` or `curl -L https://fly.io/install.sh | sh`)
- Fly.io account (`fly auth signup` or `fly auth login`)

## First Deploy

```bash
# Create the app on Fly.io (one-time)
fly apps create median-code-backend --config deploy/fly/fly.toml

# Deploy
make fly-deploy
```

## Commands

```bash
# Deploy
make fly-deploy

# View logs
make fly-logs

# Check status
make fly-status

# SSH into running machine
fly ssh console --config deploy/fly/fly.toml

# Scale up
fly scale count 2 --config deploy/fly/fly.toml
```

## Configuration

Edit `fly.toml` to adjust:
- `primary_region`: Deployment region (iad = Virginia)
- `vm.memory`: Memory allocation
- `vm.cpus`: CPU count
- `min_machines_running`: Minimum instances (0 = scale to zero)

## Regions

Common regions: `iad` (Virginia), `lax` (Los Angeles), `lhr` (London), `nrt` (Tokyo).

List all: `fly platform regions`
