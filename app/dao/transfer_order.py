"""Transfer order DAO. SECURITY: All queries MUST filter by workspace_id."""
from datetime import date, datetime, time
from typing import List, Optional, Tuple

from sqlalchemy import and_, case, desc, func, or_
from sqlalchemy.orm import Query, Session, joinedload

from app.dao.base import BaseDAO
from app.models.factory import Factory
from app.models.machine import Machine
from app.models.project import Project
from app.models.project_component import ProjectComponent
from app.models.transfer_order import TransferOrder
from app.models.transfer_order_item import TransferOrderItem
from app.schemas.transfer_order import (
    TransferOrderCreate,
    TransferOrderItemCreate,
    TransferOrderItemUpdate,
    TransferOrderUpdate,
)


def _transfer_order_is_complete_clause():
    return TransferOrder.completed_at.isnot(None)


def _location_factory_match(
    session: Session,
    *,
    workspace_id: int,
    location_type,
    location_id,
    factory_id: int,
):
    machine_ids = session.query(Machine.id).filter(
        Machine.workspace_id == workspace_id,
        Machine.factory_id == factory_id,
    )
    component_ids = (
        session.query(ProjectComponent.id)
        .join(Project, Project.id == ProjectComponent.project_id)
        .filter(
            ProjectComponent.workspace_id == workspace_id,
            Project.factory_id == factory_id,
        )
    )
    return or_(
        and_(
            location_type.in_(("storage", "damaged")),
            location_id == factory_id,
        ),
        and_(location_type == "machine", location_id.in_(machine_ids)),
        and_(location_type == "project", location_id.in_(component_ids)),
    )


def _location_resolvable_clause(location_type):
    return location_type.in_(("storage", "damaged", "machine", "project"))


def _apply_transfer_factory_filter(
    query: Query, session: Session, *, workspace_id: int, factory_id: int
) -> Query:
    dest_match = _location_factory_match(
        session,
        workspace_id=workspace_id,
        location_type=TransferOrder.destination_location_type,
        location_id=TransferOrder.destination_location_id,
        factory_id=factory_id,
    )
    source_match = _location_factory_match(
        session,
        workspace_id=workspace_id,
        location_type=TransferOrder.source_location_type,
        location_id=TransferOrder.source_location_id,
        factory_id=factory_id,
    )
    dest_resolvable = _location_resolvable_clause(TransferOrder.destination_location_type)
    return query.filter(
        or_(
            dest_match,
            and_(~dest_resolvable, source_match),
        )
    )


def _apply_transfer_order_hub_filters(
    query: Query,
    *,
    workspace_id: int,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    status_ids: Optional[List[int]] = None,
    factory_id: Optional[int] = None,
    source_location_type: Optional[str] = None,
    destination_location_type: Optional[str] = None,
    search: Optional[str] = None,
    exclude_complete: bool = True,
) -> Query:
    query = query.filter(TransferOrder.workspace_id == workspace_id)

    if date_from is not None:
        query = query.filter(
            TransferOrder.created_at >= datetime.combine(date_from, time.min)
        )
    if date_to is not None:
        query = query.filter(
            TransferOrder.created_at <= datetime.combine(date_to, time.max)
        )
    if status_ids:
        query = query.filter(TransferOrder.current_status_id.in_(status_ids))
    if source_location_type:
        query = query.filter(TransferOrder.source_location_type == source_location_type)
    if destination_location_type:
        query = query.filter(
            TransferOrder.destination_location_type == destination_location_type
        )

    if factory_id is not None:
        query = _apply_transfer_factory_filter(
            query, query.session, workspace_id=workspace_id, factory_id=factory_id
        )

    if exclude_complete:
        query = query.filter(TransferOrder.completed_at.is_(None))

    if search and search.strip():
        term = search.strip()
        session = query.session
        matching_factory_ids = session.query(Factory.id).filter(
            Factory.workspace_id == workspace_id,
            Factory.name.ilike(f"%{term}%"),
        )
        matching_machine_ids = session.query(Machine.id).filter(
            Machine.workspace_id == workspace_id,
            Machine.name.ilike(f"%{term}%"),
        )
        matching_component_ids = session.query(ProjectComponent.id).filter(
            ProjectComponent.workspace_id == workspace_id,
            ProjectComponent.name.ilike(f"%{term}%"),
        )

        query = query.filter(
            or_(
                TransferOrder.transfer_number.ilike(f"%{term}%"),
                TransferOrder.source_location_type.ilike(f"%{term}%"),
                TransferOrder.destination_location_type.ilike(f"%{term}%"),
                and_(
                    TransferOrder.source_location_type.in_(("storage", "damaged")),
                    TransferOrder.source_location_id.in_(matching_factory_ids),
                ),
                and_(
                    TransferOrder.destination_location_type.in_(("storage", "damaged")),
                    TransferOrder.destination_location_id.in_(matching_factory_ids),
                ),
                and_(
                    TransferOrder.source_location_type == "machine",
                    TransferOrder.source_location_id.in_(matching_machine_ids),
                ),
                and_(
                    TransferOrder.destination_location_type == "machine",
                    TransferOrder.destination_location_id.in_(matching_machine_ids),
                ),
                and_(
                    TransferOrder.source_location_type == "project",
                    TransferOrder.source_location_id.in_(matching_component_ids),
                ),
                and_(
                    TransferOrder.destination_location_type == "project",
                    TransferOrder.destination_location_id.in_(matching_component_ids),
                ),
            )
        )

    return query


