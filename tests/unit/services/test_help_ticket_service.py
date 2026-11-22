"""Unit tests for app/services/help_ticket_service.py.

Implements tests/unit/services/help_ticket_service.cases.md (revision 1), one
test per case, in card order. Real Postgres session (`db` fixture): a
`commit()` only releases a savepoint, so the service's commits are safe and the
fixture's outer rollback discards everything. Patched, as Conventions name
them: the clock of the DAO (C cards), the close clock of the manager (U cards
except U-11), the failing commit / failing refresh wraps and the commit /
rollback spies (both still call the real method).

Normal mode: every test is written from its card and carries a `# [claude] <ID>`
comment. Row names of the cards are the lower-case names here (T -> t, `W1.id`
-> `w1.id`); `# Then N` marks the checks of the card's Then line N.
"""

# ruff: noqa: SIM117, DTZ001  (Conventions prescribe the nested `with` and naive datetimes)
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import func, select, text
from sqlalchemy.exc import DataError, IntegrityError

from app.managers.help_ticket_manager import (
    HelpTicketForbiddenError,
    HelpTicketNotFoundError,
)
from app.models.enums import HelpTicketStatusEnum, RoleEnum
from app.models.help_ticket import HelpTicket
from app.schemas.help_ticket import (
    HelpTicketCreate,
    HelpTicketResponse,
    HelpTicketUpdate,
    PlatformHelpTicketListItem,
)
from app.services.help_ticket_service import help_ticket_service
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "svc"
svc = help_ticket_service

OWNER_R = RoleEnum("owner")
GTM_R = RoleEnum("ground-team-manager")
GT_R = RoleEnum("ground-team")
FIN_R = RoleEnum("finance")
OPEN = HelpTicketStatusEnum("open")
CLOSED = HelpTicketStatusEnum("closed")

MISSING = 999999999
PAST = datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc)
FORBID = "You do not have access to this help ticket."
NOTFOUND = "Help ticket not found."

# The fixed moment of "clock" and "close clock"
FIXED = datetime(2026, 6, 1, 12, 0)

BUG_1441 = "BUG-1441: A help ticket number's year comes from the server's local clock"
BUG_1442 = "BUG-1442: Help tickets of one creation time come back in no fixed order"
BUG_1443 = "BUG-1443: `%` and `_` in the support inbox search match every ticket"
BUG_1574 = "BUG-1574: Help ticket titles are stored untrimmed, and blank titles and descriptions are accepted"
BUG_1575 = (
    "BUG-1575: `null` for a ticket's title or description answers a database error"
)
BUG_1576 = "BUG-1576: Closing an already closed ticket rewrites who closed it and when"
BUG_1577 = "BUG-1577: A ticket's close time depends on the database's time zone"
BUG_1578 = "BUG-1578: A platform admin's workspace ticket list is empty, though they can open every ticket by id"
BUG_1863 = "BUG-1863: Owner, manager or platform admin can rewrite another member's help ticket"


def _add(db, row):
    db.add(row)
    db.flush()
    return row


# --------------------------------------------------------------------------- #
# Conventions -> standing rows (every test, in this order)
# --------------------------------------------------------------------------- #


# Convention "TAG", once per test
@pytest.fixture
def tag():
    return uuid.uuid4().hex[:8]


@pytest.fixture
def w1(db, tag):
    return make_workspace(db, name=f"Gamma {tag}")


@pytest.fixture
def w2(db, w1, tag):
    return make_workspace(db, name=f"Delta {tag}")


@pytest.fixture
def mgr(db, w2):
    return make_profile(db, name="Karim")


@pytest.fixture
def cr(db, mgr):
    return make_profile(db, name="Rahim")


@pytest.fixture
def own(db, cr):
    return make_profile(db, name="Owen")


@pytest.fixture
def adm(db, own):
    return make_profile(db, name="Sam", is_platform_admin=True)


@pytest.fixture
def fin(db, adm):
    return make_profile(db, name="Fatima")


@pytest.fixture(autouse=True)
def standing_rows(fin):
    pass


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #


# Convention "ticket": the card gives ticket_number; "but" changes other columns
@pytest.fixture
def mk_ticket(db, w1, cr):
    def _mk(number, **but):
        fields = {
            "workspace_id": w1.id,
            "ticket_number": number,
            "title": "Printer jam",
            "description": "It jams",
            "category": "hardware",
            "created_by": cr.id,
        }
        fields.update(but)
        return _add(db, HelpTicket(**fields))

    return _mk


# Convention "closed ticket"
@pytest.fixture
def mk_closed(mk_ticket, mgr):
    def _mk(number, **but):
        return mk_ticket(
            number,
            **{"status": "closed", "closed_at": PAST, "closed_by": mgr.id, **but},
        )

    return _mk


# Convention "commit point"
def commit_point(db):
    db.commit()


# Convention "extra row X" (after the commit point, not committed)
@pytest.fixture
def mk_extra(db, w2, fin, tag):
    def _mk():
        x = _add(
            db,
            HelpTicket(
                workspace_id=w2.id,
                ticket_number=f"HELP-X-{tag}",
                title="Extra",
                description="Extra",
                created_by=fin.id,
            ),
        )
        return x.id

    return _mk


# Convention "pending P" (after the commit point, not committed)
@pytest.fixture
def mk_pending(db, w2, fin, tag):
    def _mk():
        return _add(
            db,
            HelpTicket(
                workspace_id=w2.id,
                ticket_number=f"HELP-P-{tag}",
                title="Pending",
                description="Pending",
                created_by=fin.id,
            ),
        )

    return _mk


# --------------------------------------------------------------------------- #
# Conventions -> externals
# --------------------------------------------------------------------------- #


def _fixed_datetime(now_value):
    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now_value

    return _FixedDatetime


# Convention "clock" (C cards); C-05 passes its own two values
@contextmanager
def clock(now=FIXED, utc=FIXED):
    with (
        patch("app.dao.help_ticket.datetime", _fixed_datetime(now)),
        patch("app.dao.help_ticket.utcnow", create=True, return_value=utc),
        patch("app.utils.time.utcnow", return_value=utc),
    ):
        yield


# Convention "close clock" (U cards except U-11)
@contextmanager
def close_clock():
    with patch("app.managers.help_ticket_manager.utcnow", return_value=FIXED):
        yield


# Convention "spies": both wrap the real method
@contextmanager
def spies(db):
    with (
        patch.object(db, "commit", wraps=db.commit) as cm,
        patch.object(db, "rollback", wraps=db.rollback) as rb,
    ):
        yield cm, rb


# Convention "failing commit" (the rollback spy wraps the real method)
@contextmanager
def failing_commit(db):
    with (
        patch.object(db, "commit", side_effect=RuntimeError("boom")),
        patch.object(db, "rollback", wraps=db.rollback) as rb,
    ):
        yield rb


# Convention "failing refresh"
@contextmanager
def failing_refresh(db):
    with patch.object(db, "refresh", side_effect=RuntimeError("boom")):
        yield


# Convention "seqscan"
def seqscan(db):
    db.execute(text("SET LOCAL enable_indexscan = off"))
    db.execute(text("SET LOCAL enable_bitmapscan = off"))
    db.execute(text("SET LOCAL enable_indexonlyscan = off"))


# --------------------------------------------------------------------------- #
# Conventions -> named checks
# --------------------------------------------------------------------------- #


# Convention "re-read X"
def reread(db, ticket_id):
    db.expire_all()
    return db.get(HelpTicket, ticket_id)


_UNCHANGED_FIELDS = (
    "title",
    "description",
    "category",
    "status",
    "closed_at",
    "closed_by",
    "created_by",
)


# Convention "unchanged(T)": taken at the commit point and after a re-read
def snap(db, ticket_id):
    row = reread(db, ticket_id)
    return {f: getattr(row, f) for f in _UNCHANGED_FIELDS}


# Convention "nothing written": help_tickets rows of W1 and of W2
def counts(db, w1_id, w2_id):
    return tuple(
        db.scalar(
            select(func.count())
            .select_from(HelpTicket)
            .where(HelpTicket.workspace_id == ws_id)
        )
        for ws_id in (w1_id, w2_id)
    )


# Convention "x_gone"
def x_gone(db, x_id):
    return (
        db.scalar(
            select(func.count()).select_from(HelpTicket).where(HelpTicket.id == x_id)
        )
        == 0
    )


# Convention "idset(r)"
def idset(result):
    return {t.id for t in result}


# Convention "own(r)"
def own_ids(result, own):
    return {t.id for t in result if t.id in own}


# Convention "committed:" lines: one rollback, then fresh reads
def committed(db, ticket_id):
    db.expire_all()
    return db.execute(
        select(HelpTicket).where(HelpTicket.id == ticket_id)
    ).scalar_one_or_none()


# --------------------------------------------------------------------------- #
# HelpTicketService.create_ticket
# --------------------------------------------------------------------------- #


