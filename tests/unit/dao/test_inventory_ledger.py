"""Unit tests for app/dao/inventory_ledger.py.

Implements tests/unit/dao/inventory_ledger.cases.md, one test per case. Real
Postgres session (`db` fixture). Nothing is mocked and no clock is patched
(spec: no externals).

Built in local-coder mode: the scaffold and the exemplar tests in the first
part of this file are hand-written; tests below a `# [local-coder] <ID>`
comment were written by the local model from one case card each, with
tests/unit/dao/inventory_ledger.helpers.md as its only view of this file.
"""
# ruff: noqa: SIM117, DTZ001, FURB157  (prescribed by the cards: nested with, naive datetimes, Decimal("...") literals)
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from psycopg2.errors import (
    InvalidRowCountInLimitClause,
    InvalidRowCountInResultOffsetClause,
)
from sqlalchemy import func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import ArgumentError, DataError

from app.dao.inventory_ledger import inventory_ledger_dao
from app.models.enums import InventoryTypeEnum
from app.models.factory import Factory
from app.models.inventory_ledger import InventoryLedger
from app.models.item import Item
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton inventory_ledger_dao" (a module-level name, not a fixture)
dao = inventory_ledger_dao

# Convention "STORAGE, DAMAGED, WASTE, SCRAP = the four members of InventoryTypeEnum"
STORAGE = InventoryTypeEnum.STORAGE
DAMAGED = InventoryTypeEnum.DAMAGED
WASTE = InventoryTypeEnum.WASTE
SCRAP = InventoryTypeEnum.SCRAP

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999

# Convention "T1 ... T5" (all naive)
T1 = datetime(2026, 1, 1, 9, 0, 0)
T2 = datetime(2026, 1, 1, 10, 0, 0)
T3 = datetime(2026, 1, 1, 11, 0, 0)
T4 = datetime(2026, 1, 1, 12, 0, 0)
T5 = datetime(2026, 1, 1, 13, 0, 0)


# Convention "HIGH_ID": a marker that `mk_entry(id=HIGH_ID)` replaces, at insert
# time, by high_id(db) below. It is evaluated when the row is inserted, because
# the value depends on the rows and on the sequence position at that moment.
class _HighId:
    def __repr__(self):
        return "HIGH_ID"


HIGH_ID = _HighId()


def high_id(db):
    """Greater of (greatest inventory_ledger.id, 0 if none) and (last_value of the sequence), plus 1000000."""
    max_id = db.execute(select(func.max(InventoryLedger.__table__.c.id))).scalar() or 0
    last_value = db.execute(text("SELECT last_value FROM inventory_ledger_id_seq")).scalar()
    return max(max_id, last_value) + 1000000


# --------------------------------------------------------------------------- #
# Conventions -> fixtures (actors and the eight standing rows)
# --------------------------------------------------------------------------- #

# Convention "W1, W2 = two workspaces rows"
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


# Convention "U1, U2 = two profiles rows"
@pytest.fixture
def u1(db):
    return make_profile(db)


@pytest.fixture
def u2(db, u1):
    return make_profile(db)


def _add(db, row):
    db.add(row)
    db.flush()
    return row


def _factory(db, name, abbreviation, workspace_id, is_deleted=False):
    return _add(db, Factory(name=name, abbreviation=abbreviation, workspace_id=workspace_id,
                            is_active=True, is_deleted=is_deleted))


def _item(db, name, workspace_id, is_active=True):
    return _add(db, Item(name=name, name_normalized=name.lower(), unit="pcs",
                         workspace_id=workspace_id, is_active=is_active))


# Convention "F1, F2, F9, FD" (standing factories; FD is the soft-deleted one)
@pytest.fixture
def f1(db, w1):
    return _factory(db, "Factory One", "F1", w1.id)


@pytest.fixture
def f2(db, w1, f1):
    return _factory(db, "Factory Two", "F2", w1.id)


@pytest.fixture
def f9(db, w2, f2):
    return _factory(db, "Factory Nine", "F9", w2.id)


@pytest.fixture
def fd(db, w1, f9):
    return _factory(db, "Old Plant", "OP", w1.id, is_deleted=True)


# Convention "I1, I2, I9, IR" (standing items; IR is the removed catalog item)
@pytest.fixture
def i1(db, w1, fd):
    return _item(db, "Bolt", w1.id)


@pytest.fixture
def i2(db, w1, i1):
    return _item(db, "Nut", w1.id)


@pytest.fixture
def i9(db, w2, i2):
    return _item(db, "Bolt", w2.id)


@pytest.fixture
def ir(db, w1, i9):
    return _item(db, "Old Gasket", w1.id, is_active=False)


# Convention "These eight rows exist in every test and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(db, w1, w2, u1, u2, f1, f2, f9, fd, i1, i2, i9, ir):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builders (fixtures; each inserts one row and flushes)
# --------------------------------------------------------------------------- #

# Convention "entry" (the default inventory_ledger row)
@pytest.fixture
def mk_entry(db, w1, u1, f1, i1):
    """mk_entry(performed_at=..., **columns) -> InventoryLedger. Keywords only."""
    def _mk(*, performed_at, **columns):
        fields = {
            "workspace_id": w1.id, "factory_id": f1.id, "item_id": i1.id,
            "inventory_type": STORAGE, "transaction_type": "manual_add", "quantity": 1,
            "qty_before": 0, "qty_after": 5, "avg_price_after": Decimal("2.00"),
            "performed_by": u1.id, "source_type": None, "source_id": None,
            "performed_at": performed_at,
        }
        fields.update(columns)
        if fields.get("id") is HIGH_ID:
            fields["id"] = high_id(db)
        return _add(db, InventoryLedger(**fields))
    return _mk


# Convention "X9" (the other workspace's entry) - its own builder, so that no
# test expands the shorthand by hand
@pytest.fixture
def mk_x9(mk_entry, w2, f9, i9):
    """mk_x9() -> InventoryLedger. Takes no arguments."""
    def _mk():
        return mk_entry(performed_at=T5, workspace_id=w2.id, factory_id=f9.id, item_id=i9.id)
    return _mk


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (plain functions; no expected values inside)
# --------------------------------------------------------------------------- #

def _id_of(row):
    """Primary key of a row, without touching its (possibly expired) attributes."""
    return sa_inspect(row).identity[0]


# Convention "re-read X": expire_all, then SELECT X by id
def reread(db, row):
    """Fresh copy of `row` from the database, or None if it is gone."""
    model, row_id = type(row), _id_of(row)
    db.expire_all()
    return db.execute(select(model).where(model.id == row_id)).scalar_one_or_none()


# Convention "unchanged(X)": every column of X, straight from the table
def snap(db, row):
    """Dict column -> database value of `row`, or None if it is gone."""
    table = type(row).__table__
    found = db.execute(select(table).where(table.c.id == _id_of(row))).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "count:" lines: rows of the table in all workspaces
def count_rows(db, model):
    return db.execute(select(func.count()).select_from(model.__table__)).scalar_one()


# Convention "nothing written": row counts of inventory_ledger, factories and items
def written(db):
    return {"inventory_ledger": count_rows(db, InventoryLedger),
            "factories": count_rows(db, Factory), "items": count_rows(db, Item)}


# Convention "ids(result)": the ids in the order returned (the order is part of the check)
def ids(result):
    return [row.id for row in result]


# --------------------------------------------------------------------------- #
# Exemplar tests (hand-written; shown verbatim in inventory_ledger.helpers.md)
# --------------------------------------------------------------------------- #

