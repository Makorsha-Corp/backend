"""
Project Manager

Business logic for project operations.
"""
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from datetime import datetime

from app.managers.base_manager import BaseManager
from app.models.project import Project
from app.models.project_event import ProjectEvent
from app.models.project_member import ProjectMember
from app.models.enums import ProjectVisibilityEnum
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.dao.project import project_dao
from app.dao.factory import factory_dao
from app.dao.project_event import project_event_dao
from app.dao.project_member import project_member_dao
from app.dao.workspace_member import workspace_member_dao
from app.dao.workspace import workspace_dao
from app.dao.profile import profile_dao
from app.models.profile import Profile

PRIVILEGED_ROLES = frozenset({'owner', 'ground-team-manager'})

PROJECT_LOG_FIELDS = {
    'name': 'Name',
    'description': 'Description',
    'budget': 'Budget',
    'deadline': 'Deadline',
    'start_date': 'Start date',
    'end_date': 'End date',
    'priority': 'Priority',
    'status': 'Status',
    'factory_id': 'Factory',
    'visibility': 'Visibility',
}


class ProjectManager(BaseManager[Project]):
    """Manager for project business logic."""

    def __init__(self):
        super().__init__(Project)
        self.project_dao = project_dao
        self.factory_dao = factory_dao
        self.event_dao = project_event_dao
        self.member_dao = project_member_dao

    def _visibility_value(self, project: Project) -> str:
        vis = project.visibility
        if vis is None:
            return ProjectVisibilityEnum.WORKSPACE.value
        if isinstance(vis, ProjectVisibilityEnum):
            return vis.value
        return str(vis)

    def _is_workspace_owner(self, session: Session, user_id: int, workspace_id: int) -> bool:
        workspace = workspace_dao.get(session, id=workspace_id)
        return bool(workspace and workspace.owner_user_id == user_id)

    def _is_privileged(self, session: Session, user_id: int, workspace_id: int) -> bool:
        if self._is_workspace_owner(session, user_id, workspace_id):
            return True
        member = workspace_member_dao.get_by_workspace_and_user(
            session, workspace_id=workspace_id, user_id=user_id
        )
        return bool(member and member.status == 'active' and member.role in PRIVILEGED_ROLES)

    def can_access_project(
        self,
        session: Session,
        project: Project,
        user_id: int,
        workspace_id: int,
    ) -> bool:
        if self._visibility_value(project) == ProjectVisibilityEnum.WORKSPACE.value:
            return True
        if self._is_privileged(session, user_id, workspace_id):
            return True
        if project.created_by == user_id:
            return True
        return bool(
            self.member_dao.get_by_project_and_user(
                session,
                project_id=project.id,
                user_id=user_id,
                workspace_id=workspace_id,
            )
        )

    def _get_project_or_404(
        self,
        session: Session,
        project_id: int,
        workspace_id: int,
    ) -> Project:
        project = self.project_dao.get_by_id_and_workspace(
            session, id=project_id, workspace_id=workspace_id
        )
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID {project_id} not found",
            )
        return project

    def require_project_access(
        self,
        session: Session,
        project_id: int,
        workspace_id: int,
        user_id: int,
    ) -> Project:
        project = self._get_project_or_404(session, project_id, workspace_id)
        if not self.can_access_project(session, project, user_id, workspace_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this project",
            )
        return project

    def require_component_access(
        self,
        session: Session,
        component_id: int,
        workspace_id: int,
        user_id: int,
    ) -> int:
        from app.dao.project_component import project_component_dao

        component = project_component_dao.get_by_id_and_workspace(
            session, id=component_id, workspace_id=workspace_id
        )
        if not component:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project component not found",
            )
        self.require_project_access(
            session, component.project_id, workspace_id, user_id
        )
        return component.project_id

    def _format_field_value(self, value) -> str | None:
        if value is None:
            return None
        if hasattr(value, 'value'):
            return str(value.value)
        if isinstance(value, datetime):
            return value.strftime('%Y-%m-%d')
        return str(value)

    def _collect_field_changes(
        self,
        record: Project,
        update_dict: dict,
        fields: dict[str, str],
    ) -> List[dict]:
        changes: List[dict] = []
        for field, label in fields.items():
            if field not in update_dict:
                continue
            old_val = getattr(record, field)
            new_val = update_dict[field]
            if old_val == new_val:
                continue
            changes.append({
                'field': field,
                'label': label,
                'from_value': self._format_field_value(old_val),
                'to_value': self._format_field_value(new_val),
            })
        return changes

    def log_for_component(
        self,
        session: Session,
        component_id: int,
        workspace_id: int,
        event_type: str,
        description: str,
        performed_by: Optional[int] = None,
        metadata: dict | None = None,
    ) -> Optional[ProjectEvent]:
        from app.dao.project_component import project_component_dao

        component = project_component_dao.get_by_id_and_workspace(
            session, id=component_id, workspace_id=workspace_id
        )
        if not component:
            return None
        event_metadata = dict(metadata or {})
        event_metadata.setdefault('component_id', component.id)
        event_metadata.setdefault('component_name', component.name)
        return self.log_event(
            session,
            component.project_id,
            workspace_id,
            event_type,
            description,
            performed_by,
            event_metadata,
        )

    def log_event(
        self,
        session: Session,
        project_id: int,
        workspace_id: int,
        event_type: str,
        description: str,
        performed_by: Optional[int] = None,
        metadata: dict | None = None,
    ) -> ProjectEvent:
        ev = ProjectEvent(
            workspace_id=workspace_id,
            project_id=project_id,
            event_type=event_type,
            description=description,
            metadata_json=metadata,
            performed_by=performed_by,
        )
        session.add(ev)
        session.flush()
        return ev

    def list_events(
        self,
        session: Session,
        project_id: int,
        workspace_id: int,
        user_id: int,
    ) -> List[Tuple[ProjectEvent, Optional[Profile]]]:
        self.require_project_access(session, project_id, workspace_id, user_id)
        events = self.event_dao.get_by_project(
            session, project_id=project_id, workspace_id=workspace_id
        )
        return [
            (e, profile_dao.get(session, id=e.performed_by) if e.performed_by else None)
            for e in events
        ]

    def list_members(
        self,
        session: Session,
        project_id: int,
        workspace_id: int,
        user_id: int,
    ) -> List[ProjectMember]:
        self.require_project_access(session, project_id, workspace_id, user_id)
        return self.member_dao.get_by_project(
            session, project_id=project_id, workspace_id=workspace_id
        )

    def add_member(
        self,
        session: Session,
        project_id: int,
        member_user_id: int,
        workspace_id: int,
        assigned_by: int,
    ) -> ProjectMember:
        self.require_project_access(session, project_id, workspace_id, assigned_by)
        member = workspace_member_dao.get_by_workspace_and_user(
            session, workspace_id=workspace_id, user_id=member_user_id
        )
        if not member or member.status != 'active':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is not an active member of this workspace",
            )
        existing = self.member_dao.get_by_project_and_user(
            session,
            project_id=project_id,
            user_id=member_user_id,
            workspace_id=workspace_id,
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User is already a member of this project",
            )
        obj = ProjectMember(
            workspace_id=workspace_id,
            project_id=project_id,
            user_id=member_user_id,
            assigned_by=assigned_by,
        )
        session.add(obj)
        session.flush()
        profile = profile_dao.get(session, id=member_user_id)
        user_name = profile.name if profile else f'User #{member_user_id}'
        self.log_event(
            session,
            project_id,
            workspace_id,
            'member_added',
            f'Added {user_name} to the project',
            assigned_by,
            metadata={'user_id': member_user_id, 'user_name': user_name},
        )
        return obj

    def remove_member(
        self,
        session: Session,
        project_id: int,
        member_user_id: int,
        workspace_id: int,
        performed_by: int,
    ) -> None:
        self.require_project_access(session, project_id, workspace_id, performed_by)
        project = self._get_project_or_404(session, project_id, workspace_id)
        if project.created_by == member_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove the project creator from members",
            )
        rec = self.member_dao.get_by_project_and_user(
            session,
            project_id=project_id,
            user_id=member_user_id,
            workspace_id=workspace_id,
        )
        if not rec:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project member not found",
            )
        profile = profile_dao.get(session, id=member_user_id)
        user_name = profile.name if profile else f'User #{member_user_id}'
        session.delete(rec)
        session.flush()
        self.log_event(
            session,
            project_id,
            workspace_id,
            'member_removed',
            f'Removed {user_name} from the project',
            performed_by,
            metadata={'user_id': member_user_id, 'user_name': user_name},
        )

    def set_visibility(
        self,
        session: Session,
        project_id: int,
        visibility: ProjectVisibilityEnum,
        workspace_id: int,
        user_id: int,
    ) -> Project:
        project = self.require_project_access(session, project_id, workspace_id, user_id)
        if project.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot update deleted project",
            )
        if self._visibility_value(project) == visibility.value:
            return project
        old_label = self._visibility_value(project)
        project.visibility = visibility.value
        project.updated_by = user_id
        project.updated_at = datetime.utcnow()
        session.add(project)
        session.flush()
        self.log_event(
            session,
            project_id,
            workspace_id,
            'visibility_updated',
            f'Changed visibility from {old_label} to {visibility.value}',
            user_id,
            metadata={
                'changes': [{
                    'field': 'visibility',
                    'label': 'Visibility',
                    'from_value': old_label,
                    'to_value': visibility.value,
                }],
            },
        )
        return project

    def create_project(
        self,
        session: Session,
        project_data: ProjectCreate,
        workspace_id: int,
        user_id: int,
    ) -> Project:
        factory = self.factory_dao.get_by_id_and_workspace(
            session, id=project_data.factory_id, workspace_id=workspace_id
        )
        if not factory:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Factory with ID {project_data.factory_id} not found",
            )
        if factory.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot create project for deleted factory",
            )

        project_dict = project_data.model_dump()
        project_dict['workspace_id'] = workspace_id
        project_dict['created_by'] = user_id
        project_dict['is_active'] = True
        project_dict['is_deleted'] = False
        project_dict['visibility'] = ProjectVisibilityEnum.WORKSPACE.value

        project = self.project_dao.create(session, obj_in=project_dict)

        session.add(ProjectMember(
            workspace_id=workspace_id,
            project_id=project.id,
            user_id=user_id,
            assigned_by=user_id,
        ))
        session.flush()

        self.log_event(
            session,
            project.id,
            workspace_id,
            'created',
            f'Created project "{project.name}"',
            user_id,
        )
        return project

    def get_project(
        self,
        session: Session,
        project_id: int,
        workspace_id: int,
        user_id: int,
    ) -> Project:
        return self.require_project_access(session, project_id, workspace_id, user_id)

    def list_projects(
        self,
        session: Session,
        workspace_id: int,
        user_id: int,
        factory_id: Optional[int] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Project]:
        if factory_id:
            projects = self.project_dao.get_by_factory(
                session,
                factory_id=factory_id,
                workspace_id=workspace_id,
                skip=skip,
                limit=limit,
            )
        elif status:
            from app.models.enums import ProjectStatusEnum
            projects = self.project_dao.get_by_status(
                session,
                status=ProjectStatusEnum(status),
                workspace_id=workspace_id,
                skip=skip,
                limit=limit,
            )
        else:
            projects = self.project_dao.get_by_workspace(
                session, workspace_id=workspace_id, skip=skip, limit=limit
            )

        if self._is_privileged(session, user_id, workspace_id):
            return projects

        return [
            p for p in projects
            if self.can_access_project(session, p, user_id, workspace_id)
        ]

    def update_project(
        self,
        session: Session,
        project_id: int,
        project_data: ProjectUpdate,
        workspace_id: int,
        user_id: int,
    ) -> Project:
        project = self.require_project_access(session, project_id, workspace_id, user_id)

        if project.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot update deleted project",
            )

        update_dict = project_data.model_dump(exclude_unset=True, exclude_none=True)
        changes = self._collect_field_changes(project, update_dict, PROJECT_LOG_FIELDS)
        update_dict['updated_by'] = user_id
        update_dict['updated_at'] = datetime.utcnow()

        updated_project = self.project_dao.update(
            session, db_obj=project, obj_in=update_dict
        )

        if changes:
            status_changes = [c for c in changes if c['field'] == 'status']
            other_changes = [c for c in changes if c['field'] != 'status']
            if status_changes:
                self.log_event(
                    session,
                    project_id,
                    workspace_id,
                    'status_updated',
                    'Changed project status',
                    user_id,
                    metadata={'changes': status_changes},
                )
            if other_changes:
                self.log_event(
                    session,
                    project_id,
                    workspace_id,
                    'updated',
                    'Updated project details',
                    user_id,
                    metadata={'changes': other_changes},
                )

        return updated_project

    def delete_project(
        self,
        session: Session,
        project_id: int,
        workspace_id: int,
        user_id: int,
    ) -> Project:
        project = self.require_project_access(session, project_id, workspace_id, user_id)

        if project.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Project is already deleted",
            )

        project.is_deleted = True
        project.deleted_at = datetime.utcnow()
        project.deleted_by = user_id
        session.add(project)
        session.flush()

        self.log_event(
            session,
            project_id,
            workspace_id,
            'deleted',
            f'Deactivated project "{project.name}"',
            user_id,
        )
        return project


project_manager = ProjectManager()
