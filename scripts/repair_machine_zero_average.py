#!/usr/bin/env python3
"""Restore the machine average lost to manual stock changes (BUG-993, spec Q1).

A machine's average lives in its newest ledger entry. Manual changes used to
write 0.00 there, so every later movement read 0.00. For each machine + item
whose latest entry has a zero average, a non-zero quantity and an earlier
non-zero average, this appends one `inventory_adjustment` entry: quantity 0,
quantity unchanged, `avg_price_after` and `unit_cost` = the last non-zero
average, `value_after` = qty x that average. Appends only: no existing ledger
row and no `machine_items` row is edited. Work orders already costed at 0.00
stay, and a blended average (a receipt on top of 0.00) stays, because it cannot
be told from a real one.

Printed and left alone:
- the zero did not come from a manual change: the first zero entry after the
  last non-zero average is not `manual` / `adjustment`, e.g. a receipt at 0.00
  with no stock on the machine, which is a real average;
- no stock row, or two of them for the pair (run
  scripts/merge_duplicate_machine_items.py first);
- a new entry arrived while the script ran.

Not a target at all: an empty latest average, and a machine + item that never
had a non-zero average (a first entry with no history stays 0.00).

A quantity that differs from the stock row is printed: review it, then use
POST /ledgers/machine/reconcile/.

The database is whatever app settings give: DATABASE_URL from the environment,
otherwise from the `.env` file in the backend folder. It is printed first. Dry
run by default: prints what would change and rolls back. Pass --apply to
commit. All repairs run in one transaction, with the stock rows locked.

Usage:
    python scripts/repair_machine_zero_average.py --performed-by PROFILE_ID [--apply]
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

import app.db.base  # noqa: F401  (registers every model)
from app.dao.machine_item_ledger import machine_item_ledger_dao
from app.db.session import SessionLocal
from app.models.machine_item import MachineItem
from app.models.machine_item_ledger import MachineItemLedger
from app.models.profile import Profile

MANUAL_SOURCE_TYPES = ("manual", "adjustment")
REPAIR_SOURCE_TYPE = "repair"


@dataclass
class Repair:
    workspace_id: int
    machine_id: int
    item_id: int
    latest_id: int
    source_id: int
    qty: int
    average: Decimal
    value: Decimal
    new_id: int
    stock_qty: int


@dataclass
class Skip:
    workspace_id: int
    machine_id: int
    item_id: int
    latest_id: int
    reason: str


def _same_key(entry: MachineItemLedger):
    return (
        MachineItemLedger.workspace_id == entry.workspace_id,
        MachineItemLedger.machine_id == entry.machine_id,
        MachineItemLedger.item_id == entry.item_id,
    )


def _before(entry: MachineItemLedger):
    return or_(
        MachineItemLedger.performed_at < entry.performed_at,
        and_(MachineItemLedger.performed_at == entry.performed_at, MachineItemLedger.id < entry.id),
    )


def _after(entry: MachineItemLedger):
    return or_(
        MachineItemLedger.performed_at > entry.performed_at,
        and_(MachineItemLedger.performed_at == entry.performed_at, MachineItemLedger.id > entry.id),
    )


def _zero_latest_entries(session: Session) -> list[MachineItemLedger]:
    ranked = select(
        MachineItemLedger.id,
        func.row_number()
        .over(
            partition_by=(
                MachineItemLedger.workspace_id,
                MachineItemLedger.machine_id,
                MachineItemLedger.item_id,
            ),
            order_by=(MachineItemLedger.performed_at.desc(), MachineItemLedger.id.desc()),
        )
        .label("position"),
    ).subquery()
    return list(session.scalars(
        select(MachineItemLedger)
        .join(ranked, MachineItemLedger.id == ranked.c.id)
        .where(
            ranked.c.position == 1,
            MachineItemLedger.avg_price_after == 0,
            MachineItemLedger.qty_after != 0,
        )
        .order_by(
            MachineItemLedger.workspace_id,
            MachineItemLedger.machine_id,
            MachineItemLedger.item_id,
        )
    ).all())


def _skip(latest: MachineItemLedger, reason: str) -> Skip:
    return Skip(latest.workspace_id, latest.machine_id, latest.item_id, latest.id, reason)


def repair_zero_averages(session: Session, performed_by: int) -> tuple[list[Repair], list[Skip]]:
    """Append one entry per target in the session's transaction. Does not commit."""
    repairs: list[Repair] = []
    skips: list[Skip] = []

    for latest in _zero_latest_entries(session):
        last_priced = session.scalars(
            select(MachineItemLedger)
            .where(*_same_key(latest), _before(latest), MachineItemLedger.avg_price_after > 0)
            .order_by(MachineItemLedger.performed_at.desc(), MachineItemLedger.id.desc())
            .limit(1)
        ).first()
        if last_priced is None:  # never had a cost: a first entry stays 0.00
            continue

        first_zero = session.scalars(
            select(MachineItemLedger)
            .where(*_same_key(latest), _after(last_priced))
            .order_by(MachineItemLedger.performed_at, MachineItemLedger.id)
            .limit(1)
        ).first()
        if first_zero.source_type not in MANUAL_SOURCE_TYPES:
            skips.append(_skip(
                latest,
                f"the zero came from entry {first_zero.id} "
                f"(source_type {first_zero.source_type}), not from a manual change",
            ))
            continue

        stock_rows = session.scalars(
            select(MachineItem)
            .where(
                MachineItem.workspace_id == latest.workspace_id,
                MachineItem.machine_id == latest.machine_id,
                MachineItem.item_id == latest.item_id,
            )
            .order_by(MachineItem.id)
            .with_for_update(of=MachineItem)
        ).unique().all()
        if not stock_rows:
            skips.append(_skip(latest, "no stock row for this machine and item"))
            continue
        if len(stock_rows) > 1:
            skips.append(_skip(latest, "two stock rows: run scripts/merge_duplicate_machine_items.py first"))
            continue

        newer = session.scalars(
            select(MachineItemLedger).where(*_same_key(latest), _after(latest)).limit(1)
        ).first()
        if newer is not None:  # a movement landed before the lock
            skips.append(_skip(latest, f"entry {newer.id} arrived while the script ran"))
            continue

        average = last_priced.avg_price_after
        qty = latest.qty_after
        value = Decimal(qty) * average
        entry = machine_item_ledger_dao.create(session, obj_in={
            "workspace_id": latest.workspace_id,
            "machine_id": latest.machine_id,
            "item_id": latest.item_id,
            "transaction_type": "inventory_adjustment",
            "quantity": 0,
            "unit_cost": average,
            "total_cost": Decimal("0.00"),
            "qty_before": qty,
            "qty_after": qty,
            "value_before": Decimal("0.00"),
            "value_after": value,
            "avg_price_before": Decimal("0.00"),
            "avg_price_after": average,
            "source_type": REPAIR_SOURCE_TYPE,
            "notes": f"Average restored from ledger entry {last_priced.id} (BUG-993)",
            "performed_by": performed_by,
        })
        repairs.append(Repair(
            workspace_id=latest.workspace_id,
            machine_id=latest.machine_id,
            item_id=latest.item_id,
            latest_id=latest.id,
            source_id=last_priced.id,
            qty=qty,
            average=average,
            value=value,
            new_id=entry.id,
            stock_qty=stock_rows[0].qty,
        ))
    return repairs, skips


