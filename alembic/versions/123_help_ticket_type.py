"""Add type column to help_tickets (support|feedback discriminator).

Revision ID: 123_help_ticket_type
Revises: 122_sales_order_decimal_quantities
Create Date: 2026-09-21
"""
import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import add_column_if_not_exists, drop_column_if_exists

revision = "123_help_ticket_type"
down_revision = "122_sales_order_decimal_quantities"
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_column_if_not_exists(
        "help_tickets",
        sa.Column("type", sa.String(16), nullable=False, server_default="support"),
    )
    op.create_index(
        "ix_help_tickets_type",
        "help_tickets",
        ["type"],
        unique=False,
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("ix_help_tickets_type", table_name="help_tickets", if_exists=True)
    drop_column_if_exists("help_tickets", "type")
