#!/bin/sh
set -e

echo "=== Running database migrations ==="
# Retry loop — DB might not be ready yet despite depends_on
for i in $(seq 1 10); do
    echo "--- Migration attempt $i ---"
    if alembic upgrade head 2>&1; then
        echo "Migrations applied successfully."
        break
    fi
    echo "Migration attempt $i failed. Waiting for DB..."
    sleep 3
done

echo "=== Starting uvicorn ==="
exec uvicorn app.main:app --host 0.0.0.0 --port 8012
