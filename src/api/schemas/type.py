# src/api/schemas/type.py
"""Pydantic schemas for Type entity."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TypeResponse(BaseModel):
    """Response schema for type data.

    :ivar id: Unique identifier for the type.
    :ivar namespace_id: Namespace this type belongs to.
    :ivar name: Type name.
    :ivar category: Type category (primitive or abstract).
    :ivar python_type: Python type representation.
    :ivar description: Type description.
    :ivar compatible_types: Compatible validator categories for this type.
    :ivar used_in_fields: Count of fields using this type.
    """

    id: UUID = Field(..., examples=["00000000-0000-0000-0001-000000000001"])
    namespace_id: UUID = Field(
        ..., alias="namespaceId", examples=["00000000-0000-0000-0000-000000000001"]
    )
    name: str = Field(..., examples=["str"])
    category: str = Field(..., examples=["primitive"])
    python_type: str = Field(..., alias="pythonType", examples=["str"])
    description: str = Field(..., examples=["String type for text data"])
    compatible_types: list[str] = Field(
        ..., alias="compatibleTypes", examples=[["string"]]
    )
    used_in_fields: int = Field(default=0, alias="usedInFields", examples=[5])

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
