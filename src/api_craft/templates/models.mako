<%doc>
- Template Parameters:
- models: List[TemplateModel]
- imports: Set[str] - set of import statements
</%doc>\
% for import_stmt in sorted(imports):
${import_stmt}
% endfor
from pydantic import BaseModel
% for model in models:


class ${model.name}(BaseModel):
%     for field in model.fields:
    ${field.name}: ${field.type}${" " if field.required else " = None"}
%     endfor
% endfor

