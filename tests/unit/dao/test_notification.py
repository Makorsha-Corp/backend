"""Unit tests for app/dao/notification.py.

Implements tests/unit/dao/notification.cases.md, one test per case, in card
order. Real Postgres session (`db` fixture). The one patch is the Conventions'
external: every `mark_read` When runs under
`patch("app.dao.notification.utcnow", return_value=NOW)`.

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117, DTZ001  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`, and naive NOW)
import json
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import DataError, IntegrityError

from app.dao.notification import notification_dao
from app.models.notification import Notification
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton notification_dao"
dao = notification_dao

# Convention "MISSING"
MISSING = 999999999

# Convention "NOW" (naive), "EARLY", "T1, T2, T3" (aware UTC)
NOW = datetime(2026, 3, 5, 17, 0, 0)
EARLY = datetime(2026, 3, 1, 8, 0, 0, tzinfo=timezone.utc)
T1 = datetime(2026, 3, 1, 9, 0, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 3, 2, 9, 0, 0, tzinfo=timezone.utc)
T3 = datetime(2026, 3, 3, 9, 0, 0, tzinfo=timezone.utc)

# Convention "Externals": the patch target of every mark_read When
CLOCK = "app.dao.notification.utcnow"


# --------------------------------------------------------------------------- #
# Conventions -> the rows that exist in every test (W1, W2, U1, U2, U3)
# --------------------------------------------------------------------------- #

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


@pytest.fixture
def u3(db, u2):
    return make_profile(db)


# Convention "Standing rows, no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2, u1, u2, u3):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builder "note" (flushes before it returns)
# --------------------------------------------------------------------------- #

def _note_fields(w1, u1, u2):
    return {"workspace_id": w1.id, "recipient_user_id": u1.id, "actor_user_id": u2.id,
            "notification_type": "mention", "entity_type": "purchase_order", "entity_id": 1,
            "source_type": "discussion", "source_id": 1}


@pytest.fixture
def mk_note(db, w1, u1, u2):
    """mk_note(**but) -> Notification: "note", with the card's "but" columns."""
    def _mk(**but):
        row = Notification(**{**_note_fields(w1, u1, u2), **but})
        db.add(row)
        db.flush()
        return row
    return _mk


# The "51 notes E1 ... E51, built with add_all" Given of GF-10, GF-11
@pytest.fixture
def mk_many_notes(db, w1, u1, u2):
    """mk_many_notes(count) -> `newest`: the ids of Ecount, ... E1; Ek created at 09:00:k UTC."""
    def _mk(count):
        rows = [Notification(**{**_note_fields(w1, u1, u2),
                                "created_at": datetime(2026, 3, 1, 9, 0, k, tzinfo=timezone.utc)})
                for k in range(1, count + 1)]
        db.add_all(rows)
        db.flush()
        return [row.id for row in reversed(rows)]
    return _mk


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (no expected values inside)
# --------------------------------------------------------------------------- #

# Convention "idset(items)", "ids(items)"
def idset(items):
    return {r.id for r in items}


def ids(items):
    return [r.id for r in items]


# Convention "re-read X"
def reread(db, row):
    db.expire_all()
    return db.execute(select(Notification).where(Notification.id == row.id)).scalar_one_or_none()


# Convention "unchanged(X)": every column of X, straight from the table
def snap(db, row):
    table = Notification.__table__
    found = db.execute(select(table).where(table.c.id == sa_inspect(row).identity[0])).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "utc_read(X)"
def utc_read(db, row):
    return db.execute(text("SELECT read_at AT TIME ZONE 'UTC' FROM notifications WHERE id = :id"), {"id": row.id}).scalar()


# Convention "nothing written": the number of `notifications` rows stored
def stored_count(db):
    return db.scalar(select(func.count()).select_from(Notification.__table__))


# Convention "count" lines of CR-11: raw SELECT count(*) of W1's rows
def w_count(db, workspace_id):
    return db.execute(text("SELECT count(*) FROM notifications WHERE workspace_id = :w"), {"w": workspace_id}).scalar()


