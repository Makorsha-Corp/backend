"""Unit tests for app/managers/po_receive_inventory.py.

Implements tests/unit/managers/po_receive_inventory.cases.md (revision 5), one
test per case. Real Postgres session (`db` fixture, bundled into the `w`
world fixture below, which builds every actor named in the cases file's
Conventions once per test). Spec: "Externals to mock: none" -- all stock
mechanics run for real through app/managers/inventory_movements.py. The only
patches are the three listed race simulations (BUG-680 R1a).

Revision 5 adds PRI-D-05, PRI-P-34, PRI-P-35, PRI-RE-21, PRI-RE-22 (the
smallest non-zero whole delta, +-1, on the other side of the 0 boundary from
the designed 5/3-unit cases) and fixes nine test-weakness findings routed
here by po_receive_inventory.verify.md (findings 2-10): PRI-V-10's
pending_return() no longer sets a bug-masking parent status; PRI-P-01,
PRI-P-16, PRI-P-18, PRI-P-22, PRI-P-24, PRI-P-27, PRI-P-28, PRI-PR-02 and
PRI-RE-19 now assert the full "nothing written" / "no activity event" /
exact-column Then clause instead of a partial check.
"""
# ruff: noqa: SIM117, FURB157  (prescribed by the cards: nested with, Decimal("...") literals)
import itertools
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.managers.po_receive_inventory import (
    _delta_to_int,
    _ledger_exists,
    _location_for_po,
    _machine_ledger_exists,
    _post_event_item_delta,
    _reverse_event_item_posting,
    _reverse_legacy_line_posting,
    _storage_ledger_exists,
    post_receive_event_inventory,
    reverse_po_receive_inventory,
)
from app.managers.po_receive_inventory import (
    _machine_ledger_exists as _real_machine_ledger_exists,
)
from app.managers.po_receive_inventory import (
    _storage_ledger_exists as _real_storage_ledger_exists,
)
from app.models.enums import InventoryTypeEnum
from app.models.factory import Factory
from app.models.inventory import Inventory
from app.models.inventory_ledger import InventoryLedger
from app.models.item import Item
from app.models.machine import Machine
from app.models.machine_activity_event import MachineActivityEvent
from app.models.machine_item import MachineItem
from app.models.machine_item_ledger import MachineItemLedger
from app.models.po_receive_event import PoReceiveEvent, PoReceiveEventItem
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.purchase_order_return import (
    PurchaseOrderReturn,
    PurchaseOrderReturnItem,
)
from app.models.status import Status
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> fixtures / helpers
# --------------------------------------------------------------------------- #

# Convention "Times"
T0 = __import__("datetime").datetime(2026, 1, 1, 8, 0, 0)
T1 = __import__("datetime").datetime(2026, 1, 1, 9, 0, 0)
T2 = __import__("datetime").datetime(2026, 2, 1, 10, 0, 0)
T3 = __import__("datetime").datetime(2026, 2, 2, 10, 0, 0)
T4 = __import__("datetime").datetime(2026, 2, 3, 10, 0, 0)

BUG_680 = "BUG-680: concurrent receive/void for the same source double-moves stock (no unique index)"
BUG_681 = "BUG-681: destination_type free text lets a PO silently skip inventory (schema fix deferred)"
BUG_682 = "BUG-682: voiding a PO after a purchase return removes the returned units a second time"
BUG_683 = "BUG-683: void reverses at the PO's current destination, not the location it was posted at"
BUG_684 = "BUG-684: receiving can post stock into a soft-deleted factory or machine"

_seq = itertools.count(1)


def _n() -> int:
    return next(_seq)


# --------------------------------------------------------------------------- #
# Low-level row builders (local to this module; promote to factories.py if a
# second test file needs them -- see notes file)
# --------------------------------------------------------------------------- #

def make_item(db, workspace_id, name, *, active=True):
    row = Item(
        workspace_id=workspace_id,
        name=name,
        name_normalized=name.lower(),
        unit="pcs",
        is_active=active,
    )
    db.add(row)
    db.flush()
    return row


def make_factory(db, workspace_id, name, *, deleted=False):
    row = Factory(
        workspace_id=workspace_id,
        name=name,
        abbreviation=name[:3].upper(),
        is_deleted=deleted,
    )
    db.add(row)
    db.flush()
    return row


def make_machine(db, workspace_id, factory_id, name, *, deleted=False):
    row = Machine(
        workspace_id=workspace_id,
        name=name,
        factory_id=factory_id,
        is_deleted=deleted,
    )
    db.add(row)
    db.flush()
    return row


def make_status(db, workspace_id, name="Open"):
    row = Status(workspace_id=workspace_id, name=name, comment="")
    db.add(row)
    db.flush()
    return row


def make_po(db, workspace_id, user_id, *, destination_type, destination_id, po_number):
    status = make_status(db, workspace_id)
    row = PurchaseOrder(
        workspace_id=workspace_id,
        po_number=po_number,
        destination_type=destination_type,
        destination_id=destination_id,
        current_status_id=status.id,
        created_by=user_id,
    )
    db.add(row)
    db.flush()
    return row


def make_line(db, po, item_id, *, line_number, unit_price):
    row = PurchaseOrderItem(
        workspace_id=po.workspace_id,
        purchase_order_id=po.id,
        line_number=line_number,
        item_id=item_id,
        quantity_ordered=Decimal("1000"),
        unit_price=unit_price,
    )
    db.add(row)
    db.flush()
    return row


def make_event(db, po, created_at):
    row = PoReceiveEvent(
        workspace_id=po.workspace_id,
        purchase_order_id=po.id,
        event_type="receive",
        created_at=created_at,
    )
    db.add(row)
    db.flush()
    return row


def make_event_item(db, event, po_line, delta):
    row = PoReceiveEventItem(
        receive_event_id=event.id,
        po_item_id=po_line.id,
        quantity_delta=delta if isinstance(delta, Decimal) else Decimal(str(delta)),
    )
    db.add(row)
    db.flush()
    return row


# --------------------------------------------------------------------------- #
# World fixture: every actor named in the cases file's Conventions
# --------------------------------------------------------------------------- #

@pytest.fixture
def w(db):
    ns = SimpleNamespace(db=db)
    ns.w1 = make_workspace(db)
    ns.w2 = make_workspace(db)
    ns.u1 = make_profile(db)
    ns.u2 = make_profile(db)

    ns.x = make_item(db, ns.w1.id, "Hex Bolt")
    ns.y = make_item(db, ns.w1.id, "Flat Washer")
    ns.xd = make_item(db, ns.w1.id, "Old Gasket", active=False)
    ns.z2 = make_item(db, ns.w2.id, "Foreign Nut")

    ns.a = make_factory(db, ns.w1.id, "Factory A")
    ns.b = make_factory(db, ns.w1.id, "Factory B")
    ns.ad = make_factory(db, ns.w1.id, "Factory Ad", deleted=True)
    ns.f2 = make_factory(db, ns.w2.id, "Factory F2")

    ns.m1 = make_machine(db, ns.w1.id, ns.a.id, "Machine M1")
    ns.m2 = make_machine(db, ns.w1.id, ns.a.id, "Machine M2")
    ns.md = make_machine(db, ns.w1.id, ns.a.id, "Machine Md", deleted=True)
    ns.m9 = make_machine(db, ns.w2.id, ns.f2.id, "Machine M9")

    ns.p = make_po(
        db, ns.w1.id, ns.u1.id,
        destination_type="storage", destination_id=ns.a.id, po_number="PO-2026-004",
    )
    ns.l1 = make_line(db, ns.p, ns.x.id, line_number=1, unit_price=Decimal("26.00"))
    ns.l2 = make_line(db, ns.p, ns.y.id, line_number=2, unit_price=Decimal("4.00"))

    ns.p2 = make_po(
        db, ns.w1.id, ns.u1.id,
        destination_type="storage", destination_id=ns.a.id, po_number="PO-2026-099",
    )
    return ns


# --------------------------------------------------------------------------- #
# Stock / ledger shorthand builders (Conventions: posted / legacy / reversed /
# legacy-reversed / stock / mstock / return / pending-return)
# --------------------------------------------------------------------------- #

def _seed_ledger(
    w, loc, item, *, source_type, source_id, qty,
    qty_before=0, qty_after=None, avg_before=None, avg_after=None,
    value_before=None, value_after=None, ws_id=None, performed_at=T0,
    performed_by=None, unit_cost=None, total_cost=None,
):
    """Insert one bare ledger row (existence-check / state-seed fixture) into the
    correct table for `loc` (a Factory or Machine). `ws_id` overrides the
    location's own workspace, for isolation cases that plant a row elsewhere."""
    db = w.db
    workspace_id = ws_id if ws_id is not None else loc.workspace_id
    qty_after = qty if qty_after is None else qty_after
    if isinstance(loc, Machine):
        row = MachineItemLedger(
            workspace_id=workspace_id, machine_id=loc.id, item_id=item.id,
            transaction_type="test_fixture", quantity=qty,
            unit_cost=unit_cost if unit_cost is not None else Decimal("0"),
            total_cost=total_cost if total_cost is not None else Decimal("0"),
            qty_before=qty_before, qty_after=qty_after,
            value_before=value_before, value_after=value_after,
            avg_price_before=avg_before, avg_price_after=avg_after,
            source_type=source_type, source_id=source_id,
            performed_by=performed_by or w.u1.id, performed_at=performed_at,
        )
    else:
        row = InventoryLedger(
            workspace_id=workspace_id, inventory_type=InventoryTypeEnum.STORAGE,
            factory_id=loc.id, item_id=item.id, transaction_type="test_fixture",
            quantity=qty, unit_cost=unit_cost if unit_cost is not None else Decimal("0"),
            total_cost=total_cost, qty_before=qty_before, qty_after=qty_after,
            avg_price_before=avg_before, avg_price_after=avg_after,
            source_type=source_type, source_id=source_id,
            performed_by=performed_by, performed_at=performed_at,
        )
    db.add(row)
    db.flush()
    return row


def posted(w, event_item, loc, item, qty, *, ws_id=None, performed_at=T0):
    return _seed_ledger(
        w, loc, item, source_type="po_receive_event_item", source_id=event_item.id,
        qty=qty, ws_id=ws_id, performed_at=performed_at,
    )


def legacy(w, po_line, loc, item, qty, *, ws_id=None, performed_at=T0):
    return _seed_ledger(
        w, loc, item, source_type="purchase_order", source_id=po_line.id,
        qty=qty, ws_id=ws_id, performed_at=performed_at,
    )


def reversed_(w, event_item, loc, item, *, qty=0, ws_id=None, performed_at=T0):
    return _seed_ledger(
        w, loc, item, source_type="po_receive_event_item_reversal", source_id=event_item.id,
        qty=qty, ws_id=ws_id, performed_at=performed_at,
    )


def legacy_reversed(w, po_line, loc, item, *, qty=0, ws_id=None, performed_at=T0):
    return _seed_ledger(
        w, loc, item, source_type="purchase_order_reversal", source_id=po_line.id,
        qty=qty, ws_id=ws_id, performed_at=performed_at,
    )


def stock(w, factory, item, qty, avg, *, performed_at=T1, pre=None):
    """`stock(factory, item) = qty @ avg`: an Inventory row plus a trailing seed
    ledger row (source_type 'test_seed'), inserted last so it is the latest
    entry by performed_at (ledger wins). `pre=(qty, avg, deleted)` inserts a
    DIFFERENT pre-existing Inventory row first (PRI-P-04)."""
    db = w.db
    if pre is not None:
        pq, pa, pdel = pre
        row = Inventory(
            workspace_id=factory.workspace_id, item_id=item.id,
            inventory_type=InventoryTypeEnum.STORAGE, factory_id=factory.id,
            qty=pq, avg_price=pa, updated_by=w.u2.id, is_deleted=pdel,
        )
    else:
        row = Inventory(
            workspace_id=factory.workspace_id, item_id=item.id,
            inventory_type=InventoryTypeEnum.STORAGE, factory_id=factory.id,
            qty=qty, avg_price=avg, updated_by=w.u2.id,
        )
    db.add(row)
    db.flush()
    _seed_ledger(
        w, factory, item, source_type="test_seed", source_id=0, qty=qty,
        qty_before=0, qty_after=qty, avg_before=None, avg_after=avg,
        performed_at=performed_at,
    )
    return row


def mstock(w, machine, item, qty, avg, *, performed_at=T1):
    db = w.db
    row = MachineItem(workspace_id=machine.workspace_id, machine_id=machine.id, item_id=item.id, qty=qty)
    db.add(row)
    db.flush()
    _seed_ledger(
        w, machine, item, source_type="test_seed", source_id=0, qty=qty,
        qty_before=0, qty_after=qty, avg_before=avg, avg_after=avg,
        value_before=None, value_after=None, performed_at=performed_at,
    )
    return row


def mk_return_item(w, po_line, qty, *, status="completed"):
    ret = PurchaseOrderReturn(
        workspace_id=po_line.workspace_id,
        purchase_order_id=po_line.purchase_order_id,
        return_number=f"PR-TEST-{_n()}",
        status=status,
        created_by=w.u1.id,
    )
    w.db.add(ret)
    w.db.flush()
    item_row = PurchaseOrderReturnItem(
        workspace_id=po_line.workspace_id,
        return_id=ret.id,
        po_item_id=po_line.id,
        item_id=po_line.item_id,
        quantity_returned=qty,
    )
    w.db.add(item_row)
    w.db.flush()
    return item_row


def return_(w, po_line, qty, loc, item, *, ws_id=None, performed_at=T0):
    """Completed purchase return (spec R6a / Notes, G3): a PurchaseOrderReturnItem
    plus a matching stock-out ledger row in the same ledger/location as the
    original posting."""
    ri = mk_return_item(w, po_line, qty)
    _seed_ledger(
        w, loc, item, source_type="purchase_return_item", source_id=ri.id,
        qty=qty, ws_id=ws_id, performed_at=performed_at,
    )
    return ri


def pending_return(w, po_line, qty):
    """Pending return (Conventions: return item only, no ledger row). The
    parent return keeps the default 'completed' status: spec R6a says the
    parent status is not consulted, so the missing ledger row must be the
    only thing stopping netting (verify.md finding 2)."""
    return mk_return_item(w, po_line, qty)


# --------------------------------------------------------------------------- #
# Call wrappers (Conventions: workspace_id=W1, user_id=U1 unless stated)
# --------------------------------------------------------------------------- #

def call_post(w, event_item, po_line, *, po=None):
    return _post_event_item_delta(
        w.db, po=po or w.p, event_item=event_item, po_line=po_line,
        workspace_id=w.w1.id, user_id=w.u1.id,
    )


def call_reverse_item(w, event_item, po_line, *, po=None):
    return _reverse_event_item_posting(
        w.db, po=po or w.p, event_item=event_item, po_line=po_line,
        workspace_id=w.w1.id, user_id=w.u1.id,
    )


