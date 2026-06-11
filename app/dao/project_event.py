"""Project event DAO. SECURITY: All queries MUST filter by workspace_id."""
from typing import List
from sqlalchemy import desc
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.project_event import ProjectEvent
from app.schemas.project import ProjectEventResponse


class ProjectEventDAO(BaseDAO[ProjectEvent, ProjectEventResponse, ProjectEventResponse]):
    def get_by_project(
        self, db: Session, *, project_id: int, workspace_id: int
    ) -> List[ProjectEvent]:
        return (
            db.query(ProjectEvent)
            .filter(
                ProjectEvent.project_id == project_id,
                ProjectEvent.workspace_id == workspace_id,
            )
            .order_by(desc(ProjectEvent.created_at), desc(ProjectEvent.id))
            .all()
        )


project_event_dao = ProjectEventDAO(ProjectEvent)
