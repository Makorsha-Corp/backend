"""Production line machine membership (stations with many machines).

Revision ID: 128_production_line_machines
Revises: 127_production_launch
Create Date: 2026-09-27
"""
import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import table_exists

revision = "128_production_line_machines"
down_revision = "127_production_launch"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not table_exists("production_line_machines"):
        op.create_table(
            "production_line_machines",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("workspace_id", sa.Integer(), nullable=False),
            sa.Column("production_line_id", sa.Integer(), nullable=False),
            sa.Column("machine_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["machine_id"], ["machines.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["production_line_id"], ["production_lines.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("production_line_id", "machine_id", name="uq_production_line_machine"),
        )
        op.create_index(
            "ix_production_line_machines_workspace_id",
            "production_line_machines",
            ["workspace_id"],
        )
        op.create_index(
            "ix_production_line_machines_production_line_id",
            "production_line_machines",
            ["production_line_id"],
        )
        op.create_index(
            "ix_production_line_machines_machine_id",
            "production_line_machines",
            ["machine_id"],
        )

        op.execute(
            """
            INSERT INTO production_line_machines (workspace_id, production_line_id, machine_id)
            SELECT workspace_id, id, machine_id
            FROM production_lines
            WHERE machine_id IS NOT NULL
            """
        )


def downgrade() -> None:
    if table_exists("production_line_machines"):
        op.drop_index("ix_production_line_machines_machine_id", table_name="production_line_machines")
        op.drop_index("ix_production_line_machines_production_line_id", table_name="production_line_machines")
        op.drop_index("ix_production_line_machines_workspace_id", table_name="production_line_machines")
        op.drop_table("production_line_machines")
