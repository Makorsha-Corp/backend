"""Machine maintenance log DAO operations

SECURITY NOTICE:
This DAO handles workspace-scoped data. All query methods MUST filter by workspace_id.
"""

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.enums import MaintenanceTypeEnum
from app.models.machine import Machine
from app.models.machine_maintenance_log import MachineMaintenanceLog
from app.schemas.machine_maintenance_log import (
    MachineMaintenanceLogCreate,
    MachineMaintenanceLogUpdate,
)
from app.utils.time import utcnow


def _same_workspace_logs(db: Session):
    """Logs whose machine is in the log's own workspace (HR-16, BUG-1101).

    Only the machine's workspace_id is compared, never its state.
    """
    return db.query(MachineMaintenanceLog).join(
        Machine, Machine.id == MachineMaintenanceLog.machine_id
    ).filter(Machine.workspace_id == MachineMaintenanceLog.workspace_id)


class MachineMaintenanceLogDAO(BaseDAO[MachineMaintenanceLog, MachineMaintenanceLogCreate, MachineMaintenanceLogUpdate]):
    """DAO for MachineMaintenanceLog model (workspace-scoped)"""

    def get_by_workspace(
        self, db: Session, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> list[MachineMaintenanceLog]:
        """Get all maintenance logs in workspace, newest first."""
        return _same_workspace_logs(db).filter(
            MachineMaintenanceLog.workspace_id == workspace_id,
            MachineMaintenanceLog.is_deleted == False,
        ).order_by(
            desc(MachineMaintenanceLog.maintenance_date), desc(MachineMaintenanceLog.id)
        ).offset(skip).limit(limit).all()

    def get_by_id_and_workspace(
        self, db: Session, *, id: int, workspace_id: int
    ) -> MachineMaintenanceLog | None:
        """Get maintenance log by ID with workspace isolation."""
        return _same_workspace_logs(db).filter(
            MachineMaintenanceLog.id == id,
            MachineMaintenanceLog.workspace_id == workspace_id,
        ).first()

    def get_by_machine(
        self, db: Session, machine_id: int, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> list[MachineMaintenanceLog]:
        """Get all maintenance logs for a machine, newest first."""
        return _same_workspace_logs(db).filter(
            MachineMaintenanceLog.workspace_id == workspace_id,
            MachineMaintenanceLog.machine_id == machine_id,
            MachineMaintenanceLog.is_deleted == False,
        ).order_by(
            desc(MachineMaintenanceLog.maintenance_date), desc(MachineMaintenanceLog.id)
        ).offset(skip).limit(limit).all()

    def get_by_type(
        self, db: Session, maintenance_type: MaintenanceTypeEnum, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> list[MachineMaintenanceLog]:
        """Get maintenance logs by type, newest first."""
        return _same_workspace_logs(db).filter(
            MachineMaintenanceLog.workspace_id == workspace_id,
            MachineMaintenanceLog.maintenance_type == maintenance_type,
            MachineMaintenanceLog.is_deleted == False,
        ).order_by(
            desc(MachineMaintenanceLog.maintenance_date), desc(MachineMaintenanceLog.id)
        ).offset(skip).limit(limit).all()

    def get_by_machine_and_type(
        self, db: Session, machine_id: int, maintenance_type: MaintenanceTypeEnum,
        *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> list[MachineMaintenanceLog]:
        """Get maintenance logs for a machine filtered by type."""
        return _same_workspace_logs(db).filter(
            MachineMaintenanceLog.workspace_id == workspace_id,
            MachineMaintenanceLog.machine_id == machine_id,
            MachineMaintenanceLog.maintenance_type == maintenance_type,
            MachineMaintenanceLog.is_deleted == False,
        ).order_by(
            desc(MachineMaintenanceLog.maintenance_date), desc(MachineMaintenanceLog.id)
        ).offset(skip).limit(limit).all()

    def soft_delete(self, db: Session, *, db_obj: MachineMaintenanceLog, deleted_by: int) -> MachineMaintenanceLog:
        """Soft delete a maintenance log."""
        db_obj.is_active = False
        db_obj.is_deleted = True
        db_obj.deleted_at = utcnow()
        db_obj.deleted_by = deleted_by
        db.add(db_obj)
        db.flush()
        return db_obj

    def restore(self, db: Session, *, db_obj: MachineMaintenanceLog) -> MachineMaintenanceLog:
        """Restore a soft-deleted maintenance log."""
        db_obj.is_active = True
        db_obj.is_deleted = False
        db_obj.deleted_at = None
        db_obj.deleted_by = None
        db.add(db_obj)
        db.flush()
        return db_obj


# Singleton instance
machine_maintenance_log_dao = MachineMaintenanceLogDAO(MachineMaintenanceLog)
