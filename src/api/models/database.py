# src/api/models/database.py
"""SQLAlchemy ORM models for all API entities."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base

if TYPE_CHECKING:
    pass


def generate_uuid() -> UUID:
    """Generate a UUID for use as primary key.

    :returns: A UUID4 object.
    """
    return uuid4()


def utc_now() -> datetime:
    """Return current UTC timestamp.

    :returns: Current datetime in UTC.
    """
    return datetime.now(timezone.utc)


class UserModel(Base):
    """Application user linked to Clerk for authentication.

    :ivar id: Unique identifier for the user.
    :ivar clerk_id: Clerk user ID (unique external identifier).
    :ivar created_at: Creation timestamp.
    :ivar updated_at: Last update timestamp.
    """

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    clerk_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    first_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    namespaces: Mapped[list["Namespace"]] = relationship(back_populates="user")
    types: Mapped[list["TypeModel"]] = relationship(back_populates="user")
    apis: Mapped[list["ApiModel"]] = relationship(back_populates="user")
    fields: Mapped[list["FieldModel"]] = relationship(back_populates="user")
    objects: Mapped[list["ObjectDefinition"]] = relationship(back_populates="user")
    generations: Mapped[list["GenerationModel"]] = relationship(back_populates="user")


class GenerationModel(Base):
    """Log entry for each API code generation event.

    :ivar id: Unique identifier for the generation.
    :ivar user_id: Reference to the user who triggered the generation.
    :ivar api_id: Reference to the API that was generated.
    :ivar created_at: Timestamp of the generation event.
    """

    __tablename__ = "generations"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    api_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("apis.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    user: Mapped["UserModel"] = relationship(back_populates="generations")
    api: Mapped["ApiModel"] = relationship(back_populates="generations")


class Namespace(Base):
    """Namespace for organizing API entities.

    :ivar id: Unique identifier for the namespace.
    :ivar user_id: Owner user ID from Clerk (null for system namespace).
    :ivar name: Namespace display name.
    :ivar description: Optional description.
    :ivar is_default: Whether this is the user's default namespace.
    """

    __tablename__ = "namespaces"
    __table_args__ = (
        Index(
            "ix_namespaces_one_default_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("is_default = true"),
        ),
        UniqueConstraint("user_id", "name", name="uq_namespaces_user_name"),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    user_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    user: Mapped["UserModel | None"] = relationship(back_populates="namespaces")
    apis: Mapped[list["ApiModel"]] = relationship(
        back_populates="namespace", cascade="all, delete-orphan"
    )
    fields: Mapped[list["FieldModel"]] = relationship(
        back_populates="namespace", cascade="all, delete-orphan"
    )
    objects: Mapped[list["ObjectDefinition"]] = relationship(
        back_populates="namespace", cascade="all, delete-orphan"
    )
    types: Mapped[list["TypeModel"]] = relationship(
        back_populates="namespace", cascade="all, delete-orphan"
    )
    field_constraints: Mapped[list["FieldConstraintModel"]] = relationship(
        back_populates="namespace", cascade="all, delete-orphan"
    )


class TypeModel(Base):
    """Type definition for field types.

    :ivar id: Unique identifier for the type.
    :ivar namespace_id: Reference to the containing namespace.
    :ivar user_id: Owner user ID (null for system seed types).
    :ivar name: Type name (str, int, float, bool, datetime, uuid).
    :ivar python_type: Python type representation.
    :ivar description: Type description.
    :ivar import_path: Import statement for this type (e.g. 'from datetime import datetime').
    :ivar parent_type_id: Self-referential FK for constrained types (e.g. EmailStr → str).
    """

    __tablename__ = "types"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    namespace_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("namespaces.id"), nullable=False, index=True
    )
    user_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    python_type: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    import_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_type_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("types.id"), nullable=True
    )

    # Relationships
    user: Mapped["UserModel | None"] = relationship(back_populates="types")
    namespace: Mapped["Namespace"] = relationship(back_populates="types")
    fields: Mapped[list["FieldModel"]] = relationship(back_populates="field_type")
    parent_type: Mapped["TypeModel | None"] = relationship(
        remote_side=[id], back_populates="children"
    )
    children: Mapped[list["TypeModel"]] = relationship(back_populates="parent_type")


class FieldConstraintModel(Base):
    """Field constraint definition (Pydantic Field constraints like max_length, gt, etc.).

    :ivar id: Unique identifier for the field constraint.
    :ivar namespace_id: Reference to the containing namespace.
    :ivar name: Constraint name (max_length, min_length, gt, ge, etc.).
    :ivar description: Constraint description.
    :ivar parameter_types: List of types this constraint's parameter accepts.
    :ivar docs_url: URL to documentation.
    :ivar compatible_types: List of type names this constraint applies to.
    """

    __tablename__ = "field_constraints"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    namespace_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("namespaces.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    parameter_types: Mapped[list] = mapped_column(ARRAY(Text), nullable=False)
    docs_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    compatible_types: Mapped[list] = mapped_column(ARRAY(Text), nullable=False)

    # Relationships
    namespace: Mapped["Namespace"] = relationship(back_populates="field_constraints")


class FieldValidatorTemplateModel(Base):
    """Field validator template definition (system-seeded catalogue).

    :ivar id: Unique identifier for the template.
    :ivar name: Template display name.
    :ivar description: Template description.
    :ivar compatible_types: List of type names this template applies to.
    :ivar mode: Validator mode (before, after).
    :ivar parameters: Template parameter definitions (JSONB array).
    :ivar body_template: Jinja2 template for the function body.
    """

    __tablename__ = "field_validator_templates"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    compatible_types: Mapped[list] = mapped_column(ARRAY(Text), nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    parameters: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    body_template: Mapped[str] = mapped_column(Text, nullable=False)


class ModelValidatorTemplateModel(Base):
    """Model validator template definition (system-seeded catalogue).

    :ivar id: Unique identifier for the template.
    :ivar name: Template display name.
    :ivar description: Template description.
    :ivar mode: Validator mode (before, after).
    :ivar parameters: Template parameter definitions (JSONB array).
    :ivar field_mappings: Field mapping definitions (JSONB array).
    :ivar body_template: Jinja2 template for the function body.
    """

    __tablename__ = "model_validator_templates"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    parameters: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    field_mappings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    body_template: Mapped[str] = mapped_column(Text, nullable=False)


class ApiModel(Base):
    """API definition containing endpoints.

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

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    namespace_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("namespaces.id"), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    base_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    server_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    user: Mapped["UserModel"] = relationship(back_populates="apis")
    namespace: Mapped["Namespace"] = relationship(back_populates="apis")
    endpoints: Mapped[list["ApiEndpoint"]] = relationship(
        back_populates="api", cascade="all, delete-orphan"
    )
    generations: Mapped[list["GenerationModel"]] = relationship(
        cascade="all, delete-orphan"
    )


