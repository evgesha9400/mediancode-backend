<%doc>
- Template Parameters:
- models: List[InputModel] - model definitions to generate
- imports: Set[str] - set of import statements
- pydantic_imports: List[str] - sorted pydantic import names (e.g. ["BaseModel", "Field"])
- render_field: callable(field) -> str - renders a field definition line
- indent_body: callable(body, spaces=4) -> str - indents a function body
</%doc>\
% for import_stmt in sorted(imports):
${import_stmt}
% endfor
from pydantic import ${', '.join(pydantic_imports)}
% for model in models:


class ${model.name}(BaseModel):
%     if str(model.name).endswith('Response'):
    model_config = ConfigDict(from_attributes=True)

%     endif
%     for field in model.fields:
    ${render_field(field)}
%     endfor
%     for field in model.fields:
%         for fv in field.field_validators:

    @field_validator("${field.name}", mode="${fv.mode}")
    @classmethod
    def ${fv.function_name}(cls, v):
${indent_body(fv.function_body)}
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
${indent_body(mv.function_body)}
%     endfor
% endfor
