"""
Machine Manager

Business logic for machine operations including status tracking via activity events.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.managers.base_manager import BaseManager
from app.models.machine import Machine
from app.models.enums import MachineEventTypeEnum
from app.schemas.machine import MachineCreate, MachineUpdate
from app.schemas.machine_event import MachineEventCreate, MachineEventResponse
from app.dao.machine import machine_dao
from app.dao.factory_section import factory_section_dao
from app.managers.machine_activity_manager import (
    machine_activity_manager,
    MACHINE_LOG_FIELDS,
)


class MachineManager(BaseManager[Machine]):
    """
    Manager for machine business logic.

    Handles:
    - Machine CRUD with workspace isolation and factory section validation
    - Machine status changes via activity events with is_running synchronization
    - Soft delete with validation
    """

    def __init__(self):
        super().__init__(Machine)
        self.machine_dao = machine_dao
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
        machine_activity_manager.log_event(
            session,
            machine.id,
            workspace_id,
            "created",
            f"Machine created: {machine.name}",
            performed_by=user_id,
        )
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

        update_dict = machine_data.model_dump(exclude_unset=True, exclude_none=True)
        update_dict['updated_by'] = user_id

        changes = machine_activity_manager.collect_field_changes(
            machine, update_dict, MACHINE_LOG_FIELDS
        )
        updated_machine = self.machine_dao.update(session, db_obj=machine, obj_in=update_dict)
        if changes:
            machine_activity_manager.log_event(
                session,
                machine_id,
                workspace_id,
                "updated",
                "Machine details updated",
                performed_by=user_id,
                metadata={"changes": changes},
            )
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
        maintenance_window: str = "all",
        has_model_number: Optional[bool] = None,
        has_manufacturer: Optional[bool] = None,
        latest_event_type: Optional[MachineEventTypeEnum] = None,
        sort_by: str = "name",
        sort_dir: str = "asc",
        skip: int = 0,
        limit: int = 100,
        include_deleted: bool = False
    ) -> List[Machine]:
        """Search machines in workspace with optional filters."""
        if include_deleted:
            # Preserve existing behavior for include_deleted callers.
            machines = self.machine_dao.get_by_workspace(
                session, workspace_id=workspace_id, skip=skip, limit=limit
            )
            if factory_section_id is not None:
                machines = [m for m in machines if m.factory_section_id == factory_section_id]
            if is_running is not None:
                machines = [m for m in machines if m.is_running == is_running]
            if search:
                s = search.lower()
                machines = [
                    m for m in machines
                    if s in m.name.lower()
                    or (m.model_number and s in m.model_number.lower())
                    or (m.manufacturer and s in m.manufacturer.lower())
                ]
            return machines

        return self.machine_dao.search_advanced(
            session,
            workspace_id=workspace_id,
            factory_section_id=factory_section_id,
            is_running=is_running,
            search=search,
            maintenance_window=maintenance_window,
            has_model_number=has_model_number,
            has_manufacturer=has_manufacturer,
            latest_event_type=latest_event_type,
            sort_by=sort_by,
            sort_dir=sort_dir,
            skip=skip,
            limit=limit,
        )

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
        machine_activity_manager.log_event(
            session,
            machine_id,
            workspace_id,
            "deactivated",
            f"Machine deactivated: {machine.name}",
            performed_by=user_id,
        )
        return deleted_machine

    # ==================== MACHINE STATUS ====================

    def create_machine_event(
        self,
        session: Session,
        event_data: MachineEventCreate,
        workspace_id: int,
        user_id: int
    ) -> MachineEventResponse:
        """
        Record a machine status change in the activity log and sync is_running.

        Business rule: RUNNING -> is_running=True, all others -> is_running=False.
        """
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

        latest_activity = machine_activity_manager.get_latest_status(
            session, event_data.machine_id, workspace_id
        )
        prev_status = machine_activity_manager.status_from_activity(latest_activity)
        new_status = event_data.event_type.value
        if prev_status and prev_status == new_status:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Machine is already in '{new_status}' state"
            )

        activity = machine_activity_manager.log_event(
            session,
            event_data.machine_id,
            workspace_id,
            "status_updated",
            f"Status set to {new_status.lower()}",
            performed_by=user_id,
            metadata={
                "status": new_status,
                "changes": [
                    {
                        "field": "status",
                        "label": "Status",
                        "from_value": prev_status,
                        "to_value": new_status,
                    }
                ],
            },
        )

        new_is_running = (event_data.event_type == MachineEventTypeEnum.RUNNING)
        if machine.is_running != new_is_running:
            self.machine_dao.update(
                session, db_obj=machine,
                obj_in={'is_running': new_is_running, 'updated_by': user_id}
            )

        return MachineEventResponse(
            id=activity.id,
            workspace_id=workspace_id,
            machine_id=event_data.machine_id,
            event_type=event_data.event_type,
            started_at=activity.created_at,
            initiated_by=user_id,
            note=event_data.note,
            created_at=activity.created_at,
            created_by=user_id,
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
