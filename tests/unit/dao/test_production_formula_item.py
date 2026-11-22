"""Unit tests for app/dao/production_formula_item.py.

Implements tests/unit/dao/production_formula_item.cases.md, one test per case, in card order. Real
Postgres session (`db` fixture).
Nothing is mocked and no clock is patched (Conventions, Externals).

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117, DTZ001  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested():`, and naive datetimes)
from datetime import datetime

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError

from app.dao.production_formula_item import production_formula_item_dao
from app.models.item import Item
from app.models.production_formula import ProductionFormula
from app.models.production_formula_item import ProductionFormulaItem
from app.schemas.production_formula_item import (
    ProductionFormulaItemCreate,
    ProductionFormulaItemUpdate,
)
from tests.unit.factories import make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton production_formula_item_dao" (a module-level name, not a fixture)
dao = production_formula_item_dao

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
def pf1(db, w1, w2):
    return _add(db, ProductionFormula(workspace_id=w1.id, formula_code="FM-1", name="Yarn"))


@pytest.fixture
def pf2(db, w1, pf1):
    return _add(db, ProductionFormula(workspace_id=w1.id, formula_code="FM-2", name="Rope"))


@pytest.fixture
def pfd(db, w1, pf2):
    return _add(db, ProductionFormula(workspace_id=w1.id, formula_code="FM-3", name="Twine", is_active=False, is_default=False))


@pytest.fixture
def pf9(db, w2, pfd):
    return _add(db, ProductionFormula(workspace_id=w2.id, formula_code="FM-9", name="Far"))


@pytest.fixture
def i1(db, w1, pf9):
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
def standing_rows(w1, w2, pf1, pf2, pfd, pf9, i1, i2, i3, ix, i9):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builders (fixtures; each mk_ flushes before it returns)
# --------------------------------------------------------------------------- #

# Convention "line"
@pytest.fixture
def new_line(w1, pf1, i1):
    """new_line(**columns) -> ProductionFormulaItem, not added."""
    def _new(**columns):
        return ProductionFormulaItem(**{"workspace_id": w1.id, "formula_id": pf1.id, "item_id": i1.id, "item_role": "input", "quantity": 2, **columns})
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


# Convention "nothing written": the number of `production_formula_items` rows stored (all workspaces)
def stored_count(db):
    return db.scalar(select(func.count()).select_from(ProductionFormulaItem.__table__))


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
        """The one SELECT from `production_formula_items`; fails loudly unless there is exactly one."""
        [statement] = [s for s in self.selects() if "FROM production_formula_items" in s]
        return statement


@pytest.fixture
def recorder(db):
    statement_recorder = StatementRecorder(db)
    yield statement_recorder
    statement_recorder.stop()


# --------------------------------------------------------------------------- #
# ProductionFormulaItemDAO.get_by_formula
# --------------------------------------------------------------------------- #


# [claude] PFI-G-01
def test_pfi_g_01__returns_a_list_of_the_parent_s_lines_of_every_role(db, w1, pf1, i1, i2, i3, mk_line):
    """PFI-G-01 — returns a list of the parent's lines, of every role.
    Rules: `get_by_formula` R1, Returns"""
    a = mk_line(item_role="input", item_id=i1.id)
    b = mk_line(item_role="output", item_id=i2.id)
    c = mk_line(item_role="waste", item_id=i3.id)
    d = mk_line(item_role="byproduct", item_id=i1.id)

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert sorted(ids(result)) == [a.id, b.id, c.id, d.id]
    # Then 3
    assert isinstance(result[0], ProductionFormulaItem)


# [claude] PFI-G-02
def test_pfi_g_02__a_line_of_another_parent_is_not_returned(db, w1, pf1, pf2, i1, i2, mk_line):
    """PFI-G-02 — a line of another parent is not returned.
    Rules: `get_by_formula` R1"""
    mk_line(item_role="input", item_id=i1.id, formula_id=pf2.id)
    a = mk_line(item_role="input", item_id=i2.id)

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] PFI-G-03
def test_pfi_g_03__the_right_parent_under_another_workspace_returns_an_empty_list(db, w2, pf1, i1, mk_line):
    """PFI-G-03 — the right parent under another workspace returns an empty list.
    Rules: `get_by_formula` R1"""
    mk_line(item_role="input", item_id=i1.id)

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] PFI-G-04
def test_pfi_g_04__a_w2_row_on_a_w1_parent_is_returned_for_w2(db, w2, pf1, i1, mk_line):
    """PFI-G-04 — a W2 row on a W1 parent is returned for W2.
    Rules: `get_by_formula` R1"""
    a = mk_line(item_role="input", item_id=i1.id, workspace_id=w2.id)

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w2.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] PFI-G-05
def test_pfi_g_05__a_w2_row_on_a_w1_parent_is_not_returned_for_w1(db, w1, w2, pf1, i1, mk_line):
    """PFI-G-05 — a W2 row on a W1 parent is not returned for W1.
    Rules: `get_by_formula` R1"""
    mk_line(item_role="input", item_id=i1.id, workspace_id=w2.id)

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PFI-G-06
def test_pfi_g_06__an_unknown_parent_returns_an_empty_list(db, w1, i1, mk_line):
    """PFI-G-06 — an unknown parent returns an empty list.
    Rules: `get_by_formula` R2"""
    mk_line(item_role="input", item_id=i1.id)

    result = dao.get_by_formula(db, formula_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PFI-G-07
def test_pfi_g_07__formula_id_0_returns_an_empty_list(db, w1, i1, mk_line):
    """PFI-G-07 — formula_id=0 returns an empty list.
    Rules: `get_by_formula` R2"""
    mk_line(item_role="input", item_id=i1.id)

    result = dao.get_by_formula(db, formula_id=0, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PFI-G-08
def test_pfi_g_08__a_parent_with_no_lines_returns_an_empty_list(db, w1, pf2, i1, mk_line):
    """PFI-G-08 — a parent with no lines returns an empty list.
    Rules: `get_by_formula` R2"""
    mk_line(item_role="input", item_id=i1.id)

    result = dao.get_by_formula(db, formula_id=pf2.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PFI-G-09
@pytest.mark.xfail(strict=True, reason="BUG-1319: A formula's lines have no sort order")
def test_pfi_g_09__the_query_orders_by_id_ascending(db, w1, pf1, i1, mk_line, recorder):
    """PFI-G-09 — the query orders by id, ascending.
    Rules: `get_by_formula` R3 [BUG-1319]"""
    a = mk_line(item_role="input", item_id=i1.id)

    recorder.start()
    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id)

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


# [claude] PFI-G-10
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1319: A formula's lines have no sort order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_pfi_g_10__lines_come_back_by_id_when_the_lowest_id_was_updated(db, w1, pf1, i1, i2, i3, mk_line):
    """PFI-G-10 — lines come back by id, when the lowest id was updated.
    Rules: `get_by_formula` R3 [BUG-1319]"""
    seqscan(db)
    a = mk_line(item_role="input", item_id=i1.id, quantity=7)
    b = mk_line(item_role="input", item_id=i2.id, quantity=9)
    c = mk_line(item_role="input", item_id=i3.id, quantity=5)
    a.quantity = 8
    db.flush()
    db.expire_all()

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [a.id, b.id, c.id]


# [claude] PFI-G-11
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1319: A formula's lines have no sort order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_pfi_g_11__lines_come_back_by_id_when_item_role_and_quantity_would_each_sort_othe(db, w1, pf1, i1, i2, i3, mk_line):
    """PFI-G-11 — lines come back by id, when item, role and quantity would each sort otherwise.
    Rules: `get_by_formula` R3 [BUG-1319]"""
    seqscan(db)
    a = mk_line(item_role="output", item_id=i3.id, quantity=7)
    b = mk_line(item_role="waste", item_id=i1.id, quantity=9)
    c = mk_line(item_role="byproduct", item_id=i2.id, quantity=5)
    db.expire_all()

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [a.id, b.id, c.id]


# [claude] PFI-G-12
def test_pfi_g_12__there_is_no_cap_101_lines_give_101_rows(db, w1, pf1, new_line):
    """PFI-G-12 — there is no cap: 101 lines give 101 rows.
    Rules: `get_by_formula` R4"""
    rows = [new_line() for k in range(1, 102)]
    add_many(db, rows)
    newest = [row.id for row in rows]

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert sorted(ids(result)) == sorted(newest)


# [claude] PFI-G-13
def test_pfi_g_13__a_line_of_a_deactivated_formula_is_returned(db, w1, pfd, i1, mk_line):
    """PFI-G-13 — a line of a deactivated formula is returned.
    Rules: `get_by_formula` R5"""
    a = mk_line(item_role="input", item_id=i1.id, formula_id=pfd.id)

    result = dao.get_by_formula(db, formula_id=pfd.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] PFI-G-14
def test_pfi_g_14__a_line_of_a_removed_item_is_returned(db, w1, pf1, ix, mk_line):
    """PFI-G-14 — a line of a removed item is returned.
    Rules: `get_by_formula` R5"""
    a = mk_line(item_role="input", item_id=ix.id)

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] PFI-G-15
def test_pfi_g_15__two_lines_with_one_item_and_role_are_both_returned(db, w1, pf1, i1, mk_line):
    """PFI-G-15 — two lines with one item and role are both returned.
    Rules: `get_by_formula` R6"""
    a = mk_line(item_role="input", item_id=i1.id)
    b = mk_line(item_role="input", item_id=i1.id)

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]


# [claude] PFI-G-16
def test_pfi_g_16__the_query_does_not_read_the_parent_tables(db, w1, pf1, i1, mk_line, recorder):
    """PFI-G-16 — the query does not read the parent tables.
    Rules: `get_by_formula` R5"""
    mk_line(item_role="input", item_id=i1.id)

    recorder.start()
    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 1
    # Then 2
    sql = recorder.sql()
    assert "JOIN" not in sql


# [claude] PFI-G-17
def test_pfi_g_17__writes_nothing_a_pending_row_that_would_sort_first_stays_pending_and_i(db, w1, pf1, i1, i2, mk_line, recorder):
    """PFI-G-17 — writes nothing: a pending row that would sort first stays pending and is not returned.
    Rules: `get_by_formula` Side effects"""
    a = mk_line(item_role="input", item_id=i2.id)
    p = ProductionFormulaItem(workspace_id=w1.id, formula_id=pf1.id, item_id=i1.id, item_role="input", quantity=1)
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    recorder.start()
    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id)

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


# [claude] PFI-G-18
def test_pfi_g_18__writes_nothing_a_read_leaves_the_caller_s_unflushed_edit_alone(db, w1, pf1, i1, i2, mk_line):
    """PFI-G-18 — writes nothing: a read leaves the caller's unflushed edit alone.
    Rules: `get_by_formula` Side effects"""
    a = mk_line(item_role="input", item_id=i1.id)
    b = mk_line(item_role="input", item_id=i2.id)
    b.quantity = 44

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert b.quantity == 44


# --------------------------------------------------------------------------- #
# ProductionFormulaItemDAO.get_by_formula_and_role
# --------------------------------------------------------------------------- #


# [claude] PFI-R-01
def test_pfi_r_01__returns_a_list_of_the_lines_of_that_parent_and_role(db, w1, pf1, i1, i2, i3, mk_line):
    """PFI-R-01 — returns a list of the lines of that parent and role.
    Rules: `get_by_formula_and_role` R1, Returns"""
    a = mk_line(item_role="input", item_id=i1.id)
    mk_line(item_role="output", item_id=i2.id)
    b = mk_line(item_role="input", item_id=i3.id)

    result = dao.get_by_formula_and_role(db, formula_id=pf1.id, item_role="input", workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 3
    assert isinstance(result[0], ProductionFormulaItem)


# [claude] PFI-R-02
def test_pfi_r_02__a_line_of_another_parent_is_not_returned(db, w1, pf1, pf2, i1, i2, mk_line):
    """PFI-R-02 — a line of another parent is not returned.
    Rules: `get_by_formula_and_role` R1"""
    mk_line(item_role="input", item_id=i1.id, formula_id=pf2.id)
    a = mk_line(item_role="input", item_id=i2.id)

    result = dao.get_by_formula_and_role(db, formula_id=pf1.id, item_role="input", workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] PFI-R-03
def test_pfi_r_03__the_right_parent_and_role_under_another_workspace_returns_an_empty_lis(db, w2, pf1, i1, mk_line):
    """PFI-R-03 — the right parent and role under another workspace returns an empty list.
    Rules: `get_by_formula_and_role` R1"""
    mk_line(item_role="input", item_id=i1.id)

    result = dao.get_by_formula_and_role(db, formula_id=pf1.id, item_role="input", workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] PFI-R-04
def test_pfi_r_04__two_lines_with_one_item_and_role_are_both_returned(db, w1, pf1, i1, mk_line):
    """PFI-R-04 — two lines with one item and role are both returned.
    Rules: `get_by_formula_and_role` R1"""
    a = mk_line(item_role="input", item_id=i1.id)
    b = mk_line(item_role="input", item_id=i1.id)

    result = dao.get_by_formula_and_role(db, formula_id=pf1.id, item_role="input", workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]


# [claude] PFI-R-05
def test_pfi_r_05__a_role_in_capitals_finds_nothing(db, w1, pf1, i1, mk_line):
    """PFI-R-05 — a role in capitals finds nothing.
    Rules: `get_by_formula_and_role` R2"""
    mk_line(item_role="input", item_id=i1.id)

    result = dao.get_by_formula_and_role(db, formula_id=pf1.id, item_role="INPUT", workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PFI-R-06
def test_pfi_r_06__a_leading_space_in_the_role_finds_nothing(db, w1, pf1, i1, mk_line):
    """PFI-R-06 — a leading space in the role finds nothing.
    Rules: `get_by_formula_and_role` R2"""
    mk_line(item_role="input", item_id=i1.id)

    result = dao.get_by_formula_and_role(db, formula_id=pf1.id, item_role=" input", workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PFI-R-07
def test_pfi_r_07__the_start_of_a_role_finds_nothing(db, w1, pf1, i1, mk_line):
    """PFI-R-07 — the start of a role finds nothing.
    Rules: `get_by_formula_and_role` R2"""
    mk_line(item_role="input", item_id=i1.id)

    result = dao.get_by_formula_and_role(db, formula_id=pf1.id, item_role="inp", workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PFI-R-08
def test_pfi_r_08__the_end_of_a_role_finds_nothing(db, w1, pf1, i1, mk_line):
    """PFI-R-08 — the end of a role finds nothing.
    Rules: `get_by_formula_and_role` R2"""
    mk_line(item_role="input", item_id=i1.id)

    result = dao.get_by_formula_and_role(db, formula_id=pf1.id, item_role="put", workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PFI-R-09
def test_pfi_r_09__is_no_wildcard_in_a_role(db, w1, pf1, i1, mk_line):
    """PFI-R-09 — _ is no wildcard in a role.
    Rules: `get_by_formula_and_role` R2"""
    mk_line(item_role="input", item_id=i1.id)

    result = dao.get_by_formula_and_role(db, formula_id=pf1.id, item_role="i_put", workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PFI-R-10
def test_pfi_r_10__is_no_wildcard_in_a_role(db, w1, pf1, i1, mk_line):
    """PFI-R-10 — % is no wildcard in a role.
    Rules: `get_by_formula_and_role` R2"""
    mk_line(item_role="input", item_id=i1.id)

    result = dao.get_by_formula_and_role(db, formula_id=pf1.id, item_role="%", workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PFI-R-11
def test_pfi_r_11__an_unknown_role_finds_nothing(db, w1, pf1, i1, mk_line):
    """PFI-R-11 — an unknown role finds nothing.
    Rules: `get_by_formula_and_role` R2"""
    mk_line(item_role="input", item_id=i1.id)

    result = dao.get_by_formula_and_role(db, formula_id=pf1.id, item_role="zzz", workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PFI-R-12
def test_pfi_r_12__a_stored_role_with_a_space_is_not_found_the_stored_side_is_not_trimmed(db, w1, pf1, i1, mk_line):
    """PFI-R-12 — a stored role with a space is not found: the stored side is not trimmed.
    Rules: `get_by_formula_and_role` R2"""
    mk_line(item_role=" input", item_id=i1.id)

    result = dao.get_by_formula_and_role(db, formula_id=pf1.id, item_role="input", workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PFI-R-13
def test_pfi_r_13__a_stored_role_in_capitals_is_not_found(db, w1, pf1, i1, mk_line):
    """PFI-R-13 — a stored role in capitals is not found.
    Rules: `get_by_formula_and_role` R2"""
    mk_line(item_role="INPUT", item_id=i1.id)

    result = dao.get_by_formula_and_role(db, formula_id=pf1.id, item_role="input", workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PFI-R-14
def test_pfi_r_14__an_unknown_parent_returns_an_empty_list(db, w1, i1, mk_line):
    """PFI-R-14 — an unknown parent returns an empty list.
    Rules: `get_by_formula_and_role` R2"""
    mk_line(item_role="input", item_id=i1.id)

    result = dao.get_by_formula_and_role(db, formula_id=MISSING, item_role="input", workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PFI-R-15
def test_pfi_r_15__formula_id_0_returns_an_empty_list(db, w1, i1, mk_line):
    """PFI-R-15 — formula_id=0 returns an empty list.
    Rules: `get_by_formula_and_role` R2"""
    mk_line(item_role="input", item_id=i1.id)

    result = dao.get_by_formula_and_role(db, formula_id=0, item_role="input", workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PFI-R-16
@pytest.mark.xfail(strict=True, reason="BUG-1320: A formula's lines of one role have no sort order")
def test_pfi_r_16__the_query_orders_by_id_ascending(db, w1, pf1, i1, mk_line, recorder):
    """PFI-R-16 — the query orders by id, ascending.
    Rules: `get_by_formula_and_role` R3 [BUG-1320]"""
    a = mk_line(item_role="input", item_id=i1.id)

    recorder.start()
    result = dao.get_by_formula_and_role(db, formula_id=pf1.id, item_role="input", workspace_id=w1.id)

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


# [claude] PFI-R-17
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1320: A formula's lines of one role have no sort order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_pfi_r_17__lines_come_back_by_id_when_the_lowest_id_was_updated(db, w1, pf1, i1, i2, i3, mk_line):
    """PFI-R-17 — lines come back by id, when the lowest id was updated.
    Rules: `get_by_formula_and_role` R3 [BUG-1320]"""
    seqscan(db)
    a = mk_line(item_role="input", item_id=i1.id, quantity=7)
    b = mk_line(item_role="input", item_id=i2.id, quantity=9)
    c = mk_line(item_role="input", item_id=i3.id, quantity=5)
    a.quantity = 8
    db.flush()
    db.expire_all()

    result = dao.get_by_formula_and_role(db, formula_id=pf1.id, item_role="input", workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [a.id, b.id, c.id]


# [claude] PFI-R-18
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1320: A formula's lines of one role have no sort order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_pfi_r_18__lines_come_back_by_id_when_item_and_quantity_would_each_sort_otherwise(db, w1, pf1, i1, i2, i3, mk_line):
    """PFI-R-18 — lines come back by id, when item and quantity would each sort otherwise.
    Rules: `get_by_formula_and_role` R3 [BUG-1320]"""
    seqscan(db)
    a = mk_line(item_role="input", item_id=i3.id, quantity=7)
    b = mk_line(item_role="input", item_id=i1.id, quantity=9)
    c = mk_line(item_role="input", item_id=i2.id, quantity=5)
    db.expire_all()

    result = dao.get_by_formula_and_role(db, formula_id=pf1.id, item_role="input", workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [a.id, b.id, c.id]


# [claude] PFI-R-19
def test_pfi_r_19__there_is_no_cap_101_lines_give_101_rows(db, w1, pf1, new_line):
    """PFI-R-19 — there is no cap: 101 lines give 101 rows.
    Rules: `get_by_formula_and_role` R4"""
    rows = [new_line() for k in range(1, 102)]
    add_many(db, rows)
    newest = [row.id for row in rows]

    result = dao.get_by_formula_and_role(db, formula_id=pf1.id, item_role="input", workspace_id=w1.id)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert sorted(ids(result)) == sorted(newest)


# [claude] PFI-R-20
def test_pfi_r_20__a_line_of_a_deactivated_formula_is_returned(db, w1, pfd, i1, mk_line):
    """PFI-R-20 — a line of a deactivated formula is returned.
    Rules: `get_by_formula_and_role` R5"""
    a = mk_line(item_role="input", item_id=i1.id, formula_id=pfd.id)

    result = dao.get_by_formula_and_role(db, formula_id=pfd.id, item_role="input", workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] PFI-R-21
def test_pfi_r_21__a_line_of_a_removed_item_is_returned(db, w1, pf1, ix, mk_line):
    """PFI-R-21 — a line of a removed item is returned.
    Rules: `get_by_formula_and_role` R5"""
    a = mk_line(item_role="input", item_id=ix.id)

    result = dao.get_by_formula_and_role(db, formula_id=pf1.id, item_role="input", workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] PFI-R-22
def test_pfi_r_22__the_query_does_not_read_the_parent_tables(db, w1, pf1, i1, mk_line, recorder):
    """PFI-R-22 — the query does not read the parent tables.
    Rules: `get_by_formula_and_role` R5"""
    mk_line(item_role="input", item_id=i1.id)

    recorder.start()
    result = dao.get_by_formula_and_role(db, formula_id=pf1.id, item_role="input", workspace_id=w1.id)

    # Then 1
    assert len(result) == 1
    # Then 2
    sql = recorder.sql()
    assert "JOIN" not in sql


# [claude] PFI-R-23
def test_pfi_r_23__writes_nothing_a_pending_row_that_would_sort_first_stays_pending_and_i(db, w1, pf1, i1, i2, mk_line, recorder):
    """PFI-R-23 — writes nothing: a pending row that would sort first stays pending and is not returned.
    Rules: `get_by_formula_and_role` Side effects"""
    a = mk_line(item_role="input", item_id=i2.id)
    p = ProductionFormulaItem(workspace_id=w1.id, formula_id=pf1.id, item_id=i1.id, item_role="input", quantity=1)
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    recorder.start()
    result = dao.get_by_formula_and_role(db, formula_id=pf1.id, item_role="input", workspace_id=w1.id)

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


# [claude] PFI-R-24
def test_pfi_r_24__writes_nothing_a_read_leaves_the_caller_s_unflushed_edit_alone(db, w1, pf1, i1, i2, mk_line):
    """PFI-R-24 — writes nothing: a read leaves the caller's unflushed edit alone.
    Rules: `get_by_formula_and_role` Side effects"""
    a = mk_line(item_role="input", item_id=i1.id)
    b = mk_line(item_role="input", item_id=i2.id)
    b.quantity = 44

    result = dao.get_by_formula_and_role(db, formula_id=pf1.id, item_role="input", workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert b.quantity == 44


# [claude] PFI-R-25
def test_pfi_r_25__a_w2_line_on_the_w1_parent_is_not_returned_for_w1(db, w1, w2, pf1, i1, mk_line):
    """PFI-R-25 — a W2 line on the W1 parent is not returned for W1.
    Rules: `get_by_formula_and_role` R1"""
    mk_line(item_role="input", item_id=i1.id, workspace_id=w2.id)

    result = dao.get_by_formula_and_role(db, formula_id=pf1.id, item_role="input", workspace_id=w1.id)

    # Then 1
    assert result == []


# --------------------------------------------------------------------------- #
# ProductionFormulaItemDAO.get_by_id_and_workspace
# --------------------------------------------------------------------------- #


# [claude] PFI-I-01
def test_pfi_i_01__returns_the_row_with_that_id(db, w1, pf1, i1, i2, mk_line):
    """PFI-I-01 — returns the row with that id.
    Rules: `get_by_id_and_workspace` R1, Returns"""
    mk_line(item_role="input", item_id=i2.id)
    a = mk_line(item_role="input", item_id=i1.id)

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, ProductionFormulaItem)
    # Then 2
    assert result.id == a.id
    # Then 3
    assert result.formula_id == pf1.id
    assert result.workspace_id == w1.id
    assert result.item_role == "input"
    assert result.quantity == 2


# [claude] PFI-I-02
def test_pfi_i_02__another_workspace_s_id_returns_none_when_that_row_is_the_later_one(db, w1, w2, pf9, i1, i9, mk_line):
    """PFI-I-02 — another workspace's id returns None, when that row is the later one.
    Rules: `get_by_id_and_workspace` R2"""
    mk_line(item_role="input", item_id=i1.id)
    z = mk_line(item_id=i9.id, item_role="input", workspace_id=w2.id, formula_id=pf9.id)

    result = dao.get_by_id_and_workspace(db, id=z.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] PFI-I-03
def test_pfi_i_03__another_workspace_s_id_returns_none_when_that_row_is_the_earlier_one(db, w1, w2, pf9, i1, i9, mk_line):
    """PFI-I-03 — another workspace's id returns None, when that row is the earlier one.
    Rules: `get_by_id_and_workspace` R2"""
    z = mk_line(item_id=i9.id, item_role="input", workspace_id=w2.id, formula_id=pf9.id)
    mk_line(item_role="input", item_id=i1.id)

    result = dao.get_by_id_and_workspace(db, id=z.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] PFI-I-04
def test_pfi_i_04__the_id_under_another_workspace_returns_none(db, w2, i1, mk_line):
    """PFI-I-04 — the id under another workspace returns None.
    Rules: `get_by_id_and_workspace` R2"""
    a = mk_line(item_role="input", item_id=i1.id)

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w2.id)

    # Then 1
    assert result is None


# [claude] PFI-I-05
def test_pfi_i_05__an_unknown_id_returns_none(db, w1, i1, mk_line):
    """PFI-I-05 — an unknown id returns None.
    Rules: `get_by_id_and_workspace` R3"""
    mk_line(item_role="input", item_id=i1.id)

    result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] PFI-I-06
def test_pfi_i_06__id_0_returns_none(db, w1, i1, mk_line):
    """PFI-I-06 — id=0 returns None.
    Rules: `get_by_id_and_workspace` R3"""
    mk_line(item_role="input", item_id=i1.id)

    result = dao.get_by_id_and_workspace(db, id=0, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] PFI-I-07
def test_pfi_i_07__writes_nothing_a_read_that_finds_nothing_leaves_the_session_as_it_was(db, w1, pf1, i1, mk_line, recorder):
    """PFI-I-07 — writes nothing: a read that finds nothing leaves the session as it was.
    Rules: `get_by_id_and_workspace` R3, Side effects"""
    a = mk_line(item_role="input", item_id=i1.id)
    p = ProductionFormulaItem(workspace_id=w1.id, formula_id=pf1.id, item_id=i1.id, item_role="input", quantity=1)
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


# [claude] PFI-I-08
def test_pfi_i_08__writes_nothing_a_read_that_finds_its_row_leaves_the_session_as_it_was(db, w1, pf1, i1, mk_line, recorder):
    """PFI-I-08 — writes nothing: a read that finds its row leaves the session as it was.
    Rules: `get_by_id_and_workspace` Side effects"""
    a = mk_line(item_role="input", item_id=i1.id)
    p = ProductionFormulaItem(workspace_id=w1.id, formula_id=pf1.id, item_id=i1.id, item_role="input", quantity=1)
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


# [claude] PFI-I-09
def test_pfi_i_09__writes_nothing_a_read_leaves_the_caller_s_unflushed_edit_alone(db, w1, i1, i2, mk_line):
    """PFI-I-09 — writes nothing: a read leaves the caller's unflushed edit alone.
    Rules: `get_by_id_and_workspace` Side effects"""
    a = mk_line(item_role="input", item_id=i1.id)
    b = mk_line(item_role="input", item_id=i2.id)
    b.quantity = 44

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert b.quantity == 44


# [claude] PFI-I-10
def test_pfi_i_10__a_line_of_a_deactivated_formula_is_returned(db, w1, pfd, i1, mk_line):
    """PFI-I-10 — a line of a deactivated formula is returned.
    Rules: `get_by_id_and_workspace` R4"""
    a = mk_line(item_role="input", item_id=i1.id, formula_id=pfd.id)

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id


# [claude] PFI-I-11
def test_pfi_i_11__a_line_of_a_removed_item_is_returned(db, w1, ix, mk_line):
    """PFI-I-11 — a line of a removed item is returned.
    Rules: `get_by_id_and_workspace` R4"""
    a = mk_line(item_role="input", item_id=ix.id)

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id


# [claude] PFI-I-12
def test_pfi_i_12__the_query_does_not_read_the_parent_tables(db, w1, i1, mk_line, recorder):
    """PFI-I-12 — the query does not read the parent tables.
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
# Inherited BaseDAO methods on ProductionFormulaItem
# --------------------------------------------------------------------------- #


