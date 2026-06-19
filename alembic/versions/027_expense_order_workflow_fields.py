"""Add expense order workflow fields and line item allocation columns.

Revision ID: 027_expense_order_workflow_fields
Revises: 026_transfer_order_approvers
"""

import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import (
    add_column_if_not_exists,
    column_exists,
    create_unique_constraint_if_not_exists,
    drop_unique_constraint_if_exists,
)

revision = '027_expense_order_workflow_fields'
down_revision = '026_transfer_order_approvers'
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_column_if_not_exists(
        'expense_orders',
        sa.Column('details_confirmed', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    add_column_if_not_exists(
        'expense_orders',
        sa.Column('items_confirmed', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    add_column_if_not_exists(
        'expense_orders',
        sa.Column('invoice_confirmed', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    add_column_if_not_exists(
        'expense_orders',
        sa.Column('required_approvals', sa.Integer(), nullable=True),
    )
    add_column_if_not_exists(
        'expense_orders',
        sa.Column('completed_by', sa.Integer(), sa.ForeignKey('profiles.id', ondelete='SET NULL'), nullable=True),
    )
    add_column_if_not_exists(
        'expense_orders',
        sa.Column('completed_at', sa.DateTime(), nullable=True),
    )

    for col in ('details_confirmed', 'items_confirmed', 'invoice_confirmed'):
        if column_exists('expense_orders', col):
            op.alter_column('expense_orders', col, server_default=None)

    add_column_if_not_exists(
        'expense_order_items',
        sa.Column('account_id', sa.Integer(), sa.ForeignKey('accounts.id', ondelete='SET NULL'), nullable=True),
    )
    add_column_if_not_exists(
        'expense_order_items',
        sa.Column('cost_center_type', sa.String(50), nullable=True),
    )
    add_column_if_not_exists(
        'expense_order_items',
        sa.Column('cost_center_id', sa.Integer(), nullable=True),
    )

    drop_unique_constraint_if_exists('expense_orders', 'expense_orders_expense_number_key')
    create_unique_constraint_if_not_exists(
        'expense_orders', 'uq_eo_workspace_number', ['workspace_id', 'expense_number']
    )


def downgrade() -> None:
    drop_unique_constraint_if_exists('expense_orders', 'uq_eo_workspace_number')
    from app.db.migration_helpers import unique_constraint_exists

    if not unique_constraint_exists('expense_orders', 'expense_orders_expense_number_key'):
        op.create_unique_constraint('expense_orders_expense_number_key', 'expense_orders', ['expense_number'])

    for col in ('cost_center_id', 'cost_center_type', 'account_id'):
        if column_exists('expense_order_items', col):
            op.drop_column('expense_order_items', col)

    for col in ('completed_at', 'completed_by', 'required_approvals', 'invoice_confirmed', 'items_confirmed', 'details_confirmed'):
        if column_exists('expense_orders', col):
            op.drop_column('expense_orders', col)
