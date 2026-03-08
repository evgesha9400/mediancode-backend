# Database Generation Design

## Overview

Extend api_craft to generate database-backed FastAPI projects. When enabled, the generator produces SQLAlchemy ORM models, Alembic migrations, Docker Compose for local PostgreSQL, and views that query the database instead of returning hardcoded placeholders.

## Decisions

- **ORM:** SQLAlchemy 2.0 async, database-agnostic, PostgreSQL default
- **Migrations:** Alembic only (auto-generate from ORM models)
- **Relationships:** Foreign keys (1-to-many) in v1, many-to-many deferred
- **Entity detection:** Models with a `pk: true` field become database tables
- **Backward compatibility:** `database.enabled: false` (default) produces identical output to today
- **CDK/Infrastructure:** Not in scope. Groundwork laid via `DATABASE_URL` env var pattern. Future phases will add infrastructure manifests and CDK generation.

## Input Spec Changes

### `InputField` — new fields

```python
class InputField(BaseModel):
    # ... existing fields ...
    pk: bool = False                           # marks primary key
    fk: str | None = None                      # target entity name for foreign key
    on_delete: OnDeleteAction = "restrict"     # cascade | restrict | set_null
```

### `InputApiConfig` — new database section

```python
class InputDatabaseConfig(BaseModel):
    enabled: bool = False
    seed_data: bool = True

class InputApiConfig(BaseModel):
    # ... existing fields ...
    database: InputDatabaseConfig = InputDatabaseConfig()
```

### Example YAML

```yaml
config:
  healthcheck: /healthcheck
  database:
    enabled: true
    seed_data: true

objects:
  - name: Order
    fields:
      - name: id
        type: int
        pk: true
      - name: status
        type: str

  - name: OrderItem
    fields:
      - name: id
        type: int
        pk: true
      - name: order_id
        type: int
        fk: Order
        on_delete: cascade
      - name: product_name
        type: str
      - name: quantity
        type: int

  - name: CreateOrderRequest
    fields:
      - name: status
        type: str
```

## Template Model Changes

### New models

```python
class TemplateORMField(BaseModel):
    name: str
    python_type: str          # e.g. "int", "str | None"
    column_type: str          # e.g. "Integer", "String(100)", "Text"
    primary_key: bool = False
    nullable: bool = False
    autoincrement: bool = False
    foreign_key: str | None = None     # e.g. "orders.id"
    on_delete: str | None = None       # "CASCADE", "RESTRICT", "SET NULL"

class TemplateORMModel(BaseModel):
    class_name: str           # "ItemRecord"
    table_name: str           # "items"
    source_model: str         # "Item"
    fields: list[TemplateORMField]

class TemplateDatabaseConfig(BaseModel):
    enabled: bool
    seed_data: bool
    default_url: str          # default DATABASE_URL for docker-compose
```

### Existing model additions

```python
class TemplateField(BaseModel):
    # ... existing ...
    pk: bool = False

class TemplateAPI(BaseModel):
    # ... existing ...
    orm_models: list[TemplateORMModel] = []
    database_config: TemplateDatabaseConfig | None = None
```

## Type Mapping (Python → SQLAlchemy)

| Python Type | SQLAlchemy Column | Notes |
|---|---|---|
| `str` (with max_length) | `String(N)` | N from max_length validator |
| `str` (no max_length) | `Text` | |
| `int` | `Integer` | |
| `float` | `Float` | |
| `bool` | `Boolean` | |
| `datetime` | `DateTime` | |
| `date` | `Date` | |
| `time` | `Time` | |
| `uuid` | `Uuid` | SQLAlchemy 2.0 native, DB-agnostic |
| `Decimal` | `Numeric` | Preserves precision |
| `EmailStr` | `String(320)` | RFC 5321 max |
| `HttpUrl` | `Text` | No practical max |
| `List[...]`, `Dict[...]` | skipped | Relationships — future feature |

## Generated Files (when database.enabled: true)

### New files

| File | Purpose |
|---|---|
| `src/database.py` | Async engine, session factory, `DATABASE_URL` from env |
| `src/orm_models.py` | SQLAlchemy table models for entities with PK fields |
| `src/seed.py` | Idempotent seed using placeholder generator data |
| `docker-compose.yml` | PostgreSQL 18 + API service |
| `alembic.ini` | Alembic config, reads `DATABASE_URL` env var |
| `migrations/env.py` | Alembic env, imports `orm_models.Base.metadata` |
| `migrations/versions/0001_initial.py` | Initial migration matching ORM models |

### Modified files

| File | Change |
|---|---|
| `src/views.py` | DB queries via `Depends(get_session)` instead of hardcoded returns |
| `src/main.py` | Lifespan context manager with DB init + seed |
| `pyproject.toml` | Adds sqlalchemy[asyncio], asyncpg, alembic |
| `Makefile` | Adds db-up, db-upgrade, db-seed, db-reset, db-downgrade |
| `Dockerfile` | Copies migrations/, runs alembic upgrade head before uvicorn |
| `README.md` | Database setup documentation section |

## Generated Code Examples

### `src/database.py`

```python
import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/{snake_name}"
)

engine = create_async_engine(DATABASE_URL)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
```

### `src/orm_models.py`

```python
from sqlalchemy import Integer, String, Float, Text, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class OrderRecord(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(Text)

class OrderItemRecord(Base):
    __tablename__ = "order_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id", ondelete="CASCADE"))
    product_name: Mapped[str] = mapped_column(Text)
    quantity: Mapped[int] = mapped_column(Integer)
```

### `src/views.py` (database-enabled)

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_session
from models import Order, CreateOrderRequest
from orm_models import OrderRecord

