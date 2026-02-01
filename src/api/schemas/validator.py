# src/api/schemas/validator.py
"""Pydantic schemas for Validator entity."""

from pydantic import BaseModel, Field


class FieldReferenceSchema(BaseModel):
    """Reference to a field using a validator.

    :ivar name: Field name.
    :ivar field_id: Field unique identifier.
    """

    name: str = Field(..., examples=["email"])
    field_id: str = Field(..., alias="fieldId", examples=["field-1"])

    class Config:
        """Pydantic model configuration."""

        populate_by_name = True


class ValidatorResponse(BaseModel):
    """Response schema for validator data.

    :ivar name: Validator name.
    :ivar namespace_id: Namespace this validator belongs to.
    :ivar type: Validator type category (string, numeric, collection).
    :ivar description: Validator description.
    :ivar category: Whether this is inline or custom.
    :ivar parameter_type: Type of parameter this validator accepts.
    :ivar example_usage: Example Pydantic code usage.
    :ivar pydantic_docs_url: URL to Pydantic documentation.
    :ivar used_in_fields: Count of fields using this validator.
    :ivar fields_using_validator: List of fields using this validator.
    """

    name: str = Field(..., examples=["email_format"])
    namespace_id: str = Field(..., alias="namespaceId", examples=["namespace-global"])
    type: str = Field(..., examples=["string"])
    description: str = Field(..., examples=["Validates email format"])
    category: str = Field(..., examples=["inline"])
    parameter_type: str = Field(..., alias="parameterType", examples=["None"])
    example_usage: str = Field(..., alias="exampleUsage", examples=["EmailStr"])
    pydantic_docs_url: str = Field(
        ..., alias="pydanticDocsUrl", examples=["https://docs.pydantic.dev/"]
    )
    used_in_fields: int = Field(default=0, alias="usedInFields", examples=[3])
    fields_using_validator: list[FieldReferenceSchema] = Field(
        default_factory=list,
        alias="fieldsUsingValidator",
        examples=[[{"name": "email", "fieldId": "field-1"}]],
    )

    class Config:
        """Pydantic model configuration."""

        populate_by_name = True
