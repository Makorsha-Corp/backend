"""Machine activity event manager - unified audit log for machines."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.dao.machine import machine_dao
from app.dao.machine_activity_event import machine_activity_event_dao
from app.dao.profile import profile_dao
from app.models.machine_activity_event import MachineActivityEvent

MACHINE_LOG_FIELDS: dict[str, str] = {
    "name": "Name",
    "factory_id": "Factory",
    "factory_section_id": "Section",
    "model_number": "Model number",
    "manufacturer": "Manufacturer",
    "note": "Note",
    "next_maintenance_schedule": "Next maintenance date",
    "next_maintenance_note": "Next maintenance note",
}

MACHINE_ITEM_LOG_FIELDS: dict[str, str] = {
    "qty": "Quantity",
    "req_qty": "Required quantity",
    "defective_qty": "Defective quantity",
}


class MachineActivityManager:
    """Append-only machine activity log."""

    def __init__(self) -> None:
        self.event_dao = machine_activity_event_dao
        self.machine_dao = machine_dao

    @staticmethod
    def format_field_value(value: Any) -> str | None:
        if value is None:
            return None
        if hasattr(value, "value"):
            return str(value.value)
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M")
        if isinstance(value, date):
            return value.isoformat()
        return str(value)

    def collect_field_changes(
        self,
        record: Any,
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
            changes.append(
                {
                    "field": field,
                    "label": label,
                    "from_value": self.format_field_value(old_val),
                    "to_value": self.format_field_value(new_val),
                }
            )
        return changes

    def log_event(
        self,
        session: Session,
        machine_id: int,
        workspace_id: int,
        event_type: str,
        description: str,
        performed_by: Optional[int] = None,
        metadata: dict | None = None,
    ) -> MachineActivityEvent:
        ev = MachineActivityEvent(
            workspace_id=workspace_id,
            machine_id=machine_id,
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
        machine_id: int,
        workspace_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Tuple[MachineActivityEvent, Optional[Any]]]:
        machine = self.machine_dao.get_by_id_and_workspace(
            session, id=machine_id, workspace_id=workspace_id
        )
        if not machine:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Machine with ID {machine_id} not found",
            )
        events = self.event_dao.get_by_machine(
            session,
            machine_id=machine_id,
            workspace_id=workspace_id,
            skip=skip,
            limit=limit,
        )
        return [
            (e, profile_dao.get(session, id=e.performed_by) if e.performed_by else None)
            for e in events
        ]

    def get_latest_status(
        self,
        session: Session,
        machine_id: int,
        workspace_id: int,
    ) -> Optional[MachineActivityEvent]:
        self.machine_dao.get_by_id_and_workspace(
            session, id=machine_id, workspace_id=workspace_id
        )  # 404 if missing
        return self.event_dao.get_latest_status_by_machine(
            session, machine_id=machine_id, workspace_id=workspace_id
        )

    def get_latest_status_map(
        self,
        session: Session,
        workspace_id: int,
        machine_ids: List[int],
    ) -> dict[int, MachineActivityEvent]:
        return self.event_dao.get_latest_status_map(
            session, workspace_id=workspace_id, machine_ids=machine_ids
        )

    @staticmethod
    def status_from_activity(event: Optional[MachineActivityEvent]) -> Optional[str]:
        if not event or not event.metadata_json:
            return None
        return event.metadata_json.get("status")


machine_activity_manager = MachineActivityManager()
