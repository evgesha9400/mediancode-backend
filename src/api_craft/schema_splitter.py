# src/api_craft/schema_splitter.py
"""Schema splitting: derives Create/Update/Response schemas from InputModel."""

from api_craft.models.input import InputAPI, InputField, InputModel
from api_craft.models.types import PascalCaseName


def split_model_schemas(input_model: InputModel) -> list[InputModel]:
    """Split an InputModel into Create, Update, and Response InputModels.

    - Create: fields with exposure in (read_write, write_only), PK excluded
    - Update: same as Create but all fields nullable
    - Response: fields with exposure in (read_write, read_only), PK included
    """
    model_validators = list(input_model.model_validators)

    # Create fields: non-PK, exposure allows writing
    create_fields = [
        f
        for f in input_model.fields
        if f.exposure in ("read_write", "write_only") and not f.pk
    ]

    # Update fields: same selection as Create but all nullable
    update_fields = [f.model_copy(update={"nullable": True}) for f in create_fields]

    # Response fields: exposure allows reading (PK included)
    response_fields = list(
        f for f in input_model.fields if f.exposure in ("read_write", "read_only")
    )

    # Add FK ID fields for `references` relationships
    for rel in input_model.relationships:
        if rel.cardinality == "references":
            fk_name = f"{rel.name}_id"
            existing_names = {str(f.name) for f in response_fields}
            if fk_name not in existing_names:
                response_fields.append(
                    InputField(
                        type="uuid",
                        name=fk_name,
                        nullable=False,
                        description=f"FK reference to {rel.target_model}",
                    )
                )

    return [
        InputModel(
            name=PascalCaseName(f"{input_model.name}Create"),
            fields=create_fields,
            description=input_model.description,
            model_validators=model_validators,
        ),
        InputModel(
            name=PascalCaseName(f"{input_model.name}Update"),
            fields=update_fields,
            description=input_model.description,
            model_validators=[],
        ),
        InputModel(
            name=PascalCaseName(f"{input_model.name}Response"),
            fields=response_fields,
            description=input_model.description,
            model_validators=[],
        ),
    ]


def _model_needs_split(model: InputModel) -> bool:
    """Check if a single model uses non-default exposure flags or has pk=True."""
    for field in model.fields:
        if field.exposure != "read_write" or field.pk:
            return True
    return False


def _has_appears_flags(input_api: InputAPI) -> bool:
    """Check if any field in the API uses non-default exposure flags or has pk=True."""
    return any(_model_needs_split(model) for model in input_api.objects)
