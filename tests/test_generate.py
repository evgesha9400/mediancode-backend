from unittest import TestCase
from models.input import InputAPI
from main import generate_fastapi
import utils
import pathlib


class TestGenerateFastAPI(TestCase):
    @staticmethod
    def item_response():
        return {
            "name": "Item",
            "fields": [
                {
                    "type": "int",
                    "name": "id",
                    "required": True
                },
                {
                    "type": "str",
                    "name": "name",
                    "required": True
                }
            ]
        }

    @staticmethod
    def items_response():
        return {
            "name": "Items",
            "fields": [
                {
                    "type": "List[GetItem]",
                    "name": "items",
                    "required": True
                }
            ]
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
            "response": self.item_response(),
            "path_params": [self.item_id_path_param()],
        }

        list_items_view = {
            "name": "ListItems",
            "path": "/items",
            "method": "GET",
            "query_params": [
                {
                    "name": "limit",
                    "type": "int",
                    "required": False
                },
                {
                    "name": "offset",
                    "type": "int",
                    "required": False
                }
            ],
            "response": self.items_response()
        }

        create_item_view = {
            "name": "CreateItem",
            "path": "/items",
            "method": "POST",
            "response": self.item_response(),
            "request": {
                "name": "Item",
                "fields": [
                    {
                        "type": "str",
                        "name": "name",
                        "required": True
                    }
                ]
            }
        }

        update_item_view = {
            "name": "UpdateItem",
            "path": "/items/{item_id}",
            "method": "PUT",
            "response": self.item_response(),
            "request": {
                "name": "Item",
                "fields": [
                    {
                        "type": "str",
                        "name": "name",
                        "required": True
                    }
                ]
            },
            "path_params": [self.item_id_path_param()],
        }

        delete_item_view = {
            "name": "DeleteItem",
            "path": "/items/{item_id}",
            "method": "DELETE",
            "path_params": [self.item_id_path_param()],
            "response": self.item_response(),
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
            ]
        }
        return InputAPI.model_validate(items_api)

    def test_generate(self):
        generate_fastapi(
            self.test_api(),
            path="/Users/evgesha/Desktop"
        )

    def test_generate_dry_run(self):
        generate_fastapi(self.test_api(), dry_run=True)



class TestUtils(TestCase):
    def test_create_project_structure(self):
        base_path = str(pathlib.Path(__file__).parent.resolve())
        structure = {
            "test": {
                "src": None,
                "develop": None,
                "tests": None
            }
        }
        utils.create_project_structure(base_path, structure)