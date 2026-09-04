"""Add return_type to PO/SO returns and quantity_refunded tracking columns.

Revision ID: 114_return_type_and_refunds
Revises: 113_order_returns
Create Date: 2026-08-29
"""
import sqlalchemy as sa

from app.db.migration_helpers import add_column_if_not_exists, drop_column_if_exists

revision = "121_return_type_and_refunds"
down_revision = "120_order_returns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_column_if_not_exists(
        "purchase_order_returns",
        sa.Column("return_type", sa.String(20), nullable=False, server_default="refund"),
    )
    add_column_if_not_exists(
        "sales_order_returns",
        sa.Column("return_type", sa.String(20), nullable=False, server_default="refund"),
    )
    add_column_if_not_exists(
        "purchase_order_items",
        sa.Column("quantity_refunded", sa.Numeric(15, 2), nullable=False, server_default="0"),
    )
    add_column_if_not_exists(
        "sales_order_items",
        sa.Column("quantity_refunded", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    drop_column_if_exists("sales_order_items", "quantity_refunded")
    drop_column_if_exists("purchase_order_items", "quantity_refunded")
    drop_column_if_exists("sales_order_returns", "return_type")
    drop_column_if_exists("purchase_order_returns", "return_type")
