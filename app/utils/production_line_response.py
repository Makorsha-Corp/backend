"""Build production line API responses with machine membership."""
from typing import Dict, Iterable, List, Sequence

from sqlalchemy.orm import Session

from app.dao.production_line_machine import production_line_machine_dao
from app.managers.machine_activity_manager import machine_activity_manager
from app.models.machine import Machine
from app.models.production_line import ProductionLine
from app.schemas.production_line import (
    ProductionLineMachineBrief,
    ProductionLineMachineStatusSummary,
    ProductionLineResponse,
)


def _summary_from_machines(machines: List[Machine]) -> ProductionLineMachineStatusSummary:
    total = len(machines)
    running = sum(1 for m in machines if m.is_running)
    return ProductionLineMachineStatusSummary(total=total, running=running, idle=total - running)


def build_production_line_response(
    line: ProductionLine,
    machines: List[Machine],
    status_map: Dict[int, object] | None = None,
) -> ProductionLineResponse:
    status_map = status_map or {}
    briefs = []
    for m in machines:
        event = status_map.get(m.id)
        latest = machine_activity_manager.status_from_activity(event) if event else None
        briefs.append(
            ProductionLineMachineBrief(
                id=m.id,
                name=m.name,
                is_running=bool(m.is_running),
                latest_status_type=latest,
            )
        )
    return ProductionLineResponse(
        id=line.id,
        workspace_id=line.workspace_id,
        factory_id=line.factory_id,
        machine_id=line.machine_id,
        name=line.name,
        description=line.description,
        is_active=line.is_active,
        created_by=line.created_by,
        updated_by=line.updated_by,
        machine_ids=[m.id for m in machines],
        machines=briefs,
        machine_status_summary=_summary_from_machines(machines),
    )


def build_production_line_responses(
    session: Session,
    lines: Sequence[ProductionLine],
    workspace_id: int,
) -> List[ProductionLineResponse]:
    line_ids = [line.id for line in lines]
    grouped = production_line_machine_dao.get_machines_by_line_ids(
        session, line_ids=line_ids, workspace_id=workspace_id
    )
    all_ids: list[int] = []
    for machines in grouped.values():
        all_ids.extend(m.id for m in machines)
    status_map = (
        machine_activity_manager.get_latest_status_map(session, workspace_id=workspace_id, machine_ids=all_ids)
        if all_ids
        else {}
    )
    return [
        build_production_line_response(line, grouped.get(line.id, []), status_map=status_map)
        for line in lines
    ]


def mirror_machine_id_column(machine_ids: List[int]) -> int | None:
    """Keep legacy production_lines.machine_id in sync with junction."""
    if len(machine_ids) == 1:
        return machine_ids[0]
    return None
