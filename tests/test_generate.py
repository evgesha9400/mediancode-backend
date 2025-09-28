import json
from pathlib import Path
from unittest import TestCase

from api_craft.main import generate_fastapi
from api_craft.models.input import InputAPI


class TestGenerateFastAPI(TestCase):
    def _get_api_data(self) -> InputAPI:
        """Load API configuration from JSON file."""
        json_path = Path(__file__).parent / "data" / "items_api_input.json"
        with open(json_path, "r") as f:
            api_data = json.load(f)
        return InputAPI.model_validate(api_data)

    def test_generate(self):
        generate_fastapi(self._get_api_data(), path="/Users/evgesha/Desktop")

    def test_generate_dry_run(self):
        generate_fastapi(self._get_api_data(), dry_run=True)
