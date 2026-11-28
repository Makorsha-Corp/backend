"""Unit tests for app/dao/inventory.py.

Implements tests/unit/dao/inventory.cases.md, one test per case. Real Postgres
session (`db` fixture). Nothing is mocked and no clock is patched (spec: no
externals); the only patches are the race simulations and the commit spy of
the cards marked "Author: claude".

Built in local-coder mode: the scaffold and the exemplar tests in the first
part of this file are hand-written; tests below a `# [local-coder] <ID>`
comment were written by the local model from one case card each, with
tests/unit/dao/inventory.helpers.md as its only view of this file.
"""
# ruff: noqa: SIM117, DTZ001, FURB157  (prescribed by the cards: nested with, naive datetimes, Decimal("...") literals)
from datetime import datetime
from decimal import Decimal
from unittest.mock import (
    patch,  # race simulations and commit spy (Author: claude cards)
)

import pytest
from psycopg2.errors import (
    ForeignKeyViolation,
    InvalidRowCountInLimitClause,
    InvalidRowCountInResultOffsetClause,
    UniqueViolation,
)
from sqlalchemy import func, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.engine import Row
from sqlalchemy.exc import DataError, IntegrityError

from app.dao.inventory import inventory_dao
from app.models.enums import InventoryTypeEnum
from app.models.factory import Factory
from app.models.inventory import Inventory
from app.models.inventory_ledger import InventoryLedger
from app.models.item import Item
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton inventory_dao". A plain module-level name;
# the fixture of the same name below only makes `dao` legal as a test argument.
dao = inventory_dao

# Convention "STORAGE, DAMAGED, WASTE, SCRAP = the four members of InventoryTypeEnum"
STORAGE = InventoryTypeEnum.STORAGE
DAMAGED = InventoryTypeEnum.DAMAGED
WASTE = InventoryTypeEnum.WASTE
SCRAP = InventoryTypeEnum.SCRAP

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999

# Convention "T0 ... T5" (all naive)
T0 = datetime(2025, 12, 1, 8, 0, 0)
T1 = datetime(2026, 1, 1, 9, 0, 0)
T2 = datetime(2026, 1, 1, 10, 0, 0)
T3 = datetime(2026, 1, 1, 11, 0, 0)
T4 = datetime(2026, 1, 1, 12, 0, 0)
T5 = datetime(2026, 1, 1, 13, 0, 0)


# --------------------------------------------------------------------------- #
# Conventions -> fixtures (actors and the six fixed rows)
# --------------------------------------------------------------------------- #

@pytest.fixture(name="dao")
def _dao_fixture():
    return inventory_dao


# Convention "W1, W2 = two workspaces rows"
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db):
    return make_workspace(db)


# Convention "U1 is created_by of every Given stock row, U2 is the acting user"
@pytest.fixture
def u1(db):
    return make_profile(db)


@pytest.fixture
def u2(db):
    return make_profile(db)


def _add(db, row):
    db.add(row)
    db.flush()
    return row


# Convention "F1, F2, F9" (fixed factories)
@pytest.fixture
def f1(db, w1):
    return _add(db, Factory(name="Factory One", abbreviation="F1", workspace_id=w1.id,
                            is_active=True, is_deleted=False))


@pytest.fixture
def f2(db, w1, f1):
    return _add(db, Factory(name="Factory Two", abbreviation="F2", workspace_id=w1.id,
                            is_active=True, is_deleted=False))


@pytest.fixture
def f9(db, w2, f2):
    return _add(db, Factory(name="Factory Nine", abbreviation="F9", workspace_id=w2.id,
                            is_active=True, is_deleted=False))


def _item(db, name, workspace_id, **columns):
    fields = {"name": name, "name_normalized": name.lower(), "workspace_id": workspace_id,
              "unit": "pcs", "is_active": True, "description": None, "sku": None}
    fields.update(columns)
    return _add(db, Item(**fields))


# Convention "I1, I2, I9" (fixed items)
@pytest.fixture
def i1(db, w1, f9):
    return _item(db, "Bolt", w1.id)


@pytest.fixture
def i2(db, w1, i1):
    return _item(db, "Nut", w1.id)


@pytest.fixture
def i9(db, w2, i2):
    return _item(db, "Bolt", w2.id)


# Convention "These six rows exist in every test and need no Given line"
@pytest.fixture(autouse=True)
def fixed_rows(db, w1, w2, u1, u2, f1, f2, f9, i1, i2, i9):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builders (fixtures; each inserts one row and flushes)
# --------------------------------------------------------------------------- #

# Convention "default item"
@pytest.fixture
def mk_item(db, w1):
    """mk_item(name, **columns) -> Item."""
    def _mk(name, **columns):
        columns.setdefault("workspace_id", w1.id)
        return _item(db, name, columns.pop("workspace_id"), **columns)
    return _mk


# Convention "`factories` row: ..." (a card's own factory)
@pytest.fixture
def mk_factory(db, w1):
    """mk_factory(name, abbreviation, **columns) -> Factory."""
    def _mk(name, abbreviation, **columns):
        fields = {"name": name, "abbreviation": abbreviation, "workspace_id": w1.id,
                  "is_active": True, "is_deleted": False}
        fields.update(columns)
        return _add(db, Factory(**fields))
    return _mk


# Convention "default stock of <item> in <factory>" / "deleted"
@pytest.fixture
def mk_stock(db, w1, u1):
    """mk_stock(item, factory, deleted=False, **columns) -> Inventory."""
    def _mk(item, factory, deleted=False, **columns):
        fields = {
            "item_id": item.id, "factory_id": factory.id, "workspace_id": w1.id,
            "inventory_type": STORAGE, "qty": 5, "avg_price": Decimal("2.00"), "note": None,
            "created_by": u1.id, "updated_by": None, "updated_at": None,
            "is_active": True, "is_deleted": False, "deleted_at": None, "deleted_by": None,
        }
        if deleted:
            fields.update(is_deleted=True, is_active=False, deleted_at=T0, deleted_by=u1.id)
        fields.update(columns)
        return _add(db, Inventory(**fields))
    return _mk


# Convention "entry of <item> in <factory>"
@pytest.fixture
def mk_entry(db, w1):
    """mk_entry(item, factory, *, qty_after, avg_price_after, performed_at, **columns) -> InventoryLedger."""
    def _mk(item, factory, *, qty_after, avg_price_after, performed_at, **columns):
        fields = {
            "item_id": item.id, "factory_id": factory.id, "workspace_id": w1.id,
            "inventory_type": STORAGE, "transaction_type": "manual_add", "quantity": 1,
            "qty_before": 0, "qty_after": qty_after, "avg_price_after": avg_price_after,
            "performed_at": performed_at,
        }
        fields.update(columns)
        return _add(db, InventoryLedger(**fields))
    return _mk


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (plain functions; no expected values inside)
# --------------------------------------------------------------------------- #

def _id_of(row):
    """Primary key of a row, without touching its (possibly expired) attributes."""
    return sa_inspect(row).identity[0]


# Convention "re-read X": expire_all, then SELECT X by id
def reread(db, row):
    """Fresh copy of `row` (any model) from the database, or None if it is gone."""
    model, row_id = type(row), _id_of(row)
    db.expire_all()
    return db.execute(select(model).where(model.id == row_id)).scalar_one_or_none()


# Convention "unchanged(X)": every column of X, straight from the table
def snap(db, row):
    """Dict column -> database value of `row` (any model), or None if it is gone."""
    table = type(row).__table__
    found = db.execute(select(table).where(table.c.id == _id_of(row))).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "count:" lines: rows of the table in all workspaces
def count_rows(db, model):
    return db.execute(select(func.count()).select_from(model.__table__)).scalar_one()


# Convention "nothing written": row counts of inventory and inventory_ledger
def written(db):
    return {"inventory": count_rows(db, Inventory), "inventory_ledger": count_rows(db, InventoryLedger)}


# Convention "ids(result)"
def ids(result):
    return sorted(row.id for row in result)


# Convention "names(result)"
def names(result):
    return [row.item_name for row in result]


# Convention "by_type(result)"
def by_type(result):
    return {(r[0], r[1], r[2]) for r in result[3]}


# Convention "HIGH_ID": greatest inventory_ledger.id at this moment (0 if none) + 1000000
def high_id(db):
    return (db.execute(select(func.max(InventoryLedger.__table__.c.id))).scalar() or 0) + 1000000


# --------------------------------------------------------------------------- #
# Exemplar tests (hand-written; shown verbatim in inventory.helpers.md)
# --------------------------------------------------------------------------- #

def test_inv_st_12__factory_filter_soft_delete_and_scope(db, w1, w2, f1, f2, f9, i1, i2, i9, mk_stock):
    """INV-ST-12 — factory filter, soft-delete and workspace scope apply to every part.
    Rules: stats_filtered R1; _filtered_query R1, R2, R5"""
    mk_stock(i1, f1)
    mk_stock(i2, f1, deleted=True, qty=7)
    mk_stock(i1, f2, qty=4)
    mk_stock(i9, f9, workspace_id=w2.id)

    result = dao.stats_filtered(db, workspace_id=w1.id, factory_id=f1.id)

    # Then 1
    assert result[0] == 1
    # Then 2
    assert result[1] == 5
    # Then 3
    assert result[2] == Decimal("10.00")
    # Then 4
    assert by_type(result) == {(STORAGE, 1, 5)}


def test_inv_en_05__soft_deleted_row_restored_and_aligned(db, w1, u1, u2, f1, i1, mk_stock, mk_entry):
    """INV-EN-05 — a soft-deleted row is restored, aligned and returned.
    Rules: ensure_for_factory_item_type R3; restore R1, R2"""
    s1 = mk_stock(i1, f1, deleted=True, qty=7, avg_price=Decimal("5.00"), note="old note")
    mk_entry(i1, f1, qty_after=20, avg_price_after=Decimal("6.00"), performed_at=T1)

    result = dao.ensure_for_factory_item_type(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE,
                                              workspace_id=w1.id, created_by=u2.id)

    # Then 1
    assert result.id == s1.id
    # Then 2
    row = reread(db, s1)
    assert row.is_deleted is False
    assert row.is_active is True
    # Then 3
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 4
    assert row.qty == 20
    # Then 5
    assert row.avg_price == Decimal("6.00")
    # Then 6
    assert row.updated_by == u2.id
    # Then 7
    assert row.note == "old note"
    # Then 8
    assert row.created_by == u1.id
    # Then 9
    assert count_rows(db, Inventory) == 1


def test_inv_l_17__negative_limit_rejected(db, w1, f1, i1, mk_stock):
    """INV-L-17 — negative limit is rejected by the database and nothing changes.
    Rules: list_filtered R5, Errors row 1"""
    s1 = mk_stock(i1, f1)
    before = written(db)
    before_s1 = snap(db, s1)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.list_filtered(db, workspace_id=w1.id, limit=-1)

    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInLimitClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201W"
    # Then 4
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 5
    assert written(db) == before
    # Then 6
    assert snap(db, s1) == before_s1


@pytest.mark.xfail(strict=True, reason="BUG-882: Stock held in a soft-deleted factory is still listed, "
                                       "counted and included in the stock statistics")
