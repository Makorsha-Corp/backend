"""PO stage statuses, purchase workflow seed, composite workflow type unique

Revision ID: 022_po_stage_workflow
Revises: 021_po_item_quantity_received_backfill
"""

from alembic import op
import sqlalchemy as sa

revision = '022_po_stage_workflow'
down_revision = '021_po_item_quantity_received_backfill'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text('ALTER TABLE order_workflows DROP CONSTRAINT IF EXISTS order_workflows_type_key')
    )
    op.create_unique_constraint(
        'uq_order_workflows_workspace_type',
        'order_workflows',
        ['workspace_id', 'type'],
    )


def downgrade() -> None:
    op.drop_constraint('uq_order_workflows_workspace_type', 'order_workflows', type_='unique')
    op.create_unique_constraint('order_workflows_type_key', 'order_workflows', ['type'])
