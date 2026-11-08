"""Step conditions on formula stages and batch stage logs.

Revision ID: 135_formula_and_batch_stage_parameters
Revises: 134_items_waste_byproduct_tags
"""
import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import table_exists

revision = "135_formula_and_batch_stage_parameters"
down_revision = "134_items_waste_byproduct_tags"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not table_exists("production_formula_stage_parameters"):
        op.create_table(
            "production_formula_stage_parameters",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("workspace_id", sa.Integer(), nullable=False),
            sa.Column("formula_stage_id", sa.Integer(), nullable=False),
            sa.Column("label", sa.String(length=120), nullable=False),
            sa.Column("planned_value", sa.Text(), nullable=False),
            sa.Column("planned_value_numeric", sa.Numeric(precision=18, scale=6), nullable=True),
            sa.Column("unit", sa.String(length=40), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["formula_stage_id"], ["production_formula_stages.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_production_formula_stage_parameters_workspace_id",
            "production_formula_stage_parameters",
            ["workspace_id"],
        )
        op.create_index(
            "ix_production_formula_stage_parameters_formula_stage_id",
            "production_formula_stage_parameters",
            ["formula_stage_id"],
        )

    if not table_exists("production_batch_stage_parameters"):
        op.create_table(
            "production_batch_stage_parameters",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("workspace_id", sa.Integer(), nullable=False),
            sa.Column("batch_id", sa.Integer(), nullable=False),
            sa.Column("batch_stage_log_id", sa.Integer(), nullable=False),
            sa.Column("label", sa.String(length=120), nullable=False),
            sa.Column("planned_value", sa.Text(), nullable=False),
            sa.Column("planned_value_numeric", sa.Numeric(precision=18, scale=6), nullable=True),
            sa.Column("actual_value", sa.Text(), nullable=True),
            sa.Column("actual_value_numeric", sa.Numeric(precision=18, scale=6), nullable=True),
            sa.Column("unit", sa.String(length=40), nullable=True),
            sa.Column("source_parameter_id", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["batch_id"], ["production_batches.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["batch_stage_log_id"], ["production_batch_stage_logs.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["source_parameter_id"],
                ["production_formula_stage_parameters.id"],
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_production_batch_stage_parameters_workspace_id",
            "production_batch_stage_parameters",
            ["workspace_id"],
        )
        op.create_index(
            "ix_production_batch_stage_parameters_batch_id",
            "production_batch_stage_parameters",
            ["batch_id"],
        )
        op.create_index(
            "ix_production_batch_stage_parameters_batch_stage_log_id",
            "production_batch_stage_parameters",
            ["batch_stage_log_id"],
        )


def downgrade() -> None:
    if table_exists("production_batch_stage_parameters"):
        op.drop_table("production_batch_stage_parameters")
    if table_exists("production_formula_stage_parameters"):
        op.drop_table("production_formula_stage_parameters")
