"""Add work_order_items.action_type + replaced_item_id — lets a part line declare
whether it's being installed, replacing an existing part (into the damaged bucket),
or borrowed (returned to source at completion) instead of just plain-consumed.

Revision ID: 052_work_order_item_action_type
Revises: 051_work_order_uses_inventory
"""

import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import column_exists

revision = '052_work_order_item_action_type'
down_revision = '051_work_order_uses_inventory'
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not column_exists('work_order_items', 'action_type'):
        op.add_column(
            'work_order_items',
            sa.Column('action_type', sa.String(20), nullable=False, server_default='CONSUME'),
        )
    if not column_exists('work_order_items', 'replaced_item_id'):
        op.add_column(
            'work_order_items',
            sa.Column('replaced_item_id', sa.Integer(), sa.ForeignKey('items.id'), nullable=True),
        )
        op.create_index(
            'ix_work_order_items_replaced_item_id', 'work_order_items', ['replaced_item_id']
        )


def downgrade() -> None:
    if column_exists('work_order_items', 'replaced_item_id'):
        op.drop_index('ix_work_order_items_replaced_item_id', table_name='work_order_items')
        op.drop_column('work_order_items', 'replaced_item_id')
    if column_exists('work_order_items', 'action_type'):
        op.drop_column('work_order_items', 'action_type')
