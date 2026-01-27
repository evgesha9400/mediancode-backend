"""Hybrid test suite for api_craft code generation.

This test suite implements a hybrid testing approach:
1. Smoke tests - Ensure generation runs without errors
2. Syntax validation - Ensure generated Python is valid
3. Structural assertions - Verify key patterns exist
4. Field coverage tests - Verify new fields are properly handled
"""

import ast
import json
from pathlib import Path
from typing import Iterator

import pytest

from api_craft.main import APIGenerator
from api_craft.models.input import InputAPI

DATA_PATH = Path(__file__).parent / "data"
OUTPUT_PATH = Path(__file__).parent / "output"


def load_test_input(filename: str) -> InputAPI:
    """Load and validate an API input from JSON file.

    :param filename: Name of the JSON file in the data directory.
    :returns: Validated InputAPI model.
    """
    json_path = DATA_PATH / filename
    with open(json_path, "r") as f:
        api_data = json.load(f)
    return InputAPI.model_validate(api_data)


class GeneratedProject:
    """Helper class for accessing generated project files."""

    def __init__(self, project_path: Path):
        self.project_path = project_path
        self._files: dict[str, str] | None = None

    @property
    def files(self) -> dict[str, str]:
        """Lazy-load all project files as strings."""
        if self._files is None:
            self._files = {}
            for path in self.project_path.rglob("*"):
                if path.is_file():
                    rel_path = path.relative_to(self.project_path).as_posix()
                    try:
                        self._files[rel_path] = path.read_text()
                    except UnicodeDecodeError:
                        pass  # Skip binary files
        return self._files

    def get_python_files(self) -> Iterator[tuple[str, str]]:
        """Yield all Python files as (filename, content) tuples."""
        for filename, content in self.files.items():
            if filename.endswith(".py"):
                yield filename, content

    def __getitem__(self, key: str) -> str:
        """Access a file by relative path."""
        return self.files[key]

    def __contains__(self, key: str) -> bool:
        """Check if a file exists."""
        return key in self.files


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def items_api_input() -> InputAPI:
    """Load the items API test input."""
    return load_test_input("items_api_input.json")


@pytest.fixture
def user_management_api_input() -> InputAPI:
    """Load the user management API test input with all fields."""
    return load_test_input("user_management_api_input.json")


@pytest.fixture
def generated_items_api(items_api_input: InputAPI, tmp_path: Path) -> GeneratedProject:
    """Generate the items API and return the project wrapper."""
    generator = APIGenerator()
    generator.generate(items_api_input, path=str(tmp_path))
    return GeneratedProject(tmp_path / "items-api")


@pytest.fixture
def generated_user_management_api(user_management_api_input: InputAPI, tmp_path: Path) -> GeneratedProject:
    """Generate the complete API and return the project wrapper."""
    generator = APIGenerator()
    generator.generate(user_management_api_input, path=str(tmp_path))
    return GeneratedProject(tmp_path / "user-management-api")


# =============================================================================
# Smoke Tests - Generation completes without errors
# =============================================================================


class TestSmokeGeneration:
    """Smoke tests to ensure generation runs without errors."""

    def test_items_api_generates(self, generated_items_api: GeneratedProject):
        """Items API generates without errors."""
        assert generated_items_api.project_path.exists()

    def test_user_management_api_generates(self, generated_user_management_api: GeneratedProject):
        """Complete API with all fields generates without errors."""
        assert generated_user_management_api.project_path.exists()

    def test_dry_run_does_not_write_files(self, items_api_input: InputAPI, tmp_path: Path):
        """Dry run mode does not create any files."""
        generator = APIGenerator()
        generator.generate(items_api_input, path=str(tmp_path), dry_run=True)
        # Dry run should not create the project directory
        assert not (tmp_path / "items-api").exists()


# =============================================================================
# File Structure Tests - Expected files are generated
# =============================================================================


