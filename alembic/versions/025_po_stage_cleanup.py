"""Drop legacy PO workflow FK columns; remove orphan purchase workflows.

Revision ID: 025_po_stage_cleanup
Revises: 024_po_stage_column
"""

import sqlalchemy as sa
from alembic import op

revision = '025_po_stage_cleanup'
down_revision = '024_po_stage_column'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            'ALTER TABLE purchase_orders '
            'DROP CONSTRAINT IF EXISTS purchase_orders_current_status_id_fkey'
        )
    )
    op.execute(
        sa.text(
            'ALTER TABLE purchase_orders '
            'DROP CONSTRAINT IF EXISTS purchase_orders_order_workflow_id_fkey'
        )
    )
    op.drop_column('purchase_orders', 'current_status_id')
    op.drop_column('purchase_orders', 'order_workflow_id')
    op.execute(sa.text("DELETE FROM order_workflows WHERE type = 'purchase'"))


def downgrade() -> None:
    op.add_column(
        'purchase_orders',
        sa.Column('current_status_id', sa.Integer(), nullable=True),
    )
    op.add_column(
        'purchase_orders',
        sa.Column('order_workflow_id', sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        'purchase_orders_current_status_id_fkey',
        'purchase_orders',
        'statuses',
        ['current_status_id'],
        ['id'],
        ondelete='RESTRICT',
    )
    op.create_foreign_key(
        'purchase_orders_order_workflow_id_fkey',
        'purchase_orders',
        'order_workflows',
        ['order_workflow_id'],
        ['id'],
        ondelete='RESTRICT',
    )
