"""Invoice items, invoice events, receiving_started, items_updated_at.

Revision ID: 036_invoice_items_events
Revises: 035_drop_order_header_notes
"""

import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import (
    add_column_if_not_exists,
    column_exists,
    table_exists,
)

revision = "036_invoice_items_events"
down_revision = "035_drop_order_header_notes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. items_updated_at on order tables — used for discrepancy detection
    add_column_if_not_exists("purchase_orders", sa.Column("items_updated_at", sa.DateTime(), nullable=True))
    add_column_if_not_exists("expense_orders",  sa.Column("items_updated_at", sa.DateTime(), nullable=True))
    add_column_if_not_exists("sales_orders",    sa.Column("items_updated_at", sa.DateTime(), nullable=True))

    # 2. New columns on account_invoices
    add_column_if_not_exists("account_invoices", sa.Column("order_type", sa.String(30), nullable=True))
    add_column_if_not_exists(
        "account_invoices",
        sa.Column("receiving_started", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    add_column_if_not_exists("account_invoices", sa.Column("last_synced_at", sa.DateTime(), nullable=True))

    # 3. Migrate locked → confirmed + receiving_started = true
    op.execute(sa.text(
        "UPDATE account_invoices "
        "SET invoice_status = 'confirmed', receiving_started = true "
        "WHERE invoice_status = 'locked'"
    ))

    # 4. invoice_items
    if not table_exists("invoice_items"):
        op.create_table(
            "invoice_items",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "workspace_id",
                sa.Integer(),
                sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "invoice_id",
                sa.Integer(),
                sa.ForeignKey("account_invoices.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("line_number", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("item_id", sa.Integer(), nullable=True),
            sa.Column("source_order_item_id", sa.Integer(), nullable=True),
            sa.Column("source_order_item_type", sa.String(30), nullable=True),
            sa.Column("quantity", sa.Numeric(15, 2), nullable=False),
            sa.Column("unit", sa.String(50), nullable=True),
            sa.Column("unit_price", sa.Numeric(15, 2), nullable=False),
            sa.Column("line_subtotal", sa.Numeric(15, 2), nullable=False),
            sa.Column("last_synced_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column(
                "created_by",
                sa.Integer(),
                sa.ForeignKey("profiles.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
        op.create_index("ix_invoice_items_workspace_id", "invoice_items", ["workspace_id"])
        op.create_index("ix_invoice_items_invoice_id", "invoice_items", ["invoice_id"])

    # 5. invoice_events — replaces invoice_status_tracker + financial_audit_logs for invoices
    if not table_exists("invoice_events"):
        op.create_table(
            "invoice_events",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "workspace_id",
                sa.Integer(),
                sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "invoice_id",
                sa.Integer(),
                sa.ForeignKey("account_invoices.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("event_type", sa.String(50), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column(
                "performed_by",
                sa.Integer(),
                sa.ForeignKey("profiles.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_invoice_events_workspace_id", "invoice_events", ["workspace_id"])
        op.create_index("ix_invoice_events_invoice_id", "invoice_events", ["invoice_id"])


def downgrade() -> None:
    if table_exists("invoice_events"):
        op.drop_table("invoice_events")
    if table_exists("invoice_items"):
        op.drop_table("invoice_items")

    for table, col in [
        ("account_invoices", "last_synced_at"),
        ("account_invoices", "receiving_started"),
        ("account_invoices", "order_type"),
        ("sales_orders", "items_updated_at"),
        ("expense_orders", "items_updated_at"),
        ("purchase_orders", "items_updated_at"),
    ]:
        if column_exists(table, col):
            op.drop_column(table, col)

    # Note: locked→confirmed data migration is not reversed
