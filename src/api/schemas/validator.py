# src/api/schemas/validator.py
"""Pydantic schemas for Validator entity."""

from pydantic import BaseModel, Field


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

    class Config:
        """Pydantic model configuration."""

        populate_by_name = True
