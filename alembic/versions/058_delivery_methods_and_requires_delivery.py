"""Delivery methods, per-line requires_delivery flag, nullable delivery item_id.

Revision ID: 058_delivery_methods_and_requires_delivery
Revises: 057_item_type_and_free_text_sales_lines
Create Date: 2026-07-26
"""
import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import (
    add_column_if_not_exists,
    drop_column_if_exists,
    table_exists,
)

revision = "058_delivery_methods_and_requires_delivery"
down_revision = "057_item_type_and_free_text_sales_lines"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not table_exists("delivery_methods"):
        op.create_table(
            "delivery_methods",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("profiles.id"), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("updated_by", sa.Integer(), sa.ForeignKey("profiles.id"), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
            sa.Column("deleted_by", sa.Integer(), sa.ForeignKey("profiles.id"), nullable=True),
        )
        op.create_index("ix_delivery_methods_workspace_id", "delivery_methods", ["workspace_id"])

    add_column_if_not_exists(
        "sales_order_items",
        sa.Column("requires_delivery", sa.Boolean(), nullable=False, server_default="true"),
    )
    add_column_if_not_exists(
        "sales_deliveries",
        sa.Column(
            "delivery_method_id", sa.Integer(),
            sa.ForeignKey("delivery_methods.id", ondelete="SET NULL"), nullable=True,
        ),
    )
    op.create_index("ix_sales_deliveries_delivery_method_id", "sales_deliveries", ["delivery_method_id"])

    # sales_delivery_items.item_id: relax to nullable so delivered free-text lines
    # (no catalog item, no Product stock to deduct) can be recorded in a delivery.
    op.alter_column(
        "sales_delivery_items", "item_id",
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM sales_delivery_items WHERE item_id IS NULL"))
    op.alter_column(
        "sales_delivery_items", "item_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.drop_index("ix_sales_deliveries_delivery_method_id", table_name="sales_deliveries")
    drop_column_if_exists("sales_deliveries", "delivery_method_id")
    drop_column_if_exists("sales_order_items", "requires_delivery")
    if table_exists("delivery_methods"):
        op.drop_table("delivery_methods")