def call_reverse_legacy(w, po_line, *, po=None):
    return _reverse_legacy_line_posting(
        w.db, po=po or w.p, po_line=po_line, workspace_id=w.w1.id, user_id=w.u1.id,
    )


def call_reverse_po(w, po_lines, *, po=None):
    return reverse_po_receive_inventory(
        w.db, po or w.p, po_lines, w.w1.id, w.u1.id,
    )


# --------------------------------------------------------------------------- #
# Read-back helpers ("re-read", "New ledger rows", "Nothing written")
# --------------------------------------------------------------------------- #

def max_id(db, model):
    return db.scalar(select(func.max(model.id))) or 0


def new_rows(db, model, before_id):
    db.expire_all()
    return db.execute(
        select(model).where(model.id > before_id).order_by(model.id)
    ).scalars().all()


def snapshot_ids(db):
    return (max_id(db, InventoryLedger), max_id(db, MachineItemLedger), max_id(db, MachineActivityEvent))


def assert_nothing_written(db, before):
    bi, bm, ba = before
    assert new_rows(db, InventoryLedger, bi) == []
    assert new_rows(db, MachineItemLedger, bm) == []
    assert new_rows(db, MachineActivityEvent, ba) == []


def reread_stock_rows(db, factory, item):
    db.expire_all()
    return db.execute(
        select(Inventory).where(
            Inventory.workspace_id == factory.workspace_id,
            Inventory.factory_id == factory.id,
            Inventory.item_id == item.id,
            Inventory.inventory_type == InventoryTypeEnum.STORAGE,
        )
    ).scalars().all()


def reread_stock(db, factory, item):
    rows = reread_stock_rows(db, factory, item)
    assert len(rows) == 1
    return rows[0]


def reread_mstock_rows(db, machine, item):
    db.expire_all()
    return db.execute(
        select(MachineItem).where(
            MachineItem.workspace_id == machine.workspace_id,
            MachineItem.machine_id == machine.id,
            MachineItem.item_id == item.id,
        )
    ).scalars().all()


def reread_mstock(db, machine, item):
    rows = reread_mstock_rows(db, machine, item)
    assert len(rows) == 1
    return rows[0]


def rows_for_source(db, ws_id, source_type, source_id, model=InventoryLedger):
    db.expire_all()
    return db.execute(
        select(model).where(
            model.workspace_id == ws_id,
            model.source_type == source_type,
            model.source_id == source_id,
        ).order_by(model.id)
    ).scalars().all()


def one(rows):
    assert len(rows) == 1
    return rows[0]


def assert_cols(row, **expected):
    for k, v in expected.items():
        actual = getattr(row, k)
        assert actual == v, f"{k}: expected {v!r}, got {actual!r}"


def new_activity(db, machine, before_id):
    db.expire_all()
    return db.execute(
        select(MachineActivityEvent).where(
            MachineActivityEvent.machine_id == machine.id,
            MachineActivityEvent.id > before_id,
        ).order_by(MachineActivityEvent.id)
    ).scalars().all()


# --------------------------------------------------------------------------- #
# Race simulation (Conventions: BUG-680 R1a only)
# --------------------------------------------------------------------------- #

def race_simulation(target_type):
    def storage_fx(session, *, workspace_id, source_type, source_id):
        if source_type == target_type:
            return False
        return _real_storage_ledger_exists(
            session, workspace_id=workspace_id, source_type=source_type, source_id=source_id
        )

    def machine_fx(session, *, workspace_id, source_type, source_id):
        if source_type == target_type:
            return False
        return _real_machine_ledger_exists(
            session, workspace_id=workspace_id, source_type=source_type, source_id=source_id
        )

    return (
        patch("app.managers.po_receive_inventory._storage_ledger_exists", side_effect=storage_fx),
        patch("app.managers.po_receive_inventory._machine_ledger_exists", side_effect=machine_fx),
    )


# =========================================================================== #
# _delta_to_int (5 cases)
# =========================================================================== #

@pytest.mark.parametrize("delta", [Decimal("5"), Decimal("5.0000")], ids=["PRI-D-01a", "PRI-D-01b"])
def test_pri_d_01__whole_positive_delta(delta):
    """PRI-D-01 -- a whole positive delta returns its int value.
    Rules: _delta_to_int R1."""
    result = _delta_to_int(delta, line_number=7)
    assert result == 5
    assert type(result) is int


def test_pri_d_02__whole_negative_delta_returns_abs():
    """PRI-D-02 -- a whole negative delta returns its absolute value.
    Rules: _delta_to_int R2."""
    result = _delta_to_int(Decimal("-3"), line_number=7)
    assert result == 3
    assert type(result) is int


@pytest.mark.parametrize(
    "delta",
    [pytest.param(Decimal("0"), id="PRI-D-03a"), pytest.param(Decimal("-0"), id="PRI-D-03b"),
     pytest.param(Decimal("0.0000"), id="PRI-D-03c")],
)
def test_pri_d_03__zero_delta_returns_zero(delta):
    """PRI-D-03 -- a zero delta returns 0, no exception.
    Rules: _delta_to_int R3."""
    assert _delta_to_int(delta, line_number=7) == 0


@pytest.mark.parametrize(
    "delta",
    [pytest.param(Decimal("2.5"), id="PRI-D-04a"), pytest.param(Decimal("-0.5"), id="PRI-D-04b"),
     pytest.param(Decimal("1.0001"), id="PRI-D-04c")],
)
def test_pri_d_04__fractional_delta_400(delta):
    """PRI-D-04 -- a fractional delta raises 400 with the line number.
    Rules: _delta_to_int R4; Errors row 1."""
    with pytest.raises(HTTPException) as exc:
        _delta_to_int(delta, line_number=7)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Line 7 has a fractional quantity delta; inventory requires whole units"


@pytest.mark.parametrize("delta", [Decimal("1"), Decimal("-1")], ids=["PRI-D-05a", "PRI-D-05b"])
def test_pri_d_05__smallest_nonzero_whole_delta(delta):
    """PRI-D-05 -- a delta of exactly +-1 (smallest non-zero whole delta, the
    other side of the 0 boundary from D-01/D-02) returns 1, no exception.
    Rules: _delta_to_int R1, R2, R3."""
    result = _delta_to_int(delta, line_number=7)
    assert result == 1
    assert type(result) is int


# =========================================================================== #
# _ledger_exists (5 cases), model = MachineItemLedger
# =========================================================================== #

def test_pri_le_01__matching_rows_true(db, w):
    """PRI-LE-01 -- two matching rows gives True; no soft-delete filter (every row counts).
    Rules: _ledger_exists R1, R4."""
    _seed_ledger(w, w.m1, w.x, source_type="po_receive_event_item", source_id=501, qty=1)
    _seed_ledger(w, w.m1, w.x, source_type="po_receive_event_item", source_id=501, qty=1)
    assert _ledger_exists(
        db, workspace_id=w.w1.id, source_type="po_receive_event_item", source_id=501, model=MachineItemLedger
    ) is True


def test_pri_le_02__other_workspace_isolated(db, w):
    """PRI-LE-02 -- a matching row in another workspace does not count there, but does in its own.
    Rules: _ledger_exists R2."""
    _seed_ledger(w, w.m9, w.z2, source_type="po_receive_event_item", source_id=501, qty=1, ws_id=w.w2.id)
    assert _ledger_exists(
        db, workspace_id=w.w1.id, source_type="po_receive_event_item", source_id=501, model=MachineItemLedger
    ) is False
    assert _ledger_exists(
        db, workspace_id=w.w2.id, source_type="po_receive_event_item", source_id=501, model=MachineItemLedger
    ) is True


@pytest.mark.parametrize(
    "source_type,source_id",
    [
        pytest.param("po_receive_event_item_reversal", 501, id="PRI-LE-03a"),
        pytest.param("po_receive_event_item", 502, id="PRI-LE-03b"),
        pytest.param("PO_RECEIVE_EVENT_ITEM", 501, id="PRI-LE-03c"),
    ],
)
def test_pri_le_03__type_or_id_mismatch_false(db, w, source_type, source_id):
    """PRI-LE-03 -- a row with a different type or id (or wrong case) does not count.
    Rules: _ledger_exists R3."""
    _seed_ledger(w, w.m1, w.x, source_type="po_receive_event_item", source_id=501, qty=1)
    assert _ledger_exists(
        db, workspace_id=w.w1.id, source_type=source_type, source_id=source_id, model=MachineItemLedger
    ) is False


def test_pri_le_04__empty_table_false(db, w):
    """PRI-LE-04 -- an empty table gives False.
    Rules: _ledger_exists R1."""
    assert _ledger_exists(
        db, workspace_id=w.w1.id, source_type="po_receive_event_item", source_id=501, model=MachineItemLedger
    ) is False


def test_pri_le_05__only_given_model_table_read(db, w):
    """PRI-LE-05 -- a matching row only in inventory_ledger does not count for MachineItemLedger.
    Rules: _ledger_exists R1."""
    _seed_ledger(w, w.a, w.x, source_type="po_receive_event_item", source_id=501, qty=1)
    assert _ledger_exists(
        db, workspace_id=w.w1.id, source_type="po_receive_event_item", source_id=501, model=MachineItemLedger
    ) is False


# =========================================================================== #
# _storage_ledger_exists (3 cases)
# =========================================================================== #

def test_pri_sle_01__matching_storage_row_true(db, w):
    """PRI-SLE-01 -- a matching inventory_ledger row gives True.
    Rules: _storage_ledger_exists R1."""
    _seed_ledger(w, w.a, w.x, source_type="po_receive_event_item", source_id=601, qty=1)
    assert _storage_ledger_exists(db, workspace_id=w.w1.id, source_type="po_receive_event_item", source_id=601) is True


def test_pri_sle_02__any_inventory_type_counts(db, w):
    """PRI-SLE-02 -- a DAMAGED-type row still counts (any inventory type).
    Rules: _storage_ledger_exists R1."""
    row = InventoryLedger(
        workspace_id=w.w1.id, inventory_type=InventoryTypeEnum.DAMAGED, factory_id=w.a.id, item_id=w.x.id,
        transaction_type="test_fixture", quantity=1, qty_before=0, qty_after=1,
        source_type="po_receive_event_item", source_id=601, performed_at=T0,
    )
    db.add(row)
    db.flush()
    assert _storage_ledger_exists(db, workspace_id=w.w1.id, source_type="po_receive_event_item", source_id=601) is True


def test_pri_sle_03__isolation_from_workspace_type_id_and_other_ledger(db, w):
    """PRI-SLE-03 -- wrong workspace, wrong type, wrong id and the other ledger all don't count.
    Rules: _storage_ledger_exists R1 (via _ledger_exists R2, R3)."""
    _seed_ledger(w, w.f2, w.z2, source_type="po_receive_event_item", source_id=601, qty=1, ws_id=w.w2.id)
    _seed_ledger(w, w.a, w.x, source_type="purchase_order", source_id=601, qty=1)
    _seed_ledger(w, w.a, w.x, source_type="po_receive_event_item", source_id=602, qty=1)
    _seed_ledger(w, w.m1, w.x, source_type="po_receive_event_item", source_id=601, qty=1)
    assert _storage_ledger_exists(db, workspace_id=w.w1.id, source_type="po_receive_event_item", source_id=601) is False


# =========================================================================== #
# _machine_ledger_exists (3 cases)
# =========================================================================== #

def test_pri_mle_01__matching_machine_row_true(db, w):
    """PRI-MLE-01 -- a matching machine_item_ledger row gives True.
    Rules: _machine_ledger_exists R1."""
    _seed_ledger(w, w.m1, w.x, source_type="purchase_order", source_id=701, qty=1)
    assert _machine_ledger_exists(db, workspace_id=w.w1.id, source_type="purchase_order", source_id=701) is True


def test_pri_mle_02__isolation_from_workspace_type_and_id(db, w):
    """PRI-MLE-02 -- wrong workspace, wrong type and wrong id all don't count.
    Rules: _machine_ledger_exists R1 (via _ledger_exists R2, R3)."""
    _seed_ledger(w, w.m9, w.z2, source_type="purchase_order", source_id=701, qty=1, ws_id=w.w2.id)
    _seed_ledger(w, w.m1, w.x, source_type="purchase_order_reversal", source_id=701, qty=1)
    _seed_ledger(w, w.m1, w.x, source_type="purchase_order", source_id=702, qty=1)
    assert _machine_ledger_exists(db, workspace_id=w.w1.id, source_type="purchase_order", source_id=701) is False


def test_pri_mle_03__only_given_model_table_read(db, w):
    """PRI-MLE-03 -- a matching row only in inventory_ledger does not count for machine ledger.
    Rules: _machine_ledger_exists R1."""
    _seed_ledger(w, w.a, w.x, source_type="purchase_order", source_id=701, qty=1)
    assert _machine_ledger_exists(db, workspace_id=w.w1.id, source_type="purchase_order", source_id=701) is False


# =========================================================================== #
# _location_for_po (4 cases) -- po is an unsaved PurchaseOrder
# =========================================================================== #

def test_pri_loc_01__storage():
    """PRI-LOC-01 -- destination_type 'storage' maps to ('storage', destination_id).
    Rules: _location_for_po R1."""
    po = PurchaseOrder(destination_type="storage", destination_id=42)
    assert _location_for_po(po) == ("storage", 42)


def test_pri_loc_02__machine():
    """PRI-LOC-02 -- destination_type 'machine' maps to ('machine', destination_id).
    Rules: _location_for_po R2."""
    po = PurchaseOrder(destination_type="machine", destination_id=43)
    assert _location_for_po(po) == ("machine", 43)


def test_pri_loc_03__project_none():
    """PRI-LOC-03 -- destination_type 'project' maps to None.
    Rules: _location_for_po R3."""
    po = PurchaseOrder(destination_type="project", destination_id=44)
    assert _location_for_po(po) is None


@pytest.mark.parametrize(
    "destination_type",
    [pytest.param("Storage", id="PRI-LOC-04a"), pytest.param("storage ", id="PRI-LOC-04b"),
     pytest.param("MACHINE", id="PRI-LOC-04c"), pytest.param("", id="PRI-LOC-04d"),
     pytest.param("factory", id="PRI-LOC-04e")],
)
def test_pri_loc_04__exact_comparison_other_spellings_none(destination_type):
    """PRI-LOC-04 -- any spelling other than the exact lowercase strings maps to None
    (BUG-681 note: this module's own comparison stays exact; the schema fix is deferred).
    Rules: _location_for_po R3."""
    po = PurchaseOrder(destination_type=destination_type, destination_id=45)
    assert _location_for_po(po) is None


# =========================================================================== #
# _post_event_item_delta (35 cases)
# Default: P destination storage:A, line L1, receive event E1 (T2).
# =========================================================================== #

