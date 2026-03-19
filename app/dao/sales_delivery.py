"""Sales delivery DAO operations"""
from typing import List
from sqlalchemy.orm import Session
from datetime import datetime, date
from app.dao.base import BaseDAO
from app.models.sales_delivery import SalesDelivery
from app.schemas.sales_delivery import SalesDeliveryCreate, SalesDeliveryUpdate


class DAOSalesDelivery(BaseDAO[SalesDelivery, SalesDeliveryCreate, SalesDeliveryUpdate]):
    """DAO operations for SalesDelivery model"""

    def generate_delivery_number(
        self, db: Session, *, workspace_id: int, year: int
    ) -> str:
        """
        Generate next delivery number for workspace and year
        Format: DEL-{year}-{sequence}

        Args:
            db: Database session
            workspace_id: Workspace ID
            year: Year for the delivery number

        Returns:
            Generated delivery number (e.g., "DEL-2025-001")
        """
        prefix = f"DEL-{year}-"
        count = (
            db.query(SalesDelivery)
            .filter(
                SalesDelivery.workspace_id == workspace_id,
                SalesDelivery.delivery_number.like(f"{prefix}%")
            )
            .count()
        )
        next_sequence = count + 1
        return f"{prefix}{next_sequence:03d}"

    def create_with_user(
        self,
        db: Session,
        *,
        obj_in: SalesDeliveryCreate,
        workspace_id: int,
        user_id: int
    ) -> SalesDelivery:
        """
        Create a new sales delivery with auto-generated number

        Args:
            db: Database session
            obj_in: Sales delivery creation schema
            workspace_id: Workspace ID
            user_id: Creator user ID

        Returns:
            Created sales delivery instance (not yet committed)
        """
        # Generate delivery number
        current_year = datetime.now().year
        delivery_number = self.generate_delivery_number(
            db, workspace_id=workspace_id, year=current_year
        )

        obj_in_data = obj_in.model_dump()
        db_obj = SalesDelivery(
            **obj_in_data,
            workspace_id=workspace_id,
            delivery_number=delivery_number,
            created_by=user_id
        )
        db.add(db_obj)
        db.flush()
        return db_obj

    def get_by_sales_order(
        self,
        db: Session,
        *,
        sales_order_id: int,
        workspace_id: int
    ) -> List[SalesDelivery]:
        """Get all deliveries for a sales order"""
        return (
            db.query(SalesDelivery)
            .filter(
                SalesDelivery.sales_order_id == sales_order_id,
                SalesDelivery.workspace_id == workspace_id
            )
            .all()
        )

    def get_by_status(
        self,
        db: Session,
        *,
        delivery_status: str,
        workspace_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[SalesDelivery]:
        """Get deliveries by status"""
        return (
            db.query(SalesDelivery)
            .filter(
                SalesDelivery.delivery_status == delivery_status,
                SalesDelivery.workspace_id == workspace_id
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_date_range(
        self,
        db: Session,
        *,
        start_date: date,
        end_date: date,
        workspace_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[SalesDelivery]:
        """Get deliveries within a date range"""
        return (
            db.query(SalesDelivery)
            .filter(
                SalesDelivery.workspace_id == workspace_id,
                SalesDelivery.scheduled_date >= start_date,
                SalesDelivery.scheduled_date <= end_date
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_pending_deliveries(
        self, db: Session, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[SalesDelivery]:
        """Get deliveries with status 'planned'"""
        return self.get_by_status(
            db, delivery_status='planned', workspace_id=workspace_id, skip=skip, limit=limit
        )


sales_delivery_dao = DAOSalesDelivery(SalesDelivery)
