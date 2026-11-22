"""Unit tests for app/managers/help_ticket_manager.py.

Implements tests/unit/managers/help_ticket_manager.cases.md (revision 1), one
test per case, in card order. Real Postgres session (`db` fixture); the manager
never commits, so the fixture's outer rollback discards everything. Patched, as
Conventions name them: the DAO clock (C cards), the manager's close clock (U
cards except U-17), and the commit / rollback spies (both still call the real
method). Nothing else is mocked.

Normal mode: every test is written from its card and carries a `# [claude] <ID>`
comment. Row names of the cards are the lower-case names here (T -> t, `W1.id`
-> `w1.id`, `HM` -> `HM`); `# Then N` marks the checks of the card's Then line N.
"""

# ruff: noqa: SIM117, DTZ001  (Conventions prescribe the nested `with` and naive datetimes)
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import event, func, select, text
from sqlalchemy.exc import DataError, IntegrityError

from app.managers.help_ticket_manager import (
    TICKET_VIEW_ALL_ROLES,
    HelpTicketForbiddenError,
    HelpTicketManager,
    HelpTicketNotFoundError,
    help_ticket_manager,
)
from app.models.enums import HelpTicketStatusEnum, RoleEnum
from app.models.help_ticket import HelpTicket
from app.schemas.help_ticket import (
    HelpTicketCreate,
    HelpTicketResponse,
    HelpTicketUpdate,
    PlatformHelpTicketListItem,
)
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "HM"
HM = help_ticket_manager

OWNER_R = RoleEnum("owner")
GTM_R = RoleEnum("ground-team-manager")
GT_R = RoleEnum("ground-team")
FIN_R = RoleEnum("finance")
OPEN = HelpTicketStatusEnum("open")
CLOSED = HelpTicketStatusEnum("closed")

MISSING = 999999999
PAST = datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc)
CLOSE_AT = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
FORBID = "You do not have access to this help ticket."
NOTFOUND = "Help ticket not found."

# The fixed moment of "clock"
FIXED = datetime(2026, 6, 1, 12, 0)

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
def w0(db, tag):
    return make_workspace(db, name=f"Alpha {tag}")


@pytest.fixture
def w1(db, w0, tag):
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


# Convention "pending P": added, never flushed
@pytest.fixture
def mk_pending(db, w2, fin, tag):
    def _mk():
        p = HelpTicket(
            workspace_id=w2.id,
            ticket_number=f"HELP-P-{tag}",
            title="Pending",
            description="Pending",
            created_by=fin.id,
        )
        db.add(p)
        return p

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


# Convention "clock" (every C card)
@contextmanager
def clock():
    with (
        patch("app.dao.help_ticket.datetime", _fixed_datetime(FIXED)),
        patch("app.dao.help_ticket.utcnow", create=True, return_value=FIXED),
        patch("app.utils.time.utcnow", return_value=FIXED),
    ):
        yield


# Convention "close clock" (every U card except U-17)
@contextmanager
def close_clock():
    with patch("app.managers.help_ticket_manager.utcnow", return_value=CLOSE_AT):
        yield


# Convention "spies": both wrap the real method
@contextmanager
def spies(db):
    with (
        patch.object(db, "commit", wraps=db.commit) as cm,
        patch.object(db, "rollback", wraps=db.rollback) as rb,
    ):
        yield cm, rb


# Convention "sql_log": statements sent on the session's connection
@contextmanager
def record_sql(db):
    log = []
    conn = db.connection()

    def _listener(conn_, cursor, statement, parameters, context, executemany):
        log.append(statement)

    event.listen(conn, "before_cursor_execute", _listener)
    try:
        yield log
    finally:
        event.remove(conn, "before_cursor_execute", _listener)


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
    "updated_at",
)


# Convention "snapshot" for unchanged(T): database values, read without touching
# the session's objects (no expire, no refresh)
def snap(db, ticket_id):
    row = db.execute(
        select(*(getattr(HelpTicket, f) for f in _UNCHANGED_FIELDS)).where(
            HelpTicket.id == ticket_id
        )
    ).one()
    return dict(zip(_UNCHANGED_FIELDS, row, strict=True))


# Convention "unchanged(T)": after a re-read
def unchanged(db, ticket_id):
    row = reread(db, ticket_id)
    return {f: getattr(row, f) for f in _UNCHANGED_FIELDS}


# Convention "nothing written": help_tickets rows of W0, W1 and W2
def counts(db, w0_id, w1_id, w2_id):
    return tuple(
        db.scalar(
            select(func.count())
            .select_from(HelpTicket)
            .where(HelpTicket.workspace_id == ws_id)
        )
        for ws_id in (w0_id, w1_id, w2_id)
    )


def w1_count(db, w1_id):
    return db.scalar(
        select(func.count()).select_from(HelpTicket).where(HelpTicket.workspace_id == w1_id)
    )


# Convention "idset(r)"
def idset(result):
    return {t.id for t in result}


# Convention "own(r)"
def own_ids(result, own):
    return {t.id for t in result if t.id in own}


# --------------------------------------------------------------------------- #
# HelpTicketManager.can_view_all_tickets
# --------------------------------------------------------------------------- #


# [claude] HTM-VA-01
def test_htm_va_01__owner_sees_all():
    """HTM-VA-01 — "owner" sees all.
    Rules: `can_view_all_tickets` R1"""
    result = HelpTicketManager.can_view_all_tickets("owner")
    # Then 1
    assert result is True


# [claude] HTM-VA-02
def test_htm_va_02__ground_team_manager_sees_all():
    """HTM-VA-02 — "ground-team-manager" sees all.
    Rules: `can_view_all_tickets` R1"""
    result = HelpTicketManager.can_view_all_tickets("ground-team-manager")
    # Then 1
    assert result is True


# [claude] HTM-VA-03
def test_htm_va_03__the_roleenum_owner_member_sees_all():
    """HTM-VA-03 — the RoleEnum owner member sees all.
    Rules: `can_view_all_tickets` R1"""
    result = HelpTicketManager.can_view_all_tickets(OWNER_R)
    # Then 1
    assert result is True


# [claude] HTM-VA-04
def test_htm_va_04__the_roleenum_ground_team_manager_member_sees_all():
    """HTM-VA-04 — the RoleEnum ground-team-manager member sees all.
    Rules: `can_view_all_tickets` R1"""
    result = HelpTicketManager.can_view_all_tickets(GTM_R)
    # Then 1
    assert result is True


# [claude] HTM-VA-05
def test_htm_va_05__finance_does_not():
    """HTM-VA-05 — "finance" does not.
    Rules: `can_view_all_tickets` R1"""
    result = HelpTicketManager.can_view_all_tickets("finance")
    # Then 1
    assert result is False


# [claude] HTM-VA-06
def test_htm_va_06__ground_team_does_not():
    """HTM-VA-06 — "ground-team" does not.
    Rules: `can_view_all_tickets` R1"""
    result = HelpTicketManager.can_view_all_tickets(GT_R)
    # Then 1
    assert result is False


# [claude] HTM-VA-07
def test_htm_va_07__none_does_not():
    """HTM-VA-07 — None does not.
    Rules: `can_view_all_tickets` R1"""
    result = HelpTicketManager.can_view_all_tickets(None)
    # Then 1
    assert result is False


# [claude] HTM-VA-08
def test_htm_va_08__the_empty_string_does_not():
    """HTM-VA-08 — the empty string does not.
    Rules: `can_view_all_tickets` R1"""
    result = HelpTicketManager.can_view_all_tickets("")
    # Then 1
    assert result is False


# [claude] HTM-VA-09
def test_htm_va_09__owner_with_a_capital_does_not():
    """HTM-VA-09 — "Owner" with a capital does not.
    Rules: `can_view_all_tickets` R1"""
    result = HelpTicketManager.can_view_all_tickets("Owner")
    # Then 1
    assert result is False


# [claude] HTM-VA-10
def test_htm_va_10__owner_with_a_leading_space_does_not():
    """HTM-VA-10 — " owner" with a leading space does not.
    Rules: `can_view_all_tickets` R1"""
    result = HelpTicketManager.can_view_all_tickets(" owner")
    # Then 1
    assert result is False


# [claude] HTM-VA-11
def test_htm_va_11__manager_a_part_of_the_role_does_not():
    """HTM-VA-11 — "manager", a part of the role, does not.
    Rules: `can_view_all_tickets` R1"""
    result = HelpTicketManager.can_view_all_tickets("manager")
    # Then 1
    assert result is False


# [claude] HTM-VA-12
def test_htm_va_12__ground_team_manager_with_underscores_does_not():
    """HTM-VA-12 — "ground_team_manager" with underscores does not.
    Rules: `can_view_all_tickets` R1"""
    result = HelpTicketManager.can_view_all_tickets("ground_team_manager")
    # Then 1
    assert result is False


# [claude] HTM-VA-13
def test_htm_va_13__own_the_start_of_a_role_does_not():
    """HTM-VA-13 — "own", the start of a role, does not.
    Rules: `can_view_all_tickets` R1"""
    result = HelpTicketManager.can_view_all_tickets("own")
    # Then 1
    assert result is False


# [claude] HTM-VA-14
def test_htm_va_14__the_view_all_set_holds_exactly_the_two_roles():
    """HTM-VA-14 — the view-all set holds exactly the two roles.
    Rules: `can_view_all_tickets` R1 (Facts: `TICKET_VIEW_ALL_ROLES`)"""
    result = set(TICKET_VIEW_ALL_ROLES)
    # Then 1
    assert result == {"owner", "ground-team-manager"}


# --------------------------------------------------------------------------- #
# HelpTicketManager.can_access_ticket
# --------------------------------------------------------------------------- #


# [claude] HTM-AC-01
def test_htm_ac_01__a_platform_admin_without_a_role_may_open_a_members_ticket(mk_ticket, adm):
    """HTM-AC-01 — a platform admin without a role may open a member's ticket.
    Rules: `can_access_ticket` R1"""
    t = mk_ticket("HELP-2026-001")
    result = HelpTicketManager.can_access_ticket(ticket=t, user=adm, role=None)
    # Then 1
    assert result is True


# [claude] HTM-AC-02
def test_htm_ac_02__a_platform_admin_with_a_plain_role_may_open_a_ticket_whose_creator_is_gone(
    mk_ticket, adm
):
    """HTM-AC-02 — a platform admin with a plain role may open a ticket whose creator is gone.
    Rules: `can_access_ticket` R1"""
    t = mk_ticket("HELP-2026-001", created_by=None)
    result = HelpTicketManager.can_access_ticket(ticket=t, user=adm, role=GT_R)
    # Then 1
    assert result is True


# [claude] HTM-AC-03
def test_htm_ac_03__an_owner_higher_id_may_open_a_members_ticket(mk_ticket, own):
    """HTM-AC-03 — an owner (higher id than the creator) may open a member's ticket.
    Rules: `can_access_ticket` R2"""
    t = mk_ticket("HELP-2026-001")
    result = HelpTicketManager.can_access_ticket(ticket=t, user=own, role=OWNER_R)
    # Then 1
    assert result is True


# [claude] HTM-AC-04
def test_htm_ac_04__a_ground_team_manager_lower_id_may_open_a_members_ticket(mk_ticket, mgr):
    """HTM-AC-04 — a ground-team-manager (lower id than the creator) may open a member's ticket.
    Rules: `can_access_ticket` R2"""
    t = mk_ticket("HELP-2026-001")
    result = HelpTicketManager.can_access_ticket(ticket=t, user=mgr, role=GTM_R)
    # Then 1
    assert result is True


# [claude] HTM-AC-05
def test_htm_ac_05__the_role_as_a_plain_string_owner_counts(mk_ticket, fin):
    """HTM-AC-05 — the role as a plain string "owner" counts.
    Rules: `can_access_ticket` R2"""
    t = mk_ticket("HELP-2026-001")
    result = HelpTicketManager.can_access_ticket(ticket=t, user=fin, role="owner")
    # Then 1
    assert result is True


