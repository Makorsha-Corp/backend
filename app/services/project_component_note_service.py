"""Project component task service for business orchestration"""
from sqlalchemy.orm import Session
from app.dao.project_component_task import project_component_task_dao
from app.schemas.project_component_note import ProjectComponentNoteCreate, ProjectComponentNoteUpdate


class ProjectComponentNoteService:
    """Service for project component task workflows - handles transactions"""

    def get_notes(self, db: Session, project_component_id: int, workspace_id: int, skip: int = 0, limit: int = 100):
        """Get all project component notes, optionally filtered by component"""
        return project_component_task_dao.get_by_component(
            db, is_note=True, project_component_id=project_component_id, workspace_id=workspace_id, skip=skip, limit=limit
        )

    def get_by_id_and_workspace(self, db: Session, note_id: int, workspace_id: int):
        """Get project component note by ID and workspace"""
        return project_component_task_dao.get_by_id_and_workspace(
            db, id=note_id, workspace_id=workspace_id
        )

    def create_note(self, db: Session, note_in: ProjectComponentNoteCreate, workspace_id: int):
        """Create project component task with transaction management"""
        try:
            note_dict = note_in.model_dump()
            note_dict['workspace_id'] = workspace_id
            note_dict['is_note'] = True
            note = project_component_task_dao.create(db, obj_in=note_dict)
            db.commit()
            db.refresh(note)
            return note
        except Exception as e:
            db.rollback()
            raise

    def update_note(self, db: Session, note_id: int, note_in: ProjectComponentNoteUpdate, workspace_id: int):
        """Update project component task with transaction management"""
        try:
            note = project_component_task_dao.get_by_id_and_workspace(
                db, id=note_id, workspace_id=workspace_id
            )
            if not note:
                return None
            note = project_component_task_dao.update(db, db_obj=note, obj_in=note_in)
            db.commit()
            db.refresh(note)
            return note
        except Exception as e:
            db.rollback()
            raise

    def delete_note(self, db: Session, note_id: int, workspace_id: int):
        """Delete project component task with transaction management"""
        try:
            note = project_component_task_dao.get_by_id_and_workspace(
                db, id=note_id, workspace_id=workspace_id
            )
            if not note:
                return False
            project_component_task_dao.remove(db, id=note_id)
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            raise


project_component_note_service = ProjectComponentNoteService()
