#!/usr/bin/env python3
"""Find rows linked to a parent row of another workspace (read-only audit).

The pairs are generated from the SQLAlchemy models: every foreign key from a
table with `workspace_id` to another table with `workspace_id`. For each pair
this prints how many rows have a `workspace_id` different from their parent's,
plus up to 5 sample child ids.

Strictly read-only: it issues SELECT statements only, the transaction is marked
read-only on the server (so a write would fail) and it is rolled back at the
end. The database it reads is whatever DATABASE_URL points at; its name is
printed first so that a run can be identified.

Usage:
    python scripts/find_cross_workspace_rows.py
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.db.base import Base
from app.db.session import SessionLocal, engine

SAMPLE_LIMIT = 5


@dataclass(frozen=True)
class Pair:
    child_table: str
    child_column: str
    parent_table: str


def workspace_pairs() -> list[Pair]:
    """Every foreign key between two tables that both have `workspace_id`."""
    tables = Base.metadata.tables
    pairs = [
        Pair(table.name, fk.parent.name, fk.column.table.name)
        for table in tables.values()
        if "workspace_id" in table.c
        for fk in table.foreign_keys
        if "workspace_id" in fk.column.table.c
    ]
    return sorted(pairs, key=lambda p: (p.child_table, p.child_column))


def check_pair(db: Session, pair: Pair) -> tuple[int, list[int]]:
    """Return (rows whose workspace differs from the parent's, sample child ids)."""
    child = Base.metadata.tables[pair.child_table]
    # Aliased so that a self-referencing pair compares two different rows.
    parent = Base.metadata.tables[pair.parent_table].alias("parent")
    fk_column = child.c[pair.child_column]
    target_column = next(iter(fk_column.foreign_keys)).column.name

    joined = child.join(parent, fk_column == parent.c[target_column])
    # IS DISTINCT FROM: a NULL workspace on one side only also counts as different.
    differs = child.c.workspace_id.is_distinct_from(parent.c.workspace_id)

    count = db.execute(select(func.count()).select_from(joined).where(differs)).scalar_one()
    if not count:
        return 0, []
    sample_ids = db.execute(
        select(child.c.id).select_from(joined).where(differs).order_by(child.c.id).limit(SAMPLE_LIMIT)
    ).scalars().all()
    return count, list(sample_ids)


def scan(db: Session) -> list[tuple[Pair, int, list[int]]]:
    """Check every pair on the given session."""
    return [(pair, *check_pair(db, pair)) for pair in workspace_pairs()]


def main() -> int:
    # DEBUG=True turns on SQL echo, which would bury the report.
    engine.echo = False

    db = SessionLocal()
    try:
        # A SELECT, so that the run really issues nothing else.
        db.execute(select(func.set_config("transaction_read_only", "on", True)))
        database_name = db.execute(select(func.current_database())).scalar_one()
        print(f"Database: {database_name}")

        results = scan(db)
    finally:
        db.rollback()
        db.close()

    print(f"Checked {len(results)} pair(s).")
    print()
    for pair, count, sample_ids in results:
        link = f"{pair.child_table}.{pair.child_column} -> {pair.parent_table}"
        line = f"  {count:>8}  {link}"
        if sample_ids:
            line += f"  (sample ids: {', '.join(str(i) for i in sample_ids)})"
        print(line)

    total = sum(count for _, count, _ in results)
    affected = sum(1 for _, count, _ in results if count)
    print()
    print(f"Total: {total} cross-workspace row(s) in {affected} pair(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
