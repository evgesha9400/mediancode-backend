# src/api/services/field.py
"""Service layer for Field operations."""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.models.database import (
    ApiEndpoint,
    AppliedFieldValidatorModel,
    FieldConstraintValueAssociation,
    FieldModel,
    FieldValidatorTemplateModel,
    Namespace,
    ObjectFieldAssociation,
)
from api.schemas.field import (
    FieldConstraintValueInput,
    FieldCreate,
    FieldUpdate,
    FieldValidatorInput,
)
from api.services.base import BaseService


class FieldService(BaseService[FieldModel]):
    """Service for Field CRUD operations.

    :ivar model_class: The FieldModel model class.
    """

    model_class = FieldModel

    def _field_load_options(self):
        """Standard eager-load options for field queries."""
        return [
            selectinload(FieldModel.field_type),
            selectinload(FieldModel.constraint_values).selectinload(
                FieldConstraintValueAssociation.constraint
            ),
            selectinload(FieldModel.validators).selectinload(
                AppliedFieldValidatorModel.template
            ),
        ]

    async def list_for_user(
        self,
        user_id: UUID,
        namespace_id: str | None = None,
    ) -> list[FieldModel]:
        """List fields owned by a user.

        :param user_id: The authenticated user's ID.
        :param namespace_id: Optional namespace filter.
        :returns: List of user's fields with validators loaded.
        """
        query = (
            select(FieldModel)
            .join(Namespace)
            .options(*self._field_load_options())
            .where(Namespace.user_id == user_id)
        )
        if namespace_id:
            query = query.where(FieldModel.namespace_id == namespace_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_id_for_user(
        self, field_id: str, user_id: UUID
    ) -> FieldModel | None:
        """Get a field if owned by the user.

        :param field_id: The field's unique identifier.
        :param user_id: The authenticated user's ID.
        :returns: The field if owned by user, None otherwise.
        """
        query = (
            select(FieldModel)
            .join(Namespace)
            .options(*self._field_load_options())
            .where(
                FieldModel.id == field_id,
                Namespace.user_id == user_id,
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_for_user(self, user_id: UUID, data: FieldCreate) -> FieldModel:
        """Create a new field for a user.

        :param user_id: The authenticated user's ID.
        :param data: Field creation data.
        :returns: The created field.
        :raises HTTPException: If namespace not owned by user.
        """
        await self.validate_namespace_for_creation(data.namespace_id, user_id)

        field = FieldModel(
            namespace_id=data.namespace_id,
            user_id=user_id,
            name=data.name,
            type_id=data.type_id,
            description=data.description,
            default_value=data.default_value,
            container=data.container,
        )
        self.db.add(field)
        await self.db.flush()

        if data.constraints:
            await self._set_constraint_associations(field, data.constraints)

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
        if "container" in data.model_fields_set:
            field.container = data.container

        if data.constraints is not None:
            await self._set_constraint_associations(field, data.constraints)

        if data.validators is not None:
            await self._set_validators(field, data.validators)

        await self.db.flush()
        await self.db.refresh(field)
        return field

    async def _set_constraint_associations(
        self, field: FieldModel, constraints: list[FieldConstraintValueInput]
    ) -> None:
        """Replace constraint associations for a field.

        :param field: The field model.
        :param constraints: New constraint inputs (empty list clears all).
        """
        await self.db.execute(
            delete(FieldConstraintValueAssociation).where(
                FieldConstraintValueAssociation.field_id == field.id
            )
        )
        for c in constraints:
            assoc = FieldConstraintValueAssociation(
                constraint_id=c.constraint_id,
                field_id=field.id,
                value=c.value,
            )
            self.db.add(assoc)
        await self.db.flush()

    async def _set_validators(
        self, field: FieldModel, validators: list[FieldValidatorInput]
    ) -> None:
        """Replace validators for a field.

        :param field: The field model.
        :param validators: New validator inputs (empty list clears all).
        """
        await self.db.execute(
            delete(AppliedFieldValidatorModel).where(
                AppliedFieldValidatorModel.field_id == field.id
            )
        )
        for position, v in enumerate(validators):
            # Validate template exists
            template = await self.db.get(FieldValidatorTemplateModel, v.template_id)
            if not template:
                raise ValueError(f"Field validator template not found: {v.template_id}")
            validator = AppliedFieldValidatorModel(
                field_id=field.id,
                template_id=v.template_id,
                parameters=v.parameters,
                position=position,
            )
            self.db.add(validator)
        await self.db.flush()

    async def delete_field(self, field: FieldModel) -> None:
        """Delete a field if not in use.

        :param field: The field to delete.
        :raises HTTPException: If field is used in objects.
        """
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

    async def get_used_in_apis(self, field_id: UUID) -> list[UUID]:
        """Get API IDs where this field is used.

        :param field_id: The field's ID.
        :returns: List of API IDs.
        """
        objects_subquery = (
            select(ObjectFieldAssociation.object_id)
            .where(ObjectFieldAssociation.field_id == field_id)
            .subquery()
        )
        query = (
            select(ApiEndpoint.api_id)
            .where(
                or_(
                    ApiEndpoint.query_params_object_id.in_(select(objects_subquery)),
                    ApiEndpoint.object_id.in_(select(objects_subquery)),
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
