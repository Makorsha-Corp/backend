"""Helpers for order workflow terminal status resolution."""
from typing import Dict, Iterable, List, Set

from sqlalchemy.orm import Session

from app.models.order_workflow import OrderWorkflow


def terminal_status_ids_by_workflow(
    db: Session,
    *,
    workspace_id: int,
    workflow_ids: Iterable[int],
) -> Dict[int, int]:
    """Map workflow_id -> last status_id in status_sequence (terminal status)."""
    wf_ids: Set[int] = {wid for wid in workflow_ids if wid is not None}
    if not wf_ids:
        return {}

    wfs = (
        db.query(OrderWorkflow)
        .filter(
            OrderWorkflow.workspace_id == workspace_id,
            OrderWorkflow.id.in_(wf_ids),
        )
        .all()
    )
    terminal_by_wf: Dict[int, int] = {}
    for wf in wfs:
        seq = wf.status_sequence or []
        if isinstance(seq, list) and len(seq) > 0:
            last = seq[-1]
            if isinstance(last, int):
                terminal_by_wf[wf.id] = last
    return terminal_by_wf


def is_order_terminal(
    *,
    workflow_id: int | None,
    current_status_id: int | None,
    terminal_by_wf: Dict[int, int],
) -> bool:
    if workflow_id is None or current_status_id is None:
        return False
    last_id = terminal_by_wf.get(workflow_id)
    return last_id is not None and current_status_id == last_id
