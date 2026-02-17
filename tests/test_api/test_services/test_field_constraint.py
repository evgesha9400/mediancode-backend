# tests/test_api/test_services/test_field_constraint.py
"""Integration tests for field constraints."""

import pytest

pytestmark = pytest.mark.integration

import pytest_asyncio
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.database import FieldConstraintModel, Namespace
from api.services.field_constraint import FieldConstraintService
from api.settings import get_settings
from conftest import TEST_USER_ID

OTHER_USER_ID = "test_user_other"


@pytest_asyncio.fixture
async def test_constraint(db_session: AsyncSession, test_namespace: Namespace):
    """Create a test constraint in the user namespace."""
    constraint = FieldConstraintModel(
        namespace_id=test_namespace.id,
        name="custom_test",
        description="Custom test constraint",
        parameter_type="str",
        docs_url="",
        compatible_types=["str"],
    )
    db_session.add(constraint)
    await db_session.commit()
    await db_session.refresh(constraint)

    yield constraint

    # Cleanup
    await db_session.execute(
        delete(FieldConstraintModel).where(FieldConstraintModel.id == constraint.id)
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_seed_constraints_visible_via_system_namespace(
    db_session: AsyncSession,
    provisioned_namespace: Namespace,
):
    """Test that seed constraints from the system namespace are visible to provisioned users."""
    settings = get_settings()
    result = await db_session.execute(
        select(FieldConstraintModel)
        .join(Namespace)
        .where(
            or_(
                Namespace.user_id == TEST_USER_ID,
                Namespace.id == settings.system_namespace_id,
            )
        )
    )
    constraints = result.scalars().all()

    # Should have all 8 standard constraints from system namespace
    assert len(constraints) == 8

    constraint_names = {c.name for c in constraints}
    expected = {
        "max_length",
        "min_length",
        "pattern",
        "gt",
        "ge",
        "lt",
        "le",
        "multiple_of",
    }
    assert constraint_names == expected


@pytest.mark.asyncio
async def test_list_constraints_includes_custom_and_seed(
    db_session: AsyncSession,
    test_namespace: Namespace,
    test_constraint: FieldConstraintModel,
    provisioned_namespace: Namespace,
):
    """Test that user sees both seed and custom constraints via OR clause."""
    settings = get_settings()
    result = await db_session.execute(
        select(FieldConstraintModel)
        .join(Namespace)
        .where(
            or_(
                Namespace.user_id == TEST_USER_ID,
                Namespace.id == settings.system_namespace_id,
            )
        )
    )
    constraints = result.scalars().all()

    # Should have 8 seed constraints + 1 custom constraint
    assert len(constraints) >= 9

    constraint_names = {c.name for c in constraints}
    assert "custom_test" in constraint_names
    assert "max_length" in constraint_names


@pytest.mark.asyncio
async def test_seed_constraints_include_standard_set(
    db_session: AsyncSession,
    provisioned_namespace: Namespace,
):
    """Test that standard constraints are visible from the system namespace."""
    settings = get_settings()
    expected_constraints = ["max_length", "min_length", "pattern", "gt"]

    result = await db_session.execute(
        select(FieldConstraintModel)
        .join(Namespace)
        .where(
            or_(
                Namespace.user_id == TEST_USER_ID,
                Namespace.id == settings.system_namespace_id,
            )
        )
    )
    constraints = result.scalars().all()

    constraint_names = {c.name for c in constraints}
    for expected_name in expected_constraints:
        assert (
            expected_name in constraint_names
        ), f"Constraint '{expected_name}' should be visible from system namespace"


@pytest.mark.asyncio
async def test_seed_constraints_have_compatible_types(
    db_session: AsyncSession,
    provisioned_namespace: Namespace,
):
    """Test that seed constraints have compatible_types set."""
    settings = get_settings()
    result = await db_session.execute(
        select(FieldConstraintModel).where(
            FieldConstraintModel.namespace_id == settings.system_namespace_id,
        )
    )
    constraints = result.scalars().all()

    assert len(constraints) > 0
    assert all(len(c.compatible_types) > 0 for c in constraints)


# --- Tests: get_by_id_for_user ---


@pytest.mark.asyncio
async def test_get_constraint_by_id_for_user_returns_user_constraint(
    db_session: AsyncSession,
    test_namespace: Namespace,
    test_constraint: FieldConstraintModel,
):
    """get_by_id_for_user returns a constraint owned by the requesting user."""
    service = FieldConstraintService(db_session)
    result = await service.get_by_id_for_user(str(test_constraint.id), TEST_USER_ID)
    assert result is not None
    assert result.id == test_constraint.id


@pytest.mark.asyncio
async def test_get_constraint_by_id_for_user_excludes_system_constraints(
    db_session: AsyncSession,
    provisioned_namespace: Namespace,
):
    """get_by_id_for_user returns None for system namespace constraints."""
    settings = get_settings()
    result = await db_session.execute(
        select(FieldConstraintModel).where(
            FieldConstraintModel.namespace_id == settings.system_namespace_id,
        )
    )
    system_constraint = result.scalars().first()
    assert system_constraint is not None

    service = FieldConstraintService(db_session)
    result = await service.get_by_id_for_user(str(system_constraint.id), TEST_USER_ID)
    assert result is None


@pytest.mark.asyncio
async def test_get_constraint_by_id_for_user_excludes_other_users(
    db_session: AsyncSession,
    test_namespace: Namespace,
    test_constraint: FieldConstraintModel,
):
    """get_by_id_for_user returns None when a different user requests the constraint."""
    service = FieldConstraintService(db_session)
    result = await service.get_by_id_for_user(str(test_constraint.id), OTHER_USER_ID)
    assert result is None