# Convention "Statement recorder"
class StatementRecorder:
    def __init__(self, db):
        self.bind = db.get_bind()
        self.calls = []

    def _record(self, conn, cursor, statement, parameters, context, executemany):
        self.calls.append((statement, parameters))

    def __enter__(self):
        event.listen(self.bind, "before_cursor_execute", self._record)
        return self

    def __exit__(self, *exc_info):
        event.remove(self.bind, "before_cursor_execute", self._record)
        return False

    @property
    def recorded(self):
        return [s for s, _ in self.calls]

    @property
    def selects(self):
        return [s for s in self.recorded if s.lstrip().upper().startswith("SELECT")]

    @property
    def written(self):
        return [s for s in self.recorded if s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]

    @property
    def sql(self):
        """The one recorded SELECT from notifications that contains LIMIT; fails loudly unless there is exactly one."""
        [statement] = [s for s in self.selects if "FROM notifications" in s and "LIMIT" in s]
        return statement

    @property
    def notify(self):
        [statement] = [s for s in self.recorded if "pg_notify" in s]
        return statement

    @property
    def notify_args(self):
        [params] = [p for s, p in self.calls if "pg_notify" in s]
        return list(params.values()) if isinstance(params, dict) else list(params)

    @property
    def payload(self):
        [value] = [v for v in self.notify_args if isinstance(v, str) and v.startswith("{")]
        return value


# Convention "order_part"
def order_part_of(sql):
    return sql.split("ORDER BY", 1)[1].split("LIMIT", 1)[0] if "ORDER BY" in sql else ""


# --------------------------------------------------------------------------- #
# NotificationDAO.get_for_user
# --------------------------------------------------------------------------- #


