# tests/test_api_fields.py
"""Integration tests for field constraint values flow."""

import pytest

pytestmark = pytest.mark.integration

import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.database import (
    FieldConstraintModel,
    FieldConstraintValueAssociation,
    FieldModel,
    Namespace,
    TypeModel,
)
from api.schemas.field import FieldCreate, FieldUpdate
from api.services.field import FieldService
from conftest import TEST_USER_ID


# --- Fixtures ---


@pytest_asyncio.fixture
async def user_namespace(db_session: AsyncSession, provisioned_namespace: Namespace):
    """Create a user-owned (unlocked) namespace for field tests."""
    namespace = Namespace(
        name="Field Test Namespace",
        description="Namespace for field constraint value tests",
        user_id=TEST_USER_ID,
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
    """Get the user's provisioned 'str' type."""
    result = await db_session.execute(
        select(TypeModel).where(
            TypeModel.namespace_id == provisioned_namespace.id,
            TypeModel.name == "str",
        )
    )
    return result.scalar_one()


@pytest_asyncio.fixture
async def max_length_constraint(
    db_session: AsyncSession, provisioned_namespace: Namespace
):
    """Get the user's provisioned 'max_length' field constraint."""
    result = await db_session.execute(
        select(FieldConstraintModel).where(
            FieldConstraintModel.namespace_id == provisioned_namespace.id,
            FieldConstraintModel.name == "max_length",
        )
    )
    return result.scalar_one()


@pytest_asyncio.fixture
async def min_length_constraint(
    db_session: AsyncSession, provisioned_namespace: Namespace
):
    """Get the user's provisioned 'min_length' field constraint."""
    result = await db_session.execute(
        select(FieldConstraintModel).where(
            FieldConstraintModel.namespace_id == provisioned_namespace.id,
            FieldConstraintModel.name == "min_length",
        )
    )
    return result.scalar_one()


@pytest_asyncio.fixture
async def pattern_constraint(
    db_session: AsyncSession, provisioned_namespace: Namespace
):
    """Get the user's provisioned 'pattern' field constraint."""
    result = await db_session.execute(
        select(FieldConstraintModel).where(
            FieldConstraintModel.namespace_id == provisioned_namespace.id,
            FieldConstraintModel.name == "pattern",
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
    name: str = "test_field",
    constraints: list | None = None,
) -> FieldModel:
    """Create a field via the service layer."""
    data = FieldCreate.model_validate(
        {
            "namespaceId": namespace.id,
            "name": name,
            "typeId": type_model.id,
            "constraints": constraints or [],
        }
    )
    return await service.create_for_user(TEST_USER_ID, data)


async def _reload_field(service: FieldService, field: FieldModel) -> FieldModel:
    """Reload a field with all relationships via the service."""
    loaded = await service.get_by_id_for_user(str(field.id), TEST_USER_ID)
    assert loaded is not None, f"Field {field.id} not found after reload"
    return loaded


# --- Tests: Create with constraints ---


@pytest.mark.asyncio
async def test_create_field_with_constraint_value(
    user_namespace: Namespace,
    str_type: TypeModel,
    max_length_constraint: FieldConstraintModel,
    field_service: FieldService,
):
    """Creating a field with a constraint stores the parameter value."""
    field = await _create_field(
        field_service,
        user_namespace,
        str_type,
        name="username",
        constraints=[{"constraintId": str(max_length_constraint.id), "value": "255"}],
    )
    loaded = await _reload_field(field_service, field)

    assert len(loaded.constraint_values) == 1
    cv = loaded.constraint_values[0]
    assert cv.constraint_id == max_length_constraint.id
    assert cv.value == "255"
    assert cv.constraint.name == "max_length"


@pytest.mark.asyncio
async def test_create_field_with_constraint_no_value(
    user_namespace: Namespace,
    str_type: TypeModel,
    pattern_constraint: FieldConstraintModel,
    field_service: FieldService,
):
    """A constraint can be attached without a value (null parameter)."""
    field = await _create_field(
        field_service,
        user_namespace,
        str_type,
        name="tag",
        constraints=[{"constraintId": str(pattern_constraint.id)}],
    )
    loaded = await _reload_field(field_service, field)

    assert len(loaded.constraint_values) == 1
    cv = loaded.constraint_values[0]
    assert cv.constraint_id == pattern_constraint.id
    assert cv.value is None
    assert cv.constraint.name == "pattern"


@pytest.mark.asyncio
async def test_create_field_with_multiple_constraints(
    user_namespace: Namespace,
    str_type: TypeModel,
    max_length_constraint: FieldConstraintModel,
    min_length_constraint: FieldConstraintModel,
    pattern_constraint: FieldConstraintModel,
    field_service: FieldService,
):
    """Multiple constraints with values can be attached to a single field."""
    field = await _create_field(
        field_service,
        user_namespace,
        str_type,
        name="email",
        constraints=[
            {"constraintId": str(max_length_constraint.id), "value": "320"},
            {"constraintId": str(min_length_constraint.id), "value": "5"},
            {
                "constraintId": str(pattern_constraint.id),
                "value": r"^[\w.]+@[\w.]+$",
            },
        ],
    )
    loaded = await _reload_field(field_service, field)

    assert len(loaded.constraint_values) == 3
    by_name = {cv.constraint.name: cv for cv in loaded.constraint_values}
    assert by_name["max_length"].value == "320"
    assert by_name["min_length"].value == "5"
    assert by_name["pattern"].value == r"^[\w.]+@[\w.]+$"


@pytest.mark.asyncio
async def test_create_field_without_constraints(
    user_namespace: Namespace,
    str_type: TypeModel,
    field_service: FieldService,
):
    """A field can be created with no constraints."""
    field = await _create_field(
        field_service,
        user_namespace,
        str_type,
        name="plain_field",
    )
    loaded = await _reload_field(field_service, field)

    assert len(loaded.constraint_values) == 0


# --- Tests: Update constraints ---


@pytest.mark.asyncio
async def test_update_field_add_constraints(
    user_namespace: Namespace,
    str_type: TypeModel,
    max_length_constraint: FieldConstraintModel,
    field_service: FieldService,
):
    """Constraints can be added to a field that previously had none."""
    field = await _create_field(
        field_service,
        user_namespace,
        str_type,
        name="bio",
    )
    loaded = await _reload_field(field_service, field)
    assert len(loaded.constraint_values) == 0

    update = FieldUpdate.model_validate(
        {
            "constraints": [
                {"constraintId": str(max_length_constraint.id), "value": "500"}
            ]
        }
    )
    await field_service.update_field(loaded, update)
    reloaded = await _reload_field(field_service, loaded)

    assert len(reloaded.constraint_values) == 1
    assert reloaded.constraint_values[0].value == "500"
    assert reloaded.constraint_values[0].constraint.name == "max_length"


@pytest.mark.asyncio
async def test_update_field_replace_constraints(
    user_namespace: Namespace,
    str_type: TypeModel,
    max_length_constraint: FieldConstraintModel,
    min_length_constraint: FieldConstraintModel,
    field_service: FieldService,
):
    """Updating constraints replaces all existing ones."""
    field = await _create_field(
        field_service,
        user_namespace,
        str_type,
        name="title",
        constraints=[{"constraintId": str(max_length_constraint.id), "value": "100"}],
    )
    loaded = await _reload_field(field_service, field)
    assert len(loaded.constraint_values) == 1
    assert loaded.constraint_values[0].constraint.name == "max_length"

    update = FieldUpdate.model_validate(
        {"constraints": [{"constraintId": str(min_length_constraint.id), "value": "1"}]}
    )
    await field_service.update_field(loaded, update)
    reloaded = await _reload_field(field_service, loaded)

    assert len(reloaded.constraint_values) == 1
    assert reloaded.constraint_values[0].constraint.name == "min_length"
    assert reloaded.constraint_values[0].value == "1"


@pytest.mark.asyncio
async def test_update_field_clear_constraints(
    user_namespace: Namespace,
    str_type: TypeModel,
    max_length_constraint: FieldConstraintModel,
    field_service: FieldService,
):
    """Passing an empty constraints list clears all constraints."""
    field = await _create_field(
        field_service,
        user_namespace,
        str_type,
        name="slug",
        constraints=[{"constraintId": str(max_length_constraint.id), "value": "200"}],
    )
    loaded = await _reload_field(field_service, field)
    assert len(loaded.constraint_values) == 1

    update = FieldUpdate.model_validate({"constraints": []})
    await field_service.update_field(loaded, update)
    reloaded = await _reload_field(field_service, loaded)

    assert len(reloaded.constraint_values) == 0


@pytest.mark.asyncio
async def test_update_field_constraints_unchanged_when_omitted(
    user_namespace: Namespace,
    str_type: TypeModel,
    max_length_constraint: FieldConstraintModel,
    field_service: FieldService,
):
    """Omitting constraints from update (None) preserves existing ones."""
    field = await _create_field(
        field_service,
        user_namespace,
        str_type,
        name="code",
        constraints=[{"constraintId": str(max_length_constraint.id), "value": "50"}],
    )
    loaded = await _reload_field(field_service, field)
    assert len(loaded.constraint_values) == 1

    update = FieldUpdate.model_validate({"name": "code_v2"})
    await field_service.update_field(loaded, update)
    reloaded = await _reload_field(field_service, loaded)

    assert reloaded.name == "code_v2"
    assert len(reloaded.constraint_values) == 1
    assert reloaded.constraint_values[0].value == "50"


# --- Tests: Delete cascade ---


@pytest.mark.asyncio
async def test_delete_field_cascades_constraint_associations(
    db_session: AsyncSession,
    user_namespace: Namespace,
    str_type: TypeModel,
    max_length_constraint: FieldConstraintModel,
    field_service: FieldService,
):
    """Deleting a field removes its constraint value associations."""
    field = await _create_field(
        field_service,
        user_namespace,
        str_type,
        name="temp_field",
        constraints=[{"constraintId": str(max_length_constraint.id), "value": "10"}],
    )
    await db_session.flush()
    field_id = field.id

    # Verify association exists
    result = await db_session.execute(
        select(FieldConstraintValueAssociation).where(
            FieldConstraintValueAssociation.field_id == field_id
        )
    )
    assert len(result.scalars().all()) == 1

    # Delete the field
    loaded = await _reload_field(field_service, field)
    await field_service.delete_field(loaded)
    await db_session.flush()

    # Verify association was cascade-deleted
    result = await db_session.execute(
        select(FieldConstraintValueAssociation).where(
            FieldConstraintValueAssociation.field_id == field_id
        )
    )
    assert len(result.scalars().all()) == 0