# [claude] HTS-C-01
def test_hts_c_01__the_ticket_is_created_committed_and_answered_with_its_creators_name(
    db, w1, cr
):
    """HTS-C-01 — the ticket is created, committed and answered with its creator's name.
    Rules: `create_ticket` R1, R3, TC1, TC2"""
    commit_point(db)
    with clock():
        result = svc.create_ticket(
            db,
            workspace=w1,
            user=cr,
            payload=HelpTicketCreate(
                title="Printer jam", description="It jams", category="hardware"
            ),
        )

    # Then 1
    assert isinstance(result, HelpTicketResponse)
    # Then 2
    assert result.ticket_number == "HELP-2026-001"
    assert result.status == OPEN
    # Then 3
    assert result.workspace_id == w1.id
    assert result.created_by == cr.id
    assert result.creator_name == "Rahim"
    # Then 4
    assert result.title == "Printer jam"
    assert result.description == "It jams"
    assert result.category == "hardware"
    # Then 5
    assert result.closed_at is None
    assert result.closed_by is None
    # Then 6
    assert result.created_at is not None
    assert result.updated_at is not None
    # Then 7
    db.rollback()
    row = committed(db, result.id)
    assert row is not None
    assert row.ticket_number == "HELP-2026-001"
    assert row.created_by == cr.id


# [claude] HTS-C-02
def test_hts_c_02__an_unknown_user_rolls_back_reaches_the_caller_and_discards_other_pending_changes(
    db,
    w1,
    w2,
    mk_extra,
):
    """HTS-C-02 — an unknown user rolls back, reaches the caller, and discards other pending changes.
    Rules: `create_ticket` R4, TC3, Errors"""
    commit_point(db)
    w1_id, w2_id = w1.id, w2.id
    before = counts(db, w1_id, w2_id)
    x_id = mk_extra()

    # Then 1
    with pytest.raises(IntegrityError), clock():
        svc.create_ticket(
            db,
            workspace=w1,
            user=SimpleNamespace(id=MISSING, name="Ghost"),
            payload=HelpTicketCreate(title="Printer jam", description="It jams"),
        )
    # Then 2
    assert x_gone(db, x_id)
    # Then 3
    assert counts(db, w1_id, w2_id) == before
    # Then 4
    assert db.execute(text("SELECT 1")).scalar() == 1


# [claude] HTS-C-03
def test_hts_c_03__a_failing_commit_rolls_back_and_nothing_is_saved(db, w1, w2, cr):
    """HTS-C-03 — a failing commit rolls back and nothing is saved.
    Rules: `create_ticket` R4, TC4"""
    commit_point(db)
    w1_id, w2_id = w1.id, w2.id
    before = counts(db, w1_id, w2_id)
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb, clock():
            svc.create_ticket(
                db,
                workspace=w1,
                user=cr,
                payload=HelpTicketCreate(title="Printer jam", description="It jams"),
            )

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert counts(db, w1_id, w2_id) == before


# [claude] HTS-C-04
def test_hts_c_04__a_failing_reread_after_the_commit_leaves_the_ticket_saved(
    db, w1, cr
):
    """HTS-C-04 — a failing re-read after the commit leaves the ticket saved.
    Rules: `create_ticket` R4, TC5"""
    commit_point(db)
    w1_id, cr_id = w1.id, cr.id
    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db), clock():
            svc.create_ticket(
                db,
                workspace=w1,
                user=cr,
                payload=HelpTicketCreate(title="Printer jam", description="It jams"),
            )

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    db.rollback()
    db.expire_all()
    rows = (
        db.execute(select(HelpTicket).where(HelpTicket.workspace_id == w1_id))
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].title == "Printer jam"
    assert rows[0].created_by == cr_id


# [claude] HTS-C-05
@pytest.mark.xfail(strict=True, reason=BUG_1441)
def test_hts_c_05__the_year_of_the_number_is_the_utc_year_pass_through(db, w1, cr):
    """HTS-C-05 — the year of the number is the UTC year (pass-through).
    Rules: `create_ticket` R1 (DAO `create_with_user` R2 [BUG-1441])"""
    commit_point(db)
    with clock(now=datetime(2027, 1, 1, 5, 0), utc=datetime(2026, 12, 31, 23, 0)):
        result = svc.create_ticket(
            db,
            workspace=w1,
            user=cr,
            payload=HelpTicketCreate(title="Printer jam", description="It jams"),
        )

    # Then 1
    assert isinstance(result, HelpTicketResponse)
    # Then 2
    assert result.ticket_number == "HELP-2026-001"


# [claude] HTS-C-06
@pytest.mark.xfail(strict=True, reason=BUG_1574)
def test_hts_c_06__title_description_and_category_are_stored_trimmed(db, w1, cr):
    """HTS-C-06 — title, description and category are stored trimmed.
    Rules: `create_ticket` R2 [BUG-1574]"""
    commit_point(db)
    with clock():
        result = svc.create_ticket(
            db,
            workspace=w1,
            user=cr,
            payload=HelpTicketCreate(
                title="  Printer  ", description="  It jams  ", category=" hardware "
            ),
        )

    # Then 1
    assert isinstance(result, HelpTicketResponse)
    # Then 2
    assert reread(db, result.id).title == "Printer"
    # Then 3
    assert reread(db, result.id).description == "It jams"
    # Then 4
    assert reread(db, result.id).category == "hardware"


# [claude] HTS-C-07
@pytest.mark.xfail(strict=True, reason=BUG_1574)
def test_hts_c_07__a_whitespace_only_title_is_refused_by_the_schema():
    """HTS-C-07 — a whitespace-only title is refused by the schema.
    Rules: `create_ticket` R2 [BUG-1574]"""
    # Then 1
    with pytest.raises(PydanticValidationError):
        HelpTicketCreate(title="   ", description="It jams")


# [claude] HTS-C-08
@pytest.mark.xfail(strict=True, reason=BUG_1574)
def test_hts_c_08__a_whitespace_only_description_is_refused_by_the_schema():
    """HTS-C-08 — a whitespace-only description is refused by the schema.
    Rules: `create_ticket` R2 [BUG-1574]"""
    # Then 1
    with pytest.raises(PydanticValidationError):
        HelpTicketCreate(title="Printer jam", description="   ")


# [claude] HTS-C-09
@pytest.mark.xfail(strict=True, reason=BUG_1574)
def test_hts_c_09__a_whitespace_only_category_is_stored_as_none(db, w1, cr):
    """HTS-C-09 — a whitespace-only category is stored as None.
    Rules: `create_ticket` R2 [BUG-1574]"""
    commit_point(db)
    with clock():
        result = svc.create_ticket(
            db,
            workspace=w1,
            user=cr,
            payload=HelpTicketCreate(
                title="Printer jam", description="It jams", category="   "
            ),
        )

    # Then 1
    assert isinstance(result, HelpTicketResponse)
    # Then 2
    assert reread(db, result.id).category is None


# [claude] HTS-C-10
def test_hts_c_10__inner_spaces_and_capitals_are_kept(db, w1, cr):
    """HTS-C-10 — inner spaces and capitals are kept.
    Rules: `create_ticket` R2"""
    commit_point(db)
    with clock():
        result = svc.create_ticket(
            db,
            workspace=w1,
            user=cr,
            payload=HelpTicketCreate(
                title="Printer  JAM", description="It  jams", category="Hard  ware"
            ),
        )

    # Then 1
    assert result.title == "Printer  JAM"
    # Then 2
    row = reread(db, result.id)
    assert row.title == "Printer  JAM"
    assert row.description == "It  jams"
    assert row.category == "Hard  ware"


# --------------------------------------------------------------------------- #
# HelpTicketService.list_tickets
# --------------------------------------------------------------------------- #


# [claude] HTS-L-01
def test_hts_l_01__an_owner_sees_every_ticket_of_the_workspace_not_another_workspaces(
    db,
    w1,
    w2,
    mgr,
    own,
    mk_ticket,
):
    """HTS-L-01 — an owner sees every ticket of the workspace, not another workspace's.
    Rules: `list_tickets` R1"""
    tm = mk_ticket("HELP-2026-001", created_by=mgr.id)
    tc = mk_ticket("HELP-2026-002")
    to = mk_ticket("HELP-2026-003", created_by=own.id)
    tn = mk_ticket("HELP-2026-004", created_by=None)
    mk_ticket("HELP-2026-001", workspace_id=w2.id)
    result = svc.list_tickets(
        db, workspace_id=w1.id, user=own, role=OWNER_R, limit=1000
    )

    # Then 1
    assert all(isinstance(t, HelpTicketResponse) for t in result)
    # Then 2
    assert idset(result) == {tm.id, tc.id, to.id, tn.id}


# [claude] HTS-L-02
def test_hts_l_02__a_ground_team_manager_sees_every_ticket_of_the_workspace(
    db, w1, w2, mgr, own, mk_ticket
):
    """HTS-L-02 — a ground-team-manager sees every ticket of the workspace.
    Rules: `list_tickets` R1"""
    tm = mk_ticket("HELP-2026-001", created_by=mgr.id)
    tc = mk_ticket("HELP-2026-002")
    to = mk_ticket("HELP-2026-003", created_by=own.id)
    mk_ticket("HELP-2026-001", workspace_id=w2.id)
    result = svc.list_tickets(db, workspace_id=w1.id, user=mgr, role=GTM_R, limit=1000)

    # Then 1
    assert idset(result) == {tm.id, tc.id, to.id}


# [claude] HTS-L-03
def test_hts_l_03__a_ground_team_member_sees_only_their_own_not_lower_or_higher_creators(
    db,
    w1,
    w2,
    mgr,
    cr,
    own,
    mk_ticket,
):
    """HTS-L-03 — a ground-team member sees only their own, not lower or higher creators'.
    Rules: `list_tickets` R1"""
    mk_ticket("HELP-2026-001", created_by=mgr.id)
    tc = mk_ticket("HELP-2026-002")
    mk_ticket("HELP-2026-003", created_by=own.id)
    mk_ticket("HELP-2026-004", created_by=None)
    mk_ticket("HELP-2026-001", workspace_id=w2.id)
    result = svc.list_tickets(db, workspace_id=w1.id, user=cr, role=GT_R, limit=1000)

    # Then 1
    assert idset(result) == {tc.id}


