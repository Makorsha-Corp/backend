"""Per-step material quantities for in-batch virtual WIP.

Revision ID: 144_production_batch_stage_log_items
Revises: 143_decimal_production_quantities
Create Date: 2026-10-10
"""
import sqlalchemy as sa
from alembic import op

revision = "144_production_batch_stage_log_items"
down_revision = "143_decimal_production_quantities"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "production_batch_stage_log_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("batch_stage_log_id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("item_role", sa.String(length=20), nullable=False),
        sa.Column("expected_quantity", sa.Numeric(15, 2), nullable=True),
        sa.Column("actual_quantity", sa.Numeric(15, 2), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["batch_id"], ["production_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["batch_stage_log_id"], ["production_batch_stage_logs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "batch_stage_log_id",
            "item_id",
            "item_role",
            name="uq_batch_stage_log_item_role",
        ),
    )
    op.create_index(
        "ix_production_batch_stage_log_items_workspace_id",
        "production_batch_stage_log_items",
        ["workspace_id"],
    )
    op.create_index(
        "ix_production_batch_stage_log_items_batch_id",
        "production_batch_stage_log_items",
        ["batch_id"],
    )
    op.create_index(
        "ix_production_batch_stage_log_items_batch_stage_log_id",
        "production_batch_stage_log_items",
        ["batch_stage_log_id"],
    )
    op.create_index(
        "ix_production_batch_stage_log_items_item_id",
        "production_batch_stage_log_items",
        ["item_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_production_batch_stage_log_items_item_id",
        table_name="production_batch_stage_log_items",
    )
    op.drop_index(
        "ix_production_batch_stage_log_items_batch_stage_log_id",
        table_name="production_batch_stage_log_items",
    )
    op.drop_index(
        "ix_production_batch_stage_log_items_batch_id",
        table_name="production_batch_stage_log_items",
    )
    op.drop_index(
        "ix_production_batch_stage_log_items_workspace_id",
        table_name="production_batch_stage_log_items",
    )
    op.drop_table("production_batch_stage_log_items")