# [claude] PFI-INH-01
def test_pfi_inh_01__create_with_a_dict_gives_the_defaults(db, w1, pf1, i1):
    """PFI-INH-01 — create with a dict gives the defaults.
    Rules: `inherited` R1"""
    result = dao.create(db, obj_in={"workspace_id": w1.id, "formula_id": pf1.id, "item_id": i1.id, "item_role": "input", "quantity": 2})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.item_role == "input"
    assert row.quantity == 2
    # Then 3
    row = reread(db, result)
    assert row.is_optional is False
    assert row.unit is None
    assert row.tolerance_percentage is None


# [claude] PFI-INH-02
def test_pfi_inh_02__create_with_a_productionformulaitemcreate_fails_on_flush_and_saves_not(db, pf1, i1):
    """PFI-INH-02 — create with a ProductionFormulaItemCreate fails on flush and saves nothing.
    Rules: `inherited` R2"""
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in=ProductionFormulaItemCreate(formula_id=pf1.id, item_id=i1.id, item_role="input", quantity=2))
    # Then 2
    assert exc.value.orig.pgcode == "23502"
    # Then 3
    assert count_rows(db, ProductionFormulaItem) == 0


# [claude] PFI-INH-03
def test_pfi_inh_03__an_odd_role_is_stored(db, w1, pf1, i1):
    """PFI-INH-03 — an odd role is stored.
    Rules: `inherited` R3"""
    result = dao.create(db, obj_in={"workspace_id": w1.id, "formula_id": pf1.id, "item_id": i1.id, "item_role": "zzz", "quantity": 2})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.item_role == "zzz"