# [claude] HTS-L-04
def test_hts_l_04__a_finance_member_sees_only_their_own(
    db, w1, mgr, cr, own, mk_ticket
):
    """HTS-L-04 — a finance member sees only their own.
    Rules: `list_tickets` R1"""
    mk_ticket("HELP-2026-001", created_by=mgr.id)
    tc = mk_ticket("HELP-2026-002")
    mk_ticket("HELP-2026-003", created_by=own.id)
    result = svc.list_tickets(db, workspace_id=w1.id, user=cr, role=FIN_R, limit=1000)

    # Then 1
    assert idset(result) == {tc.id}


# [claude] HTS-L-05
def test_hts_l_05__no_role_sees_only_their_own(db, w1, mgr, cr, own, mk_ticket):
    """HTS-L-05 — no role sees only their own.
    Rules: `list_tickets` R1"""
    mk_ticket("HELP-2026-001", created_by=mgr.id)
    tc = mk_ticket("HELP-2026-002")
    mk_ticket("HELP-2026-003", created_by=own.id)
    result = svc.list_tickets(db, workspace_id=w1.id, user=cr, role=None, limit=1000)

    # Then 1
    assert idset(result) == {tc.id}


# [claude] HTS-L-06
def test_hts_l_06__the_later_workspaces_list_does_not_show_the_earlier_workspaces_tickets(
    db,
    w2,
    own,
    mk_ticket,
):
    """HTS-L-06 — the later workspace's list does not show the earlier workspace's tickets.
    Rules: `list_tickets` R1"""
    mk_ticket("HELP-2026-001")
    tz = mk_ticket("HELP-2026-001", workspace_id=w2.id)
    result = svc.list_tickets(
        db, workspace_id=w2.id, user=own, role=OWNER_R, limit=1000
    )

    # Then 1
    assert idset(result) == {tz.id}


# [claude] HTS-L-07
def test_hts_l_07__status_closed_keeps_only_closed_tickets(
    db, w1, own, mk_ticket, mk_closed
):
    """HTS-L-07 — status closed keeps only closed tickets.
    Rules: `list_tickets` R1"""
    mk_ticket("HELP-2026-001")
    tb = mk_closed("HELP-2026-002")
    result = svc.list_tickets(
        db, workspace_id=w1.id, user=own, role=OWNER_R, status=CLOSED, limit=1000
    )

    # Then 1
    assert idset(result) == {tb.id}


# [claude] HTS-L-08
def test_hts_l_08__status_open_keeps_only_open_tickets(
    db, w1, own, mk_ticket, mk_closed
):
    """HTS-L-08 — status open keeps only open tickets.
    Rules: `list_tickets` R1"""
    mk_closed("HELP-2026-001")
    tb = mk_ticket("HELP-2026-002")
    result = svc.list_tickets(
        db, workspace_id=w1.id, user=own, role=OWNER_R, status=OPEN, limit=1000
    )

    # Then 1
    assert idset(result) == {tb.id}


# [claude] HTS-L-09
def test_hts_l_09__the_default_limit_is_100(db, w1, own, mk_ticket):
    """HTS-L-09 — the default limit is 100.
    Rules: `list_tickets` R1 (paging)"""
    for k in range(1, 102):
        mk_ticket(f"HELP-2026-{k:03d}")
    result = svc.list_tickets(db, workspace_id=w1.id, user=own, role=OWNER_R)

    # Then 1
    assert len(result) == 100


# [claude] HTS-L-10
def test_hts_l_10__skip_reaches_the_query(db, w1, own, mk_ticket):
    """HTS-L-10 — skip reaches the query.
    Rules: `list_tickets` R1 (paging)"""
    mk_ticket("HELP-2026-001")
    mk_ticket("HELP-2026-002")
    result = svc.list_tickets(
        db, workspace_id=w1.id, user=own, role=OWNER_R, skip=2, limit=1000
    )

    # Then 1
    assert result == []


