# src/api/routers/types.py
"""Router for Type endpoints (read-only)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import CurrentUser
from api.database import get_db
from api.models.database import FieldModel, TypeModel
from api.schemas.type import TypeResponse
from api.settings import get_settings

router = APIRouter(prefix="/types", tags=["Types"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_field_counts_by_type(db: AsyncSession) -> dict[str, int]:
    """Get count of fields for each type.

    :param db: Database session.
    :returns: Dict mapping type ID (as string) to field count.
    """
    query = (
        select(FieldModel.type_id, func.count(FieldModel.id))
        .group_by(FieldModel.type_id)
    )
    result = await db.execute(query)
    return {str(row[0]): row[1] for row in result.fetchall()}


@router.get(
    "",
    response_model=list[TypeResponse],
    summary="List all types",
    description="Retrieve all primitive and abstract type definitions.",
)
async def list_types(
    user_id: CurrentUser,
    db: DbSession,
    namespace_id: str | None = None,
) -> list[TypeResponse]:
    """List all types.

    :param user_id: Authenticated user ID.
    :param db: Database session.
    :param namespace_id: Optional namespace filter. If provided, returns types
        from the specified namespace plus all global built-in types.
    :returns: List of type responses.
    """
    # Query types from database
    query = select(TypeModel)
    if namespace_id:
        settings = get_settings()
        query = query.where(
            or_(
                TypeModel.namespace_id == namespace_id,
                TypeModel.namespace_id == settings.global_namespace_id,
            )
        )

    result = await db.execute(query)
    types = result.scalars().all()

    # Get field counts
    field_counts = await get_field_counts_by_type(db)

    return [
        TypeResponse(
            id=t.id,
            namespace_id=t.namespace_id,
            name=t.name,
            category=t.category,
            python_type=t.python_type,
            description=t.description,
            compatible_types=t.compatible_types,
            used_in_fields=field_counts.get(str(t.id), 0),
        )
        for t in types
    ]