def test_pri_p_01__storage_positive_delta(db, w):
    """PRI-P-01 -- a positive delta at a storage destination writes one ledger row and updates stock.
    Rules: _post_event_item_delta R6."""
    stock(w, w.a, w.x, 10, Decimal("20.00"))
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    result = call_post(w, e1a, w.l1)
    assert result is True
    rows = rows_for_source(db, w.w1.id, "po_receive_event_item", e1a.id)
    row = one(rows)
    assert_cols(
        row, workspace_id=w.w1.id, inventory_type=InventoryTypeEnum.STORAGE, factory_id=w.a.id, item_id=w.x.id,
        transaction_type="purchase_order", quantity=5, unit_cost=Decimal("26.00"), total_cost=Decimal("130.00"),
        qty_before=10, qty_after=15, avg_price_before=Decimal("20.00"), avg_price_after=Decimal("22.00"),
        source_type="po_receive_event_item", source_id=e1a.id, transfer_source_type=None, transfer_source_id=None,
        notes=f"PO PO-2026-004 line 1 (receive event #{e1a.id})", performed_by=w.u1.id,
    )
    inv = reread_stock(db, w.a, w.x)
    assert inv.qty == 15
    assert inv.avg_price == Decimal("22.00")
    assert inv.updated_by == w.u1.id
    assert new_rows(db, MachineItemLedger, 0) == []
    assert new_rows(db, MachineActivityEvent, 0) == []


def test_pri_p_02__storage_row_created_if_missing(db, w):
    """PRI-P-02 -- with no existing inventories/ledger row, one is created from scratch.
    Rules: _post_event_item_delta R6 (Notes: row created if missing)."""
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    result = call_post(w, e1a, w.l1)
    assert result is True
    row = one(rows_for_source(db, w.w1.id, "po_receive_event_item", e1a.id))
    assert_cols(
        row, qty_before=0, qty_after=5, avg_price_before=None, avg_price_after=Decimal("26.00"),
        unit_cost=Decimal("26.00"), total_cost=Decimal("130.00"),
    )
    inv = reread_stock(db, w.a, w.x)
    assert inv.qty == 5
    assert inv.avg_price == Decimal("26.00")
    assert inv.updated_by == w.u1.id


def test_pri_p_03__weighted_average_rounded(db, w):
    """PRI-P-03 -- the new weighted average is rounded to 0.01.
    Rules: _post_event_item_delta R6 (Notes: avg rounded to 0.01)."""
    stock(w, w.a, w.x, 10, Decimal("20.00"))
    w.l1.unit_price = Decimal("21.00")
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("3"))
    result = call_post(w, e1a, w.l1)
    assert result is True
    row = one(rows_for_source(db, w.w1.id, "po_receive_event_item", e1a.id))
    assert_cols(row, avg_price_before=Decimal("20.00"), avg_price_after=Decimal("20.23"), total_cost=Decimal("63.00"))
    inv = reread_stock(db, w.a, w.x)
    assert inv.qty == 13
    assert inv.avg_price == Decimal("20.23")


def test_pri_p_04__ledger_wins_soft_deleted_row_restored(db, w):
    """PRI-P-04 -- the ledger's latest row wins over a stale/soft-deleted inventories row.
    Rules: _post_event_item_delta R6 (Notes: ledger wins, soft-deleted row restored)."""
    stock(w, w.a, w.x, 10, Decimal("20.00"), pre=(99, Decimal("1.00"), True))
    stale_id = one(reread_stock_rows(db, w.a, w.x)).id
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    result = call_post(w, e1a, w.l1)
    assert result is True
    row = one(rows_for_source(db, w.w1.id, "po_receive_event_item", e1a.id))
    assert_cols(row, qty_before=10, qty_after=15, avg_price_before=Decimal("20.00"), avg_price_after=Decimal("22.00"))
    inv = reread_stock(db, w.a, w.x)
    assert inv.id == stale_id
    assert inv.is_deleted is False
    assert inv.qty == 15
    assert inv.avg_price == Decimal("22.00")


def test_pri_p_05__machine_positive_delta(db, w):
    """PRI-P-05 -- a positive delta at a machine destination writes one machine ledger row,
    updates stock and logs an activity event.
    Rules: _post_event_item_delta R7, R11."""
    w.p.destination_type = "machine"
    w.p.destination_id = w.m1.id
    mstock(w, w.m1, w.x, 10, Decimal("20.00"))
    before_activity = max_id(db, MachineActivityEvent)
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    result = call_post(w, e1a, w.l1)
    assert result is True
    row = one(rows_for_source(db, w.w1.id, "po_receive_event_item", e1a.id, model=MachineItemLedger))
    assert_cols(
        row, workspace_id=w.w1.id, machine_id=w.m1.id, item_id=w.x.id, transaction_type="purchase_order",
        quantity=5, unit_cost=Decimal("26.00"), total_cost=Decimal("130.00"), qty_before=10, qty_after=15,
        avg_price_before=Decimal("20.00"), avg_price_after=Decimal("22.00"), value_before=Decimal("200.00"),
        value_after=Decimal("330.00"), source_type="po_receive_event_item", source_id=e1a.id,
        notes=f"PO PO-2026-004 line 1 (receive event #{e1a.id})", performed_by=w.u1.id,
    )
    mi = reread_mstock(db, w.m1, w.x)
    assert mi.qty == 15
    ev = one(new_activity(db, w.m1, before_activity))
    assert ev.event_type == "purchase_received"
    assert ev.description == "Purchase received: 5 units of Hex Bolt from PO PO-2026-004"
    assert ev.performed_by == w.u1.id
    assert ev.metadata_json == {"item_id": w.x.id, "item_name": "Hex Bolt", "quantity": 5}
    assert "work_order_id" not in ev.metadata_json
    assert new_rows(db, InventoryLedger, 0) == []


def test_pri_p_06__machine_old_average_ignored_when_stock_zero(db, w):
    """PRI-P-06 -- when stock is 0, the stale average is ignored for the new average.
    Rules: _post_event_item_delta R7 (old average ignored when stock 0)."""
    w.p.destination_type = "machine"
    w.p.destination_id = w.m1.id
    mstock(w, w.m1, w.x, 0, Decimal("99.00"))
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    assert call_post(w, e1a, w.l1) is True
    row = one(rows_for_source(db, w.w1.id, "po_receive_event_item", e1a.id, model=MachineItemLedger))
    assert_cols(
        row, qty_before=0, qty_after=5, avg_price_before=Decimal("99.00"), avg_price_after=Decimal("26.00"),
        value_before=Decimal("0.00"), value_after=Decimal("130.00"),
    )
    assert reread_mstock(db, w.m1, w.x).qty == 5


def test_pri_p_07__machine_row_created_cost_zero_without_ledger(db, w):
    """PRI-P-07 -- with no machine_items/ledger row, one is created and cost defaults to 0.
    Rules: _post_event_item_delta R7 (Notes: machine item created; cost 0 without ledger)."""
    w.p.destination_type = "machine"
    w.p.destination_id = w.m1.id
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    assert call_post(w, e1a, w.l1) is True
    row = one(rows_for_source(db, w.w1.id, "po_receive_event_item", e1a.id, model=MachineItemLedger))
    assert_cols(
        row, qty_before=0, qty_after=5, avg_price_before=Decimal("0.00"), avg_price_after=Decimal("26.00"),
        value_before=Decimal("0.00"), value_after=Decimal("130.00"),
    )
    assert reread_mstock(db, w.m1, w.x).qty == 5


def test_pri_p_08__machine_current_cost_is_latest_by_performed_at(db, w):
    """PRI-P-08 -- the machine's current cost is the latest ledger row by performed_at,
    not by insertion order.
    Rules: _post_event_item_delta R7 (Notes: current cost = latest by performed_at)."""
    w.p.destination_type = "machine"
    w.p.destination_id = w.m1.id
    mi = MachineItem(workspace_id=w.w1.id, machine_id=w.m1.id, item_id=w.x.id, qty=10)
    db.add(mi)
    db.flush()
    _seed_ledger(w, w.m1, w.x, source_type="test_fixture", source_id=1, qty=0,
                 qty_before=10, qty_after=10, avg_before=Decimal("20.00"), avg_after=Decimal("20.00"),
                 performed_at=T1)
    _seed_ledger(w, w.m1, w.x, source_type="test_fixture", source_id=2, qty=0,
                 qty_before=10, qty_after=10, avg_before=Decimal("50.00"), avg_after=Decimal("50.00"),
                 performed_at=T0)
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    assert call_post(w, e1a, w.l1) is True
    row = one(rows_for_source(db, w.w1.id, "po_receive_event_item", e1a.id, model=MachineItemLedger))
    assert_cols(row, avg_price_before=Decimal("20.00"), avg_price_after=Decimal("22.00"), value_before=Decimal("200.00"))


def test_pri_p_09__storage_negative_delta(db, w):
    """PRI-P-09 -- a negative (downward correction) delta at storage stocks out and keeps the average.
    Rules: _post_event_item_delta R8."""
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    posted(w, e1a, w.a, w.x, 5)
    stock(w, w.a, w.x, 10, Decimal("20.00"))
    e2 = make_event(db, w.p, T3)
    e2a = make_event_item(db, e2, w.l1, Decimal("-3"))
    assert call_post(w, e2a, w.l1) is True
    row = one(rows_for_source(db, w.w1.id, "po_receive_event_item", e2a.id))
    assert_cols(
        row, inventory_type=InventoryTypeEnum.STORAGE, factory_id=w.a.id, item_id=w.x.id,
        transaction_type="inventory_adjustment", quantity=3, unit_cost=Decimal("20.00"), total_cost=Decimal("60.00"),
        qty_before=10, qty_after=7, avg_price_before=Decimal("20.00"), avg_price_after=Decimal("20.00"),
        source_type="po_receive_event_item", source_id=e2a.id, transfer_destination_type=None,
        transfer_destination_id=None, notes=f"PO PO-2026-004 line 1 (receive event #{e2a.id}) — quantity correction",
        performed_by=w.u1.id,
    )
    inv = reread_stock(db, w.a, w.x)
    assert inv.qty == 7
    assert inv.avg_price == Decimal("20.00")
    assert inv.updated_by == w.u1.id


def test_pri_p_10__storage_negative_delta_null_avg_cost_zero(db, w):
    """PRI-P-10 -- a NULL average bucket treats current cost as 0 for a correction.
    Rules: _post_event_item_delta R8 (bucket avg NULL -> cost 0)."""
    stock(w, w.a, w.x, 5, None)
    e2 = make_event(db, w.p, T3)
    e2a = make_event_item(db, e2, w.l1, Decimal("-2"))
    assert call_post(w, e2a, w.l1) is True
    row = one(rows_for_source(db, w.w1.id, "po_receive_event_item", e2a.id))
    assert_cols(row, unit_cost=Decimal("0.00"), total_cost=Decimal("0.00"), quantity=2, qty_before=5, qty_after=3)
    assert reread_stock(db, w.a, w.x).qty == 3


def test_pri_p_11__machine_negative_delta(db, w):
    """PRI-P-11 -- a negative delta at a machine destination stocks out and logs a correction event.
    Rules: _post_event_item_delta R9."""
    w.p.destination_type = "machine"
    w.p.destination_id = w.m1.id
    mstock(w, w.m1, w.x, 10, Decimal("20.00"))
    before_activity = max_id(db, MachineActivityEvent)
    e2 = make_event(db, w.p, T3)
    e2a = make_event_item(db, e2, w.l1, Decimal("-3"))
    assert call_post(w, e2a, w.l1) is True
    row = one(rows_for_source(db, w.w1.id, "po_receive_event_item", e2a.id, model=MachineItemLedger))
    assert_cols(
        row, machine_id=w.m1.id, item_id=w.x.id, transaction_type="inventory_adjustment", quantity=3,
        unit_cost=Decimal("20.00"), total_cost=Decimal("60.00"), qty_before=10, qty_after=7,
        avg_price_before=Decimal("20.00"), avg_price_after=Decimal("20.00"), value_before=Decimal("200.00"),
        value_after=Decimal("140.00"), source_type="po_receive_event_item", source_id=e2a.id,
        notes=f"PO PO-2026-004 line 1 (receive event #{e2a.id}) — quantity correction",
    )
    assert reread_mstock(db, w.m1, w.x).qty == 7
    ev = one(new_activity(db, w.m1, before_activity))
    assert ev.event_type == "purchase_correction"
    assert ev.description == "Receiving correction: 3 units of Hex Bolt removed from PO PO-2026-004"
    assert ev.performed_by == w.u1.id


def test_pri_p_12__storage_insufficient_stock_400(db, w):
    """PRI-P-12 -- a stock-out larger than what's on hand raises 400 and writes nothing.
    Rules: _post_event_item_delta R10; Errors row 4."""
    stock(w, w.a, w.x, 2, Decimal("20.00"))
    before = snapshot_ids(db)
    e2 = make_event(db, w.p, T3)
    e2a = make_event_item(db, e2, w.l1, Decimal("-3"))
    with pytest.raises(HTTPException) as exc:
        call_post(w, e2a, w.l1)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Insufficient stock (2 available, 3 requested)"
    assert new_rows(db, InventoryLedger, before[0]) == []
    inv = reread_stock(db, w.a, w.x)
    assert inv.qty == 2
    assert inv.avg_price == Decimal("20.00")


def test_pri_p_13__storage_stock_out_to_zero(db, w):
    """PRI-P-13 -- a stock-out exactly equal to stock on hand succeeds, ending at 0.
    Rules: _post_event_item_delta R10."""
    stock(w, w.a, w.x, 3, Decimal("20.00"))
    e2 = make_event(db, w.p, T3)
    e2a = make_event_item(db, e2, w.l1, Decimal("-3"))
    assert call_post(w, e2a, w.l1) is True
    row = one(rows_for_source(db, w.w1.id, "po_receive_event_item", e2a.id))
    assert_cols(row, qty_before=3, qty_after=0)
    assert reread_stock(db, w.a, w.x).qty == 0


def test_pri_p_14__machine_insufficient_stock_400(db, w):
    """PRI-P-14 -- machine insufficient stock raises 400 and writes nothing.
    Rules: _post_event_item_delta R10; Errors row 5."""
    w.p.destination_type = "machine"
    w.p.destination_id = w.m1.id
    mstock(w, w.m1, w.x, 2, Decimal("20.00"))
    before = snapshot_ids(db)
    e2 = make_event(db, w.p, T3)
    e2a = make_event_item(db, e2, w.l1, Decimal("-3"))
    with pytest.raises(HTTPException) as exc:
        call_post(w, e2a, w.l1)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Insufficient machine stock (2 available, 3 requested)"
    assert_nothing_written(db, before)
    assert reread_mstock(db, w.m1, w.x).qty == 2


def test_pri_p_15__machine_stock_out_to_zero(db, w):
    """PRI-P-15 -- a machine stock-out exactly equal to stock on hand succeeds, logging a correction.
    Rules: _post_event_item_delta R10."""
    w.p.destination_type = "machine"
    w.p.destination_id = w.m1.id
    mstock(w, w.m1, w.x, 3, Decimal("20.00"))
    before_activity = max_id(db, MachineActivityEvent)
    e2 = make_event(db, w.p, T3)
    e2a = make_event_item(db, e2, w.l1, Decimal("-3"))
    assert call_post(w, e2a, w.l1) is True
    row = one(rows_for_source(db, w.w1.id, "po_receive_event_item", e2a.id, model=MachineItemLedger))
    assert_cols(row, qty_after=0)
    assert reread_mstock(db, w.m1, w.x).qty == 0
    ev = one(new_activity(db, w.m1, before_activity))
    assert ev.event_type == "purchase_correction"


