# Validator Template Catalogues — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace raw `functionBody` validators with backend-seeded template catalogues, template-referenced CRUD, and Jinja2-based code generation at generation time.

**Architecture:** Two new catalogue tables (field_validator_templates, model_validator_templates), two modified junction tables (applied_field_validators, applied_model_validators), two renamed tables (applied_constraints, fields_on_objects). CRUD stores template references only. Jinja2 rendering happens exclusively in the generation service.

**Tech Stack:** SQLAlchemy 2.0 (async), Alembic, FastAPI, Pydantic v2, Jinja2, pytest

**Design doc:** `docs/plans/2026-02-24-validator-template-catalogues-backend-design.md`

---

### Task 1: Modify Initial Schema Migration — New Catalogue Tables + Renamed Junction Tables

**Files:**
- Modify: `src/api/migrations/versions/4141ad7f2255_initial_schema.py`

**Step 1: Add field_validator_templates table to migration**

Add after the `field_constraints` table creation (around line 175) and before `field_validators`:

```python
op.create_table(
    "field_validator_templates",
    sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        nullable=False,
        server_default=sa.text("gen_random_uuid()"),
    ),
    sa.Column("name", sa.Text(), nullable=False),
    sa.Column("description", sa.Text(), nullable=False),
    sa.Column("compatible_types", postgresql.ARRAY(sa.Text()), nullable=False),
    sa.Column("mode", sa.Text(), nullable=False),
    sa.Column("parameters", postgresql.JSONB(), nullable=False, server_default="[]"),
    sa.Column("body_template", sa.Text(), nullable=False),
    sa.PrimaryKeyConstraint("id"),
)
```

**Step 2: Add model_validator_templates table to migration**

Add after `field_validator_templates`:

```python
op.create_table(
    "model_validator_templates",
    sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        nullable=False,
        server_default=sa.text("gen_random_uuid()"),
    ),
    sa.Column("name", sa.Text(), nullable=False),
    sa.Column("description", sa.Text(), nullable=False),
    sa.Column("mode", sa.Text(), nullable=False),
    sa.Column("parameters", postgresql.JSONB(), nullable=False, server_default="[]"),
    sa.Column("field_mappings", postgresql.JSONB(), nullable=False, server_default="[]"),
    sa.Column("body_template", sa.Text(), nullable=False),
    sa.PrimaryKeyConstraint("id"),
)
```

**Step 3: Replace field_validators table with applied_field_validators**

Replace the existing `field_validators` `create_table` block (lines ~223-246) with:

```python
op.create_table(
    "applied_field_validators",
    sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        nullable=False,
        server_default=sa.text("gen_random_uuid()"),
    ),
    sa.Column("field_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("parameters", postgresql.JSONB(), nullable=True),
    sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
    sa.ForeignKeyConstraint(["field_id"], ["fields.id"], ondelete="CASCADE"),
    sa.ForeignKeyConstraint(
        ["template_id"], ["field_validator_templates.id"], ondelete="CASCADE"
    ),
    sa.PrimaryKeyConstraint("id"),
)
op.create_index(
    op.f("ix_applied_field_validators_field_id"),
    "applied_field_validators",
    ["field_id"],
    unique=False,
)
op.create_index(
    op.f("ix_applied_field_validators_template_id"),
    "applied_field_validators",
    ["template_id"],
    unique=False,
)
```

**Step 4: Replace model_validators table with applied_model_validators**

Replace the existing `model_validators` `create_table` block (lines ~278-301) with:

```python
op.create_table(
    "applied_model_validators",
    sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        nullable=False,
        server_default=sa.text("gen_random_uuid()"),
    ),
    sa.Column("object_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("parameters", postgresql.JSONB(), nullable=True),
    sa.Column("field_mappings", postgresql.JSONB(), nullable=False, server_default="{}"),
    sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
    sa.ForeignKeyConstraint(["object_id"], ["objects.id"], ondelete="CASCADE"),
    sa.ForeignKeyConstraint(
        ["template_id"], ["model_validator_templates.id"], ondelete="CASCADE"
    ),
    sa.PrimaryKeyConstraint("id"),
)
op.create_index(
    op.f("ix_applied_model_validators_object_id"),
    "applied_model_validators",
    ["object_id"],
    unique=False,
)
op.create_index(
    op.f("ix_applied_model_validators_template_id"),
    "applied_model_validators",
    ["template_id"],
    unique=False,
)
```

**Step 5: Rename field_constraint_field_associations to applied_constraints**

Replace the existing `field_constraint_field_associations` `create_table` block (lines ~303-332) — change only the table name to `applied_constraints`. Keep all columns and indexes identical, updating index names to match:

```python
op.create_table(
    "applied_constraints",
    # ... same columns as before ...
)
op.create_index(
    op.f("ix_applied_constraints_constraint_id"),
    "applied_constraints",
    ["constraint_id"],
    unique=False,
)
op.create_index(
    op.f("ix_applied_constraints_field_id"),
    "applied_constraints",
    ["field_id"],
    unique=False,
)
```

**Step 6: Rename object_field_associations to fields_on_objects**

Replace the existing `object_field_associations` `create_table` block — change only the table name to `fields_on_objects`. Keep all columns and indexes identical, updating index names:

```python
op.create_table(
    "fields_on_objects",
    # ... same columns as before ...
)
op.create_index(
    op.f("ix_fields_on_objects_field_id"),
    "fields_on_objects",
    ["field_id"],
    unique=False,
)
op.create_index(
    op.f("ix_fields_on_objects_object_id"),
    "fields_on_objects",
    ["object_id"],
    unique=False,
)
```

