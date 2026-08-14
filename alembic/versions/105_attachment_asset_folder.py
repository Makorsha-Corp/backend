"""Add asset_folder column to attachments.

Revision ID: 105_attachment_asset_folder
Revises: 104_attachments_cloudinary
Create Date: 2026-08-10
"""
import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import add_column_if_not_exists, drop_column_if_exists

revision = "105_attachment_asset_folder"
down_revision = "104_attachments_cloudinary"
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_column_if_not_exists(
        "attachments",
        sa.Column("asset_folder", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    drop_column_if_exists("attachments", "asset_folder")
