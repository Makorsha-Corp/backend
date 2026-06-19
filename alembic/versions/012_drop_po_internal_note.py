"""Drop internal_note from purchase_orders.

Description is the sole user-facing order text field; internal_note is unused.

Revision ID: 012_drop_po_internal_note
Revises: 011_po_section_locks
Create Date: 2026-06-05
"""

import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import column_exists, drop_column_if_exists

revision = '012_drop_po_internal_note'
down_revision = '011_po_section_locks'
branch_labels = None
depends_on = None


def upgrade() -> None:
    drop_column_if_exists('purchase_orders', 'internal_note')


def downgrade() -> None:
    if not column_exists('purchase_orders', 'internal_note'):
        op.add_column('purchase_orders', sa.Column('internal_note', sa.Text(), nullable=True))
