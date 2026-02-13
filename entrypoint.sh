#!/bin/sh
set -e

if [ "$DB_RESET" = "true" ]; then
    echo "DB_RESET=true — dropping and recreating schema..."
    python -c "
from sqlalchemy import create_engine, text
import os
url = os.environ['DATABASE_URL'].replace('+asyncpg', '').replace('postgres://', 'postgresql://')
engine = create_engine(url)
with engine.connect() as conn:
    conn.execute(text('DROP SCHEMA public CASCADE'))
    conn.execute(text('CREATE SCHEMA public'))
    conn.commit()
print('Schema reset complete')
"
fi

echo "Running migrations..."
alembic -c alembic.ini upgrade head

echo "Starting server..."
exec uvicorn api.main:app --host 0.0.0.0 --port "${PORT:-8080}"
