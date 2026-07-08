"""DAO operations for WorkOrderType model

SECURITY NOTICE:
This DAO handles workspace-scoped data. All inherited BaseDAO methods automatically
filter by workspace_id via get_by_workspace() and get_by_id_and_workspace().
"""
from typing import List
from datetime import datetime
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.work_order_type import WorkOrderType
from app.schemas.work_order_type import WorkOrderTypeCreate, WorkOrderTypeUpdate


class DAOWorkOrderType(BaseDAO[WorkOrderType, WorkOrderTypeCreate, WorkOrderTypeUpdate]):
    """
    DAO operations for WorkOrderType model (workspace-scoped)

    Uses inherited BaseDAO methods which are workspace-safe:
    - get_by_workspace() - Get all work order types in workspace
    - get_by_id_and_workspace() - Get specific work order type in workspace
    """

    def get_active_types(
        self, db: Session, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[WorkOrderType]:
        """Get all active, non-deleted work order types for a workspace (SECURITY-CRITICAL: workspace-filtered)"""
        return (
            db.query(WorkOrderType)
            .filter(
                WorkOrderType.workspace_id == workspace_id,  # SECURITY: workspace isolation
                WorkOrderType.is_active == True,
                WorkOrderType.is_deleted == False
            )
            .order_by(WorkOrderType.name)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def soft_delete(
        self, db: Session, *, db_obj: WorkOrderType, deleted_by: int
    ) -> WorkOrderType:
        """Soft delete a work order type (does NOT commit)"""
        db_obj.is_deleted = True
        db_obj.deleted_at = datetime.utcnow()
        db_obj.deleted_by = deleted_by
        db.add(db_obj)
        db.flush()
        return db_obj

    def restore(
        self, db: Session, *, db_obj: WorkOrderType
    ) -> WorkOrderType:
        """Restore a soft-deleted work order type (does NOT commit)"""
        db_obj.is_deleted = False
        db_obj.deleted_at = None
        db_obj.deleted_by = None
        db.add(db_obj)
        db.flush()
        return db_obj


work_order_type_dao = DAOWorkOrderType(WorkOrderType)
