# Prompt: Implement CI/CD for Coolify Deployment

Use this prompt with Claude Code to implement GitHub Actions CI/CD for the Median Code Backend deployed on Coolify.

---

## Context

- **Project**: Median Code Backend (FastAPI + PostgreSQL)
- **Repo**: median-code-backend
- **Branches**: `main` (production), `develop` (development)
- **Deployment**: Coolify on a Digital Ocean droplet (self-hosted)
- **Coolify auto-deploys** on push via GitHub webhooks — CI/CD should gate deployments by running checks first
- **Existing commands**: `make test`, `poetry run black src/`, `poetry run pytest`
- **Python version**: 3.13
- **Package manager**: Poetry

## What to Implement

Create a GitHub Actions CI/CD pipeline with the following:

### 1. CI Pipeline (`.github/workflows/ci.yml`)

Runs on every push to `develop` and `main`, and on all PRs targeting those branches.

**Jobs:**

#### a) Lint & Format Check
- Install Python 3.13 + Poetry
- Install dependencies via `poetry install`
- Run `poetry run black --check src/` to verify formatting
- Run `poetry run ruff check src/` if ruff is installed, otherwise skip

#### b) Test
- Install Python 3.13 + Poetry
- Install dependencies
- Spin up a PostgreSQL 16 service container for tests
- Set `DATABASE_URL` env var pointing to the service container
- Run `poetry run pytest tests/ -v`
- Tests should run against the service container DB

#### c) Docker Build Smoke Test
- Run `docker build -t median-code-backend-test .` to verify the Dockerfile builds
- Do NOT push the image anywhere — just verify it builds

### 2. Branch Protection Rules

Document (do NOT auto-configure) the recommended GitHub branch protection rules:

- `main` branch:
  - Require PR before merging
  - Require CI checks to pass (lint, test, docker build)
  - Require 1 approval (optional for solo dev)
  - No direct pushes

- `develop` branch:
  - Require CI checks to pass
  - Allow direct pushes (for fast iteration)

### 3. Deployment Flow

Coolify handles deployment via webhooks — the GitHub Actions pipeline should NOT trigger deployments directly. The flow is:

```
Push to develop
  → GitHub Actions runs CI (lint, test, build)
  → If CI passes + webhook fires → Coolify deploys to dev

PR from develop → main
  → GitHub Actions runs CI on PR
  → Merge PR
  → GitHub Actions runs CI on main
  → Webhook fires → Coolify deploys to production
```

If you want to add an optional deployment gate (only deploy after CI passes), implement this:

- Add a step that calls the Coolify API to trigger deployment only after CI succeeds
- This requires a `COOLIFY_API_TOKEN` and `COOLIFY_WEBHOOK_URL` secret
- Coolify API docs: https://coolify.io/docs/api/deploy-webhook
- Make this an OPTIONAL enhancement — the basic setup should work without it

### 4. Caching

- Cache Poetry dependencies between runs using `actions/cache` with the Poetry virtualenv path
- Cache Docker layers if possible

## Constraints

- Keep it simple — don't over-engineer
- Use the latest stable versions of GitHub Actions
- PostgreSQL service container should use `postgres:16-alpine` to match the dev setup
- All secrets (if any) should be documented but NOT hardcoded
- The pipeline should complete in under 5 minutes for a typical run
- Do NOT modify the Dockerfile, application code, or Coolify configuration
- Do NOT create a separate CD workflow — Coolify handles deployment

## Files to Create

1. `.github/workflows/ci.yml` — the CI pipeline
2. Update `docs/COOLIFY_DEPLOYMENT.md` — add a "CI/CD" section referencing the GitHub Actions pipeline and branch protection rules

## Files to Read First

Before implementing, read these files to understand the project structure:

- `pyproject.toml` — dependencies, scripts, tool configs
- `Makefile` — existing commands
- `Dockerfile` — build process
- `src/api/settings.py` — env var configuration
- `tests/` — test structure and what's being tested
- `docs/COOLIFY_DEPLOYMENT.md` — current deployment docs
