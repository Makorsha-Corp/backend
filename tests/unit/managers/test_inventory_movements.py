"""Unit tests for app/managers/inventory_movements.py.

Implements tests/unit/managers/inventory_movements.cases.md (revision 4), one
test per case. Real Postgres session (`db` fixture). This module has no
`utcnow` of its own: the only externals are the SQLAlchemy column defaults on
`MachineItemLedger.performed_at` and `MachineActivityEvent.created_at`, frozen
by patching each default's `arg` callable (spec Notes). Factory-ledger
`performed_at` is the DB's `now()` and cannot be frozen; it is asserted
"not None and > T1" instead. SQL-capture (BUG-660/661 lock cases) follows the
`payment_transaction_manager` RR-08 pattern.
"""
# ruff: noqa: SIM117, DTZ001, FURB157  (prescribed by the cards: nested with, naive datetimes, Decimal("...") literals)
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import event, or_, select, text
from sqlalchemy.exc import DataError, IntegrityError

from app.managers.inventory_movements import (
    _machine_in,
    _machine_out,
    _storage_in,
    _storage_out,
    ensure_machine_item,
    get_machine_unit_cost,
    inventory_type_for_location,
    item_name,
    post_stock_in,
    post_stock_out,
    weighted_avg_price,
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
from app.utils.item_name_normalize import normalize_item_name
from tests.unit.factories import make_profile, make_workspace

STORAGE = InventoryTypeEnum.STORAGE
DAMAGED = InventoryTypeEnum.DAMAGED

# --------------------------------------------------------------------------- #
# Conventions -> module constants / fixtures / helpers
# --------------------------------------------------------------------------- #

# Convention "T0, T1, NOW"
T0 = datetime(2025, 1, 1, 8, 0, 0)
T1 = datetime(2025, 2, 1, 8, 0, 0)
NOW = datetime(2026, 9, 27, 12, 0, 0)

# Convention "NOID"
NOID = 999999999

# Convention "Long strings"
S50 = "x" * 50
S51 = "x" * 51

BUG_660 = "BUG-660: the factory stock row is not read with SELECT ... FOR UPDATE (HR-10)"
BUG_661 = "BUG-661: the machine-item row is not read with SELECT ... FOR UPDATE (HR-10)"
BUG_662 = "BUG-662: a soft-deleted factory is accepted as a stock location (HR-4)"
BUG_663 = "BUG-663: a soft-deleted machine is accepted as a stock location (HR-4)"
BUG_664 = "BUG-664: latest-ledger tie-break picks the physically first-inserted row, not the greatest id"
BUG_665 = "BUG-665: qty < 1 is accepted by post_stock_out/post_stock_in instead of rejected"
BUG_666 = "BUG-666: the item is never checked to belong to the workspace"
BUG_1040 = "BUG-1040: money rounded half to even in Python, half away from zero in the database"


# Convention "Time": freeze NOW at the MachineItemLedger.performed_at /
# MachineActivityEvent.created_at column defaults (module has no utcnow).
# SQLAlchemy memoizes each column's default on first insert, so the memo is cleared
# on both sides: without that the freeze fails once another test file has inserted.
@pytest.fixture(autouse=True)
def _freeze_now():
    columns = (MachineItemLedger.__table__.c.performed_at, MachineActivityEvent.__table__.c.created_at)
    with patch.object(columns[0].default, "arg", lambda ctx: NOW), \
         patch.object(columns[1].default, "arg", lambda ctx: NOW):
        for column in columns:
            column.__dict__.pop("_default_description_tuple", None)
        yield
    for column in columns:
        column.__dict__.pop("_default_description_tuple", None)


# Convention "W1, W2 = two workspaces"
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db):
    return make_workspace(db)


# Convention "U1, U2 = two profiles"
@pytest.fixture
def u1(db):
    return make_profile(db)


@pytest.fixture
def u2(db):
    return make_profile(db)


# Convention "F1, F1b, F2, F3": factories (local model, not in tests/unit/factories.py).
def _mk_factory(db, ws, name, *, deleted=False):
    row = Factory(
        workspace_id=ws.id, name=name, abbreviation=name[:3].upper(),
        is_deleted=deleted, is_active=not deleted,
    )
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def f1(db, w1):
    return _mk_factory(db, w1, "Factory 1")


@pytest.fixture
def f1b(db, w1):
    return _mk_factory(db, w1, "Factory 1b")


@pytest.fixture
def f2(db, w2):
    return _mk_factory(db, w2, "Factory 2")


@pytest.fixture
def f3(db, w1):
    return _mk_factory(db, w1, "Factory 3", deleted=True)


# Convention "M1, M1b, M2, M3": machines.
def _mk_machine(db, ws, factory, name, *, deleted=False):
    row = Machine(
        workspace_id=ws.id, factory_id=factory.id, name=name,
        is_deleted=deleted, is_active=not deleted,
    )
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def m1(db, w1, f1):
    return _mk_machine(db, w1, f1, "Machine 1")


@pytest.fixture
def m1b(db, w1, f1):
    return _mk_machine(db, w1, f1, "Machine 1b")


@pytest.fixture
def m2(db, w2, f2):
    return _mk_machine(db, w2, f2, "Machine 2")


@pytest.fixture
def m3(db, w1, f1):
    return _mk_machine(db, w1, f1, "Machine 3", deleted=True)


# Convention "I1, I2, IX, I_OFF": items.
def _mk_item(db, ws, name, *, active=True):
    row = Item(
        workspace_id=ws.id, name=name, name_normalized=normalize_item_name(name),
        unit="pcs", is_active=active,
    )
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def i1(db, w1):
    return _mk_item(db, w1, "Bearing 6204")


@pytest.fixture
def i2(db, w1):
    return _mk_item(db, w1, "V-Belt A42")


@pytest.fixture
def ix(db, w2):
    return _mk_item(db, w2, "Foreign Gasket")


@pytest.fixture
def i_off(db, w1):
    return _mk_item(db, w1, "Old Pulley", active=False)


# Raw builders for custom Given setups (bucket/ledger rows that don't match S()'s
# "one opening row" shape, e.g. a bucket whose qty/avg disagrees with its ledger).
def mk_inventory(db, *, workspace_id, factory_id, item_id, inv_type, qty, avg_price,
                  created_by_id, updated_by_id=None, soft_deleted=False,
                  deleted_at=None, deleted_by_id=None):
    row = Inventory(
        workspace_id=workspace_id, factory_id=factory_id, item_id=item_id,
        inventory_type=inv_type, qty=qty, avg_price=avg_price,
        is_deleted=soft_deleted, is_active=not soft_deleted,
        created_by=created_by_id, updated_by=updated_by_id,
        deleted_at=deleted_at, deleted_by=deleted_by_id,
    )
    db.add(row)
    db.flush()
    return row


def mk_inv_ledger(db, *, workspace_id, factory_id, item_id, inv_type, qty_after, avg_after,
                   qty_before=0, avg_before=None, quantity=None, unit_cost=None,
                   performed_by_id, performed_at, transaction_type="opening",
                   source_type="manual", source_id=1, dest_type=None, dest_id=None,
                   src_type=None, src_id=None, row_id=None):
    q = quantity if quantity is not None else (qty_after - qty_before)
    uc = unit_cost if unit_cost is not None else (avg_after if avg_after is not None else Decimal(0))
    row = InventoryLedger(
        id=row_id,
        workspace_id=workspace_id, inventory_type=inv_type, factory_id=factory_id, item_id=item_id,
        transaction_type=transaction_type, quantity=q,
        unit_cost=uc, total_cost=(uc * Decimal(q)).quantize(Decimal("0.01")),
        qty_before=qty_before, qty_after=qty_after,
        avg_price_before=avg_before, avg_price_after=avg_after,
        source_type=source_type, source_id=source_id,
        transfer_destination_type=dest_type, transfer_destination_id=dest_id,
        transfer_source_type=src_type, transfer_source_id=src_id,
        performed_by=performed_by_id, performed_at=performed_at,
    )
    db.add(row)
    db.flush()
    return row


def mk_machine_item(db, *, workspace_id, machine_id, item_id, qty, req_qty=None, defective_qty=None):
    row = MachineItem(workspace_id=workspace_id, machine_id=machine_id, item_id=item_id,
                       qty=qty, req_qty=req_qty, defective_qty=defective_qty)
    db.add(row)
    db.flush()
    return row


def mk_machine_ledger(db, *, workspace_id, machine_id, item_id, qty_after, avg_after,
                       qty_before=0, avg_before=Decimal(0), quantity=None, unit_cost=None,
                       value_before=None, value_after=None,
                       performed_by_id, performed_at, transaction_type="opening",
                       source_type="manual", source_id=1, dest_type=None, dest_id=None,
                       src_type=None, src_id=None, row_id=None):
    q = quantity if quantity is not None else (qty_after - qty_before)
    uc = unit_cost if unit_cost is not None else (avg_after if avg_after is not None else Decimal(0))
    vb = value_before if value_before is not None else (Decimal(qty_before) * (avg_before or Decimal(0)))
    va = value_after if value_after is not None else (Decimal(qty_after) * (avg_after or Decimal(0)))
    row = MachineItemLedger(
        id=row_id,
        workspace_id=workspace_id, machine_id=machine_id, item_id=item_id,
        transaction_type=transaction_type, quantity=q,
        unit_cost=uc, total_cost=(uc * Decimal(q)).quantize(Decimal("0.01")),
        qty_before=qty_before, qty_after=qty_after,
        value_before=vb, value_after=va,
        avg_price_before=avg_before, avg_price_after=avg_after,
        source_type=source_type, source_id=source_id,
        transfer_destination_type=dest_type, transfer_destination_id=dest_id,
        transfer_source_type=src_type, transfer_source_id=src_id,
        performed_by=performed_by_id, performed_at=performed_at,
    )
    db.add(row)
    db.flush()
    return row


# Convention "Tie insertion" (BUG-664 tie cases only): row C's explicit id, read from the
# database just before the insert, so id(B) < id(A) < id(C).
def _next_id_plus(db, table_name, offset=1_000_000):
    seq = db.execute(text("SELECT pg_get_serial_sequence(:t, 'id')"), {"t": table_name}).scalar_one()
    nextval = db.execute(text("SELECT nextval(:seq)"), {"seq": seq}).scalar_one()
    return nextval + offset


# Convention "S(F, I, TYPE, q, p)": a factory stock bucket + matching opening ledger row.
@pytest.fixture
def S(db, u2):
    def _mk(factory, item, inv_type, qty, price, *, workspace_id=None, soft_deleted=False):
        ws_id = workspace_id if workspace_id is not None else factory.workspace_id
        bucket = mk_inventory(
            db, workspace_id=ws_id, factory_id=factory.id, item_id=item.id, inv_type=inv_type,
            qty=qty, avg_price=price, created_by_id=u2.id, updated_by_id=u2.id,
            soft_deleted=soft_deleted, deleted_at=T1 if soft_deleted else None,
            deleted_by_id=u2.id if soft_deleted else None,
        )
        mk_inv_ledger(
            db, workspace_id=ws_id, factory_id=factory.id, item_id=item.id, inv_type=inv_type,
            qty_after=qty, avg_after=price, qty_before=0, avg_before=None,
            unit_cost=(price if price is not None else Decimal(0)),
            performed_by_id=u2.id, performed_at=T0,
        )
        return bucket
    return _mk


# Convention "MS(M, I, q, p)": a machine stock row + matching opening ledger row.
@pytest.fixture
def MS(db, u2):
    def _mk(machine, item, qty, price):
        row = mk_machine_item(db, workspace_id=machine.workspace_id, machine_id=machine.id,
                               item_id=item.id, qty=qty)
        mk_machine_ledger(
            db, workspace_id=machine.workspace_id, machine_id=machine.id, item_id=item.id,
            qty_after=qty, avg_after=price, qty_before=0, avg_before=Decimal(0),
            unit_cost=price, performed_by_id=u2.id, performed_at=T0,
        )
        return row
    return _mk


# Convention "Default call arguments"
def so_kwargs(w1, u1, **overrides):
    d = dict(
        inventory_type=STORAGE, transaction_type="consumption", source_type="work_order",
        source_id=17, notes="WO-17 line 1", workspace_id=w1.id, user_id=u1.id,
        dest_type=None, dest_id=None,
    )
    d.update(overrides)
    return d


def si_kwargs(w1, u1, **overrides):
    d = dict(
        inventory_type=STORAGE, transaction_type="transfer_in", source_type="transfer_order",
        source_id=31, notes="TO-31", workspace_id=w1.id, user_id=u1.id,
        source_loc_type=None, source_loc_id=None,
    )
    d.update(overrides)
    return d


def mo_kwargs(w1, u1, **overrides):
    d = dict(
        transaction_type="consumption", source_type="work_order", source_id=17,
        notes="WO-17 line 1", workspace_id=w1.id, user_id=u1.id,
        dest_type=None, dest_id=None, activity_event_type="consumption", activity_description=None,
    )
    d.update(overrides)
    return d


def mi_kwargs(w1, u1, **overrides):
    d = dict(
        transaction_type="transfer_in", source_type="transfer_order", source_id=31,
        notes="TO-31", workspace_id=w1.id, user_id=u1.id,
        source_loc_type=None, source_loc_id=None, activity_event_type="transfer_in", activity_description=None,
    )
    d.update(overrides)
    return d


def pso_kwargs(w1, u1, **overrides):
    d = dict(
        transaction_type="consumption", source_type="work_order", source_id=17,
        notes="WO-17 line 1", workspace_id=w1.id, user_id=u1.id,
        dest_type=None, dest_id=None, activity_event_type=None, activity_description=None,
    )
    d.update(overrides)
    return d


def psi_kwargs(w1, u1, **overrides):
    d = dict(
        transaction_type="transfer_in", source_type="transfer_order", source_id=31,
        notes="TO-31", workspace_id=w1.id, user_id=u1.id,
        source_loc_type=None, source_loc_id=None, activity_event_type=None, activity_description=None,
    )
    d.update(overrides)
    return d


# Convention "re-read"
def reread_inventory(db, inv_id):
    db.expire_all()
    return db.execute(select(Inventory).where(Inventory.id == inv_id)).scalar_one()


def reread_machine_item(db, mi_id):
    db.expire_all()
    return db.execute(select(MachineItem).where(MachineItem.id == mi_id)).scalar_one()


def inventory_rows(db, workspace_id, factory_id, item_id, inv_type):
    db.expire_all()
    return db.execute(
        select(Inventory).where(
            Inventory.workspace_id == workspace_id, Inventory.factory_id == factory_id,
            Inventory.item_id == item_id, Inventory.inventory_type == inv_type,
        ).order_by(Inventory.id)
    ).scalars().all()


def ledger_rows(db, workspace_id, factory_id, item_id, inv_type):
    db.expire_all()
    return db.execute(
        select(InventoryLedger).where(
            InventoryLedger.workspace_id == workspace_id, InventoryLedger.factory_id == factory_id,
            InventoryLedger.item_id == item_id, InventoryLedger.inventory_type == inv_type,
        ).order_by(InventoryLedger.id)
    ).scalars().all()


def ledger_rows_any_type(db, workspace_id, factory_id, item_id):
    db.expire_all()
    return db.execute(
        select(InventoryLedger).where(
            InventoryLedger.workspace_id == workspace_id, InventoryLedger.factory_id == factory_id,
            InventoryLedger.item_id == item_id,
        ).order_by(InventoryLedger.id)
    ).scalars().all()


def machine_item_rows(db, workspace_id, machine_id, item_id):
    db.expire_all()
    return db.execute(
        select(MachineItem).where(
            MachineItem.workspace_id == workspace_id, MachineItem.machine_id == machine_id,
            MachineItem.item_id == item_id,
        ).order_by(MachineItem.id)
    ).scalars().all()


def machine_ledger_rows(db, workspace_id, machine_id, item_id):
    db.expire_all()
    return db.execute(
        select(MachineItemLedger).where(
            MachineItemLedger.workspace_id == workspace_id, MachineItemLedger.machine_id == machine_id,
            MachineItemLedger.item_id == item_id,
        ).order_by(MachineItemLedger.id)
    ).scalars().all()


def machine_events(db, workspace_id, machine_id):
    db.expire_all()
    return db.execute(
        select(MachineActivityEvent).where(
            MachineActivityEvent.workspace_id == workspace_id, MachineActivityEvent.machine_id == machine_id,
        ).order_by(MachineActivityEvent.id)
    ).scalars().all()


def rows_matching(db, model, **eq):
    """All rows of `model` where ANY given column equals its value (OR) -- for
    'no row with factory_id X or item_id Y anywhere' checks."""
    db.expire_all()
    conds = [getattr(model, k) == v for k, v in eq.items()]
    return db.execute(select(model).where(or_(*conds))).scalars().all()


def assert_no_events(db, *ws):
    """Convention 'No events': zero machine_activity_events rows in the given workspaces."""
    db.expire_all()
    ids = [w.id for w in ws]
    rows = db.execute(
        select(MachineActivityEvent).where(MachineActivityEvent.workspace_id.in_(ids))
    ).scalars().all()
    assert rows == []


def event_metadata(ev):
    return ev.metadata_json


