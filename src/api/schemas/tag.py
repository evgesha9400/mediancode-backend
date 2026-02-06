# src/api/schemas/tag.py
"""Pydantic schemas for API tags (embedded in API entity)."""

from pydantic import BaseModel, Field


class TagSchema(BaseModel):
    """Schema for a tag embedded in an API.

    Tags are stored as JSONB in the apis table and referenced by name
    from endpoints.

    :ivar name: Tag name for OpenAPI spec.
    :ivar description: Tag description.
    """

    name: str = Field(..., examples=["Users"])
    description: str = Field(..., examples=["User management endpoints"])

    class Config:
        """Pydantic model configuration."""

        populate_by_name = True
