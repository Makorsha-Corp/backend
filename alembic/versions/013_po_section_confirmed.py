"""Rename PO section locks to confirmed; add supplier_confirmed.

Revision ID: 013_po_section_confirmed
Revises: 012_drop_po_internal_note
Create Date: 2026-06-05
"""

import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import add_column_if_not_exists, column_names

revision = '013_po_section_confirmed'
down_revision = '012_drop_po_internal_note'
branch_labels = None
depends_on = None


def upgrade() -> None:
    po_cols = column_names('purchase_orders')

    if 'details_locked' in po_cols:
        op.alter_column('purchase_orders', 'details_locked', new_column_name='details_confirmed')
    if 'notes_locked' in po_cols:
        op.alter_column('purchase_orders', 'notes_locked', new_column_name='notes_confirmed')
    if 'items_locked' in po_cols:
        op.alter_column('purchase_orders', 'items_locked', new_column_name='items_confirmed')

    add_column_if_not_exists(
        'purchase_orders',
        sa.Column('supplier_confirmed', sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    if table_has_po_events():
        op.execute(
            "UPDATE purchase_order_events SET event_type = REPLACE(event_type, '_unlocked', '_unconfirmed') "
            "WHERE event_type LIKE '%_unlocked'"
        )
        op.execute(
            "UPDATE purchase_order_events SET event_type = REPLACE(event_type, '_locked', '_confirmed') "
            "WHERE event_type LIKE '%_locked'"
        )


def table_has_po_events() -> bool:
    from app.db.migration_helpers import table_exists

    return table_exists('purchase_order_events')


def downgrade() -> None:
    from app.db.migration_helpers import column_exists, drop_column_if_exists

    if table_has_po_events():
        op.execute(
            "UPDATE purchase_order_events SET event_type = REPLACE(event_type, '_unconfirmed', '_unlocked') "
            "WHERE event_type LIKE '%_unconfirmed'"
        )
        op.execute(
            "UPDATE purchase_order_events SET event_type = REPLACE(event_type, '_confirmed', '_locked') "
            "WHERE event_type LIKE '%_confirmed'"
        )

    drop_column_if_exists('purchase_orders', 'supplier_confirmed')

    po_cols = column_names('purchase_orders')
    if 'items_confirmed' in po_cols:
        op.alter_column('purchase_orders', 'items_confirmed', new_column_name='items_locked')
    if 'notes_confirmed' in po_cols:
        op.alter_column('purchase_orders', 'notes_confirmed', new_column_name='notes_locked')
    if 'details_confirmed' in po_cols:
        op.alter_column('purchase_orders', 'details_confirmed', new_column_name='details_locked')
