"""In-batch WIP between production steps (prior step outputs)."""
from __future__ import annotations

import re
from collections import defaultdict
from decimal import Decimal
from typing import Iterable, Optional

_STEP_LOG_ID = re.compile(r"step_log=(\d+)")

from app.models.production_batch_item import ProductionBatchItem
from app.models.production_batch_stage_log import ProductionBatchStageLog
from app.models.production_formula_stage import ProductionFormulaStage
from app.models.production_formula_stage_item import ProductionFormulaStageItem
from app.utils.production_quantity import as_quantity, scale_quantity


def resolve_stage_output_item_id(
    log: ProductionBatchStageLog,
    stages_by_id: dict[int, ProductionFormulaStage],
    stage_items_by_stage: dict[int, list[ProductionFormulaStageItem]],
) -> Optional[int]:
    stage_id = log.formula_stage_id
    if stage_id is None:
        return None
    stage = stages_by_id.get(stage_id)
    if stage and stage.expected_output_item_id:
        return stage.expected_output_item_id
    for row in sorted(stage_items_by_stage.get(stage_id, []), key=lambda r: r.id):
        if row.item_role == "output":
            return row.item_id
    return None


def input_qty_from_step_rows(rows: Iterable) -> dict[int, Decimal]:
    """Prefer per-step actual, else expected. Empty when the log has no input rows."""
    by_item: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
    saw_input = False
    for row in rows:
        if getattr(row, "item_role", None) != "input":
            continue
        saw_input = True
        raw = row.actual_quantity if row.actual_quantity is not None else row.expected_quantity
        if raw is None:
            continue
        qty = as_quantity(raw)
        if qty <= 0:
            continue
        by_item[row.item_id] += qty
    if not saw_input:
        return {}
    return dict(by_item)


def step_input_quantities_for_log(
    log: ProductionBatchStageLog,
    *,
    multiplier: Decimal,
    stage_items_by_stage: dict[int, list[ProductionFormulaStageItem]],
    batch_items: list[ProductionBatchItem],
    step_rows: Optional[Iterable] = None,
) -> dict[int, Decimal]:
    """Item_id -> qty consumed when this step starts (matches step input deductions)."""
    if step_rows is not None:
        rows = list(step_rows)
        if rows:
            return input_qty_from_step_rows(rows)

    by_item: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))

    if log.formula_stage_id is not None:
        for row in stage_items_by_stage.get(log.formula_stage_id, []):
            if row.item_role != "input":
                continue
            qty = scale_quantity(row.quantity, multiplier)
            if qty <= 0:
                continue
            by_item[row.item_id] += qty
        return dict(by_item)

    for bi in batch_items:
        if bi.item_role != "input":
            continue
        qty = bi.actual_quantity or bi.expected_quantity
        if not qty:
            continue
        by_item[bi.item_id] += as_quantity(qty)
    return dict(by_item)


def compute_wip_available_by_item(
    stage_logs: Iterable[ProductionBatchStageLog],
    current_log: ProductionBatchStageLog,
    *,
    multiplier: Decimal,
    stages_by_id: dict[int, ProductionFormulaStage],
    stage_items_by_stage: dict[int, list[ProductionFormulaStageItem]],
    batch_items: list[ProductionBatchItem],
    step_items_by_log: Optional[dict[int, list]] = None,
) -> dict[int, Decimal]:
    wip: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
    sorted_logs = sorted(stage_logs, key=lambda l: (l.stage_order, l.id))
    rows_by_log = step_items_by_log or {}

    for log in sorted_logs:
        if log.stage_order > current_log.stage_order:
            break
        if log.id == current_log.id:
            break

        if log.status in ("in_progress", "completed"):
            inputs = step_input_quantities_for_log(
                log,
                multiplier=multiplier,
                stage_items_by_stage=stage_items_by_stage,
                batch_items=batch_items,
                step_rows=rows_by_log.get(log.id),
            )
            for item_id, qty in inputs.items():
                wip[item_id] = max(Decimal("0"), wip[item_id] - qty)

        if log.status == "completed" and log.output_quantity is not None:
            out_item_id = resolve_stage_output_item_id(
                log, stages_by_id, stage_items_by_stage
            )
            out_qty = as_quantity(log.output_quantity)
            if out_item_id is not None and out_qty > 0:
                wip[out_item_id] += out_qty

    return dict(wip)


def compute_remaining_wip(
    stage_logs: Iterable[ProductionBatchStageLog],
    *,
    multiplier: Decimal,
    stages_by_id: dict[int, ProductionFormulaStage],
    stage_items_by_stage: dict[int, list[ProductionFormulaStageItem]],
    batch_items: list[ProductionBatchItem],
    step_items_by_log: Optional[dict[int, list]] = None,
) -> dict[int, Decimal]:
    """Pool after every step, as if nothing further will consume it."""

    class _AfterLast:
        stage_order = 10**9
        id = 10**9

    return compute_wip_available_by_item(
        stage_logs,
        _AfterLast(),  # type: ignore[arg-type]
        multiplier=multiplier,
        stages_by_id=stages_by_id,
        stage_items_by_stage=stage_items_by_stage,
        batch_items=batch_items,
        step_items_by_log=step_items_by_log,
    )