class TestFileStructure:
    """Tests to verify the correct file structure is generated."""

    EXPECTED_SRC_FILES = [
        "src/models.py",
        "src/views.py",
        "src/main.py",
    ]

    EXPECTED_PROJECT_FILES = [
        "pyproject.toml",
        "Makefile",
        "Dockerfile",
        "swagger.py",
    ]

    def test_items_api_has_expected_src_files(self, generated_items_api: GeneratedProject):
        """Items API has all expected source files."""
        for filename in self.EXPECTED_SRC_FILES:
            assert filename in generated_items_api, f"Missing file: {filename}"

    def test_items_api_has_expected_project_files(self, generated_items_api: GeneratedProject):
        """Items API has all expected project files."""
        for filename in self.EXPECTED_PROJECT_FILES:
            assert filename in generated_items_api, f"Missing file: {filename}"

    def test_user_management_api_has_expected_files(self, generated_user_management_api: GeneratedProject):
        """Complete API has all expected files."""
        for filename in self.EXPECTED_SRC_FILES + self.EXPECTED_PROJECT_FILES:
            assert filename in generated_user_management_api, f"Missing file: {filename}"

    def test_path_params_file_generated_when_needed(self, generated_items_api: GeneratedProject):
        """path.py is generated when path parameters are defined."""
        assert "src/path.py" in generated_items_api

    def test_query_params_file_generated_when_needed(self, generated_items_api: GeneratedProject):
        """query.py is generated when query parameters are defined."""
        assert "src/query.py" in generated_items_api


# =============================================================================
# Syntax Validation - Generated Python is valid
# =============================================================================


class TestSyntaxValidation:
    """Tests to verify generated Python code is syntactically valid."""

    def test_items_api_python_syntax(self, generated_items_api: GeneratedProject):
        """All generated Python files in items API are syntactically valid."""
        for filename, content in generated_items_api.get_python_files():
            try:
                ast.parse(content)
            except SyntaxError as e:
                pytest.fail(f"Syntax error in {filename}: {e}")

    def test_user_management_api_python_syntax(self, generated_user_management_api: GeneratedProject):
        """All generated Python files in complete API are syntactically valid."""
        for filename, content in generated_user_management_api.get_python_files():
            try:
                ast.parse(content)
            except SyntaxError as e:
                pytest.fail(f"Syntax error in {filename}: {e}")

    def test_models_can_be_compiled(self, generated_items_api: GeneratedProject):
        """models.py can be compiled to bytecode."""
        content = generated_items_api["src/models.py"]
        try:
            compile(content, "models.py", "exec")
        except SyntaxError as e:
            pytest.fail(f"Failed to compile models.py: {e}")

    def test_views_can_be_compiled(self, generated_items_api: GeneratedProject):
        """views.py can be compiled to bytecode."""
        content = generated_items_api["src/views.py"]
        try:
            compile(content, "views.py", "exec")
        except SyntaxError as e:
            pytest.fail(f"Failed to compile views.py: {e}")


# =============================================================================
# Structural Assertions - Key patterns exist
# =============================================================================


class TestModelsStructure:
    """Tests to verify generated models have correct structure."""

    def test_models_import_pydantic(self, generated_items_api: GeneratedProject):
        """models.py imports BaseModel from pydantic."""
        models = generated_items_api["src/models.py"]
        assert "from pydantic import BaseModel" in models

    def test_items_api_has_expected_model_classes(self, generated_items_api: GeneratedProject):
        """Items API generates expected model classes."""
        models = generated_items_api["src/models.py"]
        expected_classes = [
            "GetItemResponse",
            "GetItemsResponse",
            "CreateItemRequest",
            "UpdateItemRequest",
        ]
        for class_name in expected_classes:
            assert f"class {class_name}(BaseModel):" in models

    def test_user_management_api_has_expected_model_classes(self, generated_user_management_api: GeneratedProject):
        """Complete API generates expected model classes."""
        models = generated_user_management_api["src/models.py"]
        expected_classes = [
            "User",
            "UserList",
            "CreateUserRequest",
            "UpdateUserRequest",
            "LoginRequest",
            "TokenResponse",
        ]
        for class_name in expected_classes:
            assert f"class {class_name}(BaseModel):" in models

    def test_model_fields_have_correct_types(self, generated_items_api: GeneratedProject):
        """Model fields have correct type annotations."""
        models = generated_items_api["src/models.py"]
        # GetItemResponse should have id: int and name: str
        assert "id: int" in models
        assert "name: str" in models

    def test_list_fields_use_typing(self, generated_items_api: GeneratedProject):
        """List fields import and use typing.List."""
        models = generated_items_api["src/models.py"]
        assert "from typing import" in models
        assert "List[GetItemResponse]" in models


