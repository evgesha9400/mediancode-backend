# src/api/schemas/constraint.py
"""Pydantic schemas for Constraint entity."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FieldReferenceSchema(BaseModel):
    """Reference to a field using a constraint.

    :ivar name: Field name.
    :ivar field_id: Field unique identifier.
    """

    name: str = Field(..., examples=["email"])
    field_id: UUID = Field(
        ..., alias="fieldId", examples=["00000000-0000-0000-0003-000000000001"]
    )

    model_config = ConfigDict(populate_by_name=True)


class ConstraintResponse(BaseModel):
    """Response schema for constraint data.

    :ivar id: Unique identifier for the constraint.
    :ivar namespace_id: Namespace this constraint belongs to.
    :ivar name: Constraint name.
    :ivar description: Constraint description.
    :ivar parameter_type: Type of parameter this constraint accepts.
    :ivar docs_url: URL to documentation.
    :ivar compatible_types: List of type names this constraint applies to.
    :ivar used_in_fields: Count of fields using this constraint.
    :ivar fields_using_constraint: List of fields using this constraint.
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
    used_in_fields: int = Field(default=0, alias="usedInFields", examples=[3])
    fields_using_constraint: list[FieldReferenceSchema] = Field(
        default_factory=list,
        alias="fieldsUsingConstraint",
        examples=[[{"name": "email", "fieldId": "field-1"}]],
    )

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