class FieldModel(Base):
    """Field definition used in object compositions.

    :ivar id: Unique identifier for the field.
    :ivar namespace_id: Reference to the containing namespace.
    :ivar user_id: Owner user ID from Clerk.
    :ivar name: Field name (will become Pydantic field name).
    :ivar type_id: Reference to the field's type definition.
    :ivar description: Field description.
    :ivar default_value: Default value expression (Python code).
    """

    __tablename__ = "fields"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    namespace_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("namespaces.id"), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    type_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("types.id"), nullable=False, index=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    container: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)

    __table_args__ = (
        CheckConstraint("container IN ('List')", name="ck_fields_container"),
    )

    # Relationships
    user: Mapped["UserModel"] = relationship(back_populates="fields")
    namespace: Mapped["Namespace"] = relationship(back_populates="fields")
    field_type: Mapped["TypeModel"] = relationship(back_populates="fields")
    object_associations: Mapped[list["ObjectFieldAssociation"]] = relationship(
        back_populates="field"
    )
    constraint_values: Mapped[list["FieldConstraintValueAssociation"]] = relationship(
        back_populates="field", cascade="all, delete-orphan"
    )
    validators: Mapped[list["AppliedFieldValidatorModel"]] = relationship(
        back_populates="field",
        cascade="all, delete-orphan",
        order_by="AppliedFieldValidatorModel.position",
    )


