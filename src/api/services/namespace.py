# src/api/services/namespace.py
"""Service layer for Namespace operations."""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.database import (
    ApiEndpoint,
    ApiModel,
    FieldModel,
    Namespace,
    ObjectDefinition,
)
from api.schemas.namespace import NamespaceCreate, NamespaceUpdate
from api.services.base import BaseService


class NamespaceService(BaseService[Namespace]):
    """Service for Namespace CRUD operations.

    :ivar model_class: The Namespace model class.
    """

    model_class = Namespace

    async def list_for_user(self, user_id: UUID) -> list[Namespace]:
        """List namespaces owned by a user.

        :param user_id: The authenticated user's ID.
        :returns: List of user's namespaces.
        """
        query = select(Namespace).where(Namespace.user_id == user_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_id_for_user(
        self, namespace_id: str, user_id: UUID
    ) -> Namespace | None:
        """Get a namespace if owned by the user.

        :param namespace_id: The namespace's unique identifier.
        :param user_id: The authenticated user's ID.
        :returns: The namespace if owned by user, None otherwise.
        """
        query = select(Namespace).where(
            Namespace.id == namespace_id,
            Namespace.user_id == user_id,
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_for_user(self, user_id: UUID, data: NamespaceCreate) -> Namespace:
        """Create a new namespace for a user.

        :param user_id: The authenticated user's ID.
        :param data: Namespace creation data.
        :returns: The created namespace.
        """
        namespace = Namespace(
            user_id=user_id,
            name=data.name,
            description=data.description,
            locked=False,
        )
        self.db.add(namespace)
        await self.db.flush()
        await self.db.refresh(namespace)
        return namespace

    async def update_namespace(
        self,
        namespace: Namespace,
        data: NamespaceUpdate,
    ) -> Namespace:
        """Update a namespace.

        :param namespace: The namespace to update.
        :param data: Update data.
        :returns: The updated namespace.
        :raises HTTPException: If namespace is locked.
        """
        if namespace.locked:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot modify locked namespace",
            )

        if data.name is not None:
            namespace.name = data.name
        if data.description is not None:
            namespace.description = data.description

        await self.db.flush()
        await self.db.refresh(namespace)
        return namespace

    async def delete_namespace(self, namespace: Namespace) -> None:
        """Delete a namespace if empty and not locked.

        :param namespace: The namespace to delete.
        :raises HTTPException: If namespace is locked or has entities.
        """
        if namespace.locked:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete locked namespace",
            )

        # Count entities in namespace
        counts = await self._count_entities(namespace.id)

        if any(counts.values()):
            parts = []
            if counts["fields"] > 0:
                parts.append(f"{counts['fields']} fields")
            if counts["objects"] > 0:
                parts.append(f"{counts['objects']} objects")
            if counts["endpoints"] > 0:
                parts.append(f"{counts['endpoints']} endpoints")
            if counts["apis"] > 0:
                parts.append(f"{counts['apis']} APIs")

            detail = f"Cannot delete namespace: contains {', '.join(parts)}"
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=detail,
            )

        await self.db.delete(namespace)
        await self.db.flush()

    async def _count_entities(self, namespace_id: str) -> dict[str, int]:
        """Count all entity types in a namespace.

        :param namespace_id: The namespace ID.
        :returns: Dictionary of entity type to count.
        """
        counts = {}

        for model, name in [
            (FieldModel, "fields"),
            (ObjectDefinition, "objects"),
            (ApiModel, "apis"),
        ]:
            query = (
                select(func.count())
                .select_from(model)
                .where(model.namespace_id == namespace_id)
            )
            result = await self.db.execute(query)
            counts[name] = result.scalar() or 0

        # ApiEndpoint has no namespace_id; count via join through ApiModel
        endpoint_query = (
            select(func.count())
            .select_from(ApiEndpoint)
            .join(ApiModel, ApiEndpoint.api_id == ApiModel.id)
            .where(ApiModel.namespace_id == namespace_id)
        )
        result = await self.db.execute(endpoint_query)
        counts["endpoints"] = result.scalar() or 0

        return counts


def get_namespace_service(db: AsyncSession) -> NamespaceService:
    """Factory function for NamespaceService.

    :param db: Database session.
    :returns: NamespaceService instance.
    """
    return NamespaceService(db)