def test_led_pf_01__returns_that_user_s_entries_of_every_type_factory_item_and_transaction(db, w1, u1, u2, f2, i2, mk_entry):
    """LED-PF-01 — returns that user's entries of every type, factory, item and transaction type.
    Rules: `get_by_performer` R1, R4"""
    e1 = mk_entry(performed_at=T1)
    mk_entry(performed_at=T3, performed_by=u2.id)
    mk_entry(performed_at=T2, performed_by=None)
    e4 = mk_entry(performed_at=T4, inventory_type=DAMAGED, factory_id=f2.id, item_id=i2.id, transaction_type="sale")

    result = dao.get_by_performer(db, performed_by=u1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [e4.id, e1.id]
    # Then 3
    assert isinstance(result[0], InventoryLedger)


def test_led_w_04__a_call_for_the_other_workspace_returns_only_that_workspace_s_entry(db, w2, mk_entry, mk_x9):
    """LED-W-04 — a call for the other workspace returns only that workspace's entry.
    Rules: `get_by_workspace` R1"""
    mk_entry(performed_at=T1)
    x9 = mk_x9()

    result = dao.get_by_workspace(db, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [x9.id]


def test_led_w_33__negative_limit_is_rejected_by_the_database_and_nothing_changes(db, w1, mk_entry):
    """LED-W-33 — negative limit is rejected by the database and nothing changes.
    Rules: `get_by_workspace` R10, Errors row 1"""
    e1 = mk_entry(performed_at=T1)
    before = written(db)
    before_e1 = snap(db, e1)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_workspace(db, workspace_id=w1.id, limit=-1)

    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInLimitClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201W"
    # Then 4
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 5
    assert written(db) == before
    # Then 6
    assert snap(db, e1) == before_e1


@pytest.mark.xfail(strict=True, reason="BUG-655: Inventory balance and inventory reconcile crash whenever the bucket has history")
def test_led_bal_12__newer_entries_of_other_buckets_do_not_change_the_balance(db, w1, w2, f1, f2, i1, i2, mk_entry):
    """LED-BAL-12 — newer entries of other buckets do not change the balance.
    Rules: `calculate_balance` R4 [BUG-655], R3"""
    mk_entry(performed_at=T1, qty_after=20, avg_price_after=Decimal("6.00"))
    mk_entry(performed_at=T2, inventory_type=DAMAGED, qty_after=91)
    mk_entry(performed_at=T3, factory_id=f2.id, qty_after=92)
    mk_entry(performed_at=T4, item_id=i2.id, qty_after=93)
    mk_entry(performed_at=T5, workspace_id=w2.id, qty_after=94)

    result = dao.calculate_balance(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result[0] == 20
    # Then 2
    assert result[1] == Decimal("120.00")


# --------------------------------------------------------------------------- #
# Cards marked "Author: claude" (hand-written): the 101-entry cases
# --------------------------------------------------------------------------- #

def mk_101(mk_entry):
    """Given "101 entries N1 ... N101, inserted in that order": Nk has
    performed_at = datetime(2026, 1, 1, 0, 0) + timedelta(minutes=k) and is
    otherwise the default entry. Returns {k: Nk}."""
    return {k: mk_entry(performed_at=datetime(2026, 1, 1, 0, 0) + timedelta(minutes=k)) for k in range(1, 102)}


def test_led_w_28__default_limit_returns_the_100_newest_of_101_entries(db, w1, mk_entry):
    """LED-W-28 — default limit returns the 100 newest of 101 entries.
    Rules: `get_by_workspace` R8"""
    n = mk_101(mk_entry)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert result[0].id == n[101].id
    # Then 3
    assert result[99].id == n[2].id
    # Then 4
    assert n[1].id not in ids(result)


def test_led_w_29__an_explicit_limit_of_101_returns_all_101_entries(db, w1, mk_entry):
    """LED-W-29 — an explicit limit of 101 returns all 101 entries.
    Rules: `get_by_workspace` R8"""
    n = mk_101(mk_entry)

    result = dao.get_by_workspace(db, workspace_id=w1.id, limit=101)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert result[0].id == n[101].id
    # Then 3
    assert result[100].id == n[1].id


def test_led_tt_26__default_limit_returns_the_100_newest_of_101_entries_of_that_type(db, w1, mk_entry):
    """LED-TT-26 — default limit returns the 100 newest of 101 entries of that type.
    Rules: `get_by_transaction_type` R5"""
    n = mk_101(mk_entry)

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert result[0].id == n[101].id
    # Then 3
    assert result[99].id == n[2].id
    # Then 4
    assert n[1].id not in ids(result)


def test_led_dr_25__default_limit_returns_the_100_newest_of_101_entries_inside_the_window(db, w1, mk_entry):
    """LED-DR-25 — default limit returns the 100 newest of 101 entries inside the window.
    Rules: `get_by_date_range` R6"""
    n = mk_101(mk_entry)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=datetime(2026, 1, 1, 0, 0, 0), end_date=datetime(2026, 1, 1, 2, 0, 0))

    # Then 1
    assert len(result) == 100
    # Then 2
    assert result[0].id == n[101].id
    # Then 3
    assert result[99].id == n[2].id
    # Then 4
    assert n[1].id not in ids(result)


def test_led_pf_15__default_limit_returns_the_user_s_100_newest_of_101_entries(db, w1, u1, mk_entry):
    """LED-PF-15 — default limit returns the user's 100 newest of 101 entries.
    Rules: `get_by_performer` R5"""
    n = mk_101(mk_entry)

    result = dao.get_by_performer(db, performed_by=u1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert result[0].id == n[101].id
    # Then 3
    assert result[99].id == n[2].id
    # Then 4
    assert n[1].id not in ids(result)


# --------------------------------------------------------------------------- #
# Tests written by the local model, one card each
# --------------------------------------------------------------------------- #

# [local-coder] LED-W-02
def test_led_w_02__with_no_filter_entries_of_every_type_factory_item_transaction_type_and(db, w1, u2, f2, i2, mk_entry):
    """LED-W-02 — with no filter, entries of every type, factory, item, transaction type and performer are returned.
    Rules: `get_by_workspace` R2"""
    e1 = mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T2, inventory_type=DAMAGED, factory_id=f2.id)
    e3 = mk_entry(performed_at=T3, item_id=i2.id, transaction_type="sale", performed_by=None)
    e4 = mk_entry(performed_at=T4, inventory_type=SCRAP, performed_by=u2.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e4.id, e3.id, e2.id, e1.id]


# [local-coder] LED-TT-04
def test_led_tt_04__a_trailing_space_in_the_transaction_type_is_not_trimmed(db, w1, mk_entry):
    """LED-TT-04 — a trailing space in the transaction type is not trimmed.
    Rules: `get_by_transaction_type` R1"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T2, transaction_type="sale")

    result = dao.get_by_transaction_type(db, transaction_type="manual_add ", workspace_id=w1.id)

    # Then 1
    assert result == []


# [local-coder] LED-TT-22
@pytest.mark.xfail(strict=True, reason="BUG-640: Ledger lists ordered by performed_at only; ties in no fixed order")
def test_led_tt_22__entries_sharing_a_performed_at_come_back_greatest_id_first(db, w1, mk_entry):
    """LED-TT-22 — entries sharing a performed_at come back greatest id first.
    Rules: `get_by_transaction_type` R4a [BUG-640]"""
    eb = mk_entry(performed_at=T1)
    ec = mk_entry(performed_at=T1, id=HIGH_ID)
    ea = mk_entry(performed_at=T1)

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [ec.id, ea.id, eb.id]


# [local-coder] LED-DR-02
def test_led_dr_02__bounds_one_microsecond_inside_the_outer_entries_keep_only_the_middle_e(db, w1, mk_entry):
    """LED-DR-02 — bounds one microsecond inside the outer entries keep only the middle entry.
    Rules: `get_by_date_range` R1"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T3)
    e3 = mk_entry(performed_at=T2)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=datetime(2026, 1, 1, 9, 0, 0, 1), end_date=datetime(2026, 1, 1, 10, 59, 59, 999999))

    # Then 1
    assert ids(result) == [e3.id]


# [local-coder] LED-DR-07
def test_led_dr_07__start_date_none_is_refused_before_any_query_and_nothing_changes(db, w1, mk_entry):
    """LED-DR-07 — start_date None is refused before any query and nothing changes.
    Rules: `get_by_date_range` R3, Errors row 1"""
    e1 = mk_entry(performed_at=T1)
    before = written(db)
    before_e1 = snap(db, e1)

    # Then 1
    with pytest.raises(ArgumentError) as exc:
        dao.get_by_date_range(db, workspace_id=w1.id, start_date=None, end_date=T3)

    # Then 2
    assert str(exc.value).startswith("Only '=', '!=', 'is_()', 'is_not()', 'is_distinct_from()', 'is_not_distinct_from()' operators can be used with None/True/False")
    # Then 3
    assert written(db) == before
    # Then 4
    assert snap(db, e1) == before_e1


# [local-coder] LED-DR-19
@pytest.mark.xfail(strict=True, reason="BUG-885: Inventory ledger lists treat factory_id=0 / item_id=0 as 'no filter'")
def test_led_dr_19__factory_id_0_filters_and_returns_an_empty_list(db, w1, f2, mk_entry):
    """LED-DR-19 — factory_id 0 filters and returns an empty list.
    Rules: `get_by_date_range` R4a [BUG-885]"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T2, factory_id=f2.id)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T3, factory_id=0)

    # Then 1
    assert result == []


# [local-coder] LED-PF-03
def test_led_pf_03__an_entry_the_same_user_performed_in_another_workspace_is_not_returned(db, w1, u1, mk_entry, mk_x9):
    """LED-PF-03 — an entry the same user performed in another workspace is not returned.
    Rules: `get_by_performer` R2"""
    e1 = mk_entry(performed_at=T1)
    mk_x9()

    result = dao.get_by_performer(db, performed_by=u1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]


# [local-coder] LED-BAL-11
@pytest.mark.xfail(strict=True, reason="BUG-655: Inventory balance and inventory reconcile crash whenever the bucket has history")
def test_led_bal_11__the_balance_comes_from_the_entry_with_the_greatest_performed_at(db, w1, f1, i1, mk_entry):
    """LED-BAL-11 — the balance comes from the entry with the greatest performed_at.
    Rules: `calculate_balance` R4 [BUG-655]"""
    mk_entry(performed_at=T1, qty_after=30, avg_price_after=Decimal("7.00"))
    mk_entry(performed_at=T3, qty_after=20, avg_price_after=Decimal("6.00"))
    mk_entry(performed_at=T2, qty_after=10, avg_price_after=Decimal("4.00"))

    result = dao.calculate_balance(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result[0] == 20
    # Then 2
    assert result[1] == Decimal("120.00")


# [local-coder] LED-BAL-13
@pytest.mark.xfail(strict=True, reason="BUG-641: 'Latest entry' balance lookups pick an arbitrary row on a timestamp tie; BUG-655: Inventory balance and inventory reconcile crash whenever the bucket has history")
def test_led_bal_13__among_entries_sharing_the_newest_performed_at_the_greatest_id_gives_th(db, w1, f1, i1, mk_entry):
    """LED-BAL-13 — among entries sharing the newest performed_at the greatest id gives the balance.
    Rules: `calculate_balance` R4a [BUG-641, BUG-655]"""
    mk_entry(performed_at=T1, qty_after=15)
    mk_entry(performed_at=T1, id=HIGH_ID, qty_after=10)
    mk_entry(performed_at=T1, qty_after=99)

    result = dao.calculate_balance(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result[0] == 10
    # Then 2
    assert result[1] == Decimal("20.00")


# [local-coder] LED-LE-06
@pytest.mark.xfail(strict=True, reason="BUG-664: 'Latest ledger entry' picked by timestamp alone can pick a stale row")
def test_led_le_06__among_entries_sharing_the_newest_performed_at_the_greatest_id_wins(db, w1, f1, i1, mk_entry):
    """LED-LE-06 — among entries sharing the newest performed_at the greatest id wins.
    Rules: `get_latest_entry` R3 [BUG-664]"""
    mk_entry(performed_at=T1, qty_after=15)
    ec = mk_entry(performed_at=T1, id=HIGH_ID, qty_after=10)
    mk_entry(performed_at=T1, qty_after=99)

    result = dao.get_latest_entry(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result.id == ec.id
    # Then 2
    assert result.qty_after == 10


# [local-coder] LED-LE-18
def test_led_le_18__the_lookup_changes_nothing_in_the_database(db, w1, f1, i1, mk_entry):
    """LED-LE-18 — the lookup changes nothing in the database.
    Rules: `get_latest_entry` R7"""
    e1 = mk_entry(performed_at=T1, qty_after=20, avg_price_after=Decimal("6.00"))
    before = written(db)
    before_e1 = snap(db, e1)

    result = dao.get_latest_entry(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result.id == e1.id
    # Then 2
    assert written(db) == before
    # Then 3
    assert snap(db, e1) == before_e1
    # Then 4
    row = reread(db, e1)
    assert row.qty_after == 20
    assert row.performed_at == T1
    # Then 5
    assert row.avg_price_after == Decimal("6.00")
    # Then 6
    assert count_rows(db, InventoryLedger) == 1


# [local-coder] LED-EX-10
def test_led_ex_10__source_id_none_matches_an_entry_whose_source_id_is_null(db, w1, mk_entry):
    """LED-EX-10 — source_id None matches an entry whose source id is NULL.
    Rules: `exists_for_source` R4"""
    mk_entry(performed_at=T1, source_type="po")

    result = dao.exists_for_source(db, workspace_id=w1.id, source_type="po", source_id=None)

    # Then 1
    assert result is True


# [local-coder] LED-W-01
def test_led_w_01__returns_a_list_of_ledger_rows_newest_first_whatever_the_insertion(db, w1, mk_entry):
    """LED-W-01 — returns a list of ledger rows, newest first whatever the insertion order.
    Rules: `get_by_workspace` R2, R7"""
    e1 = mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T3)
    e3 = mk_entry(performed_at=T2)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [e2.id, e3.id, e1.id]
    # Then 3
    assert isinstance(result[0], InventoryLedger)


# [local-coder] LED-W-03
def test_led_w_03__an_entry_of_another_workspace_is_not_returned(db, w1, mk_entry, mk_x9):
    """LED-W-03 — an entry of another workspace is not returned.
    Rules: `get_by_workspace` R1"""
    e1 = mk_entry(performed_at=T1)
    mk_x9()

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]


# [local-coder] LED-W-05
def test_led_w_05__another_workspace_s_entry_is_not_returned_when_its_factory_id_is_the(db, w1, f9, mk_entry, mk_x9):
    """LED-W-05 — another workspace's entry is not returned when its factory id is the filter.
    Rules: `get_by_workspace` R1, R4"""
    mk_entry(performed_at=T1)
    mk_x9()

    result = dao.get_by_workspace(db, workspace_id=w1.id, factory_id=f9.id)

    # Then 1
    assert result == []


# [local-coder] LED-W-06
def test_led_w_06__another_workspace_s_entry_is_not_returned_when_its_item_id_is_the(db, w1, i9, mk_entry, mk_x9):
    """LED-W-06 — another workspace's entry is not returned when its item id is the filter.
    Rules: `get_by_workspace` R1, R5"""
    mk_entry(performed_at=T1)
    mk_x9()

    result = dao.get_by_workspace(db, workspace_id=w1.id, item_id=i9.id)

    # Then 1
    assert result == []


# [local-coder] LED-W-07
def test_led_w_07__an_entry_of_the_other_workspace_booked_in_this_workspace_s_factory(db, w1, w2, f1, i1, mk_entry):
    """LED-W-07 — an entry of the other workspace booked in this workspace's factory and item is not returned.
    Rules: `get_by_workspace` R1"""
    e1 = mk_entry(performed_at=T1)
    mk_entry(performed_at=T2, workspace_id=w2.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, factory_id=f1.id, item_id=i1.id)

    # Then 1
    assert ids(result) == [e1.id]


# [local-coder] LED-W-08
def test_led_w_08__an_unknown_workspace_id_returns_an_empty_list(db, mk_entry):
    """LED-W-08 — an unknown workspace id returns an empty list.
    Rules: `get_by_workspace` R1"""
    mk_entry(performed_at=T1)

    result = dao.get_by_workspace(db, workspace_id=MISSING)

    # Then 1
    assert result == []


# [local-coder] LED-W-09
def test_led_w_09__inventory_type_filter_keeps_only_that_type(db, w1, mk_entry):
    """LED-W-09 — inventory_type filter keeps only that type.
    Rules: `get_by_workspace` R3"""
    mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T2, inventory_type=DAMAGED)
    mk_entry(performed_at=T3, inventory_type=SCRAP)

    result = dao.get_by_workspace(db, workspace_id=w1.id, inventory_type=DAMAGED)

    # Then 1
    assert ids(result) == [e2.id]


# [local-coder] LED-W-10
def test_led_w_10__a_type_with_no_entries_returns_an_empty_list(db, w1, mk_entry):
    """LED-W-10 — a type with no entries returns an empty list.
    Rules: `get_by_workspace` R3"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T2, inventory_type=DAMAGED)

    result = dao.get_by_workspace(db, workspace_id=w1.id, inventory_type=WASTE)

    # Then 1
    assert result == []


# [local-coder] LED-W-11
def test_led_w_11__explicit_none_for_every_optional_filter_applies_no_filter(db, w1, f2, i2, mk_entry):
    """LED-W-11 — explicit None for every optional filter applies no filter.
    Rules: `get_by_workspace` R3, R4, R5"""
    e1 = mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T2, inventory_type=DAMAGED, factory_id=f2.id, item_id=i2.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, inventory_type=None, factory_id=None, item_id=None)

    # Then 1
    assert ids(result) == [e2.id, e1.id]