def _transfer_route_defined_clause():
    return and_(
        TransferOrder.source_location_id > 0,
        TransferOrder.destination_location_id > 0,
        TransferOrder.source_location_type.isnot(None),
        TransferOrder.source_location_type != "",
        TransferOrder.destination_location_type.isnot(None),
        TransferOrder.destination_location_type != "",
    )


def _hub_base_query(db: Session, *, workspace_id: int, **filters) -> Query:
    query = db.query(TransferOrder).options(joinedload(TransferOrder.current_status))
    return _apply_transfer_order_hub_filters(query, workspace_id=workspace_id, **filters)


class TransferOrderDAO(BaseDAO[TransferOrder, TransferOrderCreate, TransferOrderUpdate]):
    def get_by_workspace(
        self, db: Session, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[TransferOrder]:
        query = (
            db.query(TransferOrder)
            .options(joinedload(TransferOrder.current_status))
            .filter(TransferOrder.workspace_id == workspace_id)
        )
        return query.order_by(desc(TransferOrder.created_at)).offset(skip).limit(limit).all()

    def list_for_hub(
        self,
        db: Session,
        *,
        workspace_id: int,
        skip: int = 0,
        limit: int = 50,
        **filters,
    ) -> List[TransferOrder]:
        return (
            _hub_base_query(db, workspace_id=workspace_id, **filters)
            .order_by(desc(TransferOrder.created_at), desc(TransferOrder.id))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_for_hub(self, db: Session, *, workspace_id: int, **filters) -> int:
        filtered_ids = (
            _hub_base_query(db, workspace_id=workspace_id, **filters)
            .with_entities(TransferOrder.id)
            .distinct()
            .subquery()
        )
        return int(db.query(func.count()).select_from(filtered_ids).scalar() or 0)

    def list_recent_for_hub(
        self,
        db: Session,
        *,
        workspace_id: int,
        limit: int = 10,
        **filters,
    ) -> List[TransferOrder]:
        return (
            _hub_base_query(db, workspace_id=workspace_id, **filters)
            .order_by(desc(TransferOrder.updated_at), desc(TransferOrder.created_at))
            .limit(limit)
            .all()
        )

    def count_machine_involved_for_hub(
        self, db: Session, *, workspace_id: int, **filters
    ) -> int:
        filtered_ids = (
            _hub_base_query(db, workspace_id=workspace_id, **filters)
            .with_entities(TransferOrder.id)
            .distinct()
            .subquery()
        )
        return (
            db.query(TransferOrder)
            .filter(TransferOrder.id.in_(filtered_ids))
            .filter(
                or_(
                    TransferOrder.source_location_type == "machine",
                    TransferOrder.destination_location_type == "machine",
                )
            )
            .count()
        )

    def get_pending_highlights_for_hub(
        self, db: Session, *, workspace_id: int, **filters
    ) -> dict:
        base = _hub_base_query(db, workspace_id=workspace_id, **filters).filter(
            TransferOrder.completed_at.is_(None)
        )

        planned_q = base.filter(_transfer_route_defined_clause())
        draft_q = base.filter(~_transfer_route_defined_clause())

        planned_count = planned_q.count()
        planned_sample = (
            planned_q.order_by(desc(TransferOrder.updated_at)).limit(3).all()
        )

        awaiting_count = draft_q.count()
        awaiting_sample = (
            draft_q.order_by(desc(TransferOrder.updated_at)).limit(3).all()
        )

        oldest_draft_sample = (
            draft_q.order_by(TransferOrder.created_at.asc()).limit(5).all()
        )

        def _highlight(order: TransferOrder, *, stage: str) -> dict:
            return {
                "id": order.id,
                "order_number": order.transfer_number,
                "status_name": stage,
                "created_at": order.created_at,
            }

        return {
            "pending_planned_count": planned_count,
            "pending_planned": [_highlight(o, stage="Planned") for o in planned_sample],
            "awaiting_setup_count": awaiting_count,
            "awaiting_setup": [_highlight(o, stage="Draft") for o in awaiting_sample],
            "oldest_drafts": [_highlight(o, stage="Draft") for o in oldest_draft_sample],
        }

    def aggregate_hub_stats(
        self, db: Session, *, workspace_id: int, **filters
    ) -> Tuple[int, int, int]:
        filtered_ids = (
            _hub_base_query(db, workspace_id=workspace_id, **filters)
            .with_entities(TransferOrder.id)
            .distinct()
            .subquery()
        )
        query = db.query(TransferOrder).filter(TransferOrder.id.in_(filtered_ids))

        open_count_expr = case(
            (_transfer_order_is_complete_clause(), 0),
            else_=1,
        )
        completed_count_expr = case(
            (_transfer_order_is_complete_clause(), 1),
            else_=0,
        )

        row = query.with_entities(
            func.count(TransferOrder.id),
            func.coalesce(func.sum(open_count_expr), 0),
            func.coalesce(func.sum(completed_count_expr), 0),
        ).one()

        return int(row[0] or 0), int(row[1] or 0), int(row[2] or 0)

    def list_touching_location_incomplete(
        self,
        db: Session,
        *,
        workspace_id: int,
        location_type: str,
        location_id: int,
    ) -> List[TransferOrder]:
        touch = or_(
            and_(
                TransferOrder.source_location_type == location_type,
                TransferOrder.source_location_id == location_id,
            ),
            and_(
                TransferOrder.destination_location_type == location_type,
                TransferOrder.destination_location_id == location_id,
            ),
        )
        return (
            db.query(TransferOrder)
            .options(joinedload(TransferOrder.current_status))
            .filter(
                TransferOrder.workspace_id == workspace_id,
                TransferOrder.completed_at.is_(None),
                touch,
            )
            .order_by(desc(TransferOrder.created_at))
            .all()
        )

    def list_inbound_to_storage_incomplete(
        self,
        db: Session,
        *,
        workspace_id: int,
        factory_id: int,
    ) -> List[TransferOrder]:
        """Incomplete transfers whose destination is factory storage."""
        return (
            db.query(TransferOrder)
            .options(joinedload(TransferOrder.current_status))
            .filter(
                TransferOrder.workspace_id == workspace_id,
                TransferOrder.completed_at.is_(None),
                TransferOrder.destination_location_type == "storage",
                TransferOrder.destination_location_id == factory_id,
            )
            .order_by(desc(TransferOrder.created_at))
            .all()
        )

    def get_by_id_and_workspace(
        self, db: Session, *, id: int, workspace_id: int
    ) -> Optional[TransferOrder]:
        return (
            db.query(TransferOrder)
            .options(joinedload(TransferOrder.current_status))
            .filter(TransferOrder.id == id, TransferOrder.workspace_id == workspace_id)
            .first()
        )

    def get_next_number(self, db: Session, *, workspace_id: int) -> str:
        from datetime import datetime

        year = datetime.now().year
        prefix = f"TR-{year}-"
        last = (
            db.query(TransferOrder)
            .filter(
                TransferOrder.workspace_id == workspace_id,
                TransferOrder.transfer_number.like(f"{prefix}%"),
            )
            .order_by(desc(TransferOrder.transfer_number))
            .first()
        )
        if last:
            try:
                return f"{prefix}{int(last.transfer_number.split('-')[-1]) + 1:03d}"
            except (ValueError, IndexError):
                pass
        return f"{prefix}001"


class TransferOrderItemDAO(
    BaseDAO[TransferOrderItem, TransferOrderItemCreate, TransferOrderItemUpdate]
):
    def get_by_order(
        self, db: Session, *, transfer_order_id: int, workspace_id: int
    ) -> List[TransferOrderItem]:
        return (
            db.query(TransferOrderItem)
            .filter(
                TransferOrderItem.transfer_order_id == transfer_order_id,
                TransferOrderItem.workspace_id == workspace_id,
            )
            .order_by(TransferOrderItem.line_number)
            .all()
        )

    def get_by_transfer_order_ids(
        self,
        db: Session,
        *,
        workspace_id: int,
        transfer_order_ids: List[int],
    ) -> List[TransferOrderItem]:
        if not transfer_order_ids:
            return []
        return (
            db.query(TransferOrderItem)
            .filter(
                TransferOrderItem.workspace_id == workspace_id,
                TransferOrderItem.transfer_order_id.in_(transfer_order_ids),
            )
            .order_by(TransferOrderItem.transfer_order_id, TransferOrderItem.line_number)
            .all()
        )

    def get_by_id_and_workspace(
        self, db: Session, *, id: int, workspace_id: int
    ) -> Optional[TransferOrderItem]:
        return (
            db.query(TransferOrderItem)
            .filter(TransferOrderItem.id == id, TransferOrderItem.workspace_id == workspace_id)
            .first()
        )


transfer_order_dao = TransferOrderDAO(TransferOrder)
transfer_order_item_dao = TransferOrderItemDAO(TransferOrderItem)
