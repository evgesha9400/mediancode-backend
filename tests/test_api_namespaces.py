# tests/test_api_namespaces.py
"""Integration tests for namespace CRUD endpoints."""

import pytest

pytestmark = pytest.mark.integration

import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.database import ApiModel, FieldModel, Namespace, ObjectDefinition
from api.schemas.namespace import NamespaceCreate, NamespaceUpdate
from api.services.namespace import NamespaceService
from conftest import TEST_USER_ID


# --- Fixtures ---


@pytest_asyncio.fixture
async def namespace_service(db_session: AsyncSession):
    """Create a NamespaceService instance."""
    return NamespaceService(db_session)


@pytest_asyncio.fixture
async def user_namespace(db_session: AsyncSession, provisioned_namespace: Namespace):
    """Create a user-owned (unlocked) namespace for namespace tests."""
    namespace = Namespace(
        name="Custom Namespace",
        description="User-owned namespace for testing",
        user_id=TEST_USER_ID,
    )
    db_session.add(namespace)
    await db_session.commit()
    await db_session.refresh(namespace)

    yield namespace

    await db_session.execute(delete(Namespace).where(Namespace.id == namespace.id))
    await db_session.commit()


@pytest_asyncio.fixture
async def namespace_with_field(
    db_session: AsyncSession,
    user_namespace: Namespace,
):
    """Create a namespace that contains a field entity."""
    from api.models.database import TypeModel
    from api.settings import get_settings

    settings = get_settings()

    # Get the system str type for the field
    result = await db_session.execute(
        select(TypeModel).where(
            TypeModel.namespace_id == settings.system_namespace_id,
            TypeModel.name == "str",
        )
    )
    str_type = result.scalar_one()

    field = FieldModel(
        namespace_id=user_namespace.id,
        user_id=TEST_USER_ID,
        name="test_field",
        type_id=str_type.id,
    )
    db_session.add(field)
    await db_session.commit()
    await db_session.refresh(field)

    yield user_namespace

    # Cleanup field before namespace fixture cleans up namespace
    await db_session.execute(delete(FieldModel).where(FieldModel.id == field.id))
    await db_session.commit()


@pytest_asyncio.fixture
async def namespace_with_object(
    db_session: AsyncSession,
    user_namespace: Namespace,
):
    """Create a namespace that contains an object entity."""
    obj = ObjectDefinition(
        namespace_id=user_namespace.id,
        user_id=TEST_USER_ID,
        name="TestObject",
    )
    db_session.add(obj)
    await db_session.commit()
    await db_session.refresh(obj)

    yield user_namespace

    # Cleanup object before namespace fixture cleans up namespace
    await db_session.execute(
        delete(ObjectDefinition).where(ObjectDefinition.id == obj.id)
    )
    await db_session.commit()


@pytest_asyncio.fixture
async def namespace_with_api(
    db_session: AsyncSession,
    user_namespace: Namespace,
):
    """Create a namespace that contains an API entity."""
    api = ApiModel(
        namespace_id=user_namespace.id,
        user_id=TEST_USER_ID,
        title="Test API",
        version="1.0.0",
    )
    db_session.add(api)
    await db_session.commit()
    await db_session.refresh(api)

    yield user_namespace

    # Cleanup api before namespace fixture cleans up namespace
    await db_session.execute(delete(ApiModel).where(ApiModel.id == api.id))
    await db_session.commit()


# --- Tests: List namespaces ---


@pytest.mark.asyncio
async def test_list_namespaces_returns_user_namespaces(
    provisioned_namespace: Namespace,
    namespace_service: NamespaceService,
):
    """Listing namespaces returns all namespaces owned by the user."""
    namespaces = await namespace_service.list_for_user(TEST_USER_ID)

    assert len(namespaces) >= 1
    assert all(ns.user_id == TEST_USER_ID for ns in namespaces)


@pytest.mark.asyncio
async def test_list_namespaces_includes_default_namespace(
    provisioned_namespace: Namespace,
    namespace_service: NamespaceService,
):
    """Listing namespaces includes the user's default (Global) namespace."""
    namespaces = await namespace_service.list_for_user(TEST_USER_ID)

    default_namespaces = [ns for ns in namespaces if ns.is_default]
    assert len(default_namespaces) == 1
    assert default_namespaces[0].name == "Global"
    assert default_namespaces[0].locked is True