class TestViewsStructure:
    """Tests to verify generated views have correct structure."""

    def test_views_import_fastapi(self, generated_items_api: GeneratedProject):
        """views.py imports APIRouter from fastapi."""
        views = generated_items_api["src/views.py"]
        assert "from fastapi import APIRouter" in views

    def test_views_create_router(self, generated_items_api: GeneratedProject):
        """views.py creates an APIRouter instance."""
        views = generated_items_api["src/views.py"]
        assert "api_router = APIRouter()" in views

    def test_items_api_has_expected_endpoints(self, generated_items_api: GeneratedProject):
        """Items API generates expected endpoint decorators."""
        views = generated_items_api["src/views.py"]
        expected_patterns = [
            '@api_router.get(path="/items/{item_id}"',
            '@api_router.get(path="/items"',
            '@api_router.post(path="/items"',
            '@api_router.put(path="/items/{item_id}"',
            '@api_router.delete(path="/items/{item_id}"',
        ]
        for pattern in expected_patterns:
            assert pattern in views, f"Missing endpoint pattern: {pattern}"

    def test_user_management_api_has_expected_endpoints(self, generated_user_management_api: GeneratedProject):
        """Complete API generates expected endpoints."""
        views = generated_user_management_api["src/views.py"]
        # Check for user endpoints
        assert "/users" in views
        assert "/users/{user_id}" in views
        # Check for auth endpoint
        assert "/auth/login" in views

    def test_views_use_response_model(self, generated_items_api: GeneratedProject):
        """Views specify response_model in decorator."""
        views = generated_items_api["src/views.py"]
        assert "response_model=GetItemResponse" in views
        assert "response_model=GetItemsResponse" in views

    def test_post_endpoints_accept_request_body(self, generated_items_api: GeneratedProject):
        """POST endpoints accept request body parameter."""
        views = generated_items_api["src/views.py"]
        assert "request: CreateItemRequest" in views

    def test_views_are_async(self, generated_items_api: GeneratedProject):
        """View functions are defined as async."""
        views = generated_items_api["src/views.py"]
        assert "async def get_item(" in views
        assert "async def create_item(" in views


class TestPathAndQueryParams:
    """Tests for path and query parameter generation."""

    def test_path_params_file_defines_annotated_types(self, generated_items_api: GeneratedProject):
        """path.py defines Annotated types for path parameters."""
        path_py = generated_items_api["src/path.py"]
        assert "from typing import Annotated" in path_py
        assert "ItemId" in path_py

    def test_query_params_file_defines_annotated_types(self, generated_items_api: GeneratedProject):
        """query.py defines Annotated types for query parameters."""
        query_py = generated_items_api["src/query.py"]
        assert "from typing import Annotated" in query_py
        assert "Limit" in query_py
        assert "Offset" in query_py

    def test_views_use_path_param_types(self, generated_items_api: GeneratedProject):
        """Views use path parameter types from path.py."""
        views = generated_items_api["src/views.py"]
        assert "item_id: path.ItemId" in views

    def test_views_use_query_param_types(self, generated_items_api: GeneratedProject):
        """Views use query parameter types from query.py."""
        views = generated_items_api["src/views.py"]
        assert "limit: query.Limit" in views
        assert "offset: query.Offset" in views


