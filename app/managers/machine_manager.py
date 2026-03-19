"""
Machine Manager

Business logic for machine operations including status tracking via events.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.managers.base_manager import BaseManager
from app.models.machine import Machine
from app.models.machine_event import MachineEvent
from app.models.enums import MachineEventTypeEnum
from app.schemas.machine import MachineCreate, MachineUpdate
from app.schemas.machine_event import MachineEventCreate
from app.dao.machine import machine_dao
from app.dao.machine_event import machine_event_dao
from app.dao.factory_section import factory_section_dao


class MachineManager(BaseManager[Machine]):
    """
    Manager for machine business logic.

    Handles:
    - Machine CRUD with workspace isolation and factory section validation
    - Machine event creation with automatic is_running synchronization
    - Soft delete with validation
    """

    def __init__(self):
        super().__init__(Machine)
        self.machine_dao = machine_dao
        self.machine_event_dao = machine_event_dao
        self.factory_section_dao = factory_section_dao

    # ==================== MACHINE CRUD ====================

    def create_machine(
        self,
        session: Session,
        machine_data: MachineCreate,
        workspace_id: int,
        user_id: int
    ) -> Machine:
        """
        Create new machine.

        Validates factory section exists and belongs to workspace.
        New machines default to is_running=False.
        """
        # Validate factory section exists and belongs to workspace
        section = self.factory_section_dao.get_by_id_and_workspace(
            session, id=machine_data.factory_section_id, workspace_id=workspace_id
        )
        if not section:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Factory section with ID {machine_data.factory_section_id} not found"
            )
        if section.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot create machine in a deleted factory section"
            )

        # Check for duplicate name in the same section
        existing = self._check_name_exists_in_section(
            session, workspace_id=workspace_id,
            factory_section_id=machine_data.factory_section_id,
            name=machine_data.name
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Machine with name '{machine_data.name}' already exists in this section"
            )

        # Create machine with audit fields
        machine_dict = machine_data.model_dump()
        machine_dict['workspace_id'] = workspace_id
        machine_dict['created_by'] = user_id
        machine_dict['is_running'] = False

        machine = self.machine_dao.create(session, obj_in=machine_dict)
        return machine

    def update_machine(
        self,
        session: Session,
        machine_id: int,
        machine_data: MachineUpdate,
        workspace_id: int,
        user_id: int
    ) -> Machine:
        """Update machine metadata (does NOT change is_running -- use events for that)."""
        machine = self.machine_dao.get_by_id_and_workspace(
            session, id=machine_id, workspace_id=workspace_id
        )
        if not machine:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Machine with ID {machine_id} not found"
            )
        if machine.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot update a deleted machine"
            )

        # If factory_section_id is being changed, validate new section
        if machine_data.factory_section_id and machine_data.factory_section_id != machine.factory_section_id:
            section = self.factory_section_dao.get_by_id_and_workspace(
                session, id=machine_data.factory_section_id, workspace_id=workspace_id
            )
            if not section:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Factory section with ID {machine_data.factory_section_id} not found"
                )
            if section.is_deleted:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot move machine to a deleted factory section"
                )

        # Check name uniqueness in target section
        target_section_id = machine_data.factory_section_id if machine_data.factory_section_id else machine.factory_section_id
        if machine_data.name and machine_data.name != machine.name:
            if self._check_name_exists_in_section(
                session, workspace_id=workspace_id,
                factory_section_id=target_section_id,
                name=machine_data.name,
                exclude_id=machine_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Machine with name '{machine_data.name}' already exists in this section"
                )

        update_dict = machine_data.model_dump(exclude_unset=True)
        update_dict['updated_by'] = user_id

        updated_machine = self.machine_dao.update(session, db_obj=machine, obj_in=update_dict)
        return updated_machine

    def get_machine(
        self,
        session: Session,
        machine_id: int,
        workspace_id: int
    ) -> Machine:
        """Get machine by ID with workspace validation."""
        machine = self.machine_dao.get_by_id_and_workspace(
            session, id=machine_id, workspace_id=workspace_id
        )
        if not machine:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Machine with ID {machine_id} not found"
            )
        return machine

    def search_machines(
        self,
        session: Session,
        workspace_id: int,
        factory_section_id: Optional[int] = None,
        is_running: Optional[bool] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
        include_deleted: bool = False
    ) -> List[Machine]:
        """Search machines in workspace with optional filters."""
        if factory_section_id:
            machines = self.machine_dao.get_by_section(
                session, factory_section_id=factory_section_id,
                workspace_id=workspace_id, include_deleted=include_deleted,
                skip=skip, limit=limit
            )
        else:
            if include_deleted:
                machines = self.machine_dao.get_by_workspace(
                    session, workspace_id=workspace_id, skip=skip, limit=limit
                )
            else:
                machines = self.machine_dao.get_active_by_workspace(
                    session, workspace_id=workspace_id, skip=skip, limit=limit
                )

        # Apply is_running filter
        if is_running is not None:
            machines = [m for m in machines if m.is_running == is_running]

        # Apply search filter
        if search:
            search_lower = search.lower()
            machines = [
                m for m in machines
                if search_lower in m.name.lower()
                or (m.model_number and search_lower in m.model_number.lower())
                or (m.manufacturer and search_lower in m.manufacturer.lower())
            ]

        return machines

    def delete_machine(
        self,
        session: Session,
        machine_id: int,
        workspace_id: int,
        user_id: int
    ) -> Machine:
        """Soft delete machine."""
        machine = self.machine_dao.get_by_id_and_workspace(
            session, id=machine_id, workspace_id=workspace_id
        )
        if not machine:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Machine with ID {machine_id} not found"
            )
        if machine.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Machine is already deleted"
            )

        deleted_machine = self.machine_dao.soft_delete(session, db_obj=machine, deleted_by=user_id)
        return deleted_machine

    # ==================== MACHINE EVENTS ====================

    def create_machine_event(
        self,
        session: Session,
        event_data: MachineEventCreate,
        workspace_id: int,
        user_id: int
    ) -> MachineEvent:
        """
        Create a machine event and synchronize machine.is_running.

        Business rule: RUNNING -> is_running=True, all others -> is_running=False.
        """
        # Validate machine exists and belongs to workspace
        machine = self.machine_dao.get_by_id_and_workspace(
            session, id=event_data.machine_id, workspace_id=workspace_id
        )
        if not machine:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Machine with ID {event_data.machine_id} not found"
            )
        if machine.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot create event for a deleted machine"
            )

        # Check for redundant event (same status as current latest)
        latest_event = self.machine_event_dao.get_latest_by_machine(
            session, event_data.machine_id, workspace_id=workspace_id
        )
        if latest_event and latest_event.event_type == event_data.event_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Machine is already in '{event_data.event_type.value}' state"
            )

        # Create event record
        event_dict = event_data.model_dump()
        event_dict['workspace_id'] = workspace_id
        event_dict['initiated_by'] = user_id
        event_dict['created_by'] = user_id

        event = self.machine_event_dao.create(session, obj_in=event_dict)

        # Synchronize machine.is_running based on event type
        new_is_running = (event_data.event_type == MachineEventTypeEnum.RUNNING)
        if machine.is_running != new_is_running:
            self.machine_dao.update(
                session, db_obj=machine,
                obj_in={'is_running': new_is_running, 'updated_by': user_id}
            )

        return event

    def get_machine_events(
        self,
        session: Session,
        machine_id: int,
        workspace_id: int,
        event_type: Optional[MachineEventTypeEnum] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[MachineEvent]:
        """Get events for a machine with optional type filter."""
        # Validate machine exists
        machine = self.machine_dao.get_by_id_and_workspace(
            session, id=machine_id, workspace_id=workspace_id
        )
        if not machine:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Machine with ID {machine_id} not found"
            )

        if event_type:
            return self.machine_event_dao.get_by_machine_and_type(
                session, machine_id, event_type,
                workspace_id=workspace_id, skip=skip, limit=limit
            )
        return self.machine_event_dao.get_by_machine(
            session, machine_id, workspace_id=workspace_id,
            skip=skip, limit=limit
        )

    def get_latest_machine_event(
        self,
        session: Session,
        machine_id: int,
        workspace_id: int
    ) -> Optional[MachineEvent]:
        """Get the latest event for a machine."""
        machine = self.machine_dao.get_by_id_and_workspace(
            session, id=machine_id, workspace_id=workspace_id
        )
        if not machine:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Machine with ID {machine_id} not found"
            )

        return self.machine_event_dao.get_latest_by_machine(
            session, machine_id, workspace_id=workspace_id
        )

    # ==================== HELPER METHODS ====================

    def _check_name_exists_in_section(
        self,
        session: Session,
        workspace_id: int,
        factory_section_id: int,
        name: str,
        exclude_id: Optional[int] = None
    ) -> bool:
        """Check if machine name already exists in a factory section (excluding deleted)."""
        machines = self.machine_dao.get_by_section(
            session, factory_section_id=factory_section_id,
            workspace_id=workspace_id
        )
        for machine in machines:
            if machine.name == name and (exclude_id is None or machine.id != exclude_id):
                return True
        return False


# Singleton instance
machine_manager = MachineManager()
