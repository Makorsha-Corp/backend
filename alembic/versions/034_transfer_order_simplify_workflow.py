"""Drop transfer order section confirms and legacy date columns.

Revision ID: 034_transfer_order_simplify_workflow
Revises: 033_drop_machine_events
"""

import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import column_exists

revision = "034_transfer_order_simplify_workflow"
down_revision = "033_drop_machine_events"
branch_labels = None
depends_on = None

_COLUMNS = (
    "order_date",
    "expected_completion_date",
    "route_confirmed",
    "items_confirmed",
)


def upgrade() -> None:
    for col in _COLUMNS:
        if column_exists("transfer_orders", col):
            op.drop_column("transfer_orders", col)


def downgrade() -> None:
    if not column_exists("transfer_orders", "order_date"):
        op.add_column(
            "transfer_orders",
            sa.Column("order_date", sa.Date(), nullable=False, server_default=sa.text("CURRENT_DATE")),
        )
        op.alter_column("transfer_orders", "order_date", server_default=None)
    if not column_exists("transfer_orders", "expected_completion_date"):
        op.add_column(
            "transfer_orders",
            sa.Column("expected_completion_date", sa.Date(), nullable=True),
        )
    if not column_exists("transfer_orders", "route_confirmed"):
        op.add_column(
            "transfer_orders",
            sa.Column("route_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        op.alter_column("transfer_orders", "route_confirmed", server_default=None)
    if not column_exists("transfer_orders", "items_confirmed"):
        op.add_column(
            "transfer_orders",
            sa.Column("items_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        op.alter_column("transfer_orders", "items_confirmed", server_default=None)
