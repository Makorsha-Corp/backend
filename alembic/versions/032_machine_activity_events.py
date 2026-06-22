"""Add machine_activity_events table.

Revision ID: 032_machine_activity_events
Revises: 031_add_discussions_notifications
"""

import sqlalchemy as sa
from alembic import op

revision = "032_machine_activity_events"
down_revision = "031_add_discussions_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "machine_activity_events" in inspector.get_table_names():
        return

    op.create_table(
        "machine_activity_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("machine_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("performed_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["machine_id"], ["machines.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["performed_by"], ["profiles.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_machine_activity_events_workspace_id",
        "machine_activity_events",
        ["workspace_id"],
    )
    op.create_index(
        "ix_machine_activity_events_machine_id",
        "machine_activity_events",
        ["machine_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "machine_activity_events" not in inspector.get_table_names():
        return

    op.drop_index("ix_machine_activity_events_machine_id", table_name="machine_activity_events")
    op.drop_index("ix_machine_activity_events_workspace_id", table_name="machine_activity_events")
    op.drop_table("machine_activity_events")
