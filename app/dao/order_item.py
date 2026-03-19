"""DAO operations for OrderItem model (workspace-scoped)"""
from typing import List
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.order_item import OrderItem
from app.schemas.order_item import OrderItemCreate, OrderItemUpdate


class DAOOrderItem(BaseDAO[OrderItem, OrderItemCreate, OrderItemUpdate]):
    """
    DAO operations for OrderItem model.

    SECURITY: All methods MUST filter by workspace_id to prevent cross-workspace data access.
    """

    def get_by_order(
        self, db: Session, *, order_id: int, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[OrderItem]:
        """
        Get order items by order ID (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            order_id: Order ID
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of order items belonging to the workspace
        """
        return (
            db.query(OrderItem)
            .filter(
                OrderItem.workspace_id == workspace_id,  # SECURITY: workspace isolation
                OrderItem.order_id == order_id
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_pending_approval(
        self, db: Session, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[OrderItem]:
        """
        Get order items pending approval (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of pending order items belonging to the workspace

        Security Note:
            WITHOUT workspace filter, this would return pending items from ALL workspaces!
        """
        return (
            db.query(OrderItem)
            .filter(
                OrderItem.workspace_id == workspace_id,  # SECURITY: CRITICAL filter
                OrderItem.approved_pending_order == False
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_vendor(
        self, db: Session, *, vendor_id: int, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[OrderItem]:
        """
        Get order items by vendor ID (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            vendor_id: Vendor ID
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of order items for vendor belonging to the workspace
        """
        return (
            db.query(OrderItem)
            .filter(
                OrderItem.workspace_id == workspace_id,  # SECURITY: workspace isolation
                OrderItem.vendor_id == vendor_id
            )
            .offset(skip)
            .limit(limit)
            .all()
        )


order_item_dao = DAOOrderItem(OrderItem)
