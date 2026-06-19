#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."

echo "=== alembic current ==="
alembic current
echo "=== alembic upgrade head ==="
alembic upgrade head
echo "=== migrations OK ==="

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:?PORT not set}"
