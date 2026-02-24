# tests/test_api/test_services/test_object.py
"""Integration tests for template-referenced model validators on objects."""

import pytest

pytestmark = pytest.mark.integration

import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from uuid import UUID

from api.models.database import (
    AppliedModelValidatorModel,
    FieldModel,
    Namespace,
    ObjectDefinition,
    TypeModel,
    UserModel,
)
from api.schemas.field import FieldCreate
from api.schemas.object import ObjectCreate, ObjectUpdate
from api.services.field import FieldService
from api.services.object import ObjectService
from api.settings import get_settings

# Seed model validator template UUIDs (from b1a2c3d4e5f6 migration)
MVT_FIELD_COMPARISON_ID = "00000000-0000-0000-0004-000000000001"
MVT_MUTUAL_EXCLUSIVITY_ID = "00000000-0000-0000-0004-000000000002"


# --- Fixtures ---


@pytest_asyncio.fixture
async def user_namespace(
    db_session: AsyncSession, provisioned_namespace: Namespace, test_user: UserModel
):
    """Create a user-owned (unlocked) namespace for object tests."""
    namespace = Namespace(
        name="Object Test Namespace",
        description="Namespace for template-referenced model validator tests",
        user_id=test_user.id,
    )
    db_session.add(namespace)
    await db_session.commit()
    await db_session.refresh(namespace)

    yield namespace

    await db_session.execute(
        delete(ObjectDefinition).where(ObjectDefinition.namespace_id == namespace.id)
    )
    await db_session.execute(
        delete(FieldModel).where(FieldModel.namespace_id == namespace.id)
    )
    await db_session.execute(delete(Namespace).where(Namespace.id == namespace.id))
    await db_session.commit()


@pytest_asyncio.fixture
async def str_type(db_session: AsyncSession, provisioned_namespace: Namespace):
    """Get the seed 'str' type from the system namespace."""
    settings = get_settings()
    result = await db_session.execute(
        select(TypeModel).where(
            TypeModel.namespace_id == settings.system_namespace_id,
            TypeModel.name == "str",
        )
    )
    return result.scalar_one()


@pytest_asyncio.fixture
def object_service(db_session: AsyncSession):
    """Create an ObjectService instance."""
    return ObjectService(db_session)


@pytest_asyncio.fixture
def field_service(db_session: AsyncSession):
    """Create a FieldService instance."""
    return FieldService(db_session)


@pytest_asyncio.fixture
async def test_field(
    user_namespace: Namespace,
    str_type: TypeModel,
    field_service: FieldService,
    test_user: UserModel,
):
    """Create a test field for use in objects."""
    data = FieldCreate.model_validate(
        {
            "namespaceId": user_namespace.id,
            "name": "test_field",
            "typeId": str_type.id,
        }
    )
    return await field_service.create_for_user(test_user.id, data)


# --- Helpers ---


async def _create_object(
    service: ObjectService,
    namespace: Namespace,
    user_id: UUID,
    field_id: UUID,
    name: str = "TestObject",
    validators: list | None = None,
) -> ObjectDefinition:
    """Create an object via the service layer."""
    data = ObjectCreate.model_validate(
        {
            "namespaceId": namespace.id,
            "name": name,
            "fields": [{"fieldId": str(field_id), "required": True}],
            "validators": validators or [],
        }
    )
    return await service.create_for_user(user_id, data)


async def _reload_object(
    service: ObjectService, obj: ObjectDefinition, user_id: UUID
) -> ObjectDefinition:
    """Reload an object with all relationships via the service."""
    loaded = await service.get_by_id_for_user(str(obj.id), user_id)
    assert loaded is not None, f"Object {obj.id} not found after reload"
    return loaded


# --- Tests: Create with template-referenced model validators ---


