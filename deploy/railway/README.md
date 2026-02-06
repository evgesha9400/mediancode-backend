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
- GitHub repository with `main` and `develop` branches
- Domain access for DNS configuration
- Two Clerk applications (production and development)

### Step 1: Create Railway Project

**Option A: Via CLI**
```bash
railway login
railway init
# Select "Empty Project"
# Name it: median-code-backend
```

**Option B: Via Dashboard**
1. Go to https://railway.app/dashboard
2. Click "New Project"
3. Select "Empty Project"
4. Name it: `median-code-backend`

### Step 2: Create Environments

Railway Dashboard → Your Project → Settings → Environments

1. You start with one environment (usually called `production`)
2. Click "New Environment"
3. Name it: `development`

You should now have two environments:
- `production`
- `development`

### Step 3: Connect GitHub Repository

Railway Dashboard → Your Project → Settings → Source

1. Click "Connect GitHub"
2. Authorize Railway to access your repositories
3. Select the `median-code-backend` repository
4. Configure deployment triggers:

| Environment | Branch | Auto-Deploy |
|-------------|--------|-------------|
| `production` | `main` | Yes |
| `development` | `develop` | Yes |

### Step 4: Add PostgreSQL Database (Each Environment)

Repeat for both `production` and `development` environments:

1. Railway Dashboard → Select environment (top dropdown)
2. Click "+ New" in the project canvas
3. Select "Database" → "PostgreSQL"
4. Wait for provisioning (~30 seconds)

Railway automatically creates `DATABASE_URL` variable.

### Step 5: Create Backend Service (Each Environment)

After connecting GitHub (Step 3), Railway should auto-create a service. If not:

1. Railway Dashboard → Select environment
2. Click "+ New" → "GitHub Repo"
3. Select `median-code-backend`
4. Railway detects the Dockerfile and configures automatically

### Step 6: Set Environment Variables

For each environment, click the Backend service → Variables tab → Add these:

**Production Environment:**
```
CLERK_FRONTEND_API_URL=https://your-prod-app.clerk.accounts.dev
FRONTEND_URL=https://mediancode.com
GLOBAL_NAMESPACE_ID=namespace-global
```

**Development Environment:**
```
CLERK_FRONTEND_API_URL=https://your-dev-app.clerk.accounts.dev
FRONTEND_URL=https://dev.mediancode.com
GLOBAL_NAMESPACE_ID=namespace-global
```

> **Note:** `DATABASE_URL` is automatically set by Railway when you add PostgreSQL. Do not add it manually.

### Step 7: Configure Health Check

For each environment's Backend service:

1. Click Backend service → Settings
2. Under "Deploy" section:
   - **Healthcheck Path:** `/health`
   - **Healthcheck Timeout:** `30` seconds

### Step 8: Add Custom Domains

For each environment's Backend service:

1. Click Backend service → Settings → Domains
2. Click "Generate Domain" (creates a `.up.railway.app` domain)
3. Click "Add Custom Domain"
4. Enter the domain:
   - Production: `api.mediancode.com`
   - Development: `api.dev.mediancode.com`
5. Railway shows the required DNS configuration

### Step 9: Configure DNS

In your domain registrar (e.g., Cloudflare, Namecheap, GoDaddy):

**Production:**
```
Type: CNAME
Name: api
Target: <railway-provided-domain>.up.railway.app
```

**Development:**
```
Type: CNAME
Name: api.dev
Target: <railway-provided-domain>.up.railway.app
```

> **Note:** If using Cloudflare, set proxy status to "DNS only" (gray cloud) initially until SSL is verified.

Wait for DNS propagation (5-30 minutes). Railway will automatically provision SSL certificates.

### Step 10: Run Initial Database Migration

```bash
# Link to your Railway project
railway link

# For production
railway environment production
railway run alembic upgrade head

# For development
railway environment development
railway run alembic upgrade head
```

### Step 11: Verify Deployment

Test both environments:

```bash
# Production
curl https://api.mediancode.com/health
# Expected: {"status":"healthy"}

# Development
curl https://api.dev.mediancode.com/health
# Expected: {"status":"healthy"}
```

---

## Deployment Flow (After Setup)