api_router = APIRouter()

@api_router.get(path="/orders/{order_id}", response_model=Order, tags=["Orders"])
async def get_order(order_id: path.OrderId, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(OrderRecord).where(OrderRecord.id == order_id))
    record = result.scalars().first()
    if not record:
        raise HTTPException(status_code=404, detail="Order not found")
    return record

@api_router.post(path="/orders", response_model=Order, tags=["Orders"])
async def create_order(request: CreateOrderRequest, session: AsyncSession = Depends(get_session)):
    record = OrderRecord(**request.model_dump())
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record

@api_router.put(path="/orders/{order_id}", response_model=Order, tags=["Orders"])
async def update_order(order_id: path.OrderId, request: UpdateOrderRequest, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(OrderRecord).where(OrderRecord.id == order_id))
    record = result.scalars().first()
    if not record:
        raise HTTPException(status_code=404, detail="Order not found")
    for key, value in request.model_dump(exclude_unset=True).items():
        setattr(record, key, value)
    await session.commit()
    await session.refresh(record)
    return record

@api_router.delete(path="/orders/{order_id}", tags=["Orders"])
async def delete_order(order_id: path.OrderId, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(OrderRecord).where(OrderRecord.id == order_id))
    record = result.scalars().first()
    if not record:
        raise HTTPException(status_code=404, detail="Order not found")
    await session.delete(record)
    await session.commit()
    return record
```

### `src/main.py` (database-enabled)

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from database import engine, async_session
from orm_models import Base
from seed import seed_database
from views import api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_session() as session:
        await seed_database(session)
    yield
    await engine.dispose()

app = FastAPI(
    title="Orders Api",
    description="...",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(api_router)
```

### `docker-compose.yml`

```yaml
services:
  db:
    image: postgres:18
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: {snake_name}
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 3s
      retries: 5

  api:
    build: .
    ports:
      - "8000:80"
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:postgres@db:5432/{snake_name}
    depends_on:
      db:
        condition: service_healthy

volumes:
  pgdata:
```

### `Makefile` additions

```makefile
db-up:
	@docker compose up db -d
	@echo "Waiting for PostgreSQL..."
	@until docker compose exec db pg_isready -U postgres > /dev/null 2>&1; do sleep 1; done
	@echo "PostgreSQL is ready."

db-down:
	@docker compose down

db-upgrade: db-up
	@PYTHONPATH=src poetry run alembic upgrade head

db-downgrade:
	@PYTHONPATH=src poetry run alembic downgrade -1

db-seed: db-upgrade
	@PYTHONPATH=src poetry run python -c "import asyncio; from seed import seed_database; from database import async_session; asyncio.run(seed_database(async_session()))"

db-reset:
	@docker compose down -v
	@$(MAKE) db-upgrade
	@$(MAKE) db-seed

run-local: db-up
	@PYTHONPATH=src DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/$(PROJECT_NAME) poetry run uvicorn main:app --reload --port 8000

run-stack:
	@docker compose up --build
```

### Dependencies

```toml
# Added to pyproject.toml when database.enabled
"sqlalchemy[asyncio] (>=2.0.0,<3.0.0)"
"asyncpg (>=0.31.0,<1.0.0)"
"alembic (>=1.18.0,<2.0.0)"
```

## Pipeline Changes

### Transform (`transformers.py`)

New function `transform_orm_models()`:
- Filters InputModels to those with a `pk: true` field
- Maps each field's Python type to SQLAlchemy column type via TYPE_MAP
- Resolves FK references to `{target_table}.{pk_column}`
- Skips `List[...]`, `Dict[...]`, model reference fields
- Sets `autoincrement=True` for `int` PKs, `False` for `uuid` PKs
- ORM class named `{Model}Record`, table named as snake_case plural

Called from `transform_api()` only when `database.enabled` is `True`.

### Extract (`extractors.py`)

New functions:
- `collect_orm_imports()` — scans ORM fields for unique column types
- `collect_database_dependencies()` — returns SQLAlchemy/asyncpg/Alembic dep strings

### Render (`renderers.py`)

Six new render functions:
- `render_orm_models(orm_models, imports, template)`
- `render_database(api, template)`
- `render_seed(orm_models, placeholder_data, template)`
- `render_docker_compose(api, template)`
- `render_alembic_ini(api, template)`
- `render_alembic_env(api, template)`

### Write (`main.py`)

`write_files()` extended to:
- Create `migrations/versions/` directory
- Write `alembic.ini` to project root
- Write `env.py` to `migrations/`
- Write initial migration to `migrations/versions/`
- Write `docker-compose.yml` to project root

### Validation (`validators.py`)

New `validate_foreign_keys()`:
- Verifies FK target entity exists
- Verifies FK target entity has a PK field
- Called from `InputAPI._validate_references()`

## View-to-Entity Mapping

Endpoint's response model is looked up: if the model has a PK field, it has a corresponding ORM record. The HTTP method determines the query pattern:

| Method | Query Pattern |
|---|---|
| GET + path param | `select().where(pk == param)` + 404 |
| GET (list) | `select()` with optional query param filters |
| POST | `Model(**request.model_dump())`, add, commit, refresh |
| PUT | select by pk, update from `request.model_dump(exclude_unset=True)`, commit |
| DELETE | select by pk, delete, commit |

Endpoints whose response model has no PK retain hardcoded placeholder behavior.

## Future Work (not in scope)

- Many-to-many relationships (association tables)
- Auto-derived request/response shapes from entity definition
- CDK generation (service + infrastructure stacks)
- Infrastructure manifests for multi-service orchestration
- Migration tool selection (DBmate, etc.)
- Shared model library generation
