# src/api/models/members.py
"""CTI (Class Table Inheritance) models for unified object members.

Three tables implement a joined-table-inheritance hierarchy:
- ``object_members`` — base identity/ordering for every member
- ``scalar_members`` — child table for field-backed members
- ``relationship_members`` — child table for relationship members
"""

from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base


def _generate_uuid() -> UUID:
    """Generate a UUID for use as primary key.

    :returns: A UUID4 object.
    """
    return uuid4()


class ObjectMember(Base):
    """Base table for all object members (scalar or relationship).

    Uses SQLAlchemy joined-table inheritance with ``member_type`` as
    the polymorphic discriminator.

    :ivar id: Unique identifier for the member.
    :ivar object_id: Reference to the owning object.
    :ivar name: Member name (unique per object).
    :ivar position: Display/ordering position within the object.
    :ivar member_type: Discriminator (``'scalar'`` or ``'relationship'``).
    """

    __tablename__ = "object_members"
    __table_args__ = (
        UniqueConstraint("object_id", "name", name="uq_object_members_object_name"),
        UniqueConstraint(
            "object_id",
            "position",
            name="uq_object_members_object_position",
            deferrable=True,
            initially="DEFERRED",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=_generate_uuid
    )
    object_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("objects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    member_type: Mapped[str] = mapped_column(Text, nullable=False)

    # Back-reference to the owning object
    parent_object: Mapped["ObjectDefinition"] = relationship(  # noqa: F821
        "ObjectDefinition",
        back_populates="members",
        foreign_keys=[object_id],
    )

    __mapper_args__ = {
        "polymorphic_on": member_type,
    }


class ScalarMember(ObjectMember):
    """Child table for scalar (field-backed) members.

    :ivar id: Shared PK with ``object_members``.
    :ivar field_id: Reference to the field definition.
    :ivar role: Structural role of the field on this object.
    :ivar is_nullable: Whether the field is nullable.
    :ivar default_value: Optional literal default value.
    """

    __tablename__ = "scalar_members"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("object_members.id", ondelete="CASCADE"),
        primary_key=True,
    )
    field_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("fields.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    is_nullable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    default_value: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Eager-loadable reference to the field definition
    field: Mapped["FieldModel"] = relationship(  # noqa: F821
        "FieldModel", foreign_keys=[field_id]
    )

    __mapper_args__ = {"polymorphic_identity": "scalar"}


class RelationshipMember(ObjectMember):
    """Child table for relationship members.

    :ivar id: Shared PK with ``object_members``.
    :ivar target_object_id: Reference to the target object (RESTRICT delete).
    :ivar kind: Relationship kind (one_to_one, one_to_many, many_to_many).
    :ivar inverse_name: Name for the derived reverse field on the target.
    :ivar required: Whether the derived FK column is NOT NULL.
    """

    __tablename__ = "relationship_members"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("object_members.id", ondelete="CASCADE"),
        primary_key=True,
    )
    target_object_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("objects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    inverse_name: Mapped[str] = mapped_column(Text, nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Eager-loadable reference to the target object
    target_object: Mapped["ObjectDefinition"] = relationship(  # noqa: F821
        "ObjectDefinition", foreign_keys=[target_object_id]
    )

    __mapper_args__ = {"polymorphic_identity": "relationship"}