def test_inv_fq_36__stock_in_soft_deleted_factory_not_matched(db, w1, f1, i1, mk_factory, mk_stock):
    """INV-FQ-36 — stock in a soft-deleted factory is not matched.
    Rules: _filtered_query R11a [BUG-882]; list_filtered R1a [BUG-882]"""
    fa = mk_factory("Old Plant", "OP", is_active=True, is_deleted=True)
    s1 = mk_stock(i1, f1)
    mk_stock(i1, fa, qty=30)

    result = dao.list_filtered(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [s1.id]


# [local-coder] INV-FQ-10
@pytest.mark.xfail(strict=True, reason="BUG-880: Inventory list / count / stats treat factory_id=0 as 'no factory filter'")
def test_inv_fq_10__factory_id_0_matches_no_rows(db, w1, f1, f2, i1, mk_stock):
    """INV-FQ-10 — factory_id 0 matches no rows.
    Rules: _filtered_query R5 [BUG-880]"""
    mk_stock(i1, f1)
    mk_stock(i1, f2)

    result = dao.list_filtered(db, workspace_id=w1.id, factory_id=0)

    # Then 1
    assert result == []


# [local-coder] INV-FQ-23
def test_inv_fq_23__note_item_description_item_sku_and_factory_name_are_not_searched(db, w1, mk_item, mk_factory, mk_stock):
    """INV-FQ-23 — note, item description, item SKU and factory name are not searched.
    Rules: _filtered_query R9"""
    ia = mk_item("Washer", description="gasket kit", sku="GASKET-1")
    fa = mk_factory("Gasket Plant", "GP", workspace_id=w1.id)
    mk_stock(ia, fa, note="gasket spare")

    result = dao.list_filtered(db, workspace_id=w1.id, search="gasket")

    # Then 1
    assert result == []


# [local-coder] INV-FQ-35
def test_inv_fq_35__listing_leaves_removed_item_stock_untouched(db, w1, f1, i1, mk_item, mk_stock):
    """INV-FQ-35 — listing leaves the stock row of a removed item and the item itself untouched.
    Rules: _filtered_query R11c"""
    ia = mk_item("Old Gasket", is_active=False)
    s1 = mk_stock(i1, f1)
    s2 = mk_stock(ia, f1, qty=12)
    before_s2 = snap(db, s2)
    before_ia = snap(db, ia)

    result = dao.list_filtered(db, workspace_id=w1.id)

    # Then 1
    assert s1.id in ids(result)
    # Then 2
    assert snap(db, s2) == before_s2
    # Then 3
    row = reread(db, s2)
    assert row.is_deleted is False
    assert row.qty == 12
    assert row.item_id == ia.id
    # Then 4
    assert row.avg_price == Decimal("2.00")
    # Then 5
    assert snap(db, ia) == before_ia
    # Then 6
    row_ia = reread(db, ia)
    assert row_ia.is_active is False
    # Then 7
    assert count_rows(db, Inventory) == 2


# [local-coder] INV-CNT-02
def test_inv_cnt_02__deleted_zero_quantity_and_other_workspace_rows_are_not_counted(db, w1, w2, f1, f2, f9, i1, i2, i9, mk_stock):
    """INV-CNT-02 — deleted, zero-quantity and other-workspace rows are not counted.
    Rules: count_filtered R1; _filtered_query R1, R2, R7"""
    mk_stock(i1, f1)
    mk_stock(i2, f1, deleted=True)
    mk_stock(i1, f2, qty=0)
    mk_stock(i9, f9, workspace_id=w2.id)

    result = dao.count_filtered(db, workspace_id=w1.id)

    # Then 1
    assert result == 1


# [local-coder] INV-ST-01
def test_inv_st_01__records_total_quantity_and_value(db, w1, f1, f2, i1, i2, mk_stock):
    """INV-ST-01 — records, total quantity and value; a NULL price adds no value.
    Rules: stats_filtered R1, R2, R3, R4, R5"""
    mk_stock(i1, f1, qty=5, avg_price=Decimal("2.50"))
    mk_stock(i2, f1, qty=4, avg_price=Decimal("3.33"))
    mk_stock(i1, f2, qty=8, avg_price=None)

    result = dao.stats_filtered(db, workspace_id=w1.id)

    # Then 1
    assert type(result) is tuple
    # Then 2
    assert len(result) == 4
    # Then 3
    assert result[0] == 3
    # Then 4
    assert type(result[0]) is int
    # Then 5
    assert result[1] == 17
    # Then 6
    assert type(result[1]) is int
    # Then 7
    assert result[2] == Decimal("25.82")
    # Then 8
    assert isinstance(result[2], Decimal)
    # Then 9
    assert by_type(result) == {(STORAGE, 2, 17)}
    # Then 10
    assert len(result[3]) == 1


# [local-coder] INV-SY-17
def test_inv_sy_17__among_entries_sharing_newest_performed_at_greatest_id_wins(db, w1, u2, f1, i1, mk_stock, mk_entry):
    """INV-SY-17 — among entries sharing the newest performed_at the greatest id wins.
    Rules: sync_snapshot_from_ledger R12 [BUG-664]"""
    s1 = mk_stock(i1, f1, qty=7, avg_price=Decimal("5.00"))
    mk_entry(i1, f1, qty_after=15, avg_price_after=Decimal("1.00"), performed_at=T1)
    mk_entry(i1, f1, id=high_id(db), qty_after=10, avg_price_after=Decimal("4.00"), performed_at=T1)
    mk_entry(i1, f1, qty_after=30, avg_price_after=Decimal("7.00"), performed_at=T1)

    result = dao.sync_snapshot_from_ledger(db, inv=s1, workspace_id=w1.id, updated_by=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.qty == 10
    # Then 3
    assert row.avg_price == Decimal("4.00")


# [local-coder] INV-EN-11
def test_inv_en_11__a_row_differing_only_in_workspace_is_not_reused_a_new_row_is_created_next_to_it(db, w1, w2, f1, i1, u2, mk_stock):
    """INV-EN-11 — a row differing only in workspace is not reused: a new row is created next to it.
    Rules: ensure_for_factory_item_type R7"""
    s1 = mk_stock(i1, f1, workspace_id=w2.id)
    before_s1 = snap(db, s1)

    result = dao.ensure_for_factory_item_type(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id, created_by=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert result.id != s1.id
    # Then 3
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.factory_id == f1.id
    assert row.item_id == i1.id
    # Then 4
    assert row.inventory_type == STORAGE
    # Then 5
    assert snap(db, s1) == before_s1
    # Then 6
    assert count_rows(db, Inventory) == 2


# [local-coder] INV-EN-18
def test_inv_en_18__unknown_item_id_fails_on_foreign_key(db, w1, f1, i2, u2, mk_stock):
    """INV-EN-18 — an unknown item_id fails on the foreign key; nothing is created, the session stays usable.
    Rules: ensure_for_factory_item_type R8, Errors row 1"""
    s1 = mk_stock(i2, f1)
    before_s1 = snap(db, s1)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        dao.ensure_for_factory_item_type(db, factory_id=f1.id, item_id=MISSING, inventory_type=STORAGE,
                                         workspace_id=w1.id, created_by=u2.id)

    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert exc.value.orig.pgcode == "23503"
    # Then 4
    assert "inventory_item_id_fkey" in str(exc.value.orig)
    # Then 5
    assert count_rows(db, Inventory) == 1
    # Then 6
    assert snap(db, s1) == before_s1


# [local-coder] INV-GI-09
@pytest.mark.xfail(strict=True, reason="BUG-884: Item summary still shows and totals stock held in a soft-deleted factory")
def test_inv_gi_09__soft_deleted_factory_not_returned(db, w1, f1, i1, mk_factory, mk_stock):
    """INV-GI-09 — a row in a soft-deleted factory is not returned.
    Rules: get_by_item R1a [BUG-884]"""
    fa = mk_factory("Old Plant", "OP", workspace_id=w1.id, is_active=True, is_deleted=True)
    s1 = mk_stock(i1, f1)
    mk_stock(i1, fa, qty=30)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [s1.id]


# [local-coder] INV-R-01
def test_inv_r_01__a_soft_deleted_row_is_brought_back_and_nothing_else_changes(db, u1, f1, i1, mk_stock):
    """INV-R-01 — a soft-deleted row is brought back and nothing else changes.
    Rules: restore R1, R2, R4"""
    s1 = mk_stock(i1, f1, deleted=True, qty=7, avg_price=Decimal("5.00"), note="n1", updated_by=u1.id)
    before_created_at = snap(db, s1)["created_at"]

    result = dao.restore(db, db_obj=s1)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.is_active is True
    assert row.is_deleted is False
    # Then 3
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 4
    assert row.qty == 7
    # Then 5
    assert row.avg_price == Decimal("5.00")
    # Then 6
    assert row.note == "n1"
    # Then 7
    assert row.created_by == u1.id
    assert row.updated_by == u1.id
    # Then 8
    assert row.updated_at is not None
    # Then 9
    assert row.created_at == before_created_at


# [local-coder] INV-FQ-26
@pytest.mark.xfail(strict=True, reason="BUG-702: Inventory/stats search text acts as SQL wildcards")
def test_inv_fq_26__a_backslash_in_search_text_matched(db, w1, f1, mk_item, mk_stock):
    """INV-FQ-26 — a backslash in the search text is matched literally.
    Rules: _filtered_query R9 [BUG-702]"""
    ia = mk_item("a\\b")
    ib = mk_item("ab")
    s1 = mk_stock(ia, f1)
    mk_stock(ib, f1)

    result = dao.list_filtered(db, workspace_id=w1.id, search="a\\b")

    # Then 1
    assert ids(result) == [s1.id]


# [local-coder] INV-L-04
@pytest.mark.xfail(strict=True, reason="BUG-701: Inventory list has no stable sort order")
def test_inv_l_04__item_names_differing_only_in_case_come_back_in_stock_row_id_order(db, w1, f1, i1, mk_item, mk_stock):
    """INV-L-04 — item names differing only in case come back in stock-row id order (upper case first).
    Rules: list_filtered R2 [BUG-701]"""
    ib = mk_item("bolt", name_normalized="bolt lower")
    mk_stock(i1, f1)
    mk_stock(ib, f1)

    result = dao.list_filtered(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert names(result) == ["Bolt", "bolt"]


# [local-coder] INV-L-10
def test_inv_l_10__default_limit_returns_first_100_of_101(db, w1, f1, mk_item, mk_stock):
    """INV-L-10 — default limit returns the first 100 of 101 rows.
    Rules: list_filtered R3"""
    items = []
    for n in range(1, 102):
        item = mk_item(f"Item {n:03d}")
        items.append(item)
        mk_stock(item, f1)

    result = dao.list_filtered(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert names(result)[0] == "Item 001"
    # Then 3
    assert names(result)[-1] == "Item 100"


# [local-coder] INV-L-18
def test_inv_l_18__negative_skip_rejected(db, w1, f1, i1, mk_stock):
    """INV-L-18 — negative skip is rejected by the database and nothing changes.
    Rules: list_filtered R5, Errors row 2"""
    s1 = mk_stock(i1, f1)
    before = written(db)
    before_s1 = snap(db, s1)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.list_filtered(db, workspace_id=w1.id, skip=-1)

    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201X"
    # Then 4
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 5
    assert written(db) == before
    # Then 6
    assert snap(db, s1) == before_s1


# [local-coder] INV-ST-17
def test_inv_st_17__each_per_type_row_is_a_3_item_row(db, w1, f1, i1, mk_stock):
    """INV-ST-17 — each per-type row is a 3-item Row: type member, int, int.
    Rules: stats_filtered R5"""
    mk_stock(i1, f1)

    result = dao.stats_filtered(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result[3], list)
    # Then 2
    assert isinstance(result[3][0], Row)
    # Then 3
    assert len(result[3][0]) == 3
    # Then 4
    assert isinstance(result[3][0][0], InventoryTypeEnum)
    # Then 5
    assert type(result[3][0][1]) is int
    # Then 6
    assert type(result[3][0][2]) is int
    # Then 7
    t, n, q = result[3][0]
    assert (t, n, q) == (STORAGE, 1, 5)


# [local-coder] INV-SY-10
def test_inv_sy_10__newer_entries_of_other_buckets_are_ignored(db, w1, w2, f1, f2, i1, i2, u2, mk_stock, mk_entry):
    """INV-SY-10 — newer entries of other buckets are ignored.
    Rules: sync_snapshot_from_ledger R7"""
    s1 = mk_stock(i1, f1, qty=7, avg_price=Decimal("5.00"))
    mk_entry(i1, f1, qty_after=20, avg_price_after=Decimal("6.00"), performed_at=T1)
    mk_entry(i1, f1, inventory_type=DAMAGED, qty_after=91, avg_price_after=Decimal("9.10"), performed_at=T2)
    mk_entry(i1, f2, qty_after=92, avg_price_after=Decimal("9.20"), performed_at=T3)
    mk_entry(i2, f1, qty_after=93, avg_price_after=Decimal("9.30"), performed_at=T4)
    mk_entry(i1, f1, workspace_id=w2.id, qty_after=94, avg_price_after=Decimal("9.40"), performed_at=T5)

    result = dao.sync_snapshot_from_ledger(db, inv=s1, workspace_id=w1.id, updated_by=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.qty == 20
    # Then 3
    assert row.avg_price == Decimal("6.00")


# [local-coder] INV-SY-12
def test_inv_sy_12__no_other_column_of_the_row_is_touched(db, w1, u1, u2, f1, i1, mk_stock, mk_entry):
    """INV-SY-12 — no other column of the row is touched.
    Rules: sync_snapshot_from_ledger R8"""
    s1 = mk_stock(i1, f1, qty=7, avg_price=Decimal("5.00"), note="keep me")
    mk_entry(i1, f1, qty_after=20, avg_price_after=Decimal("6.00"), performed_at=T1)

    created_before = snap(db, s1)["created_at"]

    result = dao.sync_snapshot_from_ledger(db, inv=s1, workspace_id=w1.id, updated_by=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.qty == 20
    # Then 3
    assert row.note == "keep me"
    # Then 4
    assert row.created_by == u1.id
    # Then 5
    assert row.is_active is True
    assert row.is_deleted is False
    # Then 6
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 7
    assert row.created_at == created_before


# [local-coder] INV-EN-15
def test_inv_en_15__a_second_call_with_the_same_arguments_returns_the_same_row(db, w1, u2, f1, i1):
    """INV-EN-15 — a second call with the same arguments returns the same row.
    Rules: ensure_for_factory_item_type R7, R1"""
    first = dao.ensure_for_factory_item_type(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE,
                                             workspace_id=w1.id, created_by=u2.id)

    result = dao.ensure_for_factory_item_type(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE,
                                              workspace_id=w1.id, created_by=u2.id)

    # Then 1
    assert result.id == first.id
    # Then 2
    assert count_rows(db, Inventory) == 1


# [local-coder] INV-EN-20
def test_inv_en_20__unknown_created_by_fails_on_foreign_key(db, w1, f1, i1, i2, mk_stock):
    """INV-EN-20 — an unknown created_by fails on the foreign key; nothing is created, the session stays usable.
    Rules: ensure_for_factory_item_type R8, Errors row 3"""
    s1 = mk_stock(i2, f1)
    before_s1 = snap(db, s1)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        dao.ensure_for_factory_item_type(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE,
                                         workspace_id=w1.id, created_by=MISSING)

    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert exc.value.orig.pgcode == "23503"
    # Then 4
    assert "inventory_created_by_fkey" in str(exc.value.orig)
    # Then 5
    assert count_rows(db, Inventory) == 1
    # Then 6
    assert snap(db, s1) == before_s1


# [local-coder] INV-R-02
def test_inv_r_02__a_restored_row_is_found_again_by_the_live_bucket_lookup(db, w1, f1, i1, mk_stock):
    """INV-R-02 — a restored row is found again by the live bucket lookup.
    Rules: restore R1"""
    s1 = mk_stock(i1, f1, deleted=True)

    result = dao.restore(db, db_obj=s1)

    # Then 1
    assert result is s1
    # Then 2
    assert dao.get_by_factory_item_type(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id).id == s1.id


# [local-coder] INV-FQ-21
def test_inv_fq_21__a_row_matches_when_either_the_name_or_the_unit_contains_the_text(db, w1, f1, i2, mk_item, mk_stock):
    """INV-FQ-21 — a row matches when either the name or the unit contains the text.
    Rules: _filtered_query R9, R10"""
    ia = mk_item("Kg Scale")
    ib = mk_item("Wire", unit="kg")
    s1 = mk_stock(ia, f1)
    s2 = mk_stock(ib, f1)
    mk_stock(i2, f1)

    result = dao.list_filtered(db, workspace_id=w1.id, search="kg")

    # Then 1
    assert ids(result) == [s1.id, s2.id]


# [local-coder] INV-FQ-31
@pytest.mark.xfail(strict=True, reason="BUG-883: Stock of a catalog item removed from the catalog is still listed, counted, included in the")
def test_inv_fq_31__stock_of_a_removed_catalog_item_is_not_matched(db, w1, f1, i1, mk_item, mk_stock):
    """INV-FQ-31 — stock of a removed catalog item is not matched.
    Rules: _filtered_query R11 [BUG-883]; list_filtered R1b [BUG-883]"""
    ia = mk_item("Old Gasket", is_active=False)
    s1 = mk_stock(i1, f1)
    mk_stock(ia, f1, qty=12)

    result = dao.list_filtered(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [s1.id]


# [local-coder] INV-L-06
def test_inv_l_06__first_window_of_two(db, w1, f1, mk_item, mk_stock):
    """INV-L-06 — first window of two.
    Rules: list_filtered R3"""
    ia = mk_item("Echo")
    ib = mk_item("Delta")
    ic = mk_item("Charlie")
    id_ = mk_item("Bravo")
    ie = mk_item("Alpha")
    mk_stock(ia, f1)
    mk_stock(ib, f1)
    mk_stock(ic, f1)
    mk_stock(id_, f1)
    mk_stock(ie, f1)

    result = dao.list_filtered(db, workspace_id=w1.id, skip=0, limit=2)

    # Then 1
    assert names(result) == ["Alpha", "Bravo"]


# [local-coder] INV-CNT-13
@pytest.mark.xfail(strict=True, reason="BUG-883: Stock of a catalog item removed from the catalog is still listed, counted, included in the")
def test_inv_cnt_13__filtering_by_a_removed_items_id_counts_nothing(db, w1, f1, i1, mk_item, mk_stock):
    """INV-CNT-13 — filtering by a removed item's id counts nothing.
    Rules: count_filtered R1b [BUG-883]; _filtered_query R11 [BUG-883]"""
    ia = mk_item("Old Gasket", is_active=False)
    mk_stock(i1, f1)
    mk_stock(ia, f1, qty=12)

    result = dao.count_filtered(db, workspace_id=w1.id, item_id=ia.id)

    # Then 1
    assert result == 0


# [local-coder] INV-ST-24
@pytest.mark.xfail(strict=True, reason="BUG-883: Stock of a catalog item removed from the catalog is still listed, counted, included in the")
def test_inv_st_24__removed_item_absent_from_per_type_rows(db, w1, f1, i1, mk_item, mk_stock):
    """INV-ST-24 — stock of a removed item is absent from the per-type rows.
    Rules: stats_filtered R5b [BUG-883]; _filtered_query R11 [BUG-883]"""
    ia = mk_item("Old Gasket", is_active=False)
    mk_stock(i1, f1)
    mk_stock(ia, f1, qty=12)
    mk_stock(ia, f1, inventory_type=SCRAP, qty=3)

    result = dao.stats_filtered(db, workspace_id=w1.id)

    # Then 1
    assert by_type(result) == {(STORAGE, 1, 5)}
    # Then 2
    assert len(result[3]) == 1


# [local-coder] INV-GF-11
def test_inv_gf_11__the_live_row_of_a_bucket_of_a_removed_item_is_returned(db, w1, f1, mk_item, mk_stock):
    """INV-GF-11 — the live row of a bucket of a removed item is returned.
    Rules: get_by_factory_item_type R5"""
    ia = mk_item("Old Gasket", is_active=False)
    s1 = mk_stock(ia, f1)

    result = dao.get_by_factory_item_type(db, factory_id=f1.id, item_id=ia.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result.id == s1.id


# [local-coder] INV-FQ-01
def test_inv_fq_01__default_call_returns_workspace_live_instock_rows(db, w1, w2, f1, f9, i1, i2, i9, mk_stock):
    """INV-FQ-01 — default call returns the workspace's live in-stock rows, each once.
    Rules: _filtered_query R1, R3, R12"""
    s1 = mk_stock(i1, f1)
    s2 = mk_stock(i2, f1)
    mk_stock(i9, f9, workspace_id=w2.id)

    result = dao.list_filtered(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [s1.id, s2.id]


# [local-coder] INV-FQ-02
def test_inv_fq_02__other_workspace_returns_only_that_workspace_rows(db, w2, f1, f9, i1, i2, i9, mk_stock):
    """INV-FQ-02 — a call for the other workspace returns only that workspace's rows.
    Rules: _filtered_query R1"""
    mk_stock(i1, f1)
    mk_stock(i2, f1)
    s9 = mk_stock(i9, f9, workspace_id=w2.id)

    result = dao.list_filtered(db, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [s9.id]


# [local-coder] INV-FQ-03
def test_inv_fq_03__a_w1_stock_row_pointing_at_a_w2_item_is_matched_and_searchable(db, w1, f1, i2, i9, mk_stock):
    """INV-FQ-03 — a W1 stock row pointing at a W2 item is matched and searchable.
    Rules: _filtered_query R1"""
    s1 = mk_stock(i9, f1)
    mk_stock(i2, f1)

    result = dao.list_filtered(db, workspace_id=w1.id, search="bolt")

    # Then 1
    assert ids(result) == [s1.id]
    # Then 2
    assert result[0].item_name == "Bolt"


# [local-coder] INV-FQ-04
def test_inv_fq_04__soft_deleted_stock_rows_are_not_matched(db, w1, f1, i1, i2, mk_stock):
    """INV-FQ-04 — soft-deleted stock rows are not matched.
    Rules: _filtered_query R2"""
    s1 = mk_stock(i1, f1)
    mk_stock(i2, f1, deleted=True)

    result = dao.list_filtered(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [s1.id]


# [local-coder] INV-FQ-05
def test_inv_fq_05__a_live_stock_row_with_is_active_false_item_active_is_matched(db, w1, f1, i1, mk_stock):
    """INV-FQ-05 — a live stock row with is_active False (item active) is matched.
    Rules: _filtered_query R2, R11c"""
    s1 = mk_stock(i1, f1, is_active=False)

    result = dao.list_filtered(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [s1.id]


# [local-coder] INV-FQ-06
def test_inv_fq_06__inventory_type_filter_keeps_only_that_type(db, w1, f1, i1, mk_stock):
    """INV-FQ-06 — inventory_type filter keeps only that type.
    Rules: _filtered_query R4"""
    mk_stock(i1, f1)
    s2 = mk_stock(i1, f1, inventory_type=DAMAGED)
    mk_stock(i1, f1, inventory_type=SCRAP)

    result = dao.list_filtered(db, workspace_id=w1.id, inventory_type=DAMAGED)

    # Then 1
    assert ids(result) == [s2.id]


# [local-coder] INV-FQ-07
def test_inv_fq_07__explicit_none_for_every_optional_filter_applies_no_filter(db, w1, f1, f2, i1, i2, mk_stock):
    """INV-FQ-07 — explicit None for every optional filter applies no filter.
    Rules: _filtered_query R3, R4, R5, R6, R8"""
    s1 = mk_stock(i1, f1)
    s2 = mk_stock(i2, f2, inventory_type=DAMAGED)

    result = dao.list_filtered(db, workspace_id=w1.id, inventory_type=None, factory_id=None, item_id=None, search=None)

    # Then 1
    assert ids(result) == [s1.id, s2.id]


# [local-coder] INV-FQ-08
def test_inv_fq_08__a_type_with_no_stock_rows_returns_nothing(db, w1, f1, i1, mk_stock):
    """INV-FQ-08 — a type with no stock rows returns nothing.
    Rules: _filtered_query R4"""
    mk_stock(i1, f1)

    result = dao.list_filtered(db, workspace_id=w1.id, inventory_type=WASTE)

    # Then 1
    assert result == []


# [local-coder] INV-FQ-09
def test_inv_fq_09__factory_id_filter_keeps_only_that_factory(db, w1, f1, f2, i1, mk_stock):
    """INV-FQ-09 — factory_id filter keeps only that factory.
    Rules: _filtered_query R5, R12"""
    mk_stock(i1, f1)
    s2 = mk_stock(i1, f2)

    result = dao.list_filtered(db, workspace_id=w1.id, factory_id=f2.id)

    # Then 1
    assert ids(result) == [s2.id]


# [local-coder] INV-FQ-11
def test_inv_fq_11__factory_id_not_exists(db, w1, f1, i1, mk_stock):
    """INV-FQ-11 — a factory id that does not exist matches nothing.
    Rules: _filtered_query R5"""
    mk_stock(i1, f1)

    result = dao.list_filtered(db, workspace_id=w1.id, factory_id=MISSING)

    # Then 1
    assert result == []


# [local-coder] INV-FQ-12
def test_inv_fq_12__a_factory_whose_stock_is_all_in_another_workspace_matches_nothing(db, w1, w2, f1, f9, i1, i9, mk_stock):
    """INV-FQ-12 — a factory whose stock is all in another workspace matches nothing.
    Rules: _filtered_query R5, R1"""
    mk_stock(i1, f1)
    mk_stock(i9, f9, workspace_id=w2.id)

    result = dao.list_filtered(db, workspace_id=w1.id, factory_id=f9.id)

    # Then 1
    assert result == []


# [local-coder] INV-FQ-13
def test_inv_fq_13__item_id_filter_keeps_only_that_item(db, w1, f1, i1, i2, mk_stock):
    """INV-FQ-13 — item_id filter keeps only that item.
    Rules: _filtered_query R6"""
    mk_stock(i1, f1)
    s2 = mk_stock(i2, f1)

    result = dao.list_filtered(db, workspace_id=w1.id, item_id=i2.id)

    # Then 1
    assert ids(result) == [s2.id]


# [local-coder] INV-FQ-14
def test_inv_fq_14__item_id_0_filters_and_matches_nothing(db, w1, f1, i1, i2, mk_stock):
    """INV-FQ-14 — item_id 0 filters and matches nothing.
    Rules: _filtered_query R6"""
    mk_stock(i1, f1)
    mk_stock(i2, f1)

    result = dao.list_filtered(db, workspace_id=w1.id, item_id=0)

    # Then 1
    assert result == []


# [local-coder] INV-FQ-15
def test_inv_fq_15__by_default_only_rows_with_qty_above_zero_are_matched(db, w1, f1, f2, i1, i2, mk_stock):
    """INV-FQ-15 — by default only rows with qty above zero are matched.
    Rules: _filtered_query R7"""
    s1 = mk_stock(i1, f1, qty=1)
    mk_stock(i2, f1, qty=0)
    mk_stock(i1, f2, qty=-2)

    result = dao.list_filtered(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [s1.id]


# [local-coder] INV-FQ-16
def test_inv_fq_16__include_zero_qty_true_matches_zero_and_negative_quantities(db, w1, f1, f2, i1, i2, mk_stock):
    """INV-FQ-16 — include_zero_qty True matches zero and negative quantities too.
    Rules: _filtered_query R7"""
    s1 = mk_stock(i1, f1, qty=1)
    s2 = mk_stock(i2, f1, qty=0)
    s3 = mk_stock(i1, f2, qty=-2)

    result = dao.list_filtered(db, workspace_id=w1.id, include_zero_qty=True)

    # Then 1
    assert ids(result) == [s1.id, s2.id, s3.id]


# [local-coder] INV-FQ-17
def test_inv_fq_17__empty_search_text_applies_no_search(db, w1, f1, i1, i2, mk_stock):
    """INV-FQ-17 — empty search text applies no search.
    Rules: _filtered_query R8"""
    s1 = mk_stock(i1, f1)
    s2 = mk_stock(i2, f1)

    result = dao.list_filtered(db, workspace_id=w1.id, search="")

    # Then 1
    assert ids(result) == [s1.id, s2.id]


# [local-coder] INV-FQ-18
def test_inv_fq_18__whitespace_only_search_text_applies_no_search(db, w1, f1, i1, i2, mk_stock):
    """INV-FQ-18 — whitespace-only search text applies no search.
    Rules: _filtered_query R8"""
    s1 = mk_stock(i1, f1)
    s2 = mk_stock(i2, f1)

    result = dao.list_filtered(db, workspace_id=w1.id, search="   ")

    # Then 1
    assert ids(result) == [s1.id, s2.id]


# [local-coder] INV-FQ-19
def test_inv_fq_19__search_is_trimmed_and_matches_the_item_name_case_insensitively_anywhere_in_it(db, w1, f1, i1, i2, mk_item, mk_stock):
    """INV-FQ-19 — search is trimmed and matches the item name case-insensitively anywhere in it.
    Rules: _filtered_query R9"""
    ia = mk_item("Big Bolts M8")
    s1 = mk_stock(ia, f1)
    s2 = mk_stock(i1, f1)
    mk_stock(i2, f1)

    result = dao.list_filtered(db, workspace_id=w1.id, search=" BOLT ")

    # Then 1
    assert ids(result) == [s1.id, s2.id]


# [local-coder] INV-FQ-20
def test_inv_fq_20__search_matches_item_unit_case_insensitively_anywhere_in_it(db, w1, f1, i2, mk_item, mk_stock):
    """INV-FQ-20 — search matches the item unit case-insensitively anywhere in it.
    Rules: _filtered_query R9"""
    ia = mk_item("Wire", unit="kg")
    s1 = mk_stock(i2, f1)
    mk_stock(ia, f1)

    result = dao.list_filtered(db, workspace_id=w1.id, search="C")

    # Then 1
    assert ids(result) == [s1.id]


# [local-coder] INV-FQ-22
def test_inv_fq_22__inner_whitespace_of_the_search_text_is_kept(db, w1, f1, mk_item, mk_stock):
    """INV-FQ-22 — inner whitespace of the search text is kept.
    Rules: _filtered_query R9"""
    ia = mk_item("Hex Bolt")
    ib = mk_item("HexBolt")
    s1 = mk_stock(ia, f1)
    mk_stock(ib, f1)

    result = dao.list_filtered(db, workspace_id=w1.id, search="x b")

    # Then 1
    assert ids(result) == [s1.id]


# [local-coder] INV-FQ-24
@pytest.mark.xfail(strict=True, reason="BUG-702: Inventory/stats search text acts as SQL wildcards")
def test_inv_fq_24__percent_in_search_matched_literal(db, w1, f1, i2, mk_item, mk_stock):
    """INV-FQ-24 — a percent sign in the search text is matched literally.
    Rules: _filtered_query R9 [BUG-702]"""
    ia = mk_item("50% Mix")
    s1 = mk_stock(ia, f1)
    mk_stock(i2, f1)

    result = dao.list_filtered(db, workspace_id=w1.id, search="%")

    # Then 1
    assert ids(result) == [s1.id]


# [local-coder] INV-FQ-25
@pytest.mark.xfail(strict=True, reason="BUG-702: Inventory/stats search text acts as SQL wildcards")
def test_inv_fq_25__underscore_in_search_text_matched_literally(db, w1, f1, i2, mk_item, mk_stock):
    """INV-FQ-25 — an underscore in the search text is matched literally.
    Rules: _filtered_query R9 [BUG-702]"""
    ia = mk_item("_x Rod")
    s1 = mk_stock(ia, f1)
    mk_stock(i2, f1)

    result = dao.list_filtered(db, workspace_id=w1.id, search="_")

    # Then 1
    assert ids(result) == [s1.id]


# [local-coder] INV-FQ-27
def test_inv_fq_27__text_containing_a_percent_sign_finds_the_item_whose_name_contains_it(db, w1, f1, i2, mk_item, mk_stock):
    """INV-FQ-27 — text containing a percent sign finds the item whose name contains it.
    Rules: _filtered_query R9"""
    ia = mk_item("50% Mix")
    s1 = mk_stock(ia, f1)
    mk_stock(i2, f1)

    result = dao.list_filtered(db, workspace_id=w1.id, search="50%")

    # Then 1
    assert ids(result) == [s1.id]


# [local-coder] INV-FQ-28
def test_inv_fq_28__text_containing_an_underscore_finds_the_item_whose_name_contains_it(db, w1, f1, i2, mk_item, mk_stock):
    """INV-FQ-28 — text containing an underscore finds the item whose name contains it.
    Rules: _filtered_query R9"""
    ia = mk_item("_x Rod")
    s1 = mk_stock(ia, f1)
    mk_stock(i2, f1)

    result = dao.list_filtered(db, workspace_id=w1.id, search="_x")

    # Then 1
    assert ids(result) == [s1.id]


# [local-coder] INV-FQ-29
def test_inv_fq_29__type_factory_and_item_filters_combine_with_and(db, w1, f1, f2, i1, i2, mk_stock):
    """INV-FQ-29 — type, factory and item filters combine with AND.
    Rules: _filtered_query R10"""
    s1 = mk_stock(i1, f1)
    mk_stock(i1, f2)
    mk_stock(i1, f1, inventory_type=DAMAGED)
    mk_stock(i2, f1)

    result = dao.list_filtered(db, workspace_id=w1.id, inventory_type=STORAGE, factory_id=f1.id, item_id=i1.id)

    # Then 1
    assert ids(result) == [s1.id]


# [local-coder] INV-FQ-30
def test_inv_fq_30__search_combines_with_and_with_type_factory_and_quantity_filters(db, w1, f1, f2, i1, i2, mk_item, mk_stock):
    """INV-FQ-30 — search combines with AND with the type, factory and quantity filters.
    Rules: _filtered_query R10"""
    ia = mk_item("Bolt Long")
    s1 = mk_stock(i1, f1)
    mk_stock(i1, f2)
    mk_stock(i2, f1)
    mk_stock(i1, f1, inventory_type=DAMAGED)
    mk_stock(ia, f1, qty=0)

    result = dao.list_filtered(db, workspace_id=w1.id, search="bolt", factory_id=f1.id, inventory_type=STORAGE)

    # Then 1
    assert ids(result) == [s1.id]


# [local-coder] INV-FQ-32
@pytest.mark.xfail(strict=True, reason="BUG-883: Stock of a catalog item removed from the catalog is still listed, counted, included in the")
def test_inv_fq_32__removed_item_id_not_matched(db, w1, f1, i1, mk_item, mk_stock):
    """INV-FQ-32 — stock of a removed item is not matched by that item's own id.
    Rules: _filtered_query R11 [BUG-883]; list_filtered R1b [BUG-883]"""
    ia = mk_item("Old Gasket", is_active=False)
    mk_stock(i1, f1)
    mk_stock(ia, f1, qty=12)

    result = dao.list_filtered(db, workspace_id=w1.id, item_id=ia.id)

    # Then 1
    assert result == []


# [local-coder] INV-FQ-33
@pytest.mark.xfail(strict=True, reason="BUG-883: Stock of a catalog item removed from the catalog is still listed, counted, included in the")
def test_inv_fq_33__removed_item_not_found_by_search(db, w1, f1, i1, mk_item, mk_stock):
    """INV-FQ-33 — stock of a removed item is not found by a search for its name.
    Rules: _filtered_query R11 [BUG-883]; list_filtered R1b [BUG-883]"""
    ia = mk_item("Old Gasket", is_active=False)
    mk_stock(i1, f1)
    mk_stock(ia, f1, qty=12)

    result = dao.list_filtered(db, workspace_id=w1.id, search="gasket")

    # Then 1
    assert result == []


# [local-coder] INV-FQ-34
@pytest.mark.xfail(strict=True, reason="BUG-883: Stock of a catalog item removed from the catalog is still listed, counted, included in the")
def test_inv_fq_34__removed_item_stays_hidden(db, w1, f1, i1, mk_item, mk_stock):
    """INV-FQ-34 — stock of a removed item stays hidden whatever the other filters.
    Rules: _filtered_query R11 [BUG-883]"""
    ia = mk_item("Old Gasket", is_active=False)
    s1 = mk_stock(i1, f1)
    mk_stock(ia, f1, qty=12)

    result = dao.list_filtered(db, workspace_id=w1.id, inventory_type=STORAGE, factory_id=f1.id, include_zero_qty=True)

    # Then 1
    assert ids(result) == [s1.id]


# [local-coder] INV-FQ-37
@pytest.mark.xfail(strict=True, reason="BUG-882: Stock held in a soft-deleted factory is still listed, counted and included in the stock st")
def test_inv_fq_37__stock_in_soft_deleted_factory_not_matched_by_factory_id(db, w1, f1, i1, mk_factory, mk_stock):
    """INV-FQ-37 — stock in a soft-deleted factory is not matched by that factory's own id.
    Rules: _filtered_query R11a [BUG-882]; list_filtered R1a [BUG-882]"""
    fa = mk_factory("Old Plant", "OP", is_active=True, is_deleted=True)
    mk_stock(i1, f1)
    mk_stock(i1, fa, qty=30)

    result = dao.list_filtered(db, workspace_id=w1.id, factory_id=fa.id)

    # Then 1
    assert result == []


# [local-coder] INV-FQ-38
@pytest.mark.xfail(strict=True, reason="BUG-882: Stock held in a soft-deleted factory is still listed, counted and included in the stock st")
def test_inv_fq_38__stock_in_soft_deleted_factory_stays_hidden(db, w1, f1, i1, mk_factory, mk_stock):
    """INV-FQ-38 — stock in a soft-deleted factory stays hidden whatever the other filters.
    Rules: _filtered_query R11a [BUG-882]"""
    fa = mk_factory("Old Plant", "OP", is_active=True, is_deleted=True)
    s1 = mk_stock(i1, f1)
    mk_stock(i1, fa, qty=30)

    result = dao.list_filtered(db, workspace_id=w1.id, inventory_type=STORAGE, item_id=i1.id, search="bolt", include_zero_qty=True)

    # Then 1
    assert ids(result) == [s1.id]


# [local-coder] INV-FQ-39
def test_inv_fq_39__stock_in_an_inactive_but_live_factory_is_matched(db, w1, f1, i1, mk_factory, mk_stock):
    """INV-FQ-39 — stock in an inactive but live factory is matched.
    Rules: _filtered_query R11b"""
    fb = mk_factory("Idle Plant", "IP", is_active=False, is_deleted=False)
    s1 = mk_stock(i1, fb)
    s2 = mk_stock(i1, f1)

    result = dao.list_filtered(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [s1.id, s2.id]


# [local-coder] INV-FQ-40
def test_inv_fq_40__listing_leaves_the_stock_row_of_a_soft_deleted_factory_untouched(db, w1, f1, i1, mk_factory, mk_stock):
    """INV-FQ-40 — listing leaves the stock row of a soft-deleted factory untouched.
    Rules: _filtered_query R11b"""
    fa = mk_factory("Old Plant", "OP", is_active=True, is_deleted=True)
    s1 = mk_stock(i1, f1)
    s2 = mk_stock(i1, fa, qty=30)
    before_s2 = snap(db, s2)

    result = dao.list_filtered(db, workspace_id=w1.id)

    # Then 1
    assert s1.id in ids(result)
    # Then 2
    assert snap(db, s2) == before_s2
    # Then 3
    row = reread(db, s2)
    assert row.is_deleted is False
    assert row.qty == 30
    assert row.factory_id == fa.id
    # Then 4
    assert row.avg_price == Decimal("2.00")
    # Then 5
    assert count_rows(db, Inventory) == 2


# [local-coder] INV-L-01
def test_inv_l_01__returns_a_list_of_inventory_rows_with_the_item_loaded(db, w1, f1, i1, mk_stock):
    """INV-L-01 — returns a list of Inventory rows with the item loaded.
    Rules: list_filtered R1"""
    s1 = mk_stock(i1, f1)

    result = dao.list_filtered(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert len(result) == 1
    # Then 3
    assert isinstance(result[0], Inventory)
    # Then 4
    assert result[0].id == s1.id
    # Then 5
    assert result[0].item_name == "Bolt"
    # Then 6
    assert result[0].item_unit == "pcs"


# [local-coder] INV-L-02
def test_inv_l_02__rows_are_ordered_by_item_name_ignoring_case(db, w1, f1, mk_item, mk_stock):
    """INV-L-02 — rows are ordered by item name ignoring case.
    Rules: list_filtered R2"""
    ia = mk_item("Zulu")
    ib = mk_item("apple")
    ic = mk_item("Banana")
    mk_stock(ia, f1)
    mk_stock(ib, f1)
    mk_stock(ic, f1)

    result = dao.list_filtered(db, workspace_id=w1.id)

    # Then 1
    assert names(result) == ["apple", "Banana", "Zulu"]


# [local-coder] INV-L-03
def test_inv_l_03__rows_of_same_item_lower_id_first_after_earlier_names(db, w1, f1, f2, i1, mk_item, mk_stock):
    """INV-L-03 — rows of the same item come back lower id first, after earlier names.
    Rules: list_filtered R2"""
    ia = mk_item("Apple")
    s1 = mk_stock(i1, f2)
    s2 = mk_stock(i1, f1)
    s3 = mk_stock(ia, f1)

    result = dao.list_filtered(db, workspace_id=w1.id)

    # Then 1
    assert [row.id for row in result] == [s3.id, s1.id, s2.id]


# [local-coder] INV-L-05
def test_inv_l_05__item_names_differing_only_in_case_come_back_in_stock_row_id_order(db, w1, f1, i1, mk_item, mk_stock):
    """INV-L-05 — item names differing only in case come back in stock-row id order (lower case first).
    Rules: list_filtered R2"""
    ib = mk_item("bolt", name_normalized="bolt lower")
    mk_stock(ib, f1)
    mk_stock(i1, f1)

    result = dao.list_filtered(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert names(result) == ["bolt", "Bolt"]


# [local-coder] INV-L-07
def test_inv_l_07__second_window_of_two_continues_without_repeat_or_gap(db, w1, f1, mk_item, mk_stock):
    """INV-L-07 — second window of two continues without repeat or gap.
    Rules: list_filtered R3"""
    ia = mk_item("Echo")
    ib = mk_item("Delta")
    ic = mk_item("Charlie")
    id_ = mk_item("Bravo")
    ie = mk_item("Alpha")
    mk_stock(ia, f1)
    mk_stock(ib, f1)
    mk_stock(ic, f1)
    mk_stock(id_, f1)
    mk_stock(ie, f1)

    result = dao.list_filtered(db, workspace_id=w1.id, skip=2, limit=2)

    # Then 1
    assert names(result) == ["Charlie", "Delta"]


# [local-coder] INV-L-08
def test_inv_l_08__last_window_is_short(db, w1, f1, mk_item, mk_stock):
    """INV-L-08 — last window is short.
    Rules: list_filtered R3"""
    ia = mk_item("Echo")
    ib = mk_item("Delta")
    ic = mk_item("Charlie")
    id_ = mk_item("Bravo")
    ie = mk_item("Alpha")
    mk_stock(ia, f1)
    mk_stock(ib, f1)
    mk_stock(ic, f1)
    mk_stock(id_, f1)
    mk_stock(ie, f1)

    result = dao.list_filtered(db, workspace_id=w1.id, skip=4, limit=2)

    # Then 1
    assert names(result) == ["Echo"]


# [local-coder] INV-L-09
def test_inv_l_09__skip_and_limit_are_applied_after_filtering(db, w1, f1, mk_item, mk_stock):
    """INV-L-09 — skip and limit are applied after filtering.
    Rules: list_filtered R3"""
    ia = mk_item("Echo")
    ib = mk_item("Delta")
    ic = mk_item("Charlie")
    id_ = mk_item("Bravo")
    ie = mk_item("Alpha")
    mk_stock(ia, f1)
    mk_stock(ib, f1)
    mk_stock(ic, f1, qty=0)
    mk_stock(id_, f1)
    mk_stock(ie, f1, qty=0)

    result = dao.list_filtered(db, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert names(result) == ["Delta"]


# [local-coder] INV-L-11
def test_inv_l_11__explicit_limit_101_returns_all_101_rows(db, w1, f1, mk_item, mk_stock):
    """INV-L-11 — an explicit limit of 101 returns all 101 rows.
    Rules: list_filtered R3"""
    for n in range(1, 102):
        item = mk_item(f"Item {n:03d}")
        mk_stock(item, f1)

    result = dao.list_filtered(db, workspace_id=w1.id, limit=101)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert names(result)[-1] == "Item 101"


# [local-coder] INV-L-12
def test_inv_l_12__limit_0_returns_empty_list(db, w1, f1, i1, mk_stock):
    """INV-L-12 — limit 0 returns an empty list.
    Rules: list_filtered R4"""
    mk_stock(i1, f1)

    result = dao.list_filtered(db, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [local-coder] INV-L-13
def test_inv_l_13__skip_equal_to_matching_rows_returns_empty(db, w1, f1, i1, i2, mk_stock):
    """INV-L-13 — skip equal to the number of matching rows returns an empty list.
    Rules: list_filtered R4"""
    mk_stock(i1, f1)
    mk_stock(i2, f1)

    result = dao.list_filtered(db, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [local-coder] INV-L-14
def test_inv_l_14__skip_one_below_the_number_of_matching_rows_returns_the_last_row(db, w1, f1, i1, i2, mk_stock):
    """INV-L-14 — skip one below the number of matching rows returns the last row.
    Rules: list_filtered R4, R3"""
    mk_stock(i1, f1)
    s2 = mk_stock(i2, f1)

    result = dao.list_filtered(db, workspace_id=w1.id, skip=1)

    # Then 1
    assert ids(result) == [s2.id]


# [local-coder] INV-L-15
def test_inv_l_15__a_workspace_with_no_stock_rows_returns_an_empty_list(db, w2, f1, i1, mk_stock):
    """INV-L-15 — a workspace with no stock rows returns an empty list.
    Rules: list_filtered R4"""
    mk_stock(i1, f1)

    result = dao.list_filtered(db, workspace_id=w2.id)

    # Then 1
    assert result == []


# [local-coder] INV-L-16
def test_inv_l_16__unknown_workspace_id_returns_empty_list(db, f1, i1, mk_stock):
    """INV-L-16 — an unknown workspace id returns an empty list.
    Rules: list_filtered R4"""
    mk_stock(i1, f1)

    result = dao.list_filtered(db, workspace_id=MISSING)

    # Then 1
    assert result == []


# [local-coder] INV-L-19
@pytest.mark.xfail(strict=True, reason="BUG-882: Stock held in a soft-deleted factory is still listed, counted and included in the stock st")
def test_inv_l_19__a_row_in_a_soft_deleted_factory_does_not_use_up_a_place_in_the_page(db, w1, f1, i1, mk_factory, mk_stock):
    """INV-L-19 — a row in a soft-deleted factory does not use up a place in the page.
    Rules: list_filtered R1a [BUG-882]"""
    fa = mk_factory("Old Plant", "OP", is_active=True, is_deleted=True)
    mk_stock(i1, fa, qty=30)
    s2 = mk_stock(i1, f1)

    result = dao.list_filtered(db, workspace_id=w1.id, limit=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id == s2.id


# [local-coder] INV-L-20
def test_inv_l_20__with_limit_1_the_live_factory_row_is_returned_when_it_has_the_lower_id(db, w1, f1, i1, mk_factory, mk_stock):
    """INV-L-20 — with limit 1 the live-factory row is returned when it has the lower id.
    Rules: list_filtered R1, R3"""
    fa = mk_factory("Old Plant", "OP", is_active=True, is_deleted=True)
    s1 = mk_stock(i1, f1)
    mk_stock(i1, fa, qty=30)

    result = dao.list_filtered(db, workspace_id=w1.id, limit=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id == s1.id


# [local-coder] INV-L-21
@pytest.mark.xfail(strict=True, reason="BUG-883: Stock of a catalog item removed from the catalog is still listed, counted, included in the")
def test_inv_l_21__a_row_of_a_removed_item_does_not_use_up_a_place_in_the_page(db, w1, f1, i1, mk_item, mk_stock):
    """INV-L-21 — a row of a removed item does not use up a place in the page.
    Rules: list_filtered R1b [BUG-883]"""
    ia = mk_item("Anvil", is_active=False)
    mk_stock(ia, f1, qty=12)
    s2 = mk_stock(i1, f1)

    result = dao.list_filtered(db, workspace_id=w1.id, limit=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id == s2.id


# [local-coder] INV-L-22
def test_inv_l_22__with_limit_1_the_active_items_row_is_returned_when_its_name_sorts_first(db, w1, f1, i1, mk_item, mk_stock):
    """INV-L-22 — with limit 1 the active item's row is returned when its name sorts first.
    Rules: list_filtered R1, R3"""
    ia = mk_item("Old Gasket", is_active=False)
    s1 = mk_stock(i1, f1)
    mk_stock(ia, f1, qty=12)

    result = dao.list_filtered(db, workspace_id=w1.id, limit=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id == s1.id


# [local-coder] INV-CNT-01
def test_inv_cnt_01__counts_stock_rows_not_distinct_items(db, w1, f1, f2, i1, i2, mk_stock):
    """INV-CNT-01 — counts stock rows, not distinct items.
    Rules: count_filtered R1"""
    mk_stock(i1, f1)
    mk_stock(i1, f2)
    mk_stock(i2, f1)

    result = dao.count_filtered(db, workspace_id=w1.id)

    # Then 1
    assert result == 3
    # Then 2
    assert type(result) is int


# [local-coder] INV-CNT-03
def test_inv_cnt_03__include_zero_qty_true_counts_zero_qty_row(db, w1, w2, f1, f2, f9, i1, i2, i9, mk_stock):
    """INV-CNT-03 — include_zero_qty True also counts the zero-quantity row.
    Rules: count_filtered R1; _filtered_query R7"""
    mk_stock(i1, f1)
    mk_stock(i2, f1, deleted=True)
    mk_stock(i1, f2, qty=0)
    mk_stock(i9, f9, workspace_id=w2.id)

    result = dao.count_filtered(db, workspace_id=w1.id, include_zero_qty=True)

    # Then 1
    assert result == 2


# [local-coder] INV-CNT-04
def test_inv_cnt_04__type_and_factory_filters_apply_to_the_count(db, w1, f1, f2, i1, mk_stock):
    """INV-CNT-04 — type and factory filters apply to the count.
    Rules: count_filtered R1; _filtered_query R4, R5, R10"""
    mk_stock(i1, f1)
    mk_stock(i1, f1, inventory_type=DAMAGED)
    mk_stock(i1, f2, inventory_type=DAMAGED)

    result = dao.count_filtered(db, workspace_id=w1.id, inventory_type=DAMAGED, factory_id=f1.id)

    # Then 1
    assert result == 1


# [local-coder] INV-CNT-05
def test_inv_cnt_05__item_filter_applies_to_the_count(db, w1, f1, f2, i1, i2, mk_stock):
    """INV-CNT-05 — item filter applies to the count.
    Rules: count_filtered R1; _filtered_query R6"""
    mk_stock(i1, f1)
    mk_stock(i2, f1)
    mk_stock(i2, f2)

    result = dao.count_filtered(db, workspace_id=w1.id, item_id=i2.id)

    # Then 1
    assert result == 2


# [local-coder] INV-CNT-06
def test_inv_cnt_06__search_applies_to_the_count(db, w1, f1, f2, i1, i2, mk_stock):
    """INV-CNT-06 — search applies to the count.
    Rules: count_filtered R1; _filtered_query R9"""
    mk_stock(i1, f1)
    mk_stock(i2, f1)
    mk_stock(i2, f2)

    result = dao.count_filtered(db, workspace_id=w1.id, search=" NUT ")

    # Then 1
    assert result == 2


# [local-coder] INV-CNT-07
@pytest.mark.xfail(strict=True, reason="BUG-880: Inventory list / count / stats treat factory_id=0 as 'no factory filter'")
def test_inv_cnt_07__factory_id_0_counts_nothing(db, w1, f1, f2, i1, mk_stock):
    """INV-CNT-07 — factory_id 0 counts nothing.
    Rules: count_filtered R1; _filtered_query R5 [BUG-880]"""
    mk_stock(i1, f1)
    mk_stock(i1, f2)

    result = dao.count_filtered(db, workspace_id=w1.id, factory_id=0)

    # Then 1
    assert result == 0


# [local-coder] INV-CNT-08
def test_inv_cnt_08__a_workspace_with_no_stock_rows_counts_0_as_an_int(db, w2, f1, i1, mk_stock):
    """INV-CNT-08 — a workspace with no stock rows counts 0 as an int.
    Rules: count_filtered R2"""
    mk_stock(i1, f1)

    result = dao.count_filtered(db, workspace_id=w2.id)

    # Then 1
    assert result == 0
    # Then 2
    assert type(result) is int


# [local-coder] INV-CNT-09
def test_inv_cnt_09__unknown_workspace_id_counts_0_as_an_int(db, f1, i1, mk_stock):
    """INV-CNT-09 — an unknown workspace id counts 0 as an int.
    Rules: count_filtered R2"""
    mk_stock(i1, f1)

    result = dao.count_filtered(db, workspace_id=MISSING)

    # Then 1
    assert result == 0
    # Then 2
    assert type(result) is int


# [local-coder] INV-CNT-10
@pytest.mark.xfail(strict=True, reason="BUG-882: Stock held in a soft-deleted factory is still listed, counted and included in the stock st")
def test_inv_cnt_10__stock_in_soft_deleted_factory_not_counted(db, w1, f1, i1, mk_factory, mk_stock):
    """INV-CNT-10 — stock in a soft-deleted factory is not counted.
    Rules: count_filtered R1a [BUG-882]; _filtered_query R11a [BUG-882]"""
    fa = mk_factory("Old Plant", "OP", is_active=True, is_deleted=True)
    mk_stock(i1, f1)
    mk_stock(i1, fa, qty=30)

    result = dao.count_filtered(db, workspace_id=w1.id)

    # Then 1
    assert result == 1


# [local-coder] INV-CNT-11
@pytest.mark.xfail(strict=True, reason="BUG-882: Stock held in a soft-deleted factory is still listed, counted and included in the stock st")
def test_inv_cnt_11__filtering_by_a_soft_deleted_factory_counts_nothing(db, w1, f1, i1, mk_factory, mk_stock):
    """INV-CNT-11 — filtering by a soft-deleted factory counts nothing.
    Rules: count_filtered R1a [BUG-882]; _filtered_query R11a [BUG-882]"""
    fa = mk_factory("Old Plant", "OP", is_active=True, is_deleted=True)
    mk_stock(i1, f1)
    mk_stock(i1, fa, qty=30)

    result = dao.count_filtered(db, workspace_id=w1.id, factory_id=fa.id)

    # Then 1
    assert result == 0


# [local-coder] INV-CNT-12
@pytest.mark.xfail(strict=True, reason="BUG-883: Stock of a catalog item removed from the catalog is still listed, counted, included in the")
def test_inv_cnt_12__stock_of_removed_catalog_item_is_not_counted(db, w1, f1, i1, mk_item, mk_stock):
    """INV-CNT-12 — stock of a removed catalog item is not counted.
    Rules: count_filtered R1b [BUG-883]; _filtered_query R11 [BUG-883]"""
    ia = mk_item("Old Gasket", is_active=False)
    mk_stock(i1, f1)
    mk_stock(ia, f1, qty=12)

    result = dao.count_filtered(db, workspace_id=w1.id)

    # Then 1
    assert result == 1


# [local-coder] INV-CNT-14
@pytest.mark.xfail(strict=True, reason="BUG-883: Stock of a catalog item removed from the catalog is still listed, counted, included in the")
def test_inv_cnt_14__searching_for_a_removed_items_name_counts_nothing(db, w1, f1, i1, mk_item, mk_stock):
    """INV-CNT-14 — searching for a removed item's name counts nothing.
    Rules: count_filtered R1b [BUG-883]; _filtered_query R11 [BUG-883]"""
    ia = mk_item("Old Gasket", is_active=False)
    mk_stock(i1, f1)
    mk_stock(ia, f1, qty=12)

    result = dao.count_filtered(db, workspace_id=w1.id, search="gasket")

    # Then 1
    assert result == 0


# [local-coder] INV-CNT-15
def test_inv_cnt_15__stock_in_an_inactive_but_live_factory_is_counted(db, w1, f1, i1, mk_factory, mk_stock):
    """INV-CNT-15 — stock in an inactive but live factory is counted.
    Rules: count_filtered R1; _filtered_query R11b"""
    fb = mk_factory("Idle Plant", "IP", workspace_id=w1.id, is_active=False, is_deleted=False)
    mk_stock(i1, fb)
    mk_stock(i1, f1)

    result = dao.count_filtered(db, workspace_id=w1.id)

    # Then 1
    assert result == 2


# [local-coder] INV-ST-02
def test_inv_st_02__per_type_rows_count_distinct_items_and_sum_qty(db, w1, f1, f2, i1, i2, mk_stock):
    """INV-ST-02 — per-type rows count distinct items and sum quantity.
    Rules: stats_filtered R5, R2, R3"""
    mk_stock(i1, f1, qty=5)
    mk_stock(i1, f2, qty=4)
    mk_stock(i2, f1, qty=1)
    mk_stock(i1, f1, inventory_type=SCRAP, qty=3)

    result = dao.stats_filtered(db, workspace_id=w1.id)

    # Then 1
    assert result[0] == 4
    # Then 2
    assert result[1] == 13
    # Then 3
    assert result[2] == Decimal("26.00")
    # Then 4
    assert by_type(result) == {(STORAGE, 2, 10), (SCRAP, 1, 3)}
    # Then 5
    assert len(result[3]) == 2


# [local-coder] INV-ST-04
def test_inv_st_04__include_zero_qty_true_zero_rows_count_and_negative_rows_subtract(db, w1, f1, f2, i1, i2, mk_stock):
    """INV-ST-04 — include_zero_qty True: zero rows count and negative rows subtract.
    Rules: stats_filtered R1, R3, R4"""
    mk_stock(i1, f1)
    mk_stock(i2, f1, qty=0, avg_price=Decimal("3.00"))
    mk_stock(i1, f2, qty=-2, avg_price=Decimal("1.00"))

    result = dao.stats_filtered(db, workspace_id=w1.id, include_zero_qty=True)

    # Then 1
    assert result[0] == 3
    # Then 2
    assert result[1] == 3
    # Then 3
    assert result[2] == Decimal("8.00")
    # Then 4
    assert by_type(result) == {(STORAGE, 2, 3)}


# [local-coder] INV-ST-05
def test_inv_st_05__default_zero_and_negative_rows_are_left_out_of_every_part(db, w1, f1, f2, i1, i2, mk_stock):
    """INV-ST-05 — default: zero and negative rows are left out of every part.
    Rules: stats_filtered R1, R3, R4; _filtered_query R7"""
    mk_stock(i1, f1)
    mk_stock(i2, f1, qty=0, avg_price=Decimal("3.00"))
    mk_stock(i1, f2, qty=-2, avg_price=Decimal("1.00"))

    result = dao.stats_filtered(db, workspace_id=w1.id)

    # Then 1
    assert result[0] == 1
    # Then 2
    assert result[1] == 5
    # Then 3
    assert result[2] == Decimal("10.00")
    # Then 4
    assert by_type(result) == {(STORAGE, 1, 5)}


# [local-coder] INV-ST-06
def test_inv_st_06__include_zero_qty_true(db, w1, f1, i1, mk_stock):
    """INV-ST-06 — include_zero_qty True: a type whose only row has qty 0 appears with total 0.
    Rules: stats_filtered R5"""
    mk_stock(i1, f1)
    mk_stock(i1, f1, inventory_type=DAMAGED, qty=0)

    result = dao.stats_filtered(db, workspace_id=w1.id, include_zero_qty=True)

    # Then 1
    assert result[0] == 2
    # Then 2
    assert by_type(result) == {(STORAGE, 1, 5), (DAMAGED, 1, 0)}
    # Then 3
    assert len(result[3]) == 2


# [local-coder] INV-ST-07
def test_inv_st_07__a_type_with_no_matched_row_is_absent_from_the_per_type_rows(db, w1, f1, i1, mk_stock):
    """INV-ST-07 — a type with no matched row is absent from the per-type rows.
    Rules: stats_filtered R5"""
    mk_stock(i1, f1)
    mk_stock(i1, f1, inventory_type=DAMAGED, qty=0)

    result = dao.stats_filtered(db, workspace_id=w1.id)

    # Then 1
    assert result[0] == 1
    # Then 2
    assert by_type(result) == {(STORAGE, 1, 5)}
    # Then 3
    assert len(result[3]) == 1


# [local-coder] INV-ST-08
def test_inv_st_08__a_workspace_with_no_stock_rows_gives_zeros_and_an_empty_list(db, w2, f1, i1, mk_stock):
    """INV-ST-08 — a workspace with no stock rows gives zeros and an empty list.
    Rules: stats_filtered R7"""
    mk_stock(i1, f1)

    result = dao.stats_filtered(db, workspace_id=w2.id)

    # Then 1
    assert result == (0, 0, Decimal("0"), [])
    # Then 2
    assert type(result[0]) is int
    # Then 3
    assert type(result[1]) is int
    # Then 4
    assert isinstance(result[2], Decimal)
    # Then 5
    assert isinstance(result[3], list)


# [local-coder] INV-ST-09
def test_inv_st_09__unknown_workspace_id_gives_zeros_and_empty_list(db, f1, i1, mk_stock):
    """INV-ST-09 — an unknown workspace id gives zeros and an empty list.
    Rules: stats_filtered R7"""
    mk_stock(i1, f1)

    result = dao.stats_filtered(db, workspace_id=MISSING)

    # Then 1
    assert result == (0, 0, Decimal("0"), [])
    # Then 2
    assert type(result[0]) is int
    # Then 3
    assert type(result[1]) is int
    # Then 4
    assert isinstance(result[2], Decimal)
    # Then 5
    assert isinstance(result[3], list)


# [local-coder] INV-ST-10
def test_inv_st_10__filters_matching_no_row_give_zeros_and_an_empty_list(db, w1, f1, i1, mk_stock):
    """INV-ST-10 — filters matching no row give zeros and an empty list.
    Rules: stats_filtered R7"""
    mk_stock(i1, f1)

    result = dao.stats_filtered(db, workspace_id=w1.id, inventory_type=WASTE)

    # Then 1
    assert result == (0, 0, Decimal("0"), [])
    # Then 2
    assert type(result[0]) is int
    # Then 3
    assert type(result[1]) is int
    # Then 4
    assert isinstance(result[2], Decimal)
    # Then 5
    assert isinstance(result[3], list)


# [local-coder] INV-ST-11
def test_inv_st_11__when_every_matched_price_is_null_the_value_is_decimal_zero_not_none(db, w1, f1, i1, i2, mk_stock):
    """INV-ST-11 — when every matched price is NULL the value is Decimal zero, not None.
    Rules: stats_filtered R8, R4"""
    mk_stock(i1, f1, avg_price=None)
    mk_stock(i2, f1, qty=3, avg_price=None)

    result = dao.stats_filtered(db, workspace_id=w1.id)

    # Then 1
    assert result[0] == 2
    # Then 2
    assert result[1] == 8
    # Then 3
    assert result[2] == Decimal("0")
    # Then 4
    assert isinstance(result[2], Decimal)


# [local-coder] INV-ST-13
def test_inv_st_13__without_filters_the_same_rows_give_the_workspaces_live_totals(db, w1, w2, f1, f2, f9, i1, i2, i9, mk_stock):
    """INV-ST-13 — without filters the same rows give the workspace's live totals.
    Rules: stats_filtered R1, R2, R5; _filtered_query R1, R2"""
    mk_stock(i1, f1)
    mk_stock(i2, f1, deleted=True, qty=7)
    mk_stock(i1, f2, qty=4)
    mk_stock(i9, f9, workspace_id=w2.id)

    result = dao.stats_filtered(db, workspace_id=w1.id)

    # Then 1
    assert result[0] == 2
    # Then 2
    assert result[1] == 9
    # Then 3
    assert result[2] == Decimal("18.00")
    # Then 4
    assert by_type(result) == {(STORAGE, 1, 9)}


# [local-coder] INV-ST-14
def test_inv_st_14__search_applies_to_every_part(db, w1, f1, i1, i2, mk_stock):
    """INV-ST-14 — search applies to every part.
    Rules: stats_filtered R1; _filtered_query R9"""
    mk_stock(i1, f1)
    mk_stock(i2, f1, qty=3)
    mk_stock(i1, f1, inventory_type=DAMAGED, qty=2, avg_price=Decimal("4.00"))

    result = dao.stats_filtered(db, workspace_id=w1.id, search="bolt")

    # Then 1
    assert result[0] == 2
    # Then 2
    assert result[1] == 7
    # Then 3
    assert result[2] == Decimal("18.00")
    # Then 4
    assert by_type(result) == {(STORAGE, 1, 5), (DAMAGED, 1, 2)}


# [local-coder] INV-ST-15
def test_inv_st_15__type_and_item_filters_apply_to_every_part(db, w1, f1, i1, i2, mk_stock):
    """INV-ST-15 — type and item filters apply to every part.
    Rules: stats_filtered R1; _filtered_query R4, R6"""
    mk_stock(i1, f1)
    mk_stock(i2, f1, qty=3)
    mk_stock(i1, f1, inventory_type=DAMAGED, qty=2, avg_price=Decimal("4.00"))

    result = dao.stats_filtered(db, workspace_id=w1.id, inventory_type=DAMAGED, item_id=i1.id)

    # Then 1
    assert result[0] == 1
    # Then 2
    assert result[1] == 2
    # Then 3
    assert result[2] == Decimal("8.00")
    # Then 4
    assert by_type(result) == {(DAMAGED, 1, 2)}


# [local-coder] INV-ST-16
@pytest.mark.xfail(strict=True, reason="BUG-880: Inventory list / count / stats treat factory_id=0 as 'no factory filter'")
def test_inv_st_16__factory_id_0_gives_zero_statistics(db, w1, f1, f2, i1, mk_stock):
    """INV-ST-16 — factory_id 0 gives zero statistics.
    Rules: stats_filtered R1; _filtered_query R5 [BUG-880]"""
    mk_stock(i1, f1)
    mk_stock(i1, f2)

    result = dao.stats_filtered(db, workspace_id=w1.id, factory_id=0)

    # Then 1
    assert result[0] == 0
    # Then 2
    assert result[1] == 0
    # Then 3
    assert result[3] == []


# [local-coder] INV-ST-18
@pytest.mark.xfail(strict=True, reason="BUG-882: Stock held in a soft-deleted factory is still listed, counted and included in the stock st")
def test_inv_st_18__stock_in_soft_deleted_factory_adds_nothing_to_the_totals(db, w1, f1, i1, mk_factory, mk_stock):
    """INV-ST-18 — stock in a soft-deleted factory adds nothing to the totals.
    Rules: stats_filtered R1a [BUG-882]; _filtered_query R11a [BUG-882]"""
    fa = mk_factory("Old Plant", "OP", workspace_id=w1.id, is_active=True, is_deleted=True)
    mk_stock(i1, f1)
    mk_stock(i1, fa, qty=30, avg_price=Decimal("1.00"))

    result = dao.stats_filtered(db, workspace_id=w1.id)

    # Then 1
    assert result[0] == 1
    # Then 2
    assert result[1] == 5
    # Then 3
    assert result[2] == Decimal("10.00")


# [local-coder] INV-ST-19
@pytest.mark.xfail(strict=True, reason="BUG-882: Stock held in a soft-deleted factory is still listed, counted and included in the stock st")
def test_inv_st_19__factory_filter_soft_deleted_factory(db, w1, f1, i1, mk_factory, mk_stock):
    """INV-ST-19 — filtering by a soft-deleted factory gives the empty result.
    Rules: stats_filtered R1a [BUG-882]; _filtered_query R11a [BUG-882]"""
    fa = mk_factory("Old Plant", "OP", workspace_id=w1.id, is_active=True, is_deleted=True)
    mk_stock(i1, f1)
    mk_stock(i1, fa, qty=30, avg_price=Decimal("1.00"))

    result = dao.stats_filtered(db, workspace_id=w1.id, factory_id=fa.id)

    # Then 1
    assert result == (0, 0, Decimal("0"), [])


# [local-coder] INV-ST-20
@pytest.mark.xfail(strict=True, reason="BUG-882: Stock held in a soft-deleted factory is still listed, counted and included in the stock st")
def test_inv_st_20__stock_in_soft_deleted_factory_is_absent_from_the_per_type_rows(db, w1, f1, i1, i2, mk_factory, mk_stock):
    """INV-ST-20 — stock in a soft-deleted factory is absent from the per-type rows.
    Rules: stats_filtered R5a [BUG-882]; _filtered_query R11a [BUG-882]"""
    fa = mk_factory("Old Plant", "OP", is_active=True, is_deleted=True)
    mk_stock(i1, f1)
    mk_stock(i1, fa, qty=30)
    mk_stock(i2, fa, qty=2)
    mk_stock(i1, fa, inventory_type=SCRAP, qty=3)

    result = dao.stats_filtered(db, workspace_id=w1.id)

    # Then 1
    assert by_type(result) == {(STORAGE, 1, 5)}
    # Then 2
    assert len(result[3]) == 1


# [local-coder] INV-ST-21
@pytest.mark.xfail(strict=True, reason="BUG-883: Stock of a catalog item removed from the catalog is still listed, counted, included in the")
def test_inv_st_21__stock_of_removed_catalog_item_adds_nothing(db, w1, f1, i1, mk_item, mk_stock):
    """INV-ST-21 — stock of a removed catalog item adds nothing to the totals.
    Rules: stats_filtered R1b [BUG-883]; _filtered_query R11 [BUG-883]"""
    ia = mk_item("Old Gasket", is_active=False)
    mk_stock(i1, f1)
    mk_stock(ia, f1, qty=12, avg_price=Decimal("5.00"))

    result = dao.stats_filtered(db, workspace_id=w1.id)

    # Then 1
    assert result[0] == 1
    # Then 2
    assert result[1] == 5
    # Then 3
    assert result[2] == Decimal("10.00")


# [local-coder] INV-ST-22
@pytest.mark.xfail(strict=True, reason="BUG-883: Stock of a catalog item removed from the catalog is still listed, counted, included in the")
def test_inv_st_22__filtering_by_removed_item_id(db, w1, f1, i1, mk_item, mk_stock):
    """INV-ST-22 — filtering by a removed item's id gives the empty result.
    Rules: stats_filtered R1b [BUG-883]; _filtered_query R11 [BUG-883]"""
    ia = mk_item("Old Gasket", is_active=False)
    mk_stock(i1, f1)
    mk_stock(ia, f1, qty=12, avg_price=Decimal("5.00"))

    result = dao.stats_filtered(db, workspace_id=w1.id, item_id=ia.id)

    # Then 1
    assert result == (0, 0, Decimal("0"), [])


# [local-coder] INV-ST-23
@pytest.mark.xfail(strict=True, reason="BUG-883: Stock of a catalog item removed from the catalog is still listed, counted, included in the")
def test_inv_st_23__searching_for_removed_item_name_gives_empty_result(db, w1, f1, i1, mk_item, mk_stock):
    """INV-ST-23 — searching for a removed item's name gives the empty result.
    Rules: stats_filtered R1b [BUG-883]; _filtered_query R11 [BUG-883]"""
    ia = mk_item("Old Gasket", is_active=False)
    mk_stock(i1, f1)
    mk_stock(ia, f1, qty=12, avg_price=Decimal("5.00"))

    result = dao.stats_filtered(db, workspace_id=w1.id, search="gasket")

    # Then 1
    assert result == (0, 0, Decimal("0"), [])


# [local-coder] INV-ST-25
def test_inv_st_25__stock_in_inactive_but_live_factory_is_in_the_totals(db, w1, f1, i1, mk_factory, mk_stock):
    """INV-ST-25 — stock in an inactive but live factory is in the totals.
    Rules: stats_filtered R1; _filtered_query R11b"""
    fb = mk_factory("Idle Plant", "IP", is_active=False, is_deleted=False)
    mk_stock(i1, fb, qty=30)
    mk_stock(i1, f1)

    result = dao.stats_filtered(db, workspace_id=w1.id)

    # Then 1
    assert result[0] == 2
    # Then 2
    assert result[1] == 35
    # Then 3
    assert result[2] == Decimal("70.00")
    # Then 4
    assert by_type(result) == {(STORAGE, 1, 35)}


# [local-coder] INV-GIW-01
def test_inv_giw_01__returns_the_row_with_that_id_in_that_workspace(db, w1, f1, i1, i2, mk_stock):
    """INV-GIW-01 — returns the row with that id in that workspace.
    Rules: get_by_id_and_workspace R1"""
    s1 = mk_stock(i1, f1)
    mk_stock(i2, f1)

    result = dao.get_by_id_and_workspace(db, id=s1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == s1.id


# [local-coder] INV-GIW-02
def test_inv_giw_02__an_id_of_another_workspace_returns_none(db, w2, f1, i1, mk_stock):
    """INV-GIW-02 — an id of another workspace returns None.
    Rules: get_by_id_and_workspace R2"""
    s1 = mk_stock(i1, f1)

    result = dao.get_by_id_and_workspace(db, id=s1.id, workspace_id=w2.id)

    # Then 1
    assert result is None


# [local-coder] INV-GIW-03
def test_inv_giw_03__unknown_id_returns_none(db, w1, f1, i1, mk_stock):
    """INV-GIW-03 — an unknown id returns None.
    Rules: get_by_id_and_workspace R3"""
    mk_stock(i1, f1)

    result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result is None


# [local-coder] INV-GIW-04
def test_inv_giw_04__soft_deleted_row_still_returned(db, w1, f1, i1, mk_stock):
    """INV-GIW-04 — a soft-deleted row is still returned.
    Rules: get_by_id_and_workspace R4"""
    s1 = mk_stock(i1, f1, deleted=True)

    result = dao.get_by_id_and_workspace(db, id=s1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == s1.id
    # Then 2
    assert result.is_deleted is True


# [local-coder] INV-GIW-05
def test_inv_giw_05__a_row_with_qty_0_is_returned(db, w1, i1, f1, mk_stock):
    """INV-GIW-05 — a row with qty 0 is returned.
    Rules: get_by_id_and_workspace R4"""
    s1 = mk_stock(i1, f1, qty=0)

    result = dao.get_by_id_and_workspace(db, id=s1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == s1.id
    # Then 2
    assert result.qty == 0


# [local-coder] INV-GIW-06
def test_inv_giw_06__negative_qty_returned(db, w1, f1, i1, mk_stock):
    """INV-GIW-06 — a row with negative qty is returned.
    Rules: get_by_id_and_workspace R4"""
    s1 = mk_stock(i1, f1, qty=-3)

    result = dao.get_by_id_and_workspace(db, id=s1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == s1.id
    # Then 2
    assert result.qty == -3


# [local-coder] INV-GIW-07
def test_inv_giw_07__a_row_whose_factory_is_soft_deleted_is_still_returned_by_id(db, w1, i1, mk_factory, mk_stock):
    """INV-GIW-07 — a row whose factory is soft-deleted is still returned by id.
    Rules: get_by_id_and_workspace R5"""
    fa = mk_factory("Old Plant", "OP", is_active=True, is_deleted=True)
    s1 = mk_stock(i1, fa)

    result = dao.get_by_id_and_workspace(db, id=s1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == s1.id
    # Then 2
    assert result.factory_id == fa.id


# [local-coder] INV-GIW-08
def test_inv_giw_08__a_row_whose_item_has_been_removed_is_still_returned_by_id(db, w1, f1, mk_item, mk_stock):
    """INV-GIW-08 — a row whose item has been removed is still returned by id.
    Rules: get_by_id_and_workspace R5"""
    ia = mk_item("Old Gasket", is_active=False)
    s1 = mk_stock(ia, f1)

    result = dao.get_by_id_and_workspace(db, id=s1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == s1.id
    # Then 2
    assert result.item_id == ia.id


# [local-coder] INV-GF-01
def test_inv_gf_01__returns_the_live_row_of_the_exact_bucket_among_neighbouring_buckets(db, w1, f1, f2, i1, i2, mk_stock):
    """INV-GF-01 — returns the live row of the exact bucket among neighbouring buckets.
    Rules: get_by_factory_item_type R1"""
    s1 = mk_stock(i1, f1)
    mk_stock(i1, f2)
    mk_stock(i2, f1)
    mk_stock(i1, f1, inventory_type=DAMAGED)

    result = dao.get_by_factory_item_type(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result.id == s1.id


# [local-coder] INV-GF-02
def test_inv_gf_02__a_row_that_differs_only_by_workspace_is_not_returned(db, w1, w2, f9, i9, mk_stock):
    """INV-GF-02 — a row that differs only by workspace is not returned.
    Rules: get_by_factory_item_type R2"""
    mk_stock(i9, f9, workspace_id=w2.id)

    result = dao.get_by_factory_item_type(db, factory_id=f9.id, item_id=i9.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result is None


# [local-coder] INV-GF-03
def test_inv_gf_03__a_row_that_differs_only_by_factory_is_not_returned(db, w1, f1, f2, i1, mk_stock):
    """INV-GF-03 — a row that differs only by factory is not returned.
    Rules: get_by_factory_item_type R2"""
    mk_stock(i1, f1)

    result = dao.get_by_factory_item_type(db, factory_id=f2.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result is None


# [local-coder] INV-GF-04
def test_inv_gf_04__a_row_that_differs_only_by_item_is_not_returned(db, w1, f1, i1, i2, mk_stock):
    """INV-GF-04 — a row that differs only by item is not returned.
    Rules: get_by_factory_item_type R2"""
    mk_stock(i1, f1)

    result = dao.get_by_factory_item_type(db, factory_id=f1.id, item_id=i2.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result is None


# [local-coder] INV-GF-05
def test_inv_gf_05__a_row_that_differs_only_by_type_is_not_returned(db, w1, f1, i1, mk_stock):
    """INV-GF-05 — a row that differs only by type is not returned.
    Rules: get_by_factory_item_type R2"""
    mk_stock(i1, f1)

    result = dao.get_by_factory_item_type(db, factory_id=f1.id, item_id=i1.id, inventory_type=DAMAGED, workspace_id=w1.id)

    # Then 1
    assert result is None


# [local-coder] INV-GF-06
def test_inv_gf_06__soft_deleted_bucket_returns_none(db, w1, f1, i1, mk_stock):
    """INV-GF-06 — a soft-deleted bucket row returns None.
    Rules: get_by_factory_item_type R3"""
    mk_stock(i1, f1, deleted=True)

    result = dao.get_by_factory_item_type(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result is None


# [local-coder] INV-GF-07
def test_inv_gf_07__a_live_row_with_is_active_false_is_returned(db, w1, f1, i1, mk_stock):
    """INV-GF-07 — a live row with is_active False is returned.
    Rules: get_by_factory_item_type R4"""
    s1 = mk_stock(i1, f1, is_active=False)

    result = dao.get_by_factory_item_type(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result.id == s1.id


# [local-coder] INV-GF-08
def test_inv_gf_08__a_live_row_with_qty_0_is_returned(db, w1, f1, i1, mk_stock):
    """INV-GF-08 — a live row with qty 0 is returned.
    Rules: get_by_factory_item_type R4"""
    s1 = mk_stock(i1, f1, qty=0)

    result = dao.get_by_factory_item_type(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result.id == s1.id


# [local-coder] INV-GF-09
def test_inv_gf_09__a_live_row_with_negative_qty_is_returned(db, w1, f1, i1, mk_stock):
    """INV-GF-09 — a live row with negative qty is returned.
    Rules: get_by_factory_item_type R4"""
    s1 = mk_stock(i1, f1, qty=-4)

    result = dao.get_by_factory_item_type(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result.id == s1.id


# [local-coder] INV-GF-10
def test_inv_gf_10__the_live_row_of_a_bucket_in_a_soft_deleted_factory_is_returned(db, w1, i1, mk_factory, mk_stock):
    """INV-GF-10 — the live row of a bucket in a soft-deleted factory is returned.
    Rules: get_by_factory_item_type R5"""
    fa = mk_factory("Old Plant", "OP", is_active=True, is_deleted=True)
    s1 = mk_stock(i1, fa)

    result = dao.get_by_factory_item_type(db, factory_id=fa.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result.id == s1.id


# [local-coder] INV-GA-01
def test_inv_ga_01__returns_the_live_row_of_the_exact_bucket_among_neighbouring_buckets(db, w1, f1, f2, i1, i2, mk_stock):
    """INV-GA-01 — returns the live row of the exact bucket among neighbouring buckets.
    Rules: _get_any_by_factory_item_type R1"""
    s1 = mk_stock(i1, f1)
    mk_stock(i1, f2)
    mk_stock(i2, f1)
    mk_stock(i1, f1, inventory_type=DAMAGED)

    result = dao._get_any_by_factory_item_type(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result.id == s1.id


# [local-coder] INV-GA-02
def test_inv_ga_02__a_row_that_differs_only_by_workspace_is_not_returned(db, w1, w2, f9, i9, mk_stock):
    """INV-GA-02 — a row that differs only by workspace is not returned.
    Rules: _get_any_by_factory_item_type R2"""
    mk_stock(i9, f9, workspace_id=w2.id)

    result = dao._get_any_by_factory_item_type(db, factory_id=f9.id, item_id=i9.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result is None


# [local-coder] INV-GA-03
def test_inv_ga_03__a_row_that_differs_only_by_factory_is_not_returned(db, w1, f1, f2, i1, mk_stock):
    """INV-GA-03 — a row that differs only by factory is not returned.
    Rules: _get_any_by_factory_item_type R2"""
    mk_stock(i1, f1)

    result = dao._get_any_by_factory_item_type(db, factory_id=f2.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result is None


# [local-coder] INV-GA-04
def test_inv_ga_04__a_row_that_differs_only_by_item_is_not_returned(db, w1, f1, i1, i2, mk_stock):
    """INV-GA-04 — a row that differs only by item is not returned.
    Rules: _get_any_by_factory_item_type R2"""
    mk_stock(i1, f1)

    result = dao._get_any_by_factory_item_type(db, factory_id=f1.id, item_id=i2.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result is None


# [local-coder] INV-GA-05
def test_inv_ga_05__a_row_that_differs_only_by_type_is_not_returned(db, w1, f1, i1, mk_stock):
    """INV-GA-05 — a row that differs only by type is not returned.
    Rules: _get_any_by_factory_item_type R2"""
    mk_stock(i1, f1)

    result = dao._get_any_by_factory_item_type(db, factory_id=f1.id, item_id=i1.id, inventory_type=DAMAGED, workspace_id=w1.id)

    # Then 1
    assert result is None


# [local-coder] INV-GA-06
def test_inv_ga_06__a_soft_deleted_bucket_row_is_returned(db, w1, f1, i1, mk_stock):
    """INV-GA-06 — a soft-deleted bucket row is returned.
    Rules: _get_any_by_factory_item_type R1"""
    s1 = mk_stock(i1, f1, deleted=True)

    result = dao._get_any_by_factory_item_type(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result.id == s1.id
    # Then 2
    assert result.is_deleted is True


# [local-coder] INV-GA-07
def test_inv_ga_07__no_row_at_all_for_the_bucket_returns_none(db, w1, f1, i1):
    """INV-GA-07 — no row at all for the bucket returns None.
    Rules: _get_any_by_factory_item_type R2"""

    result = dao._get_any_by_factory_item_type(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result is None


# [local-coder] INV-SY-01
def test_inv_sy_01__row_takes_values_of_entry_with_greatest_performed_at_and_is_stamped(db, w1, u2, f1, i1, mk_stock, mk_entry):
    """INV-SY-01 — row takes the values of the entry with the greatest performed_at and is stamped.
    Rules: sync_snapshot_from_ledger R1, R5, R11"""
    s1 = mk_stock(i1, f1, qty=7, avg_price=Decimal("5.00"))
    mk_entry(i1, f1, qty_after=20, avg_price_after=Decimal("6.00"), performed_at=T3)
    mk_entry(i1, f1, qty_after=30, avg_price_after=Decimal("7.00"), performed_at=T1)
    mk_entry(i1, f1, qty_after=10, avg_price_after=Decimal("4.00"), performed_at=T2)

    result = dao.sync_snapshot_from_ledger(db, inv=s1, workspace_id=w1.id, updated_by=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.qty == 20
    # Then 3
    assert row.avg_price == Decimal("6.00")
    # Then 4
    assert row.updated_by == u2.id
    # Then 5
    assert row.updated_at is not None
    # Then 6
    assert count_rows(db, InventoryLedger) == 3
    # Then 7
    assert count_rows(db, Inventory) == 1


# [local-coder] INV-SY-02
def test_inv_sy_02__a_null_average_price_on_the_newest_entry_is_copied(db, w1, u2, f1, i1, mk_stock, mk_entry):
    """INV-SY-02 — a NULL average price on the newest entry is copied.
    Rules: sync_snapshot_from_ledger R2"""
    s1 = mk_stock(i1, f1, qty=20, avg_price=Decimal("6.00"))
    mk_entry(i1, f1, qty_after=9, avg_price_after=Decimal("3.00"), performed_at=T1)
    mk_entry(i1, f1, qty_after=5, avg_price_after=None, performed_at=T2)

    result = dao.sync_snapshot_from_ledger(db, inv=s1, workspace_id=w1.id, updated_by=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.qty == 5
    # Then 3
    assert row.avg_price is None


# [local-coder] INV-SY-03
def test_inv_sy_03__bucket_with_no_ledger_set_to_zero_and_no_price(db, w1, u2, f1, i1, mk_stock):
    """INV-SY-03 — a bucket with no ledger entry is set to 0 and no price.
    Rules: sync_snapshot_from_ledger R3, R5"""
    s1 = mk_stock(i1, f1, qty=7, avg_price=Decimal("5.00"))

    result = dao.sync_snapshot_from_ledger(db, inv=s1, workspace_id=w1.id, updated_by=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.qty == 0
    # Then 3
    assert row.avg_price is None
    # Then 4
    assert row.updated_by == u2.id
    # Then 5
    assert count_rows(db, InventoryLedger) == 0


# [local-coder] INV-SY-04
def test_inv_sy_04__no_ledger_entry_and_row_already_at_zero_no_price(db, w1, u2, f1, i1, mk_stock):
    """INV-SY-04 — no ledger entry and a row already at 0 / no price: nothing is written.
    Rules: sync_snapshot_from_ledger R3, R6"""
    s1 = mk_stock(i1, f1, qty=0, avg_price=None)
    before_s1 = snap(db, s1)

    result = dao.sync_snapshot_from_ledger(db, inv=s1, workspace_id=w1.id, updated_by=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    assert snap(db, s1) == before_s1
    # Then 3
    row = reread(db, s1)
    assert row.updated_by is None
    # Then 4
    assert row.updated_at is None


# [local-coder] INV-SY-05
def test_inv_sy_05__a_different_price_alone_triggers_the_write(db, w1, u2, f1, i1, mk_stock, mk_entry):
    """INV-SY-05 — a different price alone triggers the write.
    Rules: sync_snapshot_from_ledger R4"""
    s1 = mk_stock(i1, f1, qty=20, avg_price=Decimal("5.00"))
    mk_entry(i1, f1, qty_after=20, avg_price_after=Decimal("6.00"), performed_at=T1)

    result = dao.sync_snapshot_from_ledger(db, inv=s1, workspace_id=w1.id, updated_by=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.qty == 20
    # Then 3
    assert row.avg_price == Decimal("6.00")
    # Then 4
    assert row.updated_by == u2.id


# [local-coder] INV-SY-06
def test_inv_sy_06__a_different_quantity_alone_triggers_the_write(db, w1, u2, f1, i1, mk_stock, mk_entry):
    """INV-SY-06 — a different quantity alone triggers the write.
    Rules: sync_snapshot_from_ledger R4"""
    s1 = mk_stock(i1, f1, qty=7, avg_price=Decimal("6.00"))
    mk_entry(i1, f1, qty_after=20, avg_price_after=Decimal("6.00"), performed_at=T1)

    result = dao.sync_snapshot_from_ledger(db, inv=s1, workspace_id=w1.id, updated_by=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.qty == 20
    # Then 3
    assert row.avg_price == Decimal("6.00")
    # Then 4
    assert row.updated_by == u2.id


# [local-coder] INV-SY-07
def test_inv_sy_07__without_updated_by_a_changed_row_keeps_its_previous_stamp(db, w1, u1, f1, i1, mk_stock, mk_entry):
    """INV-SY-07 — without updated_by a changed row keeps its previous stamp.
    Rules: sync_snapshot_from_ledger R5"""
    s1 = mk_stock(i1, f1, qty=7, avg_price=Decimal("5.00"), updated_by=u1.id)
    mk_entry(i1, f1, qty_after=20, avg_price_after=Decimal("6.00"), performed_at=T1)

    result = dao.sync_snapshot_from_ledger(db, inv=s1, workspace_id=w1.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.qty == 20
    # Then 3
    assert row.updated_by == u1.id
    # Then 4
    assert row.updated_at is not None


# [local-coder] INV-SY-08
def test_inv_sy_08__values_already_equal_to_the_ledger_nothing_is_written_no_stamp(db, w1, u1, u2, f1, i1, mk_stock, mk_entry):
    """INV-SY-08 — values already equal to the ledger: nothing is written, no stamp.
    Rules: sync_snapshot_from_ledger R6"""
    s1 = mk_stock(i1, f1, qty=20, avg_price=Decimal("6.00"), updated_by=u1.id)
    mk_entry(i1, f1, qty_after=20, avg_price_after=Decimal("6"), performed_at=T1)

    before_s1 = snap(db, s1)

    result = dao.sync_snapshot_from_ledger(db, inv=s1, workspace_id=w1.id, updated_by=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    assert snap(db, s1) == before_s1
    # Then 3
    row = reread(db, s1)
    assert row.updated_by == u1.id
    # Then 4
    assert row.updated_at is None
    # Then 5
    assert row.qty == 20


# [local-coder] INV-SY-09
def test_inv_sy_09__no_price_on_both_sides_counts_as_equal(db, w1, u2, f1, i1, mk_stock, mk_entry):
    """INV-SY-09 — no price on both sides counts as equal.
    Rules: sync_snapshot_from_ledger R6"""
    s1 = mk_stock(i1, f1, qty=4, avg_price=None)
    mk_entry(i1, f1, qty_after=4, avg_price_after=None, performed_at=T1)

    before_s1 = snap(db, s1)

    result = dao.sync_snapshot_from_ledger(db, inv=s1, workspace_id=w1.id, updated_by=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    assert snap(db, s1) == before_s1
    # Then 3
    row = reread(db, s1)
    assert row.updated_by is None
    # Then 4
    assert row.updated_at is None


# [local-coder] INV-SY-11
def test_inv_sy_11__entries_of_other_buckets_only(db, w1, u2, f1, f2, i1, mk_stock, mk_entry):
    """INV-SY-11 — entries of other buckets only: the bucket counts as having no ledger.
    Rules: sync_snapshot_from_ledger R7, R3"""
    s1 = mk_stock(i1, f1, qty=7, avg_price=Decimal("5.00"))
    mk_entry(i1, f1, inventory_type=DAMAGED, qty_after=91, avg_price_after=Decimal("9.10"), performed_at=T1)
    mk_entry(i1, f2, qty_after=92, avg_price_after=Decimal("9.20"), performed_at=T2)

    result = dao.sync_snapshot_from_ledger(db, inv=s1, workspace_id=w1.id, updated_by=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.qty == 0
    # Then 3
    assert row.avg_price is None


# [local-coder] INV-SY-13
def test_inv_sy_13__a_soft_deleted_row_is_aligned_and_stays_soft_deleted(db, w1, u1, u2, f1, i1, mk_stock, mk_entry):
    """INV-SY-13 — a soft-deleted row is aligned and stays soft-deleted.
    Rules: sync_snapshot_from_ledger R9, R8"""
    s1 = mk_stock(i1, f1, deleted=True, qty=7, avg_price=Decimal("5.00"))
    mk_entry(i1, f1, qty_after=20, avg_price_after=Decimal("6.00"), performed_at=T1)

    result = dao.sync_snapshot_from_ledger(db, inv=s1, workspace_id=w1.id, updated_by=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.qty == 20
    # Then 3
    assert row.avg_price == Decimal("6.00")
    # Then 4
    assert row.is_deleted is True
    assert row.is_active is False
    # Then 5
    assert row.deleted_at == T0
    # Then 6
    assert row.deleted_by == u1.id


# [local-coder] INV-SY-14
def test_inv_sy_14__ledger_searched_by_workspace_id_arg(db, w2, u2, f1, i1, mk_stock, mk_entry):
    """INV-SY-14 — the ledger is searched in the workspace_id argument, not the row's workspace.
    Rules: sync_snapshot_from_ledger R10"""
    s1 = mk_stock(i1, f1, qty=7, avg_price=Decimal("5.00"))
    mk_entry(i1, f1, qty_after=20, avg_price_after=Decimal("6.00"), performed_at=T2)
    mk_entry(i1, f1, workspace_id=w2.id, qty_after=33, avg_price_after=Decimal("3.00"), performed_at=T1)

    result = dao.sync_snapshot_from_ledger(db, inv=s1, workspace_id=w2.id, updated_by=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.qty == 33
    # Then 3
    assert row.avg_price == Decimal("3.00")


# [local-coder] INV-SY-15
def test_inv_sy_15__called_with_a_workspace_that_has_no_entries_the_row_is_set_to_0_and_no_price(db, w2, u2, f1, i1, mk_stock, mk_entry):
    """INV-SY-15 — called with a workspace that has no entries, the row is set to 0 and no price.
    Rules: sync_snapshot_from_ledger R10, R3"""
    s1 = mk_stock(i1, f1, qty=7, avg_price=Decimal("5.00"))
    mk_entry(i1, f1, qty_after=20, avg_price_after=Decimal("6.00"), performed_at=T1)

    result = dao.sync_snapshot_from_ledger(db, inv=s1, workspace_id=w2.id, updated_by=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.qty == 0
    # Then 3
    assert row.avg_price is None


# [local-coder] INV-EN-01
def test_inv_en_01__a_live_row_is_returned_aligned_to_the_ledger_and_stamped(db, w1, u1, u2, f1, i1, mk_stock, mk_entry):
    """INV-EN-01 — a live row is returned, aligned to the ledger and stamped.
    Rules: ensure_for_factory_item_type R1; sync_snapshot_from_ledger R1, R5"""
    s1 = mk_stock(i1, f1, qty=7, avg_price=Decimal("5.00"))
    mk_entry(i1, f1, qty_after=20, avg_price_after=Decimal("6.00"), performed_at=T1)

    result = dao.ensure_for_factory_item_type(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE,
                                              workspace_id=w1.id, created_by=u2.id)

    # Then 1
    assert result.id == s1.id
    # Then 2
    row = reread(db, s1)
    assert row.qty == 20
    # Then 3
    assert row.avg_price == Decimal("6.00")
    # Then 4
    assert row.updated_by == u2.id
    # Then 5
    assert row.created_by == u1.id
    # Then 6
    assert count_rows(db, Inventory) == 1
    # Then 7
    assert count_rows(db, InventoryLedger) == 1


# [local-coder] INV-EN-02
def test_inv_en_02__a_live_row_already_equal_to_the_ledger_is_returned_unchanged_and_unstamped(db, w1, u2, f1, i1, mk_stock, mk_entry):
    """INV-EN-02 — a live row already equal to the ledger is returned unchanged and unstamped.
    Rules: ensure_for_factory_item_type R1; sync_snapshot_from_ledger R6"""
    s1 = mk_stock(i1, f1, qty=20, avg_price=Decimal("6.00"))
    mk_entry(i1, f1, qty_after=20, avg_price_after=Decimal("6.00"), performed_at=T1)

    before_s1 = snap(db, s1)

    result = dao.ensure_for_factory_item_type(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE,
                                              workspace_id=w1.id, created_by=u2.id)

    # Then 1
    assert result.id == s1.id
    # Then 2
    assert snap(db, s1) == before_s1
    # Then 3
    row = reread(db, s1)
    assert row.updated_by is None
    # Then 4
    assert row.updated_at is None
    # Then 5
    assert count_rows(db, Inventory) == 1


# [local-coder] INV-EN-03
def test_inv_en_03__a_live_row_whose_bucket_has_no_ledger_entry_is_set_to_0_and_no_price(db, w1, u2, f1, i1, mk_stock):
    """INV-EN-03 — a live row whose bucket has no ledger entry is set to 0 and no price.
    Rules: ensure_for_factory_item_type R1; sync_snapshot_from_ledger R3"""
    s1 = mk_stock(i1, f1, qty=7, avg_price=Decimal("5.00"))

    result = dao.ensure_for_factory_item_type(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE,
                                              workspace_id=w1.id, created_by=u2.id)

    # Then 1
    assert result.id == s1.id
    # Then 2
    row = reread(db, s1)
    assert row.qty == 0
    # Then 3
    assert row.avg_price is None
    # Then 4
    assert row.updated_by == u2.id
    # Then 5
    assert count_rows(db, Inventory) == 1


# [local-coder] INV-EN-04
def test_inv_en_04__a_live_row_with_is_active_false_is_reused_and_stays_inactive(db, w1, u2, f1, i1, mk_stock, mk_entry):
    """INV-EN-04 — a live row with is_active False is reused and stays inactive.
    Rules: ensure_for_factory_item_type R2"""
    s1 = mk_stock(i1, f1, is_active=False, qty=20, avg_price=Decimal("6.00"))
    mk_entry(i1, f1, qty_after=20, avg_price_after=Decimal("6.00"), performed_at=T1)

    result = dao.ensure_for_factory_item_type(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE,
                                              workspace_id=w1.id, created_by=u2.id)

    # Then 1
    assert result.id == s1.id
    # Then 2
    row = reread(db, s1)
    assert row.is_active is False
    # Then 3
    assert row.is_deleted is False
    # Then 4
    assert count_rows(db, Inventory) == 1


# [local-coder] INV-EN-06
def test_inv_en_06__a_soft_deleted_row_whose_values_equal_the_ledger_is_restored_with_values_kept(db, w1, u1, u2, f1, i1, mk_stock, mk_entry):
    """INV-EN-06 — a soft-deleted row whose values equal the ledger is restored with values kept.
    Rules: ensure_for_factory_item_type R3"""
    s1 = mk_stock(i1, f1, deleted=True, qty=4, avg_price=Decimal("2.00"), updated_by=u1.id)
    mk_entry(i1, f1, qty_after=4, avg_price_after=Decimal("2.00"), performed_at=T1)

    result = dao.ensure_for_factory_item_type(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE,
                                              workspace_id=w1.id, created_by=u2.id)

    # Then 1
    assert result.id == s1.id
    # Then 2
    row = reread(db, s1)
    assert row.is_deleted is False
    assert row.is_active is True
    # Then 3
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 4
    assert row.qty == 4
    # Then 5
    assert row.avg_price == Decimal("2.00")
    # Then 6
    assert row.updated_at is not None
    # Then 7
    assert count_rows(db, Inventory) == 1


# [local-coder] INV-EN-07
@pytest.mark.xfail(strict=True, reason="BUG-881: Restoring a soft-deleted stock row does not record who restored it")
def test_inv_en_07__a_restored_row_is_stamped_with_the_acting_user_even_when_its_values_do_not_change(db, w1, u1, u2, f1, i1, mk_stock, mk_entry):
    """INV-EN-07 — a restored row is stamped with the acting user even when its values do not change.
    Rules: ensure_for_factory_item_type R4 [BUG-881]"""
    s1 = mk_stock(i1, f1, deleted=True, qty=4, avg_price=Decimal("2.00"), updated_by=u1.id)
    mk_entry(i1, f1, qty_after=4, avg_price_after=Decimal("2.00"), performed_at=T1)

    result = dao.ensure_for_factory_item_type(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE,
                                              workspace_id=w1.id, created_by=u2.id)

    # Then 1
    assert result.id == s1.id
    # Then 2
    row = reread(db, s1)
    assert row.is_deleted is False
    # Then 3
    assert row.updated_by == u2.id


# [local-coder] INV-EN-08
def test_inv_en_08__no_row_and_no_ledger_an_empty_row_is_created(db, w1, u2, f1, i1):
    """INV-EN-08 — no row and no ledger: an empty row is created.
    Rules: ensure_for_factory_item_type R5"""

    result = dao.ensure_for_factory_item_type(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE,
                                              workspace_id=w1.id, created_by=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.factory_id == f1.id
    assert row.item_id == i1.id
    # Then 3
    assert row.inventory_type == STORAGE
    # Then 4
    assert row.qty == 0
    assert row.avg_price is None
    # Then 5
    assert row.created_by == u2.id
    assert row.note is None
    # Then 6
    assert row.is_active is True
    assert row.is_deleted is False
    assert row.created_at is not None
    # Then 7
    assert row.updated_by is None
    assert row.updated_at is None
    # Then 8
    assert count_rows(db, Inventory) == 1


# [local-coder] INV-EN-09
def test_inv_en_09__no_row_but_ledger_entries(db, w1, u2, f1, i1, mk_entry):
    """INV-EN-09 — no row but ledger entries: the new row is aligned and stamped.
    Rules: ensure_for_factory_item_type R6, R5"""
    mk_entry(i1, f1, qty_after=20, avg_price_after=Decimal("6.00"), performed_at=T2)
    mk_entry(i1, f1, qty_after=9, avg_price_after=Decimal("3.00"), performed_at=T1)

    result = dao.ensure_for_factory_item_type(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE,
                                              workspace_id=w1.id, created_by=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.qty == 20
    # Then 3
    assert row.avg_price == Decimal("6.00")
    # Then 4
    assert row.created_by == u2.id
    assert row.updated_by == u2.id
    # Then 5
    assert row.updated_at is not None
    # Then 6
    assert count_rows(db, Inventory) == 1
    # Then 7
    assert count_rows(db, InventoryLedger) == 2


# [local-coder] INV-EN-10
def test_inv_en_10__no_row_and_newest_entry_of_0_no_price(db, w1, u2, f1, i1, mk_entry):
    """INV-EN-10 — no row and a newest entry of 0 / no price: the new row is not stamped.
    Rules: ensure_for_factory_item_type R6"""
    mk_entry(i1, f1, qty_after=0, avg_price_after=None, performed_at=T2)
    mk_entry(i1, f1, qty_after=9, avg_price_after=Decimal("3.00"), performed_at=T1)

    result = dao.ensure_for_factory_item_type(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE,
                                              workspace_id=w1.id, created_by=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.qty == 0
    assert row.avg_price is None
    # Then 3
    assert row.updated_by is None
    assert row.updated_at is None
    # Then 4
    assert count_rows(db, Inventory) == 1


# [local-coder] INV-EN-12
def test_inv_en_12__a_row_differing_only_in_factory_is_not_reused_a_new_row_is_created_next_to_it(db, w1, u2, f1, f2, i1, mk_stock):
    """INV-EN-12 — a row differing only in factory is not reused: a new row is created next to it.
    Rules: ensure_for_factory_item_type R7"""
    s1 = mk_stock(i1, f2)

    before_s1 = snap(db, s1)

    result = dao.ensure_for_factory_item_type(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id, created_by=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert result.id != s1.id
    # Then 3
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.factory_id == f1.id
    assert row.item_id == i1.id
    # Then 4
    assert row.inventory_type == STORAGE
    # Then 5
    assert snap(db, s1) == before_s1
    # Then 6
    assert count_rows(db, Inventory) == 2


# [local-coder] INV-EN-13
def test_inv_en_13__a_row_differing_only_in_item_is_not_reused_a_new_row_is_created_next_to_it(db, w1, u2, f1, i1, i2, mk_stock):
    """INV-EN-13 — a row differing only in item is not reused: a new row is created next to it.
    Rules: ensure_for_factory_item_type R7"""
    s1 = mk_stock(i2, f1)

    before_s1 = snap(db, s1)

    result = dao.ensure_for_factory_item_type(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE,
                                              workspace_id=w1.id, created_by=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert result.id != s1.id
    # Then 3
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.factory_id == f1.id
    assert row.item_id == i1.id
    # Then 4
    assert row.inventory_type == STORAGE
    # Then 5
    assert snap(db, s1) == before_s1
    # Then 6
    assert count_rows(db, Inventory) == 2


# [local-coder] INV-EN-14
def test_inv_en_14__a_row_differing_only_in_inventory_type_is_not_reused_a_new_row_is_created_next_to_it(db, w1, u2, f1, i1, mk_stock):
    """INV-EN-14 — a row differing only in inventory type is not reused: a new row is created next to it.
    Rules: ensure_for_factory_item_type R7"""
    s1 = mk_stock(i1, f1, inventory_type=DAMAGED)
    before_s1 = snap(db, s1)

    result = dao.ensure_for_factory_item_type(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id, created_by=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert result.id != s1.id
    # Then 3
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.factory_id == f1.id
    assert row.item_id == i1.id
    # Then 4
    assert row.inventory_type == STORAGE
    # Then 5
    assert snap(db, s1) == before_s1
    # Then 6
    assert count_rows(db, Inventory) == 2


# [local-coder] INV-EN-16
def test_inv_en_16__an_item_of_another_workspace_is_accepted(db, w1, f1, i9, u2):
    """INV-EN-16 — an item of another workspace is accepted.
    Rules: ensure_for_factory_item_type R8"""
    result = dao.ensure_for_factory_item_type(db, factory_id=f1.id, item_id=i9.id, inventory_type=STORAGE,
                                              workspace_id=w1.id, created_by=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.item_id == i9.id
    # Then 3
    assert count_rows(db, Inventory) == 1


# [local-coder] INV-EN-17
def test_inv_en_17__factory_of_another_workspace_is_accepted(db, w1, f9, i1, u2):
    """INV-EN-17 — a factory of another workspace is accepted.
    Rules: ensure_for_factory_item_type R8"""

    result = dao.ensure_for_factory_item_type(db, factory_id=f9.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id, created_by=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.factory_id == f9.id
    # Then 3
    assert count_rows(db, Inventory) == 1


# [local-coder] INV-EN-19
def test_inv_en_19__unknown_factory_id_fails_on_foreign_key(db, w1, u2, f1, i1, i2, mk_stock):
    """INV-EN-19 — an unknown factory_id fails on the foreign key; nothing is created, the session stays usable.
    Rules: ensure_for_factory_item_type R8, Errors row 2"""
    s1 = mk_stock(i2, f1)
    before_s1 = snap(db, s1)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        dao.ensure_for_factory_item_type(db, factory_id=MISSING, item_id=i1.id, inventory_type=STORAGE,
                                         workspace_id=w1.id, created_by=u2.id)

    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert exc.value.orig.pgcode == "23503"
    # Then 4
    assert "inventory_factory_id_fkey" in str(exc.value.orig)
    # Then 5
    assert count_rows(db, Inventory) == 1
    # Then 6
    assert snap(db, s1) == before_s1


# [local-coder] INV-EN-21
def test_inv_en_21__unknown_workspace_id_fails_on_foreign_key(db, u2, f1, i1, i2, mk_stock):
    """INV-EN-21 — an unknown workspace_id fails on the foreign key; nothing is created, the session stays usable.
    Rules: ensure_for_factory_item_type R8, Errors row 4"""
    s1 = mk_stock(i2, f1)
    before_s1 = snap(db, s1)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        dao.ensure_for_factory_item_type(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE,
                                         workspace_id=MISSING, created_by=u2.id)

    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert exc.value.orig.pgcode == "23503"
    # Then 4
    assert "inventory_workspace_id_fkey" in str(exc.value.orig)
    # Then 5
    assert count_rows(db, Inventory) == 1
    # Then 6
    assert snap(db, s1) == before_s1


# [local-coder] INV-EN-27
def test_inv_en_27__alignment_uses_only_the_ledger_of_the_workspace_id_argument(db, w1, w2, u2, f1, i1, mk_stock, mk_entry):
    """INV-EN-27 — alignment uses only the ledger of the workspace_id argument.
    Rules: ensure_for_factory_item_type R1; sync_snapshot_from_ledger R7"""
    s1 = mk_stock(i1, f1, qty=7, avg_price=Decimal("5.00"))
    mk_entry(i1, f1, qty_after=20, avg_price_after=Decimal("6.00"), performed_at=T1)
    mk_entry(i1, f1, qty_after=33, avg_price_after=Decimal("3.00"), performed_at=T2, workspace_id=w2.id)

    result = dao.ensure_for_factory_item_type(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id, created_by=u2.id)

    # Then 1
    assert result.id == s1.id
    # Then 2
    row = reread(db, s1)
    assert row.qty == 20
    # Then 3
    assert row.avg_price == Decimal("6.00")


# [local-coder] INV-EN-28
def test_inv_en_28__soft_deleted_factory_reuses_live_row(db, w1, u2, i1, mk_factory, mk_stock, mk_entry):
    """INV-EN-28 — the live row of a bucket in a soft-deleted factory is reused.
    Rules: ensure_for_factory_item_type R1; get_by_factory_item_type R5"""
    fa = mk_factory("Old Plant", "OP", is_active=True, is_deleted=True)
    s1 = mk_stock(i1, fa, qty=7, avg_price=Decimal("5.00"))
    mk_entry(i1, fa, qty_after=20, avg_price_after=Decimal("6.00"), performed_at=T1)

    result = dao.ensure_for_factory_item_type(db, factory_id=fa.id, item_id=i1.id, inventory_type=STORAGE,
                                              workspace_id=w1.id, created_by=u2.id)

    # Then 1
    assert result.id == s1.id
    # Then 2
    row = reread(db, s1)
    assert row.qty == 20
    # Then 3
    assert row.updated_by == u2.id
    # Then 4
    assert count_rows(db, Inventory) == 1


# [local-coder] INV-GI-01
def test_inv_gi_01__returns_item_live_rows_across_factories_and_types(db, w1, f1, f2, i1, i2, mk_stock):
    """INV-GI-01 — returns the item's live rows across factories and all four types, not other items.
    Rules: get_by_item R1, R4, R5"""
    s1 = mk_stock(i1, f1)
    s2 = mk_stock(i1, f2)
    s3 = mk_stock(i1, f1, inventory_type=DAMAGED)
    s4 = mk_stock(i1, f1, inventory_type=WASTE)
    s5 = mk_stock(i1, f1, inventory_type=SCRAP)
    mk_stock(i2, f1)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [s1.id, s2.id, s3.id, s4.id, s5.id]


# [local-coder] INV-GI-02
def test_inv_gi_02__rows_with_zero_and_negative_quantity_are_included(db, w1, f1, f2, i1, mk_stock):
    """INV-GI-02 — rows with zero and negative quantity are included.
    Rules: get_by_item R2"""
    s1 = mk_stock(i1, f1, qty=0)
    s2 = mk_stock(i1, f2, qty=-3)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [s1.id, s2.id]


# [local-coder] INV-GI-03
def test_inv_gi_03__soft_deleted_rows_excluded_inactive_live_rows_included(db, w1, f1, f2, i1, mk_stock):
    """INV-GI-03 — soft-deleted rows are excluded, inactive live rows are included.
    Rules: get_by_item R3"""
    mk_stock(i1, f1, deleted=True)
    s2 = mk_stock(i1, f2, is_active=False)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [s2.id]


# [local-coder] INV-GI-04
def test_inv_gi_04__rows_of_same_item_in_other_workspace_not_mixed(db, w2, f1, f2, i1, mk_stock):
    """INV-GI-04 — rows of the same item id in another workspace are not mixed in.
    Rules: get_by_item R4"""
    mk_stock(i1, f1)
    s2 = mk_stock(i1, f2, workspace_id=w2.id)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [s2.id]


# [local-coder] INV-GI-06
def test_inv_gi_06__unknown_item_id_returns_empty_list(db, w1, f1, i1, mk_stock):
    """INV-GI-06 — an unknown item id returns an empty list.
    Rules: get_by_item R6"""
    mk_stock(i1, f1)

    result = dao.get_by_item(db, item_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result == []


# [local-coder] INV-GI-07
def test_inv_gi_07__unknown_workspace_returns_empty_list(db, f1, i1, mk_stock):
    """INV-GI-07 — an unknown workspace id returns an empty list.
    Rules: get_by_item R6"""
    mk_stock(i1, f1)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=MISSING)

    # Then 1
    assert result == []


# [local-coder] INV-GI-08
def test_inv_gi_08__an_item_with_only_soft_deleted_rows_returns_an_empty_list(db, w1, f1, i1, i2, mk_stock):
    """INV-GI-08 — an item with only soft-deleted rows returns an empty list.
    Rules: get_by_item R6, R3"""
    mk_stock(i1, f1, deleted=True)
    mk_stock(i2, f1)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [local-coder] INV-GI-10
@pytest.mark.xfail(strict=True, reason="BUG-884: Item summary still shows and totals stock held in a soft-deleted factory")
def test_inv_gi_10__soft_deleted_factory_returns_empty_list(db, w1, i1, mk_factory, mk_stock):
    """INV-GI-10 — an item whose only stock sits in a soft-deleted factory returns an empty list.
    Rules: get_by_item R1a [BUG-884]"""
    fa = mk_factory("Old Plant", "OP", workspace_id=w1.id, is_active=True, is_deleted=True)
    mk_stock(i1, fa, qty=30)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [local-coder] INV-GI-11
def test_inv_gi_11__a_row_in_an_inactive_but_live_factory_is_returned(db, w1, f1, i1, mk_factory, mk_stock):
    """INV-GI-11 — a row in an inactive but live factory is returned.
    Rules: get_by_item R1b, R1"""
    fb = mk_factory("Idle Plant", "IP", is_active=False, is_deleted=False)
    s1 = mk_stock(i1, fb)
    s2 = mk_stock(i1, f1)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [s1.id, s2.id]


# [local-coder] INV-GI-12
def test_inv_gi_12__soft_deleted_factory_stock_untouched(db, w1, f1, i1, mk_factory, mk_stock):
    """INV-GI-12 — the call leaves the stock row of a soft-deleted factory untouched.
    Rules: get_by_item R1b"""
    fa = mk_factory("Old Plant", "OP", is_active=True, is_deleted=True)
    s1 = mk_stock(i1, f1)
    s2 = mk_stock(i1, fa, qty=30)

    before_s2 = snap(db, s2)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert s1.id in ids(result)
    # Then 2
    assert snap(db, s2) == before_s2
    # Then 3
    row = reread(db, s2)
    assert row.is_deleted is False
    assert row.qty == 30
    assert row.factory_id == fa.id
    # Then 4
    assert row.avg_price == Decimal("2.00")


# [local-coder] INV-GI-13
def test_inv_gi_13__removed_item_returns_live_stock(db, w1, f1, i1, mk_item, mk_stock):
    """INV-GI-13 — the live rows of a removed item are returned when asked for by its id.
    Rules: get_by_item R3"""
    ia = mk_item("Old Gasket", is_active=False)
    s1 = mk_stock(ia, f1)
    mk_stock(i1, f1)

    result = dao.get_by_item(db, item_id=ia.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [s1.id]


# [local-coder] INV-R-03
def test_inv_r_03__a_row_that_is_already_live_and_active_is_left_untouched(db, f1, i1, mk_stock):
    """INV-R-03 — a row that is already live and active is left untouched.
    Rules: restore R3"""
    s1 = mk_stock(i1, f1)
    before_s1 = snap(db, s1)

    result = dao.restore(db, db_obj=s1)

    # Then 1
    assert result is s1
    # Then 2
    assert snap(db, s1) == before_s1
    # Then 3
    row = reread(db, s1)
    assert row.updated_at is None


# [local-coder] INV-R-04
def test_inv_r_04__a_live_row_with_is_active_false_becomes_active(db, f1, i1, mk_stock):
    """INV-R-04 — a live row with is_active False becomes active.
    Rules: restore R3"""
    s1 = mk_stock(i1, f1, is_active=False)

    result = dao.restore(db, db_obj=s1)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.is_active is True
    # Then 3
    assert row.is_deleted is False



# --------------------------------------------------------------------------- #
# Cards marked "Author: claude" (hand-written in Step D; not sent to the local model)
# --------------------------------------------------------------------------- #

# Convention "Rolled back": spy that wraps (does not replace) db.commit.
def commit_spy(db):
    return patch.object(db, "commit", wraps=db.commit)


# Convention "race R9": the live lookup always misses; the any-lookup misses on the
# first call only and delegates to the real method afterwards.
def race_r9():
    real = inventory_dao._get_any_by_factory_item_type
    calls = []

    def _first_none(db, **kwargs):
        calls.append(kwargs)
        return None if len(calls) == 1 else real(db, **kwargs)

    return (patch.object(inventory_dao, "get_by_factory_item_type", return_value=None),
            patch.object(inventory_dao, "_get_any_by_factory_item_type", side_effect=_first_none))


# Convention "race R10": both lookups miss on every call.
def race_r10():
    return (patch.object(inventory_dao, "get_by_factory_item_type", return_value=None),
            patch.object(inventory_dao, "_get_any_by_factory_item_type", return_value=None))


@pytest.mark.xfail(strict=False, reason="BUG-719: Per-type breakdown in inventory stats has no fixed order")
def test_inv_st_03__per_type_rows_in_enum_order(db, w1, f1, i1, mk_stock):
    """INV-ST-03 — per-type rows come back in enum order STORAGE, DAMAGED, WASTE, SCRAP.
    Rules: stats_filtered R6 [BUG-719]"""
    mk_stock(i1, f1, inventory_type=SCRAP)
    mk_stock(i1, f1, inventory_type=WASTE)
    mk_stock(i1, f1, inventory_type=DAMAGED)
    mk_stock(i1, f1)

    result = dao.stats_filtered(db, workspace_id=w1.id)

    # Then 1
    assert len(result[3]) == 4
    # Then 2
    assert [r[0] for r in result[3]] == [STORAGE, DAMAGED, WASTE, SCRAP]


def test_inv_sy_16__change_flushed_not_committed(db, w1, u2, f1, i1, mk_stock, mk_entry):
    """INV-SY-16 — the change is flushed but not committed: a rollback restores the row.
    Rules: sync_snapshot_from_ledger R11"""
    s1 = mk_stock(i1, f1, qty=7, avg_price=Decimal("5.00"))
    mk_entry(i1, f1, qty_after=20, avg_price_after=Decimal("6.00"), performed_at=T1)

    with commit_spy(db) as spy:
        sp = db.begin_nested()
        result = dao.sync_snapshot_from_ledger(db, inv=s1, workspace_id=w1.id, updated_by=u2.id)

        # Then 1
        assert result is s1
        # Then 2
        row = reread(db, s1)
        assert row.qty == 20

        sp.rollback()
        # Then 3
        row = reread(db, s1)
        assert row.qty == 7
        # Then 4
        assert row.avg_price == Decimal("5.00")
        assert row.updated_by is None
        # Then 5
        assert spy.call_count == 0


def test_inv_en_22__race_lost_to_live_row(db, w1, u2, f1, i1, mk_stock, mk_entry):
    """INV-EN-22 — insert loses a race to a live row: that row is returned, aligned, no error.
    Rules: ensure_for_factory_item_type R9"""
    s1 = mk_stock(i1, f1, qty=7, avg_price=Decimal("5.00"))
    mk_entry(i1, f1, qty_after=20, avg_price_after=Decimal("6.00"), performed_at=T1)

    live_lookup, any_lookup = race_r9()
    with live_lookup, any_lookup:
        result = dao.ensure_for_factory_item_type(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE,
                                                  workspace_id=w1.id, created_by=u2.id)

    # Then 1
    assert result.id == s1.id
    # Then 2
    row = reread(db, s1)
    assert row.qty == 20
    # Then 3
    assert row.avg_price == Decimal("6.00")
    # Then 4
    assert row.updated_by == u2.id
    # Then 5
    assert row.is_deleted is False
    # Then 6
    assert count_rows(db, Inventory) == 1


def test_inv_en_23__race_lost_to_soft_deleted_row(db, w1, u2, f1, i1, mk_stock, mk_entry):
    """INV-EN-23 — insert loses a race to a soft-deleted row: it is restored, aligned and returned.
    Rules: ensure_for_factory_item_type R9"""
    s1 = mk_stock(i1, f1, deleted=True, qty=7, avg_price=Decimal("5.00"))
    mk_entry(i1, f1, qty_after=20, avg_price_after=Decimal("6.00"), performed_at=T1)

    live_lookup, any_lookup = race_r9()
    with live_lookup, any_lookup:
        result = dao.ensure_for_factory_item_type(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE,
                                                  workspace_id=w1.id, created_by=u2.id)

    # Then 1
    assert result.id == s1.id
    # Then 2
    row = reread(db, s1)
    assert row.is_deleted is False
    assert row.is_active is True
    # Then 3
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 4
    assert row.qty == 20
    # Then 5
    assert count_rows(db, Inventory) == 1


def test_inv_en_24__unique_violation_row_not_found_reraised(db, w1, u2, f1, i1, mk_stock, mk_entry):
    """INV-EN-24 — unique violation and the row still cannot be found: the IntegrityError is re-raised.
    Rules: ensure_for_factory_item_type R10, Errors row 5"""
    s1 = mk_stock(i1, f1, qty=7, avg_price=Decimal("5.00"))
    mk_entry(i1, f1, qty_after=20, avg_price_after=Decimal("6.00"), performed_at=T1)
    before_s1 = snap(db, s1)

    live_lookup, any_lookup = race_r10()
    with live_lookup, any_lookup:
        # Then 1
        with pytest.raises(IntegrityError) as exc:
            dao.ensure_for_factory_item_type(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE,
                                             workspace_id=w1.id, created_by=u2.id)

    # Then 2
    assert isinstance(exc.value.orig, UniqueViolation)
    # Then 3
    assert exc.value.orig.pgcode == "23505"
    # Then 4
    assert "uq_inventory_workspace_item_type_factory" in str(exc.value.orig)
    # Then 5
    assert count_rows(db, Inventory) == 1
    # Then 6
    assert snap(db, s1) == before_s1


def test_inv_en_25__created_row_flushed_not_committed(db, w1, u2, f1, i1):
    """INV-EN-25 — a created row is flushed but not committed: a rollback removes it.
    Rules: ensure_for_factory_item_type R11"""
    with commit_spy(db) as spy:
        sp = db.begin_nested()
        result = dao.ensure_for_factory_item_type(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE,
                                                  workspace_id=w1.id, created_by=u2.id)

        # Then 1
        assert result.id is not None
        # Then 2
        assert count_rows(db, Inventory) == 1

        sp.rollback()
        # Then 3
        assert count_rows(db, Inventory) == 0
        # Then 4
        assert spy.call_count == 0


def test_inv_en_26__restore_and_alignment_not_committed(db, w1, u1, u2, f1, i1, mk_stock, mk_entry):
    """INV-EN-26 — a restore and alignment are not committed: a rollback undoes them.
    Rules: ensure_for_factory_item_type R11"""
    s1 = mk_stock(i1, f1, deleted=True, qty=7, avg_price=Decimal("5.00"))
    mk_entry(i1, f1, qty_after=20, avg_price_after=Decimal("6.00"), performed_at=T1)

    with commit_spy(db) as spy:
        sp = db.begin_nested()
        result = dao.ensure_for_factory_item_type(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE,
                                                  workspace_id=w1.id, created_by=u2.id)

        # Then 1
        assert result.id == s1.id
        # Then 2
        row = reread(db, s1)
        assert row.is_deleted is False
        assert row.qty == 20

        sp.rollback()
        # Then 3
        row = reread(db, s1)
        assert row.is_deleted is True
        assert row.is_active is False
        # Then 4
        assert row.qty == 7
        assert row.deleted_at == T0
        assert row.deleted_by == u1.id
        # Then 5
        assert spy.call_count == 0


def test_inv_gi_05__no_row_cap_104_rows(db, w1, i1, mk_factory, mk_stock):
    """INV-GI-05 — there is no row cap: 104 matching rows are all returned.
    Rules: get_by_item R5"""
    for n in range(1, 27):
        plant = mk_factory(f"Plant {n:02d}", f"P{n:02d}")
        for inventory_type in (STORAGE, DAMAGED, WASTE, SCRAP):
            mk_stock(i1, plant, inventory_type=inventory_type)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 104
    # Then 2
    assert len({row.id for row in result}) == 104


def test_inv_r_05__restore_flushed_not_committed(db, u1, f1, i1, mk_stock):
    """INV-R-05 — the restore is flushed but not committed: a rollback makes the row deleted again.
    Rules: restore R4"""
    s1 = mk_stock(i1, f1, deleted=True)

    with commit_spy(db) as spy:
        sp = db.begin_nested()
        result = dao.restore(db, db_obj=s1)

        # Then 1
        assert result is s1
        # Then 2
        row = reread(db, s1)
        assert row.is_deleted is False

        sp.rollback()
        # Then 3
        row = reread(db, s1)
        assert row.is_deleted is True
        assert row.is_active is False
        # Then 4
        assert row.deleted_at == T0
        assert row.deleted_by == u1.id
        # Then 5
        assert spy.call_count == 0
