"""Add purchase_order_events activity log table.

Append-only event log per purchase order: created, received, approved,
approval_withdrawn.

Revision ID: 010_po_events
Revises: 009_po_approvers
Create Date: 2026-06-05
"""

import sqlalchemy as sa
from alembic import op

revision = '010_po_events'
down_revision = '009_po_approvers'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'purchase_order_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('purchase_order_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('performed_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['purchase_order_id'], ['purchase_orders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['performed_by'], ['profiles.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_purchase_order_events_workspace_id', 'purchase_order_events', ['workspace_id'])
    op.create_index('ix_purchase_order_events_purchase_order_id', 'purchase_order_events', ['purchase_order_id'])


def downgrade() -> None:
    op.drop_index('ix_purchase_order_events_purchase_order_id', table_name='purchase_order_events')
    op.drop_index('ix_purchase_order_events_workspace_id', table_name='purchase_order_events')
    op.drop_table('purchase_order_events')