@pytest.mark.asyncio
async def test_list_namespaces_includes_custom_namespace(
    user_namespace: Namespace,
    namespace_service: NamespaceService,
):
    """Listing namespaces includes user-created custom namespaces."""
    namespaces = await namespace_service.list_for_user(TEST_USER_ID)

    namespace_names = {ns.name for ns in namespaces}
    assert "Custom Namespace" in namespace_names


@pytest.mark.asyncio
async def test_list_namespaces_excludes_other_users(
    db_session: AsyncSession,
    provisioned_namespace: Namespace,
    namespace_service: NamespaceService,
):
    """Listing namespaces does not return namespaces owned by other users."""
    other_user_ns = Namespace(
        name="Other User Namespace",
        user_id="other_user_id",
    )
    db_session.add(other_user_ns)
    await db_session.flush()

    namespaces = await namespace_service.list_for_user(TEST_USER_ID)

    namespace_ids = {ns.id for ns in namespaces}
    assert other_user_ns.id not in namespace_ids

    # Cleanup
    await db_session.execute(delete(Namespace).where(Namespace.id == other_user_ns.id))
    await db_session.flush()


# --- Tests: Get namespace by ID ---


@pytest.mark.asyncio
async def test_get_namespace_by_id(
    user_namespace: Namespace,
    namespace_service: NamespaceService,
):
    """Getting a namespace by ID returns the correct namespace."""
    result = await namespace_service.get_by_id_for_user(
        str(user_namespace.id), TEST_USER_ID
    )

    assert result is not None
    assert result.id == user_namespace.id
    assert result.name == "Custom Namespace"
    assert result.description == "User-owned namespace for testing"


@pytest.mark.asyncio
async def test_get_namespace_by_id_not_found(
    provisioned_namespace: Namespace,
    namespace_service: NamespaceService,
):
    """Getting a non-existent namespace returns None."""
    import uuid

    fake_id = str(uuid.uuid4())
    result = await namespace_service.get_by_id_for_user(fake_id, TEST_USER_ID)

    assert result is None


@pytest.mark.asyncio
async def test_get_namespace_by_id_wrong_user(
    user_namespace: Namespace,
    namespace_service: NamespaceService,
):
    """Getting a namespace owned by another user returns None."""
    result = await namespace_service.get_by_id_for_user(
        str(user_namespace.id), "different_user_id"
    )

    assert result is None


@pytest.mark.asyncio
async def test_get_default_namespace_by_id(
    provisioned_namespace: Namespace,
    namespace_service: NamespaceService,
):
    """Getting the default (Global) namespace by ID works correctly."""
    result = await namespace_service.get_by_id_for_user(
        str(provisioned_namespace.id), TEST_USER_ID
    )

    assert result is not None
    assert result.is_default is True
    assert result.locked is True
    assert result.name == "Global"


# --- Tests: Create namespace ---


@pytest.mark.asyncio
async def test_create_namespace(
    provisioned_namespace: Namespace,
    namespace_service: NamespaceService,
):
    """Creating a namespace stores the correct data."""
    data = NamespaceCreate(name="New Project", description="A new project namespace")
    namespace = await namespace_service.create_for_user(TEST_USER_ID, data)

    assert namespace.name == "New Project"
    assert namespace.description == "A new project namespace"
    assert namespace.user_id == TEST_USER_ID
    assert namespace.locked is False
    assert namespace.is_default is False
    assert namespace.id is not None


@pytest.mark.asyncio
async def test_create_namespace_without_description(
    provisioned_namespace: Namespace,
    namespace_service: NamespaceService,
):
    """Creating a namespace without a description sets it to None."""
    data = NamespaceCreate(name="No Description")
    namespace = await namespace_service.create_for_user(TEST_USER_ID, data)

    assert namespace.name == "No Description"
    assert namespace.description is None
    assert namespace.locked is False


@pytest.mark.asyncio
async def test_create_namespace_is_not_locked(
    provisioned_namespace: Namespace,
    namespace_service: NamespaceService,
):
    """User-created namespaces are never locked."""
    data = NamespaceCreate(name="Unlocked Namespace")
    namespace = await namespace_service.create_for_user(TEST_USER_ID, data)

    assert namespace.locked is False


@pytest.mark.asyncio
async def test_create_namespace_is_not_default(
    provisioned_namespace: Namespace,
    namespace_service: NamespaceService,
):
    """User-created namespaces are never marked as default."""
    data = NamespaceCreate(name="Not Default")
    namespace = await namespace_service.create_for_user(TEST_USER_ID, data)

    assert namespace.is_default is False


