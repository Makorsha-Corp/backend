"""Derive recipe-level output and duration from path stages (not legacy formula items)."""
from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Optional, Sequence, TypeVar

TStage = TypeVar("TStage")
TItem = TypeVar("TItem")


def _stage_order(stage: object) -> int:
    return int(getattr(stage, "stage_order", 0))


def last_formula_stage(stages: Sequence[TStage]) -> Optional[TStage]:
    if not stages:
        return None
    return max(stages, key=_stage_order)


def finished_good_output_quantity(stages: Sequence[object], stage_items: Iterable[object]) -> Decimal:
    last = last_formula_stage(stages)
    if last is None:
        return Decimal("0")
    last_id = getattr(last, "id", None)
    if last_id is None:
        return Decimal("0")
    total = Decimal("0")
    for row in stage_items:
        if getattr(row, "formula_stage_id", None) != last_id:
            continue
        if getattr(row, "item_role", None) != "output":
            continue
        total += Decimal(str(getattr(row, "quantity", 0) or 0))
    return total


def estimated_recipe_duration_minutes(stages: Sequence[object]) -> Optional[int]:
    if not stages:
        return None
    total = 0
    any_set = False
    for stage in stages:
        minutes = getattr(stage, "expected_duration_minutes", None)
        if minutes is not None:
            total += int(minutes)
            any_set = True
    return total if any_set else None