# [local-coder] LED-W-12
def test_led_w_12__factory_id_filter_keeps_only_that_factory(db, w1, f2, mk_entry):
    """LED-W-12 — factory_id filter keeps only that factory.
    Rules: `get_by_workspace` R4"""
    e1 = mk_entry(performed_at=T2, factory_id=f2.id)
    mk_entry(performed_at=T1)
    e3 = mk_entry(performed_at=T3, factory_id=f2.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, factory_id=f2.id)

    # Then 1
    assert ids(result) == [e3.id, e1.id]


# [local-coder] LED-W-13
def test_led_w_13__a_factory_id_that_does_not_exist_returns_an_empty_list(db, w1, mk_entry):
    """LED-W-13 — a factory id that does not exist returns an empty list.
    Rules: `get_by_workspace` R4"""
    mk_entry(performed_at=T1)

    result = dao.get_by_workspace(db, workspace_id=w1.id, factory_id=MISSING)

    # Then 1
    assert result == []


# [local-coder] LED-W-14
def test_led_w_14__a_negative_factory_id_returns_an_empty_list(db, w1, mk_entry):
    """LED-W-14 — a negative factory id returns an empty list.
    Rules: `get_by_workspace` R4"""
    mk_entry(performed_at=T1)

    result = dao.get_by_workspace(db, workspace_id=w1.id, factory_id=-1)

    # Then 1
    assert result == []


# [local-coder] LED-W-15
@pytest.mark.xfail(strict=True, reason="BUG-885: Inventory ledger lists treat factory_id=0 / item_id=0 as 'no filter'")
def test_led_w_15__factory_id_0_filters_and_returns_an_empty_list(db, w1, f2, mk_entry):
    """LED-W-15 — factory_id 0 filters and returns an empty list.
    Rules: `get_by_workspace` R4a [BUG-885]"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T2, factory_id=f2.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, factory_id=0)

    # Then 1
    assert result == []


# [local-coder] LED-W-16
def test_led_w_16__item_id_filter_keeps_only_that_item(db, w1, i2, mk_entry):
    """LED-W-16 — item_id filter keeps only that item.
    Rules: `get_by_workspace` R5"""
    e1 = mk_entry(performed_at=T2, item_id=i2.id)
    mk_entry(performed_at=T1)
    e3 = mk_entry(performed_at=T3, item_id=i2.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, item_id=i2.id)

    # Then 1
    assert ids(result) == [e3.id, e1.id]


# [local-coder] LED-W-17
def test_led_w_17__an_item_id_that_does_not_exist_returns_an_empty_list(db, w1, mk_entry):
    """LED-W-17 — an item id that does not exist returns an empty list.
    Rules: `get_by_workspace` R5"""
    mk_entry(performed_at=T1)

    result = dao.get_by_workspace(db, workspace_id=w1.id, item_id=MISSING)

    # Then 1
    assert result == []


# [local-coder] LED-W-18
@pytest.mark.xfail(strict=True, reason="BUG-885: Inventory ledger lists treat factory_id=0 / item_id=0 as 'no filter'")
def test_led_w_18__item_id_0_filters_and_returns_an_empty_list(db, w1, i2, mk_entry):
    """LED-W-18 — item_id 0 filters and returns an empty list.
    Rules: `get_by_workspace` R5a [BUG-885]"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T2, item_id=i2.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, item_id=0)

    # Then 1
    assert result == []


# [local-coder] LED-W-19
def test_led_w_19__type_factory_and_item_filters_combine_with_and(db, w1, f1, f2, i1, i2, mk_entry):
    """LED-W-19 — type, factory and item filters combine with AND.
    Rules: `get_by_workspace` R6"""
    e1 = mk_entry(performed_at=T1)
    mk_entry(performed_at=T2, factory_id=f2.id)
    mk_entry(performed_at=T3, inventory_type=DAMAGED)
    mk_entry(performed_at=T4, item_id=i2.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, inventory_type=STORAGE, factory_id=f1.id, item_id=i1.id)

    # Then 1
    assert ids(result) == [e1.id]


# [local-coder] LED-W-20
def test_led_w_20__two_filters_combine_with_and_and_the_result_stays_newest_first(db, w1, f1, f2, mk_entry):
    """LED-W-20 — two filters combine with AND and the result stays newest first.
    Rules: `get_by_workspace` R6, R7"""
    e1 = mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T3)
    mk_entry(performed_at=T2, inventory_type=DAMAGED)
    mk_entry(performed_at=T4, factory_id=f2.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, inventory_type=STORAGE, factory_id=f1.id)

    # Then 1
    assert ids(result) == [e2.id, e1.id]


# [local-coder] LED-W-21
@pytest.mark.xfail(strict=True, reason="BUG-640: Ledger lists ordered by performed_at only; ties in no fixed order")
def test_led_w_21__entries_sharing_a_performed_at_come_back_greatest_id_first(db, w1, mk_entry):
    """LED-W-21 — entries sharing a performed_at come back greatest id first.
    Rules: `get_by_workspace` R7a [BUG-640]"""
    eb = mk_entry(performed_at=T1)
    ec = mk_entry(performed_at=T1, id=HIGH_ID)
    ea = mk_entry(performed_at=T1)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [ec.id, ea.id, eb.id]


# [local-coder] LED-W-22
def test_led_w_22__entries_sharing_a_performed_at_are_each_returned_once_between_the(db, w1, mk_entry):
    """LED-W-22 — entries sharing a performed_at are each returned once, between the newer and the older entry.
    Rules: `get_by_workspace` R7"""
    e1 = mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T2)
    e3 = mk_entry(performed_at=T2)
    e4 = mk_entry(performed_at=T3)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 4
    # Then 2
    assert result[0].id == e4.id
    # Then 3
    assert result[3].id == e1.id
    # Then 4
    assert sorted(ids(result)) == [e1.id, e2.id, e3.id, e4.id]


# [local-coder] LED-W-23
def test_led_w_23__skip_1_and_limit_1_return_exactly_the_second_newest_entry(db, w1, mk_entry):
    """LED-W-23 — skip 1 and limit 1 return exactly the second newest entry.
    Rules: `get_by_workspace` R8"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T3)
    e3 = mk_entry(performed_at=T2)

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [e3.id]


# [local-coder] LED-W-24
def test_led_w_24__first_window_of_two(db, w1, mk_entry):
    """LED-W-24 — first window of two.
    Rules: `get_by_workspace` R8"""
    mk_entry(performed_at=T3)
    mk_entry(performed_at=T1)
    e3 = mk_entry(performed_at=T5)
    mk_entry(performed_at=T2)
    e5 = mk_entry(performed_at=T4)

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=0, limit=2)

    # Then 1
    assert ids(result) == [e3.id, e5.id]


# [local-coder] LED-W-25
def test_led_w_25__second_window_of_two_continues_without_repeat_or_gap(db, w1, mk_entry):
    """LED-W-25 — second window of two continues without repeat or gap.
    Rules: `get_by_workspace` R8"""
    e1 = mk_entry(performed_at=T3)
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T5)
    e4 = mk_entry(performed_at=T2)
    mk_entry(performed_at=T4)

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=2, limit=2)

    # Then 1
    assert ids(result) == [e1.id, e4.id]


# [local-coder] LED-W-26
def test_led_w_26__last_window_is_short(db, w1, mk_entry):
    """LED-W-26 — last window is short.
    Rules: `get_by_workspace` R8"""
    mk_entry(performed_at=T3)
    e2 = mk_entry(performed_at=T1)
    mk_entry(performed_at=T5)
    mk_entry(performed_at=T2)
    mk_entry(performed_at=T4)

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=4, limit=2)

    # Then 1
    assert ids(result) == [e2.id]


# [local-coder] LED-W-27
def test_led_w_27__skip_and_limit_are_applied_after_filtering(db, w1, f1, f2, mk_entry):
    """LED-W-27 — skip and limit are applied after filtering.
    Rules: `get_by_workspace` R8"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T2, factory_id=f2.id)
    e3 = mk_entry(performed_at=T3)
    mk_entry(performed_at=T4, factory_id=f2.id)
    mk_entry(performed_at=T5)

    result = dao.get_by_workspace(db, workspace_id=w1.id, factory_id=f1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [e3.id]


# [local-coder] LED-W-30
def test_led_w_30__limit_0_returns_an_empty_list(db, w1, mk_entry):
    """LED-W-30 — limit 0 returns an empty list.
    Rules: `get_by_workspace` R9"""
    mk_entry(performed_at=T1)

    result = dao.get_by_workspace(db, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [local-coder] LED-W-31
def test_led_w_31__skip_equal_to_the_number_of_matching_entries_returns_an_empty_list(db, w1, mk_entry):
    """LED-W-31 — skip equal to the number of matching entries returns an empty list.
    Rules: `get_by_workspace` R9"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T2)

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [local-coder] LED-W-32
def test_led_w_32__skip_one_below_the_number_of_matching_entries_returns_the_oldest_entry(db, w1, mk_entry):
    """LED-W-32 — skip one below the number of matching entries returns the oldest entry.
    Rules: `get_by_workspace` R9, R8"""
    e1 = mk_entry(performed_at=T1)
    mk_entry(performed_at=T2)

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=1)

    # Then 1
    assert ids(result) == [e1.id]


# [local-coder] LED-W-34
def test_led_w_34__negative_skip_is_rejected_by_the_database_and_nothing_changes(db, w1, mk_entry):
    """LED-W-34 — negative skip is rejected by the database and nothing changes.
    Rules: `get_by_workspace` R10, Errors row 2"""
    e1 = mk_entry(performed_at=T1)
    before = written(db)
    before_e1 = snap(db, e1)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_workspace(db, workspace_id=w1.id, skip=-1)

    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201X"
    # Then 4
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 5
    assert written(db) == before
    # Then 6
    assert snap(db, e1) == before_e1


# [local-coder] LED-W-35
def test_led_w_35__an_entry_booked_in_a_soft_deleted_factory_is_listed_like_any_other(db, w1, fd, mk_entry):
    """LED-W-35 — an entry booked in a soft-deleted factory is listed like any other.
    Rules: `get_by_workspace` R11"""
    e1 = mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T2, factory_id=fd.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e2.id, e1.id]


# [local-coder] LED-W-36
def test_led_w_36__the_id_of_a_soft_deleted_factory_works_as_the_factory_filter(db, w1, fd, mk_entry):
    """LED-W-36 — the id of a soft-deleted factory works as the factory filter.
    Rules: `get_by_workspace` R11"""
    mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T2, factory_id=fd.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, factory_id=fd.id)

    # Then 1
    assert ids(result) == [e2.id]


# [local-coder] LED-W-37
def test_led_w_37__an_entry_of_a_removed_catalog_item_is_listed_like_any_other(db, w1, ir, mk_entry):
    """LED-W-37 — an entry of a removed catalog item is listed like any other.
    Rules: `get_by_workspace` R12"""
    e1 = mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T2, item_id=ir.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e2.id, e1.id]


# [local-coder] LED-W-38
def test_led_w_38__the_id_of_a_removed_catalog_item_works_as_the_item_filter(db, w1, ir, mk_entry):
    """LED-W-38 — the id of a removed catalog item works as the item filter.
    Rules: `get_by_workspace` R12"""
    mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T2, item_id=ir.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, item_id=ir.id)

    # Then 1
    assert ids(result) == [e2.id]


# [local-coder] LED-W-39
def test_led_w_39__listing_changes_nothing_in_the_database(db, w1, mk_entry):
    """LED-W-39 — listing changes nothing in the database.
    Rules: `get_by_workspace` R13"""
    e1 = mk_entry(performed_at=T1, qty_after=20, avg_price_after=Decimal("6.00"))
    before = written(db)
    before_e1 = snap(db, e1)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]
    # Then 2
    assert written(db) == before
    # Then 3
    assert snap(db, e1) == before_e1
    # Then 4
    row = reread(db, e1)
    assert row.qty_after == 20
    assert row.performed_at == T1
    # Then 5
    assert row.avg_price_after == Decimal("6.00")
    # Then 6
    assert count_rows(db, InventoryLedger) == 1


# [local-coder] LED-TT-01
def test_led_tt_01__returns_only_the_entries_of_that_transaction_type_newest_first(db, w1, mk_entry):
    """LED-TT-01 — returns only the entries of that transaction type, newest first.
    Rules: `get_by_transaction_type` R1, R4"""
    e1 = mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T3)
    e3 = mk_entry(performed_at=T2)
    mk_entry(performed_at=T4, transaction_type="sale")

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [e2.id, e3.id, e1.id]
    # Then 3
    assert isinstance(result[0], InventoryLedger)


# [local-coder] LED-TT-02
def test_led_tt_02__the_other_transaction_type_returns_only_its_own_entry(db, w1, mk_entry):
    """LED-TT-02 — the other transaction type returns only its own entry.
    Rules: `get_by_transaction_type` R1"""
    mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T2, transaction_type="sale")
    mk_entry(performed_at=T3)

    result = dao.get_by_transaction_type(db, transaction_type="sale", workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e2.id]


# [local-coder] LED-TT-03
def test_led_tt_03__the_transaction_type_is_compared_case_sensitively(db, w1, mk_entry):
    """LED-TT-03 — the transaction type is compared case-sensitively.
    Rules: `get_by_transaction_type` R1"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T2, transaction_type="sale")

    result = dao.get_by_transaction_type(db, transaction_type="MANUAL_ADD", workspace_id=w1.id)

    # Then 1
    assert result == []


# [local-coder] LED-TT-05
def test_led_tt_05__a_percent_sign_in_the_transaction_type_is_an_ordinary_character(db, w1, mk_entry):
    """LED-TT-05 — a percent sign in the transaction type is an ordinary character.
    Rules: `get_by_transaction_type` R1"""
    mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T2, transaction_type="manual%")

    result = dao.get_by_transaction_type(db, transaction_type="manual%", workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e2.id]


# [local-coder] LED-TT-06
def test_led_tt_06__an_underscore_in_the_transaction_type_is_an_ordinary_character(db, w1, mk_entry):
    """LED-TT-06 — an underscore in the transaction type is an ordinary character.
    Rules: `get_by_transaction_type` R1"""
    mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T2, transaction_type="manual_ad_")

    result = dao.get_by_transaction_type(db, transaction_type="manual_ad_", workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e2.id]