def leftover_handoff_lines(
    stage_logs: Iterable[ProductionBatchStageLog],
    leftover: dict[int, Decimal],
    *,
    multiplier: Decimal,
    stages_by_id: dict[int, ProductionFormulaStage],
    stage_items_by_stage: dict[int, list[ProductionFormulaStageItem]],
    batch_items: list[ProductionBatchItem],
    step_items_by_log: Optional[dict[int, list]] = None,
) -> list[dict]:
    """One story per leftover item: who made it, which later steps took from that output."""
    producers: dict[int, ProductionBatchStageLog] = {}
    draws: list[tuple[ProductionBatchStageLog, int, Decimal]] = []
    wip: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
    rows_by_log = step_items_by_log or {}

    for log in sorted(stage_logs, key=lambda row: (row.stage_order, row.id)):
        if log.status in ("in_progress", "completed"):
            inputs = step_input_quantities_for_log(
                log,
                multiplier=multiplier,
                stage_items_by_stage=stage_items_by_stage,
                batch_items=batch_items,
                step_rows=rows_by_log.get(log.id),
            )
            for item_id, qty in inputs.items():
                from_wip = min(wip[item_id], qty)
                if from_wip > 0:
                    draws.append((log, item_id, from_wip))
                wip[item_id] = max(Decimal("0"), wip[item_id] - qty)

        if log.status == "completed" and log.output_quantity is not None:
            out_item_id = resolve_stage_output_item_id(log, stages_by_id, stage_items_by_stage)
            out_qty = as_quantity(log.output_quantity)
            if out_item_id is not None and out_qty > 0:
                producers[out_item_id] = log
                wip[out_item_id] += out_qty

    lines: list[dict] = []
    for item_id, qty in sorted(leftover.items()):
        posted = as_quantity(qty)
        if posted <= 0:
            continue
        producer = producers.get(item_id)
        made = (
            as_quantity(producer.output_quantity)
            if producer is not None and producer.output_quantity is not None
            else posted
        )
        used_by: list[dict] = []
        if producer is not None:
            for log, draw_item, draw_qty in draws:
                if draw_item != item_id:
                    continue
                if (log.stage_order, log.id) <= (producer.stage_order, producer.id):
                    continue
                used_by.append({"stage_name": log.stage_name, "qty": draw_qty})
        used = sum((row["qty"] for row in used_by), Decimal("0"))
        lines.append(
            {
                "item_id": item_id,
                "qty": posted,
                "made": made,
                "from_stage_name": producer.stage_name if producer is not None else "Earlier step",
                "used": used,
                "used_by": used_by,
            }
        )
    return lines


def group_step_start_storage_inputs(
    rows: Iterable[tuple[str, int, Decimal]],
    *,
    stage_name_by_log_id: dict[int, str],
    stage_order_by_log_id: dict[int, tuple[int, int]],
) -> list[dict]:
    """Sum storage taken at step start, one line per step log and item."""
    grouped: dict[tuple[int, int], Decimal] = defaultdict(lambda: Decimal("0"))
    fallback_name: dict[int, str] = {}
    for note, item_id, qty in rows:
        amount = as_quantity(qty)
        if amount <= 0:
            continue
        match = _STEP_LOG_ID.search(note or "")
        if not match:
            continue
        log_id = int(match.group(1))
        grouped[(log_id, item_id)] += amount
        if log_id not in stage_name_by_log_id:
            parts = [part.strip() for part in (note or "").split("|")]
            if len(parts) >= 3:
                fallback_name[log_id] = parts[-2]

    lines: list[dict] = []
    for (log_id, item_id), qty in grouped.items():
        if qty <= 0:
            continue
        stage_name = stage_name_by_log_id.get(log_id) or fallback_name.get(log_id) or f"Step #{log_id}"
        lines.append({"item_id": item_id, "qty": qty, "stage_name": stage_name, "_log_id": log_id})
    lines.sort(
        key=lambda row: (
            stage_order_by_log_id.get(row["_log_id"], (10**9, row["_log_id"])),
            row["item_id"],
        )
    )
    for row in lines:
        row.pop("_log_id", None)
    return lines


def leftover_intermediate_wip(
    wip: dict[int, Decimal],
    posted_output_by_item: dict[int, Decimal],
) -> dict[int, Decimal]:
    """Drop finished-good qty that complete_batch already posts to products."""
    leftover: dict[int, Decimal] = {}
    for item_id, qty in wip.items():
        remaining = qty - posted_output_by_item.get(item_id, Decimal("0"))
        if remaining > 0:
            leftover[item_id] = remaining
    return leftover


def storage_needed_after_wip(
    item_id: int,
    qty_needed: Decimal,
    wip_available: dict[int, Decimal],
) -> tuple[Decimal, Decimal]:
    """Returns (from_wip, storage_needed). Mutates wip_available in place."""
    available_wip = wip_available.get(item_id, Decimal("0"))
    from_wip = min(available_wip, qty_needed)
    wip_available[item_id] = available_wip - from_wip
    storage_needed = qty_needed - from_wip
    return from_wip, storage_needed
