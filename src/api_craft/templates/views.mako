<%doc>
- Template Parameters:
- views (list): A list of views to generate
- database_config: TemplateDatabaseConfig | None
- orm_model_map: dict[str, str] | None - maps response model name to ORM class name
- orm_pk_map: dict[str, str] | None - maps primary key field name to ORM class name
</%doc>\
% if database_config:
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session
% else:
from fastapi import APIRouter
% endif
<%
model_names = []
for view in views:
    if view.response_model and view.response_model not in model_names:
        model_names.append(view.response_model)
    if view.request_model and view.request_model not in model_names:
        model_names.append(view.request_model)
has_path_params = any(view.path_params for view in views)
has_query_params = any(view.query_params for view in views)
has_no_response = any(not view.response_model for view in views)
orm_model_names_from_response = {
    orm_model_map[view.response_model]
    for view in views
    if view.response_model and orm_model_map and view.response_model in orm_model_map
}
orm_model_names_from_pk = set()
if orm_pk_map:
    for view in views:
        if view.method == "delete" and not view.response_model and view.path_params:
            for p in view.path_params:
                if p.snake_name in orm_pk_map:
                    orm_model_names_from_pk.add(orm_pk_map[p.snake_name])
orm_model_names = sorted(orm_model_names_from_response | orm_model_names_from_pk)
%>
% if has_no_response:
from starlette.responses import Response
% endif
% if model_names:
from models import (
% for index, name in enumerate(model_names):
    ${name}${"," if index < len(model_names) - 1 else ""}
% endfor
)
% endif
% if database_config and orm_model_names:
from orm_models import (
% for index, name in enumerate(orm_model_names):
    ${name}${"," if index < len(orm_model_names) - 1 else ""}
% endfor
)
% endif
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
        suffix = " = None" if q_param.optional else ""
        signature_lines.append(
            f"    {q_param.snake_name}: query.{q_param.camel_name}{suffix},"
        )
    if database_config:
        signature_lines.append("    session: AsyncSession = Depends(get_session),")
    has_signature = bool(signature_lines)
    # Determine if this view's response model has an ORM model
    has_orm = orm_model_map and view.response_model and view.response_model in orm_model_map
    orm_class = orm_model_map.get(view.response_model, "") if orm_model_map and view.response_model else ""
    # For delete without response model, resolve ORM class from path param PK
    if not has_orm and view.method == "delete" and orm_pk_map and view.path_params:
        for p in view.path_params:
            if p.snake_name in orm_pk_map:
                orm_class = orm_pk_map[p.snake_name]
                has_orm = True
                break
%>
@api_router.${view.method}(
    path="${view.path}",
% if view.response_model:
% if view.response_shape == "list":
    response_model=list[${view.response_model}],
% else:
    response_model=${view.response_model},
% endif
% else:
    status_code=204,
% endif
% if view.tag:
    tags=["${view.tag}"],
% endif
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
% if database_config and has_orm:
## Database-backed view body
% if view.method == "get" and view.response_shape == "list":
    result = await session.execute(select(${orm_class}))
    return result.scalars().all()
% elif view.method == "get":
<%
    pk_param = view.path_params[0].snake_name if view.path_params else "id"
%>\
    result = await session.execute(select(${orm_class}).where(${orm_class}.${pk_param} == ${pk_param}))
    record = result.scalars().first()
    if not record:
        raise HTTPException(status_code=404, detail="${view.response_model} not found")
    return record
% elif view.method == "post":
    data = request.model_dump()
    for k, v in data.items():
        if type(v).__module__.startswith("pydantic"):
            data[k] = str(v)
    record = ${orm_class}(**data)
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record
% elif view.method == "put" or view.method == "patch":
<%
    pk_param = view.path_params[0].snake_name if view.path_params else "id"
%>\
    result = await session.execute(select(${orm_class}).where(${orm_class}.${pk_param} == ${pk_param}))
    record = result.scalars().first()
    if not record:
        raise HTTPException(status_code=404, detail="${view.response_model} not found")
    for key, value in request.model_dump(exclude_unset=True).items():
        if type(value).__module__.startswith("pydantic"):
            value = str(value)
        setattr(record, key, value)
    await session.commit()
    await session.refresh(record)
    return record
% elif view.method == "delete":
<%
    pk_param = view.path_params[0].snake_name if view.path_params else "id"
%>\
    result = await session.execute(select(${orm_class}).where(${orm_class}.${pk_param} == ${pk_param}))
    record = result.scalars().first()
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    await session.delete(record)
    await session.commit()
    return Response(status_code=204)
% endif
% else:
## Non-database view body (placeholder)
    # TODO: implement your view
% if not view.response_model:
    return Response(status_code=204)
% elif view.response_shape == "list":
% if view.response_placeholders:
    return [${view.response_model}(
%     for field_name, value in view.response_placeholders.items():
        ${field_name}=${value.__repr__()},
%     endfor
    )]
% else:
    return [${view.response_model}()]
% endif
% else:
% if view.response_placeholders:
    return ${view.response_model}(
%     for field_name, value in view.response_placeholders.items():
        ${field_name}=${value.__repr__()},
%     endfor
    )
% else:
    return ${view.response_model}()
% endif
% endif
% endif
% endfor