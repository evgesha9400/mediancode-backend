> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans

# Backend Implementation Plan: Namespace Protections

## Goal

Add protections for the Global namespace (fully read-only, no delete), enforce unique namespace names per user, block deletion of the default namespace on the frontend, and allow setting `is_default` during namespace creation.

## Architecture

The Global namespace (auto-provisioned, named "Global") must be fully protected from edits and deletion. Protection is identified by name — since names are unique per user, only the provisioned one can be "Global".

Changes touch four layers:
1. **Schema** — Add `locked` computed field to response, `is_default` to create request
2. **Model** — Add unique constraint on `(user_id, name)`
3. **Service** — Add guards for Global namespace edits/deletion, handle `is_default` on create, validate duplicate names
4. **Tests** — Cover all new guards and edge cases

## Tech Stack

Python 3.13+, FastAPI, SQLAlchemy 2.x (async), Pydantic v2, Alembic, pytest

## Prerequisite

None — backend executes first.

---

## Part 1: Schema & Model Changes

### Task 1: Add `locked` computed field to NamespaceResponse

**File**: `src/api/schemas/namespace.py`

**Steps**:
1. Import `computed_field` from `pydantic`
2. Add a `@computed_field` property `locked` to `NamespaceResponse` that returns `self.name == "Global"`

**Before** (~line 37):
```python
class NamespaceResponse(BaseModel):
    id: UUID = Field(..., examples=["00000000-0000-0000-0000-000000000001"])
    name: str = Field(..., examples=["global"])
    description: str | None = Field(
        default=None, examples=["Immutable global templates and examples"]
    )
    is_default: bool = Field(..., alias="isDefault", examples=[False])

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
```

**After**:
```python
class NamespaceResponse(BaseModel):
    id: UUID = Field(..., examples=["00000000-0000-0000-0000-000000000001"])
    name: str = Field(..., examples=["global"])
    description: str | None = Field(
        default=None, examples=["Immutable global templates and examples"]
    )
    is_default: bool = Field(..., alias="isDefault", examples=[False])

    @computed_field  # type: ignore[prop-decorator]
    @property
    def locked(self) -> bool:
        """True for the provisioned Global namespace (fully read-only)."""
        return self.name == "Global"

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
```

**Test**: `poetry run pytest tests/test_api/test_services/test_namespace.py -x -q`
**Commit**: `feat(api): add locked computed field to NamespaceResponse`

---

### Task 2: Add `is_default` to NamespaceCreate schema

**File**: `src/api/schemas/namespace.py`

**Steps**:
1. Add `is_default: bool | None` field to `NamespaceCreate` with alias `"isDefault"` and default `None`
2. Add `model_config = ConfigDict(populate_by_name=True)` to `NamespaceCreate`

**Before** (~line 9):
```python
class NamespaceCreate(BaseModel):
    name: str = Field(..., examples=["my-api-project"])
    description: str | None = Field(
        default=None, examples=["Custom namespace for my API project"]
    )
```

**After**:
```python
class NamespaceCreate(BaseModel):
    name: str = Field(..., examples=["my-api-project"])
    description: str | None = Field(
        default=None, examples=["Custom namespace for my API project"]
    )
    is_default: bool | None = Field(default=None, alias="isDefault")

    model_config = ConfigDict(populate_by_name=True)
```

