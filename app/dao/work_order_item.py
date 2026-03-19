"""Work order item DAO

SECURITY: All queries MUST filter by workspace_id.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.work_order_item import WorkOrderItem
from app.schemas.work_order_item import WorkOrderItemCreate, WorkOrderItemUpdate


class WorkOrderItemDAO(BaseDAO[WorkOrderItem, WorkOrderItemCreate, WorkOrderItemUpdate]):
    """DAO for WorkOrderItem model (workspace-scoped)"""

    def get_by_work_order(
        self, db: Session, *, work_order_id: int, workspace_id: int
    ) -> List[WorkOrderItem]:
        """Get all items for a work order."""
        return db.query(WorkOrderItem).filter(
            WorkOrderItem.work_order_id == work_order_id,
            WorkOrderItem.workspace_id == workspace_id,
        ).all()

    def get_by_id_and_workspace(
        self, db: Session, *, id: int, workspace_id: int
    ) -> Optional[WorkOrderItem]:
        """Get item by ID with workspace isolation."""
        return db.query(WorkOrderItem).filter(
            WorkOrderItem.id == id,
            WorkOrderItem.workspace_id == workspace_id,
        ).first()


work_order_item_dao = WorkOrderItemDAO(WorkOrderItem)
