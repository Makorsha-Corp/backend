"""Sales delivery item DAO operations"""
from typing import List
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.sales_delivery_item import SalesDeliveryItem
from app.schemas.sales_delivery_item import SalesDeliveryItemCreate, SalesDeliveryItemUpdate


class DAOSalesDeliveryItem(BaseDAO[SalesDeliveryItem, SalesDeliveryItemCreate, SalesDeliveryItemUpdate]):
    """DAO operations for SalesDeliveryItem model"""

    def get_by_delivery(
        self,
        db: Session,
        *,
        delivery_id: int,
        workspace_id: int
    ) -> List[SalesDeliveryItem]:
        """Get all items for a delivery"""
        return (
            db.query(SalesDeliveryItem)
            .filter(
                SalesDeliveryItem.delivery_id == delivery_id,
                SalesDeliveryItem.workspace_id == workspace_id
            )
            .all()
        )

sales_delivery_item_dao = DAOSalesDeliveryItem(SalesDeliveryItem)
