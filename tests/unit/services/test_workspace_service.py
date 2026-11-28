"""Unit tests for app/services/workspace_service.py.

Implements tests/unit/services/workspace_service.cases.md (revision 5), one test
per case, in card order. Real Postgres session (`db` fixture): a `commit()`
only releases a savepoint, so the service's commits are safe and the fixture's
outer rollback discards everything. Patched, as Conventions name them: the
manager's and the invitation DAO's `utcnow` (every When runs inside `clock()`),
the failing commit / refresh wraps, the refresh trap and the commit / rollback
spies (the spies still call the real method).

Normal mode: every test is written from its card and carries a `# [claude] <ID>`
comment. Card names are attributes of the standing-rows namespace `s`
(`s.W1`, `s.UA`, `s.EA`, ...); `# Then N` marks the checks of the card's Then
line N.
"""

# ruff: noqa: SIM117, DTZ001  (Conventions prescribe the nested `with` and naive datetimes)
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import event, func, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import DataError, IntegrityError

from app.core.exceptions import (
    APIException,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.models.factory import Factory
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.workspace import Workspace
from app.models.workspace_audit_log import WorkspaceAuditLog
from app.models.workspace_invitation import WorkspaceInvitation
from app.models.workspace_member import WorkspaceMember
from app.schemas.workspace import WorkspaceCreate, WorkspaceUpdate
from app.schemas.workspace_invitation import AcceptInvitationRequest, InviteUserRequest
from app.schemas.workspace_member import RoleChangeRequest
from app.services.workspace_service import workspace_service
from tests.unit.factories import make_profile, make_subscription_plan, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

svc = workspace_service

MISSING = 999999999
NOW = datetime(2026, 3, 5, 12, 0, 0)
DAY = timedelta(days=1)
NOTMEM = "You are not a member of this workspace"
OWNONLY = "Only the workspace owner can perform this action"

BUG_1280 = "BUG-1280: Someone who left the workspace stays on its projects"
BUG_1400 = "BUG-1400: Member lists have no sort order"
BUG_1404 = "BUG-1404: Workspace audit rows never record IP address or user agent"
BUG_1871 = 'BUG-1871: "Unlimited" plan (max_members = -1) cannot send any invitation'
BUG_1872 = 'BUG-1872: "Unlimited" plan (max_members = -1) cannot add any member'
BUG_1873 = "BUG-1873: Two open invitations to one email take two seats"
BUG_1874 = (
    "BUG-1874: Accepting one invitation leaves the other invitations to that email "
    "pending and counted"
)
BUG_1980 = "BUG-1980: Workspace names are not trimmed and may be only spaces"
BUG_1982 = "BUG-1982: A removed member can be invited back but can never accept"
BUG_1985 = "BUG-1985: A new member's row never records who invited them"
BUG_1986 = (
    "BUG-1986: A non-owner trying to cancel an invitation learns whether it exists "
    "and its state"
)
BUG_1987 = "BUG-1987: Invitation expiry boundary differs from the lists and seat count"
BUG_1990 = "BUG-1990: Any member who is not ground-team can remove any non-owner member"
BUG_2250 = "BUG-2250: Editing a workspace tells a missing workspace from someone else's"
BUG_2251 = (
    "BUG-2251: Not-found and wrong-state refusals of member removal and invitation "
    "cancel answer 403"
)
BUG_2252 = (
    "BUG-2252: Workspace, member and invitation lists read one related row per entry"
)
BUG_2253 = "BUG-2253: Member role changes and workspace edits leave no audit row"
BUG_2254 = "BUG-2254: A removed member's role can still be changed"
BUG_2256 = "BUG-2256: Over-long billing email or position gives a 500"
BUG_2257 = "BUG-2257: The service lets a member be given the owner role"
BUG_2258 = "BUG-2258: The owner can never change their own position"
NO_OWNER = "The owner role cannot be assigned. Ownership transfer is not available."


def _add(db, row):
    db.add(row)
    db.flush()
    return row


# --------------------------------------------------------------------------- #
# Conventions -> standing rows (every test, built in this order)
# --------------------------------------------------------------------------- #


@pytest.fixture
def s(db):
    tag = uuid.uuid4().hex[:8]
    n = SimpleNamespace(TAG=tag, SL=f"acme-{tag}")
    n.E0 = f"zed.{tag}@acme.com"
    n.EO = f"own.{tag}@acme.com"
    n.EA = f"ann.{tag}@acme.com"
    n.EB = f"bob.{tag}@acme.com"
    n.EC = f"cat.{tag}@acme.com"
    n.E2 = f"two.{tag}@acme.com"
    n.EQ = f"qin.{tag}@acme.com"
    n.ED = f"dan.{tag}@acme.com"
    n.PL0 = make_subscription_plan(db, max_members=10)
    n.PL1 = make_subscription_plan(db, max_members=10)
    n.PL2 = make_subscription_plan(db, max_members=10)
    n.U0 = make_profile(db, email=n.E0, name="Zara Zero")
    n.UO = make_profile(db, email=n.EO, name="Olive Owner")
    n.UA = make_profile(db, email=n.EA, name="Ann Lee")
    n.UB = make_profile(db, email=n.EB, name="Bob Roy")
    n.UC = make_profile(db, email=n.EC, name="Cat Kim")
    n.U2 = make_profile(db, email=n.E2, name="Tom Two")
    n.UQ = make_profile(db, email=n.EQ, name="Quinn Extra")
    n.W0 = make_workspace(db, subscription_plan_id=n.PL0.id, owner_user_id=n.U0.id)
    n.W1 = make_workspace(db, subscription_plan_id=n.PL1.id, owner_user_id=n.UO.id)
    n.W2 = make_workspace(db, subscription_plan_id=n.PL2.id, owner_user_id=n.U2.id)
    n.M0 = _add(
        db,
        WorkspaceMember(
            workspace_id=n.W0.id, user_id=n.U0.id, role="owner", status="active"
        ),
    )
    n.MO = _add(
        db,
        WorkspaceMember(
            workspace_id=n.W1.id, user_id=n.UO.id, role="owner", status="active"
        ),
    )
    n.M2 = _add(
        db,
        WorkspaceMember(
            workspace_id=n.W2.id, user_id=n.U2.id, role="owner", status="active"
        ),
    )
    return n


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #


# Convention "member(U, role, status='active', ws=W1)"; "but" adds columns
def member(db, s, u, role, status="active", ws=None, **but):
    ws = ws or s.W1
    return _add(
        db,
        WorkspaceMember(
            workspace_id=ws.id, user_id=u.id, role=role, status=status, **but
        ),
    )


# Convention "invitation J to e"; "but" overrides columns
def invitation(db, s, j, email, **but):
    fields = {
        "workspace_id": s.W1.id,
        "email": email,
        "role": "member",
        "token": f"tok-{j}-{s.TAG}",
        "status": "pending",
        "expires_at": NOW + DAY,
        "invited_by_user_id": s.UO.id,
    }
    fields.update(but)
    return _add(db, WorkspaceInvitation(**fields))


# Convention "limit n"
def limit(db, s, n):
    s.PL1.max_members = n
    db.flush()


# Convention "PD"
def mk_pd(db, s):
    return make_subscription_plan(
        db, name=f"free-{s.TAG}", is_default=True, is_active=True, max_members=3
    )


# Convention "PX"
def mk_px(db, s):
    return make_subscription_plan(
        db, name=f"pro-{s.TAG}", is_default=False, is_active=True, max_members=10
    )


# Convention "commit point"
def commit_point(db):
    db.commit()


# Convention "extra row X" (after the commit point, not committed); returns X_ID
def add_x(db, s):
    x = _add(
        db,
        WorkspaceMember(
            workspace_id=s.W2.id, user_id=s.UQ.id, role="viewer", status="active"
        ),
    )
    return x.id


# --------------------------------------------------------------------------- #
# Conventions -> externals and named checks
# --------------------------------------------------------------------------- #


# Externals: every When runs inside it
@contextmanager
def clock():
    with (
        patch("app.managers.workspace_manager.utcnow", return_value=NOW),
        patch("app.dao.workspace_invitation.utcnow", return_value=NOW),
    ):
        yield


def snap(row):
    """Every column of the row (for unchanged(X)), read from the instance."""
    return {a.key: getattr(row, a.key) for a in sa_inspect(type(row)).column_attrs}


def reread(db, model, row_id):
    db.expire_all()
    return db.get(model, row_id)


def reread_snap(db, model, row_id):
    return snap(reread(db, model, row_id))


def counts(db):
    """'nothing written': rows of the four workspace tables, all workspaces."""
    return tuple(
        db.scalar(select(func.count()).select_from(m))
        for m in (Workspace, WorkspaceMember, WorkspaceInvitation, WorkspaceAuditLog)
    )


def x_count(db, x_id):
    return db.scalar(
        select(func.count())
        .select_from(WorkspaceMember)
        .where(WorkspaceMember.id == x_id)
    )


def audit(db, ws_id, action):
    db.expire_all()
    return db.scalars(
        select(WorkspaceAuditLog)
        .where(
            WorkspaceAuditLog.workspace_id == ws_id,
            WorkspaceAuditLog.action == action,
        )
        .order_by(WorkspaceAuditLog.id)
    ).all()


def wsids(r):
    return {p[0].id for p in r}


def ids0(r):
    return {p[0].id for p in r}


def uids(r):
    return {p[0].user_id for p in r}


@contextmanager
def spies(db):
    with (
        patch.object(db, "commit", wraps=db.commit) as cm,
        patch.object(db, "rollback", wraps=db.rollback) as rb,
    ):
        yield cm, rb


@contextmanager
def failing_commit(db):
    with (
        patch.object(db, "commit", side_effect=RuntimeError("boom")),
        patch.object(db, "rollback", wraps=db.rollback) as rb,
    ):
        yield rb


@contextmanager
def failing_refresh(db):
    with patch.object(db, "refresh", side_effect=RuntimeError("boom")):
        yield


@contextmanager
def refresh_trap(db):
    with patch.object(db, "refresh", side_effect=RuntimeError("boom")) as rf:
        yield rf


@contextmanager
def recorder(db):
    """Convention 'recorder' (rev 4): the caller evaluates the When's keyword arguments
    into `kw` first; then expire_all and record every statement of the When."""
    db.expire_all()
    stmts = []
    conn = db.connection()

    def rec(conn_, cursor, statement, params, context, executemany):
        stmts.append(statement)

    event.listen(conn, "before_cursor_execute", rec)
    try:
        yield stmts
    finally:
        event.remove(conn, "before_cursor_execute", rec)


# =========================================================================== #
# _require_active_membership
# =========================================================================== #


# [claude] WSS-AM-01
def test_wss_am_01__active_members_row_is_returned(db, s):
    """WSS-AM-01 — an active member's row is returned.
    Rules: _require_active_membership R1."""
    ma = member(db, s, s.UA, "viewer")
    with clock():
        result = svc._require_active_membership(
            db, workspace_id=s.W1.id, user_id=s.UA.id
        )
    # Then 1
    assert result.id == ma.id
    # Then 2
    assert not db.new and not db.dirty and not db.deleted


# [claude] WSS-AM-02
def test_wss_am_02__unknown_workspace_refused(db, s):
    """WSS-AM-02 — an unknown workspace is refused as "not a member".
    Rules: _require_active_membership R2."""
    member(db, s, s.UA, "viewer")
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc._require_active_membership(db, workspace_id=MISSING, user_id=s.UA.id)
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == NOTMEM


# [claude] WSS-AM-03
def test_wss_am_03__workspace_id_0_refused(db, s):
    """WSS-AM-03 — workspace id 0 is refused.
    Rules: _require_active_membership R2."""
    member(db, s, s.UA, "viewer")
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc._require_active_membership(db, workspace_id=0, user_id=s.UA.id)
    # Then 2
    assert exc.value.detail == NOTMEM


# [claude] WSS-AM-04
def test_wss_am_04__owner_of_w0_not_member_of_w1(db, s):
    """WSS-AM-04 — the owner of W0 (lower id) is not a member of W1.
    Rules: _require_active_membership R2."""
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc._require_active_membership(db, workspace_id=s.W1.id, user_id=s.U0.id)
    # Then 2
    assert exc.value.detail == NOTMEM


# [claude] WSS-AM-05
def test_wss_am_05__owner_of_w2_not_member_of_w1(db, s):
    """WSS-AM-05 — the owner of W2 (higher id) is not a member of W1.
    Rules: _require_active_membership R2."""
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc._require_active_membership(db, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.detail == NOTMEM


# [claude] WSS-AM-06
def test_wss_am_06__inactive_row_in_w1_refused(db, s):
    """WSS-AM-06 — an inactive row in W1 is refused even with active rows in W0 and W2.
    Rules: _require_active_membership R1, R3."""
    member(db, s, s.UA, "owner", ws=s.W0)
    member(db, s, s.UA, "manager", status="inactive")
    member(db, s, s.UA, "owner", ws=s.W2)
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc._require_active_membership(db, workspace_id=s.W1.id, user_id=s.UA.id)
    # Then 2
    assert exc.value.detail == NOTMEM


# [claude] WSS-AM-07
def test_wss_am_07__unknown_user_refused(db, s):
    """WSS-AM-07 — an unknown user is refused.
    Rules: _require_active_membership R2."""
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc._require_active_membership(db, workspace_id=s.W1.id, user_id=MISSING)
    # Then 2
    assert exc.value.detail == NOTMEM


# [claude] WSS-AM-08
def test_wss_am_08__suspended_refused(db, s):
    """WSS-AM-08 — status "suspended" is refused.
    Rules: _require_active_membership R3."""
    member(db, s, s.UA, "viewer", status="suspended")
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc._require_active_membership(db, workspace_id=s.W1.id, user_id=s.UA.id)
    # Then 2
    assert exc.value.detail == NOTMEM


# [claude] WSS-AM-09
def test_wss_am_09__invited_refused(db, s):
    """WSS-AM-09 — status "invited" is refused.
    Rules: _require_active_membership R3."""
    member(db, s, s.UA, "viewer", status="invited")
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc._require_active_membership(db, workspace_id=s.W1.id, user_id=s.UA.id)
    # Then 2
    assert exc.value.detail == NOTMEM


# [claude] WSS-AM-10
def test_wss_am_10__capital_active_refused(db, s):
    """WSS-AM-10 — status "Active" (capital) is refused.
    Rules: _require_active_membership R3."""
    member(db, s, s.UA, "viewer", status="Active")
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc._require_active_membership(db, workspace_id=s.W1.id, user_id=s.UA.id)
    # Then 2
    assert exc.value.detail == NOTMEM


# [claude] WSS-AM-11
def test_wss_am_11__leading_space_active_refused(db, s):
    """WSS-AM-11 — status " active" (leading space) is refused.
    Rules: _require_active_membership R3."""
    member(db, s, s.UA, "viewer", status=" active")
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc._require_active_membership(db, workspace_id=s.W1.id, user_id=s.UA.id)
    # Then 2
    assert exc.value.detail == NOTMEM


# [claude] WSS-AM-12
def test_wss_am_12__any_role_passes_empty_included(db, s):
    """WSS-AM-12 — any role passes, an empty role included.
    Rules: _require_active_membership R4."""
    ma = member(db, s, s.UA, "")
    with clock():
        result = svc._require_active_membership(
            db, workspace_id=s.W1.id, user_id=s.UA.id
        )
    # Then 1
    assert result.id == ma.id


# [claude] WSS-AM-13
def test_wss_am_13__platform_admin_not_member_refused(db, s):
    """WSS-AM-13 — a platform admin who is not a member is refused.
    Rules: _require_active_membership R4."""
    s.UA.is_platform_admin = True
    db.flush()
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc._require_active_membership(db, workspace_id=s.W1.id, user_id=s.UA.id)
    # Then 2
    assert exc.value.detail == NOTMEM


# =========================================================================== #
# _require_owner
# =========================================================================== #


# [claude] WSS-RO-01
def test_wss_ro_01__stored_owner_role_passes(db, s):
    """WSS-RO-01 — an active member whose stored role is "owner" passes, whoever
    owner_user_id names, and gets their own row.
    Rules: _require_owner R1, R2 (D6), R3."""
    ma = member(db, s, s.UA, "owner")
    with clock():
        result = svc._require_owner(db, workspace_id=s.W1.id, user_id=s.UA.id)
    # Then 1
    assert isinstance(result, WorkspaceMember)
    assert result.id == ma.id
    assert result.user_id == s.UA.id
    # Then 2
    assert not db.new and not db.dirty and not db.deleted


# [claude] WSS-RO-02
def test_wss_ro_02__active_manager_refused(db, s):
    """WSS-RO-02 — an active "manager" is refused.
    Rules: _require_owner R2."""
    member(db, s, s.UA, "manager")
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc._require_owner(db, workspace_id=s.W1.id, user_id=s.UA.id)
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == OWNONLY


# [claude] WSS-RO-03
def test_wss_ro_03__capital_owner_refused(db, s):
    """WSS-RO-03 — role "Owner" (capital) is refused.
    Rules: _require_owner R2."""
    member(db, s, s.UA, "Owner")
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc._require_owner(db, workspace_id=s.W1.id, user_id=s.UA.id)
    # Then 2
    assert exc.value.detail == OWNONLY


# [claude] WSS-RO-04
def test_wss_ro_04__owner_with_trailing_space_refused(db, s):
    """WSS-RO-04 — role "owner " (trailing space) is refused.
    Rules: _require_owner R2."""
    member(db, s, s.UA, "owner ")
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc._require_owner(db, workspace_id=s.W1.id, user_id=s.UA.id)
    # Then 2
    assert exc.value.detail == OWNONLY


# [claude] WSS-RO-05
def test_wss_ro_05__owner_of_w0_member_in_w1_refused(db, s):
    """WSS-RO-05 — the owner of W0 is only a "member" in W1 and is refused.
    Rules: _require_owner R2."""
    member(db, s, s.U0, "member")
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc._require_owner(db, workspace_id=s.W1.id, user_id=s.U0.id)
    # Then 2
    assert exc.value.detail == OWNONLY


# [claude] WSS-RO-06
def test_wss_ro_06__owner_of_w2_member_in_w1_refused(db, s):
    """WSS-RO-06 — the owner of W2 is only a "member" in W1 and is refused.
    Rules: _require_owner R2."""
    member(db, s, s.U2, "member")
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc._require_owner(db, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.detail == OWNONLY


# [claude] WSS-RO-07
def test_wss_ro_07__inactive_owner_gets_membership_message(db, s):
    """WSS-RO-07 — an inactive "owner" row gets the membership message first.
    Rules: _require_owner R1."""
    member(db, s, s.UA, "owner", status="inactive")
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc._require_owner(db, workspace_id=s.W1.id, user_id=s.UA.id)
    # Then 2
    assert exc.value.detail == NOTMEM


# [claude] WSS-RO-08
def test_wss_ro_08__owner_user_id_without_row_refused(db, s):
    """WSS-RO-08 — the user named by owner_user_id without a member row is refused.
    Rules: _require_owner R1, R2 (D6)."""
    s.W1.owner_user_id = s.UA.id
    db.flush()
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc._require_owner(db, workspace_id=s.W1.id, user_id=s.UA.id)
    # Then 2
    assert exc.value.detail == NOTMEM


# =========================================================================== #
# list_user_workspaces
# =========================================================================== #


# [claude] WSS-LW-01
def test_wss_lw_01__one_pair_per_active_membership(db, s):
    """WSS-LW-01 — one pair per active membership, every workspace.
    Rules: list_user_workspaces R1, R2."""
    member(db, s, s.UA, "viewer", ws=s.W2)
    member(db, s, s.UA, "manager", ws=s.W0)
    member(db, s, s.UA, "member")
    member(db, s, s.UB, "member")
    with clock():
        result = svc.list_user_workspaces(db, user_id=s.UA.id)
    # Then 1
    assert len(result) == 3
    # Then 2
    assert wsids(result) == {s.W0.id, s.W1.id, s.W2.id}
    # Then 3
    assert all(m.user_id == s.UA.id and m.workspace_id == w.id for (w, m) in result)


# [claude] WSS-LW-02
def test_wss_lw_02__inactive_and_capital_active_left_out(db, s):
    """WSS-LW-02 — inactive and "Active" memberships are left out.
    Rules: list_user_workspaces R1."""
    member(db, s, s.UA, "viewer", status="inactive", ws=s.W0)
    member(db, s, s.UA, "member")
    member(db, s, s.UA, "viewer", status="Active", ws=s.W2)
    with clock():
        result = svc.list_user_workspaces(db, user_id=s.UA.id)
    # Then 1
    assert wsids(result) == {s.W1.id}


# [claude] WSS-LW-03
def test_wss_lw_03__suspended_and_space_active_left_out(db, s):
    """WSS-LW-03 — "suspended" and " active" memberships are left out.
    Rules: list_user_workspaces R1."""
    member(db, s, s.UA, "viewer", status="suspended", ws=s.W0)
    member(db, s, s.UA, "member")
    member(db, s, s.UA, "viewer", status=" active", ws=s.W2)
    with clock():
        result = svc.list_user_workspaces(db, user_id=s.UA.id)
    # Then 1
    assert wsids(result) == {s.W1.id}


# [claude] WSS-LW-04
def test_wss_lw_04__unknown_user_gets_empty_list(db, s):
    """WSS-LW-04 — an unknown user gets an empty list.
    Rules: list_user_workspaces R5."""
    with clock():
        result = svc.list_user_workspaces(db, user_id=MISSING)
    # Then 1
    assert result == []


# [claude] WSS-LW-05
def test_wss_lw_05__only_inactive_membership_gets_empty_list(db, s):
    """WSS-LW-05 — a user with only an inactive membership gets an empty list.
    Rules: list_user_workspaces R5."""
    member(db, s, s.UA, "viewer", status="inactive")
    with clock():
        result = svc.list_user_workspaces(db, user_id=s.UA.id)
    # Then 1
    assert result == []


# [claude] WSS-LW-06
def test_wss_lw_06__read_neither_commits_nor_rolls_back(db, s):
    """WSS-LW-06 — the read neither commits nor rolls back.
    Rules: list_user_workspaces R5; TC6."""
    member(db, s, s.UA, "member")
    commit_point(db)
    x_id = add_x(db, s)
    with spies(db) as (cm, rb), clock():
        result = svc.list_user_workspaces(db, user_id=s.UA.id)
    # Then 1
    assert wsids(result) == {s.W1.id}
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert x_count(db, x_id) == 1
    db.rollback()
    # Then 5
    assert x_count(db, x_id) == 0


# [claude] WSS-LW-07
@pytest.mark.xfail(strict=True, reason=BUG_2252)
def test_wss_lw_07__workspaces_read_together(db, s):
    """WSS-LW-07 — the workspaces are read together.
    Rules: list_user_workspaces R4 [BUG-2252]."""
    w3 = make_workspace(db)
    w4 = make_workspace(db)
    member(db, s, s.UA, "member", ws=s.W0)
    member(db, s, s.UA, "member")
    member(db, s, s.UA, "member", ws=s.W2)
    member(db, s, s.UA, "member", ws=w3)
    member(db, s, s.UA, "member", ws=w4)
    commit_point(db)
    ids = {s.W0.id, s.W1.id, s.W2.id, w3.id, w4.id}
    kw = {"user_id": s.UA.id}
    with recorder(db) as stmts, clock():
        result = svc.list_user_workspaces(db, **kw)
    # Then 1
    assert wsids(result) == ids
    # Then 2
    assert len(stmts) <= 3


# [claude] WSS-LW-08
@pytest.mark.xfail(strict=True, reason=BUG_1400)
def test_wss_lw_08__membership_query_ordered(db, s):
    """WSS-LW-08 — the membership query is ordered (pass-through).
    Rules: list_user_workspaces R2 [BUG-1400]."""
    member(db, s, s.UA, "member")
    commit_point(db)
    w1_id = s.W1.id
    kw = {"user_id": s.UA.id}
    with recorder(db) as stmts, clock():
        result = svc.list_user_workspaces(db, **kw)
    # Then 1
    assert wsids(result) == {w1_id}
    # Then 2
    assert any("workspace_members" in st and "ORDER BY" in st.upper() for st in stmts)


# =========================================================================== #
# create_workspace
# =========================================================================== #


# [claude] WSS-C-01
def test_wss_c_01__created_on_default_plan_committed(db, s):
    """WSS-C-01 — the workspace is created on the default plan, committed and re-read.
    Rules: create_workspace R1; TC1, TC2."""
    pd = mk_pd(db, s)
    pd_id, ua_id = pd.id, s.UA.id
    commit_point(db)
    with clock():
        result = svc.create_workspace(
            db,
            workspace_data=WorkspaceCreate(name="Acme Tools", slug=s.SL),
            owner_user_id=ua_id,
        )
    # Then 1
    assert isinstance(result, Workspace)
    # Then 2
    assert result.created_at is not None
    assert not (
        {c.key for c in sa_inspect(result).mapper.column_attrs}
        & sa_inspect(result).expired_attributes
    )
    result_id = result.id
    db.rollback()
    # Then 3
    ws = db.scalars(select(Workspace).where(Workspace.slug == s.SL)).one()
    assert ws.name == "Acme Tools"
    assert ws.owner_user_id == ua_id
    assert ws.subscription_plan_id == pd_id
    # Then 4
    m = db.scalars(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == result_id, WorkspaceMember.user_id == ua_id
        )
    ).one()
    assert m.role == "owner"
    assert m.status == "active"
    # Then 5
    n = db.scalar(
        select(func.count())
        .select_from(WorkspaceAuditLog)
        .where(
            WorkspaceAuditLog.workspace_id == result_id,
            WorkspaceAuditLog.action == "workspace_created",
        )
    )
    assert n == 1


# [claude] WSS-C-02
def test_wss_c_02__plan_and_owner_position_from_body(db, s):
    """WSS-C-02 — plan id and owner position come from the request body.
    Rules: create_workspace R1 (manager R1, pending OQ-16)."""
    mk_pd(db, s)
    px = mk_px(db, s)
    px_id, ua_id = px.id, s.UA.id
    commit_point(db)
    with clock():
        result = svc.create_workspace(
            db,
            workspace_data=WorkspaceCreate(
                name="Acme Tools",
                slug=s.SL,
                subscription_plan_id=px_id,
                owner_position="CEO",
            ),
            owner_user_id=ua_id,
        )
    # Then 1
    assert result.subscription_plan_id == px_id
    result_id = result.id
    db.rollback()
    # Then 2
    m = db.scalars(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == result_id, WorkspaceMember.user_id == ua_id
        )
    ).one()
    assert m.position == "CEO"


# [claude] WSS-C-03
def test_wss_c_03__no_default_plan_400(db, s):
    """WSS-C-03 — no default plan: 400 with the manager's text, everything pending discarded.
    Rules: create_workspace R2, Errors row 1; TX1, TC3."""
    commit_point(db)
    before = counts(db)
    x_id = add_x(db, s)
    # Then 1
    with pytest.raises(ValidationError) as exc:
        with clock():
            svc.create_workspace(
                db,
                workspace_data=WorkspaceCreate(name="Acme Tools", slug=s.SL),
                owner_user_id=s.UA.id,
            )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "No default subscription plan found"
    # Then 4
    assert isinstance(exc.value.__context__, ValueError)
    # Then 5
    assert x_count(db, x_id) == 0
    # Then 6
    assert counts(db) == before


# [claude] WSS-C-04
def test_wss_c_04__unknown_plan_id_400(db, s):
    """WSS-C-04 — an unknown plan id: 400 "Invalid subscription plan".
    Rules: create_workspace R2; TX1."""
    mk_pd(db, s)
    commit_point(db)
    before = counts(db)
    # Then 1
    with pytest.raises(ValidationError) as exc:
        with clock():
            svc.create_workspace(
                db,
                workspace_data=WorkspaceCreate(
                    name="Acme Tools", slug=s.SL, subscription_plan_id=MISSING
                ),
                owner_user_id=s.UA.id,
            )
    # Then 2
    assert exc.value.detail == "Invalid subscription plan"
    # Then 3
    assert counts(db) == before


# [claude] WSS-C-05
def test_wss_c_05__taken_slug_400(db, s):
    """WSS-C-05 — a taken slug: 400 with the slug in the text.
    Rules: create_workspace R2; TX1."""
    mk_pd(db, s)
    slug = s.W1.slug
    commit_point(db)
    before = counts(db)
    # Then 1
    with pytest.raises(ValidationError) as exc:
        with clock():
            svc.create_workspace(
                db,
                workspace_data=WorkspaceCreate(name="Acme Tools", slug=slug),
                owner_user_id=s.UA.id,
            )
    # Then 2
    assert (
        exc.value.detail
        == f"Workspace slug '{slug}' is already taken. Please choose a different name."
    )
    # Then 3
    assert counts(db) == before


# [claude] WSS-C-06
def test_wss_c_06__unknown_owner_integrity_error(db, s):
    """WSS-C-06 — an unknown owner: the IntegrityError passes unchanged, nothing saved.
    Rules: create_workspace R3; TC3."""
    mk_pd(db, s)
    commit_point(db)
    before = counts(db)
    x_id = add_x(db, s)
    # Then 1
    with pytest.raises(IntegrityError):
        with clock():
            svc.create_workspace(
                db,
                workspace_data=WorkspaceCreate(name="Acme Tools", slug=s.SL),
                owner_user_id=MISSING,
            )
    # Then 2
    assert x_count(db, x_id) == 0
    # Then 3
    assert counts(db) == before
    # Then 4
    assert db.execute(select(func.count()).select_from(Workspace)).scalar() >= 3


# [claude] WSS-C-07
def test_wss_c_07__failing_commit_rolls_back(db, s):
    """WSS-C-07 — a failing commit rolls back, nothing saved.
    Rules: create_workspace R3; TC4."""
    mk_pd(db, s)
    commit_point(db)
    before = counts(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb, clock():
            svc.create_workspace(
                db,
                workspace_data=WorkspaceCreate(name="Acme Tools", slug=s.SL),
                owner_user_id=s.UA.id,
            )
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert counts(db) == before


# [claude] WSS-C-08
def test_wss_c_08__failing_refresh_leaves_workspace_saved(db, s):
    """WSS-C-08 — a failing re-read leaves the workspace saved.
    Rules: create_workspace R3; TC5."""
    mk_pd(db, s)
    commit_point(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db), clock():
            svc.create_workspace(
                db,
                workspace_data=WorkspaceCreate(name="Acme Tools", slug=s.SL),
                owner_user_id=s.UA.id,
            )
    assert str(exc.value) == "boom"
    db.rollback()
    # Then 2
    n = db.scalar(
        select(func.count()).select_from(Workspace).where(Workspace.slug == s.SL)
    )
    assert n == 1


# [claude] WSS-C-09
@pytest.mark.xfail(strict=True, reason=BUG_1404)
def test_wss_c_09__ip_and_user_agent_reach_audit(db, s):
    """WSS-C-09 — IP and user agent reach the workspace_created audit row.
    Rules: create_workspace R4 [BUG-1404]."""
    mk_pd(db, s)
    commit_point(db)
    with clock():
        result = svc.create_workspace(
            db,
            workspace_data=WorkspaceCreate(name="Acme Tools", slug=s.SL),
            owner_user_id=s.UA.id,
            ip_address="203.0.113.7",
            user_agent="Mozilla/5.0 Test",
        )
    # Then 1
    assert isinstance(result, Workspace)
    result_id = result.id
    # Then 2
    rows = audit(db, result_id, "workspace_created")
    assert len(rows) == 1
    # Then 3
    assert rows[0].ip_address == "203.0.113.7"
    assert rows[0].user_agent == "Mozilla/5.0 Test"


# [claude] WSS-C-10
@pytest.mark.xfail(strict=True, reason=BUG_1980)
def test_wss_c_10__name_stored_trimmed(db, s):
    """WSS-C-10 — the name is stored trimmed (pass-through).
    Rules: create_workspace R1 (manager R12) [BUG-1980]."""
    mk_pd(db, s)
    commit_point(db)
    with clock():
        result = svc.create_workspace(
            db,
            workspace_data=WorkspaceCreate(name=" Acme ", slug=s.SL),
            owner_user_id=s.UA.id,
        )
    # Then 1
    assert isinstance(result, Workspace)
    db.rollback()
    # Then 2
    ws = db.scalars(select(Workspace).where(Workspace.slug == s.SL)).one()
    assert ws.name == "Acme"


# [claude] WSS-C-11
@pytest.mark.xfail(strict=True, reason=BUG_2256)
def test_wss_c_11__owner_position_256_refused_by_schema(s):
    """WSS-C-11 — an owner position of 256 characters is refused by the schema.
    Rules: update_workspace R5a [BUG-2256] (WorkspaceCreate.owner_position)."""
    # Then 1
    with pytest.raises(PydanticValidationError):
        WorkspaceCreate(name="Acme Tools", slug=s.SL, owner_position="p" * 256)


# [claude] WSS-C-12
def test_wss_c_12__owner_position_255_accepted_by_schema(s):
    """WSS-C-12 — an owner position of 255 characters is accepted by the schema.
    Rules: update_workspace R5a (WorkspaceCreate.owner_position)."""
    result = WorkspaceCreate(name="Acme Tools", slug=s.SL, owner_position="p" * 255)
    # Then 1
    assert result.owner_position == "p" * 255


# [claude] WSS-C-13
@pytest.mark.xfail(strict=True, reason=BUG_2256)
def test_wss_c_13__billing_email_256_refused_by_create_schema(s):
    """WSS-C-13 — a billing email of 256 characters is refused by WorkspaceCreate.
    Rules: update_workspace R5a [BUG-2256] (WorkspaceCreate.billing_email)."""
    # Then 1
    with pytest.raises(PydanticValidationError):
        WorkspaceCreate(name="Acme Tools", slug=s.SL, billing_email="a" * 256)


# [claude] WSS-C-14
def test_wss_c_14__billing_email_255_accepted_by_create_schema(s):
    """WSS-C-14 — a billing email of 255 characters is accepted by WorkspaceCreate.
    Rules: update_workspace R5a (WorkspaceCreate.billing_email)."""
    result = WorkspaceCreate(name="Acme Tools", slug=s.SL, billing_email="a" * 255)
    # Then 1
    assert result.billing_email == "a" * 255


# =========================================================================== #
# get_workspace_with_plan
# =========================================================================== #


# [claude] WSS-G-01
def test_wss_g_01__member_gets_workspace_and_plan(db, s):
    """WSS-G-01 — a member gets the workspace and its plan.
    Rules: get_workspace_with_plan R1, R2."""
    member(db, s, s.UA, "viewer")
    with clock():
        result = svc.get_workspace_with_plan(
            db, workspace_id=s.W1.id, requesting_user_id=s.UA.id
        )
    # Then 1
    assert result[0].id == s.W1.id
    # Then 2
    assert result[1].id == s.PL1.id


# [claude] WSS-G-02
def test_wss_g_02__inactive_plan_returned_as_is(db, s):
    """WSS-G-02 — an inactive plan is returned as it is.
    Rules: get_workspace_with_plan R2."""
    s.PL1.is_active = False
    db.flush()
    member(db, s, s.UA, "viewer")
    with clock():
        result = svc.get_workspace_with_plan(
            db, workspace_id=s.W1.id, requesting_user_id=s.UA.id
        )
    # Then 1
    assert result[1].id == s.PL1.id
    # Then 2
    assert result[1].is_active is False


# [claude] WSS-G-03
def test_wss_g_03__unknown_id_answers_403(db, s):
    """WSS-G-03 — an unknown id answers 403, not 404.
    Rules: get_workspace_with_plan R1, R3."""
    member(db, s, s.UA, "viewer")
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc.get_workspace_with_plan(
                db, workspace_id=MISSING, requesting_user_id=s.UA.id
            )
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == NOTMEM


# [claude] WSS-G-04
def test_wss_g_04__owner_of_w2_cannot_read_w1(db, s):
    """WSS-G-04 — the owner of W2 cannot read W1.
    Rules: get_workspace_with_plan R1."""
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc.get_workspace_with_plan(
                db, workspace_id=s.W1.id, requesting_user_id=s.U2.id
            )
    # Then 2
    assert exc.value.detail == NOTMEM


# [claude] WSS-G-05
def test_wss_g_05__read_neither_commits_nor_rolls_back(db, s):
    """WSS-G-05 — the read neither commits nor rolls back.
    Rules: get_workspace_with_plan R4; TC6."""
    member(db, s, s.UA, "viewer")
    commit_point(db)
    x_id = add_x(db, s)
    w1_id, ua_id = s.W1.id, s.UA.id
    with spies(db) as (cm, rb), clock():
        result = svc.get_workspace_with_plan(
            db, workspace_id=w1_id, requesting_user_id=ua_id
        )
    # Then 1
    assert result[0].id == w1_id
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert x_count(db, x_id) == 1
    db.rollback()
    # Then 5
    assert x_count(db, x_id) == 0


# =========================================================================== #
# update_workspace
# =========================================================================== #


# [claude] WSS-U-01
def test_wss_u_01__owner_renames_workspace(db, s):
    """WSS-U-01 — the owner renames the workspace; committed, re-read, nothing else changes.
    Rules: update_workspace R2, R3, R7; TC1, TC2."""
    s.W1.billing_email = "pay@acme.com"
    s.W1.settings = {"timezone": "Asia/Dhaka"}
    db.flush()
    commit_point(db)
    w1_id, pl1_id, uo_id = s.W1.id, s.PL1.id, s.UO.id
    with clock():
        result = svc.update_workspace(
            db,
            workspace_id=w1_id,
            current_user_id=uo_id,
            workspace_update=WorkspaceUpdate(name="Acme Renamed"),
        )
    # Then 1
    assert result.id == w1_id
    assert result.name == "Acme Renamed"
    # Then 2
    assert result.updated_at is not None
    assert not (
        {c.key for c in sa_inspect(result).mapper.column_attrs}
        & sa_inspect(result).expired_attributes
    )
    db.rollback()
    ws = db.scalars(select(Workspace).where(Workspace.id == w1_id)).one()
    # Then 3
    assert ws.name == "Acme Renamed"
    # Then 4
    assert ws.billing_email == "pay@acme.com"
    assert ws.settings == {"timezone": "Asia/Dhaka"}
    # Then 5
    assert ws.subscription_plan_id == pl1_id
    assert ws.owner_user_id == uo_id


# [claude] WSS-U-02
def test_wss_u_02__null_name_kept_billing_email_any_string(db, s):
    """WSS-U-02 — name: null leaves the name; billing email is any string.
    Rules: update_workspace R3, R5."""
    name = s.W1.name
    commit_point(db)
    w1_id = s.W1.id
    with clock():
        result = svc.update_workspace(
            db,
            workspace_id=w1_id,
            current_user_id=s.UO.id,
            workspace_update=WorkspaceUpdate(name=None, billing_email="not an email"),
        )
    # Then 1
    assert result.billing_email == "not an email"
    db.rollback()
    # Then 2
    ws = db.scalars(select(Workspace).where(Workspace.id == w1_id)).one()
    assert ws.name == name
    assert ws.billing_email == "not an email"


# [claude] WSS-U-03
def test_wss_u_03__settings_replace_stored_object(db, s):
    """WSS-U-03 — settings replace the stored object whole.
    Rules: update_workspace R5 (D9)."""
    s.W1.settings = {"timezone": "Asia/Dhaka"}
    db.flush()
    commit_point(db)
    w1_id = s.W1.id
    with clock():
        result = svc.update_workspace(
            db,
            workspace_id=w1_id,
            current_user_id=s.UO.id,
            workspace_update=WorkspaceUpdate(settings={"foo": 1}),
        )
    # Then 1
    assert result.settings == {"foo": 1}
    db.rollback()
    # Then 2
    ws = db.scalars(select(Workspace).where(Workspace.id == w1_id)).one()
    assert ws.settings == {"foo": 1}


# [claude] WSS-U-04
def test_wss_u_04__invalid_iana_timezone_refused_by_schema():
    """WSS-U-04 — an invalid IANA timezone is refused by the schema.
    Rules: update_workspace R5."""
    # Then 1
    with pytest.raises(PydanticValidationError) as exc:
        WorkspaceUpdate(settings={"timezone": "Mars/Base"})
    # Then 2
    assert "Invalid IANA timezone in workspace settings" in str(exc.value)


# [claude] WSS-U-05
def test_wss_u_05__blank_timezone_passes_schema():
    """WSS-U-05 — a blank timezone passes the schema.
    Rules: update_workspace R5."""
    result = WorkspaceUpdate(settings={"timezone": ""})
    # Then 1
    assert result.settings == {"timezone": ""}


# [claude] WSS-U-06
def test_wss_u_06__name_256_refused_by_schema():
    """WSS-U-06 — a 256-character name is refused by the schema.
    Rules: update_workspace R4."""
    # Then 1
    with pytest.raises(PydanticValidationError):
        WorkspaceUpdate(name="a" * 256)


# [claude] WSS-U-07
def test_wss_u_07__name_255_stored(db, s):
    """WSS-U-07 — a 255-character name is stored.
    Rules: update_workspace R4."""
    commit_point(db)
    w1_id = s.W1.id
    with clock():
        result = svc.update_workspace(
            db,
            workspace_id=w1_id,
            current_user_id=s.UO.id,
            workspace_update=WorkspaceUpdate(name="a" * 255),
        )
    # Then 1
    assert result.name == "a" * 255
    db.rollback()
    # Then 2
    ws = db.scalars(select(Workspace).where(Workspace.id == w1_id)).one()
    assert ws.name == "a" * 255


# [claude] WSS-U-08
def test_wss_u_08__empty_name_refused_by_schema():
    """WSS-U-08 — an empty name is refused by the schema.
    Rules: update_workspace R4."""
    # Then 1
    with pytest.raises(PydanticValidationError):
        WorkspaceUpdate(name="")


# [claude] WSS-U-09
@pytest.mark.xfail(strict=True, reason=BUG_1980)
def test_wss_u_09__name_stored_trimmed(db, s):
    """WSS-U-09 — the name is stored trimmed.
    Rules: update_workspace R4 [BUG-1980]."""
    commit_point(db)
    w1_id = s.W1.id
    with clock():
        result = svc.update_workspace(
            db,
            workspace_id=w1_id,
            current_user_id=s.UO.id,
            workspace_update=WorkspaceUpdate(name="  Acme  "),
        )
    # Then 1
    assert result.id == w1_id
    db.rollback()
    # Then 2
    ws = db.scalars(select(Workspace).where(Workspace.id == w1_id)).one()
    assert ws.name == "Acme"


# [claude] WSS-U-10
@pytest.mark.xfail(strict=True, reason=BUG_1980)
def test_wss_u_10__whitespace_only_name_refused_by_schema():
    """WSS-U-10 — a whitespace-only name is refused by the schema.
    Rules: update_workspace R4 [BUG-1980]."""
    # Then 1
    with pytest.raises(PydanticValidationError):
        WorkspaceUpdate(name="   ")


# [claude] WSS-U-11
def test_wss_u_11__active_non_owner_refused(db, s):
    """WSS-U-11 — an active member who is not the owner is refused; pending changes stay pending.
    Rules: update_workspace R2, Errors row 3; TX2."""
    member(db, s, s.UA, "manager")
    commit_point(db)
    before = counts(db)
    w1_before = snap(s.W1)
    x_id = add_x(db, s)
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc.update_workspace(
                db,
                workspace_id=s.W1.id,
                current_user_id=s.UA.id,
                workspace_update=WorkspaceUpdate(name="Hacked"),
            )
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == "Only workspace owner can update workspace"
    # Then 4
    assert not db.dirty and not db.new and not db.deleted
    # Then 5
    assert x_count(db, x_id) == 1
    # Then 6
    assert reread_snap(db, Workspace, w1_before["id"]) == w1_before
    db.rollback()
    # Then 7
    assert x_count(db, x_id) == 0
    # Then 8
    assert counts(db) == before


# [claude] WSS-U-12
def test_wss_u_12__stored_owner_not_owner_user_id_refused(db, s):
    """WSS-U-12 — a member whose stored role is "owner" but who is not owner_user_id is refused.
    Rules: update_workspace R2 (D6)."""
    member(db, s, s.UA, "owner")
    commit_point(db)
    w1_before = snap(s.W1)
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc.update_workspace(
                db,
                workspace_id=s.W1.id,
                current_user_id=s.UA.id,
                workspace_update=WorkspaceUpdate(name="Hacked"),
            )
    # Then 2
    assert exc.value.detail == "Only workspace owner can update workspace"
    # Then 3
    assert not db.dirty and not db.new
    # Then 4
    assert reread_snap(db, Workspace, w1_before["id"]) == w1_before


# [claude] WSS-U-13
@pytest.mark.xfail(strict=True, reason=BUG_2250)
def test_wss_u_13__unknown_workspace_not_a_member(db, s):
    """WSS-U-13 — an unknown workspace answers "not a member".
    Rules: update_workspace R1 [BUG-2250], Errors rows 1-2."""
    commit_point(db)
    before = counts(db)
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc.update_workspace(
                db,
                workspace_id=MISSING,
                current_user_id=s.UO.id,
                workspace_update=WorkspaceUpdate(name="Hacked"),
            )
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == NOTMEM
    # Then 4
    assert not db.dirty and not db.new
    # Then 5
    assert counts(db) == before


# [claude] WSS-U-14
@pytest.mark.xfail(strict=True, reason=BUG_2250)
def test_wss_u_14__workspace_id_0_not_a_member(db, s):
    """WSS-U-14 — workspace id 0 answers "not a member".
    Rules: update_workspace R1 [BUG-2250]."""
    commit_point(db)
    before = counts(db)
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc.update_workspace(
                db,
                workspace_id=0,
                current_user_id=s.UO.id,
                workspace_update=WorkspaceUpdate(name="Hacked"),
            )
    # Then 2
    assert exc.value.detail == NOTMEM
    # Then 3
    assert not db.dirty and not db.new
    # Then 4
    assert counts(db) == before


# [claude] WSS-U-15
@pytest.mark.xfail(strict=True, reason=BUG_2250)
def test_wss_u_15__owner_of_w0_not_a_member_on_w1(db, s):
    """WSS-U-15 — the owner of W0 (lower id) gets "not a member" on W1.
    Rules: update_workspace R1 [BUG-2250]."""
    commit_point(db)
    w1_before = snap(s.W1)
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc.update_workspace(
                db,
                workspace_id=s.W1.id,
                current_user_id=s.U0.id,
                workspace_update=WorkspaceUpdate(name="Hacked"),
            )
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == NOTMEM
    # Then 4
    assert not db.dirty and not db.new
    # Then 5
    assert reread_snap(db, Workspace, w1_before["id"]) == w1_before


# [claude] WSS-U-16
@pytest.mark.xfail(strict=True, reason=BUG_2250)
def test_wss_u_16__owner_of_w2_not_a_member_on_w1(db, s):
    """WSS-U-16 — the owner of W2 (higher id) gets "not a member" on W1.
    Rules: update_workspace R1 [BUG-2250]."""
    commit_point(db)
    w1_before = snap(s.W1)
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc.update_workspace(
                db,
                workspace_id=s.W1.id,
                current_user_id=s.U2.id,
                workspace_update=WorkspaceUpdate(name="Hacked"),
            )
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == NOTMEM
    # Then 4
    assert not db.dirty and not db.new
    # Then 5
    assert reread_snap(db, Workspace, w1_before["id"]) == w1_before


# [claude] WSS-U-17
@pytest.mark.xfail(strict=True, reason=BUG_2250)
def test_wss_u_17__no_membership_anywhere_not_a_member(db, s):
    """WSS-U-17 — a person with no membership anywhere gets "not a member".
    Rules: update_workspace R1 [BUG-2250]."""
    commit_point(db)
    w1_before = snap(s.W1)
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc.update_workspace(
                db,
                workspace_id=s.W1.id,
                current_user_id=s.UB.id,
                workspace_update=WorkspaceUpdate(name="Hacked"),
            )
    # Then 2
    assert exc.value.detail == NOTMEM
    # Then 3
    assert not db.dirty and not db.new
    # Then 4
    assert reread_snap(db, Workspace, w1_before["id"]) == w1_before


# [claude] WSS-U-18
@pytest.mark.xfail(strict=True, reason=BUG_2250)
def test_wss_u_18__owner_user_id_without_row_refused(db, s):
    """WSS-U-18 — owner_user_id without a member row is refused.
    Rules: update_workspace R1 [BUG-2250]."""
    s.W1.owner_user_id = s.UA.id
    db.flush()
    commit_point(db)
    before = counts(db)
    w1_before = snap(s.W1)
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc.update_workspace(
                db,
                workspace_id=s.W1.id,
                current_user_id=s.UA.id,
                workspace_update=WorkspaceUpdate(name="Hacked"),
            )
    # Then 2
    assert exc.value.detail == NOTMEM
    # Then 3
    assert not db.dirty and not db.new
    # Then 4
    assert reread_snap(db, Workspace, w1_before["id"]) == w1_before
    # Then 5
    assert counts(db) == before


# [claude] WSS-U-19
@pytest.mark.xfail(strict=True, reason=BUG_2250)
def test_wss_u_19__owner_user_id_with_inactive_row_refused(db, s):
    """WSS-U-19 — owner_user_id with an inactive row is refused.
    Rules: update_workspace R1 [BUG-2250]."""
    s.W1.owner_user_id = s.UA.id
    db.flush()
    member(db, s, s.UA, "owner", status="inactive")
    commit_point(db)
    w1_before = snap(s.W1)
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc.update_workspace(
                db,
                workspace_id=s.W1.id,
                current_user_id=s.UA.id,
                workspace_update=WorkspaceUpdate(name="Hacked"),
            )
    # Then 2
    assert exc.value.detail == NOTMEM
    # Then 3
    assert not db.dirty and not db.new
    # Then 4
    assert reread_snap(db, Workspace, w1_before["id"]) == w1_before


# [claude] WSS-U-20
@pytest.mark.xfail(strict=True, reason=BUG_2250)
def test_wss_u_20__owner_user_id_with_suspended_row_refused(db, s):
    """WSS-U-20 — owner_user_id with a suspended row is refused.
    Rules: update_workspace R1 [BUG-2250]."""
    s.W1.owner_user_id = s.UA.id
    db.flush()
    member(db, s, s.UA, "owner", status="suspended")
    commit_point(db)
    w1_before = snap(s.W1)
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc.update_workspace(
                db,
                workspace_id=s.W1.id,
                current_user_id=s.UA.id,
                workspace_update=WorkspaceUpdate(name="Hacked"),
            )
    # Then 2
    assert exc.value.detail == NOTMEM
    # Then 3
    assert not db.dirty and not db.new
    # Then 4
    assert reread_snap(db, Workspace, w1_before["id"]) == w1_before


# [claude] WSS-U-21
@pytest.mark.xfail(strict=True, reason=BUG_2253)
def test_wss_u_21__name_change_writes_audit_row(db, s):
    """WSS-U-21 — a name change writes one workspace_updated audit row.
    Rules: update_workspace R6 [BUG-2253]."""
    commit_point(db)
    w1_id, uo_id = s.W1.id, s.UO.id
    with clock():
        result = svc.update_workspace(
            db,
            workspace_id=w1_id,
            current_user_id=uo_id,
            workspace_update=WorkspaceUpdate(name="Acme Renamed"),
        )
    # Then 1
    assert result.name == "Acme Renamed"
    # Then 2
    rows = audit(db, w1_id, "workspace_updated")
    assert len(rows) == 1
    # Then 3
    assert rows[0].user_id == uo_id
    assert rows[0].metadata_json == {"fields": ["name"]}


# [claude] WSS-U-22
@pytest.mark.xfail(strict=True, reason=BUG_2253)
def test_wss_u_22__audit_lists_every_changed_field_in_order(db, s):
    """WSS-U-22 — the audit row lists every changed field in the order name, billing_email,
    settings.
    Rules: update_workspace R6 [BUG-2253]."""
    s.W1.settings = {"timezone": "Asia/Dhaka"}
    db.flush()
    commit_point(db)
    w1_id = s.W1.id
    with clock():
        result = svc.update_workspace(
            db,
            workspace_id=w1_id,
            current_user_id=s.UO.id,
            workspace_update=WorkspaceUpdate(
                settings={"timezone": "UTC"},
                billing_email="pay@acme.com",
                name="Acme Renamed",
            ),
        )
    # Then 1
    assert result.name == "Acme Renamed"
    # Then 2
    rows = audit(db, w1_id, "workspace_updated")
    assert len(rows) == 1
    # Then 3
    assert rows[0].metadata_json == {"fields": ["name", "billing_email", "settings"]}


# [claude] WSS-U-23
def test_wss_u_23__same_value_no_audit_updated_at_kept(db, s):
    """WSS-U-23 — the same value again: no audit row, updated_at kept.
    Rules: update_workspace R6, R7."""
    name = s.W1.name
    commit_point(db)
    t = s.W1.updated_at
    w1_id = s.W1.id
    with clock():
        result = svc.update_workspace(
            db,
            workspace_id=w1_id,
            current_user_id=s.UO.id,
            workspace_update=WorkspaceUpdate(name=name),
        )
    # Then 1
    assert result.name == name
    # Then 2
    assert len(audit(db, w1_id, "workspace_updated")) == 0
    db.rollback()
    # Then 3
    ws = db.scalars(select(Workspace).where(Workspace.id == w1_id)).one()
    assert ws.updated_at == t


# [claude] WSS-U-24
@pytest.mark.xfail(strict=True, reason=BUG_2253)
def test_wss_u_24__audit_row_carries_ip_and_user_agent(db, s):
    """WSS-U-24 — the workspace_updated row carries IP and user agent.
    Rules: update_workspace R6 [BUG-2253] [BUG-1404]."""
    commit_point(db)
    w1_id = s.W1.id
    with clock():
        result = svc.update_workspace(
            db,
            workspace_id=w1_id,
            current_user_id=s.UO.id,
            workspace_update=WorkspaceUpdate(name="Acme Renamed"),
            ip_address="203.0.113.7",
            user_agent="Mozilla/5.0 Test",
        )
    # Then 1
    assert result.name == "Acme Renamed"
    # Then 2
    rows = audit(db, w1_id, "workspace_updated")
    assert len(rows) == 1
    # Then 3
    assert rows[0].ip_address == "203.0.113.7"
    assert rows[0].user_agent == "Mozilla/5.0 Test"


# [claude] WSS-U-25
def test_wss_u_25__failing_commit_rolls_back(db, s):
    """WSS-U-25 — a failing commit rolls back, the name is unchanged.
    Rules: update_workspace R7; TC4."""
    commit_point(db)
    w1_before = snap(s.W1)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb, clock():
            svc.update_workspace(
                db,
                workspace_id=s.W1.id,
                current_user_id=s.UO.id,
                workspace_update=WorkspaceUpdate(name="Acme Renamed"),
            )
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert reread_snap(db, Workspace, w1_before["id"]) == w1_before


# [claude] WSS-U-26
def test_wss_u_26__failing_refresh_leaves_change_saved(db, s):
    """WSS-U-26 — a failing re-read leaves the change saved.
    Rules: update_workspace R7; TC5."""
    commit_point(db)
    w1_id = s.W1.id
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db), clock():
            svc.update_workspace(
                db,
                workspace_id=w1_id,
                current_user_id=s.UO.id,
                workspace_update=WorkspaceUpdate(name="Acme Renamed"),
            )
    assert str(exc.value) == "boom"
    db.rollback()
    # Then 2
    ws = db.scalars(select(Workspace).where(Workspace.id == w1_id)).one()
    assert ws.name == "Acme Renamed"


# [claude] WSS-U-27
def test_wss_u_27__error_inside_try_rolls_back(db, s):
    """WSS-U-27 — an error inside the try rolls back and discards pending changes.
    Rules: update_workspace R7; TC3."""
    commit_point(db)
    before = counts(db)
    w1_before = snap(s.W1)
    x_id = add_x(db, s)
    # Then 1
    with pytest.raises(DataError) as exc:
        with clock():
            svc.update_workspace(
                db,
                workspace_id=s.W1.id,
                current_user_id=s.UO.id,
                workspace_update=WorkspaceUpdate.model_construct(
                    billing_email="a" * 256
                ),
            )
    # Then 2
    assert exc.value.orig.pgcode == "22001"
    # Then 3
    assert x_count(db, x_id) == 0
    # Then 4
    assert reread_snap(db, Workspace, w1_before["id"]) == w1_before
    # Then 5
    assert counts(db) == before
    # Then 6
    assert db.execute(select(func.count()).select_from(Workspace)).scalar() >= 3


# [claude] WSS-U-28
@pytest.mark.xfail(strict=True, reason=BUG_2256)
def test_wss_u_28__billing_email_256_refused_by_schema():
    """WSS-U-28 — a billing email of 256 characters is refused by the schema.
    Rules: update_workspace R5a [BUG-2256]."""
    # Then 1
    with pytest.raises(PydanticValidationError):
        WorkspaceUpdate(billing_email="a" * 256)


# [claude] WSS-U-29
def test_wss_u_29__billing_email_255_accepted_by_schema():
    """WSS-U-29 — a billing email of 255 characters is accepted by the schema.
    Rules: update_workspace R5a."""
    result = WorkspaceUpdate(billing_email="a" * 255)
    # Then 1
    assert result.billing_email == "a" * 255


# =========================================================================== #
# list_members
# =========================================================================== #


# [claude] WSS-LM-01
def test_wss_lm_01__ground_team_lists_active_members(db, s):
    """WSS-LM-01 — a ground-team member lists the active members with their profiles.
    Rules: list_members R1, R2, R3, R4."""
    member(db, s, s.UA, "ground-team")
    member(db, s, s.UB, "member", status="inactive")
    member(db, s, s.UC, "viewer", status="suspended")
    member(db, s, s.UB, "member", ws=s.W0)
    member(db, s, s.UC, "member", ws=s.W2)
    with clock():
        result = svc.list_members(db, workspace_id=s.W1.id, requesting_user_id=s.UA.id)
    # Then 1
    assert uids(result) == {s.UO.id, s.UA.id}
    # Then 2
    assert all(m.workspace_id == s.W1.id for (m, p) in result)
    # Then 3
    assert all(p.id == m.user_id for (m, p) in result)


# [claude] WSS-LM-02
def test_wss_lm_02__include_inactive_returns_every_row(db, s):
    """WSS-LM-02 — include_inactive returns every row of the workspace.
    Rules: list_members R3."""
    member(db, s, s.UA, "ground-team")
    member(db, s, s.UB, "member", status="inactive")
    member(db, s, s.UC, "viewer", status="suspended")
    member(db, s, s.UQ, "member", ws=s.W0)
    member(db, s, s.UQ, "member", ws=s.W2)
    with clock():
        result = svc.list_members(
            db, workspace_id=s.W1.id, requesting_user_id=s.UA.id, include_inactive=True
        )
    # Then 1
    assert uids(result) == {s.UO.id, s.UA.id, s.UB.id, s.UC.id}


# [claude] WSS-LM-03
def test_wss_lm_03__capital_active_not_active_by_default(db, s):
    """WSS-LM-03 — "Active" is not "active" by default.
    Rules: list_members R3."""
    member(db, s, s.UA, "member")
    member(db, s, s.UB, "member", status="Active")
    with clock():
        result = svc.list_members(db, workspace_id=s.W1.id, requesting_user_id=s.UA.id)
    # Then 1
    assert uids(result) == {s.UO.id, s.UA.id}


# [claude] WSS-LM-04
def test_wss_lm_04__owner_of_w0_cannot_list_w1(db, s):
    """WSS-LM-04 — the owner of W0 cannot list W1.
    Rules: list_members R1."""
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc.list_members(db, workspace_id=s.W1.id, requesting_user_id=s.U0.id)
    # Then 2
    assert exc.value.detail == NOTMEM


# [claude] WSS-LM-05
def test_wss_lm_05__inactive_caller_refused(db, s):
    """WSS-LM-05 — an inactive caller is refused, also with include_inactive.
    Rules: list_members R1."""
    member(db, s, s.UA, "manager", status="inactive")
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc.list_members(
                db,
                workspace_id=s.W1.id,
                requesting_user_id=s.UA.id,
                include_inactive=True,
            )
    # Then 2
    assert exc.value.detail == NOTMEM


# [claude] WSS-LM-06
def test_wss_lm_06__read_neither_commits_nor_rolls_back(db, s):
    """WSS-LM-06 — the read neither commits nor rolls back.
    Rules: list_members R6; TC6."""
    member(db, s, s.UA, "member")
    commit_point(db)
    x_id = add_x(db, s)
    w1_id, ua_id, uo_id = s.W1.id, s.UA.id, s.UO.id
    with spies(db) as (cm, rb), clock():
        result = svc.list_members(db, workspace_id=w1_id, requesting_user_id=ua_id)
    # Then 1
    assert uids(result) == {uo_id, ua_id}
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert x_count(db, x_id) == 1
    db.rollback()
    # Then 5
    assert x_count(db, x_id) == 0


# [claude] WSS-LM-07
@pytest.mark.xfail(strict=True, reason=BUG_2252)
def test_wss_lm_07__profiles_read_together(db, s):
    """WSS-LM-07 — profiles are read together.
    Rules: list_members R5 [BUG-2252]."""
    member(db, s, s.UA, "member")
    member(db, s, s.UB, "member")
    member(db, s, s.UC, "member")
    member(db, s, s.UQ, "member")
    commit_point(db)
    ids = {s.UO.id, s.UA.id, s.UB.id, s.UC.id, s.UQ.id}
    kw = {"workspace_id": s.W1.id, "requesting_user_id": s.UA.id}
    with recorder(db) as stmts, clock():
        result = svc.list_members(db, **kw)
    # Then 1
    assert uids(result) == ids
    # Then 2
    assert len(stmts) <= 3


# [claude] WSS-LM-08
@pytest.mark.xfail(strict=True, reason=BUG_1400)
def test_wss_lm_08__member_query_ordered(db, s):
    """WSS-LM-08 — the member query is ordered (pass-through).
    Rules: list_members R2 [BUG-1400]."""
    member(db, s, s.UA, "member")
    commit_point(db)
    ua_id, uo_id = s.UA.id, s.UO.id
    kw = {"workspace_id": s.W1.id, "requesting_user_id": s.UA.id}
    with recorder(db) as stmts, clock():
        result = svc.list_members(db, **kw)
    # Then 1
    assert uids(result) == {uo_id, ua_id}
    # Then 2
    assert any("workspace_members" in st and "ORDER BY" in st.upper() for st in stmts)


# =========================================================================== #
# update_member_role
# =========================================================================== #


# [claude] WSS-MR-01
def test_wss_mr_01__owner_changes_role_and_position(db, s):
    """WSS-MR-01 — the owner changes a member's role and position; committed and re-read.
    Rules: update_member_role R2, R3, R5; TC1, TC2."""
    ma = member(db, s, s.UA, "viewer")
    ma_id = ma.id
    commit_point(db)
    with clock():
        result = svc.update_member_role(
            db,
            workspace_id=s.W1.id,
            owner_user_id=s.UO.id,
            target_user_id=s.UA.id,
            new_role="manager",
            position="Lead",
        )
    # Then 1
    assert result.id == ma_id
    assert result.role == "manager"
    # Then 2
    assert not (
        {c.key for c in sa_inspect(result).mapper.column_attrs}
        & sa_inspect(result).expired_attributes
    )
    db.rollback()
    # Then 3
    row = db.scalars(select(WorkspaceMember).where(WorkspaceMember.id == ma_id)).one()
    assert row.role == "manager"
    assert row.position == "Lead"
    assert row.status == "active"


# [claude] WSS-MR-02
def test_wss_mr_02__position_none_keeps_position(db, s):
    """WSS-MR-02 — position=None leaves the position.
    Rules: update_member_role R5."""
    ma = member(db, s, s.UA, "viewer", position="Clerk")
    ma_id = ma.id
    commit_point(db)
    with clock():
        result = svc.update_member_role(
            db,
            workspace_id=s.W1.id,
            owner_user_id=s.UO.id,
            target_user_id=s.UA.id,
            new_role="member",
            position=None,
        )
    # Then 1
    assert result.role == "member"
    db.rollback()
    # Then 2
    row = db.scalars(select(WorkspaceMember).where(WorkspaceMember.id == ma_id)).one()
    assert row.position == "Clerk"


# [claude] WSS-MR-03
def test_wss_mr_03__empty_position_stored(db, s):
    """WSS-MR-03 — position="" stores an empty position.
    Rules: update_member_role R5."""
    ma = member(db, s, s.UA, "viewer", position="Clerk")
    ma_id = ma.id
    commit_point(db)
    with clock():
        result = svc.update_member_role(
            db,
            workspace_id=s.W1.id,
            owner_user_id=s.UO.id,
            target_user_id=s.UA.id,
            new_role="viewer",
            position="",
        )
    # Then 1
    assert result.position == ""
    db.rollback()
    # Then 2
    row = db.scalars(select(WorkspaceMember).where(WorkspaceMember.id == ma_id)).one()
    assert row.position == ""


# [claude] WSS-MR-04
@pytest.mark.xfail(strict=True, reason=BUG_2257)
def test_wss_mr_04__owner_cannot_promote_member_to_owner(db, s):
    """WSS-MR-04 — the owner cannot promote an active member to "owner".
    Rules: update_member_role R5a [BUG-2257]; TX2."""
    ma = member(db, s, s.UA, "viewer")
    commit_point(db)
    before = counts(db)
    ma_before = snap(ma)
    x_id = add_x(db, s)
    # Then 1
    with pytest.raises(ValidationError) as exc:
        with clock():
            svc.update_member_role(
                db,
                workspace_id=s.W1.id,
                owner_user_id=s.UO.id,
                target_user_id=s.UA.id,
                new_role="owner",
            )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == NO_OWNER
    # Then 4
    assert not db.dirty and not db.new and not db.deleted
    # Then 5
    assert x_count(db, x_id) == 1
    # Then 6
    assert reread_snap(db, WorkspaceMember, ma_before["id"]) == ma_before
    db.rollback()
    # Then 7
    assert x_count(db, x_id) == 0
    # Then 8
    assert counts(db) == before


# [claude] WSS-MR-05
def test_wss_mr_05__suspended_members_role_changed(db, s):
    """WSS-MR-05 — a suspended member's role can be changed.
    Rules: update_member_role R3."""
    ma = member(db, s, s.UA, "viewer", status="suspended")
    ma_id = ma.id
    commit_point(db)
    with clock():
        result = svc.update_member_role(
            db,
            workspace_id=s.W1.id,
            owner_user_id=s.UO.id,
            target_user_id=s.UA.id,
            new_role="member",
        )
    # Then 1
    assert result.role == "member"
    db.rollback()
    # Then 2
    row = db.scalars(select(WorkspaceMember).where(WorkspaceMember.id == ma_id)).one()
    assert row.role == "member"
    assert row.status == "suspended"


# [claude] WSS-MR-06
def test_wss_mr_06__other_workspace_rows_untouched(db, s):
    """WSS-MR-06 — the same person's rows in other workspaces are not touched.
    Rules: update_member_role R7."""
    a0 = member(db, s, s.UA, "viewer", ws=s.W0)
    ma = member(db, s, s.UA, "viewer")
    a2 = member(db, s, s.UA, "viewer", ws=s.W2)
    commit_point(db)
    a0_before, a2_before = snap(a0), snap(a2)
    ma_id = ma.id
    with clock():
        result = svc.update_member_role(
            db,
            workspace_id=s.W1.id,
            owner_user_id=s.UO.id,
            target_user_id=s.UA.id,
            new_role="manager",
            position="Lead",
        )
    # Then 1
    assert result.id == ma_id
    # Then 2
    assert reread_snap(db, WorkspaceMember, a0_before["id"]) == a0_before
    # Then 3
    assert reread_snap(db, WorkspaceMember, a2_before["id"]) == a2_before


# [claude] WSS-MR-07
def test_wss_mr_07__target_without_row_404(db, s):
    """WSS-MR-07 — a target with no row: 404, pending changes stay pending.
    Rules: update_member_role R3; TX2."""
    commit_point(db)
    before = counts(db)
    x_id = add_x(db, s)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        with clock():
            svc.update_member_role(
                db,
                workspace_id=s.W1.id,
                owner_user_id=s.UO.id,
                target_user_id=s.UB.id,
                new_role="manager",
            )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Member not found"
    # Then 4
    assert not db.dirty and not db.new and not db.deleted
    # Then 5
    assert x_count(db, x_id) == 1
    db.rollback()
    # Then 6
    assert x_count(db, x_id) == 0
    # Then 7
    assert counts(db) == before


# [claude] WSS-MR-08
def test_wss_mr_08__target_member_of_w0_only_404(db, s):
    """WSS-MR-08 — a target who is a member of W0 only: 404.
    Rules: update_member_role R3."""
    a0 = member(db, s, s.UA, "viewer", ws=s.W0)
    commit_point(db)
    a0_before = snap(a0)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        with clock():
            svc.update_member_role(
                db,
                workspace_id=s.W1.id,
                owner_user_id=s.UO.id,
                target_user_id=s.UA.id,
                new_role="manager",
            )
    # Then 2
    assert exc.value.detail == "Member not found"
    # Then 3
    assert not db.dirty and not db.new
    # Then 4
    assert reread_snap(db, WorkspaceMember, a0_before["id"]) == a0_before


# [claude] WSS-MR-09
def test_wss_mr_09__target_member_of_w2_only_404(db, s):
    """WSS-MR-09 — a target who is a member of W2 only: 404.
    Rules: update_member_role R3."""
    a2 = member(db, s, s.UA, "viewer", ws=s.W2)
    commit_point(db)
    a2_before = snap(a2)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        with clock():
            svc.update_member_role(
                db,
                workspace_id=s.W1.id,
                owner_user_id=s.UO.id,
                target_user_id=s.UA.id,
                new_role="manager",
            )
    # Then 2
    assert exc.value.detail == "Member not found"
    # Then 3
    assert not db.dirty and not db.new
    # Then 4
    assert reread_snap(db, WorkspaceMember, a2_before["id"]) == a2_before


# [claude] WSS-MR-10
@pytest.mark.xfail(strict=True, reason=BUG_2254)
def test_wss_mr_10__inactive_member_not_found(db, s):
    """WSS-MR-10 — a removed (inactive) member answers "Member not found".
    Rules: update_member_role R3 [BUG-2254]."""
    ma = member(db, s, s.UA, "viewer", status="inactive")
    commit_point(db)
    ma_before = snap(ma)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        with clock():
            svc.update_member_role(
                db,
                workspace_id=s.W1.id,
                owner_user_id=s.UO.id,
                target_user_id=s.UA.id,
                new_role="manager",
            )
    # Then 2
    assert exc.value.detail == "Member not found"
    # Then 3
    assert not db.dirty and not db.new
    # Then 4
    assert reread_snap(db, WorkspaceMember, ma_before["id"]) == ma_before


# [claude] WSS-MR-11
def test_wss_mr_11__owners_own_role_cannot_change(db, s):
    """WSS-MR-11 — the owner's own role cannot be changed.
    Rules: update_member_role R4."""
    commit_point(db)
    mo_before = snap(s.MO)
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc.update_member_role(
                db,
                workspace_id=s.W1.id,
                owner_user_id=s.UO.id,
                target_user_id=s.UO.id,
                new_role="viewer",
            )
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == "Cannot change workspace owner's role"
    # Then 4
    assert not db.dirty and not db.new
    # Then 5
    assert reread_snap(db, WorkspaceMember, mo_before["id"]) == mo_before


# [claude] WSS-MR-12
def test_wss_mr_12__active_manager_not_owner_refused(db, s):
    """WSS-MR-12 — an active manager who is not the owner is refused, pending changes stay
    pending.
    Rules: update_member_role R2; TX2."""
    member(db, s, s.UA, "manager")
    mb = member(db, s, s.UB, "viewer")
    commit_point(db)
    mb_before = snap(mb)
    x_id = add_x(db, s)
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc.update_member_role(
                db,
                workspace_id=s.W1.id,
                owner_user_id=s.UA.id,
                target_user_id=s.UB.id,
                new_role="member",
            )
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == "Only workspace owner can change member roles"
    # Then 4
    assert not db.dirty and not db.new and not db.deleted
    # Then 5
    assert x_count(db, x_id) == 1
    # Then 6
    assert reread_snap(db, WorkspaceMember, mb_before["id"]) == mb_before


# [claude] WSS-MR-13
@pytest.mark.xfail(strict=True, reason=BUG_2250)
def test_wss_mr_13__unknown_workspace_not_a_member(db, s):
    """WSS-MR-13 — an unknown workspace answers "not a member".
    Rules: update_member_role R1 [BUG-2250]."""
    commit_point(db)
    before = counts(db)
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc.update_member_role(
                db,
                workspace_id=MISSING,
                owner_user_id=s.UO.id,
                target_user_id=s.UA.id,
                new_role="member",
            )
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == NOTMEM
    # Then 4
    assert not db.dirty and not db.new
    # Then 5
    assert counts(db) == before


# [claude] WSS-MR-14
@pytest.mark.xfail(strict=True, reason=BUG_2250)
def test_wss_mr_14__owner_of_w0_not_a_member_on_w1(db, s):
    """WSS-MR-14 — the owner of W0 (lower id) gets "not a member" on W1.
    Rules: update_member_role R1 [BUG-2250]."""
    mb = member(db, s, s.UB, "viewer")
    commit_point(db)
    mb_before = snap(mb)
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc.update_member_role(
                db,
                workspace_id=s.W1.id,
                owner_user_id=s.U0.id,
                target_user_id=s.UB.id,
                new_role="member",
            )
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == NOTMEM
    # Then 4
    assert not db.dirty and not db.new
    # Then 5
    assert reread_snap(db, WorkspaceMember, mb_before["id"]) == mb_before


# [claude] WSS-MR-15
@pytest.mark.xfail(strict=True, reason=BUG_2250)
def test_wss_mr_15__owner_of_w2_not_a_member_on_w1(db, s):
    """WSS-MR-15 — the owner of W2 (higher id) gets "not a member" on W1.
    Rules: update_member_role R1 [BUG-2250]."""
    mb = member(db, s, s.UB, "viewer")
    commit_point(db)
    mb_before = snap(mb)
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc.update_member_role(
                db,
                workspace_id=s.W1.id,
                owner_user_id=s.U2.id,
                target_user_id=s.UB.id,
                new_role="member",
            )
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == NOTMEM
    # Then 4
    assert not db.dirty and not db.new
    # Then 5
    assert reread_snap(db, WorkspaceMember, mb_before["id"]) == mb_before


# [claude] WSS-MR-16
@pytest.mark.xfail(strict=True, reason=BUG_2250)
def test_wss_mr_16__owner_user_id_without_row_refused(db, s):
    """WSS-MR-16 — owner_user_id without a member row is refused.
    Rules: update_member_role R1 [BUG-2250]."""
    s.W1.owner_user_id = s.UA.id
    db.flush()
    mb = member(db, s, s.UB, "viewer")
    commit_point(db)
    mb_before = snap(mb)
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc.update_member_role(
                db,
                workspace_id=s.W1.id,
                owner_user_id=s.UA.id,
                target_user_id=s.UB.id,
                new_role="member",
            )
    # Then 2
    assert exc.value.detail == NOTMEM
    # Then 3
    assert not db.dirty and not db.new
    # Then 4
    assert reread_snap(db, WorkspaceMember, mb_before["id"]) == mb_before


# [claude] WSS-MR-17
@pytest.mark.xfail(strict=True, reason=BUG_2250)
def test_wss_mr_17__owner_user_id_with_inactive_row_refused(db, s):
    """WSS-MR-17 — owner_user_id with an inactive row is refused.
    Rules: update_member_role R1 [BUG-2250]."""
    s.W1.owner_user_id = s.UA.id
    db.flush()
    member(db, s, s.UA, "owner", status="inactive")
    mb = member(db, s, s.UB, "viewer")
    commit_point(db)
    mb_before = snap(mb)
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc.update_member_role(
                db,
                workspace_id=s.W1.id,
                owner_user_id=s.UA.id,
                target_user_id=s.UB.id,
                new_role="member",
            )
    # Then 2
    assert exc.value.detail == NOTMEM
    # Then 3
    assert not db.dirty and not db.new
    # Then 4
    assert reread_snap(db, WorkspaceMember, mb_before["id"]) == mb_before


# [claude] WSS-MR-18
@pytest.mark.xfail(strict=True, reason=BUG_2253)
def test_wss_mr_18__role_change_writes_audit_row(db, s):
    """WSS-MR-18 — a role change writes one member_role_changed audit row.
    Rules: update_member_role R6 [BUG-2253]."""
    member(db, s, s.UA, "viewer", position="Clerk")
    commit_point(db)
    w1_id, uo_id, ua_id = s.W1.id, s.UO.id, s.UA.id
    with clock():
        result = svc.update_member_role(
            db,
            workspace_id=w1_id,
            owner_user_id=uo_id,
            target_user_id=ua_id,
            new_role="manager",
            position="Lead",
        )
    # Then 1
    assert result.role == "manager"
    # Then 2
    rows = audit(db, w1_id, "member_role_changed")
    assert len(rows) == 1
    # Then 3
    assert rows[0].user_id == uo_id
    # Then 4
    assert rows[0].metadata_json == {
        "member_id": ua_id,
        "from_role": "viewer",
        "to_role": "manager",
        "from_position": "Clerk",
        "to_position": "Lead",
    }


# [claude] WSS-MR-19
def test_wss_mr_19__same_role_no_position_no_audit(db, s):
    """WSS-MR-19 — the same role and no position: no audit row.
    Rules: update_member_role R6."""
    member(db, s, s.UA, "viewer", position="Clerk")
    commit_point(db)
    w1_id = s.W1.id
    with clock():
        result = svc.update_member_role(
            db,
            workspace_id=w1_id,
            owner_user_id=s.UO.id,
            target_user_id=s.UA.id,
            new_role="viewer",
        )
    # Then 1
    assert result.role == "viewer"
    # Then 2
    assert len(audit(db, w1_id, "member_role_changed")) == 0


# [claude] WSS-MR-20
@pytest.mark.xfail(strict=True, reason=BUG_2253)
def test_wss_mr_20__audit_row_carries_ip_and_user_agent(db, s):
    """WSS-MR-20 — the member_role_changed row carries IP and user agent.
    Rules: update_member_role R6 [BUG-2253] [BUG-1404]."""
    member(db, s, s.UA, "viewer")
    commit_point(db)
    w1_id = s.W1.id
    with clock():
        result = svc.update_member_role(
            db,
            workspace_id=w1_id,
            owner_user_id=s.UO.id,
            target_user_id=s.UA.id,
            new_role="manager",
            ip_address="203.0.113.7",
            user_agent="Mozilla/5.0 Test",
        )
    # Then 1
    assert result.role == "manager"
    # Then 2
    rows = audit(db, w1_id, "member_role_changed")
    assert len(rows) == 1
    # Then 3
    assert rows[0].ip_address == "203.0.113.7"
    assert rows[0].user_agent == "Mozilla/5.0 Test"


# [claude] WSS-MR-21
def test_wss_mr_21__failing_commit_rolls_back(db, s):
    """WSS-MR-21 — a failing commit rolls back, the role is unchanged.
    Rules: update_member_role R5; TC4."""
    ma = member(db, s, s.UA, "viewer")
    commit_point(db)
    ma_before = snap(ma)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb, clock():
            svc.update_member_role(
                db,
                workspace_id=s.W1.id,
                owner_user_id=s.UO.id,
                target_user_id=s.UA.id,
                new_role="manager",
            )
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert reread_snap(db, WorkspaceMember, ma_before["id"]) == ma_before


# [claude] WSS-MR-22
def test_wss_mr_22__failing_refresh_leaves_role_saved(db, s):
    """WSS-MR-22 — a failing re-read leaves the role saved.
    Rules: update_member_role R5; TC5."""
    ma = member(db, s, s.UA, "viewer")
    ma_id = ma.id
    commit_point(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db), clock():
            svc.update_member_role(
                db,
                workspace_id=s.W1.id,
                owner_user_id=s.UO.id,
                target_user_id=s.UA.id,
                new_role="manager",
            )
    assert str(exc.value) == "boom"
    db.rollback()
    # Then 2
    row = db.scalars(select(WorkspaceMember).where(WorkspaceMember.id == ma_id)).one()
    assert row.role == "manager"


# [claude] WSS-MR-23
def test_wss_mr_23__position_too_long_fails_at_commit(db, s):
    """WSS-MR-23 — a position too long for its column fails at the commit: rolled back,
    pending changes discarded.
    Rules: update_member_role R5; TC4."""
    ma = member(db, s, s.UA, "viewer", position="Clerk")
    commit_point(db)
    before = counts(db)
    ma_before = snap(ma)
    x_id = add_x(db, s)
    # Then 1
    with pytest.raises(DataError) as exc:
        with clock():
            svc.update_member_role(
                db,
                workspace_id=s.W1.id,
                owner_user_id=s.UO.id,
                target_user_id=s.UA.id,
                new_role="manager",
                position="p" * 256,
            )
    # Then 2
    assert exc.value.orig.pgcode == "22001"
    # Then 3
    assert x_count(db, x_id) == 0
    # Then 4
    assert reread_snap(db, WorkspaceMember, ma_before["id"]) == ma_before
    # Then 5
    assert counts(db) == before


# [claude] WSS-MR-24
@pytest.mark.xfail(strict=True, reason=BUG_2256)
def test_wss_mr_24__position_256_refused_by_role_change_request():
    """WSS-MR-24 — a position of 256 characters is refused by RoleChangeRequest.
    Rules: update_workspace R5a [BUG-2256] (RoleChangeRequest.position)."""
    # Then 1
    with pytest.raises(PydanticValidationError):
        RoleChangeRequest(new_role="manager", position="p" * 256)


# [claude] WSS-MR-25
def test_wss_mr_25__position_255_accepted_by_role_change_request():
    """WSS-MR-25 — a position of 255 characters is accepted by RoleChangeRequest.
    Rules: update_workspace R5a (RoleChangeRequest.position)."""
    result = RoleChangeRequest(new_role="manager", position="p" * 255)
    # Then 1
    assert result.position == "p" * 255


# [claude] WSS-MR-26
@pytest.mark.xfail(strict=True, reason=BUG_2257)
def test_wss_mr_26__owner_refusal_before_member_not_found(db, s):
    """WSS-MR-26 — "owner" for a target with no row: the owner-role refusal comes before
    "Member not found".
    Rules: update_member_role R5a [BUG-2257] (before R3); TX2."""
    commit_point(db)
    before = counts(db)
    x_id = add_x(db, s)
    # Then 1
    with pytest.raises(ValidationError) as exc:
        with clock():
            svc.update_member_role(
                db,
                workspace_id=s.W1.id,
                owner_user_id=s.UO.id,
                target_user_id=s.UB.id,
                new_role="owner",
            )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == NO_OWNER
    # Then 4
    assert not db.dirty and not db.new and not db.deleted
    # Then 5
    assert x_count(db, x_id) == 1
    db.rollback()
    # Then 6
    assert x_count(db, x_id) == 0
    # Then 7
    assert counts(db) == before


# [claude] WSS-MR-27
@pytest.mark.xfail(strict=True, reason=BUG_2257)
def test_wss_mr_27__owner_for_inactive_member_refused(db, s):
    """WSS-MR-27 — "owner" for a removed (inactive) member is refused.
    Rules: update_member_role R5a [BUG-2257] (before R3); TX2."""
    ma = member(db, s, s.UA, "viewer", status="inactive")
    commit_point(db)
    before = counts(db)
    ma_before = snap(ma)
    x_id = add_x(db, s)
    # Then 1
    with pytest.raises(ValidationError) as exc:
        with clock():
            svc.update_member_role(
                db,
                workspace_id=s.W1.id,
                owner_user_id=s.UO.id,
                target_user_id=s.UA.id,
                new_role="owner",
            )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == NO_OWNER
    # Then 4
    assert not db.dirty and not db.new and not db.deleted
    # Then 5
    assert x_count(db, x_id) == 1
    # Then 6
    assert reread_snap(db, WorkspaceMember, ma_before["id"]) == ma_before
    db.rollback()
    # Then 7
    assert x_count(db, x_id) == 0
    # Then 8
    assert counts(db) == before


# [claude] WSS-MR-28
@pytest.mark.xfail(strict=True, reason=BUG_2257)
def test_wss_mr_28__owner_for_owners_own_row_refused_before_r4(db, s):
    """WSS-MR-28 — "owner" for the owner's own row: the owner-role refusal comes before R4.
    Rules: update_member_role R5a [BUG-2257] (before R3, R4); TX2."""
    commit_point(db)
    before = counts(db)
    mo_before = snap(s.MO)
    x_id = add_x(db, s)
    # Then 1
    with pytest.raises(ValidationError) as exc:
        with clock():
            svc.update_member_role(
                db,
                workspace_id=s.W1.id,
                owner_user_id=s.UO.id,
                target_user_id=s.UO.id,
                new_role="owner",
            )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == NO_OWNER
    # Then 4
    assert not db.dirty and not db.new and not db.deleted
    # Then 5
    assert x_count(db, x_id) == 1
    # Then 6
    assert reread_snap(db, WorkspaceMember, mo_before["id"]) == mo_before
    db.rollback()
    # Then 7
    assert x_count(db, x_id) == 0
    # Then 8
    assert counts(db) == before


# [claude] WSS-MR-29
def test_wss_mr_29__capital_owner_stored_as_given(db, s):
    """WSS-MR-29 — only exactly "owner" is refused: "Owner" is stored as given.
    Rules: update_member_role R5, R5a."""
    ma = member(db, s, s.UA, "viewer")
    ma_id = ma.id
    commit_point(db)
    with clock():
        result = svc.update_member_role(
            db,
            workspace_id=s.W1.id,
            owner_user_id=s.UO.id,
            target_user_id=s.UA.id,
            new_role="Owner",
        )
    # Then 1
    assert result.role == "Owner"
    db.rollback()
    # Then 2
    row = db.scalars(select(WorkspaceMember).where(WorkspaceMember.id == ma_id)).one()
    assert row.role == "Owner"


# [claude] WSS-MR-30
def test_wss_mr_30__non_owner_asking_for_owner_gets_owner_message(db, s):
    """WSS-MR-30 — a non-owner asking for "owner" gets the owner message first (R2 before R5a).
    Rules: update_member_role R2, R5a; TX2."""
    member(db, s, s.UA, "manager")
    mb = member(db, s, s.UB, "viewer")
    commit_point(db)
    before = counts(db)
    mb_before = snap(mb)
    x_id = add_x(db, s)
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc.update_member_role(
                db,
                workspace_id=s.W1.id,
                owner_user_id=s.UA.id,
                target_user_id=s.UB.id,
                new_role="owner",
            )
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == "Only workspace owner can change member roles"
    # Then 4
    assert not db.dirty and not db.new and not db.deleted
    # Then 5
    assert x_count(db, x_id) == 1
    # Then 6
    assert reread_snap(db, WorkspaceMember, mb_before["id"]) == mb_before
    db.rollback()
    # Then 7
    assert x_count(db, x_id) == 0
    # Then 8
    assert counts(db) == before


# [claude] WSS-MR-31
@pytest.mark.xfail(strict=True, reason=BUG_2258)
def test_wss_mr_31__owner_changes_own_position_without_role(db, s):
    """WSS-MR-31 — the owner changes their own position with no role.
    Rules: update_member_role R4a [BUG-2258], R5, R6 (BUG-2253's row)."""
    s.MO.position = "Founder"
    db.flush()
    commit_point(db)
    mo_id, w1_id, uo_id = s.MO.id, s.W1.id, s.UO.id
    with clock():
        result = svc.update_member_role(
            db,
            workspace_id=w1_id,
            owner_user_id=uo_id,
            target_user_id=uo_id,
            new_role=None,
            position="Director",
        )
    # Then 1
    assert result.id == mo_id
    assert result.position == "Director"
    db.rollback()
    # Then 2
    row = db.scalars(select(WorkspaceMember).where(WorkspaceMember.id == mo_id)).one()
    assert row.position == "Director"
    assert row.role == "owner"
    assert row.status == "active"
    # Then 3
    rows = audit(db, w1_id, "member_role_changed")
    assert len(rows) == 1
    # Then 4
    assert rows[0].metadata_json == {
        "member_id": uo_id,
        "from_role": "owner",
        "to_role": "owner",
        "from_position": "Founder",
        "to_position": "Director",
    }


# [claude] WSS-MR-32
def test_wss_mr_32__owner_role_with_position_still_refused(db, s):
    """WSS-MR-32 — the owner's role with a position is still refused, and the position is not
    stored either.
    Rules: update_member_role R4, R4a."""
    s.MO.position = "Founder"
    db.flush()
    commit_point(db)
    before = counts(db)
    mo_before = snap(s.MO)
    x_id = add_x(db, s)
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc.update_member_role(
                db,
                workspace_id=s.W1.id,
                owner_user_id=s.UO.id,
                target_user_id=s.UO.id,
                new_role="manager",
                position="Director",
            )
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == "Cannot change workspace owner's role"
    # Then 4
    assert not db.dirty and not db.new and not db.deleted
    # Then 5
    assert x_count(db, x_id) == 1
    # Then 6
    assert reread_snap(db, WorkspaceMember, mo_before["id"]) == mo_before
    db.rollback()
    # Then 7
    assert x_count(db, x_id) == 0
    # Then 8
    assert counts(db) == before


# [claude] WSS-MR-33
@pytest.mark.xfail(strict=True, reason=BUG_2258)
def test_wss_mr_33__none_role_keeps_role_applies_position(db, s):
    """WSS-MR-33 — new_role=None keeps another member's role and applies only the position.
    Rules: update_member_role R4a [BUG-2258]."""
    ma = member(db, s, s.UA, "viewer", position="Clerk")
    ma_id = ma.id
    commit_point(db)
    with clock():
        result = svc.update_member_role(
            db,
            workspace_id=s.W1.id,
            owner_user_id=s.UO.id,
            target_user_id=s.UA.id,
            new_role=None,
            position="Lead",
        )
    # Then 1
    assert result.role == "viewer"
    assert result.position == "Lead"
    db.rollback()
    # Then 2
    row = db.scalars(select(WorkspaceMember).where(WorkspaceMember.id == ma_id)).one()
    assert row.role == "viewer"
    assert row.position == "Lead"


# =========================================================================== #
# remove_member
# =========================================================================== #


# [claude] WSS-RM-01
def test_wss_rm_01__owner_removes_member(db, s):
    """WSS-RM-01 — the owner removes a member; committed, None returned.
    Rules: remove_member R1, R2; TC1, TX3."""
    ma = member(db, s, s.UA, "member")
    commit_point(db)
    ma_id, w1_id, uo_id, ua_id = ma.id, s.W1.id, s.UO.id, s.UA.id
    with clock():
        result = svc.remove_member(
            db, workspace_id=w1_id, remover_user_id=uo_id, target_user_id=ua_id
        )
    # Then 1
    assert result is None
    db.rollback()
    # Then 2
    row = db.scalars(select(WorkspaceMember).where(WorkspaceMember.id == ma_id)).one()
    assert row.status == "inactive"
    assert row.left_at == NOW
    assert row.role == "member"
    # Then 3
    rows = audit(db, w1_id, "member_removed")
    assert len(rows) == 1
    # Then 4
    assert rows[0].user_id == uo_id
    assert rows[0].metadata_json == {"removed_member_id": ua_id}


# [claude] WSS-RM-02
def test_wss_rm_02__ground_team_manager_removes_ground_team(db, s):
    """WSS-RM-02 — the remover's stored role is used: a ground-team-manager removes ground-team.
    Rules: remove_member R2."""
    member(db, s, s.UB, "ground-team-manager")
    ma = member(db, s, s.UA, "ground-team")
    ma_id = ma.id
    commit_point(db)
    with clock():
        result = svc.remove_member(
            db, workspace_id=s.W1.id, remover_user_id=s.UB.id, target_user_id=s.UA.id
        )
    # Then 1
    assert result is None
    db.rollback()
    # Then 2
    row = db.scalars(select(WorkspaceMember).where(WorkspaceMember.id == ma_id)).one()
    assert row.status == "inactive"


# [claude] WSS-RM-03
def test_wss_rm_03__no_reread_after_commit(db, s):
    """WSS-RM-03 — no re-read after the commit.
    Rules: remove_member R2; TX3."""
    ma = member(db, s, s.UA, "member")
    ma_id = ma.id
    commit_point(db)
    with refresh_trap(db) as rf, clock():
        result = svc.remove_member(
            db, workspace_id=s.W1.id, remover_user_id=s.UO.id, target_user_id=s.UA.id
        )
    # Then 1
    assert result is None
    # Then 2
    assert rf.call_count == 0
    db.rollback()
    # Then 3
    row = db.scalars(select(WorkspaceMember).where(WorkspaceMember.id == ma_id)).one()
    assert row.status == "inactive"


# [claude] WSS-RM-04
def test_wss_rm_04__non_member_caller_refused_first(db, s):
    """WSS-RM-04 — a caller who is not a member is refused first; pending changes stay pending.
    Rules: remove_member R1; TX2."""
    ma = member(db, s, s.UA, "member")
    commit_point(db)
    ma_before = snap(ma)
    x_id = add_x(db, s)
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc.remove_member(
                db,
                workspace_id=s.W1.id,
                remover_user_id=s.U2.id,
                target_user_id=s.UA.id,
            )
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == NOTMEM
    # Then 4
    assert not db.dirty and not db.new and not db.deleted
    # Then 5
    assert x_count(db, x_id) == 1
    # Then 6
    assert reread_snap(db, WorkspaceMember, ma_before["id"]) == ma_before


# [claude] WSS-RM-05
def test_wss_rm_05__inactive_caller_refused(db, s):
    """WSS-RM-05 — an inactive caller is refused.
    Rules: remove_member R1."""
    member(db, s, s.UB, "owner", status="inactive")
    ma = member(db, s, s.UA, "member")
    commit_point(db)
    ma_before = snap(ma)
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc.remove_member(
                db,
                workspace_id=s.W1.id,
                remover_user_id=s.UB.id,
                target_user_id=s.UA.id,
            )
    # Then 2
    assert exc.value.detail == NOTMEM
    # Then 3
    assert not db.dirty and not db.new
    # Then 4
    assert reread_snap(db, WorkspaceMember, ma_before["id"]) == ma_before


# [claude] WSS-RM-06
def test_wss_rm_06__owner_role_in_w0_does_not_count(db, s):
    """WSS-RM-06 — an "owner" role held in W0 does not count: ground-team in W1 is refused.
    Rules: remove_member R2, R3."""
    member(db, s, s.UB, "owner", ws=s.W0)
    member(db, s, s.UB, "ground-team")
    ma = member(db, s, s.UA, "member")
    commit_point(db)
    ma_before = snap(ma)
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc.remove_member(
                db,
                workspace_id=s.W1.id,
                remover_user_id=s.UB.id,
                target_user_id=s.UA.id,
            )
    # Then 2
    assert exc.value.detail == "You do not have permission to remove members"
    # Then 3
    assert not db.dirty and not db.new
    # Then 4
    assert reread_snap(db, WorkspaceMember, ma_before["id"]) == ma_before


# [claude] WSS-RM-07
def test_wss_rm_07__owner_role_in_w2_does_not_count(db, s):
    """WSS-RM-07 — an "owner" role held in W2 does not count: ground-team in W1 is refused.
    Rules: remove_member R2, R3."""
    member(db, s, s.UB, "ground-team")
    member(db, s, s.UB, "owner", ws=s.W2)
    ma = member(db, s, s.UA, "member")
    commit_point(db)
    ma_before = snap(ma)
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc.remove_member(
                db,
                workspace_id=s.W1.id,
                remover_user_id=s.UB.id,
                target_user_id=s.UA.id,
            )
    # Then 2
    assert exc.value.detail == "You do not have permission to remove members"
    # Then 3
    assert not db.dirty and not db.new
    # Then 4
    assert reread_snap(db, WorkspaceMember, ma_before["id"]) == ma_before


# [claude] WSS-RM-08
def test_wss_rm_08__removing_owner_stays_403(db, s):
    """WSS-RM-08 — removing the owner stays 403; the rollback discards pending changes.
    Rules: remove_member R3; TX1, TC3."""
    commit_point(db)
    before = counts(db)
    mo_before = snap(s.MO)
    x_id = add_x(db, s)
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc.remove_member(
                db,
                workspace_id=s.W1.id,
                remover_user_id=s.UO.id,
                target_user_id=s.UO.id,
            )
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert (
        exc.value.detail == "Cannot remove workspace owner. Transfer ownership first."
    )
    # Then 4
    assert isinstance(exc.value.__context__, ValueError)
    # Then 5
    assert x_count(db, x_id) == 0
    # Then 6
    assert reread_snap(db, WorkspaceMember, mo_before["id"]) == mo_before
    # Then 7
    assert counts(db) == before


# [claude] WSS-RM-09
def test_wss_rm_09__ground_team_manager_removing_member_403(db, s):
    """WSS-RM-09 — a ground-team-manager removing a "member" stays 403.
    Rules: remove_member R3 (manager R4)."""
    member(db, s, s.UB, "ground-team-manager")
    ma = member(db, s, s.UA, "member")
    commit_point(db)
    before = counts(db)
    ma_before = snap(ma)
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc.remove_member(
                db,
                workspace_id=s.W1.id,
                remover_user_id=s.UB.id,
                target_user_id=s.UA.id,
            )
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == "Managers can only remove ground-team members"
    # Then 4
    assert reread_snap(db, WorkspaceMember, ma_before["id"]) == ma_before
    # Then 5
    assert counts(db) == before


# [claude] WSS-RM-10
def test_wss_rm_10__not_a_member_text_reaches_caller(db, s):
    """WSS-RM-10 — "not a member" text reaches the caller (holds before and after BUG-2251).
    Rules: remove_member R3."""
    commit_point(db)
    before = counts(db)
    x_id = add_x(db, s)
    # Then 1
    with pytest.raises(APIException) as exc:
        with clock():
            svc.remove_member(
                db,
                workspace_id=s.W1.id,
                remover_user_id=s.UO.id,
                target_user_id=s.UC.id,
            )
    # Then 2
    assert exc.value.detail == "User is not a member of this workspace"
    # Then 3
    assert x_count(db, x_id) == 0
    # Then 4
    assert counts(db) == before


# [claude] WSS-RM-11
@pytest.mark.xfail(strict=True, reason=BUG_2251)
def test_wss_rm_11__target_without_row_404(db, s):
    """WSS-RM-11 — a target with no row answers 404.
    Rules: remove_member R3 [BUG-2251]."""
    commit_point(db)
    before = counts(db)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        with clock():
            svc.remove_member(
                db,
                workspace_id=s.W1.id,
                remover_user_id=s.UO.id,
                target_user_id=s.UC.id,
            )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "User is not a member of this workspace"
    # Then 4
    assert not db.dirty and not db.new
    # Then 5
    assert counts(db) == before


# [claude] WSS-RM-12
@pytest.mark.xfail(strict=True, reason=BUG_2251)
def test_wss_rm_12__target_member_of_w0_only_404(db, s):
    """WSS-RM-12 — a target who is a member of W0 only answers 404.
    Rules: remove_member R3 [BUG-2251]."""
    a0 = member(db, s, s.UA, "member", ws=s.W0)
    commit_point(db)
    a0_before = snap(a0)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        with clock():
            svc.remove_member(
                db,
                workspace_id=s.W1.id,
                remover_user_id=s.UO.id,
                target_user_id=s.UA.id,
            )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "User is not a member of this workspace"
    # Then 4
    assert not db.dirty and not db.new
    # Then 5
    assert reread_snap(db, WorkspaceMember, a0_before["id"]) == a0_before


# [claude] WSS-RM-13
@pytest.mark.xfail(strict=True, reason=BUG_2251)
def test_wss_rm_13__target_member_of_w2_only_404(db, s):
    """WSS-RM-13 — a target who is a member of W2 only answers 404.
    Rules: remove_member R3 [BUG-2251]."""
    a2 = member(db, s, s.UA, "member", ws=s.W2)
    commit_point(db)
    a2_before = snap(a2)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        with clock():
            svc.remove_member(
                db,
                workspace_id=s.W1.id,
                remover_user_id=s.UO.id,
                target_user_id=s.UA.id,
            )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "User is not a member of this workspace"
    # Then 4
    assert not db.dirty and not db.new
    # Then 5
    assert reread_snap(db, WorkspaceMember, a2_before["id"]) == a2_before


# [claude] WSS-RM-14
@pytest.mark.xfail(strict=True, reason=BUG_2251)
def test_wss_rm_14__already_removed_target_404(db, s):
    """WSS-RM-14 — an already removed target answers 404 and stays as it was.
    Rules: remove_member R3 [BUG-2251] (manager R1a, BUG-1984: both must be fixed)."""
    ma = member(
        db, s, s.UA, "member", status="inactive", left_at=datetime(2026, 2, 1, 9, 0, 0)
    )
    commit_point(db)
    before = counts(db)
    ma_before = snap(ma)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        with clock():
            svc.remove_member(
                db,
                workspace_id=s.W1.id,
                remover_user_id=s.UO.id,
                target_user_id=s.UA.id,
            )
    # Then 2
    assert exc.value.detail == "User is not a member of this workspace"
    # Then 3
    assert not db.dirty and not db.new
    # Then 4
    assert reread_snap(db, WorkspaceMember, ma_before["id"]) == ma_before
    # Then 5
    assert counts(db) == before


# [claude] WSS-RM-15
@pytest.mark.xfail(strict=True, reason=BUG_1990)
def test_wss_rm_15__manager_may_not_remove_member(db, s):
    """WSS-RM-15 — a "manager" may not remove a "member" (pass-through).
    Rules: remove_member R2 (manager R4b) [BUG-1990]."""
    member(db, s, s.UB, "manager")
    ma = member(db, s, s.UA, "member")
    commit_point(db)
    ma_before = snap(ma)
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc.remove_member(
                db,
                workspace_id=s.W1.id,
                remover_user_id=s.UB.id,
                target_user_id=s.UA.id,
            )
    # Then 2
    assert exc.value.detail == "Managers can only remove ground-team members"
    # Then 3
    assert reread_snap(db, WorkspaceMember, ma_before["id"]) == ma_before


# [claude] WSS-RM-16
@pytest.mark.xfail(strict=True, reason=BUG_1990)
def test_wss_rm_16__viewer_may_not_remove_anyone(db, s):
    """WSS-RM-16 — a "viewer" may not remove anyone (pass-through).
    Rules: remove_member R2 (manager R5) [BUG-1990]."""
    member(db, s, s.UB, "viewer")
    ma = member(db, s, s.UA, "member")
    commit_point(db)
    ma_before = snap(ma)
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc.remove_member(
                db,
                workspace_id=s.W1.id,
                remover_user_id=s.UB.id,
                target_user_id=s.UA.id,
            )
    # Then 2
    assert exc.value.detail == "You do not have permission to remove members"
    # Then 3
    assert reread_snap(db, WorkspaceMember, ma_before["id"]) == ma_before


# [claude] WSS-RM-17
@pytest.mark.xfail(strict=True, reason=BUG_1280)
def test_wss_rm_17__project_memberships_go_with_member(db, s):
    """WSS-RM-17 — the removed person's project memberships go with them (pass-through).
    Rules: remove_member R2 (manager R9) [BUG-1280]."""
    member(db, s, s.UA, "member")
    fac = _add(db, Factory(workspace_id=s.W1.id, name="Plant", abbreviation="PL"))
    p = _add(
        db,
        Project(
            workspace_id=s.W1.id,
            factory_id=fac.id,
            name=f"Project {s.TAG}",
            description="Main",
        ),
    )
    _add(
        db,
        ProjectMember(
            workspace_id=s.W1.id, project_id=p.id, user_id=s.UA.id, assigned_by=s.UO.id
        ),
    )
    commit_point(db)
    p_id, ua_id = p.id, s.UA.id
    with clock():
        result = svc.remove_member(
            db, workspace_id=s.W1.id, remover_user_id=s.UO.id, target_user_id=ua_id
        )
    # Then 1
    assert result is None
    db.rollback()
    # Then 2
    n = db.scalar(
        select(func.count())
        .select_from(ProjectMember)
        .where(ProjectMember.project_id == p_id, ProjectMember.user_id == ua_id)
    )
    assert n == 0


# [claude] WSS-RM-18
@pytest.mark.xfail(strict=True, reason=BUG_1404)
def test_wss_rm_18__ip_and_user_agent_reach_member_removed(db, s):
    """WSS-RM-18 — IP and user agent reach the member_removed row.
    Rules: remove_member R4 [BUG-1404]."""
    member(db, s, s.UA, "member")
    commit_point(db)
    w1_id = s.W1.id
    with clock():
        result = svc.remove_member(
            db,
            workspace_id=w1_id,
            remover_user_id=s.UO.id,
            target_user_id=s.UA.id,
            ip_address="203.0.113.7",
            user_agent="Mozilla/5.0 Test",
        )
    # Then 1
    assert result is None
    # Then 2
    rows = audit(db, w1_id, "member_removed")
    assert len(rows) == 1
    # Then 3
    assert rows[0].ip_address == "203.0.113.7"
    assert rows[0].user_agent == "Mozilla/5.0 Test"


# [claude] WSS-RM-19
def test_wss_rm_19__failing_commit_member_stays_active(db, s):
    """WSS-RM-19 — a failing commit rolls back, the member stays active.
    Rules: remove_member R5; TC4."""
    ma = member(db, s, s.UA, "member")
    commit_point(db)
    before = counts(db)
    ma_before = snap(ma)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb, clock():
            svc.remove_member(
                db,
                workspace_id=s.W1.id,
                remover_user_id=s.UO.id,
                target_user_id=s.UA.id,
            )
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert reread_snap(db, WorkspaceMember, ma_before["id"]) == ma_before
    # Then 4
    assert counts(db) == before


# =========================================================================== #
# send_invitation
# =========================================================================== #


def inv_count(db, ws_id, email):
    return db.scalar(
        select(func.count())
        .select_from(WorkspaceInvitation)
        .where(
            WorkspaceInvitation.workspace_id == ws_id,
            WorkspaceInvitation.email == email,
        )
    )


# [claude] WSS-SI-01
def test_wss_si_01__owner_invites_email(db, s):
    """WSS-SI-01 — the owner invites an email; committed and re-read.
    Rules: send_invitation R1, R2; TC1, TC2."""
    commit_point(db)
    w1_id, uo_id = s.W1.id, s.UO.id
    with clock():
        result = svc.send_invitation(
            db,
            workspace_id=w1_id,
            inviter_user_id=uo_id,
            email=s.ED,
            role="member",
            position="Tech",
        )
    # Then 1
    assert isinstance(result, WorkspaceInvitation)
    # Then 2
    assert len(result.token) == 43
    assert not (
        {c.key for c in sa_inspect(result).mapper.column_attrs}
        & sa_inspect(result).expired_attributes
    )
    inv_id = result.id
    db.rollback()
    row = db.scalars(
        select(WorkspaceInvitation).where(WorkspaceInvitation.id == inv_id)
    ).one()
    # Then 3
    assert row.workspace_id == w1_id
    assert row.email == s.ED
    assert row.role == "member"
    assert row.position == "Tech"
    # Then 4
    assert row.status == "pending"
    assert row.expires_at == NOW + timedelta(days=3)
    assert row.invited_by_user_id == uo_id
    # Then 5
    assert len(audit(db, w1_id, "invitation_sent")) == 1


# [claude] WSS-SI-02
def test_wss_si_02__stored_owner_role_may_invite(db, s):
    """WSS-SI-02 — a member whose stored role is "owner" may invite, whoever owner_user_id names.
    Rules: send_invitation R1 (D6)."""
    member(db, s, s.UA, "owner")
    commit_point(db)
    ua_id = s.UA.id
    with clock():
        result = svc.send_invitation(
            db, workspace_id=s.W1.id, inviter_user_id=ua_id, email=s.ED, role="viewer"
        )
    # Then 1
    assert isinstance(result, WorkspaceInvitation)
    inv_id = result.id
    db.rollback()
    # Then 2
    row = db.scalars(
        select(WorkspaceInvitation).where(WorkspaceInvitation.id == inv_id)
    ).one()
    assert row.invited_by_user_id == ua_id


# [claude] WSS-SI-03
def test_wss_si_03__active_manager_refused_before_anything(db, s):
    """WSS-SI-03 — an active manager is refused before anything; pending changes stay pending.
    Rules: send_invitation R1; TX2."""
    member(db, s, s.UA, "manager")
    commit_point(db)
    before = counts(db)
    x_id = add_x(db, s)
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc.send_invitation(
                db,
                workspace_id=s.W1.id,
                inviter_user_id=s.UA.id,
                email=s.ED,
                role="member",
            )
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == OWNONLY
    # Then 4
    assert not db.dirty and not db.new and not db.deleted
    # Then 5
    assert x_count(db, x_id) == 1
    db.rollback()
    # Then 6
    assert x_count(db, x_id) == 0
    # Then 7
    assert counts(db) == before


# [claude] WSS-SI-04
def test_wss_si_04__owner_of_w2_member_in_w1_refused(db, s):
    """WSS-SI-04 — the owner of W2, a "member" in W1, is refused.
    Rules: send_invitation R1."""
    member(db, s, s.U2, "member")
    commit_point(db)
    before = counts(db)
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc.send_invitation(
                db,
                workspace_id=s.W1.id,
                inviter_user_id=s.U2.id,
                email=s.ED,
                role="member",
            )
    # Then 2
    assert exc.value.detail == OWNONLY
    # Then 3
    assert not db.dirty and not db.new
    # Then 4
    assert counts(db) == before


# [claude] WSS-SI-05
def test_wss_si_05__non_member_refused_with_membership_message(db, s):
    """WSS-SI-05 — a non-member is refused with the membership message.
    Rules: send_invitation R1."""
    commit_point(db)
    before = counts(db)
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc.send_invitation(
                db,
                workspace_id=s.W1.id,
                inviter_user_id=s.U0.id,
                email=s.ED,
                role="member",
            )
    # Then 2
    assert exc.value.detail == NOTMEM
    # Then 3
    assert not db.dirty and not db.new
    # Then 4
    assert counts(db) == before


# [claude] WSS-SI-06
def test_wss_si_06__invalid_role_400(db, s):
    """WSS-SI-06 — an invalid role: 400 with the manager's text; pending changes discarded.
    Rules: send_invitation R3; TX1, TC3."""
    commit_point(db)
    before = counts(db)
    x_id = add_x(db, s)
    # Then 1
    with pytest.raises(ValidationError) as exc:
        with clock():
            svc.send_invitation(
                db,
                workspace_id=s.W1.id,
                inviter_user_id=s.UO.id,
                email=s.ED,
                role="owner",
            )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert (
        exc.value.detail
        == "Invalid role. Must be one of: ground-team, manager, member, viewer"
    )
    # Then 4
    assert isinstance(exc.value.__context__, ValueError)
    # Then 5
    assert x_count(db, x_id) == 0
    # Then 6
    assert counts(db) == before


# [claude] WSS-SI-07
def test_wss_si_07__already_member_email_400(db, s):
    """WSS-SI-07 — an email that is already a member: 400.
    Rules: send_invitation R3."""
    member(db, s, s.UA, "member")
    commit_point(db)
    before = counts(db)
    # Then 1
    with pytest.raises(ValidationError) as exc:
        with clock():
            svc.send_invitation(
                db,
                workspace_id=s.W1.id,
                inviter_user_id=s.UO.id,
                email=s.EA,
                role="member",
            )
    # Then 2
    assert (
        exc.value.detail == "User with this email is already a member of this workspace"
    )
    # Then 3
    assert counts(db) == before


# [claude] WSS-SI-08
def test_wss_si_08__seats_full_400(db, s):
    """WSS-SI-08 — seats full: 400 with the limit in the text.
    Rules: send_invitation R3."""
    limit(db, s, 1)
    commit_point(db)
    before = counts(db)
    # Then 1
    with pytest.raises(ValidationError) as exc:
        with clock():
            svc.send_invitation(
                db,
                workspace_id=s.W1.id,
                inviter_user_id=s.UO.id,
                email=s.ED,
                role="member",
            )
    # Then 2
    assert exc.value.detail == (
        "Workspace has reached maximum member limit (1). "
        "Upgrade subscription to add more members."
    )
    # Then 3
    assert counts(db) == before


# [claude] WSS-SI-09
@pytest.mark.xfail(strict=True, reason=BUG_1873)
def test_wss_si_09__second_pending_invitation_refused(db, s):
    """WSS-SI-09 — a second pending invitation to the same email is refused (pass-through).
    Rules: send_invitation R2 (manager R4) [BUG-1873]."""
    invitation(db, s, "J", s.ED)
    commit_point(db)
    before = counts(db)
    # Then 1
    with pytest.raises(ValidationError) as exc:
        with clock():
            svc.send_invitation(
                db,
                workspace_id=s.W1.id,
                inviter_user_id=s.UO.id,
                email=s.ED,
                role="member",
            )
    # Then 2
    assert exc.value.detail == "This email is already invited to this workspace"
    # Then 3
    assert counts(db) == before


# [claude] WSS-SI-10
@pytest.mark.xfail(strict=True, reason=BUG_1871)
def test_wss_si_10__negative_limit_means_no_limit(db, s):
    """WSS-SI-10 — a negative limit means no limit (pass-through).
    Rules: send_invitation R2 (manager R8) [BUG-1871]."""
    limit(db, s, -1)
    commit_point(db)
    w1_id = s.W1.id
    with clock():
        result = svc.send_invitation(
            db, workspace_id=w1_id, inviter_user_id=s.UO.id, email=s.ED, role="member"
        )
    # Then 1
    assert isinstance(result, WorkspaceInvitation)
    db.rollback()
    # Then 2
    assert inv_count(db, w1_id, s.ED) == 1


# [claude] WSS-SI-11
@pytest.mark.xfail(strict=True, reason=BUG_1404)
def test_wss_si_11__ip_and_user_agent_reach_invitation_sent(db, s):
    """WSS-SI-11 — IP and user agent reach the invitation_sent row.
    Rules: send_invitation R4 [BUG-1404]."""
    commit_point(db)
    w1_id = s.W1.id
    with clock():
        result = svc.send_invitation(
            db,
            workspace_id=w1_id,
            inviter_user_id=s.UO.id,
            email=s.ED,
            role="member",
            ip_address="203.0.113.7",
            user_agent="Mozilla/5.0 Test",
        )
    # Then 1
    assert isinstance(result, WorkspaceInvitation)
    # Then 2
    rows = audit(db, w1_id, "invitation_sent")
    assert len(rows) == 1
    # Then 3
    assert rows[0].ip_address == "203.0.113.7"
    assert rows[0].user_agent == "Mozilla/5.0 Test"


# [claude] WSS-SI-12
def test_wss_si_12__failing_commit_nothing_saved(db, s):
    """WSS-SI-12 — a failing commit rolls back, nothing saved.
    Rules: send_invitation R3; TC4."""
    commit_point(db)
    before = counts(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb, clock():
            svc.send_invitation(
                db,
                workspace_id=s.W1.id,
                inviter_user_id=s.UO.id,
                email=s.ED,
                role="member",
            )
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert counts(db) == before


# [claude] WSS-SI-13
def test_wss_si_13__failing_refresh_leaves_invitation_saved(db, s):
    """WSS-SI-13 — a failing re-read leaves the invitation saved.
    Rules: send_invitation R2; TC5."""
    commit_point(db)
    w1_id = s.W1.id
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db), clock():
            svc.send_invitation(
                db,
                workspace_id=w1_id,
                inviter_user_id=s.UO.id,
                email=s.ED,
                role="member",
            )
    assert str(exc.value) == "boom"
    db.rollback()
    # Then 2
    assert inv_count(db, w1_id, s.ED) == 1


# [claude] WSS-SI-14
@pytest.mark.xfail(strict=True, reason=BUG_2256)
def test_wss_si_14__position_256_refused_by_invite_request(s):
    """WSS-SI-14 — a position of 256 characters is refused by InviteUserRequest.
    Rules: update_workspace R5a [BUG-2256] (InviteUserRequest.position)."""
    # Then 1
    with pytest.raises(PydanticValidationError):
        InviteUserRequest(email=s.ED, role="member", position="p" * 256)


# [claude] WSS-SI-15
def test_wss_si_15__position_255_accepted_by_invite_request(s):
    """WSS-SI-15 — a position of 255 characters is accepted by InviteUserRequest.
    Rules: update_workspace R5a (InviteUserRequest.position)."""
    result = InviteUserRequest(email=s.ED, role="member", position="p" * 255)
    # Then 1
    assert result.position == "p" * 255


# =========================================================================== #
# list_invitations
# =========================================================================== #


# [claude] WSS-LI-01
def test_wss_li_01__default_pending_unexpired_only(db, s):
    """WSS-LI-01 — by default only pending, unexpired invitations of the workspace.
    Rules: list_invitations R1, R2, R3."""
    i1 = invitation(db, s, "I1", s.EA)
    invitation(db, s, "I2", s.EB, expires_at=NOW - DAY, invited_by_user_id=s.UA.id)
    invitation(db, s, "I3", s.EC, status="accepted", invited_by_user_id=s.UB.id)
    invitation(db, s, "I4", s.ED, status="cancelled", invited_by_user_id=None)
    invitation(db, s, "I0", s.EA, workspace_id=s.W0.id, invited_by_user_id=s.U0.id)
    invitation(db, s, "I9", s.EA, workspace_id=s.W2.id, invited_by_user_id=s.U2.id)
    with clock():
        result = svc.list_invitations(
            db, workspace_id=s.W1.id, requesting_user_id=s.UO.id
        )
    # Then 1
    assert ids0(result) == {i1.id}
    # Then 2
    assert result[0][1].id == s.W1.id
    # Then 3
    assert {i.id: (p.id if p else None) for (i, w, p) in result} == {i1.id: s.UO.id}


# [claude] WSS-LI-02
def test_wss_li_02__include_expired_every_invitation(db, s):
    """WSS-LI-02 — include_expired returns every invitation of the workspace, any status.
    Rules: list_invitations R2."""
    i1 = invitation(db, s, "I1", s.EA)
    i2 = invitation(db, s, "I2", s.EB, expires_at=NOW - DAY, invited_by_user_id=s.UA.id)
    i3 = invitation(db, s, "I3", s.EC, status="accepted", invited_by_user_id=s.UB.id)
    i4 = invitation(db, s, "I4", s.ED, status="cancelled", invited_by_user_id=None)
    invitation(db, s, "I0", s.EA, workspace_id=s.W0.id, invited_by_user_id=s.U0.id)
    invitation(db, s, "I9", s.EA, workspace_id=s.W2.id, invited_by_user_id=s.U2.id)
    with clock():
        result = svc.list_invitations(
            db, workspace_id=s.W1.id, requesting_user_id=s.UO.id, include_expired=True
        )
    # Then 1
    assert ids0(result) == {i1.id, i2.id, i3.id, i4.id}
    # Then 2
    assert all(w.id == s.W1.id for (i, w, p) in result)
    # Then 3
    assert {i.id: (p.id if p else None) for (i, w, p) in result} == {
        i1.id: s.UO.id,
        i2.id: s.UA.id,
        i3.id: s.UB.id,
        i4.id: None,
    }


# [claude] WSS-LI-03
def test_wss_li_03__invitation_without_inviter_paired_with_none(db, s):
    """WSS-LI-03 — an invitation without an inviter is paired with None.
    Rules: list_invitations R3."""
    i1 = invitation(db, s, "I1", s.EA, invited_by_user_id=None)
    i2 = invitation(db, s, "I2", s.EB, invited_by_user_id=s.UA.id)
    i3 = invitation(db, s, "I3", s.EC)
    with clock():
        result = svc.list_invitations(
            db, workspace_id=s.W1.id, requesting_user_id=s.UO.id
        )
    # Then 1
    assert ids0(result) == {i1.id, i2.id, i3.id}
    # Then 2
    assert {i.id: (p.id if p else None) for (i, w, p) in result} == {
        i1.id: None,
        i2.id: s.UA.id,
        i3.id: s.UO.id,
    }


# [claude] WSS-LI-04
def test_wss_li_04__active_manager_may_not_list(db, s):
    """WSS-LI-04 — an active manager may not list invitations.
    Rules: list_invitations R1."""
    member(db, s, s.UA, "manager")
    invitation(db, s, "I1", s.EB, invited_by_user_id=s.UB.id)
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc.list_invitations(db, workspace_id=s.W1.id, requesting_user_id=s.UA.id)
    # Then 2
    assert exc.value.detail == OWNONLY


# [claude] WSS-LI-05
def test_wss_li_05__read_neither_commits_nor_rolls_back(db, s):
    """WSS-LI-05 — the read neither commits nor rolls back.
    Rules: list_invitations R6; TC6."""
    i1 = invitation(db, s, "I1", s.EA)
    i2 = invitation(db, s, "I2", s.EB, invited_by_user_id=s.UA.id)
    i1_id, i2_id = i1.id, i2.id
    commit_point(db)
    x_id = add_x(db, s)
    w1_id, uo_id, ua_id = s.W1.id, s.UO.id, s.UA.id
    with spies(db) as (cm, rb), clock():
        result = svc.list_invitations(db, workspace_id=w1_id, requesting_user_id=uo_id)
    # Then 1
    assert {i.id: (p.id if p else None) for (i, w, p) in result} == {
        i1_id: uo_id,
        i2_id: ua_id,
    }
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert x_count(db, x_id) == 1
    db.rollback()
    # Then 5
    assert x_count(db, x_id) == 0


# [claude] WSS-LI-06
@pytest.mark.xfail(strict=True, reason=BUG_2252)
def test_wss_li_06__inviters_read_together(db, s):
    """WSS-LI-06 — inviters are read together.
    Rules: list_invitations R5 [BUG-2252]."""
    member(db, s, s.UA, "member")
    member(db, s, s.UB, "member")
    member(db, s, s.UC, "member")
    member(db, s, s.UQ, "member")
    invitation(db, s, "J1", s.ED)
    invitation(db, s, "J2", s.ED, invited_by_user_id=s.UA.id)
    invitation(db, s, "J3", s.ED, invited_by_user_id=s.UB.id)
    invitation(db, s, "J4", s.ED, invited_by_user_id=s.UC.id)
    invitation(db, s, "J5", s.ED, invited_by_user_id=s.UQ.id)
    commit_point(db)
    kw = {"workspace_id": s.W1.id, "requesting_user_id": s.UO.id}
    with recorder(db) as stmts, clock():
        result = svc.list_invitations(db, **kw)
    # Then 1
    assert len(result) == 5
    # Then 2
    assert len(stmts) <= 3


# [claude] WSS-LI-07
def test_wss_li_07__invitation_query_ordered(db, s):
    """WSS-LI-07 — the invitation query is ordered (pass-through).
    Rules: list_invitations R4 [BUG-1401]."""
    invitation(db, s, "I1", s.EA)
    commit_point(db)
    kw = {"workspace_id": s.W1.id, "requesting_user_id": s.UO.id}
    with recorder(db) as stmts, clock():
        result = svc.list_invitations(db, **kw)
    # Then 1
    assert len(result) == 1
    # Then 2
    assert any(
        "workspace_invitations" in st and "ORDER BY" in st.upper() for st in stmts
    )


# =========================================================================== #
# accept_invitation
# =========================================================================== #


def member_row(db, member_id):
    return db.scalars(
        select(WorkspaceMember).where(WorkspaceMember.id == member_id)
    ).one()


def inv_row(db, inv_id):
    return db.scalars(
        select(WorkspaceInvitation).where(WorkspaceInvitation.id == inv_id)
    ).one()


# [claude] WSS-AI-01
def test_wss_ai_01__accepting_makes_user_member(db, s):
    """WSS-AI-01 — accepting makes the user a member with the invitation's role and position.
    Rules: accept_invitation R1, R4, R7; TC1, TC2."""
    i = invitation(db, s, "I", s.EA, role="manager", position="Lead")
    commit_point(db)
    i_id, w1_id, ua_id = i.id, s.W1.id, s.UA.id
    with clock():
        result = svc.accept_invitation(
            db,
            workspace_id=w1_id,
            token=f"tok-I-{s.TAG}",
            current_user_id=ua_id,
            current_user_email=s.EA,
        )
    # Then 1
    assert isinstance(result, WorkspaceMember)
    assert not (
        {c.key for c in sa_inspect(result).mapper.column_attrs}
        & sa_inspect(result).expired_attributes
    )
    m_id = result.id
    db.rollback()
    # Then 2
    m = member_row(db, m_id)
    assert m.workspace_id == w1_id
    assert m.user_id == ua_id
    assert m.status == "active"
    assert m.role == "manager"
    assert m.position == "Lead"
    # Then 3
    row = inv_row(db, i_id)
    assert row.status == "accepted"
    assert row.accepted_by_user_id == ua_id
    # Then 4
    assert len(audit(db, w1_id, "invitation_accepted")) == 1


# [claude] WSS-AI-02
def test_wss_ai_02__given_position_replaces_invitations(db, s):
    """WSS-AI-02 — a given position replaces the invitation's.
    Rules: accept_invitation R3."""
    invitation(db, s, "I", s.EA, position="Lead")
    commit_point(db)
    with clock():
        result = svc.accept_invitation(
            db,
            workspace_id=s.W1.id,
            token=f"tok-I-{s.TAG}",
            current_user_id=s.UA.id,
            current_user_email=s.EA,
            position="Chief",
        )
    # Then 1
    assert result.position == "Chief"
    m_id = result.id
    db.rollback()
    # Then 2
    assert member_row(db, m_id).position == "Chief"


# [claude] WSS-AI-03
def test_wss_ai_03__empty_position_replaces_too(db, s):
    """WSS-AI-03 — an empty position replaces the invitation's too.
    Rules: accept_invitation R3."""
    invitation(db, s, "I", s.EA, position="Lead")
    commit_point(db)
    with clock():
        result = svc.accept_invitation(
            db,
            workspace_id=s.W1.id,
            token=f"tok-I-{s.TAG}",
            current_user_id=s.UA.id,
            current_user_email=s.EA,
            position="",
        )
    # Then 1
    assert result.position == ""
    m_id = result.id
    db.rollback()
    # Then 2
    assert member_row(db, m_id).position == ""


# [claude] WSS-AI-04
def test_wss_ai_04__w2_invitation_under_w1_400(db, s):
    """WSS-AI-04 — a valid invitation of W2 used under W1: 400, nothing changed.
    Rules: accept_invitation R2, R5."""
    i = invitation(db, s, "I", s.EA, workspace_id=s.W2.id, invited_by_user_id=s.U2.id)
    commit_point(db)
    before = counts(db)
    i_before = snap(i)
    x_id = add_x(db, s)
    # Then 1
    with pytest.raises(ValidationError) as exc:
        with clock():
            svc.accept_invitation(
                db,
                workspace_id=s.W1.id,
                token=f"tok-I-{s.TAG}",
                current_user_id=s.UA.id,
                current_user_email=s.EA,
                position="Chief",
            )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Invitation does not belong to this workspace"
    # Then 4
    assert x_count(db, x_id) == 0
    # Then 5
    assert reread_snap(db, WorkspaceInvitation, i_before["id"]) == i_before
    # Then 6
    assert counts(db) == before


# [claude] WSS-AI-05
def test_wss_ai_05__w0_invitation_under_w1_400(db, s):
    """WSS-AI-05 — a valid invitation of W0 used under W1: 400.
    Rules: accept_invitation R2."""
    i = invitation(db, s, "I", s.EA, workspace_id=s.W0.id, invited_by_user_id=s.U0.id)
    commit_point(db)
    before = counts(db)
    i_before = snap(i)
    # Then 1
    with pytest.raises(ValidationError) as exc:
        with clock():
            svc.accept_invitation(
                db,
                workspace_id=s.W1.id,
                token=f"tok-I-{s.TAG}",
                current_user_id=s.UA.id,
                current_user_email=s.EA,
            )
    # Then 2
    assert exc.value.detail == "Invitation does not belong to this workspace"
    # Then 3
    assert reread_snap(db, WorkspaceInvitation, i_before["id"]) == i_before
    # Then 4
    assert counts(db) == before


# [claude] WSS-AI-06
def test_wss_ai_06__expired_other_workspace_gets_expiry_message(db, s):
    """WSS-AI-06 — an expired invitation of another workspace gets the expiry message.
    Rules: accept_invitation R1, R2."""
    invitation(db, s, "I", s.EA, workspace_id=s.W2.id, expires_at=NOW - DAY)
    commit_point(db)
    before = counts(db)
    # Then 1
    with pytest.raises(ValidationError) as exc:
        with clock():
            svc.accept_invitation(
                db,
                workspace_id=s.W1.id,
                token=f"tok-I-{s.TAG}",
                current_user_id=s.UA.id,
                current_user_email=s.EA,
            )
    # Then 2
    assert (
        exc.value.detail == "Invitation has expired. Please request a new invitation."
    )
    # Then 3
    assert counts(db) == before


# [claude] WSS-AI-07
def test_wss_ai_07__unknown_token_400(db, s):
    """WSS-AI-07 — an unknown token: 400, pending changes discarded.
    Rules: accept_invitation R1; TX1, TC3."""
    commit_point(db)
    before = counts(db)
    x_id = add_x(db, s)
    # Then 1
    with pytest.raises(ValidationError) as exc:
        with clock():
            svc.accept_invitation(
                db,
                workspace_id=s.W1.id,
                token=f"tok-NONE-{s.TAG}",
                current_user_id=s.UA.id,
                current_user_email=s.EA,
            )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Invalid invitation token"
    # Then 4
    assert isinstance(exc.value.__context__, ValueError)
    # Then 5
    assert x_count(db, x_id) == 0
    # Then 6
    assert counts(db) == before


# [claude] WSS-AI-08
def test_wss_ai_08__another_email_400(db, s):
    """WSS-AI-08 — another email: 400 naming both emails.
    Rules: accept_invitation R1."""
    i = invitation(db, s, "I", s.EA)
    commit_point(db)
    before = counts(db)
    i_before = snap(i)
    # Then 1
    with pytest.raises(ValidationError) as exc:
        with clock():
            svc.accept_invitation(
                db,
                workspace_id=s.W1.id,
                token=f"tok-I-{s.TAG}",
                current_user_id=s.UB.id,
                current_user_email=s.EB,
            )
    # Then 2
    assert (
        exc.value.detail
        == f"This invitation was sent to {s.EA}. You cannot accept it with {s.EB}."
    )
    # Then 3
    assert reread_snap(db, WorkspaceInvitation, i_before["id"]) == i_before
    # Then 4
    assert counts(db) == before


# [claude] WSS-AI-09
def test_wss_ai_09__already_member_400_position_rolled_back(db, s):
    """WSS-AI-09 — already a member: 400, and the position override is rolled back.
    Rules: accept_invitation R4, R5."""
    member(db, s, s.UA, "viewer")
    i = invitation(db, s, "I", s.EA, position="Lead")
    i_id = i.id
    commit_point(db)
    before = counts(db)
    # Then 1
    with pytest.raises(ValidationError) as exc:
        with clock():
            svc.accept_invitation(
                db,
                workspace_id=s.W1.id,
                token=f"tok-I-{s.TAG}",
                current_user_id=s.UA.id,
                current_user_email=s.EA,
                position="Chief",
            )
    # Then 2
    assert exc.value.detail == "User is already a member of this workspace"
    # Then 3
    row = reread(db, WorkspaceInvitation, i_id)
    assert row.position == "Lead"
    assert row.status == "pending"
    # Then 4
    assert counts(db) == before


# [claude] WSS-AI-10
def test_wss_ai_10__seats_full_at_accept_400(db, s):
    """WSS-AI-10 — seats full at accept: 400.
    Rules: accept_invitation R4."""
    limit(db, s, 1)
    i = invitation(db, s, "I", s.EA)
    commit_point(db)
    before = counts(db)
    i_before = snap(i)
    # Then 1
    with pytest.raises(ValidationError) as exc:
        with clock():
            svc.accept_invitation(
                db,
                workspace_id=s.W1.id,
                token=f"tok-I-{s.TAG}",
                current_user_id=s.UA.id,
                current_user_email=s.EA,
            )
    # Then 2
    assert exc.value.detail == (
        "Workspace has reached maximum member limit (1). "
        "Upgrade subscription to add more members."
    )
    # Then 3
    assert reread_snap(db, WorkspaceInvitation, i_before["id"]) == i_before
    # Then 4
    assert counts(db) == before


# [claude] WSS-AI-11
def test_wss_ai_11__failing_commit_no_member(db, s):
    """WSS-AI-11 — a failing commit rolls back: no member, invitation still pending.
    Rules: accept_invitation R5, R7; TC4."""
    i = invitation(db, s, "I", s.EA)
    commit_point(db)
    before = counts(db)
    i_before = snap(i)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb, clock():
            svc.accept_invitation(
                db,
                workspace_id=s.W1.id,
                token=f"tok-I-{s.TAG}",
                current_user_id=s.UA.id,
                current_user_email=s.EA,
            )
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert reread_snap(db, WorkspaceInvitation, i_before["id"]) == i_before
    # Then 4
    assert counts(db) == before


# [claude] WSS-AI-12
def test_wss_ai_12__failing_refresh_leaves_membership_saved(db, s):
    """WSS-AI-12 — a failing re-read leaves the membership saved.
    Rules: accept_invitation R7; TC5."""
    invitation(db, s, "I", s.EA)
    commit_point(db)
    w1_id, ua_id = s.W1.id, s.UA.id
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db), clock():
            svc.accept_invitation(
                db,
                workspace_id=w1_id,
                token=f"tok-I-{s.TAG}",
                current_user_id=ua_id,
                current_user_email=s.EA,
            )
    assert str(exc.value) == "boom"
    db.rollback()
    # Then 2
    n = db.scalar(
        select(func.count())
        .select_from(WorkspaceMember)
        .where(
            WorkspaceMember.workspace_id == w1_id,
            WorkspaceMember.user_id == ua_id,
            WorkspaceMember.status == "active",
        )
    )
    assert n == 1


