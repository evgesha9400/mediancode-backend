# src/api/routers/endpoints.py
"""Router for Endpoint endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import CurrentUser
from api.database import get_db
from api.schemas.endpoint import (
    ApiEndpointCreate,
    ApiEndpointResponse,
    ApiEndpointUpdate,
    EndpointParameterSchema,
)
from api.services.endpoint import EndpointService, get_endpoint_service

router = APIRouter(prefix="/endpoints", tags=["Endpoints"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


def get_service(db: DbSession) -> EndpointService:
    """Get endpoint service instance.

    :param db: Database session.
    :returns: EndpointService instance.
    """
    return get_endpoint_service(db)


def _to_response(endpoint) -> ApiEndpointResponse:
    """Convert an endpoint model to response schema.

    :param endpoint: Endpoint database model.
    :returns: ApiEndpointResponse schema.
    """
    path_params = [
        EndpointParameterSchema(
            id=p.id,
            name=p.name,
            type=p.type,
            description=p.description,
            required=p.required,
        )
        for p in sorted(endpoint.path_params, key=lambda x: x.position)
    ]
    return ApiEndpointResponse(
        id=endpoint.id,
        namespace_id=endpoint.namespace_id,
        api_id=endpoint.api_id,
        method=endpoint.method,
        path=endpoint.path,
        description=endpoint.description,
        tag_id=endpoint.tag_id,
        path_params=path_params,
        query_params_object_id=endpoint.query_params_object_id,
        request_body_object_id=endpoint.request_body_object_id,
        response_body_object_id=endpoint.response_body_object_id,
        use_envelope=endpoint.use_envelope,
        response_shape=endpoint.response_shape,
    )


@router.get(
    "",
    response_model=list[ApiEndpointResponse],
    summary="List all endpoints",
    description="Retrieve all API endpoint definitions accessible to the authenticated user.",
)
async def list_endpoints(
    user_id: CurrentUser,
    db: DbSession,
    namespace_id: str | None = None,
) -> list[ApiEndpointResponse]:
    """List all endpoints accessible to the user.

    :param user_id: Authenticated user ID.
    :param db: Database session.
    :param namespace_id: Optional namespace filter.
    :returns: List of endpoint responses.
    """
    service = get_service(db)
    endpoints = await service.list_for_user(user_id, namespace_id)
    return [_to_response(ep) for ep in endpoints]


@router.post(
    "",
    response_model=ApiEndpointResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new endpoint",
    description="Create a new API endpoint definition.",
)
async def create_endpoint(
    data: ApiEndpointCreate,
    user_id: CurrentUser,
    db: DbSession,
) -> ApiEndpointResponse:
    """Create a new endpoint.

    :param data: Endpoint creation data.
    :param user_id: Authenticated user ID.
    :param db: Database session.
    :returns: Created endpoint response.
    """
    service = get_service(db)
    endpoint = await service.create_for_user(user_id, data)
    # Reload with path params
    endpoint = await service.get_by_id_for_user(endpoint.id, user_id)
    return _to_response(endpoint)


@router.get(
    "/{endpoint_id}",
    response_model=ApiEndpointResponse,
    summary="Get endpoint by ID",
    description="Retrieve a specific API endpoint by its ID.",
)
async def get_endpoint(
    endpoint_id: str,
    user_id: CurrentUser,
    db: DbSession,
) -> ApiEndpointResponse:
    """Get an endpoint by ID.

    :param endpoint_id: Endpoint unique identifier.
    :param user_id: Authenticated user ID.
    :param db: Database session.
    :returns: Endpoint response.
    :raises HTTPException: If endpoint not found.
    """
    service = get_service(db)
    endpoint = await service.get_by_id_for_user(endpoint_id, user_id)
    if not endpoint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Endpoint with ID '{endpoint_id}' not found",
        )
    return _to_response(endpoint)


@router.put(
    "/{endpoint_id}",
    response_model=ApiEndpointResponse,
    summary="Update endpoint",
    description="Update an existing API endpoint definition.",
)
async def update_endpoint(
    endpoint_id: str,
    data: ApiEndpointUpdate,
    user_id: CurrentUser,
    db: DbSession,
) -> ApiEndpointResponse:
    """Update an endpoint.

    :param endpoint_id: Endpoint unique identifier.
    :param data: Endpoint update data.
    :param user_id: Authenticated user ID.
    :param db: Database session.
    :returns: Updated endpoint response.
    :raises HTTPException: If endpoint not found.
    """
    service = get_service(db)
    endpoint = await service.get_by_id_for_user(endpoint_id, user_id)
    if not endpoint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Endpoint with ID '{endpoint_id}' not found",
        )

    # Verify ownership
    if endpoint.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify endpoint in locked namespace",
        )

    updated = await service.update_endpoint(endpoint, data)
    # Reload with path params
    updated = await service.get_by_id_for_user(updated.id, user_id)
    return _to_response(updated)


@router.delete(
    "/{endpoint_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete endpoint",
    description="Delete an API endpoint definition.",
)
async def delete_endpoint(
    endpoint_id: str,
    user_id: CurrentUser,
    db: DbSession,
) -> None:
    """Delete an endpoint.

    :param endpoint_id: Endpoint unique identifier.
    :param user_id: Authenticated user ID.
    :param db: Database session.
    :raises HTTPException: If endpoint not found.
    """
    service = get_service(db)
    endpoint = await service.get_by_id_for_user(endpoint_id, user_id)
    if not endpoint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Endpoint with ID '{endpoint_id}' not found",
        )

    # Verify ownership
    if endpoint.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete endpoint in locked namespace",
        )

    await service.delete_endpoint(endpoint)
