"""Machine Service for orchestrating machine workflows"""
from typing import List, Optional
from sqlalchemy.orm import Session

from app.services.base_service import BaseService
from app.managers.machine_manager import machine_manager
from app.models.machine import Machine
from app.models.machine_event import MachineEvent
from app.models.enums import MachineEventTypeEnum
from app.schemas.machine import MachineCreate, MachineUpdate
from app.schemas.machine_event import MachineEventCreate


class MachineService(BaseService):
    """
    Service for Machine workflows.

    Handles transaction boundaries (commit/rollback).
    Delegates business logic to MachineManager.
    """

    def __init__(self):
        super().__init__()
        self.machine_manager = machine_manager

    # ==================== MACHINE CRUD ====================

    def create_machine(
        self, db: Session, machine_in: MachineCreate,
        workspace_id: int, user_id: int
    ) -> Machine:
        """Create a new machine."""
        try:
            machine = self.machine_manager.create_machine(
                session=db, machine_data=machine_in,
                workspace_id=workspace_id, user_id=user_id
            )
            self._commit_transaction(db)
            db.refresh(machine)
            return machine
        except Exception:
            self._rollback_transaction(db)
            raise

    def get_machine(
        self, db: Session, machine_id: int, workspace_id: int
    ) -> Machine:
        """Get machine by ID."""
        return self.machine_manager.get_machine(db, machine_id, workspace_id)

    def get_machines(
        self, db: Session, workspace_id: int,
        factory_section_id: Optional[int] = None,
        is_running: Optional[bool] = None,
        search: Optional[str] = None,
        skip: int = 0, limit: int = 100
    ) -> List[Machine]:
        """Get machines in workspace with optional filters."""
        return self.machine_manager.search_machines(
            session=db, workspace_id=workspace_id,
            factory_section_id=factory_section_id,
            is_running=is_running, search=search,
            skip=skip, limit=limit
        )

    def update_machine(
        self, db: Session, machine_id: int, machine_in: MachineUpdate,
        workspace_id: int, user_id: int
    ) -> Machine:
        """Update machine metadata."""
        try:
            machine = self.machine_manager.update_machine(
                session=db, machine_id=machine_id,
                machine_data=machine_in,
                workspace_id=workspace_id, user_id=user_id
            )
            self._commit_transaction(db)
            db.refresh(machine)
            return machine
        except Exception:
            self._rollback_transaction(db)
            raise

    def delete_machine(
        self, db: Session, machine_id: int,
        workspace_id: int, user_id: int
    ) -> Machine:
        """Soft delete machine."""
        try:
            machine = self.machine_manager.delete_machine(
                session=db, machine_id=machine_id,
                workspace_id=workspace_id, user_id=user_id
            )
            self._commit_transaction(db)
            db.refresh(machine)
            return machine
        except Exception:
            self._rollback_transaction(db)
            raise

    # ==================== MACHINE EVENTS ====================

    def create_machine_event(
        self, db: Session, event_in: MachineEventCreate,
        workspace_id: int, user_id: int
    ) -> MachineEvent:
        """Create machine event and sync is_running."""
        try:
            event = self.machine_manager.create_machine_event(
                session=db, event_data=event_in,
                workspace_id=workspace_id, user_id=user_id
            )
            self._commit_transaction(db)
            db.refresh(event)
            return event
        except Exception:
            self._rollback_transaction(db)
            raise

    def get_machine_events(
        self, db: Session, machine_id: int, workspace_id: int,
        event_type: Optional[MachineEventTypeEnum] = None,
        skip: int = 0, limit: int = 100
    ) -> List[MachineEvent]:
        """Get events for a machine."""
        return self.machine_manager.get_machine_events(
            session=db, machine_id=machine_id,
            workspace_id=workspace_id, event_type=event_type,
            skip=skip, limit=limit
        )

    def get_latest_machine_event(
        self, db: Session, machine_id: int, workspace_id: int
    ) -> Optional[MachineEvent]:
        """Get latest event for a machine."""
        return self.machine_manager.get_latest_machine_event(
            session=db, machine_id=machine_id,
            workspace_id=workspace_id
        )


# Singleton instance
machine_service = MachineService()
