# src/api/deps.py
"""Shared FastAPI dependencies."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import CurrentUser
from api.database import get_db
from api.services.user_provisioning import UserProvisioningService

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_provisioned_user(user_id: CurrentUser, db: DbSession) -> str:
    """Ensure the user is provisioned before proceeding.

    :param user_id: The authenticated user's ID.
    :param db: Database session.
    :returns: The user ID after provisioning is confirmed.
    """
    service = UserProvisioningService(db)
    await service.ensure_provisioned(user_id)
    return user_id


ProvisionedUser = Annotated[str, Depends(get_provisioned_user)]
