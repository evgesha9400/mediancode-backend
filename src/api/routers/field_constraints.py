# src/api/routers/field_constraints.py
"""Router for Field Constraint endpoints (read-only)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import CurrentUser
from api.database import get_db
from api.models.database import FieldConstraintModel, FieldConstraintValueAssociation
from api.schemas.field_constraint import FieldConstraintResponse
from api.settings import get_settings

router = APIRouter(prefix="/field-constraints", tags=["Field Constraints"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_field_counts_by_constraint(db: AsyncSession) -> dict[str, int]:
    """Get count of fields for each field constraint.

    :param db: Database session.
    :returns: Dict mapping field constraint ID (as string) to field count.
    """
    query = select(
        FieldConstraintValueAssociation.constraint_id,
        func.count(FieldConstraintValueAssociation.id),
    ).group_by(FieldConstraintValueAssociation.constraint_id)
    result = await db.execute(query)
    return {str(row[0]): row[1] for row in result.fetchall()}


@router.get(
    "",
    response_model=list[FieldConstraintResponse],
    summary="List all field constraints",
    description="Retrieve all field constraint definitions (Pydantic Field constraints).",
)
async def list_field_constraints(
    user_id: CurrentUser,
    db: DbSession,
    namespace_id: str | None = None,
) -> list[FieldConstraintResponse]:
    """List all field constraints.

    :param user_id: Authenticated user ID.
    :param db: Database session.
    :param namespace_id: Optional namespace filter. If provided, returns constraints
        from the specified namespace plus all global constraints.
    :returns: List of field constraint responses.
    """
    query = select(FieldConstraintModel)
    if namespace_id:
        settings = get_settings()
        query = query.where(
            or_(
                FieldConstraintModel.namespace_id == namespace_id,
                FieldConstraintModel.namespace_id == settings.global_namespace_id,
            )
        )

    result = await db.execute(query)
    constraints = result.scalars().all()

    field_counts = await get_field_counts_by_constraint(db)

    return [
        FieldConstraintResponse(
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
