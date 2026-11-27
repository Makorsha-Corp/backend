"""Unit tests for app/dao/workspace_member.py.

Implements tests/unit/dao/workspace_member.cases.md, one test per case, in card
order. Real Postgres session (`db` fixture). Nothing is mocked and no clock is
read (Conventions, Externals: None).

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`)
import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy.exc import IntegrityError

from app.dao.workspace_member import workspace_member_dao
from app.models.workspace_member import WorkspaceMember
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton workspace_member_dao"
dao = workspace_member_dao

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999

BUG_1400 = "BUG-1400: Member lists have no sort order"
BUG_1400_NON_STRICT = (
    "BUG-1400: Member lists have no sort order "
    "(non-strict: rows come back in physical order, which can match by accident)"
)


# --------------------------------------------------------------------------- #
# Conventions -> the rows that exist in every test
# --------------------------------------------------------------------------- #

# Convention "W1, W2 = two workspaces rows from make_workspace(db)"; each fixture
# depends on the one before, so ids rise in the order the Conventions list them.
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


# Convention "U1, U2, U3 = three profiles rows from make_profile(db)"
@pytest.fixture
def u1(db, w2):
    return make_profile(db)


@pytest.fixture
def u2(db, u1):
    return make_profile(db)


@pytest.fixture
def u3(db, u2):
    return make_profile(db)


# Convention "Standing rows, in every test, no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2, u1, u2, u3):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builder (flushes before it returns)
# --------------------------------------------------------------------------- #

# Convention "member": workspace W1, user U1, role "member", status "active";
# keywords override the columns the card lists after "but".
@pytest.fixture
def mk_member(db, w1, u1):
    """mk_member(**columns) -> WorkspaceMember, inserted and flushed."""
    def _mk(**columns):
        fields = {"workspace_id": w1.id, "user_id": u1.id, "role": "member", "status": "active"}
        fields.update(columns)
        row = WorkspaceMember(**fields)
        db.add(row)
        db.flush()
        return row
    return _mk


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (plain functions; no expected values inside)
# --------------------------------------------------------------------------- #

# Convention "idset(result)"
def idset(result):
    return {r.id for r in result}


# Convention "ids(result)": order is part of the check
def ids(result):
    return [r.id for r in result]


# Convention "seqscan": run in this order
def seqscan(db):
    db.execute(text("SET LOCAL enable_indexscan = off"))
    db.execute(text("SET LOCAL enable_bitmapscan = off"))
    db.execute(text("SET LOCAL enable_indexonlyscan = off"))


# WSM-WU-06 Then 4: rows stored for one workspace and user
def pair_count(db, workspace_id, user_id):
    t = WorkspaceMember.__table__
    return db.scalar(select(func.count()).select_from(t).where(t.c.workspace_id == workspace_id, t.c.user_id == user_id))


# WSM-WU-09, WSM-HA-07 Then 2 ("count:"): rows stored for one user, any workspace
def user_count(db, user_id):
    t = WorkspaceMember.__table__
    return db.scalar(select(func.count()).select_from(t).where(t.c.user_id == user_id))


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
        """The one SELECT from workspace_members; fails loudly unless there is exactly one."""
        [statement] = [s for s in self.statements
                       if s.lstrip().upper().startswith("SELECT") and "FROM workspace_members" in s]
        return statement


# Convention "order_part": the text of `sql` after its first ORDER BY ("" when there is none)
def order_part_of(sql):
    return sql.split("ORDER BY", 1)[1] if "ORDER BY" in sql else ""


# --------------------------------------------------------------------------- #
# WorkspaceMemberDAO.get_by_workspace_and_user
# --------------------------------------------------------------------------- #


# [claude] WSM-WU-01
def test_wsm_wu_01__the_row_of_that_user_in_that_workspace_is_returned_whatever_its_status(db, w1, w2, u1, mk_member):
    """WSM-WU-01 — the row of that user in that workspace is returned, whatever its status.
    Rules: `get_by_workspace_and_user` R1, Returns"""
    mk_member(workspace_id=w2.id)
    a = mk_member(status="inactive")

    result = dao.get_by_workspace_and_user(db, workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert isinstance(result, WorkspaceMember)
    # Then 2
    assert result.id == a.id
    # Then 3
    assert result.status == "inactive"
    assert result.role == "member"


# [claude] WSM-WU-02
def test_wsm_wu_02__the_user_s_row_in_another_workspace_the_earlier_id_is_not_matched(db, w1, w2, u1, u2, mk_member):
    """WSM-WU-02 — the user's row in another workspace, the earlier id, is not matched.
    Rules: `get_by_workspace_and_user` R2"""
    mk_member(workspace_id=w2.id)
    mk_member(user_id=u2.id)

    result = dao.get_by_workspace_and_user(db, workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert result is None


# [claude] WSM-WU-03
def test_wsm_wu_03__the_user_s_row_in_another_workspace_the_later_id_is_not_matched(db, w1, w2, u1, u2, mk_member):
    """WSM-WU-03 — the user's row in another workspace, the later id, is not matched.
    Rules: `get_by_workspace_and_user` R2"""
    mk_member(user_id=u2.id)
    mk_member(workspace_id=w2.id)

    result = dao.get_by_workspace_and_user(db, workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert result is None


# [claude] WSM-WU-04
def test_wsm_wu_04__user_id_0_gives_none_no_error(db, w1, mk_member):
    """WSM-WU-04 — user id 0 gives None, no error.
    Rules: `get_by_workspace_and_user` R2"""
    mk_member()

    result = dao.get_by_workspace_and_user(db, workspace_id=w1.id, user_id=0)

    # Then 1
    assert result is None


# [claude] WSM-WU-05
def test_wsm_wu_05__an_unknown_workspace_gives_none_no_error(db, u1, mk_member):
    """WSM-WU-05 — an unknown workspace gives None, no error.
    Rules: `get_by_workspace_and_user` R2"""
    mk_member()

    result = dao.get_by_workspace_and_user(db, workspace_id=MISSING, user_id=u1.id)

    # Then 1
    assert result is None


# [claude] WSM-WU-06
def test_wsm_wu_06__a_second_row_for_one_workspace_and_user_is_refused_by_the_database(db, w1, u1, mk_member):
    """WSM-WU-06 — a second row for one workspace and user is refused by the database.
    Rules: `get_by_workspace_and_user` R3"""
    mk_member()
    p = WorkspaceMember(workspace_id=w1.id, user_id=u1.id, role="admin", status="active")

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            db.add(p)
            db.flush()
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    assert "uq_workspace_user" in str(exc.value.orig)
    # Then 4
    assert pair_count(db, w1.id, u1.id) == 1


# [claude] WSM-WU-07
def test_wsm_wu_07__positional_arguments_raise_typeerror(db, w1, u1, mk_member):
    """WSM-WU-07 — positional arguments raise TypeError.
    Rules: `get_by_workspace_and_user` Errors"""
    mk_member()

    # Then 1
    with pytest.raises(TypeError):
        dao.get_by_workspace_and_user(db, w1.id, u1.id)


# [claude] WSM-WU-08
def test_wsm_wu_08__writes_nothing_a_pending_row_stays_pending_an_unflushed_edit_stays_unf(db, w1, u1, u2, u3, mk_member):
    """WSM-WU-08 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed.
    Rules: `get_by_workspace_and_user` Side effects"""
    a = mk_member()
    b = mk_member(user_id=u2.id)
    p = WorkspaceMember(workspace_id=w1.id, user_id=u3.id, role="member", status="active")
    db.add(p)
    b.role = "admin"

    with StatementRecorder(db) as recorder:
        result = dao.get_by_workspace_and_user(db, workspace_id=w1.id, user_id=u1.id)
    written = recorder.written()

    # Then 1
    assert result.id == a.id
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert b in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert not db.deleted
    # Then 7
    assert written == []


# [claude] WSM-WU-09
def test_wsm_wu_09__another_user_with_a_lower_id_in_this_workspace_is_not_matched(db, w1, u2, mk_member):
    """WSM-WU-09 — another user with a lower id in this workspace is not matched.
    Rules: `get_by_workspace_and_user` R2"""
    mk_member()

    result = dao.get_by_workspace_and_user(db, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert user_count(db, u2.id) == 0


# --------------------------------------------------------------------------- #
# WorkspaceMemberDAO.get_by_user
# --------------------------------------------------------------------------- #


# [claude] WSM-GU-01
def test_wsm_gu_01__every_membership_of_the_user_in_every_workspace_whatever_the_status(db, w2, u1, u2, mk_member):
    """WSM-GU-01 — every membership of the user, in every workspace, whatever the status.
    Rules: `get_by_user` R1, Returns"""
    a = mk_member()
    mk_member(user_id=u2.id)
    b = mk_member(workspace_id=w2.id, status="inactive")

    result = dao.get_by_user(db, user_id=u1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert idset(result) == {a.id, b.id}
    # Then 3
    assert len(result) == 2


# [claude] WSM-GU-02
def test_wsm_gu_02__user_id_0_returns_an_empty_list(db, mk_member):
    """WSM-GU-02 — user id 0 returns an empty list.
    Rules: `get_by_user` R2"""
    mk_member()

    result = dao.get_by_user(db, user_id=0)

    # Then 1
    assert result == []


# [claude] WSM-GU-03
def test_wsm_gu_03__no_cap_101_memberships_give_101_rows(db, u1, mk_member):
    """WSM-GU-03 — no cap: 101 memberships give 101 rows.
    Rules: `get_by_user` R2"""
    v = [make_workspace(db) for _ in range(101)]
    m = [mk_member(workspace_id=vk.id) for vk in v]

    result = dao.get_by_user(db, user_id=u1.id)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert idset(result) == {mk.id for mk in m}


# [claude] WSM-GU-04
@pytest.mark.xfail(strict=False, reason=BUG_1400_NON_STRICT)
def test_wsm_gu_04__rows_come_id_ascending_also_after_the_lowest_id_was_updated(db, w2, u1, mk_member):
    """WSM-GU-04 — rows come id ascending, also after the lowest id was updated.
    Rules: `get_by_user` R3 [BUG-1400]"""
    w3 = make_workspace(db)
    w4 = make_workspace(db)
    seqscan(db)
    a = mk_member()
    b = mk_member(workspace_id=w2.id)
    c = mk_member(workspace_id=w3.id)
    d = mk_member(workspace_id=w4.id)
    a.role = "admin"
    db.flush()
    db.expire_all()

    result = dao.get_by_user(db, user_id=u1.id)

    # Then 1
    assert len(result) == 4
    # Then 2
    assert ids(result) == [a.id, b.id, c.id, d.id]


# [claude] WSM-GU-05
@pytest.mark.xfail(strict=True, reason=BUG_1400)
def test_wsm_gu_05__the_query_orders_by_id_ascending(db, u1, mk_member):
    """WSM-GU-05 — the query orders by id ascending.
    Rules: `get_by_user` R3 [BUG-1400]"""
    a = mk_member()

    with StatementRecorder(db) as recorder:
        result = dao.get_by_user(db, user_id=u1.id)
    sql = recorder.sql()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert ".id" in order_part
    # Then 4
    assert "DESC" not in order_part.upper()
    # Then 5
    assert order_part.count(",") == 0


# [claude] WSM-GU-06
def test_wsm_gu_06__writes_nothing_a_pending_row_stays_pending_an_unflushed_edit_stays_unf(db, w2, u1, u2, mk_member):
    """WSM-GU-06 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed.
    Rules: `get_by_user` Side effects"""
    a = mk_member()
    b = mk_member(user_id=u2.id)
    p = WorkspaceMember(workspace_id=w2.id, user_id=u1.id, role="member", status="active")
    db.add(p)
    b.role = "admin"

    with StatementRecorder(db) as recorder:
        result = dao.get_by_user(db, user_id=u1.id)
    written = recorder.written()

    # Then 1
    assert idset(result) == {a.id}
    # Then 2
    assert p in db.new
    # Then 3
    assert p.id is None
    # Then 4
    assert len(db.new) == 1
    # Then 5
    assert b in db.dirty
    # Then 6
    assert len(db.dirty) == 1
    # Then 7
    assert not db.deleted
    # Then 8
    assert written == []


# [claude] WSM-GU-07
def test_wsm_gu_07__another_user_s_row_with_a_lower_user_id_is_not_returned(db, w2, u2, mk_member):
    """WSM-GU-07 — another user's row with a lower user id is not returned.
    Rules: `get_by_user` R1"""
    mk_member()
    a = mk_member(user_id=u2.id, workspace_id=w2.id)

    result = dao.get_by_user(db, user_id=u2.id)

    # Then 1
    assert idset(result) == {a.id}


# --------------------------------------------------------------------------- #
# WorkspaceMemberDAO.get_workspace_members
# --------------------------------------------------------------------------- #


# [claude] WSM-GM-01
def test_wsm_gm_01__by_default_only_rows_with_status_exactly_active(db, w1, u2, u3, mk_member):
    """WSM-GM-01 — by default only rows with status exactly 'active'.
    Rules: `get_workspace_members` R1, Returns"""
    a = mk_member()
    mk_member(user_id=u2.id, status="Active")
    mk_member(user_id=u3.id, status="inactive")
    p4 = make_profile(db)
    mk_member(user_id=p4.id, status=" active")
    p5 = make_profile(db)
    mk_member(user_id=p5.id, status="suspended")
    p6 = make_profile(db)
    mk_member(user_id=p6.id, status="invited")

    result = dao.get_workspace_members(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert idset(result) == {a.id}


# [claude] WSM-GM-02
def test_wsm_gm_02__status_none_returns_every_row_of_the_workspace_and_none_of_another(db, w1, w2, u2, u3, mk_member):
    """WSM-GM-02 — status=None returns every row of the workspace, and none of another.
    Rules: `get_workspace_members` R2, R3"""
    a = mk_member()
    b = mk_member(user_id=u2.id, status="inactive")
    c = mk_member(user_id=u3.id, status="")
    mk_member(workspace_id=w2.id)

    result = dao.get_workspace_members(db, workspace_id=w1.id, status=None)

    # Then 1
    assert idset(result) == {a.id, b.id, c.id}


# [claude] WSM-GM-03
def test_wsm_gm_03__status_returns_the_rows_whose_status_is_the_empty_string_not_every_row(db, w1, u2, mk_member):
    """WSM-GM-03 — status="" returns the rows whose status is the empty string, not every row.
    Rules: `get_workspace_members` R2"""
    mk_member()
    b = mk_member(user_id=u2.id, status="")

    result = dao.get_workspace_members(db, workspace_id=w1.id, status="")

    # Then 1
    assert idset(result) == {b.id}


# [claude] WSM-GM-04
def test_wsm_gm_04__another_status_keeps_exactly_the_rows_with_that_status(db, w1, w2, u2, mk_member):
    """WSM-GM-04 — another status keeps exactly the rows with that status.
    Rules: `get_workspace_members` R2"""
    mk_member()
    b = mk_member(user_id=u2.id, status="suspended")
    mk_member(workspace_id=w2.id, status="suspended")

    result = dao.get_workspace_members(db, workspace_id=w1.id, status="suspended")

    # Then 1
    assert idset(result) == {b.id}


# [claude] WSM-GM-05
def test_wsm_gm_05__status_in_capitals_finds_nothing(db, w1, mk_member):
    """WSM-GM-05 — status in capitals finds nothing.
    Rules: `get_workspace_members` R2"""
    mk_member(status="suspended")

    result = dao.get_workspace_members(db, workspace_id=w1.id, status="Suspended")

    # Then 1
    assert result == []


# [claude] WSM-GM-06
def test_wsm_gm_06__status_with_a_leading_space_finds_nothing(db, w1, mk_member):
    """WSM-GM-06 — status with a leading space finds nothing.
    Rules: `get_workspace_members` R2"""
    mk_member(status="suspended")

    result = dao.get_workspace_members(db, workspace_id=w1.id, status=" suspended")

    # Then 1
    assert result == []


# [claude] WSM-GM-07
def test_wsm_gm_07__part_of_a_status_finds_nothing(db, w1, mk_member):
    """WSM-GM-07 — part of a status finds nothing.
    Rules: `get_workspace_members` R2"""
    mk_member(status="suspended")

    result = dao.get_workspace_members(db, workspace_id=w1.id, status="suspend")

    # Then 1
    assert result == []


# [claude] WSM-GM-08
def test_wsm_gm_08__is_no_wildcard_in_a_status(db, w1, mk_member):
    """WSM-GM-08 — _ is no wildcard in a status.
    Rules: `get_workspace_members` R2"""
    mk_member(status="suspended")

    result = dao.get_workspace_members(db, workspace_id=w1.id, status="suspende_")

    # Then 1
    assert result == []


# [claude] WSM-GM-09
def test_wsm_gm_09__workspace_id_0_returns_an_empty_list(db, mk_member):
    """WSM-GM-09 — workspace id 0 returns an empty list.
    Rules: `get_workspace_members` R3"""
    mk_member()

    result = dao.get_workspace_members(db, workspace_id=0, status=None)

    # Then 1
    assert result == []


# [claude] WSM-GM-10
def test_wsm_gm_10__no_cap_101_active_members_give_101_rows(db, w1, mk_member):
    """WSM-GM-10 — no cap: 101 active members give 101 rows.
    Rules: `get_workspace_members` R3"""
    p = [make_profile(db) for _ in range(101)]
    m = [mk_member(user_id=pk.id) for pk in p]

    result = dao.get_workspace_members(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert idset(result) == {mk.id for mk in m}


# [claude] WSM-GM-11
@pytest.mark.xfail(strict=False, reason=BUG_1400_NON_STRICT)
def test_wsm_gm_11__rows_come_id_ascending_also_after_the_lowest_id_was_updated(db, w1, u2, u3, mk_member):
    """WSM-GM-11 — rows come id ascending, also after the lowest id was updated.
    Rules: `get_workspace_members` R4 [BUG-1400]"""
    p4 = make_profile(db)
    seqscan(db)
    a = mk_member()
    b = mk_member(user_id=u2.id)
    c = mk_member(user_id=u3.id)
    d = mk_member(user_id=p4.id)
    a.role = "admin"
    db.flush()
    db.expire_all()

    result = dao.get_workspace_members(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 4
    # Then 2
    assert ids(result) == [a.id, b.id, c.id, d.id]


# [claude] WSM-GM-12
@pytest.mark.xfail(strict=True, reason=BUG_1400)
def test_wsm_gm_12__the_query_orders_by_id_ascending(db, w1, mk_member):
    """WSM-GM-12 — the query orders by id ascending.
    Rules: `get_workspace_members` R4 [BUG-1400]"""
    a = mk_member()

    with StatementRecorder(db) as recorder:
        result = dao.get_workspace_members(db, workspace_id=w1.id)
    sql = recorder.sql()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert ".id" in order_part
    # Then 4
    assert "DESC" not in order_part.upper()
    # Then 5
    assert order_part.count(",") == 0


# [claude] WSM-GM-13
def test_wsm_gm_13__writes_nothing_a_pending_row_stays_pending_an_unflushed_edit_stays_unf(db, w1, w2, u2, mk_member):
    """WSM-GM-13 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed.
    Rules: `get_workspace_members` Side effects"""
    a = mk_member()
    b = mk_member(workspace_id=w2.id)
    p = WorkspaceMember(workspace_id=w1.id, user_id=u2.id, role="member", status="active")
    db.add(p)
    b.role = "admin"

    with StatementRecorder(db) as recorder:
        result = dao.get_workspace_members(db, workspace_id=w1.id)
    written = recorder.written()

    # Then 1
    assert idset(result) == {a.id}
    # Then 2
    assert p in db.new
    # Then 3
    assert p.id is None
    # Then 4
    assert len(db.new) == 1
    # Then 5
    assert b in db.dirty
    # Then 6
    assert len(db.dirty) == 1
    # Then 7
    assert not db.deleted
    # Then 8
    assert written == []


# [claude] WSM-GM-14
def test_wsm_gm_14__a_row_of_a_workspace_with_a_lower_id_is_not_returned(db, w2, mk_member):
    """WSM-GM-14 — a row of a workspace with a lower id is not returned.
    Rules: `get_workspace_members` R3"""
    mk_member()
    a = mk_member(workspace_id=w2.id)

    result = dao.get_workspace_members(db, workspace_id=w2.id, status=None)

    # Then 1
    assert idset(result) == {a.id}


# --------------------------------------------------------------------------- #
# WorkspaceMemberDAO.get_by_workspace
# --------------------------------------------------------------------------- #


# [claude] WSM-GW-01
def test_wsm_gw_01__every_row_of_the_workspace_whatever_the_status_none_of_another(db, w1, w2, u2, u3, mk_member):
    """WSM-GW-01 — every row of the workspace, whatever the status, none of another.
    Rules: `get_by_workspace` R1"""
    a = mk_member()
    b = mk_member(user_id=u2.id, status="inactive")
    c = mk_member(user_id=u3.id, status="Active")
    mk_member(workspace_id=w2.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert idset(result) == {a.id, b.id, c.id}


# [claude] WSM-GW-02
@pytest.mark.xfail(strict=True, reason=BUG_1400)
def test_wsm_gw_02__the_query_orders_by_id_ascending(db, w1, mk_member):
    """WSM-GW-02 — the query orders by id ascending.
    Rules: `get_by_workspace` R2 [BUG-1400]"""
    a = mk_member()

    with StatementRecorder(db) as recorder:
        result = dao.get_by_workspace(db, workspace_id=w1.id)
    sql = recorder.sql()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert ".id" in order_part
    # Then 4
    assert "DESC" not in order_part.upper()
    # Then 5
    assert order_part.count(",") == 0


# [claude] WSM-GW-03
def test_wsm_gw_03__skip_is_refused(db, w1, mk_member):
    """WSM-GW-03 — skip is refused.
    Rules: `get_by_workspace` R3, Errors"""
    mk_member()

    # Then 1
    with pytest.raises(TypeError):
        dao.get_by_workspace(db, workspace_id=w1.id, skip=0)


# [claude] WSM-GW-04
def test_wsm_gw_04__limit_is_refused(db, w1, mk_member):
    """WSM-GW-04 — limit is refused.
    Rules: `get_by_workspace` R3, Errors"""
    mk_member()

    # Then 1
    with pytest.raises(TypeError):
        dao.get_by_workspace(db, workspace_id=w1.id, limit=100)


# [claude] WSM-GW-05
def test_wsm_gw_05__a_positional_workspace_id_is_refused(db, w1, mk_member):
    """WSM-GW-05 — a positional workspace id is refused.
    Rules: `get_by_workspace` Errors"""
    mk_member()

    # Then 1
    with pytest.raises(TypeError):
        dao.get_by_workspace(db, w1.id)


# [claude] WSM-GW-06
def test_wsm_gw_06__no_cap_101_members_give_101_rows_the_base_method_stopped_at_100(db, w1, mk_member):
    """WSM-GW-06 — no cap: 101 members give 101 rows (the base method stopped at 100).
    Rules: `get_by_workspace` R1"""
    p = [make_profile(db) for _ in range(101)]
    m = [mk_member(user_id=pk.id, status="inactive") for pk in p]

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert idset(result) == {mk.id for mk in m}


# [claude] WSM-GW-07
def test_wsm_gw_07__writes_nothing_a_pending_row_stays_pending_an_unflushed_edit_stays_unf(db, w1, w2, u2, mk_member):
    """WSM-GW-07 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed.
    Rules: `get_by_workspace` Side effects"""
    a = mk_member()
    b = mk_member(workspace_id=w2.id)
    p = WorkspaceMember(workspace_id=w1.id, user_id=u2.id, role="member", status="active")
    db.add(p)
    b.role = "admin"

    with StatementRecorder(db) as recorder:
        result = dao.get_by_workspace(db, workspace_id=w1.id)
    written = recorder.written()

    # Then 1
    assert idset(result) == {a.id}
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert b in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert not db.deleted
    # Then 7
    assert written == []


# --------------------------------------------------------------------------- #
# WorkspaceMemberDAO.count_active_members
# --------------------------------------------------------------------------- #


# [claude] WSM-CA-01
def test_wsm_ca_01__counts_the_rows_with_status_exactly_active_the_owner_s_included(db, w1, w2, u2, u3, mk_member):
    """WSM-CA-01 — counts the rows with status exactly 'active', the owner's included.
    Rules: `count_active_members` R1, R2, Returns"""
    mk_member(role="owner")
    mk_member(user_id=u2.id)
    mk_member(user_id=u3.id, status="Active")
    p4 = make_profile(db)
    mk_member(user_id=p4.id, status="inactive")
    p5 = make_profile(db)
    mk_member(user_id=p5.id, status=" active")
    mk_member(workspace_id=w2.id)

    result = dao.count_active_members(db, workspace_id=w1.id)

    # Then 1
    assert type(result) is int
    # Then 2
    assert result == 2


# [claude] WSM-CA-02
def test_wsm_ca_02__a_workspace_with_no_active_member_gives_0(db, w1, w2, mk_member):
    """WSM-CA-02 — a workspace with no active member gives 0.
    Rules: `count_active_members` R2"""
    mk_member(status="inactive")
    mk_member(workspace_id=w2.id)

    result = dao.count_active_members(db, workspace_id=w1.id)

    # Then 1
    assert result == 0


# [claude] WSM-CA-03
def test_wsm_ca_03__workspace_id_0_gives_0(db, mk_member):
    """WSM-CA-03 — workspace id 0 gives 0.
    Rules: `count_active_members` R2"""
    mk_member()

    result = dao.count_active_members(db, workspace_id=0)

    # Then 1
    assert result == 0


# [claude] WSM-CA-04
def test_wsm_ca_04__writes_nothing_a_pending_row_stays_pending_and_is_not_counted(db, w1, w2, u2, mk_member):
    """WSM-CA-04 — writes nothing: a pending row stays pending and is not counted.
    Rules: `count_active_members` Side effects"""
    mk_member()
    b = mk_member(workspace_id=w2.id)
    p = WorkspaceMember(workspace_id=w1.id, user_id=u2.id, role="member", status="active")
    db.add(p)
    b.role = "admin"

    with StatementRecorder(db) as recorder:
        result = dao.count_active_members(db, workspace_id=w1.id)
    written = recorder.written()

    # Then 1
    assert result == 1
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert b in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert written == []


# [claude] WSM-CA-05
def test_wsm_ca_05__an_active_row_of_a_workspace_with_a_lower_id_is_not_counted(db, w2, mk_member):
    """WSM-CA-05 — an active row of a workspace with a lower id is not counted.
    Rules: `count_active_members` R2"""
    mk_member()
    mk_member(workspace_id=w2.id)

    result = dao.count_active_members(db, workspace_id=w2.id)

    # Then 1
    assert result == 1


# [claude] WSM-CA-06
def test_wsm_ca_06__a_part_of_active_or_a_longer_word_is_not_counted(db, w1, u2, mk_member):
    """WSM-CA-06 — a part of 'active', or a longer word, is not counted.
    Rules: `count_active_members` R1"""
    mk_member(status="activ")
    mk_member(user_id=u2.id, status="actives")

    result = dao.count_active_members(db, workspace_id=w1.id)

    # Then 1
    assert result == 0


# --------------------------------------------------------------------------- #
# WorkspaceMemberDAO.has_access
# --------------------------------------------------------------------------- #


# [claude] WSM-HA-01
def test_wsm_ha_01__an_active_member_has_access(db, w1, w2, u1, mk_member):
    """WSM-HA-01 — an active member has access.
    Rules: `has_access` R1, Returns"""
    mk_member(workspace_id=w2.id, status="inactive")
    mk_member()

    result = dao.has_access(db, user_id=u1.id, workspace_id=w1.id)

    # Then 1
    assert result is True


# [claude] WSM-HA-02
def test_wsm_ha_02__status_active_in_capitals_gives_false(db, w1, u1, mk_member):
    """WSM-HA-02 — status 'Active' in capitals gives False.
    Rules: `has_access` R2"""
    mk_member(status="Active")

    result = dao.has_access(db, user_id=u1.id, workspace_id=w1.id)

    # Then 1
    assert result is False


# [claude] WSM-HA-03
def test_wsm_ha_03__status_inactive_gives_false(db, w1, u1, mk_member):
    """WSM-HA-03 — status 'inactive' gives False.
    Rules: `has_access` R2"""
    mk_member(status="inactive")

    result = dao.has_access(db, user_id=u1.id, workspace_id=w1.id)

    # Then 1
    assert result is False


# [claude] WSM-HA-04
def test_wsm_ha_04__an_active_member_of_another_workspace_only_gives_false(db, w1, w2, u1, u2, mk_member):
    """WSM-HA-04 — an active member of another workspace only gives False.
    Rules: `has_access` R2"""
    mk_member(workspace_id=w2.id)
    mk_member(user_id=u2.id)

    result = dao.has_access(db, user_id=u1.id, workspace_id=w1.id)

    # Then 1
    assert result is False


# [claude] WSM-HA-05
def test_wsm_ha_05__user_id_0_gives_false(db, w1, mk_member):
    """WSM-HA-05 — user id 0 gives False.
    Rules: `has_access` R2"""
    mk_member()

    result = dao.has_access(db, user_id=0, workspace_id=w1.id)

    # Then 1
    assert result is False


# [claude] WSM-HA-06
def test_wsm_ha_06__writes_nothing_a_pending_row_stays_pending_an_unflushed_edit_stays_unf(db, w1, u1, u2, u3, mk_member):
    """WSM-HA-06 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed.
    Rules: `has_access` Side effects"""
    mk_member()
    b = mk_member(user_id=u2.id)
    p = WorkspaceMember(workspace_id=w1.id, user_id=u3.id, role="member", status="active")
    db.add(p)
    b.status = "inactive"

    with StatementRecorder(db) as recorder:
        result = dao.has_access(db, user_id=u1.id, workspace_id=w1.id)
    written = recorder.written()

    # Then 1
    assert result is True
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert b in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert written == []


# [claude] WSM-HA-07
def test_wsm_ha_07__the_access_gate_a_non_member_with_a_higher_id_than_the_only_member_get(db, w1, u2, mk_member):
    """WSM-HA-07 — the access gate: a non-member with a higher id than the only member gets False.
    Rules: `has_access` R2"""
    mk_member()

    result = dao.has_access(db, user_id=u2.id, workspace_id=w1.id)

    # Then 1
    assert result is False
    # Then 2
    assert user_count(db, u2.id) == 0


# [claude] WSM-HA-08
def test_wsm_ha_08__status_gives_false(db, w1, u1, mk_member):
    """WSM-HA-08 — status "" gives False.
    Rules: `has_access` R2"""
    mk_member(status="")

    result = dao.has_access(db, user_id=u1.id, workspace_id=w1.id)

    # Then 1
    assert result is False


# [claude] WSM-HA-09
def test_wsm_ha_09__status_active_with_a_leading_space_gives_false(db, w1, u1, mk_member):
    """WSM-HA-09 — status " active" with a leading space gives False.
    Rules: `has_access` R2"""
    mk_member(status=" active")

    result = dao.has_access(db, user_id=u1.id, workspace_id=w1.id)

    # Then 1
    assert result is False


# [claude] WSM-HA-10
def test_wsm_ha_10__status_active_with_a_trailing_space_gives_false(db, w1, u1, mk_member):
    """WSM-HA-10 — status "active " with a trailing space gives False.
    Rules: `has_access` R2"""
    mk_member(status="active ")

    result = dao.has_access(db, user_id=u1.id, workspace_id=w1.id)

    # Then 1
    assert result is False


# [claude] WSM-HA-11
def test_wsm_ha_11__status_activ_a_part_of_the_word_gives_false(db, w1, u1, mk_member):
    """WSM-HA-11 — status "activ", a part of the word, gives False.
    Rules: `has_access` R2"""
    mk_member(status="activ")

    result = dao.has_access(db, user_id=u1.id, workspace_id=w1.id)

    # Then 1
    assert result is False
