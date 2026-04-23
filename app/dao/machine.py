"""DAO operations for Machine model (workspace-scoped)"""
from typing import List, Optional
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from app.dao.base import BaseDAO
from app.models.machine import Machine
from app.models.machine_event import MachineEvent
from app.models.enums import MachineEventTypeEnum
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

    def search_advanced(
        self,
        db: Session,
        *,
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
    ) -> List[Machine]:
        """Advanced machine search with filters and sorting (workspace-scoped)."""
        query = db.query(Machine).filter(
            Machine.workspace_id == workspace_id,
            Machine.is_deleted == False
        )

        if factory_section_id is not None:
            query = query.filter(Machine.factory_section_id == factory_section_id)

        if is_running is not None:
            query = query.filter(Machine.is_running == is_running)

        if search:
            search_like = f"%{search}%"
            query = query.filter(
                or_(
                    Machine.name.ilike(search_like),
                    Machine.model_number.ilike(search_like),
                    Machine.manufacturer.ilike(search_like),
                )
            )

        if has_model_number is True:
            query = query.filter(Machine.model_number.isnot(None), Machine.model_number != "")
        elif has_model_number is False:
            query = query.filter(or_(Machine.model_number.is_(None), Machine.model_number == ""))

        if has_manufacturer is True:
            query = query.filter(Machine.manufacturer.isnot(None), Machine.manufacturer != "")
        elif has_manufacturer is False:
            query = query.filter(or_(Machine.manufacturer.is_(None), Machine.manufacturer == ""))

        today = date.today()
        if maintenance_window == "overdue":
            query = query.filter(
                Machine.next_maintenance_schedule.isnot(None),
                Machine.next_maintenance_schedule < today
            )
        elif maintenance_window == "next_7_days":
            query = query.filter(
                Machine.next_maintenance_schedule.isnot(None),
                Machine.next_maintenance_schedule >= today,
                Machine.next_maintenance_schedule <= (today + timedelta(days=7))
            )
        elif maintenance_window == "next_30_days":
            query = query.filter(
                Machine.next_maintenance_schedule.isnot(None),
                Machine.next_maintenance_schedule >= today,
                Machine.next_maintenance_schedule <= (today + timedelta(days=30))
            )
        elif maintenance_window == "none_scheduled":
            query = query.filter(Machine.next_maintenance_schedule.is_(None))

        if latest_event_type is not None:
            latest_started_subq = (
                db.query(
                    MachineEvent.machine_id.label("machine_id"),
                    func.max(MachineEvent.started_at).label("latest_started_at"),
                )
                .filter(MachineEvent.workspace_id == workspace_id)
                .group_by(MachineEvent.machine_id)
                .subquery()
            )

            latest_event_subq = (
                db.query(
                    MachineEvent.machine_id.label("machine_id"),
                    MachineEvent.event_type.label("event_type"),
                )
                .join(
                    latest_started_subq,
                    and_(
                        MachineEvent.machine_id == latest_started_subq.c.machine_id,
                        MachineEvent.started_at == latest_started_subq.c.latest_started_at,
                    ),
                )
                .filter(MachineEvent.workspace_id == workspace_id)
                .subquery()
            )

            query = (
                query.join(latest_event_subq, Machine.id == latest_event_subq.c.machine_id)
                .filter(latest_event_subq.c.event_type == latest_event_type)
            )

        sort_field_map = {
            "name": Machine.name,
            "created_at": Machine.created_at,
            "maintenance_date": Machine.next_maintenance_schedule,
        }
        sort_column = sort_field_map.get(sort_by, Machine.name)
        order_by_expr = sort_column.desc() if sort_dir == "desc" else sort_column.asc()
        if sort_by == "maintenance_date":
            order_by_expr = order_by_expr.nullslast()

        return query.order_by(order_by_expr, Machine.id.asc()).offset(skip).limit(limit).all()


machine_dao = DAOMachine(Machine)
