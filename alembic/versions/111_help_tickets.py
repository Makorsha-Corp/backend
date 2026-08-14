"""Add help_tickets table for workspace support requests.

Revision ID: 111_help_tickets
Revises: 110_attachment_ledger
Create Date: 2026-08-13
"""
import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import table_exists

revision = "111_help_tickets"
down_revision = "110_attachment_ledger"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if table_exists("help_tickets"):
        return

    op.create_table(
        "help_tickets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("ticket_number", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["profiles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["closed_by"], ["profiles.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "ticket_number", name="uq_help_tickets_workspace_number"),
    )
    op.create_index("ix_help_tickets_workspace_id", "help_tickets", ["workspace_id"])
    op.create_index("ix_help_tickets_ticket_number", "help_tickets", ["ticket_number"])
    op.create_index("ix_help_tickets_status", "help_tickets", ["status"])
    op.create_index("ix_help_tickets_created_by", "help_tickets", ["created_by"])


def downgrade() -> None:
    if not table_exists("help_tickets"):
        return
    op.drop_index("ix_help_tickets_created_by", table_name="help_tickets")
    op.drop_index("ix_help_tickets_status", table_name="help_tickets")
    op.drop_index("ix_help_tickets_ticket_number", table_name="help_tickets")
    op.drop_index("ix_help_tickets_workspace_id", table_name="help_tickets")
    op.drop_table("help_tickets")
