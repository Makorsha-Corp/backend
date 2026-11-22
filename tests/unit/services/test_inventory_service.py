"""Unit tests for app/services/inventory_service.py.

Implements tests/unit/services/inventory_service.cases.md (Revision 2), one test
per case, in card order. Real Postgres session (`db` fixture): a `commit()` only
releases a savepoint, so the service's commits are safe and the fixture's outer
rollback discards everything. Nothing is patched except what Conventions name:
the spies, the failing commit / failing refresh wraps and the race simulation of
INVS-C-09.

Normal mode: every test is written from its card and carries a `# [claude] <ID>`
comment. Row names of the cards are the lower-case names here (T -> t,
`W1.id` -> `w1.id`); `# Then N` marks the checks of the card's Then line N.
"""
# ruff: noqa: SIM117, FURB157  (Conventions prescribe `with pytest.raises(...)` around `with patch.object(...)`; Decimal("7") etc. are the cards' literal values)
import os
import re
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import event, func, inspect, select
from sqlalchemy.exc import DataError, IntegrityError

from app.dao.inventory import inventory_dao
from app.models.enums import InventoryTypeEnum
from app.models.factory import Factory
from app.models.inventory import Inventory
from app.models.inventory_ledger import InventoryLedger
from app.models.item import Item
from app.models.order_workflow import OrderWorkflow
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.status import Status
from app.models.workspace import Workspace
from app.schemas.inventory import InventoryCreate, InventoryUpdate
from app.services.inventory_service import InventoryService, inventory_service
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "svc"
svc = inventory_service
assert isinstance(svc, InventoryService)

STORAGE = InventoryTypeEnum.STORAGE
DAMAGED = InventoryTypeEnum.DAMAGED
WASTE = InventoryTypeEnum.WASTE
SCRAP = InventoryTypeEnum.SCRAP

# Convention "MISSING"
MISSING = 999999999

# Convention "T0" (naive)
T0 = datetime(2020, 1, 2, 3, 4, 5)  # noqa: DTZ001

# Convention "SFX"
SFX = str(os.getpid())

_BUGS = {
    700: "get_inventory returns soft-deleted inventory rows",
    701: "Inventory list has no stable sort order",
    702: "Inventory/stats search text acts as SQL wildcards",
    703: "update_inventory stamps updated_by on no-op updates",
    704: "update_inventory reads stock quantity without a row lock",
    705: "delete_inventory (clear stock) reads stock without a row lock",
    706: "Incoming summary processes factories with no sort order",
    707: "Zero average price records ledger total_cost as empty",
    710: "Inventory can be created for a catalog item of another workspace",
    712: "Average price can change with no ledger entry",
    713: "Update cannot clear note or avg_price",
    714: "Creating over a soft-deleted row fails with an opaque database conflict",
    715: "Inventory can be created in a soft-deleted factory",
    716: "Clear stock leaves a negative quantity untouched",
    717: "Voided purchase orders still count as incoming stock",
    718: "Per-factory incoming summary accepts a soft-deleted factory",
    719: "Per-type breakdown in inventory stats has no fixed order",
    3082: "The \"include deleted\" option on inventory get can't be reached from the API",
}


def xfail(n, strict=True):
    """Expect `xfail BUG-n` (strict) or `xfail BUG-n (non-strict)`."""
    return pytest.mark.xfail(strict=strict, reason=f"BUG-{n}: {_BUGS[n]}")


# --------------------------------------------------------------------------- #
# Conventions -> standing rows: W1, W2, U1, U2, F1, I1 (in this order)
# --------------------------------------------------------------------------- #

@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


# U1 acts
@pytest.fixture
def u1(db, w2):
    return make_profile(db)


# U2 created the Given rows
@pytest.fixture
def u2(db, u1):
    return make_profile(db)


def _add(db, row):
    db.add(row)
    db.flush()
    return row


def _factory_fields(w1, but):
    fields = {"workspace_id": w1.id, "name": "Main Plant", "abbreviation": "MAI", "is_active": True,
              "is_deleted": False}
    fields.update(but)
    return fields


def _item_fields(w1, but):
    fields = {"workspace_id": w1.id, "name": "Bolt", "unit": "pkgs", "is_active": True}
    fields.update(but)
    fields["name_normalized"] = fields["name"].lower()
    return fields


# Builder "factory"
@pytest.fixture
def f1(db, u2, w1):
    return _add(db, Factory(**_factory_fields(w1, {})))


# Builder "item"
@pytest.fixture
def i1(db, f1, w1):
    return _add(db, Item(**_item_fields(w1, {})))


@pytest.fixture(autouse=True)
def standing(i1):
    pass


# --------------------------------------------------------------------------- #
# Conventions -> builders (inserted directly, flushed one at a time)
# --------------------------------------------------------------------------- #

class Given:
    def __init__(self, db, w1, w2, u1, u2, f1, i1):
        self.db, self.w1, self.w2, self.u1, self.u2, self.f1, self.i1 = db, w1, w2, u1, u2, f1, i1

    # "factory, but ..."
    def factory(self, **but):
        return _add(self.db, Factory(**_factory_fields(self.w1, but)))

    # "item, but ..."
    def item(self, **but):
        return _add(self.db, Item(**_item_fields(self.w1, but)))

    def f2(self):
        return self.factory(name="Second Plant", abbreviation="SEC")

    def fx(self):
        return self.factory(workspace_id=self.w2.id, name="Foreign Plant", abbreviation="FOR")

    # FD: a real factory soft delete; is_active stays True
    def fd(self):
        return self.factory(name="Old Plant", abbreviation="OLD", is_deleted=True, deleted_at=T0,
                            deleted_by=self.u2.id)

    def fi(self):
        return self.factory(name="Idle Plant", abbreviation="IDL", is_active=False)

    def i2(self):
        return self.item(name="Hex Nut", unit="pcs")

    def i3(self):
        return self.item(name="Washer", unit="pcs")

    def ix(self):
        return self.item(workspace_id=self.w2.id, name="Secret Part", unit="pcs")

    def inv_fields(self, but):
        fields = {"workspace_id": self.w1.id, "item_id": self.i1.id, "inventory_type": STORAGE,
                  "factory_id": self.f1.id, "qty": 10, "avg_price": Decimal("5.00"), "note": "n1",
                  "is_active": True, "is_deleted": False, "created_by": self.u2.id, "updated_by": None}
        fields.update(but)
        return fields

    # Builder "inv"
    def inv(self, **but):
        return _add(self.db, Inventory(**self.inv_fields(but)))

    # "gone" (after "but", inventory only)
    def gone(self):
        return {"is_active": False, "is_deleted": True, "deleted_at": T0, "deleted_by": self.u2.id}

    # "TX = inv, but workspace_id W2.id, item_id IX.id, factory_id FX.id"
    def foreign(self, ix, fx, **but):
        return self.inv(workspace_id=self.w2.id, item_id=ix.id, factory_id=fx.id, **but)

    # Incoming rows: S_OPEN, S_DONE, WF
    def flow(self):
        s_open = _add(self.db, Status(workspace_id=self.w1.id, name="Ordered", comment="Ordered"))
        s_done = _add(self.db, Status(workspace_id=self.w1.id, name="Received", comment="Received"))
        wf = _add(self.db, OrderWorkflow(workspace_id=self.w1.id, name="Flow", type="PFM",
                                         status_sequence=[s_open.id, s_done.id]))
        return s_open, s_done, wf

    # "po k on F"
    def po(self, k, factory, s_open, wf, **but):
        fields = {"workspace_id": self.w1.id, "po_number": f"PO-INVS-{SFX}-{k}", "destination_type": "storage",
                  "destination_id": factory.id, "current_status_id": s_open.id, "order_workflow_id": wf.id,
                  "voided": False, "created_by": self.u1.id}
        fields.update(but)
        return _add(self.db, PurchaseOrder(**fields))

    # "line of P"
    def line(self, p, **but):
        fields = {"workspace_id": self.w1.id, "purchase_order_id": p.id, "line_number": 1, "item_id": self.i1.id,
                  "quantity_ordered": Decimal("10"), "quantity_received": Decimal("3")}
        fields.update(but)
        return _add(self.db, PurchaseOrderItem(**fields))


@pytest.fixture
def g(db, w1, w2, u1, u2, f1, i1):
    return Given(db, w1, w2, u1, u2, f1, i1)


# Convention "commit point"
def commit_point(db):
    db.commit()


# Convention "X" (after the commit point): flushed, not committed
def mk_x(db):
    return make_workspace(db).id


# --------------------------------------------------------------------------- #
# Conventions -> named checks
# --------------------------------------------------------------------------- #

def _id_of(row):
    return inspect(row).identity[0]


# "re-read R"
def reread(db, row):
    row_id = _id_of(row)
    db.expire_all()
    return db.get(Inventory, row_id)


_UNCHANGED = ("qty", "avg_price", "note", "is_active", "is_deleted", "updated_by")


def _snap(db, row_id):
    found = db.execute(
        select(*(getattr(Inventory, c) for c in _UNCHANGED)).where(Inventory.id == row_id)
    ).one()
    return dict(zip(_UNCHANGED, found, strict=True))


# "unchanged(R)": values at the commit point ...
def snap_before(db, row):
    return _snap(db, _id_of(row))


# ... and after a re-read
def snap(db, row):
    row_id = _id_of(row)
    db.expire_all()
    return _snap(db, row_id)


