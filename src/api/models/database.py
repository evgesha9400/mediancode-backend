# src/api/models/database.py
"""SQLAlchemy ORM models for all API entities."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base

if TYPE_CHECKING:
    pass


def generate_uuid() -> str:
    """Generate a UUID string for use as primary key.

    :returns: A UUID4 string.
    """
    return str(uuid4())


def utc_now() -> datetime:
    """Return current UTC timestamp.

    :returns: Current datetime in UTC.
    """
    return datetime.now(timezone.utc)


class Namespace(Base):
    """Namespace for organizing API entities.

    :ivar id: Unique identifier for the namespace.
    :ivar user_id: Owner user ID from Clerk (null for global namespace).
    :ivar name: Namespace display name.
    :ivar description: Optional description.
    :ivar locked: Whether this namespace is immutable (e.g., global).
    """

    __tablename__ = "namespaces"

    id: Mapped[str] = mapped_column(
        String(255), primary_key=True, default=generate_uuid
    )
    user_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    apis: Mapped[list["ApiModel"]] = relationship(
        back_populates="namespace", cascade="all, delete-orphan"
    )
    fields: Mapped[list["FieldModel"]] = relationship(
        back_populates="namespace", cascade="all, delete-orphan"
    )
    objects: Mapped[list["ObjectDefinition"]] = relationship(
        back_populates="namespace", cascade="all, delete-orphan"
    )
    tags: Mapped[list["EndpointTag"]] = relationship(
        back_populates="namespace", cascade="all, delete-orphan"
    )
    endpoints: Mapped[list["ApiEndpoint"]] = relationship(
        back_populates="namespace", cascade="all, delete-orphan"
    )


class ApiModel(Base):
    """API definition containing endpoints and tags.

    :ivar id: Unique identifier for the API.
    :ivar namespace_id: Reference to the containing namespace.
    :ivar user_id: Owner user ID from Clerk.
    :ivar title: API title for OpenAPI spec.
    :ivar version: Semantic version string.
    :ivar description: API description.
    :ivar base_url: Base path for all endpoints.
    :ivar server_url: Full server URL.
    :ivar created_at: Creation timestamp.
    :ivar updated_at: Last update timestamp.
    """

    __tablename__ = "apis"

    id: Mapped[str] = mapped_column(
        String(255), primary_key=True, default=generate_uuid
    )
    namespace_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("namespaces.id"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    base_url: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    server_url: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    namespace: Mapped["Namespace"] = relationship(back_populates="apis")
    tags: Mapped[list["EndpointTag"]] = relationship(
        back_populates="api", cascade="all, delete-orphan"
    )
    endpoints: Mapped[list["ApiEndpoint"]] = relationship(
        back_populates="api", cascade="all, delete-orphan"
    )


class FieldModel(Base):
    """Field definition used in object compositions.

    :ivar id: Unique identifier for the field.
    :ivar namespace_id: Reference to the containing namespace.
    :ivar user_id: Owner user ID from Clerk.
    :ivar name: Field name (will become Pydantic field name).
    :ivar type: Primitive type name (str, int, float, bool, datetime, uuid).
    :ivar description: Field description.
    :ivar default_value: Default value expression (Python code).
    """

    __tablename__ = "fields"

    id: Mapped[str] = mapped_column(
        String(255), primary_key=True, default=generate_uuid
    )
    namespace_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("namespaces.id"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_value: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    namespace: Mapped["Namespace"] = relationship(back_populates="fields")
    validators: Mapped[list["FieldValidator"]] = relationship(
        back_populates="field", cascade="all, delete-orphan"
    )
    object_associations: Mapped[list["ObjectFieldAssociation"]] = relationship(
        back_populates="field"
    )


class FieldValidator(Base):
    """Validator applied to a field.

    :ivar id: Unique identifier for the validator instance.
    :ivar field_id: Reference to the parent field.
    :ivar name: Validator name (references ValidatorBase.name).
    :ivar params: Validator parameters as JSON.
    """

    __tablename__ = "field_validators"

    id: Mapped[str] = mapped_column(
        String(255), primary_key=True, default=generate_uuid
    )
    field_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("fields.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    params: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    field: Mapped["FieldModel"] = relationship(back_populates="validators")


class ObjectDefinition(Base):
    """Object definition composed of field references.

    :ivar id: Unique identifier for the object.
    :ivar namespace_id: Reference to the containing namespace.
    :ivar user_id: Owner user ID from Clerk.
    :ivar name: Object name (will become Pydantic model class name).
    :ivar description: Object description.
    """

    __tablename__ = "objects"

    id: Mapped[str] = mapped_column(
        String(255), primary_key=True, default=generate_uuid
    )
    namespace_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("namespaces.id"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    namespace: Mapped["Namespace"] = relationship(back_populates="objects")
    field_associations: Mapped[list["ObjectFieldAssociation"]] = relationship(
        back_populates="object", cascade="all, delete-orphan"
    )


class ObjectFieldAssociation(Base):
    """Association between objects and fields with required flag.

    :ivar id: Unique identifier for the association.
    :ivar object_id: Reference to the parent object.
    :ivar field_id: Reference to the field.
    :ivar required: Whether this field is required in the object.
    :ivar position: Order position for field display.
    """

    __tablename__ = "object_field_associations"

    id: Mapped[str] = mapped_column(
        String(255), primary_key=True, default=generate_uuid
    )
    object_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("objects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("fields.id"), nullable=False, index=True
    )
    required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    position: Mapped[int] = mapped_column(default=0, nullable=False)

    # Relationships
    object: Mapped["ObjectDefinition"] = relationship(
        back_populates="field_associations"
    )
    field: Mapped["FieldModel"] = relationship(back_populates="object_associations")


class EndpointTag(Base):
    """Tag for grouping endpoints in OpenAPI spec.

    :ivar id: Unique identifier for the tag.
    :ivar namespace_id: Reference to the containing namespace.
    :ivar api_id: Reference to the parent API.
    :ivar user_id: Owner user ID from Clerk.
    :ivar name: Tag name for OpenAPI spec.
    :ivar description: Tag description.
    """

    __tablename__ = "endpoint_tags"

    id: Mapped[str] = mapped_column(
        String(255), primary_key=True, default=generate_uuid
    )
    namespace_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("namespaces.id"), nullable=False, index=True
    )
    api_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("apis.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    namespace: Mapped["Namespace"] = relationship(back_populates="tags")
    api: Mapped["ApiModel"] = relationship(back_populates="tags")
    endpoints: Mapped[list["ApiEndpoint"]] = relationship(back_populates="tag")


class ApiEndpoint(Base):
    """API endpoint definition.

    :ivar id: Unique identifier for the endpoint.
    :ivar namespace_id: Reference to the containing namespace.
    :ivar api_id: Reference to the parent API.
    :ivar user_id: Owner user ID from Clerk.
    :ivar method: HTTP method (GET, POST, PUT, PATCH, DELETE).
    :ivar path: URL path with optional parameters in {braces}.
    :ivar description: Endpoint description for OpenAPI spec.
    :ivar tag_id: Optional reference to EndpointTag.
    :ivar query_params_object_id: Optional reference to Object for query parameters.
    :ivar request_body_object_id: Optional reference to Object for request body.
    :ivar response_body_object_id: Optional reference to Object for response body.
    :ivar use_envelope: Whether to wrap response in standard envelope.
    :ivar response_shape: Response shape (object or list).
    """

    __tablename__ = "api_endpoints"

    id: Mapped[str] = mapped_column(
        String(255), primary_key=True, default=generate_uuid
    )
    namespace_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("namespaces.id"), nullable=False, index=True
    )
    api_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("apis.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    method: Mapped[str] = mapped_column(
        Enum("GET", "POST", "PUT", "PATCH", "DELETE", name="http_method"),
        nullable=False,
    )
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    tag_id: Mapped[str | None] = mapped_column(
        String(255), ForeignKey("endpoint_tags.id"), nullable=True, index=True
    )
    query_params_object_id: Mapped[str | None] = mapped_column(
        String(255), ForeignKey("objects.id"), nullable=True
    )
    request_body_object_id: Mapped[str | None] = mapped_column(
        String(255), ForeignKey("objects.id"), nullable=True
    )
    response_body_object_id: Mapped[str | None] = mapped_column(
        String(255), ForeignKey("objects.id"), nullable=True
    )
    use_envelope: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    response_shape: Mapped[str] = mapped_column(
        Enum("object", "list", name="response_shape"),
        default="object",
        nullable=False,
    )

    # Relationships
    namespace: Mapped["Namespace"] = relationship(back_populates="endpoints")
    api: Mapped["ApiModel"] = relationship(back_populates="endpoints")
    tag: Mapped["EndpointTag | None"] = relationship(back_populates="endpoints")
    path_params: Mapped[list["EndpointParameter"]] = relationship(
        back_populates="endpoint", cascade="all, delete-orphan"
    )
    query_params_object: Mapped["ObjectDefinition | None"] = relationship(
        foreign_keys=[query_params_object_id]
    )
    request_body_object: Mapped["ObjectDefinition | None"] = relationship(
        foreign_keys=[request_body_object_id]
    )
    response_body_object: Mapped["ObjectDefinition | None"] = relationship(
        foreign_keys=[response_body_object_id]
    )


class EndpointParameter(Base):
    """Path parameter for an endpoint.

    :ivar id: Unique identifier for the parameter.
    :ivar endpoint_id: Reference to the parent endpoint.
    :ivar name: Parameter name (extracted from path {braces}).
    :ivar type: Primitive type name.
    :ivar description: Parameter description.
    :ivar required: Whether parameter is required (path params always true).
    :ivar position: Order position for parameter display.
    """

    __tablename__ = "endpoint_parameters"

    id: Mapped[str] = mapped_column(
        String(255), primary_key=True, default=generate_uuid
    )
    endpoint_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("api_endpoints.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    position: Mapped[int] = mapped_column(default=0, nullable=False)

    # Relationships
    endpoint: Mapped["ApiEndpoint"] = relationship(back_populates="path_params")
