# src/api/schemas/validator.py
"""Pydantic schemas for Validator entity."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FieldReferenceSchema(BaseModel):
    """Reference to a field using a validator.

    :ivar name: Field name.
    :ivar field_id: Field unique identifier.
    """

    name: str = Field(..., examples=["email"])
    field_id: UUID = Field(
        ..., alias="fieldId", examples=["00000000-0000-0000-0003-000000000001"]
    )

    model_config = ConfigDict(populate_by_name=True)


class ValidatorResponse(BaseModel):
    """Response schema for validator data.

    :ivar id: Unique identifier for the validator.
    :ivar namespace_id: Namespace this validator belongs to.
    :ivar name: Validator name.
    :ivar type: Validator type category (string, numeric, collection).
    :ivar description: Validator description.
    :ivar category: Whether this is inline or custom.
    :ivar parameter_type: Type of parameter this validator accepts.
    :ivar example_usage: Example Pydantic code usage.
    :ivar docs_url: URL to documentation.
    :ivar used_in_fields: Count of fields using this validator.
    :ivar fields_using_validator: List of fields using this validator.
    """

    id: UUID = Field(..., examples=["00000000-0000-0000-0002-000000000001"])
    namespace_id: UUID = Field(
        ..., alias="namespaceId", examples=["00000000-0000-0000-0000-000000000001"]
    )
    name: str = Field(..., examples=["max_length"])
    type: str = Field(..., examples=["string"])
    description: str = Field(
        ..., examples=["Validates string length does not exceed maximum"]
    )
    category: str = Field(..., examples=["inline"])
    parameter_type: str = Field(..., alias="parameterType", examples=["int"])
    example_usage: str = Field(
        ..., alias="exampleUsage", examples=["Field(max_length=255)"]
    )
    docs_url: str = Field(..., alias="docsUrl", examples=["https://docs.pydantic.dev/"])
    used_in_fields: int = Field(default=0, alias="usedInFields", examples=[3])
    fields_using_validator: list[FieldReferenceSchema] = Field(
        default_factory=list,
        alias="fieldsUsingValidator",
        examples=[[{"name": "email", "fieldId": "field-1"}]],
    )

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