# [claude] HTM-AC-06
def test_htm_ac_06__an_owner_may_open_a_ticket_whose_creator_is_gone(mk_ticket, own):
    """HTM-AC-06 — an owner may open a ticket whose creator is gone.
    Rules: `can_access_ticket` R2, R3"""
    t = mk_ticket("HELP-2026-001", created_by=None)
    result = HelpTicketManager.can_access_ticket(ticket=t, user=own, role=OWNER_R)
    # Then 1
    assert result is True


# [claude] HTM-AC-07
def test_htm_ac_07__the_creator_with_no_role_may_open_their_ticket(mk_ticket, cr):
    """HTM-AC-07 — the creator with no role may open their ticket.
    Rules: `can_access_ticket` R3"""
    t = mk_ticket("HELP-2026-001")
    result = HelpTicketManager.can_access_ticket(ticket=t, user=cr, role=None)
    # Then 1
    assert result is True


# [claude] HTM-AC-08
def test_htm_ac_08__the_creator_as_a_ground_team_member_may_open_their_ticket(mk_ticket, cr):
    """HTM-AC-08 — the creator as a ground-team member may open their ticket.
    Rules: `can_access_ticket` R3"""
    t = mk_ticket("HELP-2026-001")
    result = HelpTicketManager.can_access_ticket(ticket=t, user=cr, role=GT_R)
    # Then 1
    assert result is True


# [claude] HTM-AC-09
def test_htm_ac_09__a_ground_team_member_with_a_lower_id_may_not(mk_ticket, mgr):
    """HTM-AC-09 — a ground-team member with a lower id than the creator may not.
    Rules: `can_access_ticket` R3"""
    t = mk_ticket("HELP-2026-001")
    result = HelpTicketManager.can_access_ticket(ticket=t, user=mgr, role=GT_R)
    # Then 1
    assert result is False


# [claude] HTM-AC-10
def test_htm_ac_10__a_finance_member_with_a_higher_id_may_not(mk_ticket, fin):
    """HTM-AC-10 — a finance member with a higher id than the creator may not.
    Rules: `can_access_ticket` R3"""
    t = mk_ticket("HELP-2026-001")
    result = HelpTicketManager.can_access_ticket(ticket=t, user=fin, role=FIN_R)
    # Then 1
    assert result is False


# [claude] HTM-AC-11
def test_htm_ac_11__no_role_and_not_an_admin_may_not(mk_ticket, own):
    """HTM-AC-11 — no role and not an admin may not.
    Rules: `can_access_ticket` R1, R2, R3"""
    t = mk_ticket("HELP-2026-001")
    result = HelpTicketManager.can_access_ticket(ticket=t, user=own, role=None)
    # Then 1
    assert result is False


# [claude] HTM-AC-12
def test_htm_ac_12__a_ticket_whose_creator_is_gone_is_closed_to_a_plain_member(mk_ticket, fin):
    """HTM-AC-12 — a ticket whose creator is gone is closed to a plain member.
    Rules: `can_access_ticket` R3"""
    t = mk_ticket("HELP-2026-001", created_by=None)
    result = HelpTicketManager.can_access_ticket(ticket=t, user=fin, role=FIN_R)
    # Then 1
    assert result is False


# [claude] HTM-AC-13
def test_htm_ac_13__a_user_object_without_is_platform_admin_counts_as_not_an_admin(
    mk_ticket, fin
):
    """HTM-AC-13 — a user object without is_platform_admin counts as not an admin.
    Rules: `can_access_ticket` R1"""
    t = mk_ticket("HELP-2026-001")
    result = HelpTicketManager.can_access_ticket(
        ticket=t, user=SimpleNamespace(id=fin.id), role=None
    )
    # Then 1
    assert result is False


# [claude] HTM-AC-14
def test_htm_ac_14__a_user_object_without_is_platform_admin_is_still_let_in_as_the_creator(
    mk_ticket, cr
):
    """HTM-AC-14 — a user object without is_platform_admin is still let in as the creator.
    Rules: `can_access_ticket` R1, R3"""
    t = mk_ticket("HELP-2026-001")
    result = HelpTicketManager.can_access_ticket(
        ticket=t, user=SimpleNamespace(id=cr.id), role=None
    )
    # Then 1
    assert result is True


# [claude] HTM-AC-15
def test_htm_ac_15__is_platform_admin_false_with_a_view_all_role_still_counts_by_role(
    mk_ticket, fin
):
    """HTM-AC-15 — is_platform_admin False with a view-all role still counts by role.
    Rules: `can_access_ticket` R1, R2"""
    t = mk_ticket("HELP-2026-001")
    result = HelpTicketManager.can_access_ticket(
        ticket=t, user=SimpleNamespace(id=fin.id, is_platform_admin=False), role=GTM_R
    )
    # Then 1
    assert result is True


# [claude] HTM-AC-16
def test_htm_ac_16__owner_with_a_capital_is_not_a_view_all_role(mk_ticket, fin):
    """HTM-AC-16 — "Owner" with a capital is not a view-all role.
    Rules: `can_access_ticket` R2"""
    t = mk_ticket("HELP-2026-001")
    result = HelpTicketManager.can_access_ticket(ticket=t, user=fin, role="Owner")
    # Then 1
    assert result is False


# [claude] HTM-AC-17
def test_htm_ac_17__the_creator_of_a_different_ticket_may_not_open_this_one(mk_ticket, fin):
    """HTM-AC-17 — the creator of a different ticket may not open this one.
    Rules: `can_access_ticket` R3"""
    mk_ticket("HELP-2026-001", created_by=fin.id)
    t = mk_ticket("HELP-2026-002")
    mk_ticket("HELP-2026-003", created_by=fin.id)
    result = HelpTicketManager.can_access_ticket(ticket=t, user=fin, role=GT_R)
    # Then 1
    assert result is False


# [claude] HTM-AC-18
def test_htm_ac_18__the_check_runs_no_query(db, mk_ticket, cr):
    """HTM-AC-18 — the check runs no query.
    Rules: `can_access_ticket` Persistence (pure)"""
    t = mk_ticket("HELP-2026-001")
    with record_sql(db) as sql_log:
        result = HelpTicketManager.can_access_ticket(ticket=t, user=cr, role=GT_R)
    # Then 1
    assert result is True
    # Then 2
    assert sql_log == []


# [claude] HTM-AC-19
def test_htm_ac_19__the_tickets_workspace_is_not_looked_at(mk_ticket, w2, own):
    """HTM-AC-19 — the ticket's workspace is not looked at.
    Rules: `can_access_ticket` R4"""
    tz = mk_ticket("HELP-2026-001", workspace_id=w2.id)
    result = HelpTicketManager.can_access_ticket(ticket=tz, user=own, role=OWNER_R)
    # Then 1
    assert result is True


# --------------------------------------------------------------------------- #
# HelpTicketManager.get_by_id_and_workspace
# --------------------------------------------------------------------------- #


# [claude] HTM-G-01
def test_htm_g_01__the_creator_gets_their_ticket_not_a_neighbour_with_its_creator(
    db, mk_ticket, w1, cr
):
    """HTM-G-01 — the creator gets their ticket, not a neighbour, with its creator.
    Rules: `get_by_id_and_workspace` R1, R3"""
    mk_ticket("HELP-2026-001", title="Other")
    t = mk_ticket("HELP-2026-002")
    mk_ticket("HELP-2026-003", title="Third")
    result = HM.get_by_id_and_workspace(
        db, ticket_id=t.id, workspace_id=w1.id, user=cr, role=GT_R
    )
    # Then 1
    assert result is t
    # Then 2
    assert result.title == "Printer jam"
    assert result.ticket_number == "HELP-2026-002"
    # Then 3
    assert result.creator.name == "Rahim"


# [claude] HTM-G-02
def test_htm_g_02__an_owner_higher_id_gets_a_members_ticket(db, mk_ticket, w1, own):
    """HTM-G-02 — an owner (higher id than the creator) gets a member's ticket.
    Rules: `get_by_id_and_workspace` R3"""
    t = mk_ticket("HELP-2026-001")
    result = HM.get_by_id_and_workspace(
        db, ticket_id=t.id, workspace_id=w1.id, user=own, role=OWNER_R
    )
    # Then 1
    assert result is t


# [claude] HTM-G-03
def test_htm_g_03__a_ground_team_manager_lower_id_gets_a_members_ticket(db, mk_ticket, w1, mgr):
    """HTM-G-03 — a ground-team-manager (lower id than the creator) gets a member's ticket.
    Rules: `get_by_id_and_workspace` R3"""
    t = mk_ticket("HELP-2026-001")
    result = HM.get_by_id_and_workspace(
        db, ticket_id=t.id, workspace_id=w1.id, user=mgr, role=GTM_R
    )
    # Then 1
    assert result is t


# [claude] HTM-G-04
def test_htm_g_04__a_platform_admin_without_a_role_gets_a_members_ticket(db, mk_ticket, w1, adm):
    """HTM-G-04 — a platform admin without a role gets a member's ticket.
    Rules: `get_by_id_and_workspace` R3"""
    t = mk_ticket("HELP-2026-001")
    result = HM.get_by_id_and_workspace(
        db, ticket_id=t.id, workspace_id=w1.id, user=adm, role=None
    )
    # Then 1
    assert result is t


# [claude] HTM-G-05
def test_htm_g_05__an_owner_gets_a_ticket_whose_creator_is_gone_creator_none(
    db, mk_ticket, w1, own
):
    """HTM-G-05 — an owner gets a ticket whose creator is gone, creator None.
    Rules: `get_by_id_and_workspace` R3"""
    t = mk_ticket("HELP-2026-001", created_by=None)
    result = HM.get_by_id_and_workspace(
        db, ticket_id=t.id, workspace_id=w1.id, user=own, role=OWNER_R
    )
    # Then 1
    assert result is t
    # Then 2
    assert result.creator is None


# [claude] HTM-G-06
def test_htm_g_06__a_ground_team_member_with_a_lower_id_is_refused(db, mk_ticket, w1, mgr):
    """HTM-G-06 — a ground-team member with a lower id than the creator is refused.
    Rules: `get_by_id_and_workspace` R2, Errors row 2"""
    t = mk_ticket("HELP-2026-001")
    # Then 1
    with pytest.raises(HelpTicketForbiddenError) as exc:
        HM.get_by_id_and_workspace(db, ticket_id=t.id, workspace_id=w1.id, user=mgr, role=GT_R)
    # Then 2
    assert type(exc.value) is HelpTicketForbiddenError
    # Then 3
    assert str(exc.value) == FORBID
    # Then 4
    assert isinstance(exc.value, PermissionError)


# [claude] HTM-G-07
def test_htm_g_07__a_finance_member_with_a_higher_id_is_refused(db, mk_ticket, w1, fin):
    """HTM-G-07 — a finance member with a higher id than the creator is refused.
    Rules: `get_by_id_and_workspace` R2"""
    t = mk_ticket("HELP-2026-001")
    # Then 1
    with pytest.raises(HelpTicketForbiddenError) as exc:
        HM.get_by_id_and_workspace(db, ticket_id=t.id, workspace_id=w1.id, user=fin, role=FIN_R)
    # Then 2
    assert str(exc.value) == FORBID


# [claude] HTM-G-08
def test_htm_g_08__no_role_and_not_an_admin_is_refused(db, mk_ticket, w1, own):
    """HTM-G-08 — no role and not an admin is refused.
    Rules: `get_by_id_and_workspace` R2"""
    t = mk_ticket("HELP-2026-001")
    # Then 1
    with pytest.raises(HelpTicketForbiddenError) as exc:
        HM.get_by_id_and_workspace(db, ticket_id=t.id, workspace_id=w1.id, user=own, role=None)
    # Then 2
    assert str(exc.value) == FORBID


# [claude] HTM-G-09
def test_htm_g_09__a_ticket_whose_creator_is_gone_is_refused_to_a_plain_member(
    db, mk_ticket, w1, fin
):
    """HTM-G-09 — a ticket whose creator is gone is refused to a plain member.
    Rules: `get_by_id_and_workspace` R2"""
    t = mk_ticket("HELP-2026-001", created_by=None)
    # Then 1
    with pytest.raises(HelpTicketForbiddenError) as exc:
        HM.get_by_id_and_workspace(db, ticket_id=t.id, workspace_id=w1.id, user=fin, role=FIN_R)
    # Then 2
    assert str(exc.value) == FORBID


