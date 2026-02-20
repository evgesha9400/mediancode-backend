# src/api/services/field.py
"""Service layer for Field operations."""

from uuid import UUID

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.models.database import (
    ApiEndpoint,
    FieldConstraintValueAssociation,
    FieldModel,
    FieldValidatorAssociation,
    Namespace,
    ObjectFieldAssociation,
)
from api.schemas.field import FieldConstraintValueInput, FieldCreate, FieldUpdate
from api.schemas.field_validator import FieldValidatorReferenceInput
from api.services.base import BaseService


class FieldService(BaseService[FieldModel]):
    """Service for Field CRUD operations.

    :ivar model_class: The FieldModel model class.
    """

    model_class = FieldModel

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
            .options(
                selectinload(FieldModel.field_type),
                selectinload(FieldModel.constraint_values).selectinload(
                    FieldConstraintValueAssociation.constraint
                ),
                selectinload(FieldModel.validator_associations).selectinload(
                    FieldValidatorAssociation.validator
                ),
            )
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
            .options(
                selectinload(FieldModel.field_type),
                selectinload(FieldModel.constraint_values).selectinload(
                    FieldConstraintValueAssociation.constraint
                ),
                selectinload(FieldModel.validator_associations).selectinload(
                    FieldValidatorAssociation.validator
                ),
            )
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
        :raises HTTPException: If namespace not owned by user or is locked.
        """
        await self.validate_namespace_for_creation(data.namespace_id, user_id)

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

        if data.constraints:
            await self._set_constraint_associations(field, data.constraints)

        if data.validators:
            await self._set_validator_associations(field, data.validators)

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

        if data.constraints is not None:
            await self._set_constraint_associations(field, data.constraints)

        if data.validators is not None:
            await self._set_validator_associations(field, data.validators)

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

    async def _set_validator_associations(
        self, field: FieldModel, validators: list[FieldValidatorReferenceInput]
    ) -> None:
        """Replace validator associations for a field.

        :param field: The field model.
        :param validators: New validator inputs (empty list clears all).
        """
        await self.db.execute(
            delete(FieldValidatorAssociation).where(
                FieldValidatorAssociation.field_id == field.id
            )
        )
        for v in validators:
            assoc = FieldValidatorAssociation(
                validator_id=v.validator_id,
                field_id=field.id,
            )
            self.db.add(assoc)
        await self.db.flush()

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
