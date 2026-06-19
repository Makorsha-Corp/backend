"""Add metadata JSON to purchase_order_events.

Revision ID: 014_po_event_metadata
Revises: 013_po_section_confirmed
Create Date: 2026-06-05
"""

import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import add_column_if_not_exists

revision = '014_po_event_metadata'
down_revision = '013_po_section_confirmed'
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_column_if_not_exists(
        'purchase_order_events', sa.Column('metadata', sa.JSON(), nullable=True)
    )


def downgrade() -> None:
    from app.db.migration_helpers import drop_column_if_exists

    drop_column_if_exists('purchase_order_events', 'metadata')
