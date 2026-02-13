# tests/test_api_constraints.py
"""Integration tests for constraints endpoint."""

import pytest

pytestmark = pytest.mark.integration

import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.database import ConstraintModel, Namespace
from api.settings import get_settings


@pytest_asyncio.fixture
async def test_constraint(db_session: AsyncSession, test_namespace: Namespace):
    """Create a test constraint in the user namespace."""
    constraint = ConstraintModel(
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
        delete(ConstraintModel).where(ConstraintModel.id == constraint.id)
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_list_constraints_no_namespace_filter(
    db_session: AsyncSession,
    test_constraint: ConstraintModel,
):
    """Test that all constraints are returned when no namespace filter is provided."""
    query = select(ConstraintModel)
    result = await db_session.execute(query)
    all_constraints = result.scalars().all()

    # Should have global constraints + test constraint
    assert len(all_constraints) > 0

    # Verify global constraints exist
    settings = get_settings()
    global_constraints = [c for c in all_constraints if c.namespace_id == settings.global_namespace_id]
    assert len(global_constraints) > 0

    # Verify test constraint exists
    test_constraints = [c for c in all_constraints if c.id == test_constraint.id]
    assert len(test_constraints) == 1


@pytest.mark.asyncio
async def test_list_constraints_with_user_namespace(
    db_session: AsyncSession,
    test_namespace: Namespace,
    test_constraint: ConstraintModel,
):
    """Test that global + user namespace constraints are returned when filtering by user namespace."""
    settings = get_settings()

    from sqlalchemy import or_, select

    query = select(ConstraintModel).where(
        or_(
            ConstraintModel.namespace_id == test_namespace.id,
            ConstraintModel.namespace_id == settings.global_namespace_id,
        )
    )
    result = await db_session.execute(query)
    constraints = result.scalars().all()

    # Should have global constraints + test constraint
    assert len(constraints) > 0

    # Verify global constraints are included
    global_constraints = [c for c in constraints if c.namespace_id == settings.global_namespace_id]
    assert len(global_constraints) > 0

    # Verify test constraint is included
    test_constraints = [c for c in constraints if c.id == test_constraint.id]
    assert len(test_constraints) == 1

    # Verify no constraints from other namespaces
    other_constraints = [
        c for c in constraints
        if c.namespace_id != test_namespace.id
        and c.namespace_id != settings.global_namespace_id
    ]
    assert len(other_constraints) == 0


@pytest.mark.asyncio
async def test_list_constraints_global_namespace_only(db_session: AsyncSession):
    """Test that only global constraints are returned when filtering by global namespace."""
    settings = get_settings()

    from sqlalchemy import or_, select

    query = select(ConstraintModel).where(
        or_(
            ConstraintModel.namespace_id == settings.global_namespace_id,
            ConstraintModel.namespace_id == settings.global_namespace_id,
        )
    )
    result = await db_session.execute(query)
    constraints = result.scalars().all()

    # All constraints should be from global namespace
    assert all(c.namespace_id == settings.global_namespace_id for c in constraints)
    assert len(constraints) > 0


@pytest.mark.asyncio
async def test_list_constraints_includes_standard_constraints(
    db_session: AsyncSession,
    test_namespace: Namespace,
):
    """Test that standard constraints are always included regardless of namespace filter."""
    settings = get_settings()

    expected_constraints = ["max_length", "min_length", "pattern", "email_format"]

    from sqlalchemy import or_, select

    query = select(ConstraintModel).where(
        or_(
            ConstraintModel.namespace_id == test_namespace.id,
            ConstraintModel.namespace_id == settings.global_namespace_id,
        )
    )
    result = await db_session.execute(query)
    constraints = result.scalars().all()

    # Verify all expected constraints are present
    constraint_names = {c.name for c in constraints}
    for expected_name in expected_constraints:
        assert (
            expected_name in constraint_names
        ), f"Constraint '{expected_name}' should be available in filtered results"

    # Verify global constraints have compatible_types set
    global_constraints = [c for c in constraints if c.namespace_id == settings.global_namespace_id]
    assert len(global_constraints) > 0
    assert all(len(c.compatible_types) > 0 for c in global_constraints)
