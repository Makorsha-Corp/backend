"""Alembic chain placeholder (revision retained for deploy compatibility).

Revision ID: 021_po_item_quantity_received_backfill
Revises: 020_invoice_locked_backfill
"""

from alembic import op

revision = '021_po_item_quantity_received_backfill'
down_revision = '020_invoice_locked_backfill'
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
