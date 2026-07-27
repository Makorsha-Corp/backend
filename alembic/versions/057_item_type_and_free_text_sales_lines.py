"""Item.item_type (physical/service) + free-text sales order lines.

Revision ID: 057_item_type_and_free_text_sales_lines
Revises: 056_merge_payment_and_schedules
Create Date: 2026-07-23
"""
import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import add_column_if_not_exists, drop_column_if_exists

revision = "057_item_type_and_free_text_sales_lines"
down_revision = "056_merge_payment_and_schedules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_column_if_not_exists(
        "items",
        sa.Column("item_type", sa.String(20), nullable=False, server_default="physical"),
    )
    add_column_if_not_exists(
        "sales_order_items",
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.alter_column(
        "sales_order_items", "item_id",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.create_check_constraint(
        "ck_sales_order_items_item_or_description",
        "sales_order_items",
        "item_id IS NOT NULL OR description IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_sales_order_items_item_or_description", "sales_order_items", type_="check"
    )
    # Free-text lines have no catalog item to fall back to — deleting them is the
    # only way to safely re-tighten item_id to NOT NULL. Documented data loss.
    op.execute(sa.text("DELETE FROM sales_order_items WHERE item_id IS NULL"))
    op.alter_column(
        "sales_order_items", "item_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    drop_column_if_exists("sales_order_items", "description")
    drop_column_if_exists("items", "item_type")