def test_pri_p_16__already_posted_returns_false(db, w):
    """PRI-P-16 -- a receive line already posted writes nothing and returns False.
    Rules: _post_event_item_delta R1."""
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    posted(w, e1a, w.a, w.x, 5)
    inv0 = stock(w, w.a, w.x, 5, Decimal("26.00"))
    before = snapshot_ids(db)
    assert call_post(w, e1a, w.l1) is False
    assert_nothing_written(db, before)
    assert len(rows_for_source(db, w.w1.id, "po_receive_event_item", e1a.id)) == 1
    inv = reread_stock(db, w.a, w.x)
    assert inv.qty == 5
    assert inv.avg_price == Decimal("26.00")
    assert inv.updated_by == inv0.updated_by


def test_pri_p_17__already_posted_in_either_ledger(db, w):
    """PRI-P-17 -- already posted in the OTHER ledger (machine) still blocks a storage post.
    Rules: _post_event_item_delta R1 (either ledger)."""
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    posted(w, e1a, w.m1, w.x, 5)
    stock(w, w.a, w.x, 10, Decimal("20.00"))
    before = snapshot_ids(db)
    assert call_post(w, e1a, w.l1) is False
    assert_nothing_written(db, before)
    assert reread_stock(db, w.a, w.x).qty == 10


def test_pri_p_18__already_posted_other_workspace_does_not_block(db, w):
    """PRI-P-18 -- a matching source row in another workspace does not block this one.
    Rules: _post_event_item_delta R1 (other workspace)."""
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    other = _seed_ledger(w, w.f2, w.z2, source_type="po_receive_event_item", source_id=e1a.id, qty=1, ws_id=w.w2.id)
    other_before = {
        c: getattr(other, c)
        for c in (
            "workspace_id", "factory_id", "item_id", "quantity", "qty_before", "qty_after",
            "avg_price_before", "avg_price_after", "source_type", "source_id",
        )
    }
    stock(w, w.a, w.x, 10, Decimal("20.00"))
    assert call_post(w, e1a, w.l1) is True
    rows = rows_for_source(db, w.w1.id, "po_receive_event_item", e1a.id)
    assert len(rows) == 1
    assert reread_stock(db, w.a, w.x).qty == 15
    db.expire_all()
    still_there = db.get(InventoryLedger, other.id)
    assert still_there is not None
    assert_cols(still_there, **other_before)


def test_pri_p_19__project_destination_returns_false(db, w):
    """PRI-P-19 -- a project destination writes nothing and creates no stock rows.
    Rules: _post_event_item_delta R2."""
    w.p.destination_type = "project"
    w.p.destination_id = 77
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    before = snapshot_ids(db)
    assert call_post(w, e1a, w.l1) is False
    assert_nothing_written(db, before)
    assert reread_stock_rows(db, w.a, w.x) == []


def test_pri_p_20__project_destination_even_fractional_no_error(db, w):
    """PRI-P-20 -- project destination returns False even for a fractional delta (no exception).
    Rules: _post_event_item_delta R2 (even fractional)."""
    w.p.destination_type = "project"
    w.p.destination_id = 77
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("2.5"))
    before = snapshot_ids(db)
    assert call_post(w, e1a, w.l1) is False
    assert_nothing_written(db, before)


def test_pri_p_21__destination_comparison_is_exact(db, w):
    """PRI-P-21 -- a 'Storage' destination (case/whitespace variant) is treated like a project (BUG-681 note).
    Rules: _post_event_item_delta R2."""
    w.p.destination_type = "Storage"
    w.p.destination_id = w.a.id
    stock(w, w.a, w.x, 10, Decimal("20.00"))
    before = snapshot_ids(db)
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    assert call_post(w, e1a, w.l1) is False
    assert_nothing_written(db, before)
    assert reread_stock(db, w.a, w.x).qty == 10


def test_pri_p_22__zero_delta_returns_false(db, w):
    """PRI-P-22 -- a zero delta writes nothing and creates no stock row.
    Rules: _post_event_item_delta R3."""
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("0"))
    before = snapshot_ids(db)
    assert call_post(w, e1a, w.l1) is False
    assert_nothing_written(db, before)
    assert reread_stock_rows(db, w.a, w.x) == []


def test_pri_p_23__fractional_delta_400(db, w):
    """PRI-P-23 -- a fractional delta at a storage destination raises 400 with the line number.
    Rules: _post_event_item_delta R4; Errors row 1."""
    stock(w, w.a, w.x, 10, Decimal("20.00"))
    w.l1.line_number = 3
    before = snapshot_ids(db)
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("2.5"))
    with pytest.raises(HTTPException) as exc:
        call_post(w, e1a, w.l1)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Line 3 has a fractional quantity delta; inventory requires whole units"
    assert_nothing_written(db, before)


@pytest.mark.parametrize("delta", [pytest.param(Decimal("5"), id="PRI-P-24a"), pytest.param(Decimal("-3"), id="PRI-P-24b")])
def test_pri_p_24__null_unit_price_invalid_operation(db, w, delta):
    """PRI-P-24 -- a NULL unit price raises decimal.InvalidOperation (not HTTPException).
    Rules: _post_event_item_delta R5; Errors row 6."""
    stock(w, w.a, w.x, 10, Decimal("20.00"))
    w.l1.unit_price = None
    before = snapshot_ids(db)
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, delta)
    with pytest.raises(InvalidOperation):
        call_post(w, e1a, w.l1)
    assert_nothing_written(db, before)
    inv = reread_stock(db, w.a, w.x)
    assert inv.qty == 10
    assert inv.avg_price == Decimal("20.00")


def test_pri_p_25__soft_deleted_item_name_still_used(db, w):
    """PRI-P-25 -- a soft-deleted item's name is still used in the activity description.
    Rules: _post_event_item_delta R11 (soft-deleted item name)."""
    w.p.destination_type = "machine"
    w.p.destination_id = w.m1.id
    ld = make_line(db, w.p, w.xd.id, line_number=1, unit_price=Decimal("10.00"))
    mstock(w, w.m1, w.xd, 0, None)
    before_activity = max_id(db, MachineActivityEvent)
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, ld, Decimal("2"))
    assert call_post(w, e1a, ld) is True
    ev = one(new_activity(db, w.m1, before_activity))
    assert ev.description == "Purchase received: 2 units of Old Gasket from PO PO-2026-004"
    assert ev.metadata_json["item_name"] == "Old Gasket"


def test_pri_p_26__item_not_in_workspace_falls_back_to_id(db, w):
    """PRI-P-26 -- an item that doesn't exist in this workspace falls back to 'Item #<id>'.
    Rules: _post_event_item_delta R11 (item not in workspace)."""
    w.p.destination_type = "machine"
    w.p.destination_id = w.m1.id
    lz = make_line(db, w.p, w.z2.id, line_number=1, unit_price=Decimal("10.00"))
    before_activity = max_id(db, MachineActivityEvent)
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, lz, Decimal("2"))
    assert call_post(w, e1a, lz) is True
    ev = one(new_activity(db, w.m1, before_activity))
    assert ev.description == f"Purchase received: 2 units of Item #{w.z2.id} from PO PO-2026-004"
    assert ev.metadata_json["item_name"] == f"Item #{w.z2.id}"
    assert ev.metadata_json["item_id"] == w.z2.id


@pytest.mark.parametrize(
    "dest",
    [pytest.param("missing", id="PRI-P-27a"), pytest.param("other_ws", id="PRI-P-27b")],
)
def test_pri_p_27__storage_factory_404(db, w, dest):
    """PRI-P-27 -- an unknown or another-workspace factory id raises 404 and writes nothing.
    Rules: _post_event_item_delta R12; Errors row 2."""
    if dest == "missing":
        factory_id = 999999
    else:
        factory_id = w.f2.id
    w.p.destination_type = "storage"
    w.p.destination_id = factory_id
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    before = snapshot_ids(db)
    with pytest.raises(HTTPException) as exc:
        call_post(w, e1a, w.l1)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Factory with ID {factory_id} not found"
    assert_nothing_written(db, before)
    assert db.execute(
        select(Inventory).where(Inventory.factory_id == factory_id, Inventory.item_id == w.x.id)
    ).scalars().all() == []


@pytest.mark.parametrize(
    "dest",
    [pytest.param("missing", id="PRI-P-28a"), pytest.param("other_ws", id="PRI-P-28b")],
)
def test_pri_p_28__machine_404(db, w, dest):
    """PRI-P-28 -- an unknown or another-workspace machine id raises 404 and writes nothing.
    Rules: _post_event_item_delta R12; Errors row 3."""
    machine_id = 999999 if dest == "missing" else w.m9.id
    w.p.destination_type = "machine"
    w.p.destination_id = machine_id
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    before = snapshot_ids(db)
    with pytest.raises(HTTPException) as exc:
        call_post(w, e1a, w.l1)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Machine with ID {machine_id} not found"
    assert_nothing_written(db, before)
    assert db.execute(
        select(MachineItem).where(MachineItem.machine_id == machine_id, MachineItem.item_id == w.x.id)
    ).scalars().all() == []


@pytest.mark.xfail(strict=True, reason=BUG_684)
def test_pri_p_29__soft_deleted_factory_rejected(db, w):
    """PRI-P-29 -- receiving into a soft-deleted factory is rejected with 400 before writing anything.
    Rules: _post_event_item_delta R12a; Errors row 7 [BUG-684]."""
    w.p.destination_type = "storage"
    w.p.destination_id = w.ad.id
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    with pytest.raises(HTTPException) as exc:
        call_post(w, e1a, w.l1)
    assert exc.value.status_code == 400
    assert exc.value.detail == f"Factory with ID {w.ad.id} has been deleted"
    assert db.execute(
        select(Inventory).where(Inventory.factory_id == w.ad.id, Inventory.item_id == w.x.id)
    ).scalars().all() == []


@pytest.mark.xfail(strict=True, reason=BUG_684)
def test_pri_p_32__soft_deleted_machine_rejected(db, w):
    """PRI-P-32 -- receiving into a soft-deleted machine is rejected with 400 before writing anything.
    Rules: _post_event_item_delta R12a; Errors row 7 [BUG-684]."""
    w.p.destination_type = "machine"
    w.p.destination_id = w.md.id
    before_activity = max_id(db, MachineActivityEvent)
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    with pytest.raises(HTTPException) as exc:
        call_post(w, e1a, w.l1)
    assert exc.value.status_code == 400
    assert exc.value.detail == f"Machine with ID {w.md.id} has been deleted"
    assert db.execute(
        select(MachineItem).where(MachineItem.machine_id == w.md.id, MachineItem.item_id == w.x.id)
    ).scalars().all() == []
    assert new_activity(db, w.md, before_activity) == []


@pytest.mark.xfail(strict=True, reason=BUG_680)
def test_pri_p_30__race_duplicate_storage_post(db, w):
    """PRI-P-30 -- a concurrent duplicate storage post raises IntegrityError (DB index); none today.
    Rules: _post_event_item_delta R1a; Errors row 8 [BUG-680]."""
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    posted(w, e1a, w.a, w.x, 5)
    stock(w, w.a, w.x, 5, Decimal("26.00"))
    p1, p2 = race_simulation("po_receive_event_item")
    with p1, p2:
        with pytest.raises(IntegrityError):
            with db.begin_nested():
                call_post(w, e1a, w.l1)
    rows = rows_for_source(db, w.w1.id, "po_receive_event_item", e1a.id)
    assert len(rows) == 1
    assert reread_stock(db, w.a, w.x).qty == 5


@pytest.mark.xfail(strict=True, reason=BUG_680)
def test_pri_p_31__race_duplicate_machine_post(db, w):
    """PRI-P-31 -- a concurrent duplicate machine post raises IntegrityError (DB index); none today.
    Rules: _post_event_item_delta R1a; Errors row 8 [BUG-680]."""
    w.p.destination_type = "machine"
    w.p.destination_id = w.m1.id
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    posted(w, e1a, w.m1, w.x, 5)
    mstock(w, w.m1, w.x, 5, Decimal("26.00"))
    p1, p2 = race_simulation("po_receive_event_item")
    with p1, p2:
        with pytest.raises(IntegrityError):
            with db.begin_nested():
                call_post(w, e1a, w.l1)
    rows = rows_for_source(db, w.w1.id, "po_receive_event_item", e1a.id, model=MachineItemLedger)
    assert len(rows) == 1
    assert reread_mstock(db, w.m1, w.x).qty == 5


def test_pri_p_33__written_rows_scoped_to_workspace(db, w):
    """PRI-P-33 -- the new ledger row is scoped to this workspace; another workspace's row is untouched.
    Rules: _post_event_item_delta R6 (workspace scoping of rows written)."""
    stock(w, w.a, w.x, 10, Decimal("20.00"))
    other = Inventory(
        workspace_id=w.w2.id, item_id=w.z2.id, inventory_type=InventoryTypeEnum.STORAGE,
        factory_id=w.f2.id, qty=4, avg_price=None, updated_by=w.u2.id,
    )
    db.add(other)
    db.flush()
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    assert call_post(w, e1a, w.l1) is True
    row = one(rows_for_source(db, w.w1.id, "po_receive_event_item", e1a.id))
    assert row.workspace_id == w.w1.id
    db.expire_all()
    assert db.get(Inventory, other.id).qty == 4


def test_pri_p_34__smallest_positive_delta_stocks_in_one(db, w):
    """PRI-P-34 -- a delta of exactly +1 (smallest positive, other side of the
    delta==0 boundary from P-01/P-22) still stocks in, 1 unit.
    Rules: _post_event_item_delta R3, R6 (smallest positive delta)."""
    stock(w, w.a, w.x, 10, Decimal("20.00"))
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("1"))
    result = call_post(w, e1a, w.l1)
    assert result is True
    row = one(rows_for_source(db, w.w1.id, "po_receive_event_item", e1a.id))
    assert_cols(
        row, factory_id=w.a.id, item_id=w.x.id, transaction_type="purchase_order",
        quantity=1, unit_cost=Decimal("26.00"), total_cost=Decimal("26.00"),
        qty_before=10, qty_after=11, avg_price_before=Decimal("20.00"), avg_price_after=Decimal("20.55"),
        source_type="po_receive_event_item", source_id=e1a.id, performed_by=w.u1.id,
    )
    inv = reread_stock(db, w.a, w.x)
    assert inv.qty == 11
    assert inv.avg_price == Decimal("20.55")
    assert inv.updated_by == w.u1.id
    assert new_rows(db, MachineItemLedger, 0) == []


