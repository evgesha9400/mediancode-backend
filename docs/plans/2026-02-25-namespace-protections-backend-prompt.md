# Session Prompt: Namespace Protections — Backend

## Context

You are implementing namespace protections on the backend: making the Global namespace fully read-only, blocking deletion of the default namespace, adding `is_default` support to namespace creation, enforcing unique namespace names per user, and adding a `locked` computed field to the API response.

The full implementation plan is at:

`/Users/evgesha/Documents/Projects/median-code-backend/docs/plans/2026-02-25-namespace-protections-impl.md`

Read the plan before doing anything.

## Instructions

Execute the plan task-by-task following these rules:

1. Read the full plan first
2. Execute task-by-task in order — do NOT skip ahead
3. Run tests after each task — fix failures before moving on
4. Commit after each task with the commit message specified in the plan
5. Zero failures is the only acceptable outcome
6. If a test fails, fix it before proceeding — do not accumulate debt

**REQUIRED SUB-SKILL:** Use superpowers:executing-plans to implement this plan.

## Scope

- **Tasks**: 9 tasks across 3 parts
- **Parts**: Schema & Model Changes, Service Layer Protections, Tests
- **Estimated files**: 5 files to create/modify (schema, model, service, migration, tests)

## Key constraints

- **Test command**: `poetry run pytest tests/test_api/test_services/test_namespace.py -x -q` (per task), `poetry run pytest -x -q` (final)
- **Migration**: Use `poetry run alembic revision --autogenerate` for schema changes, then `poetry run alembic upgrade head`
- **Python**: 3.13+, async SQLAlchemy, Pydantic v2
- **Commit standard**: Conventional commits with scopes: `api`, `test`
- **Do NOT include Co-Authored-By lines** in commits (backend repo convention)
- The `user_namespace` fixture in tests is the auto-provisioned "Global" namespace — use it for Global protection tests
- The `locked` field is a Pydantic `@computed_field`, NOT a database column
