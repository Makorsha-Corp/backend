"""Workspace shift windows and batch shift_id.

Revision ID: 136_workspace_shifts_and_batch_shift_id
Revises: 135_formula_and_batch_stage_parameters
"""
import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import table_exists

revision = "136_workspace_shifts_and_batch_shift_id"
down_revision = "135_formula_and_batch_stage_parameters"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not table_exists("workspace_shifts"):
        op.create_table(
            "workspace_shifts",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("workspace_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=80), nullable=False),
            sa.Column("start_time", sa.Time(), nullable=False),
            sa.Column("end_time", sa.Time(), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("updated_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by"], ["profiles.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["updated_by"], ["profiles.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_workspace_shifts_workspace_id", "workspace_shifts", ["workspace_id"])

    if table_exists("production_batches") and table_exists("workspace_shifts"):
        bind = op.get_bind()
        insp = sa.inspect(bind)
        cols = {c["name"] for c in insp.get_columns("production_batches")}
        if "shift_id" not in cols:
            op.add_column(
                "production_batches",
                sa.Column("shift_id", sa.Integer(), nullable=True),
            )
            op.create_foreign_key(
                "fk_production_batches_shift_id",
                "production_batches",
                "workspace_shifts",
                ["shift_id"],
                ["id"],
                ondelete="SET NULL",
            )
            op.create_index("ix_production_batches_shift_id", "production_batches", ["shift_id"])


def downgrade() -> None:
    if table_exists("production_batches"):
        cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("production_batches")}
        if "shift_id" in cols:
            op.drop_index("ix_production_batches_shift_id", table_name="production_batches")
            op.drop_constraint("fk_production_batches_shift_id", "production_batches", type_="foreignkey")
            op.drop_column("production_batches", "shift_id")
    if table_exists("workspace_shifts"):
        op.drop_index("ix_workspace_shifts_workspace_id", table_name="workspace_shifts")
        op.drop_table("workspace_shifts")
