"""Pydantic models used by the Mako templates that generate the FastAPI code."""

from typing import Any

from pydantic import BaseModel

from api_craft.models.enums import ResponseShape, ValidatorMode


class TemplateValidator(BaseModel):
    """Validator definition for template rendering."""

    name: str
    params: dict[str, Any] | None = None


class TemplateResolvedFieldValidator(BaseModel):
    """Resolved field validator for template rendering."""

    function_name: str
    mode: ValidatorMode
    function_body: str


class TemplateResolvedModelValidator(BaseModel):
    """Resolved model validator for template rendering."""

    function_name: str
    mode: ValidatorMode
    function_body: str


class TemplateField(BaseModel):
    """Field definition for template rendering."""

    type: str
    name: str
    optional: bool
    description: str | None = None
    default_value: str | None = None
    validators: list[TemplateValidator] = []
    field_validators: list[TemplateResolvedFieldValidator] = []
    pk: bool = False


class TemplateModel(BaseModel):
    """Generic model definition used by rendered templates."""

    name: str
    fields: list[TemplateField]
    description: str | None = None
    model_validators: list[TemplateResolvedModelValidator] = []


class TemplateQueryParam(BaseModel):
    """Query parameter definition for template rendering."""

    camel_name: str
    snake_name: str
    type: str
    title: str
    optional: bool
    description: str | None = None


class TemplatePathParam(BaseModel):
    """Path parameter definition for template rendering."""

    snake_name: str
    camel_name: str
    type: str
    title: str
    description: str | None = None


class TemplateTag(BaseModel):
    """Tag definition for OpenAPI documentation."""

    name: str
    description: str | None = None


class TemplateView(BaseModel):
    """View (endpoint) definition for template rendering."""

    snake_name: str
    camel_name: str
    path: str
    method: str
    response_model: str | None = None
    request_model: str | None
    response_placeholders: dict[str, Any] | None
    query_params: list[TemplateQueryParam]
    path_params: list[TemplatePathParam]
    tag: str | None = None
    description: str | None = None
    use_envelope: bool = True
    response_shape: ResponseShape = "object"


class TemplateAPIConfig(BaseModel):
    """Configuration for template rendering."""

    healthcheck: str | None
    response_placeholders: bool


class TemplateORMField(BaseModel):
    """ORM field definition for template rendering."""

    name: str
    python_type: str
    column_type: str
    primary_key: bool = False
    nullable: bool = False
    autoincrement: bool = False
    uuid_default: bool = False
    foreign_key: str | None = None


class TemplateRelationship(BaseModel):
    """Relationship definition for ORM template rendering."""

    name: str
    target_model: str
    target_class_name: str
    cardinality: str
    is_inferred: bool = False
    fk_column: str | None = None
    association_table: str | None = None


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


class TemplateAPI(BaseModel):
    """Root API definition for template rendering."""

    snake_name: str
    camel_name: str
    kebab_name: str
    spaced_name: str
    version: str
    author: str
    description: str
    app_port: int = 8001
    models: list[TemplateModel]
    views: list[TemplateView]
    tags: list[TemplateTag] = []
    config: TemplateAPIConfig
    orm_models: list[TemplateORMModel] = []
    database_config: TemplateDatabaseConfig | None = None
