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

from app.db.migration_helpers import add_column_if_not_exists, column_exists

revision = '008_po_dates'
down_revision = '007_position_to_workspace_member'
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_column_if_not_exists('purchase_orders', sa.Column('order_date', sa.Date(), nullable=True))
    add_column_if_not_exists(
        'purchase_orders', sa.Column('expected_delivery_date', sa.Date(), nullable=True)
    )
    add_column_if_not_exists(
        'purchase_orders', sa.Column('actual_delivery_date', sa.Date(), nullable=True)
    )
    if column_exists('purchase_orders', 'order_date'):
        op.execute(
            'UPDATE purchase_orders SET order_date = created_at::date WHERE order_date IS NULL'
        )


def downgrade() -> None:
    from app.db.migration_helpers import drop_column_if_exists

    drop_column_if_exists('purchase_orders', 'actual_delivery_date')
    drop_column_if_exists('purchase_orders', 'expected_delivery_date')
    drop_column_if_exists('purchase_orders', 'order_date')
