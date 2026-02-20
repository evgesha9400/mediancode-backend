# tests/test_api/test_services/test_field_validator.py
"""Integration tests for field validators and field-validator associations."""

import pytest

pytestmark = pytest.mark.integration

from uuid import UUID, uuid4

import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.database import (
    FieldConstraintModel,
    FieldModel,
    FieldValidatorAssociation,
    FieldValidatorModel,
    Namespace,
    TypeModel,
    UserModel,
)
from api.schemas.field import FieldCreate, FieldUpdate
from api.schemas.field_validator import (
    FieldValidatorCreate,
    FieldValidatorUpdate,
)
from api.services.field import FieldService
from api.services.field_validator import FieldValidatorService
from api.settings import get_settings

OTHER_USER_ID = uuid4()


# --- Fixtures ---


@pytest_asyncio.fixture
async def user_namespace(
    db_session: AsyncSession, provisioned_namespace: Namespace, test_user: UserModel
):
    """Create a user-owned (unlocked) namespace for validator tests."""
    namespace = Namespace(
        name="Validator Test Namespace",
        description="Namespace for field validator tests",
        user_id=test_user.id,
    )
    db_session.add(namespace)
    await db_session.commit()
    await db_session.refresh(namespace)

    yield namespace

    await db_session.execute(
        delete(FieldModel).where(FieldModel.namespace_id == namespace.id)
    )
    await db_session.execute(
        delete(FieldValidatorModel).where(
            FieldValidatorModel.namespace_id == namespace.id
        )
    )
    await db_session.execute(delete(Namespace).where(Namespace.id == namespace.id))
    await db_session.commit()


@pytest_asyncio.fixture
async def str_type(db_session: AsyncSession, provisioned_namespace: Namespace):
    """Get the seed 'str' type from the system namespace."""
    settings = get_settings()
    result = await db_session.execute(
        select(TypeModel).where(
            TypeModel.namespace_id == settings.system_namespace_id,
            TypeModel.name == "str",
        )
    )
    return result.scalar_one()


@pytest_asyncio.fixture
def validator_service(db_session: AsyncSession):
    """Create a FieldValidatorService instance."""
    return FieldValidatorService(db_session)


@pytest_asyncio.fixture
def field_service(db_session: AsyncSession):
    """Create a FieldService instance."""
    return FieldService(db_session)


async def _create_validator(
    service: FieldValidatorService,
    namespace: Namespace,
    user_id: UUID,
    function_name: str = "trim_whitespace",
    name: str | None = "Trim Whitespace",
    mode: str = "before",
    function_body: str = "def trim_whitespace(cls, v):\n    return v.strip()",
    compatible_types: list[str] | None = None,
) -> FieldValidatorModel:
    """Create a validator via the service layer."""
    data = FieldValidatorCreate.model_validate(
        {
            "namespaceId": namespace.id,
            "name": name,
            "functionName": function_name,
            "mode": mode,
            "functionBody": function_body,
            "compatibleTypes": compatible_types or ["str"],
        }
    )
    return await service.create_for_user(user_id, data)


async def _create_field(
    service: FieldService,
    namespace: Namespace,
    type_model: TypeModel,
    user_id: UUID,
    name: str = "test_field",
    validators: list | None = None,
) -> FieldModel:
    """Create a field via the service layer."""
    data = FieldCreate.model_validate(
        {
            "namespaceId": namespace.id,
            "name": name,
            "typeId": type_model.id,
            "validators": validators or [],
        }
    )
    return await service.create_for_user(user_id, data)


async def _reload_field(
    service: FieldService, field: FieldModel, user_id: UUID
) -> FieldModel:
    """Reload a field with all relationships via the service."""
    loaded = await service.get_by_id_for_user(str(field.id), user_id)
    assert loaded is not None, f"Field {field.id} not found after reload"
    return loaded


# --- Tests: CRUD lifecycle ---


@pytest.mark.asyncio
async def test_create_validator(
    user_namespace: Namespace,
    validator_service: FieldValidatorService,
    test_user: UserModel,
):
    """Creating a field validator stores all fields correctly."""
    validator = await _create_validator(
        validator_service,
        user_namespace,
        test_user.id,
        function_name="to_lowercase",
        name="To Lowercase",
        mode="after",
        function_body="def to_lowercase(cls, v):\n    return v.lower()",
        compatible_types=["str", "EmailStr"],
    )

    assert validator.function_name == "to_lowercase"
    assert validator.name == "To Lowercase"
    assert validator.mode == "after"
    assert validator.function_body == "def to_lowercase(cls, v):\n    return v.lower()"
    assert validator.compatible_types == ["str", "EmailStr"]
    assert validator.namespace_id == user_namespace.id
    assert validator.user_id == test_user.id


