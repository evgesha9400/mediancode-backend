# Implementation Plan: Global Namespace Edit Guard (Backend)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans

## Goal

Tighten the Global namespace update guard so the API only accepts `isDefault` changes — reject `name` and `description` fields entirely, even if values match the current state.

## Architecture

The backend already has partial guards in `NamespaceService.update_namespace()` that reject name/description changes for the Global namespace *when the new value differs*. This plan tightens the guard to reject those fields entirely (even if unchanged), making the API contract unambiguous: the only mutable field on the Global namespace is `isDefault`.

No database, schema, or migration changes are required.

## Tech Stack

Python 3.12, FastAPI, SQLAlchemy 2, Pydantic v2, pytest + pytest-asyncio

## Prerequisite

None — backend goes first.

## Tasks

### Task 1: Tighten Global namespace update guard in service

**Files to modify:**
- `src/api/services/namespace.py` (~line 106, `update_namespace` method)

**Steps:**

1. Replace the current Global guard block (lines 106-120):

**Before:**
```python
# Global namespace is read-only (name and description cannot be changed)
if namespace.name == "Global":
    if data.name is not None and data.name != namespace.name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot rename the Global namespace",
        )
    if (
        data.description is not None
        and data.description != namespace.description
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify the Global namespace description",
        )
```

**After:**
```python
# Global namespace: only isDefault can be changed
if namespace.name == "Global":
    if data.name is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify the Global namespace name",
        )
    if data.description is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify the Global namespace description",
        )
```

The key difference: we no longer check `data.name != namespace.name` or `data.description != namespace.description`. If the field is present at all, it's rejected.

**Test command:**
```bash
poetry run pytest tests/test_api/test_services/test_namespace.py -v -k "global"
```

**Commit:**
```
feat(namespaces): tighten Global namespace update guard

- Reject name/description fields entirely on Global namespace
  update, even if values match current state
- Only isDefault is accepted as a mutable field
```

---

### Task 2: Update existing tests and add new coverage

**Files to modify:**
- `tests/test_api/test_services/test_namespace.py`

**Steps:**

1. Update `test_cannot_rename_global_namespace` — keep as-is (still tests renaming with a different name, which should still be rejected).

2. Update `test_cannot_modify_global_description` — keep as-is (still tests changing description to a different value).

3. Add a new test: `test_cannot_send_same_name_on_global_namespace` — sends `NamespaceUpdate(name="Global")` (same value) and expects 400:

```python
@pytest.mark.asyncio
async def test_cannot_send_same_name_on_global_namespace(
    provisioned_namespace: Namespace,
    namespace_service: NamespaceService,
):
    """Sending name field on Global namespace is rejected even if value matches."""
    data = NamespaceUpdate(name="Global")

    with pytest.raises(HTTPException) as exc_info:
        await namespace_service.update_namespace(provisioned_namespace, data)

    assert exc_info.value.status_code == 400
    assert "Cannot modify the Global namespace name" in exc_info.value.detail
```

4. Add a new test: `test_cannot_send_same_description_on_global_namespace` — sends `NamespaceUpdate(description=provisioned_namespace.description)` and expects 400:

```python
@pytest.mark.asyncio
async def test_cannot_send_same_description_on_global_namespace(
    provisioned_namespace: Namespace,
    namespace_service: NamespaceService,
):
    """Sending description field on Global namespace is rejected even if value matches."""
    data = NamespaceUpdate(description=provisioned_namespace.description)

    with pytest.raises(HTTPException) as exc_info:
        await namespace_service.update_namespace(provisioned_namespace, data)

    assert exc_info.value.status_code == 400
    assert "Cannot modify the Global namespace description" in exc_info.value.detail
```

5. Add a new test: `test_global_namespace_update_only_is_default` — sends `NamespaceUpdate(isDefault=True)` with no name/description and expects success:

```python
@pytest.mark.asyncio
async def test_global_namespace_update_only_is_default(
    provisioned_namespace: Namespace,
    namespace_service: NamespaceService,
):
    """Global namespace accepts isDefault-only update."""
    data = NamespaceUpdate(is_default=True)
    updated = await namespace_service.update_namespace(provisioned_namespace, data)

    assert updated.is_default is True
    assert updated.name == "Global"
```

Place these new tests immediately after the existing `test_can_set_global_as_default` test in the "Global Namespace Protection Tests" section.

**Test command:**
```bash
poetry run pytest tests/test_api/test_services/test_namespace.py -v
```

**Commit:**
```
test(namespaces): add tests for tightened Global update guard

- Verify same-value name/description are rejected on Global
- Verify isDefault-only update succeeds on Global
```

---

### Task 3: Update existing test assertion

**Files to modify:**
- `tests/test_api/test_services/test_namespace.py`

**Steps:**

1. Find `test_update_default_namespace_name` (tests renaming Global). Update the expected error message from `"Cannot rename the Global namespace"` to `"Cannot modify the Global namespace name"` to match the new wording:

```python
assert "Cannot modify the Global namespace name" in exc_info.value.detail
```

**Test command:**
```bash
poetry run pytest tests/test_api/test_services/test_namespace.py -v
```

**Commit:**
```
fix(tests): update assertion to match new Global guard message
```

---

### Task 4: Final verification

**Test command:**
```bash
poetry run pytest tests/ -v
```

All tests must pass. Zero failures.

---

### Task 5: Cleanup

Delete the plan file:

```bash
rm docs/plans/2026-02-25-global-ns-edit-guard-impl.md
rm docs/plans/2026-02-25-global-ns-edit-guard-backend-prompt.md
```

**Commit:**
```
chore(plans): remove completed Global namespace edit guard plan
```

---

## Expected API Contract

After implementation, the namespace update endpoint behaves as follows:

### Global namespace — allowed update:
```
PUT /v1/namespaces/{global-ns-id}
Content-Type: application/json

{
  "isDefault": true
}
```
Response: `200 OK` with updated namespace (isDefault=true, locked=true)

### Global namespace — rejected update (name provided):
```
PUT /v1/namespaces/{global-ns-id}
Content-Type: application/json

{
  "name": "Global",
  "isDefault": true
}
```
Response: `400 Bad Request` — `"Cannot modify the Global namespace name"`

### Global namespace — rejected update (description provided):
```
PUT /v1/namespaces/{global-ns-id}
Content-Type: application/json

{
  "description": "anything"
}
```
Response: `400 Bad Request` — `"Cannot modify the Global namespace description"`

### Non-global namespace — always fully editable:
```
PUT /v1/namespaces/{user-ns-id}
Content-Type: application/json

{
  "name": "new-name",
  "description": "new description",
  "isDefault": true
}
```
Response: `200 OK` — all fields updated, regardless of whether namespace is default
