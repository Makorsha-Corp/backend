"""Project component activity event DAO. SECURITY: All queries MUST filter by workspace_id."""
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.dao.base import BaseDAO
from app.models.project_component_activity_event import ProjectComponentActivityEvent


class ProjectComponentActivityEventDAO(
    BaseDAO[ProjectComponentActivityEvent, object, object]
):
    def get_by_component(
        self,
        db: Session,
        *,
        project_component_id: int,
        workspace_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ProjectComponentActivityEvent]:
        return (
            db.query(ProjectComponentActivityEvent)
            .filter(
                ProjectComponentActivityEvent.project_component_id == project_component_id,
                ProjectComponentActivityEvent.workspace_id == workspace_id,
            )
            .order_by(desc(ProjectComponentActivityEvent.created_at), desc(ProjectComponentActivityEvent.id))
            .offset(skip)
            .limit(limit)
            .all()
        )


project_component_activity_event_dao = ProjectComponentActivityEventDAO(ProjectComponentActivityEvent)
