"""Add name/company fields and follow-up status to waitlist_signups.

Revision ID: 103_waitlist_signup_fields
Revises: 102_so_approval_workflow
Create Date: 2026-08-08
"""
import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import add_column_if_not_exists, drop_column_if_exists

revision = "103_waitlist_signup_fields"
down_revision = "102_so_approval_workflow"
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_column_if_not_exists("waitlist_signups", sa.Column("first_name", sa.String(length=100), nullable=True))
    add_column_if_not_exists("waitlist_signups", sa.Column("last_name", sa.String(length=100), nullable=True))
    add_column_if_not_exists("waitlist_signups", sa.Column("company_name", sa.String(length=200), nullable=True))
    add_column_if_not_exists(
        "waitlist_signups",
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
    )
    op.create_index(
        "ix_waitlist_signups_status", "waitlist_signups", ["status"], unique=False, if_not_exists=True
    )


def downgrade() -> None:
    op.drop_index("ix_waitlist_signups_status", table_name="waitlist_signups", if_exists=True)
    drop_column_if_exists("waitlist_signups", "status")
    drop_column_if_exists("waitlist_signups", "company_name")
    drop_column_if_exists("waitlist_signups", "last_name")
    drop_column_if_exists("waitlist_signups", "first_name")