**Step 7: Update the downgrade() function**

Update all `drop_table` and `drop_index` calls to use the new table names. Drop new catalogue tables in downgrade too.

**Step 8: Commit**

```bash
git add src/api/migrations/versions/4141ad7f2255_initial_schema.py
git commit -m "refactor(migrations)!: add template catalogue tables and rename junction tables"
```

---

### Task 2: Add Seed Data for Validator Templates

**Files:**
- Modify: `src/api/migrations/versions/b1a2c3d4e5f6_seed_system_data.py`

**Step 1: Add field validator template UUIDs and seed data**

Add after the existing `CONSTRAINTS_DATA` list. Use UUID range `0003-*`. Each template needs: `id`, `name`, `description`, `compatible_types`, `mode`, `parameters` (JSONB array), `body_template` (Jinja2 string).

Define all 9 field validator templates:

```python
# Fixed UUIDs for field validator templates
FVT_STRIP_AND_NORMALIZE_ID = UUID("00000000-0000-0000-0003-000000000001")
FVT_NORMALIZE_WHITESPACE_ID = UUID("00000000-0000-0000-0003-000000000002")
FVT_DEFAULT_IF_EMPTY_ID = UUID("00000000-0000-0000-0003-000000000003")
FVT_TRIM_TO_LENGTH_ID = UUID("00000000-0000-0000-0003-000000000004")
FVT_SANITIZE_HTML_ID = UUID("00000000-0000-0000-0003-000000000005")
FVT_ROUND_DECIMAL_ID = UUID("00000000-0000-0000-0003-000000000006")
FVT_SLUG_FORMAT_ID = UUID("00000000-0000-0000-0003-000000000007")
FVT_FUTURE_DATE_ID = UUID("00000000-0000-0000-0003-000000000008")
FVT_PAST_DATE_ID = UUID("00000000-0000-0000-0003-000000000009")

FIELD_VALIDATOR_TEMPLATES_DATA = [
    {
        "id": FVT_STRIP_AND_NORMALIZE_ID,
        "name": "Strip & Normalize Case",
        "description": "Strips whitespace and normalizes text case",
        "compatible_types": ["str"],
        "mode": "before",
        "parameters": [
            {
                "key": "case",
                "label": "Case normalization",
                "type": "select",
                "placeholder": "",
                "options": [
                    {"value": "lower", "label": "lowercase"},
                    {"value": "upper", "label": "UPPERCASE"},
                    {"value": "title", "label": "Title Case"},
                ],
                "required": True,
            }
        ],
        "body_template": "    v = v.strip().{{ case }}()\n    return v",
    },
    {
        "id": FVT_NORMALIZE_WHITESPACE_ID,
        "name": "Normalize Whitespace",
        "description": "Collapses multiple whitespace characters into single spaces and strips edges",
        "compatible_types": ["str"],
        "mode": "before",
        "parameters": [],
        "body_template": "    import re\n    v = re.sub(r'\\s+', ' ', v).strip()\n    return v",
    },
    {
        "id": FVT_DEFAULT_IF_EMPTY_ID,
        "name": "Default If Empty",
        "description": "Replaces empty or whitespace-only strings with a default value",
        "compatible_types": ["str"],
        "mode": "before",
        "parameters": [
            {
                "key": "default_value",
                "label": "Default value",
                "type": "text",
                "placeholder": "N/A",
                "required": True,
            }
        ],
        "body_template": "    if not v or not v.strip():\n        v = \"{{ default_value }}\"\n    return v",
    },
    {
        "id": FVT_TRIM_TO_LENGTH_ID,
        "name": "Trim To Length",
        "description": "Truncates string to maximum length instead of rejecting",
        "compatible_types": ["str"],
        "mode": "before",
        "parameters": [
            {
                "key": "max_length",
                "label": "Maximum length",
                "type": "number",
                "placeholder": "255",
                "required": True,
            }
        ],
        "body_template": "    v = v[:{{ max_length }}]\n    return v",
    },
    {
        "id": FVT_SANITIZE_HTML_ID,
        "name": "Strip HTML Tags",
        "description": "Removes HTML tags from string input for security",
        "compatible_types": ["str"],
        "mode": "before",
        "parameters": [],
        "body_template": "    import re\n    v = re.sub(r'<[^>]+>', '', v)\n    return v",
    },
    {
        "id": FVT_ROUND_DECIMAL_ID,
        "name": "Round Decimal",
        "description": "Rounds numeric value to specified decimal places",
        "compatible_types": ["float", "Decimal"],
        "mode": "before",
        "parameters": [
            {
                "key": "places",
                "label": "Decimal places",
                "type": "number",
                "placeholder": "2",
                "required": True,
            }
        ],
        "body_template": "    v = round(v, {{ places }})\n    return v",
    },
    {
        "id": FVT_SLUG_FORMAT_ID,
        "name": "Slug Format",
        "description": "Validates that string is a valid URL slug (lowercase alphanumeric and hyphens)",
        "compatible_types": ["str"],
        "mode": "after",
        "parameters": [],
        "body_template": "    import re\n    if not re.match(r'^[a-z0-9]+(?:-[a-z0-9]+)*$', v):\n        raise ValueError('Value must be a valid slug (lowercase letters, numbers, and hyphens)')\n    return v",
    },
    {
        "id": FVT_FUTURE_DATE_ID,
        "name": "Future Date Only",
        "description": "Validates that date/datetime is in the future",
        "compatible_types": ["datetime", "date"],
        "mode": "after",
        "parameters": [],
        "body_template": "    from datetime import datetime, date\n    now = datetime.now() if isinstance(v, datetime) else date.today()\n    if v <= now:\n        raise ValueError('Value must be a future date')\n    return v",
    },
    {
        "id": FVT_PAST_DATE_ID,
        "name": "Past Date Only",
        "description": "Validates that date/datetime is in the past",
        "compatible_types": ["datetime", "date"],
        "mode": "after",
        "parameters": [],
        "body_template": "    from datetime import datetime, date\n    now = datetime.now() if isinstance(v, datetime) else date.today()\n    if v >= now:\n        raise ValueError('Value must be a past date')\n    return v",
    },
]
```

