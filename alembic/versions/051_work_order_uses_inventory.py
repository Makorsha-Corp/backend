"""Add work_orders.uses_inventory — decided at creation time (the Maintenance
wizard's "parts?" question). When False, items can never be added to the order.

Revision ID: 051_work_order_uses_inventory
Revises: 050_work_order_types
"""

import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import column_exists

revision = '051_work_order_uses_inventory'
down_revision = '050_work_order_types'
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not column_exists('work_orders', 'uses_inventory'):
        op.add_column(
            'work_orders',
            sa.Column('uses_inventory', sa.Boolean(), nullable=False, server_default=sa.true()),
        )


def downgrade() -> None:
    if column_exists('work_orders', 'uses_inventory'):
        op.drop_column('work_orders', 'uses_inventory')