@pytest.mark.asyncio
async def test_get_validator_by_id_for_user(
    user_namespace: Namespace,
    validator_service: FieldValidatorService,
    test_user: UserModel,
):
    """get_by_id_for_user returns a validator owned by the requesting user."""
    validator = await _create_validator(validator_service, user_namespace, test_user.id)

    result = await validator_service.get_by_id_for_user(str(validator.id), test_user.id)
    assert result is not None
    assert result.id == validator.id


@pytest.mark.asyncio
async def test_get_validator_by_id_excludes_other_users(
    user_namespace: Namespace,
    validator_service: FieldValidatorService,
    test_user: UserModel,
):
    """get_by_id_for_user returns None when a different user requests the validator."""
    validator = await _create_validator(validator_service, user_namespace, test_user.id)

    result = await validator_service.get_by_id_for_user(
        str(validator.id), OTHER_USER_ID
    )
    assert result is None


@pytest.mark.asyncio
async def test_list_validators_for_user(
    user_namespace: Namespace,
    validator_service: FieldValidatorService,
    test_user: UserModel,
):
    """list_for_user returns validators from user's namespaces."""
    await _create_validator(
        validator_service, user_namespace, test_user.id, function_name="val_a"
    )
    await _create_validator(
        validator_service, user_namespace, test_user.id, function_name="val_b"
    )

    validators = await validator_service.list_for_user(test_user.id)
    fn_names = {v.function_name for v in validators}
    assert "val_a" in fn_names
    assert "val_b" in fn_names


@pytest.mark.asyncio
async def test_list_validators_with_namespace_filter(
    user_namespace: Namespace,
    validator_service: FieldValidatorService,
    test_user: UserModel,
):
    """list_for_user with namespace_id filter returns only that namespace's validators."""
    await _create_validator(
        validator_service, user_namespace, test_user.id, function_name="ns_val"
    )

    validators = await validator_service.list_for_user(
        test_user.id, namespace_id=str(user_namespace.id)
    )
    fn_names = {v.function_name for v in validators}
    assert "ns_val" in fn_names

    # Filtering by a random namespace should return none of our validators
    validators_other = await validator_service.list_for_user(
        test_user.id, namespace_id=str(uuid4())
    )
    fn_names_other = {v.function_name for v in validators_other}
    assert "ns_val" not in fn_names_other


@pytest.mark.asyncio
async def test_update_validator(
    user_namespace: Namespace,
    validator_service: FieldValidatorService,
    test_user: UserModel,
):
    """Updating a validator changes only the specified fields."""
    validator = await _create_validator(validator_service, user_namespace, test_user.id)

    update = FieldValidatorUpdate.model_validate(
        {
            "name": "Updated Name",
            "functionName": "updated_fn",
            "compatibleTypes": ["int", "float"],
        }
    )
    updated = await validator_service.update_validator(validator, update)

    assert updated.name == "Updated Name"
    assert updated.function_name == "updated_fn"
    assert updated.compatible_types == ["int", "float"]
    # Unchanged fields preserved
    assert updated.mode == "before"
    assert updated.function_body == "def trim_whitespace(cls, v):\n    return v.strip()"


@pytest.mark.asyncio
async def test_delete_validator(
    user_namespace: Namespace,
    validator_service: FieldValidatorService,
    test_user: UserModel,
):
    """Deleting a validator removes it from the database."""
    validator = await _create_validator(validator_service, user_namespace, test_user.id)
    validator_id = validator.id

    await validator_service.delete_validator(validator)

    result = await validator_service.get_by_id_for_user(str(validator_id), test_user.id)
    assert result is None


# --- Tests: Deletion guard ---