# [claude] HTM-G-10
def test_htm_g_10__a_user_without_is_platform_admin_and_not_the_creator_is_refused(
    db, mk_ticket, w1, own
):
    """HTM-G-10 — a user without is_platform_admin and not the creator is refused.
    Rules: `get_by_id_and_workspace` R2"""
    t = mk_ticket("HELP-2026-001")
    # Then 1
    with pytest.raises(HelpTicketForbiddenError) as exc:
        HM.get_by_id_and_workspace(
            db, ticket_id=t.id, workspace_id=w1.id, user=SimpleNamespace(id=own.id), role=GT_R
        )
    # Then 2
    assert str(exc.value) == FORBID


# [claude] HTM-G-11
def test_htm_g_11__an_unknown_id_is_not_found(db, mk_ticket, w1, own):
    """HTM-G-11 — an unknown id is not found.
    Rules: `get_by_id_and_workspace` R1, Errors row 1"""
    mk_ticket("HELP-2026-001")
    # Then 1
    with pytest.raises(HelpTicketNotFoundError) as exc:
        HM.get_by_id_and_workspace(
            db, ticket_id=MISSING, workspace_id=w1.id, user=own, role=OWNER_R
        )
    # Then 2
    assert type(exc.value) is HelpTicketNotFoundError
    # Then 3
    assert str(exc.value) == NOTFOUND
    # Then 4
    assert isinstance(exc.value, LookupError)


# [claude] HTM-G-12
def test_htm_g_12__id_0_is_not_found(db, mk_ticket, w1, own):
    """HTM-G-12 — id 0 is not found.
    Rules: `get_by_id_and_workspace` R1"""
    mk_ticket("HELP-2026-001")
    # Then 1
    with pytest.raises(HelpTicketNotFoundError) as exc:
        HM.get_by_id_and_workspace(db, ticket_id=0, workspace_id=w1.id, user=own, role=OWNER_R)
    # Then 2
    assert str(exc.value) == NOTFOUND


# [claude] HTM-G-13
def test_htm_g_13__the_later_workspaces_ticket_asked_in_w1_is_not_found_even_by_its_creator(
    db, mk_ticket, w1, w2, cr
):
    """HTM-G-13 — the later workspace's ticket asked in W1 is not found, even by its creator.
    Rules: `get_by_id_and_workspace` R1"""
    tz = mk_ticket("HELP-2026-001", workspace_id=w2.id)
    # Then 1
    with pytest.raises(HelpTicketNotFoundError) as exc:
        HM.get_by_id_and_workspace(db, ticket_id=tz.id, workspace_id=w1.id, user=cr, role=OWNER_R)
    # Then 2
    assert str(exc.value) == NOTFOUND


# [claude] HTM-G-14
def test_htm_g_14__the_earlier_workspaces_ticket_asked_in_w1_is_not_found_even_by_its_creator(
    db, mk_ticket, w0, w1, cr
):
    """HTM-G-14 — the earlier workspace's ticket asked in W1 is not found, even by its creator.
    Rules: `get_by_id_and_workspace` R1"""
    tz = mk_ticket("HELP-2026-001", workspace_id=w0.id)
    # Then 1
    with pytest.raises(HelpTicketNotFoundError) as exc:
        HM.get_by_id_and_workspace(db, ticket_id=tz.id, workspace_id=w1.id, user=cr, role=OWNER_R)
    # Then 2
    assert str(exc.value) == NOTFOUND


# [claude] HTM-G-15
def test_htm_g_15__w1s_ticket_asked_in_the_later_workspace_is_not_found(db, mk_ticket, w2, own):
    """HTM-G-15 — W1's ticket asked in the later workspace is not found.
    Rules: `get_by_id_and_workspace` R1"""
    t = mk_ticket("HELP-2026-001")
    # Then 1
    with pytest.raises(HelpTicketNotFoundError) as exc:
        HM.get_by_id_and_workspace(db, ticket_id=t.id, workspace_id=w2.id, user=own, role=OWNER_R)
    # Then 2
    assert str(exc.value) == NOTFOUND


# [claude] HTM-G-16
def test_htm_g_16__w1s_ticket_asked_in_the_earlier_workspace_is_not_found(db, mk_ticket, w0, own):
    """HTM-G-16 — W1's ticket asked in the earlier workspace is not found.
    Rules: `get_by_id_and_workspace` R1"""
    t = mk_ticket("HELP-2026-001")
    # Then 1
    with pytest.raises(HelpTicketNotFoundError) as exc:
        HM.get_by_id_and_workspace(db, ticket_id=t.id, workspace_id=w0.id, user=own, role=OWNER_R)
    # Then 2
    assert str(exc.value) == NOTFOUND


# [claude] HTM-G-17
def test_htm_g_17__another_workspaces_ticket_gives_not_found_before_any_access_check(
    db, mk_ticket, w1, w2, fin
):
    """HTM-G-17 — another workspace's ticket gives "not found" before any access check.
    Rules: `get_by_id_and_workspace` R1 (order of checks)"""
    tz = mk_ticket("HELP-2026-001", workspace_id=w2.id)
    # Then 1
    with pytest.raises(HelpTicketNotFoundError) as exc:
        HM.get_by_id_and_workspace(db, ticket_id=tz.id, workspace_id=w1.id, user=fin, role=FIN_R)
    # Then 2
    assert type(exc.value) is HelpTicketNotFoundError
    # Then 3
    assert str(exc.value) == NOTFOUND


# [claude] HTM-G-18
def test_htm_g_18__an_admin_asking_for_another_workspaces_ticket_is_not_found(
    db, mk_ticket, w0, w1, adm
):
    """HTM-G-18 — an admin asking for another workspace's ticket is not found.
    Rules: `get_by_id_and_workspace` R1 (HR-16: the workspace methods are scoped)"""
    tz = mk_ticket("HELP-2026-001", workspace_id=w0.id)
    # Then 1
    with pytest.raises(HelpTicketNotFoundError) as exc:
        HM.get_by_id_and_workspace(db, ticket_id=tz.id, workspace_id=w1.id, user=adm, role=None)
    # Then 2
    assert str(exc.value) == NOTFOUND


# [claude] HTM-G-19
def test_htm_g_19__the_creator_of_other_tickets_here_and_elsewhere_is_refused_this_one(
    db, mk_ticket, w0, w1, w2, fin
):
    """HTM-G-19 — the creator of other tickets, here and elsewhere, is refused this one.
    Rules: `get_by_id_and_workspace` R2 (creator grant held on a different record)"""
    mk_ticket("HELP-2026-002", workspace_id=w0.id, created_by=fin.id)
    mk_ticket("HELP-2026-001", created_by=fin.id)
    t = mk_ticket("HELP-2026-002")
    mk_ticket("HELP-2026-003", created_by=fin.id)
    mk_ticket("HELP-2026-002", workspace_id=w2.id, created_by=fin.id)
    # Then 1
    with pytest.raises(HelpTicketForbiddenError) as exc:
        HM.get_by_id_and_workspace(db, ticket_id=t.id, workspace_id=w1.id, user=fin, role=GT_R)
    # Then 2
    assert str(exc.value) == FORBID


# [claude] HTM-G-20
def test_htm_g_20__a_successful_get_writes_nothing_and_keeps_the_callers_pending_row(
    db, mk_ticket, mk_pending, w1, cr
):
    """HTM-G-20 — a successful get writes nothing and keeps the caller's pending row.
    Rules: `get_by_id_and_workspace` Side effects"""
    t = mk_ticket("HELP-2026-001")
    p = mk_pending()
    with spies(db) as (cm, rb):
        result = HM.get_by_id_and_workspace(
            db, ticket_id=t.id, workspace_id=w1.id, user=cr, role=GT_R
        )
    # Then 1
    assert result is t
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert db.is_modified(t) is False
    # Then 5
    assert not db.dirty
    assert not db.deleted
    # Then 6
    assert len(db.new) == 1
    assert p in db.new


# [claude] HTM-G-21
def test_htm_g_21__a_refused_get_neither_rolls_back_nor_drops_the_callers_pending_row(
    db, mk_ticket, mk_pending, w1, fin
):
    """HTM-G-21 — a refused get neither rolls back nor drops the caller's pending row.
    Rules: `get_by_id_and_workspace` R2, Side effects"""
    t = mk_ticket("HELP-2026-001")
    p = mk_pending()
    # Then 1
    with spies(db) as (cm, rb), pytest.raises(HelpTicketForbiddenError):
        HM.get_by_id_and_workspace(db, ticket_id=t.id, workspace_id=w1.id, user=fin, role=FIN_R)
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert len(db.new) == 1
    assert p in db.new


# --------------------------------------------------------------------------- #
# HelpTicketManager.list_tickets
# --------------------------------------------------------------------------- #


# [claude] HTM-L-01
def test_htm_l_01__an_owner_sees_every_ticket_of_w1_none_of_w0_or_w2(
    db, mk_ticket, w0, w1, w2, mgr, own
):
    """HTM-L-01 — an owner sees every ticket of W1, none of W0 or W2.
    Rules: `list_tickets` R1"""
    mk_ticket("HELP-2026-001", workspace_id=w0.id)
    tm = mk_ticket("HELP-2026-001", created_by=mgr.id)
    tc = mk_ticket("HELP-2026-002")
    to = mk_ticket("HELP-2026-003", created_by=own.id)
    tn = mk_ticket("HELP-2026-004", created_by=None)
    mk_ticket("HELP-2026-001", workspace_id=w2.id)
    result = HM.list_tickets(db, workspace_id=w1.id, user=own, role=OWNER_R, limit=1000)
    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert all(isinstance(t, HelpTicket) for t in result)
    # Then 3
    assert idset(result) == {tm.id, tc.id, to.id, tn.id}


# [claude] HTM-L-02
def test_htm_l_02__a_ground_team_manager_sees_every_ticket_of_w1(
    db, mk_ticket, w1, w2, mgr, fin
):
    """HTM-L-02 — a ground-team-manager sees every ticket of W1.
    Rules: `list_tickets` R1"""
    tm = mk_ticket("HELP-2026-001", created_by=mgr.id)
    tc = mk_ticket("HELP-2026-002")
    tf = mk_ticket("HELP-2026-003", created_by=fin.id)
    mk_ticket("HELP-2026-001", workspace_id=w2.id, created_by=mgr.id)
    result = HM.list_tickets(db, workspace_id=w1.id, user=mgr, role=GTM_R, limit=1000)
    # Then 1
    assert idset(result) == {tm.id, tc.id, tf.id}


# [claude] HTM-L-03
def test_htm_l_03__a_ground_team_member_sees_only_their_own(
    db, mk_ticket, w0, w1, w2, mgr, cr, fin
):
    """HTM-L-03 — a ground-team member sees only their own, not lower or higher creators'.
    Rules: `list_tickets` R1"""
    mk_ticket("HELP-2026-001", created_by=mgr.id)
    tc = mk_ticket("HELP-2026-002")
    mk_ticket("HELP-2026-003", created_by=fin.id)
    mk_ticket("HELP-2026-004", created_by=None)
    mk_ticket("HELP-2026-001", workspace_id=w2.id)
    mk_ticket("HELP-2026-001", workspace_id=w0.id)
    result = HM.list_tickets(db, workspace_id=w1.id, user=cr, role=GT_R, limit=1000)
    # Then 1
    assert idset(result) == {tc.id}


# [claude] HTM-L-04
def test_htm_l_04__a_finance_member_sees_only_their_own(db, mk_ticket, w1, fin):
    """HTM-L-04 — a finance member sees only their own.
    Rules: `list_tickets` R1"""
    mk_ticket("HELP-2026-001")
    tf = mk_ticket("HELP-2026-002", created_by=fin.id)
    result = HM.list_tickets(db, workspace_id=w1.id, user=fin, role=FIN_R, limit=1000)
    # Then 1
    assert idset(result) == {tf.id}


