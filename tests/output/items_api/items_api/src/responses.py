from pydantic import BaseModel
from typing import List


class GetItem(BaseModel):
    id: int 
    name: str 


class ListItems(BaseModel):
    items: List[GetItem] 


class CreateItem(BaseModel):
    id: int 
    name: str 


class UpdateItem(BaseModel):
    id: int 
    name: str 


class DeleteItem(BaseModel):
    id: int 
    name: str 
