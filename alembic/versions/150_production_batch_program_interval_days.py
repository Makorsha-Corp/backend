"""production_batch_programs.interval_days for custom cadence.

Revision ID: 150_batch_program_interval
Revises: 149_batch_planned_status
Create Date: 2026-10-27
"""
import sqlalchemy as sa
from alembic import op

revision = "150_batch_program_interval"
down_revision = "149_batch_planned_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "production_batch_programs",
        sa.Column("interval_days", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("production_batch_programs", "interval_days")
