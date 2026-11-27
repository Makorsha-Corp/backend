"""Unit tests for app/managers/po_return_inventory.py.

Implements tests/unit/managers/po_return_inventory.cases.md (revision 3), one
test per case. Real Postgres session (`db` fixture). No externals are mocked
(spec: "Externals mocked: none"); `utcnow` is real, so every seeded ledger row
gets an explicit past `performed_at` (the `clock` fixture) and every row the
function itself writes is later than any seed.
"""
# ruff: noqa: DTZ001, DTZ003, FURB157  (prescribed by the cards: naive datetimes, Decimal("...") literals)
import inspect
import itertools
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.managers.po_return_inventory import (
    PO_RETURN_ITEM_SOURCE,
    _location_for_po,
    _machine_ledger_exists,
    _quantity_to_int,
    _storage_ledger_exists,
    post_purchase_return_inventory,
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
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.purchase_order_return import (
    PurchaseOrderReturn,
    PurchaseOrderReturnItem,
)
from app.models.status import Status
from app.utils.item_name_normalize import normalize_item_name
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> fixtures / helpers
# --------------------------------------------------------------------------- #

SUFFIX = "has a fractional quantity; inventory requires whole units"

BUG_802 = "BUG-802: the fractional-quantity error names the PO item's internal id, not the line number"
BUG_803 = "BUG-803: ambiguous-latest-row tie-break when 3+ same-item lines share one performed_at in one call"

_seq = itertools.count(1)


def _n() -> int:
    return next(_seq)


# Convention "W1, W2 = two workspaces". "U1 = creates setup rows, U2 = user_id"
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db):
    return make_workspace(db)


@pytest.fixture
def u1(db):
    return make_profile(db)


@pytest.fixture
def u2(db):
    return make_profile(db)


# Convention "F1, F1d, F2"
def mk_factory(db, ws, *, deleted=False):
    n = _n()
    row = Factory(
        workspace_id=ws.id, name=f"Factory {n}", abbreviation=f"F{n}",
        is_active=not deleted, is_deleted=deleted,
    )
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def f1(db, w1):
    return mk_factory(db, w1)


@pytest.fixture
def f1d(db, w1):
    return mk_factory(db, w1, deleted=True)


@pytest.fixture
def f2(db, w2):
    return mk_factory(db, w2)


# Convention "M1, M3, M1d, M2"
def mk_machine(db, ws, factory, *, deleted=False):
    n = _n()
    row = Machine(
        workspace_id=ws.id, name=f"Machine {n}", factory_id=factory.id,
        is_active=not deleted, is_deleted=deleted,
    )
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def m1(db, w1, f1):
    return mk_machine(db, w1, f1)


@pytest.fixture
def m3(db, w1, f1):
    return mk_machine(db, w1, f1)


@pytest.fixture
def m1d(db, w1, f1):
    return mk_machine(db, w1, f1, deleted=True)


@pytest.fixture
def m2(db, w2, f2):
    return mk_machine(db, w2, f2)


# Convention "I1 = Steel Bolt M8, I2 = Hex Nut M8 (W1); IX = Foreign Washer (W2)"
def mk_item(db, ws, name):
    row = Item(workspace_id=ws.id, name=name, name_normalized=normalize_item_name(name), unit="pcs")
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def i1(db, w1):
    return mk_item(db, w1, "Steel Bolt M8")


@pytest.fixture
def i2(db, w1):
    return mk_item(db, w1, "Hex Nut M8")


@pytest.fixture
def ix(db, w2):
    return mk_item(db, w2, "Foreign Washer")


# Convention "PO: a purchase order in W1, po_number 'PO-0012'; destination per case"
def mk_status(db, ws):
    row = Status(workspace_id=ws.id, name="Open", comment="")
    db.add(row)
    db.flush()
    return row