Note: Add `ConfigDict` to the imports at the top of the file if not already imported (it's already used by `NamespaceUpdate` and `NamespaceResponse`).

**Test**: `poetry run pytest tests/test_api/test_services/test_namespace.py -x -q`
**Commit**: `feat(api): add is_default to NamespaceCreate schema`

---

### Task 3: Add unique constraint on (user_id, name)

**Steps**:
1. Create a new Alembic migration: `poetry run alembic revision --autogenerate -m "add_unique_namespace_name_per_user"`
2. The migration should add a unique index on `(user_id, name)` to the `namespaces` table
3. Also add the constraint to the model's `__table_args__`

**Model change** in `src/api/models/database.py` (~line 115, inside `Namespace.__table_args__`):

**Before**:
```python
    __table_args__ = (
        Index(
            "ix_namespaces_one_default_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("is_default = true"),
        ),
    )
```

**After**:
```python
    __table_args__ = (
        Index(
            "ix_namespaces_one_default_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("is_default = true"),
        ),
        UniqueConstraint("user_id", "name", name="uq_namespaces_user_name"),
    )
```

Note: Import `UniqueConstraint` from `sqlalchemy` at the top of the file.

**Migration**: After editing the model, run:
```bash
poetry run alembic revision --autogenerate -m "add_unique_namespace_name_per_user"
```

Review the generated migration to confirm it creates the unique constraint. Then:
```bash
poetry run alembic upgrade head
```

**Test**: `poetry run pytest tests/test_api/test_services/test_namespace.py -x -q`
**Commit**: `feat(api): add unique constraint on namespace (user_id, name)`

---

## Part 2: Service Layer Protections

### Task 4: Protect Global namespace from updates

**File**: `src/api/services/namespace.py`

**Steps**:
1. In `update_namespace()`, add a guard at the top (after the docstring, before any field updates): if `namespace.name == "Global"`, reject changes to `name` and `description`
2. Allow `is_default` changes on the Global namespace (user can still set/unset it as default)

**Add before the existing `if data.name is not None:` line** (~line 88):

```python
    # Global namespace is read-only (name and description cannot be changed)
    if namespace.name == "Global":
        if data.name is not None and data.name != namespace.name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot rename the Global namespace",
            )
        if data.description is not None and data.description != namespace.description:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot modify the Global namespace description",
            )
```

**Test**: `poetry run pytest tests/test_api/test_services/test_namespace.py -x -q`
**Commit**: `feat(api): protect Global namespace from name and description changes`

---

### Task 5: Protect Global namespace from deletion

**File**: `src/api/services/namespace.py`

**Steps**:
1. In `delete_namespace()`, add a guard before the existing `is_default` check: if `namespace.name == "Global"`, raise 400

**Add before the existing `if namespace.is_default:` line** (~line 119):

```python
    if namespace.name == "Global":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the Global namespace",
        )
```

**Test**: `poetry run pytest tests/test_api/test_services/test_namespace.py -x -q`
**Commit**: `feat(api): protect Global namespace from deletion`

---

### Task 6: Handle is_default on create

**File**: `src/api/services/namespace.py`

**Steps**:
1. In `create_for_user()`, after creating the namespace, check if `data.is_default is True`
2. If so, clear `is_default` on all other user namespaces, then set `is_default=True` on the new one
3. Also block creation of a namespace named "Global" (reserved name)

**Replace** `create_for_user` method (~lines 55-70):

```python
    async def create_for_user(self, user_id: UUID, data: NamespaceCreate) -> Namespace:
        """Create a new namespace for a user.

        :param user_id: The authenticated user's ID.
        :param data: Namespace creation data.
        :returns: The created namespace.
        :raises HTTPException: If name is reserved or duplicate.
        """
        if data.name == "Global":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Cannot create a namespace named "Global" — this name is reserved',
            )

        namespace = Namespace(
            user_id=user_id,
            name=data.name,
            description=data.description,
        )

        if data.is_default is True:
            await self.db.execute(
                update(Namespace)
                .where(Namespace.user_id == user_id, Namespace.id != namespace.id)
                .values(is_default=False)
            )
            namespace.is_default = True

        self.db.add(namespace)
        await self.db.flush()
        await self.db.refresh(namespace)
        return namespace
```

Note: `update` should already be imported from `sqlalchemy` (used in `update_namespace`). Verify.

**Test**: `poetry run pytest tests/test_api/test_services/test_namespace.py -x -q`
**Commit**: `feat(api): handle is_default on create and block reserved Global name`

---

### Task 7: Add duplicate name validation on create and update

**File**: `src/api/services/namespace.py`

**Steps**:
1. Add a private helper `_name_exists_for_user(user_id, name, exclude_id=None)` that queries the DB
2. Call it in `create_for_user()` before inserting
3. Call it in `update_namespace()` before updating name (only if `data.name` differs from current)

**Add helper method** to `NamespaceService`:
```python
    async def _name_exists_for_user(
        self, user_id: UUID, name: str, exclude_id: UUID | None = None
    ) -> bool:
        """Check if a namespace name already exists for a user."""
        query = select(Namespace.id).where(
            Namespace.user_id == user_id, Namespace.name == name
        )
        if exclude_id:
            query = query.where(Namespace.id != exclude_id)
        result = await self.db.execute(query)
        return result.scalar() is not None
```

**In `create_for_user`**, after the "Global" check, add:
```python
        if await self._name_exists_for_user(user_id, data.name):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f'Namespace "{data.name}" already exists',
            )
```

**In `update_namespace`**, after the Global guard, before the existing `if data.name is not None:` block, add:
```python
        if data.name is not None and data.name != namespace.name:
            if await self._name_exists_for_user(namespace.user_id, data.name, exclude_id=namespace.id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f'Namespace "{data.name}" already exists',
                )
```

**Test**: `poetry run pytest tests/test_api/test_services/test_namespace.py -x -q`
**Commit**: `feat(api): add duplicate namespace name validation`

---

## Part 3: Tests

### Task 8: Add tests for all new protections

**File**: `tests/test_api/test_services/test_namespace.py`

**Add the following test cases** (append to the end of the file or into the appropriate test class):

```python
# --- Global namespace protection tests ---

async def test_cannot_rename_global_namespace(namespace_service, user_namespace):
    """Global namespace name cannot be changed."""
    with pytest.raises(HTTPException) as exc_info:
        await namespace_service.update_namespace(
            user_namespace, NamespaceUpdate(name="New Name")
        )
    assert exc_info.value.status_code == 400
    assert "Cannot rename the Global namespace" in exc_info.value.detail


async def test_cannot_modify_global_description(namespace_service, user_namespace):
    """Global namespace description cannot be changed."""
    with pytest.raises(HTTPException) as exc_info:
        await namespace_service.update_namespace(
            user_namespace, NamespaceUpdate(description="new desc")
        )
    assert exc_info.value.status_code == 400
    assert "Cannot modify the Global namespace description" in exc_info.value.detail


async def test_can_set_global_as_default(namespace_service, user_namespace):
    """Global namespace can still be set as default."""
    # Create another namespace and make it default
    other = await namespace_service.create_for_user(
        user_namespace.user_id, NamespaceCreate(name="Other")
    )
    await namespace_service.update_namespace(other, NamespaceUpdate(is_default=True))
    # Now set Global back as default — should succeed
    refreshed_global = await namespace_service.get_by_id_for_user(
        str(user_namespace.id), user_namespace.user_id
    )
    result = await namespace_service.update_namespace(
        refreshed_global, NamespaceUpdate(is_default=True)
    )
    assert result.is_default is True


async def test_cannot_delete_global_namespace(namespace_service, user_namespace):
    """Global namespace cannot be deleted regardless of default status."""
    # First make another namespace default so Global is not default
    other = await namespace_service.create_for_user(
        user_namespace.user_id, NamespaceCreate(name="Other")
    )
    await namespace_service.update_namespace(other, NamespaceUpdate(is_default=True))
    # Try to delete Global — should still fail
    refreshed_global = await namespace_service.get_by_id_for_user(
        str(user_namespace.id), user_namespace.user_id
    )
    with pytest.raises(HTTPException) as exc_info:
        await namespace_service.delete_namespace(refreshed_global)
    assert exc_info.value.status_code == 400
    assert "Cannot delete the Global namespace" in exc_info.value.detail


# --- Reserved name tests ---

async def test_cannot_create_namespace_named_global(namespace_service, user_namespace):
    """Cannot create another namespace named Global."""
    with pytest.raises(HTTPException) as exc_info:
        await namespace_service.create_for_user(
            user_namespace.user_id, NamespaceCreate(name="Global")
        )
    assert exc_info.value.status_code == 400
    assert "reserved" in exc_info.value.detail


# --- Create with is_default tests ---

async def test_create_namespace_with_is_default(namespace_service, user_namespace):
    """Creating with is_default=True clears default on others."""
    new_ns = await namespace_service.create_for_user(
        user_namespace.user_id,
        NamespaceCreate(name="New Default", is_default=True),
    )
    assert new_ns.is_default is True
    # Global should no longer be default
    refreshed_global = await namespace_service.get_by_id_for_user(
        str(user_namespace.id), user_namespace.user_id
    )
    assert refreshed_global.is_default is False


async def test_create_namespace_without_is_default(namespace_service, user_namespace):
    """Creating without is_default leaves existing default unchanged."""
    new_ns = await namespace_service.create_for_user(
        user_namespace.user_id, NamespaceCreate(name="Non-Default")
    )
    assert new_ns.is_default is False
    refreshed_global = await namespace_service.get_by_id_for_user(
        str(user_namespace.id), user_namespace.user_id
    )
    assert refreshed_global.is_default is True


# --- Duplicate name tests ---

async def test_cannot_create_duplicate_name(namespace_service, user_namespace):
    """Cannot create two namespaces with the same name."""
    await namespace_service.create_for_user(
        user_namespace.user_id, NamespaceCreate(name="Unique")
    )
    with pytest.raises(HTTPException) as exc_info:
        await namespace_service.create_for_user(
            user_namespace.user_id, NamespaceCreate(name="Unique")
        )
    assert exc_info.value.status_code == 400
    assert "already exists" in exc_info.value.detail


async def test_cannot_rename_to_existing_name(namespace_service, user_namespace):
    """Cannot rename a namespace to another existing name."""
    other = await namespace_service.create_for_user(
        user_namespace.user_id, NamespaceCreate(name="Other")
    )
    with pytest.raises(HTTPException) as exc_info:
        await namespace_service.update_namespace(
            other, NamespaceUpdate(name="Global")
        )
    assert exc_info.value.status_code == 400
    # Could be "reserved" or "already exists" — both are valid
    assert exc_info.value.status_code == 400


# --- Locked field in response tests ---

async def test_global_namespace_response_locked_true(user_namespace):
    """Global namespace response has locked=True."""
    response = NamespaceResponse.model_validate(user_namespace)
    assert response.locked is True


async def test_user_namespace_response_locked_false(namespace_service, user_namespace):
    """User-created namespace response has locked=False."""
    ns = await namespace_service.create_for_user(
        user_namespace.user_id, NamespaceCreate(name="Custom")
    )
    response = NamespaceResponse.model_validate(ns)
    assert response.locked is False
```

**Adapt the tests to the existing test file structure** — the file uses fixtures like `namespace_service`, `user_namespace` etc. Check the existing fixtures at the top of the test file and reuse them. The `user_namespace` fixture likely returns the auto-provisioned "Global" namespace.

**Test**: `poetry run pytest tests/test_api/test_services/test_namespace.py -x -v`
**Commit**: `test(api): add tests for namespace protections`

---

## Final Verification

### Task 9: Run full test suite

```bash
poetry run pytest -x -q
```

All tests must pass. Fix any failures before proceeding.

**Commit**: Only if fixes were needed — `fix(api): resolve test failures from namespace protections`

---

## Expected API Contract

After implementation, the API responses will look like:

### GET /namespaces
```json
[
  {
    "id": "abc-123",
    "name": "Global",
    "description": null,
    "isDefault": true,
    "locked": true
  },
  {
    "id": "def-456",
    "name": "My Project",
    "description": "Custom namespace",
    "isDefault": false,
    "locked": false
  }
]
```

### POST /namespaces (with isDefault)
**Request**:
```json
{
  "name": "My Project",
  "description": "Custom namespace",
  "isDefault": true
}
```
**Response** (201):
```json
{
  "id": "def-456",
  "name": "My Project",
  "description": "Custom namespace",
  "isDefault": true,
  "locked": false
}
```

### PUT /namespaces/{id} on Global namespace
**Request**: `{"name": "Renamed"}`
**Response** (400): `{"detail": "Cannot rename the Global namespace"}`

### DELETE /namespaces/{id} on Global namespace
**Response** (400): `{"detail": "Cannot delete the Global namespace"}`

### DELETE /namespaces/{id} on default namespace
**Response** (400): `{"detail": "Cannot delete the default namespace"}`

### POST /namespaces with name "Global"
**Response** (400): `{"detail": "Cannot create a namespace named \"Global\" — this name is reserved"}`

### POST /namespaces with duplicate name
**Response** (400): `{"detail": "Namespace \"My Project\" already exists"}`
