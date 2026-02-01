# src/api/services/generation.py
"""Service for generating FastAPI code from API entities."""

import io
import os
import tempfile
import zipfile

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.models.database import (
    ApiModel,
    FieldModel,
    ObjectDefinition,
)
from api.settings import get_settings
from api_craft.main import APIGenerator
from api_craft.models.input import (
    InputAPI,
    InputApiConfig,
    InputEndpoint,
    InputField,
    InputModel,
    InputPathParam,
    InputQueryParam,
    InputTag,
    InputValidator,
)


async def generate_api_zip(api: ApiModel, db: AsyncSession) -> io.BytesIO:
    """Generate a ZIP file containing the FastAPI application for an API.

    :param api: The API model with loaded relations.
    :param db: Database session for fetching related entities.
    :returns: BytesIO buffer containing the ZIP file.
    """
    # Fetch all related data
    objects_map = await _fetch_objects(api, db)
    fields_map = await _fetch_fields(objects_map, db)

    # Convert to api_craft InputAPI format
    input_api = _convert_to_input_api(api, objects_map, fields_map)

    # Generate files to a temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        generator = APIGenerator()
        generator.generate(input_api, path=temp_dir)

        # Create ZIP file
        zip_buffer = io.BytesIO()
        project_name = input_api.name.replace(" ", "").lower()
        # api_craft uses kebab-case for directory name
        from api_craft.utils import camel_to_kebab

        project_dir = os.path.join(temp_dir, camel_to_kebab(input_api.name))

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(project_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arc_name = os.path.relpath(file_path, project_dir)
                    zf.write(file_path, arc_name)

        zip_buffer.seek(0)
        return zip_buffer


async def _fetch_objects(api: ApiModel, db: AsyncSession) -> dict[str, ObjectDefinition]:
    """Fetch all objects referenced by the API's endpoints.

    :param api: The API model.
    :param db: Database session.
    :returns: Map of object ID to ObjectDefinition.
    """
    settings = get_settings()

    # Collect all object IDs from endpoints
    object_ids: set[str] = set()
    for endpoint in api.endpoints:
        if endpoint.query_params_object_id:
            object_ids.add(endpoint.query_params_object_id)
        if endpoint.request_body_object_id:
            object_ids.add(endpoint.request_body_object_id)
        if endpoint.response_body_object_id:
            object_ids.add(endpoint.response_body_object_id)

    if not object_ids:
        return {}

    # Fetch objects with field associations
    query = (
        select(ObjectDefinition)
        .options(selectinload(ObjectDefinition.field_associations))
        .where(ObjectDefinition.id.in_(object_ids))
    )
    result = await db.execute(query)
    objects = result.scalars().all()

    return {obj.id: obj for obj in objects}


async def _fetch_fields(
    objects_map: dict[str, ObjectDefinition],
    db: AsyncSession,
) -> dict[str, FieldModel]:
    """Fetch all fields referenced by objects.

    :param objects_map: Map of object ID to ObjectDefinition.
    :param db: Database session.
    :returns: Map of field ID to FieldModel.
    """
    # Collect all field IDs from objects
    field_ids: set[str] = set()
    for obj in objects_map.values():
        for assoc in obj.field_associations:
            field_ids.add(assoc.field_id)

    if not field_ids:
        return {}

    # Fetch fields with validators
    query = select(FieldModel).options(selectinload(FieldModel.validators)).where(FieldModel.id.in_(field_ids))
    result = await db.execute(query)
    fields = result.scalars().all()

    return {f.id: f for f in fields}


def _convert_to_input_api(
    api: ApiModel,
    objects_map: dict[str, ObjectDefinition],
    fields_map: dict[str, FieldModel],
) -> InputAPI:
    """Convert database entities to api_craft InputAPI format.

    :param api: The API model.
    :param objects_map: Map of object ID to ObjectDefinition.
    :param fields_map: Map of field ID to FieldModel.
    :returns: InputAPI for code generation.
    """
    # Convert objects to InputModel
    input_objects: list[InputModel] = []
    for obj in objects_map.values():
        fields: list[InputField] = []
        for assoc in sorted(obj.field_associations, key=lambda x: x.position):
            field = fields_map.get(assoc.field_id)
            if field:
                # Convert field validators
                validators = [InputValidator(name=v.name, params=v.params) for v in field.validators]
                input_field = InputField(
                    name=field.name,
                    type=_map_field_type(field.type),
                    required=assoc.required,
                    description=field.description,
                    default_value=field.default_value,
                    validators=validators,
                )
                fields.append(input_field)

        # Ensure object name is PascalCase
        obj_name = _to_pascal_case(obj.name)
        input_objects.append(InputModel(name=obj_name, fields=fields, description=obj.description))

    # Build tag lookup and convert tags
    tags_by_id = {tag.id: tag for tag in api.tags}
    input_tags = [InputTag(name=tag.name, description=tag.description) for tag in api.tags]

    # Convert endpoints to InputEndpoint
    input_endpoints: list[InputEndpoint] = []
    for endpoint in api.endpoints:
        # Build endpoint name from method and path
        endpoint_name = _build_endpoint_name(endpoint.method, endpoint.path)

        # Get tag name if present
        tag_name = None
        if endpoint.tag_id and endpoint.tag_id in tags_by_id:
            tag_name = tags_by_id[endpoint.tag_id].name

        # Convert path params
        path_params = None
        if endpoint.path_params:
            path_params = [
                InputPathParam(
                    name=p.name,
                    type=_map_field_type(p.type),
                    description=p.description,
                )
                for p in sorted(endpoint.path_params, key=lambda x: x.position)
            ]

        # Get query params from object
        query_params = None
        if endpoint.query_params_object_id:
            query_obj = objects_map.get(endpoint.query_params_object_id)
            if query_obj:
                query_params = []
                for assoc in sorted(query_obj.field_associations, key=lambda x: x.position):
                    field = fields_map.get(assoc.field_id)
                    if field:
                        query_params.append(
                            InputQueryParam(
                                name=field.name,
                                type=_map_field_type(field.type),
                                required=assoc.required,
                                description=field.description,
                            )
                        )

        # Get request/response object names
        request_name = None
        if endpoint.request_body_object_id:
            req_obj = objects_map.get(endpoint.request_body_object_id)
            if req_obj:
                request_name = _to_pascal_case(req_obj.name)

        response_name = None
        if endpoint.response_body_object_id:
            resp_obj = objects_map.get(endpoint.response_body_object_id)
            if resp_obj:
                response_name = _to_pascal_case(resp_obj.name)

        input_endpoint = InputEndpoint(
            name=endpoint_name,
            path=endpoint.path,
            method=endpoint.method,
            tag=tag_name,
            request=request_name,
            response=response_name,
            query_params=query_params,
            path_params=path_params,
            description=endpoint.description,
            use_envelope=endpoint.use_envelope,
            response_shape=endpoint.response_shape,
        )
        input_endpoints.append(input_endpoint)

    # Build API name in PascalCase
    api_name = _to_pascal_case(api.title.replace(" ", ""))

    return InputAPI(
        name=api_name,
        version=api.version,
        author="Median Code",
        description=api.description or "API Generated by Median Code",
        objects=input_objects,
        endpoints=input_endpoints,
        tags=input_tags,
        config=InputApiConfig(
            healthcheck="/health",
            response_placeholders=True,
        ),
    )


def _map_field_type(field_type: str) -> str:
    """Map API field type to Python type string.

    :param field_type: The field type from the database.
    :returns: Python type string.
    """
    type_mapping = {
        "str": "str",
        "int": "int",
        "float": "float",
        "bool": "bool",
        "datetime": "datetime.datetime",
        "uuid": "str",  # UUIDs are typically strings in API inputs
    }
    return type_mapping.get(field_type, "str")


def _to_pascal_case(name: str) -> str:
    """Convert a name to PascalCase.

    :param name: The name to convert.
    :returns: PascalCase name.
    """
    # Remove non-alphanumeric characters and capitalize each word
    words = []
    current_word = []
    for char in name:
        if char.isalnum():
            current_word.append(char)
        else:
            if current_word:
                words.append("".join(current_word))
                current_word = []
    if current_word:
        words.append("".join(current_word))

    # Capitalize each word
    return "".join(word.capitalize() for word in words)


def _build_endpoint_name(method: str, path: str) -> str:
    """Build an endpoint name from HTTP method and path.

    :param method: HTTP method (GET, POST, etc.).
    :param path: URL path.
    :returns: PascalCase endpoint name.
    """
    # Extract path segments, excluding parameters
    segments = []
    for segment in path.strip("/").split("/"):
        if not segment.startswith("{"):
            segments.append(segment)

    # Build name from method and segments
    method_prefix = method.lower().capitalize()
    if segments:
        path_part = "".join(word.capitalize() for word in segments)
        name = f"{method_prefix}{path_part}"
    else:
        name = f"{method_prefix}Root"

    return name
