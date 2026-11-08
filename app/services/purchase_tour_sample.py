"""Hidden per-workspace purchase order used by the purchase help tour."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.seed_po_workflow import ensure_po_stage_statuses, seed_po_workflow
from app.models.account import Account
from app.models.attachment import Attachment
from app.models.attachment_link import AttachmentLink
from app.models.discussion import Discussion
from app.models.factory import Factory
from app.models.item import Item
from app.models.po_receive_event import PoReceiveEvent, PoReceiveEventItem
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_approver import PurchaseOrderApprover
from app.models.purchase_order_event import PurchaseOrderEvent
from app.models.purchase_order_item import PurchaseOrderItem
from app.utils.time import utcnow

TOUR_PO_NUMBER = "PO-TOUR-SAMPLE"
TOUR_DESCRIPTION = "Routine spares restock for ring frame section."
TOUR_COMMENT = "Confirm order items, approve, then finalize the invoice — same rhythm as a real PO."
TOUR_FACTORY_NAME = "Tour sample mill"
TOUR_ACCOUNT_NAME = "Sample supplier"

TOUR_LINES = (
    {"name": "Ring frame spare belt", "unit": "pcs", "qty": Decimal("4"), "price": Decimal("48.00")},
    {"name": "Lubricating oil (20L)", "unit": "drum", "qty": Decimal("2"), "price": Decimal("125.00")},
)


def reject_tour_sample_action(po: PurchaseOrder, detail: str) -> None:
    if po.is_tour_sample:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def get_purchase_tour_sample(db: Session, *, workspace_id: int) -> PurchaseOrder | None:
    return (
        db.query(PurchaseOrder)
        .filter(
            PurchaseOrder.workspace_id == workspace_id,
            PurchaseOrder.is_tour_sample.is_(True),
        )
        .first()
    )


def ensure_purchase_tour_sample(db: Session, *, workspace_id: int, user_id: int) -> PurchaseOrder:
    existing = get_purchase_tour_sample(db, workspace_id=workspace_id)
    if existing is not None:
        return existing

    po = PurchaseOrder(
        workspace_id=workspace_id,
        po_number=TOUR_PO_NUMBER,
        is_tour_sample=True,
        destination_type="storage",
        destination_id=_factory_id(db, workspace_id, user_id),
        current_status_id=_draft_status_id(db, workspace_id),
        order_workflow_id=seed_po_workflow(db, workspace_id).id,
        created_by=user_id,
        subtotal=Decimal("0"),
        total_amount=Decimal("0"),
        required_approvals=1,
    )
    db.add(po)
    db.flush()
    apply_purchase_tour_template(db, po, user_id=user_id)
    return po


def apply_purchase_tour_template(db: Session, po: PurchaseOrder, *, user_id: int) -> PurchaseOrder:
    """Rewrite the sample from the code template. Does not commit."""
    if not po.is_tour_sample:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not a sample purchase order")

    _clear_sample_children(db, po, user_id=user_id)
    factory_id = _factory_id(db, po.workspace_id, user_id)
    account_id = _account_id(db, po.workspace_id, user_id)
    today = utcnow().date()

    po.po_number = TOUR_PO_NUMBER
    po.account_id = account_id
    po.destination_type = "storage"
    po.destination_id = factory_id
    po.order_date = today
    po.expected_delivery_date = today + timedelta(days=8)
    po.actual_delivery_date = None
    po.description = TOUR_DESCRIPTION
    po.current_status_id = _draft_status_id(db, po.workspace_id)
    po.order_workflow_id = seed_po_workflow(db, po.workspace_id).id
    po.required_approvals = 1
    po.invoice_id = None
    po.supplier_confirmed = True
    po.details_confirmed = True
    po.items_confirmed = False
    po.invoice_confirmed = False
    po.invoice_ever_linked = False
    po.paid = False
    po.voided = False
    po.void_note = None
    po.voided_at = None
    po.voided_by = None
    po.updated_by = user_id
    po.updated_at = utcnow()

    total = Decimal("0")
    for index, spec in enumerate(TOUR_LINES, start=1):
        item = _item_for_line(db, po.workspace_id, user_id, spec["name"], spec["unit"])
        line_total = spec["qty"] * spec["price"]
        total += line_total
        db.add(
            PurchaseOrderItem(
                workspace_id=po.workspace_id,
                purchase_order_id=po.id,
                line_number=index,
                item_id=item.id,
                quantity_ordered=spec["qty"],
                quantity_received=Decimal("0"),
                unit_price=spec["price"],
                line_subtotal=line_total,
            )
        )

    po.subtotal = total
    po.total_amount = total
    db.add(
        PurchaseOrderApprover(
            workspace_id=po.workspace_id,
            purchase_order_id=po.id,
            user_id=user_id,
            assigned_by=user_id,
            approved=False,
        )
    )
    db.add(
        Discussion(
            workspace_id=po.workspace_id,
            entity_type="purchase_order",
            entity_id=po.id,
            user_id=user_id,
            message=TOUR_COMMENT,
        )
    )
    db.flush()
    db.refresh(po)
    return po


def _clear_sample_children(db: Session, po: PurchaseOrder, *, user_id: int) -> None:
    if po.invoice_id is not None:
        from app.dao.account_invoice import account_invoice_dao
        from app.managers.account_invoice_manager import account_invoice_manager
        from app.services.purchase_order_service import purchase_order_service

        invoice = account_invoice_dao.get_by_id_and_workspace(
            db, id=po.invoice_id, workspace_id=po.workspace_id
        )
        if invoice and invoice.invoice_status == "confirmed":
            account_invoice_manager.revert_to_draft(
                db, po.invoice_id, po.workspace_id, user_id
            )
        purchase_order_service._delete_linked_draft_invoice_for_po(
            db, po, po.workspace_id, user_id
        )
    event_ids = [
        row.id
        for row in db.query(PoReceiveEvent.id)
        .filter(PoReceiveEvent.purchase_order_id == po.id)
        .all()
    ]
    if event_ids:
        db.query(PoReceiveEventItem).filter(PoReceiveEventItem.receive_event_id.in_(event_ids)).delete(
            synchronize_session=False
        )
        db.query(PoReceiveEvent).filter(PoReceiveEvent.id.in_(event_ids)).delete(synchronize_session=False)

    db.query(PurchaseOrderItem).filter(PurchaseOrderItem.purchase_order_id == po.id).delete(
        synchronize_session=False
    )
    db.query(PurchaseOrderApprover).filter(PurchaseOrderApprover.purchase_order_id == po.id).delete(
        synchronize_session=False
    )
    db.query(PurchaseOrderEvent).filter(PurchaseOrderEvent.purchase_order_id == po.id).delete(
        synchronize_session=False
    )
    db.query(Discussion).filter(
        Discussion.workspace_id == po.workspace_id,
        Discussion.entity_type == "purchase_order",
        Discussion.entity_id == po.id,
    ).delete(synchronize_session=False)

    link_rows = (
        db.query(AttachmentLink)
        .filter(
            AttachmentLink.workspace_id == po.workspace_id,
            AttachmentLink.entity_type == "purchase_order",
            AttachmentLink.entity_id == po.id,
        )
        .all()
    )
    attachment_ids = [link.attachment_id for link in link_rows]
    for link in link_rows:
        db.delete(link)
    if attachment_ids:
        db.query(Attachment).filter(Attachment.id.in_(attachment_ids)).update(
            {Attachment.is_deleted: True, Attachment.deleted_at: utcnow()},
            synchronize_session=False,
        )
    db.flush()


def _draft_status_id(db: Session, workspace_id: int) -> int:
    statuses = ensure_po_stage_statuses(db, workspace_id)
    return statuses["Draft"]


def _factory_id(db: Session, workspace_id: int, user_id: int) -> int:
    factory = (
        db.query(Factory)
        .filter(
            Factory.workspace_id == workspace_id,
            Factory.is_deleted.is_(False),
        )
        .order_by(Factory.id.asc())
        .first()
    )
    if factory is not None:
        return factory.id
    created = Factory(
        workspace_id=workspace_id,
        name=TOUR_FACTORY_NAME,
        abbreviation="TSM",
        created_by=user_id,
        is_active=True,
        is_deleted=False,
    )
    db.add(created)
    db.flush()
    return created.id


def _account_id(db: Session, workspace_id: int, user_id: int) -> int:
    account = (
        db.query(Account)
        .filter(
            Account.workspace_id == workspace_id,
            Account.is_deleted.is_(False),
        )
        .order_by(Account.id.asc())
        .first()
    )
    if account is not None:
        return account.id
    created = Account(
        workspace_id=workspace_id,
        name=TOUR_ACCOUNT_NAME,
        created_by=user_id,
        is_active=True,
        is_deleted=False,
        allow_invoices=True,
    )
    db.add(created)
    db.flush()
    return created.id


def _item_for_line(db: Session, workspace_id: int, user_id: int, name: str, unit: str) -> Item:
    normalized = name.strip().lower()
    item = (
        db.query(Item)
        .filter(
            Item.workspace_id == workspace_id,
            Item.name_normalized == normalized,
            Item.is_active.is_(True),
        )
        .first()
    )
    if item is not None:
        return item
    created = Item(
        workspace_id=workspace_id,
        name=name,
        name_normalized=normalized,
        unit=unit,
        created_by=user_id,
        is_active=True,
        item_type="physical",
    )
    db.add(created)
    db.flush()
    return created
