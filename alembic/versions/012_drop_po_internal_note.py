"""Drop internal_note from purchase_orders.

Description is the sole user-facing order text field; internal_note is unused.

Revision ID: 012_drop_po_internal_note
Revises: 011_po_section_locks
Create Date: 2026-06-05
"""

import sqlalchemy as sa
from alembic import op

revision = '012_drop_po_internal_note'
down_revision = '011_po_section_locks'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column('purchase_orders', 'internal_note')


def downgrade() -> None:
    op.add_column('purchase_orders', sa.Column('internal_note', sa.Text(), nullable=True))