# Convention "SQL capture"
class SqlCapture:
    def __init__(self, engine):
        self.engine = engine
        self.statements = []

    def _on(self, conn, cursor, statement, parameters, context, executemany):
        self.statements.append(statement)

    def __enter__(self):
        event.listen(self.engine, "before_cursor_execute", self._on)
        return self

    def __exit__(self, *exc):
        event.remove(self.engine, "before_cursor_execute", self._on)
        return False

    def locks(self, table):
        return any(
            s.lstrip().upper().startswith("SELECT") and table in s and "FOR UPDATE" in s
            for s in self.statements
        )


# --------------------------------------------------------------------------- #
# item_name
# --------------------------------------------------------------------------- #

def test_invm_in_01__item_of_workspace_returns_name(db, w1, i1):
    """INVM-IN-01 - an item of the workspace returns its stored name.
    Rules: item_name R1."""
    assert item_name(db, i1.id, w1.id) == "Bearing 6204"


def test_invm_in_02__missing_item_returns_fallback(db, w1):
    """INVM-IN-02 - no item with that id returns the Item #<id> fallback, no exception.
    Rules: item_name R2."""
    assert item_name(db, NOID, w1.id) == f"Item #{NOID}"


def test_invm_in_03__foreign_item_returns_fallback(db, w1, ix):
    """INVM-IN-03 - an item of another workspace returns the fallback, not its name.
    Rules: item_name R2."""
    assert item_name(db, ix.id, w1.id) == f"Item #{ix.id}"


def test_invm_in_04__item_found_in_its_own_workspace(db, w2, ix):
    """INVM-IN-04 - looked up in its own workspace, the item name is returned.
    Rules: item_name R1."""
    assert item_name(db, ix.id, w2.id) == "Foreign Gasket"


def test_invm_in_05__inactive_item_still_found(db, w1, i_off):
    """INVM-IN-05 - an inactive item is still found by name (no soft-delete column).
    Rules: item_name R3."""
    assert item_name(db, i_off.id, w1.id) == "Old Pulley"


# --------------------------------------------------------------------------- #
# weighted_avg_price
# --------------------------------------------------------------------------- #

def test_invm_wap_01__even_split_averages():
    """INVM-WAP-01 - equal old/add quantities average their costs.
    Rules: weighted_avg_price R2."""
    result = weighted_avg_price(10, Decimal("5.00"), 10, Decimal("7.00"))
    assert result == Decimal("6.00")
    assert isinstance(result, Decimal)


def test_invm_wap_02__same_cost_stays_same():
    """INVM-WAP-02 - adding at the same unit cost keeps the average unchanged.
    Rules: weighted_avg_price R2."""
    result = weighted_avg_price(1, Decimal("1.00"), 2, Decimal("1.00"))
    assert result == Decimal("1.00")
    assert isinstance(result, Decimal)


def test_invm_wap_03__rounds_to_two_decimals():
    """INVM-WAP-03 - a non-terminating weighted average is rounded to 2 decimals.
    Rules: weighted_avg_price R2."""
    result = weighted_avg_price(2, Decimal("1.00"), 1, Decimal("2.00"))
    assert result == Decimal("1.33")
    assert str(result) == "1.33"
    assert isinstance(result, Decimal)


@pytest.mark.xfail(strict=True, reason=BUG_1040)
def test_invm_wap_04__midpoint_rounds_half_up():
    """INVM-WAP-04 - an exact .025 midpoint rounds half away from zero to .03, not .02.
    Rules: weighted_avg_price R2a [BUG-1040]."""
    result = weighted_avg_price(1, Decimal("0.01"), 1, Decimal("0.04"))
    assert result == Decimal("0.03")
    assert isinstance(result, Decimal)


def test_invm_wap_05__midpoint_never_rounds_down():
    """INVM-WAP-05 - an exact .035 midpoint rounds half away from zero to .04, not .03.
    Rules: weighted_avg_price R2a."""
    result = weighted_avg_price(1, Decimal("0.01"), 1, Decimal("0.06"))
    assert result == Decimal("0.04")
    assert isinstance(result, Decimal)


def test_invm_wap_06__zero_add_qty_keeps_old_avg():
    """INVM-WAP-06 - add_qty == 0 returns the old average unchanged.
    Rules: weighted_avg_price R1."""
    result = weighted_avg_price(10, Decimal("5.00"), 0, Decimal("9.00"))
    assert result == Decimal("5.00")
    assert isinstance(result, Decimal)


def test_invm_wap_07__negative_add_qty_keeps_old_avg():
    """INVM-WAP-07 - a negative add_qty returns the old average unchanged.
    Rules: weighted_avg_price R1."""
    result = weighted_avg_price(10, Decimal("5.00"), -3, Decimal("9.00"))
    assert result == Decimal("5.00")
    assert isinstance(result, Decimal)


def test_invm_wap_08__zero_add_qty_none_avg_returns_zero():
    """INVM-WAP-08 - add_qty == 0 with old_avg None returns Decimal(0), not None.
    Rules: weighted_avg_price R1."""
    result = weighted_avg_price(10, None, 0, Decimal("9.00"))
    assert result == Decimal(0)
    assert isinstance(result, Decimal)


def test_invm_wap_09__zero_add_qty_zero_avg_returns_zero():
    """INVM-WAP-09 - add_qty == 0 with old_avg 0 returns Decimal(0).
    Rules: weighted_avg_price R1."""
    result = weighted_avg_price(10, Decimal("0"), 0, Decimal("9.00"))
    assert result == Decimal(0)
    assert isinstance(result, Decimal)


def test_invm_wap_10__other_side_of_r1_averages():
    """INVM-WAP-10 - add_qty == 1 (other side of R1) still averages per R2.
    Rules: weighted_avg_price R1, R2."""
    result = weighted_avg_price(10, Decimal("5.00"), 1, Decimal("16.00"))
    assert result == Decimal("6.00")
    assert isinstance(result, Decimal)


def test_invm_wap_11__empty_bucket_returns_unit_cost_unrounded():
    """INVM-WAP-11 - an empty bucket (old_qty 0) returns unit_cost as given, unrounded.
    Rules: weighted_avg_price R3."""
    result = weighted_avg_price(0, Decimal("5.00"), 4, Decimal("3.337"))
    assert result == Decimal("3.337")
    assert str(result) == "3.337"
    assert isinstance(result, Decimal)


def test_invm_wap_12__negative_old_qty_returns_unit_cost():
    """INVM-WAP-12 - a negative old_qty returns unit_cost, not a weighted value.
    Rules: weighted_avg_price R3."""
    result = weighted_avg_price(-2, Decimal("5.00"), 3, Decimal("4.00"))
    assert result == Decimal("4.00")
    assert isinstance(result, Decimal)


def test_invm_wap_13__other_side_of_r3_averages():
    """INVM-WAP-13 - old_qty == 1 (other side of R3) still averages per R2.
    Rules: weighted_avg_price R2, R3."""
    result = weighted_avg_price(1, Decimal("5.00"), 1, Decimal("7.00"))
    assert result == Decimal("6.00")
    assert isinstance(result, Decimal)


def test_invm_wap_14__unknown_old_avg_returns_unit_cost():
    """INVM-WAP-14 - old_avg None with old_qty > 0 ignores existing units, returns unit_cost.
    Rules: weighted_avg_price R4."""
    result = weighted_avg_price(5, None, 5, Decimal("2.345"))
    assert result == Decimal("2.345")
    assert str(result) == "2.345"
    assert isinstance(result, Decimal)


def test_invm_wap_15__zero_old_avg_is_known_not_unknown():
    """INVM-WAP-15 - old_avg == Decimal(0) counts as known (R2 applies, not R4).
    Rules: weighted_avg_price R5."""
    result = weighted_avg_price(10, Decimal("0"), 10, Decimal("4.00"))
    assert result == Decimal("2.00")
    assert isinstance(result, Decimal)


# --------------------------------------------------------------------------- #
# inventory_type_for_location
# --------------------------------------------------------------------------- #

def test_invm_itl_01__damaged_maps_to_damaged():
    """INVM-ITL-01 - "damaged" maps to InventoryTypeEnum.DAMAGED.
    Rules: inventory_type_for_location R1."""
    assert inventory_type_for_location("damaged") == InventoryTypeEnum.DAMAGED


def test_invm_itl_02__storage_maps_to_storage():
    """INVM-ITL-02 - "storage" maps to InventoryTypeEnum.STORAGE.
    Rules: inventory_type_for_location R2."""
    assert inventory_type_for_location("storage") == InventoryTypeEnum.STORAGE


def test_invm_itl_03__machine_maps_to_storage():
    """INVM-ITL-03 - "machine" maps to STORAGE (only "damaged" is special).
    Rules: inventory_type_for_location R2."""
    assert inventory_type_for_location("machine") == InventoryTypeEnum.STORAGE


def test_invm_itl_04__case_sensitive_capitalized_damaged_maps_to_storage():
    """INVM-ITL-04 - "Damaged" (capitalized) maps to STORAGE, not DAMAGED (case-sensitive).
    Rules: inventory_type_for_location R2."""
    assert inventory_type_for_location("Damaged") == InventoryTypeEnum.STORAGE


def test_invm_itl_05__empty_string_maps_to_storage():
    """INVM-ITL-05 - an empty string maps to STORAGE.
    Rules: inventory_type_for_location R2."""
    assert inventory_type_for_location("") == InventoryTypeEnum.STORAGE


def test_invm_itl_06__trailing_space_maps_to_storage():
    """INVM-ITL-06 - "damaged " (trailing space) maps to STORAGE, not DAMAGED.
    Rules: inventory_type_for_location R2."""
    assert inventory_type_for_location("damaged ") == InventoryTypeEnum.STORAGE


# --------------------------------------------------------------------------- #
# _storage_out
# --------------------------------------------------------------------------- #

def test_invm_so_01__happy_path_deduct(db, S, w1, u1, u2, f1, i1, m1):
    """INVM-SO-01 - deducting stock updates the bucket and writes a matching ledger row.
    Rules: _storage_out R7, R8, R3."""
    b = S(f1, i1, STORAGE, 10, Decimal("5.00"))
    result = _storage_out(db, factory_id=f1.id, item_id=i1.id, qty=4,
                           **so_kwargs(w1, u1, dest_type="machine", dest_id=m1.id))
    assert result == Decimal("5.00")
    r = reread_inventory(db, b.id)
    assert r.qty == 6
    assert r.avg_price == Decimal("5.00")
    assert r.updated_by == u1.id
    assert r.created_by == u2.id
    assert r.is_deleted is False
    assert len(inventory_rows(db, w1.id, f1.id, i1.id, STORAGE)) == 1
    ledgers = ledger_rows(db, w1.id, f1.id, i1.id, STORAGE)
    assert len(ledgers) == 2
    new = ledgers[-1]
    assert new.workspace_id == w1.id
    assert new.inventory_type == STORAGE
    assert new.factory_id == f1.id
    assert new.item_id == i1.id
    assert new.transaction_type == "consumption"
    assert new.quantity == 4
    assert new.unit_cost == Decimal("5.00")
    assert new.total_cost == Decimal("20.00")
    assert new.qty_before == 10
    assert new.qty_after == 6
    assert new.avg_price_before == Decimal("5.00")
    assert new.avg_price_after == Decimal("5.00")
    assert new.source_type == "work_order"
    assert new.source_id == 17
    assert new.transfer_destination_type == "machine"
    assert new.transfer_destination_id == m1.id
    assert new.transfer_source_type is None
    assert new.transfer_source_id is None
    assert new.notes == "WO-17 line 1"
    assert new.performed_by == u1.id
    assert new.performed_at is not None and new.performed_at > T1
    assert_no_events(db, w1)


def test_invm_so_02__exact_quantity_drains_to_zero(db, S, w1, u1, f1, i1):
    """INVM-SO-02 - deducting the full available quantity drains the bucket to zero.
    Rules: _storage_out R6."""
    S(f1, i1, STORAGE, 5, Decimal("5.00"))
    result = _storage_out(db, factory_id=f1.id, item_id=i1.id, qty=5, **so_kwargs(w1, u1))
    assert result == Decimal("5.00")
    rows = inventory_rows(db, w1.id, f1.id, i1.id, STORAGE)
    assert rows[0].qty == 0
    new = ledger_rows(db, w1.id, f1.id, i1.id, STORAGE)[-1]
    assert new.qty_before == 5
    assert new.qty_after == 0
    assert new.total_cost == Decimal("25.00")


def test_invm_so_03__insufficient_stock_rejected(db, S, w1, u1, u2, f1, i1):
    """INVM-SO-03 - a deduction larger than available stock is rejected and nothing is written.
    Rules: _storage_out R5, R3a; Errors row 3."""
    b = S(f1, i1, STORAGE, 5, Decimal("5.00"))
    with pytest.raises(HTTPException) as exc:
        _storage_out(db, factory_id=f1.id, item_id=i1.id, qty=6, **so_kwargs(w1, u1))
    db.flush()
    assert exc.value.status_code == 400
    assert exc.value.detail == "Insufficient stock (5 available, 6 requested)"
    assert len(ledger_rows(db, w1.id, f1.id, i1.id, STORAGE)) == 1
    r = reread_inventory(db, b.id)
    assert r.qty == 5
    assert r.avg_price == Decimal("5.00")
    assert r.updated_by == u2.id


def test_invm_so_04__sync_from_ledger_before_stock_check(db, w1, u1, u2, f1, i1):
    """INVM-SO-04 - the bucket is synced from its one ledger row before the stock check runs.
    Rules: _storage_out R5, R3a."""
    b = mk_inventory(db, workspace_id=w1.id, factory_id=f1.id, item_id=i1.id, inv_type=STORAGE,
                      qty=10, avg_price=Decimal("5.00"), created_by_id=u2.id, updated_by_id=u2.id)
    mk_inv_ledger(db, workspace_id=w1.id, factory_id=f1.id, item_id=i1.id, inv_type=STORAGE,
                  qty_after=3, avg_after=Decimal("4.00"), performed_by_id=u2.id, performed_at=T0)
    with pytest.raises(HTTPException) as exc:
        _storage_out(db, factory_id=f1.id, item_id=i1.id, qty=5, **so_kwargs(w1, u1))
    db.flush()
    assert exc.value.status_code == 400
    assert exc.value.detail == "Insufficient stock (3 available, 5 requested)"
    assert len(ledger_rows(db, w1.id, f1.id, i1.id, STORAGE)) == 1
    r = reread_inventory(db, b.id)
    assert r.qty == 3
    assert r.avg_price == Decimal("4.00")
    assert r.updated_by == u1.id


def test_invm_so_05__sync_then_deduct_from_synced_value(db, w1, u1, u2, f1, i1):
    """INVM-SO-05 - a successful deduction uses the synced qty/avg, not the stale bucket values.
    Rules: _storage_out R3a, R7, R8."""
    b = mk_inventory(db, workspace_id=w1.id, factory_id=f1.id, item_id=i1.id, inv_type=STORAGE,
                      qty=10, avg_price=Decimal("5.00"), created_by_id=u2.id, updated_by_id=u2.id)
    mk_inv_ledger(db, workspace_id=w1.id, factory_id=f1.id, item_id=i1.id, inv_type=STORAGE,
                  qty_after=8, avg_after=Decimal("6.00"), performed_by_id=u2.id, performed_at=T0)
    result = _storage_out(db, factory_id=f1.id, item_id=i1.id, qty=2, **so_kwargs(w1, u1))
    assert result == Decimal("6.00")
    r = reread_inventory(db, b.id)
    assert r.qty == 6
    assert r.avg_price == Decimal("6.00")
    assert r.updated_by == u1.id
    new = ledger_rows(db, w1.id, f1.id, i1.id, STORAGE)[-1]
    assert new.qty_before == 8
    assert new.qty_after == 6
    assert new.unit_cost == Decimal("6.00")
    assert new.total_cost == Decimal("12.00")
    assert new.avg_price_before == Decimal("6.00")
    assert new.avg_price_after == Decimal("6.00")


def test_invm_so_06__no_ledger_rows_syncs_to_zero(db, w1, u1, u2, f1, i1):
    """INVM-SO-06 - a bucket with no ledger rows syncs to empty before the stock check.
    Rules: _storage_out R3a, R5."""
    b = mk_inventory(db, workspace_id=w1.id, factory_id=f1.id, item_id=i1.id, inv_type=STORAGE,
                      qty=10, avg_price=Decimal("5.00"), created_by_id=u2.id, updated_by_id=u2.id)
    with pytest.raises(HTTPException) as exc:
        _storage_out(db, factory_id=f1.id, item_id=i1.id, qty=1, **so_kwargs(w1, u1))
    db.flush()
    assert exc.value.status_code == 400
    assert exc.value.detail == "Insufficient stock (0 available, 1 requested)"
    assert len(ledger_rows(db, w1.id, f1.id, i1.id, STORAGE)) == 0
    r = reread_inventory(db, b.id)
    assert r.qty == 0
    assert r.avg_price is None
    assert r.updated_by == u1.id