**Step 2: Add model validator template UUIDs and seed data**

Define all 6 model validator templates using UUID range `0004-*`:

```python
# Fixed UUIDs for model validator templates
MVT_PASSWORD_CONFIRM_ID = UUID("00000000-0000-0000-0004-000000000001")
MVT_DATE_RANGE_ID = UUID("00000000-0000-0000-0004-000000000002")
MVT_MUTUAL_EXCLUSIVITY_ID = UUID("00000000-0000-0000-0004-000000000003")
MVT_CONDITIONAL_REQUIRED_ID = UUID("00000000-0000-0000-0004-000000000004")
MVT_NUMERIC_COMPARISON_ID = UUID("00000000-0000-0000-0004-000000000005")
MVT_AT_LEAST_ONE_ID = UUID("00000000-0000-0000-0004-000000000006")

MODEL_VALIDATOR_TEMPLATES_DATA = [
    {
        "id": MVT_PASSWORD_CONFIRM_ID,
        "name": "Password Confirmation",
        "description": "Ensures password and confirmation fields match",
        "mode": "after",
        "parameters": [],
        "field_mappings": [
            {"key": "password_field", "label": "Password field", "compatibleTypes": ["str"], "required": True},
            {"key": "confirm_field", "label": "Confirmation field", "compatibleTypes": ["str"], "required": True},
        ],
        "body_template": "    if self.{{ password_field }} != self.{{ confirm_field }}:\n        raise ValueError('Password and confirmation do not match')\n    return self",
    },
    {
        "id": MVT_DATE_RANGE_ID,
        "name": "Date Range",
        "description": "Validates that start date is before end date",
        "mode": "after",
        "parameters": [
            {
                "key": "comparison",
                "label": "Comparison mode",
                "type": "select",
                "placeholder": "",
                "options": [
                    {"value": "<", "label": "Strict (start < end)"},
                    {"value": "<=", "label": "Inclusive (start <= end)"},
                ],
                "required": True,
            }
        ],
        "field_mappings": [
            {"key": "start_field", "label": "Start date field", "compatibleTypes": ["datetime", "date"], "required": True},
            {"key": "end_field", "label": "End date field", "compatibleTypes": ["datetime", "date"], "required": True},
        ],
        "body_template": "    if not (self.{{ start_field }} {{ comparison }} self.{{ end_field }}):\n        raise ValueError('Start date must be before end date')\n    return self",
    },
    {
        "id": MVT_MUTUAL_EXCLUSIVITY_ID,
        "name": "Mutual Exclusivity",
        "description": "Ensures exactly one of two fields is set (not both, not neither)",
        "mode": "after",
        "parameters": [],
        "field_mappings": [
            {"key": "field_a", "label": "Field A", "compatibleTypes": [], "required": True},
            {"key": "field_b", "label": "Field B", "compatibleTypes": [], "required": True},
        ],
        "body_template": "    a_set = self.{{ field_a }} is not None\n    b_set = self.{{ field_b }} is not None\n    if a_set == b_set:\n        raise ValueError('Exactly one of {{ field_a }} or {{ field_b }} must be provided')\n    return self",
    },
    {
        "id": MVT_CONDITIONAL_REQUIRED_ID,
        "name": "Conditional Required",
        "description": "Makes a field required when a trigger field meets a condition",
        "mode": "after",
        "parameters": [
            {
                "key": "condition",
                "label": "Condition",
                "type": "select",
                "placeholder": "",
                "options": [
                    {"value": "equals", "label": "Equals value"},
                    {"value": "not_equals", "label": "Does not equal value"},
                    {"value": "is_truthy", "label": "Is truthy"},
                ],
                "required": True,
            },
            {
                "key": "trigger_value",
                "label": "Trigger value",
                "type": "text",
                "placeholder": "value to compare against",
                "required": False,
            },
        ],
        "field_mappings": [
            {"key": "trigger_field", "label": "Trigger field", "compatibleTypes": [], "required": True},
            {"key": "required_field", "label": "Required field", "compatibleTypes": [], "required": True},
        ],
        "body_template": "    trigger = self.{{ trigger_field }}\n    condition_met = False\n    if '{{ condition }}' == 'equals':\n        condition_met = str(trigger) == '{{ trigger_value }}'\n    elif '{{ condition }}' == 'not_equals':\n        condition_met = str(trigger) != '{{ trigger_value }}'\n    elif '{{ condition }}' == 'is_truthy':\n        condition_met = bool(trigger)\n    if condition_met and self.{{ required_field }} is None:\n        raise ValueError('{{ required_field }} is required when {{ trigger_field }} condition is met')\n    return self",
    },
    {
        "id": MVT_NUMERIC_COMPARISON_ID,
        "name": "Numeric Comparison",
        "description": "Validates that one numeric field is less than another",
        "mode": "after",
        "parameters": [
            {
                "key": "comparison",
                "label": "Comparison mode",
                "type": "select",
                "placeholder": "",
                "options": [
                    {"value": "<", "label": "Strict (lesser < greater)"},
                    {"value": "<=", "label": "Inclusive (lesser <= greater)"},
                ],
                "required": True,
            }
        ],
        "field_mappings": [
            {"key": "lesser_field", "label": "Lesser field", "compatibleTypes": ["int", "float", "Decimal"], "required": True},
            {"key": "greater_field", "label": "Greater field", "compatibleTypes": ["int", "float", "Decimal"], "required": True},
        ],
        "body_template": "    if self.{{ lesser_field }} is not None and self.{{ greater_field }} is not None:\n        if not (self.{{ lesser_field }} {{ comparison }} self.{{ greater_field }}):\n            raise ValueError('{{ lesser_field }} must be less than {{ greater_field }}')\n    return self",
    },
    {
        "id": MVT_AT_LEAST_ONE_ID,
        "name": "At Least One Required",
        "description": "Ensures at least one of two fields is provided",
        "mode": "before",
        "parameters": [],
        "field_mappings": [
            {"key": "field_a", "label": "Field A", "compatibleTypes": [], "required": True},
            {"key": "field_b", "label": "Field B", "compatibleTypes": [], "required": True},
        ],
        "body_template": "    if data.get('{{ field_a }}') is None and data.get('{{ field_b }}') is None:\n        raise ValueError('At least one of {{ field_a }} or {{ field_b }} must be provided')\n    return data",
    },
]
```

