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

The API will be available at [http://localhost:${api.app_port}](http://localhost:${api.app_port})

${"###"} Docker Container

```bash
make run-container
```

The API will be available at [http://localhost:${api.app_port}](http://localhost:${api.app_port})
% if api.database_config:

${"##"} Database

This project uses PostgreSQL with async SQLAlchemy and Alembic for migrations.

${"###"} Setup

```bash
# Start PostgreSQL (Docker)
make db-up

# Create initial migration
make db-init

# Apply migrations
make db-upgrade

# Reset database (drop and recreate)
make db-reset
```

${"###"} Port Configuration

Default ports are configured in `.env`:

${"```"}
DB_PORT=${api.database_config.db_port}
APP_PORT=${api.app_port}
${"```"}

Change these values to avoid conflicts with other services.

${"###"} Run Full Stack (Docker Compose)

```bash
make run-stack
```
% endif

${"##"} API Documentation

Once running, interactive API documentation is available at:

- **Swagger UI:** [http://localhost:${api.app_port}/docs](http://localhost:${api.app_port}/docs)
- **ReDoc:** [http://localhost:${api.app_port}/redoc](http://localhost:${api.app_port}/redoc)
- **OpenAPI JSON:** [http://localhost:${api.app_port}/openapi.json](http://localhost:${api.app_port}/openapi.json)

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
% if api.database_config:
│   ├── orm_models.py    # SQLAlchemy ORM models
│   ├── database.py      # Database engine and session
% endif
│   └── ...
├── .env                 # Port configuration
├── pyproject.toml       # Project dependencies
├── Makefile             # Common commands
├── Dockerfile           # Container configuration
% if api.database_config:
├── docker-compose.yml   # Docker Compose for DB + API
├── alembic.ini          # Alembic configuration
├── migrations/          # Alembic migration files
% endif
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
% if api.database_config:
| `make db-up` | Start PostgreSQL container |
| `make db-down` | Stop Docker Compose services |
| `make db-init` | Create initial Alembic migration |
| `make db-upgrade` | Apply pending migrations |
| `make db-downgrade` | Rollback last migration |
| `make db-reset` | Reset database (drop + migrate) |
| `make run-stack` | Run full stack via Docker Compose |
% endif
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