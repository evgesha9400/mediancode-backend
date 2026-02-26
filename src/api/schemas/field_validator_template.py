# src/api/schemas/field_validator_template.py
"""Pydantic schemas for Field Validator Template entity."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from api.schemas.literals import ValidatorMode


class FieldValidatorTemplateResponse(BaseModel):
    """Response schema for a field validator template.

    :ivar id: Unique identifier for the template.
    :ivar name: Template display name.
    :ivar description: Template description.
    :ivar compatible_types: List of type names this template applies to.
    :ivar mode: Validator mode (before, after).
    :ivar parameters: Template parameter definitions.
    :ivar body_template: Jinja2 template for the function body.
    """

    id: UUID
    name: str
    description: str
    compatible_types: list[str] = Field(..., alias="compatibleTypes")
    mode: ValidatorMode
    parameters: list[dict]
    body_template: str = Field(..., alias="bodyTemplate")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
