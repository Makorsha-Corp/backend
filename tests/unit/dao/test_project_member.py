"""Unit tests for app/dao/project_member.py.

Implements tests/unit/dao/project_member.cases.md, one test per case, in
card order. Real Postgres session (`db` fixture).
Nothing is mocked and no clock is patched (Conventions, Externals: None).

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: DTZ001  (naive datetimes)
from datetime import datetime, timedelta

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect

from app.dao.project_member import project_member_dao
from app.models.factory import Factory
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.workspace_member import WorkspaceMember
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton project_member_dao" (a module-level name, not a fixture)
dao = project_member_dao

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999

# Convention "T9, T10, T11, T12"
T9 = datetime(2026, 3, 4, 9, 0, 0)
T10 = datetime(2026, 3, 4, 10, 0, 0)
T11 = datetime(2026, 3, 4, 11, 0, 0)
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


@pytest.fixture
def u2(db, pjd):
    return make_profile(db)


@pytest.fixture
def u3(db, u2):
    return make_profile(db)


# Convention "These rows exist in every test and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2, u1, f1, pj1, pj2, pjd, u2, u3):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builders (fixtures; each flushes before it returns)
# --------------------------------------------------------------------------- #

# Convention "member": the columns the Conventions say are not passed stay out of the constructor
@pytest.fixture
def mk_member(db, w1, u1, pj1):
    """mk_member(assigned_at=..., **columns) -> ProjectMember. Keywords only."""
    def _mk(*, assigned_at, **columns):
        fields = {"workspace_id": w1.id, "project_id": pj1.id, "user_id": u1.id, "assigned_at": assigned_at}
        fields.update(columns)
        return _add(db, ProjectMember(**fields))
    return _mk


# Convention "left U": the membership of someone removed from W1
@pytest.fixture
def mk_left(db, w1):
    """mk_left(user) -> WorkspaceMember."""
    def _mk(user):
        return _add(db, WorkspaceMember(workspace_id=w1.id, user_id=user.id, role="member", status="inactive"))
    return _mk


# The "built with add_all" Given lines
@pytest.fixture
def mk_many(db, w1, u1, pj1):
    """mk_many(count) -> `in_order`: the ids of the rows, in the card's order."""
    def _mk(count):
        people = [make_profile(db) for _ in range(count)]
        rows = [ProjectMember(workspace_id=w1.id, project_id=pj1.id, user_id=people[k - 1].id, assigned_at=T10 + timedelta(minutes=k))
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


# Convention "nothing written": the number of project_members rows stored (all workspaces)
def stored_count(db):
    return db.execute(select(func.count()).select_from(ProjectMember.__table__)).scalar_one()


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
        """The one SELECT from project_members; fails loudly unless there is exactly one."""
        [statement] = [s for s in self.selects() if "project_members" in s]
        return statement


# Convention "order_part": the text of `sql` after its first ORDER BY ("" when there is none)
def order_part_of(sql):
    return sql.split("ORDER BY", 1)[1] if "ORDER BY" in sql else ""


# --------------------------------------------------------------------------- #
# ProjectMemberDAO.get_by_project
# --------------------------------------------------------------------------- #


# [claude] PMB-G-01
def test_pmb_g_01__returns_a_list_of_the_project_s_members(db, w1, pj1, u2, mk_member):
    """PMB-G-01 — returns a list of the project's members.
    Rules: `get_by_project` R1, Returns"""
    a = mk_member(assigned_at=T10)
    b = mk_member(assigned_at=T11, user_id=u2.id)

    result = dao.get_by_project(db, project_id=pj1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [a.id, b.id]
    # Then 3
    assert isinstance(result[0], ProjectMember)


# [claude] PMB-G-02
def test_pmb_g_02__a_member_of_another_project_of_the_same_workspace_is_not_returned_thou(db, w1, pj1, pj2, u2, mk_member):
    """PMB-G-02 — a member of another project of the same workspace is not returned, though it sorts first.
    Rules: `get_by_project` R1"""
    a = mk_member(assigned_at=T11, user_id=u2.id)
    mk_member(assigned_at=T10, project_id=pj2.id)

    result = dao.get_by_project(db, project_id=pj1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] PMB-G-03
def test_pmb_g_03__the_right_project_under_another_workspace_returns_an_empty_list(db, w2, pj1, mk_member):
    """PMB-G-03 — the right project under another workspace returns an empty list.
    Rules: `get_by_project` R1"""
    mk_member(assigned_at=T10)

    result = dao.get_by_project(db, project_id=pj1.id, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] PMB-G-04
def test_pmb_g_04__an_unknown_workspace_returns_an_empty_list(db, pj1, mk_member):
    """PMB-G-04 — an unknown workspace returns an empty list.
    Rules: `get_by_project` R1"""
    mk_member(assigned_at=T10)

    result = dao.get_by_project(db, project_id=pj1.id, workspace_id=MISSING)

    # Then 1
    assert result == []


# [claude] PMB-G-05
def test_pmb_g_05__an_unknown_project_id_returns_an_empty_list(db, w1, mk_member):
    """PMB-G-05 — an unknown project id returns an empty list.
    Rules: `get_by_project` R2"""
    mk_member(assigned_at=T10)

    result = dao.get_by_project(db, project_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PMB-G-06
def test_pmb_g_06__project_id_0_returns_an_empty_list(db, w1, mk_member):
    """PMB-G-06 — project id 0 returns an empty list.
    Rules: `get_by_project` R2"""
    mk_member(assigned_at=T10)

    result = dao.get_by_project(db, project_id=0, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PMB-G-07
def test_pmb_g_07__a_project_with_no_rows_returns_an_empty_list(db, w1, pj2, mk_member):
    """PMB-G-07 — a project with no rows returns an empty list.
    Rules: `get_by_project` R2"""
    mk_member(assigned_at=T10)

    result = dao.get_by_project(db, project_id=pj2.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PMB-G-08
def test_pmb_g_08__members_are_ordered_by_assigned_at_ascending_whatever_their_ids(db, w1, pj1, u2, u3, mk_member):
    """PMB-G-08 — members are ordered by assigned_at ascending, whatever their ids.
    Rules: `get_by_project` R3"""
    a = mk_member(assigned_at=T12, user_id=u3.id)
    b = mk_member(assigned_at=T11, user_id=u2.id)
    c = mk_member(assigned_at=T10)

    result = dao.get_by_project(db, project_id=pj1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [c.id, b.id, a.id]


# [claude] PMB-G-09
def test_pmb_g_09__one_microsecond_inside_one_day_decides_the_order_against_id(db, w1, pj1, u2, mk_member):
    """PMB-G-09 — one microsecond inside one day decides the order, against id.
    Rules: `get_by_project` R3"""
    a = mk_member(assigned_at=T10 + timedelta(microseconds=1))
    b = mk_member(assigned_at=T10, user_id=u2.id)

    result = dao.get_by_project(db, project_id=pj1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] PMB-G-10
def test_pmb_g_10__on_a_tie_both_members_are_returned_after_the_earlier_one(db, w1, pj1, u2, u3, mk_member):
    """PMB-G-10 — on a tie both members are returned, after the earlier one.
    Rules: `get_by_project` R4, R3"""
    a = mk_member(assigned_at=T11)
    b = mk_member(assigned_at=T11, user_id=u2.id)
    c = mk_member(assigned_at=T10, user_id=u3.id)
    a.assigned_by = u3.id
    db.flush()
    db.expire_all()

    result = dao.get_by_project(db, project_id=pj1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert result[0].id == c.id
    # Then 3
    assert {r.id for r in result[1:]} == {a.id, b.id}


# [claude] PMB-G-11
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1274: Project members with one `assigned_at` come back in no fixed order"
    " (non-strict: the order rests on physical row order, which can match by accident)",
)
def test_pmb_g_11__on_a_tie_the_lowest_id_comes_first_when_the_lower_id_was_updated(db, w1, pj1, u2, u3, mk_member):
    """PMB-G-11 — on a tie the lowest id comes first, when the lower id was updated.
    Rules: `get_by_project` R4 [BUG-1274]"""
    a = mk_member(assigned_at=T11)
    b = mk_member(assigned_at=T11, user_id=u2.id)
    seqscan(db)
    a.assigned_by = u3.id
    db.flush()
    db.expire_all()

    result = dao.get_by_project(db, project_id=pj1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert ids(result) == [a.id, b.id]


# [claude] PMB-G-12
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1274: Project members with one `assigned_at` come back in no fixed order"
    " (non-strict: the order rests on physical row order, which can match by accident)",
)
def test_pmb_g_12__on_a_tie_the_lowest_id_comes_first_when_the_user_would_sort_the_other(db, w1, u1, pj1, u2, u3, mk_member):
    """PMB-G-12 — on a tie the lowest id comes first, when the user would sort the other way.
    Rules: `get_by_project` R4 [BUG-1274]"""
    a = mk_member(assigned_at=T11, user_id=u2.id, assigned_by=u3.id)
    b = mk_member(assigned_at=T11, assigned_by=u1.id)
    db.expire_all()

    result = dao.get_by_project(db, project_id=pj1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert ids(result) == [a.id, b.id]


# [claude] PMB-G-13
@pytest.mark.xfail(strict=True, reason="BUG-1274: Project members with one `assigned_at` come back in no fixed order")
def test_pmb_g_13__the_query_orders_by_assigned_at_then_id_ascending(db, w1, pj1, mk_member):
    """PMB-G-13 — the query orders by assigned_at, then id ascending.
    Rules: `get_by_project` R4 [BUG-1274]"""
    a = mk_member(assigned_at=T10)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_project(db, project_id=pj1.id, workspace_id=w1.id)
    sql = recorder.sql()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "assigned_at" in order_part
    # Then 4
    assert ".id" in order_part
    # Then 5
    assert order_part.index("assigned_at") < order_part.index(".id")
    # Then 6
    assert "DESC" not in order_part.upper()


# [claude] PMB-G-14
def test_pmb_g_14__the_members_of_a_soft_deleted_project_are_returned(db, w1, pjd, mk_member):
    """PMB-G-14 — the members of a soft-deleted project are returned.
    Rules: `get_by_project` R5"""
    a = mk_member(assigned_at=T10, project_id=pjd.id)

    result = dao.get_by_project(db, project_id=pjd.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] PMB-G-15
def test_pmb_g_15__someone_who_left_the_workspace_is_returned(db, w1, pj1, u2, mk_member, mk_left):
    """PMB-G-15 — someone who left the workspace is returned.
    Rules: `get_by_project` R6"""
    mk_left(u2)
    a = mk_member(assigned_at=T10, user_id=u2.id)

    result = dao.get_by_project(db, project_id=pj1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] PMB-G-16
def test_pmb_g_16__there_is_no_cap_101_members_give_101_rows(db, w1, pj1, mk_many):
    """PMB-G-16 — there is no cap: 101 members give 101 rows.
    Rules: `get_by_project` R7"""
    in_order = mk_many(101)

    result = dao.get_by_project(db, project_id=pj1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert ids(result) == in_order


# [claude] PMB-G-17
def test_pmb_g_17__writes_nothing_an_earlier_pending_row_stays_pending_and_alone_in_the_s(db, w1, pj1, u2, mk_member):
    """PMB-G-17 — writes nothing: an earlier pending row stays pending and alone in the session.
    Rules: `get_by_project` Side effects"""
    a = mk_member(assigned_at=T10)
    p = ProjectMember(workspace_id=w1.id, project_id=pj1.id, user_id=u2.id, assigned_at=T9)
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
    assert "workspace_members" not in sql
    # Then 12
    assert stored_count(db) == before
    # Then 13
    db.expire_all()
    assert snap(db, a) == before_a


# [claude] PMB-G-18
def test_pmb_g_18__a_w2_member_on_a_w1_project_is_not_returned_for_w1(db, w1, w2, pj1, mk_member):
    """PMB-G-18 — a W2 member on a W1 project is not returned for W1.
    Rules: `get_by_project` R1"""
    mk_member(assigned_at=T10, workspace_id=w2.id)

    result = dao.get_by_project(db, project_id=pj1.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PMB-G-19
def test_pmb_g_19__writes_nothing_an_unflushed_edit_of_another_row_stays_unflushed_and_is(db, w1, pj1, pj2, u2, mk_member):
    """PMB-G-19 — writes nothing: an unflushed edit of another row stays unflushed and is not reloaded.
    Rules: `get_by_project` Side effects"""
    a = mk_member(assigned_at=T10)
    b = mk_member(assigned_at=T11, project_id=pj2.id)
    b.assigned_by = u2.id

    result = dao.get_by_project(db, project_id=pj1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert b.assigned_by == u2.id


# --------------------------------------------------------------------------- #
# ProjectMemberDAO.get_by_project_and_user
# --------------------------------------------------------------------------- #


# [claude] PMB-GU-01
def test_pmb_gu_01__returns_the_row_of_that_user_not_the_project_s_first_row(db, w1, pj1, u2, mk_member):
    """PMB-GU-01 — returns the row of that user, not the project's first row.
    Rules: `get_by_project_and_user` R1, Returns"""
    mk_member(assigned_at=T10)
    b = mk_member(assigned_at=T11, user_id=u2.id)

    result = dao.get_by_project_and_user(db, project_id=pj1.id, user_id=u2.id, workspace_id=w1.id)

    # Then 1
    assert result.id == b.id
    # Then 2
    assert isinstance(result, ProjectMember)


# [claude] PMB-GU-02
def test_pmb_gu_02__returns_the_row_on_that_project_not_the_user_s_first_row(db, w1, u1, pj2, mk_member):
    """PMB-GU-02 — returns the row on that project, not the user's first row.
    Rules: `get_by_project_and_user` R1"""
    mk_member(assigned_at=T10)
    b = mk_member(assigned_at=T10, project_id=pj2.id)

    result = dao.get_by_project_and_user(db, project_id=pj2.id, user_id=u1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == b.id


# [claude] PMB-GU-03
def test_pmb_gu_03__a_person_who_is_not_a_member_returns_none_and_nothing_is_created(db, w1, u1, pj1, pj2, u2, mk_member):
    """PMB-GU-03 — a person who is not a member returns None and nothing is created.
    Rules: `get_by_project_and_user` R2"""
    mk_member(assigned_at=T10, project_id=pj2.id)
    mk_member(assigned_at=T11, user_id=u2.id)
    before = stored_count(db)

    result = dao.get_by_project_and_user(db, project_id=pj1.id, user_id=u1.id, workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    assert stored_count(db) == before


# [claude] PMB-GU-04
def test_pmb_gu_04__an_unknown_project_returns_none(db, w1, u1, mk_member):
    """PMB-GU-04 — an unknown project returns None.
    Rules: `get_by_project_and_user` R2"""
    mk_member(assigned_at=T10)

    result = dao.get_by_project_and_user(db, project_id=MISSING, user_id=u1.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] PMB-GU-05
def test_pmb_gu_05__an_unknown_user_returns_none(db, w1, pj1, mk_member):
    """PMB-GU-05 — an unknown user returns None.
    Rules: `get_by_project_and_user` R2"""
    mk_member(assigned_at=T10)

    result = dao.get_by_project_and_user(db, project_id=pj1.id, user_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] PMB-GU-06
def test_pmb_gu_06__another_workspace_returns_none(db, w2, u1, pj1, mk_member):
    """PMB-GU-06 — another workspace returns None.
    Rules: `get_by_project_and_user` R3"""
    mk_member(assigned_at=T10)

    result = dao.get_by_project_and_user(db, project_id=pj1.id, user_id=u1.id, workspace_id=w2.id)

    # Then 1
    assert result is None


# [claude] PMB-GU-07
def test_pmb_gu_07__the_row_on_a_soft_deleted_project_is_returned(db, w1, u1, pjd, mk_member):
    """PMB-GU-07 — the row on a soft-deleted project is returned.
    Rules: `get_by_project_and_user` R4"""
    a = mk_member(assigned_at=T10, project_id=pjd.id)

    result = dao.get_by_project_and_user(db, project_id=pjd.id, user_id=u1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id


# [claude] PMB-GU-08
def test_pmb_gu_08__the_row_of_someone_who_left_the_workspace_is_returned(db, w1, pj1, u2, mk_member, mk_left):
    """PMB-GU-08 — the row of someone who left the workspace is returned.
    Rules: `get_by_project_and_user` R4"""
    mk_left(u2)
    a = mk_member(assigned_at=T10, user_id=u2.id)

    result = dao.get_by_project_and_user(db, project_id=pj1.id, user_id=u2.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id


# [claude] PMB-GU-09
def test_pmb_gu_09__writes_nothing_a_read_that_finds_its_row_leaves_the_session_as_it_was(db, w1, u1, pj1, u2, mk_member):
    """PMB-GU-09 — writes nothing: a read that finds its row leaves the session as it was.
    Rules: `get_by_project_and_user` Side effects"""
    a = mk_member(assigned_at=T10)
    p = ProjectMember(workspace_id=w1.id, project_id=pj1.id, user_id=u2.id, assigned_at=T9)
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_project_and_user(db, project_id=pj1.id, user_id=u1.id, workspace_id=w1.id)
    written = recorder.written()
    selects = recorder.selects()
    sql = recorder.sql()

    # Then 1
    assert result.id == a.id
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
    assert "workspace_members" not in sql
    # Then 12
    assert stored_count(db) == before
    # Then 13
    db.expire_all()
    assert snap(db, a) == before_a


# [claude] PMB-GU-10
def test_pmb_gu_10__a_w2_row_of_that_project_and_user_is_not_returned_for_w1(db, w1, w2, u1, pj1, mk_member):
    """PMB-GU-10 — a W2 row of that project and user is not returned for W1.
    Rules: `get_by_project_and_user` R3"""
    mk_member(assigned_at=T10, workspace_id=w2.id)

    result = dao.get_by_project_and_user(db, project_id=pj1.id, user_id=u1.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] PMB-GU-11
def test_pmb_gu_11__writes_nothing_an_unflushed_edit_of_another_row_stays_unflushed_and_is(db, w1, u1, pj1, u2, mk_member):
    """PMB-GU-11 — writes nothing: an unflushed edit of another row stays unflushed and is not reloaded.
    Rules: `get_by_project_and_user` Side effects"""
    a = mk_member(assigned_at=T10)
    b = mk_member(assigned_at=T11, user_id=u2.id)
    b.assigned_by = u2.id

    result = dao.get_by_project_and_user(db, project_id=pj1.id, user_id=u1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert b.assigned_by == u2.id
