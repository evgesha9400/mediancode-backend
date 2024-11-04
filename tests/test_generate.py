from unittest import TestCase

from api_craft.main import generate_fastapi
from api_craft.models.input import InputAPI


class TestGenerateFastAPI(TestCase):
    @staticmethod
    def item_response():
        return {
            "name": "Item",
            "fields": [
                {"type": "int", "name": "id", "required": True},
                {"type": "str", "name": "name", "required": True},
            ],
        }

    @staticmethod
    def items_response():
        return {
            "name": "Items",
            "fields": [{"type": "List[GetItem]", "name": "items", "required": True}],
        }

    @staticmethod
    def item_id_path_param():
        return {
            "name": "item_id",
            "type": "int",
        }

    def test_api(self) -> InputAPI:
        get_item_view = {
            "name": "GetItem",
            "path": "/items/{item_id}",
            "method": "GET",
            "tag": "Items",
            "response": self.item_response(),
            "path_params": [self.item_id_path_param()],
        }

        list_items_view = {
            "name": "ListItems",
            "path": "/items",
            "method": "GET",
            "tag": "Items",
            "query_params": [
                {"name": "limit", "type": "int", "required": False},
                {"name": "offset", "type": "int", "required": False},
            ],
            "response": self.items_response(),
        }

        create_item_view = {
            "name": "CreateItem",
            "path": "/items",
            "method": "POST",
            "response": self.item_response(),
            "request": {
                "name": "Item",
                "fields": [{"type": "str", "name": "name", "required": True}],
            },
        }

        update_item_view = {
            "name": "UpdateItem",
            "path": "/items/{item_id}",
            "method": "PUT",
            "tag": "Items",
            "response": self.item_response(),
            "request": {
                "name": "Item",
                "fields": [{"type": "str", "name": "name", "required": True}],
            },
            "path_params": [self.item_id_path_param()],
        }

        delete_item_view = {
            "name": "DeleteItem",
            "path": "/items/{item_id}",
            "tag": "Items",
            "method": "DELETE",
            "path_params": [self.item_id_path_param()],
            "response": self.item_response(),
        }

        config = {
            "healthcheck": "/healthcheck",
            "response_placeholders": True
        }

        items_api = {
            "name": "ItemsApi",
            "version": "0.1.0",
            "views": [
                get_item_view,
                list_items_view,
                create_item_view,
                update_item_view,
                delete_item_view,
            ],
            "config": config,
        }
        return InputAPI.model_validate(items_api)

    def test_generate(self):
        generate_fastapi(self.test_api(), path="/Users/evgesha/Desktop")

    def test_generate_dry_run(self):
        generate_fastapi(self.test_api(), dry_run=True)
