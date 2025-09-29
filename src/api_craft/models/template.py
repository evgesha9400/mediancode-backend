"""This file contains the pydantic models for the Jinja2 templates that will be used to generate the FastAPI code."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class TemplateField(BaseModel):
    type: str
    name: str
    required: bool


class TemplateModel(BaseModel):
    """Generic model definition used by rendered templates."""

    name: str
    fields: List[TemplateField]


class TemplateQueryParam(BaseModel):
    camel_name: str
    snake_name: str
    type: str
    title: str
    required: bool


class TemplatePathParam(BaseModel):
    snake_name: str
    camel_name: str
    type: str
    title: str


class TemplateView(BaseModel):
    snake_name: str
    camel_name: str
    path: str
    method: str
    response_model: str
    request_model: Optional[str]
    response_placeholders: Optional[Dict[str, Any]]
    query_params: List[TemplateQueryParam]
    path_params: List[TemplatePathParam]


class TemplateAPIConfig(BaseModel):
    healthcheck: Optional[str]
    response_placeholders: bool


class TemplateAPI(BaseModel):
    snake_name: str
    camel_name: str
    spaced_name: str
    version: str
    author: str
    description: str
    models: List[TemplateModel]
    views: List[TemplateView]
    config: TemplateAPIConfig
