"""Add recurrence start/end dates on work order templates.

Revision ID: 062_work_order_template_recurrence_range
Revises: 061_drop_work_order_schedules
"""

import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import column_exists

revision = '062_work_order_template_recurrence_range'
down_revision = '061_drop_work_order_schedules'
branch_labels = None
depends_on = None


def upgrade() -> None:
    for col in ('recurrence_start_date', 'recurrence_end_date'):
        if not column_exists('work_order_templates', col):
            op.add_column('work_order_templates', sa.Column(col, sa.Date(), nullable=True))


def downgrade() -> None:
    for col in ('recurrence_end_date', 'recurrence_start_date'):
        if column_exists('work_order_templates', col):
            op.drop_column('work_order_templates', col)