def test_invm_so_07__no_bucket_and_no_ledger_creates_empty_bucket(db, w1, u1, f1, i1):
    """INVM-SO-07 - with no bucket and no ledger rows, an empty bucket is created, then rejected for stock.
    Rules: _storage_out R3, R5."""
    with pytest.raises(HTTPException) as exc:
        _storage_out(db, factory_id=f1.id, item_id=i1.id, qty=1, **so_kwargs(w1, u1))
    db.flush()
    assert exc.value.status_code == 400
    assert exc.value.detail == "Insufficient stock (0 available, 1 requested)"
    assert len(ledger_rows(db, w1.id, f1.id, i1.id, STORAGE)) == 0
    rows = inventory_rows(db, w1.id, f1.id, i1.id, STORAGE)
    assert len(rows) == 1
    assert rows[0].qty == 0
    assert rows[0].avg_price is None
    assert rows[0].created_by == u1.id


def test_invm_so_08__no_bucket_but_ledger_exists_creates_and_syncs(db, w1, u1, f1, i1):
    """INVM-SO-08 - no bucket row but a ledger row exists: a new bucket is created and synced, then deducted.
    Rules: _storage_out R3, R3a, R8."""
    mk_inv_ledger(db, workspace_id=w1.id, factory_id=f1.id, item_id=i1.id, inv_type=STORAGE,
                  qty_after=7, avg_after=Decimal("3.00"), performed_by_id=u1.id, performed_at=T0)
    result = _storage_out(db, factory_id=f1.id, item_id=i1.id, qty=2, **so_kwargs(w1, u1))
    assert result == Decimal("3.00")
    rows = inventory_rows(db, w1.id, f1.id, i1.id, STORAGE)
    assert len(rows) == 1
    assert rows[0].qty == 5
    assert rows[0].avg_price == Decimal("3.00")
    assert rows[0].created_by == u1.id
    assert rows[0].updated_by == u1.id
    assert rows[0].is_deleted is False
    new = ledger_rows(db, w1.id, f1.id, i1.id, STORAGE)[-1]
    assert new.qty_before == 7
    assert new.qty_after == 5


def test_invm_so_09__soft_deleted_bucket_restored(db, S, w1, u1, f1, i1):
    """INVM-SO-09 - a soft-deleted bucket is restored in place and then deducted.
    Rules: _storage_out R3."""
    b = S(f1, i1, STORAGE, 4, Decimal("2.50"), soft_deleted=True)
    result = _storage_out(db, factory_id=f1.id, item_id=i1.id, qty=1, **so_kwargs(w1, u1))
    assert result == Decimal("2.50")
    rows = inventory_rows(db, w1.id, f1.id, i1.id, STORAGE)
    assert len(rows) == 1
    assert rows[0].id == b.id
    assert rows[0].is_deleted is False
    assert rows[0].is_active is True
    assert rows[0].deleted_at is None
    assert rows[0].deleted_by is None
    assert rows[0].qty == 3
    new = ledger_rows(db, w1.id, f1.id, i1.id, STORAGE)[-1]
    assert new.qty_before == 4
    assert new.qty_after == 3


def test_invm_so_10__isolation_other_buckets_and_workspace_untouched(db, S, w1, w2, u1, f1, f1b, i1, i2):
    """INVM-SO-10 - only the exact (workspace, factory, item, type) bucket is affected; others are untouched.
    Rules: _storage_out R3, R3a."""
    damaged = S(f1, i1, DAMAGED, 10, Decimal("5.00"))
    other_factory = S(f1b, i1, STORAGE, 10, Decimal("5.00"))
    other_item = S(f1, i2, STORAGE, 10, Decimal("5.00"))
    other_ws = S(f1, i1, STORAGE, 10, Decimal("5.00"), workspace_id=w2.id)
    with pytest.raises(HTTPException) as exc:
        _storage_out(db, factory_id=f1.id, item_id=i1.id, qty=1, **so_kwargs(w1, u1))
    assert exc.value.status_code == 400
    assert exc.value.detail == "Insufficient stock (0 available, 1 requested)"
    for bucket, ws_id, factory, item, inv_type in [
        (damaged, w1.id, f1, i1, DAMAGED),
        (other_factory, w1.id, f1b, i1, STORAGE),
        (other_item, w1.id, f1, i2, STORAGE),
        (other_ws, w2.id, f1, i1, STORAGE),
    ]:
        r = reread_inventory(db, bucket.id)
        assert r.qty == 10
        assert len(ledger_rows(db, ws_id, factory.id, item.id, inv_type)) == 1


def test_invm_so_11__unknown_factory_404(db, S, w1, u1, f1, i1):
    """INVM-SO-11 - an unknown factory id raises 404 and writes nothing.
    Rules: _storage_out R1; Errors row 1."""
    b = S(f1, i1, STORAGE, 10, Decimal("5.00"))
    with pytest.raises(HTTPException) as exc:
        _storage_out(db, factory_id=NOID, item_id=i1.id, qty=1, **so_kwargs(w1, u1))
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Factory with ID {NOID} not found"
    assert rows_matching(db, Inventory, factory_id=NOID) == []
    assert rows_matching(db, InventoryLedger, factory_id=NOID) == []
    r = reread_inventory(db, b.id)
    assert r.qty == 10
    assert len(ledger_rows(db, w1.id, f1.id, i1.id, STORAGE)) == 1


def test_invm_so_12__foreign_factory_404(db, w1, w2, u1, f2, i1):
    """INVM-SO-12 - a factory of another workspace raises 404 and writes nothing.
    Rules: _storage_out R1; Errors row 1."""
    with pytest.raises(HTTPException) as exc:
        _storage_out(db, factory_id=f2.id, item_id=i1.id, qty=1, **so_kwargs(w1, u1))
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Factory with ID {f2.id} not found"
    assert rows_matching(db, Inventory, factory_id=f2.id) == []
    assert rows_matching(db, InventoryLedger, factory_id=f2.id) == []


@pytest.mark.xfail(strict=True, reason=BUG_662)
def test_invm_so_13__soft_deleted_factory_accepted_today(db, S, w1, u1, f3, i1):
    """INVM-SO-13 - a soft-deleted factory should be treated as not found.
    Rules: _storage_out R2 [BUG-662]; Errors row 1."""
    b = S(f3, i1, STORAGE, 10, Decimal("5.00"))
    with pytest.raises(HTTPException) as exc:
        _storage_out(db, factory_id=f3.id, item_id=i1.id, qty=1, **so_kwargs(w1, u1))
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Factory with ID {f3.id} not found"
    assert reread_inventory(db, b.id).qty == 10
    assert len(ledger_rows(db, w1.id, f3.id, i1.id, STORAGE)) == 1


@pytest.mark.xfail(strict=True, reason=BUG_660)
def test_invm_so_14__bucket_row_should_be_locked(db, engine, S, w1, u1, f1, i1):
    """INVM-SO-14 - the bucket row should be read with SELECT ... FOR UPDATE.
    Rules: _storage_out R4 [BUG-660]."""
    S(f1, i1, STORAGE, 10, Decimal("5.00"))
    with SqlCapture(engine) as cap:
        result = _storage_out(db, factory_id=f1.id, item_id=i1.id, qty=1, **so_kwargs(w1, u1))
    assert result == Decimal("5.00")
    assert cap.locks("inventory")
    rows = inventory_rows(db, w1.id, f1.id, i1.id, STORAGE)
    assert rows[0].qty == 9


@pytest.mark.xfail(strict=True, reason=BUG_666)
def test_invm_so_15__item_check_runs_before_sync(db, w1, u1, u2, f1, ix):
    """INVM-SO-15 - a foreign item should be rejected before the bucket is synced from its ledger.
    Rules: _storage_out R9 [BUG-666]; Errors row 2."""
    b = mk_inventory(db, workspace_id=w1.id, factory_id=f1.id, item_id=ix.id, inv_type=STORAGE,
                      qty=7, avg_price=Decimal("5.00"), created_by_id=u2.id, updated_by_id=u2.id)
    mk_inv_ledger(db, workspace_id=w1.id, factory_id=f1.id, item_id=ix.id, inv_type=STORAGE,
                  qty_after=10, avg_after=Decimal("5.00"), performed_by_id=u2.id, performed_at=T0)
    with pytest.raises(HTTPException) as exc:
        _storage_out(db, factory_id=f1.id, item_id=ix.id, qty=2, **so_kwargs(w1, u1))
    db.flush()
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Item with ID {ix.id} not found"
    r = reread_inventory(db, b.id)
    assert r.qty == 7
    assert r.updated_by == u2.id
    assert len(ledger_rows(db, w1.id, f1.id, ix.id, STORAGE)) == 1


@pytest.mark.xfail(strict=True, reason=BUG_666)
def test_invm_so_16__item_check_before_bucket_create(db, w1, u1, f1):
    """INVM-SO-16 - an unknown item id should be rejected before any bucket row is created.
    Rules: _storage_out R9 [BUG-666]; Errors row 2."""
    with pytest.raises(HTTPException) as exc:
        with db.begin_nested():
            _storage_out(db, factory_id=f1.id, item_id=NOID, qty=1, **so_kwargs(w1, u1))
            db.flush()
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Item with ID {NOID} not found"
    assert rows_matching(db, Inventory, item_id=NOID) == []
    assert rows_matching(db, InventoryLedger, item_id=NOID) == []


def test_invm_so_17__null_avg_price_deducts_at_zero_cost(db, S, w1, u1, f1, i1):
    """INVM-SO-17 - a bucket with no average price deducts at zero unit cost.
    Rules: _storage_out R7, R8."""
    S(f1, i1, STORAGE, 5, None)
    result = _storage_out(db, factory_id=f1.id, item_id=i1.id, qty=2, **so_kwargs(w1, u1))
    assert result == Decimal(0)
    new = ledger_rows(db, w1.id, f1.id, i1.id, STORAGE)[-1]
    assert new.unit_cost == Decimal(0)
    assert new.total_cost == Decimal(0)
    assert new.avg_price_before is None
    assert new.avg_price_after is None
    assert new.qty_after == 3
    rows = inventory_rows(db, w1.id, f1.id, i1.id, STORAGE)
    assert rows[0].qty == 3
    assert rows[0].avg_price is None


@pytest.mark.xfail(strict=True, reason=BUG_664)
def test_invm_so_18__tied_ledger_rows_sync_from_wrong_row(db, w1, u1, u2, f1, i1):
    """INVM-SO-18 - with three tied ledger rows (B, C-explicit-high-id, A), the bucket should
    sync from C (the intended latest), not from B or A.
    Rules: _storage_out R3a [BUG-664]."""
    bucket = mk_inventory(db, workspace_id=w1.id, factory_id=f1.id, item_id=i1.id, inv_type=STORAGE,
                           qty=10, avg_price=Decimal("5.00"), created_by_id=u2.id, updated_by_id=u2.id)
    # Tie insertion convention: row B, then row C (explicit id = nextval + 1_000_000), then row A.
    mk_inv_ledger(db, workspace_id=w1.id, factory_id=f1.id, item_id=i1.id, inv_type=STORAGE,
                  qty_after=12, avg_after=Decimal("4.50"), performed_by_id=u2.id, performed_at=T0)
    c_id = _next_id_plus(db, "inventory_ledger")
    mk_inv_ledger(db, workspace_id=w1.id, factory_id=f1.id, item_id=i1.id, inv_type=STORAGE,
                  qty_after=10, avg_after=Decimal("5.00"), performed_by_id=u2.id, performed_at=T0,
                  row_id=c_id)
    mk_inv_ledger(db, workspace_id=w1.id, factory_id=f1.id, item_id=i1.id, inv_type=STORAGE,
                  qty_after=15, avg_after=Decimal("4.00"), performed_by_id=u2.id, performed_at=T0)
    result = _storage_out(db, factory_id=f1.id, item_id=i1.id, qty=5, **so_kwargs(w1, u1))
    assert result == Decimal("5.00")
    r = reread_inventory(db, bucket.id)
    assert r.qty == 5
    assert r.avg_price == Decimal("5.00")
    new = ledger_rows(db, w1.id, f1.id, i1.id, STORAGE)[-1]
    assert new.qty_before == 10
    assert new.qty_after == 5
    assert new.unit_cost == Decimal("5.00")


def test_invm_so_20__two_postings_no_tie_each_syncs_correctly(db, S, w1, u1, f1, i1):
    """INVM-SO-20 - two stock-outs of 5 in one save (no tie) each sync correctly.
    Rules: _storage_out R3a, R8."""
    S(f1, i1, STORAGE, 20, Decimal("5.00"))
    results = [
        _storage_out(db, factory_id=f1.id, item_id=i1.id, qty=5, **so_kwargs(w1, u1))
        for _ in range(2)
    ]
    assert results == [Decimal("5.00")] * 2
    rows = inventory_rows(db, w1.id, f1.id, i1.id, STORAGE)
    assert rows[0].qty == 10
    ledgers = ledger_rows(db, w1.id, f1.id, i1.id, STORAGE)
    assert len(ledgers) == 3
    new_two = ledgers[1:]
    assert [r.qty_before for r in new_two] == [20, 15]
    assert [r.qty_after for r in new_two] == [15, 10]
    assert new_two[0].performed_at == new_two[1].performed_at
    assert new_two[0].performed_at is not None and new_two[0].performed_at > T1


def test_invm_so_21__inactive_item_accepted(db, S, w1, u1, f1, i_off):
    """INVM-SO-21 - an inactive item is still accepted for a stock-out.
    Rules: _storage_out R9 (inactive item accepted)."""
    S(f1, i_off, STORAGE, 5, Decimal("2.00"))
    result = _storage_out(db, factory_id=f1.id, item_id=i_off.id, qty=2, **so_kwargs(w1, u1))
    assert result == Decimal("2.00")
    rows = inventory_rows(db, w1.id, f1.id, i_off.id, STORAGE)
    assert rows[0].qty == 3
    new = ledger_rows(db, w1.id, f1.id, i_off.id, STORAGE)[-1]
    assert new.item_id == i_off.id
    assert new.qty_before == 5
    assert new.qty_after == 3


def test_invm_so_22__free_string_fields_stored_as_given(db, S, w1, u1, f1, i1, m1):
    """INVM-SO-22 - transaction_type/source_type/dest_type are free 50-char strings stored verbatim.
    Rules: Inputs (free String(50))."""
    S(f1, i1, STORAGE, 10, Decimal("5.00"))
    result = _storage_out(db, factory_id=f1.id, item_id=i1.id, qty=1,
                           **so_kwargs(w1, u1, transaction_type=S50, source_type=S50,
                                       dest_type=S50, dest_id=m1.id))
    assert result == Decimal("5.00")
    new = ledger_rows(db, w1.id, f1.id, i1.id, STORAGE)[-1]
    assert new.transaction_type == S50
    assert new.source_type == S50
    assert new.transfer_destination_type == S50
    rows = inventory_rows(db, w1.id, f1.id, i1.id, STORAGE)
    assert rows[0].qty == 9


def test_invm_so_23__overlong_transaction_type_dataerror(db, S, w1, u1, f1, i1):
    """INVM-SO-23 - an over-long transaction_type raises DataError on flush (pins today's behavior).
    Rules: Inputs (over-long value -> DataError)."""
    b = S(f1, i1, STORAGE, 10, Decimal("5.00"))
    with pytest.raises(DataError):
        with db.begin_nested():
            _storage_out(db, factory_id=f1.id, item_id=i1.id, qty=1,
                         **so_kwargs(w1, u1, transaction_type=S51))
            db.flush()
    ledgers = ledger_rows(db, w1.id, f1.id, i1.id, STORAGE)
    assert len(ledgers) == 1
    assert not any(r.transaction_type == S51 for r in ledgers)
    assert reread_inventory(db, b.id).qty == 10


# --------------------------------------------------------------------------- #
# _storage_in
# --------------------------------------------------------------------------- #

def test_invm_si_01__happy_path_add(db, S, w1, u1, f1, f1b, i1):
    """INVM-SI-01 - adding stock updates the bucket (weighted avg) and writes a matching ledger row.
    Rules: _storage_in R5, R6, R7."""
    b = S(f1, i1, STORAGE, 10, Decimal("5.00"))
    result = _storage_in(db, factory_id=f1.id, item_id=i1.id, qty=10, unit_cost=Decimal("7.00"),
                          **si_kwargs(w1, u1, source_loc_type="factory", source_loc_id=f1b.id))
    assert result is None
    r = reread_inventory(db, b.id)
    assert r.qty == 20
    assert r.avg_price == Decimal("6.00")
    assert r.updated_by == u1.id
    assert len(inventory_rows(db, w1.id, f1.id, i1.id, STORAGE)) == 1
    ledgers = ledger_rows(db, w1.id, f1.id, i1.id, STORAGE)
    assert len(ledgers) == 2
    new = ledgers[-1]
    assert new.workspace_id == w1.id
    assert new.inventory_type == STORAGE
    assert new.factory_id == f1.id
    assert new.item_id == i1.id
    assert new.transaction_type == "transfer_in"
    assert new.quantity == 10
    assert new.unit_cost == Decimal("7.00")
    assert new.total_cost == Decimal("70.00")
    assert new.qty_before == 10
    assert new.qty_after == 20
    assert new.avg_price_before == Decimal("5.00")
    assert new.avg_price_after == Decimal("6.00")
    assert new.source_type == "transfer_order"
    assert new.source_id == 31
    assert new.transfer_source_type == "factory"
    assert new.transfer_source_id == f1b.id
    assert new.transfer_destination_type is None
    assert new.transfer_destination_id is None
    assert new.notes == "TO-31"
    assert new.performed_by == u1.id
    assert new.performed_at is not None and new.performed_at > T1
    assert_no_events(db, w1)


