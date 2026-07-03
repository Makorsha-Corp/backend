"""Move expense order cost-center allocation from line items to the order header.

Revision ID: 045_expense_order_order_level_allocation
Revises: 044_expense_order_simplify_workflow
"""

import sqlalchemy as sa

from app.db.migration_helpers import add_column_if_not_exists, drop_column_if_exists

revision = '045_expense_order_order_level_allocation'
down_revision = '044_expense_order_simplify_workflow'
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_column_if_not_exists(
        'expense_orders',
        sa.Column('cost_center_id', sa.Integer(), nullable=True),
    )
    add_column_if_not_exists(
        'order_templates',
        sa.Column('cost_center_id', sa.Integer(), nullable=True),
    )
    drop_column_if_exists('expense_order_items', 'cost_center_type')
    drop_column_if_exists('expense_order_items', 'cost_center_id')


def downgrade() -> None:
    add_column_if_not_exists(
        'expense_order_items',
        sa.Column('cost_center_type', sa.String(50), nullable=True),
    )
    add_column_if_not_exists(
        'expense_order_items',
        sa.Column('cost_center_id', sa.Integer(), nullable=True),
    )
    drop_column_if_exists('order_templates', 'cost_center_id')
    drop_column_if_exists('expense_orders', 'cost_center_id')
