"""Add purchase_orders.paid; revert workflow to single Complete stage.

Revision ID: 043_po_paid_column_revert_complete
Revises: 042_po_complete_unpaid_paid
Create Date: 2026-06-29
"""
import sqlalchemy as sa
from alembic import op

revision = '043_po_paid_column_revert_complete'
down_revision = '042_po_complete_unpaid_paid'
branch_labels = None
depends_on = None


def upgrade():
    from sqlalchemy.orm import Session

    from app.db.seed_po_workflow import PO_WORKFLOW_TYPE, ensure_po_stage_statuses, _stage_status_sequence
    from app.dao.order_workflow import order_workflow_dao
    from app.models.purchase_order import PurchaseOrder
    from app.models.account_invoice import AccountInvoice
    from app.models.workspace import Workspace

    op.add_column(
        'purchase_orders',
        sa.Column('paid', sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    session = Session(bind=op.get_bind())
    try:
        workspace_ids = [row[0] for row in session.query(Workspace.id).all()]
        for workspace_id in workspace_ids:
            stage_ids = ensure_po_stage_statuses(session, workspace_id)
            complete_id = stage_ids.get('Complete')
            complete_unpaid_id = stage_ids.get('Complete - Unpaid')
            complete_paid_id = stage_ids.get('Complete - Paid')

            if complete_id is None:
                continue

            legacy_complete_ids = [
                sid for sid in (complete_unpaid_id, complete_paid_id) if sid is not None
            ]
            if legacy_complete_ids:
                session.query(PurchaseOrder).filter(
                    PurchaseOrder.workspace_id == workspace_id,
                    PurchaseOrder.current_status_id.in_(legacy_complete_ids),
                ).update(
                    {PurchaseOrder.current_status_id: complete_id},
                    synchronize_session=False,
                )

            pos = (
                session.query(PurchaseOrder)
                .filter(PurchaseOrder.workspace_id == workspace_id)
                .all()
            )
            for po in pos:
                if po.invoice_id is None:
                    po.paid = False
                    continue
                inv = session.query(AccountInvoice).filter(
                    AccountInvoice.id == po.invoice_id,
                    AccountInvoice.workspace_id == workspace_id,
                ).first()
                po.paid = bool(inv and inv.payment_status == 'paid')

            sequence = _stage_status_sequence(stage_ids)
            workflow = order_workflow_dao.get_by_type(
                session, workflow_type=PO_WORKFLOW_TYPE, workspace_id=workspace_id
            )
            if workflow:
                workflow.status_sequence = sequence
                workflow.description = 'Draft → Planning → Receiving → Complete'
                session.flush()
    finally:
        session.close()


def downgrade():
    op.drop_column('purchase_orders', 'paid')
