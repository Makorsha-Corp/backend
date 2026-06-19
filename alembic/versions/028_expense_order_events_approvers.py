"""Add expense_order_events and expense_order_approvers tables.

Revision ID: 028_expense_order_events_approvers
Revises: 027_expense_order_workflow_fields
"""

import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import table_exists

revision = '028_expense_order_events_approvers'
down_revision = '027_expense_order_workflow_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not table_exists('expense_order_events'):
        op.create_table(
            'expense_order_events',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('workspace_id', sa.Integer(), nullable=False),
            sa.Column('expense_order_id', sa.Integer(), nullable=False),
            sa.Column('event_type', sa.String(50), nullable=False),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('metadata', sa.JSON(), nullable=True),
            sa.Column('performed_by', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['expense_order_id'], ['expense_orders.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['performed_by'], ['profiles.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_expense_order_events_workspace_id', 'expense_order_events', ['workspace_id'])
        op.create_index('ix_expense_order_events_expense_order_id', 'expense_order_events', ['expense_order_id'])

    if not table_exists('expense_order_approvers'):
        op.create_table(
            'expense_order_approvers',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('workspace_id', sa.Integer(), nullable=False),
            sa.Column('expense_order_id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('assigned_by', sa.Integer(), nullable=True),
            sa.Column('assigned_at', sa.DateTime(), nullable=False),
            sa.Column('approved', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('approved_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['expense_order_id'], ['expense_orders.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['user_id'], ['profiles.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['assigned_by'], ['profiles.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('expense_order_id', 'user_id', name='uq_eo_approver_eo_user'),
        )
        op.create_index('ix_expense_order_approvers_workspace_id', 'expense_order_approvers', ['workspace_id'])
        op.create_index('ix_expense_order_approvers_expense_order_id', 'expense_order_approvers', ['expense_order_id'])
        op.create_index('ix_expense_order_approvers_user_id', 'expense_order_approvers', ['user_id'])


def downgrade() -> None:
    if table_exists('expense_order_approvers'):
        op.drop_index('ix_expense_order_approvers_user_id', table_name='expense_order_approvers')
        op.drop_index('ix_expense_order_approvers_expense_order_id', table_name='expense_order_approvers')
        op.drop_index('ix_expense_order_approvers_workspace_id', table_name='expense_order_approvers')
        op.drop_table('expense_order_approvers')

    if table_exists('expense_order_events'):
        op.drop_index('ix_expense_order_events_expense_order_id', table_name='expense_order_events')
        op.drop_index('ix_expense_order_events_workspace_id', table_name='expense_order_events')
        op.drop_table('expense_order_events')
