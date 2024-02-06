from pydantic import BaseModel

from typing import List, Optional


class TemplateField(BaseModel):
    type: str
    name: str
    required: bool = True


class TemplateModel(BaseModel):
    name: str
    fields: list[TemplateField]


class TemplateQueryParam(BaseModel):
    name: str
    type: str
    required: bool = False


class TemplatePathParam(BaseModel):
    name: str
    type: str


class TemplateView(BaseModel):
    name: str
    path: str
    method: str
    response: TemplateModel
    request: Optional[TemplateModel] = None
    query_params: List[TemplateQueryParam] = None
    path_params: List[TemplatePathParam] = None
    response_codes: list[int] = [200]


class TemplateAPI(BaseModel):
    name: str
    version: str
    views: List[TemplateView]
