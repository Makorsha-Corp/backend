"""Add profiles.timezone for per-user datetime display preference.

Revision ID: 106_profile_timezone
Revises: 105_attachment_asset_folder
Create Date: 2026-08-11
"""
import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import add_column_if_not_exists, drop_column_if_exists

revision = "106_profile_timezone"
down_revision = "105_attachment_asset_folder"
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_column_if_not_exists(
        "profiles",
        sa.Column("timezone", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    drop_column_if_exists("profiles", "timezone")
