"""Sales orders: add per-order contact_name/contact_phone; merge customer_confirmed
+ details_confirmed into a single order_info_confirmed column.

Revision ID: 105_so_contact_confirm
Revises: 104_drop_so_quotation_sent
Create Date: 2026-08-14
"""
import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import add_column_if_not_exists, column_exists, drop_column_if_exists

revision = "105_so_contact_confirm"
down_revision = "104_drop_so_quotation_sent"
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_column_if_not_exists("sales_orders", sa.Column("contact_name", sa.String(255), nullable=True))
    add_column_if_not_exists("sales_orders", sa.Column("contact_phone", sa.String(50), nullable=True))

    add_column_if_not_exists(
        "sales_orders", sa.Column("order_info_confirmed", sa.Boolean(), nullable=False, server_default="false")
    )
    if column_exists("sales_orders", "customer_confirmed") and column_exists("sales_orders", "details_confirmed"):
        op.execute(
            "UPDATE sales_orders SET order_info_confirmed = (customer_confirmed AND details_confirmed)"
        )

    drop_column_if_exists("sales_orders", "customer_confirmed")
    drop_column_if_exists("sales_orders", "details_confirmed")


def downgrade() -> None:
    add_column_if_not_exists(
        "sales_orders", sa.Column("customer_confirmed", sa.Boolean(), nullable=False, server_default="false")
    )
    add_column_if_not_exists(
        "sales_orders", sa.Column("details_confirmed", sa.Boolean(), nullable=False, server_default="false")
    )
    if column_exists("sales_orders", "order_info_confirmed"):
        op.execute(
            "UPDATE sales_orders SET customer_confirmed = order_info_confirmed, "
            "details_confirmed = order_info_confirmed"
        )
    drop_column_if_exists("sales_orders", "order_info_confirmed")
    drop_column_if_exists("sales_orders", "contact_phone")
    drop_column_if_exists("sales_orders", "contact_name")