# [claude] WSS-AI-13
@pytest.mark.xfail(strict=True, reason=BUG_1982)
def test_wss_ai_13__removed_member_comes_back_on_same_row(db, s):
    """WSS-AI-13 — a removed member comes back on the same row (pass-through).
    Rules: accept_invitation R4 (manager R2a) [BUG-1982]."""
    ma = member(db, s, s.UA, "viewer", status="inactive")
    invitation(db, s, "I", s.EA, role="manager")
    ma_id = ma.id
    commit_point(db)
    with clock():
        result = svc.accept_invitation(
            db,
            workspace_id=s.W1.id,
            token=f"tok-I-{s.TAG}",
            current_user_id=s.UA.id,
            current_user_email=s.EA,
        )
    # Then 1
    assert result.id == ma_id
    db.rollback()
    # Then 2
    m = member_row(db, ma_id)
    assert m.status == "active"
    assert m.role == "manager"
    assert m.left_at is None


# [claude] WSS-AI-14
@pytest.mark.xfail(strict=True, reason=BUG_1874)
def test_wss_ai_14__other_pending_invitations_cancelled(db, s):
    """WSS-AI-14 — other pending invitations to the same email are cancelled (pass-through).
    Rules: accept_invitation R4 (manager R5) [BUG-1874]."""
    invitation(db, s, "I", s.EA)
    j = invitation(db, s, "J", s.EA)
    j_id = j.id
    commit_point(db)
    with clock():
        result = svc.accept_invitation(
            db,
            workspace_id=s.W1.id,
            token=f"tok-I-{s.TAG}",
            current_user_id=s.UA.id,
            current_user_email=s.EA,
        )
    # Then 1
    assert isinstance(result, WorkspaceMember)
    db.rollback()
    # Then 2
    assert inv_row(db, j_id).status == "cancelled"


