# ruff: noqa: DTZ001, SIM117, FURB157
# (naive datetimes are the Conventions' own; pytest.raises + begin_nested are kept
# as two `with` blocks as the cards read; Decimal("…") literals are the cards' own.)
"""Unit tests for app/managers/inventory_manager.py.

Implements tests/unit/managers/inventory_manager.cases.md (revision 5), one
test per case. Real Postgres session (`db` fixture). No externals mocked
(spec Conventions: created_at/updated_at/performed_at all come from the
database); the only patches are the RS-1 race simulation.
"""
import itertools
import re
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import event, func, select
from sqlalchemy.exc import IntegrityError

from app.dao.inventory import inventory_dao
from app.managers.inventory_manager import InventoryManager
from app.models.enums import InventoryTypeEnum
from app.models.factory import Factory
from app.models.inventory import Inventory
from app.models.inventory_ledger import InventoryLedger
from app.models.item import Item
from app.models.order_workflow import OrderWorkflow
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.status import Status
from app.models.transfer_order import TransferOrder
from app.models.transfer_order_item import TransferOrderItem
from app.schemas.inventory import InventoryCreate, InventoryUpdate
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> fixtures / helpers
# --------------------------------------------------------------------------- #

STORAGE = InventoryTypeEnum.STORAGE
DAMAGED = InventoryTypeEnum.DAMAGED
WASTE = InventoryTypeEnum.WASTE
SCRAP = InventoryTypeEnum.SCRAP

BUG_700 = "BUG-700: get_inventory returns soft-deleted inventory rows"
BUG_701 = "BUG-701: Inventory list has no stable sort order"
BUG_702 = "BUG-702: Inventory/stats search text acts as SQL wildcards"
BUG_703 = "BUG-703: update_inventory stamps updated_by on no-op updates"
BUG_704 = "BUG-704: update_inventory reads stock quantity without a row lock"
BUG_705 = "BUG-705: delete_inventory (\"clear stock\") reads stock without a row lock"
BUG_706 = "BUG-706: Incoming summary processes factories with no sort order"
BUG_707 = "BUG-707: Zero average price records ledger total_cost as empty"
BUG_708 = "BUG-708: avg_price with too many decimals/digits accepted"
BUG_709 = "BUG-709: Workspace-wide incoming summary silently covers at most 500 factories"
BUG_710 = "BUG-710: Inventory can be created for a catalog item of another workspace"
BUG_711 = "BUG-711: Negative qty and avg_price accepted"
BUG_712 = "BUG-712: Average price can change with no ledger entry"
BUG_713 = "BUG-713: Update cannot clear note or avg_price"
BUG_714 = "BUG-714: Creating over a soft-deleted row fails with an opaque database conflict"
BUG_715 = "BUG-715: Inventory can be created in a soft-deleted factory"
BUG_716 = "BUG-716: \"Clear stock\" leaves a negative quantity untouched"
BUG_717 = "BUG-717: Voided purchase orders still count as incoming stock"
BUG_718 = "BUG-718: Per-factory incoming summary accepts a soft-deleted factory"
BUG_719 = "BUG-719: Per-type breakdown in inventory stats has no fixed order"

_seq = itertools.count(1)


# Convention "W1, W2, W3 = workspaces"
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db):
    return make_workspace(db)


@pytest.fixture
def w3(db):
    return make_workspace(db)


# Convention "U1, U2 = profiles in W1"
@pytest.fixture
def u1(db):
    return make_profile(db)


@pytest.fixture
def u2(db):
    return make_profile(db)


# Convention "M = an InventoryManager() instance"
@pytest.fixture
def M():
    return InventoryManager()


# --------------------------------------------------------------------------- #
# Row builders (local; not promoted to factories.py in this batch run)
# --------------------------------------------------------------------------- #

def mk_factory(db, ws, name, *, active=True, deleted=False):
    row = Factory(
        workspace_id=ws.id, name=name, abbreviation=name[:3].upper(),
        is_active=active, is_deleted=deleted,
    )
    db.add(row)
    db.flush()
    return row


def mk_item(db, ws, name, unit="pcs", *, active=True):
    row = Item(
        workspace_id=ws.id, name=name, name_normalized=name.lower(),
        unit=unit, is_active=active,
    )
    db.add(row)
    db.flush()
    return row


def mk_inv(db, ws, item, inv_type, factory, qty, avg_price, note, *,
           is_active=True, is_deleted=False, created_by=None, updated_by=None):
    row = Inventory(
        workspace_id=ws.id, item_id=item.id, inventory_type=inv_type, factory_id=factory.id,
        qty=qty, avg_price=avg_price, note=note,
        is_active=is_active, is_deleted=is_deleted,
        created_by=created_by, updated_by=updated_by,
    )
    db.add(row)
    db.flush()
    return row


def mk_status(db, ws, name):
    row = Status(workspace_id=ws.id, name=name, comment=name)
    db.add(row)
    db.flush()
    return row


def mk_workflow(db, ws, *, status_sequence):
    n = next(_seq)
    row = OrderWorkflow(
        workspace_id=ws.id, name=f"WF {n}", type=f"wf-type-{n}",
        status_sequence=status_sequence,
    )
    db.add(row)
    db.flush()
    return row


def mk_po(db, ws, u, *, status, factory=None, destination_type="storage",
          destination_id=None, workflow=None, voided=False, number, id_=None):
    row = PurchaseOrder(
        id=id_,
        workspace_id=ws.id,
        po_number=number,
        destination_type=destination_type,
        destination_id=destination_id if destination_id is not None else factory.id,
        current_status_id=status.id,
        order_workflow_id=workflow.id if workflow else None,
        voided=voided,
        created_by=u.id,
    )
    db.add(row)
    db.flush()
    return row


def mk_po_line(db, ws, po, item, qty_ordered, qty_received, *, line_number=1):
    """quantity_ordered / quantity_received are NOT NULL DB columns with no
    reliable NULL path; a cases-file 'NULL' for either is implemented as 0,
    which the manager's own `value or 0` fallback treats identically to a
    real NULL (best-practice default, delegated by reviewer)."""
    row = PurchaseOrderItem(
        workspace_id=ws.id, purchase_order_id=po.id, line_number=line_number,
        item_id=item.id,
        quantity_ordered=Decimal(str(qty_ordered)) if qty_ordered is not None else Decimal("0"),
        quantity_received=Decimal(str(qty_received)) if qty_received is not None else Decimal("0"),
    )
    db.add(row)
    db.flush()
    return row


def mk_tr(db, ws, u, *, status, factory=None, destination_location_type="storage",
          destination_location_id=None, completed_at=None, number, id_=None):
    row = TransferOrder(
        id=id_,
        workspace_id=ws.id,
        transfer_number=number,
        source_location_type="storage",
        source_location_id=factory.id if factory else 0,
        destination_location_type=destination_location_type,
        destination_location_id=(
            destination_location_id if destination_location_id is not None else factory.id
        ),
        current_status_id=status.id,
        created_by=u.id,
        completed_at=completed_at,
    )
    db.add(row)
    db.flush()
    return row


def mk_tr_line(db, ws, tr, item, qty, *, line_number=1):
    row = TransferOrderItem(
        workspace_id=ws.id, transfer_order_id=tr.id, line_number=line_number,
        item_id=item.id,
        quantity=Decimal(str(qty)) if qty is not None else Decimal("0"),
    )
    db.add(row)
    db.flush()
    return row


# --------------------------------------------------------------------------- #
# Shared rows (Conventions: Factories, Catalog items, Inventory rows)
# --------------------------------------------------------------------------- #

@pytest.fixture
def f1(db, w1):
    return mk_factory(db, w1, "Main Plant")


@pytest.fixture
def f2(db, w1):
    return mk_factory(db, w1, "Second Plant")


@pytest.fixture
def f_in(db, w1):
    return mk_factory(db, w1, "Idle Plant", active=False)


@pytest.fixture
def f_del(db, w1):
    return mk_factory(db, w1, "Old Plant", deleted=True)


@pytest.fixture
def fx(db, w2):
    return mk_factory(db, w2, "Foreign Plant")


@pytest.fixture
def i1(db, w1):
    return mk_item(db, w1, "Bolt", "pkgs")


@pytest.fixture
def i2(db, w1, i1):
    return mk_item(db, w1, "Hex Nut", "pcs")


@pytest.fixture
def i3(db, w1, i2):
    return mk_item(db, w1, "Washer", "pcs")


@pytest.fixture
def i4(db, w1, i3):
    return mk_item(db, w1, "Rivet", "pcs")


@pytest.fixture
def i5(db, w1, i4):
    return mk_item(db, w1, "Screw", "pcs")


@pytest.fixture
def ix(db, w2):
    return mk_item(db, w2, "Secret Part", "pcs")


# Convention "Inventory rows ... unless stated created_by U2, updated_by NULL"
@pytest.fixture
def inv(db, u2):
    def _mk(ws, item, inv_type, factory, qty, avg_price, note, **kw):
        kw.setdefault("created_by", u2.id)
        return mk_inv(db, ws, item, inv_type, factory, qty, avg_price, note, **kw)
    return _mk


@pytest.fixture
def T(inv, w1, i1, f1):
    return inv(w1, i1, STORAGE, f1, 10, Decimal("5.00"), "n1")


@pytest.fixture
def TX(inv, w2, ix, fx):
    return inv(w2, ix, STORAGE, fx, 10, Decimal("5.00"), "x1")


@pytest.fixture
def TD(inv, w1, i1, f1):
    return inv(w1, i1, STORAGE, f1, 10, Decimal("5.00"), "n1", is_deleted=True, is_active=False)


# Convention "Incoming-summary vocabulary"
@pytest.fixture
def s_open(db, w1):
    return mk_status(db, w1, "Ordered")


@pytest.fixture
def s_done(db, w1):
    return mk_status(db, w1, "Received")


@pytest.fixture
def s_tr(db, w1):
    return mk_status(db, w1, "In Transit")


@pytest.fixture
def s_draft(db, w1):
    return mk_status(db, w1, "Draft")


@pytest.fixture
def wf(db, w1, s_open, s_done):
    return mk_workflow(db, w1, status_sequence=[s_open.id, s_done.id])


# Convention "RS-1" race simulation (create_inventory R9 only)
@pytest.fixture
def race_rs1():
    with patch.object(inventory_dao, "get_by_factory_item_type", return_value=None), \
         patch.object(inventory_dao, "_get_any_by_factory_item_type", return_value=None, create=True):
        yield


# --------------------------------------------------------------------------- #
# Query / assertion helpers
# --------------------------------------------------------------------------- #

def reread_inv(db, inv_id):
    db.expire_all()
    return db.execute(select(Inventory).where(Inventory.id == inv_id)).scalar_one()


def ledger_rows(db, ws, factory, item, inv_type):
    """Ledger rows for the (workspace, factory, item, type) bucket, by id."""
    db.expire_all()
    return db.execute(
        select(InventoryLedger).where(
            InventoryLedger.workspace_id == ws.id,
            InventoryLedger.factory_id == factory.id,
            InventoryLedger.item_id == item.id,
            InventoryLedger.inventory_type == inv_type,
        ).order_by(InventoryLedger.id)
    ).scalars().all()


def ws_counts(db, ws):
    """(# inventory rows, # ledger rows) in the workspace, fresh query."""
    db.expire_all()
    inv_n = db.scalar(
        select(func.count()).select_from(Inventory).where(Inventory.workspace_id == ws.id)
    )
    led_n = db.scalar(
        select(func.count()).select_from(InventoryLedger).where(InventoryLedger.workspace_id == ws.id)
    )
    return inv_n, led_n


def missing_id_for(db, model):
    return (db.scalar(select(func.max(model.id))) or 0) + 100000


def inv_rows_for(db, ws, item, inv_type, factory, *, include_deleted=True):
    db.expire_all()
    q = select(Inventory).where(
        Inventory.workspace_id == ws.id, Inventory.item_id == item.id,
        Inventory.inventory_type == inv_type, Inventory.factory_id == factory.id,
    )
    if not include_deleted:
        q = q.where(Inventory.is_deleted == False)
    return db.execute(q.order_by(Inventory.id)).scalars().all()


def assert_fields(row, **expected):
    for k, v in expected.items():
        actual = getattr(row, k)
        assert actual == v, f"{k}: expected {v!r}, got {actual!r}"


def not_found_factory(fid):
    return f"Factory with ID {fid} not found"


def not_found_item(iid):
    return f"Item with ID {iid} not found"


def not_found_inv(iid):
    return f"Inventory record with ID {iid} not found"


# Convention "SQL capture (lock cases)"
_LOCKED_READ_RE = re.compile(r"\bfrom\s+inventory\b", re.IGNORECASE)


class SQLCapture:
    def __init__(self, db):
        self.conn = db.connection()
        self.statements = []

    def _on(self, conn, cursor, statement, parameters, context, executemany):
        self.statements.append(statement)

    def __enter__(self):
        event.listen(self.conn, "before_cursor_execute", self._on)
        return self

    def __exit__(self, *exc):
        event.remove(self.conn, "before_cursor_execute", self._on)
        return False


def inventory_selects(statements):
    return [s for s in statements if s.lstrip().upper().startswith("SELECT") and _LOCKED_READ_RE.search(s)]


# exact clause FOR UPDATE OF inventory (spec G9)
def locked_read_of_inventory(statements):
    return any(s.rstrip().endswith("FOR UPDATE OF inventory") for s in inventory_selects(statements))


def no_nowait_or_skip_locked(statements):
    return not any("NOWAIT" in s.upper() or "SKIP LOCKED" in s.upper() for s in inventory_selects(statements))


# Convention "Results": incoming-summary field-by-field comparison
def order_tuple(o):
    return (o.order_kind, o.order_id, o.order_number, o.status_name, o.pending_qty)


def summary_tuples(result):
    return [
        (s.factory_id, s.item_id, s.total_pending_qty, s.order_count,
         [order_tuple(o) for o in s.orders])
        for s in result
    ]


def page_ids(result):
    return [row.id for row in result.items]


def by_type_map(result):
    return {row.inventory_type: (row.unique_item_count, row.total_qty) for row in result.by_type}


def by_type_list(result):
    return [(row.inventory_type, row.unique_item_count, row.total_qty) for row in result.by_type]


# =========================================================================== #
# InventoryManager.create_inventory
# =========================================================================== #

def test_inv_c_01__happy_path_full_ledger_entry(db, M, w1, u1, i1, f1):
    """INV-C-01 — creating a new row writes the row and a full initial ledger entry.
    Rules: create_inventory R4 R6 R7 R8."""
    res = M.create_inventory(
        db, InventoryCreate(item_id=i1.id, inventory_type=STORAGE, factory_id=f1.id,
                             qty=3, avg_price=Decimal("10.50"), note=" Opening stock "),
        w1.id, u1.id,
    )
    assert res.id is not None
    r = reread_inv(db, res.id)
    assert_fields(
        r, workspace_id=w1.id, item_id=i1.id, inventory_type=STORAGE, factory_id=f1.id,
        qty=3, avg_price=Decimal("10.50"), note=" Opening stock ",
        created_by=u1.id, updated_by=None, is_active=True, is_deleted=False,
    )
    assert r.created_at is not None
    rows = ledger_rows(db, w1, f1, i1, STORAGE)
    assert len(rows) == 1
    assert_fields(
        rows[0], workspace_id=w1.id, inventory_type=STORAGE, factory_id=f1.id, item_id=i1.id,
        transaction_type="manual_add", quantity=3, unit_cost=Decimal("10.50"),
        total_cost=Decimal("31.50"), qty_before=0, qty_after=3,
        avg_price_before=None, avg_price_after=Decimal("10.50"), source_type="manual",
        source_id=None, notes="Initial inventory record created", performed_by=u1.id,
    )


def test_inv_c_02__qty_one_ledger_entry(db, M, w1, u1, i1, f1):
    """INV-C-02 — qty 1 writes matching ledger quantity/cost fields.
    Rules: create_inventory R7."""
    res = M.create_inventory(
        db, InventoryCreate(item_id=i1.id, inventory_type=STORAGE, factory_id=f1.id,
                             qty=1, avg_price=Decimal("2.00")),
        w1.id, u1.id,
    )
    assert res.id is not None
    r = reread_inv(db, res.id)
    assert r.qty == 1
    rows = ledger_rows(db, w1, f1, i1, STORAGE)
    assert len(rows) == 1
    assert_fields(rows[0], quantity=1, qty_before=0, qty_after=1,
                  unit_cost=Decimal("2.00"), total_cost=Decimal("2.00"))


