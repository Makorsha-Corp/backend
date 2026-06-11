"""Project component service for business orchestration"""
from sqlalchemy.orm import Session
from app.dao.project_component import project_component_dao
from app.managers.project_manager import project_manager
from app.schemas.project_component import ProjectComponentCreate, ProjectComponentUpdate


class ProjectComponentService:
    """Service for project component workflows - handles transactions"""

    def get_components(
        self,
        db: Session,
        workspace_id: int,
        user_id: int,
        project_id: int = None,
        skip: int = 0,
        limit: int = 100,
    ):
        if project_id:
            project_manager.require_project_access(
                db, project_id, workspace_id, user_id
            )
            return project_component_dao.get_by_project(
                db,
                project_id=project_id,
                workspace_id=workspace_id,
                skip=skip,
                limit=limit,
            )

        all_components = project_component_dao.get_by_workspace(
            db, workspace_id=workspace_id, skip=skip, limit=limit
        )
        accessible = []
        for component in all_components:
            project = project_manager.project_dao.get_by_id_and_workspace(
                db, id=component.project_id, workspace_id=workspace_id
            )
            if project and project_manager.can_access_project(
                db, project, user_id, workspace_id
            ):
                accessible.append(component)
        return accessible

    def get_by_id(self, db: Session, component_id: int, workspace_id: int, user_id: int):
        project_manager.require_component_access(
            db, component_id, workspace_id, user_id
        )
        return project_component_dao.get_by_id_and_workspace(
            db, id=component_id, workspace_id=workspace_id
        )

    def create_component(
        self,
        db: Session,
        component_in: ProjectComponentCreate,
        workspace_id: int,
        user_id: int,
    ):
        try:
            project_manager.require_project_access(
                db, component_in.project_id, workspace_id, user_id
            )
            component_dict = component_in.model_dump()
            component_dict['workspace_id'] = workspace_id
            component = project_component_dao.create(db, obj_in=component_dict)
            project_manager.log_event(
                db,
                component_in.project_id,
                workspace_id,
                'component_created',
                f'Added component "{component.name}"',
                user_id,
                metadata={'component_id': component.id, 'component_name': component.name},
            )
            db.commit()
            db.refresh(component)
            return component
        except Exception:
            db.rollback()
            raise

    def update_component(
        self,
        db: Session,
        component_id: int,
        component_in: ProjectComponentUpdate,
        workspace_id: int,
        user_id: int,
    ):
        try:
            project_manager.require_component_access(
                db, component_id, workspace_id, user_id
            )
            component = project_component_dao.get_by_id_and_workspace(
                db, id=component_id, workspace_id=workspace_id
            )
            if not component:
                return None
            component = project_component_dao.update(
                db, db_obj=component, obj_in=component_in
            )
            project_manager.log_for_component(
                db,
                component_id,
                workspace_id,
                'component_updated',
                f'Updated component "{component.name}"',
                user_id,
            )
            db.commit()
            db.refresh(component)
            return component
        except Exception:
            db.rollback()
            raise

    def delete_component(
        self,
        db: Session,
        component_id: int,
        workspace_id: int,
        user_id: int,
    ):
        try:
            project_manager.require_component_access(
                db, component_id, workspace_id, user_id
            )
            component = project_component_dao.get_by_id_and_workspace(
                db, id=component_id, workspace_id=workspace_id
            )
            if not component:
                return False
            project_manager.log_for_component(
                db,
                component_id,
                workspace_id,
                'component_deleted',
                f'Deleted component "{component.name}"',
                user_id,
            )
            project_component_dao.remove(db, id=component_id)
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise


project_component_service = ProjectComponentService()
