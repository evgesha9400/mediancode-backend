# tests/test_api_craft/test_input_models.py
"""Tests for input model changes: pk, database config."""

import pytest
from api_craft.models.input import (
    InputDatabaseConfig,
    InputField,
    InputModel,
    InputApiConfig,
    InputAPI,
    InputEndpoint,
)


class TestPrimaryKeyField:
    def test_field_pk_defaults_false(self):
        field = InputField(name="name", type="str")
        assert field.pk is False

    def test_field_pk_true(self):
        field = InputField(name="id", type="int", pk=True)
        assert field.pk is True


class TestDatabaseConfig:
    def test_database_config_defaults(self):
        config = InputApiConfig()
        assert config.database.enabled is False
        assert config.database.seed_data is True

    def test_database_enabled(self):
        config = InputApiConfig(database={"enabled": True})
        assert config.database.enabled is True

    def test_database_seed_disabled(self):
        config = InputApiConfig(database={"enabled": True, "seed_data": False})
        assert config.database.seed_data is False


class TestPrimaryKeyValidation:
    def test_optional_pk_rejected(self):
        """PK field must not be optional."""
        with pytest.raises(ValueError, match="cannot be optional"):
            InputAPI(
                name="PkTest",
                endpoints=[
                    InputEndpoint(
                        name="GetItems", path="/items", method="GET", response="Item"
                    )
                ],
                objects=[
                    InputModel(
                        name="Item",
                        fields=[
                            InputField(name="id", type="int", pk=True, optional=True)
                        ],
                    ),
                ],
            )

    def test_multiple_pks_rejected(self):
        """Only one PK field per model is allowed."""
        with pytest.raises(ValueError, match="multiple primary key"):
            InputAPI(
                name="PkTest",
                endpoints=[
                    InputEndpoint(
                        name="GetItems", path="/items", method="GET", response="Item"
                    )
                ],
                objects=[
                    InputModel(
                        name="Item",
                        fields=[
                            InputField(name="id", type="int", pk=True),
                            InputField(name="uuid", type="uuid", pk=True),
                        ],
                    ),
                ],
            )


from api_craft.models.template import (
    TemplateORMField,
    TemplateORMModel,
    TemplateDatabaseConfig,
)


class TestTemplateORMModels:
    def test_orm_field_creation(self):
        field = TemplateORMField(
            name="id",
            python_type="int",
            column_type="Integer",
            primary_key=True,
            autoincrement=True,
        )
        assert field.primary_key is True
        assert field.nullable is False

    def test_orm_model_creation(self):
        model = TemplateORMModel(
            class_name="ItemRecord",
            table_name="items",
            source_model="Item",
            fields=[
                TemplateORMField(
                    name="id",
                    python_type="int",
                    column_type="Integer",
                    primary_key=True,
                ),
                TemplateORMField(name="name", python_type="str", column_type="Text"),
            ],
        )
        assert model.class_name == "ItemRecord"
        assert model.table_name == "items"
        assert len(model.fields) == 2

    def test_database_config(self):
        config = TemplateDatabaseConfig(
            enabled=True,
            default_url="postgresql+asyncpg://postgres:postgres@localhost:5433/test",
        )
        assert config.enabled is True
        assert config.db_port == 5433


