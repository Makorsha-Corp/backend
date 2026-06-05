"""Purchase Order Manager - business logic for purchase orders"""
from typing import List, Optional, Tuple
from decimal import Decimal
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.managers.base_manager import BaseManager
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.purchase_order_approver import PurchaseOrderApprover
from app.models.profile import Profile
from app.schemas.purchase_order import (
    PurchaseOrderCreate, PurchaseOrderUpdate,
    PurchaseOrderItemCreate, PurchaseOrderItemUpdate,
)
from app.dao.purchase_order import purchase_order_dao, purchase_order_item_dao
from app.dao.purchase_order_approver import purchase_order_approver_dao
from app.dao.workspace_member import workspace_member_dao
from app.dao.profile import profile_dao


class PurchaseOrderManager(BaseManager[PurchaseOrder]):
    """Manager for purchase order business logic."""

    def __init__(self):
        super().__init__(PurchaseOrder)
        self.po_dao = purchase_order_dao
        self.item_dao = purchase_order_item_dao
        self.approver_dao = purchase_order_approver_dao

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

        po = self.po_dao.create(session, obj_in=po_dict)

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
        return self.po_dao.update(session, db_obj=record, obj_in=update_dict)

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
        workspace_id: int
    ) -> PurchaseOrderItem:
        """Update purchase order item."""
        record = self.item_dao.get_by_id_and_workspace(session, id=item_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order item not found")
        update_dict = data.model_dump(exclude_unset=True)

        if 'quantity_ordered' in update_dict or 'unit_price' in update_dict:
            qty = Decimal(str(update_dict.get('quantity_ordered', record.quantity_ordered)))
            price = Decimal(str(update_dict.get('unit_price', record.unit_price)))
            update_dict['line_subtotal'] = qty * price

        result = self.item_dao.update(session, db_obj=record, obj_in=update_dict)
        po = self.po_dao.get_by_id_and_workspace(session, id=record.purchase_order_id, workspace_id=workspace_id)
        if po:
            self._recalc_totals(session, po)
        return result

    def remove_item(self, session: Session, item_id: int, workspace_id: int) -> PurchaseOrderItem:
        """Remove item from purchase order."""
        record = self.item_dao.get_by_id_and_workspace(session, id=item_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order item not found")
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
        return rec


purchase_order_manager = PurchaseOrderManager()
