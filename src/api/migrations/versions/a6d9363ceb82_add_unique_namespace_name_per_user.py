"""add_unique_namespace_name_per_user

Revision ID: a6d9363ceb82
Revises: b1a2c3d4e5f6
Create Date: 2026-02-25 20:18:56.090723
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a6d9363ceb82"
down_revision: str | None = "b1a2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_namespaces_user_name", "namespaces", ["user_id", "name"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_namespaces_user_name", "namespaces", type_="unique")
