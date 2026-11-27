"""Unit tests for app/managers/product_manager.py.

Implements tests/unit/managers/product_manager.cases.md (revision 3), one test
per case (the schema cards C-25 ... C-32 and U-28 ... U-35 are parametrized, one
param id per case). Real Postgres session (`db` fixture), rolled back after
each test. Nothing is mocked: the spec lists no externals. `performed_at`,
`created_at`, `updated_at` and `deleted_at` are database defaults and are only
checked as set / not set.

`make_sellable` does not exist yet (BUG-2793): every MS card is a strict xfail
that fails today at the call (AttributeError), written exactly as the card.
"""
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import event, func, or_, select

from app.core.exceptions import ValidationError as AppValidationError
from app.dao.product import product_dao
from app.managers.product_manager import _quantity_to_int, product_manager
from app.models.account import Account
from app.models.factory import Factory
from app.models.item import Item
from app.models.product import Product
from app.models.product_ledger import ProductLedger
from app.schemas.product import ProductCreate, ProductUpdate
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> module constants / fixtures / helpers
# --------------------------------------------------------------------------- #

# Convention "M": the singleton
M = product_manager

# Convention "MISSING", "T0"; sale-entry times "T1", "T2"
MISSING = 999999999
T0 = datetime(2026, 1, 15, 9, 0, 0)  # noqa: DTZ001
T1 = datetime(2026, 2, 1, 9, 0, 0)  # noqa: DTZ001
T2 = datetime(2026, 2, 2, 9, 0, 0)  # noqa: DTZ001

BUG_1011 = "BUG-1011: Product can be created for another workspace's item"
BUG_1040 = "BUG-1040: Money rounded half to even in Python, half away from zero in the database"
BUG_1336 = "BUG-1336: After a product row is soft-deleted, its key cannot be used again"
BUG_2770 = "BUG-2770: Finished-goods stock moves read the product row without a lock"
BUG_2771 = "BUG-2771: Editing a product with no change still stamps updated_by"
BUG_2772 = "BUG-2772: Opening a deleted product by id returns it"
BUG_2773 = "BUG-2773: A product of a deleted factory or removed item can still be opened"
BUG_2774 = "BUG-2774: A product holding stock can be deleted"
BUG_2775 = "BUG-2775: Negative quantity, cost, price and minimum order accepted"
BUG_2776 = "BUG-2776: Product cost and price with too many decimals or digits accepted"
BUG_2777 = "BUG-2777: Product edit cannot clear cost, price, minimum order or note"
BUG_2778 = "BUG-2778: Product average cost can change with no ledger row"
BUG_2779 = "BUG-2779: Zero product cost records ledger total_cost as empty"
BUG_2780 = "BUG-2780: Product can be created in a deleted factory or for a removed item"
BUG_2781 = "BUG-2781: A taken product bucket key reaches the database as a raw unique violation"
BUG_2782 = "BUG-2782: Insufficient-stock message names item and factory by internal id"
BUG_2783 = "BUG-2783: Customer-return ledger row is mislabelled"
BUG_2793 = "BUG-2793: Finished goods can become sellable only by flipping the whole product row"
BUG_2794 = "BUG-2794: Customer-returned goods carry no cost when the bucket has no average"
BUG_2811 = ("BUG-2811: A costed production output into a key with no row creates the bucket with its average "
            "already set, so the ledger's avg_cost_before equals the run cost")


def xfail(reason):
    return pytest.mark.xfail(strict=True, reason=reason)


# Convention "Standing rows": W0 < W1 < W2, U1, U2, factories, items, AC1; each flushed.
@pytest.fixture
def s(db):
    w0, w1, w2 = make_workspace(db), make_workspace(db), make_workspace(db)
    u1, u2 = make_profile(db), make_profile(db)

    def factory(ws, name, abbreviation, **extra):
        row = Factory(workspace_id=ws.id, name=name, abbreviation=abbreviation, **extra)
        db.add(row)
        db.flush()
        return row

    def item(ws, name, **extra):
        row = Item(workspace_id=ws.id, name=name, name_normalized=name.lower(), unit="pcs", **extra)
        db.add(row)
        db.flush()
        return row

    f0 = factory(w0, "Zero Plant", "Z0")
    f1 = factory(w1, "Factory One", "F1")
    f2 = factory(w1, "Factory Two", "F2")
    fd = factory(w1, "Old Plant", "OP", is_deleted=True, deleted_at=T0, deleted_by=u1.id)
    fi = factory(w1, "Idle Plant", "IP", is_active=False)
    f9 = factory(w2, "Far Plant", "F9")
    i0 = item(w0, "Zero Nut")
    i1 = item(w1, "Bolt")
    i2 = item(w1, "Cam")
    ix = item(w1, "Old Gasket", is_active=False)
    i9 = item(w2, "Far Crate")
    ac1 = Account(workspace_id=w1.id, name="Acme")
    db.add(ac1)
    db.flush()
    db.expire_all()
    return SimpleNamespace(
        W0=w0, W1=w1, W2=w2, U1=u1, U2=u2,
        F0=f0, F1=f1, F2=f2, FD=fd, FI=fi, F9=f9,
        I0=i0, I1=i1, I2=i2, IX=ix, I9=i9, AC1=ac1,
    )


# Convention "stock" (+ "for sale", "deleted", "of W0"/"of W2" via workspace_id=...)
def mk(db, s, *, for_sale=False, deleted=False, **overrides):
    fields = {
        "workspace_id": s.W1.id, "item_id": s.I1.id, "factory_id": s.F1.id,
        "qty": 5, "created_by": s.U1.id,
    }
    if for_sale:
        fields["is_available_for_sale"] = True
    if deleted:
        fields.update(is_active=False, is_deleted=True, deleted_at=T0, deleted_by=s.U1.id)
    fields.update(overrides)
    row = Product(**fields)
    db.add(row)
    db.flush()
    return row


# Convention "sale entry": unit_cost also goes into avg_cost_before / avg_cost_after
def mk_sale(db, s, *, performed_at, unit_cost, **overrides):
    fields = {
        "workspace_id": s.W1.id, "factory_id": s.F1.id, "item_id": s.I1.id,
        "transaction_type": "sale", "quantity": 1, "qty_before": 1, "qty_after": 0,
        "source_type": "sales_delivery", "source_id": 501, "performed_by": s.U1.id,
        "performed_at": performed_at, "unit_cost": unit_cost,
        "avg_cost_before": unit_cost, "avg_cost_after": unit_cost,
    }
    fields.update(overrides)
    row = ProductLedger(**fields)
    db.add(row)
    db.flush()
    return row


# Convention "re-read X": expire, then SELECT by id
def reread(db, row):
    model, row_id = type(row), row.id
    db.expire_all()
    return db.execute(select(model).where(model.id == row_id)).scalar_one_or_none()


# Convention "unchanged(X)": every column, read from the database
def snap(db, row):
    table, row_id = type(row).__table__, row.id
    db.expire_all()
    found = db.execute(select(table).where(table.c.id == row_id)).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "count:" lines: all workspaces, with the filter stated
def count(db, model, *conditions):
    return db.execute(select(func.count()).select_from(model).where(*conditions)).scalar_one()


# Convention "nothing written"
def counts(db):
    return {"products": count(db, Product), "product_ledger": count(db, ProductLedger)}


# Convention "ledger_of(F, I)": W1 rows of that factory and item, ordered by id
def ledger_of(db, s, factory, item):
    ws_id, factory_id, item_id = s.W1.id, factory.id, item.id
    db.expire_all()
    query = select(ProductLedger).where(
        ProductLedger.workspace_id == ws_id,
        ProductLedger.factory_id == factory_id,
        ProductLedger.item_id == item_id,
    ).order_by(ProductLedger.id)
    return list(db.execute(query).scalars())


# Convention "out" / "in" (make_sellable): the one ledger row with that transfer side
def out_row(db):
    db.expire_all()
    return db.execute(
        select(ProductLedger).where(ProductLedger.transfer_destination_type == "product")
    ).scalar_one()


def in_row(db):
    db.expire_all()
    return db.execute(
        select(ProductLedger).where(ProductLedger.transfer_source_type == "product")
    ).scalar_one()


# Convention "Statement recorder": before_cursor_execute on db.connection()
@contextmanager
def record(db):
    connection = db.connection()
    statements = []

    def _record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    rec = SimpleNamespace(selects=[], psel=[], written=[])
    event.listen(connection, "before_cursor_execute", _record)
    try:
        yield rec
    finally:
        event.remove(connection, "before_cursor_execute", _record)
        for text_ in statements:
            head = text_.lstrip().upper()
            if head.startswith("SELECT"):
                rec.selects.append(text_)
                if "FROM products" in text_:
                    rec.psel.append(text_)
            elif head.startswith(("INSERT", "UPDATE", "DELETE")):
                rec.written.append(text_)


# --------------------------------------------------------------------------- #
# _quantity_to_int
# --------------------------------------------------------------------------- #

def test_prdm_qi_01__whole_decimal_with_two_places_becomes_int(db, s):
    """PRDM-QI-01 — a whole Decimal with two places becomes an int.
    Rules: _quantity_to_int R1."""
    result = _quantity_to_int(Decimal("5.00"), label="Delivery line")

    # Then 1
    assert result == 5
    # Then 2
    assert type(result) is int


def test_prdm_qi_02__plain_int_returned_as_is(db, s):
    """PRDM-QI-02 — a plain int is returned as is.
    Rules: _quantity_to_int R1."""
    result = _quantity_to_int(7, label="Delivery line")

    # Then 1
    assert result == 7
    # Then 2
    assert type(result) is int


def test_prdm_qi_03__zero_returned_as_0(db, s):
    """PRDM-QI-03 — zero is returned as 0.
    Rules: _quantity_to_int R1."""
    result = _quantity_to_int(Decimal(0), label="Return line")

    # Then 1
    assert result == 0
    # Then 2
    assert type(result) is int


def test_prdm_qi_04__negative_whole_value_keeps_sign(db, s):
    """PRDM-QI-04 — a negative whole value keeps its sign.
    Rules: _quantity_to_int R1."""
    result = _quantity_to_int(Decimal(-3), label="Return line")

    # Then 1
    assert result == -3


def test_prdm_qi_05__one_whole_unit_is_1(db, s):
    """PRDM-QI-05 — one whole unit is 1.
    Rules: _quantity_to_int R1."""
    result = _quantity_to_int(Decimal("1.00"), label="Delivery line")

    # Then 1
    assert result == 1


def test_prdm_qi_06__half_unit_refused_with_label(db, s):
    """PRDM-QI-06 — a half unit is refused with the label in the message.
    Rules: _quantity_to_int R2, Errors row 1."""
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _quantity_to_int(Decimal("2.5"), label="Delivery line")
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Delivery line has a fractional quantity; stock requires whole units"


def test_prdm_qi_07__one_hundredth_refused_other_label(db, s):
    """PRDM-QI-07 — one hundredth is refused, with another label.
    Rules: _quantity_to_int R2."""
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _quantity_to_int(Decimal("0.01"), label="Return line")
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Return line has a fractional quantity; stock requires whole units"


def test_prdm_qi_08__just_under_whole_number_refused(db, s):
    """PRDM-QI-08 — just under a whole number is refused.
    Rules: _quantity_to_int R2."""
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _quantity_to_int(Decimal("4.99"), label="Delivery line")
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Delivery line has a fractional quantity; stock requires whole units"


# --------------------------------------------------------------------------- #
# create_product
# --------------------------------------------------------------------------- #

