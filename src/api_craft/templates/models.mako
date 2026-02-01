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

# Check if any model has validators
has_validators = any(
    any(field.validators for field in model.fields)
    for model in models
)
%>\
% for import_stmt in sorted(imports):
${import_stmt}
% endfor
from pydantic import BaseModel${', Field' if has_validators else ''}
% for model in models:


class ${model.name}(BaseModel):
%     for field in model.fields:
    ${render_field(field)}
%     endfor
% endfor

