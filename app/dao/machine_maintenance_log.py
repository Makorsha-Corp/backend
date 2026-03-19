"""Machine maintenance log DAO operations

SECURITY NOTICE:
This DAO handles workspace-scoped data. All query methods MUST filter by workspace_id.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.dao.base import BaseDAO
from app.models.machine_maintenance_log import MachineMaintenanceLog
from app.models.enums import MaintenanceTypeEnum
from app.schemas.machine_maintenance_log import MachineMaintenanceLogCreate, MachineMaintenanceLogUpdate


class MachineMaintenanceLogDAO(BaseDAO[MachineMaintenanceLog, MachineMaintenanceLogCreate, MachineMaintenanceLogUpdate]):
    """DAO for MachineMaintenanceLog model (workspace-scoped)"""

    def get_by_workspace(
        self, db: Session, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[MachineMaintenanceLog]:
        """Get all maintenance logs in workspace, newest first."""
        return db.query(MachineMaintenanceLog).filter(
            MachineMaintenanceLog.workspace_id == workspace_id,
            MachineMaintenanceLog.is_deleted == False,
        ).order_by(desc(MachineMaintenanceLog.maintenance_date)).offset(skip).limit(limit).all()

    def get_by_id_and_workspace(
        self, db: Session, *, id: int, workspace_id: int
    ) -> Optional[MachineMaintenanceLog]:
        """Get maintenance log by ID with workspace isolation."""
        return db.query(MachineMaintenanceLog).filter(
            MachineMaintenanceLog.id == id,
            MachineMaintenanceLog.workspace_id == workspace_id,
        ).first()

    def get_by_machine(
        self, db: Session, machine_id: int, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[MachineMaintenanceLog]:
        """Get all maintenance logs for a machine, newest first."""
        return db.query(MachineMaintenanceLog).filter(
            MachineMaintenanceLog.workspace_id == workspace_id,
            MachineMaintenanceLog.machine_id == machine_id,
            MachineMaintenanceLog.is_deleted == False,
        ).order_by(desc(MachineMaintenanceLog.maintenance_date)).offset(skip).limit(limit).all()

    def get_by_type(
        self, db: Session, maintenance_type: MaintenanceTypeEnum, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[MachineMaintenanceLog]:
        """Get maintenance logs by type, newest first."""
        return db.query(MachineMaintenanceLog).filter(
            MachineMaintenanceLog.workspace_id == workspace_id,
            MachineMaintenanceLog.maintenance_type == maintenance_type,
            MachineMaintenanceLog.is_deleted == False,
        ).order_by(desc(MachineMaintenanceLog.maintenance_date)).offset(skip).limit(limit).all()

    def get_by_machine_and_type(
        self, db: Session, machine_id: int, maintenance_type: MaintenanceTypeEnum,
        *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[MachineMaintenanceLog]:
        """Get maintenance logs for a machine filtered by type."""
        return db.query(MachineMaintenanceLog).filter(
            MachineMaintenanceLog.workspace_id == workspace_id,
            MachineMaintenanceLog.machine_id == machine_id,
            MachineMaintenanceLog.maintenance_type == maintenance_type,
            MachineMaintenanceLog.is_deleted == False,
        ).order_by(desc(MachineMaintenanceLog.maintenance_date)).offset(skip).limit(limit).all()

    def soft_delete(self, db: Session, *, db_obj: MachineMaintenanceLog, deleted_by: int) -> MachineMaintenanceLog:
        """Soft delete a maintenance log."""
        from sqlalchemy.sql import func
        db_obj.is_active = False
        db_obj.is_deleted = True
        db_obj.deleted_at = func.now()
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
