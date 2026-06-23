"""Drop order-header note fields; sales orders notes -> description.

Revision ID: 035_drop_order_header_notes
Revises: 034_transfer_order_simplify_workflow
"""

import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import column_exists, drop_column_if_exists

revision = "035_drop_order_header_notes"
down_revision = "034_transfer_order_simplify_workflow"
branch_labels = None
depends_on = None


def upgrade() -> None:
    drop_column_if_exists("transfer_orders", "note")
    drop_column_if_exists("purchase_orders", "order_note")
    drop_column_if_exists("purchase_orders", "notes_confirmed")
    drop_column_if_exists("expense_orders", "expense_note")
    drop_column_if_exists("expense_orders", "internal_note")
    drop_column_if_exists("work_orders", "notes")

    if column_exists("sales_orders", "notes") and not column_exists("sales_orders", "description"):
        op.add_column("sales_orders", sa.Column("description", sa.Text(), nullable=True))
        op.execute(sa.text("UPDATE sales_orders SET description = notes WHERE notes IS NOT NULL"))
        op.drop_column("sales_orders", "notes")
    elif column_exists("sales_orders", "notes"):
        drop_column_if_exists("sales_orders", "notes")


def downgrade() -> None:
    if not column_exists("transfer_orders", "note"):
        op.add_column("transfer_orders", sa.Column("note", sa.Text(), nullable=True))

    if not column_exists("purchase_orders", "order_note"):
        op.add_column("purchase_orders", sa.Column("order_note", sa.Text(), nullable=True))
    if not column_exists("purchase_orders", "notes_confirmed"):
        op.add_column(
            "purchase_orders",
            sa.Column("notes_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        op.alter_column("purchase_orders", "notes_confirmed", server_default=None)

    if not column_exists("expense_orders", "expense_note"):
        op.add_column("expense_orders", sa.Column("expense_note", sa.Text(), nullable=True))
    if not column_exists("expense_orders", "internal_note"):
        op.add_column("expense_orders", sa.Column("internal_note", sa.Text(), nullable=True))

    if not column_exists("work_orders", "notes"):
        op.add_column("work_orders", sa.Column("notes", sa.Text(), nullable=True))

    if column_exists("sales_orders", "description") and not column_exists("sales_orders", "notes"):
        op.add_column("sales_orders", sa.Column("notes", sa.Text(), nullable=True))
        op.execute(sa.text("UPDATE sales_orders SET notes = description WHERE description IS NOT NULL"))
        op.drop_column("sales_orders", "description")
