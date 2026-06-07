"""Alembic chain placeholder (revision retained for deploy compatibility).

No data backfill — fresh PO lines set quantity_received on create.

Revision ID: 019_po_item_quantity_received_backfill
Revises: 018_po_invoice_confirmed
"""

from alembic import op

revision = '019_po_item_quantity_received_backfill'
down_revision = '018_po_invoice_confirmed'
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
