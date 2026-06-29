"""po complete unpaid/paid stages (replaces Payment Due + Complete)

Revision ID: 042_po_complete_unpaid_paid
Revises: 041_po_payment_due_stage
Create Date: 2026-06-29
"""
from alembic import op

revision = '042_po_complete_unpaid_paid'
down_revision = '041_po_payment_due_stage'
branch_labels = None
depends_on = None


def upgrade():
    from sqlalchemy.orm import Session

    from app.db.seed_po_workflow import PO_WORKFLOW_TYPE, ensure_po_stage_statuses, _stage_status_sequence
    from app.dao.order_workflow import order_workflow_dao
    from app.models.purchase_order import PurchaseOrder
    from app.models.account_invoice import AccountInvoice
    from app.models.workspace import Workspace

    session = Session(bind=op.get_bind())
    try:
        workspace_ids = [row[0] for row in session.query(Workspace.id).all()]
        for workspace_id in workspace_ids:
            stage_ids = ensure_po_stage_statuses(session, workspace_id)
            sequence = _stage_status_sequence(stage_ids)
            workflow = order_workflow_dao.get_by_type(
                session, workflow_type=PO_WORKFLOW_TYPE, workspace_id=workspace_id
            )
            if workflow:
                workflow.status_sequence = sequence
                workflow.description = (
                    'Draft → Planning → Receiving → Complete - Unpaid → Complete - Paid'
                )
                session.flush()

            receiving_id = stage_ids.get('Receiving')
            complete_unpaid_id = stage_ids.get('Complete - Unpaid')
            complete_paid_id = stage_ids.get('Complete - Paid')
            payment_due_id = stage_ids.get('Payment Due')
            legacy_complete_id = stage_ids.get('Complete')

            if payment_due_id and receiving_id:
                session.query(PurchaseOrder).filter(
                    PurchaseOrder.workspace_id == workspace_id,
                    PurchaseOrder.current_status_id == payment_due_id,
                ).update(
                    {PurchaseOrder.current_status_id: receiving_id},
                    synchronize_session=False,
                )

            if legacy_complete_id and complete_unpaid_id and complete_paid_id:
                pos = (
                    session.query(PurchaseOrder)
                    .filter(
                        PurchaseOrder.workspace_id == workspace_id,
                        PurchaseOrder.current_status_id == legacy_complete_id,
                    )
                    .all()
                )
                for po in pos:
                    target_id = complete_unpaid_id
                    if po.invoice_id:
                        inv = session.query(AccountInvoice).filter(
                            AccountInvoice.id == po.invoice_id,
                            AccountInvoice.workspace_id == workspace_id,
                        ).first()
                        if inv and inv.payment_status == 'paid':
                            target_id = complete_paid_id
                    po.current_status_id = target_id
                session.flush()
    finally:
        session.close()


def downgrade():
    pass
