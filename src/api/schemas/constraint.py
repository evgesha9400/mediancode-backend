# src/api/schemas/constraint.py
"""Pydantic schemas for Constraint entity."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ConstraintResponse(BaseModel):
    """Response schema for constraint data.

    :ivar id: Unique identifier for the constraint.
    :ivar namespace_id: Namespace this constraint belongs to.
    :ivar name: Constraint name.
    :ivar description: Constraint description.
    :ivar parameter_type: Type of parameter this constraint accepts.
    :ivar docs_url: URL to documentation.
    :ivar compatible_types: List of type names this constraint applies to.
    """

    id: UUID = Field(..., examples=["00000000-0000-0000-0002-000000000001"])
    namespace_id: UUID = Field(
        ..., alias="namespaceId", examples=["00000000-0000-0000-0000-000000000001"]
    )
    name: str = Field(..., examples=["max_length"])
    description: str = Field(
        ..., examples=["Validates string length does not exceed maximum"]
    )
    parameter_type: str = Field(..., alias="parameterType", examples=["int"])
    docs_url: str | None = Field(
        default=None, alias="docsUrl", examples=["https://docs.pydantic.dev/"]
    )
    compatible_types: list[str] = Field(
        ..., alias="compatibleTypes", examples=[["str", "uuid"]]
    )

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
