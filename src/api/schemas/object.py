# src/api/schemas/object.py
"""Pydantic schemas for Object entity."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from pydantic import Field as PydanticField

from api.schemas.literals import FieldExposure
from api.schemas.relationship import ObjectRelationshipResponse
from api_craft.models.types import PascalCaseName


class FieldDefaultLiteralSchema(BaseModel):
    """API schema for a literal default value.

    :ivar kind: Discriminator tag, always 'literal'.
    :ivar value: The literal default value as a string.
    """

    kind: Literal["literal"]
    value: str


class FieldDefaultGeneratedSchema(BaseModel):
    """API schema for a generated default value.

    :ivar kind: Discriminator tag, always 'generated'.
    :ivar strategy: The generation strategy to apply.
    """

    kind: Literal["generated"]
    strategy: Literal["uuid4", "now", "now_on_update", "auto_increment"]


FieldDefaultSchema = Annotated[
    FieldDefaultLiteralSchema | FieldDefaultGeneratedSchema,
    PydanticField(discriminator="kind"),
]


class ObjectFieldReferenceSchema(BaseModel):
    """Schema for a field reference in an object.

    :ivar field_id: Reference to Field.id.
    :ivar is_pk: Whether this field is the primary key.
    :ivar exposure: Where this field appears: read_write, write_only, or read_only.
    :ivar nullable: Whether this field is nullable in the object.
    :ivar default: Optional default value (literal or generated strategy).
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    field_id: UUID = Field(
        ..., alias="fieldId", examples=["00000000-0000-0000-0003-000000000001"]
    )
    is_pk: bool = Field(default=False, alias="isPk", examples=[False])
    exposure: FieldExposure = Field(default="read_write")
    nullable: bool = Field(default=False)
    default: FieldDefaultSchema | None = Field(default=None)


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
    :ivar used_in_apis: Array of API IDs that use this object.
    :ivar validators: Model validators attached to this object.
    :ivar relationships: Object relationships.
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
    relationships: list[ObjectRelationshipResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
