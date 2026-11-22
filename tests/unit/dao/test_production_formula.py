"""Unit tests for app/dao/production_formula.py.

Implements tests/unit/dao/production_formula.cases.md, one test per case, in card order. Real
Postgres session (`db` fixture).
Nothing is mocked and no clock is patched (Conventions, Externals).

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117, DTZ001  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested():`, and naive datetimes)
from datetime import datetime

import pytest
from pydantic import ValidationError
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import DataError, IntegrityError

from app.dao.production_formula import production_formula_dao
from app.models.production_formula import ProductionFormula
from app.schemas.production_formula import (
    ProductionFormulaCreate,
    ProductionFormulaUpdate,
)
from tests.unit.factories import make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton production_formula_dao" (a module-level name, not a fixture)
dao = production_formula_dao

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


# Convention "they exist in every test and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builders (fixtures; each mk_ flushes before it returns)
# --------------------------------------------------------------------------- #

# Convention "formula"
@pytest.fixture
def new_formula(w1):
    """new_formula(formula_code=..., name=..., **columns) -> ProductionFormula, not added."""
    def _new(*, formula_code, name, **columns):
        return ProductionFormula(**{"workspace_id": w1.id, "formula_code": formula_code, "name": name, **columns})
    return _new


@pytest.fixture
def mk_formula(db, new_formula):
    """mk_formula(...) = new_formula(...), added and flushed."""
    def _mk(**columns):
        return _add(db, new_formula(**columns))
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


# Convention "nothing written": the number of `production_formulas` rows stored (all workspaces)
def stored_count(db):
    return db.scalar(select(func.count()).select_from(ProductionFormula.__table__))


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
        """The one SELECT from `production_formulas`; fails loudly unless there is exactly one."""
        [statement] = [s for s in self.selects() if "FROM production_formulas" in s]
        return statement


@pytest.fixture
def recorder(db):
    statement_recorder = StatementRecorder(db)
    yield statement_recorder
    statement_recorder.stop()


# --------------------------------------------------------------------------- #
# ProductionFormulaDAO.get_by_workspace
# --------------------------------------------------------------------------- #


# [claude] PFM-GW-01
def test_pfm_gw_01__returns_a_list_of_the_workspace_s_formulas(db, w1, mk_formula):
    """PFM-GW-01 — returns a list of the workspace's formulas.
    Rules: `get_by_workspace` R1, Returns"""
    a = mk_formula(formula_code="FM-A", name="Alpha")
    b = mk_formula(formula_code="FM-B", name="Bravo")

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 3
    assert isinstance(result[0], ProductionFormula)


# [claude] PFM-GW-02
def test_pfm_gw_02__a_row_of_another_workspace_is_not_returned(db, w1, w2, mk_formula):
    """PFM-GW-02 — a row of another workspace is not returned.
    Rules: `get_by_workspace` R1"""
    mk_formula(formula_code="FM-Z", name="Alpha", workspace_id=w2.id)
    a = mk_formula(formula_code="FM-A", name="Bravo")

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] PFM-GW-03
def test_pfm_gw_03__an_inactive_formula_is_returned(db, w1, mk_formula):
    """PFM-GW-03 — an inactive formula is returned.
    Rules: `get_by_workspace` R2"""
    a = mk_formula(formula_code="FM-A", name="Alpha")
    b = mk_formula(formula_code="FM-B", name="Bravo", is_active=False, is_default=False)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]


# [claude] PFM-GW-04
def test_pfm_gw_04__an_inactive_formula_takes_a_place_in_the_page(db, w1, mk_formula):
    """PFM-GW-04 — an inactive formula takes a place in the page.
    Rules: `get_by_workspace` R2"""
    mk_formula(formula_code="FM-X", name="Alpha", is_active=False)
    mk_formula(formula_code="FM-A", name="Bravo")
    mk_formula(formula_code="FM-B", name="Charlie")

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=2)

    # Then 1
    assert len(result) == 1


# [claude] PFM-GW-05
@pytest.mark.xfail(strict=True, reason="BUG-100: BaseDAO list methods have no sort order")
def test_pfm_gw_05__the_query_orders_by_id_ascending(db, w1, mk_formula, recorder):
    """PFM-GW-05 — the query orders by id, ascending.
    Rules: `get_by_workspace` R3 [BUG-100]"""
    a = mk_formula(formula_code="FM-A", name="Alpha")

    recorder.start()
    result = dao.get_by_workspace(db, workspace_id=w1.id)

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


# [claude] PFM-GW-06
@pytest.mark.xfail(
    strict=False,
    reason="BUG-100: BaseDAO list methods have no sort order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_pfm_gw_06__rows_come_back_by_id_when_the_lowest_id_was_updated(db, w1, mk_formula):
    """PFM-GW-06 — rows come back by id, when the lowest id was updated.
    Rules: `get_by_workspace` R3 [BUG-100]"""
    seqscan(db)
    a = mk_formula(formula_code="FM-A", name="Charlie")
    b = mk_formula(formula_code="FM-B", name="Alpha")
    c = mk_formula(formula_code="FM-C", name="Bravo")
    a.description = "Changed"
    db.flush()
    db.expire_all()

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [a.id, b.id, c.id]


# [claude] PFM-GW-07
@pytest.mark.xfail(
    strict=False,
    reason="BUG-100: BaseDAO list methods have no sort order "
    "(non-strict: the rows have no fixed order; which row is on which page rests on physical row order)",
)
def test_pfm_gw_07__rows_paged_one_at_a_time_neither_repeat_nor_miss_a_row(db, w1, mk_formula):
    """PFM-GW-07 — rows paged one at a time neither repeat nor miss a row.
    Rules: `get_by_workspace` R3 [BUG-100], R4"""
    seqscan(db)
    a = mk_formula(formula_code="FM-A", name="Charlie")
    b = mk_formula(formula_code="FM-B", name="Alpha")
    c = mk_formula(formula_code="FM-C", name="Bravo")
    d = mk_formula(formula_code="FM-D", name="Echo")
    e = mk_formula(formula_code="FM-E", name="Delta")
    a.description = "Changed"
    db.flush()
    db.expire_all()

    pages = [dao.get_by_workspace(db, workspace_id=w1.id, skip=k, limit=1) for k in range(5)]

    # Then 1
    assert [len(p) for p in pages] == [1, 1, 1, 1, 1]
    # Then 2
    assert [p[0].id for p in pages] == [a.id, b.id, c.id, d.id, e.id]


# [claude] PFM-GW-08
def test_pfm_gw_08__with_the_defaults_101_rows_give_100(db, w1, new_formula):
    """PFM-GW-08 — with the defaults 101 rows give 100.
    Rules: `get_by_workspace` R4"""
    rows = [new_formula(formula_code=f"FM-{k}", name=f"Mix {k:03d}") for k in range(1, 102)]
    add_many(db, rows)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert len(set(ids(result))) == 100


# [claude] PFM-GW-09
def test_pfm_gw_09__limit_1000_gives_all_101(db, w1, new_formula):
    """PFM-GW-09 — limit=1000 gives all 101.
    Rules: `get_by_workspace` R4"""
    rows = [new_formula(formula_code=f"FM-{k}", name=f"Mix {k:03d}") for k in range(1, 102)]
    add_many(db, rows)
    newest = [row.id for row in rows]

    result = dao.get_by_workspace(db, workspace_id=w1.id, limit=1000)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert sorted(ids(result)) == sorted(newest)


# [claude] PFM-GW-10
def test_pfm_gw_10__skip_and_limit_cut_one_row_from_the_middle(db, w1, mk_formula):
    """PFM-GW-10 — skip and limit cut one row from the middle.
    Rules: `get_by_workspace` R4"""
    mk_formula(formula_code="FM-A", name="Alpha")
    mk_formula(formula_code="FM-B", name="Bravo")
    mk_formula(formula_code="FM-C", name="Charlie")

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert len(result) == 1


# [claude] PFM-GW-11
def test_pfm_gw_11__limit_0_returns_an_empty_list(db, w1, mk_formula):
    """PFM-GW-11 — limit=0 returns an empty list.
    Rules: `get_by_workspace` R5"""
    mk_formula(formula_code="FM-A", name="Alpha")
    mk_formula(formula_code="FM-B", name="Bravo")

    result = dao.get_by_workspace(db, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [claude] PFM-GW-12
def test_pfm_gw_12__limit_1_returns_one_row(db, w1, mk_formula):
    """PFM-GW-12 — limit=1 returns one row.
    Rules: `get_by_workspace` R5"""
    mk_formula(formula_code="FM-A", name="Alpha")
    mk_formula(formula_code="FM-B", name="Bravo")

    result = dao.get_by_workspace(db, workspace_id=w1.id, limit=1)

    # Then 1
    assert len(result) == 1


# [claude] PFM-GW-13
def test_pfm_gw_13__skip_at_the_number_of_rows_returns_an_empty_list(db, w1, mk_formula):
    """PFM-GW-13 — skip at the number of rows returns an empty list.
    Rules: `get_by_workspace` R5"""
    mk_formula(formula_code="FM-A", name="Alpha")
    mk_formula(formula_code="FM-B", name="Bravo")

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [claude] PFM-GW-14
def test_pfm_gw_14__skip_at_the_last_row_returns_one_row(db, w1, mk_formula):
    """PFM-GW-14 — skip at the last row returns one row.
    Rules: `get_by_workspace` R5"""
    mk_formula(formula_code="FM-A", name="Alpha")
    mk_formula(formula_code="FM-B", name="Bravo")

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=1)

    # Then 1
    assert len(result) == 1


# [claude] PFM-GW-15
def test_pfm_gw_15__a_negative_limit_raises(db, w1, mk_formula):
    """PFM-GW-15 — a negative limit raises.
    Rules: `get_by_workspace` R6, Errors row 1"""
    mk_formula(formula_code="FM-A", name="Alpha")
    mk_formula(formula_code="FM-B", name="Bravo")
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


# [claude] PFM-GW-16
def test_pfm_gw_16__a_negative_skip_raises(db, w1, mk_formula):
    """PFM-GW-16 — a negative skip raises.
    Rules: `get_by_workspace` R6, Errors row 2"""
    mk_formula(formula_code="FM-A", name="Alpha")
    mk_formula(formula_code="FM-B", name="Bravo")
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


# [claude] PFM-GW-17
def test_pfm_gw_17__an_unknown_workspace_returns_an_empty_list(db, mk_formula):
    """PFM-GW-17 — an unknown workspace returns an empty list.
    Rules: `get_by_workspace` R5"""
    mk_formula(formula_code="FM-A", name="Alpha")

    result = dao.get_by_workspace(db, workspace_id=MISSING)

    # Then 1
    assert result == []


# [claude] PFM-GW-18
def test_pfm_gw_18__a_workspace_with_no_rows_returns_an_empty_list(db, w2, mk_formula):
    """PFM-GW-18 — a workspace with no rows returns an empty list.
    Rules: `get_by_workspace` R5"""
    mk_formula(formula_code="FM-A", name="Alpha")

    result = dao.get_by_workspace(db, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] PFM-GW-19
def test_pfm_gw_19__writes_nothing_a_pending_row_that_would_sort_first_stays_pending_and_i(db, w1, mk_formula, recorder):
    """PFM-GW-19 — writes nothing: a pending row that would sort first stays pending and is not returned.
    Rules: `get_by_workspace` Side effects"""
    a = mk_formula(formula_code="FM-A", name="Bravo")
    p = ProductionFormula(workspace_id=w1.id, formula_code="FM-P", name="Aardvark")
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


# [claude] PFM-GW-20
def test_pfm_gw_20__writes_nothing_a_read_leaves_the_caller_s_unflushed_edit_alone(db, w1, mk_formula):
    """PFM-GW-20 — writes nothing: a read leaves the caller's unflushed edit alone.
    Rules: `get_by_workspace` Side effects"""
    a = mk_formula(formula_code="FM-A", name="Alpha")
    b = mk_formula(formula_code="FM-B", name="Bravo")
    b.description = "Edited"

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert b.description == "Edited"


# [claude] PFM-GW-21
def test_pfm_gw_21__another_workspace_s_row_takes_no_place_in_the_page_whatever_the_row_or(db, w1, w2, mk_formula):
    """PFM-GW-21 — another workspace's row takes no place in the page, whatever the row order.
    Rules: `get_by_workspace` R1"""
    z = mk_formula(formula_code="FM-Z", name="Alpha", workspace_id=w2.id)
    a = mk_formula(formula_code="FM-A", name="Bravo")
    b = mk_formula(formula_code="FM-B", name="Charlie")

    result = dao.get_by_workspace(db, workspace_id=w1.id, limit=2)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 3
    assert z.id not in ids(result)


# --------------------------------------------------------------------------- #
# ProductionFormulaDAO.get_by_formula_code
# --------------------------------------------------------------------------- #


# [claude] PFM-GC-01
def test_pfm_gc_01__returns_the_row_with_that_code(db, w1, mk_formula):
    """PFM-GC-01 — returns the row with that code.
    Rules: `get_by_formula_code` R1, Returns"""
    mk_formula(formula_code="ROPE-1", name="Rope")
    a = mk_formula(formula_code="YARN-1", name="Yarn")

    result = dao.get_by_formula_code(db, formula_code="YARN-1", workspace_id=w1.id)

    # Then 1
    assert isinstance(result, ProductionFormula)
    # Then 2
    assert result.id == a.id
    # Then 3
    assert result.name == "Yarn"


# [claude] PFM-GC-02
def test_pfm_gc_02__the_same_code_in_another_workspace_is_not_matched(db, w1, w2, mk_formula):
    """PFM-GC-02 — the same code in another workspace is not matched.
    Rules: `get_by_formula_code` R2"""
    mk_formula(formula_code="YARN-1", name="Yarn", workspace_id=w2.id)

    result = dao.get_by_formula_code(db, formula_code="YARN-1", workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] PFM-GC-03
def test_pfm_gc_03__each_workspace_finds_its_own_row_when_the_other_workspace_s_row_is_the(db, w1, w2, mk_formula):
    """PFM-GC-03 — each workspace finds its own row, when the other workspace's row is the earlier one.
    Rules: `get_by_formula_code` R2"""
    mk_formula(formula_code="YARN-1", name="Far", workspace_id=w2.id)
    a = mk_formula(formula_code="YARN-1", name="Yarn")

    result = dao.get_by_formula_code(db, formula_code="YARN-1", workspace_id=w1.id)

    # Then 1
    assert result.id == a.id


# [claude] PFM-GC-04
def test_pfm_gc_04__each_workspace_finds_its_own_row_when_the_other_workspace_s_row_is_the(db, w2, mk_formula):
    """PFM-GC-04 — each workspace finds its own row, when the other workspace's row is the later one.
    Rules: `get_by_formula_code` R2"""
    mk_formula(formula_code="YARN-1", name="Yarn")
    z = mk_formula(formula_code="YARN-1", name="Far", workspace_id=w2.id)

    result = dao.get_by_formula_code(db, formula_code="YARN-1", workspace_id=w2.id)

    # Then 1
    assert result.id == z.id


# [claude] PFM-GC-05
def test_pfm_gc_05__a_code_with_no_row_returns_none(db, w1, mk_formula):
    """PFM-GC-05 — a code with no row returns None.
    Rules: `get_by_formula_code` R2"""
    mk_formula(formula_code="YARN-1", name="Yarn")

    result = dao.get_by_formula_code(db, formula_code="NOPE-9", workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] PFM-GC-06
def test_pfm_gc_06__the_code_returns_none(db, w1, mk_formula):
    """PFM-GC-06 — the code "" returns None.
    Rules: `get_by_formula_code` R2"""
    mk_formula(formula_code="YARN-1", name="Yarn")

    result = dao.get_by_formula_code(db, formula_code="", workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] PFM-GC-07
def test_pfm_gc_07__a_part_of_the_code_returns_none(db, w1, mk_formula):
    """PFM-GC-07 — a part of the code returns None.
    Rules: `get_by_formula_code` R2"""
    mk_formula(formula_code="YARN-1", name="Yarn")

    result = dao.get_by_formula_code(db, formula_code="YARN", workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] PFM-GC-08
def test_pfm_gc_08__the_end_of_the_code_returns_none(db, w1, mk_formula):
    """PFM-GC-08 — the end of the code returns None.
    Rules: `get_by_formula_code` R2"""
    mk_formula(formula_code="YARN-1", name="Yarn")

    result = dao.get_by_formula_code(db, formula_code="RN-1", workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] PFM-GC-09
def test_pfm_gc_09__is_no_wildcard(db, w1, mk_formula):
    """PFM-GC-09 — % is no wildcard.
    Rules: `get_by_formula_code` R2"""
    mk_formula(formula_code="YARN-1", name="Yarn")

    result = dao.get_by_formula_code(db, formula_code="YARN%", workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] PFM-GC-10
def test_pfm_gc_10__is_no_wildcard(db, w1, mk_formula):
    """PFM-GC-10 — _ is no wildcard.
    Rules: `get_by_formula_code` R2"""
    mk_formula(formula_code="YARN-1", name="Yarn")

    result = dao.get_by_formula_code(db, formula_code="YARN_1", workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] PFM-GC-11
@pytest.mark.xfail(strict=True, reason="BUG-1316: Formula code uniqueness is a Python read, exact match only")
def test_pfm_gc_11__a_code_in_small_letters_finds_the_capital_row(db, w1, mk_formula):
    """PFM-GC-11 — a code in small letters finds the capital row.
    Rules: `get_by_formula_code` R3 [BUG-1316]"""
    a = mk_formula(formula_code="YARN-1", name="Yarn")

    result = dao.get_by_formula_code(db, formula_code="yarn-1", workspace_id=w1.id)

    # Then 1
    assert result is not None
    # Then 2
    assert result.id == a.id


# [claude] PFM-GC-12
@pytest.mark.xfail(strict=True, reason="BUG-1316: Formula code uniqueness is a Python read, exact match only")
def test_pfm_gc_12__a_code_with_spaces_finds_the_row(db, w1, mk_formula):
    """PFM-GC-12 — a code with spaces finds the row.
    Rules: `get_by_formula_code` R3 [BUG-1316]"""
    a = mk_formula(formula_code="YARN-1", name="Yarn")

    result = dao.get_by_formula_code(db, formula_code=" YARN-1 ", workspace_id=w1.id)

    # Then 1
    assert result is not None
    # Then 2
    assert result.id == a.id


# [claude] PFM-GC-13
@pytest.mark.xfail(strict=True, reason="BUG-1316: Formula code uniqueness is a Python read, exact match only")
def test_pfm_gc_13__a_code_in_capitals_finds_a_stored_small_letter_row(db, w1, mk_formula):
    """PFM-GC-13 — a code in capitals finds a stored small-letter row.
    Rules: `get_by_formula_code` R3 [BUG-1316]"""
    a = mk_formula(formula_code="yarn-1", name="Yarn")

    result = dao.get_by_formula_code(db, formula_code="YARN-1", workspace_id=w1.id)

    # Then 1
    assert result is not None
    # Then 2
    assert result.id == a.id


# [claude] PFM-GC-14
@pytest.mark.xfail(strict=True, reason="BUG-1316: Formula code uniqueness is a Python read, exact match only")
def test_pfm_gc_14__a_stored_code_with_a_leading_space_is_found_the_stored_side_is_trimmed(db, w1, mk_formula):
    """PFM-GC-14 — a stored code with a leading space is found: the stored side is trimmed too.
    Rules: `get_by_formula_code` R3 [BUG-1316]"""
    a = mk_formula(formula_code=" YARN-1", name="Yarn")

    result = dao.get_by_formula_code(db, formula_code="YARN-1", workspace_id=w1.id)

    # Then 1
    assert result is not None
    # Then 2
    assert result.id == a.id


# [claude] PFM-GC-15
def test_pfm_gc_15__an_inactive_formula_is_found_so_its_code_stays_taken(db, w1, mk_formula):
    """PFM-GC-15 — an inactive formula is found, so its code stays taken.
    Rules: `get_by_formula_code` R5"""
    a = mk_formula(formula_code="YARN-1", name="Yarn", is_active=False, is_default=False)

    result = dao.get_by_formula_code(db, formula_code="YARN-1", workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.is_active is False


# [claude] PFM-GC-16
def test_pfm_gc_16__writes_nothing_a_pending_row_with_that_code_stays_pending_and_is_not_r(db, w1, mk_formula, recorder):
    """PFM-GC-16 — writes nothing: a pending row with that code stays pending and is not returned.
    Rules: `get_by_formula_code` Side effects"""
    a = mk_formula(formula_code="ROPE-1", name="Rope")
    p = ProductionFormula(workspace_id=w1.id, formula_code="YARN-1", name="Pending")
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    recorder.start()
    result = dao.get_by_formula_code(db, formula_code="YARN-1", workspace_id=w1.id)

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


# [claude] PFM-GC-17
def test_pfm_gc_17__writes_nothing_a_read_leaves_the_caller_s_unflushed_edit_alone(db, w1, mk_formula):
    """PFM-GC-17 — writes nothing: a read leaves the caller's unflushed edit alone.
    Rules: `get_by_formula_code` Side effects"""
    a = mk_formula(formula_code="YARN-1", name="Yarn")
    b = mk_formula(formula_code="ROPE-1", name="Rope")
    b.description = "Edited"

    result = dao.get_by_formula_code(db, formula_code="YARN-1", workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert b.description == "Edited"


# [claude] PFM-GC-18
def test_pfm_gc_18__an_inner_space_is_kept_yarn_1_does_not_find_yarn_1(db, w1, mk_formula):
    """PFM-GC-18 — an inner space is kept: YARN -1 does not find YARN-1.
    Rules: `get_by_formula_code` R3"""
    mk_formula(formula_code="YARN-1", name="Yarn")

    result = dao.get_by_formula_code(db, formula_code="YARN -1", workspace_id=w1.id)

    # Then 1
    assert result is None


# --------------------------------------------------------------------------- #
# ProductionFormulaDAO.get_active_by_workspace
# --------------------------------------------------------------------------- #


# [claude] PFM-GA-01
def test_pfm_ga_01__returns_a_list_of_the_active_formulas(db, w1, mk_formula):
    """PFM-GA-01 — returns a list of the active formulas.
    Rules: `get_active_by_workspace` R1, Returns"""
    a = mk_formula(formula_code="FM-A", name="Alpha")
    b = mk_formula(formula_code="FM-B", name="Bravo")

    result = dao.get_active_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 3
    assert isinstance(result[0], ProductionFormula)


# [claude] PFM-GA-02
def test_pfm_ga_02__an_inactive_formula_is_not_returned(db, w1, mk_formula):
    """PFM-GA-02 — an inactive formula is not returned.
    Rules: `get_active_by_workspace` R1"""
    mk_formula(formula_code="FM-X", name="Alpha", is_active=False, is_default=False)
    a = mk_formula(formula_code="FM-A", name="Bravo")

    result = dao.get_active_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] PFM-GA-03
def test_pfm_ga_03__a_row_of_another_workspace_is_not_returned(db, w1, w2, mk_formula):
    """PFM-GA-03 — a row of another workspace is not returned.
    Rules: `get_active_by_workspace` R1"""
    mk_formula(formula_code="FM-Z", name="Alpha", workspace_id=w2.id)
    a = mk_formula(formula_code="FM-A", name="Bravo")

    result = dao.get_active_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] PFM-GA-04
def test_pfm_ga_04__the_active_filter_runs_before_the_page_skip_2_past_the_two_visible_row(db, w1, mk_formula):
    """PFM-GA-04 — the active filter runs before the page: skip=2 past the two visible rows gives nothing.
    Rules: `get_active_by_workspace` R1"""
    mk_formula(formula_code="FM-X", name="Alpha", is_active=False, is_default=False)
    mk_formula(formula_code="FM-A", name="Bravo")
    mk_formula(formula_code="FM-B", name="Charlie")

    result = dao.get_active_by_workspace(db, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [claude] PFM-GA-05
def test_pfm_ga_05__the_active_filter_runs_before_the_page_skip_1_leaves_one_visible_row(db, w1, mk_formula):
    """PFM-GA-05 — the active filter runs before the page: skip=1 leaves one visible row.
    Rules: `get_active_by_workspace` R1"""
    x = mk_formula(formula_code="FM-X", name="Alpha", is_active=False, is_default=False)
    mk_formula(formula_code="FM-A", name="Bravo")
    mk_formula(formula_code="FM-B", name="Charlie")

    result = dao.get_active_by_workspace(db, workspace_id=w1.id, skip=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert x.id not in ids(result)


# [claude] PFM-GA-06
def test_pfm_ga_06__an_unknown_workspace_returns_an_empty_list(db, mk_formula):
    """PFM-GA-06 — an unknown workspace returns an empty list.
    Rules: `get_active_by_workspace` R2"""
    mk_formula(formula_code="FM-A", name="Alpha")

    result = dao.get_active_by_workspace(db, workspace_id=MISSING)

    # Then 1
    assert result == []


# [claude] PFM-GA-07
def test_pfm_ga_07__a_workspace_with_no_active_formulas_returns_an_empty_list(db, w1, mk_formula):
    """PFM-GA-07 — a workspace with no active formulas returns an empty list.
    Rules: `get_active_by_workspace` R2"""
    mk_formula(formula_code="FM-A", name="Alpha", is_active=False)

    result = dao.get_active_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PFM-GA-08
@pytest.mark.xfail(strict=True, reason="BUG-1314: The active formula list has no sort order")
def test_pfm_ga_08__the_query_orders_by_name_then_id_ascending(db, w1, mk_formula, recorder):
    """PFM-GA-08 — the query orders by name, then id, ascending.
    Rules: `get_active_by_workspace` R3 [BUG-1314]"""
    a = mk_formula(formula_code="FM-A", name="Alpha")

    recorder.start()
    result = dao.get_active_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    sql = recorder.sql()
    order_part = order_part_of(sql)
    assert "ORDER BY" in sql
    # Then 3
    assert "name" in order_part
    # Then 4
    assert ".id" in order_part
    # Then 5
    assert order_part.index("name") < order_part.index(".id")
    # Then 6
    assert "DESC" not in order_part.upper()
    # Then 7
    assert order_part.count(",") == 1


# [claude] PFM-GA-09
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1314: The active formula list has no sort order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_pfm_ga_09__names_come_back_case_insensitively_apple_banana_zulu(db, w1, mk_formula):
    """PFM-GA-09 — names come back case-insensitively: "apple", "Banana", "Zulu".
    Rules: `get_active_by_workspace` R3 [BUG-1314]"""
    seqscan(db)
    a = mk_formula(formula_code="FM-A", name="Zulu")
    b = mk_formula(formula_code="FM-B", name="apple")
    c = mk_formula(formula_code="FM-C", name="Banana")
    db.expire_all()

    result = dao.get_active_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [b.id, c.id, a.id]


# [claude] PFM-GA-10
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1314: The active formula list has no sort order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_pfm_ga_10__yarn_and_yarn_tie_on_the_name_the_lower_id_comes_first_capital_first(db, w1, mk_formula):
    """PFM-GA-10 — "Yarn" and "yarn" tie on the name: the lower id comes first, capital first.
    Rules: `get_active_by_workspace` R3 [BUG-1314]"""
    seqscan(db)
    a = mk_formula(formula_code="FM-A", name="Yarn")
    b = mk_formula(formula_code="FM-B", name="yarn")
    db.expire_all()

    result = dao.get_active_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert ids(result) == [a.id, b.id]


# [claude] PFM-GA-11
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1314: The active formula list has no sort order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_pfm_ga_11__yarn_and_yarn_tie_on_the_name_the_lower_id_comes_first_small_letter_fi(db, w1, mk_formula):
    """PFM-GA-11 — "yarn" and "Yarn" tie on the name: the lower id comes first, small letter first.
    Rules: `get_active_by_workspace` R3 [BUG-1314]"""
    seqscan(db)
    a = mk_formula(formula_code="FM-A", name="yarn")
    b = mk_formula(formula_code="FM-B", name="Yarn")
    db.expire_all()

    result = dao.get_active_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert ids(result) == [a.id, b.id]


# [claude] PFM-GA-12
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1314: The active formula list has no sort order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_pfm_ga_12__a_tie_on_the_name_goes_to_the_lower_id_when_code_and_version_would_sor(db, w1, mk_formula):
    """PFM-GA-12 — a tie on the name goes to the lower id, when code and version would sort otherwise and the lowest id was updated.
    Rules: `get_active_by_workspace` R3 [BUG-1314]"""
    seqscan(db)
    a = mk_formula(formula_code="FM-M", name="Yarn", version=2)
    b = mk_formula(formula_code="FM-Z", name="Yarn", version=3)
    c = mk_formula(formula_code="FM-A", name="Yarn", version=1)
    a.description = "Changed"
    db.flush()
    db.expire_all()

    result = dao.get_active_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [a.id, b.id, c.id]


# [claude] PFM-GA-13
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1314: The active formula list has no sort order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_pfm_ga_13__the_order_is_applied_before_the_page_is_cut(db, w1, mk_formula):
    """PFM-GA-13 — the order is applied before the page is cut.
    Rules: `get_active_by_workspace` R3 [BUG-1314]"""
    seqscan(db)
    mk_formula(formula_code="FM-A", name="Zulu")
    mk_formula(formula_code="FM-B", name="apple")
    c = mk_formula(formula_code="FM-C", name="Banana")
    db.expire_all()

    result = dao.get_active_by_workspace(db, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert ids(result) == [c.id]


# [claude] PFM-GA-14
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1314: The active formula list has no sort order "
    "(non-strict: the rows have no fixed order; which row is on which page rests on physical row order)",
)
def test_pfm_ga_14__rows_paged_one_at_a_time_neither_repeat_nor_miss_a_row(db, w1, mk_formula):
    """PFM-GA-14 — rows paged one at a time neither repeat nor miss a row.
    Rules: `get_active_by_workspace` R3 [BUG-1314], R4"""
    seqscan(db)
    a = mk_formula(formula_code="FM-A", name="Charlie")
    b = mk_formula(formula_code="FM-B", name="Alpha")
    c = mk_formula(formula_code="FM-C", name="Bravo")
    d = mk_formula(formula_code="FM-D", name="Echo")
    e = mk_formula(formula_code="FM-E", name="Delta")
    b.description = "Changed"
    db.flush()
    db.expire_all()

    pages = [dao.get_active_by_workspace(db, workspace_id=w1.id, skip=k, limit=1) for k in range(5)]

    # Then 1
    assert [len(p) for p in pages] == [1, 1, 1, 1, 1]
    # Then 2
    assert [p[0].id for p in pages] == [b.id, c.id, a.id, e.id, d.id]


# [claude] PFM-GA-15
def test_pfm_ga_15__with_the_defaults_101_rows_give_100(db, w1, new_formula):
    """PFM-GA-15 — with the defaults 101 rows give 100.
    Rules: `get_active_by_workspace` R4"""
    rows = [new_formula(formula_code=f"FM-{k}", name=f"Mix {k:03d}") for k in range(1, 102)]
    add_many(db, rows)

    result = dao.get_active_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert len(set(ids(result))) == 100


# [claude] PFM-GA-16
def test_pfm_ga_16__limit_1000_gives_all_101(db, w1, new_formula):
    """PFM-GA-16 — limit=1000 gives all 101.
    Rules: `get_active_by_workspace` R4"""
    rows = [new_formula(formula_code=f"FM-{k}", name=f"Mix {k:03d}") for k in range(1, 102)]
    add_many(db, rows)
    newest = [row.id for row in rows]

    result = dao.get_active_by_workspace(db, workspace_id=w1.id, limit=1000)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert sorted(ids(result)) == sorted(newest)


# [claude] PFM-GA-17
def test_pfm_ga_17__skip_and_limit_cut_one_row_from_the_middle(db, w1, mk_formula):
    """PFM-GA-17 — skip and limit cut one row from the middle.
    Rules: `get_active_by_workspace` R4"""
    mk_formula(formula_code="FM-A", name="Alpha")
    mk_formula(formula_code="FM-B", name="Bravo")
    mk_formula(formula_code="FM-C", name="Charlie")

    result = dao.get_active_by_workspace(db, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert len(result) == 1


# [claude] PFM-GA-18
def test_pfm_ga_18__limit_0_returns_an_empty_list(db, w1, mk_formula):
    """PFM-GA-18 — limit=0 returns an empty list.
    Rules: `get_active_by_workspace` R2"""
    mk_formula(formula_code="FM-A", name="Alpha")
    mk_formula(formula_code="FM-B", name="Bravo")

    result = dao.get_active_by_workspace(db, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [claude] PFM-GA-19
def test_pfm_ga_19__limit_1_returns_one_row(db, w1, mk_formula):
    """PFM-GA-19 — limit=1 returns one row.
    Rules: `get_active_by_workspace` R2"""
    mk_formula(formula_code="FM-A", name="Alpha")
    mk_formula(formula_code="FM-B", name="Bravo")

    result = dao.get_active_by_workspace(db, workspace_id=w1.id, limit=1)

    # Then 1
    assert len(result) == 1


# [claude] PFM-GA-20
def test_pfm_ga_20__skip_at_the_number_of_rows_returns_an_empty_list(db, w1, mk_formula):
    """PFM-GA-20 — skip at the number of rows returns an empty list.
    Rules: `get_active_by_workspace` R2"""
    mk_formula(formula_code="FM-A", name="Alpha")
    mk_formula(formula_code="FM-B", name="Bravo")

    result = dao.get_active_by_workspace(db, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [claude] PFM-GA-21
def test_pfm_ga_21__skip_at_the_last_row_returns_one_row(db, w1, mk_formula):
    """PFM-GA-21 — skip at the last row returns one row.
    Rules: `get_active_by_workspace` R2"""
    mk_formula(formula_code="FM-A", name="Alpha")
    mk_formula(formula_code="FM-B", name="Bravo")

    result = dao.get_active_by_workspace(db, workspace_id=w1.id, skip=1)

    # Then 1
    assert len(result) == 1


# [claude] PFM-GA-22
def test_pfm_ga_22__a_negative_limit_raises(db, w1, mk_formula):
    """PFM-GA-22 — a negative limit raises.
    Rules: `get_active_by_workspace` R5, Errors row 1"""
    mk_formula(formula_code="FM-A", name="Alpha")
    mk_formula(formula_code="FM-B", name="Bravo")
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_active_by_workspace(db, workspace_id=w1.id, limit=-1)
    # Then 2
    assert exc.value.orig.pgcode == "2201W"
    # Then 3
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 4
    assert stored_count(db) == before


# [claude] PFM-GA-23
def test_pfm_ga_23__a_negative_skip_raises(db, w1, mk_formula):
    """PFM-GA-23 — a negative skip raises.
    Rules: `get_active_by_workspace` R5, Errors row 2"""
    mk_formula(formula_code="FM-A", name="Alpha")
    mk_formula(formula_code="FM-B", name="Bravo")
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_active_by_workspace(db, workspace_id=w1.id, skip=-1)
    # Then 2
    assert exc.value.orig.pgcode == "2201X"
    # Then 3
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 4
    assert stored_count(db) == before


# [claude] PFM-GA-24
def test_pfm_ga_24__writes_nothing_a_pending_row_that_would_sort_first_stays_pending_and_i(db, w1, mk_formula, recorder):
    """PFM-GA-24 — writes nothing: a pending row that would sort first stays pending and is not returned.
    Rules: `get_active_by_workspace` Side effects"""
    a = mk_formula(formula_code="FM-A", name="Bravo")
    p = ProductionFormula(workspace_id=w1.id, formula_code="FM-P", name="Aardvark")
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    recorder.start()
    result = dao.get_active_by_workspace(db, workspace_id=w1.id)

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


# [claude] PFM-GA-25
def test_pfm_ga_25__writes_nothing_a_read_leaves_the_caller_s_unflushed_edit_alone(db, w1, mk_formula):
    """PFM-GA-25 — writes nothing: a read leaves the caller's unflushed edit alone.
    Rules: `get_active_by_workspace` Side effects"""
    a = mk_formula(formula_code="FM-A", name="Alpha")
    b = mk_formula(formula_code="FM-B", name="Bravo")
    b.description = "Edited"

    result = dao.get_active_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert b.description == "Edited"


# [claude] PFM-GA-26
def test_pfm_ga_26__another_workspace_s_row_takes_no_place_in_the_page_whatever_the_row_or(db, w1, w2, mk_formula):
    """PFM-GA-26 — another workspace's row takes no place in the page, whatever the row order.
    Rules: `get_active_by_workspace` R1"""
    z = mk_formula(formula_code="FM-Z", name="Alpha", workspace_id=w2.id)
    a = mk_formula(formula_code="FM-A", name="Bravo")
    b = mk_formula(formula_code="FM-B", name="Charlie")

    result = dao.get_active_by_workspace(db, workspace_id=w1.id, limit=2)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 3
    assert z.id not in ids(result)


# --------------------------------------------------------------------------- #
# ProductionFormulaDAO.get_default_formulas
# --------------------------------------------------------------------------- #


# [claude] PFM-GD-01
def test_pfm_gd_01__returns_a_list_of_the_active_default_formulas(db, w1, mk_formula):
    """PFM-GD-01 — returns a list of the active default formulas.
    Rules: `get_default_formulas` R1, Returns"""
    a = mk_formula(formula_code="FM-A", name="Alpha", is_default=True)
    mk_formula(formula_code="FM-X", name="Bravo")

    result = dao.get_default_formulas(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert sorted(ids(result)) == [a.id]
    # Then 3
    assert isinstance(result[0], ProductionFormula)


# [claude] PFM-GD-02
def test_pfm_gd_02__a_workspace_with_none_returns_an_empty_list(db, w1, mk_formula):
    """PFM-GD-02 — a workspace with none returns an empty list.
    Rules: `get_default_formulas` R1"""
    mk_formula(formula_code="FM-X", name="Alpha")

    result = dao.get_default_formulas(db, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PFM-GD-03
def test_pfm_gd_03__a_default_of_another_workspace_is_not_returned(db, w1, w2, mk_formula):
    """PFM-GD-03 — a default of another workspace is not returned.
    Rules: `get_default_formulas` R1"""
    mk_formula(formula_code="FM-Z", name="Far", workspace_id=w2.id, is_default=True)
    a = mk_formula(formula_code="FM-A", name="Bravo", is_default=True)

    result = dao.get_default_formulas(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] PFM-GD-04
def test_pfm_gd_04__an_inactive_formula_with_the_flag_is_not_returned(db, w1, mk_formula):
    """PFM-GD-04 — an inactive formula with the flag is not returned.
    Rules: `get_default_formulas` R2"""
    mk_formula(formula_code="FM-X", name="Alpha", is_default=True, is_active=False)
    a = mk_formula(formula_code="FM-A", name="Bravo", is_default=True)

    result = dao.get_default_formulas(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] PFM-GD-05
def test_pfm_gd_05__two_defaults_give_two_rows(db, w1, mk_formula):
    """PFM-GD-05 — two defaults give two rows.
    Rules: `get_default_formulas` R3"""
    a = mk_formula(formula_code="FM-A", name="Alpha", is_default=True)
    b = mk_formula(formula_code="FM-B", name="Bravo", is_default=True)

    result = dao.get_default_formulas(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]


# [claude] PFM-GD-06
def test_pfm_gd_06__there_is_no_cap_101_defaults_give_101_rows(db, w1, new_formula):
    """PFM-GD-06 — there is no cap: 101 defaults give 101 rows.
    Rules: `get_default_formulas` R3"""
    rows = [new_formula(formula_code=f"FM-{k}", name=f"Mix {k:03d}", is_default=True) for k in range(1, 102)]
    add_many(db, rows)
    newest = [row.id for row in rows]

    result = dao.get_default_formulas(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert sorted(ids(result)) == sorted(newest)


# [claude] PFM-GD-07
@pytest.mark.xfail(strict=True, reason="BUG-1315: Default formulas have no sort order")
def test_pfm_gd_07__the_query_orders_by_name_then_id_ascending(db, w1, mk_formula, recorder):
    """PFM-GD-07 — the query orders by name, then id, ascending.
    Rules: `get_default_formulas` R4 [BUG-1315]"""
    a = mk_formula(formula_code="FM-A", name="Alpha", is_default=True)

    recorder.start()
    result = dao.get_default_formulas(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    sql = recorder.sql()
    order_part = order_part_of(sql)
    assert "ORDER BY" in sql
    # Then 3
    assert "name" in order_part
    # Then 4
    assert ".id" in order_part
    # Then 5
    assert order_part.index("name") < order_part.index(".id")
    # Then 6
    assert "DESC" not in order_part.upper()
    # Then 7
    assert order_part.count(",") == 1


# [claude] PFM-GD-08
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1315: Default formulas have no sort order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_pfm_gd_08__names_come_back_case_insensitively_apple_banana_zulu(db, w1, mk_formula):
    """PFM-GD-08 — names come back case-insensitively: "apple", "Banana", "Zulu".
    Rules: `get_default_formulas` R4 [BUG-1315]"""
    seqscan(db)
    a = mk_formula(formula_code="FM-A", name="Zulu", is_default=True)
    b = mk_formula(formula_code="FM-B", name="apple", is_default=True)
    c = mk_formula(formula_code="FM-C", name="Banana", is_default=True)
    db.expire_all()

    result = dao.get_default_formulas(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [b.id, c.id, a.id]


# [claude] PFM-GD-09
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1315: Default formulas have no sort order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_pfm_gd_09__yarn_and_yarn_tie_on_the_name_the_lower_id_comes_first_capital_first(db, w1, mk_formula):
    """PFM-GD-09 — "Yarn" and "yarn" tie on the name: the lower id comes first, capital first.
    Rules: `get_default_formulas` R4 [BUG-1315]"""
    seqscan(db)
    a = mk_formula(formula_code="FM-A", name="Yarn", is_default=True)
    b = mk_formula(formula_code="FM-B", name="yarn", is_default=True)
    db.expire_all()

    result = dao.get_default_formulas(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert ids(result) == [a.id, b.id]


# [claude] PFM-GD-10
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1315: Default formulas have no sort order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_pfm_gd_10__a_tie_on_the_name_goes_to_the_lower_id_when_the_lowest_id_was_updated(db, w1, mk_formula):
    """PFM-GD-10 — a tie on the name goes to the lower id, when the lowest id was updated.
    Rules: `get_default_formulas` R4 [BUG-1315]"""
    seqscan(db)
    a = mk_formula(formula_code="FM-A", name="Yarn", is_default=True)
    b = mk_formula(formula_code="FM-B", name="Yarn", is_default=True)
    c = mk_formula(formula_code="FM-C", name="Yarn", is_default=True)
    a.description = "Changed"
    db.flush()
    db.expire_all()

    result = dao.get_default_formulas(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [a.id, b.id, c.id]


# [claude] PFM-GD-11
def test_pfm_gd_11__writes_nothing_a_pending_row_that_would_sort_first_stays_pending_and_i(db, w1, mk_formula, recorder):
    """PFM-GD-11 — writes nothing: a pending row that would sort first stays pending and is not returned.
    Rules: `get_default_formulas` Side effects"""
    a = mk_formula(formula_code="FM-A", name="Bravo", is_default=True)
    p = ProductionFormula(workspace_id=w1.id, formula_code="FM-P", name="Aardvark", is_default=True)
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    recorder.start()
    result = dao.get_default_formulas(db, workspace_id=w1.id)

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


# [claude] PFM-GD-12
def test_pfm_gd_12__writes_nothing_a_read_leaves_the_caller_s_unflushed_edit_alone(db, w1, mk_formula):
    """PFM-GD-12 — writes nothing: a read leaves the caller's unflushed edit alone.
    Rules: `get_default_formulas` Side effects"""
    a = mk_formula(formula_code="FM-A", name="Alpha", is_default=True)
    b = mk_formula(formula_code="FM-B", name="Bravo", is_default=True)
    b.description = "Edited"

    result = dao.get_default_formulas(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert b.description == "Edited"


# [claude] PFM-GD-13
def test_pfm_gd_13__a_w1_default_is_not_returned_for_w2(db, w2, mk_formula):
    """PFM-GD-13 — a W1 default is not returned for W2.
    Rules: `get_default_formulas` R1"""
    mk_formula(formula_code="FM-A", name="Alpha", is_default=True)

    result = dao.get_default_formulas(db, workspace_id=w2.id)

    # Then 1
    assert result == []


# --------------------------------------------------------------------------- #
# ProductionFormulaDAO.get_by_id_and_workspace
# --------------------------------------------------------------------------- #


# [claude] PFM-GI-01
def test_pfm_gi_01__returns_the_row_with_that_id(db, w1, mk_formula):
    """PFM-GI-01 — returns the row with that id.
    Rules: `get_by_id_and_workspace` R1, Returns"""
    mk_formula(formula_code="FM-B", name="Bravo")
    a = mk_formula(formula_code="FM-A", name="Alpha")

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, ProductionFormula)
    # Then 2
    assert result.id == a.id
    # Then 3
    assert result.name == "Alpha"
    assert result.workspace_id == w1.id
    assert result.formula_code == "FM-A"


# [claude] PFM-GI-02
def test_pfm_gi_02__another_workspace_s_id_returns_none_when_that_row_is_the_later_one(db, w1, w2, mk_formula):
    """PFM-GI-02 — another workspace's id returns None, when that row is the later one.
    Rules: `get_by_id_and_workspace` R2"""
    mk_formula(formula_code="FM-A", name="Alpha")
    z = mk_formula(formula_code="FM-Z", name="Bravo", workspace_id=w2.id)

    result = dao.get_by_id_and_workspace(db, id=z.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] PFM-GI-03
def test_pfm_gi_03__another_workspace_s_id_returns_none_when_that_row_is_the_earlier_one(db, w1, w2, mk_formula):
    """PFM-GI-03 — another workspace's id returns None, when that row is the earlier one.
    Rules: `get_by_id_and_workspace` R2"""
    z = mk_formula(formula_code="FM-Z", name="Bravo", workspace_id=w2.id)
    mk_formula(formula_code="FM-A", name="Alpha")

    result = dao.get_by_id_and_workspace(db, id=z.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] PFM-GI-04
def test_pfm_gi_04__the_id_under_another_workspace_returns_none(db, w2, mk_formula):
    """PFM-GI-04 — the id under another workspace returns None.
    Rules: `get_by_id_and_workspace` R2"""
    a = mk_formula(formula_code="FM-A", name="Alpha")

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w2.id)

    # Then 1
    assert result is None


# [claude] PFM-GI-05
def test_pfm_gi_05__an_unknown_id_returns_none(db, w1, mk_formula):
    """PFM-GI-05 — an unknown id returns None.
    Rules: `get_by_id_and_workspace` R3"""
    mk_formula(formula_code="FM-A", name="Alpha")

    result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] PFM-GI-06
def test_pfm_gi_06__id_0_returns_none(db, w1, mk_formula):
    """PFM-GI-06 — id=0 returns None.
    Rules: `get_by_id_and_workspace` R3"""
    mk_formula(formula_code="FM-A", name="Alpha")

    result = dao.get_by_id_and_workspace(db, id=0, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] PFM-GI-07
def test_pfm_gi_07__writes_nothing_a_read_that_finds_nothing_leaves_the_session_as_it_was(db, w1, mk_formula, recorder):
    """PFM-GI-07 — writes nothing: a read that finds nothing leaves the session as it was.
    Rules: `get_by_id_and_workspace` R3, Side effects"""
    a = mk_formula(formula_code="FM-A", name="Alpha")
    p = ProductionFormula(workspace_id=w1.id, formula_code="FM-P", name="Aardvark")
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


# [claude] PFM-GI-08
def test_pfm_gi_08__writes_nothing_a_read_that_finds_its_row_leaves_the_session_as_it_was(db, w1, mk_formula, recorder):
    """PFM-GI-08 — writes nothing: a read that finds its row leaves the session as it was.
    Rules: `get_by_id_and_workspace` Side effects"""
    a = mk_formula(formula_code="FM-A", name="Alpha")
    p = ProductionFormula(workspace_id=w1.id, formula_code="FM-P", name="Aardvark")
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


# [claude] PFM-GI-09
def test_pfm_gi_09__writes_nothing_a_read_leaves_the_caller_s_unflushed_edit_alone(db, w1, mk_formula):
    """PFM-GI-09 — writes nothing: a read leaves the caller's unflushed edit alone.
    Rules: `get_by_id_and_workspace` Side effects"""
    a = mk_formula(formula_code="FM-A", name="Alpha")
    b = mk_formula(formula_code="FM-B", name="Bravo")
    b.description = "Edited"

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert b.description == "Edited"


# [claude] PFM-GI-10
def test_pfm_gi_10__an_inactive_formula_is_returned(db, w1, mk_formula):
    """PFM-GI-10 — an inactive formula is returned.
    Rules: `get_by_id_and_workspace` R4"""
    a = mk_formula(formula_code="FM-A", name="Alpha", is_active=False, is_default=False)

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.is_active is False


# --------------------------------------------------------------------------- #
# Inherited BaseDAO methods on ProductionFormula
# --------------------------------------------------------------------------- #


# [claude] PFM-INH-01
def test_pfm_inh_01__create_with_a_dict_gives_the_defaults(db, w1):
    """PFM-INH-01 — create with a dict gives the defaults.
    Rules: `inherited` R1"""
    result = dao.create(db, obj_in={"workspace_id": w1.id, "formula_code": "YARN-1", "name": "Yarn"})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.version == 1
    assert row.is_active is True
    assert row.is_default is False
    # Then 3
    row = reread(db, result)
    assert row.created_at is not None
    assert row.updated_at is not None


# [claude] PFM-INH-02
def test_pfm_inh_02__create_with_a_productionformulacreate_fails_on_flush_and_saves_nothing(db):
    """PFM-INH-02 — create with a ProductionFormulaCreate fails on flush and saves nothing.
    Rules: `inherited` R2"""
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in=ProductionFormulaCreate(formula_code="YARN-1", name="Yarn"))
    # Then 2
    assert exc.value.orig.pgcode == "23502"
    # Then 3
    assert count_rows(db, ProductionFormula) == 0


# [claude] PFM-INH-03
@pytest.mark.xfail(strict=True, reason="BUG-1316: Formula code uniqueness is a Python read, exact match only")
def test_pfm_inh_03__a_second_row_with_the_same_code_is_refused(db, w1, mk_formula):
    """PFM-INH-03 — a second row with the same code is refused.
    Rules: `inherited` R3 [BUG-1316]"""
    mk_formula(formula_code="YARN-1", name="Yarn")

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "formula_code": "YARN-1", "name": "Yarn"})
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    assert count_rows(db, ProductionFormula, ProductionFormula.workspace_id == w1.id) == 1


# [claude] PFM-INH-04
@pytest.mark.xfail(strict=True, reason="BUG-1316: Formula code uniqueness is a Python read, exact match only")
def test_pfm_inh_04__a_second_row_in_other_capitals_is_refused(db, w1, mk_formula):
    """PFM-INH-04 — a second row in other capitals is refused.
    Rules: `inherited` R3 [BUG-1316]"""
    mk_formula(formula_code="YARN-1", name="Yarn")

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "formula_code": "yarn-1", "name": "Yarn"})
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    assert count_rows(db, ProductionFormula, ProductionFormula.workspace_id == w1.id) == 1


# [claude] PFM-INH-05
@pytest.mark.xfail(strict=True, reason="BUG-1316: Formula code uniqueness is a Python read, exact match only")
def test_pfm_inh_05__a_second_row_with_spaces_round_the_code_is_refused(db, w1, mk_formula):
    """PFM-INH-05 — a second row with spaces round the code is refused.
    Rules: `inherited` R3 [BUG-1316]"""
    mk_formula(formula_code="YARN-1", name="Yarn")

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "formula_code": " YARN-1 ", "name": "Yarn"})
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    assert count_rows(db, ProductionFormula, ProductionFormula.workspace_id == w1.id) == 1


# [claude] PFM-INH-06
@pytest.mark.xfail(strict=True, reason="BUG-1316: Formula code uniqueness is a Python read, exact match only")
def test_pfm_inh_06__the_code_of_an_inactive_formula_is_refused_the_index_covers_every_row(db, w1, mk_formula):
    """PFM-INH-06 — the code of an inactive formula is refused: the index covers every row.
    Rules: `inherited` R3 [BUG-1316]"""
    mk_formula(formula_code="YARN-1", name="Yarn", is_active=False, is_default=False)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "formula_code": "YARN-1", "name": "Yarn"})
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    assert count_rows(db, ProductionFormula, ProductionFormula.workspace_id == w1.id) == 1


# [claude] PFM-INH-07
def test_pfm_inh_07__the_same_code_under_another_workspace_is_accepted(db, w2, mk_formula):
    """PFM-INH-07 — the same code under another workspace is accepted.
    Rules: `inherited` R3"""
    a = mk_formula(formula_code="YARN-1", name="Yarn")

    result = dao.create(db, obj_in={"workspace_id": w2.id, "formula_code": "YARN-1", "name": "Yarn"})

    # Then 1
    assert result.id != a.id
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w2.id


# [claude] PFM-INH-08
def test_pfm_inh_08__another_code_in_one_workspace_is_accepted(db, w1, mk_formula):
    """PFM-INH-08 — another code in one workspace is accepted.
    Rules: `inherited` R3"""
    a = mk_formula(formula_code="YARN-1", name="Yarn")

    result = dao.create(db, obj_in={"workspace_id": w1.id, "formula_code": "YARN-2", "name": "Yarn"})

    # Then 1
    assert result.id != a.id
    # Then 2
    assert count_rows(db, ProductionFormula, ProductionFormula.workspace_id == w1.id) == 2


# [claude] PFM-INH-09
@pytest.mark.xfail(strict=True, reason="BUG-1316: Formula code uniqueness is a Python read, exact match only")
def test_pfm_inh_09__update_moving_a_row_onto_a_taken_code_is_refused(db, mk_formula):
    """PFM-INH-09 — update moving a row onto a taken code is refused.
    Rules: `inherited` R3a [BUG-1316]"""
    mk_formula(formula_code="YARN-1", name="Yarn")
    b = mk_formula(formula_code="ROPE-1", name="Rope")

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.update(db, db_obj=b, obj_in={"formula_code": "YARN-1"})
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    row = reread(db, b)
    assert row.formula_code == "ROPE-1"


# [claude] PFM-INH-10
@pytest.mark.xfail(strict=True, reason="BUG-1316: Formula code uniqueness is a Python read, exact match only")
def test_pfm_inh_10__update_moving_a_row_onto_a_taken_code_in_other_capitals_is_refused(db, mk_formula):
    """PFM-INH-10 — update moving a row onto a taken code in other capitals is refused.
    Rules: `inherited` R3a [BUG-1316]"""
    mk_formula(formula_code="YARN-1", name="Yarn")
    b = mk_formula(formula_code="ROPE-1", name="Rope")

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.update(db, db_obj=b, obj_in={"formula_code": "yarn-1"})
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    row = reread(db, b)
    assert row.formula_code == "ROPE-1"


# [claude] PFM-INH-11
def test_pfm_inh_11__update_onto_a_row_s_own_code_is_accepted(db, mk_formula):
    """PFM-INH-11 — update onto a row's own code is accepted.
    Rules: `inherited` R3a"""
    a = mk_formula(formula_code="YARN-1", name="Yarn")

    result = dao.update(db, db_obj=a, obj_in={"formula_code": "YARN-1", "name": "Yarn two"})

    # Then 1
    assert result.id == a.id
    # Then 2
    row = reread(db, a)
    assert row.formula_code == "YARN-1"
    assert row.name == "Yarn two"


# [claude] PFM-INH-12
def test_pfm_inh_12__update_onto_a_code_taken_only_in_another_workspace_is_accepted(db, w2, mk_formula):
    """PFM-INH-12 — update onto a code taken only in another workspace is accepted.
    Rules: `inherited` R3a"""
    mk_formula(formula_code="YARN-1", name="Far", workspace_id=w2.id)
    b = mk_formula(formula_code="ROPE-1", name="Rope")

    result = dao.update(db, db_obj=b, obj_in={"formula_code": "YARN-1"})

    # Then 1
    assert result.id == b.id
    # Then 2
    row = reread(db, b)
    assert row.formula_code == "YARN-1"


# --------------------------------------------------------------------------- #
# Schemas ProductionFormulaCreate, ProductionFormulaUpdate (BUG-1317)
# --------------------------------------------------------------------------- #


# [claude] PFM-SCH-01
@pytest.mark.xfail(strict=True, reason="BUG-1317: Blank formula codes and names accepted; stored untrimmed")
def test_pfm_sch_01__a_whitespace_only_name_is_refused_on_create():
    """PFM-SCH-01 — a whitespace-only name is refused on create.
    Rules: `schema` BUG-1317"""
    # Then 1
    with pytest.raises(ValidationError):
        ProductionFormulaCreate(formula_code="YARN-1", name="   ")


# [claude] PFM-SCH-02
@pytest.mark.xfail(strict=True, reason="BUG-1317: Blank formula codes and names accepted; stored untrimmed")
def test_pfm_sch_02__a_whitespace_only_code_is_refused_on_create():
    """PFM-SCH-02 — a whitespace-only code is refused on create.
    Rules: `schema` BUG-1317"""
    # Then 1
    with pytest.raises(ValidationError):
        ProductionFormulaCreate(formula_code="   ", name="Yarn")


# [claude] PFM-SCH-03
@pytest.mark.xfail(strict=True, reason="BUG-1317: Blank formula codes and names accepted; stored untrimmed")
def test_pfm_sch_03__a_whitespace_only_name_is_refused_on_update():
    """PFM-SCH-03 — a whitespace-only name is refused on update.
    Rules: `schema` BUG-1317"""
    # Then 1
    with pytest.raises(ValidationError):
        ProductionFormulaUpdate(name="   ")


# [claude] PFM-SCH-04
@pytest.mark.xfail(strict=True, reason="BUG-1317: Blank formula codes and names accepted; stored untrimmed")
def test_pfm_sch_04__a_code_is_stored_trimmed():
    """PFM-SCH-04 — a code is stored trimmed.
    Rules: `schema` BUG-1317"""
    result = ProductionFormulaCreate(formula_code=" RE-1 ", name="Yarn")

    # Then 1
    assert result.formula_code == "RE-1"


# [claude] PFM-SCH-05
@pytest.mark.xfail(strict=True, reason="BUG-1317: Blank formula codes and names accepted; stored untrimmed")
def test_pfm_sch_05__a_name_is_stored_trimmed_on_create():
    """PFM-SCH-05 — a name is stored trimmed on create.
    Rules: `schema` BUG-1317"""
    result = ProductionFormulaCreate(formula_code="RE-1", name=" Yarn ")

    # Then 1
    assert result.name == "Yarn"


# [claude] PFM-SCH-06
@pytest.mark.xfail(strict=True, reason="BUG-1317: Blank formula codes and names accepted; stored untrimmed")
def test_pfm_sch_06__a_name_is_stored_trimmed_on_update():
    """PFM-SCH-06 — a name is stored trimmed on update.
    Rules: `schema` BUG-1317"""
    result = ProductionFormulaUpdate(name=" Yarn ")

    # Then 1
    assert result.name == "Yarn"


# [claude] PFM-SCH-07
def test_pfm_sch_07__inner_spaces_and_case_are_kept_as_typed():
    """PFM-SCH-07 — inner spaces and case are kept as typed.
    Rules: `schema` Companion"""
    result = ProductionFormulaCreate(formula_code="Re-1", name="Fine  Yarn")

    # Then 1
    assert result.name == "Fine  Yarn"
    # Then 2
    assert result.formula_code == "Re-1"
