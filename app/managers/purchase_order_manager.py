"""Purchase Order Manager - business logic for purchase orders"""
from typing import List, Optional, Tuple
from decimal import Decimal
from datetime import date, datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.managers.base_manager import BaseManager
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.purchase_order_approver import PurchaseOrderApprover
from app.models.purchase_order_event import PurchaseOrderEvent
from app.models.profile import Profile
from app.schemas.purchase_order import (
    PurchaseOrderCreate, PurchaseOrderUpdate,
    PurchaseOrderItemCreate, PurchaseOrderItemUpdate,
)
from app.dao.purchase_order import purchase_order_dao, purchase_order_item_dao
from app.dao.purchase_order_approver import purchase_order_approver_dao
from app.dao.purchase_order_event import purchase_order_event_dao
from app.dao.workspace_member import workspace_member_dao
from app.dao.profile import profile_dao

INVOICE_LOCKED_DETAIL_FIELDS = frozenset({
    'account_id', 'destination_type', 'destination_id', 'order_date',
})
NOTES_FIELDS = frozenset({'description', 'order_note', 'internal_note'})
DETAIL_LOG_FIELDS = {
    'account_id': 'Supplier',
    'destination_type': 'Destination type',
    'destination_id': 'Destination',
    'order_date': 'Order date',
    'expected_delivery_date': 'Expected delivery',
}
NOTE_LOG_FIELDS = {
    'description': 'Description',
    'order_note': 'Order note',
    'internal_note': 'Internal note',
}
INVOICE_LOCK_MSG = 'Locked after invoice creation'
SECTION_LOCK_FIELDS = {
    'details_locked': ('details', 'Order details'),
    'notes_locked': ('notes', 'Order notes'),
    'items_locked': ('items', 'Order items'),
}


