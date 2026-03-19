"""DAO operations for OrderPartLog model (legacy audit trail)

SECURITY NOTICE:
This DAO handles workspace-scoped data. All query methods MUST filter by workspace_id
to prevent unauthorized cross-workspace data access.
"""
from typing import List
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.order_part_log import OrderPartLog
from app.schemas.order_part_log import OrderPartLogCreate


class DAOOrderPartLog(BaseDAO[OrderPartLog, OrderPartLogCreate, OrderPartLogCreate]):
    """DAO operations for OrderPartLog model (workspace-scoped, legacy audit trail)"""

    def get_by_order_part(
        self, db: Session, *, order_part_id: int, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[OrderPartLog]:
        """
        Get logs by order part ID (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            order_part_id: Order part (order item) ID to filter by
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of order part logs belonging to the workspace, ordered by most recent first
        """
        return (
            db.query(OrderPartLog)
            .filter(
                OrderPartLog.workspace_id == workspace_id,  # SECURITY: workspace isolation
                OrderPartLog.order_part_id == order_part_id
            )
            .order_by(OrderPartLog.updated_on.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )


order_part_log_dao = DAOOrderPartLog(OrderPartLog)