Once setup is complete, deployment is automatic:

```
Push to develop  →  Railway auto-deploys  →  api.dev.mediancode.com
Push to main     →  Railway auto-deploys  →  api.mediancode.com
```

### Typical Workflow

```bash
# 1. Work on develop branch
git checkout develop
# ... make changes ...
git add .
git commit -m "feat: add new feature"
git push origin develop
# Railway auto-deploys to development

# 2. When ready for production
git checkout main
git merge develop
git push origin main
# Railway auto-deploys to production
```

---

## Manual Deployment (Optional)

If you need to deploy without pushing to GitHub, use the deploy script:

### Setup Local Environment Files

```bash
# Copy examples
cp .env.development.example .env.development
cp .env.production.example .env.production

# Edit with your actual values
# - CLERK_FRONTEND_API_URL
# - FRONTEND_URL
```

### Deploy Commands

```bash
make deploy-dev          # Deploy to development
make deploy-prod         # Deploy to production
make deploy-dev-dry      # Preview development deploy (no changes)
make deploy-prod-dry     # Preview production deploy (no changes)
```

The deploy script will:
1. Validate Railway CLI and login
2. Load variables from `.env.{environment}`
3. Sync variables to Railway
4. Check PostgreSQL is provisioned
5. Run database migrations
6. Deploy and verify health

---

## Database Migrations

### Auto-Run on Deploy (Recommended)

Add to Railway service settings (Settings → Deploy):

**Start Command:**
```
alembic upgrade head && uvicorn src.api.main:app --host 0.0.0.0 --port $PORT
```

### Manual Migration

```bash
# Switch to target environment
railway environment production  # or: development

# Run migrations
railway run alembic upgrade head

# Check status
railway run alembic history

# Create new migration (locally)
poetry run alembic revision --autogenerate -m "description"
```

---

## Useful Commands

```bash
# Environment management
railway environment production    # Switch to production
railway environment development   # Switch to development

# Logs and monitoring
railway logs                      # View logs (follow mode)
railway logs --lines 100          # View last 100 lines

# Variables
railway variables                 # List all variables
railway variables set KEY=value   # Set a variable

# Database
railway connect postgres          # Interactive psql session
railway run alembic upgrade head  # Run migrations

# General
railway open                      # Open dashboard in browser
railway status                    # Show project status
```

---

## Vercel Frontend Integration

Set these environment variables in Vercel for your frontend:

**Production (vercel.com → Project → Settings → Environment Variables):**
```
NEXT_PUBLIC_API_URL=https://api.mediancode.com
```

**Preview/Development:**
```
NEXT_PUBLIC_API_URL=https://api.dev.mediancode.com
```

---

## Troubleshooting

### Deployment Fails

```bash
# Check logs
railway logs

# Verify environment variables
railway variables

# Test locally with Railway env
railway run python -c "from api.settings import get_settings; print(get_settings())"
```

### Database Connection Issues

```bash
# Verify DATABASE_URL exists
railway variables | grep DATABASE

# Test connection
railway run python -c "from api.database import engine; print(engine.url)"
```

### Health Check Fails

1. Verify `/health` endpoint works locally
2. Check that port is correctly read from `$PORT` environment variable
3. Review Railway logs for startup errors

### DNS/SSL Issues

1. Verify CNAME record is correct
2. Wait for DNS propagation (use https://dnschecker.org)
3. If using Cloudflare, temporarily disable proxy (gray cloud)
4. Railway auto-provisions SSL once DNS resolves

---

## Security

- **HTTPS:** Automatic TLS via Railway
- **CORS:** Restricted to `FRONTEND_URL` only
- **Rate Limiting:** 100 req/min standard, 10 req/min for code generation
- **Headers:** X-Frame-Options, HSTS, CSP
- **Auth:** Clerk JWT validation

---

## Costs

Railway Starter Plan ($5/month):

| Resource | Estimated Cost |
|----------|---------------|
| Base plan | $5/month |
| Compute (2 services) | ~$5-10/month |
| PostgreSQL (2 databases) | ~$5-10/month |
| **Total** | **~$15-25/month** |

Usage-based pricing:
- Compute: $0.000231/minute
- PostgreSQL: $0.000231/minute + storage