@pytest.mark.asyncio
async def test_create_object_with_validators(
    user_namespace: Namespace,
    object_service: ObjectService,
    test_field: FieldModel,
    test_user: UserModel,
):
    """Creating an object with a template-referenced validator creates child validator rows."""
    obj = await _create_object(
        object_service,
        user_namespace,
        test_user.id,
        test_field.id,
        name="ValidatedObject",
        validators=[
            {
                "templateId": MVT_FIELD_COMPARISON_ID,
                "parameters": {"operator": "=="},
                "fieldMappings": {
                    "field_a": "password",
                    "field_b": "password_confirm",
                },
            }
        ],
    )
    loaded = await _reload_object(object_service, obj, test_user.id)

    assert len(loaded.validators) == 1
    v = loaded.validators[0]
    assert v.template_id == UUID(MVT_FIELD_COMPARISON_ID)
    assert v.parameters == {"operator": "=="}
    assert v.field_mappings == {
        "field_a": "password",
        "field_b": "password_confirm",
    }
    assert v.id is not None


@pytest.mark.asyncio
async def test_create_object_without_validators(
    user_namespace: Namespace,
    object_service: ObjectService,
    test_field: FieldModel,
    test_user: UserModel,
):
    """An object created with no validators returns empty validators list."""
    obj = await _create_object(
        object_service,
        user_namespace,
        test_user.id,
        test_field.id,
        name="PlainObject",
    )
    loaded = await _reload_object(object_service, obj, test_user.id)

    assert len(loaded.validators) == 0


@pytest.mark.asyncio
async def test_create_object_with_multiple_validators(
    user_namespace: Namespace,
    object_service: ObjectService,
    test_field: FieldModel,
    test_user: UserModel,
):
    """Multiple template-referenced model validators are created with correct position ordering."""
    obj = await _create_object(
        object_service,
        user_namespace,
        test_user.id,
        test_field.id,
        name="MultiValObject",
        validators=[
            {
                "templateId": MVT_FIELD_COMPARISON_ID,
                "parameters": {"operator": "=="},
                "fieldMappings": {
                    "field_a": "password",
                    "field_b": "password_confirm",
                },
            },
            {
                "templateId": MVT_MUTUAL_EXCLUSIVITY_ID,
                "parameters": None,
                "fieldMappings": {
                    "field_a": "email",
                    "field_b": "phone",
                },
            },
        ],
    )
    loaded = await _reload_object(object_service, obj, test_user.id)

    assert len(loaded.validators) == 2
    assert loaded.validators[0].template_id == UUID(MVT_FIELD_COMPARISON_ID)
    assert loaded.validators[0].position == 0
    assert loaded.validators[1].template_id == UUID(MVT_MUTUAL_EXCLUSIVITY_ID)
    assert loaded.validators[1].position == 1


# --- Tests: Update validators ---


@pytest.mark.asyncio
async def test_update_object_replace_validators(
    user_namespace: Namespace,
    object_service: ObjectService,
    test_field: FieldModel,
    test_user: UserModel,
):
    """Updating validators replaces all existing ones."""
    obj = await _create_object(
        object_service,
        user_namespace,
        test_user.id,
        test_field.id,
        name="ReplaceValObject",
        validators=[
            {
                "templateId": MVT_FIELD_COMPARISON_ID,
                "parameters": {"operator": "=="},
                "fieldMappings": {
                    "field_a": "password",
                    "field_b": "password_confirm",
                },
            }
        ],
    )
    loaded = await _reload_object(object_service, obj, test_user.id)
    assert len(loaded.validators) == 1
    assert loaded.validators[0].template_id == UUID(MVT_FIELD_COMPARISON_ID)

    update = ObjectUpdate.model_validate(
        {
            "validators": [
                {
                    "templateId": MVT_FIELD_COMPARISON_ID,
                    "parameters": {"operator": "<"},
                    "fieldMappings": {
                        "field_a": "start_date",
                        "field_b": "end_date",
                    },
                }
            ]
        }
    )
    await object_service.update_object(loaded, update)
    reloaded = await _reload_object(object_service, loaded, test_user.id)

    assert len(reloaded.validators) == 1
    assert reloaded.validators[0].template_id == UUID(MVT_FIELD_COMPARISON_ID)
    assert reloaded.validators[0].parameters == {"operator": "<"}
    assert reloaded.validators[0].field_mappings == {
        "field_a": "start_date",
        "field_b": "end_date",
    }


