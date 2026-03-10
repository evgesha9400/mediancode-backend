# src/api/schemas/object.py
"""Pydantic schemas for Object entity."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from api_craft.models.types import PascalCaseName


class ObjectFieldReferenceSchema(BaseModel):
    """Schema for a field reference in an object.

    :ivar field_id: Reference to Field.id.
    :ivar optional: Whether this field is optional in the object.
    """

    field_id: UUID = Field(
        ..., alias="fieldId", examples=["00000000-0000-0000-0003-000000000001"]
    )
    optional: bool = Field(default=False, examples=[False])
    is_pk: bool = Field(default=False, alias="isPk", examples=[False])

    model_config = ConfigDict(populate_by_name=True)


class ModelValidatorInput(BaseModel):
    """Request schema for attaching a model validator template to an object.

    :ivar template_id: Reference to the model validator template.
    :ivar parameters: Template parameter values.
    :ivar field_mappings: Maps template field mapping keys to actual field names.
    """

    template_id: UUID = Field(..., alias="templateId")
    parameters: dict[str, str] | None = Field(default=None)
    field_mappings: dict[str, str] = Field(..., alias="fieldMappings")

    model_config = ConfigDict(populate_by_name=True)


class ModelValidatorResponse(BaseModel):
    """Response schema for an applied model validator.

    :ivar id: Unique identifier for the applied validator.
    :ivar template_id: Reference to the template.
    :ivar parameters: Template parameter values.
    :ivar field_mappings: Resolved field name mappings.
    """

    id: UUID
    template_id: UUID = Field(..., alias="templateId")
    parameters: dict[str, str] | None = Field(default=None)
    field_mappings: dict[str, str] = Field(..., alias="fieldMappings")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ObjectCreate(BaseModel):
    """Request schema for creating an object.

    :ivar namespace_id: Namespace this object belongs to.
    :ivar name: Object name.
    :ivar description: Object description.
    :ivar fields: List of field references.
    :ivar validators: Inline model validator definitions for this object.
    """

    namespace_id: UUID = Field(
        ..., alias="namespaceId", examples=["00000000-0000-0000-0000-000000000002"]
    )
    name: PascalCaseName = Field(..., examples=["User"])
    description: str | None = Field(default=None, examples=["User object definition"])
    fields: list[ObjectFieldReferenceSchema] = Field(...)
    validators: list[ModelValidatorInput] = Field(default_factory=list)


class ObjectUpdate(BaseModel):
    """Request schema for updating an object.

    :ivar name: Updated object name.
    :ivar description: Updated description.
    :ivar fields: Updated list of field references (None = don't touch).
    :ivar validators: Updated validators (None = don't touch, [] = clear all).
    """

    name: PascalCaseName | None = Field(default=None, examples=["UpdatedObjectName"])
    description: str | None = Field(default=None, examples=["Updated description"])
    fields: list[ObjectFieldReferenceSchema] | None = Field(default=None)
    validators: list[ModelValidatorInput] | None = Field(default=None)


class ObjectResponse(BaseModel):
    """Response schema for object data.

    :ivar id: Unique identifier for the object.
    :ivar namespace_id: Namespace this object belongs to.
    :ivar name: Object name.
    :ivar description: Object description.
    :ivar fields: List of field references.
    :ivar used_in_apis: Array of endpoint IDs that use this object.
    :ivar validators: Model validators attached to this object.
    """

    id: UUID = Field(..., examples=["00000000-0000-0000-0007-000000000001"])
    namespace_id: UUID = Field(
        ..., alias="namespaceId", examples=["00000000-0000-0000-0000-000000000001"]
    )
    name: str = Field(..., examples=["User"])
    description: str | None = Field(default=None, examples=["User account object"])
    fields: list[ObjectFieldReferenceSchema] = Field(default_factory=list)
    used_in_apis: list[UUID] = Field(
        default_factory=list,
        alias="usedInApis",
        examples=[["00000000-0000-0000-0004-000000000001"]],
    )
    validators: list[ModelValidatorResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
