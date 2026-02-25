<%doc>
- Parameters:
- api : TemplateApi
</%doc>\
# ${api.spaced_name}

${api.description}

**Version:** ${api.version}
**Author:** ${api.author}

${"##"} Features
% if api.tags:
% for tag in api.tags:

${"###"} ${tag.name}
% if tag.description:

${tag.description}
% endif
% for view in api.views:
% if view.tag == tag.name:
- **${view.method.upper()}** `${view.path}` - ${view.description or view.camel_name}
% endif
% endfor
% endfor
% else:
% for view in api.views:
- **${view.method.upper()}** `${view.path}` - ${view.description or view.camel_name}
% endfor
% endif

${"##"} Prerequisites

- Python 3.13+
- [Poetry](https://python-poetry.org/docs/#installation)
- Docker (optional, for containerized deployment)

${"##"} Installation

```bash
# Install dependencies
make install

# Or manually with Poetry
poetry install
```

${"##"} Running the Application

${"###"} Local Development

```bash
make run-local
```

The API will be available at [http://localhost:8000](http://localhost:8000)

${"###"} Docker Container

```bash
make run-container
```

The API will be available at [http://localhost:8000](http://localhost:8000)

${"##"} API Documentation

Once running, interactive API documentation is available at:

- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **OpenAPI JSON:** [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

${"##"} Project Structure

```
${api.kebab_name}/
├── src/
│   ├── main.py          # FastAPI application entry point
│   ├── views.py         # API route handlers
│   ├── models.py        # Pydantic request/response models
% if api.views and any(v.path_params for v in api.views):
│   ├── path.py          # Path parameter validators
% endif
% if api.views and any(v.query_params for v in api.views):
│   ├── query.py         # Query parameter validators
% endif
│   └── ...
├── pyproject.toml       # Project dependencies
├── Makefile             # Common commands
├── Dockerfile           # Container configuration
└── swagger.py           # OpenAPI schema generator
```

${"##"} Available Commands

| Command | Description |
|---------|-------------|
| `make install` | Install project dependencies |
| `make run-local` | Run the API locally with hot reload |
| `make build` | Build Docker image |
| `make run-container` | Build and run in Docker container |
| `make clean` | Stop and remove Docker container/image |
| `make swagger` | Generate swagger.yaml from the API |
% if api.config.healthcheck:

${"##"} Health Check

A health check endpoint is available at `${api.config.healthcheck}` for container orchestration and monitoring.
% endif

${"##"} Models
% for model in api.models:

${"###"} ${model.name}
% if model.description:

${model.description}
% endif

| Field | Type | Required | Description |
|-------|------|----------|-------------|
% for field in model.fields:
| `${field.name}` | `${field.type}` | ${"No" if field.optional else "Yes"} | ${field.description or "-"} |
% endfor
% endfor

---

*Generated with [Median Code](https://mediancode.ai)*
