# Inline Validators Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move validators from standalone M2M entities to 1:many child rows on fields (field validators) and objects (model validators), removing all standalone CRUD endpoints.

**Architecture:** Field validators become child rows of the `fields` table. Model validators become child rows of the `objects` table. Both are created/updated/deleted inline through their parent entity's existing CRUD endpoints. Standalone validator endpoints, services, schemas, and routes are deleted. A single Alembic migration drops old tables and creates new ones (dev-only, no data preservation).

**Tech Stack:** Python 3.13+, FastAPI, SQLAlchemy 2.0 (async), Alembic, PostgreSQL, Pydantic v2, pytest

**Design doc:** `../median-code-frontend/docs/plans/2026-02-23-inline-validators-design.md`

---

## Task 1: Alembic Migration — Drop Old Tables, Create New

**Files:**
- Create: `src/api/migrations/versions/XXXX_inline_validators.py` (use `alembic revision --autogenerate -m "inline validators"` or create manually)

**Step 1: Generate migration file**

```bash
cd /Users/evgesha/Documents/Projects/median-code-backend
poetry run alembic revision -m "inline_validators_schema"
```

**Step 2: Write the migration**

```python
"""Inline validators schema.

Move field_validators and model_validators from standalone M2M entities
to 1:many child rows on fields and objects respectively.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

# revision identifiers
revision = "FILL_IN"
down_revision = "FILL_IN"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Drop junction tables (they have FKs to validator tables)
    op.drop_table("field_validator_field_associations")
    op.drop_table("model_validator_object_associations")

    # 2. Drop old standalone validator tables
    op.drop_table("field_validators")
    op.drop_table("model_validators")

    # 3. Create new field_validators (child of fields)
    op.create_table(
        "field_validators",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("field_id", PgUUID(as_uuid=True), sa.ForeignKey("fields.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("function_name", sa.Text(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("function_body", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
    )

    # 4. Create new model_validators (child of objects)
    op.create_table(
        "model_validators",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("object_id", PgUUID(as_uuid=True), sa.ForeignKey("objects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("function_name", sa.Text(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("function_body", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("model_validators")
    op.drop_table("field_validators")
    # Old tables are not recreated (dev-only, clean swap)
```

**Step 3: Verify migration compiles**

```bash
poetry run alembic check
```

**Step 4: Commit**

