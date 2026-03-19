"""Expense order DAO. SECURITY: All queries MUST filter by workspace_id."""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.dao.base import BaseDAO
from app.models.expense_order import ExpenseOrder
from app.models.expense_order_item import ExpenseOrderItem
from app.schemas.expense_order import ExpenseOrderCreate, ExpenseOrderUpdate, ExpenseOrderItemCreate, ExpenseOrderItemUpdate


class ExpenseOrderDAO(BaseDAO[ExpenseOrder, ExpenseOrderCreate, ExpenseOrderUpdate]):
    def get_by_workspace(self, db: Session, *, workspace_id: int, expense_category: Optional[str] = None, account_id: Optional[int] = None, skip: int = 0, limit: int = 100) -> List[ExpenseOrder]:
        query = db.query(ExpenseOrder).filter(ExpenseOrder.workspace_id == workspace_id)
        if expense_category:
            query = query.filter(ExpenseOrder.expense_category == expense_category)
        if account_id:
            query = query.filter(ExpenseOrder.account_id == account_id)
        return query.order_by(desc(ExpenseOrder.created_at)).offset(skip).limit(limit).all()

    def get_by_id_and_workspace(self, db: Session, *, id: int, workspace_id: int) -> Optional[ExpenseOrder]:
        return db.query(ExpenseOrder).filter(ExpenseOrder.id == id, ExpenseOrder.workspace_id == workspace_id).first()

    def get_next_number(self, db: Session, *, workspace_id: int) -> str:
        from datetime import datetime
        year = datetime.now().year
        prefix = f"EXP-{year}-"
        last = db.query(ExpenseOrder).filter(ExpenseOrder.workspace_id == workspace_id, ExpenseOrder.expense_number.like(f"{prefix}%")).order_by(desc(ExpenseOrder.expense_number)).first()
        if last:
            try:
                return f"{prefix}{int(last.expense_number.split('-')[-1]) + 1:03d}"
            except (ValueError, IndexError):
                pass
        return f"{prefix}001"


class ExpenseOrderItemDAO(BaseDAO[ExpenseOrderItem, ExpenseOrderItemCreate, ExpenseOrderItemUpdate]):
    def get_by_order(self, db: Session, *, expense_order_id: int, workspace_id: int) -> List[ExpenseOrderItem]:
        return db.query(ExpenseOrderItem).filter(ExpenseOrderItem.expense_order_id == expense_order_id, ExpenseOrderItem.workspace_id == workspace_id).order_by(ExpenseOrderItem.line_number).all()

    def get_by_id_and_workspace(self, db: Session, *, id: int, workspace_id: int) -> Optional[ExpenseOrderItem]:
        return db.query(ExpenseOrderItem).filter(ExpenseOrderItem.id == id, ExpenseOrderItem.workspace_id == workspace_id).first()


expense_order_dao = ExpenseOrderDAO(ExpenseOrder)
expense_order_item_dao = ExpenseOrderItemDAO(ExpenseOrderItem)
