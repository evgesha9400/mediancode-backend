# src/api/routers/fields.py
"""Router for Field endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import CurrentUser
from api.database import get_db
from api.schemas.field import (
    FieldConstraintValueResponse,
    FieldCreate,
    FieldResponse,
    FieldUpdate,
)
from api.services.field import FieldService, get_field_service

router = APIRouter(prefix="/fields", tags=["Fields"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


def get_service(db: DbSession) -> FieldService:
    """Get field service instance.

    :param db: Database session.
    :returns: FieldService instance.
    """
    return get_field_service(db)


async def _to_response(field, service: FieldService) -> FieldResponse:
    """Convert a field model to response schema.

    :param field: Field database model.
    :param service: FieldService instance for fetching usage data.
    :returns: FieldResponse schema.
    """
    used_in_apis = await service.get_used_in_apis(field.id)
    constraints = [
        FieldConstraintValueResponse(
            constraint_id=cv.constraint_id,
            name=cv.constraint.name,
            value=cv.value,
        )
        for cv in field.constraint_values
    ]
    return FieldResponse(
        id=field.id,
        namespace_id=field.namespace_id,
        name=field.name,
        type_id=field.type_id,
        description=field.description,
        default_value=field.default_value,
        used_in_apis=used_in_apis,
        constraints=constraints,
    )


@router.get(
    "",
    response_model=list[FieldResponse],
    summary="List all fields",
    description="Retrieve all field definitions accessible to the authenticated user.",
)
async def list_fields(
    user_id: CurrentUser,
    db: DbSession,
    namespace_id: str | None = None,
) -> list[FieldResponse]:
    """List all fields accessible to the user.

    :param user_id: Authenticated user ID.
    :param db: Database session.
    :param namespace_id: Optional namespace filter.
    :returns: List of field responses.
    """
    service = get_service(db)
    fields = await service.list_for_user(user_id, namespace_id)
    return [await _to_response(f, service) for f in fields]


@router.post(
    "",
    response_model=FieldResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new field",
    description="Create a new field definition.",
)
async def create_field(
    data: FieldCreate,
    user_id: CurrentUser,
    db: DbSession,
) -> FieldResponse:
    """Create a new field.

    :param data: Field creation data.
    :param user_id: Authenticated user ID.
    :param db: Database session.
    :returns: Created field response.
    """
    service = get_service(db)
    field = await service.create_for_user(user_id, data)
    # Reload with relationships
    field = await service.get_by_id_for_user(field.id, user_id)
    return await _to_response(field, service)


@router.get(
    "/{field_id}",
    response_model=FieldResponse,
    summary="Get field by ID",
    description="Retrieve a specific field by its ID.",
)
async def get_field(
    field_id: str,
    user_id: CurrentUser,
    db: DbSession,
) -> FieldResponse:
    """Get a field by ID.

    :param field_id: Field unique identifier.
    :param user_id: Authenticated user ID.
    :param db: Database session.
    :returns: Field response.
    :raises HTTPException: If field not found.
    """
    service = get_service(db)
    field = await service.get_by_id_for_user(field_id, user_id)
    if not field:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Field with ID '{field_id}' not found",
        )
    return await _to_response(field, service)


@router.put(
    "/{field_id}",
    response_model=FieldResponse,
    summary="Update field",
    description="Update an existing field definition.",
)
async def update_field(
    field_id: str,
    data: FieldUpdate,
    user_id: CurrentUser,
    db: DbSession,
) -> FieldResponse:
    """Update a field.

    :param field_id: Field unique identifier.
    :param data: Field update data.
    :param user_id: Authenticated user ID.
    :param db: Database session.
    :returns: Updated field response.
    :raises HTTPException: If field not found.
    """
    service = get_service(db)
    field = await service.get_by_id_for_user(field_id, user_id)
    if not field:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Field with ID '{field_id}' not found",
        )

    # Verify ownership
    if field.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify field in locked namespace",
        )

    updated = await service.update_field(field, data)
    # Reload with relationships
    updated = await service.get_by_id_for_user(updated.id, user_id)
    return await _to_response(updated, service)


@router.delete(
    "/{field_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete field",
    description="Delete a field. Cannot delete if used in objects.",
)
async def delete_field(
    field_id: str,
    user_id: CurrentUser,
    db: DbSession,
) -> None:
    """Delete a field.

    :param field_id: Field unique identifier.
    :param user_id: Authenticated user ID.
    :param db: Database session.
    :raises HTTPException: If field not found or in use.
    """
    service = get_service(db)
    field = await service.get_by_id_for_user(field_id, user_id)
    if not field:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Field with ID '{field_id}' not found",
        )

    # Verify ownership
    if field.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete field in locked namespace",
        )

    await service.delete_field(field)
