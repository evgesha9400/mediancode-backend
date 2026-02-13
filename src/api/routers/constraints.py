# src/api/routers/constraints.py
"""Router for Constraint endpoints (read-only)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import CurrentUser
from api.database import get_db
from api.models.database import ConstraintModel, FieldModel, FieldValidator
from api.schemas.constraint import ConstraintResponse, FieldReferenceSchema
from api.settings import get_settings

router = APIRouter(prefix="/constraints", tags=["Constraints"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_fields_by_constraint(
    db: AsyncSession,
) -> dict[str, list[FieldReferenceSchema]]:
    """Get fields grouped by constraint name.

    :param db: Database session.
    :returns: Dict mapping constraint name to list of field references.
    """
    query = select(FieldValidator.name, FieldModel.id, FieldModel.name).join(
        FieldModel, FieldValidator.field_id == FieldModel.id
    )
    result = await db.execute(query)

    fields_by_constraint: dict[str, list[FieldReferenceSchema]] = {}
    for constraint_name, field_id, field_name in result.fetchall():
        if constraint_name not in fields_by_constraint:
            fields_by_constraint[constraint_name] = []
        fields_by_constraint[constraint_name].append(
            FieldReferenceSchema(name=field_name, field_id=field_id)
        )

    return fields_by_constraint


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

    # Get fields using each constraint
    fields_by_constraint = await get_fields_by_constraint(db)

    return [
        ConstraintResponse(
            id=c.id,
            namespace_id=c.namespace_id,
            name=c.name,
            description=c.description,
            parameter_type=c.parameter_type,
            docs_url=c.docs_url,
            compatible_types=c.compatible_types,
            used_in_fields=len(fields_by_constraint.get(c.name, [])),
            fields_using_constraint=fields_by_constraint.get(c.name, []),
        )
        for c in constraints
    ]
