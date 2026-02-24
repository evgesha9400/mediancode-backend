# src/api/schemas/model_validator_template.py
"""Pydantic schemas for Model Validator Template entity."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ModelValidatorTemplateResponse(BaseModel):
    """Response schema for a model validator template.

    :ivar id: Unique identifier for the template.
    :ivar name: Template display name.
    :ivar description: Template description.
    :ivar mode: Validator mode (before, after).
    :ivar parameters: Template parameter definitions.
    :ivar field_mappings: Field mapping definitions.
    :ivar body_template: Jinja2 template for the function body.
    """

    id: UUID
    name: str
    description: str
    mode: str
    parameters: list[dict]
    field_mappings: list[dict] = Field(..., alias="fieldMappings")
    body_template: str = Field(..., alias="bodyTemplate")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
