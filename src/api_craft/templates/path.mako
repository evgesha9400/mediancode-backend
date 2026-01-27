<%doc>
- Template Parameters:
- params (list): List of TemplatePathParam
- imports : Set[str] - set of import statements
</%doc>\
"""This module contains validators for path parameters."""
% for import_stmt in sorted(imports):
${import_stmt}
% endfor
from typing import Annotated
from fastapi import Path
% for param in params:

${param.camel_name} = Annotated[
    ${param.type},
    Path(
        title="${param.title}",
    ),
]
% endfor

