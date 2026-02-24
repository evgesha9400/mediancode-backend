"""Service for Field Validator Template operations (read-only catalogue)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.database import FieldValidatorTemplateModel


class FieldValidatorTemplateService:
    """Service for field validator template operations.

    :param db: Async database session.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_all(self) -> list[FieldValidatorTemplateModel]:
        """List all field validator templates.

        :returns: List of all field validator templates.
        """
        result = await self.db.execute(
            select(FieldValidatorTemplateModel).order_by(
                FieldValidatorTemplateModel.name
            )
        )
        return list(result.scalars().all())


def get_field_validator_template_service(
    db: AsyncSession,
) -> FieldValidatorTemplateService:
    """Factory for FieldValidatorTemplateService.

    :param db: Async database session.
    :returns: FieldValidatorTemplateService instance.
    """
    return FieldValidatorTemplateService(db)
