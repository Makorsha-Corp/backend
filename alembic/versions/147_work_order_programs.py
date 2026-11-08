"""Work order programs and work_orders.program_id.

Revision ID: 147_work_order_programs
Revises: 146_production_batch_programs
Create Date: 2026-10-26
"""
import sqlalchemy as sa
from alembic import op

revision = "147_work_order_programs"
down_revision = "146_production_batch_programs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "work_order_programs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("factory_id", sa.Integer(), nullable=False),
        sa.Column("machine_id", sa.Integer(), nullable=False),
        sa.Column("work_order_type_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("work_order_template_id", sa.Integer(), nullable=True),
        sa.Column("cadence", sa.String(length=16), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["factory_id"], ["factories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["machine_id"], ["machines.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["work_order_type_id"], ["work_order_types.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["work_order_template_id"], ["work_order_templates.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["profiles.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_work_order_programs_workspace_id",
        "work_order_programs",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        "ix_work_order_programs_factory_id",
        "work_order_programs",
        ["factory_id"],
        unique=False,
    )
    op.create_index(
        "ix_work_order_programs_machine_id",
        "work_order_programs",
        ["machine_id"],
        unique=False,
    )
    op.create_index(
        "ix_work_order_programs_status",
        "work_order_programs",
        ["status"],
        unique=False,
    )
    op.add_column(
        "work_orders",
        sa.Column("program_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_work_orders_program_id",
        "work_orders",
        "work_order_programs",
        ["program_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_work_orders_program_id",
        "work_orders",
        ["program_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_work_orders_program_id", table_name="work_orders")
    op.drop_constraint("fk_work_orders_program_id", "work_orders", type_="foreignkey")
    op.drop_column("work_orders", "program_id")
    op.drop_index("ix_work_order_programs_status", table_name="work_order_programs")
    op.drop_index("ix_work_order_programs_machine_id", table_name="work_order_programs")
    op.drop_index("ix_work_order_programs_factory_id", table_name="work_order_programs")
    op.drop_index("ix_work_order_programs_workspace_id", table_name="work_order_programs")
    op.drop_table("work_order_programs")
