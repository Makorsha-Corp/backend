"""Route-first cleanup: routes are line sequences; recipes link by route_step_id.

Revision ID: 132_route_first_cleanup
Revises: 131_recipe_route_fills
"""
import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import (
    column_exists,
    drop_column_if_exists,
    drop_foreign_key_if_exists,
    foreign_key_constraint_exists,
)

revision = "132_route_first_cleanup"
down_revision = "131_recipe_route_fills"
branch_labels = None
depends_on = None


def upgrade() -> None:
    drop_foreign_key_if_exists("production_route_steps", "fk_production_route_steps_machine_id")
    if column_exists("production_route_steps", "machine_id"):
        op.execute("DROP INDEX IF EXISTS ix_production_route_steps_machine_id")
        drop_column_if_exists("production_route_steps", "machine_id")

    drop_foreign_key_if_exists("production_routes", "fk_production_routes_formula_id")
    if column_exists("production_routes", "formula_id"):
        op.execute("DROP INDEX IF EXISTS ix_production_routes_formula_id")
        drop_column_if_exists("production_routes", "formula_id")

    if column_exists("production_route_steps", "formula_stage_id"):
        op.execute("ALTER TABLE production_route_steps DROP CONSTRAINT IF EXISTS uq_route_step_formula_stage")
        op.execute("DROP INDEX IF EXISTS ix_production_route_steps_formula_stage_id")
        drop_foreign_key_if_exists("production_route_steps", "fk_production_route_steps_formula_stage_id")
        drop_column_if_exists("production_route_steps", "formula_stage_id")

    op.execute(
        """
        UPDATE production_route_steps AS step
        SET production_line_id = picked.line_id
        FROM (
            SELECT route.id AS route_id, line.id AS line_id
            FROM production_routes AS route
            JOIN LATERAL (
                SELECT id FROM production_lines
                WHERE factory_id = route.factory_id
                ORDER BY id
                LIMIT 1
            ) AS line ON true
        ) AS picked
        WHERE step.route_id = picked.route_id
          AND step.production_line_id IS NULL
        """
    )
    op.execute("DELETE FROM production_route_steps WHERE production_line_id IS NULL")
    op.alter_column("production_route_steps", "production_line_id", existing_type=sa.Integer(), nullable=False)

    if not column_exists("production_formula_stages", "is_used"):
        op.add_column(
            "production_formula_stages",
            sa.Column("is_used", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        )

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
            ondelete="SET NULL",
        )
    if column_exists("production_formula_stages", "is_used"):
        op.drop_column("production_formula_stages", "is_used")
    op.alter_column("production_route_steps", "production_line_id", existing_type=sa.Integer(), nullable=True)
