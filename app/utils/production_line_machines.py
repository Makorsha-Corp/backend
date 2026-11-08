"""Validate production line machine membership for assignments."""
from sqlalchemy.orm import Session

from app.dao.production_line import production_line_dao
from app.dao.production_line_machine import production_line_machine_dao

LINE_NEEDS_MACHINES_MSG = "Assign at least one machine to this production line first."


def production_line_has_machines(session: Session, *, line_id: int, workspace_id: int) -> bool:
    machine_ids = production_line_machine_dao.get_machine_ids_for_line(
        session, production_line_id=line_id, workspace_id=workspace_id
    )
    if machine_ids:
        return True
    line = production_line_dao.get_by_id_and_workspace(session, id=line_id, workspace_id=workspace_id)
    return line is not None and line.machine_id is not None


def assert_production_line_assignable(
    session: Session,
    *,
    line_id: int,
    workspace_id: int,
    previous_line_id: int | None = None,
) -> None:
    """Allow keeping an already-assigned line; require machines when assigning or changing line."""
    if previous_line_id is not None and line_id == previous_line_id:
        return
    if not production_line_has_machines(session, line_id=line_id, workspace_id=workspace_id):
        raise ValueError(LINE_NEEDS_MACHINES_MSG)