def test_invm_si_02__no_bucket_and_no_ledger_creates_bucket(db, w1, u1, f1, i1):
    """INVM-SI-02 - with no bucket and no ledger rows, a new bucket is created and stocked.
    Rules: _storage_in R3, R5, R6, R7."""
    result = _storage_in(db, factory_id=f1.id, item_id=i1.id, qty=4, unit_cost=Decimal("3.50"),
                          **si_kwargs(w1, u1))
    assert result is None
    rows = inventory_rows(db, w1.id, f1.id, i1.id, STORAGE)
    assert len(rows) == 1
    assert rows[0].qty == 4
    assert rows[0].avg_price == Decimal("3.50")
    assert rows[0].created_by == u1.id
    assert rows[0].updated_by == u1.id
    assert rows[0].is_deleted is False
    ledgers = ledger_rows(db, w1.id, f1.id, i1.id, STORAGE)
    assert len(ledgers) == 1
    new = ledgers[0]
    assert new.qty_before == 0
    assert new.qty_after == 4
    assert new.avg_price_before is None
    assert new.avg_price_after == Decimal("3.50")
    assert new.unit_cost == Decimal("3.50")
    assert new.total_cost == Decimal("14.00")


def test_invm_si_03__soft_deleted_bucket_restored(db, S, w1, u1, f1, i1):
    """INVM-SI-03 - a soft-deleted bucket is restored in place and then stocked.
    Rules: _storage_in R3, R5."""
    b = S(f1, i1, STORAGE, 2, Decimal("1.00"), soft_deleted=True)
    result = _storage_in(db, factory_id=f1.id, item_id=i1.id, qty=1, unit_cost=Decimal("2.00"),
                          **si_kwargs(w1, u1))
    assert result is None
    rows = inventory_rows(db, w1.id, f1.id, i1.id, STORAGE)
    assert len(rows) == 1
    assert rows[0].id == b.id
    assert rows[0].is_deleted is False
    assert rows[0].is_active is True
    assert rows[0].deleted_at is None
    assert rows[0].deleted_by is None
    assert rows[0].qty == 3
    assert rows[0].avg_price == Decimal("1.33")
    new = ledger_rows(db, w1.id, f1.id, i1.id, STORAGE)[-1]
    assert new.avg_price_before == Decimal("1.00")
    assert new.avg_price_after == Decimal("1.33")
    assert new.qty_before == 2
    assert new.qty_after == 3


def test_invm_si_04__sync_empty_qty_unit_cost_wins(db, w1, u1, u2, f1, i1):
    """INVM-SI-04 - a bucket synced to qty 0 adds at the given unit cost (qty 0 side of weighted avg).
    Rules: _storage_in R3 (sync), R5."""
    b = mk_inventory(db, workspace_id=w1.id, factory_id=f1.id, item_id=i1.id, inv_type=STORAGE,
                      qty=10, avg_price=Decimal("5.00"), created_by_id=u2.id, updated_by_id=u2.id)
    mk_inv_ledger(db, workspace_id=w1.id, factory_id=f1.id, item_id=i1.id, inv_type=STORAGE,
                  qty_after=0, avg_after=Decimal("5.00"), performed_by_id=u2.id, performed_at=T0)
    result = _storage_in(db, factory_id=f1.id, item_id=i1.id, qty=2, unit_cost=Decimal("8.00"),
                          **si_kwargs(w1, u1))
    assert result is None
    r = reread_inventory(db, b.id)
    assert r.qty == 2
    assert r.avg_price == Decimal("8.00")
    new = ledger_rows(db, w1.id, f1.id, i1.id, STORAGE)[-1]
    assert new.qty_before == 0
    assert new.qty_after == 2
    assert new.avg_price_before == Decimal("5.00")
    assert new.avg_price_after == Decimal("8.00")


def test_invm_si_05__no_ledger_rows_syncs_to_zero_then_adds(db, w1, u1, u2, f1, i1):
    """INVM-SI-05 - a bucket with no ledger rows syncs to empty before the add.
    Rules: _storage_in R3 (sync), R5."""
    mk_inventory(db, workspace_id=w1.id, factory_id=f1.id, item_id=i1.id, inv_type=STORAGE,
                 qty=6, avg_price=Decimal("3.00"), created_by_id=u2.id, updated_by_id=u2.id)
    result = _storage_in(db, factory_id=f1.id, item_id=i1.id, qty=2, unit_cost=Decimal("4.00"),
                          **si_kwargs(w1, u1))
    assert result is None
    rows = inventory_rows(db, w1.id, f1.id, i1.id, STORAGE)
    assert rows[0].qty == 2
    assert rows[0].avg_price == Decimal("4.00")
    ledgers = ledger_rows(db, w1.id, f1.id, i1.id, STORAGE)
    assert len(ledgers) == 1
    new = ledgers[0]
    assert new.qty_before == 0
    assert new.qty_after == 2
    assert new.avg_price_before is None
    assert new.avg_price_after == Decimal("4.00")


def test_invm_si_06__large_quantity_no_overflow_exception(db, w1, u1, f1, i1):
    """INVM-SI-06 - a very large quantity is accepted without an overflow exception.
    Rules: _storage_in R4."""
    result = _storage_in(db, factory_id=f1.id, item_id=i1.id, qty=100000, unit_cost=Decimal("1.00"),
                          **si_kwargs(w1, u1))
    assert result is None
    rows = inventory_rows(db, w1.id, f1.id, i1.id, STORAGE)
    assert rows[0].qty == 100000
    new = ledger_rows(db, w1.id, f1.id, i1.id, STORAGE)[-1]
    assert new.qty_after == 100000
    assert new.total_cost == Decimal("100000.00")


def test_invm_si_07__negative_unit_cost_accepted(db, w1, u1, f1, i1):
    """INVM-SI-07 - a negative unit cost is accepted and stored as given.
    Rules: _storage_in R5, R6 (Inputs: negative unit_cost accepted)."""
    result = _storage_in(db, factory_id=f1.id, item_id=i1.id, qty=2, unit_cost=Decimal("-1.00"),
                          **si_kwargs(w1, u1))
    assert result is None
    rows = inventory_rows(db, w1.id, f1.id, i1.id, STORAGE)
    assert rows[0].qty == 2
    assert rows[0].avg_price == Decimal("-1.00")
    new = ledger_rows(db, w1.id, f1.id, i1.id, STORAGE)[-1]
    assert new.unit_cost == Decimal("-1.00")
    assert new.total_cost == Decimal("-2.00")


def test_invm_si_08__isolation_other_inventory_type_untouched(db, S, w1, u1, f1, i1):
    """INVM-SI-08 - stocking STORAGE creates a separate bucket from an existing DAMAGED one.
    Rules: _storage_in R3."""
    damaged = S(f1, i1, DAMAGED, 10, Decimal("9.00"))
    result = _storage_in(db, factory_id=f1.id, item_id=i1.id, qty=5, unit_cost=Decimal("1.00"),
                          **si_kwargs(w1, u1))
    assert result is None
    storage_rows = inventory_rows(db, w1.id, f1.id, i1.id, STORAGE)
    assert len(storage_rows) == 1
    assert storage_rows[0].qty == 5
    assert storage_rows[0].avg_price == Decimal("1.00")
    r = reread_inventory(db, damaged.id)
    assert r.qty == 10
    assert r.avg_price == Decimal("9.00")
    assert len(ledger_rows(db, w1.id, f1.id, i1.id, DAMAGED)) == 1


def test_invm_si_09__unknown_factory_404(db, w1, u1, i1):
    """INVM-SI-09 - an unknown factory id raises 404 and writes nothing.
    Rules: _storage_in R1; Errors row 1."""
    with pytest.raises(HTTPException) as exc:
        _storage_in(db, factory_id=NOID, item_id=i1.id, qty=1, unit_cost=Decimal("1.00"),
                    **si_kwargs(w1, u1))
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Factory with ID {NOID} not found"
    assert rows_matching(db, Inventory, factory_id=NOID) == []
    assert rows_matching(db, InventoryLedger, factory_id=NOID) == []


def test_invm_si_10__foreign_factory_404(db, w1, w2, u1, f2, i1):
    """INVM-SI-10 - a factory of another workspace raises 404 and writes nothing.
    Rules: _storage_in R1; Errors row 1."""
    with pytest.raises(HTTPException) as exc:
        _storage_in(db, factory_id=f2.id, item_id=i1.id, qty=1, unit_cost=Decimal("1.00"),
                    **si_kwargs(w1, u1))
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Factory with ID {f2.id} not found"
    assert rows_matching(db, Inventory, factory_id=f2.id) == []
    assert rows_matching(db, InventoryLedger, factory_id=f2.id) == []


@pytest.mark.xfail(strict=True, reason=BUG_662)
def test_invm_si_11__soft_deleted_factory_accepted_today(db, w1, u1, f3, i1):
    """INVM-SI-11 - a soft-deleted factory should be treated as not found.
    Rules: _storage_in R2 [BUG-662]; Errors row 1."""
    with pytest.raises(HTTPException) as exc:
        _storage_in(db, factory_id=f3.id, item_id=i1.id, qty=1, unit_cost=Decimal("1.00"),
                    **si_kwargs(w1, u1))
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Factory with ID {f3.id} not found"
    assert rows_matching(db, Inventory, factory_id=f3.id) == []
    assert rows_matching(db, InventoryLedger, factory_id=f3.id) == []


@pytest.mark.xfail(strict=True, reason=BUG_660)
def test_invm_si_12__bucket_row_should_be_locked(db, engine, S, w1, u1, f1, i1):
    """INVM-SI-12 - the bucket row should be read with SELECT ... FOR UPDATE.
    Rules: _storage_in R3 [BUG-660]."""
    S(f1, i1, STORAGE, 10, Decimal("5.00"))
    with SqlCapture(engine) as cap:
        result = _storage_in(db, factory_id=f1.id, item_id=i1.id, qty=1, unit_cost=Decimal("5.00"),
                              **si_kwargs(w1, u1))
    assert result is None
    assert cap.locks("inventory")
    rows = inventory_rows(db, w1.id, f1.id, i1.id, STORAGE)
    assert rows[0].qty == 11


@pytest.mark.xfail(strict=True, reason=BUG_666)
def test_invm_si_13__item_check_before_bucket_create(db, w1, u1, f1, ix):
    """INVM-SI-13 - a foreign item should be rejected before any bucket row is created.
    Rules: _storage_in R8 [BUG-666]; Errors row 2."""
    with pytest.raises(HTTPException) as exc:
        _storage_in(db, factory_id=f1.id, item_id=ix.id, qty=3, unit_cost=Decimal("2.00"),
                    **si_kwargs(w1, u1))
    db.flush()
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Item with ID {ix.id} not found"
    assert rows_matching(db, Inventory, item_id=ix.id) == []
    assert rows_matching(db, InventoryLedger, item_id=ix.id) == []


@pytest.mark.xfail(strict=True, reason=BUG_666)
def test_invm_si_14__item_check_before_bucket_create_noid(db, w1, u1, f1):
    """INVM-SI-14 - an unknown item id should be rejected before any bucket row is created.
    Rules: _storage_in R8 [BUG-666]; Errors row 2."""
    with pytest.raises(HTTPException) as exc:
        with db.begin_nested():
            _storage_in(db, factory_id=f1.id, item_id=NOID, qty=1, unit_cost=Decimal("1.00"),
                        **si_kwargs(w1, u1))
            db.flush()
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Item with ID {NOID} not found"
    assert rows_matching(db, Inventory, item_id=NOID) == []
    assert rows_matching(db, InventoryLedger, item_id=NOID) == []


@pytest.mark.xfail(strict=True, reason=BUG_664)
def test_invm_si_15__tied_ledger_rows_sync_from_wrong_row(db, w1, u1, u2, f1, i1):
    """INVM-SI-15 - with three tied ledger rows (B, C-explicit-high-id, A), the bucket should
    sync from C (the intended latest), not from B or A.
    Rules: _storage_in R3 (sync) [BUG-664]."""
    bucket = mk_inventory(db, workspace_id=w1.id, factory_id=f1.id, item_id=i1.id, inv_type=STORAGE,
                           qty=10, avg_price=Decimal("5.00"), created_by_id=u2.id, updated_by_id=u2.id)
    # Tie insertion convention: row B, then row C (explicit id = nextval + 1_000_000), then row A.
    mk_inv_ledger(db, workspace_id=w1.id, factory_id=f1.id, item_id=i1.id, inv_type=STORAGE,
                  qty_after=12, avg_after=Decimal("4.50"), performed_by_id=u2.id, performed_at=T0)
    c_id = _next_id_plus(db, "inventory_ledger")
    mk_inv_ledger(db, workspace_id=w1.id, factory_id=f1.id, item_id=i1.id, inv_type=STORAGE,
                  qty_after=10, avg_after=Decimal("5.00"), performed_by_id=u2.id, performed_at=T0,
                  row_id=c_id)
    mk_inv_ledger(db, workspace_id=w1.id, factory_id=f1.id, item_id=i1.id, inv_type=STORAGE,
                  qty_after=15, avg_after=Decimal("4.00"), performed_by_id=u2.id, performed_at=T0)
    result = _storage_in(db, factory_id=f1.id, item_id=i1.id, qty=10, unit_cost=Decimal("7.00"),
                          **si_kwargs(w1, u1))
    assert result is None
    r = reread_inventory(db, bucket.id)
    assert r.qty == 20
    assert r.avg_price == Decimal("6.00")
    new = ledger_rows(db, w1.id, f1.id, i1.id, STORAGE)[-1]
    assert new.qty_before == 10
    assert new.avg_price_before == Decimal("5.00")
    assert new.avg_price_after == Decimal("6.00")


def test_invm_si_16__inactive_item_accepted(db, w1, u1, f1, i_off):
    """INVM-SI-16 - an inactive item is still accepted for a stock-in.
    Rules: _storage_in R8 (inactive item accepted)."""
    result = _storage_in(db, factory_id=f1.id, item_id=i_off.id, qty=3, unit_cost=Decimal("2.00"),
                          **si_kwargs(w1, u1))
    assert result is None
    rows = inventory_rows(db, w1.id, f1.id, i_off.id, STORAGE)
    assert len(rows) == 1
    assert rows[0].qty == 3
    assert rows[0].avg_price == Decimal("2.00")
    assert len(ledger_rows(db, w1.id, f1.id, i_off.id, STORAGE)) == 1


# --------------------------------------------------------------------------- #
# ensure_machine_item
# --------------------------------------------------------------------------- #

def test_invm_emi_01__existing_row_returned(db, w1, m1, i1):
    """INVM-EMI-01 - an existing machine_items row for the key is returned unchanged.
    Rules: ensure_machine_item R1."""
    r = mk_machine_item(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id,
                         qty=7, req_qty=3, defective_qty=1)
    result = ensure_machine_item(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)
    assert result.id == r.id
    row = reread_machine_item(db, r.id)
    assert row.qty == 7
    assert row.req_qty == 3
    assert row.defective_qty == 1
    assert len(machine_item_rows(db, w1.id, m1.id, i1.id)) == 1


def test_invm_emi_02__isolation_other_keys_untouched(db, w1, w2, m1, m1b, i1, i2):
    """INVM-EMI-02 - only the exact (workspace, machine, item) row is returned; others are untouched.
    Rules: ensure_machine_item R1, R2."""
    other_machine = mk_machine_item(db, workspace_id=w1.id, machine_id=m1b.id, item_id=i1.id, qty=5)
    other_item = mk_machine_item(db, workspace_id=w1.id, machine_id=m1.id, item_id=i2.id, qty=5)
    other_ws = mk_machine_item(db, workspace_id=w2.id, machine_id=m1.id, item_id=i1.id, qty=5)
    result = ensure_machine_item(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)
    assert result.id not in {other_machine.id, other_item.id, other_ws.id}
    row = reread_machine_item(db, result.id)
    assert row.workspace_id == w1.id
    assert row.machine_id == m1.id
    assert row.item_id == i1.id
    assert row.qty == 0
    assert reread_machine_item(db, other_machine.id).qty == 5
    assert reread_machine_item(db, other_item.id).qty == 5
    assert reread_machine_item(db, other_ws.id).qty == 5
    assert len(machine_item_rows(db, w1.id, m1.id, i1.id)) == 1


def test_invm_emi_03__no_row_creates_one(db, w1, m1, i1):
    """INVM-EMI-03 - no existing row: a new one is created with qty 0 and flushed.
    Rules: ensure_machine_item R2."""
    result = ensure_machine_item(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)
    assert result.id is not None
    row = reread_machine_item(db, result.id)
    assert row.workspace_id == w1.id
    assert row.machine_id == m1.id
    assert row.item_id == i1.id
    assert row.qty == 0
    assert row.req_qty is None
    assert row.defective_qty is None


def test_invm_emi_04__foreign_machine_accepted(db, w1, w2, m2, i1):
    """INVM-EMI-04 - a machine of another workspace is still accepted (no machine ownership check here).
    Rules: ensure_machine_item R3."""
    result = ensure_machine_item(db, machine_id=m2.id, item_id=i1.id, workspace_id=w1.id)
    row = reread_machine_item(db, result.id)
    assert row.workspace_id == w1.id
    assert row.machine_id == m2.id
    assert row.item_id == i1.id
    assert row.qty == 0


