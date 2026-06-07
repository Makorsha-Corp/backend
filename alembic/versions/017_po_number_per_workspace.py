"""Scope purchase order po_number uniqueness per workspace.

Revision ID: 017_po_number_per_workspace
Revises: 016_invoice_status_and_void
Create Date: 2026-06-07
"""

from alembic import op

revision = '017_po_number_per_workspace'
down_revision = '016_invoice_status_and_void'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        'ALTER TABLE purchase_orders DROP CONSTRAINT IF EXISTS purchase_orders_po_number_key'
    )
    op.create_unique_constraint(
        'uq_po_workspace_number',
        'purchase_orders',
        ['workspace_id', 'po_number'],
    )


def downgrade() -> None:
    op.drop_constraint('uq_po_workspace_number', 'purchase_orders', type_='unique')
    op.create_unique_constraint('purchase_orders_po_number_key', 'purchase_orders', ['po_number'])
