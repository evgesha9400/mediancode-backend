# src/api/routers/tags.py
"""Router for Tag endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import CurrentUser
from api.database import get_db
from api.schemas.tag import TagCreate, TagResponse, TagUpdate
from api.services.tag import TagService, get_tag_service

router = APIRouter(prefix="/tags", tags=["Tags"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


def get_service(db: DbSession) -> TagService:
    """Get tag service instance.

    :param db: Database session.
    :returns: TagService instance.
    """
    return get_tag_service(db)


@router.get(
    "",
    response_model=list[TagResponse],
    summary="List all tags",
    description="Retrieve all endpoint tags accessible to the authenticated user.",
)
async def list_tags(
    user_id: CurrentUser,
    db: DbSession,
    namespace_id: str | None = None,
) -> list[TagResponse]:
    """List all tags accessible to the user.

    :param user_id: Authenticated user ID.
    :param db: Database session.
    :param namespace_id: Optional namespace filter.
    :returns: List of tag responses.
    """
    service = get_service(db)
    tags = await service.list_for_user(user_id, namespace_id)
    return [TagResponse.model_validate(tag) for tag in tags]


@router.post(
    "",
    response_model=TagResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new tag",
    description="Create a new endpoint tag.",
)
async def create_tag(
    data: TagCreate,
    user_id: CurrentUser,
    db: DbSession,
) -> TagResponse:
    """Create a new tag.

    :param data: Tag creation data.
    :param user_id: Authenticated user ID.
    :param db: Database session.
    :returns: Created tag response.
    """
    service = get_service(db)
    tag = await service.create_for_user(user_id, data)
    return TagResponse.model_validate(tag)


@router.get(
    "/{tag_id}",
    response_model=TagResponse,
    summary="Get tag by ID",
    description="Retrieve a specific tag by its ID.",
)
async def get_tag(
    tag_id: str,
    user_id: CurrentUser,
    db: DbSession,
) -> TagResponse:
    """Get a tag by ID.

    :param tag_id: Tag unique identifier.
    :param user_id: Authenticated user ID.
    :param db: Database session.
    :returns: Tag response.
    :raises HTTPException: If tag not found.
    """
    service = get_service(db)
    tag = await service.get_by_id_for_user(tag_id, user_id)
    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tag with ID '{tag_id}' not found",
        )
    return TagResponse.model_validate(tag)


@router.put(
    "/{tag_id}",
    response_model=TagResponse,
    summary="Update tag",
    description="Update an existing endpoint tag.",
)
async def update_tag(
    tag_id: str,
    data: TagUpdate,
    user_id: CurrentUser,
    db: DbSession,
) -> TagResponse:
    """Update a tag.

    :param tag_id: Tag unique identifier.
    :param data: Tag update data.
    :param user_id: Authenticated user ID.
    :param db: Database session.
    :returns: Updated tag response.
    :raises HTTPException: If tag not found.
    """
    service = get_service(db)
    tag = await service.get_by_id_for_user(tag_id, user_id)
    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tag with ID '{tag_id}' not found",
        )

    # Verify ownership
    if tag.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify tag in locked namespace",
        )

    updated = await service.update_tag(tag, data)
    return TagResponse.model_validate(updated)


@router.delete(
    "/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete tag",
    description="Delete a tag. Cannot delete if used by endpoints.",
)
async def delete_tag(
    tag_id: str,
    user_id: CurrentUser,
    db: DbSession,
) -> None:
    """Delete a tag.

    :param tag_id: Tag unique identifier.
    :param user_id: Authenticated user ID.
    :param db: Database session.
    :raises HTTPException: If tag not found or in use.
    """
    service = get_service(db)
    tag = await service.get_by_id_for_user(tag_id, user_id)
    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tag with ID '{tag_id}' not found",
        )

    # Verify ownership
    if tag.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete tag in locked namespace",
        )

    await service.delete_tag(tag)
