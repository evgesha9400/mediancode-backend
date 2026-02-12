# src/api/routers/apis.py
"""Router for API endpoints."""

import io
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import CurrentUser
from api.database import get_db
from api.rate_limit import (
    RATE_LIMIT_DEFAULT,
    RATE_LIMIT_GENERATION,
    limiter,
)
from api.schemas.api import ApiCreate, ApiResponse, ApiUpdate
from api.services.api import ApiService, get_api_service

router = APIRouter(prefix="/apis", tags=["APIs"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


def get_service(db: DbSession) -> ApiService:
    """Get API service instance.

    :param db: Database session.
    :returns: ApiService instance.
    """
    return get_api_service(db)


@router.get(
    "",
    response_model=list[ApiResponse],
    summary="List all APIs",
    description="Retrieve all API definitions accessible to the authenticated user.",
)
@limiter.limit(RATE_LIMIT_DEFAULT)
async def list_apis(
    request: Request,
    user_id: CurrentUser,
    db: DbSession,
    namespace_id: str | None = None,
) -> list[ApiResponse]:
    """List all APIs accessible to the user.

    :param user_id: Authenticated user ID.
    :param db: Database session.
    :param namespace_id: Optional namespace filter.
    :returns: List of API responses.
    """
    service = get_service(db)
    apis = await service.list_for_user(user_id, namespace_id)
    return [ApiResponse.model_validate(api) for api in apis]


@router.post(
    "",
    response_model=ApiResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new API",
    description="Create a new API definition.",
)
@limiter.limit(RATE_LIMIT_DEFAULT)
async def create_api(
    request: Request,
    data: ApiCreate,
    user_id: CurrentUser,
    db: DbSession,
) -> ApiResponse:
    """Create a new API.

    :param data: API creation data.
    :param user_id: Authenticated user ID.
    :param db: Database session.
    :returns: Created API response.
    """
    service = get_service(db)
    api = await service.create_for_user(user_id, data)
    return ApiResponse.model_validate(api)


@router.get(
    "/{api_id}",
    response_model=ApiResponse,
    summary="Get API by ID",
    description="Retrieve a specific API definition by its ID.",
)
async def get_api(
    api_id: str,
    user_id: CurrentUser,
    db: DbSession,
) -> ApiResponse:
    """Get an API by ID.

    :param api_id: API unique identifier.
    :param user_id: Authenticated user ID.
    :param db: Database session.
    :returns: API response.
    :raises HTTPException: If API not found.
    """
    service = get_service(db)
    api = await service.get_by_id_for_user(api_id, user_id)
    if not api:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API with ID '{api_id}' not found",
        )
    return ApiResponse.model_validate(api)


@router.put(
    "/{api_id}",
    response_model=ApiResponse,
    summary="Update API",
    description="Update an existing API definition.",
)
async def update_api(
    api_id: str,
    data: ApiUpdate,
    user_id: CurrentUser,
    db: DbSession,
) -> ApiResponse:
    """Update an API.

    :param api_id: API unique identifier.
    :param data: API update data.
    :param user_id: Authenticated user ID.
    :param db: Database session.
    :returns: Updated API response.
    :raises HTTPException: If API not found.
    """
    service = get_service(db)
    api = await service.get_by_id_for_user(api_id, user_id)
    if not api:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API with ID '{api_id}' not found",
        )

    # Verify ownership
    if api.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify API in locked namespace",
        )

    updated = await service.update_api(api, data)
    return ApiResponse.model_validate(updated)


@router.delete(
    "/{api_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete API",
    description="Delete an API definition. This cascades to endpoints and tags.",
)
async def delete_api(
    api_id: str,
    user_id: CurrentUser,
    db: DbSession,
) -> None:
    """Delete an API.

    :param api_id: API unique identifier.
    :param user_id: Authenticated user ID.
    :param db: Database session.
    :raises HTTPException: If API not found.
    """
    service = get_service(db)
    api = await service.get_by_id_for_user(api_id, user_id)
    if not api:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API with ID '{api_id}' not found",
        )

    # Verify ownership
    if api.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete API in locked namespace",
        )

    await service.delete_api(api)


@router.post(
    "/{api_id}/generate",
    summary="Generate FastAPI application",
    description="Generates a complete FastAPI application for the specified API.",
    responses={
        200: {
            "description": "Successfully generated FastAPI application",
            "content": {
                "application/zip": {"schema": {"type": "string", "format": "binary"}}
            },
        }
    },
)
@limiter.limit(RATE_LIMIT_GENERATION)
async def generate_api_code(
    request: Request,
    api_id: str,
    user_id: CurrentUser,
    db: DbSession,
) -> StreamingResponse:
    """Generate FastAPI application code for an API.

    :param api_id: API unique identifier.
    :param user_id: Authenticated user ID.
    :param db: Database session.
    :returns: Streaming response with ZIP file.
    :raises HTTPException: If API not found.
    """
    # Import here to avoid circular imports
    from api.services.generation import generate_api_zip

    service = get_service(db)
    api = await service.get_with_relations(api_id, user_id)
    if not api:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API with ID '{api_id}' not found",
        )

    # Generate the ZIP file
    zip_buffer = await generate_api_zip(api, db)

    # Return as streaming response
    return StreamingResponse(
        io.BytesIO(zip_buffer.getvalue()),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{api.title.lower().replace(" ", "-")}-api.zip"'
        },
    )
