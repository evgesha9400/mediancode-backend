# src/api/schemas/api.py
"""Pydantic schemas for Api entity."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from api_craft.models.enums import CdkCompute
from api_craft.models.types import PascalCaseName


class ApiCreate(BaseModel):
    """Request schema for creating an API.

    :ivar namespace_id: Namespace this API belongs to.
    :ivar title: API title in PascalCase (used as project identifier).
    :ivar version: Semantic version string.
    :ivar description: API description.
    :ivar base_url: Base path for all endpoints.
    :ivar server_url: Full server URL.
    """

    namespace_id: UUID = Field(
        ..., alias="namespaceId", examples=["00000000-0000-0000-0000-000000000002"]
    )
    title: PascalCaseName = Field(..., examples=["UserManagementApi"])
    version: str = Field(..., examples=["1.0.0"])
    description: str | None = Field(
        default="", examples=["API for managing user accounts"]
    )
    base_url: str | None = Field(default="", alias="baseUrl", examples=["/api/v1"])
    server_url: str | None = Field(
        default="", alias="serverUrl", examples=["https://api.example.com"]
    )


class ApiUpdate(BaseModel):
    """Request schema for updating an API.

    :ivar title: Updated API title in PascalCase.
    :ivar version: Updated version string.
    :ivar description: Updated API description.
    :ivar base_url: Updated base path.
    :ivar server_url: Updated server URL.
    """

    title: PascalCaseName | None = Field(default=None, examples=["UpdatedApiTitle"])
    version: str | None = Field(default=None, examples=["2.0.0"])
    description: str | None = Field(default=None, examples=["Updated API description"])
    base_url: str | None = Field(default=None, alias="baseUrl", examples=["/api/v2"])
    server_url: str | None = Field(
        default=None, alias="serverUrl", examples=["https://api.example.com"]
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
    created_at: datetime = Field(
        ..., alias="createdAt", examples=["2026-01-25T10:30:00Z"]
    )
    updated_at: datetime = Field(
        ..., alias="updatedAt", examples=["2026-01-25T10:30:00Z"]
    )

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class GenerateOptions(BaseModel):
    """Options for code generation passed to POST /v1/apis/{api_id}/generate.

    :ivar response_placeholders: Generate placeholder response bodies.
    :ivar database_enabled: Generate database support (SQLAlchemy, Alembic, Docker Compose).
    :ivar cdk_enabled: Generate CDK infrastructure files.
    :ivar cdk_compute: Compute platform for CDK — 'lambda' or 'ecs'.
    """

    response_placeholders: bool = Field(default=True, alias="responsePlaceholders")
    database_enabled: bool = Field(default=False, alias="databaseEnabled")
    cdk_enabled: bool = Field(default=False, alias="cdkEnabled")
    cdk_compute: CdkCompute = Field(default="lambda", alias="cdkCompute")

    model_config = ConfigDict(populate_by_name=True)