def test_pri_p_35__smallest_negative_delta_stocks_out_one(db, w):
    """PRI-P-35 -- a delta of exactly -1 (smallest negative, other side of the
    delta==0 boundary) still stocks out, 1 unit.
    Rules: _post_event_item_delta R3, R8 (smallest negative delta)."""
    stock(w, w.a, w.x, 10, Decimal("20.00"))
    e2 = make_event(db, w.p, T3)
    e2a = make_event_item(db, e2, w.l1, Decimal("-1"))
    result = call_post(w, e2a, w.l1)
    assert result is True
    row = one(rows_for_source(db, w.w1.id, "po_receive_event_item", e2a.id))
    assert_cols(
        row, factory_id=w.a.id, item_id=w.x.id, transaction_type="inventory_adjustment",
        quantity=1, unit_cost=Decimal("20.00"), total_cost=Decimal("20.00"),
        qty_before=10, qty_after=9, avg_price_before=Decimal("20.00"), avg_price_after=Decimal("20.00"),
        source_type="po_receive_event_item", source_id=e2a.id,
        notes=f"PO PO-2026-004 line 1 (receive event #{e2a.id}) — quantity correction",
        performed_by=w.u1.id,
    )
    inv = reread_stock(db, w.a, w.x)
    assert inv.qty == 9
    assert inv.avg_price == Decimal("20.00")
    assert inv.updated_by == w.u1.id


# =========================================================================== #
# post_receive_event_inventory (6 cases)
# =========================================================================== #

def test_pri_pr_01__two_pairs_both_posted(db, w):
    """PRI-PR-01 -- two distinct pairs are both posted, in order.
    Rules: post_receive_event_inventory R1."""
    stock(w, w.a, w.x, 10, Decimal("20.00"))
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    e1b = make_event_item(db, e1, w.l2, Decimal("3"))
    result = post_receive_event_inventory(db, w.p, [(e1a, w.l1), (e1b, w.l2)], w.w1.id, w.u1.id)
    assert result == 2
    db.expire_all()
    ids = {
        "a": one(rows_for_source(db, w.w1.id, "po_receive_event_item", e1a.id)).id,
        "b": one(rows_for_source(db, w.w1.id, "po_receive_event_item", e1b.id)).id,
    }
    assert ids["a"] < ids["b"]
    assert reread_stock(db, w.a, w.x).qty == 15
    assert reread_stock(db, w.a, w.x).avg_price == Decimal("22.00")
    ay = reread_stock(db, w.a, w.y)
    assert ay.qty == 3
    assert ay.avg_price == Decimal("4.00")


def test_pri_pr_02__only_true_results_counted(db, w):
    """PRI-PR-02 -- a zero-delta pair returns False and is not counted.
    Rules: post_receive_event_inventory R1 (count only True)."""
    stock(w, w.a, w.x, 10, Decimal("20.00"))
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("0"))
    e1b = make_event_item(db, e1, w.l2, Decimal("3"))
    before = snapshot_ids(db)
    result = post_receive_event_inventory(db, w.p, [(e1a, w.l1), (e1b, w.l2)], w.w1.id, w.u1.id)
    assert result == 1
    assert rows_for_source(db, w.w1.id, "po_receive_event_item", e1a.id) == []
    new_inv_rows = new_rows(db, InventoryLedger, before[0])
    assert len(new_inv_rows) == 1
    assert new_inv_rows[0].source_id == e1b.id
    assert new_rows(db, MachineItemLedger, before[1]) == []
    assert new_rows(db, MachineActivityEvent, before[2]) == []
    assert reread_stock(db, w.a, w.x).qty == 10


def test_pri_pr_03__empty_sequence_returns_zero(db, w):
    """PRI-PR-03 -- an empty sequence returns 0 and writes nothing.
    Rules: post_receive_event_inventory R2."""
    stock(w, w.a, w.x, 10, Decimal("20.00"))
    before = snapshot_ids(db)
    result = post_receive_event_inventory(db, w.p, [], w.w1.id, w.u1.id)
    assert result == 0
    assert_nothing_written(db, before)


def test_pri_pr_04__same_line_twice_posted_once(db, w):
    """PRI-PR-04 -- the same receive line appearing twice is posted once (second sees first's row).
    Rules: post_receive_event_inventory R3."""
    stock(w, w.a, w.x, 10, Decimal("20.00"))
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    result = post_receive_event_inventory(db, w.p, [(e1a, w.l1), (e1a, w.l1)], w.w1.id, w.u1.id)
    assert result == 1
    assert len(rows_for_source(db, w.w1.id, "po_receive_event_item", e1a.id)) == 1
    assert reread_stock(db, w.a, w.x).qty == 15


def test_pri_pr_05__error_propagates_earlier_rows_kept(db, w):
    """PRI-PR-05 -- an error on a later pair propagates; earlier pairs' writes are kept (no rollback).
    Rules: post_receive_event_inventory R4."""
    stock(w, w.a, w.x, 10, Decimal("20.00"))
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    e1b = make_event_item(db, e1, w.l2, Decimal("1.5"))
    with pytest.raises(HTTPException) as exc:
        post_receive_event_inventory(db, w.p, [(e1a, w.l1), (e1b, w.l2)], w.w1.id, w.u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Line 2 has a fractional quantity delta; inventory requires whole units"
    assert len(rows_for_source(db, w.w1.id, "po_receive_event_item", e1a.id)) == 1
    assert reread_stock(db, w.a, w.x).qty == 15
    assert rows_for_source(db, w.w1.id, "po_receive_event_item", e1b.id) == []


def test_pri_pr_06__project_destination_returns_zero(db, w):
    """PRI-PR-06 -- a project destination posts nothing for any number of pairs.
    Rules: post_receive_event_inventory R1 (via _post_event_item_delta R2)."""
    w.p.destination_type = "project"
    w.p.destination_id = 77
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    e1b = make_event_item(db, e1, w.l2, Decimal("3"))
    before = snapshot_ids(db)
    result = post_receive_event_inventory(db, w.p, [(e1a, w.l1), (e1b, w.l2)], w.w1.id, w.u1.id)
    assert result == 0
    assert_nothing_written(db, before)


# =========================================================================== #
# _reverse_event_item_posting (22 cases)
# Call: _reverse_event_item_posting(db, po=P, event_item=E1.a, po_line=L1, ...)
# =========================================================================== #

def test_pri_re_01__storage_reversal_same_location(db, w):
    """PRI-RE-01 -- reversing a positive receive at storage stocks out and keeps the average.
    Rules: _reverse_event_item_posting R6, R9 (same location)."""
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    posted(w, e1a, w.a, w.x, 5)
    stock(w, w.a, w.x, 15, Decimal("22.00"))
    result = call_reverse_item(w, e1a, w.l1)
    assert result is True
    row = one(rows_for_source(db, w.w1.id, "po_receive_event_item_reversal", e1a.id))
    assert_cols(
        row, inventory_type=InventoryTypeEnum.STORAGE, factory_id=w.a.id, item_id=w.x.id,
        transaction_type="inventory_adjustment", quantity=5, unit_cost=Decimal("22.00"), total_cost=Decimal("110.00"),
        qty_before=15, qty_after=10, avg_price_before=Decimal("22.00"), avg_price_after=Decimal("22.00"),
        source_type="po_receive_event_item_reversal", source_id=e1a.id,
        notes=f"PO PO-2026-004 voided — reverse receive event #{e1a.id} line 1", performed_by=w.u1.id,
    )
    inv = reread_stock(db, w.a, w.x)
    assert inv.qty == 10
    assert inv.avg_price == Decimal("22.00")
    assert inv.updated_by == w.u1.id


def test_pri_re_02__machine_reversal(db, w):
    """PRI-RE-02 -- reversing a positive receive at a machine stocks out and logs an activity event.
    Rules: _reverse_event_item_posting R6."""
    w.p.destination_type = "machine"
    w.p.destination_id = w.m1.id
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    posted(w, e1a, w.m1, w.x, 5)
    mstock(w, w.m1, w.x, 15, Decimal("22.00"))
    before_activity = max_id(db, MachineActivityEvent)
    assert call_reverse_item(w, e1a, w.l1) is True
    row = one(rows_for_source(db, w.w1.id, "po_receive_event_item_reversal", e1a.id, model=MachineItemLedger))
    assert_cols(
        row, machine_id=w.m1.id, transaction_type="inventory_adjustment", quantity=5, unit_cost=Decimal("22.00"),
        total_cost=Decimal("110.00"), qty_before=15, qty_after=10, avg_price_before=Decimal("22.00"),
        avg_price_after=Decimal("22.00"), value_before=Decimal("330.00"), value_after=Decimal("220.00"),
        source_type="po_receive_event_item_reversal", source_id=e1a.id,
        notes=f"PO PO-2026-004 voided — reverse receive event #{e1a.id} line 1", performed_by=w.u1.id,
    )
    assert reread_mstock(db, w.m1, w.x).qty == 10
    ev = one(new_activity(db, w.m1, before_activity))
    assert ev.event_type == "purchase_reversed"
    assert ev.description == "PO PO-2026-004 voided — 5 units of Hex Bolt removed"
    assert ev.performed_by == w.u1.id


def test_pri_re_03__storage_reversal_of_negative_delta(db, w):
    """PRI-RE-03 -- reversing a downward correction stocks back in with cost from the line's unit price.
    Rules: _reverse_event_item_posting R7."""
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("-2"))
    posted(w, e1a, w.a, w.x, 2)
    stock(w, w.a, w.x, 8, Decimal("20.00"))
    assert call_reverse_item(w, e1a, w.l1) is True
    row = one(rows_for_source(db, w.w1.id, "po_receive_event_item_reversal", e1a.id))
    assert_cols(
        row, transaction_type="inventory_adjustment", quantity=2, unit_cost=Decimal("26.00"),
        total_cost=Decimal("52.00"), qty_before=8, qty_after=10, avg_price_before=Decimal("20.00"),
        avg_price_after=Decimal("21.20"), source_type="po_receive_event_item_reversal", source_id=e1a.id,
        notes=f"PO PO-2026-004 voided — reverse receive event #{e1a.id} line 1",
    )
    inv = reread_stock(db, w.a, w.x)
    assert inv.qty == 10
    assert inv.avg_price == Decimal("21.20")


def test_pri_re_04__machine_reversal_of_negative_delta(db, w):
    """PRI-RE-04 -- reversing a downward correction at a machine stocks back in and logs restore activity.
    Rules: _reverse_event_item_posting R7."""
    w.p.destination_type = "machine"
    w.p.destination_id = w.m1.id
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("-2"))
    posted(w, e1a, w.m1, w.x, 2)
    mstock(w, w.m1, w.x, 8, Decimal("20.00"))
    before_activity = max_id(db, MachineActivityEvent)
    assert call_reverse_item(w, e1a, w.l1) is True
    row = one(rows_for_source(db, w.w1.id, "po_receive_event_item_reversal", e1a.id, model=MachineItemLedger))
    assert_cols(
        row, quantity=2, unit_cost=Decimal("26.00"), qty_before=8, qty_after=10, avg_price_before=Decimal("20.00"),
        avg_price_after=Decimal("21.20"), value_before=Decimal("160.00"), value_after=Decimal("212.00"),
        source_type="po_receive_event_item_reversal",
    )
    assert reread_mstock(db, w.m1, w.x).qty == 10
    ev = one(new_activity(db, w.m1, before_activity))
    assert ev.event_type == "purchase_reversed"
    assert ev.description == "PO PO-2026-004 voided — 2 units of Hex Bolt restored"


def test_pri_re_05__already_reversed_returns_false(db, w):
    """PRI-RE-05 -- a receive line already reversed writes nothing.
    Rules: _reverse_event_item_posting R1."""
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    posted(w, e1a, w.a, w.x, 5)
    reversed_(w, e1a, w.a, w.x)
    stock(w, w.a, w.x, 10, Decimal("22.00"))
    before = snapshot_ids(db)
    assert call_reverse_item(w, e1a, w.l1) is False
    assert_nothing_written(db, before)


def test_pri_re_06__already_reversed_in_either_ledger(db, w):
    """PRI-RE-06 -- already reversed in the OTHER ledger (machine) still blocks a storage reversal.
    Rules: _reverse_event_item_posting R1 (either ledger)."""
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    posted(w, e1a, w.a, w.x, 5)
    reversed_(w, e1a, w.m1, w.x)
    stock(w, w.a, w.x, 10, Decimal("22.00"))
    before = snapshot_ids(db)
    assert call_reverse_item(w, e1a, w.l1) is False
    assert_nothing_written(db, before)


def test_pri_re_07__reversal_in_other_workspace_does_not_block(db, w):
    """PRI-RE-07 -- a reversal row in another workspace does not block this one.
    Rules: _reverse_event_item_posting R1 (other workspace)."""
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    posted(w, e1a, w.a, w.x, 5)
    _seed_ledger(w, w.f2, w.z2, source_type="po_receive_event_item_reversal", source_id=e1a.id, qty=1, ws_id=w.w2.id)
    stock(w, w.a, w.x, 15, Decimal("22.00"))
    assert call_reverse_item(w, e1a, w.l1) is True
    assert len(rows_for_source(db, w.w1.id, "po_receive_event_item_reversal", e1a.id)) == 1
    assert reread_stock(db, w.a, w.x).qty == 10


def test_pri_re_08__never_posted_returns_false(db, w):
    """PRI-RE-08 -- a receive line that was never posted writes nothing.
    Rules: _reverse_event_item_posting R2."""
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    stock(w, w.a, w.x, 15, Decimal("22.00"))
    before = snapshot_ids(db)
    assert call_reverse_item(w, e1a, w.l1) is False
    assert_nothing_written(db, before)


def test_pri_re_09__posted_only_in_other_workspace_returns_false(db, w):
    """PRI-RE-09 -- a posting row only in another workspace means "never posted" here.
    Rules: _reverse_event_item_posting R2 (other workspace)."""
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    _seed_ledger(w, w.f2, w.z2, source_type="po_receive_event_item", source_id=e1a.id, qty=1, ws_id=w.w2.id)
    stock(w, w.a, w.x, 15, Decimal("22.00"))
    before = snapshot_ids(db)
    assert call_reverse_item(w, e1a, w.l1) is False
    assert_nothing_written(db, before)


def test_pri_re_10__zero_delta_returns_false(db, w):
    """PRI-RE-10 -- a zero-delta receive line writes nothing on reversal.
    Rules: _reverse_event_item_posting R4."""
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("0"))
    posted(w, e1a, w.a, w.x, 0)
    stock(w, w.a, w.x, 15, Decimal("22.00"))
    before = snapshot_ids(db)
    assert call_reverse_item(w, e1a, w.l1) is False
    assert_nothing_written(db, before)


def test_pri_re_11__fractional_delta_400(db, w):
    """PRI-RE-11 -- a fractional delta raises 400 on reversal.
    Rules: _reverse_event_item_posting R5."""
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("2.5"))
    posted(w, e1a, w.a, w.x, 2)
    stock(w, w.a, w.x, 15, Decimal("22.00"))
    before = snapshot_ids(db)
    with pytest.raises(HTTPException) as exc:
        call_reverse_item(w, e1a, w.l1)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Line 1 has a fractional quantity delta; inventory requires whole units"
    assert_nothing_written(db, before)


