from fastapi import APIRouter
import path
import query
import requests
import responses


api_router = APIRouter()

 
@api_router.get(
    path="/items/{item_id}",
    response_model=responses.GetItem
)
async def get_item(
    item_id: path.ItemId,
):
    # TODO: implement your view
    
    return responses.GetItem(
        id=1,
        name='example 2',
    )
    


 
@api_router.get(
    path="/items",
    response_model=responses.ListItems
)
async def list_items(
    limit: query.Limit = None,
    offset: query.Offset = None,
):
    # TODO: implement your view
    
    return responses.ListItems(
        items=[{'id': 1, 'name': 'example 1'}, {'id': 2, 'name': 'example 2'}],
    )
    


 
@api_router.post(
    path="/items",
    response_model=responses.CreateItem
)
async def create_item(
    request: requests.CreateItem,
):
    # TODO: implement your view
    
    return responses.CreateItem(
        id=1,
        name='example 2',
    )
    


 
@api_router.put(
    path="/items/{item_id}",
    response_model=responses.UpdateItem
)
async def update_item(
    item_id: path.ItemId,
    request: requests.UpdateItem,
):
    # TODO: implement your view
    
    return responses.UpdateItem(
        id=1,
        name='example 2',
    )
    


 
@api_router.delete(
    path="/items/{item_id}",
    response_model=responses.DeleteItem
)
async def delete_item(
    item_id: path.ItemId,
):
    # TODO: implement your view
    
    return responses.DeleteItem(
        id=1,
        name='example 2',
    )
    
