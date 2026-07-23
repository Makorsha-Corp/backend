"""Add generation_mode to work_order_templates.

Revision ID: 057_work_order_template_generation_mode
Revises: 056_merge_payment_and_schedules
Create Date: 2026-07-23
"""

from alembic import op
import sqlalchemy as sa

revision = '057_work_order_template_generation_mode'
down_revision = '056_merge_payment_and_schedules'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'work_order_templates',
        sa.Column(
            'generation_mode',
            sa.String(length=20),
            nullable=False,
            server_default='schedule',
        ),
    )


def downgrade() -> None:
    op.drop_column('work_order_templates', 'generation_mode')
