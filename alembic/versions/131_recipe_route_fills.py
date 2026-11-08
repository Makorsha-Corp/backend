"""Recipe templates remember routes; route steps are station fills.

Revision ID: 131_recipe_route_fills
Revises: 130_formula_stage_items
Create Date: 2026-09-28
"""
import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import column_exists, foreign_key_constraint_exists

revision = "131_recipe_route_fills"
down_revision = "130_formula_stage_items"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not column_exists("production_routes", "formula_id"):
        op.add_column("production_routes", sa.Column("formula_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_production_routes_formula_id",
            "production_routes",
            "production_formulas",
            ["formula_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index("ix_production_routes_formula_id", "production_routes", ["formula_id"])

    if not column_exists("production_route_steps", "formula_stage_id"):
        op.add_column("production_route_steps", sa.Column("formula_stage_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_production_route_steps_formula_stage_id",
            "production_route_steps",
            "production_formula_stages",
            ["formula_stage_id"],
            ["id"],
            ondelete="CASCADE",
        )
        op.create_index(
            "ix_production_route_steps_formula_stage_id",
            "production_route_steps",
            ["formula_stage_id"],
        )
        op.create_unique_constraint(
            "uq_route_step_formula_stage",
            "production_route_steps",
            ["route_id", "formula_stage_id"],
        )

    op.alter_column("production_route_steps", "production_line_id", existing_type=sa.Integer(), nullable=True)

    if foreign_key_constraint_exists("production_formula_stages", "fk_production_formula_stages_route_step_id"):
        op.drop_constraint(
            "fk_production_formula_stages_route_step_id",
            "production_formula_stages",
            type_="foreignkey",
        )
        op.create_foreign_key(
            "fk_production_formula_stages_route_step_id",
            "production_formula_stages",
            "production_route_steps",
            ["route_step_id"],
            ["id"],
            ondelete="SET NULL",
        )

    op.execute(
        """
        UPDATE production_routes AS route
        SET formula_id = picked.id
        FROM (
            SELECT DISTINCT ON (route_id) id, route_id
            FROM production_formulas
            WHERE route_id IS NOT NULL
            ORDER BY route_id, is_active DESC, id ASC
        ) AS picked
        WHERE route.id = picked.route_id
          AND route.formula_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE production_route_steps AS step
        SET formula_stage_id = stage.id
        FROM production_formula_stages AS stage
        WHERE stage.route_step_id = step.id
          AND step.formula_stage_id IS NULL
        """
    )


def downgrade() -> None:
    if foreign_key_constraint_exists("production_formula_stages", "fk_production_formula_stages_route_step_id"):
        op.drop_constraint(
            "fk_production_formula_stages_route_step_id",
            "production_formula_stages",
            type_="foreignkey",
        )
        op.create_foreign_key(
            "fk_production_formula_stages_route_step_id",
            "production_formula_stages",
            "production_route_steps",
            ["route_step_id"],
            ["id"],
            ondelete="CASCADE",
        )
    op.alter_column("production_route_steps", "production_line_id", existing_type=sa.Integer(), nullable=False)
    if column_exists("production_route_steps", "formula_stage_id"):
        op.drop_constraint("uq_route_step_formula_stage", "production_route_steps", type_="unique")
        op.drop_index("ix_production_route_steps_formula_stage_id", table_name="production_route_steps")
        op.drop_constraint(
            "fk_production_route_steps_formula_stage_id",
            "production_route_steps",
            type_="foreignkey",
        )
        op.drop_column("production_route_steps", "formula_stage_id")
    if column_exists("production_routes", "formula_id"):
        op.drop_index("ix_production_routes_formula_id", table_name="production_routes")
        op.drop_constraint("fk_production_routes_formula_id", "production_routes", type_="foreignkey")
        op.drop_column("production_routes", "formula_id")
