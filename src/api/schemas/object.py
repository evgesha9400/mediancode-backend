# src/api/schemas/object.py
"""Pydantic schemas for Object entity."""

from pydantic import BaseModel, Field


class ObjectFieldReferenceSchema(BaseModel):
    """Schema for a field reference in an object.

    :ivar field_id: Reference to Field.id.
    :ivar required: Whether this field is required in the object.
    """

    field_id: str = Field(..., alias="fieldId", examples=["field-1"])
    required: bool = Field(..., examples=[True])

    class Config:
        """Pydantic model configuration."""

        populate_by_name = True


class ObjectCreate(BaseModel):
    """Request schema for creating an object.

    :ivar namespace_id: Namespace this object belongs to.
    :ivar name: Object name.
    :ivar description: Object description.
    :ivar fields: List of field references.
    """

    namespace_id: str = Field(..., alias="namespaceId", examples=["namespace-user"])
    name: str = Field(..., examples=["User"])
    description: str | None = Field(default=None, examples=["User object definition"])
    fields: list[ObjectFieldReferenceSchema] = Field(...)


class ObjectUpdate(BaseModel):
    """Request schema for updating an object.

    :ivar name: Updated object name.
    :ivar description: Updated description.
    :ivar fields: Updated list of field references.
    """

    name: str | None = Field(default=None, examples=["UpdatedObjectName"])
    description: str | None = Field(default=None, examples=["Updated description"])
    fields: list[ObjectFieldReferenceSchema] | None = Field(default=None)


class ObjectResponse(BaseModel):
    """Response schema for object data.

    :ivar id: Unique identifier for the object.
    :ivar namespace_id: Namespace this object belongs to.
    :ivar name: Object name.
    :ivar description: Object description.
    :ivar fields: List of field references.
    :ivar used_in_apis: Array of endpoint IDs that use this object.
    """

    id: str = Field(..., examples=["object-1"])
    namespace_id: str = Field(..., alias="namespaceId", examples=["namespace-global"])
    name: str = Field(..., examples=["User"])
    description: str | None = Field(default=None, examples=["User account object"])
    fields: list[ObjectFieldReferenceSchema] = Field(default_factory=list)
    used_in_apis: list[str] = Field(
        default_factory=list,
        alias="usedInApis",
        examples=[["endpoint-1", "endpoint-2"]],
    )

    class Config:
        """Pydantic model configuration."""

        from_attributes = True
        populate_by_name = True
