"""Project component activity event manager - append-only audit log for project components."""
from __future__ import annotations

from typing import List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.dao.profile import profile_dao
from app.dao.project_component import project_component_dao
from app.dao.project_component_activity_event import project_component_activity_event_dao
from app.models.project_component_activity_event import ProjectComponentActivityEvent


class ProjectComponentActivityManager:
    """Append-only project component activity log."""

    def __init__(self) -> None:
        self.event_dao = project_component_activity_event_dao
        self.component_dao = project_component_dao

    def log_event(
        self,
        session: Session,
        project_component_id: int,
        workspace_id: int,
        event_type: str,
        description: str,
        performed_by: Optional[int] = None,
        metadata: dict | None = None,
    ) -> ProjectComponentActivityEvent:
        ev = ProjectComponentActivityEvent(
            workspace_id=workspace_id,
            project_component_id=project_component_id,
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
        project_component_id: int,
        workspace_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Tuple[ProjectComponentActivityEvent, Optional[object]]]:
        component = self.component_dao.get_by_id_and_workspace(
            session, id=project_component_id, workspace_id=workspace_id
        )
        if not component:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project component with ID {project_component_id} not found",
            )
        events = self.event_dao.get_by_component(
            session,
            project_component_id=project_component_id,
            workspace_id=workspace_id,
            skip=skip,
            limit=limit,
        )
        return [
            (e, profile_dao.get(session, id=e.performed_by) if e.performed_by else None)
            for e in events
        ]


project_component_activity_manager = ProjectComponentActivityManager()