# =============================================================================
# New Field Coverage Tests - Verify new fields are handled
# =============================================================================


class TestNewInputFields:
    """Tests to verify new input model fields are properly handled."""

    def test_input_model_accepts_description(self):
        """InputModel accepts description field."""
        from api_craft.models.input import InputField, InputModel

        model = InputModel(
            name="TestModel",
            fields=[InputField(name="id", type="int", required=True)],
            description="A test model",
        )
        assert model.description == "A test model"

    def test_input_field_accepts_description(self):
        """InputField accepts description field."""
        from api_craft.models.input import InputField

        field = InputField(
            name="email",
            type="str",
            required=True,
            description="User email address",
        )
        assert field.description == "User email address"

    def test_input_field_accepts_default_value(self):
        """InputField accepts default_value field."""
        from api_craft.models.input import InputField

        field = InputField(
            name="is_active",
            type="bool",
            required=False,
            default_value="True",
        )
        assert field.default_value == "True"

    def test_input_field_accepts_validators(self):
        """InputField accepts validators field."""
        from api_craft.models.input import InputField, InputValidator

        field = InputField(
            name="email",
            type="str",
            required=True,
            validators=[
                InputValidator(name="max_length", params={"value": 255}),
            ],
        )
        assert len(field.validators) == 1
        assert field.validators[0].name == "max_length"
        assert field.validators[0].params == {"value": 255}

    def test_input_view_accepts_description(self):
        """InputView accepts description field."""
        from api_craft.models.input import InputView

        view = InputView(
            name="ListUsers",
            path="/users",
            method="GET",
            response="User",
            description="Get all users",
        )
        assert view.description == "Get all users"

    def test_input_view_accepts_use_envelope(self):
        """InputView accepts use_envelope field."""
        from api_craft.models.input import InputView

        view = InputView(
            name="ListUsers",
            path="/users",
            method="GET",
            response="User",
            use_envelope=False,
        )
        assert view.use_envelope is False

    def test_input_view_accepts_response_shape(self):
        """InputView accepts response_shape field."""
        from api_craft.models.input import InputView

        view = InputView(
            name="ListUsers",
            path="/users",
            method="GET",
            response="UserList",
            response_shape="list",
        )
        assert view.response_shape == "list"

    def test_input_api_accepts_tags(self):
        """InputAPI accepts tags field."""
        from api_craft.models.input import (
            InputAPI,
            InputField,
            InputModel,
            InputTag,
            InputView,
        )

        api = InputAPI(
            name="TestApi",
            objects=[
                InputModel(
                    name="User",
                    fields=[InputField(name="id", type="int", required=True)],
                )
            ],
            views=[
                InputView(
                    name="GetUser",
                    path="/users",
                    method="GET",
                    response="User",
                )
            ],
            tags=[
                InputTag(name="Users", description="User operations"),
            ],
        )
        assert len(api.tags) == 1
        assert api.tags[0].name == "Users"
        assert api.tags[0].description == "User operations"

    def test_input_path_param_accepts_description(self):
        """InputPathParam accepts description field."""
        from api_craft.models.input import InputPathParam

        param = InputPathParam(
            name="user_id",
            type="int",
            description="The user's unique identifier",
        )
        assert param.description == "The user's unique identifier"

    def test_input_query_param_accepts_description(self):
        """InputQueryParam accepts description field."""
        from api_craft.models.input import InputQueryParam

        param = InputQueryParam(
            name="limit",
            type="int",
            required=False,
            description="Maximum results to return",
        )
        assert param.description == "Maximum results to return"


