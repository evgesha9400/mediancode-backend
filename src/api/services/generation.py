# src/api/services/generation.py
"""Service for generating FastAPI code from API entities."""

import io
import os
import tempfile
import zipfile

from jinja2 import Environment
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectin_polymorphic, selectinload

from api.models.database import (
    ApiModel,
    AppliedFieldValidatorModel,
    AppliedModelValidatorModel,
    FieldConstraintValueAssociation,
    FieldModel,
    Namespace,
    ObjectDefinition,
)
from api.models.members import ObjectMember, RelationshipMember, ScalarMember
from api.schemas.api import GenerateOptions
from api_craft.main import APIGenerator
from api_craft.models.input import (
    FieldDefaultGenerated,
    FieldDefaultLiteral,
    InputAPI,
    InputApiConfig,
    InputCdkConfig,
    InputDatabaseConfig,
    InputEndpoint,
    InputField,
    InputModel,
    InputPathParam,
    InputQueryParam,
    InputRelationship,
    InputResolvedFieldValidator,
    InputResolvedModelValidator,
    InputTag,
    InputValidator,
)


def _render_template(body_template: str, context: dict[str, str]) -> str:
    """Render a Jinja2 body template with the given context.

    :param body_template: Jinja2 template string.
    :param context: Template variables to substitute.
    :returns: Rendered Python code string.
    """
    env = Environment()
    template = env.from_string(body_template)
    return template.render(**context)


async def generate_api_zip(
    api: ApiModel, db: AsyncSession, options: GenerateOptions = None
) -> io.BytesIO:
    """Generate a ZIP file containing the FastAPI application for an API.

    :param api: The API model with loaded relations.
    :param db: Database session for fetching related entities.
    :param options: Optional generation options.
    :returns: BytesIO buffer containing the ZIP file.
    """
    # Fetch ALL objects (not just endpoint-selected) for full-graph FK derivation
    objects_map = await _fetch_objects(api, db)
    fields_map = await _fetch_fields(api, objects_map, db)

    # Convert to api_craft InputAPI format
    if options is None:
        options = GenerateOptions()
    input_api = _convert_to_input_api(api, objects_map, fields_map, options)

    # Generate files to a temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        generator = APIGenerator()
        generator.generate(input_api, path=temp_dir)

        # Create ZIP file
        zip_buffer = io.BytesIO()
        # api_craft uses kebab-case for directory name
        from api_craft.utils import camel_to_kebab

        project_dir = os.path.join(temp_dir, camel_to_kebab(input_api.name))

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(project_dir):
                dirs[:] = [d for d in dirs if d != "__pycache__"]
                for file in files:
                    file_path = os.path.join(root, file)
                    arc_name = os.path.relpath(file_path, project_dir)
                    zf.write(file_path, arc_name)

        zip_buffer.seek(0)
        return zip_buffer


async def _fetch_objects(
    api: ApiModel, db: AsyncSession
) -> dict[str, ObjectDefinition]:
    """Fetch ALL objects in the user's namespace for full-graph FK derivation.

    All objects are needed (not just endpoint-selected) because any object
    may have a relationship whose target is an endpoint-selected object,
    and that relationship determines FK columns on the target.

    :param api: The API model.
    :param db: Database session.
    :returns: Map of object ID to ObjectDefinition.
    """
    # Fetch all objects in the same namespace as the API, with members loaded
    query = (
        select(ObjectDefinition)
        .where(ObjectDefinition.namespace_id == api.namespace_id)
        .options(
            selectinload(ObjectDefinition.members).options(
                selectin_polymorphic(ObjectMember, [ScalarMember, RelationshipMember]),
                selectinload(ScalarMember.field),
            ),
            selectinload(ObjectDefinition.validators).selectinload(
                AppliedModelValidatorModel.template
            ),
        )
    )
    result = await db.execute(query)
    objects = result.scalars().all()

    return {obj.id: obj for obj in objects}


async def _fetch_fields(
    api: ApiModel,
    objects_map: dict[str, ObjectDefinition],
    db: AsyncSession,
) -> dict[str, FieldModel]:
    """Fetch all fields referenced by objects and path parameters.

    :param api: The API model with endpoints loaded.
    :param objects_map: Map of object ID to ObjectDefinition.
    :param db: Database session.
    :returns: Map of field ID to FieldModel.
    """
    # Collect all field IDs from scalar members
    field_ids: set[str] = set()
    for obj in objects_map.values():
        for member in obj.members:
            if isinstance(member, ScalarMember):
                field_ids.add(member.field_id)

    # Collect field IDs from endpoint path_params
    for endpoint in api.endpoints:
        for param in endpoint.path_params or []:
            field_id = param.get("fieldId")
            if field_id:
                field_ids.add(field_id)

    if not field_ids:
        return {}

    # Fetch fields with type, constraint values, and validator templates
    query = (
        select(FieldModel)
        .options(
            selectinload(FieldModel.field_type),
            selectinload(FieldModel.constraint_values).selectinload(
                FieldConstraintValueAssociation.constraint
            ),
            selectinload(FieldModel.validators).selectinload(
                AppliedFieldValidatorModel.template
            ),
        )
        .where(FieldModel.id.in_(field_ids))
    )
    result = await db.execute(query)
    fields = result.scalars().all()

    return {f.id: f for f in fields}


