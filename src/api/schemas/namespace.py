# src/api/schemas/namespace.py
"""Pydantic schemas for Namespace entity."""

from pydantic import BaseModel, Field


class NamespaceCreate(BaseModel):
    """Request schema for creating a namespace.

    :ivar name: Namespace name.
    :ivar description: Optional namespace description.
    """

    name: str = Field(..., examples=["my-api-project"])
    description: str | None = Field(
        default=None, examples=["Custom namespace for my API project"]
    )


class NamespaceUpdate(BaseModel):
    """Request schema for updating a namespace.

    :ivar name: Updated namespace name.
    :ivar description: Updated namespace description.
    """

    name: str | None = Field(default=None, examples=["updated-namespace-name"])
    description: str | None = Field(default=None, examples=["Updated description"])


class NamespaceResponse(BaseModel):
    """Response schema for namespace data.

    :ivar id: Unique identifier for the namespace.
    :ivar name: Namespace name.
    :ivar description: Namespace description.
    :ivar locked: Whether this namespace is locked (immutable).
    """

    id: str = Field(..., examples=["namespace-global"])
    name: str = Field(..., examples=["global"])
    description: str | None = Field(
        default=None, examples=["Immutable global templates and examples"]
    )
    locked: bool = Field(..., examples=[True])

    class Config:
        """Pydantic model configuration."""

        from_attributes = True
