# src/api/schemas/field_validator.py
"""Pydantic schemas for Field Validator entity."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FieldValidatorCreate(BaseModel):
    """Request schema for creating a field validator.

    :ivar namespace_id: Namespace this validator belongs to.
    :ivar name: Display name for the validator.
    :ivar function_name: Name of the validation function.
    :ivar mode: Validator mode (before, after, wrap, plain).
    :ivar function_body: Python source code of the validator function.
    :ivar description: Optional description.
    :ivar compatible_types: List of type names this validator applies to.
    """

    namespace_id: UUID = Field(
        ..., alias="namespaceId", examples=["00000000-0000-0000-0000-000000000002"]
    )
    name: str | None = Field(default=None, examples=["Trim Whitespace"])
    function_name: str = Field(..., alias="functionName", examples=["trim_whitespace"])
    mode: str = Field(..., examples=["before"])
    function_body: str = Field(
        ...,
        alias="functionBody",
        examples=["def trim_whitespace(cls, v):\n    return v.strip()"],
    )
    description: str | None = Field(
        default=None, examples=["Trims leading/trailing whitespace"]
    )
    compatible_types: list[str] = Field(
        default_factory=list, alias="compatibleTypes", examples=[["str"]]
    )


class FieldValidatorUpdate(BaseModel):
    """Request schema for updating a field validator.

    :ivar name: Updated display name.
    :ivar function_name: Updated function name.
    :ivar mode: Updated validator mode.
    :ivar function_body: Updated function body.
    :ivar description: Updated description.
    :ivar compatible_types: Updated compatible types.
    """

    name: str | None = Field(default=None, examples=["Trim Whitespace"])
    function_name: str | None = Field(
        default=None, alias="functionName", examples=["trim_whitespace"]
    )
    mode: str | None = Field(default=None, examples=["before"])
    function_body: str | None = Field(
        default=None,
        alias="functionBody",
        examples=["def trim_whitespace(cls, v):\n    return v.strip()"],
    )
    description: str | None = Field(default=None, examples=["Updated description"])
    compatible_types: list[str] | None = Field(
        default=None, alias="compatibleTypes", examples=[["str"]]
    )


class FieldValidatorResponse(BaseModel):
    """Response schema for field validator data.

    :ivar id: Unique identifier for the field validator.
    :ivar namespace_id: Namespace this validator belongs to.
    :ivar name: Display name.
    :ivar function_name: Name of the validation function.
    :ivar mode: Validator mode.
    :ivar function_body: Python source code.
    :ivar description: Optional description.
    :ivar compatible_types: List of type names this validator applies to.
    :ivar used_in_fields: Number of fields using this validator.
    """

    id: UUID = Field(..., examples=["00000000-0000-0000-0005-000000000001"])
    namespace_id: UUID = Field(
        ..., alias="namespaceId", examples=["00000000-0000-0000-0000-000000000001"]
    )
    name: str | None = Field(default=None, examples=["Trim Whitespace"])
    function_name: str = Field(..., alias="functionName", examples=["trim_whitespace"])
    mode: str = Field(..., examples=["before"])
    function_body: str = Field(
        ...,
        alias="functionBody",
        examples=["def trim_whitespace(cls, v):\n    return v.strip()"],
    )
    description: str | None = Field(default=None, examples=["Trims whitespace"])
    compatible_types: list[str] = Field(
        ..., alias="compatibleTypes", examples=[["str"]]
    )
    used_in_fields: int = Field(default=0, alias="usedInFields")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class FieldValidatorReferenceInput(BaseModel):
    """Request schema for attaching a field validator to a field.

    :ivar validator_id: Reference to the field validator definition.
    """

    validator_id: UUID = Field(..., alias="validatorId")

    model_config = ConfigDict(populate_by_name=True)


class FieldValidatorReferenceResponse(BaseModel):
    """Response schema for a field validator reference attached to a field.

    :ivar validator_id: Reference to the field validator definition.
    :ivar function_name: Validator function name.
    :ivar name: Validator display name.
    """

    validator_id: UUID = Field(..., alias="validatorId")
    function_name: str = Field(..., alias="functionName")
    name: str | None = Field(default=None)

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
