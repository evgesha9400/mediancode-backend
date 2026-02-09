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

# Default port (Railway overrides via $PORT)
ENV PORT=8080

# Copy Alembic config (used by Railway releaseCommand)
COPY alembic.ini ./

# Run the application (shell form to expand $PORT)
CMD uvicorn api.main:app --host 0.0.0.0 --port $PORT
