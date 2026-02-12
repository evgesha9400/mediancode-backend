# src/api/schemas/api.py
"""Pydantic schemas for Api entity."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from api.schemas.tag import TagSchema


class ApiCreate(BaseModel):
    """Request schema for creating an API.

    :ivar namespace_id: Namespace this API belongs to.
    :ivar title: API title for OpenAPI spec.
    :ivar version: Semantic version string.
    :ivar description: API description.
    :ivar base_url: Base path for all endpoints.
    :ivar server_url: Full server URL.
    :ivar tags: List of tag definitions for this API.
    """

    namespace_id: UUID = Field(
        ..., alias="namespaceId", examples=["00000000-0000-0000-0000-000000000002"]
    )
    title: str = Field(..., examples=["User Management API"])
    version: str = Field(..., examples=["1.0.0"])
    description: str | None = Field(
        default="", examples=["API for managing user accounts"]
    )
    base_url: str | None = Field(default="", alias="baseUrl", examples=["/api/v1"])
    server_url: str | None = Field(
        default="", alias="serverUrl", examples=["https://api.example.com"]
    )
    tags: list[TagSchema] = Field(
        default_factory=list,
        examples=[[{"name": "Users", "description": "User management endpoints"}]],
    )


class ApiUpdate(BaseModel):
    """Request schema for updating an API.

    :ivar title: Updated API title.
    :ivar version: Updated version string.
    :ivar description: Updated API description.
    :ivar base_url: Updated base path.
    :ivar server_url: Updated server URL.
    :ivar tags: Updated list of tag definitions.
    """

    title: str | None = Field(default=None, examples=["Updated API Title"])
    version: str | None = Field(default=None, examples=["2.0.0"])
    description: str | None = Field(default=None, examples=["Updated API description"])
    base_url: str | None = Field(default=None, alias="baseUrl", examples=["/api/v2"])
    server_url: str | None = Field(
        default=None, alias="serverUrl", examples=["https://api.example.com"]
    )
    tags: list[TagSchema] | None = Field(
        default=None,
        examples=[[{"name": "Users", "description": "Updated user endpoints"}]],
    )


class ApiResponse(BaseModel):
    """Response schema for API data.

    :ivar id: Unique identifier for the API.
    :ivar namespace_id: Namespace this API belongs to.
    :ivar title: API title.
    :ivar version: Semantic version string.
    :ivar description: API description.
    :ivar base_url: Base path for all endpoints.
    :ivar server_url: Full server URL.
    :ivar tags: List of tag definitions for this API.
    :ivar created_at: Creation timestamp.
    :ivar updated_at: Last update timestamp.
    """

    id: UUID = Field(..., examples=["00000000-0000-0000-0005-000000000001"])
    namespace_id: UUID = Field(
        ..., alias="namespaceId", examples=["00000000-0000-0000-0000-000000000001"]
    )
    title: str = Field(..., examples=["User Management API"])
    version: str = Field(..., examples=["1.0.0"])
    description: str = Field(..., examples=["Endpoints for user management"])
    base_url: str = Field(..., alias="baseUrl", examples=["/api/v1"])
    server_url: str = Field(
        ..., alias="serverUrl", examples=["https://api.example.com"]
    )
    tags: list[TagSchema] = Field(
        default_factory=list,
        examples=[[{"name": "Users", "description": "User management endpoints"}]],
    )
    created_at: datetime = Field(
        ..., alias="createdAt", examples=["2026-01-25T10:30:00Z"]
    )
    updated_at: datetime = Field(
        ..., alias="updatedAt", examples=["2026-01-25T10:30:00Z"]
    )

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
