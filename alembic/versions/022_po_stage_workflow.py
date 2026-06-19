"""PO stage statuses, purchase workflow seed, composite workflow type unique

Revision ID: 022_po_stage_workflow
Revises: 021_po_item_quantity_received_backfill
"""

import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import create_unique_constraint_if_not_exists, drop_unique_constraint_if_exists

revision = '022_po_stage_workflow'
down_revision = '021_po_item_quantity_received_backfill'
branch_labels = None
depends_on = None


def upgrade() -> None:
    drop_unique_constraint_if_exists('order_workflows', 'order_workflows_type_key')
    create_unique_constraint_if_not_exists(
        'order_workflows', 'uq_order_workflows_workspace_type', ['workspace_id', 'type']
    )

    from sqlalchemy.orm import Session

    from app.db.seed_po_workflow import seed_po_workflow_for_all_workspaces

    session = Session(bind=op.get_bind())
    try:
        seed_po_workflow_for_all_workspaces(session)
        session.flush()
    finally:
        session.close()


def downgrade() -> None:
    drop_unique_constraint_if_exists('order_workflows', 'uq_order_workflows_workspace_type')
    from app.db.migration_helpers import unique_constraint_exists

    if not unique_constraint_exists('order_workflows', 'order_workflows_type_key'):
        op.create_unique_constraint('order_workflows_type_key', 'order_workflows', ['type'])
