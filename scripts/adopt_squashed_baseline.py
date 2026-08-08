"""One-time adoption of the squashed migration baseline.

Databases migrated with the old chain are stamped `064_waitlist_signups`,
a revision that no longer exists after the squash. Replaying the baseline
on them would fail (tables already exist), so this script rewrites the
stamp to `100_squashed_baseline` instead.

Safe to run repeatedly:
- old (pre-squash) stamp found -> updated to the new baseline id
- stamp is a revision the current alembic scripts still know about (the
  baseline itself, or anything applied on top of it since) -> no-op;
  `alembic upgrade head` takes it from there
- no alembic_version yet -> no-op (fresh DB; `alembic upgrade head` handles it)
- any other stamp -> hard error (schema state unknown; investigate)

Run automatically by scripts/railway_start.sh before `alembic upgrade head`.
"""
import os
import sys

from alembic.config import Config
from alembic.script import ScriptDirectory
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

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _known_revisions() -> set[str]:
    """Every revision id the current codebase's alembic scripts still define."""
    config = Config(os.path.join(BACKEND_ROOT, "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    return {rev.revision for rev in script.walk_revisions()}


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

        # Any stamp the current migration scripts still recognize (the
        # baseline itself, or anything layered on top of it since) needs no
        # rewriting -- `alembic upgrade head` will walk forward from there.
        if set(rows) <= _known_revisions():
            print(f"adopt_squashed_baseline: {sorted(rows)} already known to the "
                  "current migration history -- nothing to do")
            return

        if frozenset(rows) in OLD_HEADS:
            # Collapse to a single row: the pre-squash 063 pair is two rows.
            conn.execute(text("DELETE FROM alembic_version"))
            conn.execute(text("INSERT INTO alembic_version (version_num) VALUES (:new)"),
                         {"new": NEW_BASELINE})
            print(f"adopt_squashed_baseline: {sorted(rows)} -> {NEW_BASELINE}")
            return

        print(f"adopt_squashed_baseline: unexpected revision(s) {rows!r}. "
              f"Expected one of {[sorted(h) for h in OLD_HEADS]} or a revision "
              "known to the current migration history; refusing to guess. "
              "Bring the database to a pre-squash head with the old migrations, "
              "or stamp it manually.",
              file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