def test_pri_re_12__storage_insufficient_stock_400(db, w):
    """PRI-RE-12 -- reversing into insufficient storage stock raises 400 (Q2: intended).
    Rules: _reverse_event_item_posting R8 (Q2)."""
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    posted(w, e1a, w.a, w.x, 5)
    stock(w, w.a, w.x, 2, Decimal("22.00"))
    before = snapshot_ids(db)
    with pytest.raises(HTTPException) as exc:
        call_reverse_item(w, e1a, w.l1)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Insufficient stock (2 available, 5 requested)"
    assert_nothing_written(db, before)
    assert reread_stock(db, w.a, w.x).qty == 2


def test_pri_re_13__machine_insufficient_stock_400(db, w):
    """PRI-RE-13 -- reversing into insufficient machine stock raises 400 (Q2: intended).
    Rules: _reverse_event_item_posting R8 (Q2)."""
    w.p.destination_type = "machine"
    w.p.destination_id = w.m1.id
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("10"))
    posted(w, e1a, w.m1, w.x, 10)
    mstock(w, w.m1, w.x, 2, Decimal("22.00"))
    before = snapshot_ids(db)
    with pytest.raises(HTTPException) as exc:
        call_reverse_item(w, e1a, w.l1)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Insufficient machine stock (2 available, 10 requested)"
    assert_nothing_written(db, before)
    assert reread_mstock(db, w.m1, w.x).qty == 2


def test_pri_re_14__null_unit_price_invalid_operation(db, w):
    """PRI-RE-14 -- a NULL unit price raises decimal.InvalidOperation on reversal.
    Rules: _reverse_event_item_posting R10 (unit price NULL)."""
    w.l1.unit_price = None
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    posted(w, e1a, w.a, w.x, 5)
    stock(w, w.a, w.x, 15, Decimal("22.00"))
    before = snapshot_ids(db)
    from decimal import InvalidOperation
    with pytest.raises(InvalidOperation):
        call_reverse_item(w, e1a, w.l1)
    assert_nothing_written(db, before)


def test_pri_re_15__storage_404_other_workspace_factory(db, w):
    """PRI-RE-15 -- the posting's recorded factory belongs to another workspace: 404.
    Rules: _reverse_event_item_posting R10 (via _post_event_item_delta R12)."""
    w.p.destination_type = "storage"
    w.p.destination_id = w.f2.id
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    row = InventoryLedger(
        workspace_id=w.w1.id, inventory_type=InventoryTypeEnum.STORAGE, factory_id=w.f2.id, item_id=w.x.id,
        transaction_type="test_fixture", quantity=5, qty_before=0, qty_after=5,
        source_type="po_receive_event_item", source_id=e1a.id, performed_at=T0,
    )
    db.add(row)
    db.flush()
    before = snapshot_ids(db)
    with pytest.raises(HTTPException) as exc:
        call_reverse_item(w, e1a, w.l1)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Factory with ID {w.f2.id} not found"
    assert_nothing_written(db, before)


def test_pri_re_16__reversal_still_works_at_deleted_location(db, w):
    """PRI-RE-16 -- a reversal can still remove stock at a since soft-deleted factory.
    Rules: _reverse_event_item_posting R10 (P R12a scope: reversals still work at a deleted location)."""
    w.p.destination_type = "storage"
    w.p.destination_id = w.ad.id
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    posted(w, e1a, w.ad, w.x, 5)
    stock(w, w.ad, w.x, 5, Decimal("26.00"))
    assert call_reverse_item(w, e1a, w.l1) is True
    row = one(rows_for_source(db, w.w1.id, "po_receive_event_item_reversal", e1a.id))
    assert_cols(row, factory_id=w.ad.id, quantity=5, qty_after=0)
    assert reread_stock(db, w.ad, w.x).qty == 0


@pytest.mark.xfail(strict=True, reason=BUG_680)
def test_pri_re_17__race_duplicate_reversal(db, w):
    """PRI-RE-17 -- a concurrent duplicate reversal raises IntegrityError (DB index); none today.
    Rules: _reverse_event_item_posting R1a [BUG-680]."""
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    posted(w, e1a, w.a, w.x, 5)
    reversed_(w, e1a, w.a, w.x)
    stock(w, w.a, w.x, 10, Decimal("22.00"))
    p1, p2 = race_simulation("po_receive_event_item_reversal")
    with p1, p2:
        with pytest.raises(IntegrityError):
            with db.begin_nested():
                call_reverse_item(w, e1a, w.l1)
    rows = rows_for_source(db, w.w1.id, "po_receive_event_item_reversal", e1a.id)
    assert len(rows) == 1
    assert reread_stock(db, w.a, w.x).qty == 10


@pytest.mark.xfail(strict=True, reason=BUG_683)
def test_pri_re_18__reversal_uses_original_storage_location(db, w):
    """PRI-RE-18 -- the reversal happens at the ORIGINAL factory, not the PO's current destination.
    Rules: _reverse_event_item_posting R9 [BUG-683]."""
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    posted(w, e1a, w.a, w.x, 5)
    stock(w, w.a, w.x, 15, Decimal("22.00"))
    stock(w, w.b, w.x, 20, Decimal("30.00"))
    w.p.destination_type = "storage"
    w.p.destination_id = w.b.id
    assert call_reverse_item(w, e1a, w.l1) is True
    row = one(rows_for_source(db, w.w1.id, "po_receive_event_item_reversal", e1a.id))
    assert_cols(row, factory_id=w.a.id, quantity=5, qty_before=15, qty_after=10)
    assert reread_stock(db, w.a, w.x).qty == 10
    bx = reread_stock(db, w.b, w.x)
    assert bx.qty == 20
    assert bx.avg_price == Decimal("30.00")


@pytest.mark.xfail(strict=True, reason=BUG_683)
def test_pri_re_19__reversal_uses_original_location_even_if_now_machine(db, w):
    """PRI-RE-19 -- the reversal happens at the original FACTORY even though the PO now points at a machine.
    Rules: _reverse_event_item_posting R9 [BUG-683]."""
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    posted(w, e1a, w.a, w.x, 5)
    stock(w, w.a, w.x, 15, Decimal("22.00"))
    mstock(w, w.m1, w.x, 20, Decimal("30.00"))
    w.p.destination_type = "machine"
    w.p.destination_id = w.m1.id
    assert call_reverse_item(w, e1a, w.l1) is True
    rows = rows_for_source(db, w.w1.id, "po_receive_event_item_reversal", e1a.id)
    row = one(rows)
    assert row.factory_id == w.a.id
    assert row.quantity == 5
    assert reread_stock(db, w.a, w.x).qty == 10
    assert rows_for_source(db, w.w1.id, "po_receive_event_item_reversal", e1a.id, model=MachineItemLedger) == []
    assert reread_mstock(db, w.m1, w.x).qty == 20
    assert new_activity(db, w.m1, 0) == []


@pytest.mark.xfail(strict=True, reason=BUG_683)
def test_pri_re_20__project_destination_still_reverses_at_recorded_location(db, w):
    """PRI-RE-20 -- the PO's current destination (now project) no longer blocks the reversal.
    Rules: _reverse_event_item_posting R3, R9 [BUG-683]."""
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    posted(w, e1a, w.a, w.x, 5)
    stock(w, w.a, w.x, 15, Decimal("22.00"))
    w.p.destination_type = "project"
    w.p.destination_id = 77
    assert call_reverse_item(w, e1a, w.l1) is True
    row = one(rows_for_source(db, w.w1.id, "po_receive_event_item_reversal", e1a.id))
    assert row.factory_id == w.a.id
    assert row.quantity == 5
    assert reread_stock(db, w.a, w.x).qty == 10


def test_pri_re_21__smallest_posted_delta_reverses_stock_out_one(db, w):
    """PRI-RE-21 -- reversing a posted +1 (smallest positive, other side of the
    delta==0 boundary) still stocks out, 1 unit.
    Rules: _reverse_event_item_posting R4, R6 (smallest posted +1)."""
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("1"))
    posted(w, e1a, w.a, w.x, 1)
    stock(w, w.a, w.x, 11, Decimal("20.00"))
    assert call_reverse_item(w, e1a, w.l1) is True
    row = one(rows_for_source(db, w.w1.id, "po_receive_event_item_reversal", e1a.id))
    assert_cols(
        row, factory_id=w.a.id, item_id=w.x.id, transaction_type="inventory_adjustment",
        quantity=1, unit_cost=Decimal("20.00"), total_cost=Decimal("20.00"),
        qty_before=11, qty_after=10, avg_price_before=Decimal("20.00"), avg_price_after=Decimal("20.00"),
        source_type="po_receive_event_item_reversal", source_id=e1a.id,
        notes=f"PO PO-2026-004 voided — reverse receive event #{e1a.id} line 1",
        performed_by=w.u1.id,
    )
    inv = reread_stock(db, w.a, w.x)
    assert inv.qty == 10
    assert inv.avg_price == Decimal("20.00")
    assert inv.updated_by == w.u1.id


def test_pri_re_22__smallest_posted_delta_reverses_stock_in_one(db, w):
    """PRI-RE-22 -- reversing a posted -1 (smallest negative, other side of the
    delta==0 boundary) still stocks in, 1 unit.
    Rules: _reverse_event_item_posting R4, R7 (smallest posted -1)."""
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("-1"))
    posted(w, e1a, w.a, w.x, 1)
    stock(w, w.a, w.x, 9, Decimal("20.00"))
    assert call_reverse_item(w, e1a, w.l1) is True
    row = one(rows_for_source(db, w.w1.id, "po_receive_event_item_reversal", e1a.id))
    assert_cols(
        row, factory_id=w.a.id, item_id=w.x.id, transaction_type="inventory_adjustment",
        quantity=1, unit_cost=Decimal("26.00"), total_cost=Decimal("26.00"),
        qty_before=9, qty_after=10, avg_price_before=Decimal("20.00"), avg_price_after=Decimal("20.60"),
        source_type="po_receive_event_item_reversal", source_id=e1a.id, performed_by=w.u1.id,
    )
    inv = reread_stock(db, w.a, w.x)
    assert inv.qty == 10
    assert inv.avg_price == Decimal("20.60")
    assert inv.updated_by == w.u1.id


# =========================================================================== #
# _reverse_legacy_line_posting (15 cases)
# =========================================================================== #

def test_pri_rl_01__storage_legacy_reversal(db, w):
    """PRI-RL-01 -- a storage legacy posting is reversed with the legacy row's own quantity.
    Rules: _reverse_legacy_line_posting R4, R5."""
    legacy(w, w.l1, w.a, w.x, 4)
    stock(w, w.a, w.x, 10, Decimal("20.00"))
    assert call_reverse_legacy(w, w.l1) is True
    row = one(rows_for_source(db, w.w1.id, "purchase_order_reversal", w.l1.id))
    assert_cols(
        row, inventory_type=InventoryTypeEnum.STORAGE, factory_id=w.a.id, item_id=w.x.id,
        transaction_type="inventory_adjustment", quantity=4, unit_cost=Decimal("20.00"), total_cost=Decimal("80.00"),
        qty_before=10, qty_after=6, avg_price_before=Decimal("20.00"), avg_price_after=Decimal("20.00"),
        source_type="purchase_order_reversal", source_id=w.l1.id,
        notes="PO PO-2026-004 voided — reverse legacy posting for line 1", performed_by=w.u1.id,
    )
    inv = reread_stock(db, w.a, w.x)
    assert inv.qty == 6
    assert inv.updated_by == w.u1.id


def test_pri_rl_02__machine_legacy_reversal(db, w):
    """PRI-RL-02 -- a machine legacy posting is reversed and logs an activity event.
    Rules: _reverse_legacy_line_posting R4, R5."""
    w.p.destination_type = "machine"
    w.p.destination_id = w.m1.id
    legacy(w, w.l1, w.m1, w.x, 7)
    mstock(w, w.m1, w.x, 10, Decimal("20.00"))
    before_activity = max_id(db, MachineActivityEvent)
    assert call_reverse_legacy(w, w.l1) is True
    row = one(rows_for_source(db, w.w1.id, "purchase_order_reversal", w.l1.id, model=MachineItemLedger))
    assert_cols(
        row, machine_id=w.m1.id, quantity=7, unit_cost=Decimal("20.00"), total_cost=Decimal("140.00"),
        qty_before=10, qty_after=3, value_before=Decimal("200.00"), value_after=Decimal("60.00"),
        source_type="purchase_order_reversal", source_id=w.l1.id,
        notes="PO PO-2026-004 voided — reverse legacy posting for line 1",
    )
    assert reread_mstock(db, w.m1, w.x).qty == 3
    ev = one(new_activity(db, w.m1, before_activity))
    assert ev.event_type == "purchase_reversed"
    assert ev.description == "PO PO-2026-004 voided — 7 units of Hex Bolt removed"
    assert ev.performed_by == w.u1.id


def test_pri_rl_03__factory_row_preferred_over_machine(db, w):
    """PRI-RL-03 -- when both a legacy factory row and a legacy machine row exist, the factory one is used.
    Rules: _reverse_legacy_line_posting R4 (factory row preferred)."""
    legacy(w, w.l1, w.a, w.x, 4)
    legacy(w, w.l1, w.m1, w.x, 7)
    stock(w, w.a, w.x, 10, Decimal("20.00"))
    mstock(w, w.m1, w.x, 10, Decimal("20.00"))
    assert call_reverse_legacy(w, w.l1) is True
    assert rows_for_source(db, w.w1.id, "purchase_order_reversal", w.l1.id, model=MachineItemLedger) == []
    row = one(rows_for_source(db, w.w1.id, "purchase_order_reversal", w.l1.id))
    assert row.quantity == 4
    assert reread_stock(db, w.a, w.x).qty == 6
    assert reread_mstock(db, w.m1, w.x).qty == 10


def test_pri_rl_04__several_legacy_rows_one_used(db, w):
    """PRI-RL-04 -- several legacy rows in the same ledger: exactly one reversal is written.
    Rules: _reverse_legacy_line_posting R4 (no defined order)."""
    legacy(w, w.l1, w.a, w.x, 3)
    legacy(w, w.l1, w.a, w.x, 3)
    stock(w, w.a, w.x, 10, Decimal("20.00"))
    assert call_reverse_legacy(w, w.l1) is True
    row = one(rows_for_source(db, w.w1.id, "purchase_order_reversal", w.l1.id))
    assert row.quantity == 3
    assert reread_stock(db, w.a, w.x).qty == 7


def test_pri_rl_05__already_reversed_returns_false(db, w):
    """PRI-RL-05 -- a legacy posting already reversed writes nothing.
    Rules: _reverse_legacy_line_posting R1."""
    legacy(w, w.l1, w.a, w.x, 4)
    legacy_reversed(w, w.l1, w.a, w.x)
    stock(w, w.a, w.x, 6, Decimal("20.00"))
    before = snapshot_ids(db)
    assert call_reverse_legacy(w, w.l1) is False
    assert_nothing_written(db, before)


