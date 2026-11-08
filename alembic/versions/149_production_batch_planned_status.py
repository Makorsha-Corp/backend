"""Program occurrence batches: draft -> planned status.

Revision ID: 149_batch_planned_status
Revises: 148_work_order_program_interval
Create Date: 2026-10-27
"""
from alembic import op

revision = "149_batch_planned_status"
down_revision = "148_work_order_program_interval"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE production_batches
        SET status = 'planned'
        WHERE status = 'draft'
          AND program_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE production_batches
        SET status = 'draft'
        WHERE status = 'planned'
          AND program_id IS NOT NULL
        """
    )
