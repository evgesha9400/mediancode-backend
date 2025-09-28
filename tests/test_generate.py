import json
from pathlib import Path
from unittest import TestCase

from src.api_craft.main import generate_fastapi
from src.api_craft.models.input import InputAPI

DATA_PATH = Path(__file__).parent / "data"
OUTPUT_PATH = Path(__file__).parent / "output"


class TestGenerateItemsAPI(TestCase):
    def _get_api_data(self) -> InputAPI:
        """Load API configuration from JSON file."""
        json_path = DATA_PATH / "items_api_input.json"
        with open(json_path, "r") as f:
            api_data = json.load(f)
        return InputAPI.model_validate(api_data)

    def test_generate(self):
        generate_fastapi(self._get_api_data(), path=OUTPUT_PATH)

    def test_generate_dry_run(self):
        generate_fastapi(self._get_api_data(), dry_run=True)


# class TestGenerateMedianCodeAPI(TestCase):
#     def _get_api_data(self) -> InputAPI:
#         """Load API configuration from JSON file."""
#         json_path = DATA_PATH / "median_code_api_input.json"
#         with open(json_path, "r") as f:
#             api_data = json.load(f)
#         return InputAPI.model_validate(api_data)

#     def test_generate_dry_run(self):
#         """Test dry run generation of the Median Code API."""
#         generate_fastapi(self._get_api_data(), dry_run=True)

#     def test_generate(self):
#         """Test actual generation of the Median Code API."""
#         generate_fastapi(self._get_api_data(), path=OUTPUT_PATH)
