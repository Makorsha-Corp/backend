"""Project component task service for business orchestration"""
from sqlalchemy.orm import Session
from app.dao.project_component_task import project_component_task_dao
from app.schemas.project_component_task import ProjectComponentTaskCreate, ProjectComponentTaskUpdate


class ProjectComponentTaskService:
    """Service for project component task workflows - handles transactions"""

    def create_task(self, db: Session, task_in: ProjectComponentTaskCreate, workspace_id: int):
        """Create project component task with transaction management"""
        try:
            task_dict = task_in.model_dump()
            task_dict['workspace_id'] = workspace_id
            task = project_component_task_dao.create(db, obj_in=task_dict)
            db.commit()
            db.refresh(task)
            return task
        except Exception as e:
            db.rollback()
            raise

    def update_task(self, db: Session, task_id: int, task_in: ProjectComponentTaskUpdate, workspace_id: int):
        """Update project component task with transaction management"""
        try:
            task = project_component_task_dao.get_by_id_and_workspace(
                db, id=task_id, workspace_id=workspace_id
            )
            if not task:
                return None
            task = project_component_task_dao.update(db, db_obj=task, obj_in=task_in)
            db.commit()
            db.refresh(task)
            return task
        except Exception as e:
            db.rollback()
            raise

    def delete_task(self, db: Session, task_id: int, workspace_id: int):
        """Delete project component task with transaction management"""
        try:
            task = project_component_task_dao.get_by_id_and_workspace(
                db, id=task_id, workspace_id=workspace_id
            )
            if not task:
                return False
            project_component_task_dao.remove(db, id=task_id)
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            raise


project_component_task_service = ProjectComponentTaskService()
