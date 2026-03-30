"""Storage item service for business orchestration"""
from sqlalchemy.orm import Session
from app.dao.storage_item import storage_item_dao
from app.schemas.storage_item import StorageItemCreate, StorageItemUpdate


class StorageItemService:
    """Service for storage item workflows - handles transactions"""

    def get_items(self, db: Session, workspace_id: int, factory_id: int = None, skip: int = 0, limit: int = 100):
        """Get storage items with optional filtering"""
        if factory_id:
            return storage_item_dao.get_by_factory(db, factory_id=factory_id, workspace_id=workspace_id, skip=skip, limit=limit)
        else:
            return storage_item_dao.get_by_workspace(db, workspace_id=workspace_id, skip=skip, limit=limit)

    def get_by_id(self, db: Session, item_id: int, workspace_id: int):
        """Get storage item by ID"""
        return storage_item_dao.get_by_id_and_workspace(db, id=item_id, workspace_id=workspace_id)

    def create_item(self, db: Session, item_in: StorageItemCreate, workspace_id: int):
        """Create storage item with transaction management"""
        try:
            item_dict = item_in.model_dump()
            item_dict['workspace_id'] = workspace_id
            item = storage_item_dao.create(db, obj_in=item_dict)
            db.commit()
            db.refresh(item)
            return item
        except Exception:
            db.rollback()
            raise

    def update_item(self, db: Session, item_id: int, item_in: StorageItemUpdate, workspace_id: int):
        """Update storage item with transaction management"""
        try:
            item = storage_item_dao.get_by_id_and_workspace(db, id=item_id, workspace_id=workspace_id)
            if not item:
                return None
            item = storage_item_dao.update(db, db_obj=item, obj_in=item_in)
            db.commit()
            db.refresh(item)
            return item
        except Exception:
            db.rollback()
            raise

    def delete_item(self, db: Session, item_id: int, workspace_id: int):
        """Delete storage item with transaction management"""
        try:
            item = storage_item_dao.get_by_id_and_workspace(db, id=item_id, workspace_id=workspace_id)
            if not item:
                return False
            storage_item_dao.remove(db, id=item_id)
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise


storage_item_service = StorageItemService()
