# src/api/schemas/model_validator.py
"""Pydantic schemas for Model Validator entity."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ModelValidatorCreate(BaseModel):
    """Request schema for creating a model validator.

    :ivar namespace_id: Namespace this validator belongs to.
    :ivar name: Name of the validation function.
    :ivar description: Optional description.
    :ivar required_fields: List of field names required by this validator.
    :ivar mode: Validator mode (before, after).
    :ivar code: Python source code of the validator function.
    """

    namespace_id: UUID = Field(
        ..., alias="namespaceId", examples=["00000000-0000-0000-0000-000000000002"]
    )
    name: str = Field(..., examples=["check_password_match"])
    description: str | None = Field(
        default=None, examples=["Ensures password and confirm_password match"]
    )
    required_fields: list[str] = Field(
        default_factory=list,
        alias="requiredFields",
        examples=[["password", "confirm_password"]],
    )
    mode: str = Field(..., examples=["after"])
    code: str = Field(
        ...,
        examples=[
            "def check_password_match(cls, values):\n"
            "    if values.password != values.confirm_password:\n"
            '        raise ValueError("Passwords do not match")\n'
            "    return values"
        ],
    )


class ModelValidatorUpdate(BaseModel):
    """Request schema for updating a model validator.

    :ivar name: Updated function name.
    :ivar description: Updated description.
    :ivar required_fields: Updated required fields.
    :ivar mode: Updated validator mode.
    :ivar code: Updated function body.
    """

    name: str | None = Field(default=None, examples=["check_password_match"])
    description: str | None = Field(default=None, examples=["Updated description"])
    required_fields: list[str] | None = Field(
        default=None,
        alias="requiredFields",
        examples=[["password", "confirm_password"]],
    )
    mode: str | None = Field(default=None, examples=["after"])
    code: str | None = Field(default=None, examples=["def validate(cls, values): ..."])


class ModelValidatorResponse(BaseModel):
    """Response schema for model validator data.

    :ivar id: Unique identifier for the model validator.
    :ivar namespace_id: Namespace this validator belongs to.
    :ivar name: Name of the validation function.
    :ivar description: Optional description.
    :ivar required_fields: List of field names required by this validator.
    :ivar mode: Validator mode.
    :ivar code: Python source code.
    :ivar used_in_objects: Number of objects using this validator.
    """

    id: UUID = Field(..., examples=["00000000-0000-0000-0006-000000000001"])
    namespace_id: UUID = Field(
        ..., alias="namespaceId", examples=["00000000-0000-0000-0000-000000000001"]
    )
    name: str = Field(..., examples=["check_password_match"])
    description: str | None = Field(default=None, examples=["Validates password match"])
    required_fields: list[str] = Field(
        ...,
        alias="requiredFields",
        examples=[["password", "confirm_password"]],
    )
    mode: str = Field(..., examples=["after"])
    code: str = Field(..., examples=["def check_password_match(cls, values): ..."])
    used_in_objects: int = Field(default=0, alias="usedInObjects")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ModelValidatorReferenceInput(BaseModel):
    """Request schema for attaching a model validator to an object.

    :ivar validator_id: Reference to the model validator definition.
    """

    validator_id: UUID = Field(..., alias="validatorId")

    model_config = ConfigDict(populate_by_name=True)


class ModelValidatorReferenceResponse(BaseModel):
    """Response schema for a model validator reference attached to an object.

    :ivar validator_id: Reference to the model validator definition.
    :ivar name: Validator function name.
    """

    validator_id: UUID = Field(..., alias="validatorId")
    name: str = Field(...)

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
