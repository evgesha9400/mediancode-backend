"""Pydantic models used by the Mako templates that generate the FastAPI code."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel


class TemplateValidator(BaseModel):
    """Validator definition for template rendering."""

    name: str
    params: Dict[str, Any] | None = None


class TemplateField(BaseModel):
    """Field definition for template rendering."""

    type: str
    name: str
    required: bool
    description: str | None = None
    default_value: str | None = None
    validators: List[TemplateValidator] = []


class TemplateModel(BaseModel):
    """Generic model definition used by rendered templates."""

    name: str
    fields: List[TemplateField]
    description: str | None = None


class TemplateQueryParam(BaseModel):
    """Query parameter definition for template rendering."""

    camel_name: str
    snake_name: str
    type: str
    title: str
    required: bool
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
    request_model: Optional[str]
    response_placeholders: Optional[Dict[str, Any]]
    query_params: List[TemplateQueryParam]
    path_params: List[TemplatePathParam]
    tag: str | None = None
    description: str | None = None
    use_envelope: bool = True
    response_shape: Literal["object", "list"] = "object"


class TemplateAPIConfig(BaseModel):
    """Configuration for template rendering."""

    healthcheck: Optional[str]
    response_placeholders: bool
    format_code: bool = True


class TemplateAPI(BaseModel):
    """Root API definition for template rendering."""

    snake_name: str
    camel_name: str
    kebab_name: str
    spaced_name: str
    version: str
    author: str
    description: str
    models: List[TemplateModel]
    views: List[TemplateView]
    tags: List[TemplateTag] = []
    config: TemplateAPIConfig
