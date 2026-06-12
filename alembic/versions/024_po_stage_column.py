"""Add purchase_orders.stage (code-defined workflow).

Revision ID: 024_po_stage_column
Revises: 023_project_events_members
"""

import sqlalchemy as sa
from alembic import op

revision = '024_po_stage_column'
down_revision = '023_project_events_members'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'purchase_orders',
        sa.Column('stage', sa.String(length=20), nullable=False, server_default='Draft'),
    )
    op.alter_column('purchase_orders', 'stage', server_default=None)
    op.alter_column('purchase_orders', 'current_status_id', nullable=True)


def downgrade() -> None:
    op.alter_column('purchase_orders', 'current_status_id', nullable=False)
    op.drop_column('purchase_orders', 'stage')
