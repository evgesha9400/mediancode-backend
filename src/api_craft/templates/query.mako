<%doc>
- Parameters:
- params : List of TemplateQueryParam
- imports : Set[str] - set of import statements
</%doc>\
"""This module contains query parameter type definitions and validators."""
% for import_stmt in sorted(imports):
${import_stmt}
% endfor
from typing import Annotated
from fastapi import Query
% for param in params:

${param.camel_name} = Annotated[
    ${param.type},
    Query(
        title="${param.title}",
    ),
]
% endfor

