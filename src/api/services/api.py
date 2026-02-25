# src/api/services/api.py
"""Service layer for Api operations."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.models.database import ApiModel, Namespace
from api.schemas.api import ApiCreate, ApiUpdate
from api.services.base import BaseService


class ApiService(BaseService[ApiModel]):
    """Service for Api CRUD operations.

    :ivar model_class: The ApiModel model class.
    """

    model_class = ApiModel

    async def list_for_user(
        self,
        user_id: UUID,
        namespace_id: str | None = None,
    ) -> list[ApiModel]:
        """List APIs owned by a user.

        :param user_id: The authenticated user's ID.
        :param namespace_id: Optional namespace filter.
        :returns: List of user's APIs.
        """
        query = select(ApiModel).join(Namespace).where(Namespace.user_id == user_id)
        if namespace_id:
            query = query.where(ApiModel.namespace_id == namespace_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_id_for_user(self, api_id: str, user_id: UUID) -> ApiModel | None:
        """Get an API if owned by the user.

        :param api_id: The API's unique identifier.
        :param user_id: The authenticated user's ID.
        :returns: The API if owned by user, None otherwise.
        """
        query = (
            select(ApiModel)
            .join(Namespace)
            .where(
                ApiModel.id == api_id,
                Namespace.user_id == user_id,
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_with_relations(self, api_id: str, user_id: UUID) -> ApiModel | None:
        """Get an API with all its related entities loaded.

        :param api_id: The API's unique identifier.
        :param user_id: The authenticated user's ID.
        :returns: The API with loaded relations if owned by user, None otherwise.
        """
        query = (
            select(ApiModel)
            .join(Namespace)
            .options(
                selectinload(ApiModel.endpoints),
            )
            .where(
                ApiModel.id == api_id,
                Namespace.user_id == user_id,
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_for_user(self, user_id: UUID, data: ApiCreate) -> ApiModel:
        """Create a new API for a user.

        :param user_id: The authenticated user's ID.
        :param data: API creation data.
        :returns: The created API.
        :raises HTTPException: If namespace not owned by user.
        """
        await self.validate_namespace_for_creation(data.namespace_id, user_id)

        api = ApiModel(
            namespace_id=data.namespace_id,
            user_id=user_id,
            title=data.title,
            version=data.version,
            description=data.description or "",
            base_url=data.base_url or "",
            server_url=data.server_url or "",
        )
        self.db.add(api)
        await self.db.flush()
        await self.db.refresh(api)
        return api

    async def update_api(self, api: ApiModel, data: ApiUpdate) -> ApiModel:
        """Update an API.

        :param api: The API to update.
        :param data: Update data.
        :returns: The updated API.
        """
        if data.title is not None:
            api.title = data.title
        if data.version is not None:
            api.version = data.version
        if data.description is not None:
            api.description = data.description
        if data.base_url is not None:
            api.base_url = data.base_url
        if data.server_url is not None:
            api.server_url = data.server_url

        await self.db.flush()
        await self.db.refresh(api)
        return api

    async def delete_api(self, api: ApiModel) -> None:
        """Delete an API (cascades to endpoints).

        :param api: The API to delete.
        """
        await self.db.delete(api)
        await self.db.flush()


def get_api_service(db: AsyncSession) -> ApiService:
    """Factory function for ApiService.

    :param db: Database session.
    :returns: ApiService instance.
    """
    return ApiService(db)
