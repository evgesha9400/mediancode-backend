# src/api/routers/field_constraints.py
"""Router for Field Constraint endpoints (read-only)."""

from fastapi import APIRouter

from api.deps import DbSession, ProvisionedUser
from api.schemas.field_constraint import FieldConstraintResponse
from api.services.field_constraint import (
    FieldConstraintService,
    get_field_constraint_service,
)

router = APIRouter(prefix="/field-constraints", tags=["Field Constraints"])


def get_service(db: DbSession) -> FieldConstraintService:
    """Get field constraint service instance.

    :param db: Database session.
    :returns: FieldConstraintService instance.
    """
    return get_field_constraint_service(db)


@router.get(
    "",
    response_model=list[FieldConstraintResponse],
    summary="List all field constraints",
    description="Retrieve all field constraint definitions accessible to the authenticated user.",
)
async def list_field_constraints(
    user_id: ProvisionedUser,
    db: DbSession,
    namespace_id: str | None = None,
) -> list[FieldConstraintResponse]:
    """List all field constraints accessible to the user.

    :param user_id: Authenticated user ID.
    :param db: Database session.
    :param namespace_id: Optional namespace filter.
    :returns: List of field constraint responses.
    """
    service = get_service(db)
    constraints = await service.list_for_user(user_id, namespace_id)
    field_counts = await service.get_field_counts_for_user(user_id)

    return [
        FieldConstraintResponse(
            id=c.id,
            namespace_id=c.namespace_id,
            name=c.name,
            description=c.description,
            parameter_types=c.parameter_types,
            docs_url=c.docs_url,
            compatible_types=c.compatible_types,
            used_in_fields=field_counts.get(str(c.id), 0),
        )
        for c in constraints
    ]
