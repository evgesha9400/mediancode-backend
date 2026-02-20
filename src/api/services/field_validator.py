# src/api/services/field_validator.py
"""Service layer for Field Validator operations."""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.database import (
    FieldModel,
    FieldValidatorAssociation,
    FieldValidatorModel,
    Namespace,
)
from api.schemas.field_validator import FieldValidatorCreate, FieldValidatorUpdate
from api.services.base import BaseService
from api.settings import get_settings


class FieldValidatorService(BaseService[FieldValidatorModel]):
    """Service for Field Validator CRUD operations.

    :ivar model_class: The FieldValidatorModel model class.
    """

    model_class = FieldValidatorModel

    async def list_for_user(
        self,
        user_id: UUID,
        namespace_id: str | None = None,
    ) -> list[FieldValidatorModel]:
        """List field validators visible to a user (own namespaces + system namespace).

        :param user_id: The authenticated user's ID.
        :param namespace_id: Optional namespace filter.
        :returns: List of visible field validators.
        """
        settings = get_settings()
        query = (
            select(FieldValidatorModel)
            .join(Namespace)
            .where(
                or_(
                    Namespace.user_id == user_id,
                    Namespace.id == settings.system_namespace_id,
                )
            )
        )
        if namespace_id:
            query = query.where(FieldValidatorModel.namespace_id == namespace_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_id_for_user(
        self, validator_id: str, user_id: UUID
    ) -> FieldValidatorModel | None:
        """Get a field validator if owned by the user.

        System namespace validators (``user_id IS NULL``) are excluded, so
        this method returns ``None`` for them — making it safe to use as a gate
        before mutation operations.

        :param validator_id: The validator's unique identifier.
        :param user_id: The authenticated user's ID.
        :returns: The validator if owned by user, None otherwise.
        """
        query = (
            select(FieldValidatorModel)
            .join(Namespace)
            .where(
                FieldValidatorModel.id == validator_id,
                Namespace.user_id == user_id,
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_visible_by_id(
        self, validator_id: str, user_id: UUID
    ) -> FieldValidatorModel | None:
        """Get a field validator visible to the user (own + system).

        :param validator_id: The validator's unique identifier.
        :param user_id: The authenticated user's ID.
        :returns: The validator if visible, None otherwise.
        """
        settings = get_settings()
        query = (
            select(FieldValidatorModel)
            .join(Namespace)
            .where(
                FieldValidatorModel.id == validator_id,
                or_(
                    Namespace.user_id == user_id,
                    Namespace.id == settings.system_namespace_id,
                ),
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_for_user(
        self, user_id: UUID, data: FieldValidatorCreate
    ) -> FieldValidatorModel:
        """Create a new field validator for a user.

        :param user_id: The authenticated user's ID.
        :param data: Validator creation data.
        :returns: The created validator.
        :raises HTTPException: If namespace not owned by user.
        """
        await self.validate_namespace_for_creation(data.namespace_id, user_id)

        validator = FieldValidatorModel(
            namespace_id=data.namespace_id,
            user_id=user_id,
            name=data.name,
            function_name=data.function_name,
            mode=data.mode,
            function_body=data.function_body,
            description=data.description,
            compatible_types=data.compatible_types,
        )
        self.db.add(validator)
        await self.db.flush()
        await self.db.refresh(validator)
        return validator

    async def update_validator(
        self, validator: FieldValidatorModel, data: FieldValidatorUpdate
    ) -> FieldValidatorModel:
        """Update a field validator.

        :param validator: The validator to update.
        :param data: Update data.
        :returns: The updated validator.
        """
        if data.name is not None:
            validator.name = data.name
        if data.function_name is not None:
            validator.function_name = data.function_name
        if data.mode is not None:
            validator.mode = data.mode
        if data.function_body is not None:
            validator.function_body = data.function_body
        if data.description is not None:
            validator.description = data.description
        if data.compatible_types is not None:
            validator.compatible_types = data.compatible_types

        await self.db.flush()
        await self.db.refresh(validator)
        return validator

    async def delete_validator(self, validator: FieldValidatorModel) -> None:
        """Delete a field validator if not in use.

        :param validator: The validator to delete.
        :raises HTTPException: If validator is used in fields.
        """
        count_query = (
            select(func.count())
            .select_from(FieldValidatorAssociation)
            .where(FieldValidatorAssociation.validator_id == validator.id)
        )
        result = await self.db.execute(count_query)
        usage_count = result.scalar() or 0

        if usage_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete validator: used in {usage_count} fields",
            )

        await self.db.delete(validator)
        await self.db.flush()

    async def get_field_counts_for_user(self, user_id: UUID) -> dict[str, int]:
        """Get count of fields per validator, scoped to the current user's fields.

        :param user_id: The authenticated user's ID.
        :returns: Dict mapping validator ID (as string) to field count.
        """
        query = (
            select(
                FieldValidatorAssociation.validator_id,
                func.count(FieldValidatorAssociation.id),
            )
            .join(FieldModel)
            .join(Namespace)
            .where(Namespace.user_id == user_id)
            .group_by(FieldValidatorAssociation.validator_id)
        )
        result = await self.db.execute(query)
        return {str(row[0]): row[1] for row in result.fetchall()}


def get_field_validator_service(db: AsyncSession) -> FieldValidatorService:
    """Factory function for FieldValidatorService.

    :param db: Database session.
    :returns: FieldValidatorService instance.
    """
    return FieldValidatorService(db)