@pytest.mark.asyncio
async def test_delete_validator_in_use_raises_400(
    db_session: AsyncSession,
    user_namespace: Namespace,
    str_type: TypeModel,
    validator_service: FieldValidatorService,
    field_service: FieldService,
    test_user: UserModel,
):
    """Deleting a validator that is attached to a field raises HTTP 400."""
    validator = await _create_validator(validator_service, user_namespace, test_user.id)

    # Create a field with this validator attached
    await _create_field(
        field_service,
        user_namespace,
        str_type,
        test_user.id,
        name="guarded_field",
        validators=[{"validatorId": str(validator.id)}],
    )
    await db_session.flush()

    with pytest.raises(HTTPException) as exc_info:
        await validator_service.delete_validator(validator)
    assert exc_info.value.status_code == 400
    assert "used in" in exc_info.value.detail


# --- Tests: Field counts ---


@pytest.mark.asyncio
async def test_get_field_counts_for_user(
    db_session: AsyncSession,
    user_namespace: Namespace,
    str_type: TypeModel,
    validator_service: FieldValidatorService,
    field_service: FieldService,
    test_user: UserModel,
):
    """get_field_counts_for_user returns correct usage counts."""
    validator = await _create_validator(
        validator_service, user_namespace, test_user.id, function_name="count_test"
    )

    # No fields yet
    counts = await validator_service.get_field_counts_for_user(test_user.id)
    assert counts.get(str(validator.id), 0) == 0

    # Attach to one field
    await _create_field(
        field_service,
        user_namespace,
        str_type,
        test_user.id,
        name="counted_field_1",
        validators=[{"validatorId": str(validator.id)}],
    )
    await db_session.flush()

    counts = await validator_service.get_field_counts_for_user(test_user.id)
    assert counts.get(str(validator.id), 0) == 1

    # Attach to another field
    await _create_field(
        field_service,
        user_namespace,
        str_type,
        test_user.id,
        name="counted_field_2",
        validators=[{"validatorId": str(validator.id)}],
    )
    await db_session.flush()

    counts = await validator_service.get_field_counts_for_user(test_user.id)
    assert counts.get(str(validator.id), 0) == 2


# --- Tests: Field integration ---


@pytest.mark.asyncio
async def test_create_field_with_validator(
    user_namespace: Namespace,
    str_type: TypeModel,
    validator_service: FieldValidatorService,
    field_service: FieldService,
    test_user: UserModel,
):
    """Creating a field with a validator reference stores the association."""
    validator = await _create_validator(validator_service, user_namespace, test_user.id)

    field = await _create_field(
        field_service,
        user_namespace,
        str_type,
        test_user.id,
        name="validated_field",
        validators=[{"validatorId": str(validator.id)}],
    )
    loaded = await _reload_field(field_service, field, test_user.id)

    assert len(loaded.validator_associations) == 1
    va = loaded.validator_associations[0]
    assert va.validator_id == validator.id
    assert va.validator.function_name == "trim_whitespace"
    assert va.validator.name == "Trim Whitespace"


@pytest.mark.asyncio
async def test_create_field_without_validators(
    user_namespace: Namespace,
    str_type: TypeModel,
    field_service: FieldService,
    test_user: UserModel,
):
    """A field can be created with no validators."""
    field = await _create_field(
        field_service,
        user_namespace,
        str_type,
        test_user.id,
        name="plain_field",
    )
    loaded = await _reload_field(field_service, field, test_user.id)

    assert len(loaded.validator_associations) == 0


@pytest.mark.asyncio
async def test_update_field_add_validators(
    user_namespace: Namespace,
    str_type: TypeModel,
    validator_service: FieldValidatorService,
    field_service: FieldService,
    test_user: UserModel,
):
    """Validators can be added to a field that previously had none."""
    validator = await _create_validator(validator_service, user_namespace, test_user.id)

    field = await _create_field(
        field_service,
        user_namespace,
        str_type,
        test_user.id,
        name="add_val_field",
    )
    loaded = await _reload_field(field_service, field, test_user.id)
    assert len(loaded.validator_associations) == 0

    update = FieldUpdate.model_validate(
        {"validators": [{"validatorId": str(validator.id)}]}
    )
    await field_service.update_field(loaded, update)
    reloaded = await _reload_field(field_service, loaded, test_user.id)

    assert len(reloaded.validator_associations) == 1
    assert reloaded.validator_associations[0].validator_id == validator.id


