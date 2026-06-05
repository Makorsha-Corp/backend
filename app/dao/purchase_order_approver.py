"""Purchase order approver DAO. SECURITY: All queries MUST filter by workspace_id."""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.purchase_order_approver import PurchaseOrderApprover
from app.schemas.purchase_order import PurchaseOrderApproverCreate


class PurchaseOrderApproverDAO(BaseDAO[PurchaseOrderApprover, PurchaseOrderApproverCreate, PurchaseOrderApproverCreate]):
    def get_by_order(
        self, db: Session, *, purchase_order_id: int, workspace_id: int
    ) -> List[PurchaseOrderApprover]:
        return (
            db.query(PurchaseOrderApprover)
            .filter(
                PurchaseOrderApprover.purchase_order_id == purchase_order_id,
                PurchaseOrderApprover.workspace_id == workspace_id,
            )
            .order_by(PurchaseOrderApprover.assigned_at)
            .all()
        )

    def get_by_order_and_user(
        self, db: Session, *, purchase_order_id: int, user_id: int, workspace_id: int
    ) -> Optional[PurchaseOrderApprover]:
        return (
            db.query(PurchaseOrderApprover)
            .filter(
                PurchaseOrderApprover.purchase_order_id == purchase_order_id,
                PurchaseOrderApprover.user_id == user_id,
                PurchaseOrderApprover.workspace_id == workspace_id,
            )
            .first()
        )


purchase_order_approver_dao = PurchaseOrderApproverDAO(PurchaseOrderApprover)
