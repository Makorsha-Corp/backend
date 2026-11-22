"""Unit tests for app/dao/workspace_audit_log.py.

Implements tests/unit/dao/workspace_audit_log.cases.md, one test per case, in
card order. Real Postgres session (`db` fixture). Nothing is mocked and no clock
is patched (Conventions, Externals: None); WAL-LA-20 wraps `db.commit` in a spy
that still calls through, as its "rolled back" convention prescribes.

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117, DTZ001  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested():`, and a naive datetime in WAL-LA-11)
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy.exc import DataError, IntegrityError, StatementError

from app.dao.workspace_audit_log import workspace_audit_log_dao
from app.models.workspace_audit_log import WorkspaceAuditLog
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton workspace_audit_log_dao"
dao = workspace_audit_log_dao

# Convention "MISSING, SLACK, IP45, IP46, UA5000"
MISSING = 999999999
SLACK = timedelta(seconds=5)
IP45 = "1" * 45
IP46 = "1" * 46
UA5000 = "u" * 5000


# --------------------------------------------------------------------------- #
# Conventions -> the rows that exist in every test
# --------------------------------------------------------------------------- #

# Convention "W1, W2 = two workspaces rows from make_workspace(db)". w2 depends
# on w1, so the ids rise in the order the Conventions list them.
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


# Convention "U1 = a profiles row from make_profile(db)"
@pytest.fixture
def u1(db, w2):
    return make_profile(db)


# Convention "Standing rows, in every test, no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2, u1):
    return None


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (plain functions; no expected values inside)
# --------------------------------------------------------------------------- #

# Convention "re-read X": db.expire_all(), then SELECT X by id
def reread(db, row_id):
    db.expire_all()
    return db.execute(select(WorkspaceAuditLog).where(WorkspaceAuditLog.id == row_id)).scalar_one_or_none()


# Convention "nothing written": the number of workspace_audit_logs rows stored (all workspaces)
def stored_count(db):
    return db.scalar(select(func.count()).select_from(WorkspaceAuditLog.__table__))


# The "count: workspace_audit_logs has exactly N rows with ..." lines
def count_rows(db, **where):
    stmt = select(func.count()).select_from(WorkspaceAuditLog)
    for column, value in where.items():
        stmt = stmt.where(getattr(WorkspaceAuditLog, column) == value)
    return db.scalar(stmt)


# Convention "clock window": a naive UTC reading of the real clock
def utc_clock():
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Convention "stamp(X)": created_at read as UTC, a naive value
def stamp(db, row):
    return db.execute(
        text("SELECT created_at AT TIME ZONE 'UTC' FROM workspace_audit_logs WHERE id = :id"), {"id": row.id}
    ).scalar()


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

    def selects(self):
        return [s for s in self.statements if s.lstrip().upper().startswith("SELECT")]


# --------------------------------------------------------------------------- #
# WorkspaceAuditLogDAO.log_action
# --------------------------------------------------------------------------- #


# [claude] WAL-LA-01
def test_wal_la_01__one_row_with_exactly_the_given_values_flushed(db, w1, u1):
    """WAL-LA-01 — one row with exactly the given values, flushed.
    Rules: `log_action` R1, Returns"""
    result = dao.log_action(db, workspace_id=w1.id, user_id=u1.id, action="member_added",
                            resource_type="workspace_member", resource_id=42, metadata={"role": "admin", "n": 2},
                            ip_address="10.0.0.1", user_agent="Mozilla/5.0")

    # Then 1
    assert isinstance(result, WorkspaceAuditLog)
    # Then 2
    assert result.id is not None
    # Then 3
    row = reread(db, result.id)
    assert row.workspace_id == w1.id
    assert row.user_id == u1.id
    assert row.action == "member_added"
    # Then 4
    assert row.resource_type == "workspace_member"
    assert row.resource_id == 42
    # Then 5
    assert row.metadata_json == {"role": "admin", "n": 2}
    # Then 6
    assert row.ip_address == "10.0.0.1"
    assert row.user_agent == "Mozilla/5.0"
    # Then 7
    assert count_rows(db, workspace_id=w1.id) == 1


# [claude] WAL-LA-02
def test_wal_la_02__optional_values_not_given_are_stored_null_an_empty_action_is_accepted(db, w1, u1):
    """WAL-LA-02 — optional values not given are stored NULL; an empty action is accepted.
    Rules: `log_action` R2"""
    result = dao.log_action(db, workspace_id=w1.id, user_id=u1.id, action="")

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result.id)
    assert row.action == ""
    # Then 3
    assert row.resource_type is None
    assert row.resource_id is None
    assert row.metadata_json is None
    # Then 4
    assert row.ip_address is None
    assert row.user_agent is None


# [claude] WAL-LA-03
def test_wal_la_03__no_workspace_and_no_user_are_stored_null(db):
    """WAL-LA-03 — no workspace and no user are stored NULL.
    Rules: `log_action` R2"""
    result = dao.log_action(db, workspace_id=None, user_id=None, action="system_check")

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result.id)
    assert row.workspace_id is None
    assert row.user_id is None
    assert row.action == "system_check"


# [claude] WAL-LA-04
def test_wal_la_04__a_list_as_metadata_is_stored(db, w1, u1):
    """WAL-LA-04 — a list as metadata is stored.
    Rules: `log_action` R1"""
    result = dao.log_action(db, workspace_id=w1.id, user_id=u1.id, action="bulk", metadata=[1, "two"])

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result.id)
    assert row.metadata_json == [1, "two"]


# [claude] WAL-LA-05
def test_wal_la_05__a_5_000_character_user_agent_is_stored_whole(db, w1, u1):
    """WAL-LA-05 — a 5 000-character user agent is stored whole.
    Rules: `log_action` R3"""
    result = dao.log_action(db, workspace_id=w1.id, user_id=u1.id, action="login", user_agent=UA5000)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result.id)
    assert row.user_agent == UA5000


# [claude] WAL-LA-06
def test_wal_la_06__a_45_character_ip_address_is_stored_whole(db, w1, u1):
    """WAL-LA-06 — a 45-character IP address is stored whole.
    Rules: `log_action` R3"""
    result = dao.log_action(db, workspace_id=w1.id, user_id=u1.id, action="login", ip_address=IP45)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result.id)
    assert row.ip_address == IP45


# [claude] WAL-LA-07
@pytest.mark.xfail(strict=True, reason="BUG-1405: Over-long IP address would fail the audited action")
def test_wal_la_07__a_46_character_ip_address_is_cut_to_45_and_the_row_is_written(db, w1, u1):
    """WAL-LA-07 — a 46-character IP address is cut to 45 and the row is written.
    Rules: `log_action` R3 [BUG-1405]"""
    with db.begin_nested():
        result = dao.log_action(db, workspace_id=w1.id, user_id=u1.id, action="login", ip_address=IP46)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result.id)
    assert row.ip_address == IP45
    # Then 3
    assert count_rows(db, workspace_id=w1.id) == 1


# [claude] WAL-LA-08
def test_wal_la_08__an_action_of_100_and_a_resource_type_of_50_characters_are_stored_whole(db, w1, u1):
    """WAL-LA-08 — an action of 100 and a resource type of 50 characters are stored whole.
    Rules: `log_action` R4"""
    result = dao.log_action(db, workspace_id=w1.id, user_id=u1.id, action="a" * 100, resource_type="r" * 50)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result.id)
    assert row.action == "a" * 100
    assert row.resource_type == "r" * 50


# [claude] WAL-LA-09
def test_wal_la_09__an_action_of_101_characters_raises_dataerror_and_writes_nothing(db, w1, u1):
    """WAL-LA-09 — an action of 101 characters raises DataError and writes nothing.
    Rules: `log_action` R4, Errors row 1"""
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.log_action(db, workspace_id=w1.id, user_id=u1.id, action="a" * 101)
    # Then 2
    assert exc.value.orig.pgcode == "22001"
    # Then 3
    assert stored_count(db) == before


# [claude] WAL-LA-10
def test_wal_la_10__a_resource_type_of_51_characters_raises_dataerror_and_writes_nothing(db, w1, u1):
    """WAL-LA-10 — a resource type of 51 characters raises DataError and writes nothing.
    Rules: `log_action` R4, Errors row 1"""
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.log_action(db, workspace_id=w1.id, user_id=u1.id, action="x", resource_type="r" * 51)
    # Then 2
    assert exc.value.orig.pgcode == "22001"
    # Then 3
    assert stored_count(db) == before


# [claude] WAL-LA-11
def test_wal_la_11__metadata_json_cannot_encode_raises_statementerror_and_writes_nothing(db, w1, u1):
    """WAL-LA-11 — metadata JSON cannot encode raises StatementError and writes nothing.
    Rules: `log_action` R4, Errors row 3"""
    before = stored_count(db)

    # Then 1
    with pytest.raises(StatementError) as exc:
        with db.begin_nested():
            dao.log_action(db, workspace_id=w1.id, user_id=u1.id, action="x",
                           metadata={"at": datetime(2026, 3, 5, 12, 0, 0)})
    # Then 2
    assert isinstance(exc.value.orig, TypeError)
    # Then 3
    assert stored_count(db) == before


# [claude] WAL-LA-12
def test_wal_la_12__an_unknown_workspace_raises_integrityerror_23503_and_writes_nothing(db, u1):
    """WAL-LA-12 — an unknown workspace raises IntegrityError 23503 and writes nothing.
    Rules: `log_action` R4, Errors row 2"""
    before = stored_count(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.log_action(db, workspace_id=MISSING, user_id=u1.id, action="x")
    # Then 2
    assert exc.value.orig.pgcode == "23503"
    # Then 3
    assert stored_count(db) == before


# [claude] WAL-LA-13
def test_wal_la_13__an_unknown_user_raises_integrityerror_23503_and_writes_nothing(db, w1):
    """WAL-LA-13 — an unknown user raises IntegrityError 23503 and writes nothing.
    Rules: `log_action` R4, Errors row 2"""
    before = stored_count(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.log_action(db, workspace_id=w1.id, user_id=MISSING, action="x")
    # Then 2
    assert exc.value.orig.pgcode == "23503"
    # Then 3
    assert stored_count(db) == before


# [claude] WAL-LA-14
def test_wal_la_14__under_a_utc_session_created_at_read_as_utc_is_the_moment_of_the_call(db, w1, u1):
    """WAL-LA-14 — under a UTC session, created_at read as UTC is the moment of the call.
    Rules: `log_action` R5"""
    db.execute(text("SET LOCAL TIME ZONE 'UTC'"))
    before = utc_clock()

    result = dao.log_action(db, workspace_id=w1.id, user_id=u1.id, action="tz")
    after = utc_clock()

    # Then 1
    assert result.id is not None
    # Then 2
    db.expire_all()
    assert stamp(db, result) >= before - SLACK
    # Then 3
    assert stamp(db, result) <= after + SLACK


# [claude] WAL-LA-15
@pytest.mark.xfail(strict=True, reason="BUG-1403: A workspace audit row's time depends on the database's time zone")
def test_wal_la_15__under_asia_dhaka_created_at_read_as_utc_is_still_the_moment_of_the_cal(db, w1, u1):
    """WAL-LA-15 — under Asia/Dhaka, created_at read as UTC is still the moment of the call.
    Rules: `log_action` R5 [BUG-1403]"""
    db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))
    before = utc_clock()

    result = dao.log_action(db, workspace_id=w1.id, user_id=u1.id, action="tz")
    after = utc_clock()

    # Then 1
    assert result.id is not None
    # Then 2
    db.expire_all()
    assert stamp(db, result) >= before - SLACK
    # Then 3
    assert stamp(db, result) <= after + SLACK


# [claude] WAL-LA-16
@pytest.mark.xfail(strict=True, reason="BUG-1403: A workspace audit row's time depends on the database's time zone")
def test_wal_la_16__under_america_new_york_created_at_read_as_utc_is_still_the_moment_of_t(db, w1, u1):
    """WAL-LA-16 — under America/New_York, created_at read as UTC is still the moment of the call.
    Rules: `log_action` R5 [BUG-1403]"""
    db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))
    before = utc_clock()

    result = dao.log_action(db, workspace_id=w1.id, user_id=u1.id, action="tz")
    after = utc_clock()

    # Then 1
    assert result.id is not None
    # Then 2
    db.expire_all()
    assert stamp(db, result) <= after + SLACK
    # Then 3
    assert stamp(db, result) >= before - SLACK


# [claude] WAL-LA-17
def test_wal_la_17__an_identical_earlier_row_does_not_stop_a_second_one(db, w1, u1):
    """WAL-LA-17 — an identical earlier row does not stop a second one.
    Rules: `log_action` R6"""
    e = WorkspaceAuditLog(workspace_id=w1.id, user_id=u1.id, action="member_added")
    db.add(e)
    db.flush()

    result = dao.log_action(db, workspace_id=w1.id, user_id=u1.id, action="member_added")

    # Then 1
    assert result.id != e.id
    # Then 2
    assert count_rows(db, workspace_id=w1.id, action="member_added") == 2


# [claude] WAL-LA-18
def test_wal_la_18__positional_arguments_raise_typeerror(db, w1, u1):
    """WAL-LA-18 — positional arguments raise TypeError.
    Rules: `log_action` R7, Errors row 4"""
    before = stored_count(db)

    # Then 1
    with pytest.raises(TypeError):
        dao.log_action(db, w1.id, u1.id, "x")
    # Then 2
    assert stored_count(db) == before


# [claude] WAL-LA-19
def test_wal_la_19__leaving_out_action_raises_typeerror(db, w1, u1):
    """WAL-LA-19 — leaving out action raises TypeError.
    Rules: `log_action` R7, Errors row 4"""
    before = stored_count(db)

    # Then 1
    with pytest.raises(TypeError):
        dao.log_action(db, workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert stored_count(db) == before


# [claude] WAL-LA-20
def test_wal_la_20__the_row_is_flushed_not_committed_visible_in_the_session_gone_after_a(db, w1, u1, monkeypatch):
    """WAL-LA-20 — the row is flushed, not committed: visible in the session, gone after a rollback.
    Rules: `log_action` R1, Side effects"""
    count_sql = text("SELECT count(*) FROM workspace_audit_logs WHERE workspace_id = :w AND action = :a")
    spy = MagicMock(wraps=db.commit)
    monkeypatch.setattr(db, "commit", spy)
    sp = db.begin_nested()

    result = dao.log_action(db, workspace_id=w1.id, user_id=u1.id, action="spy")

    # Then 1
    assert result.id is not None
    # Then 2
    assert db.execute(count_sql, {"w": w1.id, "a": "spy"}).scalar() == 1
    # Then 3
    sp.rollback()
    assert db.execute(count_sql, {"w": w1.id, "a": "spy"}).scalar() == 0
    # Then 4
    spy.assert_not_called()


# [claude] WAL-LA-21
def test_wal_la_21__one_insert_and_nothing_else_no_existence_check_of_workspace_or_user(db, w1, u1):
    """WAL-LA-21 — one INSERT and nothing else: no existence check of workspace or user.
    Rules: `log_action` R6"""
    with StatementRecorder(db) as recorder:
        result = dao.log_action(db, workspace_id=w1.id, user_id=u1.id, action="rec")
    written = recorder.written()
    selects = recorder.selects()

    # Then 1
    assert result.id is not None
    # Then 2
    assert len(written) == 1
    # Then 3
    assert "INSERT INTO workspace_audit_logs" in written[0]
    # Then 4
    assert not any("FROM workspaces" in s for s in selects)
    # Then 5
    assert not any("FROM profiles" in s for s in selects)


# [claude] WAL-LA-22
def test_wal_la_22__leaving_out_workspace_id_raises_typeerror(db, u1):
    """WAL-LA-22 — leaving out workspace_id raises TypeError.
    Rules: `log_action` R7, Errors row 4"""
    before = stored_count(db)

    # Then 1
    with pytest.raises(TypeError):
        dao.log_action(db, user_id=u1.id, action="x")
    # Then 2
    assert stored_count(db) == before


# [claude] WAL-LA-23
def test_wal_la_23__leaving_out_user_id_raises_typeerror(db, w1):
    """WAL-LA-23 — leaving out user_id raises TypeError.
    Rules: `log_action` R7, Errors row 4"""
    before = stored_count(db)

    # Then 1
    with pytest.raises(TypeError):
        dao.log_action(db, workspace_id=w1.id, action="x")
    # Then 2
    assert stored_count(db) == before
