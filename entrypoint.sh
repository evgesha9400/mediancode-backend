#!/bin/sh
set -e

if [ "$DB_RESET" = "true" ]; then
    echo "DB_RESET=true — dropping and recreating schema..."
    python -c "
import asyncio, asyncpg, os
async def reset():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'])
    await conn.execute('DROP SCHEMA IF EXISTS public CASCADE')
    await conn.execute('CREATE SCHEMA public')
    await conn.close()
asyncio.run(reset())
print('Schema reset complete.')
"
else
    echo "DB_RESET is not set — skipping schema reset."
fi

echo "Running migrations..."
alembic -c alembic.ini upgrade head
echo "Migrations complete."

echo "Starting server..."
exec uvicorn api.main:app --host 0.0.0.0 --port "${PORT:-8080}"
