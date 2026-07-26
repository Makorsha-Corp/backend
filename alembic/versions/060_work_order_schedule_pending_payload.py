"""Add pending_entry_payload to work_order_schedules for ad-hoc staged footer entries.

Revision ID: 060_work_order_schedule_pending_payload
Revises: 059_drop_machine_next_maintenance
"""

import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import column_exists

revision = '060_work_order_schedule_pending_payload'
down_revision = '059_drop_machine_next_maintenance'
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not column_exists('work_order_schedules', 'pending_entry_payload'):
        op.add_column(
            'work_order_schedules',
            sa.Column('pending_entry_payload', sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    if column_exists('work_order_schedules', 'pending_entry_payload'):
        op.drop_column('work_order_schedules', 'pending_entry_payload')