def test_pri_rl_06a__already_reversed_in_machine_ledger_blocks(db, w):
    """PRI-RL-06a -- a legacy reversal row in the OTHER ledger (machine) still blocks.
    Rules: _reverse_legacy_line_posting R1 (either ledger)."""
    legacy(w, w.l1, w.a, w.x, 4)
    legacy_reversed(w, w.l1, w.m1, w.x)
    stock(w, w.a, w.x, 10, Decimal("20.00"))
    before = snapshot_ids(db)
    assert call_reverse_legacy(w, w.l1) is False
    assert_nothing_written(db, before)


def test_pri_rl_06b__reversal_only_in_other_workspace_does_not_block(db, w):
    """PRI-RL-06b -- a legacy reversal row only in another workspace does not block this one.
    Rules: _reverse_legacy_line_posting R1 (other workspace)."""
    legacy(w, w.l1, w.a, w.x, 4)
    _seed_ledger(w, w.f2, w.z2, source_type="purchase_order_reversal", source_id=w.l1.id, qty=1, ws_id=w.w2.id)
    stock(w, w.a, w.x, 10, Decimal("20.00"))
    assert call_reverse_legacy(w, w.l1) is True
    assert len(rows_for_source(db, w.w1.id, "purchase_order_reversal", w.l1.id)) == 1
    assert reread_stock(db, w.a, w.x).qty == 6


def test_pri_rl_07__no_legacy_posting_returns_false(db, w):
    """PRI-RL-07 -- with no legacy posting at all, nothing is written.
    Rules: _reverse_legacy_line_posting R2."""
    stock(w, w.a, w.x, 10, Decimal("20.00"))
    before = snapshot_ids(db)
    assert call_reverse_legacy(w, w.l1) is False
    assert_nothing_written(db, before)


def test_pri_rl_08__legacy_posting_only_in_other_workspace_returns_false(db, w):
    """PRI-RL-08 -- a legacy posting row only in another workspace means "no posting" here.
    Rules: _reverse_legacy_line_posting R2 (other workspace)."""
    _seed_ledger(w, w.f2, w.z2, source_type="purchase_order", source_id=w.l1.id, qty=1, ws_id=w.w2.id)
    stock(w, w.a, w.x, 10, Decimal("20.00"))
    before = snapshot_ids(db)
    assert call_reverse_legacy(w, w.l1) is False
    assert_nothing_written(db, before)


def test_pri_rl_09__zero_quantity_legacy_row_still_reverses(db, w):
    """PRI-RL-09 -- a legacy row with quantity 0 still writes a (no-op) reversal row and returns True.
    Rules: _reverse_legacy_line_posting R6."""
    legacy(w, w.l1, w.a, w.x, 0)
    stock(w, w.a, w.x, 10, Decimal("20.00"))
    assert call_reverse_legacy(w, w.l1) is True
    row = one(rows_for_source(db, w.w1.id, "purchase_order_reversal", w.l1.id))
    assert_cols(row, quantity=0, qty_before=10, qty_after=10)
    assert reread_stock(db, w.a, w.x).qty == 10


def test_pri_rl_10__insufficient_stock_400(db, w):
    """PRI-RL-10 -- reversing a legacy posting into insufficient stock raises 400 (Q2: intended).
    Rules: _reverse_legacy_line_posting R7 (Q2)."""
    legacy(w, w.l1, w.a, w.x, 4)
    stock(w, w.a, w.x, 3, Decimal("20.00"))
    before = snapshot_ids(db)
    with pytest.raises(HTTPException) as exc:
        call_reverse_legacy(w, w.l1)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Insufficient stock (3 available, 4 requested)"
    assert_nothing_written(db, before)
    assert reread_stock(db, w.a, w.x).qty == 3


def test_pri_rl_11__unit_price_not_used(db, w):
    """PRI-RL-11 -- a NULL po_line unit price does not raise; the legacy row's own cost is used.
    Rules: _reverse_legacy_line_posting R8 (unit price not used)."""
    w.l1.unit_price = None
    legacy(w, w.l1, w.a, w.x, 4)
    stock(w, w.a, w.x, 10, Decimal("20.00"))
    assert call_reverse_legacy(w, w.l1) is True
    row = one(rows_for_source(db, w.w1.id, "purchase_order_reversal", w.l1.id))
    assert row.quantity == 4
    assert row.unit_cost == Decimal("20.00")
    assert reread_stock(db, w.a, w.x).qty == 6


def test_pri_rl_12a__legacy_factory_other_workspace_404(db, w):
    """PRI-RL-12a -- the legacy row's recorded factory belongs to another workspace: 404.
    Rules: _reverse_legacy_line_posting R8 (via P R12: 404)."""
    w.p.destination_type = "storage"
    w.p.destination_id = w.f2.id
    row = InventoryLedger(
        workspace_id=w.w1.id, inventory_type=InventoryTypeEnum.STORAGE, factory_id=w.f2.id, item_id=w.x.id,
        transaction_type="test_fixture", quantity=4, unit_cost=Decimal("0"), qty_before=0, qty_after=4,
        source_type="purchase_order", source_id=w.l1.id, performed_at=T0,
    )
    db.add(row)
    db.flush()
    before = snapshot_ids(db)
    with pytest.raises(HTTPException) as exc:
        call_reverse_legacy(w, w.l1)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Factory with ID {w.f2.id} not found"
    assert_nothing_written(db, before)


def test_pri_rl_12b__legacy_reversal_at_deleted_factory_still_works(db, w):
    """PRI-RL-12b -- a legacy reversal can still work at a since soft-deleted factory.
    Rules: _reverse_legacy_line_posting R8 (deleted location still reversible)."""
    w.p.destination_type = "storage"
    w.p.destination_id = w.ad.id
    legacy(w, w.l1, w.ad, w.x, 4)
    stock(w, w.ad, w.x, 10, Decimal("20.00"))
    assert call_reverse_legacy(w, w.l1) is True
    assert reread_stock(db, w.ad, w.x).qty == 6


@pytest.mark.xfail(strict=True, reason=BUG_683)
def test_pri_rl_13__reversal_uses_legacy_rows_recorded_location(db, w):
    """PRI-RL-13 -- the reversal happens at the legacy row's recorded factory, not the PO's current destination.
    Rules: _reverse_legacy_line_posting R8 [BUG-683]."""
    legacy(w, w.l1, w.a, w.x, 4)
    stock(w, w.a, w.x, 10, Decimal("20.00"))
    stock(w, w.b, w.x, 20, Decimal("30.00"))
    w.p.destination_type = "storage"
    w.p.destination_id = w.b.id
    assert call_reverse_legacy(w, w.l1) is True
    row = one(rows_for_source(db, w.w1.id, "purchase_order_reversal", w.l1.id))
    assert row.factory_id == w.a.id
    assert row.quantity == 4
    assert reread_stock(db, w.a, w.x).qty == 6
    assert reread_stock(db, w.b, w.x).qty == 20


@pytest.mark.xfail(strict=True, reason=BUG_680)
def test_pri_rl_14__race_duplicate_legacy_reversal(db, w):
    """PRI-RL-14 -- a concurrent duplicate legacy reversal raises IntegrityError (DB index); none today.
    Rules: _reverse_legacy_line_posting R1a [BUG-680]."""
    legacy(w, w.l1, w.a, w.x, 4)
    legacy_reversed(w, w.l1, w.a, w.x)
    stock(w, w.a, w.x, 6, Decimal("20.00"))
    p1, p2 = race_simulation("purchase_order_reversal")
    with p1, p2:
        with pytest.raises(IntegrityError):
            with db.begin_nested():
                call_reverse_legacy(w, w.l1)
    rows = rows_for_source(db, w.w1.id, "purchase_order_reversal", w.l1.id)
    assert len(rows) == 1
    assert reread_stock(db, w.a, w.x).qty == 6


@pytest.mark.xfail(strict=True, reason=BUG_683)
def test_pri_rl_15__project_destination_still_reverses_legacy_at_recorded_location(db, w):
    """PRI-RL-15 -- the PO's current destination (now project) no longer blocks the legacy reversal.
    Rules: _reverse_legacy_line_posting R3, R8 [BUG-683]."""
    legacy(w, w.l1, w.a, w.x, 4)
    stock(w, w.a, w.x, 10, Decimal("20.00"))
    w.p.destination_type = "project"
    w.p.destination_id = 77
    assert call_reverse_legacy(w, w.l1) is True
    row = one(rows_for_source(db, w.w1.id, "purchase_order_reversal", w.l1.id))
    assert row.factory_id == w.a.id
    assert row.quantity == 4
    assert reread_stock(db, w.a, w.x).qty == 6


# =========================================================================== #
# reverse_po_receive_inventory (18 cases)
# Call: reverse_po_receive_inventory(db, P, po_lines=[L1, L2] unless stated, W1, U1)
# =========================================================================== #

def test_pri_v_01__both_lines_reversed(db, w):
    """PRI-V-01 -- both posted receive lines of the PO are reversed.
    Rules: reverse_po_receive_inventory R1, R4, R5."""
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    e1b = make_event_item(db, e1, w.l2, Decimal("3"))
    posted(w, e1a, w.a, w.x, 5)
    posted(w, e1b, w.a, w.y, 3)
    stock(w, w.a, w.x, 15, Decimal("22.00"))
    stock(w, w.a, w.y, 3, Decimal("4.00"))
    result = call_reverse_po(w, [w.l1, w.l2])
    assert result == 2
    ids = {r.source_id for r in rows_for_source(db, w.w1.id, "po_receive_event_item_reversal", e1a.id)} | \
          {r.source_id for r in rows_for_source(db, w.w1.id, "po_receive_event_item_reversal", e1b.id)}
    assert ids == {e1a.id, e1b.id}
    assert reread_stock(db, w.a, w.x).qty == 10
    assert reread_stock(db, w.a, w.y).qty == 0


def test_pri_v_02__other_po_and_other_workspace_event_ignored(db, w):
    """PRI-V-02 -- another PO's event and this PO's event recorded under another workspace are ignored.
    Rules: reverse_po_receive_inventory R1 (other PO / other workspace ignored)."""
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    posted(w, e1a, w.a, w.x, 5)
    l9 = make_line(db, w.p2, w.x.id, line_number=1, unit_price=Decimal("26.00"))
    e9 = make_event(db, w.p2, T2)
    e9a = make_event_item(db, e9, l9, Decimal("4"))
    posted(w, e9a, w.a, w.x, 4)
    e8 = PoReceiveEvent(workspace_id=w.w2.id, purchase_order_id=w.p.id, event_type="receive", created_at=T2)
    db.add(e8)
    db.flush()
    e8a = make_event_item(db, e8, w.l1, Decimal("2"))
    posted(w, e8a, w.a, w.x, 2)
    stock(w, w.a, w.x, 21, Decimal("22.00"))
    result = call_reverse_po(w, [w.l1])
    assert result == 1
    rows = rows_for_source(db, w.w1.id, "po_receive_event_item_reversal", e1a.id)
    assert len(rows) == 1
    assert rows_for_source(db, w.w1.id, "po_receive_event_item_reversal", e9a.id) == []
    assert rows_for_source(db, w.w1.id, "po_receive_event_item_reversal", e8a.id) == []
    assert reread_stock(db, w.a, w.x).qty == 16


def test_pri_v_03__newest_event_reversed_first(db, w):
    """PRI-V-03 -- the newer correction is restored before the earlier receive is taken out.
    Rules: reverse_po_receive_inventory R2 (newest event first)."""
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    e2 = make_event(db, w.p, T3)
    e2a = make_event_item(db, e2, w.l1, Decimal("-2"))
    posted(w, e1a, w.a, w.x, 5)
    posted(w, e2a, w.a, w.x, 2)
    stock(w, w.a, w.x, 3, Decimal("26.00"))
    result = call_reverse_po(w, [w.l1])
    assert result == 2
    db.expire_all()
    rows = db.execute(
        select(InventoryLedger).where(
            InventoryLedger.workspace_id == w.w1.id,
            InventoryLedger.source_type == "po_receive_event_item_reversal",
        ).order_by(InventoryLedger.id)
    ).scalars().all()
    assert [r.source_id for r in rows] == [e2a.id, e1a.id]
    assert reread_stock(db, w.a, w.x).qty == 0


def test_pri_v_04__same_timestamp_tie_broken_by_id_desc(db, w):
    """PRI-V-04 -- events at the same timestamp are reversed by receive-line id descending.
    Rules: reverse_po_receive_inventory R2 (same timestamp -> receive-line id desc)."""
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    e2 = make_event(db, w.p, T2)
    e2a = make_event_item(db, e2, w.l1, Decimal("-2"))
    assert e2a.id > e1a.id
    posted(w, e1a, w.a, w.x, 5)
    posted(w, e2a, w.a, w.x, 2)
    stock(w, w.a, w.x, 3, Decimal("26.00"))
    result = call_reverse_po(w, [w.l1])
    assert result == 2
    db.expire_all()
    rows = db.execute(
        select(InventoryLedger).where(
            InventoryLedger.workspace_id == w.w1.id,
            InventoryLedger.source_type == "po_receive_event_item_reversal",
        ).order_by(InventoryLedger.id)
    ).scalars().all()
    assert [r.source_id for r in rows] == [e2a.id, e1a.id]
    assert reread_stock(db, w.a, w.x).qty == 0


def test_pri_v_05__line_not_in_po_lines_skipped(db, w):
    """PRI-V-05 -- a receive line whose PO line is not in po_lines is skipped.
    Rules: reverse_po_receive_inventory R3."""
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    e1b = make_event_item(db, e1, w.l2, Decimal("3"))
    posted(w, e1a, w.a, w.x, 5)
    posted(w, e1b, w.a, w.y, 3)
    stock(w, w.a, w.x, 15, Decimal("22.00"))
    stock(w, w.a, w.y, 3, Decimal("4.00"))
    result = call_reverse_po(w, [w.l1])
    assert result == 1
    assert rows_for_source(db, w.w1.id, "po_receive_event_item_reversal", e1b.id) == []
    assert reread_stock(db, w.a, w.y).qty == 3


def test_pri_v_06__event_pass_then_legacy_pass_in_po_lines_order(db, w):
    """PRI-V-06 -- event-item reversals run first, then legacy reversals in po_lines order.
    Rules: reverse_po_receive_inventory R4 (event pass, then legacy pass)."""
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    posted(w, e1a, w.a, w.x, 5)
    legacy(w, w.l1, w.a, w.x, 4)
    legacy(w, w.l2, w.a, w.y, 3)
    stock(w, w.a, w.x, 19, Decimal("20.00"))
    stock(w, w.a, w.y, 3, Decimal("4.00"))
    result = call_reverse_po(w, [w.l2, w.l1])
    assert result == 3
    db.expire_all()
    rows = db.execute(
        select(InventoryLedger).where(InventoryLedger.workspace_id == w.w1.id).order_by(InventoryLedger.id)
    ).scalars().all()
    new_part = [r for r in rows if r.source_type in ("po_receive_event_item_reversal", "purchase_order_reversal")]
    assert [(r.source_type, r.source_id) for r in new_part] == [
        ("po_receive_event_item_reversal", e1a.id),
        ("purchase_order_reversal", w.l2.id),
        ("purchase_order_reversal", w.l1.id),
    ]
    assert reread_stock(db, w.a, w.x).qty == 10
    assert reread_stock(db, w.a, w.y).qty == 0