**Step 3: Update upgrade() to seed template data**

Add `bulk_insert` calls after the existing constraints insert:

```python
# Seed field validator templates
fvt_table = sa.table(
    "field_validator_templates",
    sa.column("id", postgresql.UUID),
    sa.column("name", sa.Text),
    sa.column("description", sa.Text),
    sa.column("compatible_types", postgresql.ARRAY(sa.Text)),
    sa.column("mode", sa.Text),
    sa.column("parameters", postgresql.JSONB),
    sa.column("body_template", sa.Text),
)
op.bulk_insert(fvt_table, FIELD_VALIDATOR_TEMPLATES_DATA)

# Seed model validator templates
mvt_table = sa.table(
    "model_validator_templates",
    sa.column("id", postgresql.UUID),
    sa.column("name", sa.Text),
    sa.column("description", sa.Text),
    sa.column("mode", sa.Text),
    sa.column("parameters", postgresql.JSONB),
    sa.column("field_mappings", postgresql.JSONB),
    sa.column("body_template", sa.Text),
)
op.bulk_insert(mvt_table, MODEL_VALIDATOR_TEMPLATES_DATA)
```

**Step 4: Update downgrade() to delete template seed data**

Add deletes before the existing constraint deletes (reverse order):

```python
op.execute("DELETE FROM model_validator_templates")
op.execute("DELETE FROM field_validator_templates")
```

**Step 5: Commit**

```bash
git add src/api/migrations/versions/b1a2c3d4e5f6_seed_system_data.py
git commit -m "feat(migrations): seed field and model validator template catalogues"
```

---

### Task 3: Update SQLAlchemy Database Models

**Files:**
- Modify: `src/api/models/database.py`

**Step 1: Add FieldValidatorTemplateModel**

Add after `FieldConstraintModel` (after line ~215):

```python
class FieldValidatorTemplateModel(Base):
    """Field validator template definition (system-seeded catalogue).

    :ivar id: Unique identifier for the template.
    :ivar name: Template display name.
    :ivar description: Template description.
    :ivar compatible_types: List of type names this template applies to.
    :ivar mode: Validator mode (before, after).
    :ivar parameters: Template parameter definitions (JSONB array).
    :ivar body_template: Jinja2 template for the function body.
    """

    __tablename__ = "field_validator_templates"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    compatible_types: Mapped[list] = mapped_column(ARRAY(Text), nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    parameters: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    body_template: Mapped[str] = mapped_column(Text, nullable=False)
```

**Step 2: Add ModelValidatorTemplateModel**

Add after `FieldValidatorTemplateModel`:

```python
class ModelValidatorTemplateModel(Base):
    """Model validator template definition (system-seeded catalogue).

    :ivar id: Unique identifier for the template.
    :ivar name: Template display name.
    :ivar description: Template description.
    :ivar mode: Validator mode (before, after).
    :ivar parameters: Template parameter definitions (JSONB array).
    :ivar field_mappings: Field mapping definitions (JSONB array).
    :ivar body_template: Jinja2 template for the function body.
    """

    __tablename__ = "model_validator_templates"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    parameters: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    field_mappings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    body_template: Mapped[str] = mapped_column(Text, nullable=False)
```

**Step 3: Replace FieldValidatorModel with AppliedFieldValidatorModel**

Replace the existing `FieldValidatorModel` class (lines 310-340):

```python
class AppliedFieldValidatorModel(Base):
    """Applied field validator referencing a template.

    :ivar id: Unique identifier for the applied validator.
    :ivar field_id: Reference to the parent field.
    :ivar template_id: Reference to the field validator template.
    :ivar parameters: User-configured template parameter values.
    :ivar position: Display/execution order position.
    """

    __tablename__ = "applied_field_validators"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    field_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("fields.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    template_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("field_validator_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parameters: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    position: Mapped[int] = mapped_column(default=0, nullable=False)

    # Relationships
    field: Mapped["FieldModel"] = relationship(back_populates="validators")
    template: Mapped["FieldValidatorTemplateModel"] = relationship()
```

**Step 4: Replace ModelValidatorModel with AppliedModelValidatorModel**

Replace the existing `ModelValidatorModel` class (lines 414-444):

