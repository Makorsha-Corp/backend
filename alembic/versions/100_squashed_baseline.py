"""Squashed baseline — full schema as of 064_waitlist_signups (2026-08-01).

Replaces migrations 001..064. The previous chain was not replayable from an
empty database: 001_initial ran `Base.metadata.create_all()` (which builds the
*current* model schema), so later migrations collided with tables that already
existed. This baseline is a sanitized `pg_dump --schema-only` of a database
that had the full chain applied — i.e. exactly what production (Railway) has,
including hand-written indexes the ORM models don't declare (pg_trgm index on
items.name_normalized, composite ix_items_workspace_active).

Existing databases that are stamped `064_waitlist_signups` must adopt this
revision id instead of replaying it — see scripts/adopt_squashed_baseline.py
(run automatically by scripts/railway_start.sh before `alembic upgrade head`).

Revision ID: 100_squashed_baseline
Revises:
Create Date: 2026-08-01
"""
import os

from alembic import op


revision = '100_squashed_baseline'
down_revision = None
branch_labels = None
depends_on = None

_SQL_FILE = os.path.join(os.path.dirname(__file__), '100_squashed_baseline.sql')


def upgrade() -> None:
    with open(_SQL_FILE, encoding='utf-8') as f:
        sql = f.read()
    op.get_bind().exec_driver_sql(sql)


def downgrade() -> None:
    raise NotImplementedError(
        "The squashed baseline cannot be downgraded; drop the database instead."
    )