def test_prdm_c_01__create_stores_every_field_and_one_opening_row(db, s):
    """PRDM-C-01 — a create stores every field and one opening ledger row.
    Rules: create_product R6, R7."""
    result = M.create_product(db, data=ProductCreate(
        item_id=s.I1.id, factory_id=s.F1.id, qty=4, avg_cost=Decimal("12.50"),
        selling_price=Decimal("20.00"), min_order_qty=2, is_available_for_sale=True, note="First lot",
    ), workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert isinstance(result, Product)
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == s.W1.id
    assert row.item_id == s.I1.id
    assert row.factory_id == s.F1.id
    assert row.qty == 4
    # Then 3
    assert row.avg_cost == Decimal("12.50")
    assert row.selling_price == Decimal("20.00")
    assert row.min_order_qty == 2
    assert row.is_available_for_sale is True
    assert row.note == "First lot"
    # Then 4
    assert row.created_by == s.U2.id
    assert row.updated_by is None
    assert row.is_active is True
    assert row.is_deleted is False
    # Then 5
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 6
    assert e.transaction_type == "manual_add"
    assert e.quantity == 4
    assert e.qty_before == 0
    assert e.qty_after == 4
    # Then 7
    assert e.unit_cost == Decimal("12.50")
    assert e.total_cost == Decimal("50.00")
    assert e.avg_cost_before is None
    assert e.avg_cost_after == Decimal("12.50")
    # Then 8
    assert e.source_type == "manual"
    assert e.source_id is None
    assert e.transfer_source_type is None
    assert e.transfer_source_id is None
    assert e.transfer_destination_type is None
    assert e.transfer_destination_id is None
    # Then 9
    assert e.notes == "Initial product record created"
    assert e.performed_by == s.U2.id
    assert e.workspace_id == s.W1.id
    assert e.performed_at is not None


def test_prdm_c_02__only_item_and_factory_takes_defaults_no_ledger(db, s):
    """PRDM-C-02 — a create with only item and factory takes the defaults and writes no ledger row.
    Rules: create_product R6, R7a."""
    result = M.create_product(db, data=ProductCreate(item_id=s.I1.id, factory_id=s.F1.id),
                              workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.qty == 0
    assert row.avg_cost is None
    assert row.selling_price is None
    assert row.min_order_qty is None
    assert row.is_available_for_sale is False
    assert row.note is None
    # Then 3
    assert row.created_by == s.U2.id
    assert row.is_active is True
    assert row.is_deleted is False
    # Then 4
    assert count(db, ProductLedger) == 0


def test_prdm_c_03__one_unit_opens_with_ledger_row_of_1(db, s):
    """PRDM-C-03 — one unit opens with a ledger row of 1.
    Rules: create_product R7 (other side of qty > 0)."""
    result = M.create_product(db, data=ProductCreate(
        item_id=s.I1.id, factory_id=s.F1.id, qty=1, avg_cost=Decimal("3.25"),
    ), workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 3
    assert e.quantity == 1
    assert e.qty_before == 0
    assert e.qty_after == 1
    assert e.unit_cost == Decimal("3.25")
    assert e.total_cost == Decimal("3.25")


def test_prdm_c_04__no_cost_gives_ledger_row_with_empty_cost(db, s):
    """PRDM-C-04 — no cost gives a ledger row with empty cost fields.
    Rules: create_product R7 (avg_cost None -> total_cost NULL)."""
    result = M.create_product(db, data=ProductCreate(item_id=s.I1.id, factory_id=s.F1.id, qty=6),
                              workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 3
    assert e.quantity == 6
    assert e.qty_after == 6
    assert e.unit_cost is None
    assert e.total_cost is None
    assert e.avg_cost_before is None
    assert e.avg_cost_after is None


def test_prdm_c_05__zero_cost_opening_row_carries_zero_cost(db, s):
    """PRDM-C-05 — a zero cost: the opening row carries the zero cost.
    Rules: create_product R7 (parts that hold today; BUG-2779 is C-06)."""
    result = M.create_product(db, data=ProductCreate(
        item_id=s.I1.id, factory_id=s.F1.id, qty=5, avg_cost=Decimal("0.00"),
    ), workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.avg_cost == Decimal("0.00")
    assert row.qty == 5
    # Then 3
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 4
    assert e.quantity == 5
    assert e.unit_cost == Decimal("0.00")
    assert e.avg_cost_after == Decimal("0.00")


@xfail(BUG_2779)
def test_prdm_c_06__zero_cost_gives_ledger_total_0(db, s):
    """PRDM-C-06 — a zero cost gives a ledger total of 0.00.
    Rules: create_product R7 [BUG-2779]."""
    result = M.create_product(db, data=ProductCreate(
        item_id=s.I1.id, factory_id=s.F1.id, qty=5, avg_cost=Decimal("0.00"),
    ), workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 3
    assert e.total_cost == Decimal("0.00")


def test_prdm_c_07__qty_0_with_cost_row_keeps_cost(db, s):
    """PRDM-C-07 — quantity 0 with a cost: the row keeps the cost.
    Rules: create_product R6 (part that holds today; BUG-2778 is C-08)."""
    result = M.create_product(db, data=ProductCreate(
        item_id=s.I1.id, factory_id=s.F1.id, qty=0, avg_cost=Decimal("7.00"),
    ), workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.qty == 0
    assert row.avg_cost == Decimal("7.00")


@xfail(BUG_2778)
def test_prdm_c_08__qty_0_with_cost_writes_zero_quantity_manual_add(db, s):
    """PRDM-C-08 — quantity 0 with a cost writes a zero-quantity manual_add row.
    Rules: create_product R7a [BUG-2778]."""
    result = M.create_product(db, data=ProductCreate(
        item_id=s.I1.id, factory_id=s.F1.id, qty=0, avg_cost=Decimal("7.00"),
    ), workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 3
    assert e.transaction_type == "manual_add"
    assert e.quantity == 0
    assert e.qty_before == 0
    assert e.qty_after == 0
    # Then 4
    assert e.avg_cost_before is None
    assert e.avg_cost_after == Decimal("7.00")
    assert e.total_cost == Decimal("0.00")


def test_prdm_c_09__zero_everywhere_accepted(db, s):
    """PRDM-C-09 — zero everywhere is accepted.
    Rules: create_product R5 ("0 is accepted everywhere")."""
    result = M.create_product(db, data=ProductCreate(
        item_id=s.I1.id, factory_id=s.F1.id, qty=0, avg_cost=Decimal("0.00"),
        selling_price=Decimal("0.00"), min_order_qty=0,
    ), workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.qty == 0
    assert row.avg_cost == Decimal("0.00")
    assert row.selling_price == Decimal("0.00")
    assert row.min_order_qty == 0


def test_prdm_c_10__unknown_factory_not_found(db, s):
    """PRDM-C-10 — an unknown factory is not found.
    Rules: create_product R1, Errors row 1."""
    before = counts(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_product(db, data=ProductCreate(item_id=s.I1.id, factory_id=MISSING, qty=3),
                         workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory with ID 999999999 not found"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before


def test_prdm_c_11__factory_of_w0_not_found(db, s):
    """PRDM-C-11 — a factory of W0 (lower workspace id) is not found.
    Rules: create_product R1, Errors row 1; HR-16."""
    before = counts(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_product(db, data=ProductCreate(item_id=s.I1.id, factory_id=s.F0.id, qty=3),
                         workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory with ID {s.F0.id} not found"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before


def test_prdm_c_12__factory_of_w2_not_found(db, s):
    """PRDM-C-12 — a factory of W2 (higher workspace id) is not found.
    Rules: create_product R1, Errors row 1; HR-16."""
    before = counts(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_product(db, data=ProductCreate(item_id=s.I1.id, factory_id=s.F9.id, qty=3),
                         workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory with ID {s.F9.id} not found"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before


def test_prdm_c_13__inactive_but_live_factory_accepted(db, s):
    """PRDM-C-13 — an inactive but live factory is accepted.
    Rules: create_product R2 (inactive-but-live side)."""
    result = M.create_product(db, data=ProductCreate(item_id=s.I1.id, factory_id=s.FI.id, qty=2),
                              workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.factory_id == s.FI.id
    assert row.qty == 2
    # Then 3
    assert len(ledger_of(db, s, s.FI, s.I1)) == 1


@xfail(BUG_2780)
def test_prdm_c_14__soft_deleted_factory_not_found(db, s):
    """PRDM-C-14 — a soft-deleted factory is not found.
    Rules: create_product R2 [BUG-2780], Errors row 1."""
    before = counts(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_product(db, data=ProductCreate(item_id=s.I1.id, factory_id=s.FD.id, qty=3),
                         workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory with ID {s.FD.id} not found"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before


@xfail(BUG_2780)
def test_prdm_c_15__removed_item_not_found(db, s):
    """PRDM-C-15 — a removed item is not found.
    Rules: create_product R2a [BUG-2780], Errors row 2."""
    before = counts(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_product(db, data=ProductCreate(item_id=s.IX.id, factory_id=s.F1.id, qty=3),
                         workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Item with ID {s.IX.id} not found"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before


@xfail(BUG_1011)
def test_prdm_c_16__item_of_w0_not_found(db, s):
    """PRDM-C-16 — an item of W0 is not found.
    Rules: create_product R2a [BUG-1011], Errors row 2; HR-16."""
    before = counts(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_product(db, data=ProductCreate(item_id=s.I0.id, factory_id=s.F1.id, qty=3),
                         workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Item with ID {s.I0.id} not found"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before


@xfail(BUG_1011)
def test_prdm_c_17__item_of_w2_not_found(db, s):
    """PRDM-C-17 — an item of W2 is not found.
    Rules: create_product R2a [BUG-1011], Errors row 2; HR-16."""
    before = counts(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_product(db, data=ProductCreate(item_id=s.I9.id, factory_id=s.F1.id, qty=3),
                         workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Item with ID {s.I9.id} not found"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before


@xfail(BUG_1011)
def test_prdm_c_18__unknown_item_not_found(db, s):
    """PRDM-C-18 — an unknown item is not found.
    Rules: create_product R2a [BUG-1011], Errors row 2."""
    before = counts(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_product(db, data=ProductCreate(item_id=MISSING, factory_id=s.F1.id, qty=3),
                         workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Item with ID 999999999 not found"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before


def test_prdm_c_19__live_row_of_same_key_is_conflict(db, s):
    """PRDM-C-19 — a live row of the same key is a conflict.
    Rules: create_product R3, Errors row 3."""
    p = mk(db, s, for_sale=True, qty=9)
    db.expire_all()
    before = counts(db)
    before_p = snap(db, p)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_product(db, data=ProductCreate(
            item_id=s.I1.id, factory_id=s.F1.id, qty=3, is_available_for_sale=True,
        ), workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Product record already exists for this item/factory/availability combination"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before
    # Then 6
    assert snap(db, p) == before_p


def test_prdm_c_20__for_sale_row_does_not_block_not_for_sale_create(db, s):
    """PRDM-C-20 — a for-sale row does not block a not-for-sale create.
    Rules: create_product R3 (only the exact flag counts)."""
    p = mk(db, s, for_sale=True, qty=9)
    db.expire_all()
    before_p = snap(db, p)

    result = M.create_product(db, data=ProductCreate(item_id=s.I1.id, factory_id=s.F1.id, qty=3),
                              workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert result.id != p.id
    # Then 3
    row = reread(db, result)
    assert row.is_available_for_sale is False
    assert row.qty == 3
    # Then 4
    assert snap(db, p) == before_p


def test_prdm_c_21__rows_of_other_factory_or_item_do_not_block(db, s):
    """PRDM-C-21 — rows of another factory or another item do not block.
    Rules: create_product R3 (key = factory and item)."""
    pa = mk(db, s, factory_id=s.F2.id)
    pb = mk(db, s, item_id=s.I2.id)
    db.expire_all()
    before_pa = snap(db, pa)
    before_pb = snap(db, pb)

    result = M.create_product(db, data=ProductCreate(item_id=s.I1.id, factory_id=s.F1.id, qty=3),
                              workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert count(db, Product, Product.workspace_id == s.W1.id) == 3
    # Then 3
    assert snap(db, pa) == before_pa
    # Then 4
    assert snap(db, pb) == before_pb


def test_prdm_c_22__same_key_rows_of_w0_and_w2_do_not_block(db, s):
    """PRDM-C-22 — same-key rows of W0 and W2 do not block a W1 create.
    Rules: create_product R3 (workspace in the key); HR-16."""
    p0 = mk(db, s, workspace_id=s.W0.id)
    p9 = mk(db, s, workspace_id=s.W2.id)
    db.expire_all()
    before_p0 = snap(db, p0)
    before_p9 = snap(db, p9)

    result = M.create_product(db, data=ProductCreate(item_id=s.I1.id, factory_id=s.F1.id, qty=3),
                              workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == s.W1.id
    assert row.qty == 3
    # Then 3
    assert snap(db, p0) == before_p0
    # Then 4
    assert snap(db, p9) == before_p9
    # Then 5
    assert len(ledger_of(db, s, s.F1, s.I1)) == 1


@xfail(BUG_1336)
def test_prdm_c_23__soft_deleted_row_of_same_key_is_conflict(db, s):
    """PRDM-C-23 — a soft-deleted row of the same key is a conflict.
    Rules: create_product R4 [BUG-1336], Errors row 3."""
    mk(db, s, deleted=True, qty=0)
    db.expire_all()
    before = counts(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_product(db, data=ProductCreate(item_id=s.I1.id, factory_id=s.F1.id, qty=3),
                         workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Product record already exists for this item/factory/availability combination"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before


def test_prdm_c_24__create_flushed_not_committed(db, s):
    """PRDM-C-24 — the create is flushed but not committed.
    Rules: create_product Returns ("flushed, not committed"); Side effects."""
    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as spy:
        result = M.create_product(db, data=ProductCreate(item_id=s.I1.id, factory_id=s.F1.id, qty=4),
                                  workspace_id=s.W1.id, user_id=s.U2.id)

        # Then 1
        assert result.id is not None
        # Then 2
        assert count(db, Product) == 1
        # Then 3
        assert count(db, ProductLedger) == 1
        sp.rollback()
        # Then 4
        assert count(db, Product) == 0
        # Then 5
        assert count(db, ProductLedger) == 0
        # Then 6
        spy.assert_not_called()


@pytest.mark.parametrize("build", [
    pytest.param(lambda s: ProductCreate(item_id=s.I1.id, factory_id=s.F1.id, qty=-1),
                 id="PRDM-C-25", marks=xfail(BUG_2775)),
    pytest.param(lambda s: ProductCreate(item_id=s.I1.id, factory_id=s.F1.id, avg_cost=Decimal("-0.01")),
                 id="PRDM-C-26", marks=xfail(BUG_2775)),
    pytest.param(lambda s: ProductCreate(item_id=s.I1.id, factory_id=s.F1.id, selling_price=Decimal("-0.01")),
                 id="PRDM-C-27", marks=xfail(BUG_2775)),
    pytest.param(lambda s: ProductCreate(item_id=s.I1.id, factory_id=s.F1.id, min_order_qty=-1),
                 id="PRDM-C-28", marks=xfail(BUG_2775)),
    pytest.param(lambda s: ProductCreate(item_id=s.I1.id, factory_id=s.F1.id, qty=3, avg_cost=Decimal("10.005")),
                 id="PRDM-C-29", marks=xfail(BUG_2776)),
    pytest.param(lambda s: ProductCreate(item_id=s.I1.id, factory_id=s.F1.id, selling_price=Decimal("1.005")),
                 id="PRDM-C-30", marks=xfail(BUG_2776)),
    pytest.param(lambda s: ProductCreate(item_id=s.I1.id, factory_id=s.F1.id,
                                         avg_cost=Decimal("10000000000000.00")),
                 id="PRDM-C-31", marks=xfail(BUG_2776)),
    pytest.param(lambda s: ProductCreate(item_id=s.I1.id, factory_id=s.F1.id,
                                         selling_price=Decimal(10000000000000)),
                 id="PRDM-C-32", marks=xfail(BUG_2776)),
])
def test_prdm_c_25_to_32__create_schema_refuses_out_of_range(db, s, build):
    """PRDM-C-25 … PRDM-C-32 — the create schema refuses a negative or over-precise value.
    Rules: create_product R5 [BUG-2775, BUG-2776], Errors row 4."""
    # Then 1
    with pytest.raises(PydanticValidationError):
        build(s)


def test_prdm_c_33__largest_two_decimal_cost_and_price_pass_schema(db, s):
    """PRDM-C-33 — the largest two-decimal cost and price pass the schema.
    Rules: create_product R5 (other side of the 13-digit / 2-decimal limit)."""
    result = ProductCreate(item_id=s.I1.id, factory_id=s.F1.id,
                           avg_cost=Decimal("9999999999999.99"), selling_price=Decimal("0.01"))

    # Then 1
    assert result.avg_cost == Decimal("9999999999999.99")
    # Then 2
    assert result.selling_price == Decimal("0.01")


@xfail(BUG_2775)
def test_prdm_c_34__schema_checked_before_factory(db, s):
    """PRDM-C-34 — the schema is checked before the factory.
    Rules: create_product R0, R5 [BUG-2775]."""
    before = counts(db)

    # Then 1
    with pytest.raises(PydanticValidationError) as exc:
        ProductCreate(item_id=s.I1.id, factory_id=MISSING, qty=-1)
    # Then 2
    assert exc.value.errors()[0]["loc"] == ("qty",)
    # Then 3
    assert counts(db) == before


def test_prdm_c_35__unknown_factory_wins_over_removed_item(db, s):
    """PRDM-C-35 — an unknown factory wins over a removed item.
    Rules: create_product R0, R1."""
    before = counts(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_product(db, data=ProductCreate(item_id=s.IX.id, factory_id=MISSING, qty=3),
                         workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory with ID 999999999 not found"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before


@xfail(BUG_2780)
def test_prdm_c_36__soft_deleted_factory_wins_over_removed_item(db, s):
    """PRDM-C-36 — a soft-deleted factory wins over a removed item.
    Rules: create_product R0, R2 [BUG-2780]."""
    before = counts(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_product(db, data=ProductCreate(item_id=s.IX.id, factory_id=s.FD.id, qty=3),
                         workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory with ID {s.FD.id} not found"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before


@xfail(BUG_2780)
def test_prdm_c_37__removed_item_wins_over_taken_key(db, s):
    """PRDM-C-37 — a removed item wins over a taken key.
    Rules: create_product R0, R2a [BUG-2780]."""
    p = mk(db, s, item_id=s.IX.id, qty=2)
    db.expire_all()
    before = counts(db)
    before_p = snap(db, p)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_product(db, data=ProductCreate(item_id=s.IX.id, factory_id=s.F1.id, qty=3),
                         workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Item with ID {s.IX.id} not found"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before
    # Then 6
    assert snap(db, p) == before_p


@xfail(BUG_2780)
def test_prdm_c_38__soft_deleted_factory_wins_over_taken_key(db, s):
    """PRDM-C-38 — a soft-deleted factory wins over a taken key.
    Rules: create_product R0, R2 [BUG-2780]."""
    p = mk(db, s, factory_id=s.FD.id, qty=2)
    db.expire_all()
    before = counts(db)
    before_p = snap(db, p)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_product(db, data=ProductCreate(item_id=s.I1.id, factory_id=s.FD.id, qty=3),
                         workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory with ID {s.FD.id} not found"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before
    # Then 6
    assert snap(db, p) == before_p


# --------------------------------------------------------------------------- #
# update_product
# --------------------------------------------------------------------------- #

def test_prdm_u_01__unknown_id_not_found(db, s):
    """PRDM-U-01 — an unknown id is not found.
    Rules: update_product R1, Errors row 1."""
    p = mk(db, s)
    db.expire_all()
    before = counts(db)
    before_p = snap(db, p)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_product(db, prod_id=MISSING, data=ProductUpdate(note="x"), workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Product record with ID 999999999 not found"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before
    # Then 6
    assert snap(db, p) == before_p


def test_prdm_u_02__row_of_w0_not_found_from_w1(db, s):
    """PRDM-U-02 — a row of W0 (lower id) is not found from W1.
    Rules: update_product R1; HR-16."""
    p0 = mk(db, s, workspace_id=s.W0.id, factory_id=s.F0.id, item_id=s.I0.id)
    mk(db, s)
    db.expire_all()
    before = counts(db)
    before_p0 = snap(db, p0)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_product(db, prod_id=p0.id, data=ProductUpdate(qty=8), workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Product record with ID {p0.id} not found"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before
    # Then 6
    assert snap(db, p0) == before_p0


def test_prdm_u_03__row_of_w2_not_found_from_w1(db, s):
    """PRDM-U-03 — a row of W2 (higher id) is not found from W1.
    Rules: update_product R1; HR-16."""
    mk(db, s)
    p9 = mk(db, s, workspace_id=s.W2.id, factory_id=s.F9.id, item_id=s.I9.id)
    db.expire_all()
    before = counts(db)
    before_p9 = snap(db, p9)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_product(db, prod_id=p9.id, data=ProductUpdate(qty=8), workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Product record with ID {p9.id} not found"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before
    # Then 6
    assert snap(db, p9) == before_p9


def test_prdm_u_04__soft_deleted_row_cannot_be_updated(db, s):
    """PRDM-U-04 — a soft-deleted row cannot be updated.
    Rules: update_product R2, Errors row 2."""
    p = mk(db, s, deleted=True, qty=0)
    db.expire_all()
    before = counts(db)
    before_p = snap(db, p)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_product(db, prod_id=p.id, data=ProductUpdate(qty=8), workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update a deleted product record"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before
    # Then 6
    assert snap(db, p) == before_p


def test_prdm_u_05__soft_deleted_row_of_w2_is_not_found(db, s):
    """PRDM-U-05 — a soft-deleted row of W2 is "not found", not "deleted".
    Rules: update_product R1 before R2."""
    p9 = mk(db, s, workspace_id=s.W2.id, factory_id=s.F9.id, item_id=s.I9.id, deleted=True, qty=0)
    db.expire_all()
    before = counts(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_product(db, prod_id=p9.id, data=ProductUpdate(qty=8), workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Product record with ID {p9.id} not found"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before


def test_prdm_u_06__fields_other_than_qty_stored_and_stamped(db, s):
    """PRDM-U-06 — fields other than qty are stored and stamped, with no ledger row.
    Rules: update_product R5 (something changes), R6, R7 (no qty / cost change -> no row)."""
    p = mk(db, s, avg_cost=Decimal("10.00"), selling_price=Decimal("15.00"), min_order_qty=1, note="Old")
    db.expire_all()

    result = M.update_product(db, prod_id=p.id, data=ProductUpdate(
        selling_price=Decimal("18.00"), min_order_qty=3, note="New",
    ), workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    row = reread(db, p)
    assert row.selling_price == Decimal("18.00")
    assert row.min_order_qty == 3
    assert row.note == "New"
    # Then 3
    assert row.qty == 5
    assert row.avg_cost == Decimal("10.00")
    assert row.is_available_for_sale is False
    assert row.factory_id == s.F1.id
    assert row.item_id == s.I1.id
    # Then 4
    assert row.updated_by == s.U2.id
    assert row.created_by == s.U1.id
    # Then 5
    assert count(db, ProductLedger) == 0


def test_prdm_u_07__omitted_fields_left_as_they_are(db, s):
    """PRDM-U-07 — omitted fields are left as they are.
    Rules: update_product R3 (omitted -> unchanged), R6."""
    p = mk(db, s, avg_cost=Decimal("10.00"), selling_price=Decimal("15.00"), min_order_qty=1, note="Old")
    db.expire_all()

    result = M.update_product(db, prod_id=p.id, data=ProductUpdate(note="Only note"),
                              workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    row = reread(db, p)
    assert row.note == "Only note"
    # Then 3
    assert row.qty == 5
    assert row.avg_cost == Decimal("10.00")
    assert row.selling_price == Decimal("15.00")
    assert row.min_order_qty == 1


def test_prdm_u_08__raising_quantity_writes_one_adjustment_row(db, s):
    """PRDM-U-08 — raising the quantity writes one adjustment row.
    Rules: update_product R7, R8."""
    p = mk(db, s, avg_cost=Decimal("10.00"))
    db.expire_all()

    result = M.update_product(db, prod_id=p.id, data=ProductUpdate(qty=8), workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    row = reread(db, p)
    assert row.qty == 8
    assert row.avg_cost == Decimal("10.00")
    assert row.updated_by == s.U2.id
    # Then 3
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 4
    assert e.transaction_type == "inventory_adjustment"
    assert e.quantity == 3
    assert e.qty_before == 5
    assert e.qty_after == 8
    # Then 5
    assert e.unit_cost == Decimal("10.00")
    assert e.total_cost == Decimal("30.00")
    assert e.avg_cost_before == Decimal("10.00")
    assert e.avg_cost_after == Decimal("10.00")
    # Then 6
    assert e.source_type == "adjustment"
    assert e.source_id is None
    assert e.transfer_source_type is None
    assert e.transfer_source_id is None
    assert e.transfer_destination_type is None
    assert e.transfer_destination_id is None
    # Then 7
    assert e.notes == "Quantity adjusted from 5 to 8"
    assert e.performed_by == s.U2.id
    assert e.workspace_id == s.W1.id


def test_prdm_u_09__lowering_quantity_records_size_of_change(db, s):
    """PRDM-U-09 — lowering the quantity records the size of the change.
    Rules: update_product R7 (quantity = |new - old|)."""
    p = mk(db, s, avg_cost=Decimal("10.00"))
    db.expire_all()

    result = M.update_product(db, prod_id=p.id, data=ProductUpdate(qty=2), workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    assert reread(db, p).qty == 2
    # Then 3
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 4
    assert e.quantity == 3
    assert e.qty_before == 5
    assert e.qty_after == 2
    assert e.total_cost == Decimal("30.00")
    # Then 5
    assert e.notes == "Quantity adjusted from 5 to 2"


def test_prdm_u_10__change_of_one_unit_recorded(db, s):
    """PRDM-U-10 — a change of one unit is recorded.
    Rules: update_product R7 (smallest change)."""
    p = mk(db, s, avg_cost=Decimal("10.00"))
    db.expire_all()

    result = M.update_product(db, prod_id=p.id, data=ProductUpdate(qty=6), workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 3
    assert e.quantity == 1
    assert e.qty_before == 5
    assert e.qty_after == 6
    assert e.total_cost == Decimal("10.00")


def test_prdm_u_11__setting_quantity_to_0_recorded(db, s):
    """PRDM-U-11 — setting the quantity to 0 is recorded.
    Rules: update_product R7."""
    p = mk(db, s, avg_cost=Decimal("10.00"))
    db.expire_all()

    result = M.update_product(db, prod_id=p.id, data=ProductUpdate(qty=0), workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    assert reread(db, p).qty == 0
    # Then 3
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 4
    assert e.quantity == 5
    assert e.qty_before == 5
    assert e.qty_after == 0
    assert e.total_cost == Decimal("50.00")
    # Then 5
    assert e.notes == "Quantity adjusted from 5 to 0"


def test_prdm_u_12__new_cost_sent_with_quantity_prices_adjustment(db, s):
    """PRDM-U-12 — a new cost sent with the quantity prices the adjustment.
    Rules: update_product R6, R7 (avg_cost_after = unit_cost = the cost sent)."""
    p = mk(db, s, avg_cost=Decimal("10.00"))
    db.expire_all()

    result = M.update_product(db, prod_id=p.id, data=ProductUpdate(qty=7, avg_cost=Decimal("12.00")),
                              workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    row = reread(db, p)
    assert row.qty == 7
    assert row.avg_cost == Decimal("12.00")
    # Then 3
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 4
    assert e.quantity == 2
    assert e.qty_before == 5
    assert e.qty_after == 7
    # Then 5
    assert e.avg_cost_before == Decimal("10.00")
    assert e.avg_cost_after == Decimal("12.00")
    assert e.unit_cost == Decimal("12.00")
    assert e.total_cost == Decimal("24.00")


def test_prdm_u_13__no_cost_adjustment_has_empty_cost(db, s):
    """PRDM-U-13 — no cost: the adjustment has empty cost fields.
    Rules: update_product R7, R8 (unit_cost None -> total_cost NULL)."""
    p = mk(db, s)
    db.expire_all()

    result = M.update_product(db, prod_id=p.id, data=ProductUpdate(qty=9), workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 3
    assert e.quantity == 4
    assert e.unit_cost is None
    assert e.total_cost is None
    assert e.avg_cost_before is None
    assert e.avg_cost_after is None


def test_prdm_u_14__zero_cost_adjustment_carries_zero_cost(db, s):
    """PRDM-U-14 — a zero cost: the adjustment carries the zero cost.
    Rules: update_product R7 (parts that hold today; BUG-2779 is U-15)."""
    p = mk(db, s, avg_cost=Decimal("0.00"))
    db.expire_all()

    result = M.update_product(db, prod_id=p.id, data=ProductUpdate(qty=8), workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 3
    assert e.quantity == 3
    assert e.unit_cost == Decimal("0.00")
    assert e.avg_cost_before == Decimal("0.00")
    assert e.avg_cost_after == Decimal("0.00")


@xfail(BUG_2779)
def test_prdm_u_15__zero_cost_gives_adjustment_total_0(db, s):
    """PRDM-U-15 — a zero cost gives an adjustment total of 0.00.
    Rules: update_product R8 [BUG-2779]."""
    p = mk(db, s, avg_cost=Decimal("0.00"))
    db.expire_all()

    result = M.update_product(db, prod_id=p.id, data=ProductUpdate(qty=8), workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 3
    assert e.total_cost == Decimal("0.00")


def test_prdm_u_16__same_quantity_sent_again_writes_no_ledger(db, s):
    """PRDM-U-16 — the same quantity sent again writes no ledger row.
    Rules: update_product R7 ("sent and differs")."""
    p = mk(db, s, avg_cost=Decimal("10.00"))
    db.expire_all()

    result = M.update_product(db, prod_id=p.id, data=ProductUpdate(qty=5), workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    row = reread(db, p)
    assert row.qty == 5
    assert row.avg_cost == Decimal("10.00")
    # Then 3
    assert count(db, ProductLedger) == 0


@xfail(BUG_2771)
def test_prdm_u_17__same_values_sent_again_do_not_stamp(db, s):
    """PRDM-U-17 — the same values sent again do not stamp updated_by.
    Rules: update_product R5 [BUG-2771]; HR-9."""
    p = mk(db, s, avg_cost=Decimal("10.00"), note="Same")
    db.expire_all()

    result = M.update_product(db, prod_id=p.id, data=ProductUpdate(qty=5, note="Same"),
                              workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    assert count(db, ProductLedger) == 0
    # Then 3
    assert reread(db, p).updated_by is None


def test_prdm_u_18__empty_body_returns_row_no_ledger(db, s):
    """PRDM-U-18 — an empty body returns the row and writes no ledger row.
    Rules: update_product R5 (part that holds today; the stamp is U-19)."""
    p = mk(db, s, avg_cost=Decimal("10.00"))
    db.expire_all()

    result = M.update_product(db, prod_id=p.id, data=ProductUpdate(), workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    row = reread(db, p)
    assert row.qty == 5
    assert row.avg_cost == Decimal("10.00")
    # Then 3
    assert count(db, ProductLedger) == 0


@xfail(BUG_2771)
def test_prdm_u_19__empty_body_does_not_stamp(db, s):
    """PRDM-U-19 — an empty body does not stamp updated_by.
    Rules: update_product R5 [BUG-2771]; HR-9."""
    p = mk(db, s)
    db.expire_all()

    result = M.update_product(db, prod_id=p.id, data=ProductUpdate(), workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    assert reread(db, p).updated_by is None


def test_prdm_u_20__changing_only_cost_row_takes_new_cost(db, s):
    """PRDM-U-20 — changing only the cost: the row takes the new cost.
    Rules: update_product R6 (part that holds today; the ledger row is U-21)."""
    p = mk(db, s, avg_cost=Decimal("10.00"))
    db.expire_all()

    result = M.update_product(db, prod_id=p.id, data=ProductUpdate(avg_cost=Decimal("12.00")),
                              workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    row = reread(db, p)
    assert row.avg_cost == Decimal("12.00")
    assert row.qty == 5
    assert row.updated_by == s.U2.id


@xfail(BUG_2778)
def test_prdm_u_21__changing_only_cost_writes_zero_quantity_row(db, s):
    """PRDM-U-21 — changing only the cost writes a zero-quantity adjustment row.
    Rules: update_product R7 [BUG-2778]."""
    p = mk(db, s, avg_cost=Decimal("10.00"))
    db.expire_all()

    result = M.update_product(db, prod_id=p.id, data=ProductUpdate(avg_cost=Decimal("12.00")),
                              workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 3
    assert e.transaction_type == "inventory_adjustment"
    assert e.quantity == 0
    assert e.qty_before == 5
    assert e.qty_after == 5
    # Then 4
    assert e.avg_cost_before == Decimal("10.00")
    assert e.avg_cost_after == Decimal("12.00")
    assert e.unit_cost == Decimal("12.00")
    assert e.total_cost == Decimal("0.00")
    # Then 5
    assert e.source_type == "adjustment"
    assert e.notes == "Average cost adjusted from 10.00 to 12.00"
    assert e.performed_by == s.U2.id


@xfail(BUG_2778)
def test_prdm_u_22__same_quantity_with_new_cost_writes_cost_row(db, s):
    """PRDM-U-22 — the same quantity with a new cost also writes the cost row.
    Rules: update_product R7 [BUG-2778] (qty unchanged but avg_cost changes)."""
    p = mk(db, s, avg_cost=Decimal("10.00"))
    db.expire_all()

    result = M.update_product(db, prod_id=p.id, data=ProductUpdate(qty=5, avg_cost=Decimal("11.00")),
                              workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 3
    assert e.quantity == 0
    assert e.qty_before == 5
    assert e.qty_after == 5
    assert e.avg_cost_after == Decimal("11.00")


def test_prdm_u_23__same_cost_sent_again_writes_no_ledger(db, s):
    """PRDM-U-23 — the same cost sent again writes no ledger row.
    Rules: update_product R7 (cost "changes" means differs)."""
    p = mk(db, s, avg_cost=Decimal("10.00"))
    db.expire_all()

    result = M.update_product(db, prod_id=p.id, data=ProductUpdate(avg_cost=Decimal("10.00")),
                              workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    assert reread(db, p).avg_cost == Decimal("10.00")
    # Then 3
    assert count(db, ProductLedger) == 0


@xfail(BUG_2777)
def test_prdm_u_24__explicit_null_clears_selling_price(db, s):
    """PRDM-U-24 — an explicit null clears the selling price.
    Rules: update_product R3 [BUG-2777]."""
    p = mk(db, s, selling_price=Decimal("15.00"))
    db.expire_all()

    result = M.update_product(db, prod_id=p.id, data=ProductUpdate(selling_price=None),
                              workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    assert reread(db, p).selling_price is None


@xfail(BUG_2777)
def test_prdm_u_25__explicit_null_clears_note(db, s):
    """PRDM-U-25 — an explicit null clears the note.
    Rules: update_product R3 [BUG-2777]."""
    p = mk(db, s, note="Old")
    db.expire_all()

    result = M.update_product(db, prod_id=p.id, data=ProductUpdate(note=None), workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    assert reread(db, p).note is None


@xfail(BUG_2777)
def test_prdm_u_26__explicit_null_clears_minimum_order(db, s):
    """PRDM-U-26 — an explicit null clears the minimum order.
    Rules: update_product R3 [BUG-2777]."""
    p = mk(db, s, min_order_qty=4)
    db.expire_all()

    result = M.update_product(db, prod_id=p.id, data=ProductUpdate(min_order_qty=None),
                              workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    assert reread(db, p).min_order_qty is None


@xfail("BUG-2777, BUG-2778")
def test_prdm_u_27__explicit_null_clears_cost_and_writes_cost_row(db, s):
    """PRDM-U-27 — an explicit null clears the cost and writes the cost row.
    Rules: update_product R3, R7 [BUG-2777, BUG-2778]."""
    p = mk(db, s, avg_cost=Decimal("10.00"))
    db.expire_all()

    result = M.update_product(db, prod_id=p.id, data=ProductUpdate(avg_cost=None),
                              workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    row = reread(db, p)
    assert row.avg_cost is None
    assert row.qty == 5
    # Then 3
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 4
    assert e.quantity == 0
    assert e.qty_before == 5
    assert e.qty_after == 5
    assert e.avg_cost_before == Decimal("10.00")
    assert e.avg_cost_after is None
    assert e.total_cost is None
    # Then 5
    assert e.notes == "Average cost adjusted from 10.00 to None"


@pytest.mark.parametrize("build", [
    pytest.param(lambda: ProductUpdate(qty=None), id="PRDM-U-28", marks=xfail(BUG_2777)),
    pytest.param(lambda: ProductUpdate(is_available_for_sale=None), id="PRDM-U-29", marks=xfail(BUG_2777)),
    pytest.param(lambda: ProductUpdate(qty=-1), id="PRDM-U-30", marks=xfail(BUG_2775)),
    pytest.param(lambda: ProductUpdate(avg_cost=Decimal("-0.01")), id="PRDM-U-31", marks=xfail(BUG_2775)),
    pytest.param(lambda: ProductUpdate(selling_price=Decimal("-0.01")), id="PRDM-U-32", marks=xfail(BUG_2775)),
    pytest.param(lambda: ProductUpdate(min_order_qty=-1), id="PRDM-U-33", marks=xfail(BUG_2775)),
    pytest.param(lambda: ProductUpdate(avg_cost=Decimal("1.005")), id="PRDM-U-34", marks=xfail(BUG_2776)),
    pytest.param(lambda: ProductUpdate(selling_price=Decimal(10000000000000)), id="PRDM-U-35",
                 marks=xfail(BUG_2776)),
])
def test_prdm_u_28_to_35__update_schema_refuses_null_or_out_of_range(db, s, build):
    """PRDM-U-28 … PRDM-U-35 — the update schema refuses a null qty / flag or an out-of-range value.
    Rules: update_product R3 [BUG-2777], R4 [BUG-2775, BUG-2776], Errors row 4."""
    # Then 1
    with pytest.raises(PydanticValidationError):
        build()


def test_prdm_u_36__zero_values_pass_update_schema_and_stored(db, s):
    """PRDM-U-36 — zero values pass the update schema and are stored.
    Rules: update_product R4 (0 side), R6."""
    p = mk(db, s, avg_cost=Decimal("10.00"), selling_price=Decimal("15.00"), min_order_qty=1)
    db.expire_all()

    result = M.update_product(db, prod_id=p.id, data=ProductUpdate(selling_price=Decimal("0.00"), min_order_qty=0),
                              workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    row = reread(db, p)
    assert row.selling_price == Decimal("0.00")
    assert row.min_order_qty == 0


def test_prdm_u_37__update_touches_only_its_own_row(db, s):
    """PRDM-U-37 — the update touches only its own row.
    Rules: update_product R6; HR-16."""
    p0 = mk(db, s, workspace_id=s.W0.id)
    p = mk(db, s)
    pa = mk(db, s, for_sale=True)
    p9 = mk(db, s, workspace_id=s.W2.id)
    db.expire_all()
    before_p0, before_pa, before_p9 = snap(db, p0), snap(db, pa), snap(db, p9)

    result = M.update_product(db, prod_id=p.id, data=ProductUpdate(qty=8), workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    assert reread(db, p).qty == 8
    # Then 3
    assert snap(db, p0) == before_p0
    # Then 4
    assert snap(db, pa) == before_pa
    # Then 5
    assert snap(db, p9) == before_p9
    # Then 6
    assert count(db, ProductLedger) == 1


def test_prdm_u_38__update_flushed_not_committed(db, s):
    """PRDM-U-38 — the update is flushed but not committed.
    Rules: update_product Returns ("flushed"); Side effects."""
    p = mk(db, s)
    db.expire_all()

    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as spy:
        result = M.update_product(db, prod_id=p.id, data=ProductUpdate(qty=8), workspace_id=s.W1.id, user_id=s.U2.id)

        # Then 1
        assert result.id == p.id
        # Then 2
        assert count(db, ProductLedger) == 1
        # Then 3
        assert count(db, Product, Product.qty == 8) == 1
        sp.rollback()
        # Then 4
        assert count(db, ProductLedger) == 0
        # Then 5
        assert count(db, Product, Product.qty == 5) == 1
        # Then 6
        spy.assert_not_called()


@xfail(BUG_2770)
def test_prdm_u_39__row_read_with_row_lock(db, s):
    """PRDM-U-39 — the row is read with a row lock.
    Rules: update_product R11 [BUG-2770]; HR-10."""
    p = mk(db, s)
    db.expire_all()
    prod_id = p.id

    with record(db) as rec:
        result = M.update_product(db, prod_id=prod_id, data=ProductUpdate(qty=8),
                                  workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == prod_id
    # Then 2
    assert not any("SKIP LOCKED" in s_ for s_ in rec.psel)
    # Then 3
    assert not any("NOWAIT" in s_ for s_ in rec.psel)
    # Then 4
    assert any("FOR UPDATE" in s_ for s_ in rec.psel)


@xfail(BUG_2778)
def test_prdm_u_52__new_cost_printed_as_sent_in_note(db, s):
    """PRDM-U-52 — the new cost is printed as sent in the note.
    Rules: update_product R7, R7a [BUG-2778]."""
    p = mk(db, s, avg_cost=Decimal("10.00"))
    db.expire_all()

    result = M.update_product(db, prod_id=p.id, data=ProductUpdate(avg_cost=Decimal(12)),
                              workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 3
    assert e.notes == "Average cost adjusted from 10.00 to 12"
    # Then 4
    assert e.avg_cost_after == Decimal("12.00")
    assert e.quantity == 0


@xfail(BUG_2778)
def test_prdm_u_53__cost_on_uncosted_row_note_from_none(db, s):
    """PRDM-U-53 — setting a cost on an uncosted row writes the note from None.
    Rules: update_product R7, R7a, R8 [BUG-2778]."""
    p = mk(db, s)
    db.expire_all()

    result = M.update_product(db, prod_id=p.id, data=ProductUpdate(avg_cost=Decimal("12.00")),
                              workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 3
    assert e.notes == "Average cost adjusted from None to 12.00"
    # Then 4
    assert e.avg_cost_before is None
    assert e.avg_cost_after == Decimal("12.00")
    assert e.unit_cost == Decimal("12.00")
    assert e.total_cost == Decimal("0.00")
    # Then 5
    assert e.quantity == 0
    assert e.qty_before == 5
    assert e.qty_after == 5
    assert e.transaction_type == "inventory_adjustment"


def test_prdm_u_55__adjustment_cost_in_cents_exact_total(db, s):
    """PRDM-U-55 — an adjustment with a cost in cents records an exact total.
    Rules: update_product R7, R8 (total_cost = unit_cost × quantity, not rounded to whole units)."""
    p = mk(db, s, avg_cost=Decimal("3.35"))
    db.expire_all()

    result = M.update_product(db, prod_id=p.id, data=ProductUpdate(qty=8),
                              workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 3
    assert e.quantity == 3
    assert e.unit_cost == Decimal("3.35")
    assert e.total_cost == Decimal("10.05")


# --------------------------------------------------------------------------- #
# get_product
# --------------------------------------------------------------------------- #

def test_prdm_g_01__workspace_row_returned(db, s):
    """PRDM-G-01 — the workspace's row is returned.
    Rules: get_product R1."""
    p = mk(db, s, avg_cost=Decimal("10.00"), selling_price=Decimal("15.00"))
    db.expire_all()

    result = M.get_product(db, prod_id=p.id, workspace_id=s.W1.id)

    # Then 1
    assert isinstance(result, Product)
    # Then 2
    assert result.id == p.id
    assert result.workspace_id == s.W1.id
    assert result.qty == 5
    assert result.avg_cost == Decimal("10.00")
    assert result.selling_price == Decimal("15.00")


def test_prdm_g_02__unknown_id_not_found(db, s):
    """PRDM-G-02 — an unknown id is not found.
    Rules: get_product R1."""
    mk(db, s)
    db.expire_all()

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_product(db, prod_id=MISSING, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Product record with ID 999999999 not found"


def test_prdm_g_03__row_of_w0_not_found_from_w1(db, s):
    """PRDM-G-03 — a row of W0 (lower id) is not found from W1.
    Rules: get_product R1; HR-16."""
    p0 = mk(db, s, workspace_id=s.W0.id, factory_id=s.F0.id, item_id=s.I0.id)
    mk(db, s)
    db.expire_all()

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_product(db, prod_id=p0.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Product record with ID {p0.id} not found"


def test_prdm_g_04__row_of_w2_not_found_from_w1(db, s):
    """PRDM-G-04 — a row of W2 (higher id) is not found from W1.
    Rules: get_product R1; HR-16."""
    mk(db, s)
    p9 = mk(db, s, workspace_id=s.W2.id, factory_id=s.F9.id, item_id=s.I9.id)
    db.expire_all()

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_product(db, prod_id=p9.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Product record with ID {p9.id} not found"


def test_prdm_g_05__row_of_inactive_live_factory_returned(db, s):
    """PRDM-G-05 — a row of an inactive but live factory is returned.
    Rules: get_product R3 (inactive factory hides nothing)."""
    p = mk(db, s, factory_id=s.FI.id)
    db.expire_all()

    result = M.get_product(db, prod_id=p.id, workspace_id=s.W1.id)

    # Then 1
    assert result.id == p.id


@xfail(BUG_2772)
def test_prdm_g_06__soft_deleted_row_not_found_by_default(db, s):
    """PRDM-G-06 — a soft-deleted row is not found by default.
    Rules: get_product R2 [BUG-2772]; HR-4."""
    p = mk(db, s, deleted=True, qty=0)
    db.expire_all()

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_product(db, prod_id=p.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Product record with ID {p.id} not found"


@xfail(BUG_2772)
def test_prdm_g_07__include_deleted_returns_soft_deleted_row(db, s):
    """PRDM-G-07 — include_deleted=True returns a soft-deleted row.
    Rules: get_product R2 [BUG-2772]."""
    p = mk(db, s, deleted=True, qty=0)
    db.expire_all()

    result = M.get_product(db, prod_id=p.id, workspace_id=s.W1.id, include_deleted=True)

    # Then 1
    assert result.id == p.id
    # Then 2
    assert result.is_deleted is True


@xfail(BUG_2773)
def test_prdm_g_08__row_of_soft_deleted_factory_not_found(db, s):
    """PRDM-G-08 — a row of a soft-deleted factory is not found by default.
    Rules: get_product R3 [BUG-2773]."""
    p = mk(db, s, factory_id=s.FD.id)
    db.expire_all()

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_product(db, prod_id=p.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Product record with ID {p.id} not found"


@xfail(BUG_2773)
def test_prdm_g_09__row_of_removed_item_not_found(db, s):
    """PRDM-G-09 — a row of a removed item is not found by default.
    Rules: get_product R3 [BUG-2773]."""
    p = mk(db, s, item_id=s.IX.id)
    db.expire_all()

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_product(db, prod_id=p.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Product record with ID {p.id} not found"


@xfail(BUG_2773)
def test_prdm_g_10__include_deleted_returns_row_of_deleted_factory(db, s):
    """PRDM-G-10 — include_deleted=True returns a row of a soft-deleted factory.
    Rules: get_product R3 [BUG-2773]."""
    p = mk(db, s, factory_id=s.FD.id)
    db.expire_all()

    result = M.get_product(db, prod_id=p.id, workspace_id=s.W1.id, include_deleted=True)

    # Then 1
    assert result.id == p.id


def test_prdm_g_11__read_takes_no_lock_writes_nothing(db, s):
    """PRDM-G-11 — the read takes no lock and writes nothing.
    Rules: get_product Side effects (none); HR-10 scope."""
    p = mk(db, s)
    db.expire_all()
    prod_id, ws_id = p.id, s.W1.id

    with record(db) as rec:
        result = M.get_product(db, prod_id=prod_id, workspace_id=ws_id)

    # Then 1
    assert result.id == prod_id
    # Then 2
    assert all("FOR UPDATE" not in s_ for s_ in rec.selects)
    # Then 3
    assert rec.written == []
    # Then 4
    assert not db.dirty


# --------------------------------------------------------------------------- #
# list_products
# --------------------------------------------------------------------------- #

def test_prdm_l_01__defaults_return_live_rows_as_dao(db, s):
    """PRDM-L-01 — the defaults return the workspace's live rows, as the DAO does.
    Rules: list_products R1."""
    mk(db, s, workspace_id=s.W0.id, factory_id=s.F0.id, item_id=s.I0.id)
    pa = mk(db, s)
    pb = mk(db, s, for_sale=True, item_id=s.I2.id)
    mk(db, s, factory_id=s.F2.id, deleted=True, qty=0)
    mk(db, s, workspace_id=s.W2.id, factory_id=s.F9.id, item_id=s.I9.id)
    db.expire_all()

    result = M.list_products(db, workspace_id=s.W1.id)

    # Then 1
    assert sorted(r.id for r in result) == [pa.id, pb.id]
    # Then 2
    assert sorted(r.id for r in result) == sorted(r.id for r in product_dao.get_by_workspace(db, workspace_id=s.W1.id))


def test_prdm_l_02__factory_filter_passed_on(db, s):
    """PRDM-L-02 — the factory filter is passed on.
    Rules: list_products R1."""
    pa = mk(db, s)
    mk(db, s, factory_id=s.F2.id)
    pc = mk(db, s, item_id=s.I2.id)
    db.expire_all()

    result = M.list_products(db, workspace_id=s.W1.id, factory_id=s.F1.id, limit=1000)

    # Then 1
    assert sorted(r.id for r in result) == [pa.id, pc.id]


def test_prdm_l_03__for_sale_filter_passed_on(db, s):
    """PRDM-L-03 — the for-sale filter is passed on.
    Rules: list_products R1."""
    mk(db, s)
    pb = mk(db, s, for_sale=True)
    pc = mk(db, s, for_sale=True, item_id=s.I2.id)
    db.expire_all()

    result = M.list_products(db, workspace_id=s.W1.id, is_available_for_sale=True, limit=1000)

    # Then 1
    assert sorted(r.id for r in result) == [pb.id, pc.id]


def test_prdm_l_04__not_for_sale_filter_passed_on(db, s):
    """PRDM-L-04 — the not-for-sale filter is passed on (False is a filter, not "none").
    Rules: list_products R1."""
    pa = mk(db, s)
    mk(db, s, for_sale=True)
    db.expire_all()

    result = M.list_products(db, workspace_id=s.W1.id, is_available_for_sale=False, limit=1000)

    # Then 1
    assert [r.id for r in result] == [pa.id]


def test_prdm_l_05__skip_and_limit_passed_on(db, s):
    """PRDM-L-05 — skip and limit are passed on.
    Rules: list_products R1."""
    mk(db, s, item_id=s.I1.id)
    mk(db, s, item_id=s.I2.id)
    mk(db, s, for_sale=True, item_id=s.I1.id)
    mk(db, s, for_sale=True, item_id=s.I2.id)
    mk(db, s, factory_id=s.F2.id)
    db.expire_all()

    result = M.list_products(db, workspace_id=s.W1.id, skip=1, limit=2)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert len(M.list_products(db, workspace_id=s.W1.id, skip=4, limit=2)) == 1


def test_prdm_l_06__default_limit_is_100(db, s):
    """PRDM-L-06 — the default limit is 100.
    Rules: list_products R1 (default limit 100, skip 0)."""
    for n in range(101):
        name = f"P{n:03d}"
        item = Item(workspace_id=s.W1.id, name=name, name_normalized=name.lower(), unit="pcs")
        db.add(item)
        db.flush()
        mk(db, s, item_id=item.id)
    db.expire_all()

    result = M.list_products(db, workspace_id=s.W1.id)

    # Then 1
    assert len(result) == 100


def test_prdm_l_07__list_takes_no_lock_writes_nothing(db, s):
    """PRDM-L-07 — the list takes no lock and writes nothing.
    Rules: list_products Side effects (none)."""
    pa = mk(db, s)
    db.expire_all()
    pa_id, ws_id = pa.id, s.W1.id

    with record(db) as rec:
        result = M.list_products(db, workspace_id=ws_id, limit=1000)

    # Then 1
    assert [r.id for r in result] == [pa_id]
    # Then 2
    assert all("FOR UPDATE" not in s_ for s_ in rec.selects)
    # Then 3
    assert rec.written == []


# --------------------------------------------------------------------------- #
# delete_product
# --------------------------------------------------------------------------- #

def test_prdm_d_01__row_at_0_soft_deleted_and_returned(db, s):
    """PRDM-D-01 — a row at 0 is soft-deleted and returned.
    Rules: delete_product R4."""
    p = mk(db, s, qty=0, avg_cost=Decimal("10.00"), selling_price=Decimal("15.00"))
    db.expire_all()

    result = M.delete_product(db, prod_id=p.id, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    row = reread(db, p)
    assert row.is_deleted is True
    assert row.is_active is False
    assert row.deleted_at is not None
    assert row.deleted_by == s.U2.id
    # Then 3
    assert row.updated_by is None
    assert row.qty == 0
    assert row.avg_cost == Decimal("10.00")
    assert row.selling_price == Decimal("15.00")
    # Then 4
    assert count(db, ProductLedger) == 0


def test_prdm_d_02__unknown_id_not_found(db, s):
    """PRDM-D-02 — an unknown id is not found.
    Rules: delete_product R1."""
    p = mk(db, s, qty=0)
    db.expire_all()
    before_p = snap(db, p)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_product(db, prod_id=MISSING, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Product record with ID 999999999 not found"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert snap(db, p) == before_p


def test_prdm_d_03__row_of_w0_not_found_from_w1(db, s):
    """PRDM-D-03 — a row of W0 (lower id) is not found from W1.
    Rules: delete_product R1; HR-16."""
    p0 = mk(db, s, workspace_id=s.W0.id, factory_id=s.F0.id, item_id=s.I0.id, qty=0)
    mk(db, s, qty=0)
    db.expire_all()
    before_p0 = snap(db, p0)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_product(db, prod_id=p0.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Product record with ID {p0.id} not found"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert snap(db, p0) == before_p0


def test_prdm_d_04__row_of_w2_not_found_from_w1(db, s):
    """PRDM-D-04 — a row of W2 (higher id) is not found from W1.
    Rules: delete_product R1; HR-16."""
    mk(db, s, qty=0)
    p9 = mk(db, s, workspace_id=s.W2.id, factory_id=s.F9.id, item_id=s.I9.id, qty=4)
    db.expire_all()
    before_p9 = snap(db, p9)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_product(db, prod_id=p9.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Product record with ID {p9.id} not found"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert snap(db, p9) == before_p9


def test_prdm_d_05__already_deleted_row_refused(db, s):
    """PRDM-D-05 — an already deleted row is refused.
    Rules: delete_product R2."""
    p = mk(db, s, deleted=True, qty=0)
    db.expire_all()
    before_p = snap(db, p)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_product(db, prod_id=p.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Product record is already deleted"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert snap(db, p) == before_p


def test_prdm_d_06__already_deleted_row_with_stock_is_already_deleted(db, s):
    """PRDM-D-06 — an already deleted row that kept stock is "already deleted".
    Rules: delete_product R2 before R3."""
    p = mk(db, s, deleted=True, qty=4)
    db.expire_all()
    before_p = snap(db, p)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_product(db, prod_id=p.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Product record is already deleted"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert snap(db, p) == before_p


@xfail(BUG_2774)
def test_prdm_d_07__row_holding_stock_refused_with_blocker(db, s):
    """PRDM-D-07 — a row holding stock is refused with its blocker.
    Rules: delete_product R3 [BUG-2774]."""
    p = mk(db, s, qty=4)
    db.expire_all()
    before = counts(db)
    before_p = snap(db, p)

    # Then 1
    with pytest.raises(AppValidationError) as exc:
        M.delete_product(db, prod_id=p.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Product record still holds stock"
    # Then 4
    assert exc.value.errors == [{"type": "product_stock", "id": p.id, "qty": 4}]
    # Then 5
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 6
    assert counts(db) == before
    # Then 7
    assert snap(db, p) == before_p


@xfail(BUG_2774)
def test_prdm_d_08__row_with_negative_stock_refused_with_blocker(db, s):
    """PRDM-D-08 — a row with negative stock is refused with its blocker.
    Rules: delete_product R3 [BUG-2774] (qty != 0, negative side)."""
    p = mk(db, s, qty=-2)
    db.expire_all()
    before = counts(db)
    before_p = snap(db, p)

    # Then 1
    with pytest.raises(AppValidationError) as exc:
        M.delete_product(db, prod_id=p.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Product record still holds stock"
    # Then 4
    assert exc.value.errors == [{"type": "product_stock", "id": p.id, "qty": -2}]
    # Then 5
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 6
    assert counts(db) == before
    # Then 7
    assert snap(db, p) == before_p


def test_prdm_d_09__delete_touches_only_its_own_row(db, s):
    """PRDM-D-09 — the delete touches only its own row.
    Rules: delete_product R4; HR-16."""
    p0 = mk(db, s, workspace_id=s.W0.id, qty=0)
    p = mk(db, s, qty=0)
    pa = mk(db, s, for_sale=True, qty=0)
    p9 = mk(db, s, workspace_id=s.W2.id, qty=0)
    db.expire_all()
    before_p0, before_pa, before_p9 = snap(db, p0), snap(db, pa), snap(db, p9)

    result = M.delete_product(db, prod_id=p.id, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    assert reread(db, p).is_deleted is True
    # Then 3
    assert snap(db, p0) == before_p0
    # Then 4
    assert snap(db, pa) == before_pa
    # Then 5
    assert snap(db, p9) == before_p9


def test_prdm_d_10__delete_takes_no_lock(db, s):
    """PRDM-D-10 — the delete takes no lock.
    Rules: delete_product R4 (no lock, HR-10 exempt)."""
    p = mk(db, s, qty=0)
    db.expire_all()
    prod_id = p.id

    with record(db) as rec:
        result = M.delete_product(db, prod_id=prod_id, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == prod_id
    # Then 2
    assert all("FOR UPDATE" not in s_ for s_ in rec.selects)


def test_prdm_d_11__delete_flushed_not_committed(db, s):
    """PRDM-D-11 — the delete is flushed but not committed.
    Rules: delete_product Side effects ("flushed")."""
    p = mk(db, s, qty=0)
    db.expire_all()

    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as spy:
        result = M.delete_product(db, prod_id=p.id, workspace_id=s.W1.id, user_id=s.U2.id)

        # Then 1
        assert result.id == p.id
        # Then 2
        assert count(db, Product, Product.is_deleted.is_(True)) == 1
        sp.rollback()
        # Then 3
        assert count(db, Product, Product.is_deleted.is_(True)) == 0
        # Then 4
        spy.assert_not_called()


# --------------------------------------------------------------------------- #
# apply_production_output (unit_cost not given)
# --------------------------------------------------------------------------- #

def test_prdm_po_01__output_into_empty_key_creates_bucket(db, s):
    """PRDM-PO-01 — output into a key with no row creates the not-for-sale bucket.
    Rules: apply_production_output R2, R3, R4, R8."""
    result = M.apply_production_output(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                       item_id=s.I1.id, quantity=3, batch_id=77,
                                       notes="SYSTEM - PRODUCTION BATCH COMPLETE | B-17")

    # Then 1
    assert isinstance(result, Product)
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == s.W1.id
    assert row.factory_id == s.F1.id
    assert row.item_id == s.I1.id
    assert row.is_available_for_sale is False
    assert row.qty == 3
    assert row.avg_cost is None
    # Then 3
    assert row.created_by == s.U2.id
    assert row.updated_by == s.U2.id
    assert row.is_deleted is False
    # Then 4
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 5
    assert e.transaction_type == "production"
    assert e.quantity == 3
    assert e.qty_before == 0
    assert e.qty_after == 3
    # Then 6
    assert e.unit_cost is None
    assert e.total_cost is None
    assert e.avg_cost_before is None
    assert e.avg_cost_after is None
    # Then 7
    assert e.source_type == "production_batch"
    assert e.source_id == 77
    assert e.transfer_source_type is None
    assert e.transfer_source_id is None
    assert e.transfer_destination_type is None
    assert e.transfer_destination_id is None
    # Then 8
    assert e.notes == "SYSTEM - PRODUCTION BATCH COMPLETE | B-17"
    assert e.performed_by == s.U2.id
    assert e.workspace_id == s.W1.id


def test_prdm_po_02__output_adds_to_existing_bucket_keeps_cost(db, s):
    """PRDM-PO-02 — output adds to the existing not-for-sale bucket and keeps its cost.
    Rules: apply_production_output R2, R3, R4, R8."""
    p = mk(db, s, avg_cost=Decimal("10.00"))
    db.expire_all()

    result = M.apply_production_output(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                       item_id=s.I1.id, quantity=4, batch_id=77)

    # Then 1
    assert result.id == p.id
    # Then 2
    row = reread(db, p)
    assert row.qty == 9
    assert row.avg_cost == Decimal("10.00")
    assert row.updated_by == s.U2.id
    # Then 3
    assert count(db, Product) == 1
    # Then 4
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 5
    assert e.quantity == 4
    assert e.qty_before == 5
    assert e.qty_after == 9
    # Then 6
    assert e.unit_cost is None
    assert e.total_cost is None
    assert e.avg_cost_before == Decimal("10.00")
    assert e.avg_cost_after == Decimal("10.00")


def test_prdm_po_03__one_unit_accepted(db, s):
    """PRDM-PO-03 — one unit is accepted.
    Rules: apply_production_output R1 (other side of <= 0)."""
    p = mk(db, s)
    db.expire_all()

    result = M.apply_production_output(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                       item_id=s.I1.id, quantity=1, batch_id=77)

    # Then 1
    assert result.id == p.id
    # Then 2
    assert reread(db, p).qty == 6
    # Then 3
    assert len(ledger_of(db, s, s.F1, s.I1)) == 1


def test_prdm_po_04__zero_output_refused(db, s):
    """PRDM-PO-04 — zero output is refused.
    Rules: apply_production_output R1, Errors row 1."""
    p = mk(db, s)
    db.expire_all()
    before = counts(db)
    before_p = snap(db, p)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.apply_production_output(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                  item_id=s.I1.id, quantity=0, batch_id=77)
    # Then 2
    assert str(exc.value) == "Production output quantity must be positive"
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert counts(db) == before
    # Then 5
    assert snap(db, p) == before_p


def test_prdm_po_05__negative_output_refused_no_bucket(db, s):
    """PRDM-PO-05 — negative output is refused, also with no bucket.
    Rules: apply_production_output R1."""
    before = counts(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.apply_production_output(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                  item_id=s.I1.id, quantity=-1, batch_id=77)
    # Then 2
    assert str(exc.value) == "Production output quantity must be positive"
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert counts(db) == before


def test_prdm_po_06__for_sale_row_never_used(db, s):
    """PRDM-PO-06 — a for-sale row is never used: a not-for-sale row is created beside it.
    Rules: apply_production_output R2, R2a ("the for-sale row is never touched")."""
    ps = mk(db, s, for_sale=True, qty=20)
    db.expire_all()
    before_ps = snap(db, ps)

    result = M.apply_production_output(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                       item_id=s.I1.id, quantity=3, batch_id=77)

    # Then 1
    assert result.id != ps.id
    # Then 2
    row = reread(db, result)
    assert row.is_available_for_sale is False
    assert row.qty == 3
    # Then 3
    assert snap(db, ps) == before_ps
    # Then 4
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 5
    assert e.qty_before == 0
    assert e.qty_after == 3


def test_prdm_po_07__both_rows_only_not_for_sale_moves(db, s):
    """PRDM-PO-07 — with both rows present, only the not-for-sale row moves.
    Rules: apply_production_output R2, R2a."""
    ps = mk(db, s, for_sale=True, qty=20)
    p = mk(db, s)
    db.expire_all()
    before_ps = snap(db, ps)

    result = M.apply_production_output(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                       item_id=s.I1.id, quantity=3, batch_id=77)

    # Then 1
    assert result.id == p.id
    # Then 2
    assert reread(db, p).qty == 8
    # Then 3
    assert snap(db, ps) == before_ps


def test_prdm_po_08__rows_of_other_factory_or_item_untouched(db, s):
    """PRDM-PO-08 — rows of another factory or item are not touched.
    Rules: apply_production_output R2 (key = factory and item)."""
    pa = mk(db, s, factory_id=s.F2.id)
    p = mk(db, s)
    pb = mk(db, s, item_id=s.I2.id)
    db.expire_all()
    before_pa, before_pb = snap(db, pa), snap(db, pb)

    result = M.apply_production_output(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                       item_id=s.I1.id, quantity=3, batch_id=77)

    # Then 1
    assert result.id == p.id
    # Then 2
    assert reread(db, p).qty == 8
    # Then 3
    assert snap(db, pa) == before_pa
    # Then 4
    assert snap(db, pb) == before_pb


def test_prdm_po_09__same_key_rows_of_w0_w2_neither_used_nor_touched(db, s):
    """PRDM-PO-09 — same-key rows of W0 and W2 are neither used nor touched.
    Rules: apply_production_output R2 (workspace in the key); HR-16."""
    p0 = mk(db, s, workspace_id=s.W0.id, qty=50)
    p9 = mk(db, s, workspace_id=s.W2.id, qty=60)
    db.expire_all()
    before_p0, before_p9 = snap(db, p0), snap(db, p9)

    result = M.apply_production_output(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                       item_id=s.I1.id, quantity=3, batch_id=77)

    # Then 1
    assert result.id != p0.id
    assert result.id != p9.id
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == s.W1.id
    assert row.qty == 3
    # Then 3
    assert snap(db, p0) == before_p0
    # Then 4
    assert snap(db, p9) == before_p9
    # Then 5
    assert len(ledger_of(db, s, s.F1, s.I1)) == 1


def test_prdm_po_10__no_notes_default_batch_note(db, s):
    """PRDM-PO-10 — no notes give the default batch note.
    Rules: apply_production_output R8 (notes falsy -> default)."""
    p = mk(db, s)
    db.expire_all()

    result = M.apply_production_output(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                       item_id=s.I1.id, quantity=3, batch_id=77)

    # Then 1
    assert result.id == p.id
    # Then 2
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    # Then 3
    assert entries[0].notes == "SYSTEM - PRODUCTION BATCH COMPLETE | batch id 77"


def test_prdm_po_11__empty_notes_default_batch_note(db, s):
    """PRDM-PO-11 — empty notes also give the default batch note.
    Rules: apply_production_output R8 ("" takes the default)."""
    p = mk(db, s)
    db.expire_all()

    result = M.apply_production_output(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                       item_id=s.I1.id, quantity=3, batch_id=78, notes="")

    # Then 1
    assert result.id == p.id
    # Then 2
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    # Then 3
    assert entries[0].notes == "SYSTEM - PRODUCTION BATCH COMPLETE | batch id 78"


def test_prdm_po_12__second_call_same_batch_posts_again(db, s):
    """PRDM-PO-12 — a second call for the same batch posts again.
    Rules: apply_production_output R9."""
    p = mk(db, s)
    M.apply_production_output(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                              item_id=s.I1.id, quantity=3, batch_id=77)
    db.expire_all()

    result = M.apply_production_output(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                       item_id=s.I1.id, quantity=3, batch_id=77)

    # Then 1
    assert result.id == p.id
    # Then 2
    assert reread(db, p).qty == 11
    # Then 3
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 2
    # Then 4
    assert [e.source_id for e in entries] == [77, 77]
    assert [e.qty_after for e in entries] == [8, 11]


def test_prdm_po_13__negative_bucket_added_to(db, s):
    """PRDM-PO-13 — a negative bucket is added to.
    Rules: apply_production_output R3."""
    p = mk(db, s, qty=-2)
    db.expire_all()

    result = M.apply_production_output(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                       item_id=s.I1.id, quantity=4, batch_id=77)

    # Then 1
    assert result.id == p.id
    # Then 2
    assert reread(db, p).qty == 2
    # Then 3
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 4
    assert e.qty_before == -2
    assert e.qty_after == 2
    assert e.quantity == 4


@xfail(BUG_1336)
def test_prdm_po_14__soft_deleted_row_restored_and_added_to(db, s):
    """PRDM-PO-14 — a soft-deleted not-for-sale row is restored and added to.
    Rules: apply_production_output R2a [BUG-1336]."""
    p = mk(db, s, deleted=True, qty=6, avg_cost=Decimal("3.00"))
    db.expire_all()

    result = M.apply_production_output(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                       item_id=s.I1.id, quantity=4, batch_id=77)

    # Then 1
    assert result.id == p.id
    # Then 2
    row = reread(db, p)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 3
    assert row.qty == 10
    assert row.avg_cost == Decimal("3.00")
    assert row.updated_by == s.U2.id
    assert row.is_available_for_sale is False
    # Then 4
    assert count(db, Product) == 1
    # Then 5
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 6
    assert e.transaction_type == "production"
    assert e.qty_before == 6
    assert e.qty_after == 10
    assert e.quantity == 4


@xfail(BUG_2770)
def test_prdm_po_15__bucket_row_read_with_row_lock(db, s):
    """PRDM-PO-15 — the bucket row is read with a row lock.
    Rules: apply_production_output R10 [BUG-2770]; HR-10."""
    p = mk(db, s)
    db.expire_all()
    prod_id, ws_id, u_id, f_id, i_id = p.id, s.W1.id, s.U2.id, s.F1.id, s.I1.id

    with record(db) as rec:
        result = M.apply_production_output(db, workspace_id=ws_id, user_id=u_id, factory_id=f_id,
                                           item_id=i_id, quantity=3, batch_id=77)

    # Then 1
    assert result.id == prod_id
    # Then 2
    assert not any("SKIP LOCKED" in s_ for s_ in rec.psel)
    # Then 3
    assert not any("NOWAIT" in s_ for s_ in rec.psel)
    # Then 4
    assert any("FOR UPDATE" in s_ for s_ in rec.psel)


def test_prdm_po_16__output_flushed_not_committed(db, s):
    """PRDM-PO-16 — the output is flushed but not committed.
    Rules: apply_production_output Returns ("flushed"); Side effects."""
    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as spy:
        result = M.apply_production_output(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                           item_id=s.I1.id, quantity=3, batch_id=77)

        # Then 1
        assert result.id is not None
        # Then 2
        assert count(db, Product) == 1
        # Then 3
        assert count(db, ProductLedger) == 1
        sp.rollback()
        # Then 4
        assert count(db, Product) == 0
        # Then 5
        assert count(db, ProductLedger) == 0
        # Then 6
        spy.assert_not_called()


# --------------------------------------------------------------------------- #
# apply_sale_deduction
# --------------------------------------------------------------------------- #

def test_prdm_sd_01__delivery_takes_units_at_average(db, s):
    """PRDM-SD-01 — a delivery takes units from the for-sale bucket at its average.
    Rules: apply_sale_deduction R5, R6."""
    p = mk(db, s, for_sale=True, qty=10, avg_cost=Decimal("4.00"))
    db.expire_all()

    result = M.apply_sale_deduction(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                    item_id=s.I1.id, quantity=3, delivery_id=55, account_id=s.AC1.id,
                                    notes="Delivery DL-1 for SO-7")

    # Then 1
    assert result.id == p.id
    # Then 2
    row = reread(db, p)
    assert row.qty == 7
    assert row.avg_cost == Decimal("4.00")
    assert row.updated_by == s.U2.id
    # Then 3
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 4
    assert e.transaction_type == "sale"
    assert e.quantity == 3
    assert e.qty_before == 10
    assert e.qty_after == 7
    # Then 5
    assert e.unit_cost == Decimal("4.00")
    assert e.total_cost == Decimal("12.00")
    assert e.avg_cost_before == Decimal("4.00")
    assert e.avg_cost_after == Decimal("4.00")
    # Then 6
    assert e.source_type == "sales_delivery"
    assert e.source_id == 55
    assert e.transfer_destination_type == "customer"
    assert e.transfer_destination_id == s.AC1.id
    assert e.transfer_source_type is None
    assert e.transfer_source_id is None
    # Then 7
    assert e.notes == "Delivery DL-1 for SO-7"
    assert e.performed_by == s.U2.id
    assert e.workspace_id == s.W1.id


def test_prdm_sd_02__whole_decimal_quantity_used_as_whole_units(db, s):
    """PRDM-SD-02 — a whole Decimal quantity is used as whole units.
    Rules: apply_sale_deduction R2."""
    p = mk(db, s, for_sale=True, qty=10, avg_cost=Decimal("4.00"))
    db.expire_all()

    result = M.apply_sale_deduction(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                    item_id=s.I1.id, quantity=Decimal("3.00"), delivery_id=55, account_id=s.AC1.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    assert reread(db, p).qty == 7
    # Then 3
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 4
    assert e.quantity == 3
    assert e.total_cost == Decimal("12.00")


def test_prdm_sd_03__taking_exactly_what_is_held_leaves_0(db, s):
    """PRDM-SD-03 — taking exactly what is held leaves 0.
    Rules: apply_sale_deduction R4 (equal allowed)."""
    p = mk(db, s, for_sale=True, qty=3, avg_cost=Decimal("4.00"))
    db.expire_all()

    result = M.apply_sale_deduction(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                    item_id=s.I1.id, quantity=3, delivery_id=55, account_id=s.AC1.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    assert reread(db, p).qty == 0
    # Then 3
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 4
    assert e.qty_before == 3
    assert e.qty_after == 0


def test_prdm_sd_04__bucket_with_no_cost_empty_cost_fields(db, s):
    """PRDM-SD-04 — a bucket with no cost records empty cost fields.
    Rules: apply_sale_deduction R6 (average None -> NULL)."""
    p = mk(db, s, for_sale=True, qty=10)
    db.expire_all()

    result = M.apply_sale_deduction(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                    item_id=s.I1.id, quantity=3, delivery_id=55, account_id=s.AC1.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 3
    assert e.unit_cost is None
    assert e.total_cost is None
    assert e.avg_cost_before is None
    assert e.avg_cost_after is None


def test_prdm_sd_05__zero_average_total_0(db, s):
    """PRDM-SD-05 — a zero average records a total of 0.00.
    Rules: apply_sale_deduction R6 (0 -> 0.00)."""
    p = mk(db, s, for_sale=True, qty=10, avg_cost=Decimal("0.00"))
    db.expire_all()

    result = M.apply_sale_deduction(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                    item_id=s.I1.id, quantity=3, delivery_id=55, account_id=s.AC1.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 3
    assert e.unit_cost == Decimal("0.00")
    assert e.total_cost == Decimal("0.00")


def test_prdm_sd_06__no_notes_no_account_default_note_empty_destination(db, s):
    """PRDM-SD-06 — no notes and no account: default note, empty destination id.
    Rules: apply_sale_deduction R6 (default notes; account_id may be NULL)."""
    p = mk(db, s, for_sale=True, qty=10)
    db.expire_all()

    result = M.apply_sale_deduction(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                    item_id=s.I1.id, quantity=3, delivery_id=55)

    # Then 1
    assert result.id == p.id
    # Then 2
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 3
    assert e.notes == "SYSTEM - SALES DELIVERY | delivery id 55"
    # Then 4
    assert e.transfer_destination_type == "customer"
    assert e.transfer_destination_id is None


def test_prdm_sd_07__empty_notes_default_note(db, s):
    """PRDM-SD-07 — empty notes also give the default note.
    Rules: apply_sale_deduction R6 (notes falsy)."""
    p = mk(db, s, for_sale=True, qty=10)
    db.expire_all()

    result = M.apply_sale_deduction(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                    item_id=s.I1.id, quantity=3, delivery_id=56, account_id=s.AC1.id, notes="")

    # Then 1
    assert result.id == p.id
    # Then 2
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    # Then 3
    assert entries[0].notes == "SYSTEM - SALES DELIVERY | delivery id 56"


def test_prdm_sd_08__zero_quantity_refused(db, s):
    """PRDM-SD-08 — zero quantity is refused.
    Rules: apply_sale_deduction R1, Errors row 1."""
    p = mk(db, s, for_sale=True, qty=10)
    db.expire_all()
    before = counts(db)
    before_p = snap(db, p)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.apply_sale_deduction(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                               item_id=s.I1.id, quantity=0, delivery_id=55, account_id=s.AC1.id)
    # Then 2
    assert str(exc.value) == "Sale deduction quantity must be positive"
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert counts(db) == before
    # Then 5
    assert snap(db, p) == before_p


def test_prdm_sd_09__negative_quantity_refused(db, s):
    """PRDM-SD-09 — a negative quantity is refused.
    Rules: apply_sale_deduction R1."""
    p = mk(db, s, for_sale=True, qty=10)
    db.expire_all()
    before = counts(db)
    before_p = snap(db, p)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.apply_sale_deduction(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                               item_id=s.I1.id, quantity=-1, delivery_id=55, account_id=s.AC1.id)
    # Then 2
    assert str(exc.value) == "Sale deduction quantity must be positive"
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert counts(db) == before
    # Then 5
    assert snap(db, p) == before_p


def test_prdm_sd_10__negative_fraction_refused_as_not_positive(db, s):
    """PRDM-SD-10 — a negative fraction is refused as not positive, before the fraction check.
    Rules: apply_sale_deduction R1 ("checked before R2")."""
    mk(db, s, for_sale=True, qty=10)
    db.expire_all()
    before = counts(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.apply_sale_deduction(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                               item_id=s.I1.id, quantity=Decimal("-0.5"), delivery_id=55, account_id=s.AC1.id)
    # Then 2
    assert str(exc.value) == "Sale deduction quantity must be positive"
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert counts(db) == before


def test_prdm_sd_11__fractional_quantity_refused(db, s):
    """PRDM-SD-11 — a fractional quantity is refused.
    Rules: apply_sale_deduction R3, Errors row 2."""
    p = mk(db, s, for_sale=True, qty=10)
    db.expire_all()
    before = counts(db)
    before_p = snap(db, p)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.apply_sale_deduction(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                               item_id=s.I1.id, quantity=Decimal("2.5"), delivery_id=55, account_id=s.AC1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Delivery line has a fractional quantity; stock requires whole units"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before
    # Then 6
    assert snap(db, p) == before_p


def test_prdm_sd_12__no_for_sale_row_refused_available_0(db, s):
    """PRDM-SD-12 — no for-sale row: refused, available 0.
    Rules: apply_sale_deduction R4 (part that holds today; text is SD-18), Errors row 3."""
    before = counts(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.apply_sale_deduction(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                               item_id=s.I1.id, quantity=3, delivery_id=55, account_id=s.AC1.id)
    # Then 2
    assert exc.value.status_code == 422
    # Then 3
    assert exc.value.detail.startswith("Insufficient sellable stock for ")
    # Then 4
    assert exc.value.detail.endswith(": requested 3, available 0")
    # Then 5
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 6
    assert counts(db) == before


def test_prdm_sd_13__too_little_stock_refused_with_available(db, s):
    """PRDM-SD-13 — too little stock: refused with what is available.
    Rules: apply_sale_deduction R4."""
    p = mk(db, s, for_sale=True, qty=2, avg_cost=Decimal("4.00"))
    db.expire_all()
    before = counts(db)
    before_p = snap(db, p)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.apply_sale_deduction(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                               item_id=s.I1.id, quantity=3, delivery_id=55, account_id=s.AC1.id)
    # Then 2
    assert exc.value.status_code == 422
    # Then 3
    assert exc.value.detail.endswith(": requested 3, available 2")
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before
    # Then 6
    assert snap(db, p) == before_p


def test_prdm_sd_14__soft_deleted_for_sale_row_counts_as_missing(db, s):
    """PRDM-SD-14 — a soft-deleted for-sale row counts as missing and is not restored.
    Rules: apply_sale_deduction R4 (deleted row = available 0, not restored)."""
    p = mk(db, s, for_sale=True, deleted=True, qty=10)
    db.expire_all()
    before = counts(db)
    before_p = snap(db, p)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.apply_sale_deduction(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                               item_id=s.I1.id, quantity=3, delivery_id=55, account_id=s.AC1.id)
    # Then 2
    assert exc.value.status_code == 422
    # Then 3
    assert exc.value.detail.endswith(": requested 3, available 0")
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before
    # Then 6
    assert snap(db, p) == before_p


def test_prdm_sd_15__not_for_sale_row_never_counts(db, s):
    """PRDM-SD-15 — the not-for-sale row never counts.
    Rules: apply_sale_deduction R4."""
    p = mk(db, s, qty=10)
    db.expire_all()
    before = counts(db)
    before_p = snap(db, p)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.apply_sale_deduction(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                               item_id=s.I1.id, quantity=3, delivery_id=55, account_id=s.AC1.id)
    # Then 2
    assert exc.value.status_code == 422
    # Then 3
    assert exc.value.detail.endswith(": requested 3, available 0")
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before
    # Then 6
    assert snap(db, p) == before_p


def test_prdm_sd_16__for_sale_rows_of_w0_w2_do_not_count(db, s):
    """PRDM-SD-16 — for-sale rows of the same key in W0 and W2 do not count.
    Rules: apply_sale_deduction R4 (workspace in the key); HR-16."""
    p0 = mk(db, s, workspace_id=s.W0.id, for_sale=True, qty=10)
    p9 = mk(db, s, workspace_id=s.W2.id, for_sale=True, qty=10)
    db.expire_all()
    before = counts(db)
    before_p0, before_p9 = snap(db, p0), snap(db, p9)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.apply_sale_deduction(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                               item_id=s.I1.id, quantity=3, delivery_id=55, account_id=s.AC1.id)
    # Then 2
    assert exc.value.status_code == 422
    # Then 3
    assert exc.value.detail.endswith(": requested 3, available 0")
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before
    # Then 6
    assert snap(db, p0) == before_p0
    # Then 7
    assert snap(db, p9) == before_p9


def test_prdm_sd_17__for_sale_row_of_other_factory_does_not_count(db, s):
    """PRDM-SD-17 — a for-sale row of another factory does not count.
    Rules: apply_sale_deduction R4 (key = factory)."""
    pa = mk(db, s, for_sale=True, factory_id=s.F2.id, qty=10)
    db.expire_all()
    before = counts(db)
    before_pa = snap(db, pa)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.apply_sale_deduction(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                               item_id=s.I1.id, quantity=3, delivery_id=55, account_id=s.AC1.id)
    # Then 2
    assert exc.value.status_code == 422
    # Then 3
    assert exc.value.detail.endswith(": requested 3, available 0")
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before
    # Then 6
    assert snap(db, pa) == before_pa


@xfail(BUG_2782)
def test_prdm_sd_18__short_stock_message_names_item_and_factory(db, s):
    """PRDM-SD-18 — the short-stock message names the item and factory.
    Rules: apply_sale_deduction R4 [BUG-2782]."""
    mk(db, s, for_sale=True, qty=2)
    db.expire_all()

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.apply_sale_deduction(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                               item_id=s.I1.id, quantity=3, delivery_id=55, account_id=s.AC1.id)
    # Then 2
    assert exc.value.status_code == 422
    # Then 3
    assert exc.value.detail == 'Insufficient sellable stock for "Bolt" at Factory One: requested 3, available 2'


@xfail(BUG_2782)
def test_prdm_sd_19__no_row_message_names_item_and_factory(db, s):
    """PRDM-SD-19 — the no-row message names the item and factory.
    Rules: apply_sale_deduction R4 [BUG-2782]."""
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.apply_sale_deduction(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F2.id,
                               item_id=s.I2.id, quantity=3, delivery_id=55, account_id=s.AC1.id)
    # Then 2
    assert exc.value.status_code == 422
    # Then 3
    assert exc.value.detail == 'Insufficient sellable stock for "Cam" at Factory Two: requested 3, available 0'


def test_prdm_sd_20__only_w1_for_sale_row_moves(db, s):
    """PRDM-SD-20 — only the W1 for-sale row moves; its neighbours stay.
    Rules: apply_sale_deduction R4, R5; HR-16."""
    p0 = mk(db, s, workspace_id=s.W0.id, for_sale=True, qty=10)
    pn = mk(db, s, qty=10)
    p = mk(db, s, for_sale=True, qty=10)
    p9 = mk(db, s, workspace_id=s.W2.id, for_sale=True, qty=10)
    db.expire_all()
    before_p0, before_pn, before_p9 = snap(db, p0), snap(db, pn), snap(db, p9)

    result = M.apply_sale_deduction(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                    item_id=s.I1.id, quantity=3, delivery_id=55, account_id=s.AC1.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    assert reread(db, p).qty == 7
    # Then 3
    assert snap(db, p0) == before_p0
    # Then 4
    assert snap(db, pn) == before_pn
    # Then 5
    assert snap(db, p9) == before_p9


@xfail(BUG_2770)
def test_prdm_sd_21__for_sale_row_read_with_row_lock(db, s):
    """PRDM-SD-21 — the for-sale row is read with a row lock.
    Rules: apply_sale_deduction R7 [BUG-2770]; HR-10."""
    p = mk(db, s, for_sale=True, qty=10)
    db.expire_all()
    prod_id, ws_id, u_id, f_id, i_id, ac_id = p.id, s.W1.id, s.U2.id, s.F1.id, s.I1.id, s.AC1.id

    with record(db) as rec:
        result = M.apply_sale_deduction(db, workspace_id=ws_id, user_id=u_id, factory_id=f_id,
                                        item_id=i_id, quantity=3, delivery_id=55, account_id=ac_id)

    # Then 1
    assert result.id == prod_id
    # Then 2
    assert not any("SKIP LOCKED" in s_ for s_ in rec.psel)
    # Then 3
    assert not any("NOWAIT" in s_ for s_ in rec.psel)
    # Then 4
    assert any("FOR UPDATE" in s_ for s_ in rec.psel)


def test_prdm_sd_22__deduction_flushed_not_committed(db, s):
    """PRDM-SD-22 — the deduction is flushed but not committed.
    Rules: apply_sale_deduction Side effects ("flushed")."""
    p = mk(db, s, for_sale=True, qty=10)
    db.expire_all()

    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as spy:
        result = M.apply_sale_deduction(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                        item_id=s.I1.id, quantity=3, delivery_id=55, account_id=s.AC1.id)

        # Then 1
        assert result.id == p.id
        # Then 2
        assert count(db, ProductLedger) == 1
        # Then 3
        assert count(db, Product, Product.qty == 7) == 1
        sp.rollback()
        # Then 4
        assert count(db, ProductLedger) == 0
        # Then 5
        assert count(db, Product, Product.qty == 10) == 1
        # Then 6
        spy.assert_not_called()


def test_prdm_sd_23__delivery_of_one_unit_accepted(db, s):
    """PRDM-SD-23 — a delivery of one unit is accepted.
    Rules: apply_sale_deduction R1 (other side of <= 0), R5, R6."""
    p = mk(db, s, for_sale=True, qty=10, avg_cost=Decimal("4.00"))
    db.expire_all()

    result = M.apply_sale_deduction(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                    item_id=s.I1.id, quantity=1, delivery_id=55, account_id=s.AC1.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    assert reread(db, p).qty == 9
    # Then 3
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 4
    assert e.quantity == 1
    assert e.qty_before == 10
    assert e.qty_after == 9
    assert e.total_cost == Decimal("4.00")


def test_prdm_sd_24__delivery_at_average_in_cents_exact_total(db, s):
    """PRDM-SD-24 — a delivery at an average in cents records an exact total.
    Rules: apply_sale_deduction R6 (total_cost = avg × quantity, not rounded to whole units)."""
    p = mk(db, s, for_sale=True, qty=10, avg_cost=Decimal("4.35"))
    db.expire_all()

    result = M.apply_sale_deduction(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                    item_id=s.I1.id, quantity=3, delivery_id=55, account_id=s.AC1.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 3
    assert e.unit_cost == Decimal("4.35")
    assert e.total_cost == Decimal("13.05")
    assert e.avg_cost_before == Decimal("4.35")
    assert e.avg_cost_after == Decimal("4.35")


# --------------------------------------------------------------------------- #
# apply_sale_return (quantities, labels, notes)
# --------------------------------------------------------------------------- #

def test_prdm_sr_01__customer_return_adds_units(db, s):
    """PRDM-SR-01 — a customer return adds units to the for-sale bucket.
    Rules: apply_sale_return R4, R5 (quantity), R7 (parts that hold today)."""
    p = mk(db, s, for_sale=True, qty=7)
    db.expire_all()

    result = M.apply_sale_return(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                 item_id=s.I1.id, quantity=2, return_id=12, account_id=s.AC1.id,
                                 notes="Return SR-4 for SO-7")

    # Then 1
    assert result.id == p.id
    # Then 2
    row = reread(db, p)
    assert row.qty == 9
    assert row.is_available_for_sale is True
    assert row.updated_by == s.U2.id
    # Then 3
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 4
    assert e.transaction_type == "return"
    assert e.quantity == 2
    assert e.qty_before == 7
    assert e.qty_after == 9
    # Then 5
    assert e.source_id == 12
    assert e.notes == "Return SR-4 for SO-7"
    assert e.performed_by == s.U2.id
    assert e.workspace_id == s.W1.id


@xfail(BUG_2783)
def test_prdm_sr_02__return_row_labelled_as_from_customer(db, s):
    """PRDM-SR-02 — the return row is labelled as coming from the customer.
    Rules: apply_sale_return R7 [BUG-2783]."""
    p = mk(db, s, for_sale=True, qty=7)
    db.expire_all()

    result = M.apply_sale_return(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                 item_id=s.I1.id, quantity=2, return_id=12, account_id=s.AC1.id,
                                 notes="Return SR-4 for SO-7")

    # Then 1
    assert result.id == p.id
    # Then 2
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 3
    assert e.source_type == "sales_return"
    # Then 4
    assert e.transfer_source_type == "customer"
    assert e.transfer_source_id == s.AC1.id
    # Then 5
    assert e.transfer_destination_type is None
    assert e.transfer_destination_id is None


def test_prdm_sr_03__no_for_sale_row_one_created_and_filled(db, s):
    """PRDM-SR-03 — no for-sale row: one is created and filled.
    Rules: apply_sale_return R4 (created), R5 (quantity)."""
    result = M.apply_sale_return(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                 item_id=s.I1.id, quantity=2, return_id=12, account_id=s.AC1.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == s.W1.id
    assert row.factory_id == s.F1.id
    assert row.item_id == s.I1.id
    assert row.is_available_for_sale is True
    assert row.qty == 2
    # Then 3
    assert row.created_by == s.U2.id
    assert row.is_deleted is False
    # Then 4
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 5
    assert e.qty_before == 0
    assert e.qty_after == 2
    assert e.quantity == 2


def test_prdm_sr_04__whole_decimal_quantity_used_as_whole_units(db, s):
    """PRDM-SR-04 — a whole Decimal quantity is used as whole units.
    Rules: apply_sale_return R2."""
    p = mk(db, s, for_sale=True, qty=7)
    db.expire_all()

    result = M.apply_sale_return(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                 item_id=s.I1.id, quantity=Decimal("2.00"), return_id=12, account_id=s.AC1.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    assert reread(db, p).qty == 9
    # Then 3
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    # Then 4
    assert entries[0].quantity == 2


def test_prdm_sr_05__zero_quantity_refused(db, s):
    """PRDM-SR-05 — zero quantity is refused.
    Rules: apply_sale_return R1, Errors."""
    p = mk(db, s, for_sale=True, qty=7)
    db.expire_all()
    before = counts(db)
    before_p = snap(db, p)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.apply_sale_return(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                            item_id=s.I1.id, quantity=0, return_id=12, account_id=s.AC1.id)
    # Then 2
    assert str(exc.value) == "Sale return quantity must be positive"
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert counts(db) == before
    # Then 5
    assert snap(db, p) == before_p


def test_prdm_sr_06__negative_quantity_refused_no_bucket(db, s):
    """PRDM-SR-06 — a negative quantity is refused, also with no bucket.
    Rules: apply_sale_return R1."""
    before = counts(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.apply_sale_return(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                            item_id=s.I1.id, quantity=-1, return_id=12, account_id=s.AC1.id)
    # Then 2
    assert str(exc.value) == "Sale return quantity must be positive"
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert counts(db) == before


def test_prdm_sr_07__fractional_quantity_refused_no_bucket_created(db, s):
    """PRDM-SR-07 — a fractional quantity is refused, and no bucket is created.
    Rules: apply_sale_return R3, Errors."""
    before = counts(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.apply_sale_return(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                            item_id=s.I1.id, quantity=Decimal("1.5"), return_id=12, account_id=s.AC1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Return line has a fractional quantity; stock requires whole units"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before


def test_prdm_sr_08__no_notes_default_return_note(db, s):
    """PRDM-SR-08 — no notes give the default return note.
    Rules: apply_sale_return R7 (default notes)."""
    p = mk(db, s, for_sale=True, qty=7)
    db.expire_all()

    result = M.apply_sale_return(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                 item_id=s.I1.id, quantity=2, return_id=12, account_id=s.AC1.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    # Then 3
    assert entries[0].notes == "SYSTEM - SALES RETURN | return id 12"


def test_prdm_sr_09__empty_notes_default_return_note(db, s):
    """PRDM-SR-09 — empty notes also give the default return note.
    Rules: apply_sale_return R7 (notes falsy)."""
    p = mk(db, s, for_sale=True, qty=7)
    db.expire_all()

    result = M.apply_sale_return(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                 item_id=s.I1.id, quantity=2, return_id=13, account_id=s.AC1.id, notes="")

    # Then 1
    assert result.id == p.id
    # Then 2
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    # Then 3
    assert entries[0].notes == "SYSTEM - SALES RETURN | return id 13"


def test_prdm_sr_10__not_for_sale_row_never_used(db, s):
    """PRDM-SR-10 — the not-for-sale row is never used.
    Rules: apply_sale_return R4 (for-sale bucket only)."""
    pn = mk(db, s, qty=10)
    db.expire_all()
    before_pn = snap(db, pn)

    result = M.apply_sale_return(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                 item_id=s.I1.id, quantity=2, return_id=12, account_id=s.AC1.id)

    # Then 1
    assert result.id != pn.id
    # Then 2
    row = reread(db, result)
    assert row.is_available_for_sale is True
    assert row.qty == 2
    # Then 3
    assert snap(db, pn) == before_pn


def test_prdm_sr_11__for_sale_rows_of_w0_w2_neither_used_nor_touched(db, s):
    """PRDM-SR-11 — for-sale rows of the same key in W0 and W2 are neither used nor touched.
    Rules: apply_sale_return R4 (workspace in the key); HR-16."""
    p0 = mk(db, s, workspace_id=s.W0.id, for_sale=True, qty=10)
    p9 = mk(db, s, workspace_id=s.W2.id, for_sale=True, qty=10)
    db.expire_all()
    before_p0, before_p9 = snap(db, p0), snap(db, p9)

    result = M.apply_sale_return(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                 item_id=s.I1.id, quantity=2, return_id=12, account_id=s.AC1.id)

    # Then 1
    assert result.id != p0.id
    assert result.id != p9.id
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == s.W1.id
    assert row.qty == 2
    # Then 3
    assert snap(db, p0) == before_p0
    # Then 4
    assert snap(db, p9) == before_p9


def test_prdm_sr_12__two_lines_one_item_two_rows_same_source(db, s):
    """PRDM-SR-12 — two lines of one item on one return give two rows with the same source.
    Rules: apply_sale_return R8."""
    p = mk(db, s, for_sale=True, qty=7)
    M.apply_sale_return(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                        item_id=s.I1.id, quantity=2, return_id=12, account_id=s.AC1.id)
    db.expire_all()

    result = M.apply_sale_return(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                 item_id=s.I1.id, quantity=3, return_id=12, account_id=s.AC1.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    assert reread(db, p).qty == 12
    # Then 3
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 2
    # Then 4
    assert [e.source_id for e in entries] == [12, 12]
    assert [e.qty_after for e in entries] == [9, 12]


@xfail(BUG_1336)
def test_prdm_sr_13__soft_deleted_for_sale_row_restored_and_added_to(db, s):
    """PRDM-SR-13 — a soft-deleted for-sale row is restored and added to.
    Rules: apply_sale_return R4 [BUG-1336]."""
    p = mk(db, s, for_sale=True, deleted=True, qty=4, avg_cost=Decimal("3.00"))
    db.expire_all()

    result = M.apply_sale_return(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                 item_id=s.I1.id, quantity=2, return_id=12, account_id=s.AC1.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    row = reread(db, p)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 3
    assert row.qty == 6
    assert row.avg_cost == Decimal("3.00")
    assert row.updated_by == s.U2.id
    assert row.is_available_for_sale is True
    # Then 4
    assert count(db, Product) == 1
    # Then 5
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 6
    assert e.qty_before == 4
    assert e.qty_after == 6


@xfail(BUG_2770)
def test_prdm_sr_14__for_sale_row_read_with_row_lock(db, s):
    """PRDM-SR-14 — the for-sale row is read with a row lock.
    Rules: apply_sale_return R9 [BUG-2770]; HR-10."""
    p = mk(db, s, for_sale=True, qty=7)
    db.expire_all()
    prod_id, ws_id, u_id, f_id, i_id, ac_id = p.id, s.W1.id, s.U2.id, s.F1.id, s.I1.id, s.AC1.id

    with record(db) as rec:
        result = M.apply_sale_return(db, workspace_id=ws_id, user_id=u_id, factory_id=f_id,
                                     item_id=i_id, quantity=2, return_id=12, account_id=ac_id)

    # Then 1
    assert result.id == prod_id
    # Then 2
    assert not any("SKIP LOCKED" in s_ for s_ in rec.psel)
    # Then 3
    assert not any("NOWAIT" in s_ for s_ in rec.psel)
    # Then 4
    assert any("FOR UPDATE" in s_ for s_ in rec.psel)


def test_prdm_sr_15__return_flushed_not_committed(db, s):
    """PRDM-SR-15 — the return is flushed but not committed.
    Rules: apply_sale_return Side effects ("flushed")."""
    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as spy:
        result = M.apply_sale_return(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                     item_id=s.I1.id, quantity=2, return_id=12, account_id=s.AC1.id)

        # Then 1
        assert result.id is not None
        # Then 2
        assert count(db, Product) == 1
        # Then 3
        assert count(db, ProductLedger) == 1
        sp.rollback()
        # Then 4
        assert count(db, Product) == 0
        # Then 5
        assert count(db, ProductLedger) == 0
        # Then 6
        spy.assert_not_called()


def test_prdm_sr_30__negative_fraction_refused_as_not_positive(db, s):
    """PRDM-SR-30 — a negative fraction is refused as not positive, before the fraction check.
    Rules: apply_sale_return R1 (G6: checked before R3)."""
    p = mk(db, s, for_sale=True, qty=7)
    db.expire_all()
    before = counts(db)
    before_p = snap(db, p)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.apply_sale_return(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                            item_id=s.I1.id, quantity=Decimal("-0.5"), return_id=12, account_id=s.AC1.id)
    # Then 2
    assert str(exc.value) == "Sale return quantity must be positive"
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert counts(db) == before
    # Then 5
    assert snap(db, p) == before_p


def test_prdm_sr_31__return_of_one_unit_accepted(db, s):
    """PRDM-SR-31 — a return of one unit is accepted.
    Rules: apply_sale_return R1 (other side of <= 0), R5."""
    p = mk(db, s, for_sale=True, qty=7)
    db.expire_all()

    result = M.apply_sale_return(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                 item_id=s.I1.id, quantity=1, return_id=12, account_id=s.AC1.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    assert reread(db, p).qty == 8
    # Then 3
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 4
    assert e.quantity == 1
    assert e.qty_before == 7
    assert e.qty_after == 8


# --------------------------------------------------------------------------- #
# apply_production_output — costed output (OQ-50: intended for now, revisit after launch)
# --------------------------------------------------------------------------- #

def test_prdm_po_17__costed_output_weighted_into_average(db, s):
    """PRDM-PO-17 — a costed output is weighted into the average.
    Rules: apply_production_output R5, R8 (OQ-50, revisit after launch)."""
    p = mk(db, s, qty=10, avg_cost=Decimal("5.00"))
    db.expire_all()

    result = M.apply_production_output(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                       item_id=s.I1.id, quantity=10, batch_id=77, unit_cost=Decimal("6.00"))

    # Then 1
    assert result.id == p.id
    # Then 2
    row = reread(db, p)
    assert row.qty == 20
    assert row.avg_cost == Decimal("5.50")
    # Then 3
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 4
    assert e.unit_cost == Decimal("6.00")
    assert e.total_cost == Decimal("60.00")
    assert e.avg_cost_before == Decimal("5.00")
    assert e.avg_cost_after == Decimal("5.50")
    # Then 5
    assert e.qty_before == 10
    assert e.qty_after == 20
    assert e.quantity == 10


@xfail(BUG_1040)
def test_prdm_po_18__half_cent_average_rounds_half_up(db, s):
    """PRDM-PO-18 — a weighted average at an exact half cent rounds half up.
    Rules: apply_production_output R5 [BUG-1040] (OQ-50, revisit after launch); HR-15."""
    p = mk(db, s, qty=3, avg_cost=Decimal("1.00"))
    db.expire_all()

    result = M.apply_production_output(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                       item_id=s.I1.id, quantity=1, batch_id=77, unit_cost=Decimal("1.50"))

    # Then 1
    assert result.id == p.id
    # Then 2
    assert reread(db, p).avg_cost == Decimal("1.13")
    # Then 3
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    # Then 4
    assert entries[0].avg_cost_after == Decimal("1.13")


def test_prdm_po_19__non_half_cent_average_rounds_to_nearest(db, s):
    """PRDM-PO-19 — a weighted average that is not a half cent rounds to the nearest cent.
    Rules: apply_production_output R5, R8 (OQ-50, revisit after launch)."""
    p = mk(db, s, qty=2, avg_cost=Decimal("1.00"))
    db.expire_all()

    result = M.apply_production_output(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                       item_id=s.I1.id, quantity=1, batch_id=77, unit_cost=Decimal("1.50"))

    # Then 1
    assert result.id == p.id
    # Then 2
    row = reread(db, p)
    assert row.qty == 3
    assert row.avg_cost == Decimal("1.17")
    # Then 3
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 4
    assert e.unit_cost == Decimal("1.50")
    assert e.total_cost == Decimal("1.50")
    assert e.avg_cost_before == Decimal("1.00")
    assert e.avg_cost_after == Decimal("1.17")


@xfail(BUG_2811)
def test_prdm_po_20__costed_output_into_new_bucket_takes_unit_cost(db, s):
    """PRDM-PO-20 — a costed output into a new bucket takes the unit cost and records no cost before.
    Rules: apply_production_output R2 (avg_cost = unit_cost), R6, R8, R8a [BUG-2811] (OQ-50, revisit after launch)."""
    result = M.apply_production_output(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                       item_id=s.I1.id, quantity=4, batch_id=77, unit_cost=Decimal("6.00"))

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.qty == 4
    assert row.avg_cost == Decimal("6.00")
    assert row.is_available_for_sale is False
    # Then 3
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 4
    assert e.unit_cost == Decimal("6.00")
    assert e.total_cost == Decimal("24.00")
    assert e.avg_cost_before is None
    assert e.avg_cost_after == Decimal("6.00")


def test_prdm_po_21__empty_bucket_with_old_average_revalued(db, s):
    """PRDM-PO-21 — an empty bucket with an old average is revalued at the unit cost.
    Rules: apply_production_output R6 (old qty 0) (OQ-50, revisit after launch)."""
    p = mk(db, s, qty=0, avg_cost=Decimal("9.00"))
    db.expire_all()

    result = M.apply_production_output(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                       item_id=s.I1.id, quantity=4, batch_id=77, unit_cost=Decimal("6.00"))

    # Then 1
    assert result.id == p.id
    # Then 2
    row = reread(db, p)
    assert row.qty == 4
    assert row.avg_cost == Decimal("6.00")
    # Then 3
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 4
    assert e.avg_cost_before == Decimal("9.00")
    assert e.avg_cost_after == Decimal("6.00")


def test_prdm_po_22__stock_without_average_revalued(db, s):
    """PRDM-PO-22 — a bucket with stock but no average is revalued at the unit cost.
    Rules: apply_production_output R6 (old avg_cost None) (OQ-50, revisit after launch)."""
    p = mk(db, s)
    db.expire_all()

    result = M.apply_production_output(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                       item_id=s.I1.id, quantity=4, batch_id=77, unit_cost=Decimal("6.00"))

    # Then 1
    assert result.id == p.id
    # Then 2
    row = reread(db, p)
    assert row.qty == 9
    assert row.avg_cost == Decimal("6.00")
    # Then 3
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 4
    assert e.avg_cost_before is None
    assert e.avg_cost_after == Decimal("6.00")
    assert e.total_cost == Decimal("24.00")


def test_prdm_po_23__negative_bucket_revalued(db, s):
    """PRDM-PO-23 — a negative bucket is revalued at the unit cost.
    Rules: apply_production_output R6 (old qty negative) (OQ-50, revisit after launch)."""
    p = mk(db, s, qty=-2, avg_cost=Decimal("5.00"))
    db.expire_all()

    result = M.apply_production_output(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                       item_id=s.I1.id, quantity=4, batch_id=77, unit_cost=Decimal("6.00"))

    # Then 1
    assert result.id == p.id
    # Then 2
    row = reread(db, p)
    assert row.qty == 2
    assert row.avg_cost == Decimal("6.00")
    # Then 3
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 4
    assert e.avg_cost_before == Decimal("5.00")
    assert e.avg_cost_after == Decimal("6.00")


def test_prdm_po_24__zero_unit_cost_is_a_cost(db, s):
    """PRDM-PO-24 — a zero unit cost is a cost: weighted in, total 0.00.
    Rules: apply_production_output R5, R8 (OQ-50, revisit after launch)."""
    p = mk(db, s, qty=10, avg_cost=Decimal("5.00"))
    db.expire_all()

    result = M.apply_production_output(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                       item_id=s.I1.id, quantity=10, batch_id=77, unit_cost=Decimal("0.00"))

    # Then 1
    assert result.id == p.id
    # Then 2
    row = reread(db, p)
    assert row.qty == 20
    assert row.avg_cost == Decimal("2.50")
    # Then 3
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 4
    assert e.unit_cost == Decimal("0.00")
    assert e.total_cost == Decimal("0.00")
    assert e.avg_cost_after == Decimal("2.50")


def test_prdm_po_25__old_average_0_with_stock_weighted(db, s):
    """PRDM-PO-25 — an old average of 0.00 with stock is weighted as a real cost.
    Rules: apply_production_output R5, R8 (OQ-50, revisit after launch; G1)."""
    p = mk(db, s, qty=10, avg_cost=Decimal("0.00"))
    db.expire_all()

    result = M.apply_production_output(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                       item_id=s.I1.id, quantity=10, batch_id=77, unit_cost=Decimal("6.00"))

    # Then 1
    assert result.id == p.id
    # Then 2
    row = reread(db, p)
    assert row.qty == 20
    assert row.avg_cost == Decimal("3.00")
    # Then 3
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 4
    assert e.avg_cost_before == Decimal("0.00")
    assert e.avg_cost_after == Decimal("3.00")
    assert e.unit_cost == Decimal("6.00")
    assert e.total_cost == Decimal("60.00")


def test_prdm_po_26__costed_output_into_new_bucket_what_holds_today(db, s):
    """PRDM-PO-26 — a costed output into a new bucket: what holds today besides the cost before.
    Rules: apply_production_output R2, R6, R8 (the parts of PO-20 that hold today and after BUG-2811)."""
    result = M.apply_production_output(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                       item_id=s.I1.id, quantity=4, batch_id=77, unit_cost=Decimal("6.00"))

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.qty == 4
    assert row.avg_cost == Decimal("6.00")
    assert row.is_available_for_sale is False
    # Then 3
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 4
    assert e.unit_cost == Decimal("6.00")
    assert e.total_cost == Decimal("24.00")
    assert e.avg_cost_after == Decimal("6.00")
    assert e.qty_before == 0
    assert e.qty_after == 4


@xfail(BUG_1336)
def test_prdm_po_27__restored_bucket_not_new_kept_average_is_cost_before(db, s):
    """PRDM-PO-27 — a restored soft-deleted bucket is not new: its kept average is the cost before.
    Rules: apply_production_output R2a [BUG-1336], R5, R8a (a restored row is not new)."""
    p = mk(db, s, deleted=True, qty=6, avg_cost=Decimal("3.00"))
    db.expire_all()

    result = M.apply_production_output(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                       item_id=s.I1.id, quantity=4, batch_id=77, unit_cost=Decimal("6.00"))

    # Then 1
    assert result.id == p.id
    # Then 2
    row = reread(db, p)
    assert row.qty == 10
    assert row.avg_cost == Decimal("4.20")
    assert row.is_deleted is False
    # Then 3
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 4
    assert e.qty_before == 6
    assert e.qty_after == 10
    assert e.avg_cost_before == Decimal("3.00")
    assert e.avg_cost_after == Decimal("4.20")
    assert e.unit_cost == Decimal("6.00")
    assert e.total_cost == Decimal("24.00")


def test_prdm_po_28__old_stock_of_1_weighted_not_revalued(db, s):
    """PRDM-PO-28 — an old stock of 1 is weighted, not revalued.
    Rules: apply_production_output R5 (old qty > 0 at its smallest), R8 (OQ-50, revisit after launch)."""
    p = mk(db, s, qty=1, avg_cost=Decimal("2.00"))
    db.expire_all()

    result = M.apply_production_output(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                       item_id=s.I1.id, quantity=3, batch_id=77, unit_cost=Decimal("4.00"))

    # Then 1
    assert result.avg_cost == Decimal("3.50")
    # Then 2
    row = reread(db, p)
    assert row.qty == 4
    assert row.avg_cost == Decimal("3.50")
    # Then 3
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 4
    assert e.avg_cost_before == Decimal("2.00")
    assert e.avg_cost_after == Decimal("3.50")
    assert e.total_cost == Decimal("12.00")


def test_prdm_po_29__average_third_decimal_below_5_rounds_down(db, s):
    """PRDM-PO-29 — an average whose third decimal is below 5 rounds down, also in the session.
    Rules: apply_production_output R5 (rounded to 2 places), R8 (OQ-50, revisit after launch)."""
    p = mk(db, s, qty=2, avg_cost=Decimal("1.00"))
    db.expire_all()

    result = M.apply_production_output(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                       item_id=s.I1.id, quantity=1, batch_id=77, unit_cost=Decimal("2.00"))

    # Then 1
    assert result.avg_cost == Decimal("1.33")
    # Then 2
    row = reread(db, p)
    assert row.qty == 3
    assert row.avg_cost == Decimal("1.33")
    # Then 3
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 4
    assert e.avg_cost_before == Decimal("1.00")
    assert e.avg_cost_after == Decimal("1.33")
    assert e.unit_cost == Decimal("2.00")
    assert e.total_cost == Decimal("2.00")


# --------------------------------------------------------------------------- #
# update_product — flipping the for-sale flag (R9 [BUG-2793], R10)
# --------------------------------------------------------------------------- #

@xfail(BUG_2793)
def test_prdm_u_40__flip_of_stocked_row_to_for_sale_refused(db, s):
    """PRDM-U-40 — flipping a row that holds stock to for sale is refused.
    Rules: update_product R9 [BUG-2793]; Errors row 3."""
    p = mk(db, s, avg_cost=Decimal("10.00"))
    db.expire_all()
    before = counts(db)
    before_p = snap(db, p)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_product(db, prod_id=p.id, data=ProductUpdate(is_available_for_sale=True),
                         workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Product record holds stock — use Make sellable to move units"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before
    # Then 6
    assert snap(db, p) == before_p


@xfail(BUG_2793)
def test_prdm_u_41__flip_of_stocked_for_sale_row_back_refused(db, s):
    """PRDM-U-41 — flipping a stocked for-sale row back is refused too.
    Rules: update_product R9 [BUG-2793] (either direction)."""
    p = mk(db, s, for_sale=True, avg_cost=Decimal("10.00"))
    db.expire_all()
    before = counts(db)
    before_p = snap(db, p)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_product(db, prod_id=p.id, data=ProductUpdate(is_available_for_sale=False),
                         workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Product record holds stock — use Make sellable to move units"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before
    # Then 6
    assert snap(db, p) == before_p


@xfail(BUG_2793)
def test_prdm_u_42__flip_with_new_quantity_refused_on_stocked_row(db, s):
    """PRDM-U-42 — a flip sent with a new quantity is refused on a stocked row.
    Rules: update_product R9 [BUG-2793] (a qty sent in the same call does not help)."""
    p = mk(db, s, avg_cost=Decimal("10.00"))
    db.expire_all()
    before = counts(db)
    before_p = snap(db, p)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_product(db, prod_id=p.id, data=ProductUpdate(is_available_for_sale=True, qty=8),
                         workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Product record holds stock — use Make sellable to move units"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before
    # Then 6
    assert snap(db, p) == before_p


def test_prdm_u_43__for_sale_rows_of_w0_w2_do_not_block_flip(db, s):
    """PRDM-U-43 — for-sale rows of the same key in W0 and W2 do not block a flip.
    Rules: update_product R9, R10 (workspace in the key); HR-16."""
    p0 = mk(db, s, workspace_id=s.W0.id, for_sale=True)
    p = mk(db, s, qty=0)
    p9 = mk(db, s, workspace_id=s.W2.id, for_sale=True)
    db.expire_all()
    before_p0, before_p9 = snap(db, p0), snap(db, p9)

    result = M.update_product(db, prod_id=p.id, data=ProductUpdate(is_available_for_sale=True),
                              workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    assert reread(db, p).is_available_for_sale is True
    # Then 3
    assert snap(db, p0) == before_p0
    # Then 4
    assert snap(db, p9) == before_p9


def test_prdm_u_44__for_sale_rows_of_other_factory_or_item_do_not_block(db, s):
    """PRDM-U-44 — for-sale rows of another factory or item do not block a flip.
    Rules: update_product R10 (key = factory and item)."""
    pa = mk(db, s, for_sale=True, factory_id=s.F2.id)
    p = mk(db, s, qty=0)
    pb = mk(db, s, for_sale=True, item_id=s.I2.id)
    db.expire_all()
    before_pa, before_pb = snap(db, pa), snap(db, pb)

    result = M.update_product(db, prod_id=p.id, data=ProductUpdate(is_available_for_sale=True),
                              workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    assert reread(db, p).is_available_for_sale is True
    # Then 3
    assert snap(db, pa) == before_pa
    # Then 4
    assert snap(db, pb) == before_pb


@xfail(BUG_2781)
def test_prdm_u_45__flip_onto_key_with_live_row_is_conflict(db, s):
    """PRDM-U-45 — flipping onto a key with a live row is a conflict.
    Rules: update_product R10 [BUG-2781], Errors row 4."""
    ps = mk(db, s, for_sale=True, qty=30)
    p = mk(db, s, qty=0)
    db.expire_all()
    before = counts(db)
    before_p, before_ps = snap(db, p), snap(db, ps)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_product(db, prod_id=p.id, data=ProductUpdate(is_available_for_sale=True),
                         workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Product record already exists for this item/factory/availability combination"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before
    # Then 6
    assert snap(db, p) == before_p
    # Then 7
    assert snap(db, ps) == before_ps


@xfail(BUG_2781)
def test_prdm_u_46__flip_onto_key_with_soft_deleted_row_is_conflict(db, s):
    """PRDM-U-46 — flipping onto a key with a soft-deleted row is a conflict.
    Rules: update_product R10 [BUG-2781]."""
    mk(db, s, for_sale=True, deleted=True, qty=0)
    p = mk(db, s, qty=0)
    db.expire_all()
    before = counts(db)
    before_p = snap(db, p)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_product(db, prod_id=p.id, data=ProductUpdate(is_available_for_sale=True),
                         workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Product record already exists for this item/factory/availability combination"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before
    # Then 6
    assert snap(db, p) == before_p


def test_prdm_u_47__row_at_0_flips_with_cost_no_ledger(db, s):
    """PRDM-U-47 — a row at 0 flips to for sale with its cost and no ledger row.
    Rules: update_product R9 (row at qty 0 flips)."""
    p = mk(db, s, qty=0, avg_cost=Decimal("10.00"))
    db.expire_all()

    result = M.update_product(db, prod_id=p.id, data=ProductUpdate(is_available_for_sale=True),
                              workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    row = reread(db, p)
    assert row.is_available_for_sale is True
    assert row.qty == 0
    assert row.avg_cost == Decimal("10.00")
    assert row.updated_by == s.U2.id
    # Then 3
    assert count(db, Product) == 1
    # Then 4
    assert count(db, ProductLedger) == 0


def test_prdm_u_48__for_sale_row_at_0_flips_back(db, s):
    """PRDM-U-48 — a for-sale row at 0 flips back.
    Rules: update_product R9 (row at qty 0, other direction)."""
    p = mk(db, s, for_sale=True, qty=0, avg_cost=Decimal("10.00"))
    db.expire_all()

    result = M.update_product(db, prod_id=p.id, data=ProductUpdate(is_available_for_sale=False),
                              workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    row = reread(db, p)
    assert row.is_available_for_sale is False
    assert row.qty == 0
    assert row.avg_cost == Decimal("10.00")
    # Then 3
    assert count(db, ProductLedger) == 0


def test_prdm_u_49__row_at_0_flipped_with_quantity_writes_only_adjustment(db, s):
    """PRDM-U-49 — a row at 0 flipped with a new quantity writes only the quantity adjustment.
    Rules: update_product R9, R7."""
    p = mk(db, s, qty=0, avg_cost=Decimal("10.00"))
    db.expire_all()

    result = M.update_product(db, prod_id=p.id, data=ProductUpdate(is_available_for_sale=True, qty=8),
                              workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    row = reread(db, p)
    assert row.is_available_for_sale is True
    assert row.qty == 8
    # Then 3
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 4
    assert e.transaction_type == "inventory_adjustment"
    assert e.quantity == 8
    assert e.qty_before == 0
    assert e.qty_after == 8
    # Then 5
    assert e.unit_cost == Decimal("10.00")
    assert e.total_cost == Decimal("80.00")
    assert e.notes == "Quantity adjusted from 0 to 8"


@xfail(BUG_2793)
def test_prdm_u_50__row_with_negative_stock_refused(db, s):
    """PRDM-U-50 — a row with negative stock is not "at 0" and is refused.
    Rules: update_product R9 [BUG-2793] (qty not 0)."""
    p = mk(db, s, qty=-2)
    db.expire_all()
    before = counts(db)
    before_p = snap(db, p)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_product(db, prod_id=p.id, data=ProductUpdate(is_available_for_sale=True),
                         workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Product record holds stock — use Make sellable to move units"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before
    # Then 6
    assert snap(db, p) == before_p


@xfail(BUG_2793)
def test_prdm_u_51__stocked_row_flipped_with_qty_0_still_refused(db, s):
    """PRDM-U-51 — a stocked row flipped with qty 0 sent is still refused (the stored qty decides).
    Rules: update_product R9 [BUG-2793]."""
    p = mk(db, s, qty=1)
    db.expire_all()
    before = counts(db)
    before_p = snap(db, p)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_product(db, prod_id=p.id, data=ProductUpdate(is_available_for_sale=True, qty=0),
                         workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Product record holds stock — use Make sellable to move units"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before
    # Then 6
    assert snap(db, p) == before_p


@xfail(BUG_2793)
def test_prdm_u_54__stocked_flip_onto_taken_key_gets_stock_refusal(db, s):
    """PRDM-U-54 — a stocked row flipped onto a taken key gets the stock refusal, not the conflict.
    Rules: update_product R10a (R9 before R10), R9 [BUG-2793]."""
    ps = mk(db, s, for_sale=True, qty=30)
    p = mk(db, s, avg_cost=Decimal("10.00"))
    db.expire_all()
    before = counts(db)
    before_p, before_ps = snap(db, p), snap(db, ps)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_product(db, prod_id=p.id, data=ProductUpdate(is_available_for_sale=True),
                         workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Product record holds stock — use Make sellable to move units"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before
    # Then 6
    assert snap(db, p) == before_p
    # Then 7
    assert snap(db, ps) == before_ps


# --------------------------------------------------------------------------- #
# apply_sale_return — cost of returned units (R5, R6; R6a [BUG-2794])
# --------------------------------------------------------------------------- #

def test_prdm_sr_16__returned_units_valued_at_current_average(db, s):
    """PRDM-SR-16 — returned units are valued at the bucket's current average, which is kept.
    Rules: apply_sale_return R5, R6."""
    p = mk(db, s, for_sale=True, qty=7, avg_cost=Decimal("4.00"))
    db.expire_all()

    result = M.apply_sale_return(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                 item_id=s.I1.id, quantity=2, return_id=12, account_id=s.AC1.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    assert reread(db, p).avg_cost == Decimal("4.00")
    # Then 3
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 4
    assert e.unit_cost == Decimal("4.00")
    assert e.total_cost == Decimal("8.00")
    assert e.avg_cost_before == Decimal("4.00")
    assert e.avg_cost_after == Decimal("4.00")


def test_prdm_sr_17__no_average_no_sale_return_has_no_cost(db, s):
    """PRDM-SR-17 — no average and no sale on record: the return has no cost.
    Rules: apply_sale_return R6a (no costed sale: as today)."""
    p = mk(db, s, for_sale=True, qty=7)
    db.expire_all()

    result = M.apply_sale_return(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                 item_id=s.I1.id, quantity=2, return_id=12, account_id=s.AC1.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    assert reread(db, p).avg_cost is None
    # Then 3
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 4
    assert e.unit_cost is None
    assert e.total_cost is None
    assert e.avg_cost_before is None
    assert e.avg_cost_after is None


def test_prdm_sr_18__bucket_created_by_return_no_sale_has_no_average(db, s):
    """PRDM-SR-18 — a bucket created by the return, with no sale on record, has no average.
    Rules: apply_sale_return R4 (avg_cost None), R6a (no costed sale)."""
    result = M.apply_sale_return(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                 item_id=s.I1.id, quantity=2, return_id=12, account_id=s.AC1.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, result).avg_cost is None
    # Then 3
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 4
    assert e.unit_cost is None
    assert e.total_cost is None


def test_prdm_sr_19__zero_average_total_0(db, s):
    """PRDM-SR-19 — a zero average records a total of 0.00.
    Rules: apply_sale_return R5, R6 (0.00 is an average: 0 -> 0.00)."""
    p = mk(db, s, for_sale=True, qty=7, avg_cost=Decimal("0.00"))
    db.expire_all()

    result = M.apply_sale_return(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                 item_id=s.I1.id, quantity=2, return_id=12, account_id=s.AC1.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 3
    assert e.unit_cost == Decimal("0.00")
    assert e.total_cost == Decimal("0.00")


@xfail(BUG_2794)
def test_prdm_sr_20__no_average_latest_sale_cost_used(db, s):
    """PRDM-SR-20 — no average: the latest sale's cost is used and becomes the average.
    Rules: apply_sale_return R6a [BUG-2794] (spec example)."""
    s1 = mk_sale(db, s, performed_at=T1, unit_cost=Decimal("50.00"))
    p = mk(db, s, for_sale=True, qty=0)
    db.expire_all()
    before_s1 = snap(db, s1)

    result = M.apply_sale_return(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                 item_id=s.I1.id, quantity=4, return_id=12, account_id=s.AC1.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    row = reread(db, p)
    assert row.qty == 4
    assert row.avg_cost == Decimal("50.00")
    # Then 3
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 2
    n = entries[-1]
    # Then 4
    assert n.transaction_type == "return"
    assert n.quantity == 4
    assert n.qty_before == 0
    assert n.qty_after == 4
    # Then 5
    assert n.unit_cost == Decimal("50.00")
    assert n.total_cost == Decimal("200.00")
    assert n.avg_cost_before is None
    assert n.avg_cost_after == Decimal("50.00")
    # Then 6
    assert snap(db, s1) == before_s1


@xfail(BUG_2794)
def test_prdm_sr_21__no_bucket_created_bucket_takes_latest_sale_cost(db, s):
    """PRDM-SR-21 — no bucket at all: the created bucket takes the latest sale's cost.
    Rules: apply_sale_return R4, R6a [BUG-2794]."""
    mk_sale(db, s, performed_at=T1, unit_cost=Decimal("50.00"))
    db.expire_all()

    result = M.apply_sale_return(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                 item_id=s.I1.id, quantity=4, return_id=12, account_id=s.AC1.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.qty == 4
    assert row.is_available_for_sale is True
    assert row.avg_cost == Decimal("50.00")
    # Then 3
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 2
    n = entries[-1]
    # Then 4
    assert n.unit_cost == Decimal("50.00")
    assert n.total_cost == Decimal("200.00")
    assert n.avg_cost_before is None
    assert n.avg_cost_after == Decimal("50.00")


@xfail(BUG_2794)
def test_prdm_sr_22__latest_sale_chosen_by_performed_at(db, s):
    """PRDM-SR-22 — the latest sale is chosen by performed_at, not by id.
    Rules: apply_sale_return R6a [BUG-2794] (latest = performed_at desc)."""
    mk_sale(db, s, performed_at=T2, unit_cost=Decimal("50.00"))
    mk_sale(db, s, performed_at=T1, unit_cost=Decimal("40.00"))
    p = mk(db, s, for_sale=True, qty=0)
    db.expire_all()

    result = M.apply_sale_return(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                 item_id=s.I1.id, quantity=4, return_id=12, account_id=s.AC1.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    assert reread(db, p).avg_cost == Decimal("50.00")
    # Then 3
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 3
    n = entries[-1]
    # Then 4
    assert n.unit_cost == Decimal("50.00")
    assert n.total_cost == Decimal("200.00")


@xfail(BUG_2794)
def test_prdm_sr_23__two_sales_at_one_time_higher_id_wins(db, s):
    """PRDM-SR-23 — two sales at one time: the higher id wins.
    Rules: apply_sale_return R6a [BUG-2794] (tie: id desc)."""
    mk_sale(db, s, performed_at=T1, unit_cost=Decimal("40.00"))
    mk_sale(db, s, performed_at=T1, unit_cost=Decimal("45.00"))
    p = mk(db, s, for_sale=True, qty=0)
    db.expire_all()

    result = M.apply_sale_return(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                 item_id=s.I1.id, quantity=4, return_id=12, account_id=s.AC1.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    assert reread(db, p).avg_cost == Decimal("45.00")
    # Then 3
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 3
    n = entries[-1]
    # Then 4
    assert n.unit_cost == Decimal("45.00")
    assert n.total_cost == Decimal("180.00")


@xfail(BUG_2794)
def test_prdm_sr_24__later_uncosted_sale_skipped(db, s):
    """PRDM-SR-24 — a later sale with no cost is skipped for the latest costed one.
    Rules: apply_sale_return R6a [BUG-2794] ("that has a unit_cost")."""
    mk_sale(db, s, performed_at=T1, unit_cost=Decimal("30.00"))
    mk_sale(db, s, performed_at=T2, unit_cost=None, avg_cost_before=None, avg_cost_after=None, total_cost=None)
    p = mk(db, s, for_sale=True, qty=0)
    db.expire_all()

    result = M.apply_sale_return(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                 item_id=s.I1.id, quantity=4, return_id=12, account_id=s.AC1.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    assert reread(db, p).avg_cost == Decimal("30.00")
    # Then 3
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 3
    n = entries[-1]
    # Then 4
    assert n.unit_cost == Decimal("30.00")
    assert n.total_cost == Decimal("120.00")


def test_prdm_sr_25__sales_of_w0_w2_do_not_give_cost(db, s):
    """PRDM-SR-25 — sales of the same key in W0 and W2 do not give a cost.
    Rules: apply_sale_return R6a (other workspace: as today); HR-16."""
    s0 = mk_sale(db, s, workspace_id=s.W0.id, performed_at=T1, unit_cost=Decimal("50.00"))
    p = mk(db, s, for_sale=True, qty=0)
    s9 = mk_sale(db, s, workspace_id=s.W2.id, performed_at=T2, unit_cost=Decimal("60.00"))
    db.expire_all()
    before_s0, before_s9 = snap(db, s0), snap(db, s9)

    result = M.apply_sale_return(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                 item_id=s.I1.id, quantity=4, return_id=12, account_id=s.AC1.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    row = reread(db, p)
    assert row.qty == 4
    assert row.avg_cost is None
    # Then 3
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 4
    assert e.unit_cost is None
    assert e.total_cost is None
    assert e.avg_cost_after is None
    # Then 5
    assert snap(db, s0) == before_s0
    # Then 6
    assert snap(db, s9) == before_s9


def test_prdm_sr_26__other_factory_item_or_non_sale_rows_do_not_give_cost(db, s):
    """PRDM-SR-26 — sales of another factory or item, and non-sale rows of the key, do not give a cost.
    Rules: apply_sale_return R6a (only sale rows of this factory and item)."""
    mk_sale(db, s, factory_id=s.F2.id, performed_at=T1, unit_cost=Decimal("50.00"))
    mk_sale(db, s, item_id=s.I2.id, performed_at=T1, unit_cost=Decimal("51.00"))
    mk_sale(db, s, transaction_type="production", source_type="production_batch", performed_at=T2,
            unit_cost=Decimal("52.00"))
    p = mk(db, s, for_sale=True, qty=0)
    db.expire_all()

    result = M.apply_sale_return(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                 item_id=s.I1.id, quantity=4, return_id=12, account_id=s.AC1.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    row = reread(db, p)
    assert row.qty == 4
    assert row.avg_cost is None
    # Then 3
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 2
    n = entries[-1]
    # Then 4
    assert n.transaction_type == "return"
    assert n.unit_cost is None
    assert n.total_cost is None
    assert n.avg_cost_after is None


def test_prdm_sr_27__bucket_own_average_wins_over_last_sale(db, s):
    """PRDM-SR-27 — a bucket's own average wins over the last sale's cost.
    Rules: apply_sale_return R5, R6 (average set: no fallback)."""
    mk_sale(db, s, performed_at=T1, unit_cost=Decimal("50.00"))
    p = mk(db, s, for_sale=True, qty=7, avg_cost=Decimal("4.00"))
    db.expire_all()

    result = M.apply_sale_return(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                 item_id=s.I1.id, quantity=4, return_id=12, account_id=s.AC1.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    row = reread(db, p)
    assert row.qty == 11
    assert row.avg_cost == Decimal("4.00")
    # Then 3
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 2
    n = entries[-1]
    # Then 4
    assert n.unit_cost == Decimal("4.00")
    assert n.total_cost == Decimal("16.00")
    assert n.avg_cost_before == Decimal("4.00")
    assert n.avg_cost_after == Decimal("4.00")


def test_prdm_sr_28__average_0_is_an_average_last_sale_not_used(db, s):
    """PRDM-SR-28 — an average of 0.00 is an average: the last sale's cost is not used.
    Rules: apply_sale_return R5, R6 (0.00 counts)."""
    mk_sale(db, s, performed_at=T1, unit_cost=Decimal("50.00"))
    p = mk(db, s, for_sale=True, qty=7, avg_cost=Decimal("0.00"))
    db.expire_all()

    result = M.apply_sale_return(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                 item_id=s.I1.id, quantity=4, return_id=12, account_id=s.AC1.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    assert reread(db, p).avg_cost == Decimal("0.00")
    # Then 3
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 2
    n = entries[-1]
    # Then 4
    assert n.unit_cost == Decimal("0.00")
    assert n.total_cost == Decimal("0.00")
    assert n.avg_cost_after == Decimal("0.00")


@xfail("BUG-2794, BUG-1336")
def test_prdm_sr_29__restored_uncosted_bucket_takes_latest_sale_cost(db, s):
    """PRDM-SR-29 — a restored uncosted bucket takes the latest sale's cost.
    Rules: apply_sale_return R4 [BUG-1336], R6a [BUG-2794] (needs both fixes)."""
    mk_sale(db, s, performed_at=T1, unit_cost=Decimal("50.00"))
    p = mk(db, s, for_sale=True, deleted=True, qty=0)
    db.expire_all()

    result = M.apply_sale_return(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                 item_id=s.I1.id, quantity=4, return_id=12, account_id=s.AC1.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    row = reread(db, p)
    assert row.is_deleted is False
    assert row.qty == 4
    assert row.avg_cost == Decimal("50.00")
    # Then 3
    assert count(db, Product) == 1
    # Then 4
    n = ledger_of(db, s, s.F1, s.I1)[-1]
    assert n.unit_cost == Decimal("50.00")
    assert n.total_cost == Decimal("200.00")
    assert n.avg_cost_before is None


def test_prdm_sr_32__return_at_average_in_cents_exact_total(db, s):
    """PRDM-SR-32 — a return at an average in cents records an exact total.
    Rules: apply_sale_return R6 (total_cost = avg × quantity, not rounded to whole units)."""
    p = mk(db, s, for_sale=True, qty=7, avg_cost=Decimal("2.15"))
    db.expire_all()

    result = M.apply_sale_return(db, workspace_id=s.W1.id, user_id=s.U2.id, factory_id=s.F1.id,
                                 item_id=s.I1.id, quantity=3, return_id=12, account_id=s.AC1.id)

    # Then 1
    assert result.id == p.id
    # Then 2
    row = reread(db, p)
    assert row.qty == 10
    assert row.avg_cost == Decimal("2.15")
    # Then 3
    entries = ledger_of(db, s, s.F1, s.I1)
    assert len(entries) == 1
    e = entries[0]
    # Then 4
    assert e.unit_cost == Decimal("2.15")
    assert e.total_cost == Decimal("6.45")
    assert e.avg_cost_before == Decimal("2.15")
    assert e.avg_cost_after == Decimal("2.15")


# --------------------------------------------------------------------------- #
# make_sellable (new method, BUG-2793) — every card fails today at the call
# --------------------------------------------------------------------------- #

def mk_source(db, s, **overrides):
    """S = stock, but qty 10, avg_cost 5.00 (the not-for-sale source)."""
    return mk(db, s, **{"qty": 10, "avg_cost": Decimal("5.00"), **overrides})


def mk_target(db, s, **overrides):
    """T = stock, but for sale, qty 4, avg_cost 8.00 (the for-sale target)."""
    return mk(db, s, for_sale=True, **{"qty": 4, "avg_cost": Decimal("8.00"), **overrides})


@xfail(BUG_2793)
def test_prdm_ms_01__units_move_into_existing_target_weighted(db, s):
    """PRDM-MS-01 — units move into the existing for-sale bucket, weighted into its average.
    Rules: make_sellable M3, M4, M5, M8, Returns."""
    src = mk_source(db, s)
    tgt = mk_target(db, s)
    db.expire_all()

    result = M.make_sellable(db, prod_id=src.id, quantity=3, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == tgt.id
    # Then 2
    src_row = reread(db, src)
    assert src_row.qty == 7
    assert src_row.avg_cost == Decimal("5.00")
    assert src_row.is_available_for_sale is False
    assert src_row.updated_by == s.U2.id
    # Then 3
    tgt_row = reread(db, tgt)
    assert tgt_row.qty == 7
    assert tgt_row.avg_cost == Decimal("6.71")
    assert tgt_row.is_available_for_sale is True
    assert tgt_row.updated_by == s.U2.id
    # Then 4
    src_row, tgt_row = reread(db, src), reread(db, tgt)
    assert src_row.qty + tgt_row.qty == 14
    # Then 5
    assert count(db, Product) == 2
    # Then 6
    assert len(ledger_of(db, s, s.F1, s.I1)) == 2


@xfail(BUG_2793)
def test_prdm_ms_02__out_row_records_source_side(db, s):
    """PRDM-MS-02 — the out row records the source side and points at the target.
    Rules: make_sellable M6 (out row)."""
    src = mk_source(db, s)
    tgt = mk_target(db, s)
    db.expire_all()

    result = M.make_sellable(db, prod_id=src.id, quantity=3, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == tgt.id
    # Then 2
    out = out_row(db)
    assert out.transaction_type == "transfer"
    assert out.source_type == "make_sellable"
    assert out.source_id == tgt.id
    assert out.quantity == 3
    # Then 3
    assert out.qty_before == 10
    assert out.qty_after == 7
    # Then 4
    assert out.unit_cost == Decimal("5.00")
    assert out.total_cost == Decimal("15.00")
    assert out.avg_cost_before == Decimal("5.00")
    assert out.avg_cost_after == Decimal("5.00")
    # Then 5
    assert out.transfer_destination_type == "product"
    assert out.transfer_destination_id == tgt.id
    # Then 6
    assert out.notes == "Made sellable: 3 unit(s)"
    assert out.performed_by == s.U2.id
    assert out.workspace_id == s.W1.id
    assert out.factory_id == s.F1.id
    assert out.item_id == s.I1.id


@xfail(BUG_2793)
def test_prdm_ms_03__in_row_records_target_side(db, s):
    """PRDM-MS-03 — the in row records the target side and points at the source.
    Rules: make_sellable M5, M6 (in row)."""
    src = mk_source(db, s)
    tgt = mk_target(db, s)
    db.expire_all()

    result = M.make_sellable(db, prod_id=src.id, quantity=3, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == tgt.id
    # Then 2
    in_ = in_row(db)
    assert in_.transaction_type == "transfer"
    assert in_.source_type == "make_sellable"
    assert in_.source_id == src.id
    assert in_.quantity == 3
    # Then 3
    assert in_.qty_before == 4
    assert in_.qty_after == 7
    # Then 4
    assert in_.unit_cost == Decimal("5.00")
    assert in_.total_cost == Decimal("15.00")
    assert in_.avg_cost_before == Decimal("8.00")
    assert in_.avg_cost_after == Decimal("6.71")
    # Then 5
    assert in_.transfer_source_type == "product"
    assert in_.transfer_source_id == src.id
    # Then 6
    assert in_.notes == "Made sellable: 3 unit(s)"
    assert in_.performed_by == s.U2.id
    assert in_.workspace_id == s.W1.id


@xfail(BUG_2793)
def test_prdm_ms_04__half_cent_target_average_rounds_half_up(db, s):
    """PRDM-MS-04 — a weighted target average at an exact half cent rounds half up.
    Rules: make_sellable M5 (HR-15)."""
    src = mk(db, s, qty=5, avg_cost=Decimal("1.50"))
    tgt = mk(db, s, for_sale=True, qty=3, avg_cost=Decimal("1.00"))
    db.expire_all()

    result = M.make_sellable(db, prod_id=src.id, quantity=1, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == tgt.id
    # Then 2
    tgt_row = reread(db, tgt)
    assert tgt_row.qty == 4
    assert tgt_row.avg_cost == Decimal("1.13")
    # Then 3
    in_ = in_row(db)
    assert in_.avg_cost_after == Decimal("1.13")
    assert in_.unit_cost == Decimal("1.50")
    assert in_.total_cost == Decimal("1.50")


@xfail(BUG_2793)
def test_prdm_ms_05__average_below_half_cent_rounds_down(db, s):
    """PRDM-MS-05 — a weighted average below a half cent rounds down.
    Rules: make_sellable M5 (rounding, other side)."""
    src = mk(db, s, qty=5, avg_cost=Decimal("1.50"))
    tgt = mk(db, s, for_sale=True, qty=2, avg_cost=Decimal("1.00"))
    db.expire_all()

    result = M.make_sellable(db, prod_id=src.id, quantity=1, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == tgt.id
    # Then 2
    tgt_row = reread(db, tgt)
    assert tgt_row.qty == 3
    assert tgt_row.avg_cost == Decimal("1.17")


@xfail(BUG_2793)
def test_prdm_ms_06__no_for_sale_row_target_created_with_source_average(db, s):
    """PRDM-MS-06 — no for-sale row: the target is created with the source average.
    Rules: make_sellable M3 (created), M5."""
    src = mk_source(db, s)
    db.expire_all()

    result = M.make_sellable(db, prod_id=src.id, quantity=3, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id != src.id
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == s.W1.id
    assert row.factory_id == s.F1.id
    assert row.item_id == s.I1.id
    assert row.is_available_for_sale is True
    # Then 3
    assert row.qty == 3
    assert row.avg_cost == Decimal("5.00")
    assert row.created_by == s.U2.id
    assert row.is_deleted is False
    # Then 4
    assert reread(db, src).qty == 7
    # Then 5
    assert count(db, Product) == 2
    # Then 6
    in_ = in_row(db)
    assert in_.qty_before == 0
    assert in_.qty_after == 3
    assert in_.avg_cost_before is None
    assert in_.avg_cost_after == Decimal("5.00")
    assert in_.transfer_source_id == src.id
    # Then 7
    out = out_row(db)
    assert out.transfer_destination_id == result.id
    assert out.source_id == result.id


@xfail(BUG_2793)
def test_prdm_ms_07__empty_target_with_old_average_takes_source_average(db, s):
    """PRDM-MS-07 — an empty target with an old average takes the source average.
    Rules: make_sellable M5 (target qty 0: otherwise branch)."""
    src = mk_source(db, s)
    tgt = mk_target(db, s, qty=0, avg_cost=Decimal("9.00"))
    db.expire_all()

    result = M.make_sellable(db, prod_id=src.id, quantity=3, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == tgt.id
    # Then 2
    tgt_row = reread(db, tgt)
    assert tgt_row.qty == 3
    assert tgt_row.avg_cost == Decimal("5.00")
    # Then 3
    in_ = in_row(db)
    assert in_.avg_cost_before == Decimal("9.00")
    assert in_.avg_cost_after == Decimal("5.00")


@xfail(BUG_2793)
def test_prdm_ms_08__stocked_target_without_average_takes_source_average(db, s):
    """PRDM-MS-08 — a target holding stock with no average takes the source average.
    Rules: make_sellable M5 (target average None)."""
    src = mk_source(db, s)
    tgt = mk_target(db, s, avg_cost=None)
    db.expire_all()

    result = M.make_sellable(db, prod_id=src.id, quantity=3, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == tgt.id
    # Then 2
    tgt_row = reread(db, tgt)
    assert tgt_row.qty == 7
    assert tgt_row.avg_cost == Decimal("5.00")
    # Then 3
    in_ = in_row(db)
    assert in_.avg_cost_before is None
    assert in_.avg_cost_after == Decimal("5.00")


@xfail(BUG_2793)
def test_prdm_ms_09__uncosted_source_leaves_target_average(db, s):
    """PRDM-MS-09 — an uncosted source leaves the target average as it was, and the rows carry no cost.
    Rules: make_sellable M5 (source average None), M6."""
    src = mk_source(db, s, avg_cost=None)
    tgt = mk_target(db, s)
    db.expire_all()

    result = M.make_sellable(db, prod_id=src.id, quantity=3, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == tgt.id
    # Then 2
    tgt_row = reread(db, tgt)
    assert tgt_row.qty == 7
    assert tgt_row.avg_cost == Decimal("8.00")
    # Then 3
    out = out_row(db)
    assert out.unit_cost is None
    assert out.total_cost is None
    assert out.avg_cost_before is None
    assert out.avg_cost_after is None
    # Then 4
    in_ = in_row(db)
    assert in_.unit_cost is None
    assert in_.total_cost is None
    assert in_.avg_cost_before == Decimal("8.00")
    assert in_.avg_cost_after == Decimal("8.00")


@xfail(BUG_2793)
def test_prdm_ms_10__uncosted_source_into_missing_target_no_average(db, s):
    """PRDM-MS-10 — an uncosted source into a missing target creates it with no average.
    Rules: make_sellable M3, M5 (source average None)."""
    src = mk_source(db, s, avg_cost=None)
    db.expire_all()

    result = M.make_sellable(db, prod_id=src.id, quantity=3, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id != src.id
    # Then 2
    row = reread(db, result)
    assert row.qty == 3
    assert row.avg_cost is None
    assert row.is_available_for_sale is True
    # Then 3
    in_ = in_row(db)
    assert in_.unit_cost is None
    assert in_.total_cost is None
    assert in_.avg_cost_after is None


@xfail(BUG_2793)
def test_prdm_ms_11__source_average_0_is_a_cost(db, s):
    """PRDM-MS-11 — a source average of 0.00 is a cost: weighted in, totals 0.00.
    Rules: make_sellable M5, M6 (0 -> 0.00)."""
    src = mk_source(db, s, avg_cost=Decimal("0.00"))
    tgt = mk_target(db, s)
    db.expire_all()

    result = M.make_sellable(db, prod_id=src.id, quantity=4, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == tgt.id
    # Then 2
    tgt_row = reread(db, tgt)
    assert tgt_row.qty == 8
    assert tgt_row.avg_cost == Decimal("4.00")
    # Then 3
    out = out_row(db)
    assert out.unit_cost == Decimal("0.00")
    assert out.total_cost == Decimal("0.00")
    # Then 4
    in_ = in_row(db)
    assert in_.unit_cost == Decimal("0.00")
    assert in_.total_cost == Decimal("0.00")
    assert in_.avg_cost_after == Decimal("4.00")


@xfail(BUG_2793)
def test_prdm_ms_12__soft_deleted_for_sale_row_restored_as_target(db, s):
    """PRDM-MS-12 — a soft-deleted for-sale row is restored as the target.
    Rules: make_sellable M3 (restored, BUG-1336 columns)."""
    src = mk_source(db, s)
    tgt = mk_target(db, s, deleted=True, qty=2)
    db.expire_all()

    result = M.make_sellable(db, prod_id=src.id, quantity=3, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == tgt.id
    # Then 2
    tgt_row = reread(db, tgt)
    assert tgt_row.is_deleted is False
    assert tgt_row.is_active is True
    assert tgt_row.deleted_at is None
    assert tgt_row.deleted_by is None
    assert tgt_row.updated_by == s.U2.id
    # Then 3
    assert tgt_row.qty == 5
    assert tgt_row.avg_cost == Decimal("6.20")
    # Then 4
    assert count(db, Product) == 2
    # Then 5
    in_ = in_row(db)
    assert in_.qty_before == 2
    assert in_.qty_after == 5
    assert in_.avg_cost_before == Decimal("8.00")
    assert in_.avg_cost_after == Decimal("6.20")


@xfail(BUG_2793)
def test_prdm_ms_13__moving_everything_allowed_leaves_0(db, s):
    """PRDM-MS-13 — moving everything the source holds is allowed and leaves it at 0.
    Rules: make_sellable M2 (equal side)."""
    src = mk_source(db, s)
    tgt = mk_target(db, s)
    db.expire_all()

    result = M.make_sellable(db, prod_id=src.id, quantity=10, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == tgt.id
    # Then 2
    src_row = reread(db, src)
    assert src_row.qty == 0
    assert src_row.is_deleted is False
    assert src_row.avg_cost == Decimal("5.00")
    # Then 3
    tgt_row = reread(db, tgt)
    assert tgt_row.qty == 14
    assert tgt_row.avg_cost == Decimal("5.86")
    # Then 4
    out = out_row(db)
    assert out.qty_before == 10
    assert out.qty_after == 0
    assert out.quantity == 10
    assert out.total_cost == Decimal("50.00")


@xfail(BUG_2793)
def test_prdm_ms_14__one_unit_moved(db, s):
    """PRDM-MS-14 — one unit is moved.
    Rules: make_sellable M2 (smallest whole quantity)."""
    src = mk_source(db, s)
    tgt = mk_target(db, s)
    db.expire_all()

    result = M.make_sellable(db, prod_id=src.id, quantity=1, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == tgt.id
    # Then 2
    assert reread(db, src).qty == 9
    # Then 3
    tgt_row = reread(db, tgt)
    assert tgt_row.qty == 5
    assert tgt_row.avg_cost == Decimal("7.40")
    # Then 4
    out = out_row(db)
    assert out.quantity == 1
    assert out.notes == "Made sellable: 1 unit(s)"


@xfail(BUG_2793)
def test_prdm_ms_15__whole_decimal_quantity_accepted(db, s):
    """PRDM-MS-15 — a whole Decimal quantity is accepted as whole units.
    Rules: make_sellable M2 (Decimal("3.00") is whole)."""
    src = mk_source(db, s)
    tgt = mk_target(db, s)
    db.expire_all()

    result = M.make_sellable(db, prod_id=src.id, quantity=Decimal("3.00"), workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == tgt.id
    # Then 2
    assert reread(db, src).qty == 7
    # Then 3
    assert reread(db, tgt).qty == 7
    # Then 4
    assert out_row(db).quantity == 3


@xfail(BUG_2793)
def test_prdm_ms_16__unknown_id_not_found(db, s):
    """PRDM-MS-16 — an unknown id is not found.
    Rules: make_sellable M1; Errors row 1."""
    tgt = mk(db, s, for_sale=True, qty=4)
    db.expire_all()
    before = counts(db)
    before_t = snap(db, tgt)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.make_sellable(db, prod_id=MISSING, quantity=1, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Product record with ID 999999999 not found"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before
    # Then 6
    assert snap(db, tgt) == before_t


@xfail(BUG_2793)
def test_prdm_ms_17__source_of_w0_not_found(db, s):
    """PRDM-MS-17 — a source of W0 (lower workspace id) is not found from W1.
    Rules: make_sellable M1 (HR-16)."""
    s0 = mk(db, s, workspace_id=s.W0.id, qty=10)
    db.expire_all()
    before = counts(db)
    before_s0 = snap(db, s0)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.make_sellable(db, prod_id=s0.id, quantity=1, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Product record with ID {s0.id} not found"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before
    # Then 6
    assert snap(db, s0) == before_s0


@xfail(BUG_2793)
def test_prdm_ms_18__source_of_w2_not_found(db, s):
    """PRDM-MS-18 — a source of W2 (higher workspace id) is not found from W1.
    Rules: make_sellable M1 (HR-16)."""
    s9 = mk(db, s, workspace_id=s.W2.id, qty=10)
    db.expire_all()
    before = counts(db)
    before_s9 = snap(db, s9)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.make_sellable(db, prod_id=s9.id, quantity=1, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Product record with ID {s9.id} not found"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before
    # Then 6
    assert snap(db, s9) == before_s9


@xfail(BUG_2793)
def test_prdm_ms_19__soft_deleted_source_refused(db, s):
    """PRDM-MS-19 — a soft-deleted source is refused.
    Rules: make_sellable M1; Errors row 2."""
    src = mk(db, s, deleted=True, qty=10)
    db.expire_all()
    before = counts(db)
    before_s = snap(db, src)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.make_sellable(db, prod_id=src.id, quantity=1, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update a deleted product record"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before
    # Then 6
    assert snap(db, src) == before_s


@xfail(BUG_2793)
def test_prdm_ms_20__for_sale_source_refused(db, s):
    """PRDM-MS-20 — a for-sale source is refused.
    Rules: make_sellable M1; Errors row 3."""
    src = mk(db, s, for_sale=True, qty=10)
    db.expire_all()
    before = counts(db)
    before_s = snap(db, src)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.make_sellable(db, prod_id=src.id, quantity=1, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Only a not-for-sale product record can be made sellable"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before
    # Then 6
    assert snap(db, src) == before_s


@pytest.mark.parametrize("quantity", [
    pytest.param(0, id="PRDM-MS-21", marks=xfail(BUG_2793)),
    pytest.param(-1, id="PRDM-MS-22", marks=xfail(BUG_2793)),
    pytest.param(Decimal("1.5"), id="PRDM-MS-23", marks=xfail(BUG_2793)),
])
def test_prdm_ms_21_to_23__bad_quantity_refused(db, s, quantity):
    """PRDM-MS-21 … PRDM-MS-23 — quantity 0, a negative or a fractional quantity is refused.
    Rules: make_sellable M2; Errors row 4."""
    src = mk_source(db, s)
    db.expire_all()
    before = counts(db)
    before_s = snap(db, src)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.make_sellable(db, prod_id=src.id, quantity=quantity, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Quantity must be a positive whole number"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before
    # Then 6
    assert snap(db, src) == before_s


@xfail(BUG_2793)
def test_prdm_ms_24__one_more_than_held_refused(db, s):
    """PRDM-MS-24 — one more than the source holds is refused.
    Rules: make_sellable M2; Errors row 5."""
    src = mk_source(db, s)
    tgt = mk_target(db, s)
    db.expire_all()
    before = counts(db)
    before_s, before_t = snap(db, src), snap(db, tgt)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.make_sellable(db, prod_id=src.id, quantity=11, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 422
    # Then 3
    assert exc.value.detail == "Insufficient stock to make sellable: requested 11, available 10"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before
    # Then 6
    assert snap(db, src) == before_s
    # Then 7
    assert snap(db, tgt) == before_t


@xfail(BUG_2793)
def test_prdm_ms_25__deleted_source_reported_before_bad_quantity(db, s):
    """PRDM-MS-25 — a deleted source is reported before a bad quantity.
    Rules: make_sellable M2 (order: M1, then M2)."""
    src = mk(db, s, deleted=True, qty=10)
    db.expire_all()
    before = counts(db)
    before_s = snap(db, src)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.make_sellable(db, prod_id=src.id, quantity=0, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update a deleted product record"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before
    # Then 6
    assert snap(db, src) == before_s


@xfail(BUG_2793)
def test_prdm_ms_26__for_sale_source_reported_before_too_large_quantity(db, s):
    """PRDM-MS-26 — a for-sale source is reported before too large a quantity.
    Rules: make_sellable M2 (order: M1, then M2)."""
    src = mk(db, s, for_sale=True, qty=10)
    db.expire_all()
    before = counts(db)
    before_s = snap(db, src)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.make_sellable(db, prod_id=src.id, quantity=99, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Only a not-for-sale product record can be made sellable"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before
    # Then 6
    assert snap(db, src) == before_s


@xfail(BUG_2793)
def test_prdm_ms_27__for_sale_rows_of_w0_w2_not_the_target(db, s):
    """PRDM-MS-27 — for-sale rows of the same key in W0 and W2 are not the target.
    Rules: make_sellable M3 (target in this workspace); HR-16."""
    t0 = mk_target(db, s, workspace_id=s.W0.id)
    src = mk_source(db, s)
    t9 = mk_target(db, s, workspace_id=s.W2.id)
    db.expire_all()
    before_t0, before_t9 = snap(db, t0), snap(db, t9)

    result = M.make_sellable(db, prod_id=src.id, quantity=3, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id not in (t0.id, t9.id)
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == s.W1.id
    assert row.qty == 3
    assert row.avg_cost == Decimal("5.00")
    # Then 3
    assert snap(db, t0) == before_t0
    # Then 4
    assert snap(db, t9) == before_t9
    # Then 5
    assert count(db, ProductLedger, or_(ProductLedger.workspace_id == s.W0.id,
                                        ProductLedger.workspace_id == s.W2.id)) == 0


@xfail(BUG_2793)
def test_prdm_ms_28__for_sale_rows_of_other_factory_or_item_not_the_target(db, s):
    """PRDM-MS-28 — for-sale rows of another factory or item are not the target.
    Rules: make_sellable M3 (same factory and item)."""
    ta = mk(db, s, for_sale=True, factory_id=s.F2.id, qty=4)
    src = mk_source(db, s)
    tb = mk(db, s, for_sale=True, item_id=s.I2.id, qty=4)
    db.expire_all()
    before_ta, before_tb = snap(db, ta), snap(db, tb)

    result = M.make_sellable(db, prod_id=src.id, quantity=3, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id not in (ta.id, tb.id)
    # Then 2
    row = reread(db, result)
    assert row.factory_id == s.F1.id
    assert row.item_id == s.I1.id
    assert row.qty == 3
    # Then 3
    assert snap(db, ta) == before_ta
    # Then 4
    assert snap(db, tb) == before_tb


@xfail(BUG_2793)
def test_prdm_ms_29__rows_read_with_row_lock(db, s):
    """PRDM-MS-29 — the rows are read with a row lock.
    Rules: make_sellable M7 (HR-10; the order of the two locks is Deferred)."""
    src = mk_source(db, s)
    tgt = mk_target(db, s)
    db.expire_all()
    src_id, tgt_id, ws_id, u_id = src.id, tgt.id, s.W1.id, s.U2.id

    with record(db) as rec:
        result = M.make_sellable(db, prod_id=src_id, quantity=3, workspace_id=ws_id, user_id=u_id)

    # Then 1
    assert result.id == tgt_id
    # Then 2
    assert any("FOR UPDATE" in s_ for s_ in rec.psel)
    # Then 3
    assert not any("SKIP LOCKED" in s_ for s_ in rec.psel)
    # Then 4
    assert not any("NOWAIT" in s_ for s_ in rec.psel)


@xfail(BUG_2793)
def test_prdm_ms_30__move_flushed_not_committed(db, s):
    """PRDM-MS-30 — the move is flushed but not committed.
    Rules: make_sellable M9."""
    src = mk_source(db, s)
    tgt = mk_target(db, s)
    db.expire_all()

    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as spy:
        result = M.make_sellable(db, prod_id=src.id, quantity=3, workspace_id=s.W1.id, user_id=s.U2.id)

        # Then 1
        assert result.id == tgt.id
        # Then 2
        assert count(db, ProductLedger) == 2
        sp.rollback()
        # Then 3
        assert count(db, ProductLedger) == 0
        # Then 4
        assert reread(db, src).qty == 10
        # Then 5
        spy.assert_not_called()
