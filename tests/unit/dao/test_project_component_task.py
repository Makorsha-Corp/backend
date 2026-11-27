"""Unit tests for app/dao/project_component_task.py.

Implements tests/unit/dao/project_component_task.cases.md, one test per case,
in card order. Real Postgres session (`db` fixture). Nothing is mocked and no
clock is patched (Conventions, Externals: None).

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`)
import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy.exc import DataError

from app.dao.project_component_task import project_component_task_dao
from app.models.factory import Factory
from app.models.project import Project
from app.models.project_component import ProjectComponent
from app.models.project_component_task import ProjectComponentTask
from tests.unit.factories import make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton project_component_task_dao" (a module-level name, not a fixture)
dao = project_component_task_dao

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999


# --------------------------------------------------------------------------- #
# Conventions -> the rows that exist in every test
# --------------------------------------------------------------------------- #

def _add(db, row):
    db.add(row)
    db.flush()
    return row


# The Conventions list these rows in this order; each fixture depends on the one
# before, so the rows are flushed one at a time and ids rise in that order.
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
def pj1(db, w1, f1):
    return _add(db, Project(workspace_id=w1.id, factory_id=f1.id, name="Project One", description="Main"))


@pytest.fixture
def pjd(db, w1, f1, pj1):
    return _add(db, Project(workspace_id=w1.id, factory_id=f1.id, name="Project Gone", description="Main",
                            is_deleted=True, is_active=False))


@pytest.fixture
def pc1(db, w1, pj1, pjd):
    return _add(db, ProjectComponent(workspace_id=w1.id, project_id=pj1.id, name="Roof"))


@pytest.fixture
def pc2(db, w1, pj1, pc1):
    return _add(db, ProjectComponent(workspace_id=w1.id, project_id=pj1.id, name="Wall"))


@pytest.fixture
def pcd(db, w1, pjd, pc2):
    return _add(db, ProjectComponent(workspace_id=w1.id, project_id=pjd.id, name="Old roof"))


# Convention "These rows exist in every test and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2, f1, pj1, pjd, pc1, pc2, pcd):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builders (fixtures; each flushes before it returns)
# --------------------------------------------------------------------------- #

# Convention "task": is_note and is_completed are left to their defaults unless listed
@pytest.fixture
def mk_task(db, w1, pc1):
    """mk_task(name=..., **columns) -> ProjectComponentTask. Keywords only."""
    def _mk(*, name, **columns):
        fields = {"workspace_id": w1.id, "project_component_id": pc1.id, "name": name, "description": "Do it"}
        fields.update(columns)
        return _add(db, ProjectComponentTask(**fields))
    return _mk


# Convention "note" = task, but is_note True
@pytest.fixture
def mk_note(mk_task):
    """mk_note(name=..., **columns) -> ProjectComponentTask with is_note True."""
    def _mk(*, name, **columns):
        return mk_task(name=name, is_note=True, **columns)
    return _mk


# The "104 tasks E1 ... E104, built with add_all and flushed" Given lines
@pytest.fixture
def mk_many(db, w1, pc1):
    """mk_many(count) -> the rows E1 ... Ecount, Ek named f"Task {k:03d}"."""
    def _mk(count):
        rows = [ProjectComponentTask(workspace_id=w1.id, project_component_id=pc1.id, name=f"Task {k:03d}",
                                     description="Do it")
                for k in range(1, count + 1)]
        db.add_all(rows)
        db.flush()
        return rows
    return _mk


# Convention "bumpK(X)"
def bump(db, row):
    db.execute(text("UPDATE project_component_tasks SET name = name WHERE id = :i"), {"i": row.id})
    db.expire_all()


# Convention "seqscan"
def seqscan(db):
    db.execute(text("SET LOCAL enable_indexscan = off"))
    db.execute(text("SET LOCAL enable_bitmapscan = off"))
    db.execute(text("SET LOCAL enable_indexonlyscan = off"))


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (plain functions; no expected values inside)
# --------------------------------------------------------------------------- #

# Convention "ids(result)": in the order returned
def ids(result):
    return [row.id for row in result]


# Convention "nothing written": the number of project_component_tasks rows stored (all workspaces)
def stored_count(db):
    return db.scalar(select(func.count()).select_from(ProjectComponentTask.__table__))


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

    def written(self):
        return [s for s in self.statements if s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]

    def sql(self):
        """The one SELECT from project_component_tasks; fails loudly unless there is exactly one."""
        [statement] = [s for s in self.statements
                       if s.lstrip().upper().startswith("SELECT") and "FROM project_component_tasks" in s]
        return statement


# Convention "order_part": the text of `sql` after its first ORDER BY and before any LIMIT ("" when there is no ORDER BY)
def order_part_of(sql):
    return sql.split("ORDER BY", 1)[1].split("LIMIT", 1)[0] if "ORDER BY" in sql else ""


# --------------------------------------------------------------------------- #
# DAOProjectComponentTask.get_by_component
# --------------------------------------------------------------------------- #


# [claude] PCT-GC-01
def test_pct_gc_01__with_is_note_none_open_and_completed_tasks_and_notes(db, w1, pc1, mk_task, mk_note):
    """PCT-GC-01 — with is_note None: open and completed tasks and notes of the component.
    Rules: `get_by_component` R1, R2, R3, Returns"""
    t = mk_task(name="Fix")
    c = mk_task(name="Paint", is_completed=True)
    n = mk_note(name="Remark")

    result = dao.get_by_component(db, project_component_id=pc1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert set(ids(result)) == {t.id, c.id, n.id}
    # Then 3
    assert isinstance(result[0], ProjectComponentTask)


# [claude] PCT-GC-02
def test_pct_gc_02__a_row_of_another_component_is_not_returned(db, w1, pc1, pc2, mk_task):
    """PCT-GC-02 — a row of another component is not returned.
    Rules: `get_by_component` R1"""
    mk_task(name="Aaa", project_component_id=pc2.id)
    t = mk_task(name="Fix")

    result = dao.get_by_component(db, project_component_id=pc1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [t.id]


# [claude] PCT-GC-03
def test_pct_gc_03__a_w2_row_on_a_w1_component_is_not_returned_for_w1(db, w1, w2, pc1, mk_task):
    """PCT-GC-03 — a W2 row on a W1 component is not returned for W1.
    Rules: `get_by_component` R1"""
    t = mk_task(name="Fix")
    mk_task(name="Aaa", workspace_id=w2.id)

    result = dao.get_by_component(db, project_component_id=pc1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [t.id]


# [claude] PCT-GC-04
def test_pct_gc_04__a_w2_row_on_a_w1_component_is_returned_for_w2(db, w2, pc1, mk_task):
    """PCT-GC-04 — a W2 row on a W1 component is returned for W2.
    Rules: `get_by_component` R1"""
    mk_task(name="Fix")
    x = mk_task(name="Aaa", workspace_id=w2.id)

    result = dao.get_by_component(db, project_component_id=pc1.id, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [x.id]


# [claude] PCT-GC-05
def test_pct_gc_05__an_unknown_component_id_returns_an_empty_list(db, w1, mk_task):
    """PCT-GC-05 — an unknown component id returns an empty list.
    Rules: `get_by_component` R1"""
    mk_task(name="Fix")

    result = dao.get_by_component(db, project_component_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PCT-GC-06
def test_pct_gc_06__component_id_0_returns_an_empty_list(db, w1, mk_task):
    """PCT-GC-06 — component id 0 returns an empty list.
    Rules: `get_by_component` R1"""
    mk_task(name="Fix")

    result = dao.get_by_component(db, project_component_id=0, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PCT-GC-07
def test_pct_gc_07__is_note_true_returns_only_notes(db, w1, pc1, mk_task, mk_note):
    """PCT-GC-07 — is_note=True returns only notes.
    Rules: `get_by_component` R2"""
    mk_task(name="Fix")
    n = mk_note(name="Remark")

    result = dao.get_by_component(db, project_component_id=pc1.id, workspace_id=w1.id, is_note=True)

    # Then 1
    assert ids(result) == [n.id]


# [claude] PCT-GC-08
def test_pct_gc_08__is_note_false_returns_only_tasks(db, w1, pc1, mk_task, mk_note):
    """PCT-GC-08 — is_note=False returns only tasks.
    Rules: `get_by_component` R2"""
    t = mk_task(name="Fix")
    mk_note(name="Remark")

    result = dao.get_by_component(db, project_component_id=pc1.id, workspace_id=w1.id, is_note=False)

    # Then 1
    assert ids(result) == [t.id]


# [claude] PCT-GC-09
def test_pct_gc_09__the_note_filter_comes_before_the_page_a_note_takes_no_place(db, w1, pc1, mk_task, mk_note):
    """PCT-GC-09 — the note filter comes before the page: a note takes no place.
    Rules: `get_by_component` R2, R5"""
    mk_note(name="Aaa")
    a = mk_task(name="Beta")
    b = mk_task(name="Gamma")

    result = dao.get_by_component(db, project_component_id=pc1.id, workspace_id=w1.id, is_note=False, skip=1, limit=10)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id in {a.id, b.id}


# [claude] PCT-GC-10
def test_pct_gc_10__the_component_filter_comes_before_the_page(db, w1, pc1, pc2, mk_task):
    """PCT-GC-10 — the component filter comes before the page: another component's row takes no place.
    Rules: `get_by_component` R1, R5"""
    mk_task(name="Aaa", project_component_id=pc2.id)
    a = mk_task(name="Beta")
    b = mk_task(name="Gamma")

    result = dao.get_by_component(db, project_component_id=pc1.id, workspace_id=w1.id, skip=1, limit=10)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id in {a.id, b.id}


# [claude] PCT-GC-11
@pytest.mark.xfail(strict=False, reason="BUG-1447: A component's tasks and notes have no sort order")
def test_pct_gc_11__rows_come_by_name_case_insensitive_whatever_their_ids(db, w1, pc1, mk_task, mk_note):
    """PCT-GC-11 — rows come by name, case-insensitive, whatever their ids.
    Rules: `get_by_component` R4 [BUG-1447]"""
    z = mk_task(name="Zulu")
    a = mk_task(name="apple")
    b = mk_note(name="Banana")
    seqscan(db)

    result = dao.get_by_component(db, project_component_id=pc1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [a.id, b.id, z.id]


# [claude] PCT-GC-12
@pytest.mark.xfail(strict=False, reason="BUG-1447: A component's tasks and notes have no sort order")
def test_pct_gc_12__names_that_differ_only_in_case_tie_and_the_lowest_id_comes_first(db, w1, pc1, mk_task):
    """PCT-GC-12 — names that differ only in case tie, and the lowest id comes first.
    Rules: `get_by_component` R4 [BUG-1447]"""
    a = mk_task(name="roof")
    b = mk_task(name="Roof")
    c = mk_task(name="wall")
    d = mk_task(name="Wall")
    seqscan(db)
    bump(db, a)

    result = dao.get_by_component(db, project_component_id=pc1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 4
    # Then 2
    assert ids(result) == [a.id, b.id, c.id, d.id]


# [claude] PCT-GC-13
@pytest.mark.xfail(strict=True, reason="BUG-1447: A component's tasks and notes have no sort order")
def test_pct_gc_13__the_query_orders_by_name_then_id_ascending(db, w1, pc1, mk_task):
    """PCT-GC-13 — the query orders by name, then id, ascending.
    Rules: `get_by_component` R4 [BUG-1447]"""
    t = mk_task(name="Fix")

    with StatementRecorder(db) as recorder:
        result = dao.get_by_component(db, project_component_id=pc1.id, workspace_id=w1.id)
    sql = recorder.sql()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [t.id]
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


# [claude] PCT-GC-14
def test_pct_gc_14__with_the_defaults_104_rows_give_100(db, w1, pc1, mk_many):
    """PCT-GC-14 — with the defaults 104 rows give 100.
    Rules: `get_by_component` R5"""
    mk_many(104)

    result = dao.get_by_component(db, project_component_id=pc1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100


# [claude] PCT-GC-15
def test_pct_gc_15__limit_1000_gives_all_104(db, w1, pc1, mk_many):
    """PCT-GC-15 — limit=1000 gives all 104.
    Rules: `get_by_component` R5"""
    rows = mk_many(104)
    all_ids = {row.id for row in rows}

    result = dao.get_by_component(db, project_component_id=pc1.id, workspace_id=w1.id, limit=1000)

    # Then 1
    assert len(result) == 104
    # Then 2
    assert set(ids(result)) == all_ids


# [claude] PCT-GC-16
def test_pct_gc_16__limit_0_returns_an_empty_list(db, w1, pc1, mk_task):
    """PCT-GC-16 — limit=0 returns an empty list.
    Rules: `get_by_component` R5"""
    mk_task(name="Fix")
    mk_task(name="Paint")

    result = dao.get_by_component(db, project_component_id=pc1.id, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [claude] PCT-GC-17
def test_pct_gc_17__limit_1_returns_one_row(db, w1, pc1, mk_task):
    """PCT-GC-17 — limit=1 returns one row.
    Rules: `get_by_component` R5"""
    mk_task(name="Fix")
    mk_task(name="Paint")

    result = dao.get_by_component(db, project_component_id=pc1.id, workspace_id=w1.id, limit=1)

    # Then 1
    assert len(result) == 1


# [claude] PCT-GC-18
def test_pct_gc_18__skip_past_the_end_returns_an_empty_list(db, w1, pc1, mk_task):
    """PCT-GC-18 — skip past the end returns an empty list.
    Rules: `get_by_component` R5"""
    mk_task(name="Fix")
    mk_task(name="Paint")

    result = dao.get_by_component(db, project_component_id=pc1.id, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [claude] PCT-GC-19
def test_pct_gc_19__a_negative_limit_raises_dataerror(db, w1, pc1, mk_task):
    """PCT-GC-19 — a negative limit raises DataError.
    Rules: `get_by_component` R5, Errors"""
    mk_task(name="Fix")
    before = stored_count(db)

    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_component(db, project_component_id=pc1.id, workspace_id=w1.id, limit=-1)

    # Then 1
    assert exc.value.orig.pgcode == "2201W"
    # Then 2
    assert stored_count(db) == before


# [claude] PCT-GC-20
def test_pct_gc_20__a_negative_skip_raises_dataerror(db, w1, pc1, mk_task):
    """PCT-GC-20 — a negative skip raises DataError.
    Rules: `get_by_component` R5, Errors"""
    mk_task(name="Fix")
    before = stored_count(db)

    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_component(db, project_component_id=pc1.id, workspace_id=w1.id, skip=-1)

    # Then 1
    assert exc.value.orig.pgcode == "2201X"
    # Then 2
    assert stored_count(db) == before


# [claude] PCT-GC-21
def test_pct_gc_21__the_rows_of_a_component_of_a_soft_deleted_project_are_returned(db, w1, pcd, mk_task):
    """PCT-GC-21 — the rows of a component of a soft-deleted project are returned.
    Rules: `get_by_component` R6"""
    t = mk_task(name="Fix", project_component_id=pcd.id)

    result = dao.get_by_component(db, project_component_id=pcd.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [t.id]


# [claude] PCT-GC-22
def test_pct_gc_22__writes_nothing_a_pending_row_stays_pending(db, w1, pc1, pc2, mk_task):
    """PCT-GC-22 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed.
    Rules: `get_by_component` Side effects"""
    a = mk_task(name="Fix")
    b = mk_task(name="Paint", project_component_id=pc2.id)
    b.name = "Edited"
    p = ProjectComponentTask(workspace_id=w1.id, project_component_id=pc1.id, name="Pending", description="Do it")
    db.add(p)
    before = stored_count(db)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_component(db, project_component_id=pc1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert b in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert recorder.written() == []
    # Then 7
    assert "FOR UPDATE" not in recorder.sql().upper()
    # Then 8
    assert stored_count(db) == before


# [claude] PCT-GC-23
@pytest.mark.xfail(strict=False, reason="BUG-1447: A component's tasks and notes have no sort order")
def test_pct_gc_23__names_that_differ_only_in_case_tie_whichever_case_sorts_first_byte_wise(db, w1, pc1, mk_task):
    """PCT-GC-23 — names that differ only in case tie, whichever case sorts first byte-wise.
    Rules: `get_by_component` R4 [BUG-1447]"""
    b = mk_task(name="Roof")
    a = mk_task(name="roof")
    c = mk_task(name="Banana")
    d = mk_task(name="apple")

    result = dao.get_by_component(db, project_component_id=pc1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [d.id, c.id, b.id, a.id]


# --------------------------------------------------------------------------- #
# DAOProjectComponentTask.get_incomplete_tasks
# --------------------------------------------------------------------------- #


# [claude] PCT-GI-01
def test_pct_gi_01__with_the_defaults_the_component_s_open_tasks_only(db, w1, pc1, mk_task, mk_note):
    """PCT-GI-01 — with the defaults: the component's open tasks only.
    Rules: `get_incomplete_tasks` R1, R2, R3, Returns"""
    t = mk_task(name="Fix")
    mk_task(name="Paint", is_completed=True)
    mk_note(name="Remark")

    result = dao.get_incomplete_tasks(db, project_component_id=pc1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [t.id]
    # Then 3
    assert isinstance(result[0], ProjectComponentTask)


# [claude] PCT-GI-02
def test_pct_gi_02__is_note_true_returns_the_open_notes_only(db, w1, pc1, mk_task, mk_note):
    """PCT-GI-02 — is_note=True returns the open notes only.
    Rules: `get_incomplete_tasks` R2, R3"""
    mk_task(name="Fix")
    n = mk_note(name="Remark")
    mk_note(name="Old remark", is_completed=True)

    result = dao.get_incomplete_tasks(db, project_component_id=pc1.id, workspace_id=w1.id, is_note=True)

    # Then 1
    assert ids(result) == [n.id]


# [claude] PCT-GI-03
def test_pct_gi_03__is_note_none_returns_an_empty_list(db, w1, pc1, mk_task, mk_note):
    """PCT-GI-03 — is_note=None returns an empty list.
    Rules: `get_incomplete_tasks` R2"""
    mk_task(name="Fix")
    mk_note(name="Remark")

    result = dao.get_incomplete_tasks(db, project_component_id=pc1.id, workspace_id=w1.id, is_note=None)

    # Then 1
    assert result == []


# [claude] PCT-GI-04
def test_pct_gi_04__an_open_task_of_another_component_is_not_returned(db, w1, pc1, pc2, mk_task):
    """PCT-GI-04 — an open task of another component is not returned.
    Rules: `get_incomplete_tasks` R1"""
    mk_task(name="Aaa", project_component_id=pc2.id)
    t = mk_task(name="Fix")

    result = dao.get_incomplete_tasks(db, project_component_id=pc1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [t.id]


# [claude] PCT-GI-05
def test_pct_gi_05__a_w2_row_on_a_w1_component_is_not_returned_for_w1(db, w1, w2, pc1, mk_task):
    """PCT-GI-05 — a W2 row on a W1 component is not returned for W1.
    Rules: `get_incomplete_tasks` R1"""
    t = mk_task(name="Fix")
    mk_task(name="Aaa", workspace_id=w2.id)

    result = dao.get_incomplete_tasks(db, project_component_id=pc1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [t.id]


# [claude] PCT-GI-06
def test_pct_gi_06__an_unknown_component_id_returns_an_empty_list(db, w1, mk_task):
    """PCT-GI-06 — an unknown component id returns an empty list.
    Rules: `get_incomplete_tasks` R1"""
    mk_task(name="Fix")

    result = dao.get_incomplete_tasks(db, project_component_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PCT-GI-07
def test_pct_gi_07__the_completed_filter_comes_before_the_page(db, w1, pc1, mk_task):
    """PCT-GI-07 — the completed filter comes before the page: a completed row takes no place.
    Rules: `get_incomplete_tasks` R3, R5"""
    mk_task(name="Aaa", is_completed=True)
    a = mk_task(name="Beta")
    b = mk_task(name="Gamma")

    result = dao.get_incomplete_tasks(db, project_component_id=pc1.id, workspace_id=w1.id, skip=1, limit=10)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id in {a.id, b.id}


# [claude] PCT-GI-08
@pytest.mark.xfail(strict=False, reason="BUG-1447: A component's tasks and notes have no sort order")
def test_pct_gi_08__open_tasks_come_by_name_case_insensitive_whatever_their_ids(db, w1, pc1, mk_task):
    """PCT-GI-08 — open tasks come by name, case-insensitive, whatever their ids.
    Rules: `get_incomplete_tasks` R4 [BUG-1447]"""
    z = mk_task(name="Zulu")
    a = mk_task(name="apple")
    b = mk_task(name="Banana")
    seqscan(db)

    result = dao.get_incomplete_tasks(db, project_component_id=pc1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [a.id, b.id, z.id]


# [claude] PCT-GI-09
@pytest.mark.xfail(strict=True, reason="BUG-1447: A component's tasks and notes have no sort order")
def test_pct_gi_09__the_query_orders_by_name_then_id_ascending(db, w1, pc1, mk_task):
    """PCT-GI-09 — the query orders by name, then id, ascending.
    Rules: `get_incomplete_tasks` R4 [BUG-1447]"""
    t = mk_task(name="Fix")

    with StatementRecorder(db) as recorder:
        result = dao.get_incomplete_tasks(db, project_component_id=pc1.id, workspace_id=w1.id)
    sql = recorder.sql()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [t.id]
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


# [claude] PCT-GI-10
def test_pct_gi_10__with_the_defaults_104_open_tasks_give_100(db, w1, pc1, mk_many):
    """PCT-GI-10 — with the defaults 104 open tasks give 100.
    Rules: `get_incomplete_tasks` R5"""
    mk_many(104)

    result = dao.get_incomplete_tasks(db, project_component_id=pc1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100


# [claude] PCT-GI-11
def test_pct_gi_11__limit_1000_gives_all_104(db, w1, pc1, mk_many):
    """PCT-GI-11 — limit=1000 gives all 104.
    Rules: `get_incomplete_tasks` R5"""
    rows = mk_many(104)
    all_ids = {row.id for row in rows}

    result = dao.get_incomplete_tasks(db, project_component_id=pc1.id, workspace_id=w1.id, limit=1000)

    # Then 1
    assert len(result) == 104
    # Then 2
    assert set(ids(result)) == all_ids


# [claude] PCT-GI-12
def test_pct_gi_12__limit_0_returns_an_empty_list(db, w1, pc1, mk_task):
    """PCT-GI-12 — limit=0 returns an empty list.
    Rules: `get_incomplete_tasks` R5"""
    mk_task(name="Fix")

    result = dao.get_incomplete_tasks(db, project_component_id=pc1.id, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [claude] PCT-GI-13
def test_pct_gi_13__a_negative_limit_raises_dataerror(db, w1, pc1, mk_task):
    """PCT-GI-13 — a negative limit raises DataError.
    Rules: `get_incomplete_tasks` R5, Errors"""
    mk_task(name="Fix")
    before = stored_count(db)

    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_incomplete_tasks(db, project_component_id=pc1.id, workspace_id=w1.id, limit=-1)

    # Then 1
    assert exc.value.orig.pgcode == "2201W"
    # Then 2
    assert stored_count(db) == before


# [claude] PCT-GI-14
def test_pct_gi_14__a_negative_skip_raises_dataerror(db, w1, pc1, mk_task):
    """PCT-GI-14 — a negative skip raises DataError.
    Rules: `get_incomplete_tasks` R5, Errors"""
    mk_task(name="Fix")
    before = stored_count(db)

    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_incomplete_tasks(db, project_component_id=pc1.id, workspace_id=w1.id, skip=-1)

    # Then 1
    assert exc.value.orig.pgcode == "2201X"
    # Then 2
    assert stored_count(db) == before


# [claude] PCT-GI-15
def test_pct_gi_15__the_open_tasks_of_a_component_of_a_soft_deleted_project_are_returned(db, w1, pcd, mk_task):
    """PCT-GI-15 — the open tasks of a component of a soft-deleted project are returned.
    Rules: `get_incomplete_tasks` R6"""
    t = mk_task(name="Fix", project_component_id=pcd.id)

    result = dao.get_incomplete_tasks(db, project_component_id=pcd.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [t.id]


# [claude] PCT-GI-16
def test_pct_gi_16__writes_nothing_a_pending_row_stays_pending(db, w1, pc1, pc2, mk_task):
    """PCT-GI-16 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed.
    Rules: `get_incomplete_tasks` Side effects"""
    a = mk_task(name="Fix")
    b = mk_task(name="Paint", project_component_id=pc2.id)
    b.name = "Edited"
    p = ProjectComponentTask(workspace_id=w1.id, project_component_id=pc1.id, name="Pending", description="Do it")
    db.add(p)
    before = stored_count(db)

    with StatementRecorder(db) as recorder:
        result = dao.get_incomplete_tasks(db, project_component_id=pc1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert b in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert recorder.written() == []
    # Then 7
    assert "FOR UPDATE" not in recorder.sql().upper()
    # Then 8
    assert stored_count(db) == before


# [claude] PCT-GI-17
@pytest.mark.xfail(strict=False, reason="BUG-1447: A component's tasks and notes have no sort order")
def test_pct_gi_17__names_that_differ_only_in_case_tie_whichever_case_sorts_first_byte_wise(db, w1, pc1, mk_task):
    """PCT-GI-17 — names that differ only in case tie, whichever case sorts first byte-wise.
    Rules: `get_incomplete_tasks` R4 [BUG-1447]"""
    b = mk_task(name="Roof")
    a = mk_task(name="roof")
    c = mk_task(name="Banana")
    d = mk_task(name="apple")

    result = dao.get_incomplete_tasks(db, project_component_id=pc1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [d.id, c.id, b.id, a.id]


# [claude] PCT-GI-18
def test_pct_gi_18__asked_for_w2_only_the_w2_row_is_returned_though_the_w1_row_is_earlier(db, w2, pc1, mk_task):
    """PCT-GI-18 — asked for W2, only the W2 row is returned, though the W1 row is earlier.
    Rules: `get_incomplete_tasks` R1"""
    mk_task(name="Alpha")
    z = mk_task(name="Zed", workspace_id=w2.id)

    result = dao.get_incomplete_tasks(db, project_component_id=pc1.id, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [z.id]
