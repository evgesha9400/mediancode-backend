# src/api/schemas/field.py
"""Pydantic schemas for Field entity."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FieldCreate(BaseModel):
    """Request schema for creating a field.

    :ivar namespace_id: Namespace this field belongs to.
    :ivar name: Field name.
    :ivar type_id: Reference to the type definition UUID.
    :ivar description: Field description.
    :ivar default_value: Default value expression.
    """

    namespace_id: UUID = Field(
        ..., alias="namespaceId", examples=["00000000-0000-0000-0000-000000000002"]
    )
    name: str = Field(..., examples=["email"])
    type_id: UUID = Field(
        ..., alias="typeId", examples=["00000000-0000-0000-0001-000000000001"]
    )
    description: str | None = Field(default=None, examples=["User email address"])
    default_value: str | None = Field(default=None, alias="defaultValue", examples=[""])


class FieldUpdate(BaseModel):
    """Request schema for updating a field.

    :ivar name: Updated field name.
    :ivar description: Updated description.
    :ivar default_value: Updated default value.
    """

    name: str | None = Field(default=None, examples=["updated_field_name"])
    description: str | None = Field(default=None, examples=["Updated description"])
    default_value: str | None = Field(
        default=None, alias="defaultValue", examples=["new_default"]
    )


class FieldResponse(BaseModel):
    """Response schema for field data.

    :ivar id: Unique identifier for the field.
    :ivar namespace_id: Namespace this field belongs to.
    :ivar name: Field name.
    :ivar type_id: Reference to the type definition UUID.
    :ivar description: Field description.
    :ivar default_value: Default value expression.
    :ivar used_in_apis: Array of endpoint IDs where this field is used.
    """

    id: UUID = Field(..., examples=["00000000-0000-0000-0003-000000000001"])
    namespace_id: UUID = Field(
        ..., alias="namespaceId", examples=["00000000-0000-0000-0000-000000000001"]
    )
    name: str = Field(..., examples=["email"])
    type_id: UUID = Field(
        ..., alias="typeId", examples=["00000000-0000-0000-0001-000000000001"]
    )
    description: str | None = Field(default=None, examples=["User email address"])
    default_value: str | None = Field(default=None, alias="defaultValue", examples=[""])
    used_in_apis: list[UUID] = Field(
        default_factory=list,
        alias="usedInApis",
        examples=[["00000000-0000-0000-0004-000000000001"]],
    )

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
