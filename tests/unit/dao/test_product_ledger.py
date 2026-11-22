"""Unit tests for app/dao/product_ledger.py.

Implements tests/unit/dao/product_ledger.cases.md, one test per case, in card order. Real
Postgres session (`db` fixture).
Nothing is mocked and no clock is patched (Conventions, Externals).

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117, DTZ001  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested():`, and naive datetimes)
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from psycopg2.errors import NotNullViolation
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import DataError, IntegrityError

from app.dao.product_ledger import product_ledger_dao
from app.models.factory import Factory
from app.models.item import Item
from app.models.product import Product
from app.models.product_ledger import ProductLedger
from app.schemas.product_ledger import ProductLedgerCreate, ProductLedgerUpdate
from app.utils.time import utcnow
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton product_ledger_dao" (a module-level name, not a fixture)
dao = product_ledger_dao

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999

# Convention "T0": a past stamp
T0 = datetime(2026, 1, 15, 9, 0, 0)

# Conventions: fixed values
T9 = datetime(2026, 3, 1, 9, 0, 0)
T10 = datetime(2026, 3, 1, 10, 0, 0)
T11 = datetime(2026, 3, 1, 11, 0, 0)
T12 = datetime(2026, 3, 1, 12, 0, 0)


# Convention "Z(h, m)": an aware bound
def Z(h, m):
    return datetime(2026, 3, 1, h, m, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- #
# Conventions -> the rows that exist in every test
# --------------------------------------------------------------------------- #

def _add(db, row):
    db.add(row)
    db.flush()
    return row


# Given lines "built with add_all"
def add_many(db, rows):
    db.add_all(rows)
    db.flush()


# Conventions list these rows in this order; each fixture depends on the one before,
# so they are flushed one at a time in that order and the ids rise in that order.
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


@pytest.fixture
def u1(db, w2):
    return make_profile(db)


@pytest.fixture
def u2(db, u1):
    return make_profile(db)


@pytest.fixture
def f1(db, w1, u2):
    return _add(db, Factory(workspace_id=w1.id, name="Factory One", abbreviation="F1"))


@pytest.fixture
def f2(db, w1, f1):
    return _add(db, Factory(workspace_id=w1.id, name="Factory Two", abbreviation="F2"))


@pytest.fixture
def fd(db, w1, u1, f2):
    return _add(db, Factory(workspace_id=w1.id, name="Old Plant", abbreviation="OP", is_deleted=True, deleted_at=T9, deleted_by=u1.id))


@pytest.fixture
def f9(db, w2, fd):
    return _add(db, Factory(workspace_id=w2.id, name="Far Plant", abbreviation="F9"))


@pytest.fixture
def i1(db, w1, f9):
    return _add(db, Item(workspace_id=w1.id, name="Bolt", name_normalized="bolt", unit="pcs"))


@pytest.fixture
def i2(db, w1, i1):
    return _add(db, Item(workspace_id=w1.id, name="Cam", name_normalized="cam", unit="pcs"))


@pytest.fixture
def ix(db, w1, i2):
    return _add(db, Item(workspace_id=w1.id, name="Old Gasket", name_normalized="old gasket", unit="pcs", is_active=False))


@pytest.fixture
def i9(db, w2, ix):
    return _add(db, Item(workspace_id=w2.id, name="Far Crate", name_normalized="far crate", unit="pcs"))


# Convention "they exist in every test and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2, u1, u2, f1, f2, fd, f9, i1, i2, ix, i9):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builders (fixtures; each mk_ flushes before it returns)
# --------------------------------------------------------------------------- #

# Convention "entry"
@pytest.fixture
def new_entry(w1, f1, i1):
    """new_entry(performed_at=..., **columns) -> ProductLedger, not added."""
    def _new(*, performed_at, **columns):
        return ProductLedger(**{"workspace_id": w1.id, "factory_id": f1.id, "item_id": i1.id, "transaction_type": "sale", "quantity": 1, "qty_before": 5, "qty_after": 4, "performed_at": performed_at, **columns})
    return _new


@pytest.fixture
def mk_entry(db, new_entry):
    """mk_entry(...) = new_entry(...), added and flushed."""
    def _mk(**columns):
        return _add(db, new_entry(**columns))
    return _mk

# Convention "posted"
@pytest.fixture
def mk_posted(mk_entry):
    """mk_posted(source_id=..., **columns) -> ProductLedger: an entry with performed_at T10, source_type "production_batch"."""
    def _mk(*, source_id, **columns):
        return mk_entry(**{"performed_at": T10, "source_type": "production_batch", "source_id": source_id, **columns})
    return _mk


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (no expected values inside)
# --------------------------------------------------------------------------- #

# Convention "ids(result)": in the order returned
def ids(result):
    return [row.id for row in result]


# Convention "unchanged(X)": every column of X, straight from the table
def snap(db, row):
    """Dict column -> database value of `row`, or None if it is gone."""
    table = type(row).__table__
    found = db.execute(select(table).where(table.c.id == sa_inspect(row).identity[0])).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "unchanged(X) except c, ...": the same, leaving out the columns named
def without(snapshot, *columns):
    return {k: v for k, v in snapshot.items() if k not in columns}


# Convention "re-read X": expire, then SELECT by id
def reread(db, row):
    db.expire_all()
    return db.get(type(row), sa_inspect(row).identity[0])


# Convention "nothing written": the number of `product_ledger` rows stored (all workspaces)
def stored_count(db):
    return db.scalar(select(func.count()).select_from(ProductLedger.__table__))


# Convention "count:": rows in all workspaces, with the filter stated
def count_rows(db, model, *where):
    return db.scalar(select(func.count()).select_from(model.__table__).where(*where))


# Convention "seq scan": three steps at that place in the Given
def seqscan(db):
    db.execute(text("SET LOCAL enable_indexscan = off"))
    db.execute(text("SET LOCAL enable_bitmapscan = off"))
    db.execute(text("SET LOCAL enable_indexonlyscan = off"))


# Convention "order_part": the text of `sql` after its first ORDER BY and before any LIMIT ("" when there is no ORDER BY)
def order_part_of(sql):
    return sql.split("ORDER BY", 1)[1].split("LIMIT", 1)[0] if "ORDER BY" in sql else ""


# Convention "Statement recorder": the SQL text of every statement the session's
# connection sends from recorder.start() (the start of the When) to the end of the test.
class StatementRecorder:
    def __init__(self, db):
        self.bind = db.get_bind()
        self.statements = []
        self.started = False

    def _record(self, conn, cursor, statement, parameters, context, executemany):
        self.statements.append(statement)

    def start(self):
        event.listen(self.bind, "before_cursor_execute", self._record)
        self.started = True

    def stop(self):
        if self.started:
            event.remove(self.bind, "before_cursor_execute", self._record)
            self.started = False

    def selects(self):
        return [s for s in self.statements if s.lstrip().upper().startswith("SELECT")]

    def written(self):
        return [s for s in self.statements if s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]

    def sql(self):
        """The one SELECT from `product_ledger`; fails loudly unless there is exactly one."""
        [statement] = [s for s in self.selects() if "FROM product_ledger" in s]
        return statement


@pytest.fixture
def recorder(db):
    statement_recorder = StatementRecorder(db)
    yield statement_recorder
    statement_recorder.stop()


# --------------------------------------------------------------------------- #
# ProductLedgerDAO.get_by_workspace
# --------------------------------------------------------------------------- #


# [claude] PLG-GW-01
def test_plg_gw_01__with_no_filters_a_list_of_the_workspace_s_rows_newest_first(db, w1, mk_entry):
    """PLG-GW-01 — with no filters: a list of the workspace's rows, newest first.
    Rules: `get_by_workspace` R1, Returns"""
    a = mk_entry(performed_at=T11)
    b = mk_entry(performed_at=T12)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [b.id, a.id]
    # Then 3
    assert isinstance(result[0], ProductLedger)


# [claude] PLG-GW-02
def test_plg_gw_02__a_newer_row_of_another_workspace_is_not_returned(db, w1, w2, f9, i9, mk_entry):
    """PLG-GW-02 — a newer row of another workspace is not returned.
    Rules: `get_by_workspace` R1"""
    a = mk_entry(performed_at=T11)
    mk_entry(performed_at=T12, workspace_id=w2.id, factory_id=f9.id, item_id=i9.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] PLG-GW-03
def test_plg_gw_03__an_earlier_id_row_of_another_workspace_is_not_returned(db, w1, w2, f9, i9, mk_entry):
    """PLG-GW-03 — an earlier-id row of another workspace is not returned.
    Rules: `get_by_workspace` R1"""
    mk_entry(performed_at=T12, workspace_id=w2.id, factory_id=f9.id, item_id=i9.id)
    a = mk_entry(performed_at=T11)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] PLG-GW-04
def test_plg_gw_04__an_unknown_workspace_returns_an_empty_list(db, mk_entry):
    """PLG-GW-04 — an unknown workspace returns an empty list.
    Rules: `get_by_workspace` R1"""
    mk_entry(performed_at=T12)

    result = dao.get_by_workspace(db, workspace_id=MISSING)

    # Then 1
    assert result == []


# [claude] PLG-GW-05
def test_plg_gw_05__factory_id_narrows_to_that_factory(db, w1, f1, f2, mk_entry):
    """PLG-GW-05 — factory_id narrows to that factory.
    Rules: `get_by_workspace` R2"""
    mk_entry(performed_at=T12, factory_id=f2.id)
    a = mk_entry(performed_at=T11)

    result = dao.get_by_workspace(db, workspace_id=w1.id, factory_id=f1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] PLG-GW-06
def test_plg_gw_06__factory_id_0_returns_an_empty_list_0_is_a_filter(db, w1, mk_entry):
    """PLG-GW-06 — factory_id=0 returns an empty list: 0 is a filter.
    Rules: `get_by_workspace` R2"""
    mk_entry(performed_at=T12)

    result = dao.get_by_workspace(db, workspace_id=w1.id, factory_id=0)

    # Then 1
    assert result == []


# [claude] PLG-GW-07
def test_plg_gw_07__factory_id_none_applies_no_filter(db, w1, f2, mk_entry):
    """PLG-GW-07 — factory_id=None applies no filter.
    Rules: `get_by_workspace` R2"""
    a = mk_entry(performed_at=T12)
    b = mk_entry(performed_at=T11, factory_id=f2.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, factory_id=None)

    # Then 1
    assert ids(result) == [a.id, b.id]


# [claude] PLG-GW-08
def test_plg_gw_08__item_id_narrows_to_that_item(db, w1, i1, i2, mk_entry):
    """PLG-GW-08 — item_id narrows to that item.
    Rules: `get_by_workspace` R3"""
    mk_entry(performed_at=T12, item_id=i2.id)
    a = mk_entry(performed_at=T11)

    result = dao.get_by_workspace(db, workspace_id=w1.id, item_id=i1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] PLG-GW-09
def test_plg_gw_09__item_id_0_returns_an_empty_list_0_is_a_filter(db, w1, mk_entry):
    """PLG-GW-09 — item_id=0 returns an empty list: 0 is a filter.
    Rules: `get_by_workspace` R3"""
    mk_entry(performed_at=T12)

    result = dao.get_by_workspace(db, workspace_id=w1.id, item_id=0)

    # Then 1
    assert result == []


# [claude] PLG-GW-10
def test_plg_gw_10__item_id_none_applies_no_filter(db, w1, i2, mk_entry):
    """PLG-GW-10 — item_id=None applies no filter.
    Rules: `get_by_workspace` R3"""
    a = mk_entry(performed_at=T12)
    b = mk_entry(performed_at=T11, item_id=i2.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, item_id=None)

    # Then 1
    assert ids(result) == [a.id, b.id]


# [claude] PLG-GW-11
def test_plg_gw_11__a_row_at_exactly_start_date_is_returned(db, w1, mk_entry):
    """PLG-GW-11 — a row at exactly start_date is returned.
    Rules: `get_by_workspace` R4"""
    mk_entry(performed_at=T10)
    b = mk_entry(performed_at=T11)
    c = mk_entry(performed_at=T12)

    result = dao.get_by_workspace(db, workspace_id=w1.id, start_date=T11)

    # Then 1
    assert ids(result) == [c.id, b.id]


# [claude] PLG-GW-12
def test_plg_gw_12__a_row_one_second_before_start_date_is_not_returned(db, w1, mk_entry):
    """PLG-GW-12 — a row one second before start_date is not returned.
    Rules: `get_by_workspace` R4"""
    mk_entry(performed_at=T10)
    mk_entry(performed_at=T11)
    c = mk_entry(performed_at=T12)

    result = dao.get_by_workspace(db, workspace_id=w1.id, start_date=T11 + timedelta(seconds=1))

    # Then 1
    assert ids(result) == [c.id]


# [claude] PLG-GW-13
def test_plg_gw_13__a_row_at_exactly_end_date_is_returned(db, w1, mk_entry):
    """PLG-GW-13 — a row at exactly end_date is returned.
    Rules: `get_by_workspace` R4"""
    a = mk_entry(performed_at=T10)
    b = mk_entry(performed_at=T11)
    mk_entry(performed_at=T12)

    result = dao.get_by_workspace(db, workspace_id=w1.id, end_date=T11)

    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] PLG-GW-14
def test_plg_gw_14__a_row_one_second_after_end_date_is_not_returned(db, w1, mk_entry):
    """PLG-GW-14 — a row one second after end_date is not returned.
    Rules: `get_by_workspace` R4"""
    a = mk_entry(performed_at=T10)
    mk_entry(performed_at=T11)
    mk_entry(performed_at=T12)

    result = dao.get_by_workspace(db, workspace_id=w1.id, end_date=T11 - timedelta(seconds=1))

    # Then 1
    assert ids(result) == [a.id]


# [claude] PLG-GW-15
def test_plg_gw_15__both_bounds_keep_the_range_inclusive(db, w1, mk_entry):
    """PLG-GW-15 — both bounds keep the range, inclusive.
    Rules: `get_by_workspace` R4"""
    a = mk_entry(performed_at=T10)
    b = mk_entry(performed_at=T11)
    mk_entry(performed_at=T12)

    result = dao.get_by_workspace(db, workspace_id=w1.id, start_date=T10, end_date=T11)

    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] PLG-GW-16
def test_plg_gw_16__equal_bounds_keep_the_row_at_that_instant(db, w1, mk_entry):
    """PLG-GW-16 — equal bounds keep the row at that instant.
    Rules: `get_by_workspace` R4"""
    mk_entry(performed_at=T10)
    b = mk_entry(performed_at=T11)
    mk_entry(performed_at=T12)

    result = dao.get_by_workspace(db, workspace_id=w1.id, start_date=T11, end_date=T11)

    # Then 1
    assert ids(result) == [b.id]


# [claude] PLG-GW-17
def test_plg_gw_17__an_inverted_range_returns_an_empty_list_with_no_error(db, w1, mk_entry):
    """PLG-GW-17 — an inverted range returns an empty list, with no error.
    Rules: `get_by_workspace` R4"""
    mk_entry(performed_at=T10)
    mk_entry(performed_at=T11)
    mk_entry(performed_at=T12)

    result = dao.get_by_workspace(db, workspace_id=w1.id, start_date=T12, end_date=T10)

    # Then 1
    assert result == []


# [claude] PLG-GW-18
def test_plg_gw_18__a_date_with_no_time_reaches_the_dao_as_midnight_compared_as_given(db, w1, mk_entry):
    """PLG-GW-18 — a date with no time reaches the DAO as midnight, compared as given.
    Rules: `get_by_workspace` R4"""
    mk_entry(performed_at=T10)
    mk_entry(performed_at=T11)
    mk_entry(performed_at=T12)

    result = dao.get_by_workspace(db, workspace_id=w1.id, end_date=datetime(2026, 3, 1, 0, 0, 0))

    # Then 1
    assert result == []


# [claude] PLG-GW-19
def test_plg_gw_19__aware_bounds_find_the_row_under_utc(db, w1, mk_entry):
    """PLG-GW-19 — aware bounds find the row under UTC.
    Rules: `get_by_workspace` R4a"""
    db.execute(text("SET LOCAL TIME ZONE 'UTC'"))
    a = mk_entry(performed_at=T12)

    result = dao.get_by_workspace(db, workspace_id=w1.id, start_date=Z(11, 30), end_date=Z(12, 30))

    # Then 1
    assert ids(result) == [a.id]


# [claude] PLG-GW-20
@pytest.mark.xfail(strict=True, reason="BUG-992: Ledger date filter with a time zone depends on the database's time-zone setting")
def test_plg_gw_20__aware_bounds_find_the_row_under_asia_dhaka(db, w1, mk_entry):
    """PLG-GW-20 — aware bounds find the row under Asia/Dhaka.
    Rules: `get_by_workspace` R4a [BUG-992]"""
    db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))
    a = mk_entry(performed_at=T12)

    result = dao.get_by_workspace(db, workspace_id=w1.id, start_date=Z(11, 30), end_date=Z(12, 30))

    # Then 1
    assert ids(result) == [a.id]


# [claude] PLG-GW-21
@pytest.mark.xfail(strict=True, reason="BUG-992: Ledger date filter with a time zone depends on the database's time-zone setting")
def test_plg_gw_21__aware_bounds_find_the_row_under_america_new_york(db, w1, mk_entry):
    """PLG-GW-21 — aware bounds find the row under America/New_York.
    Rules: `get_by_workspace` R4a [BUG-992]"""
    db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))
    a = mk_entry(performed_at=T12)

    result = dao.get_by_workspace(db, workspace_id=w1.id, start_date=Z(11, 30), end_date=Z(12, 30))

    # Then 1
    assert ids(result) == [a.id]


# [claude] PLG-GW-22
@pytest.mark.xfail(strict=True, reason="BUG-992: Ledger date filter with a time zone depends on the database's time-zone setting")
def test_plg_gw_22__an_aware_start_date_alone_is_converted_too(db, w1, mk_entry):
    """PLG-GW-22 — an aware start_date alone is converted too.
    Rules: `get_by_workspace` R4a [BUG-992]"""
    db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))
    a = mk_entry(performed_at=T12)

    result = dao.get_by_workspace(db, workspace_id=w1.id, start_date=Z(11, 30))

    # Then 1
    assert ids(result) == [a.id]


# [claude] PLG-GW-23
@pytest.mark.xfail(strict=True, reason="BUG-992: Ledger date filter with a time zone depends on the database's time-zone setting")
def test_plg_gw_23__an_aware_end_date_alone_is_converted_too(db, w1, mk_entry):
    """PLG-GW-23 — an aware end_date alone is converted too.
    Rules: `get_by_workspace` R4a [BUG-992]"""
    db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))
    mk_entry(performed_at=T12)

    result = dao.get_by_workspace(db, workspace_id=w1.id, end_date=Z(11, 30))

    # Then 1
    assert result == []


# [claude] PLG-GW-24
def test_plg_gw_24__transaction_type_keeps_the_rows_of_that_type(db, w1, mk_entry):
    """PLG-GW-24 — transaction_type keeps the rows of that type.
    Rules: `get_by_workspace` R5"""
    mk_entry(performed_at=T12, transaction_type="return")
    a = mk_entry(performed_at=T11)

    result = dao.get_by_workspace(db, workspace_id=w1.id, transaction_type="sale")

    # Then 1
    assert ids(result) == [a.id]


# [claude] PLG-GW-25
def test_plg_gw_25__capitals_do_not_match(db, w1, mk_entry):
    """PLG-GW-25 — capitals do not match.
    Rules: `get_by_workspace` R5"""
    mk_entry(performed_at=T12)

    result = dao.get_by_workspace(db, workspace_id=w1.id, transaction_type="SALE")

    # Then 1
    assert result == []


# [claude] PLG-GW-26
def test_plg_gw_26__a_leading_space_does_not_match(db, w1, mk_entry):
    """PLG-GW-26 — a leading space does not match.
    Rules: `get_by_workspace` R5"""
    mk_entry(performed_at=T12)

    result = dao.get_by_workspace(db, workspace_id=w1.id, transaction_type=" sale")

    # Then 1
    assert result == []


# [claude] PLG-GW-27
def test_plg_gw_27__the_start_of_a_type_does_not_match(db, w1, mk_entry):
    """PLG-GW-27 — the start of a type does not match.
    Rules: `get_by_workspace` R5"""
    mk_entry(performed_at=T12)

    result = dao.get_by_workspace(db, workspace_id=w1.id, transaction_type="sal")

    # Then 1
    assert result == []


# [claude] PLG-GW-28
def test_plg_gw_28__the_end_of_a_type_does_not_match(db, w1, mk_entry):
    """PLG-GW-28 — the end of a type does not match.
    Rules: `get_by_workspace` R5"""
    mk_entry(performed_at=T12)

    result = dao.get_by_workspace(db, workspace_id=w1.id, transaction_type="ale")

    # Then 1
    assert result == []


# [claude] PLG-GW-29
def test_plg_gw_29__is_no_wildcard(db, w1, mk_entry):
    """PLG-GW-29 — _ is no wildcard.
    Rules: `get_by_workspace` R5"""
    mk_entry(performed_at=T12)

    result = dao.get_by_workspace(db, workspace_id=w1.id, transaction_type="s_le")

    # Then 1
    assert result == []


# [claude] PLG-GW-30
def test_plg_gw_30__is_no_wildcard(db, w1, mk_entry):
    """PLG-GW-30 — % is no wildcard.
    Rules: `get_by_workspace` R5"""
    mk_entry(performed_at=T12)

    result = dao.get_by_workspace(db, workspace_id=w1.id, transaction_type="%")

    # Then 1
    assert result == []


# [claude] PLG-GW-31
def test_plg_gw_31__a_space_alone_is_a_filter_and_finds_nothing(db, w1, mk_entry):
    """PLG-GW-31 — a space alone is a filter and finds nothing.
    Rules: `get_by_workspace` R5"""
    mk_entry(performed_at=T12)

    result = dao.get_by_workspace(db, workspace_id=w1.id, transaction_type=" ")

    # Then 1
    assert result == []


# [claude] PLG-GW-32
def test_plg_gw_32__a_stored_type_with_a_space_is_not_found_the_stored_side_is_not_trimmed(db, w1, mk_entry):
    """PLG-GW-32 — a stored type with a space is not found: the stored side is not trimmed.
    Rules: `get_by_workspace` R5"""
    mk_entry(performed_at=T12, transaction_type=" sale")

    result = dao.get_by_workspace(db, workspace_id=w1.id, transaction_type="sale")

    # Then 1
    assert result == []


# [claude] PLG-GW-33
def test_plg_gw_33__a_stored_type_in_capitals_is_not_found(db, w1, mk_entry):
    """PLG-GW-33 — a stored type in capitals is not found.
    Rules: `get_by_workspace` R5"""
    mk_entry(performed_at=T12, transaction_type="SALE")

    result = dao.get_by_workspace(db, workspace_id=w1.id, transaction_type="sale")

    # Then 1
    assert result == []


# [claude] PLG-GW-34
def test_plg_gw_34__transaction_type_applies_no_filter(db, w1, mk_entry):
    """PLG-GW-34 — transaction_type="" applies no filter.
    Rules: `get_by_workspace` R5a"""
    a = mk_entry(performed_at=T12)
    b = mk_entry(performed_at=T11, transaction_type="return")

    result = dao.get_by_workspace(db, workspace_id=w1.id, transaction_type="")

    # Then 1
    assert ids(result) == [a.id, b.id]


# [claude] PLG-GW-35
def test_plg_gw_35__transaction_type_none_applies_no_filter(db, w1, mk_entry):
    """PLG-GW-35 — transaction_type=None applies no filter.
    Rules: `get_by_workspace` R5a"""
    a = mk_entry(performed_at=T12)
    b = mk_entry(performed_at=T11, transaction_type="return")

    result = dao.get_by_workspace(db, workspace_id=w1.id, transaction_type=None)

    # Then 1
    assert ids(result) == [a.id, b.id]


# [claude] PLG-GW-36
def test_plg_gw_36__all_the_filters_combine_with_and(db, w1, f1, f2, i1, i2, mk_entry):
    """PLG-GW-36 — all the filters combine with AND.
    Rules: `get_by_workspace` R6"""
    a = mk_entry(performed_at=T11)
    mk_entry(performed_at=T11, factory_id=f2.id)
    mk_entry(performed_at=T11, item_id=i2.id)
    mk_entry(performed_at=T9)
    mk_entry(performed_at=T12)
    mk_entry(performed_at=T11, transaction_type="return")

    result = dao.get_by_workspace(db, workspace_id=w1.id, factory_id=f1.id, item_id=i1.id, start_date=T10, end_date=T11, transaction_type="sale")

    # Then 1
    assert ids(result) == [a.id]


# [claude] PLG-GW-37
def test_plg_gw_37__two_filters_no_row_meets_together_return_an_empty_list(db, w1, f2, i2, mk_entry):
    """PLG-GW-37 — two filters no row meets together return an empty list.
    Rules: `get_by_workspace` R6"""
    mk_entry(performed_at=T12, factory_id=f2.id)
    mk_entry(performed_at=T11, item_id=i2.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, factory_id=f2.id, item_id=i2.id)

    # Then 1
    assert result == []


# [claude] PLG-GW-38
def test_plg_gw_38__the_factory_filter_runs_before_the_page(db, w1, f1, f2, mk_entry):
    """PLG-GW-38 — the factory filter runs before the page.
    Rules: `get_by_workspace` R6"""
    mk_entry(performed_at=T12, factory_id=f2.id)
    mk_entry(performed_at=T11)
    b = mk_entry(performed_at=T10)

    result = dao.get_by_workspace(db, workspace_id=w1.id, factory_id=f1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] PLG-GW-39
def test_plg_gw_39__the_item_filter_runs_before_the_page(db, w1, i1, i2, mk_entry):
    """PLG-GW-39 — the item filter runs before the page.
    Rules: `get_by_workspace` R6"""
    mk_entry(performed_at=T12, item_id=i2.id)
    mk_entry(performed_at=T11)
    b = mk_entry(performed_at=T10)

    result = dao.get_by_workspace(db, workspace_id=w1.id, item_id=i1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] PLG-GW-40
def test_plg_gw_40__the_type_filter_runs_before_the_page(db, w1, mk_entry):
    """PLG-GW-40 — the type filter runs before the page.
    Rules: `get_by_workspace` R6"""
    mk_entry(performed_at=T12, transaction_type="return")
    mk_entry(performed_at=T11)
    b = mk_entry(performed_at=T10)

    result = dao.get_by_workspace(db, workspace_id=w1.id, transaction_type="sale", skip=1, limit=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] PLG-GW-41
def test_plg_gw_41__the_date_filter_runs_before_the_page(db, w1, mk_entry):
    """PLG-GW-41 — the date filter runs before the page.
    Rules: `get_by_workspace` R6"""
    mk_entry(performed_at=T12)
    mk_entry(performed_at=T11)
    b = mk_entry(performed_at=T10)

    result = dao.get_by_workspace(db, workspace_id=w1.id, end_date=T11, skip=1, limit=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] PLG-GW-42
@pytest.mark.xfail(strict=True, reason="BUG-640: Ledger lists ordered by `performed_at` only; ties in no fixed order")
def test_plg_gw_42__the_query_orders_by_performed_at_then_id_both_descending(db, w1, mk_entry, recorder):
    """PLG-GW-42 — the query orders by performed_at, then id, both descending.
    Rules: `get_by_workspace` R7 [BUG-640]"""
    a = mk_entry(performed_at=T12)

    recorder.start()
    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    sql = recorder.sql()
    order_part = order_part_of(sql)
    assert "ORDER BY" in sql
    # Then 3
    assert "performed_at" in order_part
    # Then 4
    assert ".id" in order_part
    # Then 5
    assert order_part.index("performed_at") < order_part.index(".id")
    # Then 6
    assert order_part.upper().count("DESC") == 2
    # Then 7
    assert order_part.count(",") == 1


# [claude] PLG-GW-43
@pytest.mark.xfail(
    strict=False,
    reason="BUG-640: Ledger lists ordered by `performed_at` only; ties in no fixed order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_plg_gw_43__tied_rows_the_highest_id_comes_first_when_the_lowest_id_was_updated(db, w1, mk_entry):
    """PLG-GW-43 — tied rows: the highest id comes first, when the lowest id was updated.
    Rules: `get_by_workspace` R7 [BUG-640]"""
    seqscan(db)
    a = mk_entry(performed_at=T11)
    b = mk_entry(performed_at=T11)
    c = mk_entry(performed_at=T11)
    a.notes = "Changed"
    db.flush()
    db.expire_all()

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [c.id, b.id, a.id]


# [claude] PLG-GW-44
@pytest.mark.xfail(
    strict=False,
    reason="BUG-640: Ledger lists ordered by `performed_at` only; ties in no fixed order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_plg_gw_44__tied_rows_the_id_decides_when_type_quantity_user_and_source_would_each(db, w1, u1, u2, mk_entry):
    """PLG-GW-44 — tied rows: the id decides, when type, quantity, user and source would each sort otherwise, and an older row has the highest id.
    Rules: `get_by_workspace` R7 [BUG-640]"""
    seqscan(db)
    a = mk_entry(performed_at=T11, transaction_type="return", quantity=7, performed_by=u2.id, source_id=30)
    b = mk_entry(performed_at=T11, transaction_type="sale", quantity=9, performed_by=u1.id, source_id=10)
    c = mk_entry(performed_at=T11, transaction_type="adjust", quantity=5, performed_by=u2.id, source_id=20)
    d = mk_entry(performed_at=T10, transaction_type="zero", quantity=1)
    db.expire_all()

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 4
    # Then 2
    assert ids(result) == [c.id, b.id, a.id, d.id]


# [claude] PLG-GW-45
@pytest.mark.xfail(
    strict=False,
    reason="BUG-640: Ledger lists ordered by `performed_at` only; ties in no fixed order "
    "(non-strict: the rows have no fixed order; which row is on which page rests on physical row order)",
)
def test_plg_gw_45__rows_paged_one_at_a_time_neither_repeat_nor_miss_a_row(db, w1, mk_entry):
    """PLG-GW-45 — rows paged one at a time neither repeat nor miss a row.
    Rules: `get_by_workspace` R7 [BUG-640], R8"""
    seqscan(db)
    a = mk_entry(performed_at=T11)
    b = mk_entry(performed_at=T11)
    c = mk_entry(performed_at=T11)
    d = mk_entry(performed_at=T11)
    e = mk_entry(performed_at=T11)
    a.notes = "Changed"
    db.flush()
    db.expire_all()

    pages = [dao.get_by_workspace(db, workspace_id=w1.id, skip=k, limit=1) for k in range(5)]

    # Then 1
    assert [len(p) for p in pages] == [1, 1, 1, 1, 1]
    # Then 2
    assert [p[0].id for p in pages] == [e.id, d.id, c.id, b.id, a.id]


# [claude] PLG-GW-46
def test_plg_gw_46__the_later_time_comes_first_whatever_the_ids(db, w1, mk_entry):
    """PLG-GW-46 — the later time comes first, whatever the ids.
    Rules: `get_by_workspace` R7a"""
    a = mk_entry(performed_at=T10)
    b = mk_entry(performed_at=T12)
    c = mk_entry(performed_at=T11)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [b.id, c.id, a.id]


# [claude] PLG-GW-47
def test_plg_gw_47__an_older_row_with_the_higher_id_inside_one_day_comes_after(db, w1, mk_entry):
    """PLG-GW-47 — an older row with the higher id inside one day comes after.
    Rules: `get_by_workspace` R7a"""
    a = mk_entry(performed_at=T12)
    b = mk_entry(performed_at=T11)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id, b.id]


# [claude] PLG-GW-48
def test_plg_gw_48__the_order_is_applied_before_the_page_is_cut(db, w1, mk_entry):
    """PLG-GW-48 — the order is applied before the page is cut.
    Rules: `get_by_workspace` R7a"""
    mk_entry(performed_at=T10)
    mk_entry(performed_at=T12)
    c = mk_entry(performed_at=T11)

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [c.id]


# [claude] PLG-GW-49
def test_plg_gw_49__with_the_defaults_101_rows_give_100(db, w1, new_entry):
    """PLG-GW-49 — with the defaults 101 rows give 100.
    Rules: `get_by_workspace` R8"""
    rows = [new_entry(performed_at=T9 + timedelta(minutes=k)) for k in range(1, 102)]
    add_many(db, rows)
    newest = [row.id for row in reversed(rows)]

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert ids(result) == newest[:100]


# [claude] PLG-GW-50
def test_plg_gw_50__limit_1000_gives_all_101(db, w1, new_entry):
    """PLG-GW-50 — limit=1000 gives all 101.
    Rules: `get_by_workspace` R8"""
    rows = [new_entry(performed_at=T9 + timedelta(minutes=k)) for k in range(1, 102)]
    add_many(db, rows)
    newest = [row.id for row in reversed(rows)]

    result = dao.get_by_workspace(db, workspace_id=w1.id, limit=1000)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert ids(result) == newest


# [claude] PLG-GW-51
def test_plg_gw_51__skip_and_limit_cut_one_row_from_the_middle(db, w1, mk_entry):
    """PLG-GW-51 — skip and limit cut one row from the middle.
    Rules: `get_by_workspace` R8"""
    mk_entry(performed_at=T12)
    b = mk_entry(performed_at=T11)
    mk_entry(performed_at=T10)

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] PLG-GW-52
def test_plg_gw_52__limit_0_returns_an_empty_list(db, w1, mk_entry):
    """PLG-GW-52 — limit=0 returns an empty list.
    Rules: `get_by_workspace` R9"""
    mk_entry(performed_at=T12)
    mk_entry(performed_at=T11)

    result = dao.get_by_workspace(db, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [claude] PLG-GW-53
def test_plg_gw_53__limit_1_returns_one_row(db, w1, mk_entry):
    """PLG-GW-53 — limit=1 returns one row.
    Rules: `get_by_workspace` R9"""
    a = mk_entry(performed_at=T12)
    mk_entry(performed_at=T11)

    result = dao.get_by_workspace(db, workspace_id=w1.id, limit=1)

    # Then 1
    assert ids(result) == [a.id]


# [claude] PLG-GW-54
def test_plg_gw_54__skip_at_the_number_of_rows_returns_an_empty_list(db, w1, mk_entry):
    """PLG-GW-54 — skip at the number of rows returns an empty list.
    Rules: `get_by_workspace` R9"""
    mk_entry(performed_at=T12)
    mk_entry(performed_at=T11)

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [claude] PLG-GW-55
def test_plg_gw_55__skip_at_the_last_row_returns_one_row(db, w1, mk_entry):
    """PLG-GW-55 — skip at the last row returns one row.
    Rules: `get_by_workspace` R9"""
    mk_entry(performed_at=T12)
    b = mk_entry(performed_at=T11)

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] PLG-GW-56
def test_plg_gw_56__a_negative_limit_raises(db, w1, mk_entry):
    """PLG-GW-56 — a negative limit raises.
    Rules: `get_by_workspace` R10, Errors row 1"""
    mk_entry(performed_at=T12)
    mk_entry(performed_at=T11)
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_workspace(db, workspace_id=w1.id, limit=-1)
    # Then 2
    assert exc.value.orig.pgcode == "2201W"
    # Then 3
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 4
    assert stored_count(db) == before


# [claude] PLG-GW-57
def test_plg_gw_57__a_negative_skip_raises(db, w1, mk_entry):
    """PLG-GW-57 — a negative skip raises.
    Rules: `get_by_workspace` R10, Errors row 2"""
    mk_entry(performed_at=T12)
    mk_entry(performed_at=T11)
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_workspace(db, workspace_id=w1.id, skip=-1)
    # Then 2
    assert exc.value.orig.pgcode == "2201X"
    # Then 3
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 4
    assert stored_count(db) == before


# [claude] PLG-GW-58
def test_plg_gw_58__the_row_of_a_soft_deleted_factory_is_returned(db, w1, fd, mk_entry):
    """PLG-GW-58 — the row of a soft-deleted factory is returned.
    Rules: `get_by_workspace` R11"""
    a = mk_entry(performed_at=T12, factory_id=fd.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] PLG-GW-59
def test_plg_gw_59__the_row_of_a_soft_deleted_factory_is_returned_filtered_by_that_factory(db, w1, fd, mk_entry):
    """PLG-GW-59 — the row of a soft-deleted factory is returned, filtered by that factory.
    Rules: `get_by_workspace` R11"""
    a = mk_entry(performed_at=T12, factory_id=fd.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, factory_id=fd.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] PLG-GW-60
def test_plg_gw_60__the_row_of_a_removed_item_is_returned(db, w1, ix, mk_entry):
    """PLG-GW-60 — the row of a removed item is returned.
    Rules: `get_by_workspace` R11"""
    a = mk_entry(performed_at=T12, item_id=ix.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] PLG-GW-61
def test_plg_gw_61__the_row_of_a_removed_item_is_returned_filtered_by_that_item(db, w1, ix, mk_entry):
    """PLG-GW-61 — the row of a removed item is returned, filtered by that item.
    Rules: `get_by_workspace` R11"""
    a = mk_entry(performed_at=T12, item_id=ix.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, item_id=ix.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] PLG-GW-62
def test_plg_gw_62__the_query_does_not_read_the_parent_tables(db, w1, fd, mk_entry, recorder):
    """PLG-GW-62 — the query does not read the parent tables.
    Rules: `get_by_workspace` R11"""
    mk_entry(performed_at=T12, factory_id=fd.id)

    recorder.start()
    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 1
    # Then 2
    sql = recorder.sql()
    assert "JOIN" not in sql
    # Then 3
    assert "factories" not in sql


# [claude] PLG-GW-63
def test_plg_gw_63__writes_nothing_a_pending_row_that_would_sort_first_stays_pending_and_i(db, w1, f1, i1, mk_entry, recorder):
    """PLG-GW-63 — writes nothing: a pending row that would sort first stays pending and is not returned.
    Rules: `get_by_workspace` Side effects"""
    a = mk_entry(performed_at=T11)
    p = ProductLedger(workspace_id=w1.id, factory_id=f1.id, item_id=i1.id, transaction_type="sale", quantity=1, qty_before=5, qty_after=4, performed_at=T12)
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    recorder.start()
    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert p in db.new
    # Then 3
    assert p.id is None
    # Then 4
    assert len(db.new) == 1
    # Then 5
    assert not db.dirty and not db.deleted
    # Then 6
    assert stored_count(db) == before
    # Then 7
    db.expire_all()
    assert snap(db, a) == before_a
    # Then 8
    assert recorder.written() == []


# [claude] PLG-GW-64
def test_plg_gw_64__writes_nothing_a_read_leaves_the_caller_s_unflushed_edit_alone(db, w1, mk_entry):
    """PLG-GW-64 — writes nothing: a read leaves the caller's unflushed edit alone.
    Rules: `get_by_workspace` Side effects"""
    a = mk_entry(performed_at=T12)
    b = mk_entry(performed_at=T11)
    b.notes = "Edited"

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert b.notes == "Edited"


# [claude] PLG-GW-65
def test_plg_gw_65__another_workspace_s_row_sorts_first_and_takes_no_place_in_the_page(db, w1, w2, f9, i9, mk_entry):
    """PLG-GW-65 — another workspace's row sorts first and takes no place in the page.
    Rules: `get_by_workspace` R1, R6"""
    mk_entry(performed_at=T12, workspace_id=w2.id, factory_id=f9.id, item_id=i9.id)
    mk_entry(performed_at=T11)
    b = mk_entry(performed_at=T10)

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] PLG-GW-66
def test_plg_gw_66__bounds_at_06_00_are_converted_under_utc(db, w1, mk_entry):
    """PLG-GW-66 — bounds at +06:00 are converted, under UTC.
    Rules: `get_by_workspace` R4a"""
    db.execute(text("SET LOCAL TIME ZONE 'UTC'"))
    a = mk_entry(performed_at=T12)

    result = dao.get_by_workspace(db, workspace_id=w1.id, start_date=datetime(2026, 3, 1, 17, 30, tzinfo=timezone(timedelta(hours=6))), end_date=datetime(2026, 3, 1, 18, 30, tzinfo=timezone(timedelta(hours=6))))

    # Then 1
    assert ids(result) == [a.id]


# --------------------------------------------------------------------------- #
# ProductLedgerDAO.exists_for_production_batch
# --------------------------------------------------------------------------- #


# [claude] PLG-EX-01
def test_plg_ex_01__one_matching_row_gives_true(db, w1, mk_posted):
    """PLG-EX-01 — one matching row gives True.
    Rules: `exists_for_production_batch` R1, Returns"""
    mk_posted(source_id=88)

    result = dao.exists_for_production_batch(db, workspace_id=w1.id, batch_id=88)

    # Then 1
    assert result is True


# [claude] PLG-EX-02
def test_plg_ex_02__several_matching_rows_give_true(db, w1, mk_posted):
    """PLG-EX-02 — several matching rows give True.
    Rules: `exists_for_production_batch` R1"""
    mk_posted(source_id=88)
    mk_posted(source_id=88, transaction_type="production_output")

    result = dao.exists_for_production_batch(db, workspace_id=w1.id, batch_id=88)

    # Then 1
    assert result is True


# [claude] PLG-EX-03
def test_plg_ex_03__a_batch_with_no_ledger_row_gives_false(db, w1):
    """PLG-EX-03 — a batch with no ledger row gives False.
    Rules: `exists_for_production_batch` R2, Returns"""
    result = dao.exists_for_production_batch(db, workspace_id=w1.id, batch_id=88)

    # Then 1
    assert result is False


# [claude] PLG-EX-04
def test_plg_ex_04__another_batch_gives_false(db, w1, mk_posted):
    """PLG-EX-04 — another batch gives False.
    Rules: `exists_for_production_batch` R2"""
    mk_posted(source_id=87)

    result = dao.exists_for_production_batch(db, workspace_id=w1.id, batch_id=88)

    # Then 1
    assert result is False


# [claude] PLG-EX-05
def test_plg_ex_05__batch_id_0_gives_false(db, w1, mk_posted):
    """PLG-EX-05 — batch_id=0 gives False.
    Rules: `exists_for_production_batch` R2"""
    mk_posted(source_id=88)

    result = dao.exists_for_production_batch(db, workspace_id=w1.id, batch_id=0)

    # Then 1
    assert result is False


# [claude] PLG-EX-06
def test_plg_ex_06__an_unknown_batch_gives_false(db, w1, mk_posted):
    """PLG-EX-06 — an unknown batch gives False.
    Rules: `exists_for_production_batch` R2"""
    mk_posted(source_id=88)

    result = dao.exists_for_production_batch(db, workspace_id=w1.id, batch_id=MISSING)

    # Then 1
    assert result is False


# [claude] PLG-EX-07
def test_plg_ex_07__the_row_s_own_id_is_not_the_batch_id(db, w1, mk_posted):
    """PLG-EX-07 — the row's own id is not the batch id.
    Rules: `exists_for_production_batch` R2"""
    a = mk_posted(source_id=999999998)

    result = dao.exists_for_production_batch(db, workspace_id=w1.id, batch_id=a.id)

    # Then 1
    assert result is False


# [claude] PLG-EX-08
def test_plg_ex_08__the_same_source_id_under_sales_delivery_gives_false(db, w1, mk_entry):
    """PLG-EX-08 — the same source_id under sales_delivery gives False.
    Rules: `exists_for_production_batch` R3"""
    mk_entry(performed_at=T10, source_type="sales_delivery", source_id=88)

    result = dao.exists_for_production_batch(db, workspace_id=w1.id, batch_id=88)

    # Then 1
    assert result is False


# [claude] PLG-EX-09
def test_plg_ex_09__a_row_with_no_source_type_gives_false(db, w1, mk_entry):
    """PLG-EX-09 — a row with no source_type gives False.
    Rules: `exists_for_production_batch` R3"""
    mk_entry(performed_at=T10, source_id=88)

    result = dao.exists_for_production_batch(db, workspace_id=w1.id, batch_id=88)

    # Then 1
    assert result is False


# [claude] PLG-EX-10
def test_plg_ex_10__a_stored_source_type_in_capitals_does_not_count(db, w1, mk_entry):
    """PLG-EX-10 — a stored source_type in capitals does not count.
    Rules: `exists_for_production_batch` R3"""
    mk_entry(performed_at=T10, source_type="PRODUCTION_BATCH", source_id=88)

    result = dao.exists_for_production_batch(db, workspace_id=w1.id, batch_id=88)

    # Then 1
    assert result is False


# [claude] PLG-EX-11
def test_plg_ex_11__a_stored_source_type_with_a_leading_space_does_not_count(db, w1, mk_entry):
    """PLG-EX-11 — a stored source_type with a leading space does not count.
    Rules: `exists_for_production_batch` R3"""
    mk_entry(performed_at=T10, source_type=" production_batch", source_id=88)

    result = dao.exists_for_production_batch(db, workspace_id=w1.id, batch_id=88)

    # Then 1
    assert result is False


# [claude] PLG-EX-12
def test_plg_ex_12__a_part_of_the_source_type_does_not_count(db, w1, mk_entry):
    """PLG-EX-12 — a part of the source_type does not count.
    Rules: `exists_for_production_batch` R3"""
    mk_entry(performed_at=T10, source_type="production", source_id=88)

    result = dao.exists_for_production_batch(db, workspace_id=w1.id, batch_id=88)

    # Then 1
    assert result is False


# [claude] PLG-EX-13
def test_plg_ex_13__another_separator_does_not_count_is_no_wildcard(db, w1, mk_entry):
    """PLG-EX-13 — another separator does not count: _ is no wildcard.
    Rules: `exists_for_production_batch` R3"""
    mk_entry(performed_at=T10, source_type="production-batch", source_id=88)

    result = dao.exists_for_production_batch(db, workspace_id=w1.id, batch_id=88)

    # Then 1
    assert result is False


# [claude] PLG-EX-14
def test_plg_ex_14__a_matching_row_under_another_workspace_gives_false(db, w1, w2, f9, i9, mk_posted):
    """PLG-EX-14 — a matching row under another workspace gives False.
    Rules: `exists_for_production_batch` R4"""
    mk_posted(source_id=88, workspace_id=w2.id, factory_id=f9.id, item_id=i9.id)

    result = dao.exists_for_production_batch(db, workspace_id=w1.id, batch_id=88)

    # Then 1
    assert result is False


# [claude] PLG-EX-15
def test_plg_ex_15__a_matching_row_of_w1_gives_false_for_w2(db, w2, mk_posted):
    """PLG-EX-15 — a matching row of W1 gives False for W2.
    Rules: `exists_for_production_batch` R4"""
    mk_posted(source_id=88)

    result = dao.exists_for_production_batch(db, workspace_id=w2.id, batch_id=88)

    # Then 1
    assert result is False


# [claude] PLG-EX-16
def test_plg_ex_16__the_w1_row_answers_w1_when_w2_s_row_is_the_earlier_one(db, w1, w2, f9, i9, mk_posted):
    """PLG-EX-16 — the W1 row answers W1, when W2's row is the earlier one.
    Rules: `exists_for_production_batch` R4"""
    mk_posted(source_id=88, workspace_id=w2.id, factory_id=f9.id, item_id=i9.id)
    mk_posted(source_id=88)

    result = dao.exists_for_production_batch(db, workspace_id=w1.id, batch_id=88)

    # Then 1
    assert result is True


# [claude] PLG-EX-17
def test_plg_ex_17__writes_nothing_a_pending_matching_row_stays_pending_and_does_not_count(db, w1, f1, i1, mk_posted, recorder):
    """PLG-EX-17 — writes nothing: a pending matching row stays pending and does not count.
    Rules: `exists_for_production_batch` Side effects"""
    a = mk_posted(source_id=87)
    p = ProductLedger(workspace_id=w1.id, factory_id=f1.id, item_id=i1.id, transaction_type="sale", quantity=1, qty_before=5, qty_after=4, performed_at=T12, source_type="production_batch", source_id=88)
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    recorder.start()
    result = dao.exists_for_production_batch(db, workspace_id=w1.id, batch_id=88)

    # Then 1
    assert result is False
    # Then 2
    assert p in db.new
    # Then 3
    assert p.id is None
    # Then 4
    assert len(db.new) == 1
    # Then 5
    assert not db.dirty and not db.deleted
    # Then 6
    assert stored_count(db) == before
    # Then 7
    db.expire_all()
    assert snap(db, a) == before_a
    # Then 8
    assert recorder.written() == []


# [claude] PLG-EX-18
def test_plg_ex_18__writes_nothing_a_read_leaves_the_caller_s_unflushed_edit_alone(db, w1, mk_posted):
    """PLG-EX-18 — writes nothing: a read leaves the caller's unflushed edit alone.
    Rules: `exists_for_production_batch` Side effects"""
    mk_posted(source_id=88)
    b = mk_posted(source_id=87)
    b.notes = "Edited"

    result = dao.exists_for_production_batch(db, workspace_id=w1.id, batch_id=88)

    # Then 1
    assert result is True
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert b.notes == "Edited"


# [claude] PLG-EX-19
def test_plg_ex_19__a_stored_source_type_that_extends_the_constant_does_not_count(db, w1, mk_entry):
    """PLG-EX-19 — a stored source_type that extends the constant does not count.
    Rules: `exists_for_production_batch` R3"""
    mk_entry(performed_at=T10, source_type="production_batch_v2", source_id=88)

    result = dao.exists_for_production_batch(db, workspace_id=w1.id, batch_id=88)

    # Then 1
    assert result is False


# --------------------------------------------------------------------------- #
# Inherited BaseDAO methods on ProductLedger
# --------------------------------------------------------------------------- #


# [claude] PLG-INH-01
def test_plg_inh_01__create_with_a_productledgercreate_fails_on_flush_and_saves_nothing(db, f1, i1):
    """PLG-INH-01 — create with a ProductLedgerCreate fails on flush and saves nothing.
    Rules: `inherited` R1"""
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in=ProductLedgerCreate(factory_id=f1.id, item_id=i1.id, transaction_type="sale", quantity=1, qty_before=5, qty_after=4))
    # Then 2
    assert isinstance(exc.value.orig, NotNullViolation)
    # Then 3
    assert exc.value.orig.pgcode == "23502"
    # Then 4
    assert count_rows(db, ProductLedger) == 0


# [claude] PLG-INH-02
def test_plg_inh_02__create_with_a_dict_and_no_performed_at_sets_it(db, w1, f1, i1):
    """PLG-INH-02 — create with a dict and no performed_at sets it.
    Rules: `inherited` R2"""
    result = dao.create(db, obj_in={"workspace_id": w1.id, "factory_id": f1.id, "item_id": i1.id, "transaction_type": "sale", "quantity": 1, "qty_before": 5, "qty_after": 4})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.performed_at is not None
    # Then 3
    row = reread(db, result)
    assert row.quantity == 1
    assert row.qty_before == 5
    assert row.qty_after == 4


# [claude] PLG-INH-03
def test_plg_inh_03__create_is_flushed_not_committed_a_rollback_removes_the_row(db, w1, f1, i1):
    """PLG-INH-03 — create is flushed, not committed: a rollback removes the row.
    Rules: `inherited` R2"""
    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        result = dao.create(db, obj_in={"workspace_id": w1.id, "factory_id": f1.id, "item_id": i1.id, "transaction_type": "sale", "quantity": 1, "qty_before": 5, "qty_after": 4})

    # Then 1
    assert result.id is not None
    # Then 2
    assert count_rows(db, ProductLedger) == 1
    # Then 3
    sp.rollback()
    assert count_rows(db, ProductLedger) == 0
    # Then 4
    commit_spy.assert_not_called()


# [claude] PLG-INH-04
def test_plg_inh_04__create_changes_no_stock_row(db, w1, f1, i1):
    """PLG-INH-04 — create changes no stock row.
    Rules: `inherited` Side effects"""
    s = _add(db, Product(workspace_id=w1.id, item_id=i1.id, factory_id=f1.id, qty=5))
    before_s = snap(db, s)

    result = dao.create(db, obj_in={"workspace_id": w1.id, "factory_id": f1.id, "item_id": i1.id, "transaction_type": "sale", "quantity": 1, "qty_before": 5, "qty_after": 4})

    # Then 1
    assert result.id is not None
    # Then 2
    db.expire_all()
    assert snap(db, s) == before_s


# [claude] PLG-INH-05
@pytest.mark.xfail(strict=True, reason="BUG-1337: A product ledger entry's time depends on the database's time zone")
def test_plg_inh_05__performed_at_is_within_a_minute_of_utc_under_asia_dhaka(db, w1, f1, i1):
    """PLG-INH-05 — performed_at is within a minute of UTC, under Asia/Dhaka.
    Rules: `inherited` R2a [BUG-1337]"""
    db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))

    result = dao.create(db, obj_in={"workspace_id": w1.id, "factory_id": f1.id, "item_id": i1.id, "transaction_type": "sale", "quantity": 1, "qty_before": 5, "qty_after": 4})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert abs(row.performed_at - utcnow()) < timedelta(minutes=1)


# [claude] PLG-INH-06
def test_plg_inh_06__update_with_a_productledgerupdate_changes_notes(db, mk_entry):
    """PLG-INH-06 — update with a ProductLedgerUpdate changes notes.
    Rules: `inherited` R3"""
    a = mk_entry(performed_at=T12, notes="Old")
    before_a = snap(db, a)

    result = dao.update(db, db_obj=a, obj_in=ProductLedgerUpdate(notes="New"))

    # Then 1
    assert result.id == a.id
    # Then 2
    row = reread(db, a)
    assert row.notes == "New"
    # Then 3
    db.expire_all()
    assert without(snap(db, a), "notes") == without(before_a, "notes")


# [claude] PLG-INH-07
def test_plg_inh_07__update_with_a_dict_changes_any_column(db, mk_entry):
    """PLG-INH-07 — update with a dict changes any column.
    Rules: `inherited` R4"""
    a = mk_entry(performed_at=T12)

    result = dao.update(db, db_obj=a, obj_in={"quantity": 9})

    # Then 1
    assert result.id == a.id
    # Then 2
    row = reread(db, a)
    assert row.quantity == 9


# [claude] PLG-INH-08
def test_plg_inh_08__update_is_flushed_not_committed_a_rollback_restores_the_row(db, mk_entry):
    """PLG-INH-08 — update is flushed, not committed: a rollback restores the row.
    Rules: `inherited` R4"""
    a = mk_entry(performed_at=T12)

    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        result = dao.update(db, db_obj=a, obj_in={"quantity": 9})

    # Then 1
    assert result.id == a.id
    # Then 2
    assert count_rows(db, ProductLedger, ProductLedger.quantity == 9) == 1
    # Then 3
    sp.rollback()
    assert count_rows(db, ProductLedger, ProductLedger.quantity == 1) == 1
    # Then 4
    commit_spy.assert_not_called()


# [claude] PLG-INH-09
def test_plg_inh_09__remove_hard_deletes_the_row(db, mk_entry):
    """PLG-INH-09 — remove hard-deletes the row.
    Rules: `inherited` R5"""
    a = mk_entry(performed_at=T12)
    b = mk_entry(performed_at=T11)
    before_b = snap(db, b)

    result = dao.remove(db, id=a.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert count_rows(db, ProductLedger) == 1
    # Then 3
    db.expire_all()
    assert snap(db, b) == before_b


# [claude] PLG-INH-10
def test_plg_inh_10__remove_is_flushed_not_committed_a_rollback_brings_the_row_back(db, mk_entry):
    """PLG-INH-10 — remove is flushed, not committed: a rollback brings the row back.
    Rules: `inherited` R5"""
    a = mk_entry(performed_at=T12)

    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        result = dao.remove(db, id=a.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert count_rows(db, ProductLedger) == 0
    # Then 3
    sp.rollback()
    assert count_rows(db, ProductLedger) == 1
    # Then 4
    commit_spy.assert_not_called()