# "ledger(R)"
def ledger(db, row):
    key = db.execute(
        select(Inventory.workspace_id, Inventory.factory_id, Inventory.item_id, Inventory.inventory_type)
        .where(Inventory.id == _id_of(row))
    ).one()
    return list(db.execute(
        select(InventoryLedger)
        .where(InventoryLedger.workspace_id == key[0], InventoryLedger.factory_id == key[1],
               InventoryLedger.item_id == key[2], InventoryLedger.inventory_type == key[3])
        .order_by(InventoryLedger.id)
    ).scalars().all())


# "ledger_all"
def ledger_all(db, w1):
    return db.execute(
        select(func.count()).select_from(InventoryLedger).where(InventoryLedger.workspace_id == w1.id)
    ).scalar_one()


# "inv_count"
def inv_count(db, w1):
    return db.execute(
        select(func.count()).select_from(Inventory).where(Inventory.workspace_id == w1.id)
    ).scalar_one()


# "x_gone" / "x_there"
def x_gone(db, x_id):
    return db.execute(select(Workspace.id).where(Workspace.id == x_id)).first() is None


def x_there(db, x_id):
    return db.execute(select(Workspace.id).where(Workspace.id == x_id)).first() is not None


# "loaded(r)"
def loaded(r):
    return inspect(r).expired_attributes.isdisjoint({c.key for c in inspect(Inventory).column_attrs})


# "session: usable"
def usable(db):
    return db.execute(select(1)).scalar() == 1


# "recorder": statements sent during the When
class Recorder:
    def __init__(self, db):
        self.bind = db.connection()
        self.statements = []

    def _record(self, conn, cursor, statement, parameters, context, executemany):
        self.statements.append(statement)

    def __enter__(self):
        event.listen(self.bind, "before_cursor_execute", self._record)
        return self

    def __exit__(self, *exc_info):
        event.remove(self.bind, "before_cursor_execute", self._record)
        return False

    @property
    def inv_selects(self):
        return [s for s in self.statements
                if s.lstrip().startswith("SELECT") and re.search(r"FROM inventory(\s|$)", s)]


# Race simulation (INVS-C-09 only)
def race():
    return (patch.object(inventory_dao, "get_by_factory_item_type", return_value=None),
            patch.object(inventory_dao, "_get_any_by_factory_item_type", return_value=None, create=True))


# --------------------------------------------------------------------------- #
# InventoryService.create_inventory
# --------------------------------------------------------------------------- #

