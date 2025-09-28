from pydantic import BaseModel



class CreateItem(BaseModel):
    name: str 


class UpdateItem(BaseModel):
    name: str 