# [claude] WSS-AI-15
@pytest.mark.xfail(strict=True, reason=BUG_1987)
def test_wss_ai_15__expiring_exactly_now_refused(db, s):
    """WSS-AI-15 — an invitation expiring exactly now is refused (pass-through).
    Rules: accept_invitation R1 (manager validate R2) [BUG-1987]."""
    i = invitation(db, s, "I", s.EA, expires_at=NOW)
    commit_point(db)
    i_before = snap(i)
    # Then 1
    with pytest.raises(ValidationError) as exc:
        with clock():
            svc.accept_invitation(
                db,
                workspace_id=s.W1.id,
                token=f"tok-I-{s.TAG}",
                current_user_id=s.UA.id,
                current_user_email=s.EA,
            )
    # Then 2
    assert (
        exc.value.detail == "Invitation has expired. Please request a new invitation."
    )
    # Then 3
    assert reread_snap(db, WorkspaceInvitation, i_before["id"]) == i_before


# [claude] WSS-AI-16
@pytest.mark.xfail(strict=True, reason=BUG_1872)
def test_wss_ai_16__negative_limit_no_limit_at_accept(db, s):
    """WSS-AI-16 — a negative limit means no limit at accept (pass-through).
    Rules: accept_invitation R4 (manager add R5a) [BUG-1872]."""
    limit(db, s, -1)
    invitation(db, s, "I", s.EA)
    commit_point(db)
    with clock():
        result = svc.accept_invitation(
            db,
            workspace_id=s.W1.id,
            token=f"tok-I-{s.TAG}",
            current_user_id=s.UA.id,
            current_user_email=s.EA,
        )
    # Then 1
    assert isinstance(result, WorkspaceMember)
    m_id = result.id
    db.rollback()
    # Then 2
    assert member_row(db, m_id).status == "active"