# [claude] HTM-L-05
def test_htm_l_05__no_role_and_not_an_admin_sees_only_their_own(db, mk_ticket, w1, own):
    """HTM-L-05 — no role and not an admin sees only their own.
    Rules: `list_tickets` R1"""
    mk_ticket("HELP-2026-001")
    to = mk_ticket("HELP-2026-002", created_by=own.id)
    result = HM.list_tickets(db, workspace_id=w1.id, user=own, role=None, limit=1000)
    # Then 1
    assert idset(result) == {to.id}


# [claude] HTM-L-06
def test_htm_l_06__the_own_tickets_filter_is_applied_before_paging(
    db, mk_ticket, w1, mgr, cr, own, fin
):
    """HTM-L-06 — the own-tickets filter is applied before paging.
    Rules: `list_tickets` R1 (HR-5)"""
    mk_ticket("HELP-2026-001", created_by=mgr.id)
    mk_ticket("HELP-2026-002", created_by=fin.id)
    tc = mk_ticket("HELP-2026-003")
    mk_ticket("HELP-2026-004", created_by=own.id)
    result = HM.list_tickets(db, workspace_id=w1.id, user=cr, role=GT_R, limit=1)
    # Then 1
    assert idset(result) == {tc.id}


# [claude] HTM-L-07
def test_htm_l_07__status_closed_keeps_only_closed_tickets(db, mk_ticket, mk_closed, w1, own):
    """HTM-L-07 — status closed keeps only closed tickets.
    Rules: `list_tickets` R1 (status)"""
    mk_ticket("HELP-2026-001")
    tb = mk_closed("HELP-2026-002")
    result = HM.list_tickets(
        db, workspace_id=w1.id, user=own, role=OWNER_R, status=CLOSED, limit=1000
    )
    # Then 1
    assert idset(result) == {tb.id}


# [claude] HTM-L-08
def test_htm_l_08__status_open_keeps_only_open_tickets(db, mk_ticket, mk_closed, w1, own):
    """HTM-L-08 — status open keeps only open tickets.
    Rules: `list_tickets` R1 (status)"""
    ta = mk_ticket("HELP-2026-001")
    mk_closed("HELP-2026-002")
    result = HM.list_tickets(
        db, workspace_id=w1.id, user=own, role=OWNER_R, status=OPEN, limit=1000
    )
    # Then 1
    assert idset(result) == {ta.id}


# [claude] HTM-L-09
def test_htm_l_09__status_none_keeps_both(db, mk_ticket, mk_closed, w1, own):
    """HTM-L-09 — status None keeps both.
    Rules: `list_tickets` R1 (status)"""
    ta = mk_ticket("HELP-2026-001")
    tb = mk_closed("HELP-2026-002")
    result = HM.list_tickets(
        db, workspace_id=w1.id, user=own, role=OWNER_R, status=None, limit=1000
    )
    # Then 1
    assert idset(result) == {ta.id, tb.id}


# [claude] HTM-L-10
def test_htm_l_10__the_default_limit_is_100(db, mk_ticket, w1, own):
    """HTM-L-10 — the default limit is 100.
    Rules: `list_tickets` R1 (paging default)"""
    for k in range(1, 102):
        mk_ticket(f"HELP-2026-{k:03d}")
    result = HM.list_tickets(db, workspace_id=w1.id, user=own, role=OWNER_R)
    # Then 1
    assert len(result) == 100


# [claude] HTM-L-11
def test_htm_l_11__skip_reaches_the_query(db, mk_ticket, w1, own):
    """HTM-L-11 — skip reaches the query.
    Rules: `list_tickets` R1 (paging)"""
    ta = mk_ticket("HELP-2026-001")
    tb = mk_ticket("HELP-2026-002")
    tc = mk_ticket("HELP-2026-003")
    result = HM.list_tickets(db, workspace_id=w1.id, user=own, role=OWNER_R, skip=1, limit=1000)
    # Then 1
    assert len(result) == 2
    # Then 2
    assert idset(result) < {ta.id, tb.id, tc.id}


# [claude] HTM-L-12
def test_htm_l_12__limit_reaches_the_query(db, mk_ticket, w1, own):
    """HTM-L-12 — limit reaches the query.
    Rules: `list_tickets` R1 (paging)"""
    mk_ticket("HELP-2026-001")
    mk_ticket("HELP-2026-002")
    mk_ticket("HELP-2026-003")
    result = HM.list_tickets(db, workspace_id=w1.id, user=own, role=OWNER_R, limit=2)
    # Then 1
    assert len(result) == 2


# [claude] HTM-L-13
def test_htm_l_13__each_ticket_comes_with_its_creator(db, mk_ticket, w1, mgr, own):
    """HTM-L-13 — each ticket comes with its creator.
    Rules: `list_tickets` Returns (creator loaded)"""
    tm = mk_ticket("HELP-2026-001", created_by=mgr.id)
    tc = mk_ticket("HELP-2026-002")
    tn = mk_ticket("HELP-2026-003", created_by=None)
    result = HM.list_tickets(db, workspace_id=w1.id, user=own, role=OWNER_R, limit=1000)
    # Then 1
    assert {t.id: (t.creator.name if t.creator else None) for t in result} == {
        tm.id: "Karim",
        tc.id: "Rahim",
        tn.id: None,
    }


# [claude] HTM-L-14
@pytest.mark.xfail(strict=True, reason=BUG_1578)
def test_htm_l_14__a_platform_admin_without_a_role_sees_every_ticket_of_the_workspace(
    db, mk_ticket, w1, w2, mgr, adm
):
    """HTM-L-14 — a platform admin without a role sees every ticket of the workspace.
    Rules: `list_tickets` R2 [BUG-1578]"""
    tm = mk_ticket("HELP-2026-001", created_by=mgr.id)
    tc = mk_ticket("HELP-2026-002")
    mk_ticket("HELP-2026-001", workspace_id=w2.id)
    result = HM.list_tickets(db, workspace_id=w1.id, user=adm, role=None, limit=1000)
    # Then 1
    assert idset(result) == {tm.id, tc.id}


# [claude] HTM-L-15
@pytest.mark.xfail(strict=True, reason=BUG_1578)
def test_htm_l_15__a_platform_admin_with_a_plain_role_sees_every_ticket_of_the_workspace(
    db, mk_ticket, w0, w1, mgr, adm, fin
):
    """HTM-L-15 — a platform admin with a plain role sees every ticket of the workspace.
    Rules: `list_tickets` R2 [BUG-1578]"""
    tm = mk_ticket("HELP-2026-001", created_by=mgr.id)
    ta = mk_ticket("HELP-2026-002", created_by=adm.id)
    tf = mk_ticket("HELP-2026-003", created_by=fin.id)
    mk_ticket("HELP-2026-001", workspace_id=w0.id)
    result = HM.list_tickets(db, workspace_id=w1.id, user=adm, role=GT_R, limit=1000)
    # Then 1
    assert idset(result) == {tm.id, ta.id, tf.id}


# [claude] HTM-L-16
def test_htm_l_16__a_platform_admins_own_tickets_of_the_workspace_are_listed_another_workspaces_are_not(
    db, mk_ticket, w0, w1, w2, adm
):
    """HTM-L-16 — a platform admin's own tickets of the workspace are listed, another workspace's are not.
    Rules: `list_tickets` R1, R2 (holds before and after BUG-1578)"""
    mk_ticket("HELP-2026-001", workspace_id=w0.id, created_by=adm.id)
    ta = mk_ticket("HELP-2026-001", created_by=adm.id)
    mk_ticket("HELP-2026-001", workspace_id=w2.id, created_by=adm.id)
    result = HM.list_tickets(db, workspace_id=w1.id, user=adm, role=None, limit=1000)
    # Then 1
    assert idset(result) == {ta.id}


# [claude] HTM-L-17
def test_htm_l_17__a_negative_skip_raises_dataerror(db, mk_ticket, w1, own):
    """HTM-L-17 — a negative skip raises DataError.
    Rules: `list_tickets` Errors"""
    mk_ticket("HELP-2026-001")
    # Then 1
    with pytest.raises(DataError):
        with db.begin_nested():
            HM.list_tickets(db, workspace_id=w1.id, user=own, role=OWNER_R, skip=-1)


# [claude] HTM-L-18
def test_htm_l_18__a_negative_limit_raises_dataerror(db, mk_ticket, w1, own):
    """HTM-L-18 — a negative limit raises DataError.
    Rules: `list_tickets` Errors"""
    mk_ticket("HELP-2026-001")
    # Then 1
    with pytest.raises(DataError):
        with db.begin_nested():
            HM.list_tickets(db, workspace_id=w1.id, user=own, role=OWNER_R, limit=-1)


# [claude] HTM-L-19
def test_htm_l_19__a_list_writes_nothing_and_keeps_the_callers_pending_row(
    db, mk_ticket, mk_pending, w1, own
):
    """HTM-L-19 — a list writes nothing and keeps the caller's pending row.
    Rules: `list_tickets` Side effects"""
    tc = mk_ticket("HELP-2026-001")
    p = mk_pending()
    with spies(db) as (cm, rb):
        result = HM.list_tickets(db, workspace_id=w1.id, user=own, role=OWNER_R, limit=1000)
    # Then 1
    assert idset(result) == {tc.id}
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert len(db.new) == 1
    assert p in db.new


# --------------------------------------------------------------------------- #
# HelpTicketManager.list_platform_tickets
# --------------------------------------------------------------------------- #


# [claude] HTM-P-01
def test_htm_p_01__tickets_of_every_workspace_each_as_an_item_with_its_workspaces_and_creators_name(
    db, mk_ticket, tag, w0, w2, mgr, fin
):
    """HTM-P-01 — tickets of every workspace, each as an item with its workspace's and creator's name.
    Rules: `list_platform_tickets` R1, R2, R3"""
    t0 = mk_ticket("HELP-2026-001", workspace_id=w0.id, created_by=fin.id)
    t1 = mk_ticket("HELP-2026-001")
    t2 = mk_ticket("HELP-2026-001", workspace_id=w2.id, created_by=mgr.id)
    own = {t0.id, t1.id, t2.id}
    result = HM.list_platform_tickets(db, search=tag, limit=1000)
    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert all(isinstance(t, PlatformHelpTicketListItem) for t in result)
    # Then 3
    assert own_ids(result, own) == {t0.id, t1.id, t2.id}
    # Then 4
    assert {t.id: (t.workspace_name, t.creator_name) for t in result if t.id in own} == {
        t0.id: (f"Alpha {tag}", "Fatima"),
        t1.id: (f"Gamma {tag}", "Rahim"),
        t2.id: (f"Delta {tag}", "Karim"),
    }


# [claude] HTM-P-02
def test_htm_p_02__an_item_carries_the_tickets_own_fields(db, mk_closed, tag, w2, mgr, cr):
    """HTM-P-02 — an item carries the ticket's own fields.
    Rules: `list_platform_tickets` R2"""
    t1 = mk_closed("HELP-2026-004", workspace_id=w2.id)
    result = HM.list_platform_tickets(db, search=tag, limit=1000)
    # Then 1
    assert [t.id for t in result if t.id == t1.id] == [t1.id]
    # Then 2
    e = next(t for t in result if t.id == t1.id)
    assert e.ticket_number == "HELP-2026-004"
    assert e.workspace_id == w2.id
    assert e.title == "Printer jam"
    assert e.description == "It jams"
    assert e.category == "hardware"
    # Then 3
    assert e.status == CLOSED
    assert e.closed_at == PAST
    assert e.closed_by == mgr.id
    assert e.created_by == cr.id


# [claude] HTM-P-03
def test_htm_p_03__a_ticket_without_a_creator_has_creator_name_none(db, mk_ticket, tag):
    """HTM-P-03 — a ticket without a creator has creator_name None.
    Rules: `list_platform_tickets` R2"""
    t1 = mk_ticket("HELP-2026-001", created_by=None)
    result = HM.list_platform_tickets(db, search=tag, limit=1000)
    # Then 1
    assert {t.id: t.creator_name for t in result if t.id == t1.id} == {t1.id: None}


