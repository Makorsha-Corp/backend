"""Project component service for business orchestration"""
from sqlalchemy.orm import Session
from app.dao.project_component import project_component_dao
from app.schemas.project_component import ProjectComponentCreate, ProjectComponentUpdate


class ProjectComponentService:
    """Service for project component workflows - handles transactions"""

    def get_components(self, db: Session, workspace_id: int, project_id: int = None, skip: int = 0, limit: int = 100):
        """Get project components with optional filtering"""
        if project_id:
            return project_component_dao.get_by_project(db, project_id=project_id, workspace_id=workspace_id, skip=skip, limit=limit)
        else:
            return project_component_dao.get_by_workspace(db, workspace_id=workspace_id, skip=skip, limit=limit)

    def get_by_id(self, db: Session, component_id: int, workspace_id: int):
        """Get project component by ID"""
        return project_component_dao.get_by_id_and_workspace(db, id=component_id, workspace_id=workspace_id)

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
