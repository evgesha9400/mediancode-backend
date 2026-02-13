# Coolify Deployment (on Digital Ocean)

Deploy the Median Code Backend to a self-hosted Coolify instance on a Digital Ocean droplet with dev/prod environment separation.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Digital Ocean Droplet ($6-12/mo)                         │
│                    Ubuntu 24.04 LTS                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  Coolify (Management UI)              coolify.mediancode.com         │   │
│  │  ├── Traefik (Reverse Proxy + Auto SSL via Let's Encrypt)            │   │
│  │  └── Docker Engine                                                   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────┐  ┌─────────────────────────────────┐   │
│  │   Production Environment        │  │   Development Environment       │   │
│  │   (branch: main)                │  │   (branch: develop)             │   │
│  │                                 │  │                                 │   │
│  │  ┌───────────┐  ┌───────────┐   │  │  ┌───────────┐  ┌───────────┐   │   │
│  │  │  Backend  │  │ PostgreSQL│   │  │  │  Backend  │  │ PostgreSQL│   │   │
│  │  │  Service  │  │  Database │   │  │  │  Service  │  │  Database │   │   │
│  │  └───────────┘  └───────────┘   │  │  └───────────┘  └───────────┘   │   │
│  │        │                        │  │        │                        │   │
│  │        ▼                        │  │        ▼                        │   │
│  │  api.mediancode.com             │  │  dev.api.mediancode.com         │   │
│  └─────────────────────────────────┘  └─────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      ▲
                                      │ webhook (deploy)
                                      │
                    ┌─────────────────────────────────┐
                    │       GitHub Actions (CI)       │
                    │                                 │
                    │  push ──► tests ──► if pass ──► │
                    │          deploy via webhook     │
                    └─────────────────────────────────┘
                                      ▲
                                      │
                    ┌─────────────────────────────────┐
                    │         GitHub Repository       │
                    │    median-code-backend          │
                    │                                 │
                    │  push main ──────► production   │
                    │  push develop ───► development  │
                    └─────────────────────────────────┘
```

## URL Structure

| Environment    | Backend URL              | Branch    |
| -------------- | ------------------------ | --------- |
| **Production** | `api.mediancode.com`     | `main`    |
| **Development**| `dev.api.mediancode.com` | `develop` |
| **Coolify UI** | `coolify.mediancode.com` | —         |

---

## Prerequisites

- Domain with DNS access (e.g. Cloudflare, Namecheap)
- GitHub repository with `main` and `develop` branches
- Credit card for Digital Ocean ($6-12/mo)

---

## Step 1: Create a Digital Ocean Account

1. Go to https://cloud.digitalocean.com/registrations/new
2. Sign up with email or GitHub
3. Add a payment method (credit card or PayPal)

> New accounts often get **$200 free credit for 60 days**.

---

## Step 2: Create an SSH Key for Digital Ocean

Before creating the droplet, generate a dedicated SSH key:

```bash
ssh-keygen -t ed25519 -C "digitalocean" -f ~/.ssh/digitalocean
```

Then add an entry to `~/.ssh/config` so SSH uses this key automatically:

```
Host median-server
  HostName <droplet-ip>        # Update after droplet is created
  User root
  IdentityFile ~/.ssh/digitalocean
```

> **Important**: If your SSH config has `IdentitiesOnly yes` in the global `Host *` block, SSH will **only** use keys explicitly listed in config entries. Without this config entry, `ssh root@<ip>` will fail even if the key exists.

You'll update `HostName` with the actual IP after creating the droplet in the next step.

---

## Step 3: Create a Droplet

1. In the DO dashboard, click **Create > Droplets**
2. Configure:
   - **Region**: Closest to your users (e.g. Frankfurt, NYC)
   - **Image**: Ubuntu 24.04 LTS
   - **Size**: $6/mo (1 vCPU, 1GB RAM, 25GB SSD) — minimum viable. $12/mo (2GB RAM) recommended for running two environments with Postgres.
   - **Authentication**: SSH key — click **New SSH Key** and paste the contents of `~/.ssh/digitalocean.pub`
   - **Hostname**: `median-code-server`
3. Click **Create Droplet**
4. Note the **public IP address**
5. Update `~/.ssh/config` — replace `<droplet-ip>` with the actual IP

---

## Step 4: Install Coolify

SSH into the droplet, then run the install script:

```bash
ssh median-server
```

Once connected to the server:

```bash
curl -fsSL https://cdn.coollabs.io/coolify/install.sh | bash
```

> **Important**: These are two separate steps. SSH in first, then run the install command on the server. Do not run them as a single command — if SSH fails, the install script will run on your local machine instead.

This installs Coolify, Docker, and Traefik. Takes 2-3 minutes.

After installation, Coolify will display your access URL and recommend backing up `/data/coolify/source/.env`. You can do this later once everything is set up — store it in a password manager.

---

## Step 5: Initial Coolify Setup

1. Open `http://<droplet-ip>:8000` in your browser
2. Create an admin account (email + password)
3. On the server setup page, click **Localhost** to use the droplet as the deployment target
4. Coolify will verify Docker is running — wait for the green check

---

## Step 6: Configure DNS for Coolify

In your DNS provider (Cloudflare, Namecheap, etc.), add an A record for the Coolify dashboard:

```
Type: A    Name: coolify      Value: <droplet-ip>    TTL: Auto
```

Then in Coolify **Settings > General**, set the instance FQDN to `https://coolify.mediancode.com`.

> Coolify auto-provisions SSL certificates via Let's Encrypt once DNS resolves.

---

## Step 7: Connect GitHub

1. In Coolify sidebar, go to **Sources**
2. Click **Add** > **GitHub App**
3. It will ask for a name — use `median-code-backend` (same name in both Coolify and GitHub)
4. Follow the wizard to create a GitHub App on your account
5. Authorize and install it on the `median-code-backend` repository
6. One GitHub App handles both environments — the dev/prod split is configured per-resource later

> You do NOT need separate GitHub Apps for dev and prod.

---

## Step 8: Create Project Structure

1. In Coolify sidebar, go to **Projects**
2. Click **Add** to create a new project
3. Name: `Median Code`
4. Inside the project, you'll see a **default** environment — rename it to `production`
5. Click **Add Environment** and name it `development`

---

## Step 9: Set Up Development Environment

### 9a. Configure DNS for Development

In your DNS provider, add an A record for the dev API:

```
Type: A    Name: dev.api      Value: <droplet-ip>    TTL: Auto
```

### 9b. Add PostgreSQL Database

Select the **development** environment, then:

1. Click **Add Resource** > **Database** > **PostgreSQL**
2. Configure on the **General** tab:

| Field              | Value                    |
| ------------------ | ------------------------ |
| **Name**           | `median-code-dev-db`     |
| **Description**    | `Development database for Median Code Backend` |
| **Image**          | `postgres:18-alpine` |
| **Username**       | `postgres` (default, leave as-is) |
| **Password**       | Keep the auto-generated strong password |
| **Initial Database** | `median_code` |

3. **Make it publicly available**: Leave **unchecked**. External DB client access (DBeaver, TablePlus) is handled via SSH tunnel instead — see [Connecting from a Local DB Client](#connecting-from-a-local-db-client).
4. Click **Save**, then **Start**
5. Once running, copy the **Postgres URL (internal)** — you'll need it for the app config

### 9c. Add Backend Application

1. Go back to the development environment and click **Add Resource**
2. Under **Git Based**, select **Private Repository (with GitHub App)**
3. Select your GitHub source and the `median-code-backend` repository
4. Set **Branch**: `develop`
5. **Build Pack**: `Dockerfile` (should be auto-detected)
6. Click **Save**

### 9d. Configure Application Settings

In the application resource, go to **General** tab:

| Field                  | Value                                        |
| ---------------------- | -------------------------------------------- |
| **Name**               | `median-code-dev-api`                        |
| **Description**        | `Development API for Median Code Backend`    |
| **Build Pack**         | `Dockerfile`                                 |
| **Domains**            | `https://dev.api.mediancode.com` (or leave the auto-generated sslip.io URL for initial testing) |
| **Ports Exposes**      | `8080`                                       |
| **Port Mappings**      | Clear/empty (delete any default like `3000:3000`) |
| **Base Directory**     | `/`                                          |
| **Dockerfile Location**| `/Dockerfile`                                |

Go to **Environment Variables** tab and add:

| Variable               | Value                                        | Notes                           |
| ---------------------- | -------------------------------------------- | ------------------------------- |
| `DATABASE_URL`         | *(Postgres URL (internal) from step 9b)*     | Postgres connection string      |
| `ENVIRONMENT`          | `development`                                |                                 |
| `CLERK_FRONTEND_API_URL` | `https://accurate-lion-1.clerk.accounts.dev` | From Clerk dashboard (dev)    |
| `FRONTEND_URL`         | `https://dev.mediancode.com`                 | For CORS                        |
| `GLOBAL_NAMESPACE_ID`  | `00000000-0000-0000-0000-000000000001`       | Global namespace UUID           |

> **Note**: Do NOT add `PORT` — the Dockerfile sets `ENV PORT=8080` as default. Do NOT add `PYTHONPATH` — the Dockerfile handles this.

### 9e. Database Migrations

Migrations run automatically on every deployment via `entrypoint.sh`. The entrypoint runs `alembic upgrade head` before starting the server — no additional configuration needed in Coolify.

**Resetting the database (development phase only):** While the schema is still evolving and migrations are being rewritten, add a `DB_RESET` environment variable to force a clean slate on the next deploy:

| Variable    | Value  | Notes                                          |
| ----------- | ------ | ---------------------------------------------- |
| `DB_RESET`  | `true` | Drops and recreates the schema before migrating |

The entrypoint will drop the `public` schema, recreate it, then run all migrations from scratch. **Remove this variable after the deploy** — it should not stay set permanently.

### 9f. Configure Health Check

Go to the **Healthcheck** tab:

| Field              | Value       |
| ------------------ | ----------- |
| **Method**         | `GET`       |
| **Scheme**         | `http`      |
| **Host**           | `localhost` |
| **Port**           | `8080`      |
| **Path**           | `/health`   |
| **Return Code**    | `200`       |
| **Interval (s)**   | `30`        |
| **Timeout (s)**    | `5`         |
| **Retries**        | `10`        |
| **Start Period (s)** | `5`       |

Click **Enable Healthcheck**, then **Save**.

### 9g. Configure Resource Limits

Go to the **Resource Limits** tab. These limits ensure dev containers don't starve production on a shared 2GB droplet.

> **Important**: Memory values must include the `m` suffix (e.g., `256m` not `256`). Without the suffix, Docker interprets the value as bytes and rejects it with "Minimum memory limit allowed is 6MB".

**For the API container (`median-code-dev-api`):**

| Field                  | Value  | Notes                                              |
| ---------------------- | ------ | -------------------------------------------------- |
| **Number of CPUs**     | `0.25` |                                                    |
| **CPU sets to use**    | *(empty)* | Not useful with a single vCPU                   |
| **CPU Weight**         | `512`  | Half of default — prod gets priority under contention |
| **Soft Memory Limit**  | `192m` | Target memory usage (can exceed if RAM is free)    |
| **Swappiness**         | `60`   | Default, balanced                                  |
| **Maximum Memory Limit** | `256m` | Hard cap — container is OOM-killed if exceeded   |
| **Maximum Swap Limit** | `0`    |                                                    |

**For the database (`median-code-dev-db`):** apply the same values via its Resource Limits tab.

### 9h. Verify Advanced Settings

Go to the **Advanced** tab:

- **Auto Deploy**: **Unchecked** — deployments are triggered by GitHub Actions after CI passes (see Step 11)
- **Force Https**: Checked
- **Enable Gzip Compression**: Checked

### 9i. Deploy and Verify

Click **Deploy** (top right) and monitor the build logs under the **Deployments** tab.

Once deployed, verify:

```bash
curl https://dev.api.mediancode.com/health
# Expected: {"status":"healthy"}
```

---

## Step 10: Set Up Production Environment

### 10a. Configure DNS for Production

In your DNS provider, add an A record for the production API:

```
Type: A    Name: api          Value: <droplet-ip>    TTL: Auto
```

### 10b. Add PostgreSQL Database

Select the **production** environment, then:

1. Click **Add Resource** > **Database** > **PostgreSQL**
2. Configure on the **General** tab:

| Field              | Value                    |
| ------------------ | ------------------------ |
| **Name**           | `median-code-prod-db`    |
| **Description**    | `Production database for Median Code Backend` |
| **Image**          | `postgres:18-alpine` |
| **Username**       | `postgres` (default, leave as-is) |
| **Password**       | Keep the auto-generated strong password |
| **Initial Database** | `median_code` |

3. **Make it publicly available**: Leave **unchecked**. External DB client access (DBeaver, TablePlus) is handled via SSH tunnel instead — see [Connecting from a Local DB Client](#connecting-from-a-local-db-client).
4. Click **Save**, then **Start**
5. Once running, copy the **Postgres URL (internal)** — you'll need it for the app config

### 10c. Add Backend Application

1. Go back to the production environment and click **Add Resource**
2. Under **Git Based**, select **Private Repository (with GitHub App)**
3. Select your GitHub source and the `median-code-backend` repository
4. Set **Branch**: `main`
5. **Build Pack**: `Dockerfile` (should be auto-detected)
6. Click **Save**

### 10d. Configure Application Settings

In the application resource, go to **General** tab:

| Field                  | Value                                        |
| ---------------------- | -------------------------------------------- |
| **Name**               | `median-code-prod-api`                       |
| **Description**        | `Production API for Median Code Backend`     |
| **Build Pack**         | `Dockerfile`                                 |
| **Domains**            | `https://api.mediancode.com` (or leave the auto-generated sslip.io URL for initial testing) |
| **Ports Exposes**      | `8080`                                       |
| **Port Mappings**      | Clear/empty (delete any default like `3000:3000`) |
| **Base Directory**     | `/`                                          |
| **Dockerfile Location**| `/Dockerfile`                                |

Go to **Environment Variables** tab and add:

| Variable               | Value                                        | Notes                           |
| ---------------------- | -------------------------------------------- | ------------------------------- |
| `DATABASE_URL`         | *(Postgres URL (internal) from step 10b)*    | Postgres connection string      |
| `ENVIRONMENT`          | `production`                                 |                                 |
| `CLERK_FRONTEND_API_URL` | `https://clerk.mediancode.com`             | From Clerk dashboard (prod)     |
| `FRONTEND_URL`         | `https://mediancode.com`                     | For CORS                        |
| `GLOBAL_NAMESPACE_ID`  | `00000000-0000-0000-0000-000000000001`       | Global namespace UUID           |

> **Note**: Do NOT add `PORT` — the Dockerfile sets `ENV PORT=8080` as default. Do NOT add `PYTHONPATH` — the Dockerfile handles this.

### 10e. Database Migrations

Same as development (step 9e) — migrations run automatically via `entrypoint.sh` on every deployment. The `DB_RESET` variable works here too when needed during the development phase.

### 10f. Configure Health Check

Go to the **Healthcheck** tab:

| Field              | Value       |
| ------------------ | ----------- |
| **Method**         | `GET`       |
| **Scheme**         | `http`      |
| **Host**           | `localhost` |
| **Port**           | `8080`      |
| **Path**           | `/health`   |
| **Return Code**    | `200`       |
| **Interval (s)**   | `30`        |
| **Timeout (s)**    | `5`         |
| **Retries**        | `10`        |
| **Start Period (s)** | `5`       |

Click **Enable Healthcheck**, then **Save**.

### 10g. Configure Resource Limits

Go to the **Resource Limits** tab. Production gets ~2x the resources of development.

**For the API container (`median-code-prod-api`):**

| Field                  | Value  | Notes                                              |
| ---------------------- | ------ | -------------------------------------------------- |
| **Number of CPUs**     | `0.5`  |                                                    |
| **CPU sets to use**    | *(empty)* | Not useful with a single vCPU                   |
| **CPU Weight**         | `1024` | Default — gets 2x priority over dev (512) under contention |
| **Soft Memory Limit**  | `384m` | Target memory usage (can exceed if RAM is free)    |
| **Swappiness**         | `60`   | Default, balanced                                  |
| **Maximum Memory Limit** | `512m` | Hard cap — container is OOM-killed if exceeded   |
| **Maximum Swap Limit** | `0`    |                                                    |

**For the database (`median-code-prod-db`):** apply the same values via its Resource Limits tab.

### 10h. Verify Advanced Settings

Go to the **Advanced** tab:

- **Auto Deploy**: **Unchecked** — deployments are triggered by GitHub Actions after CI passes (see Step 11)
- **Force Https**: Checked
- **Enable Gzip Compression**: Checked

### 10i. Deploy and Verify

Click **Deploy** (top right) and monitor the build logs under the **Deployments** tab.

Once deployed, verify:

```bash
curl https://api.mediancode.com/health
# Expected: {"status":"healthy"}
```

---

## Step 11: Configure CI/CD (GitHub Actions → Coolify)

Deployments are gated behind CI — Coolify only deploys after tests pass in GitHub Actions. Auto Deploy is disabled in Coolify; instead, GitHub Actions calls Coolify's deploy webhook on success.

The CI workflow lives in `.github/workflows/ci.yml`. It runs tests on every push and PR, and triggers deployment only on direct pushes to `main` or `develop` after tests pass. Concurrent pushes to the same branch cancel in-progress runs so only the latest commit deploys.

### 11a. Enable Coolify API Access

1. In Coolify, go to **Settings** (sidebar) > **Configuration** > **Advanced**
2. Enable **API Access**
3. Leave **Allowed IPs for API Access** empty — GitHub Actions runners use thousands of dynamic IP ranges that change frequently, so IP-restricting is not practical. The bearer token (step 11b) is the security boundary.

### 11b. Create Coolify API Token

1. In Coolify, go to **Keys & Tokens** in the sidebar (opens the **Security** page)
2. Click the **API Tokens** tab
3. Enter description: `github-actions`
4. Under **Token Permissions**, uncheck **read** and check **deploy** only
5. Click **Create** and copy the generated token — you'll need it in step 11d

### 11c. Copy Deploy Webhook URLs

For each application resource, copy the webhook URL:

**Development (`median-code-dev-api`):**

1. Open the `median-code-dev-api` application resource
2. Go to the **Webhooks** tab
3. Copy the **Deploy Webhook** URL

**Production (`median-code-prod-api`):**

1. Open the `median-code-prod-api` application resource
2. Go to the **Webhooks** tab
3. Copy the **Deploy Webhook** URL

### 11d. Configure GitHub Repository

Go to your GitHub repository **Settings** > **Secrets and variables** > **Actions**.

**Add a repository secret** (Secrets tab):

| Secret           | Value                              |
| ---------------- | ---------------------------------- |
| `COOLIFY_TOKEN`  | API token from step 11b            |

**Create two GitHub environments** (Settings > Environments):

**`development` environment:**

1. Click **New environment**, name it `development`
2. Go to the environment's **Variables** tab (not Secrets)
3. Add a variable:

| Variable          | Value                                        |
| ----------------- | -------------------------------------------- |
| `COOLIFY_WEBHOOK` | Deploy webhook URL for `median-code-dev-api` from step 11c |

**`production` environment:**

1. Click **New environment**, name it `production`
2. Go to the environment's **Variables** tab (not Secrets)
3. Add a variable:

| Variable          | Value                                         |
| ----------------- | --------------------------------------------- |
| `COOLIFY_WEBHOOK` | Deploy webhook URL for `median-code-prod-api` from step 11c |

> The `COOLIFY_TOKEN` secret is shared at the repo level (one Coolify instance). The `COOLIFY_WEBHOOK` variable differs per environment. The workflow automatically selects the correct environment based on the branch (`main` → `production`, `develop` → `development`).

### 11e. Verify the Pipeline

Push a commit to `develop` and check that:

1. GitHub Actions runs tests (visible in the **Actions** tab)
2. Tests pass → the deploy job triggers
3. Coolify builds and deploys (visible in Coolify's Deployments tab)

```bash
git checkout develop
git commit --allow-empty -m "ci: test pipeline"
git push origin develop
# → GitHub Actions: tests → pass → webhook → Coolify deploys to dev.api.mediancode.com
```

---

## Deployment Flow (After Setup)

Deployments are CI-gated via GitHub Actions:

```
git push origin develop  →  GitHub Actions: tests  →  pass  →  Coolify deploys to development
git push origin main     →  GitHub Actions: tests  →  pass  →  Coolify deploys to production
                                                    →  fail  →  no deploy
```

If a new push arrives while a previous run is still in progress on the same branch, the previous run is cancelled and only the latest commit is tested and deployed.

### Typical Workflow

```bash
# Work on develop
git checkout develop
# ... make changes ...
git add .
git commit -m "feat: add new feature"
git push origin develop
# → GitHub Actions runs tests → on pass → Coolify deploys to dev.api.mediancode.com

# Promote to production
git checkout main
git merge develop
git push origin main
# → GitHub Actions runs tests → on pass → Coolify deploys to api.mediancode.com
```

---

## Database Management

### Access Database Shell

In Coolify, click the Postgres resource and use the built-in **Terminal** tab to run:

```bash
psql -U postgres -d median_code
```

### Connecting from a Local DB Client

Use an SSH tunnel to connect from DBeaver, TablePlus, or other local clients. This avoids exposing the database port publicly — all traffic is encrypted through your SSH key.

Both databases listen on port 5432 inside their containers. Map them to different local ports to avoid conflicts:

**Development database:**

| Field             | Value                         |
| ----------------- | ----------------------------- |
| **Host**          | `localhost`                   |
| **Port**          | `5432`                        |
| **Database**      | `median_code`                 |
| **Username**      | `postgres`                    |
| **Password**      | *(from Coolify dev DB config)* |
| **SSH Host**      | `median-server` (or droplet IP) |
| **SSH User**      | `root`                        |
| **SSH Key**       | `~/.ssh/digitalocean`         |
| **SSH Tunnel Port** | `5432` → `median-code-dev-db:5432` |

**Production database:**

| Field             | Value                         |
| ----------------- | ----------------------------- |
| **Host**          | `localhost`                   |
| **Port**          | `5433`                        |
| **Database**      | `median_code`                 |
| **Username**      | `postgres`                    |
| **Password**      | *(from Coolify prod DB config)* |
| **SSH Host**      | `median-server` (or droplet IP) |
| **SSH User**      | `root`                        |
| **SSH Key**       | `~/.ssh/digitalocean`         |
| **SSH Tunnel Port** | `5433` → `median-code-prod-db:5432` |

> Both DB clients and CLI tools support SSH tunnels. In DBeaver: Connection Settings > SSH tab. In TablePlus: right-click connection > Edit > SSH tab.

**CLI alternative** — forward both ports in one command:

```bash
ssh -L 5432:median-code-dev-db:5432 -L 5433:median-code-prod-db:5432 median-server -N
```

Then connect your client to `localhost:5432` (dev) or `localhost:5433` (prod).

### Run Migrations Manually

Use the application's **Terminal** in Coolify:

```bash
alembic -c alembic.ini upgrade head
alembic -c alembic.ini history
```

### Create New Migration (Locally)

```bash
poetry run alembic revision --autogenerate -m "add users table"
git add .
git commit -m "feat(db): add users table migration"
git push origin develop
# Coolify auto-deploys → Dockerfile CMD runs alembic upgrade head → then starts the server
```

---

## Database Backups

Coolify provides built-in backup scheduling for database resources:

1. Click the Postgres resource
2. Go to **Backups** tab
3. Configure schedule (e.g. daily at 3:00 AM)
4. Optionally configure S3-compatible storage for off-server backups

---

## Monitoring & Logs

- **Build logs**: Click any deployment in the application resource
- **Runtime logs**: Application resource > **Logs** tab
- **Server metrics**: Coolify dashboard shows CPU, RAM, disk usage
- **Notifications**: Coolify Settings > Notifications (supports Discord, Slack, email)

---

## Troubleshooting

### Build Fails

1. Test locally first: `docker build -t test .`
2. Check build logs in Coolify (application > Deployments)
3. Verify Dockerfile path is set to `/Dockerfile`

### Health Check Fails

1. Verify the app starts on port 8080 (set via `ENV PORT=8080` in Dockerfile)
2. Check the `/health` endpoint works in container logs
3. Verify health check is configured: port `8080`, path `/health`, method `GET`
4. Check that **Ports Exposes** is set to `8080` (not `3000`) in General settings

### Database Connection Fails

1. Verify `DATABASE_URL` env var is set correctly
2. Use the **Internal URL** from Coolify (not external)
3. The app auto-converts `postgres://` to `postgresql+asyncpg://`

### SSL/Domain Issues

1. Verify A records point to the droplet IP: `dig api.mediancode.com`
2. Check DNS propagation: https://dnschecker.org
3. Coolify provisions Let's Encrypt certs automatically — may take a few minutes
4. If using Cloudflare, set proxy to **DNS only** (gray cloud) initially

### Build Fails During "Exporting Layers"

Each deployment builds a new Docker image. Old images accumulate and can fill the disk, causing builds to fail during the image export phase with exit code 255 and no clear error message.

**Immediate fix** — prune from your machine:

```bash
ssh median-server "docker system prune -a -f"
```

**Permanent fix** — enable automatic cleanup in Coolify:

1. Go to **Servers** (sidebar) > click your **localhost** server
2. Find the **Docker Cleanup** section
3. Enable scheduled cleanup of unused Docker resources

This should be configured during initial setup to prevent disk exhaustion.

### Server Resources

If the droplet runs low on memory:

```bash
ssh median-server
# Check usage
htop
docker stats

# Clear unused Docker resources
docker system prune -a -f
```

Consider upgrading to a $12/mo droplet (2GB RAM) if consistently hitting limits.

---

## Security Considerations

- **SSH**: Use SSH keys only (disable password auth)
- **Firewall**: DO Cloud Firewall — allow ports 22, 80, 443, and 8000 (Coolify UI) only
- **Updates**: `apt update && apt upgrade` periodically on the droplet
- **Coolify**: Keep Coolify updated via its built-in auto-update
- **HTTPS**: Automatic via Let's Encrypt (managed by Coolify/Traefik)
- **Database**: Ports not publicly exposed — external access via SSH tunnel only
- **CORS**: Restricted to `FRONTEND_URL` env var per environment
- **Auth**: Clerk JWT validation on API endpoints

---

## Costs

| Resource                          | Cost          |
| --------------------------------- | ------------- |
| DO Droplet (1 vCPU, 1GB RAM)     | $6/mo         |
| DO Droplet (1 vCPU, 2GB RAM)     | $12/mo        |
| Coolify                           | Free (OSS)    |
| SSL Certificates (Let's Encrypt)  | Free          |
| **Total**                         | **$6-12/mo**  |

> Compare to Railway (~$15-25/mo) or DO App Platform (~$24/mo) for the same two-environment setup.
