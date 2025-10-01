<%doc>
- Template Parameters:
- models: List[TemplateModel]
- typing_imports: Set[str]
</%doc>\
from pydantic import BaseModel
% if typing_imports:
from typing import ${", ".join(typing_imports)}
% endif
% for model in models:


class ${model.name}(BaseModel):
%     for field in model.fields:
    ${field.name}: ${field.type}${" " if field.required else " = None"}
%     endfor
% endfor

