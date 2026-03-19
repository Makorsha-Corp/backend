"""Purchase Order Manager - business logic for purchase orders"""
from typing import List, Optional
from decimal import Decimal
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.managers.base_manager import BaseManager
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.schemas.purchase_order import (
    PurchaseOrderCreate, PurchaseOrderUpdate,
    PurchaseOrderItemCreate, PurchaseOrderItemUpdate,
)
from app.dao.purchase_order import purchase_order_dao, purchase_order_item_dao


class PurchaseOrderManager(BaseManager[PurchaseOrder]):
    """Manager for purchase order business logic."""

    def __init__(self):
        super().__init__(PurchaseOrder)
        self.po_dao = purchase_order_dao
        self.item_dao = purchase_order_item_dao

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
        skip: int = 0, limit: int = 100
    ) -> List[PurchaseOrder]:
        return self.po_dao.get_by_workspace(
            session, workspace_id=workspace_id,
            account_id=account_id,
            skip=skip, limit=limit
        )

    def delete_purchase_order(self, session: Session, po_id: int, workspace_id: int) -> None:
        record = self.po_dao.get_by_id_and_workspace(session, id=po_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Purchase order with ID {po_id} not found")
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


purchase_order_manager = PurchaseOrderManager()
