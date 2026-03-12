<%doc>
- Template Parameters:
- orm_models: list[TemplateORMModel]
</%doc>\
"""Initial migration.

Revision ID: 0001
Revises: None
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
% for model in orm_models:
    op.create_table(
        "${model.table_name}",
% for field in model.fields:
<%
    col_type = field.column_type
    sa_type = f"sa.{col_type}" if "(" in col_type else f"sa.{col_type}()"
%>\
        sa.Column("${field.name}", ${sa_type}${"" if not field.autoincrement else ", autoincrement=True"}, nullable=${"True" if field.nullable and not field.primary_key else "False"}),
% endfor
        sa.PrimaryKeyConstraint(${", ".join(f'"{f.name}"' for f in model.fields if f.primary_key)}),
    )
% endfor


def downgrade() -> None:
% for model in list(reversed(orm_models)):
    op.drop_table("${model.table_name}")
% endfor
