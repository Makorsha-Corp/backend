"""Project component note service for business orchestration"""
from sqlalchemy.orm import Session
from app.dao.project_component_task import project_component_task_dao
from app.dao.project_component import project_component_dao
from app.managers.project_manager import project_manager
from app.schemas.project_component_note import ProjectComponentNoteCreate, ProjectComponentNoteUpdate


class ProjectComponentNoteService:
    """Service for project component notes."""

    def _guard_component(self, db: Session, component_id: int, workspace_id: int, user_id: int):
        project_manager.require_component_access(db, component_id, workspace_id, user_id)

    def _filter_accessible_notes(self, db: Session, notes, workspace_id: int, user_id: int):
        accessible = []
        for note in notes:
            component = project_component_dao.get_by_id_and_workspace(
                db, id=note.project_component_id, workspace_id=workspace_id
            )
            if not component:
                continue
            project = project_manager.project_dao.get_by_id_and_workspace(
                db, id=component.project_id, workspace_id=workspace_id
            )
            if project and project_manager.can_access_project(
                db, project, user_id, workspace_id
            ):
                accessible.append(note)
        return accessible

    def get_notes(
        self,
        db: Session,
        workspace_id: int,
        user_id: int,
        project_component_id: int | None = None,
        skip: int = 0,
        limit: int = 100,
    ):
        if project_component_id is None:
            from app.models.project_component_task import ProjectComponentTask

            notes = (
                db.query(ProjectComponentTask)
                .filter(
                    ProjectComponentTask.workspace_id == workspace_id,
                    ProjectComponentTask.is_note.is_(True),
                )
                .offset(skip)
                .limit(limit)
                .all()
            )
            return self._filter_accessible_notes(db, notes, workspace_id, user_id)

        self._guard_component(db, project_component_id, workspace_id, user_id)
        return project_component_task_dao.get_by_component(
            db,
            is_note=True,
            project_component_id=project_component_id,
            workspace_id=workspace_id,
            skip=skip,
            limit=limit,
        )

    def get_by_id_and_workspace(
        self, db: Session, note_id: int, workspace_id: int, user_id: int
    ):
        note = project_component_task_dao.get_by_id_and_workspace(
            db, id=note_id, workspace_id=workspace_id
        )
        if not note:
            return None
        self._guard_component(db, note.project_component_id, workspace_id, user_id)
        return note

    def create_note(
        self,
        db: Session,
        note_in: ProjectComponentNoteCreate,
        workspace_id: int,
        user_id: int,
    ):
        try:
            self._guard_component(
                db, note_in.project_component_id, workspace_id, user_id
            )
            note_dict = note_in.model_dump()
            note_dict['workspace_id'] = workspace_id
            note_dict['is_note'] = True
            note = project_component_task_dao.create(db, obj_in=note_dict)
            project_manager.log_for_component(
                db,
                note.project_component_id,
                workspace_id,
                'note_created',
                f'Added note "{note.name}"',
                user_id,
                metadata={'note_id': note.id, 'note_name': note.name},
            )
            db.commit()
            db.refresh(note)
            return note
        except Exception:
            db.rollback()
            raise

    def update_note(
        self,
        db: Session,
        note_id: int,
        note_in: ProjectComponentNoteUpdate,
        workspace_id: int,
        user_id: int,
    ):
        try:
            note = self.get_by_id_and_workspace(db, note_id, workspace_id, user_id)
            if not note:
                return None
            note = project_component_task_dao.update(db, db_obj=note, obj_in=note_in)
            project_manager.log_for_component(
                db,
                note.project_component_id,
                workspace_id,
                'note_updated',
                f'Updated note "{note.name}"',
                user_id,
                metadata={'note_id': note.id, 'note_name': note.name},
            )
            db.commit()
            db.refresh(note)
            return note
        except Exception:
            db.rollback()
            raise

    def delete_note(self, db: Session, note_id: int, workspace_id: int, user_id: int):
        try:
            note = self.get_by_id_and_workspace(db, note_id, workspace_id, user_id)
            if not note:
                return False
            project_manager.log_for_component(
                db,
                note.project_component_id,
                workspace_id,
                'note_deleted',
                f'Deleted note "{note.name}"',
                user_id,
                metadata={'note_id': note.id, 'note_name': note.name},
            )
            project_component_task_dao.remove(db, id=note_id)
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise


project_component_note_service = ProjectComponentNoteService()
