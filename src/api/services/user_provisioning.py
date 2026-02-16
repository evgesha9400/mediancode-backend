# src/api/services/user_provisioning.py
"""Service for lazy user provisioning with default namespace and data."""

import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.database import FieldConstraintModel, Namespace, TypeModel
from api.settings import get_settings

logger = logging.getLogger(__name__)


class UserProvisioningService:
    """Provisions new users with a default namespace and copies of global data.

    On first request, creates a locked default namespace for the user and
    copies all types and field constraints from the global template namespace.

    :ivar db: Async database session.
    """

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the service with a database session.

        :param db: Async database session.
        """
        self.db = db

    async def ensure_provisioned(self, user_id: str) -> None:
        """Ensure the user has a default namespace with standard data.

        Fast path: single indexed query on the partial unique index.
        If not provisioned, copies global template data into a new namespace.

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
        """Create default namespace and copy global data for a new user.

        Uses a savepoint (nested transaction) so that a race-condition
        IntegrityError only rolls back the provisioning attempt, not the
        entire request's session.

        :param user_id: The user ID to provision.
        """
        try:
            async with self.db.begin_nested():
                settings = get_settings()

                # Create default namespace
                namespace = Namespace(
                    user_id=user_id,
                    name="Global",
                    locked=True,
                    is_default=True,
                )
                self.db.add(namespace)
                await self.db.flush()

                # Copy types from global template
                result = await self.db.execute(
                    select(TypeModel).where(
                        TypeModel.namespace_id == settings.global_namespace_id
                    )
                )
                global_types = list(result.scalars().all())

                # Maps for parent_type_id remapping
                id_map = {}
                obj_map = {}

                # First pass: create types without parent_type_id
                for t in global_types:
                    new_type = TypeModel(
                        namespace_id=namespace.id,
                        user_id=user_id,
                        name=t.name,
                        python_type=t.python_type,
                        description=t.description,
                        import_path=t.import_path,
                        parent_type_id=None,
                    )
                    self.db.add(new_type)
                    await self.db.flush()
                    id_map[t.id] = new_type.id
                    obj_map[t.id] = new_type

                # Second pass: set parent_type_id references directly on session objects
                for t in global_types:
                    if t.parent_type_id is not None:
                        obj_map[t.id].parent_type_id = id_map[t.parent_type_id]

                # Copy field constraints from global template
                global_constraints = await self.db.execute(
                    select(FieldConstraintModel).where(
                        FieldConstraintModel.namespace_id
                        == settings.global_namespace_id
                    )
                )
                for c in global_constraints.scalars().all():
                    new_constraint = FieldConstraintModel(
                        namespace_id=namespace.id,
                        name=c.name,
                        description=c.description,
                        parameter_type=c.parameter_type,
                        docs_url=c.docs_url,
                        compatible_types=c.compatible_types,
                    )
                    self.db.add(new_constraint)

            logger.info("Provisioned user %s with default namespace", user_id)

        except IntegrityError:
            # Race condition: another request already provisioned this user
            logger.debug("User %s already provisioned (concurrent request)", user_id)
