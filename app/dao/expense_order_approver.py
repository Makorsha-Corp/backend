"""Expense order approver DAO. SECURITY: All queries MUST filter by workspace_id."""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.expense_order_approver import ExpenseOrderApprover
from app.schemas.expense_order import ExpenseOrderApproverCreate


class ExpenseOrderApproverDAO(BaseDAO[ExpenseOrderApprover, ExpenseOrderApproverCreate, ExpenseOrderApproverCreate]):
    def get_by_order(
        self, db: Session, *, expense_order_id: int, workspace_id: int
    ) -> List[ExpenseOrderApprover]:
        return (
            db.query(ExpenseOrderApprover)
            .filter(
                ExpenseOrderApprover.expense_order_id == expense_order_id,
                ExpenseOrderApprover.workspace_id == workspace_id,
            )
            .order_by(ExpenseOrderApprover.assigned_at)
            .all()
        )

    def get_by_order_and_user(
        self, db: Session, *, expense_order_id: int, user_id: int, workspace_id: int
    ) -> Optional[ExpenseOrderApprover]:
        return (
            db.query(ExpenseOrderApprover)
            .filter(
                ExpenseOrderApprover.expense_order_id == expense_order_id,
                ExpenseOrderApprover.user_id == user_id,
                ExpenseOrderApprover.workspace_id == workspace_id,
            )
            .first()
        )


expense_order_approver_dao = ExpenseOrderApproverDAO(ExpenseOrderApprover)
