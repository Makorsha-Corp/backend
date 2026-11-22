#!/usr/bin/env python3
"""Merge duplicate machine_items rows (BUG-983): one row per workspace + machine + item.

For each duplicated pair the lowest-id row is kept: `qty` and `defective_qty`
become the sums of the group, `req_qty` stays if set, otherwise it takes the
first value set on a later row. The other rows are deleted. Nothing else
references machine_items.id, and ledger rows are not touched.

Dry run by default: prints what would change and rolls back. Pass --apply to
commit. All merges run in one transaction, with the rows locked, so run it
before the unique index goes on, and again if the index fails to build.

The script does not post ledger adjustments. A pair whose merged qty differs
from its ledger balance is printed; review it, then use POST
/ledgers/machine/reconcile/, which treats the ledger as the source of truth.

Usage:
    python scripts/merge_duplicate_machine_items.py [--apply]
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.dao.machine_item_ledger import machine_item_ledger_dao
from app.db.session import SessionLocal
from app.models.machine_item import MachineItem


@dataclass
class Merge:
    workspace_id: int
    machine_id: int
    item_id: int
    kept_id: int
    deleted_ids: list[int]
    qty_before: list[int]
    qty: int
    defective_qty: int | None
    req_qty: int | None
    req_qty_conflict: list[int]
    ledger_qty: int


def merge_duplicates(session: Session) -> list[Merge]:
    """Merge every duplicated pair in the session's transaction. Does not commit."""
    pairs = session.execute(
        select(MachineItem.workspace_id, MachineItem.machine_id, MachineItem.item_id)
        .group_by(MachineItem.workspace_id, MachineItem.machine_id, MachineItem.item_id)
        .having(func.count(MachineItem.id) > 1)
        .order_by(MachineItem.workspace_id, MachineItem.machine_id, MachineItem.item_id)
    ).all()

    merges = []
    for workspace_id, machine_id, item_id in pairs:
        rows = session.scalars(
            select(MachineItem)
            .where(
                MachineItem.workspace_id == workspace_id,
                MachineItem.machine_id == machine_id,
                MachineItem.item_id == item_id,
            )
            .order_by(MachineItem.id)
            .with_for_update(of=MachineItem)
        ).unique().all()
        if len(rows) < 2:  # merged by someone else since the first query
            continue

        keep, others = rows[0], rows[1:]
        qty_before = [r.qty for r in rows]
        req_values = [r.req_qty for r in rows if r.req_qty is not None]
        defective_values = [r.defective_qty for r in rows if r.defective_qty is not None]

        keep.qty = sum(qty_before)
        keep.defective_qty = sum(defective_values) if defective_values else None
        keep.req_qty = req_values[0] if req_values else None
        for row in others:
            session.delete(row)
        session.flush()

        ledger_qty, _ = machine_item_ledger_dao.calculate_balance(
            session, machine_id=machine_id, item_id=item_id, workspace_id=workspace_id
        )
        merges.append(Merge(
            workspace_id=workspace_id,
            machine_id=machine_id,
            item_id=item_id,
            kept_id=keep.id,
            deleted_ids=[r.id for r in others],
            qty_before=qty_before,
            qty=keep.qty,
            defective_qty=keep.defective_qty,
            req_qty=keep.req_qty,
            req_qty_conflict=sorted(set(req_values)) if len(set(req_values)) > 1 else [],
            ledger_qty=ledger_qty,
        ))
    return merges


def report(merges: list[Merge]) -> None:
    for m in merges:
        print(
            f"workspace {m.workspace_id} machine {m.machine_id} item {m.item_id}: "
            f"keep row {m.kept_id}, delete {m.deleted_ids}, "
            f"qty {'+'.join(map(str, m.qty_before))} = {m.qty}"
        )
        if m.req_qty_conflict:
            print(f"  req_qty differed {m.req_qty_conflict}: kept {m.req_qty}")
        if m.ledger_qty != m.qty:
            print(f"  ledger balance is {m.ledger_qty}, not {m.qty}: review, then reconcile")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="commit the merges (default: dry run)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        merges = merge_duplicates(db)
        report(merges)
        if args.apply:
            db.commit()
        else:
            db.rollback()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    verb = "merged" if args.apply else "would merge (dry run, nothing changed)"
    print(f"{len(merges)} duplicated pair(s) {verb}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
