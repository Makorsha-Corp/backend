"""po_receive_events and po_receive_event_items tables

Revision ID: 038_po_receive_events
Revises: 037_purchase_order_void
Create Date: 2026-06-28
"""
from alembic import op
import sqlalchemy as sa

revision = '038_po_receive_events'
down_revision = '037_purchase_order_void'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'po_receive_events',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('purchase_order_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(20), nullable=False),  # 'receive' | 'correction'
        sa.Column('rcc', sa.String(100), nullable=True),
        sa.Column('received_by', sa.String(200), nullable=True),
        sa.Column('correction_note', sa.Text(), nullable=True),
        sa.Column('performed_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['purchase_order_id'], ['purchase_orders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['performed_by'], ['profiles.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_po_receive_events_po_id', 'po_receive_events', ['purchase_order_id'])
    op.create_index('ix_po_receive_events_workspace_id', 'po_receive_events', ['workspace_id'])

    op.create_table(
        'po_receive_event_items',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('receive_event_id', sa.Integer(), nullable=False),
        sa.Column('po_item_id', sa.Integer(), nullable=False),
        sa.Column('quantity_delta', sa.Numeric(15, 4), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['receive_event_id'], ['po_receive_events.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['po_item_id'], ['purchase_order_items.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_po_receive_event_items_event_id', 'po_receive_event_items', ['receive_event_id'])


def downgrade():
    op.drop_table('po_receive_event_items')
    op.drop_table('po_receive_events')
