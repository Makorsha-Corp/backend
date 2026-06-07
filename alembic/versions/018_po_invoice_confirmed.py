"""Add invoice_confirmed section flag on purchase orders

Revision ID: 018_po_invoice_confirmed
Revises: 017_po_number_per_workspace
"""
from alembic import op
import sqlalchemy as sa

revision = '018_po_invoice_confirmed'
down_revision = '017_po_number_per_workspace'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'purchase_orders',
        sa.Column('invoice_confirmed', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column('purchase_orders', 'invoice_confirmed', server_default=None)


def downgrade() -> None:
    op.drop_column('purchase_orders', 'invoice_confirmed')