# [claude] HTM-P-04
def test_htm_p_04__status_closed_keeps_only_closed_tickets(db, mk_ticket, mk_closed, tag, w2):
    """HTM-P-04 — status closed keeps only closed tickets.
    Rules: `list_platform_tickets` R1 (status)"""
    t1 = mk_ticket("HELP-2026-001")
    t2 = mk_closed("HELP-2026-001", workspace_id=w2.id)
    own = {t1.id, t2.id}
    result = HM.list_platform_tickets(db, status=CLOSED, search=tag, limit=1000)
    # Then 1
    assert own_ids(result, own) == {t2.id}


# [claude] HTM-P-05
def test_htm_p_05__the_search_reaches_the_query(db, mk_ticket, tag, w0, w2):
    """HTM-P-05 — the search reaches the query.
    Rules: `list_platform_tickets` R1 (search)"""
    t0 = mk_ticket("HELP-2026-001", workspace_id=w0.id)
    t1 = mk_ticket("HELP-2026-001")
    t2 = mk_ticket("HELP-2026-001", workspace_id=w2.id)
    own = {t0.id, t1.id, t2.id}
    result = HM.list_platform_tickets(db, search=f"Delta {tag}", limit=1000)
    # Then 1
    assert own_ids(result, own) == {t2.id}


# [claude] HTM-P-06
def test_htm_p_06__no_matching_row_gives_an_empty_list(db, mk_ticket, tag):
    """HTM-P-06 — no matching row gives an empty list.
    Rules: `list_platform_tickets` R2"""
    mk_ticket("HELP-2026-001")
    result = HM.list_platform_tickets(db, search=f"nomatch-{tag}", limit=1000)
    # Then 1
    assert result == []


# [claude] HTM-P-07
def test_htm_p_07__the_default_limit_is_100(db, mk_ticket, tag):
    """HTM-P-07 — the default limit is 100.
    Rules: `list_platform_tickets` R1 (paging default)"""
    for k in range(1, 102):
        mk_ticket(f"HELP-2026-{k:03d}", title=f"T{k} {tag}")
    result = HM.list_platform_tickets(db, search=tag)
    # Then 1
    assert len(result) == 100


# [claude] HTM-P-08
def test_htm_p_08__skip_reaches_the_query(db, mk_ticket, tag, w0, w2):
    """HTM-P-08 — skip reaches the query.
    Rules: `list_platform_tickets` R1 (paging)"""
    mk_ticket("HELP-2026-001", workspace_id=w0.id)
    mk_ticket("HELP-2026-001")
    mk_ticket("HELP-2026-001", workspace_id=w2.id)
    result = HM.list_platform_tickets(db, search=tag, skip=1, limit=1000)
    # Then 1
    assert len(result) == 2


# [claude] HTM-P-09
def test_htm_p_09__a_negative_limit_raises_dataerror(db, mk_ticket):
    """HTM-P-09 — a negative limit raises DataError.
    Rules: `list_platform_tickets` Errors"""
    mk_ticket("HELP-2026-001")
    # Then 1
    with pytest.raises(DataError):
        with db.begin_nested():
            HM.list_platform_tickets(db, limit=-1)


# [claude] HTM-P-10
def test_htm_p_10__items_keep_the_databases_order(db, mk_ticket, tag, w0, w2):
    """HTM-P-10 — items keep the database's order.
    Rules: `list_platform_tickets` R2 (in the DAO's order)"""
    t1 = mk_ticket("HELP-2026-001")
    t2 = mk_ticket("HELP-2026-001", workspace_id=w2.id)
    t0 = mk_ticket("HELP-2026-001", workspace_id=w0.id)
    db.execute(
        text("UPDATE help_tickets SET created_at = now() + interval '3 hours' WHERE id = :i"),
        {"i": t1.id},
    )
    db.execute(
        text("UPDATE help_tickets SET created_at = now() + interval '2 hours' WHERE id = :i"),
        {"i": t0.id},
    )
    db.execute(
        text("UPDATE help_tickets SET created_at = now() + interval '1 hour' WHERE id = :i"),
        {"i": t2.id},
    )
    db.expire_all()
    result = HM.list_platform_tickets(db, search=tag, limit=1000)
    # Then 1
    assert [t.id for t in result] == [t1.id, t0.id, t2.id]


# [claude] HTM-P-11
def test_htm_p_11__the_platform_list_writes_nothing_and_keeps_the_callers_pending_row(
    db, mk_ticket, mk_pending, tag
):
    """HTM-P-11 — the platform list writes nothing and keeps the caller's pending row.
    Rules: `list_platform_tickets` Side effects"""
    t1 = mk_ticket("HELP-2026-001")
    p = mk_pending()
    with spies(db) as (cm, rb):
        result = HM.list_platform_tickets(db, search=tag, limit=1000)
    # Then 1
    assert idset(result) == {t1.id}
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert len(db.new) == 1
    assert p in db.new


# --------------------------------------------------------------------------- #
# HelpTicketManager.get_platform_ticket
# --------------------------------------------------------------------------- #


# [claude] HTM-Q-01
def test_htm_q_01__a_ticket_of_another_workspace_is_returned_as_an_item_not_a_neighbour(
    db, mk_ticket, tag, w0, w2
):
    """HTM-Q-01 — a ticket of another workspace is returned as an item, not a neighbour.
    Rules: `get_platform_ticket` R1"""
    mk_ticket("HELP-2026-001", title="Other")
    t = mk_ticket("HELP-2026-001", workspace_id=w2.id)
    mk_ticket("HELP-2026-001", workspace_id=w0.id, title="Third")
    result = HM.get_platform_ticket(db, ticket_id=t.id)
    # Then 1
    assert isinstance(result, PlatformHelpTicketListItem)
    # Then 2
    assert result.id == t.id
    assert result.workspace_id == w2.id
    assert result.title == "Printer jam"
    # Then 3
    assert result.workspace_name == f"Delta {tag}"
    assert result.creator_name == "Rahim"


# [claude] HTM-Q-02
def test_htm_q_02__a_ticket_of_the_earliest_workspace_is_returned(db, mk_ticket, tag, w0):
    """HTM-Q-02 — a ticket of the earliest workspace is returned.
    Rules: `get_platform_ticket` R1"""
    t = mk_ticket("HELP-2026-001", workspace_id=w0.id, created_by=None)
    mk_ticket("HELP-2026-001", title="Third")
    result = HM.get_platform_ticket(db, ticket_id=t.id)
    # Then 1
    assert result.id == t.id
    assert result.workspace_name == f"Alpha {tag}"
    # Then 2
    assert result.creator_name is None


# [claude] HTM-Q-03
def test_htm_q_03__an_unknown_id_is_not_found(db, mk_ticket):
    """HTM-Q-03 — an unknown id is not found.
    Rules: `get_platform_ticket` R2"""
    mk_ticket("HELP-2026-001")
    # Then 1
    with pytest.raises(HelpTicketNotFoundError) as exc:
        HM.get_platform_ticket(db, ticket_id=MISSING)
    # Then 2
    assert type(exc.value) is HelpTicketNotFoundError
    # Then 3
    assert str(exc.value) == NOTFOUND


# [claude] HTM-Q-04
def test_htm_q_04__id_0_is_not_found(db, mk_ticket):
    """HTM-Q-04 — id 0 is not found.
    Rules: `get_platform_ticket` R2"""
    mk_ticket("HELP-2026-001")
    # Then 1
    with pytest.raises(HelpTicketNotFoundError) as exc:
        HM.get_platform_ticket(db, ticket_id=0)
    # Then 2
    assert str(exc.value) == NOTFOUND


# [claude] HTM-Q-05
def test_htm_q_05__the_platform_get_writes_nothing_and_keeps_the_callers_pending_row(
    db, mk_ticket, mk_pending
):
    """HTM-Q-05 — the platform get writes nothing and keeps the caller's pending row.
    Rules: `get_platform_ticket` Side effects"""
    t = mk_ticket("HELP-2026-001")
    p = mk_pending()
    with spies(db) as (cm, rb):
        result = HM.get_platform_ticket(db, ticket_id=t.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert len(db.new) == 1
    assert p in db.new


# --------------------------------------------------------------------------- #
# HelpTicketManager.create_ticket
# --------------------------------------------------------------------------- #


# [claude] HTM-C-01
def test_htm_c_01__one_open_ticket_is_created_numbered_and_flushed(db, w1, cr):
    """HTM-C-01 — one open ticket is created, numbered and flushed.
    Rules: `create_ticket` R1"""
    with clock():
        result = HM.create_ticket(
            db,
            workspace_id=w1.id,
            user_id=cr.id,
            payload=HelpTicketCreate(title="Printer jam", description="It jams", category="hardware"),
        )
    # Then 1
    assert isinstance(result, HelpTicket)
    assert result.id is not None
    # Then 2
    row = reread(db, result.id)
    assert row.ticket_number == "HELP-2026-001"
    assert row.workspace_id == w1.id
    assert row.created_by == cr.id
    assert row.status == "open"
    # Then 3
    assert row.title == "Printer jam"
    assert row.description == "It jams"
    assert row.category == "hardware"
    # Then 4
    assert row.closed_at is None
    assert row.closed_by is None
    # Then 5
    assert w1_count(db, w1.id) == 1


# [claude] HTM-C-02
def test_htm_c_02__the_payload_is_stored_as_given_untrimmed(db, w1, fin):
    """HTM-C-02 — the payload is stored as given, untrimmed.
    Rules: `create_ticket` R1 (no check or trimming of its own)"""
    with clock():
        result = HM.create_ticket(
            db,
            workspace_id=w1.id,
            user_id=fin.id,
            payload=HelpTicketCreate.model_construct(
                title="  Printer  JAM ", description=" It  jams ", category=None
            ),
        )
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result.id)
    assert row.title == "  Printer  JAM "
    assert row.description == " It  jams "
    assert row.category is None
    assert row.created_by == fin.id


# [claude] HTM-C-03
def test_htm_c_03__the_number_counts_only_w1s_tickets(db, mk_ticket, w0, w1, w2, cr):
    """HTM-C-03 — the number counts only W1's tickets.
    Rules: `create_ticket` R1 (DAO `create_with_user` R1)"""
    mk_ticket("HELP-2026-001", workspace_id=w0.id)
    mk_ticket("HELP-2026-002", workspace_id=w0.id)
    mk_ticket("HELP-2026-001")
    mk_ticket("HELP-2026-001", workspace_id=w2.id)
    mk_ticket("HELP-2026-002", workspace_id=w2.id)
    with clock():
        result = HM.create_ticket(
            db,
            workspace_id=w1.id,
            user_id=cr.id,
            payload=HelpTicketCreate(title="Toner low", description="Grey prints"),
        )
    # Then 1
    assert result.ticket_number == "HELP-2026-002"
    # Then 2
    row = reread(db, result.id)
    assert row.ticket_number == "HELP-2026-002"
    assert row.workspace_id == w1.id


# [claude] HTM-C-04
def test_htm_c_04__an_unknown_user_raises_integrityerror_and_nothing_is_saved(db, w0, w1, w2):
    """HTM-C-04 — an unknown user raises IntegrityError and nothing is saved.
    Rules: `create_ticket` Errors (DAO R5)"""
    before = counts(db, w0.id, w1.id, w2.id)
    # Then 1
    with pytest.raises(IntegrityError), clock():
        with db.begin_nested():
            HM.create_ticket(
                db,
                workspace_id=w1.id,
                user_id=MISSING,
                payload=HelpTicketCreate(title="Printer jam", description="It jams"),
            )
    # Then 2
    assert counts(db, w0.id, w1.id, w2.id) == before


