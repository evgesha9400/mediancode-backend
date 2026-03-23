# src/api/services/object.py
"""Service layer for Object operations."""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.models.database import (
    ApiEndpoint,
    AppliedModelValidatorModel,
    FieldModel,
    ModelValidatorTemplateModel,
    Namespace,
    ObjectDefinition,
    ObjectFieldAssociation,
    ObjectRelationship,
    TypeModel,
)
from api.schemas.object import (
    ModelValidatorInput,
    ObjectCreate,
    ObjectFieldReferenceSchema,
    ObjectUpdate,
)
from api.services.base import BaseService
from api_craft.models.validation_catalog import ALLOWED_PK_TYPES


class ObjectService(BaseService[ObjectDefinition]):
    """Service for Object CRUD operations.

    :ivar model_class: The ObjectDefinition model class.
    """

    model_class = ObjectDefinition

    # Roles whose optional and default_value are structurally forced
    _GENERATED_ROLES = {
        "pk",
        "created_timestamp",
        "updated_timestamp",
        "generated_uuid",
    }

    # Role → allowed field type base names
    _ROLE_TYPE_CONSTRAINTS: dict[str, set[str]] = {
        "pk": ALLOWED_PK_TYPES,
        "created_timestamp": {"datetime", "date"},
        "updated_timestamp": {"datetime", "date"},
        "generated_uuid": {"uuid"},
    }

    def _object_load_options(self):
        """Standard eager-load options for object queries."""
        return [
            selectinload(ObjectDefinition.field_associations),
            selectinload(ObjectDefinition.validators).selectinload(
                AppliedModelValidatorModel.template
            ),
            selectinload(ObjectDefinition.relationships),
        ]

    async def list_for_user(
        self,
        user_id: UUID,
        namespace_id: str | None = None,
    ) -> list[ObjectDefinition]:
        """List objects owned by a user.

        :param user_id: The authenticated user's ID.
        :param namespace_id: Optional namespace filter.
        :returns: List of user's objects with field associations and validators loaded.
        """
        query = (
            select(ObjectDefinition)
            .join(Namespace)
            .options(*self._object_load_options())
            .where(Namespace.user_id == user_id)
        )
        if namespace_id:
            query = query.where(ObjectDefinition.namespace_id == namespace_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_id_for_user(
        self, object_id: str, user_id: UUID
    ) -> ObjectDefinition | None:
        """Get an object if owned by the user.

        :param object_id: The object's unique identifier.
        :param user_id: The authenticated user's ID.
        :returns: The object if owned by user, None otherwise.
        """
        query = (
            select(ObjectDefinition)
            .join(Namespace)
            .options(*self._object_load_options())
            .where(
                ObjectDefinition.id == object_id,
                Namespace.user_id == user_id,
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_for_user(
        self, user_id: UUID, data: ObjectCreate
    ) -> ObjectDefinition:
        """Create a new object for a user.

        :param user_id: The authenticated user's ID.
        :param data: Object creation data.
        :returns: The created object.
        :raises HTTPException: If namespace not owned by user.
        """
        await self.validate_namespace_for_creation(data.namespace_id, user_id)

        obj = ObjectDefinition(
            namespace_id=data.namespace_id,
            user_id=user_id,
            name=data.name,
            description=data.description,
        )
        self.db.add(obj)
        await self.db.flush()

        await self._validate_role_field_types(data.fields)
        await self._set_field_associations(obj, data.fields)

        if data.validators:
            await self._set_validators(obj, data.validators)

        await self.db.refresh(obj)
        return obj

    async def update_object(
        self, obj: ObjectDefinition, data: ObjectUpdate
    ) -> ObjectDefinition:
        """Update an object.

        :param obj: The object to update.
        :param data: Update data.
        :returns: The updated object.
        """
        if data.name is not None:
            obj.name = data.name
        if data.description is not None:
            obj.description = data.description
        if data.fields is not None:
            await self._validate_role_field_types(data.fields)
            await self._set_field_associations(obj, data.fields)

        if data.validators is not None:
            await self._set_validators(obj, data.validators)

        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def delete_object(self, obj: ObjectDefinition) -> None:
        """Delete an object if not in use.

        :param obj: The object to delete.
        :raises HTTPException: If object is used in endpoints.
        """
        count_query = (
            select(func.count())
            .select_from(ApiEndpoint)
            .where(
                or_(
                    ApiEndpoint.query_params_object_id == obj.id,
                    ApiEndpoint.object_id == obj.id,
                )
            )
        )
        result = await self.db.execute(count_query)
        usage_count = result.scalar() or 0

        if usage_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete object: used in {usage_count} endpoints",
            )

        await self.db.delete(obj)
        await self.db.flush()

    async def _validate_role_field_types(
        self, fields: list[ObjectFieldReferenceSchema]
    ) -> None:
        """Validate that fields with constrained roles use compatible types.

        Checks:
        - pk role: field type must be int or uuid
        - created_timestamp / updated_timestamp: field type must be datetime or date
        - generated_uuid: field type must be uuid
        - Exactly one pk field per object (if any pk fields present)

        :param fields: List of field references to validate.
        :raises HTTPException: If a field uses an incompatible type for its role.
        """
        # Collect field IDs that need type checking, grouped by role
        role_field_ids: dict[str, list[UUID]] = {}
        for f in fields:
            if f.role in self._ROLE_TYPE_CONSTRAINTS:
                role_field_ids.setdefault(f.role, []).append(f.field_id)

        # Validate exactly one PK
        pk_count = sum(1 for f in fields if f.role == "pk")
        if pk_count > 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="An object may have at most one primary key field.",
            )

        # Fetch types for all constrained fields in one query
        all_constrained_ids = [fid for ids in role_field_ids.values() for fid in ids]
        if not all_constrained_ids:
            return

        result = await self.db.execute(
            select(FieldModel.id, TypeModel.name)
            .join(TypeModel, FieldModel.type_id == TypeModel.id)
            .where(FieldModel.id.in_(all_constrained_ids))
        )
        field_type_map = {
            row[0]: (row[1].split(".")[0] if "." in row[1] else row[1])
            for row in result.all()
        }

        for role, field_ids in role_field_ids.items():
            allowed = self._ROLE_TYPE_CONSTRAINTS[role]
            for field_id in field_ids:
                base_type = field_type_map.get(field_id)
                if base_type and base_type not in allowed:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=(
                            f"Field type '{base_type}' is not compatible with "
                            f"role '{role}'. Allowed types: "
                            f"{', '.join(sorted(allowed))}."
                        ),
                    )

    async def _set_field_associations(
        self,
        obj: ObjectDefinition,
        fields: list[ObjectFieldReferenceSchema],
    ) -> None:
        """Set field associations for an object, replacing existing ones.

        For generated roles (pk, created_timestamp, updated_timestamp,
        generated_uuid), optional and default_value are silently normalized.

        :param obj: The object to update field associations for.
        :param fields: List of field reference schemas.
        """
        delete_query = select(ObjectFieldAssociation).where(
            ObjectFieldAssociation.object_id == obj.id
        )
        result = await self.db.execute(delete_query)
        for assoc in result.scalars().all():
            await self.db.delete(assoc)

        for position, field_ref in enumerate(fields):
            # Normalize: generated roles ignore optional and default_value
            nullable = field_ref.optional
            default_value = field_ref.default_value
            if field_ref.role in self._GENERATED_ROLES:
                nullable = False
                default_value = None

            assoc = ObjectFieldAssociation(
                object_id=obj.id,
                field_id=field_ref.field_id,
                role=field_ref.role,
                nullable=nullable,
                default_value=default_value,
                position=position,
            )
            self.db.add(assoc)

        await self.db.flush()

    async def _set_validators(
        self, obj: ObjectDefinition, validators: list[ModelValidatorInput]
    ) -> None:
        """Replace model validators for an object.

        :param obj: The object model.
        :param validators: New validator inputs (empty list clears all).
        """
        await self.db.execute(
            delete(AppliedModelValidatorModel).where(
                AppliedModelValidatorModel.object_id == obj.id
            )
        )
        for position, v in enumerate(validators):
            template = await self.db.get(ModelValidatorTemplateModel, v.template_id)
            if not template:
                raise ValueError(f"Model validator template not found: {v.template_id}")
            validator = AppliedModelValidatorModel(
                object_id=obj.id,
                template_id=v.template_id,
                parameters=v.parameters,
                field_mappings=v.field_mappings,
                position=position,
            )
            self.db.add(validator)
        await self.db.flush()

    async def get_used_in_apis(self, object_id: UUID) -> list[UUID]:
        """Get API IDs where this object is used.

        :param object_id: The object's ID.
        :returns: List of API IDs.
        """
        query = (
            select(ApiEndpoint.api_id)
            .where(
                or_(
                    ApiEndpoint.query_params_object_id == object_id,
                    ApiEndpoint.object_id == object_id,
                )
            )
            .distinct()
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())


def get_object_service(db: AsyncSession) -> ObjectService:
    """Factory function for ObjectService.

    :param db: Database session.
    :returns: ObjectService instance.
    """
    return ObjectService(db)
