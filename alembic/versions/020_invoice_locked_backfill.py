"""Backfill locked invoice status for POs with receipts

Revision ID: 020_invoice_locked_backfill
Revises: 018_po_invoice_confirmed
"""
from alembic import op

revision = '020_invoice_locked_backfill'
down_revision = '018_po_invoice_confirmed'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        UPDATE account_invoices ai
        SET invoice_status = 'locked'
        FROM purchase_orders po
        WHERE po.invoice_id = ai.id
          AND ai.invoice_status = 'confirmed'
          AND EXISTS (
            SELECT 1
            FROM purchase_order_items poi
            WHERE poi.purchase_order_id = po.id
              AND poi.quantity_received > 0
          )
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE account_invoices
        SET invoice_status = 'confirmed'
        WHERE invoice_status = 'locked'
    """)
