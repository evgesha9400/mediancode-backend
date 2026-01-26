<%doc>
- Parameters:
- param : List of TemplateQueryParam
</%doc>\
"""This module contains query parameter type definitions and validators."""
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

