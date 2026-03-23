# src/api/schemas/relationship.py
"""Pydantic schemas for Object Relationship entity."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from api.schemas.literals import Cardinality


class ObjectRelationshipCreate(BaseModel):
    """Request schema for creating a relationship.

    :ivar target_object_id: Reference to the target object.
    :ivar name: Relationship name.
    :ivar cardinality: Relationship type.
    """

    target_object_id: UUID = Field(..., alias="targetObjectId")
    name: str
    cardinality: Cardinality

    model_config = ConfigDict(populate_by_name=True)


class ObjectRelationshipResponse(BaseModel):
    """Response schema for a relationship.

    :ivar id: Unique identifier.
    :ivar source_object_id: Source object reference.
    :ivar target_object_id: Target object reference.
    :ivar name: Relationship name.
    :ivar cardinality: Relationship type.
    :ivar is_inferred: Whether this is an auto-created inverse.
    :ivar inverse_id: Reference to the inverse relationship.
    :ivar fk_field_id: Reference to the auto-created FK field.
    """

    id: UUID
    source_object_id: UUID = Field(..., alias="sourceObjectId")
    target_object_id: UUID = Field(..., alias="targetObjectId")
    name: str
    cardinality: Cardinality
    is_inferred: bool = Field(default=False, alias="isInferred")
    inverse_id: UUID | None = Field(default=None, alias="inverseId")
    fk_field_id: UUID | None = Field(default=None, alias="fkFieldId")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class RelationshipMutationResponse(BaseModel):
    """Response for relationship create/delete -- includes all side effects.

    :ivar updated_objects: All objects whose fields or relationships changed.
    :ivar created_fields: Newly auto-created FK field entities.
    :ivar deleted_field_ids: IDs of FK fields that were deleted.
    """

    updated_objects: list["ObjectResponse"] = Field(
        default_factory=list, alias="updatedObjects"
    )
    created_fields: list["FieldResponse"] = Field(
        default_factory=list, alias="createdFields"
    )
    deleted_field_ids: list[UUID] = Field(default_factory=list, alias="deletedFieldIds")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
