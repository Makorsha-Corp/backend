"""Unit tests for app/dao/project.py.

Implements tests/unit/dao/project.cases.md, one test per case, in card order.
Real Postgres session (`db` fixture). Nothing is mocked and no clock is
patched (Conventions, Externals: None).

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`)
import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import DataError

from app.dao.project import project_dao
from app.models.factory import Factory
from app.models.project import Project
from tests.unit.factories import make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton project_dao"
dao = project_dao

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999


# --------------------------------------------------------------------------- #
# Conventions -> the rows that exist in every test
# --------------------------------------------------------------------------- #

def _add(db, row):
    db.add(row)
    db.flush()
    return row


# Convention "W1, W2 = two workspaces rows"; each standing row depends on the one
# listed before it, so the ids rise in the order the Conventions list them.
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


# Convention "F1 = Factory(workspace_id=W1.id, name="Factory One", abbreviation="F1")"
@pytest.fixture
def f1(db, w1, w2):
    return _add(db, Factory(workspace_id=w1.id, name="Factory One", abbreviation="F1"))


# Convention "F2 = the same, but name "Factory Two", abbreviation "F2""
@pytest.fixture
def f2(db, w1, f1):
    return _add(db, Factory(workspace_id=w1.id, name="Factory Two", abbreviation="F2"))


# Convention "FI = the same, but name "Idle Plant", abbreviation "IP", is_active False"
@pytest.fixture
def fi(db, w1, f2):
    return _add(db, Factory(workspace_id=w1.id, name="Idle Plant", abbreviation="IP", is_active=False))


# Convention "FD = the same, but name "Old Plant", abbreviation "OP", is_deleted True (is_active stays True)"
@pytest.fixture
def fd(db, w1, fi):
    return _add(db, Factory(workspace_id=w1.id, name="Old Plant", abbreviation="OP", is_deleted=True))


# Convention "F9 = the same, but workspace_id W2.id, name "Factory Nine", abbreviation "F9""
@pytest.fixture
def f9(db, w2, fd):
    return _add(db, Factory(workspace_id=w2.id, name="Factory Nine", abbreviation="F9"))


# Convention "These rows exist in every test and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2, f1, f2, fi, fd, f9):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builders (fixtures; each flushes before it returns)
# --------------------------------------------------------------------------- #

# Convention "project": status left to its default PLANNING; "deleted" = is_deleted True, is_active False
@pytest.fixture
def mk_project(db, w1, f1):
    """mk_project(name=..., **columns) -> Project. Keywords only."""
    def _mk(*, name, **columns):
        fields = {"workspace_id": w1.id, "factory_id": f1.id, "name": name, "description": "Main"}
        fields.update(columns)
        return _add(db, Project(**fields))
    return _mk


# The "104 projects E1 ... E104, built with add_all and flushed" Given of GF-18, GF-19, GS-12, GS-13
@pytest.fixture
def mk_many(db, w1, f1):
    """mk_many(count) -> [E1, ... Ecount]; Ek = project, name f"Project {k:03d}"."""
    def _mk(count):
        rows = [Project(workspace_id=w1.id, factory_id=f1.id, name=f"Project {k:03d}", description="Main")
                for k in range(1, count + 1)]
        db.add_all(rows)
        db.flush()
        return rows
    return _mk


# Convention "set_status(X, s)"
def set_status(db, row, s):
    db.execute(text("UPDATE projects SET status = CAST(:s AS projectstatusenum) WHERE id = :i"), {"s": s, "i": row.id})
    db.expire_all()


# Convention "bumpP(X)"
def bump(db, row):
    db.execute(text("UPDATE projects SET name = name WHERE id = :i"), {"i": row.id})
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


# Convention "unchanged(X)": every column of X, straight from the table
def snap(db, row):
    """Dict column -> database value of `row`, or None if it is gone."""
    table = type(row).__table__
    found = db.execute(select(table).where(table.c.id == sa_inspect(row).identity[0])).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "nothing written": the numbers of projects and factories rows stored (all workspaces)
def stored_count(db):
    return (db.scalar(select(func.count()).select_from(Project.__table__)),
            db.scalar(select(func.count()).select_from(Factory.__table__)))


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
        """`sql`: the one SELECT from projects; fails loudly unless there is exactly one."""
        [statement] = [s for s in self.statements
                       if s.lstrip().upper().startswith("SELECT") and "FROM projects" in s]
        return statement


# Convention "order_part": the text of `sql` after its first ORDER BY and before any LIMIT ("" when there is none)
def order_part_of(sql):
    return sql.split("ORDER BY", 1)[1].split("LIMIT", 1)[0] if "ORDER BY" in sql else ""


# --------------------------------------------------------------------------- #
# DAOProject.get_by_factory
# --------------------------------------------------------------------------- #


# [claude] PRJ-GF-01
def test_prj_gf_01__returns_a_list_of_the_factory_s_projects(db, w1, f1, mk_project):
    """PRJ-GF-01 — returns a list of the factory's projects
    Rules: `get_by_factory` R1, Returns"""
    a = mk_project(name="Alpha")
    b = mk_project(name="Beta")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert set(ids(result)) == {a.id, b.id}
    # Then 3
    assert isinstance(result[0], Project)


# [claude] PRJ-GF-02
def test_prj_gf_02__a_project_of_another_factory_is_not_returned(db, w1, f1, f2, mk_project):
    """PRJ-GF-02 — a project of another factory is not returned
    Rules: `get_by_factory` R1"""
    mk_project(name="Aaa", factory_id=f2.id)
    a = mk_project(name="Alpha")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] PRJ-GF-03
def test_prj_gf_03__a_w2_row_on_a_w1_factory_is_not_returned_for_w1(db, w1, w2, f1, mk_project):
    """PRJ-GF-03 — a W2 row on a W1 factory is not returned for W1
    Rules: `get_by_factory` R1"""
    a = mk_project(name="Alpha")
    mk_project(name="Aaa", workspace_id=w2.id)

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] PRJ-GF-04
def test_prj_gf_04__a_w2_row_on_a_w1_factory_is_returned_for_w2(db, w2, f1, mk_project):
    """PRJ-GF-04 — a W2 row on a W1 factory is returned for W2
    Rules: `get_by_factory` R1"""
    mk_project(name="Alpha")
    x = mk_project(name="Aaa", workspace_id=w2.id)

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [x.id]


# [claude] PRJ-GF-05
def test_prj_gf_05__an_unknown_factory_id_returns_an_empty_list(db, w1, mk_project):
    """PRJ-GF-05 — an unknown factory id returns an empty list
    Rules: `get_by_factory` R1"""
    mk_project(name="Alpha")

    result = dao.get_by_factory(db, factory_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PRJ-GF-06
def test_prj_gf_06__factory_id_0_returns_an_empty_list(db, w1, mk_project):
    """PRJ-GF-06 — factory id 0 returns an empty list
    Rules: `get_by_factory` R1"""
    mk_project(name="Alpha")

    result = dao.get_by_factory(db, factory_id=0, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PRJ-GF-07
@pytest.mark.xfail(strict=True, reason="BUG-1445: Project lists by factory or status return deleted projects")
def test_prj_gf_07__a_soft_deleted_project_is_not_returned(db, w1, f1, mk_project):
    """PRJ-GF-07 — a soft-deleted project is not returned
    Rules: `get_by_factory` R2 [BUG-1445]"""
    a = mk_project(name="Alpha")
    mk_project(name="Gone", is_deleted=True, is_active=False)

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert a.id in ids(result)
    # Then 2
    assert set(ids(result)) == {a.id}


# [claude] PRJ-GF-08
@pytest.mark.xfail(strict=True, reason="BUG-1445: Project lists by factory or status return deleted projects")
def test_prj_gf_08__a_soft_deleted_project_takes_no_place_in_the_page(db, w1, f1, mk_project):
    """PRJ-GF-08 — a soft-deleted project takes no place in the page
    Rules: `get_by_factory` R2 [BUG-1445]"""
    mk_project(name="Aaa", is_deleted=True, is_active=False)
    a = mk_project(name="Beta")
    b = mk_project(name="Gamma")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, skip=1, limit=10)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id in {a.id, b.id}


# [claude] PRJ-GF-09
def test_prj_gf_09__an_inactive_project_and_a_completed_one_are_returned(db, w1, f1, mk_project):
    """PRJ-GF-09 — an inactive project and a completed one are returned
    Rules: `get_by_factory` R2"""
    i = mk_project(name="Idle", is_active=False)
    c = mk_project(name="Done")
    set_status(db, c, "COMPLETED")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert set(ids(result)) == {i.id, c.id}


# [claude] PRJ-GF-10
@pytest.mark.xfail(strict=True, reason="BUG-1446: Projects of a deleted factory are still listed")
def test_prj_gf_10__a_soft_deleted_factory_gives_an_empty_list(db, w1, fd, mk_project):
    """PRJ-GF-10 — a soft-deleted factory gives an empty list
    Rules: `get_by_factory` R3 [BUG-1446]"""
    mk_project(name="Lost", factory_id=fd.id)

    result = dao.get_by_factory(db, factory_id=fd.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PRJ-GF-11
def test_prj_gf_11__an_inactive_but_live_factory_hides_nothing(db, w1, fi, mk_project):
    """PRJ-GF-11 — an inactive but live factory hides nothing
    Rules: `get_by_factory` R3a"""
    p = mk_project(name="Idle work", factory_id=fi.id)

    result = dao.get_by_factory(db, factory_id=fi.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [p.id]


# [claude] PRJ-GF-12
def test_prj_gf_12__the_call_changes_no_row_of_the_deleted_factory_or_its_project(db, w1, fd, mk_project):
    """PRJ-GF-12 — the call changes no row of the deleted factory or its project
    Rules: `get_by_factory` R3a"""
    p = mk_project(name="Lost", factory_id=fd.id)
    before_p = snap(db, p)
    before_fd = snap(db, fd)

    result = dao.get_by_factory(db, factory_id=fd.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert snap(db, p) == before_p
    # Then 3
    assert snap(db, fd) == before_fd


# [claude] PRJ-GF-13
def test_prj_gf_13__once_the_factory_is_live_again_its_project_is_returned(db, w1, fd, mk_project):
    """PRJ-GF-13 — once the factory is live again its project is returned
    Rules: `get_by_factory` R3a"""
    p = mk_project(name="Lost", factory_id=fd.id)
    fd.is_deleted = False
    db.flush()

    result = dao.get_by_factory(db, factory_id=fd.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [p.id]


# [claude] PRJ-GF-14
@pytest.mark.xfail(strict=False, reason="BUG-1444: Project lists by factory or status have no sort order")
def test_prj_gf_14__projects_come_by_name_case_insensitive_whatever_their_ids(db, w1, f1, mk_project):
    """PRJ-GF-14 — projects come by name, case-insensitive, whatever their ids
    Rules: `get_by_factory` R4 [BUG-1444]"""
    z = mk_project(name="Zulu")
    a = mk_project(name="apple")
    b = mk_project(name="Banana")
    seqscan(db)

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [a.id, b.id, z.id]


# [claude] PRJ-GF-15
@pytest.mark.xfail(strict=False, reason="BUG-1444: Project lists by factory or status have no sort order")
def test_prj_gf_15__names_that_differ_only_in_case_tie_and_the_lowest_id_comes_first(db, w1, f1, mk_project):
    """PRJ-GF-15 — names that differ only in case tie, and the lowest id comes first
    Rules: `get_by_factory` R4 [BUG-1444]"""
    a = mk_project(name="roof")
    b = mk_project(name="Roof")
    c = mk_project(name="wall")
    d = mk_project(name="Wall")
    seqscan(db)
    bump(db, a)

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 4
    # Then 2
    assert ids(result) == [a.id, b.id, c.id, d.id]


# [claude] PRJ-GF-16
@pytest.mark.xfail(strict=False, reason="BUG-1444: Project lists by factory or status have no sort order")
def test_prj_gf_16__the_order_comes_before_the_page_and_the_other_factory_s_row_takes_no_p(db, w1, f1, f2, mk_project):
    """PRJ-GF-16 — the order comes before the page, and the other factory's row takes no place
    Rules: `get_by_factory` R4 [BUG-1444]"""
    mk_project(name="Aaa", factory_id=f2.id)
    a = mk_project(name="Beta")
    mk_project(name="alpha")
    mk_project(name="Gamma")
    seqscan(db)

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert ids(result) == [a.id]


# [claude] PRJ-GF-17
@pytest.mark.xfail(strict=True, reason="BUG-1444: Project lists by factory or status have no sort order")
def test_prj_gf_17__the_query_orders_by_name_then_id_ascending(db, w1, f1, mk_project):
    """PRJ-GF-17 — the query orders by name, then id, ascending
    Rules: `get_by_factory` R4 [BUG-1444]"""
    a = mk_project(name="Alpha")

    with StatementRecorder(db) as rec:
        result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "ORDER BY" in rec.sql()
    # Then 3
    assert "name" in order_part_of(rec.sql())
    # Then 4
    assert ".id" in order_part_of(rec.sql())
    # Then 5
    assert order_part_of(rec.sql()).index("name") < order_part_of(rec.sql()).index(".id")
    # Then 6
    assert "DESC" not in order_part_of(rec.sql()).upper()


# [claude] PRJ-GF-18
def test_prj_gf_18__with_the_defaults_104_projects_give_100(db, w1, f1, mk_many):
    """PRJ-GF-18 — with the defaults 104 projects give 100
    Rules: `get_by_factory` R5"""
    mk_many(104)

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100


# [claude] PRJ-GF-19
def test_prj_gf_19__limit_1000_gives_all_104(db, w1, f1, mk_many):
    """PRJ-GF-19 — limit=1000 gives all 104
    Rules: `get_by_factory` R5"""
    rows = mk_many(104)
    all_ids = {row.id for row in rows}

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, limit=1000)

    # Then 1
    assert len(result) == 104
    # Then 2
    assert set(ids(result)) == all_ids


# [claude] PRJ-GF-20
def test_prj_gf_20__limit_0_returns_an_empty_list(db, w1, f1, mk_project):
    """PRJ-GF-20 — limit=0 returns an empty list
    Rules: `get_by_factory` R5"""
    mk_project(name="Alpha")
    mk_project(name="Beta")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [claude] PRJ-GF-21
def test_prj_gf_21__limit_1_returns_one_row(db, w1, f1, mk_project):
    """PRJ-GF-21 — limit=1 returns one row
    Rules: `get_by_factory` R5"""
    mk_project(name="Alpha")
    mk_project(name="Beta")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, limit=1)

    # Then 1
    assert len(result) == 1


# [claude] PRJ-GF-22
def test_prj_gf_22__skip_past_the_end_returns_an_empty_list(db, w1, f1, mk_project):
    """PRJ-GF-22 — skip past the end returns an empty list
    Rules: `get_by_factory` R5"""
    mk_project(name="Alpha")
    mk_project(name="Beta")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [claude] PRJ-GF-23
def test_prj_gf_23__a_negative_limit_raises_dataerror(db, w1, f1, mk_project):
    """PRJ-GF-23 — a negative limit raises DataError
    Rules: `get_by_factory` R5, Errors"""
    mk_project(name="Alpha")
    before_count = stored_count(db)

    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, limit=-1)

    # Then 1
    assert exc.value.orig.pgcode == "2201W"
    # Then 2
    assert stored_count(db) == before_count


# [claude] PRJ-GF-24
def test_prj_gf_24__a_negative_skip_raises_dataerror(db, w1, f1, mk_project):
    """PRJ-GF-24 — a negative skip raises DataError
    Rules: `get_by_factory` R5, Errors"""
    mk_project(name="Alpha")
    before_count = stored_count(db)

    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, skip=-1)

    # Then 1
    assert exc.value.orig.pgcode == "2201X"
    # Then 2
    assert stored_count(db) == before_count


# [claude] PRJ-GF-25
def test_prj_gf_25__writes_nothing_a_pending_project_stays_pending_an_unflushed_edit_stays(db, w1, f1, f2, mk_project):
    """PRJ-GF-25 — writes nothing: a pending project stays pending, an unflushed edit stays unflushed
    Rules: `get_by_factory` Side effects"""
    a = mk_project(name="Alpha")
    b = mk_project(name="Beta", factory_id=f2.id)
    b.name = "Edited"
    p = Project(workspace_id=w1.id, factory_id=f1.id, name="Pending", description="Main")
    db.add(p)
    before_count = stored_count(db)

    with StatementRecorder(db) as rec:
        result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

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
    assert rec.written() == []
    # Then 7
    assert "FOR UPDATE" not in rec.sql().upper()
    # Then 8
    assert stored_count(db) == before_count


# [claude] PRJ-GF-26
def test_prj_gf_26__the_factory_filter_comes_before_the_page_another_factory_s_row_takes_n(db, w1, f1, f2, mk_project):
    """PRJ-GF-26 — the factory filter comes before the page: another factory's row takes no place
    Rules: `get_by_factory` R1, R5"""
    mk_project(name="Aaa", factory_id=f2.id)
    a = mk_project(name="Beta")
    b = mk_project(name="Gamma")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, skip=1, limit=10)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id in {a.id, b.id}


# [claude] PRJ-GF-27
@pytest.mark.xfail(strict=False, reason="BUG-1444: Project lists by factory or status have no sort order")
def test_prj_gf_27__names_that_differ_only_in_case_tie_whichever_case_sorts_first_byte_wise(db, w1, f1, mk_project):
    """PRJ-GF-27 — names that differ only in case tie, whichever case sorts first byte-wise
    Rules: `get_by_factory` R4 [BUG-1444]"""
    b = mk_project(name="Roof")
    a = mk_project(name="roof")
    c = mk_project(name="Banana")
    d = mk_project(name="apple")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [d.id, c.id, b.id, a.id]


# --------------------------------------------------------------------------- #
# DAOProject.get_by_status
# --------------------------------------------------------------------------- #


# [claude] PRJ-GS-01
def test_prj_gs_01__returns_the_projects_in_that_status_of_every_factory(db, w1, f2, mk_project):
    """PRJ-GS-01 — returns the projects in that status, of every factory
    Rules: `get_by_status` R1, Returns"""
    a = mk_project(name="Alpha")
    b = mk_project(name="Beta", factory_id=f2.id)
    c = mk_project(name="Done")
    set_status(db, c, "COMPLETED")

    result = dao.get_by_status(db, status="PLANNING", workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert set(ids(result)) == {a.id, b.id}
    # Then 3
    assert isinstance(result[0], Project)


# [claude] PRJ-GS-02
def test_prj_gs_02__a_w2_row_on_a_w1_factory_is_not_returned_for_w1(db, w1, w2, mk_project):
    """PRJ-GS-02 — a W2 row on a W1 factory is not returned for W1
    Rules: `get_by_status` R1"""
    a = mk_project(name="Alpha")
    mk_project(name="Aaa", workspace_id=w2.id)

    result = dao.get_by_status(db, status="PLANNING", workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] PRJ-GS-03
def test_prj_gs_03__a_w2_row_on_a_w1_factory_is_returned_for_w2(db, w2, mk_project):
    """PRJ-GS-03 — a W2 row on a W1 factory is returned for W2
    Rules: `get_by_status` R1"""
    mk_project(name="Alpha")
    x = mk_project(name="Aaa", workspace_id=w2.id)

    result = dao.get_by_status(db, status="PLANNING", workspace_id=w2.id)

    # Then 1
    assert ids(result) == [x.id]


# [claude] PRJ-GS-04
def test_prj_gs_04__a_lowercase_status_raises_dataerror_22p02(db, w1, mk_project):
    """PRJ-GS-04 — a lowercase status raises DataError 22P02
    Rules: `get_by_status` Inputs, Errors"""
    mk_project(name="Alpha")
    before_count = stored_count(db)

    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_status(db, status="planning", workspace_id=w1.id)

    # Then 1
    assert exc.value.orig.pgcode == "22P02"
    # Then 2
    assert stored_count(db) == before_count


# [claude] PRJ-GS-05
@pytest.mark.xfail(strict=True, reason="BUG-1445: Project lists by factory or status return deleted projects")
def test_prj_gs_05__a_soft_deleted_project_is_not_returned(db, w1, mk_project):
    """PRJ-GS-05 — a soft-deleted project is not returned
    Rules: `get_by_status` R2 [BUG-1445]"""
    a = mk_project(name="Alpha")
    mk_project(name="Gone", is_deleted=True, is_active=False)

    result = dao.get_by_status(db, status="PLANNING", workspace_id=w1.id)

    # Then 1
    assert a.id in ids(result)
    # Then 2
    assert set(ids(result)) == {a.id}


# [claude] PRJ-GS-06
def test_prj_gs_06__an_inactive_project_is_returned(db, w1, mk_project):
    """PRJ-GS-06 — an inactive project is returned
    Rules: `get_by_status` R2"""
    i = mk_project(name="Idle", is_active=False)

    result = dao.get_by_status(db, status="PLANNING", workspace_id=w1.id)

    # Then 1
    assert ids(result) == [i.id]


# [claude] PRJ-GS-07
@pytest.mark.xfail(strict=True, reason="BUG-1446: Projects of a deleted factory are still listed")
def test_prj_gs_07__a_project_of_a_soft_deleted_factory_is_not_returned_the_others_are(db, w1, fd, mk_project):
    """PRJ-GS-07 — a project of a soft-deleted factory is not returned; the others are
    Rules: `get_by_status` R3 [BUG-1446]"""
    a = mk_project(name="Alpha")
    mk_project(name="Lost", factory_id=fd.id)

    result = dao.get_by_status(db, status="PLANNING", workspace_id=w1.id)

    # Then 1
    assert a.id in ids(result)
    # Then 2
    assert set(ids(result)) == {a.id}


# [claude] PRJ-GS-08
def test_prj_gs_08__a_project_of_an_inactive_but_live_factory_is_returned(db, w1, fi, mk_project):
    """PRJ-GS-08 — a project of an inactive but live factory is returned
    Rules: `get_by_status` R3a"""
    p = mk_project(name="Idle work", factory_id=fi.id)

    result = dao.get_by_status(db, status="PLANNING", workspace_id=w1.id)

    # Then 1
    assert ids(result) == [p.id]


# [claude] PRJ-GS-09
def test_prj_gs_09__the_call_changes_no_row_of_the_deleted_factory_or_its_project(db, w1, fd, mk_project):
    """PRJ-GS-09 — the call changes no row of the deleted factory or its project
    Rules: `get_by_status` R3a"""
    p = mk_project(name="Lost", factory_id=fd.id)
    before_p = snap(db, p)
    before_fd = snap(db, fd)

    result = dao.get_by_status(db, status="PLANNING", workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert snap(db, p) == before_p
    # Then 3
    assert snap(db, fd) == before_fd


# [claude] PRJ-GS-10
@pytest.mark.xfail(strict=False, reason="BUG-1444: Project lists by factory or status have no sort order")
def test_prj_gs_10__projects_come_by_name_case_insensitive_whatever_their_ids(db, w1, f2, mk_project):
    """PRJ-GS-10 — projects come by name, case-insensitive, whatever their ids
    Rules: `get_by_status` R4 [BUG-1444]"""
    z = mk_project(name="Zulu")
    a = mk_project(name="apple", factory_id=f2.id)
    b = mk_project(name="Banana")
    seqscan(db)

    result = dao.get_by_status(db, status="PLANNING", workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [a.id, b.id, z.id]


# [claude] PRJ-GS-11
@pytest.mark.xfail(strict=True, reason="BUG-1444: Project lists by factory or status have no sort order")
def test_prj_gs_11__the_query_orders_by_name_then_id_ascending(db, w1, mk_project):
    """PRJ-GS-11 — the query orders by name, then id, ascending
    Rules: `get_by_status` R4 [BUG-1444]"""
    a = mk_project(name="Alpha")

    with StatementRecorder(db) as rec:
        result = dao.get_by_status(db, status="PLANNING", workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "ORDER BY" in rec.sql()
    # Then 3
    assert "name" in order_part_of(rec.sql())
    # Then 4
    assert ".id" in order_part_of(rec.sql())
    # Then 5
    assert order_part_of(rec.sql()).index("name") < order_part_of(rec.sql()).index(".id")
    # Then 6
    assert "DESC" not in order_part_of(rec.sql()).upper()


# [claude] PRJ-GS-12
def test_prj_gs_12__with_the_defaults_104_projects_give_100(db, w1, mk_many):
    """PRJ-GS-12 — with the defaults 104 projects give 100
    Rules: `get_by_status` R5"""
    mk_many(104)

    result = dao.get_by_status(db, status="PLANNING", workspace_id=w1.id)

    # Then 1
    assert len(result) == 100


# [claude] PRJ-GS-13
def test_prj_gs_13__limit_1000_gives_all_104(db, w1, mk_many):
    """PRJ-GS-13 — limit=1000 gives all 104
    Rules: `get_by_status` R5"""
    rows = mk_many(104)
    all_ids = {row.id for row in rows}

    result = dao.get_by_status(db, status="PLANNING", workspace_id=w1.id, limit=1000)

    # Then 1
    assert len(result) == 104
    # Then 2
    assert set(ids(result)) == all_ids


# [claude] PRJ-GS-14
def test_prj_gs_14__limit_0_returns_an_empty_list(db, w1, mk_project):
    """PRJ-GS-14 — limit=0 returns an empty list
    Rules: `get_by_status` R5"""
    mk_project(name="Alpha")

    result = dao.get_by_status(db, status="PLANNING", workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [claude] PRJ-GS-15
def test_prj_gs_15__skip_past_the_end_returns_an_empty_list(db, w1, mk_project):
    """PRJ-GS-15 — skip past the end returns an empty list
    Rules: `get_by_status` R5"""
    mk_project(name="Alpha")

    result = dao.get_by_status(db, status="PLANNING", workspace_id=w1.id, skip=1)

    # Then 1
    assert result == []


# [claude] PRJ-GS-16
def test_prj_gs_16__a_negative_limit_raises_dataerror(db, w1, mk_project):
    """PRJ-GS-16 — a negative limit raises DataError
    Rules: `get_by_status` R5, Errors"""
    mk_project(name="Alpha")
    before_count = stored_count(db)

    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_status(db, status="PLANNING", workspace_id=w1.id, limit=-1)

    # Then 1
    assert exc.value.orig.pgcode == "2201W"
    # Then 2
    assert stored_count(db) == before_count


# [claude] PRJ-GS-17
def test_prj_gs_17__a_negative_skip_raises_dataerror(db, w1, mk_project):
    """PRJ-GS-17 — a negative skip raises DataError
    Rules: `get_by_status` R5, Errors"""
    mk_project(name="Alpha")
    before_count = stored_count(db)

    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_status(db, status="PLANNING", workspace_id=w1.id, skip=-1)

    # Then 1
    assert exc.value.orig.pgcode == "2201X"
    # Then 2
    assert stored_count(db) == before_count


# [claude] PRJ-GS-18
def test_prj_gs_18__the_status_filter_comes_before_the_page_another_status_takes_no_place(db, w1, mk_project):
    """PRJ-GS-18 — the status filter comes before the page: another status takes no place
    Rules: `get_by_status` R1, R5"""
    x = mk_project(name="Aaa")
    set_status(db, x, "COMPLETED")
    a = mk_project(name="Beta")
    b = mk_project(name="Gamma")

    result = dao.get_by_status(db, status="PLANNING", workspace_id=w1.id, skip=1, limit=10)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id in {a.id, b.id}


# [claude] PRJ-GS-19
def test_prj_gs_19__writes_nothing_a_pending_project_stays_pending_an_unflushed_edit_stays(db, w1, w2, f1, mk_project):
    """PRJ-GS-19 — writes nothing: a pending project stays pending, an unflushed edit stays unflushed
    Rules: `get_by_status` Side effects"""
    a = mk_project(name="Alpha")
    b = mk_project(name="Beta", workspace_id=w2.id)
    b.name = "Edited"
    p = Project(workspace_id=w1.id, factory_id=f1.id, name="Pending", description="Main")
    db.add(p)
    before_count = stored_count(db)

    with StatementRecorder(db) as rec:
        result = dao.get_by_status(db, status="PLANNING", workspace_id=w1.id)

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
    assert rec.written() == []
    # Then 7
    assert "FOR UPDATE" not in rec.sql().upper()
    # Then 8
    assert stored_count(db) == before_count


# [claude] PRJ-GS-20
@pytest.mark.xfail(strict=False, reason="BUG-1444: Project lists by factory or status have no sort order")
def test_prj_gs_20__names_that_differ_only_in_case_tie_whichever_case_sorts_first_byte_wise(db, w1, mk_project):
    """PRJ-GS-20 — names that differ only in case tie, whichever case sorts first byte-wise
    Rules: `get_by_status` R4 [BUG-1444]"""
    b = mk_project(name="Roof")
    a = mk_project(name="roof")
    c = mk_project(name="Banana")
    d = mk_project(name="apple")

    result = dao.get_by_status(db, status="PLANNING", workspace_id=w1.id)

    # Then 1
    assert ids(result) == [d.id, c.id, b.id, a.id]


# [claude] PRJ-GS-21
@pytest.mark.xfail(strict=False, reason="BUG-1445: Project lists by factory or status return deleted projects; "
                                        "BUG-1444: Project lists by factory or status have no sort order")
def test_prj_gs_21__a_soft_deleted_project_takes_no_place_in_the_page_after_the_name_order(db, w1, mk_project):
    """PRJ-GS-21 — a soft-deleted project takes no place in the page, after the name order
    Rules: `get_by_status` R2 [BUG-1445], R4 [BUG-1444]"""
    mk_project(name="Aaa", is_deleted=True, is_active=False)
    mk_project(name="Bbb")
    b = mk_project(name="Ccc")

    result = dao.get_by_status(db, status="PLANNING", workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [b.id]
