"""Add users table

Revision ID: c2d3e4f5g6h7
Revises: b1a2c3d4e5f6
Create Date: 2026-02-18 00:00:00.000000
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c2d3e4f5g6h7"
down_revision: str | None = "b1a2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("clerk_id", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("first_name", sa.Text(), nullable=True),
        sa.Column("last_name", sa.Text(), nullable=True),
        sa.Column("username", sa.Text(), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column(
            "credits_remaining",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "credits_used",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_clerk_id"), "users", ["clerk_id"], unique=True)

    # Backfill users from existing namespaces
    op.execute(
        """
        INSERT INTO users (id, clerk_id, credits_remaining, credits_used, created_at, updated_at)
        SELECT gen_random_uuid(), user_id, 0, 0, NOW(), NOW()
        FROM namespaces
        WHERE user_id IS NOT NULL
        GROUP BY user_id
        ON CONFLICT (clerk_id) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_users_clerk_id"), table_name="users")
    op.drop_table("users")
