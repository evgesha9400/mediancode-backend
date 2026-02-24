# tests/test_api/test_services/test_field_validator.py
"""Integration tests for template-referenced field validators on fields."""

import pytest

pytestmark = pytest.mark.integration

import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from uuid import UUID

from api.models.database import (
    AppliedFieldValidatorModel,
    FieldModel,
    Namespace,
    TypeModel,
    UserModel,
)
from api.schemas.field import FieldCreate, FieldUpdate
from api.services.field import FieldService
from api.settings import get_settings

# Seed field validator template UUIDs (from b1a2c3d4e5f6 migration)
FVT_STRIP_AND_NORMALIZE_ID = "00000000-0000-0000-0003-000000000001"
FVT_NORMALIZE_WHITESPACE_ID = "00000000-0000-0000-0003-000000000002"
FVT_DEFAULT_IF_EMPTY_ID = "00000000-0000-0000-0003-000000000003"
FVT_TRIM_TO_LENGTH_ID = "00000000-0000-0000-0003-000000000004"


# --- Fixtures ---


@pytest_asyncio.fixture
async def user_namespace(
    db_session: AsyncSession, provisioned_namespace: Namespace, test_user: UserModel
):
    """Create a user-owned (unlocked) namespace for validator tests."""
    namespace = Namespace(
        name="Validator Test Namespace",
        description="Namespace for template-referenced field validator tests",
        user_id=test_user.id,
    )
    db_session.add(namespace)
    await db_session.commit()
    await db_session.refresh(namespace)

    yield namespace

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
def field_service(db_session: AsyncSession):
    """Create a FieldService instance."""
    return FieldService(db_session)


# --- Helpers ---


async def _create_field(
    service: FieldService,
    namespace: Namespace,
    type_model: TypeModel,
    user_id: UUID,
    name: str = "test_field",
    validators: list | None = None,
) -> FieldModel:
    """Create a field via the service layer."""
    data = FieldCreate.model_validate(
        {
            "namespaceId": namespace.id,
            "name": name,
            "typeId": type_model.id,
            "validators": validators or [],
        }
    )
    return await service.create_for_user(user_id, data)


async def _reload_field(
    service: FieldService, field: FieldModel, user_id: UUID
) -> FieldModel:
    """Reload a field with all relationships via the service."""
    loaded = await service.get_by_id_for_user(str(field.id), user_id)
    assert loaded is not None, f"Field {field.id} not found after reload"
    return loaded


# --- Tests: Create with template-referenced validators ---


@pytest.mark.asyncio
async def test_create_field_with_validators(
    user_namespace: Namespace,
    str_type: TypeModel,
    field_service: FieldService,
    test_user: UserModel,
):
    """Creating a field with a template-referenced validator creates child validator rows."""
    field = await _create_field(
        field_service,
        user_namespace,
        str_type,
        user_id=test_user.id,
        name="validated_field",
        validators=[
            {
                "templateId": FVT_NORMALIZE_WHITESPACE_ID,
                "parameters": None,
            }
        ],
    )
    loaded = await _reload_field(field_service, field, test_user.id)

    assert len(loaded.validators) == 1
    v = loaded.validators[0]
    assert v.template_id == UUID(FVT_NORMALIZE_WHITESPACE_ID)
    assert v.parameters is None
    assert v.id is not None


@pytest.mark.asyncio
async def test_create_field_with_multiple_validators(
    user_namespace: Namespace,
    str_type: TypeModel,
    field_service: FieldService,
    test_user: UserModel,
):
    """Multiple template-referenced validators are created with correct position ordering."""
    field = await _create_field(
        field_service,
        user_namespace,
        str_type,
        user_id=test_user.id,
        name="multi_val_field",
        validators=[
            {
                "templateId": FVT_STRIP_AND_NORMALIZE_ID,
                "parameters": {"case": "lower"},
            },
            {
                "templateId": FVT_NORMALIZE_WHITESPACE_ID,
                "parameters": None,
            },
        ],
    )
    loaded = await _reload_field(field_service, field, test_user.id)

    assert len(loaded.validators) == 2
    assert loaded.validators[0].template_id == UUID(FVT_STRIP_AND_NORMALIZE_ID)
    assert loaded.validators[0].parameters == {"case": "lower"}
    assert loaded.validators[0].position == 0
    assert loaded.validators[1].template_id == UUID(FVT_NORMALIZE_WHITESPACE_ID)
    assert loaded.validators[1].parameters is None
    assert loaded.validators[1].position == 1


@pytest.mark.asyncio
async def test_create_field_without_validators(
    user_namespace: Namespace,
    str_type: TypeModel,
    field_service: FieldService,
    test_user: UserModel,
):
    """A field created with no validators returns empty validators list."""
    field = await _create_field(
        field_service,
        user_namespace,
        str_type,
        user_id=test_user.id,
        name="plain_field",
    )
    loaded = await _reload_field(field_service, field, test_user.id)

    assert len(loaded.validators) == 0