@pytest.mark.asyncio
async def test_create_namespace_appears_in_list(
    provisioned_namespace: Namespace,
    namespace_service: NamespaceService,
):
    """A newly created namespace appears in the user's namespace list."""
    data = NamespaceCreate(name="Listed Namespace")
    created = await namespace_service.create_for_user(TEST_USER_ID, data)

    namespaces = await namespace_service.list_for_user(TEST_USER_ID)
    namespace_ids = {ns.id for ns in namespaces}

    assert created.id in namespace_ids


@pytest.mark.asyncio
async def test_create_namespace_with_duplicate_name(
    user_namespace: Namespace,
    namespace_service: NamespaceService,
):
    """Creating a namespace with the same name as an existing one is allowed.

    No unique constraint on name per user, so duplicate names are permitted.
    """
    data = NamespaceCreate(
        name="Custom Namespace", description="Another namespace with same name"
    )
    namespace = await namespace_service.create_for_user(TEST_USER_ID, data)

    assert namespace.name == "Custom Namespace"
    assert namespace.id != user_namespace.id


# --- Tests: Update namespace ---


@pytest.mark.asyncio
async def test_update_namespace_name(
    user_namespace: Namespace,
    namespace_service: NamespaceService,
):
    """Updating a namespace name changes it correctly."""
    data = NamespaceUpdate(name="Updated Name")
    updated = await namespace_service.update_namespace(user_namespace, data)

    assert updated.name == "Updated Name"
    assert updated.description == "User-owned namespace for testing"


@pytest.mark.asyncio
async def test_update_namespace_description(
    user_namespace: Namespace,
    namespace_service: NamespaceService,
):
    """Updating a namespace description changes it correctly."""
    data = NamespaceUpdate(description="Updated description")
    updated = await namespace_service.update_namespace(user_namespace, data)

    assert updated.name == "Custom Namespace"
    assert updated.description == "Updated description"


@pytest.mark.asyncio
async def test_update_namespace_name_and_description(
    user_namespace: Namespace,
    namespace_service: NamespaceService,
):
    """Updating both name and description in one call works correctly."""
    data = NamespaceUpdate(name="New Name", description="New description")
    updated = await namespace_service.update_namespace(user_namespace, data)

    assert updated.name == "New Name"
    assert updated.description == "New description"


@pytest.mark.asyncio
async def test_update_namespace_no_changes(
    user_namespace: Namespace,
    namespace_service: NamespaceService,
):
    """Updating with no fields set preserves existing values."""
    data = NamespaceUpdate()
    updated = await namespace_service.update_namespace(user_namespace, data)

    assert updated.name == "Custom Namespace"
    assert updated.description == "User-owned namespace for testing"


@pytest.mark.asyncio
async def test_update_locked_namespace_raises_error(
    provisioned_namespace: Namespace,
    namespace_service: NamespaceService,
):
    """Updating a locked namespace raises an HTTPException."""
    data = NamespaceUpdate(name="Hacked Name")

    with pytest.raises(HTTPException) as exc_info:
        await namespace_service.update_namespace(provisioned_namespace, data)

    assert exc_info.value.status_code == 400
    assert "Cannot modify locked namespace" in exc_info.value.detail


# --- Tests: Delete namespace ---


