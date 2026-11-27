"""Help ticket status: pending | opened | closed (replace open).

Revision ID: 124_help_ticket_status
Revises: 123_help_ticket_type, 123_landing_perf_reports
Create Date: 2026-09-22
"""
import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import table_exists

revision = "124_help_ticket_status"
down_revision = ("123_help_ticket_type", "123_landing_perf_reports")
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not table_exists("help_tickets"):
        return
    op.execute(
        sa.text("UPDATE help_tickets SET status = 'opened' WHERE status = 'open'")
    )
    op.alter_column(
        "help_tickets",
        "status",
        existing_type=sa.String(length=16),
        server_default="pending",
        existing_nullable=False,
    )


def downgrade() -> None:
    if not table_exists("help_tickets"):
        return
    op.execute(
        sa.text("UPDATE help_tickets SET status = 'open' WHERE status = 'opened'")
    )
    op.alter_column(
        "help_tickets",
        "status",
        existing_type=sa.String(length=16),
        server_default="open",
        existing_nullable=False,
    )