# [claude] HTS-L-11
def test_hts_l_11__limit_reaches_the_query(db, w1, own, mk_ticket):
    """HTS-L-11 — limit reaches the query.
    Rules: `list_tickets` R1 (paging)"""
    ta = mk_ticket("HELP-2026-001")
    tb = mk_ticket("HELP-2026-002")
    result = svc.list_tickets(db, workspace_id=w1.id, user=own, role=OWNER_R, limit=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert idset(result) <= {ta.id, tb.id}


# [claude] HTS-L-12
@pytest.mark.xfail(strict=True, reason=BUG_1578)
def test_hts_l_12__a_platform_admin_without_a_role_sees_every_ticket_of_the_workspace(
    db,
    w1,
    w2,
    mgr,
    adm,
    mk_ticket,
):
    """HTS-L-12 — a platform admin without a role sees every ticket of the workspace.
    Rules: `list_tickets` R2 [BUG-1578]"""
    tm = mk_ticket("HELP-2026-001", created_by=mgr.id)
    tc = mk_ticket("HELP-2026-002")
    mk_ticket("HELP-2026-001", workspace_id=w2.id)
    result = svc.list_tickets(db, workspace_id=w1.id, user=adm, role=None, limit=1000)

    # Then 1
    assert idset(result) == {tm.id, tc.id}


# [claude] HTS-L-13
def test_hts_l_13__each_entry_carries_its_creators_name_none_without_a_creator(
    db, w1, mgr, own, mk_ticket
):
    """HTS-L-13 — each entry carries its creator's name, None without a creator.
    Rules: `list_tickets` R3"""
    tm = mk_ticket("HELP-2026-001", created_by=mgr.id)
    tc = mk_ticket("HELP-2026-002")
    tn = mk_ticket("HELP-2026-003", created_by=None)
    result = svc.list_tickets(
        db, workspace_id=w1.id, user=own, role=OWNER_R, limit=1000
    )

    # Then 1
    assert {t.id: t.creator_name for t in result} == {
        tm.id: "Karim",
        tc.id: "Rahim",
        tn.id: None,
    }


# [claude] HTS-L-14
def test_hts_l_14__a_list_neither_commits_nor_rolls_back(
    db, w1, own, mk_ticket, mk_pending
):
    """HTS-L-14 — a list neither commits nor rolls back.
    Rules: `list_tickets` R4, TC6"""
    tc = mk_ticket("HELP-2026-001")
    commit_point(db)
    p = mk_pending()
    with spies(db) as (cm, rb):
        result = svc.list_tickets(
            db, workspace_id=w1.id, user=own, role=OWNER_R, limit=1000
        )

    # Then 1
    assert idset(result) == {tc.id}
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert db.get(HelpTicket, p.id) is not None


# [claude] HTS-L-15
def test_hts_l_15__a_negative_limit_raises_dataerror_when_called_directly(
    db, w1, own, mk_ticket
):
    """HTS-L-15 — a negative limit raises DataError when called directly.
    Rules: `list_tickets` Errors"""
    mk_ticket("HELP-2026-001")

    # Then 1
    with pytest.raises(DataError):
        with db.begin_nested():
            svc.list_tickets(db, workspace_id=w1.id, user=own, role=OWNER_R, limit=-1)


# [claude] HTS-L-16
@pytest.mark.xfail(strict=False, reason=BUG_1442)
def test_hts_l_16__tied_times_come_back_id_descending_pass_through(
    db, w1, own, mk_ticket
):
    """HTS-L-16 — tied times come back id descending (pass-through).
    Rules: `list_tickets` R1 (DAO `list_by_workspace` R5 [BUG-1442])"""
    seqscan(db)
    ta = mk_ticket("HELP-2026-001")
    tb = mk_ticket("HELP-2026-002")
    tc = mk_ticket("HELP-2026-003")
    db.execute(
        text("UPDATE help_tickets SET title = 'Printer jam!' WHERE id = :i"),
        {"i": ta.id},
    )
    db.expire_all()
    result = svc.list_tickets(
        db, workspace_id=w1.id, user=own, role=OWNER_R, limit=1000
    )

    # Then 1
    assert [t.id for t in result] == [tc.id, tb.id, ta.id]


# --------------------------------------------------------------------------- #
# HelpTicketService.get_ticket
# --------------------------------------------------------------------------- #


# [claude] HTS-G-01
def test_hts_g_01__the_creator_gets_their_ticket_with_every_field_not_a_neighbour(
    db, w1, cr, mk_ticket
):
    """HTS-G-01 — the creator gets their ticket with every field, not a neighbour.
    Rules: `get_ticket` R1"""
    mk_ticket("HELP-2026-001", title="Other")
    t = mk_ticket("HELP-2026-002")
    mk_ticket("HELP-2026-003", title="Third")
    result = svc.get_ticket(db, workspace_id=w1.id, ticket_id=t.id, user=cr, role=GT_R)

    # Then 1
    assert isinstance(result, HelpTicketResponse)
    # Then 2
    assert result.id == t.id
    assert result.ticket_number == "HELP-2026-002"
    assert result.workspace_id == w1.id
    # Then 3
    assert result.title == "Printer jam"
    assert result.description == "It jams"
    assert result.category == "hardware"
    # Then 4
    assert result.status == OPEN
    assert result.created_by == cr.id
    assert result.creator_name == "Rahim"


# [claude] HTS-G-02
def test_hts_g_02__an_owner_higher_id_than_the_creator_gets_a_members_ticket(
    db, w1, own, mk_ticket
):
    """HTS-G-02 — an owner (higher id than the creator) gets a member's ticket.
    Rules: `get_ticket` R1"""
    t = mk_ticket("HELP-2026-001")
    result = svc.get_ticket(
        db, workspace_id=w1.id, ticket_id=t.id, user=own, role=OWNER_R
    )

    # Then 1
    assert result.id == t.id
    assert result.creator_name == "Rahim"


# [claude] HTS-G-03
def test_hts_g_03__a_ground_team_manager_lower_id_than_the_creator_gets_a_members_ticket(
    db, w1, mgr, mk_ticket
):
    """HTS-G-03 — a ground-team-manager (lower id than the creator) gets a member's ticket.
    Rules: `get_ticket` R1"""
    t = mk_ticket("HELP-2026-001")
    result = svc.get_ticket(
        db, workspace_id=w1.id, ticket_id=t.id, user=mgr, role=GTM_R
    )

    # Then 1
    assert result.id == t.id


# [claude] HTS-G-04
def test_hts_g_04__a_platform_admin_without_a_role_gets_a_members_ticket(
    db, w1, adm, mk_ticket
):
    """HTS-G-04 — a platform admin without a role gets a member's ticket.
    Rules: `get_ticket` R1"""
    t = mk_ticket("HELP-2026-001")
    result = svc.get_ticket(db, workspace_id=w1.id, ticket_id=t.id, user=adm, role=None)

    # Then 1
    assert result.id == t.id


# [claude] HTS-G-05
def test_hts_g_05__a_ground_team_member_with_a_lower_id_than_the_creator_is_refused(
    db, w1, mgr, mk_ticket
):
    """HTS-G-05 — a ground-team member with a lower id than the creator is refused.
    Rules: `get_ticket` R2, Errors"""
    t = mk_ticket("HELP-2026-001")

    # Then 1
    with pytest.raises(HelpTicketForbiddenError) as exc:
        svc.get_ticket(db, workspace_id=w1.id, ticket_id=t.id, user=mgr, role=GT_R)
    # Then 2
    assert type(exc.value) is HelpTicketForbiddenError
    # Then 3
    assert str(exc.value) == FORBID


# [claude] HTS-G-06
def test_hts_g_06__a_finance_member_with_a_higher_id_than_the_creator_is_refused(
    db, w1, fin, mk_ticket
):
    """HTS-G-06 — a finance member with a higher id than the creator is refused.
    Rules: `get_ticket` R2"""
    t = mk_ticket("HELP-2026-001")

    # Then 1
    with pytest.raises(HelpTicketForbiddenError) as exc:
        svc.get_ticket(db, workspace_id=w1.id, ticket_id=t.id, user=fin, role=FIN_R)
    # Then 2
    assert str(exc.value) == FORBID


# [claude] HTS-G-07
def test_hts_g_07__no_role_and_not_a_platform_admin_is_refused(db, w1, own, mk_ticket):
    """HTS-G-07 — no role and not a platform admin is refused.
    Rules: `get_ticket` R2"""
    t = mk_ticket("HELP-2026-001")

    # Then 1
    with pytest.raises(HelpTicketForbiddenError) as exc:
        svc.get_ticket(db, workspace_id=w1.id, ticket_id=t.id, user=own, role=None)
    # Then 2
    assert str(exc.value) == FORBID


# [claude] HTS-G-08
def test_hts_g_08__an_unknown_id_is_not_found(db, w1, own, mk_ticket):
    """HTS-G-08 — an unknown id is not found.
    Rules: `get_ticket` R3"""
    mk_ticket("HELP-2026-001")

    # Then 1
    with pytest.raises(HelpTicketNotFoundError) as exc:
        svc.get_ticket(
            db, workspace_id=w1.id, ticket_id=MISSING, user=own, role=OWNER_R
        )
    # Then 2
    assert type(exc.value) is HelpTicketNotFoundError
    # Then 3
    assert str(exc.value) == NOTFOUND


# [claude] HTS-G-09
def test_hts_g_09__id_0_is_not_found(db, w1, own, mk_ticket):
    """HTS-G-09 — id 0 is not found.
    Rules: `get_ticket` R3"""
    mk_ticket("HELP-2026-001")

    # Then 1
    with pytest.raises(HelpTicketNotFoundError) as exc:
        svc.get_ticket(db, workspace_id=w1.id, ticket_id=0, user=own, role=OWNER_R)
    # Then 2
    assert str(exc.value) == NOTFOUND


# [claude] HTS-G-10
def test_hts_g_10__the_later_workspaces_ticket_asked_in_the_earlier_workspace_is_not_found_even_by_its_creator(
    db,
    w1,
    w2,
    cr,
    mk_ticket,
):
    """HTS-G-10 — the later workspace's ticket asked in the earlier workspace is not found, even by its creator.
    Rules: `get_ticket` R3"""
    tz = mk_ticket("HELP-2026-001", workspace_id=w2.id)

    # Then 1
    with pytest.raises(HelpTicketNotFoundError) as exc:
        svc.get_ticket(db, workspace_id=w1.id, ticket_id=tz.id, user=cr, role=OWNER_R)
    # Then 2
    assert str(exc.value) == NOTFOUND


# [claude] HTS-G-11
def test_hts_g_11__the_earlier_workspaces_ticket_asked_in_the_later_workspace_is_not_found(
    db,
    w2,
    own,
    mk_ticket,
):
    """HTS-G-11 — the earlier workspace's ticket asked in the later workspace is not found.
    Rules: `get_ticket` R3"""
    t = mk_ticket("HELP-2026-001")

    # Then 1
    with pytest.raises(HelpTicketNotFoundError) as exc:
        svc.get_ticket(db, workspace_id=w2.id, ticket_id=t.id, user=own, role=OWNER_R)
    # Then 2
    assert str(exc.value) == NOTFOUND


# [claude] HTS-G-12
def test_hts_g_12__another_workspaces_ticket_gives_not_found_before_any_access_check(
    db, w1, w2, fin, mk_ticket
):
    """HTS-G-12 — another workspace's ticket gives "not found" before any access check.
    Rules: `get_ticket` R3"""
    tz = mk_ticket("HELP-2026-001", workspace_id=w2.id)

    # Then 1
    with pytest.raises(HelpTicketNotFoundError) as exc:
        svc.get_ticket(db, workspace_id=w1.id, ticket_id=tz.id, user=fin, role=FIN_R)
    # Then 2
    assert str(exc.value) == NOTFOUND


# [claude] HTS-G-13
def test_hts_g_13__a_ticket_whose_creator_is_gone_is_refused_to_a_plain_member(
    db, w1, fin, mk_ticket
):
    """HTS-G-13 — a ticket whose creator is gone is refused to a plain member.
    Rules: `get_ticket` R4"""
    t = mk_ticket("HELP-2026-001", created_by=None)

    # Then 1
    with pytest.raises(HelpTicketForbiddenError) as exc:
        svc.get_ticket(db, workspace_id=w1.id, ticket_id=t.id, user=fin, role=FIN_R)
    # Then 2
    assert str(exc.value) == FORBID


# [claude] HTS-G-14
def test_hts_g_14__a_ticket_whose_creator_is_gone_shows_creator_name_none_to_an_owner(
    db, w1, own, mk_ticket
):
    """HTS-G-14 — a ticket whose creator is gone shows creator_name None to an owner.
    Rules: `get_ticket` R4"""
    t = mk_ticket("HELP-2026-001", created_by=None)
    result = svc.get_ticket(
        db, workspace_id=w1.id, ticket_id=t.id, user=own, role=OWNER_R
    )

    # Then 1
    assert result.id == t.id
    # Then 2
    assert result.created_by is None
    assert result.creator_name is None


# [claude] HTS-G-15
def test_hts_g_15__a_get_neither_commits_nor_rolls_back(
    db, w1, cr, mk_ticket, mk_pending
):
    """HTS-G-15 — a get neither commits nor rolls back.
    Rules: `get_ticket` R4, TC6"""
    t = mk_ticket("HELP-2026-001")
    commit_point(db)
    p = mk_pending()
    with spies(db) as (cm, rb):
        result = svc.get_ticket(
            db, workspace_id=w1.id, ticket_id=t.id, user=cr, role=GT_R
        )

    # Then 1
    assert result.id == t.id
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert db.get(HelpTicket, p.id) is not None


# [claude] HTS-G-16
def test_hts_g_16__a_refused_get_does_not_roll_back_the_session(
    db, w1, fin, mk_ticket, mk_pending
):
    """HTS-G-16 — a refused get does not roll back the session.
    Rules: `get_ticket` R2, TC6"""
    t = mk_ticket("HELP-2026-001")
    commit_point(db)
    p = mk_pending()
    with spies(db) as (_cm, rb):
        # Then 1
        with pytest.raises(HelpTicketForbiddenError):
            svc.get_ticket(db, workspace_id=w1.id, ticket_id=t.id, user=fin, role=FIN_R)

    # Then 2
    assert rb.call_count == 0
    # Then 3
    assert db.get(HelpTicket, p.id) is not None


# --------------------------------------------------------------------------- #
# HelpTicketService.update_ticket
# --------------------------------------------------------------------------- #


# [claude] HTS-U-01
def test_hts_u_01__the_creator_changes_title_description_and_category_committed(
    db, w1, cr, mk_ticket
):
    """HTS-U-01 — the creator changes title, description and category; committed.
    Rules: `update_ticket` R3, R2, R7, TC1"""
    ta = mk_ticket("HELP-2026-001", title="Other")
    t = mk_ticket("HELP-2026-002")
    tb = mk_ticket("HELP-2026-003", title="Third")
    commit_point(db)
    t_id, ta_id, tb_id = t.id, ta.id, tb.id
    with close_clock():
        result = svc.update_ticket(
            db,
            workspace_id=w1.id,
            ticket_id=t_id,
            user=cr,
            role=GT_R,
            payload=HelpTicketUpdate(
                title="Toner low", description="Grey prints", category="supplies"
            ),
        )

    # Then 1
    assert isinstance(result, HelpTicketResponse)
    # Then 2
    assert result.id == t_id
    assert result.title == "Toner low"
    assert result.creator_name == "Rahim"
    # Then 3
    db.rollback()
    row = committed(db, t_id)
    assert row.title == "Toner low"
    assert row.description == "Grey prints"
    assert row.category == "supplies"
    assert row.status == "open"
    # Then 4
    assert committed(db, ta_id).title == "Other"
    assert committed(db, tb_id).title == "Third"


# [claude] HTS-U-02
def test_hts_u_02__a_creator_who_is_an_owner_changes_their_own_tickets_text(
    db, w1, own, mk_ticket
):
    """HTS-U-02 — a creator who is an owner changes their own ticket's text.
    Rules: `update_ticket` R3"""
    t = mk_ticket("HELP-2026-001", created_by=own.id)
    commit_point(db)
    t_id = t.id
    with close_clock():
        result = svc.update_ticket(
            db,
            workspace_id=w1.id,
            ticket_id=t_id,
            user=own,
            role=OWNER_R,
            payload=HelpTicketUpdate(title="Toner low"),
        )

    # Then 1
    assert result.title == "Toner low"
    # Then 2
    db.rollback()
    row = committed(db, t_id)
    assert row.title == "Toner low"
    assert row.description == "It jams"


# [claude] HTS-U-03
def test_hts_u_03__an_empty_payload_changes_nothing(db, w1, cr, mk_ticket):
    """HTS-U-03 — an empty payload changes nothing.
    Rules: `update_ticket` R2"""
    t = mk_ticket("HELP-2026-001")
    commit_point(db)
    t_id = t.id
    before = snap(db, t_id)
    with close_clock():
        result = svc.update_ticket(
            db,
            workspace_id=w1.id,
            ticket_id=t_id,
            user=cr,
            role=GT_R,
            payload=HelpTicketUpdate(),
        )

    # Then 1
    assert result.id == t_id
    assert result.title == "Printer jam"
    assert result.status == OPEN
    # Then 2
    assert snap(db, t_id) == before


# [claude] HTS-U-04
def test_hts_u_04__a_ground_team_manager_closes_a_members_ticket(
    db, w1, mgr, mk_ticket
):
    """HTS-U-04 — a ground-team-manager closes a member's ticket.
    Rules: `update_ticket` R5, R7"""
    t = mk_ticket("HELP-2026-001")
    commit_point(db)
    t_id, mgr_id = t.id, mgr.id
    with close_clock():
        result = svc.update_ticket(
            db,
            workspace_id=w1.id,
            ticket_id=t_id,
            user=mgr,
            role=GTM_R,
            payload=HelpTicketUpdate(status="closed"),
        )

    # Then 1
    assert result.status == CLOSED
    assert result.closed_by == mgr_id
    assert result.creator_name == "Rahim"
    # Then 2
    db.rollback()
    row = committed(db, t_id)
    assert row.status == "closed"
    assert row.closed_by == mgr_id
    assert row.title == "Printer jam"
    # Then 3
    assert committed(db, t_id).closed_at is not None


# [claude] HTS-U-05
def test_hts_u_05__an_owner_reopens_a_closed_ticket_closed_at_and_closed_by_are_cleared(
    db, w1, own, mk_closed
):
    """HTS-U-05 — an owner reopens a closed ticket: closed_at and closed_by are cleared.
    Rules: `update_ticket` R5"""
    t = mk_closed("HELP-2026-001")
    commit_point(db)
    t_id = t.id
    with close_clock():
        result = svc.update_ticket(
            db,
            workspace_id=w1.id,
            ticket_id=t_id,
            user=own,
            role=OWNER_R,
            payload=HelpTicketUpdate(status="open"),
        )

    # Then 1
    assert result.status == OPEN
    assert result.closed_at is None
    assert result.closed_by is None
    # Then 2
    db.rollback()
    row = committed(db, t_id)
    assert row.status == "open"
    assert row.closed_at is None
    assert row.closed_by is None


# [claude] HTS-U-06
def test_hts_u_06__a_platform_admin_without_a_role_closes_a_members_ticket(
    db, w1, adm, mk_ticket
):
    """HTS-U-06 — a platform admin without a role closes a member's ticket.
    Rules: `update_ticket` R5"""
    t = mk_ticket("HELP-2026-001")
    commit_point(db)
    t_id, adm_id = t.id, adm.id
    with close_clock():
        result = svc.update_ticket(
            db,
            workspace_id=w1.id,
            ticket_id=t_id,
            user=adm,
            role=None,
            payload=HelpTicketUpdate(status="closed"),
        )

    # Then 1
    assert result.status == CLOSED
    # Then 2
    db.rollback()
    row = committed(db, t_id)
    assert row.status == "closed"
    assert row.closed_by == adm_id


# [claude] HTS-U-07
def test_hts_u_07__status_null_leaves_status_closed_at_and_closed_by(
    db, w1, cr, mk_closed
):
    """HTS-U-07 — status null leaves status, closed_at and closed_by.
    Rules: `update_ticket` R5"""
    t = mk_closed("HELP-2026-001")
    commit_point(db)
    t_id = t.id
    before = snap(db, t_id)
    with close_clock():
        result = svc.update_ticket(
            db,
            workspace_id=w1.id,
            ticket_id=t_id,
            user=cr,
            role=GT_R,
            payload=HelpTicketUpdate(status=None),
        )

    # Then 1
    assert result.status == CLOSED
    # Then 2
    assert snap(db, t_id) == before


# [claude] HTS-U-08
def test_hts_u_08__a_text_change_without_status_leaves_the_closed_state(
    db, w1, mgr, cr, mk_closed
):
    """HTS-U-08 — a text change without status leaves the closed state.
    Rules: `update_ticket` R5, R3"""
    t = mk_closed("HELP-2026-001")
    commit_point(db)
    t_id, mgr_id = t.id, mgr.id
    with close_clock():
        result = svc.update_ticket(
            db,
            workspace_id=w1.id,
            ticket_id=t_id,
            user=cr,
            role=GT_R,
            payload=HelpTicketUpdate(category="network"),
        )

    # Then 1
    assert result.category == "network"
    # Then 2
    db.rollback()
    row = committed(db, t_id)
    assert row.category == "network"
    assert row.status == "closed"
    assert row.closed_at == PAST
    assert row.closed_by == mgr_id


# [claude] HTS-U-09
def test_hts_u_09__reopening_an_open_ticket_changes_nothing(db, w1, own, mk_ticket):
    """HTS-U-09 — reopening an open ticket changes nothing.
    Rules: `update_ticket` R6"""
    t = mk_ticket("HELP-2026-001")
    commit_point(db)
    t_id = t.id
    before = snap(db, t_id)
    with close_clock():
        result = svc.update_ticket(
            db,
            workspace_id=w1.id,
            ticket_id=t_id,
            user=own,
            role=OWNER_R,
            payload=HelpTicketUpdate(status="open"),
        )

    # Then 1
    assert result.status == OPEN
    # Then 2
    assert snap(db, t_id) == before


# [claude] HTS-U-10
@pytest.mark.xfail(strict=True, reason=BUG_1576)
def test_hts_u_10__closing_an_already_closed_ticket_keeps_who_closed_it_and_when(
    db, w1, mgr, own, mk_closed
):
    """HTS-U-10 — closing an already closed ticket keeps who closed it and when.
    Rules: `update_ticket` R6 [BUG-1576]"""
    t = mk_closed("HELP-2026-001")
    commit_point(db)
    t_id, mgr_id = t.id, mgr.id
    with close_clock():
        result = svc.update_ticket(
            db,
            workspace_id=w1.id,
            ticket_id=t_id,
            user=own,
            role=OWNER_R,
            payload=HelpTicketUpdate(status="closed"),
        )

    # Then 1
    assert result.status == CLOSED
    # Then 2
    assert reread(db, t_id).closed_by == mgr_id
    # Then 3
    assert reread(db, t_id).closed_at == PAST


# [claude] HTS-U-11
@pytest.mark.xfail(strict=True, reason=BUG_1577)
def test_hts_u_11__closed_at_is_the_true_moment_whatever_the_databases_time_zone(
    db, w1, mgr, mk_ticket
):
    """HTS-U-11 — closed_at is the true moment whatever the database's time zone.
    Rules: `update_ticket` R6 [BUG-1577]"""
    db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))
    t = mk_ticket("HELP-2026-001")
    commit_point(db)
    t_id = t.id
    # Real clock: no close clock in this card
    result = svc.update_ticket(
        db,
        workspace_id=w1.id,
        ticket_id=t_id,
        user=mgr,
        role=GTM_R,
        payload=HelpTicketUpdate(status="closed"),
    )

    # Then 1
    assert result.status == CLOSED
    # Then 2
    row = reread(db, t_id)
    assert abs(row.closed_at - row.created_at) < timedelta(seconds=60)


