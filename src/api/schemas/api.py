# src/api/schemas/api.py
"""Pydantic schemas for Api entity."""

from datetime import datetime
from uuid import UUID

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

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

    :ivar healthcheck: Path for the healthcheck endpoint (None to disable).
    :ivar response_placeholders: Generate placeholder response bodies.
    :ivar format_code: Format generated code with Black.
    :ivar generate_swagger: Auto-generate swagger.yaml.
    :ivar database_enabled: Generate database support (SQLAlchemy, Alembic, Docker Compose).
    :ivar database_seed_data: Generate seed data helpers (only when database_enabled is True).
    """

    healthcheck: str | None = Field(default="/health")
    response_placeholders: bool = Field(default=True, alias="responsePlaceholders")
    format_code: bool = Field(default=True, alias="formatCode")
    generate_swagger: bool = Field(default=True, alias="generateSwagger")
    database_enabled: bool = Field(default=False, alias="databaseEnabled")
    database_seed_data: bool = Field(default=True, alias="databaseSeedData")

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def _validate_mutual_exclusivity(self) -> Self:
        """Validate that database and response placeholders are not both enabled.

        :returns: The validated options instance.
        :raises ValueError: If both database and response placeholders are enabled.
        """
        if self.database_enabled and self.response_placeholders:
            raise ValueError(
                "Response placeholders cannot be enabled when database generation is active. "
                "Disable response placeholders or disable database generation."
            )
        return self
