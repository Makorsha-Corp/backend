"""Add optional completion codes: sales_deliveries.completion_code (per delivery)
and sales_order_items.fulfillment_completion_code (per fulfilled line).

Revision ID: 106_completion_codes
Revises: 105_so_contact_confirm
Create Date: 2026-08-14
"""
import sqlalchemy as sa

from app.db.migration_helpers import add_column_if_not_exists, drop_column_if_exists

revision = "106_completion_codes"
down_revision = "105_so_contact_confirm"
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_column_if_not_exists("sales_deliveries", sa.Column("completion_code", sa.String(100), nullable=True))
    add_column_if_not_exists(
        "sales_order_items", sa.Column("fulfillment_completion_code", sa.String(100), nullable=True)
    )


def downgrade() -> None:
    drop_column_if_exists("sales_order_items", "fulfillment_completion_code")
    drop_column_if_exists("sales_deliveries", "completion_code")