@pytest.mark.asyncio
async def test_update_object_clear_validators(
    user_namespace: Namespace,
    object_service: ObjectService,
    test_field: FieldModel,
    test_user: UserModel,
):
    """Passing an empty validators list clears all validators."""
    obj = await _create_object(
        object_service,
        user_namespace,
        test_user.id,
        test_field.id,
        name="ClearValObject",
        validators=[
            {
                "templateId": MVT_MUTUAL_EXCLUSIVITY_ID,
                "parameters": None,
                "fieldMappings": {
                    "field_a": "email",
                    "field_b": "phone",
                },
            }
        ],
    )
    loaded = await _reload_object(object_service, obj, test_user.id)
    assert len(loaded.validators) == 1

    update = ObjectUpdate.model_validate({"validators": []})
    await object_service.update_object(loaded, update)
    reloaded = await _reload_object(object_service, loaded, test_user.id)

    assert len(reloaded.validators) == 0


@pytest.mark.asyncio
async def test_update_object_validators_unchanged_when_omitted(
    user_namespace: Namespace,
    object_service: ObjectService,
    test_field: FieldModel,
    test_user: UserModel,
):
    """Omitting validators from update (None) preserves existing ones."""
    obj = await _create_object(
        object_service,
        user_namespace,
        test_user.id,
        test_field.id,
        name="PreserveValObject",
        validators=[
            {
                "templateId": MVT_FIELD_COMPARISON_ID,
                "parameters": {"operator": "=="},
                "fieldMappings": {
                    "field_a": "password",
                    "field_b": "password_confirm",
                },
            }
        ],
    )
    loaded = await _reload_object(object_service, obj, test_user.id)
    assert len(loaded.validators) == 1

    update = ObjectUpdate.model_validate({"name": "RenamedObject"})
    await object_service.update_object(loaded, update)
    reloaded = await _reload_object(object_service, loaded, test_user.id)

    assert reloaded.name == "RenamedObject"
    assert len(reloaded.validators) == 1
    assert reloaded.validators[0].template_id == UUID(MVT_FIELD_COMPARISON_ID)
    assert reloaded.validators[0].field_mappings == {
        "field_a": "password",
        "field_b": "password_confirm",
    }


# --- Tests: Delete cascade ---


@pytest.mark.asyncio
async def test_delete_object_cascades_validators(
    db_session: AsyncSession,
    user_namespace: Namespace,
    object_service: ObjectService,
    test_field: FieldModel,
    test_user: UserModel,
):
    """Deleting an object removes its child model validators."""
    obj = await _create_object(
        object_service,
        user_namespace,
        test_user.id,
        test_field.id,
        name="CascadeObject",
        validators=[
            {
                "templateId": MVT_FIELD_COMPARISON_ID,
                "parameters": {"operator": "=="},
                "fieldMappings": {
                    "field_a": "password",
                    "field_b": "password_confirm",
                },
            }
        ],
    )
    await db_session.flush()
    obj_id = obj.id

    # Verify validator exists
    result = await db_session.execute(
        select(AppliedModelValidatorModel).where(
            AppliedModelValidatorModel.object_id == obj_id
        )
    )
    assert len(result.scalars().all()) == 1

    # Delete the object
    loaded = await _reload_object(object_service, obj, test_user.id)
    await object_service.delete_object(loaded)
    await db_session.flush()

    # Verify validator was cascade-deleted
    result = await db_session.execute(
        select(AppliedModelValidatorModel).where(
            AppliedModelValidatorModel.object_id == obj_id
        )
    )
    assert len(result.scalars().all()) == 0
