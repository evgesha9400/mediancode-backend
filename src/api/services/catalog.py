# src/api/services/catalog.py
"""Read-only catalog service for system-managed template entities."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import Base


class CatalogService:
    """Read-only service that lists all rows of a given model, ordered by name.

    Used for system-seeded catalogs (validator templates, etc.) where the only
    operation is a full ordered listing.

    :param db: Async database session.
    :param model_class: The SQLAlchemy model to query.
    """

    def __init__(self, db: AsyncSession, model_class: type[Base]) -> None:
        self.db = db
        self.model_class = model_class

    async def list_all(self) -> list[Any]:
        """Return every row ordered by name.

        :returns: All rows of the model, ordered alphabetically by name.
        """
        result = await self.db.execute(
            select(self.model_class).order_by(self.model_class.name)
        )
        return list(result.scalars().all())
