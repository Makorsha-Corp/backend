"""Add page_count column to attachments (PDF page total from Cloudinary).

Revision ID: 108_attachment_page_count
Revises: 107_audit_timestamptz
Create Date: 2026-08-13
"""
import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import add_column_if_not_exists, drop_column_if_exists

revision = "108_attachment_page_count"
down_revision = "107_audit_timestamptz"
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_column_if_not_exists(
        "attachments",
        sa.Column("page_count", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    drop_column_if_exists("attachments", "page_count")
