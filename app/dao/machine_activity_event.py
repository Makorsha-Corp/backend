"""Machine activity event DAO. SECURITY: All queries MUST filter by workspace_id."""
from typing import Dict, List, Optional

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.machine_activity_event import MachineActivityEvent
from app.schemas.machine_activity_event import MachineActivityEventResponse


class MachineActivityEventDAO(
    BaseDAO[MachineActivityEvent, MachineActivityEventResponse, MachineActivityEventResponse]
):
    def get_by_machine(
        self,
        db: Session,
        *,
        machine_id: int,
        workspace_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[MachineActivityEvent]:
        return (
            db.query(MachineActivityEvent)
            .filter(
                MachineActivityEvent.machine_id == machine_id,
                MachineActivityEvent.workspace_id == workspace_id,
            )
            .order_by(desc(MachineActivityEvent.created_at), desc(MachineActivityEvent.id))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_latest_status_by_machine(
        self,
        db: Session,
        *,
        machine_id: int,
        workspace_id: int,
    ) -> Optional[MachineActivityEvent]:
        return (
            db.query(MachineActivityEvent)
            .filter(
                MachineActivityEvent.machine_id == machine_id,
                MachineActivityEvent.workspace_id == workspace_id,
                MachineActivityEvent.event_type == "status_updated",
            )
            .order_by(desc(MachineActivityEvent.created_at), desc(MachineActivityEvent.id))
            .first()
        )

    def get_latest_status_map(
        self,
        db: Session,
        *,
        workspace_id: int,
        machine_ids: List[int],
    ) -> Dict[int, MachineActivityEvent]:
        if not machine_ids:
            return {}

        latest_created_subq = (
            db.query(
                MachineActivityEvent.machine_id.label("machine_id"),
                func.max(MachineActivityEvent.created_at).label("latest_created_at"),
            )
            .filter(
                MachineActivityEvent.workspace_id == workspace_id,
                MachineActivityEvent.event_type == "status_updated",
                MachineActivityEvent.machine_id.in_(machine_ids),
            )
            .group_by(MachineActivityEvent.machine_id)
            .subquery()
        )

        rows = (
            db.query(MachineActivityEvent)
            .join(
                latest_created_subq,
                and_(
                    MachineActivityEvent.machine_id == latest_created_subq.c.machine_id,
                    MachineActivityEvent.created_at == latest_created_subq.c.latest_created_at,
                ),
            )
            .filter(
                MachineActivityEvent.workspace_id == workspace_id,
                MachineActivityEvent.event_type == "status_updated",
            )
            .all()
        )
        return {row.machine_id: row for row in rows}


machine_activity_event_dao = MachineActivityEventDAO(MachineActivityEvent)
