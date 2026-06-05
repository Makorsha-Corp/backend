"""Add per-section lock flags on purchase orders.

Revision ID: 011_po_section_locks
Revises: 010_po_events
Create Date: 2026-06-05
"""

import sqlalchemy as sa
from alembic import op

revision = '011_po_section_locks'
down_revision = '010_po_events'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'purchase_orders',
        sa.Column('details_locked', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        'purchase_orders',
        sa.Column('notes_locked', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        'purchase_orders',
        sa.Column('items_locked', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column('purchase_orders', 'items_locked')
    op.drop_column('purchase_orders', 'notes_locked')
    op.drop_column('purchase_orders', 'details_locked')
