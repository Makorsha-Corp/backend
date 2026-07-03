"""Simplify expense order workflow: drop status/workflow FKs and confirm-flag booleans.

Revision ID: 044_expense_order_simplify_workflow
Revises: 043_po_paid_column_revert_complete
"""

import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import column_exists, drop_column_if_exists

revision = '044_expense_order_simplify_workflow'
down_revision = '043_po_paid_column_revert_complete'
branch_labels = None
depends_on = None

_DROP_COLUMNS = [
    'current_status_id',   # FK -> statuses.id (dead: never seeded/updated for expense orders)
    'order_workflow_id',   # FK -> order_workflows.id (dead: no workflow ever seeded for this type)
    'details_confirmed',
    'items_confirmed',
    'invoice_confirmed',
]


def upgrade() -> None:
    for col in _DROP_COLUMNS:
        drop_column_if_exists('expense_orders', col)


def downgrade() -> None:
    if not column_exists('expense_orders', 'current_status_id'):
        op.add_column(
            'expense_orders',
            sa.Column(
                'current_status_id', sa.Integer(),
                sa.ForeignKey('statuses.id', ondelete='RESTRICT'),
                nullable=True,  # was NOT NULL; relaxed since there is no data to backfill
            ),
        )
    if not column_exists('expense_orders', 'order_workflow_id'):
        op.add_column(
            'expense_orders',
            sa.Column(
                'order_workflow_id', sa.Integer(),
                sa.ForeignKey('order_workflows.id', ondelete='RESTRICT'),
                nullable=True,
            ),
        )
    for col in ('details_confirmed', 'items_confirmed', 'invoice_confirmed'):
        if not column_exists('expense_orders', col):
            op.add_column(
                'expense_orders',
                sa.Column(col, sa.Boolean(), nullable=False, server_default=sa.false()),
            )
