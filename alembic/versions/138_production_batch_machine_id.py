"""production_batches.machine_id for simple / run-level station

Revision ID: 138_production_batch_machine_id
Revises: 137_profile_use_24_hour_time
Create Date: 2026-10-04

"""
from alembic import op
import sqlalchemy as sa


revision = "138_production_batch_machine_id"
down_revision = "137_profile_use_24_hour_time"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "production_batches",
        sa.Column("machine_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_production_batches_machine_id",
        "production_batches",
        "machines",
        ["machine_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_production_batches_machine_id",
        "production_batches",
        ["machine_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_production_batches_machine_id", table_name="production_batches")
    op.drop_constraint("fk_production_batches_machine_id", "production_batches", type_="foreignkey")
    op.drop_column("production_batches", "machine_id")
