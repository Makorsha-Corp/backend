"""Rename production batch status planned -> recurring.

Revision ID: 151_batch_recurring_status
Revises: 150_batch_program_interval
Create Date: 2026-11-02
"""
from alembic import op

revision = "151_batch_recurring_status"
down_revision = "150_batch_program_interval"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE production_batches
        SET status = 'recurring'
        WHERE status = 'planned'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE production_batches
        SET status = 'planned'
        WHERE status = 'recurring'
        """
    )
