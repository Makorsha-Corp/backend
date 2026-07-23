"""Rename work_orders.start_date to planned_date.

Revision ID: 058_work_order_planned_date
Revises: 057_work_order_template_generation_mode
Create Date: 2026-07-23
"""

from alembic import op

revision = '058_work_order_planned_date'
down_revision = '057_work_order_template_generation_mode'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column('work_orders', 'start_date', new_column_name='planned_date')


def downgrade() -> None:
    op.alter_column('work_orders', 'planned_date', new_column_name='start_date')