# [claude] WSS-AI-17
@pytest.mark.xfail(strict=True, reason=BUG_1985)
def test_wss_ai_17__new_member_records_inviter(db, s):
    """WSS-AI-17 — the new member records who invited them (pass-through).
    Rules: accept_invitation R4 (manager add R8) [BUG-1985]."""
    invitation(db, s, "I", s.EA)
    commit_point(db)
    uo_id = s.UO.id
    with clock():
        result = svc.accept_invitation(
            db,
            workspace_id=s.W1.id,
            token=f"tok-I-{s.TAG}",
            current_user_id=s.UA.id,
            current_user_email=s.EA,
        )
    # Then 1
    assert isinstance(result, WorkspaceMember)
    m_id = result.id
    db.rollback()
    # Then 2
    assert member_row(db, m_id).invited_by_user_id == uo_id


# [claude] WSS-AI-18
@pytest.mark.xfail(strict=True, reason=BUG_1404)
def test_wss_ai_18__ip_and_user_agent_reach_invitation_accepted(db, s):
    """WSS-AI-18 — IP and user agent reach the invitation_accepted row.
    Rules: accept_invitation R6 [BUG-1404]."""
    invitation(db, s, "I", s.EA)
    commit_point(db)
    w1_id = s.W1.id
    with clock():
        result = svc.accept_invitation(
            db,
            workspace_id=w1_id,
            token=f"tok-I-{s.TAG}",
            current_user_id=s.UA.id,
            current_user_email=s.EA,
            ip_address="203.0.113.7",
            user_agent="Mozilla/5.0 Test",
        )
    # Then 1
    assert isinstance(result, WorkspaceMember)
    # Then 2
    rows = audit(db, w1_id, "invitation_accepted")
    assert len(rows) == 1
    # Then 3
    assert rows[0].ip_address == "203.0.113.7"
    assert rows[0].user_agent == "Mozilla/5.0 Test"


