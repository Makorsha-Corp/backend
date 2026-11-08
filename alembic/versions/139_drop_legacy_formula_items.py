"""Drop legacy production_formula_items and formula.estimated_duration_minutes

Revision ID: 139_drop_legacy_formula_items
Revises: 138_production_batch_machine_id
Create Date: 2026-10-04

"""
from alembic import op
import sqlalchemy as sa


revision = "139_drop_legacy_formula_items"
down_revision = "138_production_batch_machine_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("production_formula_items")
    op.drop_column("production_formulas", "estimated_duration_minutes")


def downgrade() -> None:
    op.add_column(
        "production_formulas",
        sa.Column("estimated_duration_minutes", sa.Integer(), nullable=True),
    )
    op.create_table(
        "production_formula_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("formula_id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("item_role", sa.String(length=20), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=True),
        sa.Column("is_optional", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("tolerance_percentage", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.ForeignKeyConstraint(["formula_id"], ["production_formulas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
