"""Unit tests for app/managers/machine_item_manager.py.

Implements tests/unit/managers/machine_item_manager.cases.md, one test per case,
in card order. Real Postgres session (`db` fixture). Nothing is patched except
the race simulation of MIM-C-25, as Conventions allow.

Normal mode: every test is written from its card and carries a `# [claude] <ID>`
comment. Row names of the cards are the lower-case names here (M1 -> m1, `F1.id`
-> `f1.id`); `# Then N` marks the checks of the card's Then line N.
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`)
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException
from psycopg2.errors import ForeignKeyViolation
from pydantic import ValidationError
from sqlalchemy import event, func, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import DataError, IntegrityError

from app.dao.machine_item_ledger import machine_item_ledger_dao
from app.managers.inventory_movements import (
    _machine_in,
    _machine_out,
    get_machine_unit_cost,
)
from app.managers.machine_item_manager import machine_item_manager
from app.models.factory import Factory
from app.models.item import Item
from app.models.machine import Machine
from app.models.machine_activity_event import MachineActivityEvent
from app.models.machine_item import MachineItem
from app.models.machine_item_ledger import MachineItemLedger
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.purchase_order_return import (
    PurchaseOrderReturn,
    PurchaseOrderReturnItem,
)
from app.models.status import Status
from app.models.transfer_order import TransferOrder
from app.models.transfer_order_item import TransferOrderItem
from app.models.work_order import WorkOrder
from app.models.work_order_item import WorkOrderItem
from app.models.work_order_type import WorkOrderType
from app.schemas.machine_item import (
    MachineItemBase,
    MachineItemCreate,
    MachineItemUpdate,
)
from app.utils.time import utcnow
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "M = the singleton machine_item_manager" (a module-level name, not a fixture)
M = machine_item_manager

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999

# Conventions "T9, T10, T11, T12" (naive, in the past)
T9 = datetime(2025, 1, 1, 9, 0, 0)  # noqa: DTZ001
T10 = datetime(2025, 1, 1, 10, 0, 0)  # noqa: DTZ001
T11 = datetime(2025, 1, 1, 11, 0, 0)  # noqa: DTZ001
T12 = datetime(2025, 1, 1, 12, 0, 0)  # noqa: DTZ001


def _add(db, row):
    db.add(row)
    db.flush()
    return row


def next_clock_tick():
    """Wait until the clock has moved on; patches nothing.

    The chain cards (MIM-W-21 ... MIM-W-25) write ledger entries with the real
    clock and rely on "the manager's own entry is the newest". The clock of
    Python 3.12 on Windows ticks every few milliseconds, so two entries can get
    the same `performed_at`, and the latest one is then a coin toss (BUG-664).
    See DISCREPANCY-1 in the notes.
    """
    start = utcnow()
    while utcnow() == start:
        pass


# --------------------------------------------------------------------------- #
# Conventions -> fixtures (the standing rows). Each fixture depends on the one
# before it, so the rows are inserted in the order Conventions list them.
# --------------------------------------------------------------------------- #

@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


# U1 = created_by of every Given row; U2 = the acting user of the calls
@pytest.fixture
def u1(db, w2):
    return make_profile(db)


@pytest.fixture
def u2(db, u1):
    return make_profile(db)


def _factory(db, ws, name, abbreviation, is_active=True, is_deleted=False):
    return _add(db, Factory(
        workspace_id=ws.id, name=name, abbreviation=abbreviation, is_active=is_active, is_deleted=is_deleted,
    ))


@pytest.fixture
def f1(db, w1, u2):
    return _factory(db, w1, "Main Plant", "MP")


# Convention: FD has is_deleted True, is_active stays True
@pytest.fixture
def fd(db, w1, f1):
    return _factory(db, w1, "Closed Mill", "CM", is_deleted=True)


@pytest.fixture
def fi(db, w1, fd):
    return _factory(db, w1, "Idle Plant", "IP", is_active=False)


@pytest.fixture
def f9(db, w2, fi):
    return _factory(db, w2, "Far Depot", "FR")


def _item(db, ws, u1, name, name_normalized, is_active=True):
    return _add(db, Item(
        workspace_id=ws.id, name=name, name_normalized=name_normalized, unit="pcs", is_active=is_active, created_by=u1.id,
    ))


@pytest.fixture
def i1(db, w1, u1, f9):
    return _item(db, w1, u1, "Bolt M8", "bolt m8")


@pytest.fixture
def i2(db, w1, u1, i1):
    return _item(db, w1, u1, "Washer Ten", "washer ten")


@pytest.fixture
def i3(db, w1, u1, i2):
    return _item(db, w1, u1, "Cotter Pin", "cotter pin")


@pytest.fixture
def ix(db, w1, u1, i3):
    return _item(db, w1, u1, "Old Rivet", "old rivet", is_active=False)


@pytest.fixture
def ix2(db, w1, u1, ix):
    return _item(db, w1, u1, "Old Hinge", "old hinge", is_active=False)


@pytest.fixture
def i9(db, w2, u1, ix2):
    return _item(db, w2, u1, "Far Spring", "far spring")


@pytest.fixture
def i92(db, w2, u1, i9):
    return _item(db, w2, u1, "Far Clip", "far clip")


def _machine(db, ws, factory, u1, name, is_active=True, is_deleted=False):
    return _add(db, Machine(
        workspace_id=ws.id, factory_id=factory.id, name=name, is_running=False,
        is_active=is_active, is_deleted=is_deleted, created_by=u1.id,
    ))


@pytest.fixture
def m1(db, w1, f1, u1, i92):
    return _machine(db, w1, f1, u1, "Lathe")


@pytest.fixture
def m2(db, w1, f1, u1, m1):
    return _machine(db, w1, f1, u1, "Press")


@pytest.fixture
def mx(db, w1, f1, u1, m2):
    return _machine(db, w1, f1, u1, "Old Saw", is_active=False, is_deleted=True)


@pytest.fixture
def mf(db, w1, fd, u1, mx):
    return _machine(db, w1, fd, u1, "Kiln")


@pytest.fixture
def ma(db, w1, f1, u1, mf):
    return _machine(db, w1, f1, u1, "Mixer", is_active=False)


@pytest.fixture
def mn(db, w1, fi, u1, ma):
    return _machine(db, w1, fi, u1, "Nova")


@pytest.fixture
def m9(db, w2, f9, u1, mn):
    return _machine(db, w2, f9, u1, "Grinder")


@pytest.fixture
def wt1(db, w1, m9):
    return _add(db, WorkOrderType(workspace_id=w1.id, name="Repair"))


@pytest.fixture
def wt9(db, w2, wt1):
    return _add(db, WorkOrderType(workspace_id=w2.id, name="Far Repair"))


@pytest.fixture
def std(db, w1, wt9):
    return _add(db, Status(workspace_id=w1.id, name="Draft", comment="stage"))


@pytest.fixture
def stc(db, w1, std):
    return _add(db, Status(workspace_id=w1.id, name="Complete", comment="stage"))


@pytest.fixture
def st9(db, w2, stc):
    return _add(db, Status(workspace_id=w2.id, name="Draft", comment="stage"))


# Conventions "Standing rows": in every test, no Given line needed
@pytest.fixture(autouse=True)
def standing_rows(st9):
    pass


# --------------------------------------------------------------------------- #
# Conventions -> "Given rows" (each builder inserts ONE row and flushes, so ids
# rise in the order the Given lines are written; keyword arguments are the
# columns a card's "but" changes)
# --------------------------------------------------------------------------- #

# Convention "item"
@pytest.fixture
def mk_item(db, w1, u1):
    def _mk(name, name_normalized, **but):
        fields = {
            "name": name, "name_normalized": name_normalized, "unit": "pcs",
            "workspace_id": w1.id, "is_active": True, "created_by": u1.id,
        }
        fields.update(but)
        return _add(db, Item(**fields))
    return _mk


# Convention "stock of M, I"
@pytest.fixture
def mk_stock(db, w1):
    def _mk(machine, item, qty, **but):
        fields = {
            "workspace_id": w1.id, "machine_id": machine.id, "item_id": item.id,
            "qty": qty, "req_qty": None, "defective_qty": None,
        }
        fields.update(but)
        return _add(db, MachineItem(**fields))
    return _mk


# Convention "bulk(n)": n items P00000, ... and n rows stock of M1, qty 1, by add_all
@pytest.fixture
def bulk(db, w1, u1, m1):
    def _bulk(n):
        new_items = [
            Item(
                name=f"P{i:05d}", name_normalized=f"p{i:05d}", unit="pcs",
                workspace_id=w1.id, is_active=True, created_by=u1.id,
            )
            for i in range(n)
        ]
        db.add_all(new_items)
        db.flush()
        db.add_all([
            MachineItem(workspace_id=w1.id, machine_id=m1.id, item_id=item.id, qty=1, req_qty=None, defective_qty=None)
            for item in new_items
        ])
        db.flush()
    return _bulk


# Convention "entry of M, I"
@pytest.fixture
def mk_entry(db, w1, u1):
    def _mk(machine, item, performed_at, avg_price_after, **but):
        fields = {
            "workspace_id": w1.id, "machine_id": machine.id, "item_id": item.id,
            "transaction_type": "manual_add", "quantity": 10,
            "unit_cost": Decimal("0.00"), "total_cost": Decimal("0.00"),
            "qty_before": 0, "qty_after": 10,
            "value_before": None, "value_after": None, "avg_price_before": None,
            "source_type": "manual", "performed_by": u1.id,
            "performed_at": performed_at, "avg_price_after": avg_price_after,
        }
        fields.update(but)
        return _add(db, MachineItemLedger(**fields))
    return _mk


# Convention "activity row of M"
@pytest.fixture
def mk_activity(db, w1, u1):
    def _mk(machine):
        return _add(db, MachineActivityEvent(
            workspace_id=w1.id, machine_id=machine.id, event_type="item_added", description="seed", performed_by=u1.id,
        ))
    return _mk


# Convention "work order of M"
@pytest.fixture
def mk_order(db, w1, wt1, f1):
    def _mk(machine, given_name, status, **but):
        fields = {
            "workspace_id": w1.id, "work_order_number": f"WO-{given_name}", "work_order_type_id": wt1.id,
            "title": "Service", "factory_id": f1.id, "machine_id": machine.id, "is_deleted": False,
            "status": status,
        }
        fields.update(but)
        return _add(db, WorkOrder(**fields))
    return _mk


# Convention "source line of O"
@pytest.fixture
def mk_source_line(db, w1, i1, m1):
    def _mk(order, **but):
        fields = {
            "workspace_id": w1.id, "work_order_id": order.id, "item_id": i1.id, "quantity": 2,
            "uses_inventory": True, "consumed_at": None, "source_location_type": "machine",
            "source_location_id": m1.id, "replaced_item_id": None, "is_deleted": False,
        }
        fields.update(but)
        return _add(db, WorkOrderItem(**fields))
    return _mk


# Convention "replace line of O"
@pytest.fixture
def mk_replace_line(db, w1, i1, i2):
    def _mk(order, **but):
        fields = {
            "workspace_id": w1.id, "work_order_id": order.id, "item_id": i2.id, "quantity": 1,
            "action_type": "REPLACE", "replaced_item_id": i1.id, "uses_inventory": True,
            "consumed_at": None, "is_deleted": False,
        }
        fields.update(but)
        return _add(db, WorkOrderItem(**fields))
    return _mk


# Convention "transfer out of M1"
@pytest.fixture
def mk_transfer(db, w1, u1, m1, f1, std):
    def _mk(given_name, **but):
        fields = {
            "workspace_id": w1.id, "transfer_number": f"TR-{given_name}",
            "source_location_type": "machine", "source_location_id": m1.id,
            "destination_location_type": "storage", "destination_location_id": f1.id,
            "current_status_id": std.id, "created_by": u1.id, "completed_at": None,
        }
        fields.update(but)
        return _add(db, TransferOrder(**fields))
    return _mk


# Convention "TO line of T"
@pytest.fixture
def mk_to_line(db, w1, i1):
    def _mk(transfer, **but):
        fields = {
            "workspace_id": w1.id, "transfer_order_id": transfer.id, "line_number": 1,
            "item_id": i1.id, "quantity": 3,
        }
        fields.update(but)
        return _add(db, TransferOrderItem(**fields))
    return _mk


# Convention "delivered PO to M1"
@pytest.fixture
def mk_po(db, w1, u1, m1, stc):
    def _mk(given_name, **but):
        fields = {
            "workspace_id": w1.id, "po_number": f"PO-{given_name}", "destination_type": "machine",
            "destination_id": m1.id, "current_status_id": stc.id, "created_by": u1.id, "voided": False,
        }
        fields.update(but)
        return _add(db, PurchaseOrder(**fields))
    return _mk


# Convention "PO line of P"
@pytest.fixture
def mk_po_line(db, w1, i1):
    def _mk(purchase_order, **but):
        fields = {
            "workspace_id": w1.id, "purchase_order_id": purchase_order.id, "line_number": 1,
            "item_id": i1.id, "quantity_ordered": 5,
        }
        fields.update(but)
        return _add(db, PurchaseOrderItem(**fields))
    return _mk


# Convention "return of P"
@pytest.fixture
def mk_return(db, w1, u1):
    def _mk(purchase_order, given_name, **but):
        fields = {
            "workspace_id": w1.id, "purchase_order_id": purchase_order.id,
            "return_number": f"PR-{given_name}", "created_by": u1.id, "status": "pending",
        }
        fields.update(but)
        return _add(db, PurchaseOrderReturn(**fields))
    return _mk


# Convention "return line of R, L"
@pytest.fixture
def mk_return_line(db, w1, i1):
    def _mk(purchase_return, po_line, **but):
        fields = {
            "workspace_id": w1.id, "return_id": purchase_return.id, "po_item_id": po_line.id,
            "item_id": i1.id, "quantity_returned": 2,
        }
        fields.update(but)
        return _add(db, PurchaseOrderReturnItem(**fields))
    return _mk


# --------------------------------------------------------------------------- #
# Conventions -> "Named checks"
# --------------------------------------------------------------------------- #

_TABLES = {
    "machine_items": MachineItem.__table__,
    "machine_item_ledger": MachineItemLedger.__table__,
    "machine_activity_events": MachineActivityEvent.__table__,
}


def _id_of(row):
    """Primary key of a row, without touching its (possibly expired) attributes."""
    return sa_inspect(row).identity[0]


# Convention "re-read X"
def reread(db, row):
    model, row_id = type(row), _id_of(row)
    db.expire_all()
    return db.execute(select(model).where(model.id == row_id)).scalar_one_or_none()


def _columns_of(db, row):
    table = type(row).__table__
    found = db.execute(select(table).where(table.c.id == _id_of(row))).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "unchanged(X)": snapshot after db.refresh(X), before the call
def snap_before(db, row):
    db.refresh(row)
    return _columns_of(db, row)


# Convention "unchanged(X)": after re-read, every column of X
def snap(db, row):
    db.expire_all()
    return _columns_of(db, row)


# Convention "count:" lines: rows of the named table in all workspaces, with the filter stated
def count_rows(db, table_name, **filters):
    table = _TABLES[table_name]
    query = select(func.count()).select_from(table)
    for column, value in filters.items():
        query = query.where(table.c[column] == value)
    return db.execute(query).scalar_one()


# Convention "nothing written"
def written(db):
    return {name: count_rows(db, name) for name in _TABLES}


# Convention "entries_of(M, I)": a fresh SELECT, any workspace, ordered by id
def entries_of(db, machine, item):
    machine_id, item_id = _id_of(machine), _id_of(item)
    db.expire_all()
    query = select(MachineItemLedger).where(
        MachineItemLedger.machine_id == machine_id, MachineItemLedger.item_id == item_id,
    )
    return list(db.execute(query.order_by(MachineItemLedger.id)).scalars())


# Convention "events_of(M)": a fresh SELECT, ordered by id; event_type is the card's "with" filter
def events_of(db, machine, event_type=None):
    machine_id = _id_of(machine)
    db.expire_all()
    query = select(MachineActivityEvent).where(MachineActivityEvent.machine_id == machine_id)
    if event_type is not None:
        query = query.where(MachineActivityEvent.event_type == event_type)
    return list(db.execute(query.order_by(MachineActivityEvent.id)).scalars())


# Convention "ids(x)"
def ids(rows):
    return sorted(r.id for r in rows)


# Convention "names(x)"
def names(rows):
    return [r.item_name for r in rows]


# Convention "Rolled back": a spy wrapping db.commit, still callable, records calls
def commit_spy(db, monkeypatch):
    spy = Mock(wraps=db.commit)
    monkeypatch.setattr(db, "commit", spy)
    return spy


# Convention "sql_log": a before_cursor_execute listener on db.connection(); removed after the call
@contextmanager
def record_sql(db):
    connection = db.connection()
    sql_log = []

    def _record(conn, cursor, statement, parameters, context, executemany):
        sql_log.append(statement)

    event.listen(connection, "before_cursor_execute", _record)
    try:
        yield sql_log
    finally:
        event.remove(connection, "before_cursor_execute", _record)


# --------------------------------------------------------------------------- #
# The cases
# --------------------------------------------------------------------------- #

# [claude] MIM-IN-01
def test_mim_in_01__an_item_of_the_workspace_gives_its_name(db, w1, i1):
    """MIM-IN-01 — an item of the workspace gives its name.
    Rules: `_item_name` R1"""
    result = M._item_name(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == "Bolt M8"


# [claude] MIM-IN-02
def test_mim_in_02__a_removed_item_of_the_workspace_gives_its_name_like_any_other(db, w1, ix):
    """MIM-IN-02 — a removed item of the workspace gives its name like any other.
    Rules: `_item_name` R2"""
    result = M._item_name(db, item_id=ix.id, workspace_id=w1.id)

    # Then 1
    assert result == "Old Rivet"


# [claude] MIM-G-01
def test_mim_g_01__a_row_of_the_workspace_is_returned_with_its_item_loaded(db, w1, i1, m1, mk_stock):
    """MIM-G-01 — a row of the workspace is returned with its item loaded.
    Rules: `get_machine_item` R1, Returns"""
    mi = mk_stock(m1, i1, qty=5, req_qty=7, defective_qty=1)
    result = M.get_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, MachineItem)
    # Then 2
    assert result.id == mi.id
    # Then 3
    assert result.machine_id == m1.id
    assert result.item_id == i1.id
    assert result.workspace_id == w1.id
    # Then 4
    assert result.qty == 5
    assert result.req_qty == 7
    assert result.defective_qty == 1
    # Then 5
    assert result.item_name == "Bolt M8"
    assert result.item_unit == "pcs"


# [claude] MIM-G-02
def test_mim_g_02__positional_arguments_work_as_the_service_calls_it(db, w1, i1, m1, mk_stock):
    """MIM-G-02 — positional arguments work, as the service calls it.
    Rules: `get_machine_item` R1"""
    mi = mk_stock(m1, i1, qty=5)
    result = M.get_machine_item(db, mi.id, w1.id)

    # Then 1
    assert result.id == mi.id


# [claude] MIM-G-03
def test_mim_g_03__a_row_asked_for_from_another_workspace_gets_the_same_404(db, w2, i1, m1, mk_stock):
    """MIM-G-03 — a row asked for from another workspace gets the same 404.
    Rules: `get_machine_item` R2, Errors row 1"""
    mi = mk_stock(m1, i1, qty=5)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_machine_item(db, machine_item_id=mi.id, workspace_id=w2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine item not found"
    # Then 4
    assert snap(db, mi) == before_mi
    # Then 5
    assert written(db) == before


# [claude] MIM-G-04
def test_mim_g_04__an_unknown_id_gets_the_same_404(db, w1, i1, m1, mk_stock):
    """MIM-G-04 — an unknown id gets the same 404.
    Rules: `get_machine_item` R2, Errors row 1"""
    mi = mk_stock(m1, i1, qty=5)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_machine_item(db, machine_item_id=MISSING, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine item not found"
    # Then 4
    assert snap(db, mi) == before_mi
    # Then 5
    assert written(db) == before


# [claude] MIM-G-05
def test_mim_g_05__id_0_gets_the_same_404(db, w1, i1, m1, mk_stock):
    """MIM-G-05 — id 0 gets the same 404.
    Rules: `get_machine_item` R2, Errors row 1"""
    mi = mk_stock(m1, i1, qty=5)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_machine_item(db, machine_item_id=0, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine item not found"
    # Then 4
    assert snap(db, mi) == before_mi
    # Then 5
    assert written(db) == before


# [claude] MIM-G-06
@pytest.mark.xfail(strict=True, reason="BUG-1077: A hidden machine stock row still opens by id")
def test_mim_g_06__a_row_of_a_soft_deleted_machine_is_hidden_404(db, w1, i1, mx, mk_stock):
    """MIM-G-06 — a row of a soft-deleted machine is hidden: 404.
    Rules: `get_machine_item` R3 [BUG-1077], Errors row 1"""
    mi = mk_stock(mx, i1, qty=5)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine item not found"
    # Then 4
    assert snap(db, mi) == before_mi
    # Then 5
    assert written(db) == before


# [claude] MIM-G-07
@pytest.mark.xfail(strict=True, reason="BUG-1077: A hidden machine stock row still opens by id")
def test_mim_g_07__include_deleted_true_returns_a_row_of_a_soft_deleted_machine(db, w1, i1, mx, mk_stock):
    """MIM-G-07 — include_deleted=True returns a row of a soft-deleted machine.
    Rules: `get_machine_item` R3a [BUG-1077]"""
    mi = mk_stock(mx, i1, qty=5)
    before_mi = snap_before(db, mi)
    before = written(db)
    result = M.get_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert result.id == mi.id
    # Then 2
    assert result.qty == 5
    # Then 3
    assert snap(db, mi) == before_mi
    # Then 4
    assert written(db) == before


# [claude] MIM-G-08
@pytest.mark.xfail(strict=True, reason="BUG-1077: A hidden machine stock row still opens by id")
def test_mim_g_08__a_row_of_a_live_machine_in_a_soft_deleted_factory_is_hidden_404(db, w1, i1, mf, mk_stock):
    """MIM-G-08 — a row of a live machine in a soft-deleted factory is hidden: 404.
    Rules: `get_machine_item` R3 [BUG-1077], Errors row 1"""
    mi = mk_stock(mf, i1, qty=5)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine item not found"
    # Then 4
    assert snap(db, mi) == before_mi
    # Then 5
    assert written(db) == before


# [claude] MIM-G-09
@pytest.mark.xfail(strict=True, reason="BUG-1077: A hidden machine stock row still opens by id")
def test_mim_g_09__include_deleted_true_returns_a_row_of_a_live_machine_in_a_soft_deleted_factory(db, w1, i1, mf, mk_stock):
    """MIM-G-09 — include_deleted=True returns a row of a live machine in a soft-deleted factory.
    Rules: `get_machine_item` R3a [BUG-1077]"""
    mi = mk_stock(mf, i1, qty=5)
    before_mi = snap_before(db, mi)
    before = written(db)
    result = M.get_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert result.id == mi.id
    # Then 2
    assert result.qty == 5
    # Then 3
    assert snap(db, mi) == before_mi
    # Then 4
    assert written(db) == before


# [claude] MIM-G-10
@pytest.mark.xfail(strict=True, reason="BUG-1077: A hidden machine stock row still opens by id")
def test_mim_g_10__a_row_of_a_removed_item_is_hidden_404(db, w1, ix, m1, mk_stock):
    """MIM-G-10 — a row of a removed item is hidden: 404.
    Rules: `get_machine_item` R3 [BUG-1077], Errors row 1"""
    mi = mk_stock(m1, ix, qty=5)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine item not found"
    # Then 4
    assert snap(db, mi) == before_mi
    # Then 5
    assert written(db) == before


# [claude] MIM-G-11
@pytest.mark.xfail(strict=True, reason="BUG-1077: A hidden machine stock row still opens by id")
def test_mim_g_11__include_deleted_true_returns_a_row_of_a_removed_item(db, w1, ix, m1, mk_stock):
    """MIM-G-11 — include_deleted=True returns a row of a removed item.
    Rules: `get_machine_item` R3a [BUG-1077]"""
    mi = mk_stock(m1, ix, qty=5)
    before_mi = snap_before(db, mi)
    before = written(db)
    result = M.get_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert result.id == mi.id
    # Then 2
    assert result.qty == 5
    # Then 3
    assert snap(db, mi) == before_mi
    # Then 4
    assert written(db) == before


# [claude] MIM-G-12
@pytest.mark.xfail(strict=True, reason="BUG-1077: A hidden machine stock row still opens by id")
def test_mim_g_12__include_deleted_true_returns_a_row_with_live_parents_too(db, w1, i1, m1, mk_stock):
    """MIM-G-12 — include_deleted=True returns a row with live parents too.
    Rules: `get_machine_item` R3a [BUG-1077]"""
    mi = mk_stock(m1, i1, qty=5)
    result = M.get_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert result.id == mi.id


# [claude] MIM-G-13
@pytest.mark.xfail(strict=True, reason="BUG-1077: A hidden machine stock row still opens by id")
def test_mim_g_13__include_deleted_true_does_not_open_a_row_of_another_workspace(db, w2, i1, mx, mk_stock):
    """MIM-G-13 — include_deleted=True does not open a row of another workspace.
    Rules: `get_machine_item` R2, R3a [BUG-1077], Errors row 1"""
    mi = mk_stock(mx, i1, qty=5)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_machine_item(db, machine_item_id=mi.id, workspace_id=w2.id, include_deleted=True)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine item not found"
    # Then 4
    assert written(db) == before


# [claude] MIM-G-14
@pytest.mark.xfail(strict=True, reason="BUG-1077: A hidden machine stock row still opens by id")
def test_mim_g_14__include_deleted_true_on_an_unknown_id_is_still_404(db, w1):
    """MIM-G-14 — include_deleted=True on an unknown id is still 404.
    Rules: `get_machine_item` R2, R3a [BUG-1077], Errors row 1"""
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_machine_item(db, machine_item_id=MISSING, workspace_id=w1.id, include_deleted=True)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine item not found"
    # Then 4
    assert written(db) == before


# [claude] MIM-G-15
def test_mim_g_15__an_inactive_but_live_machine_hides_nothing(db, w1, i1, ma, mk_stock):
    """MIM-G-15 — an inactive-but-live machine hides nothing.
    Rules: `get_machine_item` R4"""
    mi = mk_stock(ma, i1, qty=5)
    result = M.get_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id)

    # Then 1
    assert result.id == mi.id
    # Then 2
    assert result.item_name == "Bolt M8"


# [claude] MIM-G-16
def test_mim_g_16__a_machine_in_an_inactive_but_live_factory_hides_nothing(db, w1, i1, mn, mk_stock):
    """MIM-G-16 — a machine in an inactive-but-live factory hides nothing.
    Rules: `get_machine_item` R4"""
    mi = mk_stock(mn, i1, qty=5)
    result = M.get_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id)

    # Then 1
    assert result.id == mi.id
    # Then 2
    assert result.item_name == "Bolt M8"


# [claude] MIM-G-17
def test_mim_g_17__the_read_writes_nothing(db, w1, i1, m1, mk_stock):
    """MIM-G-17 — the read writes nothing.
    Rules: `get_machine_item` R5"""
    mi = mk_stock(m1, i1, qty=5, req_qty=7)
    before_mi = snap_before(db, mi)
    before = written(db)
    result = M.get_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id)

    # Then 1
    assert result.id == mi.id
    # Then 2
    assert mi not in db.dirty
    # Then 3
    assert snap(db, mi) == before_mi
    # Then 4
    assert written(db) == before


# [claude] MIM-G-18
@pytest.mark.xfail(strict=True, reason="BUG-1086: A stored stock row with another workspace's item shows that item's name and id")
def test_mim_g_18__a_stored_row_with_another_workspace_s_item_is_not_found(db, w1, i9, m1, mk_stock):
    """MIM-G-18 — a stored row with another workspace's item is not found.
    Rules: `get_machine_item` R6 [BUG-1086], Errors row 1"""
    mi = mk_stock(m1, i9, qty=5)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine item not found"
    # Then 4
    assert snap(db, mi) == before_mi
    # Then 5
    assert written(db) == before


# [claude] MIM-G-19
@pytest.mark.xfail(strict=True, reason="BUG-1086: A stored stock row with another workspace's item shows that item's name and id")
def test_mim_g_19__a_stored_row_with_another_workspace_s_item_is_not_found_with_include_deleted_true_either(db, w1, i9, m1, mk_stock):
    """MIM-G-19 — a stored row with another workspace's item is not found with include_deleted=True either.
    Rules: `get_machine_item` R6 [BUG-1086], R3a [BUG-1077], Errors row 1"""
    mi = mk_stock(m1, i9, qty=5)
    before_mi = snap_before(db, mi)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, include_deleted=True)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine item not found"
    # Then 4
    assert snap(db, mi) == before_mi


# [claude] MIM-G-20
def test_mim_g_20__a_stored_row_with_another_workspace_s_item_is_not_found_from_the_item_s_workspace(db, w2, i9, m1, mk_stock):
    """MIM-G-20 — a stored row with another workspace's item is not found from the item's workspace.
    Rules: `get_machine_item` R2, R6, Errors row 1"""
    mi = mk_stock(m1, i9, qty=5)
    before_mi = snap_before(db, mi)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_machine_item(db, machine_item_id=mi.id, workspace_id=w2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine item not found"
    # Then 4
    assert snap(db, mi) == before_mi


# [claude] MIM-L-01
def test_mim_l_01__with_a_machine_id_only_that_machine_s_rows_each_with_its_item_loaded(db, w1, i1, i2, m1, m2, mk_stock):
    """MIM-L-01 — with a machine_id: only that machine's rows, each with its item loaded.
    Rules: `list_machine_items` R1, Returns"""
    a = mk_stock(m1, i1, qty=5)
    b = mk_stock(m1, i2, qty=2)
    mk_stock(m2, i1, qty=9)
    result = M.list_machine_items(db, workspace_id=w1.id, machine_id=m1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [a.id, b.id]
    # Then 3
    assert sorted(r.item_name for r in result) == ["Bolt M8", "Washer Ten"]
    # Then 4
    assert sorted(r.item_unit for r in result) == ["pcs", "pcs"]


# [claude] MIM-L-02
def test_mim_l_02__with_a_machine_id_rows_come_in_item_name_order_case_insensitive(db, w1, m1, mk_item, mk_stock):
    """MIM-L-02 — with a machine_id: rows come in item-name order, case-insensitive.
    Rules: `list_machine_items` R1 [BUG-976]"""
    iz = mk_item("Zulu", "zulu")
    ia = mk_item("apple", "apple")
    ib = mk_item("Banana", "banana")
    mk_stock(m1, iz, qty=1)
    mk_stock(m1, ia, qty=1)
    mk_stock(m1, ib, qty=1)
    result = M.list_machine_items(db, workspace_id=w1.id, machine_id=m1.id)

    # Then 1
    assert names(result) == ["apple", "Banana", "Zulu"]


# [claude] MIM-L-03
def test_mim_l_03__with_a_machine_id_a_soft_deleted_machine_gives_an_empty_list(db, w1, i1, m1, mx, mk_stock):
    """MIM-L-03 — with a machine_id: a soft-deleted machine gives an empty list.
    Rules: `list_machine_items` R1 [BUG-979]"""
    a = mk_stock(mx, i1, qty=5)
    mk_stock(m1, i1, qty=5)
    before_a = snap_before(db, a)
    result = M.list_machine_items(db, workspace_id=w1.id, machine_id=mx.id)

    # Then 1
    assert result == []
    # Then 2
    assert snap(db, a) == before_a


# [claude] MIM-L-04
def test_mim_l_04__with_a_machine_id_a_machine_in_a_soft_deleted_factory_gives_an_empty_list(db, w1, i1, m1, mf, mk_stock):
    """MIM-L-04 — with a machine_id: a machine in a soft-deleted factory gives an empty list.
    Rules: `list_machine_items` R1 [BUG-979]"""
    a = mk_stock(mf, i1, qty=5)
    mk_stock(m1, i1, qty=5)
    before_a = snap_before(db, a)
    result = M.list_machine_items(db, workspace_id=w1.id, machine_id=mf.id)

    # Then 1
    assert result == []
    # Then 2
    assert snap(db, a) == before_a


# [claude] MIM-L-05
def test_mim_l_05__with_a_machine_id_a_removed_item_s_row_is_left_out_the_others_stay(db, w1, i1, ix, m1, mk_stock):
    """MIM-L-05 — with a machine_id: a removed item's row is left out, the others stay.
    Rules: `list_machine_items` R1 [BUG-980]"""
    a = mk_stock(m1, ix, qty=5)
    b = mk_stock(m1, i1, qty=5)
    before_a = snap_before(db, a)
    result = M.list_machine_items(db, workspace_id=w1.id, machine_id=m1.id)

    # Then 1
    assert ids(result) == [b.id]
    # Then 2
    assert snap(db, a) == before_a


# [claude] MIM-L-06
def test_mim_l_06__a_machine_id_of_another_workspace_returns_an_empty_list(db, w1, w2, i1, m1, m9, mk_stock):
    """MIM-L-06 — a machine_id of another workspace returns an empty list.
    Rules: `list_machine_items` R2"""
    mk_stock(m1, i1, qty=5)
    mk_stock(m9, i1, qty=5, workspace_id=w2.id)
    result = M.list_machine_items(db, workspace_id=w1.id, machine_id=m9.id)

    # Then 1
    assert result == []


# [claude] MIM-L-07
def test_mim_l_07__a_machine_id_unknown_returns_an_empty_list(db, w1, i1, m1, mk_stock):
    """MIM-L-07 — a machine_id unknown returns an empty list.
    Rules: `list_machine_items` R2"""
    mk_stock(m1, i1, qty=5)
    result = M.list_machine_items(db, workspace_id=w1.id, machine_id=MISSING)

    # Then 1
    assert result == []


# [claude] MIM-L-08
def test_mim_l_08__a_machine_id_negative_returns_an_empty_list(db, w1, i1, m1, mk_stock):
    """MIM-L-08 — a machine_id negative returns an empty list.
    Rules: `list_machine_items` R2"""
    mk_stock(m1, i1, qty=5)
    result = M.list_machine_items(db, workspace_id=w1.id, machine_id=-1)

    # Then 1
    assert result == []


# [claude] MIM-L-09
def test_mim_l_09__a_machine_id_of_a_machine_with_no_rows_returns_an_empty_list(db, w1, i1, m1, m2, mk_stock):
    """MIM-L-09 — a machine_id of a machine with no rows returns an empty list.
    Rules: `list_machine_items` R2"""
    mk_stock(m1, i1, qty=5)
    result = M.list_machine_items(db, workspace_id=w1.id, machine_id=m2.id)

    # Then 1
    assert result == []


# [claude] MIM-L-10
@pytest.mark.xfail(strict=True, reason="BUG-1074: machine_id=0 lists the whole workspace's machine stock")
def test_mim_l_10__machine_id_0_filters_like_any_integer(db, w1, i1, m1, mk_stock):
    """MIM-L-10 — machine_id 0 filters like any integer.
    Rules: `list_machine_items` R3 [BUG-1074]"""
    mk_stock(m1, i1, qty=5)
    result = M.list_machine_items(db, workspace_id=w1.id, machine_id=0)

    # Then 1
    assert result == []


# [claude] MIM-L-11
def test_mim_l_11__machine_id_none_lists_the_whole_workspace(db, w1, i1, m1, m2, mk_stock):
    """MIM-L-11 — machine_id None lists the whole workspace.
    Rules: `list_machine_items` R3, R4"""
    a = mk_stock(m1, i1, qty=5)
    b = mk_stock(m2, i1, qty=2)
    result = M.list_machine_items(db, workspace_id=w1.id, machine_id=None)

    # Then 1
    assert ids(result) == [a.id, b.id]


# [claude] MIM-L-12
def test_mim_l_12__without_a_machine_id_only_rows_of_that_workspace(db, w1, w2, i1, m1, m9, mk_stock):
    """MIM-L-12 — without a machine_id: only rows of that workspace.
    Rules: `list_machine_items` R4"""
    a = mk_stock(m1, i1, qty=5)
    mk_stock(m9, i1, qty=5, workspace_id=w2.id)
    result = M.list_machine_items(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MIM-L-13
def test_mim_l_13__without_a_machine_id_an_unknown_workspace_gives_an_empty_list(db, i1, m1, mk_stock):
    """MIM-L-13 — without a machine_id: an unknown workspace gives an empty list.
    Rules: `list_machine_items` R4"""
    mk_stock(m1, i1, qty=5)
    result = M.list_machine_items(db, workspace_id=MISSING)

    # Then 1
    assert result == []


# [claude] MIM-L-14
def test_mim_l_14__without_a_machine_id_an_empty_workspace_gives_an_empty_list(db, w2, i1, m1, mk_stock):
    """MIM-L-14 — without a machine_id: an empty workspace gives an empty list.
    Rules: `list_machine_items` R4"""
    mk_stock(m1, i1, qty=5)
    result = M.list_machine_items(db, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] MIM-L-15
def test_mim_l_15__with_a_machine_id_limit_2_of_3_rows_gives_2(db, w1, i1, i2, i3, m1, mk_stock):
    """MIM-L-15 — with a machine_id: limit 2 of 3 rows gives 2.
    Rules: `list_machine_items` R5"""
    mk_stock(m1, i1, qty=1)
    mk_stock(m1, i2, qty=1)
    mk_stock(m1, i3, qty=1)
    result = M.list_machine_items(db, workspace_id=w1.id, machine_id=m1.id, limit=2)

    # Then 1
    assert len(result) == 2


# [claude] MIM-L-16
def test_mim_l_16__with_a_machine_id_skip_1_of_3_rows_gives_2(db, w1, i1, i2, i3, m1, mk_stock):
    """MIM-L-16 — with a machine_id: skip 1 of 3 rows gives 2.
    Rules: `list_machine_items` R5"""
    mk_stock(m1, i1, qty=1)
    mk_stock(m1, i2, qty=1)
    mk_stock(m1, i3, qty=1)
    result = M.list_machine_items(db, workspace_id=w1.id, machine_id=m1.id, skip=1)

    # Then 1
    assert len(result) == 2


# [claude] MIM-L-17
def test_mim_l_17__with_a_machine_id_by_default_101_rows_give_exactly_100(db, w1, m1, bulk):
    """MIM-L-17 — with a machine_id: by default 101 rows give exactly 100.
    Rules: `list_machine_items` R5"""
    bulk(101)
    result = M.list_machine_items(db, workspace_id=w1.id, machine_id=m1.id)

    # Then 1
    assert len(result) == 100


# [claude] MIM-L-18
def test_mim_l_18__with_a_machine_id_by_default_100_rows_give_all_100(db, w1, m1, bulk):
    """MIM-L-18 — with a machine_id: by default 100 rows give all 100.
    Rules: `list_machine_items` R5"""
    bulk(100)
    result = M.list_machine_items(db, workspace_id=w1.id, machine_id=m1.id)

    # Then 1
    assert len(result) == 100


# [claude] MIM-L-19
def test_mim_l_19__with_a_machine_id_limit_101_over_101_rows_gives_101(db, w1, m1, bulk):
    """MIM-L-19 — with a machine_id: limit 101 over 101 rows gives 101.
    Rules: `list_machine_items` R5"""
    bulk(101)
    result = M.list_machine_items(db, workspace_id=w1.id, machine_id=m1.id, limit=101)

    # Then 1
    assert len(result) == 101


# [claude] MIM-L-20
def test_mim_l_20__with_a_machine_id_limit_0_gives_an_empty_list(db, w1, i1, m1, mk_stock):
    """MIM-L-20 — with a machine_id: limit 0 gives an empty list.
    Rules: `list_machine_items` R5"""
    mk_stock(m1, i1, qty=1)
    result = M.list_machine_items(db, workspace_id=w1.id, machine_id=m1.id, limit=0)

    # Then 1
    assert result == []


# [claude] MIM-L-21
def test_mim_l_21__with_a_machine_id_skip_exactly_at_the_end_gives_an_empty_list(db, w1, i1, i2, m1, mk_stock):
    """MIM-L-21 — with a machine_id: skip exactly at the end gives an empty list.
    Rules: `list_machine_items` R5"""
    mk_stock(m1, i1, qty=1)
    mk_stock(m1, i2, qty=1)
    result = M.list_machine_items(db, workspace_id=w1.id, machine_id=m1.id, skip=2)

    # Then 1
    assert result == []


# [claude] MIM-L-22
def test_mim_l_22__with_a_machine_id_skip_one_short_of_the_end_gives_the_last_row(db, w1, i1, i2, m1, mk_stock):
    """MIM-L-22 — with a machine_id: skip one short of the end gives the last row.
    Rules: `list_machine_items` R5"""
    mk_stock(m1, i1, qty=1)
    mk_stock(m1, i2, qty=1)
    result = M.list_machine_items(db, workspace_id=w1.id, machine_id=m1.id, skip=1)

    # Then 1
    assert len(result) == 1


# [claude] MIM-L-23
def test_mim_l_23__with_a_machine_id_skip_past_the_end_gives_an_empty_list(db, w1, i1, i2, m1, mk_stock):
    """MIM-L-23 — with a machine_id: skip past the end gives an empty list.
    Rules: `list_machine_items` R5"""
    mk_stock(m1, i1, qty=1)
    mk_stock(m1, i2, qty=1)
    result = M.list_machine_items(db, workspace_id=w1.id, machine_id=m1.id, skip=3)

    # Then 1
    assert result == []


# [claude] MIM-L-24
def test_mim_l_24__with_a_machine_id_consecutive_windows_partition_the_rows(db, w1, i1, i2, i3, m1, mk_stock):
    """MIM-L-24 — with a machine_id: consecutive windows partition the rows.
    Rules: `list_machine_items` R5 [BUG-976]"""
    a = mk_stock(m1, i1, qty=1)
    b = mk_stock(m1, i2, qty=1)
    c = mk_stock(m1, i3, qty=1)
    win1 = M.list_machine_items(db, workspace_id=w1.id, machine_id=m1.id, skip=0, limit=2)
    a.qty = 7
    db.flush()
    win2 = M.list_machine_items(db, workspace_id=w1.id, machine_id=m1.id, skip=2, limit=2)

    # Then 1
    assert sorted([r.id for r in win1] + [r.id for r in win2]) == [a.id, b.id, c.id]


# [claude] MIM-L-25
def test_mim_l_25__with_a_machine_id_a_negative_limit_is_rejected_by_the_database(db, w1, i1, m1, mk_stock):
    """MIM-L-25 — with a machine_id: a negative limit is rejected by the database.
    Rules: `list_machine_items` R6, Errors row 1"""
    mk_stock(m1, i1, qty=1)
    before = written(db)
    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            M.list_machine_items(db, workspace_id=w1.id, machine_id=m1.id, limit=-1)
    # Then 2
    assert exc.value.orig.pgcode == "2201W"
    # Then 3
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 4
    assert written(db) == before


# [claude] MIM-L-26
def test_mim_l_26__with_a_machine_id_a_negative_skip_is_rejected_by_the_database(db, w1, i1, m1, mk_stock):
    """MIM-L-26 — with a machine_id: a negative skip is rejected by the database.
    Rules: `list_machine_items` R6, Errors row 2"""
    mk_stock(m1, i1, qty=1)
    before = written(db)
    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            M.list_machine_items(db, workspace_id=w1.id, machine_id=m1.id, skip=-1)
    # Then 2
    assert exc.value.orig.pgcode == "2201X"
    # Then 3
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 4
    assert written(db) == before


# [claude] MIM-L-27
def test_mim_l_27__without_a_machine_id_limit_2_of_3_rows_gives_2(db, w1, i1, i2, i3, m1, mk_stock):
    """MIM-L-27 — without a machine_id: limit 2 of 3 rows gives 2.
    Rules: `list_machine_items` R5"""
    mk_stock(m1, i1, qty=1)
    mk_stock(m1, i2, qty=1)
    mk_stock(m1, i3, qty=1)
    result = M.list_machine_items(db, workspace_id=w1.id, limit=2)

    # Then 1
    assert len(result) == 2


# [claude] MIM-L-28
def test_mim_l_28__without_a_machine_id_skip_1_of_3_rows_gives_2(db, w1, i1, i2, i3, m1, mk_stock):
    """MIM-L-28 — without a machine_id: skip 1 of 3 rows gives 2.
    Rules: `list_machine_items` R5"""
    mk_stock(m1, i1, qty=1)
    mk_stock(m1, i2, qty=1)
    mk_stock(m1, i3, qty=1)
    result = M.list_machine_items(db, workspace_id=w1.id, skip=1)

    # Then 1
    assert len(result) == 2


# [claude] MIM-L-29
def test_mim_l_29__without_a_machine_id_by_default_101_rows_give_exactly_100(db, w1, bulk):
    """MIM-L-29 — without a machine_id: by default 101 rows give exactly 100.
    Rules: `list_machine_items` R5"""
    bulk(101)
    result = M.list_machine_items(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100


# [claude] MIM-L-30
def test_mim_l_30__without_a_machine_id_by_default_100_rows_give_all_100(db, w1, bulk):
    """MIM-L-30 — without a machine_id: by default 100 rows give all 100.
    Rules: `list_machine_items` R5"""
    bulk(100)
    result = M.list_machine_items(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100


# [claude] MIM-L-31
def test_mim_l_31__without_a_machine_id_limit_101_over_101_rows_gives_101(db, w1, bulk):
    """MIM-L-31 — without a machine_id: limit 101 over 101 rows gives 101.
    Rules: `list_machine_items` R5"""
    bulk(101)
    result = M.list_machine_items(db, workspace_id=w1.id, limit=101)

    # Then 1
    assert len(result) == 101


# [claude] MIM-L-32
def test_mim_l_32__without_a_machine_id_limit_0_gives_an_empty_list(db, w1, i1, m1, mk_stock):
    """MIM-L-32 — without a machine_id: limit 0 gives an empty list.
    Rules: `list_machine_items` R5"""
    mk_stock(m1, i1, qty=1)
    result = M.list_machine_items(db, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [claude] MIM-L-33
def test_mim_l_33__without_a_machine_id_skip_exactly_at_the_end_gives_an_empty_list(db, w1, i1, i2, m1, mk_stock):
    """MIM-L-33 — without a machine_id: skip exactly at the end gives an empty list.
    Rules: `list_machine_items` R5"""
    mk_stock(m1, i1, qty=1)
    mk_stock(m1, i2, qty=1)
    result = M.list_machine_items(db, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [claude] MIM-L-34
def test_mim_l_34__without_a_machine_id_skip_one_short_of_the_end_gives_the_last_row(db, w1, i1, i2, m1, mk_stock):
    """MIM-L-34 — without a machine_id: skip one short of the end gives the last row.
    Rules: `list_machine_items` R5"""
    mk_stock(m1, i1, qty=1)
    mk_stock(m1, i2, qty=1)
    result = M.list_machine_items(db, workspace_id=w1.id, skip=1)

    # Then 1
    assert len(result) == 1


# [claude] MIM-L-35
def test_mim_l_35__without_a_machine_id_skip_past_the_end_gives_an_empty_list(db, w1, i1, i2, m1, mk_stock):
    """MIM-L-35 — without a machine_id: skip past the end gives an empty list.
    Rules: `list_machine_items` R5"""
    mk_stock(m1, i1, qty=1)
    mk_stock(m1, i2, qty=1)
    result = M.list_machine_items(db, workspace_id=w1.id, skip=3)

    # Then 1
    assert result == []


# [claude] MIM-L-36
@pytest.mark.xfail(strict=False, reason="BUG-1071: Workspace-wide machine stock list has no display order")
def test_mim_l_36__without_a_machine_id_consecutive_windows_partition_the_rows(db, w1, i1, i2, i3, m1, mk_stock):
    """MIM-L-36 — without a machine_id: consecutive windows partition the rows.
    Rules: `list_machine_items` R5 [BUG-1071]"""
    a = mk_stock(m1, i1, qty=1)
    b = mk_stock(m1, i2, qty=1)
    c = mk_stock(m1, i3, qty=1)
    win1 = M.list_machine_items(db, workspace_id=w1.id, skip=0, limit=2)
    a.qty = 7
    db.flush()
    win2 = M.list_machine_items(db, workspace_id=w1.id, skip=2, limit=2)

    # Then 1
    assert sorted([r.id for r in win1] + [r.id for r in win2]) == [a.id, b.id, c.id]


# [claude] MIM-L-37
def test_mim_l_37__without_a_machine_id_a_negative_limit_is_rejected_by_the_database(db, w1, i1, m1, mk_stock):
    """MIM-L-37 — without a machine_id: a negative limit is rejected by the database.
    Rules: `list_machine_items` R6, Errors row 1"""
    mk_stock(m1, i1, qty=1)
    before = written(db)
    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            M.list_machine_items(db, workspace_id=w1.id, limit=-1)
    # Then 2
    assert exc.value.orig.pgcode == "2201W"
    # Then 3
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 4
    assert written(db) == before


# [claude] MIM-L-38
def test_mim_l_38__without_a_machine_id_a_negative_skip_is_rejected_by_the_database(db, w1, i1, m1, mk_stock):
    """MIM-L-38 — without a machine_id: a negative skip is rejected by the database.
    Rules: `list_machine_items` R6, Errors row 2"""
    mk_stock(m1, i1, qty=1)
    before = written(db)
    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            M.list_machine_items(db, workspace_id=w1.id, skip=-1)
    # Then 2
    assert exc.value.orig.pgcode == "2201X"
    # Then 3
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 4
    assert written(db) == before


# [claude] MIM-L-39
@pytest.mark.xfail(strict=True, reason="BUG-1070: Workspace-wide machine stock list shows rows of deleted machines, deleted factories and removed items")
def test_mim_l_39__without_a_machine_id_a_row_of_a_soft_deleted_machine_is_left_out(db, w1, i1, i2, m2, mx, mk_stock):
    """MIM-L-39 — without a machine_id: a row of a soft-deleted machine is left out.
    Rules: `list_machine_items` R7 [BUG-1070]"""
    a = mk_stock(mx, i1, qty=5)
    b = mk_stock(m2, i2, qty=5)
    before_a = snap_before(db, a)
    result = M.list_machine_items(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [b.id]
    # Then 2
    assert snap(db, a) == before_a


# [claude] MIM-L-40
@pytest.mark.xfail(strict=True, reason="BUG-1070: Workspace-wide machine stock list shows rows of deleted machines, deleted factories and removed items")
def test_mim_l_40__without_a_machine_id_rows_of_a_soft_deleted_machine_take_no_place_in_the_page(db, w1, i1, i2, m2, mx, mk_stock):
    """MIM-L-40 — without a machine_id: rows of a soft-deleted machine take no place in the page.
    Rules: `list_machine_items` R7 [BUG-1070]"""
    mk_stock(mx, i1, qty=5)
    mk_stock(mx, i2, qty=5)
    b = mk_stock(m2, i1, qty=5)
    result = M.list_machine_items(db, workspace_id=w1.id, limit=2)

    # Then 1
    assert ids(result) == [b.id]


# [claude] MIM-L-41
@pytest.mark.xfail(strict=True, reason="BUG-1070: Workspace-wide machine stock list shows rows of deleted machines, deleted factories and removed items")
def test_mim_l_41__without_a_machine_id_a_row_of_a_machine_in_a_soft_deleted_factory_is_left_out(db, w1, i1, i2, m2, mf, mk_stock):
    """MIM-L-41 — without a machine_id: a row of a machine in a soft-deleted factory is left out.
    Rules: `list_machine_items` R7 [BUG-1070]"""
    a = mk_stock(mf, i1, qty=5)
    b = mk_stock(m2, i2, qty=5)
    before_a = snap_before(db, a)
    result = M.list_machine_items(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [b.id]
    # Then 2
    assert snap(db, a) == before_a


# [claude] MIM-L-42
@pytest.mark.xfail(strict=True, reason="BUG-1070: Workspace-wide machine stock list shows rows of deleted machines, deleted factories and removed items")
def test_mim_l_42__without_a_machine_id_rows_of_a_machine_in_a_soft_deleted_factory_take_no_place_in_the_page(db, w1, i1, i2, m2, mf, mk_stock):
    """MIM-L-42 — without a machine_id: rows of a machine in a soft-deleted factory take no place in the page.
    Rules: `list_machine_items` R7 [BUG-1070]"""
    mk_stock(mf, i1, qty=5)
    mk_stock(mf, i2, qty=5)
    b = mk_stock(m2, i1, qty=5)
    result = M.list_machine_items(db, workspace_id=w1.id, limit=2)

    # Then 1
    assert ids(result) == [b.id]


# [claude] MIM-L-43
@pytest.mark.xfail(strict=True, reason="BUG-1070: Workspace-wide machine stock list shows rows of deleted machines, deleted factories and removed items")
def test_mim_l_43__without_a_machine_id_a_row_of_a_removed_item_is_left_out(db, w1, i2, ix, m1, m2, mk_stock):
    """MIM-L-43 — without a machine_id: a row of a removed item is left out.
    Rules: `list_machine_items` R7 [BUG-1070]"""
    a = mk_stock(m1, ix, qty=5)
    b = mk_stock(m2, i2, qty=5)
    before_a = snap_before(db, a)
    result = M.list_machine_items(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [b.id]
    # Then 2
    assert snap(db, a) == before_a


# [claude] MIM-L-44
@pytest.mark.xfail(strict=True, reason="BUG-1070: Workspace-wide machine stock list shows rows of deleted machines, deleted factories and removed items")
def test_mim_l_44__without_a_machine_id_rows_of_a_removed_item_take_no_place_in_the_page(db, w1, i1, ix, ix2, m1, m2, mk_stock):
    """MIM-L-44 — without a machine_id: rows of a removed item take no place in the page.
    Rules: `list_machine_items` R7 [BUG-1070]"""
    mk_stock(m1, ix, qty=5)
    mk_stock(m1, ix2, qty=5)
    b = mk_stock(m2, i1, qty=5)
    result = M.list_machine_items(db, workspace_id=w1.id, limit=2)

    # Then 1
    assert ids(result) == [b.id]


# [claude] MIM-L-45
@pytest.mark.xfail(strict=True, reason="BUG-1070: Workspace-wide machine stock list shows rows of deleted machines, deleted factories and removed items")
def test_mim_l_45__without_a_machine_id_a_hidden_row_does_not_use_up_the_skip(db, w1, i1, i2, ix, m1, m2, mk_stock):
    """MIM-L-45 — without a machine_id: a hidden row does not use up the skip.
    Rules: `list_machine_items` R7 [BUG-1070]"""
    mk_stock(m1, ix, qty=5)
    mk_stock(m2, i1, qty=5)
    mk_stock(m2, i2, qty=5)
    result = M.list_machine_items(db, workspace_id=w1.id, skip=1)

    # Then 1
    assert len(result) == 1


# [claude] MIM-L-46
@pytest.mark.xfail(strict=False, reason="BUG-1070: Workspace-wide machine stock list shows rows of deleted machines, deleted factories and removed items")
def test_mim_l_46__without_a_machine_id_anvil_removed_and_bolt_active_limit_1_returns_bolt(db, w1, m1, mk_item, mk_stock):
    """MIM-L-46 — without a machine_id: Anvil removed and Bolt active, limit 1 returns Bolt.
    Rules: `list_machine_items` R7 [BUG-1070]"""
    ian = mk_item("Anvil", "anvil", is_active=False)
    ibo = mk_item("Bolt", "bolt")
    mk_stock(m1, ian, qty=5)
    mk_stock(m1, ibo, qty=5)
    result = M.list_machine_items(db, workspace_id=w1.id, limit=1)

    # Then 1
    assert names(result) == ["Bolt"]


# [claude] MIM-L-47
def test_mim_l_47__without_a_machine_id_an_inactive_but_live_machine_hides_nothing(db, w1, i1, i2, m2, ma, mk_stock):
    """MIM-L-47 — without a machine_id: an inactive-but-live machine hides nothing.
    Rules: `list_machine_items` R7a"""
    a = mk_stock(ma, i1, qty=5)
    b = mk_stock(m2, i2, qty=5)
    result = M.list_machine_items(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id, b.id]


# [claude] MIM-L-48
def test_mim_l_48__with_a_machine_id_an_inactive_but_live_machine_hides_nothing(db, w1, i1, ma, mk_stock):
    """MIM-L-48 — with a machine_id: an inactive-but-live machine hides nothing.
    Rules: `list_machine_items` R1, R7a"""
    a = mk_stock(ma, i1, qty=5)
    result = M.list_machine_items(db, workspace_id=w1.id, machine_id=ma.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MIM-L-49
def test_mim_l_49__without_a_machine_id_a_machine_in_an_inactive_but_live_factory_hides_nothing(db, w1, i1, i2, m2, mn, mk_stock):
    """MIM-L-49 — without a machine_id: a machine in an inactive-but-live factory hides nothing.
    Rules: `list_machine_items` R7a"""
    a = mk_stock(mn, i1, qty=5)
    b = mk_stock(m2, i2, qty=5)
    result = M.list_machine_items(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id, b.id]


# [claude] MIM-L-50
def test_mim_l_50__with_a_machine_id_a_machine_in_an_inactive_but_live_factory_hides_nothing(db, w1, i1, mn, mk_stock):
    """MIM-L-50 — with a machine_id: a machine in an inactive-but-live factory hides nothing.
    Rules: `list_machine_items` R1, R7a"""
    a = mk_stock(mn, i1, qty=5)
    result = M.list_machine_items(db, workspace_id=w1.id, machine_id=mn.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MIM-L-51
def test_mim_l_51__listing_changes_nothing_on_hidden_rows_and_parents(db, w1, fd, i1, i2, ix, m1, mx, mf, mk_stock):
    """MIM-L-51 — listing changes nothing on hidden rows and parents.
    Rules: `list_machine_items` R7a, R10"""
    a = mk_stock(mx, i1, qty=5)
    b = mk_stock(m1, ix, qty=5)
    c = mk_stock(mf, i2, qty=5)
    before_a = snap_before(db, a)
    before_b = snap_before(db, b)
    before_c = snap_before(db, c)
    before_mx = snap_before(db, mx)
    before_ix = snap_before(db, ix)
    before_fd = snap_before(db, fd)
    before = written(db)
    result = M.list_machine_items(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert a not in db.dirty
    # Then 3
    assert snap(db, a) == before_a
    # Then 4
    assert snap(db, b) == before_b
    # Then 5
    assert snap(db, c) == before_c
    # Then 6
    assert snap(db, mx) == before_mx
    # Then 7
    assert snap(db, ix) == before_ix
    # Then 8
    assert snap(db, fd) == before_fd
    # Then 9
    assert written(db) == before


# [claude] MIM-L-52
def test_mim_l_52__a_machine_made_live_again_brings_its_row_back_unchanged(db, w1, i1, mx, mk_stock):
    """MIM-L-52 — a machine made live again brings its row back unchanged.
    Rules: `list_machine_items` R7a"""
    a = mk_stock(mx, i1, qty=5, req_qty=7)
    mx.is_deleted = False
    mx.is_active = True
    db.flush()
    result = M.list_machine_items(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert result[0].qty == 5
    assert result[0].req_qty == 7


# [claude] MIM-L-53
def test_mim_l_53__a_factory_made_live_again_brings_its_row_back_unchanged(db, w1, fd, i1, mf, mk_stock):
    """MIM-L-53 — a factory made live again brings its row back unchanged.
    Rules: `list_machine_items` R7a"""
    a = mk_stock(mf, i1, qty=5, req_qty=7)
    fd.is_deleted = False
    db.flush()
    result = M.list_machine_items(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert result[0].qty == 5
    assert result[0].req_qty == 7


# [claude] MIM-L-54
def test_mim_l_54__an_item_made_active_again_brings_its_row_back_unchanged(db, w1, ix, m1, mk_stock):
    """MIM-L-54 — an item made active again brings its row back unchanged.
    Rules: `list_machine_items` R7a"""
    a = mk_stock(m1, ix, qty=5, req_qty=7)
    ix.is_active = True
    db.flush()
    result = M.list_machine_items(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert result[0].qty == 5
    assert result[0].req_qty == 7


# [claude] MIM-L-55
@pytest.mark.xfail(strict=False, reason="BUG-1071: Workspace-wide machine stock list has no display order")
def test_mim_l_55__without_a_machine_id_rows_come_in_item_name_order_case_insensitive(db, w1, m1, m2, mk_item, mk_stock):
    """MIM-L-55 — without a machine_id: rows come in item-name order, case-insensitive.
    Rules: `list_machine_items` R8 [BUG-1071]"""
    iz = mk_item("Zulu", "zulu")
    ia = mk_item("apple", "apple")
    ib = mk_item("Banana", "banana")
    mk_stock(m1, iz, qty=1)
    mk_stock(m1, ia, qty=1)
    mk_stock(m2, ib, qty=1)
    result = M.list_machine_items(db, workspace_id=w1.id)

    # Then 1
    assert names(result) == ["apple", "Banana", "Zulu"]


# [claude] MIM-L-56
@pytest.mark.xfail(strict=False, reason="BUG-1071: Workspace-wide machine stock list has no display order")
def test_mim_l_56__without_a_machine_id_the_order_is_applied_before_limit(db, w1, m1, m2, mk_item, mk_stock):
    """MIM-L-56 — without a machine_id: the order is applied before limit.
    Rules: `list_machine_items` R8 [BUG-1071]"""
    iz = mk_item("Zulu", "zulu")
    ia = mk_item("apple", "apple")
    ib = mk_item("Banana", "banana")
    mk_stock(m1, iz, qty=1)
    mk_stock(m1, ia, qty=1)
    mk_stock(m2, ib, qty=1)
    result = M.list_machine_items(db, workspace_id=w1.id, limit=1)

    # Then 1
    assert names(result) == ["apple"]


# [claude] MIM-L-57
@pytest.mark.xfail(strict=False, reason="BUG-1071: Workspace-wide machine stock list has no display order")
def test_mim_l_57__without_a_machine_id_the_order_is_applied_before_skip(db, w1, m1, m2, mk_item, mk_stock):
    """MIM-L-57 — without a machine_id: the order is applied before skip.
    Rules: `list_machine_items` R8 [BUG-1071]"""
    iz = mk_item("Zulu", "zulu")
    ia = mk_item("apple", "apple")
    ib = mk_item("Banana", "banana")
    mk_stock(m1, iz, qty=1)
    mk_stock(m1, ia, qty=1)
    mk_stock(m2, ib, qty=1)
    result = M.list_machine_items(db, workspace_id=w1.id, skip=2)

    # Then 1
    assert names(result) == ["Zulu"]


# [claude] MIM-L-58
@pytest.mark.xfail(strict=False, reason="BUG-1071: Workspace-wide machine stock list has no display order")
def test_mim_l_58__without_a_machine_id_equal_names_in_different_case_come_lower_row_id_first(db, w1, m1, mk_item, mk_stock):
    """MIM-L-58 — without a machine_id: equal names in different case come lower row id first.
    Rules: `list_machine_items` R8 [BUG-1071]"""
    iu = mk_item("Bolt", "bolt one")
    il = mk_item("bolt", "bolt two")
    a = mk_stock(m1, il, qty=1)
    b = mk_stock(m1, iu, qty=1)
    result = M.list_machine_items(db, workspace_id=w1.id)

    # Then 1
    assert [r.id for r in result] == [a.id, b.id]


# [claude] MIM-L-59
@pytest.mark.xfail(strict=True, reason="BUG-1071: Workspace-wide machine stock list has no display order")
def test_mim_l_59__without_a_machine_id_the_query_asks_for_an_order_by(db, w1, i1, m1, mk_stock):
    """MIM-L-59 — without a machine_id: the query asks for an ORDER BY.
    Rules: `list_machine_items` R8 [BUG-1071]"""
    mk_stock(m1, i1, qty=1)
    with record_sql(db) as sql_log:
        result = M.list_machine_items(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert any("ORDER BY" in s for s in sql_log if "FROM machine_items" in s)


# [claude] MIM-L-60
@pytest.mark.xfail(strict=True, reason="BUG-1086: A stored stock row with another workspace's item shows that item's name and id")
def test_mim_l_60__with_a_machine_id_a_stored_row_with_another_workspace_s_item_is_left_out(db, w1, i1, i9, m1, mk_stock):
    """MIM-L-60 — with a machine_id: a stored row with another workspace's item is left out.
    Rules: `list_machine_items` R9 [BUG-1086]"""
    a = mk_stock(m1, i9, qty=5)
    b = mk_stock(m1, i1, qty=5)
    before_a = snap_before(db, a)
    result = M.list_machine_items(db, workspace_id=w1.id, machine_id=m1.id)

    # Then 1
    assert ids(result) == [b.id]
    # Then 2
    assert snap(db, a) == before_a


# [claude] MIM-L-61
@pytest.mark.xfail(strict=True, reason="BUG-1086: A stored stock row with another workspace's item shows that item's name and id")
def test_mim_l_61__with_a_machine_id_stored_rows_with_another_workspace_s_item_take_no_place_in_the_page(db, w1, i1, i9, i92, m1, mk_stock):
    """MIM-L-61 — with a machine_id: stored rows with another workspace's item take no place in the page.
    Rules: `list_machine_items` R9 [BUG-1086]"""
    mk_stock(m1, i9, qty=5)
    mk_stock(m1, i92, qty=5)
    b = mk_stock(m1, i1, qty=5)
    result = M.list_machine_items(db, workspace_id=w1.id, machine_id=m1.id, limit=2)

    # Then 1
    assert ids(result) == [b.id]


# [claude] MIM-L-62
def test_mim_l_62__with_a_machine_id_rows_come_back_whatever_their_quantities(db, w1, i1, i2, i3, m1, mk_stock):
    """MIM-L-62 — with a machine_id: rows come back whatever their quantities.
    Rules: `list_machine_items` R10"""
    a = mk_stock(m1, i1, qty=0)
    b = mk_stock(m1, i2, qty=-3)
    c = mk_stock(m1, i3, qty=2, req_qty=0, defective_qty=0)
    result = M.list_machine_items(db, workspace_id=w1.id, machine_id=m1.id)

    # Then 1
    assert ids(result) == [a.id, b.id, c.id]


# [claude] MIM-L-63
@pytest.mark.xfail(strict=True, reason="BUG-1086: A stored stock row with another workspace's item shows that item's name and id")
def test_mim_l_63__without_a_machine_id_a_stored_row_with_another_workspace_s_item_is_left_out(db, w1, i1, i9, m1, mk_stock):
    """MIM-L-63 — without a machine_id: a stored row with another workspace's item is left out.
    Rules: `list_machine_items` R9 [BUG-1086]"""
    a = mk_stock(m1, i9, qty=5)
    b = mk_stock(m1, i1, qty=5)
    before_a = snap_before(db, a)
    result = M.list_machine_items(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [b.id]
    # Then 2
    assert snap(db, a) == before_a


# [claude] MIM-L-64
@pytest.mark.xfail(strict=True, reason="BUG-1086: A stored stock row with another workspace's item shows that item's name and id")
def test_mim_l_64__without_a_machine_id_stored_rows_with_another_workspace_s_item_take_no_place_in_the_page(db, w1, i1, i9, i92, m1, mk_stock):
    """MIM-L-64 — without a machine_id: stored rows with another workspace's item take no place in the page.
    Rules: `list_machine_items` R9 [BUG-1086]"""
    mk_stock(m1, i9, qty=5)
    mk_stock(m1, i92, qty=5)
    b = mk_stock(m1, i1, qty=5)
    result = M.list_machine_items(db, workspace_id=w1.id, limit=2)

    # Then 1
    assert ids(result) == [b.id]


# [claude] MIM-L-65
def test_mim_l_65__without_a_machine_id_rows_come_back_whatever_their_quantities(db, w1, i1, i2, i3, m1, mk_stock):
    """MIM-L-65 — without a machine_id: rows come back whatever their quantities.
    Rules: `list_machine_items` R10"""
    a = mk_stock(m1, i1, qty=0)
    b = mk_stock(m1, i2, qty=-3)
    c = mk_stock(m1, i3, qty=2, req_qty=0, defective_qty=0)
    result = M.list_machine_items(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id, b.id, c.id]


# [claude] MIM-L-66
def test_mim_l_66__with_a_machine_id_the_read_writes_nothing(db, w1, i1, m1, mk_stock):
    """MIM-L-66 — with a machine_id: the read writes nothing.
    Rules: `list_machine_items` R10"""
    a = mk_stock(m1, i1, qty=5)
    before_a = snap_before(db, a)
    before = written(db)
    result = M.list_machine_items(db, workspace_id=w1.id, machine_id=m1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert a not in db.dirty
    # Then 3
    assert snap(db, a) == before_a
    # Then 4
    assert written(db) == before


# [claude] MIM-L-67
@pytest.mark.xfail(strict=True, reason="BUG-1070: Workspace-wide machine stock list shows rows of deleted machines, deleted factories and removed items")
def test_mim_l_67__without_a_machine_id_rows_of_a_soft_deleted_machine_that_sort_first_take_no_place_in_the_page(db, w1, i1, m2, mx, mk_item, mk_stock):
    """MIM-L-67 — without a machine_id: rows of a soft-deleted machine that sort first take no place in the page.
    Rules: `list_machine_items` R7 [BUG-1070]"""
    ia1 = mk_item("Aaa1", "aaa1")
    ia2 = mk_item("Aaa2", "aaa2")
    mk_stock(mx, ia1, qty=5)
    mk_stock(mx, ia2, qty=5)
    b = mk_stock(m2, i1, qty=5)
    result = M.list_machine_items(db, workspace_id=w1.id, limit=2)

    # Then 1
    assert ids(result) == [b.id]


# [claude] MIM-L-68
@pytest.mark.xfail(strict=True, reason="BUG-1070: Workspace-wide machine stock list shows rows of deleted machines, deleted factories and removed items")
def test_mim_l_68__without_a_machine_id_rows_of_a_machine_in_a_soft_deleted_factory_that_sort_first_take_no_place_in_the_page(db, w1, i1, m2, mf, mk_item, mk_stock):
    """MIM-L-68 — without a machine_id: rows of a machine in a soft-deleted factory that sort first take no place in the page.
    Rules: `list_machine_items` R7 [BUG-1070]"""
    ia1 = mk_item("Aaa1", "aaa1")
    ia2 = mk_item("Aaa2", "aaa2")
    mk_stock(mf, ia1, qty=5)
    mk_stock(mf, ia2, qty=5)
    b = mk_stock(m2, i1, qty=5)
    result = M.list_machine_items(db, workspace_id=w1.id, limit=2)

    # Then 1
    assert ids(result) == [b.id]


# [claude] MIM-L-69
@pytest.mark.xfail(strict=True, reason="BUG-1086: A stored stock row with another workspace's item shows that item's name and id")
def test_mim_l_69__with_a_machine_id_stored_rows_with_another_workspace_s_item_that_sort_first_take_no_place_in_the_page(db, w1, w2, i1, m1, mk_item, mk_stock):
    """MIM-L-69 — with a machine_id: stored rows with another workspace's item that sort first take no place in the page.
    Rules: `list_machine_items` R9 [BUG-1086]"""
    ia1 = mk_item("Aaa1", "aaa1", workspace_id=w2.id)
    ia2 = mk_item("Aaa2", "aaa2", workspace_id=w2.id)
    mk_stock(m1, ia1, qty=5)
    mk_stock(m1, ia2, qty=5)
    b = mk_stock(m1, i1, qty=5)
    result = M.list_machine_items(db, workspace_id=w1.id, machine_id=m1.id, limit=2)

    # Then 1
    assert ids(result) == [b.id]


# [claude] MIM-L-70
@pytest.mark.xfail(strict=True, reason="BUG-1086: A stored stock row with another workspace's item shows that item's name and id")
def test_mim_l_70__without_a_machine_id_stored_rows_with_another_workspace_s_item_that_sort_first_take_no_place_in_the_page(db, w1, w2, i1, m1, mk_item, mk_stock):
    """MIM-L-70 — without a machine_id: stored rows with another workspace's item that sort first take no place in the page.
    Rules: `list_machine_items` R9 [BUG-1086]"""
    ia1 = mk_item("Aaa1", "aaa1", workspace_id=w2.id)
    ia2 = mk_item("Aaa2", "aaa2", workspace_id=w2.id)
    mk_stock(m1, ia1, qty=5)
    mk_stock(m1, ia2, qty=5)
    b = mk_stock(m1, i1, qty=5)
    result = M.list_machine_items(db, workspace_id=w1.id, limit=2)

    # Then 1
    assert ids(result) == [b.id]


# [claude] MIM-W-01
def test_mim_w_01__one_ledger_row_is_written_with_the_arguments_as_given(db, w1, u2, i1, m1):
    """MIM-W-01 — one ledger row is written with the arguments as given.
    Rules: `_write_ledger_entry` R1, Returns"""
    result = M._write_ledger_entry(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id, transaction_type="inventory_adjustment", quantity=2, qty_before=10, qty_after=12, user_id=u2.id, notes="Count fix", source_type="adjustment")

    # Then 1
    assert result is None
    # Then 2
    assert len(entries_of(db, m1, i1)) == 1
    # Then 3
    row = entries_of(db, m1, i1)[-1]
    assert row.workspace_id == w1.id
    assert row.machine_id == m1.id
    assert row.item_id == i1.id
    # Then 4
    row = entries_of(db, m1, i1)[-1]
    assert row.transaction_type == "inventory_adjustment"
    assert row.quantity == 2
    # Then 5
    row = entries_of(db, m1, i1)[-1]
    assert row.qty_before == 10
    assert row.qty_after == 12
    # Then 6
    row = entries_of(db, m1, i1)[-1]
    assert row.source_type == "adjustment"
    assert row.notes == "Count fix"
    # Then 7
    row = entries_of(db, m1, i1)[-1]
    assert row.performed_by == u2.id
    assert row.performed_at is not None


# [claude] MIM-W-02
def test_mim_w_02__source_id_order_and_transfer_columns_stay_empty(db, w1, u2, i1, m1):
    """MIM-W-02 — source_id, order and transfer columns stay empty.
    Rules: `_write_ledger_entry` R1"""
    result = M._write_ledger_entry(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id, transaction_type="inventory_adjustment", quantity=2, qty_before=10, qty_after=12, user_id=u2.id, notes="Count fix", source_type="adjustment")

    # Then 1
    assert result is None
    # Then 2
    row = entries_of(db, m1, i1)[-1]
    assert row.source_id is None
    assert row.order_id is None
    assert row.order_type is None
    assert row.invoice_id is None
    # Then 3
    row = entries_of(db, m1, i1)[-1]
    assert row.transfer_source_id is None
    assert row.transfer_destination_id is None
    # Then 4
    row = entries_of(db, m1, i1)[-1]
    assert row.transfer_source_type is None
    assert row.transfer_destination_type is None


# [claude] MIM-W-03
def test_mim_w_03__source_type_defaults_to_manual(db, w1, u2, i1, m1):
    """MIM-W-03 — source_type defaults to "manual" .
    Rules: `_write_ledger_entry` R1"""
    result = M._write_ledger_entry(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id, transaction_type="manual_add", quantity=4, qty_before=0, qty_after=4, user_id=u2.id, notes="Opening")

    # Then 1
    assert result is None
    # Then 2
    row = entries_of(db, m1, i1)[-1]
    assert row.source_type == "manual"
    assert row.transaction_type == "manual_add"


# [claude] MIM-W-04
@pytest.mark.xfail(strict=True, reason="BUG-993: A manual stock change wipes the machine's cost")
def test_mim_w_04__the_three_prices_are_the_current_average(db, w1, u2, i1, m1, mk_entry):
    """MIM-W-04 — the three prices are the current average.
    Rules: `_write_ledger_entry` R2 [BUG-993]"""
    mk_entry(m1, i1, performed_at=T9, avg_price_after=Decimal("5.00"), qty_after=10)
    result = M._write_ledger_entry(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id, transaction_type="inventory_adjustment", quantity=2, qty_before=10, qty_after=12, user_id=u2.id, notes="Count fix", source_type="adjustment")

    # Then 1
    assert result is None
    # Then 2
    assert len(entries_of(db, m1, i1)) == 2
    # Then 3
    row = entries_of(db, m1, i1)[-1]
    assert row.unit_cost == Decimal("5.00")
    assert row.avg_price_before == Decimal("5.00")
    assert row.avg_price_after == Decimal("5.00")


# [claude] MIM-W-05
@pytest.mark.xfail(strict=True, reason="BUG-993: A manual stock change wipes the machine's cost")
def test_mim_w_05__the_average_applies_when_qty_before_is_0(db, w1, u2, i1, m1, mk_entry):
    """MIM-W-05 — the average applies when qty_before is 0.
    Rules: `_write_ledger_entry` R2 [BUG-993], R3, R4"""
    mk_entry(m1, i1, performed_at=T9, avg_price_after=Decimal("5.00"), qty_after=0)
    result = M._write_ledger_entry(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id, transaction_type="inventory_adjustment", quantity=4, qty_before=0, qty_after=4, user_id=u2.id, notes="Count fix", source_type="adjustment")

    # Then 1
    assert result is None
    # Then 2
    row = entries_of(db, m1, i1)[-1]
    assert row.unit_cost == Decimal("5.00")
    assert row.avg_price_before == Decimal("5.00")
    assert row.avg_price_after == Decimal("5.00")
    # Then 3
    row = entries_of(db, m1, i1)[-1]
    assert row.total_cost == Decimal("20.00")
    assert row.value_before == Decimal("0.00")
    assert row.value_after == Decimal("20.00")


# [claude] MIM-W-06
@pytest.mark.xfail(strict=True, reason="BUG-993: A manual stock change wipes the machine's cost")
def test_mim_w_06__total_cost_is_quantity_times_the_average(db, w1, u2, i1, m1, mk_entry):
    """MIM-W-06 — total_cost is quantity times the average.
    Rules: `_write_ledger_entry` R3 [BUG-993]"""
    mk_entry(m1, i1, performed_at=T9, avg_price_after=Decimal("5.00"), qty_after=10)
    result = M._write_ledger_entry(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id, transaction_type="inventory_adjustment", quantity=2, qty_before=10, qty_after=12, user_id=u2.id, notes="Count fix", source_type="adjustment")

    # Then 1
    assert result is None
    # Then 2
    row = entries_of(db, m1, i1)[-1]
    assert row.total_cost == Decimal("10.00")


# [claude] MIM-W-07
@pytest.mark.xfail(strict=True, reason="BUG-993: A manual stock change wipes the machine's cost")
def test_mim_w_07__total_cost_uses_the_size_of_the_quantity(db, w1, u2, i1, m1, mk_entry):
    """MIM-W-07 — total_cost uses the size of the quantity.
    Rules: `_write_ledger_entry` R3 [BUG-993]"""
    mk_entry(m1, i1, performed_at=T9, avg_price_after=Decimal("5.00"), qty_after=10)
    result = M._write_ledger_entry(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id, transaction_type="inventory_adjustment", quantity=-2, qty_before=10, qty_after=12, user_id=u2.id, notes="Count fix", source_type="adjustment")

    # Then 1
    assert result is None
    # Then 2
    row = entries_of(db, m1, i1)[-1]
    assert row.quantity == -2
    # Then 3
    row = entries_of(db, m1, i1)[-1]
    assert row.total_cost == Decimal("10.00")


# [claude] MIM-W-08
@pytest.mark.xfail(strict=True, reason="BUG-1040: Money rounded half to even in Python, half away from zero in the database (needs BUG-993 too: A manual stock change wipes the machine's cost)")
def test_mim_w_08__total_cost_of_1_at_0_125_rounds_half_up_to_0_13(db, w1, u2, i1, m1, mk_entry):
    """MIM-W-08 — total_cost of 1 at 0.125 rounds half up to 0.13.
    Rules: `_write_ledger_entry` R3 [BUG-993] [BUG-1040]"""
    lg = mk_entry(m1, i1, performed_at=T9, avg_price_after=Decimal("0.125"), qty_after=1)  # noqa: F841  (Conventions: kept alive, never refreshed)
    result = M._write_ledger_entry(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id, transaction_type="inventory_adjustment", quantity=1, qty_before=1, qty_after=2, user_id=u2.id, notes="Count fix", source_type="adjustment")

    # Then 1
    assert result is None
    # Then 2
    row = entries_of(db, m1, i1)[-1]
    assert row.total_cost == Decimal("0.13")


# [claude] MIM-W-09
@pytest.mark.xfail(strict=True, reason="BUG-1040: Money rounded half to even in Python, half away from zero in the database (needs BUG-993 too: A manual stock change wipes the machine's cost)")
def test_mim_w_09__total_cost_of_5_at_0_125_rounds_the_product_not_the_price(db, w1, u2, i1, m1, mk_entry):
    """MIM-W-09 — total_cost of 5 at 0.125 rounds the product, not the price.
    Rules: `_write_ledger_entry` R3 [BUG-993] [BUG-1040]"""
    lg = mk_entry(m1, i1, performed_at=T9, avg_price_after=Decimal("0.125"), qty_after=1)  # noqa: F841  (Conventions: kept alive, never refreshed)
    result = M._write_ledger_entry(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id, transaction_type="inventory_adjustment", quantity=5, qty_before=1, qty_after=6, user_id=u2.id, notes="Count fix", source_type="adjustment")

    # Then 1
    assert result is None
    # Then 2
    row = entries_of(db, m1, i1)[-1]
    assert row.total_cost == Decimal("0.63")


# [claude] MIM-W-10
@pytest.mark.xfail(strict=True, reason="BUG-993: A manual stock change wipes the machine's cost")
def test_mim_w_10__value_before_and_value_after_use_the_average(db, w1, u2, i1, m1, mk_entry):
    """MIM-W-10 — value_before and value_after use the average.
    Rules: `_write_ledger_entry` R4 [BUG-993]"""
    mk_entry(m1, i1, performed_at=T9, avg_price_after=Decimal("5.00"), qty_after=10)
    result = M._write_ledger_entry(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id, transaction_type="inventory_adjustment", quantity=2, qty_before=10, qty_after=12, user_id=u2.id, notes="Count fix", source_type="adjustment")

    # Then 1
    assert result is None
    # Then 2
    row = entries_of(db, m1, i1)[-1]
    assert row.value_before == Decimal("50.00")
    assert row.value_after == Decimal("60.00")


# [claude] MIM-W-11
@pytest.mark.xfail(strict=True, reason="BUG-993: A manual stock change wipes the machine's cost")
def test_mim_w_11__a_stored_negative_quantity_gives_a_negative_value(db, w1, u2, i1, m1, mk_entry):
    """MIM-W-11 — a stored negative quantity gives a negative value.
    Rules: `_write_ledger_entry` R4 [BUG-993]"""
    mk_entry(m1, i1, performed_at=T9, avg_price_after=Decimal("5.00"), qty_after=10)
    result = M._write_ledger_entry(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id, transaction_type="inventory_adjustment", quantity=5, qty_before=-3, qty_after=2, user_id=u2.id, notes="Count fix", source_type="adjustment")

    # Then 1
    assert result is None
    # Then 2
    row = entries_of(db, m1, i1)[-1]
    assert row.value_before == Decimal("-15.00")
    assert row.value_after == Decimal("10.00")


# [claude] MIM-W-12
def test_mim_w_12__no_ledger_history_all_six_cost_fields_are_0_00(db, w1, u2, i1, m1):
    """MIM-W-12 — no ledger history: all six cost fields are 0.00.
    Rules: `_write_ledger_entry` R5"""
    result = M._write_ledger_entry(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id, transaction_type="inventory_adjustment", quantity=2, qty_before=10, qty_after=12, user_id=u2.id, notes="Count fix", source_type="adjustment")

    # Then 1
    assert result is None
    # Then 2
    row = entries_of(db, m1, i1)[-1]
    assert row.unit_cost == Decimal("0.00")
    assert row.total_cost == Decimal("0.00")
    # Then 3
    row = entries_of(db, m1, i1)[-1]
    assert row.value_before == Decimal("0.00")
    assert row.value_after == Decimal("0.00")
    # Then 4
    row = entries_of(db, m1, i1)[-1]
    assert row.avg_price_before == Decimal("0.00")
    assert row.avg_price_after == Decimal("0.00")


# [claude] MIM-W-13
def test_mim_w_13__history_of_another_machine_does_not_count_all_six_cost_fields_are_0_00(db, w1, u2, i1, m1, m2, mk_entry):
    """MIM-W-13 — history of another machine does not count: all six cost fields are 0.00.
    Rules: `_write_ledger_entry` R5"""
    ot = mk_entry(m2, i1, performed_at=T9, avg_price_after=Decimal("9.00"))
    before_ot = snap_before(db, ot)
    result = M._write_ledger_entry(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id, transaction_type="inventory_adjustment", quantity=2, qty_before=10, qty_after=12, user_id=u2.id, notes="Count fix", source_type="adjustment")

    # Then 1
    assert result is None
    # Then 2
    row = entries_of(db, m1, i1)[-1]
    assert row.unit_cost == Decimal("0.00")
    assert row.total_cost == Decimal("0.00")
    # Then 3
    row = entries_of(db, m1, i1)[-1]
    assert row.value_before == Decimal("0.00")
    assert row.value_after == Decimal("0.00")
    # Then 4
    row = entries_of(db, m1, i1)[-1]
    assert row.avg_price_before == Decimal("0.00")
    assert row.avg_price_after == Decimal("0.00")
    # Then 5
    assert snap(db, ot) == before_ot


# [claude] MIM-W-14
def test_mim_w_14__history_of_another_item_does_not_count_all_six_cost_fields_are_0_00(db, w1, u2, i1, i2, m1, mk_entry):
    """MIM-W-14 — history of another item does not count: all six cost fields are 0.00.
    Rules: `_write_ledger_entry` R5"""
    ot = mk_entry(m1, i2, performed_at=T9, avg_price_after=Decimal("9.00"))
    before_ot = snap_before(db, ot)
    result = M._write_ledger_entry(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id, transaction_type="inventory_adjustment", quantity=2, qty_before=10, qty_after=12, user_id=u2.id, notes="Count fix", source_type="adjustment")

    # Then 1
    assert result is None
    # Then 2
    row = entries_of(db, m1, i1)[-1]
    assert row.unit_cost == Decimal("0.00")
    assert row.total_cost == Decimal("0.00")
    # Then 3
    row = entries_of(db, m1, i1)[-1]
    assert row.value_before == Decimal("0.00")
    assert row.value_after == Decimal("0.00")
    # Then 4
    row = entries_of(db, m1, i1)[-1]
    assert row.avg_price_before == Decimal("0.00")
    assert row.avg_price_after == Decimal("0.00")
    # Then 5
    assert snap(db, ot) == before_ot


# [claude] MIM-W-15
def test_mim_w_15__history_of_another_workspace_does_not_count_all_six_cost_fields_are_0_00(db, w1, w2, u2, i1, m1, mk_entry):
    """MIM-W-15 — history of another workspace does not count: all six cost fields are 0.00.
    Rules: `_write_ledger_entry` R5"""
    ot = mk_entry(m1, i1, performed_at=T9, avg_price_after=Decimal("9.00"), workspace_id=w2.id)
    before_ot = snap_before(db, ot)
    result = M._write_ledger_entry(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id, transaction_type="inventory_adjustment", quantity=2, qty_before=10, qty_after=12, user_id=u2.id, notes="Count fix", source_type="adjustment")

    # Then 1
    assert result is None
    # Then 2
    row = entries_of(db, m1, i1)[-1]
    assert row.unit_cost == Decimal("0.00")
    assert row.total_cost == Decimal("0.00")
    # Then 3
    row = entries_of(db, m1, i1)[-1]
    assert row.value_before == Decimal("0.00")
    assert row.value_after == Decimal("0.00")
    # Then 4
    row = entries_of(db, m1, i1)[-1]
    assert row.avg_price_before == Decimal("0.00")
    assert row.avg_price_after == Decimal("0.00")
    # Then 5
    assert snap(db, ot) == before_ot


# [claude] MIM-W-16
def test_mim_w_16__an_empty_latest_average_counts_as_0_whatever_value_after_holds(db, w1, u2, i1, m1, mk_entry):
    """MIM-W-16 — an empty latest average counts as 0, whatever value_after holds.
    Rules: `_write_ledger_entry` R6"""
    mk_entry(m1, i1, performed_at=T9, avg_price_after=None, qty_after=10, value_after=Decimal("50.00"))
    result = M._write_ledger_entry(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id, transaction_type="inventory_adjustment", quantity=2, qty_before=10, qty_after=12, user_id=u2.id, notes="Count fix", source_type="adjustment")

    # Then 1
    assert result is None
    # Then 2
    row = entries_of(db, m1, i1)[-1]
    assert row.unit_cost == Decimal("0.00")
    assert row.total_cost == Decimal("0.00")
    # Then 3
    row = entries_of(db, m1, i1)[-1]
    assert row.value_before == Decimal("0.00")
    assert row.value_after == Decimal("0.00")
    # Then 4
    row = entries_of(db, m1, i1)[-1]
    assert row.avg_price_before == Decimal("0.00")
    assert row.avg_price_after == Decimal("0.00")


# [claude] MIM-W-17
def test_mim_w_17__a_latest_average_of_0_00_stays_0_00_even_over_a_non_zero_older_one(db, w1, u2, i1, m1, mk_entry):
    """MIM-W-17 — a latest average of 0.00 stays 0.00 even over a non-zero older one.
    Rules: `_write_ledger_entry` R7"""
    l1 = mk_entry(m1, i1, performed_at=T9, avg_price_after=Decimal("5.00"))
    l2 = mk_entry(m1, i1, performed_at=T10, avg_price_after=Decimal("0.00"))
    before_l1 = snap_before(db, l1)
    before_l2 = snap_before(db, l2)
    result = M._write_ledger_entry(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id, transaction_type="inventory_adjustment", quantity=2, qty_before=10, qty_after=12, user_id=u2.id, notes="Count fix", source_type="adjustment")

    # Then 1
    assert result is None
    # Then 2
    row = entries_of(db, m1, i1)[-1]
    assert row.unit_cost == Decimal("0.00")
    assert row.total_cost == Decimal("0.00")
    # Then 3
    row = entries_of(db, m1, i1)[-1]
    assert row.value_before == Decimal("0.00")
    assert row.value_after == Decimal("0.00")
    # Then 4
    row = entries_of(db, m1, i1)[-1]
    assert row.avg_price_before == Decimal("0.00")
    assert row.avg_price_after == Decimal("0.00")
    # Then 5
    assert snap(db, l1) == before_l1
    # Then 6
    assert snap(db, l2) == before_l2


# [claude] MIM-W-18
@pytest.mark.xfail(strict=True, reason="BUG-993: A manual stock change wipes the machine's cost")
def test_mim_w_18__only_the_latest_entry_counts_not_row_order_and_not_a_newer_entry_of_another_machine(db, w1, u2, i1, m1, m2, mk_entry):
    """MIM-W-18 — only the latest entry counts, not row order and not a newer entry of another machine.
    Rules: `_write_ledger_entry` R8 [BUG-993], R2"""
    mk_entry(m1, i1, performed_at=T9, avg_price_after=Decimal("3.00"))
    mk_entry(m1, i1, performed_at=T11, avg_price_after=Decimal("5.00"))
    mk_entry(m1, i1, performed_at=T10, avg_price_after=Decimal("4.00"))
    mk_entry(m2, i1, performed_at=T12, avg_price_after=Decimal("9.00"))
    result = M._write_ledger_entry(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id, transaction_type="inventory_adjustment", quantity=2, qty_before=10, qty_after=12, user_id=u2.id, notes="Count fix", source_type="adjustment")

    # Then 1
    assert result is None
    # Then 2
    row = entries_of(db, m1, i1)[-1]
    assert row.avg_price_after == Decimal("5.00")
    assert row.unit_cost == Decimal("5.00")


# [claude] MIM-W-19
@pytest.mark.xfail(strict=True, reason="BUG-993: A manual stock change wipes the machine's cost")
def test_mim_w_19__only_the_latest_entry_counts_not_row_order_and_not_a_newer_entry_of_another_item(db, w1, u2, i1, i2, m1, mk_entry):
    """MIM-W-19 — only the latest entry counts, not row order and not a newer entry of another item.
    Rules: `_write_ledger_entry` R8 [BUG-993], R2"""
    mk_entry(m1, i1, performed_at=T9, avg_price_after=Decimal("3.00"))
    mk_entry(m1, i1, performed_at=T11, avg_price_after=Decimal("5.00"))
    mk_entry(m1, i1, performed_at=T10, avg_price_after=Decimal("4.00"))
    mk_entry(m1, i2, performed_at=T12, avg_price_after=Decimal("9.00"))
    result = M._write_ledger_entry(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id, transaction_type="inventory_adjustment", quantity=2, qty_before=10, qty_after=12, user_id=u2.id, notes="Count fix", source_type="adjustment")

    # Then 1
    assert result is None
    # Then 2
    row = entries_of(db, m1, i1)[-1]
    assert row.avg_price_after == Decimal("5.00")
    assert row.unit_cost == Decimal("5.00")


# [claude] MIM-W-20
@pytest.mark.xfail(strict=True, reason="BUG-993: A manual stock change wipes the machine's cost")
def test_mim_w_20__only_the_latest_entry_counts_not_row_order_and_not_a_newer_entry_of_another_workspace(db, w1, w2, u2, i1, m1, mk_entry):
    """MIM-W-20 — only the latest entry counts, not row order and not a newer entry of another workspace.
    Rules: `_write_ledger_entry` R8 [BUG-993], R2"""
    mk_entry(m1, i1, performed_at=T9, avg_price_after=Decimal("3.00"))
    mk_entry(m1, i1, performed_at=T11, avg_price_after=Decimal("5.00"))
    mk_entry(m1, i1, performed_at=T10, avg_price_after=Decimal("4.00"))
    mk_entry(m1, i1, performed_at=T12, avg_price_after=Decimal("9.00"), workspace_id=w2.id)
    result = M._write_ledger_entry(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id, transaction_type="inventory_adjustment", quantity=2, qty_before=10, qty_after=12, user_id=u2.id, notes="Count fix", source_type="adjustment")

    # Then 1
    assert result is None
    # Then 2
    row = entries_of(db, m1, i1)[-1]
    assert row.avg_price_after == Decimal("5.00")
    assert row.unit_cost == Decimal("5.00")


# [claude] MIM-W-21
@pytest.mark.xfail(strict=True, reason="BUG-993: A manual stock change wipes the machine's cost")
def test_mim_w_21__chain_receive_10_at_5_00_change_to_12_by_hand_the_balance_is_12_worth_60_00(db, w1, u1, u2, i1, m1, mk_stock):
    """MIM-W-21 — chain: receive 10 at 5.00, change to 12 by hand, the balance is 12 worth 60.00.
    Rules: `_write_ledger_entry` R9 [BUG-993], `update_machine_item` R8"""
    mi = mk_stock(m1, i1, qty=0)
    _machine_in(db, machine_id=m1.id, item_id=i1.id, qty=10, unit_cost=Decimal("5.00"), transaction_type="transfer_in", source_type="transfer_order", source_id=31, notes="TO-31", workspace_id=w1.id, user_id=u1.id, source_loc_type=None, source_loc_id=None, activity_event_type="transfer_in", activity_description=None)
    db.flush()
    next_clock_tick()
    result = M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(qty=12), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.qty == 12
    # Then 2
    assert machine_item_ledger_dao.calculate_balance(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id) == (12, Decimal("60.00"))


# [claude] MIM-W-22
@pytest.mark.xfail(strict=True, reason="BUG-993: A manual stock change wipes the machine's cost")
def test_mim_w_22__chain_after_the_manual_change_the_unit_cost_is_still_5_00(db, w1, u1, u2, i1, m1, mk_stock):
    """MIM-W-22 — chain: after the manual change the unit cost is still 5.00.
    Rules: `_write_ledger_entry` R9 [BUG-993]"""
    mi = mk_stock(m1, i1, qty=0)
    _machine_in(db, machine_id=m1.id, item_id=i1.id, qty=10, unit_cost=Decimal("5.00"), transaction_type="transfer_in", source_type="transfer_order", source_id=31, notes="TO-31", workspace_id=w1.id, user_id=u1.id, source_loc_type=None, source_loc_id=None, activity_event_type="transfer_in", activity_description=None)
    db.flush()
    next_clock_tick()
    result = M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(qty=12), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.qty == 12
    # Then 2
    assert get_machine_unit_cost(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id) == Decimal("5.00")


# [claude] MIM-W-23
def test_mim_w_23__chain_the_balance_quantity_follows_the_manual_change(db, w1, u1, u2, i1, m1, mk_stock):
    """MIM-W-23 — chain: the balance quantity follows the manual change.
    Rules: `_write_ledger_entry` R9, R1, `update_machine_item` R8"""
    mi = mk_stock(m1, i1, qty=0)
    _machine_in(db, machine_id=m1.id, item_id=i1.id, qty=10, unit_cost=Decimal("5.00"), transaction_type="transfer_in", source_type="transfer_order", source_id=31, notes="TO-31", workspace_id=w1.id, user_id=u1.id, source_loc_type=None, source_loc_id=None, activity_event_type="transfer_in", activity_description=None)
    db.flush()
    next_clock_tick()
    result = M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(qty=12), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.qty == 12
    # Then 2
    assert machine_item_ledger_dao.calculate_balance(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)[0] == 12


# [claude] MIM-W-24
@pytest.mark.xfail(strict=True, reason="BUG-993: A manual stock change wipes the machine's cost")
def test_mim_w_24__chain_a_consumption_after_the_manual_change_is_priced_at_5_00(db, w1, u1, u2, i1, m1, mk_stock):
    """MIM-W-24 — chain: a consumption after the manual change is priced at 5.00.
    Rules: `_write_ledger_entry` R9 [BUG-993]"""
    mi = mk_stock(m1, i1, qty=0)
    _machine_in(db, machine_id=m1.id, item_id=i1.id, qty=10, unit_cost=Decimal("5.00"), transaction_type="transfer_in", source_type="transfer_order", source_id=31, notes="TO-31", workspace_id=w1.id, user_id=u1.id, source_loc_type=None, source_loc_id=None, activity_event_type="transfer_in", activity_description=None)
    db.flush()
    next_clock_tick()
    M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(qty=12), workspace_id=w1.id, user_id=u2.id)
    db.flush()
    next_clock_tick()
    result = _machine_out(db, machine_id=m1.id, item_id=i1.id, qty=2, transaction_type="consumption", source_type="work_order", source_id=17, notes="WO-17 line 1", workspace_id=w1.id, user_id=u1.id, dest_type=None, dest_id=None, activity_event_type="consumption", activity_description=None)

    # Then 1
    assert result == Decimal("5.00")


# [claude] MIM-W-25
@pytest.mark.xfail(strict=True, reason="BUG-993: A manual stock change wipes the machine's cost")
def test_mim_w_25__chain_after_the_consumption_the_balance_is_10_worth_50_00(db, w1, u1, u2, i1, m1, mk_stock):
    """MIM-W-25 — chain: after the consumption the balance is 10 worth 50.00.
    Rules: `_write_ledger_entry` R9 [BUG-993]"""
    mi = mk_stock(m1, i1, qty=0)
    _machine_in(db, machine_id=m1.id, item_id=i1.id, qty=10, unit_cost=Decimal("5.00"), transaction_type="transfer_in", source_type="transfer_order", source_id=31, notes="TO-31", workspace_id=w1.id, user_id=u1.id, source_loc_type=None, source_loc_id=None, activity_event_type="transfer_in", activity_description=None)
    db.flush()
    next_clock_tick()
    M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(qty=12), workspace_id=w1.id, user_id=u2.id)
    db.flush()
    next_clock_tick()
    result = _machine_out(db, machine_id=m1.id, item_id=i1.id, qty=2, transaction_type="consumption", source_type="work_order", source_id=17, notes="WO-17 line 1", workspace_id=w1.id, user_id=u1.id, dest_type=None, dest_id=None, activity_event_type="consumption", activity_description=None)  # noqa: F841

    # Then 1
    row = reread(db, mi)
    assert row.qty == 10
    # Then 2
    assert machine_item_ledger_dao.calculate_balance(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id) == (10, Decimal("50.00"))


# [claude] MIM-W-26
def test_mim_w_26__an_adjustment_writes_one_inventory_adjusted_event(db, w1, u2, i1, m1):
    """MIM-W-26 — an adjustment writes one inventory_adjusted event.
    Rules: `_write_ledger_entry` R10"""
    result = M._write_ledger_entry(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id, transaction_type="inventory_adjustment", quantity=2, qty_before=10, qty_after=12, user_id=u2.id, notes="Count fix", source_type="adjustment")

    # Then 1
    assert result is None
    # Then 2
    rows = events_of(db, m1)
    assert len(rows) == 1
    # Then 3
    assert rows[0].event_type == "inventory_adjusted"
    assert rows[0].description == "Inventory adjusted on Bolt M8: 10 → 12"
    # Then 4
    assert rows[0].performed_by == u2.id
    assert rows[0].workspace_id == w1.id
    assert rows[0].machine_id == m1.id
    # Then 5
    assert rows[0].metadata_json == {"item_id": i1.id, "item_name": "Bolt M8", "quantity": 2, "changes": [{"field": "qty", "label": "Quantity", "from_value": "10", "to_value": "12"}]}


# [claude] MIM-W-27
def test_mim_w_27__the_adjustment_event_of_a_removed_item_carries_its_name(db, w1, u2, ix, m1):
    """MIM-W-27 — the adjustment event of a removed item carries its name.
    Rules: `_write_ledger_entry` R10, `_item_name` R2"""
    result = M._write_ledger_entry(db, workspace_id=w1.id, machine_id=m1.id, item_id=ix.id, transaction_type="inventory_adjustment", quantity=2, qty_before=10, qty_after=12, user_id=u2.id, notes="Count fix", source_type="adjustment")

    # Then 1
    assert result is None
    # Then 2
    rows = events_of(db, m1)
    assert len(rows) == 1
    # Then 3
    assert rows[0].description == "Inventory adjusted on Old Rivet: 10 → 12"


# [claude] MIM-W-28
def test_mim_w_28__a_manual_add_writes_the_entry_and_no_event(db, w1, u2, i1, m1):
    """MIM-W-28 — a manual_add writes the entry and no event.
    Rules: `_write_ledger_entry` R11"""
    result = M._write_ledger_entry(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id, transaction_type="manual_add", quantity=4, qty_before=0, qty_after=4, user_id=u2.id, notes="Opening")

    # Then 1
    assert result is None
    # Then 2
    assert len(entries_of(db, m1, i1)) == 1
    # Then 3
    rows = events_of(db, m1)
    assert len(rows) == 0


# [claude] MIM-W-29
def test_mim_w_29__an_unknown_user_is_a_foreign_key_error_manual_add(db, w1, i1, m1):
    """MIM-W-29 — an unknown user is a foreign key error (manual_add).
    Rules: `_write_ledger_entry` R12, Errors row 1"""
    before = written(db)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            M._write_ledger_entry(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id, transaction_type="manual_add", quantity=2, qty_before=10, qty_after=12, user_id=MISSING, notes="Count fix", source_type="adjustment")
    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert exc.value.orig.diag.constraint_name == "machine_item_ledger_performed_by_fkey"
    # Then 4
    assert written(db) == before


# [claude] MIM-W-30
def test_mim_w_30__an_unknown_user_is_a_foreign_key_error_inventory_adjustment(db, w1, i1, m1):
    """MIM-W-30 — an unknown user is a foreign key error (inventory_adjustment).
    Rules: `_write_ledger_entry` R12, Errors row 1"""
    before = written(db)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            M._write_ledger_entry(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id, transaction_type="inventory_adjustment", quantity=2, qty_before=10, qty_after=12, user_id=MISSING, notes="Count fix", source_type="adjustment")
    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert exc.value.orig.diag.constraint_name == "machine_item_ledger_performed_by_fkey"
    # Then 4
    assert written(db) == before


# [claude] MIM-W-31
def test_mim_w_31__the_entry_and_event_are_flushed_but_not_committed(db, w1, u2, i1, m1, monkeypatch):
    """MIM-W-31 — the entry and event are flushed but not committed.
    Rules: `_write_ledger_entry` R13"""
    sp = db.begin_nested()
    spy = commit_spy(db, monkeypatch)
    result = M._write_ledger_entry(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id, transaction_type="inventory_adjustment", quantity=2, qty_before=10, qty_after=12, user_id=u2.id, notes="Count fix", source_type="adjustment")

    # Then 1
    assert result is None
    # Then 2
    assert len(entries_of(db, m1, i1)) == 1
    # Then 3
    rows = events_of(db, m1)
    assert len(rows) == 1
    # Then 4
    sp.rollback()
    assert count_rows(db, "machine_item_ledger") == 0
    # Then 5
    assert count_rows(db, "machine_activity_events") == 0
    # Then 6
    spy.assert_not_called()


# [claude] MIM-W-32
@pytest.mark.xfail(strict=True, reason="BUG-1040: Money rounded half to even in Python, half away from zero in the database (needs BUG-993 too: A manual stock change wipes the machine's cost)")
def test_mim_w_32__value_before_and_value_after_at_0_125_round_half_up(db, w1, u2, i1, m1, mk_entry):
    """MIM-W-32 — value_before and value_after at 0.125 round half up.
    Rules: `_write_ledger_entry` R4 [BUG-993] [BUG-1040]"""
    lg = mk_entry(m1, i1, performed_at=T9, avg_price_after=Decimal("0.125"), qty_after=1)  # noqa: F841  (Conventions: kept alive, never refreshed)
    result = M._write_ledger_entry(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id, transaction_type="inventory_adjustment", quantity=1, qty_before=1, qty_after=2, user_id=u2.id, notes="Count fix", source_type="adjustment")

    # Then 1
    assert result is None
    # Then 2
    row = entries_of(db, m1, i1)[-1]
    assert row.value_before == Decimal("0.13")
    assert row.value_after == Decimal("0.25")


# [claude] MIM-W-33
@pytest.mark.xfail(strict=True, reason="BUG-1040: Money rounded half to even in Python, half away from zero in the database (needs BUG-993 too: A manual stock change wipes the machine's cost)")
def test_mim_w_33__value_after_at_0_125_on_a_change_from_2_to_1_rounds_half_up(db, w1, u2, i1, m1, mk_entry):
    """MIM-W-33 — value_after at 0.125 on a change from 2 to 1 rounds half up.
    Rules: `_write_ledger_entry` R4 [BUG-993] [BUG-1040]"""
    lg = mk_entry(m1, i1, performed_at=T9, avg_price_after=Decimal("0.125"), qty_after=2)  # noqa: F841  (Conventions: kept alive, never refreshed)
    result = M._write_ledger_entry(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id, transaction_type="inventory_adjustment", quantity=1, qty_before=2, qty_after=1, user_id=u2.id, notes="Count fix", source_type="adjustment")

    # Then 1
    assert result is None
    # Then 2
    row = entries_of(db, m1, i1)[-1]
    assert row.value_after == Decimal("0.13")


# [claude] MIM-C-01
def test_mim_c_01__a_missing_machine_gets_the_same_404(db, w1, u2, i1):
    """MIM-C-01 — a missing machine gets the same 404.
    Rules: `create_machine_item` R1, Errors row 1"""
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine_item(db, item_data=MachineItemCreate(machine_id=MISSING, item_id=i1.id, qty=5), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine not found in this workspace"
    # Then 4
    assert len(db.new) == 0
    # Then 5
    db.flush()
    # Then 6
    assert written(db) == before


# [claude] MIM-C-02
def test_mim_c_02__a_machine_of_another_workspace_gets_the_same_404(db, w1, u2, i1, m9):
    """MIM-C-02 — a machine of another workspace gets the same 404.
    Rules: `create_machine_item` R1, Errors row 1"""
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine_item(db, item_data=MachineItemCreate(machine_id=m9.id, item_id=i1.id, qty=5), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine not found in this workspace"
    # Then 4
    assert len(db.new) == 0
    # Then 5
    db.flush()
    # Then 6
    assert written(db) == before


# [claude] MIM-C-03
def test_mim_c_03__machine_id_0_gets_the_same_404(db, w1, u2, i1):
    """MIM-C-03 — machine id 0 gets the same 404.
    Rules: `create_machine_item` R1, Errors row 1"""
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine_item(db, item_data=MachineItemCreate(machine_id=0, item_id=i1.id, qty=5), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine not found in this workspace"
    # Then 4
    assert len(db.new) == 0
    # Then 5
    db.flush()
    # Then 6
    assert written(db) == before


# [claude] MIM-C-04
def test_mim_c_04__a_soft_deleted_machine_is_refused(db, w1, u2, i1, mx):
    """MIM-C-04 — a soft-deleted machine is refused.
    Rules: `create_machine_item` R2, Errors row 2"""
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine_item(db, item_data=MachineItemCreate(machine_id=mx.id, item_id=i1.id, qty=5), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot add items to a deleted machine"
    # Then 4
    assert len(db.new) == 0
    # Then 5
    db.flush()
    # Then 6
    assert written(db) == before


# [claude] MIM-C-05
@pytest.mark.xfail(strict=True, reason="BUG-1076: Stock can be added to a machine of a soft-deleted factory")
def test_mim_c_05__a_live_machine_in_a_soft_deleted_factory_is_refused_like_a_deleted_machine(db, w1, u2, i1, mf):
    """MIM-C-05 — a live machine in a soft-deleted factory is refused like a deleted machine.
    Rules: `create_machine_item` R3 [BUG-1076], Errors row 2"""
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine_item(db, item_data=MachineItemCreate(machine_id=mf.id, item_id=i1.id, qty=5), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot add items to a deleted machine"
    # Then 4
    assert len(db.new) == 0
    # Then 5
    db.flush()
    # Then 6
    assert written(db) == before


# [claude] MIM-C-06
def test_mim_c_06__an_inactive_but_live_machine_is_accepted(db, w1, u2, i1, ma):
    """MIM-C-06 — an inactive-but-live machine is accepted.
    Rules: `create_machine_item` R4"""
    result = M.create_machine_item(db, item_data=MachineItemCreate(machine_id=ma.id, item_id=i1.id, qty=5), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.machine_id == ma.id
    assert row.qty == 5
    # Then 3
    assert count_rows(db, "machine_items") == 1


# [claude] MIM-C-07
def test_mim_c_07__a_machine_in_an_inactive_but_live_factory_is_accepted(db, w1, u2, i1, mn):
    """MIM-C-07 — a machine in an inactive-but-live factory is accepted.
    Rules: `create_machine_item` R4"""
    result = M.create_machine_item(db, item_data=MachineItemCreate(machine_id=mn.id, item_id=i1.id, qty=5), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.machine_id == mn.id
    assert row.qty == 5
    # Then 3
    assert count_rows(db, "machine_items") == 1


# [claude] MIM-C-08
@pytest.mark.xfail(strict=True, reason="BUG-1010: Machine stock accepts another workspace's item and shows its name")
def test_mim_c_08__a_missing_item_gets_the_same_404(db, w1, u2, m1):
    """MIM-C-08 — a missing item gets the same 404.
    Rules: `create_machine_item` R5 [BUG-1010], Errors row 3"""
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine_item(db, item_data=MachineItemCreate(machine_id=m1.id, item_id=MISSING, qty=5), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Item with ID 999999999 not found"
    # Then 4
    assert len(db.new) == 0
    # Then 5
    db.flush()
    # Then 6
    assert written(db) == before


# [claude] MIM-C-09
@pytest.mark.xfail(strict=True, reason="BUG-1010: Machine stock accepts another workspace's item and shows its name")
def test_mim_c_09__item_id_0_gets_the_same_404(db, w1, u2, m1):
    """MIM-C-09 — item id 0 gets the same 404.
    Rules: `create_machine_item` R5 [BUG-1010], Errors row 3"""
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine_item(db, item_data=MachineItemCreate(machine_id=m1.id, item_id=0, qty=5), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Item with ID 0 not found"
    # Then 4
    assert len(db.new) == 0
    # Then 5
    db.flush()
    # Then 6
    assert written(db) == before


# [claude] MIM-C-10
@pytest.mark.xfail(strict=True, reason="BUG-1010: Machine stock accepts another workspace's item and shows its name")
def test_mim_c_10__an_item_of_another_workspace_gets_the_same_404(db, w1, u2, i9, m1):
    """MIM-C-10 — an item of another workspace gets the same 404.
    Rules: `create_machine_item` R5 [BUG-1010], Errors row 3"""
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine_item(db, item_data=MachineItemCreate(machine_id=m1.id, item_id=i9.id, qty=5), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Item with ID {i9.id} not found"
    # Then 4
    assert len(db.new) == 0
    # Then 5
    db.flush()
    # Then 6
    assert written(db) == before


# [claude] MIM-C-11
@pytest.mark.xfail(strict=True, reason="BUG-1085: A removed catalog item can be added to a machine")
def test_mim_c_11__a_removed_item_of_the_workspace_is_refused(db, w1, u2, ix, m1):
    """MIM-C-11 — a removed item of the workspace is refused.
    Rules: `create_machine_item` R6 [BUG-1085], Errors row 4"""
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine_item(db, item_data=MachineItemCreate(machine_id=m1.id, item_id=ix.id, qty=5), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot add a removed item to a machine"
    # Then 4
    assert len(db.new) == 0
    # Then 5
    db.flush()
    # Then 6
    assert written(db) == before


# [claude] MIM-C-12
@pytest.mark.xfail(strict=True, reason="BUG-1085: A removed catalog item can be added to a machine")
def test_mim_c_12__the_removed_item_refusal_holds_with_qty_0(db, w1, u2, ix, m1):
    """MIM-C-12 — the removed-item refusal holds with qty 0.
    Rules: `create_machine_item` R6 [BUG-1085], Errors row 4"""
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine_item(db, item_data=MachineItemCreate(machine_id=m1.id, item_id=ix.id), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot add a removed item to a machine"
    # Then 4
    assert len(db.new) == 0
    # Then 5
    db.flush()
    # Then 6
    assert written(db) == before


# [claude] MIM-C-13
def test_mim_c_13__machine_check_first_a_missing_machine_with_a_missing_item_is_the_machine_s_404(db, w1, u2):
    """MIM-C-13 — machine check first: a missing machine with a missing item is the machine's 404.
    Rules: `create_machine_item` R1, R5, Errors row 1"""
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine_item(db, item_data=MachineItemCreate(machine_id=MISSING, item_id=MISSING, qty=5), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine not found in this workspace"
    # Then 4
    assert len(db.new) == 0
    # Then 5
    db.flush()
    # Then 6
    assert written(db) == before


# [claude] MIM-C-14
def test_mim_c_14__machine_check_first_a_deleted_machine_with_a_missing_item_is_the_400(db, w1, u2, mx):
    """MIM-C-14 — machine check first: a deleted machine with a missing item is the 400.
    Rules: `create_machine_item` R2, R5, Errors row 2"""
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine_item(db, item_data=MachineItemCreate(machine_id=mx.id, item_id=MISSING, qty=5), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot add items to a deleted machine"
    # Then 4
    assert len(db.new) == 0
    # Then 5
    db.flush()
    # Then 6
    assert written(db) == before


# [claude] MIM-C-15
def test_mim_c_15__machine_check_first_a_deleted_machine_with_a_removed_item_is_the_machine_s_400(db, w1, u2, ix, mx):
    """MIM-C-15 — machine check first: a deleted machine with a removed item is the machine's 400.
    Rules: `create_machine_item` R2, R6, Errors row 2"""
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine_item(db, item_data=MachineItemCreate(machine_id=mx.id, item_id=ix.id, qty=5), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot add items to a deleted machine"
    # Then 4
    assert len(db.new) == 0
    # Then 5
    db.flush()
    # Then 6
    assert written(db) == before


# [claude] MIM-C-16
@pytest.mark.xfail(strict=True, reason="BUG-1076: Stock can be added to a machine of a soft-deleted factory")
def test_mim_c_16__factory_check_before_the_item_check_a_deleted_factory_with_a_missing_item_is_the_400(db, w1, u2, mf):
    """MIM-C-16 — factory check before the item check: a deleted factory with a missing item is the 400.
    Rules: `create_machine_item` R3 [BUG-1076], R5, Errors row 2"""
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine_item(db, item_data=MachineItemCreate(machine_id=mf.id, item_id=MISSING, qty=5), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot add items to a deleted machine"
    # Then 4
    assert len(db.new) == 0
    # Then 5
    db.flush()
    # Then 6
    assert written(db) == before


# [claude] MIM-C-17
@pytest.mark.xfail(strict=True, reason="BUG-1010: Machine stock accepts another workspace's item and shows its name")
def test_mim_c_17__item_check_before_the_duplicate_check_another_workspace_s_item_already_on_the_machine_is_the_404(db, w1, u2, i9, m1, mk_stock):
    """MIM-C-17 — item check before the duplicate check: another workspace's item already on the machine is the 404.
    Rules: `create_machine_item` R5 [BUG-1010], R7, Errors row 3"""
    mi = mk_stock(m1, i9, qty=2)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine_item(db, item_data=MachineItemCreate(machine_id=m1.id, item_id=i9.id, qty=5), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Item with ID {i9.id} not found"
    # Then 4
    assert snap(db, mi) == before_mi
    # Then 5
    assert written(db) == before


# [claude] MIM-C-18
@pytest.mark.xfail(strict=True, reason="BUG-1085: A removed catalog item can be added to a machine")
def test_mim_c_18__removed_check_before_the_duplicate_check_a_removed_item_already_on_the_machine_is_the_400(db, w1, u2, ix, m1, mk_stock):
    """MIM-C-18 — removed check before the duplicate check: a removed item already on the machine is the 400.
    Rules: `create_machine_item` R6 [BUG-1085], R7, Errors row 4"""
    mi = mk_stock(m1, ix, qty=2)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine_item(db, item_data=MachineItemCreate(machine_id=m1.id, item_id=ix.id, qty=5), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot add a removed item to a machine"
    # Then 4
    assert snap(db, mi) == before_mi
    # Then 5
    assert written(db) == before


# [claude] MIM-C-19
def test_mim_c_19__a_row_for_the_pair_gets_the_409(db, w1, u2, i1, m1, mk_stock):
    """MIM-C-19 — a row for the pair gets the 409.
    Rules: `create_machine_item` R7, Errors row 5"""
    mi = mk_stock(m1, i1, qty=3)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine_item(db, item_data=MachineItemCreate(machine_id=m1.id, item_id=i1.id, qty=5), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "This item already exists on this machine. Update the existing record instead."
    # Then 4
    assert len(db.new) == 0
    # Then 5
    assert mi not in db.dirty
    # Then 6
    db.flush()
    # Then 7
    assert snap(db, mi) == before_mi
    # Then 8
    assert written(db) == before


# [claude] MIM-C-20
def test_mim_c_20__a_row_for_the_pair_with_qty_0_gets_the_409(db, w1, u2, i1, m1, mk_stock):
    """MIM-C-20 — a row for the pair with qty 0 gets the 409.
    Rules: `create_machine_item` R7, Errors row 5"""
    mi = mk_stock(m1, i1, qty=0)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine_item(db, item_data=MachineItemCreate(machine_id=m1.id, item_id=i1.id, qty=5), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "This item already exists on this machine. Update the existing record instead."
    # Then 4
    assert len(db.new) == 0
    # Then 5
    assert mi not in db.dirty
    # Then 6
    db.flush()
    # Then 7
    assert snap(db, mi) == before_mi
    # Then 8
    assert written(db) == before


# [claude] MIM-C-21
def test_mim_c_21__a_row_of_the_pair_on_an_inactive_machine_still_gets_the_409(db, w1, u2, i1, ma, mk_stock):
    """MIM-C-21 — a row of the pair on an inactive machine still gets the 409.
    Rules: `create_machine_item` R7, R4, Errors row 5"""
    mi = mk_stock(ma, i1, qty=3)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine_item(db, item_data=MachineItemCreate(machine_id=ma.id, item_id=i1.id, qty=5), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "This item already exists on this machine. Update the existing record instead."
    # Then 4
    assert snap(db, mi) == before_mi
    # Then 5
    assert written(db) == before


# [claude] MIM-C-22
def test_mim_c_22__the_same_pair_under_another_workspace_id_does_not_block(db, w1, w2, u2, i1, m1, mk_stock):
    """MIM-C-22 — the same pair under another workspace_id does not block.
    Rules: `create_machine_item` R7"""
    ot = mk_stock(m1, i1, qty=3, workspace_id=w2.id)
    before_ot = snap_before(db, ot)
    result = M.create_machine_item(db, item_data=MachineItemCreate(machine_id=m1.id, item_id=i1.id, qty=5), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.qty == 5
    # Then 3
    assert snap(db, ot) == before_ot
    # Then 4
    assert count_rows(db, "machine_items") == 2


# [claude] MIM-C-23
def test_mim_c_23__another_item_on_the_machine_does_not_block(db, w1, u2, i1, i2, m1, mk_stock):
    """MIM-C-23 — another item on the machine does not block.
    Rules: `create_machine_item` R7"""
    ot = mk_stock(m1, i2, qty=3)
    before_ot = snap_before(db, ot)
    result = M.create_machine_item(db, item_data=MachineItemCreate(machine_id=m1.id, item_id=i1.id, qty=5), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert snap(db, ot) == before_ot
    # Then 3
    assert count_rows(db, "machine_items") == 2


# [claude] MIM-C-24
def test_mim_c_24__the_item_on_another_machine_does_not_block(db, w1, u2, i1, m1, m2, mk_stock):
    """MIM-C-24 — the item on another machine does not block.
    Rules: `create_machine_item` R7"""
    ot = mk_stock(m2, i1, qty=3)
    before_ot = snap_before(db, ot)
    result = M.create_machine_item(db, item_data=MachineItemCreate(machine_id=m1.id, item_id=i1.id, qty=5), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert snap(db, ot) == before_ot
    # Then 3
    assert count_rows(db, "machine_items") == 2


# [claude] MIM-C-25
@pytest.mark.xfail(strict=True, reason="BUG-983: Machine stock can hold two rows for the same machine and item")
def test_mim_c_25__a_lost_race_gets_the_same_409_and_nothing_is_saved(db, w1, u2, i1, m1, mk_stock):
    """MIM-C-25 — a lost race gets the same 409 and nothing is saved.
    Rules: `create_machine_item` R8 [BUG-983], Errors row 5"""
    mi = mk_stock(m1, i1, qty=3)
    before_mi = snap_before(db, mi)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with patch.object(M.machine_item_dao, "get_by_machine_and_item", return_value=None):
            with db.begin_nested():
                M.create_machine_item(db, item_data=MachineItemCreate(machine_id=m1.id, item_id=i1.id, qty=5), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "This item already exists on this machine. Update the existing record instead."
    # Then 4
    assert count_rows(db, "machine_items", machine_id=m1.id, item_id=i1.id) == 1
    # Then 5
    assert snap(db, mi) == before_mi
    # Then 6
    assert count_rows(db, "machine_item_ledger") == 0
    # Then 7
    assert count_rows(db, "machine_activity_events") == 0


# [claude] MIM-C-26
def test_mim_c_26__the_row_carries_the_input_and_the_caller_s_workspace(db, w1, u2, i1, m1):
    """MIM-C-26 — the row carries the input and the caller's workspace.
    Rules: `create_machine_item` R9, Returns"""
    result = M.create_machine_item(db, item_data=MachineItemCreate(machine_id=m1.id, item_id=i1.id, qty=5, req_qty=7, defective_qty=1), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert isinstance(result, MachineItem)
    # Then 2
    assert result.id is not None
    # Then 3
    assert result.item_name == "Bolt M8"
    assert result.item_unit == "pcs"
    # Then 4
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.machine_id == m1.id
    assert row.item_id == i1.id
    # Then 5
    row = reread(db, result)
    assert row.qty == 5
    assert row.req_qty == 7
    assert row.defective_qty == 1
    # Then 6
    assert count_rows(db, "machine_items") == 1


# [claude] MIM-C-27
def test_mim_c_27__optional_fields_not_sent_stay_empty_and_qty_defaults_to_0(db, w1, u2, i1, m1):
    """MIM-C-27 — optional fields not sent stay empty and qty defaults to 0.
    Rules: `create_machine_item` R9, R11"""
    result = M.create_machine_item(db, item_data=MachineItemCreate(machine_id=m1.id, item_id=i1.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.qty == 0
    assert row.req_qty is None
    assert row.defective_qty is None


# [claude] MIM-C-28
def test_mim_c_28__qty_above_0_books_one_manual_add_entry(db, w1, u2, i1, m1):
    """MIM-C-28 — qty above 0 books one manual_add entry.
    Rules: `create_machine_item` R10"""
    result = M.create_machine_item(db, item_data=MachineItemCreate(machine_id=m1.id, item_id=i1.id, qty=5), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert len(entries_of(db, m1, i1)) == 1
    # Then 3
    row = entries_of(db, m1, i1)[-1]
    assert row.transaction_type == "manual_add"
    assert row.quantity == 5
    # Then 4
    row = entries_of(db, m1, i1)[-1]
    assert row.qty_before == 0
    assert row.qty_after == 5
    # Then 5
    row = entries_of(db, m1, i1)[-1]
    assert row.source_type == "manual"
    assert row.notes == "Initial machine inventory record created"
    # Then 6
    row = entries_of(db, m1, i1)[-1]
    assert row.performed_by == u2.id
    assert row.workspace_id == w1.id
    # Then 7
    row = entries_of(db, m1, i1)[-1]
    assert row.unit_cost == Decimal("0.00")
    assert row.total_cost == Decimal("0.00")
    # Then 8
    row = entries_of(db, m1, i1)[-1]
    assert row.value_before == Decimal("0.00")
    assert row.value_after == Decimal("0.00")
    # Then 9
    row = entries_of(db, m1, i1)[-1]
    assert row.avg_price_before == Decimal("0.00")
    assert row.avg_price_after == Decimal("0.00")


# [claude] MIM-C-29
def test_mim_c_29__qty_1_books_an_entry(db, w1, u2, i1, m1):
    """MIM-C-29 — qty 1 books an entry.
    Rules: `create_machine_item` R10"""
    result = M.create_machine_item(db, item_data=MachineItemCreate(machine_id=m1.id, item_id=i1.id, qty=1), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert len(entries_of(db, m1, i1)) == 1
    # Then 3
    row = entries_of(db, m1, i1)[-1]
    assert row.quantity == 1
    assert row.qty_after == 1


# [claude] MIM-C-30
def test_mim_c_30__qty_before_is_0_whatever_the_ledger_holds(db, w1, u2, i1, m1, mk_entry):
    """MIM-C-30 — qty_before is 0 whatever the ledger holds.
    Rules: `create_machine_item` R10"""
    lg = mk_entry(m1, i1, performed_at=T9, avg_price_after=Decimal("0.00"), qty_after=7)
    before_lg = snap_before(db, lg)
    result = M.create_machine_item(db, item_data=MachineItemCreate(machine_id=m1.id, item_id=i1.id, qty=4), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert len(entries_of(db, m1, i1)) == 2
    # Then 3
    row = entries_of(db, m1, i1)[-1]
    assert row.quantity == 4
    assert row.qty_before == 0
    assert row.qty_after == 4
    # Then 4
    assert snap(db, lg) == before_lg


# [claude] MIM-C-31
@pytest.mark.xfail(strict=True, reason="BUG-993: A manual stock change wipes the machine's cost")
def test_mim_c_31__the_opening_entry_takes_the_machine_s_current_average(db, w1, u2, i1, m1, mk_entry):
    """MIM-C-31 — the opening entry takes the machine's current average.
    Rules: `create_machine_item` R10, `_write_ledger_entry` R2 [BUG-993], R3, R4"""
    mk_entry(m1, i1, performed_at=T9, avg_price_after=Decimal("5.00"), qty_after=0)
    result = M.create_machine_item(db, item_data=MachineItemCreate(machine_id=m1.id, item_id=i1.id, qty=4), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = entries_of(db, m1, i1)[-1]
    assert row.unit_cost == Decimal("5.00")
    assert row.avg_price_before == Decimal("5.00")
    assert row.avg_price_after == Decimal("5.00")
    # Then 3
    row = entries_of(db, m1, i1)[-1]
    assert row.total_cost == Decimal("20.00")
    assert row.value_before == Decimal("0.00")
    assert row.value_after == Decimal("20.00")


# [claude] MIM-C-32
@pytest.mark.xfail(strict=True, reason="BUG-993: A manual stock change wipes the machine's cost")
def test_mim_c_32__a_row_removed_and_added_again_keeps_the_average(db, w1, u2, i1, m1, mk_stock, mk_entry):
    """MIM-C-32 — a row removed and added again keeps the average.
    Rules: `create_machine_item` R10, `_write_ledger_entry` R2 [BUG-993], `delete_machine_item` R10"""
    mi = mk_stock(m1, i1, qty=5)
    mk_entry(m1, i1, performed_at=T9, avg_price_after=Decimal("3.00"), qty_after=5, value_after=Decimal("15.00"))
    old_id = mi.id
    M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    db.flush()
    result = M.create_machine_item(db, item_data=MachineItemCreate(machine_id=m1.id, item_id=i1.id, qty=4), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id != old_id
    # Then 2
    row = entries_of(db, m1, i1)[-1]
    assert row.unit_cost == Decimal("3.00")
    assert row.avg_price_after == Decimal("3.00")
    # Then 3
    row = entries_of(db, m1, i1)[-1]
    assert row.total_cost == Decimal("12.00")
    assert row.value_after == Decimal("12.00")


# [claude] MIM-C-33
def test_mim_c_33__qty_0_books_no_entry(db, w1, u2, i1, m1):
    """MIM-C-33 — qty 0 books no entry.
    Rules: `create_machine_item` R11"""
    result = M.create_machine_item(db, item_data=MachineItemCreate(machine_id=m1.id, item_id=i1.id, qty=0), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert count_rows(db, "machine_item_ledger") == 0
    # Then 3
    rows = events_of(db, m1)
    assert len(rows) == 1


# [claude] MIM-C-34
def test_mim_c_34__qty_left_at_its_default_books_no_entry(db, w1, u2, i1, m1):
    """MIM-C-34 — qty left at its default books no entry.
    Rules: `create_machine_item` R11"""
    result = M.create_machine_item(db, item_data=MachineItemCreate(machine_id=m1.id, item_id=i1.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert count_rows(db, "machine_item_ledger") == 0
    # Then 3
    rows = events_of(db, m1)
    assert len(rows) == 1


# [claude] MIM-C-35
@pytest.mark.xfail(strict=True, reason="BUG-1079: Negative machine stock quantities are accepted")
def test_mim_c_35__a_negative_qty_is_rejected_by_machineitemcreate(db):
    """MIM-C-35 — a negative qty is rejected by MachineItemCreate.
    Rules: `create_machine_item` R12 [BUG-1079], Errors row 6"""
    # Then 1
    with pytest.raises(ValidationError):
        MachineItemCreate(machine_id=1, item_id=1, qty=-1)
    # Then 2
    assert count_rows(db, "machine_items") == 0


# [claude] MIM-C-36
def test_mim_c_36__qty_0_is_accepted_by_machineitemcreate(db):
    """MIM-C-36 — qty 0 is accepted by MachineItemCreate.
    Rules: `create_machine_item` R12"""
    result = MachineItemCreate(machine_id=1, item_id=1, qty=0)

    # Then 1
    assert result.qty == 0


# [claude] MIM-C-37
@pytest.mark.xfail(strict=True, reason="BUG-1078: A machine stock quantity beyond 32 bits crashes")
def test_mim_c_37__a_qty_of_2147483648_is_rejected_by_machineitemcreate(db):
    """MIM-C-37 — a qty of 2147483648 is rejected by MachineItemCreate.
    Rules: `create_machine_item` R14 [BUG-1078], Errors row 6"""
    # Then 1
    with pytest.raises(ValidationError):
        MachineItemCreate(machine_id=1, item_id=1, qty=2147483648)
    # Then 2
    assert count_rows(db, "machine_items") == 0


# [claude] MIM-C-38
@pytest.mark.xfail(strict=True, reason="BUG-1079: Negative machine stock quantities are accepted")
def test_mim_c_38__a_negative_req_qty_is_rejected_by_machineitemcreate(db):
    """MIM-C-38 — a negative req_qty is rejected by MachineItemCreate.
    Rules: `create_machine_item` R13 [BUG-1079], Errors row 6"""
    # Then 1
    with pytest.raises(ValidationError):
        MachineItemCreate(machine_id=1, item_id=1, req_qty=-1)
    # Then 2
    assert count_rows(db, "machine_items") == 0


# [claude] MIM-C-39
def test_mim_c_39__req_qty_0_is_accepted_by_machineitemcreate(db):
    """MIM-C-39 — req_qty 0 is accepted by MachineItemCreate.
    Rules: `create_machine_item` R13"""
    result = MachineItemCreate(machine_id=1, item_id=1, req_qty=0)

    # Then 1
    assert result.req_qty == 0


# [claude] MIM-C-40
@pytest.mark.xfail(strict=True, reason="BUG-1078: A machine stock quantity beyond 32 bits crashes")
def test_mim_c_40__a_req_qty_of_2147483648_is_rejected_by_machineitemcreate(db):
    """MIM-C-40 — a req_qty of 2147483648 is rejected by MachineItemCreate.
    Rules: `create_machine_item` R14 [BUG-1078], Errors row 6"""
    # Then 1
    with pytest.raises(ValidationError):
        MachineItemCreate(machine_id=1, item_id=1, req_qty=2147483648)
    # Then 2
    assert count_rows(db, "machine_items") == 0


# [claude] MIM-C-41
@pytest.mark.xfail(strict=True, reason="BUG-1079: Negative machine stock quantities are accepted")
def test_mim_c_41__a_negative_defective_qty_is_rejected_by_machineitemcreate(db):
    """MIM-C-41 — a negative defective_qty is rejected by MachineItemCreate.
    Rules: `create_machine_item` R13 [BUG-1079], Errors row 6"""
    # Then 1
    with pytest.raises(ValidationError):
        MachineItemCreate(machine_id=1, item_id=1, defective_qty=-1)
    # Then 2
    assert count_rows(db, "machine_items") == 0


# [claude] MIM-C-42
def test_mim_c_42__defective_qty_0_is_accepted_by_machineitemcreate(db):
    """MIM-C-42 — defective_qty 0 is accepted by MachineItemCreate.
    Rules: `create_machine_item` R13"""
    result = MachineItemCreate(machine_id=1, item_id=1, defective_qty=0)

    # Then 1
    assert result.defective_qty == 0


# [claude] MIM-C-43
@pytest.mark.xfail(strict=True, reason="BUG-1078: A machine stock quantity beyond 32 bits crashes")
def test_mim_c_43__a_defective_qty_of_2147483648_is_rejected_by_machineitemcreate(db):
    """MIM-C-43 — a defective_qty of 2147483648 is rejected by MachineItemCreate.
    Rules: `create_machine_item` R14 [BUG-1078], Errors row 6"""
    # Then 1
    with pytest.raises(ValidationError):
        MachineItemCreate(machine_id=1, item_id=1, defective_qty=2147483648)
    # Then 2
    assert count_rows(db, "machine_items") == 0


# [claude] MIM-C-44
def test_mim_c_44__req_qty_none_is_accepted_by_machineitemcreate(db):
    """MIM-C-44 — req_qty None is accepted by MachineItemCreate.
    Rules: `create_machine_item` R13"""
    result = MachineItemCreate(machine_id=1, item_id=1, req_qty=None)

    # Then 1
    assert result.req_qty is None


# [claude] MIM-C-45
def test_mim_c_45__defective_qty_none_is_accepted_by_machineitemcreate(db):
    """MIM-C-45 — defective_qty None is accepted by MachineItemCreate.
    Rules: `create_machine_item` R13"""
    result = MachineItemCreate(machine_id=1, item_id=1, defective_qty=None)

    # Then 1
    assert result.defective_qty is None


# [claude] MIM-C-46
def test_mim_c_46__machineitembase_has_no_minimum(db):
    """MIM-C-46 — MachineItemBase has no minimum.
    Rules: `create_machine_item` R12"""
    result = MachineItemBase(machine_id=1, item_id=1, qty=-1)

    # Then 1
    assert result.qty == -1


# [claude] MIM-C-47
def test_mim_c_47__2147483647_is_accepted_and_stored_on_all_three_fields(db, w1, u2, i1, m1):
    """MIM-C-47 — 2147483647 is accepted and stored on all three fields.
    Rules: `create_machine_item` R14"""
    result = M.create_machine_item(db, item_data=MachineItemCreate(machine_id=m1.id, item_id=i1.id, qty=2147483647, req_qty=2147483647, defective_qty=2147483647), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.qty == 2147483647
    assert row.req_qty == 2147483647
    assert row.defective_qty == 2147483647
    # Then 3
    row = entries_of(db, m1, i1)[-1]
    assert row.quantity == 2147483647


# [claude] MIM-C-48
def test_mim_c_48__one_item_added_event_with_qty_above_0(db, w1, u2, i1, m1):
    """MIM-C-48 — one item_added event with qty above 0.
    Rules: `create_machine_item` R15"""
    result = M.create_machine_item(db, item_data=MachineItemCreate(machine_id=m1.id, item_id=i1.id, qty=5), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    rows = events_of(db, m1)
    assert len(rows) == 1
    # Then 3
    assert rows[0].event_type == "item_added"
    assert rows[0].description == "Item added: Bolt M8"
    # Then 4
    assert rows[0].performed_by == u2.id
    assert rows[0].workspace_id == w1.id
    assert rows[0].machine_id == m1.id
    # Then 5
    assert rows[0].metadata_json == {"item_id": i1.id, "item_name": "Bolt M8", "machine_item_id": result.id, "quantity": 5}


# [claude] MIM-C-49
def test_mim_c_49__one_item_added_event_with_qty_0(db, w1, u2, i2, m1):
    """MIM-C-49 — one item_added event with qty 0.
    Rules: `create_machine_item` R15"""
    result = M.create_machine_item(db, item_data=MachineItemCreate(machine_id=m1.id, item_id=i2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    rows = events_of(db, m1)
    assert len(rows) == 1
    # Then 3
    assert rows[0].event_type == "item_added"
    assert rows[0].description == "Item added: Washer Ten"
    # Then 4
    assert rows[0].metadata_json == {"item_id": i2.id, "item_name": "Washer Ten", "machine_item_id": result.id, "quantity": 0}


# [claude] MIM-C-50
def test_mim_c_50__an_unknown_user_with_qty_above_0_fails_on_the_ledger(db, w1, i1, m1):
    """MIM-C-50 — an unknown user with qty above 0 fails on the ledger.
    Rules: `create_machine_item` R16, Errors row 7"""
    before = written(db)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            M.create_machine_item(db, item_data=MachineItemCreate(machine_id=m1.id, item_id=i1.id, qty=5), workspace_id=w1.id, user_id=MISSING)
    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert exc.value.orig.diag.constraint_name == "machine_item_ledger_performed_by_fkey"
    # Then 4
    assert written(db) == before


# [claude] MIM-C-51
def test_mim_c_51__an_unknown_user_with_qty_0_fails_on_the_activity_entry(db, w1, i1, m1):
    """MIM-C-51 — an unknown user with qty 0 fails on the activity entry.
    Rules: `create_machine_item` R16, Errors row 7"""
    before = written(db)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            M.create_machine_item(db, item_data=MachineItemCreate(machine_id=m1.id, item_id=i1.id, qty=0), workspace_id=w1.id, user_id=MISSING)
    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert exc.value.orig.diag.constraint_name == "machine_activity_events_performed_by_fkey"
    # Then 4
    assert written(db) == before


# [claude] MIM-C-52
def test_mim_c_52__the_create_is_flushed_but_not_committed(db, w1, u2, i1, m1, monkeypatch):
    """MIM-C-52 — the create is flushed but not committed.
    Rules: `create_machine_item` R17"""
    sp = db.begin_nested()
    spy = commit_spy(db, monkeypatch)
    result = M.create_machine_item(db, item_data=MachineItemCreate(machine_id=m1.id, item_id=i1.id, qty=5), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert count_rows(db, "machine_items") == 1
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert count_rows(db, "machine_activity_events") == 1
    # Then 5
    sp.rollback()
    assert count_rows(db, "machine_items") == 0
    # Then 6
    assert count_rows(db, "machine_item_ledger") == 0
    # Then 7
    assert count_rows(db, "machine_activity_events") == 0
    # Then 8
    spy.assert_not_called()


# [claude] MIM-U-01
def test_mim_u_01__a_row_of_another_workspace_gets_the_404(db, w2, u2, i1, m1, mk_stock):
    """MIM-U-01 — a row of another workspace gets the 404.
    Rules: `update_machine_item` R1, Errors row 1"""
    mi = mk_stock(m1, i1, qty=5)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(qty=12), workspace_id=w2.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine item not found"
    # Then 4
    assert mi not in db.dirty
    # Then 5
    assert mi not in db.deleted
    # Then 6
    db.flush()
    # Then 7
    assert snap(db, mi) == before_mi
    # Then 8
    assert written(db) == before


# [claude] MIM-U-02
def test_mim_u_02__an_unknown_id_gets_the_404(db, w1, u2, i1, m1, mk_stock):
    """MIM-U-02 — an unknown id gets the 404.
    Rules: `update_machine_item` R1, Errors row 1"""
    mi = mk_stock(m1, i1, qty=5)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine_item(db, machine_item_id=MISSING, item_data=MachineItemUpdate(qty=12), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine item not found"
    # Then 4
    assert mi not in db.dirty
    # Then 5
    assert mi not in db.deleted
    # Then 6
    db.flush()
    # Then 7
    assert snap(db, mi) == before_mi
    # Then 8
    assert written(db) == before


# [claude] MIM-U-03
def test_mim_u_03__id_0_gets_the_404(db, w1, u2, i1, m1, mk_stock):
    """MIM-U-03 — id 0 gets the 404.
    Rules: `update_machine_item` R1, Errors row 1"""
    mi = mk_stock(m1, i1, qty=5)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine_item(db, machine_item_id=0, item_data=MachineItemUpdate(qty=12), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine item not found"
    # Then 4
    assert mi not in db.dirty
    # Then 5
    assert mi not in db.deleted
    # Then 6
    db.flush()
    # Then 7
    assert snap(db, mi) == before_mi
    # Then 8
    assert written(db) == before


# [claude] MIM-U-04
@pytest.mark.xfail(strict=True, reason="BUG-1083: Stock on a deleted machine can still be edited")
def test_mim_u_04__a_row_of_a_soft_deleted_machine_is_refused(db, w1, u2, i1, mx, mk_stock):
    """MIM-U-04 — a row of a soft-deleted machine is refused.
    Rules: `update_machine_item` R2 [BUG-1083], Errors row 2"""
    mi = mk_stock(mx, i1, qty=5)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(qty=12), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update items of a deleted machine"
    # Then 4
    assert mi not in db.dirty
    # Then 5
    assert mi not in db.deleted
    # Then 6
    db.flush()
    # Then 7
    assert snap(db, mi) == before_mi
    # Then 8
    assert written(db) == before


# [claude] MIM-U-05
@pytest.mark.xfail(strict=True, reason="BUG-1083: Stock on a deleted machine can still be edited")
def test_mim_u_05__a_row_of_a_soft_deleted_machine_is_refused_for_a_target_change_alone(db, w1, u2, i1, mx, mk_stock):
    """MIM-U-05 — a row of a soft-deleted machine is refused for a target change alone.
    Rules: `update_machine_item` R2 [BUG-1083], Errors row 2"""
    mi = mk_stock(mx, i1, qty=5)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(req_qty=3), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update items of a deleted machine"
    # Then 4
    assert mi not in db.dirty
    # Then 5
    assert mi not in db.deleted
    # Then 6
    db.flush()
    # Then 7
    assert snap(db, mi) == before_mi
    # Then 8
    assert written(db) == before


# [claude] MIM-U-06
@pytest.mark.xfail(strict=True, reason="BUG-1083: Stock on a deleted machine can still be edited")
def test_mim_u_06__a_row_of_a_soft_deleted_machine_is_refused_with_no_field_sent(db, w1, u2, i1, mx, mk_stock):
    """MIM-U-06 — a row of a soft-deleted machine is refused with no field sent.
    Rules: `update_machine_item` R2 [BUG-1083], Errors row 2"""
    mi = mk_stock(mx, i1, qty=5)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update items of a deleted machine"
    # Then 4
    assert mi not in db.dirty
    # Then 5
    assert mi not in db.deleted
    # Then 6
    db.flush()
    # Then 7
    assert snap(db, mi) == before_mi
    # Then 8
    assert written(db) == before


# [claude] MIM-U-07
@pytest.mark.xfail(strict=True, reason="BUG-1083: Stock on a deleted machine can still be edited")
def test_mim_u_07__a_row_of_a_soft_deleted_machine_is_refused_before_an_unknown_user_matters(db, w1, i1, mx, mk_stock):
    """MIM-U-07 — a row of a soft-deleted machine is refused before an unknown user matters.
    Rules: `update_machine_item` R2 [BUG-1083], R16, Errors row 2"""
    mi = mk_stock(mx, i1, qty=5)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(qty=12), workspace_id=w1.id, user_id=MISSING)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update items of a deleted machine"
    # Then 4
    assert mi not in db.dirty
    # Then 5
    assert mi not in db.deleted
    # Then 6
    db.flush()
    # Then 7
    assert snap(db, mi) == before_mi
    # Then 8
    assert written(db) == before


# [claude] MIM-U-08
@pytest.mark.xfail(strict=True, reason="BUG-1083: Stock on a deleted machine can still be edited")
def test_mim_u_08__a_row_of_a_machine_in_a_soft_deleted_factory_is_refused(db, w1, u2, i1, mf, mk_stock):
    """MIM-U-08 — a row of a machine in a soft-deleted factory is refused.
    Rules: `update_machine_item` R2 [BUG-1083], Errors row 2"""
    mi = mk_stock(mf, i1, qty=5)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(qty=12), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update items of a deleted machine"
    # Then 4
    assert mi not in db.dirty
    # Then 5
    assert mi not in db.deleted
    # Then 6
    db.flush()
    # Then 7
    assert snap(db, mi) == before_mi
    # Then 8
    assert written(db) == before


# [claude] MIM-U-09
@pytest.mark.xfail(strict=True, reason="BUG-1083: Stock on a deleted machine can still be edited")
def test_mim_u_09__a_row_of_a_machine_in_a_soft_deleted_factory_is_refused_for_a_target_change_alone(db, w1, u2, i1, mf, mk_stock):
    """MIM-U-09 — a row of a machine in a soft-deleted factory is refused for a target change alone.
    Rules: `update_machine_item` R2 [BUG-1083], Errors row 2"""
    mi = mk_stock(mf, i1, qty=5)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(req_qty=3), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update items of a deleted machine"
    # Then 4
    assert mi not in db.dirty
    # Then 5
    assert mi not in db.deleted
    # Then 6
    db.flush()
    # Then 7
    assert snap(db, mi) == before_mi
    # Then 8
    assert written(db) == before


# [claude] MIM-U-10
@pytest.mark.xfail(strict=True, reason="BUG-1083: Stock on a deleted machine can still be edited")
def test_mim_u_10__a_row_of_a_machine_in_a_soft_deleted_factory_is_refused_with_no_field_sent(db, w1, u2, i1, mf, mk_stock):
    """MIM-U-10 — a row of a machine in a soft-deleted factory is refused with no field sent.
    Rules: `update_machine_item` R2 [BUG-1083], Errors row 2"""
    mi = mk_stock(mf, i1, qty=5)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update items of a deleted machine"
    # Then 4
    assert mi not in db.dirty
    # Then 5
    assert mi not in db.deleted
    # Then 6
    db.flush()
    # Then 7
    assert snap(db, mi) == before_mi
    # Then 8
    assert written(db) == before


# [claude] MIM-U-11
@pytest.mark.xfail(strict=True, reason="BUG-1083: Stock on a deleted machine can still be edited")
def test_mim_u_11__a_row_of_a_machine_in_a_soft_deleted_factory_is_refused_before_an_unknown_user_matters(db, w1, i1, mf, mk_stock):
    """MIM-U-11 — a row of a machine in a soft-deleted factory is refused before an unknown user matters.
    Rules: `update_machine_item` R2 [BUG-1083], R16, Errors row 2"""
    mi = mk_stock(mf, i1, qty=5)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(qty=12), workspace_id=w1.id, user_id=MISSING)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update items of a deleted machine"
    # Then 4
    assert mi not in db.dirty
    # Then 5
    assert mi not in db.deleted
    # Then 6
    db.flush()
    # Then 7
    assert snap(db, mi) == before_mi
    # Then 8
    assert written(db) == before


# [claude] MIM-U-12
def test_mim_u_12__a_row_of_an_inactive_but_live_machine_is_updated(db, w1, u2, i1, ma, mk_stock):
    """MIM-U-12 — a row of an inactive-but-live machine is updated.
    Rules: `update_machine_item` R2"""
    mi = mk_stock(ma, i1, qty=5)
    result = M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(qty=12), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is mi
    # Then 2
    row = reread(db, mi)
    assert row.qty == 12
    # Then 3
    assert len(entries_of(db, ma, i1)) == 1


# [claude] MIM-U-13
def test_mim_u_13__a_row_of_a_machine_in_an_inactive_but_live_factory_is_updated(db, w1, u2, i1, mn, mk_stock):
    """MIM-U-13 — a row of a machine in an inactive-but-live factory is updated.
    Rules: `update_machine_item` R2"""
    mi = mk_stock(mn, i1, qty=5)
    result = M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(qty=12), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is mi
    # Then 2
    row = reread(db, mi)
    assert row.qty == 12
    # Then 3
    assert len(entries_of(db, mn, i1)) == 1


# [claude] MIM-U-14
def test_mim_u_14__a_row_of_a_removed_item_is_updated_like_any_other(db, w1, u2, ix, m1, mk_stock):
    """MIM-U-14 — a row of a removed item is updated like any other.
    Rules: `update_machine_item` R3, R8, R12"""
    mi = mk_stock(m1, ix, qty=5)
    result = M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(qty=12), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is mi
    # Then 2
    row = reread(db, mi)
    assert row.qty == 12
    # Then 3
    assert len(entries_of(db, m1, ix)) == 1
    # Then 4
    rows = events_of(db, m1, event_type="inventory_adjusted")
    assert len(rows) == 1
    # Then 5
    rows = events_of(db, m1, event_type="item_updated")
    assert len(rows) == 1
    # Then 6
    [row] = events_of(db, m1, event_type="item_updated")
    assert row.description == "Item updated: Old Rivet"


# [claude] MIM-U-15
@pytest.mark.xfail(strict=True, reason="BUG-1072: Manual machine stock edit does not lock the row")
def test_mim_u_15__the_row_is_read_for_update(db, w1, u2, i1, m1, mk_stock):
    """MIM-U-15 — the row is read FOR UPDATE.
    Rules: `update_machine_item` R4 [BUG-1072]"""
    mi = mk_stock(m1, i1, qty=5)
    with record_sql(db) as sql_log:
        result = M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(qty=12), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is mi
    # Then 2
    assert any("FOR UPDATE" in s for s in sql_log if s.lstrip().startswith("SELECT") and "FROM machine_items" in s)


# [claude] MIM-U-16
def test_mim_u_16__qty_alone_is_written_the_omitted_fields_stay(db, w1, u2, i1, m1, mk_stock):
    """MIM-U-16 — qty alone is written, the omitted fields stay.
    Rules: `update_machine_item` R5, R6"""
    mi = mk_stock(m1, i1, qty=5, req_qty=7, defective_qty=1)
    result = M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(qty=12), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is mi
    # Then 2
    row = reread(db, mi)
    assert row.qty == 12
    # Then 3
    row = reread(db, mi)
    assert row.req_qty == 7
    assert row.defective_qty == 1


# [claude] MIM-U-17
def test_mim_u_17__req_qty_alone_is_written_the_omitted_fields_stay(db, w1, u2, i1, m1, mk_stock):
    """MIM-U-17 — req_qty alone is written, the omitted fields stay.
    Rules: `update_machine_item` R5, R6"""
    mi = mk_stock(m1, i1, qty=5, req_qty=7, defective_qty=1)
    result = M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(req_qty=3), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is mi
    # Then 2
    row = reread(db, mi)
    assert row.req_qty == 3
    # Then 3
    row = reread(db, mi)
    assert row.qty == 5
    assert row.defective_qty == 1


# [claude] MIM-U-18
def test_mim_u_18__defective_qty_alone_is_written_the_omitted_fields_stay(db, w1, u2, i1, m1, mk_stock):
    """MIM-U-18 — defective_qty alone is written, the omitted fields stay.
    Rules: `update_machine_item` R5, R6"""
    mi = mk_stock(m1, i1, qty=5, req_qty=7, defective_qty=1)
    result = M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(defective_qty=2), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is mi
    # Then 2
    row = reread(db, mi)
    assert row.defective_qty == 2
    # Then 3
    row = reread(db, mi)
    assert row.qty == 5
    assert row.req_qty == 7


# [claude] MIM-U-19
def test_mim_u_19__all_three_fields_together_are_written(db, w1, u2, i1, m1, mk_stock):
    """MIM-U-19 — all three fields together are written.
    Rules: `update_machine_item` R5"""
    mi = mk_stock(m1, i1, qty=5, req_qty=7, defective_qty=1)
    result = M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(qty=12, req_qty=3, defective_qty=2), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is mi
    # Then 2
    row = reread(db, mi)
    assert row.qty == 12
    assert row.req_qty == 3
    assert row.defective_qty == 2


# [claude] MIM-U-20
def test_mim_u_20__qty_0_is_a_value_and_is_applied(db, w1, u2, i1, m1, mk_stock):
    """MIM-U-20 — qty 0 is a value and is applied.
    Rules: `update_machine_item` R5, R12"""
    mi = mk_stock(m1, i1, qty=5, req_qty=7, defective_qty=1)
    result = M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(qty=0), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is mi
    # Then 2
    row = reread(db, mi)
    assert row.qty == 0
    # Then 3
    rows = events_of(db, m1, event_type="item_updated")
    assert len(rows) == 1
    # Then 4
    assert rows[0].metadata_json == {"item_id": i1.id, "item_name": "Bolt M8", "machine_item_id": mi.id, "changes": [{"field": "qty", "label": "Quantity", "from_value": "5", "to_value": "0"}]}


# [claude] MIM-U-21
def test_mim_u_21__req_qty_0_is_a_value_and_is_applied(db, w1, u2, i1, m1, mk_stock):
    """MIM-U-21 — req_qty 0 is a value and is applied.
    Rules: `update_machine_item` R5, R12"""
    mi = mk_stock(m1, i1, qty=5, req_qty=7, defective_qty=1)
    result = M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(req_qty=0), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is mi
    # Then 2
    row = reread(db, mi)
    assert row.req_qty == 0
    # Then 3
    rows = events_of(db, m1, event_type="item_updated")
    assert len(rows) == 1
    # Then 4
    assert rows[0].metadata_json == {"item_id": i1.id, "item_name": "Bolt M8", "machine_item_id": mi.id, "changes": [{"field": "req_qty", "label": "Required quantity", "from_value": "7", "to_value": "0"}]}


# [claude] MIM-U-22
def test_mim_u_22__defective_qty_0_is_a_value_and_is_applied(db, w1, u2, i1, m1, mk_stock):
    """MIM-U-22 — defective_qty 0 is a value and is applied.
    Rules: `update_machine_item` R5, R12"""
    mi = mk_stock(m1, i1, qty=5, req_qty=7, defective_qty=1)
    result = M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(defective_qty=0), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is mi
    # Then 2
    row = reread(db, mi)
    assert row.defective_qty == 0
    # Then 3
    rows = events_of(db, m1, event_type="item_updated")
    assert len(rows) == 1
    # Then 4
    assert rows[0].metadata_json == {"item_id": i1.id, "item_name": "Bolt M8", "machine_item_id": mi.id, "changes": [{"field": "defective_qty", "label": "Defective quantity", "from_value": "1", "to_value": "0"}]}


# [claude] MIM-U-23
@pytest.mark.xfail(strict=True, reason="BUG-1075: A machine's target and defect count cannot be cleared")
def test_mim_u_23__an_explicit_null_clears_req_qty_and_records_to_value_none(db, w1, u2, i1, m1, mk_stock):
    """MIM-U-23 — an explicit null clears req_qty and records to_value None.
    Rules: `update_machine_item` R6 [BUG-1075], R12"""
    mi = mk_stock(m1, i1, qty=5, req_qty=7, defective_qty=1)
    result = M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(req_qty=None), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is mi
    # Then 2
    row = reread(db, mi)
    assert row.req_qty is None
    # Then 3
    row = reread(db, mi)
    assert row.qty == 5
    assert row.defective_qty == 1
    # Then 4
    assert count_rows(db, "machine_item_ledger") == 0
    # Then 5
    rows = events_of(db, m1)
    assert len(rows) == 1
    # Then 6
    assert rows[0].metadata_json == {"item_id": i1.id, "item_name": "Bolt M8", "machine_item_id": mi.id, "changes": [{"field": "req_qty", "label": "Required quantity", "from_value": "7", "to_value": None}]}


# [claude] MIM-U-24
@pytest.mark.xfail(strict=True, reason="BUG-1075: A machine's target and defect count cannot be cleared")
def test_mim_u_24__an_explicit_null_clears_defective_qty_and_records_to_value_none(db, w1, u2, i1, m1, mk_stock):
    """MIM-U-24 — an explicit null clears defective_qty and records to_value None.
    Rules: `update_machine_item` R6 [BUG-1075], R12"""
    mi = mk_stock(m1, i1, qty=5, req_qty=7, defective_qty=1)
    result = M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(defective_qty=None), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is mi
    # Then 2
    row = reread(db, mi)
    assert row.defective_qty is None
    # Then 3
    row = reread(db, mi)
    assert row.qty == 5
    assert row.req_qty == 7
    # Then 4
    assert count_rows(db, "machine_item_ledger") == 0
    # Then 5
    rows = events_of(db, m1)
    assert len(rows) == 1
    # Then 6
    assert rows[0].metadata_json == {"item_id": i1.id, "item_name": "Bolt M8", "machine_item_id": mi.id, "changes": [{"field": "defective_qty", "label": "Defective quantity", "from_value": "1", "to_value": None}]}


# [claude] MIM-U-25
@pytest.mark.xfail(strict=True, reason="BUG-1075: A machine's target and defect count cannot be cleared")
def test_mim_u_25__null_on_one_field_next_to_a_value_on_another(db, w1, u2, i1, m1, mk_stock):
    """MIM-U-25 — null on one field next to a value on another.
    Rules: `update_machine_item` R6 [BUG-1075], R5"""
    mi = mk_stock(m1, i1, qty=5, req_qty=7, defective_qty=1)
    result = M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(req_qty=None, defective_qty=2), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is mi
    # Then 2
    row = reread(db, mi)
    assert row.req_qty is None
    # Then 3
    row = reread(db, mi)
    assert row.defective_qty == 2
    # Then 4
    rows = events_of(db, m1)
    assert len(rows) == 1
    # Then 5
    assert rows[0].metadata_json == {"item_id": i1.id, "item_name": "Bolt M8", "machine_item_id": mi.id, "changes": [{"field": "req_qty", "label": "Required quantity", "from_value": "7", "to_value": None}, {"field": "defective_qty", "label": "Defective quantity", "from_value": "1", "to_value": "2"}]}


# [claude] MIM-U-26
@pytest.mark.xfail(strict=True, reason="BUG-1075: A machine's target and defect count cannot be cleared")
def test_mim_u_26__a_null_qty_is_rejected_by_machineitemupdate(db, i1, m1, mk_stock):
    """MIM-U-26 — a null qty is rejected by MachineItemUpdate.
    Rules: `update_machine_item` R6 [BUG-1075], Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    before_mi = snap_before(db, mi)
    # Then 1
    with pytest.raises(ValidationError):
        MachineItemUpdate(qty=None)
    # Then 2
    assert snap(db, mi) == before_mi


# [claude] MIM-U-27
def test_mim_u_27__no_field_sent_no_entry_no_event(db, w1, u2, i1, m1, mk_stock):
    """MIM-U-27 — no field sent: no entry, no event.
    Rules: `update_machine_item` R7, R6"""
    mi = mk_stock(m1, i1, qty=5, req_qty=7, defective_qty=1)
    before_mi = snap_before(db, mi)
    before = written(db)
    result = M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is mi
    # Then 2
    assert mi not in db.dirty
    # Then 3
    assert snap(db, mi) == before_mi
    # Then 4
    assert written(db) == before


# [claude] MIM-U-28
def test_mim_u_28__no_field_sent_by_an_unknown_user_raises_nothing(db, w1, i1, m1, mk_stock):
    """MIM-U-28 — no field sent by an unknown user raises nothing.
    Rules: `update_machine_item` R7"""
    mi = mk_stock(m1, i1, qty=5, req_qty=7, defective_qty=1)
    before_mi = snap_before(db, mi)
    before = written(db)
    result = M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(), workspace_id=w1.id, user_id=MISSING)

    # Then 1
    assert result is mi
    # Then 2
    assert snap(db, mi) == before_mi
    # Then 3
    assert written(db) == before


# [claude] MIM-U-29
def test_mim_u_29__the_same_values_no_entry_no_event(db, w1, u2, i1, m1, mk_stock):
    """MIM-U-29 — the same values: no entry, no event.
    Rules: `update_machine_item` R7"""
    mi = mk_stock(m1, i1, qty=5, req_qty=7, defective_qty=1)
    before_mi = snap_before(db, mi)
    before = written(db)
    result = M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(qty=5, req_qty=7, defective_qty=1), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is mi
    # Then 2
    assert mi not in db.dirty
    # Then 3
    assert snap(db, mi) == before_mi
    # Then 4
    assert written(db) == before


# [claude] MIM-U-30
def test_mim_u_30__the_same_values_by_an_unknown_user_raises_nothing(db, w1, i1, m1, mk_stock):
    """MIM-U-30 — the same values by an unknown user raises nothing.
    Rules: `update_machine_item` R7"""
    mi = mk_stock(m1, i1, qty=5, req_qty=7, defective_qty=1)
    before_mi = snap_before(db, mi)
    before = written(db)
    result = M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(qty=5, req_qty=7, defective_qty=1), workspace_id=w1.id, user_id=MISSING)

    # Then 1
    assert result is mi
    # Then 2
    assert snap(db, mi) == before_mi
    # Then 3
    assert written(db) == before


# [claude] MIM-U-31
def test_mim_u_31__null_on_a_field_already_empty_no_entry_no_event(db, w1, u2, i1, m1, mk_stock):
    """MIM-U-31 — null on a field already empty: no entry, no event.
    Rules: `update_machine_item` R7"""
    mi = mk_stock(m1, i1, qty=5)
    before_mi = snap_before(db, mi)
    before = written(db)
    result = M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(req_qty=None), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is mi
    # Then 2
    assert mi not in db.dirty
    # Then 3
    assert snap(db, mi) == before_mi
    # Then 4
    assert written(db) == before


# [claude] MIM-U-32
def test_mim_u_32__null_on_a_field_already_empty_by_an_unknown_user_raises_nothing(db, w1, i1, m1, mk_stock):
    """MIM-U-32 — null on a field already empty by an unknown user raises nothing.
    Rules: `update_machine_item` R7"""
    mi = mk_stock(m1, i1, qty=5)
    before_mi = snap_before(db, mi)
    before = written(db)
    result = M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(req_qty=None), workspace_id=w1.id, user_id=MISSING)

    # Then 1
    assert result is mi
    # Then 2
    assert snap(db, mi) == before_mi
    # Then 3
    assert written(db) == before


# [claude] MIM-U-33
def test_mim_u_33__a_qty_change_up_5_to_12_books_one_adjustment(db, w1, u2, i1, m1, mk_stock):
    """MIM-U-33 — a qty change up (5 to 12) books one adjustment.
    Rules: `update_machine_item` R8"""
    mi = mk_stock(m1, i1, qty=5)
    result = M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(qty=12), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is mi
    # Then 2
    row = reread(db, mi)
    assert row.qty == 12
    # Then 3
    assert len(entries_of(db, m1, i1)) == 1
    # Then 4
    row = entries_of(db, m1, i1)[-1]
    assert row.transaction_type == "inventory_adjustment"
    assert row.quantity == 7
    # Then 5
    row = entries_of(db, m1, i1)[-1]
    assert row.qty_before == 5
    assert row.qty_after == 12
    # Then 6
    row = entries_of(db, m1, i1)[-1]
    assert row.source_type == "adjustment"
    assert row.notes == "Manual machine inventory adjustment: 5 -> 12"
    # Then 7
    row = entries_of(db, m1, i1)[-1]
    assert row.performed_by == u2.id
    assert row.workspace_id == w1.id


# [claude] MIM-U-34
def test_mim_u_34__a_qty_change_down_12_to_5_books_one_adjustment(db, w1, u2, i1, m1, mk_stock):
    """MIM-U-34 — a qty change down (12 to 5) books one adjustment.
    Rules: `update_machine_item` R8"""
    mi = mk_stock(m1, i1, qty=12)
    result = M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(qty=5), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is mi
    # Then 2
    row = reread(db, mi)
    assert row.qty == 5
    # Then 3
    assert len(entries_of(db, m1, i1)) == 1
    # Then 4
    row = entries_of(db, m1, i1)[-1]
    assert row.transaction_type == "inventory_adjustment"
    assert row.quantity == 7
    # Then 5
    row = entries_of(db, m1, i1)[-1]
    assert row.qty_before == 12
    assert row.qty_after == 5
    # Then 6
    row = entries_of(db, m1, i1)[-1]
    assert row.source_type == "adjustment"
    assert row.notes == "Manual machine inventory adjustment: 12 -> 5"
    # Then 7
    row = entries_of(db, m1, i1)[-1]
    assert row.performed_by == u2.id
    assert row.workspace_id == w1.id


# [claude] MIM-U-35
def test_mim_u_35__a_qty_change_to_0_5_to_0_books_one_adjustment(db, w1, u2, i1, m1, mk_stock):
    """MIM-U-35 — a qty change to 0 (5 to 0) books one adjustment.
    Rules: `update_machine_item` R8"""
    mi = mk_stock(m1, i1, qty=5)
    result = M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(qty=0), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is mi
    # Then 2
    row = reread(db, mi)
    assert row.qty == 0
    # Then 3
    assert len(entries_of(db, m1, i1)) == 1
    # Then 4
    row = entries_of(db, m1, i1)[-1]
    assert row.transaction_type == "inventory_adjustment"
    assert row.quantity == 5
    # Then 5
    row = entries_of(db, m1, i1)[-1]
    assert row.qty_before == 5
    assert row.qty_after == 0
    # Then 6
    row = entries_of(db, m1, i1)[-1]
    assert row.source_type == "adjustment"
    assert row.notes == "Manual machine inventory adjustment: 5 -> 0"
    # Then 7
    row = entries_of(db, m1, i1)[-1]
    assert row.performed_by == u2.id
    assert row.workspace_id == w1.id


# [claude] MIM-U-36
def test_mim_u_36__a_qty_change_from_0_0_to_5_books_one_adjustment(db, w1, u2, i1, m1, mk_stock):
    """MIM-U-36 — a qty change from 0 (0 to 5) books one adjustment.
    Rules: `update_machine_item` R8"""
    mi = mk_stock(m1, i1, qty=0)
    result = M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(qty=5), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is mi
    # Then 2
    row = reread(db, mi)
    assert row.qty == 5
    # Then 3
    assert len(entries_of(db, m1, i1)) == 1
    # Then 4
    row = entries_of(db, m1, i1)[-1]
    assert row.transaction_type == "inventory_adjustment"
    assert row.quantity == 5
    # Then 5
    row = entries_of(db, m1, i1)[-1]
    assert row.qty_before == 0
    assert row.qty_after == 5
    # Then 6
    row = entries_of(db, m1, i1)[-1]
    assert row.source_type == "adjustment"
    assert row.notes == "Manual machine inventory adjustment: 0 -> 5"
    # Then 7
    row = entries_of(db, m1, i1)[-1]
    assert row.performed_by == u2.id
    assert row.workspace_id == w1.id


# [claude] MIM-U-37
def test_mim_u_37__no_history_the_adjustment_s_cost_fields_are_0_00(db, w1, u2, i1, m1, mk_stock):
    """MIM-U-37 — no history: the adjustment's cost fields are 0.00.
    Rules: `update_machine_item` R8, `_write_ledger_entry` R5"""
    mi = mk_stock(m1, i1, qty=5)
    result = M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(qty=12), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is mi
    # Then 2
    row = entries_of(db, m1, i1)[-1]
    assert row.unit_cost == Decimal("0.00")
    assert row.total_cost == Decimal("0.00")
    # Then 3
    row = entries_of(db, m1, i1)[-1]
    assert row.value_before == Decimal("0.00")
    assert row.value_after == Decimal("0.00")
    # Then 4
    row = entries_of(db, m1, i1)[-1]
    assert row.avg_price_before == Decimal("0.00")
    assert row.avg_price_after == Decimal("0.00")


# [claude] MIM-U-38
@pytest.mark.xfail(strict=True, reason="BUG-993: A manual stock change wipes the machine's cost")
def test_mim_u_38__the_adjustment_takes_the_current_average(db, w1, u2, i1, m1, mk_stock, mk_entry):
    """MIM-U-38 — the adjustment takes the current average.
    Rules: `update_machine_item` R8, `_write_ledger_entry` R2 [BUG-993], R3, R4"""
    mi = mk_stock(m1, i1, qty=10)
    mk_entry(m1, i1, performed_at=T9, avg_price_after=Decimal("5.00"), qty_after=10, value_after=Decimal("50.00"))
    result = M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(qty=12), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is mi
    # Then 2
    row = entries_of(db, m1, i1)[-1]
    assert row.unit_cost == Decimal("5.00")
    assert row.avg_price_before == Decimal("5.00")
    assert row.avg_price_after == Decimal("5.00")
    # Then 3
    row = entries_of(db, m1, i1)[-1]
    assert row.total_cost == Decimal("10.00")
    assert row.value_before == Decimal("50.00")
    assert row.value_after == Decimal("60.00")


# [claude] MIM-U-39
@pytest.mark.xfail(strict=True, reason="BUG-1040: Money rounded half to even in Python, half away from zero in the database (needs BUG-993 too: A manual stock change wipes the machine's cost)")
def test_mim_u_39__half_up_through_the_edit_1_at_0_125_gives_total_cost_0_13(db, w1, u2, i1, m1, mk_stock, mk_entry):
    """MIM-U-39 — half up through the edit: 1 at 0.125 gives total_cost 0.13.
    Rules: `update_machine_item` R8, `_write_ledger_entry` R3 [BUG-993] [BUG-1040]"""
    mi = mk_stock(m1, i1, qty=1)
    lg = mk_entry(m1, i1, performed_at=T9, avg_price_after=Decimal("0.125"), qty_after=1)  # noqa: F841  (Conventions: kept alive, never refreshed)
    result = M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(qty=2), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is mi
    # Then 2
    row = entries_of(db, m1, i1)[-1]
    assert row.total_cost == Decimal("0.13")


# [claude] MIM-U-40
def test_mim_u_40__qty_sent_unchanged_next_to_a_changed_field_no_entry_one_event(db, w1, u2, i1, m1, mk_stock):
    """MIM-U-40 — qty sent unchanged next to a changed field: no entry, one event.
    Rules: `update_machine_item` R9, R12"""
    mi = mk_stock(m1, i1, qty=5, req_qty=7, defective_qty=1)
    result = M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(qty=5, req_qty=3), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is mi
    # Then 2
    row = reread(db, mi)
    assert row.qty == 5
    assert row.req_qty == 3
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 0
    # Then 4
    rows = events_of(db, m1)
    assert len(rows) == 1
    # Then 5
    assert rows[0].metadata_json == {"item_id": i1.id, "item_name": "Bolt M8", "machine_item_id": mi.id, "changes": [{"field": "req_qty", "label": "Required quantity", "from_value": "7", "to_value": "3"}]}


# [claude] MIM-U-41
def test_mim_u_41__req_qty_alone_no_ledger_entry_one_event(db, w1, u2, i1, m1, mk_stock):
    """MIM-U-41 — req_qty alone: no ledger entry, one event.
    Rules: `update_machine_item` R10, R12"""
    mi = mk_stock(m1, i1, qty=5, req_qty=7, defective_qty=1)
    result = M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(req_qty=3), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is mi
    # Then 2
    assert count_rows(db, "machine_item_ledger") == 0
    # Then 3
    rows = events_of(db, m1)
    assert len(rows) == 1
    # Then 4
    assert rows[0].event_type == "item_updated"
    assert rows[0].description == "Item updated: Bolt M8"
    # Then 5
    assert rows[0].performed_by == u2.id
    assert rows[0].workspace_id == w1.id
    assert rows[0].machine_id == m1.id
    # Then 6
    assert rows[0].metadata_json == {"item_id": i1.id, "item_name": "Bolt M8", "machine_item_id": mi.id, "changes": [{"field": "req_qty", "label": "Required quantity", "from_value": "7", "to_value": "3"}]}


# [claude] MIM-U-42
def test_mim_u_42__defective_qty_alone_no_ledger_entry_one_event(db, w1, u2, i1, m1, mk_stock):
    """MIM-U-42 — defective_qty alone: no ledger entry, one event.
    Rules: `update_machine_item` R10, R12"""
    mi = mk_stock(m1, i1, qty=5, req_qty=7, defective_qty=1)
    result = M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(defective_qty=2), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is mi
    # Then 2
    assert count_rows(db, "machine_item_ledger") == 0
    # Then 3
    rows = events_of(db, m1)
    assert len(rows) == 1
    # Then 4
    assert rows[0].event_type == "item_updated"
    assert rows[0].description == "Item updated: Bolt M8"
    # Then 5
    assert rows[0].performed_by == u2.id
    assert rows[0].workspace_id == w1.id
    assert rows[0].machine_id == m1.id
    # Then 6
    assert rows[0].metadata_json == {"item_id": i1.id, "item_name": "Bolt M8", "machine_item_id": mi.id, "changes": [{"field": "defective_qty", "label": "Defective quantity", "from_value": "1", "to_value": "2"}]}


# [claude] MIM-U-43
def test_mim_u_43__a_qty_change_gives_both_activity_entries(db, w1, u2, i1, m1, mk_stock):
    """MIM-U-43 — a qty change gives both activity entries.
    Rules: `update_machine_item` R11, R12, `_write_ledger_entry` R10"""
    mi = mk_stock(m1, i1, qty=5)
    result = M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(qty=12), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is mi
    # Then 2
    rows = events_of(db, m1)
    assert len(rows) == 2
    # Then 3
    rows = events_of(db, m1, event_type="inventory_adjusted")
    assert len(rows) == 1
    # Then 4
    rows = events_of(db, m1, event_type="item_updated")
    assert len(rows) == 1
    # Then 5
    [row] = events_of(db, m1, event_type="inventory_adjusted")
    assert row.description == "Inventory adjusted on Bolt M8: 5 → 12"
    # Then 6
    [row] = events_of(db, m1, event_type="inventory_adjusted")
    assert row.metadata_json == {"item_id": i1.id, "item_name": "Bolt M8", "quantity": 7, "changes": [{"field": "qty", "label": "Quantity", "from_value": "5", "to_value": "12"}]}
    # Then 7
    [row] = events_of(db, m1, event_type="item_updated")
    assert row.description == "Item updated: Bolt M8"
    # Then 8
    [row] = events_of(db, m1, event_type="item_updated")
    assert row.metadata_json == {"item_id": i1.id, "item_name": "Bolt M8", "machine_item_id": mi.id, "changes": [{"field": "qty", "label": "Quantity", "from_value": "5", "to_value": "12"}]}


# [claude] MIM-U-44
def test_mim_u_44__changes_list_all_three_fields_in_order(db, w1, u2, i1, m1, mk_stock):
    """MIM-U-44 — changes list all three fields in order.
    Rules: `update_machine_item` R12"""
    mi = mk_stock(m1, i1, qty=5, req_qty=7, defective_qty=1)
    result = M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(defective_qty=2, req_qty=3, qty=12), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is mi
    # Then 2
    rows = events_of(db, m1, event_type="item_updated")
    assert len(rows) == 1
    # Then 3
    [row] = events_of(db, m1, event_type="item_updated")
    assert row.metadata_json == {"item_id": i1.id, "item_name": "Bolt M8", "machine_item_id": mi.id, "changes": [{"field": "qty", "label": "Quantity", "from_value": "5", "to_value": "12"}, {"field": "req_qty", "label": "Required quantity", "from_value": "7", "to_value": "3"}, {"field": "defective_qty", "label": "Defective quantity", "from_value": "1", "to_value": "2"}]}


# [claude] MIM-U-45
def test_mim_u_45__changes_leave_out_a_field_sent_with_its_old_value(db, w1, u2, i1, m1, mk_stock):
    """MIM-U-45 — changes leave out a field sent with its old value.
    Rules: `update_machine_item` R12"""
    mi = mk_stock(m1, i1, qty=5, req_qty=7, defective_qty=1)
    result = M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(qty=12, req_qty=7, defective_qty=2), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is mi
    # Then 2
    rows = events_of(db, m1, event_type="item_updated")
    assert len(rows) == 1
    # Then 3
    [row] = events_of(db, m1, event_type="item_updated")
    assert row.metadata_json == {"item_id": i1.id, "item_name": "Bolt M8", "machine_item_id": mi.id, "changes": [{"field": "qty", "label": "Quantity", "from_value": "5", "to_value": "12"}, {"field": "defective_qty", "label": "Defective quantity", "from_value": "1", "to_value": "2"}]}


# [claude] MIM-U-46
def test_mim_u_46__an_empty_old_value_is_none_in_changes(db, w1, u2, i1, m1, mk_stock):
    """MIM-U-46 — an empty old value is None in changes.
    Rules: `update_machine_item` R12"""
    mi = mk_stock(m1, i1, qty=5)
    result = M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(req_qty=3), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is mi
    # Then 2
    rows = events_of(db, m1, event_type="item_updated")
    assert len(rows) == 1
    # Then 3
    assert rows[0].metadata_json == {"item_id": i1.id, "item_name": "Bolt M8", "machine_item_id": mi.id, "changes": [{"field": "req_qty", "label": "Required quantity", "from_value": None, "to_value": "3"}]}


# [claude] MIM-U-47
@pytest.mark.xfail(strict=True, reason="BUG-1079: Negative machine stock quantities are accepted")
def test_mim_u_47__a_negative_qty_is_rejected_by_machineitemupdate(db, i1, m1, mk_stock):
    """MIM-U-47 — a negative qty is rejected by MachineItemUpdate.
    Rules: `update_machine_item` R13 [BUG-1079], Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    before_mi = snap_before(db, mi)
    # Then 1
    with pytest.raises(ValidationError):
        MachineItemUpdate(qty=-1)
    # Then 2
    assert snap(db, mi) == before_mi


# [claude] MIM-U-48
def test_mim_u_48__qty_0_is_accepted_by_machineitemupdate(db):
    """MIM-U-48 — qty 0 is accepted by MachineItemUpdate.
    Rules: `update_machine_item` R13"""
    result = MachineItemUpdate(qty=0)

    # Then 1
    assert result.qty == 0


# [claude] MIM-U-49
@pytest.mark.xfail(strict=True, reason="BUG-1078: A machine stock quantity beyond 32 bits crashes")
def test_mim_u_49__a_qty_of_2147483648_is_rejected_by_machineitemupdate(db, i1, m1, mk_stock):
    """MIM-U-49 — a qty of 2147483648 is rejected by MachineItemUpdate.
    Rules: `update_machine_item` R14 [BUG-1078], Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    before_mi = snap_before(db, mi)
    # Then 1
    with pytest.raises(ValidationError):
        MachineItemUpdate(qty=2147483648)
    # Then 2
    assert snap(db, mi) == before_mi


# [claude] MIM-U-50
@pytest.mark.xfail(strict=True, reason="BUG-1079: Negative machine stock quantities are accepted")
def test_mim_u_50__a_negative_req_qty_is_rejected_by_machineitemupdate(db, i1, m1, mk_stock):
    """MIM-U-50 — a negative req_qty is rejected by MachineItemUpdate.
    Rules: `update_machine_item` R13 [BUG-1079], Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    before_mi = snap_before(db, mi)
    # Then 1
    with pytest.raises(ValidationError):
        MachineItemUpdate(req_qty=-1)
    # Then 2
    assert snap(db, mi) == before_mi


# [claude] MIM-U-51
def test_mim_u_51__req_qty_0_is_accepted_by_machineitemupdate(db):
    """MIM-U-51 — req_qty 0 is accepted by MachineItemUpdate.
    Rules: `update_machine_item` R13"""
    result = MachineItemUpdate(req_qty=0)

    # Then 1
    assert result.req_qty == 0


# [claude] MIM-U-52
@pytest.mark.xfail(strict=True, reason="BUG-1078: A machine stock quantity beyond 32 bits crashes")
def test_mim_u_52__a_req_qty_of_2147483648_is_rejected_by_machineitemupdate(db, i1, m1, mk_stock):
    """MIM-U-52 — a req_qty of 2147483648 is rejected by MachineItemUpdate.
    Rules: `update_machine_item` R14 [BUG-1078], Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    before_mi = snap_before(db, mi)
    # Then 1
    with pytest.raises(ValidationError):
        MachineItemUpdate(req_qty=2147483648)
    # Then 2
    assert snap(db, mi) == before_mi


# [claude] MIM-U-53
@pytest.mark.xfail(strict=True, reason="BUG-1079: Negative machine stock quantities are accepted")
def test_mim_u_53__a_negative_defective_qty_is_rejected_by_machineitemupdate(db, i1, m1, mk_stock):
    """MIM-U-53 — a negative defective_qty is rejected by MachineItemUpdate.
    Rules: `update_machine_item` R13 [BUG-1079], Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    before_mi = snap_before(db, mi)
    # Then 1
    with pytest.raises(ValidationError):
        MachineItemUpdate(defective_qty=-1)
    # Then 2
    assert snap(db, mi) == before_mi


# [claude] MIM-U-54
def test_mim_u_54__defective_qty_0_is_accepted_by_machineitemupdate(db):
    """MIM-U-54 — defective_qty 0 is accepted by MachineItemUpdate.
    Rules: `update_machine_item` R13"""
    result = MachineItemUpdate(defective_qty=0)

    # Then 1
    assert result.defective_qty == 0


# [claude] MIM-U-55
@pytest.mark.xfail(strict=True, reason="BUG-1078: A machine stock quantity beyond 32 bits crashes")
def test_mim_u_55__a_defective_qty_of_2147483648_is_rejected_by_machineitemupdate(db, i1, m1, mk_stock):
    """MIM-U-55 — a defective_qty of 2147483648 is rejected by MachineItemUpdate.
    Rules: `update_machine_item` R14 [BUG-1078], Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    before_mi = snap_before(db, mi)
    # Then 1
    with pytest.raises(ValidationError):
        MachineItemUpdate(defective_qty=2147483648)
    # Then 2
    assert snap(db, mi) == before_mi


# [claude] MIM-U-56
def test_mim_u_56__a_row_already_negative_is_edited_as_an_ordinary_adjustment_3_to_2(db, w1, u2, i1, m1, mk_stock):
    """MIM-U-56 — a row already negative is edited as an ordinary adjustment (-3 to 2).
    Rules: `update_machine_item` R13, R8"""
    mi = mk_stock(m1, i1, qty=-3)
    result = M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(qty=2), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is mi
    # Then 2
    row = reread(db, mi)
    assert row.qty == 2
    # Then 3
    assert len(entries_of(db, m1, i1)) == 1
    # Then 4
    row = entries_of(db, m1, i1)[-1]
    assert row.transaction_type == "inventory_adjustment"
    assert row.quantity == 5
    # Then 5
    row = entries_of(db, m1, i1)[-1]
    assert row.qty_before == -3
    assert row.qty_after == 2
    # Then 6
    row = entries_of(db, m1, i1)[-1]
    assert row.source_type == "adjustment"
    assert row.notes == "Manual machine inventory adjustment: -3 -> 2"
    # Then 7
    row = entries_of(db, m1, i1)[-1]
    assert row.performed_by == u2.id
    assert row.workspace_id == w1.id


# [claude] MIM-U-57
def test_mim_u_57__a_row_already_negative_is_edited_as_an_ordinary_adjustment_3_to_0(db, w1, u2, i1, m1, mk_stock):
    """MIM-U-57 — a row already negative is edited as an ordinary adjustment (-3 to 0).
    Rules: `update_machine_item` R13, R8"""
    mi = mk_stock(m1, i1, qty=-3)
    result = M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(qty=0), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is mi
    # Then 2
    row = reread(db, mi)
    assert row.qty == 0
    # Then 3
    assert len(entries_of(db, m1, i1)) == 1
    # Then 4
    row = entries_of(db, m1, i1)[-1]
    assert row.transaction_type == "inventory_adjustment"
    assert row.quantity == 3
    # Then 5
    row = entries_of(db, m1, i1)[-1]
    assert row.qty_before == -3
    assert row.qty_after == 0
    # Then 6
    row = entries_of(db, m1, i1)[-1]
    assert row.source_type == "adjustment"
    assert row.notes == "Manual machine inventory adjustment: -3 -> 0"
    # Then 7
    row = entries_of(db, m1, i1)[-1]
    assert row.performed_by == u2.id
    assert row.workspace_id == w1.id


# [claude] MIM-U-58
def test_mim_u_58__2147483647_is_accepted_and_stored_on_all_three_fields(db, w1, u2, i1, m1, mk_stock):
    """MIM-U-58 — 2147483647 is accepted and stored on all three fields.
    Rules: `update_machine_item` R14"""
    mi = mk_stock(m1, i1, qty=5)
    result = M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(qty=2147483647, req_qty=2147483647, defective_qty=2147483647), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is mi
    # Then 2
    row = reread(db, mi)
    assert row.qty == 2147483647
    assert row.req_qty == 2147483647
    assert row.defective_qty == 2147483647


# [claude] MIM-U-59
@pytest.mark.xfail(strict=True, reason="BUG-1086: A stored stock row with another workspace's item shows that item's name and id")
def test_mim_u_59__a_stored_row_with_another_workspace_s_item_is_not_found(db, w1, u2, i9, m1, mk_stock):
    """MIM-U-59 — a stored row with another workspace's item is not found.
    Rules: `update_machine_item` R15 [BUG-1086], Errors row 1, `_item_name` R3 [BUG-1086]"""
    mi = mk_stock(m1, i9, qty=5)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(qty=12), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine item not found"
    # Then 4
    assert mi not in db.dirty
    # Then 5
    assert mi not in db.deleted
    # Then 6
    db.flush()
    # Then 7
    assert snap(db, mi) == before_mi
    # Then 8
    assert written(db) == before


# [claude] MIM-U-60
@pytest.mark.xfail(strict=True, reason="BUG-1086: A stored stock row with another workspace's item shows that item's name and id")
def test_mim_u_60__a_stored_row_with_another_workspace_s_item_is_not_found_with_no_field_sent(db, w1, u2, i9, m1, mk_stock):
    """MIM-U-60 — a stored row with another workspace's item is not found with no field sent.
    Rules: `update_machine_item` R15 [BUG-1086], Errors row 1"""
    mi = mk_stock(m1, i9, qty=5)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine item not found"
    # Then 4
    assert mi not in db.dirty
    # Then 5
    assert mi not in db.deleted
    # Then 6
    db.flush()
    # Then 7
    assert snap(db, mi) == before_mi
    # Then 8
    assert written(db) == before


# [claude] MIM-U-61
@pytest.mark.xfail(strict=True, reason="BUG-1086: A stored stock row with another workspace's item shows that item's name and id")
def test_mim_u_61__not_found_wins_over_the_deleted_machine_refusal_for_such_a_row(db, w1, u2, i9, mx, mk_stock):
    """MIM-U-61 — not found wins over the deleted-machine refusal for such a row.
    Rules: `update_machine_item` R15 [BUG-1086], R2 [BUG-1083], Errors row 1"""
    mi = mk_stock(mx, i9, qty=5)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(qty=12), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine item not found"
    # Then 4
    assert mi not in db.dirty
    # Then 5
    assert mi not in db.deleted
    # Then 6
    db.flush()
    # Then 7
    assert snap(db, mi) == before_mi
    # Then 8
    assert written(db) == before


# [claude] MIM-U-62
def test_mim_u_62__an_unknown_user_with_a_qty_change_fails_on_the_ledger(db, w1, i1, m1, mk_stock):
    """MIM-U-62 — an unknown user with a qty change fails on the ledger.
    Rules: `update_machine_item` R16, Errors row 4"""
    mi = mk_stock(m1, i1, qty=5)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(qty=12), workspace_id=w1.id, user_id=MISSING)
    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert exc.value.orig.diag.constraint_name == "machine_item_ledger_performed_by_fkey"
    # Then 4
    assert snap(db, mi) == before_mi
    # Then 5
    assert written(db) == before


# [claude] MIM-U-63
def test_mim_u_63__an_unknown_user_with_only_another_field_changed_fails_on_the_activity_entry(db, w1, i1, m1, mk_stock):
    """MIM-U-63 — an unknown user with only another field changed fails on the activity entry.
    Rules: `update_machine_item` R16, Errors row 4"""
    mi = mk_stock(m1, i1, qty=5)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(req_qty=3), workspace_id=w1.id, user_id=MISSING)
    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert exc.value.orig.diag.constraint_name == "machine_activity_events_performed_by_fkey"
    # Then 4
    assert snap(db, mi) == before_mi
    # Then 5
    assert written(db) == before


# [claude] MIM-U-64
def test_mim_u_64__the_update_is_flushed_but_not_committed(db, w1, u2, i1, m1, mk_stock, monkeypatch):
    """MIM-U-64 — the update is flushed but not committed.
    Rules: `update_machine_item` R17"""
    mi = mk_stock(m1, i1, qty=5)
    sp = db.begin_nested()
    spy = commit_spy(db, monkeypatch)
    result = M.update_machine_item(db, machine_item_id=mi.id, item_data=MachineItemUpdate(qty=12), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is mi
    # Then 2
    row = reread(db, mi)
    assert row.qty == 12
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    rows = events_of(db, m1)
    assert len(rows) == 2
    # Then 5
    sp.rollback()
    row = reread(db, mi)
    assert row.qty == 5
    # Then 6
    assert count_rows(db, "machine_item_ledger") == 0
    # Then 7
    assert count_rows(db, "machine_activity_events") == 0
    # Then 8
    spy.assert_not_called()


# [claude] MIM-D-01
def test_mim_d_01__a_row_of_another_workspace_gets_the_404(db, w2, u2, i1, m1, mk_stock):
    """MIM-D-01 — a row of another workspace gets the 404.
    Rules: `delete_machine_item` R1, Errors row 1"""
    mi = mk_stock(m1, i1, qty=5)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w2.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine item not found"
    # Then 4
    assert mi not in db.dirty
    # Then 5
    assert mi not in db.deleted
    # Then 6
    db.flush()
    # Then 7
    assert snap(db, mi) == before_mi
    # Then 8
    assert written(db) == before


# [claude] MIM-D-02
def test_mim_d_02__an_unknown_id_gets_the_404(db, w1, u2, i1, m1, mk_stock):
    """MIM-D-02 — an unknown id gets the 404.
    Rules: `delete_machine_item` R1, Errors row 1"""
    mi = mk_stock(m1, i1, qty=5)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_machine_item(db, machine_item_id=MISSING, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine item not found"
    # Then 4
    assert mi not in db.dirty
    # Then 5
    assert mi not in db.deleted
    # Then 6
    db.flush()
    # Then 7
    assert snap(db, mi) == before_mi
    # Then 8
    assert written(db) == before


# [claude] MIM-D-03
def test_mim_d_03__id_0_gets_the_404(db, w1, u2, i1, m1, mk_stock):
    """MIM-D-03 — id 0 gets the 404.
    Rules: `delete_machine_item` R1, Errors row 1"""
    mi = mk_stock(m1, i1, qty=5)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_machine_item(db, machine_item_id=0, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine item not found"
    # Then 4
    assert mi not in db.dirty
    # Then 5
    assert mi not in db.deleted
    # Then 6
    db.flush()
    # Then 7
    assert snap(db, mi) == before_mi
    # Then 8
    assert written(db) == before


# [claude] MIM-D-04
@pytest.mark.xfail(strict=True, reason="BUG-1084: Stock on a deleted machine can still be removed")
def test_mim_d_04__a_row_of_a_soft_deleted_machine_with_qty_5_is_refused(db, w1, u2, i1, mx, mk_stock):
    """MIM-D-04 — a row of a soft-deleted machine with qty 5 is refused.
    Rules: `delete_machine_item` R2 [BUG-1084], Errors row 2"""
    mi = mk_stock(mx, i1, qty=5)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot remove items from a deleted machine"
    # Then 4
    assert mi not in db.dirty
    # Then 5
    assert mi not in db.deleted
    # Then 6
    db.flush()
    # Then 7
    assert snap(db, mi) == before_mi
    # Then 8
    assert written(db) == before


# [claude] MIM-D-05
@pytest.mark.xfail(strict=True, reason="BUG-1084: Stock on a deleted machine can still be removed")
def test_mim_d_05__a_row_of_a_soft_deleted_machine_with_qty_0_is_refused(db, w1, u2, i1, mx, mk_stock):
    """MIM-D-05 — a row of a soft-deleted machine with qty 0 is refused.
    Rules: `delete_machine_item` R2 [BUG-1084], Errors row 2"""
    mi = mk_stock(mx, i1, qty=0)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot remove items from a deleted machine"
    # Then 4
    assert mi not in db.dirty
    # Then 5
    assert mi not in db.deleted
    # Then 6
    db.flush()
    # Then 7
    assert snap(db, mi) == before_mi
    # Then 8
    assert written(db) == before


# [claude] MIM-D-06
@pytest.mark.xfail(strict=True, reason="BUG-1084: Stock on a deleted machine can still be removed")
def test_mim_d_06__a_row_of_a_soft_deleted_machine_is_refused_before_an_unknown_user_matters(db, w1, i1, mx, mk_stock):
    """MIM-D-06 — a row of a soft-deleted machine is refused before an unknown user matters.
    Rules: `delete_machine_item` R2 [BUG-1084], R12, Errors row 2"""
    mi = mk_stock(mx, i1, qty=5)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=MISSING)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot remove items from a deleted machine"
    # Then 4
    assert mi not in db.dirty
    # Then 5
    assert mi not in db.deleted
    # Then 6
    db.flush()
    # Then 7
    assert snap(db, mi) == before_mi
    # Then 8
    assert written(db) == before


# [claude] MIM-D-07
@pytest.mark.xfail(strict=True, reason="BUG-1084: Stock on a deleted machine can still be removed")
def test_mim_d_07__a_row_of_a_soft_deleted_machine_with_an_open_order_gets_the_400_not_the_blockers(db, w1, u2, i1, m2, mx, mk_stock, mk_order, mk_source_line):
    """MIM-D-07 — a row of a soft-deleted machine with an open order gets the 400, not the blockers.
    Rules: `delete_machine_item` R2 [BUG-1084], R5 [BUG-1081], Errors row 2"""
    mi = mk_stock(mx, i1, qty=5)
    o1 = mk_order(m2, "O1", status="DRAFT")
    l1 = mk_source_line(o1, source_location_id=mx.id)
    before_mi = snap_before(db, mi)
    before_l1 = snap_before(db, l1)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot remove items from a deleted machine"
    # Then 4
    assert mi not in db.dirty
    # Then 5
    assert mi not in db.deleted
    # Then 6
    db.flush()
    # Then 7
    assert snap(db, mi) == before_mi
    # Then 8
    assert written(db) == before
    # Then 9
    assert snap(db, l1) == before_l1


# [claude] MIM-D-08
@pytest.mark.xfail(strict=True, reason="BUG-1084: Stock on a deleted machine can still be removed")
def test_mim_d_08__a_row_of_a_machine_in_a_soft_deleted_factory_with_qty_5_is_refused(db, w1, u2, i1, mf, mk_stock):
    """MIM-D-08 — a row of a machine in a soft-deleted factory with qty 5 is refused.
    Rules: `delete_machine_item` R2 [BUG-1084], Errors row 2"""
    mi = mk_stock(mf, i1, qty=5)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot remove items from a deleted machine"
    # Then 4
    assert mi not in db.dirty
    # Then 5
    assert mi not in db.deleted
    # Then 6
    db.flush()
    # Then 7
    assert snap(db, mi) == before_mi
    # Then 8
    assert written(db) == before


# [claude] MIM-D-09
@pytest.mark.xfail(strict=True, reason="BUG-1084: Stock on a deleted machine can still be removed")
def test_mim_d_09__a_row_of_a_machine_in_a_soft_deleted_factory_with_qty_0_is_refused(db, w1, u2, i1, mf, mk_stock):
    """MIM-D-09 — a row of a machine in a soft-deleted factory with qty 0 is refused.
    Rules: `delete_machine_item` R2 [BUG-1084], Errors row 2"""
    mi = mk_stock(mf, i1, qty=0)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot remove items from a deleted machine"
    # Then 4
    assert mi not in db.dirty
    # Then 5
    assert mi not in db.deleted
    # Then 6
    db.flush()
    # Then 7
    assert snap(db, mi) == before_mi
    # Then 8
    assert written(db) == before


# [claude] MIM-D-10
@pytest.mark.xfail(strict=True, reason="BUG-1084: Stock on a deleted machine can still be removed")
def test_mim_d_10__a_row_of_a_machine_in_a_soft_deleted_factory_is_refused_before_an_unknown_user_matters(db, w1, i1, mf, mk_stock):
    """MIM-D-10 — a row of a machine in a soft-deleted factory is refused before an unknown user matters.
    Rules: `delete_machine_item` R2 [BUG-1084], R12, Errors row 2"""
    mi = mk_stock(mf, i1, qty=5)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=MISSING)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot remove items from a deleted machine"
    # Then 4
    assert mi not in db.dirty
    # Then 5
    assert mi not in db.deleted
    # Then 6
    db.flush()
    # Then 7
    assert snap(db, mi) == before_mi
    # Then 8
    assert written(db) == before


# [claude] MIM-D-11
@pytest.mark.xfail(strict=True, reason="BUG-1084: Stock on a deleted machine can still be removed")
def test_mim_d_11__a_row_of_a_machine_in_a_soft_deleted_factory_with_an_open_order_gets_the_400_not_the_blockers(db, w1, u2, i1, m2, mf, mk_stock, mk_order, mk_source_line):
    """MIM-D-11 — a row of a machine in a soft-deleted factory with an open order gets the 400, not the blockers.
    Rules: `delete_machine_item` R2 [BUG-1084], R5 [BUG-1081], Errors row 2"""
    mi = mk_stock(mf, i1, qty=5)
    o1 = mk_order(m2, "O1", status="DRAFT")
    l1 = mk_source_line(o1, source_location_id=mf.id)
    before_mi = snap_before(db, mi)
    before_l1 = snap_before(db, l1)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot remove items from a deleted machine"
    # Then 4
    assert mi not in db.dirty
    # Then 5
    assert mi not in db.deleted
    # Then 6
    db.flush()
    # Then 7
    assert snap(db, mi) == before_mi
    # Then 8
    assert written(db) == before
    # Then 9
    assert snap(db, l1) == before_l1


# [claude] MIM-D-12
def test_mim_d_12__a_row_of_an_inactive_but_live_machine_is_deleted(db, w1, u2, i1, ma, mk_stock):
    """MIM-D-12 — a row of an inactive-but-live machine is deleted.
    Rules: `delete_machine_item` R2"""
    mi = mk_stock(ma, i1, qty=5)
    mi_id = mi.id
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert len(entries_of(db, ma, i1)) == 1


# [claude] MIM-D-13
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_13__a_row_of_an_inactive_but_live_machine_with_an_open_order_is_refused_with_its_blockers(db, w1, u2, i1, m2, ma, mk_stock, mk_order, mk_source_line):
    """MIM-D-13 — a row of an inactive-but-live machine with an open order is refused with its blockers.
    Rules: `delete_machine_item` R2, R5 (a) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(ma, i1, qty=5)
    o1 = mk_order(m2, "O1", status="DRAFT")
    l1 = mk_source_line(o1, source_location_id=ma.id)
    before_mi = snap_before(db, mi)
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, o1) == before_o1
    # Then 11
    assert snap(db, l1) == before_l1


# [claude] MIM-D-14
def test_mim_d_14__a_row_of_a_machine_in_an_inactive_but_live_factory_is_deleted(db, w1, u2, i1, mn, mk_stock):
    """MIM-D-14 — a row of a machine in an inactive-but-live factory is deleted.
    Rules: `delete_machine_item` R2"""
    mi = mk_stock(mn, i1, qty=5)
    mi_id = mi.id
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert len(entries_of(db, mn, i1)) == 1


# [claude] MIM-D-15
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_15__a_row_of_a_machine_in_an_inactive_but_live_factory_with_an_open_order_is_refused_with_its_blockers(db, w1, u2, i1, m2, mn, mk_stock, mk_order, mk_source_line):
    """MIM-D-15 — a row of a machine in an inactive-but-live factory with an open order is refused with its blockers.
    Rules: `delete_machine_item` R2, R5 (a) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(mn, i1, qty=5)
    o1 = mk_order(m2, "O1", status="DRAFT")
    l1 = mk_source_line(o1, source_location_id=mn.id)
    before_mi = snap_before(db, mi)
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, o1) == before_o1
    # Then 11
    assert snap(db, l1) == before_l1


# [claude] MIM-D-16
def test_mim_d_16__a_row_of_a_removed_item_is_deleted_like_any_other(db, w1, u2, ix, m1, mk_stock):
    """MIM-D-16 — a row of a removed item is deleted like any other.
    Rules: `delete_machine_item` R3, R6, R9"""
    mi = mk_stock(m1, ix, qty=3)
    mi_id = mi.id
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert len(entries_of(db, m1, ix)) == 1
    # Then 4
    [row] = events_of(db, m1, event_type="item_removed")
    assert row.description == "Item removed: Old Rivet"


# [claude] MIM-D-17
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_17__a_row_of_a_removed_item_with_an_open_order_is_refused_like_any_other(db, w1, u2, ix, m1, mk_stock, mk_order, mk_source_line):
    """MIM-D-17 — a row of a removed item with an open order is refused like any other.
    Rules: `delete_machine_item` R3, R5 (a) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, ix, qty=3)
    o1 = mk_order(m1, "O1", status="DRAFT")
    l1 = mk_source_line(o1, item_id=ix.id)
    before_mi = snap_before(db, mi)
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, o1) == before_o1
    # Then 11
    assert snap(db, l1) == before_l1


# [claude] MIM-D-18
@pytest.mark.xfail(strict=True, reason="BUG-1073: Removing a machine stock row does not lock it")
def test_mim_d_18__the_row_is_read_for_update(db, w1, u2, i1, m1, mk_stock):
    """MIM-D-18 — the row is read FOR UPDATE.
    Rules: `delete_machine_item` R4 [BUG-1073]"""
    mi = mk_stock(m1, i1, qty=5)
    with record_sql(db) as sql_log:
        result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert any("FOR UPDATE" in s for s in sql_log if s.lstrip().startswith("SELECT") and "FROM machine_items" in s)


# [claude] MIM-D-19
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_19__a_a_draft_order_with_an_unconsumed_line_sourcing_from_this_machine_blocks(db, w1, u2, i1, m1, mk_stock, mk_order, mk_source_line):
    """MIM-D-19 — (a) a DRAFT order with an unconsumed line sourcing from this machine blocks.
    Rules: `delete_machine_item` R5 (a) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT")
    l1 = mk_source_line(o1)
    before_mi = snap_before(db, mi)
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, o1) == before_o1
    # Then 11
    assert snap(db, l1) == before_l1


# [claude] MIM-D-20
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_20__b_a_draft_order_on_this_machine_with_a_replace_line_for_this_item_blocks(db, w1, u2, i1, m1, mk_stock, mk_order, mk_replace_line):
    """MIM-D-20 — (b) a DRAFT order on this machine with a REPLACE line for this item blocks.
    Rules: `delete_machine_item` R5 (b) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT")
    l1 = mk_replace_line(o1)
    before_mi = snap_before(db, mi)
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, o1) == before_o1
    # Then 11
    assert snap(db, l1) == before_l1


# [claude] MIM-D-21
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_21__a_a_in_progress_order_with_an_unconsumed_line_sourcing_from_this_machine_blocks(db, w1, u2, i1, m1, mk_stock, mk_order, mk_source_line):
    """MIM-D-21 — (a) a IN_PROGRESS order with an unconsumed line sourcing from this machine blocks.
    Rules: `delete_machine_item` R5 (a) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="IN_PROGRESS")
    l1 = mk_source_line(o1)
    before_mi = snap_before(db, mi)
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, o1) == before_o1
    # Then 11
    assert snap(db, l1) == before_l1


# [claude] MIM-D-22
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_22__b_a_in_progress_order_on_this_machine_with_a_replace_line_for_this_item_blocks(db, w1, u2, i1, m1, mk_stock, mk_order, mk_replace_line):
    """MIM-D-22 — (b) a IN_PROGRESS order on this machine with a REPLACE line for this item blocks.
    Rules: `delete_machine_item` R5 (b) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="IN_PROGRESS")
    l1 = mk_replace_line(o1)
    before_mi = snap_before(db, mi)
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, o1) == before_o1
    # Then 11
    assert snap(db, l1) == before_l1


# [claude] MIM-D-23
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_23__c_a_not_completed_transfer_out_of_this_machine_with_a_line_for_this_item_blocks(db, w1, u2, i1, m1, mk_stock, mk_transfer, mk_to_line):
    """MIM-D-23 — (c) a not-completed transfer out of this machine with a line for this item blocks.
    Rules: `delete_machine_item` R5 (c) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    to1 = mk_transfer("TO1")
    tl1 = mk_to_line(to1)
    before_mi = snap_before(db, mi)
    before_to1 = snap_before(db, to1)
    before_tl1 = snap_before(db, tl1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "transfer_order", "id": to1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, to1) == before_to1
    # Then 11
    assert snap(db, tl1) == before_tl1


# [claude] MIM-D-24
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_24__d_a_pending_return_of_a_purchase_order_delivered_to_this_machine_blocks(db, w1, u2, i1, m1, mk_stock, mk_po, mk_po_line, mk_return, mk_return_line):
    """MIM-D-24 — (d) a pending return of a purchase order delivered to this machine blocks.
    Rules: `delete_machine_item` R5 (d) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    po1 = mk_po("PO1")
    pol1 = mk_po_line(po1)
    rt1 = mk_return(po1, "RT1")
    rl1 = mk_return_line(rt1, pol1)
    before_mi = snap_before(db, mi)
    before_rt1 = snap_before(db, rt1)
    before_rl1 = snap_before(db, rl1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "purchase_return", "id": rt1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, rt1) == before_rt1
    # Then 11
    assert snap(db, rl1) == before_rl1


# [claude] MIM-D-25
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_25__a_the_order_s_own_machine_is_not_read_an_order_of_another_machine_blocks(db, w1, u2, i1, m1, m2, mk_stock, mk_order, mk_source_line):
    """MIM-D-25 — (a) the order's own machine is not read: an order of another machine blocks.
    Rules: `delete_machine_item` R5 (a) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m2, "O1", status="DRAFT")
    mk_source_line(o1)
    before_mi = snap_before(db, mi)
    before_o1 = snap_before(db, o1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, o1) == before_o1


# [claude] MIM-D-26
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_26__a_the_order_s_own_machine_is_not_read_an_order_with_no_machine_blocks(db, w1, u2, i1, m1, mk_stock, mk_order, mk_source_line):
    """MIM-D-26 — (a) the order's own machine is not read: an order with no machine blocks.
    Rules: `delete_machine_item` R5 (a) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT", machine_id=None)
    mk_source_line(o1)
    before_mi = snap_before(db, mi)
    before_o1 = snap_before(db, o1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, o1) == before_o1


# [claude] MIM-D-27
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_27__a_the_order_s_soft_deleted_factory_is_not_read(db, w1, u2, fd, i1, m1, m2, mk_stock, mk_order, mk_source_line):
    """MIM-D-27 — (a) the order's soft-deleted factory is not read.
    Rules: `delete_machine_item` R5 (a) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m2, "O1", status="DRAFT", factory_id=fd.id)
    mk_source_line(o1)
    before_mi = snap_before(db, mi)
    before_o1 = snap_before(db, o1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, o1) == before_o1


# [claude] MIM-D-28
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_28__a_the_order_s_inactive_factory_is_not_read(db, w1, u2, fi, i1, m1, m2, mk_stock, mk_order, mk_source_line):
    """MIM-D-28 — (a) the order's inactive factory is not read.
    Rules: `delete_machine_item` R5 (a) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m2, "O1", status="DRAFT", factory_id=fi.id)
    mk_source_line(o1)
    before_mi = snap_before(db, mi)
    before_o1 = snap_before(db, o1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, o1) == before_o1


# [claude] MIM-D-29
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_29__a_the_order_s_soft_deleted_machine_is_not_read(db, w1, u2, i1, m1, mx, mk_stock, mk_order, mk_source_line):
    """MIM-D-29 — (a) the order's soft-deleted machine is not read.
    Rules: `delete_machine_item` R5 (a) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(mx, "O1", status="DRAFT")
    mk_source_line(o1)
    before_mi = snap_before(db, mi)
    before_o1 = snap_before(db, o1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, o1) == before_o1


# [claude] MIM-D-30
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_30__b_a_consumed_replace_line_still_blocks_consumed_at_is_not_read(db, w1, u2, i1, m1, mk_stock, mk_order, mk_replace_line):
    """MIM-D-30 — (b) a consumed REPLACE line still blocks: `consumed_at` is not read.
    Rules: `delete_machine_item` R5 (b) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT")
    mk_replace_line(o1, consumed_at=T9)
    before_mi = snap_before(db, mi)
    before_o1 = snap_before(db, o1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, o1) == before_o1


# [claude] MIM-D-32
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_32__b_the_order_s_soft_deleted_factory_is_not_read(db, w1, u2, fd, i1, m1, mk_stock, mk_order, mk_replace_line):
    """MIM-D-32 — (b) the order's soft-deleted factory is not read.
    Rules: `delete_machine_item` R5 (b) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT", factory_id=fd.id)
    mk_replace_line(o1)
    before_mi = snap_before(db, mi)
    before_o1 = snap_before(db, o1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, o1) == before_o1


# [claude] MIM-D-33
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_33__b_the_order_s_inactive_factory_is_not_read(db, w1, u2, fi, i1, m1, mk_stock, mk_order, mk_replace_line):
    """MIM-D-33 — (b) the order's inactive factory is not read.
    Rules: `delete_machine_item` R5 (b) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT", factory_id=fi.id)
    mk_replace_line(o1)
    before_mi = snap_before(db, mi)
    before_o1 = snap_before(db, o1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, o1) == before_o1


# [claude] MIM-D-34
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_34__c_the_stage_is_not_read_a_transfer_at_stage_complete_with_completed_at_empty_blocks(db, w1, u2, i1, m1, stc, mk_stock, mk_transfer, mk_to_line):
    """MIM-D-34 — (c) the stage is not read: a transfer at stage Complete with completed_at empty blocks.
    Rules: `delete_machine_item` R5 (c) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    to1 = mk_transfer("TO1", current_status_id=stc.id)
    mk_to_line(to1)
    before_mi = snap_before(db, mi)
    before_to1 = snap_before(db, to1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "transfer_order", "id": to1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, to1) == before_to1


# [claude] MIM-D-35
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_35__c_a_soft_deleted_destination_factory_is_not_read(db, w1, u2, fd, i1, m1, mk_stock, mk_transfer, mk_to_line):
    """MIM-D-35 — (c) a soft-deleted destination factory is not read.
    Rules: `delete_machine_item` R5 (c) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    to1 = mk_transfer("TO1", destination_location_id=fd.id)
    mk_to_line(to1)
    before_mi = snap_before(db, mi)
    before_to1 = snap_before(db, to1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "transfer_order", "id": to1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, to1) == before_to1


# [claude] MIM-D-36
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_36__c_an_inactive_destination_factory_is_not_read(db, w1, u2, fi, i1, m1, mk_stock, mk_transfer, mk_to_line):
    """MIM-D-36 — (c) an inactive destination factory is not read.
    Rules: `delete_machine_item` R5 (c) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    to1 = mk_transfer("TO1", destination_location_id=fi.id)
    mk_to_line(to1)
    before_mi = snap_before(db, mi)
    before_to1 = snap_before(db, to1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "transfer_order", "id": to1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, to1) == before_to1


# [claude] MIM-D-37
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_37__c_a_soft_deleted_destination_machine_is_not_read(db, w1, u2, i1, m1, mx, mk_stock, mk_transfer, mk_to_line):
    """MIM-D-37 — (c) a soft-deleted destination machine is not read.
    Rules: `delete_machine_item` R5 (c) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    to1 = mk_transfer("TO1", destination_location_type="machine", destination_location_id=mx.id)
    mk_to_line(to1)
    before_mi = snap_before(db, mi)
    before_to1 = snap_before(db, to1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "transfer_order", "id": to1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, to1) == before_to1


# [claude] MIM-D-38
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_38__d_a_voided_purchase_order_is_not_read_its_pending_return_blocks(db, w1, u2, i1, m1, mk_stock, mk_po, mk_po_line, mk_return, mk_return_line):
    """MIM-D-38 — (d) a voided purchase order is not read: its pending return blocks.
    Rules: `delete_machine_item` R5 (d) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    po1 = mk_po("PO1", voided=True)
    pol1 = mk_po_line(po1)
    rt1 = mk_return(po1, "RT1")
    mk_return_line(rt1, pol1)
    before_mi = snap_before(db, mi)
    before_rt1 = snap_before(db, rt1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "purchase_return", "id": rt1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, rt1) == before_rt1


# [claude] MIM-D-39
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_39__d_the_stage_is_not_read_a_purchase_order_at_stage_draft_with_a_pending_return_blocks(db, w1, u2, i1, m1, std, mk_stock, mk_po, mk_po_line, mk_return, mk_return_line):
    """MIM-D-39 — (d) the stage is not read: a purchase order at stage Draft with a pending return blocks.
    Rules: `delete_machine_item` R5 (d) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    po1 = mk_po("PO1", current_status_id=std.id)
    pol1 = mk_po_line(po1)
    rt1 = mk_return(po1, "RT1")
    mk_return_line(rt1, pol1)
    before_mi = snap_before(db, mi)
    before_rt1 = snap_before(db, rt1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "purchase_return", "id": rt1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, rt1) == before_rt1


# [claude] MIM-D-40
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_40__a_an_order_and_line_of_w2_on_the_source_machine_shows_only_the_generic_entry(db, w1, w2, u2, f9, i1, m1, m9, wt9, mk_stock, mk_order, mk_source_line):
    """MIM-D-40 — (a) an order and line of W2 on the source machine shows only the generic entry.
    Rules: `delete_machine_item` R5 (a) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m9, "O1", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    l1 = mk_source_line(o1, workspace_id=w2.id)
    before_mi = snap_before(db, mi)
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, o1) == before_o1
    # Then 11
    assert snap(db, l1) == before_l1


# [claude] MIM-D-41
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_41__a_a_w1_line_on_an_order_of_w2_shows_only_the_generic_entry(db, w1, w2, u2, f9, i1, m1, m9, wt9, mk_stock, mk_order, mk_source_line):
    """MIM-D-41 — (a) a W1 line on an order of W2 shows only the generic entry.
    Rules: `delete_machine_item` R5 (a) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m9, "O1", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    l1 = mk_source_line(o1)
    before_mi = snap_before(db, mi)
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, o1) == before_o1
    # Then 11
    assert snap(db, l1) == before_l1


# [claude] MIM-D-42
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_42__a_a_w2_line_on_an_order_of_w1_shows_only_the_generic_entry(db, w1, w2, u2, i1, m1, mk_stock, mk_order, mk_source_line):
    """MIM-D-42 — (a) a W2 line on an order of W1 shows only the generic entry.
    Rules: `delete_machine_item` R5 (a) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT")
    l1 = mk_source_line(o1, workspace_id=w2.id)
    before_mi = snap_before(db, mi)
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, o1) == before_o1
    # Then 11
    assert snap(db, l1) == before_l1


# [claude] MIM-D-43
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_43__a_an_in_progress_order_and_line_of_w2_shows_only_the_generic_entry(db, w1, w2, u2, f9, i1, m1, m9, wt9, mk_stock, mk_order, mk_source_line):
    """MIM-D-43 — (a) an IN_PROGRESS order and line of W2 shows only the generic entry.
    Rules: `delete_machine_item` R5 (a) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m9, "O1", status="IN_PROGRESS", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    l1 = mk_source_line(o1, workspace_id=w2.id)
    before_mi = snap_before(db, mi)
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, o1) == before_o1
    # Then 11
    assert snap(db, l1) == before_l1


# [claude] MIM-D-44
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_44__b_an_order_and_replace_line_of_w2_on_this_machine_shows_only_the_generic_entry(db, w1, w2, u2, f9, i1, m1, wt9, mk_stock, mk_order, mk_replace_line):
    """MIM-D-44 — (b) an order and REPLACE line of W2 on this machine shows only the generic entry.
    Rules: `delete_machine_item` R5 (b) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    l1 = mk_replace_line(o1, workspace_id=w2.id)
    before_mi = snap_before(db, mi)
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, o1) == before_o1
    # Then 11
    assert snap(db, l1) == before_l1


# [claude] MIM-D-45
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_45__b_a_w1_replace_line_on_an_order_of_w2_shows_only_the_generic_entry(db, w1, w2, u2, f9, i1, m1, wt9, mk_stock, mk_order, mk_replace_line):
    """MIM-D-45 — (b) a W1 REPLACE line on an order of W2 shows only the generic entry.
    Rules: `delete_machine_item` R5 (b) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    l1 = mk_replace_line(o1)
    before_mi = snap_before(db, mi)
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, o1) == before_o1
    # Then 11
    assert snap(db, l1) == before_l1


# [claude] MIM-D-46
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_46__b_a_w2_replace_line_on_an_order_of_w1_shows_only_the_generic_entry(db, w1, w2, u2, i1, m1, mk_stock, mk_order, mk_replace_line):
    """MIM-D-46 — (b) a W2 REPLACE line on an order of W1 shows only the generic entry.
    Rules: `delete_machine_item` R5 (b) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT")
    l1 = mk_replace_line(o1, workspace_id=w2.id)
    before_mi = snap_before(db, mi)
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, o1) == before_o1
    # Then 11
    assert snap(db, l1) == before_l1


# [claude] MIM-D-47
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_47__b_an_in_progress_order_and_replace_line_of_w2_shows_only_the_generic_entry(db, w1, w2, u2, f9, i1, m1, wt9, mk_stock, mk_order, mk_replace_line):
    """MIM-D-47 — (b) an IN_PROGRESS order and REPLACE line of W2 shows only the generic entry.
    Rules: `delete_machine_item` R5 (b) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="IN_PROGRESS", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    l1 = mk_replace_line(o1, workspace_id=w2.id)
    before_mi = snap_before(db, mi)
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, o1) == before_o1
    # Then 11
    assert snap(db, l1) == before_l1


# [claude] MIM-D-48
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_48__c_a_transfer_and_line_of_w2_shows_only_the_generic_entry(db, w1, w2, u2, f9, i1, m1, st9, mk_stock, mk_transfer, mk_to_line):
    """MIM-D-48 — (c) a transfer and line of W2 shows only the generic entry.
    Rules: `delete_machine_item` R5 (c) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    to1 = mk_transfer("TO1", workspace_id=w2.id, current_status_id=st9.id, destination_location_id=f9.id)
    tl1 = mk_to_line(to1, workspace_id=w2.id)
    before_mi = snap_before(db, mi)
    before_to1 = snap_before(db, to1)
    before_tl1 = snap_before(db, tl1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, to1) == before_to1
    # Then 11
    assert snap(db, tl1) == before_tl1


# [claude] MIM-D-49
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_49__c_a_w1_line_on_a_transfer_of_w2_shows_only_the_generic_entry(db, w1, w2, u2, f9, i1, m1, st9, mk_stock, mk_transfer, mk_to_line):
    """MIM-D-49 — (c) a W1 line on a transfer of W2 shows only the generic entry.
    Rules: `delete_machine_item` R5 (c) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    to1 = mk_transfer("TO1", workspace_id=w2.id, current_status_id=st9.id, destination_location_id=f9.id)
    tl1 = mk_to_line(to1)
    before_mi = snap_before(db, mi)
    before_to1 = snap_before(db, to1)
    before_tl1 = snap_before(db, tl1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, to1) == before_to1
    # Then 11
    assert snap(db, tl1) == before_tl1


# [claude] MIM-D-50
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_50__c_a_w2_line_on_a_transfer_of_w1_shows_only_the_generic_entry(db, w1, w2, u2, i1, m1, mk_stock, mk_transfer, mk_to_line):
    """MIM-D-50 — (c) a W2 line on a transfer of W1 shows only the generic entry.
    Rules: `delete_machine_item` R5 (c) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    to1 = mk_transfer("TO1")
    tl1 = mk_to_line(to1, workspace_id=w2.id)
    before_mi = snap_before(db, mi)
    before_to1 = snap_before(db, to1)
    before_tl1 = snap_before(db, tl1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, to1) == before_to1
    # Then 11
    assert snap(db, tl1) == before_tl1


# [claude] MIM-D-51
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_51__d_a_purchase_order_return_and_line_all_of_w2_shows_only_the_generic_entry(db, w1, w2, u2, i1, m1, st9, mk_stock, mk_po, mk_po_line, mk_return, mk_return_line):
    """MIM-D-51 — (d) a purchase order, return and line all of W2 shows only the generic entry.
    Rules: `delete_machine_item` R5 (d) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    po1 = mk_po("PO1", workspace_id=w2.id, current_status_id=st9.id)
    pol1 = mk_po_line(po1, workspace_id=w2.id)
    rt1 = mk_return(po1, "RT1", workspace_id=w2.id)
    rl1 = mk_return_line(rt1, pol1, workspace_id=w2.id)
    before_mi = snap_before(db, mi)
    before_rt1 = snap_before(db, rt1)
    before_rl1 = snap_before(db, rl1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, rt1) == before_rt1
    # Then 11
    assert snap(db, rl1) == before_rl1


# [claude] MIM-D-52
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_52__d_a_return_and_line_of_w2_on_a_purchase_order_of_w1_shows_only_the_generic_entry(db, w1, w2, u2, i1, m1, mk_stock, mk_po, mk_po_line, mk_return, mk_return_line):
    """MIM-D-52 — (d) a return and line of W2 on a purchase order of W1 shows only the generic entry.
    Rules: `delete_machine_item` R5 (d) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    po1 = mk_po("PO1")
    pol1 = mk_po_line(po1)
    rt1 = mk_return(po1, "RT1", workspace_id=w2.id)
    rl1 = mk_return_line(rt1, pol1, workspace_id=w2.id)
    before_mi = snap_before(db, mi)
    before_rt1 = snap_before(db, rt1)
    before_rl1 = snap_before(db, rl1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, rt1) == before_rt1
    # Then 11
    assert snap(db, rl1) == before_rl1


# [claude] MIM-D-53
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_53__d_a_w1_line_on_a_return_of_w2_shows_only_the_generic_entry(db, w1, w2, u2, i1, m1, mk_stock, mk_po, mk_po_line, mk_return, mk_return_line):
    """MIM-D-53 — (d) a W1 line on a return of W2 shows only the generic entry.
    Rules: `delete_machine_item` R5 (d) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    po1 = mk_po("PO1")
    pol1 = mk_po_line(po1)
    rt1 = mk_return(po1, "RT1", workspace_id=w2.id)
    rl1 = mk_return_line(rt1, pol1)
    before_mi = snap_before(db, mi)
    before_rt1 = snap_before(db, rt1)
    before_rl1 = snap_before(db, rl1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, rt1) == before_rt1
    # Then 11
    assert snap(db, rl1) == before_rl1


# [claude] MIM-D-54
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_54__d_a_w2_line_on_a_return_of_w1_shows_only_the_generic_entry(db, w1, w2, u2, i1, m1, mk_stock, mk_po, mk_po_line, mk_return, mk_return_line):
    """MIM-D-54 — (d) a W2 line on a return of W1 shows only the generic entry.
    Rules: `delete_machine_item` R5 (d) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    po1 = mk_po("PO1")
    pol1 = mk_po_line(po1)
    rt1 = mk_return(po1, "RT1")
    rl1 = mk_return_line(rt1, pol1, workspace_id=w2.id)
    before_mi = snap_before(db, mi)
    before_rt1 = snap_before(db, rt1)
    before_rl1 = snap_before(db, rl1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, rt1) == before_rt1
    # Then 11
    assert snap(db, rl1) == before_rl1


# [claude] MIM-D-55
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_55__a_lines_are_judged_one_at_a_time_own_line_and_w2_line_give_the_entry_and_the_generic_one(db, w1, w2, u2, i1, m1, mk_stock, mk_order, mk_source_line):
    """MIM-D-55 — (a) lines are judged one at a time: own line and W2 line give the entry and the generic one.
    Rules: `delete_machine_item` R5 (a) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT")
    l1 = mk_source_line(o1)
    l2 = mk_source_line(o1, workspace_id=w2.id)
    before_mi = snap_before(db, mi)
    before_l1 = snap_before(db, l1)
    before_l2 = snap_before(db, l2)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}, {"type": "other_workspace"}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, l1) == before_l1
    # Then 11
    assert snap(db, l2) == before_l2


# [claude] MIM-D-56
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_56__b_lines_are_judged_one_at_a_time_own_line_and_w2_line_give_the_entry_and_the_generic_one(db, w1, w2, u2, i1, m1, mk_stock, mk_order, mk_replace_line):
    """MIM-D-56 — (b) lines are judged one at a time: own line and W2 line give the entry and the generic one.
    Rules: `delete_machine_item` R5 (b) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT")
    l1 = mk_replace_line(o1)
    l2 = mk_replace_line(o1, workspace_id=w2.id)
    before_mi = snap_before(db, mi)
    before_l1 = snap_before(db, l1)
    before_l2 = snap_before(db, l2)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}, {"type": "other_workspace"}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, l1) == before_l1
    # Then 11
    assert snap(db, l2) == before_l2


# [claude] MIM-D-57
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_57__c_lines_are_judged_one_at_a_time_own_line_and_w2_line_give_the_entry_and_the_generic_one(db, w1, w2, u2, i1, m1, mk_stock, mk_transfer, mk_to_line):
    """MIM-D-57 — (c) lines are judged one at a time: own line and W2 line give the entry and the generic one.
    Rules: `delete_machine_item` R5 (c) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    to1 = mk_transfer("TO1")
    tl1 = mk_to_line(to1)
    tl2 = mk_to_line(to1, workspace_id=w2.id, line_number=2)
    before_mi = snap_before(db, mi)
    before_tl1 = snap_before(db, tl1)
    before_tl2 = snap_before(db, tl2)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "transfer_order", "id": to1.id}, {"type": "other_workspace"}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, tl1) == before_tl1
    # Then 11
    assert snap(db, tl2) == before_tl2


# [claude] MIM-D-58
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_58__d_lines_are_judged_one_at_a_time_own_line_and_w2_line_give_the_entry_and_the_generic_one(db, w1, w2, u2, i1, m1, mk_stock, mk_po, mk_po_line, mk_return, mk_return_line):
    """MIM-D-58 — (d) lines are judged one at a time: own line and W2 line give the entry and the generic one.
    Rules: `delete_machine_item` R5 (d) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    po1 = mk_po("PO1")
    pol1 = mk_po_line(po1)
    rt1 = mk_return(po1, "RT1")
    rl1 = mk_return_line(rt1, pol1)
    rl2 = mk_return_line(rt1, pol1, workspace_id=w2.id)
    before_mi = snap_before(db, mi)
    before_rl1 = snap_before(db, rl1)
    before_rl2 = snap_before(db, rl2)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "purchase_return", "id": rt1.id}, {"type": "other_workspace"}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, rl1) == before_rl1
    # Then 11
    assert snap(db, rl2) == before_rl2


# [claude] MIM-D-59
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_59__a_a_w1_row_on_a_w2_factory_keeps_its_normal_entry(db, w1, u2, f9, i1, m1, mk_stock, mk_order, mk_source_line):
    """MIM-D-59 — (a) a W1 row on a W2 factory keeps its normal entry.
    Rules: `delete_machine_item` R5 (a) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT", factory_id=f9.id)
    mk_source_line(o1)
    before_mi = snap_before(db, mi)
    before_o1 = snap_before(db, o1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, o1) == before_o1


# [claude] MIM-D-60
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_60__a_a_w1_row_on_a_w2_work_order_type_keeps_its_normal_entry(db, w1, u2, i1, m1, wt9, mk_stock, mk_order, mk_source_line):
    """MIM-D-60 — (a) a W1 row on a W2 work order type keeps its normal entry.
    Rules: `delete_machine_item` R5 (a) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT", work_order_type_id=wt9.id)
    mk_source_line(o1)
    before_mi = snap_before(db, mi)
    before_o1 = snap_before(db, o1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, o1) == before_o1


# [claude] MIM-D-61
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_61__a_a_w1_row_on_a_w2_machine_as_its_own_machine_keeps_its_normal_entry(db, w1, u2, i1, m1, m9, mk_stock, mk_order, mk_source_line):
    """MIM-D-61 — (a) a W1 row on a W2 machine as its own machine keeps its normal entry.
    Rules: `delete_machine_item` R5 (a) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m9, "O1", status="DRAFT")
    mk_source_line(o1)
    before_mi = snap_before(db, mi)
    before_o1 = snap_before(db, o1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, o1) == before_o1


# [claude] MIM-D-62
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_62__b_a_w1_row_on_a_w2_factory_keeps_its_normal_entry(db, w1, u2, f9, i1, m1, mk_stock, mk_order, mk_replace_line):
    """MIM-D-62 — (b) a W1 row on a W2 factory keeps its normal entry.
    Rules: `delete_machine_item` R5 (b) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT", factory_id=f9.id)
    mk_replace_line(o1)
    before_mi = snap_before(db, mi)
    before_o1 = snap_before(db, o1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, o1) == before_o1


# [claude] MIM-D-63
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_63__b_a_w1_row_on_a_w2_work_order_type_keeps_its_normal_entry(db, w1, u2, i1, m1, wt9, mk_stock, mk_order, mk_replace_line):
    """MIM-D-63 — (b) a W1 row on a W2 work order type keeps its normal entry.
    Rules: `delete_machine_item` R5 (b) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT", work_order_type_id=wt9.id)
    mk_replace_line(o1)
    before_mi = snap_before(db, mi)
    before_o1 = snap_before(db, o1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, o1) == before_o1


# [claude] MIM-D-64
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_64__c_a_w1_row_on_a_w2_stage_keeps_its_normal_entry(db, w1, u2, i1, m1, st9, mk_stock, mk_transfer, mk_to_line):
    """MIM-D-64 — (c) a W1 row on a W2 stage keeps its normal entry.
    Rules: `delete_machine_item` R5 (c) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    to1 = mk_transfer("TO1", current_status_id=st9.id)
    mk_to_line(to1)
    before_mi = snap_before(db, mi)
    before_to1 = snap_before(db, to1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "transfer_order", "id": to1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, to1) == before_to1


# [claude] MIM-D-65
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_65__c_a_w1_row_on_a_w2_destination_factory_keeps_its_normal_entry(db, w1, u2, f9, i1, m1, mk_stock, mk_transfer, mk_to_line):
    """MIM-D-65 — (c) a W1 row on a W2 destination factory keeps its normal entry.
    Rules: `delete_machine_item` R5 (c) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    to1 = mk_transfer("TO1", destination_location_id=f9.id)
    mk_to_line(to1)
    before_mi = snap_before(db, mi)
    before_to1 = snap_before(db, to1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "transfer_order", "id": to1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, to1) == before_to1


# [claude] MIM-D-66
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_66__c_a_w1_row_on_a_w2_destination_machine_keeps_its_normal_entry(db, w1, u2, i1, m1, m9, mk_stock, mk_transfer, mk_to_line):
    """MIM-D-66 — (c) a W1 row on a W2 destination machine keeps its normal entry.
    Rules: `delete_machine_item` R5 (c) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    to1 = mk_transfer("TO1", destination_location_type="machine", destination_location_id=m9.id)
    mk_to_line(to1)
    before_mi = snap_before(db, mi)
    before_to1 = snap_before(db, to1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "transfer_order", "id": to1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, to1) == before_to1


# [claude] MIM-D-67
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_67__d_a_w1_row_on_a_purchase_order_at_a_w2_stage_keeps_its_normal_entry(db, w1, u2, i1, m1, st9, mk_stock, mk_po, mk_po_line, mk_return, mk_return_line):
    """MIM-D-67 — (d) a W1 row on a purchase order at a W2 stage keeps its normal entry.
    Rules: `delete_machine_item` R5 (d) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    po1 = mk_po("PO1", current_status_id=st9.id)
    pol1 = mk_po_line(po1)
    rt1 = mk_return(po1, "RT1")
    mk_return_line(rt1, pol1)
    before_mi = snap_before(db, mi)
    before_rt1 = snap_before(db, rt1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "purchase_return", "id": rt1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, rt1) == before_rt1


# [claude] MIM-D-68
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_68__d_a_w1_row_on_a_w2_purchase_order_line_behind_the_return_line_keeps_its_normal_entry(db, w1, w2, u2, i1, m1, mk_stock, mk_po, mk_po_line, mk_return, mk_return_line):
    """MIM-D-68 — (d) a W1 row on a W2 purchase order line behind the return line keeps its normal entry.
    Rules: `delete_machine_item` R5 (d) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    po1 = mk_po("PO1")
    mk_po_line(po1)
    rt1 = mk_return(po1, "RT1")
    pol9 = mk_po_line(po1, workspace_id=w2.id, line_number=2)
    mk_return_line(rt1, pol9)
    before_mi = snap_before(db, mi)
    before_rt1 = snap_before(db, rt1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "purchase_return", "id": rt1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, rt1) == before_rt1


# [claude] MIM-D-69
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_69__work_orders_sort_by_order_id_not_by_line_id(db, w1, u2, i1, m1, mk_stock, mk_order, mk_source_line):
    """MIM-D-69 — work orders sort by order id, not by line id.
    Rules: `delete_machine_item` R5a [BUG-1081], Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT")
    o2 = mk_order(m1, "O2", status="DRAFT")
    mk_source_line(o2)
    mk_source_line(o1)
    before_mi = snap_before(db, mi)
    before_o1 = snap_before(db, o1)
    before_o2 = snap_before(db, o2)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}, {"type": "work_order", "id": o2.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, o1) == before_o1
    # Then 11
    assert snap(db, o2) == before_o2


# [claude] MIM-D-70
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_70__transfers_sort_by_order_id_not_by_line_id(db, w1, u2, i1, m1, mk_stock, mk_transfer, mk_to_line):
    """MIM-D-70 — transfers sort by order id, not by line id.
    Rules: `delete_machine_item` R5a [BUG-1081], Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    to1 = mk_transfer("TO1")
    to2 = mk_transfer("TO2")
    mk_to_line(to2)
    mk_to_line(to1)
    before_mi = snap_before(db, mi)
    before_to1 = snap_before(db, to1)
    before_to2 = snap_before(db, to2)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "transfer_order", "id": to1.id}, {"type": "transfer_order", "id": to2.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, to1) == before_to1
    # Then 11
    assert snap(db, to2) == before_to2


# [claude] MIM-D-71
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_71__returns_sort_by_return_id_not_by_line_id(db, w1, u2, i1, m1, mk_stock, mk_po, mk_po_line, mk_return, mk_return_line):
    """MIM-D-71 — returns sort by return id, not by line id.
    Rules: `delete_machine_item` R5a [BUG-1081], Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    po1 = mk_po("PO1")
    pol1 = mk_po_line(po1)
    rt1 = mk_return(po1, "RT1")
    rt2 = mk_return(po1, "RT2")
    mk_return_line(rt2, pol1)
    mk_return_line(rt1, pol1)
    before_mi = snap_before(db, mi)
    before_rt1 = snap_before(db, rt1)
    before_rt2 = snap_before(db, rt2)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "purchase_return", "id": rt1.id}, {"type": "purchase_return", "id": rt2.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, rt1) == before_rt1
    # Then 11
    assert snap(db, rt2) == before_rt2


# [claude] MIM-D-72
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_72__types_sort_work_order_transfer_return_whatever_was_built_first(db, w1, u2, i1, m1, mk_stock, mk_order, mk_source_line, mk_transfer, mk_to_line, mk_po, mk_po_line, mk_return, mk_return_line):
    """MIM-D-72 — types sort work order, transfer, return, whatever was built first.
    Rules: `delete_machine_item` R5a [BUG-1081], R5 (a), R5 (c), R5 (d), Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    po1 = mk_po("PO1")
    pol1 = mk_po_line(po1)
    rt1 = mk_return(po1, "RT1")
    mk_return_line(rt1, pol1)
    to1 = mk_transfer("TO1")
    mk_to_line(to1)
    o1 = mk_order(m1, "O1", status="DRAFT")
    mk_source_line(o1)
    before_mi = snap_before(db, mi)
    before_o1 = snap_before(db, o1)
    before_to1 = snap_before(db, to1)
    before_rt1 = snap_before(db, rt1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}, {"type": "transfer_order", "id": to1.id}, {"type": "purchase_return", "id": rt1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, o1) == before_o1
    # Then 11
    assert snap(db, to1) == before_to1
    # Then 12
    assert snap(db, rt1) == before_rt1


# [claude] MIM-D-73
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_73__the_generic_entry_comes_last_after_every_type_though_its_row_was_built_first(db, w1, w2, u2, f9, i1, m1, m9, wt9, mk_stock, mk_order, mk_source_line, mk_transfer, mk_to_line, mk_po, mk_po_line, mk_return, mk_return_line):
    """MIM-D-73 — the generic entry comes last, after every type, though its row was built first.
    Rules: `delete_machine_item` R5a [BUG-1081], Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o9 = mk_order(m9, "O9", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    l9 = mk_source_line(o9, workspace_id=w2.id)
    po1 = mk_po("PO1")
    pol1 = mk_po_line(po1)
    rt1 = mk_return(po1, "RT1")
    mk_return_line(rt1, pol1)
    to1 = mk_transfer("TO1")
    mk_to_line(to1)
    o1 = mk_order(m1, "O1", status="DRAFT")
    mk_source_line(o1)
    before_mi = snap_before(db, mi)
    before_o9 = snap_before(db, o9)
    before_l9 = snap_before(db, l9)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}, {"type": "transfer_order", "id": to1.id}, {"type": "purchase_return", "id": rt1.id}, {"type": "other_workspace"}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, o9) == before_o9
    # Then 11
    assert snap(db, l9) == before_l9


# [claude] MIM-D-74
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_74__a_w2_row_of_another_type_goes_last_after_a_transfer(db, w1, w2, u2, f9, i1, m1, m9, wt9, mk_stock, mk_order, mk_source_line, mk_transfer, mk_to_line):
    """MIM-D-74 — a W2 row of another type goes last after a transfer.
    Rules: `delete_machine_item` R5a [BUG-1081], Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o9 = mk_order(m9, "O9", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    mk_source_line(o9, workspace_id=w2.id)
    to1 = mk_transfer("TO1")
    mk_to_line(to1)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "transfer_order", "id": to1.id}, {"type": "other_workspace"}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before


# [claude] MIM-D-75
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_75__a_w2_row_of_another_type_goes_last_after_a_return(db, w1, w2, u2, f9, i1, m1, m9, wt9, mk_stock, mk_order, mk_source_line, mk_po, mk_po_line, mk_return, mk_return_line):
    """MIM-D-75 — a W2 row of another type goes last after a return.
    Rules: `delete_machine_item` R5a [BUG-1081], Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o9 = mk_order(m9, "O9", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    mk_source_line(o9, workspace_id=w2.id)
    po1 = mk_po("PO1")
    pol1 = mk_po_line(po1)
    rt1 = mk_return(po1, "RT1")
    mk_return_line(rt1, pol1)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "purchase_return", "id": rt1.id}, {"type": "other_workspace"}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before


# [claude] MIM-D-76
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_76__a_w2_row_of_another_type_goes_last_after_a_work_order(db, w1, w2, u2, f9, i1, m1, st9, mk_stock, mk_order, mk_source_line, mk_transfer, mk_to_line):
    """MIM-D-76 — a W2 row of another type goes last after a work order.
    Rules: `delete_machine_item` R5a [BUG-1081], Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    to9 = mk_transfer("TO9", workspace_id=w2.id, current_status_id=st9.id, destination_location_id=f9.id)
    mk_to_line(to9, workspace_id=w2.id)
    o1 = mk_order(m1, "O1", status="DRAFT")
    mk_source_line(o1)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}, {"type": "other_workspace"}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before


# [claude] MIM-D-77
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_77__two_blocking_lines_on_one_order_give_one_entry(db, w1, u2, i1, m1, mk_stock, mk_order, mk_source_line):
    """MIM-D-77 — two blocking lines on one order give one entry.
    Rules: `delete_machine_item` R5a [BUG-1081], Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT")
    mk_source_line(o1)
    mk_source_line(o1)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before


# [claude] MIM-D-78
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_78__two_replace_lines_on_one_order_give_one_entry(db, w1, u2, i1, m1, mk_stock, mk_order, mk_replace_line):
    """MIM-D-78 — two REPLACE lines on one order give one entry.
    Rules: `delete_machine_item` R5a [BUG-1081], Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT")
    mk_replace_line(o1)
    mk_replace_line(o1)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before


# [claude] MIM-D-79
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_79__a_line_under_a_and_one_under_b_on_one_order_give_one_entry(db, w1, u2, i1, m1, mk_stock, mk_order, mk_source_line, mk_replace_line):
    """MIM-D-79 — a line under (a) and one under (b) on one order give one entry.
    Rules: `delete_machine_item` R5a [BUG-1081], Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT")
    mk_source_line(o1)
    mk_replace_line(o1)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before


# [claude] MIM-D-80
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_80__two_lines_on_one_transfer_give_one_entry(db, w1, u2, i1, m1, mk_stock, mk_transfer, mk_to_line):
    """MIM-D-80 — two lines on one transfer give one entry.
    Rules: `delete_machine_item` R5a [BUG-1081], Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    to1 = mk_transfer("TO1")
    mk_to_line(to1)
    mk_to_line(to1, line_number=2)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "transfer_order", "id": to1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before


# [claude] MIM-D-81
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_81__two_lines_on_one_return_give_one_entry(db, w1, u2, i1, m1, mk_stock, mk_po, mk_po_line, mk_return, mk_return_line):
    """MIM-D-81 — two lines on one return give one entry.
    Rules: `delete_machine_item` R5a [BUG-1081], Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    po1 = mk_po("PO1")
    pol1 = mk_po_line(po1)
    rt1 = mk_return(po1, "RT1")
    mk_return_line(rt1, pol1)
    mk_return_line(rt1, pol1)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "purchase_return", "id": rt1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before


# [claude] MIM-D-82
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_82__an_a_order_and_a_separate_b_order_give_two_entries(db, w1, u2, i1, m1, mk_stock, mk_order, mk_source_line, mk_replace_line):
    """MIM-D-82 — an (a) order and a separate (b) order give two entries.
    Rules: `delete_machine_item` R5a [BUG-1081], Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT")
    mk_source_line(o1)
    o2 = mk_order(m1, "O2", status="DRAFT")
    mk_replace_line(o2)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}, {"type": "work_order", "id": o2.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before


# [claude] MIM-D-83
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_83__two_w2_orders_give_one_generic_entry(db, w1, w2, u2, f9, i1, m1, m9, wt9, mk_stock, mk_order, mk_source_line):
    """MIM-D-83 — two W2 orders give one generic entry.
    Rules: `delete_machine_item` R5a [BUG-1081], Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m9, "O1", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    mk_source_line(o1, workspace_id=w2.id)
    o2 = mk_order(m9, "O2", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    mk_source_line(o2, workspace_id=w2.id)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before


# [claude] MIM-D-84
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_84__two_w2_lines_on_one_w2_order_give_one_generic_entry(db, w1, w2, u2, f9, i1, m1, m9, wt9, mk_stock, mk_order, mk_source_line):
    """MIM-D-84 — two W2 lines on one W2 order give one generic entry.
    Rules: `delete_machine_item` R5a [BUG-1081], Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m9, "O1", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    mk_source_line(o1, workspace_id=w2.id)
    mk_source_line(o1, workspace_id=w2.id)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before


# [claude] MIM-D-85
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_85__one_w2_row_of_each_type_gives_one_generic_entry(db, w1, w2, u2, f9, i1, m1, m9, wt9, st9, mk_stock, mk_order, mk_source_line, mk_replace_line, mk_transfer, mk_to_line, mk_po, mk_po_line, mk_return, mk_return_line):
    """MIM-D-85 — one W2 row of each type gives one generic entry.
    Rules: `delete_machine_item` R5a [BUG-1081], Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m9, "O1", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    mk_source_line(o1, workspace_id=w2.id)
    o2 = mk_order(m1, "O2", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    mk_replace_line(o2, workspace_id=w2.id)
    to1 = mk_transfer("TO1", workspace_id=w2.id, current_status_id=st9.id, destination_location_id=f9.id)
    mk_to_line(to1, workspace_id=w2.id)
    po1 = mk_po("PO1", workspace_id=w2.id, current_status_id=st9.id)
    pol1 = mk_po_line(po1, workspace_id=w2.id)
    rt1 = mk_return(po1, "RT1", workspace_id=w2.id)
    mk_return_line(rt1, pol1, workspace_id=w2.id)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before


# [claude] MIM-D-86
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_86__a_a_completed_order_is_not_listed_beside_an_open_one(db, w1, u2, i1, m1, mk_stock, mk_order, mk_source_line):
    """MIM-D-86 — (a) a COMPLETED order is not listed beside an open one.
    Rules: `delete_machine_item` R5 (a) [BUG-1081], R5a, R5b, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="COMPLETED")
    mk_source_line(o1)
    o2 = mk_order(m1, "O2", status="DRAFT")
    mk_source_line(o2)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o2.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before


# [claude] MIM-D-87
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_87__b_a_voided_order_is_not_listed_beside_an_open_one(db, w1, u2, i1, m1, mk_stock, mk_order, mk_replace_line):
    """MIM-D-87 — (b) a VOIDED order is not listed beside an open one.
    Rules: `delete_machine_item` R5 (b) [BUG-1081], R5a, R5b, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="VOIDED")
    mk_replace_line(o1)
    o2 = mk_order(m1, "O2", status="DRAFT")
    mk_replace_line(o2)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o2.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before


# [claude] MIM-D-88
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_88__c_a_completed_transfer_is_not_listed_beside_an_open_one(db, w1, u2, i1, m1, mk_stock, mk_transfer, mk_to_line):
    """MIM-D-88 — (c) a completed transfer is not listed beside an open one.
    Rules: `delete_machine_item` R5 (c) [BUG-1081], R5a, R5b, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    to1 = mk_transfer("TO1", completed_at=T9)
    mk_to_line(to1)
    to2 = mk_transfer("TO2")
    mk_to_line(to2)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "transfer_order", "id": to2.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before


# [claude] MIM-D-89
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_89__d_a_completed_return_is_not_listed_beside_a_pending_one(db, w1, u2, i1, m1, mk_stock, mk_po, mk_po_line, mk_return, mk_return_line):
    """MIM-D-89 — (d) a completed return is not listed beside a pending one.
    Rules: `delete_machine_item` R5 (d) [BUG-1081], R5a, R5b, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    po1 = mk_po("PO1")
    pol1 = mk_po_line(po1)
    rt1 = mk_return(po1, "RT1", status="completed")
    mk_return_line(rt1, pol1)
    rt2 = mk_return(po1, "RT2")
    mk_return_line(rt2, pol1)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "purchase_return", "id": rt2.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before


# [claude] MIM-D-90
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_90__a_a_w2_order_in_a_closed_state_adds_no_generic_entry_to_an_own_blocker(db, w1, w2, u2, f9, i1, m1, m9, wt9, mk_stock, mk_order, mk_source_line):
    """MIM-D-90 — (a) a W2 order in a closed state adds no generic entry to an own blocker.
    Rules: `delete_machine_item` R5 (a) [BUG-1081], R5a, R5b, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m9, "O1", status="COMPLETED", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    mk_source_line(o1, workspace_id=w2.id)
    o2 = mk_order(m1, "O2", status="DRAFT")
    mk_source_line(o2)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o2.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before


# [claude] MIM-D-91
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_91__b_a_w2_order_in_a_closed_state_adds_no_generic_entry_to_an_own_blocker(db, w1, w2, u2, f9, i1, m1, wt9, mk_stock, mk_order, mk_replace_line):
    """MIM-D-91 — (b) a W2 order in a closed state adds no generic entry to an own blocker.
    Rules: `delete_machine_item` R5 (b) [BUG-1081], R5a, R5b, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="VOIDED", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    mk_replace_line(o1, workspace_id=w2.id)
    o2 = mk_order(m1, "O2", status="DRAFT")
    mk_replace_line(o2)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o2.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before


# [claude] MIM-D-92
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_92__c_a_completed_w2_transfer_adds_no_generic_entry_to_an_own_blocker(db, w1, w2, u2, f9, i1, m1, st9, mk_stock, mk_transfer, mk_to_line):
    """MIM-D-92 — (c) a completed W2 transfer adds no generic entry to an own blocker.
    Rules: `delete_machine_item` R5 (c) [BUG-1081], R5a, R5b, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    to1 = mk_transfer("TO1", workspace_id=w2.id, current_status_id=st9.id, destination_location_id=f9.id, completed_at=T9)
    mk_to_line(to1, workspace_id=w2.id)
    to2 = mk_transfer("TO2")
    mk_to_line(to2)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "transfer_order", "id": to2.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before


# [claude] MIM-D-93
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_93__d_a_completed_w2_return_adds_no_generic_entry_to_an_own_blocker(db, w1, w2, u2, i1, m1, mk_stock, mk_po, mk_po_line, mk_return, mk_return_line):
    """MIM-D-93 — (d) a completed W2 return adds no generic entry to an own blocker.
    Rules: `delete_machine_item` R5 (d) [BUG-1081], R5a, R5b, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    po1 = mk_po("PO1")
    pol1 = mk_po_line(po1)
    rt1 = mk_return(po1, "RT1", workspace_id=w2.id, status="completed")
    mk_return_line(rt1, pol1, workspace_id=w2.id)
    po2 = mk_po("PO2")
    pol2 = mk_po_line(po2)
    rt2 = mk_return(po2, "RT2")
    mk_return_line(rt2, pol2)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "purchase_return", "id": rt2.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before


# [claude] MIM-D-94
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_94__a_an_own_closed_order_adds_nothing_to_a_w2_blocker(db, w1, w2, u2, f9, i1, m1, m9, wt9, mk_stock, mk_order, mk_source_line):
    """MIM-D-94 — (a) an own closed order adds nothing to a W2 blocker.
    Rules: `delete_machine_item` R5 (a) [BUG-1081], R5a, R5b, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="COMPLETED")
    mk_source_line(o1)
    o2 = mk_order(m9, "O2", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    mk_source_line(o2, workspace_id=w2.id)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before


# [claude] MIM-D-95
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_95__b_an_own_closed_order_adds_nothing_to_a_w2_blocker(db, w1, w2, u2, f9, i1, m1, wt9, mk_stock, mk_order, mk_replace_line):
    """MIM-D-95 — (b) an own closed order adds nothing to a W2 blocker.
    Rules: `delete_machine_item` R5 (b) [BUG-1081], R5a, R5b, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="VOIDED")
    mk_replace_line(o1)
    o2 = mk_order(m1, "O2", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    mk_replace_line(o2, workspace_id=w2.id)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before


# [claude] MIM-D-96
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_96__c_an_own_completed_transfer_adds_nothing_to_a_w2_blocker(db, w1, w2, u2, f9, i1, m1, st9, mk_stock, mk_transfer, mk_to_line):
    """MIM-D-96 — (c) an own completed transfer adds nothing to a W2 blocker.
    Rules: `delete_machine_item` R5 (c) [BUG-1081], R5a, R5b, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    to1 = mk_transfer("TO1", completed_at=T9)
    mk_to_line(to1)
    to2 = mk_transfer("TO2", workspace_id=w2.id, current_status_id=st9.id, destination_location_id=f9.id)
    mk_to_line(to2, workspace_id=w2.id)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before


# [claude] MIM-D-97
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_97__d_an_own_completed_return_adds_nothing_to_a_w2_blocker(db, w1, w2, u2, i1, m1, mk_stock, mk_po, mk_po_line, mk_return, mk_return_line):
    """MIM-D-97 — (d) an own completed return adds nothing to a W2 blocker.
    Rules: `delete_machine_item` R5 (d) [BUG-1081], R5a, R5b, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    po1 = mk_po("PO1")
    pol1 = mk_po_line(po1)
    rt1 = mk_return(po1, "RT1", status="completed")
    mk_return_line(rt1, pol1)
    po2 = mk_po("PO2")
    pol2 = mk_po_line(po2)
    rt2 = mk_return(po2, "RT2", workspace_id=w2.id)
    mk_return_line(rt2, pol2, workspace_id=w2.id)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before


# [claude] MIM-D-98
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_98__a_refused_row_with_qty_0_stays_and_books_nothing(db, w1, u2, i1, m1, mk_stock, mk_order, mk_source_line):
    """MIM-D-98 — a refused row with qty 0 stays and books nothing.
    Rules: `delete_machine_item` R5 (a) [BUG-1081], R5a, R5b, Errors row 3"""
    mi = mk_stock(m1, i1, qty=0)
    o1 = mk_order(m1, "O1", status="DRAFT")
    mk_source_line(o1)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before


# [claude] MIM-D-99
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_99__a_refused_row_with_a_negative_qty_stays_and_books_nothing(db, w1, u2, i1, m1, mk_stock, mk_order, mk_source_line):
    """MIM-D-99 — a refused row with a negative qty stays and books nothing.
    Rules: `delete_machine_item` R5 (a) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=-3)
    o1 = mk_order(m1, "O1", status="DRAFT")
    mk_source_line(o1)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before


# [claude] MIM-D-100
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_100__a_refused_row_keeps_its_target_and_defect_count(db, w1, u2, i1, m1, mk_stock, mk_order, mk_source_line):
    """MIM-D-100 — a refused row keeps its target and defect count.
    Rules: `delete_machine_item` R5 (a) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5, req_qty=7, defective_qty=1)
    o1 = mk_order(m1, "O1", status="DRAFT")
    mk_source_line(o1)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    row = reread(db, mi)
    assert row.qty == 5
    assert row.req_qty == 7
    assert row.defective_qty == 1


# [claude] MIM-D-101
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_101__a_refusal_leaves_earlier_ledger_rows_and_events_alone(db, w1, u2, i1, m1, mk_stock, mk_entry, mk_activity, mk_order, mk_source_line):
    """MIM-D-101 — a refusal leaves earlier ledger rows and events alone.
    Rules: `delete_machine_item` R5 (a) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    lg = mk_entry(m1, i1, performed_at=T9, avg_price_after=Decimal("5.00"), qty_after=5)
    ev = mk_activity(m1)
    o1 = mk_order(m1, "O1", status="DRAFT")
    mk_source_line(o1)
    before_mi = snap_before(db, mi)
    before_lg = snap_before(db, lg)
    before_ev = snap_before(db, ev)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, lg) == before_lg
    # Then 11
    assert snap(db, ev) == before_ev


# [claude] MIM-D-102
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_102__an_in_use_row_deleted_by_an_unknown_user_gets_the_refusal_not_a_database_error(db, w1, i1, m1, mk_stock, mk_order, mk_source_line):
    """MIM-D-102 — an in-use row deleted by an unknown user gets the refusal, not a database error.
    Rules: `delete_machine_item` R5 (a) [BUG-1081], R5a, R12, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT")
    l1 = mk_source_line(o1)
    before_mi = snap_before(db, mi)
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=MISSING)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, o1) == before_o1
    # Then 11
    assert snap(db, l1) == before_l1


# [claude] MIM-D-103
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_103__a_row_blocked_only_by_w2_rows_deleted_by_an_unknown_user_gets_the_generic_refusal(db, w1, w2, f9, i1, m1, m9, wt9, mk_stock, mk_order, mk_source_line):
    """MIM-D-103 — a row blocked only by W2 rows, deleted by an unknown user, gets the generic refusal.
    Rules: `delete_machine_item` R5 (a) [BUG-1081], R5a, R12, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m9, "O1", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    l1 = mk_source_line(o1, workspace_id=w2.id)
    before_mi = snap_before(db, mi)
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=MISSING)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, o1) == before_o1
    # Then 11
    assert snap(db, l1) == before_l1


# [claude] MIM-D-104
def test_mim_d_104__r1_before_r5_a_row_asked_for_from_another_workspace_is_the_404_whatever_blocks_it(db, w2, u2, i1, m1, mk_stock, mk_order, mk_source_line):
    """MIM-D-104 — R1 before R5: a row asked for from another workspace is the 404, whatever blocks it.
    Rules: `delete_machine_item` R1, R5, Errors row 1"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT")
    l1 = mk_source_line(o1)
    before_mi = snap_before(db, mi)
    before_l1 = snap_before(db, l1)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w2.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine item not found"
    # Then 4
    assert mi not in db.dirty
    # Then 5
    assert mi not in db.deleted
    # Then 6
    db.flush()
    # Then 7
    assert snap(db, mi) == before_mi
    # Then 8
    assert written(db) == before
    # Then 9
    assert snap(db, l1) == before_l1


# [claude] MIM-D-105
def test_mim_d_105__a_does_not_block_a_completed_order(db, w1, u2, i1, m1, mk_stock, mk_order, mk_source_line):
    """MIM-D-105 — (a) does not block: a `COMPLETED` order.
    Rules: `delete_machine_item` R5b, R5 (a)"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="COMPLETED")
    l1 = mk_source_line(o1)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-106
def test_mim_d_106__a_does_not_block_w2_order_and_line_a_completed_order(db, w1, w2, u2, f9, i1, m1, m9, wt9, mk_stock, mk_order, mk_source_line):
    """MIM-D-106 — (a) does not block: W2 order and line: a `COMPLETED` order.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m9, "O1", status="COMPLETED", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    l1 = mk_source_line(o1, workspace_id=w2.id)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-107
def test_mim_d_107__a_does_not_block_w1_line_on_a_w2_order_a_completed_order(db, w1, w2, u2, f9, i1, m1, m9, wt9, mk_stock, mk_order, mk_source_line):
    """MIM-D-107 — (a) does not block: W1 line on a W2 order: a `COMPLETED` order.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m9, "O1", status="COMPLETED", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    l1 = mk_source_line(o1)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-108
def test_mim_d_108__a_does_not_block_w2_line_on_a_w1_order_a_completed_order(db, w1, w2, u2, i1, m1, mk_stock, mk_order, mk_source_line):
    """MIM-D-108 — (a) does not block: W2 line on a W1 order: a `COMPLETED` order.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="COMPLETED")
    l1 = mk_source_line(o1, workspace_id=w2.id)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-109
def test_mim_d_109__a_does_not_block_a_voided_order(db, w1, u2, i1, m1, mk_stock, mk_order, mk_source_line):
    """MIM-D-109 — (a) does not block: a `VOIDED` order.
    Rules: `delete_machine_item` R5b, R5 (a)"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="VOIDED")
    l1 = mk_source_line(o1)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-110
def test_mim_d_110__a_does_not_block_w2_order_and_line_a_voided_order(db, w1, w2, u2, f9, i1, m1, m9, wt9, mk_stock, mk_order, mk_source_line):
    """MIM-D-110 — (a) does not block: W2 order and line: a `VOIDED` order.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m9, "O1", status="VOIDED", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    l1 = mk_source_line(o1, workspace_id=w2.id)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-111
def test_mim_d_111__a_does_not_block_w1_line_on_a_w2_order_a_voided_order(db, w1, w2, u2, f9, i1, m1, m9, wt9, mk_stock, mk_order, mk_source_line):
    """MIM-D-111 — (a) does not block: W1 line on a W2 order: a `VOIDED` order.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m9, "O1", status="VOIDED", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    l1 = mk_source_line(o1)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-112
def test_mim_d_112__a_does_not_block_w2_line_on_a_w1_order_a_voided_order(db, w1, w2, u2, i1, m1, mk_stock, mk_order, mk_source_line):
    """MIM-D-112 — (a) does not block: W2 line on a W1 order: a `VOIDED` order.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="VOIDED")
    l1 = mk_source_line(o1, workspace_id=w2.id)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-113
def test_mim_d_113__a_does_not_block_a_soft_deleted_order(db, w1, u2, i1, m1, mk_stock, mk_order, mk_source_line):
    """MIM-D-113 — (a) does not block: a soft-deleted order.
    Rules: `delete_machine_item` R5b, R5 (a)"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT", is_deleted=True)
    l1 = mk_source_line(o1)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-114
def test_mim_d_114__a_does_not_block_w2_order_and_line_a_soft_deleted_order(db, w1, w2, u2, f9, i1, m1, m9, wt9, mk_stock, mk_order, mk_source_line):
    """MIM-D-114 — (a) does not block: W2 order and line: a soft-deleted order.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m9, "O1", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id, is_deleted=True)
    l1 = mk_source_line(o1, workspace_id=w2.id)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-115
def test_mim_d_115__a_does_not_block_w1_line_on_a_w2_order_a_soft_deleted_order(db, w1, w2, u2, f9, i1, m1, m9, wt9, mk_stock, mk_order, mk_source_line):
    """MIM-D-115 — (a) does not block: W1 line on a W2 order: a soft-deleted order.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m9, "O1", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id, is_deleted=True)
    l1 = mk_source_line(o1)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-116
def test_mim_d_116__a_does_not_block_w2_line_on_a_w1_order_a_soft_deleted_order(db, w1, w2, u2, i1, m1, mk_stock, mk_order, mk_source_line):
    """MIM-D-116 — (a) does not block: W2 line on a W1 order: a soft-deleted order.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT", is_deleted=True)
    l1 = mk_source_line(o1, workspace_id=w2.id)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-117
def test_mim_d_117__a_does_not_block_a_soft_deleted_line(db, w1, u2, i1, m1, mk_stock, mk_order, mk_source_line):
    """MIM-D-117 — (a) does not block: a soft-deleted line.
    Rules: `delete_machine_item` R5b, R5 (a)"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT")
    l1 = mk_source_line(o1, is_deleted=True)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-118
def test_mim_d_118__a_does_not_block_w2_order_and_line_a_soft_deleted_line(db, w1, w2, u2, f9, i1, m1, m9, wt9, mk_stock, mk_order, mk_source_line):
    """MIM-D-118 — (a) does not block: W2 order and line: a soft-deleted line.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m9, "O1", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    l1 = mk_source_line(o1, workspace_id=w2.id, is_deleted=True)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-119
def test_mim_d_119__a_does_not_block_w1_line_on_a_w2_order_a_soft_deleted_line(db, w1, w2, u2, f9, i1, m1, m9, wt9, mk_stock, mk_order, mk_source_line):
    """MIM-D-119 — (a) does not block: W1 line on a W2 order: a soft-deleted line.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m9, "O1", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    l1 = mk_source_line(o1, is_deleted=True)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-120
def test_mim_d_120__a_does_not_block_w2_line_on_a_w1_order_a_soft_deleted_line(db, w1, w2, u2, i1, m1, mk_stock, mk_order, mk_source_line):
    """MIM-D-120 — (a) does not block: W2 line on a W1 order: a soft-deleted line.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT")
    l1 = mk_source_line(o1, workspace_id=w2.id, is_deleted=True)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-121
def test_mim_d_121__a_does_not_block_a_line_with_uses_inventory_false(db, w1, u2, i1, m1, mk_stock, mk_order, mk_source_line):
    """MIM-D-121 — (a) does not block: a line with `uses_inventory False`.
    Rules: `delete_machine_item` R5b, R5 (a)"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT")
    l1 = mk_source_line(o1, uses_inventory=False)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-122
def test_mim_d_122__a_does_not_block_w2_order_and_line_a_line_with_uses_inventory_false(db, w1, w2, u2, f9, i1, m1, m9, wt9, mk_stock, mk_order, mk_source_line):
    """MIM-D-122 — (a) does not block: W2 order and line: a line with `uses_inventory False`.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m9, "O1", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    l1 = mk_source_line(o1, workspace_id=w2.id, uses_inventory=False)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-123
def test_mim_d_123__a_does_not_block_w1_line_on_a_w2_order_a_line_with_uses_inventory_false(db, w1, w2, u2, f9, i1, m1, m9, wt9, mk_stock, mk_order, mk_source_line):
    """MIM-D-123 — (a) does not block: W1 line on a W2 order: a line with `uses_inventory False`.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m9, "O1", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    l1 = mk_source_line(o1, uses_inventory=False)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-124
def test_mim_d_124__a_does_not_block_w2_line_on_a_w1_order_a_line_with_uses_inventory_false(db, w1, w2, u2, i1, m1, mk_stock, mk_order, mk_source_line):
    """MIM-D-124 — (a) does not block: W2 line on a W1 order: a line with `uses_inventory False`.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT")
    l1 = mk_source_line(o1, workspace_id=w2.id, uses_inventory=False)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-125
def test_mim_d_125__a_does_not_block_a_consumed_line(db, w1, u2, i1, m1, mk_stock, mk_order, mk_source_line):
    """MIM-D-125 — (a) does not block: a consumed line.
    Rules: `delete_machine_item` R5b, R5 (a)"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT")
    l1 = mk_source_line(o1, consumed_at=T9)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-126
def test_mim_d_126__a_does_not_block_w2_order_and_line_a_consumed_line(db, w1, w2, u2, f9, i1, m1, m9, wt9, mk_stock, mk_order, mk_source_line):
    """MIM-D-126 — (a) does not block: W2 order and line: a consumed line.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m9, "O1", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    l1 = mk_source_line(o1, workspace_id=w2.id, consumed_at=T9)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-127
def test_mim_d_127__a_does_not_block_w1_line_on_a_w2_order_a_consumed_line(db, w1, w2, u2, f9, i1, m1, m9, wt9, mk_stock, mk_order, mk_source_line):
    """MIM-D-127 — (a) does not block: W1 line on a W2 order: a consumed line.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m9, "O1", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    l1 = mk_source_line(o1, consumed_at=T9)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-128
def test_mim_d_128__a_does_not_block_w2_line_on_a_w1_order_a_consumed_line(db, w1, w2, u2, i1, m1, mk_stock, mk_order, mk_source_line):
    """MIM-D-128 — (a) does not block: W2 line on a W1 order: a consumed line.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT")
    l1 = mk_source_line(o1, workspace_id=w2.id, consumed_at=T9)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-129
def test_mim_d_129__a_does_not_block_a_storage_source_with_the_machine_s_id(db, w1, u2, i1, m1, mk_stock, mk_order, mk_source_line):
    """MIM-D-129 — (a) does not block: a storage source with the machine's id.
    Rules: `delete_machine_item` R5b, R5 (a)"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT")
    l1 = mk_source_line(o1, source_location_type="storage")
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-130
def test_mim_d_130__a_does_not_block_w2_order_and_line_a_storage_source_with_the_machine_s_id(db, w1, w2, u2, f9, i1, m1, m9, wt9, mk_stock, mk_order, mk_source_line):
    """MIM-D-130 — (a) does not block: W2 order and line: a storage source with the machine's id.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m9, "O1", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    l1 = mk_source_line(o1, workspace_id=w2.id, source_location_type="storage")
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-131
def test_mim_d_131__a_does_not_block_w1_line_on_a_w2_order_a_storage_source_with_the_machine_s_id(db, w1, w2, u2, f9, i1, m1, m9, wt9, mk_stock, mk_order, mk_source_line):
    """MIM-D-131 — (a) does not block: W1 line on a W2 order: a storage source with the machine's id.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m9, "O1", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    l1 = mk_source_line(o1, source_location_type="storage")
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-132
def test_mim_d_132__a_does_not_block_w2_line_on_a_w1_order_a_storage_source_with_the_machine_s_id(db, w1, w2, u2, i1, m1, mk_stock, mk_order, mk_source_line):
    """MIM-D-132 — (a) does not block: W2 line on a W1 order: a storage source with the machine's id.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT")
    l1 = mk_source_line(o1, workspace_id=w2.id, source_location_type="storage")
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-133
def test_mim_d_133__a_does_not_block_a_source_on_another_machine(db, w1, u2, i1, m1, m2, mk_stock, mk_order, mk_source_line):
    """MIM-D-133 — (a) does not block: a source on another machine.
    Rules: `delete_machine_item` R5b, R5 (a)"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT")
    l1 = mk_source_line(o1, source_location_id=m2.id)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-134
def test_mim_d_134__a_does_not_block_w2_order_and_line_a_source_on_another_machine(db, w1, w2, u2, f9, i1, m1, m2, m9, wt9, mk_stock, mk_order, mk_source_line):
    """MIM-D-134 — (a) does not block: W2 order and line: a source on another machine.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m9, "O1", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    l1 = mk_source_line(o1, workspace_id=w2.id, source_location_id=m2.id)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-135
def test_mim_d_135__a_does_not_block_w1_line_on_a_w2_order_a_source_on_another_machine(db, w1, w2, u2, f9, i1, m1, m2, m9, wt9, mk_stock, mk_order, mk_source_line):
    """MIM-D-135 — (a) does not block: W1 line on a W2 order: a source on another machine.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m9, "O1", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    l1 = mk_source_line(o1, source_location_id=m2.id)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-136
def test_mim_d_136__a_does_not_block_w2_line_on_a_w1_order_a_source_on_another_machine(db, w1, w2, u2, i1, m1, m2, mk_stock, mk_order, mk_source_line):
    """MIM-D-136 — (a) does not block: W2 line on a W1 order: a source on another machine.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT")
    l1 = mk_source_line(o1, workspace_id=w2.id, source_location_id=m2.id)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-137
def test_mim_d_137__a_does_not_block_a_line_of_another_item(db, w1, u2, i1, i2, m1, mk_stock, mk_order, mk_source_line):
    """MIM-D-137 — (a) does not block: a line of another item.
    Rules: `delete_machine_item` R5b, R5 (a)"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT")
    l1 = mk_source_line(o1, item_id=i2.id)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-138
def test_mim_d_138__a_does_not_block_w2_order_and_line_a_line_of_another_item(db, w1, w2, u2, f9, i1, i2, m1, m9, wt9, mk_stock, mk_order, mk_source_line):
    """MIM-D-138 — (a) does not block: W2 order and line: a line of another item.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m9, "O1", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    l1 = mk_source_line(o1, workspace_id=w2.id, item_id=i2.id)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-139
def test_mim_d_139__a_does_not_block_w1_line_on_a_w2_order_a_line_of_another_item(db, w1, w2, u2, f9, i1, i2, m1, m9, wt9, mk_stock, mk_order, mk_source_line):
    """MIM-D-139 — (a) does not block: W1 line on a W2 order: a line of another item.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m9, "O1", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    l1 = mk_source_line(o1, item_id=i2.id)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-140
def test_mim_d_140__a_does_not_block_w2_line_on_a_w1_order_a_line_of_another_item(db, w1, w2, u2, i1, i2, m1, mk_stock, mk_order, mk_source_line):
    """MIM-D-140 — (a) does not block: W2 line on a W1 order: a line of another item.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT")
    l1 = mk_source_line(o1, workspace_id=w2.id, item_id=i2.id)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-141
def test_mim_d_141__b_does_not_block_a_completed_order(db, w1, u2, i1, m1, mk_stock, mk_order, mk_replace_line):
    """MIM-D-141 — (b) does not block: a `COMPLETED` order.
    Rules: `delete_machine_item` R5b, R5 (b)"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="COMPLETED")
    l1 = mk_replace_line(o1)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-142
def test_mim_d_142__b_does_not_block_w2_order_and_line_a_completed_order(db, w1, w2, u2, f9, i1, m1, wt9, mk_stock, mk_order, mk_replace_line):
    """MIM-D-142 — (b) does not block: W2 order and line: a `COMPLETED` order.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="COMPLETED", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    l1 = mk_replace_line(o1, workspace_id=w2.id)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-143
def test_mim_d_143__b_does_not_block_w1_line_on_a_w2_order_a_completed_order(db, w1, w2, u2, f9, i1, m1, wt9, mk_stock, mk_order, mk_replace_line):
    """MIM-D-143 — (b) does not block: W1 line on a W2 order: a `COMPLETED` order.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="COMPLETED", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    l1 = mk_replace_line(o1)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-144
def test_mim_d_144__b_does_not_block_w2_line_on_a_w1_order_a_completed_order(db, w1, w2, u2, i1, m1, mk_stock, mk_order, mk_replace_line):
    """MIM-D-144 — (b) does not block: W2 line on a W1 order: a `COMPLETED` order.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="COMPLETED")
    l1 = mk_replace_line(o1, workspace_id=w2.id)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-145
def test_mim_d_145__b_does_not_block_a_voided_order(db, w1, u2, i1, m1, mk_stock, mk_order, mk_replace_line):
    """MIM-D-145 — (b) does not block: a `VOIDED` order.
    Rules: `delete_machine_item` R5b, R5 (b)"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="VOIDED")
    l1 = mk_replace_line(o1)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-146
def test_mim_d_146__b_does_not_block_w2_order_and_line_a_voided_order(db, w1, w2, u2, f9, i1, m1, wt9, mk_stock, mk_order, mk_replace_line):
    """MIM-D-146 — (b) does not block: W2 order and line: a `VOIDED` order.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="VOIDED", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    l1 = mk_replace_line(o1, workspace_id=w2.id)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-147
def test_mim_d_147__b_does_not_block_w1_line_on_a_w2_order_a_voided_order(db, w1, w2, u2, f9, i1, m1, wt9, mk_stock, mk_order, mk_replace_line):
    """MIM-D-147 — (b) does not block: W1 line on a W2 order: a `VOIDED` order.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="VOIDED", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    l1 = mk_replace_line(o1)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-148
def test_mim_d_148__b_does_not_block_w2_line_on_a_w1_order_a_voided_order(db, w1, w2, u2, i1, m1, mk_stock, mk_order, mk_replace_line):
    """MIM-D-148 — (b) does not block: W2 line on a W1 order: a `VOIDED` order.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="VOIDED")
    l1 = mk_replace_line(o1, workspace_id=w2.id)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-149
def test_mim_d_149__b_does_not_block_a_soft_deleted_order(db, w1, u2, i1, m1, mk_stock, mk_order, mk_replace_line):
    """MIM-D-149 — (b) does not block: a soft-deleted order.
    Rules: `delete_machine_item` R5b, R5 (b)"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT", is_deleted=True)
    l1 = mk_replace_line(o1)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-150
def test_mim_d_150__b_does_not_block_w2_order_and_line_a_soft_deleted_order(db, w1, w2, u2, f9, i1, m1, wt9, mk_stock, mk_order, mk_replace_line):
    """MIM-D-150 — (b) does not block: W2 order and line: a soft-deleted order.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id, is_deleted=True)
    l1 = mk_replace_line(o1, workspace_id=w2.id)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-151
def test_mim_d_151__b_does_not_block_w1_line_on_a_w2_order_a_soft_deleted_order(db, w1, w2, u2, f9, i1, m1, wt9, mk_stock, mk_order, mk_replace_line):
    """MIM-D-151 — (b) does not block: W1 line on a W2 order: a soft-deleted order.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id, is_deleted=True)
    l1 = mk_replace_line(o1)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-152
def test_mim_d_152__b_does_not_block_w2_line_on_a_w1_order_a_soft_deleted_order(db, w1, w2, u2, i1, m1, mk_stock, mk_order, mk_replace_line):
    """MIM-D-152 — (b) does not block: W2 line on a W1 order: a soft-deleted order.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT", is_deleted=True)
    l1 = mk_replace_line(o1, workspace_id=w2.id)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-153
def test_mim_d_153__b_does_not_block_a_soft_deleted_line(db, w1, u2, i1, m1, mk_stock, mk_order, mk_replace_line):
    """MIM-D-153 — (b) does not block: a soft-deleted line.
    Rules: `delete_machine_item` R5b, R5 (b)"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT")
    l1 = mk_replace_line(o1, is_deleted=True)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-154
def test_mim_d_154__b_does_not_block_w2_order_and_line_a_soft_deleted_line(db, w1, w2, u2, f9, i1, m1, wt9, mk_stock, mk_order, mk_replace_line):
    """MIM-D-154 — (b) does not block: W2 order and line: a soft-deleted line.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    l1 = mk_replace_line(o1, workspace_id=w2.id, is_deleted=True)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-155
def test_mim_d_155__b_does_not_block_w1_line_on_a_w2_order_a_soft_deleted_line(db, w1, w2, u2, f9, i1, m1, wt9, mk_stock, mk_order, mk_replace_line):
    """MIM-D-155 — (b) does not block: W1 line on a W2 order: a soft-deleted line.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    l1 = mk_replace_line(o1, is_deleted=True)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-156
def test_mim_d_156__b_does_not_block_w2_line_on_a_w1_order_a_soft_deleted_line(db, w1, w2, u2, i1, m1, mk_stock, mk_order, mk_replace_line):
    """MIM-D-156 — (b) does not block: W2 line on a W1 order: a soft-deleted line.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT")
    l1 = mk_replace_line(o1, workspace_id=w2.id, is_deleted=True)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-157
def test_mim_d_157__b_does_not_block_a_line_that_is_not_replace(db, w1, u2, i1, m1, mk_stock, mk_order, mk_replace_line):
    """MIM-D-157 — (b) does not block: a line that is not REPLACE.
    Rules: `delete_machine_item` R5b, R5 (b)"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT")
    l1 = mk_replace_line(o1, action_type="INSTALL")
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-158
def test_mim_d_158__b_does_not_block_w2_order_and_line_a_line_that_is_not_replace(db, w1, w2, u2, f9, i1, m1, wt9, mk_stock, mk_order, mk_replace_line):
    """MIM-D-158 — (b) does not block: W2 order and line: a line that is not REPLACE.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    l1 = mk_replace_line(o1, workspace_id=w2.id, action_type="INSTALL")
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-159
def test_mim_d_159__b_does_not_block_w1_line_on_a_w2_order_a_line_that_is_not_replace(db, w1, w2, u2, f9, i1, m1, wt9, mk_stock, mk_order, mk_replace_line):
    """MIM-D-159 — (b) does not block: W1 line on a W2 order: a line that is not REPLACE.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    l1 = mk_replace_line(o1, action_type="INSTALL")
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-160
def test_mim_d_160__b_does_not_block_w2_line_on_a_w1_order_a_line_that_is_not_replace(db, w1, w2, u2, i1, m1, mk_stock, mk_order, mk_replace_line):
    """MIM-D-160 — (b) does not block: W2 line on a W1 order: a line that is not REPLACE.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT")
    l1 = mk_replace_line(o1, workspace_id=w2.id, action_type="INSTALL")
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-161
def test_mim_d_161__b_does_not_block_a_replace_line_for_another_item(db, w1, u2, i1, ix, m1, mk_stock, mk_order, mk_replace_line):
    """MIM-D-161 — (b) does not block: a REPLACE line for another item.
    Rules: `delete_machine_item` R5b, R5 (b)"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT")
    l1 = mk_replace_line(o1, replaced_item_id=ix.id)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-162
def test_mim_d_162__b_does_not_block_w2_order_and_line_a_replace_line_for_another_item(db, w1, w2, u2, f9, i1, ix, m1, wt9, mk_stock, mk_order, mk_replace_line):
    """MIM-D-162 — (b) does not block: W2 order and line: a REPLACE line for another item.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    l1 = mk_replace_line(o1, workspace_id=w2.id, replaced_item_id=ix.id)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-163
def test_mim_d_163__b_does_not_block_w1_line_on_a_w2_order_a_replace_line_for_another_item(db, w1, w2, u2, f9, i1, ix, m1, wt9, mk_stock, mk_order, mk_replace_line):
    """MIM-D-163 — (b) does not block: W1 line on a W2 order: a REPLACE line for another item.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    l1 = mk_replace_line(o1, replaced_item_id=ix.id)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-164
def test_mim_d_164__b_does_not_block_w2_line_on_a_w1_order_a_replace_line_for_another_item(db, w1, w2, u2, i1, ix, m1, mk_stock, mk_order, mk_replace_line):
    """MIM-D-164 — (b) does not block: W2 line on a W1 order: a REPLACE line for another item.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT")
    l1 = mk_replace_line(o1, workspace_id=w2.id, replaced_item_id=ix.id)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-165
def test_mim_d_165__b_does_not_block_an_order_of_another_machine(db, w1, u2, i1, m1, m2, mk_stock, mk_order, mk_replace_line):
    """MIM-D-165 — (b) does not block: an order of another machine.
    Rules: `delete_machine_item` R5b, R5 (b)"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m2, "O1", status="DRAFT")
    l1 = mk_replace_line(o1)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-166
def test_mim_d_166__b_does_not_block_w2_order_and_line_an_order_of_another_machine(db, w1, w2, u2, f9, i1, m1, m2, wt9, mk_stock, mk_order, mk_replace_line):
    """MIM-D-166 — (b) does not block: W2 order and line: an order of another machine.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m2, "O1", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    l1 = mk_replace_line(o1, workspace_id=w2.id)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-167
def test_mim_d_167__b_does_not_block_w1_line_on_a_w2_order_an_order_of_another_machine(db, w1, w2, u2, f9, i1, m1, m2, wt9, mk_stock, mk_order, mk_replace_line):
    """MIM-D-167 — (b) does not block: W1 line on a W2 order: an order of another machine.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m2, "O1", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    l1 = mk_replace_line(o1)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-168
def test_mim_d_168__b_does_not_block_w2_line_on_a_w1_order_an_order_of_another_machine(db, w1, w2, u2, i1, m1, m2, mk_stock, mk_order, mk_replace_line):
    """MIM-D-168 — (b) does not block: W2 line on a W1 order: an order of another machine.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m2, "O1", status="DRAFT")
    l1 = mk_replace_line(o1, workspace_id=w2.id)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-169
def test_mim_d_169__b_does_not_block_an_order_with_no_machine(db, w1, u2, i1, m1, mk_stock, mk_order, mk_replace_line):
    """MIM-D-169 — (b) does not block: an order with no machine.
    Rules: `delete_machine_item` R5b, R5 (b)"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT", machine_id=None)
    l1 = mk_replace_line(o1)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-170
def test_mim_d_170__b_does_not_block_w2_order_and_line_an_order_with_no_machine(db, w1, w2, u2, f9, i1, m1, wt9, mk_stock, mk_order, mk_replace_line):
    """MIM-D-170 — (b) does not block: W2 order and line: an order with no machine.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id, machine_id=None)
    l1 = mk_replace_line(o1, workspace_id=w2.id)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-171
def test_mim_d_171__b_does_not_block_w1_line_on_a_w2_order_an_order_with_no_machine(db, w1, w2, u2, f9, i1, m1, wt9, mk_stock, mk_order, mk_replace_line):
    """MIM-D-171 — (b) does not block: W1 line on a W2 order: an order with no machine.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id, machine_id=None)
    l1 = mk_replace_line(o1)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-172
def test_mim_d_172__b_does_not_block_w2_line_on_a_w1_order_an_order_with_no_machine(db, w1, w2, u2, i1, m1, mk_stock, mk_order, mk_replace_line):
    """MIM-D-172 — (b) does not block: W2 line on a W1 order: an order with no machine.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT", machine_id=None)
    l1 = mk_replace_line(o1, workspace_id=w2.id)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-173
def test_mim_d_173__c_does_not_block_a_completed_transfer(db, w1, u2, i1, m1, mk_stock, mk_transfer, mk_to_line):
    """MIM-D-173 — (c) does not block: a completed transfer.
    Rules: `delete_machine_item` R5b, R5 (c)"""
    mi = mk_stock(m1, i1, qty=5)
    to1 = mk_transfer("TO1", completed_at=T9)
    tl1 = mk_to_line(to1)
    mi_id = mi.id
    before_to1 = snap_before(db, to1)
    before_tl1 = snap_before(db, tl1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, to1) == before_to1
    # Then 5
    assert snap(db, tl1) == before_tl1


# [claude] MIM-D-174
def test_mim_d_174__c_does_not_block_w2_transfer_and_line_a_completed_transfer(db, w1, w2, u2, f9, i1, m1, st9, mk_stock, mk_transfer, mk_to_line):
    """MIM-D-174 — (c) does not block: W2 transfer and line: a completed transfer.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    to1 = mk_transfer("TO1", workspace_id=w2.id, current_status_id=st9.id, destination_location_id=f9.id, completed_at=T9)
    tl1 = mk_to_line(to1, workspace_id=w2.id)
    mi_id = mi.id
    before_to1 = snap_before(db, to1)
    before_tl1 = snap_before(db, tl1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, to1) == before_to1
    # Then 5
    assert snap(db, tl1) == before_tl1


# [claude] MIM-D-175
def test_mim_d_175__c_does_not_block_w1_line_on_a_w2_transfer_a_completed_transfer(db, w1, w2, u2, f9, i1, m1, st9, mk_stock, mk_transfer, mk_to_line):
    """MIM-D-175 — (c) does not block: W1 line on a W2 transfer: a completed transfer.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    to1 = mk_transfer("TO1", workspace_id=w2.id, current_status_id=st9.id, destination_location_id=f9.id, completed_at=T9)
    tl1 = mk_to_line(to1)
    mi_id = mi.id
    before_to1 = snap_before(db, to1)
    before_tl1 = snap_before(db, tl1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, to1) == before_to1
    # Then 5
    assert snap(db, tl1) == before_tl1


# [claude] MIM-D-176
def test_mim_d_176__c_does_not_block_w2_line_on_a_w1_transfer_a_completed_transfer(db, w1, w2, u2, i1, m1, mk_stock, mk_transfer, mk_to_line):
    """MIM-D-176 — (c) does not block: W2 line on a W1 transfer: a completed transfer.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    to1 = mk_transfer("TO1", completed_at=T9)
    tl1 = mk_to_line(to1, workspace_id=w2.id)
    mi_id = mi.id
    before_to1 = snap_before(db, to1)
    before_tl1 = snap_before(db, tl1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, to1) == before_to1
    # Then 5
    assert snap(db, tl1) == before_tl1


# [claude] MIM-D-177
def test_mim_d_177__c_does_not_block_a_transfer_into_the_machine(db, w1, u2, f1, i1, m1, mk_stock, mk_transfer, mk_to_line):
    """MIM-D-177 — (c) does not block: a transfer into the machine.
    Rules: `delete_machine_item` R5b, R5 (c)"""
    mi = mk_stock(m1, i1, qty=5)
    to1 = mk_transfer("TO1", source_location_type="storage", source_location_id=f1.id, destination_location_type="machine", destination_location_id=m1.id)
    tl1 = mk_to_line(to1)
    mi_id = mi.id
    before_to1 = snap_before(db, to1)
    before_tl1 = snap_before(db, tl1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, to1) == before_to1
    # Then 5
    assert snap(db, tl1) == before_tl1


# [claude] MIM-D-178
def test_mim_d_178__c_does_not_block_w2_transfer_and_line_a_transfer_into_the_machine(db, w1, w2, u2, f1, i1, m1, st9, mk_stock, mk_transfer, mk_to_line):
    """MIM-D-178 — (c) does not block: W2 transfer and line: a transfer into the machine.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    to1 = mk_transfer("TO1", workspace_id=w2.id, current_status_id=st9.id, source_location_type="storage", source_location_id=f1.id, destination_location_type="machine", destination_location_id=m1.id)
    tl1 = mk_to_line(to1, workspace_id=w2.id)
    mi_id = mi.id
    before_to1 = snap_before(db, to1)
    before_tl1 = snap_before(db, tl1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, to1) == before_to1
    # Then 5
    assert snap(db, tl1) == before_tl1


# [claude] MIM-D-179
def test_mim_d_179__c_does_not_block_w1_line_on_a_w2_transfer_a_transfer_into_the_machine(db, w1, w2, u2, f1, i1, m1, st9, mk_stock, mk_transfer, mk_to_line):
    """MIM-D-179 — (c) does not block: W1 line on a W2 transfer: a transfer into the machine.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    to1 = mk_transfer("TO1", workspace_id=w2.id, current_status_id=st9.id, source_location_type="storage", source_location_id=f1.id, destination_location_type="machine", destination_location_id=m1.id)
    tl1 = mk_to_line(to1)
    mi_id = mi.id
    before_to1 = snap_before(db, to1)
    before_tl1 = snap_before(db, tl1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, to1) == before_to1
    # Then 5
    assert snap(db, tl1) == before_tl1


# [claude] MIM-D-180
def test_mim_d_180__c_does_not_block_w2_line_on_a_w1_transfer_a_transfer_into_the_machine(db, w1, w2, u2, f1, i1, m1, mk_stock, mk_transfer, mk_to_line):
    """MIM-D-180 — (c) does not block: W2 line on a W1 transfer: a transfer into the machine.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    to1 = mk_transfer("TO1", source_location_type="storage", source_location_id=f1.id, destination_location_type="machine", destination_location_id=m1.id)
    tl1 = mk_to_line(to1, workspace_id=w2.id)
    mi_id = mi.id
    before_to1 = snap_before(db, to1)
    before_tl1 = snap_before(db, tl1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, to1) == before_to1
    # Then 5
    assert snap(db, tl1) == before_tl1


# [claude] MIM-D-181
def test_mim_d_181__c_does_not_block_a_storage_source_with_the_machine_s_id(db, w1, u2, i1, m1, mk_stock, mk_transfer, mk_to_line):
    """MIM-D-181 — (c) does not block: a storage source with the machine's id.
    Rules: `delete_machine_item` R5b, R5 (c)"""
    mi = mk_stock(m1, i1, qty=5)
    to1 = mk_transfer("TO1", source_location_type="storage")
    tl1 = mk_to_line(to1)
    mi_id = mi.id
    before_to1 = snap_before(db, to1)
    before_tl1 = snap_before(db, tl1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, to1) == before_to1
    # Then 5
    assert snap(db, tl1) == before_tl1


# [claude] MIM-D-182
def test_mim_d_182__c_does_not_block_w2_transfer_and_line_a_storage_source_with_the_machine_s_id(db, w1, w2, u2, f9, i1, m1, st9, mk_stock, mk_transfer, mk_to_line):
    """MIM-D-182 — (c) does not block: W2 transfer and line: a storage source with the machine's id.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    to1 = mk_transfer("TO1", workspace_id=w2.id, current_status_id=st9.id, destination_location_id=f9.id, source_location_type="storage")
    tl1 = mk_to_line(to1, workspace_id=w2.id)
    mi_id = mi.id
    before_to1 = snap_before(db, to1)
    before_tl1 = snap_before(db, tl1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, to1) == before_to1
    # Then 5
    assert snap(db, tl1) == before_tl1


# [claude] MIM-D-183
def test_mim_d_183__c_does_not_block_w1_line_on_a_w2_transfer_a_storage_source_with_the_machine_s_id(db, w1, w2, u2, f9, i1, m1, st9, mk_stock, mk_transfer, mk_to_line):
    """MIM-D-183 — (c) does not block: W1 line on a W2 transfer: a storage source with the machine's id.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    to1 = mk_transfer("TO1", workspace_id=w2.id, current_status_id=st9.id, destination_location_id=f9.id, source_location_type="storage")
    tl1 = mk_to_line(to1)
    mi_id = mi.id
    before_to1 = snap_before(db, to1)
    before_tl1 = snap_before(db, tl1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, to1) == before_to1
    # Then 5
    assert snap(db, tl1) == before_tl1


# [claude] MIM-D-184
def test_mim_d_184__c_does_not_block_w2_line_on_a_w1_transfer_a_storage_source_with_the_machine_s_id(db, w1, w2, u2, i1, m1, mk_stock, mk_transfer, mk_to_line):
    """MIM-D-184 — (c) does not block: W2 line on a W1 transfer: a storage source with the machine's id.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    to1 = mk_transfer("TO1", source_location_type="storage")
    tl1 = mk_to_line(to1, workspace_id=w2.id)
    mi_id = mi.id
    before_to1 = snap_before(db, to1)
    before_tl1 = snap_before(db, tl1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, to1) == before_to1
    # Then 5
    assert snap(db, tl1) == before_tl1


# [claude] MIM-D-185
def test_mim_d_185__c_does_not_block_a_transfer_out_of_another_machine(db, w1, u2, i1, m1, m2, mk_stock, mk_transfer, mk_to_line):
    """MIM-D-185 — (c) does not block: a transfer out of another machine.
    Rules: `delete_machine_item` R5b, R5 (c)"""
    mi = mk_stock(m1, i1, qty=5)
    to1 = mk_transfer("TO1", source_location_id=m2.id)
    tl1 = mk_to_line(to1)
    mi_id = mi.id
    before_to1 = snap_before(db, to1)
    before_tl1 = snap_before(db, tl1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, to1) == before_to1
    # Then 5
    assert snap(db, tl1) == before_tl1


# [claude] MIM-D-186
def test_mim_d_186__c_does_not_block_w2_transfer_and_line_a_transfer_out_of_another_machine(db, w1, w2, u2, f9, i1, m1, m2, st9, mk_stock, mk_transfer, mk_to_line):
    """MIM-D-186 — (c) does not block: W2 transfer and line: a transfer out of another machine.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    to1 = mk_transfer("TO1", workspace_id=w2.id, current_status_id=st9.id, destination_location_id=f9.id, source_location_id=m2.id)
    tl1 = mk_to_line(to1, workspace_id=w2.id)
    mi_id = mi.id
    before_to1 = snap_before(db, to1)
    before_tl1 = snap_before(db, tl1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, to1) == before_to1
    # Then 5
    assert snap(db, tl1) == before_tl1


# [claude] MIM-D-187
def test_mim_d_187__c_does_not_block_w1_line_on_a_w2_transfer_a_transfer_out_of_another_machine(db, w1, w2, u2, f9, i1, m1, m2, st9, mk_stock, mk_transfer, mk_to_line):
    """MIM-D-187 — (c) does not block: W1 line on a W2 transfer: a transfer out of another machine.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    to1 = mk_transfer("TO1", workspace_id=w2.id, current_status_id=st9.id, destination_location_id=f9.id, source_location_id=m2.id)
    tl1 = mk_to_line(to1)
    mi_id = mi.id
    before_to1 = snap_before(db, to1)
    before_tl1 = snap_before(db, tl1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, to1) == before_to1
    # Then 5
    assert snap(db, tl1) == before_tl1


# [claude] MIM-D-188
def test_mim_d_188__c_does_not_block_w2_line_on_a_w1_transfer_a_transfer_out_of_another_machine(db, w1, w2, u2, i1, m1, m2, mk_stock, mk_transfer, mk_to_line):
    """MIM-D-188 — (c) does not block: W2 line on a W1 transfer: a transfer out of another machine.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    to1 = mk_transfer("TO1", source_location_id=m2.id)
    tl1 = mk_to_line(to1, workspace_id=w2.id)
    mi_id = mi.id
    before_to1 = snap_before(db, to1)
    before_tl1 = snap_before(db, tl1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, to1) == before_to1
    # Then 5
    assert snap(db, tl1) == before_tl1


# [claude] MIM-D-189
def test_mim_d_189__c_does_not_block_a_line_of_another_item(db, w1, u2, i1, i2, m1, mk_stock, mk_transfer, mk_to_line):
    """MIM-D-189 — (c) does not block: a line of another item.
    Rules: `delete_machine_item` R5b, R5 (c)"""
    mi = mk_stock(m1, i1, qty=5)
    to1 = mk_transfer("TO1")
    tl1 = mk_to_line(to1, item_id=i2.id)
    mi_id = mi.id
    before_to1 = snap_before(db, to1)
    before_tl1 = snap_before(db, tl1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, to1) == before_to1
    # Then 5
    assert snap(db, tl1) == before_tl1


# [claude] MIM-D-190
def test_mim_d_190__c_does_not_block_w2_transfer_and_line_a_line_of_another_item(db, w1, w2, u2, f9, i1, i2, m1, st9, mk_stock, mk_transfer, mk_to_line):
    """MIM-D-190 — (c) does not block: W2 transfer and line: a line of another item.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    to1 = mk_transfer("TO1", workspace_id=w2.id, current_status_id=st9.id, destination_location_id=f9.id)
    tl1 = mk_to_line(to1, workspace_id=w2.id, item_id=i2.id)
    mi_id = mi.id
    before_to1 = snap_before(db, to1)
    before_tl1 = snap_before(db, tl1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, to1) == before_to1
    # Then 5
    assert snap(db, tl1) == before_tl1


# [claude] MIM-D-191
def test_mim_d_191__c_does_not_block_w1_line_on_a_w2_transfer_a_line_of_another_item(db, w1, w2, u2, f9, i1, i2, m1, st9, mk_stock, mk_transfer, mk_to_line):
    """MIM-D-191 — (c) does not block: W1 line on a W2 transfer: a line of another item.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    to1 = mk_transfer("TO1", workspace_id=w2.id, current_status_id=st9.id, destination_location_id=f9.id)
    tl1 = mk_to_line(to1, item_id=i2.id)
    mi_id = mi.id
    before_to1 = snap_before(db, to1)
    before_tl1 = snap_before(db, tl1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, to1) == before_to1
    # Then 5
    assert snap(db, tl1) == before_tl1


# [claude] MIM-D-192
def test_mim_d_192__c_does_not_block_w2_line_on_a_w1_transfer_a_line_of_another_item(db, w1, w2, u2, i1, i2, m1, mk_stock, mk_transfer, mk_to_line):
    """MIM-D-192 — (c) does not block: W2 line on a W1 transfer: a line of another item.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    to1 = mk_transfer("TO1")
    tl1 = mk_to_line(to1, workspace_id=w2.id, item_id=i2.id)
    mi_id = mi.id
    before_to1 = snap_before(db, to1)
    before_tl1 = snap_before(db, tl1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, to1) == before_to1
    # Then 5
    assert snap(db, tl1) == before_tl1


# [claude] MIM-D-193
def test_mim_d_193__d_does_not_block_a_completed_return(db, w1, u2, i1, m1, mk_stock, mk_po, mk_po_line, mk_return, mk_return_line):
    """MIM-D-193 — (d) does not block: a `completed` return.
    Rules: `delete_machine_item` R5b, R5 (d)"""
    mi = mk_stock(m1, i1, qty=5)
    po1 = mk_po("PO1")
    pol1 = mk_po_line(po1)
    rt1 = mk_return(po1, "RT1", status="completed")
    rl1 = mk_return_line(rt1, pol1)
    mi_id = mi.id
    before_rt1 = snap_before(db, rt1)
    before_rl1 = snap_before(db, rl1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, rt1) == before_rt1
    # Then 5
    assert snap(db, rl1) == before_rl1


# [claude] MIM-D-194
def test_mim_d_194__d_does_not_block_all_of_w2_a_completed_return(db, w1, w2, u2, i1, m1, st9, mk_stock, mk_po, mk_po_line, mk_return, mk_return_line):
    """MIM-D-194 — (d) does not block: all of W2: a `completed` return.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    po1 = mk_po("PO1", workspace_id=w2.id, current_status_id=st9.id)
    pol1 = mk_po_line(po1, workspace_id=w2.id)
    rt1 = mk_return(po1, "RT1", workspace_id=w2.id, status="completed")
    rl1 = mk_return_line(rt1, pol1, workspace_id=w2.id)
    mi_id = mi.id
    before_rt1 = snap_before(db, rt1)
    before_rl1 = snap_before(db, rl1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, rt1) == before_rt1
    # Then 5
    assert snap(db, rl1) == before_rl1


# [claude] MIM-D-195
def test_mim_d_195__d_does_not_block_w1_line_on_a_w2_return_a_completed_return(db, w1, w2, u2, i1, m1, mk_stock, mk_po, mk_po_line, mk_return, mk_return_line):
    """MIM-D-195 — (d) does not block: W1 line on a W2 return: a `completed` return.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    po1 = mk_po("PO1")
    pol1 = mk_po_line(po1)
    rt1 = mk_return(po1, "RT1", workspace_id=w2.id, status="completed")
    rl1 = mk_return_line(rt1, pol1)
    mi_id = mi.id
    before_rt1 = snap_before(db, rt1)
    before_rl1 = snap_before(db, rl1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, rt1) == before_rt1
    # Then 5
    assert snap(db, rl1) == before_rl1


# [claude] MIM-D-196
def test_mim_d_196__d_does_not_block_w2_line_on_a_w1_return_a_completed_return(db, w1, w2, u2, i1, m1, mk_stock, mk_po, mk_po_line, mk_return, mk_return_line):
    """MIM-D-196 — (d) does not block: W2 line on a W1 return: a `completed` return.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    po1 = mk_po("PO1")
    pol1 = mk_po_line(po1)
    rt1 = mk_return(po1, "RT1", status="completed")
    rl1 = mk_return_line(rt1, pol1, workspace_id=w2.id)
    mi_id = mi.id
    before_rt1 = snap_before(db, rt1)
    before_rl1 = snap_before(db, rl1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, rt1) == before_rt1
    # Then 5
    assert snap(db, rl1) == before_rl1


# [claude] MIM-D-197
def test_mim_d_197__d_does_not_block_a_voided_return(db, w1, u2, i1, m1, mk_stock, mk_po, mk_po_line, mk_return, mk_return_line):
    """MIM-D-197 — (d) does not block: a `voided` return.
    Rules: `delete_machine_item` R5b, R5 (d)"""
    mi = mk_stock(m1, i1, qty=5)
    po1 = mk_po("PO1")
    pol1 = mk_po_line(po1)
    rt1 = mk_return(po1, "RT1", status="voided")
    rl1 = mk_return_line(rt1, pol1)
    mi_id = mi.id
    before_rt1 = snap_before(db, rt1)
    before_rl1 = snap_before(db, rl1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, rt1) == before_rt1
    # Then 5
    assert snap(db, rl1) == before_rl1


# [claude] MIM-D-198
def test_mim_d_198__d_does_not_block_all_of_w2_a_voided_return(db, w1, w2, u2, i1, m1, st9, mk_stock, mk_po, mk_po_line, mk_return, mk_return_line):
    """MIM-D-198 — (d) does not block: all of W2: a `voided` return.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    po1 = mk_po("PO1", workspace_id=w2.id, current_status_id=st9.id)
    pol1 = mk_po_line(po1, workspace_id=w2.id)
    rt1 = mk_return(po1, "RT1", workspace_id=w2.id, status="voided")
    rl1 = mk_return_line(rt1, pol1, workspace_id=w2.id)
    mi_id = mi.id
    before_rt1 = snap_before(db, rt1)
    before_rl1 = snap_before(db, rl1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, rt1) == before_rt1
    # Then 5
    assert snap(db, rl1) == before_rl1


# [claude] MIM-D-199
def test_mim_d_199__d_does_not_block_w1_line_on_a_w2_return_a_voided_return(db, w1, w2, u2, i1, m1, mk_stock, mk_po, mk_po_line, mk_return, mk_return_line):
    """MIM-D-199 — (d) does not block: W1 line on a W2 return: a `voided` return.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    po1 = mk_po("PO1")
    pol1 = mk_po_line(po1)
    rt1 = mk_return(po1, "RT1", workspace_id=w2.id, status="voided")
    rl1 = mk_return_line(rt1, pol1)
    mi_id = mi.id
    before_rt1 = snap_before(db, rt1)
    before_rl1 = snap_before(db, rl1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, rt1) == before_rt1
    # Then 5
    assert snap(db, rl1) == before_rl1


# [claude] MIM-D-200
def test_mim_d_200__d_does_not_block_w2_line_on_a_w1_return_a_voided_return(db, w1, w2, u2, i1, m1, mk_stock, mk_po, mk_po_line, mk_return, mk_return_line):
    """MIM-D-200 — (d) does not block: W2 line on a W1 return: a `voided` return.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    po1 = mk_po("PO1")
    pol1 = mk_po_line(po1)
    rt1 = mk_return(po1, "RT1", status="voided")
    rl1 = mk_return_line(rt1, pol1, workspace_id=w2.id)
    mi_id = mi.id
    before_rt1 = snap_before(db, rt1)
    before_rl1 = snap_before(db, rl1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, rt1) == before_rt1
    # Then 5
    assert snap(db, rl1) == before_rl1


# [claude] MIM-D-201
def test_mim_d_201__d_does_not_block_a_purchase_order_into_storage_with_the_machine_s_id(db, w1, u2, i1, m1, mk_stock, mk_po, mk_po_line, mk_return, mk_return_line):
    """MIM-D-201 — (d) does not block: a purchase order into storage with the machine's id.
    Rules: `delete_machine_item` R5b, R5 (d)"""
    mi = mk_stock(m1, i1, qty=5)
    po1 = mk_po("PO1", destination_type="storage")
    pol1 = mk_po_line(po1)
    rt1 = mk_return(po1, "RT1")
    rl1 = mk_return_line(rt1, pol1)
    mi_id = mi.id
    before_rt1 = snap_before(db, rt1)
    before_rl1 = snap_before(db, rl1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, rt1) == before_rt1
    # Then 5
    assert snap(db, rl1) == before_rl1


# [claude] MIM-D-202
def test_mim_d_202__d_does_not_block_all_of_w2_a_purchase_order_into_storage_with_the_machine_s_id(db, w1, w2, u2, i1, m1, st9, mk_stock, mk_po, mk_po_line, mk_return, mk_return_line):
    """MIM-D-202 — (d) does not block: all of W2: a purchase order into storage with the machine's id.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    po1 = mk_po("PO1", workspace_id=w2.id, current_status_id=st9.id, destination_type="storage")
    pol1 = mk_po_line(po1, workspace_id=w2.id)
    rt1 = mk_return(po1, "RT1", workspace_id=w2.id)
    rl1 = mk_return_line(rt1, pol1, workspace_id=w2.id)
    mi_id = mi.id
    before_rt1 = snap_before(db, rt1)
    before_rl1 = snap_before(db, rl1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, rt1) == before_rt1
    # Then 5
    assert snap(db, rl1) == before_rl1


# [claude] MIM-D-203
def test_mim_d_203__d_does_not_block_w1_line_on_a_w2_return_a_purchase_order_into_storage_with_the_machine_s_id(db, w1, w2, u2, i1, m1, mk_stock, mk_po, mk_po_line, mk_return, mk_return_line):
    """MIM-D-203 — (d) does not block: W1 line on a W2 return: a purchase order into storage with the machine's id.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    po1 = mk_po("PO1", destination_type="storage")
    pol1 = mk_po_line(po1)
    rt1 = mk_return(po1, "RT1", workspace_id=w2.id)
    rl1 = mk_return_line(rt1, pol1)
    mi_id = mi.id
    before_rt1 = snap_before(db, rt1)
    before_rl1 = snap_before(db, rl1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, rt1) == before_rt1
    # Then 5
    assert snap(db, rl1) == before_rl1


# [claude] MIM-D-204
def test_mim_d_204__d_does_not_block_w2_line_on_a_w1_return_a_purchase_order_into_storage_with_the_machine_s_id(db, w1, w2, u2, i1, m1, mk_stock, mk_po, mk_po_line, mk_return, mk_return_line):
    """MIM-D-204 — (d) does not block: W2 line on a W1 return: a purchase order into storage with the machine's id.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    po1 = mk_po("PO1", destination_type="storage")
    pol1 = mk_po_line(po1)
    rt1 = mk_return(po1, "RT1")
    rl1 = mk_return_line(rt1, pol1, workspace_id=w2.id)
    mi_id = mi.id
    before_rt1 = snap_before(db, rt1)
    before_rl1 = snap_before(db, rl1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, rt1) == before_rt1
    # Then 5
    assert snap(db, rl1) == before_rl1


# [claude] MIM-D-205
def test_mim_d_205__d_does_not_block_a_purchase_order_to_another_machine(db, w1, u2, i1, m1, m2, mk_stock, mk_po, mk_po_line, mk_return, mk_return_line):
    """MIM-D-205 — (d) does not block: a purchase order to another machine.
    Rules: `delete_machine_item` R5b, R5 (d)"""
    mi = mk_stock(m1, i1, qty=5)
    po1 = mk_po("PO1", destination_id=m2.id)
    pol1 = mk_po_line(po1)
    rt1 = mk_return(po1, "RT1")
    rl1 = mk_return_line(rt1, pol1)
    mi_id = mi.id
    before_rt1 = snap_before(db, rt1)
    before_rl1 = snap_before(db, rl1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, rt1) == before_rt1
    # Then 5
    assert snap(db, rl1) == before_rl1


# [claude] MIM-D-206
def test_mim_d_206__d_does_not_block_all_of_w2_a_purchase_order_to_another_machine(db, w1, w2, u2, i1, m1, m2, st9, mk_stock, mk_po, mk_po_line, mk_return, mk_return_line):
    """MIM-D-206 — (d) does not block: all of W2: a purchase order to another machine.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    po1 = mk_po("PO1", workspace_id=w2.id, current_status_id=st9.id, destination_id=m2.id)
    pol1 = mk_po_line(po1, workspace_id=w2.id)
    rt1 = mk_return(po1, "RT1", workspace_id=w2.id)
    rl1 = mk_return_line(rt1, pol1, workspace_id=w2.id)
    mi_id = mi.id
    before_rt1 = snap_before(db, rt1)
    before_rl1 = snap_before(db, rl1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, rt1) == before_rt1
    # Then 5
    assert snap(db, rl1) == before_rl1


# [claude] MIM-D-207
def test_mim_d_207__d_does_not_block_w1_line_on_a_w2_return_a_purchase_order_to_another_machine(db, w1, w2, u2, i1, m1, m2, mk_stock, mk_po, mk_po_line, mk_return, mk_return_line):
    """MIM-D-207 — (d) does not block: W1 line on a W2 return: a purchase order to another machine.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    po1 = mk_po("PO1", destination_id=m2.id)
    pol1 = mk_po_line(po1)
    rt1 = mk_return(po1, "RT1", workspace_id=w2.id)
    rl1 = mk_return_line(rt1, pol1)
    mi_id = mi.id
    before_rt1 = snap_before(db, rt1)
    before_rl1 = snap_before(db, rl1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, rt1) == before_rt1
    # Then 5
    assert snap(db, rl1) == before_rl1


# [claude] MIM-D-208
def test_mim_d_208__d_does_not_block_w2_line_on_a_w1_return_a_purchase_order_to_another_machine(db, w1, w2, u2, i1, m1, m2, mk_stock, mk_po, mk_po_line, mk_return, mk_return_line):
    """MIM-D-208 — (d) does not block: W2 line on a W1 return: a purchase order to another machine.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    po1 = mk_po("PO1", destination_id=m2.id)
    pol1 = mk_po_line(po1)
    rt1 = mk_return(po1, "RT1")
    rl1 = mk_return_line(rt1, pol1, workspace_id=w2.id)
    mi_id = mi.id
    before_rt1 = snap_before(db, rt1)
    before_rl1 = snap_before(db, rl1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, rt1) == before_rt1
    # Then 5
    assert snap(db, rl1) == before_rl1


# [claude] MIM-D-209
def test_mim_d_209__d_does_not_block_a_return_line_of_another_item(db, w1, u2, i1, i2, m1, mk_stock, mk_po, mk_po_line, mk_return, mk_return_line):
    """MIM-D-209 — (d) does not block: a return line of another item.
    Rules: `delete_machine_item` R5b, R5 (d)"""
    mi = mk_stock(m1, i1, qty=5)
    po1 = mk_po("PO1")
    pol1 = mk_po_line(po1)
    rt1 = mk_return(po1, "RT1")
    rl1 = mk_return_line(rt1, pol1, item_id=i2.id)
    mi_id = mi.id
    before_rt1 = snap_before(db, rt1)
    before_rl1 = snap_before(db, rl1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, rt1) == before_rt1
    # Then 5
    assert snap(db, rl1) == before_rl1


# [claude] MIM-D-210
def test_mim_d_210__d_does_not_block_all_of_w2_a_return_line_of_another_item(db, w1, w2, u2, i1, i2, m1, st9, mk_stock, mk_po, mk_po_line, mk_return, mk_return_line):
    """MIM-D-210 — (d) does not block: all of W2: a return line of another item.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    po1 = mk_po("PO1", workspace_id=w2.id, current_status_id=st9.id)
    pol1 = mk_po_line(po1, workspace_id=w2.id)
    rt1 = mk_return(po1, "RT1", workspace_id=w2.id)
    rl1 = mk_return_line(rt1, pol1, workspace_id=w2.id, item_id=i2.id)
    mi_id = mi.id
    before_rt1 = snap_before(db, rt1)
    before_rl1 = snap_before(db, rl1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, rt1) == before_rt1
    # Then 5
    assert snap(db, rl1) == before_rl1


# [claude] MIM-D-211
def test_mim_d_211__d_does_not_block_w1_line_on_a_w2_return_a_return_line_of_another_item(db, w1, w2, u2, i1, i2, m1, mk_stock, mk_po, mk_po_line, mk_return, mk_return_line):
    """MIM-D-211 — (d) does not block: W1 line on a W2 return: a return line of another item.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    po1 = mk_po("PO1")
    pol1 = mk_po_line(po1)
    rt1 = mk_return(po1, "RT1", workspace_id=w2.id)
    rl1 = mk_return_line(rt1, pol1, item_id=i2.id)
    mi_id = mi.id
    before_rt1 = snap_before(db, rt1)
    before_rl1 = snap_before(db, rl1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, rt1) == before_rt1
    # Then 5
    assert snap(db, rl1) == before_rl1


# [claude] MIM-D-212
def test_mim_d_212__d_does_not_block_w2_line_on_a_w1_return_a_return_line_of_another_item(db, w1, w2, u2, i1, i2, m1, mk_stock, mk_po, mk_po_line, mk_return, mk_return_line):
    """MIM-D-212 — (d) does not block: W2 line on a W1 return: a return line of another item.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    po1 = mk_po("PO1")
    pol1 = mk_po_line(po1)
    rt1 = mk_return(po1, "RT1")
    rl1 = mk_return_line(rt1, pol1, workspace_id=w2.id, item_id=i2.id)
    mi_id = mi.id
    before_rt1 = snap_before(db, rt1)
    before_rl1 = snap_before(db, rl1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, rt1) == before_rt1
    # Then 5
    assert snap(db, rl1) == before_rl1


# [claude] MIM-D-213
def test_mim_d_213__the_row_s_own_quantities_do_not_block(db, w1, u2, i1, m1, mk_stock):
    """MIM-D-213 — the row's own quantities do not block.
    Rules: `delete_machine_item` R5b, R6"""
    mi = mk_stock(m1, i1, qty=5, req_qty=7, defective_qty=1)
    mi_id = mi.id
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0


# [claude] MIM-D-214
def test_mim_d_214__a_purchase_order_into_the_machine_with_no_return_does_not_block(db, w1, u2, i1, m1, std, mk_stock, mk_po, mk_po_line):
    """MIM-D-214 — a purchase order into the machine with no return does not block.
    Rules: `delete_machine_item` R5b"""
    mi = mk_stock(m1, i1, qty=5)
    po1 = mk_po("PO1", current_status_id=std.id)
    pol1 = mk_po_line(po1)
    mi_id = mi.id
    before_po1 = snap_before(db, po1)
    before_pol1 = snap_before(db, pol1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, po1) == before_po1
    # Then 5
    assert snap(db, pol1) == before_pol1


# [claude] MIM-D-215
def test_mim_d_215__earlier_ledger_rows_and_activity_do_not_block_and_stay(db, w1, u2, i1, m1, mk_stock, mk_entry, mk_activity):
    """MIM-D-215 — earlier ledger rows and activity do not block and stay.
    Rules: `delete_machine_item` R5b, R10"""
    mi = mk_stock(m1, i1, qty=5)
    lg = mk_entry(m1, i1, performed_at=T9, avg_price_after=Decimal("0.00"), qty_after=5)
    ev = mk_activity(m1)
    mi_id = mi.id
    before_lg = snap_before(db, lg)
    before_ev = snap_before(db, ev)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert snap(db, lg) == before_lg
    # Then 4
    assert snap(db, ev) == before_ev
    # Then 5
    assert len(entries_of(db, m1, i1)) == 2


# [claude] MIM-D-216
def test_mim_d_216__qty_above_0_books_one_final_adjustment_to_0(db, w1, u2, i1, m1, mk_stock):
    """MIM-D-216 — qty above 0 books one final adjustment to 0.
    Rules: `delete_machine_item` R6, Returns"""
    mi = mk_stock(m1, i1, qty=5)
    mi_id = mi.id
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert len(entries_of(db, m1, i1)) == 1
    # Then 4
    row = entries_of(db, m1, i1)[-1]
    assert row.transaction_type == "inventory_adjustment"
    assert row.quantity == 5
    # Then 5
    row = entries_of(db, m1, i1)[-1]
    assert row.qty_before == 5
    assert row.qty_after == 0
    # Then 6
    row = entries_of(db, m1, i1)[-1]
    assert row.source_type == "adjustment"
    assert row.notes == "Machine inventory record deleted"
    # Then 7
    row = entries_of(db, m1, i1)[-1]
    assert row.performed_by == u2.id
    assert row.workspace_id == w1.id
    # Then 8
    row = entries_of(db, m1, i1)[-1]
    assert row.unit_cost == Decimal("0.00")
    assert row.total_cost == Decimal("0.00")
    # Then 9
    row = entries_of(db, m1, i1)[-1]
    assert row.value_before == Decimal("0.00")
    assert row.value_after == Decimal("0.00")
    # Then 10
    row = entries_of(db, m1, i1)[-1]
    assert row.avg_price_before == Decimal("0.00")
    assert row.avg_price_after == Decimal("0.00")


# [claude] MIM-D-217
def test_mim_d_217__the_final_adjustment_writes_its_inventory_adjusted_event(db, w1, u2, i1, m1, mk_stock):
    """MIM-D-217 — the final adjustment writes its inventory_adjusted event.
    Rules: `delete_machine_item` R6"""
    mi = mk_stock(m1, i1, qty=5)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    [row] = events_of(db, m1, event_type="inventory_adjusted")
    assert row.description == "Inventory adjusted on Bolt M8: 5 → 0"
    # Then 3
    [row] = events_of(db, m1, event_type="inventory_adjusted")
    assert row.performed_by == u2.id
    assert row.workspace_id == w1.id
    assert row.machine_id == m1.id
    # Then 4
    [row] = events_of(db, m1, event_type="inventory_adjusted")
    assert row.metadata_json == {"item_id": i1.id, "item_name": "Bolt M8", "quantity": 5, "changes": [{"field": "qty", "label": "Quantity", "from_value": "5", "to_value": "0"}]}


# [claude] MIM-D-218
@pytest.mark.xfail(strict=True, reason="BUG-993: A manual stock change wipes the machine's cost")
def test_mim_d_218__the_final_adjustment_is_valued_at_the_current_average(db, w1, u2, i1, m1, mk_stock, mk_entry):
    """MIM-D-218 — the final adjustment is valued at the current average.
    Rules: `delete_machine_item` R6, `_write_ledger_entry` R2 [BUG-993], R3, R4"""
    mi = mk_stock(m1, i1, qty=5)
    mk_entry(m1, i1, performed_at=T9, avg_price_after=Decimal("3.00"), qty_after=5, value_after=Decimal("15.00"))
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    row = entries_of(db, m1, i1)[-1]
    assert row.unit_cost == Decimal("3.00")
    assert row.avg_price_before == Decimal("3.00")
    assert row.avg_price_after == Decimal("3.00")
    # Then 3
    row = entries_of(db, m1, i1)[-1]
    assert row.total_cost == Decimal("15.00")
    assert row.value_before == Decimal("15.00")
    assert row.value_after == Decimal("0.00")


# [claude] MIM-D-219
def test_mim_d_219__after_the_delete_the_ledger_balance_is_0(db, w1, u2, i1, m1, mk_stock, mk_entry):
    """MIM-D-219 — after the delete the ledger balance is 0.
    Rules: `delete_machine_item` R6, `_write_ledger_entry` R9"""
    mi = mk_stock(m1, i1, qty=5)
    mk_entry(m1, i1, performed_at=T9, avg_price_after=Decimal("3.00"), qty_after=5, value_after=Decimal("15.00"))
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert machine_item_ledger_dao.calculate_balance(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id) == (0, Decimal("0.00"))


# [claude] MIM-D-220
def test_mim_d_220__qty_0_books_no_ledger_entry(db, w1, u2, i1, m1, mk_stock):
    """MIM-D-220 — qty 0 books no ledger entry.
    Rules: `delete_machine_item` R7"""
    mi = mk_stock(m1, i1, qty=0)
    mi_id = mi.id
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 0
    # Then 4
    rows = events_of(db, m1)
    assert len(rows) == 1


# [claude] MIM-D-221
@pytest.mark.xfail(strict=True, reason="BUG-1080: Removing a negative stock row leaves the ledger negative")
def test_mim_d_221__qty_below_0_books_the_same_final_adjustment(db, w1, u2, i1, m1, mk_stock):
    """MIM-D-221 — qty below 0 books the same final adjustment.
    Rules: `delete_machine_item` R8 [BUG-1080]"""
    mi = mk_stock(m1, i1, qty=-3)
    mi_id = mi.id
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert len(entries_of(db, m1, i1)) == 1
    # Then 4
    row = entries_of(db, m1, i1)[-1]
    assert row.transaction_type == "inventory_adjustment"
    assert row.quantity == 3
    # Then 5
    row = entries_of(db, m1, i1)[-1]
    assert row.qty_before == -3
    assert row.qty_after == 0
    # Then 6
    row = entries_of(db, m1, i1)[-1]
    assert row.source_type == "adjustment"
    assert row.notes == "Machine inventory record deleted"


# [claude] MIM-D-222
@pytest.mark.xfail(strict=True, reason="BUG-1080: Removing a negative stock row leaves the ledger negative")
def test_mim_d_222__qty_below_0_writes_the_inventory_adjusted_event(db, w1, u2, i1, m1, mk_stock):
    """MIM-D-222 — qty below 0 writes the inventory_adjusted event.
    Rules: `delete_machine_item` R8 [BUG-1080], R12"""
    mi = mk_stock(m1, i1, qty=-3)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    rows = events_of(db, m1, event_type="inventory_adjusted")
    assert len(rows) == 1
    # Then 3
    [row] = events_of(db, m1, event_type="inventory_adjusted")
    assert row.description == "Inventory adjusted on Bolt M8: -3 → 0"


# [claude] MIM-D-223
@pytest.mark.xfail(strict=True, reason="BUG-1080: Removing a negative stock row leaves the ledger negative")
def test_mim_d_223__qty_below_0_the_ledger_ends_at_0(db, w1, u2, i1, m1, mk_stock, mk_entry):
    """MIM-D-223 — qty below 0: the ledger ends at 0.
    Rules: `delete_machine_item` R8 [BUG-1080]"""
    mi = mk_stock(m1, i1, qty=-3)
    mk_entry(m1, i1, performed_at=T9, avg_price_after=Decimal("5.00"), qty_after=-3, value_after=Decimal("-15.00"))
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert machine_item_ledger_dao.calculate_balance(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id) == (0, Decimal("0.00"))


# [claude] MIM-D-224
def test_mim_d_224__a_row_with_qty_below_0_is_still_deleted_with_its_item_removed_event(db, w1, u2, i1, m1, mk_stock):
    """MIM-D-224 — a row with qty below 0 is still deleted, with its item_removed event.
    Rules: `delete_machine_item` R8, R9, R10"""
    mi = mk_stock(m1, i1, qty=-3)
    mi_id = mi.id
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    rows = events_of(db, m1, event_type="item_removed")
    assert len(rows) == 1


# [claude] MIM-D-225
def test_mim_d_225__one_item_removed_event_with_qty_5(db, w1, u2, i1, m1, mk_stock):
    """MIM-D-225 — one item_removed event with qty 5.
    Rules: `delete_machine_item` R9"""
    mi = mk_stock(m1, i1, qty=5, req_qty=7, defective_qty=1)
    mi_id = mi.id
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    rows = events_of(db, m1, event_type="item_removed")
    assert len(rows) == 1
    # Then 3
    [row] = events_of(db, m1, event_type="item_removed")
    assert row.description == "Item removed: Bolt M8"
    # Then 4
    [row] = events_of(db, m1, event_type="item_removed")
    assert row.performed_by == u2.id
    assert row.workspace_id == w1.id
    assert row.machine_id == m1.id
    # Then 5
    [row] = events_of(db, m1, event_type="item_removed")
    assert row.metadata_json == {"item_id": i1.id, "item_name": "Bolt M8", "machine_item_id": mi_id}
    # Then 6
    rows = events_of(db, m1)
    assert len(rows) == 2


# [claude] MIM-D-226
def test_mim_d_226__one_item_removed_event_with_qty_0(db, w1, u2, i1, m1, mk_stock):
    """MIM-D-226 — one item_removed event with qty 0.
    Rules: `delete_machine_item` R9"""
    mi = mk_stock(m1, i1, qty=0, req_qty=7, defective_qty=1)
    mi_id = mi.id
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    rows = events_of(db, m1, event_type="item_removed")
    assert len(rows) == 1
    # Then 3
    [row] = events_of(db, m1, event_type="item_removed")
    assert row.description == "Item removed: Bolt M8"
    # Then 4
    [row] = events_of(db, m1, event_type="item_removed")
    assert row.performed_by == u2.id
    assert row.workspace_id == w1.id
    assert row.machine_id == m1.id
    # Then 5
    [row] = events_of(db, m1, event_type="item_removed")
    assert row.metadata_json == {"item_id": i1.id, "item_name": "Bolt M8", "machine_item_id": mi_id}
    # Then 6
    rows = events_of(db, m1)
    assert len(rows) == 1


# [claude] MIM-D-227
def test_mim_d_227__only_this_row_goes_the_machine_s_other_rows_and_the_item_s_rows_elsewhere_stay(db, w1, u2, i1, i2, m1, m2, mk_stock):
    """MIM-D-227 — only this row goes: the machine's other rows and the item's rows elsewhere stay.
    Rules: `delete_machine_item` R10"""
    mi = mk_stock(m1, i1, qty=5)
    a = mk_stock(m1, i2, qty=2)
    b = mk_stock(m2, i1, qty=3)
    mi_id = mi.id
    before_a = snap_before(db, a)
    before_b = snap_before(db, b)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert snap(db, a) == before_a
    # Then 4
    assert snap(db, b) == before_b
    # Then 5
    assert count_rows(db, "machine_items") == 2


# [claude] MIM-D-228
def test_mim_d_228__the_target_and_defect_count_go_with_the_row(db, w1, u2, i1, m1, mk_stock):
    """MIM-D-228 — the target and defect count go with the row.
    Rules: `delete_machine_item` R10"""
    mi = mk_stock(m1, i1, qty=0, req_qty=7, defective_qty=1)
    mi_id = mi.id
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_items") == 0


# [claude] MIM-D-229
def test_mim_d_229__a_later_create_for_the_pair_gets_a_new_row_id(db, w1, u2, i1, m1, mk_stock):
    """MIM-D-229 — a later create for the pair gets a new row id.
    Rules: `delete_machine_item` R10, `create_machine_item` R10"""
    mi = mk_stock(m1, i1, qty=5)
    old_id = mi.id
    M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    db.flush()
    result = M.create_machine_item(db, item_data=MachineItemCreate(machine_id=m1.id, item_id=i1.id, qty=4), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id != old_id
    # Then 2
    row = reread(db, result)
    assert row.qty == 4
    # Then 3
    assert count_rows(db, "machine_items", id=old_id) == 0


# [claude] MIM-D-230
@pytest.mark.xfail(strict=True, reason="BUG-1086: A stored stock row with another workspace's item shows that item's name and id")
def test_mim_d_230__a_stored_row_with_another_workspace_s_item_is_not_found(db, w1, u2, i9, m1, mk_stock):
    """MIM-D-230 — a stored row with another workspace's item is not found.
    Rules: `delete_machine_item` R11 [BUG-1086], Errors row 1, `_item_name` R3 [BUG-1086]"""
    mi = mk_stock(m1, i9, qty=5)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine item not found"
    # Then 4
    assert mi not in db.dirty
    # Then 5
    assert mi not in db.deleted
    # Then 6
    db.flush()
    # Then 7
    assert snap(db, mi) == before_mi
    # Then 8
    assert written(db) == before


# [claude] MIM-D-231
@pytest.mark.xfail(strict=True, reason="BUG-1086: A stored stock row with another workspace's item shows that item's name and id")
def test_mim_d_231__not_found_wins_over_the_deleted_machine_refusal_for_such_a_row(db, w1, u2, i9, mx, mk_stock):
    """MIM-D-231 — not found wins over the deleted-machine refusal for such a row.
    Rules: `delete_machine_item` R11 [BUG-1086], R2 [BUG-1084], Errors row 1"""
    mi = mk_stock(mx, i9, qty=5)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine item not found"
    # Then 4
    assert mi not in db.dirty
    # Then 5
    assert mi not in db.deleted
    # Then 6
    db.flush()
    # Then 7
    assert snap(db, mi) == before_mi
    # Then 8
    assert written(db) == before


# [claude] MIM-D-232
@pytest.mark.xfail(strict=True, reason="BUG-1086: A stored stock row with another workspace's item shows that item's name and id")
def test_mim_d_232__not_found_wins_over_the_open_order_refusal_for_such_a_row(db, w1, u2, i9, m1, mk_stock, mk_order, mk_source_line):
    """MIM-D-232 — not found wins over the open-order refusal for such a row.
    Rules: `delete_machine_item` R11 [BUG-1086], R5 [BUG-1081], Errors row 1"""
    mi = mk_stock(m1, i9, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT")
    l1 = mk_source_line(o1, item_id=i9.id)
    before_mi = snap_before(db, mi)
    before_l1 = snap_before(db, l1)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine item not found"
    # Then 4
    assert mi not in db.dirty
    # Then 5
    assert mi not in db.deleted
    # Then 6
    db.flush()
    # Then 7
    assert snap(db, mi) == before_mi
    # Then 8
    assert written(db) == before
    # Then 9
    assert snap(db, l1) == before_l1


# [claude] MIM-D-233
def test_mim_d_233__an_unknown_user_with_qty_above_0_fails_on_the_ledger(db, w1, i1, m1, mk_stock):
    """MIM-D-233 — an unknown user with qty above 0 fails on the ledger.
    Rules: `delete_machine_item` R12, Errors row 4"""
    mi = mk_stock(m1, i1, qty=5)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=MISSING)
    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert exc.value.orig.diag.constraint_name == "machine_item_ledger_performed_by_fkey"
    # Then 4
    assert snap(db, mi) == before_mi
    # Then 5
    assert written(db) == before


# [claude] MIM-D-234
def test_mim_d_234__an_unknown_user_with_qty_0_fails_on_the_activity_entry(db, w1, i1, m1, mk_stock):
    """MIM-D-234 — an unknown user with qty 0 fails on the activity entry.
    Rules: `delete_machine_item` R12, Errors row 4"""
    mi = mk_stock(m1, i1, qty=0)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=MISSING)
    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert exc.value.orig.diag.constraint_name == "machine_activity_events_performed_by_fkey"
    # Then 4
    assert snap(db, mi) == before_mi
    # Then 5
    assert written(db) == before


# [claude] MIM-D-235
@pytest.mark.xfail(strict=True, reason="BUG-1080: Removing a negative stock row leaves the ledger negative")
def test_mim_d_235__an_unknown_user_with_qty_below_0_fails_on_the_ledger(db, w1, i1, m1, mk_stock):
    """MIM-D-235 — an unknown user with qty below 0 fails on the ledger.
    Rules: `delete_machine_item` R12 [BUG-1080], R8, Errors row 4"""
    mi = mk_stock(m1, i1, qty=-3)
    before_mi = snap_before(db, mi)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=MISSING)
    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert exc.value.orig.diag.constraint_name == "machine_item_ledger_performed_by_fkey"
    # Then 4
    assert snap(db, mi) == before_mi


# [claude] MIM-D-236
def test_mim_d_236__an_unknown_user_with_qty_below_0_leaves_the_row_in_place(db, w1, i1, m1, mk_stock):
    """MIM-D-236 — an unknown user with qty below 0 leaves the row in place.
    Rules: `delete_machine_item` R12, Errors row 4"""
    mi = mk_stock(m1, i1, qty=-3)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=MISSING)
    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert snap(db, mi) == before_mi
    # Then 4
    assert written(db) == before


# [claude] MIM-D-237
def test_mim_d_237__the_delete_is_flushed_but_not_committed(db, w1, u2, i1, m1, mk_stock, monkeypatch):
    """MIM-D-237 — the delete is flushed but not committed.
    Rules: `delete_machine_item` R13"""
    mi = mk_stock(m1, i1, qty=5)
    mi_id = mi.id
    sp = db.begin_nested()
    spy = commit_spy(db, monkeypatch)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    rows = events_of(db, m1)
    assert len(rows) == 2
    # Then 5
    sp.rollback()
    row = reread(db, mi)
    assert row.qty == 5
    # Then 6
    assert count_rows(db, "machine_item_ledger") == 0
    # Then 7
    assert count_rows(db, "machine_activity_events") == 0
    # Then 8
    spy.assert_not_called()


# [claude] MIM-D-238
def test_mim_d_238__b_does_not_block_a_line_with_uses_inventory_false(db, w1, u2, i1, m1, mk_stock, mk_order, mk_replace_line):
    """MIM-D-238 — (b) does not block: a line with `uses_inventory False`.
    Rules: `delete_machine_item` R5b, R5 (b)"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT")
    l1 = mk_replace_line(o1, uses_inventory=False)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-239
def test_mim_d_239__b_does_not_block_w2_order_and_line_a_line_with_uses_inventory_false(db, w1, w2, u2, f9, i1, m1, wt9, mk_stock, mk_order, mk_replace_line):
    """MIM-D-239 — (b) does not block: W2 order and line: a line with `uses_inventory False`.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    l1 = mk_replace_line(o1, workspace_id=w2.id, uses_inventory=False)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-240
def test_mim_d_240__b_does_not_block_w1_line_on_a_w2_order_a_line_with_uses_inventory_false(db, w1, w2, u2, f9, i1, m1, wt9, mk_stock, mk_order, mk_replace_line):
    """MIM-D-240 — (b) does not block: W1 line on a W2 order: a line with `uses_inventory False`.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    l1 = mk_replace_line(o1, uses_inventory=False)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-241
def test_mim_d_241__b_does_not_block_w2_line_on_a_w1_order_a_line_with_uses_inventory_false(db, w1, w2, u2, i1, m1, mk_stock, mk_order, mk_replace_line):
    """MIM-D-241 — (b) does not block: W2 line on a W1 order: a line with `uses_inventory False`.
    Rules: `delete_machine_item` R5b, R5a"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT")
    l1 = mk_replace_line(o1, workspace_id=w2.id, uses_inventory=False)
    mi_id = mi.id
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert count_rows(db, "machine_item_ledger") == 1
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] MIM-D-242
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_242__d_a_w1_return_and_line_on_a_purchase_order_of_w2_show_only_the_generic_entry(db, w1, w2, u2, i1, m1, st9, mk_stock, mk_po, mk_po_line, mk_return, mk_return_line):
    """MIM-D-242 — (d) a W1 return and line on a purchase order of W2 show only the generic entry.
    Rules: `delete_machine_item` R5 (d) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    po1 = mk_po("PO1", workspace_id=w2.id, current_status_id=st9.id)
    pol1 = mk_po_line(po1, workspace_id=w2.id)
    rt1 = mk_return(po1, "RT1")
    rl1 = mk_return_line(rt1, pol1)
    before_mi = snap_before(db, mi)
    before_po1 = snap_before(db, po1)
    before_rt1 = snap_before(db, rt1)
    before_rl1 = snap_before(db, rl1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, po1) == before_po1
    # Then 11
    assert snap(db, rt1) == before_rt1
    # Then 12
    assert snap(db, rl1) == before_rl1


# [claude] MIM-D-243
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_243__c_the_stage_is_not_read_a_transfer_at_stage_cancelled_with_completed_at_empty_blocks(db, w1, u2, i1, m1, mk_stock, mk_transfer, mk_to_line):
    """MIM-D-243 — (c) the stage is not read: a transfer at stage Cancelled with completed_at empty blocks.
    Rules: `delete_machine_item` R5 (c) [BUG-1081], R5a, R5b, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    stx = _add(db, Status(workspace_id=w1.id, name="Cancelled", comment="stage"))
    to1 = mk_transfer("TO1", current_status_id=stx.id)
    mk_to_line(to1)
    before_mi = snap_before(db, mi)
    before_to1 = snap_before(db, to1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "transfer_order", "id": to1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, to1) == before_to1


# [claude] MIM-D-244
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_244__d_the_stage_is_not_read_a_purchase_order_at_stage_planning_with_a_pending_return_blocks(db, w1, u2, i1, m1, mk_stock, mk_po, mk_po_line, mk_return, mk_return_line):
    """MIM-D-244 — (d) the stage is not read: a purchase order at stage Planning with a pending return blocks.
    Rules: `delete_machine_item` R5 (d) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    stp = _add(db, Status(workspace_id=w1.id, name="Planning", comment="stage"))
    po1 = mk_po("PO1", current_status_id=stp.id)
    pol1 = mk_po_line(po1)
    rt1 = mk_return(po1, "RT1")
    mk_return_line(rt1, pol1)
    before_mi = snap_before(db, mi)
    before_rt1 = snap_before(db, rt1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "purchase_return", "id": rt1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, rt1) == before_rt1


# [claude] MIM-D-245
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_245__d_the_stage_is_not_read_a_purchase_order_at_stage_receiving_with_a_pending_return_blocks(db, w1, u2, i1, m1, mk_stock, mk_po, mk_po_line, mk_return, mk_return_line):
    """MIM-D-245 — (d) the stage is not read: a purchase order at stage Receiving with a pending return blocks.
    Rules: `delete_machine_item` R5 (d) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    str = _add(db, Status(workspace_id=w1.id, name="Receiving", comment="stage"))
    po1 = mk_po("PO1", current_status_id=str.id)
    pol1 = mk_po_line(po1)
    rt1 = mk_return(po1, "RT1")
    mk_return_line(rt1, pol1)
    before_mi = snap_before(db, mi)
    before_rt1 = snap_before(db, rt1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "purchase_return", "id": rt1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, rt1) == before_rt1


# [claude] MIM-D-246
def test_mim_d_246__qty_1_books_a_final_adjustment(db, w1, u2, i1, m1, mk_stock):
    """MIM-D-246 — qty 1 books a final adjustment.
    Rules: `delete_machine_item` R6"""
    mi = mk_stock(m1, i1, qty=1)
    mi_id = mi.id
    result = M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    assert len(entries_of(db, m1, i1)) == 1
    # Then 4
    row = entries_of(db, m1, i1)[-1]
    assert row.transaction_type == "inventory_adjustment"
    assert row.quantity == 1
    # Then 5
    row = entries_of(db, m1, i1)[-1]
    assert row.qty_before == 1
    assert row.qty_after == 0


# [claude] MIM-D-247
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_247__a_an_install_line_sourcing_this_item_from_this_machine_blocks(db, w1, u2, i1, m1, mk_stock, mk_order, mk_source_line):
    """MIM-D-247 — (a) an INSTALL line sourcing this item from this machine blocks.
    Rules: `delete_machine_item` R5 (a) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT")
    l1 = mk_source_line(o1, action_type="INSTALL")
    before_mi = snap_before(db, mi)
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, o1) == before_o1
    # Then 11
    assert snap(db, l1) == before_l1


# [claude] MIM-D-248
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_248__a_a_borrow_line_sourcing_this_item_from_this_machine_blocks(db, w1, u2, i1, m1, mk_stock, mk_order, mk_source_line):
    """MIM-D-248 — (a) a BORROW line sourcing this item from this machine blocks.
    Rules: `delete_machine_item` R5 (a) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT")
    l1 = mk_source_line(o1, action_type="BORROW")
    before_mi = snap_before(db, mi)
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, o1) == before_o1
    # Then 11
    assert snap(db, l1) == before_l1


# [claude] MIM-D-249
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_249__a_a_replace_line_sourcing_this_item_from_this_machine_blocks(db, w1, u2, i1, i2, m1, mk_stock, mk_order, mk_source_line):
    """MIM-D-249 — (a) a REPLACE line sourcing this item from this machine blocks.
    Rules: `delete_machine_item` R5 (a) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT")
    l1 = mk_source_line(o1, action_type="REPLACE", replaced_item_id=i2.id)
    before_mi = snap_before(db, mi)
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, o1) == before_o1
    # Then 11
    assert snap(db, l1) == before_l1


# [claude] MIM-D-250
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mim_d_250__one_line_that_meets_both_a_and_b_gives_one_entry_for_the_order(db, w1, u2, i1, m1, mk_stock, mk_order, mk_source_line):
    """MIM-D-250 — one line that meets both (a) and (b) gives one entry for the order.
    Rules: `delete_machine_item` R5 (a) [BUG-1081], R5 (b) [BUG-1081], R5a, Errors row 3"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "O1", status="DRAFT")
    l1 = mk_source_line(o1, action_type="REPLACE", replaced_item_id=i1.id)
    before_mi = snap_before(db, mi)
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    before = written(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine item has open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    assert mi not in db.dirty
    # Then 6
    assert mi not in db.deleted
    # Then 7
    db.flush()
    # Then 8
    assert snap(db, mi) == before_mi
    # Then 9
    assert written(db) == before
    # Then 10
    assert snap(db, o1) == before_o1
    # Then 11
    assert snap(db, l1) == before_l1
