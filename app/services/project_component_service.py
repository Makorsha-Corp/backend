"""Project component service for business orchestration"""
from sqlalchemy.orm import Session
from app.dao.project_component import project_component_dao
from app.schemas.project_component import ProjectComponentCreate, ProjectComponentUpdate


class ProjectComponentService:
    """Service for project component workflows - handles transactions"""

    def create_component(self, db: Session, component_in: ProjectComponentCreate, workspace_id: int):
        """Create project component with transaction management"""
        try:
            component_dict = component_in.model_dump()
            component_dict['workspace_id'] = workspace_id
            component = project_component_dao.create(db, obj_in=component_dict)
            db.commit()
            db.refresh(component)
            return component
        except Exception as e:
            db.rollback()
            raise

    def update_component(self, db: Session, component_id: int, component_in: ProjectComponentUpdate, workspace_id: int):
        """Update project component with transaction management"""
        try:
            component = project_component_dao.get_by_id_and_workspace(
                db, id=component_id, workspace_id=workspace_id
            )
            if not component:
                return None
            component = project_component_dao.update(db, db_obj=component, obj_in=component_in)
            db.commit()
            db.refresh(component)
            return component
        except Exception as e:
            db.rollback()
            raise

    def delete_component(self, db: Session, component_id: int, workspace_id: int):
        """Delete project component with transaction management"""
        try:
            component = project_component_dao.get_by_id_and_workspace(
                db, id=component_id, workspace_id=workspace_id
            )
            if not component:
                return False
            project_component_dao.remove(db, id=component_id)
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            raise


project_component_service = ProjectComponentService()
