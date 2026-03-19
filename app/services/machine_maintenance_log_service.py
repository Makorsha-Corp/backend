"""Machine Maintenance Log Service for orchestrating maintenance log workflows"""
from typing import List, Optional
from sqlalchemy.orm import Session

from app.services.base_service import BaseService
from app.managers.machine_maintenance_log_manager import machine_maintenance_log_manager
from app.models.machine_maintenance_log import MachineMaintenanceLog
from app.models.enums import MaintenanceTypeEnum
from app.schemas.machine_maintenance_log import MachineMaintenanceLogCreate, MachineMaintenanceLogUpdate


class MachineMaintenanceLogService(BaseService):
    """Service for machine maintenance log workflows. Handles commit/rollback."""

    def __init__(self):
        super().__init__()
        self.manager = machine_maintenance_log_manager

    def create_log(
        self, db: Session, log_in: MachineMaintenanceLogCreate,
        workspace_id: int, user_id: int
    ) -> MachineMaintenanceLog:
        """Create a maintenance log entry."""
        try:
            log = self.manager.create_log(
                session=db, log_data=log_in,
                workspace_id=workspace_id, user_id=user_id
            )
            self._commit_transaction(db)
            db.refresh(log)
            return log
        except Exception:
            self._rollback_transaction(db)
            raise

    def update_log(
        self, db: Session, log_id: int, log_in: MachineMaintenanceLogUpdate,
        workspace_id: int, user_id: int
    ) -> MachineMaintenanceLog:
        """Update a maintenance log entry."""
        try:
            log = self.manager.update_log(
                session=db, log_id=log_id, log_data=log_in,
                workspace_id=workspace_id, user_id=user_id
            )
            self._commit_transaction(db)
            db.refresh(log)
            return log
        except Exception:
            self._rollback_transaction(db)
            raise

    def get_log(
        self, db: Session, log_id: int, workspace_id: int
    ) -> MachineMaintenanceLog:
        """Get maintenance log by ID."""
        return self.manager.get_log(db, log_id, workspace_id)

    def list_logs(
        self, db: Session, workspace_id: int,
        machine_id: Optional[int] = None,
        maintenance_type: Optional[MaintenanceTypeEnum] = None,
        skip: int = 0, limit: int = 100
    ) -> List[MachineMaintenanceLog]:
        """List maintenance logs with optional filters."""
        return self.manager.list_logs(
            session=db, workspace_id=workspace_id,
            machine_id=machine_id, maintenance_type=maintenance_type,
            skip=skip, limit=limit
        )

    def delete_log(
        self, db: Session, log_id: int,
        workspace_id: int, user_id: int
    ) -> MachineMaintenanceLog:
        """Soft delete a maintenance log."""
        try:
            log = self.manager.delete_log(
                session=db, log_id=log_id,
                workspace_id=workspace_id, user_id=user_id
            )
            self._commit_transaction(db)
            db.refresh(log)
            return log
        except Exception:
            self._rollback_transaction(db)
            raise


# Singleton instance
machine_maintenance_log_service = MachineMaintenanceLogService()
