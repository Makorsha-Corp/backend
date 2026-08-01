#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."

# Must run before any alembic command: rewrites the pre-squash stamp
# (064_waitlist_signups) to the squashed baseline id. `alembic current`
# would otherwise error on the unknown revision.
echo "=== adopt squashed baseline (no-op unless pre-squash stamp) ==="
python -m scripts.adopt_squashed_baseline
echo "=== alembic current ==="
alembic current
echo "=== alembic upgrade head ==="
alembic upgrade head
echo "=== migrations OK ==="

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:?PORT not set}"
