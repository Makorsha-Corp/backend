"""Unit tests for app/dao/product.py.

Implements tests/unit/dao/product.cases.md, one test per case, in card order. Real
Postgres session (`db` fixture).
Only `app.dao.product.utcnow` is patched, on the cards that say clock NOW.

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117, DTZ001  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested():`, and naive datetimes)
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

import pytest
from psycopg2.errors import (
    ForeignKeyViolation,
    NotNullViolation,
    NumericValueOutOfRange,
    UniqueViolation,
)
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import DataError, IntegrityError

from app.dao.product import product_dao
from app.models.factory import Factory
from app.models.item import Item
from app.models.product import Product
from app.models.product_ledger import ProductLedger
from app.schemas.product import ProductCreate, ProductUpdate
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton product_dao" (a module-level name, not a fixture)
dao = product_dao

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999

# Convention "T0": a past stamp
T0 = datetime(2026, 1, 15, 9, 0, 0)

# Conventions: fixed values
NOW = datetime(2031, 5, 6, 7, 8, 9)


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
    return _add(db, Factory(workspace_id=w1.id, name="Old Plant", abbreviation="OP", is_deleted=True, deleted_at=T0, deleted_by=u1.id))


@pytest.fixture
def fi(db, w1, fd):
    return _add(db, Factory(workspace_id=w1.id, name="Idle Plant", abbreviation="IP", is_active=False))


@pytest.fixture
def f9(db, w2, fi):
    return _add(db, Factory(workspace_id=w2.id, name="Far Plant", abbreviation="F9"))


@pytest.fixture
def i1(db, w1, f9):
    return _add(db, Item(workspace_id=w1.id, name="Bolt", name_normalized="bolt", unit="pcs"))


@pytest.fixture
def i2(db, w1, i1):
    return _add(db, Item(workspace_id=w1.id, name="Cam", name_normalized="cam", unit="pcs"))


@pytest.fixture
def i3(db, w1, i2):
    return _add(db, Item(workspace_id=w1.id, name="Disc", name_normalized="disc", unit="pcs"))


@pytest.fixture
def i4(db, w1, i3):
    return _add(db, Item(workspace_id=w1.id, name="Gear", name_normalized="gear", unit="pcs"))


@pytest.fixture
def i5(db, w1, i4):
    return _add(db, Item(workspace_id=w1.id, name="Hook", name_normalized="hook", unit="pcs"))


@pytest.fixture
def ix(db, w1, i5):
    return _add(db, Item(workspace_id=w1.id, name="Old Gasket", name_normalized="old gasket", unit="pcs", is_active=False))


@pytest.fixture
def i9(db, w2, ix):
    return _add(db, Item(workspace_id=w2.id, name="Far Crate", name_normalized="far crate", unit="pcs"))


# Convention "they exist in every test and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2, u1, u2, f1, f2, fd, fi, f9, i1, i2, i3, i4, i5, ix, i9):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builders (fixtures; each mk_ flushes before it returns)
# --------------------------------------------------------------------------- #

# Convention "stock"
@pytest.fixture
def new_stock(w1, i1, f1):
    """new_stock(**columns) -> Product, not added."""
    def _new(**columns):
        return Product(**{"workspace_id": w1.id, "item_id": i1.id, "factory_id": f1.id, "qty": 5, **columns})
    return _new


@pytest.fixture
def mk_stock(db, new_stock):
    """mk_stock(...) = new_stock(...), added and flushed."""
    def _mk(**columns):
        return _add(db, new_stock(**columns))
    return _mk

# Convention "item"
@pytest.fixture
def new_item(w1):
    """new_item(name=..., **columns) -> Item, not added."""
    def _new(*, name, **columns):
        return Item(**{"workspace_id": w1.id, "unit": "pcs", "name_normalized": name.lower(), "name": name, **columns})
    return _new


@pytest.fixture
def mk_item(db, new_item):
    """mk_item(...) = new_item(...), added and flushed."""
    def _mk(**columns):
        return _add(db, new_item(**columns))
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


# Convention "nothing written": the number of `products` rows stored (all workspaces)
def stored_count(db):
    return db.scalar(select(func.count()).select_from(Product.__table__))


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


# Convention "clock NOW": during the When. The module does not import utcnow yet, so the patch is unused today.
def clock_now():
    return patch("app.dao.product.utcnow", create=True, return_value=NOW)


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
        """The one SELECT from `products`; fails loudly unless there is exactly one."""
        [statement] = [s for s in self.selects() if "FROM products" in s]
        return statement


@pytest.fixture
def recorder(db):
    statement_recorder = StatementRecorder(db)
    yield statement_recorder
    statement_recorder.stop()


# --------------------------------------------------------------------------- #
# ProductDAO.get_by_workspace
# --------------------------------------------------------------------------- #


# [claude] PRD-GW-01
def test_prd_gw_01__returns_a_list_of_the_live_rows(db, w1, i1, i2, mk_stock):
    """PRD-GW-01 — returns a list of the live rows.
    Rules: `get_by_workspace` R1, Returns"""
    a = mk_stock(item_id=i1.id)
    b = mk_stock(item_id=i2.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 3
    assert isinstance(result[0], Product)


# [claude] PRD-GW-02
def test_prd_gw_02__a_row_of_another_workspace_with_a_later_id_is_not_returned(db, w1, w2, f9, i1, i9, mk_stock):
    """PRD-GW-02 — a row of another workspace with a later id is not returned.
    Rules: `get_by_workspace` R1"""
    a = mk_stock(item_id=i1.id)
    mk_stock(workspace_id=w2.id, item_id=i9.id, factory_id=f9.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] PRD-GW-03
def test_prd_gw_03__a_row_of_another_workspace_with_an_earlier_id_is_not_returned(db, w1, w2, f9, i1, i9, mk_stock):
    """PRD-GW-03 — a row of another workspace with an earlier id is not returned.
    Rules: `get_by_workspace` R1"""
    mk_stock(workspace_id=w2.id, item_id=i9.id, factory_id=f9.id)
    a = mk_stock(item_id=i1.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] PRD-GW-04
def test_prd_gw_04__a_soft_deleted_row_is_not_returned(db, w1, u1, i1, i2, mk_stock):
    """PRD-GW-04 — a soft-deleted row is not returned.
    Rules: `get_by_workspace` R2"""
    mk_stock(item_id=i1.id, is_active=False, is_deleted=True, deleted_at=T0, deleted_by=u1.id)
    a = mk_stock(item_id=i2.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] PRD-GW-05
def test_prd_gw_05__the_soft_delete_filter_runs_before_the_page_skip_2_past_the_two_visibl(db, w1, u1, i1, i2, i3, mk_stock):
    """PRD-GW-05 — the soft-delete filter runs before the page: skip=2 past the two visible rows gives nothing.
    Rules: `get_by_workspace` R2"""
    mk_stock(item_id=i1.id, is_active=False, is_deleted=True, deleted_at=T0, deleted_by=u1.id)
    mk_stock(item_id=i2.id)
    mk_stock(item_id=i3.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [claude] PRD-GW-06
def test_prd_gw_06__the_soft_delete_filter_runs_before_the_page_skip_1_leaves_one_visible_(db, w1, u1, i1, i2, i3, mk_stock):
    """PRD-GW-06 — the soft-delete filter runs before the page: skip=1 leaves one visible row.
    Rules: `get_by_workspace` R2"""
    x = mk_stock(item_id=i1.id, is_active=False, is_deleted=True, deleted_at=T0, deleted_by=u1.id)
    mk_stock(item_id=i2.id)
    mk_stock(item_id=i3.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert x.id not in ids(result)


# [claude] PRD-GW-07
def test_prd_gw_07__a_row_with_is_active_false_is_deleted_false_is_returned(db, w1, i1, i2, mk_stock):
    """PRD-GW-07 — a row with is_active False, is_deleted False is returned.
    Rules: `get_by_workspace` R2"""
    a = mk_stock(item_id=i1.id, is_active=False)
    b = mk_stock(item_id=i2.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]


# [claude] PRD-GW-08
def test_prd_gw_08__factory_id_narrows_to_that_factory(db, w1, f1, f2, i1, i2, i3, mk_stock):
    """PRD-GW-08 — factory_id narrows to that factory.
    Rules: `get_by_workspace` R3"""
    mk_stock(item_id=i1.id, factory_id=f2.id)
    a = mk_stock(item_id=i2.id)
    b = mk_stock(item_id=i3.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, factory_id=f1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]


# [claude] PRD-GW-09
def test_prd_gw_09__factory_id_0_returns_an_empty_list_0_is_a_filter(db, w1, i1, mk_stock):
    """PRD-GW-09 — factory_id=0 returns an empty list: 0 is a filter.
    Rules: `get_by_workspace` R3"""
    mk_stock(item_id=i1.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, factory_id=0)

    # Then 1
    assert result == []


# [claude] PRD-GW-10
def test_prd_gw_10__factory_id_none_applies_no_filter(db, w1, f2, i1, i2, mk_stock):
    """PRD-GW-10 — factory_id=None applies no filter.
    Rules: `get_by_workspace` R3"""
    a = mk_stock(item_id=i1.id)
    b = mk_stock(item_id=i2.id, factory_id=f2.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, factory_id=None)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]


# [claude] PRD-GW-11
def test_prd_gw_11__the_factory_filter_runs_before_the_page_skip_2_past_the_two_visible_ro(db, w1, f1, f2, i1, i2, i3, mk_stock):
    """PRD-GW-11 — the factory filter runs before the page: skip=2 past the two visible rows gives nothing.
    Rules: `get_by_workspace` R3"""
    mk_stock(item_id=i1.id, factory_id=f2.id)
    mk_stock(item_id=i2.id)
    mk_stock(item_id=i3.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, factory_id=f1.id, skip=2)

    # Then 1
    assert result == []


# [claude] PRD-GW-12
def test_prd_gw_12__the_factory_filter_runs_before_the_page_skip_1_leaves_one_visible_row(db, w1, f1, f2, i1, i2, i3, mk_stock):
    """PRD-GW-12 — the factory filter runs before the page: skip=1 leaves one visible row.
    Rules: `get_by_workspace` R3"""
    x = mk_stock(item_id=i1.id, factory_id=f2.id)
    mk_stock(item_id=i2.id)
    mk_stock(item_id=i3.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, factory_id=f1.id, skip=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert x.id not in ids(result)


# [claude] PRD-GW-13
def test_prd_gw_13__is_available_for_sale_true_returns_only_the_for_sale_rows(db, w1, i1, i2, mk_stock):
    """PRD-GW-13 — is_available_for_sale=True returns only the for-sale rows.
    Rules: `get_by_workspace` R4"""
    mk_stock(item_id=i1.id)
    a = mk_stock(item_id=i2.id, is_available_for_sale=True)

    result = dao.get_by_workspace(db, workspace_id=w1.id, is_available_for_sale=True)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] PRD-GW-14
def test_prd_gw_14__is_available_for_sale_false_is_a_filter_not_no_filter(db, w1, i1, i2, mk_stock):
    """PRD-GW-14 — is_available_for_sale=False is a filter, not "no filter".
    Rules: `get_by_workspace` R4"""
    mk_stock(item_id=i1.id, is_available_for_sale=True)
    a = mk_stock(item_id=i2.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, is_available_for_sale=False)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] PRD-GW-15
def test_prd_gw_15__is_available_for_sale_none_returns_both(db, w1, i1, mk_stock):
    """PRD-GW-15 — is_available_for_sale=None returns both.
    Rules: `get_by_workspace` R4"""
    a = mk_stock(item_id=i1.id, is_available_for_sale=True)
    b = mk_stock(item_id=i1.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, is_available_for_sale=None)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]


# [claude] PRD-GW-16
def test_prd_gw_16__the_sale_filter_runs_before_the_page_skip_2_past_the_two_visible_rows_(db, w1, i1, i2, i3, mk_stock):
    """PRD-GW-16 — the sale filter runs before the page: skip=2 past the two visible rows gives nothing.
    Rules: `get_by_workspace` R4"""
    mk_stock(item_id=i1.id, is_available_for_sale=True)
    mk_stock(item_id=i2.id)
    mk_stock(item_id=i3.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, is_available_for_sale=False, skip=2)

    # Then 1
    assert result == []


# [claude] PRD-GW-17
def test_prd_gw_17__the_sale_filter_runs_before_the_page_skip_1_leaves_one_visible_row(db, w1, i1, i2, i3, mk_stock):
    """PRD-GW-17 — the sale filter runs before the page: skip=1 leaves one visible row.
    Rules: `get_by_workspace` R4"""
    x = mk_stock(item_id=i1.id, is_available_for_sale=True)
    mk_stock(item_id=i2.id)
    mk_stock(item_id=i3.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, is_available_for_sale=False, skip=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert x.id not in ids(result)


# [claude] PRD-GW-18
def test_prd_gw_18__the_two_filters_combine_with_and(db, w1, f1, f2, i1, i2, i3, mk_stock):
    """PRD-GW-18 — the two filters combine with AND.
    Rules: `get_by_workspace` R4"""
    a = mk_stock(item_id=i1.id, is_available_for_sale=True)
    mk_stock(item_id=i2.id)
    mk_stock(item_id=i3.id, factory_id=f2.id, is_available_for_sale=True)

    result = dao.get_by_workspace(db, workspace_id=w1.id, factory_id=f1.id, is_available_for_sale=True)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] PRD-GW-19
def test_prd_gw_19__two_filters_no_row_meets_together_return_an_empty_list(db, w1, f2, i1, i2, mk_stock):
    """PRD-GW-19 — two filters no row meets together return an empty list.
    Rules: `get_by_workspace` R4"""
    mk_stock(item_id=i1.id, is_available_for_sale=True)
    mk_stock(item_id=i2.id, factory_id=f2.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, factory_id=f2.id, is_available_for_sale=True)

    # Then 1
    assert result == []


# [claude] PRD-GW-20
def test_prd_gw_20__a_row_with_qty_0_is_returned(db, w1, i1, mk_stock):
    """PRD-GW-20 — a row with qty 0 is returned.
    Rules: `get_by_workspace` R4a"""
    a = mk_stock(item_id=i1.id, qty=0)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] PRD-GW-21
def test_prd_gw_21__a_row_with_a_negative_qty_is_returned(db, w1, i1, mk_stock):
    """PRD-GW-21 — a row with a negative qty is returned.
    Rules: `get_by_workspace` R4a"""
    a = mk_stock(item_id=i1.id, qty=-4)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] PRD-GW-22
def test_prd_gw_22__an_unknown_workspace_returns_an_empty_list(db, i1, mk_stock):
    """PRD-GW-22 — an unknown workspace returns an empty list.
    Rules: `get_by_workspace` R5"""
    mk_stock(item_id=i1.id)

    result = dao.get_by_workspace(db, workspace_id=MISSING)

    # Then 1
    assert result == []


# [claude] PRD-GW-23
def test_prd_gw_23__a_workspace_with_no_rows_returns_an_empty_list(db, w2, i1, mk_stock):
    """PRD-GW-23 — a workspace with no rows returns an empty list.
    Rules: `get_by_workspace` R5"""
    mk_stock(item_id=i1.id)

    result = dao.get_by_workspace(db, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] PRD-GW-24
@pytest.mark.xfail(strict=True, reason="BUG-1327: Product list shows stock of a deleted factory and of a removed item")
def test_prd_gw_24__a_row_of_a_soft_deleted_factory_is_not_returned(db, w1, fd, i1, i2, mk_stock):
    """PRD-GW-24 — a row of a soft-deleted factory is not returned.
    Rules: `get_by_workspace` R5a [BUG-1327]"""
    mk_stock(item_id=i1.id, factory_id=fd.id)
    a = mk_stock(item_id=i2.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] PRD-GW-25
@pytest.mark.xfail(strict=True, reason="BUG-1327: Product list shows stock of a deleted factory and of a removed item")
def test_prd_gw_25__asked_by_the_soft_deleted_factory_s_id_an_empty_list(db, w1, fd, i1, i2, mk_stock):
    """PRD-GW-25 — asked by the soft-deleted factory's id: an empty list.
    Rules: `get_by_workspace` R5a [BUG-1327]"""
    mk_stock(item_id=i1.id, factory_id=fd.id)
    mk_stock(item_id=i2.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, factory_id=fd.id)

    # Then 1
    assert result == []


# [claude] PRD-GW-26
@pytest.mark.xfail(strict=True, reason="BUG-1327: Product list shows stock of a deleted factory and of a removed item")
def test_prd_gw_26__a_w2_row_on_a_soft_deleted_w1_factory_is_hidden_too(db, w2, fd, i9, mk_stock):
    """PRD-GW-26 — a W2 row on a soft-deleted W1 factory is hidden too.
    Rules: `get_by_workspace` R5a [BUG-1327]"""
    mk_stock(workspace_id=w2.id, item_id=i9.id, factory_id=fd.id)

    result = dao.get_by_workspace(db, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] PRD-GW-27
@pytest.mark.xfail(strict=True, reason="BUG-1327: Product list shows stock of a deleted factory and of a removed item")
def test_prd_gw_27__a_row_of_a_soft_deleted_factory_takes_no_place_skip_2_past_the_two_liv(db, w1, fd, i1, i2, i3, mk_stock):
    """PRD-GW-27 — a row of a soft-deleted factory takes no place: skip=2 past the two live rows gives nothing.
    Rules: `get_by_workspace` R5a [BUG-1327]"""
    mk_stock(item_id=i1.id, factory_id=fd.id)
    mk_stock(item_id=i2.id)
    mk_stock(item_id=i3.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [claude] PRD-GW-28
@pytest.mark.xfail(strict=True, reason="BUG-1327: Product list shows stock of a deleted factory and of a removed item")
def test_prd_gw_28__a_row_of_a_soft_deleted_factory_takes_no_place_skip_1_leaves_one_live_(db, w1, fd, i1, i2, i3, mk_stock):
    """PRD-GW-28 — a row of a soft-deleted factory takes no place: skip=1 leaves one live row.
    Rules: `get_by_workspace` R5a [BUG-1327]"""
    x = mk_stock(item_id=i1.id, factory_id=fd.id)
    mk_stock(item_id=i2.id)
    mk_stock(item_id=i3.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert x.id not in ids(result)


# [claude] PRD-GW-29
@pytest.mark.xfail(strict=True, reason="BUG-1327: Product list shows stock of a deleted factory and of a removed item")
def test_prd_gw_29__a_row_of_a_removed_item_is_not_returned(db, w1, i2, ix, mk_stock):
    """PRD-GW-29 — a row of a removed item is not returned.
    Rules: `get_by_workspace` R5b [BUG-1327]"""
    mk_stock(item_id=ix.id)
    a = mk_stock(item_id=i2.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] PRD-GW-30
@pytest.mark.xfail(strict=True, reason="BUG-1327: Product list shows stock of a deleted factory and of a removed item")
def test_prd_gw_30__a_w2_row_of_a_removed_w1_item_is_hidden_too(db, w2, f9, ix, mk_stock):
    """PRD-GW-30 — a W2 row of a removed W1 item is hidden too.
    Rules: `get_by_workspace` R5b [BUG-1327]"""
    mk_stock(workspace_id=w2.id, item_id=ix.id, factory_id=f9.id)

    result = dao.get_by_workspace(db, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] PRD-GW-31
@pytest.mark.xfail(strict=True, reason="BUG-1327: Product list shows stock of a deleted factory and of a removed item")
def test_prd_gw_31__a_row_of_a_removed_item_takes_no_place_skip_2_past_the_two_live_rows_g(db, w1, i2, i3, ix, mk_stock):
    """PRD-GW-31 — a row of a removed item takes no place: skip=2 past the two live rows gives nothing.
    Rules: `get_by_workspace` R5b [BUG-1327]"""
    mk_stock(item_id=ix.id)
    mk_stock(item_id=i2.id)
    mk_stock(item_id=i3.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [claude] PRD-GW-32
@pytest.mark.xfail(strict=True, reason="BUG-1327: Product list shows stock of a deleted factory and of a removed item")
def test_prd_gw_32__a_row_of_a_removed_item_takes_no_place_skip_1_leaves_one_live_row(db, w1, i2, i3, ix, mk_stock):
    """PRD-GW-32 — a row of a removed item takes no place: skip=1 leaves one live row.
    Rules: `get_by_workspace` R5b [BUG-1327]"""
    x = mk_stock(item_id=ix.id)
    mk_stock(item_id=i2.id)
    mk_stock(item_id=i3.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert x.id not in ids(result)


# [claude] PRD-GW-33
def test_prd_gw_33__listing_with_a_deleted_factory_and_a_removed_item_changes_nothing(db, w1, fd, i1, ix, mk_stock, recorder):
    """PRD-GW-33 — listing with a deleted factory and a removed item changes nothing.
    Rules: `get_by_workspace` R5c"""
    x = mk_stock(item_id=i1.id, factory_id=fd.id)
    y = mk_stock(item_id=ix.id)
    before_x = snap(db, x)
    before_y = snap(db, y)
    before_fd = snap(db, fd)
    before_ix = snap(db, ix)

    recorder.start()
    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    db.expire_all()
    assert snap(db, x) == before_x
    # Then 3
    assert snap(db, y) == before_y
    # Then 4
    assert snap(db, fd) == before_fd
    # Then 5
    assert snap(db, ix) == before_ix
    # Then 6
    assert recorder.written() == []


# [claude] PRD-GW-34
def test_prd_gw_34__an_inactive_factory_hides_nothing(db, w1, fi, i1, mk_stock):
    """PRD-GW-34 — an inactive factory hides nothing.
    Rules: `get_by_workspace` R5c"""
    a = mk_stock(item_id=i1.id, factory_id=fi.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] PRD-GW-35
def test_prd_gw_35__once_the_factory_is_live_again_the_row_is_back_unchanged(db, w1, fd, i1, mk_stock):
    """PRD-GW-35 — once the factory is live again the row is back, unchanged.
    Rules: `get_by_workspace` R5c"""
    x = mk_stock(item_id=i1.id, factory_id=fd.id)
    fd.is_deleted = False
    fd.deleted_at = None
    fd.deleted_by = None
    db.flush()
    before_x = snap(db, x)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [x.id]
    # Then 2
    db.expire_all()
    assert snap(db, x) == before_x


# [claude] PRD-GW-36
def test_prd_gw_36__once_the_item_is_active_again_the_row_is_back_unchanged(db, w1, ix, mk_stock):
    """PRD-GW-36 — once the item is active again the row is back, unchanged.
    Rules: `get_by_workspace` R5c"""
    x = mk_stock(item_id=ix.id)
    ix.is_active = True
    db.flush()
    before_x = snap(db, x)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [x.id]
    # Then 2
    db.expire_all()
    assert snap(db, x) == before_x


# [claude] PRD-GW-37
@pytest.mark.xfail(strict=True, reason="BUG-1325: The product list has no sort order")
def test_prd_gw_37__the_query_orders_by_name_then_id_ascending(db, w1, i1, mk_stock, recorder):
    """PRD-GW-37 — the query orders by name, then id, ascending.
    Rules: `get_by_workspace` R6 [BUG-1325]"""
    a = mk_stock(item_id=i1.id)

    recorder.start()
    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    sql = recorder.sql()
    order_part = order_part_of(sql)
    assert "ORDER BY" in sql
    # Then 3
    assert "name" in order_part
    # Then 4
    assert "products.id" in order_part
    # Then 5
    assert order_part.index("name") < order_part.index("products.id")
    # Then 6
    assert "DESC" not in order_part.upper()
    # Then 7
    assert order_part.count(",") == 1


# [claude] PRD-GW-38
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1325: The product list has no sort order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_prd_gw_38__item_names_come_back_case_insensitively_apple_banana_zulu(db, w1, mk_item, mk_stock):
    """PRD-GW-38 — item names come back case-insensitively: "apple", "Banana", "Zulu".
    Rules: `get_by_workspace` R6 [BUG-1325]"""
    seqscan(db)
    iz = mk_item(name="Zulu")
    ia = mk_item(name="apple")
    ib = mk_item(name="Banana")
    a = mk_stock(item_id=iz.id)
    b = mk_stock(item_id=ia.id)
    c = mk_stock(item_id=ib.id)
    db.expire_all()

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [b.id, c.id, a.id]


# [claude] PRD-GW-39
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1325: The product list has no sort order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_prd_gw_39__press_and_press_tie_on_the_item_name_the_lower_row_id_comes_first_capi(db, w1, mk_item, mk_stock):
    """PRD-GW-39 — "Press" and "press" tie on the item name: the lower row id comes first, capital first.
    Rules: `get_by_workspace` R6 [BUG-1325]"""
    seqscan(db)
    ip = mk_item(name="Press", name_normalized="press one")
    iq = mk_item(name="press", name_normalized="press two")
    a = mk_stock(item_id=ip.id)
    b = mk_stock(item_id=iq.id)
    db.expire_all()

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert ids(result) == [a.id, b.id]


# [claude] PRD-GW-40
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1325: The product list has no sort order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_prd_gw_40__press_and_press_tie_on_the_item_name_the_lower_row_id_comes_first_smal(db, w1, mk_item, mk_stock):
    """PRD-GW-40 — "press" and "Press" tie on the item name: the lower row id comes first, small letter first.
    Rules: `get_by_workspace` R6 [BUG-1325]"""
    seqscan(db)
    ip = mk_item(name="press", name_normalized="press one")
    iq = mk_item(name="Press", name_normalized="press two")
    a = mk_stock(item_id=ip.id)
    b = mk_stock(item_id=iq.id)
    db.expire_all()

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert ids(result) == [a.id, b.id]


# [claude] PRD-GW-41
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1325: The product list has no sort order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_prd_gw_41__rows_of_one_item_tie_the_row_id_decides_when_factory_flag_and_qty_woul(db, w1, f1, f2, mk_stock):
    """PRD-GW-41 — rows of one item tie: the row id decides, when factory, flag and qty would each sort otherwise and the lowest id was updated.
    Rules: `get_by_workspace` R6 [BUG-1325]"""
    seqscan(db)
    a = mk_stock(factory_id=f2.id, qty=7)
    b = mk_stock(factory_id=f1.id, qty=9, is_available_for_sale=True)
    c = mk_stock(factory_id=f1.id, qty=5)
    a.qty = 8
    db.flush()
    db.expire_all()

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [a.id, b.id, c.id]


# [claude] PRD-GW-42
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1325: The product list has no sort order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_prd_gw_42__a_row_of_a_higher_item_id_with_an_earlier_name_comes_first_item_id_is_(db, w1, i1, i2, i3, mk_stock):
    """PRD-GW-42 — a row of a higher item id with an earlier name comes first: item id is not the key.
    Rules: `get_by_workspace` R6 [BUG-1325]"""
    seqscan(db)
    a = mk_stock(item_id=i3.id)
    b = mk_stock(item_id=i1.id)
    c = mk_stock(item_id=i2.id)
    db.expire_all()

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [b.id, c.id, a.id]


# [claude] PRD-GW-43
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1325: The product list has no sort order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_prd_gw_43__the_order_is_applied_before_the_page_is_cut(db, w1, mk_item, mk_stock):
    """PRD-GW-43 — the order is applied before the page is cut.
    Rules: `get_by_workspace` R6 [BUG-1325]"""
    seqscan(db)
    iz = mk_item(name="Zulu")
    ia = mk_item(name="apple")
    ib = mk_item(name="Banana")
    mk_stock(item_id=iz.id)
    mk_stock(item_id=ia.id)
    c = mk_stock(item_id=ib.id)
    db.expire_all()

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert ids(result) == [c.id]


# [claude] PRD-GW-44
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1325: The product list has no sort order "
    "(non-strict: the rows have no fixed order; which row is on which page rests on physical row order)",
)
def test_prd_gw_44__rows_paged_one_at_a_time_neither_repeat_nor_miss_a_row(db, w1, i1, i2, i3, i4, i5, mk_stock):
    """PRD-GW-44 — rows paged one at a time neither repeat nor miss a row.
    Rules: `get_by_workspace` R6 [BUG-1325], R7"""
    seqscan(db)
    a = mk_stock(item_id=i3.id)
    b = mk_stock(item_id=i1.id)
    c = mk_stock(item_id=i2.id)
    d = mk_stock(item_id=i5.id)
    e = mk_stock(item_id=i4.id)
    b.qty = 8
    db.flush()
    db.expire_all()

    pages = [dao.get_by_workspace(db, workspace_id=w1.id, skip=k, limit=1) for k in range(5)]

    # Then 1
    assert [len(p) for p in pages] == [1, 1, 1, 1, 1]
    # Then 2
    assert [p[0].id for p in pages] == [b.id, c.id, a.id, e.id, d.id]


# [claude] PRD-GW-45
def test_prd_gw_45__with_the_defaults_101_rows_give_100(db, w1, new_item, new_stock):
    """PRD-GW-45 — with the defaults 101 rows give 100.
    Rules: `get_by_workspace` R7"""
    items = [new_item(name=f"Item {k:03d}") for k in range(1, 102)]
    add_many(db, items)
    rows = [new_stock(item_id=items[k - 1].id) for k in range(1, 102)]
    add_many(db, rows)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert len(set(ids(result))) == 100


# [claude] PRD-GW-46
def test_prd_gw_46__limit_1000_gives_all_101(db, w1, new_item, new_stock):
    """PRD-GW-46 — limit=1000 gives all 101.
    Rules: `get_by_workspace` R7"""
    items = [new_item(name=f"Item {k:03d}") for k in range(1, 102)]
    add_many(db, items)
    rows = [new_stock(item_id=items[k - 1].id) for k in range(1, 102)]
    add_many(db, rows)
    newest = [row.id for row in rows]

    result = dao.get_by_workspace(db, workspace_id=w1.id, limit=1000)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert sorted(ids(result)) == sorted(newest)


# [claude] PRD-GW-47
def test_prd_gw_47__skip_and_limit_cut_one_row_from_the_middle(db, w1, i1, i2, i3, mk_stock):
    """PRD-GW-47 — skip and limit cut one row from the middle.
    Rules: `get_by_workspace` R7"""
    mk_stock(item_id=i1.id)
    mk_stock(item_id=i2.id)
    mk_stock(item_id=i3.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert len(result) == 1


# [claude] PRD-GW-48
def test_prd_gw_48__limit_0_returns_an_empty_list(db, w1, i1, i2, mk_stock):
    """PRD-GW-48 — limit=0 returns an empty list.
    Rules: `get_by_workspace` R5"""
    mk_stock(item_id=i1.id)
    mk_stock(item_id=i2.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [claude] PRD-GW-49
def test_prd_gw_49__limit_1_returns_one_row(db, w1, i1, i2, mk_stock):
    """PRD-GW-49 — limit=1 returns one row.
    Rules: `get_by_workspace` R5"""
    mk_stock(item_id=i1.id)
    mk_stock(item_id=i2.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, limit=1)

    # Then 1
    assert len(result) == 1


# [claude] PRD-GW-50
def test_prd_gw_50__skip_at_the_number_of_rows_returns_an_empty_list(db, w1, i1, i2, mk_stock):
    """PRD-GW-50 — skip at the number of rows returns an empty list.
    Rules: `get_by_workspace` R5"""
    mk_stock(item_id=i1.id)
    mk_stock(item_id=i2.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [claude] PRD-GW-51
def test_prd_gw_51__skip_at_the_last_row_returns_one_row(db, w1, i1, i2, mk_stock):
    """PRD-GW-51 — skip at the last row returns one row.
    Rules: `get_by_workspace` R5"""
    mk_stock(item_id=i1.id)
    mk_stock(item_id=i2.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=1)

    # Then 1
    assert len(result) == 1


# [claude] PRD-GW-52
def test_prd_gw_52__a_negative_limit_raises(db, w1, i1, i2, mk_stock):
    """PRD-GW-52 — a negative limit raises.
    Rules: `get_by_workspace` R8, Errors row 1"""
    mk_stock(item_id=i1.id)
    mk_stock(item_id=i2.id)
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


# [claude] PRD-GW-53
def test_prd_gw_53__a_negative_skip_raises(db, w1, i1, i2, mk_stock):
    """PRD-GW-53 — a negative skip raises.
    Rules: `get_by_workspace` R8, Errors row 2"""
    mk_stock(item_id=i1.id)
    mk_stock(item_id=i2.id)
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


# [claude] PRD-GW-54
def test_prd_gw_54__each_row_carries_its_item_s_name_and_unit_with_no_further_query(db, w1, i2, mk_stock, recorder):
    """PRD-GW-54 — each row carries its item's name and unit, with no further query.
    Rules: `get_by_workspace` R9"""
    mk_stock(item_id=i2.id)
    w = w1.id
    db.expire_all()

    recorder.start()
    result = dao.get_by_workspace(db, workspace_id=w)

    # Then 1
    assert result[0].item_name == "Cam"
    # Then 2
    assert result[0].item_unit == "pcs"
    # Then 3
    selects = recorder.selects()
    assert len(selects) == 1


# [claude] PRD-GW-55
def test_prd_gw_55__writes_nothing_a_pending_row_that_would_sort_first_stays_pending_and_i(db, w1, f2, i2, i5, mk_stock, recorder):
    """PRD-GW-55 — writes nothing: a pending row that would sort first stays pending and is not returned.
    Rules: `get_by_workspace` Side effects"""
    a = mk_stock(item_id=i2.id)
    p = Product(workspace_id=w1.id, item_id=i5.id, factory_id=f2.id, qty=1)
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


# [claude] PRD-GW-56
def test_prd_gw_56__writes_nothing_a_read_leaves_the_caller_s_unflushed_edit_alone(db, w1, i1, i2, mk_stock):
    """PRD-GW-56 — writes nothing: a read leaves the caller's unflushed edit alone.
    Rules: `get_by_workspace` Side effects"""
    a = mk_stock(item_id=i1.id)
    b = mk_stock(item_id=i2.id)
    b.note = "Edited"

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert b.note == "Edited"


# [claude] PRD-GW-57
def test_prd_gw_57__another_workspace_s_row_takes_no_place_in_the_page_whatever_the_row_or(db, w1, w2, f9, i4, i5, i9, mk_stock):
    """PRD-GW-57 — another workspace's row takes no place in the page, whatever the row order.
    Rules: `get_by_workspace` R1"""
    z = mk_stock(workspace_id=w2.id, item_id=i9.id, factory_id=f9.id)
    a = mk_stock(item_id=i4.id)
    b = mk_stock(item_id=i5.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, limit=2)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 3
    assert z.id not in ids(result)


# --------------------------------------------------------------------------- #
# ProductDAO.get_by_id_and_workspace
# --------------------------------------------------------------------------- #


# [claude] PRD-GI-01
def test_prd_gi_01__returns_the_row_with_that_id(db, w1, f1, i1, i2, mk_stock):
    """PRD-GI-01 — returns the row with that id.
    Rules: `get_by_id_and_workspace` R1, Returns"""
    mk_stock(item_id=i2.id)
    a = mk_stock(item_id=i1.id)

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, Product)
    # Then 2
    assert result.id == a.id
    # Then 3
    assert result.workspace_id == w1.id
    assert result.item_id == i1.id
    assert result.factory_id == f1.id
    assert result.qty == 5


# [claude] PRD-GI-02
def test_prd_gi_02__another_workspace_s_id_returns_none_when_that_row_is_the_later_one(db, w1, w2, f9, i1, i9, mk_stock):
    """PRD-GI-02 — another workspace's id returns None, when that row is the later one.
    Rules: `get_by_id_and_workspace` R2"""
    mk_stock(item_id=i1.id)
    z = mk_stock(workspace_id=w2.id, item_id=i9.id, factory_id=f9.id)

    result = dao.get_by_id_and_workspace(db, id=z.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] PRD-GI-03
def test_prd_gi_03__another_workspace_s_id_returns_none_when_that_row_is_the_earlier_one(db, w1, w2, f9, i1, i9, mk_stock):
    """PRD-GI-03 — another workspace's id returns None, when that row is the earlier one.
    Rules: `get_by_id_and_workspace` R2"""
    z = mk_stock(workspace_id=w2.id, item_id=i9.id, factory_id=f9.id)
    mk_stock(item_id=i1.id)

    result = dao.get_by_id_and_workspace(db, id=z.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] PRD-GI-04
def test_prd_gi_04__the_id_under_another_workspace_returns_none(db, w2, i1, mk_stock):
    """PRD-GI-04 — the id under another workspace returns None.
    Rules: `get_by_id_and_workspace` R2"""
    a = mk_stock(item_id=i1.id)

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w2.id)

    # Then 1
    assert result is None


# [claude] PRD-GI-05
def test_prd_gi_05__an_unknown_id_returns_none(db, w1, i1, mk_stock):
    """PRD-GI-05 — an unknown id returns None.
    Rules: `get_by_id_and_workspace` R3"""
    mk_stock(item_id=i1.id)

    result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] PRD-GI-06
def test_prd_gi_06__id_0_returns_none(db, w1, i1, mk_stock):
    """PRD-GI-06 — id=0 returns None.
    Rules: `get_by_id_and_workspace` R3"""
    mk_stock(item_id=i1.id)

    result = dao.get_by_id_and_workspace(db, id=0, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] PRD-GI-07
def test_prd_gi_07__writes_nothing_a_read_that_finds_nothing_leaves_the_session_as_it_was(db, w1, f2, i1, i5, mk_stock, recorder):
    """PRD-GI-07 — writes nothing: a read that finds nothing leaves the session as it was.
    Rules: `get_by_id_and_workspace` R3, Side effects"""
    a = mk_stock(item_id=i1.id)
    p = Product(workspace_id=w1.id, item_id=i5.id, factory_id=f2.id, qty=1)
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    recorder.start()
    result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result is None
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


# [claude] PRD-GI-08
def test_prd_gi_08__writes_nothing_a_read_that_finds_its_row_leaves_the_session_as_it_was(db, w1, f2, i1, i5, mk_stock, recorder):
    """PRD-GI-08 — writes nothing: a read that finds its row leaves the session as it was.
    Rules: `get_by_id_and_workspace` Side effects"""
    a = mk_stock(item_id=i1.id)
    p = Product(workspace_id=w1.id, item_id=i5.id, factory_id=f2.id, qty=1)
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    recorder.start()
    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
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


# [claude] PRD-GI-09
def test_prd_gi_09__writes_nothing_a_read_leaves_the_caller_s_unflushed_edit_alone(db, w1, i1, i2, mk_stock):
    """PRD-GI-09 — writes nothing: a read leaves the caller's unflushed edit alone.
    Rules: `get_by_id_and_workspace` Side effects"""
    a = mk_stock(item_id=i1.id)
    b = mk_stock(item_id=i2.id)
    b.note = "Edited"

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert b.note == "Edited"


# [claude] PRD-GI-10
def test_prd_gi_10__a_soft_deleted_row_is_returned(db, w1, u1, i1, mk_stock):
    """PRD-GI-10 — a soft-deleted row is returned.
    Rules: `get_by_id_and_workspace` R4"""
    a = mk_stock(item_id=i1.id, is_active=False, is_deleted=True, deleted_at=T0, deleted_by=u1.id)

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.is_deleted is True


# [claude] PRD-GI-11
def test_prd_gi_11__a_row_of_a_soft_deleted_factory_is_returned(db, w1, fd, i1, mk_stock):
    """PRD-GI-11 — a row of a soft-deleted factory is returned.
    Rules: `get_by_id_and_workspace` R4"""
    a = mk_stock(item_id=i1.id, factory_id=fd.id)

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id


# [claude] PRD-GI-12
def test_prd_gi_12__a_row_of_a_removed_item_is_returned(db, w1, ix, mk_stock):
    """PRD-GI-12 — a row of a removed item is returned.
    Rules: `get_by_id_and_workspace` R4"""
    a = mk_stock(item_id=ix.id)

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id


# [claude] PRD-GI-13
def test_prd_gi_13__the_query_does_not_read_the_parent_tables(db, w1, i1, mk_stock, recorder):
    """PRD-GI-13 — the query does not read the parent tables.
    Rules: `get_by_id_and_workspace` R4"""
    a = mk_stock(item_id=i1.id)

    recorder.start()
    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    sql = recorder.sql()
    assert "factories" not in sql


# --------------------------------------------------------------------------- #
# ProductDAO.get_by_factory_item_available
# --------------------------------------------------------------------------- #


# [claude] PRD-GK-01
def test_prd_gk_01__returns_the_row_with_that_key(db, w1, f1, i1, i2, mk_stock):
    """PRD-GK-01 — returns the row with that key.
    Rules: `get_by_factory_item_available` R1, Returns"""
    mk_stock(item_id=i2.id)
    a = mk_stock()

    result = dao.get_by_factory_item_available(db, factory_id=f1.id, item_id=i1.id, is_available_for_sale=False, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, Product)
    # Then 2
    assert result.id == a.id
    # Then 3
    assert result.qty == 5


# [claude] PRD-GK-02
def test_prd_gk_02__the_not_for_sale_row_is_told_from_the_for_sale_row(db, w1, f1, i1, mk_stock):
    """PRD-GK-02 — the not-for-sale row is told from the for-sale row.
    Rules: `get_by_factory_item_available` R1"""
    mk_stock(is_available_for_sale=True)
    a = mk_stock()

    result = dao.get_by_factory_item_available(db, factory_id=f1.id, item_id=i1.id, is_available_for_sale=False, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id


# [claude] PRD-GK-03
def test_prd_gk_03__the_for_sale_row_is_told_from_the_not_for_sale_row(db, w1, f1, i1, mk_stock):
    """PRD-GK-03 — the for-sale row is told from the not-for-sale row.
    Rules: `get_by_factory_item_available` R1"""
    mk_stock()
    b = mk_stock(is_available_for_sale=True)

    result = dao.get_by_factory_item_available(db, factory_id=f1.id, item_id=i1.id, is_available_for_sale=True, workspace_id=w1.id)

    # Then 1
    assert result.id == b.id


# [claude] PRD-GK-04
def test_prd_gk_04__another_factory_is_not_matched(db, w1, f2, i1, mk_stock):
    """PRD-GK-04 — another factory is not matched.
    Rules: `get_by_factory_item_available` R2"""
    mk_stock()

    result = dao.get_by_factory_item_available(db, factory_id=f2.id, item_id=i1.id, is_available_for_sale=False, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] PRD-GK-05
def test_prd_gk_05__another_item_is_not_matched(db, w1, f1, i2, mk_stock):
    """PRD-GK-05 — another item is not matched.
    Rules: `get_by_factory_item_available` R2"""
    mk_stock()

    result = dao.get_by_factory_item_available(db, factory_id=f1.id, item_id=i2.id, is_available_for_sale=False, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] PRD-GK-06
def test_prd_gk_06__another_sale_state_is_not_matched(db, w1, f1, i1, mk_stock):
    """PRD-GK-06 — another sale state is not matched.
    Rules: `get_by_factory_item_available` R2"""
    mk_stock()

    result = dao.get_by_factory_item_available(db, factory_id=f1.id, item_id=i1.id, is_available_for_sale=True, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] PRD-GK-07
def test_prd_gk_07__is_available_for_sale_false_is_matched_as_a_value(db, w1, f1, i1, mk_stock):
    """PRD-GK-07 — is_available_for_sale=False is matched as a value.
    Rules: `get_by_factory_item_available` R2"""
    mk_stock(is_available_for_sale=True)

    result = dao.get_by_factory_item_available(db, factory_id=f1.id, item_id=i1.id, is_available_for_sale=False, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] PRD-GK-08
def test_prd_gk_08__another_workspace_is_not_matched(db, w2, f1, i1, mk_stock):
    """PRD-GK-08 — another workspace is not matched.
    Rules: `get_by_factory_item_available` R2"""
    mk_stock()

    result = dao.get_by_factory_item_available(db, factory_id=f1.id, item_id=i1.id, is_available_for_sale=False, workspace_id=w2.id)

    # Then 1
    assert result is None


# [claude] PRD-GK-09
def test_prd_gk_09__a_w2_row_of_that_key_is_not_matched_when_it_is_the_earlier_one(db, w1, w2, f1, i1, mk_stock):
    """PRD-GK-09 — a W2 row of that key is not matched, when it is the earlier one.
    Rules: `get_by_factory_item_available` R2"""
    mk_stock(workspace_id=w2.id)

    result = dao.get_by_factory_item_available(db, factory_id=f1.id, item_id=i1.id, is_available_for_sale=False, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] PRD-GK-10
def test_prd_gk_10__a_w2_row_of_that_key_is_not_picked_over_the_w1_row_when_it_is_the_earl(db, w1, w2, f1, i1, mk_stock):
    """PRD-GK-10 — a W2 row of that key is not picked over the W1 row, when it is the earlier one.
    Rules: `get_by_factory_item_available` R2"""
    mk_stock(workspace_id=w2.id)
    a = mk_stock()

    result = dao.get_by_factory_item_available(db, factory_id=f1.id, item_id=i1.id, is_available_for_sale=False, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id


# [claude] PRD-GK-11
def test_prd_gk_11__the_w2_row_of_that_key_answers_w2_when_it_is_the_later_one(db, w2, f1, i1, mk_stock):
    """PRD-GK-11 — the W2 row of that key answers W2, when it is the later one.
    Rules: `get_by_factory_item_available` R2"""
    mk_stock()
    z = mk_stock(workspace_id=w2.id)

    result = dao.get_by_factory_item_available(db, factory_id=f1.id, item_id=i1.id, is_available_for_sale=False, workspace_id=w2.id)

    # Then 1
    assert result.id == z.id


# [claude] PRD-GK-12
def test_prd_gk_12__factory_id_0_returns_none(db, w1, i1, mk_stock):
    """PRD-GK-12 — factory_id=0 returns None.
    Rules: `get_by_factory_item_available` R2"""
    mk_stock()

    result = dao.get_by_factory_item_available(db, factory_id=0, item_id=i1.id, is_available_for_sale=False, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] PRD-GK-13
def test_prd_gk_13__an_unknown_item_returns_none_and_creates_no_row(db, w1, f1, mk_stock):
    """PRD-GK-13 — an unknown item returns None and creates no row.
    Rules: `get_by_factory_item_available` R2"""
    mk_stock()

    result = dao.get_by_factory_item_available(db, factory_id=f1.id, item_id=MISSING, is_available_for_sale=False, workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, Product) == 1


# [claude] PRD-GK-14
def test_prd_gk_14__a_soft_deleted_row_is_not_found_although_it_holds_the_key(db, w1, u1, f1, i1, mk_stock):
    """PRD-GK-14 — a soft-deleted row is not found, although it holds the key.
    Rules: `get_by_factory_item_available` R3"""
    mk_stock(is_active=False, is_deleted=True, deleted_at=T0, deleted_by=u1.id)

    result = dao.get_by_factory_item_available(db, factory_id=f1.id, item_id=i1.id, is_available_for_sale=False, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] PRD-GK-15
def test_prd_gk_15__a_soft_deleted_for_sale_row_does_not_hide_the_live_not_for_sale_row(db, w1, u1, f1, i1, mk_stock):
    """PRD-GK-15 — a soft-deleted for-sale row does not hide the live not-for-sale row.
    Rules: `get_by_factory_item_available` R3"""
    mk_stock(is_available_for_sale=True, is_active=False, is_deleted=True, deleted_at=T0, deleted_by=u1.id)
    a = mk_stock()

    result = dao.get_by_factory_item_available(db, factory_id=f1.id, item_id=i1.id, is_available_for_sale=False, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id


# [claude] PRD-GK-16
def test_prd_gk_16__a_row_of_a_soft_deleted_factory_is_found(db, w1, fd, i1, mk_stock):
    """PRD-GK-16 — a row of a soft-deleted factory is found.
    Rules: `get_by_factory_item_available` R4"""
    a = mk_stock(factory_id=fd.id)

    result = dao.get_by_factory_item_available(db, factory_id=fd.id, item_id=i1.id, is_available_for_sale=False, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id


# [claude] PRD-GK-17
def test_prd_gk_17__a_row_of_a_removed_item_is_found(db, w1, f1, ix, mk_stock):
    """PRD-GK-17 — a row of a removed item is found.
    Rules: `get_by_factory_item_available` R4"""
    a = mk_stock(item_id=ix.id)

    result = dao.get_by_factory_item_available(db, factory_id=f1.id, item_id=ix.id, is_available_for_sale=False, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id


# [claude] PRD-GK-18
def test_prd_gk_18__the_query_does_not_read_the_factory(db, w1, f1, i1, mk_stock, recorder):
    """PRD-GK-18 — the query does not read the factory.
    Rules: `get_by_factory_item_available` R4"""
    a = mk_stock()

    recorder.start()
    result = dao.get_by_factory_item_available(db, factory_id=f1.id, item_id=i1.id, is_available_for_sale=False, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    sql = recorder.sql()
    assert "factories" not in sql


# [claude] PRD-GK-19
def test_prd_gk_19__a_row_with_is_active_false_is_deleted_false_is_found(db, w1, f1, i1, mk_stock):
    """PRD-GK-19 — a row with is_active False, is_deleted False is found.
    Rules: `get_by_factory_item_available` R5"""
    a = mk_stock(is_active=False)

    result = dao.get_by_factory_item_available(db, factory_id=f1.id, item_id=i1.id, is_available_for_sale=False, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id


# [claude] PRD-GK-20
def test_prd_gk_20__writes_nothing_a_pending_row_of_that_key_stays_pending_and_is_not_retu(db, w1, f1, i1, i2, mk_stock, recorder):
    """PRD-GK-20 — writes nothing: a pending row of that key stays pending and is not returned.
    Rules: `get_by_factory_item_available` Side effects"""
    a = mk_stock(item_id=i2.id)
    p = Product(workspace_id=w1.id, item_id=i1.id, factory_id=f1.id, qty=1)
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    recorder.start()
    result = dao.get_by_factory_item_available(db, factory_id=f1.id, item_id=i1.id, is_available_for_sale=False, workspace_id=w1.id)

    # Then 1
    assert result is None
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


# [claude] PRD-GK-21
def test_prd_gk_21__writes_nothing_a_read_leaves_the_caller_s_unflushed_edit_alone(db, w1, f1, i1, i2, mk_stock):
    """PRD-GK-21 — writes nothing: a read leaves the caller's unflushed edit alone.
    Rules: `get_by_factory_item_available` Side effects"""
    a = mk_stock()
    b = mk_stock(item_id=i2.id)
    b.note = "Edited"

    result = dao.get_by_factory_item_available(db, factory_id=f1.id, item_id=i1.id, is_available_for_sale=False, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert b.note == "Edited"


# --------------------------------------------------------------------------- #
# ProductDAO._get_any_by_factory_item_available
# --------------------------------------------------------------------------- #


# [claude] PRD-GA-01
@pytest.mark.xfail(strict=True, raises=AttributeError, reason="BUG-1336: After a product row is soft-deleted, its key cannot be used again")
def test_prd_ga_01__returns_a_live_row_with_that_key(db, w1, f1, i1, i2, mk_stock):
    """PRD-GA-01 — returns a live row with that key.
    Rules: `_get_any_by_factory_item_available` R1 [BUG-1336], Returns"""
    mk_stock(item_id=i2.id)
    a = mk_stock()

    result = dao._get_any_by_factory_item_available(db, factory_id=f1.id, item_id=i1.id, is_available_for_sale=False, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, Product)
    # Then 2
    assert result.id == a.id


# [claude] PRD-GA-02
@pytest.mark.xfail(strict=True, raises=AttributeError, reason="BUG-1336: After a product row is soft-deleted, its key cannot be used again")
def test_prd_ga_02__returns_a_soft_deleted_row_with_that_key_with_its_qty(db, w1, u1, f1, i1, mk_stock):
    """PRD-GA-02 — returns a soft-deleted row with that key, with its qty.
    Rules: `_get_any_by_factory_item_available` R1 [BUG-1336]"""
    a = mk_stock(qty=5, is_active=False, is_deleted=True, deleted_at=T0, deleted_by=u1.id)

    result = dao._get_any_by_factory_item_available(db, factory_id=f1.id, item_id=i1.id, is_available_for_sale=False, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.is_deleted is True
    # Then 3
    assert result.qty == 5


# [claude] PRD-GA-03
@pytest.mark.xfail(strict=True, raises=AttributeError, reason="BUG-1336: After a product row is soft-deleted, its key cannot be used again")
def test_prd_ga_03__the_not_for_sale_row_is_told_from_the_for_sale_row(db, w1, f1, i1, mk_stock):
    """PRD-GA-03 — the not-for-sale row is told from the for-sale row.
    Rules: `_get_any_by_factory_item_available` R1 [BUG-1336]"""
    mk_stock(is_available_for_sale=True)
    a = mk_stock()

    result = dao._get_any_by_factory_item_available(db, factory_id=f1.id, item_id=i1.id, is_available_for_sale=False, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id


# [claude] PRD-GA-04
@pytest.mark.xfail(strict=True, raises=AttributeError, reason="BUG-1336: After a product row is soft-deleted, its key cannot be used again")
def test_prd_ga_04__the_for_sale_row_is_told_from_the_not_for_sale_row_deleted(db, w1, u1, f1, i1, mk_stock):
    """PRD-GA-04 — the for-sale row is told from the not-for-sale row, deleted.
    Rules: `_get_any_by_factory_item_available` R1 [BUG-1336]"""
    mk_stock()
    b = mk_stock(is_available_for_sale=True, is_active=False, is_deleted=True, deleted_at=T0, deleted_by=u1.id)

    result = dao._get_any_by_factory_item_available(db, factory_id=f1.id, item_id=i1.id, is_available_for_sale=True, workspace_id=w1.id)

    # Then 1
    assert result.id == b.id


# [claude] PRD-GA-05
@pytest.mark.xfail(strict=True, raises=AttributeError, reason="BUG-1336: After a product row is soft-deleted, its key cannot be used again")
def test_prd_ga_05__a_row_of_a_soft_deleted_factory_is_found(db, w1, fd, i1, mk_stock):
    """PRD-GA-05 — a row of a soft-deleted factory is found.
    Rules: `_get_any_by_factory_item_available` R1 [BUG-1336]"""
    a = mk_stock(factory_id=fd.id)

    result = dao._get_any_by_factory_item_available(db, factory_id=fd.id, item_id=i1.id, is_available_for_sale=False, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id


# [claude] PRD-GA-06
@pytest.mark.xfail(strict=True, raises=AttributeError, reason="BUG-1336: After a product row is soft-deleted, its key cannot be used again")
def test_prd_ga_06__a_row_of_a_removed_item_is_found(db, w1, f1, ix, mk_stock):
    """PRD-GA-06 — a row of a removed item is found.
    Rules: `_get_any_by_factory_item_available` R1 [BUG-1336]"""
    a = mk_stock(item_id=ix.id)

    result = dao._get_any_by_factory_item_available(db, factory_id=f1.id, item_id=ix.id, is_available_for_sale=False, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id


# [claude] PRD-GA-07
@pytest.mark.xfail(strict=True, raises=AttributeError, reason="BUG-1336: After a product row is soft-deleted, its key cannot be used again")
def test_prd_ga_07__another_factory_is_not_matched(db, w1, u1, f2, i1, mk_stock):
    """PRD-GA-07 — another factory is not matched.
    Rules: `_get_any_by_factory_item_available` R2 [BUG-1336]"""
    mk_stock(is_active=False, is_deleted=True, deleted_at=T0, deleted_by=u1.id)

    result = dao._get_any_by_factory_item_available(db, factory_id=f2.id, item_id=i1.id, is_available_for_sale=False, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] PRD-GA-08
@pytest.mark.xfail(strict=True, raises=AttributeError, reason="BUG-1336: After a product row is soft-deleted, its key cannot be used again")
def test_prd_ga_08__another_item_is_not_matched(db, w1, u1, f1, i2, mk_stock):
    """PRD-GA-08 — another item is not matched.
    Rules: `_get_any_by_factory_item_available` R2 [BUG-1336]"""
    mk_stock(is_active=False, is_deleted=True, deleted_at=T0, deleted_by=u1.id)

    result = dao._get_any_by_factory_item_available(db, factory_id=f1.id, item_id=i2.id, is_available_for_sale=False, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] PRD-GA-09
@pytest.mark.xfail(strict=True, raises=AttributeError, reason="BUG-1336: After a product row is soft-deleted, its key cannot be used again")
def test_prd_ga_09__another_sale_state_is_not_matched(db, w1, u1, f1, i1, mk_stock):
    """PRD-GA-09 — another sale state is not matched.
    Rules: `_get_any_by_factory_item_available` R2 [BUG-1336]"""
    mk_stock(is_active=False, is_deleted=True, deleted_at=T0, deleted_by=u1.id)

    result = dao._get_any_by_factory_item_available(db, factory_id=f1.id, item_id=i1.id, is_available_for_sale=True, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] PRD-GA-10
@pytest.mark.xfail(strict=True, raises=AttributeError, reason="BUG-1336: After a product row is soft-deleted, its key cannot be used again")
def test_prd_ga_10__another_workspace_is_not_matched(db, w2, u1, f1, i1, mk_stock):
    """PRD-GA-10 — another workspace is not matched.
    Rules: `_get_any_by_factory_item_available` R2 [BUG-1336]"""
    mk_stock(is_active=False, is_deleted=True, deleted_at=T0, deleted_by=u1.id)

    result = dao._get_any_by_factory_item_available(db, factory_id=f1.id, item_id=i1.id, is_available_for_sale=False, workspace_id=w2.id)

    # Then 1
    assert result is None


# [claude] PRD-GA-11
@pytest.mark.xfail(strict=True, raises=AttributeError, reason="BUG-1336: After a product row is soft-deleted, its key cannot be used again")
def test_prd_ga_11__factory_id_0_returns_none(db, w1, u1, i1, mk_stock):
    """PRD-GA-11 — factory_id=0 returns None.
    Rules: `_get_any_by_factory_item_available` R2 [BUG-1336]"""
    mk_stock(is_active=False, is_deleted=True, deleted_at=T0, deleted_by=u1.id)

    result = dao._get_any_by_factory_item_available(db, factory_id=0, item_id=i1.id, is_available_for_sale=False, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] PRD-GA-12
@pytest.mark.xfail(strict=True, raises=AttributeError, reason="BUG-1336: After a product row is soft-deleted, its key cannot be used again")
def test_prd_ga_12__a_w2_row_of_that_key_is_not_matched_when_it_is_the_earlier_one(db, w1, w2, f1, i1, mk_stock):
    """PRD-GA-12 — a W2 row of that key is not matched, when it is the earlier one.
    Rules: `_get_any_by_factory_item_available` R2 [BUG-1336]"""
    mk_stock(workspace_id=w2.id)
    a = mk_stock()

    result = dao._get_any_by_factory_item_available(db, factory_id=f1.id, item_id=i1.id, is_available_for_sale=False, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id


# [claude] PRD-GA-13
@pytest.mark.xfail(strict=True, raises=AttributeError, reason="BUG-1336: After a product row is soft-deleted, its key cannot be used again")
def test_prd_ga_13__no_match_returns_none_and_creates_no_row(db, w1, f1, mk_stock):
    """PRD-GA-13 — no match returns None and creates no row.
    Rules: `_get_any_by_factory_item_available` R2 [BUG-1336]"""
    mk_stock()

    result = dao._get_any_by_factory_item_available(db, factory_id=f1.id, item_id=MISSING, is_available_for_sale=False, workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, Product) == 1


# [claude] PRD-GA-14
@pytest.mark.xfail(strict=True, raises=AttributeError, reason="BUG-1336: After a product row is soft-deleted, its key cannot be used again")
def test_prd_ga_14__a_soft_deleted_row_stays_soft_deleted(db, w1, u1, f1, i1, mk_stock, recorder):
    """PRD-GA-14 — a soft-deleted row stays soft-deleted.
    Rules: `_get_any_by_factory_item_available` R3 [BUG-1336]"""
    a = mk_stock(is_active=False, is_deleted=True, deleted_at=T0, deleted_by=u1.id)
    before_a = snap(db, a)

    recorder.start()
    result = dao._get_any_by_factory_item_available(db, factory_id=f1.id, item_id=i1.id, is_available_for_sale=False, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    db.expire_all()
    assert snap(db, a) == before_a
    # Then 3
    assert recorder.written() == []


# [claude] PRD-GA-15
@pytest.mark.xfail(strict=True, raises=AttributeError, reason="BUG-1336: After a product row is soft-deleted, its key cannot be used again")
def test_prd_ga_15__writes_nothing_a_pending_row_of_that_key_stays_pending_and_is_not_retu(db, w1, f1, i1, i2, mk_stock, recorder):
    """PRD-GA-15 — writes nothing: a pending row of that key stays pending and is not returned.
    Rules: `_get_any_by_factory_item_available` R3 [BUG-1336], Side effects"""
    a = mk_stock(item_id=i2.id)
    p = Product(workspace_id=w1.id, item_id=i1.id, factory_id=f1.id, qty=1)
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    recorder.start()
    result = dao._get_any_by_factory_item_available(db, factory_id=f1.id, item_id=i1.id, is_available_for_sale=False, workspace_id=w1.id)

    # Then 1
    assert result is None
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


# [claude] PRD-GA-16
@pytest.mark.xfail(strict=True, raises=AttributeError, reason="BUG-1336: After a product row is soft-deleted, its key cannot be used again")
def test_prd_ga_16__writes_nothing_a_read_leaves_the_caller_s_unflushed_edit_alone(db, w1, f1, i1, i2, mk_stock):
    """PRD-GA-16 — writes nothing: a read leaves the caller's unflushed edit alone.
    Rules: `_get_any_by_factory_item_available` R3 [BUG-1336], Side effects"""
    a = mk_stock()
    b = mk_stock(item_id=i2.id)
    b.note = "Edited"

    result = dao._get_any_by_factory_item_available(db, factory_id=f1.id, item_id=i1.id, is_available_for_sale=False, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert b.note == "Edited"


# [claude] PRD-GA-17
@pytest.mark.xfail(strict=True, raises=AttributeError, reason="BUG-1336: After a product row is soft-deleted, its key cannot be used again")
def test_prd_ga_17__a_w2_row_is_not_found_for_w1_even_soft_deleted(db, w1, w2, u1, f9, i9, mk_stock):
    """PRD-GA-17 — a W2 row is not found for W1, even soft-deleted.
    Rules: `_get_any_by_factory_item_available` R2 [BUG-1336]"""
    mk_stock(workspace_id=w2.id, factory_id=f9.id, item_id=i9.id, is_active=False, is_deleted=True, deleted_at=T0, deleted_by=u1.id)

    result = dao._get_any_by_factory_item_available(db, factory_id=f9.id, item_id=i9.id, is_available_for_sale=False, workspace_id=w1.id)

    # Then 1
    assert result is None


# --------------------------------------------------------------------------- #
# ProductDAO.get_by_item
# --------------------------------------------------------------------------- #


# [claude] PRD-GT-01
def test_prd_gt_01__returns_a_list_of_the_item_s_rows_for_sale_or_not(db, w1, f2, i1, mk_stock):
    """PRD-GT-01 — returns a list of the item's rows, for sale or not.
    Rules: `get_by_item` R1, Returns"""
    a = mk_stock()
    b = mk_stock(is_available_for_sale=True)
    c = mk_stock(factory_id=f2.id)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert sorted(ids(result)) == [a.id, b.id, c.id]
    # Then 3
    assert isinstance(result[0], Product)


# [claude] PRD-GT-02
def test_prd_gt_02__rows_are_returned_whatever_their_quantities(db, w1, i1, mk_stock):
    """PRD-GT-02 — rows are returned whatever their quantities.
    Rules: `get_by_item` R1"""
    a = mk_stock(qty=0)
    b = mk_stock(is_available_for_sale=True, qty=-4)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]


# [claude] PRD-GT-03
def test_prd_gt_03__a_row_of_another_item_is_not_returned(db, w1, i1, i2, mk_stock):
    """PRD-GT-03 — a row of another item is not returned.
    Rules: `get_by_item` R1"""
    mk_stock(item_id=i2.id)
    a = mk_stock()

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] PRD-GT-04
def test_prd_gt_04__the_right_item_under_another_workspace_returns_an_empty_list(db, w2, i1, mk_stock):
    """PRD-GT-04 — the right item under another workspace returns an empty list.
    Rules: `get_by_item` R1"""
    mk_stock()

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] PRD-GT-05
def test_prd_gt_05__a_w2_row_of_that_item_is_not_returned_for_w1_when_it_is_the_earlier_on(db, w1, w2, f9, i1, mk_stock):
    """PRD-GT-05 — a W2 row of that item is not returned for W1, when it is the earlier one.
    Rules: `get_by_item` R1"""
    mk_stock(workspace_id=w2.id, factory_id=f9.id)
    a = mk_stock()

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] PRD-GT-06
def test_prd_gt_06__a_soft_deleted_row_is_not_returned(db, w1, u1, i1, mk_stock):
    """PRD-GT-06 — a soft-deleted row is not returned.
    Rules: `get_by_item` R2"""
    mk_stock(is_active=False, is_deleted=True, deleted_at=T0, deleted_by=u1.id)
    a = mk_stock(is_available_for_sale=True)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] PRD-GT-07
def test_prd_gt_07__an_unknown_item_returns_an_empty_list(db, w1, mk_stock):
    """PRD-GT-07 — an unknown item returns an empty list.
    Rules: `get_by_item` R3"""
    mk_stock()

    result = dao.get_by_item(db, item_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PRD-GT-08
def test_prd_gt_08__item_id_0_returns_an_empty_list(db, w1, mk_stock):
    """PRD-GT-08 — item_id=0 returns an empty list.
    Rules: `get_by_item` R3"""
    mk_stock()

    result = dao.get_by_item(db, item_id=0, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PRD-GT-09
def test_prd_gt_09__an_item_with_no_rows_returns_an_empty_list(db, w1, i2, mk_stock):
    """PRD-GT-09 — an item with no rows returns an empty list.
    Rules: `get_by_item` R3"""
    mk_stock()

    result = dao.get_by_item(db, item_id=i2.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PRD-GT-10
@pytest.mark.xfail(strict=True, reason="BUG-1328: Item summary counts finished goods of a deleted factory")
def test_prd_gt_10__a_row_of_a_soft_deleted_factory_is_not_returned(db, w1, fd, i1, mk_stock):
    """PRD-GT-10 — a row of a soft-deleted factory is not returned.
    Rules: `get_by_item` R3a [BUG-1328]"""
    a = mk_stock()
    mk_stock(factory_id=fd.id)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] PRD-GT-11
@pytest.mark.xfail(strict=True, reason="BUG-1328: Item summary counts finished goods of a deleted factory")
def test_prd_gt_11__only_in_a_soft_deleted_factory_an_empty_list(db, w1, fd, i1, mk_stock):
    """PRD-GT-11 — only in a soft-deleted factory: an empty list.
    Rules: `get_by_item` R3a [BUG-1328]"""
    mk_stock(factory_id=fd.id)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PRD-GT-12
@pytest.mark.xfail(strict=True, reason="BUG-1328: Item summary counts finished goods of a deleted factory")
def test_prd_gt_12__a_w2_row_on_a_soft_deleted_w1_factory_is_hidden_too(db, w2, fd, i1, mk_stock):
    """PRD-GT-12 — a W2 row on a soft-deleted W1 factory is hidden too.
    Rules: `get_by_item` R3a [BUG-1328]"""
    mk_stock(workspace_id=w2.id, factory_id=fd.id)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] PRD-GT-13
def test_prd_gt_13__reading_with_a_soft_deleted_factory_changes_nothing(db, w1, fd, i1, mk_stock, recorder):
    """PRD-GT-13 — reading with a soft-deleted factory changes nothing.
    Rules: `get_by_item` R3b"""
    x = mk_stock(factory_id=fd.id)
    before_x = snap(db, x)
    before_fd = snap(db, fd)

    recorder.start()
    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    db.expire_all()
    assert snap(db, x) == before_x
    # Then 3
    assert snap(db, fd) == before_fd
    # Then 4
    assert recorder.written() == []


# [claude] PRD-GT-14
def test_prd_gt_14__an_inactive_factory_hides_nothing(db, w1, fi, i1, mk_stock):
    """PRD-GT-14 — an inactive factory hides nothing.
    Rules: `get_by_item` R3b"""
    a = mk_stock(factory_id=fi.id)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] PRD-GT-15
def test_prd_gt_15__once_the_factory_is_live_again_the_row_is_back_unchanged(db, w1, fd, i1, mk_stock):
    """PRD-GT-15 — once the factory is live again the row is back, unchanged.
    Rules: `get_by_item` R3b"""
    x = mk_stock(factory_id=fd.id)
    fd.is_deleted = False
    fd.deleted_at = None
    fd.deleted_by = None
    db.flush()
    before_x = snap(db, x)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [x.id]
    # Then 2
    db.expire_all()
    assert snap(db, x) == before_x


# [claude] PRD-GT-16
@pytest.mark.xfail(strict=True, reason="BUG-1338: Item summary shows finished goods of a removed item")
def test_prd_gt_16__the_rows_of_a_removed_item_are_not_returned(db, w1, ix, mk_stock):
    """PRD-GT-16 — the rows of a removed item are not returned.
    Rules: `get_by_item` R3c [BUG-1338]"""
    mk_stock(item_id=ix.id)

    result = dao.get_by_item(db, item_id=ix.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PRD-GT-17
@pytest.mark.xfail(strict=True, reason="BUG-1326: An item's product rows have no sort order")
def test_prd_gt_17__the_query_orders_by_id_ascending(db, w1, i1, mk_stock, recorder):
    """PRD-GT-17 — the query orders by id, ascending.
    Rules: `get_by_item` R4 [BUG-1326]"""
    a = mk_stock()

    recorder.start()
    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    sql = recorder.sql()
    order_part = order_part_of(sql)
    assert "ORDER BY" in sql
    # Then 3
    assert ".id" in order_part
    # Then 4
    assert "DESC" not in order_part.upper()
    # Then 5
    assert order_part.count(",") == 0


# [claude] PRD-GT-18
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1326: An item's product rows have no sort order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_prd_gt_18__rows_come_back_by_id_when_the_lowest_id_was_updated(db, w1, f2, i1, mk_stock):
    """PRD-GT-18 — rows come back by id, when the lowest id was updated.
    Rules: `get_by_item` R4 [BUG-1326]"""
    seqscan(db)
    a = mk_stock()
    b = mk_stock(is_available_for_sale=True)
    c = mk_stock(factory_id=f2.id)
    a.qty = 8
    db.flush()
    db.expire_all()

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [a.id, b.id, c.id]


# [claude] PRD-GT-19
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1326: An item's product rows have no sort order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_prd_gt_19__rows_come_back_by_id_when_factory_flag_and_qty_would_each_sort_otherwi(db, w1, f2, i1, mk_stock):
    """PRD-GT-19 — rows come back by id, when factory, flag and qty would each sort otherwise.
    Rules: `get_by_item` R4 [BUG-1326]"""
    seqscan(db)
    a = mk_stock(factory_id=f2.id, is_available_for_sale=True, qty=7)
    b = mk_stock(qty=9)
    c = mk_stock(is_available_for_sale=True, qty=5)
    db.expire_all()

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [a.id, b.id, c.id]


# [claude] PRD-GT-20
def test_prd_gt_20__there_is_no_cap_101_rows_give_101(db, w1, i1, new_stock):
    """PRD-GT-20 — there is no cap: 101 rows give 101.
    Rules: `get_by_item` R5"""
    factories = [Factory(workspace_id=w1.id, name=f"Plant {k}", abbreviation=f"P{k}") for k in range(1, 52)]
    add_many(db, factories)
    rows = [new_stock(item_id=i1.id, factory_id=factories[k - 1].id, is_available_for_sale=flag)
            for k in range(1, 51) for flag in (False, True)]
    rows.append(new_stock(item_id=i1.id, factory_id=factories[50].id, is_available_for_sale=False))
    add_many(db, rows)
    all_ids = [row.id for row in rows]

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert sorted(ids(result)) == sorted(all_ids)


# [claude] PRD-GT-21
def test_prd_gt_21__writes_nothing_a_pending_row_that_would_sort_first_stays_pending_and_i(db, w1, f2, i1, i5, mk_stock, recorder):
    """PRD-GT-21 — writes nothing: a pending row that would sort first stays pending and is not returned.
    Rules: `get_by_item` Side effects"""
    a = mk_stock(is_available_for_sale=True)
    p = Product(workspace_id=w1.id, item_id=i5.id, factory_id=f2.id, qty=1)
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    recorder.start()
    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

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


# [claude] PRD-GT-22
def test_prd_gt_22__writes_nothing_a_read_leaves_the_caller_s_unflushed_edit_alone(db, w1, i1, mk_stock):
    """PRD-GT-22 — writes nothing: a read leaves the caller's unflushed edit alone.
    Rules: `get_by_item` Side effects"""
    a = mk_stock()
    b = mk_stock(is_available_for_sale=True)
    b.note = "Edited"

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert b.note == "Edited"


# [claude] PRD-GT-23
def test_prd_gt_23__a_row_with_is_active_false_is_deleted_false_is_returned(db, w1, i1, mk_stock):
    """PRD-GT-23 — a row with is_active False, is_deleted False is returned.
    Rules: `get_by_item` R2a"""
    a = mk_stock(is_active=False)
    b = mk_stock(is_available_for_sale=True)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]


# [claude] PRD-GT-24
def test_prd_gt_24__reading_a_removed_item_changes_nothing_to_its_rows_or_to_the_item(db, w1, ix, mk_stock, recorder):
    """PRD-GT-24 — reading a removed item changes nothing, to its rows or to the item.
    Rules: `get_by_item` R3b"""
    a = mk_stock(item_id=ix.id)
    before_a = snap(db, a)
    before_ix = snap(db, ix)

    recorder.start()
    result = dao.get_by_item(db, item_id=ix.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    db.expire_all()
    assert snap(db, a) == before_a
    # Then 3
    assert snap(db, ix) == before_ix
    # Then 4
    assert recorder.written() == []


# [claude] PRD-GT-25
def test_prd_gt_25__once_the_item_is_active_again_its_rows_are_back_unchanged(db, w1, ix, mk_stock):
    """PRD-GT-25 — once the item is active again its rows are back, unchanged.
    Rules: `get_by_item` R3b"""
    a = mk_stock(item_id=ix.id)
    ix.is_active = True
    db.flush()
    before_a = snap(db, a)

    result = dao.get_by_item(db, item_id=ix.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]
    # Then 2
    db.expire_all()
    assert snap(db, a) == before_a


# --------------------------------------------------------------------------- #
# ProductDAO.soft_delete
# --------------------------------------------------------------------------- #


# [claude] PRD-SD-01
def test_prd_sd_01__sets_the_three_flags_and_returns_the_same_object(db, u2, mk_stock):
    """PRD-SD-01 — sets the three flags and returns the same object.
    Rules: `soft_delete` R1, Returns"""
    a = mk_stock()

    result = dao.soft_delete(db, db_obj=a, deleted_by=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.is_deleted is True
    assert row.is_active is False
    assert row.deleted_by == u2.id


# [claude] PRD-SD-02
def test_prd_sd_02__every_other_column_keeps_its_value(db, u1, u2, mk_stock):
    """PRD-SD-02 — every other column keeps its value.
    Rules: `soft_delete` R2"""
    a = mk_stock(qty=4, avg_cost=Decimal("2.50"), selling_price=Decimal("3.75"), min_order_qty=2, is_available_for_sale=True, note="Keep", created_by=u1.id, updated_by=u1.id)
    before_a = snap(db, a)

    result = dao.soft_delete(db, db_obj=a, deleted_by=u2.id)

    # Then 1
    assert result is a
    # Then 2
    db.expire_all()
    assert without(snap(db, a), "is_deleted", "is_active", "deleted_by", "deleted_at", "updated_at") == without(before_a, "is_deleted", "is_active", "deleted_by", "deleted_at", "updated_at")
    # Then 3
    row = reread(db, a)
    assert row.qty == 4
    assert row.avg_cost == Decimal("2.50")
    assert row.selling_price == Decimal("3.75")


# [claude] PRD-SD-03
def test_prd_sd_03__no_ledger_row_is_written(db, u1, u2, mk_stock):
    """PRD-SD-03 — no ledger row is written.
    Rules: `soft_delete` R2"""
    a = mk_stock(qty=4, avg_cost=Decimal("2.50"), selling_price=Decimal("3.75"), min_order_qty=2, is_available_for_sale=True, note="Keep", created_by=u1.id, updated_by=u1.id)

    result = dao.soft_delete(db, db_obj=a, deleted_by=u2.id)

    # Then 1
    assert result is a
    # Then 2
    assert count_rows(db, ProductLedger) == 0


# [claude] PRD-SD-04
def test_prd_sd_04__updated_at_moves_from_none_and_updated_by_stays(db, u1, u2, mk_stock):
    """PRD-SD-04 — updated_at moves from None, and updated_by stays.
    Rules: `soft_delete` R3"""
    a = mk_stock(updated_by=u1.id)

    result = dao.soft_delete(db, db_obj=a, deleted_by=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.updated_at is not None
    # Then 3
    row = reread(db, a)
    assert row.updated_by == u1.id


# [claude] PRD-SD-05
def test_prd_sd_05__updated_at_moves_from_a_past_stamp(db, u2, mk_stock):
    """PRD-SD-05 — updated_at moves from a past stamp.
    Rules: `soft_delete` R3"""
    a = mk_stock(updated_at=T0)

    result = dao.soft_delete(db, db_obj=a, deleted_by=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.updated_at != T0


# [claude] PRD-SD-06
def test_prd_sd_06__deleted_at_is_set(db, u2, mk_stock):
    """PRD-SD-06 — deleted_at is set.
    Rules: `soft_delete` R3a"""
    a = mk_stock()

    result = dao.soft_delete(db, db_obj=a, deleted_by=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.deleted_at is not None


# [claude] PRD-SD-07
@pytest.mark.xfail(strict=True, reason="BUG-1335: A product's delete time depends on the database's time zone")
def test_prd_sd_07__deleted_at_comes_from_utcnow_naive(db, u2, mk_stock):
    """PRD-SD-07 — deleted_at comes from utcnow, naive.
    Rules: `soft_delete` R3a [BUG-1335]"""
    a = mk_stock()

    with clock_now():
        result = dao.soft_delete(db, db_obj=a, deleted_by=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.deleted_at == NOW


# [claude] PRD-SD-08
@pytest.mark.xfail(strict=True, reason="BUG-1335: A product's delete time depends on the database's time zone")
def test_prd_sd_08__deleted_at_comes_from_utcnow_under_any_session_time_zone(db, u2, mk_stock):
    """PRD-SD-08 — deleted_at comes from utcnow under any session time zone.
    Rules: `soft_delete` R3a [BUG-1335]"""
    db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))
    a = mk_stock()

    with clock_now():
        result = dao.soft_delete(db, db_obj=a, deleted_by=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.deleted_at == NOW


# [claude] PRD-SD-09
def test_prd_sd_09__the_row_stops_being_found_by_the_three_reads_and_is_found_by_id(db, w1, u2, f1, i1, mk_stock):
    """PRD-SD-09 — the row stops being found by the three reads and is found by id.
    Rules: `soft_delete` R4"""
    a = mk_stock()

    result = dao.soft_delete(db, db_obj=a, deleted_by=u2.id)

    # Then 1
    assert result is a
    # Then 2
    assert dao.get_by_workspace(db, workspace_id=w1.id) == []
    # Then 3
    assert dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id) == []
    # Then 4
    assert dao.get_by_factory_item_available(db, factory_id=f1.id, item_id=i1.id, is_available_for_sale=False, workspace_id=w1.id) is None
    # Then 5
    assert dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id).id == a.id


# [claude] PRD-SD-10
def test_prd_sd_10__on_a_row_already_deleted_it_raises_nothing_and_overwrites_deleted_at_a(db, u1, u2, mk_stock):
    """PRD-SD-10 — on a row already deleted it raises nothing and overwrites deleted_at and deleted_by.
    Rules: `soft_delete` R5"""
    a = mk_stock(is_active=False, is_deleted=True, deleted_at=T0, deleted_by=u1.id)

    result = dao.soft_delete(db, db_obj=a, deleted_by=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.deleted_by == u2.id
    assert row.deleted_at != T0
    # Then 3
    row = reread(db, a)
    assert row.is_deleted is True
    assert row.is_active is False


# [claude] PRD-SD-11
def test_prd_sd_11__not_committed_a_rollback_restores_the_row(db, u2, mk_stock):
    """PRD-SD-11 — not committed: a rollback restores the row.
    Rules: `soft_delete` R6"""
    a = mk_stock()

    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        result = dao.soft_delete(db, db_obj=a, deleted_by=u2.id)

    # Then 1
    assert result is a
    # Then 2
    assert count_rows(db, Product, Product.is_deleted.is_(True)) == 1
    # Then 3
    sp.rollback()
    assert count_rows(db, Product, Product.is_deleted.is_(False)) == 1
    # Then 4
    commit_spy.assert_not_called()
    # Then 5
    row = reread(db, a)
    assert row.is_active is True
    assert row.deleted_by is None
    assert row.deleted_at is None


# [claude] PRD-SD-12
def test_prd_sd_12__an_unknown_deleted_by_fails_on_flush_and_changes_nothing(db, mk_stock):
    """PRD-SD-12 — an unknown deleted_by fails on flush and changes nothing.
    Rules: `soft_delete` Errors row 1"""
    a = mk_stock()
    before_a = snap(db, a)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.soft_delete(db, db_obj=a, deleted_by=MISSING)
    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert exc.value.orig.pgcode == "23503"
    # Then 4
    db.expire_all()
    assert snap(db, a) == before_a


# [claude] PRD-SD-13
def test_prd_sd_13__one_row_is_updated_and_flushed_another_stays_as_it_was(db, u2, i2, mk_stock, recorder):
    """PRD-SD-13 — one row is updated and flushed; another stays as it was.
    Rules: `soft_delete` Side effects"""
    a = mk_stock()
    b = mk_stock(item_id=i2.id)
    before_b = snap(db, b)

    recorder.start()
    result = dao.soft_delete(db, db_obj=a, deleted_by=u2.id)

    # Then 1
    assert result is a
    # Then 2
    assert len(recorder.written()) == 1
    # Then 3
    assert not db.dirty
    # Then 4
    db.expire_all()
    assert snap(db, b) == before_b


# --------------------------------------------------------------------------- #
# ProductDAO.restore
# --------------------------------------------------------------------------- #


# [claude] PRD-RS-01
def test_prd_rs_01__clears_the_four_fields_and_returns_the_same_object(db, u1, mk_stock):
    """PRD-RS-01 — clears the four fields and returns the same object.
    Rules: `restore` R1, Returns"""
    a = mk_stock(is_active=False, is_deleted=True, deleted_at=T0, deleted_by=u1.id)

    result = dao.restore(db, db_obj=a)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.is_active is True
    assert row.is_deleted is False
    assert row.deleted_at is None
    assert row.deleted_by is None


# [claude] PRD-RS-02
def test_prd_rs_02__qty_and_every_other_column_keep_their_values(db, u1, mk_stock):
    """PRD-RS-02 — qty and every other column keep their values.
    Rules: `restore` R2"""
    a = mk_stock(qty=4, avg_cost=Decimal("2.50"), selling_price=Decimal("3.75"), min_order_qty=2, is_available_for_sale=True, note="Keep", created_by=u1.id, is_active=False, is_deleted=True, deleted_at=T0, deleted_by=u1.id)
    before_a = snap(db, a)

    result = dao.restore(db, db_obj=a)

    # Then 1
    assert result is a
    # Then 2
    db.expire_all()
    assert without(snap(db, a), "is_active", "is_deleted", "deleted_at", "deleted_by", "updated_at") == without(before_a, "is_active", "is_deleted", "deleted_at", "deleted_by", "updated_at")
    # Then 3
    row = reread(db, a)
    assert row.qty == 4
    assert row.avg_cost == Decimal("2.50")


# [claude] PRD-RS-03
def test_prd_rs_03__no_ledger_row_is_written(db, u1, mk_stock):
    """PRD-RS-03 — no ledger row is written.
    Rules: `restore` R2"""
    a = mk_stock(qty=4, is_active=False, is_deleted=True, deleted_at=T0, deleted_by=u1.id)

    result = dao.restore(db, db_obj=a)

    # Then 1
    assert result is a
    # Then 2
    assert count_rows(db, ProductLedger) == 0


# [claude] PRD-RS-04
def test_prd_rs_04__updated_at_moves_and_updated_by_stays(db, u1, mk_stock):
    """PRD-RS-04 — updated_at moves, and updated_by stays.
    Rules: `restore` R2"""
    a = mk_stock(updated_at=T0, updated_by=u1.id, is_active=False, is_deleted=True, deleted_at=T0, deleted_by=u1.id)

    result = dao.restore(db, db_obj=a)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.updated_at != T0
    # Then 3
    row = reread(db, a)
    assert row.updated_by == u1.id


# [claude] PRD-RS-05
def test_prd_rs_05__the_row_is_found_again_by_the_three_reads(db, w1, u1, f1, i1, mk_stock):
    """PRD-RS-05 — the row is found again by the three reads.
    Rules: `restore` R3"""
    a = mk_stock(is_active=False, is_deleted=True, deleted_at=T0, deleted_by=u1.id)

    result = dao.restore(db, db_obj=a)

    # Then 1
    assert result is a
    # Then 2
    assert dao.get_by_factory_item_available(db, factory_id=f1.id, item_id=i1.id, is_available_for_sale=False, workspace_id=w1.id).id == a.id
    # Then 3
    assert [r.id for r in dao.get_by_workspace(db, workspace_id=w1.id)] == [a.id]
    # Then 4
    assert [r.id for r in dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)] == [a.id]


# [claude] PRD-RS-06
def test_prd_rs_06__on_a_live_row_it_raises_nothing_and_changes_no_value(db, mk_stock):
    """PRD-RS-06 — on a live row it raises nothing and changes no value.
    Rules: `restore` R4"""
    a = mk_stock(qty=4)

    result = dao.restore(db, db_obj=a)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.is_active is True
    assert row.is_deleted is False
    assert row.qty == 4


# [claude] PRD-RS-07
def test_prd_rs_07__a_row_with_is_active_false_becomes_active(db, mk_stock):
    """PRD-RS-07 — a row with is_active False becomes active.
    Rules: `restore` R4"""
    a = mk_stock(is_active=False)

    result = dao.restore(db, db_obj=a)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.is_active is True


# [claude] PRD-RS-08
def test_prd_rs_08__not_committed_a_rollback_restores_the_deleted_state(db, u1, mk_stock):
    """PRD-RS-08 — not committed: a rollback restores the deleted state.
    Rules: `restore` Side effects"""
    a = mk_stock(is_active=False, is_deleted=True, deleted_at=T0, deleted_by=u1.id)

    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        result = dao.restore(db, db_obj=a)

    # Then 1
    assert result is a
    # Then 2
    assert count_rows(db, Product, Product.is_deleted.is_(False)) == 1
    # Then 3
    sp.rollback()
    assert count_rows(db, Product, Product.is_deleted.is_(True)) == 1
    # Then 4
    commit_spy.assert_not_called()


# [claude] PRD-RS-09
def test_prd_rs_09__one_row_is_updated_and_flushed_another_stays_as_it_was(db, u1, i2, mk_stock, recorder):
    """PRD-RS-09 — one row is updated and flushed; another stays as it was.
    Rules: `restore` Side effects"""
    a = mk_stock(is_active=False, is_deleted=True, deleted_at=T0, deleted_by=u1.id)
    b = mk_stock(item_id=i2.id, is_active=False, is_deleted=True, deleted_at=T0, deleted_by=u1.id)
    before_b = snap(db, b)

    recorder.start()
    result = dao.restore(db, db_obj=a)

    # Then 1
    assert result is a
    # Then 2
    assert len(recorder.written()) == 1
    # Then 3
    assert not db.dirty
    # Then 4
    db.expire_all()
    assert snap(db, b) == before_b


# [claude] PRD-RS-10
def test_prd_rs_10__updated_at_moves_from_none_and_updated_by_stays(db, u1, mk_stock):
    """PRD-RS-10 — updated_at moves from None, and updated_by stays.
    Rules: `restore` R2"""
    a = mk_stock(updated_by=u1.id, is_active=False, is_deleted=True, deleted_at=T0, deleted_by=u1.id)

    result = dao.restore(db, db_obj=a)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.updated_at is not None
    # Then 3
    row = reread(db, a)
    assert row.updated_by == u1.id


# --------------------------------------------------------------------------- #
# Inherited BaseDAO methods on Product
# --------------------------------------------------------------------------- #


# [claude] PRD-INH-01
def test_prd_inh_01__create_with_a_dict_gives_the_defaults(db, w1, f1, i1):
    """PRD-INH-01 — create with a dict gives the defaults.
    Rules: `inherited` R1"""
    result = dao.create(db, obj_in={"workspace_id": w1.id, "item_id": i1.id, "factory_id": f1.id})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.qty == 0
    assert row.is_available_for_sale is False
    # Then 3
    row = reread(db, result)
    assert row.is_active is True
    assert row.is_deleted is False
    # Then 4
    row = reread(db, result)
    assert row.avg_cost is None
    assert row.updated_at is None
    assert row.created_at is not None


# [claude] PRD-INH-02
def test_prd_inh_02__create_is_flushed_not_committed_a_rollback_removes_the_row(db, w1, f1, i1):
    """PRD-INH-02 — create is flushed, not committed: a rollback removes the row.
    Rules: `inherited` R1"""
    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        result = dao.create(db, obj_in={"workspace_id": w1.id, "item_id": i1.id, "factory_id": f1.id})

    # Then 1
    assert result.id is not None
    # Then 2
    assert count_rows(db, Product) == 1
    # Then 3
    sp.rollback()
    assert count_rows(db, Product) == 0
    # Then 4
    commit_spy.assert_not_called()


# [claude] PRD-INH-03
def test_prd_inh_03__create_with_a_productcreate_fails_on_flush_and_saves_nothing(db, f1, i1):
    """PRD-INH-03 — create with a ProductCreate fails on flush and saves nothing.
    Rules: `inherited` R2"""
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in=ProductCreate(item_id=i1.id, factory_id=f1.id))
    # Then 2
    assert isinstance(exc.value.orig, NotNullViolation)
    # Then 3
    assert exc.value.orig.pgcode == "23502"
    # Then 4
    assert count_rows(db, Product) == 0


# [claude] PRD-INH-04
def test_prd_inh_04__a_second_row_of_one_key_is_refused(db, w1, f1, i1, mk_stock):
    """PRD-INH-04 — a second row of one key is refused.
    Rules: `inherited` R3"""
    mk_stock()

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "item_id": i1.id, "factory_id": f1.id})
    # Then 2
    assert isinstance(exc.value.orig, UniqueViolation)
    # Then 3
    assert exc.value.orig.pgcode == "23505"
    # Then 4
    assert count_rows(db, Product) == 1


# [claude] PRD-INH-05
def test_prd_inh_05__a_second_row_of_one_key_is_refused_when_the_first_is_soft_deleted(db, w1, u1, f1, i1, mk_stock):
    """PRD-INH-05 — a second row of one key is refused when the first is soft-deleted.
    Rules: `inherited` R3"""
    mk_stock(is_active=False, is_deleted=True, deleted_at=T0, deleted_by=u1.id)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "item_id": i1.id, "factory_id": f1.id})
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    assert count_rows(db, Product) == 1


# [claude] PRD-INH-06
def test_prd_inh_06__the_same_item_and_factory_with_the_other_flag_is_accepted(db, w1, f1, i1, mk_stock):
    """PRD-INH-06 — the same item and factory with the other flag is accepted.
    Rules: `inherited` R3"""
    a = mk_stock()

    result = dao.create(db, obj_in={"workspace_id": w1.id, "item_id": i1.id, "factory_id": f1.id, "is_available_for_sale": True})

    # Then 1
    assert result.id != a.id
    # Then 2
    row = reread(db, result)
    assert row.is_available_for_sale is True
    # Then 3
    assert count_rows(db, Product) == 2


# [claude] PRD-INH-07
def test_prd_inh_07__a_negative_qty_is_stored(db, w1, f1, i1):
    """PRD-INH-07 — a negative qty is stored.
    Rules: `inherited` R4"""
    result = dao.create(db, obj_in={"workspace_id": w1.id, "item_id": i1.id, "factory_id": f1.id, "qty": -4})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.qty == -4


# [claude] PRD-INH-08
def test_prd_inh_08__the_top_of_32_bits_is_stored(db, w1, f1, i1):
    """PRD-INH-08 — the top of 32 bits is stored.
    Rules: `inherited` R4"""
    result = dao.create(db, obj_in={"workspace_id": w1.id, "item_id": i1.id, "factory_id": f1.id, "qty": 2147483647})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.qty == 2147483647


# [claude] PRD-INH-09
def test_prd_inh_09__one_above_32_bits_raises(db, w1, f1, i1):
    """PRD-INH-09 — one above 32 bits raises.
    Rules: `inherited` R4"""
    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "item_id": i1.id, "factory_id": f1.id, "qty": 2147483648})
    # Then 2
    assert isinstance(exc.value.orig, NumericValueOutOfRange)
    # Then 3
    assert exc.value.orig.pgcode == "22003"
    # Then 4
    assert count_rows(db, Product) == 0


# [claude] PRD-INH-10
def test_prd_inh_10__avg_cost_0_125_reads_back_0_13_the_column_rounds_half_away_from_zero(db, w1, f1, i1):
    """PRD-INH-10 — avg_cost 0.125 reads back 0.13: the column rounds half away from zero.
    Rules: `inherited` R5"""
    result = dao.create(db, obj_in={"workspace_id": w1.id, "item_id": i1.id, "factory_id": f1.id, "avg_cost": Decimal("0.125")})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.avg_cost == Decimal("0.13")


# [claude] PRD-INH-11
def test_prd_inh_11__avg_cost_0_124_reads_back_0_12(db, w1, f1, i1):
    """PRD-INH-11 — avg_cost 0.124 reads back 0.12.
    Rules: `inherited` R5"""
    result = dao.create(db, obj_in={"workspace_id": w1.id, "item_id": i1.id, "factory_id": f1.id, "avg_cost": Decimal("0.124")})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.avg_cost == Decimal("0.12")


# [claude] PRD-INH-12
def test_prd_inh_12__update_with_a_productupdate_sets_qty_to_0_and_keeps_note(db, mk_stock):
    """PRD-INH-12 — update with a ProductUpdate sets qty to 0 and keeps note.
    Rules: `inherited` R6"""
    a = mk_stock(qty=4, note="Keep")

    result = dao.update(db, db_obj=a, obj_in=ProductUpdate(qty=0, note=None))

    # Then 1
    assert result.id == a.id
    # Then 2
    row = reread(db, a)
    assert row.qty == 0
    assert row.note == "Keep"


# [claude] PRD-INH-13
def test_prd_inh_13__update_is_flushed_not_committed_a_rollback_restores_the_row(db, mk_stock):
    """PRD-INH-13 — update is flushed, not committed: a rollback restores the row.
    Rules: `inherited` R6"""
    a = mk_stock(qty=4)

    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        result = dao.update(db, db_obj=a, obj_in=ProductUpdate(qty=0))

    # Then 1
    assert result.id == a.id
    # Then 2
    assert count_rows(db, Product, Product.qty == 0) == 1
    # Then 3
    sp.rollback()
    assert count_rows(db, Product, Product.qty == 4) == 1
    # Then 4
    commit_spy.assert_not_called()


# [claude] PRD-INH-14
def test_prd_inh_14__update_changes_a_soft_deleted_row_like_any_other(db, u1, mk_stock):
    """PRD-INH-14 — update changes a soft-deleted row like any other.
    Rules: `inherited` R7"""
    a = mk_stock(qty=4, is_active=False, is_deleted=True, deleted_at=T0, deleted_by=u1.id)

    result = dao.update(db, db_obj=a, obj_in=ProductUpdate(qty=9))

    # Then 1
    assert result.id == a.id
    # Then 2
    row = reread(db, a)
    assert row.qty == 9
    assert row.is_deleted is True
