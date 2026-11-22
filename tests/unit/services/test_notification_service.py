"""Unit tests for app/services/notification_service.py.

Implements tests/unit/services/notification_service.cases.md (revision 1), one
test per case, in card order (there is no NSV-M-05). Real Postgres session (`db`
fixture): a `commit()` only releases a savepoint, so the service's commits are
safe and the fixture's outer rollback discards everything. Nothing is patched
except what Conventions name: the clock patch of NSV-M-08, the failing commit,
the failing update of NSV-M-11 and the commit / rollback spies (which still
call the real method).

Normal mode: every test is written from its card and carries a `# [claude] <ID>`
comment. Row names of the cards are the lower-case names here (UA -> ua, A -> a,
`W1.id` -> `w1.id`); `# Then N` marks the checks of the card's Then line N.
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with patch.object(...)`)
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import event, func, inspect, select, text
from sqlalchemy.exc import DataError, IntegrityError

from app.dao.notification import notification_dao
from app.models.notification import Notification
from app.models.workspace_member import WorkspaceMember
from app.schemas.notification import MarkReadRequest
from app.services.notification_service import (
    _active_workspace_member_ids,
    humanize_mention_preview,
    notification_service,
)
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "svc = the singleton notification_service"
svc = notification_service

MISSING = 999999999
NOW = datetime(2026, 3, 5, 17, 0, 0)  # noqa: DTZ001
T2 = datetime(2026, 3, 2, 9, 0, 0, tzinfo=timezone.utc)
EARLY = datetime(2026, 3, 1, 8, 0, 0, tzinfo=timezone.utc)


# Convention "bn(n)": the number n in Bengali digits
def bn(n):
    return "".join(chr(0x09E6 + int(c)) for c in str(n))


def _add(db, row):
    db.add(row)
    db.flush()
    return row


# --------------------------------------------------------------------------- #
# Conventions -> standing rows, in Conventions order
# --------------------------------------------------------------------------- #

@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


@pytest.fixture
def ua(db, w2):
    return make_profile(db, name="Ann")


@pytest.fixture
def ub(db, ua):
    return make_profile(db, name="Bob")


@pytest.fixture
def us(db, ub):
    return make_profile(db, name="Sue")


@pytest.fixture
def ui(db, us):
    return make_profile(db, name="Ivy")


@pytest.fixture
def uo(db, ui):
    return make_profile(db, name="Otto")


@pytest.fixture
def un(db, uo):
    return make_profile(db, name="Nora")


def _member(db, ws, profile, status):
    return _add(db, WorkspaceMember(workspace_id=ws.id, user_id=profile.id, role="member", status=status))


# Convention "Memberships": UA, UB active in W1; US suspended in W1; UI invited in W1; UO active in W2; UN none
@pytest.fixture
def memberships(db, w1, w2, ua, ub, us, ui, uo, un):
    _member(db, w1, ua, "active")
    _member(db, w1, ub, "active")
    _member(db, w1, us, "suspended")
    _member(db, w1, ui, "invited")
    _member(db, w2, uo, "active")


# Conventions "Standing rows": in every test, no Given line needed
@pytest.fixture(autouse=True)
def standing_rows(memberships):
    pass


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #

def _note_fields(w1, ua, ub, but):
    fields = {
        "workspace_id": w1.id, "recipient_user_id": ua.id, "actor_user_id": ub.id, "notification_type": "mention",
        "entity_type": "purchase_order", "entity_id": 1, "source_type": "discussion", "source_id": 1,
    }
    fields.update(but)
    return fields


# Convention "note": one row, flushed
@pytest.fixture
def mk_note(db, w1, ua, ub):
    def _mk(**but):
        return _add(db, Notification(**_note_fields(w1, ua, ub, but)))
    return _mk


# Convention "n notes, by add_all"
@pytest.fixture
def mk_notes(db, w1, ua, ub):
    def _mk(n):
        rows = [Notification(**_note_fields(w1, ua, ub, {})) for _ in range(n)]
        db.add_all(rows)
        db.flush()
        return rows
    return _mk


# Convention "read note"
READ = {"is_read": True, "read_at": EARLY}


# Convention "commit point"
def commit_point(db):
    db.commit()


# --------------------------------------------------------------------------- #
# Conventions -> named checks
# --------------------------------------------------------------------------- #

def _id_of(row):
    return inspect(row).identity[0]


# Convention "re-read X"
def reread(db, row):
    row_id = _id_of(row)
    db.expire_all()
    return db.execute(select(Notification).where(Notification.id == row_id)).scalar_one_or_none()


def _columns(db, row_id):
    table = Notification.__table__
    found = db.execute(select(table).where(table.c.id == row_id)).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "unchanged(X)": every column at the commit point ...
def snap_before(db, row):
    return _columns(db, _id_of(row))


# ... and after a re-read
def snap(db, row):
    row_id = _id_of(row)
    db.expire_all()
    return _columns(db, row_id)


# Convention "idset(items)"
def idset(items):
    return {r.id for r in items}


# Convention "mentions": notifications of W1 with notification_type "mention" and source_id 77
def mentions(db, w1):
    db.expire_all()
    query = select(Notification).where(
        Notification.workspace_id == w1.id, Notification.notification_type == "mention", Notification.source_id == 77,
    )
    return list(db.execute(query).scalars())


# Convention "utc_read(X)"
def utc_read(db, row):
    return db.execute(
        text("SELECT read_at AT TIME ZONE 'UTC' FROM notifications WHERE id = :id"), {"id": _id_of(row)},
    ).scalar()


# Convention "count:" lines: notifications rows (all workspaces), with the filter stated
def count_notes(db, **filters):
    query = select(func.count()).select_from(Notification)
    for column, value in filters.items():
        query = query.where(getattr(Notification, column) == value)
    return db.execute(query).scalar_one()


# Convention "nothing written"
def written(db):
    return count_notes(db)


# Convention "spies": both wrap the real method
@contextmanager
def spies(db):
    with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:
        yield cm, rb


# Convention "Statement recorder"
@contextmanager
def record_sql(db):
    connection = db.connection()
    sql_log = []

    def _record(conn, cursor, statement, parameters, context, executemany):
        sql_log.append(statement)

    event.listen(connection, "before_cursor_execute", _record)
    try:
        yield sql_log
    finally:
        event.remove(connection, "before_cursor_execute", _record)


def _kind(statement):
    return statement.lstrip().split(None, 1)[0].upper() if statement.strip() else ""


# Convention "selects": every recorded SELECT
def selects_of(sql_log):
    return [s for s in sql_log if _kind(s) == "SELECT"]


# Convention "written": every recorded INSERT, UPDATE or DELETE
def writes_of(sql_log):
    return [s for s in sql_log if _kind(s) in ("INSERT", "UPDATE", "DELETE")]


# --------------------------------------------------------------------------- #
# humanize_mention_preview
# --------------------------------------------------------------------------- #

# [claude] NSV-H-01
def test_nsv_h_01__a_token_cut_by_the_limit_stays_as_cut(db):
    """NSV-H-01 — a token cut by the limit stays as cut.
    Rules: `humanize_mention_preview` R1"""
    commit_point(db)
    result = humanize_mention_preview(db, message="x" * 197 + "@[5]")

    # Then 1
    assert result == "x" * 197 + "@[5"


# [claude] NSV-H-02
def test_nsv_h_02__a_token_that_just_fits_is_replaced_so_the_text_grows_past_the_limit(db, ua):
    """NSV-H-02 — a token that just fits is replaced, so the text grows past the limit.
    Rules: `humanize_mention_preview` R1, R3"""
    tok = f"@[{ua.id}]"
    commit_point(db)
    result = humanize_mention_preview(db, message="x" * (200 - len(tok)) + tok)

    # Then 1
    assert result == "x" * (200 - len(tok)) + "@Ann"


# [claude] NSV-H-03
def test_nsv_h_03__max_len_5_cuts_the_text_to_five_characters(db):
    """NSV-H-03 — max_len=5 cuts the text to five characters.
    Rules: `humanize_mention_preview` R1"""
    commit_point(db)
    result = humanize_mention_preview(db, message="abcdefgh", max_len=5)

    # Then 1
    assert result == "abcde"


# [claude] NSV-H-04
def test_nsv_h_04__an_empty_message_gives_an_empty_text(db):
    """NSV-H-04 — an empty message gives an empty text.
    Rules: `humanize_mention_preview` R1"""
    commit_point(db)
    result = humanize_mention_preview(db, message="")

    # Then 1
    assert result == ""


# [claude] NSV-H-05
def test_nsv_h_05__a_text_without_a_token_is_returned_unchanged_and_no_profile_is_read(db):
    """NSV-H-05 — a text without a token is returned unchanged and no profile is read.
    Rules: `humanize_mention_preview` R2"""
    commit_point(db)
    with record_sql(db) as sql_log:
        result = humanize_mention_preview(db, message="Please check the press @ 5")
    selects = selects_of(sql_log)

    # Then 1
    assert result == "Please check the press @ 5"
    # Then 2
    assert selects == []


# [claude] NSV-H-06
def test_nsv_h_06__a_known_profile_is_named_and_the_same_id_twice_is_replaced_twice(db, ua, ub):
    """NSV-H-06 — a known profile is named, and the same id twice is replaced twice.
    Rules: `humanize_mention_preview` R3"""
    m = f"hi @[{ua.id}] and @[{ub.id}] and @[{ua.id}]"
    commit_point(db)
    result = humanize_mention_preview(db, message=m)

    # Then 1
    assert result == "hi @Ann and @Bob and @Ann"


# [claude] NSV-H-07
def test_nsv_h_07__leading_zeros_are_read_as_the_number(db, ua):
    """NSV-H-07 — leading zeros are read as the number.
    Rules: `humanize_mention_preview` R3"""
    m = f"@[00{ua.id}]"
    commit_point(db)
    result = humanize_mention_preview(db, message=m)

    # Then 1
    assert result == "@Ann"


# [claude] NSV-H-08
def test_nsv_h_08__an_id_with_no_profile_becomes_user_id(db):
    """NSV-H-08 — an id with no profile becomes @User <id>.
    Rules: `humanize_mention_preview` R4"""
    commit_point(db)
    result = humanize_mention_preview(db, message="ping @[999999999]")

    # Then 1
    assert result == "ping @User 999999999"


# [claude] NSV-H-09
@pytest.mark.xfail(strict=True, reason="BUG-1534: A mention preview shows the name of anyone on the platform")
def test_nsv_h_09__a_member_of_another_workspace_only_is_not_named(db, w1, uo):
    """NSV-H-09 — a member of another workspace only is not named.
    Rules: `humanize_mention_preview` R5 [BUG-1534]"""
    m = f"@[{uo.id}]"
    commit_point(db)
    result = humanize_mention_preview(db, message=m, workspace_id=w1.id)

    # Then 1
    assert result == f"@User {uo.id}"


# [claude] NSV-H-10
@pytest.mark.xfail(strict=True, reason="BUG-1534: A mention preview shows the name of anyone on the platform")
def test_nsv_h_10__a_profile_with_no_membership_is_not_named(db, w1, un):
    """NSV-H-10 — a profile with no membership is not named.
    Rules: `humanize_mention_preview` R5 [BUG-1534]"""
    m = f"@[{un.id}]"
    commit_point(db)
    result = humanize_mention_preview(db, message=m, workspace_id=w1.id)

    # Then 1
    assert result == f"@User {un.id}"


# [claude] NSV-H-11
@pytest.mark.xfail(strict=True, reason="BUG-1534: A mention preview shows the name of anyone on the platform")
def test_nsv_h_11__with_the_workspace_given_a_member_in_any_status_is_named(db, w1, ua, us, ui):
    """NSV-H-11 — with the workspace given, a member in any status is named.
    Rules: `humanize_mention_preview` R5 [BUG-1534]"""
    m = f"@[{us.id}] @[{ui.id}] @[{ua.id}]"
    commit_point(db)
    result = humanize_mention_preview(db, message=m, workspace_id=w1.id)

    # Then 1
    assert result == "@Sue @Ivy @Ann"


# [claude] NSV-H-12
def test_nsv_h_12__a_suspended_member_is_named(db, us):
    """NSV-H-12 — a suspended member is named.
    Rules: `humanize_mention_preview` R5"""
    m = f"@[{us.id}]"
    commit_point(db)
    result = humanize_mention_preview(db, message=m)

    # Then 1
    assert result == "@Sue"


# [claude] NSV-H-13
def test_nsv_h_13__text_that_only_looks_like_a_token_is_left_as_typed(db):
    """NSV-H-13 — text that only looks like a token is left as typed.
    Rules: `humanize_mention_preview` R6"""
    commit_point(db)
    result = humanize_mention_preview(db, message="@[abc] @[] @[ 1] @[-1]")

    # Then 1
    assert result == "@[abc] @[] @[ 1] @[-1]"


# [claude] NSV-H-14
@pytest.mark.xfail(strict=True, reason="BUG-1536: Non-ASCII digits inside `@[…]` make a mention")
def test_nsv_h_14__bengali_digits_make_no_token(db, ua):
    """NSV-H-14 — Bengali digits make no token.
    Rules: `humanize_mention_preview` R7 [BUG-1536]"""
    m = "@[" + bn(ua.id) + "]"
    commit_point(db)
    result = humanize_mention_preview(db, message=m)

    # Then 1
    assert result == m


# [claude] NSV-H-15
def test_nsv_h_15__a_superscript_digit_makes_no_token(db):
    """NSV-H-15 — a superscript digit makes no token.
    Rules: `humanize_mention_preview` R7"""
    commit_point(db)
    result = humanize_mention_preview(db, message="@[²]")

    # Then 1
    assert result == "@[²]"


# [claude] NSV-H-16
def test_nsv_h_16__ascii_digits_still_make_a_token(db, ub):
    """NSV-H-16 — ASCII digits still make a token.
    Rules: `humanize_mention_preview` R7"""
    m = f"@[{ub.id}]"
    commit_point(db)
    result = humanize_mention_preview(db, message=m)

    # Then 1
    assert result == "@Bob"


# [claude] NSV-H-17
def test_nsv_h_17__nothing_is_written(db, ua, mk_note):
    """NSV-H-17 — nothing is written.
    Rules: `humanize_mention_preview` R8"""
    commit_point(db)
    mk_note()
    m = f"@[{ua.id}]"
    with record_sql(db) as sql_log:
        result = humanize_mention_preview(db, message=m)
    writes = writes_of(sql_log)

    # Then 1
    assert result == "@Ann"
    # Then 2
    assert writes == []
    # Then 3
    db.rollback()
    assert count_notes(db) == 0


# --------------------------------------------------------------------------- #
# _active_workspace_member_ids
# --------------------------------------------------------------------------- #

# [claude] NSV-A-01
def test_nsv_a_01__the_set_of_the_workspaces_active_members(db, w1, ua, ub):
    """NSV-A-01 — the set of the workspace's active members.
    Rules: `_active_workspace_member_ids` R1"""
    commit_point(db)
    result = _active_workspace_member_ids(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, set)
    # Then 2
    assert result == {ua.id, ub.id}


# [claude] NSV-A-02
def test_nsv_a_02__status_must_be_exactly_active(db, w1, ua, ub):
    """NSV-A-02 — status must be exactly "active".
    Rules: `_active_workspace_member_ids` R1"""
    uc = make_profile(db, name="Cal")
    _add(db, WorkspaceMember(workspace_id=w1.id, user_id=uc.id, role="member", status="Active"))
    commit_point(db)
    result = _active_workspace_member_ids(db, workspace_id=w1.id)

    # Then 1
    assert result == {ua.id, ub.id}


# [claude] NSV-A-03
def test_nsv_a_03__no_cap_101_more_active_members_are_all_in_the_set(db, w1):
    """NSV-A-03 — no cap: 101 more active members are all in the set.
    Rules: `_active_workspace_member_ids` R1"""
    for k in range(1, 102):
        profile = make_profile(db, name=f"M{k}")
        _add(db, WorkspaceMember(workspace_id=w1.id, user_id=profile.id, role="member", status="active"))
    commit_point(db)
    result = _active_workspace_member_ids(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 103


# --------------------------------------------------------------------------- #
# NotificationService.list_for_user
# --------------------------------------------------------------------------- #

# [claude] NSV-L-01
def test_nsv_l_01__the_users_notifications_of_the_workspace_with_total_and_unread_count(
    db, w1, w2, ua, ub, mk_note,
):
    """NSV-L-01 — the user's notifications of the workspace, with total and unread count.
    Rules: `list_for_user` R1"""
    a = mk_note()
    b = mk_note(**READ)
    mk_note(recipient_user_id=ub.id)
    mk_note(workspace_id=w2.id)
    commit_point(db)
    result = svc.list_for_user(db, workspace_id=w1.id, user_id=ua.id)

    # Then 1
    assert isinstance(result, tuple)
    assert len(result) == 3
    # Then 2
    assert idset(result[0]) == {a.id, b.id}
    # Then 3
    assert result[1] == 2
    assert result[2] == 1


# [claude] NSV-L-02
def test_nsv_l_02__unread_only_reaches_the_dao(db, w1, ua, mk_note):
    """NSV-L-02 — unread_only reaches the DAO.
    Rules: `list_for_user` R1"""
    a = mk_note()
    mk_note(**READ)
    commit_point(db)
    result = svc.list_for_user(db, workspace_id=w1.id, user_id=ua.id, unread_only=True)

    # Then 1
    assert idset(result[0]) == {a.id}


# [claude] NSV-L-03
def test_nsv_l_03__with_the_defaults_51_notifications_give_a_page_of_50(db, w1, ua, mk_notes):
    """NSV-L-03 — with the defaults 51 notifications give a page of 50.
    Rules: `list_for_user` R1"""
    mk_notes(51)
    commit_point(db)
    result = svc.list_for_user(db, workspace_id=w1.id, user_id=ua.id)

    # Then 1
    assert len(result[0]) == 50
    # Then 2
    assert result[1] == 51


# [claude] NSV-L-04
def test_nsv_l_04__skip_and_limit_reach_the_dao(db, w1, ua, mk_notes):
    """NSV-L-04 — skip and limit reach the DAO.
    Rules: `list_for_user` R1"""
    mk_notes(3)
    commit_point(db)
    result = svc.list_for_user(db, workspace_id=w1.id, user_id=ua.id, skip=2, limit=1000)

    # Then 1
    assert len(result[0]) == 1
    # Then 2
    assert result[1] == 3


# [claude] NSV-L-05
def test_nsv_l_05__nothing_is_written_committed_or_rolled_back(db, w1, ua, mk_note):
    """NSV-L-05 — nothing is written, committed or rolled back.
    Rules: `list_for_user` R2"""
    a = mk_note()
    commit_point(db)
    p = mk_note()
    with spies(db) as (cm, rb):
        result = svc.list_for_user(db, workspace_id=w1.id, user_id=ua.id)

    # Then 1
    assert idset(result[0]) == {a.id, p.id}
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    db.rollback()
    assert reread(db, a).is_read is False
    # Then 5
    assert count_notes(db) == 1


# [claude] NSV-L-06
@pytest.mark.xfail(strict=False, reason="BUG-1412: Notifications with one timestamp come back in no fixed order")
def test_nsv_l_06__pass_through_bug_1412_on_a_tie_the_higher_id_comes_first(db, w1, ua, mk_note):
    """NSV-L-06 — pass-through BUG-1412: on a tie the higher id comes first.
    Rules: `list_for_user` R1 [BUG-1412]"""
    a = mk_note(created_at=T2)
    b = mk_note(created_at=T2)
    c = mk_note(created_at=T2)
    a.preview = "edited"
    db.flush()
    commit_point(db)
    result = svc.list_for_user(db, workspace_id=w1.id, user_id=ua.id)

    # Then 1
    assert len(result[0]) == 3
    # Then 2
    assert [r.id for r in result[0]] == [c.id, b.id, a.id]


# [claude] NSV-L-07
def test_nsv_l_07__a_negative_limit_raises_the_daos_dataerror(db, w1, ua, mk_note):
    """NSV-L-07 — a negative limit raises the DAO's DataError.
    Rules: `list_for_user` R1, Errors"""
    mk_note()
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(DataError):
        with db.begin_nested():
            svc.list_for_user(db, workspace_id=w1.id, user_id=ua.id, limit=-1)
    # Then 2
    assert written(db) == before


# --------------------------------------------------------------------------- #
# NotificationService.mark_read
# --------------------------------------------------------------------------- #

# [claude] NSV-M-01
def test_nsv_m_01__ids_omitted_marks_all_the_users_unread_notifications_and_commits(
    db, w1, w2, ua, ub, mk_note,
):
    """NSV-M-01 — ids omitted marks all the user's unread notifications and commits.
    Rules: `mark_read` R1, R2"""
    a = mk_note()
    b = mk_note()
    c = mk_note(recipient_user_id=ub.id)
    z = mk_note(workspace_id=w2.id)
    commit_point(db)
    result = svc.mark_read(db, workspace_id=w1.id, user_id=ua.id, data=MarkReadRequest())

    # Then 1
    assert result == 2
    # Then 2
    db.rollback()
    row = reread(db, a)
    assert row.is_read is True
    assert row.read_at is not None
    # Then 3
    assert reread(db, b).is_read is True
    # Then 4
    assert reread(db, c).is_read is False
    # Then 5
    assert reread(db, z).is_read is False


# [claude] NSV-M-02
def test_nsv_m_02__ids_none_marks_all_like_omitted(db, w1, ua, mk_note):
    """NSV-M-02 — ids=None marks all, like omitted.
    Rules: `mark_read` R1"""
    mk_note()
    mk_note()
    commit_point(db)
    result = svc.mark_read(db, workspace_id=w1.id, user_id=ua.id, data=MarkReadRequest(ids=None))

    # Then 1
    assert result == 2


# [claude] NSV-M-03
def test_nsv_m_03__named_ids_mark_only_those(db, w1, ua, mk_note):
    """NSV-M-03 — named ids mark only those.
    Rules: `mark_read` R1"""
    a = mk_note()
    b = mk_note()
    commit_point(db)
    result = svc.mark_read(db, workspace_id=w1.id, user_id=ua.id, data=MarkReadRequest(ids=[a.id]))

    # Then 1
    assert result == 1
    # Then 2
    db.rollback()
    assert reread(db, a).is_read is True
    # Then 3
    assert reread(db, b).is_read is False


# [claude] NSV-M-04
def test_nsv_m_04__another_persons_notification_is_not_marked(db, w1, ua, ub, mk_note):
    """NSV-M-04 — another person's notification is not marked.
    Rules: `mark_read` R1"""
    c = mk_note(recipient_user_id=ub.id)
    commit_point(db)
    before_c = snap_before(db, c)
    result = svc.mark_read(db, workspace_id=w1.id, user_id=ua.id, data=MarkReadRequest(ids=[c.id]))

    # Then 1
    assert result == 0
    # Then 2
    assert snap(db, c) == before_c


# [claude] NSV-M-06
def test_nsv_m_06__a_failing_commit_reaches_the_caller_unchanged_no_rollback_nothing_saved(db, w1, ua, mk_note):
    """NSV-M-06 — a failing commit reaches the caller unchanged; no rollback; nothing saved.
    Rules: `mark_read` R4"""
    a = mk_note()
    commit_point(db)
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "commit", side_effect=RuntimeError("boom")), \
                patch.object(db, "rollback", wraps=db.rollback) as rb:
            svc.mark_read(db, workspace_id=w1.id, user_id=ua.id, data=MarkReadRequest())
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count == 0
    # Then 3
    db.rollback()
    assert reread(db, a).is_read is False


# [claude] NSV-M-07
@pytest.mark.xfail(strict=True, reason="BUG-1414: Marking an empty list of notifications read marks all of them")
def test_nsv_m_07__pass_through_bug_1414_an_empty_list_marks_nothing(db, w1, ua, mk_note):
    """NSV-M-07 — pass-through BUG-1414: an empty list marks nothing.
    Rules: `mark_read` R1 [BUG-1414]"""
    a = mk_note()
    mk_note()
    commit_point(db)
    result = svc.mark_read(db, workspace_id=w1.id, user_id=ua.id, data=MarkReadRequest(ids=[]))

    # Then 1
    assert result == 0
    # Then 2
    db.rollback()
    assert reread(db, a).is_read is False


# [claude] NSV-M-08
@pytest.mark.xfail(strict=True, reason="BUG-1413: A notification's read time depends on the database's time zone")
def test_nsv_m_08__pass_through_bug_1413_read_at_read_as_utc_is_the_moment_of_the_call(db, w1, ua, mk_note):
    """NSV-M-08 — pass-through BUG-1413: read_at read as UTC is the moment of the call.
    Rules: `mark_read` R1 [BUG-1413]"""
    db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))
    a = mk_note()
    commit_point(db)
    with patch("app.dao.notification.utcnow", return_value=NOW):
        result = svc.mark_read(db, workspace_id=w1.id, user_id=ua.id, data=MarkReadRequest())

    # Then 1
    assert result == 1
    # Then 2
    db.expire_all()
    assert utc_read(db, a) == NOW


# [claude] NSV-M-09
def test_nsv_m_09__a_second_call_marks_nothing(db, w1, ua, mk_note):
    """NSV-M-09 — a second call marks nothing.
    Rules: `mark_read` R1, R2"""
    a = mk_note()
    commit_point(db)
    svc.mark_read(db, workspace_id=w1.id, user_id=ua.id, data=MarkReadRequest())
    result = svc.mark_read(db, workspace_id=w1.id, user_id=ua.id, data=MarkReadRequest())

    # Then 1
    assert result == 0
    # Then 2
    db.rollback()
    assert reread(db, a).is_read is True


# [claude] NSV-M-10
def test_nsv_m_10__a_row_loaded_before_the_call_reads_true_afterwards_the_commit_expired_it(db, w1, ua, mk_note):
    """NSV-M-10 — a row loaded before the call reads True afterwards: the commit expired it.
    Rules: `mark_read` R3"""
    a = mk_note()
    commit_point(db)
    db.refresh(a)
    result = svc.mark_read(db, workspace_id=w1.id, user_id=ua.id, data=MarkReadRequest(ids=[a.id]))

    # Then 1
    assert result == 1
    # Then 2
    assert a.is_read is True


# [claude] NSV-M-11
def test_nsv_m_11__a_failing_update_reaches_the_caller_unchanged_no_commit_no_rollback_nothing_saved(
    db, w1, ua, mk_note,
):
    """NSV-M-11 — a failing update reaches the caller unchanged; no commit, no rollback; nothing saved.
    Rules: `mark_read` R4"""
    a = mk_note()
    commit_point(db)
    with pytest.raises(RuntimeError) as exc:
        with patch.object(notification_dao, "mark_read", side_effect=RuntimeError("boom")), spies(db) as (cm, rb):
            svc.mark_read(db, workspace_id=w1.id, user_id=ua.id, data=MarkReadRequest())
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    db.rollback()
    assert reread(db, a).is_read is False


# --------------------------------------------------------------------------- #
# NotificationService.fan_out_mentions
# --------------------------------------------------------------------------- #

# [claude] NSV-F-01
def test_nsv_f_01__each_mentioned_active_member_gets_one_notification_with_every_field(db, w1, ua, ub, un):
    """NSV-F-01 — each mentioned active member gets one notification with every field.
    Rules: `fan_out_mentions` R1, R7"""
    commit_point(db)
    result = svc.fan_out_mentions(
        db, workspace_id=w1.id, actor_user_id=un.id, mentioned_user_ids=[ua.id, ub.id],
        entity_type="purchase_order", entity_id=12, source_id=77, preview="hi @Ann",
    )
    rows = mentions(db, w1)

    # Then 1
    assert result is None
    # Then 2
    assert {n.recipient_user_id for n in rows} == {ua.id, ub.id}
    # Then 3
    assert len(rows) == 2
    # Then 4
    for n in rows:
        assert n.workspace_id == w1.id
        assert n.actor_user_id == un.id
        assert n.entity_type == "purchase_order"
        assert n.entity_id == 12
    # Then 5
    for n in rows:
        assert n.source_type == "discussion"
        assert n.preview == "hi @Ann"
        assert n.is_read is False


# [claude] NSV-F-02
def test_nsv_f_02__preview_defaults_to_none(db, w1, ua, un):
    """NSV-F-02 — preview defaults to None.
    Rules: `fan_out_mentions` R1"""
    commit_point(db)
    svc.fan_out_mentions(
        db, workspace_id=w1.id, actor_user_id=un.id, mentioned_user_ids=[ua.id],
        entity_type="purchase_order", entity_id=12, source_id=77,
    )
    rows = mentions(db, w1)

    # Then 1
    assert len(rows) == 1
    # Then 2
    assert rows[0].preview is None


# [claude] NSV-F-03
def test_nsv_f_03__suspended_invited_other_workspace_and_unknown_ids_are_skipped_without_error(
    db, w1, ua, us, ui, uo, un,
):
    """NSV-F-03 — suspended, invited, other-workspace and unknown ids are skipped without error.
    Rules: `fan_out_mentions` R2"""
    commit_point(db)
    result = svc.fan_out_mentions(
        db, workspace_id=w1.id, actor_user_id=un.id, mentioned_user_ids=[us.id, ui.id, uo.id, MISSING, ua.id],
        entity_type="purchase_order", entity_id=12, source_id=77,
    )
    rows = mentions(db, w1)

    # Then 1
    assert result is None
    # Then 2
    assert {n.recipient_user_id for n in rows} == {ua.id}


# [claude] NSV-F-04
@pytest.mark.xfail(strict=True, reason="BUG-1535: Mentioning yourself sends you a notification")
def test_nsv_f_04__the_actor_is_never_notified_of_their_own_mention(db, w1, ua, ub):
    """NSV-F-04 — the actor is never notified of their own mention.
    Rules: `fan_out_mentions` R4 [BUG-1535]"""
    commit_point(db)
    svc.fan_out_mentions(
        db, workspace_id=w1.id, actor_user_id=ua.id, mentioned_user_ids=[ua.id, ub.id],
        entity_type="purchase_order", entity_id=12, source_id=77,
    )
    rows = mentions(db, w1)

    # Then 1
    assert {n.recipient_user_id for n in rows} == {ub.id}


# [claude] NSV-F-05
def test_nsv_f_05__an_id_listed_twice_gets_one_notification(db, w1, ua, un):
    """NSV-F-05 — an id listed twice gets one notification.
    Rules: `fan_out_mentions` R3"""
    commit_point(db)
    svc.fan_out_mentions(
        db, workspace_id=w1.id, actor_user_id=un.id, mentioned_user_ids=[ua.id, ua.id],
        entity_type="purchase_order", entity_id=12, source_id=77,
    )
    rows = mentions(db, w1)

    # Then 1
    assert len(rows) == 1


# [claude] NSV-F-06
def test_nsv_f_06__an_empty_list_creates_nothing(db, w1, un):
    """NSV-F-06 — an empty list creates nothing.
    Rules: `fan_out_mentions` R5"""
    commit_point(db)
    before = written(db)
    result = svc.fan_out_mentions(
        db, workspace_id=w1.id, actor_user_id=un.id, mentioned_user_ids=[],
        entity_type="purchase_order", entity_id=12, source_id=77,
    )

    # Then 1
    assert result is None
    # Then 2
    assert written(db) == before


# [claude] NSV-F-07
def test_nsv_f_07__the_rows_are_flushed_into_the_callers_transaction_not_committed(db, w1, ua, un):
    """NSV-F-07 — the rows are flushed into the caller's transaction, not committed.
    Rules: `fan_out_mentions` R6"""
    commit_point(db)
    with spies(db) as (cm, rb):
        svc.fan_out_mentions(
            db, workspace_id=w1.id, actor_user_id=un.id, mentioned_user_ids=[ua.id],
            entity_type="purchase_order", entity_id=12, source_id=77,
        )
    rows = mentions(db, w1)

    # Then 1
    assert len(rows) == 1
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    db.rollback()
    assert count_notes(db) == 0


# [claude] NSV-F-08
def test_nsv_f_08__another_workspaces_call_does_not_notify_this_workspaces_members(db, w2, ua, uo, un):
    """NSV-F-08 — another workspace's call does not notify this workspace's members.
    Rules: `fan_out_mentions` R1, R2"""
    commit_point(db)
    svc.fan_out_mentions(
        db, workspace_id=w2.id, actor_user_id=un.id, mentioned_user_ids=[ua.id, uo.id],
        entity_type="purchase_order", entity_id=12, source_id=77,
    )

    # Then 1
    assert count_notes(db, source_id=77) == 1
    # Then 2
    db.expire_all()
    row = db.execute(select(Notification).where(Notification.source_id == 77)).scalar_one()
    assert row.recipient_user_id == uo.id
    assert row.workspace_id == w2.id


# [claude] NSV-F-09
def test_nsv_f_09__a_database_error_reaches_the_caller_unchanged(db, w1, ua):
    """NSV-F-09 — a database error reaches the caller unchanged.
    Rules: `fan_out_mentions` R6, Errors"""
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            svc.fan_out_mentions(
                db, workspace_id=w1.id, actor_user_id=MISSING, mentioned_user_ids=[ua.id],
                entity_type="purchase_order", entity_id=12, source_id=77,
            )
    # Then 2
    assert exc.value.orig.pgcode == "23503"
    # Then 3
    assert written(db) == before


# [claude] NSV-F-10
def test_nsv_f_10__on_a_database_error_the_function_neither_commits_nor_rolls_back(db, w1, ua):
    """NSV-F-10 — on a database error the function neither commits nor rolls back.
    Rules: `fan_out_mentions` R6, Errors"""
    commit_point(db)
    with spies(db) as (cm, rb):
        # Then 1
        with pytest.raises(IntegrityError) as exc:
            with db.begin_nested():
                svc.fan_out_mentions(
                    db, workspace_id=w1.id, actor_user_id=MISSING, mentioned_user_ids=[ua.id],
                    entity_type="purchase_order", entity_id=12, source_id=77,
                )
    # Then 2
    assert exc.value.orig.pgcode == "23503"
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert rb.call_count == 0
