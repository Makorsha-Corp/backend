"""Production launch: routes, step logs, schedule, order links.

Revision ID: 127_production_launch
Revises: 126_help_ticket_event_timestamp_fix
Create Date: 2026-09-27
"""
import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import column_exists, table_exists

revision = "127_production_launch"
down_revision = "126_help_ticket_event_timestamp_fix"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not table_exists("production_routes"):
        op.create_table(
            "production_routes",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("workspace_id", sa.Integer(), nullable=False),
            sa.Column("factory_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("updated_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["created_by"], ["profiles.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["factory_id"], ["factories.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["updated_by"], ["profiles.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_production_routes_workspace_id", "production_routes", ["workspace_id"])
        op.create_index("ix_production_routes_factory_id", "production_routes", ["factory_id"])

    if not table_exists("production_route_steps"):
        op.create_table(
            "production_route_steps",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("workspace_id", sa.Integer(), nullable=False),
            sa.Column("route_id", sa.Integer(), nullable=False),
            sa.Column("step_order", sa.Integer(), nullable=False),
            sa.Column("production_line_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["production_line_id"], ["production_lines.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["route_id"], ["production_routes.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("route_id", "step_order", name="uq_route_step_order"),
        )
        op.create_index("ix_production_route_steps_workspace_id", "production_route_steps", ["workspace_id"])
        op.create_index("ix_production_route_steps_route_id", "production_route_steps", ["route_id"])
        op.create_index(
            "ix_production_route_steps_production_line_id",
            "production_route_steps",
            ["production_line_id"],
        )

    _add_column(
        "production_formulas",
        sa.Column("route_id", sa.Integer(), nullable=True),
    )
    if column_exists("production_formulas", "route_id") and not _fk_exists(
        "production_formulas", "fk_production_formulas_route_id"
    ):
        op.create_foreign_key(
            "fk_production_formulas_route_id",
            "production_formulas",
            "production_routes",
            ["route_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index("ix_production_formulas_route_id", "production_formulas", ["route_id"])

    _add_column(
        "production_formula_stages",
        sa.Column("route_step_id", sa.Integer(), nullable=True),
    )
    if column_exists("production_formula_stages", "route_step_id") and not _fk_exists(
        "production_formula_stages", "fk_production_formula_stages_route_step_id"
    ):
        op.create_foreign_key(
            "fk_production_formula_stages_route_step_id",
            "production_formula_stages",
            "production_route_steps",
            ["route_step_id"],
            ["id"],
            ondelete="CASCADE",
        )
        op.create_index(
            "ix_production_formula_stages_route_step_id",
            "production_formula_stages",
            ["route_step_id"],
        )
        op.create_unique_constraint(
            "uq_formula_stage_route_step",
            "production_formula_stages",
            ["formula_id", "route_step_id"],
        )

    _add_column("production_batches", sa.Column("route_id", sa.Integer(), nullable=True))
    _add_column("production_batches", sa.Column("planned_start_at", sa.DateTime(), nullable=True))
    _add_column("production_batches", sa.Column("sales_order_item_id", sa.Integer(), nullable=True))
    if column_exists("production_batches", "route_id") and not _fk_exists(
        "production_batches", "fk_production_batches_route_id"
    ):
        op.create_foreign_key(
            "fk_production_batches_route_id",
            "production_batches",
            "production_routes",
            ["route_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index("ix_production_batches_route_id", "production_batches", ["route_id"])
    if column_exists("production_batches", "sales_order_item_id") and not _fk_exists(
        "production_batches", "fk_production_batches_sales_order_item_id"
    ):
        op.create_foreign_key(
            "fk_production_batches_sales_order_item_id",
            "production_batches",
            "sales_order_items",
            ["sales_order_item_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index(
            "ix_production_batches_sales_order_item_id",
            "production_batches",
            ["sales_order_item_id"],
        )

    _add_column("production_batch_stage_logs", sa.Column("route_step_id", sa.Integer(), nullable=True))
    _add_column("production_batch_stage_logs", sa.Column("machine_id", sa.Integer(), nullable=True))
    _add_column(
        "production_batch_stage_logs",
        sa.Column("expected_duration_minutes", sa.Integer(), nullable=True),
    )
    _add_column(
        "production_batch_stage_logs",
        sa.Column("expected_output_quantity", sa.Integer(), nullable=True),
    )
    _add_column("production_batch_stage_logs", sa.Column("rework_quantity", sa.Integer(), nullable=True))
    _add_column("production_batch_stage_logs", sa.Column("rework_of_log_id", sa.Integer(), nullable=True))
    if column_exists("production_batch_stage_logs", "route_step_id") and not _fk_exists(
        "production_batch_stage_logs", "fk_stage_logs_route_step_id"
    ):
        op.create_foreign_key(
            "fk_stage_logs_route_step_id",
            "production_batch_stage_logs",
            "production_route_steps",
            ["route_step_id"],
            ["id"],
            ondelete="SET NULL",
        )
    if column_exists("production_batch_stage_logs", "machine_id") and not _fk_exists(
        "production_batch_stage_logs", "fk_stage_logs_machine_id"
    ):
        op.create_foreign_key(
            "fk_stage_logs_machine_id",
            "production_batch_stage_logs",
            "machines",
            ["machine_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index("ix_stage_logs_machine_id", "production_batch_stage_logs", ["machine_id"])
    if column_exists("production_batch_stage_logs", "rework_of_log_id") and not _fk_exists(
        "production_batch_stage_logs", "fk_stage_logs_rework_of_log_id"
    ):
        op.create_foreign_key(
            "fk_stage_logs_rework_of_log_id",
            "production_batch_stage_logs",
            "production_batch_stage_logs",
            ["rework_of_log_id"],
            ["id"],
            ondelete="SET NULL",
        )

    _add_column("expense_orders", sa.Column("production_batch_id", sa.Integer(), nullable=True))
    if column_exists("expense_orders", "production_batch_id") and not _fk_exists(
        "expense_orders", "fk_expense_orders_production_batch_id"
    ):
        op.create_foreign_key(
            "fk_expense_orders_production_batch_id",
            "expense_orders",
            "production_batches",
            ["production_batch_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index(
            "ix_expense_orders_production_batch_id",
            "expense_orders",
            ["production_batch_id"],
        )

    _add_column("purchase_orders", sa.Column("production_batch_id", sa.Integer(), nullable=True))
    if column_exists("purchase_orders", "production_batch_id") and not _fk_exists(
        "purchase_orders", "fk_purchase_orders_production_batch_id"
    ):
        op.create_foreign_key(
            "fk_purchase_orders_production_batch_id",
            "purchase_orders",
            "production_batches",
            ["production_batch_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index(
            "ix_purchase_orders_production_batch_id",
            "purchase_orders",
            ["production_batch_id"],
        )


def _add_column(table: str, column: sa.Column) -> None:
    if column_exists(table, column.name):
        return
    op.add_column(table, column)


def _fk_exists(table: str, name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return any(fk.get("name") == name for fk in insp.get_foreign_keys(table))


def downgrade() -> None:
    if column_exists("purchase_orders", "production_batch_id"):
        op.drop_index("ix_purchase_orders_production_batch_id", table_name="purchase_orders")
        op.drop_constraint("fk_purchase_orders_production_batch_id", "purchase_orders", type_="foreignkey")
        op.drop_column("purchase_orders", "production_batch_id")
    if column_exists("expense_orders", "production_batch_id"):
        op.drop_index("ix_expense_orders_production_batch_id", table_name="expense_orders")
        op.drop_constraint("fk_expense_orders_production_batch_id", "expense_orders", type_="foreignkey")
        op.drop_column("expense_orders", "production_batch_id")
    if table_exists("production_route_steps"):
        op.drop_table("production_route_steps")
    if table_exists("production_routes"):
        op.drop_table("production_routes")
