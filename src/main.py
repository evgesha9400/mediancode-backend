import logging
import os

from jinja2 import Environment, FileSystemLoader

from extractors import extract_models, extract_views
from models.input import InputAPI
from transformers import transform_api
from utils import create_dir, write_file
from renderers import render_models, render_views

logging.basicConfig(level="INFO")
logger = logging.getLogger(__name__)
curr_dir = os.path.dirname(__file__)
template_dir = os.path.join(curr_dir, "templates")
env = Environment(loader=FileSystemLoader(template_dir))


def generate_fastapi(api: InputAPI, dry_run: bool = False):
    models_template = env.get_template("models.j2")
    views_template = env.get_template("views.j2")

    template_api = transform_api(api)

    template_models = extract_models(template_api)
    template_views = extract_views(template_api)

    rendered_models = render_models(template_models, models_template)
    rendered_views = render_views(template_views, views_template)

    if dry_run:
        logger.info("Dry run enabled. No files will be written.")
        logger.info(f"models.py:\n{rendered_models}")
        logger.info(f"views.py:\n{rendered_views}")
    else:
        path = os.path.join(curr_dir, "generated")
        create_dir(path)
        write_file(os.path.join(path, "models.py"), rendered_models)
        write_file(os.path.join(path, "views.py"), rendered_views)