# [claude] INVS-C-01
def test_invs_c_01__a_create_is_committed_with_its_opening_ledger_entry(db, w1, u1, f1, i1):
    """INVS-C-01 — a create is committed with its opening ledger entry and returned re-read.
    Rules: `create_inventory` R1, Returns; TC1, TC2"""
    commit_point(db)
    result = svc.create_inventory(
        db, inv_in=InventoryCreate(item_id=i1.id, inventory_type=STORAGE, factory_id=f1.id, qty=3,
                                   avg_price=Decimal("10.50"), note="Opening"),
        workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert loaded(result)
    # Then 2
    assert isinstance(result, Inventory)
    assert result.id is not None
    assert result.created_at is not None
    # Then 3
    assert result.qty == 3
    assert result.avg_price == Decimal("10.50")
    assert result.created_by == u1.id
    # Then 4
    db.rollback()
    row = reread(db, result)
    assert row.qty == 3
    assert row.avg_price == Decimal("10.50")
    assert row.note == "Opening"
    assert row.workspace_id == w1.id
    assert row.is_deleted is False
    # Then 5
    assert len(ledger(db, result)) == 1
    # Then 6
    entry = ledger(db, result)[0]
    assert entry.transaction_type == "manual_add"
    assert entry.quantity == 3
    assert entry.total_cost == Decimal("31.50")
    assert entry.qty_before == 0
    assert entry.qty_after == 3
    assert entry.performed_by == u1.id


# [claude] INVS-C-02
def test_invs_c_02__an_unknown_factory_404_passes_and_pending_row_discarded(db, w1, u1, i1):
    """INVS-C-02 — an unknown factory: the 404 passes unchanged and the pending row is discarded.
    Rules: `create_inventory` R2, Errors; TC3"""
    commit_point(db)
    x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_inventory(
            db, inv_in=InventoryCreate(item_id=i1.id, inventory_type=STORAGE, factory_id=MISSING, qty=3),
            workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory with ID 999999999 not found"
    # Then 4
    assert not db.new
    assert not db.dirty
    # Then 5
    assert x_gone(db, x_id)
    # Then 6
    assert inv_count(db, w1) == 0
    # Then 7
    assert ledger_all(db, w1) == 0
    # Then 8
    assert usable(db)


# [claude] INVS-C-03
def test_invs_c_03__another_workspaces_factory_404_pending_row_discarded(db, g, w1, u1, i1):
    """INVS-C-03 — another workspace's factory: the 404 passes unchanged, the pending row is discarded.
    Rules: `create_inventory` R2, Errors; TC3"""
    fx = g.fx()
    commit_point(db)
    x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_inventory(
            db, inv_in=InventoryCreate(item_id=i1.id, inventory_type=STORAGE, factory_id=fx.id, qty=3),
            workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory with ID {fx.id} not found"
    # Then 4
    assert x_gone(db, x_id)
    # Then 5
    assert inv_count(db, w1) == 0
    # Then 6
    assert ledger_all(db, w1) == 0


# [claude] INVS-C-04
def test_invs_c_04__a_live_duplicate_409_passes_pending_row_discarded(db, g, w1, u1, f1, i1):
    """INVS-C-04 — a live duplicate: the 409 passes unchanged, the pending row is discarded.
    Rules: `create_inventory` R2, Errors; TC3 (holds today and after BUG-714)"""
    t = g.inv()
    commit_point(db)
    before_t = snap_before(db, t)
    x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_inventory(
            db, inv_in=InventoryCreate(item_id=i1.id, inventory_type=STORAGE, factory_id=f1.id, qty=7),
            workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Inventory record already exists for this item/type/factory combination"
    # Then 4
    assert x_gone(db, x_id)
    # Then 5
    assert inv_count(db, w1) == 1
    # Then 6
    assert snap(db, t) == before_t
    # Then 7
    assert len(ledger(db, t)) == 0
    # Then 8
    assert usable(db)


# [claude] INVS-C-05
@xfail(710)
def test_invs_c_05__bug_710_another_workspaces_item_gets_404_item(db, g, w1, u1, f1):
    """INVS-C-05 — BUG-710: another workspace's item gets the 404 Item, the pending row is discarded.
    Rules: `create_inventory` R2 [BUG-710], Errors"""
    ix = g.ix()
    commit_point(db)
    x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_inventory(
            db, inv_in=InventoryCreate(item_id=ix.id, inventory_type=STORAGE, factory_id=f1.id, qty=3),
            workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Item with ID {ix.id} not found"
    # Then 4
    assert x_gone(db, x_id)
    # Then 5
    assert inv_count(db, w1) == 0
    # Then 6
    assert ledger_all(db, w1) == 0


# [claude] INVS-C-06
@xfail(715)
def test_invs_c_06__bug_715_a_soft_deleted_factory_gets_the_404(db, g, w1, u1, i1):
    """INVS-C-06 — pass-through BUG-715: a soft-deleted factory gets the 404, the pending row is discarded.
    Rules: `create_inventory` R1 [BUG-715], R2"""
    fd = g.fd()
    commit_point(db)
    x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_inventory(
            db, inv_in=InventoryCreate(item_id=i1.id, inventory_type=STORAGE, factory_id=fd.id, qty=3),
            workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory with ID {fd.id} not found"
    # Then 4
    assert x_gone(db, x_id)
    # Then 5
    assert inv_count(db, w1) == 0


# [claude] INVS-C-07
def test_invs_c_07__an_inactive_but_live_factory_is_accepted(db, g, w1, u1, i1):
    """INVS-C-07 — an inactive but live factory is accepted and committed.
    Rules: `create_inventory` R1 (holds today and after BUG-715)"""
    fi = g.fi()
    commit_point(db)
    result = svc.create_inventory(
        db, inv_in=InventoryCreate(item_id=i1.id, inventory_type=STORAGE, factory_id=fi.id, qty=2),
        workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.factory_id == fi.id
    # Then 2
    db.rollback()
    row = reread(db, result)
    assert row.qty == 2
    assert row.factory_id == fi.id
    # Then 3
    assert len(ledger(db, result)) == 1


# [claude] INVS-C-08
def test_invs_c_08__a_database_error_at_the_flush_passes_unchanged(db, w1, u1, f1, i1):
    """INVS-C-08 — a database error at the flush passes unchanged, nothing saved, session usable.
    Rules: `create_inventory` R3, Errors; TC3"""
    commit_point(db)
    x_id = mk_x(db)
    data = InventoryCreate.model_construct(item_id=i1.id, inventory_type=STORAGE, factory_id=f1.id, qty=1,
                                           avg_price=Decimal("1e13"), note=None)
    # Then 1
    with pytest.raises(DataError):
        svc.create_inventory(db, inv_in=data, workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert not db.new
    assert not db.dirty
    # Then 3
    assert x_gone(db, x_id)
    # Then 4
    assert inv_count(db, w1) == 0
    # Then 5
    assert ledger_all(db, w1) == 0
    # Then 6
    assert usable(db)


# [claude] INVS-C-09
def test_invs_c_09__a_concurrent_duplicates_integrity_error_passes(db, g, w1, u1, f1, i1):
    """INVS-C-09 — a concurrent duplicate's IntegrityError passes unchanged after the rollback.
    Rules: `create_inventory` R3, Errors; TC3"""
    t = g.inv()
    commit_point(db)
    before_t = snap_before(db, t)
    x_id = mk_x(db)
    lookup, lookup_any = race()
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with lookup, lookup_any:
            svc.create_inventory(
                db, inv_in=InventoryCreate(item_id=i1.id, inventory_type=STORAGE, factory_id=f1.id, qty=4),
                workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    assert x_gone(db, x_id)
    # Then 4
    assert inv_count(db, w1) == 1
    # Then 5
    assert snap(db, t) == before_t
    # Then 6
    assert len(ledger(db, t)) == 0
    # Then 7
    assert usable(db)


# [claude] INVS-C-10
def test_invs_c_10__a_failing_commit_is_rolled_back_and_re_raised(db, w1, u1, f1, i1):
    """INVS-C-10 — a failing commit is rolled back and re-raised; row, ledger and pending row gone.
    Rules: `create_inventory` R4; TC4"""
    commit_point(db)
    x_id = mk_x(db)
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "commit", side_effect=RuntimeError("boom")), \
                patch.object(db, "rollback", wraps=db.rollback) as rb:
            svc.create_inventory(
                db, inv_in=InventoryCreate(item_id=i1.id, inventory_type=STORAGE, factory_id=f1.id, qty=3),
                workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert x_gone(db, x_id)
    # Then 4
    assert inv_count(db, w1) == 0
    # Then 5
    assert ledger_all(db, w1) == 0


# [claude] INVS-C-11
def test_invs_c_11__a_failing_re_read_after_the_commit_leaves_row_and_ledger_saved(db, w1, u1, f1, i1):
    """INVS-C-11 — a failing re-read after the commit leaves row and ledger saved.
    Rules: `create_inventory` R4; TC5"""
    commit_point(db)
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "refresh", side_effect=RuntimeError("boom")):
            svc.create_inventory(
                db, inv_in=InventoryCreate(item_id=i1.id, inventory_type=STORAGE, factory_id=f1.id, qty=3),
                workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    db.rollback()
    assert inv_count(db, w1) == 1
    # Then 3
    assert ledger_all(db, w1) == 1


# [claude] INVS-C-12
@xfail(707)
def test_invs_c_12__bug_707_a_zero_price_gives_total_cost_0_00(db, w1, u1, f1, i1):
    """INVS-C-12 — pass-through BUG-707: a zero price gives total_cost 0.00 on the opening entry.
    Rules: `create_inventory` R1 [BUG-707]"""
    commit_point(db)
    result = svc.create_inventory(
        db, inv_in=InventoryCreate(item_id=i1.id, inventory_type=STORAGE, factory_id=f1.id, qty=2,
                                   avg_price=Decimal("0.00")),
        workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.qty == 2
    # Then 2
    db.rollback()
    assert len(ledger(db, result)) == 1
    # Then 3
    assert ledger(db, result)[0].total_cost == Decimal("0.00")


# [claude] INVS-C-13
def test_invs_c_13__a_zero_price_is_stored_with_unit_cost_0_00(db, w1, u1, f1, i1):
    """INVS-C-13 — a zero price is stored and the opening entry carries unit_cost 0.00.
    Rules: `create_inventory` R1 (holds today and after BUG-707)"""
    commit_point(db)
    result = svc.create_inventory(
        db, inv_in=InventoryCreate(item_id=i1.id, inventory_type=STORAGE, factory_id=f1.id, qty=2,
                                   avg_price=Decimal("0.00")),
        workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.avg_price == Decimal("0.00")
    # Then 2
    db.rollback()
    row = reread(db, result)
    assert row.avg_price == Decimal("0.00")
    assert row.qty == 2
    # Then 3
    assert len(ledger(db, result)) == 1
    # Then 4
    entry = ledger(db, result)[0]
    assert entry.unit_cost == Decimal("0.00")
    assert entry.quantity == 2


# [claude] INVS-C-14
@xfail(714)
def test_invs_c_14__bug_714_a_soft_deleted_row_of_the_bucket_is_restored(db, g, w1, u1, u2, f1, i1):
    """INVS-C-14 — pass-through BUG-714: a soft-deleted row of the bucket is restored and committed.
    Rules: `create_inventory` R1 [BUG-714]"""
    td = g.inv(**g.gone())
    commit_point(db)
    result = svc.create_inventory(
        db, inv_in=InventoryCreate(item_id=i1.id, inventory_type=STORAGE, factory_id=f1.id, qty=4,
                                   avg_price=Decimal("6.00"), note="Back"),
        workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.id == td.id
    # Then 2
    db.rollback()
    row = reread(db, td)
    assert row.is_deleted is False
    assert row.qty == 4
    assert row.avg_price == Decimal("6.00")
    assert row.note == "Back"
    # Then 3
    row = reread(db, td)
    assert row.created_by == u2.id
    assert row.updated_by == u1.id
    # Then 4
    assert inv_count(db, w1) == 1
    # Then 5
    assert len(ledger(db, td)) == 1
    # Then 6
    entry = ledger(db, td)[0]
    assert entry.transaction_type == "manual_add"
    assert entry.quantity == 4


# [claude] INVS-C-15
def test_invs_c_15__qty_0_with_no_price_writes_no_ledger_entry(db, w1, u1, f1, i1):
    """INVS-C-15 — qty 0 with no price: the row is committed and no ledger entry is written.
    Rules: `create_inventory` R1 (opening entry only when qty > 0)"""
    commit_point(db)
    result = svc.create_inventory(
        db, inv_in=InventoryCreate(item_id=i1.id, inventory_type=STORAGE, factory_id=f1.id, qty=0),
        workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.qty == 0
    # Then 2
    db.rollback()
    row = reread(db, result)
    assert row.qty == 0
    assert row.avg_price is None
    # Then 3
    assert len(ledger(db, result)) == 0


# [claude] INVS-C-16
def test_invs_c_16__a_successful_create_also_commits_a_pending_change(db, w1, u1, f1, i1):
    """INVS-C-16 — a successful create also commits a change already pending in the session.
    Rules: `create_inventory` R1; TC1"""
    commit_point(db)
    x_id = mk_x(db)
    result = svc.create_inventory(
        db, inv_in=InventoryCreate(item_id=i1.id, inventory_type=STORAGE, factory_id=f1.id, qty=1),
        workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.qty == 1
    # Then 2
    db.rollback()
    assert x_there(db, x_id)
    # Then 3
    assert inv_count(db, w1) == 1


# --------------------------------------------------------------------------- #
# InventoryService.update_inventory
# --------------------------------------------------------------------------- #

# [claude] INVS-U-01
def test_invs_u_01__a_quantity_edit_is_committed_with_its_ledger_entry(db, g, w1, u1):
    """INVS-U-01 — a quantity edit is committed with its ledger entry and returned re-read.
    Rules: `update_inventory` R1, Returns; TC1, TC2"""
    t = g.inv()
    commit_point(db)
    result = svc.update_inventory(db, inv_id=t.id, inv_in=InventoryUpdate(qty=15), workspace_id=w1.id,
                                  user_id=u1.id)
    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == t.id
    assert result.qty == 15
    assert result.updated_at is not None
    # Then 3
    db.rollback()
    row = reread(db, t)
    assert row.qty == 15
    assert row.updated_by == u1.id
    assert row.updated_at is not None
    # Then 4
    row = reread(db, t)
    assert row.avg_price == Decimal("5.00")
    assert row.note == "n1"
    # Then 5
    assert len(ledger(db, t)) == 1
    # Then 6
    entry = ledger(db, t)[0]
    assert entry.transaction_type == "inventory_adjustment"
    assert entry.quantity == 5
    assert entry.qty_before == 10
    assert entry.qty_after == 15
    assert entry.notes == "Quantity adjusted from 10 to 15"
    assert entry.performed_by == u1.id


# [claude] INVS-U-02
def test_invs_u_02__another_workspaces_row_404_pending_row_discarded(db, g, w1, u1):
    """INVS-U-02 — another workspace's row: the 404 passes unchanged, the pending row is discarded.
    Rules: `update_inventory` R2, Errors; TC3"""
    fx = g.fx()
    ix = g.ix()
    tx = g.foreign(ix, fx)
    commit_point(db)
    before_tx = snap_before(db, tx)
    x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_inventory(db, inv_id=tx.id, inv_in=InventoryUpdate(qty=99), workspace_id=w1.id,
                             user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Inventory record with ID {tx.id} not found"
    # Then 4
    assert not db.new
    assert not db.dirty
    # Then 5
    assert x_gone(db, x_id)
    # Then 6
    assert snap(db, tx) == before_tx
    # Then 7
    assert len(ledger(db, tx)) == 0
    # Then 8
    assert usable(db)


# [claude] INVS-U-03
def test_invs_u_03__an_unknown_id_404_pending_row_discarded(db, g, w1, u1):
    """INVS-U-03 — an unknown id: the 404 passes unchanged, the pending row is discarded.
    Rules: `update_inventory` R2, Errors; TC3"""
    t = g.inv()
    commit_point(db)
    before_t = snap_before(db, t)
    x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_inventory(db, inv_id=MISSING, inv_in=InventoryUpdate(qty=99), workspace_id=w1.id,
                             user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Inventory record with ID 999999999 not found"
    # Then 4
    assert x_gone(db, x_id)
    # Then 5
    assert snap(db, t) == before_t


# [claude] INVS-U-04
def test_invs_u_04__a_soft_deleted_row_400_pending_row_discarded(db, g, w1, u1):
    """INVS-U-04 — a soft-deleted row: the 400 passes unchanged, the pending row is discarded.
    Rules: `update_inventory` R2, Errors; TC3"""
    td = g.inv(**g.gone())
    commit_point(db)
    before_td = snap_before(db, td)
    x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_inventory(db, inv_id=td.id, inv_in=InventoryUpdate(qty=99), workspace_id=w1.id,
                             user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update a deleted inventory record"
    # Then 4
    assert x_gone(db, x_id)
    # Then 5
    assert snap(db, td) == before_td
    # Then 6
    assert len(ledger(db, td)) == 0


# [claude] INVS-U-05
@xfail(713)
def test_invs_u_05__bug_713_qty_sent_as_null_gets_the_422(db, g, w1, u1):
    """INVS-U-05 — BUG-713: qty sent as null gets the 422, the pending row is discarded.
    Rules: `update_inventory` R2 [BUG-713], Errors"""
    t = g.inv()
    commit_point(db)
    before_t = snap_before(db, t)
    x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_inventory(db, inv_id=t.id, inv_in=InventoryUpdate(qty=None), workspace_id=w1.id,
                             user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 422
    # Then 3
    assert exc.value.detail == "qty cannot be empty"
    # Then 4
    assert x_gone(db, x_id)
    # Then 5
    assert snap(db, t) == before_t


# [claude] INVS-U-06
@xfail(713)
def test_invs_u_06__bug_713_a_note_sent_as_null_is_cleared(db, g, w1, u1):
    """INVS-U-06 — pass-through BUG-713: a note sent as null is cleared and committed.
    Rules: `update_inventory` R1 [BUG-713]"""
    t = g.inv()
    commit_point(db)
    result = svc.update_inventory(db, inv_id=t.id, inv_in=InventoryUpdate(note=None), workspace_id=w1.id,
                                  user_id=u1.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert result.note is None
    # Then 3
    db.rollback()
    row = reread(db, t)
    assert row.note is None
    assert row.qty == 10


# [claude] INVS-U-07
def test_invs_u_07__fields_not_sent_are_kept(db, g, w1, u1):
    """INVS-U-07 — fields not sent are kept.
    Rules: `update_inventory` R1"""
    t = g.inv()
    commit_point(db)
    result = svc.update_inventory(db, inv_id=t.id, inv_in=InventoryUpdate(note="Shelf 4"), workspace_id=w1.id,
                                  user_id=u1.id)
    # Then 1
    assert result.note == "Shelf 4"
    # Then 2
    db.rollback()
    row = reread(db, t)
    assert row.note == "Shelf 4"
    assert row.qty == 10
    assert row.avg_price == Decimal("5.00")
    # Then 3
    assert len(ledger(db, t)) == 0


# [claude] INVS-U-08
def test_invs_u_08__a_database_error_at_the_flush_passes_unchanged(db, g, w1, u1):
    """INVS-U-08 — a database error at the flush passes unchanged, nothing saved, session usable.
    Rules: `update_inventory` R3; TC3"""
    t = g.inv()
    commit_point(db)
    before_t = snap_before(db, t)
    x_id = mk_x(db)
    data = InventoryUpdate.model_construct(avg_price=Decimal("1e13"))
    # Then 1
    with pytest.raises(DataError):
        svc.update_inventory(db, inv_id=t.id, inv_in=data, workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert not db.dirty
    # Then 3
    assert x_gone(db, x_id)
    # Then 4
    assert snap(db, t) == before_t
    # Then 5
    assert len(ledger(db, t)) == 0
    # Then 6
    assert usable(db)


# [claude] INVS-U-09
def test_invs_u_09__a_failing_commit_is_rolled_back(db, g, w1, u1):
    """INVS-U-09 — a failing commit is rolled back: quantity, ledger and pending row not saved.
    Rules: `update_inventory` R3; TC4"""
    t = g.inv()
    commit_point(db)
    before_t = snap_before(db, t)
    x_id = mk_x(db)
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "commit", side_effect=RuntimeError("boom")), \
                patch.object(db, "rollback", wraps=db.rollback) as rb:
            svc.update_inventory(db, inv_id=t.id, inv_in=InventoryUpdate(qty=15), workspace_id=w1.id,
                                 user_id=u1.id)
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert x_gone(db, x_id)
    # Then 4
    assert snap(db, t) == before_t
    # Then 5
    assert len(ledger(db, t)) == 0


# [claude] INVS-U-10
def test_invs_u_10__a_failing_re_read_after_the_commit_leaves_the_edit_saved(db, g, w1, u1):
    """INVS-U-10 — a failing re-read after the commit leaves the edit saved.
    Rules: `update_inventory` R3; TC5"""
    t = g.inv()
    commit_point(db)
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "refresh", side_effect=RuntimeError("boom")):
            svc.update_inventory(db, inv_id=t.id, inv_in=InventoryUpdate(qty=15), workspace_id=w1.id,
                                 user_id=u1.id)
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    db.rollback()
    assert reread(db, t).qty == 15
    # Then 3
    assert len(ledger(db, t)) == 1


# [claude] INVS-U-11
@xfail(703)
def test_invs_u_11__bug_703_an_empty_update_does_not_stamp_updated_by(db, g, w1, u1):
    """INVS-U-11 — pass-through BUG-703: an empty update does not stamp updated_by.
    Rules: `update_inventory` R1 [BUG-703]"""
    t = g.inv()
    commit_point(db)
    result = svc.update_inventory(db, inv_id=t.id, inv_in=InventoryUpdate(), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    db.rollback()
    assert reread(db, t).updated_by is None


# [claude] INVS-U-12
@xfail(704)
def test_invs_u_12__bug_704_the_row_is_read_for_update_of_inventory(db, g, w1, u1):
    """INVS-U-12 — pass-through BUG-704: the row is read with FOR UPDATE OF inventory.
    Rules: `update_inventory` R1a [BUG-704]"""
    t = g.inv()
    commit_point(db)
    with Recorder(db) as rec:
        result = svc.update_inventory(db, inv_id=t.id, inv_in=InventoryUpdate(qty=11), workspace_id=w1.id,
                                      user_id=u1.id)
    inv_selects = rec.inv_selects
    # Then 1
    assert result.qty == 11
    # Then 2
    assert any(s.rstrip().endswith("FOR UPDATE OF inventory") for s in inv_selects)
    # Then 3
    assert not any("NOWAIT" in s or "SKIP LOCKED" in s for s in inv_selects)


# [claude] INVS-U-13
@xfail(707)
def test_invs_u_13__bug_707_a_quantity_edit_at_price_0_00_gives_total_cost_0_00(db, g, w1, u1):
    """INVS-U-13 — pass-through BUG-707: a quantity edit at price 0.00 gives total_cost 0.00.
    Rules: `update_inventory` R1 [BUG-707]"""
    t = g.inv(avg_price=Decimal("0.00"))
    commit_point(db)
    result = svc.update_inventory(db, inv_id=t.id, inv_in=InventoryUpdate(qty=12), workspace_id=w1.id,
                                  user_id=u1.id)
    # Then 1
    assert result.qty == 12
    # Then 2
    db.rollback()
    assert len(ledger(db, t)) == 1
    # Then 3
    assert ledger(db, t)[0].total_cost == Decimal("0.00")


# [claude] INVS-U-14
@xfail(712)
def test_invs_u_14__bug_712_a_price_only_edit_writes_a_ledger_entry(db, g, w1, u1):
    """INVS-U-14 — pass-through BUG-712: a price-only edit writes a ledger entry.
    Rules: `update_inventory` R1 [BUG-712]"""
    t = g.inv()
    commit_point(db)
    result = svc.update_inventory(db, inv_id=t.id, inv_in=InventoryUpdate(avg_price=Decimal("6.00")),
                                  workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.avg_price == Decimal("6.00")
    # Then 2
    db.rollback()
    assert len(ledger(db, t)) == 1
    # Then 3
    entry = ledger(db, t)[0]
    assert entry.transaction_type == "inventory_adjustment"
    assert entry.quantity == 0
    assert entry.qty_before == 10
    assert entry.qty_after == 10
    # Then 4
    entry = ledger(db, t)[0]
    assert entry.avg_price_before == Decimal("5.00")
    assert entry.avg_price_after == Decimal("6.00")
    assert entry.notes == "Average price adjusted from 5.00 to 6.00"


# [claude] INVS-U-15
def test_invs_u_15__a_price_only_edit_is_committed(db, g, w1, u1):
    """INVS-U-15 — a price-only edit is committed.
    Rules: `update_inventory` R1 (holds today and after BUG-712)"""
    t = g.inv()
    commit_point(db)
    result = svc.update_inventory(db, inv_id=t.id, inv_in=InventoryUpdate(avg_price=Decimal("6.00")),
                                  workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.avg_price == Decimal("6.00")
    # Then 2
    db.rollback()
    row = reread(db, t)
    assert row.avg_price == Decimal("6.00")
    assert row.qty == 10
    assert row.updated_by == u1.id


# [claude] INVS-U-16
def test_invs_u_16__a_successful_update_also_commits_a_pending_change(db, g, w1, u1):
    """INVS-U-16 — a successful update also commits a change already pending in the session.
    Rules: `update_inventory` R1; TC1"""
    t = g.inv()
    commit_point(db)
    x_id = mk_x(db)
    result = svc.update_inventory(db, inv_id=t.id, inv_in=InventoryUpdate(qty=12), workspace_id=w1.id,
                                  user_id=u1.id)
    # Then 1
    assert result.qty == 12
    # Then 2
    db.rollback()
    assert x_there(db, x_id)
    # Then 3
    assert reread(db, t).qty == 12


# --------------------------------------------------------------------------- #
# InventoryService.get_inventory
# --------------------------------------------------------------------------- #

# [claude] INVS-G-01
def test_invs_g_01__a_row_of_the_workspace_is_returned(db, g, w1):
    """INVS-G-01 — a row of the workspace is returned.
    Rules: `get_inventory` R1"""
    fx = g.fx()
    ix = g.ix()
    g.foreign(ix, fx)
    t = g.inv()
    commit_point(db)
    result = svc.get_inventory(db, inv_id=t.id, workspace_id=w1.id)
    # Then 1
    assert isinstance(result, Inventory)
    # Then 2
    assert result.id == t.id
    assert result.qty == 10
    assert result.workspace_id == w1.id


# [claude] INVS-G-02
def test_invs_g_02__another_workspaces_row_404(db, g, w1):
    """INVS-G-02 — another workspace's row: the 404 passes unchanged.
    Rules: `get_inventory` R1, Errors (holds today and after BUG-700 / BUG-3082)"""
    g.inv()
    fx = g.fx()
    ix = g.ix()
    tx = g.foreign(ix, fx)
    commit_point(db)
    before_tx = snap_before(db, tx)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_inventory(db, inv_id=tx.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Inventory record with ID {tx.id} not found"
    # Then 4
    assert snap(db, tx) == before_tx


# [claude] INVS-G-03
def test_invs_g_03__an_unknown_id_gets_the_404(db, g, w1):
    """INVS-G-03 — an unknown id gets the 404.
    Rules: `get_inventory` R1, Errors"""
    g.inv()
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_inventory(db, inv_id=MISSING, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Inventory record with ID 999999999 not found"


# [claude] INVS-G-04
@xfail(700)
def test_invs_g_04__bug_700_a_soft_deleted_row_is_hidden_by_default(db, g, w1):
    """INVS-G-04 — BUG-700: a soft-deleted row is hidden by default.
    Rules: `get_inventory` R2 [BUG-700], Errors"""
    td = g.inv(**g.gone())
    commit_point(db)
    before_td = snap_before(db, td)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_inventory(db, inv_id=td.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Inventory record with ID {td.id} not found"
    # Then 4
    assert snap(db, td) == before_td


# [claude] INVS-G-05
@xfail(3082)
def test_invs_g_05__bug_3082_include_deleted_true_returns_a_soft_deleted_row(db, g, w1):
    """INVS-G-05 — BUG-3082: include_deleted=True returns a soft-deleted row of the workspace.
    Rules: `get_inventory` R3 [BUG-3082]
    Note: Remove the xfail only after BUG-700 is fixed too. A BUG-3082 fix that ignores
    `include_deleted` would still pass these cards; only G-04 catches it."""
    td = g.inv(**g.gone())
    commit_point(db)
    result = svc.get_inventory(db, inv_id=td.id, workspace_id=w1.id, include_deleted=True)
    # Then 1
    assert result.id == td.id
    # Then 2
    assert result.is_deleted is True
    assert result.qty == 10


# [claude] INVS-G-06
@xfail(3082)
def test_invs_g_06__bug_3082_include_deleted_true_does_not_reach_another_workspace(db, g, w1):
    """INVS-G-06 — BUG-3082: include_deleted=True does not reach another workspace.
    Rules: `get_inventory` R3 [BUG-3082], Errors
    Note: Remove the xfail only after BUG-700 is fixed too. A BUG-3082 fix that ignores
    `include_deleted` would still pass these cards; only G-04 catches it."""
    fx = g.fx()
    ix = g.ix()
    zd = g.foreign(ix, fx, **g.gone())
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_inventory(db, inv_id=zd.id, workspace_id=w1.id, include_deleted=True)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Inventory record with ID {zd.id} not found"


# [claude] INVS-G-07
@xfail(3082)
def test_invs_g_07__bug_3082_include_deleted_false_returns_a_live_row(db, g, w1):
    """INVS-G-07 — BUG-3082: include_deleted=False returns a live row.
    Rules: `get_inventory` Inputs, R1 [BUG-3082]
    Note: Remove the xfail only after BUG-700 is fixed too. A BUG-3082 fix that ignores
    `include_deleted` would still pass these cards; only G-04 catches it."""
    t = g.inv()
    commit_point(db)
    result = svc.get_inventory(db, inv_id=t.id, workspace_id=w1.id, include_deleted=False)
    # Then 1
    assert result.id == t.id


# [claude] INVS-G-08
def test_invs_g_08__a_soft_deleted_row_of_another_workspace_stays_404(db, g, w1):
    """INVS-G-08 — a soft-deleted row of another workspace stays 404 by default.
    Rules: `get_inventory` R1, R3 (holds today and after the fix)"""
    fx = g.fx()
    ix = g.ix()
    zd = g.foreign(ix, fx, **g.gone())
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_inventory(db, inv_id=zd.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Inventory record with ID {zd.id} not found"


# [claude] INVS-G-09
def test_invs_g_09__the_read_neither_commits_nor_rolls_back(db, g, w1):
    """INVS-G-09 — the read neither commits nor rolls back.
    Rules: `get_inventory` R4; TC6"""
    t = g.inv()
    i2 = g.i2()
    b = g.inv(item_id=i2.id)
    commit_point(db)
    x_id = mk_x(db)
    b.note = "Edited"
    with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:
        result = svc.get_inventory(db, inv_id=t.id, workspace_id=w1.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert b in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert x_there(db, x_id)
    # Then 7
    db.rollback()
    assert x_gone(db, x_id)
    # Then 8
    assert reread(db, b).note == "n1"


# [claude] INVS-G-10
def test_invs_g_10__a_404_from_the_manager_passes_with_no_rollback(db, g, w1):
    """INVS-G-10 — a 404 from the manager passes unchanged with no rollback.
    Rules: `get_inventory` R4; TC6"""
    g.inv()
    commit_point(db)
    x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with patch.object(db, "commit", wraps=db.commit) as cm, \
                patch.object(db, "rollback", wraps=db.rollback) as rb:
            svc.get_inventory(db, inv_id=MISSING, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert rb.call_count == 0
    # Then 5
    assert x_there(db, x_id)


# --------------------------------------------------------------------------- #
# InventoryService.get_inventory_page
# --------------------------------------------------------------------------- #

# [claude] INVS-P-01
def test_invs_p_01__defaults_live_rows_with_qty_above_0_skip_0_limit_50(db, g, w1):
    """INVS-P-01 — with the defaults: live rows of the workspace with qty > 0, skip 0, limit 50.
    Rules: `get_inventory_page` R1"""
    i2 = g.i2()
    fx = g.fx()
    ix = g.ix()
    g.inv(item_id=i2.id, qty=0)
    a = g.inv()
    g.foreign(ix, fx)
    commit_point(db)
    result = svc.get_inventory_page(db, workspace_id=w1.id)
    # Then 1
    assert [r.id for r in result.items] == [a.id]
    # Then 2
    assert result.total == 1
    # Then 3
    assert result.skip == 0
    assert result.limit == 50
    assert result.has_more is False


# [claude] INVS-P-02
def test_invs_p_02__inventory_type_reaches_the_manager(db, g, w1):
    """INVS-P-02 — inventory_type reaches the manager.
    Rules: `get_inventory_page` R1"""
    b = g.inv(inventory_type=DAMAGED)
    g.inv()
    commit_point(db)
    result = svc.get_inventory_page(db, workspace_id=w1.id, inventory_type=DAMAGED)
    # Then 1
    assert [r.id for r in result.items] == [b.id]
    # Then 2
    assert result.total == 1


# [claude] INVS-P-03
def test_invs_p_03__factory_id_reaches_the_manager(db, g, w1):
    """INVS-P-03 — factory_id reaches the manager.
    Rules: `get_inventory_page` R1"""
    f2 = g.f2()
    b = g.inv(factory_id=f2.id)
    g.inv()
    commit_point(db)
    result = svc.get_inventory_page(db, workspace_id=w1.id, factory_id=f2.id)
    # Then 1
    assert [r.id for r in result.items] == [b.id]
    # Then 2
    assert result.total == 1


# [claude] INVS-P-04
def test_invs_p_04__item_id_reaches_the_manager(db, g, w1):
    """INVS-P-04 — item_id reaches the manager.
    Rules: `get_inventory_page` R1"""
    i2 = g.i2()
    b = g.inv(item_id=i2.id)
    g.inv()
    commit_point(db)
    result = svc.get_inventory_page(db, workspace_id=w1.id, item_id=i2.id)
    # Then 1
    assert [r.id for r in result.items] == [b.id]
    # Then 2
    assert result.total == 1


# [claude] INVS-P-05
def test_invs_p_05__search_reaches_the_manager(db, g, w1):
    """INVS-P-05 — search reaches the manager (text in the middle, other case).
    Rules: `get_inventory_page` R1 (holds today and after BUG-702)"""
    i2 = g.i2()
    b = g.inv(item_id=i2.id)
    g.inv()
    commit_point(db)
    result = svc.get_inventory_page(db, workspace_id=w1.id, search="X NU")
    # Then 1
    assert [r.id for r in result.items] == [b.id]
    # Then 2
    assert result.total == 1


# [claude] INVS-P-06
def test_invs_p_06__include_zero_qty_true_reaches_the_manager(db, g, w1):
    """INVS-P-06 — include_zero_qty=True reaches the manager.
    Rules: `get_inventory_page` R1"""
    i2 = g.i2()
    b = g.inv(item_id=i2.id, qty=0)
    a = g.inv()
    commit_point(db)
    result = svc.get_inventory_page(db, workspace_id=w1.id, include_zero_qty=True)
    # Then 1
    assert sorted(r.id for r in result.items) == sorted([a.id, b.id])
    # Then 2
    assert result.total == 2


# [claude] INVS-P-07
def test_invs_p_07__skip_and_limit_reach_the_manager_and_are_echoed(db, g, w1):
    """INVS-P-07 — skip and limit reach the manager and are echoed.
    Rules: `get_inventory_page` R1"""
    i2 = g.i2()
    i3 = g.i3()
    g.inv(item_id=i3.id)
    g.inv()
    rh = g.inv(item_id=i2.id)
    commit_point(db)
    result = svc.get_inventory_page(db, workspace_id=w1.id, skip=1, limit=1)
    # Then 1
    assert [r.id for r in result.items] == [rh.id]
    # Then 2
    assert result.total == 3
    # Then 3
    assert result.skip == 1
    assert result.limit == 1
    assert result.has_more is True


# [claude] INVS-P-08
def test_invs_p_08__limit_1000_reaches_the_manager(db, g, w1):
    """INVS-P-08 — limit=1000 reaches the manager.
    Rules: `get_inventory_page` R1"""
    i2 = g.i2()
    i3 = g.i3()
    rw = g.inv(item_id=i3.id)
    g.inv()
    rh = g.inv(item_id=i2.id)
    commit_point(db)
    result = svc.get_inventory_page(db, workspace_id=w1.id, skip=1, limit=1000)
    # Then 1
    assert [r.id for r in result.items] == [rh.id, rw.id]
    # Then 2
    assert result.limit == 1000
    assert result.has_more is False


# [claude] INVS-P-09
def test_invs_p_09__the_default_limit_is_50(db, g, w1):
    """INVS-P-09 — the default limit is 50: 51 rows give 50.
    Rules: `get_inventory_page` R1"""
    items = [Item(**_item_fields(w1, {"name": f"Part {k:02d}", "unit": "pcs"})) for k in range(1, 52)]
    db.add_all(items)
    db.flush()
    db.add_all([Inventory(**g.inv_fields({"item_id": it.id})) for it in items])
    db.flush()
    commit_point(db)
    result = svc.get_inventory_page(db, workspace_id=w1.id)
    # Then 1
    assert len(result.items) == 50
    # Then 2
    assert result.total == 51
    # Then 3
    assert result.limit == 50
    assert result.has_more is True


# [claude] INVS-P-10
def test_invs_p_10__rows_come_in_item_name_order_ignoring_case(db, g, w1):
    """INVS-P-10 — rows come in item-name order ignoring case.
    Rules: `get_inventory_page` R1 (holds today and after BUG-701)"""
    ic = g.item(name="Cog")
    ia = g.item(name="apple")
    rc = g.inv(item_id=ic.id)
    rb = g.inv()
    ra = g.inv(item_id=ia.id)
    commit_point(db)
    result = svc.get_inventory_page(db, workspace_id=w1.id)
    # Then 1
    assert [r.id for r in result.items] == [ra.id, rb.id, rc.id]


# [claude] INVS-P-11
@xfail(701)
def test_invs_p_11__bug_701_a_case_only_tie_is_broken_by_inventory_id(db, g, w1):
    """INVS-P-11 — pass-through BUG-701: a case-only tie is broken by inventory id.
    Rules: `get_inventory_page` R1 [BUG-701]"""
    iu = g.item(name="Apple")
    il = g.item(name="apple")
    ru = g.inv(item_id=iu.id)
    rl = g.inv(item_id=il.id)
    commit_point(db)
    result = svc.get_inventory_page(db, workspace_id=w1.id)
    # Then 1
    assert len(result.items) == 2
    # Then 2
    assert [r.id for r in result.items] == [ru.id, rl.id]


# [claude] INVS-P-12
@xfail(702)
def test_invs_p_12__bug_702_percent_is_literal_and_matches_nothing(db, g, w1):
    """INVS-P-12 — pass-through BUG-702: "%" is literal and matches nothing.
    Rules: `get_inventory_page` R1 [BUG-702]"""
    i2 = g.i2()
    g.inv()
    g.inv(item_id=i2.id)
    commit_point(db)
    result = svc.get_inventory_page(db, workspace_id=w1.id, search="%")
    # Then 1
    assert result.total == 0
    # Then 2
    assert result.items == []


# [claude] INVS-P-13
def test_invs_p_13__the_list_neither_commits_nor_rolls_back(db, g, w1):
    """INVS-P-13 — the list neither commits nor rolls back.
    Rules: `get_inventory_page` R2; TC6"""
    a = g.inv()
    commit_point(db)
    x_id = mk_x(db)
    a.note = "Edited"
    with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:
        result = svc.get_inventory_page(db, workspace_id=w1.id)
    # Then 1
    assert [r.id for r in result.items] == [a.id]
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert a in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert x_there(db, x_id)
    # Then 7
    db.rollback()
    assert x_gone(db, x_id)
    # Then 8
    assert reread(db, a).note == "n1"


# [claude] INVS-P-14
def test_invs_p_14__a_soft_deleted_row_is_left_out(db, g, w1):
    """INVS-P-14 — a soft-deleted row is left out.
    Rules: `get_inventory_page` R1"""
    i2 = g.i2()
    g.inv(item_id=i2.id, **g.gone())
    a = g.inv()
    commit_point(db)
    result = svc.get_inventory_page(db, workspace_id=w1.id)
    # Then 1
    assert [r.id for r in result.items] == [a.id]
    # Then 2
    assert result.total == 1


# --------------------------------------------------------------------------- #
# InventoryService.get_inventory_stats
# --------------------------------------------------------------------------- #

# [claude] INVS-S-01
def test_invs_s_01__defaults_totals_of_live_rows_with_qty_above_0(db, g, w1):
    """INVS-S-01 — with the defaults: totals of the workspace's live rows with qty > 0.
    Rules: `get_inventory_stats` R1"""
    i2 = g.i2()
    i3 = g.i3()
    fx = g.fx()
    ix = g.ix()
    g.inv()
    g.inv(item_id=i2.id, qty=4, avg_price=Decimal("2.50"))
    g.inv(item_id=i3.id, qty=0)
    g.foreign(ix, fx)
    commit_point(db)
    result = svc.get_inventory_stats(db, workspace_id=w1.id)
    # Then 1
    assert result.records == 2
    assert result.total_qty == 14
    # Then 2
    assert result.estimated_value == Decimal("60.00")
    # Then 3
    assert len(result.by_type) == 1
    # Then 4
    assert result.by_type[0].inventory_type == STORAGE
    assert result.by_type[0].unique_item_count == 2
    assert result.by_type[0].total_qty == 14


# [claude] INVS-S-02
def test_invs_s_02__inventory_type_reaches_the_manager(db, g, w1):
    """INVS-S-02 — inventory_type reaches the manager.
    Rules: `get_inventory_stats` R1"""
    g.inv()
    g.inv(inventory_type=DAMAGED, qty=3)
    commit_point(db)
    result = svc.get_inventory_stats(db, workspace_id=w1.id, inventory_type=DAMAGED)
    # Then 1
    assert result.records == 1
    assert result.total_qty == 3


# [claude] INVS-S-03
def test_invs_s_03__factory_id_reaches_the_manager(db, g, w1):
    """INVS-S-03 — factory_id reaches the manager.
    Rules: `get_inventory_stats` R1"""
    f2 = g.f2()
    g.inv()
    g.inv(factory_id=f2.id, qty=3)
    commit_point(db)
    result = svc.get_inventory_stats(db, workspace_id=w1.id, factory_id=f2.id)
    # Then 1
    assert result.records == 1
    assert result.total_qty == 3


# [claude] INVS-S-04
def test_invs_s_04__item_id_reaches_the_manager(db, g, w1):
    """INVS-S-04 — item_id reaches the manager.
    Rules: `get_inventory_stats` R1"""
    i2 = g.i2()
    g.inv()
    g.inv(item_id=i2.id, qty=3)
    commit_point(db)
    result = svc.get_inventory_stats(db, workspace_id=w1.id, item_id=i2.id)
    # Then 1
    assert result.records == 1
    assert result.total_qty == 3


# [claude] INVS-S-05
def test_invs_s_05__search_reaches_the_manager(db, g, w1):
    """INVS-S-05 — search reaches the manager (text in the middle, other case).
    Rules: `get_inventory_stats` R1 (holds today and after BUG-702)"""
    i2 = g.i2()
    g.inv()
    g.inv(item_id=i2.id, qty=3)
    commit_point(db)
    result = svc.get_inventory_stats(db, workspace_id=w1.id, search="X NU")
    # Then 1
    assert result.records == 1
    assert result.total_qty == 3


# [claude] INVS-S-06
def test_invs_s_06__include_zero_qty_true_reaches_the_manager(db, g, w1):
    """INVS-S-06 — include_zero_qty=True reaches the manager.
    Rules: `get_inventory_stats` R1"""
    i2 = g.i2()
    g.inv()
    g.inv(item_id=i2.id, qty=0)
    commit_point(db)
    result = svc.get_inventory_stats(db, workspace_id=w1.id, include_zero_qty=True)
    # Then 1
    assert result.records == 2
    assert result.total_qty == 10


# [claude] INVS-S-07
def test_invs_s_07__no_matching_rows_zero_totals_and_an_empty_breakdown(db, w1):
    """INVS-S-07 — no matching rows: zero totals and an empty breakdown.
    Rules: `get_inventory_stats` R1"""
    commit_point(db)
    result = svc.get_inventory_stats(db, workspace_id=w1.id)
    # Then 1
    assert result.records == 0
    assert result.total_qty == 0
    # Then 2
    assert result.estimated_value == Decimal("0")
    # Then 3
    assert result.by_type == []


# [claude] INVS-S-08
@xfail(702)
def test_invs_s_08__bug_702_underscore_is_literal_and_matches_nothing(db, g, w1):
    """INVS-S-08 — pass-through BUG-702: "_" is literal and matches nothing.
    Rules: `get_inventory_stats` R1 [BUG-702]"""
    i2 = g.i2()
    g.inv()
    g.inv(item_id=i2.id, qty=3)
    commit_point(db)
    result = svc.get_inventory_stats(db, workspace_id=w1.id, search="_")
    # Then 1
    assert result.records == 0
    # Then 2
    assert result.total_qty == 0


# [claude] INVS-S-09
@xfail(719, strict=False)
def test_invs_s_09__bug_719_the_breakdown_comes_in_enum_order(db, g, w1):
    """INVS-S-09 — pass-through BUG-719: the breakdown comes in enum order.
    Rules: `get_inventory_stats` R1 [BUG-719]"""
    g.inv(inventory_type=SCRAP)
    g.inv(inventory_type=WASTE)
    g.inv(inventory_type=DAMAGED)
    g.inv()
    commit_point(db)
    result = svc.get_inventory_stats(db, workspace_id=w1.id)
    # Then 1
    assert len(result.by_type) == 4
    # Then 2
    assert [e.inventory_type for e in result.by_type] == [STORAGE, DAMAGED, WASTE, SCRAP]


# [claude] INVS-S-10
def test_invs_s_10__the_stats_neither_commit_nor_roll_back(db, g, w1):
    """INVS-S-10 — the stats neither commit nor roll back.
    Rules: `get_inventory_stats` R2; TC6"""
    a = g.inv()
    commit_point(db)
    x_id = mk_x(db)
    a.qty = 99
    with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:
        result = svc.get_inventory_stats(db, workspace_id=w1.id)
    # Then 1
    assert result.records == 1
    assert result.total_qty == 10
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert a in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert x_there(db, x_id)
    # Then 7
    db.rollback()
    assert x_gone(db, x_id)
    # Then 8
    assert reread(db, a).qty == 10


# --------------------------------------------------------------------------- #
# InventoryService.get_incoming_summary
# --------------------------------------------------------------------------- #

# [claude] INVS-IS-01
def test_invs_is_01__one_factory_its_open_po_line_is_summarised(db, g, w1, f1, i1):
    """INVS-IS-01 — one factory: its open PO line is summarised, the other factory's is not.
    Rules: `get_incoming_summary` R1"""
    s_open, _s_done, wf = g.flow()
    f2 = g.f2()
    p1 = g.po(1, f1, s_open, wf)
    g.line(p1)
    p2 = g.po(2, f2, s_open, wf)
    g.line(p2)
    commit_point(db)
    result = svc.get_incoming_summary(db, workspace_id=w1.id, factory_id=f1.id)
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].factory_id == f1.id
    assert result[0].item_id == i1.id
    # Then 3
    assert result[0].total_pending_qty == Decimal("7")
    assert result[0].order_count == 1
    # Then 4
    assert len(result[0].orders) == 1
    # Then 5
    order = result[0].orders[0]
    assert order.order_kind == "purchase"
    assert order.order_id == p1.id
    assert order.order_number == f"PO-INVS-{SFX}-1"
    assert order.status_name == "Ordered"
    assert order.pending_qty == Decimal("7")


# [claude] INVS-IS-02
def test_invs_is_02__factory_id_none_covers_every_active_factory(db, g, w1, f1, i1):
    """INVS-IS-02 — factory_id=None covers every active factory of the workspace.
    Rules: `get_incoming_summary` R1"""
    s_open, _s_done, wf = g.flow()
    f2 = g.f2()
    p1 = g.po(1, f1, s_open, wf)
    g.line(p1)
    p2 = g.po(2, f2, s_open, wf)
    g.line(p2)
    commit_point(db)
    result = svc.get_incoming_summary(db, workspace_id=w1.id)
    # Then 1
    assert len(result) == 2
    # Then 2
    assert {(r.factory_id, r.item_id) for r in result} == {(f1.id, i1.id), (f2.id, i1.id)}


# [claude] INVS-IS-03
def test_invs_is_03__factory_id_0_gets_the_404(db, g, w1, f1):
    """INVS-IS-03 — factory_id=0 gets the 404.
    Rules: `get_incoming_summary` R1, R2, Errors"""
    s_open, _s_done, wf = g.flow()
    p1 = g.po(1, f1, s_open, wf)
    g.line(p1)
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_incoming_summary(db, workspace_id=w1.id, factory_id=0)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory with ID 0 not found"


# [claude] INVS-IS-04
def test_invs_is_04__another_workspaces_factory_gets_the_404(db, g, w1):
    """INVS-IS-04 — another workspace's factory gets the 404.
    Rules: `get_incoming_summary` R2, Errors"""
    fx = g.fx()
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_incoming_summary(db, workspace_id=w1.id, factory_id=fx.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory with ID {fx.id} not found"


# [claude] INVS-IS-05
@xfail(718)
def test_invs_is_05__bug_718_a_soft_deleted_factory_gets_the_404(db, g, w1):
    """INVS-IS-05 — pass-through BUG-718: a soft-deleted factory gets the 404.
    Rules: `get_incoming_summary` R1 [BUG-718], R2"""
    s_open, _s_done, wf = g.flow()
    fd = g.fd()
    p1 = g.po(1, fd, s_open, wf)
    g.line(p1)
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_incoming_summary(db, workspace_id=w1.id, factory_id=fd.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory with ID {fd.id} not found"


# [claude] INVS-IS-06
def test_invs_is_06__an_inactive_but_live_factory_is_still_summarised(db, g, w1):
    """INVS-IS-06 — an inactive but live factory is still summarised.
    Rules: `get_incoming_summary` R1 (holds today and after BUG-718)"""
    s_open, _s_done, wf = g.flow()
    fi = g.fi()
    p1 = g.po(1, fi, s_open, wf)
    g.line(p1)
    commit_point(db)
    result = svc.get_incoming_summary(db, workspace_id=w1.id, factory_id=fi.id)
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].factory_id == fi.id
    assert result[0].total_pending_qty == Decimal("7")


# [claude] INVS-IS-07
@xfail(717)
def test_invs_is_07__bug_717_a_voided_po_is_not_incoming(db, g, w1, f1):
    """INVS-IS-07 — pass-through BUG-717: a voided PO is not incoming.
    Rules: `get_incoming_summary` R1 [BUG-717]"""
    s_open, _s_done, wf = g.flow()
    p1 = g.po(1, f1, s_open, wf)
    g.line(p1)
    pv = g.po(2, f1, s_open, wf, voided=True)
    g.line(pv, quantity_ordered=Decimal("8"), quantity_received=Decimal("0"))
    commit_point(db)
    result = svc.get_incoming_summary(db, workspace_id=w1.id, factory_id=f1.id)
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].total_pending_qty == Decimal("7")
    assert result[0].order_count == 1
    # Then 3
    assert [o.order_id for o in result[0].orders] == [p1.id]


# [claude] INVS-IS-08
def test_invs_is_08__the_summary_neither_commits_nor_rolls_back(db, g, w1, f1):
    """INVS-IS-08 — the summary neither commits nor rolls back.
    Rules: `get_incoming_summary` R3; TC6"""
    s_open, _s_done, wf = g.flow()
    p1 = g.po(1, f1, s_open, wf)
    g.line(p1)
    t = g.inv()
    commit_point(db)
    x_id = mk_x(db)
    t.note = "Edited"
    with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:
        result = svc.get_incoming_summary(db, workspace_id=w1.id, factory_id=f1.id)
    # Then 1
    assert len(result) == 1
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert t in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert x_there(db, x_id)
    # Then 7
    db.rollback()
    assert x_gone(db, x_id)
    # Then 8
    assert reread(db, t).note == "n1"


# [claude] INVS-IS-09
@xfail(706, strict=False)
def test_invs_is_09__bug_706_factories_come_in_name_order_ignoring_case(db, g, w1, f1):
    """INVS-IS-09 — pass-through BUG-706: factories come in name order ignoring case.
    Rules: `get_incoming_summary` R1 [BUG-706]"""
    s_open, _s_done, wf = g.flow()
    fa = g.factory(name="alpha Plant", abbreviation="ALP")
    p1 = g.po(1, f1, s_open, wf)
    g.line(p1)
    p2 = g.po(2, fa, s_open, wf)
    g.line(p2)
    commit_point(db)
    result = svc.get_incoming_summary(db, workspace_id=w1.id)
    # Then 1
    assert len(result) == 2
    # Then 2
    assert [r.factory_id for r in result] == [fa.id, f1.id]


# [claude] INVS-IS-10
def test_invs_is_10__a_404_from_the_manager_passes_with_no_rollback(db, g, w1):
    """INVS-IS-10 — a 404 from the manager passes unchanged with no rollback.
    Rules: `get_incoming_summary` R2, R3; TC6"""
    g.inv()
    commit_point(db)
    x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with patch.object(db, "commit", wraps=db.commit) as cm, \
                patch.object(db, "rollback", wraps=db.rollback) as rb:
            svc.get_incoming_summary(db, workspace_id=w1.id, factory_id=0)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert rb.call_count == 0
    # Then 5
    assert x_there(db, x_id)


# --------------------------------------------------------------------------- #
# InventoryService.delete_inventory
# --------------------------------------------------------------------------- #

# [claude] INVS-D-01
def test_invs_d_01__clear_stock_is_committed_with_its_ledger_entry(db, g, w1, u1):
    """INVS-D-01 — clear stock is committed with its ledger entry; the row stays live.
    Rules: `delete_inventory` R1, Returns; TC1, TC2"""
    t = g.inv()
    commit_point(db)
    result = svc.delete_inventory(db, inv_id=t.id, workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == t.id
    assert result.qty == 0
    assert result.is_deleted is False
    assert result.updated_at is not None
    # Then 3
    db.rollback()
    row = reread(db, t)
    assert row.qty == 0
    assert row.updated_by == u1.id
    assert row.is_deleted is False
    assert row.is_active is True
    # Then 4
    row = reread(db, t)
    assert row.avg_price == Decimal("5.00")
    assert row.note == "n1"
    # Then 5
    assert len(ledger(db, t)) == 1
    # Then 6
    entry = ledger(db, t)[0]
    assert entry.transaction_type == "inventory_adjustment"
    assert entry.quantity == 10
    assert entry.qty_before == 10
    assert entry.qty_after == 0
    assert entry.total_cost == Decimal("50.00")
    assert entry.notes == "Stock cleared"
    assert entry.performed_by == u1.id


# [claude] INVS-D-02
def test_invs_d_02__qty_already_0_committed_unchanged_no_ledger_entry(db, g, w1, u1):
    """INVS-D-02 — qty already 0: committed, returned unchanged, no ledger entry.
    Rules: `delete_inventory` R2 (holds today and after BUG-716)"""
    t = g.inv(qty=0)
    commit_point(db)
    x_id = mk_x(db)
    result = svc.delete_inventory(db, inv_id=t.id, workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.id == t.id
    assert result.qty == 0
    # Then 2
    db.rollback()
    assert x_there(db, x_id)
    # Then 3
    row = reread(db, t)
    assert row.qty == 0
    assert row.updated_by is None
    # Then 4
    assert len(ledger(db, t)) == 0


# [claude] INVS-D-03
def test_invs_d_03__another_workspaces_row_404_pending_row_discarded(db, g, w1, u1):
    """INVS-D-03 — another workspace's row: the 404 passes unchanged, the pending row is discarded.
    Rules: `delete_inventory` R3, Errors; TC3"""
    fx = g.fx()
    ix = g.ix()
    tx = g.foreign(ix, fx)
    commit_point(db)
    before_tx = snap_before(db, tx)
    x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_inventory(db, inv_id=tx.id, workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Inventory record with ID {tx.id} not found"
    # Then 4
    assert not db.new
    assert not db.dirty
    # Then 5
    assert x_gone(db, x_id)
    # Then 6
    assert snap(db, tx) == before_tx
    # Then 7
    assert len(ledger(db, tx)) == 0
    # Then 8
    assert usable(db)


# [claude] INVS-D-04
def test_invs_d_04__an_unknown_id_404_pending_row_discarded(db, g, w1, u1):
    """INVS-D-04 — an unknown id: the 404 passes unchanged, the pending row is discarded.
    Rules: `delete_inventory` R3, Errors; TC3"""
    t = g.inv()
    commit_point(db)
    before_t = snap_before(db, t)
    x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_inventory(db, inv_id=MISSING, workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Inventory record with ID 999999999 not found"
    # Then 4
    assert x_gone(db, x_id)
    # Then 5
    assert snap(db, t) == before_t


# [claude] INVS-D-05
def test_invs_d_05__a_soft_deleted_row_400_pending_row_discarded(db, g, w1, u1):
    """INVS-D-05 — a soft-deleted row: the 400 passes unchanged, the pending row is discarded.
    Rules: `delete_inventory` R3, Errors; TC3"""
    td = g.inv(**g.gone())
    commit_point(db)
    before_td = snap_before(db, td)
    x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_inventory(db, inv_id=td.id, workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot clear stock on a deactivated inventory record"
    # Then 4
    assert x_gone(db, x_id)
    # Then 5
    assert snap(db, td) == before_td
    # Then 6
    assert len(ledger(db, td)) == 0


# [claude] INVS-D-06
def test_invs_d_06__a_failing_commit_is_rolled_back(db, g, w1, u1):
    """INVS-D-06 — a failing commit is rolled back: qty, ledger and pending row not saved.
    Rules: `delete_inventory` R4; TC4"""
    t = g.inv()
    commit_point(db)
    before_t = snap_before(db, t)
    x_id = mk_x(db)
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "commit", side_effect=RuntimeError("boom")), \
                patch.object(db, "rollback", wraps=db.rollback) as rb:
            svc.delete_inventory(db, inv_id=t.id, workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert x_gone(db, x_id)
    # Then 4
    assert snap(db, t) == before_t
    # Then 5
    assert len(ledger(db, t)) == 0


# [claude] INVS-D-07
def test_invs_d_07__a_failing_re_read_after_the_commit_leaves_the_clear_saved(db, g, w1, u1):
    """INVS-D-07 — a failing re-read after the commit leaves the clear saved.
    Rules: `delete_inventory` R4; TC5"""
    t = g.inv()
    commit_point(db)
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "refresh", side_effect=RuntimeError("boom")):
            svc.delete_inventory(db, inv_id=t.id, workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    db.rollback()
    assert reread(db, t).qty == 0
    # Then 3
    assert len(ledger(db, t)) == 1


# [claude] INVS-D-08
@xfail(716)
def test_invs_d_08__bug_716_a_negative_quantity_is_cleared_to_0(db, g, w1, u1):
    """INVS-D-08 — pass-through BUG-716: a negative quantity is cleared to 0 with a ledger entry.
    Rules: `delete_inventory` R1 [BUG-716]"""
    t = g.inv(qty=-4)
    commit_point(db)
    result = svc.delete_inventory(db, inv_id=t.id, workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    db.rollback()
    row = reread(db, t)
    assert row.qty == 0
    assert row.updated_by == u1.id
    # Then 3
    assert len(ledger(db, t)) == 1
    # Then 4
    entry = ledger(db, t)[0]
    assert entry.quantity == 4
    assert entry.qty_before == -4
    assert entry.qty_after == 0
    assert entry.notes == "Stock cleared"


# [claude] INVS-D-09
@xfail(705)
def test_invs_d_09__bug_705_the_row_is_read_for_update_of_inventory(db, g, w1, u1):
    """INVS-D-09 — pass-through BUG-705: the row is read with FOR UPDATE OF inventory.
    Rules: `delete_inventory` R1a [BUG-705]"""
    t = g.inv()
    commit_point(db)
    with Recorder(db) as rec:
        result = svc.delete_inventory(db, inv_id=t.id, workspace_id=w1.id, user_id=u1.id)
    inv_selects = rec.inv_selects
    # Then 1
    assert result.qty == 0
    # Then 2
    assert any(s.rstrip().endswith("FOR UPDATE OF inventory") for s in inv_selects)
    # Then 3
    assert not any("NOWAIT" in s or "SKIP LOCKED" in s for s in inv_selects)


# [claude] INVS-D-10
@xfail(707)
def test_invs_d_10__bug_707_a_clear_at_price_0_00_gives_total_cost_0_00(db, g, w1, u1):
    """INVS-D-10 — pass-through BUG-707: a clear at price 0.00 gives total_cost 0.00.
    Rules: `delete_inventory` R1 [BUG-707]"""
    t = g.inv(avg_price=Decimal("0.00"))
    commit_point(db)
    result = svc.delete_inventory(db, inv_id=t.id, workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.qty == 0
    # Then 2
    db.rollback()
    assert len(ledger(db, t)) == 1
    # Then 3
    assert ledger(db, t)[0].total_cost == Decimal("0.00")


# [claude] INVS-D-11
def test_invs_d_11__a_successful_clear_also_commits_a_pending_change(db, g, w1, u1):
    """INVS-D-11 — a successful clear also commits a change already pending in the session.
    Rules: `delete_inventory` R1; TC1"""
    t = g.inv()
    commit_point(db)
    x_id = mk_x(db)
    result = svc.delete_inventory(db, inv_id=t.id, workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.qty == 0
    # Then 2
    db.rollback()
    assert x_there(db, x_id)
    # Then 3
    assert reread(db, t).qty == 0