def test_invm_emi_05__unknown_machine_integrity_error(db, w1, i1):
    """INVM-EMI-05 - an unknown machine id raises IntegrityError on the FK.
    Rules: ensure_machine_item R3; Errors."""
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            ensure_machine_item(db, machine_id=NOID, item_id=i1.id, workspace_id=w1.id)
    assert rows_matching(db, MachineItem, machine_id=NOID) == []


def test_invm_emi_06__unknown_item_integrity_error(db, w1, m1):
    """INVM-EMI-06 - an unknown item id raises IntegrityError on the FK.
    Rules: ensure_machine_item R3; Errors."""
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            ensure_machine_item(db, machine_id=m1.id, item_id=NOID, workspace_id=w1.id)
    assert rows_matching(db, MachineItem, item_id=NOID) == []


def test_invm_emi_07__duplicate_rows_first_match_returned(db, w1, m1, i1):
    """INVM-EMI-07 - with two rows for the same key, one of them is returned and neither is changed.
    Rules: ensure_machine_item R4."""
    r_a = mk_machine_item(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id, qty=2)
    r_b = mk_machine_item(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id, qty=3)
    result = ensure_machine_item(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)
    assert result.id in {r_a.id, r_b.id}
    assert len(machine_item_rows(db, w1.id, m1.id, i1.id)) == 2
    assert reread_machine_item(db, r_a.id).qty == 2
    assert reread_machine_item(db, r_b.id).qty == 3


# --------------------------------------------------------------------------- #
# get_machine_unit_cost
# --------------------------------------------------------------------------- #

def test_invm_muc_01__latest_by_time_not_insertion(db, w1, u1, m1, i1):
    """INVM-MUC-01 - the latest entry is picked by performed_at, not by insertion/id order.
    Rules: get_machine_unit_cost R1."""
    mk_machine_ledger(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id,
                       qty_after=10, avg_after=Decimal("12.00"), performed_by_id=u1.id, performed_at=T1)
    mk_machine_ledger(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id,
                       qty_after=5, avg_after=Decimal("9.00"), performed_by_id=u1.id, performed_at=T0)
    result = get_machine_unit_cost(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)
    assert result == Decimal("12.00")
    assert isinstance(result, Decimal)


def test_invm_muc_02__no_ledger_rows_returns_zero(db, w1, m1, i1):
    """INVM-MUC-02 - with no ledger rows, returns Decimal(0), not None.
    Rules: get_machine_unit_cost R2."""
    result = get_machine_unit_cost(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)
    assert result == Decimal(0)
    assert isinstance(result, Decimal)


def test_invm_muc_03__isolation_other_keys_ignored(db, w1, w2, u1, m1, m1b, i1, i2):
    """INVM-MUC-03 - ledger rows for other (workspace, machine, item) keys are not consulted.
    Rules: get_machine_unit_cost R2."""
    mk_machine_ledger(db, workspace_id=w2.id, machine_id=m1.id, item_id=i1.id,
                       qty_after=5, avg_after=Decimal("8.00"), performed_by_id=u1.id, performed_at=T0)
    mk_machine_ledger(db, workspace_id=w1.id, machine_id=m1b.id, item_id=i1.id,
                       qty_after=5, avg_after=Decimal("8.00"), performed_by_id=u1.id, performed_at=T0)
    mk_machine_ledger(db, workspace_id=w1.id, machine_id=m1.id, item_id=i2.id,
                       qty_after=5, avg_after=Decimal("8.00"), performed_by_id=u1.id, performed_at=T0)
    result = get_machine_unit_cost(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)
    assert result == Decimal(0)


def test_invm_muc_04__newest_row_null_avg_not_fallback_to_older(db, w1, u1, m1, i1):
    """INVM-MUC-04 - the newest row has a null avg_price_after: returns 0, the older row is not consulted.
    Rules: get_machine_unit_cost R3."""
    mk_machine_ledger(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id,
                       qty_after=5, avg_after=None, performed_by_id=u1.id, performed_at=T1)
    mk_machine_ledger(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id,
                       qty_after=5, avg_after=Decimal("7.00"), performed_by_id=u1.id, performed_at=T0)
    result = get_machine_unit_cost(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)
    assert result == Decimal(0)


@pytest.mark.xfail(strict=True, reason=BUG_664)
def test_invm_muc_05__tied_rows_picks_wrong_one(db, w1, u1, m1, i1):
    """INVM-MUC-05 - with three tied ledger rows (B, C-explicit-high-id, A), the greatest-id
    (C) row's avg_price_after should be picked, not B's or A's.
    Rules: get_machine_unit_cost R1 [BUG-664]."""
    # Tie insertion convention: row B, then row C (explicit id = nextval + 1_000_000), then row A.
    mk_machine_ledger(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id,
                       qty_after=5, avg_after=Decimal("4.00"), performed_by_id=u1.id, performed_at=T0)
    c_id = _next_id_plus(db, "machine_item_ledger")
    mk_machine_ledger(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id,
                       qty_after=5, avg_after=Decimal("10.00"), performed_by_id=u1.id, performed_at=T0,
                       row_id=c_id)
    mk_machine_ledger(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id,
                       qty_after=5, avg_after=Decimal("3.00"), performed_by_id=u1.id, performed_at=T0)
    result = get_machine_unit_cost(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)
    assert result == Decimal("10.00")


# --------------------------------------------------------------------------- #
# _machine_out
# --------------------------------------------------------------------------- #

def test_invm_mo_01__happy_path_deduct_with_event(db, MS, w1, u1, f1, m1, i1):
    """INVM-MO-01 - deducting machine stock updates the row, writes a ledger row and an activity event.
    Rules: _machine_out R3, R6-R9."""
    mi = MS(m1, i1, 10, Decimal("4.00"))
    result = _machine_out(db, machine_id=m1.id, item_id=i1.id, qty=3,
                           **mo_kwargs(w1, u1, dest_type="factory", dest_id=f1.id))
    assert result == Decimal("4.00")
    row = reread_machine_item(db, mi.id)
    assert row.qty == 7
    assert len(machine_item_rows(db, w1.id, m1.id, i1.id)) == 1
    ledgers = machine_ledger_rows(db, w1.id, m1.id, i1.id)
    assert len(ledgers) == 2
    new = ledgers[-1]
    assert new.workspace_id == w1.id
    assert new.machine_id == m1.id
    assert new.item_id == i1.id
    assert new.transaction_type == "consumption"
    assert new.quantity == 3
    assert new.unit_cost == Decimal("4.00")
    assert new.total_cost == Decimal("12.00")
    assert new.qty_before == 10
    assert new.qty_after == 7
    assert new.value_before == Decimal("40.00")
    assert new.value_after == Decimal("28.00")
    assert new.avg_price_before == Decimal("4.00")
    assert new.avg_price_after == Decimal("4.00")
    assert new.source_type == "work_order"
    assert new.source_id == 17
    assert new.transfer_destination_type == "factory"
    assert new.transfer_destination_id == f1.id
    assert new.transfer_source_type is None
    assert new.transfer_source_id is None
    assert new.order_type is None
    assert new.order_id is None
    assert new.invoice_id is None
    assert new.notes == "WO-17 line 1"
    assert new.performed_by == u1.id
    assert new.performed_at == NOW
    events = machine_events(db, w1.id, m1.id)
    assert len(events) == 1
    ev = events[0]
    assert ev.workspace_id == w1.id
    assert ev.event_type == "consumption"
    assert ev.performed_by == u1.id
    assert ev.created_at == NOW
    assert ev.description == "consumption: 3 units of Bearing 6204"
    assert event_metadata(ev) == {"item_id": i1.id, "item_name": "Bearing 6204", "quantity": 3, "work_order_id": 17}


def test_invm_mo_02__exact_quantity_drains_to_zero(db, MS, w1, u1, m1, i1):
    """INVM-MO-02 - deducting the full available quantity drains the row to zero.
    Rules: _machine_out R6."""
    MS(m1, i1, 5, Decimal("4.00"))
    result = _machine_out(db, machine_id=m1.id, item_id=i1.id, qty=5, **mo_kwargs(w1, u1))
    assert result == Decimal("4.00")
    rows = machine_item_rows(db, w1.id, m1.id, i1.id)
    assert rows[0].qty == 0
    new = machine_ledger_rows(db, w1.id, m1.id, i1.id)[-1]
    assert new.qty_before == 5
    assert new.qty_after == 0
    assert new.value_after == Decimal("0.00")
    assert len(machine_events(db, w1.id, m1.id)) == 1


def test_invm_mo_03__insufficient_stock_rejected(db, MS, w1, u1, m1, i1):
    """INVM-MO-03 - a deduction larger than available stock is rejected and nothing is written.
    Rules: _machine_out R5; Errors row 3."""
    MS(m1, i1, 5, Decimal("4.00"))
    with pytest.raises(HTTPException) as exc:
        _machine_out(db, machine_id=m1.id, item_id=i1.id, qty=6, **mo_kwargs(w1, u1))
    assert exc.value.status_code == 400
    assert exc.value.detail == "Insufficient machine stock (5 available, 6 requested)"
    rows = machine_item_rows(db, w1.id, m1.id, i1.id)
    assert rows[0].qty == 5
    assert len(machine_ledger_rows(db, w1.id, m1.id, i1.id)) == 1
    assert_no_events(db, w1)


def test_invm_mo_04__no_row_and_no_ledger_rejected(db, w1, u1, m1, i1):
    """INVM-MO-04 - no machine_items row and no ledger: rejected for insufficient stock.
    Rules: _machine_out R3, R5."""
    with pytest.raises(HTTPException) as exc:
        _machine_out(db, machine_id=m1.id, item_id=i1.id, qty=1, **mo_kwargs(w1, u1))
    assert exc.value.status_code == 400
    assert exc.value.detail == "Insufficient machine stock (0 available, 1 requested)"
    assert machine_ledger_rows(db, w1.id, m1.id, i1.id) == []
    assert_no_events(db, w1)


def test_invm_mo_05__row_qty_not_synced_from_ledger(db, w1, u1, m1, i1):
    """INVM-MO-05 - the machine row's own qty is used directly; it is not re-synced from the ledger.
    Rules: _machine_out R3."""
    mi = mk_machine_item(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id, qty=10)
    mk_machine_ledger(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id,
                       qty_after=2, avg_after=Decimal("4.00"), performed_by_id=u1.id, performed_at=T0)
    result = _machine_out(db, machine_id=m1.id, item_id=i1.id, qty=5, **mo_kwargs(w1, u1))
    assert result == Decimal("4.00")
    row = reread_machine_item(db, mi.id)
    assert row.qty == 5
    new = machine_ledger_rows(db, w1.id, m1.id, i1.id)[-1]
    assert new.qty_before == 10
    assert new.qty_after == 5


def test_invm_mo_06__no_ledger_zero_cost(db, w1, u1, m1, i1):
    """INVM-MO-06 - a machine row with no ledger rows deducts at zero unit cost.
    Rules: _machine_out R7, R8."""
    mi = mk_machine_item(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id, qty=5)
    result = _machine_out(db, machine_id=m1.id, item_id=i1.id, qty=2, **mo_kwargs(w1, u1))
    assert result == Decimal(0)
    row = reread_machine_item(db, mi.id)
    assert row.qty == 3
    ledgers = machine_ledger_rows(db, w1.id, m1.id, i1.id)
    assert len(ledgers) == 1
    new = ledgers[0]
    assert new.unit_cost == Decimal(0)
    assert new.total_cost == Decimal(0)
    assert new.value_before == Decimal(0)
    assert new.value_after == Decimal(0)
    assert new.avg_price_before == Decimal(0)
    assert new.avg_price_after == Decimal(0)
    assert new.qty_before == 5
    assert new.qty_after == 3


def test_invm_mo_07__custom_activity_description(db, MS, w1, u1, m1, i1):
    """INVM-MO-07 - a given activity_description is used verbatim on the event.
    Rules: _machine_out R9."""
    MS(m1, i1, 10, Decimal("4.00"))
    result = _machine_out(db, machine_id=m1.id, item_id=i1.id, qty=3,
                           **mo_kwargs(w1, u1, activity_description="Loaded for WO-17"))
    assert result == Decimal("4.00")
    events = machine_events(db, w1.id, m1.id)
    assert len(events) == 1
    assert events[0].description == "Loaded for WO-17"


def test_invm_mo_08__empty_activity_description_falls_back(db, MS, w1, u1, m1, i1):
    """INVM-MO-08 - an empty activity_description falls back to the generated description.
    Rules: _machine_out R9."""
    MS(m1, i1, 10, Decimal("4.00"))
    result = _machine_out(db, machine_id=m1.id, item_id=i1.id, qty=3,
                           **mo_kwargs(w1, u1, activity_description=""))
    assert result == Decimal("4.00")
    events = machine_events(db, w1.id, m1.id)
    assert len(events) == 1
    assert events[0].description == "consumption: 3 units of Bearing 6204"


def test_invm_mo_09__transfer_order_source_no_work_order_key(db, MS, w1, u1, m1, i1):
    """INVM-MO-09 - a non-work_order source_type omits work_order_id from the event metadata.
    Rules: _machine_out R9."""
    MS(m1, i1, 10, Decimal("4.00"))
    result = _machine_out(db, machine_id=m1.id, item_id=i1.id, qty=3,
                           **mo_kwargs(w1, u1, source_type="transfer_order", source_id=31))
    assert result == Decimal("4.00")
    events = machine_events(db, w1.id, m1.id)
    assert len(events) == 1
    assert event_metadata(events[0]) == {"item_id": i1.id, "item_name": "Bearing 6204", "quantity": 3}
    new = machine_ledger_rows(db, w1.id, m1.id, i1.id)[-1]
    assert new.source_type == "transfer_order"
    assert new.source_id == 31


def test_invm_mo_10__source_type_case_sensitive(db, MS, w1, u1, m1, i1):
    """INVM-MO-10 - "Work_Order" (capitalized) does not match "work_order"; metadata has no key.
    Rules: _machine_out R9."""
    MS(m1, i1, 10, Decimal("4.00"))
    result = _machine_out(db, machine_id=m1.id, item_id=i1.id, qty=3,
                           **mo_kwargs(w1, u1, source_type="Work_Order", source_id=17))
    assert result == Decimal("4.00")
    events = machine_events(db, w1.id, m1.id)
    assert "work_order_id" not in event_metadata(events[0])


def test_invm_mo_11__unknown_machine_404(db, MS, w1, u1, m1, i1):
    """INVM-MO-11 - an unknown machine id raises 404 and writes nothing.
    Rules: _machine_out R1; Errors row 1."""
    mi = MS(m1, i1, 10, Decimal("4.00"))
    with pytest.raises(HTTPException) as exc:
        _machine_out(db, machine_id=NOID, item_id=i1.id, qty=1, **mo_kwargs(w1, u1))
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Machine with ID {NOID} not found"
    assert rows_matching(db, MachineItem, machine_id=NOID) == []
    assert rows_matching(db, MachineItemLedger, machine_id=NOID) == []
    assert reread_machine_item(db, mi.id).qty == 10
    assert_no_events(db, w1)


def test_invm_mo_12__foreign_machine_404(db, w1, w2, u1, m2, i1):
    """INVM-MO-12 - a machine of another workspace raises 404 and writes nothing.
    Rules: _machine_out R1; Errors row 1."""
    with pytest.raises(HTTPException) as exc:
        _machine_out(db, machine_id=m2.id, item_id=i1.id, qty=1, **mo_kwargs(w1, u1))
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Machine with ID {m2.id} not found"
    assert rows_matching(db, MachineItem, machine_id=m2.id) == []
    assert rows_matching(db, MachineItemLedger, machine_id=m2.id) == []
    assert_no_events(db, w1, w2)


@pytest.mark.xfail(strict=True, reason=BUG_663)
def test_invm_mo_13__soft_deleted_machine_accepted_today(db, MS, w1, u1, m3, i1):
    """INVM-MO-13 - a soft-deleted machine should be treated as not found.
    Rules: _machine_out R2 [BUG-663]; Errors row 1."""
    mi = MS(m3, i1, 10, Decimal("4.00"))
    with pytest.raises(HTTPException) as exc:
        _machine_out(db, machine_id=m3.id, item_id=i1.id, qty=1, **mo_kwargs(w1, u1))
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Machine with ID {m3.id} not found"
    assert reread_machine_item(db, mi.id).qty == 10
    assert len(machine_ledger_rows(db, w1.id, m3.id, i1.id)) == 1
    assert_no_events(db, w1)


@pytest.mark.xfail(strict=True, reason=BUG_661)
def test_invm_mo_14__row_should_be_locked(db, engine, MS, w1, u1, m1, i1):
    """INVM-MO-14 - the machine_items row should be read with SELECT ... FOR UPDATE.
    Rules: _machine_out R4 [BUG-661]."""
    MS(m1, i1, 10, Decimal("4.00"))
    with SqlCapture(engine) as cap:
        result = _machine_out(db, machine_id=m1.id, item_id=i1.id, qty=1, **mo_kwargs(w1, u1))
    assert result == Decimal("4.00")
    assert cap.locks("machine_items")
    rows = machine_item_rows(db, w1.id, m1.id, i1.id)
    assert rows[0].qty == 9


