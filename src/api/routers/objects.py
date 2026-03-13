# src/api/routers/objects.py
"""Router for Object endpoints."""

from fastapi import APIRouter, HTTPException, status

from api.deps import DbSession, ProvisionedUser
from api.schemas.object import (
    ModelValidatorResponse,
    ObjectCreate,
    ObjectFieldReferenceSchema,
    ObjectResponse,
    ObjectUpdate,
)
from api.schemas.relationship import (
    ObjectRelationshipCreate,
    ObjectRelationshipResponse,
)
from api.services.object import ObjectService, get_object_service
from api.services.relationship import RelationshipService, get_relationship_service

router = APIRouter(prefix="/objects", tags=["Objects"])


def get_service(db: DbSession) -> ObjectService:
    """Get object service instance.

    :param db: Database session.
    :returns: ObjectService instance.
    """
    return get_object_service(db)


async def _to_response(obj, service: ObjectService) -> ObjectResponse:
    """Convert an object model to response schema.

    :param obj: Object database model.
    :param service: ObjectService for fetching usage.
    :returns: ObjectResponse schema.
    """
    fields = [
        ObjectFieldReferenceSchema(
            field_id=fa.field_id,
            optional=fa.optional,
            is_pk=fa.is_pk,
            appears=fa.appears,
        )
        for fa in sorted(obj.field_associations, key=lambda x: x.position)
    ]
    validators = [
        ModelValidatorResponse(
            id=v.id,
            template_id=v.template_id,
            parameters=v.parameters,
            field_mappings=v.field_mappings,
        )
        for v in sorted(obj.validators, key=lambda x: x.position)
    ]
    relationships = [
        ObjectRelationshipResponse(
            id=r.id,
            source_object_id=r.source_object_id,
            target_object_id=r.target_object_id,
            name=r.name,
            cardinality=r.cardinality,
            is_inferred=r.is_inferred,
            inverse_id=r.inverse_id,
        )
        for r in sorted(obj.relationships, key=lambda x: x.position)
    ]
    used_in_apis = await service.get_used_in_apis(obj.id)
    return ObjectResponse(
        id=obj.id,
        namespace_id=obj.namespace_id,
        name=obj.name,
        description=obj.description,
        fields=fields,
        used_in_apis=used_in_apis,
        validators=validators,
        relationships=relationships,
    )


@router.get(
    "",
    response_model=list[ObjectResponse],
    summary="List all objects",
    description="Retrieve all object definitions accessible to the authenticated user.",
)
async def list_objects(
    user: ProvisionedUser,
    db: DbSession,
    namespace_id: str | None = None,
) -> list[ObjectResponse]:
    """List all objects accessible to the user.

    :param user: Authenticated user.
    :param db: Database session.
    :param namespace_id: Optional namespace filter.
    :returns: List of object responses.
    """
    service = get_service(db)
    objects = await service.list_for_user(user.id, namespace_id)
    return [await _to_response(obj, service) for obj in objects]


@router.post(
    "",
    response_model=ObjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new object",
    description="Create a new object definition.",
)
async def create_object(
    data: ObjectCreate,
    user: ProvisionedUser,
    db: DbSession,
) -> ObjectResponse:
    """Create a new object.

    :param data: Object creation data.
    :param user: Authenticated user.
    :param db: Database session.
    :returns: Created object response.
    """
    service = get_service(db)
    obj = await service.create_for_user(user.id, data)
    # Reload with field associations
    obj = await service.get_by_id_for_user(obj.id, user.id)
    return await _to_response(obj, service)


@router.get(
    "/{object_id}",
    response_model=ObjectResponse,
    summary="Get object by ID",
    description="Retrieve a specific object by its ID.",
)
async def get_object(
    object_id: str,
    user: ProvisionedUser,
    db: DbSession,
) -> ObjectResponse:
    """Get an object by ID.

    :param object_id: Object unique identifier.
    :param user: Authenticated user.
    :param db: Database session.
    :returns: Object response.
    :raises HTTPException: If object not found.
    """
    service = get_service(db)
    obj = await service.get_by_id_for_user(object_id, user.id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Object with ID '{object_id}' not found",
        )
    return await _to_response(obj, service)


@router.put(
    "/{object_id}",
    response_model=ObjectResponse,
    summary="Update object",
    description="Update an existing object definition.",
)
async def update_object(
    object_id: str,
    data: ObjectUpdate,
    user: ProvisionedUser,
    db: DbSession,
) -> ObjectResponse:
    """Update an object.

    :param object_id: Object unique identifier.
    :param data: Object update data.
    :param user: Authenticated user.
    :param db: Database session.
    :returns: Updated object response.
    :raises HTTPException: If object not found.
    """
    service = get_service(db)
    obj = await service.get_by_id_for_user(object_id, user.id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Object with ID '{object_id}' not found",
        )

    # Verify ownership
    if obj.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify this object",
        )

    updated = await service.update_object(obj, data)
    # Reload with field associations
    updated = await service.get_by_id_for_user(updated.id, user.id)
    return await _to_response(updated, service)


@router.delete(
    "/{object_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete object",
    description="Delete an object. Cannot delete if used in endpoints.",
)
async def delete_object(
    object_id: str,
    user: ProvisionedUser,
    db: DbSession,
) -> None:
    """Delete an object.

    :param object_id: Object unique identifier.
    :param user: Authenticated user.
    :param db: Database session.
    :raises HTTPException: If object not found or in use.
    """
    service = get_service(db)
    obj = await service.get_by_id_for_user(object_id, user.id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Object with ID '{object_id}' not found",
        )

    # Verify ownership
    if obj.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete this object",
        )

    await service.delete_object(obj)


@router.post(
    "/{object_id}/relationships",
    response_model=ObjectRelationshipResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a relationship",
    description="Create a relationship from this object to a target object. Auto-creates the inverse.",
)
async def create_relationship(
    object_id: str,
    data: ObjectRelationshipCreate,
    user: ProvisionedUser,
    db: DbSession,
) -> ObjectRelationshipResponse:
    """Create a relationship on an object.

    :param object_id: Source object ID.
    :param data: Relationship creation data.
    :param user: Authenticated user.
    :param db: Database session.
    :returns: Created relationship response.
    :raises HTTPException: If object not found.
    """
    obj_service = get_service(db)
    obj = await obj_service.get_by_id_for_user(object_id, user.id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Object with ID '{object_id}' not found",
        )

    rel_service = get_relationship_service(db)
    rel = await rel_service.create_relationship(obj.id, data)
    return ObjectRelationshipResponse(
        id=rel.id,
        source_object_id=rel.source_object_id,
        target_object_id=rel.target_object_id,
        name=rel.name,
        cardinality=rel.cardinality,
        is_inferred=rel.is_inferred,
        inverse_id=rel.inverse_id,
    )


@router.delete(
    "/{object_id}/relationships/{relationship_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a relationship",
    description="Delete a relationship and its auto-created inverse.",
)
async def delete_relationship(
    object_id: str,
    relationship_id: str,
    user: ProvisionedUser,
    db: DbSession,
) -> None:
    """Delete a relationship and its inverse.

    :param object_id: Object ID (for URL structure).
    :param relationship_id: Relationship ID.
    :param user: Authenticated user.
    :param db: Database session.
    :raises HTTPException: If object or relationship not found.
    """
    obj_service = get_service(db)
    obj = await obj_service.get_by_id_for_user(object_id, user.id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Object with ID '{object_id}' not found",
        )

    rel_service = get_relationship_service(db)
    await rel_service.delete_relationship(relationship_id)
