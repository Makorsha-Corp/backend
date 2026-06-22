"""Drop machine_events table.

Revision ID: 033_drop_machine_events
Revises: 032_machine_activity_events
"""

import sqlalchemy as sa
from alembic import op

revision = "033_drop_machine_events"
down_revision = "032_machine_activity_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "machine_events" not in inspector.get_table_names():
        return
    op.drop_table("machine_events")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "machine_events" in inspector.get_table_names():
        return

    op.create_table(
        "machine_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("machine_id", sa.Integer(), nullable=False),
        sa.Column(
            "event_type",
            sa.Enum("IDLE", "RUNNING", "OFF", "MAINTENANCE", name="machineeventtypeenum"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("initiated_by", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["profiles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["initiated_by"], ["profiles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["machine_id"], ["machines.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_machine_events_id"), "machine_events", ["id"], unique=False)