def report(repairs: list[Repair], skips: list[Skip]) -> None:
    for r in repairs:
        print(
            f"workspace {r.workspace_id} machine {r.machine_id} item {r.item_id}: "
            f"append after entry {r.latest_id}: qty {r.qty}, average {r.average} "
            f"(from entry {r.source_id}), value {r.value}"
        )
        if r.stock_qty != r.qty:
            print(f"  stock row says {r.stock_qty}, not {r.qty}: review, then reconcile")
    for s in skips:
        print(
            f"workspace {s.workspace_id} machine {s.machine_id} item {s.item_id}: "
            f"left alone, entry {s.latest_id}: {s.reason}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--performed-by", type=int, required=True,
        help="profile id recorded on the appended entries (performed_by is NOT NULL)",
    )
    parser.add_argument("--apply", action="store_true", help="commit the repairs (default: dry run)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        print(f"database: {db.connection().engine.url.database}")
        if db.get(Profile, args.performed_by) is None:
            print(f"profile {args.performed_by} not found", file=sys.stderr)
            db.rollback()
            return 2
        repairs, skips = repair_zero_averages(db, args.performed_by)
        report(repairs, skips)
        if args.apply:
            db.commit()
        else:
            db.rollback()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    verb = "appended" if args.apply else "would be appended (dry run, nothing changed)"
    print(f"{len(repairs)} entry(ies) {verb}, {len(skips)} left alone")
    return 0


if __name__ == "__main__":
    sys.exit(main())
