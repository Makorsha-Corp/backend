"""Work order soft timing windows.

Revision ID: 152_work_order_soft_timing
Revises: 151_batch_recurring_status
Create Date: 2026-11-02
"""
import sqlalchemy as sa
from alembic import op

revision = "152_work_order_soft_timing"
down_revision = "151_batch_recurring_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("work_orders", sa.Column("shift_id", sa.Integer(), nullable=True))
    op.add_column("work_orders", sa.Column("planned_start_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("work_orders", sa.Column("planned_end_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        "fk_work_orders_shift_id",
        "work_orders",
        "workspace_shifts",
        ["shift_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_work_orders_shift_id", "work_orders", ["shift_id"])

    for table in ("work_order_templates", "work_order_programs"):
        op.add_column(table, sa.Column("shift_id", sa.Integer(), nullable=True))
        op.add_column(table, sa.Column("planned_start_time", sa.Time(), nullable=True))
        op.add_column(table, sa.Column("expected_duration_minutes", sa.Integer(), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_shift_id",
            table,
            "workspace_shifts",
            ["shift_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    for table in ("work_order_programs", "work_order_templates"):
        op.drop_constraint(f"fk_{table}_shift_id", table, type_="foreignkey")
        op.drop_column(table, "expected_duration_minutes")
        op.drop_column(table, "planned_start_time")
        op.drop_column(table, "shift_id")

    op.drop_index("ix_work_orders_shift_id", table_name="work_orders")
    op.drop_constraint("fk_work_orders_shift_id", "work_orders", type_="foreignkey")
    op.drop_column("work_orders", "planned_end_at")
    op.drop_column("work_orders", "planned_start_at")
    op.drop_column("work_orders", "shift_id")