# [claude] PFI-INH-04
def test_pfi_inh_04__a_zero_quantity_is_stored(db, w1, pf1, i1):
    """PFI-INH-04 — a zero quantity is stored.
    Rules: `inherited` R3"""
    result = dao.create(db, obj_in={"workspace_id": w1.id, "formula_id": pf1.id, "item_id": i1.id, "item_role": "input", "quantity": 0})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.quantity == 0


# [claude] PFI-INH-05
def test_pfi_inh_05__a_negative_quantity_is_stored(db, w1, pf1, i1):
    """PFI-INH-05 — a negative quantity is stored.
    Rules: `inherited` R3"""
    result = dao.create(db, obj_in={"workspace_id": w1.id, "formula_id": pf1.id, "item_id": i1.id, "item_role": "input", "quantity": -3})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.quantity == -3


# [claude] PFI-INH-06
def test_pfi_inh_06__update_with_a_schema_applies_the_fields_set_to_a_value(db, i1, mk_line):
    """PFI-INH-06 — update with a schema applies the fields set to a value.
    Rules: `inherited` R4"""
    a = mk_line(item_role="input", item_id=i1.id, quantity=2, unit="kg")

    result = dao.update(db, db_obj=a, obj_in=ProductionFormulaItemUpdate(quantity=5, unit=None))

    # Then 1
    assert result.id == a.id
    # Then 2
    row = reread(db, a)
    assert row.quantity == 5
    assert row.unit == "kg"


# [claude] PFI-INH-07
def test_pfi_inh_07__remove_hard_deletes_the_row(db, i1, i2, mk_line):
    """PFI-INH-07 — remove hard-deletes the row.
    Rules: `inherited` R5"""
    a = mk_line(item_role="input", item_id=i1.id)
    b = mk_line(item_role="input", item_id=i2.id)
    before_b = snap(db, b)

    result = dao.remove(db, id=a.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert count_rows(db, ProductionFormulaItem) == 1
    # Then 3
    db.expire_all()
    assert snap(db, b) == before_b