```python
class AppliedModelValidatorModel(Base):
    """Applied model validator referencing a template.

    :ivar id: Unique identifier for the applied validator.
    :ivar object_id: Reference to the parent object.
    :ivar template_id: Reference to the model validator template.
    :ivar parameters: User-configured template parameter values.
    :ivar field_mappings: Maps template field mapping keys to actual field names.
    :ivar position: Display/execution order position.
    """

    __tablename__ = "applied_model_validators"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    object_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("objects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    template_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("model_validator_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parameters: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    field_mappings: Mapped[dict] = mapped_column(JSONB, nullable=False)
    position: Mapped[int] = mapped_column(default=0, nullable=False)

    # Relationships
    object: Mapped["ObjectDefinition"] = relationship(back_populates="validators")
    template: Mapped["ModelValidatorTemplateModel"] = relationship()
```

**Step 5: Update FieldConstraintValueAssociation tablename**

Change `__tablename__` from `"field_constraint_field_associations"` to `"applied_constraints"` (line ~456).

**Step 6: Update ObjectFieldAssociation tablename**

Change `__tablename__` from `"object_field_associations"` to `"fields_on_objects"` (line ~390).

**Step 7: Update FieldModel.validators relationship**

Update the `validators` relationship on `FieldModel` (line ~303) to reference `AppliedFieldValidatorModel`:

```python
validators: Mapped[list["AppliedFieldValidatorModel"]] = relationship(
    back_populates="field",
    cascade="all, delete-orphan",
    order_by="AppliedFieldValidatorModel.position",
)
```

**Step 8: Update ObjectDefinition.validators relationship**

Update the `validators` relationship on `ObjectDefinition` (line ~373) to reference `AppliedModelValidatorModel`:

```python
validators: Mapped[list["AppliedModelValidatorModel"]] = relationship(
    back_populates="object",
    cascade="all, delete-orphan",
    order_by="AppliedModelValidatorModel.position",
)
```

**Step 9: Run black**

```bash
poetry run black src/api/models/database.py
```

**Step 10: Commit**

```bash
git add src/api/models/database.py
git commit -m "refactor(models)!: replace inline validators with template-referenced models"
```

---

### Task 4: Update Pydantic Schemas

**Files:**
- Modify: `src/api/schemas/field.py`
- Modify: `src/api/schemas/object.py`
- Create: `src/api/schemas/field_validator_template.py`
- Create: `src/api/schemas/model_validator_template.py`

**Step 1: Create field_validator_template.py schema**

```python
# src/api/schemas/field_validator_template.py
"""Pydantic schemas for Field Validator Template entity."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FieldValidatorTemplateResponse(BaseModel):
    """Response schema for a field validator template.

    :ivar id: Unique identifier for the template.
    :ivar name: Template display name.
    :ivar description: Template description.
    :ivar compatible_types: List of type names this template applies to.
    :ivar mode: Validator mode (before, after).
    :ivar parameters: Template parameter definitions.
    :ivar body_template: Jinja2 template for the function body.
    """

    id: UUID
    name: str
    description: str
    compatible_types: list[str] = Field(..., alias="compatibleTypes")
    mode: str
    parameters: list[dict]
    body_template: str = Field(..., alias="bodyTemplate")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
```

**Step 2: Create model_validator_template.py schema**

```python
# src/api/schemas/model_validator_template.py
"""Pydantic schemas for Model Validator Template entity."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ModelValidatorTemplateResponse(BaseModel):
    """Response schema for a model validator template.

    :ivar id: Unique identifier for the template.
    :ivar name: Template display name.
    :ivar description: Template description.
    :ivar mode: Validator mode (before, after).
    :ivar parameters: Template parameter definitions.
    :ivar field_mappings: Field mapping definitions.
    :ivar body_template: Jinja2 template for the function body.
    """

    id: UUID
    name: str
    description: str
    mode: str
    parameters: list[dict]
    field_mappings: list[dict] = Field(..., alias="fieldMappings")
    body_template: str = Field(..., alias="bodyTemplate")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
```

**Step 3: Update FieldValidatorInput in field.py**

Replace the existing `FieldValidatorInput` class (lines 37-51):

```python
class FieldValidatorInput(BaseModel):
    """Request schema for attaching a field validator template to a field.

    :ivar template_id: Reference to the field validator template.
    :ivar parameters: Template parameter values.
    """

    template_id: UUID = Field(..., alias="templateId")
    parameters: dict[str, str] | None = Field(default=None)

    model_config = ConfigDict(populate_by_name=True)
```

**Step 4: Update FieldValidatorResponse in field.py**

Replace the existing `FieldValidatorResponse` class (lines 54-70):

```python
class FieldValidatorResponse(BaseModel):
    """Response schema for an applied field validator.

    :ivar id: Unique identifier for the applied validator.
    :ivar template_id: Reference to the template.
    :ivar parameters: Template parameter values.
    """

    id: UUID
    template_id: UUID = Field(..., alias="templateId")
    parameters: dict[str, str] | None = Field(default=None)

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
```

**Step 5: Update ModelValidatorInput in object.py**

Replace the existing `ModelValidatorInput` class (lines 24-38):

```python
class ModelValidatorInput(BaseModel):
    """Request schema for attaching a model validator template to an object.

    :ivar template_id: Reference to the model validator template.
    :ivar parameters: Template parameter values.
    :ivar field_mappings: Maps template field mapping keys to actual field names.
    """

    template_id: UUID = Field(..., alias="templateId")
    parameters: dict[str, str] | None = Field(default=None)
    field_mappings: dict[str, str] = Field(..., alias="fieldMappings")

    model_config = ConfigDict(populate_by_name=True)
```