@pytest.mark.asyncio
async def test_delete_empty_namespace(
    db_session: AsyncSession,
    user_namespace: Namespace,
    namespace_service: NamespaceService,
):
    """Deleting an empty namespace succeeds."""
    namespace_id = user_namespace.id

    await namespace_service.delete_namespace(user_namespace)
    await db_session.flush()

    result = await db_session.execute(
        select(Namespace).where(Namespace.id == namespace_id)
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_delete_locked_namespace_raises_error(
    provisioned_namespace: Namespace,
    namespace_service: NamespaceService,
):
    """Deleting the locked default namespace raises an HTTPException."""
    with pytest.raises(HTTPException) as exc_info:
        await namespace_service.delete_namespace(provisioned_namespace)

    assert exc_info.value.status_code == 400
    assert "Cannot delete locked namespace" in exc_info.value.detail


@pytest.mark.asyncio
async def test_delete_namespace_with_field_raises_error(
    namespace_with_field: Namespace,
    namespace_service: NamespaceService,
):
    """Deleting a namespace that contains fields raises an HTTPException."""
    with pytest.raises(HTTPException) as exc_info:
        await namespace_service.delete_namespace(namespace_with_field)

    assert exc_info.value.status_code == 400
    assert "Cannot delete namespace" in exc_info.value.detail
    assert "fields" in exc_info.value.detail


@pytest.mark.asyncio
async def test_delete_namespace_with_object_raises_error(
    namespace_with_object: Namespace,
    namespace_service: NamespaceService,
):
    """Deleting a namespace that contains objects raises an HTTPException."""
    with pytest.raises(HTTPException) as exc_info:
        await namespace_service.delete_namespace(namespace_with_object)

    assert exc_info.value.status_code == 400
    assert "Cannot delete namespace" in exc_info.value.detail
    assert "objects" in exc_info.value.detail


@pytest.mark.asyncio
async def test_delete_namespace_with_api_raises_error(
    namespace_with_api: Namespace,
    namespace_service: NamespaceService,
):
    """Deleting a namespace that contains APIs raises an HTTPException."""
    with pytest.raises(HTTPException) as exc_info:
        await namespace_service.delete_namespace(namespace_with_api)

    assert exc_info.value.status_code == 400
    assert "Cannot delete namespace" in exc_info.value.detail
    assert "APIs" in exc_info.value.detail


# --- Tests: Default namespace properties ---


@pytest.mark.asyncio
async def test_default_namespace_is_locked(
    provisioned_namespace: Namespace,
):
    """The provisioned default namespace is locked."""
    assert provisioned_namespace.locked is True
    assert provisioned_namespace.is_default is True


@pytest.mark.asyncio
async def test_default_namespace_name_is_global(
    provisioned_namespace: Namespace,
):
    """The provisioned default namespace is named 'Global'."""
    assert provisioned_namespace.name == "Global"


@pytest.mark.asyncio
async def test_default_namespace_owned_by_user(
    provisioned_namespace: Namespace,
):
    """The provisioned default namespace is owned by the test user."""
    assert provisioned_namespace.user_id == TEST_USER_ID


# --- Tests: User isolation ---


@pytest.mark.asyncio
async def test_user_cannot_see_system_namespace(
    provisioned_namespace: Namespace,
    namespace_service: NamespaceService,
):
    """The system namespace (user_id=NULL) does not appear in user's list."""
    namespaces = await namespace_service.list_for_user(TEST_USER_ID)

    assert all(ns.user_id == TEST_USER_ID for ns in namespaces)
    assert all(ns.user_id is not None for ns in namespaces)


@pytest.mark.asyncio
async def test_user_cannot_get_system_namespace_by_id(
    provisioned_namespace: Namespace,
    namespace_service: NamespaceService,
):
    """The system namespace cannot be fetched by a regular user."""
    from api.settings import get_settings

    settings = get_settings()
    result = await namespace_service.get_by_id_for_user(
        str(settings.system_namespace_id), TEST_USER_ID
    )

    assert result is None


@pytest.mark.asyncio
async def test_user_cannot_see_other_users_namespaces(
    db_session: AsyncSession,
    provisioned_namespace: Namespace,
    namespace_service: NamespaceService,
):
    """A user cannot list namespaces belonging to another user."""
    other_ns = Namespace(
        name="Other Namespace",
        user_id="other_user_xyz",
    )
    db_session.add(other_ns)
    await db_session.flush()

    namespaces = await namespace_service.list_for_user(TEST_USER_ID)
    namespace_ids = {ns.id for ns in namespaces}

    assert other_ns.id not in namespace_ids

    # Cleanup
    await db_session.execute(delete(Namespace).where(Namespace.id == other_ns.id))
    await db_session.flush()


@pytest.mark.asyncio
async def test_user_cannot_get_other_users_namespace_by_id(
    db_session: AsyncSession,
    provisioned_namespace: Namespace,
    namespace_service: NamespaceService,
):
    """A user cannot fetch a namespace that belongs to another user."""
    other_ns = Namespace(
        name="Private Namespace",
        user_id="other_user_abc",
    )
    db_session.add(other_ns)
    await db_session.flush()

    result = await namespace_service.get_by_id_for_user(str(other_ns.id), TEST_USER_ID)

    assert result is None

    # Cleanup
    await db_session.execute(delete(Namespace).where(Namespace.id == other_ns.id))
    await db_session.flush()
