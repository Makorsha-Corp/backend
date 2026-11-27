#!/usr/bin/env python3
"""Restate stored averages rounded half to even (BUG-1040, spec Q2, Q2a).

Python rounded divided averages half to even; money rounds half up (HR-15).
Owner, 2026-10-31: "Found rows only": correct only the found rows' own columns;
later rows and current averages stay. This is the one approved in-place edit of
ledger rows.

A row is found from its own columns alone. With
    n = qty_before * average before + quantity * unit_cost
    d = qty_before + quantity
n / d must be an exact midpoint (third decimal 5, nothing after it) and the
stored average must be the half-even value where half up differs. For a work
order line, n = total_cost and d = quantity, over consumed lines.

| Table | Rows looked at | Columns written |
|---|---|---|
| machine_item_ledger | every entry | avg_price_after, value_after = qty_after x it |
| inventory_ledger | source_type not manual / adjustment | avg_price_after |
| product_ledger | transaction_type production | avg_cost_after |
| work_order_items | consumed lines | unit_cost (updated_at stamps itself) |

Printed and left alone: a found row that is the latest entry of its machine +
item, or of its factory + item + stock type. The average in use is read from
that entry, so correcting it would change a current average.

Run scripts/repair_machine_zero_average.py first: otherwise the repair could
carry a corrected average forward and change a current average.

Not handled: `total_cost` rows. No app path should produce one, and one that
exists cannot be restated, because the original price is stored nowhere. This
script looks at averages only.

The database is whatever app settings give: DATABASE_URL from the environment,
otherwise from the `.env` file in the backend folder. It is printed first. Dry
run by default: prints what would change and rolls back. Pass --apply to
commit. All restatements run in one transaction, with the found rows locked.

Usage:
    python scripts/restate_half_even_averages.py [--apply]
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

import app.db.base  # noqa: F401  (registers every model)
from app.db.session import SessionLocal
from app.models.inventory_ledger import InventoryLedger
from app.models.machine_item_ledger import MachineItemLedger
from app.models.product_ledger import ProductLedger
from app.models.work_order_item import WorkOrderItem

CENT = Decimal("0.01")


@dataclass
class Restated:
    table: str
    id: int
    workspace_id: int
    column: str
    old: Decimal
    new: Decimal
    value_old: Decimal | None = None
    value_new: Decimal | None = None


@dataclass
class Skip:
    table: str
    id: int
    workspace_id: int
    column: str
    old: Decimal
    new: Decimal


def half_even_differs(numerator: Decimal, denominator: Decimal, stored: Decimal) -> Decimal | None:
    """The half-up value when `stored` is the half-even value and they differ."""
    value = numerator / denominator
    up = value.quantize(CENT, rounding=ROUND_HALF_UP)
    even = value.quantize(CENT, rounding=ROUND_HALF_EVEN)
    if up != even and stored == even:
        return up
    return None


def _is_latest(session: Session, model, row, key_columns: tuple) -> bool:
    newer = session.scalars(
        select(model.id)
        .where(
            *[getattr(model, c) == getattr(row, c) for c in key_columns],
            or_(
                model.performed_at > row.performed_at,
                and_(model.performed_at == row.performed_at, model.id > row.id),
            ),
        )
        .limit(1)
    ).first()
    return newer is None


def _midpoint_candidates(session: Session, model, before, after, *conditions) -> list:
    numerator = model.qty_before * before + model.quantity * model.unit_cost
    denominator = model.qty_before + model.quantity
    return list(session.scalars(
        select(model)
        .where(
            model.qty_before > 0,
            model.quantity > 0,
            before.is_not(None),
            after.is_not(None),
            model.unit_cost.is_not(None),
            numerator > 0,
            func.mod(numerator * 200, denominator) == 0,
            *conditions,
        )
        .order_by(model.id)
        .with_for_update(of=model)
    ).unique().all())


def _ledger_new_value(row, before: Decimal, after: Decimal) -> Decimal | None:
    numerator = Decimal(row.qty_before) * before + Decimal(row.quantity) * row.unit_cost
    return half_even_differs(numerator, Decimal(row.qty_before + row.quantity), after)


def _restate_machine(session: Session, done: list[Restated], skipped: list[Skip]) -> None:
    model = MachineItemLedger
    for row in _midpoint_candidates(session, model, model.avg_price_before, model.avg_price_after):
        new = _ledger_new_value(row, row.avg_price_before, row.avg_price_after)
        if new is None:
            continue
        old = row.avg_price_after
        if _is_latest(session, model, row, ("workspace_id", "machine_id", "item_id")):
            skipped.append(Skip(model.__tablename__, row.id, row.workspace_id, "avg_price_after", old, new))
            continue
        value_old = row.value_after
        row.avg_price_after = new
        row.value_after = Decimal(row.qty_after) * new
        done.append(Restated(
            model.__tablename__, row.id, row.workspace_id, "avg_price_after", old, new,
            value_old, row.value_after,
        ))


def _restate_inventory(session: Session, done: list[Restated], skipped: list[Skip]) -> None:
    model = InventoryLedger
    keep_out = model.source_type.is_(None) | model.source_type.not_in(("manual", "adjustment"))
    for row in _midpoint_candidates(session, model, model.avg_price_before, model.avg_price_after, keep_out):
        new = _ledger_new_value(row, row.avg_price_before, row.avg_price_after)
        if new is None:
            continue
        old = row.avg_price_after
        if _is_latest(session, model, row, ("workspace_id", "factory_id", "item_id", "inventory_type")):
            skipped.append(Skip(model.__tablename__, row.id, row.workspace_id, "avg_price_after", old, new))
            continue
        row.avg_price_after = new
        done.append(Restated(model.__tablename__, row.id, row.workspace_id, "avg_price_after", old, new))


def _restate_product(session: Session, done: list[Restated]) -> None:
    model = ProductLedger
    for row in _midpoint_candidates(
        session, model, model.avg_cost_before, model.avg_cost_after, model.transaction_type == "production"
    ):
        new = _ledger_new_value(row, row.avg_cost_before, row.avg_cost_after)
        if new is None:
            continue
        old = row.avg_cost_after
        row.avg_cost_after = new
        done.append(Restated(model.__tablename__, row.id, row.workspace_id, "avg_cost_after", old, new))


def _restate_work_order_lines(session: Session, done: list[Restated]) -> None:
    model = WorkOrderItem
    lines = session.scalars(
        select(model)
        .where(
            model.consumed_at.is_not(None),
            model.total_cost > 0,
            model.quantity > 0,
            model.unit_cost.is_not(None),
            func.mod(model.quantity, 1) == 0,
            func.mod(model.total_cost * 200, model.quantity) == 0,
        )
        .order_by(model.id)
        .with_for_update(of=model)
    ).unique().all()
    for line in lines:
        new = half_even_differs(line.total_cost, line.quantity, line.unit_cost)
        if new is None:
            continue
        old = line.unit_cost
        line.unit_cost = new
        done.append(Restated(model.__tablename__, line.id, line.workspace_id, "unit_cost", old, new))


def restate(session: Session) -> tuple[list[Restated], list[Skip]]:
    """Correct every found row in the session's transaction. Does not commit."""
    done: list[Restated] = []
    skipped: list[Skip] = []
    _restate_machine(session, done, skipped)
    _restate_inventory(session, done, skipped)
    _restate_product(session, done)
    _restate_work_order_lines(session, done)
    session.flush()
    return done, skipped


def report(done: list[Restated], skipped: list[Skip]) -> None:
    for r in done:
        line = f"{r.table} {r.id} (workspace {r.workspace_id}): {r.column} {r.old} -> {r.new}"
        if r.value_new is not None:
            line += f", value_after {r.value_old} -> {r.value_new}"
        print(line)
    for s in skipped:
        print(
            f"{s.table} {s.id} (workspace {s.workspace_id}): left alone, latest entry: "
            f"{s.column} {s.old}, half up {s.new}, correcting it would change a current average"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="commit the corrections (default: dry run)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        print(f"database: {db.connection().engine.url.database}")
        done, skipped = restate(db)
        report(done, skipped)
        if args.apply:
            db.commit()
        else:
            db.rollback()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    verb = "restated" if args.apply else "would be restated (dry run, nothing changed)"
    print(f"{len(done)} row(s) {verb}, {len(skipped)} left alone")
    return 0


if __name__ == "__main__":
    sys.exit(main())
