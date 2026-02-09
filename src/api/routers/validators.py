# src/api/routers/validators.py
"""Router for Validator endpoints (read-only)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import CurrentUser
from api.database import get_db
from api.models.database import FieldModel, FieldValidator, ValidatorModel
from api.schemas.validator import FieldReferenceSchema, ValidatorResponse
from api.settings import get_settings

router = APIRouter(prefix="/validators", tags=["Validators"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_fields_by_validator(
    db: AsyncSession,
) -> dict[str, list[FieldReferenceSchema]]:
    """Get fields grouped by validator name.

    :param db: Database session.
    :returns: Dict mapping validator name to list of field references.
    """
    query = (
        select(FieldValidator.name, FieldModel.id, FieldModel.name)
        .join(FieldModel, FieldValidator.field_id == FieldModel.id)
    )
    result = await db.execute(query)

    fields_by_validator: dict[str, list[FieldReferenceSchema]] = {}
    for validator_name, field_id, field_name in result.fetchall():
        if validator_name not in fields_by_validator:
            fields_by_validator[validator_name] = []
        fields_by_validator[validator_name].append(
            FieldReferenceSchema(name=field_name, field_id=field_id)
        )

    return fields_by_validator


@router.get(
    "",
    response_model=list[ValidatorResponse],
    summary="List all validators",
    description="Retrieve all validator definitions including inline and custom validators.",
)
async def list_validators(
    user_id: CurrentUser,
    db: DbSession,
    namespace_id: str | None = None,
) -> list[ValidatorResponse]:
    """List all validators.

    :param user_id: Authenticated user ID.
    :param db: Database session.
    :param namespace_id: Optional namespace filter. If provided, returns validators
        from the specified namespace plus all global inline validators.
    :returns: List of validator responses.
    """
    # Query validators from database
    query = select(ValidatorModel)
    if namespace_id:
        settings = get_settings()
        query = query.where(
            or_(
                ValidatorModel.namespace_id == namespace_id,
                ValidatorModel.namespace_id == settings.global_namespace_id,
            )
        )

    result = await db.execute(query)
    validators = result.scalars().all()

    # Get fields using each validator
    fields_by_validator = await get_fields_by_validator(db)

    return [
        ValidatorResponse(
            id=v.id,
            namespace_id=v.namespace_id,
            name=v.name,
            type=v.type,
            description=v.description,
            category=v.category,
            parameter_type=v.parameter_type,
            example_usage=v.example_usage,
            pydantic_docs_url=v.pydantic_docs_url,
            used_in_fields=len(fields_by_validator.get(v.name, [])),
            fields_using_validator=fields_by_validator.get(v.name, []),
        )
        for v in validators
    ]
