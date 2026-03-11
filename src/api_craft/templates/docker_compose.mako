<%doc>
- Template Parameters:
- api: TemplateAPI
</%doc>\
services:
  db:
    image: postgres:18
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: ${api.snake_name}
    ports:
      - "${"${"}DB_PORT:-${api.database_config.db_port}}:5432"
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
      - "${"${"}APP_PORT:-${api.app_port}}:80"
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:postgres@db:5432/${api.snake_name}
    depends_on:
      db:
        condition: service_healthy

volumes:
  pgdata:
