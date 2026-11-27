"""Unit tests for app/services/discussion_service.py.

Implements tests/unit/services/discussion_service.cases.md (revision 2), one test
per case, in card order. Real Postgres session (`db` fixture): a `commit()` only
releases a savepoint, so the service's commit is safe and the fixture's outer
rollback discards everything. Nothing is patched except what Conventions name:
the commit / rollback spies (which still call the real method) and the failing
commit of DSS-C-27. The statement recorder of DSS-L-14 only listens.

Normal mode: every test is written from its card and carries a `# [claude] <ID>`
comment. Row names of the cards are the lower-case names here (UA -> ua, R1 -> r1,
`W1.id` -> `w1.id`); `# Then N` marks the checks of the card's Then line N.
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with patch.object(...)`)
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from sqlalchemy import event, func, inspect, select, text
from sqlalchemy.exc import DataError, DBAPIError, IntegrityError, PendingRollbackError

from app.core.exceptions import NotFoundError
from app.core.exceptions import ValidationError as AppValidationError
from app.models.discussion import Discussion
from app.models.enums import DiscussionEntityType as ET
from app.models.factory import Factory
from app.models.help_ticket import HelpTicket
from app.models.item import Item
from app.models.notification import Notification
from app.models.project import Project
from app.models.project_component import ProjectComponent
from app.models.project_member import ProjectMember
from app.models.purchase_order import PurchaseOrder
from app.models.status import Status
from app.models.workspace_member import WorkspaceMember
from app.schemas.discussion import DiscussionCreate
from app.services.discussion_service import _extract_mentions, discussion_service
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "svc = the singleton discussion_service"
svc = discussion_service

MISSING = 999999999


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
def uo(db, us):
    return make_profile(db, name="Otto")


def _member(db, ws, profile, status):
    return _add(db, WorkspaceMember(workspace_id=ws.id, user_id=profile.id, role="member", status=status))


# Convention "Memberships": UA, UB active in W1; US suspended in W1; UO active in W2
@pytest.fixture
def memberships(db, w1, w2, ua, ub, us, uo):
    _member(db, w1, ua, "active")
    _member(db, w1, ub, "active")
    _member(db, w1, us, "suspended")
    _member(db, w2, uo, "active")


@pytest.fixture
def f1(db, w1, memberships):
    return _add(db, Factory(workspace_id=w1.id, name="Factory One", abbreviation="F1"))


@pytest.fixture
def f9(db, w2, f1):
    return _add(db, Factory(workspace_id=w2.id, name="Factory Nine", abbreviation="F9"))


@pytest.fixture
def p1(db, w1, f1, f9):
    return _add(db, Project(workspace_id=w1.id, factory_id=f1.id, name="Project One", description="Main"))


@pytest.fixture
def p9(db, w2, f9, p1):
    return _add(db, Project(workspace_id=w2.id, factory_id=f9.id, name="Project Nine", description="Main"))


# Conventions "Standing rows": in every test, no Given line needed
@pytest.fixture(autouse=True)
def standing_rows(p9):
    pass


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #

def _msg_fields(w1, p1, ua, but):
    fields = {
        "workspace_id": w1.id, "entity_type": "project", "entity_id": p1.id, "user_id": ua.id, "message": "Hello",
    }
    fields.update(but)
    return fields


# Convention "msg": after "but" every column that differs
@pytest.fixture
def mk_msg(db, w1, p1, ua):
    def _mk(**but):
        return _add(db, Discussion(**_msg_fields(w1, p1, ua, but)))
    return _mk


# Convention "reply on R"
@pytest.fixture
def mk_reply(mk_msg):
    def _mk(parent, **but):
        return mk_msg(parent_id=parent.id, **but)
    return _mk


# Convention "n messages, by add_all"
@pytest.fixture
def mk_msgs(db, w1, p1, ua):
    def _mk(n):
        rows = [Discussion(**_msg_fields(w1, p1, ua, {"message": f"m{k:02d}"})) for k in range(n)]
        db.add_all(rows)
        db.flush()
        return rows
    return _mk


# Convention "XM": msg, but message "Extra" (after the commit point)
@pytest.fixture
def mk_xm(mk_msg):
    def _mk():
        return mk_msg(message="Extra")
    return _mk


# Convention "project": the card gives name and any other column
@pytest.fixture
def mk_project(db, w1, f1):
    def _mk(name, **cols):
        return _add(db, Project(workspace_id=w1.id, factory_id=f1.id, description="Main", name=name, **cols))
    return _mk


# Convention "item"
@pytest.fixture
def mk_item(db, w1):
    def _mk(**but):
        fields = {"workspace_id": w1.id, "name": "Bolt M8", "name_normalized": "bolt m8", "unit": "pcs", "is_active": True}
        fields.update(but)
        return _add(db, Item(**fields))
    return _mk


# Convention "stage"
@pytest.fixture
def mk_stage(db, w1):
    def _mk():
        return _add(db, Status(workspace_id=w1.id, name="Draft", comment="A note"))
    return _mk


# Convention "purchase on S"
@pytest.fixture
def mk_purchase(db, w1, ua):
    def _mk(stage):
        return _add(db, PurchaseOrder(
            workspace_id=w1.id, po_number="PO-1", destination_type="storage", destination_id=1, subtotal=0,
            total_amount=0, current_status_id=stage.id, created_by=ua.id,
        ))
    return _mk


# Convention "ticket"
@pytest.fixture
def mk_ticket(db, w1, ua):
    def _mk(**but):
        fields = {
            "workspace_id": w1.id, "ticket_number": "HELP-2026-001", "title": "Printer jam",
            "description": "It jams", "created_by": ua.id,
        }
        fields.update(but)
        return _add(db, HelpTicket(**fields))
    return _mk


# Convention "person N as R": a profile with an active W1 membership of role R
@pytest.fixture
def mk_person(db, w1):
    def _mk(name, role):
        person = make_profile(db, name=name)
        _add(db, WorkspaceMember(workspace_id=w1.id, user_id=person.id, role=role, status="active"))
        return person
    return _mk


# Convention "admin PA": a platform admin with no membership anywhere
@pytest.fixture
def mk_admin(db):
    def _mk():
        pa = make_profile(db, name="Pat")
        pa.is_platform_admin = True
        db.flush()
        return pa
    return _mk


# Convention "W1 owner is U" (and C-48's `W2.owner_user_id = UB.id`)
def set_owner(db, ws, profile):
    ws.owner_user_id = profile.id
    db.flush()


# Convention "private project": project, but visibility "invited_only", created_by UA; the card gives name
@pytest.fixture
def mk_private_project(mk_project, ua):
    def _mk(name):
        return mk_project(name, visibility="invited_only", created_by=ua.id)
    return _mk


# Convention "component of P"
@pytest.fixture
def mk_component(db, w1):
    def _mk(project):
        return _add(db, ProjectComponent(workspace_id=w1.id, project_id=project.id, name="Frame"))
    return _mk


# Convention "invite U to P"
@pytest.fixture
def invite(db, w1):
    def _mk(profile, project):
        return _add(db, ProjectMember(workspace_id=w1.id, project_id=project.id, user_id=profile.id))
    return _mk


# Convention "older(X, h)"
def older(db, row, h):
    db.execute(
        text("UPDATE discussions SET created_at = now() - make_interval(hours => :h) WHERE id = :i"),
        {"h": h, "i": row.id},
    )
    db.expire_all()


# Convention "bumpD(X)"
def bump_d(db, row):
    db.execute(text("UPDATE discussions SET message = message || '!' WHERE id = :i"), {"i": row.id})
    db.expire_all()


# Convention "seqscan"
def seqscan(db):
    db.execute(text("SET LOCAL enable_indexscan = off"))
    db.execute(text("SET LOCAL enable_bitmapscan = off"))
    db.execute(text("SET LOCAL enable_indexonlyscan = off"))


# Convention "commit point"
def commit_point(db):
    db.commit()


# --------------------------------------------------------------------------- #
# Conventions -> named checks
# --------------------------------------------------------------------------- #

# Convention "re-read X": expire, then SELECT by id
def reread(db, model, row_id):
    db.expire_all()
    return db.execute(select(model).where(model.id == row_id)).scalar_one_or_none()


# Convention "ids(x)"
def ids(rows):
    return sorted(r.id for r in rows)


# Convention "order(x)"
def order(rows):
    return [r.id for r in rows]


# Convention "reply_ids(r)"
def reply_ids(row):
    return [x.id for x in row.replies]


# Convention "notes(M)": a fresh SELECT of the mention notifications of message M
#   ("notes(M) with recipient_user_id == U.id" adds that filter: `recipient=U.id`)
def notes(db, mid, recipient=None):
    db.expire_all()
    query = select(Notification).where(Notification.source_type == "discussion", Notification.source_id == mid)
    if recipient is not None:
        query = query.where(Notification.recipient_user_id == recipient)
    return list(db.execute(query.order_by(Notification.id)).scalars())


# Convention "recipients(M)"
def recipients(db, mid):
    return sorted(n.recipient_user_id for n in notes(db, mid))


# Convention "count:" lines: a fresh query with the filter stated
def count_discussions(db, **filters):
    query = select(func.count()).select_from(Discussion)
    for column, value in filters.items():
        query = query.where(getattr(Discussion, column) == value)
    return db.execute(query).scalar_one()


def count_notifications(db, **filters):
    query = select(func.count()).select_from(Notification)
    for column, value in filters.items():
        query = query.where(getattr(Notification, column) == value)
    return db.execute(query).scalar_one()


# Convention "loaded:"
def unloaded(result):
    return inspect(result).unloaded


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


# Convention "selects": the text of every recorded SELECT
def selects_of(sql_log):
    return [s for s in sql_log if s.lstrip().upper().startswith("SELECT")]


# --------------------------------------------------------------------------- #
# _extract_mentions
# --------------------------------------------------------------------------- #

# [claude] DSS-X-01
def test_dss_x_01__every_token_gives_its_id_in_order_duplicates_kept():
    """DSS-X-01 — every token gives its id, in order, duplicates kept.
    Rules: `_extract_mentions` R1"""
    result = _extract_mentions("hi @[5] and @[12] @[5]")

    # Then 1
    assert result == [5, 12, 5]


# [claude] DSS-X-02
def test_dss_x_02__a_message_without_a_token_gives_an_empty_list():
    """DSS-X-02 — a message without a token gives an empty list.
    Rules: `_extract_mentions` R1"""
    result = _extract_mentions("hello @Bob [5]")

    # Then 1
    assert result == []


# [claude] DSS-X-03
def test_dss_x_03__malformed_tokens_give_nothing():
    """DSS-X-03 — malformed tokens give nothing.
    Rules: `_extract_mentions` R1"""
    result = _extract_mentions("@[] @[a1] @5 @[ 5] @[-5]")

    # Then 1
    assert result == []


# [claude] DSS-X-04
def test_dss_x_04__leading_zeros_are_read_as_the_number():
    """DSS-X-04 — leading zeros are read as the number.
    Rules: `_extract_mentions` R1"""
    result = _extract_mentions("ping @[007]")

    # Then 1
    assert result == [7]


# [claude] DSS-X-05
@pytest.mark.xfail(strict=True, reason="BUG-1536: Non-ASCII digits inside `@[…]` make a mention")
def test_dss_x_05__bengali_and_arabic_indic_digits_make_no_token():
    """DSS-X-05 — Bengali and Arabic-Indic digits make no token.
    Rules: `_extract_mentions` R2 [BUG-1536]"""
    result = _extract_mentions("hi @[১২] and @[١٢]")

    # Then 1
    assert result == []


# --------------------------------------------------------------------------- #
# DiscussionService.list
# --------------------------------------------------------------------------- #

# [claude] DSS-L-01
def test_dss_l_01__the_records_top_level_messages_of_the_workspace_with_the_count(db, w1, w2, p1, mk_msg, mk_reply):
    """DSS-L-01 — the record's top-level messages of the workspace, with the count, defaults skip 0 and limit 50.
    Rules: `list` R1"""
    r1 = mk_msg()
    mk_reply(r1)
    mk_msg(entity_id=MISSING)
    mk_msg(entity_type="machine")
    mk_msg(workspace_id=w2.id)
    r2 = mk_msg(message="Second")
    commit_point(db)
    result = svc.list(db, w1.id, ET("project"), p1.id)
    items, total = result[0], result[1]

    # Then 1
    assert isinstance(result, tuple)
    # Then 2
    assert ids(items) == [r1.id, r2.id]
    # Then 3
    assert total == 2


# [claude] DSS-L-02
def test_dss_l_02__with_the_default_limit_51_roots_give_50_and_the_full_count(db, w1, p1, mk_msgs):
    """DSS-L-02 — with the default limit, 51 roots give 50 and the full count.
    Rules: `list` R1"""
    mk_msgs(51)
    commit_point(db)
    result = svc.list(db, w1.id, ET("project"), p1.id)
    items, total = result[0], result[1]

    # Then 1
    assert len(items) == 50
    # Then 2
    assert total == 51


# [claude] DSS-L-03
def test_dss_l_03__skip_and_limit_are_passed_on(db, w1, p1, mk_msg):
    """DSS-L-03 — skip and limit are passed on: skip=1 with limit=1000.
    Rules: `list` R1"""
    mk_msg()
    mk_msg(message="Second")
    commit_point(db)
    result = svc.list(db, w1.id, ET("project"), p1.id, skip=1, limit=1000)
    items, total = result[0], result[1]

    # Then 1
    assert len(items) == 1
    # Then 2
    assert total == 2


# [claude] DSS-L-17
def test_dss_l_17__limit_is_passed_on_unchanged_limit_51_of_52_roots_gives_51(db, w1, p1, mk_msgs):
    """DSS-L-17 — limit is passed on unchanged: limit=51 of 52 roots gives 51.
    Rules: `list` R1"""
    mk_msgs(52)
    commit_point(db)
    result = svc.list(db, w1.id, ET("project"), p1.id, limit=51)
    items, total = result[0], result[1]

    # Then 1
    assert len(items) == 51
    # Then 2
    assert total == 52


# [claude] DSS-L-04
def test_dss_l_04__a_negative_limit_raises_data_error_and_leaves_the_session_aborted(db, w1, p1, mk_msg):
    """DSS-L-04 — a negative limit raises DataError and leaves the session aborted.
    Rules: `list` R4, Errors; D4"""
    mk_msg()
    commit_point(db)
    # Then 1
    with pytest.raises(DataError):
        svc.list(db, w1.id, ET("project"), p1.id, skip=0, limit=-1)
    # Then 2
    with pytest.raises(DBAPIError):
        db.execute(text("SELECT 1"))


# [claude] DSS-L-05
def test_dss_l_05__the_list_neither_commits_nor_rolls_back(db, w1, p1, mk_msg, mk_xm):
    """DSS-L-05 — the list neither commits nor rolls back.
    Rules: `list` R4; D4"""
    r1 = mk_msg()
    commit_point(db)
    xm = mk_xm()
    r1.message = "Edited"
    with spies(db) as (cm, rb):
        result = svc.list(db, w1.id, ET("project"), p1.id)
    items = result[0]

    # Then 1
    assert xm.id in [r.id for r in items]
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert r1 in db.dirty
    # Then 5
    db.rollback()
    assert count_discussions(db, message="Extra") == 0


# [claude] DSS-L-06
def test_dss_l_06__the_thread_of_a_purchase_order_is_listed(db, w1, mk_msg, mk_stage, mk_purchase):
    """DSS-L-06 — the thread of a purchase order (no soft delete) is listed.
    Rules: `list` R1, R3"""
    s = mk_stage()
    o = mk_purchase(s)
    m = mk_msg(entity_type="purchase_order", entity_id=o.id)
    commit_point(db)
    result = svc.list(db, w1.id, ET("purchase_order"), o.id)
    items, total = result[0], result[1]

    # Then 1
    assert ids(items) == [m.id]
    # Then 2
    assert total == 1


# [claude] DSS-L-07
def test_dss_l_07__the_thread_of_a_live_item_is_listed(db, w1, mk_msg, mk_item):
    """DSS-L-07 — the thread of a live item is listed.
    Rules: `list` R1, R3"""
    i = mk_item()
    m = mk_msg(entity_type="item", entity_id=i.id)
    commit_point(db)
    result = svc.list(db, w1.id, ET("item"), i.id)
    items, total = result[0], result[1]

    # Then 1
    assert ids(items) == [m.id]
    # Then 2
    assert total == 1


# [claude] DSS-L-08
@pytest.mark.xfail(
    strict=True,
    reason="BUG-1686: Discussions are posted and listed on records that do not exist or belong to another workspace",
)
def test_dss_l_08__an_unknown_record_is_not_found(db, w1, mk_msg):
    """DSS-L-08 — an unknown record is not found.
    Rules: `list` R2 [BUG-1686], Errors"""
    mk_msg(entity_id=MISSING)
    commit_point(db)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.list(db, w1.id, ET("project"), MISSING)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Record not found"


# [claude] DSS-L-09
@pytest.mark.xfail(
    strict=True,
    reason="BUG-1686: Discussions are posted and listed on records that do not exist or belong to another workspace",
)
def test_dss_l_09__another_workspaces_record_is_not_found(db, w1, p9, mk_msg):
    """DSS-L-09 — another workspace's record is not found.
    Rules: `list` R2 [BUG-1686], Errors"""
    mk_msg(entity_id=p9.id)
    commit_point(db)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.list(db, w1.id, ET("project"), p9.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Record not found"


# [claude] DSS-L-10
@pytest.mark.xfail(strict=True, reason="BUG-1687: A soft-deleted record's discussion is still listed and posted to")
def test_dss_l_10__a_soft_deleted_project_is_not_found(db, w1, mk_msg, mk_project):
    """DSS-L-10 — a soft-deleted project is not found.
    Rules: `list` R3 [BUG-1687], Errors"""
    pd = mk_project("Old Project", is_deleted=True)
    mk_msg(entity_id=pd.id)
    commit_point(db)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.list(db, w1.id, ET("project"), pd.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Record not found"


# [claude] DSS-L-11
@pytest.mark.xfail(strict=True, reason="BUG-1687: A soft-deleted record's discussion is still listed and posted to")
def test_dss_l_11__an_inactive_item_is_not_found(db, w1, mk_msg, mk_item):
    """DSS-L-11 — an inactive item is not found.
    Rules: `list` R3 [BUG-1687], Errors"""
    i_d = mk_item(is_active=False)
    mk_msg(entity_type="item", entity_id=i_d.id)
    commit_point(db)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.list(db, w1.id, ET("item"), i_d.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Record not found"


# [claude] DSS-L-12
@pytest.mark.xfail(strict=False, reason="BUG-1438: Discussion messages of one time come back in no fixed order")
def test_dss_l_12__pass_through_bug_1438_roots_oldest_first_then_by_id_also_after_an_update(db, w1, p1, mk_msg):
    """DSS-L-12 — pass-through BUG-1438: roots oldest first, then by id, also after an update.
    Rules: `list` R1 [BUG-1438]"""
    r1 = mk_msg()
    r2 = mk_msg(message="Second")
    r3 = mk_msg(message="Third")
    older(db, r3, 1)
    seqscan(db)
    bump_d(db, r1)
    commit_point(db)
    result = svc.list(db, w1.id, ET("project"), p1.id)
    items = result[0]

    # Then 1
    assert ids(items) == [r1.id, r2.id, r3.id]
    # Then 2
    assert order(items) == [r3.id, r1.id, r2.id]


# [claude] DSS-L-13
@pytest.mark.xfail(strict=False, reason="BUG-1439: Replies in a discussion thread have no order")
def test_dss_l_13__pass_through_bug_1439_replies_come_oldest_first_then_by_id(db, w1, p1, mk_msg, mk_reply):
    """DSS-L-13 — pass-through BUG-1439: replies come oldest first, then by id.
    Rules: `list` R1 [BUG-1439]"""
    r = mk_msg()
    a = mk_reply(r)
    b = mk_reply(r, message="Two")
    c = mk_reply(r, message="Three")
    seqscan(db)
    bump_d(db, a)
    commit_point(db)
    result = svc.list(db, w1.id, ET("project"), p1.id)
    items = result[0]

    # Then 1
    assert sorted(reply_ids(items[0])) == [a.id, b.id, c.id]
    # Then 2
    assert reply_ids(items[0]) == [a.id, b.id, c.id]


# [claude] DSS-L-14
@pytest.mark.xfail(strict=True, reason="BUG-1490: A discussion page loads its replies one query per message")
def test_dss_l_14__pass_through_bug_1490_the_replies_are_loaded_with_the_page(db, w1, p1, mk_msg, mk_reply):
    """DSS-L-14 — pass-through BUG-1490: the replies are loaded with the page.
    Rules: `list` R1 [BUG-1490]"""
    r = mk_msg()
    mk_reply(r)
    db.expire_all()
    commit_point(db)
    with record_sql(db) as sql_log:
        result = svc.list(db, w1.id, ET("project"), p1.id)
    items = result[0]
    selects = selects_of(sql_log)

    # Then 1
    assert ids(items) == [r.id]
    # Then 2
    assert any("parent_id IN" in s for s in selects)


BUG_1867 = "BUG-1867: Any member reads and posts on a private project's discussion"
BUG_1868 = "BUG-1868: Any member reads and posts on another member's help ticket discussion"


# [claude] DSS-L-15
@pytest.mark.xfail(strict=True, reason=BUG_1867)
def test_dss_l_15__a_plain_member_gets_404_for_a_private_projects_thread(db, w1, ub, mk_msg, mk_private_project):
    """DSS-L-15 — a plain member gets 404 for a private project's thread.
    Rules: `list` R5 [BUG-1867], Errors"""
    pp = mk_private_project("Secret Project")
    mk_msg(entity_id=pp.id)
    commit_point(db)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.list(db, w1.id, ET("project"), pp.id, user_id=ub.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Record not found"


# [claude] DSS-L-16
@pytest.mark.xfail(strict=True, reason=BUG_1868)
def test_dss_l_16__a_plain_member_gets_404_for_a_help_ticket_they_did_not_create(db, w1, ub, mk_msg, mk_ticket):
    """DSS-L-16 — a plain member gets 404 for a help ticket they did not create.
    Rules: `list` R5a [BUG-1868], Errors"""
    t = mk_ticket()
    mk_msg(entity_type="support_ticket", entity_id=t.id)
    commit_point(db)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.list(db, w1.id, ET("support_ticket"), t.id, user_id=ub.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Record not found"


# [claude] DSS-L-18
@pytest.mark.xfail(strict=True, reason=BUG_1867)
def test_dss_l_18__the_creator_of_a_private_project_gets_its_thread(db, w1, ua, mk_msg, mk_private_project):
    """DSS-L-18 — the creator of a private project gets its thread.
    Rules: `list` R5 [BUG-1867]"""
    pp = mk_private_project("Secret Project")
    m = mk_msg(entity_id=pp.id)
    commit_point(db)
    result = svc.list(db, w1.id, ET("project"), pp.id, user_id=ua.id)
    items, total = result[0], result[1]

    # Then 1
    assert ids(items) == [m.id]
    # Then 2
    assert total == 1


# [claude] DSS-L-19
@pytest.mark.xfail(strict=True, reason=BUG_1867)
def test_dss_l_19__the_workspace_owner_gets_a_private_projects_thread(
    db, w1, mk_msg, mk_person, mk_private_project,
):
    """DSS-L-19 — the workspace owner gets a private project's thread.
    Rules: `list` R5 [BUG-1867]"""
    uw = mk_person("Wes", "member")
    set_owner(db, w1, uw)
    pp = mk_private_project("Secret Project")
    m = mk_msg(entity_id=pp.id)
    commit_point(db)
    result = svc.list(db, w1.id, ET("project"), pp.id, user_id=uw.id)
    items, total = result[0], result[1]

    # Then 1
    assert ids(items) == [m.id]
    # Then 2
    assert total == 1


# [claude] DSS-L-20
@pytest.mark.xfail(strict=True, reason=BUG_1867)
def test_dss_l_20__a_member_with_role_owner_gets_a_private_projects_thread(
    db, w1, mk_msg, mk_person, mk_private_project,
):
    """DSS-L-20 — a member with role owner gets a private project's thread.
    Rules: `list` R5 [BUG-1867]"""
    ur = mk_person("Ron", "owner")
    pp = mk_private_project("Secret Project")
    m = mk_msg(entity_id=pp.id)
    commit_point(db)
    result = svc.list(db, w1.id, ET("project"), pp.id, user_id=ur.id)
    items, total = result[0], result[1]

    # Then 1
    assert ids(items) == [m.id]
    # Then 2
    assert total == 1


# [claude] DSS-L-21
@pytest.mark.xfail(strict=True, reason=BUG_1867)
def test_dss_l_21__a_member_with_role_ground_team_manager_gets_a_private_projects_thread(
    db, w1, mk_msg, mk_person, mk_private_project,
):
    """DSS-L-21 — a member with role ground-team-manager gets a private project's thread.
    Rules: `list` R5 [BUG-1867]"""
    um = mk_person("Mia", "ground-team-manager")
    pp = mk_private_project("Secret Project")
    m = mk_msg(entity_id=pp.id)
    commit_point(db)
    result = svc.list(db, w1.id, ET("project"), pp.id, user_id=um.id)
    items, total = result[0], result[1]

    # Then 1
    assert ids(items) == [m.id]
    # Then 2
    assert total == 1


# [claude] DSS-L-22
@pytest.mark.xfail(strict=True, reason=BUG_1867)
def test_dss_l_22__a_person_invited_to_a_private_project_gets_its_thread(
    db, w1, mk_msg, mk_person, mk_private_project, invite,
):
    """DSS-L-22 — a person invited to a private project gets its thread.
    Rules: `list` R5 [BUG-1867]"""
    up = mk_person("Pia", "member")
    pp = mk_private_project("Secret Project")
    invite(up, pp)
    m = mk_msg(entity_id=pp.id)
    commit_point(db)
    result = svc.list(db, w1.id, ET("project"), pp.id, user_id=up.id)
    items, total = result[0], result[1]

    # Then 1
    assert ids(items) == [m.id]
    # Then 2
    assert total == 1


# [claude] DSS-L-23
@pytest.mark.xfail(strict=True, reason=BUG_1867)
def test_dss_l_23__a_workspace_visibility_projects_thread_is_open_to_every_member(db, w1, ub, p1, mk_msg):
    """DSS-L-23 — a workspace-visibility project's thread is open to every member.
    Rules: `list` R5 [BUG-1867]"""
    m = mk_msg()
    commit_point(db)
    result = svc.list(db, w1.id, ET("project"), p1.id, user_id=ub.id)
    items, total = result[0], result[1]

    # Then 1
    assert ids(items) == [m.id]
    # Then 2
    assert total == 1


# [claude] DSS-L-24
@pytest.mark.xfail(strict=True, reason=BUG_1868)
def test_dss_l_24__the_creator_of_a_help_ticket_gets_its_thread(db, w1, ub, mk_msg, mk_ticket):
    """DSS-L-24 — the creator of a help ticket gets its thread.
    Rules: `list` R5a [BUG-1868]"""
    t = mk_ticket(created_by=ub.id)
    m = mk_msg(entity_type="support_ticket", entity_id=t.id)
    commit_point(db)
    result = svc.list(db, w1.id, ET("support_ticket"), t.id, user_id=ub.id)
    items, total = result[0], result[1]

    # Then 1
    assert ids(items) == [m.id]
    # Then 2
    assert total == 1


# [claude] DSS-L-25
@pytest.mark.xfail(strict=True, reason=BUG_1868)
def test_dss_l_25__a_member_with_role_ground_team_manager_gets_any_help_tickets_thread(
    db, w1, mk_msg, mk_person, mk_ticket,
):
    """DSS-L-25 — a member with role ground-team-manager gets any help ticket's thread.
    Rules: `list` R5a [BUG-1868]"""
    um = mk_person("Mia", "ground-team-manager")
    t = mk_ticket()
    m = mk_msg(entity_type="support_ticket", entity_id=t.id)
    commit_point(db)
    result = svc.list(db, w1.id, ET("support_ticket"), t.id, user_id=um.id)
    items, total = result[0], result[1]

    # Then 1
    assert ids(items) == [m.id]
    # Then 2
    assert total == 1


# [claude] DSS-L-26
@pytest.mark.xfail(strict=True, reason=BUG_1868)
def test_dss_l_26__a_member_with_role_owner_gets_any_help_tickets_thread(db, w1, mk_msg, mk_person, mk_ticket):
    """DSS-L-26 — a member with role owner gets any help ticket's thread.
    Rules: `list` R5a [BUG-1868]"""
    ur = mk_person("Ron", "owner")
    t = mk_ticket()
    m = mk_msg(entity_type="support_ticket", entity_id=t.id)
    commit_point(db)
    result = svc.list(db, w1.id, ET("support_ticket"), t.id, user_id=ur.id)
    items, total = result[0], result[1]

    # Then 1
    assert ids(items) == [m.id]
    # Then 2
    assert total == 1


# [claude] DSS-L-27
@pytest.mark.xfail(strict=True, reason=BUG_1868)
def test_dss_l_27__a_platform_admin_with_no_membership_gets_any_help_tickets_thread(
    db, w1, mk_msg, mk_admin, mk_ticket,
):
    """DSS-L-27 — a platform admin with no membership gets any help ticket's thread.
    Rules: `list` R5a [BUG-1868]"""
    pa = mk_admin()
    t = mk_ticket()
    m = mk_msg(entity_type="support_ticket", entity_id=t.id)
    commit_point(db)
    result = svc.list(db, w1.id, ET("support_ticket"), t.id, user_id=pa.id)
    items, total = result[0], result[1]

    # Then 1
    assert ids(items) == [m.id]
    # Then 2
    assert total == 1


# [claude] DSS-L-28
@pytest.mark.xfail(strict=True, reason=BUG_1867)
def test_dss_l_28__a_component_of_a_private_project_a_plain_member_gets_404(
    db, w1, ub, mk_msg, mk_private_project, mk_component,
):
    """DSS-L-28 — a component of a private project: a plain member gets 404.
    Rules: `list` R5b [BUG-1867], Errors"""
    pp = mk_private_project("Secret Project")
    c = mk_component(pp)
    mk_msg(entity_type="project_component", entity_id=c.id)
    commit_point(db)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.list(db, w1.id, ET("project_component"), c.id, user_id=ub.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Record not found"


# [claude] DSS-L-29
@pytest.mark.xfail(strict=True, reason=BUG_1867)
def test_dss_l_29__a_component_of_a_private_project_a_person_invited_to_the_project_gets_its_thread(
    db, w1, mk_msg, mk_person, mk_private_project, invite, mk_component,
):
    """DSS-L-29 — a component of a private project: a person invited to the project gets its thread.
    Rules: `list` R5b [BUG-1867]"""
    up = mk_person("Pia", "member")
    pp = mk_private_project("Secret Project")
    invite(up, pp)
    c = mk_component(pp)
    m = mk_msg(entity_type="project_component", entity_id=c.id)
    commit_point(db)
    result = svc.list(db, w1.id, ET("project_component"), c.id, user_id=up.id)
    items, total = result[0], result[1]

    # Then 1
    assert ids(items) == [m.id]
    # Then 2
    assert total == 1


# [claude] DSS-L-30
@pytest.mark.xfail(strict=True, reason=BUG_1867)
def test_dss_l_30__a_component_of_a_workspace_visibility_project_is_open_to_every_member(
    db, w1, ub, p1, mk_msg, mk_component,
):
    """DSS-L-30 — a component of a workspace-visibility project is open to every member.
    Rules: `list` R5b [BUG-1867]"""
    c = mk_component(p1)
    m = mk_msg(entity_type="project_component", entity_id=c.id)
    commit_point(db)
    result = svc.list(db, w1.id, ET("project_component"), c.id, user_id=ub.id)
    items, total = result[0], result[1]

    # Then 1
    assert ids(items) == [m.id]
    # Then 2
    assert total == 1


# [claude] DSS-L-31
@pytest.mark.xfail(strict=True, reason=BUG_1867)
def test_dss_l_31__another_record_type_purchase_order_keeps_membership_as_its_only_check(
    db, w1, ub, mk_msg, mk_stage, mk_purchase,
):
    """DSS-L-31 — another record type (purchase order) keeps membership as its only check.
    Rules: `list` R5c [BUG-1867]"""
    s = mk_stage()
    o = mk_purchase(s)
    m = mk_msg(entity_type="purchase_order", entity_id=o.id)
    commit_point(db)
    result = svc.list(db, w1.id, ET("purchase_order"), o.id, user_id=ub.id)
    items, total = result[0], result[1]

    # Then 1
    assert ids(items) == [m.id]
    # Then 2
    assert total == 1


# [claude] DSS-L-32
@pytest.mark.xfail(strict=True, reason=BUG_1867)
def test_dss_l_32__a_platform_admin_gets_404_for_a_private_projects_thread(
    db, w1, mk_msg, mk_admin, mk_private_project,
):
    """DSS-L-32 — a platform admin gets 404 for a private project's thread.
    Rules: `list` R5 [BUG-1867], Errors"""
    pa = mk_admin()
    pp = mk_private_project("Secret Project")
    mk_msg(entity_id=pp.id)
    commit_point(db)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.list(db, w1.id, ET("project"), pp.id, user_id=pa.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Record not found"


# [claude] DSS-L-33
@pytest.mark.xfail(strict=True, reason=BUG_1868)
def test_dss_l_33__a_suspended_member_with_role_owner_gets_404_for_a_help_ticket_they_did_not_create(
    db, w1, mk_msg, mk_ticket,
):
    """DSS-L-33 — a suspended member with role owner gets 404 for a help ticket they did not create.
    Rules: `list` R5a [BUG-1868], Errors"""
    uq = make_profile(db, name="Quinn")
    _add(db, WorkspaceMember(workspace_id=w1.id, user_id=uq.id, role="owner", status="suspended"))
    t = mk_ticket()
    mk_msg(entity_type="support_ticket", entity_id=t.id)
    commit_point(db)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.list(db, w1.id, ET("support_ticket"), t.id, user_id=uq.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Record not found"


# --------------------------------------------------------------------------- #
# DiscussionService.create
# --------------------------------------------------------------------------- #

# [claude] DSS-C-01
def test_dss_c_01__a_top_level_message_is_stored_committed_once_and_returned_re_read(db, w1, ua, p1):
    """DSS-C-01 — a top-level message is stored, committed once and returned re-read; no token, no notification.
    Rules: `create` R1, R10, Returns; D1"""
    commit_point(db)
    with spies(db) as (cm, rb):
        result = svc.create(
            db, workspace_id=w1.id, user_id=ua.id,
            data=DiscussionCreate(entity_type=ET("project"), entity_id=p1.id, message="Hello there"),
        )

    # Then 1
    assert "id" not in unloaded(result)
    assert "created_at" not in unloaded(result)
    assert "message" not in unloaded(result)
    mid = result.id
    # Then 2
    assert isinstance(result, Discussion)
    assert result.parent_id is None
    # Then 3
    assert cm.call_count == 1
    # Then 4
    assert rb.call_count == 0
    # Then 5
    db.rollback()
    row = reread(db, Discussion, mid)
    assert row.workspace_id == w1.id
    assert row.entity_type == "project"
    assert row.entity_id == p1.id
    # Then 6
    row = reread(db, Discussion, mid)
    assert row.user_id == ua.id
    assert row.message == "Hello there"
    assert row.parent_id is None
    # Then 7
    assert count_notifications(db, workspace_id=w1.id) == 0


# [claude] DSS-C-02
def test_dss_c_02__the_message_is_stored_as_typed_spaces_kept(db, w1, ua, p1):
    """DSS-C-02 — the message is stored as typed, spaces kept.
    Rules: `create` R1"""
    commit_point(db)
    result = svc.create(
        db, workspace_id=w1.id, user_id=ua.id,
        data=DiscussionCreate(entity_type=ET("project"), entity_id=p1.id, message="  Hello  "),
    )
    mid = result.id

    # Then 1
    assert result.message == "  Hello  "
    # Then 2
    db.rollback()
    assert reread(db, Discussion, mid).message == "  Hello  "


# [claude] DSS-C-03
def test_dss_c_03__a_reply_to_a_top_level_message_of_the_same_record_is_stored_with_its_parent(
    db, w1, ub, p1, mk_msg,
):
    """DSS-C-03 — a reply to a top-level message of the same record is stored with its parent.
    Rules: `create` R8"""
    r = mk_msg()
    commit_point(db)
    result = svc.create(
        db, workspace_id=w1.id, user_id=ub.id,
        data=DiscussionCreate(entity_type=ET("project"), entity_id=p1.id, message="Agreed", parent_id=r.id),
    )
    mid = result.id

    # Then 1
    assert result.parent_id == r.id
    # Then 2
    db.rollback()
    row = reread(db, Discussion, mid)
    assert row.parent_id == r.id
    assert row.user_id == ub.id
    assert row.entity_id == p1.id


# [claude] DSS-C-04
def test_dss_c_04__a_mentioned_member_gets_one_notification_committed_with_the_message(db, w1, ua, ub, p1):
    """DSS-C-04 — a mentioned member gets one notification, committed with the message.
    Rules: `create` R9; D1"""
    commit_point(db)
    result = svc.create(
        db, workspace_id=w1.id, user_id=ua.id,
        data=DiscussionCreate(entity_type=ET("project"), entity_id=p1.id, message=f"Thanks @[{ub.id}] for this"),
    )
    mid = result.id

    # Then 1
    assert result.message == f"Thanks @[{ub.id}] for this"
    # Then 2
    db.rollback()
    assert count_discussions(db, id=mid) == 1
    # Then 3
    assert len(notes(db, mid)) == 1
    # Then 4
    note = notes(db, mid)[0]
    assert note.workspace_id == w1.id
    assert note.recipient_user_id == ub.id
    assert note.actor_user_id == ua.id
    assert note.notification_type == "mention"
    # Then 5
    note = notes(db, mid)[0]
    assert note.entity_type == "project"
    assert note.entity_id == p1.id
    assert note.source_type == "discussion"
    assert note.source_id == mid
    # Then 6
    note = notes(db, mid)[0]
    assert note.preview == "Thanks @Bob for this"
    assert note.is_read is False


# [claude] DSS-C-05
def test_dss_c_05__each_active_member_once_a_suspended_member_and_an_unknown_id_are_skipped(
    db, w1, ua, ub, us, p1,
):
    """DSS-C-05 — each active member once; a suspended member and an unknown id are skipped, and the preview names them as today.
    Rules: `create` R9"""
    commit_point(db)
    result = svc.create(
        db, workspace_id=w1.id, user_id=ua.id,
        data=DiscussionCreate(
            entity_type=ET("project"), entity_id=p1.id, message=f"@[{ub.id}] @[{ub.id}] @[{us.id}] @[{MISSING}]",
        ),
    )
    mid = result.id

    # Then 1
    assert result.id == mid
    # Then 2
    db.rollback()
    assert recipients(db, mid) == [ub.id]
    # Then 3
    assert notes(db, mid)[0].preview == "@Bob @Bob @Sue @User 999999999"


# [claude] DSS-C-06
def test_dss_c_06__a_member_of_another_workspace_only_gets_no_notification(db, w1, ua, uo, p1):
    """DSS-C-06 — a member of another workspace only gets no notification.
    Rules: `create` R9"""
    commit_point(db)
    result = svc.create(
        db, workspace_id=w1.id, user_id=ua.id,
        data=DiscussionCreate(entity_type=ET("project"), entity_id=p1.id, message=f"see @[{uo.id}]"),
    )
    mid = result.id

    # Then 1
    assert result.id == mid
    # Then 2
    db.rollback()
    assert len(notes(db, mid)) == 0


# [claude] DSS-C-07
@pytest.mark.xfail(strict=True, reason="BUG-1535: Mentioning yourself sends you a notification")
def test_dss_c_07__pass_through_bug_1535_the_author_is_not_notified_of_their_own_mention(db, w1, ua, ub, p1):
    """DSS-C-07 — pass-through BUG-1535: the author is not notified of their own mention.
    Rules: `create` R9 [BUG-1535]"""
    commit_point(db)
    result = svc.create(
        db, workspace_id=w1.id, user_id=ua.id,
        data=DiscussionCreate(entity_type=ET("project"), entity_id=p1.id, message=f"@[{ua.id}] and @[{ub.id}]"),
    )
    mid = result.id

    # Then 1
    assert result.id == mid
    # Then 2
    db.rollback()
    assert recipients(db, mid) == [ub.id]


# [claude] DSS-C-08
@pytest.mark.xfail(strict=True, reason="BUG-1534: A mention preview shows the name of anyone on the platform")
def test_dss_c_08__the_preview_names_only_members_of_the_callers_workspace(db, w1, ua, ub, uo, p1):
    """DSS-C-08 — the preview names only members of the caller's workspace.
    Rules: `create` R9 [BUG-1534]"""
    commit_point(db)
    result = svc.create(
        db, workspace_id=w1.id, user_id=ua.id,
        data=DiscussionCreate(entity_type=ET("project"), entity_id=p1.id, message=f"@[{ub.id}] @[{uo.id}]"),
    )
    mid = result.id

    # Then 1
    assert result.id == mid
    # Then 2
    db.rollback()
    assert recipients(db, mid) == [ub.id]
    # Then 3
    assert notes(db, mid)[0].preview == f"@Bob @User {uo.id}"


BUG_1694 = "BUG-1694: Every refused reply crashes with a server error instead of 404 / 400"


# [claude] DSS-C-09
@pytest.mark.xfail(strict=True, reason=BUG_1694)
def test_dss_c_09__parent_id_0_is_not_found(db, w1, ub, p1, mk_msg):
    """DSS-C-09 — parent id 0 is not found.
    Rules: `create` R5 [BUG-1694], Errors row 3"""
    mk_msg()
    commit_point(db)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.create(
            db, workspace_id=w1.id, user_id=ub.id,
            data=DiscussionCreate(entity_type=ET("project"), entity_id=p1.id, message="Reply", parent_id=0),
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Parent discussion not found"


# [claude] DSS-C-10
@pytest.mark.xfail(strict=True, reason=BUG_1694)
def test_dss_c_10__an_unknown_parent_id_is_not_found(db, w1, ub, p1, mk_msg):
    """DSS-C-10 — an unknown parent id is not found.
    Rules: `create` R5 [BUG-1694], Errors row 3"""
    mk_msg()
    commit_point(db)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.create(
            db, workspace_id=w1.id, user_id=ub.id,
            data=DiscussionCreate(entity_type=ET("project"), entity_id=p1.id, message="Reply", parent_id=MISSING),
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Parent discussion not found"


# [claude] DSS-C-11
@pytest.mark.xfail(strict=True, reason=BUG_1694)
def test_dss_c_11__a_parent_of_another_workspace_is_not_found(db, w1, w2, ub, p1, mk_msg):
    """DSS-C-11 — a parent of another workspace is not found.
    Rules: `create` R5 [BUG-1694], Errors row 3"""
    rz = mk_msg(workspace_id=w2.id)
    commit_point(db)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.create(
            db, workspace_id=w1.id, user_id=ub.id,
            data=DiscussionCreate(entity_type=ET("project"), entity_id=p1.id, message="Reply", parent_id=rz.id),
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Parent discussion not found"


# [claude] DSS-C-12
@pytest.mark.xfail(strict=True, reason=BUG_1694)
def test_dss_c_12__a_reply_to_a_reply_is_refused_one_level_only(db, w1, ub, p1, mk_msg, mk_reply):
    """DSS-C-12 — a reply to a reply is refused: one level only.
    Rules: `create` R6 [BUG-1694], Errors row 4"""
    r = mk_msg()
    q = mk_reply(r)
    commit_point(db)
    # Then 1
    with pytest.raises(AppValidationError) as exc:
        svc.create(
            db, workspace_id=w1.id, user_id=ub.id,
            data=DiscussionCreate(entity_type=ET("project"), entity_id=p1.id, message="Deeper", parent_id=q.id),
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.error_type == "validation_error"
    # Then 4
    assert exc.value.detail == "Replies can only be one level deep"


# [claude] DSS-C-13
@pytest.mark.xfail(strict=True, reason=BUG_1694)
def test_dss_c_13__a_reply_on_another_record_id_is_refused(db, w1, ub, mk_msg, mk_project):
    """DSS-C-13 — a reply on another record id is refused.
    Rules: `create` R7 [BUG-1694], Errors row 5"""
    p2 = mk_project("Project Two")
    r = mk_msg()
    commit_point(db)
    # Then 1
    with pytest.raises(AppValidationError) as exc:
        svc.create(
            db, workspace_id=w1.id, user_id=ub.id,
            data=DiscussionCreate(entity_type=ET("project"), entity_id=p2.id, message="Wrong place", parent_id=r.id),
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Reply must be on the same entity as the parent"


# [claude] DSS-C-14
@pytest.mark.xfail(strict=True, reason=BUG_1694)
def test_dss_c_14__a_reply_on_another_record_type_with_the_same_id_is_refused(db, w1, ub, p1, mk_msg):
    """DSS-C-14 — a reply on another record type with the same id is refused.
    Rules: `create` R7 [BUG-1694], Errors row 5"""
    r = mk_msg(entity_type="machine")
    commit_point(db)
    # Then 1
    with pytest.raises(AppValidationError) as exc:
        svc.create(
            db, workspace_id=w1.id, user_id=ub.id,
            data=DiscussionCreate(entity_type=ET("project"), entity_id=p1.id, message="Wrong type", parent_id=r.id),
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Reply must be on the same entity as the parent"


# [claude] DSS-C-15
@pytest.mark.xfail(strict=True, reason=BUG_1694)
def test_dss_c_15__depth_is_checked_before_the_record(db, w1, ub, p1, mk_msg, mk_reply, mk_project):
    """DSS-C-15 — depth is checked before the record: a reply on another record's reply gets the depth message.
    Rules: `create` R6, R7 [BUG-1694], Errors row 4"""
    p2 = mk_project("Project Two")
    r = mk_msg(entity_id=p2.id)
    q = mk_reply(r, entity_id=p2.id)
    commit_point(db)
    # Then 1
    with pytest.raises(AppValidationError) as exc:
        svc.create(
            db, workspace_id=w1.id, user_id=ub.id,
            data=DiscussionCreate(entity_type=ET("project"), entity_id=p1.id, message="Deeper", parent_id=q.id),
        )
    # Then 2
    assert exc.value.detail == "Replies can only be one level deep"


# [claude] DSS-C-16
def test_dss_c_16__a_missing_parent_writes_nothing_does_not_commit_and_does_not_roll_back(
    db, w1, ub, p1, mk_msg, mk_xm,
):
    """DSS-C-16 — a missing parent writes nothing, does not commit, and does not roll back other changes.
    Rules: `create` R5, R12; D2"""
    mk_msg()
    commit_point(db)
    mk_xm()
    with pytest.raises((TypeError, NotFoundError)) as exc:
        with spies(db) as (cm, rb):
            svc.create(
                db, workspace_id=w1.id, user_id=ub.id,
                data=DiscussionCreate(entity_type=ET("project"), entity_id=p1.id, message="Reply", parent_id=0),
            )
    # Then 1
    assert isinstance(exc.value, (TypeError, NotFoundError))
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert count_discussions(db, message="Extra") == 1
    # Then 5
    assert count_discussions(db, message="Reply") == 0
    # Then 6
    assert count_notifications(db, workspace_id=w1.id) == 0


# [claude] DSS-C-17
def test_dss_c_17__a_reply_to_a_reply_writes_nothing_does_not_commit_and_does_not_roll_back(
    db, w1, ub, p1, mk_msg, mk_reply, mk_xm,
):
    """DSS-C-17 — a reply to a reply writes nothing, does not commit, and does not roll back other changes.
    Rules: `create` R6, R12; D2"""
    r = mk_msg()
    q = mk_reply(r)
    commit_point(db)
    mk_xm()
    with pytest.raises((TypeError, AppValidationError)) as exc:
        with spies(db) as (cm, rb):
            svc.create(
                db, workspace_id=w1.id, user_id=ub.id,
                data=DiscussionCreate(entity_type=ET("project"), entity_id=p1.id, message="Deeper", parent_id=q.id),
            )
    # Then 1
    assert isinstance(exc.value, (TypeError, AppValidationError))
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert count_discussions(db, message="Extra") == 1
    # Then 5
    assert count_discussions(db, message="Deeper") == 0


# [claude] DSS-C-18
def test_dss_c_18__a_reply_on_another_record_writes_nothing_does_not_commit_and_does_not_roll_back(
    db, w1, ub, mk_msg, mk_project, mk_xm,
):
    """DSS-C-18 — a reply on another record writes nothing, does not commit, and does not roll back other changes.
    Rules: `create` R7, R12; D2"""
    p2 = mk_project("Project Two")
    r = mk_msg()
    commit_point(db)
    mk_xm()
    with pytest.raises((TypeError, AppValidationError)) as exc:
        with spies(db) as (cm, rb):
            svc.create(
                db, workspace_id=w1.id, user_id=ub.id,
                data=DiscussionCreate(
                    entity_type=ET("project"), entity_id=p2.id, message="Wrong place", parent_id=r.id,
                ),
            )
    # Then 1
    assert isinstance(exc.value, (TypeError, AppValidationError))
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert count_discussions(db, message="Extra") == 1
    # Then 5
    assert count_discussions(db, message="Wrong place") == 0


BUG_1686 = "BUG-1686: Discussions are posted and listed on records that do not exist or belong to another workspace"
BUG_1687 = "BUG-1687: A soft-deleted record's discussion is still listed and posted to"


# [claude] DSS-C-19
@pytest.mark.xfail(strict=True, reason=BUG_1686)
def test_dss_c_19__a_message_on_an_unknown_record_is_refused(db, w1, ua):
    """DSS-C-19 — a message on an unknown record is refused.
    Rules: `create` R3 [BUG-1686], Errors row 1"""
    commit_point(db)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.create(
            db, workspace_id=w1.id, user_id=ua.id,
            data=DiscussionCreate(entity_type=ET("project"), entity_id=MISSING, message="Ghost"),
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Record not found"
    # Then 4
    assert count_discussions(db, message="Ghost") == 0


# [claude] DSS-C-20
@pytest.mark.xfail(strict=True, reason=BUG_1686)
def test_dss_c_20__a_message_on_another_workspaces_record_is_refused(db, w1, ua, p9):
    """DSS-C-20 — a message on another workspace's record is refused.
    Rules: `create` R3 [BUG-1686], Errors row 1"""
    commit_point(db)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.create(
            db, workspace_id=w1.id, user_id=ua.id,
            data=DiscussionCreate(entity_type=ET("project"), entity_id=p9.id, message="Ghost"),
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Record not found"
    # Then 4
    assert count_discussions(db, message="Ghost") == 0


# [claude] DSS-C-21
@pytest.mark.xfail(strict=True, reason=BUG_1687)
def test_dss_c_21__a_message_on_a_soft_deleted_project_is_refused(db, w1, ua, mk_project):
    """DSS-C-21 — a message on a soft-deleted project is refused.
    Rules: `create` R4 [BUG-1687], Errors row 1"""
    pd = mk_project("Old Project", is_deleted=True)
    commit_point(db)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.create(
            db, workspace_id=w1.id, user_id=ua.id,
            data=DiscussionCreate(entity_type=ET("project"), entity_id=pd.id, message="Ghost"),
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Record not found"
    # Then 4
    assert count_discussions(db, message="Ghost") == 0


# [claude] DSS-C-22
@pytest.mark.xfail(strict=True, reason=BUG_1687)
def test_dss_c_22__a_message_on_an_inactive_item_is_refused(db, w1, ua, mk_item):
    """DSS-C-22 — a message on an inactive item is refused.
    Rules: `create` R4 [BUG-1687], Errors row 1"""
    i_d = mk_item(is_active=False)
    commit_point(db)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.create(
            db, workspace_id=w1.id, user_id=ua.id,
            data=DiscussionCreate(entity_type=ET("item"), entity_id=i_d.id, message="Ghost"),
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Record not found"
    # Then 4
    assert count_discussions(db, message="Ghost") == 0


# [claude] DSS-C-23
@pytest.mark.xfail(strict=True, reason=BUG_1686)
def test_dss_c_23__the_record_is_checked_before_the_parent(db, w1, ua):
    """DSS-C-23 — the record is checked before the parent.
    Rules: `create` R2, R3 [BUG-1686]"""
    commit_point(db)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.create(
            db, workspace_id=w1.id, user_id=ua.id,
            data=DiscussionCreate(entity_type=ET("project"), entity_id=MISSING, message="Ghost", parent_id=0),
        )
    # Then 2
    assert exc.value.detail == "Record not found"


# [claude] DSS-C-24
@pytest.mark.xfail(strict=True, reason=BUG_1686)
def test_dss_c_24__a_record_refusal_does_not_commit_and_leaves_other_changes_pending(db, w1, ua, mk_msg, mk_xm):
    """DSS-C-24 — a record refusal does not commit and leaves other changes pending.
    Rules: `create` R3, R12 [BUG-1686]; D2"""
    mk_msg()
    commit_point(db)
    mk_xm()
    # Then 1
    with pytest.raises(NotFoundError):
        with spies(db) as (cm, rb):
            svc.create(
                db, workspace_id=w1.id, user_id=ua.id,
                data=DiscussionCreate(entity_type=ET("project"), entity_id=MISSING, message="Ghost"),
            )
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert count_discussions(db, message="Extra") == 1


# [claude] DSS-C-25
def test_dss_c_25__a_message_on_a_purchase_order_is_stored(db, w1, ua, mk_stage, mk_purchase):
    """DSS-C-25 — a message on a purchase order (no soft delete) is stored.
    Rules: `create` R1, R3, R4"""
    s = mk_stage()
    o = mk_purchase(s)
    commit_point(db)
    result = svc.create(
        db, workspace_id=w1.id, user_id=ua.id,
        data=DiscussionCreate(entity_type=ET("purchase_order"), entity_id=o.id, message="Arrived"),
    )
    mid = result.id

    # Then 1
    assert result.entity_type == "purchase_order"
    assert result.entity_id == o.id
    # Then 2
    db.rollback()
    row = reread(db, Discussion, mid)
    assert row.entity_type == "purchase_order"
    assert row.entity_id == o.id
    assert row.workspace_id == w1.id


# [claude] DSS-C-26
def test_dss_c_26__an_unknown_author_the_database_error_reaches_the_caller_and_the_service_does_not_roll_back(
    db, w1, p1, mk_msg, mk_xm,
):
    """DSS-C-26 — an unknown author: the database error reaches the caller and the service does not roll back.
    Rules: `create` R12, Errors row 6; D3"""
    mk_msg()
    commit_point(db)
    mk_xm()
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with spies(db) as (cm, rb):
            svc.create(
                db, workspace_id=w1.id, user_id=MISSING,
                data=DiscussionCreate(entity_type=ET("project"), entity_id=p1.id, message="Orphan"),
            )
    # Then 2
    assert exc.value.orig.pgcode == "23503"
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert cm.call_count == 0
    # Then 5
    with pytest.raises(PendingRollbackError):
        db.execute(text("SELECT 1"))
    # Then 6
    db.rollback()
    assert count_discussions(db, message="Orphan") == 0
    # Then 7
    assert count_discussions(db, message="Extra") == 0


# [claude] DSS-C-27
def test_dss_c_27__a_failing_commit_reaches_the_caller_the_service_does_not_roll_back_nothing_is_saved(
    db, w1, ua, ub, p1,
):
    """DSS-C-27 — a failing commit reaches the caller; the service does not roll back; nothing is saved.
    Rules: `create` R12; D3"""
    commit_point(db)
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "commit", side_effect=RuntimeError("boom")), \
                patch.object(db, "rollback", wraps=db.rollback) as rb:
            svc.create(
                db, workspace_id=w1.id, user_id=ua.id,
                data=DiscussionCreate(entity_type=ET("project"), entity_id=p1.id, message=f"Lost @[{ub.id}]"),
            )
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count == 0
    # Then 3
    db.rollback()
    assert count_discussions(db, workspace_id=w1.id) == 0
    # Then 4
    assert count_notifications(db, workspace_id=w1.id) == 0


# [claude] DSS-C-28
@pytest.mark.xfail(strict=True, reason=BUG_1867)
def test_dss_c_28__a_plain_member_cannot_post_on_a_private_projects_thread(db, w1, ub, mk_private_project, mk_xm):
    """DSS-C-28 — a plain member cannot post on a private project's thread: 404, nothing written, other changes kept.
    Rules: `create` R11, R12 [BUG-1867], Errors row 2; D2"""
    pp = mk_private_project("Secret Project")
    commit_point(db)
    mk_xm()
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        with spies(db) as (cm, rb):
            svc.create(
                db, workspace_id=w1.id, user_id=ub.id,
                data=DiscussionCreate(entity_type=ET("project"), entity_id=pp.id, message="Hidden"),
            )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Record not found"
    # Then 4
    assert cm.call_count == 0
    # Then 5
    assert rb.call_count == 0
    # Then 6
    assert count_discussions(db, message="Hidden") == 0
    # Then 7
    assert count_discussions(db, message="Extra") == 1


# [claude] DSS-C-29
@pytest.mark.xfail(strict=True, reason=BUG_1868)
def test_dss_c_29__a_plain_member_cannot_post_on_a_help_ticket_they_did_not_create(db, w1, ub, mk_ticket, mk_xm):
    """DSS-C-29 — a plain member cannot post on a help ticket they did not create: 404, nothing written, other changes kept.
    Rules: `create` R11a, R12 [BUG-1868], Errors row 2; D2"""
    t = mk_ticket()
    commit_point(db)
    mk_xm()
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        with spies(db) as (cm, rb):
            svc.create(
                db, workspace_id=w1.id, user_id=ub.id,
                data=DiscussionCreate(entity_type=ET("support_ticket"), entity_id=t.id, message="Hidden"),
            )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Record not found"
    # Then 4
    assert cm.call_count == 0
    # Then 5
    assert rb.call_count == 0
    # Then 6
    assert count_discussions(db, message="Hidden") == 0
    # Then 7
    assert count_discussions(db, message="Extra") == 1


# [claude] DSS-C-30
def test_dss_c_30__a_parent_of_another_workspace_nothing_written_no_commit_no_rollback_of_other_changes(
    db, w1, w2, ub, p1, mk_msg, mk_xm,
):
    """DSS-C-30 — a parent of another workspace: nothing written, no commit, no rollback of other changes.
    Rules: `create` R5, R12; D2"""
    rz = mk_msg(workspace_id=w2.id)
    commit_point(db)
    mk_xm()
    with pytest.raises((TypeError, NotFoundError)) as exc:
        with spies(db) as (cm, rb):
            svc.create(
                db, workspace_id=w1.id, user_id=ub.id,
                data=DiscussionCreate(entity_type=ET("project"), entity_id=p1.id, message="Reply", parent_id=rz.id),
            )
    # Then 1
    assert isinstance(exc.value, (TypeError, NotFoundError))
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert count_discussions(db, message="Extra") == 1
    # Then 5
    assert count_discussions(db, message="Reply") == 0


# [claude] DSS-C-31
def test_dss_c_31__a_parent_on_another_record_type_with_the_same_id_nothing_written_no_commit_no_rollback(
    db, w1, ub, p1, mk_msg, mk_xm,
):
    """DSS-C-31 — a parent on another record type with the same id: nothing written, no commit, no rollback of other changes.
    Rules: `create` R7, R12; D2"""
    r = mk_msg(entity_type="machine")
    commit_point(db)
    mk_xm()
    with pytest.raises((TypeError, AppValidationError)) as exc:
        with spies(db) as (cm, rb):
            svc.create(
                db, workspace_id=w1.id, user_id=ub.id,
                data=DiscussionCreate(entity_type=ET("project"), entity_id=p1.id, message="Wrong type", parent_id=r.id),
            )
    # Then 1
    assert isinstance(exc.value, (TypeError, AppValidationError))
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert count_discussions(db, message="Extra") == 1
    # Then 5
    assert count_discussions(db, message="Wrong type") == 0


# [claude] DSS-C-32
def test_dss_c_32__two_distinct_active_members_mentioned_are_both_notified_a_suspended_one_is_not(
    db, w1, ua, ub, us, p1,
):
    """DSS-C-32 — two distinct active members mentioned are both notified; a suspended one is not.
    Rules: `create` R9"""
    uc = make_profile(db, name="Cid")
    _add(db, WorkspaceMember(workspace_id=w1.id, user_id=uc.id, role="member", status="active"))
    commit_point(db)
    result = svc.create(
        db, workspace_id=w1.id, user_id=ua.id,
        data=DiscussionCreate(entity_type=ET("project"), entity_id=p1.id, message=f"@[{us.id}] @[{ub.id}] @[{uc.id}]"),
    )
    mid = result.id

    # Then 1
    assert result.id == mid
    # Then 2
    db.rollback()
    assert recipients(db, mid) == sorted([ub.id, uc.id])


# [claude] DSS-C-33
def test_dss_c_33__the_creator_posts_on_a_private_projects_thread(db, w1, ua, mk_private_project):
    """DSS-C-33 — the creator posts on a private project's thread.
    Rules: `create` R11"""
    pp = mk_private_project("Secret Project")
    commit_point(db)
    result = svc.create(
        db, workspace_id=w1.id, user_id=ua.id,
        data=DiscussionCreate(entity_type=ET("project"), entity_id=pp.id, message="Visible"),
    )

    # Then 1
    assert result.user_id == ua.id
    assert result.entity_id == pp.id
    # Then 2
    db.rollback()
    assert count_discussions(db, message="Visible") == 1


# [claude] DSS-C-34
def test_dss_c_34__the_workspace_owner_posts_on_a_private_projects_thread(db, w1, mk_person, mk_private_project):
    """DSS-C-34 — the workspace owner posts on a private project's thread.
    Rules: `create` R11"""
    uw = mk_person("Wes", "member")
    set_owner(db, w1, uw)
    pp = mk_private_project("Secret Project")
    commit_point(db)
    result = svc.create(
        db, workspace_id=w1.id, user_id=uw.id,
        data=DiscussionCreate(entity_type=ET("project"), entity_id=pp.id, message="Visible"),
    )

    # Then 1
    assert result.user_id == uw.id
    assert result.entity_id == pp.id
    # Then 2
    db.rollback()
    assert count_discussions(db, message="Visible") == 1


# [claude] DSS-C-35
def test_dss_c_35__a_member_with_role_owner_posts_on_a_private_projects_thread(
    db, w1, mk_person, mk_private_project,
):
    """DSS-C-35 — a member with role owner posts on a private project's thread.
    Rules: `create` R11"""
    ur = mk_person("Ron", "owner")
    pp = mk_private_project("Secret Project")
    commit_point(db)
    result = svc.create(
        db, workspace_id=w1.id, user_id=ur.id,
        data=DiscussionCreate(entity_type=ET("project"), entity_id=pp.id, message="Visible"),
    )

    # Then 1
    assert result.user_id == ur.id
    assert result.entity_id == pp.id
    # Then 2
    db.rollback()
    assert count_discussions(db, message="Visible") == 1


# [claude] DSS-C-36
def test_dss_c_36__a_member_with_role_ground_team_manager_posts_on_a_private_projects_thread(
    db, w1, mk_person, mk_private_project,
):
    """DSS-C-36 — a member with role ground-team-manager posts on a private project's thread.
    Rules: `create` R11"""
    um = mk_person("Mia", "ground-team-manager")
    pp = mk_private_project("Secret Project")
    commit_point(db)
    result = svc.create(
        db, workspace_id=w1.id, user_id=um.id,
        data=DiscussionCreate(entity_type=ET("project"), entity_id=pp.id, message="Visible"),
    )

    # Then 1
    assert result.user_id == um.id
    assert result.entity_id == pp.id
    # Then 2
    db.rollback()
    assert count_discussions(db, message="Visible") == 1


# [claude] DSS-C-37
def test_dss_c_37__a_person_invited_to_a_private_project_posts_on_its_thread(
    db, w1, mk_person, mk_private_project, invite,
):
    """DSS-C-37 — a person invited to a private project posts on its thread.
    Rules: `create` R11"""
    up = mk_person("Pia", "member")
    pp = mk_private_project("Secret Project")
    invite(up, pp)
    commit_point(db)
    result = svc.create(
        db, workspace_id=w1.id, user_id=up.id,
        data=DiscussionCreate(entity_type=ET("project"), entity_id=pp.id, message="Visible"),
    )

    # Then 1
    assert result.user_id == up.id
    assert result.entity_id == pp.id
    # Then 2
    db.rollback()
    assert count_discussions(db, message="Visible") == 1


# [claude] DSS-C-38
def test_dss_c_38__the_creator_of_a_help_ticket_posts_on_its_thread(db, w1, ub, mk_ticket):
    """DSS-C-38 — the creator of a help ticket posts on its thread.
    Rules: `create` R11a"""
    t = mk_ticket(created_by=ub.id)
    commit_point(db)
    result = svc.create(
        db, workspace_id=w1.id, user_id=ub.id,
        data=DiscussionCreate(entity_type=ET("support_ticket"), entity_id=t.id, message="Visible"),
    )

    # Then 1
    assert result.user_id == ub.id
    assert result.entity_id == t.id
    # Then 2
    db.rollback()
    assert count_discussions(db, message="Visible") == 1


# [claude] DSS-C-39
def test_dss_c_39__a_member_with_role_ground_team_manager_posts_on_any_help_ticket(db, w1, mk_person, mk_ticket):
    """DSS-C-39 — a member with role ground-team-manager posts on any help ticket.
    Rules: `create` R11a"""
    um = mk_person("Mia", "ground-team-manager")
    t = mk_ticket()
    commit_point(db)
    result = svc.create(
        db, workspace_id=w1.id, user_id=um.id,
        data=DiscussionCreate(entity_type=ET("support_ticket"), entity_id=t.id, message="Visible"),
    )

    # Then 1
    assert result.user_id == um.id
    assert result.entity_id == t.id
    # Then 2
    db.rollback()
    assert count_discussions(db, message="Visible") == 1


# [claude] DSS-C-40
def test_dss_c_40__a_member_with_role_owner_posts_on_any_help_ticket(db, w1, mk_person, mk_ticket):
    """DSS-C-40 — a member with role owner posts on any help ticket.
    Rules: `create` R11a"""
    ur = mk_person("Ron", "owner")
    t = mk_ticket()
    commit_point(db)
    result = svc.create(
        db, workspace_id=w1.id, user_id=ur.id,
        data=DiscussionCreate(entity_type=ET("support_ticket"), entity_id=t.id, message="Visible"),
    )

    # Then 1
    assert result.user_id == ur.id
    assert result.entity_id == t.id
    # Then 2
    db.rollback()
    assert count_discussions(db, message="Visible") == 1


# [claude] DSS-C-41
def test_dss_c_41__a_platform_admin_with_no_membership_posts_on_any_help_ticket(db, w1, mk_admin, mk_ticket):
    """DSS-C-41 — a platform admin with no membership posts on any help ticket.
    Rules: `create` R11a"""
    pa = mk_admin()
    t = mk_ticket()
    commit_point(db)
    result = svc.create(
        db, workspace_id=w1.id, user_id=pa.id,
        data=DiscussionCreate(entity_type=ET("support_ticket"), entity_id=t.id, message="Visible"),
    )

    # Then 1
    assert result.user_id == pa.id
    assert result.entity_id == t.id
    # Then 2
    db.rollback()
    assert count_discussions(db, message="Visible") == 1


# [claude] DSS-C-42
@pytest.mark.xfail(strict=True, reason=BUG_1867)
def test_dss_c_42__a_component_of_a_private_project_a_plain_member_cannot_post(
    db, w1, ub, mk_private_project, mk_component, mk_xm,
):
    """DSS-C-42 — a component of a private project: a plain member cannot post.
    Rules: `create` R11b, R12 [BUG-1867], Errors row 2; D2"""
    pp = mk_private_project("Secret Project")
    c = mk_component(pp)
    commit_point(db)
    mk_xm()
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        with spies(db) as (cm, rb):
            svc.create(
                db, workspace_id=w1.id, user_id=ub.id,
                data=DiscussionCreate(entity_type=ET("project_component"), entity_id=c.id, message="Hidden"),
            )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Record not found"
    # Then 4
    assert cm.call_count == 0
    # Then 5
    assert rb.call_count == 0
    # Then 6
    assert count_discussions(db, message="Hidden") == 0
    # Then 7
    assert count_discussions(db, message="Extra") == 1


# [claude] DSS-C-43
def test_dss_c_43__a_component_of_a_private_project_a_person_invited_to_the_project_posts(
    db, w1, mk_person, mk_private_project, invite, mk_component,
):
    """DSS-C-43 — a component of a private project: a person invited to the project posts.
    Rules: `create` R11b"""
    up = mk_person("Pia", "member")
    pp = mk_private_project("Secret Project")
    invite(up, pp)
    c = mk_component(pp)
    commit_point(db)
    result = svc.create(
        db, workspace_id=w1.id, user_id=up.id,
        data=DiscussionCreate(entity_type=ET("project_component"), entity_id=c.id, message="Visible"),
    )

    # Then 1
    assert result.user_id == up.id
    assert result.entity_id == c.id
    # Then 2
    db.rollback()
    assert count_discussions(db, message="Visible") == 1


# [claude] DSS-C-44
def test_dss_c_44__a_component_of_a_workspace_visibility_project_every_member_posts(db, w1, ub, p1, mk_component):
    """DSS-C-44 — a component of a workspace-visibility project: every member posts.
    Rules: `create` R11b"""
    c = mk_component(p1)
    commit_point(db)
    result = svc.create(
        db, workspace_id=w1.id, user_id=ub.id,
        data=DiscussionCreate(entity_type=ET("project_component"), entity_id=c.id, message="Visible"),
    )

    # Then 1
    assert result.user_id == ub.id
    assert result.entity_id == c.id
    # Then 2
    db.rollback()
    assert count_discussions(db, message="Visible") == 1


# [claude] DSS-C-45
def test_dss_c_45__another_record_type_purchase_order_keeps_membership_as_its_only_check(
    db, w1, ub, mk_stage, mk_purchase,
):
    """DSS-C-45 — another record type (purchase order) keeps membership as its only check.
    Rules: `create` R11c"""
    s = mk_stage()
    o = mk_purchase(s)
    commit_point(db)
    result = svc.create(
        db, workspace_id=w1.id, user_id=ub.id,
        data=DiscussionCreate(entity_type=ET("purchase_order"), entity_id=o.id, message="Visible"),
    )

    # Then 1
    assert result.user_id == ub.id
    assert result.entity_id == o.id
    # Then 2
    db.rollback()
    assert count_discussions(db, message="Visible") == 1


# [claude] DSS-C-46
@pytest.mark.xfail(strict=True, reason=BUG_1867)
def test_dss_c_46__an_invitation_to_other_private_projects_lower_and_higher_id_does_not_open_this_one(
    db, w1, ub, mk_private_project, invite, mk_xm,
):
    """DSS-C-46 — an invitation to other private projects (lower and higher id) does not open this one.
    Rules: `create` R11 [BUG-1867], Errors row 2"""
    pa2 = mk_private_project("Alpha Secret")
    pp = mk_private_project("Secret Project")
    pz3 = mk_private_project("Zeta Secret")
    invite(ub, pa2)
    invite(ub, pz3)
    commit_point(db)
    mk_xm()
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        with spies(db) as (cm, rb):
            svc.create(
                db, workspace_id=w1.id, user_id=ub.id,
                data=DiscussionCreate(entity_type=ET("project"), entity_id=pp.id, message="Hidden"),
            )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Record not found"
    # Then 4
    assert cm.call_count == 0
    # Then 5
    assert rb.call_count == 0
    # Then 6
    assert count_discussions(db, message="Hidden") == 0
    # Then 7
    assert count_discussions(db, message="Extra") == 1


# [claude] DSS-C-47
@pytest.mark.xfail(strict=True, reason=BUG_1867)
def test_dss_c_47__role_owner_in_another_workspace_does_not_open_a_private_project_here(
    db, w1, w2, ub, mk_private_project, mk_xm,
):
    """DSS-C-47 — role owner in another workspace does not open a private project here.
    Rules: `create` R11 [BUG-1867], Errors row 2"""
    _add(db, WorkspaceMember(workspace_id=w2.id, user_id=ub.id, role="owner", status="active"))
    pp = mk_private_project("Secret Project")
    commit_point(db)
    mk_xm()
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        with spies(db) as (cm, rb):
            svc.create(
                db, workspace_id=w1.id, user_id=ub.id,
                data=DiscussionCreate(entity_type=ET("project"), entity_id=pp.id, message="Hidden"),
            )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Record not found"
    # Then 4
    assert cm.call_count == 0
    # Then 5
    assert rb.call_count == 0
    # Then 6
    assert count_discussions(db, message="Hidden") == 0
    # Then 7
    assert count_discussions(db, message="Extra") == 1


# [claude] DSS-C-48
@pytest.mark.xfail(strict=True, reason=BUG_1867)
def test_dss_c_48__owning_another_workspace_does_not_open_a_private_project_here(
    db, w1, w2, ub, mk_private_project, mk_xm,
):
    """DSS-C-48 — owning another workspace does not open a private project here.
    Rules: `create` R11 [BUG-1867], Errors row 2"""
    w2.owner_user_id = ub.id
    db.flush()
    pp = mk_private_project("Secret Project")
    commit_point(db)
    mk_xm()
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        with spies(db) as (cm, rb):
            svc.create(
                db, workspace_id=w1.id, user_id=ub.id,
                data=DiscussionCreate(entity_type=ET("project"), entity_id=pp.id, message="Hidden"),
            )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Record not found"
    # Then 4
    assert cm.call_count == 0
    # Then 5
    assert rb.call_count == 0
    # Then 6
    assert count_discussions(db, message="Hidden") == 0
    # Then 7
    assert count_discussions(db, message="Extra") == 1


# [claude] DSS-C-49
@pytest.mark.xfail(strict=True, reason=BUG_1868)
def test_dss_c_49__having_created_other_help_tickets_lower_and_higher_id_does_not_open_this_one(
    db, w1, ub, mk_ticket, mk_xm,
):
    """DSS-C-49 — having created other help tickets (lower and higher id) does not open this one.
    Rules: `create` R11a [BUG-1868], Errors row 2"""
    mk_ticket(ticket_number="HELP-2026-002", created_by=ub.id)
    t = mk_ticket()
    mk_ticket(ticket_number="HELP-2026-003", created_by=ub.id)
    commit_point(db)
    mk_xm()
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        with spies(db) as (cm, rb):
            svc.create(
                db, workspace_id=w1.id, user_id=ub.id,
                data=DiscussionCreate(entity_type=ET("support_ticket"), entity_id=t.id, message="Hidden"),
            )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Record not found"
    # Then 4
    assert cm.call_count == 0
    # Then 5
    assert rb.call_count == 0
    # Then 6
    assert count_discussions(db, message="Hidden") == 0
    # Then 7
    assert count_discussions(db, message="Extra") == 1


# [claude] DSS-C-50
@pytest.mark.xfail(strict=True, reason=BUG_1867)
def test_dss_c_50__the_visibility_check_runs_before_the_parent_check(db, w1, ub, mk_private_project):
    """DSS-C-50 — the visibility check runs before the parent check.
    Rules: `create` R2, R11 [BUG-1867]"""
    pp = mk_private_project("Secret Project")
    commit_point(db)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.create(
            db, workspace_id=w1.id, user_id=ub.id,
            data=DiscussionCreate(entity_type=ET("project"), entity_id=pp.id, message="Hidden", parent_id=0),
        )
    # Then 2
    assert exc.value.detail == "Record not found"


# [claude] DSS-C-51
@pytest.mark.xfail(strict=True, reason=BUG_1867)
def test_dss_c_51__a_suspended_member_with_role_ground_team_manager_cannot_post_on_a_private_project(
    db, w1, mk_private_project, mk_xm,
):
    """DSS-C-51 — a suspended member with role ground-team-manager cannot post on a private project.
    Rules: `create` R11 [BUG-1867], Errors row 2"""
    uq = make_profile(db, name="Quinn")
    _add(db, WorkspaceMember(workspace_id=w1.id, user_id=uq.id, role="ground-team-manager", status="suspended"))
    pp = mk_private_project("Secret Project")
    commit_point(db)
    mk_xm()
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        with spies(db) as (cm, rb):
            svc.create(
                db, workspace_id=w1.id, user_id=uq.id,
                data=DiscussionCreate(entity_type=ET("project"), entity_id=pp.id, message="Hidden"),
            )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Record not found"
    # Then 4
    assert cm.call_count == 0
    # Then 5
    assert rb.call_count == 0
    # Then 6
    assert count_discussions(db, message="Hidden") == 0
    # Then 7
    assert count_discussions(db, message="Extra") == 1


BUG_1879 = "BUG-1879: A mention on a private project or help ticket notifies people who cannot open it"


# [claude] DSS-C-52
@pytest.mark.xfail(strict=True, reason=BUG_1879)
def test_dss_c_52__a_private_project_only_the_mentioned_person_who_may_open_it_is_notified(
    db, w1, ua, ub, mk_person, mk_private_project, invite,
):
    """DSS-C-52 — a private project: only the mentioned person who may open it is notified.
    Rules: `create` R9a [BUG-1879]"""
    up = mk_person("Pia", "member")
    pp = mk_private_project("Secret Project")
    invite(up, pp)
    commit_point(db)
    result = svc.create(
        db, workspace_id=w1.id, user_id=ua.id,
        data=DiscussionCreate(entity_type=ET("project"), entity_id=pp.id, message=f"Heads up @[{up.id}] @[{ub.id}]"),
    )
    mid = result.id

    # Then 1
    assert result.id == mid
    # Then 2
    db.rollback()
    assert count_discussions(db, id=mid) == 1
    # Then 3
    assert len(notes(db, mid, recipient=up.id)) == 1
    # Then 4
    assert len(notes(db, mid, recipient=ub.id)) == 0


# [claude] DSS-C-53
@pytest.mark.xfail(strict=True, reason=BUG_1879)
def test_dss_c_53__a_component_of_a_private_project_only_the_mentioned_person_who_may_open_the_project_is_notified(
    db, w1, ua, ub, mk_person, mk_private_project, invite, mk_component,
):
    """DSS-C-53 — a component of a private project: only the mentioned person who may open the project is notified.
    Rules: `create` R9a [BUG-1879]"""
    up = mk_person("Pia", "member")
    pp = mk_private_project("Secret Project")
    invite(up, pp)
    c = mk_component(pp)
    commit_point(db)
    result = svc.create(
        db, workspace_id=w1.id, user_id=ua.id,
        data=DiscussionCreate(
            entity_type=ET("project_component"), entity_id=c.id, message=f"Heads up @[{up.id}] @[{ub.id}]",
        ),
    )
    mid = result.id

    # Then 1
    assert result.id == mid
    # Then 2
    db.rollback()
    assert count_discussions(db, id=mid) == 1
    # Then 3
    assert len(notes(db, mid, recipient=up.id)) == 1
    # Then 4
    assert len(notes(db, mid, recipient=ub.id)) == 0


# [claude] DSS-C-54
@pytest.mark.xfail(strict=True, reason=BUG_1879)
def test_dss_c_54__a_help_ticket_only_the_mentioned_person_who_may_open_it_is_notified(
    db, w1, ua, ub, mk_person, mk_ticket,
):
    """DSS-C-54 — a help ticket: only the mentioned person who may open it is notified.
    Rules: `create` R9a [BUG-1879]"""
    um = mk_person("Mia", "ground-team-manager")
    t = mk_ticket()
    commit_point(db)
    result = svc.create(
        db, workspace_id=w1.id, user_id=ua.id,
        data=DiscussionCreate(
            entity_type=ET("support_ticket"), entity_id=t.id, message=f"Heads up @[{um.id}] @[{ub.id}]",
        ),
    )
    mid = result.id

    # Then 1
    assert result.id == mid
    # Then 2
    db.rollback()
    assert count_discussions(db, id=mid) == 1
    # Then 3
    assert len(notes(db, mid, recipient=um.id)) == 1
    # Then 4
    assert len(notes(db, mid, recipient=ub.id)) == 0


# [claude] DSS-C-55
@pytest.mark.xfail(strict=True, reason=BUG_1879)
def test_dss_c_55__nobody_mentioned_may_open_the_record_no_notification_the_message_is_stored(
    db, w1, ua, ub, mk_private_project,
):
    """DSS-C-55 — nobody mentioned may open the record: no notification, the message is stored.
    Rules: `create` R9a [BUG-1879]"""
    pp = mk_private_project("Secret Project")
    commit_point(db)
    result = svc.create(
        db, workspace_id=w1.id, user_id=ua.id,
        data=DiscussionCreate(entity_type=ET("project"), entity_id=pp.id, message=f"Heads up @[{ub.id}]"),
    )
    mid = result.id

    # Then 1
    assert result.id == mid
    # Then 2
    db.rollback()
    assert count_discussions(db, id=mid) == 1
    # Then 3
    assert len(notes(db, mid, recipient=ub.id)) == 0
    # Then 4
    assert len(notes(db, mid)) == 0


# [claude] DSS-C-56
def test_dss_c_56__a_workspace_visibility_project_every_mentioned_active_member_is_notified(
    db, w1, ua, ub, p1, mk_person,
):
    """DSS-C-56 — a workspace-visibility project: every mentioned active member is notified.
    Rules: `create` R9, R9a"""
    up = mk_person("Pia", "member")
    commit_point(db)
    result = svc.create(
        db, workspace_id=w1.id, user_id=ua.id,
        data=DiscussionCreate(entity_type=ET("project"), entity_id=p1.id, message=f"Heads up @[{up.id}] @[{ub.id}]"),
    )
    mid = result.id

    # Then 1
    assert result.id == mid
    # Then 2
    db.rollback()
    assert count_discussions(db, id=mid) == 1
    # Then 3
    assert len(notes(db, mid, recipient=up.id)) == 1
    # Then 4
    assert len(notes(db, mid, recipient=ub.id)) == 1


# [claude] DSS-C-57
@pytest.mark.xfail(strict=True, reason=BUG_1867)
def test_dss_c_57__a_platform_admin_cannot_post_on_a_private_project_admins_are_allowed_on_tickets_only(
    db, w1, mk_admin, mk_private_project, mk_xm,
):
    """DSS-C-57 — a platform admin cannot post on a private project: admins are allowed on tickets only.
    Rules: `create` R11, R12 [BUG-1867], Errors row 2; D2"""
    pa = mk_admin()
    pp = mk_private_project("Secret Project")
    commit_point(db)
    mk_xm()
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        with spies(db) as (cm, rb):
            svc.create(
                db, workspace_id=w1.id, user_id=pa.id,
                data=DiscussionCreate(entity_type=ET("project"), entity_id=pp.id, message="Hidden"),
            )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Record not found"
    # Then 4
    assert cm.call_count == 0
    # Then 5
    assert rb.call_count == 0
    # Then 6
    assert count_discussions(db, message="Hidden") == 0
    # Then 7
    assert count_discussions(db, message="Extra") == 1


# [claude] DSS-C-58
@pytest.mark.xfail(strict=True, reason=BUG_1868)
def test_dss_c_58__a_suspended_member_with_role_owner_cannot_post_on_a_help_ticket_they_did_not_create(
    db, w1, mk_ticket, mk_xm,
):
    """DSS-C-58 — a suspended member with role owner cannot post on a help ticket they did not create.
    Rules: `create` R11a, R12 [BUG-1868], Errors row 2; D2"""
    uq = make_profile(db, name="Quinn")
    _add(db, WorkspaceMember(workspace_id=w1.id, user_id=uq.id, role="owner", status="suspended"))
    t = mk_ticket()
    commit_point(db)
    mk_xm()
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        with spies(db) as (cm, rb):
            svc.create(
                db, workspace_id=w1.id, user_id=uq.id,
                data=DiscussionCreate(entity_type=ET("support_ticket"), entity_id=t.id, message="Hidden"),
            )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Record not found"
    # Then 4
    assert cm.call_count == 0
    # Then 5
    assert rb.call_count == 0
    # Then 6
    assert count_discussions(db, message="Hidden") == 0
    # Then 7
    assert count_discussions(db, message="Extra") == 1


# [claude] DSS-C-59
def test_dss_c_59__the_creator_of_a_help_ticket_posts_on_it_whatever_their_membership_status(db, w1, mk_ticket):
    """DSS-C-59 — the creator of a help ticket posts on it whatever their membership status.
    Rules: `create` R11a"""
    uz = make_profile(db, name="Zed")
    _add(db, WorkspaceMember(workspace_id=w1.id, user_id=uz.id, role="member", status="suspended"))
    t = mk_ticket(created_by=uz.id)
    commit_point(db)
    result = svc.create(
        db, workspace_id=w1.id, user_id=uz.id,
        data=DiscussionCreate(entity_type=ET("support_ticket"), entity_id=t.id, message="Still broken"),
    )

    # Then 1
    assert result.user_id == uz.id
    assert result.entity_id == t.id
    # Then 2
    db.rollback()
    assert count_discussions(db, message="Still broken") == 1