@pytest.mark.xfail(strict=True, reason=BUG_666)
def test_invm_mo_15__foreign_item_accepted_today(db, w1, w2, u1, MS, m1, ix):
    """INVM-MO-15 - a foreign item should be rejected (event today names it "Item #<id>").
    Rules: _machine_out R10 [BUG-666]; Errors row 2."""
    mi = MS(m1, ix, 10, Decimal("4.00"))
    with pytest.raises(HTTPException) as exc:
        _machine_out(db, machine_id=m1.id, item_id=ix.id, qty=2, **mo_kwargs(w1, u1))
    db.flush()
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Item with ID {ix.id} not found"
    assert reread_machine_item(db, mi.id).qty == 10
    assert len(machine_ledger_rows(db, w1.id, m1.id, ix.id)) == 1
    assert_no_events(db, w1, w2)


@pytest.mark.xfail(strict=True, reason=BUG_666)
def test_invm_mo_16__item_check_before_machine_item_create(db, w1, u1, m1):
    """INVM-MO-16 - an unknown item id should be rejected before any machine_items row is created.
    Rules: _machine_out R10 [BUG-666]; Errors row 2."""
    with pytest.raises(HTTPException) as exc:
        with db.begin_nested():
            _machine_out(db, machine_id=m1.id, item_id=NOID, qty=1, **mo_kwargs(w1, u1))
            db.flush()
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Item with ID {NOID} not found"
    assert rows_matching(db, MachineItem, item_id=NOID) == []
    assert rows_matching(db, MachineItemLedger, item_id=NOID) == []
    assert_no_events(db, w1)


def test_invm_mo_17__inactive_item_accepted(db, MS, w1, u1, m1, i_off):
    """INVM-MO-17 - an inactive item is still accepted for a machine stock-out.
    Rules: _machine_out R10 (inactive item accepted), R9."""
    mi = MS(m1, i_off, 5, Decimal("2.00"))
    result = _machine_out(db, machine_id=m1.id, item_id=i_off.id, qty=2, **mo_kwargs(w1, u1))
    assert result == Decimal("2.00")
    row = reread_machine_item(db, mi.id)
    assert row.qty == 3
    new = machine_ledger_rows(db, w1.id, m1.id, i_off.id)[-1]
    assert new.item_id == i_off.id
    events = machine_events(db, w1.id, m1.id)
    assert len(events) == 1
    assert events[0].description == "consumption: 2 units of Old Pulley"
    assert event_metadata(events[0])["item_name"] == "Old Pulley"


def test_invm_mo_18__free_strings_stored_as_given(db, MS, w1, u1, m1, i1):
    """INVM-MO-18 - event_type/transaction_type/source_type are free 50-char strings stored verbatim.
    Rules: _machine_out R9 (free event_type string), R8."""
    mi = MS(m1, i1, 10, Decimal("4.00"))
    result = _machine_out(db, machine_id=m1.id, item_id=i1.id, qty=1,
                           **mo_kwargs(w1, u1, activity_event_type=S50, transaction_type=S50, source_type=S50))
    assert result == Decimal("4.00")
    events = machine_events(db, w1.id, m1.id)
    assert len(events) == 1
    assert events[0].event_type == S50
    new = machine_ledger_rows(db, w1.id, m1.id, i1.id)[-1]
    assert new.transaction_type == S50
    assert new.source_type == S50
    assert reread_machine_item(db, mi.id).qty == 9


def test_invm_mo_19__overlong_event_type_dataerror(db, MS, w1, u1, m1, i1):
    """INVM-MO-19 - an over-long activity_event_type raises DataError on flush (pins today's behavior).
    Rules: _machine_out R9 (over-long event_type -> DataError)."""
    mi = MS(m1, i1, 10, Decimal("4.00"))
    with pytest.raises(DataError):
        with db.begin_nested():
            _machine_out(db, machine_id=m1.id, item_id=i1.id, qty=1,
                         **mo_kwargs(w1, u1, activity_event_type=S51))
            db.flush()
    assert reread_machine_item(db, mi.id).qty == 10
    assert len(machine_ledger_rows(db, w1.id, m1.id, i1.id)) == 1
    assert_no_events(db, w1)


# --------------------------------------------------------------------------- #
# _machine_in
# --------------------------------------------------------------------------- #

def test_invm_mi_01__happy_path_add_with_event(db, MS, w1, u1, f1, m1, i1):
    """INVM-MI-01 - adding machine stock weighted-averages the row and writes a ledger row + event.
    Rules: _machine_in R3-R7."""
    mi = MS(m1, i1, 4, Decimal("10.00"))
    result = _machine_in(db, machine_id=m1.id, item_id=i1.id, qty=4, unit_cost=Decimal("20.00"),
                          **mi_kwargs(w1, u1, source_loc_type="factory", source_loc_id=f1.id))
    assert result is None
    row = reread_machine_item(db, mi.id)
    assert row.qty == 8
    ledgers = machine_ledger_rows(db, w1.id, m1.id, i1.id)
    assert len(ledgers) == 2
    new = ledgers[-1]
    assert new.workspace_id == w1.id
    assert new.machine_id == m1.id
    assert new.item_id == i1.id
    assert new.transaction_type == "transfer_in"
    assert new.quantity == 4
    assert new.unit_cost == Decimal("20.00")
    assert new.total_cost == Decimal("80.00")
    assert new.qty_before == 4
    assert new.qty_after == 8
    assert new.value_before == Decimal("40.00")
    assert new.value_after == Decimal("120.00")
    assert new.avg_price_before == Decimal("10.00")
    assert new.avg_price_after == Decimal("15.00")
    assert new.source_type == "transfer_order"
    assert new.source_id == 31
    assert new.transfer_source_type == "factory"
    assert new.transfer_source_id == f1.id
    assert new.transfer_destination_type is None
    assert new.transfer_destination_id is None
    assert new.order_type is None
    assert new.order_id is None
    assert new.invoice_id is None
    assert new.notes == "TO-31"
    assert new.performed_by == u1.id
    assert new.performed_at == NOW
    events = machine_events(db, w1.id, m1.id)
    assert len(events) == 1
    ev = events[0]
    assert ev.workspace_id == w1.id
    assert ev.event_type == "transfer_in"
    assert ev.performed_by == u1.id
    assert ev.created_at == NOW
    assert ev.description == "transfer_in: 4 units of Bearing 6204"
    assert event_metadata(ev) == {"item_id": i1.id, "item_name": "Bearing 6204", "quantity": 4}


def test_invm_mi_02__zero_qty_row_unit_cost_wins(db, w1, u1, m1, i1):
    """INVM-MI-02 - a machine row at qty 0 adds at the given unit cost (qty 0 side of weighted avg).
    Rules: _machine_in R5."""
    mi = mk_machine_item(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id, qty=0)
    mk_machine_ledger(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id,
                       qty_after=0, avg_after=Decimal("10.00"), performed_by_id=u1.id, performed_at=T0)
    result = _machine_in(db, machine_id=m1.id, item_id=i1.id, qty=2, unit_cost=Decimal("20.00"),
                          **mi_kwargs(w1, u1))
    assert result is None
    row = reread_machine_item(db, mi.id)
    assert row.qty == 2
    new = machine_ledger_rows(db, w1.id, m1.id, i1.id)[-1]
    assert new.avg_price_before == Decimal("10.00")
    assert new.avg_price_after == Decimal("20.00")
    assert new.value_before == Decimal("0.00")
    assert new.value_after == Decimal("40.00")


def test_invm_mi_03__no_row_and_no_ledger_creates_and_stocks(db, w1, u1, m1, i1):
    """INVM-MI-03 - no machine_items row and no ledger: a new row is created and stocked.
    Rules: _machine_in R3, R5."""
    result = _machine_in(db, machine_id=m1.id, item_id=i1.id, qty=3, unit_cost=Decimal("2.50"),
                          **mi_kwargs(w1, u1))
    assert result is None
    rows = machine_item_rows(db, w1.id, m1.id, i1.id)
    assert len(rows) == 1
    assert rows[0].qty == 3
    ledgers = machine_ledger_rows(db, w1.id, m1.id, i1.id)
    assert len(ledgers) == 1
    new = ledgers[0]
    assert new.qty_before == 0
    assert new.qty_after == 3
    assert new.avg_price_before == Decimal(0)
    assert new.avg_price_after == Decimal("2.50")
    assert new.value_before == Decimal("0.00")
    assert new.value_after == Decimal("7.50")
    assert len(machine_events(db, w1.id, m1.id)) == 1


def test_invm_mi_04__no_ledger_rows_weighted_from_zero_cost(db, w1, u1, m1, i1):
    """INVM-MI-04 - a machine row with no ledger rows weighted-averages against a zero cost basis.
    Rules: _machine_in R8."""
    mi = mk_machine_item(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id, qty=5)
    result = _machine_in(db, machine_id=m1.id, item_id=i1.id, qty=5, unit_cost=Decimal("10.00"),
                          **mi_kwargs(w1, u1))
    assert result is None
    row = reread_machine_item(db, mi.id)
    assert row.qty == 10
    new = machine_ledger_rows(db, w1.id, m1.id, i1.id)[-1]
    assert new.avg_price_before == Decimal(0)
    assert new.avg_price_after == Decimal("5.00")
    assert new.value_before == Decimal("0.00")
    assert new.value_after == Decimal("50.00")


def test_invm_mi_05__work_order_source_description_and_metadata(db, MS, w1, u1, m1, i1):
    """INVM-MI-05 - a given activity_description is used verbatim, work_order_id is included.
    Rules: _machine_in R7."""
    MS(m1, i1, 4, Decimal("10.00"))
    result = _machine_in(db, machine_id=m1.id, item_id=i1.id, qty=1, unit_cost=Decimal("10.00"),
                          **mi_kwargs(w1, u1, source_type="work_order", source_id=17,
                                      activity_description="Returned from WO-17"))
    assert result is None
    events = machine_events(db, w1.id, m1.id)
    assert len(events) == 1
    assert events[0].description == "Returned from WO-17"
    assert event_metadata(events[0]) == {
        "item_id": i1.id, "item_name": "Bearing 6204", "quantity": 1, "work_order_id": 17,
    }


def test_invm_mi_06__source_type_case_sensitive_empty_description_falls_back(db, MS, w1, u1, m1, i1):
    """INVM-MI-06 - "Work_Order" (capitalized) omits work_order_id; empty description falls back.
    Rules: _machine_in R7."""
    MS(m1, i1, 4, Decimal("10.00"))
    result = _machine_in(db, machine_id=m1.id, item_id=i1.id, qty=1, unit_cost=Decimal("10.00"),
                          **mi_kwargs(w1, u1, source_type="Work_Order", source_id=17,
                                      activity_description=""))
    assert result is None
    events = machine_events(db, w1.id, m1.id)
    assert len(events) == 1
    assert events[0].description == "transfer_in: 1 units of Bearing 6204"
    assert "work_order_id" not in event_metadata(events[0])


def test_invm_mi_07__negative_qty_before_unit_cost_wins(db, w1, u1, m1, i1):
    """INVM-MI-07 - a negative qty_before (not > 0) adds at the given unit cost.
    Rules: _machine_in R5."""
    mi = mk_machine_item(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id, qty=-2)
    mk_machine_ledger(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id,
                       qty_after=-2, avg_after=Decimal("10.00"), performed_by_id=u1.id, performed_at=T0)
    result = _machine_in(db, machine_id=m1.id, item_id=i1.id, qty=3, unit_cost=Decimal("20.00"),
                          **mi_kwargs(w1, u1))
    assert result is None
    row = reread_machine_item(db, mi.id)
    assert row.qty == 1
    new = machine_ledger_rows(db, w1.id, m1.id, i1.id)[-1]
    assert new.avg_price_after == Decimal("20.00")


def test_invm_mi_08__positive_qty_before_weighted_average(db, w1, u1, m1, i1):
    """INVM-MI-08 - qty_before == 1 (other side of the boundary) still weighted-averages.
    Rules: _machine_in R5."""
    mi = mk_machine_item(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id, qty=1)
    mk_machine_ledger(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id,
                       qty_after=1, avg_after=Decimal("10.00"), performed_by_id=u1.id, performed_at=T0)
    result = _machine_in(db, machine_id=m1.id, item_id=i1.id, qty=1, unit_cost=Decimal("20.00"),
                          **mi_kwargs(w1, u1))
    assert result is None
    row = reread_machine_item(db, mi.id)
    assert row.qty == 2
    new = machine_ledger_rows(db, w1.id, m1.id, i1.id)[-1]
    assert new.avg_price_after == Decimal("15.00")


def test_invm_mi_09__unknown_machine_404(db, w1, u1, i1):
    """INVM-MI-09 - an unknown machine id raises 404 and writes nothing.
    Rules: _machine_in R1; Errors row 1."""
    with pytest.raises(HTTPException) as exc:
        _machine_in(db, machine_id=NOID, item_id=i1.id, qty=1, unit_cost=Decimal("1.00"),
                    **mi_kwargs(w1, u1))
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Machine with ID {NOID} not found"
    assert rows_matching(db, MachineItem, machine_id=NOID) == []
    assert rows_matching(db, MachineItemLedger, machine_id=NOID) == []
    assert_no_events(db, w1)


def test_invm_mi_10__foreign_machine_404(db, w1, w2, u1, m2, i1):
    """INVM-MI-10 - a machine of another workspace raises 404 and writes nothing.
    Rules: _machine_in R1; Errors row 1."""
    with pytest.raises(HTTPException) as exc:
        _machine_in(db, machine_id=m2.id, item_id=i1.id, qty=1, unit_cost=Decimal("1.00"),
                    **mi_kwargs(w1, u1))
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Machine with ID {m2.id} not found"
    assert rows_matching(db, MachineItem, machine_id=m2.id) == []
    assert rows_matching(db, MachineItemLedger, machine_id=m2.id) == []
    assert_no_events(db, w1, w2)


@pytest.mark.xfail(strict=True, reason=BUG_663)
def test_invm_mi_11__soft_deleted_machine_accepted_today(db, w1, u1, m3, i1):
    """INVM-MI-11 - a soft-deleted machine should be treated as not found.
    Rules: _machine_in R2 [BUG-663]; Errors row 1."""
    with pytest.raises(HTTPException) as exc:
        _machine_in(db, machine_id=m3.id, item_id=i1.id, qty=1, unit_cost=Decimal("1.00"),
                    **mi_kwargs(w1, u1))
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Machine with ID {m3.id} not found"
    assert rows_matching(db, MachineItem, machine_id=m3.id) == []
    assert rows_matching(db, MachineItemLedger, machine_id=m3.id) == []
    assert_no_events(db, w1)


@pytest.mark.xfail(strict=True, reason=BUG_661)
def test_invm_mi_12__row_should_be_locked(db, engine, MS, w1, u1, m1, i1):
    """INVM-MI-12 - the machine_items row should be read with SELECT ... FOR UPDATE.
    Rules: _machine_in R3 [BUG-661]."""
    mi = MS(m1, i1, 4, Decimal("10.00"))
    with SqlCapture(engine) as cap:
        result = _machine_in(db, machine_id=m1.id, item_id=i1.id, qty=1, unit_cost=Decimal("10.00"),
                              **mi_kwargs(w1, u1))
    assert result is None
    assert cap.locks("machine_items")
    assert reread_machine_item(db, mi.id).qty == 5


@pytest.mark.xfail(strict=True, reason=BUG_666)
def test_invm_mi_13__item_check_before_machine_item_create(db, w1, w2, u1, m1, ix):
    """INVM-MI-13 - a foreign item should be rejected before any machine_items row is created.
    Rules: _machine_in R9 [BUG-666]; Errors row 2."""
    with pytest.raises(HTTPException) as exc:
        _machine_in(db, machine_id=m1.id, item_id=ix.id, qty=2, unit_cost=Decimal("1.00"),
                    **mi_kwargs(w1, u1))
    db.flush()
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Item with ID {ix.id} not found"
    assert rows_matching(db, MachineItem, item_id=ix.id) == []
    assert rows_matching(db, MachineItemLedger, item_id=ix.id) == []
    assert_no_events(db, w1, w2)


@pytest.mark.xfail(strict=True, reason=BUG_666)
def test_invm_mi_14__item_check_before_machine_item_create_noid(db, w1, u1, m1):
    """INVM-MI-14 - an unknown item id should be rejected before any machine_items row is created.
    Rules: _machine_in R9 [BUG-666]; Errors row 2."""
    with pytest.raises(HTTPException) as exc:
        with db.begin_nested():
            _machine_in(db, machine_id=m1.id, item_id=NOID, qty=1, unit_cost=Decimal("1.00"),
                        **mi_kwargs(w1, u1))
            db.flush()
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Item with ID {NOID} not found"
    assert rows_matching(db, MachineItem, item_id=NOID) == []
    assert rows_matching(db, MachineItemLedger, item_id=NOID) == []
    assert_no_events(db, w1)