def test_pri_v_07__nothing_to_reverse_returns_zero(db, w):
    """PRI-V-07 -- a PO with no receive events and no legacy rows returns 0 and writes nothing.
    Rules: reverse_po_receive_inventory R5."""
    stock(w, w.a, w.x, 10, Decimal("20.00"))
    before = snapshot_ids(db)
    result = call_reverse_po(w, [w.l1, w.l2])
    assert result == 0
    assert_nothing_written(db, before)


def test_pri_v_08__second_call_is_a_no_op(db, w):
    """PRI-V-08 -- calling again after a successful void writes nothing and returns 0.
    Rules: reverse_po_receive_inventory R6."""
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    e1b = make_event_item(db, e1, w.l2, Decimal("3"))
    posted(w, e1a, w.a, w.x, 5)
    posted(w, e1b, w.a, w.y, 3)
    stock(w, w.a, w.x, 15, Decimal("22.00"))
    stock(w, w.a, w.y, 3, Decimal("4.00"))
    assert call_reverse_po(w, [w.l1, w.l2]) == 2
    before = snapshot_ids(db)
    result = call_reverse_po(w, [w.l1, w.l2])
    assert result == 0
    assert_nothing_written(db, before)
    assert reread_stock(db, w.a, w.x).qty == 10
    assert reread_stock(db, w.a, w.y).qty == 0


def test_pri_v_09__error_propagates_earlier_reversals_kept(db, w):
    """PRI-V-09 -- the newer line's reversal fails with insufficient stock; the earlier one stays written.
    Rules: reverse_po_receive_inventory R8."""
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l2, Decimal("5"))
    posted(w, e1a, w.a, w.y, 5)
    stock(w, w.a, w.y, 1, Decimal("4.00"))
    e2 = make_event(db, w.p, T3)
    e2a = make_event_item(db, e2, w.l1, Decimal("3"))
    posted(w, e2a, w.a, w.x, 3)
    stock(w, w.a, w.x, 10, Decimal("20.00"))
    with pytest.raises(HTTPException) as exc:
        call_reverse_po(w, [w.l1, w.l2])
    assert exc.value.status_code == 400
    assert exc.value.detail == "Insufficient stock (1 available, 5 requested)"
    assert len(rows_for_source(db, w.w1.id, "po_receive_event_item_reversal", e2a.id)) == 1
    assert reread_stock(db, w.a, w.x).qty == 7
    assert rows_for_source(db, w.w1.id, "po_receive_event_item_reversal", e1a.id) == []


def test_pri_v_10__pending_return_not_netted(db, w):
    """PRI-V-10 -- a pending (not completed) return is not netted; the full quantity is reversed.
    Rules: reverse_po_receive_inventory R7 (pending return is not netted)."""
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("10"))
    posted(w, e1a, w.a, w.x, 10)
    pending_return(w, w.l1, 3)
    stock(w, w.a, w.x, 30, Decimal("20.00"))
    result = call_reverse_po(w, [w.l1])
    assert result == 1
    row = one(rows_for_source(db, w.w1.id, "po_receive_event_item_reversal", e1a.id))
    assert row.quantity == 10
    assert reread_stock(db, w.a, w.x).qty == 20


@pytest.mark.xfail(strict=True, reason=BUG_682)
def test_pri_v_11__return_netted_void_leaves_stock_at_pre_po_level(db, w):
    """PRI-V-11 -- Q1 example A: the void nets out the completed return; stock ends where it started.
    Rules: reverse_po_receive_inventory R7; _reverse_event_item_posting R6a [BUG-682]."""
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("10"))
    posted(w, e1a, w.a, w.x, 10)
    return_(w, w.l1, 3, w.a, w.x)
    stock(w, w.a, w.x, 7, Decimal("20.00"))
    result = call_reverse_po(w, [w.l1])
    assert result == 1
    row = one(rows_for_source(db, w.w1.id, "po_receive_event_item_reversal", e1a.id))
    assert row.quantity == 7
    assert reread_stock(db, w.a, w.x).qty == 0


@pytest.mark.xfail(strict=True, reason=BUG_682)
def test_pri_v_12__return_netted_with_other_stock_present(db, w):
    """PRI-V-12 -- Q1 example B: netting still applies with other units of the same item present.
    Rules: reverse_po_receive_inventory R7; _reverse_event_item_posting R6a [BUG-682]."""
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("10"))
    posted(w, e1a, w.a, w.x, 10)
    return_(w, w.l1, 3, w.a, w.x)
    stock(w, w.a, w.x, 27, Decimal("20.00"))
    result = call_reverse_po(w, [w.l1])
    assert result == 1
    row = one(rows_for_source(db, w.w1.id, "po_receive_event_item_reversal", e1a.id))
    assert row.quantity == 7
    assert reread_stock(db, w.a, w.x).qty == 20


@pytest.mark.xfail(strict=True, reason=BUG_682)
def test_pri_v_13__netting_consumes_newest_event_first(db, w):
    """PRI-V-13 -- the returned quantity is consumed against the newest receive-line reversal first.
    Rules: reverse_po_receive_inventory R7; _reverse_event_item_posting R6a (newest-event-first) [BUG-682]."""
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("6"))
    e2 = make_event(db, w.p, T3)
    e2a = make_event_item(db, e2, w.l1, Decimal("4"))
    posted(w, e1a, w.a, w.x, 6)
    posted(w, e2a, w.a, w.x, 4)
    return_(w, w.l1, 5, w.a, w.x)
    stock(w, w.a, w.x, 25, Decimal("20.00"))
    result = call_reverse_po(w, [w.l1])
    assert result == 1
    assert rows_for_source(db, w.w1.id, "po_receive_event_item_reversal", e2a.id) == []
    row = one(rows_for_source(db, w.w1.id, "po_receive_event_item_reversal", e1a.id))
    assert row.quantity == 5
    assert reread_stock(db, w.a, w.x).qty == 20


@pytest.mark.xfail(strict=True, reason=BUG_682)
def test_pri_v_14__fully_returned_line_nets_to_zero(db, w):
    """PRI-V-14 -- a fully-returned receive line nets to 0 and writes nothing for it.
    Rules: reverse_po_receive_inventory R7 (fully returned) [BUG-682]."""
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("10"))
    posted(w, e1a, w.a, w.x, 10)
    return_(w, w.l1, 10, w.a, w.x)
    stock(w, w.a, w.x, 0, Decimal("20.00"))
    result = call_reverse_po(w, [w.l1])
    assert result == 0
    assert rows_for_source(db, w.w1.id, "po_receive_event_item_reversal", e1a.id) == []
    assert reread_stock(db, w.a, w.x).qty == 0


@pytest.mark.xfail(strict=True, reason=BUG_682)
def test_pri_v_15__netting_is_per_po_line(db, w):
    """PRI-V-15 -- a return on L2 only nets L2's reversal; L1's is unaffected.
    Rules: reverse_po_receive_inventory R7 (netting is per PO line) [BUG-682]."""
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("5"))
    e1b = make_event_item(db, e1, w.l2, Decimal("5"))
    posted(w, e1a, w.a, w.x, 5)
    posted(w, e1b, w.a, w.y, 5)
    return_(w, w.l2, 3, w.a, w.y)
    stock(w, w.a, w.x, 5, Decimal("20.00"))
    stock(w, w.a, w.y, 12, Decimal("4.00"))
    result = call_reverse_po(w, [w.l1, w.l2])
    assert result == 2
    row_a = one(rows_for_source(db, w.w1.id, "po_receive_event_item_reversal", e1a.id))
    assert row_a.quantity == 5
    row_b = one(rows_for_source(db, w.w1.id, "po_receive_event_item_reversal", e1b.id))
    assert row_b.quantity == 2
    assert reread_stock(db, w.a, w.x).qty == 0
    assert reread_stock(db, w.a, w.y).qty == 10


def test_pri_v_16__return_on_another_pos_line_not_netted(db, w):
    """PRI-V-16 -- a completed return on a DIFFERENT PO's line is not netted against this one.
    Rules: reverse_po_receive_inventory R7 (a return on another PO's line is not netted)."""
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("10"))
    posted(w, e1a, w.a, w.x, 10)
    l9 = make_line(db, w.p2, w.x.id, line_number=1, unit_price=Decimal("26.00"))
    return_(w, l9, 3, w.a, w.x)
    stock(w, w.a, w.x, 27, Decimal("20.00"))
    result = call_reverse_po(w, [w.l1])
    assert result == 1
    row = one(rows_for_source(db, w.w1.id, "po_receive_event_item_reversal", e1a.id))
    assert row.quantity == 10
    assert reread_stock(db, w.a, w.x).qty == 17


@pytest.mark.parametrize("variant", [pytest.param("wrong_ledger", id="PRI-V-17a"), pytest.param("wrong_workspace", id="PRI-V-17b")])
def test_pri_v_17__return_in_wrong_ledger_or_workspace_not_netted(db, w, variant):
    """PRI-V-17 -- a return ledger row in the wrong ledger or the wrong workspace is not netted
    (the other side of R6a's "same workspace, same ledger" definition).
    Rules: reverse_po_receive_inventory R7; _reverse_event_item_posting R6a."""
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("10"))
    posted(w, e1a, w.a, w.x, 10)
    stock(w, w.a, w.x, 30, Decimal("20.00"))
    ri = mk_return_item(w, w.l1, 3)
    if variant == "wrong_ledger":
        _seed_ledger(w, w.m1, w.x, source_type="purchase_return_item", source_id=ri.id, qty=3)
    else:
        _seed_ledger(w, w.f2, w.z2, source_type="purchase_return_item", source_id=ri.id, qty=3, ws_id=w.w2.id)
    result = call_reverse_po(w, [w.l1])
    assert result == 1
    row = one(rows_for_source(db, w.w1.id, "po_receive_event_item_reversal", e1a.id))
    assert row.quantity == 10
    assert reread_stock(db, w.a, w.x).qty == 20


@pytest.mark.xfail(strict=True, reason=BUG_682)
def test_pri_v_18__netting_never_negative_over_return(db, w):
    """PRI-V-18 -- "never negative": more was returned than received, so nothing is removed on void.
    Rules: reverse_po_receive_inventory R7 (never negative) [BUG-682]."""
    e1 = make_event(db, w.p, T2)
    e1a = make_event_item(db, e1, w.l1, Decimal("10"))
    posted(w, e1a, w.a, w.x, 10)
    return_(w, w.l1, 12, w.a, w.x)
    stock(w, w.a, w.x, 18, Decimal("20.00"))
    result = call_reverse_po(w, [w.l1])
    assert result == 0
    assert rows_for_source(db, w.w1.id, "po_receive_event_item_reversal", e1a.id) == []
    inv = reread_stock(db, w.a, w.x)
    assert inv.qty == 18
    assert inv.avg_price == Decimal("20.00")


# =========================================================================== #
# Database uniqueness -- BUG-680 (4 cases). No manager call: raw inserts.
# =========================================================================== #

@pytest.mark.xfail(strict=True, reason=BUG_680)
@pytest.mark.parametrize(
    "source_type",
    [
        pytest.param("po_receive_event_item", id="PRI-IDX-01a"),
        pytest.param("po_receive_event_item_reversal", id="PRI-IDX-01b"),
        pytest.param("purchase_order_reversal", id="PRI-IDX-01c"),
    ],
)
def test_pri_idx_01__storage_ledger_unique_index(db, w, source_type):
    """PRI-IDX-01 -- a second inventory_ledger row for the same (workspace, type, source_id) at a
    DIFFERENT factory should be rejected by a partial unique index; none exists today.
    Rules: P R1a, RE R1a, RL R1a [BUG-680]."""
    _seed_ledger(w, w.a, w.x, source_type=source_type, source_id=801, qty=1)
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            _seed_ledger(w, w.b, w.x, source_type=source_type, source_id=801, qty=1)
    rows = rows_for_source(db, w.w1.id, source_type, 801)
    assert len(rows) == 1


@pytest.mark.xfail(strict=True, reason=BUG_680)
@pytest.mark.parametrize(
    "source_type",
    [
        pytest.param("po_receive_event_item", id="PRI-IDX-02a"),
        pytest.param("po_receive_event_item_reversal", id="PRI-IDX-02b"),
        pytest.param("purchase_order_reversal", id="PRI-IDX-02c"),
    ],
)
def test_pri_idx_02__machine_ledger_unique_index(db, w, source_type):
    """PRI-IDX-02 -- the same, on machine_item_ledger, at a DIFFERENT machine.
    Rules: P R1a, RE R1a, RL R1a [BUG-680]."""
    _seed_ledger(w, w.m1, w.x, source_type=source_type, source_id=801, qty=1)
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            _seed_ledger(w, w.m2, w.x, source_type=source_type, source_id=801, qty=1)
    rows = rows_for_source(db, w.w1.id, source_type, 801, model=MachineItemLedger)
    assert len(rows) == 1


def test_pri_idx_03__legacy_source_type_allows_several_rows(db, w):
    """PRI-IDX-03 -- 'purchase_order' (legacy) rows are not covered by the partial index; several are allowed.
    Rules: RL R4 (several legacy rows allowed; index is partial)."""
    _seed_ledger(w, w.a, w.x, source_type="purchase_order", source_id=802, qty=1)
    _seed_ledger(w, w.m1, w.x, source_type="purchase_order", source_id=802, qty=1)
    _seed_ledger(w, w.a, w.x, source_type="purchase_order", source_id=802, qty=1)
    _seed_ledger(w, w.m1, w.x, source_type="purchase_order", source_id=802, qty=1)
    assert len(rows_for_source(db, w.w1.id, "purchase_order", 802)) == 2
    assert len(rows_for_source(db, w.w1.id, "purchase_order", 802, model=MachineItemLedger)) == 2


def test_pri_idx_04__index_scoped_by_workspace(db, w):
    """PRI-IDX-04 -- the (today-nonexistent) index would be scoped per workspace: one row per workspace is fine.
    Rules: R1a (index includes workspace)."""
    _seed_ledger(w, w.a, w.x, source_type="po_receive_event_item", source_id=803, qty=1)
    _seed_ledger(w, w.f2, w.z2, source_type="po_receive_event_item", source_id=803, qty=1, ws_id=w.w2.id)
    assert len(rows_for_source(db, w.w1.id, "po_receive_event_item", 803)) == 1
    assert len(rows_for_source(db, w.w2.id, "po_receive_event_item", 803)) == 1