class AppliedFieldValidatorModel(Base):
    """Applied field validator referencing a template.

    :ivar id: Unique identifier for the applied validator.
    :ivar field_id: Reference to the parent field.
    :ivar template_id: Reference to the field validator template.
    :ivar parameters: User-configured template parameter values.
    :ivar position: Display/execution order position.
    """

    __tablename__ = "applied_field_validators"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    field_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("fields.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    template_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("field_validator_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parameters: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    position: Mapped[int] = mapped_column(default=0, nullable=False)

    # Relationships
    field: Mapped["FieldModel"] = relationship(back_populates="validators")
    template: Mapped["FieldValidatorTemplateModel"] = relationship()


class ObjectDefinition(Base):
    """Object definition composed of field references.

    :ivar id: Unique identifier for the object.
    :ivar namespace_id: Reference to the containing namespace.
    :ivar user_id: Owner user ID from Clerk.
    :ivar name: Object name (will become Pydantic model class name).
    :ivar description: Object description.
    """

    __tablename__ = "objects"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    namespace_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("namespaces.id"), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    user: Mapped["UserModel"] = relationship(back_populates="objects")
    namespace: Mapped["Namespace"] = relationship(back_populates="objects")
    field_associations: Mapped[list["ObjectFieldAssociation"]] = relationship(
        back_populates="object", cascade="all, delete-orphan"
    )
    validators: Mapped[list["AppliedModelValidatorModel"]] = relationship(
        back_populates="object",
        cascade="all, delete-orphan",
        order_by="AppliedModelValidatorModel.position",
    )


class ObjectFieldAssociation(Base):
    """Association between objects and fields with optional flag.

    :ivar id: Unique identifier for the association.
    :ivar object_id: Reference to the parent object.
    :ivar field_id: Reference to the field.
    :ivar optional: Whether this field is optional in the object (default False = required).
    :ivar position: Order position for field display.
    """

    __tablename__ = "fields_on_objects"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    object_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("objects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("fields.id"), nullable=False, index=True
    )
    optional: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    position: Mapped[int] = mapped_column(default=0, nullable=False)
    is_pk: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    object: Mapped["ObjectDefinition"] = relationship(
        back_populates="field_associations"
    )
    field: Mapped["FieldModel"] = relationship(back_populates="object_associations")


class AppliedModelValidatorModel(Base):
    """Applied model validator referencing a template.

    :ivar id: Unique identifier for the applied validator.
    :ivar object_id: Reference to the parent object.
    :ivar template_id: Reference to the model validator template.
    :ivar parameters: User-configured template parameter values.
    :ivar field_mappings: Maps template field mapping keys to actual field names.
    :ivar position: Display/execution order position.
    """

    __tablename__ = "applied_model_validators"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    object_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("objects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    template_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("model_validator_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parameters: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    field_mappings: Mapped[dict] = mapped_column(JSONB, nullable=False)
    position: Mapped[int] = mapped_column(default=0, nullable=False)

    # Relationships
    object: Mapped["ObjectDefinition"] = relationship(back_populates="validators")
    template: Mapped["ModelValidatorTemplateModel"] = relationship()


class FieldConstraintValueAssociation(Base):
    """Association between a field constraint and a field with an optional parameter value.

    :ivar id: Unique identifier for the association.
    :ivar constraint_id: Reference to the field constraint.
    :ivar field_id: Reference to the field.
    :ivar value: Parameter value for the constraint (null for parameterless constraints).
    """

    __tablename__ = "applied_constraints"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    constraint_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("field_constraints.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("fields.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    value: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    constraint: Mapped["FieldConstraintModel"] = relationship()
    field: Mapped["FieldModel"] = relationship(back_populates="constraint_values")


class ApiEndpoint(Base):
    """API endpoint definition.

    :ivar id: Unique identifier for the endpoint.
    :ivar api_id: Reference to the parent API.
    :ivar method: HTTP method (GET, POST, PUT, PATCH, DELETE).
    :ivar path: URL path with optional parameters in {braces}.
    :ivar description: Endpoint description for OpenAPI spec.
    :ivar tag_name: Optional tag name for grouping endpoints in OpenAPI spec.
    :ivar path_params: Path parameters as JSONB list of {name, fieldId} dicts.
    :ivar query_params_object_id: Optional reference to Object for query parameters.
    :ivar request_body_object_id: Optional reference to Object for request body.
    :ivar response_body_object_id: Optional reference to Object for response body.
    :ivar use_envelope: Whether to wrap response in standard envelope.
    :ivar response_shape: Response shape (object or list).
    """

    __tablename__ = "api_endpoints"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    api_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("apis.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    method: Mapped[str] = mapped_column(Text, nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    tag_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    path_params: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    query_params_object_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("objects.id"), nullable=True
    )
    request_body_object_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("objects.id"), nullable=True
    )
    response_body_object_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("objects.id"), nullable=True
    )
    use_envelope: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    response_shape: Mapped[str] = mapped_column(Text, default="object", nullable=False)

    # Relationships
    api: Mapped["ApiModel"] = relationship(back_populates="endpoints")
    query_params_object: Mapped["ObjectDefinition | None"] = relationship(
        foreign_keys=[query_params_object_id]
    )
    request_body_object: Mapped["ObjectDefinition | None"] = relationship(
        foreign_keys=[request_body_object_id]
    )
    response_body_object: Mapped["ObjectDefinition | None"] = relationship(
        foreign_keys=[response_body_object_id]
    )
