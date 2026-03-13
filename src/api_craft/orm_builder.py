# src/api_craft/orm_builder.py
"""ORM model generation: converts InputModels into SQLAlchemy TemplateORMModels."""

from api_craft.models.input import InputModel
from api_craft.models.template import (
    TemplateORMField,
    TemplateORMModel,
    TemplateRelationship,
)
from api_craft.utils import camel_to_snake, snake_to_plural

# Map input type names to Python type annotations for Mapped[].
# Keys match the canonical python_type values from the system types table.
# The fallback in transform_orm_models splits qualified names on "." and
# retries with the base module (e.g. "decimal.Decimal" → "decimal"), so
# entries like "datetime.date" are required to avoid resolving to the
# wrong base entry ("datetime" → "datetime.datetime").
ORM_PYTHON_TYPE_MAP = {
    "str": "str",
    "int": "int",
    "float": "float",
    "bool": "bool",
    "datetime": "datetime.datetime",
    "datetime.date": "datetime.date",
    "datetime.time": "datetime.time",
    "uuid": "uuid.UUID",
    "decimal": "decimal.Decimal",
    "EmailStr": "str",
    "HttpUrl": "str",
}


def _get_max_length(validators):
    """Extract max_length value from validators list."""
    for v in validators:
        if v.name == "max_length" and v.params and "value" in v.params:
            return v.params["value"]
    return None


def map_column_type(type_str: str, validators: list) -> str | None:
    """Map a Python type string to a SQLAlchemy column type string.

    Returns None for types that cannot be mapped to columns (List, Dict, model refs).
    """
    # Skip collection types
    if type_str.startswith(("List[", "Dict[", "Set[", "Tuple[")):
        return None

    type_map = {
        "str": lambda: (
            f"String({ml})" if (ml := _get_max_length(validators)) else "Text"
        ),
        "int": lambda: "Integer",
        "float": lambda: "Float",
        "bool": lambda: "Boolean",
        "datetime": lambda: "DateTime(timezone=True)",
        "datetime.date": lambda: "Date",
        "datetime.time": lambda: "Time",
        "uuid": lambda: "Uuid",
        "decimal": lambda: "Numeric",
        "EmailStr": lambda: "String(320)",
        "HttpUrl": lambda: "Text",
    }

    # Try full qualified name first (e.g. "datetime.date"), then base module name
    factory = type_map.get(type_str)
    if factory is None:
        base = type_str.split(".")[0] if "." in type_str else type_str
        factory = type_map.get(base)
    if factory is None:
        return None
    return factory()


def _make_association_table_name(table_a: str, table_b: str) -> str:
    """Build a deterministic association table name for many_to_many.

    Sorts the two table names alphabetically to ensure the same name
    regardless of which side declares the relationship.

    :param table_a: First table name.
    :param table_b: Second table name.
    :returns: Association table name.
    """
    return "_".join(sorted([table_a, table_b]))


def transform_orm_models(input_models: list[InputModel]) -> list[TemplateORMModel]:
    """Convert InputModels with pk fields into TemplateORMModels."""
    # Build entity lookup: name -> (table_name, pk_column_name, class_name)
    entity_lookup: dict[str, tuple[str, str, str]] = {}
    for model in input_models:
        pk_fields = [f for f in model.fields if f.pk]
        if pk_fields:
            table_name = snake_to_plural(camel_to_snake(model.name))
            class_name = f"{model.name}Record"
            entity_lookup[str(model.name)] = (
                table_name,
                str(pk_fields[0].name),
                class_name,
            )

    orm_models = []
    for model in input_models:
        pk_fields = [f for f in model.fields if f.pk]
        if not pk_fields:
            continue

        table_name = snake_to_plural(camel_to_snake(model.name))
        orm_fields = []

        for field in model.fields:
            column_type = map_column_type(field.type, field.validators)
            if column_type is None:
                continue

            base_type = field.type.split(".")[0] if "." in field.type else field.type
            orm_type = ORM_PYTHON_TYPE_MAP.get(field.type) or ORM_PYTHON_TYPE_MAP.get(
                base_type, base_type
            )
            python_type = orm_type if not field.optional else f"{orm_type} | None"

            is_uuid_pk = field.pk and base_type in ("uuid", "UUID")
            orm_fields.append(
                TemplateORMField(
                    name=str(field.name),
                    python_type=python_type,
                    column_type=column_type,
                    primary_key=field.pk,
                    nullable=field.optional,
                    autoincrement=field.pk and base_type in ("int",),
                    uuid_default=is_uuid_pk,
                )
            )

        # Transform relationships
        template_rels = []
        for rel in model.relationships:
            target_info = entity_lookup.get(rel.target_model)
            if not target_info:
                continue
            target_table, target_pk, target_class = target_info

            fk_column = None
            association_table = None

            if rel.cardinality == "references":
                # Add FK column to this model's fields
                fk_col_name = f"{rel.name}_id"
                # Determine FK column type from target PK
                target_model = next(
                    (m for m in input_models if str(m.name) == rel.target_model),
                    None,
                )
                if target_model:
                    target_pk_field = next(
                        (f for f in target_model.fields if f.pk), None
                    )
                    if target_pk_field:
                        fk_col_type = map_column_type(
                            target_pk_field.type, target_pk_field.validators
                        )
                        fk_base = (
                            target_pk_field.type.split(".")[0]
                            if "." in target_pk_field.type
                            else target_pk_field.type
                        )
                        fk_orm_type = ORM_PYTHON_TYPE_MAP.get(
                            target_pk_field.type
                        ) or ORM_PYTHON_TYPE_MAP.get(fk_base, fk_base)
                        if fk_col_type:
                            orm_fields.append(
                                TemplateORMField(
                                    name=fk_col_name,
                                    python_type=fk_orm_type,
                                    column_type=fk_col_type,
                                    foreign_key=f"{target_table}.{target_pk}",
                                )
                            )
                fk_column = fk_col_name

            elif rel.cardinality == "many_to_many":
                association_table = _make_association_table_name(
                    table_name, target_table
                )

            template_rels.append(
                TemplateRelationship(
                    name=rel.name,
                    target_model=rel.target_model,
                    target_class_name=target_class,
                    cardinality=rel.cardinality,
                    is_inferred=rel.is_inferred,
                    fk_column=fk_column,
                    association_table=association_table,
                )
            )

        orm_models.append(
            TemplateORMModel(
                class_name=f"{model.name}Record",
                table_name=table_name,
                source_model=str(model.name),
                fields=orm_fields,
                relationships=template_rels,
            )
        )

    return orm_models
