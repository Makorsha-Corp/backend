"""Unit tests for app/dao/mobile_upload_session.py.

Implements tests/unit/dao/mobile_upload_session.cases.md, one test per case, in
card order. Real Postgres session (`db` fixture).
Only `app.dao.mobile_upload_session.utcnow` is patched, around the When of the cards whose Given says so (Conventions, Externals).

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: DTZ001  (naive datetimes)
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect

from app.dao.mobile_upload_session import _naive_utc, mobile_upload_session_dao
from app.models.mobile_upload_session import MobileUploadSession
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton mobile_upload_session_dao" (a module-level name, not a fixture)
dao = mobile_upload_session_dao

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999

# Convention "NOW, NOW_UTC, PAST, LATER"
NOW = datetime(2026, 3, 5, 12, 0, 0)
NOW_UTC = datetime(2026, 3, 5, 12, 0, 0, tzinfo=timezone.utc)
PAST = datetime(2026, 3, 4, 12, 0, 0, tzinfo=timezone.utc)
LATER = datetime(2026, 3, 6, 12, 0, 0, tzinfo=timezone.utc)

# Convention "US, P6, M5, TK1, TK2"
US = timedelta(microseconds=1)
P6 = timezone(timedelta(hours=6))
M5 = timezone(timedelta(hours=-5))
TK1 = "a" * 64
TK2 = "b" * 64


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
def u2(db, u1):
    return make_profile(db)


# Convention "These rows exist in every test and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2, u1, u2):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builders (fixtures; each flushes before it returns)
# --------------------------------------------------------------------------- #

# Convention "session": the columns the Conventions say are not passed stay out of the constructor
@pytest.fixture
def mk_session(db, w1, u1):
    """mk_session(**columns) -> MobileUploadSession. Keywords only."""
    def _mk(**columns):
        fields = {"workspace_id": w1.id, "created_by": u1.id, "entity_type": "purchase_order", "entity_id": 1, "token_hash": TK1, "expires_at": LATER}
        fields.update(columns)
        return _add(db, MobileUploadSession(**fields))
    return _mk


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (plain functions; no expected values inside)
# --------------------------------------------------------------------------- #

# Convention "unchanged(X)": every column of X, straight from the table
def snap(db, row):
    """Dict column -> database value of `row`, or None if it is gone."""
    table = type(row).__table__
    found = db.execute(select(table).where(table.c.id == sa_inspect(row).identity[0])).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "nothing written": the number of mobile_upload_sessions rows stored (all workspaces)
def stored_count(db):
    return db.execute(select(func.count()).select_from(MobileUploadSession.__table__)).scalar_one()


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
        """The one SELECT from mobile_upload_sessions; fails loudly unless there is exactly one."""
        [statement] = [s for s in self.selects() if "mobile_upload_sessions" in s]
        return statement


# Convention "where": the text of `sql` after its WHERE
def where_part_of(sql):
    return sql.split("WHERE", 1)[1]


# --------------------------------------------------------------------------- #
# _naive_utc
# --------------------------------------------------------------------------- #


# [claude] MUS-N-01
def test_mus_n_01__a_naive_value_comes_back_unchanged():
    """MUS-N-01 — a naive value comes back unchanged.
    Rules: `_naive_utc` R1, Returns"""
    result = _naive_utc(datetime(2026, 1, 1, 0, 0, 0))

    # Then 1
    assert result == datetime(2026, 1, 1, 0, 0, 0)
    # Then 2
    assert result.tzinfo is None


# [claude] MUS-N-02
def test_mus_n_02__a_00_00_value_keeps_its_clock_time_and_loses_its_zone():
    """MUS-N-02 — a +00:00 value keeps its clock time and loses its zone.
    Rules: `_naive_utc` R2"""
    result = _naive_utc(datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc))

    # Then 1
    assert result == datetime(2026, 1, 1, 0, 0, 0)
    # Then 2
    assert result.tzinfo is None


# [claude] MUS-N-03
@pytest.mark.xfail(strict=True, reason="BUG-1282: Mobile upload expiry depends on the database's time-zone setting")
def test_mus_n_03__a_06_00_value_is_converted_to_utc():
    """MUS-N-03 — a +06:00 value is converted to UTC.
    Rules: `_naive_utc` R2 [BUG-1282]"""
    result = _naive_utc(datetime(2026, 1, 1, 0, 0, 0, tzinfo=P6))

    # Then 1
    assert result.tzinfo is None
    # Then 2
    assert result == datetime(2025, 12, 31, 18, 0, 0)


# [claude] MUS-N-04
@pytest.mark.xfail(strict=True, reason="BUG-1282: Mobile upload expiry depends on the database's time-zone setting")
def test_mus_n_04__a_05_00_value_is_converted_to_utc():
    """MUS-N-04 — a -05:00 value is converted to UTC.
    Rules: `_naive_utc` R2 [BUG-1282]"""
    result = _naive_utc(datetime(2026, 1, 1, 8, 0, 0, tzinfo=M5))

    # Then 1
    assert result.tzinfo is None
    # Then 2
    assert result == datetime(2026, 1, 1, 13, 0, 0)


# --------------------------------------------------------------------------- #
# MobileUploadSessionDAO.get_by_token_hash
# --------------------------------------------------------------------------- #


# [claude] MUS-T-01
def test_mus_t_01__returns_the_row_with_exactly_that_hash_not_the_first_row(db, mk_session):
    """MUS-T-01 — returns the row with exactly that hash, not the first row.
    Rules: `get_by_token_hash` R1, Returns"""
    mk_session()
    b = mk_session(token_hash=TK2)

    result = dao.get_by_token_hash(db, token_hash=TK2)

    # Then 1
    assert result.id == b.id
    # Then 2
    assert isinstance(result, MobileUploadSession)


# [claude] MUS-T-02
def test_mus_t_02__a_session_of_another_workspace_is_returned_no_workspace_filter_by_desi(db, w2, mk_session):
    """MUS-T-02 — a session of another workspace is returned: no workspace filter, by design.
    Rules: `get_by_token_hash` R1"""
    a = mk_session(workspace_id=w2.id)

    result = dao.get_by_token_hash(db, token_hash=TK1)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.workspace_id == w2.id


# [claude] MUS-T-03
def test_mus_t_03__an_unknown_hash_returns_none_and_nothing_is_created(db, mk_session):
    """MUS-T-03 — an unknown hash returns None and nothing is created.
    Rules: `get_by_token_hash` R2"""
    mk_session()
    before = stored_count(db)

    result = dao.get_by_token_hash(db, token_hash=TK2)

    # Then 1
    assert result is None
    # Then 2
    assert stored_count(db) == before


# [claude] MUS-T-04
def test_mus_t_04__an_empty_hash_returns_none(db, mk_session):
    """MUS-T-04 — an empty hash returns None.
    Rules: `get_by_token_hash` R2"""
    mk_session()

    result = dao.get_by_token_hash(db, token_hash="")

    # Then 1
    assert result is None


# [claude] MUS-T-05
def test_mus_t_05__the_hash_in_another_case_returns_none(db, mk_session):
    """MUS-T-05 — the hash in another case returns None.
    Rules: `get_by_token_hash` R2"""
    mk_session()

    result = dao.get_by_token_hash(db, token_hash=TK1.upper())

    # Then 1
    assert result is None


# [claude] MUS-T-06
def test_mus_t_06__a_cancelled_session_past_its_time_is_returned(db, mk_session):
    """MUS-T-06 — a cancelled session past its time is returned.
    Rules: `get_by_token_hash` R3"""
    a = mk_session(status="cancelled", expires_at=PAST)

    result = dao.get_by_token_hash(db, token_hash=TK1)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.status == "cancelled"


# [claude] MUS-T-07
def test_mus_t_07__an_expired_session_is_returned(db, mk_session):
    """MUS-T-07 — an expired session is returned.
    Rules: `get_by_token_hash` R3"""
    a = mk_session(status="expired", expires_at=PAST)

    result = dao.get_by_token_hash(db, token_hash=TK1)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.status == "expired"


# [claude] MUS-T-08
def test_mus_t_08__a_waiting_session_past_its_time_is_returned_still_waiting(db, mk_session):
    """MUS-T-08 — a waiting session past its time is returned, still waiting.
    Rules: `get_by_token_hash` R3"""
    a = mk_session(expires_at=PAST)

    result = dao.get_by_token_hash(db, token_hash=TK1)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.status == "waiting"


# [claude] MUS-T-09
def test_mus_t_09__writes_nothing_a_read_that_finds_its_session_leaves_the_session_object(db, w1, u1, mk_session):
    """MUS-T-09 — writes nothing: a read that finds its session leaves the session object as it was.
    Rules: `get_by_token_hash` Side effects"""
    a = mk_session()
    p = MobileUploadSession(workspace_id=w1.id, created_by=u1.id, entity_type="purchase_order", entity_id=1, token_hash=TK2, expires_at=LATER)
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_token_hash(db, token_hash=TK1)
    written = recorder.written()
    selects = recorder.selects()
    sql = recorder.sql()
    where = where_part_of(sql)

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
    assert stored_count(db) == before
    # Then 11
    db.expire_all()
    assert snap(db, a) == before_a
    # Then 12
    assert "status" not in where
    # Then 13
    assert "expires_at" not in where


# [claude] MUS-T-10
def test_mus_t_10__token_hash_a_63_returns_none_the_compare_is_exact(db, mk_session):
    """MUS-T-10 — token_hash="a" * 63 returns None: the compare is exact.
    Rules: `get_by_token_hash` R2"""
    mk_session()

    result = dao.get_by_token_hash(db, token_hash="a" * 63)

    # Then 1
    assert result is None


# [claude] MUS-T-11
def test_mus_t_11__token_hash_a_64_returns_none_the_compare_is_exact(db, mk_session):
    """MUS-T-11 — token_hash=" " + "a" * 64 returns None: the compare is exact.
    Rules: `get_by_token_hash` R2"""
    mk_session()

    result = dao.get_by_token_hash(db, token_hash=" " + "a" * 64)

    # Then 1
    assert result is None


# [claude] MUS-T-12
def test_mus_t_12__token_hash_a_64_returns_none_the_compare_is_exact(db, mk_session):
    """MUS-T-12 — token_hash="a" * 64 + " " returns None: the compare is exact.
    Rules: `get_by_token_hash` R2"""
    mk_session()

    result = dao.get_by_token_hash(db, token_hash="a" * 64 + " ")

    # Then 1
    assert result is None


# [claude] MUS-T-13
def test_mus_t_13__token_hash_a_returns_none_the_compare_is_exact(db, mk_session):
    """MUS-T-13 — token_hash="a%" returns None: the compare is exact.
    Rules: `get_by_token_hash` R2"""
    mk_session()

    result = dao.get_by_token_hash(db, token_hash="a%")

    # Then 1
    assert result is None


# [claude] MUS-T-14
def test_mus_t_14__token_hash_a_63_returns_none_the_compare_is_exact(db, mk_session):
    """MUS-T-14 — token_hash="a" * 63 + "_" returns None: the compare is exact.
    Rules: `get_by_token_hash` R2"""
    mk_session()

    result = dao.get_by_token_hash(db, token_hash="a" * 63 + "_")

    # Then 1
    assert result is None


# [claude] MUS-T-15
def test_mus_t_15__a_stored_hash_a_64_is_not_found_by_a_64(db, mk_session):
    """MUS-T-15 — a stored hash "A" * 64 is not found by "a" * 64.
    Rules: `get_by_token_hash` R2"""
    mk_session(token_hash="A" * 64)

    result = dao.get_by_token_hash(db, token_hash="a" * 64)

    # Then 1
    assert result is None


# [claude] MUS-T-16
def test_mus_t_16__a_stored_hash_a_63_is_not_found_by_a_63(db, mk_session):
    """MUS-T-16 — a stored hash " " + "a" * 63 is not found by "a" * 63.
    Rules: `get_by_token_hash` R2"""
    mk_session(token_hash=" " + "a" * 63)

    result = dao.get_by_token_hash(db, token_hash="a" * 63)

    # Then 1
    assert result is None


# [claude] MUS-T-17
def test_mus_t_17__a_stored_hash_a_63_is_not_found_by_a_63(db, mk_session):
    """MUS-T-17 — a stored hash "a" * 63 + " " is not found by "a" * 63.
    Rules: `get_by_token_hash` R2"""
    mk_session(token_hash="a" * 63 + " ")

    result = dao.get_by_token_hash(db, token_hash="a" * 63)

    # Then 1
    assert result is None


# [claude] MUS-T-18
def test_mus_t_18__a_stored_hash_xy_a_62_is_not_found_by_a_62(db, mk_session):
    """MUS-T-18 — a stored hash "xy" + "a" * 62 is not found by "a" * 62.
    Rules: `get_by_token_hash` R2"""
    mk_session(token_hash="xy" + "a" * 62)

    result = dao.get_by_token_hash(db, token_hash="a" * 62)

    # Then 1
    assert result is None


# [claude] MUS-T-19
def test_mus_t_19__writes_nothing_an_unflushed_edit_of_another_row_stays_unflushed_and_is(db, mk_session):
    """MUS-T-19 — writes nothing: an unflushed edit of another row stays unflushed and is not reloaded.
    Rules: `get_by_token_hash` Side effects"""
    a = mk_session()
    b = mk_session(token_hash=TK2)
    b.status = "cancelled"

    result = dao.get_by_token_hash(db, token_hash=TK1)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert b.status == "cancelled"


# --------------------------------------------------------------------------- #
# MobileUploadSessionDAO.get_for_creator
# --------------------------------------------------------------------------- #


# [claude] MUS-C-01
def test_mus_c_01__returns_the_row_matching_id_workspace_and_creator_not_the_first_row(db, w1, u1, mk_session):
    """MUS-C-01 — returns the row matching id, workspace and creator, not the first row.
    Rules: `get_for_creator` R1, Returns"""
    mk_session()
    b = mk_session(token_hash=TK2)

    result = dao.get_for_creator(db, session_id=b.id, workspace_id=w1.id, created_by=u1.id)

    # Then 1
    assert result.id == b.id
    # Then 2
    assert isinstance(result, MobileUploadSession)


# [claude] MUS-C-02
def test_mus_c_02__another_workspace_returns_none(db, w2, u1, mk_session):
    """MUS-C-02 — another workspace returns None.
    Rules: `get_for_creator` R2"""
    a = mk_session()

    result = dao.get_for_creator(db, session_id=a.id, workspace_id=w2.id, created_by=u1.id)

    # Then 1
    assert result is None


# [claude] MUS-C-03
def test_mus_c_03__another_user_of_the_same_workspace_returns_none(db, w1, u2, mk_session):
    """MUS-C-03 — another user of the same workspace returns None.
    Rules: `get_for_creator` R2"""
    a = mk_session()

    result = dao.get_for_creator(db, session_id=a.id, workspace_id=w1.id, created_by=u2.id)

    # Then 1
    assert result is None


# [claude] MUS-C-04
def test_mus_c_04__an_unknown_id_returns_none_and_nothing_is_created(db, w1, u1, mk_session):
    """MUS-C-04 — an unknown id returns None and nothing is created.
    Rules: `get_for_creator` R2"""
    mk_session()
    before = stored_count(db)

    result = dao.get_for_creator(db, session_id=MISSING, workspace_id=w1.id, created_by=u1.id)

    # Then 1
    assert result is None
    # Then 2
    assert stored_count(db) == before


# [claude] MUS-C-05
def test_mus_c_05__a_cancelled_session_past_its_time_is_returned(db, w1, u1, mk_session):
    """MUS-C-05 — a cancelled session past its time is returned.
    Rules: `get_for_creator` R3"""
    a = mk_session(status="cancelled", expires_at=PAST)

    result = dao.get_for_creator(db, session_id=a.id, workspace_id=w1.id, created_by=u1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.status == "cancelled"


# [claude] MUS-C-06
def test_mus_c_06__a_waiting_session_past_its_time_is_returned_still_waiting(db, w1, u1, mk_session):
    """MUS-C-06 — a waiting session past its time is returned, still waiting.
    Rules: `get_for_creator` R3"""
    a = mk_session(expires_at=PAST)

    result = dao.get_for_creator(db, session_id=a.id, workspace_id=w1.id, created_by=u1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.status == "waiting"


# [claude] MUS-C-07
def test_mus_c_07__writes_nothing_a_read_that_finds_its_session_leaves_the_session_object(db, w1, u1, mk_session):
    """MUS-C-07 — writes nothing: a read that finds its session leaves the session object as it was.
    Rules: `get_for_creator` Side effects"""
    a = mk_session()
    p = MobileUploadSession(workspace_id=w1.id, created_by=u1.id, entity_type="purchase_order", entity_id=1, token_hash=TK2, expires_at=LATER)
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    with StatementRecorder(db) as recorder:
        result = dao.get_for_creator(db, session_id=a.id, workspace_id=w1.id, created_by=u1.id)
    written = recorder.written()
    selects = recorder.selects()
    sql = recorder.sql()
    where = where_part_of(sql)

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
    assert stored_count(db) == before
    # Then 11
    db.expire_all()
    assert snap(db, a) == before_a
    # Then 12
    assert "status" not in where
    # Then 13
    assert "expires_at" not in where


# [claude] MUS-C-08
def test_mus_c_08__a_w2_session_at_the_earlier_id_is_not_returned_for_w1(db, w1, w2, u1, mk_session):
    """MUS-C-08 — a W2 session at the earlier id is not returned for W1.
    Rules: `get_for_creator` R2, R1"""
    z = mk_session(workspace_id=w2.id)
    mk_session(token_hash=TK2)

    result = dao.get_for_creator(db, session_id=z.id, workspace_id=w1.id, created_by=u1.id)

    # Then 1
    assert result is None


# [claude] MUS-C-09
def test_mus_c_09__another_user_s_session_at_the_earlier_id_is_not_returned(db, w1, u1, u2, mk_session):
    """MUS-C-09 — another user's session at the earlier id is not returned.
    Rules: `get_for_creator` R2, R1"""
    z = mk_session(created_by=u2.id)
    mk_session(token_hash=TK2)

    result = dao.get_for_creator(db, session_id=z.id, workspace_id=w1.id, created_by=u1.id)

    # Then 1
    assert result is None


# [claude] MUS-C-10
def test_mus_c_10__writes_nothing_an_unflushed_edit_of_another_row_stays_unflushed_and_is(db, w1, u1, mk_session):
    """MUS-C-10 — writes nothing: an unflushed edit of another row stays unflushed and is not reloaded.
    Rules: `get_for_creator` Side effects"""
    a = mk_session()
    b = mk_session(token_hash=TK2)
    b.status = "cancelled"

    result = dao.get_for_creator(db, session_id=a.id, workspace_id=w1.id, created_by=u1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert b.status == "cancelled"


# --------------------------------------------------------------------------- #
# MobileUploadSessionDAO.mark_expired_if_needed
# --------------------------------------------------------------------------- #


# [claude] MUS-M-01
def test_mus_m_01__a_waiting_session_past_its_time_becomes_expired_on_the_same_instance():
    """MUS-M-01 — a waiting session past its time becomes expired, on the same instance.
    Rules: `mark_expired_if_needed` R1, Returns, Side effects"""
    s = MobileUploadSession(status="waiting", expires_at=NOW - timedelta(minutes=1))

    with patch("app.dao.mobile_upload_session.utcnow", return_value=NOW):
        result = dao.mark_expired_if_needed(s)

    # Then 1
    assert result is s
    # Then 2
    assert s.status == "expired"
    # Then 3
    assert s.expires_at == NOW - timedelta(minutes=1)


# [claude] MUS-M-02
def test_mus_m_02__expires_at_exactly_now_becomes_expired():
    """MUS-M-02 — expires_at exactly now becomes expired.
    Rules: `mark_expired_if_needed` R2"""
    s = MobileUploadSession(status="waiting", expires_at=NOW)

    with patch("app.dao.mobile_upload_session.utcnow", return_value=NOW):
        result = dao.mark_expired_if_needed(s)

    # Then 1
    assert result is s
    # Then 2
    assert s.status == "expired"


# [claude] MUS-M-03
def test_mus_m_03__expires_at_one_microsecond_later_stays_waiting():
    """MUS-M-03 — expires_at one microsecond later stays waiting.
    Rules: `mark_expired_if_needed` R2"""
    s = MobileUploadSession(status="waiting", expires_at=NOW + US)

    with patch("app.dao.mobile_upload_session.utcnow", return_value=NOW):
        result = dao.mark_expired_if_needed(s)

    # Then 1
    assert result is s
    # Then 2
    assert s.status == "waiting"


# [claude] MUS-M-04
def test_mus_m_04__an_uploaded_session_far_past_its_time_is_left_as_it_is():
    """MUS-M-04 — an uploaded session far past its time is left as it is.
    Rules: `mark_expired_if_needed` R3"""
    s = MobileUploadSession(status="uploaded", expires_at=NOW - timedelta(days=30))

    with patch("app.dao.mobile_upload_session.utcnow", return_value=NOW):
        result = dao.mark_expired_if_needed(s)

    # Then 1
    assert result is s
    # Then 2
    assert s.status == "uploaded"


# [claude] MUS-M-05
def test_mus_m_05__a_consumed_session_far_past_its_time_is_left_as_it_is():
    """MUS-M-05 — a consumed session far past its time is left as it is.
    Rules: `mark_expired_if_needed` R3"""
    s = MobileUploadSession(status="consumed", expires_at=NOW - timedelta(days=30))

    with patch("app.dao.mobile_upload_session.utcnow", return_value=NOW):
        result = dao.mark_expired_if_needed(s)

    # Then 1
    assert result is s
    # Then 2
    assert s.status == "consumed"


# [claude] MUS-M-06
def test_mus_m_06__a_cancelled_session_far_past_its_time_is_left_as_it_is():
    """MUS-M-06 — a cancelled session far past its time is left as it is.
    Rules: `mark_expired_if_needed` R3"""
    s = MobileUploadSession(status="cancelled", expires_at=NOW - timedelta(days=30))

    with patch("app.dao.mobile_upload_session.utcnow", return_value=NOW):
        result = dao.mark_expired_if_needed(s)

    # Then 1
    assert result is s
    # Then 2
    assert s.status == "cancelled"


# [claude] MUS-M-07
def test_mus_m_07__an_expired_session_far_past_its_time_is_left_as_it_is():
    """MUS-M-07 — an expired session far past its time is left as it is.
    Rules: `mark_expired_if_needed` R3"""
    s = MobileUploadSession(status="expired", expires_at=NOW - timedelta(days=30))

    with patch("app.dao.mobile_upload_session.utcnow", return_value=NOW):
        result = dao.mark_expired_if_needed(s)

    # Then 1
    assert result is s
    # Then 2
    assert s.status == "expired"


# [claude] MUS-M-08
def test_mus_m_08__nothing_is_written_the_row_is_dirty_in_the_session_and_a_query_still_r(db, mk_session):
    """MUS-M-08 — nothing is written: the row is dirty in the session, and a query still reads waiting.
    Rules: `mark_expired_if_needed` R4, Side effects"""
    db.execute(text("SET LOCAL TIME ZONE 'UTC'"))
    s = mk_session(expires_at=PAST)

    with patch("app.dao.mobile_upload_session.utcnow", return_value=NOW), StatementRecorder(db) as recorder:
        result = dao.mark_expired_if_needed(s)
    written = recorder.written()

    # Then 1
    assert result is s
    # Then 2
    assert s.status == "expired"
    # Then 3
    assert s in db.dirty
    # Then 4
    assert written == []
    # Then 5
    assert db.scalar(text("SELECT status FROM mobile_upload_sessions WHERE id = :i"), {"i": s.id}) == "waiting"


# [claude] MUS-M-09
def test_mus_m_09__a_naive_value_past_its_time_becomes_expired():
    """MUS-M-09 — a naive value past its time becomes expired.
    Rules: `mark_expired_if_needed` R5"""
    s = MobileUploadSession(status="waiting", expires_at=datetime(2026, 3, 5, 11, 59, 59))

    with patch("app.dao.mobile_upload_session.utcnow", return_value=NOW):
        result = dao.mark_expired_if_needed(s)

    # Then 1
    assert result is s
    # Then 2
    assert s.status == "expired"


# [claude] MUS-M-10
def test_mus_m_10__a_naive_value_later_than_now_stays_waiting():
    """MUS-M-10 — a naive value later than now stays waiting.
    Rules: `mark_expired_if_needed` R5"""
    s = MobileUploadSession(status="waiting", expires_at=datetime(2026, 3, 5, 12, 0, 1))

    with patch("app.dao.mobile_upload_session.utcnow", return_value=NOW):
        result = dao.mark_expired_if_needed(s)

    # Then 1
    assert result is s
    # Then 2
    assert s.status == "waiting"


# [claude] MUS-M-11
def test_mus_m_11__a_utc_value_exactly_now_becomes_expired():
    """MUS-M-11 — a UTC value exactly now becomes expired.
    Rules: `mark_expired_if_needed` R5"""
    s = MobileUploadSession(status="waiting", expires_at=datetime(2026, 3, 5, 12, 0, 0, tzinfo=timezone.utc))

    with patch("app.dao.mobile_upload_session.utcnow", return_value=NOW):
        result = dao.mark_expired_if_needed(s)

    # Then 1
    assert result is s
    # Then 2
    assert s.status == "expired"


# [claude] MUS-M-12
def test_mus_m_12__a_utc_value_one_microsecond_later_stays_waiting():
    """MUS-M-12 — a UTC value one microsecond later stays waiting.
    Rules: `mark_expired_if_needed` R5"""
    s = MobileUploadSession(status="waiting", expires_at=datetime(2026, 3, 5, 12, 0, 0, 1, tzinfo=timezone.utc))

    with patch("app.dao.mobile_upload_session.utcnow", return_value=NOW):
        result = dao.mark_expired_if_needed(s)

    # Then 1
    assert result is s
    # Then 2
    assert s.status == "waiting"


# [claude] MUS-M-13
@pytest.mark.xfail(strict=True, reason="BUG-1282: Mobile upload expiry depends on the database's time-zone setting")
def test_mus_m_13__a_06_00_value_past_its_true_moment_becomes_expired():
    """MUS-M-13 — a +06:00 value past its true moment becomes expired.
    Rules: `mark_expired_if_needed` R5a [BUG-1282]"""
    s = MobileUploadSession(status="waiting", expires_at=datetime(2026, 3, 5, 17, 59, 59, tzinfo=P6))

    with patch("app.dao.mobile_upload_session.utcnow", return_value=NOW):
        result = dao.mark_expired_if_needed(s)

    # Then 1
    assert result is s
    # Then 2
    assert s.status == "expired"


# [claude] MUS-M-14
@pytest.mark.xfail(strict=True, reason="BUG-1282: Mobile upload expiry depends on the database's time-zone setting")
def test_mus_m_14__a_05_00_value_before_its_true_moment_stays_waiting():
    """MUS-M-14 — a -05:00 value before its true moment stays waiting.
    Rules: `mark_expired_if_needed` R5a [BUG-1282]"""
    s = MobileUploadSession(status="waiting", expires_at=datetime(2026, 3, 5, 8, 0, 0, tzinfo=M5))

    with patch("app.dao.mobile_upload_session.utcnow", return_value=NOW):
        result = dao.mark_expired_if_needed(s)

    # Then 1
    assert result is s
    # Then 2
    assert s.status == "waiting"


# [claude] MUS-M-15
def test_mus_m_15__a_row_read_back_under_utc_compares_by_its_true_moment(db, mk_session):
    """MUS-M-15 — a row read back under UTC compares by its true moment.
    Rules: `mark_expired_if_needed` R5"""
    db.execute(text("SET LOCAL TIME ZONE 'UTC'"))
    s = mk_session(expires_at=NOW_UTC - timedelta(seconds=1))
    db.expire_all()

    with patch("app.dao.mobile_upload_session.utcnow", return_value=NOW):
        result = dao.mark_expired_if_needed(s)

    # Then 1
    assert result is s
    # Then 2
    assert s.status == "expired"


# [claude] MUS-M-16
@pytest.mark.xfail(strict=True, reason="BUG-1282: Mobile upload expiry depends on the database's time-zone setting")
def test_mus_m_16__a_row_read_back_under_asia_dhaka_past_its_true_moment_becomes_expired(db, mk_session):
    """MUS-M-16 — a row read back under Asia/Dhaka past its true moment becomes expired.
    Rules: `mark_expired_if_needed` R5a [BUG-1282]"""
    db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))
    s = mk_session(expires_at=NOW_UTC - timedelta(seconds=1))
    db.expire_all()

    with patch("app.dao.mobile_upload_session.utcnow", return_value=NOW):
        result = dao.mark_expired_if_needed(s)

    # Then 1
    assert result is s
    # Then 2
    assert s.status == "expired"


# [claude] MUS-M-17
@pytest.mark.xfail(strict=True, reason="BUG-1282: Mobile upload expiry depends on the database's time-zone setting")
def test_mus_m_17__a_row_read_back_under_america_new_york_before_its_true_moment_stays_wa(db, mk_session):
    """MUS-M-17 — a row read back under America/New_York before its true moment stays waiting.
    Rules: `mark_expired_if_needed` R5a [BUG-1282]"""
    db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))
    s = mk_session(expires_at=NOW_UTC + timedelta(hours=1))
    db.expire_all()

    with patch("app.dao.mobile_upload_session.utcnow", return_value=NOW):
        result = dao.mark_expired_if_needed(s)

    # Then 1
    assert result is s
    # Then 2
    assert s.status == "waiting"


# [claude] MUS-M-18
def test_mus_m_18__only_the_status_changes_a_pending_row_of_the_caller_is_left_alone(db, w1, u1, mk_session):
    """MUS-M-18 — only the status changes: a pending row of the caller is left alone.
    Rules: `mark_expired_if_needed` R4, Side effects"""
    db.execute(text("SET LOCAL TIME ZONE 'UTC'"))
    a = mk_session(expires_at=PAST)
    p = MobileUploadSession(workspace_id=w1.id, created_by=u1.id, entity_type="purchase_order", entity_id=1, token_hash=TK2, expires_at=LATER)
    db.add(p)

    with patch("app.dao.mobile_upload_session.utcnow", return_value=NOW):
        result = dao.mark_expired_if_needed(a)

    # Then 1
    assert result is a
    # Then 2
    assert a.status == "expired"
    # Then 3
    assert p in db.new
    # Then 4
    assert p.id is None
    # Then 5
    assert len(db.new) == 1
