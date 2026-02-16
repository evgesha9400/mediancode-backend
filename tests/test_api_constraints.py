# tests/test_api_constraints.py
"""Integration tests for field constraints endpoint."""

import pytest

pytestmark = pytest.mark.integration

import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.database import FieldConstraintModel, Namespace, TypeModel
from conftest import TEST_USER_ID


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
async def test_provisioning_creates_constraints(
    db_session: AsyncSession,
    provisioned_namespace: Namespace,
):
    """Test that provisioning creates copies of all global constraints for the user."""
    result = await db_session.execute(
        select(FieldConstraintModel).where(
            FieldConstraintModel.namespace_id == provisioned_namespace.id,
        )
    )
    constraints = result.scalars().all()

    # Should have all 8 standard constraints
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
async def test_list_constraints_includes_custom_and_provisioned(
    db_session: AsyncSession,
    test_namespace: Namespace,
    test_constraint: FieldConstraintModel,
    provisioned_namespace: Namespace,
):
    """Test that user sees both provisioned and custom constraints."""
    result = await db_session.execute(
        select(FieldConstraintModel)
        .join(Namespace)
        .where(Namespace.user_id == TEST_USER_ID)
    )
    constraints = result.scalars().all()

    # Should have at least 8 provisioned constraints + 1 custom constraint
    assert len(constraints) >= 9

    constraint_names = {c.name for c in constraints}
    assert "custom_test" in constraint_names
    assert "max_length" in constraint_names


@pytest.mark.asyncio
async def test_provisioned_constraints_include_standard_set(
    db_session: AsyncSession,
    provisioned_namespace: Namespace,
):
    """Test that standard constraints are available after provisioning."""
    expected_constraints = ["max_length", "min_length", "pattern", "gt"]

    result = await db_session.execute(
        select(FieldConstraintModel).where(
            FieldConstraintModel.namespace_id == provisioned_namespace.id,
        )
    )
    constraints = result.scalars().all()

    constraint_names = {c.name for c in constraints}
    for expected_name in expected_constraints:
        assert (
            expected_name in constraint_names
        ), f"Constraint '{expected_name}' should be available after provisioning"


@pytest.mark.asyncio
async def test_provisioned_constraints_have_compatible_types(
    db_session: AsyncSession,
    provisioned_namespace: Namespace,
):
    """Test that provisioned constraints have compatible_types set."""
    result = await db_session.execute(
        select(FieldConstraintModel).where(
            FieldConstraintModel.namespace_id == provisioned_namespace.id,
        )
    )
    constraints = result.scalars().all()

    assert len(constraints) > 0
    assert all(len(c.compatible_types) > 0 for c in constraints)
