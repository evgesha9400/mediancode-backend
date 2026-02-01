"""Main module for API generation.

This module orchestrates transforming a high-level API specification into a
fully scaffolded FastAPI project using Mako templates.
"""

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import black
from mako.exceptions import TopLevelLookupException
from mako.lookup import TemplateLookup
from mako.template import Template

from api_craft.extractors import (
    collect_model_imports,
    collect_path_params_imports,
    collect_query_params_imports,
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
    render_readme,
    render_views,
)
from api_craft.transformers import transform_api
from api_craft.utils import camel_to_kebab, copy_file, create_dir, write_file

# Configure logging
logging.basicConfig(level="INFO")
logger = logging.getLogger(__name__)


def format_python_files(directory: Path) -> None:
    """Format all Python files in a directory using Black.

    :param directory: Path to the directory containing Python files.
    """
    mode = black.Mode(line_length=120)
    for py_file in directory.rglob("*.py"):
        try:
            content = py_file.read_text()
            formatted = black.format_str(content, mode=mode)
            py_file.write_text(formatted)
            logger.debug(f"Formatted {py_file}")
        except black.InvalidInput as e:
            logger.warning(f"Could not format {py_file}: {e}")


def generate_swagger(project_dir: Path) -> None:
    """Generate swagger.yaml by running the swagger.py script.

    :param project_dir: Path to the generated project directory.
    """
    swagger_script = project_dir / "swagger.py"
    src_dir = project_dir / "src"

    if not swagger_script.exists():
        logger.warning(f"swagger.py not found at {swagger_script}")
        return

    env = os.environ.copy()
    env["PYTHONPATH"] = str(src_dir)

    result = subprocess.run(
        [sys.executable, str(swagger_script)],
        cwd=str(project_dir),
        env=env,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        logger.warning(f"Swagger generation failed: {result.stderr}")
    else:
        logger.debug(f"Swagger generated: {result.stdout}")


class APIGenerator:
    """Generate a FastAPI project from an input specification.

    The generator performs the following steps:

    1. Load Mako templates.
    2. Transform input models to template models.
    3. Extract components used by templates.
    4. Render template files.
    5. Write files into the target project structure.
    """

    def __init__(self, template_dir: str = None):
        """Initialize the generator.

        :param template_dir: Optional templates directory. If ``None``, the
            default ``templates/`` bundled with this package is used.
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
                "readme": "readme.mako",
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

        :param api: Input API model to transform.
        :returns: Transformed :class:`api_craft.models.template.TemplateAPI`.
        :raises ValueError: If transformation fails.
        """
        try:
            return transform_api(api)
        except Exception as e:
            logger.error(f"Failed to transform API: {str(e)}")
            raise ValueError("API transformation failed") from e

    def extract_components(self, template_api: TemplateAPI) -> Dict[str, Any]:
        """Extract all components from the template API.

        :param template_api: Transformed template API.
        :returns: Mapping of component names to values used by templates.
        :raises ValueError: If component extraction fails.
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

        :param components: Extracted API components.
        :param template_api: Transformed template API.
        :returns: Mapping of filenames to rendered text content.
        :raises ValueError: If rendering fails.
        """
        try:
            model_imports = collect_model_imports(components["models"])

            rendered_components = {
                "models.py": render_models(
                    components["models"], model_imports, self.templates["models"]
                ),
                "views.py": render_views(components["views"], self.templates["views"]),
                "main.py": render_main(template_api, self.templates["main"]),
                "pyproject.toml": render_pyproject(template_api, self.templates["pyproject"]),
                "Makefile": render_makefile(template_api, self.templates["makefile"]),
                "Dockerfile": render_dockerfile(template_api, self.templates["dockerfile"]),
                "README.md": render_readme(template_api, self.templates["readme"]),
            }

            if components["path_params"]:
                path_imports = collect_path_params_imports(components["path_params"])
                rendered_components["path.py"] = render_path_params(
                    components["path_params"],
                    path_imports,
                    self.templates["path"],
                )

            if components["query_params"]:
                query_imports = collect_query_params_imports(components["query_params"])
                rendered_components["query.py"] = render_query_params(
                    components["query_params"],
                    query_imports,
                    self.templates["query"],
                )

            return rendered_components
        except Exception as e:
            logger.error(f"Failed to render components: {str(e)}")
            raise ValueError("Component rendering failed") from e

    def write_files(self, rendered_components: Dict[str, str], api: InputAPI, path: str) -> None:
        """Write rendered components to files.

        :param rendered_components: Mapping of filename to content.
        :param api: Original input API.
        :param path: Output directory path.
        :raises IOError: If file writing fails.
        """
        try:
            project_name = camel_to_kebab(api.name)
            project_directory = os.path.join(path, project_name)
            src_directory = os.path.join(project_directory, "src")

            # Create directories
            create_dir(src_directory)

            # Write source files
            for filename, content in rendered_components.items():
                if filename in ["pyproject.toml", "Makefile", "Dockerfile", "README.md"]:
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
        """Run the end-to-end generation flow.

        :param api: Input API to generate code for.
        :param path: Optional output directory path.
        :param dry_run: If ``True``, log the rendered content without writing files.
        :raises Exception: If any step fails.
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

                project_dir = Path(output_path) / camel_to_kebab(api.name)

                # 6. Format code if enabled
                if template_api.config.format_code:
                    logger.info("Formatting generated code...")
                    format_python_files(project_dir)

                # 7. Generate swagger if enabled
                if template_api.config.generate_swagger:
                    logger.info("Generating swagger.yaml...")
                    generate_swagger(project_dir)

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
    """Generate FastAPI code from an input specification.

    :param api: Input API specification.
    :param path: Optional output directory path.
    :param dry_run: If ``True``, only log what would be generated.
    :raises Exception: If generation fails.
    """
    generator = APIGenerator()
    generator.generate(api, path, dry_run)
