"""Add mobile_upload_sessions for QR phone-to-desktop handoff.

Revision ID: 109_mobile_upload_sessions
Revises: 108_attachment_page_count
Create Date: 2026-08-13
"""
import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import table_exists

revision = "109_mobile_upload_sessions"
down_revision = "108_attachment_page_count"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if table_exists("mobile_upload_sessions"):
        return

    op.create_table(
        "mobile_upload_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("entity_label", sa.String(length=80), nullable=True),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="waiting"),
        sa.Column("public_id", sa.String(length=512), nullable=True),
        sa.Column("asset_folder", sa.String(length=512), nullable=True),
        sa.Column("resource_type", sa.String(length=16), nullable=True),
        sa.Column("delivery_type", sa.String(length=16), nullable=True, server_default="authenticated"),
        sa.Column("format", sa.String(length=16), nullable=True),
        sa.Column("version", sa.BigInteger(), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("mime_type", sa.String(length=128), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mobile_upload_sessions_token_hash", "mobile_upload_sessions", ["token_hash"], unique=True)
    op.create_index("ix_mobile_upload_sessions_workspace_id", "mobile_upload_sessions", ["workspace_id"])
    op.create_index("ix_mobile_upload_sessions_expires_at", "mobile_upload_sessions", ["expires_at"])
    op.create_index(
        "ix_mobile_upload_sessions_creator_status",
        "mobile_upload_sessions",
        ["workspace_id", "created_by", "status"],
    )


def downgrade() -> None:
    if table_exists("mobile_upload_sessions"):
        op.drop_table("mobile_upload_sessions")
