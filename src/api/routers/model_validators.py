# src/api/routers/model_validators.py
"""Router for Model Validator endpoints."""

from fastapi import APIRouter, HTTPException, status

from api.deps import DbSession, ProvisionedUser
from api.schemas.model_validator import (
    ModelValidatorCreate,
    ModelValidatorResponse,
    ModelValidatorUpdate,
)
from api.services.model_validator import (
    ModelValidatorService,
    get_model_validator_service,
)

router = APIRouter(prefix="/model-validators", tags=["Model Validators"])


def get_service(db: DbSession) -> ModelValidatorService:
    """Get model validator service instance.

    :param db: Database session.
    :returns: ModelValidatorService instance.
    """
    return get_model_validator_service(db)


@router.get(
    "",
    response_model=list[ModelValidatorResponse],
    summary="List all model validators",
    description="Retrieve all model validator definitions accessible to the authenticated user.",
)
async def list_model_validators(
    user: ProvisionedUser,
    db: DbSession,
    namespace_id: str | None = None,
) -> list[ModelValidatorResponse]:
    """List all model validators accessible to the user.

    :param user: Authenticated user.
    :param db: Database session.
    :param namespace_id: Optional namespace filter.
    :returns: List of model validator responses.
    """
    service = get_service(db)
    validators = await service.list_for_user(user.id, namespace_id)
    object_counts = await service.get_object_counts_for_user(user.id)

    return [
        ModelValidatorResponse(
            id=v.id,
            namespace_id=v.namespace_id,
            name=v.name,
            description=v.description,
            required_fields=v.required_fields,
            mode=v.mode,
            code=v.code,
            used_in_objects=object_counts.get(str(v.id), 0),
        )
        for v in validators
    ]


@router.get(
    "/{validator_id}",
    response_model=ModelValidatorResponse,
    summary="Get model validator by ID",
    description="Retrieve a specific model validator by its ID.",
)
async def get_model_validator(
    validator_id: str,
    user: ProvisionedUser,
    db: DbSession,
) -> ModelValidatorResponse:
    """Get a model validator by ID.

    :param validator_id: Validator unique identifier.
    :param user: Authenticated user.
    :param db: Database session.
    :returns: Model validator response.
    :raises HTTPException: If validator not found.
    """
    service = get_service(db)
    validator = await service.get_visible_by_id(validator_id, user.id)
    if not validator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model validator with ID '{validator_id}' not found",
        )
    object_counts = await service.get_object_counts_for_user(user.id)

    return ModelValidatorResponse(
        id=validator.id,
        namespace_id=validator.namespace_id,
        name=validator.name,
        description=validator.description,
        required_fields=validator.required_fields,
        mode=validator.mode,
        code=validator.code,
        used_in_objects=object_counts.get(str(validator.id), 0),
    )


@router.post(
    "",
    response_model=ModelValidatorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new model validator",
    description="Create a new model validator definition.",
)
async def create_model_validator(
    data: ModelValidatorCreate,
    user: ProvisionedUser,
    db: DbSession,
) -> ModelValidatorResponse:
    """Create a new model validator.

    :param data: Validator creation data.
    :param user: Authenticated user.
    :param db: Database session.
    :returns: Created model validator response.
    """
    service = get_service(db)
    validator = await service.create_for_user(user.id, data)

    return ModelValidatorResponse(
        id=validator.id,
        namespace_id=validator.namespace_id,
        name=validator.name,
        description=validator.description,
        required_fields=validator.required_fields,
        mode=validator.mode,
        code=validator.code,
        used_in_objects=0,
    )


@router.put(
    "/{validator_id}",
    response_model=ModelValidatorResponse,
    summary="Update model validator",
    description="Update an existing model validator definition.",
)
async def update_model_validator(
    validator_id: str,
    data: ModelValidatorUpdate,
    user: ProvisionedUser,
    db: DbSession,
) -> ModelValidatorResponse:
    """Update a model validator.

    :param validator_id: Validator unique identifier.
    :param data: Validator update data.
    :param user: Authenticated user.
    :param db: Database session.
    :returns: Updated model validator response.
    :raises HTTPException: If validator not found.
    """
    service = get_service(db)
    validator = await service.get_by_id_for_user(validator_id, user.id)
    if not validator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model validator with ID '{validator_id}' not found",
        )

    if validator.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify validator in locked namespace",
        )

    updated = await service.update_validator(validator, data)
    object_counts = await service.get_object_counts_for_user(user.id)

    return ModelValidatorResponse(
        id=updated.id,
        namespace_id=updated.namespace_id,
        name=updated.name,
        description=updated.description,
        required_fields=updated.required_fields,
        mode=updated.mode,
        code=updated.code,
        used_in_objects=object_counts.get(str(updated.id), 0),
    )


@router.delete(
    "/{validator_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete model validator",
    description="Delete a model validator. Cannot delete if used in objects.",
)
async def delete_model_validator(
    validator_id: str,
    user: ProvisionedUser,
    db: DbSession,
) -> None:
    """Delete a model validator.

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
            detail=f"Model validator with ID '{validator_id}' not found",
        )

    if validator.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete validator in locked namespace",
        )

    await service.delete_validator(validator)
