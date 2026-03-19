"""DAO operations for Machine model (workspace-scoped)"""
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.machine import Machine
from app.schemas.machine import MachineCreate, MachineUpdate


class DAOMachine(BaseDAO[Machine, MachineCreate, MachineUpdate]):
    """
    DAO operations for Machine model.

    SECURITY: All methods MUST filter by workspace_id to prevent cross-workspace data access.
    """

    def get_by_section(
        self, db: Session, *, factory_section_id: int, workspace_id: int,
        include_deleted: bool = False, skip: int = 0, limit: int = 100
    ) -> List[Machine]:
        """Get machines by factory section ID (SECURITY-CRITICAL: workspace-filtered)"""
        query = db.query(Machine).filter(
            Machine.workspace_id == workspace_id,
            Machine.factory_section_id == factory_section_id
        )
        if not include_deleted:
            query = query.filter(Machine.is_deleted == False)
        return query.offset(skip).limit(limit).all()

    def get_running_machines(
        self, db: Session, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[Machine]:
        """Get all running machines (SECURITY-CRITICAL: workspace-filtered)"""
        return (
            db.query(Machine)
            .filter(
                Machine.workspace_id == workspace_id,
                Machine.is_running == True,
                Machine.is_deleted == False
            )
            .offset(skip).limit(limit).all()
        )

    def get_active_by_workspace(
        self, db: Session, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[Machine]:
        """Get all active (non-deleted) machines in workspace"""
        return (
            db.query(Machine)
            .filter(
                Machine.workspace_id == workspace_id,
                Machine.is_deleted == False
            )
            .offset(skip).limit(limit).all()
        )

    def soft_delete(
        self, db: Session, *, db_obj: Machine, deleted_by: int
    ) -> Machine:
        """Soft delete a machine (does NOT commit)"""
        db_obj.is_deleted = True
        db_obj.is_active = False
        db_obj.deleted_at = datetime.utcnow()
        db_obj.deleted_by = deleted_by
        db.add(db_obj)
        db.flush()
        return db_obj

    def restore(
        self, db: Session, *, db_obj: Machine
    ) -> Machine:
        """Restore a soft-deleted machine (does NOT commit)"""
        db_obj.is_deleted = False
        db_obj.is_active = True
        db_obj.deleted_at = None
        db_obj.deleted_by = None
        db.add(db_obj)
        db.flush()
        return db_obj


machine_dao = DAOMachine(Machine)