# --- Role -> InputField property derivation ---

_ROLE_TO_EXPOSURE: dict[str, str] = {
    "pk": "read_only",
    "writable": "read_write",
    "write_only": "write_only",
    "read_only": "read_only",
    "created_timestamp": "read_only",
    "updated_timestamp": "read_only",
    "generated_uuid": "read_only",
}

_ROLE_GENERATED_STRATEGY: dict[str, str] = {
    "created_timestamp": "now",
    "updated_timestamp": "now_on_update",
    "generated_uuid": "uuid4",
}

_ROLE_IS_PK = {"pk"}


def _derive_input_field_props(member: ScalarMember):
    """Derive InputField properties (pk, exposure, default) from a scalar member.

    :param member: A ScalarMember record.
    :returns: Tuple of (pk, exposure, default).
    """
    pk = member.role in _ROLE_IS_PK
    exposure = _ROLE_TO_EXPOSURE[member.role]

    if member.role in _ROLE_GENERATED_STRATEGY:
        default = FieldDefaultGenerated(
            kind="generated", strategy=_ROLE_GENERATED_STRATEGY[member.role]
        )
    elif member.default_value is not None:
        default = FieldDefaultLiteral(kind="literal", value=member.default_value)
    else:
        default = None

    return pk, exposure, default


def _convert_to_input_api(
    api: ApiModel,
    objects_map: dict[str, ObjectDefinition],
    fields_map: dict[str, FieldModel],
    options: GenerateOptions,
) -> InputAPI:
    """Convert database entities to api_craft InputAPI format.

    :param api: The API model.
    :param objects_map: Map of object ID to ObjectDefinition.
    :param fields_map: Map of field ID to FieldModel.
    :param options: Generation options.
    :returns: InputAPI for code generation.
    """
    # Convert objects to InputModel — single loop over members
    input_objects: list[InputModel] = []
    for obj in objects_map.values():
        fields: list[InputField] = []
        input_relationships: list[InputRelationship] = []

        for member in sorted(obj.members, key=lambda x: x.position):
            if isinstance(member, ScalarMember):
                field = fields_map.get(member.field_id)
                if field:
                    pk, exposure, default = _derive_input_field_props(member)
                    input_field = InputField(
                        name=field.name,
                        type=_build_field_type(
                            field.field_type.python_type, field.container
                        ),
                        nullable=member.is_nullable,
                        description=field.description,
                        default=default,
                        validators=_build_field_validators(field),
                        field_validators=[
                            InputResolvedFieldValidator(**rv)
                            for rv in _build_resolved_field_validators(field)
                        ],
                        pk=pk,
                        exposure=exposure,
                    )
                    fields.append(input_field)
            elif isinstance(member, RelationshipMember):
                target_obj = objects_map.get(member.target_object_id)
                target_name = target_obj.name if target_obj else "Unknown"
                input_relationships.append(
                    InputRelationship(
                        name=member.name,
                        target_model=target_name,
                        kind=member.kind,
                        inverse_name=member.inverse_name,
                        required=member.required,
                    )
                )

        input_objects.append(
            InputModel(
                name=obj.name,
                fields=fields,
                description=obj.description,
                model_validators=[
                    InputResolvedModelValidator(**rv)
                    for rv in _build_resolved_model_validators(obj)
                ],
                relationships=input_relationships,
            )
        )

    # Derive tags from endpoint tag_names
    tag_names = {ep.tag_name for ep in api.endpoints if ep.tag_name}
    input_tags = [InputTag(name=name, description="") for name in sorted(tag_names)]

    # Convert endpoints to InputEndpoint
    input_endpoints: list[InputEndpoint] = []
    for endpoint in api.endpoints:
        endpoint_name = _build_endpoint_name(endpoint.method, endpoint.path)
        tag_name = endpoint.tag_name

        # Convert path params (JSONB dicts with name and fieldId)
        path_params = None
        if endpoint.path_params:
            path_params = []
            for p in endpoint.path_params:
                field = fields_map.get(p.get("fieldId"))
                field_type = (
                    _build_field_type(field.field_type.python_type) if field else "str"
                )
                description = field.description or "" if field else ""
                path_params.append(
                    InputPathParam(
                        name=p["name"],
                        type=field_type,
                        description=description,
                    )
                )

        # Get query params from object
        query_params = None
        if endpoint.query_params_object_id:
            query_obj = objects_map.get(endpoint.query_params_object_id)
            if query_obj:
                query_params = []
                for member in sorted(query_obj.members, key=lambda x: x.position):
                    if isinstance(member, ScalarMember):
                        field = fields_map.get(member.field_id)
                        if field:
                            query_params.append(
                                InputQueryParam(
                                    name=field.name,
                                    type=_build_field_type(
                                        field.field_type.python_type
                                    ),
                                    optional=member.is_nullable,
                                    description=field.description,
                                )
                            )

        # Get object name for the endpoint's associated object
        object_name = None
        if endpoint.object_id:
            obj = objects_map.get(endpoint.object_id)
            if obj:
                object_name = obj.name

        # Method-aware request/response mapping
        method = endpoint.method.upper()
        request_name = object_name if method in ("POST", "PUT", "PATCH") else None
        response_name = None if method == "DELETE" else object_name

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
            target=object_name,
        )
        input_endpoints.append(input_endpoint)

    api_name = api.title

    return InputAPI(
        name=api_name,
        version=api.version,
        author="Median Code",
        description=api.description or "API Generated by Median Code",
        objects=input_objects,
        endpoints=input_endpoints,
        tags=input_tags,
        config=InputApiConfig(
            healthcheck=options.healthcheck,
            response_placeholders=options.response_placeholders,
            database=InputDatabaseConfig(
                enabled=options.database_enabled,
            ),
            cdk=InputCdkConfig(
                enabled=options.cdk_enabled,
                compute=options.cdk_compute,
            ),
        ),
    )


