# Session Prompt: Global Namespace Edit Guard — Backend

## Context

You are tightening the Global namespace update guard in the backend API. Currently, the service rejects name/description changes for Global only when the new value differs from the current value. This must be changed to reject those fields entirely — the only mutable field on the Global namespace is `isDefault`.

The full implementation plan is at:

`/Users/evgesha/Documents/Projects/median-code-backend/docs/plans/2026-02-25-global-ns-edit-guard-impl.md`

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

- **Tasks**: 5 tasks (1 service change, 2 test tasks, 1 verification, 1 cleanup)
- **Parts**: Service layer, Tests
- **Estimated files**: 2 files to modify

## Key constraints

- Test command: `poetry run pytest tests/ -v`
- Single-file test: `poetry run pytest tests/test_api/test_services/test_namespace.py -v`
- The `NamespaceUpdate` Pydantic schema uses `alias="isDefault"` — in test code use the Python field name `is_default`
- The `provisioned_namespace` fixture returns the user's default Global namespace (name="Global", is_default=True)
- All tests are marked `@pytest.mark.asyncio` and `pytestmark = pytest.mark.integration`
