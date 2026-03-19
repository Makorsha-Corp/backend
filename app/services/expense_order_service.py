"""Expense Order Service - transaction orchestration"""
from typing import List, Optional
from sqlalchemy.orm import Session

from app.services.base_service import BaseService
from app.managers.expense_order_manager import expense_order_manager
from app.models.expense_order import ExpenseOrder
from app.models.expense_order_item import ExpenseOrderItem
from app.schemas.expense_order import (
    ExpenseOrderCreate, ExpenseOrderUpdate,
    ExpenseOrderItemCreate, ExpenseOrderItemUpdate,
)


class ExpenseOrderService(BaseService):
    """Service for expense order workflows. Handles commit/rollback."""

    def __init__(self):
        super().__init__()
        self.manager = expense_order_manager

    def create_expense_order(
        self, db: Session, eo_in: ExpenseOrderCreate,
        workspace_id: int, user_id: int
    ) -> ExpenseOrder:
        try:
            record = self.manager.create_expense_order(db, data=eo_in, workspace_id=workspace_id, user_id=user_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def update_expense_order(
        self, db: Session, eo_id: int, eo_in: ExpenseOrderUpdate,
        workspace_id: int, user_id: int
    ) -> ExpenseOrder:
        try:
            record = self.manager.update_expense_order(db, eo_id=eo_id, data=eo_in, workspace_id=workspace_id, user_id=user_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def get_expense_order(self, db: Session, eo_id: int, workspace_id: int) -> ExpenseOrder:
        return self.manager.get_expense_order(db, eo_id, workspace_id)

    def list_expense_orders(
        self, db: Session, workspace_id: int,
        expense_category: Optional[str] = None,
        account_id: Optional[int] = None,
        skip: int = 0, limit: int = 100
    ) -> List[ExpenseOrder]:
        return self.manager.list_expense_orders(
            db, workspace_id=workspace_id,
            expense_category=expense_category, account_id=account_id,
            skip=skip, limit=limit
        )

    def delete_expense_order(self, db: Session, eo_id: int, workspace_id: int) -> None:
        try:
            self.manager.delete_expense_order(db, eo_id=eo_id, workspace_id=workspace_id)
            self._commit_transaction(db)
        except Exception:
            self._rollback_transaction(db)
            raise

    # ─── Items ─────────────────────────────────────────────────
    def add_item(
        self, db: Session, eo_id: int, item_in: ExpenseOrderItemCreate,
        workspace_id: int
    ) -> ExpenseOrderItem:
        try:
            record = self.manager.add_item(db, eo_id=eo_id, data=item_in, workspace_id=workspace_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def update_item(
        self, db: Session, item_id: int, item_in: ExpenseOrderItemUpdate,
        workspace_id: int
    ) -> ExpenseOrderItem:
        try:
            record = self.manager.update_item(db, item_id=item_id, data=item_in, workspace_id=workspace_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def remove_item(self, db: Session, item_id: int, workspace_id: int) -> ExpenseOrderItem:
        try:
            record = self.manager.remove_item(db, item_id=item_id, workspace_id=workspace_id)
            self._commit_transaction(db)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def get_items(self, db: Session, eo_id: int, workspace_id: int) -> List[ExpenseOrderItem]:
        return self.manager.get_items(db, eo_id, workspace_id)


expense_order_service = ExpenseOrderService()
