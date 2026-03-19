"""Order DAO operations (workspace-scoped)"""
from typing import List
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.order import Order
from app.schemas.order import OrderCreate, OrderUpdate


class DAOOrder(BaseDAO[Order, OrderCreate, OrderUpdate]):
    """
    DAO operations for Order model.

    SECURITY: All methods MUST filter by workspace_id to prevent cross-workspace data access.
    """

    def create_with_user(
        self, db: Session, *, obj_in: OrderCreate, workspace_id: int, user_id: int
    ) -> Order:
        """
        Create a new order with user ID (SECURITY-CRITICAL: sets workspace_id)

        Args:
            db: Database session
            obj_in: Order creation schema
            workspace_id: Workspace ID to assign
            user_id: Creator user ID

        Returns:
            Created order instance (not yet committed)

        Note:
            Uses flush() to make the object visible within the transaction.
            The service layer must call commit() to persist changes.

        Security Note:
            CRITICAL: workspace_id MUST be set during creation to ensure workspace isolation.
            Without this, orders would be created without workspace assignment!
        """
        obj_in_data = obj_in.model_dump()
        db_obj = Order(
            **obj_in_data,
            workspace_id=workspace_id,  # SECURITY: CRITICAL - assign workspace
            created_by_user_id=user_id,
            current_status_id=1  # Default to status 1 (Pending)
        )
        db.add(db_obj)
        db.flush()  # Flush to get ID, but don't commit
        return db_obj

    def get_by_factory(
        self, db: Session, *, factory_id: int, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[Order]:
        """
        Get orders by factory (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            factory_id: Factory ID
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of orders for the factory in the workspace
        """
        return (
            db.query(Order)
            .filter(
                Order.workspace_id == workspace_id,  # SECURITY: workspace isolation
                Order.factory_id == factory_id
            )
            .offset(skip)
            .limit(limit)
            .all()
        )


order_dao = DAOOrder(Order)
