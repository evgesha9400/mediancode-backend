# src/api/services/tag.py
"""Service layer for EndpointTag operations."""

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.database import ApiEndpoint, EndpointTag, Namespace
from api.schemas.tag import TagCreate, TagUpdate
from api.services.base import BaseService
from api.settings import get_settings


class TagService(BaseService[EndpointTag]):
    """Service for EndpointTag CRUD operations.

    :ivar model_class: The EndpointTag model class.
    """

    model_class = EndpointTag

    async def list_for_user(
        self,
        user_id: str,
        namespace_id: str | None = None,
    ) -> list[EndpointTag]:
        """List tags accessible to a user.

        :param user_id: The authenticated user's ID.
        :param namespace_id: Optional namespace filter.
        :returns: List of accessible tags.
        """
        settings = get_settings()
        query = (
            select(EndpointTag)
            .join(Namespace)
            .where(
                or_(
                    Namespace.user_id == user_id,
                    Namespace.id == settings.global_namespace_id,
                )
            )
        )
        if namespace_id:
            query = query.where(EndpointTag.namespace_id == namespace_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_id_for_user(self, tag_id: str, user_id: str) -> EndpointTag | None:
        """Get a tag if accessible to the user.

        :param tag_id: The tag's unique identifier.
        :param user_id: The authenticated user's ID.
        :returns: The tag if accessible, None otherwise.
        """
        settings = get_settings()
        query = (
            select(EndpointTag)
            .join(Namespace)
            .where(
                EndpointTag.id == tag_id,
                or_(
                    Namespace.user_id == user_id,
                    Namespace.id == settings.global_namespace_id,
                ),
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_for_user(self, user_id: str, data: TagCreate) -> EndpointTag:
        """Create a new tag for a user.

        :param user_id: The authenticated user's ID.
        :param data: Tag creation data.
        :returns: The created tag.
        """
        tag = EndpointTag(
            namespace_id=data.namespace_id,
            api_id=data.api_id,
            user_id=user_id,
            name=data.name,
            description=data.description,
        )
        self.db.add(tag)
        await self.db.flush()
        await self.db.refresh(tag)
        return tag

    async def update_tag(self, tag: EndpointTag, data: TagUpdate) -> EndpointTag:
        """Update a tag.

        :param tag: The tag to update.
        :param data: Update data.
        :returns: The updated tag.
        """
        if data.api_id is not None:
            tag.api_id = data.api_id
        if data.name is not None:
            tag.name = data.name
        if data.description is not None:
            tag.description = data.description

        await self.db.flush()
        await self.db.refresh(tag)
        return tag

    async def delete_tag(self, tag: EndpointTag) -> None:
        """Delete a tag if not in use.

        :param tag: The tag to delete.
        :raises HTTPException: If tag is used by endpoints.
        """
        # Check if tag is used by any endpoints
        count_query = (
            select(func.count())
            .select_from(ApiEndpoint)
            .where(ApiEndpoint.tag_id == tag.id)
        )
        result = await self.db.execute(count_query)
        usage_count = result.scalar() or 0

        if usage_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete tag: used by {usage_count} endpoints",
            )

        await self.db.delete(tag)
        await self.db.flush()


def get_tag_service(db: AsyncSession) -> TagService:
    """Factory function for TagService.

    :param db: Database session.
    :returns: TagService instance.
    """
    return TagService(db)