# --- Tests: Update validators ---


@pytest.mark.asyncio
async def test_update_field_replace_validators(
    user_namespace: Namespace,
    str_type: TypeModel,
    field_service: FieldService,
    test_user: UserModel,
):
    """Updating validators replaces all existing ones."""
    field = await _create_field(
        field_service,
        user_namespace,
        str_type,
        user_id=test_user.id,
        name="replace_val_field",
        validators=[
            {
                "templateId": FVT_NORMALIZE_WHITESPACE_ID,
                "parameters": None,
            }
        ],
    )
    loaded = await _reload_field(field_service, field, test_user.id)
    assert len(loaded.validators) == 1
    assert loaded.validators[0].template_id == UUID(FVT_NORMALIZE_WHITESPACE_ID)

    update = FieldUpdate.model_validate(
        {
            "validators": [
                {
                    "templateId": FVT_STRIP_AND_NORMALIZE_ID,
                    "parameters": {"case": "upper"},
                }
            ]
        }
    )
    await field_service.update_field(loaded, update)
    reloaded = await _reload_field(field_service, loaded, test_user.id)

    assert len(reloaded.validators) == 1
    assert reloaded.validators[0].template_id == UUID(FVT_STRIP_AND_NORMALIZE_ID)
    assert reloaded.validators[0].parameters == {"case": "upper"}


@pytest.mark.asyncio
async def test_update_field_clear_validators(
    user_namespace: Namespace,
    str_type: TypeModel,
    field_service: FieldService,
    test_user: UserModel,
):
    """Passing an empty validators list clears all validators."""
    field = await _create_field(
        field_service,
        user_namespace,
        str_type,
        user_id=test_user.id,
        name="clear_val_field",
        validators=[
            {
                "templateId": FVT_NORMALIZE_WHITESPACE_ID,
                "parameters": None,
            }
        ],
    )
    loaded = await _reload_field(field_service, field, test_user.id)
    assert len(loaded.validators) == 1

    update = FieldUpdate.model_validate({"validators": []})
    await field_service.update_field(loaded, update)
    reloaded = await _reload_field(field_service, loaded, test_user.id)

    assert len(reloaded.validators) == 0


@pytest.mark.asyncio
async def test_update_field_validators_unchanged_when_omitted(
    user_namespace: Namespace,
    str_type: TypeModel,
    field_service: FieldService,
    test_user: UserModel,
):
    """Omitting validators from update (None) preserves existing ones."""
    field = await _create_field(
        field_service,
        user_namespace,
        str_type,
        user_id=test_user.id,
        name="preserve_val_field",
        validators=[
            {
                "templateId": FVT_TRIM_TO_LENGTH_ID,
                "parameters": {"max_length": "255"},
            }
        ],
    )
    loaded = await _reload_field(field_service, field, test_user.id)
    assert len(loaded.validators) == 1

    update = FieldUpdate.model_validate({"name": "renamed_field"})
    await field_service.update_field(loaded, update)
    reloaded = await _reload_field(field_service, loaded, test_user.id)

    assert reloaded.name == "renamed_field"
    assert len(reloaded.validators) == 1
    assert reloaded.validators[0].template_id == UUID(FVT_TRIM_TO_LENGTH_ID)
    assert reloaded.validators[0].parameters == {"max_length": "255"}


# --- Tests: Delete cascade ---


@pytest.mark.asyncio
async def test_delete_field_cascades_validators(
    db_session: AsyncSession,
    user_namespace: Namespace,
    str_type: TypeModel,
    field_service: FieldService,
    test_user: UserModel,
):
    """Deleting a field removes its child validators."""
    field = await _create_field(
        field_service,
        user_namespace,
        str_type,
        user_id=test_user.id,
        name="cascade_field",
        validators=[
            {
                "templateId": FVT_NORMALIZE_WHITESPACE_ID,
                "parameters": None,
            }
        ],
    )
    await db_session.flush()
    field_id = field.id

    # Verify validator exists
    result = await db_session.execute(
        select(AppliedFieldValidatorModel).where(
            AppliedFieldValidatorModel.field_id == field_id
        )
    )
    assert len(result.scalars().all()) == 1

    # Delete the field
    loaded = await _reload_field(field_service, field, test_user.id)
    await field_service.delete_field(loaded)
    await db_session.flush()

    # Verify validator was cascade-deleted
    result = await db_session.execute(
        select(AppliedFieldValidatorModel).where(
            AppliedFieldValidatorModel.field_id == field_id
        )
    )
    assert len(result.scalars().all()) == 0