# [local-coder] LED-TT-07
def test_led_tt_07__an_unknown_transaction_type_returns_an_empty_list(db, w1, mk_entry):
    """LED-TT-07 — an unknown transaction type returns an empty list.
    Rules: `get_by_transaction_type` R1"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T2, transaction_type="sale")

    result = dao.get_by_transaction_type(db, transaction_type="transfer_out", workspace_id=w1.id)

    # Then 1
    assert result == []


# [local-coder] LED-TT-08
def test_led_tt_08__an_empty_transaction_type_returns_an_empty_list(db, w1, mk_entry):
    """LED-TT-08 — an empty transaction type returns an empty list.
    Rules: `get_by_transaction_type` R2"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T2, transaction_type="sale")

    result = dao.get_by_transaction_type(db, transaction_type="", workspace_id=w1.id)

    # Then 1
    assert result == []


# [local-coder] LED-TT-09
def test_led_tt_09__transaction_type_none_returns_an_empty_list(db, w1, mk_entry):
    """LED-TT-09 — transaction type None returns an empty list.
    Rules: `get_by_transaction_type` R2"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T2, transaction_type="sale")

    result = dao.get_by_transaction_type(db, transaction_type=None, workspace_id=w1.id)

    # Then 1
    assert result == []


# [local-coder] LED-TT-10
def test_led_tt_10__an_entry_of_that_type_in_another_workspace_is_not_returned(db, w1, mk_entry, mk_x9):
    """LED-TT-10 — an entry of that type in another workspace is not returned.
    Rules: `get_by_transaction_type` R1"""
    e1 = mk_entry(performed_at=T1)
    mk_x9()

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]


# [local-coder] LED-TT-11
def test_led_tt_11__a_call_for_the_other_workspace_returns_only_that_workspace_s_entry(db, w2, mk_entry, mk_x9):
    """LED-TT-11 — a call for the other workspace returns only that workspace's entry.
    Rules: `get_by_transaction_type` R1"""
    mk_entry(performed_at=T1)
    x9 = mk_x9()

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w2.id)

    # Then 1
    assert ids(result) == [x9.id]


# [local-coder] LED-TT-12
def test_led_tt_12__an_unknown_workspace_id_returns_an_empty_list(db, mk_entry):
    """LED-TT-12 — an unknown workspace id returns an empty list.
    Rules: `get_by_transaction_type` R1"""
    mk_entry(performed_at=T1)

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=MISSING)

    # Then 1
    assert result == []


# [local-coder] LED-TT-13
def test_led_tt_13__inventory_type_filter_narrows_the_entries_of_that_transaction_type(db, w1, mk_entry):
    """LED-TT-13 — inventory_type filter narrows the entries of that transaction type.
    Rules: `get_by_transaction_type` R3"""
    mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T2, inventory_type=DAMAGED)
    mk_entry(performed_at=T3, inventory_type=DAMAGED, transaction_type="sale")

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id, inventory_type=DAMAGED)

    # Then 1
    assert ids(result) == [e2.id]


# [local-coder] LED-TT-14
def test_led_tt_14__factory_id_filter_narrows_the_entries_of_that_transaction_type(db, w1, f2, mk_entry):
    """LED-TT-14 — factory_id filter narrows the entries of that transaction type.
    Rules: `get_by_transaction_type` R3"""
    mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T2, factory_id=f2.id)
    mk_entry(performed_at=T3, factory_id=f2.id, transaction_type="sale")

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id, factory_id=f2.id)

    # Then 1
    assert ids(result) == [e2.id]


# [local-coder] LED-TT-15
def test_led_tt_15__item_id_filter_narrows_the_entries_of_that_transaction_type(db, w1, i2, mk_entry):
    """LED-TT-15 — item_id filter narrows the entries of that transaction type.
    Rules: `get_by_transaction_type` R3"""
    mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T2, item_id=i2.id)
    mk_entry(performed_at=T3, item_id=i2.id, transaction_type="sale")

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id, item_id=i2.id)

    # Then 1
    assert ids(result) == [e2.id]


# [local-coder] LED-TT-16
def test_led_tt_16__type_factory_and_item_filters_combine_with_the_transaction_type_with(db, w1, f1, f2, i1, i2, mk_entry):
    """LED-TT-16 — type, factory and item filters combine with the transaction type with AND.
    Rules: `get_by_transaction_type` R3"""
    e1 = mk_entry(performed_at=T1)
    mk_entry(performed_at=T2, factory_id=f2.id)
    mk_entry(performed_at=T3, inventory_type=DAMAGED)
    mk_entry(performed_at=T4, item_id=i2.id)
    mk_entry(performed_at=T5, transaction_type="sale")

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id, inventory_type=STORAGE, factory_id=f1.id, item_id=i1.id)

    # Then 1
    assert ids(result) == [e1.id]


# [local-coder] LED-TT-17
def test_led_tt_17__explicit_none_for_every_optional_filter_applies_no_filter(db, w1, f2, i2, mk_entry):
    """LED-TT-17 — explicit None for every optional filter applies no filter.
    Rules: `get_by_transaction_type` R3"""
    e1 = mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T2, inventory_type=DAMAGED, factory_id=f2.id, item_id=i2.id)

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id, inventory_type=None, factory_id=None, item_id=None)

    # Then 1
    assert ids(result) == [e2.id, e1.id]


# [local-coder] LED-TT-18
def test_led_tt_18__a_factory_id_that_does_not_exist_returns_an_empty_list(db, w1, mk_entry):
    """LED-TT-18 — a factory id that does not exist returns an empty list.
    Rules: `get_by_transaction_type` R3"""
    mk_entry(performed_at=T1)

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id, factory_id=MISSING)

    # Then 1
    assert result == []


# [local-coder] LED-TT-19
def test_led_tt_19__an_item_id_that_does_not_exist_returns_an_empty_list(db, w1, mk_entry):
    """LED-TT-19 — an item id that does not exist returns an empty list.
    Rules: `get_by_transaction_type` R3"""
    mk_entry(performed_at=T1)

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id, item_id=MISSING)

    # Then 1
    assert result == []


# [local-coder] LED-TT-20
@pytest.mark.xfail(strict=True, reason="BUG-885: Inventory ledger lists treat factory_id=0 / item_id=0 as 'no filter'")
def test_led_tt_20__factory_id_0_filters_and_returns_an_empty_list(db, w1, f2, mk_entry):
    """LED-TT-20 — factory_id 0 filters and returns an empty list.
    Rules: `get_by_transaction_type` R3a [BUG-885]"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T2, factory_id=f2.id)

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id, factory_id=0)

    # Then 1
    assert result == []


# [local-coder] LED-TT-21
@pytest.mark.xfail(strict=True, reason="BUG-885: Inventory ledger lists treat factory_id=0 / item_id=0 as 'no filter'")
def test_led_tt_21__item_id_0_filters_and_returns_an_empty_list(db, w1, i2, mk_entry):
    """LED-TT-21 — item_id 0 filters and returns an empty list.
    Rules: `get_by_transaction_type` R3a [BUG-885]"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T2, item_id=i2.id)

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id, item_id=0)

    # Then 1
    assert result == []


# [local-coder] LED-TT-23
def test_led_tt_23__entries_sharing_a_performed_at_are_each_returned_once_between_the(db, w1, mk_entry):
    """LED-TT-23 — entries sharing a performed_at are each returned once, between the newer and the older entry.
    Rules: `get_by_transaction_type` R4"""
    e1 = mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T2)
    e3 = mk_entry(performed_at=T2)
    e4 = mk_entry(performed_at=T3)

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id)

    # Then 1
    assert len(result) == 4
    # Then 2
    assert result[0].id == e4.id
    # Then 3
    assert result[3].id == e1.id
    # Then 4
    assert sorted(ids(result)) == [e1.id, e2.id, e3.id, e4.id]


# [local-coder] LED-TT-24
def test_led_tt_24__skip_1_and_limit_1_return_exactly_the_second_newest_entry(db, w1, mk_entry):
    """LED-TT-24 — skip 1 and limit 1 return exactly the second newest entry.
    Rules: `get_by_transaction_type` R5"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T3)
    e3 = mk_entry(performed_at=T2)

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [e3.id]