**Step 6: Update ModelValidatorResponse in object.py**

Replace the existing `ModelValidatorResponse` class (lines 41-57):

```python
class ModelValidatorResponse(BaseModel):
    """Response schema for an applied model validator.

    :ivar id: Unique identifier for the applied validator.
    :ivar template_id: Reference to the template.
    :ivar parameters: Template parameter values.
    :ivar field_mappings: Resolved field name mappings.
    """

    id: UUID
    template_id: UUID = Field(..., alias="templateId")
    parameters: dict[str, str] | None = Field(default=None)
    field_mappings: dict[str, str] = Field(..., alias="fieldMappings")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
```

**Step 7: Run black**

```bash
poetry run black src/api/schemas/
```

**Step 8: Commit**

```bash
git add src/api/schemas/
git commit -m "refactor(schemas)!: replace inline validator schemas with template-referenced schemas"
```

---

### Task 5: Update Services — Field and Object

**Files:**
- Modify: `src/api/services/field.py`
- Modify: `src/api/services/object.py`

**Step 1: Update field service imports**

Replace `FieldValidatorModel` with `AppliedFieldValidatorModel` in imports. Also import `FieldValidatorTemplateModel` for validation.

**Step 2: Update field service _set_validators**

Replace the existing `_set_validators` method in `FieldService` (lines ~165-186):

```python
async def _set_validators(
    self, field: FieldModel, validators: list[FieldValidatorInput]
) -> None:
    await self.db.execute(
        delete(AppliedFieldValidatorModel).where(
            AppliedFieldValidatorModel.field_id == field.id
        )
    )
    for position, v in enumerate(validators):
        # Validate template exists
        template = await self.db.get(FieldValidatorTemplateModel, v.template_id)
        if not template:
            raise ValueError(f"Field validator template not found: {v.template_id}")
        validator = AppliedFieldValidatorModel(
            field_id=field.id,
            template_id=v.template_id,
            parameters=v.parameters,
            position=position,
        )
        self.db.add(validator)
    await self.db.flush()
```

**Step 3: Update field service _field_load_options**

Update `selectinload(FieldModel.validators)` to also load the template relationship:

```python
selectinload(FieldModel.validators).selectinload(
    AppliedFieldValidatorModel.template
),
```

**Step 4: Update object service imports and _set_validators**

Same pattern as field service — replace `ModelValidatorModel` with `AppliedModelValidatorModel`, validate template exists, store template_id + parameters + field_mappings.

```python
async def _set_validators(
    self, obj: ObjectDefinition, validators: list[ModelValidatorInput]
) -> None:
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
```

**Step 5: Update object service load options**

Add template eager loading to object service's validators selectinload.

**Step 6: Run black**

```bash
poetry run black src/api/services/
```

**Step 7: Commit**

```bash
git add src/api/services/field.py src/api/services/object.py
git commit -m "refactor(services)!: use template references for validator CRUD"
```

---

### Task 6: Update Routers — Fields and Objects Response Builders

**Files:**
- Modify: `src/api/routers/fields.py`
- Modify: `src/api/routers/objects.py`

**Step 1: Update field router _to_response**

Update the validator response builder in `_to_response` (lines ~28-64 of fields.py):

```python
validators = [
    FieldValidatorResponse(
        id=v.id,
        template_id=v.template_id,
        parameters=v.parameters,
    )
    for v in sorted(field.validators, key=lambda x: x.position)
]
```

**Step 2: Update object router response builder**

Same pattern — update to use `template_id`, `parameters`, `field_mappings` instead of `function_name`, `mode`, `function_body`, `description`.

**Step 3: Run black**

```bash
poetry run black src/api/routers/
```

**Step 4: Commit**

```bash
git add src/api/routers/fields.py src/api/routers/objects.py
git commit -m "refactor(api)!: update field/object routers for template-referenced validators"
```

---

### Task 7: Create Template Catalogue Services and Routers

**Files:**
- Create: `src/api/services/field_validator_template.py`
- Create: `src/api/services/model_validator_template.py`
- Create: `src/api/routers/field_validator_templates.py`
- Create: `src/api/routers/model_validator_templates.py`
- Modify: `src/api/routers/__init__.py`
- Modify: `src/api/main.py`

**Step 1: Create field_validator_template service**

