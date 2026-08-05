"""Sales order approver DAO. SECURITY: All queries MUST filter by workspace_id."""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.sales_order_approver import SalesOrderApprover
from app.schemas.sales_order import SalesOrderApproverCreate


class SalesOrderApproverDAO(BaseDAO[SalesOrderApprover, SalesOrderApproverCreate, SalesOrderApproverCreate]):
    def get_by_order(
        self, db: Session, *, sales_order_id: int, workspace_id: int
    ) -> List[SalesOrderApprover]:
        return (
            db.query(SalesOrderApprover)
            .filter(
                SalesOrderApprover.sales_order_id == sales_order_id,
                SalesOrderApprover.workspace_id == workspace_id,
            )
            .order_by(SalesOrderApprover.assigned_at)
            .all()
        )

    def get_by_order_and_user(
        self, db: Session, *, sales_order_id: int, user_id: int, workspace_id: int
    ) -> Optional[SalesOrderApprover]:
        return (
            db.query(SalesOrderApprover)
            .filter(
                SalesOrderApprover.sales_order_id == sales_order_id,
                SalesOrderApprover.user_id == user_id,
                SalesOrderApprover.workspace_id == workspace_id,
            )
            .first()
        )


sales_order_approver_dao = SalesOrderApproverDAO(SalesOrderApprover)