# [claude] HTS-U-12
def test_hts_u_12__an_unknown_id_is_not_found_rolled_back_other_pending_changes_discarded(
    db,
    w1,
    w2,
    own,
    mk_ticket,
    mk_extra,
):
    """HTS-U-12 — an unknown id is not found, rolled back, other pending changes discarded.
    Rules: `update_ticket` R1, TC3, Errors row 1"""
    t = mk_ticket("HELP-2026-001")
    commit_point(db)
    t_id, w1_id, w2_id = t.id, w1.id, w2.id
    before = snap(db, t_id)
    before_counts = counts(db, w1_id, w2_id)
    x_id = mk_extra()

    # Then 1
    with pytest.raises(HelpTicketNotFoundError) as exc, close_clock():
        svc.update_ticket(
            db,
            workspace_id=w1_id,
            ticket_id=MISSING,
            user=own,
            role=OWNER_R,
            payload=HelpTicketUpdate(status="closed"),
        )
    # Then 2
    assert str(exc.value) == NOTFOUND
    # Then 3
    assert x_gone(db, x_id)
    # Then 4
    assert snap(db, t_id) == before
    # Then 5
    assert counts(db, w1_id, w2_id) == before_counts


# [claude] HTS-U-13
def test_hts_u_13__another_workspaces_ticket_is_not_found_and_not_changed(
    db, w1, w2, cr, mk_ticket
):
    """HTS-U-13 — another workspace's ticket is not found and not changed.
    Rules: `update_ticket` R1, Errors row 1"""
    tz = mk_ticket("HELP-2026-001", workspace_id=w2.id)
    commit_point(db)
    tz_id = tz.id
    before = snap(db, tz_id)

    # Then 1
    with pytest.raises(HelpTicketNotFoundError) as exc, close_clock():
        svc.update_ticket(
            db,
            workspace_id=w1.id,
            ticket_id=tz_id,
            user=cr,
            role=OWNER_R,
            payload=HelpTicketUpdate(status="closed"),
        )
    # Then 2
    assert str(exc.value) == NOTFOUND
    # Then 3
    assert snap(db, tz_id) == before


