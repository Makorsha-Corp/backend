"""Drop the APPROVED work order status — approvals now gate the Start action
instead of being their own visible status stage.

Revision ID: 049_work_order_drop_approved_status
Revises: 048_work_order_item_inventory_and_component_logs
"""

import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import column_exists

revision = '049_work_order_drop_approved_status'
down_revision = '048_work_order_item_inventory_and_component_logs'
branch_labels = None
depends_on = None


def upgrade() -> None:
    if column_exists('work_orders', 'status'):
        op.execute(
            sa.text(
                """
                UPDATE work_orders SET status = 'DRAFT' WHERE status = 'APPROVED';
                """
            )
        )


def downgrade() -> None:
    # No reliable way to tell which DRAFT rows were previously APPROVED; no-op.
    pass
