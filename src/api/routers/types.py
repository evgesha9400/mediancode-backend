# src/api/routers/types.py
"""Router for Type endpoints (read-only)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import CurrentUser
from api.data import get_global_types
from api.database import get_db
from api.models.database import FieldModel
from api.schemas.type import TypeResponse

router = APIRouter(prefix="/types", tags=["Types"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_field_counts_by_type(db: AsyncSession) -> dict[str, int]:
    """Get count of fields for each type.

    :param db: Database session.
    :returns: Dict mapping type name to field count.
    """
    query = (
        select(FieldModel.type, func.count(FieldModel.id))
        .group_by(FieldModel.type)
    )
    result = await db.execute(query)
    return {row[0]: row[1] for row in result.fetchall()}


@router.get(
    "",
    response_model=list[TypeResponse],
    summary="List all types",
    description="Retrieve all primitive and abstract type definitions.",
)
async def list_types(
    user_id: CurrentUser,
    db: DbSession,
) -> list[TypeResponse]:
    """List all global types.

    :param user_id: Authenticated user ID.
    :param db: Database session.
    :returns: List of type responses.
    """
    types = get_global_types()
    field_counts = await get_field_counts_by_type(db)

    return [
        TypeResponse(
            name=t["name"],
            category=t["category"],
            python_type=t["pythonType"],
            description=t["description"],
            validator_categories=t["validatorCategories"],
            used_in_fields=field_counts.get(t["name"], 0),
        )
        for t in types
    ]
