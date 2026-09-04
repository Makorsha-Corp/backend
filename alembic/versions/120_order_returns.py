"""Add PO/SO return tables and quantity_returned tracking columns.

Revision ID: 113_order_returns
Revises: 112_merge_heads
Create Date: 2026-08-18
"""
import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import add_column_if_not_exists, drop_column_if_exists, table_exists

revision = "120_order_returns"
down_revision = "119_work_order_workers_hybrid"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not table_exists("purchase_order_returns"):
        op.create_table(
            "purchase_order_returns",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
            sa.Column("purchase_order_id", sa.Integer(), sa.ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False),
            sa.Column("return_number", sa.String(100), nullable=False, unique=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("account_invoices.id", ondelete="SET NULL"), nullable=True),
            sa.Column("paid", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("completed_by", sa.Integer(), sa.ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("profiles.id", ondelete="SET NULL"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_by", sa.Integer(), sa.ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_purchase_order_returns_workspace_id", "purchase_order_returns", ["workspace_id"])
        op.create_index("ix_purchase_order_returns_purchase_order_id", "purchase_order_returns", ["purchase_order_id"])
        op.create_index("ix_purchase_order_returns_return_number", "purchase_order_returns", ["return_number"])
        op.create_index("ix_purchase_order_returns_status", "purchase_order_returns", ["status"])
        op.create_index("ix_purchase_order_returns_invoice_id", "purchase_order_returns", ["invoice_id"])

    if not table_exists("purchase_order_return_items"):
        op.create_table(
            "purchase_order_return_items",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
            sa.Column("return_id", sa.Integer(), sa.ForeignKey("purchase_order_returns.id", ondelete="CASCADE"), nullable=False),
            sa.Column("po_item_id", sa.Integer(), sa.ForeignKey("purchase_order_items.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("item_id", sa.Integer(), sa.ForeignKey("items.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("quantity_returned", sa.Numeric(15, 2), nullable=False),
            sa.Column("unit_price", sa.Numeric(15, 2), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
        )
        op.create_index("ix_purchase_order_return_items_workspace_id", "purchase_order_return_items", ["workspace_id"])
        op.create_index("ix_purchase_order_return_items_return_id", "purchase_order_return_items", ["return_id"])
        op.create_index("ix_purchase_order_return_items_po_item_id", "purchase_order_return_items", ["po_item_id"])

    if not table_exists("sales_order_returns"):
        op.create_table(
            "sales_order_returns",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
            sa.Column("sales_order_id", sa.Integer(), sa.ForeignKey("sales_orders.id", ondelete="CASCADE"), nullable=False),
            sa.Column("return_number", sa.String(100), nullable=False, unique=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("account_invoices.id", ondelete="SET NULL"), nullable=True),
            sa.Column("paid", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("completed_by", sa.Integer(), sa.ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("profiles.id", ondelete="SET NULL"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_by", sa.Integer(), sa.ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_sales_order_returns_workspace_id", "sales_order_returns", ["workspace_id"])
        op.create_index("ix_sales_order_returns_sales_order_id", "sales_order_returns", ["sales_order_id"])
        op.create_index("ix_sales_order_returns_return_number", "sales_order_returns", ["return_number"])
        op.create_index("ix_sales_order_returns_status", "sales_order_returns", ["status"])
        op.create_index("ix_sales_order_returns_invoice_id", "sales_order_returns", ["invoice_id"])

    if not table_exists("sales_order_return_items"):
        op.create_table(
            "sales_order_return_items",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
            sa.Column("return_id", sa.Integer(), sa.ForeignKey("sales_order_returns.id", ondelete="CASCADE"), nullable=False),
            sa.Column("so_item_id", sa.Integer(), sa.ForeignKey("sales_order_items.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("item_id", sa.Integer(), sa.ForeignKey("items.id", ondelete="RESTRICT"), nullable=True),
            sa.Column("quantity_returned", sa.Integer(), nullable=False),
            sa.Column("unit_price", sa.Numeric(15, 2), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
        )
        op.create_index("ix_sales_order_return_items_workspace_id", "sales_order_return_items", ["workspace_id"])
        op.create_index("ix_sales_order_return_items_return_id", "sales_order_return_items", ["return_id"])
        op.create_index("ix_sales_order_return_items_so_item_id", "sales_order_return_items", ["so_item_id"])

    add_column_if_not_exists(
        "purchase_order_items",
        sa.Column("quantity_returned", sa.Numeric(15, 2), nullable=False, server_default="0"),
    )
    add_column_if_not_exists(
        "sales_order_items",
        sa.Column("quantity_returned", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    drop_column_if_exists("sales_order_items", "quantity_returned")
    drop_column_if_exists("purchase_order_items", "quantity_returned")

    if table_exists("sales_order_return_items"):
        op.drop_table("sales_order_return_items")
    if table_exists("sales_order_returns"):
        op.drop_table("sales_order_returns")
    if table_exists("purchase_order_return_items"):
        op.drop_table("purchase_order_return_items")
    if table_exists("purchase_order_returns"):
        op.drop_table("purchase_order_returns")
