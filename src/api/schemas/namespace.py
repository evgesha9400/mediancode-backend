# src/api/schemas/namespace.py
"""Pydantic schemas for Namespace entity."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field


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
    :ivar is_default: Set this namespace as the user's default.
    """

    name: str | None = Field(default=None, examples=["updated-namespace-name"])
    description: str | None = Field(default=None, examples=["Updated description"])
    is_default: bool | None = Field(default=None, alias="isDefault")

    model_config = ConfigDict(populate_by_name=True)


class NamespaceResponse(BaseModel):
    """Response schema for namespace data.

    :ivar id: Unique identifier for the namespace.
    :ivar name: Namespace name.
    :ivar description: Namespace description.
    :ivar is_default: Whether this is the user's default namespace.
    """

    id: UUID = Field(..., examples=["00000000-0000-0000-0000-000000000001"])
    name: str = Field(..., examples=["global"])
    description: str | None = Field(
        default=None, examples=["Immutable global templates and examples"]
    )
    is_default: bool = Field(..., alias="isDefault", examples=[False])

    @computed_field  # type: ignore[prop-decorator]
    @property
    def locked(self) -> bool:
        """True for the provisioned Global namespace (fully read-only)."""
        return self.name == "Global"

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