# [claude] HTS-U-14
def test_hts_u_14__a_finance_member_higher_id_who_did_not_create_it_may_not_close_it(
    db,
    w1,
    w2,
    fin,
    mk_ticket,
    mk_extra,
):
    """HTS-U-14 — a finance member (higher id) who did not create it may not close it.
    Rules: `update_ticket` R1, TC3, Errors row 2"""
    t = mk_ticket("HELP-2026-001")
    commit_point(db)
    t_id, w1_id, w2_id = t.id, w1.id, w2.id
    before = snap(db, t_id)
    before_counts = counts(db, w1_id, w2_id)
    x_id = mk_extra()

    # Then 1
    with pytest.raises(HelpTicketForbiddenError) as exc, close_clock():
        svc.update_ticket(
            db,
            workspace_id=w1_id,
            ticket_id=t_id,
            user=fin,
            role=FIN_R,
            payload=HelpTicketUpdate(status="closed"),
        )
    # Then 2
    assert str(exc.value) == FORBID
    # Then 3
    assert x_gone(db, x_id)
    # Then 4
    assert snap(db, t_id) == before
    # Then 5
    assert counts(db, w1_id, w2_id) == before_counts


# [claude] HTS-U-15
def test_hts_u_15__a_ground_team_member_lower_id_who_did_not_create_it_may_not_close_it(
    db, w1, mgr, mk_ticket
):
    """HTS-U-15 — a ground-team member (lower id) who did not create it may not close it.
    Rules: `update_ticket` R1, Errors row 2"""
    t = mk_ticket("HELP-2026-001")
    commit_point(db)
    t_id = t.id
    before = snap(db, t_id)

    # Then 1
    with pytest.raises(HelpTicketForbiddenError) as exc, close_clock():
        svc.update_ticket(
            db,
            workspace_id=w1.id,
            ticket_id=t_id,
            user=mgr,
            role=GT_R,
            payload=HelpTicketUpdate(status="closed"),
        )
    # Then 2
    assert str(exc.value) == FORBID
    # Then 3
    assert snap(db, t_id) == before


# [claude] HTS-U-16
@pytest.mark.xfail(strict=True, reason=BUG_1863)
def test_hts_u_16__a_ground_team_manager_may_not_change_a_members_title(
    db, w1, w2, mgr, mk_ticket
):
    """HTS-U-16 — a ground-team-manager may not change a member's title.
    Rules: `update_ticket` R3a [BUG-1863], Errors row 3"""
    t = mk_ticket("HELP-2026-001")
    commit_point(db)
    t_id, w1_id, w2_id = t.id, w1.id, w2.id
    before = snap(db, t_id)
    before_counts = counts(db, w1_id, w2_id)

    # Then 1
    with pytest.raises(HelpTicketForbiddenError) as exc, close_clock():
        svc.update_ticket(
            db,
            workspace_id=w1_id,
            ticket_id=t_id,
            user=mgr,
            role=GTM_R,
            payload=HelpTicketUpdate(title="Work order missing"),
        )
    # Then 2
    assert type(exc.value) is HelpTicketForbiddenError
    # Then 3
    assert str(exc.value) == FORBID
    # Then 4
    assert snap(db, t_id) == before
    # Then 5
    assert counts(db, w1_id, w2_id) == before_counts


# [claude] HTS-U-17
@pytest.mark.xfail(strict=True, reason=BUG_1863)
def test_hts_u_17__a_ground_team_manager_may_not_change_a_members_description(
    db, w1, w2, mgr, mk_ticket
):
    """HTS-U-17 — a ground-team-manager may not change a member's description.
    Rules: `update_ticket` R3a [BUG-1863]"""
    t = mk_ticket("HELP-2026-001")
    commit_point(db)
    t_id, w1_id, w2_id = t.id, w1.id, w2.id
    before = snap(db, t_id)
    before_counts = counts(db, w1_id, w2_id)

    # Then 1
    with pytest.raises(HelpTicketForbiddenError) as exc, close_clock():
        svc.update_ticket(
            db,
            workspace_id=w1_id,
            ticket_id=t_id,
            user=mgr,
            role=GTM_R,
            payload=HelpTicketUpdate(description="Nothing happened"),
        )
    # Then 2
    assert str(exc.value) == FORBID
    # Then 3
    assert snap(db, t_id) == before
    # Then 4
    assert counts(db, w1_id, w2_id) == before_counts


# [claude] HTS-U-18
@pytest.mark.xfail(strict=True, reason=BUG_1863)
def test_hts_u_18__a_ground_team_manager_may_not_change_a_members_category(
    db, w1, mgr, mk_ticket
):
    """HTS-U-18 — a ground-team-manager may not change a member's category.
    Rules: `update_ticket` R3a [BUG-1863]"""
    t = mk_ticket("HELP-2026-001")
    commit_point(db)
    t_id = t.id
    before = snap(db, t_id)

    # Then 1
    with pytest.raises(HelpTicketForbiddenError) as exc, close_clock():
        svc.update_ticket(
            db,
            workspace_id=w1.id,
            ticket_id=t_id,
            user=mgr,
            role=GTM_R,
            payload=HelpTicketUpdate(category="other"),
        )
    # Then 2
    assert str(exc.value) == FORBID
    # Then 3
    assert snap(db, t_id) == before
    # Then 4
    assert reread(db, t_id).category == "hardware"


# [claude] HTS-U-19
@pytest.mark.xfail(strict=True, reason=BUG_1863)
def test_hts_u_19__sending_category_null_counts_as_a_text_change_and_is_refused(
    db, w1, mgr, mk_ticket
):
    """HTS-U-19 — sending category null counts as a text change and is refused.
    Rules: `update_ticket` R3a [BUG-1863]"""
    t = mk_ticket("HELP-2026-001")
    commit_point(db)
    t_id = t.id
    before = snap(db, t_id)

    # Then 1
    with pytest.raises(HelpTicketForbiddenError) as exc, close_clock():
        svc.update_ticket(
            db,
            workspace_id=w1.id,
            ticket_id=t_id,
            user=mgr,
            role=GTM_R,
            payload=HelpTicketUpdate(category=None),
        )
    # Then 2
    assert str(exc.value) == FORBID
    # Then 3
    assert reread(db, t_id).category == "hardware"
    # Then 4
    assert snap(db, t_id) == before


# [claude] HTS-U-20
@pytest.mark.xfail(strict=True, reason=BUG_1863)
def test_hts_u_20__an_owner_higher_id_than_the_creator_may_not_change_a_members_title(
    db, w1, w2, own, mk_ticket
):
    """HTS-U-20 — an owner (higher id than the creator) may not change a member's title.
    Rules: `update_ticket` R3a [BUG-1863]"""
    t = mk_ticket("HELP-2026-001")
    commit_point(db)
    t_id, w1_id, w2_id = t.id, w1.id, w2.id
    before = snap(db, t_id)
    before_counts = counts(db, w1_id, w2_id)

    # Then 1
    with pytest.raises(HelpTicketForbiddenError) as exc, close_clock():
        svc.update_ticket(
            db,
            workspace_id=w1_id,
            ticket_id=t_id,
            user=own,
            role=OWNER_R,
            payload=HelpTicketUpdate(title="Work order missing"),
        )
    # Then 2
    assert str(exc.value) == FORBID
    # Then 3
    assert snap(db, t_id) == before
    # Then 4
    assert counts(db, w1_id, w2_id) == before_counts