# [claude] WSS-AI-19
@pytest.mark.xfail(strict=True, reason=BUG_2256)
def test_wss_ai_19__position_256_refused_by_accept_request(s):
    """WSS-AI-19 — a position of 256 characters is refused by AcceptInvitationRequest.
    Rules: update_workspace R5a [BUG-2256] (AcceptInvitationRequest.position)."""
    # Then 1
    with pytest.raises(PydanticValidationError):
        AcceptInvitationRequest(token=f"tok-I-{s.TAG}", position="p" * 256)


# [claude] WSS-AI-20
def test_wss_ai_20__position_255_accepted_by_accept_request(s):
    """WSS-AI-20 — a position of 255 characters is accepted by AcceptInvitationRequest.
    Rules: update_workspace R5a (AcceptInvitationRequest.position)."""
    result = AcceptInvitationRequest(token=f"tok-I-{s.TAG}", position="p" * 255)
    # Then 1
    assert result.position == "p" * 255


# =========================================================================== #
# cancel_invitation
# =========================================================================== #


# [claude] WSS-XI-01
def test_wss_xi_01__owner_cancels_pending_invitation(db, s):
    """WSS-XI-01 — the owner cancels a pending invitation; committed, None returned.
    Rules: cancel_invitation R1, R2; TC1, TX3."""
    i = invitation(db, s, "I", s.EA)
    commit_point(db)
    i_id, w1_id, uo_id = i.id, s.W1.id, s.UO.id
    with clock():
        result = svc.cancel_invitation(
            db, workspace_id=w1_id, invitation_id=i_id, canceller_user_id=uo_id
        )
    # Then 1
    assert result is None
    db.rollback()
    # Then 2
    assert inv_row(db, i_id).status == "cancelled"
    # Then 3
    rows = audit(db, w1_id, "invitation_cancelled")
    assert len(rows) == 1
    # Then 4
    assert rows[0].user_id == uo_id
    assert rows[0].metadata_json == {"invitation_id": i_id, "email": s.EA}


