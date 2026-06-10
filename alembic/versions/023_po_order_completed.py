"""Add order_completed flag for manual PO completion

Revision ID: 023_po_order_completed
Revises: 022_po_stage_workflow
"""

from alembic import op
import sqlalchemy as sa

revision = '023_po_order_completed'
down_revision = '022_po_stage_workflow'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'purchase_orders',
        sa.Column('order_completed', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column('purchase_orders', 'order_completed', server_default=None)


def downgrade() -> None:
    op.drop_column('purchase_orders', 'order_completed')
