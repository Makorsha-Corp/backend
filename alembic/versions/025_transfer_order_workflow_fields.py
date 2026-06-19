"""Add transfer order workflow fields (section confirms, expected date, approvals threshold).

Revision ID: 025_transfer_order_workflow_fields
Revises: 024_transfer_order_events
"""

import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import add_column_if_not_exists, column_exists

revision = '025_transfer_order_workflow_fields'
down_revision = '024_transfer_order_events'
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_column_if_not_exists(
        'transfer_orders',
        sa.Column('route_confirmed', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    add_column_if_not_exists(
        'transfer_orders',
        sa.Column('items_confirmed', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    add_column_if_not_exists(
        'transfer_orders',
        sa.Column('expected_completion_date', sa.Date(), nullable=True),
    )
    add_column_if_not_exists(
        'transfer_orders',
        sa.Column('required_approvals', sa.Integer(), nullable=True),
    )

    if column_exists('transfer_orders', 'route_confirmed'):
        op.alter_column('transfer_orders', 'route_confirmed', server_default=None)
    if column_exists('transfer_orders', 'items_confirmed'):
        op.alter_column('transfer_orders', 'items_confirmed', server_default=None)


def downgrade() -> None:
    for col in ('required_approvals', 'expected_completion_date', 'items_confirmed', 'route_confirmed'):
        if column_exists('transfer_orders', col):
            op.drop_column('transfer_orders', col)