class PurchaseOrderManager(BaseManager[PurchaseOrder]):
    """Manager for purchase order business logic."""

    def __init__(self):
        super().__init__(PurchaseOrder)
        self.po_dao = purchase_order_dao
        self.item_dao = purchase_order_item_dao
        self.approver_dao = purchase_order_approver_dao
        self.event_dao = purchase_order_event_dao

    def create_purchase_order(
        self, session: Session, data: PurchaseOrderCreate,
        workspace_id: int, user_id: int
    ) -> PurchaseOrder:
        """Create purchase order with auto-generated number and nested items."""
        po_number = self.po_dao.get_next_number(session, workspace_id=workspace_id)

        items_data = data.items or []
        po_dict = data.model_dump(exclude={'items'})
        po_dict['workspace_id'] = workspace_id
        po_dict['po_number'] = po_number
        po_dict['created_by'] = user_id
        if not po_dict.get('order_date'):
            po_dict['order_date'] = date.today()

        po = self.po_dao.create(session, obj_in=po_dict)

        # Auto-add the creator as an approver.
        session.add(PurchaseOrderApprover(
            workspace_id=workspace_id,
            purchase_order_id=po.id,
            user_id=user_id,
            assigned_by=user_id,
            approved=False,
        ))
        session.flush()

        self.log_event(session, po.id, workspace_id, 'created', 'Order created', user_id)

        subtotal = Decimal('0')

        for idx, item_data in enumerate(items_data, start=1):
            item_dict = item_data.model_dump()
            item_dict['workspace_id'] = workspace_id
            item_dict['purchase_order_id'] = po.id
            item_dict['line_number'] = idx

            qty = Decimal(str(item_dict['quantity_ordered']))
            price = Decimal(str(item_dict['unit_price']))
            line_sub = qty * price
            item_dict['line_subtotal'] = line_sub

            subtotal += line_sub

            self.item_dao.create(session, obj_in=item_dict)

        po.subtotal = subtotal
        po.total_amount = subtotal
        session.flush()

        return po

    def update_purchase_order(
        self, session: Session, po_id: int, data: PurchaseOrderUpdate,
        workspace_id: int, user_id: int
    ) -> PurchaseOrder:
        """Update purchase order."""
        record = self.po_dao.get_by_id_and_workspace(session, id=po_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Purchase order with ID {po_id} not found")

        update_dict = data.model_dump(exclude_unset=True)
        update_dict['updated_by'] = user_id

        if record.invoice_id is not None:
            if update_dict.get('details_locked') is False:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail='Cannot unlock order details after invoice is created',
                )
            if update_dict.get('items_locked') is False:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail='Cannot unlock order items after invoice is created',
                )

        blocked_details = self._locked_detail_update_fields(record).intersection(update_dict)
        if blocked_details:
            detail = (
                INVOICE_LOCK_MSG
                if record.invoice_id is not None
                else 'Order details are locked'
            )
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

        if record.notes_locked and NOTES_FIELDS.intersection(update_dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Order notes are locked',
            )

        for lock_field, (section_key, label) in SECTION_LOCK_FIELDS.items():
            if lock_field not in update_dict:
                continue
            new_locked = bool(update_dict[lock_field])
            old_locked = bool(getattr(record, lock_field, False))
            if new_locked != old_locked:
                event_suffix = 'locked' if new_locked else 'unlocked'
                self.log_event(
                    session, po_id, workspace_id,
                    f'{section_key}_{event_suffix}',
                    f'{label} {event_suffix}',
                    user_id,
                )

        self._log_section_field_updates(
            session, po_id, workspace_id, user_id, record, update_dict,
        )

        return self.po_dao.update(session, db_obj=record, obj_in=update_dict)

    def _changed_field_labels(
        self, record: PurchaseOrder, update_dict: dict, fields: dict[str, str],
    ) -> List[str]:
        labels: List[str] = []
        for field, label in fields.items():
            if field not in update_dict:
                continue
            if getattr(record, field) != update_dict[field]:
                labels.append(label)
        return labels

    def _log_section_field_updates(
        self,
        session: Session,
        po_id: int,
        workspace_id: int,
        user_id: int,
        record: PurchaseOrder,
        update_dict: dict,
    ) -> None:
        detail_labels = self._changed_field_labels(record, update_dict, DETAIL_LOG_FIELDS)
        if detail_labels:
            self.log_event(
                session, po_id, workspace_id, 'details_updated',
                f"Updated order details: {', '.join(detail_labels)}",
                user_id,
            )

        note_labels = self._changed_field_labels(record, update_dict, NOTE_LOG_FIELDS)
        if note_labels:
            self.log_event(
                session, po_id, workspace_id, 'notes_updated',
                f"Updated order notes: {', '.join(note_labels)}",
                user_id,
            )

    def _locked_detail_update_fields(self, record: PurchaseOrder) -> frozenset:
        if record.invoice_id is not None:
            return INVOICE_LOCKED_DETAIL_FIELDS
        if record.details_locked:
            return INVOICE_LOCKED_DETAIL_FIELDS
        return frozenset()

    def _items_structure_locked(self, po: PurchaseOrder) -> bool:
        return bool(po.items_locked or po.invoice_id is not None)

    def details_complete_for_invoice(self, po: PurchaseOrder) -> bool:
        return (
            po.account_id is not None
            and bool(po.destination_type)
            and po.destination_id is not None
            and po.order_date is not None
        )

    def apply_post_invoice_locks(
        self, session: Session, po: PurchaseOrder, workspace_id: int, user_id: int
    ) -> None:
        """Set section locks and log events after an invoice is linked to the order."""
        self.log_event(
            session, po.id, workspace_id, 'invoice_created',
            'Invoice created', user_id,
        )
        if not po.details_locked:
            po.details_locked = True
            self.log_event(
                session, po.id, workspace_id, 'details_locked',
                'Order details locked after invoice created', user_id,
            )
        if not po.items_locked:
            po.items_locked = True
            self.log_event(
                session, po.id, workspace_id, 'items_locked',
                'Order items locked after invoice created', user_id,
            )
        session.flush()

    def get_purchase_order(self, session: Session, po_id: int, workspace_id: int) -> PurchaseOrder:
        record = self.po_dao.get_by_id_and_workspace(session, id=po_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Purchase order with ID {po_id} not found")
        return record

    def list_purchase_orders(
        self, session: Session, workspace_id: int,
        account_id: Optional[int] = None,
        invoice_id: Optional[int] = None,
        skip: int = 0, limit: int = 100
    ) -> List[PurchaseOrder]:
        return self.po_dao.get_by_workspace(
            session, workspace_id=workspace_id,
            account_id=account_id,
            invoice_id=invoice_id,
            skip=skip, limit=limit
        )

    def delete_purchase_order(self, session: Session, po_id: int, workspace_id: int) -> None:
        record = self.po_dao.get_by_id_and_workspace(session, id=po_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Purchase order with ID {po_id} not found")
        # Delete line items explicitly to avoid FK issues when DB constraints
        # were created without cascading deletes.
        line_items = self.item_dao.get_by_order(
            session, purchase_order_id=po_id, workspace_id=workspace_id
        )
        for line_item in line_items:
            session.delete(line_item)
        session.flush()
        session.delete(record)
        session.flush()

    # ─── Purchase Order Items ──────────────────────────────────
    def add_item(
        self, session: Session, po_id: int, data: PurchaseOrderItemCreate,
        workspace_id: int
    ) -> PurchaseOrderItem:
        """Add item to purchase order and recalculate totals."""
        po = self.po_dao.get_by_id_and_workspace(session, id=po_id, workspace_id=workspace_id)
        if not po:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found")
        if self._items_structure_locked(po):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=INVOICE_LOCK_MSG if po.invoice_id is not None else 'Order items are locked',
            )

        existing = self.item_dao.get_by_order(session, purchase_order_id=po_id, workspace_id=workspace_id)
        next_line = max((i.line_number for i in existing), default=0) + 1

        item_dict = data.model_dump()
        item_dict['workspace_id'] = workspace_id
        item_dict['purchase_order_id'] = po_id
        item_dict['line_number'] = next_line

        qty = Decimal(str(item_dict['quantity_ordered']))
        price = Decimal(str(item_dict['unit_price']))
        item_dict['line_subtotal'] = qty * price

        item = self.item_dao.create(session, obj_in=item_dict)
        self._recalc_totals(session, po)
        return item

    def update_item(
        self, session: Session, item_id: int, data: PurchaseOrderItemUpdate,
        workspace_id: int, user_id: Optional[int] = None
    ) -> PurchaseOrderItem:
        """Update purchase order item. Logs a 'received' event when quantity_received changes."""
        record = self.item_dao.get_by_id_and_workspace(session, id=item_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order item not found")
        update_dict = data.model_dump(exclude_unset=True)

        po = self.po_dao.get_by_id_and_workspace(
            session, id=record.purchase_order_id, workspace_id=workspace_id
        )
        if po and self._items_structure_locked(po):
            structural = set(update_dict.keys()) - {'quantity_received'}
            if structural:
                detail = (
                    f'{INVOICE_LOCK_MSG} (receiving still allowed)'
                    if po.invoice_id is not None
                    else 'Order items are locked (receiving still allowed)'
                )
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

        prev_received = Decimal(str(record.quantity_received or 0))
        received_changed = (
            'quantity_received' in update_dict
            and update_dict['quantity_received'] is not None
            and Decimal(str(update_dict['quantity_received'])) != prev_received
        )

        if 'quantity_ordered' in update_dict or 'unit_price' in update_dict:
            qty = Decimal(str(update_dict.get('quantity_ordered', record.quantity_ordered)))
            price = Decimal(str(update_dict.get('unit_price', record.unit_price)))
            update_dict['line_subtotal'] = qty * price

        result = self.item_dao.update(session, db_obj=record, obj_in=update_dict)
        po = self.po_dao.get_by_id_and_workspace(session, id=record.purchase_order_id, workspace_id=workspace_id)
        if po:
            self._recalc_totals(session, po)

        if received_changed:
            item_label = getattr(record, 'item_name', None) or f"item #{record.item_id}"
            new_received = Decimal(str(update_dict['quantity_received']))
            ordered = Decimal(str(record.quantity_ordered))
            delta = new_received - prev_received
            fully_received = new_received >= ordered

            def _qty(d: Decimal) -> str:
                return str(int(d)) if d == d.to_integral_value() else str(d.normalize())

            xy = f"({_qty(new_received)} of {_qty(ordered)})"
            if delta > 0:
                if fully_received:
                    description = f"Received {_qty(delta)} more — {xy} {item_label} fully received"
                else:
                    description = f"Received {_qty(delta)} more {xy} {item_label}"
            else:
                description = f"Receiving adjusted to {_qty(new_received)} of {_qty(ordered)} {item_label}"
            self.log_event(
                session, record.purchase_order_id, workspace_id, 'received',
                description,
                user_id,
            )

            # If this completed the final outstanding item, log an order-level
            # "all items received" milestone (once).
            if fully_received:
                po_items = self.item_dao.get_by_order(
                    session, purchase_order_id=record.purchase_order_id, workspace_id=workspace_id
                )
                all_done = po_items and all(
                    Decimal(str(i.quantity_received)) >= Decimal(str(i.quantity_ordered))
                    for i in po_items
                )
                if all_done:
                    already_logged = any(
                        e.event_type == 'all_received'
                        for e in self.event_dao.get_by_order(
                            session, purchase_order_id=record.purchase_order_id, workspace_id=workspace_id
                        )
                    )
                    if not already_logged:
                        self.log_event(
                            session, record.purchase_order_id, workspace_id, 'all_received',
                            'All items received', user_id,
                        )

        return result

    def remove_item(self, session: Session, item_id: int, workspace_id: int) -> PurchaseOrderItem:
        """Remove item from purchase order."""
        record = self.item_dao.get_by_id_and_workspace(session, id=item_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order item not found")
        po = self.po_dao.get_by_id_and_workspace(
            session, id=record.purchase_order_id, workspace_id=workspace_id
        )
        if po and self._items_structure_locked(po):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=INVOICE_LOCK_MSG if po.invoice_id is not None else 'Order items are locked',
            )
        po_id = record.purchase_order_id
        session.delete(record)
        session.flush()
        po = self.po_dao.get_by_id_and_workspace(session, id=po_id, workspace_id=workspace_id)
        if po:
            self._recalc_totals(session, po)
        return record

    def get_items(self, session: Session, po_id: int, workspace_id: int) -> List[PurchaseOrderItem]:
        return self.item_dao.get_by_order(session, purchase_order_id=po_id, workspace_id=workspace_id)

    def _recalc_totals(self, session: Session, po: PurchaseOrder):
        """Recalculate order totals from line items."""
        items = self.item_dao.get_by_order(session, purchase_order_id=po.id, workspace_id=po.workspace_id)
        subtotal = sum((i.line_subtotal or Decimal('0')) for i in items)
        po.subtotal = subtotal
        po.total_amount = subtotal
        session.flush()

    # ─── Approvers ─────────────────────────────────────────────
    def list_approvers(
        self, session: Session, po_id: int, workspace_id: int
    ) -> List[Tuple[PurchaseOrderApprover, Optional[Profile], Optional[str]]]:
        """Approvers for an order, enriched with profile + workspace position."""
        self.get_purchase_order(session, po_id, workspace_id)  # 404 guard
        approvers = self.approver_dao.get_by_order(session, purchase_order_id=po_id, workspace_id=workspace_id)
        result: List[Tuple[PurchaseOrderApprover, Optional[Profile], Optional[str]]] = []
        for a in approvers:
            profile = profile_dao.get(session, id=a.user_id)
            member = workspace_member_dao.get_by_workspace_and_user(
                session, workspace_id=workspace_id, user_id=a.user_id
            )
            result.append((a, profile, member.position if member else None))
        return result

    def approval_summary(self, session: Session, po: PurchaseOrder) -> Tuple[int, int, bool]:
        """(approved_count, required, met). required null -> all assigned must approve."""
        approvers = self.approver_dao.get_by_order(
            session, purchase_order_id=po.id, workspace_id=po.workspace_id
        )
        approved_count = sum(1 for a in approvers if a.approved)
        if po.required_approvals is not None:
            required = po.required_approvals
        elif len(approvers) > 0:
            required = len(approvers)
        else:
            required = 0
        return approved_count, required, approved_count >= required

    def approvals_met(self, session: Session, po: PurchaseOrder) -> bool:
        return self.approval_summary(session, po)[2]

    def add_approver(
        self, session: Session, po_id: int, user_id: int, workspace_id: int, assigned_by: int
    ) -> PurchaseOrderApprover:
        self.get_purchase_order(session, po_id, workspace_id)  # 404 guard
        member = workspace_member_dao.get_by_workspace_and_user(
            session, workspace_id=workspace_id, user_id=user_id
        )
        if not member or member.status != 'active':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is not an active member of this workspace"
            )
        existing = self.approver_dao.get_by_order_and_user(
            session, purchase_order_id=po_id, user_id=user_id, workspace_id=workspace_id
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User is already an approver for this order"
            )
        obj = PurchaseOrderApprover(
            workspace_id=workspace_id,
            purchase_order_id=po_id,
            user_id=user_id,
            assigned_by=assigned_by,
            approved=False,
        )
        session.add(obj)
        session.flush()
        return obj

    def remove_approver(self, session: Session, po_id: int, user_id: int, workspace_id: int) -> None:
        rec = self.approver_dao.get_by_order_and_user(
            session, purchase_order_id=po_id, user_id=user_id, workspace_id=workspace_id
        )
        if not rec:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approver not found")
        session.delete(rec)
        session.flush()

    def set_approval(
        self, session: Session, po_id: int, user_id: int, workspace_id: int, approved: bool
    ) -> PurchaseOrderApprover:
        rec = self.approver_dao.get_by_order_and_user(
            session, purchase_order_id=po_id, user_id=user_id, workspace_id=workspace_id
        )
        if not rec:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not an assigned approver for this order"
            )
        rec.approved = approved
        rec.approved_at = datetime.utcnow() if approved else None
        session.flush()

        self.log_event(
            session, po_id, workspace_id,
            'approved' if approved else 'approval_withdrawn',
            'Approved order' if approved else 'Withdrew approval',
            user_id,
        )
        return rec

    # ─── Events ────────────────────────────────────────────────
    def log_event(
        self, session: Session, po_id: int, workspace_id: int,
        event_type: str, description: str, performed_by: Optional[int] = None
    ) -> PurchaseOrderEvent:
        ev = PurchaseOrderEvent(
            workspace_id=workspace_id,
            purchase_order_id=po_id,
            event_type=event_type,
            description=description,
            performed_by=performed_by,
        )
        session.add(ev)
        session.flush()
        return ev

    def list_events(
        self, session: Session, po_id: int, workspace_id: int
    ) -> List[Tuple[PurchaseOrderEvent, Optional[Profile]]]:
        self.get_purchase_order(session, po_id, workspace_id)  # 404 guard
        events = self.event_dao.get_by_order(session, purchase_order_id=po_id, workspace_id=workspace_id)
        return [
            (e, profile_dao.get(session, id=e.performed_by) if e.performed_by else None)
            for e in events
        ]


purchase_order_manager = PurchaseOrderManager()
