# src/api/services/user_provisioning.py
"""Service for lazy user provisioning with default namespace."""

import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.database import Namespace

logger = logging.getLogger(__name__)


class UserProvisioningService:
    """Provisions new users with a default namespace.

    On first request, creates a locked default namespace for the user.
    Seed data (types and constraints) lives in the system namespace and
    is shared read-only across all users via OR clauses in service queries.

    :ivar db: Async database session.
    """

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the service with a database session.

        :param db: Async database session.
        """
        self.db = db

    async def ensure_provisioned(self, user_id: str) -> None:
        """Ensure the user has a default namespace.

        Fast path: single indexed query on the partial unique index.
        If not provisioned, creates an empty default namespace.

        :param user_id: The authenticated user's ID.
        """
        query = select(Namespace.id).where(
            Namespace.user_id == user_id,
            Namespace.is_default.is_(True),
        )
        result = await self.db.execute(query)
        if result.scalar_one_or_none() is not None:
            return

        await self._provision_user(user_id)

    async def _provision_user(self, user_id: str) -> None:
        """Create default namespace for a new user.

        Uses a savepoint (nested transaction) so that a race-condition
        IntegrityError only rolls back the provisioning attempt, not the
        entire request's session.

        :param user_id: The user ID to provision.
        """
        try:
            async with self.db.begin_nested():
                namespace = Namespace(
                    user_id=user_id,
                    name="Global",
                    locked=True,
                    is_default=True,
                )
                self.db.add(namespace)
                await self.db.flush()
            logger.info("Provisioned user %s with default namespace", user_id)
        except IntegrityError:
            logger.debug("User %s already provisioned (concurrent request)", user_id)
