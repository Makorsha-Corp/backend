"""Add attachment_markup_events audit log.

Revision ID: 117_attachment_markup_events
Revises: 116_profile_saved_stamp
Create Date: 2026-08-30
"""
import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import table_exists

revision = "117_attachment_markup_events"
down_revision = "116_profile_saved_stamp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if table_exists("attachment_markup_events"):
        return

    op.create_table(
        "attachment_markup_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("attachment_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["attachment_id"], ["attachments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_attachment_markup_events_workspace_id",
        "attachment_markup_events",
        ["workspace_id"],
    )
    op.create_index(
        "ix_attachment_markup_events_attachment_id",
        "attachment_markup_events",
        ["attachment_id"],
    )
    op.create_index(
        "ix_attachment_markup_events_attachment_created",
        "attachment_markup_events",
        ["attachment_id", "created_at"],
    )


def downgrade() -> None:
    if table_exists("attachment_markup_events"):
        op.drop_table("attachment_markup_events")
