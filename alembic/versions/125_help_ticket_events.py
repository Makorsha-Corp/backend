"""Help ticket activity events table.

Revision ID: 125_help_ticket_events
Revises: 124_help_ticket_status
Create Date: 2026-09-27
"""
import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import table_exists

revision = "125_help_ticket_events"
down_revision = "124_help_ticket_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if table_exists("help_ticket_events"):
        return
    op.create_table(
        "help_ticket_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("help_ticket_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("performed_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["help_ticket_id"], ["help_tickets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["performed_by"], ["profiles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_help_ticket_events_help_ticket_id",
        "help_ticket_events",
        ["help_ticket_id"],
        unique=False,
    )
    op.create_index(
        "ix_help_ticket_events_workspace_id",
        "help_ticket_events",
        ["workspace_id"],
        unique=False,
    )


def downgrade() -> None:
    if not table_exists("help_ticket_events"):
        return
    op.drop_index("ix_help_ticket_events_workspace_id", table_name="help_ticket_events")
    op.drop_index("ix_help_ticket_events_help_ticket_id", table_name="help_ticket_events")
    op.drop_table("help_ticket_events")
