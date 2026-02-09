# src/api/schemas/endpoint.py
"""Pydantic schemas for ApiEndpoint entity."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class EndpointParameterSchema(BaseModel):
    """Schema for a path parameter.

    :ivar id: Parameter identifier.
    :ivar name: Parameter name.
    :ivar type: Primitive type name.
    :ivar description: Parameter description.
    :ivar required: Whether parameter is required.
    """

    id: UUID = Field(..., examples=["00000000-0000-0000-0006-000000000001"])
    name: str = Field(..., examples=["user_id"])
    type: str = Field(..., examples=["uuid"])
    description: str = Field(..., examples=["Unique user identifier"])
    required: bool = Field(..., examples=[True])


class ApiEndpointCreate(BaseModel):
    """Request schema for creating an endpoint.

    :ivar namespace_id: Namespace this endpoint belongs to.
    :ivar api_id: API this endpoint belongs to.
    :ivar method: HTTP method.
    :ivar path: URL path with optional parameters.
    :ivar description: Endpoint description.
    :ivar tag_name: Optional tag name (must exist in the parent API's tags).
    :ivar path_params: Path parameters.
    :ivar query_params_object_id: Optional query params object reference.
    :ivar request_body_object_id: Optional request body object reference.
    :ivar response_body_object_id: Optional response body object reference.
    :ivar use_envelope: Whether to wrap response in envelope.
    :ivar response_shape: Response shape (object or list).
    """

    namespace_id: UUID = Field(..., alias="namespaceId", examples=["00000000-0000-0000-0000-000000000002"])
    api_id: UUID = Field(..., alias="apiId", examples=["00000000-0000-0000-0005-000000000001"])
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = Field(
        ..., examples=["GET"]
    )
    path: str = Field(..., examples=["/users/{user_id}"])
    description: str = Field(..., examples=["Get user by ID"])
    tag_name: str | None = Field(default=None, alias="tagName", examples=["Users"])
    path_params: list[EndpointParameterSchema] = Field(..., alias="pathParams")
    query_params_object_id: UUID | None = Field(
        default=None, alias="queryParamsObjectId", examples=["00000000-0000-0000-0007-000000000001"]
    )
    request_body_object_id: UUID | None = Field(
        default=None, alias="requestBodyObjectId", examples=["00000000-0000-0000-0007-000000000002"]
    )
    response_body_object_id: UUID | None = Field(
        default=None, alias="responseBodyObjectId", examples=["00000000-0000-0000-0007-000000000001"]
    )
    use_envelope: bool = Field(..., alias="useEnvelope", examples=[True])
    response_shape: Literal["object", "list"] = Field(
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
    :ivar request_body_object_id: Updated request body object reference.
    :ivar response_body_object_id: Updated response body object reference.
    :ivar use_envelope: Updated envelope setting.
    :ivar response_shape: Updated response shape.
    """

    api_id: UUID | None = Field(default=None, alias="apiId", examples=["00000000-0000-0000-0005-000000000001"])
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] | None = Field(
        default=None, examples=["POST"]
    )
    path: str | None = Field(default=None, examples=["/users"])
    description: str | None = Field(
        default=None, examples=["Updated endpoint description"]
    )
    tag_name: str | None = Field(default=None, alias="tagName")
    path_params: list[EndpointParameterSchema] | None = Field(
        default=None, alias="pathParams"
    )
    query_params_object_id: UUID | None = Field(
        default=None, alias="queryParamsObjectId"
    )
    request_body_object_id: UUID | None = Field(
        default=None, alias="requestBodyObjectId"
    )
    response_body_object_id: UUID | None = Field(
        default=None, alias="responseBodyObjectId"
    )
    use_envelope: bool | None = Field(default=None, alias="useEnvelope")
    response_shape: Literal["object", "list"] | None = Field(
        default=None, alias="responseShape"
    )


class ApiEndpointResponse(BaseModel):
    """Response schema for endpoint data.

    :ivar id: Unique identifier for the endpoint.
    :ivar namespace_id: Namespace this endpoint belongs to.
    :ivar api_id: API this endpoint belongs to.
    :ivar method: HTTP method.
    :ivar path: URL path.
    :ivar description: Endpoint description.
    :ivar tag_name: Tag name (references a tag in the parent API).
    :ivar path_params: Path parameters.
    :ivar query_params_object_id: Query params object reference.
    :ivar request_body_object_id: Request body object reference.
    :ivar response_body_object_id: Response body object reference.
    :ivar use_envelope: Whether response is wrapped in envelope.
    :ivar response_shape: Response shape.
    """

    id: UUID = Field(..., examples=["00000000-0000-0000-0004-000000000001"])
    namespace_id: UUID = Field(..., alias="namespaceId", examples=["00000000-0000-0000-0000-000000000001"])
    api_id: UUID = Field(..., alias="apiId", examples=["00000000-0000-0000-0005-000000000001"])
    method: str = Field(..., examples=["GET"])
    path: str = Field(..., examples=["/users/{user_id}"])
    description: str = Field(..., examples=["Retrieve user by ID"])
    tag_name: str | None = Field(default=None, alias="tagName", examples=["Users"])
    path_params: list[EndpointParameterSchema] = Field(
        default_factory=list, alias="pathParams"
    )
    query_params_object_id: UUID | None = Field(
        default=None, alias="queryParamsObjectId", examples=["00000000-0000-0000-0007-000000000001"]
    )
    request_body_object_id: UUID | None = Field(
        default=None, alias="requestBodyObjectId", examples=["00000000-0000-0000-0007-000000000002"]
    )
    response_body_object_id: UUID | None = Field(
        default=None, alias="responseBodyObjectId", examples=["00000000-0000-0000-0007-000000000001"]
    )
    use_envelope: bool = Field(..., alias="useEnvelope", examples=[True])
    response_shape: str = Field(..., alias="responseShape", examples=["object"])

    class Config:
        """Pydantic model configuration."""

        from_attributes = True
        populate_by_name = True
