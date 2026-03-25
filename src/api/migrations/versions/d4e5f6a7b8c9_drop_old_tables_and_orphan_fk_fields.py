"""Drop legacy tables and orphaned FK fields

Drop fields_on_objects_old and object_relationships_old tables.
Delete orphaned FieldModel rows that only served as FK fields.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-03-25 01:00:00.000000
"""

from collections.abc import Sequence
import logging

from alembic import op
import sqlalchemy as sa

logger = logging.getLogger("alembic.runtime.migration")

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # ------------------------------------------------------------------
    # 1. Delete orphaned FK fields
    # ------------------------------------------------------------------
    # FK fields are identified by having role='fk' in the old
    # fields_on_objects_old table and no remaining scalar_members reference.
    orphan_count = conn.execute(
        sa.text(
            "DELETE FROM fields "
            "WHERE id IN ("
            "  SELECT DISTINCT f.id FROM fields f "
            "  INNER JOIN fields_on_objects_old foa ON f.id = foa.field_id "
            "  WHERE foa.role = 'fk' "
            "  AND NOT EXISTS ("
            "    SELECT 1 FROM scalar_members sm WHERE sm.field_id = f.id"
            "  )"
            ")"
        )
    ).rowcount
    logger.info("Deleted %d orphaned FK field rows", orphan_count)

    # ------------------------------------------------------------------
    # 2. Drop old tables
    # ------------------------------------------------------------------
    op.drop_table("object_relationships_old")
    op.drop_table("fields_on_objects_old")

    logger.info("Dropped fields_on_objects_old and object_relationships_old tables")


def downgrade() -> None:
    # Non-reversible: the old data has been dropped.
    # To restore, re-run the unified_field_model migration downgrade first.
    raise RuntimeError(
        "Cannot reverse drop of legacy tables. "
        "Downgrade the unified_field_model migration (c3d4e5f6a7b8) instead."
    )
