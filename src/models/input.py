from pydantic import BaseModel

from typing import Literal, List


SUPPORTED_TYPES = Literal['int', 'float', 'str', 'bool', 'list', 'dict', 'datetime', 'date', 'time']


class InputField(BaseModel):
    type: SUPPORTED_TYPES
    name: str
    required: bool = True


class InputModel(BaseModel):
    name: str
    fields: list[InputField]


class InputQueryParam(BaseModel):
    name: str
    type: str
    required: bool = False


class InputPathParam(BaseModel):
    name: str
    type: str


class InputView(BaseModel):
    name: str
    path: str
    method: str
    response: InputModel
    request: InputModel = None
    query_params: List[InputQueryParam] = None
    path_params: List[InputPathParam] = None
    response_codes: list[int] = [200]


class InputAPI(BaseModel):
    name: str
    version: str
    views: List[InputView]