class TestPrimaryKeyTypeRestriction:
    """Only int and uuid types are allowed for primary key fields."""

    def test_int_pk_accepted(self):
        api = InputAPI(
            name="PkTest",
            endpoints=[
                InputEndpoint(
                    name="GetItems", path="/items", method="GET", response="Item"
                )
            ],
            objects=[
                InputModel(
                    name="Item",
                    fields=[
                        InputField(name="id", type="int", pk=True),
                        InputField(name="name", type="str"),
                    ],
                ),
            ],
        )
        assert api.objects[0].fields[0].pk is True

    def test_uuid_pk_accepted(self):
        api = InputAPI(
            name="PkTest",
            endpoints=[
                InputEndpoint(
                    name="GetItems", path="/items", method="GET", response="Item"
                )
            ],
            objects=[
                InputModel(
                    name="Item",
                    fields=[
                        InputField(name="id", type="uuid", pk=True),
                        InputField(name="name", type="str"),
                    ],
                ),
            ],
        )
        assert api.objects[0].fields[0].pk is True

    def test_uuid_dotted_pk_accepted(self):
        api = InputAPI(
            name="PkTest",
            endpoints=[
                InputEndpoint(
                    name="GetItems", path="/items", method="GET", response="Item"
                )
            ],
            objects=[
                InputModel(
                    name="Item",
                    fields=[
                        InputField(name="id", type="uuid.UUID", pk=True),
                        InputField(name="name", type="str"),
                    ],
                ),
            ],
        )
        assert api.objects[0].fields[0].pk is True

    @pytest.mark.parametrize(
        "bad_type",
        ["str", "datetime", "bool", "float", "date", "Decimal", "EmailStr"],
    )
    def test_unsupported_pk_type_rejected(self, bad_type):
        with pytest.raises(ValueError, match="unsupported type"):
            InputAPI(
                name="PkTest",
                endpoints=[
                    InputEndpoint(
                        name="GetItems",
                        path="/items",
                        method="GET",
                        response="Item",
                    )
                ],
                objects=[
                    InputModel(
                        name="Item",
                        fields=[InputField(name="id", type=bad_type, pk=True)],
                    ),
                ],
            )

    def test_non_pk_field_any_type_allowed(self):
        """Non-PK fields should not be restricted by PK type rules."""
        api = InputAPI(
            name="PkTest",
            endpoints=[
                InputEndpoint(
                    name="GetItems", path="/items", method="GET", response="Item"
                )
            ],
            objects=[
                InputModel(
                    name="Item",
                    fields=[
                        InputField(name="id", type="int", pk=True),
                        InputField(name="created_at", type="datetime"),
                        InputField(name="email", type="EmailStr"),
                    ],
                ),
            ],
        )
        assert len(api.objects[0].fields) == 3


class TestDatabaseConfigValidation:
    """Validation rules for database generation configuration."""

    def test_database_with_placeholders_raises(self):
        """Database enabled + response_placeholders=True must raise."""
        with pytest.raises(ValueError, match="Response placeholders cannot be enabled"):
            InputAPI(
                name="TestApi",
                objects=[
                    InputModel(
                        name="Item",
                        fields=[InputField(name="id", type="int", pk=True)],
                    ),
                ],
                endpoints=[
                    InputEndpoint(
                        name="GetItems", path="/items", method="GET", response="Item"
                    ),
                ],
                config=InputApiConfig(
                    response_placeholders=True,
                    database=InputDatabaseConfig(enabled=True),
                ),
            )

    def test_database_without_placeholders_passes(self):
        """Database enabled + response_placeholders=False must succeed."""
        api = InputAPI(
            name="TestApi",
            objects=[
                InputModel(
                    name="Item",
                    fields=[InputField(name="id", type="int", pk=True)],
                ),
            ],
            endpoints=[
                InputEndpoint(
                    name="GetItems", path="/items", method="GET", response="Item"
                ),
            ],
            config=InputApiConfig(
                response_placeholders=False,
                database=InputDatabaseConfig(enabled=True),
            ),
        )
        assert api.config.database.enabled is True

    def test_placeholders_without_database_passes(self):
        """Placeholders enabled without database must succeed."""
        api = InputAPI(
            name="TestApi",
            objects=[
                InputModel(
                    name="Item",
                    fields=[InputField(name="name", type="str")],
                ),
            ],
            endpoints=[
                InputEndpoint(
                    name="GetItems", path="/items", method="GET", response="Item"
                ),
            ],
            config=InputApiConfig(
                response_placeholders=True,
                database=InputDatabaseConfig(enabled=False),
            ),
        )
        assert api.config.response_placeholders is True

    def test_database_without_pk_raises(self):
        """Database enabled with no PK on any object must raise."""
        with pytest.raises(ValueError, match="at least one object with a primary key"):
            InputAPI(
                name="TestApi",
                objects=[
                    InputModel(
                        name="Item",
                        fields=[InputField(name="name", type="str")],
                    ),
                ],
                endpoints=[
                    InputEndpoint(
                        name="GetItems", path="/items", method="GET", response="Item"
                    ),
                ],
                config=InputApiConfig(
                    response_placeholders=False,
                    database=InputDatabaseConfig(enabled=True),
                ),
            )

    def test_database_with_pk_passes(self):
        """Database enabled with a PK on at least one object must succeed."""
        api = InputAPI(
            name="TestApi",
            objects=[
                InputModel(
                    name="Item",
                    fields=[
                        InputField(name="id", type="int", pk=True),
                        InputField(name="name", type="str"),
                    ],
                ),
            ],
            endpoints=[
                InputEndpoint(
                    name="GetItems", path="/items", method="GET", response="Item"
                ),
            ],
            config=InputApiConfig(
                response_placeholders=False,
                database=InputDatabaseConfig(enabled=True),
            ),
        )
        assert api.config.database.enabled is True