# [claude] WSS-XI-02
def test_wss_xi_02__no_reread_after_commit(db, s):
    """WSS-XI-02 — no re-read after the commit.
    Rules: cancel_invitation R2; TX3."""
    i = invitation(db, s, "I", s.EA)
    commit_point(db)
    i_id = i.id
    with refresh_trap(db) as rf, clock():
        result = svc.cancel_invitation(
            db, workspace_id=s.W1.id, invitation_id=i_id, canceller_user_id=s.UO.id
        )
    # Then 1
    assert result is None
    # Then 2
    assert rf.call_count == 0
    db.rollback()
    # Then 3
    assert inv_row(db, i_id).status == "cancelled"


# [claude] WSS-XI-03
def test_wss_xi_03__non_member_refused_first(db, s):
    """WSS-XI-03 — a non-member is refused first; pending changes stay pending.
    Rules: cancel_invitation R1; TX2."""
    i = invitation(db, s, "I", s.EA)
    commit_point(db)
    i_before = snap(i)
    x_id = add_x(db, s)
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc.cancel_invitation(
                db,
                workspace_id=s.W1.id,
                invitation_id=i_before["id"],
                canceller_user_id=s.U0.id,
            )
    # Then 2
    assert exc.value.detail == NOTMEM
    # Then 3
    assert not db.dirty and not db.new and not db.deleted
    # Then 4
    assert x_count(db, x_id) == 1
    # Then 5
    assert reread_snap(db, WorkspaceInvitation, i_before["id"]) == i_before


