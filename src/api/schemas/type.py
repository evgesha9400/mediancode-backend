# src/api/schemas/type.py
"""Pydantic schemas for Type entity."""

from pydantic import BaseModel, Field


class TypeResponse(BaseModel):
    """Response schema for type data.

    :ivar name: Type name.
    :ivar category: Type category (primitive or abstract).
    :ivar python_type: Python type representation.
    :ivar description: Type description.
    :ivar validator_categories: Compatible validator categories for this type.
    :ivar used_in_fields: Count of fields using this type.
    """

    name: str = Field(..., examples=["str"])
    category: str = Field(..., examples=["primitive"])
    python_type: str = Field(..., alias="pythonType", examples=["str"])
    description: str = Field(..., examples=["String type for text data"])
    validator_categories: list[str] = Field(
        ..., alias="validatorCategories", examples=[["string"]]
    )
    used_in_fields: int = Field(default=0, alias="usedInFields", examples=[5])

    class Config:
        """Pydantic model configuration."""

        populate_by_name = True
