<%doc>
- Template Parameters:
- models: List[TemplateModel]
- imports: Set[str] - set of import statements
</%doc>\
<%
def render_field_constraint(validator):
    """Render a validator as a Pydantic Field constraint."""
    name = validator.name
    params = validator.params or {}
    value = params.get('value')

    # Map validator names to Pydantic Field parameter names
    constraint_map = {
        'min_length': 'min_length',
        'max_length': 'max_length',
        'pattern': 'pattern',
        'gt': 'gt',
        'ge': 'ge',
        'lt': 'lt',
        'le': 'le',
        'multiple_of': 'multiple_of',
    }

    pydantic_name = constraint_map.get(name)
    if not pydantic_name:
        return None

    if pydantic_name == 'pattern':
        # Pattern needs to be a raw string
        return f'{pydantic_name}=r"{value}"'
    elif isinstance(value, str):
        return f'{pydantic_name}="{value}"'
    else:
        return f'{pydantic_name}={value}'

def render_field(field):
    """Render a complete field definition with validators."""
    constraints = []
    for v in field.validators:
        constraint = render_field_constraint(v)
        if constraint:
            constraints.append(constraint)

    type_annotation = field.type

    if constraints:
        field_args = ', '.join(constraints)
        if field.required:
            return f'{field.name}: {type_annotation} = Field({field_args})'
        else:
            return f'{field.name}: {type_annotation} | None = Field(default=None, {field_args})'
    else:
        if field.required:
            return f'{field.name}: {type_annotation}'
        else:
            return f'{field.name}: {type_annotation} | None = None'

# Check if any model has Field() constraints
has_field_constraints = any(
    any(field.validators for field in model.fields)
    for model in models
)

# Check if any model has @field_validator functions
has_field_validators = any(
    any(field.field_validators for field in model.fields)
    for model in models
)

# Check if any model has @model_validator functions
has_model_validators = any(
    model.model_validators
    for model in models
)

# Build pydantic imports
pydantic_imports = ['BaseModel']
if has_field_constraints:
    pydantic_imports.append('Field')
if has_field_validators:
    pydantic_imports.append('field_validator')
if has_model_validators:
    pydantic_imports.append('model_validator')
%>\
% for import_stmt in sorted(imports):
${import_stmt}
% endfor
from pydantic import ${', '.join(sorted(pydantic_imports))}
% for model in models:


class ${model.name}(BaseModel):
%     for field in model.fields:
    ${render_field(field)}
%     endfor
%     for field in model.fields:
%         for fv in field.field_validators:

    @field_validator("${field.name}", mode="${fv.mode}")
    @classmethod
    def ${fv.function_name}(cls, v):
${fv.function_body}
%         endfor
%     endfor
%     for mv in model.model_validators:

    @model_validator(mode="${mv.mode}")
%         if mv.mode == "before":
    @classmethod
    def ${mv.function_name}(cls, data):
%         else:
    def ${mv.function_name}(self):
%         endif
${mv.function_body}
%     endfor
% endfor
