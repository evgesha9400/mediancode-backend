# tests/test_api/test_services/test_type.py
"""Integration tests for types."""

import pytest

pytestmark = pytest.mark.integration

from uuid import uuid4

import pytest_asyncio
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.database import Namespace, TypeModel, UserModel
from api.services.type import TypeService
from api.settings import get_settings

OTHER_USER_ID = uuid4()


@pytest_asyncio.fixture
async def test_type(
    db_session: AsyncSession, test_namespace: Namespace, test_user: UserModel
):
    """Create a test type in the user namespace."""
    type_model = TypeModel(
        namespace_id=test_namespace.id,
        user_id=test_user.id,
        name="CustomType",
        python_type="CustomType",
        description="Custom test type",
    )
    db_session.add(type_model)
    await db_session.commit()
    await db_session.refresh(type_model)

    yield type_model

    # Cleanup
    await db_session.execute(delete(TypeModel).where(TypeModel.id == type_model.id))
    await db_session.commit()


@pytest.mark.asyncio
async def test_seed_types_visible_via_system_namespace(
    db_session: AsyncSession,
    provisioned_namespace: Namespace,
    test_user: UserModel,
):
    """Test that seed types from the system namespace are visible to provisioned users."""
    settings = get_settings()
    result = await db_session.execute(
        select(TypeModel)
        .join(Namespace)
        .where(
            or_(
                Namespace.user_id == test_user.id,
                Namespace.id == settings.system_namespace_id,
            )
        )
    )
    types = result.scalars().all()

    # Should have all 11 standard types from system namespace
    assert len(types) == 11

    type_names = {t.name for t in types}
    expected = {
        "str",
        "int",
        "float",
        "bool",
        "datetime",
        "uuid",
        "EmailStr",
        "HttpUrl",
        "Decimal",
        "date",
        "time",
    }
    assert type_names == expected


@pytest.mark.asyncio
async def test_seed_types_belong_to_system_namespace(
    db_session: AsyncSession,
    provisioned_namespace: Namespace,
):
    """Test that seed types live in the system namespace, not the user's namespace."""
    settings = get_settings()
    result = await db_session.execute(
        select(TypeModel).where(
            TypeModel.namespace_id == settings.system_namespace_id,
        )
    )
    types = result.scalars().all()

    assert len(types) == 11
    # Seed types have user_id=NULL since they belong to the system namespace
    assert all(t.user_id is None for t in types)


@pytest.mark.asyncio
async def test_seed_types_preserve_parent_relationships(
    db_session: AsyncSession,
    provisioned_namespace: Namespace,
):
    """Test that parent_type_id relationships are correct in seed types."""
    settings = get_settings()
    result = await db_session.execute(
        select(TypeModel).where(
            TypeModel.namespace_id == settings.system_namespace_id,
        )
    )
    types = result.scalars().all()
    by_name = {t.name: t for t in types}

    # EmailStr and HttpUrl should have parent_type_id pointing to str
    assert by_name["EmailStr"].parent_type_id == by_name["str"].id
    assert by_name["HttpUrl"].parent_type_id == by_name["str"].id

    # Primitive types should have no parent
    for name in ["str", "int", "float", "bool", "datetime", "uuid"]:
        assert by_name[name].parent_type_id is None


@pytest.mark.asyncio
async def test_list_types_includes_custom_and_seed(
    db_session: AsyncSession,
    test_namespace: Namespace,
    test_type: TypeModel,
    provisioned_namespace: Namespace,
    test_user: UserModel,
):
    """Test that user sees both seed types and custom types via OR clause."""
    settings = get_settings()
    result = await db_session.execute(
        select(TypeModel)
        .join(Namespace)
        .where(
            or_(
                Namespace.user_id == test_user.id,
                Namespace.id == settings.system_namespace_id,
            )
        )
    )
    types = result.scalars().all()

    # Should have 8 seed types + 1 custom type
    assert len(types) >= 9

    type_names = {t.name for t in types}
    assert "CustomType" in type_names
    assert "str" in type_names


@pytest.mark.asyncio
async def test_seed_types_include_primitives(
    db_session: AsyncSession,
    provisioned_namespace: Namespace,
    test_user: UserModel,
):
    """Test that primitive types are visible from the system namespace."""
    settings = get_settings()
    expected_primitives = ["str", "int", "float", "bool", "datetime", "uuid"]

    result = await db_session.execute(
        select(TypeModel)
        .join(Namespace)
        .where(
            or_(
                Namespace.user_id == test_user.id,
                Namespace.id == settings.system_namespace_id,
            )
        )
    )
    types = result.scalars().all()

    type_names = {t.name for t in types}
    for expected_name in expected_primitives:
        assert (
            expected_name in type_names
        ), f"Primitive type '{expected_name}' should be visible from system namespace"


# --- Tests: get_by_id_for_user ---


@pytest.mark.asyncio
async def test_get_type_by_id_for_user_returns_user_type(
    db_session: AsyncSession,
    test_namespace: Namespace,
    test_type: TypeModel,
    test_user: UserModel,
):
    """get_by_id_for_user returns a type owned by the requesting user."""
    service = TypeService(db_session)
    result = await service.get_by_id_for_user(str(test_type.id), test_user.id)
    assert result is not None
    assert result.id == test_type.id


@pytest.mark.asyncio
async def test_get_type_by_id_for_user_excludes_system_types(
    db_session: AsyncSession,
    provisioned_namespace: Namespace,
    test_user: UserModel,
):
    """get_by_id_for_user returns None for system namespace types."""
    settings = get_settings()
    result = await db_session.execute(
        select(TypeModel).where(
            TypeModel.namespace_id == settings.system_namespace_id,
        )
    )
    system_type = result.scalars().first()
    assert system_type is not None

    service = TypeService(db_session)
    result = await service.get_by_id_for_user(str(system_type.id), test_user.id)
    assert result is None


@pytest.mark.asyncio
async def test_get_type_by_id_for_user_excludes_other_users(
    db_session: AsyncSession,
    test_namespace: Namespace,
    test_type: TypeModel,
):
    """get_by_id_for_user returns None when a different user requests the type."""
    service = TypeService(db_session)
    result = await service.get_by_id_for_user(str(test_type.id), OTHER_USER_ID)
    assert result is None
