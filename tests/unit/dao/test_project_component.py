"""Unit tests for app/dao/project_component.py.

Implements tests/unit/dao/project_component.cases.md, one test per case, in
card order. Real Postgres session (`db` fixture).
Nothing is mocked and no clock is patched (Conventions, Externals: None).

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117, DTZ001  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`, and naive datetimes)
from datetime import datetime

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import DataError

from app.dao.project_component import project_component_dao
from app.models.factory import Factory
from app.models.project import Project
from app.models.project_component import ProjectComponent
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton project_component_dao" (a module-level name, not a fixture)
dao = project_component_dao

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999

# Convention "T12"
T12 = datetime(2026, 3, 4, 12, 0, 0)


# --------------------------------------------------------------------------- #
# Conventions -> the rows that exist in every test
# --------------------------------------------------------------------------- #

def _add(db, row):
    db.add(row)
    db.flush()
    return row


# Conventions list these rows in this order; each fixture depends on the one before,
# so the rows are flushed one at a time and ids rise in that order.
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
def pj1(db, w1, f1):
    return _add(db, Project(workspace_id=w1.id, factory_id=f1.id, name="Project One", description="Main"))


@pytest.fixture
def pj2(db, w1, f1, pj1):
    return _add(db, Project(workspace_id=w1.id, factory_id=f1.id, name="Project Two", description="Main"))


@pytest.fixture
def pjd(db, w1, u1, f1, pj2):
    return _add(db, Project(workspace_id=w1.id, factory_id=f1.id, name="Project Three", description="Main", is_deleted=True, deleted_at=T12, deleted_by=u1.id))


# Convention "These rows exist in every test and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2, u1, f1, pj1, pj2, pjd):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builders (fixtures; each flushes before it returns)
# --------------------------------------------------------------------------- #

# Convention "component": the columns the Conventions say are not passed stay out of the constructor
@pytest.fixture
def mk_component(db, w1, pj1):
    """mk_component(name=..., **columns) -> ProjectComponent. Keywords only."""
    def _mk(*, name, **columns):
        fields = {"workspace_id": w1.id, "project_id": pj1.id, "name": name}
        fields.update(columns)
        return _add(db, ProjectComponent(**fields))
    return _mk


# The "built with add_all" Given lines
@pytest.fixture
def mk_many(db, w1, pj1):
    """mk_many(count) -> `in_order`: the ids of the rows, in the card's order."""
    def _mk(count):
        rows = [ProjectComponent(workspace_id=w1.id, project_id=pj1.id, name=f"Part {k:03d}")
                for k in range(1, count + 1)]
        db.add_all(rows)
        db.flush()
        return [row.id for row in rows]
    return _mk


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (plain functions; no expected values inside)
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


# Convention "nothing written": the number of project_components rows stored (all workspaces)
def stored_count(db):
    return db.execute(select(func.count()).select_from(ProjectComponent.__table__)).scalar_one()


# Convention "seqscan": transaction-local, gone with the rollback
def seqscan(db):
    db.execute(text("SET LOCAL enable_indexscan = off"))
    db.execute(text("SET LOCAL enable_bitmapscan = off"))
    db.execute(text("SET LOCAL enable_indexonlyscan = off"))


# Convention "Statement recorder": the SQL text of every statement the session's
# connection sends while the block runs.
class StatementRecorder:
    def __init__(self, db):
        self.bind = db.get_bind()
        self.statements = []

    def _record(self, conn, cursor, statement, parameters, context, executemany):
        self.statements.append(statement)

    def __enter__(self):
        event.listen(self.bind, "before_cursor_execute", self._record)
        return self

    def __exit__(self, *exc_info):
        event.remove(self.bind, "before_cursor_execute", self._record)
        return False

    def selects(self):
        return [s for s in self.statements if s.lstrip().upper().startswith("SELECT")]

    def written(self):
        return [s for s in self.statements if s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]

    def sql(self):
        """The one SELECT from project_components; fails loudly unless there is exactly one."""
        [statement] = [s for s in self.selects() if "project_components" in s]
        return statement


# Convention "order_part": the text of `sql` after its first ORDER BY ("" when there is none)
def order_part_of(sql):
    return sql.split("ORDER BY", 1)[1] if "ORDER BY" in sql else ""


# --------------------------------------------------------------------------- #
# DAOProjectComponent.get_by_project
# --------------------------------------------------------------------------- #


