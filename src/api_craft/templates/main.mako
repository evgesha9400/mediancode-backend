<%doc>
- Template Parameters:
- api: TemplateApi
</%doc>\
% if api.database_config:
from contextlib import asynccontextmanager

% endif
from fastapi import FastAPI

% if api.config.healthcheck:
from starlette.responses import Response
% endif

% if api.database_config:
from database import engine
% endif

from views import api_router
% if api.database_config:


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()

% endif

app = FastAPI(
    title="${api.spaced_name}",
    description="${api.description}",
    version="${api.version}",
% if api.tags:
    openapi_tags=[
% for tag in api.tags:
        {"name": "${tag.name}"${ ', "description": "' + tag.description + '"' if tag.description else ''}},
% endfor
    ],
% endif
% if api.database_config:
    lifespan=lifespan,
% endif
)
app.include_router(api_router)


% if api.config.healthcheck:
# Health check for ECS
@app.get(path="${api.config.healthcheck}", include_in_schema=False)
async def healthcheck():
    return Response(content="OK", status_code=200)
% endif