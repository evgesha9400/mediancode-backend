"""Unified field model

Create CTI tables (object_members, scalar_members, relationship_members),
migrate data from fields_on_objects and object_relationships, then rename
old tables to *_old.

Revision ID: c3d4e5f6a7b8
Revises: b1a2c3d4e5f6
Create Date: 2026-03-25 00:00:00.000000
"""

from collections.abc import Sequence
import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from api_craft.models.enums import RelationshipKind, check_constraint_sql

logger = logging.getLogger("alembic.runtime.migration")

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b1a2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# New FieldRole values (fk removed)
_FIELD_ROLE_SQL = (
    "role IN ('pk', 'writable', 'write_only', 'read_only', "
    "'created_timestamp', 'updated_timestamp', 'generated_uuid')"
)


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Create new CTI tables
    # ------------------------------------------------------------------
    op.create_table(
        "object_members",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("member_type", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["object_id"], ["objects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_id", "name", name="uq_object_members_object_name"),
        sa.UniqueConstraint(
            "object_id",
            "position",
            name="uq_object_members_object_position",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.CheckConstraint(
            "member_type IN ('scalar', 'relationship')",
            name="ck_object_members_member_type",
        ),
    )
    op.create_index(
        "ix_object_members_object_id",
        "object_members",
        ["object_id"],
        unique=False,
    )

    op.create_table(
        "scalar_members",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("field_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column(
            "is_nullable",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("default_value", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["id"], ["object_members.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["field_id"], ["fields.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(_FIELD_ROLE_SQL, name="ck_scalar_members_role"),
    )
    op.create_index(
        "ix_scalar_members_field_id",
        "scalar_members",
        ["field_id"],
        unique=False,
    )

    op.create_table(
        "relationship_members",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("target_object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("inverse_name", sa.Text(), nullable=False),
        sa.Column(
            "required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.ForeignKeyConstraint(["id"], ["object_members.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["target_object_id"], ["objects.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            check_constraint_sql("kind", RelationshipKind),
            name="ck_relationship_members_kind",
        ),
    )
    op.create_index(
        "ix_relationship_members_target_object_id",
        "relationship_members",
        ["target_object_id"],
        unique=False,
    )
    op.create_index(
        "ix_relationship_members_inverse_unique",
        "relationship_members",
        ["target_object_id", "inverse_name"],
        unique=True,
    )

    # ------------------------------------------------------------------
    # 2. Migrate scalar data: fields_on_objects -> object_members + scalar_members
    # ------------------------------------------------------------------
    conn = op.get_bind()

    # Read all non-FK field associations, ordered by object then position
    foa_rows = conn.execute(
        sa.text(
            "SELECT id, object_id, field_id, role, nullable, position, default_value "
            "FROM fields_on_objects "
            "WHERE role != 'fk' "
            "ORDER BY object_id, position"
        )
    ).fetchall()

    for row in foa_rows:
        foa_id, object_id, field_id, role, nullable, position, default_value = row

        # Look up the field name from the fields table
        field_name_row = conn.execute(
            sa.text("SELECT name FROM fields WHERE id = :fid"),
            {"fid": field_id},
        ).fetchone()
        field_name = field_name_row[0] if field_name_row else f"field_{position}"

        # Insert base object_member row
        conn.execute(
            sa.text(
                "INSERT INTO object_members (id, object_id, name, position, member_type) "
                "VALUES (:id, :object_id, :name, :position, 'scalar')"
            ),
            {
                "id": foa_id,
                "object_id": object_id,
                "name": field_name,
                "position": position,
            },
        )

        # Insert child scalar_member row
        conn.execute(
            sa.text(
                "INSERT INTO scalar_members (id, field_id, role, is_nullable, default_value) "
                "VALUES (:id, :field_id, :role, :is_nullable, :default_value)"
            ),
            {
                "id": foa_id,
                "field_id": field_id,
                "role": role,
                "is_nullable": nullable,
                "default_value": default_value,
            },
        )

    logger.info("Migrated %d scalar members from fields_on_objects", len(foa_rows))

    # ------------------------------------------------------------------
    # 3. Migrate relationship data: object_relationships -> object_members
    #    + relationship_members
    # ------------------------------------------------------------------
    # Track the max scalar position per object for relationship position assignment
    max_positions: dict[str, int] = {}
    for row in foa_rows:
        _foa_id, object_id, _field_id, _role, _nullable, position, _dv = row
        obj_key = str(object_id)
        if obj_key not in max_positions or position > max_positions[obj_key]:
            max_positions[obj_key] = position

    # Read all non-inferred relationships
    rel_rows = conn.execute(
        sa.text(
            "SELECT id, source_object_id, target_object_id, name, cardinality, "
            "       inverse_id, position "
            "FROM object_relationships "
            "WHERE is_inferred = false "
            "ORDER BY source_object_id, position"
        )
    ).fetchall()

    migrated_count = 0
    for row in rel_rows:
        (
            rel_id,
            source_object_id,
            target_object_id,
            rel_name,
            cardinality,
            inverse_id,
            _pos,
        ) = row

        # Determine the new kind and the owning object for the new member
        if cardinality == "references":
            # References row: flip to the inverse's perspective.
            # The inverse (inferred) row's source object becomes the new member's owner.
            if inverse_id is None:
                logger.error(
                    "References relationship %s has no inverse_id — skipping. "
                    "Manual resolution required.",
                    rel_id,
                )
                continue

            inverse_row = conn.execute(
                sa.text(
                    "SELECT source_object_id, target_object_id, name, cardinality "
                    "FROM object_relationships "
                    "WHERE id = :inv_id"
                ),
                {"inv_id": inverse_id},
            ).fetchone()

            if inverse_row is None:
                logger.error(
                    "Inverse %s for references relationship %s not found — skipping.",
                    inverse_id,
                    rel_id,
                )
                continue

            inv_source_id, _inv_target_id, inv_name, inv_cardinality = inverse_row

            # The inverse's cardinality determines the new kind
            if inv_cardinality == "has_many":
                new_kind = "one_to_many"
            elif inv_cardinality == "has_one":
                new_kind = "one_to_one"
            else:
                logger.error(
                    "Unexpected inverse cardinality '%s' for references row %s — skipping.",
                    inv_cardinality,
                    rel_id,
                )
                continue

            # The inverse's source object owns the new relationship member.
            # The inverse's name becomes the new relationship name.
            # The references row's name becomes the new inverse_name.
            new_object_id = inv_source_id
            new_name = inv_name
            new_inverse_name = rel_name
            new_target_object_id = (
                source_object_id  # the references row's source is the target
            )

        elif cardinality == "has_many":
            new_kind = "one_to_many"
            new_object_id = source_object_id
            new_name = rel_name
            new_target_object_id = target_object_id

            # Derive inverse_name from the inferred inverse
            if inverse_id:
                inv_name_row = conn.execute(
                    sa.text("SELECT name FROM object_relationships WHERE id = :inv_id"),
                    {"inv_id": inverse_id},
                ).fetchone()
                new_inverse_name = inv_name_row[0] if inv_name_row else None
            else:
                new_inverse_name = None

            if not new_inverse_name:
                # Fallback: lowercase source object name
                src_obj_row = conn.execute(
                    sa.text("SELECT name FROM objects WHERE id = :oid"),
                    {"oid": source_object_id},
                ).fetchone()
                new_inverse_name = src_obj_row[0].lower() if src_obj_row else "unknown"
                logger.warning(
                    "No inverse found for has_many relationship %s — "
                    "using fallback inverse_name '%s'.",
                    rel_id,
                    new_inverse_name,
                )

        elif cardinality == "has_one":
            new_kind = "one_to_one"
            new_object_id = source_object_id
            new_name = rel_name
            new_target_object_id = target_object_id

            if inverse_id:
                inv_name_row = conn.execute(
                    sa.text("SELECT name FROM object_relationships WHERE id = :inv_id"),
                    {"inv_id": inverse_id},
                ).fetchone()
                new_inverse_name = inv_name_row[0] if inv_name_row else None
            else:
                new_inverse_name = None

            if not new_inverse_name:
                src_obj_row = conn.execute(
                    sa.text("SELECT name FROM objects WHERE id = :oid"),
                    {"oid": source_object_id},
                ).fetchone()
                new_inverse_name = src_obj_row[0].lower() if src_obj_row else "unknown"
                logger.warning(
                    "No inverse found for has_one relationship %s — "
                    "using fallback inverse_name '%s'.",
                    rel_id,
                    new_inverse_name,
                )

        elif cardinality == "many_to_many":
            new_kind = "many_to_many"
            new_object_id = source_object_id
            new_name = rel_name
            new_target_object_id = target_object_id

            if inverse_id:
                inv_name_row = conn.execute(
                    sa.text("SELECT name FROM object_relationships WHERE id = :inv_id"),
                    {"inv_id": inverse_id},
                ).fetchone()
                new_inverse_name = inv_name_row[0] if inv_name_row else None
            else:
                new_inverse_name = None

            if not new_inverse_name:
                src_obj_row = conn.execute(
                    sa.text("SELECT name FROM objects WHERE id = :oid"),
                    {"oid": source_object_id},
                ).fetchone()
                new_inverse_name = src_obj_row[0].lower() if src_obj_row else "unknown"
                logger.warning(
                    "No inverse found for many_to_many relationship %s — "
                    "using fallback inverse_name '%s'.",
                    rel_id,
                    new_inverse_name,
                )
        else:
            logger.error(
                "Unknown cardinality '%s' for relationship %s — skipping.",
                cardinality,
                rel_id,
            )
            continue

        # Compute position: start after the last scalar member
        obj_key = str(new_object_id)
        current_max = max_positions.get(obj_key, -1)
        new_position = current_max + 1
        max_positions[obj_key] = new_position

        # Insert base object_member row
        conn.execute(
            sa.text(
                "INSERT INTO object_members (id, object_id, name, position, member_type) "
                "VALUES (:id, :object_id, :name, :position, 'relationship')"
            ),
            {
                "id": rel_id,
                "object_id": new_object_id,
                "name": new_name,
                "position": new_position,
            },
        )

        # Insert child relationship_member row
        conn.execute(
            sa.text(
                "INSERT INTO relationship_members "
                "(id, target_object_id, kind, inverse_name, required) "
                "VALUES (:id, :target_object_id, :kind, :inverse_name, :required)"
            ),
            {
                "id": rel_id,
                "target_object_id": new_target_object_id,
                "kind": new_kind,
                "inverse_name": new_inverse_name,
                "required": True,
            },
        )
        migrated_count += 1

    logger.info(
        "Migrated %d relationship members from object_relationships", migrated_count
    )

    # ------------------------------------------------------------------
    # 4. Data integrity check
    # ------------------------------------------------------------------
    total_members = conn.execute(
        sa.text("SELECT count(*) FROM object_members")
    ).scalar()
    total_scalars = conn.execute(
        sa.text("SELECT count(*) FROM scalar_members")
    ).scalar()
    total_rels = conn.execute(
        sa.text("SELECT count(*) FROM relationship_members")
    ).scalar()

    if total_members != total_scalars + total_rels:
        raise RuntimeError(
            f"Integrity check failed: object_members={total_members}, "
            f"scalar_members={total_scalars}, relationship_members={total_rels}. "
            f"Expected {total_members} == {total_scalars} + {total_rels}."
        )

    # Check no orphaned child rows
    orphan_scalars = conn.execute(
        sa.text(
            "SELECT count(*) FROM scalar_members s "
            "LEFT JOIN object_members m ON s.id = m.id "
            "WHERE m.id IS NULL"
        )
    ).scalar()
    orphan_rels = conn.execute(
        sa.text(
            "SELECT count(*) FROM relationship_members r "
            "LEFT JOIN object_members m ON r.id = m.id "
            "WHERE m.id IS NULL"
        )
    ).scalar()

    if orphan_scalars or orphan_rels:
        raise RuntimeError(
            f"Orphaned child rows: scalar={orphan_scalars}, relationship={orphan_rels}"
        )

    logger.info(
        "Integrity check passed: %d total members (%d scalar, %d relationship)",
        total_members,
        total_scalars,
        total_rels,
    )

    # ------------------------------------------------------------------
    # 5. Rename old tables (preserve data for rollback safety)
    # ------------------------------------------------------------------
    op.rename_table("fields_on_objects", "fields_on_objects_old")
    op.rename_table("object_relationships", "object_relationships_old")


def downgrade() -> None:
    # Restore old tables from _old names
    op.rename_table("fields_on_objects_old", "fields_on_objects")
    op.rename_table("object_relationships_old", "object_relationships")

    # Drop new tables in reverse dependency order
    op.drop_index(
        "ix_relationship_members_inverse_unique",
        table_name="relationship_members",
    )
    op.drop_index(
        "ix_relationship_members_target_object_id",
        table_name="relationship_members",
    )
    op.drop_table("relationship_members")

    op.drop_index("ix_scalar_members_field_id", table_name="scalar_members")
    op.drop_table("scalar_members")

    op.drop_index("ix_object_members_object_id", table_name="object_members")
    op.drop_table("object_members")
