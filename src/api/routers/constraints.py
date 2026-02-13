# src/api/routers/constraints.py
"""Router for Constraint endpoints (read-only)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import CurrentUser
from api.database import get_db
from api.models.database import ConstraintFieldValueAssociation, ConstraintModel
from api.schemas.constraint import ConstraintResponse
from api.settings import get_settings

router = APIRouter(prefix="/constraints", tags=["Constraints"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_field_counts_by_constraint(db: AsyncSession) -> dict[str, int]:
    """Get count of fields for each constraint.

    :param db: Database session.
    :returns: Dict mapping constraint ID (as string) to field count.
    """
    query = select(
        ConstraintFieldValueAssociation.constraint_id,
        func.count(ConstraintFieldValueAssociation.id),
    ).group_by(ConstraintFieldValueAssociation.constraint_id)
    result = await db.execute(query)
    return {str(row[0]): row[1] for row in result.fetchall()}


@router.get(
    "",
    response_model=list[ConstraintResponse],
    summary="List all constraints",
    description="Retrieve all constraint definitions (Pydantic Field constraints).",
)
async def list_constraints(
    user_id: CurrentUser,
    db: DbSession,
    namespace_id: str | None = None,
) -> list[ConstraintResponse]:
    """List all constraints.

    :param user_id: Authenticated user ID.
    :param db: Database session.
    :param namespace_id: Optional namespace filter. If provided, returns constraints
        from the specified namespace plus all global constraints.
    :returns: List of constraint responses.
    """
    query = select(ConstraintModel)
    if namespace_id:
        settings = get_settings()
        query = query.where(
            or_(
                ConstraintModel.namespace_id == namespace_id,
                ConstraintModel.namespace_id == settings.global_namespace_id,
            )
        )

    result = await db.execute(query)
    constraints = result.scalars().all()

    field_counts = await get_field_counts_by_constraint(db)

    return [
        ConstraintResponse(
            id=c.id,
            namespace_id=c.namespace_id,
            name=c.name,
            description=c.description,
            parameter_type=c.parameter_type,
            docs_url=c.docs_url,
            compatible_types=c.compatible_types,
            used_in_fields=field_counts.get(str(c.id), 0),
        )
        for c in constraints
    ]
