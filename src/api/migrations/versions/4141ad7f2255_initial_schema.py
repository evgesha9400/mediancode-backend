# src/api/migrations/versions/4141ad7f2255_initial_schema.py
"""Initial schema

Revision ID: 4141ad7f2255
Revises:
Create Date: 2026-02-05 00:21:53.575168
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '4141ad7f2255'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Fixed UUIDs for seed data
GLOBAL_NAMESPACE_ID = UUID("00000000-0000-0000-0000-000000000001")
TYPE_STR_ID = UUID("00000000-0000-0000-0001-000000000001")
TYPE_INT_ID = UUID("00000000-0000-0000-0001-000000000002")
TYPE_FLOAT_ID = UUID("00000000-0000-0000-0001-000000000003")
TYPE_BOOL_ID = UUID("00000000-0000-0000-0001-000000000004")
TYPE_DATETIME_ID = UUID("00000000-0000-0000-0001-000000000005")
TYPE_UUID_ID = UUID("00000000-0000-0000-0001-000000000006")

# Seed data for types
TYPES_DATA = [
    {
        "id": TYPE_STR_ID,
        "namespace_id": GLOBAL_NAMESPACE_ID,
        "name": "str",
        "category": "primitive",
        "python_type": "str",
        "description": "String type for text data",
        "validator_categories": ["string"],
    },
    {
        "id": TYPE_INT_ID,
        "namespace_id": GLOBAL_NAMESPACE_ID,
        "name": "int",
        "category": "primitive",
        "python_type": "int",
        "description": "Integer type for whole numbers",
        "validator_categories": ["numeric"],
    },
    {
        "id": TYPE_FLOAT_ID,
        "namespace_id": GLOBAL_NAMESPACE_ID,
        "name": "float",
        "category": "primitive",
        "python_type": "float",
        "description": "Floating point type for decimal numbers",
        "validator_categories": ["numeric"],
    },
    {
        "id": TYPE_BOOL_ID,
        "namespace_id": GLOBAL_NAMESPACE_ID,
        "name": "bool",
        "category": "primitive",
        "python_type": "bool",
        "description": "Boolean type for true/false values",
        "validator_categories": [],
    },
    {
        "id": TYPE_DATETIME_ID,
        "namespace_id": GLOBAL_NAMESPACE_ID,
        "name": "datetime",
        "category": "primitive",
        "python_type": "datetime.datetime",
        "description": "Date and time type",
        "validator_categories": [],
    },
    {
        "id": TYPE_UUID_ID,
        "namespace_id": GLOBAL_NAMESPACE_ID,
        "name": "uuid",
        "category": "abstract",
        "python_type": "uuid.UUID",
        "description": "Universally unique identifier",
        "validator_categories": ["string"],
    },
]

# Seed data for validators
VALIDATORS_DATA = [
    # String validators
    {
        "id": UUID("00000000-0000-0000-0002-000000000001"),
        "namespace_id": GLOBAL_NAMESPACE_ID,
        "name": "max_length",
        "type": "string",
        "description": "Validates that string length does not exceed maximum",
        "category": "inline",
        "parameter_type": "int",
        "example_usage": "Field(max_length=255)",
        "pydantic_docs_url": "https://docs.pydantic.dev/latest/concepts/fields/#string-constraints",
    },
    {
        "id": UUID("00000000-0000-0000-0002-000000000002"),
        "namespace_id": GLOBAL_NAMESPACE_ID,
        "name": "min_length",
        "type": "string",
        "description": "Validates that string length is at least minimum",
        "category": "inline",
        "parameter_type": "int",
        "example_usage": "Field(min_length=1)",
        "pydantic_docs_url": "https://docs.pydantic.dev/latest/concepts/fields/#string-constraints",
    },
    {
        "id": UUID("00000000-0000-0000-0002-000000000003"),
        "namespace_id": GLOBAL_NAMESPACE_ID,
        "name": "pattern",
        "type": "string",
        "description": "Validates string matches a regular expression pattern",
        "category": "inline",
        "parameter_type": "str",
        "example_usage": "Field(pattern=r'^[a-z]+$')",
        "pydantic_docs_url": "https://docs.pydantic.dev/latest/concepts/fields/#string-constraints",
    },
    {
        "id": UUID("00000000-0000-0000-0002-000000000004"),
        "namespace_id": GLOBAL_NAMESPACE_ID,
        "name": "email_format",
        "type": "string",
        "description": "Validates email format using EmailStr type",
        "category": "inline",
        "parameter_type": "None",
        "example_usage": "EmailStr",
        "pydantic_docs_url": "https://docs.pydantic.dev/latest/api/networks/#pydantic.networks.EmailStr",
    },
    {
        "id": UUID("00000000-0000-0000-0002-000000000005"),
        "namespace_id": GLOBAL_NAMESPACE_ID,
        "name": "url_format",
        "type": "string",
        "description": "Validates URL format using HttpUrl type",
        "category": "inline",
        "parameter_type": "None",
        "example_usage": "HttpUrl",
        "pydantic_docs_url": "https://docs.pydantic.dev/latest/api/networks/#pydantic.networks.HttpUrl",
    },
    # Numeric validators
    {
        "id": UUID("00000000-0000-0000-0002-000000000006"),
        "namespace_id": GLOBAL_NAMESPACE_ID,
        "name": "gt",
        "type": "numeric",
        "description": "Validates that number is greater than specified value",
        "category": "inline",
        "parameter_type": "number",
        "example_usage": "Field(gt=0)",
        "pydantic_docs_url": "https://docs.pydantic.dev/latest/concepts/fields/#numeric-constraints",
    },
    {
        "id": UUID("00000000-0000-0000-0002-000000000007"),
        "namespace_id": GLOBAL_NAMESPACE_ID,
        "name": "ge",
        "type": "numeric",
        "description": "Validates that number is greater than or equal to specified value",
        "category": "inline",
        "parameter_type": "number",
        "example_usage": "Field(ge=0)",
        "pydantic_docs_url": "https://docs.pydantic.dev/latest/concepts/fields/#numeric-constraints",
    },
    {
        "id": UUID("00000000-0000-0000-0002-000000000008"),
        "namespace_id": GLOBAL_NAMESPACE_ID,
        "name": "lt",
        "type": "numeric",
        "description": "Validates that number is less than specified value",
        "category": "inline",
        "parameter_type": "number",
        "example_usage": "Field(lt=100)",
        "pydantic_docs_url": "https://docs.pydantic.dev/latest/concepts/fields/#numeric-constraints",
    },
    {
        "id": UUID("00000000-0000-0000-0002-000000000009"),
        "namespace_id": GLOBAL_NAMESPACE_ID,
        "name": "le",
        "type": "numeric",
        "description": "Validates that number is less than or equal to specified value",
        "category": "inline",
        "parameter_type": "number",
        "example_usage": "Field(le=100)",
        "pydantic_docs_url": "https://docs.pydantic.dev/latest/concepts/fields/#numeric-constraints",
    },
    {
        "id": UUID("00000000-0000-0000-0002-000000000010"),
        "namespace_id": GLOBAL_NAMESPACE_ID,
        "name": "multiple_of",
        "type": "numeric",
        "description": "Validates that number is a multiple of specified value",
        "category": "inline",
        "parameter_type": "number",
        "example_usage": "Field(multiple_of=5)",
        "pydantic_docs_url": "https://docs.pydantic.dev/latest/concepts/fields/#numeric-constraints",
    },
    # Collection validators
    {
        "id": UUID("00000000-0000-0000-0002-000000000011"),
        "namespace_id": GLOBAL_NAMESPACE_ID,
        "name": "min_items",
        "type": "collection",
        "description": "Validates that collection has at least minimum number of items",
        "category": "inline",
        "parameter_type": "int",
        "example_usage": "Field(min_length=1)",
        "pydantic_docs_url": "https://docs.pydantic.dev/latest/concepts/fields/#string-constraints",
    },
    {
        "id": UUID("00000000-0000-0000-0002-000000000012"),
        "namespace_id": GLOBAL_NAMESPACE_ID,
        "name": "max_items",
        "type": "collection",
        "description": "Validates that collection has at most maximum number of items",
        "category": "inline",
        "parameter_type": "int",
        "example_usage": "Field(max_length=100)",
        "pydantic_docs_url": "https://docs.pydantic.dev/latest/concepts/fields/#string-constraints",
    },
    {
        "id": UUID("00000000-0000-0000-0002-000000000013"),
        "namespace_id": GLOBAL_NAMESPACE_ID,
        "name": "unique_items",
        "type": "collection",
        "description": "Validates that all items in collection are unique",
        "category": "custom",
        "parameter_type": "None",
        "example_usage": "@field_validator(...)",
        "pydantic_docs_url": "https://docs.pydantic.dev/latest/concepts/validators/",
    },
]


def upgrade() -> None:
    # Enable pgcrypto extension for gen_random_uuid()
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # Create namespaces table
    op.create_table('namespaces',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column('user_id', sa.String(length=255), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('locked', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_namespaces_user_id'), 'namespaces', ['user_id'], unique=False)

    # Create types table
    op.create_table('types',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column('namespace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('python_type', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('validator_categories', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(['namespace_id'], ['namespaces.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_types_namespace_id'), 'types', ['namespace_id'], unique=False)

    # Create validators table
    op.create_table('validators',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column('namespace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('parameter_type', sa.String(length=50), nullable=False),
        sa.Column('example_usage', sa.String(length=255), nullable=False),
        sa.Column('pydantic_docs_url', sa.String(length=500), nullable=False),
        sa.ForeignKeyConstraint(['namespace_id'], ['namespaces.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_validators_namespace_id'), 'validators', ['namespace_id'], unique=False)

    # Create apis table (with tags JSONB column)
    op.create_table('apis',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column('namespace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('version', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('base_url', sa.String(length=255), nullable=False),
        sa.Column('server_url', sa.String(length=255), nullable=False),
        sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['namespace_id'], ['namespaces.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_apis_namespace_id'), 'apis', ['namespace_id'], unique=False)
    op.create_index(op.f('ix_apis_user_id'), 'apis', ['user_id'], unique=False)

    # Create fields table
    op.create_table('fields',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column('namespace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('default_value', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['namespace_id'], ['namespaces.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_fields_namespace_id'), 'fields', ['namespace_id'], unique=False)
    op.create_index(op.f('ix_fields_user_id'), 'fields', ['user_id'], unique=False)

    # Create objects table
    op.create_table('objects',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column('namespace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['namespace_id'], ['namespaces.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_objects_namespace_id'), 'objects', ['namespace_id'], unique=False)
    op.create_index(op.f('ix_objects_user_id'), 'objects', ['user_id'], unique=False)

    # Create field_validators table
    op.create_table('field_validators',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column('field_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('params', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['field_id'], ['fields.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_field_validators_field_id'), 'field_validators', ['field_id'], unique=False)

    # Create object_field_associations table
    op.create_table('object_field_associations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column('object_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('field_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('required', sa.Boolean(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['field_id'], ['fields.id']),
        sa.ForeignKeyConstraint(['object_id'], ['objects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_object_field_associations_field_id'), 'object_field_associations', ['field_id'], unique=False)
    op.create_index(op.f('ix_object_field_associations_object_id'), 'object_field_associations', ['object_id'], unique=False)

    # Create api_endpoints table (with tag_name instead of tag_id)
    op.create_table('api_endpoints',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column('namespace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('api_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('method', sa.Enum('GET', 'POST', 'PUT', 'PATCH', 'DELETE', name='http_method'), nullable=False),
        sa.Column('path', sa.String(length=500), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('tag_name', sa.String(length=255), nullable=True),
        sa.Column('query_params_object_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('request_body_object_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('response_body_object_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('use_envelope', sa.Boolean(), nullable=False),
        sa.Column('response_shape', sa.Enum('object', 'list', name='response_shape'), nullable=False),
        sa.ForeignKeyConstraint(['api_id'], ['apis.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['namespace_id'], ['namespaces.id']),
        sa.ForeignKeyConstraint(['query_params_object_id'], ['objects.id']),
        sa.ForeignKeyConstraint(['request_body_object_id'], ['objects.id']),
        sa.ForeignKeyConstraint(['response_body_object_id'], ['objects.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_api_endpoints_api_id'), 'api_endpoints', ['api_id'], unique=False)
    op.create_index(op.f('ix_api_endpoints_namespace_id'), 'api_endpoints', ['namespace_id'], unique=False)
    op.create_index(op.f('ix_api_endpoints_user_id'), 'api_endpoints', ['user_id'], unique=False)

    # Create endpoint_parameters table
    op.create_table('endpoint_parameters',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column('endpoint_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('required', sa.Boolean(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['endpoint_id'], ['api_endpoints.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_endpoint_parameters_endpoint_id'), 'endpoint_parameters', ['endpoint_id'], unique=False)

    # Seed global namespace (required for FK constraints on types/validators)
    op.execute(
        f"""
        INSERT INTO namespaces (id, user_id, name, description, locked)
        VALUES ('{GLOBAL_NAMESPACE_ID}'::uuid, NULL, 'Global', 'Built-in types and validators', true)
        """
    )

    # Seed types data
    types_table = sa.table(
        'types',
        sa.column('id', postgresql.UUID),
        sa.column('namespace_id', postgresql.UUID),
        sa.column('name', sa.String),
        sa.column('category', sa.String),
        sa.column('python_type', sa.String),
        sa.column('description', sa.Text),
        sa.column('validator_categories', postgresql.JSONB),
    )
    op.bulk_insert(types_table, TYPES_DATA)

    # Seed validators data
    validators_table = sa.table(
        'validators',
        sa.column('id', postgresql.UUID),
        sa.column('namespace_id', postgresql.UUID),
        sa.column('name', sa.String),
        sa.column('type', sa.String),
        sa.column('description', sa.Text),
        sa.column('category', sa.String),
        sa.column('parameter_type', sa.String),
        sa.column('example_usage', sa.String),
        sa.column('pydantic_docs_url', sa.String),
    )
    op.bulk_insert(validators_table, VALIDATORS_DATA)


def downgrade() -> None:
    op.drop_index(op.f('ix_endpoint_parameters_endpoint_id'), table_name='endpoint_parameters')
    op.drop_table('endpoint_parameters')
    op.drop_index(op.f('ix_api_endpoints_user_id'), table_name='api_endpoints')
    op.drop_index(op.f('ix_api_endpoints_namespace_id'), table_name='api_endpoints')
    op.drop_index(op.f('ix_api_endpoints_api_id'), table_name='api_endpoints')
    op.drop_table('api_endpoints')
    op.drop_index(op.f('ix_object_field_associations_object_id'), table_name='object_field_associations')
    op.drop_index(op.f('ix_object_field_associations_field_id'), table_name='object_field_associations')
    op.drop_table('object_field_associations')
    op.drop_index(op.f('ix_field_validators_field_id'), table_name='field_validators')
    op.drop_table('field_validators')
    op.drop_index(op.f('ix_objects_user_id'), table_name='objects')
    op.drop_index(op.f('ix_objects_namespace_id'), table_name='objects')
    op.drop_table('objects')
    op.drop_index(op.f('ix_fields_user_id'), table_name='fields')
    op.drop_index(op.f('ix_fields_namespace_id'), table_name='fields')
    op.drop_table('fields')
    op.drop_index(op.f('ix_apis_user_id'), table_name='apis')
    op.drop_index(op.f('ix_apis_namespace_id'), table_name='apis')
    op.drop_table('apis')
    op.drop_index(op.f('ix_validators_namespace_id'), table_name='validators')
    op.drop_table('validators')
    op.drop_index(op.f('ix_types_namespace_id'), table_name='types')
    op.drop_table('types')
    op.drop_index(op.f('ix_namespaces_user_id'), table_name='namespaces')
    op.drop_table('namespaces')

    # Drop enums
    op.execute("DROP TYPE IF EXISTS http_method")
    op.execute("DROP TYPE IF EXISTS response_shape")

    # Drop extension
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
