<%doc>
- Template Parameters:
- orm_models: list[TemplateORMModel]
- association_tables: list[dict] - many_to_many association table definitions
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
        sa.Column("${field.name}", ${sa_type}${"" if not field.autoincrement else ", autoincrement=True"}${"" if not field.foreign_key else f', sa.ForeignKey("{field.foreign_key}")'}, nullable=${"True" if field.nullable and not field.primary_key else "False"}),
% endfor
        sa.PrimaryKeyConstraint(${", ".join(f'"{f.name}"' for f in model.fields if f.primary_key)}),
    )
% endfor
% for assoc in association_tables:
    op.create_table(
        "${assoc["name"]}",
        sa.Column("${assoc["left_fk_col"]}", sa.ForeignKey("${assoc["left_table"]}.${assoc["left_pk"]}"), nullable=False),
        sa.Column("${assoc["right_fk_col"]}", sa.ForeignKey("${assoc["right_table"]}.${assoc["right_pk"]}"), nullable=False),
        sa.PrimaryKeyConstraint("${assoc["left_fk_col"]}", "${assoc["right_fk_col"]}"),
    )
% endfor


def downgrade() -> None:
% for assoc in list(reversed(association_tables)):
    op.drop_table("${assoc["name"]}")
% endfor
% for model in list(reversed(orm_models)):
    op.drop_table("${model.table_name}")
% endfor
