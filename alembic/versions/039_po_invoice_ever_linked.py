"""po invoice_ever_linked flag

Revision ID: 039_po_invoice_ever_linked
Revises: 038_po_receive_events
Create Date: 2026-06-28
"""
from alembic import op
import sqlalchemy as sa

revision = '039_po_invoice_ever_linked'
down_revision = '038_po_receive_events'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'purchase_orders',
        sa.Column('invoice_ever_linked', sa.Boolean(), nullable=False, server_default='false'),
    )
    # Backfill: any PO currently holding an invoice_id has definitely had one
    op.execute(
        "UPDATE purchase_orders SET invoice_ever_linked = true WHERE invoice_id IS NOT NULL"
    )


def downgrade():
    op.drop_column('purchase_orders', 'invoice_ever_linked')