def test_inv_c_03__zero_qty_no_ledger(db, M, w1, u1, i1, f1):
    """INV-C-03 — qty 0 (avg_price/note None) writes no ledger entry.
    Rules: create_inventory R7 R7a."""
    res = M.create_inventory(
        db, InventoryCreate(item_id=i1.id, inventory_type=STORAGE, factory_id=f1.id,
                             qty=0, avg_price=None, note=None),
        w1.id, u1.id,
    )
    assert res.id is not None
    r = reread_inv(db, res.id)
    assert r.qty == 0
    assert r.avg_price is None
    assert r.note is None
    assert ledger_rows(db, w1, f1, i1, STORAGE) == []


@pytest.mark.xfail(strict=True, reason=BUG_712)
def test_inv_c_04__zero_qty_with_price_still_no_ledger(db, M, w1, u1, i1, f1):
    """INV-C-04 — qty 0 with avg_price set should still write a full initial ledger entry.
    Rules: create_inventory R7a R8 [BUG-712]."""
    res = M.create_inventory(
        db, InventoryCreate(item_id=i1.id, inventory_type=STORAGE, factory_id=f1.id,
                             qty=0, avg_price=Decimal("4.25")),
        w1.id, u1.id,
    )
    assert res.id is not None
    rows = ledger_rows(db, w1, f1, i1, STORAGE)
    assert len(rows) == 1
    assert_fields(
        rows[0], transaction_type="manual_add", quantity=0, qty_before=0, qty_after=0,
        unit_cost=Decimal("4.25"), total_cost=Decimal("0.00"), avg_price_before=None,
        avg_price_after=Decimal("4.25"), source_type="manual",
        notes="Initial inventory record created", performed_by=u1.id,
    )


def test_inv_c_05__zero_qty_with_price_stored(db, M, w1, u1, i1, f1):
    """INV-C-05 — qty 0 with avg_price set still stores the row with that price.
    Rules: create_inventory R7."""
    res = M.create_inventory(
        db, InventoryCreate(item_id=i1.id, inventory_type=STORAGE, factory_id=f1.id,
                             qty=0, avg_price=Decimal("4.25")),
        w1.id, u1.id,
    )
    assert res.id is not None
    r = reread_inv(db, res.id)
    assert r.qty == 0
    assert r.avg_price == Decimal("4.25")


def test_inv_c_06__negative_qty_bypassing_validation_no_ledger(db, M, w1, u1, i1, f1):
    """INV-C-06 — a negative qty built via model_construct (validation bypassed) stores as-is, no ledger.
    Rules: create_inventory R7."""
    data = InventoryCreate.model_construct(
        item_id=i1.id, inventory_type=STORAGE, factory_id=f1.id,
        qty=-5, avg_price=Decimal("3.00"), note=None,
    )
    res = M.create_inventory(db, data, w1.id, u1.id)
    assert res.id is not None
    r = reread_inv(db, res.id)
    assert r.qty == -5
    assert r.avg_price == Decimal("3.00")
    assert ledger_rows(db, w1, f1, i1, STORAGE) == []


def test_inv_c_07__zero_avg_price_ledger_fields(db, M, w1, u1, i1, f1):
    """INV-C-07 — avg_price 0 stores 0.00 and writes ledger quantity/unit_cost/avg fields (total_cost untested here).
    Rules: create_inventory R8."""
    res = M.create_inventory(
        db, InventoryCreate(item_id=i1.id, inventory_type=STORAGE, factory_id=f1.id,
                             qty=10, avg_price=0),
        w1.id, u1.id,
    )
    assert res.id is not None
    r = reread_inv(db, res.id)
    assert r.avg_price == Decimal("0.00")
    rows = ledger_rows(db, w1, f1, i1, STORAGE)
    assert len(rows) == 1
    assert_fields(rows[0], quantity=10, unit_cost=Decimal("0.00"), qty_after=10,
                  avg_price_after=Decimal("0.00"))


@pytest.mark.xfail(strict=True, reason=BUG_707)
def test_inv_c_08__zero_avg_price_total_cost_zero(db, M, w1, u1, i1, f1):
    """INV-C-08 — avg_price 0 should give ledger total_cost 0.00 (not NULL).
    Rules: create_inventory R8 [BUG-707]."""
    res = M.create_inventory(
        db, InventoryCreate(item_id=i1.id, inventory_type=STORAGE, factory_id=f1.id,
                             qty=10, avg_price=0),
        w1.id, u1.id,
    )
    assert res.id is not None
    rows = ledger_rows(db, w1, f1, i1, STORAGE)
    assert rows[0].total_cost == Decimal("0.00")


def test_inv_c_09__null_avg_price_ledger_fields(db, M, w1, u1, i1, f1):
    """INV-C-09 — avg_price None writes ledger with NULL cost fields.
    Rules: create_inventory R8."""
    res = M.create_inventory(
        db, InventoryCreate(item_id=i1.id, inventory_type=STORAGE, factory_id=f1.id,
                             qty=5, avg_price=None),
        w1.id, u1.id,
    )
    assert res.id is not None
    rows = ledger_rows(db, w1, f1, i1, STORAGE)
    assert len(rows) == 1
    assert_fields(rows[0], quantity=5, unit_cost=None, total_cost=None,
                  avg_price_after=None, qty_after=5)


def test_inv_c_10__missing_factory_404(db, M, w1, u1, i1):
    """INV-C-10 — an unknown factory id raises 404 and writes nothing.
    Rules: create_inventory R1; Errors row 1."""
    missing = missing_id_for(db, Factory)
    with pytest.raises(HTTPException) as exc:
        M.create_inventory(
            db, InventoryCreate(item_id=i1.id, inventory_type=STORAGE, factory_id=missing, qty=3),
            w1.id, u1.id,
        )
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_factory(missing)
    assert ws_counts(db, w1) == (0, 0)


def test_inv_c_11__other_workspace_factory_404(db, M, w1, w2, u1, i1, fx):
    """INV-C-11 — a factory of another workspace is reported as not found.
    Rules: create_inventory R1; Errors row 1."""
    with pytest.raises(HTTPException) as exc:
        M.create_inventory(
            db, InventoryCreate(item_id=i1.id, inventory_type=STORAGE, factory_id=fx.id, qty=3),
            w1.id, u1.id,
        )
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_factory(fx.id)
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(Inventory).where(Inventory.item_id == i1.id)) == 0
    assert ws_counts(db, w1) == (0, 0)
    assert ws_counts(db, w2) == (0, 0)


@pytest.mark.xfail(strict=True, reason=BUG_715)
def test_inv_c_12__deleted_factory_should_404(db, M, w1, u1, i1, f_del):
    """INV-C-12 — a soft-deleted factory should raise 404 and write nothing.
    Rules: create_inventory R2 [BUG-715]; Errors row 1."""
    with pytest.raises(HTTPException) as exc:
        M.create_inventory(
            db, InventoryCreate(item_id=i1.id, inventory_type=STORAGE, factory_id=f_del.id, qty=3),
            w1.id, u1.id,
        )
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_factory(f_del.id)
    assert inv_rows_for(db, w1, i1, STORAGE, f_del) == []
    assert ws_counts(db, w1) == (0, 0)


def test_inv_c_13__inactive_factory_accepted(db, M, w1, u1, i1, f_in):
    """INV-C-13 — an inactive-but-live factory is accepted.
    Rules: create_inventory R2."""
    res = M.create_inventory(
        db, InventoryCreate(item_id=i1.id, inventory_type=STORAGE, factory_id=f_in.id,
                             qty=2, avg_price=Decimal("1.00")),
        w1.id, u1.id,
    )
    assert res.id is not None
    r = reread_inv(db, res.id)
    assert r.factory_id == f_in.id
    assert r.qty == 2
    assert len(ledger_rows(db, w1, f_in, i1, STORAGE)) == 1


@pytest.mark.xfail(strict=True, reason=BUG_710)
def test_inv_c_14__other_workspace_item_should_404(db, M, w1, w2, u1, f1, ix):
    """INV-C-14 — an item belonging to another workspace should raise 404 and write nothing.
    Rules: create_inventory R3 [BUG-710]; Errors row 2."""
    with pytest.raises(HTTPException) as exc:
        M.create_inventory(
            db, InventoryCreate(item_id=ix.id, inventory_type=STORAGE, factory_id=f1.id, qty=1),
            w1.id, u1.id,
        )
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_item(ix.id)
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(Inventory).where(Inventory.item_id == ix.id)) == 0
    assert ws_counts(db, w1) == (0, 0)


@pytest.mark.xfail(strict=True, reason=BUG_710)
def test_inv_c_15__missing_item_should_404_not_integrity_error(db, M, w1, u1, f1):
    """INV-C-15 — an unknown item id should raise 404, not a database FK error.
    Rules: create_inventory R3 [BUG-710]; Errors row 2."""
    missing = missing_id_for(db, Item)
    with pytest.raises(HTTPException) as exc:
        with db.begin_nested():
            M.create_inventory(
                db, InventoryCreate(item_id=missing, inventory_type=STORAGE, factory_id=f1.id, qty=1),
                w1.id, u1.id,
            )
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_item(missing)
    assert ws_counts(db, w1) == (0, 0)


@pytest.mark.xfail(strict=True, reason=BUG_711)
def test_inv_c_16__negative_qty_schema_should_reject(db, w1, i1, f1):
    """INV-C-16 — InventoryCreate should reject a negative qty.
    Rules: create_inventory R4 [BUG-711]; Errors row 3."""
    with pytest.raises(ValidationError):
        InventoryCreate(item_id=i1.id, inventory_type=STORAGE, factory_id=f1.id, qty=-1)
    assert inv_rows_for(db, w1, i1, STORAGE, f1) == []
    assert ledger_rows(db, w1, f1, i1, STORAGE) == []


def test_inv_c_17__zero_qty_zero_price_schema_builds(db, w1, i1, f1):
    """INV-C-17 — qty 0 / avg_price 0 build without error.
    Rules: create_inventory R4."""
    data = InventoryCreate(item_id=i1.id, inventory_type=STORAGE, factory_id=f1.id,
                            qty=0, avg_price=Decimal("0"))
    assert data.qty == 0
    assert data.avg_price == Decimal("0")


@pytest.mark.xfail(strict=True, reason=BUG_711)
def test_inv_c_18__negative_avg_price_schema_should_reject(db, w1, i1, f1):
    """INV-C-18 — InventoryCreate should reject a negative avg_price.
    Rules: create_inventory R4 [BUG-711]; Errors row 3."""
    with pytest.raises(ValidationError):
        InventoryCreate(item_id=i1.id, inventory_type=STORAGE, factory_id=f1.id,
                         qty=1, avg_price=Decimal("-0.01"))
    assert inv_rows_for(db, w1, i1, STORAGE, f1) == []
    assert ledger_rows(db, w1, f1, i1, STORAGE) == []


@pytest.mark.xfail(strict=True, reason=BUG_708)
def test_inv_c_19__too_many_decimals_schema_should_reject(db, w1, i1, f1):
    """INV-C-19 — InventoryCreate should reject avg_price with more than 2 decimals.
    Rules: create_inventory R4 [BUG-708]; Errors row 3."""
    with pytest.raises(ValidationError):
        InventoryCreate(item_id=i1.id, inventory_type=STORAGE, factory_id=f1.id,
                         qty=3, avg_price=Decimal("10.005"))
    assert inv_rows_for(db, w1, i1, STORAGE, f1) == []
    assert ledger_rows(db, w1, f1, i1, STORAGE) == []


def test_inv_c_20__avg_price_two_decimals_boundary(db, M, w1, u1, i1, f1):
    """INV-C-20 — avg_price with exactly 2 decimals stores and computes correctly.
    Rules: create_inventory R4."""
    res = M.create_inventory(
        db, InventoryCreate(item_id=i1.id, inventory_type=STORAGE, factory_id=f1.id,
                             qty=3, avg_price=Decimal("10.01")),
        w1.id, u1.id,
    )
    assert res.id is not None
    r = reread_inv(db, res.id)
    assert r.avg_price == Decimal("10.01")
    rows = ledger_rows(db, w1, f1, i1, STORAGE)
    assert_fields(rows[0], unit_cost=Decimal("10.01"), total_cost=Decimal("30.03"))


@pytest.mark.xfail(strict=True, reason=BUG_708)
def test_inv_c_21__too_many_integer_digits_schema_should_reject(db, w1, i1, f1):
    """INV-C-21 — InventoryCreate should reject avg_price with more than 13 integer digits.
    Rules: create_inventory R4 [BUG-708]; Errors row 3."""
    with pytest.raises(ValidationError):
        InventoryCreate(item_id=i1.id, inventory_type=STORAGE, factory_id=f1.id,
                         qty=1, avg_price=Decimal("10000000000000"))
    assert inv_rows_for(db, w1, i1, STORAGE, f1) == []
    assert ledger_rows(db, w1, f1, i1, STORAGE) == []


def test_inv_c_22__thirteen_integer_digits_boundary(db, M, w1, u1, i1, f1):
    """INV-C-22 — avg_price with exactly 13 integer digits stores and computes correctly.
    Rules: create_inventory R4."""
    res = M.create_inventory(
        db, InventoryCreate(item_id=i1.id, inventory_type=STORAGE, factory_id=f1.id,
                             qty=1, avg_price=Decimal("9999999999999.99")),
        w1.id, u1.id,
    )
    assert res.id is not None
    r = reread_inv(db, res.id)
    assert r.avg_price == Decimal("9999999999999.99")
    rows = ledger_rows(db, w1, f1, i1, STORAGE)
    assert_fields(rows[0], unit_cost=Decimal("9999999999999.99"), total_cost=Decimal("9999999999999.99"))


def test_inv_c_23__live_duplicate_409(db, M, w1, u1, i1, f1, inv):
    """INV-C-23 — a live duplicate for the same item/type/factory raises 409 and writes nothing.
    Rules: create_inventory R5; Errors row 4."""
    existing = inv(w1, i1, STORAGE, f1, 7, Decimal("2.00"), "existing")
    with pytest.raises(HTTPException) as exc:
        M.create_inventory(
            db, InventoryCreate(item_id=i1.id, inventory_type=STORAGE, factory_id=f1.id,
                                 qty=4, avg_price=Decimal("3.00"), note="new"),
            w1.id, u1.id,
        )
    assert exc.value.status_code == 409
    assert exc.value.detail == "Inventory record already exists for this item/type/factory combination"
    rows = inv_rows_for(db, w1, i1, STORAGE, f1)
    assert len(rows) == 1
    assert_fields(rows[0], qty=7, avg_price=Decimal("2.00"), note="existing", updated_by=None)
    assert ledger_rows(db, w1, f1, i1, STORAGE) == []
    assert rows[0].id == existing.id


def test_inv_c_24__other_workspace_duplicate_allowed(db, M, w1, w2, u1, i1, f1, inv):
    """INV-C-24 — a live row of the same key in another workspace does not block creation.
    Rules: create_inventory R5."""
    other = inv(w2, i1, STORAGE, f1, 7, Decimal("2.00"), "w2")
    res = M.create_inventory(
        db, InventoryCreate(item_id=i1.id, inventory_type=STORAGE, factory_id=f1.id, qty=4),
        w1.id, u1.id,
    )
    assert res.id != other.id
    assert res.workspace_id == w1.id
    assert res.qty == 4
    r = reread_inv(db, other.id)
    assert r.qty == 7
    assert r.note == "w2"
    db.expire_all()
    total = db.scalar(
        select(func.count()).select_from(Inventory).where(
            Inventory.item_id == i1.id, Inventory.inventory_type == STORAGE, Inventory.factory_id == f1.id,
        )
    )
    assert total == 2


def test_inv_c_25__other_factory_duplicate_allowed(db, M, w1, u1, i1, f1, f2, inv):
    """INV-C-25 — a live row for another factory does not block creation.
    Rules: create_inventory R5."""
    other = inv(w1, i1, STORAGE, f2, 7, Decimal("2.00"), "f2")
    res = M.create_inventory(
        db, InventoryCreate(item_id=i1.id, inventory_type=STORAGE, factory_id=f1.id, qty=4),
        w1.id, u1.id,
    )
    assert res.factory_id == f1.id
    assert res.qty == 4
    r = reread_inv(db, other.id)
    assert r.qty == 7


