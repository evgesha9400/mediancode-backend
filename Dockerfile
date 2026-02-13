FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-cache-dir poetry

# Copy dependency files
COPY pyproject.toml poetry.lock README.md ./

# Install dependencies (no-root skips installing the project itself)
RUN poetry config virtualenvs.create false && \
    poetry install --no-root --no-interaction --no-ansi

# Copy source code
COPY src/ ./src/

# Set Python path
ENV PYTHONPATH=/app/src

# Default port
ENV PORT=8080

# Copy Alembic config and entrypoint
COPY alembic.ini entrypoint.sh ./

ENTRYPOINT ["./entrypoint.sh"]
