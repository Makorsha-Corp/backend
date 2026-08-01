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

OLD_HEAD = "064_waitlist_signups"
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
        if rows == [NEW_BASELINE]:
            print("adopt_squashed_baseline: already on the squashed baseline -- nothing to do")
            return
        if rows == [OLD_HEAD]:
            conn.execute(text("UPDATE alembic_version SET version_num = :new"),
                         {"new": NEW_BASELINE})
            print(f"adopt_squashed_baseline: {OLD_HEAD} -> {NEW_BASELINE}")
            return

        print(f"adopt_squashed_baseline: unexpected revision(s) {rows!r}. "
              f"This database is neither at {OLD_HEAD} nor {NEW_BASELINE}; "
              "refusing to guess. Bring it to the old head with the pre-squash "
              "migrations, or stamp it manually.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
