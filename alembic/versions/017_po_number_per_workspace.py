"""Scope purchase order po_number uniqueness per workspace.

Revision ID: 017_po_number_per_workspace
Revises: 016_invoice_status_and_void
Create Date: 2026-06-07
"""

from alembic import op

from app.db.migration_helpers import create_unique_constraint_if_not_exists, drop_unique_constraint_if_exists

revision = '017_po_number_per_workspace'
down_revision = '016_invoice_status_and_void'
branch_labels = None
depends_on = None


def upgrade() -> None:
    drop_unique_constraint_if_exists('purchase_orders', 'purchase_orders_po_number_key')
    create_unique_constraint_if_not_exists(
        'purchase_orders', 'uq_po_workspace_number', ['workspace_id', 'po_number']
    )


def downgrade() -> None:
    drop_unique_constraint_if_exists('purchase_orders', 'uq_po_workspace_number')
    from app.db.migration_helpers import unique_constraint_exists

    if not unique_constraint_exists('purchase_orders', 'purchase_orders_po_number_key'):
        op.create_unique_constraint('purchase_orders_po_number_key', 'purchase_orders', ['po_number'])
