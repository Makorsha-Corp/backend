"""Sales order DAO operations"""
from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime
from app.dao.base import BaseDAO
from app.models.sales_order import SalesOrder
from app.schemas.sales_order import SalesOrderCreate, SalesOrderUpdate


class DAOSalesOrder(BaseDAO[SalesOrder, SalesOrderCreate, SalesOrderUpdate]):
    """DAO operations for SalesOrder model"""

    def generate_sales_order_number(
        self, db: Session, *, workspace_id: int, year: int
    ) -> str:
        """
        Generate next sales order number for workspace and year
        Format: SO-{year}-{sequence}

        Args:
            db: Database session
            workspace_id: Workspace ID
            year: Year for the order number

        Returns:
            Generated sales order number (e.g., "SO-2025-001")
        """
        # Get count of orders in this workspace for this year
        prefix = f"SO-{year}-"
        count = (
            db.query(SalesOrder)
            .filter(
                SalesOrder.workspace_id == workspace_id,
                SalesOrder.sales_order_number.like(f"{prefix}%")
            )
            .count()
        )
        next_sequence = count + 1
        return f"{prefix}{next_sequence:03d}"

    def create_with_user(
        self,
        db: Session,
        *,
        obj_in: SalesOrderCreate,
        workspace_id: int,
        user_id: int
    ) -> SalesOrder:
        """
        Create a new sales order with auto-generated number

        Args:
            db: Database session
            obj_in: Sales order creation schema
            workspace_id: Workspace ID
            user_id: Creator user ID

        Returns:
            Created sales order instance (not yet committed)
        """
        # Generate sales order number
        current_year = datetime.now().year
        sales_order_number = self.generate_sales_order_number(
            db, workspace_id=workspace_id, year=current_year
        )

        obj_in_data = obj_in.model_dump()
        db_obj = SalesOrder(
            **obj_in_data,
            workspace_id=workspace_id,
            sales_order_number=sales_order_number,
            created_by=user_id
        )
        db.add(db_obj)
        db.flush()
        return db_obj

    def get_by_account(
        self,
        db: Session,
        *,
        account_id: int,
        workspace_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[SalesOrder]:
        """Get sales orders by customer account"""
        return (
            db.query(SalesOrder)
            .filter(
                SalesOrder.account_id == account_id,
                SalesOrder.workspace_id == workspace_id
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_factory(
        self,
        db: Session,
        *,
        factory_id: int,
        workspace_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[SalesOrder]:
        """Get sales orders by factory"""
        return (
            db.query(SalesOrder)
            .filter(
                SalesOrder.factory_id == factory_id,
                SalesOrder.workspace_id == workspace_id
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_status(
        self,
        db: Session,
        *,
        status_id: int,
        workspace_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[SalesOrder]:
        """Get sales orders by status"""
        return (
            db.query(SalesOrder)
            .filter(
                SalesOrder.current_status_id == status_id,
                SalesOrder.workspace_id == workspace_id
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_pending_deliveries(
        self, db: Session, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[SalesOrder]:
        """Get sales orders with pending deliveries"""
        return (
            db.query(SalesOrder)
            .filter(
                SalesOrder.is_fully_delivered == False,
                SalesOrder.workspace_id == workspace_id
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_uninvoiced_orders(
        self, db: Session, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[SalesOrder]:
        """Get sales orders that haven't been invoiced"""
        return (
            db.query(SalesOrder)
            .filter(
                SalesOrder.is_invoiced == False,
                SalesOrder.workspace_id == workspace_id
            )
            .offset(skip)
            .limit(limit)
            .all()
        )


sales_order_dao = DAOSalesOrder(SalesOrder)
