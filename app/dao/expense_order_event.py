"""Expense order event DAO. SECURITY: All queries MUST filter by workspace_id."""
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.dao.base import BaseDAO
from app.models.expense_order_event import ExpenseOrderEvent


class ExpenseOrderEventDAO(BaseDAO[ExpenseOrderEvent, object, object]):
    def get_by_order(
        self, db: Session, *, expense_order_id: int, workspace_id: int
    ) -> List[ExpenseOrderEvent]:
        return (
            db.query(ExpenseOrderEvent)
            .filter(
                ExpenseOrderEvent.expense_order_id == expense_order_id,
                ExpenseOrderEvent.workspace_id == workspace_id,
            )
            .order_by(desc(ExpenseOrderEvent.created_at), desc(ExpenseOrderEvent.id))
            .all()
        )


expense_order_event_dao = ExpenseOrderEventDAO(ExpenseOrderEvent)
