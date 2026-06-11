#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."

echo "=== alembic current ==="
alembic current || true
echo "=== alembic upgrade head ==="
if alembic upgrade head; then
  echo "=== migrations OK ==="
else
  echo "=== ERROR: alembic upgrade failed — see logs above ==="
  echo "=== starting web server anyway so auth and other routes stay reachable ==="
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:?PORT not set}"
