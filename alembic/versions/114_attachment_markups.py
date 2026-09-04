"""Add attachment_markups overlay layers.

Revision ID: 114_attachment_markups
Revises: 113_heal_machine_tables
Create Date: 2026-08-20
"""
import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import table_exists

revision = "114_attachment_markups"
down_revision = "113_heal_machine_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if table_exists("attachment_markups"):
        return

    op.create_table(
        "attachment_markups",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("attachment_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["attachment_id"], ["attachments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("attachment_id", "user_id", name="uq_attachment_markup_user"),
    )
    op.create_index("ix_attachment_markups_workspace_id", "attachment_markups", ["workspace_id"])
    op.create_index("ix_attachment_markups_attachment_id", "attachment_markups", ["attachment_id"])
    op.create_index("ix_attachment_markups_user_id", "attachment_markups", ["user_id"])


def downgrade() -> None:
    if table_exists("attachment_markups"):
        op.drop_table("attachment_markups")
