"""Sales order item DAO operations"""
from typing import List
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.sales_order_item import SalesOrderItem
from app.schemas.sales_order_item import SalesOrderItemCreate, SalesOrderItemUpdate


class DAOSalesOrderItem(BaseDAO[SalesOrderItem, SalesOrderItemCreate, SalesOrderItemUpdate]):
    """DAO operations for SalesOrderItem model"""

    def get_by_sales_order(
        self,
        db: Session,
        *,
        sales_order_id: int,
        workspace_id: int
    ) -> List[SalesOrderItem]:
        """Get all items for a sales order"""
        return (
            db.query(SalesOrderItem)
            .filter(
                SalesOrderItem.sales_order_id == sales_order_id,
                SalesOrderItem.workspace_id == workspace_id
            )
            .all()
        )

    def get_by_item(
        self,
        db: Session,
        *,
        item_id: int,
        workspace_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[SalesOrderItem]:
        """Get all sales order items for a specific item"""
        return (
            db.query(SalesOrderItem)
            .filter(
                SalesOrderItem.item_id == item_id,
                SalesOrderItem.workspace_id == workspace_id
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

sales_order_item_dao = DAOSalesOrderItem(SalesOrderItem)
