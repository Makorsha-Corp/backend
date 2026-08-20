"""Add profiles.is_platform_admin for Makorsha staff.

Revision ID: 115_platform_admin
Revises: 114_attachment_markups
Create Date: 2026-08-20
"""
import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import column_exists

revision = "115_platform_admin"
down_revision = "114_attachment_markups"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if column_exists("profiles", "is_platform_admin"):
        return

    op.add_column(
        "profiles",
        sa.Column(
            "is_platform_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    if not column_exists("profiles", "is_platform_admin"):
        return

    op.drop_column("profiles", "is_platform_admin")
