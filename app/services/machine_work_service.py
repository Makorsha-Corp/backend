"""Shared definition of upcoming machine work (open work orders with planned dates)."""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from sqlalchemy.orm import Session, joinedload

from app.models.enums import WorkOrderStatusEnum
from app.models.machine import Machine
from app.models.machine_section_assignment import MachineSectionAssignment
from app.models.work_order import WorkOrder
from app.schemas.machine_work import (
    MachineUpcomingWorkItem,
    MachineUpcomingWorkRow,
    MachineUpcomingWorkSources,
)
from app.services.base_service import BaseService

_OPEN_WO_STATUSES = (
    WorkOrderStatusEnum.DRAFT.value,
    WorkOrderStatusEnum.IN_PROGRESS.value,
)

_SECTION_EAGER = joinedload(Machine.section_assignment).joinedload(
    MachineSectionAssignment.factory_section
)


class MachineWorkService(BaseService):
    """Open machine work orders with a planned date in the requested window."""

    def collect_raw_items(
        self,
        db: Session,
        *,
        workspace_id: int,
        start: date,
        end: date,
        factory_id: Optional[int] = None,
        machine_ids: Optional[Sequence[int]] = None,
        statuses: Optional[Sequence[str]] = None,
    ) -> List[Tuple[WorkOrder, Machine | None]]:
        """Fetch matching open work orders in the date window."""
        status_filter = statuses if statuses is not None else _OPEN_WO_STATUSES
        wo_query = (
            db.query(WorkOrder, Machine)
            .join(Machine, WorkOrder.machine_id == Machine.id)
            .options(_SECTION_EAGER)
            .filter(
                WorkOrder.workspace_id == workspace_id,
                WorkOrder.is_deleted.is_(False),
                WorkOrder.machine_id.isnot(None),
                WorkOrder.status.in_(status_filter),
                WorkOrder.planned_date.isnot(None),
                WorkOrder.planned_date >= start,
                WorkOrder.planned_date <= end,
                Machine.is_deleted.is_(False),
            )
        )
        if factory_id is not None:
            wo_query = wo_query.filter(WorkOrder.factory_id == factory_id)
        if machine_ids is not None:
            wo_query = wo_query.filter(WorkOrder.machine_id.in_(machine_ids))

        return wo_query.all()

    def upcoming_work(
        self,
        db: Session,
        *,
        workspace_id: int,
        start: date,
        end: date,
        factory_id: Optional[int] = None,
        machine_ids: Optional[Sequence[int]] = None,
    ) -> List[MachineUpcomingWorkRow]:
        """Return per-machine upcoming work rows for [start, end] inclusive."""
        wo_rows = self.collect_raw_items(
            db,
            workspace_id=workspace_id,
            start=start,
            end=end,
            factory_id=factory_id,
            machine_ids=machine_ids,
        )

        by_machine: Dict[int, dict] = defaultdict(
            lambda: {
                "machine": None,
                "items": [],
                "wo_count": 0,
            }
        )

        for work_order, machine in wo_rows:
            mid = work_order.machine_id
            assert mid is not None
            bucket = by_machine[mid]
            bucket["machine"] = machine
            bucket["wo_count"] += 1
            bucket["items"].append(
                MachineUpcomingWorkItem(
                    kind="work_order",
                    source_id=work_order.id,
                    date=work_order.planned_date,
                    title=work_order.title or work_order.work_order_number,
                    status=work_order.status,
                    work_order_type_name=work_order.work_order_type_name,
                )
            )

        rows: List[MachineUpcomingWorkRow] = []
        for mid, bucket in by_machine.items():
            machine: Machine | None = bucket["machine"]
            if machine is None:
                continue
            items: List[MachineUpcomingWorkItem] = bucket["items"]
            items.sort(key=lambda item: (item.date, item.kind, item.source_id))
            earliest = min(item.date for item in items)
            rows.append(
                MachineUpcomingWorkRow(
                    machine_id=mid,
                    name=machine.name,
                    factory_id=machine.factory_id,
                    factory_section_id=machine.factory_section_id,
                    section_name=machine.factory_section_name,
                    earliest_date=earliest,
                    count=len(items),
                    sources=MachineUpcomingWorkSources(
                        work_orders=bucket["wo_count"],
                    ),
                    items=items,
                )
            )

        rows.sort(key=lambda row: (row.earliest_date, row.name.lower(), row.machine_id))
        return rows

    def dates_by_machine(
        self,
        db: Session,
        *,
        workspace_id: int,
        machine_ids: Iterable[int],
        start: date,
        end: date,
        statuses: Optional[Sequence[str]] = None,
    ) -> Dict[int, List[date]]:
        """All work dates per machine in [start, end], sorted ascending."""
        ids = list(machine_ids)
        if not ids:
            return {}

        wo_rows = self.collect_raw_items(
            db,
            workspace_id=workspace_id,
            start=start,
            end=end,
            machine_ids=ids,
            statuses=statuses,
        )

        result: Dict[int, List[date]] = defaultdict(list)
        for work_order, _machine in wo_rows:
            assert work_order.machine_id is not None
            assert work_order.planned_date is not None
            result[work_order.machine_id].append(work_order.planned_date)

        for mid in result:
            result[mid].sort()
        return dict(result)

    @staticmethod
    def earliest_upcoming_on_or_after(dates: Sequence[date], from_date: date) -> date | None:
        upcoming = [d for d in dates if d >= from_date]
        return min(upcoming) if upcoming else None

    @staticmethod
    def has_overdue(dates: Sequence[date], today: date) -> bool:
        return any(d < today for d in dates)

    @staticmethod
    def has_upcoming_in_horizon(dates: Sequence[date], today: date, horizon_days: int) -> bool:
        end = date.fromordinal(today.toordinal() + horizon_days)
        return any(today <= d <= end for d in dates)

    def has_upcoming_work(
        self,
        db: Session,
        *,
        workspace_id: int,
        machine_id: int,
        from_date: date,
    ) -> bool:
        """True when machine has any open WO on/after from_date."""
        return (
            db.query(WorkOrder.id)
            .filter(
                WorkOrder.workspace_id == workspace_id,
                WorkOrder.machine_id == machine_id,
                WorkOrder.is_deleted.is_(False),
                WorkOrder.status.in_(_OPEN_WO_STATUSES),
                WorkOrder.planned_date.isnot(None),
                WorkOrder.planned_date >= from_date,
            )
            .limit(1)
            .first()
            is not None
        )


machine_work_service = MachineWorkService()
