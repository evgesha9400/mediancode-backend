# src/api/schemas/field.py
"""Pydantic schemas for Field entity."""

from typing import Any

from pydantic import BaseModel, Field


class FieldValidatorSchema(BaseModel):
    """Schema for a validator applied to a field.

    :ivar name: Validator name (references ValidatorBase.name).
    :ivar params: Validator parameters.
    """

    name: str = Field(..., examples=["max_length"])
    params: dict[str, Any] | None = Field(default=None, examples=[{"value": 255}])


class FieldCreate(BaseModel):
    """Request schema for creating a field.

    :ivar namespace_id: Namespace this field belongs to.
    :ivar name: Field name.
    :ivar type: Primitive type name.
    :ivar description: Field description.
    :ivar default_value: Default value expression.
    :ivar validators: List of validators to apply.
    """

    namespace_id: str = Field(..., alias="namespaceId", examples=["namespace-user"])
    name: str = Field(..., examples=["email"])
    type: str = Field(..., examples=["str"])
    description: str | None = Field(default=None, examples=["User email address"])
    default_value: str | None = Field(default=None, alias="defaultValue", examples=[""])
    validators: list[FieldValidatorSchema] | None = Field(default=None)


class FieldUpdate(BaseModel):
    """Request schema for updating a field.

    :ivar name: Updated field name.
    :ivar description: Updated description.
    :ivar default_value: Updated default value.
    :ivar validators: Updated list of validators.
    """

    name: str | None = Field(default=None, examples=["updated_field_name"])
    description: str | None = Field(default=None, examples=["Updated description"])
    default_value: str | None = Field(
        default=None, alias="defaultValue", examples=["new_default"]
    )
    validators: list[FieldValidatorSchema] | None = Field(default=None)


class FieldResponse(BaseModel):
    """Response schema for field data.

    :ivar id: Unique identifier for the field.
    :ivar namespace_id: Namespace this field belongs to.
    :ivar name: Field name.
    :ivar type: Primitive type name.
    :ivar description: Field description.
    :ivar default_value: Default value expression.
    :ivar validators: List of validators applied.
    :ivar used_in_apis: Array of endpoint IDs where this field is used.
    """

    id: str = Field(..., examples=["field-1"])
    namespace_id: str = Field(..., alias="namespaceId", examples=["namespace-global"])
    name: str = Field(..., examples=["email"])
    type: str = Field(..., examples=["str"])
    description: str | None = Field(default=None, examples=["User email address"])
    default_value: str | None = Field(default=None, alias="defaultValue", examples=[""])
    validators: list[FieldValidatorSchema] = Field(default_factory=list)
    used_in_apis: list[str] = Field(
        default_factory=list, alias="usedInApis", examples=[["endpoint-1"]]
    )

    class Config:
        """Pydantic model configuration."""

        from_attributes = True
        populate_by_name = True
