"""Add per-section lock flags on purchase orders.

Revision ID: 011_po_section_locks
Revises: 010_po_events
Create Date: 2026-06-05
"""

import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import add_column_if_not_exists, column_names

revision = '011_po_section_locks'
down_revision = '010_po_events'
branch_labels = None
depends_on = None


def upgrade() -> None:
    po_cols = column_names('purchase_orders')
    if 'details_confirmed' in po_cols:
        return

    add_column_if_not_exists(
        'purchase_orders',
        sa.Column('details_locked', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    add_column_if_not_exists(
        'purchase_orders',
        sa.Column('notes_locked', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    add_column_if_not_exists(
        'purchase_orders',
        sa.Column('items_locked', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    from app.db.migration_helpers import drop_column_if_exists

    drop_column_if_exists('purchase_orders', 'items_locked')
    drop_column_if_exists('purchase_orders', 'notes_locked')
    drop_column_if_exists('purchase_orders', 'details_locked')
