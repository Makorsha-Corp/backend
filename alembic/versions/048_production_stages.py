"""Add production formula stages and batch stage logs.

Revision ID: 048_production_stages
Revises: 047_item_name_normalized
"""

import sqlalchemy as sa
from alembic import op

revision = "048_production_stages"
down_revision = "047_item_name_normalized"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "production_formula_stages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("formula_id", sa.Integer(), nullable=False),
        sa.Column("stage_order", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("production_line_id", sa.Integer(), nullable=True),
        sa.Column("machine_id", sa.Integer(), nullable=True),
        sa.Column("expected_duration_minutes", sa.Integer(), nullable=True),
        sa.Column("expected_output_quantity", sa.Integer(), nullable=True),
        sa.Column("expected_output_item_id", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["formula_id"], ["production_formulas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["production_line_id"], ["production_lines.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["machine_id"], ["machines.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["expected_output_item_id"], ["items.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("formula_id", "stage_order", name="uq_formula_stage_order"),
    )
    op.create_index(
        "ix_production_formula_stages_workspace_id",
        "production_formula_stages",
        ["workspace_id"],
    )
    op.create_index(
        "ix_production_formula_stages_formula_id",
        "production_formula_stages",
        ["formula_id"],
    )

    op.create_table(
        "production_batch_stage_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("formula_stage_id", sa.Integer(), nullable=True),
        sa.Column("stage_name", sa.String(length=200), nullable=False),
        sa.Column("stage_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("production_line_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("logged_by", sa.Integer(), nullable=True),
        sa.Column("input_quantity", sa.Integer(), nullable=True),
        sa.Column("output_quantity", sa.Integer(), nullable=True),
        sa.Column("waste_quantity", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["batch_id"], ["production_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["formula_stage_id"], ["production_formula_stages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["production_line_id"], ["production_lines.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["logged_by"], ["profiles.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_production_batch_stage_logs_workspace_id",
        "production_batch_stage_logs",
        ["workspace_id"],
    )
    op.create_index(
        "ix_production_batch_stage_logs_batch_id",
        "production_batch_stage_logs",
        ["batch_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_production_batch_stage_logs_batch_id", table_name="production_batch_stage_logs")
    op.drop_index("ix_production_batch_stage_logs_workspace_id", table_name="production_batch_stage_logs")
    op.drop_table("production_batch_stage_logs")
    op.drop_index("ix_production_formula_stages_formula_id", table_name="production_formula_stages")
    op.drop_index("ix_production_formula_stages_workspace_id", table_name="production_formula_stages")
    op.drop_table("production_formula_stages")
