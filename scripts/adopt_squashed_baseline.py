"""One-time adoption of the squashed migration baseline.

Databases migrated with the old chain are stamped `064_waitlist_signups`,
a revision that no longer exists after the squash. Replaying the baseline
on them would fail (tables already exist), so this script rewrites the
stamp to `100_squashed_baseline` instead.

Safe to run repeatedly:
- old stamp found        -> updated to the new baseline id
- new stamp already set  -> no-op
- no alembic_version yet -> no-op (fresh DB; `alembic upgrade head` handles it)
- any other stamp        -> hard error (schema state unknown; investigate)

Run automatically by scripts/railway_start.sh before `alembic upgrade head`.
"""
import sys

from sqlalchemy import create_engine, text

from app.core.config import settings

# Every pre-squash head that exists on a real database:
#   064_merge_...  - what Railway and teammates' DBs stopped at
#   064_waitlist_signups - only ever existed on the author's machine (the
#                          migration file was never committed)
#   the 063 pair   - a DB that never ran the merge revision
# All of them describe the same schema as the baseline except possibly the
# waitlist_signups table, which 101_waitlist_signups creates afterwards.
OLD_HEADS = {
    frozenset({"064_merge_sales_delivery_and_work_order_item_soft_delete"}),
    frozenset({"064_waitlist_signups"}),
    frozenset({"063_merge_sales_delivery_and_work_order_template",
               "063_work_order_item_soft_delete"}),
}
NEW_BASELINE = "100_squashed_baseline"


def main() -> None:
    engine = create_engine(settings.DATABASE_URL)
    with engine.begin() as conn:
        exists = conn.execute(text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'alembic_version'"
        )).scalar()
        if not exists:
            print("adopt_squashed_baseline: no alembic_version table (fresh DB) -- nothing to do")
            return

        rows = [r[0] for r in conn.execute(text("SELECT version_num FROM alembic_version"))]
        if not rows:
            print("adopt_squashed_baseline: alembic_version empty -- nothing to do")
            return
        if set(rows) <= {NEW_BASELINE, "101_waitlist_signups"}:
            print("adopt_squashed_baseline: already on/after the squashed baseline -- nothing to do")
            return
        if frozenset(rows) in OLD_HEADS:
            # Collapse to a single row: the pre-squash 063 pair is two rows.
            conn.execute(text("DELETE FROM alembic_version"))
            conn.execute(text("INSERT INTO alembic_version (version_num) VALUES (:new)"),
                         {"new": NEW_BASELINE})
            print(f"adopt_squashed_baseline: {sorted(rows)} -> {NEW_BASELINE}")
            return

        print(f"adopt_squashed_baseline: unexpected revision(s) {rows!r}. "
              f"Expected one of {[sorted(h) for h in OLD_HEADS]} or "
              f"{NEW_BASELINE}; refusing to guess. Bring the database to a "
              "pre-squash head with the old migrations, or stamp it manually.",
              file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
