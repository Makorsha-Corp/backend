"""Add purchase_order_approvers table + required_approvals on purchase_orders.

Assignable workspace members approve a PO (approve-only). required_approvals is
the threshold that gates invoice creation / completion.

Revision ID: 009_po_approvers
Revises: 008_po_dates
Create Date: 2026-06-05
"""

import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import add_column_if_not_exists, table_exists

revision = '009_po_approvers'
down_revision = '008_po_dates'
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_column_if_not_exists(
        'purchase_orders', sa.Column('required_approvals', sa.Integer(), nullable=True)
    )

    if table_exists('purchase_order_approvers'):
        return

    op.create_table(
        'purchase_order_approvers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('purchase_order_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('assigned_by', sa.Integer(), nullable=True),
        sa.Column('assigned_at', sa.DateTime(), nullable=False),
        sa.Column('approved', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['purchase_order_id'], ['purchase_orders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['assigned_by'], ['profiles.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('purchase_order_id', 'user_id', name='uq_po_approver_po_user'),
    )
    op.create_index('ix_purchase_order_approvers_workspace_id', 'purchase_order_approvers', ['workspace_id'])
    op.create_index('ix_purchase_order_approvers_purchase_order_id', 'purchase_order_approvers', ['purchase_order_id'])
    op.create_index('ix_purchase_order_approvers_user_id', 'purchase_order_approvers', ['user_id'])


def downgrade() -> None:
    from app.db.migration_helpers import drop_column_if_exists

    if table_exists('purchase_order_approvers'):
        op.drop_index('ix_purchase_order_approvers_user_id', table_name='purchase_order_approvers')
        op.drop_index('ix_purchase_order_approvers_purchase_order_id', table_name='purchase_order_approvers')
        op.drop_index('ix_purchase_order_approvers_workspace_id', table_name='purchase_order_approvers')
        op.drop_table('purchase_order_approvers')
    drop_column_if_exists('purchase_orders', 'required_approvals')
