"""Workspace policy for assigning machines to production batch steps."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from sqlalchemy.orm import Session

from app.dao.production_batch_stage_log import production_batch_stage_log_dao
from app.managers.machine_activity_manager import machine_activity_manager
from app.models.enums import MachineEventTypeEnum
from app.models.machine import Machine
from app.models.production_batch import ProductionBatch
from app.models.production_batch_stage_log import ProductionBatchStageLog
from app.utils.production_stage_metrics import step_planned_windows

ProductionMachinePickPolicy = Literal["soft", "block_unavailable", "block_overlap"]

_VALID_POLICIES = frozenset({"soft", "block_unavailable", "block_overlap"})


def parse_production_machine_pick_policy(settings: dict | None) -> ProductionMachinePickPolicy:
    if not settings:
        return "soft"
    raw = settings.get("production_machine_pick_policy")
    if isinstance(raw, str) and raw in _VALID_POLICIES:
        return raw  # type: ignore[return-value]
    return "soft"


def _visual_kind(machine: Machine, latest_status: Optional[str]) -> str:
    if latest_status == MachineEventTypeEnum.MAINTENANCE.value:
        return "maintenance"
    if machine.is_running or latest_status == MachineEventTypeEnum.RUNNING.value:
        return "running"
    if latest_status == MachineEventTypeEnum.IDLE.value:
        return "idle"
    return "off"


def _ranges_overlap(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return a_start < b_end and b_start < a_end


def machine_has_schedule_overlap(
    session: Session,
    *,
    workspace_id: int,
    machine_id: int,
    window_start: datetime,
    window_end: datetime,
    exclude_batch_id: int,
) -> bool:
    if window_end <= window_start:
        return False
    batches = (
        session.query(ProductionBatch)
        .filter(
            ProductionBatch.workspace_id == workspace_id,
            ProductionBatch.id != exclude_batch_id,
            ProductionBatch.status.in_(("draft", "recurring", "in_progress")),
            ProductionBatch.planned_start_at.isnot(None),
        )
        .all()
    )
    for batch in batches:
        logs = production_batch_stage_log_dao.get_by_batch(
            session, batch_id=batch.id, workspace_id=workspace_id
        )
        for step in step_planned_windows(batch.planned_start_at, logs):
            step_machine = step.get("machine_id")
            if step_machine != machine_id:
                continue
            other_start = step["planned_start_at"]
            other_end = step["planned_end_at"]
            if _ranges_overlap(window_start, window_end, other_start, other_end):
                return True
    return False


def machine_has_other_in_progress_step(
    session: Session,
    *,
    workspace_id: int,
    machine_id: int,
    exclude_stage_log_id: Optional[int] = None,
) -> bool:
    """True when another open batch still has an in_progress step on this machine.

    Steps left in_progress on a cancelled or completed batch do not hold the floor.
    """
    q = (
        session.query(ProductionBatchStageLog)
        .join(ProductionBatch, ProductionBatch.id == ProductionBatchStageLog.batch_id)
        .filter(
            ProductionBatchStageLog.workspace_id == workspace_id,
            ProductionBatchStageLog.machine_id == machine_id,
            ProductionBatchStageLog.status == "in_progress",
            ProductionBatch.status.in_(("draft", "recurring", "in_progress")),
        )
    )
    if exclude_stage_log_id is not None:
        q = q.filter(ProductionBatchStageLog.id != exclude_stage_log_id)
    return q.first() is not None


def assert_machine_pick_allowed_for_batch_step(
    session: Session,
    *,
    workspace_id: int,
    machine: Machine,
    policy: ProductionMachinePickPolicy,
    batch: ProductionBatch,
    stage_log: Any,
    machine_id: int,
) -> None:
    """Raise ValueError when workspace policy forbids this machine assignment."""
    if policy == "soft":
        return

    latest = machine_activity_manager.get_latest_status(session, machine_id, workspace_id)
    status = machine_activity_manager.status_from_activity(latest)
    kind = _visual_kind(machine, status)

    if policy in ("block_unavailable", "block_overlap") and kind in ("maintenance", "off"):
        label = "maintenance" if kind == "maintenance" else "off"
        raise ValueError(f"Cannot assign machine in {label} state under workspace production policy")

    if policy != "block_overlap":
        return

    exclude_log_id = stage_log.id if stage_log is not None else None
    if machine_has_other_in_progress_step(
        session,
        workspace_id=workspace_id,
        machine_id=machine_id,
        exclude_stage_log_id=exclude_log_id,
    ):
        raise ValueError(
            "Cannot assign machine: another production step is in progress on this machine"
        )
