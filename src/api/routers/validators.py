# src/api/routers/validators.py
"""Router for Validator endpoints (read-only)."""

from fastapi import APIRouter

from api.auth import CurrentUser
from api.data import get_global_validators
from api.schemas.validator import ValidatorResponse
from api.settings import get_settings

router = APIRouter(prefix="/validators", tags=["Validators"])


@router.get(
    "",
    response_model=list[ValidatorResponse],
    summary="List all validators",
    description="Retrieve all validator definitions including inline and custom validators.",
)
async def list_validators(
    user_id: CurrentUser,
    namespace_id: str | None = None,
) -> list[ValidatorResponse]:
    """List all validators.

    :param user_id: Authenticated user ID.
    :param namespace_id: Optional namespace filter.
    :returns: List of validator responses.
    """
    settings = get_settings()
    validators = get_global_validators()

    # Filter by namespace if provided
    if namespace_id and namespace_id != settings.global_namespace_id:
        # Only global validators exist for now
        return []

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
        )
        for v in validators
    ]
