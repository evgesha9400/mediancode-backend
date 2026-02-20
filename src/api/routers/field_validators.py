# src/api/routers/field_validators.py
"""Router for Field Validator endpoints."""

from fastapi import APIRouter, HTTPException, status

from api.deps import DbSession, ProvisionedUser
from api.schemas.field_validator import (
    FieldValidatorCreate,
    FieldValidatorResponse,
    FieldValidatorUpdate,
)
from api.services.field_validator import (
    FieldValidatorService,
    get_field_validator_service,
)

router = APIRouter(prefix="/field-validators", tags=["Field Validators"])


def get_service(db: DbSession) -> FieldValidatorService:
    """Get field validator service instance.

    :param db: Database session.
    :returns: FieldValidatorService instance.
    """
    return get_field_validator_service(db)


@router.get(
    "",
    response_model=list[FieldValidatorResponse],
    summary="List all field validators",
    description="Retrieve all field validator definitions accessible to the authenticated user.",
)
async def list_field_validators(
    user: ProvisionedUser,
    db: DbSession,
    namespace_id: str | None = None,
) -> list[FieldValidatorResponse]:
    """List all field validators accessible to the user.

    :param user: Authenticated user.
    :param db: Database session.
    :param namespace_id: Optional namespace filter.
    :returns: List of field validator responses.
    """
    service = get_service(db)
    validators = await service.list_for_user(user.id, namespace_id)
    field_counts = await service.get_field_counts_for_user(user.id)

    return [
        FieldValidatorResponse(
            id=v.id,
            namespace_id=v.namespace_id,
            name=v.name,
            function_name=v.function_name,
            mode=v.mode,
            function_body=v.function_body,
            description=v.description,
            compatible_types=v.compatible_types,
            used_in_fields=field_counts.get(str(v.id), 0),
        )
        for v in validators
    ]


@router.get(
    "/{validator_id}",
    response_model=FieldValidatorResponse,
    summary="Get field validator by ID",
    description="Retrieve a specific field validator by its ID.",
)
async def get_field_validator(
    validator_id: str,
    user: ProvisionedUser,
    db: DbSession,
) -> FieldValidatorResponse:
    """Get a field validator by ID.

    :param validator_id: Validator unique identifier.
    :param user: Authenticated user.
    :param db: Database session.
    :returns: Field validator response.
    :raises HTTPException: If validator not found.
    """
    service = get_service(db)
    validator = await service.get_visible_by_id(validator_id, user.id)
    if not validator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Field validator with ID '{validator_id}' not found",
        )
    field_counts = await service.get_field_counts_for_user(user.id)

    return FieldValidatorResponse(
        id=validator.id,
        namespace_id=validator.namespace_id,
        name=validator.name,
        function_name=validator.function_name,
        mode=validator.mode,
        function_body=validator.function_body,
        description=validator.description,
        compatible_types=validator.compatible_types,
        used_in_fields=field_counts.get(str(validator.id), 0),
    )


@router.post(
    "",
    response_model=FieldValidatorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new field validator",
    description="Create a new field validator definition.",
)
async def create_field_validator(
    data: FieldValidatorCreate,
    user: ProvisionedUser,
    db: DbSession,
) -> FieldValidatorResponse:
    """Create a new field validator.

    :param data: Validator creation data.
    :param user: Authenticated user.
    :param db: Database session.
    :returns: Created field validator response.
    """
    service = get_service(db)
    validator = await service.create_for_user(user.id, data)

    return FieldValidatorResponse(
        id=validator.id,
        namespace_id=validator.namespace_id,
        name=validator.name,
        function_name=validator.function_name,
        mode=validator.mode,
        function_body=validator.function_body,
        description=validator.description,
        compatible_types=validator.compatible_types,
        used_in_fields=0,
    )


@router.put(
    "/{validator_id}",
    response_model=FieldValidatorResponse,
    summary="Update field validator",
    description="Update an existing field validator definition.",
)
async def update_field_validator(
    validator_id: str,
    data: FieldValidatorUpdate,
    user: ProvisionedUser,
    db: DbSession,
) -> FieldValidatorResponse:
    """Update a field validator.

    :param validator_id: Validator unique identifier.
    :param data: Validator update data.
    :param user: Authenticated user.
    :param db: Database session.
    :returns: Updated field validator response.
    :raises HTTPException: If validator not found.
    """
    service = get_service(db)
    validator = await service.get_by_id_for_user(validator_id, user.id)
    if not validator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Field validator with ID '{validator_id}' not found",
        )

    if validator.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify validator in locked namespace",
        )

    updated = await service.update_validator(validator, data)
    field_counts = await service.get_field_counts_for_user(user.id)

    return FieldValidatorResponse(
        id=updated.id,
        namespace_id=updated.namespace_id,
        name=updated.name,
        function_name=updated.function_name,
        mode=updated.mode,
        function_body=updated.function_body,
        description=updated.description,
        compatible_types=updated.compatible_types,
        used_in_fields=field_counts.get(str(updated.id), 0),
    )


@router.delete(
    "/{validator_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete field validator",
    description="Delete a field validator. Cannot delete if used in fields.",
)
async def delete_field_validator(
    validator_id: str,
    user: ProvisionedUser,
    db: DbSession,
) -> None:
    """Delete a field validator.

    :param validator_id: Validator unique identifier.
    :param user: Authenticated user.
    :param db: Database session.
    :raises HTTPException: If validator not found or in use.
    """
    service = get_service(db)
    validator = await service.get_by_id_for_user(validator_id, user.id)
    if not validator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Field validator with ID '{validator_id}' not found",
        )

    if validator.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete validator in locked namespace",
        )

    await service.delete_validator(validator)
