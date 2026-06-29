"""po item nullable unit_price and line_subtotal

Revision ID: 040_po_item_nullable_unit_price
Revises: 039_po_invoice_ever_linked
Create Date: 2026-06-28
"""
from alembic import op
import sqlalchemy as sa

revision = '040_po_item_nullable_unit_price'
down_revision = '039_po_invoice_ever_linked'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        'purchase_order_items',
        'unit_price',
        existing_type=sa.Numeric(15, 2),
        nullable=True,
    )
    op.alter_column(
        'purchase_order_items',
        'line_subtotal',
        existing_type=sa.Numeric(15, 2),
        nullable=True,
    )


def downgrade():
    op.alter_column(
        'purchase_order_items',
        'line_subtotal',
        existing_type=sa.Numeric(15, 2),
        nullable=False,
    )
    op.alter_column(
        'purchase_order_items',
        'unit_price',
        existing_type=sa.Numeric(15, 2),
        nullable=False,
    )
