"""Production batch activity events table.

Revision ID: 140_production_batch_events
Revises: 139_drop_legacy_formula_items
Create Date: 2026-10-05
"""
import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import table_exists

revision = "140_production_batch_events"
down_revision = "139_drop_legacy_formula_items"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if table_exists("production_batch_events"):
        return
    op.create_table(
        "production_batch_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("batch_stage_log_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("performed_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["production_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["batch_stage_log_id"], ["production_batch_stage_logs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["performed_by"], ["profiles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_production_batch_events_batch_id",
        "production_batch_events",
        ["batch_id"],
        unique=False,
    )
    op.create_index(
        "ix_production_batch_events_workspace_id",
        "production_batch_events",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        "ix_production_batch_events_batch_stage_log_id",
        "production_batch_events",
        ["batch_stage_log_id"],
        unique=False,
    )


def downgrade() -> None:
    if not table_exists("production_batch_events"):
        return
    op.drop_index("ix_production_batch_events_batch_stage_log_id", table_name="production_batch_events")
    op.drop_index("ix_production_batch_events_workspace_id", table_name="production_batch_events")
    op.drop_index("ix_production_batch_events_batch_id", table_name="production_batch_events")
    op.drop_table("production_batch_events")