def test_inv_c_26__other_item_duplicate_allowed(db, M, w1, u1, i1, i2, f1, inv):
    """INV-C-26 — a live row for another item does not block creation.
    Rules: create_inventory R5."""
    other = inv(w1, i2, STORAGE, f1, 7, Decimal("2.00"), "i2")
    res = M.create_inventory(
        db, InventoryCreate(item_id=i1.id, inventory_type=STORAGE, factory_id=f1.id, qty=4),
        w1.id, u1.id,
    )
    assert res.item_id == i1.id
    assert res.qty == 4
    r = reread_inv(db, other.id)
    assert r.qty == 7


def test_inv_c_27__other_type_duplicate_allowed(db, M, w1, u1, i1, f1, inv):
    """INV-C-27 — a live row of another inventory_type does not block creation.
    Rules: create_inventory R5."""
    other = inv(w1, i1, DAMAGED, f1, 7, Decimal("2.00"), "dmg")
    res = M.create_inventory(
        db, InventoryCreate(item_id=i1.id, inventory_type=STORAGE, factory_id=f1.id, qty=4),
        w1.id, u1.id,
    )
    assert res.inventory_type == STORAGE
    assert res.qty == 4
    r = reread_inv(db, other.id)
    assert r.qty == 7


@pytest.mark.xfail(strict=True, reason=BUG_714)
def test_inv_c_28__soft_deleted_row_should_be_restored(db, M, w1, u1, u2, i1, f1, inv):
    """INV-C-28 — creating over a soft-deleted row should restore it, not raise IntegrityError.
    Rules: create_inventory R5 R6a R7 R8 [BUG-714]."""
    old = inv(w1, i1, STORAGE, f1, 7, Decimal("2.00"), "old",
              is_deleted=True, is_active=False, created_by=u2.id, updated_by=u2.id)
    old_created_at = reread_inv(db, old.id).created_at
    with db.begin_nested():
        res = M.create_inventory(
            db, InventoryCreate(item_id=i1.id, inventory_type=STORAGE, factory_id=f1.id,
                                 qty=4, avg_price=Decimal("3.00"), note="new"),
            w1.id, u1.id,
        )
    assert res.id == old.id
    rows = inv_rows_for(db, w1, i1, STORAGE, f1)
    assert len(rows) == 1
    r = rows[0]
    assert_fields(
        r, id=old.id, is_deleted=False, is_active=True, qty=4, avg_price=Decimal("3.00"),
        note="new", created_by=u2.id, created_at=old_created_at, updated_by=u1.id,
    )
    assert r.updated_at is not None
    ledger = ledger_rows(db, w1, f1, i1, STORAGE)
    assert len(ledger) == 1
    assert_fields(
        ledger[0], transaction_type="manual_add", quantity=4, qty_before=0, qty_after=4,
        unit_cost=Decimal("3.00"), total_cost=Decimal("12.00"), avg_price_before=None,
        avg_price_after=Decimal("3.00"), notes="Initial inventory record created", performed_by=u1.id,
    )


def test_inv_c_29__concurrent_duplicate_integrity_error(db, M, w1, u1, i1, f1, inv, race_rs1):
    """INV-C-29 — a race against a live duplicate raises IntegrityError, not HTTPException.
    Rules: create_inventory R9; Errors row 5."""
    inv(w1, i1, STORAGE, f1, 7, Decimal("2.00"), "existing")
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            M.create_inventory(
                db, InventoryCreate(item_id=i1.id, inventory_type=STORAGE, factory_id=f1.id, qty=4),
                w1.id, u1.id,
            )
    rows = inv_rows_for(db, w1, i1, STORAGE, f1)
    assert len(rows) == 1
    assert rows[0].qty == 7
    assert ledger_rows(db, w1, f1, i1, STORAGE) == []


def test_inv_c_30__inactive_catalog_item_accepted(db, M, w1, u1, f1):
    """INV-C-30 — an inactive catalog item is accepted on create.
    Rules: create_inventory R3a."""
    i_in = mk_item(db, w1, "Old Gasket", "pcs", active=False)
    res = M.create_inventory(
        db, InventoryCreate(item_id=i_in.id, inventory_type=STORAGE, factory_id=f1.id,
                             qty=2, avg_price=Decimal("1.00")),
        w1.id, u1.id,
    )
    assert res.id is not None
    r = reread_inv(db, res.id)
    assert r.item_id == i_in.id
    assert r.workspace_id == w1.id
    assert r.qty == 2
    assert r.avg_price == Decimal("1.00")
    assert len(ledger_rows(db, w1, f1, i_in, STORAGE)) == 1


# =========================================================================== #
# InventoryManager.update_inventory
# =========================================================================== #
# All cases use T unless stated; zero ledger rows before the call.

def test_inv_u_01__note_only_no_ledger(db, M, w1, u1, T):
    """INV-U-01 — updating only note writes no ledger entry.
    Rules: update_inventory R3 R8 R9."""
    res = M.update_inventory(db, T.id, InventoryUpdate(note="n2"), w1.id, u1.id)
    assert res.id == T.id
    r = reread_inv(db, T.id)
    assert_fields(r, note="n2", qty=10, avg_price=Decimal("5.00"), updated_by=u1.id,
                  workspace_id=w1.id, item_id=T.item_id, inventory_type=STORAGE, factory_id=T.factory_id)
    assert ledger_rows(db, w1, T.factory, T.item, STORAGE) == []


def test_inv_u_02__qty_increase_full_ledger_entry(db, M, w1, u1, T):
    """INV-U-02 — a qty increase writes a full inventory_adjustment ledger entry.
    Rules: update_inventory R3 R6 R7 R9."""
    res = M.update_inventory(db, T.id, InventoryUpdate(qty=12), w1.id, u1.id)
    assert res.id == T.id
    r = reread_inv(db, T.id)
    assert_fields(r, qty=12, avg_price=Decimal("5.00"), note="n1", updated_by=u1.id)
    rows = ledger_rows(db, w1, T.factory, T.item, STORAGE)
    assert len(rows) == 1
    assert_fields(
        rows[0], workspace_id=w1.id, inventory_type=STORAGE, factory_id=T.factory_id, item_id=T.item_id,
        transaction_type="inventory_adjustment", quantity=2, unit_cost=Decimal("5.00"),
        total_cost=Decimal("10.00"), qty_before=10, qty_after=12, avg_price_before=Decimal("5.00"),
        avg_price_after=Decimal("5.00"), source_type="adjustment",
        notes="Quantity adjusted from 10 to 12", performed_by=u1.id,
    )


def test_inv_u_03__qty_decrease_ledger_quantity_is_magnitude(db, M, w1, u1, T):
    """INV-U-03 — a qty decrease writes ledger quantity as the non-negative magnitude.
    Rules: update_inventory R7."""
    res = M.update_inventory(db, T.id, InventoryUpdate(qty=4), w1.id, u1.id)
    assert res.id == T.id
    assert reread_inv(db, T.id).qty == 4
    rows = ledger_rows(db, w1, T.factory, T.item, STORAGE)
    assert len(rows) == 1
    assert_fields(rows[0], quantity=6, qty_before=10, qty_after=4, unit_cost=Decimal("5.00"),
                  total_cost=Decimal("30.00"), notes="Quantity adjusted from 10 to 4")


def test_inv_u_04__qty_to_zero_boundary(db, M, w1, u1, T):
    """INV-U-04 — qty set to 0 writes a full-quantity ledger entry.
    Rules: update_inventory R4 R7."""
    res = M.update_inventory(db, T.id, InventoryUpdate(qty=0), w1.id, u1.id)
    assert res.id == T.id
    assert reread_inv(db, T.id).qty == 0
    rows = ledger_rows(db, w1, T.factory, T.item, STORAGE)
    assert len(rows) == 1
    assert_fields(rows[0], quantity=10, qty_before=10, qty_after=0, total_cost=Decimal("50.00"),
                  notes="Quantity adjusted from 10 to 0")


def test_inv_u_05__qty_and_price_change_single_ledger_entry(db, M, w1, u1, T):
    """INV-U-05 — changing qty and avg_price together writes one ledger entry, not two.
    Rules: update_inventory R3 R6 R7 R8."""
    res = M.update_inventory(db, T.id, InventoryUpdate(qty=12, avg_price=Decimal("6.00")), w1.id, u1.id)
    assert res.id == T.id
    r = reread_inv(db, T.id)
    assert_fields(r, qty=12, avg_price=Decimal("6.00"), note="n1", workspace_id=w1.id,
                  item_id=T.item_id, inventory_type=STORAGE, factory_id=T.factory_id)
    rows = ledger_rows(db, w1, T.factory, T.item, STORAGE)
    assert len(rows) == 1
    assert_fields(rows[0], quantity=2, unit_cost=Decimal("6.00"), total_cost=Decimal("12.00"),
                  qty_before=10, qty_after=12, avg_price_before=Decimal("5.00"),
                  avg_price_after=Decimal("6.00"))


def test_inv_u_06__qty_equal_to_current_no_ledger(db, M, w1, u1, T):
    """INV-U-06 — sending the current qty is a no-op, no ledger entry.
    Rules: update_inventory R6."""
    res = M.update_inventory(db, T.id, InventoryUpdate(qty=10), w1.id, u1.id)
    assert res.id == T.id
    r = reread_inv(db, T.id)
    assert r.qty == 10
    assert r.avg_price == Decimal("5.00")
    assert ledger_rows(db, w1, T.factory, T.item, STORAGE) == []


def test_inv_u_07__null_avg_price_qty_change_null_cost_fields(db, M, w1, u1, i1, f1, inv):
    """INV-U-07 — a qty change on a NULL-avg_price row writes NULL cost fields.
    Rules: update_inventory R7."""
    row = inv(w1, i1, STORAGE, f1, 10, None, "n1")
    res = M.update_inventory(db, row.id, InventoryUpdate(qty=12), w1.id, u1.id)
    assert res.id == row.id
    rows = ledger_rows(db, w1, f1, i1, STORAGE)
    assert len(rows) == 1
    assert_fields(rows[0], quantity=2, unit_cost=None, total_cost=None,
                  avg_price_before=None, avg_price_after=None, qty_after=12)


def test_inv_u_08__zero_avg_price_qty_change_ledger_fields(db, M, w1, u1, i1, f1, inv):
    """INV-U-08 — a qty change on a 0.00-avg_price row writes 0.00 cost fields (total_cost untested here).
    Rules: update_inventory R7."""
    row = inv(w1, i1, STORAGE, f1, 10, Decimal("0.00"), "n1")
    res = M.update_inventory(db, row.id, InventoryUpdate(qty=12), w1.id, u1.id)
    assert res.id == row.id
    rows = ledger_rows(db, w1, f1, i1, STORAGE)
    assert len(rows) == 1
    assert_fields(rows[0], quantity=2, unit_cost=Decimal("0.00"), avg_price_before=Decimal("0.00"),
                  avg_price_after=Decimal("0.00"), qty_after=12)


@pytest.mark.xfail(strict=True, reason=BUG_707)
def test_inv_u_09__zero_avg_price_total_cost_should_be_zero(db, M, w1, u1, i1, f1, inv):
    """INV-U-09 — a qty change on a 0.00-avg_price row should give ledger total_cost 0.00.
    Rules: update_inventory R7 [BUG-707]."""
    row = inv(w1, i1, STORAGE, f1, 10, Decimal("0.00"), "n1")
    res = M.update_inventory(db, row.id, InventoryUpdate(qty=12), w1.id, u1.id)
    assert res.id == row.id
    rows = ledger_rows(db, w1, f1, i1, STORAGE)
    assert rows[0].total_cost == Decimal("0.00")


def test_inv_u_10__avg_price_only_change(db, M, w1, u1, T):
    """INV-U-10 — changing only avg_price stores it and stamps updated_by.
    Rules: update_inventory R3 R9."""
    res = M.update_inventory(db, T.id, InventoryUpdate(avg_price=Decimal("6.00")), w1.id, u1.id)
    assert res.id == T.id
    r = reread_inv(db, T.id)
    assert_fields(r, avg_price=Decimal("6.00"), qty=10, note="n1", updated_by=u1.id)


@pytest.mark.xfail(strict=True, reason=BUG_712)
def test_inv_u_11__avg_price_only_should_write_ledger(db, M, w1, u1, T):
    """INV-U-11 — an avg_price-only change should write a full R6a ledger entry.
    Rules: update_inventory R6 R6a [BUG-712]."""
    res = M.update_inventory(db, T.id, InventoryUpdate(avg_price=Decimal("6.00")), w1.id, u1.id)
    assert res.id == T.id
    rows = ledger_rows(db, w1, T.factory, T.item, STORAGE)
    assert len(rows) == 1
    assert_fields(
        rows[0], workspace_id=w1.id, inventory_type=STORAGE, factory_id=T.factory_id, item_id=T.item_id,
        transaction_type="inventory_adjustment", quantity=0, qty_before=10, qty_after=10,
        unit_cost=Decimal("6.00"), total_cost=Decimal("0.00"), avg_price_before=Decimal("5.00"),
        avg_price_after=Decimal("6.00"), source_type="adjustment", source_id=None,
        notes="Average price adjusted from 5.00 to 6.00", performed_by=u1.id,
    )


@pytest.mark.xfail(strict=True, reason=BUG_712)
def test_inv_u_12__unchanged_qty_sent_with_new_price_should_write_ledger(db, M, w1, u1, T):
    """INV-U-12 — qty sent but unchanged, with a new avg_price, should write a full R6a ledger entry.
    Rules: update_inventory R6 R6a [BUG-712]."""
    res = M.update_inventory(db, T.id, InventoryUpdate(qty=10, avg_price=Decimal("6.00")), w1.id, u1.id)
    assert res.id == T.id
    rows = ledger_rows(db, w1, T.factory, T.item, STORAGE)
    assert len(rows) == 1
    assert_fields(
        rows[0], transaction_type="inventory_adjustment", quantity=0, qty_before=10, qty_after=10,
        unit_cost=Decimal("6.00"), total_cost=Decimal("0.00"), avg_price_before=Decimal("5.00"),
        avg_price_after=Decimal("6.00"), source_type="adjustment",
        notes="Average price adjusted from 5.00 to 6.00", performed_by=u1.id,
    )


def test_inv_u_13__avg_price_equal_to_current_no_ledger(db, M, w1, u1, T):
    """INV-U-13 — sending the current avg_price is a no-op, no ledger entry.
    Rules: update_inventory R6."""
    res = M.update_inventory(db, T.id, InventoryUpdate(avg_price=Decimal("5.00")), w1.id, u1.id)
    assert res.id == T.id
    r = reread_inv(db, T.id)
    assert r.avg_price == Decimal("5.00")
    assert r.qty == 10
    assert ledger_rows(db, w1, T.factory, T.item, STORAGE) == []


@pytest.mark.xfail(strict=True, reason=BUG_703)
def test_inv_u_14__empty_update_should_not_stamp_updated_by(db, M, w1, u1, T):
    """INV-U-14 — an empty update should leave updated_by NULL.
    Rules: update_inventory R9 [BUG-703]."""
    res = M.update_inventory(db, T.id, InventoryUpdate(), w1.id, u1.id)
    assert res.id == T.id
    assert reread_inv(db, T.id).updated_by is None


def test_inv_u_15__empty_update_leaves_fields_unchanged(db, M, w1, u1, T):
    """INV-U-15 — an empty update leaves qty/avg_price/note unchanged and writes no ledger.
    Rules: update_inventory R3."""
    res = M.update_inventory(db, T.id, InventoryUpdate(), w1.id, u1.id)
    assert res.id == T.id
    r = reread_inv(db, T.id)
    assert_fields(r, qty=10, avg_price=Decimal("5.00"), note="n1")
    assert ledger_rows(db, w1, T.factory, T.item, STORAGE) == []


@pytest.mark.xfail(strict=True, reason=BUG_703)
def test_inv_u_16__all_fields_equal_to_stored_should_not_stamp_updated_by(db, M, w1, u1, T):
    """INV-U-16 — sending all fields equal to the stored values should leave updated_by NULL.
    Rules: update_inventory R9 [BUG-703]."""
    res = M.update_inventory(
        db, T.id, InventoryUpdate(qty=10, avg_price=Decimal("5.00"), note="n1"), w1.id, u1.id,
    )
    assert res.id == T.id
    assert reread_inv(db, T.id).updated_by is None


