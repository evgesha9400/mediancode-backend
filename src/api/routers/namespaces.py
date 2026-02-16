# src/api/routers/namespaces.py
"""Router for Namespace endpoints."""

from fastapi import APIRouter, HTTPException, status

from api.deps import DbSession, ProvisionedUser
from api.schemas.namespace import NamespaceCreate, NamespaceResponse, NamespaceUpdate
from api.services.namespace import NamespaceService, get_namespace_service

router = APIRouter(prefix="/namespaces", tags=["Namespaces"])


def get_service(db: DbSession) -> NamespaceService:
    """Get namespace service instance.

    :param db: Database session.
    :returns: NamespaceService instance.
    """
    return get_namespace_service(db)


@router.get(
    "",
    response_model=list[NamespaceResponse],
    summary="List all namespaces",
    description="Retrieve all namespaces accessible to the authenticated user.",
)
async def list_namespaces(
    user_id: ProvisionedUser,
    db: DbSession,
) -> list[NamespaceResponse]:
    """List all namespaces accessible to the user.

    :param user_id: Authenticated user ID.
    :param db: Database session.
    :returns: List of namespace responses.
    """
    service = get_service(db)
    namespaces = await service.list_for_user(user_id)
    return [NamespaceResponse.model_validate(ns) for ns in namespaces]


@router.post(
    "",
    response_model=NamespaceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new namespace",
    description="Create a new namespace for organizing API entities.",
)
async def create_namespace(
    data: NamespaceCreate,
    user_id: ProvisionedUser,
    db: DbSession,
) -> NamespaceResponse:
    """Create a new namespace.

    :param data: Namespace creation data.
    :param user_id: Authenticated user ID.
    :param db: Database session.
    :returns: Created namespace response.
    """
    service = get_service(db)
    namespace = await service.create_for_user(user_id, data)
    return NamespaceResponse.model_validate(namespace)


@router.get(
    "/{namespace_id}",
    response_model=NamespaceResponse,
    summary="Get namespace by ID",
    description="Retrieve a specific namespace by its ID.",
)
async def get_namespace(
    namespace_id: str,
    user_id: ProvisionedUser,
    db: DbSession,
) -> NamespaceResponse:
    """Get a namespace by ID.

    :param namespace_id: Namespace unique identifier.
    :param user_id: Authenticated user ID.
    :param db: Database session.
    :returns: Namespace response.
    :raises HTTPException: If namespace not found.
    """
    service = get_service(db)
    namespace = await service.get_by_id_for_user(namespace_id, user_id)
    if not namespace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Namespace with ID '{namespace_id}' not found",
        )
    return NamespaceResponse.model_validate(namespace)


@router.put(
    "/{namespace_id}",
    response_model=NamespaceResponse,
    summary="Update namespace",
    description="Update an existing namespace. Locked namespaces cannot be modified.",
)
async def update_namespace(
    namespace_id: str,
    data: NamespaceUpdate,
    user_id: ProvisionedUser,
    db: DbSession,
) -> NamespaceResponse:
    """Update a namespace.

    :param namespace_id: Namespace unique identifier.
    :param data: Namespace update data.
    :param user_id: Authenticated user ID.
    :param db: Database session.
    :returns: Updated namespace response.
    :raises HTTPException: If namespace not found or locked.
    """
    service = get_service(db)
    namespace = await service.get_by_id_for_user(namespace_id, user_id)
    if not namespace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Namespace with ID '{namespace_id}' not found",
        )

    # Verify ownership (not global namespace)
    if namespace.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify locked namespace",
        )

    updated = await service.update_namespace(namespace, data)
    return NamespaceResponse.model_validate(updated)


@router.delete(
    "/{namespace_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete namespace",
    description="Delete a namespace. Only allowed if the namespace has no entities.",
)
async def delete_namespace(
    namespace_id: str,
    user_id: ProvisionedUser,
    db: DbSession,
) -> None:
    """Delete a namespace.

    :param namespace_id: Namespace unique identifier.
    :param user_id: Authenticated user ID.
    :param db: Database session.
    :raises HTTPException: If namespace not found, locked, or has entities.
    """
    service = get_service(db)
    namespace = await service.get_by_id_for_user(namespace_id, user_id)
    if not namespace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Namespace with ID '{namespace_id}' not found",
        )

    # Verify ownership (not global namespace)
    if namespace.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete locked namespace",
        )

    await service.delete_namespace(namespace)
