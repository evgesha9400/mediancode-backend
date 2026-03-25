# src/api_craft/schema_splitter.py
"""Schema splitting: derives Create/Update/Response schemas from InputModel.

FK injection uses the full model graph: for each one_to_one/one_to_many
relationship targeting a model, inject ``{inverse_name}_id`` into Create,
Update, and Response schemas.
"""

from api_craft.models.input import InputAPI, InputField, InputModel
from api_craft.models.types import PascalCaseName


def _resolve_fk_type(
    target_model_name: str,
    all_models: list[InputModel] | None = None,
) -> str:
    """Resolve the FK field type from the target model's PK type.

    Falls back to "uuid" if the target model or its PK cannot be found.
    """
    if all_models:
        target = next((m for m in all_models if str(m.name) == target_model_name), None)
        if target:
            pk_field = next((f for f in target.fields if f.pk), None)
            if pk_field:
                return pk_field.type
    return "uuid"


def split_model_schemas(
    input_model: InputModel,
    all_models: list[InputModel] | None = None,
) -> list[InputModel]:
    """Split an InputModel into Create, Update, and Response InputModels.

    - Create: fields with exposure in (read_write, write_only), PK excluded
    - Update: same as Create but all fields nullable
    - Response: fields with exposure in (read_write, read_only), PK included

    FK fields are injected from the full model graph for incoming
    one_to_one and one_to_many relationships.
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

    # Inject FK fields from incoming relationships across the full graph
    if all_models:
        model_name = str(input_model.name)
        for source_model in all_models:
            for rel in source_model.relationships:
                if rel.target_model != model_name:
                    continue
                if rel.kind not in ("one_to_one", "one_to_many"):
                    continue

                fk_name = f"{rel.inverse_name}_id"
                # Resolve FK type from the source model's PK
                fk_type = _resolve_fk_type(str(source_model.name), all_models)
                is_required = rel.required

                # Add to Create
                existing_create = {str(f.name) for f in create_fields}
                if fk_name not in existing_create:
                    create_fields.append(
                        InputField(
                            type=fk_type,
                            name=fk_name,
                            nullable=not is_required,
                            description=f"FK reference to {source_model.name}",
                        )
                    )

                # Add to Update (always nullable on partial update)
                existing_update = {str(f.name) for f in update_fields}
                if fk_name not in existing_update:
                    update_fields.append(
                        InputField(
                            type=fk_type,
                            name=fk_name,
                            nullable=True,
                            description=f"FK reference to {source_model.name}",
                        )
                    )

                # Add to Response
                existing_response = {str(f.name) for f in response_fields}
                if fk_name not in existing_response:
                    response_fields.append(
                        InputField(
                            type=fk_type,
                            name=fk_name,
                            nullable=not is_required,
                            description=f"FK reference to {source_model.name}",
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
