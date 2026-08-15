"""Merge SO completion-codes branch with attachments/help-tickets branch.

Revision ID: 112_merge_heads
Revises: 106_completion_codes, 111_help_tickets
Create Date: 2026-08-15
"""
revision = "112_merge_heads"
down_revision = ("106_completion_codes", "111_help_tickets")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
