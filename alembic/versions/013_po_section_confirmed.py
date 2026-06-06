"""Rename PO section locks to confirmed; add supplier_confirmed.

Revision ID: 013_po_section_confirmed
Revises: 012_drop_po_internal_note
Create Date: 2026-06-05
"""

import sqlalchemy as sa
from alembic import op

revision = '013_po_section_confirmed'
down_revision = '012_drop_po_internal_note'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column('purchase_orders', 'details_locked', new_column_name='details_confirmed')
    op.alter_column('purchase_orders', 'notes_locked', new_column_name='notes_confirmed')
    op.alter_column('purchase_orders', 'items_locked', new_column_name='items_confirmed')
    op.add_column(
        'purchase_orders',
        sa.Column('supplier_confirmed', sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.execute(
        "UPDATE purchase_order_events SET event_type = REPLACE(event_type, '_unlocked', '_unconfirmed') "
        "WHERE event_type LIKE '%_unlocked'"
    )
    op.execute(
        "UPDATE purchase_order_events SET event_type = REPLACE(event_type, '_locked', '_confirmed') "
        "WHERE event_type LIKE '%_locked'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE purchase_order_events SET event_type = REPLACE(event_type, '_unconfirmed', '_unlocked') "
        "WHERE event_type LIKE '%_unconfirmed'"
    )
    op.execute(
        "UPDATE purchase_order_events SET event_type = REPLACE(event_type, '_confirmed', '_locked') "
        "WHERE event_type LIKE '%_confirmed'"
    )

    op.drop_column('purchase_orders', 'supplier_confirmed')
    op.alter_column('purchase_orders', 'items_confirmed', new_column_name='items_locked')
    op.alter_column('purchase_orders', 'notes_confirmed', new_column_name='notes_locked')
    op.alter_column('purchase_orders', 'details_confirmed', new_column_name='details_locked')
