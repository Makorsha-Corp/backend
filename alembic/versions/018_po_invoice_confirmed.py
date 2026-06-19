"""Add invoice_confirmed section flag on purchase orders

Revision ID: 018_po_invoice_confirmed
Revises: 017_po_number_per_workspace
"""
import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import add_column_if_not_exists, column_exists

revision = '018_po_invoice_confirmed'
down_revision = '017_po_number_per_workspace'
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_column_if_not_exists(
        'purchase_orders',
        sa.Column('invoice_confirmed', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    if column_exists('purchase_orders', 'invoice_confirmed'):
        op.alter_column('purchase_orders', 'invoice_confirmed', server_default=None)


def downgrade() -> None:
    from app.db.migration_helpers import drop_column_if_exists

    drop_column_if_exists('purchase_orders', 'invoice_confirmed')
