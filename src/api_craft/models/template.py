"""This file contains the pydantic models for the Jinja2 templates that will be used to generate the FastAPI code."""

from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class TemplateField(BaseModel):
    type: str
    name: str
    required: bool


class TemplateRequest(BaseModel):
    name: str
    fields: List[TemplateField]


class TemplateResponse(BaseModel):
    name: str
    fields: List[TemplateField]
    placeholder_values: Optional[Dict[str, Any]] = None


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
    response: TemplateResponse
    request: Optional[TemplateRequest]
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
    views: List[TemplateView]
    config: TemplateAPIConfig
