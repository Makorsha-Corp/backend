"""Unit tests for app/dao/production_line.py.

Implements tests/unit/dao/production_line.cases.md, one test per case, in card order. Real
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

from app.dao.production_line import production_line_dao
from app.models.factory import Factory
from app.models.machine import Machine
from app.models.production_line import ProductionLine
from app.schemas.production_line import ProductionLineCreate, ProductionLineUpdate
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton production_line_dao" (a module-level name, not a fixture)
dao = production_line_dao

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
def u1(db, w2):
    return make_profile(db)


@pytest.fixture
def f1(db, w1, u1):
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
def m1(db, w1, f1, f9):
    return _add(db, Machine(workspace_id=w1.id, factory_id=f1.id, name="Press 1"))


@pytest.fixture
def md(db, w1, u1, f1, m1):
    return _add(db, Machine(workspace_id=w1.id, factory_id=f1.id, name="Press 2", is_active=False, is_deleted=True, deleted_at=T0, deleted_by=u1.id))


# Convention "they exist in every test and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2, u1, f1, f2, fd, fi, f9, m1, md):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builders (fixtures; each mk_ flushes before it returns)
# --------------------------------------------------------------------------- #

# Convention "line"
@pytest.fixture
def new_line(w1, f1):
    """new_line(name=..., **columns) -> ProductionLine, not added."""
    def _new(*, name, **columns):
        return ProductionLine(**{"workspace_id": w1.id, "factory_id": f1.id, "name": name, **columns})
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


# Convention "nothing written": the number of `production_lines` rows stored (all workspaces)
def stored_count(db):
    return db.scalar(select(func.count()).select_from(ProductionLine.__table__))


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
        """The one SELECT from `production_lines`; fails loudly unless there is exactly one."""
        [statement] = [s for s in self.selects() if "FROM production_lines" in s]
        return statement


@pytest.fixture
def recorder(db):
    statement_recorder = StatementRecorder(db)
    yield statement_recorder
    statement_recorder.stop()


# --------------------------------------------------------------------------- #
# ProductionLineDAO.get_by_workspace
# --------------------------------------------------------------------------- #


# [claude] PLN-GW-01
def test_pln_gw_01__returns_a_list_of_the_workspace_s_lines(db, w1, mk_line):
    """PLN-GW-01 — returns a list of the workspace's lines.
    Rules: `get_by_workspace` R1, Returns"""
    a = mk_line(name="Alpha")
    b = mk_line(name="Bravo")

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 3
    assert isinstance(result[0], ProductionLine)


# [claude] PLN-GW-02
def test_pln_gw_02__a_row_of_another_workspace_is_not_returned(db, w1, w2, f9, mk_line):
    """PLN-GW-02 — a row of another workspace is not returned.
    Rules: `get_by_workspace` R1"""
    mk_line(name="Alpha", workspace_id=w2.id, factory_id=f9.id)
    a = mk_line(name="Bravo")

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] PLN-GW-03
def test_pln_gw_03__an_inactive_line_is_returned(db, w1, mk_line):
    """PLN-GW-03 — an inactive line is returned.
    Rules: `get_by_workspace` R2"""
    a = mk_line(name="Alpha")
    b = mk_line(name="Bravo", is_active=False)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]


# [claude] PLN-GW-04
def test_pln_gw_04__a_line_of_a_soft_deleted_machine_is_returned(db, w1, md, mk_line):
    """PLN-GW-04 — a line of a soft-deleted machine is returned.
    Rules: `get_by_workspace` R2"""
    a = mk_line(name="Alpha", machine_id=md.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] PLN-GW-05
def test_pln_gw_05__a_line_of_a_soft_deleted_factory_is_returned(db, w1, fd, mk_line):
    """PLN-GW-05 — a line of a soft-deleted factory is returned.
    Rules: `get_by_workspace` R2"""
    a = mk_line(name="Alpha", factory_id=fd.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] PLN-GW-06
def test_pln_gw_06__the_query_does_not_read_the_parent_tables(db, w1, mk_line, recorder):
    """PLN-GW-06 — the query does not read the parent tables.
    Rules: `get_by_workspace` R2"""
    mk_line(name="Alpha")

    recorder.start()
    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 1
    # Then 2
    sql = recorder.sql()
    assert "JOIN" not in sql
    # Then 3
    assert "factories" not in sql
    # Then 4
    assert "machines" not in sql


# [claude] PLN-GW-07
@pytest.mark.xfail(strict=True, reason="BUG-100: BaseDAO list methods have no sort order")
def test_pln_gw_07__the_query_orders_by_id_ascending(db, w1, mk_line, recorder):
    """PLN-GW-07 — the query orders by id, ascending.
    Rules: `get_by_workspace` R3 [BUG-100]"""
    a = mk_line(name="Alpha")

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


# [claude] PLN-GW-08
@pytest.mark.xfail(
    strict=False,
    reason="BUG-100: BaseDAO list methods have no sort order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_pln_gw_08__rows_come_back_by_id_when_the_lowest_id_was_updated(db, w1, mk_line):
    """PLN-GW-08 — rows come back by id, when the lowest id was updated.
    Rules: `get_by_workspace` R3 [BUG-100]"""
    seqscan(db)
    a = mk_line(name="Charlie")
    b = mk_line(name="Alpha")
    c = mk_line(name="Bravo")
    a.description = "Changed"
    db.flush()
    db.expire_all()

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [a.id, b.id, c.id]


# [claude] PLN-GW-09
@pytest.mark.xfail(
    strict=False,
    reason="BUG-100: BaseDAO list methods have no sort order "
    "(non-strict: the rows have no fixed order; which row is on which page rests on physical row order)",
)
def test_pln_gw_09__rows_paged_one_at_a_time_neither_repeat_nor_miss_a_row(db, w1, mk_line):
    """PLN-GW-09 — rows paged one at a time neither repeat nor miss a row.
    Rules: `get_by_workspace` R3 [BUG-100], R4"""
    seqscan(db)
    a = mk_line(name="Charlie")
    b = mk_line(name="Alpha")
    c = mk_line(name="Bravo")
    d = mk_line(name="Echo")
    e = mk_line(name="Delta")
    a.description = "Changed"
    db.flush()
    db.expire_all()

    pages = [dao.get_by_workspace(db, workspace_id=w1.id, skip=k, limit=1) for k in range(5)]

    # Then 1
    assert [len(p) for p in pages] == [1, 1, 1, 1, 1]
    # Then 2
    assert [p[0].id for p in pages] == [a.id, b.id, c.id, d.id, e.id]


# [claude] PLN-GW-10
def test_pln_gw_10__with_the_defaults_101_rows_give_100(db, w1, new_line):
    """PLN-GW-10 — with the defaults 101 rows give 100.
    Rules: `get_by_workspace` R4"""
    rows = [new_line(name=f"Line {k:03d}") for k in range(1, 102)]
    add_many(db, rows)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert len(set(ids(result))) == 100


# [claude] PLN-GW-11
def test_pln_gw_11__limit_1000_gives_all_101(db, w1, new_line):
    """PLN-GW-11 — limit=1000 gives all 101.
    Rules: `get_by_workspace` R4"""
    rows = [new_line(name=f"Line {k:03d}") for k in range(1, 102)]
    add_many(db, rows)
    newest = [row.id for row in rows]

    result = dao.get_by_workspace(db, workspace_id=w1.id, limit=1000)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert sorted(ids(result)) == sorted(newest)


# [claude] PLN-GW-12
def test_pln_gw_12__skip_and_limit_cut_one_row_from_the_middle(db, w1, mk_line):
    """PLN-GW-12 — skip and limit cut one row from the middle.
    Rules: `get_by_workspace` R4"""
    mk_line(name="Alpha")
    mk_line(name="Bravo")
    mk_line(name="Charlie")

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert len(result) == 1


# [claude] PLN-GW-13
def test_pln_gw_13__limit_0_returns_an_empty_list(db, w1, mk_line):
    """PLN-GW-13 — limit=0 returns an empty list.
    Rules: `get_by_workspace` R5"""
    mk_line(name="Alpha")
    mk_line(name="Bravo")

    result = dao.get_by_workspace(db, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [claude] PLN-GW-14
def test_pln_gw_14__limit_1_returns_one_row(db, w1, mk_line):
    """PLN-GW-14 — limit=1 returns one row.
    Rules: `get_by_workspace` R5"""
    mk_line(name="Alpha")
    mk_line(name="Bravo")

    result = dao.get_by_workspace(db, workspace_id=w1.id, limit=1)

    # Then 1
    assert len(result) == 1


# [claude] PLN-GW-15
def test_pln_gw_15__skip_at_the_number_of_rows_returns_an_empty_list(db, w1, mk_line):
    """PLN-GW-15 — skip at the number of rows returns an empty list.
    Rules: `get_by_workspace` R5"""
    mk_line(name="Alpha")
    mk_line(name="Bravo")

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [claude] PLN-GW-16
def test_pln_gw_16__skip_at_the_last_row_returns_one_row(db, w1, mk_line):
    """PLN-GW-16 — skip at the last row returns one row.
    Rules: `get_by_workspace` R5"""
    mk_line(name="Alpha")
    mk_line(name="Bravo")

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=1)

    # Then 1
    assert len(result) == 1


# [claude] PLN-GW-17
def test_pln_gw_17__a_negative_limit_raises(db, w1, mk_line):
    """PLN-GW-17 — a negative limit raises.
    Rules: `get_by_workspace` R6, Errors row 1"""
    mk_line(name="Alpha")
    mk_line(name="Bravo")
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


# [claude] PLN-GW-18
def test_pln_gw_18__a_negative_skip_raises(db, w1, mk_line):
    """PLN-GW-18 — a negative skip raises.
    Rules: `get_by_workspace` R6, Errors row 2"""
    mk_line(name="Alpha")
    mk_line(name="Bravo")
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


# [claude] PLN-GW-19
def test_pln_gw_19__an_unknown_workspace_returns_an_empty_list(db, mk_line):
    """PLN-GW-19 — an unknown workspace returns an empty list.
    Rules: `get_by_workspace` R5"""
    mk_line(name="Alpha")

    result = dao.get_by_workspace(db, workspace_id=MISSING)

    # Then 1
    assert result == []


# [claude] PLN-GW-20
def test_pln_gw_20__a_workspace_with_no_rows_returns_an_empty_list(db, w2, mk_line):
    """PLN-GW-20 — a workspace with no rows returns an empty list.
    Rules: `get_by_workspace` R5"""
    mk_line(name="Alpha")

    result = dao.get_by_workspace(db, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] PLN-GW-21
def test_pln_gw_21__writes_nothing_a_pending_row_that_would_sort_first_stays_pending_and_i(db, w1, f1, mk_line, recorder):
    """PLN-GW-21 — writes nothing: a pending row that would sort first stays pending and is not returned.
    Rules: `get_by_workspace` Side effects"""
    a = mk_line(name="Bravo")
    p = ProductionLine(workspace_id=w1.id, factory_id=f1.id, name="Aardvark")
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


# [claude] PLN-GW-22
def test_pln_gw_22__writes_nothing_a_read_leaves_the_caller_s_unflushed_edit_alone(db, w1, mk_line):
    """PLN-GW-22 — writes nothing: a read leaves the caller's unflushed edit alone.
    Rules: `get_by_workspace` Side effects"""
    a = mk_line(name="Alpha")
    b = mk_line(name="Bravo")
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


# [claude] PLN-GW-23
def test_pln_gw_23__another_workspace_s_row_takes_no_place_in_the_page_whatever_the_row_or(db, w1, w2, f9, mk_line):
    """PLN-GW-23 — another workspace's row takes no place in the page, whatever the row order.
    Rules: `get_by_workspace` R1"""
    z = mk_line(name="Alpha", workspace_id=w2.id, factory_id=f9.id)
    a = mk_line(name="Bravo")
    b = mk_line(name="Charlie")

    result = dao.get_by_workspace(db, workspace_id=w1.id, limit=2)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 3
    assert z.id not in ids(result)


# --------------------------------------------------------------------------- #
# ProductionLineDAO.get_by_factory
# --------------------------------------------------------------------------- #


# [claude] PLN-GF-01
def test_pln_gf_01__returns_a_list_of_the_factory_s_lines(db, w1, f1, mk_line):
    """PLN-GF-01 — returns a list of the factory's lines.
    Rules: `get_by_factory` R1, Returns"""
    a = mk_line(name="Alpha")
    b = mk_line(name="Bravo")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 3
    assert isinstance(result[0], ProductionLine)


# [claude] PLN-GF-02
def test_pln_gf_02__a_line_of_another_factory_is_not_returned(db, w1, f1, f2, mk_line):
    """PLN-GF-02 — a line of another factory is not returned.
    Rules: `get_by_factory` R1"""
    mk_line(name="Alpha", factory_id=f2.id)
    a = mk_line(name="Bravo")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] PLN-GF-03
def test_pln_gf_03__the_right_factory_under_another_workspace_returns_an_empty_list(db, w2, f1, mk_line):
    """PLN-GF-03 — the right factory under another workspace returns an empty list.
    Rules: `get_by_factory` R2"""
    mk_line(name="Alpha")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] PLN-GF-04
def test_pln_gf_04__a_w2_row_on_a_w1_factory_is_returned_for_w2(db, w2, f1, mk_line):
    """PLN-GF-04 — a W2 row on a W1 factory is returned for W2.
    Rules: `get_by_factory` R2"""
    a = mk_line(name="Alpha", workspace_id=w2.id)

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w2.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] PLN-GF-05
def test_pln_gf_05__a_w2_row_on_a_w1_factory_is_not_returned_for_w1(db, w1, w2, f1, mk_line):
    """PLN-GF-05 — a W2 row on a W1 factory is not returned for W1.
    Rules: `get_by_factory` R2"""
    mk_line(name="Alpha", workspace_id=w2.id)

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PLN-GF-06
def test_pln_gf_06__an_inactive_line_is_returned(db, w1, f1, mk_line):
    """PLN-GF-06 — an inactive line is returned.
    Rules: `get_by_factory` R3"""
    a = mk_line(name="Alpha")
    b = mk_line(name="Bravo", is_active=False)

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]


# [claude] PLN-GF-07
def test_pln_gf_07__an_unknown_factory_returns_an_empty_list(db, w1, mk_line):
    """PLN-GF-07 — an unknown factory returns an empty list.
    Rules: `get_by_factory` R3"""
    mk_line(name="Alpha")

    result = dao.get_by_factory(db, factory_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PLN-GF-08
def test_pln_gf_08__factory_id_0_returns_an_empty_list(db, w1, mk_line):
    """PLN-GF-08 — factory_id=0 returns an empty list.
    Rules: `get_by_factory` R3"""
    mk_line(name="Alpha")

    result = dao.get_by_factory(db, factory_id=0, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PLN-GF-09
def test_pln_gf_09__a_factory_with_no_lines_returns_an_empty_list(db, w1, f2, mk_line):
    """PLN-GF-09 — a factory with no lines returns an empty list.
    Rules: `get_by_factory` R3"""
    mk_line(name="Alpha")

    result = dao.get_by_factory(db, factory_id=f2.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PLN-GF-10
def test_pln_gf_10__the_query_does_not_read_the_parent_tables(db, w1, f1, md, mk_line, recorder):
    """PLN-GF-10 — the query does not read the parent tables.
    Rules: `get_by_factory` R3"""
    mk_line(name="Alpha", machine_id=md.id)

    recorder.start()
    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 1
    # Then 2
    sql = recorder.sql()
    assert "machines" not in sql


# [claude] PLN-GF-11
@pytest.mark.xfail(strict=True, reason="BUG-1312: Lines of a soft-deleted factory are still listed")
def test_pln_gf_11__a_soft_deleted_factory_returns_an_empty_list(db, w1, fd, mk_line):
    """PLN-GF-11 — a soft-deleted factory returns an empty list.
    Rules: `get_by_factory` R3a [BUG-1312]"""
    mk_line(name="Alpha")
    mk_line(name="Bravo", factory_id=fd.id)

    result = dao.get_by_factory(db, factory_id=fd.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PLN-GF-12
@pytest.mark.xfail(strict=True, reason="BUG-1312: Lines of a soft-deleted factory are still listed")
def test_pln_gf_12__a_w2_row_on_a_soft_deleted_w1_factory_is_hidden_too(db, w2, fd, mk_line):
    """PLN-GF-12 — a W2 row on a soft-deleted W1 factory is hidden too.
    Rules: `get_by_factory` R3a [BUG-1312]"""
    mk_line(name="Alpha", factory_id=fd.id, workspace_id=w2.id)

    result = dao.get_by_factory(db, factory_id=fd.id, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] PLN-GF-13
def test_pln_gf_13__listing_a_soft_deleted_factory_changes_nothing(db, w1, fd, mk_line, recorder):
    """PLN-GF-13 — listing a soft-deleted factory changes nothing.
    Rules: `get_by_factory` R3b"""
    x = mk_line(name="Alpha", factory_id=fd.id)
    before_x = snap(db, x)
    before_fd = snap(db, fd)

    recorder.start()
    result = dao.get_by_factory(db, factory_id=fd.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    db.expire_all()
    assert snap(db, x) == before_x
    # Then 3
    assert snap(db, fd) == before_fd
    # Then 4
    assert recorder.written() == []


# [claude] PLN-GF-14
def test_pln_gf_14__an_inactive_factory_hides_nothing(db, w1, fi, mk_line):
    """PLN-GF-14 — an inactive factory hides nothing.
    Rules: `get_by_factory` R3b"""
    x = mk_line(name="Alpha", factory_id=fi.id)

    result = dao.get_by_factory(db, factory_id=fi.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [x.id]


# [claude] PLN-GF-15
def test_pln_gf_15__once_the_factory_is_live_again_its_line_is_back_unchanged(db, w1, fd, mk_line):
    """PLN-GF-15 — once the factory is live again its line is back, unchanged.
    Rules: `get_by_factory` R3b"""
    x = mk_line(name="Alpha", factory_id=fd.id)
    fd.is_deleted = False
    fd.deleted_at = None
    fd.deleted_by = None
    db.flush()
    before_x = snap(db, x)

    result = dao.get_by_factory(db, factory_id=fd.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [x.id]
    # Then 2
    db.expire_all()
    assert snap(db, x) == before_x


# [claude] PLN-GF-16
@pytest.mark.xfail(strict=True, reason="BUG-1310: A factory's production lines have no sort order")
def test_pln_gf_16__the_query_orders_by_name_then_id_ascending(db, w1, f1, mk_line, recorder):
    """PLN-GF-16 — the query orders by name, then id, ascending.
    Rules: `get_by_factory` R4 [BUG-1310]"""
    a = mk_line(name="Alpha")

    recorder.start()
    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

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


# [claude] PLN-GF-17
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1310: A factory's production lines have no sort order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_pln_gf_17__names_come_back_case_insensitively_apple_banana_zulu(db, w1, f1, mk_line):
    """PLN-GF-17 — names come back case-insensitively: "apple", "Banana", "Zulu".
    Rules: `get_by_factory` R4 [BUG-1310]"""
    seqscan(db)
    a = mk_line(name="Zulu")
    b = mk_line(name="apple")
    c = mk_line(name="Banana")
    db.expire_all()

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [b.id, c.id, a.id]


# [claude] PLN-GF-18
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1310: A factory's production lines have no sort order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_pln_gf_18__press_and_press_tie_on_the_name_the_lower_id_comes_first_capital_first(db, w1, f1, mk_line):
    """PLN-GF-18 — "Press" and "press" tie on the name: the lower id comes first, capital first.
    Rules: `get_by_factory` R4 [BUG-1310]"""
    seqscan(db)
    a = mk_line(name="Press")
    b = mk_line(name="press")
    db.expire_all()

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert ids(result) == [a.id, b.id]


# [claude] PLN-GF-19
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1310: A factory's production lines have no sort order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_pln_gf_19__press_and_press_tie_on_the_name_the_lower_id_comes_first_small_letter_(db, w1, f1, mk_line):
    """PLN-GF-19 — "press" and "Press" tie on the name: the lower id comes first, small letter first.
    Rules: `get_by_factory` R4 [BUG-1310]"""
    seqscan(db)
    a = mk_line(name="press")
    b = mk_line(name="Press")
    db.expire_all()

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert ids(result) == [a.id, b.id]


# [claude] PLN-GF-20
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1310: A factory's production lines have no sort order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_pln_gf_20__a_tie_on_the_name_goes_to_the_lower_id_when_description_would_sort_oth(db, w1, f1, mk_line):
    """PLN-GF-20 — a tie on the name goes to the lower id, when description would sort otherwise and the lowest id was updated.
    Rules: `get_by_factory` R4 [BUG-1310]"""
    seqscan(db)
    a = mk_line(name="Press", description="Zed")
    b = mk_line(name="Press", description="Abe")
    c = mk_line(name="Press", description="Mid")
    a.description = "Yak"
    db.flush()
    db.expire_all()

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [a.id, b.id, c.id]


# [claude] PLN-GF-21
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1310: A factory's production lines have no sort order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_pln_gf_21__the_order_is_applied_before_the_page_is_cut(db, w1, f1, mk_line):
    """PLN-GF-21 — the order is applied before the page is cut.
    Rules: `get_by_factory` R4 [BUG-1310]"""
    seqscan(db)
    mk_line(name="Zulu")
    mk_line(name="apple")
    c = mk_line(name="Banana")
    db.expire_all()

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert ids(result) == [c.id]


# [claude] PLN-GF-22
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1310: A factory's production lines have no sort order "
    "(non-strict: the rows have no fixed order; which row is on which page rests on physical row order)",
)
def test_pln_gf_22__rows_paged_one_at_a_time_neither_repeat_nor_miss_a_row(db, w1, f1, mk_line):
    """PLN-GF-22 — rows paged one at a time neither repeat nor miss a row.
    Rules: `get_by_factory` R4 [BUG-1310], R5"""
    seqscan(db)
    a = mk_line(name="Charlie")
    b = mk_line(name="Alpha")
    c = mk_line(name="Bravo")
    d = mk_line(name="Echo")
    e = mk_line(name="Delta")
    b.description = "Changed"
    db.flush()
    db.expire_all()

    pages = [dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, skip=k, limit=1) for k in range(5)]

    # Then 1
    assert [len(p) for p in pages] == [1, 1, 1, 1, 1]
    # Then 2
    assert [p[0].id for p in pages] == [b.id, c.id, a.id, e.id, d.id]


# [claude] PLN-GF-23
def test_pln_gf_23__the_factory_filter_runs_before_the_page_skip_2_past_the_two_visible_ro(db, w1, f1, f2, mk_line):
    """PLN-GF-23 — the factory filter runs before the page: skip=2 past the two visible rows gives nothing.
    Rules: `get_by_factory` R1"""
    mk_line(name="Alpha", factory_id=f2.id)
    mk_line(name="Bravo")
    mk_line(name="Charlie")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [claude] PLN-GF-24
def test_pln_gf_24__the_factory_filter_runs_before_the_page_skip_1_leaves_one_visible_row(db, w1, f1, f2, mk_line):
    """PLN-GF-24 — the factory filter runs before the page: skip=1 leaves one visible row.
    Rules: `get_by_factory` R1"""
    x = mk_line(name="Alpha", factory_id=f2.id)
    mk_line(name="Bravo")
    mk_line(name="Charlie")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, skip=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert x.id not in ids(result)


# [claude] PLN-GF-25
def test_pln_gf_25__with_the_defaults_101_rows_give_100(db, w1, f1, new_line):
    """PLN-GF-25 — with the defaults 101 rows give 100.
    Rules: `get_by_factory` R5"""
    rows = [new_line(name=f"Line {k:03d}") for k in range(1, 102)]
    add_many(db, rows)

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert len(set(ids(result))) == 100


# [claude] PLN-GF-26
def test_pln_gf_26__limit_1000_gives_all_101(db, w1, f1, new_line):
    """PLN-GF-26 — limit=1000 gives all 101.
    Rules: `get_by_factory` R5"""
    rows = [new_line(name=f"Line {k:03d}") for k in range(1, 102)]
    add_many(db, rows)
    newest = [row.id for row in rows]

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, limit=1000)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert sorted(ids(result)) == sorted(newest)


# [claude] PLN-GF-27
def test_pln_gf_27__skip_and_limit_cut_one_row_from_the_middle(db, w1, f1, mk_line):
    """PLN-GF-27 — skip and limit cut one row from the middle.
    Rules: `get_by_factory` R5"""
    mk_line(name="Alpha")
    mk_line(name="Bravo")
    mk_line(name="Charlie")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert len(result) == 1


# [claude] PLN-GF-28
def test_pln_gf_28__limit_0_returns_an_empty_list(db, w1, f1, mk_line):
    """PLN-GF-28 — limit=0 returns an empty list.
    Rules: `get_by_factory` R6"""
    mk_line(name="Alpha")
    mk_line(name="Bravo")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [claude] PLN-GF-29
def test_pln_gf_29__limit_1_returns_one_row(db, w1, f1, mk_line):
    """PLN-GF-29 — limit=1 returns one row.
    Rules: `get_by_factory` R6"""
    mk_line(name="Alpha")
    mk_line(name="Bravo")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, limit=1)

    # Then 1
    assert len(result) == 1


# [claude] PLN-GF-30
def test_pln_gf_30__skip_at_the_number_of_rows_returns_an_empty_list(db, w1, f1, mk_line):
    """PLN-GF-30 — skip at the number of rows returns an empty list.
    Rules: `get_by_factory` R6"""
    mk_line(name="Alpha")
    mk_line(name="Bravo")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [claude] PLN-GF-31
def test_pln_gf_31__skip_at_the_last_row_returns_one_row(db, w1, f1, mk_line):
    """PLN-GF-31 — skip at the last row returns one row.
    Rules: `get_by_factory` R6"""
    mk_line(name="Alpha")
    mk_line(name="Bravo")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, skip=1)

    # Then 1
    assert len(result) == 1


# [claude] PLN-GF-32
def test_pln_gf_32__a_negative_limit_raises(db, w1, f1, mk_line):
    """PLN-GF-32 — a negative limit raises.
    Rules: `get_by_factory` R7, Errors row 1"""
    mk_line(name="Alpha")
    mk_line(name="Bravo")
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, limit=-1)
    # Then 2
    assert exc.value.orig.pgcode == "2201W"
    # Then 3
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 4
    assert stored_count(db) == before


# [claude] PLN-GF-33
def test_pln_gf_33__a_negative_skip_raises(db, w1, f1, mk_line):
    """PLN-GF-33 — a negative skip raises.
    Rules: `get_by_factory` R7, Errors row 2"""
    mk_line(name="Alpha")
    mk_line(name="Bravo")
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, skip=-1)
    # Then 2
    assert exc.value.orig.pgcode == "2201X"
    # Then 3
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 4
    assert stored_count(db) == before


# [claude] PLN-GF-34
def test_pln_gf_34__writes_nothing_a_pending_row_that_would_sort_first_stays_pending_and_i(db, w1, f1, mk_line, recorder):
    """PLN-GF-34 — writes nothing: a pending row that would sort first stays pending and is not returned.
    Rules: `get_by_factory` Side effects"""
    a = mk_line(name="Bravo")
    p = ProductionLine(workspace_id=w1.id, factory_id=f1.id, name="Aardvark")
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    recorder.start()
    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

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


# [claude] PLN-GF-35
def test_pln_gf_35__writes_nothing_a_read_leaves_the_caller_s_unflushed_edit_alone(db, w1, f1, mk_line):
    """PLN-GF-35 — writes nothing: a read leaves the caller's unflushed edit alone.
    Rules: `get_by_factory` Side effects"""
    a = mk_line(name="Alpha")
    b = mk_line(name="Bravo")
    b.description = "Edited"

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert b.description == "Edited"


# [claude] PLN-GF-36
def test_pln_gf_36__another_workspace_s_row_takes_no_place_in_the_page_whatever_the_row_or(db, w1, w2, f1, mk_line):
    """PLN-GF-36 — another workspace's row takes no place in the page, whatever the row order.
    Rules: `get_by_factory` R2"""
    z = mk_line(name="Alpha", workspace_id=w2.id)
    a = mk_line(name="Bravo")
    b = mk_line(name="Charlie")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, limit=2)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 3
    assert z.id not in ids(result)


# --------------------------------------------------------------------------- #
# ProductionLineDAO.get_active_by_workspace
# --------------------------------------------------------------------------- #


# [claude] PLN-GA-01
def test_pln_ga_01__returns_a_list_of_the_active_lines(db, w1, mk_line):
    """PLN-GA-01 — returns a list of the active lines.
    Rules: `get_active_by_workspace` R1, Returns"""
    a = mk_line(name="Alpha")
    b = mk_line(name="Bravo")

    result = dao.get_active_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 3
    assert isinstance(result[0], ProductionLine)


# [claude] PLN-GA-02
def test_pln_ga_02__an_inactive_line_is_not_returned(db, w1, mk_line):
    """PLN-GA-02 — an inactive line is not returned.
    Rules: `get_active_by_workspace` R1"""
    mk_line(name="Alpha", is_active=False)
    a = mk_line(name="Bravo")

    result = dao.get_active_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] PLN-GA-03
def test_pln_ga_03__a_row_of_another_workspace_is_not_returned(db, w1, w2, f9, mk_line):
    """PLN-GA-03 — a row of another workspace is not returned.
    Rules: `get_active_by_workspace` R1"""
    mk_line(name="Alpha", workspace_id=w2.id, factory_id=f9.id)
    a = mk_line(name="Bravo")

    result = dao.get_active_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] PLN-GA-04
def test_pln_ga_04__the_active_filter_runs_before_the_page_skip_2_past_the_two_visible_row(db, w1, mk_line):
    """PLN-GA-04 — the active filter runs before the page: skip=2 past the two visible rows gives nothing.
    Rules: `get_active_by_workspace` R1"""
    mk_line(name="Alpha", is_active=False)
    mk_line(name="Bravo")
    mk_line(name="Charlie")

    result = dao.get_active_by_workspace(db, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [claude] PLN-GA-05
def test_pln_ga_05__the_active_filter_runs_before_the_page_skip_1_leaves_one_visible_row(db, w1, mk_line):
    """PLN-GA-05 — the active filter runs before the page: skip=1 leaves one visible row.
    Rules: `get_active_by_workspace` R1"""
    x = mk_line(name="Alpha", is_active=False)
    mk_line(name="Bravo")
    mk_line(name="Charlie")

    result = dao.get_active_by_workspace(db, workspace_id=w1.id, skip=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert x.id not in ids(result)


# [claude] PLN-GA-06
def test_pln_ga_06__a_line_of_a_soft_deleted_machine_is_returned(db, w1, md, mk_line):
    """PLN-GA-06 — a line of a soft-deleted machine is returned.
    Rules: `get_active_by_workspace` R2"""
    a = mk_line(name="Alpha", machine_id=md.id)

    result = dao.get_active_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] PLN-GA-07
def test_pln_ga_07__the_query_does_not_read_the_parent_tables(db, w1, md, mk_line, recorder):
    """PLN-GA-07 — the query does not read the parent tables.
    Rules: `get_active_by_workspace` R2"""
    mk_line(name="Alpha", machine_id=md.id)

    recorder.start()
    result = dao.get_active_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 1
    # Then 2
    sql = recorder.sql()
    assert "machines" not in sql


# [claude] PLN-GA-08
def test_pln_ga_08__an_unknown_workspace_returns_an_empty_list(db, mk_line):
    """PLN-GA-08 — an unknown workspace returns an empty list.
    Rules: `get_active_by_workspace` R3"""
    mk_line(name="Alpha")

    result = dao.get_active_by_workspace(db, workspace_id=MISSING)

    # Then 1
    assert result == []


# [claude] PLN-GA-09
def test_pln_ga_09__a_workspace_with_no_active_lines_returns_an_empty_list(db, w1, mk_line):
    """PLN-GA-09 — a workspace with no active lines returns an empty list.
    Rules: `get_active_by_workspace` R3"""
    mk_line(name="Alpha", is_active=False)

    result = dao.get_active_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PLN-GA-10
@pytest.mark.xfail(strict=True, reason="BUG-1312: Lines of a soft-deleted factory are still listed")
def test_pln_ga_10__a_line_of_a_soft_deleted_factory_is_not_returned(db, w1, fd, mk_line):
    """PLN-GA-10 — a line of a soft-deleted factory is not returned.
    Rules: `get_active_by_workspace` R3a [BUG-1312]"""
    mk_line(name="Alpha", factory_id=fd.id)
    a = mk_line(name="Bravo")

    result = dao.get_active_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] PLN-GA-11
@pytest.mark.xfail(strict=True, reason="BUG-1312: Lines of a soft-deleted factory are still listed")
def test_pln_ga_11__a_w2_line_on_a_soft_deleted_w1_factory_is_hidden_too(db, w2, fd, mk_line):
    """PLN-GA-11 — a W2 line on a soft-deleted W1 factory is hidden too.
    Rules: `get_active_by_workspace` R3a [BUG-1312]"""
    mk_line(name="Alpha", factory_id=fd.id, workspace_id=w2.id)

    result = dao.get_active_by_workspace(db, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] PLN-GA-12
@pytest.mark.xfail(strict=True, reason="BUG-1312: Lines of a soft-deleted factory are still listed")
def test_pln_ga_12__a_hidden_line_takes_no_place_skip_2_past_the_two_live_rows_gives_nothi(db, w1, fd, mk_line):
    """PLN-GA-12 — a hidden line takes no place: skip=2 past the two live rows gives nothing.
    Rules: `get_active_by_workspace` R3a [BUG-1312]"""
    mk_line(name="Alpha", factory_id=fd.id)
    mk_line(name="Bravo")
    mk_line(name="Charlie")

    result = dao.get_active_by_workspace(db, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [claude] PLN-GA-13
@pytest.mark.xfail(strict=True, reason="BUG-1312: Lines of a soft-deleted factory are still listed")
def test_pln_ga_13__a_hidden_line_takes_no_place_skip_1_leaves_one_live_row(db, w1, fd, mk_line):
    """PLN-GA-13 — a hidden line takes no place: skip=1 leaves one live row.
    Rules: `get_active_by_workspace` R3a [BUG-1312]"""
    x = mk_line(name="Alpha", factory_id=fd.id)
    mk_line(name="Bravo")
    mk_line(name="Charlie")

    result = dao.get_active_by_workspace(db, workspace_id=w1.id, skip=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert x.id not in ids(result)


# [claude] PLN-GA-14
def test_pln_ga_14__listing_with_a_soft_deleted_factory_changes_nothing(db, w1, fd, mk_line, recorder):
    """PLN-GA-14 — listing with a soft-deleted factory changes nothing.
    Rules: `get_active_by_workspace` R3b"""
    x = mk_line(name="Alpha", factory_id=fd.id)
    before_x = snap(db, x)
    before_fd = snap(db, fd)

    recorder.start()
    result = dao.get_active_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    db.expire_all()
    assert snap(db, x) == before_x
    # Then 3
    assert snap(db, fd) == before_fd
    # Then 4
    assert recorder.written() == []


# [claude] PLN-GA-15
def test_pln_ga_15__an_inactive_factory_hides_nothing(db, w1, fi, mk_line):
    """PLN-GA-15 — an inactive factory hides nothing.
    Rules: `get_active_by_workspace` R3b"""
    x = mk_line(name="Alpha", factory_id=fi.id)

    result = dao.get_active_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [x.id]


# [claude] PLN-GA-16
def test_pln_ga_16__once_the_factory_is_live_again_its_line_is_back_unchanged(db, w1, fd, mk_line):
    """PLN-GA-16 — once the factory is live again its line is back, unchanged.
    Rules: `get_active_by_workspace` R3b"""
    x = mk_line(name="Alpha", factory_id=fd.id)
    fd.is_deleted = False
    fd.deleted_at = None
    fd.deleted_by = None
    db.flush()
    before_x = snap(db, x)

    result = dao.get_active_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [x.id]
    # Then 2
    db.expire_all()
    assert snap(db, x) == before_x


# [claude] PLN-GA-17
@pytest.mark.xfail(strict=True, reason="BUG-1311: The active production line list has no sort order")
def test_pln_ga_17__the_query_orders_by_name_then_id_ascending(db, w1, mk_line, recorder):
    """PLN-GA-17 — the query orders by name, then id, ascending.
    Rules: `get_active_by_workspace` R4 [BUG-1311]"""
    a = mk_line(name="Alpha")

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


# [claude] PLN-GA-18
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1311: The active production line list has no sort order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_pln_ga_18__names_come_back_case_insensitively_apple_banana_zulu(db, w1, mk_line):
    """PLN-GA-18 — names come back case-insensitively: "apple", "Banana", "Zulu".
    Rules: `get_active_by_workspace` R4 [BUG-1311]"""
    seqscan(db)
    a = mk_line(name="Zulu")
    b = mk_line(name="apple")
    c = mk_line(name="Banana")
    db.expire_all()

    result = dao.get_active_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [b.id, c.id, a.id]


# [claude] PLN-GA-19
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1311: The active production line list has no sort order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_pln_ga_19__press_and_press_tie_on_the_name_the_lower_id_comes_first_capital_first(db, w1, mk_line):
    """PLN-GA-19 — "Press" and "press" tie on the name: the lower id comes first, capital first.
    Rules: `get_active_by_workspace` R4 [BUG-1311]"""
    seqscan(db)
    a = mk_line(name="Press")
    b = mk_line(name="press")
    db.expire_all()

    result = dao.get_active_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert ids(result) == [a.id, b.id]


# [claude] PLN-GA-20
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1311: The active production line list has no sort order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_pln_ga_20__press_and_press_tie_on_the_name_the_lower_id_comes_first_small_letter_(db, w1, mk_line):
    """PLN-GA-20 — "press" and "Press" tie on the name: the lower id comes first, small letter first.
    Rules: `get_active_by_workspace` R4 [BUG-1311]"""
    seqscan(db)
    a = mk_line(name="press")
    b = mk_line(name="Press")
    db.expire_all()

    result = dao.get_active_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert ids(result) == [a.id, b.id]


# [claude] PLN-GA-21
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1311: The active production line list has no sort order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_pln_ga_21__a_tie_on_the_name_goes_to_the_lower_id_when_description_would_sort_oth(db, w1, mk_line):
    """PLN-GA-21 — a tie on the name goes to the lower id, when description would sort otherwise and the lowest id was updated.
    Rules: `get_active_by_workspace` R4 [BUG-1311]"""
    seqscan(db)
    a = mk_line(name="Press", description="Zed")
    b = mk_line(name="Press", description="Abe")
    c = mk_line(name="Press", description="Mid")
    a.description = "Yak"
    db.flush()
    db.expire_all()

    result = dao.get_active_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [a.id, b.id, c.id]


# [claude] PLN-GA-22
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1311: The active production line list has no sort order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_pln_ga_22__the_order_is_applied_before_the_page_is_cut(db, w1, mk_line):
    """PLN-GA-22 — the order is applied before the page is cut.
    Rules: `get_active_by_workspace` R4 [BUG-1311]"""
    seqscan(db)
    mk_line(name="Zulu")
    mk_line(name="apple")
    c = mk_line(name="Banana")
    db.expire_all()

    result = dao.get_active_by_workspace(db, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert ids(result) == [c.id]


# [claude] PLN-GA-23
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1311: The active production line list has no sort order "
    "(non-strict: the rows have no fixed order; which row is on which page rests on physical row order)",
)
def test_pln_ga_23__rows_paged_one_at_a_time_neither_repeat_nor_miss_a_row(db, w1, mk_line):
    """PLN-GA-23 — rows paged one at a time neither repeat nor miss a row.
    Rules: `get_active_by_workspace` R4 [BUG-1311], R5"""
    seqscan(db)
    a = mk_line(name="Charlie")
    b = mk_line(name="Alpha")
    c = mk_line(name="Bravo")
    d = mk_line(name="Echo")
    e = mk_line(name="Delta")
    b.description = "Changed"
    db.flush()
    db.expire_all()

    pages = [dao.get_active_by_workspace(db, workspace_id=w1.id, skip=k, limit=1) for k in range(5)]

    # Then 1
    assert [len(p) for p in pages] == [1, 1, 1, 1, 1]
    # Then 2
    assert [p[0].id for p in pages] == [b.id, c.id, a.id, e.id, d.id]


# [claude] PLN-GA-24
def test_pln_ga_24__with_the_defaults_101_rows_give_100(db, w1, new_line):
    """PLN-GA-24 — with the defaults 101 rows give 100.
    Rules: `get_active_by_workspace` R5"""
    rows = [new_line(name=f"Line {k:03d}") for k in range(1, 102)]
    add_many(db, rows)

    result = dao.get_active_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert len(set(ids(result))) == 100


# [claude] PLN-GA-25
def test_pln_ga_25__limit_1000_gives_all_101(db, w1, new_line):
    """PLN-GA-25 — limit=1000 gives all 101.
    Rules: `get_active_by_workspace` R5"""
    rows = [new_line(name=f"Line {k:03d}") for k in range(1, 102)]
    add_many(db, rows)
    newest = [row.id for row in rows]

    result = dao.get_active_by_workspace(db, workspace_id=w1.id, limit=1000)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert sorted(ids(result)) == sorted(newest)


# [claude] PLN-GA-26
def test_pln_ga_26__skip_and_limit_cut_one_row_from_the_middle(db, w1, mk_line):
    """PLN-GA-26 — skip and limit cut one row from the middle.
    Rules: `get_active_by_workspace` R5"""
    mk_line(name="Alpha")
    mk_line(name="Bravo")
    mk_line(name="Charlie")

    result = dao.get_active_by_workspace(db, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert len(result) == 1


# [claude] PLN-GA-27
def test_pln_ga_27__limit_0_returns_an_empty_list(db, w1, mk_line):
    """PLN-GA-27 — limit=0 returns an empty list.
    Rules: `get_active_by_workspace` R3"""
    mk_line(name="Alpha")
    mk_line(name="Bravo")

    result = dao.get_active_by_workspace(db, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [claude] PLN-GA-28
def test_pln_ga_28__limit_1_returns_one_row(db, w1, mk_line):
    """PLN-GA-28 — limit=1 returns one row.
    Rules: `get_active_by_workspace` R3"""
    mk_line(name="Alpha")
    mk_line(name="Bravo")

    result = dao.get_active_by_workspace(db, workspace_id=w1.id, limit=1)

    # Then 1
    assert len(result) == 1


# [claude] PLN-GA-29
def test_pln_ga_29__skip_at_the_number_of_rows_returns_an_empty_list(db, w1, mk_line):
    """PLN-GA-29 — skip at the number of rows returns an empty list.
    Rules: `get_active_by_workspace` R3"""
    mk_line(name="Alpha")
    mk_line(name="Bravo")

    result = dao.get_active_by_workspace(db, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [claude] PLN-GA-30
def test_pln_ga_30__skip_at_the_last_row_returns_one_row(db, w1, mk_line):
    """PLN-GA-30 — skip at the last row returns one row.
    Rules: `get_active_by_workspace` R3"""
    mk_line(name="Alpha")
    mk_line(name="Bravo")

    result = dao.get_active_by_workspace(db, workspace_id=w1.id, skip=1)

    # Then 1
    assert len(result) == 1


# [claude] PLN-GA-31
def test_pln_ga_31__a_negative_limit_raises(db, w1, mk_line):
    """PLN-GA-31 — a negative limit raises.
    Rules: `get_active_by_workspace` R6, Errors row 1"""
    mk_line(name="Alpha")
    mk_line(name="Bravo")
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


# [claude] PLN-GA-32
def test_pln_ga_32__a_negative_skip_raises(db, w1, mk_line):
    """PLN-GA-32 — a negative skip raises.
    Rules: `get_active_by_workspace` R6, Errors row 2"""
    mk_line(name="Alpha")
    mk_line(name="Bravo")
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


# [claude] PLN-GA-33
def test_pln_ga_33__writes_nothing_a_pending_row_that_would_sort_first_stays_pending_and_i(db, w1, f1, mk_line, recorder):
    """PLN-GA-33 — writes nothing: a pending row that would sort first stays pending and is not returned.
    Rules: `get_active_by_workspace` Side effects"""
    a = mk_line(name="Bravo")
    p = ProductionLine(workspace_id=w1.id, factory_id=f1.id, name="Aardvark")
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


# [claude] PLN-GA-34
def test_pln_ga_34__writes_nothing_a_read_leaves_the_caller_s_unflushed_edit_alone(db, w1, mk_line):
    """PLN-GA-34 — writes nothing: a read leaves the caller's unflushed edit alone.
    Rules: `get_active_by_workspace` Side effects"""
    a = mk_line(name="Alpha")
    b = mk_line(name="Bravo")
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


# [claude] PLN-GA-35
def test_pln_ga_35__another_workspace_s_row_takes_no_place_in_the_page_whatever_the_row_or(db, w1, w2, f9, mk_line):
    """PLN-GA-35 — another workspace's row takes no place in the page, whatever the row order.
    Rules: `get_active_by_workspace` R1"""
    z = mk_line(name="Alpha", workspace_id=w2.id, factory_id=f9.id)
    a = mk_line(name="Bravo")
    b = mk_line(name="Charlie")

    result = dao.get_active_by_workspace(db, workspace_id=w1.id, limit=2)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 3
    assert z.id not in ids(result)


# --------------------------------------------------------------------------- #
# ProductionLineDAO.get_by_id_and_workspace
# --------------------------------------------------------------------------- #


# [claude] PLN-GI-01
def test_pln_gi_01__returns_the_row_with_that_id(db, w1, f1, mk_line):
    """PLN-GI-01 — returns the row with that id.
    Rules: `get_by_id_and_workspace` R1, Returns"""
    mk_line(name="Bravo")
    a = mk_line(name="Alpha")

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, ProductionLine)
    # Then 2
    assert result.id == a.id
    # Then 3
    assert result.name == "Alpha"
    assert result.workspace_id == w1.id
    assert result.factory_id == f1.id


# [claude] PLN-GI-02
def test_pln_gi_02__another_workspace_s_id_returns_none_when_that_row_is_the_later_one(db, w1, w2, f9, mk_line):
    """PLN-GI-02 — another workspace's id returns None, when that row is the later one.
    Rules: `get_by_id_and_workspace` R2"""
    mk_line(name="Alpha")
    z = mk_line(name="Bravo", workspace_id=w2.id, factory_id=f9.id)

    result = dao.get_by_id_and_workspace(db, id=z.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] PLN-GI-03
def test_pln_gi_03__another_workspace_s_id_returns_none_when_that_row_is_the_earlier_one(db, w1, w2, f9, mk_line):
    """PLN-GI-03 — another workspace's id returns None, when that row is the earlier one.
    Rules: `get_by_id_and_workspace` R2"""
    z = mk_line(name="Bravo", workspace_id=w2.id, factory_id=f9.id)
    mk_line(name="Alpha")

    result = dao.get_by_id_and_workspace(db, id=z.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] PLN-GI-04
def test_pln_gi_04__the_id_under_another_workspace_returns_none(db, w2, mk_line):
    """PLN-GI-04 — the id under another workspace returns None.
    Rules: `get_by_id_and_workspace` R2"""
    a = mk_line(name="Alpha")

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w2.id)

    # Then 1
    assert result is None


# [claude] PLN-GI-05
def test_pln_gi_05__an_unknown_id_returns_none(db, w1, mk_line):
    """PLN-GI-05 — an unknown id returns None.
    Rules: `get_by_id_and_workspace` R3"""
    mk_line(name="Alpha")

    result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] PLN-GI-06
def test_pln_gi_06__id_0_returns_none(db, w1, mk_line):
    """PLN-GI-06 — id=0 returns None.
    Rules: `get_by_id_and_workspace` R3"""
    mk_line(name="Alpha")

    result = dao.get_by_id_and_workspace(db, id=0, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] PLN-GI-07
def test_pln_gi_07__writes_nothing_a_read_that_finds_nothing_leaves_the_session_as_it_was(db, w1, f1, mk_line, recorder):
    """PLN-GI-07 — writes nothing: a read that finds nothing leaves the session as it was.
    Rules: `get_by_id_and_workspace` R3, Side effects"""
    a = mk_line(name="Alpha")
    p = ProductionLine(workspace_id=w1.id, factory_id=f1.id, name="Aardvark")
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


# [claude] PLN-GI-08
def test_pln_gi_08__writes_nothing_a_read_that_finds_its_row_leaves_the_session_as_it_was(db, w1, f1, mk_line, recorder):
    """PLN-GI-08 — writes nothing: a read that finds its row leaves the session as it was.
    Rules: `get_by_id_and_workspace` Side effects"""
    a = mk_line(name="Alpha")
    p = ProductionLine(workspace_id=w1.id, factory_id=f1.id, name="Aardvark")
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


# [claude] PLN-GI-09
def test_pln_gi_09__writes_nothing_a_read_leaves_the_caller_s_unflushed_edit_alone(db, w1, mk_line):
    """PLN-GI-09 — writes nothing: a read leaves the caller's unflushed edit alone.
    Rules: `get_by_id_and_workspace` Side effects"""
    a = mk_line(name="Alpha")
    b = mk_line(name="Bravo")
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


# [claude] PLN-GI-10
def test_pln_gi_10__an_inactive_line_is_returned(db, w1, mk_line):
    """PLN-GI-10 — an inactive line is returned.
    Rules: `get_by_id_and_workspace` R4"""
    a = mk_line(name="Alpha", is_active=False)

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.is_active is False


# [claude] PLN-GI-11
def test_pln_gi_11__a_line_of_a_soft_deleted_factory_is_returned(db, w1, fd, mk_line):
    """PLN-GI-11 — a line of a soft-deleted factory is returned.
    Rules: `get_by_id_and_workspace` R4"""
    a = mk_line(name="Alpha", factory_id=fd.id)

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id


# [claude] PLN-GI-12
def test_pln_gi_12__a_line_of_a_soft_deleted_machine_is_returned(db, w1, md, mk_line):
    """PLN-GI-12 — a line of a soft-deleted machine is returned.
    Rules: `get_by_id_and_workspace` R4"""
    a = mk_line(name="Alpha", machine_id=md.id)

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id


# [claude] PLN-GI-13
def test_pln_gi_13__the_query_does_not_read_the_parent_tables(db, w1, mk_line, recorder):
    """PLN-GI-13 — the query does not read the parent tables.
    Rules: `get_by_id_and_workspace` R4"""
    a = mk_line(name="Alpha")

    recorder.start()
    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    sql = recorder.sql()
    assert "JOIN" not in sql
    # Then 3
    assert "factories" not in sql
    # Then 4
    assert "machines" not in sql


# --------------------------------------------------------------------------- #
# Inherited BaseDAO methods on ProductionLine
# --------------------------------------------------------------------------- #


# [claude] PLN-INH-01
def test_pln_inh_01__create_with_a_dict_gives_the_defaults(db, w1, f1):
    """PLN-INH-01 — create with a dict gives the defaults.
    Rules: `inherited` R1"""
    result = dao.create(db, obj_in={"workspace_id": w1.id, "factory_id": f1.id, "name": "Press"})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.is_active is True
    assert row.machine_id is None
    # Then 3
    row = reread(db, result)
    assert row.name == "Press"
    assert row.workspace_id == w1.id
    assert row.factory_id == f1.id


# [claude] PLN-INH-02
def test_pln_inh_02__create_with_a_productionlinecreate_fails_on_flush_and_saves_nothing(db, f1):
    """PLN-INH-02 — create with a ProductionLineCreate fails on flush and saves nothing.
    Rules: `inherited` R2"""
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in=ProductionLineCreate(factory_id=f1.id, name="Press"))
    # Then 2
    assert exc.value.orig.pgcode == "23502"
    # Then 3
    assert count_rows(db, ProductionLine) == 0


# [claude] PLN-INH-03
def test_pln_inh_03__two_lines_with_one_name_in_one_factory_are_both_saved(db, w1, f1, mk_line):
    """PLN-INH-03 — two lines with one name in one factory are both saved.
    Rules: `inherited` R3"""
    a = mk_line(name="Press")

    result = dao.create(db, obj_in={"workspace_id": w1.id, "factory_id": f1.id, "name": "Press"})

    # Then 1
    assert result.id != a.id
    # Then 2
    assert count_rows(db, ProductionLine, ProductionLine.name == "Press") == 2


# [claude] PLN-INH-04
def test_pln_inh_04__after_a_hard_delete_of_the_machine_the_line_stays_with_machine_id_none(db, m1, mk_line):
    """PLN-INH-04 — after a hard delete of the machine the line stays, with machine_id None.
    Rules: `inherited` R4"""
    a = mk_line(name="Press", machine_id=m1.id)

    db.execute(text("DELETE FROM machines WHERE id = :i"), {"i": m1.id})

    # Then 1
    row = reread(db, a)
    assert row.machine_id is None
    # Then 2
    assert count_rows(db, ProductionLine) == 1


# --------------------------------------------------------------------------- #
# Schemas ProductionLineCreate, ProductionLineUpdate (BUG-1313)
# --------------------------------------------------------------------------- #


# [claude] PLN-SCH-01
@pytest.mark.xfail(strict=True, reason="BUG-1313: Blank production line names accepted; names stored untrimmed")
def test_pln_sch_01__a_whitespace_only_name_is_refused_on_create(f1):
    """PLN-SCH-01 — a whitespace-only name is refused on create.
    Rules: `schema` BUG-1313"""
    # Then 1
    with pytest.raises(ValidationError):
        ProductionLineCreate(factory_id=f1.id, name="   ")


# [claude] PLN-SCH-02
@pytest.mark.xfail(strict=True, reason="BUG-1313: Blank production line names accepted; names stored untrimmed")
def test_pln_sch_02__a_whitespace_only_name_is_refused_on_update():
    """PLN-SCH-02 — a whitespace-only name is refused on update.
    Rules: `schema` BUG-1313"""
    # Then 1
    with pytest.raises(ValidationError):
        ProductionLineUpdate(name="   ")


# [claude] PLN-SCH-03
@pytest.mark.xfail(strict=True, reason="BUG-1313: Blank production line names accepted; names stored untrimmed")
def test_pln_sch_03__a_name_is_stored_trimmed_on_create(f1):
    """PLN-SCH-03 — a name is stored trimmed on create.
    Rules: `schema` BUG-1313"""
    result = ProductionLineCreate(factory_id=f1.id, name=" a ")

    # Then 1
    assert result.name == "a"


# [claude] PLN-SCH-04
@pytest.mark.xfail(strict=True, reason="BUG-1313: Blank production line names accepted; names stored untrimmed")
def test_pln_sch_04__a_name_is_stored_trimmed_on_update():
    """PLN-SCH-04 — a name is stored trimmed on update.
    Rules: `schema` BUG-1313"""
    result = ProductionLineUpdate(name=" a ")

    # Then 1
    assert result.name == "a"


# [claude] PLN-SCH-05
def test_pln_sch_05__inner_spaces_and_case_are_kept_as_typed(f1):
    """PLN-SCH-05 — inner spaces and case are kept as typed.
    Rules: `schema` Companion"""
    result = ProductionLineCreate(factory_id=f1.id, name="Line  B")

    # Then 1
    assert result.name == "Line  B"
