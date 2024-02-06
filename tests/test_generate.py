from unittest import TestCase
from models.input import InputAPI
from main import generate_fastapi


class TestGenerateFastAPI(TestCase):
    def test_api(self) -> InputAPI:
        test_api = {
            "name": "PetStoreAPI",
            "version": "1.0",
            "views": [
                {
                    "name": "ListPets",
                    "path": "/pets",
                    "method": "GET",
                    "response": {
                        "name": "PetsResponse",
                        "fields": [
                            {"type": "list", "name": "pets", "required": True}
                        ]
                    },
                    "response_codes": [200]
                },
                {
                    "name": "CreatePet",
                    "path": "/pets",
                    "method": "POST",
                    "request": {
                        "name": "PetRequest",
                        "fields": [
                            {"type": "str", "name": "name", "required": True},
                            {"type": "str", "name": "tag", "required": False}
                        ]
                    },
                    "response": {
                        "name": "PetResponse",
                        "fields": [
                            {"type": "str", "name": "id", "required": True},
                            {"type": "str", "name": "name", "required": True},
                            {"type": "str", "name": "tag", "required": False}
                        ]
                    },
                    "response_codes": [200, 201]
                }
            ]
        }
        return InputAPI.model_validate(test_api)

    def test_generate(self):
        generate_fastapi(self.test_api())

    def test_generate_dry_run(self):
        generate_fastapi(self.test_api(), dry_run=True)
