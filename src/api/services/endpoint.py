# src/api/services/endpoint.py
"""Service layer for ApiEndpoint operations."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.database import ApiEndpoint, ApiModel, Namespace
from api.schemas.endpoint import ApiEndpointCreate, ApiEndpointUpdate
from api.services.base import BaseService


class EndpointService(BaseService[ApiEndpoint]):
    """Service for ApiEndpoint CRUD operations.

    :ivar model_class: The ApiEndpoint model class.
    """

    model_class = ApiEndpoint

    async def list_for_user(
        self,
        user_id: UUID,
        namespace_id: str | None = None,
    ) -> list[ApiEndpoint]:
        """List endpoints owned by a user.

        :param user_id: The authenticated user's ID.
        :param namespace_id: Optional namespace filter.
        :returns: List of user's endpoints.
        """
        query = (
            select(ApiEndpoint)
            .join(ApiModel)
            .join(Namespace)
            .where(Namespace.user_id == user_id)
        )
        if namespace_id:
            query = query.where(ApiModel.namespace_id == namespace_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_id_for_user(
        self, endpoint_id: str, user_id: UUID
    ) -> ApiEndpoint | None:
        """Get an endpoint if owned by the user.

        :param endpoint_id: The endpoint's unique identifier.
        :param user_id: The authenticated user's ID.
        :returns: The endpoint if owned by user, None otherwise.
        """
        query = (
            select(ApiEndpoint)
            .join(ApiModel)
            .join(Namespace)
            .where(
                ApiEndpoint.id == endpoint_id,
                Namespace.user_id == user_id,
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_for_user(
        self, user_id: UUID, data: ApiEndpointCreate
    ) -> ApiEndpoint:
        """Create a new endpoint for a user.

        :param user_id: The authenticated user's ID.
        :param data: Endpoint creation data.
        :returns: The created endpoint.
        """
        endpoint = ApiEndpoint(
            api_id=data.api_id,
            method=data.method,
            path=data.path,
            description=data.description,
            tag_name=data.tag_name,
            path_params=[p.model_dump(by_alias=True) for p in data.path_params],
            query_params_object_id=data.query_params_object_id,
            object_id=data.object_id,
            use_envelope=data.use_envelope,
            response_shape=data.response_shape,
        )
        self.db.add(endpoint)
        await self.db.flush()
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
        if data.tag_name is not None:
            endpoint.tag_name = data.tag_name
        if data.query_params_object_id is not None:
            endpoint.query_params_object_id = data.query_params_object_id
        if data.object_id is not None:
            endpoint.object_id = data.object_id
        if data.use_envelope is not None:
            endpoint.use_envelope = data.use_envelope
        if data.response_shape is not None:
            endpoint.response_shape = data.response_shape
        if data.path_params is not None:
            endpoint.path_params = [
                p.model_dump(by_alias=True) for p in data.path_params
            ]

        await self.db.flush()
        await self.db.refresh(endpoint)
        return endpoint

    async def delete_endpoint(self, endpoint: ApiEndpoint) -> None:
        """Delete an endpoint.

        :param endpoint: The endpoint to delete.
        """
        await self.db.delete(endpoint)
        await self.db.flush()


def get_endpoint_service(db: AsyncSession) -> EndpointService:
    """Factory function for EndpointService.

    :param db: Database session.
    :returns: EndpointService instance.
    """
    return EndpointService(db)
