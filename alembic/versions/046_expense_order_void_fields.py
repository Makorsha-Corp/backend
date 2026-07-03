"""Add void fields to expense orders, mirroring purchase orders.

Revision ID: 046_expense_order_void_fields
Revises: 045_expense_order_order_level_allocation
"""

import sqlalchemy as sa

from app.db.migration_helpers import add_column_if_not_exists, drop_column_if_exists

revision = '046_expense_order_void_fields'
down_revision = '045_expense_order_order_level_allocation'
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_column_if_not_exists(
        'expense_orders',
        sa.Column('voided', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    add_column_if_not_exists(
        'expense_orders',
        sa.Column('void_note', sa.Text(), nullable=True),
    )
    add_column_if_not_exists(
        'expense_orders',
        sa.Column('voided_at', sa.DateTime(), nullable=True),
    )
    add_column_if_not_exists(
        'expense_orders',
        sa.Column('voided_by', sa.Integer(), sa.ForeignKey('profiles.id', ondelete='SET NULL'), nullable=True),
    )


def downgrade() -> None:
    drop_column_if_exists('expense_orders', 'voided_by')
    drop_column_if_exists('expense_orders', 'voided_at')
    drop_column_if_exists('expense_orders', 'void_note')
    drop_column_if_exists('expense_orders', 'voided')
