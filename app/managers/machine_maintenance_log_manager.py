"""Machine Maintenance Log Manager

Business logic for machine maintenance log operations.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.managers.base_manager import BaseManager
from app.models.machine_maintenance_log import MachineMaintenanceLog
from app.models.enums import MaintenanceTypeEnum
from app.schemas.machine_maintenance_log import MachineMaintenanceLogCreate, MachineMaintenanceLogUpdate
from app.dao.machine_maintenance_log import machine_maintenance_log_dao
from app.dao.machine import machine_dao


class MachineMaintenanceLogManager(BaseManager[MachineMaintenanceLog]):
    """Manager for machine maintenance log business logic."""

    def __init__(self):
        super().__init__(MachineMaintenanceLog)
        self.log_dao = machine_maintenance_log_dao
        self.machine_dao = machine_dao

    def create_log(
        self,
        session: Session,
        log_data: MachineMaintenanceLogCreate,
        workspace_id: int,
        user_id: int
    ) -> MachineMaintenanceLog:
        """Create a maintenance log entry. Validates machine exists in workspace."""
        machine = self.machine_dao.get_by_id_and_workspace(
            session, id=log_data.machine_id, workspace_id=workspace_id
        )
        if not machine:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Machine with ID {log_data.machine_id} not found"
            )
        if machine.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot create maintenance log for a deleted machine"
            )

        log_dict = log_data.model_dump()
        log_dict['workspace_id'] = workspace_id
        log_dict['created_by'] = user_id

        return self.log_dao.create(session, obj_in=log_dict)

    def update_log(
        self,
        session: Session,
        log_id: int,
        log_data: MachineMaintenanceLogUpdate,
        workspace_id: int,
        user_id: int
    ) -> MachineMaintenanceLog:
        """Update a maintenance log entry."""
        log = self.log_dao.get_by_id_and_workspace(
            session, id=log_id, workspace_id=workspace_id
        )
        if not log:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Maintenance log with ID {log_id} not found"
            )
        if log.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot update a deleted maintenance log"
            )

        update_dict = log_data.model_dump(exclude_unset=True)
        update_dict['updated_by'] = user_id

        return self.log_dao.update(session, db_obj=log, obj_in=update_dict)

    def get_log(
        self, session: Session, log_id: int, workspace_id: int
    ) -> MachineMaintenanceLog:
        """Get a maintenance log by ID."""
        log = self.log_dao.get_by_id_and_workspace(
            session, id=log_id, workspace_id=workspace_id
        )
        if not log:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Maintenance log with ID {log_id} not found"
            )
        return log

    def list_logs(
        self,
        session: Session,
        workspace_id: int,
        machine_id: Optional[int] = None,
        maintenance_type: Optional[MaintenanceTypeEnum] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[MachineMaintenanceLog]:
        """List maintenance logs with optional filters."""
        if machine_id and maintenance_type:
            return self.log_dao.get_by_machine_and_type(
                session, machine_id, maintenance_type,
                workspace_id=workspace_id, skip=skip, limit=limit
            )
        if machine_id:
            return self.log_dao.get_by_machine(
                session, machine_id,
                workspace_id=workspace_id, skip=skip, limit=limit
            )
        if maintenance_type:
            return self.log_dao.get_by_type(
                session, maintenance_type,
                workspace_id=workspace_id, skip=skip, limit=limit
            )
        return self.log_dao.get_by_workspace(
            session, workspace_id=workspace_id, skip=skip, limit=limit
        )

    def delete_log(
        self,
        session: Session,
        log_id: int,
        workspace_id: int,
        user_id: int
    ) -> MachineMaintenanceLog:
        """Soft delete a maintenance log."""
        log = self.log_dao.get_by_id_and_workspace(
            session, id=log_id, workspace_id=workspace_id
        )
        if not log:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Maintenance log with ID {log_id} not found"
            )
        if log.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maintenance log is already deleted"
            )

        return self.log_dao.soft_delete(session, db_obj=log, deleted_by=user_id)


# Singleton instance
machine_maintenance_log_manager = MachineMaintenanceLogManager()