# [claude] NTF-GF-01
def test_ntf_gf_01__the_user_s_rows_of_the_workspace_read_and_unread_with_total_and_unread(db, w1, w2, u1, u3, mk_note):
    """NTF-GF-01 — the user's rows of the workspace, read and unread, with total and unread count.
    Rules: `get_for_user` R1, R3, Returns"""
    a = mk_note(entity_id=MISSING)
    b = mk_note(is_read=True, read_at=EARLY)
    mk_note(recipient_user_id=u3.id)
    mk_note(workspace_id=w2.id)

    result = dao.get_for_user(db, workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert isinstance(result, tuple)
    # Then 2
    assert len(result) == 3
    # Then 3
    assert idset(result[0]) == {a.id, b.id}
    # Then 4
    assert result[1] == 2
    # Then 5
    assert result[2] == 1


# [claude] NTF-GF-02
def test_ntf_gf_02__unread_only_lists_and_counts_only_unread_rows(db, w1, u1, mk_note):
    """NTF-GF-02 — unread_only lists and counts only unread rows.
    Rules: `get_for_user` R2, R3"""
    a = mk_note()
    mk_note(is_read=True, read_at=EARLY)
    c = mk_note()

    result = dao.get_for_user(db, workspace_id=w1.id, user_id=u1.id, unread_only=True)

    # Then 1
    assert idset(result[0]) == {a.id, c.id}
    # Then 2
    assert result[1] == 2
    # Then 3
    assert result[2] == 2


# [claude] NTF-GF-03
def test_ntf_gf_03__total_and_unread_count_are_taken_before_paging(db, w1, u1, mk_note):
    """NTF-GF-03 — total and unread count are taken before paging.
    Rules: `get_for_user` R3"""
    a = mk_note(created_at=T3)
    mk_note(created_at=T2)
    mk_note(created_at=T1)
    mk_note(is_read=True, read_at=EARLY, created_at=T1)

    result = dao.get_for_user(db, workspace_id=w1.id, user_id=u1.id, limit=1)

    # Then 1
    assert ids(result[0]) == [a.id]
    # Then 2
    assert result[1] == 4
    # Then 3
    assert result[2] == 3


# [claude] NTF-GF-04
def test_ntf_gf_04__the_unread_count_with_unread_only_false_still_counts_only_unread_rows(db, w1, u1, mk_note):
    """NTF-GF-04 — the unread count with unread_only=False still counts only unread rows.
    Rules: `get_for_user` R3"""
    a = mk_note(is_read=True, read_at=EARLY)
    b = mk_note(is_read=True, read_at=EARLY)

    result = dao.get_for_user(db, workspace_id=w1.id, user_id=u1.id, unread_only=False)

    # Then 1
    assert idset(result[0]) == {a.id, b.id}
    # Then 2
    assert result[1] == 2
    # Then 3
    assert result[2] == 0


# [claude] NTF-GF-05
def test_ntf_gf_05__newest_first_by_created_at_whatever_the_ids(db, w1, u1, mk_note):
    """NTF-GF-05 — newest first by created_at, whatever the ids.
    Rules: `get_for_user` R4"""
    a = mk_note(created_at=T2)
    b = mk_note(created_at=T3)
    c = mk_note(created_at=T1)

    result = dao.get_for_user(db, workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert ids(result[0]) == [b.id, a.id, c.id]


# [claude] NTF-GF-06
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1412: Notifications with one timestamp come back in no fixed order "
    "(non-strict: the tied rows come back in physical order, which can match by accident)",
)
def test_ntf_gf_06__on_a_tie_the_higher_id_comes_first_also_after_the_lowest_id_was_update(db, w1, u1, mk_note):
    """NTF-GF-06 — on a tie the higher id comes first, also after the lowest id was updated.
    Rules: `get_for_user` R4 [BUG-1412]"""
    a = mk_note(created_at=T2)
    b = mk_note(created_at=T2)
    c = mk_note(created_at=T2)
    a.preview = "edited"
    db.flush()
    db.expire_all()

    result = dao.get_for_user(db, workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert len(result[0]) == 3
    # Then 2
    assert ids(result[0]) == [c.id, b.id, a.id]


# [claude] NTF-GF-07
@pytest.mark.xfail(strict=True, reason="BUG-1412: Notifications with one timestamp come back in no fixed order")
def test_ntf_gf_07__the_query_orders_by_created_at_then_id_both_descending(db, w1, u1, mk_note):
    """NTF-GF-07 — the query orders by created_at, then id, both descending.
    Rules: `get_for_user` R4 [BUG-1412]"""
    a = mk_note()

    with StatementRecorder(db) as recorder:
        result = dao.get_for_user(db, workspace_id=w1.id, user_id=u1.id)
    sql = recorder.sql
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result[0]) == [a.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "created_at" in order_part
    # Then 4
    assert ".id" in order_part
    # Then 5
    assert order_part.index("created_at") < order_part.index(".id")
    # Then 6
    assert order_part.upper().count("DESC") == 2
    # Then 7
    assert order_part.count(",") == 1


# [claude] NTF-GF-08
def test_ntf_gf_08__the_recipient_filter_is_applied_before_the_page(db, w1, u1, u3, mk_note):
    """NTF-GF-08 — the recipient filter is applied before the page.
    Rules: `get_for_user` R1, R5"""
    mk_note(recipient_user_id=u3.id, created_at=T3)
    mk_note(created_at=T2)
    b = mk_note(created_at=T1)

    result = dao.get_for_user(db, workspace_id=w1.id, user_id=u1.id, skip=1, limit=1)

    # Then 1
    assert ids(result[0]) == [b.id]
    # Then 2
    assert result[1] == 2


# [claude] NTF-GF-09
def test_ntf_gf_09__unread_only_is_applied_before_the_page(db, w1, u1, mk_note):
    """NTF-GF-09 — unread_only is applied before the page.
    Rules: `get_for_user` R2, R5"""
    mk_note(is_read=True, read_at=EARLY, created_at=T3)
    mk_note(created_at=T2)
    b = mk_note(created_at=T1)

    result = dao.get_for_user(db, workspace_id=w1.id, user_id=u1.id, unread_only=True, skip=1, limit=1)

    # Then 1
    assert ids(result[0]) == [b.id]
    # Then 2
    assert result[1] == 2


# [claude] NTF-GF-10
def test_ntf_gf_10__with_the_default_limit_51_rows_give_the_newest_50(db, w1, u1, mk_many_notes):
    """NTF-GF-10 — with the default limit 51 rows give the newest 50.
    Rules: `get_for_user` R5"""
    newest = mk_many_notes(51)

    result = dao.get_for_user(db, workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert len(result[0]) == 50
    # Then 2
    assert ids(result[0]) == newest[:50]
    # Then 3
    assert result[1] == 51


# [claude] NTF-GF-11
def test_ntf_gf_11__limit_1000_gives_all_51(db, w1, u1, mk_many_notes):
    """NTF-GF-11 — limit=1000 gives all 51.
    Rules: `get_for_user` R5"""
    mk_many_notes(51)

    result = dao.get_for_user(db, workspace_id=w1.id, user_id=u1.id, limit=1000)

    # Then 1
    assert len(result[0]) == 51
    # Then 2
    assert result[1] == 51


# [claude] NTF-GF-12
def test_ntf_gf_12__limit_0_gives_no_rows_and_the_counts_unchanged(db, w1, u1, mk_note):
    """NTF-GF-12 — limit=0 gives no rows and the counts unchanged.
    Rules: `get_for_user` R5"""
    mk_note()
    mk_note()

    result = dao.get_for_user(db, workspace_id=w1.id, user_id=u1.id, limit=0)

    # Then 1
    assert result[0] == []
    # Then 2
    assert result[1] == 2
    # Then 3
    assert result[2] == 2


# [claude] NTF-GF-13
def test_ntf_gf_13__an_unknown_workspace_gives_0_0(db, u1, mk_note):
    """NTF-GF-13 — an unknown workspace gives ([], 0, 0).
    Rules: `get_for_user` R5"""
    mk_note()

    result = dao.get_for_user(db, workspace_id=MISSING, user_id=u1.id)

    # Then 1
    assert result == ([], 0, 0)


# [claude] NTF-GF-14
def test_ntf_gf_14__user_id_0_gives_0_0(db, w1, mk_note):
    """NTF-GF-14 — user id 0 gives ([], 0, 0).
    Rules: `get_for_user` R5"""
    mk_note()

    result = dao.get_for_user(db, workspace_id=w1.id, user_id=0)

    # Then 1
    assert result == ([], 0, 0)


# [claude] NTF-GF-15
def test_ntf_gf_15__a_negative_skip_raises_dataerror_2201x(db, w1, u1, mk_note):
    """NTF-GF-15 — a negative skip raises DataError 2201X.
    Rules: `get_for_user` R5, Errors"""
    mk_note()
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_for_user(db, workspace_id=w1.id, user_id=u1.id, skip=-1)
    # Then 2
    assert exc.value.orig.pgcode == "2201X"
    # Then 3
    assert stored_count(db) == before


# [claude] NTF-GF-16
def test_ntf_gf_16__a_negative_limit_raises_dataerror_2201w(db, w1, u1, mk_note):
    """NTF-GF-16 — a negative limit raises DataError 2201W.
    Rules: `get_for_user` R5, Errors"""
    mk_note()
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_for_user(db, workspace_id=w1.id, user_id=u1.id, limit=-1)
    # Then 2
    assert exc.value.orig.pgcode == "2201W"
    # Then 3
    assert stored_count(db) == before


# [claude] NTF-GF-17
def test_ntf_gf_17__each_row_comes_with_its_actor_loaded_in_the_page_statement(db, w1, u1, u2, mk_note):
    """NTF-GF-17 — each row comes with its actor, loaded in the page statement.
    Rules: `get_for_user` R6"""
    a = mk_note(created_at=T2)
    b = mk_note(actor_user_id=None, created_at=T1)

    with StatementRecorder(db) as recorder:
        result = dao.get_for_user(db, workspace_id=w1.id, user_id=u1.id)
    sql = recorder.sql

    # Then 1
    assert ids(result[0]) == [a.id, b.id]
    # Then 2
    assert "profiles" in sql
    # Then 3
    assert "JOIN" in sql.upper()
    # Then 4
    assert result[0][0].actor.id == u2.id
    # Then 5
    assert result[0][1].actor is None


# [claude] NTF-GF-18
def test_ntf_gf_18__writes_nothing_a_pending_row_stays_pending_an_unflushed_edit_stays_unf(db, w1, u1, u2, u3, mk_note):
    """NTF-GF-18 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed.
    Rules: `get_for_user` Side effects"""
    a = mk_note()
    b = mk_note(recipient_user_id=u3.id)
    p = Notification(workspace_id=w1.id, recipient_user_id=u1.id, actor_user_id=u2.id, notification_type="mention",
                     entity_type="purchase_order", entity_id=2, source_type="discussion", source_id=2)
    db.add(p)
    b.preview = "edited"

    with StatementRecorder(db) as recorder:
        result = dao.get_for_user(db, workspace_id=w1.id, user_id=u1.id)
    written = recorder.written

    # Then 1
    assert ids(result[0]) == [a.id]
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


# [claude] NTF-GF-19
def test_ntf_gf_19__another_recipient_with_a_lower_id_their_rows_are_not_shown_or_counted(db, w1, u3, mk_note):
    """NTF-GF-19 — another recipient with a lower id: their rows are not shown or counted.
    Rules: `get_for_user` R1"""
    mk_note()
    a = mk_note(recipient_user_id=u3.id)

    result = dao.get_for_user(db, workspace_id=w1.id, user_id=u3.id)

    # Then 1
    assert idset(result[0]) == {a.id}
    # Then 2
    assert result[1] == 1
    # Then 3
    assert result[2] == 1


# --------------------------------------------------------------------------- #
# NotificationDAO.create
# --------------------------------------------------------------------------- #


# [claude] NTF-CR-01
def test_ntf_cr_01__one_unread_row_with_the_given_values_for_a_recipient_of_no_membership(db, w1, u1, u2):
    """NTF-CR-01 — one unread row with the given values, for a recipient of no membership.
    Rules: `create` R1, R3, Returns"""
    result = dao.create(db, workspace_id=w1.id, recipient_user_id=u1.id, actor_user_id=u2.id,
                        notification_type="approval_request", entity_type="purchase_order", entity_id=MISSING,
                        source_type="discussion", source_id=7, preview="Please approve")

    # Then 1
    assert isinstance(result, Notification)
    # Then 2
    assert result.id is not None
    # Then 3
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.recipient_user_id == u1.id
    assert row.actor_user_id == u2.id
    assert row.notification_type == "approval_request"
    # Then 4
    assert row.entity_type == "purchase_order"
    assert row.entity_id == MISSING
    assert row.source_type == "discussion"
    assert row.source_id == 7
    assert row.preview == "Please approve"
    # Then 5
    assert row.is_read is False
    assert row.read_at is None
    # Then 6
    assert row.created_at is not None
    assert row.created_at.tzinfo is not None


# [claude] NTF-CR-02
def test_ntf_cr_02__no_type_gives_mention_no_actor_and_no_preview_are_stored_null(db, w1, u1):
    """NTF-CR-02 — no type gives 'mention'; no actor and no preview are stored NULL.
    Rules: `create` R1"""
    result = dao.create(db, workspace_id=w1.id, recipient_user_id=u1.id, actor_user_id=None, notification_type=None,
                        entity_type="purchase_order", entity_id=1, source_type="discussion", source_id=1)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.notification_type == "mention"
    # Then 3
    assert row.actor_user_id is None
    assert row.preview is None


# [claude] NTF-CR-03
def test_ntf_cr_03__after_the_insert_pg_notify_is_sent_on_user_notifications_with_the_payl(db, w1, u1, u2):
    """NTF-CR-03 — after the insert, pg_notify is sent on 'user_notifications' with the payload in key order.
    Rules: `create` R2, Side effects"""
    with StatementRecorder(db) as recorder:
        result = dao.create(db, workspace_id=w1.id, recipient_user_id=u1.id, actor_user_id=u2.id,
                            notification_type="mention", entity_type="purchase_order", entity_id=1,
                            source_type="discussion", source_id=1)
    recorded = recorder.recorded
    written = recorder.written

    # Then 1
    assert result.id is not None
    # Then 2
    assert len([s for s in recorded if "pg_notify" in s]) == 1
    # Then 3
    notify = recorder.notify
    assert recorded.index(notify) > recorded.index(written[0])
    # Then 4
    notify_args = recorder.notify_args
    assert "user_notifications" in notify or "user_notifications" in notify_args
    # Then 5
    payload = recorder.payload
    assert json.loads(payload) == {"recipient_user_id": u1.id, "workspace_id": w1.id, "notification_id": result.id}
    # Then 6
    assert list(json.loads(payload).keys()) == ["recipient_user_id", "workspace_id", "notification_id"]
    # Then 7
    assert len(written) == 1
    # Then 8
    assert "INSERT INTO notifications" in written[0]


# [claude] NTF-CR-04
def test_ntf_cr_04__no_membership_or_subject_is_looked_up(db, w1, u2, u3):
    """NTF-CR-04 — no membership or subject is looked up.
    Rules: `create` R3"""
    with StatementRecorder(db) as recorder:
        result = dao.create(db, workspace_id=w1.id, recipient_user_id=u3.id, actor_user_id=u2.id,
                            notification_type="mention", entity_type="purchase_order", entity_id=MISSING,
                            source_type="discussion", source_id=1)
    selects = recorder.selects

    # Then 1
    assert result.id is not None
    # Then 2
    assert not any("workspace_members" in s for s in selects)
    # Then 3
    assert not any("purchase_orders" in s for s in selects)


# [claude] NTF-CR-05
def test_ntf_cr_05__an_unknown_workspace_raises_integrityerror_23503_no_row_no_pg_notify(db, u1, u2):
    """NTF-CR-05 — an unknown workspace raises IntegrityError 23503; no row, no pg_notify.
    Rules: `create` R4, Errors"""
    before = stored_count(db)

    with StatementRecorder(db) as recorder:
        # Then 1
        with pytest.raises(IntegrityError) as exc:
            with db.begin_nested():
                dao.create(db, workspace_id=MISSING, recipient_user_id=u1.id, actor_user_id=u2.id,
                           notification_type="mention", entity_type="purchase_order", entity_id=1,
                           source_type="discussion", source_id=1)
    recorded = recorder.recorded
    # Then 2
    assert exc.value.orig.pgcode == "23503"
    # Then 3
    assert not any("pg_notify" in s for s in recorded)
    # Then 4
    assert stored_count(db) == before


# [claude] NTF-CR-06
def test_ntf_cr_06__an_unknown_recipient_raises_integrityerror_23503_no_row_no_pg_notify(db, w1, u2):
    """NTF-CR-06 — an unknown recipient raises IntegrityError 23503; no row, no pg_notify.
    Rules: `create` R4, Errors"""
    before = stored_count(db)

    with StatementRecorder(db) as recorder:
        # Then 1
        with pytest.raises(IntegrityError) as exc:
            with db.begin_nested():
                dao.create(db, workspace_id=w1.id, recipient_user_id=MISSING, actor_user_id=u2.id,
                           notification_type="mention", entity_type="purchase_order", entity_id=1,
                           source_type="discussion", source_id=1)
    recorded = recorder.recorded
    # Then 2
    assert exc.value.orig.pgcode == "23503"
    # Then 3
    assert not any("pg_notify" in s for s in recorded)
    # Then 4
    assert stored_count(db) == before


# [claude] NTF-CR-07
def test_ntf_cr_07__an_unknown_actor_raises_integrityerror_23503_no_row_no_pg_notify(db, w1, u1):
    """NTF-CR-07 — an unknown actor raises IntegrityError 23503; no row, no pg_notify.
    Rules: `create` R4, Errors"""
    before = stored_count(db)

    with StatementRecorder(db) as recorder:
        # Then 1
        with pytest.raises(IntegrityError) as exc:
            with db.begin_nested():
                dao.create(db, workspace_id=w1.id, recipient_user_id=u1.id, actor_user_id=MISSING,
                           notification_type="mention", entity_type="purchase_order", entity_id=1,
                           source_type="discussion", source_id=1)
    recorded = recorder.recorded
    # Then 2
    assert exc.value.orig.pgcode == "23503"
    # Then 3
    assert not any("pg_notify" in s for s in recorded)
    # Then 4
    assert stored_count(db) == before


# [claude] NTF-CR-08
def test_ntf_cr_08__a_type_of_31_characters_raises_dataerror_22001_no_row_no_pg_notify(db, w1, u1, u2):
    """NTF-CR-08 — a type of 31 characters raises DataError 22001; no row, no pg_notify.
    Rules: `create` R4, Errors"""
    before = stored_count(db)

    with StatementRecorder(db) as recorder:
        # Then 1
        with pytest.raises(DataError) as exc:
            with db.begin_nested():
                dao.create(db, workspace_id=w1.id, recipient_user_id=u1.id, actor_user_id=u2.id,
                           notification_type="t" * 31, entity_type="purchase_order", entity_id=1,
                           source_type="discussion", source_id=1)
    recorded = recorder.recorded
    # Then 2
    assert exc.value.orig.pgcode == "22001"
    # Then 3
    assert not any("pg_notify" in s for s in recorded)
    # Then 4
    assert stored_count(db) == before


# [claude] NTF-CR-09
def test_ntf_cr_09__types_of_exactly_30_characters_are_stored_whole(db, w1, u1, u2):
    """NTF-CR-09 — types of exactly 30 characters are stored whole.
    Rules: `create` R4"""
    result = dao.create(db, workspace_id=w1.id, recipient_user_id=u1.id, actor_user_id=u2.id,
                        notification_type="t" * 30, entity_type="e" * 30, entity_id=1,
                        source_type="s" * 30, source_id=1)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.notification_type == "t" * 30
    assert row.entity_type == "e" * 30
    assert row.source_type == "s" * 30


# [claude] NTF-CR-10
def test_ntf_cr_10__an_entity_type_of_31_characters_raises_dataerror_22001(db, w1, u1, u2):
    """NTF-CR-10 — an entity type of 31 characters raises DataError 22001.
    Rules: `create` R4, Errors"""
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.create(db, workspace_id=w1.id, recipient_user_id=u1.id, actor_user_id=u2.id,
                       notification_type="mention", entity_type="e" * 31, entity_id=1,
                       source_type="discussion", source_id=1)
    # Then 2
    assert exc.value.orig.pgcode == "22001"
    # Then 3
    assert stored_count(db) == before


# [claude] NTF-CR-11
def test_ntf_cr_11__the_row_is_flushed_not_committed(db, w1, u1, u2):
    """NTF-CR-11 — the row is flushed, not committed.
    Rules: `create` Side effects"""
    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        sp = db.begin_nested()
        result = dao.create(db, workspace_id=w1.id, recipient_user_id=u1.id, actor_user_id=u2.id,
                            notification_type="mention", entity_type="purchase_order", entity_id=1,
                            source_type="discussion", source_id=1)

        # Then 1
        assert result.id is not None
        # Then 2
        assert w_count(db, w1.id) == 1
        sp.rollback()
        # Then 3
        assert w_count(db, w1.id) == 0
        # Then 4
        assert commit_spy.call_count == 0


# --------------------------------------------------------------------------- #
# NotificationDAO.mark_read
# --------------------------------------------------------------------------- #


# [claude] NTF-MR-01
def test_ntf_mr_01__ids_none_marks_every_unread_row_of_the_user_in_the_workspace_read_at_n(db, w1, w2, u1, u3, mk_note):
    """NTF-MR-01 — ids=None marks every unread row of the user in the workspace, read_at now (UTC session).
    Rules: `mark_read` R1, R3, R4, Returns"""
    db.execute(text("SET LOCAL TIME ZONE 'UTC'"))
    a = mk_note()
    b = mk_note()
    c = mk_note(is_read=True, read_at=EARLY)
    x = mk_note(recipient_user_id=u3.id)
    y = mk_note(workspace_id=w2.id)
    before_x = snap(db, x)
    before_y = snap(db, y)

    with patch(CLOCK, return_value=NOW):
        result = dao.mark_read(db, workspace_id=w1.id, user_id=u1.id, ids=None)

    # Then 1
    assert result == 2
    # Then 2
    assert reread(db, a).is_read is True
    assert utc_read(db, a) == NOW
    # Then 3
    assert reread(db, b).is_read is True
    assert utc_read(db, b) == NOW
    # Then 4
    assert utc_read(db, c) == datetime(2026, 3, 1, 8, 0, 0)
    # Then 5
    db.expire_all()
    assert snap(db, x) == before_x
    # Then 6
    assert snap(db, y) == before_y


# [claude] NTF-MR-02
def test_ntf_mr_02__a_list_marks_only_the_user_s_unread_rows_among_them_others_are_ignored(db, w1, w2, u1, u3, mk_note):
    """NTF-MR-02 — a list marks only the user's unread rows among them; others are ignored.
    Rules: `mark_read` R1"""
    a = mk_note()
    b = mk_note()
    c = mk_note(is_read=True, read_at=EARLY)
    x = mk_note(recipient_user_id=u3.id)
    y = mk_note(workspace_id=w2.id)
    before_x = snap(db, x)
    before_y = snap(db, y)

    with patch(CLOCK, return_value=NOW):
        result = dao.mark_read(db, workspace_id=w1.id, user_id=u1.id, ids=[a.id, c.id, x.id, y.id, MISSING, 0])

    # Then 1
    assert result == 1
    # Then 2
    row_a = reread(db, a)
    assert row_a.is_read is True
    assert row_a.read_at is not None
    # Then 3
    row_b = reread(db, b)
    assert row_b.is_read is False
    assert row_b.read_at is None
    # Then 4
    db.expire_all()
    assert snap(db, x) == before_x
    # Then 5
    assert snap(db, y) == before_y


# [claude] NTF-MR-03
@pytest.mark.xfail(strict=True, reason="BUG-1414: Marking an empty list of notifications read marks all of them")
def test_ntf_mr_03__an_empty_list_marks_nothing_and_returns_0(db, w1, u1, mk_note):
    """NTF-MR-03 — an empty list marks nothing and returns 0.
    Rules: `mark_read` R2 [BUG-1414]"""
    a = mk_note()
    b = mk_note()

    with patch(CLOCK, return_value=NOW):
        result = dao.mark_read(db, workspace_id=w1.id, user_id=u1.id, ids=[])

    # Then 1
    assert result == 0
    # Then 2
    assert reread(db, a).is_read is False
    # Then 3
    assert reread(db, b).is_read is False


# [claude] NTF-MR-04
@pytest.mark.xfail(strict=True, reason="BUG-1413: A notification's read time depends on the database's time zone")
def test_ntf_mr_04__under_asia_dhaka_read_at_read_as_utc_is_still_the_moment_of_the_call(db, w1, u1, mk_note):
    """NTF-MR-04 — under Asia/Dhaka, read_at read as UTC is still the moment of the call.
    Rules: `mark_read` R3 [BUG-1413]"""
    db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))
    a = mk_note()

    with patch(CLOCK, return_value=NOW):
        result = dao.mark_read(db, workspace_id=w1.id, user_id=u1.id, ids=None)

    # Then 1
    assert result == 1
    # Then 2
    db.expire_all()
    assert utc_read(db, a) == NOW


# [claude] NTF-MR-05
@pytest.mark.xfail(strict=True, reason="BUG-1413: A notification's read time depends on the database's time zone")
def test_ntf_mr_05__under_america_new_york_read_at_read_as_utc_is_still_the_moment_of_the(db, w1, u1, mk_note):
    """NTF-MR-05 — under America/New_York, read_at read as UTC is still the moment of the call.
    Rules: `mark_read` R3 [BUG-1413]"""
    db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))
    a = mk_note()

    with patch(CLOCK, return_value=NOW):
        result = dao.mark_read(db, workspace_id=w1.id, user_id=u1.id, ids=None)

    # Then 1
    assert result == 1
    # Then 2
    db.expire_all()
    assert utc_read(db, a) == NOW


