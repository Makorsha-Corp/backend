#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."

echo "=== alembic upgrade head ==="
if alembic upgrade head; then
  echo "=== migrations OK ==="
else
  echo "=== WARNING: alembic failed — starting web anyway ==="
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:?PORT not set}"
