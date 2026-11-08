"""Route step optional machine pin.

Revision ID: 129_route_step_machine
Revises: 128_production_line_machines
Create Date: 2026-09-27
"""
import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import column_exists

revision = "129_route_step_machine"
down_revision = "128_production_line_machines"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not column_exists("production_route_steps", "machine_id"):
        op.add_column(
            "production_route_steps",
            sa.Column("machine_id", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            "fk_production_route_steps_machine_id",
            "production_route_steps",
            "machines",
            ["machine_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index(
            "ix_production_route_steps_machine_id",
            "production_route_steps",
            ["machine_id"],
        )


def downgrade() -> None:
    if column_exists("production_route_steps", "machine_id"):
        op.drop_index("ix_production_route_steps_machine_id", table_name="production_route_steps")
        op.drop_constraint("fk_production_route_steps_machine_id", "production_route_steps", type_="foreignkey")
        op.drop_column("production_route_steps", "machine_id")
