"""DAO operations for Machine model (workspace-scoped)"""

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.dao.base import BaseDAO
from app.models.enums import MachineEventTypeEnum
from app.models.factory import Factory
from app.models.factory_section import FactorySection
from app.models.machine import Machine
from app.models.machine_activity_event import MachineActivityEvent
from app.models.machine_section_assignment import MachineSectionAssignment
from app.schemas.machine import MachineCreate, MachineUpdate
from app.utils.time import utcnow

# Eager-load the optional section assignment so Machine.factory_section_id/_name
# (properties reading `self.section_assignment`) don't N+1 across a list of machines.
_SECTION_EAGER_LOAD = joinedload(Machine.section_assignment).joinedload(MachineSectionAssignment.factory_section)

_ILIKE_ESCAPE = "\\"


def _escape_ilike(value: str) -> str:
    """Escape user input so `%`, `_` and the backslash match literally in an ILIKE pattern."""
    escaped = value.replace("\\", "\\\\")
    return escaped.replace("%", "\\%").replace("_", "\\_")


class DAOMachine(BaseDAO[Machine, MachineCreate, MachineUpdate]):
    """
    DAO operations for Machine model.

    SECURITY: All methods MUST filter by workspace_id to prevent cross-workspace data access.
    """

    def get_by_factory(
        self, db: Session, *, factory_id: int, workspace_id: int,
        include_deleted: bool = False, skip: int = 0, limit: int = 100
    ) -> list[Machine]:
        """Get machines by factory ID (SECURITY-CRITICAL: workspace-filtered)"""
        # Machines of a soft-deleted factory are hidden by the factory's state alone
        # (their rows stay untouched so restoring the factory brings them back).
        query = db.query(Machine).options(_SECTION_EAGER_LOAD).join(
            Factory, Factory.id == Machine.factory_id
        ).filter(
            Machine.workspace_id == workspace_id,
            Machine.factory_id == factory_id,
            Factory.is_deleted == False,
        )
        if not include_deleted:
            query = query.filter(Machine.is_deleted == False)
        return query.offset(skip).limit(limit).all()

    def get_by_section(
        self, db: Session, *, factory_section_id: int, workspace_id: int,
        include_deleted: bool = False, skip: int = 0, limit: int = 100
    ) -> list[Machine]:
        """Get machines assigned to a factory section (SECURITY-CRITICAL: workspace-filtered)"""
        # A soft-deleted section matches nothing, and machines of a soft-deleted
        # factory are hidden; assignment and machine rows are left as they are.
        query = db.query(Machine).options(_SECTION_EAGER_LOAD).join(
            MachineSectionAssignment, MachineSectionAssignment.machine_id == Machine.id
        ).join(
            FactorySection, FactorySection.id == MachineSectionAssignment.factory_section_id
        ).join(
            Factory, Factory.id == Machine.factory_id
        ).filter(
            Machine.workspace_id == workspace_id,
            MachineSectionAssignment.factory_section_id == factory_section_id,
            FactorySection.is_deleted == False,
            Factory.is_deleted == False,
        )
        if not include_deleted:
            query = query.filter(Machine.is_deleted == False)
        return query.offset(skip).limit(limit).all()

    def get_active_by_workspace(
        self, db: Session, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> list[Machine]:
        """Get all active (non-deleted) machines in workspace"""
        return (
            db.query(Machine)
            .options(_SECTION_EAGER_LOAD)
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
        db_obj.deleted_at = utcnow()
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
        factory_id: int | None = None,
        factory_section_id: int | None = None,
        is_running: bool | None = None,
        search: str | None = None,
        has_model_number: bool | None = None,
        has_manufacturer: bool | None = None,
        latest_event_type: MachineEventTypeEnum | None = None,
        sort_by: str = "name",
        sort_dir: str = "asc",
        skip: int = 0,
        limit: int = 100,
    ) -> list[Machine]:
        """Advanced machine search with filters and sorting (workspace-scoped)."""
        # Machines of a soft-deleted factory are hidden, whatever the other filters.
        query = db.query(Machine).options(_SECTION_EAGER_LOAD).join(
            Factory, Factory.id == Machine.factory_id
        ).filter(
            Machine.workspace_id == workspace_id,
            Machine.is_deleted == False,
            Factory.is_deleted == False,
        )

        if factory_id is not None:
            query = query.filter(Machine.factory_id == factory_id)

        if factory_section_id is not None:
            # A soft-deleted section neither filters nor matches.
            query = query.join(
                MachineSectionAssignment, MachineSectionAssignment.machine_id == Machine.id
            ).join(
                FactorySection, FactorySection.id == MachineSectionAssignment.factory_section_id
            ).filter(
                MachineSectionAssignment.factory_section_id == factory_section_id,
                FactorySection.is_deleted == False,
            )

        if is_running is not None:
            query = query.filter(Machine.is_running == is_running)

        search_text = search.strip() if search else ""
        if search_text:
            search_like = f"%{_escape_ilike(search_text)}%"
            query = query.filter(
                or_(
                    Machine.name.ilike(search_like, escape=_ILIKE_ESCAPE),
                    Machine.model_number.ilike(search_like, escape=_ILIKE_ESCAPE),
                    Machine.manufacturer.ilike(search_like, escape=_ILIKE_ESCAPE),
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

        if latest_event_type is not None:
            # Rank each machine's status changes newest first (created_at, then id) so
            # exactly one row per machine is "latest"; older rows are never consulted.
            # `as_string()` is the dialect-neutral JSON text accessor (the column is
            # generic JSON, which has no `.astext`).
            ranked_status_subq = (
                db.query(
                    MachineActivityEvent.machine_id.label("machine_id"),
                    MachineActivityEvent.metadata_json["status"].as_string().label("status"),
                    func.row_number()
                    .over(
                        partition_by=MachineActivityEvent.machine_id,
                        order_by=(MachineActivityEvent.created_at.desc(), MachineActivityEvent.id.desc()),
                    )
                    .label("rn"),
                )
                .filter(
                    MachineActivityEvent.workspace_id == workspace_id,
                    MachineActivityEvent.event_type == "status_updated",
                )
                .subquery()
            )

            query = (
                query.join(ranked_status_subq, Machine.id == ranked_status_subq.c.machine_id)
                .filter(
                    ranked_status_subq.c.rn == 1,
                    ranked_status_subq.c.status == latest_event_type.value,
                )
            )

        # Name sorts case-insensitively so case-only ties fall through to id.
        sort_field_map = {
            "name": func.lower(Machine.name),
            "created_at": Machine.created_at,
        }
        sort_column = sort_field_map.get(sort_by, func.lower(Machine.name))
        order_by_expr = sort_column.desc() if sort_dir == "desc" else sort_column.asc()

        return query.order_by(order_by_expr, Machine.id.asc()).offset(skip).limit(limit).all()


machine_dao = DAOMachine(Machine)
