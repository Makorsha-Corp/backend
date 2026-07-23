"""Shared machine expansion for template-based work order generation."""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from app.dao.machine import machine_dao
from app.models.work_order_template import WorkOrderTemplate


def resolve_template_machine_ids(
    session: Session,
    *,
    template: WorkOrderTemplate,
    workspace_id: int,
    factory_section_id: Optional[int] = None,
    factory_id: Optional[int] = None,
) -> List[int]:
    """Machines a template applies to for a generate/stage run."""
    section_id = template.default_factory_section_id or factory_section_id
    if template.default_machine_id:
        return [template.default_machine_id]
    if section_id:
        machines = machine_dao.get_by_section(
            session, factory_section_id=section_id, workspace_id=workspace_id, limit=1000,
        )
        return [m.id for m in machines]
    if factory_section_id:
        machines = machine_dao.get_by_section(
            session, factory_section_id=factory_section_id, workspace_id=workspace_id, limit=1000,
        )
        return [m.id for m in machines]
    if factory_id:
        machines = machine_dao.get_by_factory(
            session, factory_id=factory_id, workspace_id=workspace_id, limit=1000,
        )
        return [m.id for m in machines]
    return []
