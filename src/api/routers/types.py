# src/api/routers/types.py
"""Router for Type endpoints (read-only)."""

from fastapi import APIRouter

from api.auth import CurrentUser
from api.data import get_global_types
from api.schemas.type import TypeResponse

router = APIRouter(prefix="/types", tags=["Types"])


@router.get(
    "",
    response_model=list[TypeResponse],
    summary="List all types",
    description="Retrieve all primitive and abstract type definitions.",
)
async def list_types(
    user_id: CurrentUser,
) -> list[TypeResponse]:
    """List all global types.

    :param user_id: Authenticated user ID.
    :returns: List of type responses.
    """
    types = get_global_types()
    return [
        TypeResponse(
            name=t["name"],
            category=t["category"],
            python_type=t["pythonType"],
            description=t["description"],
            validator_categories=t["validatorCategories"],
        )
        for t in types
    ]
