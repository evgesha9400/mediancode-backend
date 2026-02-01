# src/api/routers/validators.py
"""Router for Validator endpoints (read-only)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import CurrentUser
from api.data import get_global_validators
from api.database import get_db
from api.models.database import FieldModel, FieldValidator
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
    :param namespace_id: Optional namespace filter.
    :returns: List of validator responses.
    """
    settings = get_settings()
    validators = get_global_validators()

    # Filter by namespace if provided
    if namespace_id and namespace_id != settings.global_namespace_id:
        # Only global validators exist for now
        return []

    fields_by_validator = await get_fields_by_validator(db)

    return [
        ValidatorResponse(
            name=v["name"],
            namespace_id=v["namespaceId"],
            type=v["type"],
            description=v["description"],
            category=v["category"],
            parameter_type=v["parameterType"],
            example_usage=v["exampleUsage"],
            pydantic_docs_url=v["pydanticDocsUrl"],
            used_in_fields=len(fields_by_validator.get(v["name"], [])),
            fields_using_validator=fields_by_validator.get(v["name"], []),
        )
        for v in validators
    ]
