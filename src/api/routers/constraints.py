# src/api/routers/constraints.py
"""Router for Constraint endpoints (read-only)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import CurrentUser
from api.database import get_db
from api.models.database import ConstraintModel
from api.schemas.constraint import ConstraintResponse
from api.settings import get_settings

router = APIRouter(prefix="/constraints", tags=["Constraints"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


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

    # TODO: Usage statistics (used_in_fields, fields_using_constraint) will be
    # re-added when constraint_field_values_associations is wired up
    return [
        ConstraintResponse(
            id=c.id,
            namespace_id=c.namespace_id,
            name=c.name,
            description=c.description,
            parameter_type=c.parameter_type,
            docs_url=c.docs_url,
            compatible_types=c.compatible_types,
        )
        for c in constraints
    ]
