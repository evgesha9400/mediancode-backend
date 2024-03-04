import logging
import os

from jinja2 import Environment, FileSystemLoader

from extractors import (
    extract_request_models,
    extract_response_models,
    extract_views,
    extract_path_parameters,
    extract_query_parameters,
    extract_types_from_models,
)
from models.input import InputAPI
from renderers import (
    render_requests,
    render_responses,
    render_views,
    render_path_params,
    render_query_params,
    render_main,
    render_pyproject,
    render_makefile,
    render_dockerfile,
)
from transformers import transform_api
from utils import create_dir, write_file, camel_to_snake, copy_file, apply_black_formatting


logging.basicConfig(level="INFO")
logger = logging.getLogger(__name__)
curr_dir = os.path.dirname(__file__)
template_dir = os.path.join(curr_dir, "templates")
static_dir = os.path.join(template_dir, "static")
env = Environment(loader=FileSystemLoader(template_dir))


def generate_fastapi(api: InputAPI, path: str = curr_dir, dry_run: bool = False):
    # Load Jinja2 templates
    requests_template = env.get_template("requests.j2")
    responses_template = env.get_template("responses.j2")
    views_template = env.get_template("views.j2")
    path_template = env.get_template("path.j2")
    query_template = env.get_template("query.j2")
    main_template = env.get_template("main.j2")
    pyproject_template = env.get_template("pyproject.j2")
    makefile_template = env.get_template("makefile.j2")
    dockerfile_template = env.get_template("dockerfile.j2")

    # Transform the InputAPI instance to a TemplateAPI instance
    template_api = transform_api(api)

    # Extract from the TemplateAPI instance
    template_requests = extract_request_models(template_api)
    template_responses = extract_response_models(template_api)
    template_views = extract_views(template_api)
    template_path = extract_path_parameters(template_api)
    template_query = extract_query_parameters(template_api)

    # Extract imports
    request_imports = extract_types_from_models(template_requests)
    response_imports = extract_types_from_models(template_responses)

    # Render the templates
    rendered_requests = render_requests(
        template_requests, request_imports, requests_template
    )
    rendered_responses = render_responses(
        template_responses, response_imports, responses_template
    )
    rendered_views = render_views(template_views, views_template)
    rendered_path_params = render_path_params(template_path, path_template)
    rendered_query_params = render_query_params(template_query, query_template)
    rendered_main = render_main(template_api, main_template)
    rendered_pyproject = render_pyproject(template_api, pyproject_template)
    rendered_makefile = render_makefile(template_api, makefile_template)
    rendered_dockerfile = render_dockerfile(template_api, dockerfile_template)

    if dry_run:
        logger.info("Dry run enabled. No files will be written.")
        logger.info(f"\nsrc/requests.py:\n{rendered_requests}")
        logger.info(f"\nsrc/responses.py:\n{rendered_responses}")
        logger.info(f"\nsrc/views.py:\n{rendered_views}")
        logger.info(f"\nsrc/path.py:\n{rendered_path_params}")
        logger.info(f"\nsrc/query.py:\n{rendered_query_params}")
        logger.info(f"\nsrc/main.py:\n{rendered_main}")
        logger.info(f"\npyproject.toml:\n{rendered_pyproject}")
        logger.info(f"\nMakefile:\n{rendered_makefile}")
        logger.info(f"\nDockerfile:\n{rendered_dockerfile}")

    else:
        project_name = camel_to_snake(api.name)
        project_directory = os.path.join(path, project_name)
        src_directory = os.path.join(project_directory, "src")
        create_dir(src_directory)
        write_file(os.path.join(src_directory, "requests.py"), rendered_requests)
        write_file(os.path.join(src_directory, "responses.py"), rendered_responses)
        write_file(os.path.join(src_directory, "views.py"), rendered_views)
        write_file(os.path.join(src_directory, "path.py"), rendered_path_params)
        write_file(os.path.join(src_directory, "query.py"), rendered_query_params)
        write_file(os.path.join(src_directory, "main.py"), rendered_main)
        write_file(
            os.path.join(project_directory, "pyproject.toml"), rendered_pyproject
        )
        write_file(os.path.join(project_directory, "Makefile"), rendered_makefile)
        write_file(os.path.join(project_directory, "Dockerfile"), rendered_dockerfile)
        copy_file(os.path.join(static_dir, "swagger.py"), os.path.join(project_directory, "swagger.py"))
        # apply_black_formatting(src_directory)