# [claude] HTM-C-05
def test_htm_c_05__a_number_already_taken_raises_integrityerror_and_nothing_is_saved(
    db, mk_ticket, w0, w1, w2, cr
):
    """HTM-C-05 — a number already taken raises IntegrityError and nothing is saved.
    Rules: `create_ticket` Errors (DAO R4)"""
    ta = mk_ticket("HELP-2026-002")
    w_ids = (w0.id, w1.id, w2.id)
    before = counts(db, *w_ids)
    before_ta = snap(db, ta.id)
    # Then 1
    with pytest.raises(IntegrityError), clock():
        with db.begin_nested():
            HM.create_ticket(
                db,
                workspace_id=w1.id,
                user_id=cr.id,
                payload=HelpTicketCreate(title="Toner low", description="Grey prints"),
            )
    # Then 2
    assert counts(db, *w_ids) == before
    # Then 3
    assert unchanged(db, ta.id) == before_ta


# [claude] HTM-C-06
def test_htm_c_06__create_flushes_but_never_commits_or_rolls_back(db, w1, cr):
    """HTM-C-06 — create flushes but never commits or rolls back.
    Rules: `create_ticket` R1 (flushed, not committed)"""
    w1_id = w1.id
    with spies(db) as (cm, rb):
        sp = db.begin_nested()
        with clock():
            result = HM.create_ticket(
                db,
                workspace_id=w1_id,
                user_id=cr.id,
                payload=HelpTicketCreate(title="Printer jam", description="It jams"),
            )
        # Then 1
        assert result.id is not None
        # Then 2
        assert (
            db.scalar(
                select(func.count())
                .select_from(HelpTicket)
                .where(HelpTicket.workspace_id == w1_id)
            )
            == 1
        )
        # Then 3
        assert cm.call_count == 0
        # Then 4
        assert rb.call_count == 0
        sp.rollback()
    # Then 5
    assert (
        db.scalar(
            select(func.count()).select_from(HelpTicket).where(HelpTicket.workspace_id == w1_id)
        )
        == 0
    )


# --------------------------------------------------------------------------- #
# HelpTicketManager.update_ticket
# --------------------------------------------------------------------------- #


# [claude] HTM-U-01
def test_htm_u_01__the_creator_changes_title_description_and_category_neighbours_untouched(
    db, mk_ticket, cr
):
    """HTM-U-01 — the creator changes title, description and category; neighbours untouched.
    Rules: `update_ticket` R2, R3; Returns"""
    ta = mk_ticket("HELP-2026-001", title="Other")
    t = mk_ticket("HELP-2026-002")
    tb = mk_ticket("HELP-2026-003", title="Third")
    with close_clock():
        result = HM.update_ticket(
            db,
            ticket=t,
            payload=HelpTicketUpdate(title="Toner low", description="Grey prints", category="supplies"),
            user_id=cr.id,
        )
    # Then 1
    assert result is t
    # Then 2
    row = reread(db, t.id)
    assert row.title == "Toner low"
    assert row.description == "Grey prints"
    assert row.category == "supplies"
    # Then 3
    row = reread(db, t.id)
    assert row.status == "open"
    assert row.closed_at is None
    assert row.closed_by is None
    assert row.created_by == cr.id
    # Then 4
    assert reread(db, ta.id).title == "Other"
    # Then 5
    assert reread(db, tb.id).title == "Third"


# [claude] HTM-U-02
def test_htm_u_02__a_creator_with_the_lowest_id_edits_their_own_tickets_text(db, mk_ticket, mgr):
    """HTM-U-02 — a creator with the lowest id edits their own ticket's text.
    Rules: `update_ticket` R3"""
    t = mk_ticket("HELP-2026-001", created_by=mgr.id)
    with close_clock():
        result = HM.update_ticket(
            db, ticket=t, payload=HelpTicketUpdate(title="Toner low"), user_id=mgr.id
        )
    # Then 1
    assert result is t
    # Then 2
    row = reread(db, t.id)
    assert row.title == "Toner low"
    assert row.description == "It jams"
    assert row.category == "hardware"


# [claude] HTM-U-03
def test_htm_u_03__category_null_from_the_creator_clears_the_category(db, mk_ticket, cr):
    """HTM-U-03 — category null from the creator clears the category.
    Rules: `update_ticket` R2"""
    t = mk_ticket("HELP-2026-001")
    with close_clock():
        result = HM.update_ticket(
            db, ticket=t, payload=HelpTicketUpdate(category=None), user_id=cr.id
        )
    # Then 1
    assert result is t
    # Then 2
    row = reread(db, t.id)
    assert row.category is None
    assert row.title == "Printer jam"
    assert row.description == "It jams"


# [claude] HTM-U-04
def test_htm_u_04__an_empty_payload_from_a_non_creator_changes_nothing_and_is_no_refusal(
    db, mk_ticket, mgr
):
    """HTM-U-04 — an empty payload from a non-creator changes nothing and is no refusal.
    Rules: `update_ticket` R1, R4 (nothing sent → no refusal), R10"""
    t = mk_ticket("HELP-2026-001", updated_at=PAST)
    before = snap(db, t.id)
    with close_clock():
        result = HM.update_ticket(db, ticket=t, payload=HelpTicketUpdate(), user_id=mgr.id)
    # Then 1
    assert result is t
    # Then 2
    assert db.is_modified(t) is False
    # Then 3
    assert unchanged(db, t.id) == before
    # Then 4
    assert reread(db, t.id).updated_at == PAST


# [claude] HTM-U-05
def test_htm_u_05__only_the_sent_field_changes_a_text_change_moves_updated_at(db, mk_ticket, cr):
    """HTM-U-05 — only the sent field changes; a text change moves updated_at.
    Rules: `update_ticket` R1, R10"""
    t = mk_ticket("HELP-2026-001", updated_at=PAST)
    with close_clock():
        result = HM.update_ticket(
            db, ticket=t, payload=HelpTicketUpdate(description="Grey prints"), user_id=cr.id
        )
    # Then 1
    assert result is t
    # Then 2
    row = reread(db, t.id)
    assert row.description == "Grey prints"
    assert row.title == "Printer jam"
    assert row.category == "hardware"
    # Then 3
    assert reread(db, t.id).updated_at != PAST


# [claude] HTM-U-06
def test_htm_u_06__a_non_creator_lower_id_closes_a_members_ticket(db, mk_ticket, mgr):
    """HTM-U-06 — a non-creator (lower id) closes a member's ticket.
    Rules: `update_ticket` R5"""
    t = mk_ticket("HELP-2026-001")
    with close_clock():
        result = HM.update_ticket(
            db, ticket=t, payload=HelpTicketUpdate(status="closed"), user_id=mgr.id
        )
    # Then 1
    assert result is t
    # Then 2
    assert result.closed_at == CLOSE_AT
    # Then 3
    row = reread(db, t.id)
    assert row.status == "closed"
    assert row.closed_by == mgr.id
    assert row.closed_at == CLOSE_AT
    # Then 4
    assert row.title == "Printer jam"
    assert row.description == "It jams"
    assert row.category == "hardware"


# [claude] HTM-U-07
def test_htm_u_07__the_creator_closes_their_own_ticket(db, mk_ticket, cr):
    """HTM-U-07 — the creator closes their own ticket.
    Rules: `update_ticket` R5"""
    t = mk_ticket("HELP-2026-001")
    with close_clock():
        result = HM.update_ticket(
            db, ticket=t, payload=HelpTicketUpdate(status="closed"), user_id=cr.id
        )
    # Then 1
    assert result is t
    # Then 2
    row = reread(db, t.id)
    assert row.status == "closed"
    assert row.closed_by == cr.id
    assert row.closed_at == CLOSE_AT


# [claude] HTM-U-08
def test_htm_u_08__a_non_creator_higher_id_reopens_a_closed_ticket(db, mk_closed, own):
    """HTM-U-08 — a non-creator (higher id) reopens a closed ticket: closed_at and closed_by are cleared.
    Rules: `update_ticket` R5"""
    t = mk_closed("HELP-2026-001")
    with close_clock():
        result = HM.update_ticket(
            db, ticket=t, payload=HelpTicketUpdate(status="open"), user_id=own.id
        )
    # Then 1
    assert result is t
    # Then 2
    row = reread(db, t.id)
    assert row.status == "open"
    assert row.closed_at is None
    assert row.closed_by is None
    # Then 3
    assert row.title == "Printer jam"


# [claude] HTM-U-09
def test_htm_u_09__status_null_leaves_status_closed_at_and_closed_by(db, mk_closed, mgr, own):
    """HTM-U-09 — status null leaves status, closed_at and closed_by.
    Rules: `update_ticket` R6"""
    t = mk_closed("HELP-2026-001")
    before = snap(db, t.id)
    with close_clock():
        result = HM.update_ticket(
            db, ticket=t, payload=HelpTicketUpdate(status=None), user_id=own.id
        )
    # Then 1
    assert result is t
    # Then 2
    assert unchanged(db, t.id) == before
    # Then 3
    row = reread(db, t.id)
    assert row.status == "closed"
    assert row.closed_at == PAST
    assert row.closed_by == mgr.id


# [claude] HTM-U-10
def test_htm_u_10__a_text_change_without_status_leaves_the_closed_state(db, mk_closed, mgr, cr):
    """HTM-U-10 — a text change without status leaves the closed state.
    Rules: `update_ticket` R6"""
    t = mk_closed("HELP-2026-001")
    with close_clock():
        result = HM.update_ticket(
            db, ticket=t, payload=HelpTicketUpdate(category="network"), user_id=cr.id
        )
    # Then 1
    assert result is t
    # Then 2
    row = reread(db, t.id)
    assert row.category == "network"
    assert row.status == "closed"
    assert row.closed_at == PAST
    assert row.closed_by == mgr.id


# [claude] HTM-U-11
def test_htm_u_11__a_status_value_other_than_open_closed_is_ignored(db, mk_ticket, own):
    """HTM-U-11 — a status value other than open / closed is ignored.
    Rules: `update_ticket` R6"""
    t = mk_ticket("HELP-2026-001")
    before = snap(db, t.id)
    with close_clock():
        result = HM.update_ticket(
            db,
            ticket=t,
            payload=HelpTicketUpdate.model_construct(_fields_set={"status"}, status="archived"),
            user_id=own.id,
        )
    # Then 1
    assert result is t
    # Then 2
    assert unchanged(db, t.id) == before
    # Then 3
    row = reread(db, t.id)
    assert row.status == "open"
    assert row.closed_at is None
    assert row.closed_by is None


# [claude] HTM-U-12
def test_htm_u_12__closed_with_a_capital_is_not_a_close(db, mk_ticket, own):
    """HTM-U-12 — "Closed" with a capital is not a close.
    Rules: `update_ticket` R6"""
    t = mk_ticket("HELP-2026-001")
    with close_clock():
        result = HM.update_ticket(
            db,
            ticket=t,
            payload=HelpTicketUpdate.model_construct(_fields_set={"status"}, status="Closed"),
            user_id=own.id,
        )
    # Then 1
    assert result is t
    # Then 2
    row = reread(db, t.id)
    assert row.status == "open"
    assert row.closed_at is None
    assert row.closed_by is None


# [claude] HTM-U-13
def test_htm_u_13__a_plain_string_closed_not_the_enum_closes(db, mk_ticket, own):
    """HTM-U-13 — a plain string "closed" (not the enum) closes.
    Rules: `update_ticket` R5, R6 (value used as given)"""
    t = mk_ticket("HELP-2026-001")
    with close_clock():
        result = HM.update_ticket(
            db,
            ticket=t,
            payload=HelpTicketUpdate.model_construct(_fields_set={"status"}, status="closed"),
            user_id=own.id,
        )
    # Then 1
    assert result is t
    # Then 2
    row = reread(db, t.id)
    assert row.status == "closed"
    assert row.closed_by == own.id
    assert row.closed_at == CLOSE_AT


