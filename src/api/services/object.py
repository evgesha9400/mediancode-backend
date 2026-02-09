# src/api/services/object.py
"""Service layer for Object operations."""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.models.database import (
    ApiEndpoint,
    Namespace,
    ObjectDefinition,
    ObjectFieldAssociation,
)
from api.schemas.object import ObjectCreate, ObjectFieldReferenceSchema, ObjectUpdate
from api.services.base import BaseService
from api.settings import get_settings


class ObjectService(BaseService[ObjectDefinition]):
    """Service for Object CRUD operations.

    :ivar model_class: The ObjectDefinition model class.
    """

    model_class = ObjectDefinition

    async def list_for_user(
        self,
        user_id: str,
        namespace_id: str | None = None,
    ) -> list[ObjectDefinition]:
        """List objects accessible to a user.

        :param user_id: The authenticated user's ID.
        :param namespace_id: Optional namespace filter.
        :returns: List of accessible objects with field associations loaded.
        """
        settings = get_settings()
        query = (
            select(ObjectDefinition)
            .join(Namespace)
            .options(selectinload(ObjectDefinition.field_associations))
            .where(
                or_(
                    Namespace.user_id == user_id,
                    Namespace.id == settings.global_namespace_id,
                )
            )
        )
        if namespace_id:
            query = query.where(ObjectDefinition.namespace_id == namespace_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_id_for_user(
        self, object_id: str, user_id: str
    ) -> ObjectDefinition | None:
        """Get an object if accessible to the user.

        :param object_id: The object's unique identifier.
        :param user_id: The authenticated user's ID.
        :returns: The object if accessible, None otherwise.
        """
        settings = get_settings()
        query = (
            select(ObjectDefinition)
            .join(Namespace)
            .options(selectinload(ObjectDefinition.field_associations))
            .where(
                ObjectDefinition.id == object_id,
                or_(
                    Namespace.user_id == user_id,
                    Namespace.id == settings.global_namespace_id,
                ),
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_for_user(
        self, user_id: str, data: ObjectCreate
    ) -> ObjectDefinition:
        """Create a new object for a user.

        :param user_id: The authenticated user's ID.
        :param data: Object creation data.
        :returns: The created object.
        """
        obj = ObjectDefinition(
            namespace_id=data.namespace_id,
            user_id=user_id,
            name=data.name,
            description=data.description,
        )
        self.db.add(obj)
        await self.db.flush()

        # Add field associations
        await self._set_field_associations(obj, data.fields)

        await self.db.refresh(obj)
        return obj

    async def update_object(
        self, obj: ObjectDefinition, data: ObjectUpdate
    ) -> ObjectDefinition:
        """Update an object.

        :param obj: The object to update.
        :param data: Update data.
        :returns: The updated object.
        """
        if data.name is not None:
            obj.name = data.name
        if data.description is not None:
            obj.description = data.description
        if data.fields is not None:
            await self._set_field_associations(obj, data.fields)

        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def delete_object(self, obj: ObjectDefinition) -> None:
        """Delete an object if not in use.

        :param obj: The object to delete.
        :raises HTTPException: If object is used in endpoints.
        """
        # Check if object is used in any endpoints
        count_query = (
            select(func.count())
            .select_from(ApiEndpoint)
            .where(
                or_(
                    ApiEndpoint.query_params_object_id == obj.id,
                    ApiEndpoint.request_body_object_id == obj.id,
                    ApiEndpoint.response_body_object_id == obj.id,
                )
            )
        )
        result = await self.db.execute(count_query)
        usage_count = result.scalar() or 0

        if usage_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete object: used in {usage_count} endpoints",
            )

        await self.db.delete(obj)
        await self.db.flush()

    async def _set_field_associations(
        self,
        obj: ObjectDefinition,
        fields: list[ObjectFieldReferenceSchema],
    ) -> None:
        """Set field associations for an object, replacing existing ones.

        :param obj: The object to update field associations for.
        :param fields: List of field reference schemas.
        """
        # Delete existing associations
        delete_query = select(ObjectFieldAssociation).where(
            ObjectFieldAssociation.object_id == obj.id
        )
        result = await self.db.execute(delete_query)
        for assoc in result.scalars().all():
            await self.db.delete(assoc)

        # Add new associations
        for position, field_ref in enumerate(fields):
            assoc = ObjectFieldAssociation(
                object_id=obj.id,
                field_id=field_ref.field_id,
                required=field_ref.required,
                position=position,
            )
            self.db.add(assoc)

        await self.db.flush()

    async def get_used_in_apis(self, object_id: UUID) -> list[UUID]:
        """Get endpoint IDs where this object is used.

        :param object_id: The object's ID.
        :returns: List of endpoint IDs.
        """
        query = select(ApiEndpoint.id).where(
            or_(
                ApiEndpoint.query_params_object_id == object_id,
                ApiEndpoint.request_body_object_id == object_id,
                ApiEndpoint.response_body_object_id == object_id,
            )
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())


def get_object_service(db: AsyncSession) -> ObjectService:
    """Factory function for ObjectService.

    :param db: Database session.
    :returns: ObjectService instance.
    """
    return ObjectService(db)
