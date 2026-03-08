from typing import Any, Self

from pydantic import BaseModel, Field, model_validator

from api.schemas.literals import (
    HttpMethod,
    OnDeleteAction,
    ResponseShape,
    ValidatorMode,
)
from api_craft.models.types import PascalCaseName, SnakeCaseName
from api_craft.models.validators import (
    validate_endpoint_references,
    validate_model_field_types,
    validate_path_parameters,
    validate_unique_object_names,
)


class InputValidator(BaseModel):
    """Validator definition applied to a field.

    :ivar name: Validator name (e.g., 'max_length', 'gt', 'pattern').
    :ivar params: Validator parameters as a dictionary (e.g., {'value': 255}).
    """

    name: str
    params: dict[str, Any] | None = None


class InputResolvedFieldValidator(BaseModel):
    """A resolved field validator with final Python code.

    :ivar function_name: Generated function name.
    :ivar mode: Validator mode (before, after).
    :ivar function_body: Rendered Python function body.
    """

    function_name: str
    mode: ValidatorMode
    function_body: str


class InputResolvedModelValidator(BaseModel):
    """A resolved model validator with final Python code.

    :ivar function_name: Generated function name.
    :ivar mode: Validator mode (before, after).
    :ivar function_body: Rendered Python function body.
    """

    function_name: str
    mode: ValidatorMode
    function_body: str


class InputField(BaseModel):
    """Field definition for an input object.

    :ivar type: Declared field type, supporting primitive values and object references.
    :ivar name: Field identifier within the object.
    :ivar optional: Whether this field is optional (default False = required).
    :ivar description: Human-readable description of the field.
    :ivar default_value: Default value expression (Python code).
    :ivar validators: List of validators applied to this field.
    :ivar field_validators: List of resolved field validators with rendered code.
    """

    type: str
    name: SnakeCaseName
    optional: bool = False
    description: str | None = None
    default_value: str | None = None
    validators: list[InputValidator] = Field(default_factory=list)
    field_validators: list[InputResolvedFieldValidator] = Field(default_factory=list)
    pk: bool = False
    fk: str | None = None
    on_delete: OnDeleteAction = "restrict"


class InputModel(BaseModel):
    """Shared object definition with a name and typed fields.

    :ivar name: Object name in PascalCase.
    :ivar fields: Ordered collection of :class:`InputField` definitions.
    :ivar description: Human-readable description of the object.
    :ivar model_validators: List of resolved model validators with rendered code.
    """

    name: PascalCaseName
    fields: list[InputField]
    description: str | None = None
    model_validators: list[InputResolvedModelValidator] = Field(default_factory=list)


class InputQueryParam(BaseModel):
    """Query parameter definition for a view.

    :ivar name: Snake_case identifier exposed to consumers.
    :ivar type: Declared type string compatible with FastAPI annotations.
    :ivar optional: Whether this parameter is optional (default False = required).
    :ivar description: Human-readable description of the parameter.
    """

    name: SnakeCaseName
    type: str
    optional: bool = False
    description: str | None = None


class InputPathParam(BaseModel):
    """Path parameter definition for a view.

    :ivar name: Snake_case identifier extracted from the route.
    :ivar type: Declared type string for the parameter value.
    :ivar description: Human-readable description of the parameter.
    """

    name: SnakeCaseName
    type: str
    description: str | None = None


class InputEndpoint(BaseModel):
    """HTTP endpoint definition referencing shared request and response objects.

    :ivar name: Explicit operation name used in generated code.
    :ivar path: Route pattern compatible with FastAPI routing.
    :ivar method: HTTP verb for the endpoint.
    :ivar tag: Optional OpenAPI tag for documentation grouping.
    :ivar response: Name of the response object referenced by the endpoint.
    :ivar request: Name of the request object referenced by the endpoint.
    :ivar query_params: Optional query parameter definitions scoped to the endpoint.
    :ivar path_params: Optional path parameter definitions scoped to the endpoint.
    :ivar description: Human-readable description for OpenAPI documentation.
    :ivar use_envelope: Whether to wrap response in a standard envelope.
    :ivar response_shape: Response shape - 'object' for single item, 'list' for array.
    """

    name: PascalCaseName
    path: str
    method: HttpMethod
    tag: str | None = None
    response: str | None = None
    request: str | None = None
    query_params: list[InputQueryParam] | None = None
    path_params: list[InputPathParam] | None = None
    description: str | None = None
    use_envelope: bool = True
    response_shape: ResponseShape = "object"

    @model_validator(mode="after")
    def _validate_path_parameters(self) -> Self:
        """Validate that path parameters match declared path_params bidirectionally.

        :returns: The validated endpoint instance.
        :raises ValueError: If path parameters don't match bidirectionally.
        """
        validate_path_parameters(self)
        return self


class InputTag(BaseModel):
    """Tag definition for grouping endpoints in OpenAPI documentation.

    :ivar name: Tag name used for grouping.
    :ivar description: Human-readable description of the tag.
    """

    name: str
    description: str | None = None


class InputDatabaseConfig(BaseModel):
    """Database configuration for the generated API.

    :ivar enabled: Whether to generate database support.
    :ivar seed_data: Whether to generate seed data helpers.
    """

    enabled: bool = False
    seed_data: bool = True


class InputApiConfig(BaseModel):
    """Configuration flags for the generated API.

    :ivar healthcheck: Optional path used to expose a healthcheck route.
    :ivar response_placeholders: Toggle for generating placeholder response bodies.
    :ivar format_code: Toggle for formatting generated code with Black.
    :ivar generate_swagger: Toggle for auto-generating swagger.yaml from the API.
    :ivar database: Database configuration for the generated API.
    """

    healthcheck: str | None = None
    response_placeholders: bool = True
    format_code: bool = True
    generate_swagger: bool = True
    database: InputDatabaseConfig = InputDatabaseConfig()


class InputAPI(BaseModel):
    """Root model describing the API to generate.

    :ivar name: API identifier used for project structure.
    :ivar version: Semantic version string.
    :ivar author: Author metadata for packaging.
    :ivar description: Human-readable API overview.
    :ivar objects: Shared object definitions referenced across endpoints.
    :ivar endpoints: HTTP endpoints composing the API.
    :ivar tags: Tag definitions for endpoint grouping.
    :ivar config: Additional configuration for generation behavior.
    """

    name: PascalCaseName
    version: str = "0.1.0"
    author: str = "Median Code"
    description: str = "API Generated by Median Code"
    objects: list[InputModel] = Field(default_factory=list)
    endpoints: list[InputEndpoint]
    tags: list[InputTag] = Field(default_factory=list)
    config: InputApiConfig = InputApiConfig()

    @model_validator(mode="after")
    def _validate_references(self) -> Self:
        """Validate cross-object references after the model is instantiated.

        :returns: The validated model instance.
        :raises ValueError: If any reference points to an unknown object or object names are not unique.
        """
        validate_unique_object_names(self.objects)
        declared_object_names = {obj.name for obj in self.objects}
        validate_model_field_types(self.objects, declared_object_names)
        validate_endpoint_references(self.endpoints, declared_object_names)
        return self