# [claude] WSS-XI-04
def test_wss_xi_04__manager_cancelling_stays_403(db, s):
    """WSS-XI-04 — a manager cancelling stays 403; the rollback discards pending changes.
    Rules: cancel_invitation R3; TX1, TC3."""
    member(db, s, s.UA, "manager")
    i = invitation(db, s, "I", s.EB)
    commit_point(db)
    before = counts(db)
    i_before = snap(i)
    x_id = add_x(db, s)
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc.cancel_invitation(
                db,
                workspace_id=s.W1.id,
                invitation_id=i_before["id"],
                canceller_user_id=s.UA.id,
            )
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == "Only the workspace owner can cancel invitations"
    # Then 4
    assert isinstance(exc.value.__context__, ValueError)
    # Then 5
    assert x_count(db, x_id) == 0
    # Then 6
    assert reread_snap(db, WorkspaceInvitation, i_before["id"]) == i_before
    # Then 7
    assert counts(db) == before


# [claude] WSS-XI-05
def test_wss_xi_05__owner_of_w2_cannot_cancel_w1_invitation(db, s):
    """WSS-XI-05 — the owner of W2, a "member" in W1, cannot cancel W1's invitation.
    Rules: cancel_invitation R2, R3."""
    member(db, s, s.U2, "member")
    i = invitation(db, s, "I", s.EA)
    commit_point(db)
    i_before = snap(i)
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc.cancel_invitation(
                db,
                workspace_id=s.W1.id,
                invitation_id=i_before["id"],
                canceller_user_id=s.U2.id,
            )
    # Then 2
    assert exc.value.detail == "Only the workspace owner can cancel invitations"
    # Then 3
    assert reread_snap(db, WorkspaceInvitation, i_before["id"]) == i_before


