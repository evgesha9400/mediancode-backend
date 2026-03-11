<%doc>
- Template Parameters:
- orm_models: list[TemplateORMModel]
- imports: list[str] - SQLAlchemy column type names
</%doc>\
<%
sa_imports = sorted(set(imports))
all_types = {f.python_type.replace(" | None", "") for m in orm_models for f in m.fields}
stdlib_modules = sorted({t.split(".")[0] for t in all_types if "." in t})
pydantic_types = sorted({t for t in all_types if t in ("EmailStr", "HttpUrl")})
%>\
% for mod in stdlib_modules:
import ${mod}
% endfor
% if stdlib_modules:

% endif
% if pydantic_types:
from pydantic import ${', '.join(pydantic_types)}

% endif
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
    if field.uuid_default:
        parts.append("default=uuid.uuid4")
    if field.nullable and not field.primary_key:
        parts.append("nullable=True")
%>\
    ${field.name}: Mapped[${field.python_type}] = mapped_column(${', '.join(parts)})
% endfor
% endfor
