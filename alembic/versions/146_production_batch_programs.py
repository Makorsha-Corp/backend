"""Production batch programs and batch program_id.

Revision ID: 146_production_batch_programs
Revises: 145_stage_log_planned_start_at
Create Date: 2026-10-25
"""
import sqlalchemy as sa
from alembic import op

revision = "146_production_batch_programs"
down_revision = "145_stage_log_planned_start_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "production_batch_programs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("factory_id", sa.Integer(), nullable=False),
        sa.Column("formula_id", sa.Integer(), nullable=False),
        sa.Column("first_start_at", sa.DateTime(), nullable=False),
        sa.Column("cadence", sa.String(length=16), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["factory_id"], ["factories.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["formula_id"], ["production_formulas.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["profiles.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_production_batch_programs_workspace_id",
        "production_batch_programs",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        "ix_production_batch_programs_factory_id",
        "production_batch_programs",
        ["factory_id"],
        unique=False,
    )
    op.create_index(
        "ix_production_batch_programs_formula_id",
        "production_batch_programs",
        ["formula_id"],
        unique=False,
    )
    op.create_index(
        "ix_production_batch_programs_status",
        "production_batch_programs",
        ["status"],
        unique=False,
    )
    op.add_column(
        "production_batches",
        sa.Column("program_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_production_batches_program_id",
        "production_batches",
        "production_batch_programs",
        ["program_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_production_batches_program_id",
        "production_batches",
        ["program_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_production_batches_program_id", table_name="production_batches")
    op.drop_constraint(
        "fk_production_batches_program_id",
        "production_batches",
        type_="foreignkey",
    )
    op.drop_column("production_batches", "program_id")
    op.drop_index(
        "ix_production_batch_programs_status",
        table_name="production_batch_programs",
    )
    op.drop_index(
        "ix_production_batch_programs_formula_id",
        table_name="production_batch_programs",
    )
    op.drop_index(
        "ix_production_batch_programs_factory_id",
        table_name="production_batch_programs",
    )
    op.drop_index(
        "ix_production_batch_programs_workspace_id",
        table_name="production_batch_programs",
    )
    op.drop_table("production_batch_programs")
