"""Add order_date, expected_delivery_date, actual_delivery_date to purchase_orders.

order_date / expected_delivery_date are user-set; actual_delivery_date is
auto-set when all line items are received. Existing rows backfill order_date
from created_at.

Revision ID: 008_po_dates
Revises: 007_position_to_workspace_member
Create Date: 2026-06-05
"""

import sqlalchemy as sa
from alembic import op

revision = '008_po_dates'
down_revision = '007_position_to_workspace_member'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('purchase_orders', sa.Column('order_date', sa.Date(), nullable=True))
    op.add_column('purchase_orders', sa.Column('expected_delivery_date', sa.Date(), nullable=True))
    op.add_column('purchase_orders', sa.Column('actual_delivery_date', sa.Date(), nullable=True))
    op.execute('UPDATE purchase_orders SET order_date = created_at::date WHERE order_date IS NULL')


def downgrade() -> None:
    op.drop_column('purchase_orders', 'actual_delivery_date')
    op.drop_column('purchase_orders', 'expected_delivery_date')
    op.drop_column('purchase_orders', 'order_date')
