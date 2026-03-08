<%doc>
- Parameters:
- api : TemplateApi
</%doc>\
# Use an official lightweight Python image.
# https://hub.docker.com/_/python
FROM python:3.13-slim
LABEL org.opencontainers.image.title="${api.snake_name}"

# Set the working directory in the container
WORKDIR /app

# Install Poetry
RUN pip install --no-cache-dir poetry

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install dependencies (no virtualenv in container)
RUN poetry config virtualenvs.create false && \
    poetry install --only main --no-interaction --no-ansi

# Copy application code
COPY src/ .
% if api.database_config:

# Copy migration files
COPY migrations/ ./migrations/
COPY alembic.ini .
% endif

# Specify the command to run on container start
% if api.database_config:
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 80"]
% else:
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
% endif