# src/api/services/relationship.py
"""Service layer for Object Relationship operations."""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.database import (
    FieldModel,
    ObjectDefinition,
    ObjectFieldAssociation,
    ObjectRelationship,
)
from sqlalchemy.orm import selectinload
from api.schemas.relationship import ObjectRelationshipCreate

INVERSE_MAP: dict[str, str] = {
    "has_one": "references",
    "has_many": "references",
    "references": "has_many",
    "many_to_many": "many_to_many",
}


def _infer_inverse_name(source_object_name: str, cardinality: str) -> str:
    """Infer the inverse relationship name from the source object name.

    :param source_object_name: Name of the source object (PascalCase).
    :param cardinality: The inverse cardinality.
    :returns: Lowercase, pluralized-if-needed name.
    """
    name = source_object_name.lower()
    if cardinality in ("has_many", "many_to_many"):
        name = name + "s"
    return name


class RelationshipService:
    """Service for relationship CRUD with auto-inverse logic."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_relationship(
        self, source_object_id: UUID, data: ObjectRelationshipCreate
    ) -> ObjectRelationship:
        """Create a relationship and its auto-inverse.

        :param source_object_id: The source object's ID.
        :param data: Relationship creation data.
        :returns: The user-created relationship.
        :raises HTTPException: If source or target object not found.
        """
        result = await self.db.execute(
            select(ObjectDefinition)
            .where(ObjectDefinition.id == source_object_id)
            .options(
                selectinload(ObjectDefinition.field_associations).selectinload(
                    ObjectFieldAssociation.field
                )
            )
        )
        source = result.scalars().first()
        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source object '{source_object_id}' not found",
            )

        result = await self.db.execute(
            select(ObjectDefinition)
            .where(ObjectDefinition.id == data.target_object_id)
            .options(
                selectinload(ObjectDefinition.field_associations).selectinload(
                    ObjectFieldAssociation.field
                )
            )
        )
        target = result.scalars().first()
        if not target:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Target object '{data.target_object_id}' not found",
            )

        # Create the user's relationship
        rel = ObjectRelationship(
            source_object_id=source_object_id,
            target_object_id=data.target_object_id,
            name=data.name,
            cardinality=data.cardinality,
            is_inferred=False,
        )
        self.db.add(rel)
        await self.db.flush()

        # Create FK field if this is a references relationship
        if data.cardinality == "references":
            fk_field_id = await self._create_fk_field(source, target, data.name)
            rel.fk_field_id = fk_field_id
            await self.db.flush()

        # Create the auto-inverse
        inverse_cardinality = INVERSE_MAP[data.cardinality]
        inverse_name = _infer_inverse_name(source.name, inverse_cardinality)

        inverse = ObjectRelationship(
            source_object_id=data.target_object_id,
            target_object_id=source_object_id,
            name=inverse_name,
            cardinality=inverse_cardinality,
            is_inferred=True,
            inverse_id=rel.id,
        )
        self.db.add(inverse)
        await self.db.flush()

        # Create FK field for inverse if it is a references relationship
        if inverse_cardinality == "references":
            fk_field_id = await self._create_fk_field(target, source, inverse_name)
            inverse.fk_field_id = fk_field_id
            await self.db.flush()

        # Link the user's relationship to its inverse
        rel.inverse_id = inverse.id
        await self.db.flush()

        return rel

    async def delete_relationship(self, relationship_id: UUID) -> None:
        """Delete a relationship and its inverse.

        :param relationship_id: The relationship's ID.
        :raises HTTPException: If relationship not found.
        """
        rel = await self.db.get(ObjectRelationship, relationship_id)
        if not rel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Relationship '{relationship_id}' not found",
            )

        # Delete FK field if this relationship owns one
        if rel.fk_field_id:
            fk_field = await self.db.get(FieldModel, rel.fk_field_id)
            if fk_field:
                # Delete associations first, then the field
                assocs = await self.db.execute(
                    select(ObjectFieldAssociation).where(
                        ObjectFieldAssociation.field_id == fk_field.id
                    )
                )
                for assoc in assocs.scalars().all():
                    await self.db.delete(assoc)
                await self.db.delete(fk_field)
                await self.db.flush()

        # Delete the inverse first if it exists
        if rel.inverse_id:
            inverse = await self.db.get(ObjectRelationship, rel.inverse_id)
            if inverse:
                # Clean up inverse's FK field
                if inverse.fk_field_id:
                    fk_field = await self.db.get(FieldModel, inverse.fk_field_id)
                    if fk_field:
                        assocs = await self.db.execute(
                            select(ObjectFieldAssociation).where(
                                ObjectFieldAssociation.field_id == fk_field.id
                            )
                        )
                        for assoc in assocs.scalars().all():
                            await self.db.delete(assoc)
                        await self.db.delete(fk_field)
                        await self.db.flush()

                # Clear the inverse's back-reference to avoid FK constraint
                inverse.inverse_id = None
                await self.db.flush()
                await self.db.delete(inverse)

        await self.db.delete(rel)
        await self.db.flush()

    async def get_by_id(self, relationship_id: UUID) -> ObjectRelationship | None:
        """Get a relationship by ID.

        :param relationship_id: The relationship's ID.
        :returns: The relationship if found, None otherwise.
        """
        return await self.db.get(ObjectRelationship, relationship_id)

    async def _create_fk_field(
        self,
        source_object: ObjectDefinition,
        target_object: ObjectDefinition,
        relationship_name: str,
    ) -> UUID:
        """Create a FK field and association for a references relationship.

        :param source_object: The object that owns the FK column.
        :param target_object: The referenced object (FK points to its PK).
        :param relationship_name: Used to derive FK field name ({name}_id).
        :returns: The created field's ID.
        """
        # Find target PK field
        pk_assoc = next(
            (a for a in target_object.field_associations if a.role == "pk"),
            None,
        )
        if not pk_assoc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Target object '{target_object.name}' has no PK field",
            )
        pk_field = pk_assoc.field

        # Create FK field with same type as target PK
        fk_field = FieldModel(
            namespace_id=source_object.namespace_id,
            user_id=source_object.user_id,
            name=f"{relationship_name}_id",
            type_id=pk_field.type_id,
            description=f"FK reference to {target_object.name}",
        )
        self.db.add(fk_field)
        await self.db.flush()

        # Create association linking FK field to source object
        max_pos = max(
            (a.position for a in source_object.field_associations), default=-1
        )
        assoc = ObjectFieldAssociation(
            object_id=source_object.id,
            field_id=fk_field.id,
            role="fk",
            nullable=False,
            position=max_pos + 1,
        )
        self.db.add(assoc)
        await self.db.flush()

        return fk_field.id


def get_relationship_service(db: AsyncSession) -> RelationshipService:
    """Factory function for RelationshipService.

    :param db: Database session.
    :returns: RelationshipService instance.
    """
    return RelationshipService(db)
