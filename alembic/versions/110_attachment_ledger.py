"""Add attachment_ledger immutable audit trail.

Revision ID: 110_attachment_ledger
Revises: 109_mobile_upload_sessions
Create Date: 2026-08-13
"""
import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import table_exists

revision = "110_attachment_ledger"
down_revision = "109_mobile_upload_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if table_exists("attachment_ledger"):
        return

    op.create_table(
        "attachment_ledger",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("attachment_id", sa.Integer(), nullable=False),
        sa.Column("transaction_type", sa.String(length=16), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("performed_by", sa.Integer(), nullable=True),
        sa.Column("performed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["attachment_id"], ["attachments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["performed_by"], ["profiles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_attachment_ledger_workspace_id", "attachment_ledger", ["workspace_id"])
    op.create_index("ix_attachment_ledger_attachment_id", "attachment_ledger", ["attachment_id"])
    op.create_index("ix_attachment_ledger_transaction_type", "attachment_ledger", ["transaction_type"])
    op.create_index("ix_attachment_ledger_entity_type", "attachment_ledger", ["entity_type"])
    op.create_index("ix_attachment_ledger_entity_id", "attachment_ledger", ["entity_id"])
    op.create_index("ix_attachment_ledger_performed_by", "attachment_ledger", ["performed_by"])
    op.create_index("ix_attachment_ledger_performed_at", "attachment_ledger", ["performed_at"])
    op.create_index(
        "ix_attachment_ledger_workspace_performed_at",
        "attachment_ledger",
        ["workspace_id", "performed_at"],
    )


def downgrade() -> None:
    if table_exists("attachment_ledger"):
        op.drop_table("attachment_ledger")
