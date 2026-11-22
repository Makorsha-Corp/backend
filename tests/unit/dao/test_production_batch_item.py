"""Unit tests for app/dao/production_batch_item.py.

Implements tests/unit/dao/production_batch_item.cases.md, one test per case, in card order. Real
Postgres session (`db` fixture).
Nothing is mocked and no clock is patched (Conventions, Externals).

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117, DTZ001  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested():`, and naive datetimes)
from datetime import date, datetime

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError

from app.dao.production_batch_item import production_batch_item_dao
from app.models.factory import Factory
from app.models.item import Item
from app.models.production_batch import ProductionBatch
from app.models.production_batch_item import ProductionBatchItem
from app.models.production_line import ProductionLine
from app.schemas.production_batch_item import (
    ProductionBatchItemCreate,
    ProductionBatchItemUpdate,
)
from tests.unit.factories import make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton production_batch_item_dao" (a module-level name, not a fixture)
dao = production_batch_item_dao

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999

# Convention "T0": a past stamp
T0 = datetime(2026, 1, 15, 9, 0, 0)


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
def f1(db, w1, w2):
    return _add(db, Factory(workspace_id=w1.id, name="Factory One", abbreviation="F1"))


@pytest.fixture
def f9(db, w2, f1):
    return _add(db, Factory(workspace_id=w2.id, name="Far Plant", abbreviation="F9"))


@pytest.fixture
def l1(db, w1, f1, f9):
    return _add(db, ProductionLine(workspace_id=w1.id, factory_id=f1.id, name="Press"))


@pytest.fixture
def l9(db, w2, f9, l1):
    return _add(db, ProductionLine(workspace_id=w2.id, factory_id=f9.id, name="Press"))


@pytest.fixture
def b1(db, w1, l1, l9):
    return _add(db, ProductionBatch(workspace_id=w1.id, batch_number="B-1", production_line_id=l1.id, batch_date=date(2026, 3, 1)))


@pytest.fixture
def b2(db, w1, l1, b1):
    return _add(db, ProductionBatch(workspace_id=w1.id, batch_number="B-2", production_line_id=l1.id, batch_date=date(2026, 3, 1)))


@pytest.fixture
def bc(db, w1, l1, b2):
    return _add(db, ProductionBatch(workspace_id=w1.id, batch_number="B-3", production_line_id=l1.id, batch_date=date(2026, 3, 1), status="cancelled"))


@pytest.fixture
def b9(db, w2, l9, bc):
    return _add(db, ProductionBatch(workspace_id=w2.id, batch_number="B-9", production_line_id=l9.id, batch_date=date(2026, 3, 1)))


@pytest.fixture
def i1(db, w1, b9):
    return _add(db, Item(workspace_id=w1.id, name="Bolt", name_normalized="bolt", unit="pcs"))


@pytest.fixture
def i2(db, w1, i1):
    return _add(db, Item(workspace_id=w1.id, name="Washer", name_normalized="washer", unit="pcs"))


@pytest.fixture
def i3(db, w1, i2):
    return _add(db, Item(workspace_id=w1.id, name="Spring", name_normalized="spring", unit="pcs"))


@pytest.fixture
def ix(db, w1, i3):
    return _add(db, Item(workspace_id=w1.id, name="Old Gasket", name_normalized="old gasket", unit="pcs", is_active=False))


@pytest.fixture
def i9(db, w2, ix):
    return _add(db, Item(workspace_id=w2.id, name="Far Crate", name_normalized="far crate", unit="pcs"))


# Convention "they exist in every test and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2, f1, f9, l1, l9, b1, b2, bc, b9, i1, i2, i3, ix, i9):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builders (fixtures; each mk_ flushes before it returns)
# --------------------------------------------------------------------------- #

# Convention "line"
@pytest.fixture
def new_line(w1, b1, i1):
    """new_line(**columns) -> ProductionBatchItem, not added."""
    def _new(**columns):
        return ProductionBatchItem(**{"workspace_id": w1.id, "batch_id": b1.id, "item_id": i1.id, "item_role": "input", **columns})
    return _new


@pytest.fixture
def mk_line(db, new_line):
    """mk_line(...) = new_line(...), added and flushed."""
    def _mk(**columns):
        return _add(db, new_line(**columns))
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


# Convention "re-read X": expire, then SELECT by id
def reread(db, row):
    db.expire_all()
    return db.get(type(row), sa_inspect(row).identity[0])


# Convention "nothing written": the number of `production_batch_items` rows stored (all workspaces)
def stored_count(db):
    return db.scalar(select(func.count()).select_from(ProductionBatchItem.__table__))


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
        """The one SELECT from `production_batch_items`; fails loudly unless there is exactly one."""
        [statement] = [s for s in self.selects() if "FROM production_batch_items" in s]
        return statement


@pytest.fixture
def recorder(db):
    statement_recorder = StatementRecorder(db)
    yield statement_recorder
    statement_recorder.stop()


# --------------------------------------------------------------------------- #
# ProductionBatchItemDAO.get_by_batch
# --------------------------------------------------------------------------- #


# [claude] BIT-G-01
def test_bit_g_01__returns_a_list_of_the_parent_s_lines_of_every_role(db, w1, b1, i1, i2, i3, mk_line):
    """BIT-G-01 — returns a list of the parent's lines, of every role.
    Rules: `get_by_batch` R1, Returns"""
    a = mk_line(item_role="input", item_id=i1.id)
    b = mk_line(item_role="output", item_id=i2.id)
    c = mk_line(item_role="waste", item_id=i3.id)
    d = mk_line(item_role="byproduct", item_id=i1.id)

    result = dao.get_by_batch(db, batch_id=b1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert sorted(ids(result)) == [a.id, b.id, c.id, d.id]
    # Then 3
    assert isinstance(result[0], ProductionBatchItem)


# [claude] BIT-G-02
def test_bit_g_02__a_line_of_another_parent_is_not_returned(db, w1, b1, b2, i1, i2, mk_line):
    """BIT-G-02 — a line of another parent is not returned.
    Rules: `get_by_batch` R1"""
    mk_line(item_role="input", item_id=i1.id, batch_id=b2.id)
    a = mk_line(item_role="input", item_id=i2.id)

    result = dao.get_by_batch(db, batch_id=b1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] BIT-G-03
def test_bit_g_03__the_right_parent_under_another_workspace_returns_an_empty_list(db, w2, b1, i1, mk_line):
    """BIT-G-03 — the right parent under another workspace returns an empty list.
    Rules: `get_by_batch` R1"""
    mk_line(item_role="input", item_id=i1.id)

    result = dao.get_by_batch(db, batch_id=b1.id, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] BIT-G-04
def test_bit_g_04__a_w2_row_on_a_w1_parent_is_returned_for_w2(db, w2, b1, i1, mk_line):
    """BIT-G-04 — a W2 row on a W1 parent is returned for W2.
    Rules: `get_by_batch` R1"""
    a = mk_line(item_role="input", item_id=i1.id, workspace_id=w2.id)

    result = dao.get_by_batch(db, batch_id=b1.id, workspace_id=w2.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] BIT-G-05
def test_bit_g_05__a_w2_row_on_a_w1_parent_is_not_returned_for_w1(db, w1, w2, b1, i1, mk_line):
    """BIT-G-05 — a W2 row on a W1 parent is not returned for W1.
    Rules: `get_by_batch` R1"""
    mk_line(item_role="input", item_id=i1.id, workspace_id=w2.id)

    result = dao.get_by_batch(db, batch_id=b1.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] BIT-G-06
def test_bit_g_06__an_unknown_parent_returns_an_empty_list(db, w1, i1, mk_line):
    """BIT-G-06 — an unknown parent returns an empty list.
    Rules: `get_by_batch` R2"""
    mk_line(item_role="input", item_id=i1.id)

    result = dao.get_by_batch(db, batch_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] BIT-G-07
def test_bit_g_07__batch_id_0_returns_an_empty_list(db, w1, i1, mk_line):
    """BIT-G-07 — batch_id=0 returns an empty list.
    Rules: `get_by_batch` R2"""
    mk_line(item_role="input", item_id=i1.id)

    result = dao.get_by_batch(db, batch_id=0, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] BIT-G-08
def test_bit_g_08__a_parent_with_no_lines_returns_an_empty_list(db, w1, b2, i1, mk_line):
    """BIT-G-08 — a parent with no lines returns an empty list.
    Rules: `get_by_batch` R2"""
    mk_line(item_role="input", item_id=i1.id)

    result = dao.get_by_batch(db, batch_id=b2.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] BIT-G-09
@pytest.mark.xfail(strict=True, reason="BUG-1322: A batch's lines have no sort order")
def test_bit_g_09__the_query_orders_by_id_ascending(db, w1, b1, i1, mk_line, recorder):
    """BIT-G-09 — the query orders by id, ascending.
    Rules: `get_by_batch` R3 [BUG-1322]"""
    a = mk_line(item_role="input", item_id=i1.id)

    recorder.start()
    result = dao.get_by_batch(db, batch_id=b1.id, workspace_id=w1.id)

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


# [claude] BIT-G-10
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1322: A batch's lines have no sort order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_bit_g_10__lines_come_back_by_id_when_the_lowest_id_was_updated(db, w1, b1, i1, i2, i3, mk_line):
    """BIT-G-10 — lines come back by id, when the lowest id was updated.
    Rules: `get_by_batch` R3 [BUG-1322]"""
    seqscan(db)
    a = mk_line(item_role="input", item_id=i1.id, expected_quantity=7)
    b = mk_line(item_role="input", item_id=i2.id, expected_quantity=9)
    c = mk_line(item_role="input", item_id=i3.id, expected_quantity=5)
    a.expected_quantity = 8
    db.flush()
    db.expire_all()

    result = dao.get_by_batch(db, batch_id=b1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [a.id, b.id, c.id]


# [claude] BIT-G-11
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1322: A batch's lines have no sort order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_bit_g_11__lines_come_back_by_id_when_item_role_and_quantity_would_each_sort_othe(db, w1, b1, i1, i2, i3, mk_line):
    """BIT-G-11 — lines come back by id, when item, role and quantity would each sort otherwise.
    Rules: `get_by_batch` R3 [BUG-1322]"""
    seqscan(db)
    a = mk_line(item_role="output", item_id=i3.id, expected_quantity=7)
    b = mk_line(item_role="waste", item_id=i1.id, expected_quantity=9)
    c = mk_line(item_role="byproduct", item_id=i2.id, expected_quantity=5)
    db.expire_all()

    result = dao.get_by_batch(db, batch_id=b1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [a.id, b.id, c.id]


# [claude] BIT-G-12
def test_bit_g_12__there_is_no_cap_101_lines_give_101_rows(db, w1, b1, new_line):
    """BIT-G-12 — there is no cap: 101 lines give 101 rows.
    Rules: `get_by_batch` R4"""
    rows = [new_line() for k in range(1, 102)]
    add_many(db, rows)
    newest = [row.id for row in rows]

    result = dao.get_by_batch(db, batch_id=b1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert sorted(ids(result)) == sorted(newest)


# [claude] BIT-G-13
def test_bit_g_13__a_line_of_a_cancelled_batch_is_returned(db, w1, bc, i1, mk_line):
    """BIT-G-13 — a line of a cancelled batch is returned.
    Rules: `get_by_batch` R5"""
    a = mk_line(item_role="input", item_id=i1.id, batch_id=bc.id)

    result = dao.get_by_batch(db, batch_id=bc.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] BIT-G-14
def test_bit_g_14__a_line_of_a_removed_item_is_returned(db, w1, b1, ix, mk_line):
    """BIT-G-14 — a line of a removed item is returned.
    Rules: `get_by_batch` R5"""
    a = mk_line(item_role="input", item_id=ix.id)

    result = dao.get_by_batch(db, batch_id=b1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] BIT-G-15
def test_bit_g_15__the_query_does_not_read_the_parent_tables(db, w1, b1, i1, mk_line, recorder):
    """BIT-G-15 — the query does not read the parent tables.
    Rules: `get_by_batch` R5"""
    mk_line(item_role="input", item_id=i1.id)

    recorder.start()
    result = dao.get_by_batch(db, batch_id=b1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 1
    # Then 2
    sql = recorder.sql()
    assert "JOIN" not in sql


# [claude] BIT-G-16
def test_bit_g_16__writes_nothing_a_pending_row_that_would_sort_first_stays_pending_and_i(db, w1, b1, i1, i2, mk_line, recorder):
    """BIT-G-16 — writes nothing: a pending row that would sort first stays pending and is not returned.
    Rules: `get_by_batch` Side effects"""
    a = mk_line(item_role="input", item_id=i2.id)
    p = ProductionBatchItem(workspace_id=w1.id, batch_id=b1.id, item_id=i1.id, item_role="input")
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    recorder.start()
    result = dao.get_by_batch(db, batch_id=b1.id, workspace_id=w1.id)

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


# [claude] BIT-G-17
def test_bit_g_17__writes_nothing_a_read_leaves_the_caller_s_unflushed_edit_alone(db, w1, b1, i1, i2, mk_line):
    """BIT-G-17 — writes nothing: a read leaves the caller's unflushed edit alone.
    Rules: `get_by_batch` Side effects"""
    a = mk_line(item_role="input", item_id=i1.id)
    b = mk_line(item_role="input", item_id=i2.id)
    b.notes = "Edited"

    result = dao.get_by_batch(db, batch_id=b1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert b.notes == "Edited"


# --------------------------------------------------------------------------- #
# ProductionBatchItemDAO.get_by_batch_and_role
# --------------------------------------------------------------------------- #


# [claude] BIT-R-01
def test_bit_r_01__returns_a_list_of_the_lines_of_that_parent_and_role(db, w1, b1, i1, i2, i3, mk_line):
    """BIT-R-01 — returns a list of the lines of that parent and role.
    Rules: `get_by_batch_and_role` R1, Returns"""
    a = mk_line(item_role="input", item_id=i1.id)
    mk_line(item_role="output", item_id=i2.id)
    b = mk_line(item_role="input", item_id=i3.id)

    result = dao.get_by_batch_and_role(db, batch_id=b1.id, item_role="input", workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 3
    assert isinstance(result[0], ProductionBatchItem)


# [claude] BIT-R-02
def test_bit_r_02__a_line_of_another_parent_is_not_returned(db, w1, b1, b2, i1, i2, mk_line):
    """BIT-R-02 — a line of another parent is not returned.
    Rules: `get_by_batch_and_role` R1"""
    mk_line(item_role="input", item_id=i1.id, batch_id=b2.id)
    a = mk_line(item_role="input", item_id=i2.id)

    result = dao.get_by_batch_and_role(db, batch_id=b1.id, item_role="input", workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] BIT-R-03
def test_bit_r_03__the_right_parent_and_role_under_another_workspace_returns_an_empty_lis(db, w2, b1, i1, mk_line):
    """BIT-R-03 — the right parent and role under another workspace returns an empty list.
    Rules: `get_by_batch_and_role` R1"""
    mk_line(item_role="input", item_id=i1.id)

    result = dao.get_by_batch_and_role(db, batch_id=b1.id, item_role="input", workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] BIT-R-04
def test_bit_r_04__two_lines_with_one_item_and_role_are_both_returned(db, w1, b1, i1, mk_line):
    """BIT-R-04 — two lines with one item and role are both returned.
    Rules: `get_by_batch_and_role` R1"""
    a = mk_line(item_role="input", item_id=i1.id)
    b = mk_line(item_role="input", item_id=i1.id)

    result = dao.get_by_batch_and_role(db, batch_id=b1.id, item_role="input", workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]


# [claude] BIT-R-05
def test_bit_r_05__a_role_in_capitals_finds_nothing(db, w1, b1, i1, mk_line):
    """BIT-R-05 — a role in capitals finds nothing.
    Rules: `get_by_batch_and_role` R2"""
    mk_line(item_role="input", item_id=i1.id)

    result = dao.get_by_batch_and_role(db, batch_id=b1.id, item_role="INPUT", workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] BIT-R-06
def test_bit_r_06__a_leading_space_in_the_role_finds_nothing(db, w1, b1, i1, mk_line):
    """BIT-R-06 — a leading space in the role finds nothing.
    Rules: `get_by_batch_and_role` R2"""
    mk_line(item_role="input", item_id=i1.id)

    result = dao.get_by_batch_and_role(db, batch_id=b1.id, item_role=" input", workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] BIT-R-07
def test_bit_r_07__the_start_of_a_role_finds_nothing(db, w1, b1, i1, mk_line):
    """BIT-R-07 — the start of a role finds nothing.
    Rules: `get_by_batch_and_role` R2"""
    mk_line(item_role="input", item_id=i1.id)

    result = dao.get_by_batch_and_role(db, batch_id=b1.id, item_role="inp", workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] BIT-R-08
def test_bit_r_08__the_end_of_a_role_finds_nothing(db, w1, b1, i1, mk_line):
    """BIT-R-08 — the end of a role finds nothing.
    Rules: `get_by_batch_and_role` R2"""
    mk_line(item_role="input", item_id=i1.id)

    result = dao.get_by_batch_and_role(db, batch_id=b1.id, item_role="put", workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] BIT-R-09
def test_bit_r_09__is_no_wildcard_in_a_role(db, w1, b1, i1, mk_line):
    """BIT-R-09 — _ is no wildcard in a role.
    Rules: `get_by_batch_and_role` R2"""
    mk_line(item_role="input", item_id=i1.id)

    result = dao.get_by_batch_and_role(db, batch_id=b1.id, item_role="i_put", workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] BIT-R-10
def test_bit_r_10__is_no_wildcard_in_a_role(db, w1, b1, i1, mk_line):
    """BIT-R-10 — % is no wildcard in a role.
    Rules: `get_by_batch_and_role` R2"""
    mk_line(item_role="input", item_id=i1.id)

    result = dao.get_by_batch_and_role(db, batch_id=b1.id, item_role="%", workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] BIT-R-11
def test_bit_r_11__an_unknown_role_finds_nothing(db, w1, b1, i1, mk_line):
    """BIT-R-11 — an unknown role finds nothing.
    Rules: `get_by_batch_and_role` R2"""
    mk_line(item_role="input", item_id=i1.id)

    result = dao.get_by_batch_and_role(db, batch_id=b1.id, item_role="zzz", workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] BIT-R-12
def test_bit_r_12__a_stored_role_with_a_space_is_not_found_the_stored_side_is_not_trimmed(db, w1, b1, i1, mk_line):
    """BIT-R-12 — a stored role with a space is not found: the stored side is not trimmed.
    Rules: `get_by_batch_and_role` R2"""
    mk_line(item_role=" input", item_id=i1.id)

    result = dao.get_by_batch_and_role(db, batch_id=b1.id, item_role="input", workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] BIT-R-13
def test_bit_r_13__a_stored_role_in_capitals_is_not_found(db, w1, b1, i1, mk_line):
    """BIT-R-13 — a stored role in capitals is not found.
    Rules: `get_by_batch_and_role` R2"""
    mk_line(item_role="INPUT", item_id=i1.id)

    result = dao.get_by_batch_and_role(db, batch_id=b1.id, item_role="input", workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] BIT-R-14
def test_bit_r_14__an_unknown_parent_returns_an_empty_list(db, w1, i1, mk_line):
    """BIT-R-14 — an unknown parent returns an empty list.
    Rules: `get_by_batch_and_role` R2"""
    mk_line(item_role="input", item_id=i1.id)

    result = dao.get_by_batch_and_role(db, batch_id=MISSING, item_role="input", workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] BIT-R-15
def test_bit_r_15__batch_id_0_returns_an_empty_list(db, w1, i1, mk_line):
    """BIT-R-15 — batch_id=0 returns an empty list.
    Rules: `get_by_batch_and_role` R2"""
    mk_line(item_role="input", item_id=i1.id)

    result = dao.get_by_batch_and_role(db, batch_id=0, item_role="input", workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] BIT-R-16
@pytest.mark.xfail(strict=True, reason="BUG-1323: A batch's lines of one role have no sort order")
def test_bit_r_16__the_query_orders_by_id_ascending(db, w1, b1, i1, mk_line, recorder):
    """BIT-R-16 — the query orders by id, ascending.
    Rules: `get_by_batch_and_role` R3 [BUG-1323]"""
    a = mk_line(item_role="input", item_id=i1.id)

    recorder.start()
    result = dao.get_by_batch_and_role(db, batch_id=b1.id, item_role="input", workspace_id=w1.id)

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


# [claude] BIT-R-17
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1323: A batch's lines of one role have no sort order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_bit_r_17__lines_come_back_by_id_when_the_lowest_id_was_updated(db, w1, b1, i1, i2, i3, mk_line):
    """BIT-R-17 — lines come back by id, when the lowest id was updated.
    Rules: `get_by_batch_and_role` R3 [BUG-1323]"""
    seqscan(db)
    a = mk_line(item_role="input", item_id=i1.id, expected_quantity=7)
    b = mk_line(item_role="input", item_id=i2.id, expected_quantity=9)
    c = mk_line(item_role="input", item_id=i3.id, expected_quantity=5)
    a.expected_quantity = 8
    db.flush()
    db.expire_all()

    result = dao.get_by_batch_and_role(db, batch_id=b1.id, item_role="input", workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [a.id, b.id, c.id]


# [claude] BIT-R-18
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1323: A batch's lines of one role have no sort order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_bit_r_18__lines_come_back_by_id_when_item_and_quantity_would_each_sort_otherwise(db, w1, b1, i1, i2, i3, mk_line):
    """BIT-R-18 — lines come back by id, when item and quantity would each sort otherwise.
    Rules: `get_by_batch_and_role` R3 [BUG-1323]"""
    seqscan(db)
    a = mk_line(item_role="input", item_id=i3.id, expected_quantity=7)
    b = mk_line(item_role="input", item_id=i1.id, expected_quantity=9)
    c = mk_line(item_role="input", item_id=i2.id, expected_quantity=5)
    db.expire_all()

    result = dao.get_by_batch_and_role(db, batch_id=b1.id, item_role="input", workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [a.id, b.id, c.id]


# [claude] BIT-R-19
def test_bit_r_19__there_is_no_cap_101_lines_give_101_rows(db, w1, b1, new_line):
    """BIT-R-19 — there is no cap: 101 lines give 101 rows.
    Rules: `get_by_batch_and_role` R4"""
    rows = [new_line() for k in range(1, 102)]
    add_many(db, rows)
    newest = [row.id for row in rows]

    result = dao.get_by_batch_and_role(db, batch_id=b1.id, item_role="input", workspace_id=w1.id)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert sorted(ids(result)) == sorted(newest)


# [claude] BIT-R-20
def test_bit_r_20__a_line_of_a_cancelled_batch_is_returned(db, w1, bc, i1, mk_line):
    """BIT-R-20 — a line of a cancelled batch is returned.
    Rules: `get_by_batch_and_role` R5"""
    a = mk_line(item_role="input", item_id=i1.id, batch_id=bc.id)

    result = dao.get_by_batch_and_role(db, batch_id=bc.id, item_role="input", workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] BIT-R-21
def test_bit_r_21__a_line_of_a_removed_item_is_returned(db, w1, b1, ix, mk_line):
    """BIT-R-21 — a line of a removed item is returned.
    Rules: `get_by_batch_and_role` R5"""
    a = mk_line(item_role="input", item_id=ix.id)

    result = dao.get_by_batch_and_role(db, batch_id=b1.id, item_role="input", workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] BIT-R-22
def test_bit_r_22__the_query_does_not_read_the_parent_tables(db, w1, b1, i1, mk_line, recorder):
    """BIT-R-22 — the query does not read the parent tables.
    Rules: `get_by_batch_and_role` R5"""
    mk_line(item_role="input", item_id=i1.id)

    recorder.start()
    result = dao.get_by_batch_and_role(db, batch_id=b1.id, item_role="input", workspace_id=w1.id)

    # Then 1
    assert len(result) == 1
    # Then 2
    sql = recorder.sql()
    assert "JOIN" not in sql


# [claude] BIT-R-23
def test_bit_r_23__writes_nothing_a_pending_row_that_would_sort_first_stays_pending_and_i(db, w1, b1, i1, i2, mk_line, recorder):
    """BIT-R-23 — writes nothing: a pending row that would sort first stays pending and is not returned.
    Rules: `get_by_batch_and_role` Side effects"""
    a = mk_line(item_role="input", item_id=i2.id)
    p = ProductionBatchItem(workspace_id=w1.id, batch_id=b1.id, item_id=i1.id, item_role="input")
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    recorder.start()
    result = dao.get_by_batch_and_role(db, batch_id=b1.id, item_role="input", workspace_id=w1.id)

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


# [claude] BIT-R-24
def test_bit_r_24__writes_nothing_a_read_leaves_the_caller_s_unflushed_edit_alone(db, w1, b1, i1, i2, mk_line):
    """BIT-R-24 — writes nothing: a read leaves the caller's unflushed edit alone.
    Rules: `get_by_batch_and_role` Side effects"""
    a = mk_line(item_role="input", item_id=i1.id)
    b = mk_line(item_role="input", item_id=i2.id)
    b.notes = "Edited"

    result = dao.get_by_batch_and_role(db, batch_id=b1.id, item_role="input", workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert b.notes == "Edited"


# [claude] BIT-R-25
def test_bit_r_25__a_w2_line_on_the_w1_parent_is_not_returned_for_w1(db, w1, w2, b1, i1, mk_line):
    """BIT-R-25 — a W2 line on the W1 parent is not returned for W1.
    Rules: `get_by_batch_and_role` R1"""
    mk_line(item_role="input", item_id=i1.id, workspace_id=w2.id)

    result = dao.get_by_batch_and_role(db, batch_id=b1.id, item_role="input", workspace_id=w1.id)

    # Then 1
    assert result == []


# --------------------------------------------------------------------------- #
# ProductionBatchItemDAO.get_by_id_and_workspace
# --------------------------------------------------------------------------- #


# [claude] BIT-I-01
def test_bit_i_01__returns_the_row_with_that_id(db, w1, b1, i1, i2, mk_line):
    """BIT-I-01 — returns the row with that id.
    Rules: `get_by_id_and_workspace` R1, Returns"""
    mk_line(item_role="input", item_id=i2.id)
    a = mk_line(item_role="input", item_id=i1.id)

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, ProductionBatchItem)
    # Then 2
    assert result.id == a.id
    # Then 3
    assert result.batch_id == b1.id
    assert result.workspace_id == w1.id
    assert result.item_role == "input"


# [claude] BIT-I-02
def test_bit_i_02__another_workspace_s_id_returns_none_when_that_row_is_the_later_one(db, w1, w2, b9, i1, i9, mk_line):
    """BIT-I-02 — another workspace's id returns None, when that row is the later one.
    Rules: `get_by_id_and_workspace` R2"""
    mk_line(item_role="input", item_id=i1.id)
    z = mk_line(item_id=i9.id, item_role="input", workspace_id=w2.id, batch_id=b9.id)

    result = dao.get_by_id_and_workspace(db, id=z.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] BIT-I-03
def test_bit_i_03__another_workspace_s_id_returns_none_when_that_row_is_the_earlier_one(db, w1, w2, b9, i1, i9, mk_line):
    """BIT-I-03 — another workspace's id returns None, when that row is the earlier one.
    Rules: `get_by_id_and_workspace` R2"""
    z = mk_line(item_id=i9.id, item_role="input", workspace_id=w2.id, batch_id=b9.id)
    mk_line(item_role="input", item_id=i1.id)

    result = dao.get_by_id_and_workspace(db, id=z.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] BIT-I-04
def test_bit_i_04__the_id_under_another_workspace_returns_none(db, w2, i1, mk_line):
    """BIT-I-04 — the id under another workspace returns None.
    Rules: `get_by_id_and_workspace` R2"""
    a = mk_line(item_role="input", item_id=i1.id)

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w2.id)

    # Then 1
    assert result is None


# [claude] BIT-I-05
def test_bit_i_05__an_unknown_id_returns_none(db, w1, i1, mk_line):
    """BIT-I-05 — an unknown id returns None.
    Rules: `get_by_id_and_workspace` R3"""
    mk_line(item_role="input", item_id=i1.id)

    result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] BIT-I-06
def test_bit_i_06__id_0_returns_none(db, w1, i1, mk_line):
    """BIT-I-06 — id=0 returns None.
    Rules: `get_by_id_and_workspace` R3"""
    mk_line(item_role="input", item_id=i1.id)

    result = dao.get_by_id_and_workspace(db, id=0, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] BIT-I-07
def test_bit_i_07__writes_nothing_a_read_that_finds_nothing_leaves_the_session_as_it_was(db, w1, b1, i1, mk_line, recorder):
    """BIT-I-07 — writes nothing: a read that finds nothing leaves the session as it was.
    Rules: `get_by_id_and_workspace` R3, Side effects"""
    a = mk_line(item_role="input", item_id=i1.id)
    p = ProductionBatchItem(workspace_id=w1.id, batch_id=b1.id, item_id=i1.id, item_role="input")
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


# [claude] BIT-I-08
def test_bit_i_08__writes_nothing_a_read_that_finds_its_row_leaves_the_session_as_it_was(db, w1, b1, i1, mk_line, recorder):
    """BIT-I-08 — writes nothing: a read that finds its row leaves the session as it was.
    Rules: `get_by_id_and_workspace` Side effects"""
    a = mk_line(item_role="input", item_id=i1.id)
    p = ProductionBatchItem(workspace_id=w1.id, batch_id=b1.id, item_id=i1.id, item_role="input")
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


# [claude] BIT-I-09
def test_bit_i_09__writes_nothing_a_read_leaves_the_caller_s_unflushed_edit_alone(db, w1, i1, i2, mk_line):
    """BIT-I-09 — writes nothing: a read leaves the caller's unflushed edit alone.
    Rules: `get_by_id_and_workspace` Side effects"""
    a = mk_line(item_role="input", item_id=i1.id)
    b = mk_line(item_role="input", item_id=i2.id)
    b.notes = "Edited"

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert b.notes == "Edited"


# [claude] BIT-I-10
def test_bit_i_10__a_line_of_a_cancelled_batch_is_returned(db, w1, bc, i1, mk_line):
    """BIT-I-10 — a line of a cancelled batch is returned.
    Rules: `get_by_id_and_workspace` R4"""
    a = mk_line(item_role="input", item_id=i1.id, batch_id=bc.id)

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id


# [claude] BIT-I-11
def test_bit_i_11__a_line_of_a_removed_item_is_returned(db, w1, ix, mk_line):
    """BIT-I-11 — a line of a removed item is returned.
    Rules: `get_by_id_and_workspace` R4"""
    a = mk_line(item_role="input", item_id=ix.id)

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id


# [claude] BIT-I-12
def test_bit_i_12__the_query_does_not_read_the_parent_tables(db, w1, i1, mk_line, recorder):
    """BIT-I-12 — the query does not read the parent tables.
    Rules: `get_by_id_and_workspace` R4"""
    a = mk_line(item_role="input", item_id=i1.id)

    recorder.start()
    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    sql = recorder.sql()
    assert "JOIN" not in sql


# --------------------------------------------------------------------------- #
# Inherited BaseDAO methods on ProductionBatchItem
# --------------------------------------------------------------------------- #


# [claude] BIT-INH-01
def test_bit_inh_01__create_with_a_dict_leaves_the_optional_columns_none(db, w1, b1, i1):
    """BIT-INH-01 — create with a dict leaves the optional columns None.
    Rules: `inherited` R1"""
    result = dao.create(db, obj_in={"workspace_id": w1.id, "batch_id": b1.id, "item_id": i1.id, "item_role": "input"})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.item_role == "input"
    # Then 3
    row = reread(db, result)
    assert row.expected_quantity is None
    assert row.actual_quantity is None
    # Then 4
    row = reread(db, result)
    assert row.source_location_type is None
    assert row.source_location_id is None
    assert row.destination_location_type is None
    assert row.destination_location_id is None
    # Then 5
    row = reread(db, result)
    assert row.notes is None


# [claude] BIT-INH-02
def test_bit_inh_02__create_with_a_productionbatchitemcreate_fails_on_flush_and_saves_nothi(db, b1, i1):
    """BIT-INH-02 — create with a ProductionBatchItemCreate fails on flush and saves nothing.
    Rules: `inherited` R2"""
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in=ProductionBatchItemCreate(batch_id=b1.id, item_id=i1.id, item_role="input"))
    # Then 2
    assert exc.value.orig.pgcode == "23502"
    # Then 3
    assert count_rows(db, ProductionBatchItem) == 0


# [claude] BIT-INH-03
def test_bit_inh_03__an_odd_role_is_stored(db, w1, b1, i1):
    """BIT-INH-03 — an odd role is stored.
    Rules: `inherited` R3"""
    result = dao.create(db, obj_in={"workspace_id": w1.id, "batch_id": b1.id, "item_id": i1.id, "item_role": "zz"})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.item_role == "zz"


# [claude] BIT-INH-04
def test_bit_inh_04__a_negative_expected_quantity_is_stored(db, w1, b1, i1):
    """BIT-INH-04 — a negative expected quantity is stored.
    Rules: `inherited` R3"""
    result = dao.create(db, obj_in={"workspace_id": w1.id, "batch_id": b1.id, "item_id": i1.id, "item_role": "input", "expected_quantity": -1})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.expected_quantity == -1


# [claude] BIT-INH-05
def test_bit_inh_05__a_zero_actual_quantity_is_stored(db, w1, b1, i1):
    """BIT-INH-05 — a zero actual quantity is stored.
    Rules: `inherited` R3"""
    result = dao.create(db, obj_in={"workspace_id": w1.id, "batch_id": b1.id, "item_id": i1.id, "item_role": "input", "actual_quantity": 0})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.actual_quantity == 0


# [claude] BIT-INH-06
def test_bit_inh_06__update_with_a_schema_applies_the_fields_set_to_a_value(db, i1, mk_line):
    """BIT-INH-06 — update with a schema applies the fields set to a value.
    Rules: `inherited` R4"""
    a = mk_line(item_role="input", item_id=i1.id, actual_quantity=2, notes="Keep")

    result = dao.update(db, db_obj=a, obj_in=ProductionBatchItemUpdate(actual_quantity=5, notes=None))

    # Then 1
    assert result.id == a.id
    # Then 2
    row = reread(db, a)
    assert row.actual_quantity == 5
    assert row.notes == "Keep"


# [claude] BIT-INH-07
def test_bit_inh_07__remove_hard_deletes_the_row(db, i1, i2, mk_line):
    """BIT-INH-07 — remove hard-deletes the row.
    Rules: `inherited` R5"""
    a = mk_line(item_role="input", item_id=i1.id)
    b = mk_line(item_role="input", item_id=i2.id)
    before_b = snap(db, b)

    result = dao.remove(db, id=a.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert count_rows(db, ProductionBatchItem) == 1
    # Then 3
    db.expire_all()
    assert snap(db, b) == before_b
