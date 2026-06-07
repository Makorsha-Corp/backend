"""Alembic chain placeholder (revision retained for deploy compatibility).

Invoice locking for POs with receipts is handled at runtime on receive.

Revision ID: 020_invoice_locked_backfill
Revises: 019_po_item_quantity_received_backfill
"""

from alembic import op

revision = '020_invoice_locked_backfill'
down_revision = '019_po_item_quantity_received_backfill'
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
