# tests/test_api/test_services/test_user.py
"""Integration tests for user service."""

import pytest

pytestmark = pytest.mark.integration

import pytest_asyncio
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.database import FieldConstraintModel, Namespace, TypeModel, UserModel
from api.services.user import UserService
from api.settings import get_settings

PROVISION_USER_A = "test_provision_user_a"
PROVISION_USER_B = "test_provision_user_b"


@pytest_asyncio.fixture
async def cleanup_users(db_session: AsyncSession):
    """Clean up provisioned data after tests."""
    yield

    for clerk_id in [PROVISION_USER_A, PROVISION_USER_B]:
        user_result = await db_session.execute(
            select(UserModel).where(UserModel.clerk_id == clerk_id)
        )
        user = user_result.scalar_one_or_none()
        if user:
            await db_session.execute(
                delete(Namespace).where(Namespace.user_id == user.id)
            )
            await db_session.execute(delete(UserModel).where(UserModel.id == user.id))
    await db_session.commit()


@pytest.mark.asyncio
async def test_provisioning_creates_default_namespace(
    db_session: AsyncSession,
    cleanup_users,
):
    """Test that provisioning creates a locked default namespace."""
    service = UserService(db_session)
    user = await service.ensure_provisioned(PROVISION_USER_A)
    await db_session.commit()

    assert isinstance(user, UserModel)
    assert user.clerk_id == PROVISION_USER_A

    result = await db_session.execute(
        select(Namespace).where(
            Namespace.user_id == user.id,
            Namespace.is_default.is_(True),
        )
    )
    namespace = result.scalar_one()

    assert namespace.name == "Global"
    assert namespace.locked is True
    assert namespace.is_default is True
    assert namespace.user_id == user.id


@pytest.mark.asyncio
async def test_provisioned_namespace_is_empty(
    db_session: AsyncSession,
    cleanup_users,
):
    """Test that provisioning does not copy types or constraints."""
    service = UserService(db_session)
    user = await service.ensure_provisioned(PROVISION_USER_A)
    await db_session.commit()

    assert isinstance(user, UserModel)
    assert user.clerk_id == PROVISION_USER_A

    result = await db_session.execute(
        select(Namespace).where(
            Namespace.user_id == user.id,
            Namespace.is_default.is_(True),
        )
    )
    namespace = result.scalar_one()

    # No types in the user's namespace
    result = await db_session.execute(
        select(TypeModel).where(TypeModel.namespace_id == namespace.id)
    )
    assert len(result.scalars().all()) == 0

    # No constraints in the user's namespace
    result = await db_session.execute(
        select(FieldConstraintModel).where(
            FieldConstraintModel.namespace_id == namespace.id
        )
    )
    assert len(result.scalars().all()) == 0


@pytest.mark.asyncio
async def test_provisioning_is_idempotent(
    db_session: AsyncSession,
    cleanup_users,
):
    """Test that calling ensure_provisioned twice doesn't duplicate data."""
    service = UserService(db_session)
    user_first = await service.ensure_provisioned(PROVISION_USER_A)
    await db_session.commit()

    # Call again
    user_second = await service.ensure_provisioned(PROVISION_USER_A)
    await db_session.commit()

    assert isinstance(user_first, UserModel)
    assert isinstance(user_second, UserModel)
    assert user_first.clerk_id == PROVISION_USER_A
    assert user_second.clerk_id == PROVISION_USER_A
    assert user_first.id == user_second.id

    # Should still have exactly one default namespace
    result = await db_session.execute(
        select(Namespace).where(
            Namespace.user_id == user_first.id,
            Namespace.is_default.is_(True),
        )
    )
    namespaces = result.scalars().all()
    assert len(namespaces) == 1


@pytest.mark.asyncio
async def test_users_get_independent_namespaces(
    db_session: AsyncSession,
    cleanup_users,
):
    """Test that two users get independent namespaces."""
    service = UserService(db_session)
    user_a = await service.ensure_provisioned(PROVISION_USER_A)
    user_b = await service.ensure_provisioned(PROVISION_USER_B)
    await db_session.commit()

    assert isinstance(user_a, UserModel)
    assert isinstance(user_b, UserModel)
    assert user_a.clerk_id == PROVISION_USER_A
    assert user_b.clerk_id == PROVISION_USER_B
    assert user_a.id != user_b.id

    result_a = await db_session.execute(
        select(Namespace).where(
            Namespace.user_id == user_a.id,
            Namespace.is_default.is_(True),
        )
    )
    ns_a = result_a.scalar_one()

    result_b = await db_session.execute(
        select(Namespace).where(
            Namespace.user_id == user_b.id,
            Namespace.is_default.is_(True),
        )
    )
    ns_b = result_b.scalar_one()

    assert ns_a.id != ns_b.id


@pytest.mark.asyncio
async def test_system_namespace_types_visible_to_provisioned_user(
    db_session: AsyncSession,
    cleanup_users,
):
    """Test that seed types from the system namespace are visible via OR clause."""
    settings = get_settings()
    service = UserService(db_session)
    user = await service.ensure_provisioned(PROVISION_USER_A)
    await db_session.commit()

    assert isinstance(user, UserModel)
    assert user.clerk_id == PROVISION_USER_A

    # Query types using the same OR pattern as TypeService.list_for_user()
    result = await db_session.execute(
        select(TypeModel)
        .join(Namespace)
        .where(
            or_(
                Namespace.user_id == user.id,
                Namespace.id == settings.system_namespace_id,
            )
        )
    )
    types = result.scalars().all()

    assert len(types) == 8
    type_names = {t.name for t in types}
    assert type_names == {
        "str",
        "int",
        "float",
        "bool",
        "datetime",
        "uuid",
        "EmailStr",
        "HttpUrl",
    }


@pytest.mark.asyncio
async def test_system_namespace_constraints_visible_to_provisioned_user(
    db_session: AsyncSession,
    cleanup_users,
):
    """Test that seed constraints from the system namespace are visible via OR clause."""
    settings = get_settings()
    service = UserService(db_session)
    user = await service.ensure_provisioned(PROVISION_USER_A)
    await db_session.commit()

    assert isinstance(user, UserModel)
    assert user.clerk_id == PROVISION_USER_A

    # Query constraints using the same OR pattern as FieldConstraintService.list_for_user()
    result = await db_session.execute(
        select(FieldConstraintModel)
        .join(Namespace)
        .where(
            or_(
                Namespace.user_id == user.id,
                Namespace.id == settings.system_namespace_id,
            )
        )
    )
    constraints = result.scalars().all()

    assert len(constraints) == 8
    constraint_names = {c.name for c in constraints}
    assert constraint_names == {
        "max_length",
        "min_length",
        "pattern",
        "gt",
        "ge",
        "lt",
        "le",
        "multiple_of",
    }