Follow the `field_constraint.py` service pattern — `list_for_user` returns all templates (they're system-level, visible to all authenticated users):

```python
# src/api/services/field_validator_template.py
"""Service for Field Validator Template operations (read-only catalogue)."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.database import FieldValidatorTemplateModel


class FieldValidatorTemplateService:
    """Service for field validator template operations.

    :param db: Async database session.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_all(self) -> list[FieldValidatorTemplateModel]:
        """List all field validator templates.

        :returns: List of all field validator templates.
        """
        result = await self.db.execute(
            select(FieldValidatorTemplateModel).order_by(
                FieldValidatorTemplateModel.name
            )
        )
        return list(result.scalars().all())


def get_field_validator_template_service(
    db: AsyncSession,
) -> FieldValidatorTemplateService:
    """Factory for FieldValidatorTemplateService.

    :param db: Async database session.
    :returns: FieldValidatorTemplateService instance.
    """
    return FieldValidatorTemplateService(db)
```

**Step 2: Create model_validator_template service**

Same pattern as above for `ModelValidatorTemplateModel`.

**Step 3: Create field_validator_templates router**

Follow the `field_constraints.py` router pattern:

```python
# src/api/routers/field_validator_templates.py
"""Router for Field Validator Template endpoints (read-only)."""

from fastapi import APIRouter

from api.deps import DbSession, ProvisionedUser
from api.schemas.field_validator_template import FieldValidatorTemplateResponse
from api.services.field_validator_template import (
    FieldValidatorTemplateService,
    get_field_validator_template_service,
)

router = APIRouter(
    prefix="/field-validator-templates", tags=["Field Validator Templates"]
)


def get_service(db: DbSession) -> FieldValidatorTemplateService:
    """Get field validator template service instance.

    :param db: Database session.
    :returns: FieldValidatorTemplateService instance.
    """
    return get_field_validator_template_service(db)


@router.get(
    "",
    response_model=list[FieldValidatorTemplateResponse],
    summary="List all field validator templates",
    description="Retrieve all field validator template definitions.",
)
async def list_field_validator_templates(
    user: ProvisionedUser,
    db: DbSession,
) -> list[FieldValidatorTemplateResponse]:
    """List all field validator templates.

    :param user: Authenticated user.
    :param db: Database session.
    :returns: List of field validator template responses.
    """
    service = get_service(db)
    templates = await service.list_all()
    return [
        FieldValidatorTemplateResponse.model_validate(t) for t in templates
    ]
```

**Step 4: Create model_validator_templates router**

Same pattern for model validator templates.

**Step 5: Register routers**

Add imports to `src/api/routers/__init__.py` and `include_router` calls to `src/api/main.py`.

**Step 6: Run black**

```bash
poetry run black src/api/
```

**Step 7: Commit**

```bash
git add src/api/services/field_validator_template.py src/api/services/model_validator_template.py \
    src/api/routers/field_validator_templates.py src/api/routers/model_validator_templates.py \
    src/api/routers/__init__.py src/api/main.py
git commit -m "feat(api): add read-only field and model validator template catalogue endpoints"
```

---

### Task 8: Update Generation Service for Template Resolution

**Files:**
- Modify: `src/api/services/generation.py`

**Step 1: Add Jinja2 rendering**

Add a template resolution function and update `_build_validators` to handle applied field validators. Also add a new function to build model validators from applied model validators.

```python
from jinja2 import Environment

def _render_template(body_template: str, context: dict[str, str]) -> str:
    """Render a Jinja2 body template with the given context.

    :param body_template: Jinja2 template string.
    :param context: Template variables to substitute.
    :returns: Rendered Python code string.
    """
    env = Environment()
    template = env.from_string(body_template)
    return template.render(**context)
```

**Step 2: Update _fetch_fields to eagerly load validator templates**

Add `selectinload(FieldModel.validators).selectinload(AppliedFieldValidatorModel.template)` to the field query in `_fetch_fields` (line ~133).

**Step 3: Update _fetch_objects to eagerly load model validator templates**

Add `selectinload(ObjectDefinition.validators).selectinload(AppliedModelValidatorModel.template)` to the object query in `_fetch_objects` (line ~93).

**Step 4: Rewrite _build_validators to handle both constraints and applied field validators**

The current function only builds from constraints. Extend it to also build from applied validators:

```python
def _build_field_validators(field: FieldModel) -> list[InputValidator]:
    """Convert field constraints AND applied field validators to InputValidator list.

    :param field: Field model with constraint_values and validators loaded.
    :returns: List of InputValidator instances for code generation.
    """
    validators = []
    # Existing constraint-based validators (Field() parameters)
    for cv in field.constraint_values:
        parsed = _parse_constraint_value(cv.value, cv.constraint.parameter_types)
        params = {"value": parsed} if parsed is not None else None
        validators.append(InputValidator(name=cv.constraint.name, params=params))
    return validators
```

Note: The applied field validators generate `@field_validator` decorated functions, which is a different code generation path than constraints (which generate `Field()` parameters). This requires extending api_craft's `InputField` model and Mako templates — covered in Task 9.

**Step 5: Add function to build resolved field validator code**

```python
def _build_resolved_field_validators(
    field: FieldModel,
) -> list[dict]:
    """Resolve applied field validators to function definitions.

    :param field: Field model with validators and templates loaded.
    :returns: List of dicts with function_name, mode, function_body.
    """
    resolved = []
    for v in sorted(field.validators, key=lambda x: x.position):
        template = v.template
        context = v.parameters or {}
        function_body = _render_template(template.body_template, context)
        function_name = f"{template.name.lower().replace(' ', '_').replace('&', 'and')}_{field.name}"
        resolved.append({
            "function_name": function_name,
            "mode": template.mode,
            "function_body": function_body,
        })
    return resolved
```

**Step 6: Add function to build resolved model validator code**

```python
def _build_resolved_model_validators(
    obj: ObjectDefinition,
) -> list[dict]:
    """Resolve applied model validators to function definitions.

    :param obj: Object model with validators and templates loaded.
    :returns: List of dicts with function_name, mode, function_body.
    """
    resolved = []
    for v in sorted(obj.validators, key=lambda x: x.position):
        template = v.template
        context = {**(v.parameters or {}), **v.field_mappings}
        function_body = _render_template(template.body_template, context)
        function_name = f"validate_{template.name.lower().replace(' ', '_').replace('&', 'and')}"
        resolved.append({
            "function_name": function_name,
            "mode": template.mode,
            "function_body": function_body,
        })
    return resolved
```

**Step 7: Run black and commit**

```bash
poetry run black src/api/services/generation.py
git add src/api/services/generation.py
git commit -m "feat(generation): add Jinja2 template resolution for validators at generation time"
```

---

### Task 9: Extend api_craft to Support @field_validator and @model_validator Code Generation

**Files:**
- Modify: `src/api_craft/models/input.py`
- Modify: `src/api_craft/models/template.py`
- Modify: `src/api_craft/transformers.py`
- Modify: `src/api_craft/templates/models.mako`

This task extends the code generation pipeline to render `@field_validator` and `@model_validator` decorated functions. Currently api_craft only generates `Field()` constraint parameters — it has no support for validator functions.

**Step 1: Add resolved validator models to input.py**

Add a new model for resolved (pre-rendered) validators:

```python
class InputResolvedFieldValidator(BaseModel):
    """A resolved field validator with final Python code.

    :ivar function_name: Generated function name.
    :ivar mode: Validator mode (before, after).
    :ivar function_body: Rendered Python function body.
    """

    function_name: str
    mode: str
    function_body: str


class InputResolvedModelValidator(BaseModel):
    """A resolved model validator with final Python code.

    :ivar function_name: Generated function name.
    :ivar mode: Validator mode (before, after).
    :ivar function_body: Rendered Python function body.
    """

    function_name: str
    mode: str
    function_body: str
```

Add `field_validators` to `InputField` and `model_validators` to `InputModel`:

```python
class InputField(BaseModel):
    # ... existing fields ...
    field_validators: list[InputResolvedFieldValidator] = []

class InputModel(BaseModel):
    # ... existing fields ...
    model_validators: list[InputResolvedModelValidator] = []
```

**Step 2: Add corresponding template models**

Add to `template.py` and update `transformers.py` to pass them through.

**Step 3: Update models.mako to render @field_validator and @model_validator**

Add Mako template blocks that render the resolved validator functions after the model class fields. This requires generating properly decorated Python functions.

**Step 4: Update generation.py _convert_to_input_api to pass resolved validators**

Wire the `_build_resolved_field_validators` and `_build_resolved_model_validators` into the `InputField` and `InputModel` construction in `_convert_to_input_api`.

**Step 5: Run black and commit**

```bash
poetry run black src/api_craft/
git add src/api_craft/
git commit -m "feat(generation): extend api_craft to generate @field_validator and @model_validator code"
```

---

### Task 10: Update All References to Renamed Tables/Models

**Files:**
- Search and update all files referencing old model names or table names

**Step 1: Find all references to old names**

Search for: `FieldValidatorModel`, `ModelValidatorModel`, `FieldConstraintValueAssociation`, `ObjectFieldAssociation`, `field_constraint_field_associations`, `object_field_associations`, `field_validators` (as table name), `model_validators` (as table name).

**Step 2: Update imports across all files**

Update every file that imports these models to use the new names:
- `FieldValidatorModel` → `AppliedFieldValidatorModel`
- `ModelValidatorModel` → `AppliedModelValidatorModel`
- Table name references in raw SQL or Alembic operations

Also rename `FieldConstraintValueAssociation` → `AppliedConstraintModel` and `ObjectFieldAssociation` → `FieldOnObjectModel` for consistency with the new table names (update `__tablename__` was done in Task 3, but the class names should also match).

**Step 3: Run black and commit**

```bash
poetry run black src/ tests/
git add -A
git commit -m "refactor: update all references to renamed validator and junction table models"
```

---

### Task 11: Update Tests

**Files:**
- Modify: `tests/test_api/test_services/test_field_validator.py`
- Modify: `tests/test_api/test_services/test_model_validator.py`
- Modify: `tests/test_api/test_services/test_field.py`
- Modify: `tests/test_api/test_services/test_object.py`
- Create: `tests/test_api/test_services/test_field_validator_template.py`
- Create: `tests/test_api/test_services/test_model_validator_template.py`

**Step 1: Create template catalogue tests**

Test that all 9 field validator templates and 6 model validator templates are seeded and returned by the service:

```python
# tests/test_api/test_services/test_field_validator_template.py
pytestmark = pytest.mark.integration

class TestFieldValidatorTemplateService:
    async def test_list_all_returns_seeded_templates(self, db_session, provisioned_namespace):
        service = FieldValidatorTemplateService(db_session)
        templates = await service.list_all()
        assert len(templates) == 9
        names = {t.name for t in templates}
        assert "Strip & Normalize Case" in names
        assert "Future Date Only" in names
```

**Step 2: Update field validator tests**

Replace raw `functionBody`/`functionName` test data with `templateId` + `parameters`. Use seeded template UUIDs from the seed migration.

**Step 3: Update model validator tests**

Same pattern — use `templateId` + `parameters` + `fieldMappings`.

**Step 4: Update field and object service tests**

Update any tests that create fields/objects with validators to use the new input format.

**Step 5: Run all tests**

```bash
poetry run pytest tests/ -v
```

**Step 6: Commit**

```bash
poetry run black tests/
git add tests/
git commit -m "test: update all validator tests for template-referenced model"
```

---

### Task 12: Reset Local Database and Verify

**Step 1: Reset local database**

```bash
# Drop and recreate
docker compose down -v
docker compose up -d
poetry run alembic upgrade head
```

**Step 2: Run full test suite**

```bash
poetry run pytest tests/ -v
```

**Step 3: Verify API manually**

Start the server and test:
- `GET /v1/field-validator-templates` returns 9 templates
- `GET /v1/model-validator-templates` returns 6 templates
- Creating a field with `validators: [{templateId: "...", parameters: {...}}]` works
- Creating an object with model validators works
- GET field/object returns the applied validators with templateId

**Step 4: Final formatting check**

```bash
poetry run black src/ tests/
```

**Step 5: Commit any fixes**

```bash
git add -A
git commit -m "chore: final cleanup after validator template catalogues implementation"
```
