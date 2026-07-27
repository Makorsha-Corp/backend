"""Add soft-delete columns on work_order_items.

Revision ID: 063_work_order_item_soft_delete
Revises: 062_work_order_template_recurrence_range
"""

import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import column_exists

revision = '063_work_order_item_soft_delete'
down_revision = '062_work_order_template_recurrence_range'
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not column_exists('work_order_items', 'is_deleted'):
        op.add_column(
            'work_order_items',
            sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if not column_exists('work_order_items', 'deleted_at'):
        op.add_column('work_order_items', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    if not column_exists('work_order_items', 'deleted_by'):
        op.add_column(
            'work_order_items',
            sa.Column('deleted_by', sa.Integer(), sa.ForeignKey('profiles.id'), nullable=True),
        )


def downgrade() -> None:
    for col in ('deleted_by', 'deleted_at', 'is_deleted'):
        if column_exists('work_order_items', col):
            op.drop_column('work_order_items', col)
