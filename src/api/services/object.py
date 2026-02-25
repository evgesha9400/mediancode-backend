# src/api/services/object.py
"""Service layer for Object operations."""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.models.database import (
    ApiEndpoint,
    AppliedModelValidatorModel,
    ModelValidatorTemplateModel,
    Namespace,
    ObjectDefinition,
    ObjectFieldAssociation,
)
from api.schemas.object import (
    ModelValidatorInput,
    ObjectCreate,
    ObjectFieldReferenceSchema,
    ObjectUpdate,
)
from api.services.base import BaseService


class ObjectService(BaseService[ObjectDefinition]):
    """Service for Object CRUD operations.

    :ivar model_class: The ObjectDefinition model class.
    """

    model_class = ObjectDefinition

    def _object_load_options(self):
        """Standard eager-load options for object queries."""
        return [
            selectinload(ObjectDefinition.field_associations),
            selectinload(ObjectDefinition.validators).selectinload(
                AppliedModelValidatorModel.template
            ),
        ]

    async def list_for_user(
        self,
        user_id: UUID,
        namespace_id: str | None = None,
    ) -> list[ObjectDefinition]:
        """List objects owned by a user.

        :param user_id: The authenticated user's ID.
        :param namespace_id: Optional namespace filter.
        :returns: List of user's objects with field associations and validators loaded.
        """
        query = (
            select(ObjectDefinition)
            .join(Namespace)
            .options(*self._object_load_options())
            .where(Namespace.user_id == user_id)
        )
        if namespace_id:
            query = query.where(ObjectDefinition.namespace_id == namespace_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_id_for_user(
        self, object_id: str, user_id: UUID
    ) -> ObjectDefinition | None:
        """Get an object if owned by the user.

        :param object_id: The object's unique identifier.
        :param user_id: The authenticated user's ID.
        :returns: The object if owned by user, None otherwise.
        """
        query = (
            select(ObjectDefinition)
            .join(Namespace)
            .options(*self._object_load_options())
            .where(
                ObjectDefinition.id == object_id,
                Namespace.user_id == user_id,
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_for_user(
        self, user_id: UUID, data: ObjectCreate
    ) -> ObjectDefinition:
        """Create a new object for a user.

        :param user_id: The authenticated user's ID.
        :param data: Object creation data.
        :returns: The created object.
        :raises HTTPException: If namespace not owned by user.
        """
        await self.validate_namespace_for_creation(data.namespace_id, user_id)

        obj = ObjectDefinition(
            namespace_id=data.namespace_id,
            user_id=user_id,
            name=data.name,
            description=data.description,
        )
        self.db.add(obj)
        await self.db.flush()

        await self._set_field_associations(obj, data.fields)

        if data.validators:
            await self._set_validators(obj, data.validators)

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

        if data.validators is not None:
            await self._set_validators(obj, data.validators)

        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def delete_object(self, obj: ObjectDefinition) -> None:
        """Delete an object if not in use.

        :param obj: The object to delete.
        :raises HTTPException: If object is used in endpoints.
        """
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
        delete_query = select(ObjectFieldAssociation).where(
            ObjectFieldAssociation.object_id == obj.id
        )
        result = await self.db.execute(delete_query)
        for assoc in result.scalars().all():
            await self.db.delete(assoc)

        for position, field_ref in enumerate(fields):
            assoc = ObjectFieldAssociation(
                object_id=obj.id,
                field_id=field_ref.field_id,
                required=field_ref.required,
                position=position,
            )
            self.db.add(assoc)

        await self.db.flush()

    async def _set_validators(
        self, obj: ObjectDefinition, validators: list[ModelValidatorInput]
    ) -> None:
        """Replace model validators for an object.

        :param obj: The object model.
        :param validators: New validator inputs (empty list clears all).
        """
        await self.db.execute(
            delete(AppliedModelValidatorModel).where(
                AppliedModelValidatorModel.object_id == obj.id
            )
        )
        for position, v in enumerate(validators):
            template = await self.db.get(ModelValidatorTemplateModel, v.template_id)
            if not template:
                raise ValueError(f"Model validator template not found: {v.template_id}")
            validator = AppliedModelValidatorModel(
                object_id=obj.id,
                template_id=v.template_id,
                parameters=v.parameters,
                field_mappings=v.field_mappings,
                position=position,
            )
            self.db.add(validator)
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