# [claude] HTS-U-21
@pytest.mark.xfail(strict=True, reason=BUG_1863)
def test_hts_u_21__a_platform_admin_may_not_change_a_members_description(
    db, w1, w2, adm, mk_ticket
):
    """HTS-U-21 — a platform admin may not change a member's description.
    Rules: `update_ticket` R3a [BUG-1863]"""
    t = mk_ticket("HELP-2026-001")
    commit_point(db)
    t_id, w1_id, w2_id = t.id, w1.id, w2.id
    before = snap(db, t_id)
    before_counts = counts(db, w1_id, w2_id)

    # Then 1
    with pytest.raises(HelpTicketForbiddenError) as exc, close_clock():
        svc.update_ticket(
            db,
            workspace_id=w1_id,
            ticket_id=t_id,
            user=adm,
            role=None,
            payload=HelpTicketUpdate(description="Nothing happened"),
        )
    # Then 2
    assert str(exc.value) == FORBID
    # Then 3
    assert snap(db, t_id) == before
    # Then 4
    assert counts(db, w1_id, w2_id) == before_counts


# [claude] HTS-U-22
@pytest.mark.xfail(strict=True, reason=BUG_1863)
def test_hts_u_22__a_text_change_combined_with_a_close_is_refused_whole_the_ticket_stays_open(
    db, w1, mgr, mk_ticket
):
    """HTS-U-22 — a text change combined with a close is refused whole: the ticket stays open.
    Rules: `update_ticket` R3a [BUG-1863]"""
    t = mk_ticket("HELP-2026-001")
    commit_point(db)
    t_id = t.id
    before = snap(db, t_id)

    # Then 1
    with pytest.raises(HelpTicketForbiddenError) as exc, close_clock():
        svc.update_ticket(
            db,
            workspace_id=w1.id,
            ticket_id=t_id,
            user=mgr,
            role=GTM_R,
            payload=HelpTicketUpdate(title="Work order missing", status="closed"),
        )
    # Then 2
    assert str(exc.value) == FORBID
    # Then 3
    row = reread(db, t_id)
    assert row.status == "open"
    assert row.closed_at is None
    assert row.closed_by is None
    # Then 4
    assert snap(db, t_id) == before


# [claude] HTS-U-23
@pytest.mark.xfail(strict=True, reason=BUG_1863)
def test_hts_u_23__sending_the_unchanged_title_still_counts_as_a_text_change(
    db, w1, mgr, mk_ticket
):
    """HTS-U-23 — sending the unchanged title still counts as a text change.
    Rules: `update_ticket` R3a [BUG-1863]"""
    t = mk_ticket("HELP-2026-001")
    commit_point(db)
    t_id = t.id
    before = snap(db, t_id)

    # Then 1
    with pytest.raises(HelpTicketForbiddenError) as exc, close_clock():
        svc.update_ticket(
            db,
            workspace_id=w1.id,
            ticket_id=t_id,
            user=mgr,
            role=GTM_R,
            payload=HelpTicketUpdate(title="Printer jam"),
        )
    # Then 2
    assert str(exc.value) == FORBID
    # Then 3
    assert snap(db, t_id) == before


# [claude] HTS-U-24
@pytest.mark.xfail(strict=True, reason=BUG_1863)
def test_hts_u_24__a_ticket_whose_creator_is_gone_has_its_text_changed_by_nobody(
    db, w1, w2, own, mk_ticket
):
    """HTS-U-24 — a ticket whose creator is gone has its text changed by nobody.
    Rules: `update_ticket` R3a [BUG-1863]"""
    t = mk_ticket("HELP-2026-001", created_by=None)
    commit_point(db)
    t_id, w1_id, w2_id = t.id, w1.id, w2.id
    before = snap(db, t_id)
    before_counts = counts(db, w1_id, w2_id)

    # Then 1
    with pytest.raises(HelpTicketForbiddenError) as exc, close_clock():
        svc.update_ticket(
            db,
            workspace_id=w1_id,
            ticket_id=t_id,
            user=own,
            role=OWNER_R,
            payload=HelpTicketUpdate(title="Work order missing"),
        )
    # Then 2
    assert str(exc.value) == FORBID
    # Then 3
    assert snap(db, t_id) == before
    # Then 4
    assert counts(db, w1_id, w2_id) == before_counts


# [claude] HTS-U-25
@pytest.mark.xfail(strict=True, reason=BUG_1863)
def test_hts_u_25__a_refused_text_change_rolls_back_other_pending_changes_of_the_session(
    db,
    w1,
    mgr,
    mk_ticket,
    mk_extra,
):
    """HTS-U-25 — a refused text change rolls back other pending changes of the session.
    Rules: `update_ticket` R3a [BUG-1863], TC3"""
    t = mk_ticket("HELP-2026-001")
    commit_point(db)
    t_id = t.id
    before = snap(db, t_id)
    x_id = mk_extra()

    # Then 1
    with pytest.raises(HelpTicketForbiddenError), close_clock():
        svc.update_ticket(
            db,
            workspace_id=w1.id,
            ticket_id=t_id,
            user=mgr,
            role=GTM_R,
            payload=HelpTicketUpdate(title="Work order missing"),
        )
    # Then 2
    assert x_gone(db, x_id)
    # Then 3
    assert snap(db, t_id) == before
    # Then 4
    assert db.execute(text("SELECT 1")).scalar() == 1


# [claude] HTS-U-26
@pytest.mark.xfail(strict=True, reason=BUG_1574)
def test_hts_u_26__a_sent_title_description_and_category_are_stored_trimmed(
    db, w1, cr, mk_ticket
):
    """HTS-U-26 — a sent title, description and category are stored trimmed.
    Rules: `update_ticket` R4 [BUG-1574]"""
    t = mk_ticket("HELP-2026-001")
    commit_point(db)
    t_id = t.id
    with close_clock():
        result = svc.update_ticket(
            db,
            workspace_id=w1.id,
            ticket_id=t_id,
            user=cr,
            role=GT_R,
            payload=HelpTicketUpdate(
                title="  Toner low  ", description="  Grey  ", category=" supplies "
            ),
        )

    # Then 1
    assert result.id == t_id
    # Then 2
    assert reread(db, t_id).title == "Toner low"
    # Then 3
    assert reread(db, t_id).description == "Grey"
    # Then 4
    assert reread(db, t_id).category == "supplies"


# [claude] HTS-U-27
@pytest.mark.xfail(strict=True, reason=BUG_1574)
def test_hts_u_27__a_whitespace_only_title_is_refused_by_the_update_schema():
    """HTS-U-27 — a whitespace-only title is refused by the update schema.
    Rules: `update_ticket` R4 [BUG-1574]"""
    # Then 1
    with pytest.raises(PydanticValidationError):
        HelpTicketUpdate(title="   ")


# [claude] HTS-U-28
@pytest.mark.xfail(strict=True, reason=BUG_1574)
def test_hts_u_28__a_whitespace_only_description_is_refused_by_the_update_schema():
    """HTS-U-28 — a whitespace-only description is refused by the update schema.
    Rules: `update_ticket` R4 [BUG-1574]"""
    # Then 1
    with pytest.raises(PydanticValidationError):
        HelpTicketUpdate(description="   ")


# [claude] HTS-U-29
@pytest.mark.xfail(strict=True, reason=BUG_1574)
def test_hts_u_29__a_whitespace_only_category_is_stored_as_none(db, w1, cr, mk_ticket):
    """HTS-U-29 — a whitespace-only category is stored as None.
    Rules: `update_ticket` R4 [BUG-1574]"""
    t = mk_ticket("HELP-2026-001")
    commit_point(db)
    t_id = t.id
    with close_clock():
        result = svc.update_ticket(
            db,
            workspace_id=w1.id,
            ticket_id=t_id,
            user=cr,
            role=GT_R,
            payload=HelpTicketUpdate(category="   "),
        )

    # Then 1
    assert result.id == t_id
    # Then 2
    assert reread(db, t_id).category is None


# [claude] HTS-U-30
@pytest.mark.xfail(strict=True, reason=BUG_1575)
def test_hts_u_30__title_null_is_refused_by_the_update_schema():
    """HTS-U-30 — title null is refused by the update schema.
    Rules: `update_ticket` R4a [BUG-1575]"""
    # Then 1
    with pytest.raises(PydanticValidationError):
        HelpTicketUpdate(title=None)


# [claude] HTS-U-31
@pytest.mark.xfail(strict=True, reason=BUG_1575)
def test_hts_u_31__description_null_is_refused_by_the_update_schema():
    """HTS-U-31 — description null is refused by the update schema.
    Rules: `update_ticket` R4a [BUG-1575]"""
    # Then 1
    with pytest.raises(PydanticValidationError):
        HelpTicketUpdate(description=None)


# [claude] HTS-U-32
def test_hts_u_32__category_null_from_the_creator_clears_the_category(
    db, w1, cr, mk_ticket
):
    """HTS-U-32 — category null from the creator clears the category.
    Rules: `update_ticket` R4a, R3"""
    t = mk_ticket("HELP-2026-001")
    commit_point(db)
    t_id = t.id
    with close_clock():
        result = svc.update_ticket(
            db,
            workspace_id=w1.id,
            ticket_id=t_id,
            user=cr,
            role=GT_R,
            payload=HelpTicketUpdate(category=None),
        )

    # Then 1
    assert result.category is None
    # Then 2
    db.rollback()
    row = committed(db, t_id)
    assert row.category is None
    assert row.title == "Printer jam"