def _build_field_type(python_type: str, container: str | None = None) -> str:
    """Build a Python type annotation from the DB python_type and optional container.

    :param python_type: The python_type value from the TypeModel.
    :param container: Optional container type (e.g. 'List').
    :returns: Python type string.
    """
    if container:
        return f"{container}[{python_type}]"
    return python_type


def _build_endpoint_name(method: str, path: str) -> str:
    """Build a PascalCase endpoint name from HTTP method and path.

    :param method: HTTP method (GET, POST, etc.).
    :param path: URL path.
    :returns: PascalCase endpoint name.
    """
    import re

    parts = []
    for segment in path.strip("/").split("/"):
        if segment.startswith("{") and segment.endswith("}"):
            param_name = segment[1:-1]
            words = re.split(r"[^a-zA-Z0-9]+", param_name)
            parts.append("By" + "".join(w.capitalize() for w in words if w))
        else:
            words = re.split(r"[^a-zA-Z0-9]+", segment)
            parts.append("".join(w.capitalize() for w in words if w))

    method_prefix = method.lower().capitalize()
    path_part = "".join(parts)
    if path_part:
        return f"{method_prefix}{path_part}"
    return f"{method_prefix}Root"


def _build_field_validators(field: FieldModel) -> list[InputValidator]:
    """Convert field constraints to InputValidator list for Field() parameters.

    :param field: Field model with constraint_values loaded.
    :returns: List of InputValidator instances for code generation.
    """
    validators = []
    for cv in field.constraint_values:
        parsed = _parse_constraint_value(cv.value, cv.constraint.parameter_types)
        params = {"value": parsed} if parsed is not None else None
        validators.append(InputValidator(name=cv.constraint.name, params=params))
    return validators


def _parse_constraint_value(value: str | None, parameter_types: list[str]) -> object:
    """Parse a string constraint value to its typed Python representation.

    :param value: Raw string value from the database (may be None).
    :param parameter_types: The constraint's declared parameter types.
    :returns: Typed Python value, or None if value is None.
    """
    if value is None:
        return None
    if "int" in parameter_types:
        try:
            return int(value)
        except ValueError:
            pass
    if "float" in parameter_types:
        try:
            return float(value)
        except ValueError:
            pass
    return value


def _build_resolved_field_validators(
    field: FieldModel,
) -> list[dict]:
    """Resolve applied field validators to function definitions.

    :param field: Field model with validators and templates loaded.
    :returns: List of dicts with function_name, mode, function_body.
    """
    resolved = []
    for v in sorted(field.validators, key=lambda x: x.position):
        template = v.template
        context = v.parameters or {}
        function_body = _render_template(template.body_template, context)
        function_name = f"{template.name.lower().replace(' ', '_').replace('&', 'and')}_{field.name}"
        resolved.append(
            {
                "function_name": function_name,
                "mode": template.mode,
                "function_body": function_body,
            }
        )
    return resolved


def _build_resolved_model_validators(
    obj: ObjectDefinition,
) -> list[dict]:
    """Resolve applied model validators to function definitions.

    :param obj: Object model with validators and templates loaded.
    :returns: List of dicts with function_name, mode, function_body.
    """
    resolved = []
    for v in sorted(obj.validators, key=lambda x: x.position):
        template = v.template
        context = {**(v.parameters or {}), **v.field_mappings}
        function_body = _render_template(template.body_template, context)
        function_name = (
            f"validate_{template.name.lower().replace(' ', '_').replace('&', 'and')}"
        )
        resolved.append(
            {
                "function_name": function_name,
                "mode": template.mode,
                "function_body": function_body,
            }
        )
    return resolved
