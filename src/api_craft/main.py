"""Main module for API generation with improved organization and clear execution flow."""

import logging
import os
from typing import Any, Dict, Optional

from mako.exceptions import TopLevelLookupException
from mako.lookup import TemplateLookup
from mako.template import Template

from api_craft.extractors import (
    collect_model_typing_imports,
    extract_models,
    extract_path_parameters,
    extract_query_parameters,
    extract_views,
)
from api_craft.models.input import InputAPI
from api_craft.models.template import TemplateAPI
from api_craft.renderers import (
    render_dockerfile,
    render_main,
    render_makefile,
    render_models,
    render_path_params,
    render_pyproject,
    render_query_params,
    render_views,
)
from api_craft.transformers import transform_api
from api_craft.utils import camel_to_kebab, copy_file, create_dir, write_file

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
        self.template_lookup: Optional[TemplateLookup] = None
        self.templates: Dict[str, Template] = {}

    def load_templates(self) -> None:
        """Load all required Mako templates.

        :raises FileNotFoundError: If template files are missing.
        """
        try:
            self.template_lookup = TemplateLookup(directories=[self.template_dir])

            # Load all templates up front
            template_files = {
                "models": "models.mako",
                "views": "views.mako",
                "path": "path.mako",
                "query": "query.mako",
                "main": "main.mako",
                "pyproject": "pyproject.mako",
                "makefile": "makefile.mako",
                "dockerfile": "dockerfile.mako",
            }

            self.templates = {
                key: self.template_lookup.get_template(filename) for key, filename in template_files.items()
            }
        except TopLevelLookupException as exc:
            logger.error(f"Failed to load templates: {str(exc)}")
            raise FileNotFoundError("Template files are missing") from exc
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
                "models": extract_models(template_api),
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
            model_imports = collect_model_typing_imports(components["models"])

            rendered_components = {
                "models.py": render_models(components["models"], model_imports, self.templates["models"]),
                "views.py": render_views(components["views"], self.templates["views"]),
                "main.py": render_main(template_api, self.templates["main"]),
                "pyproject.toml": render_pyproject(template_api, self.templates["pyproject"]),
                "Makefile": render_makefile(template_api, self.templates["makefile"]),
                "Dockerfile": render_dockerfile(template_api, self.templates["dockerfile"]),
            }

            if components["path_params"]:
                rendered_components["path.py"] = render_path_params(
                    components["path_params"],
                    self.templates["path"],
                )

            if components["query_params"]:
                rendered_components["query.py"] = render_query_params(
                    components["query_params"],
                    self.templates["query"],
                )

            return rendered_components
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
            project_name = camel_to_kebab(api.name)
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
                # apply_black_formatting(Path(output_path) / camel_to_kebab(api.name))
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