# [claude] HTM-U-14
def test_htm_u_14__a_plain_string_open_not_the_enum_reopens(db, mk_closed, own):
    """HTM-U-14 — a plain string "open" (not the enum) reopens.
    Rules: `update_ticket` R5, R6 (value used as given)"""
    t = mk_closed("HELP-2026-001")
    with close_clock():
        result = HM.update_ticket(
            db,
            ticket=t,
            payload=HelpTicketUpdate.model_construct(_fields_set={"status"}, status="open"),
            user_id=own.id,
        )
    # Then 1
    assert result is t
    # Then 2
    row = reread(db, t.id)
    assert row.status == "open"
    assert row.closed_at is None
    assert row.closed_by is None


# [claude] HTM-U-15
def test_htm_u_15__reopening_an_open_ticket_changes_nothing(db, mk_ticket, own):
    """HTM-U-15 — reopening an open ticket changes nothing.
    Rules: `update_ticket` R7 (second half)"""
    t = mk_ticket("HELP-2026-001")
    before = snap(db, t.id)
    with close_clock():
        result = HM.update_ticket(
            db, ticket=t, payload=HelpTicketUpdate(status="open"), user_id=own.id
        )
    # Then 1
    assert result is t
    # Then 2
    assert unchanged(db, t.id) == before


# [claude] HTM-U-16
@pytest.mark.xfail(strict=True, reason=BUG_1576)
def test_htm_u_16__closing_an_already_closed_ticket_keeps_who_closed_it_and_when(
    db, mk_closed, mgr, own
):
    """HTM-U-16 — closing an already closed ticket keeps who closed it and when.
    Rules: `update_ticket` R7 [BUG-1576]"""
    t = mk_closed("HELP-2026-001")
    with close_clock():
        result = HM.update_ticket(
            db, ticket=t, payload=HelpTicketUpdate(status="closed"), user_id=own.id
        )
    # Then 1
    assert result is t
    # Then 2
    row = reread(db, t.id)
    assert row.closed_by == mgr.id
    # Then 3
    assert row.closed_at == PAST
    # Then 4
    assert row.status == "closed"


# [claude] HTM-U-17
@pytest.mark.xfail(strict=True, reason=BUG_1577)
def test_htm_u_17__closed_at_is_the_true_moment_whatever_the_databases_time_zone(
    db, mk_ticket, mgr
):
    """HTM-U-17 — closed_at is the true moment whatever the database's time zone.
    Rules: `update_ticket` R8 [BUG-1577]"""
    db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))
    t = mk_ticket("HELP-2026-001")
    # Real clock: no close clock in this card.
    result = HM.update_ticket(
        db, ticket=t, payload=HelpTicketUpdate(status="closed"), user_id=mgr.id
    )
    # Then 1
    assert result is t
    # Then 2
    row = reread(db, t.id)
    assert abs(row.closed_at - row.created_at) < timedelta(seconds=60)


# [claude] HTM-U-18
@pytest.mark.xfail(strict=True, reason=BUG_1863)
def test_htm_u_18__a_ground_team_manager_may_not_change_a_members_title_refused_before_any_write(
    db, mk_ticket, mk_pending, w0, w1, w2, mgr
):
    """HTM-U-18 — a ground-team-manager (lower id) may not change a member's title; refused before any write.
    Rules: `update_ticket` R4 [BUG-1863], Errors row 1"""
    t = mk_ticket("HELP-2026-001")
    p = mk_pending()
    w_ids = (w0.id, w1.id, w2.id)
    before = snap(db, t.id)
    before_counts = counts(db, *w_ids)
    # Then 1
    with pytest.raises(HelpTicketForbiddenError) as exc, close_clock():
        HM.update_ticket(
            db, ticket=t, payload=HelpTicketUpdate(title="Work order missing"), user_id=mgr.id
        )
    # Then 2
    assert type(exc.value) is HelpTicketForbiddenError
    # Then 3
    assert str(exc.value) == FORBID
    # Then 4
    assert db.is_modified(t) is False
    # Then 5
    assert t.title == "Printer jam"
    assert t.description == "It jams"
    assert t.category == "hardware"
    # Then 6
    assert not db.dirty
    assert not db.deleted
    # Then 7
    assert len(db.new) == 1
    assert p in db.new
    # Then 8
    assert unchanged(db, t.id) == before
    # Then 9
    assert counts(db, *w_ids) == before_counts


# [claude] HTM-U-19
@pytest.mark.xfail(strict=True, reason=BUG_1863)
def test_htm_u_19__a_finance_member_higher_id_may_not_change_a_members_description(
    db, mk_ticket, mk_pending, fin
):
    """HTM-U-19 — a finance member (higher id) may not change a member's description.
    Rules: `update_ticket` R4 [BUG-1863]"""
    t = mk_ticket("HELP-2026-001")
    p = mk_pending()
    before = snap(db, t.id)
    # Then 1
    with pytest.raises(HelpTicketForbiddenError) as exc, close_clock():
        HM.update_ticket(
            db, ticket=t, payload=HelpTicketUpdate(description="Nothing happened"), user_id=fin.id
        )
    # Then 2
    assert str(exc.value) == FORBID
    # Then 3
    assert db.is_modified(t) is False
    # Then 4
    assert t.description == "It jams"
    # Then 5
    assert not db.dirty
    assert not db.deleted
    # Then 6
    assert len(db.new) == 1
    assert p in db.new
    # Then 7
    assert unchanged(db, t.id) == before


# [claude] HTM-U-20
@pytest.mark.xfail(strict=True, reason=BUG_1863)
def test_htm_u_20__an_owner_higher_id_may_not_change_a_members_category(
    db, mk_ticket, mk_pending, own
):
    """HTM-U-20 — an owner (higher id) may not change a member's category.
    Rules: `update_ticket` R4 [BUG-1863]"""
    t = mk_ticket("HELP-2026-001")
    p = mk_pending()
    before = snap(db, t.id)
    # Then 1
    with pytest.raises(HelpTicketForbiddenError) as exc, close_clock():
        HM.update_ticket(db, ticket=t, payload=HelpTicketUpdate(category="other"), user_id=own.id)
    # Then 2
    assert str(exc.value) == FORBID
    # Then 3
    assert db.is_modified(t) is False
    # Then 4
    assert t.category == "hardware"
    # Then 5
    assert not db.dirty
    assert not db.deleted
    # Then 6
    assert len(db.new) == 1
    assert p in db.new
    # Then 7
    assert unchanged(db, t.id) == before


# [claude] HTM-U-21
@pytest.mark.xfail(strict=True, reason=BUG_1863)
def test_htm_u_21__sending_category_null_counts_as_a_text_change_and_is_refused(
    db, mk_ticket, mk_pending, mgr
):
    """HTM-U-21 — sending category null counts as a text change and is refused.
    Rules: `update_ticket` R4 [BUG-1863]"""
    t = mk_ticket("HELP-2026-001")
    p = mk_pending()
    before = snap(db, t.id)
    # Then 1
    with pytest.raises(HelpTicketForbiddenError) as exc, close_clock():
        HM.update_ticket(db, ticket=t, payload=HelpTicketUpdate(category=None), user_id=mgr.id)
    # Then 2
    assert str(exc.value) == FORBID
    # Then 3
    assert db.is_modified(t) is False
    # Then 4
    assert t.category == "hardware"
    # Then 5
    assert len(db.new) == 1
    assert p in db.new
    # Then 6
    assert unchanged(db, t.id) == before


# [claude] HTM-U-22
@pytest.mark.xfail(strict=True, reason=BUG_1863)
def test_htm_u_22__sending_the_unchanged_title_still_counts_as_a_text_change(
    db, mk_ticket, mk_pending, fin
):
    """HTM-U-22 — sending the unchanged title still counts as a text change.
    Rules: `update_ticket` R4 [BUG-1863]"""
    t = mk_ticket("HELP-2026-001")
    p = mk_pending()
    before = snap(db, t.id)
    # Then 1
    with pytest.raises(HelpTicketForbiddenError) as exc, close_clock():
        HM.update_ticket(db, ticket=t, payload=HelpTicketUpdate(title="Printer jam"), user_id=fin.id)
    # Then 2
    assert str(exc.value) == FORBID
    # Then 3
    assert db.is_modified(t) is False
    # Then 4
    assert len(db.new) == 1
    assert p in db.new
    # Then 5
    assert unchanged(db, t.id) == before


# [claude] HTM-U-23
@pytest.mark.xfail(strict=True, reason=BUG_1863)
def test_htm_u_23__a_text_change_combined_with_a_close_is_refused_whole(
    db, mk_ticket, mk_pending, mgr
):
    """HTM-U-23 — a text change combined with a close is refused whole: the status is not applied.
    Rules: `update_ticket` R4 [BUG-1863]"""
    t = mk_ticket("HELP-2026-001")
    p = mk_pending()
    before = snap(db, t.id)
    # Then 1
    with pytest.raises(HelpTicketForbiddenError) as exc, close_clock():
        HM.update_ticket(
            db,
            ticket=t,
            payload=HelpTicketUpdate(title="Work order missing", status="closed"),
            user_id=mgr.id,
        )
    # Then 2
    assert str(exc.value) == FORBID
    # Then 3
    assert db.is_modified(t) is False
    # Then 4
    assert t.status == "open"
    assert t.closed_at is None
    assert t.closed_by is None
    # Then 5
    assert t.title == "Printer jam"
    # Then 6
    assert not db.dirty
    assert not db.deleted
    # Then 7
    assert len(db.new) == 1
    assert p in db.new
    # Then 8
    row = reread(db, t.id)
    assert row.status == "open"
    assert row.closed_at is None
    assert row.closed_by is None
    # Then 9
    assert unchanged(db, t.id) == before


# [claude] HTM-U-24
@pytest.mark.xfail(strict=True, reason=BUG_1863)
def test_htm_u_24__a_text_change_combined_with_a_reopen_is_refused_whole(
    db, mk_closed, mk_pending, mgr, own
):
    """HTM-U-24 — a text change combined with a reopen is refused whole: the ticket stays closed.
    Rules: `update_ticket` R4 [BUG-1863]"""
    t = mk_closed("HELP-2026-001")
    p = mk_pending()
    before = snap(db, t.id)
    # Then 1
    with pytest.raises(HelpTicketForbiddenError) as exc, close_clock():
        HM.update_ticket(
            db,
            ticket=t,
            payload=HelpTicketUpdate(description="Nothing happened", status="open"),
            user_id=own.id,
        )
    # Then 2
    assert str(exc.value) == FORBID
    # Then 3
    assert db.is_modified(t) is False
    # Then 4
    assert t.status == "closed"
    assert t.closed_at == PAST
    assert t.closed_by == mgr.id
    # Then 5
    assert t.description == "It jams"
    # Then 6
    assert len(db.new) == 1
    assert p in db.new
    # Then 7
    row = reread(db, t.id)
    assert row.status == "closed"
    assert row.closed_at == PAST
    assert row.closed_by == mgr.id
    # Then 8
    assert unchanged(db, t.id) == before


# [claude] HTM-U-25
@pytest.mark.xfail(strict=True, reason=BUG_1863)
def test_htm_u_25__a_ticket_whose_creator_is_gone_has_its_text_changed_by_nobody(
    db, mk_ticket, mk_pending, w0, w1, w2, own
):
    """HTM-U-25 — a ticket whose creator is gone has its text changed by nobody.
    Rules: `update_ticket` R4 [BUG-1863]"""
    t = mk_ticket("HELP-2026-001", created_by=None)
    p = mk_pending()
    w_ids = (w0.id, w1.id, w2.id)
    before = snap(db, t.id)
    before_counts = counts(db, *w_ids)
    # Then 1
    with pytest.raises(HelpTicketForbiddenError) as exc, close_clock():
        HM.update_ticket(
            db, ticket=t, payload=HelpTicketUpdate(title="Work order missing"), user_id=own.id
        )
    # Then 2
    assert str(exc.value) == FORBID
    # Then 3
    assert db.is_modified(t) is False
    # Then 4
    assert t.title == "Printer jam"
    # Then 5
    assert len(db.new) == 1
    assert p in db.new
    # Then 6
    assert unchanged(db, t.id) == before
    # Then 7
    assert counts(db, *w_ids) == before_counts