def test_invm_mi_15__inactive_item_accepted(db, w1, u1, m1, i_off):
    """INVM-MI-15 - an inactive item is still accepted for a machine stock-in.
    Rules: _machine_in R9 (inactive item accepted), R7."""
    result = _machine_in(db, machine_id=m1.id, item_id=i_off.id, qty=2, unit_cost=Decimal("3.00"),
                          **mi_kwargs(w1, u1))
    assert result is None
    rows = machine_item_rows(db, w1.id, m1.id, i_off.id)
    assert len(rows) == 1
    assert rows[0].qty == 2
    ledgers = machine_ledger_rows(db, w1.id, m1.id, i_off.id)
    assert len(ledgers) == 1
    assert ledgers[0].avg_price_after == Decimal("3.00")
    events = machine_events(db, w1.id, m1.id)
    assert len(events) == 1
    assert events[0].description == "transfer_in: 2 units of Old Pulley"


# --------------------------------------------------------------------------- #
# post_stock_out
# --------------------------------------------------------------------------- #

def test_invm_pso_01__storage_happy_no_event(db, S, w1, u1, f1, i1):
    """INVM-PSO-01 - a storage deduction routes to _storage_out and writes no event.
    Rules: post_stock_out R1, R3 (factory: no event)."""
    S(f1, i1, STORAGE, 10, Decimal("5.00"))
    result = post_stock_out(db, location_type="storage", location_id=f1.id, item_id=i1.id, qty=3,
                             **pso_kwargs(w1, u1, activity_event_type="item_used", activity_description="ignored"))
    assert result == Decimal("5.00")
    rows = inventory_rows(db, w1.id, f1.id, i1.id, STORAGE)
    assert rows[0].qty == 7
    new = ledger_rows(db, w1.id, f1.id, i1.id, STORAGE)[-1]
    assert new.inventory_type == STORAGE
    assert new.quantity == 3
    assert new.transfer_destination_type is None
    assert new.transfer_destination_id is None
    assert_no_events(db, w1)


def test_invm_pso_02__damaged_routes_separately_from_storage(db, S, w1, u1, f1, i1):
    """INVM-PSO-02 - "damaged" deducts the DAMAGED bucket, leaving STORAGE untouched.
    Rules: post_stock_out R2."""
    S(f1, i1, DAMAGED, 6, Decimal("2.00"))
    S(f1, i1, STORAGE, 10, Decimal("5.00"))
    result = post_stock_out(db, location_type="damaged", location_id=f1.id, item_id=i1.id, qty=2,
                             **pso_kwargs(w1, u1))
    assert result == Decimal("2.00")
    damaged_rows = inventory_rows(db, w1.id, f1.id, i1.id, DAMAGED)
    assert damaged_rows[0].qty == 4
    new = ledger_rows(db, w1.id, f1.id, i1.id, DAMAGED)[-1]
    assert new.inventory_type == DAMAGED
    storage_rows = inventory_rows(db, w1.id, f1.id, i1.id, STORAGE)
    assert storage_rows[0].qty == 10
    assert len(ledger_rows(db, w1.id, f1.id, i1.id, STORAGE)) == 1
    assert_no_events(db, w1)


def test_invm_pso_03__damaged_isolated_from_storage_stock(db, S, w1, u1, f1, i1):
    """INVM-PSO-03 - "damaged" with only a STORAGE bucket is rejected; STORAGE is untouched.
    Rules: post_stock_out R2."""
    S(f1, i1, STORAGE, 10, Decimal("5.00"))
    with pytest.raises(HTTPException) as exc:
        post_stock_out(db, location_type="damaged", location_id=f1.id, item_id=i1.id, qty=1,
                        **pso_kwargs(w1, u1))
    assert exc.value.status_code == 400
    assert exc.value.detail == "Insufficient stock (0 available, 1 requested)"
    storage_rows = inventory_rows(db, w1.id, f1.id, i1.id, STORAGE)
    assert storage_rows[0].qty == 10
    assert len(ledger_rows(db, w1.id, f1.id, i1.id, STORAGE)) == 1
    assert ledger_rows(db, w1.id, f1.id, i1.id, DAMAGED) == []


def test_invm_pso_04__storage_isolated_from_damaged_stock(db, S, w1, u1, f1, i1):
    """INVM-PSO-04 - "storage" with only a DAMAGED bucket is rejected; DAMAGED is untouched.
    Rules: post_stock_out R2."""
    S(f1, i1, DAMAGED, 10, Decimal("5.00"))
    with pytest.raises(HTTPException) as exc:
        post_stock_out(db, location_type="storage", location_id=f1.id, item_id=i1.id, qty=1,
                        **pso_kwargs(w1, u1))
    assert exc.value.status_code == 400
    assert exc.value.detail == "Insufficient stock (0 available, 1 requested)"
    damaged_rows = inventory_rows(db, w1.id, f1.id, i1.id, DAMAGED)
    assert damaged_rows[0].qty == 10
    assert len(ledger_rows(db, w1.id, f1.id, i1.id, DAMAGED)) == 1
    assert ledger_rows(db, w1.id, f1.id, i1.id, STORAGE) == []


def test_invm_pso_05__machine_happy_with_custom_event(db, MS, w1, u1, m1, i1):
    """INVM-PSO-05 - "machine" routes to _machine_out and logs the given activity event.
    Rules: post_stock_out R3."""
    MS(m1, i1, 10, Decimal("4.00"))
    result = post_stock_out(db, location_type="machine", location_id=m1.id, item_id=i1.id, qty=2,
                             **pso_kwargs(w1, u1, activity_event_type="item_used",
                                          activity_description="Used on line 2"))
    assert result == Decimal("4.00")
    rows = machine_item_rows(db, w1.id, m1.id, i1.id)
    assert rows[0].qty == 8
    new = machine_ledger_rows(db, w1.id, m1.id, i1.id)[-1]
    assert new.quantity == 2
    events = machine_events(db, w1.id, m1.id)
    assert len(events) == 1
    assert events[0].event_type == "item_used"
    assert events[0].description == "Used on line 2"


def test_invm_pso_06__machine_none_event_type_falls_back_to_transaction_type(db, MS, w1, u1, m1, i1):
    """INVM-PSO-06 - a None activity_event_type falls back to transaction_type on the event.
    Rules: post_stock_out R3."""
    MS(m1, i1, 10, Decimal("4.00"))
    result = post_stock_out(db, location_type="machine", location_id=m1.id, item_id=i1.id, qty=2,
                             **pso_kwargs(w1, u1, activity_event_type=None))
    assert result == Decimal("4.00")
    events = machine_events(db, w1.id, m1.id)
    assert len(events) == 1
    assert events[0].event_type == "consumption"
    assert events[0].description == "consumption: 2 units of Bearing 6204"


def test_invm_pso_07__machine_empty_event_type_falls_back(db, MS, w1, u1, m1, i1):
    """INVM-PSO-07 - an empty-string activity_event_type (falsy) falls back to transaction_type.
    Rules: post_stock_out R3."""
    MS(m1, i1, 10, Decimal("4.00"))
    result = post_stock_out(db, location_type="machine", location_id=m1.id, item_id=i1.id, qty=2,
                             **pso_kwargs(w1, u1, activity_event_type=""))
    assert result == Decimal("4.00")
    events = machine_events(db, w1.id, m1.id)
    assert len(events) == 1
    assert events[0].event_type == "consumption"


def test_invm_pso_08__unsupported_location_type_rejected(db, S, MS, w1, u1, f1, m1, i1):
    """INVM-PSO-08 - an unsupported location_type raises 400 and writes nothing anywhere.
    Rules: post_stock_out R4; Errors row 2."""
    S(f1, i1, STORAGE, 10, Decimal("5.00"))
    MS(m1, i1, 10, Decimal("4.00"))
    with pytest.raises(HTTPException) as exc:
        post_stock_out(db, location_type="project", location_id=f1.id, item_id=i1.id, qty=1,
                        **pso_kwargs(w1, u1))
    assert exc.value.status_code == 400
    assert exc.value.detail == "Unsupported source location type: project"
    assert inventory_rows(db, w1.id, f1.id, i1.id, STORAGE)[0].qty == 10
    assert len(ledger_rows(db, w1.id, f1.id, i1.id, STORAGE)) == 1
    assert machine_item_rows(db, w1.id, m1.id, i1.id)[0].qty == 10
    assert len(machine_ledger_rows(db, w1.id, m1.id, i1.id)) == 1
    assert_no_events(db, w1)


def test_invm_pso_09__location_type_case_sensitive(db, S, w1, u1, f1, i1):
    """INVM-PSO-09 - "Storage" (capitalized) is unsupported; case-sensitive matching.
    Rules: post_stock_out R4; Errors row 2."""
    S(f1, i1, STORAGE, 10, Decimal("5.00"))
    with pytest.raises(HTTPException) as exc:
        post_stock_out(db, location_type="Storage", location_id=f1.id, item_id=i1.id, qty=1,
                        **pso_kwargs(w1, u1))
    assert exc.value.status_code == 400
    assert exc.value.detail == "Unsupported source location type: Storage"
    assert inventory_rows(db, w1.id, f1.id, i1.id, STORAGE)[0].qty == 10
    assert len(ledger_rows(db, w1.id, f1.id, i1.id, STORAGE)) == 1


def test_invm_pso_10__empty_location_type_rejected(db, S, w1, u1, f1, i1):
    """INVM-PSO-10 - an empty location_type is unsupported; detail ends in an empty string.
    Rules: post_stock_out R4; Errors row 2."""
    S(f1, i1, STORAGE, 10, Decimal("5.00"))
    with pytest.raises(HTTPException) as exc:
        post_stock_out(db, location_type="", location_id=f1.id, item_id=i1.id, qty=1,
                        **pso_kwargs(w1, u1))
    assert exc.value.status_code == 400
    assert exc.value.detail == "Unsupported source location type: "
    assert inventory_rows(db, w1.id, f1.id, i1.id, STORAGE)[0].qty == 10
    assert len(ledger_rows(db, w1.id, f1.id, i1.id, STORAGE)) == 1


@pytest.mark.xfail(strict=True, reason=BUG_665)
def test_invm_pso_11__zero_quantity_accepted_today(db, S, w1, u1, f1, i1):
    """INVM-PSO-11 - a zero quantity should be rejected with a 400.
    Rules: post_stock_out R5 [BUG-665]; Errors row 1."""
    S(f1, i1, STORAGE, 10, Decimal("5.00"))
    with pytest.raises(HTTPException) as exc:
        post_stock_out(db, location_type="storage", location_id=f1.id, item_id=i1.id, qty=0,
                        **pso_kwargs(w1, u1))
    assert exc.value.status_code == 400
    assert exc.value.detail == "Quantity must be at least 1, got 0"
    assert inventory_rows(db, w1.id, f1.id, i1.id, STORAGE)[0].qty == 10
    assert len(ledger_rows(db, w1.id, f1.id, i1.id, STORAGE)) == 1


@pytest.mark.xfail(strict=True, reason=BUG_665)
def test_invm_pso_12__negative_quantity_accepted_today(db, S, w1, u1, f1, i1):
    """INVM-PSO-12 - a negative quantity should be rejected with a 400.
    Rules: post_stock_out R5 [BUG-665]; Errors row 1."""
    S(f1, i1, STORAGE, 10, Decimal("5.00"))
    with pytest.raises(HTTPException) as exc:
        post_stock_out(db, location_type="storage", location_id=f1.id, item_id=i1.id, qty=-5,
                        **pso_kwargs(w1, u1))
    assert exc.value.status_code == 400
    assert exc.value.detail == "Quantity must be at least 1, got -5"
    assert inventory_rows(db, w1.id, f1.id, i1.id, STORAGE)[0].qty == 10
    assert len(ledger_rows(db, w1.id, f1.id, i1.id, STORAGE)) == 1


@pytest.mark.xfail(strict=True, reason=BUG_665)
def test_invm_pso_13__machine_zero_quantity_accepted_today(db, MS, w1, u1, m1, i1):
    """INVM-PSO-13 - a zero quantity against a machine should also be rejected with a 400.
    Rules: post_stock_out R5 [BUG-665]; Errors row 1."""
    MS(m1, i1, 10, Decimal("4.00"))
    with pytest.raises(HTTPException) as exc:
        post_stock_out(db, location_type="machine", location_id=m1.id, item_id=i1.id, qty=0,
                        **pso_kwargs(w1, u1))
    assert exc.value.status_code == 400
    assert exc.value.detail == "Quantity must be at least 1, got 0"
    assert machine_item_rows(db, w1.id, m1.id, i1.id)[0].qty == 10
    assert len(machine_ledger_rows(db, w1.id, m1.id, i1.id)) == 1
    assert_no_events(db, w1)


@pytest.mark.xfail(strict=True, reason=BUG_665)
def test_invm_pso_14__quantity_checked_before_location_type(db, w1, u1, f1):
    """INVM-PSO-14 - the quantity check should run before the location_type check.
    Rules: post_stock_out R5 [BUG-665] (checked first)."""
    with pytest.raises(HTTPException) as exc:
        post_stock_out(db, location_type="project", location_id=f1.id, item_id=1, qty=0,
                        **pso_kwargs(w1, u1))
    assert exc.value.status_code == 400
    assert exc.value.detail == "Quantity must be at least 1, got 0"


def test_invm_pso_15__minimum_valid_quantity_accepted(db, S, w1, u1, f1, i1):
    """INVM-PSO-15 - qty == 1 (minimum valid) is accepted and posts normally.
    Rules: post_stock_out R5, R1."""
    S(f1, i1, STORAGE, 10, Decimal("5.00"))
    result = post_stock_out(db, location_type="storage", location_id=f1.id, item_id=i1.id, qty=1,
                             **pso_kwargs(w1, u1))
    assert result == Decimal("5.00")
    assert inventory_rows(db, w1.id, f1.id, i1.id, STORAGE)[0].qty == 9
    assert len(ledger_rows(db, w1.id, f1.id, i1.id, STORAGE)) == 2


def test_invm_pso_16__unknown_factory_404_propagated(db, w1, u1, i1):
    """INVM-PSO-16 - an unknown factory id propagates _storage_out's 404.
    Rules: post_stock_out R1; Errors row 3 (propagated)."""
    with pytest.raises(HTTPException) as exc:
        post_stock_out(db, location_type="storage", location_id=NOID, item_id=i1.id, qty=1,
                        **pso_kwargs(w1, u1))
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Factory with ID {NOID} not found"
    assert rows_matching(db, InventoryLedger, factory_id=NOID) == []


def test_invm_pso_17__unknown_machine_404_propagated(db, w1, u1, i1):
    """INVM-PSO-17 - an unknown machine id propagates _machine_out's 404.
    Rules: post_stock_out R3; Errors row 3 (propagated)."""
    with pytest.raises(HTTPException) as exc:
        post_stock_out(db, location_type="machine", location_id=NOID, item_id=i1.id, qty=1,
                        **pso_kwargs(w1, u1))
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Machine with ID {NOID} not found"
    assert rows_matching(db, MachineItemLedger, machine_id=NOID) == []
    assert_no_events(db, w1)


def test_invm_pso_18__machine_insufficient_stock_propagated(db, MS, w1, u1, m1, i1):
    """INVM-PSO-18 - machine insufficient stock propagates _machine_out's 400.
    Rules: post_stock_out R3; Errors row 3 (propagated)."""
    MS(m1, i1, 1, Decimal("4.00"))
    with pytest.raises(HTTPException) as exc:
        post_stock_out(db, location_type="machine", location_id=m1.id, item_id=i1.id, qty=2,
                        **pso_kwargs(w1, u1))
    assert exc.value.status_code == 400
    assert exc.value.detail == "Insufficient machine stock (1 available, 2 requested)"
    assert machine_item_rows(db, w1.id, m1.id, i1.id)[0].qty == 1
    assert len(machine_ledger_rows(db, w1.id, m1.id, i1.id)) == 1
    assert_no_events(db, w1)


def test_invm_pso_19__storage_location_checked_before_item(db, w1, u1, f1):
    """INVM-PSO-19 - an unknown factory id is rejected before the item would be checked.
    Rules: post_stock_out R6 (location before item)."""
    with pytest.raises(HTTPException) as exc:
        with db.begin_nested():
            post_stock_out(db, location_type="storage", location_id=NOID, item_id=NOID, qty=1,
                            **pso_kwargs(w1, u1))
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Factory with ID {NOID} not found"
    assert rows_matching(db, Inventory, factory_id=NOID) == []
    assert rows_matching(db, Inventory, item_id=NOID) == []
    assert rows_matching(db, InventoryLedger, factory_id=NOID) == []
    assert rows_matching(db, InventoryLedger, item_id=NOID) == []


@pytest.mark.xfail(strict=True, reason=BUG_666)
def test_invm_pso_20__storage_item_should_be_checked_before_stock(db, w1, u1, f1, ix):
    """INVM-PSO-20 - a foreign item should be rejected before the stock-sufficiency check.
    Rules: post_stock_out R6 (item before stock) [BUG-666]."""
    with pytest.raises(HTTPException) as exc:
        post_stock_out(db, location_type="storage", location_id=f1.id, item_id=ix.id, qty=1,
                        **pso_kwargs(w1, u1))
    db.flush()
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Item with ID {ix.id} not found"
    assert rows_matching(db, Inventory, item_id=ix.id) == []
    assert rows_matching(db, InventoryLedger, item_id=ix.id) == []


