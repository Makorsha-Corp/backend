"""Make purchase_orders.account_id optional (supplier not required).

Revision ID: 015_po_optional_supplier
Revises: 014_po_event_metadata
Create Date: 2026-06-05
"""

import sqlalchemy as sa
from alembic import op

revision = '015_po_optional_supplier'
down_revision = '014_po_event_metadata'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        'purchase_orders',
        'account_id',
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        'purchase_orders',
        'account_id',
        existing_type=sa.Integer(),
        nullable=False,
    )
