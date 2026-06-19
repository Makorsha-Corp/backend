"""Add transfer_order_events activity log table.

Append-only event log per transfer order.

Revision ID: 024_transfer_order_events
Revises: 023_project_events_members
"""

import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import table_exists

revision = '024_transfer_order_events'
down_revision = '023_project_events_members'
branch_labels = None
depends_on = None


def upgrade() -> None:
    if table_exists('transfer_order_events'):
        return

    op.create_table(
        'transfer_order_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('transfer_order_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('performed_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['transfer_order_id'], ['transfer_orders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['performed_by'], ['profiles.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_transfer_order_events_workspace_id',
        'transfer_order_events',
        ['workspace_id'],
    )
    op.create_index(
        'ix_transfer_order_events_transfer_order_id',
        'transfer_order_events',
        ['transfer_order_id'],
    )


def downgrade() -> None:
    if not table_exists('transfer_order_events'):
        return
    op.drop_index(
        'ix_transfer_order_events_transfer_order_id',
        table_name='transfer_order_events',
    )
    op.drop_index(
        'ix_transfer_order_events_workspace_id',
        table_name='transfer_order_events',
    )
    op.drop_table('transfer_order_events')