# [claude] HTS-U-33
def test_hts_u_33__a_failing_commit_rolls_back_and_nothing_is_saved(
    db, w1, mgr, mk_ticket
):
    """HTS-U-33 — a failing commit rolls back and nothing is saved.
    Rules: `update_ticket` R7, TC4"""
    t = mk_ticket("HELP-2026-001")
    commit_point(db)
    t_id = t.id
    before = snap(db, t_id)
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb, close_clock():
            svc.update_ticket(
                db,
                workspace_id=w1.id,
                ticket_id=t_id,
                user=mgr,
                role=GTM_R,
                payload=HelpTicketUpdate(status="closed"),
            )

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert snap(db, t_id) == before


# [claude] HTS-U-34
def test_hts_u_34__a_failing_reread_after_the_commit_leaves_the_change_saved(
    db, w1, mgr, mk_ticket
):
    """HTS-U-34 — a failing re-read after the commit leaves the change saved.
    Rules: `update_ticket` R7, TC5"""
    t = mk_ticket("HELP-2026-001")
    commit_point(db)
    t_id, mgr_id = t.id, mgr.id
    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db), close_clock():
            svc.update_ticket(
                db,
                workspace_id=w1.id,
                ticket_id=t_id,
                user=mgr,
                role=GTM_R,
                payload=HelpTicketUpdate(status="closed"),
            )

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    db.rollback()
    row = committed(db, t_id)
    assert row.status == "closed"
    assert row.closed_by == mgr_id


# --------------------------------------------------------------------------- #
# HelpTicketService.list_platform_tickets
# --------------------------------------------------------------------------- #


# [claude] HTS-P-01
def test_hts_p_01__tickets_of_every_workspace_each_with_its_workspaces_and_creators_name(
    db,
    w2,
    mgr,
    tag,
    mk_ticket,
):
    """HTS-P-01 — tickets of every workspace, each with its workspace's and creator's name.
    Rules: `list_platform_tickets` R1"""
    t1 = mk_ticket("HELP-2026-001")
    t2 = mk_ticket("HELP-2026-001", workspace_id=w2.id, created_by=mgr.id)
    own = {t1.id, t2.id}
    result = svc.list_platform_tickets(db, search=tag, limit=1000)

    # Then 1
    assert all(isinstance(t, PlatformHelpTicketListItem) for t in result)
    # Then 2
    assert own_ids(result, own) == {t1.id, t2.id}
    # Then 3
    assert {
        t.id: (t.workspace_name, t.creator_name) for t in result if t.id in own
    } == {
        t1.id: (f"Gamma {tag}", "Rahim"),
        t2.id: (f"Delta {tag}", "Karim"),
    }


# [claude] HTS-P-02
def test_hts_p_02__each_entry_carries_the_tickets_own_fields(
    db, w2, cr, tag, mk_ticket
):
    """HTS-P-02 — each entry carries the ticket's own fields.
    Rules: `list_platform_tickets` R1"""
    t1 = mk_ticket("HELP-2026-001", workspace_id=w2.id)
    result = svc.list_platform_tickets(db, search=tag, limit=1000)

    # Then 1
    assert [t.id for t in result if t.id == t1.id] == [t1.id]
    # Then 2
    e = next(t for t in result if t.id == t1.id)
    assert e.ticket_number == "HELP-2026-001"
    assert e.workspace_id == w2.id
    assert e.title == "Printer jam"
    assert e.status == OPEN
    assert e.created_by == cr.id


# [claude] HTS-P-03
def test_hts_p_03__a_ticket_without_a_creator_has_creator_name_none(db, tag, mk_ticket):
    """HTS-P-03 — a ticket without a creator has creator_name None.
    Rules: `list_platform_tickets` R1"""
    t1 = mk_ticket("HELP-2026-001", created_by=None)
    result = svc.list_platform_tickets(db, search=tag, limit=1000)

    # Then 1
    assert {t.id: t.creator_name for t in result if t.id == t1.id} == {t1.id: None}


# [claude] HTS-P-04
def test_hts_p_04__status_closed_keeps_only_closed_tickets(
    db, w2, tag, mk_ticket, mk_closed
):
    """HTS-P-04 — status closed keeps only closed tickets.
    Rules: `list_platform_tickets` R1"""
    t1 = mk_ticket("HELP-2026-001")
    t2 = mk_closed("HELP-2026-001", workspace_id=w2.id)
    own = {t1.id, t2.id}
    result = svc.list_platform_tickets(db, status=CLOSED, search=tag, limit=1000)

    # Then 1
    assert own_ids(result, own) == {t2.id}


# [claude] HTS-P-05
@pytest.mark.xfail(strict=True, reason=BUG_1443)
def test_hts_p_05__underscore_in_the_search_matches_only_a_literal_underscore_pass_through(
    db, tag, mk_ticket
):
    """HTS-P-05 — `_` in the search matches only a literal `_` (pass-through).
    Rules: `list_platform_tickets` R1 (DAO `list_platform` R6 [BUG-1443])"""
    t1 = mk_ticket("HELP-2026-001", title=f"a_b {tag}")
    t2 = mk_ticket("HELP-2026-002", title=f"plain {tag}")
    own = {t1.id, t2.id}
    result = svc.list_platform_tickets(db, search="_", limit=100000)

    # Then 1
    assert own_ids(result, own) == {t1.id}


# [claude] HTS-P-06
def test_hts_p_06__the_platform_list_neither_commits_nor_rolls_back(
    db, tag, mk_ticket, mk_pending
):
    """HTS-P-06 — the platform list neither commits nor rolls back.
    Rules: `list_platform_tickets` R2, TC6"""
    t1 = mk_ticket("HELP-2026-001")
    commit_point(db)
    p = mk_pending()
    with spies(db) as (cm, rb):
        result = svc.list_platform_tickets(db, search=tag, limit=1000)

    # Then 1
    assert t1.id in {t.id for t in result}
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert db.get(HelpTicket, p.id) is not None


# [claude] HTS-P-07
def test_hts_p_07__a_negative_skip_raises_dataerror_when_called_directly(db, mk_ticket):
    """HTS-P-07 — a negative skip raises DataError when called directly.
    Rules: `list_platform_tickets` Errors"""
    mk_ticket("HELP-2026-001")

    # Then 1
    with pytest.raises(DataError):
        with db.begin_nested():
            svc.list_platform_tickets(db, skip=-1)


# [claude] HTS-P-08
def test_hts_p_08__the_platform_lists_default_limit_is_100(db, tag, mk_ticket):
    """HTS-P-08 — the platform list's default limit is 100.
    Rules: `list_platform_tickets` R1 (paging)"""
    own = {
        mk_ticket(f"HELP-2026-{k:03d}", title=f"T{k} {tag}").id for k in range(1, 102)
    }
    result = svc.list_platform_tickets(db, search=tag)

    # Then 1
    assert len(own_ids(result, own)) == 100


# --------------------------------------------------------------------------- #
# HelpTicketService.get_platform_ticket
# --------------------------------------------------------------------------- #


# [claude] HTS-Q-01
def test_hts_q_01__a_ticket_of_any_workspace_is_returned_with_its_names_not_a_neighbour(
    db, w2, tag, mk_ticket
):
    """HTS-Q-01 — a ticket of any workspace is returned with its names, not a neighbour.
    Rules: `get_platform_ticket` R1"""
    mk_ticket("HELP-2026-001", title="Other")
    t = mk_ticket("HELP-2026-001", workspace_id=w2.id)
    mk_ticket("HELP-2026-002", title="Third")
    result = svc.get_platform_ticket(db, ticket_id=t.id)

    # Then 1
    assert isinstance(result, PlatformHelpTicketListItem)
    # Then 2
    assert result.id == t.id
    assert result.workspace_id == w2.id
    assert result.title == "Printer jam"
    # Then 3
    assert result.workspace_name == f"Delta {tag}"
    assert result.creator_name == "Rahim"


# [claude] HTS-Q-02
def test_hts_q_02__an_unknown_id_is_not_found(db, mk_ticket):
    """HTS-Q-02 — an unknown id is not found.
    Rules: `get_platform_ticket` R2"""
    mk_ticket("HELP-2026-001")

    # Then 1
    with pytest.raises(HelpTicketNotFoundError) as exc:
        svc.get_platform_ticket(db, ticket_id=MISSING)
    # Then 2
    assert str(exc.value) == NOTFOUND


# [claude] HTS-Q-03
def test_hts_q_03__id_0_is_not_found(db, mk_ticket):
    """HTS-Q-03 — id 0 is not found.
    Rules: `get_platform_ticket` R2"""
    mk_ticket("HELP-2026-001")

    # Then 1
    with pytest.raises(HelpTicketNotFoundError) as exc:
        svc.get_platform_ticket(db, ticket_id=0)
    # Then 2
    assert str(exc.value) == NOTFOUND


# [claude] HTS-Q-04
def test_hts_q_04__the_platform_get_neither_commits_nor_rolls_back(
    db, mk_ticket, mk_pending
):
    """HTS-Q-04 — the platform get neither commits nor rolls back.
    Rules: `get_platform_ticket` R2 (read only)"""
    t = mk_ticket("HELP-2026-001")
    commit_point(db)
    p = mk_pending()
    with spies(db) as (cm, rb):
        result = svc.get_platform_ticket(db, ticket_id=t.id)

    # Then 1
    assert result.id == t.id
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert db.get(HelpTicket, p.id) is not None