# [local-coder] LED-TT-25
def test_led_tt_25__skip_and_limit_are_applied_after_the_transaction_type_filter(db, w1, mk_entry):
    """LED-TT-25 — skip and limit are applied after the transaction type filter.
    Rules: `get_by_transaction_type` R5"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T2, transaction_type="sale")
    e3 = mk_entry(performed_at=T3)
    mk_entry(performed_at=T4, transaction_type="sale")
    mk_entry(performed_at=T5)

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [e3.id]


# [local-coder] LED-TT-27
def test_led_tt_27__limit_0_returns_an_empty_list(db, w1, mk_entry):
    """LED-TT-27 — limit 0 returns an empty list.
    Rules: `get_by_transaction_type` R5"""
    mk_entry(performed_at=T1)

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [local-coder] LED-TT-28
def test_led_tt_28__skip_equal_to_the_number_of_matching_entries_returns_an_empty_list(db, w1, mk_entry):
    """LED-TT-28 — skip equal to the number of matching entries returns an empty list.
    Rules: `get_by_transaction_type` R5"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T2)

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [local-coder] LED-TT-29
def test_led_tt_29__negative_limit_is_rejected_by_the_database_and_nothing_changes(db, w1, mk_entry):
    """LED-TT-29 — negative limit is rejected by the database and nothing changes.
    Rules: `get_by_transaction_type` R5, Errors row 1"""
    e1 = mk_entry(performed_at=T1)
    before = written(db)
    before_e1 = snap(db, e1)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id, limit=-1)

    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInLimitClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201W"
    # Then 4
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 5
    assert written(db) == before
    # Then 6
    assert snap(db, e1) == before_e1


# [local-coder] LED-TT-30
def test_led_tt_30__negative_skip_is_rejected_by_the_database_and_nothing_changes(db, w1, mk_entry):
    """LED-TT-30 — negative skip is rejected by the database and nothing changes.
    Rules: `get_by_transaction_type` R5, Errors row 2"""
    e1 = mk_entry(performed_at=T1)
    before = written(db)
    before_e1 = snap(db, e1)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id, skip=-1)

    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201X"
    # Then 4
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 5
    assert written(db) == before
    # Then 6
    assert snap(db, e1) == before_e1


# [local-coder] LED-TT-31
def test_led_tt_31__entries_of_a_soft_deleted_factory_and_of_a_removed_item_are_listed(db, w1, fd, ir, mk_entry):
    """LED-TT-31 — entries of a soft-deleted factory and of a removed item are listed like any other.
    Rules: `get_by_transaction_type` R6"""
    e1 = mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T2, factory_id=fd.id)
    e3 = mk_entry(performed_at=T3, item_id=ir.id)

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e3.id, e2.id, e1.id]


# [local-coder] LED-DR-01
def test_led_dr_01__both_bounds_are_inclusive_and_the_result_is_newest_first(db, w1, mk_entry):
    """LED-DR-01 — both bounds are inclusive and the result is newest first.
    Rules: `get_by_date_range` R1, R5"""
    e1 = mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T3)
    e3 = mk_entry(performed_at=T2)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T3)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [e2.id, e3.id, e1.id]
    # Then 3
    assert isinstance(result[0], InventoryLedger)


# [local-coder] LED-DR-03
def test_led_dr_03__entries_before_the_start_and_after_the_end_are_left_out(db, w1, mk_entry):
    """LED-DR-03 — entries before the start and after the end are left out.
    Rules: `get_by_date_range` R1"""
    e1 = mk_entry(performed_at=T3)
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T5)
    e4 = mk_entry(performed_at=T2)
    e5 = mk_entry(performed_at=T4)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T2, end_date=T4)

    # Then 1
    assert ids(result) == [e5.id, e1.id, e4.id]


# [local-coder] LED-DR-04
def test_led_dr_04__equal_start_and_end_return_the_entry_performed_at_that_instant(db, w1, mk_entry):
    """LED-DR-04 — equal start and end return the entry performed at that instant.
    Rules: `get_by_date_range` R2"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T3)
    e3 = mk_entry(performed_at=T2)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T2, end_date=T2)

    # Then 1
    assert ids(result) == [e3.id]


# [local-coder] LED-DR-05
def test_led_dr_05__equal_start_and_end_at_an_instant_with_no_entry_return_an_empty_list(db, w1, mk_entry):
    """LED-DR-05 — equal start and end at an instant with no entry return an empty list.
    Rules: `get_by_date_range` R2"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T3)
    mk_entry(performed_at=T2)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=datetime(2026, 1, 1, 10, 30, 0), end_date=datetime(2026, 1, 1, 10, 30, 0))

    # Then 1
    assert result == []


# [local-coder] LED-DR-06
def test_led_dr_06__a_start_later_than_the_end_returns_an_empty_list(db, w1, mk_entry):
    """LED-DR-06 — a start later than the end returns an empty list.
    Rules: `get_by_date_range` R2"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T3)
    mk_entry(performed_at=T2)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T3, end_date=T1)

    # Then 1
    assert result == []


# [local-coder] LED-DR-08
def test_led_dr_08__end_date_none_is_refused_before_any_query_and_nothing_changes(db, w1, mk_entry):
    """LED-DR-08 — end_date None is refused before any query and nothing changes.
    Rules: `get_by_date_range` R3, Errors row 1"""
    e1 = mk_entry(performed_at=T1)
    before = written(db)
    before_e1 = snap(db, e1)

    # Then 1
    with pytest.raises(ArgumentError) as exc:
        dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=None)

    # Then 2
    assert str(exc.value).startswith("Only '=', '!=', 'is_()', 'is_not()', 'is_distinct_from()', 'is_not_distinct_from()' operators can be used with None/True/False")
    # Then 3
    assert written(db) == before
    # Then 4
    assert snap(db, e1) == before_e1


# [local-coder] LED-DR-09
def test_led_dr_09__an_entry_of_another_workspace_inside_the_window_is_not_returned(db, w1, mk_entry, mk_x9):
    """LED-DR-09 — an entry of another workspace inside the window is not returned.
    Rules: `get_by_date_range` R1"""
    e1 = mk_entry(performed_at=T1)
    mk_x9()

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T5)

    # Then 1
    assert ids(result) == [e1.id]


# [local-coder] LED-DR-10
def test_led_dr_10__a_call_for_the_other_workspace_returns_only_that_workspace_s_entry(db, w2, mk_entry, mk_x9):
    """LED-DR-10 — a call for the other workspace returns only that workspace's entry.
    Rules: `get_by_date_range` R1"""
    mk_entry(performed_at=T1)
    x9 = mk_x9()

    result = dao.get_by_date_range(db, workspace_id=w2.id, start_date=T1, end_date=T5)

    # Then 1
    assert ids(result) == [x9.id]


# [local-coder] LED-DR-11
def test_led_dr_11__an_unknown_workspace_id_returns_an_empty_list(db, mk_entry):
    """LED-DR-11 — an unknown workspace id returns an empty list.
    Rules: `get_by_date_range` R1"""
    mk_entry(performed_at=T1)

    result = dao.get_by_date_range(db, workspace_id=MISSING, start_date=T1, end_date=T3)

    # Then 1
    assert result == []


# [local-coder] LED-DR-12
def test_led_dr_12__inventory_type_filter_narrows_the_entries_of_the_window(db, w1, mk_entry):
    """LED-DR-12 — inventory_type filter narrows the entries of the window.
    Rules: `get_by_date_range` R4"""
    mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T2, inventory_type=DAMAGED)
    mk_entry(performed_at=T3, inventory_type=SCRAP)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T3, inventory_type=DAMAGED)

    # Then 1
    assert ids(result) == [e2.id]


# [local-coder] LED-DR-13
def test_led_dr_13__factory_id_filter_narrows_the_entries_of_the_window(db, w1, f2, mk_entry):
    """LED-DR-13 — factory_id filter narrows the entries of the window.
    Rules: `get_by_date_range` R4"""
    mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T2, factory_id=f2.id)
    mk_entry(performed_at=T3)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T3, factory_id=f2.id)

    # Then 1
    assert ids(result) == [e2.id]


# [local-coder] LED-DR-14
def test_led_dr_14__item_id_filter_narrows_the_entries_of_the_window(db, w1, i2, mk_entry):
    """LED-DR-14 — item_id filter narrows the entries of the window.
    Rules: `get_by_date_range` R4"""
    mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T2, item_id=i2.id)
    mk_entry(performed_at=T3)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T3, item_id=i2.id)

    # Then 1
    assert ids(result) == [e2.id]


# [local-coder] LED-DR-15
def test_led_dr_15__type_factory_and_item_filters_combine_with_the_window_with_and(db, w1, f1, f2, i1, i2, mk_entry):
    """LED-DR-15 — type, factory and item filters combine with the window with AND.
    Rules: `get_by_date_range` R4"""
    e1 = mk_entry(performed_at=T1)
    mk_entry(performed_at=T2, factory_id=f2.id)
    mk_entry(performed_at=T2, inventory_type=DAMAGED)
    mk_entry(performed_at=T3, item_id=i2.id)
    mk_entry(performed_at=T4)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T3, inventory_type=STORAGE, factory_id=f1.id, item_id=i1.id)

    # Then 1
    assert ids(result) == [e1.id]


# [local-coder] LED-DR-16
def test_led_dr_16__explicit_none_for_every_optional_filter_applies_no_filter(db, w1, f2, i2, mk_entry):
    """LED-DR-16 — explicit None for every optional filter applies no filter.
    Rules: `get_by_date_range` R4"""
    e1 = mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T2, inventory_type=DAMAGED, factory_id=f2.id, item_id=i2.id)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T3, inventory_type=None, factory_id=None, item_id=None)

    # Then 1
    assert ids(result) == [e2.id, e1.id]


# [local-coder] LED-DR-17
def test_led_dr_17__a_factory_id_that_does_not_exist_returns_an_empty_list(db, w1, mk_entry):
    """LED-DR-17 — a factory id that does not exist returns an empty list.
    Rules: `get_by_date_range` R4"""
    mk_entry(performed_at=T1)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T3, factory_id=MISSING)

    # Then 1
    assert result == []


# [local-coder] LED-DR-18
def test_led_dr_18__an_item_id_that_does_not_exist_returns_an_empty_list(db, w1, mk_entry):
    """LED-DR-18 — an item id that does not exist returns an empty list.
    Rules: `get_by_date_range` R4"""
    mk_entry(performed_at=T1)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T3, item_id=MISSING)

    # Then 1
    assert result == []


# [local-coder] LED-DR-20
@pytest.mark.xfail(strict=True, reason="BUG-885: Inventory ledger lists treat factory_id=0 / item_id=0 as 'no filter'")
def test_led_dr_20__item_id_0_filters_and_returns_an_empty_list(db, w1, i2, mk_entry):
    """LED-DR-20 — item_id 0 filters and returns an empty list.
    Rules: `get_by_date_range` R4a [BUG-885]"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T2, item_id=i2.id)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T3, item_id=0)

    # Then 1
    assert result == []


# [local-coder] LED-DR-21
@pytest.mark.xfail(strict=True, reason="BUG-640: Ledger lists ordered by performed_at only; ties in no fixed order")
def test_led_dr_21__entries_sharing_a_performed_at_come_back_greatest_id_first(db, w1, mk_entry):
    """LED-DR-21 — entries sharing a performed_at come back greatest id first.
    Rules: `get_by_date_range` R5a [BUG-640]"""
    eb = mk_entry(performed_at=T1)
    ec = mk_entry(performed_at=T1, id=HIGH_ID)
    ea = mk_entry(performed_at=T1)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T3)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [ec.id, ea.id, eb.id]


# [local-coder] LED-DR-22
def test_led_dr_22__entries_sharing_a_performed_at_are_each_returned_once_between_the(db, w1, mk_entry):
    """LED-DR-22 — entries sharing a performed_at are each returned once, between the newer and the older entry.
    Rules: `get_by_date_range` R5"""
    e1 = mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T2)
    e3 = mk_entry(performed_at=T2)
    e4 = mk_entry(performed_at=T3)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T3)

    # Then 1
    assert len(result) == 4
    # Then 2
    assert result[0].id == e4.id
    # Then 3
    assert result[3].id == e1.id
    # Then 4
    assert sorted(ids(result)) == [e1.id, e2.id, e3.id, e4.id]


