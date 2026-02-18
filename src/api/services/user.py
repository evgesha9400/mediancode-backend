# src/api/services/user.py
"""Service for user management, provisioning, and credit operations."""

import logging

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.database import Namespace, UserModel
from api.settings import Settings, get_settings

logger = logging.getLogger(__name__)


class UserService:
    """Manages user lifecycle: provisioning, profile sync, and credits.

    On first authenticated request, creates a user row and a locked default
    namespace. Profile fields are populated later when the Clerk webhook fires.
    Seed data (types and constraints) lives in the system namespace and is
    shared read-only across all users via OR clauses in service queries.

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
        settings = get_settings()
        try:
            async with self.db.begin_nested():
                user = UserModel(
                    clerk_id=clerk_id,
                    credits_remaining=settings.default_credits,
                )
                self.db.add(user)
                await self.db.flush()

                namespace = Namespace(
                    user_id=clerk_id,
                    name="Global",
                    locked=True,
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

    async def upsert_from_clerk(self, clerk_data: dict) -> UserModel:
        """Create or update user from Clerk webhook payload.

        If the user exists (by clerk_id), updates profile fields.
        If not, creates a new user with profile fields and default credits.

        :param clerk_data: Clerk webhook payload with keys: id, email,
            first_name, last_name, username, image_url.
        :returns: The created or updated user.
        """
        settings = get_settings()
        clerk_id = clerk_data["id"]

        user = await self.get_by_clerk_id(clerk_id)
        if user is not None:
            user.email = clerk_data.get("email")
            user.first_name = clerk_data.get("first_name")
            user.last_name = clerk_data.get("last_name")
            user.username = clerk_data.get("username")
            user.image_url = clerk_data.get("image_url")
            await self.db.flush()
            await self.db.refresh(user)
            return user

        user = UserModel(
            clerk_id=clerk_id,
            email=clerk_data.get("email"),
            first_name=clerk_data.get("first_name"),
            last_name=clerk_data.get("last_name"),
            username=clerk_data.get("username"),
            image_url=clerk_data.get("image_url"),
            credits_remaining=settings.default_credits,
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def deduct_credit(self, user: UserModel) -> bool:
        """Atomically decrement credits_remaining, increment credits_used.

        When ``settings.beta_mode`` is True, returns True without deducting.
        Otherwise performs an atomic UPDATE with a credits_remaining > 0 guard.

        :param user: The user to deduct credit from.
        :returns: True if credit was deducted (or beta_mode), False if
            insufficient credits.
        """
        settings = get_settings()
        if settings.beta_mode:
            return True

        stmt = (
            update(UserModel)
            .where(UserModel.id == user.id, UserModel.credits_remaining > 0)
            .values(
                credits_remaining=UserModel.credits_remaining - 1,
                credits_used=UserModel.credits_used + 1,
            )
        )
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def has_credits(self, user: UserModel, settings: Settings) -> bool:
        """Check whether the user has credits available.

        :param user: The user to check.
        :param settings: Application settings.
        :returns: True if beta_mode is enabled or user has remaining credits.
        """
        if settings.beta_mode:
            return True
        return user.credits_remaining > 0
