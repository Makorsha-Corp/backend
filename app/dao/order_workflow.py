"""DAO operations for OrderWorkflow model

SECURITY NOTICE:
This DAO handles workspace-scoped data. All query methods MUST filter by workspace_id
to prevent unauthorized cross-workspace data access.
"""
from typing import Optional
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.order_workflow import OrderWorkflow
from app.schemas.order_workflow import OrderWorkflowCreate, OrderWorkflowUpdate


class DAOOrderWorkflow(BaseDAO[OrderWorkflow, OrderWorkflowCreate, OrderWorkflowUpdate]):
    """DAO operations for OrderWorkflow model (workspace-scoped)"""

    def get_by_type(
        self, db: Session, *, workflow_type: str, workspace_id: int
    ) -> Optional[OrderWorkflow]:
        """
        Get workflow by type (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            workflow_type: Workflow type to find (e.g., 'PFM', 'STM', 'MTM')
            workspace_id: Workspace ID to filter by

        Returns:
            OrderWorkflow instance or None if not found
        """
        return (
            db.query(OrderWorkflow)
            .filter(
                OrderWorkflow.workspace_id == workspace_id,  # SECURITY: workspace isolation
                OrderWorkflow.type == workflow_type
            )
            .first()
        )


order_workflow_dao = DAOOrderWorkflow(OrderWorkflow)
