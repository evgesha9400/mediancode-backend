# src/api/services/user.py
"""Service for user management, provisioning, and generation tracking."""

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.database import GenerationModel, Namespace, UserModel
from api.settings import Settings

logger = logging.getLogger(__name__)


class UserService:
    """Manages user lifecycle: provisioning and generation tracking.

    On first authenticated request, creates a user row and a default
    namespace. Seed data (types and constraints) lives in the system namespace
    and is shared read-only across all users via OR clauses in service queries.

    :ivar db: Async database session.
    """

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the service with a database session.

        :param db: Async database session.
        """
        self.db = db

    async def ensure_provisioned(self, clerk_id: str) -> UserModel:
        """Ensure the user exists with a default namespace.

        Fast path: single indexed lookup by clerk_id. If the user does not
        exist, creates user row + default namespace in a savepoint.

        :param clerk_id: The Clerk user ID.
        :returns: The provisioned user.
        """
        user = await self.get_by_clerk_id(clerk_id)
        if user is not None:
            return user

        return await self._provision_user(clerk_id)

    async def _provision_user(self, clerk_id: str) -> UserModel:
        """Create user row and default namespace for a new user.

        Uses a savepoint (nested transaction) so that a race-condition
        IntegrityError only rolls back the provisioning attempt, not the
        entire request's session.

        :param clerk_id: The Clerk user ID to provision.
        :returns: The created (or existing) user.
        """
        try:
            async with self.db.begin_nested():
                user = UserModel(clerk_id=clerk_id)
                self.db.add(user)
                await self.db.flush()

                namespace = Namespace(
                    user_id=user.id,
                    name="Global",
                    is_default=True,
                )
                self.db.add(namespace)
                await self.db.flush()

            logger.info("Provisioned user %s with default namespace", clerk_id)
            return user
        except IntegrityError:
            logger.debug("User %s already provisioned (concurrent request)", clerk_id)
            # Re-fetch the user that was created by the concurrent request
            existing = await self.get_by_clerk_id(clerk_id)
            assert existing is not None  # noqa: S101
            return existing

    async def get_by_clerk_id(self, clerk_id: str) -> UserModel | None:
        """Lookup user by Clerk ID.

        :param clerk_id: The Clerk user ID.
        :returns: The user if found, None otherwise.
        """
        query = select(UserModel).where(UserModel.clerk_id == clerk_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def can_generate(self, user: UserModel, settings: Settings) -> bool:
        """Check whether the user can generate an API.

        In beta mode, always returns True. Otherwise counts generations in
        the current calendar month against ``free_generation_limit``.

        :param user: The user to check.
        :param settings: Application settings.
        :returns: True if the user is allowed to generate.
        """
        if settings.beta_mode:
            return True

        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        result = await self.db.execute(
            select(func.count())
            .select_from(GenerationModel)
            .where(
                GenerationModel.user_id == user.id,
                GenerationModel.created_at >= month_start,
            )
        )
        count = result.scalar_one()
        return count < settings.free_generation_limit

    async def record_generation(self, user: UserModel, api_id: UUID) -> None:
        """Record a generation event.

        Always records, even in beta mode, for analytics purposes.

        :param user: The user who triggered the generation.
        :param api_id: The API that was generated.
        """
        generation = GenerationModel(user_id=user.id, api_id=api_id)
        self.db.add(generation)
        await self.db.flush()
