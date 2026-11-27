"""Unit tests for app/dao/attachment.py.

Implements tests/unit/dao/attachment.cases.md, one test per case, in card
order. Real Postgres session (`db` fixture). `SD` cards patch
`app.dao.attachment.utcnow` to NOW (Conventions, Externals); `GA` cards patch
nothing.

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117, DTZ001  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`, and a naive NOW)
from datetime import datetime, timezone
from unittest import mock

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError

from app.dao.attachment import attachment_dao
from app.models.attachment import Attachment
from app.models.attachment_ledger import AttachmentLedger
from app.models.attachment_link import AttachmentLink
from app.models.attachment_markup import AttachmentMarkup
from app.models.attachment_markup_event import AttachmentMarkupEvent
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton attachment_dao"
dao = attachment_dao

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999

# Convention "NOW" (naive) and "T0" (aware UTC)
NOW = datetime(2026, 11, 3, 17, 8)
T0 = datetime(2026, 11, 3, 10, 0, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- #
# Conventions -> the rows that exist in every test
# --------------------------------------------------------------------------- #

def _add(db, row):
    db.add(row)
    db.flush()
    return row


# Convention "W1, W2 = two workspaces rows; U1, U2 = two profiles rows", built in that order
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


# Convention "they exist in every test and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2, u1, u2):
    return None


# Convention "Externals": every SD card patches app.dao.attachment.utcnow to NOW during the When
def frozen_clock():
    return mock.patch("app.dao.attachment.utcnow", return_value=NOW)


# --------------------------------------------------------------------------- #
# Conventions -> row builders (each flushes before it returns)
# --------------------------------------------------------------------------- #

# Convention "attachment"; after "but" the card's columns override the defaults
@pytest.fixture
def mk_attachment(db, w1, u1):
    """mk_attachment(**columns) -> Attachment."""
    def _mk(**columns):
        fields = {"workspace_id": w1.id, "file_name": "file.png", "mime_type": "image/png", "file_size": 100,
                  "uploaded_by": u1.id, "upload_status": "ready"}
        fields.update(columns)
        return _add(db, Attachment(**fields))
    return _mk


# Convention "deleted attachment" = attachment, but is_deleted True, deleted_at T0, deleted_by U1.id
@pytest.fixture
def mk_deleted_attachment(mk_attachment, u1):
    """mk_deleted_attachment(**columns) -> Attachment."""
    def _mk(**columns):
        return mk_attachment(**{"is_deleted": True, "deleted_at": T0, "deleted_by": u1.id, **columns})
    return _mk


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (plain functions; no expected values inside)
# --------------------------------------------------------------------------- #

# Convention "stored_utc(X)": the stored deleted_at moment, in UTC, naive
def stored_utc(db, row):
    return db.scalar(text("SELECT deleted_at AT TIME ZONE 'UTC' FROM attachments WHERE id = :i"), {"i": row.id})


# Convention "re-read X": expire, then SELECT X by id
def reread(db, row):
    db.expire_all()
    model = type(row)
    return db.execute(select(model).where(model.id == sa_inspect(row).identity[0])).scalar_one_or_none()


# Convention "unchanged(X)": every column of X, straight from the table
def snap(db, row):
    """Dict column -> database value of `row`, or None if it is gone."""
    table = type(row).__table__
    found = db.execute(select(table).where(table.c.id == sa_inspect(row).identity[0])).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "nothing written": the number of attachments rows stored (all workspaces) and the number deleted
def stored_count(db):
    table = Attachment.__table__
    return (db.scalar(select(func.count()).select_from(table)),
            db.scalar(select(func.count()).select_from(table).where(table.c.is_deleted.is_(True))))


# Convention "rolled back": a spy that wraps db.commit (still callable, records calls)
def commit_spy(db):
    return mock.patch.object(db, "commit", wraps=db.commit)


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
        """The one SELECT from attachments; fails loudly unless there is exactly one."""
        [statement] = [s for s in self.statements
                       if s.lstrip().upper().startswith("SELECT") and "FROM attachments" in s]
        return statement


# --------------------------------------------------------------------------- #
# AttachmentDAO.get_active
# --------------------------------------------------------------------------- #


# [claude] ATT-GA-01
def test_att_ga_01__a_live_ready_attachment_is_returned_the_instance_the_session_holds(db, w1, mk_attachment):
    """ATT-GA-01 — a live ready attachment is returned, the instance the session holds.
    Rules: `get_active` R1, Returns"""
    mk_attachment(file_name="other.png")
    a = mk_attachment()

    result = dao.get_active(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, Attachment)
    # Then 2
    assert result is a
    # Then 3
    assert result.file_name == "file.png"


# [claude] ATT-GA-02
def test_att_ga_02__a_pending_attachment_counts_as_active(db, w1, mk_attachment):
    """ATT-GA-02 — a pending attachment counts as active.
    Rules: `get_active` R1"""
    a = mk_attachment(upload_status="pending")

    result = dao.get_active(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id


# [claude] ATT-GA-03
def test_att_ga_03__a_failed_attachment_counts_as_active(db, w1, mk_attachment):
    """ATT-GA-03 — a failed attachment counts as active.
    Rules: `get_active` R1"""
    a = mk_attachment(upload_status="failed")

    result = dao.get_active(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id


# [claude] ATT-GA-04
def test_att_ga_04__another_workspace_s_id_returns_none_when_that_row_is_the_earlier_one(db, w1, w2, mk_attachment):
    """ATT-GA-04 — another workspace's id returns None, when that row is the earlier one.
    Rules: `get_active` R2"""
    z = mk_attachment(workspace_id=w2.id)
    mk_attachment()

    result = dao.get_active(db, id=z.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] ATT-GA-05
def test_att_ga_05__another_workspace_s_id_returns_none_when_that_row_is_the_later_one(db, w1, w2, mk_attachment):
    """ATT-GA-05 — another workspace's id returns None, when that row is the later one.
    Rules: `get_active` R2"""
    mk_attachment()
    z = mk_attachment(workspace_id=w2.id)

    result = dao.get_active(db, id=z.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] ATT-GA-06
def test_att_ga_06__the_id_under_another_workspace_returns_none(db, w2, mk_attachment):
    """ATT-GA-06 — the id under another workspace returns None.
    Rules: `get_active` R2"""
    a = mk_attachment()

    result = dao.get_active(db, id=a.id, workspace_id=w2.id)

    # Then 1
    assert result is None


# [claude] ATT-GA-07
def test_att_ga_07__an_unknown_id_returns_none(db, w1, mk_attachment):
    """ATT-GA-07 — an unknown id returns None.
    Rules: `get_active` R3"""
    mk_attachment()

    result = dao.get_active(db, id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] ATT-GA-08
def test_att_ga_08__id_0_returns_none(db, w1, mk_attachment):
    """ATT-GA-08 — id 0 returns None.
    Rules: `get_active` R3"""
    mk_attachment()

    result = dao.get_active(db, id=0, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] ATT-GA-09
def test_att_ga_09__a_soft_deleted_attachment_returns_none(db, w1, mk_deleted_attachment):
    """ATT-GA-09 — a soft-deleted attachment returns None.
    Rules: `get_active` R4"""
    d = mk_deleted_attachment()

    result = dao.get_active(db, id=d.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] ATT-GA-10
def test_att_ga_10__once_is_deleted_is_false_again_the_row_is_returned(db, w1, mk_deleted_attachment):
    """ATT-GA-10 — once is_deleted is False again, the row is returned.
    Rules: `get_active` R4"""
    d = mk_deleted_attachment()
    d.is_deleted = False
    d.deleted_at = None
    d.deleted_by = None
    db.flush()

    result = dao.get_active(db, id=d.id, workspace_id=w1.id)

    # Then 1
    assert result.id == d.id


# [claude] ATT-GA-11
def test_att_ga_11__positional_arguments_work(db, w1, mk_attachment):
    """ATT-GA-11 — positional arguments work.
    Rules: `get_active` R1"""
    a = mk_attachment()

    result = dao.get_active(db, a.id, w1.id)

    # Then 1
    assert result.id == a.id


# [claude] ATT-GA-12
def test_att_ga_12__writes_nothing_a_pending_row_stays_pending_an_unflushed_edit_stays_unflushed(db, w1, u1, mk_attachment):
    """ATT-GA-12 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed.
    Rules: `get_active` Side effects"""
    a = mk_attachment()
    b = mk_attachment(file_name="other.png")
    b.note = "Edited"
    p = Attachment(workspace_id=w1.id, file_name="p.png", mime_type="image/png", file_size=1, uploaded_by=u1.id)
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    with StatementRecorder(db) as recorder:
        result = dao.get_active(db, id=a.id, workspace_id=w1.id)

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
    assert recorder.written() == []
    # Then 8
    assert "FOR UPDATE" not in recorder.sql().upper()
    # Then 9
    assert stored_count(db) == before
    # Then 10
    assert snap(db, a) == before_a


# --------------------------------------------------------------------------- #
# AttachmentDAO.soft_delete
# --------------------------------------------------------------------------- #


# [claude] ATT-SD-01
def test_att_sd_01__under_utc_the_row_is_marked_deleted_at_now_by_the_given_profile_nothing_else_changes(db, w1, u1, u2, mk_attachment):
    """ATT-SD-01 — under UTC the row is marked deleted at NOW by the given profile; nothing else changes.
    Rules: `soft_delete` R1, R2a, Returns, Side effects"""
    db.execute(text("SET LOCAL TIME ZONE 'UTC'"))
    a = mk_attachment(public_id="pid-1", file_url="https://files.example/f.png")

    with frozen_clock():
        result = dao.soft_delete(db, id=a.id, workspace_id=w1.id, deleted_by=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.is_deleted is True
    assert row.deleted_by == u2.id
    # Then 3
    assert stored_utc(db, a) == NOW
    # Then 4
    row = reread(db, a)
    assert row.upload_status == "ready"
    assert row.public_id == "pid-1"
    assert row.file_url == "https://files.example/f.png"
    # Then 5
    assert row.file_name == "file.png"
    assert row.uploaded_by == u1.id
    assert row.workspace_id == w1.id


# [claude] ATT-SD-02
@pytest.mark.xfail(strict=True, reason="BUG-1430: An attachment's delete time depends on the database's time-zone setting")
def test_att_sd_02__under_asia_dhaka_the_stored_moment_is_still_now_in_utc(db, w1, u2, mk_attachment):
    """ATT-SD-02 — under Asia/Dhaka the stored moment is still NOW in UTC.
    Rules: `soft_delete` R2 [BUG-1430]"""
    db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))
    a = mk_attachment()

    with frozen_clock():
        result = dao.soft_delete(db, id=a.id, workspace_id=w1.id, deleted_by=u2.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert reread(db, a).is_deleted is True
    # Then 3
    assert stored_utc(db, a) == NOW


# [claude] ATT-SD-03
def test_att_sd_03__the_row_of_another_workspace_is_not_deleted_when_it_is_the_earlier_one(db, w1, w2, u2, mk_attachment):
    """ATT-SD-03 — the row of another workspace is not deleted, when it is the earlier one.
    Rules: `soft_delete` R3"""
    z = mk_attachment(workspace_id=w2.id)
    a = mk_attachment()
    before_z = snap(db, z)
    before_a = snap(db, a)

    with frozen_clock():
        result = dao.soft_delete(db, id=z.id, workspace_id=w1.id, deleted_by=u2.id)

    # Then 1
    assert result is None
    # Then 2
    db.expire_all()
    assert snap(db, z) == before_z
    # Then 3
    assert snap(db, a) == before_a


# [claude] ATT-SD-04
def test_att_sd_04__the_row_of_another_workspace_is_not_deleted_when_it_is_the_later_one(db, w1, w2, u2, mk_attachment):
    """ATT-SD-04 — the row of another workspace is not deleted, when it is the later one.
    Rules: `soft_delete` R3"""
    mk_attachment()
    z = mk_attachment(workspace_id=w2.id)
    before_z = snap(db, z)

    with frozen_clock():
        result = dao.soft_delete(db, id=z.id, workspace_id=w1.id, deleted_by=u2.id)

    # Then 1
    assert result is None
    # Then 2
    db.expire_all()
    assert snap(db, z) == before_z


# [claude] ATT-SD-05
def test_att_sd_05__the_id_under_another_workspace_deletes_nothing(db, w2, u2, mk_attachment):
    """ATT-SD-05 — the id under another workspace deletes nothing.
    Rules: `soft_delete` R3"""
    a = mk_attachment()
    before_a = snap(db, a)

    with frozen_clock():
        result = dao.soft_delete(db, id=a.id, workspace_id=w2.id, deleted_by=u2.id)

    # Then 1
    assert result is None
    # Then 2
    db.expire_all()
    assert snap(db, a) == before_a


# [claude] ATT-SD-06
def test_att_sd_06__an_unknown_id_returns_none_and_writes_nothing(db, w1, u2, mk_attachment):
    """ATT-SD-06 — an unknown id returns None and writes nothing.
    Rules: `soft_delete` R3"""
    mk_attachment()
    before = stored_count(db)

    with StatementRecorder(db) as recorder, frozen_clock():
        result = dao.soft_delete(db, id=MISSING, workspace_id=w1.id, deleted_by=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert recorder.written() == []
    # Then 3
    assert stored_count(db) == before


# [claude] ATT-SD-07
def test_att_sd_07__id_0_returns_none_and_writes_nothing(db, w1, u2, mk_attachment):
    """ATT-SD-07 — id 0 returns None and writes nothing.
    Rules: `soft_delete` R3"""
    mk_attachment()
    before = stored_count(db)

    with frozen_clock():
        result = dao.soft_delete(db, id=0, workspace_id=w1.id, deleted_by=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert stored_count(db) == before


# [claude] ATT-SD-08
def test_att_sd_08__an_already_deleted_row_is_deleted_again_the_stamp_is_overwritten(db, w1, u2, mk_deleted_attachment):
    """ATT-SD-08 — an already deleted row is deleted again: the stamp is overwritten.
    Rules: `soft_delete` R4"""
    db.execute(text("SET LOCAL TIME ZONE 'UTC'"))
    d = mk_deleted_attachment()

    with frozen_clock():
        result = dao.soft_delete(db, id=d.id, workspace_id=w1.id, deleted_by=u2.id)

    # Then 1
    assert result is d
    # Then 2
    row = reread(db, d)
    assert row.is_deleted is True
    assert row.deleted_by == u2.id
    # Then 3
    assert stored_utc(db, d) == NOW


# [claude] ATT-SD-09
def test_att_sd_09__flushed_not_committed_a_savepoint_rollback_leaves_the_row_live(db, w1, u2, mk_attachment):
    """ATT-SD-09 — flushed, not committed: a savepoint rollback leaves the row live.
    Rules: `soft_delete` R5, Side effects"""
    a = mk_attachment()
    a_id = a.id

    with commit_spy(db) as spy, frozen_clock():
        sp = db.begin_nested()
        result = dao.soft_delete(db, id=a_id, workspace_id=w1.id, deleted_by=u2.id)

        # Then 1
        assert result.id == a_id
        # Then 2
        assert db.scalar(text("SELECT count(*) FROM attachments WHERE id = :i AND is_deleted"), {"i": a_id}) == 1
        sp.rollback()
        # Then 3
        row = reread(db, a)
        assert row.is_deleted is False
        assert row.deleted_by is None
        assert row.deleted_at is None
        # Then 4
        assert spy.call_count == 0


# [claude] ATT-SD-10
def test_att_sd_10__an_unknown_deleted_by_fails_at_the_flush(db, w1, mk_attachment):
    """ATT-SD-10 — an unknown deleted_by fails at the flush.
    Rules: `soft_delete` R6, Errors row 1"""
    a = mk_attachment()

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested(), frozen_clock():
            dao.soft_delete(db, id=a.id, workspace_id=w1.id, deleted_by=MISSING)
    # Then 2
    assert exc.value.orig.pgcode == "23503"
    # Then 3
    row = reread(db, a)
    assert row.is_deleted is False
    assert row.deleted_by is None
    assert row.deleted_at is None


# [claude] ATT-SD-11
def test_att_sd_11__positional_arguments_raise_typeerror_and_change_nothing(db, w1, u2, mk_attachment):
    """ATT-SD-11 — positional arguments raise TypeError and change nothing.
    Rules: `soft_delete` Errors row 2"""
    a = mk_attachment()
    before_a = snap(db, a)

    # Then 1
    with pytest.raises(TypeError):
        with frozen_clock():
            dao.soft_delete(db, a.id, w1.id, u2.id)
    # Then 2
    db.expire_all()
    assert snap(db, a) == before_a


# [claude] ATT-SD-12
def test_att_sd_12__the_attachment_s_link_markup_markup_event_and_ledger_row_are_not_touched(db, w1, u1, u2, mk_attachment):
    """ATT-SD-12 — the attachment's link, markup, markup event and ledger row are not touched.
    Rules: `soft_delete` R7"""
    a = mk_attachment()
    lnk = _add(db, AttachmentLink(workspace_id=w1.id, attachment_id=a.id, entity_type="purchase_order", entity_id=501,
                                  linked_by=u1.id))
    m = _add(db, AttachmentMarkup(workspace_id=w1.id, attachment_id=a.id, user_id=u1.id, payload={"shapes": [1]}))
    e = _add(db, AttachmentMarkupEvent(workspace_id=w1.id, attachment_id=a.id, user_id=u1.id, event_type="markup_saved",
                                       description="Saved"))
    g = _add(db, AttachmentLedger(workspace_id=w1.id, attachment_id=a.id, transaction_type="ready", file_name="file.png",
                                  mime_type="image/png", file_size=100, entity_type="purchase_order",
                                  performed_at=datetime(2026, 11, 3, 9, 0, tzinfo=timezone.utc)))
    before_l, before_m, before_e, before_g = snap(db, lnk), snap(db, m), snap(db, e), snap(db, g)

    with frozen_clock():
        result = dao.soft_delete(db, id=a.id, workspace_id=w1.id, deleted_by=u2.id)

    # Then 1
    assert result.id == a.id
    db.expire_all()
    # Then 2
    assert snap(db, lnk) == before_l
    # Then 3
    assert snap(db, m) == before_m
    # Then 4
    assert snap(db, e) == before_e
    # Then 5
    assert snap(db, g) == before_g


# [claude] ATT-SD-13
def test_att_sd_13__one_update_of_the_one_row_and_no_other_attachment_changes(db, w1, u2, mk_attachment):
    """ATT-SD-13 — one UPDATE of the one row, and no other attachment changes.
    Rules: `soft_delete` Side effects"""
    a = mk_attachment()
    b = mk_attachment(file_name="other.png")
    before_b = snap(db, b)

    with StatementRecorder(db) as recorder, frozen_clock():
        result = dao.soft_delete(db, id=a.id, workspace_id=w1.id, deleted_by=u2.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert len(recorder.written()) == 1
    # Then 3
    assert recorder.written()[0].lstrip().upper().startswith("UPDATE ATTACHMENTS")
    # Then 4
    db.expire_all()
    assert snap(db, b) == before_b
