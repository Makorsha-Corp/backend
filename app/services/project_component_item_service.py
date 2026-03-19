"""Project component item service for business orchestration"""
from sqlalchemy.orm import Session
from app.dao.project_component_item import project_component_item_dao
from app.schemas.project_component_item import ProjectComponentItemCreate, ProjectComponentItemUpdate


class ProjectComponentItemService:
    """Service for project component item workflows - handles transactions"""

    def create_component_item(self, db: Session, item_in: ProjectComponentItemCreate, workspace_id: int):
        """Create project component item with transaction management"""
        try:
            item_dict = item_in.model_dump()
            item_dict['workspace_id'] = workspace_id
            item = project_component_item_dao.create(db, obj_in=item_dict)
            db.commit()
            db.refresh(item)
            return item
        except Exception as e:
            db.rollback()
            raise

    def update_component_item(self, db: Session, item_id: int, item_in: ProjectComponentItemUpdate, workspace_id: int):
        """Update project component item with transaction management"""
        try:
            item = project_component_item_dao.get_by_id_and_workspace(
                db, id=item_id, workspace_id=workspace_id
            )
            if not item:
                return None
            item = project_component_item_dao.update(db, db_obj=item, obj_in=item_in)
            db.commit()
            db.refresh(item)
            return item
        except Exception as e:
            db.rollback()
            raise

    def delete_component_item(self, db: Session, item_id: int, workspace_id: int):
        """Delete project component item with transaction management"""
        try:
            item = project_component_item_dao.get_by_id_and_workspace(
                db, id=item_id, workspace_id=workspace_id
            )
            if not item:
                return False
            project_component_item_dao.remove(db, id=item_id)
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            raise


project_component_item_service = ProjectComponentItemService()
