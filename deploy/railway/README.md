# Railway Deployment

Deploy the Median Code Backend to Railway with dev/prod environment separation.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Railway Project: median-code-backend                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────┐  ┌─────────────────────────────────┐   │
│  │   Production Environment        │  │   Development Environment       │   │
│  │   (branch: main)                │  │   (branch: develop)             │   │
│  │                                 │  │                                 │   │
│  │  ┌───────────┐  ┌───────────┐  │  │  ┌───────────┐  ┌───────────┐    │   │
│  │  │  Backend  │  │ PostgreSQL│  │  │  │  Backend  │  │ PostgreSQL│    │   │
│  │  │  Service  │  │  Database │  │  │  │  Service  │  │  Database │    │   │
│  │  └───────────┘  └───────────┘  │  │  └───────────┘  └───────────┘    │   │
│  │        │                       │  │        │                         │   │
│  │        ▼                       │  │        ▼                         │   │
│  │  api.mediancode.com            │  │  api.dev.mediancode.com          │   │
│  └─────────────────────────────────┘  └─────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
                    ┌─────────────────────────────────┐
                    │         GitHub Repository       │
                    │    median-code-backend          │
                    │                                 │
                    │  push main ──────► production   │
                    │  push develop ───► development  │
                    └─────────────────────────────────┘
```

## URL Structure

| Environment | Backend URL | Frontend URL | Branch | Clerk App |
|-------------|-------------|--------------|--------|-----------|
| **Production** | `api.mediancode.com` | `mediancode.com` | `main` | Production |
| **Development** | `api.dev.mediancode.com` | `dev.mediancode.com` | `develop` | Development |

---

## Initial Setup (One-Time)

### Prerequisites

- Railway account: https://railway.app
- Railway CLI installed: `brew install railway` or `npm install -g @railway/cli`
- GitHub repository with `main` and `develop` branches pushed
- Domain access for DNS configuration
- Two Clerk applications (production and development)

### Step 1: Create Railway Project

1. Go to https://railway.app/dashboard
2. Click **"New Project"**
3. Select **"Empty Project"**
4. Name it: `median-code-backend`

### Step 2: Create Development Environment

Railway starts with one environment (production). Create the second:

1. Click the environment dropdown (top left, shows "production")
2. Click **"New Environment"**
3. Name it: `development`

You now have two environments. Use the dropdown to switch between them.

### Step 3: Set Up Development Environment

Select **"development"** from the environment dropdown, then:

#### 3a. Add PostgreSQL Database

1. Click **"+ Create"** (top right)
2. Select **"Database"** → **"Add PostgreSQL"**
3. Wait for provisioning (~30 seconds)

#### 3b. Add Backend Service (Connect GitHub)

1. Click **"+ Create"** (top right)
2. Select **"GitHub Repo"**
3. Connect your GitHub account if prompted
4. Select `median-code-backend` repository
5. Railway will start building (it will fail - that's OK, we need to configure it)

#### 3c. Configure Backend Service Build

Click on the newly created backend service, then go to **Settings** tab:

1. Scroll to **"Source"** section
2. Set **"Branch"** to `develop`

3. Scroll to **"Config-as-code"** section (in the right sidebar)
4. Set **"Config File Path"** to `/deploy/railway/railway.toml`
   > This tells Railway to read its config from the deploy directory instead of the repo root.
   > Paths inside `railway.toml` (like `dockerfilePath`) are resolved relative to the repo root.

5. Scroll to **"Build"** section
6. Verify **"Builder"** is set to **"Dockerfile"** (should be auto-configured from `railway.toml`)

7. Click **"Redeploy"** (top right) to rebuild with correct settings

#### 3d. Set Environment Variables

Click on backend service → **Variables** tab:

Railway may suggest variables from your code. Configure these:

| Variable | Value | Type |
|----------|-------|------|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` | Reference |
| `ENVIRONMENT` | `${{RAILWAY_ENVIRONMENT_NAME}}` | Reference |
| `CLERK_FRONTEND_API_URL` | `https://your-dev-clerk.clerk.accounts.dev` | Manual |
| `FRONTEND_URL` | `https://dev.mediancode.com` | Manual |
| `GLOBAL_NAMESPACE_ID` | `namespace-global` | Manual |

**Important:**
- `DATABASE_URL` must be added as a reference variable — Railway does **not** auto-inject it
- `ENVIRONMENT` uses a Railway built-in that resolves to the environment name
- Do NOT add suggested `PYTHONPATH` - the Dockerfile handles this

### Step 4: Set Up Production Environment

Switch to **"production"** environment (use dropdown), then repeat Step 3 with these differences:

| Setting | Production Value | Type |
|---------|------------------|------|
| Branch | `main` | Setting |
| Config File Path | `deploy/railway/railway.toml` | Setting |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` | Reference |
| `ENVIRONMENT` | `${{RAILWAY_ENVIRONMENT_NAME}}` | Reference |
| `CLERK_FRONTEND_API_URL` | `https://your-prod-clerk.clerk.accounts.dev` | Manual |
| `FRONTEND_URL` | `https://app.mediancode.com` | Manual |
| `GLOBAL_NAMESPACE_ID` | `namespace-global` | Manual |

### Step 5: Configure Custom Domains

