"""Merge payment transactions and work order schedules branches.

Revision ID: 056_merge_payment_and_schedules
Revises: 055_payment_transactions, 055_work_order_schedules
Create Date: 2026-07-21
"""

revision = '056_merge_payment_and_schedules'
down_revision = ('055_payment_transactions', '055_work_order_schedules')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