```bash
git add src/api/migrations/
git commit -m "feat(db): add inline validators migration

Drop standalone field_validators, model_validators, and their junction
tables. Create new child tables with field_id/object_id FK.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 2: Rewrite SQLAlchemy Models

**Files:**
- Modify: `src/api/models/database.py`

**Step 1: Rewrite FieldValidatorModel (currently lines 320-359)**

Replace the entire `FieldValidatorModel` class with:

```python
class FieldValidatorModel(Base):
    """Field validator function owned by a specific field.

    :ivar id: Unique identifier for the validator.
    :ivar field_id: Reference to the parent field.
    :ivar function_name: Name of the validation function.
    :ivar mode: Validator mode ("before", "after", "wrap", "plain").
    :ivar function_body: Python source code of the validator function.
    :ivar description: Optional description of the validator.
    :ivar position: Display order position.
    """

    __tablename__ = "field_validators"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    field_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("fields.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    function_name: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    function_body: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(default=0, nullable=False)

    # Relationships
    field: Mapped["FieldModel"] = relationship(back_populates="validators")
```

**Step 2: Delete FieldValidatorAssociation class entirely (currently lines 362-392)**

Remove the entire `FieldValidatorAssociation` class.

**Step 3: Rewrite ModelValidatorModel (currently lines 461-500)**

Replace the entire `ModelValidatorModel` class with:

```python
class ModelValidatorModel(Base):
    """Model validator function owned by a specific object.

    :ivar id: Unique identifier for the validator.
    :ivar object_id: Reference to the parent object.
    :ivar function_name: Name of the validation function.
    :ivar mode: Validator mode ("before", "after").
    :ivar function_body: Python source code of the validator function.
    :ivar description: Optional description of the validator.
    :ivar position: Display order position.
    """

    __tablename__ = "model_validators"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    object_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("objects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    function_name: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    function_body: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(default=0, nullable=False)

    # Relationships
    object: Mapped["ObjectDefinition"] = relationship(back_populates="validators")
```

**Step 4: Delete ObjectModelValidatorAssociation class entirely (currently lines 503-533)**

Remove the entire `ObjectModelValidatorAssociation` class.

**Step 5: Update FieldModel relationships (currently lines 275-317)**

Replace the `validator_associations` relationship (line 315-317) with:

```python
    validators: Mapped[list["FieldValidatorModel"]] = relationship(
        back_populates="field", cascade="all, delete-orphan",
        order_by="FieldValidatorModel.position",
    )
```

**Step 6: Update ObjectDefinition — add validators relationship (currently lines 395-424)**

Add after `field_associations` relationship (line 422-424):

```python
    validators: Mapped[list["ModelValidatorModel"]] = relationship(
        back_populates="object", cascade="all, delete-orphan",
        order_by="ModelValidatorModel.position",
    )
```

**Step 7: Update UserModel — remove validator backrefs (currently lines 62-67)**

Delete these two relationships from `UserModel`:

```python
    # DELETE these lines:
    field_validators: Mapped[list["FieldValidatorModel"]] = relationship(
        back_populates="user"
    )
    model_validators: Mapped[list["ModelValidatorModel"]] = relationship(
        back_populates="user"
    )
```

**Step 8: Update Namespace — remove validator backrefs (currently lines 149-154)**

Delete these two relationships from `Namespace`:

```python
    # DELETE these lines:
    field_validators: Mapped[list["FieldValidatorModel"]] = relationship(
        back_populates="namespace", cascade="all, delete-orphan"
    )
    model_validators: Mapped[list["ModelValidatorModel"]] = relationship(
        back_populates="namespace", cascade="all, delete-orphan"
    )
```

**Step 9: Clean up unused imports**

Remove `ARRAY` from the imports line (line 9) if no other model uses it. Check if any remaining model uses `ARRAY(Text)` — `FieldConstraintModel` still uses it, so keep `ARRAY`. However, verify no broken references remain to deleted classes.

**Step 10: Commit**

```bash
git add src/api/models/database.py
git commit -m "refactor(models): inline validators as child rows

Rewrite FieldValidatorModel and ModelValidatorModel as 1:many children
of fields and objects. Delete junction tables and standalone backrefs.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 3: Rewrite Pydantic Schemas

**Files:**
- Delete: `src/api/schemas/field_validator.py`
- Delete: `src/api/schemas/model_validator.py`
- Modify: `src/api/schemas/field.py`
- Modify: `src/api/schemas/object.py`

**Step 1: Rewrite `src/api/schemas/field.py`**

Replace the entire file with:

```python
# src/api/schemas/field.py
"""Pydantic schemas for Field entity."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FieldConstraintValueInput(BaseModel):
    """Request schema for attaching a field constraint to a field.

    :ivar constraint_id: Reference to the field constraint definition.
    :ivar value: Parameter value for the constraint (null for parameterless).
    """

    constraint_id: UUID = Field(..., alias="constraintId")
    value: str | None = Field(default=None)

    model_config = ConfigDict(populate_by_name=True)


class FieldConstraintValueResponse(BaseModel):
    """Response schema for a field constraint value attached to a field.

    :ivar constraint_id: Reference to the field constraint definition.
    :ivar name: Constraint name.
    :ivar value: Parameter value for the constraint.
    """

    constraint_id: UUID = Field(..., alias="constraintId")
    name: str
    value: str | None = Field(default=None)

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class FieldValidatorInput(BaseModel):
    """Request schema for an inline field validator definition.

    :ivar function_name: Python function name for the validator.
    :ivar mode: Validator mode (before, after, wrap, plain).
    :ivar function_body: Python source code of the validator function.
    :ivar description: Optional description.
    """

    function_name: str = Field(..., alias="functionName")
    mode: str
    function_body: str = Field(..., alias="functionBody")
    description: str | None = None

    model_config = ConfigDict(populate_by_name=True)


class FieldValidatorResponse(BaseModel):
    """Response schema for a field validator attached to a field.

    :ivar id: Unique identifier for the validator.
    :ivar function_name: Python function name.
    :ivar mode: Validator mode.
    :ivar function_body: Python source code.
    :ivar description: Optional description.
    """

    id: UUID
    function_name: str = Field(..., alias="functionName")
    mode: str
    function_body: str = Field(..., alias="functionBody")
    description: str | None = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class FieldCreate(BaseModel):
    """Request schema for creating a field.

    :ivar namespace_id: Namespace this field belongs to.
    :ivar name: Field name.
    :ivar type_id: Reference to the type definition UUID.
    :ivar description: Field description.
    :ivar default_value: Default value expression.
    :ivar constraints: Constraints to attach to this field.
    :ivar validators: Inline validator definitions for this field.
    """

    namespace_id: UUID = Field(
        ..., alias="namespaceId", examples=["00000000-0000-0000-0000-000000000002"]
    )
    name: str = Field(..., examples=["email"])
    type_id: UUID = Field(
        ..., alias="typeId", examples=["00000000-0000-0000-0001-000000000001"]
    )
    description: str | None = Field(default=None, examples=["User email address"])
    default_value: str | None = Field(default=None, alias="defaultValue", examples=[""])
    constraints: list[FieldConstraintValueInput] = Field(default_factory=list)
    validators: list[FieldValidatorInput] = Field(default_factory=list)


class FieldUpdate(BaseModel):
    """Request schema for updating a field.

    :ivar name: Updated field name.
    :ivar description: Updated description.
    :ivar default_value: Updated default value.
    :ivar constraints: Updated constraints (None = don't touch, [] = clear all).
    :ivar validators: Updated validators (None = don't touch, [] = clear all).
    """

    name: str | None = Field(default=None, examples=["updated_field_name"])
    description: str | None = Field(default=None, examples=["Updated description"])
    default_value: str | None = Field(
        default=None, alias="defaultValue", examples=["new_default"]
    )
    constraints: list[FieldConstraintValueInput] | None = Field(default=None)
    validators: list[FieldValidatorInput] | None = Field(default=None)


class FieldResponse(BaseModel):
    """Response schema for field data.

    :ivar id: Unique identifier for the field.
    :ivar namespace_id: Namespace this field belongs to.
    :ivar name: Field name.
    :ivar type_id: Reference to the type definition UUID.
    :ivar description: Field description.
    :ivar default_value: Default value expression.
    :ivar used_in_apis: Array of endpoint IDs where this field is used.
    :ivar constraints: Constraints attached to this field.
    :ivar validators: Validators attached to this field.
    """

    id: UUID = Field(..., examples=["00000000-0000-0000-0003-000000000001"])
    namespace_id: UUID = Field(
        ..., alias="namespaceId", examples=["00000000-0000-0000-0000-000000000001"]
    )
    name: str = Field(..., examples=["email"])
    type_id: UUID = Field(
        ..., alias="typeId", examples=["00000000-0000-0000-0001-000000000001"]
    )
    description: str | None = Field(default=None, examples=["User email address"])
    default_value: str | None = Field(default=None, alias="defaultValue", examples=[""])
    used_in_apis: list[UUID] = Field(
        default_factory=list,
        alias="usedInApis",
        examples=[["00000000-0000-0000-0004-000000000001"]],
    )
    constraints: list[FieldConstraintValueResponse] = Field(default_factory=list)
    validators: list[FieldValidatorResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
```

**Step 2: Rewrite `src/api/schemas/object.py`**

Replace the entire file with:

```python
# src/api/schemas/object.py
"""Pydantic schemas for Object entity."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ObjectFieldReferenceSchema(BaseModel):
    """Schema for a field reference in an object.

    :ivar field_id: Reference to Field.id.
    :ivar required: Whether this field is required in the object.
    """

    field_id: UUID = Field(
        ..., alias="fieldId", examples=["00000000-0000-0000-0003-000000000001"]
    )
    required: bool = Field(..., examples=[True])

    model_config = ConfigDict(populate_by_name=True)


class ModelValidatorInput(BaseModel):
    """Request schema for an inline model validator definition.

    :ivar function_name: Python function name for the validator.
    :ivar mode: Validator mode (before, after).
    :ivar function_body: Python source code of the validator function.
    :ivar description: Optional description.
    """

    function_name: str = Field(..., alias="functionName")
    mode: str
    function_body: str = Field(..., alias="functionBody")
    description: str | None = None

    model_config = ConfigDict(populate_by_name=True)


class ModelValidatorResponse(BaseModel):
    """Response schema for a model validator attached to an object.

    :ivar id: Unique identifier for the validator.
    :ivar function_name: Python function name.
    :ivar mode: Validator mode.
    :ivar function_body: Python source code.
    :ivar description: Optional description.
    """

    id: UUID
    function_name: str = Field(..., alias="functionName")
    mode: str
    function_body: str = Field(..., alias="functionBody")
    description: str | None = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ObjectCreate(BaseModel):
    """Request schema for creating an object.

    :ivar namespace_id: Namespace this object belongs to.
    :ivar name: Object name.
    :ivar description: Object description.
    :ivar fields: List of field references.
    :ivar validators: Inline model validator definitions for this object.
    """

    namespace_id: UUID = Field(
        ..., alias="namespaceId", examples=["00000000-0000-0000-0000-000000000002"]
    )
    name: str = Field(..., examples=["User"])
    description: str | None = Field(default=None, examples=["User object definition"])
    fields: list[ObjectFieldReferenceSchema] = Field(...)
    validators: list[ModelValidatorInput] = Field(default_factory=list)


class ObjectUpdate(BaseModel):
    """Request schema for updating an object.

    :ivar name: Updated object name.
    :ivar description: Updated description.
    :ivar fields: Updated list of field references (None = don't touch).
    :ivar validators: Updated validators (None = don't touch, [] = clear all).
    """

    name: str | None = Field(default=None, examples=["UpdatedObjectName"])
    description: str | None = Field(default=None, examples=["Updated description"])
    fields: list[ObjectFieldReferenceSchema] | None = Field(default=None)
    validators: list[ModelValidatorInput] | None = Field(default=None)


class ObjectResponse(BaseModel):
    """Response schema for object data.

    :ivar id: Unique identifier for the object.
    :ivar namespace_id: Namespace this object belongs to.
    :ivar name: Object name.
    :ivar description: Object description.
    :ivar fields: List of field references.
    :ivar used_in_apis: Array of endpoint IDs that use this object.
    :ivar validators: Model validators attached to this object.
    """

    id: UUID = Field(..., examples=["00000000-0000-0000-0007-000000000001"])
    namespace_id: UUID = Field(
        ..., alias="namespaceId", examples=["00000000-0000-0000-0000-000000000001"]
    )
    name: str = Field(..., examples=["User"])
    description: str | None = Field(default=None, examples=["User account object"])
    fields: list[ObjectFieldReferenceSchema] = Field(default_factory=list)
    used_in_apis: list[UUID] = Field(
        default_factory=list,
        alias="usedInApis",
        examples=[["00000000-0000-0000-0004-000000000001"]],
    )
    validators: list[ModelValidatorResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
```

**Step 3: Delete standalone schema files**

```bash
rm src/api/schemas/field_validator.py
rm src/api/schemas/model_validator.py
```

**Step 4: Commit**

```bash
git add -A src/api/schemas/
git commit -m "refactor(schemas): inline validator schemas on field/object

Replace standalone validator CRUD schemas with inline input/response
schemas embedded in field and object schemas.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 4: Rewrite Field Service

**Files:**
- Modify: `src/api/services/field.py`

**Step 1: Rewrite `src/api/services/field.py`**

Key changes:
- Remove import of `FieldValidatorAssociation` and `FieldValidatorReferenceInput`
- Import `FieldValidatorModel` instead
- Replace `selectinload(FieldModel.validator_associations).selectinload(FieldValidatorAssociation.validator)` with `selectinload(FieldModel.validators)` in both `list_for_user` and `get_by_id_for_user`
- Rewrite `_set_validator_associations` to create `FieldValidatorModel` child rows instead of junction records

Replace the entire file with:

```python
# src/api/services/field.py
"""Service layer for Field operations."""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.models.database import (
    ApiEndpoint,
    FieldConstraintValueAssociation,
    FieldModel,
    FieldValidatorModel,
    Namespace,
    ObjectFieldAssociation,
)
from api.schemas.field import FieldConstraintValueInput, FieldCreate, FieldUpdate, FieldValidatorInput
from api.services.base import BaseService


class FieldService(BaseService[FieldModel]):
    """Service for Field CRUD operations.

    :ivar model_class: The FieldModel model class.
    """

    model_class = FieldModel

    def _field_load_options(self):
        """Standard eager-load options for field queries."""
        return [
            selectinload(FieldModel.field_type),
            selectinload(FieldModel.constraint_values).selectinload(
                FieldConstraintValueAssociation.constraint
            ),
            selectinload(FieldModel.validators),
        ]

    async def list_for_user(
        self,
        user_id: UUID,
        namespace_id: str | None = None,
    ) -> list[FieldModel]:
        """List fields owned by a user.

        :param user_id: The authenticated user's ID.
        :param namespace_id: Optional namespace filter.
        :returns: List of user's fields with validators loaded.
        """
        query = (
            select(FieldModel)
            .join(Namespace)
            .options(*self._field_load_options())
            .where(Namespace.user_id == user_id)
        )
        if namespace_id:
            query = query.where(FieldModel.namespace_id == namespace_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_id_for_user(
        self, field_id: str, user_id: UUID
    ) -> FieldModel | None:
        """Get a field if owned by the user.

        :param field_id: The field's unique identifier.
        :param user_id: The authenticated user's ID.
        :returns: The field if owned by user, None otherwise.
        """
        query = (
            select(FieldModel)
            .join(Namespace)
            .options(*self._field_load_options())
            .where(
                FieldModel.id == field_id,
                Namespace.user_id == user_id,
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_for_user(self, user_id: UUID, data: FieldCreate) -> FieldModel:
        """Create a new field for a user.

        :param user_id: The authenticated user's ID.
        :param data: Field creation data.
        :returns: The created field.
        :raises HTTPException: If namespace not owned by user or is locked.
        """
        await self.validate_namespace_for_creation(data.namespace_id, user_id)

        field = FieldModel(
            namespace_id=data.namespace_id,
            user_id=user_id,
            name=data.name,
            type_id=data.type_id,
            description=data.description,
            default_value=data.default_value,
        )
        self.db.add(field)
        await self.db.flush()

        if data.constraints:
            await self._set_constraint_associations(field, data.constraints)

        if data.validators:
            await self._set_validators(field, data.validators)

        await self.db.refresh(field)
        return field

    async def update_field(self, field: FieldModel, data: FieldUpdate) -> FieldModel:
        """Update a field.

        :param field: The field to update.
        :param data: Update data.
        :returns: The updated field.
        """
        if data.name is not None:
            field.name = data.name
        if data.description is not None:
            field.description = data.description
        if data.default_value is not None:
            field.default_value = data.default_value

        if data.constraints is not None:
            await self._set_constraint_associations(field, data.constraints)

        if data.validators is not None:
            await self._set_validators(field, data.validators)

        await self.db.flush()
        await self.db.refresh(field)
        return field

    async def _set_constraint_associations(
        self, field: FieldModel, constraints: list[FieldConstraintValueInput]
    ) -> None:
        """Replace constraint associations for a field.

        :param field: The field model.
        :param constraints: New constraint inputs (empty list clears all).
        """
        await self.db.execute(
            delete(FieldConstraintValueAssociation).where(
                FieldConstraintValueAssociation.field_id == field.id
            )
        )
        for c in constraints:
            assoc = FieldConstraintValueAssociation(
                constraint_id=c.constraint_id,
                field_id=field.id,
                value=c.value,
            )
            self.db.add(assoc)
        await self.db.flush()

    async def _set_validators(
        self, field: FieldModel, validators: list[FieldValidatorInput]
    ) -> None:
        """Replace validators for a field.

        :param field: The field model.
        :param validators: New validator inputs (empty list clears all).
        """
        await self.db.execute(
            delete(FieldValidatorModel).where(
                FieldValidatorModel.field_id == field.id
            )
        )
        for position, v in enumerate(validators):
            validator = FieldValidatorModel(
                field_id=field.id,
                function_name=v.function_name,
                mode=v.mode,
                function_body=v.function_body,
                description=v.description,
                position=position,
            )
            self.db.add(validator)
        await self.db.flush()

    async def delete_field(self, field: FieldModel) -> None:
        """Delete a field if not in use.

        :param field: The field to delete.
        :raises HTTPException: If field is used in objects.
        """
        count_query = (
            select(func.count())
            .select_from(ObjectFieldAssociation)
            .where(ObjectFieldAssociation.field_id == field.id)
        )
        result = await self.db.execute(count_query)
        usage_count = result.scalar() or 0

        if usage_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete field: used in {usage_count} objects",
            )

        await self.db.delete(field)
        await self.db.flush()

    async def get_used_in_apis(self, field_id: UUID) -> list[UUID]:
        """Get endpoint IDs where this field is used.

        :param field_id: The field's ID.
        :returns: List of endpoint IDs.
        """
        objects_subquery = (
            select(ObjectFieldAssociation.object_id)
            .where(ObjectFieldAssociation.field_id == field_id)
            .subquery()
        )
        query = (
            select(ApiEndpoint.id)
            .where(
                or_(
                    ApiEndpoint.query_params_object_id.in_(select(objects_subquery)),
                    ApiEndpoint.request_body_object_id.in_(select(objects_subquery)),
                    ApiEndpoint.response_body_object_id.in_(select(objects_subquery)),
                )
            )
            .distinct()
        )
        result = await self.db.execute(query)
        return [row[0] for row in result.fetchall()]


def get_field_service(db: AsyncSession) -> FieldService:
    """Factory function for FieldService.

    :param db: Database session.
    :returns: FieldService instance.
    """
    return FieldService(db)
```

**Step 2: Commit**

```bash
git add src/api/services/field.py
git commit -m "refactor(services): inline field validators in FieldService

Replace M2M validator association logic with direct child row creation.
Simplify eager-loading to use FieldModel.validators directly.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 5: Update Object Service

**Files:**
- Modify: `src/api/services/object.py`

**Step 1: Rewrite `src/api/services/object.py`**

Key changes:
- Import `ModelValidatorModel` and `ModelValidatorInput`
- Add `selectinload(ObjectDefinition.validators)` to both queries
- Add `_set_validators()` method (same pattern as field service)
- Call `_set_validators()` in `create_for_user()` and `update_object()`

Replace the entire file with:

```python
# src/api/services/object.py
"""Service layer for Object operations."""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.models.database import (
    ApiEndpoint,
    ModelValidatorModel,
    Namespace,
    ObjectDefinition,
    ObjectFieldAssociation,
)
from api.schemas.object import ModelValidatorInput, ObjectCreate, ObjectFieldReferenceSchema, ObjectUpdate
from api.services.base import BaseService


class ObjectService(BaseService[ObjectDefinition]):
    """Service for Object CRUD operations.

    :ivar model_class: The ObjectDefinition model class.
    """

    model_class = ObjectDefinition

    def _object_load_options(self):
        """Standard eager-load options for object queries."""
        return [
            selectinload(ObjectDefinition.field_associations),
            selectinload(ObjectDefinition.validators),
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
        :raises HTTPException: If namespace not owned by user or is locked.
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
                    ApiEndpoint.request_body_object_id == obj.id,
                    ApiEndpoint.response_body_object_id == obj.id,
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

    async def _set_field_associations(
        self,
        obj: ObjectDefinition,
        fields: list[ObjectFieldReferenceSchema],
    ) -> None:
        """Set field associations for an object, replacing existing ones.

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
            assoc = ObjectFieldAssociation(
                object_id=obj.id,
                field_id=field_ref.field_id,
                required=field_ref.required,
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
            delete(ModelValidatorModel).where(
                ModelValidatorModel.object_id == obj.id
            )
        )
        for position, v in enumerate(validators):
            validator = ModelValidatorModel(
                object_id=obj.id,
                function_name=v.function_name,
                mode=v.mode,
                function_body=v.function_body,
                description=v.description,
                position=position,
            )
            self.db.add(validator)
        await self.db.flush()

    async def get_used_in_apis(self, object_id: UUID) -> list[UUID]:
        """Get endpoint IDs where this object is used.

        :param object_id: The object's ID.
        :returns: List of endpoint IDs.
        """
        query = select(ApiEndpoint.id).where(
            or_(
                ApiEndpoint.query_params_object_id == object_id,
                ApiEndpoint.request_body_object_id == object_id,
                ApiEndpoint.response_body_object_id == object_id,
            )
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())


def get_object_service(db: AsyncSession) -> ObjectService:
    """Factory function for ObjectService.

    :param db: Database session.
    :returns: ObjectService instance.
    """
    return ObjectService(db)
```

**Step 2: Commit**

```bash
git add src/api/services/object.py
git commit -m "feat(services): add inline model validators to ObjectService

Add _set_validators() method and validators eager-loading to object
queries. Model validators are now created/updated inline with objects.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 6: Delete Standalone Services

**Files:**
- Delete: `src/api/services/field_validator.py`
- Delete: `src/api/services/model_validator.py`

**Step 1: Delete the files**

```bash
rm src/api/services/field_validator.py
rm src/api/services/model_validator.py
```

**Step 2: Commit**

```bash
git add -A src/api/services/
git commit -m "refactor(services): remove standalone validator services

Validator logic is now handled inline by FieldService and ObjectService.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 7: Update Routers

**Files:**
- Modify: `src/api/routers/fields.py`
- Modify: `src/api/routers/objects.py`
- Delete: `src/api/routers/field_validators.py`
- Delete: `src/api/routers/model_validators.py`
- Modify: `src/api/routers/__init__.py`
- Modify: `src/api/main.py`

**Step 1: Update `src/api/routers/fields.py`**

Replace the imports and `_to_response` helper. The route handlers themselves do not change — only the response builder and imports:

Replace lines 1-14 (imports) with:

```python
# src/api/routers/fields.py
"""Router for Field endpoints."""

from fastapi import APIRouter, HTTPException, status

from api.deps import DbSession, ProvisionedUser
from api.schemas.field import (
    FieldConstraintValueResponse,
    FieldCreate,
    FieldResponse,
    FieldUpdate,
    FieldValidatorResponse,
)
from api.services.field import FieldService, get_field_service
```

Replace the `_to_response` function (currently lines 28-62) with:

```python
async def _to_response(field, service: FieldService) -> FieldResponse:
    """Convert a field model to response schema.

    :param field: Field database model.
    :param service: FieldService instance for fetching usage data.
    :returns: FieldResponse schema.
    """
    used_in_apis = await service.get_used_in_apis(field.id)
    constraints = [
        FieldConstraintValueResponse(
            constraint_id=cv.constraint_id,
            name=cv.constraint.name,
            value=cv.value,
        )
        for cv in field.constraint_values
    ]
    validators = [
        FieldValidatorResponse(
            id=v.id,
            function_name=v.function_name,
            mode=v.mode,
            function_body=v.function_body,
            description=v.description,
        )
        for v in sorted(field.validators, key=lambda x: x.position)
    ]
    return FieldResponse(
        id=field.id,
        namespace_id=field.namespace_id,
        name=field.name,
        type_id=field.type_id,
        description=field.description,
        default_value=field.default_value,
        used_in_apis=used_in_apis,
        constraints=constraints,
        validators=validators,
    )
```

All route handler functions remain unchanged.

**Step 2: Update `src/api/routers/objects.py`**

Replace imports (lines 1-13) with:

```python
# src/api/routers/objects.py
"""Router for Object endpoints."""

from fastapi import APIRouter, HTTPException, status

from api.deps import DbSession, ProvisionedUser
from api.schemas.object import (
    ModelValidatorResponse,
    ObjectCreate,
    ObjectFieldReferenceSchema,
    ObjectResponse,
    ObjectUpdate,
)
from api.services.object import ObjectService, get_object_service
```

Replace `_to_response` (currently lines 27-46) with:

```python
async def _to_response(obj, service: ObjectService) -> ObjectResponse:
    """Convert an object model to response schema.

    :param obj: Object database model.
    :param service: ObjectService for fetching usage.
    :returns: ObjectResponse schema.
    """
    fields = [
        ObjectFieldReferenceSchema(field_id=fa.field_id, required=fa.required)
        for fa in sorted(obj.field_associations, key=lambda x: x.position)
    ]
    validators = [
        ModelValidatorResponse(
            id=v.id,
            function_name=v.function_name,
            mode=v.mode,
            function_body=v.function_body,
            description=v.description,
        )
        for v in sorted(obj.validators, key=lambda x: x.position)
    ]
    used_in_apis = await service.get_used_in_apis(obj.id)
    return ObjectResponse(
        id=obj.id,
        namespace_id=obj.namespace_id,
        name=obj.name,
        description=obj.description,
        fields=fields,
        used_in_apis=used_in_apis,
        validators=validators,
    )
```

All route handler functions remain unchanged.

**Step 3: Delete standalone router files**

```bash
rm src/api/routers/field_validators.py
rm src/api/routers/model_validators.py
```

**Step 4: Update `src/api/routers/__init__.py`**

Replace the entire file with:

```python
# src/api/routers/__init__.py
"""FastAPI routers for API endpoints."""

from api.routers.apis import router as apis_router
from api.routers.endpoints import router as endpoints_router
from api.routers.field_constraints import router as field_constraints_router
from api.routers.fields import router as fields_router
from api.routers.namespaces import router as namespaces_router
from api.routers.objects import router as objects_router
from api.routers.types import router as types_router

__all__ = [
    "apis_router",
    "endpoints_router",
    "field_constraints_router",
    "fields_router",
    "namespaces_router",
    "objects_router",
    "types_router",
]
```

**Step 5: Update `src/api/main.py`**

Remove validator router imports and registrations.

In the imports block (lines 15-25), remove `field_validators_router` and `model_validators_router`.

In the router registration block (lines 109-117), remove these two lines:

```python
# DELETE these lines:
app.include_router(field_validators_router, prefix=api_v1_prefix)
app.include_router(model_validators_router, prefix=api_v1_prefix)
```

**Step 6: Commit**

```bash
git add -A src/api/routers/ src/api/main.py
git commit -m "refactor(routers): remove standalone validator endpoints

Delete field_validators and model_validators routers. Update fields
and objects routers to serialize inline validators in responses.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 8: Verify Build

**Step 1: Run the application import check**

```bash
cd /Users/evgesha/Documents/Projects/median-code-backend
poetry run python -c "from api.main import app; print('OK')"
```

Expected: `OK` with no import errors.

**Step 2: Run alembic migration against local DB**

```bash
poetry run alembic upgrade head
```

Expected: Migration applies cleanly.

**Step 3: Commit any fixes needed, then tag the milestone**

```bash
git add -A
git commit -m "fix: resolve import/migration issues from inline validators refactor

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 9: Update Tests — Field Validator Integration

**Files:**
- Modify or rewrite: `tests/test_api/test_services/test_field_validator.py` (or equivalent field test file)
- Modify: `tests/test_api/test_services/test_field.py`

**Context:** The existing `test_field_validator.py` tests standalone field validator CRUD. These tests must be rewritten to test inline validators through the field endpoints instead.

**Note:** Check existing test patterns in `test_field.py` to match the project's test conventions (fixtures, conftest setup, DB session handling). Follow those patterns exactly.

**Step 1: Delete standalone field validator tests**

Delete `tests/test_api/test_services/test_field_validator.py` (or rename/rewrite).

**Step 2: Add inline field validator tests to `test_field.py`**

Add test cases covering:

```python
# Test: Create field with inline validators
async def test_create_field_with_validators(self):
    """POST /v1/fields with validators list creates field + child validators."""
    # Create field with validators in payload
    # Assert response contains validators with IDs
    # Assert validator function_name, mode, function_body match input

# Test: Create field without validators
async def test_create_field_without_validators(self):
    """POST /v1/fields with empty validators list returns empty validators."""
    # Create field with validators=[]
    # Assert response.validators == []

# Test: Update field — replace validators
async def test_update_field_replace_validators(self):
    """PUT /v1/fields/{id} with new validators replaces existing ones."""
    # Create field with validator A
    # Update with validator B
    # Assert response contains only validator B
    # Assert validator A no longer exists in DB

# Test: Update field — clear validators
async def test_update_field_clear_validators(self):
    """PUT /v1/fields/{id} with validators=[] removes all validators."""
    # Create field with validators
    # Update with validators=[]
    # Assert response.validators == []

# Test: Update field — omit validators (unchanged)
async def test_update_field_omit_validators(self):
    """PUT /v1/fields/{id} without validators key leaves validators unchanged."""
    # Create field with validators
    # Update with only name change (no validators key)
    # Assert validators still present

# Test: Delete field cascades validators
async def test_delete_field_cascades_validators(self):
    """DELETE /v1/fields/{id} also deletes its child validators."""
    # Create field with validators
    # Delete field
    # Assert field_validators rows are gone (query DB directly)
```

**Step 3: Run field tests**

```bash
poetry run pytest tests/test_api/test_services/test_field.py -v
```

**Step 4: Commit**

```bash
git add -A tests/
git commit -m "test(fields): add inline field validator integration tests

Replace standalone validator CRUD tests with inline validator tests
through the field creation/update/delete endpoints.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 10: Update Tests — Model Validator Integration

**Files:**
- Delete: any standalone model validator test files
- Modify or create: `tests/test_api/test_services/test_object.py`

**Context:** There are no existing model validator tests. Create inline model validator tests as part of the object test suite.

**Step 1: Add model validator tests to the object test file**

Add test cases covering (same patterns as field validator tests):

```python
# Test: Create object with inline model validators
async def test_create_object_with_validators(self):
    """POST /v1/objects with validators list creates object + child validators."""

# Test: Create object without validators
async def test_create_object_without_validators(self):
    """POST /v1/objects with no validators returns empty validators list."""

# Test: Update object — replace validators
async def test_update_object_replace_validators(self):
    """PUT /v1/objects/{id} with new validators replaces existing ones."""

# Test: Update object — clear validators
async def test_update_object_clear_validators(self):
    """PUT /v1/objects/{id} with validators=[] removes all validators."""

# Test: Update object — omit validators (unchanged)
async def test_update_object_omit_validators(self):
    """PUT /v1/objects/{id} without validators key leaves validators unchanged."""

# Test: Delete object cascades validators
async def test_delete_object_cascades_validators(self):
    """DELETE /v1/objects/{id} also deletes its child model validators."""
```

**Step 2: Run object tests**

```bash
poetry run pytest tests/test_api/test_services/test_object.py -v
```

**Step 3: Commit**

```bash
git add -A tests/
git commit -m "test(objects): add inline model validator integration tests

Test model validator creation, replacement, clearing, and cascade
deletion through the object CRUD endpoints.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 11: Verify Old Endpoints Return 404

**Step 1: Add regression tests**

```python
# Test: Standalone field validator endpoints no longer exist
async def test_field_validators_endpoint_removed(self):
    """GET /v1/field-validators should return 404 (endpoint removed)."""
    response = await client.get("/v1/field-validators", headers=auth_headers)
    assert response.status_code == 404

async def test_model_validators_endpoint_removed(self):
    """GET /v1/model-validators should return 404 (endpoint removed)."""
    response = await client.get("/v1/model-validators", headers=auth_headers)
    assert response.status_code == 404
```

**Step 2: Run tests**

```bash
poetry run pytest tests/ -v -k "endpoint_removed"
```

**Step 3: Commit**

```bash
git add -A tests/
git commit -m "test: verify standalone validator endpoints return 404

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 12: Full Test Suite & Cleanup

**Step 1: Run the complete test suite**

```bash
poetry run pytest tests/ -v
```

Expected: All tests pass. Fix any remaining import errors or broken references.

**Step 2: Search for orphaned references**

Search the entire codebase for any remaining references to deleted code:

```bash
grep -r "FieldValidatorAssociation" src/
grep -r "ObjectModelValidatorAssociation" src/
grep -r "field_validator_field_associations" src/
grep -r "model_validator_object_associations" src/
grep -r "compatible_types" src/api/  # should only remain in FieldConstraintModel
grep -r "required_fields" src/api/   # should be gone entirely
grep -r "from api.schemas.field_validator" src/
grep -r "from api.schemas.model_validator" src/
grep -r "from api.services.field_validator" src/
grep -r "from api.services.model_validator" src/
grep -r "field_validators_router" src/
grep -r "model_validators_router" src/
```

Expected: No matches except `compatible_types` in `FieldConstraintModel` (which is correct — field constraints still use it).

**Step 3: Run formatter**

```bash
poetry run black src/ tests/
```

**Step 4: Final commit**

```bash
git add -A
git commit -m "chore: cleanup orphaned references and format

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Summary of Files Changed

### Deleted (8 files)
| File | Reason |
|---|---|
| `src/api/schemas/field_validator.py` | Standalone schemas replaced by inline schemas in `field.py` |
| `src/api/schemas/model_validator.py` | Standalone schemas replaced by inline schemas in `object.py` |
| `src/api/services/field_validator.py` | Logic absorbed by `FieldService` |
| `src/api/services/model_validator.py` | Logic absorbed by `ObjectService` |
| `src/api/routers/field_validators.py` | Endpoints removed |
| `src/api/routers/model_validators.py` | Endpoints removed |
| `tests/.../test_field_validator.py` | Standalone tests replaced by inline tests |
| Any model validator test files | Replaced by inline tests |

### Modified (7 files)
| File | Change |
|---|---|
| `src/api/models/database.py` | Rewrite validator models, delete junction models, update relationships |
| `src/api/schemas/field.py` | Replace reference schemas with inline `FieldValidatorInput`/`Response` |
| `src/api/schemas/object.py` | Add `ModelValidatorInput`/`Response`, add `validators` to create/update/response |
| `src/api/services/field.py` | Rewrite `_set_validators()` for child rows, simplify eager-loading |
| `src/api/services/object.py` | Add `_set_validators()`, add validator eager-loading |
| `src/api/routers/fields.py` | Update imports and `_to_response()` for direct child access |
| `src/api/routers/objects.py` | Update imports and `_to_response()` to include validators |
| `src/api/routers/__init__.py` | Remove validator router exports |
| `src/api/main.py` | Remove validator router registrations |

### Created (1 file)
| File | Purpose |
|---|---|
| `src/api/migrations/versions/XXXX_inline_validators.py` | Schema migration |
