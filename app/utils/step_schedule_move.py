"""Pure helpers for moving a pending step on the schedule board."""
from __future__ import annotations

from datetime import datetime

from app.utils.production_stage_metrics import ordered_stage_logs, step_planned_end


def compute_move_planned_start_updates(
    logs: list,
    moved_log_id: int,
    requested_start: datetime,
) -> dict[int, datetime]:
    """
    Clamp moved step to previous step end; push pending followers that start too soon.
    Non-pending followers are unchanged but still advance the chain cursor.
    """
    ordered = ordered_stage_logs(logs)
    idx = next(i for i, row in enumerate(ordered) if row.id == moved_log_id)
    start = requested_start
    if idx > 0:
        prev = ordered[idx - 1]
        prev_end = step_planned_end(prev)
        if prev_end is not None and start < prev_end:
            start = prev_end

    updates: dict[int, datetime] = {moved_log_id: start}
    prev_end = step_planned_end(ordered[idx], start)
    if prev_end is None:
        return updates

    for follower in ordered[idx + 1 :]:
        if getattr(follower, "status", "pending") != "pending":
            fixed_start = updates.get(follower.id, follower.planned_start_at)
            chain_end = step_planned_end(follower, fixed_start)
            if chain_end is not None:
                prev_end = chain_end
            continue
        current = updates.get(follower.id, follower.planned_start_at)
        if current is None or current < prev_end:
            updates[follower.id] = prev_end
            current = prev_end
        chain_end = step_planned_end(follower, current)
        if chain_end is not None:
            prev_end = chain_end
    return updates
