"""Unit tests for app/managers/to_inventory.py.

Implements tests/unit/managers/to_inventory.cases.md (revision 3), one test per
case. Real Postgres session (`db` fixture). Externals: none mocked (`utcnow` is
not mocked per Conventions — every seeded ledger row carries an explicit past
`performed_at`). No race simulations.
"""
# ruff: noqa: DTZ001, FURB157, RUF059  (prescribed by the cards: naive datetimes, Decimal("...") literals, setup helpers return every row of a Given)
from datetime import datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import event, func, select

from app.managers.to_inventory import (
    _line_already_posted,
    _post_location_in,
    _post_location_out,
    _quantity_to_int,
    post_transfer_order_inventory,
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
from app.models.status import Status
from app.models.transfer_order import TransferOrder
from app.models.transfer_order_event import TransferOrderEvent
from app.models.transfer_order_item import TransferOrderItem
from app.schemas.transfer_order import (
    TransferOrderCreate,
    TransferOrderItemCreate,
    TransferOrderItemUpdate,
    TransferOrderUpdate,
)
from tests.unit.factories import make_profile, make_workspace

STORAGE = InventoryTypeEnum.STORAGE
DAMAGED = InventoryTypeEnum.DAMAGED

# Convention times
PAST = datetime(2026, 1, 1, 0, 0, 0)       # default performed_at for seeded prior rows
NEWER = datetime(2026, 2, 1, 0, 0, 0)      # a later "latest" row in a bucket
NEWEST = datetime(2026, 3, 1, 0, 0, 0)     # newer rows for *other* buckets (must not matter)
OLDER = datetime(2025, 12, 1, 0, 0, 0)     # older than PAST (used by P-07's pre-existing row)
DELETED_AT = datetime(2026, 1, 15, 0, 0, 0)  # soft-delete timestamp convention

BUG_820 = "BUG-820: no row lock before the availability check"
BUG_822 = "BUG-822: soft-deleted factory/machine accepted as transfer source/destination"
BUG_823 = "BUG-823: location type not validated at entry (accepted at completion only)"
BUG_824 = "BUG-824: quantity not validated at entry (accepted at completion only)"
BUG_826 = "BUG-826: insufficient-stock error does not name the line/item"
BUG_1040 = "BUG-1040: money rounded half to even in Python, half away from zero in the database"


# --------------------------------------------------------------------------- #
# Conventions -> fixtures / helpers
# --------------------------------------------------------------------------- #

# Convention "W1, W2 = two workspaces"
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db):
    return make_workspace(db)


# Convention "U1 = a profile in W1; U2 = a profile in W2"
@pytest.fixture
def u1(db):
    return make_profile(db)


@pytest.fixture
def u2(db):
    return make_profile(db)


def mk_status(db, ws, name="Open"):
    row = Status(workspace_id=ws.id, name=name, comment="")
    db.add(row)
    db.flush()
    return row


# Convention "ST = a statuses row usable as a transfer order's current_status_id"
@pytest.fixture
def st(db, w1):
    return mk_status(db, w1)


def mk_item(db, ws, name, unit="pcs"):
    row = Item(workspace_id=ws.id, name=name, name_normalized=name.lower(), unit=unit)
    db.add(row)
    db.flush()
    return row


# Convention "I1 = item 'Bearing 6204' in W1. I2 = item 'Grease EP2' in W1.
# IX = item 'Cable' in W2."
@pytest.fixture
def i1(db, w1):
    return mk_item(db, w1, "Bearing 6204")


@pytest.fixture
def i2(db, w1):
    return mk_item(db, w1, "Grease EP2")


@pytest.fixture
def ix(db, w2):
    return mk_item(db, w2, "Cable")


def mk_factory(db, ws, name, *, deleted=False, deleted_by=None):
    row = Factory(
        workspace_id=ws.id,
        name=name,
        abbreviation=name[:3].upper(),
        is_deleted=deleted,
        is_active=not deleted,
        deleted_at=DELETED_AT if deleted else None,
        deleted_by=(deleted_by.id if deleted and deleted_by else None),
    )
    db.add(row)
    db.flush()
    return row


# Convention "F1, F2 = active factories in W1. FX = factory in W2. FD = factory
# in W1 with is_deleted = True."
@pytest.fixture
def f1(db, w1):
    return mk_factory(db, w1, "Factory One")


@pytest.fixture
def f2(db, w1):
    return mk_factory(db, w1, "Factory Two")


@pytest.fixture
def fx(db, w2):
    return mk_factory(db, w2, "Factory X")


@pytest.fixture
def fd(db, w1, u1):
    return mk_factory(db, w1, "Factory Deleted", deleted=True, deleted_by=u1)


def mk_machine(db, ws, factory, name, *, deleted=False, deleted_by=None):
    row = Machine(
        workspace_id=ws.id,
        name=name,
        factory_id=factory.id,
        is_deleted=deleted,
        is_active=not deleted,
        deleted_at=DELETED_AT if deleted else None,
        deleted_by=(deleted_by.id if deleted and deleted_by else None),
    )
    db.add(row)
    db.flush()
    return row


# Convention "M1, M2 = active machines in W1. MX = machine in W2. MD = machine
# in W1 with is_deleted = True."
@pytest.fixture
def m1(db, w1, f1):
    return mk_machine(db, w1, f1, "Machine One")


@pytest.fixture
def m2(db, w1, f1):
    return mk_machine(db, w1, f1, "Machine Two")


@pytest.fixture
def mx(db, w2, fx):
    return mk_machine(db, w2, fx, "Machine X")


@pytest.fixture
def md(db, w1, f1, u1):
    return mk_machine(db, w1, f1, "Machine Deleted", deleted=True, deleted_by=u1)


