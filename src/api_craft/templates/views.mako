<%doc>
- Template Parameters:
- views (list): A list of PreparedView instances
- database_config: TemplateDatabaseConfig | None
- orm_model_map: dict[str, str] (kept for backward compat, logic moved to prepare.py)
- orm_pk_map: dict[str, str] (kept for backward compat, logic moved to prepare.py)
- api: PreparedAPI (provides pre-computed import data)
</%doc>\
% if database_config:
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session
% else:
from fastapi import APIRouter
% endif
% if api.has_no_response:
from starlette.responses import Response
% endif
% if api.view_model_names:
from models import (
% for index, name in enumerate(api.view_model_names):
    ${name}${"," if index < len(api.view_model_names) - 1 else ""}
% endfor
)
% endif
% if database_config and api.view_orm_names:
from orm_models import (
% for index, name in enumerate(api.view_orm_names):
    ${name}${"," if index < len(api.view_orm_names) - 1 else ""}
% endfor
)
% endif
% if api.has_path_params:
import path
% endif
% if api.has_query_params:
import query
% endif


api_router = APIRouter()
% for view in views:

<%
    signature_lines = view.signature_lines
    has_signature = view.has_signature
    has_orm = view.has_orm
    orm_class = view.orm_class
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
% if view.method == "get" and view.response_shape == "list" and view.target:
## Filtered list with param inference
% if view.list_path_where:
    stmt = select(${orm_class}).where(${view.list_path_where})
% else:
    stmt = select(${orm_class})
% endif
% for qf in view.query_filters:
    if ${qf.param_name} is not None:
        stmt = stmt.where(${qf.filter_expr})
% endfor
% for pp in view.pagination_params:
% if "limit" in pp.snake_name:
    if ${pp.snake_name} is not None:
        stmt = stmt.limit(${pp.snake_name})
% elif "offset" in pp.snake_name or "skip" in pp.snake_name:
    if ${pp.snake_name} is not None:
        stmt = stmt.offset(${pp.snake_name})
% endif
% endfor
    result = await session.execute(stmt)
    return result.scalars().all()
% elif view.method == "get" and view.response_shape == "list":
    result = await session.execute(select(${orm_class}))
    return result.scalars().all()
% elif view.method == "get" and view.response_shape != "list" and view.target:
## Detail endpoint with field-based path params
    result = await session.execute(select(${orm_class}).where(${view.detail_where}))
    record = result.scalars().first()
    if not record:
        raise HTTPException(status_code=404, detail="${view.response_model} not found")
    return record
% elif view.method == "get":
    result = await session.execute(select(${orm_class}).where(${orm_class}.${view.pk_param} == ${view.pk_param}))
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
    result = await session.execute(select(${orm_class}).where(${orm_class}.${view.pk_param} == ${view.pk_param}))
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
    result = await session.execute(select(${orm_class}).where(${orm_class}.${view.pk_param} == ${view.pk_param}))
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