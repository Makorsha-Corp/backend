"""profile use_24_hour_time preference

Revision ID: 137_profile_use_24_hour_time
Revises: 136_workspace_shifts_and_batch_shift_id
Create Date: 2026-10-04

"""
from alembic import op
import sqlalchemy as sa


revision = "137_profile_use_24_hour_time"
down_revision = "136_workspace_shifts_and_batch_shift_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column("use_24_hour_time", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )


def downgrade() -> None:
    op.drop_column("profiles", "use_24_hour_time")