For each environment's backend service:

1. Click backend service → **Settings** tab
2. Scroll to **"Networking"** section
3. Click **"Generate Domain"** (creates `.up.railway.app` domain for testing)
4. Click **"+ Custom Domain"**
5. Enter domain:
   - Production: `api.mediancode.com`
   - Development: `api.dev.mediancode.com`
6. Note the Railway domain shown (needed for DNS)

### Step 6: Configure DNS

In your domain registrar (Cloudflare, Namecheap, etc.):

**Production:**
```
Type:   CNAME
Name:   api
Target: <your-production-service>.up.railway.app
```

**Development:**
```
Type:   CNAME
Name:   api.dev
Target: <your-development-service>.up.railway.app
```

> **Cloudflare users:** Set proxy to "DNS only" (gray cloud) initially until SSL is verified.

Wait 5-30 minutes for DNS propagation. Railway auto-provisions SSL.

### Step 7: Run Initial Database Migration

> **Note:** After initial setup, migrations run automatically on every deploy via the `preDeployCommand` in `railway.toml` (`alembic upgrade head`). The manual step below is only needed for the first deployment or troubleshooting.

```bash
# Link CLI to your Railway project
railway link
# Select your project when prompted

# Run migration for development
railway environment development
railway run alembic upgrade head

# Run migration for production
railway environment production
railway run alembic upgrade head
```

### Step 8: Verify Deployment

```bash
# Test development
curl https://api.dev.mediancode.com/health
# Expected: {"status":"healthy"}

# Test production
curl https://api.mediancode.com/health
# Expected: {"status":"healthy"}
```

---

## Deployment Flow (After Setup)

Deployments are automatic on push:

```
git push origin develop  →  Railway deploys to development
git push origin main     →  Railway deploys to production
```

### Typical Workflow

```bash
# Work on develop
git checkout develop
# ... make changes ...
git add .
git commit -m "feat: add new feature"
git push origin develop
# → Railway auto-deploys to api.dev.mediancode.com

# Promote to production
git checkout main
git merge develop
git push origin main
# → Railway auto-deploys to api.mediancode.com
```

---

## Database Migrations

### Run Migrations Manually

```bash
# Switch environment
railway environment development  # or: production

# Run migrations
railway run alembic upgrade head

# Check status
railway run alembic history
```

### Create New Migration

```bash
# Locally
poetry run alembic revision --autogenerate -m "add users table"

# Commit and push - then run on Railway
git add .
git commit -m "feat: add users table migration"
git push origin develop

railway environment development
railway run alembic upgrade head
```

---

## Local Testing Before Deploy

**Always test Docker builds locally before pushing:**

```bash
# Build
docker build -t median-test .

# Run (with test env vars)
docker run --rm -p 8080:80 \
  -e DATABASE_URL="postgresql+asyncpg://test:test@host.docker.internal:5432/test" \
  -e CLERK_FRONTEND_API_URL="https://test.clerk.accounts.dev" \
  -e FRONTEND_URL="https://test.com" \
  median-test

# Test health
curl http://localhost:8080/health
```

---

## Useful Commands

```bash
# Switch environments
railway environment development
railway environment production

# View logs
railway logs
railway logs --lines 100

# Manage variables
railway variables
railway variables set KEY=value

# Database access
railway connect postgres

# Run commands with Railway env
railway run alembic upgrade head
railway run python -c "print('test')"

# Open dashboard
railway open
railway status
```

---

## Troubleshooting

### Build Fails

1. **Test locally first:** `docker build -t test .`
2. Check Railway build logs (click deployment → "View logs")
3. Common issues:
   - Missing files in Dockerfile COPY
   - Poetry dependency resolution
   - Wrong Python version

### Health Check Fails

1. Check `/health` endpoint works locally
2. Verify `PORT` environment variable is used (Railway sets this)
3. Check startup logs for errors

### Database Connection Fails

```bash
# Verify DATABASE_URL exists
railway variables | grep DATABASE

# Should show something like:
# DATABASE_URL=postgresql://...
```

If missing, add the reference variable `${{Postgres.DATABASE_URL}}` to the backend service's Variables tab (see Step 3d).

**DATABASE_URL format:** Railway provides `postgres://` or `postgresql://` — the `settings.py` validator auto-converts to `postgresql+asyncpg://` for SQLAlchemy async. You do not need to manually adjust the scheme.

### DNS/SSL Issues

1. Verify CNAME is correct: `dig api.mediancode.com`
2. Check DNS propagation: https://dnschecker.org
3. Cloudflare: disable proxy temporarily (gray cloud)
4. Wait - Railway provisions SSL automatically once DNS resolves

---

## Security

- **HTTPS:** Automatic TLS via Railway
- **CORS:** Restricted to `FRONTEND_URL`
- **Rate Limiting:** 100 req/min (10 req/min for code generation)
- **Headers:** X-Frame-Options, HSTS, CSP
- **Auth:** Clerk JWT validation

---

## Costs

Railway Hobby Plan ($5/month):

| Resource | Estimated Cost |
|----------|---------------|
| Base plan | $5/month (includes $5 credit) |
| Compute (2 services) | ~$5-10/month |
| PostgreSQL (2 databases) | ~$5-10/month |
| **Total** | **~$15-25/month** |
