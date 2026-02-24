"""Service for Model Validator Template operations (read-only catalogue)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.database import ModelValidatorTemplateModel


class ModelValidatorTemplateService:
    """Service for model validator template operations.

    :param db: Async database session.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_all(self) -> list[ModelValidatorTemplateModel]:
        """List all model validator templates.

        :returns: List of all model validator templates.
        """
        result = await self.db.execute(
            select(ModelValidatorTemplateModel).order_by(
                ModelValidatorTemplateModel.name
            )
        )
        return list(result.scalars().all())


def get_model_validator_template_service(
    db: AsyncSession,
) -> ModelValidatorTemplateService:
    """Factory for ModelValidatorTemplateService.

    :param db: Async database session.
    :returns: ModelValidatorTemplateService instance.
    """
    return ModelValidatorTemplateService(db)
