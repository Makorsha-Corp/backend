"""Damaged item service for business orchestration"""
from sqlalchemy.orm import Session
from app.dao.damaged_item import damaged_item_dao
from app.schemas.damaged_item import DamagedItemCreate, DamagedItemUpdate


class DamagedItemService:
    """Service for damaged item workflows - handles transactions"""

    def get_items(self, db: Session, workspace_id: int, factory_id: int = None, skip: int = 0, limit: int = 100):
        """Get damaged items with optional filtering"""
        if factory_id:
            return damaged_item_dao.get_by_factory(db, factory_id=factory_id, workspace_id=workspace_id, skip=skip, limit=limit)
        else:
            return damaged_item_dao.get_by_workspace(db, workspace_id=workspace_id, skip=skip, limit=limit)

    def get_by_id(self, db: Session, item_id: int, workspace_id: int):
        """Get damaged item by ID"""
        return damaged_item_dao.get_by_id_and_workspace(db, id=item_id, workspace_id=workspace_id)

    def create_item(self, db: Session, item_in: DamagedItemCreate, workspace_id: int):
        """Create damaged item with transaction management"""
        try:
            item_dict = item_in.model_dump()
            item_dict['workspace_id'] = workspace_id
            item = damaged_item_dao.create(db, obj_in=item_dict)
            db.commit()
            db.refresh(item)
            return item
        except Exception:
            db.rollback()
            raise

    def update_item(self, db: Session, item_id: int, item_in: DamagedItemUpdate, workspace_id: int):
        """Update damaged item with transaction management"""
        try:
            item = damaged_item_dao.get_by_id_and_workspace(db, id=item_id, workspace_id=workspace_id)
            if not item:
                return None
            item = damaged_item_dao.update(db, db_obj=item, obj_in=item_in)
            db.commit()
            db.refresh(item)
            return item
        except Exception:
            db.rollback()
            raise

    def delete_item(self, db: Session, item_id: int, workspace_id: int):
        """Delete damaged item with transaction management"""
        try:
            item = damaged_item_dao.get_by_id_and_workspace(db, id=item_id, workspace_id=workspace_id)
            if not item:
                return False
            damaged_item_dao.remove(db, id=item_id)
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise


damaged_item_service = DamagedItemService()
