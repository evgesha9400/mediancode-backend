"""Main module for API generation with improved organization and clear execution flow."""

import logging
import os
from typing import Any, Dict, Optional

from jinja2 import Environment, FileSystemLoader, Template

from src.api_craft.extractors import (
    extract_path_parameters,
    extract_query_parameters,
    extract_request_models,
    extract_response_models,
    extract_types_from_models,
    extract_views,
)
from src.api_craft.models.input import InputAPI
from src.api_craft.models.template import TemplateAPI
from src.api_craft.renderers import (
    render_dockerfile,
    render_main,
    render_makefile,
    render_path_params,
    render_pyproject,
    render_query_params,
    render_requests,
    render_responses,
    render_views,
)
from src.api_craft.transformers import transform_api
from src.api_craft.utils import camel_to_snake, copy_file, create_dir, write_file

# Configure logging
logging.basicConfig(level="INFO")
logger = logging.getLogger(__name__)


class APIGenerator:
    """Class to handle the generation of API code with a clear, linear flow."""

    def __init__(self, template_dir: str = None):
        """Initialize the generator with template directory.

        Args:
            template_dir: Optional custom template directory path. If not provided,
                        uses the default templates directory.
        """
        self.template_dir = template_dir or os.path.join(os.path.dirname(__file__), "templates")
        self.env: Optional[Environment] = None
        self.templates: Dict[str, Template] = {}

    def load_templates(self) -> None:
        """Load all required Jinja2 templates.

        Raises:
            FileNotFoundError: If template files are missing
        """
        try:
            self.env = Environment(loader=FileSystemLoader(self.template_dir))

            # Load all templates up front
            template_files = {
                "requests": "requests.j2",
                "responses": "responses.j2",
                "views": "views.j2",
                "path": "path.j2",
                "query": "query.j2",
                "main": "main.j2",
                "pyproject": "pyproject.j2",
                "makefile": "makefile.j2",
                "dockerfile": "dockerfile.j2",
            }

            self.templates = {key: self.env.get_template(filename) for key, filename in template_files.items()}
        except Exception as e:
            logger.error(f"Failed to load templates: {str(e)}")
            raise

    def transform_api(self, api: InputAPI) -> TemplateAPI:
        """Transform input API into template format.

        Args:
            api: Input API model to transform

        Returns:
            Transformed template API

        Raises:
            ValueError: If transformation fails
        """
        try:
            return transform_api(api)
        except Exception as e:
            logger.error(f"Failed to transform API: {str(e)}")
            raise ValueError("API transformation failed") from e

    def extract_components(self, template_api: TemplateAPI) -> Dict[str, Any]:
        """Extract all components from the template API.

        Args:
            template_api: Transformed template API

        Returns:
            Dictionary containing extracted components

        Raises:
            ValueError: If component extraction fails
        """
        try:
            return {
                "requests": extract_request_models(template_api),
                "responses": extract_response_models(template_api),
                "views": extract_views(template_api),
                "path_params": extract_path_parameters(template_api),
                "query_params": extract_query_parameters(template_api),
            }
        except Exception as e:
            logger.error(f"Failed to extract components: {str(e)}")
            raise ValueError("Component extraction failed") from e

    def render_components(self, components: Dict[str, Any], template_api: TemplateAPI) -> Dict[str, str]:
        """Render all components using templates.

        Args:
            components: Extracted API components
            template_api: Transformed template API

        Returns:
            Dictionary mapping filenames to rendered content

        Raises:
            ValueError: If rendering fails
        """
        try:
            request_imports = extract_types_from_models(components["requests"])
            response_imports = extract_types_from_models(components["responses"])

            return {
                "requests.py": render_requests(components["requests"], request_imports, self.templates["requests"]),
                "responses.py": render_responses(
                    components["responses"], response_imports, self.templates["responses"]
                ),
                "views.py": render_views(components["views"], self.templates["views"]),
                "path.py": render_path_params(components["path_params"], self.templates["path"]),
                "query.py": render_query_params(components["query_params"], self.templates["query"]),
                "main.py": render_main(template_api, self.templates["main"]),
                "pyproject.toml": render_pyproject(template_api, self.templates["pyproject"]),
                "Makefile": render_makefile(template_api, self.templates["makefile"]),
                "Dockerfile": render_dockerfile(template_api, self.templates["dockerfile"]),
            }
        except Exception as e:
            logger.error(f"Failed to render components: {str(e)}")
            raise ValueError("Component rendering failed") from e

    def write_files(self, rendered_components: Dict[str, str], api: InputAPI, path: str) -> None:
        """Write rendered components to files.

        Args:
            rendered_components: Dictionary of filename to content mappings
            api: Original input API
            path: Output directory path

        Raises:
            IOError: If file writing fails
        """
        try:
            project_name = camel_to_snake(api.name)
            project_directory = os.path.join(path, project_name)
            src_directory = os.path.join(project_directory, "src")

            # Create directories
            create_dir(src_directory)

            # Write source files
            for filename, content in rendered_components.items():
                if filename in ["pyproject.toml", "Makefile", "Dockerfile"]:
                    file_path = os.path.join(project_directory, filename)
                else:
                    file_path = os.path.join(src_directory, filename)
                write_file(file_path, content)

            # Copy static files
            static_dir = os.path.join(self.template_dir, "static")
            copy_file(
                os.path.join(static_dir, "swagger.py"),
                os.path.join(project_directory, "swagger.py"),
            )
        except Exception as e:
            logger.error(f"Failed to write files: {str(e)}")
            raise IOError("File writing failed") from e

    def generate(self, api: InputAPI, path: str = None, dry_run: bool = False) -> None:
        """Main generation method with clear steps.

        Args:
            api: Input API to generate code for
            path: Optional output directory path
            dry_run: If True, only logs what would be generated

        Raises:
            Exception: If any step fails
        """
        try:
            logger.info("Starting API generation...")

            # 1. Load templates
            logger.info("Loading templates...")
            self.load_templates()

            # 2. Transform API
            logger.info("Transforming API...")
            template_api = self.transform_api(api)

            # 3. Extract components
            logger.info("Extracting components...")
            components = self.extract_components(template_api)

            # 4. Render components
            logger.info("Rendering components...")
            rendered_components = self.render_components(components, template_api)

            # 5. Write files or display dry run
            if not dry_run:
                logger.info("Writing files...")
                output_path = path or os.path.dirname(__file__)
                self.write_files(rendered_components, api, output_path)
                logger.info("API generation completed successfully.")
            else:
                logger.info("Dry run enabled. Would generate these files:")
                for filename, content in rendered_components.items():
                    logger.info(f"\n{filename}:\n{content}")
                logger.info("Dry run completed successfully.")

        except Exception as e:
            logger.error(f"API generation failed: {str(e)}")
            raise


def generate_fastapi(api: InputAPI, path: str = None, dry_run: bool = False) -> None:
    """Generate FastAPI code from input API specification.

    Args:
        api: Input API specification
        path: Optional output directory path
        dry_run: If True, only logs what would be generated

    Raises:
        Exception: If generation fails
    """
    generator = APIGenerator()
    generator.generate(api, path, dry_run)