def test_inv_u_17__missing_id_404(db, M, w1, u1, T):
    """INV-U-17 — an unknown inventory id raises 404 and changes nothing.
    Rules: update_inventory R1; Errors row 1."""
    missing = missing_id_for(db, Inventory)
    with pytest.raises(HTTPException) as exc:
        M.update_inventory(db, missing, InventoryUpdate(qty=12), w1.id, u1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_inv(missing)
    r = reread_inv(db, T.id)
    assert_fields(r, qty=10, avg_price=Decimal("5.00"), note="n1", updated_by=None)
    assert ws_counts(db, w1)[1] == 0


def test_inv_u_18__other_workspace_404(db, M, w1, w2, u1, TX):
    """INV-U-18 — another workspace's inventory id is reported as not found.
    Rules: update_inventory R1; Errors row 1."""
    with pytest.raises(HTTPException) as exc:
        M.update_inventory(db, TX.id, InventoryUpdate(qty=12), w1.id, u1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_inv(TX.id)
    r = reread_inv(db, TX.id)
    assert r.qty == 10
    assert r.note == "x1"
    assert r.updated_by is None
    assert ws_counts(db, w1)[1] == 0
    assert ws_counts(db, w2)[1] == 0


def test_inv_u_19__deleted_row_400(db, M, w1, u1, TD):
    """INV-U-19 — updating a soft-deleted row raises 400 and changes nothing.
    Rules: update_inventory R2; Errors row 2."""
    with pytest.raises(HTTPException) as exc:
        M.update_inventory(db, TD.id, InventoryUpdate(qty=12, note="z"), w1.id, u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Cannot update a deleted inventory record"
    r = reread_inv(db, TD.id)
    assert_fields(r, qty=10, note="n1", is_deleted=True, updated_by=None)
    assert ledger_rows(db, w1, TD.factory, TD.item, STORAGE) == []


@pytest.mark.xfail(strict=True, reason=BUG_711)
def test_inv_u_20__negative_qty_schema_should_reject(db, w1, T):
    """INV-U-20 — InventoryUpdate should reject a negative qty.
    Rules: update_inventory R4 [BUG-711]; Errors row 3."""
    with pytest.raises(ValidationError):
        InventoryUpdate(qty=-1)
    # Schema "nothing written" convention conflicts with Given T existing;
    # read as "T unchanged and zero ledger rows for the bucket" (best-practice
    # default, delegated by reviewer).
    r = reread_inv(db, T.id)
    assert_fields(r, qty=10, avg_price=Decimal("5.00"), note="n1", updated_by=None)
    assert ledger_rows(db, w1, T.factory, T.item, STORAGE) == []


def test_inv_u_21__zero_qty_zero_price_schema_builds(db):
    """INV-U-21 — qty 0 / avg_price 0 build without error.
    Rules: update_inventory R4."""
    data = InventoryUpdate(qty=0, avg_price=Decimal("0"))
    assert data.qty == 0
    assert data.avg_price == Decimal("0")


@pytest.mark.xfail(strict=True, reason=BUG_711)
def test_inv_u_22__negative_avg_price_schema_should_reject(db, w1, i1, f1):
    """INV-U-22 — InventoryUpdate should reject a negative avg_price.
    Rules: update_inventory R4 [BUG-711]; Errors row 3."""
    with pytest.raises(ValidationError):
        InventoryUpdate(avg_price=Decimal("-0.01"))
    assert inv_rows_for(db, w1, i1, STORAGE, f1) == []
    assert ledger_rows(db, w1, f1, i1, STORAGE) == []


@pytest.mark.xfail(strict=True, reason=BUG_708)
def test_inv_u_23__too_many_decimals_schema_should_reject(db, w1, i1, f1):
    """INV-U-23 — InventoryUpdate should reject avg_price with more than 2 decimals.
    Rules: update_inventory R4 [BUG-708]; Errors row 3."""
    with pytest.raises(ValidationError):
        InventoryUpdate(avg_price=Decimal("10.005"))
    assert inv_rows_for(db, w1, i1, STORAGE, f1) == []
    assert ledger_rows(db, w1, f1, i1, STORAGE) == []


@pytest.mark.xfail(strict=True, reason=BUG_708)
def test_inv_u_24__too_many_integer_digits_schema_should_reject(db, w1, i1, f1):
    """INV-U-24 — InventoryUpdate should reject avg_price with more than 13 integer digits.
    Rules: update_inventory R4 [BUG-708]; Errors row 3."""
    with pytest.raises(ValidationError):
        InventoryUpdate(avg_price=Decimal("10000000000000"))
    assert inv_rows_for(db, w1, i1, STORAGE, f1) == []
    assert ledger_rows(db, w1, f1, i1, STORAGE) == []


def test_inv_u_25__avg_price_two_decimals_boundary(db, M, w1, u1, T):
    """INV-U-25 — avg_price with exactly 2 decimals stores and computes correctly.
    Rules: update_inventory R4 R7."""
    res = M.update_inventory(db, T.id, InventoryUpdate(qty=11, avg_price=Decimal("10.01")), w1.id, u1.id)
    assert res.id == T.id
    r = reread_inv(db, T.id)
    assert r.avg_price == Decimal("10.01")
    assert r.qty == 11
    rows = ledger_rows(db, w1, T.factory, T.item, STORAGE)
    assert_fields(rows[0], unit_cost=Decimal("10.01"), quantity=1, total_cost=Decimal("10.01"))


def test_inv_u_26__thirteen_integer_digits_boundary(db, M, w1, u1, T):
    """INV-U-26 — avg_price with exactly 13 integer digits stores and computes correctly.
    Rules: update_inventory R4 R7."""
    res = M.update_inventory(
        db, T.id, InventoryUpdate(qty=11, avg_price=Decimal("9999999999999.99")), w1.id, u1.id,
    )
    assert res.id == T.id
    r = reread_inv(db, T.id)
    assert r.avg_price == Decimal("9999999999999.99")
    rows = ledger_rows(db, w1, T.factory, T.item, STORAGE)
    assert_fields(rows[0], unit_cost=Decimal("9999999999999.99"), total_cost=Decimal("9999999999999.99"))


@pytest.mark.xfail(strict=True, reason=BUG_713)
def test_inv_u_27__explicit_null_note_should_clear(db, M, w1, u1, T):
    """INV-U-27 — note=None (explicit) should clear the stored note.
    Rules: update_inventory R5 [BUG-713]."""
    res = M.update_inventory(db, T.id, InventoryUpdate(note=None), w1.id, u1.id)
    assert res.id == T.id
    assert reread_inv(db, T.id).note is None


@pytest.mark.xfail(strict=True, reason=BUG_713)
def test_inv_u_28__explicit_null_avg_price_should_clear_and_log(db, M, w1, u1, T):
    """INV-U-28 — avg_price=None (explicit) should clear the price and write a full ledger entry.
    Rules: update_inventory R5 R6 R6a [BUG-713][BUG-712]."""
    res = M.update_inventory(db, T.id, InventoryUpdate(avg_price=None), w1.id, u1.id)
    assert res.id == T.id
    r = reread_inv(db, T.id)
    assert r.avg_price is None
    assert r.qty == 10
    rows = ledger_rows(db, w1, T.factory, T.item, STORAGE)
    assert len(rows) == 1
    assert_fields(
        rows[0], transaction_type="inventory_adjustment", quantity=0, qty_before=10, qty_after=10,
        unit_cost=None, total_cost=None, avg_price_before=Decimal("5.00"), avg_price_after=None,
        source_type="adjustment", notes="Average price adjusted from 5.00 to None", performed_by=u1.id,
    )


@pytest.mark.xfail(strict=True, reason=BUG_713)
def test_inv_u_29__explicit_null_qty_should_422(db, M, w1, u1, T):
    """INV-U-29 — qty=None (explicit) should raise 422, not silently keep the current qty.
    Rules: update_inventory R5 [BUG-713]; Errors row 4."""
    with pytest.raises(HTTPException) as exc:
        M.update_inventory(db, T.id, InventoryUpdate(qty=None, note="changed"), w1.id, u1.id)
    assert exc.value.status_code == 422
    assert exc.value.detail == "qty cannot be empty"
    r = reread_inv(db, T.id)
    assert_fields(r, qty=10, note="n1", updated_by=None)
    assert ledger_rows(db, w1, T.factory, T.item, STORAGE) == []


@pytest.mark.xfail(strict=True, reason=BUG_704)
def test_inv_u_30__qty_change_should_lock_row(db, M, w1, u1, T):
    """INV-U-30 — a qty change should issue a locked SELECT ... FOR UPDATE OF inventory.
    Rules: update_inventory R10 [BUG-704]."""
    with SQLCapture(db) as cap:
        res = M.update_inventory(db, T.id, InventoryUpdate(qty=12), w1.id, u1.id)
    assert res.id == T.id
    assert locked_read_of_inventory(cap.statements)
    assert no_nowait_or_skip_locked(cap.statements)


def test_inv_u_31__already_null_avg_price_explicit_null_noop(db, M, w1, u1, i1, f1, inv):
    """INV-U-31 — avg_price=None on an already-NULL row is a no-op, no ledger entry.
    Rules: update_inventory R5 R6a."""
    row = inv(w1, i1, STORAGE, f1, 10, None, "n1")
    res = M.update_inventory(db, row.id, InventoryUpdate(avg_price=None), w1.id, u1.id)
    assert res.id == row.id
    r = reread_inv(db, row.id)
    assert r.avg_price is None
    assert r.qty == 10
    assert r.note == "n1"
    assert ledger_rows(db, w1, f1, i1, STORAGE) == []


@pytest.mark.xfail(strict=True, reason=BUG_712)
def test_inv_u_32__price_from_null_should_write_ledger_with_none_text(db, M, w1, u1, i1, f1, inv):
    """INV-U-32 — avg_price change from NULL should write a full ledger entry with 'None' in the notes text.
    Rules: update_inventory R6 R6a [BUG-712]."""
    row = inv(w1, i1, STORAGE, f1, 10, None, "n1")
    res = M.update_inventory(db, row.id, InventoryUpdate(avg_price=Decimal("6.00")), w1.id, u1.id)
    assert res.id == row.id
    r = reread_inv(db, row.id)
    assert r.avg_price == Decimal("6.00")
    rows = ledger_rows(db, w1, f1, i1, STORAGE)
    assert len(rows) == 1
    assert_fields(
        rows[0], transaction_type="inventory_adjustment", quantity=0, qty_before=10, qty_after=10,
        unit_cost=Decimal("6.00"), total_cost=Decimal("0.00"), avg_price_before=None,
        avg_price_after=Decimal("6.00"), source_type="adjustment",
        notes="Average price adjusted from None to 6.00", performed_by=u1.id,
    )


# =========================================================================== #
# InventoryManager.get_inventory
# =========================================================================== #

def test_inv_g_01__get_live_row(db, M, w1, T):
    """INV-G-01 — a live row of the workspace is returned.
    Rules: get_inventory R1."""
    res = M.get_inventory(db, T.id, w1.id)
    assert res.id == T.id
    assert res.qty == 10
    assert res.workspace_id == w1.id


def test_inv_g_02__zero_qty_row(db, M, w1, i1, f1, inv):
    """INV-G-02 — a zero-qty row is returned normally.
    Rules: get_inventory R1."""
    row = inv(w1, i1, STORAGE, f1, 0, None, None)
    res = M.get_inventory(db, row.id, w1.id)
    assert res.id == row.id
    assert res.qty == 0


def test_inv_g_03__negative_qty_row(db, M, w1, i1, f1, inv):
    """INV-G-03 — a negative-qty row is returned normally.
    Rules: get_inventory R1."""
    row = inv(w1, i1, STORAGE, f1, -3, None, None)
    res = M.get_inventory(db, row.id, w1.id)
    assert res.id == row.id
    assert res.qty == -3


def test_inv_g_04__missing_id_404(db, M, w1, T):
    """INV-G-04 — an unknown id raises 404; W1 row counts unchanged.
    Rules: get_inventory R2; Errors row 1."""
    missing = missing_id_for(db, Inventory)
    before = ws_counts(db, w1)
    with pytest.raises(HTTPException) as exc:
        M.get_inventory(db, missing, w1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_inv(missing)
    assert ws_counts(db, w1) == before


def test_inv_g_05__other_workspace_404(db, M, w1, TX):
    """INV-G-05 — another workspace's row is reported as not found.
    Rules: get_inventory R2; Errors row 1."""
    before = ws_counts(db, w1)
    with pytest.raises(HTTPException) as exc:
        M.get_inventory(db, TX.id, w1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_inv(TX.id)
    assert ws_counts(db, w1) == before


@pytest.mark.xfail(strict=True, reason=BUG_700)
def test_inv_g_06__missing_id_with_include_deleted(db, M, w1, T):
    """INV-G-06 — include_deleted=True on an unknown id should still raise 404.
    Rules: get_inventory R2 [BUG-700]."""
    missing = missing_id_for(db, Inventory)
    before = ws_counts(db, w1)
    with pytest.raises(HTTPException) as exc:
        M.get_inventory(db, missing, w1.id, include_deleted=True)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_inv(missing)
    assert ws_counts(db, w1) == before


@pytest.mark.xfail(strict=True, reason=BUG_700)
def test_inv_g_07__other_workspace_with_include_deleted(db, M, w1, TX):
    """INV-G-07 — include_deleted=True does not break workspace isolation.
    Rules: get_inventory R2 [BUG-700]."""
    before = ws_counts(db, w1)
    with pytest.raises(HTTPException) as exc:
        M.get_inventory(db, TX.id, w1.id, include_deleted=True)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_inv(TX.id)
    assert ws_counts(db, w1) == before


@pytest.mark.xfail(strict=True, reason=BUG_700)
def test_inv_g_08__deleted_row_should_404_by_default(db, M, w1, TD):
    """INV-G-08 — a soft-deleted row should not be found by default.
    Rules: get_inventory R3 [BUG-700]; Errors row 1."""
    before = ws_counts(db, w1)
    with pytest.raises(HTTPException) as exc:
        M.get_inventory(db, TD.id, w1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_inv(TD.id)
    assert ws_counts(db, w1) == before


@pytest.mark.xfail(strict=True, reason=BUG_700)
def test_inv_g_09__include_deleted_should_return_deleted(db, M, w1, TD):
    """INV-G-09 — include_deleted=True should return a soft-deleted row.
    Rules: get_inventory R4 [BUG-700]."""
    res = M.get_inventory(db, TD.id, w1.id, include_deleted=True)
    assert res.id == TD.id
    assert res.is_deleted is True


# =========================================================================== #
# InventoryManager.get_inventory_page
# =========================================================================== #
# Unless stated, rows are STORAGE in F1 with qty 5 and avg_price 1.00; items
# named in the row are created in W1 with unit "pcs".

def _prow(inv, ws, item, *, factory, qty=5, avg_price=Decimal("1.00"), **kw):
    return inv(ws, item, STORAGE, factory, qty, avg_price, None, **kw)


def test_inv_p_01__defaults_exclude_deleted_and_other_workspace(db, M, w1, w2, f1, fx, inv):
    """INV-P-01 — defaults list live W1 rows only, with total/skip/limit/has_more.
    Rules: get_inventory_page R1 R7 R8."""
    anchor = mk_item(db, w1, "Anchor")
    bolt = mk_item(db, w1, "Bolt")
    cable = mk_item(db, w1, "Cable")
    anvil = mk_item(db, w2, "Anvil")
    a = _prow(inv, w1, anchor, factory=f1, qty=5)
    b = _prow(inv, w1, bolt, factory=f1, qty=3)
    _prow(inv, w1, cable, factory=f1, qty=4, is_deleted=True)
    _prow(inv, w2, anvil, factory=fx, qty=9)
    res = M.get_inventory_page(db, workspace_id=w1.id)
    assert page_ids(res) == [a.id, b.id]
    assert res.total == 2
    assert res.skip == 0
    assert res.limit == 50
    assert res.has_more is False


def test_inv_p_02__inventory_type_filter(db, M, w1, f1, inv):
    """INV-P-02 — inventory_type filters to that type only.
    Rules: get_inventory_page R2."""
    anchor = mk_item(db, w1, "Anchor")
    _prow(inv, w1, anchor, factory=f1)
    b = inv(w1, anchor, DAMAGED, f1, 5, Decimal("1.00"), None)
    res = M.get_inventory_page(db, workspace_id=w1.id, inventory_type=DAMAGED)
    assert page_ids(res) == [b.id]
    assert res.total == 1


def test_inv_p_03__factory_filter(db, M, w1, f1, f2, inv):
    """INV-P-03 — factory_id filters to that factory only.
    Rules: get_inventory_page R2."""
    anchor = mk_item(db, w1, "Anchor")
    _prow(inv, w1, anchor, factory=f1)
    b = _prow(inv, w1, anchor, factory=f2)
    res = M.get_inventory_page(db, workspace_id=w1.id, factory_id=f2.id)
    assert page_ids(res) == [b.id]
    assert res.total == 1


def test_inv_p_04__factory_zero_is_no_filter(db, M, w1, f1, f2, inv):
    """INV-P-04 — factory_id=0 applies no factory filter.
    Rules: get_inventory_page R2."""
    anchor = mk_item(db, w1, "Anchor")
    a = _prow(inv, w1, anchor, factory=f1)
    b = _prow(inv, w1, anchor, factory=f2)
    res = M.get_inventory_page(db, workspace_id=w1.id, factory_id=0)
    assert page_ids(res) == [a.id, b.id]
    assert res.total == 2


def test_inv_p_05__item_filter(db, M, w1, f1, inv):
    """INV-P-05 — item_id filters to that item only.
    Rules: get_inventory_page R2."""
    anchor = mk_item(db, w1, "Anchor")
    bolt = mk_item(db, w1, "Bolt")
    _prow(inv, w1, anchor, factory=f1)
    b = _prow(inv, w1, bolt, factory=f1)
    res = M.get_inventory_page(db, workspace_id=w1.id, item_id=bolt.id)
    assert page_ids(res) == [b.id]
    assert res.total == 1


def test_inv_p_06__item_zero_matches_nothing(db, M, w1, f1, inv):
    """INV-P-06 — item_id=0 is used literally and matches no rows.
    Rules: get_inventory_page R2."""
    anchor = mk_item(db, w1, "Anchor")
    bolt = mk_item(db, w1, "Bolt")
    _prow(inv, w1, anchor, factory=f1)
    _prow(inv, w1, bolt, factory=f1)
    res = M.get_inventory_page(db, workspace_id=w1.id, item_id=0)
    assert page_ids(res) == []
    assert res.total == 0
    assert res.has_more is False


def test_inv_p_07__filters_combine(db, M, w1, f1, f2, inv):
    """INV-P-07 — inventory_type, factory_id and item_id combine with AND.
    Rules: get_inventory_page R2."""
    anchor = mk_item(db, w1, "Anchor")
    bolt = mk_item(db, w1, "Bolt")
    a = _prow(inv, w1, anchor, factory=f1)
    inv(w1, anchor, DAMAGED, f1, 5, Decimal("1.00"), None)
    _prow(inv, w1, anchor, factory=f2)
    _prow(inv, w1, bolt, factory=f1)
    res = M.get_inventory_page(db, workspace_id=w1.id, inventory_type=STORAGE,
                                factory_id=f1.id, item_id=anchor.id)
    assert page_ids(res) == [a.id]
    assert res.total == 1


def test_inv_p_08__zero_and_negative_qty_excluded_by_default(db, M, w1, f1, inv):
    """INV-P-08 — zero/negative qty rows are excluded by default.
    Rules: get_inventory_page R3."""
    anchor = mk_item(db, w1, "Anchor")
    bolt = mk_item(db, w1, "Bolt")
    cable = mk_item(db, w1, "Cable")
    a = _prow(inv, w1, anchor, factory=f1, qty=1)
    _prow(inv, w1, bolt, factory=f1, qty=0)
    _prow(inv, w1, cable, factory=f1, qty=-2)
    res = M.get_inventory_page(db, workspace_id=w1.id)
    assert page_ids(res) == [a.id]
    assert res.total == 1


def test_inv_p_09__include_zero_qty_includes_all(db, M, w1, f1, inv):
    """INV-P-09 — include_zero_qty=True includes zero and negative qty rows.
    Rules: get_inventory_page R3."""
    anchor = mk_item(db, w1, "Anchor")
    bolt = mk_item(db, w1, "Bolt")
    cable = mk_item(db, w1, "Cable")
    a = _prow(inv, w1, anchor, factory=f1, qty=1)
    z = _prow(inv, w1, bolt, factory=f1, qty=0)
    n = _prow(inv, w1, cable, factory=f1, qty=-2)
    res = M.get_inventory_page(db, workspace_id=w1.id, include_zero_qty=True)
    assert page_ids(res) == [a.id, z.id, n.id]
    assert res.total == 3


def test_inv_p_10__ordered_by_item_name(db, M, w1, f1, inv):
    """INV-P-10 — results are ordered by item name, not creation order.
    Rules: get_inventory_page R4."""
    cable = mk_item(db, w1, "cable")
    anchor = mk_item(db, w1, "anchor")
    bolt = mk_item(db, w1, "bolt")
    c = _prow(inv, w1, cable, factory=f1)
    a = _prow(inv, w1, anchor, factory=f1)
    b = _prow(inv, w1, bolt, factory=f1)
    res = M.get_inventory_page(db, workspace_id=w1.id)
    assert page_ids(res) == [a.id, b.id, c.id]


def test_inv_p_11__same_name_tie_broken_by_inventory_id(db, M, w1, f1, f2, inv):
    """INV-P-11 — rows of the same item name are ordered by inventory id.
    Rules: get_inventory_page R4."""
    anchor = mk_item(db, w1, "Anchor")
    r1 = _prow(inv, w1, anchor, factory=f1, qty=5)
    r2 = inv(w1, anchor, DAMAGED, f1, 5, Decimal("1.00"), None)
    r3 = inv(w1, anchor, SCRAP, f2, 5, Decimal("1.00"), None)
    res = M.get_inventory_page(db, workspace_id=w1.id)
    assert page_ids(res) == [r1.id, r2.id, r3.id]


@pytest.mark.xfail(strict=True, reason=BUG_701)
def test_inv_p_12__case_only_name_tie_should_sort_by_inventory_id(db, M, w1, f1, inv):
    """INV-P-12 — "Apple" and "apple" (case-only tie) should order by inventory id ascending.
    Rules: get_inventory_page R4 [BUG-701]."""
    apple_cap = mk_item(db, w1, "Apple")
    apple_low = mk_item(db, w1, "apple")
    r_cap = _prow(inv, w1, apple_cap, factory=f1)
    r_low = _prow(inv, w1, apple_low, factory=f1)
    assert r_cap.id < r_low.id
    res = M.get_inventory_page(db, workspace_id=w1.id)
    assert page_ids(res) == [r_cap.id, r_low.id]


def test_inv_p_13__skip_and_limit_middle_page(db, M, w1, f1, inv):
    """INV-P-13 — skip/limit return a middle page with correct total/has_more.
    Rules: get_inventory_page R5 R7 R8."""
    items = [mk_item(db, w1, f"Item {c}") for c in "ABCDE"]
    rows = [_prow(inv, w1, it, factory=f1) for it in items]
    res = M.get_inventory_page(db, workspace_id=w1.id, skip=1, limit=2)
    assert page_ids(res) == [rows[1].id, rows[2].id]
    assert res.total == 5
    assert res.skip == 1
    assert res.limit == 2
    assert res.has_more is True


def test_inv_p_14__skip_and_limit_last_page(db, M, w1, f1, inv):
    """INV-P-14 — skip + limit landing exactly on the end gives has_more False.
    Rules: get_inventory_page R5 R8."""
    items = [mk_item(db, w1, f"Item {c}") for c in "ABCDE"]
    rows = [_prow(inv, w1, it, factory=f1) for it in items]
    res = M.get_inventory_page(db, workspace_id=w1.id, skip=3, limit=2)
    assert page_ids(res) == [rows[3].id, rows[4].id]
    assert res.total == 5
    assert res.has_more is False


def test_inv_p_15__skip_past_end_empty_page(db, M, w1, f1, inv):
    """INV-P-15 — skip past the end returns an empty page, has_more False.
    Rules: get_inventory_page R5 R8."""
    items = [mk_item(db, w1, f"Item {c}") for c in "ABCDE"]
    for it in items:
        _prow(inv, w1, it, factory=f1)
    res = M.get_inventory_page(db, workspace_id=w1.id, skip=5, limit=2)
    assert page_ids(res) == []
    assert res.total == 5
    assert res.skip == 5
    assert res.has_more is False


def test_inv_p_16__zero_qty_excluded_before_paging(db, M, w1, f1, inv):
    """INV-P-16 — zero-qty rows are excluded before skip/limit is applied.
    Rules: get_inventory_page R3 R5 R7."""
    items = [mk_item(db, w1, f"Item {c}") for c in "ABCD"]
    a_row = _prow(inv, w1, items[0], factory=f1, qty=0)
    others = [_prow(inv, w1, it, factory=f1, qty=1) for it in items[1:]]
    res = M.get_inventory_page(db, workspace_id=w1.id, skip=0, limit=2)
    assert page_ids(res) == [others[0].id, others[1].id]
    assert res.total == 3
    assert res.has_more is True
    assert a_row.id not in page_ids(res)


def _p17_setup(db, w1, w2, f1, fx, inv):
    """Setup of INV-P-17..P-22: H=Hex Bolt, N=Nut (pkgs), plus a soft-deleted
    Hex Bolt row and a W2 "Hex Bolt Foreign" row that must never match."""
    hex_bolt = mk_item(db, w1, "Hex Bolt")
    nut = mk_item(db, w1, "Nut", "pkgs")
    hex_bolt_foreign = mk_item(db, w2, "Hex Bolt Foreign")
    h = _prow(inv, w1, hex_bolt, factory=f1)
    n = _prow(inv, w1, nut, factory=f1)
    # HD = Hex Bolt DAMAGED soft-deleted (DAMAGED, not STORAGE, per the cases
    # file row: same (ws, item, factory) as H would violate the unique
    # constraint on (workspace_id, item_id, inventory_type, factory_id),
    # which applies regardless of is_deleted — see Conventions re: T/TD).
    inv(w1, hex_bolt, DAMAGED, f1, 5, Decimal("1.00"), None, is_deleted=True)
    _prow(inv, w2, hex_bolt_foreign, factory=fx)
    return h, n


def test_inv_p_17__search_matches_item_name(db, M, w1, w2, f1, fx, inv):
    """INV-P-17 — search matches the item name, excludes deleted rows and other workspaces.
    Rules: get_inventory_page R1 R6."""
    h, _n = _p17_setup(db, w1, w2, f1, fx, inv)
    res = M.get_inventory_page(db, workspace_id=w1.id, search="X BO")
    assert page_ids(res) == [h.id]
    assert res.total == 1


def test_inv_p_18__search_matches_item_unit(db, M, w1, w2, f1, fx, inv):
    """INV-P-18 — search matches the item unit, not just the name.
    Rules: get_inventory_page R6."""
    _h, n = _p17_setup(db, w1, w2, f1, fx, inv)
    res = M.get_inventory_page(db, workspace_id=w1.id, search="KG")
    assert page_ids(res) == [n.id]
    assert res.total == 1


def test_inv_p_19__search_trimmed(db, M, w1, w2, f1, fx, inv):
    """INV-P-19 — padded search text is trimmed before matching.
    Rules: get_inventory_page R6."""
    _h, n = _p17_setup(db, w1, w2, f1, fx, inv)
    res = M.get_inventory_page(db, workspace_id=w1.id, search="  nut  ")
    assert page_ids(res) == [n.id]
    assert res.total == 1


def test_inv_p_20__whitespace_search_is_no_filter(db, M, w1, w2, f1, fx, inv):
    """INV-P-20 — whitespace-only search applies no filter.
    Rules: get_inventory_page R6."""
    h, n = _p17_setup(db, w1, w2, f1, fx, inv)
    res = M.get_inventory_page(db, workspace_id=w1.id, search="   ")
    assert page_ids(res) == [h.id, n.id]
    assert res.total == 2


def test_inv_p_21__empty_search_is_no_filter(db, M, w1, w2, f1, fx, inv):
    """INV-P-21 — search="" applies no filter.
    Rules: get_inventory_page R6."""
    h, n = _p17_setup(db, w1, w2, f1, fx, inv)
    res = M.get_inventory_page(db, workspace_id=w1.id, search="")
    assert page_ids(res) == [h.id, n.id]
    assert res.total == 2


def test_inv_p_22__search_no_match(db, M, w1, w2, f1, fx, inv):
    """INV-P-22 — a search with no match returns an empty page.
    Rules: get_inventory_page R6."""
    _p17_setup(db, w1, w2, f1, fx, inv)
    res = M.get_inventory_page(db, workspace_id=w1.id, search="zzz")
    assert page_ids(res) == []
    assert res.total == 0
    assert res.has_more is False


@pytest.mark.xfail(strict=True, reason=BUG_702)
def test_inv_p_23__percent_should_be_literal(db, M, w1, f1, inv):
    """INV-P-23 — "%" in search should match only a literal percent sign.
    Rules: get_inventory_page R6 [BUG-702]."""
    cotton = mk_item(db, w1, "100% Cotton")
    blend = mk_item(db, w1, "Cotton Blend")
    c = _prow(inv, w1, cotton, factory=f1)
    _prow(inv, w1, blend, factory=f1)
    res = M.get_inventory_page(db, workspace_id=w1.id, search="%")
    assert page_ids(res) == [c.id]
    assert res.total == 1


@pytest.mark.xfail(strict=True, reason=BUG_702)
def test_inv_p_24__underscore_should_be_literal(db, M, w1, f1, inv):
    """INV-P-24 — "_" in search should match only a literal underscore.
    Rules: get_inventory_page R6 [BUG-702]."""
    a_b = mk_item(db, w1, "A_B Bracket")
    axb = mk_item(db, w1, "AXB Bracket")
    r = _prow(inv, w1, a_b, factory=f1)
    _prow(inv, w1, axb, factory=f1)
    res = M.get_inventory_page(db, workspace_id=w1.id, search="_")
    assert page_ids(res) == [r.id]
    assert res.total == 1


@pytest.mark.xfail(strict=True, reason=BUG_702)
def test_inv_p_25__backslash_should_be_literal(db, M, w1, f1, inv):
    """INV-P-25 — a single backslash should be matched literally, not act as an escape.
    Rules: get_inventory_page R6 [BUG-702]."""
    tool = mk_item(db, w1, "C:\\Temp Tool")
    plain = mk_item(db, w1, "Plain Tool")
    r = _prow(inv, w1, tool, factory=f1)
    _prow(inv, w1, plain, factory=f1)
    res = M.get_inventory_page(db, workspace_id=w1.id, search="\\")
    assert page_ids(res) == [r.id]
    assert res.total == 1


def test_inv_p_26__name_order_holds_today(db, M, w1, f1, inv):
    """INV-P-26 — case-insensitive name order holds on the test DB collation today.
    Rules: get_inventory_page R4."""
    cherry = mk_item(db, w1, "cherry")
    banana = mk_item(db, w1, "Banana")
    apple = mk_item(db, w1, "apple")
    c = _prow(inv, w1, cherry, factory=f1)
    b = _prow(inv, w1, banana, factory=f1)
    a = _prow(inv, w1, apple, factory=f1)
    res = M.get_inventory_page(db, workspace_id=w1.id)
    assert page_ids(res) == [a.id, b.id, c.id]


# =========================================================================== #
# InventoryManager.get_inventory_stats
# =========================================================================== #

@pytest.fixture
def SS(db, w1, w2, i1, i2, ix, f1, f2, fx, inv):
    """Stats setup SS: A/B/C/D/E/N in W1, X in W2."""
    a = inv(w1, i1, STORAGE, f1, 3, Decimal("2.50"), None)
    b = inv(w1, i2, STORAGE, f2, 2, None, None)
    c = inv(w1, i1, SCRAP, f1, 4, Decimal("1.25"), None)
    d = inv(w1, i1, DAMAGED, f1, 100, Decimal("1.00"), None, is_deleted=True, is_active=False)
    e = inv(w1, i2, WASTE, f1, 0, Decimal("9.00"), None)
    n = inv(w1, i2, DAMAGED, f2, -2, Decimal("3.00"), None)
    inv(w2, ix, STORAGE, fx, 50, Decimal("1.00"), None)
    return {"A": a, "B": b, "C": c, "D": d, "E": e, "N": n}


def test_inv_s_01__defaults_exclude_deleted_and_zero_qty(db, M, w1, SS):
    """INV-S-01 — defaults aggregate only live, qty>0 rows; by_type has no DAMAGED/WASTE entry.
    Rules: get_inventory_stats R1 R2 R3 R5."""
    res = M.get_inventory_stats(db, workspace_id=w1.id)
    assert res.records == 3
    assert res.total_qty == 9
    assert res.estimated_value == Decimal("12.50")
    bt = by_type_map(res)
    assert bt == {STORAGE: (2, 5), SCRAP: (1, 4)}
    assert DAMAGED not in bt
    assert WASTE not in bt


def test_inv_s_02__empty_workspace(db, M, w3):
    """INV-S-02 — a workspace with no inventory rows gives all-zero stats.
    Rules: get_inventory_stats R2 R3 R5."""
    res = M.get_inventory_stats(db, workspace_id=w3.id)
    assert res.records == 0
    assert res.total_qty == 0
    assert res.estimated_value == Decimal("0")
    assert res.by_type == []


def test_inv_s_03__null_avg_price_rows(db, M, w1, u1, i1, i2, f1, inv):
    """INV-S-03 — rows with NULL avg_price contribute 0 to estimated_value.
    Rules: get_inventory_stats R3."""
    inv(w1, i1, STORAGE, f1, 3, None, None)
    inv(w1, i2, STORAGE, f1, 2, None, None)
    res = M.get_inventory_stats(db, workspace_id=w1.id)
    assert res.records == 2
    assert res.total_qty == 5
    assert res.estimated_value == Decimal("0")


def test_inv_s_04__inventory_type_filter(db, M, w1, SS):
    """INV-S-04 — inventory_type filters the aggregation.
    Rules: get_inventory_stats R1."""
    res = M.get_inventory_stats(db, workspace_id=w1.id, inventory_type=STORAGE)
    assert res.records == 2
    assert res.total_qty == 5
    assert res.estimated_value == Decimal("7.50")
    assert by_type_map(res) == {STORAGE: (2, 5)}


def test_inv_s_05__factory_filter(db, M, w1, f1, SS):
    """INV-S-05 — factory_id filters the aggregation.
    Rules: get_inventory_stats R1."""
    res = M.get_inventory_stats(db, workspace_id=w1.id, factory_id=f1.id)
    assert res.records == 2
    assert res.total_qty == 7
    assert res.estimated_value == Decimal("12.50")


def test_inv_s_06__item_filter(db, M, w1, i2, SS):
    """INV-S-06 — item_id filters the aggregation.
    Rules: get_inventory_stats R1."""
    res = M.get_inventory_stats(db, workspace_id=w1.id, item_id=i2.id)
    assert res.records == 1
    assert res.total_qty == 2
    assert res.estimated_value == Decimal("0")


def test_inv_s_07__include_zero_qty_includes_zero_and_negative(db, M, w1, SS):
    """INV-S-07 — include_zero_qty=True includes zero/negative qty rows but not deleted ones.
    Rules: get_inventory_stats R1 R3 R5."""
    res = M.get_inventory_stats(db, workspace_id=w1.id, include_zero_qty=True)
    assert res.records == 5
    assert res.total_qty == 7
    assert res.estimated_value == Decimal("6.50")
    bt = by_type_map(res)
    assert bt == {STORAGE: (2, 5), SCRAP: (1, 4), WASTE: (1, 0), DAMAGED: (1, -2)}


def test_inv_s_08__search_filters_to_matching_item(db, M, w1, SS):
    """INV-S-08 — search filters to rows of the matching item.
    Rules: get_inventory_stats R4."""
    res = M.get_inventory_stats(db, workspace_id=w1.id, search="x n")
    assert res.records == 1
    assert res.total_qty == 2
    assert res.estimated_value == Decimal("0")
    assert by_type_map(res) == {STORAGE: (1, 2)}


@pytest.mark.xfail(strict=True, reason=BUG_702)
def test_inv_s_09__percent_search_should_be_literal(db, M, w1, f1, inv):
    """INV-S-09 — "%" in search should match only items with a literal percent sign.
    Rules: get_inventory_stats R4 [BUG-702]."""
    cotton = mk_item(db, w1, "100% Cotton")
    blend = mk_item(db, w1, "Cotton Blend")
    inv(w1, cotton, STORAGE, f1, 2, Decimal("1.00"), None)
    inv(w1, blend, STORAGE, f1, 3, Decimal("1.00"), None)
    res = M.get_inventory_stats(db, workspace_id=w1.id, search="%")
    assert res.records == 1
    assert res.total_qty == 2
    assert res.estimated_value == Decimal("2.00")


def test_inv_s_10__unique_item_count_counts_items_not_rows(db, M, w1, i1, i2, f1, f2, inv):
    """INV-S-10 — unique_item_count counts distinct items, not rows.
    Rules: get_inventory_stats R5."""
    inv(w1, i1, STORAGE, f1, 2, None, None)
    inv(w1, i1, STORAGE, f2, 3, None, None)
    inv(w1, i2, STORAGE, f1, 1, None, None)
    res = M.get_inventory_stats(db, workspace_id=w1.id)
    assert res.records == 3
    assert by_type_map(res) == {STORAGE: (2, 6)}


@pytest.mark.xfail(strict=False, reason=BUG_719)
def test_inv_s_11__by_type_should_be_in_enum_order(db, M, w1, i1, f1, inv):
    """INV-S-11 — by_type should always come back in enum order STORAGE, DAMAGED, WASTE, SCRAP.
    Rules: get_inventory_stats R6 [BUG-719] (non-strict: may XPASS today; any XPASS is reported
    as a discrepancy, the assertion is never weakened)."""
    inv(w1, i1, SCRAP, f1, 1, None, None)
    inv(w1, i1, WASTE, f1, 1, None, None)
    inv(w1, i1, DAMAGED, f1, 1, None, None)
    inv(w1, i1, STORAGE, f1, 1, None, None)
    res = M.get_inventory_stats(db, workspace_id=w1.id)
    types = [row.inventory_type for row in res.by_type]
    assert types == [STORAGE, DAMAGED, WASTE, SCRAP]


# =========================================================================== #
# InventoryManager.delete_inventory
# =========================================================================== #
# All cases use T unless stated; zero ledger rows before the call.

def test_inv_d_01__happy_path_full_ledger_entry(db, M, w1, u1, T):
    """INV-D-01 — clearing stock zeroes qty and writes a full "Stock cleared" ledger entry.
    Rules: delete_inventory R3 R5 R6."""
    res = M.delete_inventory(db, T.id, w1.id, u1.id)
    assert res.id == T.id
    r = reread_inv(db, T.id)
    assert_fields(r, qty=0, updated_by=u1.id, is_deleted=False, is_active=True,
                  avg_price=Decimal("5.00"), note="n1")
    rows = ledger_rows(db, w1, T.factory, T.item, STORAGE)
    assert len(rows) == 1
    assert_fields(
        rows[0], workspace_id=w1.id, inventory_type=STORAGE, factory_id=T.factory_id, item_id=T.item_id,
        transaction_type="inventory_adjustment", quantity=10, unit_cost=Decimal("5.00"),
        total_cost=Decimal("50.00"), qty_before=10, qty_after=0, avg_price_before=Decimal("5.00"),
        avg_price_after=Decimal("5.00"), source_type="adjustment",
        notes="Stock cleared", performed_by=u1.id,
    )


def test_inv_d_02__qty_one_boundary(db, M, w1, u1, i1, f1, inv):
    """INV-D-02 — clearing a qty-1 row writes a matching ledger entry.
    Rules: delete_inventory R5 R6."""
    row = inv(w1, i1, STORAGE, f1, 1, Decimal("5.00"), "n1")
    res = M.delete_inventory(db, row.id, w1.id, u1.id)
    assert res.id == row.id
    assert reread_inv(db, row.id).qty == 0
    rows = ledger_rows(db, w1, f1, i1, STORAGE)
    assert len(rows) == 1
    assert_fields(rows[0], quantity=1, qty_before=1, total_cost=Decimal("5.00"))


def test_inv_d_03__zero_qty_is_noop(db, M, w1, u1, i1, f1, inv):
    """INV-D-03 — clearing an already-zero-qty row is a no-op, no ledger entry.
    Rules: delete_inventory R4."""
    row = inv(w1, i1, STORAGE, f1, 0, Decimal("5.00"), "n1")
    res = M.delete_inventory(db, row.id, w1.id, u1.id)
    assert res.id == row.id
    r = reread_inv(db, row.id)
    assert_fields(r, qty=0, updated_by=None, avg_price=Decimal("5.00"), note="n1", is_deleted=False)
    assert ledger_rows(db, w1, f1, i1, STORAGE) == []


def test_inv_d_04__null_avg_price_ledger_fields(db, M, w1, u1, i1, f1, inv):
    """INV-D-04 — clearing a NULL-avg_price row writes NULL cost fields.
    Rules: delete_inventory R6."""
    row = inv(w1, i1, STORAGE, f1, 10, None, "n1")
    res = M.delete_inventory(db, row.id, w1.id, u1.id)
    assert res.id == row.id
    rows = ledger_rows(db, w1, f1, i1, STORAGE)
    assert len(rows) == 1
    assert_fields(rows[0], quantity=10, unit_cost=None, total_cost=None,
                  avg_price_before=None, avg_price_after=None)


def test_inv_d_05__zero_avg_price_ledger_fields(db, M, w1, u1, i1, f1, inv):
    """INV-D-05 — clearing a 0.00-avg_price row writes 0.00 cost fields (total_cost untested here).
    Rules: delete_inventory R6."""
    row = inv(w1, i1, STORAGE, f1, 10, Decimal("0.00"), "n1")
    res = M.delete_inventory(db, row.id, w1.id, u1.id)
    assert res.id == row.id
    rows = ledger_rows(db, w1, f1, i1, STORAGE)
    assert len(rows) == 1
    assert_fields(rows[0], quantity=10, unit_cost=Decimal("0.00"),
                  avg_price_before=Decimal("0.00"), avg_price_after=Decimal("0.00"))


@pytest.mark.xfail(strict=True, reason=BUG_707)
def test_inv_d_06__zero_avg_price_total_cost_should_be_zero(db, M, w1, u1, i1, f1, inv):
    """INV-D-06 — clearing a 0.00-avg_price row should give ledger total_cost 0.00.
    Rules: delete_inventory R6 [BUG-707]."""
    row = inv(w1, i1, STORAGE, f1, 10, Decimal("0.00"), "n1")
    res = M.delete_inventory(db, row.id, w1.id, u1.id)
    assert res.id == row.id
    rows = ledger_rows(db, w1, f1, i1, STORAGE)
    assert rows[0].total_cost == Decimal("0.00")


@pytest.mark.xfail(strict=True, reason=BUG_716)
def test_inv_d_07__negative_qty_should_be_cleared_to_zero(db, M, w1, u1, i1, f1, inv):
    """INV-D-07 — clearing a negative-qty row should zero it and write a full ledger entry.
    Rules: delete_inventory R4 R5 R6 [BUG-716]."""
    row = inv(w1, i1, STORAGE, f1, -4, Decimal("5.00"), "n1")
    res = M.delete_inventory(db, row.id, w1.id, u1.id)
    assert res.id == row.id
    r = reread_inv(db, row.id)
    assert_fields(r, qty=0, updated_by=u1.id)
    rows = ledger_rows(db, w1, f1, i1, STORAGE)
    assert len(rows) == 1
    assert_fields(
        rows[0], transaction_type="inventory_adjustment", quantity=4, qty_before=-4, qty_after=0,
        unit_cost=Decimal("5.00"), total_cost=Decimal("20.00"),
        notes="Stock cleared", performed_by=u1.id,
    )


def test_inv_d_08__negative_qty_row_returned_unchanged(db, M, w1, u1, i1, f1, inv):
    """INV-D-08 — clearing a negative-qty row returns it with other fields untouched.
    Rules: delete_inventory R3."""
    row = inv(w1, i1, STORAGE, f1, -4, Decimal("5.00"), "n1")
    res = M.delete_inventory(db, row.id, w1.id, u1.id)
    assert res.id == row.id
    r = reread_inv(db, row.id)
    assert_fields(r, is_deleted=False, is_active=True, avg_price=Decimal("5.00"), note="n1")


def test_inv_d_09__second_clear_is_noop(db, M, w1, u1, u2, T):
    """INV-D-09 — clearing an already-cleared row a second time writes no second ledger entry.
    Rules: delete_inventory R4 R7."""
    res1 = M.delete_inventory(db, T.id, w1.id, u1.id)
    res2 = M.delete_inventory(db, T.id, w1.id, u2.id)
    assert res1.id == T.id
    assert res2.id == T.id
    r = reread_inv(db, T.id)
    assert r.qty == 0
    assert r.updated_by == u1.id
    assert len(ledger_rows(db, w1, T.factory, T.item, STORAGE)) == 1


def test_inv_d_10__missing_id_404(db, M, w1, u1, T):
    """INV-D-10 — an unknown inventory id raises 404 and changes nothing.
    Rules: delete_inventory R1; Errors row 1."""
    missing = missing_id_for(db, Inventory)
    with pytest.raises(HTTPException) as exc:
        M.delete_inventory(db, missing, w1.id, u1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_inv(missing)
    r = reread_inv(db, T.id)
    assert_fields(r, qty=10, updated_by=None)
    assert ws_counts(db, w1)[1] == 0


def test_inv_d_11__other_workspace_404(db, M, w1, w2, u1, TX):
    """INV-D-11 — another workspace's inventory id is reported as not found.
    Rules: delete_inventory R1; Errors row 1."""
    with pytest.raises(HTTPException) as exc:
        M.delete_inventory(db, TX.id, w1.id, u1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_inv(TX.id)
    r = reread_inv(db, TX.id)
    assert_fields(r, qty=10, updated_by=None)
    assert ws_counts(db, w1)[1] == 0
    assert ws_counts(db, w2)[1] == 0


def test_inv_d_12__deleted_row_400(db, M, w1, u1, TD):
    """INV-D-12 — clearing a soft-deleted row raises 400 and changes nothing.
    Rules: delete_inventory R2; Errors row 2."""
    with pytest.raises(HTTPException) as exc:
        M.delete_inventory(db, TD.id, w1.id, u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Cannot clear stock on a deactivated inventory record"
    r = reread_inv(db, TD.id)
    assert_fields(r, qty=10, updated_by=None, is_deleted=True)
    assert ledger_rows(db, w1, TD.factory, TD.item, STORAGE) == []


@pytest.mark.xfail(strict=True, reason=BUG_705)
def test_inv_d_13__clear_should_lock_row(db, M, w1, u1, T):
    """INV-D-13 — clearing stock should issue a locked SELECT ... FOR UPDATE OF inventory.
    Rules: delete_inventory R8 [BUG-705]."""
    with SQLCapture(db) as cap:
        res = M.delete_inventory(db, T.id, w1.id, u1.id)
    assert res.id == T.id
    assert locked_read_of_inventory(cap.statements)
    assert no_nowait_or_skip_locked(cap.statements)


# =========================================================================== #
# InventoryManager.get_incoming_summary_for_factory
# =========================================================================== #
# Default call: workspace_id=W1, factory_id=F1. "PO_k"/"TR_k" numbers are
# "PO-000k" / "TR-000k".

def test_inv_if_01__single_po_pending_qty(db, M, w1, u2, f1, i1, s_open, wf):
    """INV-IF-01 — one open PO with a partly-received line reports the remaining pending qty.
    Rules: get_incoming_summary_for_factory R3 R5 R9 R10 R11."""
    po1 = mk_po(db, w1, u2, status=s_open, factory=f1, workflow=wf, number="PO-0001")
    mk_po_line(db, w1, po1, i1, 10, 3)
    res = M.get_incoming_summary_for_factory(db, workspace_id=w1.id, factory_id=f1.id)
    assert len(res) == 1
    item = res[0]
    assert item.factory_id == f1.id
    assert item.item_id == i1.id
    assert item.total_pending_qty == Decimal("7")
    assert item.order_count == 1
    assert len(item.orders) == 1
    o = item.orders[0]
    assert o.order_kind == "purchase"
    assert o.order_id == po1.id
    assert o.order_number == "PO-0001"
    assert o.status_name == "Ordered"
    assert o.pending_qty == Decimal("7")


def test_inv_if_02__single_transfer_pending_qty(db, M, w1, u2, f1, i1, s_tr):
    """INV-IF-02 — one incomplete inbound transfer reports its line qty as pending.
    Rules: get_incoming_summary_for_factory R6 R7 R9 R10."""
    tr1 = mk_tr(db, w1, u2, status=s_tr, factory=f1, number="TR-0001")
    mk_tr_line(db, w1, tr1, i1, 4)
    res = M.get_incoming_summary_for_factory(db, workspace_id=w1.id, factory_id=f1.id)
    assert len(res) == 1
    item = res[0]
    assert item.factory_id == f1.id
    assert item.item_id == i1.id
    assert item.total_pending_qty == Decimal("4")
    assert item.order_count == 1
    o = item.orders[0]
    assert o.order_kind == "transfer"
    assert o.order_id == tr1.id
    assert o.order_number == "TR-0001"
    assert o.status_name == "In Transit"
    assert o.pending_qty == Decimal("4")


def test_inv_if_03__missing_factory_404(db, M, w1):
    """INV-IF-03 — an unknown factory id raises 404; W1 row counts unchanged.
    Rules: get_incoming_summary_for_factory R1; Errors row 1."""
    missing = missing_id_for(db, Factory)
    before = ws_counts(db, w1)
    with pytest.raises(HTTPException) as exc:
        M.get_incoming_summary_for_factory(db, workspace_id=w1.id, factory_id=missing)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_factory(missing)
    assert ws_counts(db, w1) == before


def test_inv_if_04__other_workspace_factory_404(db, M, w1, w2, u2, fx, ix):
    """INV-IF-04 — a factory of another workspace is reported as not found.
    Rules: get_incoming_summary_for_factory R1; Errors row 1."""
    s_w2 = mk_status(db, w2, "Ordered")
    po = mk_po(db, w2, u2, status=s_w2, factory=fx, workflow=None, number="PO-0001")
    mk_po_line(db, w2, po, ix, 5, 0)
    before = ws_counts(db, w1)
    with pytest.raises(HTTPException) as exc:
        M.get_incoming_summary_for_factory(db, workspace_id=w1.id, factory_id=fx.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_factory(fx.id)
    assert ws_counts(db, w1) == before


@pytest.mark.xfail(strict=True, reason=BUG_718)
def test_inv_if_05__deleted_factory_should_404(db, M, w1, u2, f_del, i1, s_open):
    """INV-IF-05 — a soft-deleted factory should raise 404.
    Rules: get_incoming_summary_for_factory R2 [BUG-718]; Errors row 1."""
    po = mk_po(db, w1, u2, status=s_open, factory=f_del, workflow=None, number="PO-0001")
    mk_po_line(db, w1, po, i1, 10, 0)
    before = ws_counts(db, w1)
    with pytest.raises(HTTPException) as exc:
        M.get_incoming_summary_for_factory(db, workspace_id=w1.id, factory_id=f_del.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_factory(f_del.id)
    assert ws_counts(db, w1) == before


def test_inv_if_06__inactive_factory_accepted(db, M, w1, u2, f_in, i1, s_open, wf):
    """INV-IF-06 — an inactive-but-live factory is still summarised.
    Rules: get_incoming_summary_for_factory R2."""
    po = mk_po(db, w1, u2, status=s_open, factory=f_in, workflow=wf, number="PO-0001")
    mk_po_line(db, w1, po, i1, 10, 0)
    res = M.get_incoming_summary_for_factory(db, workspace_id=w1.id, factory_id=f_in.id)
    assert len(res) == 1
    item = res[0]
    assert item.factory_id == f_in.id
    assert item.item_id == i1.id
    assert item.total_pending_qty == Decimal("10")
    assert item.order_count == 1
    assert len(item.orders) == 1
    o = item.orders[0]
    assert o.order_kind == "purchase"
    assert o.order_id == po.id
    assert o.order_number == "PO-0001"
    assert o.status_name == "Ordered"
    assert o.pending_qty == Decimal("10")


def test_inv_if_07__destination_type_and_workspace_filters(db, M, w1, w2, u2, f1, f2, i1, s_open, wf):
    """INV-IF-07 — only storage-destined POs of this workspace+factory contribute.
    Rules: get_incoming_summary_for_factory R3."""
    po1 = mk_po(db, w1, u2, status=s_open, factory=f1, workflow=wf, number="PO-0001")
    mk_po_line(db, w1, po1, i1, 5, 0)
    mk_po_line(db, w1, mk_po(db, w1, u2, status=s_open, factory=f2, workflow=wf, number="PO-0002"),
               i1, 7, 0)
    mk_po_line(
        db, w1,
        mk_po(db, w1, u2, status=s_open, factory=f1, destination_type="machine",
              destination_id=f1.id, workflow=wf, number="PO-0003"),
        i1, 8, 0,
    )
    s_w2 = mk_status(db, w2, "W2 Status")
    po4 = mk_po(db, w2, u2, status=s_w2, factory=f1, destination_type="storage",
                destination_id=f1.id, workflow=None, number="PO-0001")
    mk_po_line(db, w2, po4, i1, 9, 0)
    res = M.get_incoming_summary_for_factory(db, workspace_id=w1.id, factory_id=f1.id)
    assert len(res) == 1
    item = res[0]
    assert item.factory_id == f1.id
    assert item.item_id == i1.id
    assert item.total_pending_qty == Decimal("5")
    assert item.order_count == 1
    assert len(item.orders) == 1
    o = item.orders[0]
    assert o.order_kind == "purchase"
    assert o.order_id == po1.id
    assert o.order_number == "PO-0001"
    assert o.status_name == "Ordered"
    assert o.pending_qty == Decimal("5")


def test_inv_if_08__terminal_status_excluded(db, M, w1, u2, f1, i1, s_open, s_done, wf):
    """INV-IF-08 — a PO in its workflow's terminal status is excluded.
    Rules: get_incoming_summary_for_factory R4."""
    po1 = mk_po(db, w1, u2, status=s_done, factory=f1, workflow=wf, number="PO-0001")
    mk_po_line(db, w1, po1, i1, 5, 0)
    po2 = mk_po(db, w1, u2, status=s_open, factory=f1, workflow=wf, number="PO-0002")
    mk_po_line(db, w1, po2, i1, 3, 0)
    res = M.get_incoming_summary_for_factory(db, workspace_id=w1.id, factory_id=f1.id)
    assert len(res) == 1
    item = res[0]
    assert item.factory_id == f1.id
    assert item.item_id == i1.id
    assert item.total_pending_qty == Decimal("3")
    assert item.order_count == 1
    assert len(item.orders) == 1
    o = item.orders[0]
    assert o.order_kind == "purchase"
    assert o.order_id == po2.id
    assert o.order_number == "PO-0002"
    assert o.status_name == "Ordered"
    assert o.pending_qty == Decimal("3")


def test_inv_if_09__no_workflow_never_terminal(db, M, w1, u2, f1, i1, s_done):
    """INV-IF-09 — a PO with no workflow is never terminal, even in a "done"-looking status.
    Rules: get_incoming_summary_for_factory R4."""
    po1 = mk_po(db, w1, u2, status=s_done, factory=f1, workflow=None, number="PO-0001")
    mk_po_line(db, w1, po1, i1, 5, 0)
    res = M.get_incoming_summary_for_factory(db, workspace_id=w1.id, factory_id=f1.id)
    assert len(res) == 1
    item = res[0]
    assert item.factory_id == f1.id
    assert item.item_id == i1.id
    assert item.total_pending_qty == Decimal("5")
    assert item.order_count == 1
    assert len(item.orders) == 1
    o = item.orders[0]
    assert o.order_kind == "purchase"
    assert o.order_id == po1.id
    assert o.order_number == "PO-0001"
    assert o.status_name == "Received"
    assert o.pending_qty == Decimal("5")


def test_inv_if_10__empty_status_sequence_never_terminal(db, M, w1, u2, f1, i1, s_done):
    """INV-IF-10 — a workflow with an empty status_sequence has no terminal status.
    Rules: get_incoming_summary_for_factory R4."""
    wf_e = mk_workflow(db, w1, status_sequence=[])
    po1 = mk_po(db, w1, u2, status=s_done, factory=f1, workflow=wf_e, number="PO-0001")
    mk_po_line(db, w1, po1, i1, 5, 0)
    res = M.get_incoming_summary_for_factory(db, workspace_id=w1.id, factory_id=f1.id)
    assert len(res) == 1
    item = res[0]
    assert item.factory_id == f1.id
    assert item.item_id == i1.id
    assert item.total_pending_qty == Decimal("5")
    assert item.order_count == 1
    assert len(item.orders) == 1
    o = item.orders[0]
    assert o.order_kind == "purchase"
    assert o.order_id == po1.id
    assert o.order_number == "PO-0001"
    assert o.status_name == "Received"
    assert o.pending_qty == Decimal("5")


def test_inv_if_11__non_integer_last_status_never_terminal(db, M, w1, u2, f1, i1, s_open, s_done):
    """INV-IF-11 — a workflow whose last status_sequence element is not an int has no terminal status.
    Rules: get_incoming_summary_for_factory R4."""
    wf_s = mk_workflow(db, w1, status_sequence=[s_open.id, str(s_done.id)])
    po1 = mk_po(db, w1, u2, status=s_done, factory=f1, workflow=wf_s, number="PO-0001")
    mk_po_line(db, w1, po1, i1, 5, 0)
    res = M.get_incoming_summary_for_factory(db, workspace_id=w1.id, factory_id=f1.id)
    assert len(res) == 1
    item = res[0]
    assert item.factory_id == f1.id
    assert item.item_id == i1.id
    assert item.total_pending_qty == Decimal("5")
    assert item.order_count == 1
    assert len(item.orders) == 1
    o = item.orders[0]
    assert o.order_kind == "purchase"
    assert o.order_id == po1.id
    assert o.order_number == "PO-0001"
    assert o.status_name == "Received"
    assert o.pending_qty == Decimal("5")


def test_inv_if_12__workflow_in_other_workspace_ignored(db, M, w1, w2, u2, f1, i1, s_open, s_done):
    """INV-IF-12 — a workflow belonging to another workspace gives no terminal mapping.
    Rules: get_incoming_summary_for_factory R4."""
    wf_x = mk_workflow(db, w2, status_sequence=[s_open.id, s_done.id])
    po1 = mk_po(db, w1, u2, status=s_done, factory=f1, workflow=wf_x, number="PO-0001")
    mk_po_line(db, w1, po1, i1, 5, 0)
    res = M.get_incoming_summary_for_factory(db, workspace_id=w1.id, factory_id=f1.id)
    assert len(res) == 1
    item = res[0]
    assert item.factory_id == f1.id
    assert item.item_id == i1.id
    assert item.total_pending_qty == Decimal("5")
    assert item.order_count == 1
    assert len(item.orders) == 1
    o = item.orders[0]
    assert o.order_kind == "purchase"
    assert o.order_id == po1.id
    assert o.order_number == "PO-0001"
    assert o.status_name == "Received"
    assert o.pending_qty == Decimal("5")


@pytest.mark.xfail(strict=True, reason=BUG_717)
def test_inv_if_13__voided_po_should_be_excluded(db, M, w1, u2, f1, i1, s_open, wf):
    """INV-IF-13 — a voided PO should be excluded regardless of status.
    Rules: get_incoming_summary_for_factory R4 [BUG-717]."""
    po1 = mk_po(db, w1, u2, status=s_open, factory=f1, workflow=wf, voided=True, number="PO-0001")
    mk_po_line(db, w1, po1, i1, 6, 0)
    po2 = mk_po(db, w1, u2, status=s_open, factory=f1, workflow=wf, number="PO-0002")
    mk_po_line(db, w1, po2, i1, 3, 0)
    res = M.get_incoming_summary_for_factory(db, workspace_id=w1.id, factory_id=f1.id)
    assert len(res) == 1
    item = res[0]
    assert item.factory_id == f1.id
    assert item.item_id == i1.id
    assert item.total_pending_qty == Decimal("3")
    assert item.order_count == 1
    assert len(item.orders) == 1
    o = item.orders[0]
    assert o.order_kind == "purchase"
    assert o.order_id == po2.id
    assert o.order_number == "PO-0002"
    assert o.status_name == "Ordered"
    assert o.pending_qty == Decimal("3")


def test_inv_if_14__pending_zero_or_less_skipped(db, M, w1, u2, f1, i1, i2, i3, i4, i5, s_open, wf):
    """INV-IF-14 — lines with pending <= 0 are skipped; only I3 and I4 have pending stock.
    Rules: get_incoming_summary_for_factory R5 R11."""
    po1 = mk_po(db, w1, u2, status=s_open, factory=f1, workflow=wf, number="PO-0001")
    mk_po_line(db, w1, po1, i1, 10, 10, line_number=1)
    mk_po_line(db, w1, po1, i2, 5, 6, line_number=2)
    mk_po_line(db, w1, po1, i3, 5, None, line_number=3)
    mk_po_line(db, w1, po1, i4, 1, 0, line_number=4)
    mk_po_line(db, w1, po1, i5, None, None, line_number=5)
    res = M.get_incoming_summary_for_factory(db, workspace_id=w1.id, factory_id=f1.id)
    assert [item.item_id for item in res] == [i3.id, i4.id]
    i3_entry, i4_entry = res
    assert i3_entry.factory_id == f1.id
    assert i3_entry.total_pending_qty == Decimal("5")
    assert i3_entry.order_count == 1
    assert len(i3_entry.orders) == 1
    o3 = i3_entry.orders[0]
    assert o3.order_kind == "purchase"
    assert o3.order_id == po1.id
    assert o3.order_number == "PO-0001"
    assert o3.status_name == "Ordered"
    assert o3.pending_qty == Decimal("5")
    assert i4_entry.factory_id == f1.id
    assert i4_entry.total_pending_qty == Decimal("1")
    assert i4_entry.order_count == 1
    assert len(i4_entry.orders) == 1
    o4 = i4_entry.orders[0]
    assert o4.order_kind == "purchase"
    assert o4.order_id == po1.id
    assert o4.order_number == "PO-0001"
    assert o4.status_name == "Ordered"
    assert o4.pending_qty == Decimal("1")


def test_inv_if_15__only_incomplete_storage_destined_transfers_to_factory(
    db, M, w1, w2, u2, f1, f2, i1, s_tr,
):
    """INV-IF-15 — only incomplete transfers into this factory's storage contribute.
    Rules: get_incoming_summary_for_factory R6."""
    tr1 = mk_tr(db, w1, u2, status=s_tr, factory=f1, number="TR-0001")
    mk_tr_line(db, w1, tr1, i1, 2)
    tr2 = mk_tr(db, w1, u2, status=s_tr, factory=f1, completed_at=datetime(2026, 1, 1), number="TR-0002")
    mk_tr_line(db, w1, tr2, i1, 3)
    tr3 = mk_tr(db, w1, u2, status=s_tr, factory=f2, number="TR-0003")
    mk_tr_line(db, w1, tr3, i1, 4)
    tr4 = mk_tr(db, w1, u2, status=s_tr, factory=f1, destination_location_type="machine",
                destination_location_id=f1.id, number="TR-0004")
    mk_tr_line(db, w1, tr4, i1, 5)
    s_w2 = mk_status(db, w2, "In Transit")
    # transfer_number is globally unique (not scoped per workspace), so TR_5
    # (5th order created overall) must use a number distinct from tr1..tr4.
    tr5 = mk_tr(db, w2, u2, status=s_w2, destination_location_id=f1.id, number="TR-0005")
    mk_tr_line(db, w2, tr5, i1, 6)
    res = M.get_incoming_summary_for_factory(db, workspace_id=w1.id, factory_id=f1.id)
    assert len(res) == 1
    item = res[0]
    assert item.factory_id == f1.id
    assert item.item_id == i1.id
    assert item.total_pending_qty == Decimal("2")
    assert item.order_count == 1
    assert len(item.orders) == 1
    o = item.orders[0]
    assert o.order_kind == "transfer"
    assert o.order_id == tr1.id
    assert o.order_number == "TR-0001"
    assert o.status_name == "In Transit"
    assert o.pending_qty == Decimal("2")


def test_inv_if_16__draft_transfer_status_name(db, M, w1, u2, f1, i1, s_draft):
    """INV-IF-16 — an unapproved, draft-status transfer still counts as pending.
    Rules: get_incoming_summary_for_factory R6 R9."""
    tr1 = mk_tr(db, w1, u2, status=s_draft, factory=f1, number="TR-0001")
    mk_tr_line(db, w1, tr1, i1, 2)
    res = M.get_incoming_summary_for_factory(db, workspace_id=w1.id, factory_id=f1.id)
    assert len(res) == 1
    item = res[0]
    assert item.total_pending_qty == Decimal("2")
    o = item.orders[0]
    assert o.order_kind == "transfer"
    assert o.order_id == tr1.id
    assert o.order_number == "TR-0001"
    assert o.status_name == "Draft"
    assert o.pending_qty == Decimal("2")


def test_inv_if_17__transfer_pending_le_zero_skipped(db, M, w1, u2, f1, i1, i2, i3, i4, s_tr):
    """INV-IF-17 — transfer lines with pending <= 0 are skipped; only I4 has pending stock.
    Rules: get_incoming_summary_for_factory R7 R11."""
    tr1 = mk_tr(db, w1, u2, status=s_tr, factory=f1, number="TR-0001")
    mk_tr_line(db, w1, tr1, i1, 0, line_number=1)
    mk_tr_line(db, w1, tr1, i2, None, line_number=2)
    mk_tr_line(db, w1, tr1, i3, -1, line_number=3)
    mk_tr_line(db, w1, tr1, i4, 1, line_number=4)
    res = M.get_incoming_summary_for_factory(db, workspace_id=w1.id, factory_id=f1.id)
    assert [item.item_id for item in res] == [i4.id]
    item = res[0]
    assert item.factory_id == f1.id
    assert item.total_pending_qty == Decimal("1")
    assert item.order_count == 1
    assert len(item.orders) == 1
    o = item.orders[0]
    assert o.order_kind == "transfer"
    assert o.order_id == tr1.id
    assert o.order_number == "TR-0001"
    assert o.status_name == "In Transit"
    assert o.pending_qty == Decimal("1")


def test_inv_if_18__lines_of_same_po_merge(db, M, w1, u2, f1, i1, s_open, wf):
    """INV-IF-18 — two lines of the same item within one PO merge into one orders entry.
    Rules: get_incoming_summary_for_factory R8 R10."""
    po1 = mk_po(db, w1, u2, status=s_open, factory=f1, workflow=wf, number="PO-0001")
    mk_po_line(db, w1, po1, i1, 3, 0, line_number=1)
    mk_po_line(db, w1, po1, i1, 4, 0, line_number=2)
    po2 = mk_po(db, w1, u2, status=s_open, factory=f1, workflow=wf, number="PO-0002")
    mk_po_line(db, w1, po2, i1, 2, 0)
    res = M.get_incoming_summary_for_factory(db, workspace_id=w1.id, factory_id=f1.id)
    assert len(res) == 1
    item = res[0]
    assert item.factory_id == f1.id
    assert item.item_id == i1.id
    assert item.total_pending_qty == Decimal("9")
    assert item.order_count == 2
    assert len(item.orders) == 2
    o1, o2 = item.orders
    assert o1.order_kind == "purchase"
    assert o1.order_id == po1.id
    assert o1.order_number == "PO-0001"
    assert o1.status_name == "Ordered"
    assert o1.pending_qty == Decimal("7")
    assert o2.order_kind == "purchase"
    assert o2.order_id == po2.id
    assert o2.order_number == "PO-0002"
    assert o2.status_name == "Ordered"
    assert o2.pending_qty == Decimal("2")


def test_inv_if_19__po_and_transfer_same_id_stay_separate(db, M, w1, u2, f1, i1, s_open, s_tr, wf):
    """INV-IF-19 — a PO and a transfer sharing the same numeric id stay separate entries.
    Rules: get_incoming_summary_for_factory R8."""
    po = mk_po(db, w1, u2, status=s_open, factory=f1, workflow=wf, number="PO-0001", id_=987654)
    mk_po_line(db, w1, po, i1, 5, 0)
    tr = mk_tr(db, w1, u2, status=s_tr, factory=f1, number="TR-0001", id_=987654)
    mk_tr_line(db, w1, tr, i1, 2)
    res = M.get_incoming_summary_for_factory(db, workspace_id=w1.id, factory_id=f1.id)
    assert len(res) == 1
    item = res[0]
    assert item.factory_id == f1.id
    assert item.item_id == i1.id
    assert item.total_pending_qty == Decimal("7")
    assert item.order_count == 2
    assert len(item.orders) == 2
    o_po, o_tr = item.orders
    assert o_po.order_kind == "purchase"
    assert o_po.order_id == 987654
    assert o_po.order_number == "PO-0001"
    assert o_po.status_name == "Ordered"
    assert o_po.pending_qty == Decimal("5")
    assert o_tr.order_kind == "transfer"
    assert o_tr.order_id == 987654
    assert o_tr.order_number == "TR-0001"
    assert o_tr.status_name == "In Transit"
    assert o_tr.pending_qty == Decimal("2")


def test_inv_if_21__multi_order_results_sorted_by_item_then_purchase_before_transfer(
    db, M, w1, u2, f1, i1, i2, s_open, s_tr, wf,
):
    """INV-IF-21 — results sorted by item id; within an item, purchase entries before transfer entries.
    Rules: get_incoming_summary_for_factory R10 R11."""
    tr1 = mk_tr(db, w1, u2, status=s_tr, factory=f1, number="TR-0001")
    mk_tr_line(db, w1, tr1, i2, 1)
    tr2 = mk_tr(db, w1, u2, status=s_tr, factory=f1, number="TR-0002")
    mk_tr_line(db, w1, tr2, i2, 1)
    po1 = mk_po(db, w1, u2, status=s_open, factory=f1, workflow=wf, number="PO-0001")
    mk_po_line(db, w1, po1, i2, 1, 0, line_number=1)
    mk_po_line(db, w1, po1, i1, 1, 0, line_number=2)
    po2 = mk_po(db, w1, u2, status=s_open, factory=f1, workflow=wf, number="PO-0002")
    mk_po_line(db, w1, po2, i2, 1, 0)
    res = M.get_incoming_summary_for_factory(db, workspace_id=w1.id, factory_id=f1.id)
    assert [item.item_id for item in res] == [i1.id, i2.id]
    i1_entry, i2_entry = res
    assert i1_entry.factory_id == f1.id
    assert i1_entry.total_pending_qty == Decimal("1")
    assert i1_entry.order_count == 1
    assert len(i1_entry.orders) == 1
    o = i1_entry.orders[0]
    assert o.order_kind == "purchase"
    assert o.order_id == po1.id
    assert o.order_number == "PO-0001"
    assert o.status_name == "Ordered"
    assert o.pending_qty == Decimal("1")
    assert i2_entry.factory_id == f1.id
    assert i2_entry.total_pending_qty == Decimal("4")
    assert i2_entry.order_count == 4
    assert len(i2_entry.orders) == 4
    assert [(o.order_kind, o.order_id) for o in i2_entry.orders] == [
        ("purchase", po1.id), ("purchase", po2.id), ("transfer", tr1.id), ("transfer", tr2.id),
    ]
    assert [o.order_number for o in i2_entry.orders] == ["PO-0001", "PO-0002", "TR-0001", "TR-0002"]
    assert [o.status_name for o in i2_entry.orders] == [
        "Ordered", "Ordered", "In Transit", "In Transit",
    ]
    assert [o.pending_qty for o in i2_entry.orders] == [
        Decimal("1"), Decimal("1"), Decimal("1"), Decimal("1"),
    ]


def test_inv_if_22__no_orders_empty_list(db, M, w1, f1):
    """INV-IF-22 — no open POs and no incomplete transfers gives an empty list.
    Rules: get_incoming_summary_for_factory R12."""
    res = M.get_incoming_summary_for_factory(db, workspace_id=w1.id, factory_id=f1.id)
    assert res == []


def test_inv_if_23__fully_received_and_completed_give_empty_list(db, M, w1, u2, f1, i1, s_open, s_tr, wf):
    """INV-IF-23 — a fully-received PO and completed/zero-qty transfers give an empty list.
    Rules: get_incoming_summary_for_factory R5 R7 R12."""
    po1 = mk_po(db, w1, u2, status=s_open, factory=f1, workflow=wf, number="PO-0001")
    mk_po_line(db, w1, po1, i1, 5, 5)
    tr1 = mk_tr(db, w1, u2, status=s_tr, factory=f1, completed_at=datetime(2026, 1, 1), number="TR-0001")
    mk_tr_line(db, w1, tr1, i1, 3)
    tr2 = mk_tr(db, w1, u2, status=s_tr, factory=f1, number="TR-0002")
    mk_tr_line(db, w1, tr2, i1, 0)
    res = M.get_incoming_summary_for_factory(db, workspace_id=w1.id, factory_id=f1.id)
    assert res == []


# =========================================================================== #
# InventoryManager.get_incoming_summary
# =========================================================================== #

def test_inv_is_01__with_factory_id_matches_per_factory_result(db, M, w1, f1, f2, u2, i1, s_open, wf):
    """INV-IS-01 — with factory_id given, result matches get_incoming_summary_for_factory exactly.
    Rules: get_incoming_summary R1."""
    po1 = mk_po(db, w1, u2, status=s_open, factory=f1, workflow=wf, number="PO-0001")
    mk_po_line(db, w1, po1, i1, 5, 0)
    po2 = mk_po(db, w1, u2, status=s_open, factory=f2, workflow=wf, number="PO-0002")
    mk_po_line(db, w1, po2, i1, 3, 0)
    direct = M.get_incoming_summary_for_factory(db, workspace_id=w1.id, factory_id=f1.id)
    res = M.get_incoming_summary(db, workspace_id=w1.id, factory_id=f1.id)
    assert summary_tuples(res) == summary_tuples(direct)
    assert len(res) == 1
    item = res[0]
    assert item.factory_id == f1.id
    assert item.item_id == i1.id
    assert item.total_pending_qty == Decimal("5")
    assert item.order_count == 1
    assert len(item.orders) == 1
    o = item.orders[0]
    assert o.order_kind == "purchase"
    assert o.order_id == po1.id
    assert o.order_number == "PO-0001"
    assert o.status_name == "Ordered"
    assert o.pending_qty == Decimal("5")


def test_inv_is_02__factory_zero_404(db, M, w1):
    """INV-IS-02 — factory_id=0 raises 404 like any unknown factory id.
    Rules: get_incoming_summary R1, Errors."""
    before = ws_counts(db, w1)
    with pytest.raises(HTTPException) as exc:
        M.get_incoming_summary(db, workspace_id=w1.id, factory_id=0)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_factory(0)
    assert ws_counts(db, w1) == before


def test_inv_is_03__other_workspace_factory_404(db, M, w1, w2, fx):
    """INV-IS-03 — a factory of another workspace is reported as not found.
    Rules: get_incoming_summary R1, Errors."""
    before = ws_counts(db, w1)
    with pytest.raises(HTTPException) as exc:
        M.get_incoming_summary(db, workspace_id=w1.id, factory_id=fx.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_factory(fx.id)
    assert ws_counts(db, w1) == before


def test_inv_is_04__factory_id_given_includes_inactive(db, M, w1, u2, f_in, i1, s_open, wf):
    """INV-IS-04 — a given factory_id is summarised even if inactive.
    Rules: get_incoming_summary R1 R2."""
    po1 = mk_po(db, w1, u2, status=s_open, factory=f_in, workflow=wf, number="PO-0001")
    mk_po_line(db, w1, po1, i1, 4, 0)
    res = M.get_incoming_summary(db, workspace_id=w1.id, factory_id=f_in.id)
    assert len(res) == 1
    item = res[0]
    assert item.factory_id == f_in.id
    assert item.item_id == i1.id
    assert item.total_pending_qty == Decimal("4")
    assert item.order_count == 1
    assert len(item.orders) == 1
    o = item.orders[0]
    assert o.order_kind == "purchase"
    assert o.order_id == po1.id
    assert o.order_number == "PO-0001"
    assert o.status_name == "Ordered"
    assert o.pending_qty == Decimal("4")


def test_inv_is_05__workspace_wide_only_active_live_factories(
    db, M, w1, w2, u2, f1, f2, f_in, f_del, fx, i1, ix, s_open, wf,
):
    """INV-IS-05 — without factory_id, only active/live factories with pending stock are summarised.
    Rules: get_incoming_summary R2."""
    mk_factory(db, w1, "Empty Plant")  # F3: nothing incoming
    po1 = mk_po(db, w1, u2, status=s_open, factory=f1, workflow=wf, number="PO-0001")
    mk_po_line(db, w1, po1, i1, 5, 0)
    po2 = mk_po(db, w1, u2, status=s_open, factory=f2, workflow=wf, number="PO-0002")
    mk_po_line(db, w1, po2, i1, 3, 0)
    po3 = mk_po(db, w1, u2, status=s_open, factory=f_in, workflow=wf, number="PO-0003")
    mk_po_line(db, w1, po3, i1, 4, 0)
    po4 = mk_po(db, w1, u2, status=s_open, factory=f_del, workflow=wf, number="PO-0004")
    mk_po_line(db, w1, po4, i1, 6, 0)
    s_w2 = mk_status(db, w2, "Ordered")
    po5 = mk_po(db, w2, u2, status=s_w2, factory=fx, workflow=None, number="PO-0001")
    mk_po_line(db, w2, po5, ix, 7, 0)
    res = M.get_incoming_summary(db, workspace_id=w1.id)
    assert len(res) == 2
    assert {item.factory_id for item in res} == {f1.id, f2.id}
    by_factory = {item.factory_id: item for item in res}
    e1 = by_factory[f1.id]
    assert e1.item_id == i1.id
    assert e1.total_pending_qty == Decimal("5")
    assert e1.order_count == 1
    assert len(e1.orders) == 1
    o1 = e1.orders[0]
    assert o1.order_kind == "purchase"
    assert o1.order_id == po1.id
    assert o1.order_number == "PO-0001"
    assert o1.status_name == "Ordered"
    assert o1.pending_qty == Decimal("5")
    e2 = by_factory[f2.id]
    assert e2.item_id == i1.id
    assert e2.total_pending_qty == Decimal("3")
    assert e2.order_count == 1
    assert len(e2.orders) == 1
    o2 = e2.orders[0]
    assert o2.order_kind == "purchase"
    assert o2.order_id == po2.id
    assert o2.order_number == "PO-0002"
    assert o2.status_name == "Ordered"
    assert o2.pending_qty == Decimal("3")


def test_inv_is_06__no_factories_empty_list(db, M, w3):
    """INV-IS-06 — a workspace with no factories returns an empty list.
    Rules: get_incoming_summary R2."""
    res = M.get_incoming_summary(db, workspace_id=w3.id)
    assert res == []


@pytest.mark.xfail(strict=True, reason=BUG_709)
def test_inv_is_07__more_than_500_factories_all_covered(db, M, w3, u2):
    """INV-IS-07 — all active factories should be covered, with no 500-row cap.
    Rules: get_incoming_summary R3 [BUG-709]."""
    status = mk_status(db, w3, "Ordered")
    item = mk_item(db, w3, "Widget")
    factories = [
        Factory(workspace_id=w3.id, name=f"Plant {i:03d}", abbreviation="PLT",
                is_active=True, is_deleted=False)
        for i in range(1, 502)
    ]
    db.add_all(factories)
    db.flush()
    pos = [
        PurchaseOrder(
            workspace_id=w3.id, po_number=f"PO-{i:04d}", destination_type="storage",
            destination_id=f.id, current_status_id=status.id, order_workflow_id=None,
            voided=False, created_by=u2.id,
        )
        for i, f in enumerate(factories, start=1)
    ]
    db.add_all(pos)
    db.flush()
    lines = [
        PurchaseOrderItem(
            workspace_id=w3.id, purchase_order_id=po.id, line_number=1,
            item_id=item.id, quantity_ordered=1, quantity_received=0,
        )
        for po in pos
    ]
    db.add_all(lines)
    db.flush()
    res = M.get_incoming_summary(db, workspace_id=w3.id)
    assert len(res) == 501
    assert {item.factory_id for item in res} == {f.id for f in factories}


@pytest.mark.xfail(strict=True, reason=BUG_706)
def test_inv_is_08__factories_should_be_ordered_by_name(db, M, w3, u2):
    """INV-IS-08 — factories should be processed in name order (case-insensitive), then id.
    Rules: get_incoming_summary R4 [BUG-706]."""
    status = mk_status(db, w3, "Ordered")
    item = mk_item(db, w3, "Widget")
    names = ["charlie", "Bravo", "alpha"]
    factories = {}
    for i, name in enumerate(names, start=1):
        f = mk_factory(db, w3, name)
        factories[name] = f
        po = PurchaseOrder(
            workspace_id=w3.id, po_number=f"PO-{i:04d}", destination_type="storage",
            destination_id=f.id, current_status_id=status.id, order_workflow_id=None,
            voided=False, created_by=u2.id,
        )
        db.add(po)
        db.flush()
        db.add(PurchaseOrderItem(
            workspace_id=w3.id, purchase_order_id=po.id, line_number=1,
            item_id=item.id, quantity_ordered=1, quantity_received=0,
        ))
    db.flush()
    res = M.get_incoming_summary(db, workspace_id=w3.id)
    got_order = []
    for item in res:
        if item.factory_id not in got_order:
            got_order.append(item.factory_id)
    expected = [factories["alpha"].id, factories["Bravo"].id, factories["charlie"].id]
    assert got_order == expected