# [claude] PCO-G-01
def test_pco_g_01__returns_a_list_of_the_project_s_components(db, w1, pj1, mk_component):
    """PCO-G-01 — returns a list of the project's components.
    Rules: `get_by_project` R1, Returns"""
    a = mk_component(name="Part 1")
    b = mk_component(name="Part 2")

    result = dao.get_by_project(db, project_id=pj1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert len(result) == 2
    # Then 3
    assert set(ids(result)) == {a.id, b.id}
    # Then 4
    assert isinstance(result[0], ProjectComponent)


# [claude] PCO-G-02
def test_pco_g_02__a_component_of_another_project_of_the_same_workspace_is_not_returned_t(db, w1, pj1, pj2, mk_component):
    """PCO-G-02 — a component of another project of the same workspace is not returned, though it sorts first.
    Rules: `get_by_project` R1"""
    mk_component(name="Part 1", project_id=pj2.id)
    a = mk_component(name="Part 2")

    result = dao.get_by_project(db, project_id=pj1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] PCO-G-03
def test_pco_g_03__the_right_project_under_another_workspace_returns_an_empty_list(db, w2, pj1, mk_component):
    """PCO-G-03 — the right project under another workspace returns an empty list.
    Rules: `get_by_project` R1"""
    mk_component(name="Part 1")

    result = dao.get_by_project(db, project_id=pj1.id, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] PCO-G-04
def test_pco_g_04__an_unknown_workspace_returns_an_empty_list(db, pj1, mk_component):
    """PCO-G-04 — an unknown workspace returns an empty list.
    Rules: `get_by_project` R1"""
    mk_component(name="Part 1")

    result = dao.get_by_project(db, project_id=pj1.id, workspace_id=MISSING)

    # Then 1
    assert result == []


# [claude] PCO-G-05
def test_pco_g_05__a_w2_row_on_a_w1_project_is_returned_for_w2_only_the_row_s_workspace_i(db, w2, pj1, mk_component):
    """PCO-G-05 — a W2 row on a W1 project is returned for W2: only the row's workspace is compared.
    Rules: `get_by_project` R1"""
    a = mk_component(name="Part 1", workspace_id=w2.id)

    result = dao.get_by_project(db, project_id=pj1.id, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] PCO-G-06
def test_pco_g_06__a_w2_row_on_a_w1_project_is_not_returned_for_w1_though_it_sorts_first(db, w1, w2, pj1, mk_component):
    """PCO-G-06 — a W2 row on a W1 project is not returned for W1, though it sorts first.
    Rules: `get_by_project` R1"""
    mk_component(name="Part 1", workspace_id=w2.id)
    a = mk_component(name="Part 2")

    result = dao.get_by_project(db, project_id=pj1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] PCO-G-07
def test_pco_g_07__an_unknown_project_id_returns_an_empty_list(db, w1, mk_component):
    """PCO-G-07 — an unknown project id returns an empty list.
    Rules: `get_by_project` R2"""
    mk_component(name="Part 1")

    result = dao.get_by_project(db, project_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PCO-G-08
def test_pco_g_08__project_id_0_returns_an_empty_list(db, w1, mk_component):
    """PCO-G-08 — project id 0 returns an empty list.
    Rules: `get_by_project` R2"""
    mk_component(name="Part 1")

    result = dao.get_by_project(db, project_id=0, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PCO-G-09
def test_pco_g_09__a_project_with_no_rows_returns_an_empty_list(db, w1, pj2, mk_component):
    """PCO-G-09 — a project with no rows returns an empty list.
    Rules: `get_by_project` R2"""
    mk_component(name="Part 1")

    result = dao.get_by_project(db, project_id=pj2.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PCO-G-10
def test_pco_g_10__the_project_filter_comes_before_paging_a_row_of_another_project_does_n(db, w1, pj1, pj2, mk_component):
    """PCO-G-10 — the project filter comes before paging: a row of another project does not use up the skip.
    Rules: `get_by_project` R1, R4"""
    mk_component(name="Aaa", project_id=pj2.id)
    a = mk_component(name="Beta")
    b = mk_component(name="Gamma")

    result = dao.get_by_project(db, project_id=pj1.id, workspace_id=w1.id, skip=1, limit=10)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id in {a.id, b.id}


# [claude] PCO-G-11
def test_pco_g_11__the_workspace_filter_comes_before_paging_a_row_of_another_workspace_do(db, w1, w2, pj1, mk_component):
    """PCO-G-11 — the workspace filter comes before paging: a row of another workspace does not use up the skip.
    Rules: `get_by_project` R1, R4"""
    mk_component(name="Aaa", workspace_id=w2.id)
    a = mk_component(name="Beta")
    b = mk_component(name="Gamma")

    result = dao.get_by_project(db, project_id=pj1.id, workspace_id=w1.id, skip=1, limit=10)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id in {a.id, b.id}


# [claude] PCO-G-12
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1275: A project's components have no sort order"
    " (non-strict: the order rests on physical row order, which can match by accident)",
)
def test_pco_g_12__components_are_ordered_by_name_case_insensitive_whatever_their_ids(db, w1, pj1, mk_component):
    """PCO-G-12 — components are ordered by name, case-insensitive, whatever their ids.
    Rules: `get_by_project` R3 [BUG-1275]"""
    a = mk_component(name="Beta")
    b = mk_component(name="alpha")
    c = mk_component(name="Gamma")

    result = dao.get_by_project(db, project_id=pj1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [b.id, a.id, c.id]


# [claude] PCO-G-13
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1275: A project's components have no sort order"
    " (non-strict: the order rests on physical row order, which can match by accident)",
)
def test_pco_g_13__on_a_name_tie_also_across_case_the_lowest_id_comes_first(db, w1, pj1, mk_component):
    """PCO-G-13 — on a name tie, also across case, the lowest id comes first.
    Rules: `get_by_project` R3 [BUG-1275]"""
    a = mk_component(name="roof")
    b = mk_component(name="Roof")
    db.execute(text("UPDATE project_components SET name = name WHERE id = :i"), {"i": a.id})
    db.expire_all()
    seqscan(db)

    result = dao.get_by_project(db, project_id=pj1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert ids(result) == [a.id, b.id]


# [claude] PCO-G-14
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1275: A project's components have no sort order"
    " (non-strict: the order rests on physical row order, which can match by accident)",
)
def test_pco_g_14__the_order_comes_before_paging_and_the_hidden_row_does_not_use_up_the_s(db, w1, pj1, pj2, mk_component):
    """PCO-G-14 — the order comes before paging, and the hidden row does not use up the skip.
    Rules: `get_by_project` R3 [BUG-1275]"""
    mk_component(name="Aaa", project_id=pj2.id)
    a = mk_component(name="Beta")
    mk_component(name="alpha")
    mk_component(name="Gamma")

    result = dao.get_by_project(db, project_id=pj1.id, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert ids(result) == [a.id]


# [claude] PCO-G-15
@pytest.mark.xfail(strict=True, reason="BUG-1275: A project's components have no sort order")
def test_pco_g_15__the_query_orders_by_name_then_id_ascending(db, w1, pj1, mk_component):
    """PCO-G-15 — the query orders by name, then id ascending.
    Rules: `get_by_project` R3 [BUG-1275]"""
    a = mk_component(name="Part 1")

    with StatementRecorder(db) as recorder:
        result = dao.get_by_project(db, project_id=pj1.id, workspace_id=w1.id)
    sql = recorder.sql()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "name" in order_part
    # Then 4
    assert ".id" in order_part
    # Then 5
    assert order_part.index("name") < order_part.index(".id")
    # Then 6
    assert "DESC" not in order_part.upper()


# [claude] PCO-G-16
def test_pco_g_16__with_the_default_limit_103_rows_give_100(db, w1, pj1, mk_many):
    """PCO-G-16 — with the default limit 103 rows give 100.
    Rules: `get_by_project` R4"""
    mk_many(103)

    result = dao.get_by_project(db, project_id=pj1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100


# [claude] PCO-G-17
def test_pco_g_17__limit_1000_gives_all_103_rows(db, w1, pj1, mk_many):
    """PCO-G-17 — limit=1000 gives all 103 rows.
    Rules: `get_by_project` R4"""
    in_order = mk_many(103)

    result = dao.get_by_project(db, project_id=pj1.id, workspace_id=w1.id, limit=1000)

    # Then 1
    assert len(result) == 103
    # Then 2
    assert set(ids(result)) == set(in_order)


# [claude] PCO-G-18
def test_pco_g_18__limit_0_returns_an_empty_list(db, w1, pj1, mk_component):
    """PCO-G-18 — limit=0 returns an empty list.
    Rules: `get_by_project` R5"""
    mk_component(name="Part 1")
    mk_component(name="Part 2")
    mk_component(name="Part 3")

    result = dao.get_by_project(db, project_id=pj1.id, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [claude] PCO-G-19
def test_pco_g_19__limit_1_returns_one_row_the_other_side_of_limit_0(db, w1, pj1, mk_component):
    """PCO-G-19 — limit=1 returns one row: the other side of limit=0.
    Rules: `get_by_project` R5"""
    mk_component(name="Part 1")
    mk_component(name="Part 2")
    mk_component(name="Part 3")

    result = dao.get_by_project(db, project_id=pj1.id, workspace_id=w1.id, limit=1)

    # Then 1
    assert len(result) == 1


# [claude] PCO-G-20
def test_pco_g_20__skip_past_the_end_returns_an_empty_list(db, w1, pj1, mk_component):
    """PCO-G-20 — skip past the end returns an empty list.
    Rules: `get_by_project` R5"""
    mk_component(name="Part 1")
    mk_component(name="Part 2")
    mk_component(name="Part 3")

    result = dao.get_by_project(db, project_id=pj1.id, workspace_id=w1.id, skip=3)

    # Then 1
    assert result == []


# [claude] PCO-G-21
def test_pco_g_21__skip_2_of_three_rows_leaves_one_row_the_other_side_of_skip_past_the_en(db, w1, pj1, mk_component):
    """PCO-G-21 — skip=2 of three rows leaves one row: the other side of skip past the end.
    Rules: `get_by_project` R5"""
    mk_component(name="Part 1")
    mk_component(name="Part 2")
    mk_component(name="Part 3")

    result = dao.get_by_project(db, project_id=pj1.id, workspace_id=w1.id, skip=2)

    # Then 1
    assert len(result) == 1


# [claude] PCO-G-22
def test_pco_g_22__a_negative_limit_is_refused_by_postgres(db, w1, pj1, mk_component):
    """PCO-G-22 — a negative limit is refused by Postgres.
    Rules: `get_by_project` R6, Errors row 1 (negative `limit`)"""
    mk_component(name="Part 1")
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_project(db, project_id=pj1.id, workspace_id=w1.id, limit=-1)
    # Then 2
    assert exc.value.orig.pgcode == "2201W"
    # Then 3
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 4
    assert stored_count(db) == before


# [claude] PCO-G-23
def test_pco_g_23__a_negative_skip_is_refused_by_postgres(db, w1, pj1, mk_component):
    """PCO-G-23 — a negative skip is refused by Postgres.
    Rules: `get_by_project` R6, Errors row 2 (negative `skip`)"""
    mk_component(name="Part 1")
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_project(db, project_id=pj1.id, workspace_id=w1.id, skip=-1)
    # Then 2
    assert exc.value.orig.pgcode == "2201X"
    # Then 3
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 4
    assert stored_count(db) == before


# [claude] PCO-G-24
def test_pco_g_24__the_components_of_a_soft_deleted_project_are_returned(db, w1, pjd, mk_component):
    """PCO-G-24 — the components of a soft-deleted project are returned.
    Rules: `get_by_project` R7"""
    a = mk_component(name="Roof", project_id=pjd.id)

    result = dao.get_by_project(db, project_id=pjd.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] PCO-G-25
def test_pco_g_25__writes_nothing_a_pending_row_stays_pending_and_alone_in_the_session(db, w1, pj1, mk_component):
    """PCO-G-25 — writes nothing: a pending row stays pending and alone in the session.
    Rules: `get_by_project` Side effects"""
    a = mk_component(name="Part 1")
    p = ProjectComponent(workspace_id=w1.id, project_id=pj1.id, name="Pending")
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_project(db, project_id=pj1.id, workspace_id=w1.id)
    written = recorder.written()
    selects = recorder.selects()
    sql = recorder.sql()

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert p in db.new
    # Then 3
    assert p.id is None
    # Then 4
    assert len(db.new) == 1
    # Then 5
    assert not db.dirty
    # Then 6
    assert not db.deleted
    # Then 7
    assert written == []
    # Then 8
    assert len(selects) == 1
    # Then 9
    assert "FOR UPDATE" not in sql.upper()
    # Then 10
    assert "projects" not in sql
    # Then 11
    assert stored_count(db) == before
    # Then 12
    db.expire_all()
    assert snap(db, a) == before_a


# [claude] PCO-G-26
def test_pco_g_26__writes_nothing_an_unflushed_edit_of_another_row_stays_unflushed_and_is(db, w1, pj1, pj2, mk_component):
    """PCO-G-26 — writes nothing: an unflushed edit of another row stays unflushed and is not reloaded.
    Rules: `get_by_project` Side effects"""
    a = mk_component(name="Part 1")
    b = mk_component(name="Part 2", project_id=pj2.id)
    b.name = "Edited"

    result = dao.get_by_project(db, project_id=pj1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert b.name == "Edited"


# [claude] PCO-G-27
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1275: A project's components have no sort order"
    " (non-strict: the order rests on physical row order, which can match by accident)",
)
def test_pco_g_27__names_that_differ_only_in_case_tie_and_id_decides_whichever_case_comes(db, w1, pj1, mk_component):
    """PCO-G-27 — names that differ only in case tie, and id decides, whichever case comes first.
    Rules: `get_by_project` R3 [BUG-1275]"""
    a = mk_component(name="roof")
    b = mk_component(name="Roof")
    c = mk_component(name="Wall")
    d = mk_component(name="wall")
    db.expire_all()

    result = dao.get_by_project(db, project_id=pj1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 4
    # Then 2
    assert ids(result) == [a.id, b.id, c.id, d.id]
