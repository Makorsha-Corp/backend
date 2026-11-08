"""Scope order numbers to the workspace.

sales_order_number, transfer_number, delivery_number, and return numbers were
unique across the whole database. Each workspace generates SO-2026-001 (and the
same pattern for the others), so the second workspace's first document hit a
unique violation and the API returned 409 "This resource already exists".

expense_number already has uq_eo_workspace_number, but a leftover global unique
index still blocked EXP-2026-001 in a second workspace.

po_number is already unique per workspace (uq_po_workspace_number).

Revision ID: 142_workspace_scoped_document_numbers
Revises: 141_drop_batch_stored_totals
Create Date: 2026-10-05
"""
from alembic import op

from app.db.migration_helpers import (
    create_unique_constraint_if_not_exists,
    drop_unique_constraint_if_exists,
)

revision = "142_workspace_scoped_document_numbers"
down_revision = "141_drop_batch_stored_totals"
branch_labels = None
depends_on = None

# (table, old global unique index or constraint, new workspace constraint, number column)
_SCOPES = (
    (
        "sales_orders",
        "ix_sales_orders_sales_order_number",
        "sales_orders_sales_order_number_key",
        "uq_sales_orders_workspace_number",
        "sales_order_number",
    ),
    (
        "transfer_orders",
        "ix_transfer_orders_transfer_number",
        "transfer_orders_transfer_number_key",
        "uq_transfer_orders_workspace_number",
        "transfer_number",
    ),
    (
        "sales_deliveries",
        "ix_sales_deliveries_delivery_number",
        "sales_deliveries_delivery_number_key",
        "uq_sales_deliveries_workspace_number",
        "delivery_number",
    ),
    (
        "expense_orders",
        "ix_expense_orders_expense_number",
        "expense_orders_expense_number_key",
        "uq_eo_workspace_number",
        "expense_number",
    ),
    (
        "purchase_order_returns",
        "purchase_order_returns_return_number_key",
        "ix_purchase_order_returns_return_number",
        "uq_po_returns_workspace_number",
        "return_number",
    ),
    (
        "sales_order_returns",
        "sales_order_returns_return_number_key",
        "ix_sales_order_returns_return_number",
        "uq_so_returns_workspace_number",
        "return_number",
    ),
)


def _drop_index(name: str) -> None:
    op.execute(f'DROP INDEX IF EXISTS "{name}"')


def upgrade() -> None:
    for table, global_a, global_b, constraint, column in _SCOPES:
        # Constraint-backed unique indexes (return_number_key) must lose the
        # constraint first. Plain unique indexes (sales/transfer/delivery/expense)
        # are dropped by DROP INDEX. Either call is a no-op for the other kind.
        drop_unique_constraint_if_exists(table, global_a)
        drop_unique_constraint_if_exists(table, global_b)
        _drop_index(global_a)
        _drop_index(global_b)
        create_unique_constraint_if_not_exists(table, constraint, ["workspace_id", column])
        op.execute(f'CREATE INDEX IF NOT EXISTS "ix_{table}_{column}" ON "{table}" ("{column}")')


def downgrade() -> None:
    for table, global_a, _global_b, constraint, column in _SCOPES:
        if constraint != "uq_eo_workspace_number":
            drop_unique_constraint_if_exists(table, constraint)
        op.execute(f'DROP INDEX IF EXISTS "ix_{table}_{column}"')
        op.execute(
            f'CREATE UNIQUE INDEX IF NOT EXISTS "{global_a}" ON "{table}" ("{column}")'
        )
