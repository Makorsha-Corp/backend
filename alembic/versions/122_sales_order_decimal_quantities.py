"""Widen sales-order quantity columns from Integer to Numeric(15,2) to match
purchase-order precision.

Revision ID: 115_sales_order_decimal_quantities
Revises: 114_return_type_and_refunds
Create Date: 2026-08-30
"""
import sqlalchemy as sa
from alembic import op

revision = "122_sales_order_decimal_quantities"
down_revision = "121_return_type_and_refunds"
branch_labels = None
depends_on = None

NUMERIC_COLUMNS = [
    ("sales_order_items", "quantity_ordered"),
    ("sales_order_items", "quantity_delivered"),
    ("sales_order_items", "quantity_returned"),
    ("sales_order_items", "quantity_refunded"),
    ("sales_delivery_items", "quantity_delivered"),
    ("sales_order_return_items", "quantity_returned"),
]


def upgrade() -> None:
    for table, column in NUMERIC_COLUMNS:
        op.alter_column(
            table,
            column,
            type_=sa.Numeric(15, 2),
            postgresql_using=f"{column}::numeric(15,2)",
        )


def downgrade() -> None:
    for table, column in reversed(NUMERIC_COLUMNS):
        op.alter_column(
            table,
            column,
            type_=sa.Integer(),
            postgresql_using=f"trunc({column})::integer",
        )
