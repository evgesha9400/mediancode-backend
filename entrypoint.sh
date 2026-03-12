#!/bin/sh
set -e

if [ "$DB_RESET" = "true" ]; then
    echo "DB_RESET=true — dropping and recreating schema..."
    python -c "
import asyncio, asyncpg, os
async def reset():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'])
    await conn.execute('DROP SCHEMA public CASCADE')
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

if [ "$DB_RESET" = "true" ] && [ -f seed-shop-api.sql ]; then
    echo "Seeding Shop API data..."
    python -c "
import asyncio, asyncpg, os
async def seed():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'])
    with open('seed-shop-api.sql') as f:
        sql = f.read()
    await conn.execute(sql)
    await conn.close()
asyncio.run(seed())
print('Seed complete.')
"
fi

echo "Starting server..."
exec uvicorn api.main:app --host 0.0.0.0 --port "${PORT:-8080}"
