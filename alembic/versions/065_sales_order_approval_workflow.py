"""Sales order approval workflow: approvers, events, section-confirm/complete columns.

Revision ID: 065_sales_order_approval_workflow
Revises: 064_merge_sales_delivery_and_work_order_item_soft_delete
Create Date: 2026-08-05
"""
import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import add_column_if_not_exists, drop_column_if_exists, table_exists

revision = "065_sales_order_approval_workflow"
down_revision = "064_merge_sales_delivery_and_work_order_item_soft_delete"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not table_exists("sales_order_approvers"):
        op.create_table(
            "sales_order_approvers",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
            sa.Column("sales_order_id", sa.Integer(), sa.ForeignKey("sales_orders.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
            sa.Column("assigned_by", sa.Integer(), sa.ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True),
            sa.Column("assigned_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("approved", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("approved_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("sales_order_id", "user_id", name="uq_so_approver_so_user"),
        )
        op.create_index("ix_sales_order_approvers_workspace_id", "sales_order_approvers", ["workspace_id"])
        op.create_index("ix_sales_order_approvers_sales_order_id", "sales_order_approvers", ["sales_order_id"])
        op.create_index("ix_sales_order_approvers_user_id", "sales_order_approvers", ["user_id"])

    if not table_exists("sales_order_events"):
        op.create_table(
            "sales_order_events",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
            sa.Column("sales_order_id", sa.Integer(), sa.ForeignKey("sales_orders.id", ondelete="CASCADE"), nullable=False),
            sa.Column("event_type", sa.String(50), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.Column("performed_by", sa.Integer(), sa.ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_sales_order_events_workspace_id", "sales_order_events", ["workspace_id"])
        op.create_index("ix_sales_order_events_sales_order_id", "sales_order_events", ["sales_order_id"])

    add_column_if_not_exists("sales_orders", sa.Column("paid", sa.Boolean(), nullable=False, server_default="false"))
    add_column_if_not_exists("sales_orders", sa.Column("customer_confirmed", sa.Boolean(), nullable=False, server_default="false"))
    add_column_if_not_exists("sales_orders", sa.Column("details_confirmed", sa.Boolean(), nullable=False, server_default="false"))
    add_column_if_not_exists("sales_orders", sa.Column("items_confirmed", sa.Boolean(), nullable=False, server_default="false"))
    add_column_if_not_exists("sales_orders", sa.Column("invoice_confirmed", sa.Boolean(), nullable=False, server_default="false"))
    add_column_if_not_exists("sales_orders", sa.Column("required_approvals", sa.Integer(), nullable=True))
    add_column_if_not_exists("sales_orders", sa.Column("order_completed", sa.Boolean(), nullable=False, server_default="false"))
    add_column_if_not_exists("sales_orders", sa.Column("completed_at", sa.DateTime(), nullable=True))
    add_column_if_not_exists(
        "sales_orders",
        sa.Column("completed_by", sa.Integer(), sa.ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True),
    )


def downgrade() -> None:
    for col in (
        "completed_by", "completed_at", "order_completed", "required_approvals",
        "invoice_confirmed", "items_confirmed", "details_confirmed", "customer_confirmed", "paid",
    ):
        drop_column_if_exists("sales_orders", col)
    if table_exists("sales_order_events"):
        op.drop_table("sales_order_events")
    if table_exists("sales_order_approvers"):
        op.drop_table("sales_order_approvers")
