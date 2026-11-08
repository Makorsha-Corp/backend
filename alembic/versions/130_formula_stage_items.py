"""Per-stage formula BOM items.

Revision ID: 130_formula_stage_items
Revises: 129_route_step_machine
Create Date: 2026-09-27
"""
import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import table_exists

revision = "130_formula_stage_items"
down_revision = "129_route_step_machine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if table_exists("production_formula_stage_items"):
        return
    op.create_table(
        "production_formula_stage_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("formula_stage_id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("item_role", sa.String(length=20), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=True),
        sa.Column("is_optional", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("tolerance_percentage", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["formula_stage_id"], ["production_formula_stages.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "formula_stage_id",
            "item_id",
            "item_role",
            name="uq_formula_stage_item_role",
        ),
    )
    op.create_index(
        "ix_production_formula_stage_items_workspace_id",
        "production_formula_stage_items",
        ["workspace_id"],
    )
    op.create_index(
        "ix_production_formula_stage_items_formula_stage_id",
        "production_formula_stage_items",
        ["formula_stage_id"],
    )
    op.create_index(
        "ix_production_formula_stage_items_item_id",
        "production_formula_stage_items",
        ["item_id"],
    )
    op.create_index(
        "ix_production_formula_stage_items_item_role",
        "production_formula_stage_items",
        ["item_role"],
    )


def downgrade() -> None:
    if table_exists("production_formula_stage_items"):
        op.drop_table("production_formula_stage_items")
