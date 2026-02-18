# src/api/deps.py
"""Shared FastAPI dependencies."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import CurrentUser
from api.database import get_db
from api.models.database import UserModel
from api.services.user import UserService

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_provisioned_user(user_id: CurrentUser, db: DbSession) -> UserModel:
    """Ensure the user is provisioned before proceeding.

    :param user_id: The authenticated user's ID.
    :param db: Database session.
    :returns: The provisioned user model.
    """
    service = UserService(db)
    return await service.ensure_provisioned(user_id)


ProvisionedUser = Annotated[UserModel, Depends(get_provisioned_user)]