# [claude] NTF-MR-06
def test_ntf_mr_06__rows_already_read_keep_their_read_at_and_are_not_counted(db, w1, u1, mk_note):
    """NTF-MR-06 — rows already read keep their read_at and are not counted.
    Rules: `mark_read` R4"""
    a = mk_note(is_read=True, read_at=EARLY)

    with patch(CLOCK, return_value=NOW):
        result = dao.mark_read(db, workspace_id=w1.id, user_id=u1.id, ids=[a.id])

    # Then 1
    assert result == 0
    # Then 2
    assert reread(db, a).read_at == EARLY


# [claude] NTF-MR-07
def test_ntf_mr_07__rows_loaded_in_the_session_still_show_unread_until_refreshed(db, w1, u1, mk_note):
    """NTF-MR-07 — rows loaded in the session still show unread until refreshed.
    Rules: `mark_read` R4"""
    a = mk_note()

    with patch(CLOCK, return_value=NOW):
        result = dao.mark_read(db, workspace_id=w1.id, user_id=u1.id, ids=None)

    # Then 1
    assert result == 1
    # Then 2
    assert a.is_read is False
    # Then 3
    assert reread(db, a).is_read is True


# [claude] NTF-MR-08
def test_ntf_mr_08__no_flush_of_its_own_a_pending_notification_stays_pending_and_is_not_ma(db, w1, u1, u2, u3, mk_note):
    """NTF-MR-08 — no flush of its own: a pending notification stays pending and is not marked.
    Rules: `mark_read` R4"""
    mk_note()
    b = mk_note(recipient_user_id=u3.id)
    p = Notification(workspace_id=w1.id, recipient_user_id=u1.id, actor_user_id=u2.id, notification_type="mention",
                     entity_type="purchase_order", entity_id=2, source_type="discussion", source_id=2)
    db.add(p)
    b.preview = "edited"

    with patch(CLOCK, return_value=NOW):
        result = dao.mark_read(db, workspace_id=w1.id, user_id=u1.id, ids=None)

    # Then 1
    assert result == 1
    # Then 2
    assert p in db.new
    # Then 3
    assert p.id is None
    # Then 4
    assert b in db.dirty
    # Then 5
    assert len(db.dirty) == 1


# [claude] NTF-MR-09
def test_ntf_mr_09__the_update_is_not_committed(db, w1, u1, mk_note):
    """NTF-MR-09 — the update is not committed.
    Rules: `mark_read` Side effects"""
    a = mk_note()

    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        sp = db.begin_nested()
        with patch(CLOCK, return_value=NOW):
            result = dao.mark_read(db, workspace_id=w1.id, user_id=u1.id, ids=None)

        # Then 1
        assert result == 1
        # Then 2
        assert db.execute(text("SELECT is_read FROM notifications WHERE id = :id"), {"id": a.id}).scalar() is True
        sp.rollback()
        # Then 3
        assert db.execute(text("SELECT is_read FROM notifications WHERE id = :id"), {"id": a.id}).scalar() is False
        # Then 4
        assert commit_spy.call_count == 0