def test_invm_pso_21__location_type_checked_before_location(db, w1, u1):
    """INVM-PSO-21 - an unsupported location_type is rejected before the (nonexistent) location is looked up.
    Rules: post_stock_out R6 (location_type before location)."""
    with pytest.raises(HTTPException) as exc:
        post_stock_out(db, location_type="project", location_id=NOID, item_id=1, qty=1,
                        **pso_kwargs(w1, u1))
    assert exc.value.status_code == 400
    assert exc.value.detail == "Unsupported source location type: project"
    assert rows_matching(db, InventoryLedger, factory_id=NOID) == []
    assert rows_matching(db, MachineItemLedger, machine_id=NOID) == []
    assert_no_events(db, w1)


def test_invm_pso_22__machine_location_checked_before_item(db, w1, u1):
    """INVM-PSO-22 - an unknown machine id is rejected before the item would be checked.
    Rules: post_stock_out R6 (location before item, machine)."""
    with pytest.raises(HTTPException) as exc:
        with db.begin_nested():
            post_stock_out(db, location_type="machine", location_id=NOID, item_id=NOID, qty=1,
                            **pso_kwargs(w1, u1))
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Machine with ID {NOID} not found"
    assert rows_matching(db, MachineItem, machine_id=NOID) == []
    assert rows_matching(db, MachineItemLedger, machine_id=NOID) == []
    assert_no_events(db, w1)


@pytest.mark.xfail(strict=True, reason=BUG_666)
def test_invm_pso_23__machine_item_should_be_checked_before_stock(db, w1, w2, u1, m1, ix):
    """INVM-PSO-23 - a foreign item should be rejected before the machine stock-sufficiency check.
    Rules: post_stock_out R6 (item before stock, machine) [BUG-666]."""
    with pytest.raises(HTTPException) as exc:
        post_stock_out(db, location_type="machine", location_id=m1.id, item_id=ix.id, qty=1,
                        **pso_kwargs(w1, u1))
    db.flush()
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Item with ID {ix.id} not found"
    assert rows_matching(db, MachineItem, item_id=ix.id) == []
    assert rows_matching(db, MachineItemLedger, item_id=ix.id) == []
    assert_no_events(db, w1, w2)


# --------------------------------------------------------------------------- #
# post_stock_in
# --------------------------------------------------------------------------- #

def test_invm_psi_01__storage_happy_no_event(db, S, w1, u1, f1, i1):
    """INVM-PSI-01 - a storage addition routes to _storage_in and writes no event.
    Rules: post_stock_in R1, R3 (factory: no event)."""
    S(f1, i1, STORAGE, 10, Decimal("5.00"))
    result = post_stock_in(db, location_type="storage", location_id=f1.id, item_id=i1.id, qty=10,
                            unit_cost=Decimal("7.00"),
                            **psi_kwargs(w1, u1, activity_event_type="item_returned",
                                         activity_description="ignored"))
    assert result is None
    rows = inventory_rows(db, w1.id, f1.id, i1.id, STORAGE)
    assert rows[0].qty == 20
    assert rows[0].avg_price == Decimal("6.00")
    new = ledger_rows(db, w1.id, f1.id, i1.id, STORAGE)[-1]
    assert new.inventory_type == STORAGE
    assert new.transfer_source_type is None
    assert new.transfer_source_id is None
    assert_no_events(db, w1)


def test_invm_psi_02__damaged_routes_separately_from_storage(db, S, w1, u1, f1, i1):
    """INVM-PSI-02 - "damaged" stocks the DAMAGED bucket, leaving STORAGE untouched.
    Rules: post_stock_in R2."""
    S(f1, i1, STORAGE, 10, Decimal("5.00"))
    result = post_stock_in(db, location_type="damaged", location_id=f1.id, item_id=i1.id, qty=4,
                            unit_cost=Decimal("3.50"), **psi_kwargs(w1, u1))
    assert result is None
    damaged_rows = inventory_rows(db, w1.id, f1.id, i1.id, DAMAGED)
    assert damaged_rows[0].qty == 4
    assert damaged_rows[0].avg_price == Decimal("3.50")
    new = ledger_rows(db, w1.id, f1.id, i1.id, DAMAGED)[-1]
    assert new.inventory_type == DAMAGED
    storage_rows = inventory_rows(db, w1.id, f1.id, i1.id, STORAGE)
    assert storage_rows[0].qty == 10
    assert storage_rows[0].avg_price == Decimal("5.00")
    assert len(ledger_rows(db, w1.id, f1.id, i1.id, STORAGE)) == 1


def test_invm_psi_03__machine_happy_with_custom_event(db, MS, w1, u1, f1, m1, i1):
    """INVM-PSI-03 - "machine" routes to _machine_in and logs the given activity event.
    Rules: post_stock_in R3."""
    MS(m1, i1, 4, Decimal("10.00"))
    result = post_stock_in(db, location_type="machine", location_id=m1.id, item_id=i1.id, qty=4,
                            unit_cost=Decimal("20.00"),
                            **psi_kwargs(w1, u1, source_loc_type="factory", source_loc_id=f1.id,
                                         activity_event_type="item_returned"))
    assert result is None
    rows = machine_item_rows(db, w1.id, m1.id, i1.id)
    assert rows[0].qty == 8
    new = machine_ledger_rows(db, w1.id, m1.id, i1.id)[-1]
    assert new.avg_price_after == Decimal("15.00")
    assert new.transfer_source_type == "factory"
    assert new.transfer_source_id == f1.id
    events = machine_events(db, w1.id, m1.id)
    assert len(events) == 1
    assert events[0].event_type == "item_returned"
    assert events[0].description == "transfer_in: 4 units of Bearing 6204"


def test_invm_psi_04__machine_none_event_type_falls_back(db, MS, w1, u1, m1, i1):
    """INVM-PSI-04 - a None activity_event_type falls back to transaction_type on the event.
    Rules: post_stock_in R3."""
    MS(m1, i1, 4, Decimal("10.00"))
    result = post_stock_in(db, location_type="machine", location_id=m1.id, item_id=i1.id, qty=1,
                            unit_cost=Decimal("10.00"), **psi_kwargs(w1, u1, activity_event_type=None))
    assert result is None
    events = machine_events(db, w1.id, m1.id)
    assert len(events) == 1
    assert events[0].event_type == "transfer_in"


def test_invm_psi_05__machine_empty_event_type_falls_back(db, MS, w1, u1, m1, i1):
    """INVM-PSI-05 - an empty-string activity_event_type (falsy) falls back to transaction_type.
    Rules: post_stock_in R3."""
    MS(m1, i1, 4, Decimal("10.00"))
    result = post_stock_in(db, location_type="machine", location_id=m1.id, item_id=i1.id, qty=1,
                            unit_cost=Decimal("10.00"), **psi_kwargs(w1, u1, activity_event_type=""))
    assert result is None
    events = machine_events(db, w1.id, m1.id)
    assert len(events) == 1
    assert events[0].event_type == "transfer_in"


def test_invm_psi_06__unsupported_location_type_rejected(db, S, MS, w1, u1, f1, m1, i1):
    """INVM-PSI-06 - an unsupported location_type raises 400 and writes nothing anywhere.
    Rules: post_stock_in R4; Errors row 2."""
    S(f1, i1, STORAGE, 10, Decimal("5.00"))
    MS(m1, i1, 10, Decimal("4.00"))
    with pytest.raises(HTTPException) as exc:
        post_stock_in(db, location_type="project", location_id=f1.id, item_id=i1.id, qty=1,
                       unit_cost=Decimal("1.00"), **psi_kwargs(w1, u1))
    assert exc.value.status_code == 400
    assert exc.value.detail == "Unsupported destination location type: project"
    assert inventory_rows(db, w1.id, f1.id, i1.id, STORAGE)[0].qty == 10
    assert len(ledger_rows(db, w1.id, f1.id, i1.id, STORAGE)) == 1
    assert machine_item_rows(db, w1.id, m1.id, i1.id)[0].qty == 10
    assert len(machine_ledger_rows(db, w1.id, m1.id, i1.id)) == 1
    assert_no_events(db, w1)


def test_invm_psi_07__location_type_case_sensitive(db, S, w1, u1, f1, i1):
    """INVM-PSI-07 - "Damaged" (capitalized) is unsupported; case-sensitive matching.
    Rules: post_stock_in R4; Errors row 2."""
    S(f1, i1, DAMAGED, 10, Decimal("5.00"))
    with pytest.raises(HTTPException) as exc:
        post_stock_in(db, location_type="Damaged", location_id=f1.id, item_id=i1.id, qty=1,
                       unit_cost=Decimal("1.00"), **psi_kwargs(w1, u1))
    assert exc.value.status_code == 400
    assert exc.value.detail == "Unsupported destination location type: Damaged"
    assert inventory_rows(db, w1.id, f1.id, i1.id, DAMAGED)[0].qty == 10
    assert len(ledger_rows(db, w1.id, f1.id, i1.id, DAMAGED)) == 1
    assert ledger_rows(db, w1.id, f1.id, i1.id, STORAGE) == []


def test_invm_psi_08__empty_location_type_rejected(db, w1, u1, f1, i1):
    """INVM-PSI-08 - an empty location_type is unsupported; detail ends in an empty string.
    Rules: post_stock_in R4; Errors row 2."""
    with pytest.raises(HTTPException) as exc:
        post_stock_in(db, location_type="", location_id=f1.id, item_id=i1.id, qty=1,
                       unit_cost=Decimal("1.00"), **psi_kwargs(w1, u1))
    assert exc.value.status_code == 400
    assert exc.value.detail == "Unsupported destination location type: "
    assert ledger_rows_any_type(db, w1.id, f1.id, i1.id) == []


@pytest.mark.xfail(strict=True, reason=BUG_665)
def test_invm_psi_09__zero_quantity_accepted_today(db, S, w1, u1, f1, i1):
    """INVM-PSI-09 - a zero quantity should be rejected with a 400.
    Rules: post_stock_in R5 [BUG-665]; Errors row 1."""
    S(f1, i1, STORAGE, 10, Decimal("5.00"))
    with pytest.raises(HTTPException) as exc:
        post_stock_in(db, location_type="storage", location_id=f1.id, item_id=i1.id, qty=0,
                       unit_cost=Decimal("1.00"), **psi_kwargs(w1, u1))
    assert exc.value.status_code == 400
    assert exc.value.detail == "Quantity must be at least 1, got 0"
    assert inventory_rows(db, w1.id, f1.id, i1.id, STORAGE)[0].qty == 10
    assert len(ledger_rows(db, w1.id, f1.id, i1.id, STORAGE)) == 1


@pytest.mark.xfail(strict=True, reason=BUG_665)
def test_invm_psi_10__negative_quantity_accepted_today(db, S, w1, u1, f1, i1):
    """INVM-PSI-10 - a negative quantity should be rejected with a 400.
    Rules: post_stock_in R5 [BUG-665]; Errors row 1."""
    S(f1, i1, STORAGE, 10, Decimal("5.00"))
    with pytest.raises(HTTPException) as exc:
        post_stock_in(db, location_type="storage", location_id=f1.id, item_id=i1.id, qty=-5,
                       unit_cost=Decimal("1.00"), **psi_kwargs(w1, u1))
    assert exc.value.status_code == 400
    assert exc.value.detail == "Quantity must be at least 1, got -5"
    assert inventory_rows(db, w1.id, f1.id, i1.id, STORAGE)[0].qty == 10
    assert len(ledger_rows(db, w1.id, f1.id, i1.id, STORAGE)) == 1


@pytest.mark.xfail(strict=True, reason=BUG_665)
def test_invm_psi_11__machine_zero_quantity_accepted_today(db, MS, w1, u1, m1, i1):
    """INVM-PSI-11 - a zero quantity against a machine should also be rejected with a 400.
    Rules: post_stock_in R5 [BUG-665]; Errors row 1."""
    MS(m1, i1, 10, Decimal("4.00"))
    with pytest.raises(HTTPException) as exc:
        post_stock_in(db, location_type="machine", location_id=m1.id, item_id=i1.id, qty=0,
                       unit_cost=Decimal("1.00"), **psi_kwargs(w1, u1))
    assert exc.value.status_code == 400
    assert exc.value.detail == "Quantity must be at least 1, got 0"
    assert machine_item_rows(db, w1.id, m1.id, i1.id)[0].qty == 10
    assert len(machine_ledger_rows(db, w1.id, m1.id, i1.id)) == 1
    assert_no_events(db, w1)


@pytest.mark.xfail(strict=True, reason=BUG_665)
def test_invm_psi_12__quantity_checked_before_location_type(db, w1, u1, f1):
    """INVM-PSI-12 - the quantity check should run before the location_type check.
    Rules: post_stock_in R5 [BUG-665] (checked first)."""
    with pytest.raises(HTTPException) as exc:
        post_stock_in(db, location_type="project", location_id=f1.id, item_id=1, qty=0,
                       unit_cost=Decimal("1.00"), **psi_kwargs(w1, u1))
    assert exc.value.status_code == 400
    assert exc.value.detail == "Quantity must be at least 1, got 0"


def test_invm_psi_13__minimum_valid_quantity_accepted(db, S, w1, u1, f1, i1):
    """INVM-PSI-13 - qty == 1 (minimum valid) is accepted and posts normally.
    Rules: post_stock_in R5, R1."""
    S(f1, i1, STORAGE, 10, Decimal("5.00"))
    result = post_stock_in(db, location_type="storage", location_id=f1.id, item_id=i1.id, qty=1,
                            unit_cost=Decimal("5.00"), **psi_kwargs(w1, u1))
    assert result is None
    rows = inventory_rows(db, w1.id, f1.id, i1.id, STORAGE)
    assert rows[0].qty == 11
    assert rows[0].avg_price == Decimal("5.00")
    assert len(ledger_rows(db, w1.id, f1.id, i1.id, STORAGE)) == 2


def test_invm_psi_14__unknown_factory_404_propagated(db, w1, u1, i1):
    """INVM-PSI-14 - an unknown factory id propagates _storage_in's 404.
    Rules: post_stock_in R1; Errors row 3 (propagated)."""
    with pytest.raises(HTTPException) as exc:
        post_stock_in(db, location_type="storage", location_id=NOID, item_id=i1.id, qty=1,
                       unit_cost=Decimal("1.00"), **psi_kwargs(w1, u1))
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Factory with ID {NOID} not found"
    assert rows_matching(db, InventoryLedger, factory_id=NOID) == []


def test_invm_psi_15__unknown_machine_404_propagated(db, w1, u1, i1):
    """INVM-PSI-15 - an unknown machine id propagates _machine_in's 404.
    Rules: post_stock_in R3; Errors row 3 (propagated)."""
    with pytest.raises(HTTPException) as exc:
        post_stock_in(db, location_type="machine", location_id=NOID, item_id=i1.id, qty=1,
                       unit_cost=Decimal("1.00"), **psi_kwargs(w1, u1))
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Machine with ID {NOID} not found"
    assert rows_matching(db, MachineItemLedger, machine_id=NOID) == []
    assert_no_events(db, w1)


def test_invm_psi_16__storage_location_checked_before_item(db, w1, u1, f1):
    """INVM-PSI-16 - an unknown factory id is rejected before the item would be checked.
    Rules: post_stock_in R6 (location before item)."""
    with pytest.raises(HTTPException) as exc:
        with db.begin_nested():
            post_stock_in(db, location_type="storage", location_id=NOID, item_id=NOID, qty=1,
                          unit_cost=Decimal("1.00"), **psi_kwargs(w1, u1))
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Factory with ID {NOID} not found"
    assert rows_matching(db, Inventory, factory_id=NOID) == []
    assert rows_matching(db, Inventory, item_id=NOID) == []
    assert rows_matching(db, InventoryLedger, factory_id=NOID) == []
    assert rows_matching(db, InventoryLedger, item_id=NOID) == []


def test_invm_psi_17__location_type_checked_before_location(db, w1, u1):
    """INVM-PSI-17 - an unsupported location_type is rejected before the (nonexistent) location is looked up.
    Rules: post_stock_in R6 (location_type before location)."""
    with pytest.raises(HTTPException) as exc:
        post_stock_in(db, location_type="project", location_id=NOID, item_id=1, qty=1,
                       unit_cost=Decimal("1.00"), **psi_kwargs(w1, u1))
    assert exc.value.status_code == 400
    assert exc.value.detail == "Unsupported destination location type: project"
    assert rows_matching(db, InventoryLedger, factory_id=NOID) == []
    assert rows_matching(db, MachineItemLedger, machine_id=NOID) == []
    assert_no_events(db, w1)


def test_invm_psi_18__machine_location_checked_before_item(db, w1, u1):
    """INVM-PSI-18 - an unknown machine id is rejected before the item would be checked.
    Rules: post_stock_in R6 (location before item, machine)."""
    with pytest.raises(HTTPException) as exc:
        with db.begin_nested():
            post_stock_in(db, location_type="machine", location_id=NOID, item_id=NOID, qty=1,
                          unit_cost=Decimal("1.00"), **psi_kwargs(w1, u1))
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Machine with ID {NOID} not found"
    assert rows_matching(db, MachineItem, machine_id=NOID) == []
    assert rows_matching(db, MachineItemLedger, machine_id=NOID) == []
    assert_no_events(db, w1)