def mk_order(db, ws, status, user, *, source_type, source_id, dest_type, dest_id,
             transfer_number="TR-2026-004"):
    row = TransferOrder(
        workspace_id=ws.id,
        transfer_number=transfer_number,
        source_location_type=source_type,
        source_location_id=source_id,
        destination_location_type=dest_type,
        destination_location_id=dest_id,
        current_status_id=status.id,
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def mk_line(db, to, item, quantity, line_number):
    row = TransferOrderItem(
        workspace_id=to.workspace_id,
        transfer_order_id=to.id,
        line_number=line_number,
        item_id=item.id,
        quantity=Decimal(str(quantity)),
    )
    db.add(row)
    db.flush()
    return row


# Convention "TO = transfer order in W1 ... L = a line of TO with line_number =
# 2, item I1, quantity 3.00 ... Setup must make TO.id != L.id, e.g. by flushing
# a throw-away extra line first." Used by the _post_location_out/_in cases,
# where to.source/destination_location_type/id are not read by the function
# under test (only to.transfer_number, line.id, line.line_number), so they are
# given harmless placeholder values here.
def mk_to_line(db, w1, status, user, item, *, quantity="3.00", line_number=2):
    to = mk_order(
        db, w1, status, user,
        source_type="storage", source_id=1, dest_type="machine", dest_id=1,
    )
    mk_line(db, to, item, "1.00", 1)  # throw-away: ensures TO.id != L.id
    line = mk_line(db, to, item, quantity, line_number)
    return to, line


def seed_ledger(db, ws, factory, item, inv_type, user, *, qty_after, avg_price_after,
                performed_at=PAST, source_id=900001):
    unit_cost = avg_price_after if avg_price_after is not None else Decimal(0)
    row = InventoryLedger(
        workspace_id=ws.id,
        inventory_type=inv_type,
        factory_id=factory.id,
        item_id=item.id,
        transaction_type="purchase_receive",
        quantity=qty_after,
        unit_cost=avg_price_after,
        total_cost=(unit_cost * Decimal(qty_after)).quantize(Decimal("0.01")),
        qty_before=0,
        qty_after=qty_after,
        avg_price_before=None,
        avg_price_after=avg_price_after,
        source_type="purchase_order",
        source_id=source_id,
        performed_by=user.id,
        performed_at=performed_at,
    )
    db.add(row)
    db.flush()
    return row


def seed_inventory_row(db, ws, factory, item, inv_type, user, *, qty, avg_price, deleted=False):
    row = Inventory(
        workspace_id=ws.id,
        item_id=item.id,
        inventory_type=inv_type,
        factory_id=factory.id,
        qty=qty,
        avg_price=avg_price,
        created_by=user.id,
        is_deleted=deleted,
        is_active=not deleted,
        deleted_at=DELETED_AT if deleted else None,
        deleted_by=(user.id if deleted else None),
    )
    db.add(row)
    db.flush()
    return row


# Convention "Seeding factory stock: F/TYPE/I = q @ p"
def seed_stock(db, ws, factory, item, inv_type, user, *, qty, avg_price,
               performed_at=PAST, ledger_only=False):
    seed_ledger(db, ws, factory, item, inv_type, user, qty_after=qty,
                avg_price_after=avg_price, performed_at=performed_at)
    if not ledger_only:
        seed_inventory_row(db, ws, factory, item, inv_type, user, qty=qty, avg_price=avg_price)


def seed_machine_stock(db, ws, machine, item, *, qty):
    row = MachineItem(workspace_id=ws.id, machine_id=machine.id, item_id=item.id, qty=qty)
    db.add(row)
    db.flush()
    return row


# Convention "M/I mavg p @ t"
def seed_machine_ledger(db, ws, machine, item, user, *, qty_after, avg_price_after,
                        performed_at, source_id=900002):
    unit_cost = avg_price_after if avg_price_after is not None else Decimal(0)
    row = MachineItemLedger(
        workspace_id=ws.id,
        machine_id=machine.id,
        item_id=item.id,
        transaction_type="purchase_order",
        quantity=qty_after,
        unit_cost=unit_cost,
        total_cost=(unit_cost * Decimal(qty_after)).quantize(Decimal("0.01")),
        qty_before=0,
        qty_after=qty_after,
        value_before=Decimal(0),
        value_after=Decimal(qty_after) * unit_cost,
        avg_price_before=None,
        avg_price_after=avg_price_after,
        source_type="purchase_order",
        source_id=source_id,
        performed_by=user.id,
        performed_at=performed_at,
    )
    db.add(row)
    db.flush()
    return row


def get_bucket(db, ws, factory, item, inv_type):
    db.expire_all()
    return db.execute(
        select(Inventory).where(
            Inventory.workspace_id == ws.id,
            Inventory.factory_id == factory.id,
            Inventory.item_id == item.id,
            Inventory.inventory_type == inv_type,
        )
    ).scalars().first()


def get_machine_item(db, ws, machine, item):
    db.expire_all()
    return db.execute(
        select(MachineItem).where(
            MachineItem.workspace_id == ws.id,
            MachineItem.machine_id == machine.id,
            MachineItem.item_id == item.id,
        )
    ).scalars().first()


# Used where the case says "exactly one" row -- machine_items has no unique
# constraint on (workspace, machine, item), so .first() alone would not catch
# a duplicate row being created.
def get_machine_items_all(db, ws, machine, item):
    db.expire_all()
    return db.execute(
        select(MachineItem).where(
            MachineItem.workspace_id == ws.id,
            MachineItem.machine_id == machine.id,
            MachineItem.item_id == item.id,
        ).order_by(MachineItem.id)
    ).scalars().all()


# Convention "'New row for L': the row with source_type = 'transfer_order' and
# source_id = L.id."
def last_inv_ledger_for_line(db, line):
    db.expire_all()
    return db.execute(
        select(InventoryLedger).where(
            InventoryLedger.source_type == "transfer_order",
            InventoryLedger.source_id == line.id,
        ).order_by(InventoryLedger.id)
    ).scalars().all()


def last_machine_ledger_for_line(db, line):
    db.expire_all()
    return db.execute(
        select(MachineItemLedger).where(
            MachineItemLedger.source_type == "transfer_order",
            MachineItemLedger.source_id == line.id,
        ).order_by(MachineItemLedger.id)
    ).scalars().all()


def events_for_machine(db, machine, event_type=None):
    db.expire_all()
    q = select(MachineActivityEvent).where(MachineActivityEvent.machine_id == machine.id)
    if event_type:
        q = q.where(MachineActivityEvent.event_type == event_type)
    return db.execute(q.order_by(MachineActivityEvent.id)).scalars().all()


def to_event_count(db, to):
    db.expire_all()
    return db.scalar(
        select(func.count()).select_from(TransferOrderEvent)
        .where(TransferOrderEvent.transfer_order_id == to.id)
    )


# Convention "'Nothing written' (NW)": snapshot before/after, all workspaces.
def nw_snapshot(db):
    db.expire_all()
    counts = (
        db.scalar(select(func.count()).select_from(InventoryLedger)),
        db.scalar(select(func.count()).select_from(MachineItemLedger)),
        db.scalar(select(func.count()).select_from(MachineActivityEvent)),
    )
    inv_rows = db.execute(
        select(Inventory.id, Inventory.qty, Inventory.avg_price, Inventory.is_deleted,
               Inventory.is_active).order_by(Inventory.id)
    ).all()
    mi_rows = db.execute(
        select(MachineItem.id, MachineItem.qty).order_by(MachineItem.id)
    ).all()
    return counts, [tuple(r) for r in inv_rows], [tuple(r) for r in mi_rows]


def assert_nw(before, after):
    assert after == before


def assert_fields(row, **expected):
    for k, v in expected.items():
        actual = getattr(row, k)
        assert actual == v, f"{k}: expected {v!r}, got {actual!r}"


# Convention "Default call args"
def call_out(db, w1, u1, to, line, *, location_type, location_id, qty, item_id,
             dest_type="machine", dest_id=None):
    return _post_location_out(
        db,
        location_type=location_type,
        location_id=location_id,
        item_id=item_id,
        qty=qty,
        line=line,
        to=to,
        workspace_id=w1.id,
        user_id=u1.id,
        dest_type=dest_type,
        dest_id=dest_id,
    )


def call_in(db, w1, u1, to, line, *, location_type, location_id, qty, unit_cost, item_id,
            source_type="machine", source_id=None):
    return _post_location_in(
        db,
        location_type=location_type,
        location_id=location_id,
        item_id=item_id,
        qty=qty,
        unit_cost=unit_cost,
        line=line,
        to=to,
        workspace_id=w1.id,
        user_id=u1.id,
        source_type=source_type,
        source_id=source_id,
    )


# Convention "SQL capture": a before_cursor_execute listener recording every
# statement executed during the action only.
class SQLCapture:
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


def assert_lock_before_insert(statements, lock_table, insert_table):
    def is_insert(s):
        s = s.strip().lower()
        return s.startswith("insert into") and insert_table in s

    def is_lock(s):
        s = s.lower()
        return f"from {lock_table}" in s and "for update" in s

    insert_idx = next((i for i, s in enumerate(statements) if is_insert(s)), None)
    assert insert_idx is not None, f"no INSERT into {insert_table} captured"
    lock_idx = next((i for i, s in enumerate(statements[:insert_idx]) if is_lock(s)), None)
    assert lock_idx is not None, f"no captured SELECT on {lock_table} contains FOR UPDATE"


# =========================================================================== #
# _quantity_to_int
# =========================================================================== #

def test_toi_q_01__whole_values_return_int(db):
    """TOI-Q-01 — Decimal('5'), Decimal('5.0'), Decimal('5.00') all return 5 (int).
    Rules: _quantity_to_int R1."""
    for val in (Decimal("5"), Decimal("5.0"), Decimal("5.00")):
        result = _quantity_to_int(val, line_number=1)
        assert result == 5
        assert type(result) is int


def test_toi_q_02__one_is_boundary_whole(db):
    """TOI-Q-02 — Decimal('1') returns 1 (int).
    Rules: _quantity_to_int R1."""
    result = _quantity_to_int(Decimal("1"), line_number=1)
    assert result == 1
    assert type(result) is int


def test_toi_q_03__fractional_rejected(db):
    """TOI-Q-03 — Decimal('2.5') raises 400 fractional-quantity error.
    Rules: _quantity_to_int R2."""
    with pytest.raises(HTTPException) as exc:
        _quantity_to_int(Decimal("2.5"), line_number=2)
    assert exc.value.status_code == 400
    assert exc.value.detail == (
        "Line 2 has a fractional quantity; inventory transfers require whole units"
    )


def test_toi_q_04__small_fraction_rejected(db):
    """TOI-Q-04 — Decimal('0.01') raises 400 fractional-quantity error.
    Rules: _quantity_to_int R2."""
    with pytest.raises(HTTPException) as exc:
        _quantity_to_int(Decimal("0.01"), line_number=3)
    assert exc.value.status_code == 400
    assert exc.value.detail == (
        "Line 3 has a fractional quantity; inventory transfers require whole units"
    )


def test_toi_q_05__large_fraction_rejected(db):
    """TOI-Q-05 — Decimal('10.99') raises 400 fractional-quantity error.
    Rules: _quantity_to_int R2."""
    with pytest.raises(HTTPException) as exc:
        _quantity_to_int(Decimal("10.99"), line_number=7)
    assert exc.value.status_code == 400
    assert exc.value.detail == (
        "Line 7 has a fractional quantity; inventory transfers require whole units"
    )


def test_toi_q_06__zero_rejected(db):
    """TOI-Q-06 — Decimal('0') raises 400 no-quantity error.
    Rules: _quantity_to_int R3."""
    with pytest.raises(HTTPException) as exc:
        _quantity_to_int(Decimal("0"), line_number=4)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Line 4 has no quantity to transfer"


def test_toi_q_07__zero_scaled_rejected(db):
    """TOI-Q-07 — Decimal('0.00') raises 400 no-quantity error.
    Rules: _quantity_to_int R3."""
    with pytest.raises(HTTPException) as exc:
        _quantity_to_int(Decimal("0.00"), line_number=1)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Line 1 has no quantity to transfer"


def test_toi_q_08__negative_whole_rejected(db):
    """TOI-Q-08 — Decimal('-3') raises 400 no-quantity error.
    Rules: _quantity_to_int R3."""
    with pytest.raises(HTTPException) as exc:
        _quantity_to_int(Decimal("-3"), line_number=5)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Line 5 has no quantity to transfer"


def test_toi_q_09__negative_fraction_gets_fractional_message(db):
    """TOI-Q-09 — Decimal('-2.5') gets the fractional-quantity error, not the
    no-quantity error (the fractional check comes first).
    Rules: _quantity_to_int R4."""
    with pytest.raises(HTTPException) as exc:
        _quantity_to_int(Decimal("-2.5"), line_number=6)
    assert exc.value.status_code == 400
    assert exc.value.detail == (
        "Line 6 has a fractional quantity; inventory transfers require whole units"
    )


def test_toi_q_10__item_create_quantity_one(db):
    """TOI-Q-10 — TransferOrderItemCreate(quantity=Decimal('1')) builds; .quantity == 1.
    Rules: _quantity_to_int R5."""
    data = TransferOrderItemCreate(item_id=1, quantity=Decimal("1"))
    assert data.quantity == 1


def test_toi_q_11__item_create_quantity_five_scaled(db):
    """TOI-Q-11 — TransferOrderItemCreate(quantity=Decimal('5.00')) builds; .quantity == 5.
    Rules: _quantity_to_int R5."""
    data = TransferOrderItemCreate(item_id=1, quantity=Decimal("5.00"))
    assert data.quantity == 5


def test_toi_q_12__item_update_quantity_five(db):
    """TOI-Q-12 — TransferOrderItemUpdate(quantity=Decimal('5')) builds; .quantity == 5.
    Rules: _quantity_to_int R5."""
    data = TransferOrderItemUpdate(quantity=Decimal("5"))
    assert data.quantity == 5


@pytest.mark.xfail(strict=True, reason=BUG_824)
def test_toi_q_13__item_create_fractional_quantity_accepted(db):
    """TOI-Q-13 — TransferOrderItemCreate(quantity=Decimal('2.5')) should raise
    ValidationError on quantity.
    Rules: _quantity_to_int R5 [BUG-824]."""
    with pytest.raises(ValidationError) as exc:
        TransferOrderItemCreate(item_id=1, quantity=Decimal("2.5"))
    assert any(e["loc"] == ("quantity",) for e in exc.value.errors())


@pytest.mark.xfail(strict=True, reason=BUG_824)
def test_toi_q_14__item_create_zero_quantity_accepted(db):
    """TOI-Q-14 — TransferOrderItemCreate(quantity=Decimal('0')) should raise ValidationError.
    Rules: _quantity_to_int R5 [BUG-824]."""
    with pytest.raises(ValidationError) as exc:
        TransferOrderItemCreate(item_id=1, quantity=Decimal("0"))
    assert any(e["loc"] == ("quantity",) for e in exc.value.errors())


@pytest.mark.xfail(strict=True, reason=BUG_824)
def test_toi_q_15__item_create_negative_quantity_accepted(db):
    """TOI-Q-15 — TransferOrderItemCreate(quantity=Decimal('-3')) should raise ValidationError.
    Rules: _quantity_to_int R5 [BUG-824]."""
    with pytest.raises(ValidationError) as exc:
        TransferOrderItemCreate(item_id=1, quantity=Decimal("-3"))
    assert any(e["loc"] == ("quantity",) for e in exc.value.errors())


@pytest.mark.xfail(strict=True, reason=BUG_824)
def test_toi_q_16__item_update_fractional_quantity_accepted(db):
    """TOI-Q-16 — TransferOrderItemUpdate(quantity=Decimal('2.5')) should raise ValidationError.
    Rules: _quantity_to_int R5 [BUG-824]."""
    with pytest.raises(ValidationError) as exc:
        TransferOrderItemUpdate(quantity=Decimal("2.5"))
    assert any(e["loc"] == ("quantity",) for e in exc.value.errors())


@pytest.mark.xfail(strict=True, reason=BUG_824)
def test_toi_q_17__item_update_zero_quantity_accepted(db):
    """TOI-Q-17 — TransferOrderItemUpdate(quantity=Decimal('0')) should raise ValidationError.
    Rules: _quantity_to_int R5 [BUG-824]."""
    with pytest.raises(ValidationError) as exc:
        TransferOrderItemUpdate(quantity=Decimal("0"))
    assert any(e["loc"] == ("quantity",) for e in exc.value.errors())


@pytest.mark.xfail(strict=True, reason=BUG_824)
def test_toi_q_18__item_update_negative_quantity_accepted(db):
    """TOI-Q-18 — TransferOrderItemUpdate(quantity=Decimal('-3')) should raise ValidationError.
    Rules: _quantity_to_int R5 [BUG-824]."""
    with pytest.raises(ValidationError) as exc:
        TransferOrderItemUpdate(quantity=Decimal("-3"))
    assert any(e["loc"] == ("quantity",) for e in exc.value.errors())


# =========================================================================== #
# _line_already_posted
# =========================================================================== #

@pytest.fixture
def lp_lines(db, w1, st, u1, i1):
    """Setup for all LP cases: TO with lines L (qty 3.00, line 2) and L2 (line 3)."""
    to = mk_order(db, w1, st, u1, source_type="storage", source_id=1,
                  dest_type="machine", dest_id=1)
    mk_line(db, to, i1, "1.00", 1)  # throw-away so TO.id differs from both line ids
    line = mk_line(db, to, i1, "3.00", 2)
    line2 = mk_line(db, to, i1, "1.00", 3)
    return to, line, line2


def test_toi_lp_01__inventory_ledger_row_true(db, w1, lp_lines, f1, i1, u1):
    """TOI-LP-01 — a matching inventory_ledger row -> True.
    Rules: _line_already_posted R1, R4."""
    to, line, _line2 = lp_lines
    row = InventoryLedger(
        workspace_id=w1.id, inventory_type=STORAGE, factory_id=f1.id, item_id=i1.id,
        transaction_type="transfer_out", quantity=3, qty_before=0, qty_after=0,
        source_type="transfer_order", source_id=line.id, performed_by=u1.id,
    )
    db.add(row)
    db.flush()
    assert _line_already_posted(db, w1.id, line.id) is True


def test_toi_lp_02__machine_ledger_row_true(db, w1, lp_lines, m1, i1, u1):
    """TOI-LP-02 — no inventory ledger row but a matching machine ledger row -> True.
    Rules: _line_already_posted R2, R4."""
    to, line, _line2 = lp_lines
    row = MachineItemLedger(
        workspace_id=w1.id, machine_id=m1.id, item_id=i1.id, transaction_type="transfer_in",
        quantity=3, unit_cost=Decimal(0), total_cost=Decimal(0), qty_before=0, qty_after=0,
        source_type="transfer_order", source_id=line.id, performed_by=u1.id,
    )
    db.add(row)
    db.flush()
    assert _line_already_posted(db, w1.id, line.id) is True


def test_toi_lp_03__rows_for_other_line_false(db, w1, lp_lines, f1, m1, i1, u1):
    """TOI-LP-03 — rows exist only for L2, not L -> False.
    Rules: _line_already_posted R3."""
    to, line, line2 = lp_lines
    db.add(InventoryLedger(
        workspace_id=w1.id, inventory_type=STORAGE, factory_id=f1.id, item_id=i1.id,
        transaction_type="transfer_out", quantity=1, qty_before=0, qty_after=0,
        source_type="transfer_order", source_id=line2.id, performed_by=u1.id,
    ))
    db.add(MachineItemLedger(
        workspace_id=w1.id, machine_id=m1.id, item_id=i1.id, transaction_type="transfer_in",
        quantity=1, unit_cost=Decimal(0), total_cost=Decimal(0), qty_before=0, qty_after=0,
        source_type="transfer_order", source_id=line2.id, performed_by=u1.id,
    ))
    db.flush()
    assert _line_already_posted(db, w1.id, line.id) is False


def test_toi_lp_04__any_transaction_type_counts_inventory(db, w1, lp_lines, f1, i1, u1):
    """TOI-LP-04 — a transfer_in inventory ledger row still counts -> True.
    Rules: _line_already_posted R4."""
    to, line, _line2 = lp_lines
    db.add(InventoryLedger(
        workspace_id=w1.id, inventory_type=STORAGE, factory_id=f1.id, item_id=i1.id,
        transaction_type="transfer_in", quantity=3, qty_before=0, qty_after=3,
        source_type="transfer_order", source_id=line.id, performed_by=u1.id,
    ))
    db.flush()
    assert _line_already_posted(db, w1.id, line.id) is True


def test_toi_lp_05__any_transaction_type_counts_machine(db, w1, lp_lines, m1, i1, u1):
    """TOI-LP-05 — a transfer_out machine ledger row still counts -> True.
    Rules: _line_already_posted R4."""
    to, line, _line2 = lp_lines
    db.add(MachineItemLedger(
        workspace_id=w1.id, machine_id=m1.id, item_id=i1.id, transaction_type="transfer_out",
        quantity=3, unit_cost=Decimal(0), total_cost=Decimal(0), qty_before=3, qty_after=0,
        source_type="transfer_order", source_id=line.id, performed_by=u1.id,
    ))
    db.flush()
    assert _line_already_posted(db, w1.id, line.id) is True


def test_toi_lp_06__other_workspace_inventory_row_ignored(db, w1, lp_lines, fx, ix, u2):
    """TOI-LP-06 — a matching row in W2 does not count for W1 -> False.
    Rules: _line_already_posted R5."""
    to, line, _line2 = lp_lines
    db.add(InventoryLedger(
        workspace_id=fx.workspace_id, inventory_type=STORAGE, factory_id=fx.id, item_id=ix.id,
        transaction_type="transfer_out", quantity=3, qty_before=0, qty_after=0,
        source_type="transfer_order", source_id=line.id, performed_by=u2.id,
    ))
    db.flush()
    assert _line_already_posted(db, w1.id, line.id) is False


def test_toi_lp_07__other_workspace_machine_row_ignored(db, w1, lp_lines, mx, ix, u2):
    """TOI-LP-07 — a matching machine row in W2 does not count for W1 -> False.
    Rules: _line_already_posted R5."""
    to, line, _line2 = lp_lines
    db.add(MachineItemLedger(
        workspace_id=mx.workspace_id, machine_id=mx.id, item_id=ix.id,
        transaction_type="transfer_in", quantity=3, unit_cost=Decimal(0), total_cost=Decimal(0),
        qty_before=0, qty_after=0, source_type="transfer_order", source_id=line.id,
        performed_by=u2.id,
    ))
    db.flush()
    assert _line_already_posted(db, w1.id, line.id) is False


def test_toi_lp_08__different_source_type_inventory_ignored(db, w1, lp_lines, f1, i1, u1):
    """TOI-LP-08 — same source_id but source_type='purchase_order' does not count.
    Rules: _line_already_posted R5."""
    to, line, _line2 = lp_lines
    db.add(InventoryLedger(
        workspace_id=w1.id, inventory_type=STORAGE, factory_id=f1.id, item_id=i1.id,
        transaction_type="purchase_receive", quantity=3, qty_before=0, qty_after=3,
        source_type="purchase_order", source_id=line.id, performed_by=u1.id,
    ))
    db.flush()
    assert _line_already_posted(db, w1.id, line.id) is False


def test_toi_lp_09__different_source_type_machine_ignored(db, w1, lp_lines, m1, i1, u1):
    """TOI-LP-09 — same source_id but source_type='work_order' does not count.
    Rules: _line_already_posted R5."""
    to, line, _line2 = lp_lines
    db.add(MachineItemLedger(
        workspace_id=w1.id, machine_id=m1.id, item_id=i1.id, transaction_type="consumption",
        quantity=3, unit_cost=Decimal(0), total_cost=Decimal(0), qty_before=3, qty_after=0,
        source_type="work_order", source_id=line.id, performed_by=u1.id,
    ))
    db.flush()
    assert _line_already_posted(db, w1.id, line.id) is False


def test_toi_lp_10__order_id_not_line_id_false(db, w1, lp_lines, f1, i1, u1):
    """TOI-LP-10 — a row keyed by the order id (not the line id) does not count.
    Rules: _line_already_posted R1, R3."""
    to, line, _line2 = lp_lines
    db.add(InventoryLedger(
        workspace_id=w1.id, inventory_type=STORAGE, factory_id=f1.id, item_id=i1.id,
        transaction_type="transfer_out", quantity=3, qty_before=0, qty_after=0,
        source_type="transfer_order", source_id=to.id, performed_by=u1.id,
    ))
    db.flush()
    assert _line_already_posted(db, w1.id, line.id) is False


# =========================================================================== #
# _post_location_out
# =========================================================================== #

def test_toi_out_01__unsupported_type_project(db, w1, st, u1, i1, f1, m2):
    """TOI-OUT-01 — location_type='project' raises 400; nothing written.
    Rules: _post_location_out R1."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_stock(db, w1, f1, i1, STORAGE, u1, qty=10, avg_price=Decimal("4.00"))
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        call_out(db, w1, u1, to, line, location_type="project", location_id=f1.id,
                 qty=3, item_id=i1.id, dest_id=m2.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Unsupported source location type: project"
    assert_nw(before, nw_snapshot(db))


def test_toi_out_02__unsupported_type_miscased(db, w1, st, u1, i1, f1, m2):
    """TOI-OUT-02 — location_type='Storage' (miscased) raises 400; nothing written.
    Rules: _post_location_out R1."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_stock(db, w1, f1, i1, STORAGE, u1, qty=10, avg_price=Decimal("4.00"))
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        call_out(db, w1, u1, to, line, location_type="Storage", location_id=f1.id,
                 qty=3, item_id=i1.id, dest_id=m2.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Unsupported source location type: Storage"
    assert_nw(before, nw_snapshot(db))


def test_toi_out_03__unsupported_type_empty(db, w1, st, u1, i1, f1, m2):
    """TOI-OUT-03 — location_type='' raises 400; nothing written.
    Rules: _post_location_out R1."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_stock(db, w1, f1, i1, STORAGE, u1, qty=10, avg_price=Decimal("4.00"))
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        call_out(db, w1, u1, to, line, location_type="", location_id=f1.id,
                 qty=3, item_id=i1.id, dest_id=m2.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Unsupported source location type: "
    assert_nw(before, nw_snapshot(db))


def test_toi_out_04__storage_happy_path(db, w1, st, u1, i1, f1, m2):
    """TOI-OUT-04 — storage out happy path: ledger row, bucket update, untouched buckets.
    Rules: _post_location_out R2, R4, R6, R7."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_stock(db, w1, f1, i1, STORAGE, u1, qty=10, avg_price=Decimal("4.00"))
    result = call_out(db, w1, u1, to, line, location_type="storage", location_id=f1.id,
                       qty=3, item_id=i1.id, dest_id=m2.id)
    assert result == Decimal("4.00")
    rows = last_inv_ledger_for_line(db, line)
    assert len(rows) == 1
    assert_fields(
        rows[0], workspace_id=w1.id, inventory_type=STORAGE, factory_id=f1.id, item_id=i1.id,
        transaction_type="transfer_out", quantity=3, unit_cost=Decimal("4.00"),
        total_cost=Decimal("12.00"), qty_before=10, qty_after=7,
        avg_price_before=Decimal("4.00"), avg_price_after=Decimal("4.00"),
        transfer_destination_type="machine", transfer_destination_id=m2.id,
        transfer_source_type=None, transfer_source_id=None,
        notes="TR-2026-004 line 2 transfer out", performed_by=u1.id,
    )
    bucket = get_bucket(db, w1, f1, i1, STORAGE)
    assert_fields(bucket, qty=7, avg_price=Decimal("4.00"), updated_by=u1.id)
    assert get_bucket(db, w1, f1, i1, DAMAGED) is None
    assert db.scalar(select(func.count()).select_from(MachineActivityEvent)) == 0
    assert last_machine_ledger_for_line(db, line) == []


def test_toi_out_05__damaged_bucket_independent_of_storage(db, w1, st, u1, i1, f1, m2):
    """TOI-OUT-05 — damaged out touches only the DAMAGED bucket, not STORAGE.
    Rules: _post_location_out R2, R6, R7."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_stock(db, w1, f1, i1, DAMAGED, u1, qty=6, avg_price=Decimal("2.50"))
    seed_stock(db, w1, f1, i1, STORAGE, u1, qty=10, avg_price=Decimal("4.00"))
    result = call_out(db, w1, u1, to, line, location_type="damaged", location_id=f1.id,
                       qty=2, item_id=i1.id, dest_id=m2.id)
    assert result == Decimal("2.50")
    rows = last_inv_ledger_for_line(db, line)
    assert len(rows) == 1
    assert_fields(
        rows[0], inventory_type=DAMAGED, qty_before=6, qty_after=4,
        unit_cost=Decimal("2.50"), total_cost=Decimal("5.00"),
    )
    damaged = get_bucket(db, w1, f1, i1, DAMAGED)
    assert_fields(damaged, qty=4, avg_price=Decimal("2.50"))
    storage = get_bucket(db, w1, f1, i1, STORAGE)
    assert_fields(storage, qty=10, avg_price=Decimal("4.00"))


def test_toi_out_06__ledger_only_bucket_created(db, w1, st, u1, i1, f1, m2):
    """TOI-OUT-06 — a ledger-only bucket (no inventory row) is created on posting.
    Rules: _post_location_out R4."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_stock(db, w1, f1, i1, STORAGE, u1, qty=5, avg_price=Decimal("3.00"), ledger_only=True)
    result = call_out(db, w1, u1, to, line, location_type="storage", location_id=f1.id,
                       qty=2, item_id=i1.id, dest_id=m2.id)
    assert result == Decimal("3.00")
    bucket = get_bucket(db, w1, f1, i1, STORAGE)
    assert_fields(
        bucket, qty=3, avg_price=Decimal("3.00"), created_by=u1.id, updated_by=u1.id,
        is_deleted=False,
    )
    rows = last_inv_ledger_for_line(db, line)
    assert len(rows) == 1
    assert_fields(rows[0], qty_before=5, qty_after=3)


def test_toi_out_07__soft_deleted_bucket_restored(db, w1, st, u1, i1, f1, m2):
    """TOI-OUT-07 — a soft-deleted bucket is restored and aligned before posting.
    Rules: _post_location_out R4."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_ledger(db, w1, f1, i1, STORAGE, u1, qty_after=8, avg_price_after=Decimal("5.00"))
    deleted_row = seed_inventory_row(
        db, w1, f1, i1, STORAGE, u1, qty=0, avg_price=None, deleted=True,
    )
    result = call_out(db, w1, u1, to, line, location_type="storage", location_id=f1.id,
                       qty=3, item_id=i1.id, dest_id=m2.id)
    assert result == Decimal("5.00")
    bucket = get_bucket(db, w1, f1, i1, STORAGE)
    assert bucket.id == deleted_row.id
    assert_fields(
        bucket, is_deleted=False, is_active=True, deleted_at=None, deleted_by=None,
        qty=5, avg_price=Decimal("5.00"),
    )
    rows = last_inv_ledger_for_line(db, line)
    assert len(rows) == 1
    assert_fields(rows[0], qty_before=8, qty_after=5)


def test_toi_out_08__aligned_to_latest_ledger_not_stale_inventory_row(db, w1, st, u1, i1, f1, m2):
    """TOI-OUT-08 — the bucket's stale inventory row is realigned to the latest ledger entry.
    Rules: _post_location_out R4."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_ledger(db, w1, f1, i1, STORAGE, u1, qty_after=99, avg_price_after=Decimal("1.00"),
                performed_at=PAST)
    seed_ledger(db, w1, f1, i1, STORAGE, u1, qty_after=10, avg_price_after=Decimal("4.00"),
                performed_at=NEWER)
    seed_inventory_row(db, w1, f1, i1, STORAGE, u1, qty=50, avg_price=Decimal("9.00"))
    result = call_out(db, w1, u1, to, line, location_type="storage", location_id=f1.id,
                       qty=3, item_id=i1.id, dest_id=m2.id)
    assert result == Decimal("4.00")
    rows = last_inv_ledger_for_line(db, line)
    assert_fields(rows[0], qty_before=10, qty_after=7, unit_cost=Decimal("4.00"),
                  avg_price_before=Decimal("4.00"))
    bucket = get_bucket(db, w1, f1, i1, STORAGE)
    assert_fields(bucket, qty=7, avg_price=Decimal("4.00"))


def test_toi_out_09__other_buckets_newer_rows_do_not_matter(db, w1, st, u1, i1, i2, f1, f2, m2):
    """TOI-OUT-09 — newer ledger rows for other buckets do not affect this bucket's latest.
    Rules: _post_location_out R4."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_stock(db, w1, f1, i1, STORAGE, u1, qty=10, avg_price=Decimal("4.00"), performed_at=PAST)
    seed_ledger(db, w1, f1, i1, DAMAGED, u1, qty_after=50, avg_price_after=Decimal("9.00"),
                performed_at=NEWEST)
    seed_ledger(db, w1, f2, i1, STORAGE, u1, qty_after=60, avg_price_after=Decimal("8.00"),
                performed_at=NEWEST)
    seed_ledger(db, w1, f1, i2, STORAGE, u1, qty_after=70, avg_price_after=Decimal("7.00"),
                performed_at=NEWEST)
    result = call_out(db, w1, u1, to, line, location_type="storage", location_id=f1.id,
                       qty=3, item_id=i1.id, dest_id=m2.id)
    assert result == Decimal("4.00")
    rows = last_inv_ledger_for_line(db, line)
    assert_fields(rows[0], qty_before=10, qty_after=7)


def test_toi_out_10__shortage_aligns_bucket_before_raising(db, w1, st, u1, i1, f1, m2):
    """TOI-OUT-10 — a stale inventory row with no ledger history is aligned to 0/null
    before the shortage check raises.
    Rules: _post_location_out R4, R5."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_inventory_row(db, w1, f1, i1, STORAGE, u1, qty=20, avg_price=Decimal("4.00"))
    with pytest.raises(HTTPException) as exc:
        call_out(db, w1, u1, to, line, location_type="storage", location_id=f1.id,
                  qty=1, item_id=i1.id, dest_id=m2.id)
    assert exc.value.status_code == 400
    assert "stock (0 available, 1 requested)" in exc.value.detail
    bucket = get_bucket(db, w1, f1, i1, STORAGE)
    assert bucket.qty == 0
    assert bucket.avg_price is None
    assert last_inv_ledger_for_line(db, line) == []
    assert db.scalar(select(func.count()).select_from(MachineActivityEvent)) == 0


def test_toi_out_11__exact_available_leaves_zero(db, w1, st, u1, i1, f1, m2):
    """TOI-OUT-11 — qty exactly equal to available stock is allowed and leaves 0.
    Rules: _post_location_out R5, R7."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_stock(db, w1, f1, i1, STORAGE, u1, qty=5, avg_price=Decimal("4.00"))
    result = call_out(db, w1, u1, to, line, location_type="storage", location_id=f1.id,
                       qty=5, item_id=i1.id, dest_id=m2.id)
    assert result == Decimal("4.00")
    rows = last_inv_ledger_for_line(db, line)
    assert_fields(rows[0], qty_before=5, qty_after=0, total_cost=Decimal("20.00"))
    bucket = get_bucket(db, w1, f1, i1, STORAGE)
    assert_fields(bucket, qty=0, avg_price=Decimal("4.00"))


def test_toi_out_12__shortage_rejected(db, w1, st, u1, i1, f1, m2):
    """TOI-OUT-12 — requesting more than available raises 400; nothing written.
    Rules: _post_location_out R5."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_stock(db, w1, f1, i1, STORAGE, u1, qty=5, avg_price=Decimal("4.00"))
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        call_out(db, w1, u1, to, line, location_type="storage", location_id=f1.id,
                  qty=6, item_id=i1.id, dest_id=m2.id)
    assert exc.value.status_code == 400
    assert "stock (5 available, 6 requested)" in exc.value.detail
    bucket = get_bucket(db, w1, f1, i1, STORAGE)
    assert_fields(bucket, qty=5, avg_price=Decimal("4.00"))
    assert last_inv_ledger_for_line(db, line) == []
    assert_nw(before, nw_snapshot(db))


@pytest.mark.xfail(strict=True, reason=BUG_826)
def test_toi_out_13__shortage_message_names_line_and_item(db, w1, st, u1, i1, f1, m2):
    """TOI-OUT-13 — the shortage message should name the line and item.
    Rules: _post_location_out R5b [BUG-826]."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_stock(db, w1, f1, i1, STORAGE, u1, qty=5, avg_price=Decimal("4.00"))
    with pytest.raises(HTTPException) as exc:
        call_out(db, w1, u1, to, line, location_type="storage", location_id=f1.id,
                  qty=6, item_id=i1.id, dest_id=m2.id)
    assert exc.value.detail == (
        "Line 2 (Bearing 6204): insufficient stock (5 available, 6 requested)"
    )


@pytest.mark.xfail(strict=True, reason=BUG_826)
def test_toi_out_14__shortage_message_item_not_found_fallback(db, w1, st, u1, i1, f1, m2, ix):
    """TOI-OUT-14 — the shortage message should fall back to "Item #{id}" for an
    item not found in this workspace.
    Rules: _post_location_out R5b [BUG-826]."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    with pytest.raises(HTTPException) as exc:
        call_out(db, w1, u1, to, line, location_type="storage", location_id=f1.id,
                  qty=1, item_id=ix.id, dest_id=m2.id)
    assert exc.value.detail == (
        f"Line 2 (Item #{ix.id}): insufficient stock (0 available, 1 requested)"
    )


def test_toi_out_15__no_stock_creates_bucket_before_raising(db, w1, st, u1, i1, i2, f1, m2):
    """TOI-OUT-15 — no inventory row and no ledger: bucket prep creates a qty-0 row
    before the shortage raises.
    Rules: _post_location_out R5."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    with pytest.raises(HTTPException) as exc:
        call_out(db, w1, u1, to, line, location_type="storage", location_id=f1.id,
                  qty=1, item_id=i2.id, dest_id=m2.id)
    assert exc.value.status_code == 400
    assert "stock (0 available, 1 requested)" in exc.value.detail
    bucket = get_bucket(db, w1, f1, i2, STORAGE)
    assert bucket is not None
    assert_fields(bucket, qty=0, avg_price=None, created_by=u1.id)
    assert last_inv_ledger_for_line(db, line) == []


@pytest.mark.xfail(strict=True, reason=BUG_820)
def test_toi_out_16__storage_lock_before_insert(db, engine, w1, st, u1, i1, f1, m2):
    """TOI-OUT-16 — the storage bucket row should be locked (SELECT ... FOR UPDATE)
    before the availability check / ledger insert.
    Rules: _post_location_out R5a [BUG-820]."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_stock(db, w1, f1, i1, STORAGE, u1, qty=10, avg_price=Decimal("4.00"))
    with SQLCapture(engine) as cap:
        result = call_out(db, w1, u1, to, line, location_type="storage", location_id=f1.id,
                           qty=3, item_id=i1.id, dest_id=m2.id)
    assert result == Decimal("4.00")
    assert_lock_before_insert(cap.statements, "inventory", "inventory_ledger")


def test_toi_out_17__missing_factory_404(db, w1, st, u1, i1, f1, m2):
    """TOI-OUT-17 — an unknown factory id raises 404; nothing written.
    Rules: _post_location_out R3."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_stock(db, w1, f1, i1, STORAGE, u1, qty=10, avg_price=Decimal("4.00"))
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        call_out(db, w1, u1, to, line, location_type="storage", location_id=999999999,
                  qty=3, item_id=i1.id, dest_id=m2.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Factory with ID 999999999 not found"
    assert_nw(before, nw_snapshot(db))


def test_toi_out_18__other_workspace_factory_404(db, w1, w2, st, u1, i1, fx, ix, m2, u2):
    """TOI-OUT-18 — a factory of another workspace raises 404; nothing written.
    Rules: _post_location_out R3."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    # Seed FX/STORAGE/IX in W2 directly (performed_by U2).
    seed_ledger(db, w2, fx, ix, STORAGE, u2, qty_after=10, avg_price_after=Decimal("4.00"))
    seed_inventory_row(db, w2, fx, ix, STORAGE, u2, qty=10, avg_price=Decimal("4.00"))
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        call_out(db, w1, u1, to, line, location_type="storage", location_id=fx.id,
                  qty=3, item_id=ix.id, dest_id=m2.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Factory with ID {fx.id} not found"
    assert_nw(before, nw_snapshot(db))


@pytest.mark.xfail(strict=True, reason=BUG_822)
def test_toi_out_19__soft_deleted_factory_rejected(db, w1, st, u1, i1, fd, m2):
    """TOI-OUT-19 — a soft-deleted factory should be rejected like a missing one.
    Rules: _post_location_out R3a [BUG-822]."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_stock(db, w1, fd, i1, STORAGE, u1, qty=10, avg_price=Decimal("4.00"))
    with pytest.raises(HTTPException) as exc:
        call_out(db, w1, u1, to, line, location_type="storage", location_id=fd.id,
                  qty=3, item_id=i1.id, dest_id=m2.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Factory with ID {fd.id} not found"
    bucket = get_bucket(db, w1, fd, i1, STORAGE)
    assert bucket.qty == 10
    assert last_inv_ledger_for_line(db, line) == []


def test_toi_out_20__machine_happy_path(db, w1, st, u1, i1, m1, f2):
    """TOI-OUT-20 — machine out happy path: ledger row, stock, activity event.
    Rules: _post_location_out R8, R9, R10, R11, R12."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_machine_stock(db, w1, m1, i1, qty=10)
    seed_machine_ledger(db, w1, m1, i1, u1, qty_after=1, avg_price_after=Decimal("1.00"),
                        performed_at=PAST)
    seed_machine_ledger(db, w1, m1, i1, u1, qty_after=99, avg_price_after=Decimal("6.00"),
                        performed_at=NEWER)
    result = call_out(db, w1, u1, to, line, location_type="machine", location_id=m1.id,
                       qty=4, item_id=i1.id, dest_type="storage", dest_id=f2.id)
    assert result == Decimal("6.00")
    rows = last_machine_ledger_for_line(db, line)
    assert len(rows) == 1
    assert_fields(
        rows[0], workspace_id=w1.id, machine_id=m1.id, item_id=i1.id,
        transaction_type="transfer_out", quantity=4, unit_cost=Decimal("6.00"),
        total_cost=Decimal("24.00"), qty_before=10, qty_after=6,
        value_before=Decimal("60.00"), value_after=Decimal("36.00"),
        avg_price_before=Decimal("6.00"), avg_price_after=Decimal("6.00"),
        transfer_destination_type="storage", transfer_destination_id=f2.id,
        notes="TR-2026-004 line 2 transfer out", performed_by=u1.id,
    )
    mi = get_machine_item(db, w1, m1, i1)
    assert mi.qty == 6
    events = events_for_machine(db, m1)
    assert len(events) == 1
    assert_fields(
        events[0], machine_id=m1.id, workspace_id=w1.id, event_type="transfer_out",
        description="Transfer out: 4 units of Bearing 6204 (TR-2026-004)", performed_by=u1.id,
    )
    assert events[0].metadata_json == {"item_id": i1.id, "item_name": "Bearing 6204", "quantity": 4}
    assert "work_order_id" not in events[0].metadata_json
    assert last_inv_ledger_for_line(db, line) == []


def test_toi_out_21__machine_unit_cost_unaffected_by_other_buckets(db, w1, st, u1, i1, i2, m1, m2):
    """TOI-OUT-21 — newer ledger rows for other machine/item combos do not matter.
    Rules: _post_location_out R10."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_machine_stock(db, w1, m1, i1, qty=10)
    seed_machine_ledger(db, w1, m1, i1, u1, qty_after=10, avg_price_after=Decimal("6.00"),
                        performed_at=NEWER)
    seed_machine_ledger(db, w1, m2, i1, u1, qty_after=10, avg_price_after=Decimal("50.00"),
                        performed_at=NEWEST)
    seed_machine_ledger(db, w1, m1, i2, u1, qty_after=10, avg_price_after=Decimal("40.00"),
                        performed_at=NEWEST)
    result = call_out(db, w1, u1, to, line, location_type="machine", location_id=m1.id,
                       qty=1, item_id=i1.id, dest_id=m2.id)
    assert result == Decimal("6.00")
    rows = last_machine_ledger_for_line(db, line)
    assert_fields(rows[0], unit_cost=Decimal("6.00"))


def test_toi_out_22__no_machine_ledger_unit_cost_zero(db, w1, st, u1, i1, m1, m2):
    """TOI-OUT-22 — no machine ledger rows at all -> unit cost 0.
    Rules: _post_location_out R10."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_machine_stock(db, w1, m1, i1, qty=5)
    result = call_out(db, w1, u1, to, line, location_type="machine", location_id=m1.id,
                       qty=2, item_id=i1.id, dest_id=m2.id)
    assert result == 0
    rows = last_machine_ledger_for_line(db, line)
    assert_fields(
        rows[0], unit_cost=0, total_cost=0, value_before=0, value_after=0,
        avg_price_before=0, avg_price_after=0, qty_after=3,
    )
    mi = get_machine_item(db, w1, m1, i1)
    assert mi.qty == 3


def test_toi_out_23__latest_ledger_null_average_is_zero(db, w1, st, u1, i1, m1, m2):
    """TOI-OUT-23 — the latest machine ledger row has a null average -> unit cost 0.
    Rules: _post_location_out R10."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_machine_stock(db, w1, m1, i1, qty=5)
    seed_machine_ledger(db, w1, m1, i1, u1, qty_after=5, avg_price_after=Decimal("7.00"),
                        performed_at=PAST)
    seed_machine_ledger(db, w1, m1, i1, u1, qty_after=5, avg_price_after=None, performed_at=NEWER)
    result = call_out(db, w1, u1, to, line, location_type="machine", location_id=m1.id,
                       qty=2, item_id=i1.id, dest_id=m2.id)
    assert result == 0
    rows = last_machine_ledger_for_line(db, line)
    assert_fields(rows[0], unit_cost=0, avg_price_after=0)


def test_toi_out_24__exact_machine_stock_leaves_zero(db, w1, st, u1, i1, m1, m2):
    """TOI-OUT-24 — qty exactly equal to machine stock is allowed and leaves 0.
    Rules: _post_location_out R9, R11."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_machine_stock(db, w1, m1, i1, qty=4)
    seed_machine_ledger(db, w1, m1, i1, u1, qty_after=4, avg_price_after=Decimal("6.00"),
                        performed_at=NEWER)
    result = call_out(db, w1, u1, to, line, location_type="machine", location_id=m1.id,
                       qty=4, item_id=i1.id, dest_id=m2.id)
    assert result == Decimal("6.00")
    rows = last_machine_ledger_for_line(db, line)
    assert_fields(rows[0], qty_before=4, qty_after=0, value_after=0)
    mi = get_machine_item(db, w1, m1, i1)
    assert mi.qty == 0


def test_toi_out_25__machine_shortage_rejected(db, w1, st, u1, i1, m1, m2):
    """TOI-OUT-25 — requesting more than machine stock raises 400; nothing written.
    Rules: _post_location_out R9."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_machine_stock(db, w1, m1, i1, qty=4)
    seed_machine_ledger(db, w1, m1, i1, u1, qty_after=4, avg_price_after=Decimal("6.00"),
                        performed_at=NEWER)
    with pytest.raises(HTTPException) as exc:
        call_out(db, w1, u1, to, line, location_type="machine", location_id=m1.id,
                  qty=5, item_id=i1.id, dest_id=m2.id)
    assert exc.value.status_code == 400
    assert "stock (4 available, 5 requested)" in exc.value.detail
    mi = get_machine_item(db, w1, m1, i1)
    assert mi.qty == 4
    assert last_machine_ledger_for_line(db, line) == []
    assert db.scalar(select(func.count()).select_from(MachineActivityEvent)) == 0


@pytest.mark.xfail(strict=True, reason=BUG_826)
def test_toi_out_26__machine_shortage_message_names_line_and_item(db, w1, st, u1, i1, m1, m2):
    """TOI-OUT-26 — the machine shortage message should name the line and item.
    Rules: _post_location_out R9a [BUG-826]."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_machine_stock(db, w1, m1, i1, qty=4)
    seed_machine_ledger(db, w1, m1, i1, u1, qty_after=4, avg_price_after=Decimal("6.00"),
                        performed_at=NEWER)
    with pytest.raises(HTTPException) as exc:
        call_out(db, w1, u1, to, line, location_type="machine", location_id=m1.id,
                  qty=5, item_id=i1.id, dest_id=m2.id)
    assert exc.value.detail == (
        "Line 2 (Bearing 6204): insufficient machine stock (4 available, 5 requested)"
    )


@pytest.mark.xfail(strict=True, reason=BUG_826)
def test_toi_out_27__machine_shortage_message_item_not_found_fallback(db, w1, st, u1, i1, m1, m2, ix):
    """TOI-OUT-27 — the machine shortage message falls back to "Item #{id}".
    Rules: _post_location_out R9a [BUG-826]."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    with pytest.raises(HTTPException) as exc:
        call_out(db, w1, u1, to, line, location_type="machine", location_id=m1.id,
                  qty=1, item_id=ix.id, dest_id=m2.id)
    assert exc.value.detail == (
        f"Line 2 (Item #{ix.id}): insufficient machine stock (0 available, 1 requested)"
    )


def test_toi_out_28__no_machine_item_row_created_before_shortage(db, w1, st, u1, i1, i2, m1, m2):
    """TOI-OUT-28 — no machine_items row for the item: one is created (qty 0)
    before the shortage raises.
    Rules: _post_location_out R9."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    with pytest.raises(HTTPException) as exc:
        call_out(db, w1, u1, to, line, location_type="machine", location_id=m1.id,
                  qty=1, item_id=i2.id, dest_id=m2.id)
    assert exc.value.status_code == 400
    assert "stock (0 available, 1 requested)" in exc.value.detail
    mi = get_machine_item(db, w1, m1, i2)
    assert mi is not None
    assert mi.qty == 0
    assert last_machine_ledger_for_line(db, line) == []
    assert db.scalar(select(func.count()).select_from(MachineActivityEvent)) == 0


@pytest.mark.xfail(strict=True, reason=BUG_820)
def test_toi_out_29__machine_lock_before_insert(db, engine, w1, st, u1, i1, m1, m2):
    """TOI-OUT-29 — the machine stock row should be locked (SELECT ... FOR UPDATE)
    before the availability check / ledger insert.
    Rules: _post_location_out R5a, R9 [BUG-820]."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_machine_stock(db, w1, m1, i1, qty=10)
    seed_machine_ledger(db, w1, m1, i1, u1, qty_after=10, avg_price_after=Decimal("6.00"),
                        performed_at=NEWER)
    with SQLCapture(engine) as cap:
        result = call_out(db, w1, u1, to, line, location_type="machine", location_id=m1.id,
                           qty=4, item_id=i1.id, dest_id=m2.id)
    assert result == Decimal("6.00")
    assert_lock_before_insert(cap.statements, "machine_items", "machine_item_ledger")


def test_toi_out_30__missing_machine_404(db, w1, st, u1, i1, m1, m2):
    """TOI-OUT-30 — an unknown machine id raises 404; nothing written.
    Rules: _post_location_out R8."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_machine_stock(db, w1, m1, i1, qty=10)
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        call_out(db, w1, u1, to, line, location_type="machine", location_id=999999999,
                  qty=1, item_id=i1.id, dest_id=m2.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Machine with ID 999999999 not found"
    assert_nw(before, nw_snapshot(db))


def test_toi_out_31__other_workspace_machine_404(db, w1, w2, st, u1, i1, mx, ix, m2):
    """TOI-OUT-31 — a machine of another workspace raises 404; nothing written.
    Rules: _post_location_out R8."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_machine_stock(db, w2, mx, ix, qty=10)
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        call_out(db, w1, u1, to, line, location_type="machine", location_id=mx.id,
                  qty=1, item_id=ix.id, dest_id=m2.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Machine with ID {mx.id} not found"
    assert_nw(before, nw_snapshot(db))


@pytest.mark.xfail(strict=True, reason=BUG_822)
def test_toi_out_32__soft_deleted_machine_rejected(db, w1, st, u1, i1, md, m2):
    """TOI-OUT-32 — a soft-deleted machine should be rejected like a missing one.
    Rules: _post_location_out R8a [BUG-822]."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_machine_stock(db, w1, md, i1, qty=10)
    seed_machine_ledger(db, w1, md, i1, u1, qty_after=10, avg_price_after=Decimal("6.00"),
                        performed_at=NEWER)
    with pytest.raises(HTTPException) as exc:
        call_out(db, w1, u1, to, line, location_type="machine", location_id=md.id,
                  qty=4, item_id=i1.id, dest_id=m2.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Machine with ID {md.id} not found"
    mi = get_machine_item(db, w1, md, i1)
    assert mi.qty == 10
    assert last_machine_ledger_for_line(db, line) == []
    assert events_for_machine(db, md) == []


def test_toi_out_33__unknown_item_label_fallback(db, w1, st, u1, i1, m1, ix, m2):
    """TOI-OUT-33 — an item not found in this workspace falls back to "Item #{id}"
    in the activity event.
    Rules: _post_location_out R12."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_machine_stock(db, w1, m1, ix, qty=3)
    result = call_out(db, w1, u1, to, line, location_type="machine", location_id=m1.id,
                       qty=1, item_id=ix.id, dest_id=m2.id)
    assert result == 0
    events = events_for_machine(db, m1)
    assert len(events) == 1
    assert events[0].description == f"Transfer out: 1 units of Item #{ix.id} (TR-2026-004)"
    assert events[0].metadata_json == {
        "item_id": ix.id, "item_name": f"Item #{ix.id}", "quantity": 1,
    }
    mi = get_machine_item(db, w1, m1, ix)
    assert mi.qty == 2


def test_toi_out_34__null_average_treated_as_zero(db, w1, st, u1, i1, f1, m2):
    """TOI-OUT-34 — a bucket with a null average costs out at 0.
    Rules: _post_location_out R6, R7."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_stock(db, w1, f1, i1, STORAGE, u1, qty=5, avg_price=None)
    result = call_out(db, w1, u1, to, line, location_type="storage", location_id=f1.id,
                       qty=2, item_id=i1.id, dest_id=m2.id)
    assert result == 0
    rows = last_inv_ledger_for_line(db, line)
    assert_fields(
        rows[0], unit_cost=0, total_cost=0, avg_price_before=None, avg_price_after=None,
        qty_after=3,
    )
    bucket = get_bucket(db, w1, f1, i1, STORAGE)
    assert_fields(bucket, qty=3, avg_price=None)


# =========================================================================== #
# _post_location_in
# =========================================================================== #

def test_toi_in_01__project_destination_rejected(db, w1, st, u1, i1, f1, m2):
    """TOI-IN-01 — location_type='project' raises 400; nothing written.
    Rules: _post_location_in R1."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_stock(db, w1, f1, i1, STORAGE, u1, qty=10, avg_price=Decimal("4.00"))
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        call_in(db, w1, u1, to, line, location_type="project", location_id=f1.id,
                qty=3, unit_cost=Decimal("4.00"), item_id=i1.id, source_id=m2.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Project destination inventory posting is not yet supported"
    assert_nw(before, nw_snapshot(db))


def test_toi_in_02__unsupported_type_miscased(db, w1, st, u1, i1, f1, m2):
    """TOI-IN-02 — location_type='Storage' (miscased) raises 400; nothing written.
    Rules: _post_location_in R2."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_stock(db, w1, f1, i1, STORAGE, u1, qty=10, avg_price=Decimal("4.00"))
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        call_in(db, w1, u1, to, line, location_type="Storage", location_id=f1.id,
                qty=3, unit_cost=Decimal("4.00"), item_id=i1.id, source_id=m2.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Unsupported destination location type: Storage"
    assert_nw(before, nw_snapshot(db))


def test_toi_in_03__unsupported_type_warehouse(db, w1, st, u1, i1, f1, m2):
    """TOI-IN-03 — location_type='warehouse' raises 400; nothing written.
    Rules: _post_location_in R2."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_stock(db, w1, f1, i1, STORAGE, u1, qty=10, avg_price=Decimal("4.00"))
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        call_in(db, w1, u1, to, line, location_type="warehouse", location_id=f1.id,
                qty=3, unit_cost=Decimal("4.00"), item_id=i1.id, source_id=m2.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Unsupported destination location type: warehouse"
    assert_nw(before, nw_snapshot(db))


def test_toi_in_04__unsupported_type_empty(db, w1, st, u1, i1, f1, m2):
    """TOI-IN-04 — location_type='' raises 400; nothing written.
    Rules: _post_location_in R2."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_stock(db, w1, f1, i1, STORAGE, u1, qty=10, avg_price=Decimal("4.00"))
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        call_in(db, w1, u1, to, line, location_type="", location_id=f1.id,
                qty=3, unit_cost=Decimal("4.00"), item_id=i1.id, source_id=m2.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Unsupported destination location type: "
    assert_nw(before, nw_snapshot(db))


def test_toi_in_05__storage_happy_path(db, w1, st, u1, i1, f1, m2):
    """TOI-IN-05 — storage in happy path: ledger row, weighted average, untouched buckets.
    Rules: _post_location_in R3, R4, R5, R6."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_stock(db, w1, f1, i1, STORAGE, u1, qty=10, avg_price=Decimal("4.00"))
    result = call_in(db, w1, u1, to, line, location_type="storage", location_id=f1.id,
                      qty=5, unit_cost=Decimal("7.00"), item_id=i1.id, source_id=m2.id)
    assert result is None
    rows = last_inv_ledger_for_line(db, line)
    assert len(rows) == 1
    assert_fields(
        rows[0], workspace_id=w1.id, inventory_type=STORAGE, factory_id=f1.id, item_id=i1.id,
        transaction_type="transfer_in", quantity=5, unit_cost=Decimal("7.00"),
        total_cost=Decimal("35.00"), qty_before=10, qty_after=15,
        avg_price_before=Decimal("4.00"), avg_price_after=Decimal("5.00"),
        transfer_source_type="machine", transfer_source_id=m2.id,
        transfer_destination_type=None, transfer_destination_id=None,
        notes="TR-2026-004 line 2 transfer in", performed_by=u1.id,
    )
    bucket = get_bucket(db, w1, f1, i1, STORAGE)
    assert_fields(bucket, qty=15, avg_price=Decimal("5.00"), updated_by=u1.id)
    assert get_bucket(db, w1, f1, i1, DAMAGED) is None
    assert db.scalar(select(func.count()).select_from(MachineActivityEvent)) == 0
    assert last_machine_ledger_for_line(db, line) == []


def test_toi_in_06__damaged_bucket_independent_of_storage(db, w1, st, u1, i1, f1, m2):
    """TOI-IN-06 — damaged in touches only the DAMAGED bucket, not STORAGE.
    Rules: _post_location_in R3, R5, R6."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_stock(db, w1, f1, i1, DAMAGED, u1, qty=4, avg_price=Decimal("2.00"))
    seed_stock(db, w1, f1, i1, STORAGE, u1, qty=10, avg_price=Decimal("4.00"))
    result = call_in(db, w1, u1, to, line, location_type="damaged", location_id=f1.id,
                      qty=4, unit_cost=Decimal("3.00"), item_id=i1.id, source_id=m2.id)
    assert result is None
    rows = last_inv_ledger_for_line(db, line)
    assert len(rows) == 1
    assert_fields(rows[0], inventory_type=DAMAGED, qty_before=4, qty_after=8,
                  avg_price_after=Decimal("2.50"))
    damaged = get_bucket(db, w1, f1, i1, DAMAGED)
    assert_fields(damaged, qty=8, avg_price=Decimal("2.50"))
    storage = get_bucket(db, w1, f1, i1, STORAGE)
    assert_fields(storage, qty=10, avg_price=Decimal("4.00"))


def test_toi_in_07__weighted_average_rounds_half_even(db, w1, st, u1, i1, f1, m2):
    """TOI-IN-07 — weighted average 4/3 rounds to 1.33.
    Rules: _post_location_in R5."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_stock(db, w1, f1, i1, STORAGE, u1, qty=2, avg_price=Decimal("1.00"))
    result = call_in(db, w1, u1, to, line, location_type="storage", location_id=f1.id,
                      qty=1, unit_cost=Decimal("2.00"), item_id=i1.id, source_id=m2.id)
    assert result is None
    rows = last_inv_ledger_for_line(db, line)
    assert_fields(rows[0], avg_price_after=Decimal("1.33"))
    bucket = get_bucket(db, w1, f1, i1, STORAGE)
    assert_fields(bucket, avg_price=Decimal("1.33"), qty=3)


@pytest.mark.xfail(strict=True, reason=BUG_1040)
def test_toi_in_08__weighted_average_tie_rounds_half_up(db, w1, st, u1, i1, f1, m2):
    """TOI-IN-08 — a half-way weighted average (1.025) rounds half away from zero to 1.03.
    Rules: _post_location_in R5a [BUG-1040]."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_stock(db, w1, f1, i1, STORAGE, u1, qty=1, avg_price=Decimal("1.00"))
    result = call_in(db, w1, u1, to, line, location_type="storage", location_id=f1.id,
                      qty=1, unit_cost=Decimal("1.05"), item_id=i1.id, source_id=m2.id)
    assert result is None
    rows = last_inv_ledger_for_line(db, line)
    assert_fields(rows[0], avg_price_after=Decimal("1.03"))
    bucket = get_bucket(db, w1, f1, i1, STORAGE)
    assert_fields(bucket, avg_price=Decimal("1.03"))


def test_toi_in_09__zero_qty_bucket_uses_unit_cost(db, w1, st, u1, i1, f1, m2):
    """TOI-IN-09 — a bucket at qty 0 (even with a non-null average) falls back to unit_cost.
    Rules: _post_location_in R5."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_ledger(db, w1, f1, i1, STORAGE, u1, qty_after=0, avg_price_after=Decimal("9.00"))
    seed_inventory_row(db, w1, f1, i1, STORAGE, u1, qty=0, avg_price=Decimal("9.00"))
    result = call_in(db, w1, u1, to, line, location_type="storage", location_id=f1.id,
                      qty=3, unit_cost=Decimal("2.00"), item_id=i1.id, source_id=m2.id)
    assert result is None
    rows = last_inv_ledger_for_line(db, line)
    assert_fields(rows[0], qty_before=0, avg_price_before=Decimal("9.00"),
                  avg_price_after=Decimal("2.00"))
    bucket = get_bucket(db, w1, f1, i1, STORAGE)
    assert_fields(bucket, qty=3, avg_price=Decimal("2.00"))


def test_toi_in_10__null_average_uses_unit_cost_not_half(db, w1, st, u1, i1, f1, m2):
    """TOI-IN-10 — a null bucket average falls back to unit_cost (not halved).
    Rules: _post_location_in R5."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_stock(db, w1, f1, i1, STORAGE, u1, qty=5, avg_price=None)
    result = call_in(db, w1, u1, to, line, location_type="storage", location_id=f1.id,
                      qty=5, unit_cost=Decimal("3.00"), item_id=i1.id, source_id=m2.id)
    assert result is None
    rows = last_inv_ledger_for_line(db, line)
    assert_fields(rows[0], avg_price_before=None, avg_price_after=Decimal("3.00"))
    bucket = get_bucket(db, w1, f1, i1, STORAGE)
    assert_fields(bucket, qty=10, avg_price=Decimal("3.00"))


def test_toi_in_11__no_bucket_creates_one(db, w1, st, u1, i1, f1, m2):
    """TOI-IN-11 — no inventory row and no ledger: one is created.
    Rules: _post_location_in R4, R5, R6."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    result = call_in(db, w1, u1, to, line, location_type="storage", location_id=f1.id,
                      qty=3, unit_cost=Decimal("2.00"), item_id=i1.id, source_id=m2.id)
    assert result is None
    bucket = get_bucket(db, w1, f1, i1, STORAGE)
    assert_fields(
        bucket, qty=3, avg_price=Decimal("2.00"), created_by=u1.id, updated_by=u1.id,
        is_deleted=False,
    )
    rows = last_inv_ledger_for_line(db, line)
    assert_fields(
        rows[0], qty_before=0, qty_after=3, avg_price_before=None,
        avg_price_after=Decimal("2.00"), total_cost=Decimal("6.00"),
    )


def test_toi_in_12__soft_deleted_bucket_restored(db, w1, st, u1, i1, f1, m2):
    """TOI-IN-12 — a soft-deleted bucket is restored and aligned before posting in.
    Rules: _post_location_in R4."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_ledger(db, w1, f1, i1, STORAGE, u1, qty_after=4, avg_price_after=Decimal("5.00"))
    deleted_row = seed_inventory_row(
        db, w1, f1, i1, STORAGE, u1, qty=0, avg_price=None, deleted=True,
    )
    result = call_in(db, w1, u1, to, line, location_type="storage", location_id=f1.id,
                      qty=4, unit_cost=Decimal("5.00"), item_id=i1.id, source_id=m2.id)
    assert result is None
    bucket = get_bucket(db, w1, f1, i1, STORAGE)
    assert bucket.id == deleted_row.id
    assert_fields(
        bucket, is_deleted=False, is_active=True, deleted_at=None, deleted_by=None,
        qty=8, avg_price=Decimal("5.00"),
    )
    rows = last_inv_ledger_for_line(db, line)
    assert_fields(rows[0], qty_before=4)


def test_toi_in_13__aligned_to_latest_ledger_not_stale_inventory_row(db, w1, st, u1, i1, f1, m2):
    """TOI-IN-13 — the bucket's stale inventory row is realigned to the latest ledger entry.
    Rules: _post_location_in R4."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_ledger(db, w1, f1, i1, STORAGE, u1, qty_after=99, avg_price_after=Decimal("1.00"),
                performed_at=PAST)
    seed_ledger(db, w1, f1, i1, STORAGE, u1, qty_after=10, avg_price_after=Decimal("4.00"),
                performed_at=NEWER)
    seed_inventory_row(db, w1, f1, i1, STORAGE, u1, qty=50, avg_price=Decimal("9.00"))
    result = call_in(db, w1, u1, to, line, location_type="storage", location_id=f1.id,
                      qty=5, unit_cost=Decimal("7.00"), item_id=i1.id, source_id=m2.id)
    assert result is None
    rows = last_inv_ledger_for_line(db, line)
    assert_fields(rows[0], qty_before=10, avg_price_before=Decimal("4.00"),
                  avg_price_after=Decimal("5.00"))
    bucket = get_bucket(db, w1, f1, i1, STORAGE)
    assert_fields(bucket, qty=15, avg_price=Decimal("5.00"))


def test_toi_in_14__no_ledger_history_ignores_stale_inventory_row(db, w1, st, u1, i1, f1, m2):
    """TOI-IN-14 — a stale inventory row with no ledger history is treated as empty.
    Rules: _post_location_in R4."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_inventory_row(db, w1, f1, i1, STORAGE, u1, qty=20, avg_price=Decimal("9.00"))
    result = call_in(db, w1, u1, to, line, location_type="storage", location_id=f1.id,
                      qty=3, unit_cost=Decimal("2.00"), item_id=i1.id, source_id=m2.id)
    assert result is None
    rows = last_inv_ledger_for_line(db, line)
    assert_fields(rows[0], qty_before=0, avg_price_before=None, avg_price_after=Decimal("2.00"))
    bucket = get_bucket(db, w1, f1, i1, STORAGE)
    assert_fields(bucket, qty=3, avg_price=Decimal("2.00"))


def test_toi_in_15__zero_unit_cost_accepted_and_averaged(db, w1, st, u1, i1, f1, m2):
    """TOI-IN-15 — a unit cost of 0 is accepted and lowers the destination average.
    Rules: _post_location_in R7."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_stock(db, w1, f1, i1, STORAGE, u1, qty=10, avg_price=Decimal("4.00"))
    result = call_in(db, w1, u1, to, line, location_type="storage", location_id=f1.id,
                      qty=10, unit_cost=Decimal("0"), item_id=i1.id, source_id=m2.id)
    assert result is None
    rows = last_inv_ledger_for_line(db, line)
    assert_fields(rows[0], unit_cost=0, total_cost=0, avg_price_after=Decimal("2.00"))
    bucket = get_bucket(db, w1, f1, i1, STORAGE)
    assert_fields(bucket, qty=20, avg_price=Decimal("2.00"))


def test_toi_in_16__missing_factory_404(db, w1, st, u1, i1, m2):
    """TOI-IN-16 — an unknown factory id raises 404; nothing written.
    Rules: _post_location_in R4."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        call_in(db, w1, u1, to, line, location_type="storage", location_id=999999999,
                qty=3, unit_cost=Decimal("4.00"), item_id=i1.id, source_id=m2.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Factory with ID 999999999 not found"
    assert_nw(before, nw_snapshot(db))


def test_toi_in_17__other_workspace_factory_404(db, w1, w2, st, u1, i1, fx, ix, m2):
    """TOI-IN-17 — a factory of another workspace raises 404; nothing written.
    Rules: _post_location_in R4."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    u2x = make_profile(db)
    seed_ledger(db, w2, fx, ix, STORAGE, u2x, qty_after=10, avg_price_after=Decimal("4.00"))
    seed_inventory_row(db, w2, fx, ix, STORAGE, u2x, qty=10, avg_price=Decimal("4.00"))
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        call_in(db, w1, u1, to, line, location_type="storage", location_id=fx.id,
                qty=3, unit_cost=Decimal("4.00"), item_id=ix.id, source_id=m2.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Factory with ID {fx.id} not found"
    assert_nw(before, nw_snapshot(db))


@pytest.mark.xfail(strict=True, reason=BUG_822)
def test_toi_in_18__soft_deleted_factory_rejected(db, w1, st, u1, i1, fd, m2):
    """TOI-IN-18 — a soft-deleted factory should be rejected like a missing one.
    Rules: _post_location_in R4 [BUG-822]."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_stock(db, w1, fd, i1, STORAGE, u1, qty=10, avg_price=Decimal("4.00"))
    with pytest.raises(HTTPException) as exc:
        call_in(db, w1, u1, to, line, location_type="storage", location_id=fd.id,
                qty=3, unit_cost=Decimal("4.00"), item_id=i1.id, source_id=m2.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Factory with ID {fd.id} not found"
    bucket = get_bucket(db, w1, fd, i1, STORAGE)
    assert bucket.qty == 10
    assert last_inv_ledger_for_line(db, line) == []


def test_toi_in_19__machine_happy_path(db, w1, st, u1, i1, m1, f2):
    """TOI-IN-19 — machine in happy path: ledger row, stock, activity event.
    Rules: _post_location_in R8, R9, R10, R11."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_machine_stock(db, w1, m1, i1, qty=10)
    seed_machine_ledger(db, w1, m1, i1, u1, qty_after=1, avg_price_after=Decimal("1.00"),
                        performed_at=PAST)
    seed_machine_ledger(db, w1, m1, i1, u1, qty_after=99, avg_price_after=Decimal("4.00"),
                        performed_at=NEWER)
    result = call_in(db, w1, u1, to, line, location_type="machine", location_id=m1.id,
                      qty=5, unit_cost=Decimal("7.00"), item_id=i1.id,
                      source_type="storage", source_id=f2.id)
    assert result is None
    rows = last_machine_ledger_for_line(db, line)
    assert len(rows) == 1
    assert_fields(
        rows[0], workspace_id=w1.id, machine_id=m1.id, item_id=i1.id,
        transaction_type="transfer_in", quantity=5, unit_cost=Decimal("7.00"),
        total_cost=Decimal("35.00"), qty_before=10, qty_after=15,
        value_before=Decimal("40.00"), value_after=Decimal("75.00"),
        avg_price_before=Decimal("4.00"), avg_price_after=Decimal("5.00"),
        transfer_source_type="storage", transfer_source_id=f2.id,
        notes="TR-2026-004 line 2 transfer in", performed_by=u1.id,
    )
    mi = get_machine_item(db, w1, m1, i1)
    assert mi.qty == 15
    events = events_for_machine(db, m1)
    assert len(events) == 1
    assert_fields(
        events[0], workspace_id=w1.id, event_type="transfer_in",
        description="Transfer in: 5 units of Bearing 6204 (TR-2026-004)", performed_by=u1.id,
    )
    assert events[0].metadata_json == {"item_id": i1.id, "item_name": "Bearing 6204", "quantity": 5}
    assert last_inv_ledger_for_line(db, line) == []


def test_toi_in_20__zero_stock_uses_unit_cost_not_weighted(db, w1, st, u1, i1, m1, m2):
    """TOI-IN-20 — a machine at stock 0 (even with a ledger average) falls back to unit_cost.
    Rules: _post_location_in R9."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_machine_stock(db, w1, m1, i1, qty=0)
    seed_machine_ledger(db, w1, m1, i1, u1, qty_after=0, avg_price_after=Decimal("9.00"),
                        performed_at=NEWER)
    result = call_in(db, w1, u1, to, line, location_type="machine", location_id=m1.id,
                      qty=3, unit_cost=Decimal("2.00"), item_id=i1.id, source_id=m2.id)
    assert result is None
    rows = last_machine_ledger_for_line(db, line)
    assert_fields(
        rows[0], qty_before=0, avg_price_before=Decimal("9.00"), avg_price_after=Decimal("2.00"),
        value_before=0, value_after=Decimal("6.00"),
    )
    mi = get_machine_item(db, w1, m1, i1)
    assert mi.qty == 3


def test_toi_in_21__no_ledger_rows_avg_before_zero(db, w1, st, u1, i1, m1, m2):
    """TOI-IN-21 — no machine ledger rows at all -> avg_before 0, weighted with it.
    Rules: _post_location_in R9."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_machine_stock(db, w1, m1, i1, qty=5)
    result = call_in(db, w1, u1, to, line, location_type="machine", location_id=m1.id,
                      qty=5, unit_cost=Decimal("4.00"), item_id=i1.id, source_id=m2.id)
    assert result is None
    rows = last_machine_ledger_for_line(db, line)
    assert_fields(
        rows[0], avg_price_before=0, avg_price_after=Decimal("2.00"),
        value_before=0, value_after=Decimal("20.00"),
    )
    mi = get_machine_item(db, w1, m1, i1)
    assert mi.qty == 10


def test_toi_in_22__weighted_average_rounds_half_even(db, w1, st, u1, i1, m1, m2):
    """TOI-IN-22 — weighted average 4/3 rounds to 1.33; value_after uses the rounded average.
    Rules: _post_location_in R9, R10."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_machine_stock(db, w1, m1, i1, qty=2)
    seed_machine_ledger(db, w1, m1, i1, u1, qty_after=2, avg_price_after=Decimal("1.00"),
                        performed_at=NEWER)
    result = call_in(db, w1, u1, to, line, location_type="machine", location_id=m1.id,
                      qty=1, unit_cost=Decimal("2.00"), item_id=i1.id, source_id=m2.id)
    assert result is None
    rows = last_machine_ledger_for_line(db, line)
    assert_fields(rows[0], avg_price_after=Decimal("1.33"), value_after=Decimal("3.99"),
                  value_before=Decimal("2.00"))


def test_toi_in_23__unit_cost_unaffected_by_other_buckets(db, w1, st, u1, i1, i2, m1, m2):
    """TOI-IN-23 — newer ledger rows for other machine/item combos do not matter.
    Rules: _post_location_in R9."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_machine_stock(db, w1, m1, i1, qty=10)
    seed_machine_ledger(db, w1, m1, i1, u1, qty_after=10, avg_price_after=Decimal("4.00"),
                        performed_at=NEWER)
    seed_machine_ledger(db, w1, m2, i1, u1, qty_after=10, avg_price_after=Decimal("50.00"),
                        performed_at=NEWEST)
    seed_machine_ledger(db, w1, m1, i2, u1, qty_after=10, avg_price_after=Decimal("40.00"),
                        performed_at=NEWEST)
    result = call_in(db, w1, u1, to, line, location_type="machine", location_id=m1.id,
                      qty=5, unit_cost=Decimal("7.00"), item_id=i1.id, source_id=m2.id)
    assert result is None
    rows = last_machine_ledger_for_line(db, line)
    assert_fields(rows[0], avg_price_before=Decimal("4.00"), avg_price_after=Decimal("5.00"))


def test_toi_in_24__no_machine_item_row_created(db, w1, st, u1, i1, i2, m1, m2):
    """TOI-IN-24 — no machine_items row for the item: one is created.
    Rules: _post_location_in R8, R10."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    result = call_in(db, w1, u1, to, line, location_type="machine", location_id=m1.id,
                      qty=3, unit_cost=Decimal("2.00"), item_id=i2.id, source_id=m2.id)
    assert result is None
    mi_rows = get_machine_items_all(db, w1, m1, i2)
    assert len(mi_rows) == 1
    mi = mi_rows[0]
    assert mi.qty == 3
    rows = last_machine_ledger_for_line(db, line)
    assert_fields(rows[0], qty_before=0, qty_after=3, avg_price_after=Decimal("2.00"),
                  total_cost=Decimal("6.00"))


def test_toi_in_25__missing_machine_404(db, w1, st, u1, i1, m2):
    """TOI-IN-25 — an unknown machine id raises 404; nothing written.
    Rules: _post_location_in R8."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        call_in(db, w1, u1, to, line, location_type="machine", location_id=999999999,
                qty=1, unit_cost=Decimal("1.00"), item_id=i1.id, source_id=m2.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Machine with ID 999999999 not found"
    assert_nw(before, nw_snapshot(db))


def test_toi_in_26__other_workspace_machine_404(db, w1, w2, st, u1, i1, mx, ix, m2):
    """TOI-IN-26 — a machine of another workspace raises 404; nothing written.
    Rules: _post_location_in R8."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_machine_stock(db, w2, mx, ix, qty=10)
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        call_in(db, w1, u1, to, line, location_type="machine", location_id=mx.id,
                qty=1, unit_cost=Decimal("1.00"), item_id=ix.id, source_id=m2.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Machine with ID {mx.id} not found"
    assert_nw(before, nw_snapshot(db))


@pytest.mark.xfail(strict=True, reason=BUG_822)
def test_toi_in_27__soft_deleted_machine_rejected(db, w1, st, u1, i1, md, m2):
    """TOI-IN-27 — a soft-deleted machine should be rejected like a missing one.
    Rules: _post_location_in R8 [BUG-822]."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_machine_stock(db, w1, md, i1, qty=10)
    with pytest.raises(HTTPException) as exc:
        call_in(db, w1, u1, to, line, location_type="machine", location_id=md.id,
                qty=1, unit_cost=Decimal("1.00"), item_id=i1.id, source_id=m2.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Machine with ID {md.id} not found"
    mi = get_machine_item(db, w1, md, i1)
    assert mi.qty == 10
    assert last_machine_ledger_for_line(db, line) == []
    assert events_for_machine(db, md) == []


def test_toi_in_28__unknown_item_label_fallback(db, w1, st, u1, i1, m1, ix, m2):
    """TOI-IN-28 — an item not found in this workspace falls back to "Item #{id}"
    in the activity event.
    Rules: _post_location_in R11."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    result = call_in(db, w1, u1, to, line, location_type="machine", location_id=m1.id,
                      qty=2, unit_cost=Decimal("1.00"), item_id=ix.id, source_id=m2.id)
    assert result is None
    events = events_for_machine(db, m1)
    assert len(events) == 1
    assert events[0].description == f"Transfer in: 2 units of Item #{ix.id} (TR-2026-004)"
    assert events[0].metadata_json == {
        "item_id": ix.id, "item_name": f"Item #{ix.id}", "quantity": 2,
    }


# ---- schema cases for destination_location_type (R2a [BUG-823]) ---- #

_VALID_CREATE_KW = dict(source_location_type="storage", source_location_id=1,
                        destination_location_id=1)


@pytest.mark.parametrize("value", ["storage", "damaged", "machine", "project"])
def test_toi_in_29__create_destination_type_valid_values(db, value):
    """TOI-IN-29 — TransferOrderCreate accepts each known destination_location_type.
    Rules: _post_location_in R2a."""
    data = TransferOrderCreate(destination_location_type=value, **_VALID_CREATE_KW)
    assert data.destination_location_type == value


@pytest.mark.xfail(strict=True, reason=BUG_823)
def test_toi_in_30__create_destination_type_miscased_accepted(db):
    """TOI-IN-30 — TransferOrderCreate should reject 'Storage' as destination type.
    Rules: _post_location_in R2a [BUG-823]."""
    with pytest.raises(ValidationError) as exc:
        TransferOrderCreate(destination_location_type="Storage", **_VALID_CREATE_KW)
    assert any(e["loc"] == ("destination_location_type",) for e in exc.value.errors())


@pytest.mark.xfail(strict=True, reason=BUG_823)
def test_toi_in_31__create_destination_type_unknown_accepted(db):
    """TOI-IN-31 — TransferOrderCreate should reject 'warehouse' as destination type.
    Rules: _post_location_in R2a [BUG-823]."""
    with pytest.raises(ValidationError) as exc:
        TransferOrderCreate(destination_location_type="warehouse", **_VALID_CREATE_KW)
    assert any(e["loc"] == ("destination_location_type",) for e in exc.value.errors())


@pytest.mark.xfail(strict=True, reason=BUG_823)
def test_toi_in_32__create_destination_type_empty_accepted(db):
    """TOI-IN-32 — TransferOrderCreate should reject '' as destination type.
    Rules: _post_location_in R2a [BUG-823]."""
    with pytest.raises(ValidationError) as exc:
        TransferOrderCreate(destination_location_type="", **_VALID_CREATE_KW)
    assert any(e["loc"] == ("destination_location_type",) for e in exc.value.errors())


def test_toi_in_33__update_destination_type_valid(db):
    """TOI-IN-33 — TransferOrderUpdate(destination_location_type='damaged') builds.
    Rules: _post_location_in R2a."""
    data = TransferOrderUpdate(destination_location_type="damaged")
    assert data.destination_location_type == "damaged"


@pytest.mark.xfail(strict=True, reason=BUG_823)
def test_toi_in_34__update_destination_type_miscased_accepted(db):
    """TOI-IN-34 — TransferOrderUpdate should reject 'Storage' as destination type.
    Rules: _post_location_in R2a [BUG-823]."""
    with pytest.raises(ValidationError) as exc:
        TransferOrderUpdate(destination_location_type="Storage")
    assert any(e["loc"] == ("destination_location_type",) for e in exc.value.errors())


# ---- schema cases for source_location_type (_post_location_out R1a [BUG-823]) ---- #

_VALID_CREATE_KW_DEST = dict(destination_location_type="storage", destination_location_id=1,
                             source_location_id=1)


@pytest.mark.parametrize("value", ["storage", "damaged", "machine"])
def test_toi_in_35__create_source_type_valid_values(db, value):
    """TOI-IN-35 — TransferOrderCreate accepts each known source_location_type.
    Rules: _post_location_out R1a."""
    data = TransferOrderCreate(source_location_type=value, **_VALID_CREATE_KW_DEST)
    assert data.source_location_type == value


@pytest.mark.xfail(strict=True, reason=BUG_823)
def test_toi_in_36__create_source_type_project_accepted(db):
    """TOI-IN-36 — TransferOrderCreate should reject 'project' as source type.
    Rules: _post_location_out R1a [BUG-823]."""
    with pytest.raises(ValidationError) as exc:
        TransferOrderCreate(source_location_type="project", **_VALID_CREATE_KW_DEST)
    assert any(e["loc"] == ("source_location_type",) for e in exc.value.errors())


@pytest.mark.xfail(strict=True, reason=BUG_823)
def test_toi_in_37__create_source_type_miscased_accepted(db):
    """TOI-IN-37 — TransferOrderCreate should reject 'Storage' as source type.
    Rules: _post_location_out R1a [BUG-823]."""
    with pytest.raises(ValidationError) as exc:
        TransferOrderCreate(source_location_type="Storage", **_VALID_CREATE_KW_DEST)
    assert any(e["loc"] == ("source_location_type",) for e in exc.value.errors())


@pytest.mark.xfail(strict=True, reason=BUG_823)
def test_toi_in_38__update_source_type_unknown_accepted(db):
    """TOI-IN-38 — TransferOrderUpdate should reject 'warehouse' as source type.
    Rules: _post_location_out R1a [BUG-823]."""
    with pytest.raises(ValidationError) as exc:
        TransferOrderUpdate(source_location_type="warehouse")
    assert any(e["loc"] == ("source_location_type",) for e in exc.value.errors())


@pytest.mark.xfail(strict=True, reason=BUG_1040)
def test_toi_in_39__three_decimal_cost_rounds_half_up(db, w1, st, u1, i2, f1, m2):
    """TOI-IN-39 — total_cost rounds half away from zero, like the stored unit_cost/avg.
    Rules: _post_location_in R5, R6, R6a [BUG-1040] (G2 rounding)."""
    to, line = mk_to_line(db, w1, st, u1, i2)
    result = call_in(db, w1, u1, to, line, location_type="storage", location_id=f1.id,
                      qty=1, unit_cost=Decimal("0.125"), item_id=i2.id, source_id=m2.id)
    assert result is None
    rows = last_inv_ledger_for_line(db, line)
    assert len(rows) == 1
    assert_fields(
        rows[0], unit_cost=Decimal("0.13"),
        avg_price_before=None, avg_price_after=Decimal("0.13"), qty_after=1,
    )
    bucket = get_bucket(db, w1, f1, i2, STORAGE)
    assert_fields(bucket, qty=1, avg_price=Decimal("0.13"))
    assert_fields(rows[0], total_cost=Decimal("0.13"))


def test_toi_in_40__machine_null_average_weighted_with_zero(db, w1, st, u1, i1, m1, m2):
    """TOI-IN-40 — a null latest machine average is treated as 0 in the weighted average
    (not the unit cost, not an average of the two).
    Rules: _post_location_in R9, R10."""
    to, line = mk_to_line(db, w1, st, u1, i1)
    seed_machine_stock(db, w1, m1, i1, qty=3)
    seed_machine_ledger(db, w1, m1, i1, u1, qty_after=3, avg_price_after=Decimal("7.00"),
                        performed_at=PAST)
    seed_machine_ledger(db, w1, m1, i1, u1, qty_after=3, avg_price_after=None, performed_at=NEWER)
    result = call_in(db, w1, u1, to, line, location_type="machine", location_id=m1.id,
                      qty=1, unit_cost=Decimal("4.00"), item_id=i1.id, source_id=m2.id)
    assert result is None
    rows = last_machine_ledger_for_line(db, line)
    assert_fields(
        rows[0], avg_price_before=0, avg_price_after=Decimal("1.00"), value_before=0,
        value_after=Decimal("4.00"), qty_before=3, qty_after=4, total_cost=Decimal("4.00"),
    )
    mi = get_machine_item(db, w1, m1, i1)
    assert mi.qty == 4


def test_toi_in_41__update_source_type_omitted_none_or_value(db):
    """TOI-IN-41 — TransferOrderUpdate() / (source_location_type=None) / ('machine')
    all build without error.
    Rules: _post_location_out R1a."""
    a = TransferOrderUpdate()
    b = TransferOrderUpdate(source_location_type=None)
    c = TransferOrderUpdate(source_location_type="machine")
    assert a.source_location_type is None
    assert b.source_location_type is None
    assert c.source_location_type == "machine"


@pytest.mark.xfail(strict=True, reason=BUG_823)
def test_toi_in_42__create_source_type_empty_accepted(db):
    """TOI-IN-42 — TransferOrderCreate should reject '' as source type.
    Rules: _post_location_out R1a [BUG-823]."""
    with pytest.raises(ValidationError) as exc:
        TransferOrderCreate(source_location_type="", **_VALID_CREATE_KW_DEST)
    assert any(e["loc"] == ("source_location_type",) for e in exc.value.errors())


# =========================================================================== #
# post_transfer_order_inventory
# =========================================================================== #

def test_toi_p_01__empty_items_returns_zero(db, w1, st, u1, i1, f1, m1):
    """TOI-P-01 — items=[] returns 0; nothing written.
    Rules: post_transfer_order_inventory R1."""
    seed_stock(db, w1, f1, i1, STORAGE, u1, qty=10, avg_price=Decimal("4.00"))
    to = mk_order(db, w1, st, u1, source_type="storage", source_id=f1.id,
                  dest_type="machine", dest_id=m1.id)
    before = nw_snapshot(db)
    result = post_transfer_order_inventory(db, to, [], w1.id, u1.id)
    assert result == 0
    assert_nw(before, nw_snapshot(db))


def test_toi_p_02__single_line_storage_to_machine(db, w1, st, u1, i1, f1, m1):
    """TOI-P-02 — one line, default storage -> machine: both ledger rows, one event,
    no transfer_order_events row.
    Rules: post_transfer_order_inventory R3, R7, R9."""
    to = mk_order(db, w1, st, u1, source_type="storage", source_id=f1.id,
                  dest_type="machine", dest_id=m1.id)
    l1 = mk_line(db, to, i1, "3.00", 1)
    seed_stock(db, w1, f1, i1, STORAGE, u1, qty=10, avg_price=Decimal("4.00"))
    before_events = to_event_count(db, to)
    result = post_transfer_order_inventory(db, to, [l1], w1.id, u1.id)
    assert result == 1
    out_rows = last_inv_ledger_for_line(db, l1)
    assert len(out_rows) == 1
    assert_fields(out_rows[0], transaction_type="transfer_out", inventory_type=STORAGE,
                  factory_id=f1.id, quantity=3, unit_cost=Decimal("4.00"),
                  transfer_destination_type="machine", transfer_destination_id=m1.id)
    in_rows = last_machine_ledger_for_line(db, l1)
    assert len(in_rows) == 1
    assert_fields(in_rows[0], transaction_type="transfer_in", machine_id=m1.id, quantity=3,
                  unit_cost=Decimal("4.00"), avg_price_after=Decimal("4.00"),
                  transfer_source_type="storage", transfer_source_id=f1.id)
    bucket = get_bucket(db, w1, f1, i1, STORAGE)
    assert bucket.qty == 7
    mi = get_machine_item(db, w1, m1, i1)
    assert mi.qty == 3
    in_events = events_for_machine(db, m1, "transfer_in")
    out_events = events_for_machine(db, m1, "transfer_out")
    assert len(in_events) == 1
    assert out_events == []
    assert to_event_count(db, to) == before_events


def test_toi_p_03__single_line_machine_to_storage(db, w1, st, u1, i1, m1, f2):
    """TOI-P-03 — one line, machine -> storage: cost and avg flow correctly.
    Rules: post_transfer_order_inventory R3, R9."""
    to = mk_order(db, w1, st, u1, source_type="machine", source_id=m1.id,
                  dest_type="storage", dest_id=f2.id)
    l1 = mk_line(db, to, i1, "4.00", 1)
    seed_machine_stock(db, w1, m1, i1, qty=10)
    seed_machine_ledger(db, w1, m1, i1, u1, qty_after=10, avg_price_after=Decimal("6.00"),
                        performed_at=NEWER)
    seed_stock(db, w1, f2, i1, STORAGE, u1, qty=2, avg_price=Decimal("3.00"))
    result = post_transfer_order_inventory(db, to, [l1], w1.id, u1.id)
    assert result == 1
    out_rows = last_machine_ledger_for_line(db, l1)
    assert_fields(out_rows[0], transaction_type="transfer_out", unit_cost=Decimal("6.00"),
                  transfer_destination_type="storage", transfer_destination_id=f2.id)
    in_rows = last_inv_ledger_for_line(db, l1)
    assert_fields(in_rows[0], inventory_type=STORAGE, transaction_type="transfer_in",
                  factory_id=f2.id, unit_cost=Decimal("6.00"), qty_before=2, qty_after=6,
                  avg_price_after=Decimal("5.00"), transfer_source_type="machine",
                  transfer_source_id=m1.id)
    mi = get_machine_item(db, w1, m1, i1)
    assert mi.qty == 6
    bucket = get_bucket(db, w1, f2, i1, STORAGE)
    assert_fields(bucket, qty=6, avg_price=Decimal("5.00"))
    out_events = events_for_machine(db, m1, "transfer_out")
    assert len(out_events) == 1


def test_toi_p_04__null_source_average_costs_zero(db, w1, st, u1, i1, f1, f2):
    """TOI-P-04 — a null-average source bucket costs the transfer at 0.
    Rules: post_transfer_order_inventory R9."""
    to = mk_order(db, w1, st, u1, source_type="storage", source_id=f1.id,
                  dest_type="storage", dest_id=f2.id)
    l1 = mk_line(db, to, i1, "5.00", 1)
    seed_stock(db, w1, f1, i1, STORAGE, u1, qty=5, avg_price=None)
    seed_stock(db, w1, f2, i1, STORAGE, u1, qty=5, avg_price=Decimal("4.00"))
    result = post_transfer_order_inventory(db, to, [l1], w1.id, u1.id)
    assert result == 1
    in_rows = last_inv_ledger_for_line(db, l1)
    f2_row = next(r for r in in_rows if r.factory_id == f2.id)
    assert_fields(f2_row, transaction_type="transfer_in", unit_cost=0,
                  avg_price_after=Decimal("2.00"))
    bucket = get_bucket(db, w1, f2, i1, STORAGE)
    assert_fields(bucket, qty=10, avg_price=Decimal("2.00"))
    f1_bucket = get_bucket(db, w1, f1, i1, STORAGE)
    assert f1_bucket.qty == 0


def test_toi_p_05__machine_to_damaged_no_prior_rows(db, w1, st, u1, i1, m1, f2):
    """TOI-P-05 — machine (no ledger) -> a fresh damaged bucket: both cost at 0.
    Rules: post_transfer_order_inventory R9."""
    to = mk_order(db, w1, st, u1, source_type="machine", source_id=m1.id,
                  dest_type="damaged", dest_id=f2.id)
    l1 = mk_line(db, to, i1, "5.00", 1)
    seed_machine_stock(db, w1, m1, i1, qty=5)
    result = post_transfer_order_inventory(db, to, [l1], w1.id, u1.id)
    assert result == 1
    in_rows = last_inv_ledger_for_line(db, l1)
    assert_fields(in_rows[0], inventory_type=DAMAGED, transaction_type="transfer_in",
                  factory_id=f2.id, unit_cost=0, avg_price_after=0)
    bucket = get_bucket(db, w1, f2, i1, DAMAGED)
    assert_fields(bucket, qty=5, avg_price=0)
    mi = get_machine_item(db, w1, m1, i1)
    assert mi.qty == 0


def test_toi_p_06__damaged_to_storage_same_factory(db, w1, st, u1, i1, f1):
    """TOI-P-06 — damaged -> storage within the same factory.
    Rules: post_transfer_order_inventory R3."""
    to = mk_order(db, w1, st, u1, source_type="damaged", source_id=f1.id,
                  dest_type="storage", dest_id=f1.id)
    l1 = mk_line(db, to, i1, "2.00", 1)
    seed_stock(db, w1, f1, i1, DAMAGED, u1, qty=6, avg_price=Decimal("2.50"))
    seed_stock(db, w1, f1, i1, STORAGE, u1, qty=4, avg_price=Decimal("5.00"))
    result = post_transfer_order_inventory(db, to, [l1], w1.id, u1.id)
    assert result == 1
    rows = last_inv_ledger_for_line(db, l1)
    out_row = next(r for r in rows if r.transaction_type == "transfer_out")
    in_row = next(r for r in rows if r.transaction_type == "transfer_in")
    assert_fields(out_row, inventory_type=DAMAGED, unit_cost=Decimal("2.50"),
                  transfer_destination_type="storage", transfer_destination_id=f1.id)
    assert_fields(in_row, inventory_type=STORAGE, unit_cost=Decimal("2.50"),
                  avg_price_after=Decimal("4.17"), transfer_source_type="damaged",
                  transfer_source_id=f1.id)
    damaged = get_bucket(db, w1, f1, i1, DAMAGED)
    assert_fields(damaged, qty=4, avg_price=Decimal("2.50"))
    storage = get_bucket(db, w1, f1, i1, STORAGE)
    assert_fields(storage, qty=6, avg_price=Decimal("4.17"))
    assert last_machine_ledger_for_line(db, l1) == []
    assert db.scalar(select(func.count()).select_from(MachineActivityEvent)) == 0


def test_toi_p_07__already_posted_line_skipped(db, w1, st, u1, i1, i2, f1, m1):
    """TOI-P-07 — a pre-posted line is skipped entirely; the others post normally.
    Rules: post_transfer_order_inventory R2, R7."""
    to = mk_order(db, w1, st, u1, source_type="storage", source_id=f1.id,
                  dest_type="machine", dest_id=m1.id)
    l1 = mk_line(db, to, i1, "1.00", 1)
    l2 = mk_line(db, to, i2, "2.00", 2)
    l3 = mk_line(db, to, i1, "3.00", 3)
    seed_stock(db, w1, f1, i1, STORAGE, u1, qty=10, avg_price=Decimal("4.00"))
    seed_stock(db, w1, f1, i2, STORAGE, u1, qty=10, avg_price=Decimal("1.00"))
    db.add(InventoryLedger(
        workspace_id=w1.id, inventory_type=STORAGE, factory_id=f1.id, item_id=i2.id,
        transaction_type="transfer_out", quantity=2, qty_before=10, qty_after=12,
        avg_price_before=Decimal("1.00"), avg_price_after=Decimal("1.00"),
        source_type="transfer_order", source_id=l2.id, performed_by=u1.id,
        performed_at=OLDER,
    ))
    db.flush()
    result = post_transfer_order_inventory(db, to, [l1, l2, l3], w1.id, u1.id)
    assert result == 2
    for line in (l1, l3):
        out_rows = last_inv_ledger_for_line(db, line)
        in_rows = last_machine_ledger_for_line(db, line)
        assert len(out_rows) == 1
        assert len(in_rows) == 1
        assert out_rows[0].transaction_type == "transfer_out"
        assert in_rows[0].transaction_type == "transfer_in"
    l2_rows = last_inv_ledger_for_line(db, l2)
    assert len(l2_rows) == 1
    assert last_machine_ledger_for_line(db, l2) == []
    bucket_i1 = get_bucket(db, w1, f1, i1, STORAGE)
    assert bucket_i1.qty == 6
    bucket_i2 = get_bucket(db, w1, f1, i2, STORAGE)
    assert_fields(bucket_i2, qty=10, avg_price=Decimal("1.00"))
    mi1 = get_machine_item(db, w1, m1, i1)
    assert mi1.qty == 4
    assert get_machine_item(db, w1, m1, i2) is None


def test_toi_p_08__already_posted_fractional_line_skipped_without_validation(db, w1, st, u1, i1, f1, m1):
    """TOI-P-08 — a fractional-quantity line that is already posted is skipped
    without its quantity ever being validated.
    Rules: post_transfer_order_inventory R2, R4."""
    to = mk_order(db, w1, st, u1, source_type="storage", source_id=f1.id,
                  dest_type="machine", dest_id=m1.id)
    l1 = mk_line(db, to, i1, "2.50", 1)
    db.add(MachineItemLedger(
        workspace_id=w1.id, machine_id=m1.id, item_id=i1.id, transaction_type="transfer_in",
        quantity=1, unit_cost=Decimal(0), total_cost=Decimal(0), qty_before=0, qty_after=0,
        source_type="transfer_order", source_id=l1.id, performed_by=u1.id,
    ))
    db.flush()
    seed_stock(db, w1, f1, i1, STORAGE, u1, qty=10, avg_price=Decimal("4.00"))
    before = nw_snapshot(db)
    result = post_transfer_order_inventory(db, to, [l1], w1.id, u1.id)
    assert result == 0
    # (NW except for the pre-existing machine ledger row, which was there beforehand.)
    assert_nw(before, nw_snapshot(db))


def test_toi_p_09__fractional_quantity_raises(db, w1, st, u1, i1, f1, m1):
    """TOI-P-09 — a fractional line quantity raises 400; nothing written.
    Rules: post_transfer_order_inventory R4."""
    to = mk_order(db, w1, st, u1, source_type="storage", source_id=f1.id,
                  dest_type="machine", dest_id=m1.id)
    l1 = mk_line(db, to, i1, "2.50", 2)
    seed_stock(db, w1, f1, i1, STORAGE, u1, qty=10, avg_price=Decimal("4.00"))
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        post_transfer_order_inventory(db, to, [l1], w1.id, u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == (
        "Line 2 has a fractional quantity; inventory transfers require whole units"
    )
    assert_nw(before, nw_snapshot(db))


def test_toi_p_10__zero_quantity_raises(db, w1, st, u1, i1, f1, m1):
    """TOI-P-10 — a zero line quantity raises 400; nothing written.
    Rules: post_transfer_order_inventory R4."""
    to = mk_order(db, w1, st, u1, source_type="storage", source_id=f1.id,
                  dest_type="machine", dest_id=m1.id)
    l1 = mk_line(db, to, i1, "0.00", 1)
    seed_stock(db, w1, f1, i1, STORAGE, u1, qty=10, avg_price=Decimal("4.00"))
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        post_transfer_order_inventory(db, to, [l1], w1.id, u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Line 1 has no quantity to transfer"
    assert_nw(before, nw_snapshot(db))


def test_toi_p_11__second_line_fails_first_line_stays_written(db, w1, st, u1, i1, f1, m1):
    """TOI-P-11 — a later line's quantity error stops processing but leaves the
    earlier line's writes in place.
    Rules: post_transfer_order_inventory R5."""
    to = mk_order(db, w1, st, u1, source_type="storage", source_id=f1.id,
                  dest_type="machine", dest_id=m1.id)
    l1 = mk_line(db, to, i1, "3.00", 1)
    l2 = mk_line(db, to, i1, "2.50", 2)
    l3 = mk_line(db, to, i1, "1.00", 3)
    seed_stock(db, w1, f1, i1, STORAGE, u1, qty=10, avg_price=Decimal("4.00"))
    with pytest.raises(HTTPException) as exc:
        post_transfer_order_inventory(db, to, [l1, l2, l3], w1.id, u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == (
        "Line 2 has a fractional quantity; inventory transfers require whole units"
    )
    l1_out = last_inv_ledger_for_line(db, l1)
    l1_in = last_machine_ledger_for_line(db, l1)
    assert len(l1_out) == 1
    assert len(l1_in) == 1
    assert l1_out[0].transaction_type == "transfer_out"
    assert l1_in[0].transaction_type == "transfer_in"
    assert last_inv_ledger_for_line(db, l2) == []
    assert last_machine_ledger_for_line(db, l2) == []
    assert last_inv_ledger_for_line(db, l3) == []
    assert last_machine_ledger_for_line(db, l3) == []
    bucket = get_bucket(db, w1, f1, i1, STORAGE)
    assert bucket.qty == 7
    mi = get_machine_item(db, w1, m1, i1)
    assert mi.qty == 3


def test_toi_p_12__shortage_on_second_line_stops_processing(db, w1, st, u1, i1, i2, f1, m1):
    """TOI-P-12 — a shortage on a later line stops processing but leaves the
    earlier line's writes in place.
    Rules: post_transfer_order_inventory R5."""
    to = mk_order(db, w1, st, u1, source_type="storage", source_id=f1.id,
                  dest_type="machine", dest_id=m1.id)
    l1 = mk_line(db, to, i1, "3.00", 1)
    l2 = mk_line(db, to, i2, "20.00", 2)
    l3 = mk_line(db, to, i1, "1.00", 3)
    seed_stock(db, w1, f1, i1, STORAGE, u1, qty=10, avg_price=Decimal("4.00"))
    seed_stock(db, w1, f1, i2, STORAGE, u1, qty=5, avg_price=Decimal("1.00"))
    with pytest.raises(HTTPException) as exc:
        post_transfer_order_inventory(db, to, [l1, l2, l3], w1.id, u1.id)
    assert exc.value.status_code == 400
    assert "stock (5 available, 20 requested)" in exc.value.detail
    l1_out = last_inv_ledger_for_line(db, l1)
    l1_in = last_machine_ledger_for_line(db, l1)
    assert len(l1_out) == 1
    assert len(l1_in) == 1
    assert l1_out[0].transaction_type == "transfer_out"
    assert l1_in[0].transaction_type == "transfer_in"
    assert last_inv_ledger_for_line(db, l2) == []
    assert last_machine_ledger_for_line(db, l2) == []
    assert last_inv_ledger_for_line(db, l3) == []
    assert last_machine_ledger_for_line(db, l3) == []
    bucket_i1 = get_bucket(db, w1, f1, i1, STORAGE)
    assert bucket_i1.qty == 7
    bucket_i2 = get_bucket(db, w1, f1, i2, STORAGE)
    assert bucket_i2.qty == 5


def test_toi_p_13__project_destination_leaves_source_deduction_written(db, w1, st, u1, i1, f1):
    """TOI-P-13 — a project destination fails after the source side is already flushed.
    Rules: post_transfer_order_inventory R6."""
    to = mk_order(db, w1, st, u1, source_type="storage", source_id=f1.id,
                  dest_type="project", dest_id=0)
    l1 = mk_line(db, to, i1, "3.00", 1)
    seed_stock(db, w1, f1, i1, STORAGE, u1, qty=10, avg_price=Decimal("4.00"))
    with pytest.raises(HTTPException) as exc:
        post_transfer_order_inventory(db, to, [l1], w1.id, u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Project destination inventory posting is not yet supported"
    out_rows = last_inv_ledger_for_line(db, l1)
    assert len(out_rows) == 1
    assert out_rows[0].transaction_type == "transfer_out"
    assert out_rows[0].transfer_destination_type == "project"
    bucket = get_bucket(db, w1, f1, i1, STORAGE)
    assert bucket.qty == 7
    assert last_machine_ledger_for_line(db, l1) == []


def test_toi_p_14__missing_destination_factory_leaves_source_deduction_written(db, w1, st, u1, i1, f1):
    """TOI-P-14 — a missing destination factory fails after the source side is flushed.
    Rules: post_transfer_order_inventory R6."""
    to = mk_order(db, w1, st, u1, source_type="storage", source_id=f1.id,
                  dest_type="storage", dest_id=999999999)
    l1 = mk_line(db, to, i1, "3.00", 1)
    seed_stock(db, w1, f1, i1, STORAGE, u1, qty=10, avg_price=Decimal("4.00"))
    with pytest.raises(HTTPException) as exc:
        post_transfer_order_inventory(db, to, [l1], w1.id, u1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Factory with ID 999999999 not found"
    out_rows = last_inv_ledger_for_line(db, l1)
    assert len(out_rows) == 1
    assert out_rows[0].transaction_type == "transfer_out"
    bucket = get_bucket(db, w1, f1, i1, STORAGE)
    assert bucket.qty == 7
    assert last_machine_ledger_for_line(db, l1) == []


def test_toi_p_15__workspace_id_argument_scopes_writes_not_to_workspace_id(db, w1, w2, u1, u2, i1, f1, m1):
    """TOI-P-15 — a TO belonging to W2 still writes under the passed workspace_id (W1).
    Rules: post_transfer_order_inventory R8."""
    st2 = mk_status(db, w2)
    to = mk_order(db, w2, st2, u2, source_type="storage", source_id=f1.id,
                  dest_type="machine", dest_id=m1.id)
    l1 = mk_line(db, to, i1, "3.00", 1)
    seed_stock(db, w1, f1, i1, STORAGE, u1, qty=10, avg_price=Decimal("4.00"))
    result = post_transfer_order_inventory(db, to, [l1], w1.id, u1.id)
    assert result == 1
    out_rows = last_inv_ledger_for_line(db, l1)
    in_rows = last_machine_ledger_for_line(db, l1)
    assert out_rows[0].workspace_id == w1.id
    assert in_rows[0].workspace_id == w1.id
    events = events_for_machine(db, m1)
    assert len(events) == 1
    assert events[0].workspace_id == w1.id
    bucket = get_bucket(db, w1, f1, i1, STORAGE)
    assert bucket.qty == 7
    mi = get_machine_item(db, w1, m1, i1)
    assert mi.qty == 3


def test_toi_p_16__wrong_workspace_id_argument_factory_not_found(db, w1, w2, u2, i1, f1, m1):
    """TOI-P-16 — calling with the wrong workspace_id can't see W1's factory -> 404; NW.
    Rules: post_transfer_order_inventory R8."""
    to = mk_order(db, w1, mk_status(db, w1), u2, source_type="storage", source_id=f1.id,
                  dest_type="machine", dest_id=m1.id)
    l1 = mk_line(db, to, i1, "3.00", 1)
    seed_stock(db, w1, f1, i1, STORAGE, u2, qty=10, avg_price=Decimal("4.00"))
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        post_transfer_order_inventory(db, to, [l1], w2.id, u2.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Factory with ID {f1.id} not found"
    assert_nw(before, nw_snapshot(db))


def test_toi_p_17__unsupported_source_type_propagated(db, w1, st, u1, i1, f1, m1):
    """TOI-P-17 — an unsupported (miscased) source type on the order propagates
    _post_location_out's error.
    Rules: post_transfer_order_inventory R3 (errors propagated)."""
    to = mk_order(db, w1, st, u1, source_type="Storage", source_id=f1.id,
                  dest_type="machine", dest_id=m1.id)
    l1 = mk_line(db, to, i1, "3.00", 1)
    seed_stock(db, w1, f1, i1, STORAGE, u1, qty=10, avg_price=Decimal("4.00"))
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        post_transfer_order_inventory(db, to, [l1], w1.id, u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Unsupported source location type: Storage"
    assert_nw(before, nw_snapshot(db))
