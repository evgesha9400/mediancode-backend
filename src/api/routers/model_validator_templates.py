# src/api/routers/model_validator_templates.py
"""Router for Model Validator Template endpoints (read-only)."""

from fastapi import APIRouter

from api.deps import DbSession, ProvisionedUser
from api.models.database import ModelValidatorTemplateModel
from api.schemas.model_validator_template import ModelValidatorTemplateResponse
from api.services.catalog import CatalogService

router = APIRouter(
    prefix="/model-validator-templates", tags=["Model Validator Templates"]
)


@router.get(
    "",
    response_model=list[ModelValidatorTemplateResponse],
    summary="List all model validator templates",
    description="Retrieve all model validator template definitions.",
)
async def list_model_validator_templates(
    user: ProvisionedUser,
    db: DbSession,
) -> list[ModelValidatorTemplateResponse]:
    """List all model validator templates.

    :param user: Authenticated user.
    :param db: Database session.
    :returns: List of model validator template responses.
    """
    service = CatalogService(db, ModelValidatorTemplateModel)
    templates = await service.list_all()
    return [ModelValidatorTemplateResponse.model_validate(t) for t in templates]
