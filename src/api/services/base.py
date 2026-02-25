# src/api/services/base.py
"""Base service class with common functionality."""

from typing import Any, Generic, TypeVar
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import Base
from api.models.database import Namespace
from api.settings import get_settings

ModelT = TypeVar("ModelT", bound=Base)


class BaseService(Generic[ModelT]):
    """Base service class providing common CRUD operations.

    :ivar model_class: The SQLAlchemy model class for this service.
    """

    model_class: type[ModelT]

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the service with a database session.

        :param db: Async database session.
        """
        self.db = db

    async def get_by_id(
        self, entity_id: str, user_id: UUID | None = None
    ) -> ModelT | None:
        """Get an entity by ID, optionally filtering by user.

        :param entity_id: The entity's unique identifier.
        :param user_id: Optional user ID for filtering.
        :returns: The entity if found, None otherwise.
        """
        query = select(self.model_class).where(self.model_class.id == entity_id)
        if user_id and hasattr(self.model_class, "user_id"):
            query = query.where(self.model_class.user_id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_all(
        self,
        user_id: UUID | None = None,
        namespace_id: str | None = None,
    ) -> list[ModelT]:
        """List all entities, optionally filtering by user and namespace.

        :param user_id: Optional user ID for filtering.
        :param namespace_id: Optional namespace ID for filtering.
        :returns: List of matching entities.
        """
        query = select(self.model_class)
        if user_id and hasattr(self.model_class, "user_id"):
            query = query.where(self.model_class.user_id == user_id)
        if namespace_id and hasattr(self.model_class, "namespace_id"):
            query = query.where(self.model_class.namespace_id == namespace_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    def _assert_mutable(self, entity: ModelT) -> None:
        """Raise 403 if the entity belongs to the system namespace.

        Entities without a ``namespace_id`` attribute (e.g. association rows)
        are always considered mutable.

        :param entity: The entity to check.
        :raises HTTPException: If entity belongs to the system namespace.
        """
        if not hasattr(entity, "namespace_id"):
            return
        settings = get_settings()
        if str(entity.namespace_id) == str(settings.system_namespace_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="System namespace entities are immutable",
            )

    async def create(self, data: dict[str, Any]) -> ModelT:
        """Create a new entity.

        :param data: Dictionary of field values.
        :returns: The created entity.
        """
        entity = self.model_class(**data)
        self._assert_mutable(entity)
        self.db.add(entity)
        await self.db.flush()
        await self.db.refresh(entity)
        return entity

    async def update(self, entity: ModelT, data: dict[str, Any]) -> ModelT:
        """Update an existing entity.

        :param entity: The entity to update.
        :param data: Dictionary of field values to update.
        :returns: The updated entity.
        """
        self._assert_mutable(entity)
        for key, value in data.items():
            if value is not None:
                setattr(entity, key, value)
        await self.db.flush()
        await self.db.refresh(entity)
        return entity

    async def delete(self, entity: ModelT) -> None:
        """Delete an entity.

        :param entity: The entity to delete.
        """
        self._assert_mutable(entity)
        await self.db.delete(entity)
        await self.db.flush()

    async def validate_namespace_for_creation(
        self, namespace_id: Any, user_id: UUID
    ) -> Namespace:
        """Validate namespace ownership for entity creation.

        The ``Namespace.user_id == user_id`` filter implicitly excludes the
        system namespace (where ``user_id IS NULL``), so no explicit system
        namespace check is needed.

        :param namespace_id: The namespace ID to validate.
        :param user_id: The authenticated user's ID.
        :returns: The validated namespace.
        :raises HTTPException: If namespace not found or not owned by user.
        """
        result = await self.db.execute(
            select(Namespace).where(
                Namespace.id == namespace_id,
                Namespace.user_id == user_id,
            )
        )
        namespace = result.scalar_one_or_none()
        if namespace is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Namespace not found or not owned by user",
            )
        return namespace

    async def count_by_field(self, field_name: str, field_value: Any) -> int:
        """Count entities matching a field value.

        :param field_name: Name of the field to filter by.
        :param field_value: Value to match.
        :returns: Count of matching entities.
        """
        field = getattr(self.model_class, field_name)
        query = (
            select(func.count())
            .select_from(self.model_class)
            .where(field == field_value)
        )
        result = await self.db.execute(query)
        return result.scalar() or 0
