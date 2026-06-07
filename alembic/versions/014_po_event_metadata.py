"""Add metadata JSON to purchase_order_events.

Revision ID: 014_po_event_metadata
Revises: 013_po_section_confirmed
Create Date: 2026-06-05
"""

import sqlalchemy as sa
from alembic import op

revision = '014_po_event_metadata'
down_revision = '013_po_section_confirmed'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('purchase_order_events', sa.Column('metadata', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('purchase_order_events', 'metadata')
