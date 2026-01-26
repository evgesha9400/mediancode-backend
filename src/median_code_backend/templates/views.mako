<%doc>
- Template Parameters:
- views (list): A list of views to generate
</%doc>\
from fastapi import APIRouter
<%
model_names = []
for view in views:
    if view.response_model and view.response_model not in model_names:
        model_names.append(view.response_model)
    if view.request_model and view.request_model not in model_names:
        model_names.append(view.request_model)
has_path_params = any(view.path_params for view in views)
has_query_params = any(view.query_params for view in views)
%>
from models import (
% for index, name in enumerate(model_names):
    ${name}${"," if index < len(model_names) - 1 else ""}
% endfor
)
% if has_path_params:
import path
% endif
% if has_query_params:
import query
% endif


api_router = APIRouter()
% for view in views:

<%
    signature_lines = []
    for p_param in (view.path_params or []):
        signature_lines.append(f"    {p_param.snake_name}: path.{p_param.camel_name},")
    if view.request_model:
        signature_lines.append(f"    request: {view.request_model},")
    for q_param in (view.query_params or []):
        suffix = "" if q_param.required else " = None"
        signature_lines.append(
            f"    {q_param.snake_name}: query.{q_param.camel_name}{suffix},"
        )
    has_signature = bool(signature_lines)
%>
@api_router.${view.method}(
    path="${view.path}",
    response_model=${view.response_model}
)
% if has_signature:
async def ${view.snake_name}(
%     for line in signature_lines:
${line}
%     endfor
):
% else:
async def ${view.snake_name}():
% endif
    # TODO: implement your view
% if view.response_placeholders:
    return ${view.response_model}(
%     for field_name, value in view.response_placeholders.items():
        ${field_name}=${value.__repr__()},
%     endfor
    )
% else:
    return ${view.response_model}()
% endif
% endfor