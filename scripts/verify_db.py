#!/usr/bin/env python3
"""Verify local database schema is at Alembic head and critical tables exist."""
from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings  # noqa: E402

HEAD_REVISION = "024_transfer_order_events"

REQUIRED_TABLES = (
    "alembic_version",
    "profiles",
    "workspaces",
    "refresh_tokens",
    "purchase_orders",
    "purchase_order_events",
    "transfer_orders",
    "transfer_order_events",
    "project_events",
    "project_members",
)


def main() -> int:
    engine = create_engine(settings.DATABASE_URL)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    missing = [name for name in REQUIRED_TABLES if name not in tables]
    if missing:
        print(f"FAIL: missing tables: {', '.join(missing)}")
        return 1

    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT version_num FROM alembic_version LIMIT 1")
        ).fetchone()

    if row is None:
        print("FAIL: alembic_version is empty — run `alembic upgrade head`")
        return 1

    current = row[0]
    if current != HEAD_REVISION:
        print(f"FAIL: alembic at {current!r}, expected head {HEAD_REVISION!r}")
        return 1

    print(f"OK: revision {current}, {len(tables)} tables, all required tables present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