# [local-coder] LED-DR-23
def test_led_dr_23__skip_1_and_limit_1_return_exactly_the_second_newest_entry(db, w1, mk_entry):
    """LED-DR-23 — skip 1 and limit 1 return exactly the second newest entry.
    Rules: `get_by_date_range` R6"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T3)
    e3 = mk_entry(performed_at=T2)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T3, skip=1, limit=1)

    # Then 1
    assert ids(result) == [e3.id]


# [local-coder] LED-DR-24
def test_led_dr_24__skip_and_limit_are_applied_after_the_window_filter(db, w1, mk_entry):
    """LED-DR-24 — skip and limit are applied after the window filter.
    Rules: `get_by_date_range` R6"""
    mk_entry(performed_at=T4)
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T5)
    mk_entry(performed_at=T3)
    e5 = mk_entry(performed_at=T2)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T3, skip=1, limit=1)

    # Then 1
    assert ids(result) == [e5.id]


# [local-coder] LED-DR-26
def test_led_dr_26__limit_0_returns_an_empty_list(db, w1, mk_entry):
    """LED-DR-26 — limit 0 returns an empty list.
    Rules: `get_by_date_range` R6"""
    mk_entry(performed_at=T1)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T3, limit=0)

    # Then 1
    assert result == []


# [local-coder] LED-DR-27
def test_led_dr_27__skip_equal_to_the_number_of_matching_entries_returns_an_empty_list(db, w1, mk_entry):
    """LED-DR-27 — skip equal to the number of matching entries returns an empty list.
    Rules: `get_by_date_range` R6"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T2)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T3, skip=2)

    # Then 1
    assert result == []


# [local-coder] LED-DR-28
def test_led_dr_28__negative_limit_is_rejected_by_the_database_and_nothing_changes(db, w1, mk_entry):
    """LED-DR-28 — negative limit is rejected by the database and nothing changes.
    Rules: `get_by_date_range` R6, Errors row 2"""
    e1 = mk_entry(performed_at=T1)
    before = written(db)
    before_e1 = snap(db, e1)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T3, limit=-1)

    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInLimitClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201W"
    # Then 4
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 5
    assert written(db) == before
    # Then 6
    assert snap(db, e1) == before_e1


# [local-coder] LED-DR-29
def test_led_dr_29__negative_skip_is_rejected_by_the_database_and_nothing_changes(db, w1, mk_entry):
    """LED-DR-29 — negative skip is rejected by the database and nothing changes.
    Rules: `get_by_date_range` R6, Errors row 2"""
    e1 = mk_entry(performed_at=T1)
    before = written(db)
    before_e1 = snap(db, e1)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T3, skip=-1)

    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201X"
    # Then 4
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 5
    assert written(db) == before
    # Then 6
    assert snap(db, e1) == before_e1


# [local-coder] LED-DR-30
def test_led_dr_30__entries_of_a_soft_deleted_factory_and_of_a_removed_item_are_listed(db, w1, fd, ir, mk_entry):
    """LED-DR-30 — entries of a soft-deleted factory and of a removed item are listed like any other.
    Rules: `get_by_date_range` R7"""
    e1 = mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T2, factory_id=fd.id)
    e3 = mk_entry(performed_at=T3, item_id=ir.id)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T3)

    # Then 1
    assert ids(result) == [e3.id, e2.id, e1.id]


# [local-coder] LED-PF-02
def test_led_pf_02__the_other_user_gets_only_the_entry_that_user_performed(db, w1, u2, mk_entry):
    """LED-PF-02 — the other user gets only the entry that user performed.
    Rules: `get_by_performer` R1"""
    mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T3, performed_by=u2.id)
    mk_entry(performed_at=T2, performed_by=None)

    result = dao.get_by_performer(db, performed_by=u2.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e2.id]


