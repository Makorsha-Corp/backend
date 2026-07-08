"""Work order approver DAO. SECURITY: All queries MUST filter by workspace_id."""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.work_order_approver import WorkOrderApprover
from app.schemas.work_order import WorkOrderApproverCreate


class WorkOrderApproverDAO(BaseDAO[WorkOrderApprover, WorkOrderApproverCreate, WorkOrderApproverCreate]):
    def get_by_order(
        self, db: Session, *, work_order_id: int, workspace_id: int
    ) -> List[WorkOrderApprover]:
        return (
            db.query(WorkOrderApprover)
            .filter(
                WorkOrderApprover.work_order_id == work_order_id,
                WorkOrderApprover.workspace_id == workspace_id,
            )
            .order_by(WorkOrderApprover.assigned_at)
            .all()
        )

    def get_by_order_and_user(
        self, db: Session, *, work_order_id: int, user_id: int, workspace_id: int
    ) -> Optional[WorkOrderApprover]:
        return (
            db.query(WorkOrderApprover)
            .filter(
                WorkOrderApprover.work_order_id == work_order_id,
                WorkOrderApprover.user_id == user_id,
                WorkOrderApprover.workspace_id == workspace_id,
            )
            .first()
        )


work_order_approver_dao = WorkOrderApproverDAO(WorkOrderApprover)