# [claude] HTM-U-26
@pytest.mark.xfail(strict=True, reason=BUG_1863)
def test_htm_u_26__a_platform_admin_may_not_change_a_members_description(
    db, mk_ticket, mk_pending, adm
):
    """HTM-U-26 — a platform admin may not change a member's description.
    Rules: `update_ticket` R4 [BUG-1863]"""
    t = mk_ticket("HELP-2026-001")
    p = mk_pending()
    before = snap(db, t.id)
    # Then 1
    with pytest.raises(HelpTicketForbiddenError) as exc, close_clock():
        HM.update_ticket(
            db, ticket=t, payload=HelpTicketUpdate(description="Nothing happened"), user_id=adm.id
        )
    # Then 2
    assert str(exc.value) == FORBID
    # Then 3
    assert db.is_modified(t) is False
    # Then 4
    assert t.description == "It jams"
    # Then 5
    assert len(db.new) == 1
    assert p in db.new
    # Then 6
    assert unchanged(db, t.id) == before


# [claude] HTM-U-27
@pytest.mark.xfail(strict=True, reason=BUG_1863)
def test_htm_u_27__the_creator_of_other_tickets_here_and_elsewhere_may_not_edit_this_one(
    db, mk_ticket, mk_pending, w0, w1, w2, fin
):
    """HTM-U-27 — the creator of other tickets, here and elsewhere, may not edit this one.
    Rules: `update_ticket` R4 [BUG-1863] (creator grant held on a different record)"""
    mk_ticket("HELP-2026-002", workspace_id=w0.id, created_by=fin.id)
    mk_ticket("HELP-2026-001", created_by=fin.id)
    t = mk_ticket("HELP-2026-002")
    mk_ticket("HELP-2026-003", created_by=fin.id)
    mk_ticket("HELP-2026-002", workspace_id=w2.id, created_by=fin.id)
    p = mk_pending()
    w_ids = (w0.id, w1.id, w2.id)
    before = snap(db, t.id)
    before_counts = counts(db, *w_ids)
    # Then 1
    with pytest.raises(HelpTicketForbiddenError) as exc, close_clock():
        HM.update_ticket(
            db, ticket=t, payload=HelpTicketUpdate(title="Work order missing"), user_id=fin.id
        )
    # Then 2
    assert str(exc.value) == FORBID
    # Then 3
    assert db.is_modified(t) is False
    # Then 4
    assert t.title == "Printer jam"
    # Then 5
    assert len(db.new) == 1
    assert p in db.new
    # Then 6
    assert unchanged(db, t.id) == before
    # Then 7
    assert counts(db, *w_ids) == before_counts


# [claude] HTM-U-28
@pytest.mark.xfail(strict=True, reason=BUG_1863)
def test_htm_u_28__a_refused_text_change_neither_commits_nor_rolls_back(
    db, mk_ticket, mk_pending, mgr
):
    """HTM-U-28 — a refused text change neither commits nor rolls back.
    Rules: `update_ticket` R4 [BUG-1863] (refusal before any write; the caller owns the transaction)"""
    t = mk_ticket("HELP-2026-001")
    p = mk_pending()
    # Then 1
    with spies(db) as (cm, rb), close_clock(), pytest.raises(HelpTicketForbiddenError):
        HM.update_ticket(
            db, ticket=t, payload=HelpTicketUpdate(title="Work order missing"), user_id=mgr.id
        )
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert db.is_modified(t) is False
    # Then 5
    assert len(db.new) == 1
    assert p in db.new


# [claude] HTM-U-29
def test_htm_u_29__title_null_reaches_the_column_integrityerror_on_flush_no_rollback_by_the_manager(
    db, mk_ticket, cr
):
    """HTM-U-29 — title null reaches the column: IntegrityError on flush, no rollback by the manager.
    Rules: `update_ticket` R9, Errors row 2"""
    t = mk_ticket("HELP-2026-001")
    # Then 1
    with spies(db) as (cm, rb), close_clock(), pytest.raises(IntegrityError):
        with db.begin_nested():
            HM.update_ticket(
                db,
                ticket=t,
                payload=HelpTicketUpdate.model_construct(_fields_set={"title"}, title=None),
                user_id=cr.id,
            )
    # Then 2
    assert rb.call_count == 0
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert reread(db, t.id).title == "Printer jam"


# [claude] HTM-U-30
def test_htm_u_30__description_null_reaches_the_column_integrityerror_on_flush(db, mk_ticket, cr):
    """HTM-U-30 — description null reaches the column: IntegrityError on flush.
    Rules: `update_ticket` R9"""
    t = mk_ticket("HELP-2026-001")
    # Then 1
    with pytest.raises(IntegrityError), close_clock():
        with db.begin_nested():
            HM.update_ticket(
                db,
                ticket=t,
                payload=HelpTicketUpdate.model_construct(
                    _fields_set={"description"}, description=None
                ),
                user_id=cr.id,
            )
    # Then 2
    assert reread(db, t.id).description == "It jams"


# [claude] HTM-U-31
def test_htm_u_31__update_flushes_but_never_commits_or_rolls_back(db, mk_ticket, cr):
    """HTM-U-31 — update flushes but never commits or rolls back.
    Rules: `update_ticket` Returns (flushed, not committed)"""
    t = mk_ticket("HELP-2026-001")
    t_id = t.id
    with spies(db) as (cm, rb):
        sp = db.begin_nested()
        with close_clock():
            result = HM.update_ticket(
                db,
                ticket=t,
                payload=HelpTicketUpdate(title="Toner low", status="closed"),
                user_id=cr.id,
            )
        # Then 1
        assert result is t
        # Then 2
        assert db.execute(
            text("SELECT title, status FROM help_tickets WHERE id = :i"), {"i": t_id}
        ).one() == ("Toner low", "closed")
        # Then 3
        assert cm.call_count == 0
        # Then 4
        assert rb.call_count == 0
        sp.rollback()
    # Then 5
    assert db.execute(
        text("SELECT title, status FROM help_tickets WHERE id = :i"), {"i": t_id}
    ).one() == ("Printer jam", "open")


# [claude] HTM-U-32
def test_htm_u_32__the_creators_text_change_and_close_in_one_payload_both_apply(db, mk_ticket, cr):
    """HTM-U-32 — the creator's text change and close in one payload both apply.
    Rules: `update_ticket` R3, R5"""
    t = mk_ticket("HELP-2026-001")
    with close_clock():
        result = HM.update_ticket(
            db,
            ticket=t,
            payload=HelpTicketUpdate(title="Toner low", status="closed"),
            user_id=cr.id,
        )
    # Then 1
    assert result is t
    # Then 2
    row = reread(db, t.id)
    assert row.title == "Toner low"
    assert row.status == "closed"
    assert row.closed_by == cr.id
    assert row.closed_at == CLOSE_AT


# --------------------------------------------------------------------------- #
# HelpTicketManager.to_response
# --------------------------------------------------------------------------- #


# [claude] HTM-R-01
def test_htm_r_01__every_field_of_the_row_and_the_creators_name(db, mk_closed, w1, mgr, cr):
    """HTM-R-01 — every field of the row, and the creator's name.
    Rules: `to_response` R1, R2"""
    t = mk_closed("HELP-2026-007")
    result = HelpTicketManager.to_response(ticket=t)
    # Then 1
    assert isinstance(result, HelpTicketResponse)
    # Then 2
    assert result.id == t.id
    assert result.workspace_id == w1.id
    assert result.ticket_number == "HELP-2026-007"
    # Then 3
    assert result.title == "Printer jam"
    assert result.description == "It jams"
    assert result.category == "hardware"
    # Then 4
    assert result.status == CLOSED
    assert result.closed_at == PAST
    assert result.closed_by == mgr.id
    # Then 5
    assert result.created_by == cr.id
    assert result.creator_name == "Rahim"
    # Then 6
    assert result.created_at == db.scalar(select(HelpTicket.created_at).where(HelpTicket.id == t.id))
    # Then 7
    assert result.updated_at == db.scalar(select(HelpTicket.updated_at).where(HelpTicket.id == t.id))


# [claude] HTM-R-02
def test_htm_r_02__no_creator_gives_creator_name_none(mk_ticket):
    """HTM-R-02 — no creator gives creator_name None.
    Rules: `to_response` R2"""
    t = mk_ticket("HELP-2026-001", created_by=None)
    result = HelpTicketManager.to_response(ticket=t)
    # Then 1
    assert result.id == t.id
    assert result.created_by is None
    # Then 2
    assert result.creator_name is None


# [claude] HTM-R-03
def test_htm_r_03__an_unflushed_row_is_not_a_valid_response(w1, cr):
    """HTM-R-03 — an unflushed row is not a valid response.
    Rules: `to_response` Errors"""
    u = HelpTicket(
        workspace_id=w1.id,
        ticket_number="HELP-2026-009",
        title="Loose",
        description="Never flushed",
        created_by=cr.id,
    )
    # Then 1
    with pytest.raises(PydanticValidationError):
        HelpTicketManager.to_response(ticket=u)


# --------------------------------------------------------------------------- #
# HelpTicketManager._to_platform_item
# --------------------------------------------------------------------------- #


# [claude] HTM-I-01
def test_htm_i_01__every_response_field_the_given_workspace_name_and_the_given_creator_name(
    mk_closed, w2, mgr, cr
):
    """HTM-I-01 — every response field, the given workspace name and the given creator name.
    Rules: `_to_platform_item` R1, R2"""
    t = mk_closed("HELP-2026-007", workspace_id=w2.id)
    result = HelpTicketManager._to_platform_item(
        ticket=t, workspace_name="Elsewhere", creator_name="Zed"
    )
    # Then 1
    assert isinstance(result, PlatformHelpTicketListItem)
    # Then 2
    assert result.workspace_name == "Elsewhere"
    assert result.creator_name == "Zed"
    # Then 3
    assert result.id == t.id
    assert result.workspace_id == w2.id
    assert result.ticket_number == "HELP-2026-007"
    # Then 4
    assert result.title == "Printer jam"
    assert result.status == CLOSED
    assert result.closed_by == mgr.id
    assert result.created_by == cr.id


# [claude] HTM-I-02
def test_htm_i_02__creator_name_none_falls_back_to_the_loaded_creators_name(mk_ticket):
    """HTM-I-02 — creator_name None falls back to the loaded creator's name.
    Rules: `_to_platform_item` R2"""
    t = mk_ticket("HELP-2026-001")
    result = HelpTicketManager._to_platform_item(
        ticket=t, workspace_name="Elsewhere", creator_name=None
    )
    # Then 1
    assert result.creator_name == "Rahim"


# [claude] HTM-I-03
def test_htm_i_03__creator_name_empty_falls_back_to_the_loaded_creators_name(mk_ticket):
    """HTM-I-03 — creator_name "" falls back to the loaded creator's name.
    Rules: `_to_platform_item` R2"""
    t = mk_ticket("HELP-2026-001")
    result = HelpTicketManager._to_platform_item(
        ticket=t, workspace_name="Elsewhere", creator_name=""
    )
    # Then 1
    assert result.creator_name == "Rahim"


# [claude] HTM-I-04
def test_htm_i_04__no_given_name_and_no_creator_gives_none(mk_ticket):
    """HTM-I-04 — no given name and no creator gives None.
    Rules: `_to_platform_item` R2"""
    t = mk_ticket("HELP-2026-001", created_by=None)
    result = HelpTicketManager._to_platform_item(
        ticket=t, workspace_name="Elsewhere", creator_name=None
    )
    # Then 1
    assert result.creator_name is None
    # Then 2
    assert result.workspace_name == "Elsewhere"


# [claude] HTM-I-05
def test_htm_i_05__a_given_name_wins_over_a_ticket_without_a_creator(mk_ticket):
    """HTM-I-05 — a given name wins over a ticket without a creator.
    Rules: `_to_platform_item` R2"""
    t = mk_ticket("HELP-2026-001", created_by=None)
    result = HelpTicketManager._to_platform_item(
        ticket=t, workspace_name="Elsewhere", creator_name="Zed"
    )
    # Then 1
    assert result.creator_name == "Zed"