# [local-coder] LED-PF-04
def test_led_pf_04__a_call_for_the_other_workspace_returns_only_the_entry_performed_there(db, w2, u1, mk_entry, mk_x9):
    """LED-PF-04 — a call for the other workspace returns only the entry performed there.
    Rules: `get_by_performer` R2"""
    mk_entry(performed_at=T1)
    x9 = mk_x9()

    result = dao.get_by_performer(db, performed_by=u1.id, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [x9.id]


# [local-coder] LED-PF-05
def test_led_pf_05__a_profile_id_that_does_not_exist_returns_an_empty_list(db, w1, mk_entry):
    """LED-PF-05 — a profile id that does not exist returns an empty list.
    Rules: `get_by_performer` R2"""
    mk_entry(performed_at=T1)

    result = dao.get_by_performer(db, performed_by=MISSING, workspace_id=w1.id)

    # Then 1
    assert result == []


# [local-coder] LED-PF-06
def test_led_pf_06__performed_by_0_returns_an_empty_list_not_the_entries_without_a(db, w1, mk_entry):
    """LED-PF-06 — performed_by 0 returns an empty list, not the entries without a performer.
    Rules: `get_by_performer` R2"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T2, performed_by=None)

    result = dao.get_by_performer(db, performed_by=0, workspace_id=w1.id)

    # Then 1
    assert result == []


# [local-coder] LED-PF-07
def test_led_pf_07__an_unknown_workspace_id_returns_an_empty_list(db, u1, mk_entry):
    """LED-PF-07 — an unknown workspace id returns an empty list.
    Rules: `get_by_performer` R2"""
    mk_entry(performed_at=T1)

    result = dao.get_by_performer(db, performed_by=u1.id, workspace_id=MISSING)

    # Then 1
    assert result == []


# [local-coder] LED-PF-08
def test_led_pf_08__performed_by_none_returns_only_the_entries_without_a_performer(db, w1, u2, mk_entry):
    """LED-PF-08 — performed_by None returns only the entries without a performer.
    Rules: `get_by_performer` R3"""
    mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T2, performed_by=None)
    e3 = mk_entry(performed_at=T3, performed_by=None)
    mk_entry(performed_at=T4, performed_by=u2.id)

    result = dao.get_by_performer(db, performed_by=None, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e3.id, e2.id]


# [local-coder] LED-PF-09
def test_led_pf_09__performed_by_none_stays_inside_the_workspace(db, w1, w2, mk_entry):
    """LED-PF-09 — performed_by None stays inside the workspace.
    Rules: `get_by_performer` R3"""
    e1 = mk_entry(performed_at=T1, performed_by=None)
    mk_entry(performed_at=T2, workspace_id=w2.id, performed_by=None)

    result = dao.get_by_performer(db, performed_by=None, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]


# [local-coder] LED-PF-10
def test_led_pf_10__the_user_s_entries_come_back_newest_first_whatever_the_insertion_order(db, w1, u1, mk_entry):
    """LED-PF-10 — the user's entries come back newest first whatever the insertion order.
    Rules: `get_by_performer` R4"""
    e1 = mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T3)
    e3 = mk_entry(performed_at=T2)

    result = dao.get_by_performer(db, performed_by=u1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e2.id, e3.id, e1.id]


# [local-coder] LED-PF-11
@pytest.mark.xfail(strict=True, reason="BUG-640: Ledger lists ordered by performed_at only; ties in no fixed order")
def test_led_pf_11__entries_sharing_a_performed_at_come_back_greatest_id_first(db, w1, u1, mk_entry):
    """LED-PF-11 — entries sharing a performed_at come back greatest id first.
    Rules: `get_by_performer` R4a [BUG-640]"""
    eb = mk_entry(performed_at=T1)
    ec = mk_entry(performed_at=T1, id=HIGH_ID)
    ea = mk_entry(performed_at=T1)

    result = dao.get_by_performer(db, performed_by=u1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [ec.id, ea.id, eb.id]


# [local-coder] LED-PF-12
def test_led_pf_12__entries_sharing_a_performed_at_are_each_returned_once_between_the(db, w1, u1, mk_entry):
    """LED-PF-12 — entries sharing a performed_at are each returned once, between the newer and the older entry.
    Rules: `get_by_performer` R4"""
    e1 = mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T2)
    e3 = mk_entry(performed_at=T2)
    e4 = mk_entry(performed_at=T3)

    result = dao.get_by_performer(db, performed_by=u1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 4
    # Then 2
    assert result[0].id == e4.id
    # Then 3
    assert result[3].id == e1.id
    # Then 4
    assert sorted(ids(result)) == [e1.id, e2.id, e3.id, e4.id]


# [local-coder] LED-PF-13
def test_led_pf_13__skip_1_and_limit_1_return_exactly_the_second_newest_entry(db, w1, u1, mk_entry):
    """LED-PF-13 — skip 1 and limit 1 return exactly the second newest entry.
    Rules: `get_by_performer` R5"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T3)
    e3 = mk_entry(performed_at=T2)

    result = dao.get_by_performer(db, performed_by=u1.id, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [e3.id]


# [local-coder] LED-PF-14
def test_led_pf_14__skip_and_limit_are_applied_after_the_performer_filter(db, w1, u1, u2, mk_entry):
    """LED-PF-14 — skip and limit are applied after the performer filter.
    Rules: `get_by_performer` R5"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T2, performed_by=u2.id)
    e3 = mk_entry(performed_at=T3)
    mk_entry(performed_at=T4, performed_by=u2.id)
    mk_entry(performed_at=T5)

    result = dao.get_by_performer(db, performed_by=u1.id, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [e3.id]


# [local-coder] LED-PF-16
def test_led_pf_16__limit_0_returns_an_empty_list(db, w1, u1, mk_entry):
    """LED-PF-16 — limit 0 returns an empty list.
    Rules: `get_by_performer` R5"""
    mk_entry(performed_at=T1)

    result = dao.get_by_performer(db, performed_by=u1.id, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [local-coder] LED-PF-17
def test_led_pf_17__skip_equal_to_the_number_of_matching_entries_returns_an_empty_list(db, w1, u1, mk_entry):
    """LED-PF-17 — skip equal to the number of matching entries returns an empty list.
    Rules: `get_by_performer` R5"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T2)

    result = dao.get_by_performer(db, performed_by=u1.id, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [local-coder] LED-PF-18
def test_led_pf_18__negative_limit_is_rejected_by_the_database_and_nothing_changes(db, w1, u1, mk_entry):
    """LED-PF-18 — negative limit is rejected by the database and nothing changes.
    Rules: `get_by_performer` R5, Errors row 1"""
    e1 = mk_entry(performed_at=T1)
    before = written(db)
    before_e1 = snap(db, e1)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_performer(db, performed_by=u1.id, workspace_id=w1.id, limit=-1)

    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInLimitClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201W"
    # Then 4
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 5
    assert written(db) == before
    # Then 6
    assert snap(db, e1) == before_e1


# [local-coder] LED-PF-19
def test_led_pf_19__negative_skip_is_rejected_by_the_database_and_nothing_changes(db, w1, u1, mk_entry):
    """LED-PF-19 — negative skip is rejected by the database and nothing changes.
    Rules: `get_by_performer` R5, Errors row 2"""
    e1 = mk_entry(performed_at=T1)
    before = written(db)
    before_e1 = snap(db, e1)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_performer(db, performed_by=u1.id, workspace_id=w1.id, skip=-1)

    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201X"
    # Then 4
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 5
    assert written(db) == before
    # Then 6
    assert snap(db, e1) == before_e1


# [local-coder] LED-PF-20
def test_led_pf_20__entries_of_a_soft_deleted_factory_and_of_a_removed_item_are_listed(db, w1, u1, fd, ir, mk_entry):
    """LED-PF-20 — entries of a soft-deleted factory and of a removed item are listed like any other.
    Rules: `get_by_performer` R6"""
    e1 = mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T2, factory_id=fd.id)
    e3 = mk_entry(performed_at=T3, item_id=ir.id)

    result = dao.get_by_performer(db, performed_by=u1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e3.id, e2.id, e1.id]


# [local-coder] LED-BAL-01
def test_led_bal_01__a_bucket_with_no_ledger_entry_gives_quantity_0_and_value_0_00(db, f1, i1, w1):
    """LED-BAL-01 — a bucket with no ledger entry gives quantity 0 and value 0.00.
    Rules: `calculate_balance` R1"""

    result = dao.calculate_balance(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, tuple)
    # Then 2
    assert len(result) == 2
    # Then 3
    assert result[0] == 0
    # Then 4
    assert type(result[0]) is int
    # Then 5
    assert isinstance(result[1], Decimal)
    # Then 6
    assert str(result[1]) == "0.00"


# [local-coder] LED-BAL-02
def test_led_bal_02__an_entry_of_another_workspace_does_not_count_for_the_bucket(db, w1, w2, f1, i1, mk_entry):
    """LED-BAL-02 — an entry of another workspace does not count for the bucket.
    Rules: `calculate_balance` R3"""
    mk_entry(performed_at=T1, qty_after=20, avg_price_after=Decimal("6.00"), workspace_id=w2.id)

    result = dao.calculate_balance(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result[0] == 0
    # Then 2
    assert result[1] == Decimal("0.00")


# [local-coder] LED-BAL-03
def test_led_bal_03__an_entry_of_another_factory_does_not_count_for_the_bucket(db, w1, f1, f2, i1, mk_entry):
    """LED-BAL-03 — an entry of another factory does not count for the bucket.
    Rules: `calculate_balance` R3"""
    mk_entry(performed_at=T1, qty_after=20, avg_price_after=Decimal("6.00"), factory_id=f2.id)

    result = dao.calculate_balance(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result[0] == 0
    # Then 2
    assert result[1] == Decimal("0.00")


# [local-coder] LED-BAL-04
def test_led_bal_04__an_entry_of_another_item_does_not_count_for_the_bucket(db, w1, f1, i1, i2, mk_entry):
    """LED-BAL-04 — an entry of another item does not count for the bucket.
    Rules: `calculate_balance` R3"""
    mk_entry(performed_at=T1, qty_after=20, avg_price_after=Decimal("6.00"), item_id=i2.id)

    result = dao.calculate_balance(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result[0] == 0
    # Then 2
    assert result[1] == Decimal("0.00")


# [local-coder] LED-BAL-05
def test_led_bal_05__an_entry_of_another_inventory_type_does_not_count_for_the_bucket(db, w1, f1, i1, mk_entry):
    """LED-BAL-05 — an entry of another inventory type does not count for the bucket.
    Rules: `calculate_balance` R3"""
    mk_entry(performed_at=T1, qty_after=20, avg_price_after=Decimal("6.00"), inventory_type=DAMAGED)

    result = dao.calculate_balance(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result[0] == 0
    # Then 2
    assert result[1] == Decimal("0.00")


# [local-coder] LED-BAL-06
def test_led_bal_06__with_only_other_bucket_entries_the_result_is_empty_and_nothing_changes(db, w1, w2, f1, f2, i1, i2, mk_entry):
    """LED-BAL-06 — with only other-bucket entries the result is empty and nothing changes.
    Rules: `calculate_balance` R3, R6"""
    e1 = mk_entry(performed_at=T1, factory_id=f2.id)
    mk_entry(performed_at=T2, item_id=i2.id)
    mk_entry(performed_at=T3, inventory_type=DAMAGED)
    mk_entry(performed_at=T4, workspace_id=w2.id)
    before = written(db)
    before_e1 = snap(db, e1)

    result = dao.calculate_balance(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result[0] == 0
    # Then 2
    assert result[1] == Decimal("0.00")
    # Then 3
    assert written(db) == before
    # Then 4
    assert snap(db, e1) == before_e1
    # Then 5
    assert count_rows(db, InventoryLedger) == 4


# [local-coder] LED-BAL-07
def test_led_bal_07__a_bucket_without_entries_in_a_soft_deleted_factory_gives_quantity_0(db, w1, fd, i1, mk_entry):
    """LED-BAL-07 — a bucket without entries in a soft-deleted factory gives quantity 0 and value 0.00.
    Rules: `calculate_balance` R1, R5"""
    mk_entry(performed_at=T1)

    result = dao.calculate_balance(db, factory_id=fd.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result[0] == 0
    # Then 2
    assert result[1] == Decimal("0.00")


# [local-coder] LED-BAL-08
@pytest.mark.xfail(strict=True, reason="BUG-655: Inventory balance and inventory reconcile crash whenever the bucket has history")
def test_led_bal_08__a_single_entry_gives_its_quantity_and_quantity_times_average_price(db, w1, f1, i1, mk_entry):
    """LED-BAL-08 — a single entry gives its quantity and quantity times average price.
    Rules: `calculate_balance` R2 [BUG-655]"""
    mk_entry(performed_at=T1, qty_after=20, avg_price_after=Decimal("6.00"))

    result = dao.calculate_balance(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result[0] == 20
    # Then 2
    assert result[1] == Decimal("120.00")
    # Then 3
    assert isinstance(result, tuple)
    # Then 4
    assert type(result[0]) is int
    # Then 5
    assert isinstance(result[1], Decimal)


# [local-coder] LED-BAL-09
@pytest.mark.xfail(strict=True, reason="BUG-655: Inventory balance and inventory reconcile crash whenever the bucket has history")
def test_led_bal_09__an_entry_with_no_average_price_gives_its_quantity_and_value_0_00(db, w1, f1, i1, mk_entry):
    """LED-BAL-09 — an entry with no average price gives its quantity and value 0.00.
    Rules: `calculate_balance` R2 [BUG-655]"""
    mk_entry(performed_at=T1, qty_after=5, avg_price_after=None)

    result = dao.calculate_balance(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result[0] == 5
    # Then 2
    assert result[1] == Decimal("0.00")
    # Then 3
    assert isinstance(result[1], Decimal)


# [local-coder] LED-BAL-10
@pytest.mark.xfail(strict=True, reason="BUG-655: Inventory balance and inventory reconcile crash whenever the bucket has history")
def test_led_bal_10__an_entry_with_quantity_0_gives_quantity_0_and_value_0(db, w1, f1, i1, mk_entry):
    """LED-BAL-10 — an entry with quantity 0 gives quantity 0 and value 0.
    Rules: `calculate_balance` R2 [BUG-655]"""
    mk_entry(performed_at=T1, qty_after=0, avg_price_after=Decimal("6.00"))

    result = dao.calculate_balance(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result[0] == 0
    # Then 2
    assert result[1] == Decimal("0")


# [local-coder] LED-BAL-14
@pytest.mark.xfail(strict=True, reason="BUG-655: Inventory balance and inventory reconcile crash whenever the bucket has history")
def test_led_bal_14__the_balance_of_a_bucket_in_a_soft_deleted_factory_is_returned(db, w1, fd, i1, mk_entry):
    """LED-BAL-14 — the balance of a bucket in a soft-deleted factory is returned.
    Rules: `calculate_balance` R5 [BUG-655]"""
    mk_entry(performed_at=T1, factory_id=fd.id, qty_after=20, avg_price_after=Decimal("6.00"))

    result = dao.calculate_balance(db, factory_id=fd.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result[0] == 20
    # Then 2
    assert result[1] == Decimal("120.00")


# [local-coder] LED-BAL-15
@pytest.mark.xfail(strict=True, reason="BUG-655: Inventory balance and inventory reconcile crash whenever the bucket has history")
def test_led_bal_15__the_balance_of_a_bucket_of_a_removed_catalog_item_is_returned(db, w1, f1, ir, mk_entry):
    """LED-BAL-15 — the balance of a bucket of a removed catalog item is returned.
    Rules: `calculate_balance` R5 [BUG-655]"""
    mk_entry(performed_at=T1, item_id=ir.id, qty_after=20, avg_price_after=Decimal("6.00"))

    result = dao.calculate_balance(db, factory_id=f1.id, item_id=ir.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result[0] == 20
    # Then 2
    assert result[1] == Decimal("120.00")


# [local-coder] LED-BAL-16
@pytest.mark.xfail(strict=True, reason="BUG-655: Inventory balance and inventory reconcile crash whenever the bucket has history")
def test_led_bal_16__reading_the_balance_of_a_bucket_with_history_changes_nothing(db, w1, f1, i1, mk_entry):
    """LED-BAL-16 — reading the balance of a bucket with history changes nothing.
    Rules: `calculate_balance` R6, R2 [BUG-655]"""
    e1 = mk_entry(performed_at=T1, qty_after=20, avg_price_after=Decimal("6.00"))
    before = written(db)
    before_e1 = snap(db, e1)

    result = dao.calculate_balance(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result[0] == 20
    # Then 2
    assert written(db) == before
    # Then 3
    assert snap(db, e1) == before_e1
    # Then 4
    row = reread(db, e1)
    assert row.qty_after == 20
    # Then 5
    assert count_rows(db, InventoryLedger) == 1


# [local-coder] LED-LE-01
def test_led_le_01__a_bucket_with_no_ledger_entry_returns_none(db, w1, f1, i1):
    """LED-LE-01 — a bucket with no ledger entry returns None.
    Rules: `get_latest_entry` R1"""

    result = dao.get_latest_entry(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result is None


# [local-coder] LED-LE-02
def test_led_le_02__returns_the_entry_with_the_greatest_performed_at_when_it_was_inserted(db, w1, f1, i1, mk_entry):
    """LED-LE-02 — returns the entry with the greatest performed_at when it was inserted second.
    Rules: `get_latest_entry` R2"""
    mk_entry(performed_at=T1, qty_after=30)
    e2 = mk_entry(performed_at=T3, qty_after=20)
    mk_entry(performed_at=T2, qty_after=10)

    result = dao.get_latest_entry(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, InventoryLedger)
    # Then 2
    assert result.id == e2.id
    # Then 3
    assert result.qty_after == 20


# [local-coder] LED-LE-03
def test_led_le_03__a_single_entry_is_returned_as_it_is(db, w1, f1, i1, mk_entry):
    """LED-LE-03 — a single entry is returned as it is.
    Rules: `get_latest_entry` R2"""
    e1 = mk_entry(performed_at=T1, qty_after=30)

    result = dao.get_latest_entry(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result.id == e1.id
    # Then 2
    assert result.qty_after == 30


# [local-coder] LED-LE-04
def test_led_le_04__the_newest_entry_is_returned_when_it_has_the_lowest_id(db, w1, f1, i1, mk_entry):
    """LED-LE-04 — the newest entry is returned when it has the lowest id.
    Rules: `get_latest_entry` R2"""
    e1 = mk_entry(performed_at=T3, qty_after=20)
    mk_entry(performed_at=T1, qty_after=30)
    mk_entry(performed_at=T2, qty_after=10)

    result = dao.get_latest_entry(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result.id == e1.id
    # Then 2
    assert result.qty_after == 20


# [local-coder] LED-LE-05
def test_led_le_05__the_newest_entry_is_returned_when_it_has_the_highest_id(db, w1, f1, i1, mk_entry):
    """LED-LE-05 — the newest entry is returned when it has the highest id.
    Rules: `get_latest_entry` R2"""
    mk_entry(performed_at=T1, qty_after=30)
    mk_entry(performed_at=T2, qty_after=10)
    e3 = mk_entry(performed_at=T3, qty_after=20)

    result = dao.get_latest_entry(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result.id == e3.id
    # Then 2
    assert result.qty_after == 20


# [local-coder] LED-LE-07
def test_led_le_07__an_older_entry_never_wins_even_with_a_much_greater_id(db, w1, f1, i1, mk_entry):
    """LED-LE-07 — an older entry never wins, even with a much greater id.
    Rules: `get_latest_entry` R3, R2"""
    e1 = mk_entry(performed_at=T2, qty_after=20)
    mk_entry(performed_at=T1, id=HIGH_ID, qty_after=30)

    result = dao.get_latest_entry(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result.id == e1.id
    # Then 2
    assert result.qty_after == 20


# [local-coder] LED-LE-08
def test_led_le_08__with_a_tie_for_newest_one_of_the_tied_entries_is_returned_and_never(db, w1, f1, i1, mk_entry):
    """LED-LE-08 — with a tie for newest, one of the tied entries is returned and never the older one.
    Rules: `get_latest_entry` R3, R2"""
    mk_entry(performed_at=T1, qty_after=30)
    e2 = mk_entry(performed_at=T2, qty_after=15)
    e3 = mk_entry(performed_at=T2, qty_after=10)

    result = dao.get_latest_entry(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result.id in [e2.id, e3.id]
    # Then 2
    assert result.performed_at == T2


# [local-coder] LED-LE-09
def test_led_le_09__a_newer_entry_of_another_workspace_is_not_returned(db, w1, w2, f1, i1, mk_entry):
    """LED-LE-09 — a newer entry of another workspace is not returned.
    Rules: `get_latest_entry` R4"""
    e1 = mk_entry(performed_at=T1, qty_after=20)
    mk_entry(performed_at=T2, qty_after=91, workspace_id=w2.id)

    result = dao.get_latest_entry(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result.id == e1.id
    # Then 2
    assert result.qty_after == 20


# [local-coder] LED-LE-10
def test_led_le_10__a_newer_entry_of_another_factory_is_not_returned(db, w1, f1, f2, i1, mk_entry):
    """LED-LE-10 — a newer entry of another factory is not returned.
    Rules: `get_latest_entry` R4"""
    e1 = mk_entry(performed_at=T1, qty_after=20)
    mk_entry(performed_at=T2, qty_after=91, factory_id=f2.id)

    result = dao.get_latest_entry(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result.id == e1.id
    # Then 2
    assert result.qty_after == 20


# [local-coder] LED-LE-11
def test_led_le_11__a_newer_entry_of_another_item_is_not_returned(db, w1, f1, i1, i2, mk_entry):
    """LED-LE-11 — a newer entry of another item is not returned.
    Rules: `get_latest_entry` R4"""
    e1 = mk_entry(performed_at=T1, qty_after=20)
    mk_entry(performed_at=T2, qty_after=91, item_id=i2.id)

    result = dao.get_latest_entry(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result.id == e1.id
    # Then 2
    assert result.qty_after == 20


# [local-coder] LED-LE-12
def test_led_le_12__a_newer_entry_of_another_inventory_type_is_not_returned(db, w1, f1, i1, mk_entry):
    """LED-LE-12 — a newer entry of another inventory type is not returned.
    Rules: `get_latest_entry` R4"""
    e1 = mk_entry(performed_at=T1, qty_after=20)
    mk_entry(performed_at=T2, qty_after=91, inventory_type=DAMAGED)

    result = dao.get_latest_entry(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result.id == e1.id
    # Then 2
    assert result.qty_after == 20


# [local-coder] LED-LE-13
def test_led_le_13__when_only_entries_of_other_buckets_exist_the_result_is_none(db, w1, w2, f1, f2, i1, i2, mk_entry):
    """LED-LE-13 — when only entries of other buckets exist the result is None.
    Rules: `get_latest_entry` R4, R1"""
    mk_entry(performed_at=T1, factory_id=f2.id)
    mk_entry(performed_at=T2, item_id=i2.id)
    mk_entry(performed_at=T3, inventory_type=DAMAGED)
    mk_entry(performed_at=T4, workspace_id=w2.id)

    result = dao.get_latest_entry(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result is None


# [local-coder] LED-LE-14
def test_led_le_14__the_returned_row_carries_id_quantity_and_average_price_as_stored(db, w1, f1, i1, mk_entry):
    """LED-LE-14 — the returned row carries id, quantity and average price as stored.
    Rules: `get_latest_entry` R5"""
    e1 = mk_entry(performed_at=T1, qty_after=20, avg_price_after=Decimal("6.00"))

    result = dao.get_latest_entry(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result.id == e1.id
    # Then 2
    assert result.qty_after == 20
    # Then 3
    assert type(result.qty_after) is int
    # Then 4
    assert result.avg_price_after == Decimal("6.00")
    # Then 5
    assert isinstance(result.avg_price_after, Decimal)


# [local-coder] LED-LE-15
def test_led_le_15__a_null_average_price_is_readable_as_none(db, w1, f1, i1, mk_entry):
    """LED-LE-15 — a NULL average price is readable as None.
    Rules: `get_latest_entry` R5"""
    e1 = mk_entry(performed_at=T1, qty_after=5, avg_price_after=None)

    result = dao.get_latest_entry(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result.id == e1.id
    # Then 2
    assert result.qty_after == 5
    # Then 3
    assert result.avg_price_after is None


# [local-coder] LED-LE-16
def test_led_le_16__the_latest_entry_of_a_bucket_in_a_soft_deleted_factory_is_returned(db, w1, fd, i1, mk_entry):
    """LED-LE-16 — the latest entry of a bucket in a soft-deleted factory is returned.
    Rules: `get_latest_entry` R6"""
    e1 = mk_entry(performed_at=T1, factory_id=fd.id, qty_after=30)
    mk_entry(performed_at=T2, qty_after=20)

    result = dao.get_latest_entry(db, factory_id=fd.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result.id == e1.id
    # Then 2
    assert result.qty_after == 30


# [local-coder] LED-LE-17
def test_led_le_17__the_latest_entry_of_a_bucket_of_a_removed_catalog_item_is_returned(db, w1, f1, ir, mk_entry):
    """LED-LE-17 — the latest entry of a bucket of a removed catalog item is returned.
    Rules: `get_latest_entry` R6"""
    e1 = mk_entry(performed_at=T1, item_id=ir.id, qty_after=30)
    mk_entry(performed_at=T2, qty_after=20)

    result = dao.get_latest_entry(db, factory_id=f1.id, item_id=ir.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result.id == e1.id
    # Then 2
    assert result.qty_after == 30


# [local-coder] LED-EX-01
def test_led_ex_01__one_entry_with_that_source_type_and_id_gives_true(db, w1, mk_entry):
    """LED-EX-01 — one entry with that source type and id gives True.
    Rules: `exists_for_source` R1"""
    mk_entry(performed_at=T1, source_type="po", source_id=5)

    result = dao.exists_for_source(db, workspace_id=w1.id, source_type="po", source_id=5)

    # Then 1
    assert result is True
    # Then 2
    assert type(result) is bool


# [local-coder] LED-EX-02
def test_led_ex_02__several_entries_with_that_source_still_give_true(db, w1, mk_entry):
    """LED-EX-02 — several entries with that source still give True.
    Rules: `exists_for_source` R1"""
    mk_entry(performed_at=T1, source_type="po", source_id=5)
    mk_entry(performed_at=T2, source_type="po", source_id=5)
    mk_entry(performed_at=T3, source_type="po", source_id=5)

    result = dao.exists_for_source(db, workspace_id=w1.id, source_type="po", source_id=5)

    # Then 1
    assert result is True


# [local-coder] LED-EX-03
def test_led_ex_03__the_match_does_not_depend_on_type_factory_item_transaction_type(db, w1, f2, i2, mk_entry):
    """LED-EX-03 — the match does not depend on type, factory, item, transaction type, quantity or performer.
    Rules: `exists_for_source` R1"""
    mk_entry(performed_at=T1, inventory_type=DAMAGED, factory_id=f2.id, item_id=i2.id, transaction_type="sale", quantity=7, performed_by=None, source_type="po", source_id=5)

    result = dao.exists_for_source(db, workspace_id=w1.id, source_type="po", source_id=5)

    # Then 1
    assert result is True


# [local-coder] LED-EX-04
def test_led_ex_04__an_empty_ledger_gives_false(db, w1):
    """LED-EX-04 — an empty ledger gives False.
    Rules: `exists_for_source` R2"""

    result = dao.exists_for_source(db, workspace_id=w1.id, source_type="po", source_id=5)

    # Then 1
    assert result is False
    # Then 2
    assert type(result) is bool


# [local-coder] LED-EX-05
def test_led_ex_05__the_same_source_in_another_workspace_gives_false(db, w1, w2, mk_entry):
    """LED-EX-05 — the same source in another workspace gives False.
    Rules: `exists_for_source` R2"""
    mk_entry(performed_at=T1, workspace_id=w2.id, source_type="po", source_id=5)

    result = dao.exists_for_source(db, workspace_id=w1.id, source_type="po", source_id=5)

    # Then 1
    assert result is False


# [local-coder] LED-EX-06
def test_led_ex_06__the_same_source_id_with_another_source_type_gives_false(db, w1, mk_entry):
    """LED-EX-06 — the same source id with another source type gives False.
    Rules: `exists_for_source` R2"""
    mk_entry(performed_at=T1, source_type="to", source_id=5)

    result = dao.exists_for_source(db, workspace_id=w1.id, source_type="po", source_id=5)

    # Then 1
    assert result is False


# [local-coder] LED-EX-07
def test_led_ex_07__the_same_source_type_with_another_source_id_gives_false(db, w1, mk_entry):
    """LED-EX-07 — the same source type with another source id gives False.
    Rules: `exists_for_source` R2"""
    mk_entry(performed_at=T1, source_type="po", source_id=6)

    result = dao.exists_for_source(db, workspace_id=w1.id, source_type="po", source_id=5)

    # Then 1
    assert result is False


# [local-coder] LED-EX-08
def test_led_ex_08__an_entry_with_no_source_gives_false_for_a_named_source(db, w1, mk_entry):
    """LED-EX-08 — an entry with no source gives False for a named source.
    Rules: `exists_for_source` R2"""
    mk_entry(performed_at=T1)

    result = dao.exists_for_source(db, workspace_id=w1.id, source_type="po", source_id=5)

    # Then 1
    assert result is False


# [local-coder] LED-EX-09
def test_led_ex_09__the_source_type_is_compared_case_sensitively(db, w1, mk_entry):
    """LED-EX-09 — the source type is compared case-sensitively.
    Rules: `exists_for_source` R3"""
    mk_entry(performed_at=T1, source_type="po", source_id=5)

    result = dao.exists_for_source(db, workspace_id=w1.id, source_type="PO", source_id=5)

    # Then 1
    assert result is False


# [local-coder] LED-EX-11
def test_led_ex_11__source_id_none_does_not_match_an_entry_that_has_a_source_id(db, w1, mk_entry):
    """LED-EX-11 — source_id None does not match an entry that has a source id.
    Rules: `exists_for_source` R4"""
    mk_entry(performed_at=T1, source_type="po", source_id=5)

    result = dao.exists_for_source(db, workspace_id=w1.id, source_type="po", source_id=None)

    # Then 1
    assert result is False


# [local-coder] LED-EX-12
def test_led_ex_12__source_type_none_and_source_id_none_match_an_entry_that_has_neither(db, w1, mk_entry):
    """LED-EX-12 — source type None and source id None match an entry that has neither.
    Rules: `exists_for_source` R4"""
    mk_entry(performed_at=T1, source_type="po", source_id=5)
    mk_entry(performed_at=T2)

    result = dao.exists_for_source(db, workspace_id=w1.id, source_type=None, source_id=None)

    # Then 1
    assert result is True


# [local-coder] LED-EX-13
def test_led_ex_13__source_type_none_and_source_id_none_do_not_match_an_entry_that_has_a(db, w1, mk_entry):
    """LED-EX-13 — source type None and source id None do not match an entry that has a source.
    Rules: `exists_for_source` R4"""
    mk_entry(performed_at=T1, source_type="po", source_id=5)

    result = dao.exists_for_source(db, workspace_id=w1.id, source_type=None, source_id=None)

    # Then 1
    assert result is False


# [local-coder] LED-EX-14
def test_led_ex_14__an_entry_booked_in_a_soft_deleted_factory_counts(db, w1, fd, mk_entry):
    """LED-EX-14 — an entry booked in a soft-deleted factory counts.
    Rules: `exists_for_source` R5"""
    mk_entry(performed_at=T1, factory_id=fd.id, source_type="po", source_id=5)

    result = dao.exists_for_source(db, workspace_id=w1.id, source_type="po", source_id=5)

    # Then 1
    assert result is True


# [local-coder] LED-EX-15
def test_led_ex_15__an_entry_of_a_removed_catalog_item_counts(db, w1, ir, mk_entry):
    """LED-EX-15 — an entry of a removed catalog item counts.
    Rules: `exists_for_source` R5"""
    mk_entry(performed_at=T1, item_id=ir.id, source_type="po", source_id=5)

    result = dao.exists_for_source(db, workspace_id=w1.id, source_type="po", source_id=5)

    # Then 1
    assert result is True


# [local-coder] LED-EX-16
def test_led_ex_16__the_check_changes_nothing_in_the_database(db, w1, mk_entry):
    """LED-EX-16 — the check changes nothing in the database.
    Rules: `exists_for_source` R6"""
    e1 = mk_entry(performed_at=T1, source_type="po", source_id=5)
    before = written(db)
    before_e1 = snap(db, e1)

    result = dao.exists_for_source(db, workspace_id=w1.id, source_type="po", source_id=5)

    # Then 1
    assert result is True
    # Then 2
    assert written(db) == before
    # Then 3
    assert snap(db, e1) == before_e1
    # Then 4
    row = reread(db, e1)
    assert row.source_type == "po"
    assert row.source_id == 5
    # Then 5
    assert count_rows(db, InventoryLedger) == 1