def mk_po(db, ws, user, *, dest_type, dest_id):
    status = mk_status(db, ws)
    row = PurchaseOrder(
        workspace_id=ws.id, po_number="PO-0012", destination_type=dest_type,
        destination_id=dest_id, current_status_id=status.id, created_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def po_(db, w1, u1):
    def _po(dest_type, dest_id):
        return mk_po(db, w1, u1, dest_type=dest_type, dest_id=dest_id)
    return _po


# Convention "PL1, PL2, PL3: lines 1/2/3 of PO, item I1/I1/I2 unless stated"
def mk_line(db, po, item, *, line_number):
    row = PurchaseOrderItem(
        workspace_id=po.workspace_id, purchase_order_id=po.id, line_number=line_number,
        item_id=item.id, quantity_ordered=Decimal("1000"), unit_price=Decimal("10.00"),
    )
    db.add(row)
    db.flush()
    return row


# Convention "R: a return of PO. RI1/RI2/RI3: return items, item_id = paired
# line's item unless stated"
def mk_return(db, ws, po, user):
    row = PurchaseOrderReturn(
        workspace_id=ws.id, purchase_order_id=po.id, return_number=f"PR-{_n()}", created_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def mk_ri(db, ws, ret, po_line, qty, *, item=None):
    row = PurchaseOrderReturnItem(
        workspace_id=ws.id, return_id=ret.id, po_item_id=po_line.id,
        item_id=(item.id if item is not None else po_line.item_id),
        quantity_returned=qty,
    )
    db.add(row)
    db.flush()
    return row


# Convention "Timestamps (G2): T0 = now - 1 day. Seeded rows are T0, T0+1min,
# T0+2min, ... in the listed order unless the case gives another time."
@pytest.fixture
def clock():
    base = datetime.utcnow() - timedelta(days=1)
    counter = itertools.count()

    def _next():
        return base + timedelta(minutes=next(counter))

    return _next


def mk_inventory_row(db, ws, factory, item, inv_type, qty, avg, *, by, deleted=False):
    row = Inventory(
        workspace_id=ws.id, factory_id=factory.id, item_id=item.id, inventory_type=inv_type,
        qty=qty, avg_price=avg, is_active=not deleted, is_deleted=deleted,
        created_by=by.id, updated_by=by.id,
    )
    db.add(row)
    db.flush()
    return row


def inv_ledger_row(
    db, ws, *, inv_type, factory, item, source_type, source_id, qty, qty_before, qty_after,
    avg_before, avg_after, performed_at, transaction_type="purchase_order", performed_by=None,
):
    unit_cost = avg_before
    row = InventoryLedger(
        workspace_id=ws.id, inventory_type=inv_type, factory_id=factory.id, item_id=item.id,
        transaction_type=transaction_type, quantity=qty, unit_cost=unit_cost,
        total_cost=(unit_cost * qty).quantize(Decimal("0.01")) if unit_cost is not None else None,
        qty_before=qty_before, qty_after=qty_after, avg_price_before=avg_before, avg_price_after=avg_after,
        source_type=source_type, source_id=source_id, performed_by=performed_by, performed_at=performed_at,
    )
    db.add(row)
    db.flush()
    return row


# Convention "S(F, I) = n @ p": a storage stock row plus one "opening" storage-
# ledger row (G1: source_type 'test_seed', source_id 1, qty_before 0, qty_after
# n, avg_price_after p) — required so the function's R8a re-sync finds n @ p.
def S(db, ws, factory, item, qty, avg, *, by, clock):
    row = mk_inventory_row(db, ws, factory, item, InventoryTypeEnum.STORAGE, qty, avg, by=by)
    inv_ledger_row(
        db, ws, inv_type=InventoryTypeEnum.STORAGE, factory=factory, item=item,
        source_type="test_seed", source_id=1, qty=qty, qty_before=0, qty_after=qty,
        avg_before=None, avg_after=avg, performed_at=clock(),
    )
    return row


# Convention "D(F, I) = n": a damaged-type stock row, seeded the same way.
def D(db, ws, factory, item, qty, *, by, clock, avg=None):
    row = mk_inventory_row(db, ws, factory, item, InventoryTypeEnum.DAMAGED, qty, avg, by=by)
    inv_ledger_row(
        db, ws, inv_type=InventoryTypeEnum.DAMAGED, factory=factory, item=item,
        source_type="test_seed", source_id=1, qty=qty, qty_before=0, qty_after=qty,
        avg_before=None, avg_after=avg, performed_at=clock(),
    )
    return row


# Convention "MH(M, I) = n": the machine placement (on-hand quantity).
def MH(db, ws, machine, item, qty):
    row = MachineItem(workspace_id=ws.id, machine_id=machine.id, item_id=item.id, qty=qty)
    db.add(row)
    db.flush()
    return row


# Convention "ML(M, I, avg=p)": a pre-existing machine-ledger row.
def ML(db, ws, machine, item, avg, *, by, clock, performed_at=None):
    pa = performed_at if performed_at is not None else clock()
    unit_cost = avg if avg is not None else Decimal("0.00")
    row = MachineItemLedger(
        workspace_id=ws.id, machine_id=machine.id, item_id=item.id, transaction_type="test_seed",
        quantity=0, unit_cost=unit_cost, total_cost=Decimal("0.00"),
        qty_before=0, qty_after=0, value_before=Decimal("0.00"), value_after=Decimal("0.00"),
        avg_price_before=None, avg_price_after=avg, source_type="test_seed", source_id=1,
        performed_by=by.id, performed_at=pa,
    )
    db.add(row)
    db.flush()
    return row


# Convention "Posted-row(ledger, RIk)": a pre-existing ledger row for a return
# item, source_type 'purchase_return_item', source_id RIk.id.
def posted_storage(db, ws, factory, item, ri, qty, *, qty_before, qty_after, clock, avg=None):
    return inv_ledger_row(
        db, ws, inv_type=InventoryTypeEnum.STORAGE, factory=factory, item=item,
        source_type=PO_RETURN_ITEM_SOURCE, source_id=ri.id, qty=qty, qty_before=qty_before,
        qty_after=qty_after, avg_before=avg, avg_after=avg, performed_at=clock(),
        transaction_type="purchase_return",
    )


def posted_machine(db, ws, machine, item, ri, *, by, clock, qty=1):
    row = MachineItemLedger(
        workspace_id=ws.id, machine_id=machine.id, item_id=item.id, transaction_type="purchase_return",
        quantity=qty, unit_cost=Decimal("0.00"), total_cost=Decimal("0.00"),
        qty_before=0, qty_after=0, value_before=Decimal("0.00"), value_after=Decimal("0.00"),
        avg_price_before=None, avg_price_after=None, source_type=PO_RETURN_ITEM_SOURCE, source_id=ri.id,
        performed_by=by.id, performed_at=clock(),
    )
    db.add(row)
    db.flush()
    return row


# Raw ledger-row seeders used only by the _machine_ledger_exists /
# _storage_ledger_exists sections (arbitrary source_type/source_id, no stock
# semantics).
def seed_mledger(db, ws, machine, item, *, source_type, source_id, by):
    row = MachineItemLedger(
        workspace_id=ws.id, machine_id=machine.id, item_id=item.id, transaction_type="test_seed",
        quantity=0, unit_cost=Decimal("0.00"), total_cost=Decimal("0.00"),
        qty_before=0, qty_after=0, source_type=source_type, source_id=source_id,
        performed_by=by.id,
    )
    db.add(row)
    db.flush()
    return row


def seed_iledger(db, ws, factory, item, *, inv_type, source_type, source_id):
    return inv_ledger_row(
        db, ws, inv_type=inv_type, factory=factory, item=item,
        source_type=source_type, source_id=source_id, qty=0, qty_before=0, qty_after=0,
        avg_before=None, avg_after=None, performed_at=datetime(2020, 1, 1),
    )


# --- re-reads ---

def reread_inventory_rows(db, ws, factory, item, inv_type=InventoryTypeEnum.STORAGE):
    db.expire_all()
    return db.execute(
        select(Inventory).where(
            Inventory.workspace_id == ws.id, Inventory.factory_id == factory.id,
            Inventory.item_id == item.id, Inventory.inventory_type == inv_type,
        )
    ).scalars().all()


def reread_one_inventory(db, ws, factory, item, inv_type=InventoryTypeEnum.STORAGE):
    rows = reread_inventory_rows(db, ws, factory, item, inv_type)
    assert len(rows) == 1
    return rows[0]


def reread_machine_item(db, ws, machine, item):
    db.expire_all()
    return db.execute(
        select(MachineItem).where(
            MachineItem.workspace_id == ws.id, MachineItem.machine_id == machine.id,
            MachineItem.item_id == item.id,
        )
    ).scalar_one_or_none()


def inv_rows_for(db, ri, *, source_type=PO_RETURN_ITEM_SOURCE, workspace_id=None):
    db.expire_all()
    q = select(InventoryLedger).where(
        InventoryLedger.source_type == source_type, InventoryLedger.source_id == ri.id,
    )
    if workspace_id is not None:
        q = q.where(InventoryLedger.workspace_id == workspace_id)
    return db.scalars(q.order_by(InventoryLedger.id)).all()


def mch_rows_for(db, ri, *, source_type=PO_RETURN_ITEM_SOURCE, workspace_id=None):
    db.expire_all()
    q = select(MachineItemLedger).where(
        MachineItemLedger.source_type == source_type, MachineItemLedger.source_id == ri.id,
    )
    if workspace_id is not None:
        q = q.where(MachineItemLedger.workspace_id == workspace_id)
    return db.scalars(q.order_by(MachineItemLedger.id)).all()


def no_return_rows(db, *ris):
    for ri in ris:
        assert inv_rows_for(db, ri) == []
        assert mch_rows_for(db, ri) == []


def events_since(db, ws, before_id, *, machine=None):
    db.expire_all()
    q = select(MachineActivityEvent).where(
        MachineActivityEvent.workspace_id == ws.id, MachineActivityEvent.id > before_id,
    )
    if machine is not None:
        q = q.where(MachineActivityEvent.machine_id == machine.id)
    return db.scalars(q.order_by(MachineActivityEvent.id)).all()


def max_activity_id(db):
    return db.scalar(select(func.max(MachineActivityEvent.id))) or 0


def check(row, **expected):
    """Assert each named attribute of `row` equals its expected value."""
    for k, v in expected.items():
        got = getattr(row, k)
        assert got == v, f"{k}: expected {v!r}, got {got!r}"


def insuff_storage(avail, qty):
    return f"Insufficient stock ({avail} available, {qty} requested)"


def insuff_machine(avail, qty):
    return f"Insufficient machine stock ({avail} available, {qty} requested)"


def return_notes(po, ret, line_number):
    return f"PO {po.po_number} return {ret.id} (line {line_number})"


# Convention wrapper "qti(q, ident)" (test-side; used only by the
# _quantity_to_int pass cases).
_QTI_PARAMS = inspect.signature(_quantity_to_int).parameters


def qti(q, ident):
    if "line_number" in _QTI_PARAMS:
        return _quantity_to_int(q, line_number=ident)
    return _quantity_to_int(q, po_item_id=ident)


# --------------------------------------------------------------------------- #
# _machine_ledger_exists
# --------------------------------------------------------------------------- #

def test_pri_mle_01__matching_row_true(db, w1, u1, m3, i2):
    """PRI-MLE-01 — a matching machine-ledger row returns True.
    Rules: _machine_ledger_exists R1."""
    seed_mledger(db, w1, m3, i2, source_type=PO_RETURN_ITEM_SOURCE, source_id=501, by=u1)
    assert _machine_ledger_exists(db, workspace_id=w1.id, source_type=PO_RETURN_ITEM_SOURCE, source_id=501) is True


def test_pri_mle_02__different_source_id_false(db, w1, u1, m3, i2):
    """PRI-MLE-02 — a row with a different source_id returns False.
    Rules: _machine_ledger_exists R2."""
    seed_mledger(db, w1, m3, i2, source_type=PO_RETURN_ITEM_SOURCE, source_id=502, by=u1)
    assert _machine_ledger_exists(db, workspace_id=w1.id, source_type=PO_RETURN_ITEM_SOURCE, source_id=501) is False


def test_pri_mle_03__other_workspace_isolated(db, w1, w2, u1, m2, ix):
    """PRI-MLE-03 — a row in another workspace does not count there, but does in its own.
    Rules: _machine_ledger_exists R3."""
    seed_mledger(db, w2, m2, ix, source_type=PO_RETURN_ITEM_SOURCE, source_id=501, by=u1)
    assert _machine_ledger_exists(db, workspace_id=w1.id, source_type=PO_RETURN_ITEM_SOURCE, source_id=501) is False
    assert _machine_ledger_exists(db, workspace_id=w2.id, source_type=PO_RETURN_ITEM_SOURCE, source_id=501) is True


def test_pri_mle_04__different_source_type_false(db, w1, u1, m3, i2):
    """PRI-MLE-04 — a different source_type with the same source_id does not match.
    Rules: _machine_ledger_exists R4."""
    seed_mledger(db, w1, m3, i2, source_type='po_receive_event_item', source_id=501, by=u1)
    assert _machine_ledger_exists(db, workspace_id=w1.id, source_type=PO_RETURN_ITEM_SOURCE, source_id=501) is False
    assert _machine_ledger_exists(db, workspace_id=w1.id, source_type='po_receive_event_item', source_id=501) is True


def test_pri_mle_05__source_type_case_sensitive(db, w1, u1, m3, i2):
    """PRI-MLE-05 — the source_type match is case-sensitive.
    Rules: _machine_ledger_exists R4."""
    seed_mledger(db, w1, m3, i2, source_type=PO_RETURN_ITEM_SOURCE, source_id=501, by=u1)
    assert _machine_ledger_exists(db, workspace_id=w1.id, source_type='Purchase_Return_Item', source_id=501) is False


def test_pri_mle_06__storage_ledger_rows_not_considered(db, w1, u1, f1, i1):
    """PRI-MLE-06 — a matching row in the storage ledger does not satisfy the machine check.
    Rules: _machine_ledger_exists R5."""
    seed_iledger(db, w1, f1, i1, inv_type=InventoryTypeEnum.STORAGE, source_type=PO_RETURN_ITEM_SOURCE, source_id=501)
    assert _machine_ledger_exists(db, workspace_id=w1.id, source_type=PO_RETURN_ITEM_SOURCE, source_id=501) is False


# --------------------------------------------------------------------------- #
# _storage_ledger_exists
# --------------------------------------------------------------------------- #

def test_pri_sle_01__storage_row_true(db, w1, u1, f1, i2):
    """PRI-SLE-01 — a matching storage-type row returns True.
    Rules: _storage_ledger_exists R1."""
    seed_iledger(db, w1, f1, i2, inv_type=InventoryTypeEnum.STORAGE, source_type=PO_RETURN_ITEM_SOURCE, source_id=601)
    assert _storage_ledger_exists(db, workspace_id=w1.id, source_type=PO_RETURN_ITEM_SOURCE, source_id=601) is True


def test_pri_sle_02__damaged_row_also_true(db, w1, u1, f1d, i1):
    """PRI-SLE-02 — a matching damaged-type row also returns True.
    Rules: _storage_ledger_exists R1."""
    seed_iledger(db, w1, f1d, i1, inv_type=InventoryTypeEnum.DAMAGED, source_type=PO_RETURN_ITEM_SOURCE, source_id=601)
    assert _storage_ledger_exists(db, workspace_id=w1.id, source_type=PO_RETURN_ITEM_SOURCE, source_id=601) is True


def test_pri_sle_03__different_source_id_false(db, w1, u1, f1, i1):
    """PRI-SLE-03 — a row with a different source_id returns False.
    Rules: _storage_ledger_exists R2."""
    seed_iledger(db, w1, f1, i1, inv_type=InventoryTypeEnum.STORAGE, source_type=PO_RETURN_ITEM_SOURCE, source_id=602)
    assert _storage_ledger_exists(db, workspace_id=w1.id, source_type=PO_RETURN_ITEM_SOURCE, source_id=601) is False


def test_pri_sle_04__other_workspace_isolated(db, w1, w2, u1, f2, ix):
    """PRI-SLE-04 — a row in another workspace does not count there, but does in its own.
    Rules: _storage_ledger_exists R3."""
    seed_iledger(db, w2, f2, ix, inv_type=InventoryTypeEnum.STORAGE, source_type=PO_RETURN_ITEM_SOURCE, source_id=601)
    assert _storage_ledger_exists(db, workspace_id=w1.id, source_type=PO_RETURN_ITEM_SOURCE, source_id=601) is False
    assert _storage_ledger_exists(db, workspace_id=w2.id, source_type=PO_RETURN_ITEM_SOURCE, source_id=601) is True


def test_pri_sle_05__different_source_type_false(db, w1, u1, f1, i1):
    """PRI-SLE-05 — a different source_type with the same source_id does not match.
    Rules: _storage_ledger_exists R4."""
    seed_iledger(db, w1, f1, i1, inv_type=InventoryTypeEnum.STORAGE, source_type='po_receive_event_item', source_id=601)
    assert _storage_ledger_exists(db, workspace_id=w1.id, source_type=PO_RETURN_ITEM_SOURCE, source_id=601) is False
    assert _storage_ledger_exists(db, workspace_id=w1.id, source_type='po_receive_event_item', source_id=601) is True


def test_pri_sle_06__machine_ledger_rows_not_considered(db, w1, u1, m1, i1):
    """PRI-SLE-06 — a matching row in the machine ledger does not satisfy the storage check.
    Rules: _storage_ledger_exists R5."""
    seed_mledger(db, w1, m1, i1, source_type=PO_RETURN_ITEM_SOURCE, source_id=601, by=u1)
    assert _storage_ledger_exists(db, workspace_id=w1.id, source_type=PO_RETURN_ITEM_SOURCE, source_id=601) is False


# --------------------------------------------------------------------------- #
# _location_for_po
# --------------------------------------------------------------------------- #

def test_pri_loc_01__storage_destination():
    """PRI-LOC-01 — a storage destination maps to ('storage', destination_id).
    Rules: _location_for_po R1."""
    po = PurchaseOrder(destination_type='storage', destination_id=7)
    assert _location_for_po(po) == ('storage', 7)


def test_pri_loc_02__machine_destination():
    """PRI-LOC-02 — a machine destination maps to ('machine', destination_id).
    Rules: _location_for_po R2."""
    po = PurchaseOrder(destination_type='machine', destination_id=7)
    assert _location_for_po(po) == ('machine', 7)


def test_pri_loc_03__other_destinations_return_none():
    """PRI-LOC-03 — 'project' and 'damaged' destinations return None.
    Rules: _location_for_po R3."""
    for dest in ('project', 'damaged'):
        po = PurchaseOrder(destination_type=dest, destination_id=7)
        assert _location_for_po(po) is None


def test_pri_loc_04__case_sensitive_none():
    """PRI-LOC-04 — 'Storage' and 'MACHINE' (wrong case) return None.
    Rules: _location_for_po R3."""
    for dest in ('Storage', 'MACHINE'):
        po = PurchaseOrder(destination_type=dest, destination_id=7)
        assert _location_for_po(po) is None


def test_pri_loc_05__empty_string_none():
    """PRI-LOC-05 — an empty destination_type returns None.
    Rules: _location_for_po R3."""
    po = PurchaseOrder(destination_type='', destination_id=7)
    assert _location_for_po(po) is None


# --------------------------------------------------------------------------- #
# _quantity_to_int
# --------------------------------------------------------------------------- #

def test_pri_qti_01__whole_number_any_scale():
    """PRI-QTI-01 — a whole-number Decimal of any scale becomes an int.
    Rules: _quantity_to_int R1."""
    for q in (Decimal('3'), Decimal('3.00')):
        result = qti(q, 2)
        assert result == 3
        assert type(result) is int


def test_pri_qti_02__zero_returns_zero():
    """PRI-QTI-02 — zero converts without exception.
    Rules: _quantity_to_int R1."""
    result = qti(Decimal('0'), 2)
    assert result == 0
    assert type(result) is int


def test_pri_qti_03__negative_whole_number_no_sign_check():
    """PRI-QTI-03 — a negative whole number converts without exception (no sign check here).
    Rules: _quantity_to_int R1."""
    result = qti(Decimal('-2.00'), 2)
    assert result == -2
    assert type(result) is int


def test_pri_qti_04__fractional_raises_400():
    """PRI-QTI-04 — a fractional quantity raises 400 naming the line, ending in SUFFIX.
    Rules: _quantity_to_int R2, Errors row 1."""
    for q in (Decimal('1.5'), Decimal('0.01'), Decimal('-0.5')):
        with pytest.raises(HTTPException) as exc:
            qti(q, 2)
        assert exc.value.status_code == 400
        assert exc.value.detail.startswith('Return line for PO ')
        assert exc.value.detail.endswith(SUFFIX)


@pytest.mark.xfail(strict=True, reason=BUG_802)
def test_pri_qti_05__names_line_number_not_item_id():
    """PRI-QTI-05 — the error should name the PO line number via `line_number=`, not the item id.
    Rules: _quantity_to_int R2 [BUG-802], Errors row 1."""
    with pytest.raises(HTTPException) as exc:
        _quantity_to_int(Decimal('1.5'), line_number=2)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Return line for PO line 2 has a fractional quantity; inventory requires whole units"


# --------------------------------------------------------------------------- #
# post_purchase_return_inventory
# --------------------------------------------------------------------------- #

def test_pri_p_01__storage_happy_path(db, w1, u1, u2, f1, i1, clock, po_):
    """PRI-P-01 — a storage return deducts stock and writes one full ledger row.
    Rules: post_purchase_return_inventory R8, R8b, R16; _location_for_po R1."""
    po = po_('storage', f1.id)
    S(db, w1, f1, i1, 10, Decimal('12.50'), by=u1, clock=clock)
    D(db, w1, f1, i1, 5, by=u1, clock=clock)
    ret = mk_return(db, w1, po, u1)
    pl2 = mk_line(db, po, i1, line_number=2)
    ri1 = mk_ri(db, w1, ret, pl2, Decimal('3.00'))
    evt0 = max_activity_id(db)

    result = post_purchase_return_inventory(db, po, [(ri1, pl2)], workspace_id=w1.id, user_id=u2.id)

    assert result == 1
    stock = reread_one_inventory(db, w1, f1, i1)
    check(stock, qty=7, avg_price=Decimal('12.50'), updated_by=u2.id)
    damaged = reread_one_inventory(db, w1, f1, i1, InventoryTypeEnum.DAMAGED)
    check(damaged, qty=5)
    # Literal 'purchase_return_item' (not the imported PO_RETURN_ITEM_SOURCE
    # constant), per verify finding #1: proves the function writes this exact
    # source_type rather than merely being self-consistent with the constant.
    rows = inv_rows_for(db, ri1, source_type='purchase_return_item')
    assert len(rows) == 1
    row = rows[0]
    check(
        row, workspace_id=w1.id, factory_id=f1.id, item_id=i1.id,
        inventory_type=InventoryTypeEnum.STORAGE, transaction_type='purchase_return',
        quantity=3, qty_before=10, qty_after=7, unit_cost=Decimal('12.50'),
        total_cost=Decimal('37.50'), avg_price_before=Decimal('12.50'), avg_price_after=Decimal('12.50'),
        transfer_destination_type=None, transfer_destination_id=None, performed_by=u2.id,
        notes=return_notes(po, ret, 2),
    )
    assert mch_rows_for(db, ri1) == []
    assert events_since(db, w1, evt0) == []


def test_pri_p_02__item_comes_from_po_line(db, w1, u1, u2, f1, i1, i2, clock, po_):
    """PRI-P-02 — the deducted item is the PO line's item, not the return item's own item_id.
    Rules: post_purchase_return_inventory R8 (item comes from the PO line)."""
    po = po_('storage', f1.id)
    S(db, w1, f1, i1, 10, Decimal('12.50'), by=u1, clock=clock)
    S(db, w1, f1, i2, 4, Decimal('5.00'), by=u1, clock=clock)
    ret = mk_return(db, w1, po, u1)
    pl2 = mk_line(db, po, i1, line_number=2)
    ri1 = mk_ri(db, w1, ret, pl2, Decimal('3'), item=i2)

    result = post_purchase_return_inventory(db, po, [(ri1, pl2)], workspace_id=w1.id, user_id=u2.id)

    assert result == 1
    assert reread_one_inventory(db, w1, f1, i1).qty == 7
    assert reread_one_inventory(db, w1, f1, i2).qty == 4
    row = inv_rows_for(db, ri1)[0]
    assert row.item_id == i1.id


def test_pri_p_03__null_average_price_gives_zero_cost(db, w1, u1, u2, f1, i1, clock, po_):
    """PRI-P-03 — a stock row with no average price yields unit_cost 0 and null avg before/after.
    Rules: post_purchase_return_inventory R8 (no average price -> 0)."""
    po = po_('storage', f1.id)
    S(db, w1, f1, i1, 10, None, by=u1, clock=clock)
    ret = mk_return(db, w1, po, u1)
    pl2 = mk_line(db, po, i1, line_number=2)
    ri1 = mk_ri(db, w1, ret, pl2, Decimal('3'))

    result = post_purchase_return_inventory(db, po, [(ri1, pl2)], workspace_id=w1.id, user_id=u2.id)

    assert result == 1
    stock = reread_one_inventory(db, w1, f1, i1)
    assert stock.qty == 7
    assert stock.avg_price is None
    row = inv_rows_for(db, ri1)[0]
    check(row, unit_cost=Decimal('0.00'), total_cost=Decimal('0.00'), avg_price_before=None, avg_price_after=None)


def test_pri_p_05__exact_stock_depletes_to_zero(db, w1, u1, u2, f1, i1, clock, po_):
    """PRI-P-05 — returning exactly the available stock is allowed and leaves 0.
    Rules: post_purchase_return_inventory R9 (equal stock allowed)."""
    po = po_('storage', f1.id)
    S(db, w1, f1, i1, 3, Decimal('12.50'), by=u1, clock=clock)
    ret = mk_return(db, w1, po, u1)
    pl2 = mk_line(db, po, i1, line_number=2)
    ri1 = mk_ri(db, w1, ret, pl2, Decimal('3'))

    result = post_purchase_return_inventory(db, po, [(ri1, pl2)], workspace_id=w1.id, user_id=u2.id)

    assert result == 1
    assert reread_one_inventory(db, w1, f1, i1).qty == 0
    row = inv_rows_for(db, ri1)[0]
    check(row, qty_before=3, qty_after=0)


def test_pri_p_06__insufficient_storage_stock_unchanged(db, w1, u1, u2, f1, i1, clock, po_):
    """PRI-P-06 — insufficient storage stock raises 400 and leaves the stock row untouched.
    Rules: post_purchase_return_inventory R9, Errors row 2."""
    po = po_('storage', f1.id)
    S(db, w1, f1, i1, 2, Decimal('12.50'), by=u1, clock=clock)
    ret = mk_return(db, w1, po, u1)
    pl2 = mk_line(db, po, i1, line_number=2)
    ri1 = mk_ri(db, w1, ret, pl2, Decimal('3'))

    with pytest.raises(HTTPException) as exc:
        post_purchase_return_inventory(db, po, [(ri1, pl2)], workspace_id=w1.id, user_id=u2.id)

    assert exc.value.status_code == 400
    assert exc.value.detail == insuff_storage(2, 3)
    stock = reread_one_inventory(db, w1, f1, i1)
    check(stock, qty=2, avg_price=Decimal('12.50'), updated_by=u1.id)
    no_return_rows(db, ri1)


def test_pri_p_07__missing_stock_row_treated_as_zero(db, w1, u1, u2, f1, i1, po_):
    """PRI-P-07 — no stock row (and no ledger) is treated as 0 available; a zero row is created.
    Rules: post_purchase_return_inventory R9 (no stock row), R8a; Errors row 2."""
    po = po_('storage', f1.id)
    ret = mk_return(db, w1, po, u1)
    pl2 = mk_line(db, po, i1, line_number=2)
    ri1 = mk_ri(db, w1, ret, pl2, Decimal('3'))

    with pytest.raises(HTTPException) as exc:
        post_purchase_return_inventory(db, po, [(ri1, pl2)], workspace_id=w1.id, user_id=u2.id)

    assert exc.value.status_code == 400
    assert exc.value.detail == insuff_storage(0, 3)
    no_return_rows(db, ri1)
    stock = reread_one_inventory(db, w1, f1, i1)
    assert stock.qty == 0
    assert stock.avg_price is None


def test_pri_p_08__factory_not_found_404(db, w1, u1, u2, i1, po_):
    """PRI-P-08 — an unknown destination factory id raises 404.
    Rules: post_purchase_return_inventory R10; Errors row 4."""
    po = po_('storage', 999999)
    ret = mk_return(db, w1, po, u1)
    pl2 = mk_line(db, po, i1, line_number=2)
    ri1 = mk_ri(db, w1, ret, pl2, Decimal('3'))

    with pytest.raises(HTTPException) as exc:
        post_purchase_return_inventory(db, po, [(ri1, pl2)], workspace_id=w1.id, user_id=u2.id)

    assert exc.value.status_code == 404
    assert exc.value.detail == "Factory with ID 999999 not found"
    no_return_rows(db, ri1)


def test_pri_p_09__factory_in_other_workspace_404(db, w1, w2, u1, u2, f2, i1, clock, po_):
    """PRI-P-09 — a factory that exists only in another workspace is reported as not found.
    Rules: post_purchase_return_inventory R10; Errors row 4 (isolation)."""
    po = po_('storage', f2.id)
    S(db, w2, f2, i1, 10, Decimal('12.50'), by=u1, clock=clock)
    ret = mk_return(db, w1, po, u1)
    pl2 = mk_line(db, po, i1, line_number=2)
    ri1 = mk_ri(db, w1, ret, pl2, Decimal('3'))

    with pytest.raises(HTTPException) as exc:
        post_purchase_return_inventory(db, po, [(ri1, pl2)], workspace_id=w1.id, user_id=u2.id)

    assert exc.value.status_code == 404
    assert exc.value.detail == f"Factory with ID {f2.id} not found"
    stock = reread_one_inventory(db, w2, f2, i1)
    check(stock, qty=10, avg_price=Decimal('12.50'), updated_by=u1.id)
    no_return_rows(db, ri1)


def test_pri_p_10__soft_deleted_factory_still_found(db, w1, u1, u2, f1d, i1, clock, po_):
    """PRI-P-10 — a soft-deleted destination factory is still found and deducted.
    Rules: post_purchase_return_inventory R10 (soft-deleted factory)."""
    po = po_('storage', f1d.id)
    S(db, w1, f1d, i1, 10, Decimal('12.50'), by=u1, clock=clock)
    ret = mk_return(db, w1, po, u1)
    pl2 = mk_line(db, po, i1, line_number=2)
    ri1 = mk_ri(db, w1, ret, pl2, Decimal('3'))

    result = post_purchase_return_inventory(db, po, [(ri1, pl2)], workspace_id=w1.id, user_id=u2.id)

    assert result == 1
    assert reread_one_inventory(db, w1, f1d, i1).qty == 7
    rows = inv_rows_for(db, ri1)
    assert len(rows) == 1
    assert rows[0].factory_id == f1d.id
    assert rows[0].quantity == 3


def test_pri_p_11__machine_happy_path(db, w1, u1, u2, m1, m3, i1, i2, clock, po_):
    """PRI-P-11 — a machine return deducts on-hand stock, writes a ledger row and an activity event.
    Rules: post_purchase_return_inventory R11, R12, R16; _location_for_po R2."""
    po = po_('machine', m1.id)
    MH(db, w1, m1, i1, 10)
    ML(db, w1, m1, i1, Decimal('9.00'), by=u1, clock=clock)
    ML(db, w1, m1, i1, Decimal('12.50'), by=u1, clock=clock)
    ML(db, w1, m1, i2, Decimal('99.00'), by=u1, clock=clock)
    ML(db, w1, m3, i1, Decimal('77.00'), by=u1, clock=clock)
    ret = mk_return(db, w1, po, u1)
    pl2 = mk_line(db, po, i1, line_number=2)
    ri1 = mk_ri(db, w1, ret, pl2, Decimal('3'))
    evt0 = max_activity_id(db)

    result = post_purchase_return_inventory(db, po, [(ri1, pl2)], workspace_id=w1.id, user_id=u2.id)

    assert result == 1
    assert reread_machine_item(db, w1, m1, i1).qty == 7
    rows = mch_rows_for(db, ri1)
    assert len(rows) == 1
    row = rows[0]
    check(
        row, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id,
        transaction_type='purchase_return', quantity=3, unit_cost=Decimal('12.50'),
        value_before=Decimal('125.00'), value_after=Decimal('87.50'),
        avg_price_before=Decimal('12.50'), avg_price_after=Decimal('12.50'),
        performed_by=u2.id, notes=return_notes(po, ret, 2),
    )
    events = events_since(db, w1, evt0, machine=m1)
    assert len(events) == 1
    evt = events[0]
    check(evt, event_type='purchase_returned',
          description='Purchase returned: 3 units of Steel Bolt M8 to supplier', performed_by=u2.id)
    assert evt.metadata_json == {"item_id": i1.id, "item_name": "Steel Bolt M8", "quantity": 3}
    assert isinstance(evt.metadata_json["item_id"], int)
    assert isinstance(evt.metadata_json["quantity"], int)
    assert "work_order_id" not in evt.metadata_json
    assert inv_rows_for(db, ri1) == []


def test_pri_p_12__no_prior_machine_ledger_zero_cost(db, w1, u1, u2, m1, m3, i1, clock, po_):
    """PRI-P-12 — no prior machine-ledger entry for this machine/item yields zero cost fields.
    Rules: post_purchase_return_inventory R11 (no prior ledger -> 0)."""
    po = po_('machine', m1.id)
    MH(db, w1, m1, i1, 10)
    ML(db, w1, m3, i1, Decimal('77.00'), by=u1, clock=clock)
    ret = mk_return(db, w1, po, u1)
    pl2 = mk_line(db, po, i1, line_number=2)
    ri1 = mk_ri(db, w1, ret, pl2, Decimal('3'))

    result = post_purchase_return_inventory(db, po, [(ri1, pl2)], workspace_id=w1.id, user_id=u2.id)

    assert result == 1
    assert reread_machine_item(db, w1, m1, i1).qty == 7
    row = mch_rows_for(db, ri1)[0]
    check(row, unit_cost=Decimal('0.00'), value_before=Decimal('0.00'), value_after=Decimal('0.00'),
          avg_price_before=Decimal('0.00'), avg_price_after=Decimal('0.00'))


def test_pri_p_13__latest_null_average_zero_cost(db, w1, u1, u2, m1, i1, clock, po_):
    """PRI-P-13 — the latest machine-ledger entry with a null average yields zero cost.
    Rules: post_purchase_return_inventory R11 (latest avg null -> 0)."""
    po = po_('machine', m1.id)
    MH(db, w1, m1, i1, 10)
    ML(db, w1, m1, i1, Decimal('12.50'), by=u1, clock=clock)
    ML(db, w1, m1, i1, None, by=u1, clock=clock)
    ret = mk_return(db, w1, po, u1)
    pl2 = mk_line(db, po, i1, line_number=2)
    ri1 = mk_ri(db, w1, ret, pl2, Decimal('3'))

    result = post_purchase_return_inventory(db, po, [(ri1, pl2)], workspace_id=w1.id, user_id=u2.id)

    assert result == 1
    row = mch_rows_for(db, ri1)[0]
    check(row, unit_cost=Decimal('0.00'), value_before=Decimal('0.00'), value_after=Decimal('0.00'))


def test_pri_p_14__item_not_in_workspace_fallback_name(db, w1, u1, u2, m1, ix, po_):
    """PRI-P-14 — an item not found in this workspace uses the fallback "Item #{id}" name.
    Rules: post_purchase_return_inventory R12 (item not in workspace -> fallback name)."""
    po = po_('machine', m1.id)
    MH(db, w1, m1, ix, 5)
    ret = mk_return(db, w1, po, u1)
    pl2 = mk_line(db, po, ix, line_number=2)
    ri1 = mk_ri(db, w1, ret, pl2, Decimal('2'))
    evt0 = max_activity_id(db)

    result = post_purchase_return_inventory(db, po, [(ri1, pl2)], workspace_id=w1.id, user_id=u2.id)

    assert result == 1
    assert reread_machine_item(db, w1, m1, ix).qty == 3
    evt = events_since(db, w1, evt0, machine=m1)[0]
    assert evt.description == f"Purchase returned: 2 units of Item #{ix.id} to supplier"
    assert evt.metadata_json == {"item_id": ix.id, "item_name": f"Item #{ix.id}", "quantity": 2}


def test_pri_p_15__machine_exact_stock_depletes_to_zero(db, w1, u1, u2, m1, i1, po_):
    """PRI-P-15 — returning exactly the machine's on-hand stock is allowed.
    Rules: post_purchase_return_inventory R13 (equal stock allowed)."""
    po = po_('machine', m1.id)
    MH(db, w1, m1, i1, 3)
    ret = mk_return(db, w1, po, u1)
    pl2 = mk_line(db, po, i1, line_number=2)
    ri1 = mk_ri(db, w1, ret, pl2, Decimal('3'))
    evt0 = max_activity_id(db)

    result = post_purchase_return_inventory(db, po, [(ri1, pl2)], workspace_id=w1.id, user_id=u2.id)

    assert result == 1
    assert reread_machine_item(db, w1, m1, i1).qty == 0
    assert len(mch_rows_for(db, ri1)) == 1
    assert len(events_since(db, w1, evt0, machine=m1)) == 1


def test_pri_p_16__insufficient_machine_stock(db, w1, u1, u2, m1, i1, po_):
    """PRI-P-16 — insufficient machine stock raises 400 and changes nothing.
    Rules: post_purchase_return_inventory R13; Errors row 3."""
    po = po_('machine', m1.id)
    MH(db, w1, m1, i1, 2)
    ret = mk_return(db, w1, po, u1)
    pl2 = mk_line(db, po, i1, line_number=2)
    ri1 = mk_ri(db, w1, ret, pl2, Decimal('3'))
    evt0 = max_activity_id(db)

    with pytest.raises(HTTPException) as exc:
        post_purchase_return_inventory(db, po, [(ri1, pl2)], workspace_id=w1.id, user_id=u2.id)

    assert exc.value.status_code == 400
    assert exc.value.detail == insuff_machine(2, 3)
    assert reread_machine_item(db, w1, m1, i1).qty == 2
    no_return_rows(db, ri1)
    assert events_since(db, w1, evt0, machine=m1) == []


def test_pri_p_17__missing_placement_created_zero(db, w1, u1, u2, m1, i1, po_):
    """PRI-P-17 — no placement is treated as 0 available; a zero placement is created.
    Rules: post_purchase_return_inventory R13 (no placement -> 0 placement created); Errors row 3."""
    po = po_('machine', m1.id)
    ret = mk_return(db, w1, po, u1)
    pl2 = mk_line(db, po, i1, line_number=2)
    ri1 = mk_ri(db, w1, ret, pl2, Decimal('3'))
    evt0 = max_activity_id(db)

    with pytest.raises(HTTPException) as exc:
        post_purchase_return_inventory(db, po, [(ri1, pl2)], workspace_id=w1.id, user_id=u2.id)

    assert exc.value.status_code == 400
    assert exc.value.detail == insuff_machine(0, 3)
    no_return_rows(db, ri1)
    placement = reread_machine_item(db, w1, m1, i1)
    assert placement is not None
    assert placement.qty == 0
    assert events_since(db, w1, evt0, machine=m1) == []


def test_pri_p_18__machine_not_found_404(db, w1, u1, u2, i1, po_):
    """PRI-P-18 — an unknown destination machine id raises 404.
    Rules: post_purchase_return_inventory R14; Errors row 5."""
    po = po_('machine', 999999)
    ret = mk_return(db, w1, po, u1)
    pl2 = mk_line(db, po, i1, line_number=2)
    ri1 = mk_ri(db, w1, ret, pl2, Decimal('3'))
    evt0 = max_activity_id(db)

    with pytest.raises(HTTPException) as exc:
        post_purchase_return_inventory(db, po, [(ri1, pl2)], workspace_id=w1.id, user_id=u2.id)

    assert exc.value.status_code == 404
    assert exc.value.detail == "Machine with ID 999999 not found"
    no_return_rows(db, ri1)
    assert events_since(db, w1, evt0) == []


def test_pri_p_19__machine_in_other_workspace_404(db, w1, w2, u1, u2, m2, i1, po_):
    """PRI-P-19 — a machine that exists only in another workspace is reported as not found.
    Rules: post_purchase_return_inventory R14; Errors row 5 (isolation)."""
    po = po_('machine', m2.id)
    MH(db, w2, m2, i1, 10)
    ret = mk_return(db, w1, po, u1)
    pl2 = mk_line(db, po, i1, line_number=2)
    ri1 = mk_ri(db, w1, ret, pl2, Decimal('3'))
    evt0 = max_activity_id(db)

    with pytest.raises(HTTPException) as exc:
        post_purchase_return_inventory(db, po, [(ri1, pl2)], workspace_id=w1.id, user_id=u2.id)

    assert exc.value.status_code == 404
    assert exc.value.detail == f"Machine with ID {m2.id} not found"
    assert reread_machine_item(db, w2, m2, i1).qty == 10
    no_return_rows(db, ri1)
    assert events_since(db, w2, evt0, machine=m2) == []


def test_pri_p_20__soft_deleted_machine_still_found(db, w1, u1, u2, m1d, i1, po_):
    """PRI-P-20 — a soft-deleted destination machine is still found and deducted.
    Rules: post_purchase_return_inventory R14 (soft-deleted machine)."""
    po = po_('machine', m1d.id)
    MH(db, w1, m1d, i1, 10)
    ret = mk_return(db, w1, po, u1)
    pl2 = mk_line(db, po, i1, line_number=2)
    ri1 = mk_ri(db, w1, ret, pl2, Decimal('3'))
    evt0 = max_activity_id(db)

    result = post_purchase_return_inventory(db, po, [(ri1, pl2)], workspace_id=w1.id, user_id=u2.id)

    assert result == 1
    assert reread_machine_item(db, w1, m1d, i1).qty == 7
    rows = mch_rows_for(db, ri1)
    assert len(rows) == 1
    assert rows[0].machine_id == m1d.id
    events = events_since(db, w1, evt0, machine=m1d)
    assert len(events) == 1
    assert events[0].event_type == 'purchase_returned'


def test_pri_p_21__project_destination_returns_zero(db, w1, u1, u2, f1, i1, i2, clock, po_):
    """PRI-P-21 — a project destination short-circuits to 0, with no checks on any line.
    Rules: post_purchase_return_inventory R1; _location_for_po R3."""
    po = po_('project', f1.id)
    S(db, w1, f1, i1, 10, Decimal('12.50'), by=u1, clock=clock)
    ret = mk_return(db, w1, po, u1)
    pl1 = mk_line(db, po, i1, line_number=1)
    pl2 = mk_line(db, po, i1, line_number=2)
    pl3 = mk_line(db, po, i2, line_number=3)
    ri1 = mk_ri(db, w1, ret, pl1, Decimal('1.50'))
    ri2 = mk_ri(db, w1, ret, pl2, Decimal('3'))
    posted_storage(db, w1, f1, i1, ri2, 3, qty_before=13, qty_after=10, clock=clock, avg=Decimal('12.50'))
    ri3 = mk_ri(db, w1, ret, pl3, Decimal('3'))
    evt0 = max_activity_id(db)

    result = post_purchase_return_inventory(
        db, po, [(ri1, pl1), (ri2, pl2), (ri3, pl3)], workspace_id=w1.id, user_id=u2.id,
    )

    assert result == 0
    stock = reread_one_inventory(db, w1, f1, i1)
    check(stock, qty=10, updated_by=u1.id)
    assert len(inv_rows_for(db, ri2)) == 1
    assert inv_rows_for(db, ri1) == []
    assert inv_rows_for(db, ri3) == []
    assert mch_rows_for(db, ri1) == []
    assert mch_rows_for(db, ri2) == []
    assert mch_rows_for(db, ri3) == []
    assert events_since(db, w1, evt0) == []


def test_pri_p_22__destination_case_variant_returns_zero(db, w1, u1, u2, f1, i1, clock, po_):
    """PRI-P-22 — a wrong-case destination type ('Storage') is not recognized; returns 0.
    Rules: post_purchase_return_inventory R1; _location_for_po R3 (case)."""
    po = po_('Storage', f1.id)
    S(db, w1, f1, i1, 10, Decimal('12.50'), by=u1, clock=clock)
    ret = mk_return(db, w1, po, u1)
    pl2 = mk_line(db, po, i1, line_number=2)
    ri1 = mk_ri(db, w1, ret, pl2, Decimal('3'))

    result = post_purchase_return_inventory(db, po, [(ri1, pl2)], workspace_id=w1.id, user_id=u2.id)

    assert result == 0
    assert reread_one_inventory(db, w1, f1, i1).qty == 10
    no_return_rows(db, ri1)


def test_pri_p_23__empty_pairs_returns_zero(db, w1, u1, u2, f1, i1, clock, po_):
    """PRI-P-23 — an empty return_item_pairs sequence returns 0 and writes nothing.
    Rules: post_purchase_return_inventory R2."""
    po = po_('storage', f1.id)
    S(db, w1, f1, i1, 10, Decimal('12.50'), by=u1, clock=clock)

    result = post_purchase_return_inventory(db, po, [], workspace_id=w1.id, user_id=u2.id)

    assert result == 0
    stock = reread_one_inventory(db, w1, f1, i1)
    check(stock, qty=10, updated_by=u1.id)
    db.expire_all()
    assert db.scalar(
        select(func.count()).select_from(InventoryLedger).where(
            InventoryLedger.workspace_id == w1.id, InventoryLedger.source_type == PO_RETURN_ITEM_SOURCE,
        )
    ) == 0
    assert db.scalar(
        select(func.count()).select_from(MachineItemLedger).where(
            MachineItemLedger.workspace_id == w1.id, MachineItemLedger.source_type == PO_RETURN_ITEM_SOURCE,
        )
    ) == 0


def test_pri_p_24__idempotent_rerun_same_session(db, w1, u1, u2, f1, i1, clock, po_):
    """PRI-P-24 — calling twice with the same pairs posts once; the second call is a no-op.
    Rules: post_purchase_return_inventory R3, R16 (idempotent re-run)."""
    po = po_('storage', f1.id)
    S(db, w1, f1, i1, 10, Decimal('12.50'), by=u1, clock=clock)
    ret = mk_return(db, w1, po, u1)
    pl2 = mk_line(db, po, i1, line_number=2)
    ri1 = mk_ri(db, w1, ret, pl2, Decimal('3'))

    first = post_purchase_return_inventory(db, po, [(ri1, pl2)], workspace_id=w1.id, user_id=u2.id)
    second = post_purchase_return_inventory(db, po, [(ri1, pl2)], workspace_id=w1.id, user_id=u2.id)

    assert first == 1
    assert second == 0
    assert reread_one_inventory(db, w1, f1, i1).qty == 7
    assert len(inv_rows_for(db, ri1)) == 1


def test_pri_p_25__already_posted_detected_via_storage_ledger(db, w1, u1, u2, f1, i1, clock, po_):
    """PRI-P-25 — a return line already posted to the storage ledger is skipped.
    Rules: post_purchase_return_inventory R3."""
    po = po_('storage', f1.id)
    inv_ledger_row(
        db, w1, inv_type=InventoryTypeEnum.STORAGE, factory=f1, item=i1,
        source_type='test_seed', source_id=1, qty=12, qty_before=0, qty_after=12,
        avg_before=None, avg_after=Decimal('12.50'), performed_at=clock(),
    )
    ret = mk_return(db, w1, po, u1)
    pl2 = mk_line(db, po, i1, line_number=2)
    ri1 = mk_ri(db, w1, ret, pl2, Decimal('2'))
    # Seeded directly with the literal 'purchase_return_item' (not via
    # posted_storage(), which reads the module's own PO_RETURN_ITEM_SOURCE
    # constant), per verify finding #1: proves the already-posted check
    # recognizes this exact source_type string, not merely a self-consistent
    # constant value.
    inv_ledger_row(
        db, w1, inv_type=InventoryTypeEnum.STORAGE, factory=f1, item=i1,
        source_type='purchase_return_item', source_id=ri1.id, qty=2, qty_before=12, qty_after=10,
        avg_before=Decimal('12.50'), avg_after=Decimal('12.50'), performed_at=clock(),
        transaction_type='purchase_return',
    )
    mk_inventory_row(db, w1, f1, i1, InventoryTypeEnum.STORAGE, 10, Decimal('12.50'), by=u1)

    result = post_purchase_return_inventory(db, po, [(ri1, pl2)], workspace_id=w1.id, user_id=u2.id)

    assert result == 0
    assert reread_one_inventory(db, w1, f1, i1).qty == 10
    assert len(inv_rows_for(db, ri1, source_type='purchase_return_item')) == 1


def test_pri_p_26__already_posted_via_machine_ledger_blocks_storage(db, w1, u1, u2, f1, m1, i1, clock, po_):
    """PRI-P-26 — a line posted to the machine ledger is still skipped for a storage destination.
    Rules: post_purchase_return_inventory R3 (either ledger, regardless of destination)."""
    po = po_('storage', f1.id)
    S(db, w1, f1, i1, 10, Decimal('12.50'), by=u1, clock=clock)
    ret = mk_return(db, w1, po, u1)
    pl2 = mk_line(db, po, i1, line_number=2)
    ri1 = mk_ri(db, w1, ret, pl2, Decimal('3'))
    posted_machine(db, w1, m1, i1, ri1, by=u1, clock=clock)

    result = post_purchase_return_inventory(db, po, [(ri1, pl2)], workspace_id=w1.id, user_id=u2.id)

    assert result == 0
    assert reread_one_inventory(db, w1, f1, i1).qty == 10
    assert inv_rows_for(db, ri1) == []
    assert len(mch_rows_for(db, ri1)) == 1


def test_pri_p_27__already_posted_via_storage_ledger_blocks_machine(db, w1, u1, u2, f1, m1, i1, clock, po_):
    """PRI-P-27 — a line posted to the storage ledger is still skipped for a machine destination.
    Rules: post_purchase_return_inventory R3 (either ledger, regardless of destination)."""
    po = po_('machine', m1.id)
    MH(db, w1, m1, i1, 10)
    inv_ledger_row(
        db, w1, inv_type=InventoryTypeEnum.STORAGE, factory=f1, item=i1,
        source_type='test_seed', source_id=1, qty=13, qty_before=0, qty_after=13,
        avg_before=None, avg_after=Decimal('12.50'), performed_at=clock(),
    )
    ret = mk_return(db, w1, po, u1)
    pl2 = mk_line(db, po, i1, line_number=2)
    ri1 = mk_ri(db, w1, ret, pl2, Decimal('3'))
    posted_storage(db, w1, f1, i1, ri1, 3, qty_before=13, qty_after=10, clock=clock, avg=Decimal('12.50'))
    evt0 = max_activity_id(db)

    result = post_purchase_return_inventory(db, po, [(ri1, pl2)], workspace_id=w1.id, user_id=u2.id)

    assert result == 0
    assert reread_machine_item(db, w1, m1, i1).qty == 10
    assert mch_rows_for(db, ri1) == []
    assert events_since(db, w1, evt0, machine=m1) == []


def test_pri_p_28__already_posted_fractional_line_skipped_without_error(db, w1, u1, u2, f1, i1, clock, po_):
    """PRI-P-28 — the already-posted check runs before the quantity check; a fractional quantity
    on an already-posted line is skipped silently.
    Rules: post_purchase_return_inventory R4."""
    po = po_('storage', f1.id)
    inv_ledger_row(
        db, w1, inv_type=InventoryTypeEnum.STORAGE, factory=f1, item=i1,
        source_type='test_seed', source_id=1, qty=11, qty_before=0, qty_after=11,
        avg_before=None, avg_after=Decimal('12.50'), performed_at=clock(),
    )
    ret = mk_return(db, w1, po, u1)
    pl2 = mk_line(db, po, i1, line_number=2)
    ri1 = mk_ri(db, w1, ret, pl2, Decimal('1.50'))
    posted_storage(db, w1, f1, i1, ri1, 1, qty_before=11, qty_after=10, clock=clock, avg=Decimal('12.50'))
    mk_inventory_row(db, w1, f1, i1, InventoryTypeEnum.STORAGE, 10, Decimal('12.50'), by=u1)

    result = post_purchase_return_inventory(db, po, [(ri1, pl2)], workspace_id=w1.id, user_id=u2.id)

    assert result == 0
    assert reread_one_inventory(db, w1, f1, i1).qty == 10
    assert len(inv_rows_for(db, ri1)) == 1


def test_pri_p_29__other_workspace_posted_rows_do_not_block(db, w1, w2, u1, u2, f1, f2, m2, i1, clock, po_):
    """PRI-P-29 — a ledger row for the same return-item id in another workspace does not count.
    Rules: post_purchase_return_inventory R5 (other workspace)."""
    po = po_('storage', f1.id)
    S(db, w1, f1, i1, 10, Decimal('12.50'), by=u1, clock=clock)
    ret = mk_return(db, w1, po, u1)
    pl2 = mk_line(db, po, i1, line_number=2)
    ri1 = mk_ri(db, w1, ret, pl2, Decimal('3'))
    w2_inv_row = inv_ledger_row(
        db, w2, inv_type=InventoryTypeEnum.STORAGE, factory=f2, item=i1,
        source_type=PO_RETURN_ITEM_SOURCE, source_id=ri1.id, qty=1, qty_before=0, qty_after=1,
        avg_before=None, avg_after=None, performed_at=clock(),
    )
    w2_mch_row = posted_machine(db, w2, m2, i1, ri1, by=u1, clock=clock)

    result = post_purchase_return_inventory(db, po, [(ri1, pl2)], workspace_id=w1.id, user_id=u2.id)

    assert result == 1
    assert reread_one_inventory(db, w1, f1, i1).qty == 7
    w1_rows = inv_rows_for(db, ri1, workspace_id=w1.id)
    assert len(w1_rows) == 1
    assert w1_rows[0].quantity == 3
    w2_inv_after = inv_rows_for(db, ri1, workspace_id=w2.id)
    assert [r.id for r in w2_inv_after] == [w2_inv_row.id]
    w2_mch_after = mch_rows_for(db, ri1, workspace_id=w2.id)
    assert [r.id for r in w2_mch_after] == [w2_mch_row.id]


def test_pri_p_30__other_source_type_does_not_block(db, w1, u1, u2, f1, i1, clock, po_):
    """PRI-P-30 — a ledger row with the return item's id but a different source_type does not
    make it count as posted.
    Rules: post_purchase_return_inventory R5 (other source_type)."""
    po = po_('storage', f1.id)
    ret = mk_return(db, w1, po, u1)
    pl2 = mk_line(db, po, i1, line_number=2)
    ri1 = mk_ri(db, w1, ret, pl2, Decimal('3'))
    inv_ledger_row(
        db, w1, inv_type=InventoryTypeEnum.STORAGE, factory=f1, item=i1,
        source_type='po_receive_event_item', source_id=ri1.id, qty=10, qty_before=0, qty_after=10,
        avg_before=None, avg_after=Decimal('12.50'), performed_at=clock(),
    )
    mk_inventory_row(db, w1, f1, i1, InventoryTypeEnum.STORAGE, 10, Decimal('12.50'), by=u1)

    result = post_purchase_return_inventory(db, po, [(ri1, pl2)], workspace_id=w1.id, user_id=u2.id)

    assert result == 1
    assert reread_one_inventory(db, w1, f1, i1).qty == 7
    assert len(inv_rows_for(db, ri1)) == 1


def test_pri_p_31__fractional_quantity_raises_400(db, w1, u1, u2, f1, i1, clock, po_):
    """PRI-P-31 — a fractional, not-yet-posted quantity raises 400 and writes nothing.
    Rules: post_purchase_return_inventory R6; Errors row 1."""
    po = po_('storage', f1.id)
    S(db, w1, f1, i1, 10, Decimal('12.50'), by=u1, clock=clock)
    ret = mk_return(db, w1, po, u1)
    pl2 = mk_line(db, po, i1, line_number=2)
    ri1 = mk_ri(db, w1, ret, pl2, Decimal('1.50'))

    with pytest.raises(HTTPException) as exc:
        post_purchase_return_inventory(db, po, [(ri1, pl2)], workspace_id=w1.id, user_id=u2.id)

    assert exc.value.status_code == 400
    assert exc.value.detail.startswith('Return line for PO ')
    assert exc.value.detail.endswith(SUFFIX)
    stock = reread_one_inventory(db, w1, f1, i1)
    check(stock, qty=10, updated_by=u1.id)
    no_return_rows(db, ri1)


@pytest.mark.xfail(strict=True, reason=BUG_802)
def test_pri_p_32__fractional_quantity_names_line_number(db, w1, u1, u2, f1, i1, clock, po_):
    """PRI-P-32 — the completion-path fractional-quantity error should name the PO line number.
    Rules: post_purchase_return_inventory R6 [BUG-802]; Errors row 1."""
    po = po_('storage', f1.id)
    S(db, w1, f1, i1, 10, Decimal('12.50'), by=u1, clock=clock)
    ret = mk_return(db, w1, po, u1)
    pl2 = mk_line(db, po, i1, line_number=2)
    if pl2.id == 2:
        mk_line(db, po, i1, line_number=99)
        pl2 = mk_line(db, po, i1, line_number=2)
    ri1 = mk_ri(db, w1, ret, pl2, Decimal('1.50'))

    with pytest.raises(HTTPException) as exc:
        post_purchase_return_inventory(db, po, [(ri1, pl2)], workspace_id=w1.id, user_id=u2.id)

    assert exc.value.status_code == 400
    assert exc.value.detail == "Return line for PO line 2 has a fractional quantity; inventory requires whole units"
    stock = reread_one_inventory(db, w1, f1, i1)
    check(stock, qty=10, updated_by=u1.id)
    no_return_rows(db, ri1)


def test_pri_p_33__earlier_lines_keep_writes_when_a_later_line_fails(db, w1, u1, u2, f1, i1, i2, clock, po_):
    """PRI-P-33 — a line's writes before a fractional-quantity failure stay flushed; later lines
    are not processed.
    Rules: post_purchase_return_inventory R6 (earlier lines stay, later lines not processed)."""
    po = po_('storage', f1.id)
    S(db, w1, f1, i1, 10, Decimal('12.50'), by=u1, clock=clock)
    S(db, w1, f1, i2, 4, Decimal('5.00'), by=u1, clock=clock)
    ret = mk_return(db, w1, po, u1)
    pl1 = mk_line(db, po, i1, line_number=1)
    pl2 = mk_line(db, po, i1, line_number=2)
    pl3 = mk_line(db, po, i2, line_number=3)
    ri1 = mk_ri(db, w1, ret, pl1, Decimal('2'))
    ri2 = mk_ri(db, w1, ret, pl2, Decimal('1.50'))
    ri3 = mk_ri(db, w1, ret, pl3, Decimal('1'))

    with pytest.raises(HTTPException) as exc:
        post_purchase_return_inventory(
            db, po, [(ri1, pl1), (ri2, pl2), (ri3, pl3)], workspace_id=w1.id, user_id=u2.id,
        )

    assert exc.value.status_code == 400
    assert exc.value.detail.endswith(SUFFIX)
    row1 = inv_rows_for(db, ri1)
    assert len(row1) == 1
    check(row1[0], quantity=2, qty_before=10, qty_after=8)
    assert reread_one_inventory(db, w1, f1, i1).qty == 8
    assert inv_rows_for(db, ri2) == []
    assert inv_rows_for(db, ri3) == []
    assert reread_one_inventory(db, w1, f1, i2).qty == 4


def test_pri_p_34__fractional_quantity_at_machine_destination(db, w1, u1, u2, m1, i1, po_):
    """PRI-P-34 — a fractional quantity at a machine destination also raises 400.
    Rules: post_purchase_return_inventory R6 (machine location)."""
    po = po_('machine', m1.id)
    MH(db, w1, m1, i1, 10)
    ret = mk_return(db, w1, po, u1)
    pl2 = mk_line(db, po, i1, line_number=2)
    ri1 = mk_ri(db, w1, ret, pl2, Decimal('1.50'))
    evt0 = max_activity_id(db)

    with pytest.raises(HTTPException) as exc:
        post_purchase_return_inventory(db, po, [(ri1, pl2)], workspace_id=w1.id, user_id=u2.id)

    assert exc.value.status_code == 400
    assert exc.value.detail.endswith(SUFFIX)
    assert reread_machine_item(db, w1, m1, i1).qty == 10
    no_return_rows(db, ri1)
    assert events_since(db, w1, evt0, machine=m1) == []


def test_pri_p_35__zero_quantity_skipped(db, w1, u1, u2, f1, i1, clock, po_):
    """PRI-P-35 — a zero quantity_returned line is skipped silently.
    Rules: post_purchase_return_inventory R7 (zero)."""
    po = po_('storage', f1.id)
    S(db, w1, f1, i1, 10, Decimal('12.50'), by=u1, clock=clock)
    ret = mk_return(db, w1, po, u1)
    pl2 = mk_line(db, po, i1, line_number=2)
    ri1 = mk_ri(db, w1, ret, pl2, Decimal('0'))

    result = post_purchase_return_inventory(db, po, [(ri1, pl2)], workspace_id=w1.id, user_id=u2.id)

    assert result == 0
    stock = reread_one_inventory(db, w1, f1, i1)
    check(stock, qty=10, updated_by=u1.id)
    no_return_rows(db, ri1)


def test_pri_p_36__negative_quantity_skipped(db, w1, u1, u2, f1, i1, clock, po_):
    """PRI-P-36 — a negative quantity_returned line is skipped silently (no stock added back).
    Rules: post_purchase_return_inventory R7 (negative)."""
    po = po_('storage', f1.id)
    S(db, w1, f1, i1, 10, Decimal('12.50'), by=u1, clock=clock)
    ret = mk_return(db, w1, po, u1)
    pl2 = mk_line(db, po, i1, line_number=2)
    ri1 = mk_ri(db, w1, ret, pl2, Decimal('-2'))

    result = post_purchase_return_inventory(db, po, [(ri1, pl2)], workspace_id=w1.id, user_id=u2.id)

    assert result == 0
    assert reread_one_inventory(db, w1, f1, i1).qty == 10
    no_return_rows(db, ri1)


def test_pri_p_37__quantity_one_posts(db, w1, u1, u2, f1, i1, clock, po_):
    """PRI-P-37 — the smallest positive whole quantity posts normally.
    Rules: post_purchase_return_inventory R7 (other side: 1 posts)."""
    po = po_('storage', f1.id)
    S(db, w1, f1, i1, 10, Decimal('12.50'), by=u1, clock=clock)
    ret = mk_return(db, w1, po, u1)
    pl2 = mk_line(db, po, i1, line_number=2)
    ri1 = mk_ri(db, w1, ret, pl2, Decimal('1.00'))

    result = post_purchase_return_inventory(db, po, [(ri1, pl2)], workspace_id=w1.id, user_id=u2.id)

    assert result == 1
    assert reread_one_inventory(db, w1, f1, i1).qty == 9
    row = inv_rows_for(db, ri1)[0]
    check(row, quantity=1, qty_before=10, qty_after=9)


def test_pri_p_38__multiple_storage_lines_chain_deductions(db, w1, u1, u2, f1, i1, clock, po_):
    """PRI-P-38 — two lines for the same item post as separate rows, each from the previous one's stock.
    Rules: post_purchase_return_inventory R15, R16 (storage)."""
    po = po_('storage', f1.id)
    S(db, w1, f1, i1, 10, Decimal('12.50'), by=u1, clock=clock)
    ret = mk_return(db, w1, po, u1)
    pl1 = mk_line(db, po, i1, line_number=1)
    pl2 = mk_line(db, po, i1, line_number=2)
    ri1 = mk_ri(db, w1, ret, pl1, Decimal('3'))
    ri2 = mk_ri(db, w1, ret, pl2, Decimal('4'))

    result = post_purchase_return_inventory(
        db, po, [(ri1, pl1), (ri2, pl2)], workspace_id=w1.id, user_id=u2.id,
    )

    assert result == 2
    assert reread_one_inventory(db, w1, f1, i1).qty == 3
    row1 = inv_rows_for(db, ri1)[0]
    check(row1, quantity=3, qty_before=10, qty_after=7)
    assert row1.notes.endswith('(line 1)')
    row2 = inv_rows_for(db, ri2)[0]
    check(row2, quantity=4, qty_before=7, qty_after=3)
    assert row2.notes.endswith('(line 2)')


def test_pri_p_39__multiple_machine_lines_chain_deductions(db, w1, u1, u2, m1, i1, clock, po_):
    """PRI-P-39 — two machine lines for the same item post as separate rows and events.
    Rules: post_purchase_return_inventory R15, R16 (machine)."""
    po = po_('machine', m1.id)
    MH(db, w1, m1, i1, 10)
    ML(db, w1, m1, i1, Decimal('12.50'), by=u1, clock=clock)
    ret = mk_return(db, w1, po, u1)
    pl1 = mk_line(db, po, i1, line_number=1)
    pl2 = mk_line(db, po, i1, line_number=2)
    ri1 = mk_ri(db, w1, ret, pl1, Decimal('3'))
    ri2 = mk_ri(db, w1, ret, pl2, Decimal('4'))
    evt0 = max_activity_id(db)

    result = post_purchase_return_inventory(
        db, po, [(ri1, pl1), (ri2, pl2)], workspace_id=w1.id, user_id=u2.id,
    )

    assert result == 2
    assert reread_machine_item(db, w1, m1, i1).qty == 3
    row1 = mch_rows_for(db, ri1)[0]
    check(row1, value_before=Decimal('125.00'), value_after=Decimal('87.50'))
    row2 = mch_rows_for(db, ri2)[0]
    check(row2, value_before=Decimal('87.50'), value_after=Decimal('37.50'))
    events = events_since(db, w1, evt0, machine=m1)
    assert len(events) == 2
    descriptions = {e.description for e in events}
    assert descriptions == {
        "Purchase returned: 3 units of Steel Bolt M8 to supplier",
        "Purchase returned: 4 units of Steel Bolt M8 to supplier",
    }


def test_pri_p_40__return_value_counts_only_posted_lines(db, w1, u1, u2, f1, i1, clock, po_):
    """PRI-P-40 — the returned count excludes already-posted and skipped (qty<=0) lines.
    Rules: post_purchase_return_inventory R16 (counts only posted)."""
    po = po_('storage', f1.id)
    inv_ledger_row(
        db, w1, inv_type=InventoryTypeEnum.STORAGE, factory=f1, item=i1,
        source_type='test_seed', source_id=1, qty=12, qty_before=0, qty_after=12,
        avg_before=None, avg_after=Decimal('12.50'), performed_at=clock(),
    )
    ret = mk_return(db, w1, po, u1)
    pl1 = mk_line(db, po, i1, line_number=1)
    pl2 = mk_line(db, po, i1, line_number=2)
    pl3 = mk_line(db, po, i1, line_number=3)
    ri1 = mk_ri(db, w1, ret, pl1, Decimal('2'))
    posted_storage(db, w1, f1, i1, ri1, 2, qty_before=12, qty_after=10, clock=clock, avg=Decimal('12.50'))
    mk_inventory_row(db, w1, f1, i1, InventoryTypeEnum.STORAGE, 10, Decimal('12.50'), by=u1)
    ri2 = mk_ri(db, w1, ret, pl2, Decimal('0'))
    ri3 = mk_ri(db, w1, ret, pl3, Decimal('3'))

    result = post_purchase_return_inventory(
        db, po, [(ri1, pl1), (ri2, pl2), (ri3, pl3)], workspace_id=w1.id, user_id=u2.id,
    )

    assert result == 1
    assert reread_one_inventory(db, w1, f1, i1).qty == 7
    assert len(inv_rows_for(db, ri1)) == 1
    assert inv_rows_for(db, ri2) == []
    row3 = inv_rows_for(db, ri3)
    assert len(row3) == 1
    check(row3[0], quantity=3, qty_before=10, qty_after=7)


def test_pri_p_41__stock_row_resynced_from_ledger_before_deduction(db, w1, u1, u2, f1, i1, clock, po_):
    """PRI-P-41 — a stock row that disagrees with the ledger is re-synced before deducting.
    Rules: post_purchase_return_inventory R8a, R8."""
    po = po_('storage', f1.id)
    inv_ledger_row(
        db, w1, inv_type=InventoryTypeEnum.STORAGE, factory=f1, item=i1,
        source_type='test_seed', source_id=1, qty=8, qty_before=0, qty_after=8,
        avg_before=None, avg_after=Decimal('11.00'), performed_at=clock(),
    )
    mk_inventory_row(db, w1, f1, i1, InventoryTypeEnum.STORAGE, 10, Decimal('12.50'), by=u1)
    ret = mk_return(db, w1, po, u1)
    pl2 = mk_line(db, po, i1, line_number=2)
    ri1 = mk_ri(db, w1, ret, pl2, Decimal('3'))

    result = post_purchase_return_inventory(db, po, [(ri1, pl2)], workspace_id=w1.id, user_id=u2.id)

    assert result == 1
    row = inv_rows_for(db, ri1)[0]
    check(row, qty_before=8, qty_after=5, unit_cost=Decimal('11.00'), total_cost=Decimal('33.00'),
          avg_price_before=Decimal('11.00'), avg_price_after=Decimal('11.00'))
    stock = reread_one_inventory(db, w1, f1, i1)
    check(stock, qty=5, avg_price=Decimal('11.00'), updated_by=u2.id)


def test_pri_p_42__no_ledger_rows_resync_overwrite_kept_on_failure(db, w1, u1, u2, f1, i1, po_):
    """PRI-P-42 — with no ledger rows the stock row is re-synced to 0/null even though the
    deduction then fails; the overwrite is kept (not rolled back).
    Rules: post_purchase_return_inventory R8a (no ledger rows), R9; Errors row 2."""
    po = po_('storage', f1.id)
    row = mk_inventory_row(db, w1, f1, i1, InventoryTypeEnum.STORAGE, 10, Decimal('12.50'), by=u1)
    ret = mk_return(db, w1, po, u1)
    pl2 = mk_line(db, po, i1, line_number=2)
    ri1 = mk_ri(db, w1, ret, pl2, Decimal('3'))

    with pytest.raises(HTTPException) as exc:
        post_purchase_return_inventory(db, po, [(ri1, pl2)], workspace_id=w1.id, user_id=u2.id)

    assert exc.value.status_code == 400
    assert exc.value.detail == insuff_storage(0, 3)
    db.expire_all()
    reloaded = db.get(Inventory, row.id)
    assert reloaded.qty == 0
    assert reloaded.avg_price is None
    assert reloaded.updated_by == u2.id
    no_return_rows(db, ri1)


def test_pri_p_43__latest_by_performed_at_not_insertion_order(db, w1, u1, u2, f1, i1, clock, po_):
    """PRI-P-43 — "latest" is determined by performed_at, not by id/insertion order.
    Rules: post_purchase_return_inventory R8a (latest = performed_at, not id)."""
    po = po_('storage', f1.id)
    t0 = clock()
    inv_ledger_row(
        db, w1, inv_type=InventoryTypeEnum.STORAGE, factory=f1, item=i1,
        source_type='test_seed', source_id=1, qty=9, qty_before=0, qty_after=9,
        avg_before=None, avg_after=Decimal('12.00'), performed_at=t0 + timedelta(minutes=10),
    )
    inv_ledger_row(
        db, w1, inv_type=InventoryTypeEnum.STORAGE, factory=f1, item=i1,
        source_type='test_seed', source_id=1, qty=4, qty_before=0, qty_after=4,
        avg_before=None, avg_after=Decimal('8.00'), performed_at=t0,
    )
    mk_inventory_row(db, w1, f1, i1, InventoryTypeEnum.STORAGE, 9, Decimal('12.00'), by=u1)
    ret = mk_return(db, w1, po, u1)
    pl2 = mk_line(db, po, i1, line_number=2)
    ri1 = mk_ri(db, w1, ret, pl2, Decimal('3'))

    result = post_purchase_return_inventory(db, po, [(ri1, pl2)], workspace_id=w1.id, user_id=u2.id)

    assert result == 1
    row = inv_rows_for(db, ri1)[0]
    check(row, qty_before=9, qty_after=6, unit_cost=Decimal('12.00'))
    stock = reread_one_inventory(db, w1, f1, i1)
    check(stock, qty=6, avg_price=Decimal('12.00'))


def test_pri_p_44__only_matching_bucket_considered_for_latest(
    db, w1, w2, u1, u2, f1, f1d, f2, i1, i2, ix, clock, po_,
):
    """PRI-P-44 — only ledger rows of this workspace/factory/item/storage-type count toward "latest".
    Rules: post_purchase_return_inventory R8a (only this workspace/factory/item/storage-type rows count)."""
    po = po_('storage', f1.id)
    t0 = clock()
    inv_ledger_row(
        db, w1, inv_type=InventoryTypeEnum.STORAGE, factory=f1, item=i1,
        source_type='test_seed', source_id=1, qty=5, qty_before=0, qty_after=5,
        avg_before=None, avg_after=Decimal('12.50'), performed_at=t0,
    )
    mk_inventory_row(db, w1, f1, i1, InventoryTypeEnum.STORAGE, 5, Decimal('12.50'), by=u1)
    inv_ledger_row(
        db, w1, inv_type=InventoryTypeEnum.DAMAGED, factory=f1, item=i1,
        source_type='test_seed', source_id=1, qty=50, qty_before=0, qty_after=50,
        avg_before=None, avg_after=Decimal('1.00'), performed_at=t0 + timedelta(minutes=1),
    )
    inv_ledger_row(
        db, w1, inv_type=InventoryTypeEnum.STORAGE, factory=f1, item=i2,
        source_type='test_seed', source_id=1, qty=60, qty_before=0, qty_after=60,
        avg_before=None, avg_after=Decimal('2.00'), performed_at=t0 + timedelta(minutes=2),
    )
    mk_inventory_row(db, w1, f1, i2, InventoryTypeEnum.STORAGE, 60, Decimal('2.00'), by=u1)
    inv_ledger_row(
        db, w1, inv_type=InventoryTypeEnum.STORAGE, factory=f1d, item=i1,
        source_type='test_seed', source_id=1, qty=70, qty_before=0, qty_after=70,
        avg_before=None, avg_after=Decimal('3.00'), performed_at=t0 + timedelta(minutes=3),
    )
    inv_ledger_row(
        db, w2, inv_type=InventoryTypeEnum.STORAGE, factory=f2, item=ix,
        source_type='test_seed', source_id=1, qty=80, qty_before=0, qty_after=80,
        avg_before=None, avg_after=Decimal('4.00'), performed_at=t0 + timedelta(minutes=4),
    )
    ret = mk_return(db, w1, po, u1)
    pl2 = mk_line(db, po, i1, line_number=2)
    ri1 = mk_ri(db, w1, ret, pl2, Decimal('3'))

    result = post_purchase_return_inventory(db, po, [(ri1, pl2)], workspace_id=w1.id, user_id=u2.id)

    assert result == 1
    row = inv_rows_for(db, ri1)[0]
    check(row, qty_before=5, qty_after=2, unit_cost=Decimal('12.50'))
    stock = reread_one_inventory(db, w1, f1, i1)
    check(stock, qty=2, avg_price=Decimal('12.50'))
    assert reread_one_inventory(db, w1, f1, i2).qty == 60


def test_pri_p_45__soft_deleted_stock_row_restored_and_resynced(db, w1, u1, u2, f1, i1, clock, po_):
    """PRI-P-45 — a soft-deleted stock row is restored (not duplicated) and then re-synced.
    Rules: post_purchase_return_inventory side effects (soft-deleted stock row restored then re-synced)."""
    po = po_('storage', f1.id)
    inv_ledger_row(
        db, w1, inv_type=InventoryTypeEnum.STORAGE, factory=f1, item=i1,
        source_type='test_seed', source_id=1, qty=10, qty_before=0, qty_after=10,
        avg_before=None, avg_after=Decimal('12.50'), performed_at=clock(),
    )
    deleted_row = mk_inventory_row(
        db, w1, f1, i1, InventoryTypeEnum.STORAGE, 10, Decimal('12.50'), by=u1, deleted=True,
    )
    ret = mk_return(db, w1, po, u1)
    pl2 = mk_line(db, po, i1, line_number=2)
    ri1 = mk_ri(db, w1, ret, pl2, Decimal('3'))

    result = post_purchase_return_inventory(db, po, [(ri1, pl2)], workspace_id=w1.id, user_id=u2.id)

    assert result == 1
    rows = reread_inventory_rows(db, w1, f1, i1)
    assert len(rows) == 1
    assert rows[0].id == deleted_row.id
    check(rows[0], is_deleted=False, qty=7, avg_price=Decimal('12.50'))
    row = inv_rows_for(db, ri1)[0]
    check(row, qty_before=10, qty_after=7)


def test_pri_p_46__machine_latest_by_performed_at_not_insertion_order(db, w1, u1, u2, m1, i1, clock, po_):
    """PRI-P-46 — the machine ledger's "most recent" entry is chosen by performed_at, not id.
    Rules: post_purchase_return_inventory R11 (most recent = performed_at, not id)."""
    po = po_('machine', m1.id)
    MH(db, w1, m1, i1, 10)
    t0 = clock()
    ML(db, w1, m1, i1, Decimal('12.50'), by=u1, clock=clock, performed_at=t0 + timedelta(minutes=10))
    ML(db, w1, m1, i1, Decimal('9.00'), by=u1, clock=clock, performed_at=t0)
    ret = mk_return(db, w1, po, u1)
    pl2 = mk_line(db, po, i1, line_number=2)
    ri1 = mk_ri(db, w1, ret, pl2, Decimal('3'))

    result = post_purchase_return_inventory(db, po, [(ri1, pl2)], workspace_id=w1.id, user_id=u2.id)

    assert result == 1
    row = mch_rows_for(db, ri1)[0]
    check(row, unit_cost=Decimal('12.50'), value_before=Decimal('125.00'), value_after=Decimal('87.50'),
          avg_price_before=Decimal('12.50'), avg_price_after=Decimal('12.50'))
    assert reread_machine_item(db, w1, m1, i1).qty == 7


@pytest.mark.xfail(strict=False, reason=BUG_803)
def test_pri_p_47__three_same_item_lines_chain_correctly(db, w1, u1, u2, f1, i1, clock, po_):
    """PRI-P-47 — three lines for the same item should each deduct from the previous line's stock.
    Rules: post_purchase_return_inventory R15a [BUG-803], R15, R16."""
    po = po_('storage', f1.id)
    S(db, w1, f1, i1, 10, Decimal('12.50'), by=u1, clock=clock)
    ret = mk_return(db, w1, po, u1)
    pl1 = mk_line(db, po, i1, line_number=1)
    pl2 = mk_line(db, po, i1, line_number=2)
    pl3 = mk_line(db, po, i1, line_number=3)
    ri1 = mk_ri(db, w1, ret, pl1, Decimal('3'))
    ri2 = mk_ri(db, w1, ret, pl2, Decimal('3'))
    ri3 = mk_ri(db, w1, ret, pl3, Decimal('3'))

    result = post_purchase_return_inventory(
        db, po, [(ri1, pl1), (ri2, pl2), (ri3, pl3)], workspace_id=w1.id, user_id=u2.id,
    )

    assert result == 3
    row1 = inv_rows_for(db, ri1)[0]
    check(row1, qty_before=10, qty_after=7)
    row2 = inv_rows_for(db, ri2)[0]
    check(row2, qty_before=7, qty_after=4)
    row3 = inv_rows_for(db, ri3)[0]
    check(row3, qty_before=4, qty_after=1)
    assert reread_one_inventory(db, w1, f1, i1).qty == 1
