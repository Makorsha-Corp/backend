"""Helpers for production batch activity events."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.production_batch import ProductionBatch
from app.models.production_batch_event import ProductionBatchEvent
from app.models.production_batch_item import ProductionBatchItem
from app.models.production_batch_stage_log import ProductionBatchStageLog
from app.models.production_batch_stage_parameter import ProductionBatchStageParameter
from app.dao.production_batch_item import production_batch_item_dao
from app.dao.production_batch_stage_item import production_batch_stage_item_dao
from app.dao.production_batch_stage_parameter import production_batch_stage_parameter_dao
from app.dao.production_formula_stage_item import production_formula_stage_item_dao
from app.dao.production_formula_stage_parameter import production_formula_stage_parameter_dao
from app.utils.time import utcnow_aware


def _serialize_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: _serialize_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize_value(item) for item in value]
    return value


def _log_field(log: ProductionBatchStageLog, overrides: Optional[dict], field: str):
    if overrides and field in overrides:
        return overrides[field]
    return getattr(log, field, None)


def build_step_event_snapshot(
    session: Session,
    *,
    log: ProductionBatchStageLog,
    workspace_id: int,
    field_overrides: Optional[dict] = None,
) -> dict[str, Any]:
    """Point-in-time materials, conditions, and step qty for activity log Details."""
    materials: list[dict[str, Any]] = []
    primary_output_item_id: Optional[int] = None

    formula_by_key = {}
    if log.formula_stage_id is not None:
        stage_items = production_formula_stage_item_dao.get_by_stage(
            session, formula_stage_id=log.formula_stage_id, workspace_id=workspace_id
        )
        formula_by_key = {(row.item_id, row.item_role): row for row in stage_items}

    step_rows = production_batch_stage_item_dao.get_by_stage_log(
        session, batch_stage_log_id=log.id, workspace_id=workspace_id
    )
    if step_rows:
        for row in sorted(step_rows, key=lambda r: (r.item_role, r.id)):
            formula_row = formula_by_key.get((row.item_id, row.item_role))
            materials.append(
                {
                    "item_id": row.item_id,
                    "item_role": row.item_role,
                    "expected": _serialize_value(row.expected_quantity),
                    "actual": _serialize_value(row.actual_quantity),
                    "unit": formula_row.unit if formula_row is not None else None,
                }
            )
            if row.item_role == "output" and primary_output_item_id is None:
                primary_output_item_id = row.item_id
    elif log.formula_stage_id is not None:
        for row in sorted(formula_by_key.values(), key=lambda r: (r.item_role, r.id)):
            materials.append(
                {
                    "item_id": row.item_id,
                    "item_role": row.item_role,
                    "expected": _serialize_value(row.quantity),
                    "actual": None,
                    "unit": row.unit,
                }
            )
            if row.item_role == "output" and primary_output_item_id is None:
                primary_output_item_id = row.item_id
    else:
        batch_items = production_batch_item_dao.get_by_batch(
            session, batch_id=log.batch_id, workspace_id=workspace_id
        )
        for bi in sorted(batch_items, key=lambda r: (r.item_role, r.item_id)):
            materials.append(
                {
                    "item_id": bi.item_id,
                    "item_role": bi.item_role,
                    "expected": _serialize_value(bi.expected_quantity),
                    "actual": _serialize_value(bi.actual_quantity),
                    "unit": None,
                }
            )
            if bi.item_role == "output" and primary_output_item_id is None:
                primary_output_item_id = bi.item_id

    conditions: list[dict[str, Any]] = []
    batch_params = production_batch_stage_parameter_dao.get_by_stage_log(
        session, batch_stage_log_id=log.id, workspace_id=workspace_id
    )
    if batch_params:
        for param in batch_params:
            conditions.append(
                {
                    "label": param.label,
                    "planned": param.planned_value,
                    "actual": param.actual_value,
                    "unit": param.unit,
                }
            )
    elif log.formula_stage_id is not None:
        formula_params = production_formula_stage_parameter_dao.get_by_stage(
            session, formula_stage_id=log.formula_stage_id, workspace_id=workspace_id
        )
        for param in formula_params:
            conditions.append(
                {
                    "label": param.label,
                    "planned": param.planned_value,
                    "actual": None,
                    "unit": param.unit,
                }
            )

    return {
        "output_item_id": primary_output_item_id,
        "materials": materials,
        "conditions": conditions,
        "step_quantities": {
            "expected_output": _serialize_value(
                _log_field(log, field_overrides, "expected_output_quantity")
            ),
            "output": _serialize_value(_log_field(log, field_overrides, "output_quantity")),
            "input": _serialize_value(_log_field(log, field_overrides, "input_quantity")),
            "waste": _serialize_value(_log_field(log, field_overrides, "waste_quantity")),
            "rework": _serialize_value(_log_field(log, field_overrides, "rework_quantity")),
        },
    }


def log_batch_event(
    session: Session,
    *,
    workspace_id: int,
    batch_id: int,
    event_type: str,
    description: str,
    performed_by: Optional[int] = None,
    batch_stage_log_id: Optional[int] = None,
    metadata: Optional[dict] = None,
) -> ProductionBatchEvent:
    event = ProductionBatchEvent(
        workspace_id=workspace_id,
        batch_id=batch_id,
        batch_stage_log_id=batch_stage_log_id,
        event_type=event_type,
        description=description,
        metadata_json=_serialize_value(metadata) if metadata is not None else None,
        performed_by=performed_by,
        created_at=utcnow_aware(),
    )
    session.add(event)
    session.flush()
    return event


BATCH_UPDATE_FIELD_EVENTS: dict[str, tuple[str, str]] = {
    "planned_start_at": ("planned_start_changed", "Planned start"),
    "shift_id": ("shift_changed", "Shift"),
    "batch_date": ("batch_date_changed", "Batch date"),
    "expected_output_quantity": ("expected_output_changed", "Expected output"),
    "expected_duration_minutes": ("expected_duration_changed", "Expected duration"),
    "notes": ("notes_changed", "Notes"),
    "production_line_id": ("batch_line_changed", "Production line"),
    "machine_id": ("batch_machine_changed", "Machine"),
}

STAGE_LOG_FIELD_EVENTS: dict[str, tuple[str, str]] = {
    "production_line_id": ("step_line_changed", "Line"),
    "machine_id": ("step_machine_changed", "Machine"),
    "expected_duration_minutes": ("step_minutes_changed", "Minutes"),
    "output_quantity": ("step_output_changed", "Output qty"),
    "input_quantity": ("step_input_changed", "Input qty"),
    "waste_quantity": ("step_waste_changed", "Waste qty"),
}


def log_batch_update_events(
    session: Session,
    *,
    batch: ProductionBatch,
    update_dict: dict,
    user_id: int,
) -> None:
    for field, (event_type, label) in BATCH_UPDATE_FIELD_EVENTS.items():
        if field not in update_dict:
            continue
        before = getattr(batch, field, None)
        after = update_dict[field]
        if before == after:
            continue
        before_s = _serialize_value(before)
        after_s = _serialize_value(after)
        if field == "notes":
            desc = f"{label} updated"
        else:
            desc = f"{label} changed"
        log_batch_event(
            session,
            workspace_id=batch.workspace_id,
            batch_id=batch.id,
            event_type=event_type,
            description=desc,
            performed_by=user_id,
            metadata={"field": field, "before": before_s, "after": after_s},
        )


def log_stage_log_update_events(
    session: Session,
    *,
    log: ProductionBatchStageLog,
    update_dict: dict,
    user_id: int,
    old_status: str,
) -> None:
    new_status = update_dict.get("status", old_status)
    if new_status != old_status:
        if new_status == "skipped":
            log_batch_event(
                session,
                workspace_id=log.workspace_id,
                batch_id=log.batch_id,
                batch_stage_log_id=log.id,
                event_type="step_skipped",
                description=f"{log.stage_name} skipped",
                performed_by=user_id,
                metadata={"stage_name": log.stage_name},
            )
        elif new_status == "completed":
            output_quantity = update_dict.get("output_quantity", log.output_quantity)
            snapshot = build_step_event_snapshot(
                session,
                log=log,
                workspace_id=log.workspace_id,
                field_overrides=update_dict,
            )
            log_batch_event(
                session,
                workspace_id=log.workspace_id,
                batch_id=log.batch_id,
                batch_stage_log_id=log.id,
                event_type="step_finished",
                description=f"{log.stage_name} finished",
                performed_by=user_id,
                metadata={
                    "stage_name": log.stage_name,
                    "output_quantity": output_quantity,
                    "output_item_id": snapshot.get("output_item_id"),
                    "step_snapshot": snapshot,
                },
            )

    skip_qty_on_status_transition = new_status != old_status and new_status in (
        "completed",
        "skipped",
    )

    for field, (event_type, label) in STAGE_LOG_FIELD_EVENTS.items():
        if field not in update_dict or field == "status":
            continue
        if skip_qty_on_status_transition and field in (
            "output_quantity",
            "input_quantity",
            "waste_quantity",
        ):
            continue
        before = getattr(log, field, None)
        after = update_dict[field]
        if before == after:
            continue
        log_batch_event(
            session,
            workspace_id=log.workspace_id,
            batch_id=log.batch_id,
            batch_stage_log_id=log.id,
            event_type=event_type,
            description=f"{log.stage_name}: {label} changed",
            performed_by=user_id,
            metadata={
                "stage_name": log.stage_name,
                "field": field,
                "before": _serialize_value(before),
                "after": _serialize_value(after),
            },
        )


def log_batch_item_quantity_events(
    session: Session,
    *,
    batch_item: ProductionBatchItem,
    update_dict: dict,
    user_id: Optional[int],
    batch_stage_log_id: Optional[int] = None,
    stage_name: Optional[str] = None,
) -> None:
    stage_meta: dict[str, Any] = {}
    if stage_name:
        stage_meta["stage_name"] = stage_name
    if batch_stage_log_id is not None:
        stage_meta["batch_stage_log_id"] = batch_stage_log_id

    role_phrase = {
        "input": "input",
        "output": "output",
        "waste": "waste",
        "byproduct": "byproduct",
    }.get(batch_item.item_role, "item")

    if "expected_quantity" in update_dict:
        before = batch_item.expected_quantity
        after = update_dict["expected_quantity"]
        if before != after:
            desc = f"Item {role_phrase} expected quantity changed"
            if stage_name:
                desc = f"{stage_name}: {role_phrase} expected quantity changed"
            log_batch_event(
                session,
                workspace_id=batch_item.workspace_id,
                batch_id=batch_item.batch_id,
                batch_stage_log_id=batch_stage_log_id,
                event_type="item_expected_changed",
                description=desc,
                performed_by=user_id,
                metadata={
                    "item_id": batch_item.item_id,
                    "item_role": batch_item.item_role,
                    "before": _serialize_value(before),
                    "after": _serialize_value(after),
                    **stage_meta,
                },
            )
    if "actual_quantity" in update_dict:
        before = batch_item.actual_quantity
        after = update_dict["actual_quantity"]
        if before != after:
            desc = f"Item {role_phrase} actual quantity changed"
            if stage_name:
                desc = f"{stage_name}: {role_phrase} actual quantity changed"
            log_batch_event(
                session,
                workspace_id=batch_item.workspace_id,
                batch_id=batch_item.batch_id,
                batch_stage_log_id=batch_stage_log_id,
                event_type="item_actual_changed",
                description=desc,
                performed_by=user_id,
                metadata={
                    "item_id": batch_item.item_id,
                    "item_role": batch_item.item_role,
                    "before": _serialize_value(before),
                    "after": _serialize_value(after),
                    **stage_meta,
                },
            )


def log_condition_actual_event(
    session: Session,
    *,
    param: ProductionBatchStageParameter,
    before: Optional[str],
    after: Optional[str],
    user_id: Optional[int],
    stage_name: Optional[str] = None,
) -> None:
    before_norm = before.strip() if isinstance(before, str) and before.strip() else None
    after_norm = after.strip() if isinstance(after, str) and after.strip() else None
    if before_norm == after_norm:
        return
    desc = f"{stage_name} updated" if stage_name else "Updated"
    metadata: dict[str, Any] = {
        "stage_name": stage_name,
        "label": param.label,
        "unit": param.unit,
        "planned_value": param.planned_value,
        "before": before_norm,
        "after": after_norm,
    }
    if param.batch_stage_log_id is not None:
        stage_log = session.get(ProductionBatchStageLog, param.batch_stage_log_id)
        if stage_log is not None and stage_log.workspace_id == param.workspace_id:
            metadata["step_snapshot"] = build_step_event_snapshot(
                session, log=stage_log, workspace_id=param.workspace_id
            )
    log_batch_event(
        session,
        workspace_id=param.workspace_id,
        batch_id=param.batch_id,
        batch_stage_log_id=param.batch_stage_log_id,
        event_type="condition_actual_changed",
        description=desc,
        performed_by=user_id,
        metadata=metadata,
    )
