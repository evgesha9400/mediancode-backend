# src/api/schemas/tag.py
"""Pydantic schemas for EndpointTag entity."""

from pydantic import BaseModel, Field


class TagCreate(BaseModel):
    """Request schema for creating a tag.

    :ivar namespace_id: Namespace this tag belongs to.
    :ivar api_id: API this tag belongs to.
    :ivar name: Tag name.
    :ivar description: Tag description.
    """

    namespace_id: str = Field(..., alias="namespaceId", examples=["namespace-user"])
    api_id: str = Field(..., alias="apiId", examples=["api-1"])
    name: str = Field(..., examples=["Users"])
    description: str = Field(..., examples=["User management endpoints"])


class TagUpdate(BaseModel):
    """Request schema for updating a tag.

    :ivar api_id: Updated API reference.
    :ivar name: Updated tag name.
    :ivar description: Updated description.
    """

    api_id: str | None = Field(default=None, alias="apiId", examples=["api-1"])
    name: str | None = Field(default=None, examples=["UpdatedTagName"])
    description: str | None = Field(default=None, examples=["Updated description"])


class TagResponse(BaseModel):
    """Response schema for tag data.

    :ivar id: Unique identifier for the tag.
    :ivar namespace_id: Namespace this tag belongs to.
    :ivar api_id: API this tag belongs to.
    :ivar name: Tag name.
    :ivar description: Tag description.
    """

    id: str = Field(..., examples=["tag-1"])
    namespace_id: str = Field(..., alias="namespaceId", examples=["namespace-global"])
    api_id: str = Field(..., alias="apiId", examples=["api-1"])
    name: str = Field(..., examples=["Users"])
    description: str = Field(..., examples=["User management endpoints"])

    class Config:
        """Pydantic model configuration."""

        from_attributes = True
        populate_by_name = True