@pytest.mark.asyncio
async def test_update_field_replace_validators(
    user_namespace: Namespace,
    str_type: TypeModel,
    validator_service: FieldValidatorService,
    field_service: FieldService,
    test_user: UserModel,
):
    """Updating validators replaces all existing ones."""
    val_a = await _create_validator(
        validator_service,
        user_namespace,
        test_user.id,
        function_name="val_a",
        name="Val A",
    )
    val_b = await _create_validator(
        validator_service,
        user_namespace,
        test_user.id,
        function_name="val_b",
        name="Val B",
    )

    field = await _create_field(
        field_service,
        user_namespace,
        str_type,
        test_user.id,
        name="replace_val_field",
        validators=[{"validatorId": str(val_a.id)}],
    )
    loaded = await _reload_field(field_service, field, test_user.id)
    assert len(loaded.validator_associations) == 1
    assert loaded.validator_associations[0].validator.function_name == "val_a"

    update = FieldUpdate.model_validate(
        {"validators": [{"validatorId": str(val_b.id)}]}
    )
    await field_service.update_field(loaded, update)
    reloaded = await _reload_field(field_service, loaded, test_user.id)

    assert len(reloaded.validator_associations) == 1
    assert reloaded.validator_associations[0].validator.function_name == "val_b"


@pytest.mark.asyncio
async def test_update_field_clear_validators(
    user_namespace: Namespace,
    str_type: TypeModel,
    validator_service: FieldValidatorService,
    field_service: FieldService,
    test_user: UserModel,
):
    """Passing an empty validators list clears all validators."""
    validator = await _create_validator(validator_service, user_namespace, test_user.id)

    field = await _create_field(
        field_service,
        user_namespace,
        str_type,
        test_user.id,
        name="clear_val_field",
        validators=[{"validatorId": str(validator.id)}],
    )
    loaded = await _reload_field(field_service, field, test_user.id)
    assert len(loaded.validator_associations) == 1

    update = FieldUpdate.model_validate({"validators": []})
    await field_service.update_field(loaded, update)
    reloaded = await _reload_field(field_service, loaded, test_user.id)

    assert len(reloaded.validator_associations) == 0


@pytest.mark.asyncio
async def test_update_field_validators_unchanged_when_omitted(
    user_namespace: Namespace,
    str_type: TypeModel,
    validator_service: FieldValidatorService,
    field_service: FieldService,
    test_user: UserModel,
):
    """Omitting validators from update (None) preserves existing ones."""
    validator = await _create_validator(validator_service, user_namespace, test_user.id)

    field = await _create_field(
        field_service,
        user_namespace,
        str_type,
        test_user.id,
        name="preserve_val_field",
        validators=[{"validatorId": str(validator.id)}],
    )
    loaded = await _reload_field(field_service, field, test_user.id)
    assert len(loaded.validator_associations) == 1

    update = FieldUpdate.model_validate({"name": "renamed_field"})
    await field_service.update_field(loaded, update)
    reloaded = await _reload_field(field_service, loaded, test_user.id)

    assert reloaded.name == "renamed_field"
    assert len(reloaded.validator_associations) == 1
    assert reloaded.validator_associations[0].validator_id == validator.id


# --- Tests: Delete cascade ---


@pytest.mark.asyncio
async def test_delete_field_cascades_validator_associations(
    db_session: AsyncSession,
    user_namespace: Namespace,
    str_type: TypeModel,
    validator_service: FieldValidatorService,
    field_service: FieldService,
    test_user: UserModel,
):
    """Deleting a field removes its validator associations."""
    validator = await _create_validator(validator_service, user_namespace, test_user.id)

    field = await _create_field(
        field_service,
        user_namespace,
        str_type,
        test_user.id,
        name="cascade_field",
        validators=[{"validatorId": str(validator.id)}],
    )
    await db_session.flush()
    field_id = field.id

    # Verify association exists
    result = await db_session.execute(
        select(FieldValidatorAssociation).where(
            FieldValidatorAssociation.field_id == field_id
        )
    )
    assert len(result.scalars().all()) == 1

    # Delete the field
    loaded = await _reload_field(field_service, field, test_user.id)
    await field_service.delete_field(loaded)
    await db_session.flush()

    # Verify association was cascade-deleted
    result = await db_session.execute(
        select(FieldValidatorAssociation).where(
            FieldValidatorAssociation.field_id == field_id
        )
    )
    assert len(result.scalars().all()) == 0
