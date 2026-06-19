"""Add transfer_order_approvers table.

Revision ID: 026_transfer_order_approvers
Revises: 025_transfer_order_workflow_fields
"""

import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import table_exists

revision = '026_transfer_order_approvers'
down_revision = '025_transfer_order_workflow_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    if table_exists('transfer_order_approvers'):
        return

    op.create_table(
        'transfer_order_approvers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('transfer_order_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('assigned_by', sa.Integer(), nullable=True),
        sa.Column('assigned_at', sa.DateTime(), nullable=False),
        sa.Column('approved', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['transfer_order_id'], ['transfer_orders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['assigned_by'], ['profiles.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('transfer_order_id', 'user_id', name='uq_to_approver_to_user'),
    )
    op.create_index(
        'ix_transfer_order_approvers_workspace_id',
        'transfer_order_approvers',
        ['workspace_id'],
    )
    op.create_index(
        'ix_transfer_order_approvers_transfer_order_id',
        'transfer_order_approvers',
        ['transfer_order_id'],
    )
    op.create_index(
        'ix_transfer_order_approvers_user_id',
        'transfer_order_approvers',
        ['user_id'],
    )


def downgrade() -> None:
    if not table_exists('transfer_order_approvers'):
        return
    op.drop_index('ix_transfer_order_approvers_user_id', table_name='transfer_order_approvers')
    op.drop_index('ix_transfer_order_approvers_transfer_order_id', table_name='transfer_order_approvers')
    op.drop_index('ix_transfer_order_approvers_workspace_id', table_name='transfer_order_approvers')
    op.drop_table('transfer_order_approvers')
