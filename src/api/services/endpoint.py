# src/api/services/endpoint.py
"""Service layer for ApiEndpoint operations."""

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.models.database import ApiEndpoint, EndpointParameter, Namespace
from api.schemas.endpoint import (
    ApiEndpointCreate,
    ApiEndpointUpdate,
    EndpointParameterSchema,
)
from api.services.base import BaseService
from api.settings import get_settings


class EndpointService(BaseService[ApiEndpoint]):
    """Service for ApiEndpoint CRUD operations.

    :ivar model_class: The ApiEndpoint model class.
    """

    model_class = ApiEndpoint

    async def list_for_user(
        self,
        user_id: str,
        namespace_id: str | None = None,
    ) -> list[ApiEndpoint]:
        """List endpoints accessible to a user.

        :param user_id: The authenticated user's ID.
        :param namespace_id: Optional namespace filter.
        :returns: List of accessible endpoints with path params loaded.
        """
        settings = get_settings()
        query = (
            select(ApiEndpoint)
            .join(Namespace)
            .options(selectinload(ApiEndpoint.path_params))
            .where(
                or_(
                    Namespace.user_id == user_id,
                    Namespace.id == settings.global_namespace_id,
                )
            )
        )
        if namespace_id:
            query = query.where(ApiEndpoint.namespace_id == namespace_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_id_for_user(
        self, endpoint_id: str, user_id: str
    ) -> ApiEndpoint | None:
        """Get an endpoint if accessible to the user.

        :param endpoint_id: The endpoint's unique identifier.
        :param user_id: The authenticated user's ID.
        :returns: The endpoint if accessible, None otherwise.
        """
        settings = get_settings()
        query = (
            select(ApiEndpoint)
            .join(Namespace)
            .options(selectinload(ApiEndpoint.path_params))
            .where(
                ApiEndpoint.id == endpoint_id,
                or_(
                    Namespace.user_id == user_id,
                    Namespace.id == settings.global_namespace_id,
                ),
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_for_user(
        self, user_id: str, data: ApiEndpointCreate
    ) -> ApiEndpoint:
        """Create a new endpoint for a user.

        :param user_id: The authenticated user's ID.
        :param data: Endpoint creation data.
        :returns: The created endpoint.
        """
        endpoint = ApiEndpoint(
            namespace_id=data.namespace_id,
            api_id=data.api_id,
            user_id=user_id,
            method=data.method,
            path=data.path,
            description=data.description,
            tag_id=data.tag_id,
            query_params_object_id=data.query_params_object_id,
            request_body_object_id=data.request_body_object_id,
            response_body_object_id=data.response_body_object_id,
            use_envelope=data.use_envelope,
            response_shape=data.response_shape,
        )
        self.db.add(endpoint)
        await self.db.flush()

        # Add path parameters
        await self._set_path_params(endpoint, data.path_params)

        await self.db.refresh(endpoint)
        return endpoint

    async def update_endpoint(
        self,
        endpoint: ApiEndpoint,
        data: ApiEndpointUpdate,
    ) -> ApiEndpoint:
        """Update an endpoint.

        :param endpoint: The endpoint to update.
        :param data: Update data.
        :returns: The updated endpoint.
        """
        if data.api_id is not None:
            endpoint.api_id = data.api_id
        if data.method is not None:
            endpoint.method = data.method
        if data.path is not None:
            endpoint.path = data.path
        if data.description is not None:
            endpoint.description = data.description
        if data.tag_id is not None:
            endpoint.tag_id = data.tag_id
        if data.query_params_object_id is not None:
            endpoint.query_params_object_id = data.query_params_object_id
        if data.request_body_object_id is not None:
            endpoint.request_body_object_id = data.request_body_object_id
        if data.response_body_object_id is not None:
            endpoint.response_body_object_id = data.response_body_object_id
        if data.use_envelope is not None:
            endpoint.use_envelope = data.use_envelope
        if data.response_shape is not None:
            endpoint.response_shape = data.response_shape
        if data.path_params is not None:
            await self._set_path_params(endpoint, data.path_params)

        await self.db.flush()
        await self.db.refresh(endpoint)
        return endpoint

    async def delete_endpoint(self, endpoint: ApiEndpoint) -> None:
        """Delete an endpoint.

        :param endpoint: The endpoint to delete.
        """
        await self.db.delete(endpoint)
        await self.db.flush()

    async def _set_path_params(
        self,
        endpoint: ApiEndpoint,
        params: list[EndpointParameterSchema],
    ) -> None:
        """Set path parameters for an endpoint, replacing existing ones.

        :param endpoint: The endpoint to update parameters for.
        :param params: List of parameter schemas.
        """
        # Delete existing parameters
        delete_query = select(EndpointParameter).where(
            EndpointParameter.endpoint_id == endpoint.id
        )
        result = await self.db.execute(delete_query)
        for param in result.scalars().all():
            await self.db.delete(param)

        # Add new parameters
        for position, param_data in enumerate(params):
            param = EndpointParameter(
                id=param_data.id,
                endpoint_id=endpoint.id,
                name=param_data.name,
                type=param_data.type,
                description=param_data.description,
                required=param_data.required,
                position=position,
            )
            self.db.add(param)

        await self.db.flush()


def get_endpoint_service(db: AsyncSession) -> EndpointService:
    """Factory function for EndpointService.

    :param db: Database session.
    :returns: EndpointService instance.
    """
    return EndpointService(db)
