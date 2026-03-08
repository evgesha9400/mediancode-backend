<%doc>
- Template Parameters:
- orm_models: list[TemplateORMModel]
- imports: list[str] - SQLAlchemy column type names
</%doc>\
<%
has_foreign_keys = any(
    field.foreign_key
    for model in orm_models
    for field in model.fields
)
sa_imports = sorted(set(imports))
%>\
from sqlalchemy import ${', '.join(sa_imports)}
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass
% for model in orm_models:


class ${model.class_name}(Base):
    __tablename__ = "${model.table_name}"

% for field in model.fields:
<%
    parts = []
    parts.append(field.column_type)
    if field.primary_key:
        parts.append("primary_key=True")
    if field.autoincrement:
        parts.append("autoincrement=True")
    if field.foreign_key:
        on_del = f', ondelete="{field.on_delete}"' if field.on_delete else ''
        parts.append(f'ForeignKey("{field.foreign_key}"{on_del})')
    if field.nullable and not field.primary_key:
        parts.append("nullable=True")
%>\
    ${field.name}: Mapped[${field.python_type}] = mapped_column(${', '.join(parts)})
% endfor
% endfor