class TestCompleteApiTransformation:
    """Tests to verify complete API with all fields transforms correctly."""

    def test_user_management_api_loads_without_error(self, user_management_api_input: InputAPI):
        """Complete API input loads and validates without error."""
        assert user_management_api_input.name == "UserManagementApi"
        assert len(user_management_api_input.tags) == 2
        assert len(user_management_api_input.objects) == 6
        assert len(user_management_api_input.views) == 6

    def test_user_management_api_tags_preserved(self, user_management_api_input: InputAPI):
        """Tags are preserved in complete API."""
        tag_names = {t.name for t in user_management_api_input.tags}
        assert "Users" in tag_names
        assert "Auth" in tag_names

    def test_user_management_api_validators_preserved(self, user_management_api_input: InputAPI):
        """Field validators are preserved in complete API."""
        user_model = next(o for o in user_management_api_input.objects if o.name == "User")
        email_field = next(f for f in user_model.fields if f.name == "email")
        assert len(email_field.validators) == 1
        assert email_field.validators[0].name == "max_length"

    def test_user_management_api_descriptions_preserved(self, user_management_api_input: InputAPI):
        """Descriptions are preserved in complete API."""
        user_model = next(o for o in user_management_api_input.objects if o.name == "User")
        assert user_model.description == "Represents a user in the system"

        id_field = next(f for f in user_model.fields if f.name == "id")
        assert id_field.description == "Unique user identifier"

    def test_user_management_api_view_fields_preserved(self, user_management_api_input: InputAPI):
        """View-level fields are preserved in complete API."""
        list_users = next(v for v in user_management_api_input.views if v.name == "ListUsers")
        assert list_users.description == "List all users with pagination"
        assert list_users.use_envelope is True
        assert list_users.response_shape == "object"

        delete_user = next(v for v in user_management_api_input.views if v.name == "DeleteUser")
        assert delete_user.use_envelope is False


class TestTemplateTransformation:
    """Tests to verify input models transform correctly to template models."""

    def test_transform_preserves_field_description(self):
        """Transformer preserves field description."""
        from api_craft.models.input import InputField
        from api_craft.transformers import transform_field

        input_field = InputField(
            name="email",
            type="str",
            required=True,
            description="User email",
        )
        template_field = transform_field(input_field)
        assert template_field.description == "User email"

    def test_transform_preserves_field_validators(self):
        """Transformer preserves field validators."""
        from api_craft.models.input import InputField, InputValidator
        from api_craft.transformers import transform_field

        input_field = InputField(
            name="email",
            type="str",
            required=True,
            validators=[InputValidator(name="max_length", params={"value": 255})],
        )
        template_field = transform_field(input_field)
        assert len(template_field.validators) == 1
        assert template_field.validators[0].name == "max_length"

    def test_transform_preserves_model_description(self):
        """Transformer preserves model description."""
        from api_craft.models.input import InputField, InputModel
        from api_craft.transformers import transform_model

        input_model = InputModel(
            name="User",
            fields=[InputField(name="id", type="int", required=True)],
            description="User model",
        )
        template_model = transform_model(input_model)
        assert template_model.description == "User model"

    def test_transform_preserves_view_fields(self):
        """Transformer preserves view-level fields."""
        from api_craft.models.input import InputField, InputModel, InputView
        from api_craft.transformers import transform_model, transform_view

        # Create field map
        input_model = InputModel(
            name="User",
            fields=[InputField(name="id", type="int", required=True)],
        )
        template_model = transform_model(input_model)
        field_map = {template_model.name: template_model.fields}

        input_view = InputView(
            name="GetUser",
            path="/users",
            method="GET",
            response="User",
            tag="Users",
            description="Get a user",
            use_envelope=False,
            response_shape="object",
        )
        template_view = transform_view(input_view, field_map)

        assert template_view.tag == "Users"
        assert template_view.description == "Get a user"
        assert template_view.use_envelope is False
        assert template_view.response_shape == "object"

    def test_transform_api_preserves_tags(self):
        """Transformer preserves API tags."""
        from api_craft.models.input import (
            InputAPI,
            InputField,
            InputModel,
            InputTag,
            InputView,
        )
        from api_craft.transformers import transform_api

        input_api = InputAPI(
            name="TestApi",
            objects=[
                InputModel(
                    name="User",
                    fields=[InputField(name="id", type="int", required=True)],
                )
            ],
            views=[InputView(name="GetUser", path="/users", method="GET", response="User")],
            tags=[InputTag(name="Users", description="User ops")],
        )
        template_api = transform_api(input_api)

        assert len(template_api.tags) == 1
        assert template_api.tags[0].name == "Users"
        assert template_api.tags[0].description == "User ops"


