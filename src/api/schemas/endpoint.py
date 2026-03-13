# src/api/schemas/endpoint.py
"""Pydantic schemas for ApiEndpoint entity."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from api.schemas.literals import HttpMethod, ResponseShape
from api_craft.models.types import SnakeCaseName


class PathParamSchema(BaseModel):
    """Schema for a path parameter reference.

    :ivar name: Parameter name (extracted from path {braces}).
    :ivar field_id: Reference to the field definition.
    """

    name: SnakeCaseName = Field(..., examples=["user_id"])
    field_id: UUID = Field(
        ..., alias="fieldId", examples=["00000000-0000-0000-0003-000000000001"]
    )

    model_config = ConfigDict(populate_by_name=True)


class ApiEndpointCreate(BaseModel):
    """Request schema for creating an endpoint.

    :ivar api_id: API this endpoint belongs to.
    :ivar method: HTTP method.
    :ivar path: URL path with optional parameters.
    :ivar description: Endpoint description.
    :ivar tag_name: Optional tag name (must exist in the parent API's tags).
    :ivar path_params: Path parameters referencing field definitions.
    :ivar query_params_object_id: Optional query params object reference.
    :ivar object_id: Optional object reference for request/response body.
    :ivar use_envelope: Whether to wrap response in envelope.
    :ivar response_shape: Response shape (object or list).
    """

    api_id: UUID = Field(
        ..., alias="apiId", examples=["00000000-0000-0000-0005-000000000001"]
    )
    method: HttpMethod = Field(..., examples=["GET"])
    path: str = Field(..., examples=["/users/{user_id}"])
    description: str = Field(..., examples=["Get user by ID"])
    tag_name: str | None = Field(default=None, alias="tagName", examples=["Users"])
    path_params: list[PathParamSchema] = Field(..., alias="pathParams")
    query_params_object_id: UUID | None = Field(
        default=None,
        alias="queryParamsObjectId",
        examples=["00000000-0000-0000-0007-000000000001"],
    )
    object_id: UUID | None = Field(
        default=None,
        alias="objectId",
        examples=["00000000-0000-0000-0007-000000000002"],
    )
    use_envelope: bool = Field(..., alias="useEnvelope", examples=[True])
    response_shape: ResponseShape = Field(
        ..., alias="responseShape", examples=["object"]
    )


class ApiEndpointUpdate(BaseModel):
    """Request schema for updating an endpoint.

    :ivar api_id: Updated API reference.
    :ivar method: Updated HTTP method.
    :ivar path: Updated URL path.
    :ivar description: Updated description.
    :ivar tag_name: Updated tag name.
    :ivar path_params: Updated path parameters.
    :ivar query_params_object_id: Updated query params object reference.
    :ivar object_id: Updated object reference for request/response body.
    :ivar use_envelope: Updated envelope setting.
    :ivar response_shape: Updated response shape.
    """

    api_id: UUID | None = Field(
        default=None, alias="apiId", examples=["00000000-0000-0000-0005-000000000001"]
    )
    method: HttpMethod | None = Field(default=None, examples=["POST"])
    path: str | None = Field(default=None, examples=["/users"])
    description: str | None = Field(
        default=None, examples=["Updated endpoint description"]
    )
    tag_name: str | None = Field(default=None, alias="tagName")
    path_params: list[PathParamSchema] | None = Field(default=None, alias="pathParams")
    query_params_object_id: UUID | None = Field(
        default=None, alias="queryParamsObjectId"
    )
    object_id: UUID | None = Field(default=None, alias="objectId")
    use_envelope: bool | None = Field(default=None, alias="useEnvelope")
    response_shape: ResponseShape | None = Field(default=None, alias="responseShape")


class ApiEndpointResponse(BaseModel):
    """Response schema for endpoint data.

    :ivar id: Unique identifier for the endpoint.
    :ivar api_id: API this endpoint belongs to.
    :ivar method: HTTP method.
    :ivar path: URL path.
    :ivar description: Endpoint description.
    :ivar tag_name: Tag name (references a tag in the parent API).
    :ivar path_params: Path parameters referencing field definitions.
    :ivar query_params_object_id: Query params object reference.
    :ivar object_id: Object reference for request/response body.
    :ivar use_envelope: Whether response is wrapped in envelope.
    :ivar response_shape: Response shape.
    """

    id: UUID = Field(..., examples=["00000000-0000-0000-0004-000000000001"])
    api_id: UUID = Field(
        ..., alias="apiId", examples=["00000000-0000-0000-0005-000000000001"]
    )
    method: HttpMethod = Field(..., examples=["GET"])
    path: str = Field(..., examples=["/users/{user_id}"])
    description: str = Field(..., examples=["Retrieve user by ID"])
    tag_name: str | None = Field(default=None, alias="tagName", examples=["Users"])
    path_params: list[PathParamSchema] = Field(default_factory=list, alias="pathParams")
    query_params_object_id: UUID | None = Field(
        default=None,
        alias="queryParamsObjectId",
        examples=["00000000-0000-0000-0007-000000000001"],
    )
    object_id: UUID | None = Field(
        default=None,
        alias="objectId",
        examples=["00000000-0000-0000-0007-000000000002"],
    )
    use_envelope: bool = Field(..., alias="useEnvelope", examples=[True])
    response_shape: ResponseShape = Field(
        ..., alias="responseShape", examples=["object"]
    )

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
