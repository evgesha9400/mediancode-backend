# src/api/services/user.py
"""Service for user management, provisioning, and generation tracking."""

from datetime import datetime, timezone
import logging
from uuid import UUID

import httpx
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.database import GenerationModel, Namespace, UserModel
from api.settings import Settings, get_settings

logger = logging.getLogger(__name__)

CLERK_API_BASE = "https://api.clerk.com/v1"


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
        """Ensure the user exists with a default namespace and up-to-date profile.

        Fast path: single indexed lookup by clerk_id. If the user does not
        exist, creates user row + default namespace in a savepoint.
        Self-healing: syncs profile data from Clerk if any field is missing.

        :param clerk_id: The Clerk user ID.
        :returns: The provisioned user.
        """
        user = await self.get_by_clerk_id(clerk_id)
        if user is not None:
            if user.first_name is None or user.last_name is None or user.email is None:
                await self._sync_profile(user)
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
            await self._sync_profile(user)
            return user
        except IntegrityError:
            logger.debug("User %s already provisioned (concurrent request)", clerk_id)
            # Re-fetch the user that was created by the concurrent request
            existing = await self.get_by_clerk_id(clerk_id)
            assert existing is not None  # noqa: S101
            return existing

    async def _sync_profile(self, user: UserModel) -> None:
        """Fetch profile data from Clerk Backend API and update the user.

        Extracts first_name, last_name, and the primary email address.
        Never raises — profile sync failures must not break authentication.

        :param user: The user model to update.
        """
        settings = get_settings()
        if not settings.clerk_secret_key:
            logger.warning(
                "clerk_secret_key not configured — skipping profile sync for %s",
                user.clerk_id,
            )
            return

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{CLERK_API_BASE}/users/{user.clerk_id}",
                    headers={"Authorization": f"Bearer {settings.clerk_secret_key}"},
                    timeout=5.0,
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError:
            logger.exception("Clerk API request failed for user %s", user.clerk_id)
            return
        except Exception:
            logger.exception(
                "Unexpected error fetching Clerk profile for %s", user.clerk_id
            )
            return

        try:
            user.first_name = data.get("first_name") or None
            user.last_name = data.get("last_name") or None

            primary_email_id = data.get("primary_email_address_id")
            if primary_email_id:
                for addr in data.get("email_addresses", []):
                    if addr.get("id") == primary_email_id:
                        user.email = addr.get("email_address")
                        break

            await self.db.flush()
            logger.info(
                "Synced Clerk profile for %s (name=%s %s, email=%s)",
                user.clerk_id,
                user.first_name,
                user.last_name,
                user.email,
            )
        except Exception:
            logger.exception(
                "Failed to parse/save Clerk profile data for %s", user.clerk_id
            )

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
