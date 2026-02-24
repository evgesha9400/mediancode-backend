"""Router for Field Validator Template endpoints (read-only)."""

from fastapi import APIRouter

from api.deps import DbSession, ProvisionedUser
from api.schemas.field_validator_template import FieldValidatorTemplateResponse
from api.services.field_validator_template import (
    FieldValidatorTemplateService,
    get_field_validator_template_service,
)

router = APIRouter(
    prefix="/field-validator-templates", tags=["Field Validator Templates"]
)


def get_service(db: DbSession) -> FieldValidatorTemplateService:
    """Get field validator template service instance.

    :param db: Database session.
    :returns: FieldValidatorTemplateService instance.
    """
    return get_field_validator_template_service(db)


@router.get(
    "",
    response_model=list[FieldValidatorTemplateResponse],
    summary="List all field validator templates",
    description="Retrieve all field validator template definitions.",
)
async def list_field_validator_templates(
    user: ProvisionedUser,
    db: DbSession,
) -> list[FieldValidatorTemplateResponse]:
    """List all field validator templates.

    :param user: Authenticated user.
    :param db: Database session.
    :returns: List of field validator template responses.
    """
    service = get_service(db)
    templates = await service.list_all()
    return [FieldValidatorTemplateResponse.model_validate(t) for t in templates]
