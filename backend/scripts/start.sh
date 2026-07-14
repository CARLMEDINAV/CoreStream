#!/bin/bash
set -e

echo "CoreStream — Starting up..."
echo "Environment: ${ENVIRONMENT:-development}"

# Esperar a que PostgreSQL esté listo (máx 30 segundos)
echo "Waiting for database..."
max_retries=10
count=0
until python -c "
import asyncio, asyncpg, os, sys
async def check():
    url = os.getenv('DATABASE_URL', '')
    url = url.replace('postgresql+asyncpg://', 'postgresql://')
    url = url.replace('postgres://', 'postgresql://')
    try:
        conn = await asyncpg.connect(url)
        await conn.close()
        print('Database ready')
    except Exception as e:
        print(f'Database not ready: {e}')
        sys.exit(1)
asyncio.run(check())
" 2>/dev/null; do
    count=$((count + 1))
    if [ $count -ge $max_retries ]; then
        echo "Database not available after ${max_retries} retries — starting anyway"
        break
    fi
    echo "Retry $count/$max_retries..."
    sleep 3
done

# Correr migraciones
echo "Running database migrations..."
alembic upgrade head || echo "Warning: migrations failed, continuing..."

# Iniciar servidor
echo "Starting uvicorn on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
