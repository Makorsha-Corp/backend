"""Aggregate production overview stats (line → recipe)."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.models.production_batch import ProductionBatch
from app.models.production_batch_stage_log import ProductionBatchStageLog
from app.models.production_batch_stage_parameter import ProductionBatchStageParameter
from app.utils.production_parameter_numeric import optional_numeric_from_text
from app.utils.production_stage_metrics import duration_minutes

LATE_START_THRESHOLD_MINUTES = 15
YIELD_OUTLIER_PP = 10.0
TIME_OUTLIER_PP = 15.0
MAX_OUTLIERS = 20
SIMPLE_RECIPE_KEY = 0


def _recipe_key(formula_id: Optional[int]) -> int:
    return formula_id if formula_id is not None else SIMPLE_RECIPE_KEY


def _recipe_name(formula_id: Optional[int], formula_names: Dict[int, str]) -> str:
    if formula_id is None:
        return "Simple run"
    return formula_names.get(formula_id, f"Recipe #{formula_id}")


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _weighted_mean(pairs: Sequence[Tuple[float, float]]) -> Optional[float]:
    if not pairs:
        return None
    total_w = sum(w for _, w in pairs)
    if total_w <= 0:
        return None
    return sum(v * w for v, w in pairs) / total_w


@dataclass
class _Bucket:
    batch_count: int = 0
    output_sum: float = 0.0
    output_has: bool = False
    waste_sum: float = 0.0
    waste_has: bool = False
    yield_pairs: List[Tuple[float, float]] = field(default_factory=list)
    time_pairs: List[Tuple[float, float]] = field(default_factory=list)
    lag_minutes: List[float] = field(default_factory=list)
    late_start_count: int = 0
    gap_minutes: List[float] = field(default_factory=list)
    condition: Dict[str, List[Tuple[float, Optional[str]]]] = field(default_factory=lambda: defaultdict(list))

    def add_batch(self) -> None:
        self.batch_count += 1

    def add_output(self, quantity: float) -> None:
        if quantity > 0:
            self.output_sum += quantity
            self.output_has = True

    def add_waste(self, quantity: float) -> None:
        if quantity > 0:
            self.waste_sum += quantity
            self.waste_has = True

    def add_yield(self, pct: float, weight: float) -> None:
        if weight > 0:
            self.yield_pairs.append((pct, weight))

    def add_time(self, pct: float, weight: float = 1.0) -> None:
        if weight > 0:
            self.time_pairs.append((pct, weight))

    def add_lag(self, minutes: float) -> None:
        self.lag_minutes.append(minutes)
        if minutes > LATE_START_THRESHOLD_MINUTES:
            self.late_start_count += 1

    def add_gap(self, minutes: float) -> None:
        if minutes >= 0:
            self.gap_minutes.append(minutes)

    def add_condition_drift(self, label: str, drift: float, unit: Optional[str]) -> None:
        self.condition[label].append((drift, unit))


def _bucket_key(line_id: int, formula_id: Optional[int]) -> Tuple[int, int]:
    return (line_id, _recipe_key(formula_id))


def build_overview_stats(
    *,
    batches: Sequence[ProductionBatch],
    logs_by_batch: Dict[int, List[ProductionBatchStageLog]],
    params_by_log: Dict[int, List[ProductionBatchStageParameter]],
    items_by_batch: Optional[Dict[int, List[Any]]] = None,
    line_names: Dict[int, str],
    formula_names: Dict[int, str],
    date_from: date,
    date_to: date,
) -> Dict[str, Any]:
    buckets: Dict[Tuple[int, int], _Bucket] = defaultdict(_Bucket)
    batch_outlier_candidates: List[Dict[str, Any]] = []

    items_by_batch = items_by_batch or {}

    for batch in batches:
        formula_id = batch.formula_id
        batch_line_id = batch.production_line_id
        rk = _recipe_key(formula_id)
        batch_bucket = buckets[_bucket_key(batch_line_id, formula_id)]
        batch_bucket.add_batch()

        if batch.status == "completed":
            actual_out = _to_float(getattr(batch, "actual_output_quantity", None))
            if actual_out is not None and actual_out > 0:
                batch_bucket.add_output(actual_out)
            for item in items_by_batch.get(batch.id, []):
                if getattr(item, "item_role", None) != "waste":
                    continue
                waste_qty = _to_float(getattr(item, "actual_quantity", None))
                if waste_qty is not None and waste_qty > 0:
                    batch_bucket.add_waste(waste_qty)

        started = batch.started_at or batch.actual_start_time
        if started and batch.planned_start_at and batch.status in ("in_progress", "completed"):
            lag = (started - batch.planned_start_at).total_seconds() / 60.0
            b = buckets[_bucket_key(batch_line_id, formula_id)]
            b.add_lag(lag)

        if batch.status == "completed":
            expected_out = batch.expected_output_quantity
            eff = _to_float(batch.efficiency_percentage)
            if eff is not None and expected_out and expected_out > 0:
                buckets[_bucket_key(batch_line_id, formula_id)].add_yield(eff, float(expected_out))

            expected_dur = batch.expected_duration_minutes
            actual_dur = batch.actual_duration_minutes
            if actual_dur is None and started and batch.actual_end_time:
                actual_dur = duration_minutes(started, batch.actual_end_time)
            if (
                expected_dur is not None
                and expected_dur > 0
                and actual_dur is not None
            ):
                time_pct = (actual_dur / expected_dur) * 100.0
                buckets[_bucket_key(batch_line_id, formula_id)].add_time(time_pct)
                batch_outlier_candidates.append(
                    {
                        "batch": batch,
                        "line_id": batch_line_id,
                        "formula_id": formula_id,
                        "yield_pct": eff,
                        "time_pct": time_pct,
                        "yield_weight": float(expected_out or 1),
                    }
                )

        logs = sorted(
            logs_by_batch.get(batch.id, []),
            key=lambda row: (row.stage_order, row.id),
        )
        for idx, log in enumerate(logs):
            step_line_id = log.production_line_id or batch_line_id
            step_bucket = buckets[_bucket_key(step_line_id, formula_id)]

            if log.status == "completed" and log.started_at and log.completed_at:
                step_dur = duration_minutes(log.started_at, log.completed_at)
                exp_step = log.expected_duration_minutes
                if step_dur is not None and exp_step and exp_step > 0:
                    step_bucket.add_time((step_dur / exp_step) * 100.0)

            if idx > 0:
                prev = logs[idx - 1]
                if prev.completed_at and log.started_at:
                    gap = (log.started_at - prev.completed_at).total_seconds() / 60.0
                    step_bucket.add_gap(gap)

            for param in params_by_log.get(log.id, []):
                planned_n = optional_numeric_from_text(param.planned_value)
                actual_n = optional_numeric_from_text(param.actual_value)
                if planned_n is None or actual_n is None:
                    continue
                drift = float(actual_n - planned_n)
                step_bucket.add_condition_drift(param.label, drift, param.unit)

    group_yield: Dict[Tuple[int, int], Optional[float]] = {}
    group_time: Dict[Tuple[int, int], Optional[float]] = {}
    for key, bucket in buckets.items():
        group_yield[key] = _weighted_mean(bucket.yield_pairs)
        group_time[key] = _weighted_mean(bucket.time_pairs)

    outliers: List[Dict[str, Any]] = []
    for cand in batch_outlier_candidates:
        key = _bucket_key(cand["line_id"], cand["formula_id"])
        batch = cand["batch"]
        if cand["yield_pct"] is not None:
            avg_y = group_yield.get(key)
            if avg_y is not None and abs(cand["yield_pct"] - avg_y) > YIELD_OUTLIER_PP:
                outliers.append(
                    {
                        "batch_id": batch.id,
                        "batch_number": batch.batch_number,
                        "production_line_id": cand["line_id"],
                        "line_name": line_names.get(cand["line_id"], f"Line #{cand['line_id']}"),
                        "formula_id": cand["formula_id"] if cand["formula_id"] is not None else None,
                        "recipe_name": _recipe_name(cand["formula_id"], formula_names),
                        "metric": "yield",
                        "delta_from_group": round(cand["yield_pct"] - avg_y, 2),
                    }
                )
        if cand["time_pct"] is not None:
            avg_t = group_time.get(key)
            if avg_t is not None and abs(cand["time_pct"] - avg_t) > TIME_OUTLIER_PP:
                outliers.append(
                    {
                        "batch_id": batch.id,
                        "batch_number": batch.batch_number,
                        "production_line_id": cand["line_id"],
                        "line_name": line_names.get(cand["line_id"], f"Line #{cand['line_id']}"),
                        "formula_id": cand["formula_id"] if cand["formula_id"] is not None else None,
                        "recipe_name": _recipe_name(cand["formula_id"], formula_names),
                        "metric": "time",
                        "delta_from_group": round(cand["time_pct"] - avg_t, 2),
                    }
                )

    outliers.sort(key=lambda row: abs(row["delta_from_group"]), reverse=True)
    outliers = outliers[:MAX_OUTLIERS]

    lines_out: List[Dict[str, Any]] = []
    line_ids = sorted({k[0] for k in buckets.keys()})
    for line_id in line_ids:
        recipe_keys = sorted({k[1] for k in buckets.keys() if k[0] == line_id})
        recipe_rows: List[Dict[str, Any]] = []
        line_yield: List[Tuple[float, float]] = []
        line_time: List[Tuple[float, float]] = []
        line_lags: List[float] = []
        line_late = 0
        line_gaps: List[float] = []
        line_batch_count = 0
        line_output_sum = 0.0
        line_output_has = False
        line_waste_sum = 0.0
        line_waste_has = False

        for rk in recipe_keys:
            formula_id = None if rk == SIMPLE_RECIPE_KEY else rk
            bucket = buckets[(line_id, rk)]
            line_yield.extend(bucket.yield_pairs)
            line_time.extend(bucket.time_pairs)
            line_lags.extend(bucket.lag_minutes)
            line_late += bucket.late_start_count
            line_gaps.extend(bucket.gap_minutes)
            line_batch_count += bucket.batch_count
            if bucket.output_has:
                line_output_sum += bucket.output_sum
                line_output_has = True
            if bucket.waste_has:
                line_waste_sum += bucket.waste_sum
                line_waste_has = True

            drifts_out: List[Dict[str, Any]] = []
            for label, entries in bucket.condition.items():
                if not entries:
                    continue
                avg_drift = sum(d for d, _ in entries) / len(entries)
                unit = next((u for _, u in entries if u), None)
                drifts_out.append(
                    {
                        "label": label,
                        "unit": unit,
                        "avg_drift": round(avg_drift, 4),
                        "steps_with_actual": len(entries),
                    }
                )
            drifts_out.sort(key=lambda row: abs(row["avg_drift"]), reverse=True)

            recipe_rows.append(
                {
                    "formula_id": formula_id,
                    "recipe_name": _recipe_name(formula_id, formula_names),
                    "batch_count": bucket.batch_count,
                    "output_quantity": _round_opt(bucket.output_sum) if bucket.output_has else None,
                    "waste_quantity": _round_opt(bucket.waste_sum) if bucket.waste_has else None,
                    "yield_pct": _round_opt(_weighted_mean(bucket.yield_pairs)),
                    "time_vs_plan_pct": _round_opt(_weighted_mean(bucket.time_pairs)),
                    "avg_start_lag_minutes": _round_opt(_mean(bucket.lag_minutes)),
                    "late_start_count": bucket.late_start_count,
                    "avg_step_gap_minutes": _round_opt(_mean(bucket.gap_minutes)),
                    "condition_drifts": drifts_out[:5],
                }
            )

        lines_out.append(
            {
                "production_line_id": line_id,
                "line_name": line_names.get(line_id, f"Line #{line_id}"),
                "batch_count": line_batch_count,
                "output_quantity": _round_opt(line_output_sum) if line_output_has else None,
                "waste_quantity": _round_opt(line_waste_sum) if line_waste_has else None,
                "yield_pct": _round_opt(_weighted_mean(line_yield)),
                "time_vs_plan_pct": _round_opt(_weighted_mean(line_time)),
                "avg_start_lag_minutes": _round_opt(_mean(line_lags)),
                "late_start_count": line_late,
                "avg_step_gap_minutes": _round_opt(_mean(line_gaps)),
                "recipes": recipe_rows,
            }
        )

    return {
        "date_from": date_from,
        "date_to": date_to,
        "lines": lines_out,
        "outliers": outliers,
    }


def _mean(values: Sequence[float]) -> Optional[float]:
    if not values:
        return None
    return sum(values) / len(values)


def _round_opt(value: Optional[float], places: int = 2) -> Optional[float]:
    if value is None:
        return None
    return round(value, places)
