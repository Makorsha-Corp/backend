"""Ensure the waitlist_signups table exists.

The squashed baseline (100) was dumped from a database that already had this
table, but the migration that originally created it was never committed — so
every *other* database (Railway, teammates' local DBs) stopped at the
pre-squash head without it. Those databases adopt the baseline stamp via
scripts/adopt_squashed_baseline.py and then run this revision to close the gap.

Guarded so it is a no-op where the baseline already created the table.

Revision ID: 101_waitlist_signups
Revises: 100_squashed_baseline
Create Date: 2026-08-01
"""
import sqlalchemy as sa
from alembic import op


revision = '101_waitlist_signups'
down_revision = '100_squashed_baseline'
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if _table_exists('waitlist_signups'):
        return

    op.create_table(
        'waitlist_signups',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('email', sa.String(length=320), nullable=False),
        sa.Column('wants_product_updates', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('source', sa.String(length=64), nullable=True),
        sa.Column('ip_hash', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint('email', name='waitlist_signups_email_key'),
    )
    op.create_index('ix_waitlist_signups_email', 'waitlist_signups', ['email'], unique=True)
    op.create_index('ix_waitlist_signups_id', 'waitlist_signups', ['id'])


def downgrade() -> None:
    op.drop_index('ix_waitlist_signups_id', table_name='waitlist_signups')
    op.drop_index('ix_waitlist_signups_email', table_name='waitlist_signups')
    op.drop_table('waitlist_signups')
