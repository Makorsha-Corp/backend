"""Expense Order Manager - business logic for expense orders"""
from typing import List, Optional
from decimal import Decimal
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.managers.base_manager import BaseManager
from app.models.expense_order import ExpenseOrder
from app.models.expense_order_item import ExpenseOrderItem
from app.schemas.expense_order import (
    ExpenseOrderCreate, ExpenseOrderUpdate,
    ExpenseOrderItemCreate, ExpenseOrderItemUpdate,
)
from app.dao.expense_order import expense_order_dao, expense_order_item_dao


class ExpenseOrderManager(BaseManager[ExpenseOrder]):
    """Manager for expense order business logic."""

    def __init__(self):
        super().__init__(ExpenseOrder)
        self.eo_dao = expense_order_dao
        self.item_dao = expense_order_item_dao

    def create_expense_order(
        self, session: Session, data: ExpenseOrderCreate,
        workspace_id: int, user_id: int
    ) -> ExpenseOrder:
        """Create expense order with auto-generated number and nested items."""
        exp_number = self.eo_dao.get_next_number(session, workspace_id=workspace_id)

        items_data = data.items or []
        eo_dict = data.model_dump(exclude={'items'})
        eo_dict['workspace_id'] = workspace_id
        eo_dict['expense_number'] = exp_number
        eo_dict['created_by'] = user_id

        eo = self.eo_dao.create(session, obj_in=eo_dict)

        subtotal = Decimal('0')

        for idx, item_data in enumerate(items_data, start=1):
            item_dict = item_data.model_dump()
            item_dict['workspace_id'] = workspace_id
            item_dict['expense_order_id'] = eo.id
            item_dict['line_number'] = idx

            qty = Decimal(str(item_dict.get('quantity', 1)))
            price = Decimal(str(item_dict.get('unit_price') or 0))
            line_sub = qty * price
            item_dict['line_subtotal'] = line_sub

            subtotal += line_sub

            self.item_dao.create(session, obj_in=item_dict)

        eo.subtotal = subtotal
        eo.total_amount = subtotal
        session.flush()

        return eo

    def update_expense_order(
        self, session: Session, eo_id: int, data: ExpenseOrderUpdate,
        workspace_id: int, user_id: int
    ) -> ExpenseOrder:
        """Update expense order."""
        record = self.eo_dao.get_by_id_and_workspace(session, id=eo_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Expense order with ID {eo_id} not found")

        update_dict = data.model_dump(exclude_unset=True)
        update_dict['updated_by'] = user_id
        return self.eo_dao.update(session, db_obj=record, obj_in=update_dict)

    def get_expense_order(self, session: Session, eo_id: int, workspace_id: int) -> ExpenseOrder:
        record = self.eo_dao.get_by_id_and_workspace(session, id=eo_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Expense order with ID {eo_id} not found")
        return record

    def list_expense_orders(
        self, session: Session, workspace_id: int,
        expense_category: Optional[str] = None,
        account_id: Optional[int] = None,
        skip: int = 0, limit: int = 100
    ) -> List[ExpenseOrder]:
        return self.eo_dao.get_by_workspace(
            session, workspace_id=workspace_id,
            expense_category=expense_category, account_id=account_id,
            skip=skip, limit=limit
        )

    def delete_expense_order(self, session: Session, eo_id: int, workspace_id: int) -> None:
        record = self.eo_dao.get_by_id_and_workspace(session, id=eo_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Expense order with ID {eo_id} not found")
        session.delete(record)
        session.flush()

    # ─── Expense Order Items ──────────────────────────────────
    def add_item(
        self, session: Session, eo_id: int, data: ExpenseOrderItemCreate,
        workspace_id: int
    ) -> ExpenseOrderItem:
        """Add item to expense order and recalculate totals."""
        eo = self.eo_dao.get_by_id_and_workspace(session, id=eo_id, workspace_id=workspace_id)
        if not eo:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense order not found")

        existing = self.item_dao.get_by_order(session, expense_order_id=eo_id, workspace_id=workspace_id)
        next_line = max((i.line_number for i in existing), default=0) + 1

        item_dict = data.model_dump()
        item_dict['workspace_id'] = workspace_id
        item_dict['expense_order_id'] = eo_id
        item_dict['line_number'] = next_line

        qty = Decimal(str(item_dict.get('quantity', 1)))
        price = Decimal(str(item_dict.get('unit_price') or 0))
        item_dict['line_subtotal'] = qty * price

        item = self.item_dao.create(session, obj_in=item_dict)
        self._recalc_totals(session, eo)
        return item

    def update_item(
        self, session: Session, item_id: int, data: ExpenseOrderItemUpdate,
        workspace_id: int
    ) -> ExpenseOrderItem:
        """Update expense order item."""
        record = self.item_dao.get_by_id_and_workspace(session, id=item_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense order item not found")
        update_dict = data.model_dump(exclude_unset=True)

        if 'quantity' in update_dict or 'unit_price' in update_dict:
            qty = Decimal(str(update_dict.get('quantity', record.quantity)))
            price = Decimal(str(update_dict.get('unit_price', record.unit_price) or 0))
            update_dict['line_subtotal'] = qty * price

        result = self.item_dao.update(session, db_obj=record, obj_in=update_dict)
        eo = self.eo_dao.get_by_id_and_workspace(session, id=record.expense_order_id, workspace_id=workspace_id)
        if eo:
            self._recalc_totals(session, eo)
        return result

    def remove_item(self, session: Session, item_id: int, workspace_id: int) -> ExpenseOrderItem:
        """Remove item from expense order."""
        record = self.item_dao.get_by_id_and_workspace(session, id=item_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense order item not found")
        eo_id = record.expense_order_id
        session.delete(record)
        session.flush()
        eo = self.eo_dao.get_by_id_and_workspace(session, id=eo_id, workspace_id=workspace_id)
        if eo:
            self._recalc_totals(session, eo)
        return record

    def get_items(self, session: Session, eo_id: int, workspace_id: int) -> List[ExpenseOrderItem]:
        return self.item_dao.get_by_order(session, expense_order_id=eo_id, workspace_id=workspace_id)

    def _recalc_totals(self, session: Session, eo: ExpenseOrder):
        """Recalculate order totals from line items."""
        items = self.item_dao.get_by_order(session, expense_order_id=eo.id, workspace_id=eo.workspace_id)
        subtotal = sum((i.line_subtotal or Decimal('0')) for i in items)
        eo.subtotal = subtotal
        eo.total_amount = subtotal
        session.flush()


expense_order_manager = ExpenseOrderManager()
