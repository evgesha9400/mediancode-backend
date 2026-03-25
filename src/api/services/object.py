# src/api/services/object.py
"""Service layer for Object operations with unified member model."""

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
    TypeModel,
)
from api.models.members import ObjectMember, RelationshipMember, ScalarMember
from api.schemas.members import (
    DerivedRelationshipResponse,
    RelationshipMemberInput,
    ScalarMemberInput,
)
from api.schemas.object import (
    ModelValidatorInput,
    ObjectCreate,
    ObjectUpdate,
)
from api.services.base import BaseService
from api_craft.models.types import PascalCaseName
from api_craft.models.validation_catalog import ALLOWED_PK_TYPES


class ObjectService(BaseService[ObjectDefinition]):
    """Service for Object CRUD operations with unified members.

    :ivar model_class: The ObjectDefinition model class.
    """

    model_class = ObjectDefinition

    # Roles whose is_nullable and default_value are structurally forced
    _GENERATED_ROLES = {
        "pk",
        "created_timestamp",
        "updated_timestamp",
        "generated_uuid",
    }

    # Role -> allowed field type base names
    _ROLE_TYPE_CONSTRAINTS: dict[str, set[str]] = {
        "pk": ALLOWED_PK_TYPES,
        "created_timestamp": {"datetime", "date"},
        "updated_timestamp": {"datetime", "date"},
        "generated_uuid": {"uuid"},
    }

    def _object_load_options(self):
        """Standard eager-load options for object queries."""
        return [
            selectinload(ObjectDefinition.members).selectinload(ScalarMember.field),
            selectinload(ObjectDefinition.validators).selectinload(
                AppliedModelValidatorModel.template
            ),
        ]

    async def list_for_user(
        self,
        user_id: UUID,
        namespace_id: str | None = None,
    ) -> list[ObjectDefinition]:
        """List objects owned by a user.

        :param user_id: The authenticated user's ID.
        :param namespace_id: Optional namespace filter.
        :returns: List of user's objects with members and validators loaded.
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

        await self._validate_members(data.members, obj.id)
        await self._set_members(obj, data.members)

        if data.validators:
            await self._set_validators(obj, data.validators)

        await self.db.refresh(obj)
        return obj

    async def update_object(
        self, obj: ObjectDefinition, data: ObjectUpdate
    ) -> ObjectDefinition:
        """Update an object using reconcile-by-ID for members.

        :param obj: The object to update.
        :param data: Update data.
        :returns: The updated object.
        """
        if data.name is not None:
            obj.name = data.name
        if data.description is not None:
            obj.description = data.description
        if data.members is not None:
            await self._validate_members(data.members, obj.id)
            await self._reconcile_members(obj, data.members)

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

    # ------------------------------------------------------------------
    # Member validation
    # ------------------------------------------------------------------

    async def _validate_members(
        self,
        members: list[ScalarMemberInput | RelationshipMemberInput],
        object_id: UUID,
    ) -> None:
        """Validate members before persisting.

        :param members: List of member inputs.
        :param object_id: The owning object's ID.
        :raises HTTPException: On validation failure.
        """
        scalars = [m for m in members if isinstance(m, ScalarMemberInput)]
        relationships = [m for m in members if isinstance(m, RelationshipMemberInput)]

        # Check for duplicate names within the members array
        names = [m.name for m in members]
        if len(names) != len(set(names)):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Duplicate member names are not allowed.",
            )

        # Validate role-type constraints for scalar members
        await self._validate_role_field_types(scalars)

        # Validate relationship-specific rules
        for rel in relationships:
            await self._validate_relationship_member(rel, object_id, members)

        # Validate reconcile-by-ID type changes (reject scalar<->relationship on same id)
        for m in members:
            if m.id is not None:
                existing = await self.db.get(ObjectMember, m.id)
                if existing and existing.member_type != (
                    "scalar" if isinstance(m, ScalarMemberInput) else "relationship"
                ):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=(
                            f"Cannot change member type for id '{m.id}': "
                            f"was '{existing.member_type}', got "
                            f"'{'scalar' if isinstance(m, ScalarMemberInput) else 'relationship'}'."
                        ),
                    )

    async def _validate_relationship_member(
        self,
        rel: RelationshipMemberInput,
        object_id: UUID,
        all_members: list[ScalarMemberInput | RelationshipMemberInput],
    ) -> None:
        """Validate a single relationship member.

        :param rel: Relationship member input.
        :param object_id: The owning object's ID.
        :param all_members: All members in the current request.
        :raises HTTPException: On validation failure.
        """
        # Reject required=true for many_to_many
        if rel.kind == "many_to_many" and rel.required:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="many_to_many relationships cannot be required.",
            )

        # Self-referential: inverse_name must differ from name
        if rel.target_object_id == object_id and rel.inverse_name == rel.name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Self-referential relationship '{rel.name}' "
                    f"must have a different inverse_name."
                ),
            )

        # Check inverse_name uniqueness: (target_object_id, inverse_name) must be unique
        # across all relationship_members (excluding self if updating).
        existing_inverse_query = (
            select(func.count())
            .select_from(RelationshipMember)
            .where(
                RelationshipMember.target_object_id == rel.target_object_id,
                RelationshipMember.inverse_name == rel.inverse_name,
            )
        )
        if rel.id:
            existing_inverse_query = existing_inverse_query.where(
                RelationshipMember.id != rel.id
            )
        # Also exclude other members in this request targeting same (target, inverse_name)
        # since they are all new/updated in one batch. DB unique index will catch these.
        result = await self.db.execute(existing_inverse_query)
        if (result.scalar() or 0) > 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"inverse_name '{rel.inverse_name}' already exists "
                    f"on target object '{rel.target_object_id}'."
                ),
            )

        # Check inverse_name doesn't collide with target's authored member names
        name_collision_query = (
            select(func.count())
            .select_from(ObjectMember)
            .where(
                ObjectMember.object_id == rel.target_object_id,
                ObjectMember.name == rel.inverse_name,
            )
        )
        # If updating and target is self, the member being updated may have inverse_name
        # matching its own old name -- but DB constraints handle that.
        result = await self.db.execute(name_collision_query)
        if (result.scalar() or 0) > 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"inverse_name '{rel.inverse_name}' collides with an existing "
                    f"member name on target object '{rel.target_object_id}'."
                ),
            )

        # Check member names don't collide with incoming inverse_names targeting this object
        incoming_inverse_query = (
            select(func.count())
            .select_from(RelationshipMember)
            .where(
                RelationshipMember.target_object_id == object_id,
                RelationshipMember.inverse_name == rel.name,
            )
        )
        if rel.id:
            incoming_inverse_query = incoming_inverse_query.where(
                RelationshipMember.id != rel.id
            )
        result = await self.db.execute(incoming_inverse_query)
        if (result.scalar() or 0) > 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Member name '{rel.name}' collides with an incoming "
                    f"inverse_name targeting this object."
                ),
            )

    async def _validate_role_field_types(
        self, scalars: list[ScalarMemberInput]
    ) -> None:
        """Validate that fields with constrained roles use compatible types.

        :param scalars: List of scalar member inputs.
        :raises HTTPException: If a field uses an incompatible type for its role.
        """
        role_field_ids: dict[str, list[UUID]] = {}
        for s in scalars:
            if s.role in self._ROLE_TYPE_CONSTRAINTS:
                role_field_ids.setdefault(s.role, []).append(s.field_id)

        pk_count = sum(1 for s in scalars if s.role == "pk")
        if pk_count > 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="An object may have at most one primary key field.",
            )

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

    # ------------------------------------------------------------------
    # Member persistence
    # ------------------------------------------------------------------

    async def _set_members(
        self,
        obj: ObjectDefinition,
        members: list[ScalarMemberInput | RelationshipMemberInput],
    ) -> None:
        """Create members for a new object.

        :param obj: The object to create members for.
        :param members: Ordered list of member inputs.
        """
        for position, member in enumerate(members):
            self._create_member(obj.id, member, position)
        await self.db.flush()

    async def _reconcile_members(
        self,
        obj: ObjectDefinition,
        members: list[ScalarMemberInput | RelationshipMemberInput],
    ) -> None:
        """Reconcile members by ID: update existing, insert new, delete missing.

        :param obj: The object to update members for.
        :param members: Complete members array from the request.
        """
        # Build set of incoming IDs
        incoming_ids = {m.id for m in members if m.id is not None}

        # Delete members not in the incoming set
        existing_members = await self.db.execute(
            select(ObjectMember).where(ObjectMember.object_id == obj.id)
        )
        for existing in existing_members.scalars().all():
            if existing.id not in incoming_ids:
                await self.db.delete(existing)
        await self.db.flush()

        # Update or insert members
        for position, member in enumerate(members):
            if member.id is not None:
                # Update existing member
                existing = await self.db.get(ObjectMember, member.id)
                if existing:
                    existing.name = member.name
                    existing.position = position
                    if isinstance(member, ScalarMemberInput):
                        existing.field_id = member.field_id
                        existing.role = member.role
                        is_nullable = member.is_nullable
                        default_value = member.default_value
                        if member.role in self._GENERATED_ROLES:
                            is_nullable = False
                            default_value = None
                        existing.is_nullable = is_nullable
                        existing.default_value = default_value
                    else:
                        existing.target_object_id = member.target_object_id
                        existing.kind = member.kind
                        existing.inverse_name = member.inverse_name
                        existing.required = member.required
            else:
                # Insert new member
                self._create_member(obj.id, member, position)

        await self.db.flush()

    def _create_member(
        self,
        object_id: UUID,
        member: ScalarMemberInput | RelationshipMemberInput,
        position: int,
    ) -> None:
        """Create a single member row (base + child).

        :param object_id: The owning object's ID.
        :param member: Member input schema.
        :param position: Position index.
        """
        if isinstance(member, ScalarMemberInput):
            is_nullable = member.is_nullable
            default_value = member.default_value
            if member.role in self._GENERATED_ROLES:
                is_nullable = False
                default_value = None
            row = ScalarMember(
                object_id=object_id,
                name=member.name,
                position=position,
                field_id=member.field_id,
                role=member.role,
                is_nullable=is_nullable,
                default_value=default_value,
            )
        else:
            row = RelationshipMember(
                object_id=object_id,
                name=member.name,
                position=position,
                target_object_id=member.target_object_id,
                kind=member.kind,
                inverse_name=member.inverse_name,
                required=member.required,
            )
        self.db.add(row)

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Derived relationships
    # ------------------------------------------------------------------

    async def compute_derived_relationships(
        self, object_id: UUID
    ) -> list[DerivedRelationshipResponse]:
        """Compute incoming (derived) relationships targeting this object.

        :param object_id: The target object's ID.
        :returns: List of derived relationship response schemas.
        """
        query = (
            select(RelationshipMember)
            .where(RelationshipMember.target_object_id == object_id)
            .options(selectinload(RelationshipMember.parent_object))
        )
        result = await self.db.execute(query)
        incoming = result.scalars().all()

        derived: list[DerivedRelationshipResponse] = []
        for rel in incoming:
            source_obj = rel.parent_object
            source_name = source_obj.name if source_obj else "Unknown"
            source_obj_id = source_obj.id if source_obj else rel.object_id

            if rel.kind == "one_to_many":
                side = "many"
                implies_fk = f"{rel.inverse_name}_id"
                junction_table = None
            elif rel.kind == "one_to_one":
                side = "target"
                implies_fk = f"{rel.inverse_name}_id"
                junction_table = None
            elif rel.kind == "many_to_many":
                side = "many"
                implies_fk = None
                source_table = PascalCaseName(source_name).snake_name + "s"
                junction_table = f"{source_table}_{rel.name}"
            else:
                continue

            derived.append(
                DerivedRelationshipResponse(
                    name=rel.inverse_name,
                    source_object=source_name,
                    source_object_id=source_obj_id,
                    source_field=rel.name,
                    kind=rel.kind,
                    side=side,
                    implies_fk=implies_fk,
                    junction_table=junction_table,
                    required=rel.required,
                )
            )
        return derived

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

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
