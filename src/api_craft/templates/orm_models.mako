<%doc>
- Template Parameters:
- orm_models: list[TemplateORMModel]
- imports: list[str] - SQLAlchemy column type names
- association_tables: list[dict] - many_to_many association table definitions
</%doc>\
<%
sa_imports = sorted(set(imports))
all_types = {f.python_type.replace(" | None", "") for m in orm_models for f in m.fields}
stdlib_modules = sorted({t.split(".")[0] for t in all_types if "." in t})
pydantic_types = sorted({t for t in all_types if t in ("EmailStr", "HttpUrl")})
has_fk = any(f.foreign_key for m in orm_models for f in m.fields)
has_relationships = any(m.relationships for m in orm_models)
has_assoc_tables = bool(association_tables)
extra_sa = set()
if has_fk:
    extra_sa.add("ForeignKey")
if has_assoc_tables:
    extra_sa.add("Column")
    extra_sa.add("Table")
combined_sa = sorted(set(sa_imports) | extra_sa)
orm_imports = ["DeclarativeBase", "Mapped", "mapped_column"]
if has_relationships:
    orm_imports.append("relationship")
orm_imports_str = ", ".join(sorted(orm_imports))
%>\
% for mod in stdlib_modules:
import ${mod}
% endfor
% if stdlib_modules:

% endif
% if pydantic_types:
from pydantic import ${', '.join(pydantic_types)}

% endif
from sqlalchemy import ${', '.join(combined_sa)}
from sqlalchemy.orm import ${orm_imports_str}


class Base(DeclarativeBase):
    pass
% for assoc in association_tables:


${assoc["name"]} = Table(
    "${assoc["name"]}",
    Base.metadata,
    Column("${assoc["left_fk_col"]}", ForeignKey("${assoc["left_table"]}.${assoc["left_pk"]}"), primary_key=True),
    Column("${assoc["right_fk_col"]}", ForeignKey("${assoc["right_table"]}.${assoc["right_pk"]}"), primary_key=True),
)
% endfor
% for model in orm_models:


class ${model.class_name}(Base):
    __tablename__ = "${model.table_name}"

% for field in model.fields:
<%
    parts = []
    parts.append(field.column_type)
    if field.foreign_key:
        parts.append(f'ForeignKey("{field.foreign_key}")')
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
% for rel in model.relationships:
% if rel.cardinality == "references":
    ${rel.name}: Mapped["${rel.target_class_name}"] = relationship(foreign_keys=[${rel.fk_column}])
% elif rel.cardinality == "has_one":
    ${rel.name}: Mapped["${rel.target_class_name}"] = relationship(back_populates=None, uselist=False)
% elif rel.cardinality == "has_many":
    ${rel.name}: Mapped[list["${rel.target_class_name}"]] = relationship(back_populates=None)
% elif rel.cardinality == "many_to_many":
    ${rel.name}: Mapped[list["${rel.target_class_name}"]] = relationship(secondary=${rel.association_table}, back_populates=None)
% endif
% endfor
% endfor
