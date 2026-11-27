"""Unit tests for app/dao/attachment_markup_event.py.

Implements tests/unit/dao/attachment_markup_event.cases.md, one test per case,
in card order. Real Postgres session (`db` fixture). Nothing is mocked
(Conventions, Externals: None): the `created_at` default is bound at import
and checked against the database's real clock by tolerance only.

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117, DTZ001  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`, and naive datetimes)
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import DataError, IntegrityError

from app.dao.attachment_markup_event import attachment_markup_event_dao
from app.models.attachment import Attachment
from app.models.attachment_markup_event import AttachmentMarkupEvent
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton attachment_markup_event_dao"
dao = attachment_markup_event_dao

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999

# Convention "T10, T11, T12" (naive)
T10 = datetime(2026, 3, 4, 10, 0, 0)
T11 = datetime(2026, 3, 4, 11, 0, 0)
T12 = datetime(2026, 3, 4, 12, 0, 0)


# --------------------------------------------------------------------------- #
# Conventions -> the rows that exist in every test
# (W1, W2, U1, AT1, AT2, ATD; each depends on the one before, so ids rise in
# the order the Conventions list them)
# --------------------------------------------------------------------------- #

def _add(db, row):
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


@pytest.fixture
def u1(db, w2):
    return make_profile(db)


def _attachment_fields(w1, u1, **changes):
    fields = {"workspace_id": w1.id, "file_name": "a1.png", "mime_type": "image/png", "file_size": 100,
              "uploaded_by": u1.id, "upload_status": "ready"}
    fields.update(changes)
    return fields


# Convention "AT1"
@pytest.fixture
def at1(db, w1, u1):
    return _add(db, Attachment(**_attachment_fields(w1, u1)))


# Convention "AT2 = the same, but file_name 'a2.png'"
@pytest.fixture
def at2(db, w1, u1, at1):
    return _add(db, Attachment(**_attachment_fields(w1, u1, file_name="a2.png")))


# Convention "ATD = the same as AT1, but file_name 'gone.png', is_deleted True, deleted_by U1.id"
@pytest.fixture
def atd(db, w1, u1, at2):
    return _add(db, Attachment(**_attachment_fields(w1, u1, file_name="gone.png", is_deleted=True, deleted_by=u1.id)))


# Convention "they exist in every test and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2, u1, at1, at2, atd):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builders and Given steps
# --------------------------------------------------------------------------- #

def _entry_fields(w1, u1, at1, created_at, columns):
    fields = {"workspace_id": w1.id, "attachment_id": at1.id, "user_id": u1.id, "event_type": "markup_saved",
              "description": "Saved", "created_at": created_at}
    fields.update(columns)
    return fields


# Convention "entry": the card always gives created_at
@pytest.fixture
def mk_entry(db, w1, u1, at1):
    """mk_entry(created_at=..., **columns) -> AttachmentMarkupEvent, flushed. Keywords only."""
    def _mk(*, created_at, **columns):
        return _add(db, AttachmentMarkupEvent(**_entry_fields(w1, u1, at1, created_at, columns)))
    return _mk


# The "201 entries E1 ... E201, built with add_all and flushed" Given of LA-10, LA-11
@pytest.fixture
def mk_many_entries(db, w1, u1, at1):
    """mk_many_entries(count) -> `newest`: the ids of Ecount, ... E1; Ek at T10 + k minutes."""
    def _mk(count):
        rows = [AttachmentMarkupEvent(**_entry_fields(w1, u1, at1, T10 + timedelta(minutes=k), {}))
                for k in range(1, count + 1)]
        db.add_all(rows)
        db.flush()
        return [row.id for row in reversed(rows)]
    return _mk


# Convention "bumpE(X)"
def bump_e(db, x):
    db.execute(text("UPDATE attachment_markup_events SET description = description || '!' WHERE id = :i"),
               {"i": x.id})
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
    return [r.id for r in result]


# Convention "re-read X": expire, then SELECT by id
def reread(db, row):
    db.expire_all()
    model = type(row)
    return db.execute(select(model).where(model.id == sa_inspect(row).identity[0])).scalar_one_or_none()


# Convention "stored_json(X)"
def stored_json(db, x):
    return db.scalar(text("SELECT metadata_json::text FROM attachment_markup_events WHERE id = :i"), {"i": x.id})


# Convention "is_sql_null(X)"
def is_sql_null(db, x):
    return db.scalar(text("SELECT metadata_json IS NULL FROM attachment_markup_events WHERE id = :i"), {"i": x.id})


# Convention "UTC_CLOCK": read after the call
def utc_clock(db):
    return db.scalar(text("SELECT clock_timestamp() AT TIME ZONE 'UTC'"))


# Convention "nothing written": the number of attachment_markup_events rows stored (all workspaces)
def stored_count(db):
    return db.scalar(select(func.count()).select_from(AttachmentMarkupEvent.__table__))


# "count: attachment_markup_events has N rows with attachment_id == X"
def events_of(db, attachment_id):
    return db.scalar(text("SELECT count(*) FROM attachment_markup_events WHERE attachment_id = :a"),
                     {"a": attachment_id})


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
        """The one SELECT from attachment_markup_events; fails loudly unless there is exactly one."""
        [statement] = [s for s in self.statements
                       if s.lstrip().upper().startswith("SELECT") and "FROM attachment_markup_events" in s]
        return statement


# Convention "order_part": the text of `sql` after its first ORDER BY and before any LIMIT ("" when there is no ORDER BY)
def order_part_of(sql):
    return sql.split("ORDER BY", 1)[1].split("LIMIT", 1)[0] if "ORDER BY" in sql else ""


# --------------------------------------------------------------------------- #
# AttachmentMarkupEventDAO.list_for_attachment
# --------------------------------------------------------------------------- #


# [claude] AME-LA-01
def test_ame_la_01__returns_a_list_of_the_attachment_s_entries_newest_first(db, w1, at1, mk_entry):
    """AME-LA-01 — returns a list of the attachment's entries, newest first.
    Rules: `list_for_attachment` R1, Returns"""
    a = mk_entry(created_at=T10)
    b = mk_entry(created_at=T11)

    result = dao.list_for_attachment(db, workspace_id=w1.id, attachment_id=at1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [b.id, a.id]
    # Then 3
    assert isinstance(result[0], AttachmentMarkupEvent)


# [claude] AME-LA-02
def test_ame_la_02__a_newer_entry_of_another_attachment_is_not_returned(db, w1, at1, at2, mk_entry):
    """AME-LA-02 — a newer entry of another attachment is not returned.
    Rules: `list_for_attachment` R1"""
    a = mk_entry(created_at=T10)
    mk_entry(created_at=T12, attachment_id=at2.id)

    result = dao.list_for_attachment(db, workspace_id=w1.id, attachment_id=at1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] AME-LA-03
def test_ame_la_03__a_newer_entry_under_another_workspace_is_not_returned(db, w1, w2, at1, mk_entry):
    """AME-LA-03 — a newer entry under another workspace is not returned.
    Rules: `list_for_attachment` R2"""
    a = mk_entry(created_at=T10)
    mk_entry(created_at=T12, workspace_id=w2.id)

    result = dao.list_for_attachment(db, workspace_id=w1.id, attachment_id=at1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] AME-LA-04
def test_ame_la_04__an_unknown_attachment_id_returns_an_empty_list(db, w1, mk_entry):
    """AME-LA-04 — an unknown attachment id returns an empty list.
    Rules: `list_for_attachment` R2"""
    mk_entry(created_at=T10)

    result = dao.list_for_attachment(db, workspace_id=w1.id, attachment_id=MISSING)

    # Then 1
    assert result == []


# [claude] AME-LA-05
def test_ame_la_05__attachment_id_0_returns_an_empty_list(db, w1, mk_entry):
    """AME-LA-05 — attachment id 0 returns an empty list.
    Rules: `list_for_attachment` R2"""
    mk_entry(created_at=T10)

    result = dao.list_for_attachment(db, workspace_id=w1.id, attachment_id=0)

    # Then 1
    assert result == []


# [claude] AME-LA-06
def test_ame_la_06__newest_first_whatever_the_ids(db, w1, at1, mk_entry):
    """AME-LA-06 — newest first, whatever the ids.
    Rules: `list_for_attachment` R3"""
    a = mk_entry(created_at=T10)
    b = mk_entry(created_at=T12)
    c = mk_entry(created_at=T11)

    result = dao.list_for_attachment(db, workspace_id=w1.id, attachment_id=at1.id)

    # Then 1
    assert ids(result) == [b.id, c.id, a.id]


# [claude] AME-LA-07
def test_ame_la_07__on_a_tie_both_entries_sit_between_the_newer_and_the_older_one(db, w1, at1, mk_entry):
    """AME-LA-07 — on a tie both entries sit between the newer and the older one.
    Rules: `list_for_attachment` R3"""
    a = mk_entry(created_at=T11)
    b = mk_entry(created_at=T11)
    c = mk_entry(created_at=T12)
    d = mk_entry(created_at=T10)

    result = dao.list_for_attachment(db, workspace_id=w1.id, attachment_id=at1.id)

    # Then 1
    assert len(result) == 4
    # Then 2
    assert result[0].id == c.id
    # Then 3
    assert set(ids(result)[1:3]) == {a.id, b.id}
    # Then 4
    assert result[3].id == d.id


# [claude] AME-LA-08
@pytest.mark.xfail(strict=False, reason="BUG-1436: Markup history entries of one time come back in no fixed order")
def test_ame_la_08__on_a_tie_the_highest_id_comes_first_when_the_lowest_id_was_updated(db, w1, at1, mk_entry):
    """AME-LA-08 — on a tie the highest id comes first, when the lowest id was updated.
    Rules: `list_for_attachment` R3 [BUG-1436]"""
    a = mk_entry(created_at=T11)
    b = mk_entry(created_at=T11)
    c = mk_entry(created_at=T11)
    d = mk_entry(created_at=T12)
    seqscan(db)
    bump_e(db, a)

    result = dao.list_for_attachment(db, workspace_id=w1.id, attachment_id=at1.id)

    # Then 1
    assert len(result) == 4
    # Then 2
    assert ids(result) == [d.id, c.id, b.id, a.id]


# [claude] AME-LA-09
@pytest.mark.xfail(strict=True, reason="BUG-1436: Markup history entries of one time come back in no fixed order")
def test_ame_la_09__the_query_orders_by_created_at_then_id_both_descending(db, w1, at1, mk_entry):
    """AME-LA-09 — the query orders by created_at, then id, both descending.
    Rules: `list_for_attachment` R3 [BUG-1436]"""
    a = mk_entry(created_at=T10)

    with StatementRecorder(db) as recorder:
        result = dao.list_for_attachment(db, workspace_id=w1.id, attachment_id=at1.id)
    order_part = order_part_of(recorder.sql())

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "created_at" in order_part
    # Then 3
    assert ".id" in order_part
    # Then 4
    assert order_part.index("created_at") < order_part.index(".id")
    # Then 5
    assert order_part.upper().count("DESC") == 2


# [claude] AME-LA-10
@pytest.mark.xfail(strict=True, reason="BUG-1437: Markup history silently stops at the 200 newest entries")
def test_ame_la_10__every_entry_is_returned_201_give_201(db, w1, at1, mk_many_entries):
    """AME-LA-10 — every entry is returned: 201 give 201.
    Rules: `list_for_attachment` R4 [BUG-1437]"""
    mk_many_entries(201)

    result = dao.list_for_attachment(db, workspace_id=w1.id, attachment_id=at1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert len(result) == 201


# [claude] AME-LA-11
def test_ame_la_11__of_201_entries_the_first_200_returned_are_the_newest_200_newest_first(db, w1, at1,
                                                                                         mk_many_entries):
    """AME-LA-11 — of 201 entries the first 200 returned are the newest 200, newest first.
    Rules: `list_for_attachment` R4 [BUG-1437]"""
    newest = mk_many_entries(201)

    result = dao.list_for_attachment(db, workspace_id=w1.id, attachment_id=at1.id)

    # Then 1
    assert ids(result)[:200] == newest[:200]


# [claude] AME-LA-12
def test_ame_la_12__the_entries_of_a_soft_deleted_attachment_are_returned(db, w1, atd, mk_entry):
    """AME-LA-12 — the entries of a soft-deleted attachment are returned.
    Rules: `list_for_attachment` R5"""
    a = mk_entry(created_at=T10, attachment_id=atd.id)

    result = dao.list_for_attachment(db, workspace_id=w1.id, attachment_id=atd.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] AME-LA-13
def test_ame_la_13__writes_nothing_a_pending_entry_stays_pending_an_unflushed_edit_stays(db, w1, u1, at1, at2,
                                                                                        mk_entry):
    """AME-LA-13 — writes nothing: a pending entry stays pending, an unflushed edit stays unflushed.
    Rules: `list_for_attachment` Side effects"""
    a = mk_entry(created_at=T10)
    b = mk_entry(created_at=T10, attachment_id=at2.id)
    b.description = "Edited"
    p = AttachmentMarkupEvent(workspace_id=w1.id, attachment_id=at1.id, user_id=u1.id, event_type="markup_saved",
                              description="Pending", created_at=T12)
    db.add(p)
    before = stored_count(db)

    with StatementRecorder(db) as recorder:
        result = dao.list_for_attachment(db, workspace_id=w1.id, attachment_id=at1.id)

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


# [claude] AME-LA-14
def test_ame_la_14__asked_for_w2_only_the_w2_entry_is_returned_though_the_w1_entry_is_earl(db, w2, at1, mk_entry):
    """AME-LA-14 — asked for W2, only the W2 entry is returned, though the W1 entry is earlier.
    Rules: `list_for_attachment` R2"""
    mk_entry(created_at=T11)
    z = mk_entry(created_at=T11, workspace_id=w2.id)

    result = dao.list_for_attachment(db, workspace_id=w2.id, attachment_id=at1.id)

    # Then 1
    assert ids(result) == [z.id]


# --------------------------------------------------------------------------- #
# AttachmentMarkupEventDAO.create_event
# --------------------------------------------------------------------------- #


# [claude] AME-CE-01
def test_ame_ce_01__a_row_is_created_with_the_given_values(db, w1, u1, at1):
    """AME-CE-01 — a row is created with the given values.
    Rules: `create_event` R1, R2, Returns, Side effects"""
    result = dao.create_event(db, workspace_id=w1.id, attachment_id=at1.id, user_id=u1.id,
                              event_type="markup_updated", description="Updated layer", session_id="sess-1",
                              metadata_json={"shapes": 2})

    # Then 1
    assert isinstance(result, AttachmentMarkupEvent)
    # Then 2
    assert result.id is not None
    # Then 3
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.attachment_id == at1.id
    assert row.user_id == u1.id
    # Then 4
    assert row.event_type == "markup_updated"
    assert row.description == "Updated layer"
    assert row.session_id == "sess-1"
    # Then 5
    assert row.metadata_json == {"shapes": 2}
    # Then 6
    assert events_of(db, at1.id) == 1


# [claude] AME-CE-02
def test_ame_ce_02__under_asia_dhaka_created_at_is_the_real_moment_in_utc_naive(db, w1, u1, at1):
    """AME-CE-02 — under Asia/Dhaka created_at is the real moment in UTC, naive.
    Rules: `create_event` R1"""
    db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))

    result = dao.create_event(db, workspace_id=w1.id, attachment_id=at1.id, user_id=u1.id,
                              event_type="markup_saved", description="Saved")

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.created_at.tzinfo is None
    # Then 3
    assert abs(utc_clock(db) - row.created_at) < timedelta(seconds=5)


# [claude] AME-CE-03
def test_ame_ce_03__session_id_and_metadata_json_default_to_none_none_is_stored_as_json_n(db, w1, u1, at1):
    """AME-CE-03 — session_id and metadata_json default to None; None is stored as JSON null.
    Rules: `create_event` R2"""
    result = dao.create_event(db, workspace_id=w1.id, attachment_id=at1.id, user_id=u1.id,
                              event_type="markup_saved", description="Saved")

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.session_id is None
    assert row.metadata_json is None
    # Then 3
    assert stored_json(db, result) == "null"
    # Then 4
    assert is_sql_null(db, result) is False


# [claude] AME-CE-04
def test_ame_ce_04__empty_event_type_and_description_are_stored(db, w1, u1, at1):
    """AME-CE-04 — empty event type and description are stored.
    Rules: `create_event` R3"""
    result = dao.create_event(db, workspace_id=w1.id, attachment_id=at1.id, user_id=u1.id, event_type="",
                              description="")

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.event_type == ""
    assert row.description == ""


# [claude] AME-CE-05
def test_ame_ce_05__a_session_id_of_37_characters_raises_dataerror(db, w1, u1, at1):
    """AME-CE-05 — a session_id of 37 characters raises DataError.
    Rules: `create_event` R3, Errors"""
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.create_event(db, workspace_id=w1.id, attachment_id=at1.id, user_id=u1.id,
                             event_type="markup_saved", description="Saved", session_id="s" * 37)
    assert exc.value.orig.pgcode == "22001"
    # Then 2
    assert stored_count(db) == before


# [claude] AME-CE-06
def test_ame_ce_06__a_session_id_of_36_and_an_event_type_of_32_characters_are_stored(db, w1, u1, at1):
    """AME-CE-06 — a session_id of 36 and an event type of 32 characters are stored.
    Rules: `create_event` R3"""
    result = dao.create_event(db, workspace_id=w1.id, attachment_id=at1.id, user_id=u1.id, event_type="e" * 32,
                              description="Saved", session_id="s" * 36)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.event_type == "e" * 32
    assert row.session_id == "s" * 36


# [claude] AME-CE-07
def test_ame_ce_07__an_event_type_of_33_characters_raises_dataerror(db, w1, u1, at1):
    """AME-CE-07 — an event type of 33 characters raises DataError.
    Rules: `create_event` R3, Errors"""
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.create_event(db, workspace_id=w1.id, attachment_id=at1.id, user_id=u1.id, event_type="e" * 33,
                             description="Saved")
    assert exc.value.orig.pgcode == "22001"
    # Then 2
    assert stored_count(db) == before


# [claude] AME-CE-08
def test_ame_ce_08__description_none_raises_integrityerror_23502(db, w1, u1, at1):
    """AME-CE-08 — description None raises IntegrityError 23502.
    Rules: `create_event` R3, Errors"""
    before = stored_count(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create_event(db, workspace_id=w1.id, attachment_id=at1.id, user_id=u1.id,
                             event_type="markup_saved", description=None)
    assert exc.value.orig.pgcode == "23502"
    # Then 2
    assert stored_count(db) == before


# [claude] AME-CE-09
def test_ame_ce_09__an_unknown_attachment_raises_integrityerror_23503(db, w1, u1):
    """AME-CE-09 — an unknown attachment raises IntegrityError 23503.
    Rules: `create_event` R3, Errors"""
    before = stored_count(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create_event(db, workspace_id=w1.id, attachment_id=MISSING, user_id=u1.id,
                             event_type="markup_saved", description="Saved")
    assert exc.value.orig.pgcode == "23503"
    # Then 2
    assert stored_count(db) == before


# [claude] AME-CE-10
def test_ame_ce_10__an_unknown_user_raises_integrityerror_23503(db, w1, at1):
    """AME-CE-10 — an unknown user raises IntegrityError 23503.
    Rules: `create_event` R3, Errors"""
    before = stored_count(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create_event(db, workspace_id=w1.id, attachment_id=at1.id, user_id=MISSING,
                             event_type="markup_saved", description="Saved")
    assert exc.value.orig.pgcode == "23503"
    # Then 2
    assert stored_count(db) == before


# [claude] AME-CE-11
def test_ame_ce_11__flushed_not_committed_a_rollback_removes_the_row(db, w1, u1, at1):
    """AME-CE-11 — flushed, not committed: a rollback removes the row.
    Rules: `create_event` R4, Side effects"""
    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        result = dao.create_event(db, workspace_id=w1.id, attachment_id=at1.id, user_id=u1.id,
                                  event_type="markup_saved", description="Saved")

    # Then 1
    assert result.id is not None
    # Then 2
    assert events_of(db, at1.id) == 1
    # Then 3
    sp.rollback()
    assert events_of(db, at1.id) == 0
    # Then 4
    assert commit_spy.call_count == 0