# [claude] WSS-XI-06
def test_wss_xi_06__invitation_not_found_text_reaches_caller(db, s):
    """WSS-XI-06 — "Invitation not found" text reaches the caller (holds before and after
    BUG-2251).
    Rules: cancel_invitation R3."""
    commit_point(db)
    before = counts(db)
    # Then 1
    with pytest.raises(APIException) as exc:
        with clock():
            svc.cancel_invitation(
                db,
                workspace_id=s.W1.id,
                invitation_id=MISSING,
                canceller_user_id=s.UO.id,
            )
    # Then 2
    assert exc.value.detail == "Invitation not found"
    # Then 3
    assert counts(db) == before


# [claude] WSS-XI-07
def test_wss_xi_07__cannot_cancel_accepted_text_reaches_caller(db, s):
    """WSS-XI-07 — "Cannot cancel ... accepted" text reaches the caller (holds before and
    after BUG-2251).
    Rules: cancel_invitation R3."""
    i = invitation(db, s, "I", s.EA, status="accepted")
    commit_point(db)
    before = counts(db)
    i_before = snap(i)
    # Then 1
    with pytest.raises(APIException) as exc:
        with clock():
            svc.cancel_invitation(
                db,
                workspace_id=s.W1.id,
                invitation_id=i_before["id"],
                canceller_user_id=s.UO.id,
            )
    # Then 2
    assert exc.value.detail == "Cannot cancel invitation that is accepted"
    # Then 3
    assert reread_snap(db, WorkspaceInvitation, i_before["id"]) == i_before
    # Then 4
    assert counts(db) == before


# [claude] WSS-XI-08
@pytest.mark.xfail(strict=True, reason=BUG_2251)
def test_wss_xi_08__unknown_invitation_404(db, s):
    """WSS-XI-08 — an unknown invitation answers 404.
    Rules: cancel_invitation R3 [BUG-2251]."""
    commit_point(db)
    before = counts(db)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        with clock():
            svc.cancel_invitation(
                db,
                workspace_id=s.W1.id,
                invitation_id=MISSING,
                canceller_user_id=s.UO.id,
            )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Invitation not found"
    # Then 4
    assert not db.dirty and not db.new
    # Then 5
    assert counts(db) == before


# [claude] WSS-XI-09
@pytest.mark.xfail(strict=True, reason=BUG_2251)
def test_wss_xi_09__accepted_invitation_400(db, s):
    """WSS-XI-09 — an accepted invitation answers 400.
    Rules: cancel_invitation R3 [BUG-2251]."""
    i = invitation(db, s, "I", s.EA, status="accepted")
    commit_point(db)
    i_before = snap(i)
    # Then 1
    with pytest.raises(ValidationError) as exc:
        with clock():
            svc.cancel_invitation(
                db,
                workspace_id=s.W1.id,
                invitation_id=i_before["id"],
                canceller_user_id=s.UO.id,
            )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot cancel invitation that is accepted"
    # Then 4
    assert not db.dirty and not db.new
    # Then 5
    assert reread_snap(db, WorkspaceInvitation, i_before["id"]) == i_before


# [claude] WSS-XI-10
@pytest.mark.xfail(strict=True, reason=BUG_2251)
def test_wss_xi_10__cancelled_invitation_400(db, s):
    """WSS-XI-10 — a cancelled invitation answers 400.
    Rules: cancel_invitation R3 [BUG-2251]."""
    i = invitation(db, s, "I", s.EA, status="cancelled")
    commit_point(db)
    i_before = snap(i)
    # Then 1
    with pytest.raises(ValidationError) as exc:
        with clock():
            svc.cancel_invitation(
                db,
                workspace_id=s.W1.id,
                invitation_id=i_before["id"],
                canceller_user_id=s.UO.id,
            )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot cancel invitation that is cancelled"
    # Then 4
    assert not db.dirty and not db.new
    # Then 5
    assert reread_snap(db, WorkspaceInvitation, i_before["id"]) == i_before


# [claude] WSS-XI-11
@pytest.mark.xfail(strict=True, reason=BUG_2251)
def test_wss_xi_11__w0_invitation_404(db, s):
    """WSS-XI-11 — an invitation of W0 answers 404 "Invitation not found".
    Rules: cancel_invitation R3 [BUG-2251] (manager R2, BUG-1981: both must be fixed)."""
    i = invitation(db, s, "I", s.EA, workspace_id=s.W0.id, invited_by_user_id=s.U0.id)
    commit_point(db)
    i_before = snap(i)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        with clock():
            svc.cancel_invitation(
                db,
                workspace_id=s.W1.id,
                invitation_id=i_before["id"],
                canceller_user_id=s.UO.id,
            )
    # Then 2
    assert exc.value.detail == "Invitation not found"
    # Then 3
    assert not db.dirty and not db.new
    # Then 4
    assert reread_snap(db, WorkspaceInvitation, i_before["id"]) == i_before


# [claude] WSS-XI-12
@pytest.mark.xfail(strict=True, reason=BUG_2251)
def test_wss_xi_12__w2_invitation_404(db, s):
    """WSS-XI-12 — an invitation of W2 answers 404 "Invitation not found".
    Rules: cancel_invitation R3 [BUG-2251] (manager R2, BUG-1981: both must be fixed)."""
    i = invitation(db, s, "I", s.EA, workspace_id=s.W2.id, invited_by_user_id=s.U2.id)
    commit_point(db)
    i_before = snap(i)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        with clock():
            svc.cancel_invitation(
                db,
                workspace_id=s.W1.id,
                invitation_id=i_before["id"],
                canceller_user_id=s.UO.id,
            )
    # Then 2
    assert exc.value.detail == "Invitation not found"
    # Then 3
    assert not db.dirty and not db.new
    # Then 4
    assert reread_snap(db, WorkspaceInvitation, i_before["id"]) == i_before


# [claude] WSS-XI-13
@pytest.mark.xfail(strict=True, reason=BUG_1986)
def test_wss_xi_13__non_owner_gets_owner_message_first(db, s):
    """WSS-XI-13 — a non-owner gets the owner message first, even for an unknown id
    (pass-through).
    Rules: cancel_invitation R2 (manager R1) [BUG-1986]."""
    member(db, s, s.UA, "manager")
    commit_point(db)
    before = counts(db)
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        with clock():
            svc.cancel_invitation(
                db,
                workspace_id=s.W1.id,
                invitation_id=MISSING,
                canceller_user_id=s.UA.id,
            )
    # Then 2
    assert exc.value.detail == "Only the workspace owner can cancel invitations"
    # Then 3
    assert counts(db) == before


# [claude] WSS-XI-14
@pytest.mark.xfail(strict=True, reason=BUG_1404)
def test_wss_xi_14__ip_and_user_agent_reach_invitation_cancelled(db, s):
    """WSS-XI-14 — IP and user agent reach the invitation_cancelled row.
    Rules: cancel_invitation R4 [BUG-1404]."""
    i = invitation(db, s, "I", s.EA)
    commit_point(db)
    w1_id = s.W1.id
    with clock():
        result = svc.cancel_invitation(
            db,
            workspace_id=w1_id,
            invitation_id=i.id,
            canceller_user_id=s.UO.id,
            ip_address="203.0.113.7",
            user_agent="Mozilla/5.0 Test",
        )
    # Then 1
    assert result is None
    # Then 2
    rows = audit(db, w1_id, "invitation_cancelled")
    assert len(rows) == 1
    # Then 3
    assert rows[0].ip_address == "203.0.113.7"
    assert rows[0].user_agent == "Mozilla/5.0 Test"


# [claude] WSS-XI-15
def test_wss_xi_15__failing_commit_invitation_stays_pending(db, s):
    """WSS-XI-15 — a failing commit rolls back, the invitation stays pending.
    Rules: cancel_invitation R2; TC4."""
    i = invitation(db, s, "I", s.EA)
    commit_point(db)
    before = counts(db)
    i_before = snap(i)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb, clock():
            svc.cancel_invitation(
                db,
                workspace_id=s.W1.id,
                invitation_id=i_before["id"],
                canceller_user_id=s.UO.id,
            )
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert reread_snap(db, WorkspaceInvitation, i_before["id"]) == i_before
    # Then 4
    assert counts(db) == before


# [claude] WSS-XI-16
def test_wss_xi_16__cannot_cancel_cancelled_text_reaches_caller(db, s):
    """WSS-XI-16 — "Cannot cancel ... cancelled" text reaches the caller (holds before and
    after BUG-2251).
    Rules: cancel_invitation R3."""
    i = invitation(db, s, "I", s.EA, status="cancelled")
    commit_point(db)
    before = counts(db)
    i_before = snap(i)
    # Then 1
    with pytest.raises(APIException) as exc:
        with clock():
            svc.cancel_invitation(
                db,
                workspace_id=s.W1.id,
                invitation_id=i_before["id"],
                canceller_user_id=s.UO.id,
            )
    # Then 2
    assert exc.value.detail == "Cannot cancel invitation that is cancelled"
    # Then 3
    assert reread_snap(db, WorkspaceInvitation, i_before["id"]) == i_before
    # Then 4
    assert counts(db) == before


# =========================================================================== #
# get_my_invitations
# =========================================================================== #


# [claude] WSS-MI-01
def test_wss_mi_01__pending_unexpired_in_every_workspace(db, s):
    """WSS-MI-01 — pending, unexpired invitations to the email in every workspace, with
    workspace and inviter.
    Rules: get_my_invitations R1, R2, R5."""
    i1 = invitation(db, s, "I1", s.EA)
    i2 = invitation(db, s, "I2", s.EA, workspace_id=s.W2.id, invited_by_user_id=s.U2.id)
    i5 = invitation(db, s, "I5", s.EA, workspace_id=s.W0.id, invited_by_user_id=None)
    invitation(
        db,
        s,
        "I0",
        s.EA,
        workspace_id=s.W0.id,
        expires_at=NOW - DAY,
        invited_by_user_id=s.U0.id,
    )
    invitation(db, s, "I3", s.EA, status="accepted", invited_by_user_id=s.UB.id)
    invitation(db, s, "I4", s.EB, invited_by_user_id=s.UC.id)
    with clock():
        result = svc.get_my_invitations(db, user_email=s.EA)
    # Then 1
    assert ids0(result) == {i1.id, i2.id, i5.id}
    # Then 2
    assert {i.id: (w.id, p.id if p else None) for (i, w, p) in result} == {
        i1.id: (s.W1.id, s.UO.id),
        i2.id: (s.W2.id, s.U2.id),
        i5.id: (s.W0.id, None),
    }


# [claude] WSS-MI-02
def test_wss_mi_02__invitation_to_own_workspace_listed(db, s):
    """WSS-MI-02 — an invitation to a workspace the user already belongs to is listed.
    Rules: get_my_invitations R3 (D8)."""
    member(db, s, s.UA, "viewer")
    i1 = invitation(db, s, "I1", s.EA)
    with clock():
        result = svc.get_my_invitations(db, user_email=s.EA)
    # Then 1
    assert ids0(result) == {i1.id}


# [claude] WSS-MI-03
def test_wss_mi_03__email_without_invitation_empty(db, s):
    """WSS-MI-03 — an email with no invitation gets an empty list.
    Rules: get_my_invitations R1."""
    invitation(db, s, "I1", s.EB)
    with clock():
        result = svc.get_my_invitations(db, user_email=s.ED)
    # Then 1
    assert result == []


# [claude] WSS-MI-04
def test_wss_mi_04__email_matches_ignoring_capitals(db, s):
    """WSS-MI-04 — the email matches ignoring capitals (pass-through).
    Rules: get_my_invitations R1 [BUG-1402]."""
    i1 = invitation(db, s, "I1", s.EA)
    with clock():
        result = svc.get_my_invitations(db, user_email=f"Ann.{s.TAG}@Acme.com")
    # Then 1
    assert ids0(result) == {i1.id}


# [claude] WSS-MI-05
def test_wss_mi_05__read_neither_commits_nor_rolls_back(db, s):
    """WSS-MI-05 — the read neither commits nor rolls back.
    Rules: get_my_invitations R5; TC6."""
    i1 = invitation(db, s, "I1", s.EA)
    i1_id = i1.id
    commit_point(db)
    x_id = add_x(db, s)
    with spies(db) as (cm, rb), clock():
        result = svc.get_my_invitations(db, user_email=s.EA)
    # Then 1
    assert ids0(result) == {i1_id}
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert x_count(db, x_id) == 1
    db.rollback()
    # Then 5
    assert x_count(db, x_id) == 0


# [claude] WSS-MI-06
@pytest.mark.xfail(strict=True, reason=BUG_2252)
def test_wss_mi_06__workspaces_and_inviters_read_together(db, s):
    """WSS-MI-06 — workspaces and inviters are read together.
    Rules: get_my_invitations R4 [BUG-2252]."""
    w3 = make_workspace(db)
    w4 = make_workspace(db)
    invitation(db, s, "J0", s.EA, workspace_id=s.W0.id, invited_by_user_id=s.U0.id)
    invitation(db, s, "J1", s.EA)
    invitation(db, s, "J2", s.EA, workspace_id=s.W2.id, invited_by_user_id=s.U2.id)
    invitation(db, s, "J3", s.EA, workspace_id=w3.id, invited_by_user_id=s.UB.id)
    invitation(db, s, "J4", s.EA, workspace_id=w4.id, invited_by_user_id=s.UC.id)
    commit_point(db)
    kw = {"user_email": s.EA}
    with recorder(db) as stmts, clock():
        result = svc.get_my_invitations(db, **kw)
    # Then 1
    assert len(result) == 5
    # Then 2
    assert len(stmts) <= 3


# [claude] WSS-MI-07
def test_wss_mi_07__invitation_query_ordered(db, s):
    """WSS-MI-07 — the invitation query is ordered (pass-through).
    Rules: get_my_invitations R1 [BUG-1401]."""
    invitation(db, s, "I1", s.EA)
    commit_point(db)
    kw = {"user_email": s.EA}
    with recorder(db) as stmts, clock():
        result = svc.get_my_invitations(db, **kw)
    # Then 1
    assert len(result) == 1
    # Then 2
    assert any(
        "workspace_invitations" in st and "ORDER BY" in st.upper() for st in stmts
    )
