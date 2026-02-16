# src/api/routers/types.py
"""Router for Type endpoints (read-only)."""

from fastapi import APIRouter

from api.deps import DbSession, ProvisionedUser
from api.schemas.type import TypeResponse
from api.services.type import TypeService, get_type_service

router = APIRouter(prefix="/types", tags=["Types"])


def get_service(db: DbSession) -> TypeService:
    """Get type service instance.

    :param db: Database session.
    :returns: TypeService instance.
    """
    return get_type_service(db)


@router.get(
    "",
    response_model=list[TypeResponse],
    summary="List all types",
    description="Retrieve all type definitions accessible to the authenticated user.",
)
async def list_types(
    user_id: ProvisionedUser,
    db: DbSession,
    namespace_id: str | None = None,
) -> list[TypeResponse]:
    """List all types accessible to the user.

    :param user_id: Authenticated user ID.
    :param db: Database session.
    :param namespace_id: Optional namespace filter.
    :returns: List of type responses.
    """
    service = get_service(db)
    types = await service.list_for_user(user_id, namespace_id)
    field_counts = await service.get_field_counts_for_user(user_id)

    return [
        TypeResponse(
            id=t.id,
            namespace_id=t.namespace_id,
            name=t.name,
            python_type=t.python_type,
            description=t.description,
            import_path=t.import_path,
            parent_type_id=t.parent_type_id,
            used_in_fields=field_counts.get(str(t.id), 0),
        )
        for t in types
    ]
