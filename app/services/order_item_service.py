"""Order item service for business orchestration"""
from datetime import datetime
from sqlalchemy.orm import Session
from app.dao.order_item import order_item_dao
from app.schemas.order_item import OrderItemCreate, OrderItemUpdate


class OrderItemService:
    """Service for order item workflows - handles transactions"""

    def get_items(self, db: Session, workspace_id: int, order_id: int = None, pending_approval: bool = None, skip: int = 0, limit: int = 100):
        """Get order items with optional filtering"""
        if order_id:
            return order_item_dao.get_by_order(db, order_id=order_id, workspace_id=workspace_id, skip=skip, limit=limit)
        elif pending_approval:
            return order_item_dao.get_pending_approval(db, workspace_id=workspace_id, skip=skip, limit=limit)
        else:
            return order_item_dao.get_by_workspace(db, workspace_id=workspace_id, skip=skip, limit=limit)

    def get_by_id(self, db: Session, item_id: int, workspace_id: int):
        """Get order item by ID"""
        return order_item_dao.get_by_id_and_workspace(db, id=item_id, workspace_id=workspace_id)

    def create_item(self, db: Session, item_in: OrderItemCreate, workspace_id: int):
        """Create order item with transaction management"""
        try:
            item_dict = item_in.model_dump()
            item_dict['workspace_id'] = workspace_id
            item = order_item_dao.create(db, obj_in=item_dict)
            db.commit()
            db.refresh(item)
            return item
        except Exception:
            db.rollback()
            raise

    def update_item(self, db: Session, item_id: int, item_in: OrderItemUpdate, workspace_id: int):
        """Update order item with transaction management"""
        try:
            item = order_item_dao.get_by_id_and_workspace(db, id=item_id, workspace_id=workspace_id)
            if not item:
                return None
            item = order_item_dao.update(db, db_obj=item, obj_in=item_in)
            db.commit()
            db.refresh(item)
            return item
        except Exception:
            db.rollback()
            raise

    def delete_item(self, db: Session, item_id: int, workspace_id: int):
        """Soft delete order item with transaction management"""
        try:
            item = order_item_dao.get_by_id_and_workspace(db, id=item_id, workspace_id=workspace_id)
            if not item:
                return False
            order_item_dao.update(db, db_obj=item, obj_in={"is_deleted": True, "deleted_at": datetime.utcnow()})
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise


order_item_service = OrderItemService()
