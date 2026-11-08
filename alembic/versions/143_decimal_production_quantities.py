"""Keep fractional quantities on recipes, batches, and the stock they post to.

Recipe input 1.2 and actual output 9.5 were Integer columns, so Postgres stored
1 and 9. Yield and product/storage stock followed the truncated number.

Revision ID: 143_decimal_production_quantities
Revises: 142_workspace_scoped_document_numbers
Create Date: 2026-10-06
"""
import sqlalchemy as sa
from alembic import op

revision = "143_decimal_production_quantities"
down_revision = "142_workspace_scoped_document_numbers"
branch_labels = None
depends_on = None

NUMERIC_COLUMNS = [
    ("production_formula_stage_items", "quantity"),
    ("production_formula_stages", "expected_output_quantity"),
    ("production_batch_items", "expected_quantity"),
    ("production_batch_items", "actual_quantity"),
    ("production_batch_items", "variance_quantity"),
    ("production_batch_stage_logs", "expected_output_quantity"),
    ("production_batch_stage_logs", "input_quantity"),
    ("production_batch_stage_logs", "output_quantity"),
    ("production_batch_stage_logs", "waste_quantity"),
    ("production_batch_stage_logs", "rework_quantity"),
    ("products", "qty"),
    ("product_ledger", "quantity"),
    ("product_ledger", "qty_before"),
    ("product_ledger", "qty_after"),
    ("inventory", "qty"),
    ("inventory_ledger", "quantity"),
    ("inventory_ledger", "qty_before"),
    ("inventory_ledger", "qty_after"),
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
