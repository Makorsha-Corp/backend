"""work_order_programs.interval_days for custom cadence.

Revision ID: 148_work_order_program_interval
Revises: 147_work_order_programs
Create Date: 2026-10-26
"""
import sqlalchemy as sa
from alembic import op

revision = "148_work_order_program_interval"
down_revision = "147_work_order_programs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "work_order_programs",
        sa.Column("interval_days", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("work_order_programs", "interval_days")
