"""ORM-specific models used by Mako templates for database code generation.

These types represent database concepts (tables, columns, relationships)
that are genuinely different from the Input API models.
"""

from pydantic import BaseModel


class TemplateORMField(BaseModel):
    """ORM field definition for template rendering."""

    name: str
    python_type: str
    column_type: str
    primary_key: bool = False
    nullable: bool = False
    server_default: str | None = None
    on_update: str | None = None
    default_literal: str | None = None
    foreign_key: str | None = None


class TemplateRelationship(BaseModel):
    """Relationship definition for ORM template rendering."""

    name: str
    target_model: str
    target_class_name: str
    kind: str
    back_populates: str | None = None
    fk_column: str | None = None
    uselist: bool = True
    remote_side: str | None = None
    association_table: str | None = None
    unique_fk: bool = False


class TemplateORMModel(BaseModel):
    """ORM model (table) definition for template rendering."""

    class_name: str
    table_name: str
    source_model: str
    fields: list[TemplateORMField]
    relationships: list[TemplateRelationship] = []


class TemplateDatabaseConfig(BaseModel):
    """Database configuration for template rendering."""

    enabled: bool
    default_url: str
    db_port: int = 5433
