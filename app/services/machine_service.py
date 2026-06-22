"""Machine Service for orchestrating machine workflows"""

from typing import List, Optional

from sqlalchemy.orm import Session



from app.services.base_service import BaseService

from app.managers.machine_manager import machine_manager

from app.managers.machine_activity_manager import machine_activity_manager

from app.models.machine import Machine

from app.models.enums import MachineEventTypeEnum

from app.schemas.machine import MachineCreate, MachineUpdate, MachineResponse

from app.schemas.machine_event import MachineEventCreate, MachineEventResponse

from app.schemas.machine_activity_event import (

    MachineActivityEventMetadata,

    MachineActivityEventResponse,

)





class MachineService(BaseService):

    """

    Service for Machine workflows.



    Handles transaction boundaries (commit/rollback).

    Delegates business logic to MachineManager.

    """



    def __init__(self):

        super().__init__()

        self.machine_manager = machine_manager

        self.activity_manager = machine_activity_manager



    def _to_machine_response(

        self,

        db: Session,

        machine: Machine,

        status_map: Optional[dict] = None,

    ) -> MachineResponse:

        if status_map is not None:

            latest = status_map.get(machine.id)

        else:

            latest = self.activity_manager.get_latest_status(

                db, machine.id, machine.workspace_id

            )

        status_str = machine_activity_manager.status_from_activity(latest)

        return MachineResponse.model_validate(machine).model_copy(
            update={
                "latest_status_type": (
                    MachineEventTypeEnum(status_str) if status_str else None
                ),
                "latest_status_at": latest.created_at if latest else None,
            }
        )



    def _to_machine_responses(

        self, db: Session, machines: List[Machine], workspace_id: int

    ) -> List[MachineResponse]:

        if not machines:

            return []

        status_map = self.activity_manager.get_latest_status_map(

            db, workspace_id=workspace_id, machine_ids=[m.id for m in machines]

        )

        return [

            self._to_machine_response(db, machine, status_map=status_map)

            for machine in machines

        ]



    # ==================== MACHINE CRUD ====================



    def create_machine(

        self, db: Session, machine_in: MachineCreate,

        workspace_id: int, user_id: int

    ) -> MachineResponse:

        """Create a new machine."""

        try:

            machine = self.machine_manager.create_machine(

                session=db, machine_data=machine_in,

                workspace_id=workspace_id, user_id=user_id

            )

            self._commit_transaction(db)

            db.refresh(machine)

            return self._to_machine_response(db, machine)

        except Exception:

            self._rollback_transaction(db)

            raise



    def get_machine(

        self, db: Session, machine_id: int, workspace_id: int

    ) -> MachineResponse:

        """Get machine by ID."""

        machine = self.machine_manager.get_machine(db, machine_id, workspace_id)

        return self._to_machine_response(db, machine)



    def get_machines(

        self, db: Session, workspace_id: int,

        factory_section_id: Optional[int] = None,

        is_running: Optional[bool] = None,

        search: Optional[str] = None,

        maintenance_window: str = "all",

        has_model_number: Optional[bool] = None,

        has_manufacturer: Optional[bool] = None,

        latest_event_type: Optional[MachineEventTypeEnum] = None,

        sort_by: str = "name",

        sort_dir: str = "asc",

        skip: int = 0, limit: int = 100

    ) -> List[MachineResponse]:

        """Get machines in workspace with optional filters."""

        machines = self.machine_manager.search_machines(

            session=db, workspace_id=workspace_id,

            factory_section_id=factory_section_id,

            is_running=is_running, search=search,

            maintenance_window=maintenance_window,

            has_model_number=has_model_number,

            has_manufacturer=has_manufacturer,

            latest_event_type=latest_event_type,

            sort_by=sort_by,

            sort_dir=sort_dir,

            skip=skip, limit=limit

        )

        return self._to_machine_responses(db, machines, workspace_id)



    def update_machine(

        self, db: Session, machine_id: int, machine_in: MachineUpdate,

        workspace_id: int, user_id: int

    ) -> MachineResponse:

        """Update machine metadata."""

        try:

            machine = self.machine_manager.update_machine(

                session=db, machine_id=machine_id,

                machine_data=machine_in,

                workspace_id=workspace_id, user_id=user_id

            )

            self._commit_transaction(db)

            db.refresh(machine)

            return self._to_machine_response(db, machine)

        except Exception:

            self._rollback_transaction(db)

            raise



    def delete_machine(

        self, db: Session, machine_id: int,

        workspace_id: int, user_id: int

    ) -> MachineResponse:

        """Soft delete machine."""

        try:

            machine = self.machine_manager.delete_machine(

                session=db, machine_id=machine_id,

                workspace_id=workspace_id, user_id=user_id

            )

            self._commit_transaction(db)

            db.refresh(machine)

            return self._to_machine_response(db, machine)

        except Exception:

            self._rollback_transaction(db)

            raise



    # ==================== MACHINE STATUS ====================



    def create_machine_event(

        self, db: Session, event_in: MachineEventCreate,

        workspace_id: int, user_id: int

    ) -> MachineEventResponse:

        """Create machine status change and sync is_running."""

        try:

            event = self.machine_manager.create_machine_event(

                session=db, event_data=event_in,

                workspace_id=workspace_id, user_id=user_id

            )

            self._commit_transaction(db)

            return event

        except Exception:

            self._rollback_transaction(db)

            raise



    def get_machine_activity(

        self,

        db: Session,

        machine_id: int,

        workspace_id: int,

        skip: int = 0,

        limit: int = 100,

    ) -> list[MachineActivityEventResponse]:

        """Get unified activity log for a machine."""

        rows = self.activity_manager.list_events(

            session=db,

            machine_id=machine_id,

            workspace_id=workspace_id,

            skip=skip,

            limit=limit,

        )

        return [

            MachineActivityEventResponse(

                id=e.id,

                workspace_id=e.workspace_id,

                machine_id=e.machine_id,

                event_type=e.event_type,

                description=e.description,

                metadata=(

                    MachineActivityEventMetadata.model_validate(e.metadata_json)

                    if e.metadata_json

                    else None

                ),

                performed_by=e.performed_by,

                performer_name=profile.name if profile else None,

                created_at=e.created_at,

            )

            for e, profile in rows

        ]





# Singleton instance

machine_service = MachineService()

