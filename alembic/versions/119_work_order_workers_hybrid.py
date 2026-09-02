"""Hybrid work order assignees/completers + completed_by_names."""
import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import add_column_if_not_exists, drop_column_if_exists

revision = "119_work_order_workers_hybrid"
down_revision = "118_strip_markup_event_stroke_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_column_if_not_exists(
        "work_orders",
        sa.Column("completed_by_names", sa.String(255), nullable=True),
    )

    op.create_table(
        "work_order_assignees",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("work_order_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("work_order_id", "user_id", name="uq_wo_assignee_wo_user"),
    )
    op.create_index("ix_work_order_assignees_workspace_id", "work_order_assignees", ["workspace_id"])
    op.create_index("ix_work_order_assignees_work_order_id", "work_order_assignees", ["work_order_id"])
    op.create_index("ix_work_order_assignees_user_id", "work_order_assignees", ["user_id"])

    op.create_table(
        "work_order_completers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("work_order_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("work_order_id", "user_id", name="uq_wo_completer_wo_user"),
    )
    op.create_index("ix_work_order_completers_workspace_id", "work_order_completers", ["workspace_id"])
    op.create_index("ix_work_order_completers_work_order_id", "work_order_completers", ["work_order_id"])
    op.create_index("ix_work_order_completers_user_id", "work_order_completers", ["user_id"])

    # Backfill completers from legacy single completed_by FK.
    op.execute(
        """
        INSERT INTO work_order_completers (workspace_id, work_order_id, user_id)
        SELECT wo.workspace_id, wo.id, wo.completed_by
        FROM work_orders wo
        WHERE wo.completed_by IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM work_order_completers c
            WHERE c.work_order_id = wo.id AND c.user_id = wo.completed_by
          )
        """
    )
    op.execute(
        """
        UPDATE work_orders wo
        SET completed_by_names = p.name
        FROM profiles p
        WHERE wo.completed_by = p.id
          AND wo.completed_by_names IS NULL
          AND p.name IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_work_order_completers_user_id", table_name="work_order_completers")
    op.drop_index("ix_work_order_completers_work_order_id", table_name="work_order_completers")
    op.drop_index("ix_work_order_completers_workspace_id", table_name="work_order_completers")
    op.drop_table("work_order_completers")

    op.drop_index("ix_work_order_assignees_user_id", table_name="work_order_assignees")
    op.drop_index("ix_work_order_assignees_work_order_id", table_name="work_order_assignees")
    op.drop_index("ix_work_order_assignees_workspace_id", table_name="work_order_assignees")
    op.drop_table("work_order_assignees")

    drop_column_if_exists("work_orders", "completed_by_names")
