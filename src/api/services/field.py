# src/api/services/field.py
"""Service layer for Field operations."""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.models.database import (
    ApiEndpoint,
    FieldModel,
    FieldValidator,
    Namespace,
    ObjectFieldAssociation,
)
from api.schemas.field import FieldCreate, FieldUpdate, FieldValidatorSchema
from api.services.base import BaseService
from api.settings import get_settings


class FieldService(BaseService[FieldModel]):
    """Service for Field CRUD operations.

    :ivar model_class: The FieldModel model class.
    """

    model_class = FieldModel

    async def list_for_user(
        self,
        user_id: str,
        namespace_id: str | None = None,
    ) -> list[FieldModel]:
        """List fields accessible to a user.

        :param user_id: The authenticated user's ID.
        :param namespace_id: Optional namespace filter.
        :returns: List of accessible fields with validators loaded.
        """
        settings = get_settings()
        query = (
            select(FieldModel)
            .join(Namespace)
            .options(
                selectinload(FieldModel.validators),
                selectinload(FieldModel.field_type),
            )
            .where(
                or_(
                    Namespace.user_id == user_id,
                    Namespace.id == settings.global_namespace_id,
                )
            )
        )
        if namespace_id:
            query = query.where(FieldModel.namespace_id == namespace_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_id_for_user(
        self, field_id: str, user_id: str
    ) -> FieldModel | None:
        """Get a field if accessible to the user.

        :param field_id: The field's unique identifier.
        :param user_id: The authenticated user's ID.
        :returns: The field if accessible, None otherwise.
        """
        settings = get_settings()
        query = (
            select(FieldModel)
            .join(Namespace)
            .options(
                selectinload(FieldModel.validators),
                selectinload(FieldModel.field_type),
            )
            .where(
                FieldModel.id == field_id,
                or_(
                    Namespace.user_id == user_id,
                    Namespace.id == settings.global_namespace_id,
                ),
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_for_user(self, user_id: str, data: FieldCreate) -> FieldModel:
        """Create a new field for a user.

        :param user_id: The authenticated user's ID.
        :param data: Field creation data.
        :returns: The created field.
        """
        field = FieldModel(
            namespace_id=data.namespace_id,
            user_id=user_id,
            name=data.name,
            type_id=data.type_id,
            description=data.description,
            default_value=data.default_value,
        )
        self.db.add(field)
        await self.db.flush()

        # Add validators
        if data.validators:
            await self._set_validators(field, data.validators)

        await self.db.refresh(field)
        return field

    async def update_field(self, field: FieldModel, data: FieldUpdate) -> FieldModel:
        """Update a field.

        :param field: The field to update.
        :param data: Update data.
        :returns: The updated field.
        """
        if data.name is not None:
            field.name = data.name
        if data.description is not None:
            field.description = data.description
        if data.default_value is not None:
            field.default_value = data.default_value
        if data.validators is not None:
            await self._set_validators(field, data.validators)

        await self.db.flush()
        await self.db.refresh(field)
        return field

    async def delete_field(self, field: FieldModel) -> None:
        """Delete a field if not in use.

        :param field: The field to delete.
        :raises HTTPException: If field is used in objects.
        """
        # Check if field is used in any objects
        count_query = (
            select(func.count())
            .select_from(ObjectFieldAssociation)
            .where(ObjectFieldAssociation.field_id == field.id)
        )
        result = await self.db.execute(count_query)
        usage_count = result.scalar() or 0

        if usage_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete field: used in {usage_count} objects",
            )

        await self.db.delete(field)
        await self.db.flush()

    async def _set_validators(
        self,
        field: FieldModel,
        validators: list[FieldValidatorSchema],
    ) -> None:
        """Set validators for a field, replacing existing ones.

        :param field: The field to update validators for.
        :param validators: List of validator schemas.
        """
        # Delete existing validators
        delete_query = select(FieldValidator).where(FieldValidator.field_id == field.id)
        result = await self.db.execute(delete_query)
        for validator in result.scalars().all():
            await self.db.delete(validator)

        # Add new validators
        for validator_data in validators:
            validator = FieldValidator(
                field_id=field.id,
                name=validator_data.name,
                params=validator_data.params,
            )
            self.db.add(validator)

        await self.db.flush()

    async def get_used_in_apis(self, field_id: UUID) -> list[UUID]:
        """Get endpoint IDs where this field is used.

        A field is considered "used" if it belongs to an object that is referenced
        by an endpoint as query params, request body, or response body.

        :param field_id: The field's ID.
        :returns: List of endpoint IDs.
        """
        # Find all objects that contain this field
        objects_subquery = (
            select(ObjectFieldAssociation.object_id)
            .where(ObjectFieldAssociation.field_id == field_id)
            .subquery()
        )

        # Find all endpoints that reference these objects
        query = (
            select(ApiEndpoint.id)
            .where(
                or_(
                    ApiEndpoint.query_params_object_id.in_(select(objects_subquery)),
                    ApiEndpoint.request_body_object_id.in_(select(objects_subquery)),
                    ApiEndpoint.response_body_object_id.in_(select(objects_subquery)),
                )
            )
            .distinct()
        )

        result = await self.db.execute(query)
        return [row[0] for row in result.fetchall()]


def get_field_service(db: AsyncSession) -> FieldService:
    """Factory function for FieldService.

    :param db: Database session.
    :returns: FieldService instance.
    """
    return FieldService(db)
