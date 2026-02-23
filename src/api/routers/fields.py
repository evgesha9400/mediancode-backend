# src/api/routers/fields.py
"""Router for Field endpoints."""

from fastapi import APIRouter, HTTPException, status

from api.deps import DbSession, ProvisionedUser
from api.schemas.field import (
    FieldConstraintValueResponse,
    FieldCreate,
    FieldResponse,
    FieldUpdate,
    FieldValidatorResponse,
)
from api.services.field import FieldService, get_field_service

router = APIRouter(prefix="/fields", tags=["Fields"])


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
    validators = [
        FieldValidatorResponse(
            id=v.id,
            function_name=v.function_name,
            mode=v.mode,
            function_body=v.function_body,
            description=v.description,
        )
        for v in sorted(field.validators, key=lambda x: x.position)
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
        validators=validators,
    )


@router.get(
    "",
    response_model=list[FieldResponse],
    summary="List all fields",
    description="Retrieve all field definitions accessible to the authenticated user.",
)
async def list_fields(
    user: ProvisionedUser,
    db: DbSession,
    namespace_id: str | None = None,
) -> list[FieldResponse]:
    """List all fields accessible to the user.

    :param user: Authenticated user.
    :param db: Database session.
    :param namespace_id: Optional namespace filter.
    :returns: List of field responses.
    """
    service = get_service(db)
    fields = await service.list_for_user(user.id, namespace_id)
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
    user: ProvisionedUser,
    db: DbSession,
) -> FieldResponse:
    """Create a new field.

    :param data: Field creation data.
    :param user: Authenticated user.
    :param db: Database session.
    :returns: Created field response.
    """
    service = get_service(db)
    field = await service.create_for_user(user.id, data)
    # Reload with relationships
    field = await service.get_by_id_for_user(field.id, user.id)
    return await _to_response(field, service)


@router.get(
    "/{field_id}",
    response_model=FieldResponse,
    summary="Get field by ID",
    description="Retrieve a specific field by its ID.",
)
async def get_field(
    field_id: str,
    user: ProvisionedUser,
    db: DbSession,
) -> FieldResponse:
    """Get a field by ID.

    :param field_id: Field unique identifier.
    :param user: Authenticated user.
    :param db: Database session.
    :returns: Field response.
    :raises HTTPException: If field not found.
    """
    service = get_service(db)
    field = await service.get_by_id_for_user(field_id, user.id)
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
    user: ProvisionedUser,
    db: DbSession,
) -> FieldResponse:
    """Update a field.

    :param field_id: Field unique identifier.
    :param data: Field update data.
    :param user: Authenticated user.
    :param db: Database session.
    :returns: Updated field response.
    :raises HTTPException: If field not found.
    """
    service = get_service(db)
    field = await service.get_by_id_for_user(field_id, user.id)
    if not field:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Field with ID '{field_id}' not found",
        )

    # Verify ownership
    if field.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify field in locked namespace",
        )

    updated = await service.update_field(field, data)
    # Reload with relationships
    updated = await service.get_by_id_for_user(updated.id, user.id)
    return await _to_response(updated, service)


@router.delete(
    "/{field_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete field",
    description="Delete a field. Cannot delete if used in objects.",
)
async def delete_field(
    field_id: str,
    user: ProvisionedUser,
    db: DbSession,
) -> None:
    """Delete a field.

    :param field_id: Field unique identifier.
    :param user: Authenticated user.
    :param db: Database session.
    :raises HTTPException: If field not found or in use.
    """
    service = get_service(db)
    field = await service.get_by_id_for_user(field_id, user.id)
    if not field:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Field with ID '{field_id}' not found",
        )

    # Verify ownership
    if field.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete field in locked namespace",
        )

    await service.delete_field(field)
