# src/api/services/model_validator.py
"""Service layer for Model Validator operations."""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.database import (
    Namespace,
    ObjectDefinition,
    ObjectModelValidatorAssociation,
    ModelValidatorModel,
)
from api.schemas.model_validator import ModelValidatorCreate, ModelValidatorUpdate
from api.services.base import BaseService
from api.settings import get_settings


class ModelValidatorService(BaseService[ModelValidatorModel]):
    """Service for Model Validator CRUD operations.

    :ivar model_class: The ModelValidatorModel model class.
    """

    model_class = ModelValidatorModel

    async def list_for_user(
        self,
        user_id: UUID,
        namespace_id: str | None = None,
    ) -> list[ModelValidatorModel]:
        """List model validators visible to a user (own namespaces + system namespace).

        :param user_id: The authenticated user's ID.
        :param namespace_id: Optional namespace filter.
        :returns: List of visible model validators.
        """
        settings = get_settings()
        query = (
            select(ModelValidatorModel)
            .join(Namespace)
            .where(
                or_(
                    Namespace.user_id == user_id,
                    Namespace.id == settings.system_namespace_id,
                )
            )
        )
        if namespace_id:
            query = query.where(ModelValidatorModel.namespace_id == namespace_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_id_for_user(
        self, validator_id: str, user_id: UUID
    ) -> ModelValidatorModel | None:
        """Get a model validator if owned by the user.

        System namespace validators (``user_id IS NULL``) are excluded, so
        this method returns ``None`` for them — making it safe to use as a gate
        before mutation operations.

        :param validator_id: The validator's unique identifier.
        :param user_id: The authenticated user's ID.
        :returns: The validator if owned by user, None otherwise.
        """
        query = (
            select(ModelValidatorModel)
            .join(Namespace)
            .where(
                ModelValidatorModel.id == validator_id,
                Namespace.user_id == user_id,
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_visible_by_id(
        self, validator_id: str, user_id: UUID
    ) -> ModelValidatorModel | None:
        """Get a model validator visible to the user (own + system).

        :param validator_id: The validator's unique identifier.
        :param user_id: The authenticated user's ID.
        :returns: The validator if visible, None otherwise.
        """
        settings = get_settings()
        query = (
            select(ModelValidatorModel)
            .join(Namespace)
            .where(
                ModelValidatorModel.id == validator_id,
                or_(
                    Namespace.user_id == user_id,
                    Namespace.id == settings.system_namespace_id,
                ),
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_for_user(
        self, user_id: UUID, data: ModelValidatorCreate
    ) -> ModelValidatorModel:
        """Create a new model validator for a user.

        :param user_id: The authenticated user's ID.
        :param data: Validator creation data.
        :returns: The created validator.
        :raises HTTPException: If namespace not owned by user.
        """
        await self.validate_namespace_for_creation(data.namespace_id, user_id)

        validator = ModelValidatorModel(
            namespace_id=data.namespace_id,
            user_id=user_id,
            name=data.name,
            mode=data.mode,
            code=data.code,
            description=data.description,
            required_fields=data.required_fields,
        )
        self.db.add(validator)
        await self.db.flush()
        await self.db.refresh(validator)
        return validator

    async def update_validator(
        self, validator: ModelValidatorModel, data: ModelValidatorUpdate
    ) -> ModelValidatorModel:
        """Update a model validator.

        :param validator: The validator to update.
        :param data: Update data.
        :returns: The updated validator.
        """
        if data.name is not None:
            validator.name = data.name
        if data.mode is not None:
            validator.mode = data.mode
        if data.code is not None:
            validator.code = data.code
        if data.description is not None:
            validator.description = data.description
        if data.required_fields is not None:
            validator.required_fields = data.required_fields

        await self.db.flush()
        await self.db.refresh(validator)
        return validator

    async def delete_validator(self, validator: ModelValidatorModel) -> None:
        """Delete a model validator if not in use.

        :param validator: The validator to delete.
        :raises HTTPException: If validator is used in objects.
        """
        count_query = (
            select(func.count())
            .select_from(ObjectModelValidatorAssociation)
            .where(ObjectModelValidatorAssociation.validator_id == validator.id)
        )
        result = await self.db.execute(count_query)
        usage_count = result.scalar() or 0

        if usage_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete validator: used in {usage_count} objects",
            )

        await self.db.delete(validator)
        await self.db.flush()

    async def get_object_counts_for_user(self, user_id: UUID) -> dict[str, int]:
        """Get count of objects per validator, scoped to the current user's objects.

        :param user_id: The authenticated user's ID.
        :returns: Dict mapping validator ID (as string) to object count.
        """
        query = (
            select(
                ObjectModelValidatorAssociation.validator_id,
                func.count(ObjectModelValidatorAssociation.id),
            )
            .join(ObjectDefinition)
            .join(Namespace)
            .where(Namespace.user_id == user_id)
            .group_by(ObjectModelValidatorAssociation.validator_id)
        )
        result = await self.db.execute(query)
        return {str(row[0]): row[1] for row in result.fetchall()}


def get_model_validator_service(db: AsyncSession) -> ModelValidatorService:
    """Factory function for ModelValidatorService.

    :param db: Database session.
    :returns: ModelValidatorService instance.
    """
    return ModelValidatorService(db)
