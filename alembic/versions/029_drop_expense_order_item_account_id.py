"""Drop account_id from expense_order_items.

Revision ID: 029_drop_expense_order_item_account_id
Revises: 028_expense_order_events_approvers
"""

import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import column_exists, drop_column_if_exists

revision = '029_drop_expense_order_item_account_id'
down_revision = '028_expense_order_events_approvers'
branch_labels = None
depends_on = None


def upgrade() -> None:
    drop_column_if_exists('expense_order_items', 'account_id')


def downgrade() -> None:
    if not column_exists('expense_order_items', 'account_id'):
        op.add_column(
            'expense_order_items',
            sa.Column(
                'account_id',
                sa.Integer(),
                sa.ForeignKey('accounts.id', ondelete='SET NULL'),
                nullable=True,
            ),
        )