# =============================================================================
# Import Collection Tests
# =============================================================================


class TestCollectImports:
    """Tests for the generalized collect_imports function."""

    def test_collect_imports_empty_list(self):
        """Empty type list returns empty import set."""
        from api_craft.extractors import collect_imports

        result = collect_imports([])
        assert result == set()

    def test_collect_imports_basic_types(self):
        """Basic types (int, str, bool) need no imports."""
        from api_craft.extractors import collect_imports

        result = collect_imports(["int", "str", "bool", "float"])
        assert result == set()

    def test_collect_imports_datetime(self):
        """datetime.datetime type adds import datetime."""
        from api_craft.extractors import collect_imports

        result = collect_imports(["datetime.datetime"])
        assert "import datetime" in result

    def test_collect_imports_uuid(self):
        """uuid.UUID type adds import uuid."""
        from api_craft.extractors import collect_imports

        result = collect_imports(["uuid.UUID"])
        assert "import uuid" in result

    def test_collect_imports_decimal(self):
        """Decimal type adds from decimal import Decimal."""
        from api_craft.extractors import collect_imports

        result = collect_imports(["decimal.Decimal"])
        assert "from decimal import Decimal" in result

    def test_collect_imports_typing_list(self):
        """List generic adds typing import."""
        from api_craft.extractors import collect_imports

        result = collect_imports(["List[str]"])
        assert "from typing import List" in result

    def test_collect_imports_typing_optional(self):
        """Optional generic adds typing import."""
        from api_craft.extractors import collect_imports

        result = collect_imports(["Optional[int]"])
        assert "from typing import Optional" in result

    def test_collect_imports_multiple_typing(self):
        """Multiple typing generics are combined into single import."""
        from api_craft.extractors import collect_imports

        result = collect_imports(["List[str]", "Optional[int]", "Dict[str, int]"])
        # Should have a single combined typing import
        typing_imports = [i for i in result if "from typing import" in i]
        assert len(typing_imports) == 1
        assert "Dict" in typing_imports[0]
        assert "List" in typing_imports[0]
        assert "Optional" in typing_imports[0]

    def test_collect_imports_nested_generics(self):
        """Nested generics like Optional[List[str]] are handled."""
        from api_craft.extractors import collect_imports

        result = collect_imports(["Optional[List[str]]"])
        typing_import = next(i for i in result if "from typing import" in i)
        assert "List" in typing_import
        assert "Optional" in typing_import

    def test_collect_imports_mixed_types(self):
        """Mixed types with modules and generics work together."""
        from api_craft.extractors import collect_imports

        result = collect_imports(
            [
                "datetime.datetime",
                "List[str]",
                "Optional[uuid.UUID]",
            ]
        )
        assert "import datetime" in result
        assert "import uuid" in result
        typing_import = next(i for i in result if "from typing import" in i)
        assert "List" in typing_import
        assert "Optional" in typing_import

    def test_collect_imports_sorting_consistency(self):
        """Typing imports are sorted alphabetically for consistency."""
        from api_craft.extractors import collect_imports

        result = collect_imports(["Dict[str, int]", "Any", "List[str]"])
        typing_import = next(i for i in result if "from typing import" in i)
        # Should be alphabetically sorted: Any, Dict, List
        assert typing_import == "from typing import Any, Dict, List"

    def test_collect_model_imports_integration(self):
        """collect_model_imports works with TemplateModel instances."""
        from api_craft.extractors import collect_model_imports
        from api_craft.models.template import TemplateField, TemplateModel

        models = [
            TemplateModel(
                name="User",
                fields=[
                    TemplateField(name="id", type="int", required=True),
                    TemplateField(name="created_at", type="datetime.datetime", required=True),
                    TemplateField(name="tags", type="List[str]", required=False),
                ],
            )
        ]
        result = collect_model_imports(models)
        assert "import datetime" in result
        assert any("List" in i for i in result)

    def test_collect_path_params_imports_integration(self):
        """collect_path_params_imports works with TemplatePathParam instances."""
        from api_craft.extractors import collect_path_params_imports
        from api_craft.models.template import TemplatePathParam

        params = [
            TemplatePathParam(
                name="EventDate",
                snake_name="event_date",
                camel_name="eventDate",
                title="Event Date",
                type="datetime.datetime",
            )
        ]
        result = collect_path_params_imports(params)
        assert "import datetime" in result

    def test_collect_query_params_imports_integration(self):
        """collect_query_params_imports works with TemplateQueryParam instances."""
        from api_craft.extractors import collect_query_params_imports
        from api_craft.models.template import TemplateQueryParam

        params = [
            TemplateQueryParam(
                name="StartDate",
                snake_name="start_date",
                camel_name="startDate",
                title="Start Date",
                type="datetime.datetime",
                required=False,
            )
        ]
        result = collect_query_params_imports(params)
        assert "import datetime" in result


