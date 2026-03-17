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
<%
    query_args = [f'title="{param.title}"']
    if param.constraints:
        for key in sorted(param.constraints):
            query_args.append(f"{key}={param.constraints[key]}")
%>\

${param.camel_name} = Annotated[
    ${param.type},
    Query(
        ${", ".join(query_args)},
    ),
]
% endfor

