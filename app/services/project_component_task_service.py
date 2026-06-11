"""Project component task service for business orchestration"""
from sqlalchemy.orm import Session
from app.dao.project_component_task import project_component_task_dao
from app.dao.project_component import project_component_dao
from app.managers.project_manager import project_manager
from app.schemas.project_component_task import ProjectComponentTaskCreate, ProjectComponentTaskUpdate


class ProjectComponentTaskService:
    """Service for project component task workflows - handles transactions"""

    def _guard_component(self, db: Session, component_id: int, workspace_id: int, user_id: int):
        project_manager.require_component_access(db, component_id, workspace_id, user_id)

    def _filter_accessible_tasks(self, db: Session, tasks, workspace_id: int, user_id: int):
        accessible = []
        for task in tasks:
            component = project_component_dao.get_by_id_and_workspace(
                db, id=task.project_component_id, workspace_id=workspace_id
            )
            if not component:
                continue
            project = project_manager.project_dao.get_by_id_and_workspace(
                db, id=component.project_id, workspace_id=workspace_id
            )
            if project and project_manager.can_access_project(
                db, project, user_id, workspace_id
            ):
                accessible.append(task)
        return accessible

    def get_tasks(
        self,
        db: Session,
        workspace_id: int,
        user_id: int,
        project_component_id: int = None,
        incomplete_only: bool = False,
        is_note: bool | None = None,
        skip: int = 0,
        limit: int = 100,
    ):
        if project_component_id:
            self._guard_component(db, project_component_id, workspace_id, user_id)
            if incomplete_only:
                return project_component_task_dao.get_incomplete_tasks(
                    db,
                    project_component_id=project_component_id,
                    workspace_id=workspace_id,
                    is_note=False if is_note is None else is_note,
                    skip=skip,
                    limit=limit,
                )
            return project_component_task_dao.get_by_component(
                db,
                project_component_id=project_component_id,
                workspace_id=workspace_id,
                is_note=is_note,
                skip=skip,
                limit=limit,
            )

        all_tasks = project_component_task_dao.get_by_workspace(
            db, workspace_id=workspace_id, skip=skip, limit=limit
        )
        return self._filter_accessible_tasks(db, all_tasks, workspace_id, user_id)

    def get_by_id(self, db: Session, task_id: int, workspace_id: int, user_id: int):
        task = project_component_task_dao.get_by_id_and_workspace(
            db, id=task_id, workspace_id=workspace_id
        )
        if not task:
            return None
        self._guard_component(db, task.project_component_id, workspace_id, user_id)
        return task

    def create_task(
        self,
        db: Session,
        task_in: ProjectComponentTaskCreate,
        workspace_id: int,
        user_id: int,
    ):
        try:
            self._guard_component(
                db, task_in.project_component_id, workspace_id, user_id
            )
            task_dict = task_in.model_dump()
            task_dict['workspace_id'] = workspace_id
            task = project_component_task_dao.create(db, obj_in=task_dict)
            if not task.is_note:
                project_manager.log_for_component(
                    db,
                    task.project_component_id,
                    workspace_id,
                    'task_created',
                    f'Added task "{task.name}"',
                    user_id,
                    metadata={'task_id': task.id, 'task_name': task.name},
                )
            db.commit()
            db.refresh(task)
            return task
        except Exception:
            db.rollback()
            raise

    def update_task(
        self,
        db: Session,
        task_id: int,
        task_in: ProjectComponentTaskUpdate,
        workspace_id: int,
        user_id: int,
    ):
        try:
            task = self.get_by_id(db, task_id, workspace_id, user_id)
            if not task:
                return None
            was_completed = task.is_completed
            update_fields = task_in.model_dump(exclude_unset=True)
            task = project_component_task_dao.update(db, db_obj=task, obj_in=task_in)
            if not task.is_note:
                if 'is_completed' in update_fields and task.is_completed != was_completed:
                    event_type = 'task_completed' if task.is_completed else 'task_reopened'
                    description = (
                        f'Completed task "{task.name}"'
                        if task.is_completed
                        else f'Reopened task "{task.name}"'
                    )
                else:
                    event_type = 'task_updated'
                    description = f'Updated task "{task.name}"'
                project_manager.log_for_component(
                    db,
                    task.project_component_id,
                    workspace_id,
                    event_type,
                    description,
                    user_id,
                    metadata={'task_id': task.id, 'task_name': task.name},
                )
            db.commit()
            db.refresh(task)
            return task
        except Exception:
            db.rollback()
            raise

    def delete_task(self, db: Session, task_id: int, workspace_id: int, user_id: int):
        try:
            task = self.get_by_id(db, task_id, workspace_id, user_id)
            if not task:
                return False
            if not task.is_note:
                project_manager.log_for_component(
                    db,
                    task.project_component_id,
                    workspace_id,
                    'task_deleted',
                    f'Deleted task "{task.name}"',
                    user_id,
                    metadata={'task_id': task.id, 'task_name': task.name},
                )
            project_component_task_dao.remove(db, id=task_id)
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise


project_component_task_service = ProjectComponentTaskService()