# =============================================================================
# Backwards Compatibility Tests
# =============================================================================


class TestBackwardsCompatibility:
    """Tests to ensure existing inputs still work."""

    def test_items_api_input_still_valid(self, items_api_input: InputAPI):
        """Existing items API input loads without error."""
        assert items_api_input.name == "ItemsApi"

    def test_minimal_input_works(self):
        """Minimal input without new optional fields still works."""
        from api_craft.models.input import InputAPI, InputField, InputModel, InputView

        # This is the minimal valid input
        api = InputAPI(
            name="MinimalApi",
            objects=[
                InputModel(
                    name="Response",
                    fields=[InputField(name="ok", type="bool", required=True)],
                )
            ],
            views=[
                InputView(
                    name="Health",
                    path="/health",
                    method="GET",
                    response="Response",
                )
            ],
        )
        assert api.name == "MinimalApi"
        # New fields have sensible defaults
        assert api.tags == []
        assert api.objects[0].description is None
        assert api.views[0].use_envelope is True
        assert api.views[0].response_shape == "object"


# =============================================================================
# Manual Generation - Run with: make generate
# =============================================================================


@pytest.fixture(scope="class")
def output_path() -> Path:
    """Clean output directory once and return the path."""
    import shutil

    if OUTPUT_PATH.exists():
        shutil.rmtree(OUTPUT_PATH)
    OUTPUT_PATH.mkdir(exist_ok=True)
    return OUTPUT_PATH


@pytest.mark.manual
class TestManualGeneration:
    """Generate API projects to tests/output/ for manual inspection.

    Run with: make generate
    """

    def test_generate_items_api(
        self, items_api_input: InputAPI, output_path: Path
    ) -> None:
        """Generate items API for manual inspection."""
        generator = APIGenerator()
        generator.generate(items_api_input, path=str(output_path))
        print(f"\nGenerated: {output_path / items_api_input.name.kebab_name}")

    def test_generate_user_management_api(
        self, user_management_api_input: InputAPI, output_path: Path
    ) -> None:
        """Generate user management API for manual inspection."""
        generator = APIGenerator()
        generator.generate(user_management_api_input, path=str(output_path))
        print(f"\nGenerated: {output_path / user_management_api_input.name.kebab_name}")
