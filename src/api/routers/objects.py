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
    RelationshipMutationResponse,
)
from api.models.database import FieldModel, ObjectRelationship
from api.schemas.field import FieldResponse
from api.services.object import ObjectService, get_object_service
from api.services.relationship import RelationshipService, get_relationship_service

# Resolve forward references now that all schemas are imported.
RelationshipMutationResponse.model_rebuild()

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
            role=fa.role,
            optional=fa.nullable,
            default_value=fa.default_value,
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
            fk_field_id=r.fk_field_id,
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


def _field_to_response(field: FieldModel) -> FieldResponse:
    """Convert a field model to response schema (no associations).

    :param field: Field database model.
    :returns: FieldResponse schema.
    """
    return FieldResponse(
        id=field.id,
        namespace_id=field.namespace_id,
        name=field.name,
        type_id=field.type_id,
        description=field.description,
        default_value=field.default_value,
        used_in_apis=[],
        constraints=[],
        validators=[],
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
    response_model=RelationshipMutationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a relationship",
    description="Create a relationship from this object to a target object. Auto-creates the inverse.",
)
async def create_relationship(
    object_id: str,
    data: ObjectRelationshipCreate,
    user: ProvisionedUser,
    db: DbSession,
) -> RelationshipMutationResponse:
    """Create a relationship on an object.

    :param object_id: Source object ID.
    :param data: Relationship creation data.
    :param user: Authenticated user.
    :param db: Database session.
    :returns: Graph mutation response with updated objects and created fields.
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

    # Re-fetch both objects with fresh field/relationship data
    source_obj = await obj_service.get_by_id_for_user(str(obj.id), user.id)
    target_obj = await obj_service.get_by_id_for_user(
        str(data.target_object_id), user.id
    )

    updated_objects = []
    if source_obj:
        updated_objects.append(await _to_response(source_obj, obj_service))
    if target_obj:
        updated_objects.append(await _to_response(target_obj, obj_service))

    # Collect created FK fields
    created_fields: list[FieldResponse] = []
    if rel.fk_field_id:
        fk_field = await db.get(FieldModel, rel.fk_field_id)
        if fk_field:
            created_fields.append(_field_to_response(fk_field))
    if rel.inverse_id:
        inverse = await db.get(ObjectRelationship, rel.inverse_id)
        if inverse and inverse.fk_field_id:
            fk_field = await db.get(FieldModel, inverse.fk_field_id)
            if fk_field:
                created_fields.append(_field_to_response(fk_field))

    return RelationshipMutationResponse(
        updated_objects=updated_objects,
        created_fields=created_fields,
        deleted_field_ids=[],
    )


@router.delete(
    "/{object_id}/relationships/{relationship_id}",
    response_model=RelationshipMutationResponse,
    summary="Delete a relationship",
    description="Delete a relationship and its auto-created inverse.",
)
async def delete_relationship(
    object_id: str,
    relationship_id: str,
    user: ProvisionedUser,
    db: DbSession,
) -> RelationshipMutationResponse:
    """Delete a relationship and its inverse.

    :param object_id: Object ID (for URL structure).
    :param relationship_id: Relationship ID.
    :param user: Authenticated user.
    :param db: Database session.
    :returns: Graph mutation response with updated objects and deleted field IDs.
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
    rel = await rel_service.get_by_id(relationship_id)
    if not rel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relationship not found",
        )

    # Capture side-effect data before deletion
    target_object_id = rel.target_object_id
    deleted_field_ids = []
    if rel.fk_field_id:
        deleted_field_ids.append(rel.fk_field_id)
    if rel.inverse_id:
        inverse = await rel_service.get_by_id(rel.inverse_id)
        if inverse and inverse.fk_field_id:
            deleted_field_ids.append(inverse.fk_field_id)

    await rel_service.delete_relationship(relationship_id)

    # Re-fetch both objects with fresh data
    source_obj = await obj_service.get_by_id_for_user(object_id, user.id)
    target_obj = await obj_service.get_by_id_for_user(
        str(target_object_id), user.id
    )

    updated_objects = []
    if source_obj:
        updated_objects.append(await _to_response(source_obj, obj_service))
    if target_obj:
        updated_objects.append(await _to_response(target_obj, obj_service))

    return RelationshipMutationResponse(
        updated_objects=updated_objects,
        created_fields=[],
        deleted_field_ids=deleted_field_ids,
    )
