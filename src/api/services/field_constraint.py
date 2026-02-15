# src/api/services/field_constraint.py
"""Service layer for Field Constraint operations."""

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.database import (
    FieldConstraintModel,
    FieldConstraintValueAssociation,
    FieldModel,
    Namespace,
)
from api.services.base import BaseService
from api.settings import get_settings


class FieldConstraintService(BaseService[FieldConstraintModel]):
    """Service for Field Constraint read operations.

    :ivar model_class: The FieldConstraintModel model class.
    """

    model_class = FieldConstraintModel

    async def list_for_user(
        self,
        user_id: str,
        namespace_id: str | None = None,
    ) -> list[FieldConstraintModel]:
        """List field constraints accessible to a user (their own + global).

        :param user_id: The authenticated user's ID.
        :param namespace_id: Optional namespace filter.
        :returns: List of accessible field constraints.
        """
        settings = get_settings()
        query = (
            select(FieldConstraintModel)
            .join(Namespace)
            .where(
                or_(
                    Namespace.user_id == user_id,
                    Namespace.id == settings.global_namespace_id,
                )
            )
        )
        if namespace_id:
            query = query.where(FieldConstraintModel.namespace_id == namespace_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_field_counts_for_user(self, user_id: str) -> dict[str, int]:
        """Get count of fields per constraint, scoped to the current user's fields.

        :param user_id: The authenticated user's ID.
        :returns: Dict mapping constraint ID (as string) to field count.
        """
        settings = get_settings()
        query = (
            select(
                FieldConstraintValueAssociation.constraint_id,
                func.count(FieldConstraintValueAssociation.id),
            )
            .join(FieldModel)
            .join(Namespace)
            .where(
                or_(
                    Namespace.user_id == user_id,
                    Namespace.id == settings.global_namespace_id,
                )
            )
            .group_by(FieldConstraintValueAssociation.constraint_id)
        )
        result = await self.db.execute(query)
        return {str(row[0]): row[1] for row in result.fetchall()}


def get_field_constraint_service(db: AsyncSession) -> FieldConstraintService:
    """Factory function for FieldConstraintService.

    :param db: Database session.
    :returns: FieldConstraintService instance.
    """
    return FieldConstraintService(db)
