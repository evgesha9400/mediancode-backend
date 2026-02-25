"""Pydantic models used by the Mako templates that generate the FastAPI code."""

from typing import Any, Literal

from pydantic import BaseModel


class TemplateValidator(BaseModel):
    """Validator definition for template rendering."""

    name: str
    params: dict[str, Any] | None = None


class TemplateResolvedFieldValidator(BaseModel):
    """Resolved field validator for template rendering."""

    function_name: str
    mode: str
    function_body: str


class TemplateResolvedModelValidator(BaseModel):
    """Resolved model validator for template rendering."""

    function_name: str
    mode: str
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
    response_model: str
    request_model: str | None
    response_placeholders: dict[str, Any] | None
    query_params: list[TemplateQueryParam]
    path_params: list[TemplatePathParam]
    tag: str | None = None
    description: str | None = None
    use_envelope: bool = True
    response_shape: Literal["object", "list"] = "object"


class TemplateAPIConfig(BaseModel):
    """Configuration for template rendering."""

    healthcheck: str | None
    response_placeholders: bool
    format_code: bool = True
    generate_swagger: bool = True


class TemplateAPI(BaseModel):
    """Root API definition for template rendering."""

    snake_name: str
    camel_name: str
    kebab_name: str
    spaced_name: str
    version: str
    author: str
    description: str
    models: list[TemplateModel]
    views: list[TemplateView]
    tags: list[TemplateTag] = []
    config: TemplateAPIConfig
