# tests/test_user_provisioning.py
"""Integration tests for user provisioning service."""

import pytest

pytestmark = pytest.mark.integration

import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.database import FieldConstraintModel, Namespace, TypeModel
from api.services.user_provisioning import UserProvisioningService

PROVISION_USER_A = "test_provision_user_a"
PROVISION_USER_B = "test_provision_user_b"


@pytest_asyncio.fixture
async def cleanup_users(db_session: AsyncSession):
    """Clean up provisioned data after tests."""
    yield

    for user_id in [PROVISION_USER_A, PROVISION_USER_B]:
        # Find user's namespaces
        result = await db_session.execute(
            select(Namespace.id).where(Namespace.user_id == user_id)
        )
        ns_ids = [row[0] for row in result.fetchall()]
        for ns_id in ns_ids:
            await db_session.execute(
                delete(TypeModel).where(TypeModel.namespace_id == ns_id)
            )
            await db_session.execute(
                delete(FieldConstraintModel).where(
                    FieldConstraintModel.namespace_id == ns_id
                )
            )
        await db_session.execute(delete(Namespace).where(Namespace.user_id == user_id))
    await db_session.commit()


@pytest.mark.asyncio
async def test_provisioning_creates_default_namespace(
    db_session: AsyncSession,
    cleanup_users,
):
    """Test that provisioning creates a locked default namespace."""
    service = UserProvisioningService(db_session)
    await service.ensure_provisioned(PROVISION_USER_A)
    await db_session.commit()

    result = await db_session.execute(
        select(Namespace).where(
            Namespace.user_id == PROVISION_USER_A,
            Namespace.is_default.is_(True),
        )
    )
    namespace = result.scalar_one()

    assert namespace.name == "Global"
    assert namespace.locked is True
    assert namespace.is_default is True
    assert namespace.user_id == PROVISION_USER_A


@pytest.mark.asyncio
async def test_provisioning_copies_types(
    db_session: AsyncSession,
    cleanup_users,
):
    """Test that provisioning copies all global types."""
    service = UserProvisioningService(db_session)
    await service.ensure_provisioned(PROVISION_USER_A)
    await db_session.commit()

    result = await db_session.execute(
        select(Namespace).where(
            Namespace.user_id == PROVISION_USER_A,
            Namespace.is_default.is_(True),
        )
    )
    namespace = result.scalar_one()

    result = await db_session.execute(
        select(TypeModel).where(TypeModel.namespace_id == namespace.id)
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
    assert all(t.user_id == PROVISION_USER_A for t in types)


@pytest.mark.asyncio
async def test_provisioning_copies_constraints(
    db_session: AsyncSession,
    cleanup_users,
):
    """Test that provisioning copies all global field constraints."""
    service = UserProvisioningService(db_session)
    await service.ensure_provisioned(PROVISION_USER_A)
    await db_session.commit()

    result = await db_session.execute(
        select(Namespace).where(
            Namespace.user_id == PROVISION_USER_A,
            Namespace.is_default.is_(True),
        )
    )
    namespace = result.scalar_one()

    result = await db_session.execute(
        select(FieldConstraintModel).where(
            FieldConstraintModel.namespace_id == namespace.id
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


@pytest.mark.asyncio
async def test_provisioning_is_idempotent(
    db_session: AsyncSession,
    cleanup_users,
):
    """Test that calling ensure_provisioned twice doesn't duplicate data."""
    service = UserProvisioningService(db_session)
    await service.ensure_provisioned(PROVISION_USER_A)
    await db_session.commit()

    # Call again
    await service.ensure_provisioned(PROVISION_USER_A)
    await db_session.commit()

    # Should still have exactly one default namespace
    result = await db_session.execute(
        select(Namespace).where(
            Namespace.user_id == PROVISION_USER_A,
            Namespace.is_default.is_(True),
        )
    )
    namespaces = result.scalars().all()
    assert len(namespaces) == 1


@pytest.mark.asyncio
async def test_users_get_independent_data(
    db_session: AsyncSession,
    cleanup_users,
):
    """Test that two users get independent provisioned data."""
    service = UserProvisioningService(db_session)
    await service.ensure_provisioned(PROVISION_USER_A)
    await service.ensure_provisioned(PROVISION_USER_B)
    await db_session.commit()

    # Get namespaces for each user
    result_a = await db_session.execute(
        select(Namespace).where(
            Namespace.user_id == PROVISION_USER_A,
            Namespace.is_default.is_(True),
        )
    )
    ns_a = result_a.scalar_one()

    result_b = await db_session.execute(
        select(Namespace).where(
            Namespace.user_id == PROVISION_USER_B,
            Namespace.is_default.is_(True),
        )
    )
    ns_b = result_b.scalar_one()

    # Different namespace IDs
    assert ns_a.id != ns_b.id

    # Each has their own types
    result = await db_session.execute(
        select(TypeModel).where(TypeModel.namespace_id == ns_a.id)
    )
    types_a = result.scalars().all()

    result = await db_session.execute(
        select(TypeModel).where(TypeModel.namespace_id == ns_b.id)
    )
    types_b = result.scalars().all()

    assert len(types_a) == 8
    assert len(types_b) == 8

    # Type IDs should be different between users
    ids_a = {t.id for t in types_a}
    ids_b = {t.id for t in types_b}
    assert ids_a.isdisjoint(ids_b)


@pytest.mark.asyncio
async def test_provisioning_preserves_parent_type_relationships(
    db_session: AsyncSession,
    cleanup_users,
):
    """Test that parent_type_id relationships are correctly remapped."""
    service = UserProvisioningService(db_session)
    await service.ensure_provisioned(PROVISION_USER_A)
    await db_session.commit()

    result = await db_session.execute(
        select(Namespace).where(
            Namespace.user_id == PROVISION_USER_A,
            Namespace.is_default.is_(True),
        )
    )
    namespace = result.scalar_one()

    result = await db_session.execute(
        select(TypeModel).where(TypeModel.namespace_id == namespace.id)
    )
    types = result.scalars().all()
    by_name = {t.name: t for t in types}

    # EmailStr -> str
    assert by_name["EmailStr"].parent_type_id == by_name["str"].id
    # HttpUrl -> str
    assert by_name["HttpUrl"].parent_type_id == by_name["str"].id
    # Primitives have no parent
    assert by_name["str"].parent_type_id is None
    assert by_name["int"].parent_type_id is None
