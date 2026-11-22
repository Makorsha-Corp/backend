"""Unit tests for app/managers/project_manager.py.

Implements tests/unit/managers/project_manager.cases.md, one test per card, in
card order. Real Postgres session (`db` fixture), rolled back after each test.
The only thing patched in every test is the clock:
`app.managers.project_manager.utcnow` returns NOW (Conventions, Externals).
The commit spies of the "Rolled back" cards wrap `db.commit` (Conventions).

Every test that touches the database builds the Standing rows (fixture `S`,
attributes named as in the cards: `S.W1`, `S.UG`, `S.F1` ...). Given rows are
built by the helpers below (`proj`, `member`, `pmem`, `comp`, `ev`, `bulk`,
`set_owner`), one flush per row. `# Then N` marks the checks of the card's
Then line N.
"""
# ruff: noqa: SIM117, FURB157  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`;
# budgets are written as the cards write them, e.g. Decimal("0"))
import os
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import event, func, insert, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import DataError

from app.managers.project_manager import (
    PRIVILEGED_ROLES,
    PROJECT_LOG_FIELDS,
    project_manager,
)
from app.models.enums import (
    ProjectPriorityEnum,
    ProjectStatusEnum,
    ProjectVisibilityEnum,
)
from app.models.factory import Factory
from app.models.project import Project
from app.models.project_component import ProjectComponent
from app.models.project_event import ProjectEvent
from app.models.project_member import ProjectMember
from app.models.subscription_plan import SubscriptionPlan
from app.models.workspace_member import WorkspaceMember
from app.schemas.project import ProjectCreate, ProjectUpdate
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "PM = project_manager"
PM = project_manager

# Convention "MISSING": an id no row of any table has
MISSING = 999999999

# Conventions T0..T3, NOW (all naive)
T0 = datetime(2025, 12, 1, 8, 0, 0)  # noqa: DTZ001
T1 = datetime(2026, 1, 1, 9, 0, 0)  # noqa: DTZ001
T2 = datetime(2026, 1, 1, 10, 0, 0)  # noqa: DTZ001
T3 = datetime(2026, 1, 1, 11, 0, 0)  # noqa: DTZ001
NOW = datetime(2026, 3, 1, 10, 0, 0)  # noqa: DTZ001

PLANNING = ProjectStatusEnum.PLANNING
IN_PROGRESS = ProjectStatusEnum.IN_PROGRESS
COMPLETED = ProjectStatusEnum.COMPLETED
ON_HOLD = ProjectStatusEnum.ON_HOLD
CANCELLED = ProjectStatusEnum.CANCELLED


# Convention "XID(k)": an explicit row id no sequence gives
def XID(k):
    return 800_000_000 + (os.getpid() % 1_000_000) * 10 + k


# Convention "val(x)"
def val(x):
    return getattr(x, "value", x)


# Convention "idset(x)"
def idset(rows):
    return {r.id for r in rows}


# Convention "names(x)" (order is part of the check)
def names(rows):
    return [r.name for r in rows]


# --------------------------------------------------------------------------- #
# Externals: the clock, patched in every test
# --------------------------------------------------------------------------- #

@pytest.fixture(autouse=True)
def clock():
    with patch("app.managers.project_manager.utcnow", return_value=NOW) as m:
        yield m


# --------------------------------------------------------------------------- #
# Conventions -> Standing rows (built in this order, each flushed)
# --------------------------------------------------------------------------- #

def _add(db, row):
    db.add(row)
    db.flush()
    return row


# Given row "member(U, role, status="active", ws=W1)"
def member(db, S, u, role, status="active", ws=None):
    ws = ws or S.W1
    return _add(db, WorkspaceMember(workspace_id=ws.id, user_id=u.id, role=role, status=status))


@pytest.fixture
def S(db):
    s = SimpleNamespace()
    s.W0 = make_workspace(db)
    s.W1 = make_workspace(db)
    s.W2 = make_workspace(db)
    s.U1 = make_profile(db, name="Ana Rahman")
    s.U2 = make_profile(db, name="Bilal Khan")
    s.UG = make_profile(db, name="Mia Khan")
    member(db, s, s.U1, "ground-team")
    member(db, s, s.U2, "owner")
    member(db, s, s.UG, "ground-team")
    s.F0 = _add(db, Factory(workspace_id=s.W0.id, name="Factory Zero", abbreviation="F0"))
    s.F1 = _add(db, Factory(workspace_id=s.W1.id, name="Factory One", abbreviation="F1"))
    s.F2 = _add(db, Factory(workspace_id=s.W1.id, name="Factory Two", abbreviation="F2"))
    s.FI = _add(db, Factory(workspace_id=s.W1.id, name="Idle Plant", abbreviation="IP", is_active=False))
    s.FD = _add(db, Factory(workspace_id=s.W1.id, name="Old Plant", abbreviation="OP", is_deleted=True))
    s.F9 = _add(db, Factory(workspace_id=s.W2.id, name="Factory Nine", abbreviation="F9"))
    return s


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #

def proj(db, S, name, where="W1", private=False, deleted=False, **over):
    """proj / W0 proj / W2 proj; `private`, `deleted` as Conventions; `over` = the columns after "but"."""
    ws = getattr(S, where)
    factory = {"W0": S.F0, "W1": S.F1, "W2": S.F9}[where]
    fields = {
        "workspace_id": ws.id, "factory_id": factory.id, "name": name,
        "description": "Main", "created_by": S.U1.id,
    }
    if private:
        fields["visibility"] = "invited_only"
    if deleted:
        fields.update(is_deleted=True, deleted_at=T0, deleted_by=S.U1.id)
    fields.update(over)
    return _add(db, Project(**fields))


def pmem(db, S, p, u, **over):
    fields = {"workspace_id": p.workspace_id, "project_id": p.id, "user_id": u.id, "assigned_by": S.U1.id}
    fields.update(over)
    return _add(db, ProjectMember(**fields))


def comp(db, p, name, **over):
    return _add(db, ProjectComponent(workspace_id=p.workspace_id, project_id=p.id, name=name, **over))


def ev(db, p, event_type, at, by):
    return _add(db, ProjectEvent(
        workspace_id=p.workspace_id, project_id=p.id, event_type=event_type, description="seed",
        performed_by=by, created_at=at, metadata_json=None,
    ))


def bulk(db, S, n, p):
    db.execute(insert(Project), [
        {
            "workspace_id": S.W1.id, "factory_id": S.F1.id, "name": f"{p}{i:05d}", "description": "Main",
            "created_by": S.U1.id, "visibility": "workspace", "is_active": True, "is_deleted": False,
            "priority": ProjectPriorityEnum.LOW, "status": PLANNING,
        }
        for i in range(n)
    ])
    db.expire_all()


def set_owner(db, ws, u):
    ws.owner_user_id = u.id
    db.flush()


# --------------------------------------------------------------------------- #
# Named checks
# --------------------------------------------------------------------------- #

def _columns(model):
    return [c.key for c in sa_inspect(model).mapper.column_attrs]


def snap(db, row):
    """Snapshot for unchanged(X), taken after the last Given line."""
    db.refresh(row)
    return {k: getattr(row, k) for k in _columns(type(row))}


def unchanged(db, row, before):
    db.expire_all()
    fresh = db.get(type(row), before["id"])
    return fresh is not None and {k: getattr(fresh, k) for k in _columns(type(row))} == before


def reread(db, model, row_id):
    db.expire_all()
    return db.get(model, row_id)


def counts(db):
    """"nothing written": row counts of the four tables (all workspaces)."""
    return tuple(
        db.execute(select(func.count()).select_from(m)).scalar_one()
        for m in (Project, ProjectMember, ProjectEvent, ProjectComponent)
    )


def events_of(db, p):
    db.expire_all()
    return db.execute(select(ProjectEvent).where(ProjectEvent.project_id == p.id).order_by(ProjectEvent.id)).scalars().all()


def members_of(db, p):
    db.expire_all()
    return db.execute(select(ProjectMember).where(ProjectMember.project_id == p.id).order_by(ProjectMember.id)).scalars().all()


# Given step "recorder"
def recorder(db):
    stmts = []

    def rec(conn, cursor, statement, params, context, executemany):
        stmts.append(statement)

    conn = db.connection()
    event.listen(conn, "before_cursor_execute", rec)
    return stmts, lambda: event.remove(conn, "before_cursor_execute", rec)


# =========================================================================== #
# _visibility_value
# =========================================================================== #

def test_prjm_vv_01__no_visibility_reads_workspace():
    """PRJM-VV-01 — no visibility reads as "workspace".
    Rules: _visibility_value R1."""
    P = Project(name="Draft", visibility=None)
    result = PM._visibility_value(P)
    # Then 1
    assert result == "workspace"


def test_prjm_vv_02__enum_member_gives_value():
    """PRJM-VV-02 — an enum member gives its value.
    Rules: _visibility_value R1."""
    P = Project(name="Draft", visibility=ProjectVisibilityEnum.INVITED_ONLY)
    result = PM._visibility_value(P)
    # Then 1
    assert result == "invited_only"
    # Then 2
    assert type(result) is str


def test_prjm_vv_03__enum_workspace_gives_workspace():
    """PRJM-VV-03 — the enum member WORKSPACE gives "workspace".
    Rules: _visibility_value R1."""
    P = Project(name="Draft", visibility=ProjectVisibilityEnum.WORKSPACE)
    result = PM._visibility_value(P)
    # Then 1
    assert result == "workspace"


def test_prjm_vv_04__stored_text_returned_as_stored():
    """PRJM-VV-04 — stored text is returned as stored.
    Rules: _visibility_value R1."""
    P = Project(name="Draft", visibility="invited_only")
    result = PM._visibility_value(P)
    # Then 1
    assert result == "invited_only"


def test_prjm_vv_05__other_text_returned_unchanged():
    """PRJM-VV-05 — any other text is returned unchanged, case and spaces kept.
    Rules: _visibility_value R1."""
    P = Project(name="Draft", visibility=" Secret Team")
    result = PM._visibility_value(P)
    # Then 1
    assert result == " Secret Team"


# =========================================================================== #
# _is_workspace_owner
# =========================================================================== #

def test_prjm_wo_01__owner_without_membership(db, S):
    """PRJM-WO-01 — the workspace's owner is the owner, with no membership row.
    Rules: _is_workspace_owner R1."""
    UX = make_profile(db, name="Omar Ali")
    set_owner(db, S.W1, UX)
    result = PM._is_workspace_owner(db, user_id=UX.id, workspace_id=S.W1.id)
    # Then 1
    assert result is True


def test_prjm_wo_02__lower_id_other_user_not_owner(db, S):
    """PRJM-WO-02 — another user with a lower id is not the owner.
    Rules: _is_workspace_owner R1."""
    set_owner(db, S.W1, S.U1)
    result = PM._is_workspace_owner(db, user_id=S.UG.id, workspace_id=S.W1.id)
    # Then 1
    assert result is False


def test_prjm_wo_03__higher_id_other_user_not_owner(db, S):
    """PRJM-WO-03 — another user with a higher id is not the owner.
    Rules: _is_workspace_owner R1."""
    UX = make_profile(db, name="Omar Ali")
    set_owner(db, S.W1, UX)
    result = PM._is_workspace_owner(db, user_id=S.UG.id, workspace_id=S.W1.id)
    # Then 1
    assert result is False


def test_prjm_wo_04__ownerless_workspace(db, S):
    """PRJM-WO-04 — a workspace with no owner has no owner.
    Rules: _is_workspace_owner R1."""
    result = PM._is_workspace_owner(db, user_id=S.U2.id, workspace_id=S.W1.id)
    # Then 1
    assert result is False


def test_prjm_wo_05__unknown_workspace_false(db, S):
    """PRJM-WO-05 — an unknown workspace answers False, no error.
    Rules: _is_workspace_owner R1."""
    set_owner(db, S.W1, S.UG)
    result = PM._is_workspace_owner(db, user_id=S.UG.id, workspace_id=MISSING)
    # Then 1
    assert result is False


def test_prjm_wo_06__owning_w0_not_w1(db, S):
    """PRJM-WO-06 — owning W0 (lower id) does not make the caller owner of W1.
    Rules: _is_workspace_owner R1."""
    set_owner(db, S.W0, S.UG)
    result = PM._is_workspace_owner(db, user_id=S.UG.id, workspace_id=S.W1.id)
    # Then 1
    assert result is False


def test_prjm_wo_07__owning_w2_not_w1(db, S):
    """PRJM-WO-07 — owning W2 (higher id) does not make the caller owner of W1.
    Rules: _is_workspace_owner R1."""
    set_owner(db, S.W2, S.UG)
    result = PM._is_workspace_owner(db, user_id=S.UG.id, workspace_id=S.W1.id)
    # Then 1
    assert result is False


# =========================================================================== #
# _is_privileged
# =========================================================================== #

def test_prjm_pv_01__workspace_owner_privileged(db, S):
    """PRJM-PV-01 — the workspace owner is privileged whatever their membership.
    Rules: _is_privileged R1."""
    UX = make_profile(db, name="Omar Ali")
    member(db, S, UX, "ground-team", status="suspended")
    set_owner(db, S.W1, UX)
    result = PM._is_privileged(db, user_id=UX.id, workspace_id=S.W1.id)
    # Then 1
    assert result is True


def test_prjm_pv_02__active_owner_role(db, S):
    """PRJM-PV-02 — an active member with role owner is privileged.
    Rules: _is_privileged R2."""
    result = PM._is_privileged(db, user_id=S.U2.id, workspace_id=S.W1.id)
    # Then 1
    assert result is True


def test_prjm_pv_03__active_ground_team_manager(db, S):
    """PRJM-PV-03 — an active member with role ground-team-manager is privileged.
    Rules: _is_privileged R2."""
    UX = make_profile(db, name="Omar Ali")
    member(db, S, UX, "ground-team-manager")
    result = PM._is_privileged(db, user_id=UX.id, workspace_id=S.W1.id)
    # Then 1
    assert result is True


def test_prjm_pv_04__plain_ground_team_not(db, S):
    """PRJM-PV-04 — a plain ground-team member is not privileged.
    Rules: _is_privileged R2."""
    result = PM._is_privileged(db, user_id=S.UG.id, workspace_id=S.W1.id)
    # Then 1
    assert result is False


@pytest.mark.parametrize(("role", "status"), [
    pytest.param("owner", "suspended", id="PRJM-PV-05"),
    pytest.param("owner", "invited", id="PRJM-PV-06"),
    pytest.param("owner", "inactive", id="PRJM-PV-07"),
    pytest.param("owner", "Active", id="PRJM-PV-08"),
    pytest.param("ground-team-manager", "suspended", id="PRJM-PV-09"),
    pytest.param("Owner", "active", id="PRJM-PV-10"),
    pytest.param(" owner", "active", id="PRJM-PV-11"),
    pytest.param("manager", "active", id="PRJM-PV-12"),
    pytest.param("ground_team_manager", "active", id="PRJM-PV-13"),
    pytest.param("finance", "active", id="PRJM-PV-14"),
])
def test_prjm_pv_05_14__role_and_status_compared_exactly(db, S, role, status):
    """PRJM-PV-05 … PV-14 — a role or status not exactly active + privileged role is not privileged.
    Rules: _is_privileged R2."""
    UX = make_profile(db, name="Omar Ali")
    member(db, S, UX, role, status=status)
    result = PM._is_privileged(db, user_id=UX.id, workspace_id=S.W1.id)
    # Then 1
    assert result is False


def test_prjm_pv_15__no_membership_not_owner(db, S):
    """PRJM-PV-15 — no membership and not the owner: not privileged.
    Rules: _is_privileged R1, R2."""
    UX = make_profile(db, name="Omar Ali")
    result = PM._is_privileged(db, user_id=UX.id, workspace_id=S.W1.id)
    # Then 1
    assert result is False


def test_prjm_pv_16__owner_role_in_w0_not_w1(db, S):
    """PRJM-PV-16 — role owner in W0 (lower workspace id) does not count in W1.
    Rules: _is_privileged R2."""
    UX = make_profile(db, name="Omar Ali")
    member(db, S, UX, "owner", ws=S.W0)
    member(db, S, UX, "ground-team")
    result = PM._is_privileged(db, user_id=UX.id, workspace_id=S.W1.id)
    # Then 1
    assert result is False


def test_prjm_pv_17__gtm_role_in_w2_not_w1(db, S):
    """PRJM-PV-17 — role ground-team-manager in W2 (higher workspace id) does not count in W1.
    Rules: _is_privileged R2."""
    UX = make_profile(db, name="Omar Ali")
    member(db, S, UX, "ground-team-manager", ws=S.W2)
    member(db, S, UX, "ground-team")
    result = PM._is_privileged(db, user_id=UX.id, workspace_id=S.W1.id)
    # Then 1
    assert result is False


def test_prjm_pv_18__privileged_set_exact():
    """PRJM-PV-18 — the privileged set is exactly owner and ground-team-manager.
    Rules: _is_privileged R2 (Facts)."""
    result = PRIVILEGED_ROLES
    # Then 1
    assert set(result) == {"owner", "ground-team-manager"}


# =========================================================================== #
# can_access_project
# =========================================================================== #

def test_prjm_ca_01__workspace_project_open_no_read(db, S):
    """PRJM-CA-01 — a workspace-visible project is open to a plain member, with no read.
    Rules: can_access_project R1."""
    P = proj(db, S, "Open")
    stmts, stop = recorder(db)
    result = PM.can_access_project(db, project=P, user_id=S.UG.id, workspace_id=S.W1.id)
    stop()
    # Then 1
    assert result is True
    # Then 2
    assert len(stmts) == 0


def test_prjm_ca_02__no_visibility_open(db, S):
    """PRJM-CA-02 — a project with no visibility is open to a plain member.
    Rules: can_access_project R1; _visibility_value R1."""
    P = Project(workspace_id=S.W1.id, factory_id=S.F1.id, name="Draft", description="Main",
                created_by=S.U1.id, visibility=None)
    result = PM.can_access_project(db, project=P, user_id=S.UG.id, workspace_id=S.W1.id)
    # Then 1
    assert result is True


def test_prjm_ca_03__private_closed_to_plain_member(db, S):
    """PRJM-CA-03 — a private project is closed to a plain member.
    Rules: can_access_project R2."""
    P = proj(db, S, "Secret", private=True)
    result = PM.can_access_project(db, project=P, user_id=S.UG.id, workspace_id=S.W1.id)
    # Then 1
    assert result is False


def test_prjm_ca_04__workspace_owner_opens_private(db, S):
    """PRJM-CA-04 — the workspace owner with no membership opens a private project.
    Rules: can_access_project R2; _is_privileged R1."""
    UX = make_profile(db, name="Omar Ali")
    set_owner(db, S.W1, UX)
    P = proj(db, S, "Secret", private=True)
    result = PM.can_access_project(db, project=P, user_id=UX.id, workspace_id=S.W1.id)
    # Then 1
    assert result is True


def test_prjm_ca_05__owner_role_opens_private(db, S):
    """PRJM-CA-05 — an active member with role owner opens a private project.
    Rules: can_access_project R2."""
    P = proj(db, S, "Secret", private=True)
    result = PM.can_access_project(db, project=P, user_id=S.U2.id, workspace_id=S.W1.id)
    # Then 1
    assert result is True


def test_prjm_ca_06__gtm_opens_private(db, S):
    """PRJM-CA-06 — an active ground-team-manager opens a private project.
    Rules: can_access_project R2."""
    UX = make_profile(db, name="Omar Ali")
    member(db, S, UX, "ground-team-manager")
    P = proj(db, S, "Secret", private=True)
    result = PM.can_access_project(db, project=P, user_id=UX.id, workspace_id=S.W1.id)
    # Then 1
    assert result is True


def test_prjm_ca_07__creator_opens_private(db, S):
    """PRJM-CA-07 — the creator opens their private project.
    Rules: can_access_project R2."""
    P = proj(db, S, "Secret", private=True, created_by=S.UG.id)
    result = PM.can_access_project(db, project=P, user_id=S.UG.id, workspace_id=S.W1.id)
    # Then 1
    assert result is True


def test_prjm_ca_08__project_member_opens_private(db, S):
    """PRJM-CA-08 — a project member opens a private project.
    Rules: can_access_project R2."""
    P = proj(db, S, "Secret", private=True)
    pmem(db, S, P, S.UG)
    result = PM.can_access_project(db, project=P, user_id=S.UG.id, workspace_id=S.W1.id)
    # Then 1
    assert result is True


def test_prjm_ca_09__member_without_workspace_membership(db, S):
    """PRJM-CA-09 — a project member with no workspace membership still opens it (raw).
    Rules: can_access_project R2."""
    UX = make_profile(db, name="Omar Ali")
    P = proj(db, S, "Secret", private=True)
    pmem(db, S, P, UX)
    result = PM.can_access_project(db, project=P, user_id=UX.id, workspace_id=S.W1.id)
    # Then 1
    assert result is True


def test_prjm_ca_10__member_with_inactive_membership(db, S):
    """PRJM-CA-10 — a project member whose membership is inactive still opens it (raw).
    Rules: can_access_project R2."""
    UX = make_profile(db, name="Omar Ali")
    member(db, S, UX, "ground-team", status="inactive")
    P = proj(db, S, "Secret", private=True)
    pmem(db, S, P, UX)
    result = PM.can_access_project(db, project=P, user_id=UX.id, workspace_id=S.W1.id)
    # Then 1
    assert result is True


def test_prjm_ca_11__suspended_owner_refused(db, S):
    """PRJM-CA-11 — a suspended member with role owner is refused a private project.
    Rules: can_access_project R2; _is_privileged R2."""
    UX = make_profile(db, name="Omar Ali")
    member(db, S, UX, "owner", status="suspended")
    P = proj(db, S, "Secret", private=True)
    result = PM.can_access_project(db, project=P, user_id=UX.id, workspace_id=S.W1.id)
    # Then 1
    assert result is False


def test_prjm_ca_12__inactive_gtm_refused(db, S):
    """PRJM-CA-12 — an inactive ground-team-manager is refused a private project.
    Rules: can_access_project R2; _is_privileged R2."""
    UX = make_profile(db, name="Omar Ali")
    member(db, S, UX, "ground-team-manager", status="inactive")
    P = proj(db, S, "Secret", private=True)
    result = PM.can_access_project(db, project=P, user_id=UX.id, workspace_id=S.W1.id)
    # Then 1
    assert result is False


def test_prjm_ca_13__owning_w0_does_not_open(db, S):
    """PRJM-CA-13 — owning W0 does not open a private project of W1.
    Rules: can_access_project R2."""
    set_owner(db, S.W0, S.UG)
    P = proj(db, S, "Secret", private=True)
    result = PM.can_access_project(db, project=P, user_id=S.UG.id, workspace_id=S.W1.id)
    # Then 1
    assert result is False


def test_prjm_ca_14__owning_w2_does_not_open(db, S):
    """PRJM-CA-14 — owning W2 does not open a private project of W1.
    Rules: can_access_project R2."""
    set_owner(db, S.W2, S.UG)
    P = proj(db, S, "Secret", private=True)
    result = PM.can_access_project(db, project=P, user_id=S.UG.id, workspace_id=S.W1.id)
    # Then 1
    assert result is False


def test_prjm_ca_15__privileged_elsewhere_does_not_open(db, S):
    """PRJM-CA-15 — privileged only in W0 and W2 (rows built before the W1 row) does not open it.
    Rules: can_access_project R2."""
    UX = make_profile(db, name="Omar Ali")
    member(db, S, UX, "owner", ws=S.W2)
    member(db, S, UX, "ground-team-manager", ws=S.W0)
    member(db, S, UX, "ground-team")
    P = proj(db, S, "Secret", private=True)
    result = PM.can_access_project(db, project=P, user_id=UX.id, workspace_id=S.W1.id)
    # Then 1
    assert result is False


def test_prjm_ca_16__membership_of_other_projects(db, S):
    """PRJM-CA-16 — membership of other private projects (lower and higher id) does not open this one.
    Rules: can_access_project R2."""
    PA = proj(db, S, "Alpha Secret", private=True)
    P = proj(db, S, "Secret", private=True)
    PZ = proj(db, S, "Zeta Secret", private=True)
    pmem(db, S, PA, S.UG)
    pmem(db, S, PZ, S.UG)
    result = PM.can_access_project(db, project=P, user_id=S.UG.id, workspace_id=S.W1.id)
    # Then 1
    assert result is False


def test_prjm_ca_17__other_users_membership(db, S):
    """PRJM-CA-17 — other users' membership of this project (lower and higher user id) does not open it.
    Rules: can_access_project R2."""
    UX = make_profile(db, name="Omar Ali")
    P = proj(db, S, "Secret", private=True)
    pmem(db, S, P, S.U2)
    pmem(db, S, P, UX)
    result = PM.can_access_project(db, project=P, user_id=S.UG.id, workspace_id=S.W1.id)
    # Then 1
    assert result is False


def test_prjm_ca_18__member_row_under_w2(db, S):
    """PRJM-CA-18 — a membership row of this project filed under W2 does not open it in W1.
    Rules: can_access_project R2."""
    P = proj(db, S, "Secret", private=True)
    _add(db, ProjectMember(workspace_id=S.W2.id, project_id=P.id, user_id=S.UG.id, assigned_by=S.U1.id))
    result = PM.can_access_project(db, project=P, user_id=S.UG.id, workspace_id=S.W1.id)
    # Then 1
    assert result is False


def test_prjm_ca_19__created_other_projects(db, S):
    """PRJM-CA-19 — having created other projects (lower and higher id) does not open this one.
    Rules: can_access_project R2."""
    proj(db, S, "Alpha Secret", private=True, created_by=S.UG.id)
    P = proj(db, S, "Secret", private=True)
    proj(db, S, "Zeta Secret", private=True, created_by=S.UG.id)
    result = PM.can_access_project(db, project=P, user_id=S.UG.id, workspace_id=S.W1.id)
    # Then 1
    assert result is False


def test_prjm_ca_20__higher_id_creator(db, S):
    """PRJM-CA-20 — a creator with a higher id than the caller does not open it for the caller.
    Rules: can_access_project R2."""
    UX = make_profile(db, name="Omar Ali")
    P = proj(db, S, "Secret", private=True, created_by=UX.id)
    result = PM.can_access_project(db, project=P, user_id=S.UG.id, workspace_id=S.W1.id)
    # Then 1
    assert result is False


def test_prjm_ca_21__lower_id_w1_owner(db, S):
    """PRJM-CA-21 — a W1 owner with a lower id than the caller does not open it for the caller.
    Rules: can_access_project R2; _is_workspace_owner R1."""
    set_owner(db, S.W1, S.U1)
    P = proj(db, S, "Secret", private=True)
    result = PM.can_access_project(db, project=P, user_id=S.UG.id, workspace_id=S.W1.id)
    # Then 1
    assert result is False


def test_prjm_ca_22__higher_id_w1_owner(db, S):
    """PRJM-CA-22 — a W1 owner with a higher id than the caller does not open it for the caller.
    Rules: can_access_project R2; _is_workspace_owner R1."""
    UX = make_profile(db, name="Omar Ali")
    set_owner(db, S.W1, UX)
    P = proj(db, S, "Secret", private=True)
    result = PM.can_access_project(db, project=P, user_id=S.UG.id, workspace_id=S.W1.id)
    # Then 1
    assert result is False


def test_prjm_ca_23__no_creator_closed_to_plain(db, S):
    """PRJM-CA-23 — a private project with no creator is closed to a plain member.
    Rules: can_access_project R3."""
    P = proj(db, S, "Secret", private=True, created_by=None)
    result = PM.can_access_project(db, project=P, user_id=S.UG.id, workspace_id=S.W1.id)
    # Then 1
    assert result is False


def test_prjm_ca_24__no_creator_open_to_privileged(db, S):
    """PRJM-CA-24 — a private project with no creator is open to a privileged member.
    Rules: can_access_project R3."""
    P = proj(db, S, "Secret", private=True, created_by=None)
    result = PM.can_access_project(db, project=P, user_id=S.U2.id, workspace_id=S.W1.id)
    # Then 1
    assert result is True


def test_prjm_ca_25__no_creator_open_to_member(db, S):
    """PRJM-CA-25 — a private project with no creator is open to its project member.
    Rules: can_access_project R3."""
    P = proj(db, S, "Secret", private=True, created_by=None)
    pmem(db, S, P, S.UG)
    result = PM.can_access_project(db, project=P, user_id=S.UG.id, workspace_id=S.W1.id)
    # Then 1
    assert result is True


@pytest.mark.parametrize("vis", [
    pytest.param("Workspace", id="PRJM-CA-26"),
    pytest.param(" workspace", id="PRJM-CA-27"),
    pytest.param("work", id="PRJM-CA-28"),
])
def test_prjm_ca_26_28__near_workspace_text_is_private(db, S, vis):
    """PRJM-CA-26 … CA-28 — visibility text that is not exactly "workspace" is private.
    Rules: can_access_project R1, R2."""
    P = proj(db, S, "Secret", visibility=vis)
    result = PM.can_access_project(db, project=P, user_id=S.UG.id, workspace_id=S.W1.id)
    # Then 1
    assert result is False


def test_prjm_ca_29__other_text_private_open_to_creator(db, S):
    """PRJM-CA-29 — any other visibility text is private and opens for the creator only among plain members.
    Rules: can_access_project R2."""
    P = proj(db, S, "Secret", visibility="private", created_by=S.UG.id)
    result = PM.can_access_project(db, project=P, user_id=S.UG.id, workspace_id=S.W1.id)
    # Then 1
    assert result is True


def test_prjm_ca_30__project_workspace_not_looked_at(db, S):
    """PRJM-CA-30 — the project's own workspace is not looked at.
    Rules: can_access_project R3."""
    P = proj(db, S, "Far Secret", where="W2", private=True)
    result = PM.can_access_project(db, project=P, user_id=S.U2.id, workspace_id=S.W1.id)
    # Then 1
    assert result is True


def test_prjm_ca_31__deleted_private_open_to_creator(db, S):
    """PRJM-CA-31 — a soft-deleted private project is still open to its creator.
    Rules: can_access_project R3."""
    P = proj(db, S, "Gone Secret", private=True, deleted=True, created_by=S.UG.id)
    result = PM.can_access_project(db, project=P, user_id=S.UG.id, workspace_id=S.W1.id)
    # Then 1
    assert result is True


def test_prjm_ca_32__unflushed_edit_kept(db, S):
    """PRJM-CA-32 — the check leaves the caller's unflushed edit in place.
    Rules: can_access_project R2 (reads only)."""
    P = proj(db, S, "Secret", private=True)
    B = proj(db, S, "Board")
    B.description = "Edited"
    result = PM.can_access_project(db, project=P, user_id=S.UG.id, workspace_id=S.W1.id)
    # Then 1
    assert result is False
    # Then 2
    assert B in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert not db.new and not db.deleted


def test_prjm_ca_33__w2_private_member_row_under_w2_closed_with_w1(db, S):
    """PRJM-CA-33 — a W2 private project with its member row under W2 is closed when asked with W1.
    Rules: can_access_project R2, R3."""
    P9 = proj(db, S, "Far Secret", where="W2", private=True)
    pmem(db, S, P9, S.UG)
    result = PM.can_access_project(db, project=P9, user_id=S.UG.id, workspace_id=S.W1.id)
    # Then 1
    assert result is False


# =========================================================================== #
# _get_project_or_404
# =========================================================================== #

def test_prjm_gn_01__returns_project_of_workspace(db, S):
    """PRJM-GN-01 — returns the project of the workspace.
    Rules: _get_project_or_404 R1."""
    proj(db, S, "Zero", where="W0")
    P = proj(db, S, "Roof job")
    proj(db, S, "Nine", where="W2")
    result = PM._get_project_or_404(db, project_id=P.id, workspace_id=S.W1.id)
    # Then 1
    assert result.id == P.id
    # Then 2
    assert isinstance(result, Project)


def test_prjm_gn_02__deleted_returned_raw(db, S):
    """PRJM-GN-02 — a soft-deleted project is returned (raw).
    Rules: _get_project_or_404 R1."""
    P = proj(db, S, "Gone", deleted=True)
    result = PM._get_project_or_404(db, project_id=P.id, workspace_id=S.W1.id)
    # Then 1
    assert result.id == P.id
    # Then 2
    assert result.is_deleted is True


def test_prjm_gn_03__unknown_id_404(db, S):
    """PRJM-GN-03 — an unknown id is 404.
    Rules: _get_project_or_404 R1."""
    proj(db, S, "Roof job")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM._get_project_or_404(db, project_id=MISSING, workspace_id=S.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Project with ID 999999999 not found"


def test_prjm_gn_04__id_zero_404(db, S):
    """PRJM-GN-04 — id 0 is 404.
    Rules: _get_project_or_404 R1."""
    proj(db, S, "Roof job")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM._get_project_or_404(db, project_id=0, workspace_id=S.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Project with ID 0 not found"


def test_prjm_gn_05__w0_project_404(db, S):
    """PRJM-GN-05 — a W0 project (lower id) is 404 in W1.
    Rules: _get_project_or_404 R1."""
    P0 = proj(db, S, "Zero", where="W0")
    proj(db, S, "Roof job")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM._get_project_or_404(db, project_id=P0.id, workspace_id=S.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project with ID {P0.id} not found"


def test_prjm_gn_06__w2_project_404(db, S):
    """PRJM-GN-06 — a W2 project (higher id) is 404 in W1.
    Rules: _get_project_or_404 R1."""
    proj(db, S, "Roof job")
    P9 = proj(db, S, "Nine", where="W2")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM._get_project_or_404(db, project_id=P9.id, workspace_id=S.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project with ID {P9.id} not found"


# =========================================================================== #
# require_project_access
# =========================================================================== #

def test_prjm_ra_01__workspace_project_returned(db, S):
    """PRJM-RA-01 — a workspace-visible project is returned to a plain member.
    Rules: require_project_access R4."""
    P = proj(db, S, "Roof job")
    result = PM.require_project_access(db, project_id=P.id, workspace_id=S.W1.id, user_id=S.UG.id)
    # Then 1
    assert result.id == P.id
    # Then 2
    assert result.name == "Roof job"


def test_prjm_ra_02__private_returned_to_member(db, S):
    """PRJM-RA-02 — a private project is returned to its project member.
    Rules: require_project_access R4."""
    P = proj(db, S, "Secret", private=True)
    pmem(db, S, P, S.UG)
    result = PM.require_project_access(db, project_id=P.id, workspace_id=S.W1.id, user_id=S.UG.id)
    # Then 1
    assert result.id == P.id


def test_prjm_ra_03__private_refused_403(db, S):
    """PRJM-RA-03 — a private project the caller may not open is 403.
    Rules: require_project_access R2, Errors R2."""
    P = proj(db, S, "Secret", private=True)
    before = snap(db, P)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.require_project_access(db, project_id=P.id, workspace_id=S.W1.id, user_id=S.UG.id)
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == "You do not have access to this project"
    # Then 4
    assert unchanged(db, P, before)


def test_prjm_ra_04__unknown_id_404(db, S):
    """PRJM-RA-04 — an unknown id is 404.
    Rules: require_project_access R1, Errors R1."""
    proj(db, S, "Roof job")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.require_project_access(db, project_id=MISSING, workspace_id=S.W1.id, user_id=S.UG.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Project with ID 999999999 not found"


def test_prjm_ra_05__other_workspace_private_404(db, S):
    """PRJM-RA-05 — another workspace's private project is 404, not 403.
    Rules: require_project_access R1."""
    P9 = proj(db, S, "Far Secret", where="W2", private=True)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.require_project_access(db, project_id=P9.id, workspace_id=S.W1.id, user_id=S.UG.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project with ID {P9.id} not found"


def test_prjm_ra_06__w0_project_404_for_privileged(db, S):
    """PRJM-RA-06 — a W0 project (lower id) is 404 in W1, even for a privileged caller.
    Rules: require_project_access R1."""
    P0 = proj(db, S, "Zero", where="W0")
    proj(db, S, "Roof job")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.require_project_access(db, project_id=P0.id, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project with ID {P0.id} not found"


def test_prjm_ra_07__unflushed_edit_kept(db, S):
    """PRJM-RA-07 — the check leaves the caller's unflushed edit in place.
    Rules: require_project_access R4 (reads only)."""
    P = proj(db, S, "Secret", private=True)
    B = proj(db, S, "Board")
    B.description = "Edited"
    result = PM.require_project_access(db, project_id=P.id, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 1
    assert result.id == P.id
    # Then 2
    assert B in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert not db.new and not db.deleted


# =========================================================================== #
# require_component_access
# =========================================================================== #

def test_prjm_rc_01__returns_project_id(db, S):
    """PRJM-RC-01 — returns the component's project id, not the component id.
    Rules: require_component_access R1, R2, Returns."""
    P = proj(db, S, "Roof job", id=XID(1))
    C = comp(db, P, "Roof", id=XID(5))
    result = PM.require_component_access(db, component_id=C.id, workspace_id=S.W1.id, user_id=S.UG.id)
    # Then 1
    assert result == XID(1)


def test_prjm_rc_02__private_open_to_member(db, S):
    """PRJM-RC-02 — a component of a private project is open to the project's member.
    Rules: require_component_access R2."""
    P = proj(db, S, "Secret", private=True, id=XID(2))
    C = comp(db, P, "Vault", id=XID(7))
    pmem(db, S, P, S.UG)
    result = PM.require_component_access(db, component_id=C.id, workspace_id=S.W1.id, user_id=S.UG.id)
    # Then 1
    assert result == XID(2)


def test_prjm_rc_03__private_refused_403(db, S):
    """PRJM-RC-03 — a component of a private project the caller may not open is 403.
    Rules: require_component_access R3."""
    P = proj(db, S, "Secret", private=True)
    C = comp(db, P, "Vault")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.require_component_access(db, component_id=C.id, workspace_id=S.W1.id, user_id=S.UG.id)
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == "You do not have access to this project"


def test_prjm_rc_04__unknown_component_404(db, S):
    """PRJM-RC-04 — an unknown component id is 404.
    Rules: require_component_access R1."""
    P = proj(db, S, "Roof job")
    comp(db, P, "Roof")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.require_component_access(db, component_id=MISSING, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Project component not found"


def test_prjm_rc_05__component_zero_404(db, S):
    """PRJM-RC-05 — component id 0 is 404.
    Rules: require_component_access R1."""
    P = proj(db, S, "Roof job")
    comp(db, P, "Roof")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.require_component_access(db, component_id=0, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Project component not found"


def test_prjm_rc_06__w0_component_404(db, S):
    """PRJM-RC-06 — a W0 component (lower id) is 404 in W1.
    Rules: require_component_access R1."""
    P0 = proj(db, S, "Zero", where="W0")
    C0 = comp(db, P0, "Cellar")
    P = proj(db, S, "Roof job")
    comp(db, P, "Roof")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.require_component_access(db, component_id=C0.id, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Project component not found"


def test_prjm_rc_07__w2_component_404(db, S):
    """PRJM-RC-07 — a W2 component (higher id) is 404 in W1.
    Rules: require_component_access R1."""
    P = proj(db, S, "Roof job")
    comp(db, P, "Roof")
    P9 = proj(db, S, "Nine", where="W2")
    C9 = comp(db, P9, "Floor")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.require_component_access(db, component_id=C9.id, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Project component not found"


def test_prjm_rc_08__w1_component_on_w2_project(db, S):
    """PRJM-RC-08 — a W1 component on a W2 project answers 404 for that project.
    Rules: require_component_access R4."""
    P9 = proj(db, S, "Nine", where="W2")
    CX = _add(db, ProjectComponent(workspace_id=S.W1.id, project_id=P9.id, name="Stray"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.require_component_access(db, component_id=CX.id, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project with ID {P9.id} not found"


@pytest.mark.xfail(strict=True, reason="BUG-1278: a soft-deleted project's members and components answer 404")
def test_prjm_rc_09__deleted_project_component_404(db, S):
    """PRJM-RC-09 — a component of a soft-deleted project is 404 for the project.
    Rules: require_component_access R2 [BUG-1278]; require_project_access R3."""
    P = proj(db, S, "Gone", deleted=True)
    C = comp(db, P, "Roof")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.require_component_access(db, component_id=C.id, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project with ID {P.id} not found"


# =========================================================================== #
# _format_field_value
# =========================================================================== #

def test_prjm_ff_01__none_stays_none():
    """PRJM-FF-01 — None stays None.
    Rules: _format_field_value R1."""
    result = PM._format_field_value(None)
    # Then 1
    assert result is None


@pytest.mark.parametrize(("value", "expected"), [
    pytest.param(ProjectStatusEnum.COMPLETED, "COMPLETED", id="PRJM-FF-02"),
    pytest.param(datetime(2026, 3, 1, 15, 30, 45), "2026-03-01", id="PRJM-FF-03"),  # noqa: DTZ001
    pytest.param(Decimal("1000.00"), "1000.00", id="PRJM-FF-04"),
    pytest.param(Decimal("1000.5"), "1000.5", id="PRJM-FF-05"),
    pytest.param(" Line 3", " Line 3", id="PRJM-FF-06"),
    pytest.param(7, "7", id="PRJM-FF-07"),
])
def test_prjm_ff_02_07__formats_value(value, expected):
    """PRJM-FF-02 … FF-07 — enum value, date of a datetime, or str(value).
    Rules: _format_field_value R1, R2."""
    result = PM._format_field_value(value)
    # Then 1
    assert result == expected


# =========================================================================== #
# _collect_field_changes
# =========================================================================== #

def test_prjm_cf_01__one_entry_per_changed_field():
    """PRJM-CF-01 — one entry per changed field, in the order of fields.
    Rules: _collect_field_changes R1, R2."""
    R = Project(name="Old", description="Main", budget=Decimal("10.00"))
    result = PM._collect_field_changes(R, {"budget": Decimal("20.00"), "name": "New"}, PROJECT_LOG_FIELDS)
    # Then 1
    assert result == [
        {"field": "name", "label": "Name", "from_value": "Old", "to_value": "New"},
        {"field": "budget", "label": "Budget", "from_value": "10.00", "to_value": "20.00"},
    ]


def test_prjm_cf_02__order_from_fields():
    """PRJM-CF-02 — the order comes from fields, not from the update dict.
    Rules: _collect_field_changes R1."""
    R = Project(name="Old", description="Main")
    result = PM._collect_field_changes(R, {"name": "New", "description": "Side"}, {"description": "Description", "name": "Name"})
    # Then 1
    assert [e["field"] for e in result] == ["description", "name"]


def test_prjm_cf_03__key_not_in_fields_ignored(S):
    """PRJM-CF-03 — a key not in fields is ignored.
    Rules: _collect_field_changes R1."""
    R = Project(name="Old", description="Main", created_by=S.U1.id)
    result = PM._collect_field_changes(R, {"created_by": S.U2.id, "description": "Side"}, PROJECT_LOG_FIELDS)
    # Then 1
    assert result == [{"field": "description", "label": "Description", "from_value": "Main", "to_value": "Side"}]


def test_prjm_cf_04__equal_value_no_entry():
    """PRJM-CF-04 — an equal value gives no entry.
    Rules: _collect_field_changes R1."""
    R = Project(name="Old", description="Main")
    result = PM._collect_field_changes(R, {"name": "Old", "description": "Main"}, PROJECT_LOG_FIELDS)
    # Then 1
    assert result == []


def test_prjm_cf_05__empty_dict_empty_list():
    """PRJM-CF-05 — an empty update dict gives an empty list.
    Rules: _collect_field_changes R1, Returns."""
    R = Project(name="Old", description="Main")
    result = PM._collect_field_changes(R, {}, PROJECT_LOG_FIELDS)
    # Then 1
    assert result == []
    # Then 2
    assert isinstance(result, list)


def test_prjm_cf_06__decimal_1000_equals_1000_00():
    """PRJM-CF-06 — Decimal 1000 equals 1000.00: no entry.
    Rules: _collect_field_changes R2."""
    R = Project(name="Old", budget=Decimal("1000.00"))
    result = PM._collect_field_changes(R, {"budget": Decimal("1000")}, PROJECT_LOG_FIELDS)
    # Then 1
    assert result == []


def test_prjm_cf_07__deadline_moved_by_hours():
    """PRJM-CF-07 — a deadline moved by hours in one day is an entry showing the same date twice.
    Rules: _collect_field_changes R2."""
    R = Project(name="Old", deadline=datetime(2026, 3, 1, 9, 0, 0))  # noqa: DTZ001
    result = PM._collect_field_changes(R, {"deadline": datetime(2026, 3, 1, 17, 0, 0)}, PROJECT_LOG_FIELDS)  # noqa: DTZ001
    # Then 1
    assert result == [{"field": "deadline", "label": "Deadline", "from_value": "2026-03-01", "to_value": "2026-03-01"}]


def test_prjm_cf_08__from_nothing_from_value_none():
    """PRJM-CF-08 — a value set from nothing has from_value None.
    Rules: _collect_field_changes R2; _format_field_value R1."""
    R = Project(name="Old", budget=None)
    result = PM._collect_field_changes(R, {"budget": Decimal("10.00")}, PROJECT_LOG_FIELDS)
    # Then 1
    assert result == [{"field": "budget", "label": "Budget", "from_value": None, "to_value": "10.00"}]


def test_prjm_cf_09__status_factory_visibility_labels(S):
    """PRJM-CF-09 — status, factory and visibility use their labels and value texts.
    Rules: _collect_field_changes R1, R2 (Facts: labels)."""
    R = Project(name="Old", status=PLANNING, factory_id=S.F1.id, visibility="workspace")
    result = PM._collect_field_changes(
        R, {"visibility": "invited_only", "factory_id": S.F2.id, "status": COMPLETED}, PROJECT_LOG_FIELDS,
    )
    # Then 1
    assert result == [
        {"field": "status", "label": "Status", "from_value": "PLANNING", "to_value": "COMPLETED"},
        {"field": "factory_id", "label": "Factory", "from_value": str(S.F1.id), "to_value": str(S.F2.id)},
        {"field": "visibility", "label": "Visibility", "from_value": "workspace", "to_value": "invited_only"},
    ]


def test_prjm_cf_10__log_fields_in_order():
    """PRJM-CF-10 — the log fields and their labels, in order.
    Rules: _collect_field_changes R1 (Facts: PROJECT_LOG_FIELDS)."""
    result = list(PROJECT_LOG_FIELDS.items())
    # Then 1
    assert result == [
        ("name", "Name"), ("description", "Description"), ("budget", "Budget"), ("deadline", "Deadline"),
        ("start_date", "Start date"), ("end_date", "End date"), ("priority", "Priority"), ("status", "Status"),
        ("factory_id", "Factory"), ("visibility", "Visibility"),
    ]


# =========================================================================== #
# log_for_component
# =========================================================================== #

def test_prjm_lc_01__writes_event_with_component(db, S):
    """PRJM-LC-01 — writes one event on the component's project with the component in the metadata.
    Rules: log_for_component R2, Returns; log_event R1."""
    P = proj(db, S, "Roof job", id=XID(1))
    C = comp(db, P, "Roof", id=XID(5))
    result = PM.log_for_component(db, component_id=C.id, workspace_id=S.W1.id, event_type="task_added",
                                  description="Added task Seal", performed_by=S.U2.id, metadata={"task": "Seal"})
    # Then 1
    assert isinstance(result, ProjectEvent)
    # Then 2
    assert result.id is not None
    # Then 3
    rows = events_of(db, P)
    assert len(rows) == 1
    row = rows[0]
    # Then 4
    assert row.project_id == XID(1)
    assert row.workspace_id == S.W1.id
    assert row.event_type == "task_added"
    # Then 5
    assert row.description == "Added task Seal"
    assert row.performed_by == S.U2.id
    # Then 6
    assert row.metadata_json == {"task": "Seal", "component_id": XID(5), "component_name": "Roof"}


def test_prjm_lc_02__no_metadata_gives_component_dict(db, S):
    """PRJM-LC-02 — with no metadata the stored metadata is the component dict, never null.
    Rules: log_for_component R2."""
    P = proj(db, S, "Roof job")
    C = comp(db, P, "Roof")
    result = PM.log_for_component(db, component_id=C.id, workspace_id=S.W1.id, event_type="note_added", description="Note")
    # Then 1
    assert result.id is not None
    row = reread(db, ProjectEvent, result.id)
    # Then 2
    assert row.metadata_json == {"component_id": C.id, "component_name": "Roof"}
    # Then 3
    assert row.performed_by is None


def test_prjm_lc_03__caller_component_keys_win(db, S):
    """PRJM-LC-03 — the caller's component keys win.
    Rules: log_for_component R2."""
    P = proj(db, S, "Roof job")
    C = comp(db, P, "Roof")
    result = PM.log_for_component(db, component_id=C.id, workspace_id=S.W1.id, event_type="note_added",
                                  description="Note", performed_by=S.U2.id,
                                  metadata={"component_id": 5, "component_name": "Old Roof"})
    # Then 1
    assert result.id is not None
    row = reread(db, ProjectEvent, result.id)
    # Then 2
    assert row.metadata_json == {"component_id": 5, "component_name": "Old Roof"}


def test_prjm_lc_04__caller_dict_not_changed(db, S):
    """PRJM-LC-04 — the caller's dict is not changed.
    Rules: log_for_component R2."""
    P = proj(db, S, "Roof job")
    C = comp(db, P, "Roof")
    meta = {"task": "Seal"}
    result = PM.log_for_component(db, component_id=C.id, workspace_id=S.W1.id, event_type="task_added",
                                  description="Added", performed_by=S.U2.id, metadata=meta)
    # Then 1
    assert result.id is not None
    # Then 2
    assert meta == {"task": "Seal"}


def test_prjm_lc_05__unknown_component_none(db, S):
    """PRJM-LC-05 — an unknown component returns None and writes nothing.
    Rules: log_for_component R1."""
    P = proj(db, S, "Roof job")
    comp(db, P, "Roof")
    before = counts(db)
    result = PM.log_for_component(db, component_id=MISSING, workspace_id=S.W1.id, event_type="note_added",
                                  description="Note", performed_by=S.U2.id)
    # Then 1
    assert result is None
    # Then 2
    assert not db.new
    # Then 3
    assert counts(db) == before


def test_prjm_lc_06__component_zero_none(db, S):
    """PRJM-LC-06 — component id 0 returns None and writes nothing.
    Rules: log_for_component R1."""
    P = proj(db, S, "Roof job")
    comp(db, P, "Roof")
    before = counts(db)
    result = PM.log_for_component(db, component_id=0, workspace_id=S.W1.id, event_type="note_added",
                                  description="Note", performed_by=S.U2.id)
    # Then 1
    assert result is None
    # Then 2
    assert not db.new
    # Then 3
    assert counts(db) == before


def test_prjm_lc_07__w0_component_none(db, S):
    """PRJM-LC-07 — a W0 component (lower id) returns None in W1.
    Rules: log_for_component R1."""
    P0 = proj(db, S, "Zero", where="W0")
    C0 = comp(db, P0, "Cellar")
    P = proj(db, S, "Roof job")
    comp(db, P, "Roof")
    before = counts(db)
    result = PM.log_for_component(db, component_id=C0.id, workspace_id=S.W1.id, event_type="note_added",
                                  description="Note", performed_by=S.U2.id)
    # Then 1
    assert result is None
    # Then 2
    assert not db.new
    # Then 3
    assert counts(db) == before


def test_prjm_lc_08__w2_component_none(db, S):
    """PRJM-LC-08 — a W2 component (higher id) returns None in W1.
    Rules: log_for_component R1."""
    P = proj(db, S, "Roof job")
    comp(db, P, "Roof")
    P9 = proj(db, S, "Nine", where="W2")
    C9 = comp(db, P9, "Floor")
    before = counts(db)
    result = PM.log_for_component(db, component_id=C9.id, workspace_id=S.W1.id, event_type="note_added",
                                  description="Note", performed_by=S.U2.id)
    # Then 1
    assert result is None
    # Then 2
    assert not db.new
    # Then 3
    assert counts(db) == before


def test_prjm_lc_09__does_not_commit(db, S):
    """PRJM-LC-09 — log_for_component does not commit.
    Rules: log_for_component R2 (Overview: never commits)."""
    P = proj(db, S, "Roof job")
    C = comp(db, P, "Roof")
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        PM.log_for_component(db, component_id=C.id, workspace_id=S.W1.id, event_type="note_added",
                             description="Note", performed_by=S.U2.id)
        sp.rollback()
    # Then 1
    assert cm.call_count == 0
    # Then 2
    assert len(events_of(db, P)) == 0


# =========================================================================== #
# log_event
# =========================================================================== #

def test_prjm_le_01__writes_row_exactly(db, S):
    """PRJM-LE-01 — writes one row with exactly the values given, flushed.
    Rules: log_event R1, Returns."""
    P = proj(db, S, "Roof job")
    result = PM.log_event(db, project_id=P.id, workspace_id=S.W1.id, event_type="cost_added",
                          description="Added cost", performed_by=S.U2.id, metadata={"amount": "10.50"})
    # Then 1
    assert isinstance(result, ProjectEvent)
    # Then 2
    assert result.id is not None
    # Then 3
    rows = events_of(db, P)
    assert len(rows) == 1
    row = rows[0]
    # Then 4
    assert row.workspace_id == S.W1.id
    assert row.project_id == P.id
    assert row.event_type == "cost_added"
    # Then 5
    assert row.description == "Added cost"
    assert row.performed_by == S.U2.id
    # Then 6
    assert row.metadata_json == {"amount": "10.50"}
    assert row.created_at is not None


def test_prjm_le_02__no_metadata_no_performer_null(db, S):
    """PRJM-LE-02 — no metadata and no performer are stored as null.
    Rules: log_event R1."""
    P = proj(db, S, "Roof job")
    result = PM.log_event(db, project_id=P.id, workspace_id=S.W1.id, event_type="note", description="Plain")
    # Then 1
    assert result.id is not None
    row = reread(db, ProjectEvent, result.id)
    # Then 2
    assert row.metadata_json is None
    assert row.performed_by is None


def test_prjm_le_03__deleted_project_logged_to(db, S):
    """PRJM-LE-03 — a soft-deleted project of the workspace is logged to.
    Rules: log_event R3."""
    P = proj(db, S, "Gone", deleted=True)
    result = PM.log_event(db, project_id=P.id, workspace_id=S.W1.id, event_type="note",
                          description="After close", performed_by=S.U2.id)
    # Then 1
    assert result.id is not None
    # Then 2
    assert len(events_of(db, P)) == 1


def test_prjm_le_04__event_type_50_chars(db, S):
    """PRJM-LE-04 — an event type of 50 characters is stored.
    Rules: log_event R4."""
    P = proj(db, S, "Roof job")
    result = PM.log_event(db, project_id=P.id, workspace_id=S.W1.id, event_type="e" * 50,
                          description="Long", performed_by=S.U2.id)
    # Then 1
    assert result.id is not None
    row = reread(db, ProjectEvent, result.id)
    # Then 2
    assert row.event_type == "e" * 50


def test_prjm_le_05__event_type_51_chars_fails(db, S):
    """PRJM-LE-05 — an event type of 51 characters fails at the flush.
    Rules: log_event R4."""
    P = proj(db, S, "Roof job")
    # Then 1
    with pytest.raises(DataError):
        with db.begin_nested():
            PM.log_event(db, project_id=P.id, workspace_id=S.W1.id, event_type="e" * 51,
                         description="Long", performed_by=S.U2.id)
    # Then 2
    assert len(events_of(db, P)) == 0


@pytest.mark.xfail(strict=True, reason="BUG-1192: log_event does not check the project against the workspace")
def test_prjm_le_06__w2_project_refused(db, S):
    """PRJM-LE-06 — a W2 project (higher id) is refused as not found.
    Rules: log_event R2 [BUG-1192]."""
    proj(db, S, "Roof job")
    P9 = proj(db, S, "Nine", where="W2")
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.log_event(db, project_id=P9.id, workspace_id=S.W1.id, event_type="note",
                     description="Stray", performed_by=S.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project with ID {P9.id} not found"
    # Then 4
    assert not db.new
    # Then 5
    assert counts(db) == before


@pytest.mark.xfail(strict=True, reason="BUG-1192: log_event does not check the project against the workspace")
def test_prjm_le_07__w0_project_refused(db, S):
    """PRJM-LE-07 — a W0 project (lower id) is refused as not found.
    Rules: log_event R2 [BUG-1192]."""
    P0 = proj(db, S, "Zero", where="W0")
    proj(db, S, "Roof job")
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.log_event(db, project_id=P0.id, workspace_id=S.W1.id, event_type="note",
                     description="Stray", performed_by=S.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project with ID {P0.id} not found"
    # Then 4
    assert not db.new
    # Then 5
    assert counts(db) == before


@pytest.mark.xfail(strict=True, reason="BUG-1192: log_event does not check the project against the workspace")
def test_prjm_le_08__unknown_project_refused(db, S):
    """PRJM-LE-08 — an unknown project id is refused as not found.
    Rules: log_event R2 [BUG-1192]."""
    proj(db, S, "Roof job")
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with db.begin_nested():
            PM.log_event(db, project_id=MISSING, workspace_id=S.W1.id, event_type="note",
                         description="Stray", performed_by=S.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Project with ID 999999999 not found"
    # Then 4
    assert counts(db) == before


@pytest.mark.xfail(strict=True, reason="BUG-1192: log_event does not check the project against the workspace")
def test_prjm_le_09__project_zero_refused(db, S):
    """PRJM-LE-09 — project id 0 is refused as not found.
    Rules: log_event R2 [BUG-1192]."""
    proj(db, S, "Roof job")
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with db.begin_nested():
            PM.log_event(db, project_id=0, workspace_id=S.W1.id, event_type="note",
                         description="Stray", performed_by=S.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Project with ID 0 not found"
    # Then 4
    assert counts(db) == before


def test_prjm_le_10__does_not_commit(db, S):
    """PRJM-LE-10 — log_event does not commit.
    Rules: log_event R1."""
    P = proj(db, S, "Roof job")
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        PM.log_event(db, project_id=P.id, workspace_id=S.W1.id, event_type="note",
                     description="Plain", performed_by=S.U2.id)
        sp.rollback()
    # Then 1
    assert cm.call_count == 0
    # Then 2
    assert len(events_of(db, P)) == 0


# =========================================================================== #
# list_events
# =========================================================================== #

def test_prjm_ev_01__newest_first_with_profiles(db, S):
    """PRJM-EV-01 — newest first, id breaks ties, each with its performer's profile.
    Rules: list_events R3, Returns."""
    P = proj(db, S, "Roof job")
    EA = ev(db, P, "a", T1, S.U1.id)
    EB = ev(db, P, "b", T3, None)
    EC = ev(db, P, "c", T2, S.U2.id)
    ED = ev(db, P, "d", T3, S.UG.id)
    result = PM.list_events(db, project_id=P.id, workspace_id=S.W1.id, user_id=S.UG.id)
    # Then 1
    assert [e.id for e, _ in result] == [ED.id, EB.id, EC.id, EA.id]
    # Then 2
    assert [(p.id if p is not None else None) for _, p in result] == [S.UG.id, None, S.U2.id, S.U1.id]
    # Then 3
    assert isinstance(result, list)


def test_prjm_ev_02__other_project_and_workspace_not_listed(db, S):
    """PRJM-EV-02 — events of another project and of another workspace are not listed.
    Rules: list_events R3."""
    P = proj(db, S, "Roof job")
    Q = proj(db, S, "Wall job")
    E1 = ev(db, P, "a", T1, S.U1.id)
    ev(db, Q, "b", T2, S.U1.id)
    _add(db, ProjectEvent(workspace_id=S.W2.id, project_id=P.id, event_type="c", description="seed",
                          performed_by=S.U1.id, created_at=T3, metadata_json=None))
    result = PM.list_events(db, project_id=P.id, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 1
    assert [e.id for e, _ in result] == [E1.id]


def test_prjm_ev_03__no_events_empty(db, S):
    """PRJM-EV-03 — a project with no events gives an empty list.
    Rules: list_events R3."""
    P = proj(db, S, "Roof job")
    result = PM.list_events(db, project_id=P.id, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 1
    assert result == []


def test_prjm_ev_04__deleted_project_log_answered(db, S):
    """PRJM-EV-04 — a soft-deleted project's log is still answered.
    Rules: list_events R2."""
    P = proj(db, S, "Gone", deleted=True)
    E1 = ev(db, P, "deleted", T1, S.U1.id)
    result = PM.list_events(db, project_id=P.id, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 1
    assert [e.id for e, _ in result] == [E1.id]


def test_prjm_ev_05__private_log_403(db, S):
    """PRJM-EV-05 — a private project's log is 403 for a plain member.
    Rules: list_events R1."""
    P = proj(db, S, "Secret", private=True)
    ev(db, P, "a", T1, S.U1.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.list_events(db, project_id=P.id, workspace_id=S.W1.id, user_id=S.UG.id)
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == "You do not have access to this project"


def test_prjm_ev_06__private_log_open_to_creator(db, S):
    """PRJM-EV-06 — a private project's log is open to its creator.
    Rules: list_events R1."""
    P = proj(db, S, "Secret", private=True, created_by=S.UG.id)
    E1 = ev(db, P, "a", T1, S.U1.id)
    result = PM.list_events(db, project_id=P.id, workspace_id=S.W1.id, user_id=S.UG.id)
    # Then 1
    assert [e.id for e, _ in result] == [E1.id]


def test_prjm_ev_07__other_workspace_404(db, S):
    """PRJM-EV-07 — another workspace's project is 404.
    Rules: list_events R1."""
    P9 = proj(db, S, "Nine", where="W2")
    ev(db, P9, "a", T1, S.U1.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.list_events(db, project_id=P9.id, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project with ID {P9.id} not found"


@pytest.mark.xfail(strict=True, reason="BUG-1964: list_events reads one profile per entry")
def test_prjm_ev_08__performers_read_together(db, S):
    """PRJM-EV-08 — performers are read together: at most three statements besides the project read.
    Rules: list_events R4 [BUG-1964]."""
    P = proj(db, S, "Roof job")
    UX = make_profile(db, name="Omar Ali")
    UY = make_profile(db, name="Rina Das")
    ev(db, P, "a", T1, S.U1.id)
    ev(db, P, "b", T1, S.U2.id)
    ev(db, P, "c", T2, S.UG.id)
    ev(db, P, "d", T2, UX.id)
    ev(db, P, "e", T3, UY.id)
    # The call's arguments are read before the expiry, so refreshing W1 / UG for
    # them is not counted as a statement of list_events.
    project_id, workspace_id, user_id = P.id, S.W1.id, S.UG.id
    db.expire_all()
    stmts, stop = recorder(db)
    result = PM.list_events(db, project_id=project_id, workspace_id=workspace_id, user_id=user_id)
    stop()
    # Then 1
    assert len(result) == 5
    # Then 2
    assert len([s for s in stmts if "FROM projects" not in s]) <= 3


# =========================================================================== #
# list_members
# =========================================================================== #

def test_prjm_lm_01__order_of_assigned_at(db, S):
    """PRJM-LM-01 — members in order of assigned_at, not of id.
    Rules: list_members R2."""
    P = proj(db, S, "Roof job")
    MA = pmem(db, S, P, S.U1, assigned_at=T2)
    MB = pmem(db, S, P, S.U2, assigned_at=T1)
    MC = pmem(db, S, P, S.UG, assigned_at=T3)
    result = PM.list_members(db, project_id=P.id, workspace_id=S.W1.id, user_id=S.UG.id)
    # Then 1
    assert [m.id for m in result] == [MB.id, MA.id, MC.id]


def test_prjm_lm_02__other_project_not_listed(db, S):
    """PRJM-LM-02 — members of another project are not listed; a person who left the workspace is.
    Rules: list_members R2."""
    UX = make_profile(db, name="Omar Ali")
    Q = proj(db, S, "Wall job")
    P = proj(db, S, "Roof job")
    pmem(db, S, Q, S.U1, assigned_at=T1)
    MX = pmem(db, S, P, UX, assigned_at=T2)
    result = PM.list_members(db, project_id=P.id, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 1
    assert [m.id for m in result] == [MX.id]


@pytest.mark.xfail(strict=False, reason="BUG-1274: project members with one assigned_at have no id tie-break")
def test_prjm_lm_03__tie_by_id(db, S):
    """PRJM-LM-03 — members with one assigned_at come back by id.
    Rules: list_members R2 (project member DAO R4 [BUG-1274])."""
    # [claude] PRJM-LM-03
    P = proj(db, S, "Roof job")
    MA = pmem(db, S, P, S.U1, assigned_at=T1)
    MB = pmem(db, S, P, S.U2, assigned_at=T1)
    db.execute(text("SET LOCAL enable_indexscan = off"))
    db.execute(text("SET LOCAL enable_bitmapscan = off"))
    db.execute(text("SET LOCAL enable_indexonlyscan = off"))
    db.execute(text("UPDATE project_members SET assigned_by = assigned_by WHERE id = :i"), {"i": MA.id})
    db.expire_all()
    result = PM.list_members(db, project_id=P.id, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 1
    assert [m.id for m in result] == [MA.id, MB.id]


def test_prjm_lm_04__private_members_403(db, S):
    """PRJM-LM-04 — a private project's members are 403 for a plain member.
    Rules: list_members R1."""
    P = proj(db, S, "Secret", private=True)
    pmem(db, S, P, S.U1)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.list_members(db, project_id=P.id, workspace_id=S.W1.id, user_id=S.UG.id)
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == "You do not have access to this project"


def test_prjm_lm_05__other_workspace_404(db, S):
    """PRJM-LM-05 — another workspace's project is 404.
    Rules: list_members R1."""
    P9 = proj(db, S, "Nine", where="W2")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.list_members(db, project_id=P9.id, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project with ID {P9.id} not found"


@pytest.mark.xfail(strict=True, reason="BUG-1278: a soft-deleted project's members and components answer 404")
def test_prjm_lm_06__deleted_project_members_404(db, S):
    """PRJM-LM-06 — a soft-deleted project's members are 404.
    Rules: list_members R1 [BUG-1278]; require_project_access R3."""
    P = proj(db, S, "Gone", deleted=True)
    pmem(db, S, P, S.U1)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.list_members(db, project_id=P.id, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project with ID {P.id} not found"


# =========================================================================== #
# add_member
# =========================================================================== #

def test_prjm_am_01__adds_and_logs(db, S):
    """PRJM-AM-01 — adds an active member and logs member_added with their name.
    Rules: add_member R4, Returns."""
    UX = make_profile(db, name="Omar Ali")
    member(db, S, UX, "ground-team")
    P = proj(db, S, "Secret", private=True)
    result = PM.add_member(db, project_id=P.id, member_user_id=UX.id, workspace_id=S.W1.id, assigned_by=S.U2.id)
    # Then 1
    assert isinstance(result, ProjectMember)
    # Then 2
    assert result.id is not None
    # Then 3
    rows = members_of(db, P)
    assert len(rows) == 1
    row = rows[0]
    # Then 4
    assert row.workspace_id == S.W1.id
    assert row.project_id == P.id
    assert row.user_id == UX.id
    assert row.assigned_by == S.U2.id
    assert row.assigned_at is not None
    # Then 5
    evs = events_of(db, P)
    assert len(evs) == 1
    e = evs[0]
    # Then 6
    assert e.event_type == "member_added"
    assert e.description == "Added Omar Ali to the project"
    assert e.performed_by == S.U2.id
    assert e.workspace_id == S.W1.id
    # Then 7
    assert e.metadata_json == {"user_id": UX.id, "user_name": "Omar Ali"}


def test_prjm_am_02__workspace_project_plain_member_adds(db, S):
    """PRJM-AM-02 — works the same on a workspace-visible project, added by a plain member.
    Rules: add_member R1, R4."""
    UX = make_profile(db, name="Omar Ali")
    member(db, S, UX, "finance")
    P = proj(db, S, "Roof job")
    result = PM.add_member(db, project_id=P.id, member_user_id=UX.id, workspace_id=S.W1.id, assigned_by=S.UG.id)
    # Then 1
    assert result.user_id == UX.id
    row = reread(db, ProjectMember, result.id)
    # Then 2
    assert row.assigned_by == S.UG.id
    # Then 3
    evs = events_of(db, P)
    assert len(evs) == 1
    # Then 4
    assert evs[0].description == "Added Omar Ali to the project"
    assert evs[0].performed_by == S.UG.id


def test_prjm_am_03__member_of_other_projects_added_here(db, S):
    """PRJM-AM-03 — a member of another project only is added here.
    Rules: add_member R3, R4."""
    UX = make_profile(db, name="Omar Ali")
    member(db, S, UX, "ground-team")
    Q = proj(db, S, "Wall job")
    P = proj(db, S, "Roof job")
    R = proj(db, S, "Yard job")
    pmem(db, S, Q, UX)
    pmem(db, S, R, UX)
    result = PM.add_member(db, project_id=P.id, member_user_id=UX.id, workspace_id=S.W1.id, assigned_by=S.U2.id)
    # Then 1
    assert result.project_id == P.id
    # Then 2
    assert len(members_of(db, P)) == 1


def test_prjm_am_04__no_membership_400(db, S):
    """PRJM-AM-04 — a person with no membership of the workspace is 400.
    Rules: add_member R2."""
    UX = make_profile(db, name="Omar Ali")
    P = proj(db, S, "Roof job")
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.add_member(db, project_id=P.id, member_user_id=UX.id, workspace_id=S.W1.id, assigned_by=S.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "User is not an active member of this workspace"
    # Then 4
    assert not db.new
    # Then 5
    assert counts(db) == before


def test_prjm_am_05__unknown_user_400(db, S):
    """PRJM-AM-05 — an unknown user id is 400.
    Rules: add_member R2."""
    P = proj(db, S, "Roof job")
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.add_member(db, project_id=P.id, member_user_id=MISSING, workspace_id=S.W1.id, assigned_by=S.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "User is not an active member of this workspace"
    # Then 4
    assert counts(db) == before


@pytest.mark.parametrize(("role", "status", "ws"), [
    pytest.param("owner", "active", "W0", id="PRJM-AM-06"),
    pytest.param("owner", "active", "W2", id="PRJM-AM-07"),
    pytest.param("ground-team", "suspended", "W1", id="PRJM-AM-08"),
    pytest.param("ground-team", "invited", "W1", id="PRJM-AM-09"),
    pytest.param("ground-team", "inactive", "W1", id="PRJM-AM-10"),
    pytest.param("ground-team", "Active", "W1", id="PRJM-AM-11"),
])
def test_prjm_am_06_11__not_active_member_of_w1_400(db, S, role, status, ws):
    """PRJM-AM-06 … AM-11 — a membership of another workspace only, or not exactly "active", is 400.
    Rules: add_member R2."""
    UX = make_profile(db, name="Omar Ali")
    member(db, S, UX, role, status=status, ws=getattr(S, ws))
    P = proj(db, S, "Roof job")
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.add_member(db, project_id=P.id, member_user_id=UX.id, workspace_id=S.W1.id, assigned_by=S.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "User is not an active member of this workspace"
    # Then 4
    assert counts(db) == before


def test_prjm_am_12__already_member_409(db, S):
    """PRJM-AM-12 — someone already a member is 409.
    Rules: add_member R3."""
    UX = make_profile(db, name="Omar Ali")
    member(db, S, UX, "ground-team")
    P = proj(db, S, "Roof job")
    MX = pmem(db, S, P, UX)
    before_mx = snap(db, MX)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.add_member(db, project_id=P.id, member_user_id=UX.id, workspace_id=S.W1.id, assigned_by=S.U2.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "User is already a member of this project"
    # Then 4
    assert not db.new and not db.dirty
    # Then 5
    assert unchanged(db, MX, before_mx)
    # Then 6
    assert counts(db) == before


def test_prjm_am_13__creator_409(db, S):
    """PRJM-AM-13 — the creator, a member from creation, is 409.
    Rules: add_member R3."""
    P = proj(db, S, "Roof job")
    pmem(db, S, P, S.U1, assigned_by=S.U1.id)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.add_member(db, project_id=P.id, member_user_id=S.U1.id, workspace_id=S.W1.id, assigned_by=S.U2.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "User is already a member of this project"
    # Then 4
    assert not db.new and not db.dirty
    # Then 5
    assert counts(db) == before


def test_prjm_am_14__suspended_existing_member_400(db, S):
    """PRJM-AM-14 — a suspended person already on the project gets 400 (status is checked first).
    Rules: add_member R2, R3."""
    UX = make_profile(db, name="Omar Ali")
    member(db, S, UX, "ground-team", status="suspended")
    P = proj(db, S, "Roof job")
    pmem(db, S, P, UX)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.add_member(db, project_id=P.id, member_user_id=UX.id, workspace_id=S.W1.id, assigned_by=S.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "User is not an active member of this workspace"
    # Then 4
    assert counts(db) == before


def test_prjm_am_15__caller_without_access_403(db, S):
    """PRJM-AM-15 — a caller who may not open the private project is 403.
    Rules: add_member R1."""
    UX = make_profile(db, name="Omar Ali")
    member(db, S, UX, "ground-team")
    P = proj(db, S, "Secret", private=True)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.add_member(db, project_id=P.id, member_user_id=UX.id, workspace_id=S.W1.id, assigned_by=S.UG.id)
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == "You do not have access to this project"
    # Then 4
    assert counts(db) == before


def test_prjm_am_16__other_workspace_404(db, S):
    """PRJM-AM-16 — another workspace's project is 404.
    Rules: add_member R1."""
    UX = make_profile(db, name="Omar Ali")
    member(db, S, UX, "ground-team")
    P9 = proj(db, S, "Nine", where="W2")
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.add_member(db, project_id=P9.id, member_user_id=UX.id, workspace_id=S.W1.id, assigned_by=S.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project with ID {P9.id} not found"
    # Then 4
    assert counts(db) == before


@pytest.mark.xfail(strict=True, reason="BUG-1278: a soft-deleted project's members and components answer 404")
def test_prjm_am_17__deleted_project_404(db, S):
    """PRJM-AM-17 — a soft-deleted project is 404 and nobody is added.
    Rules: add_member R1 [BUG-1278]."""
    UX = make_profile(db, name="Omar Ali")
    member(db, S, UX, "ground-team")
    P = proj(db, S, "Gone", deleted=True)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.add_member(db, project_id=P.id, member_user_id=UX.id, workspace_id=S.W1.id, assigned_by=S.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project with ID {P.id} not found"
    # Then 4
    assert not db.new
    # Then 5
    assert counts(db) == before


def test_prjm_am_18__does_not_commit(db, S):
    """PRJM-AM-18 — add_member does not commit.
    Rules: add_member R4."""
    UX = make_profile(db, name="Omar Ali")
    member(db, S, UX, "ground-team")
    P = proj(db, S, "Roof job")
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        PM.add_member(db, project_id=P.id, member_user_id=UX.id, workspace_id=S.W1.id, assigned_by=S.U2.id)
        sp.rollback()
    # Then 1
    assert cm.call_count == 0
    # Then 2
    assert len(members_of(db, P)) == 0
    # Then 3
    assert len(events_of(db, P)) == 0


# =========================================================================== #
# remove_member
# =========================================================================== #

def test_prjm_rm_01__removes_and_logs(db, S):
    """PRJM-RM-01 — removes the row and logs member_removed with their name.
    Rules: remove_member R4."""
    UX = make_profile(db, name="Omar Ali")
    member(db, S, UX, "ground-team")
    P = proj(db, S, "Secret", private=True)
    MU = pmem(db, S, P, S.U2)
    pmem(db, S, P, UX)
    result = PM.remove_member(db, project_id=P.id, member_user_id=UX.id, workspace_id=S.W1.id, performed_by=S.U2.id)
    # Then 1
    assert result is None
    # Then 2
    assert [m.id for m in members_of(db, P)] == [MU.id]
    # Then 3
    evs = events_of(db, P)
    assert len(evs) == 1
    e = evs[0]
    # Then 4
    assert e.event_type == "member_removed"
    assert e.description == "Removed Omar Ali from the project"
    assert e.performed_by == S.U2.id
    assert e.workspace_id == S.W1.id
    # Then 5
    assert e.metadata_json == {"user_id": UX.id, "user_name": "Omar Ali"}


def test_prjm_rm_02__lower_id_member_removed(db, S):
    """PRJM-RM-02 — a member with a lower id than the creator is removed.
    Rules: remove_member R2, R4."""
    UX = make_profile(db, name="Omar Ali")
    P = proj(db, S, "Roof job", created_by=UX.id)
    pmem(db, S, P, S.U1)
    result = PM.remove_member(db, project_id=P.id, member_user_id=S.U1.id, workspace_id=S.W1.id, performed_by=S.U2.id)
    # Then 1
    assert result is None
    # Then 2
    assert len(members_of(db, P)) == 0
    # Then 3
    assert len(events_of(db, P)) == 1


def test_prjm_rm_03__left_workspace_removed(db, S):
    """PRJM-RM-03 — a person who left the workspace can be removed.
    Rules: remove_member R4."""
    UX = make_profile(db, name="Omar Ali")
    P = proj(db, S, "Roof job")
    pmem(db, S, P, UX)
    result = PM.remove_member(db, project_id=P.id, member_user_id=UX.id, workspace_id=S.W1.id, performed_by=S.U2.id)
    # Then 1
    assert result is None
    # Then 2
    assert len(members_of(db, P)) == 0
    # Then 3
    (e,) = events_of(db, P)
    assert e.description == "Removed Omar Ali from the project"


def test_prjm_rm_04__member_removes_self(db, S):
    """PRJM-RM-04 — a member may remove themselves.
    Rules: remove_member R1, R4."""
    P = proj(db, S, "Secret", private=True)
    pmem(db, S, P, S.UG)
    result = PM.remove_member(db, project_id=P.id, member_user_id=S.UG.id, workspace_id=S.W1.id, performed_by=S.UG.id)
    # Then 1
    assert result is None
    # Then 2
    assert len(members_of(db, P)) == 0
    # Then 3
    (e,) = events_of(db, P)
    assert e.performed_by == S.UG.id
    assert e.description == "Removed Mia Khan from the project"


def test_prjm_rm_05__creator_400(db, S):
    """PRJM-RM-05 — removing the creator is 400 and nothing is deleted.
    Rules: remove_member R2."""
    P = proj(db, S, "Roof job")
    M1 = pmem(db, S, P, S.U1)
    before_m1 = snap(db, M1)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.remove_member(db, project_id=P.id, member_user_id=S.U1.id, workspace_id=S.W1.id, performed_by=S.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot remove the project creator from members"
    # Then 4
    assert not db.deleted and not db.new
    # Then 5
    assert unchanged(db, M1, before_m1)
    # Then 6
    assert counts(db) == before


def test_prjm_rm_06__creator_check_before_lookup(db, S):
    """PRJM-RM-06 — the creator check comes before the membership lookup.
    Rules: remove_member R2, R3."""
    P = proj(db, S, "Roof job")
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.remove_member(db, project_id=P.id, member_user_id=S.U1.id, workspace_id=S.W1.id, performed_by=S.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot remove the project creator from members"
    # Then 4
    assert not db.deleted and not db.new
    # Then 5
    assert counts(db) == before


def test_prjm_rm_07__no_creator_member_removed(db, S):
    """PRJM-RM-07 — a project with no creator: a member is removed.
    Rules: remove_member R2, R4."""
    P = proj(db, S, "Roof job", created_by=None)
    pmem(db, S, P, S.UG)
    result = PM.remove_member(db, project_id=P.id, member_user_id=S.UG.id, workspace_id=S.W1.id, performed_by=S.U2.id)
    # Then 1
    assert result is None
    # Then 2
    assert len(members_of(db, P)) == 0


def test_prjm_rm_08__not_on_project_404(db, S):
    """PRJM-RM-08 — someone not on the project is 404.
    Rules: remove_member R3."""
    P = proj(db, S, "Roof job")
    M2 = pmem(db, S, P, S.U2)
    before_m2 = snap(db, M2)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.remove_member(db, project_id=P.id, member_user_id=S.UG.id, workspace_id=S.W1.id, performed_by=S.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Project member not found"
    # Then 4
    assert unchanged(db, M2, before_m2)
    # Then 5
    assert counts(db) == before


def test_prjm_rm_09__member_of_other_projects_404(db, S):
    """PRJM-RM-09 — a membership of other projects only (lower and higher id) is 404 here.
    Rules: remove_member R3."""
    Q = proj(db, S, "Wall job")
    P = proj(db, S, "Roof job")
    R = proj(db, S, "Yard job")
    MQ = pmem(db, S, Q, S.UG)
    MR = pmem(db, S, R, S.UG)
    before_mq = snap(db, MQ)
    before_mr = snap(db, MR)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.remove_member(db, project_id=P.id, member_user_id=S.UG.id, workspace_id=S.W1.id, performed_by=S.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Project member not found"
    # Then 4
    assert unchanged(db, MQ, before_mq)
    # Then 5
    assert unchanged(db, MR, before_mr)
    # Then 6
    assert counts(db) == before


def test_prjm_rm_10__caller_without_access_403(db, S):
    """PRJM-RM-10 — a caller who may not open the private project is 403.
    Rules: remove_member R1."""
    P = proj(db, S, "Secret", private=True)
    M2 = pmem(db, S, P, S.U2)
    before_m2 = snap(db, M2)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.remove_member(db, project_id=P.id, member_user_id=S.U2.id, workspace_id=S.W1.id, performed_by=S.UG.id)
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == "You do not have access to this project"
    # Then 4
    assert unchanged(db, M2, before_m2)
    # Then 5
    assert counts(db) == before


def test_prjm_rm_11__other_workspace_404(db, S):
    """PRJM-RM-11 — another workspace's project is 404.
    Rules: remove_member R1."""
    P9 = proj(db, S, "Nine", where="W2")
    M9 = pmem(db, S, P9, S.UG)
    before_m9 = snap(db, M9)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.remove_member(db, project_id=P9.id, member_user_id=S.UG.id, workspace_id=S.W1.id, performed_by=S.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project with ID {P9.id} not found"
    # Then 4
    assert unchanged(db, M9, before_m9)
    # Then 5
    assert counts(db) == before


@pytest.mark.xfail(strict=True, reason="BUG-1278: a soft-deleted project's members and components answer 404")
def test_prjm_rm_12__deleted_project_404(db, S):
    """PRJM-RM-12 — a soft-deleted project is 404 and nobody is removed.
    Rules: remove_member R1 [BUG-1278]."""
    P = proj(db, S, "Gone", deleted=True)
    pmem(db, S, P, S.UG)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.remove_member(db, project_id=P.id, member_user_id=S.UG.id, workspace_id=S.W1.id, performed_by=S.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project with ID {P.id} not found"
    # Then 4
    assert not db.deleted and not db.new
    # Then 5
    assert counts(db) == before


def test_prjm_rm_13__does_not_commit(db, S):
    """PRJM-RM-13 — remove_member does not commit.
    Rules: remove_member R4."""
    P = proj(db, S, "Roof job")
    pmem(db, S, P, S.UG)
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        PM.remove_member(db, project_id=P.id, member_user_id=S.UG.id, workspace_id=S.W1.id, performed_by=S.U2.id)
        sp.rollback()
    # Then 1
    assert cm.call_count == 0
    # Then 2
    assert len(members_of(db, P)) == 1
    # Then 3
    assert len(events_of(db, P)) == 0


# =========================================================================== #
# set_visibility
# =========================================================================== #

def test_prjm_sv_01__make_private(db, S):
    """PRJM-SV-01 — makes a project private, stamps it and logs the change.
    Rules: set_visibility R4."""
    P = proj(db, S, "Roof job")
    result = PM.set_visibility(db, project_id=P.id, visibility=ProjectVisibilityEnum.INVITED_ONLY,
                               workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 1
    assert result.id == P.id
    row = reread(db, Project, P.id)
    # Then 2
    assert row.visibility == "invited_only"
    assert row.updated_by == S.U2.id
    assert row.updated_at == NOW
    # Then 3
    evs = events_of(db, P)
    assert len(evs) == 1
    e = evs[0]
    # Then 4
    assert e.event_type == "visibility_updated"
    assert e.description == "Changed visibility from workspace to invited_only"
    assert e.performed_by == S.U2.id
    # Then 5
    assert e.metadata_json == {"changes": [
        {"field": "visibility", "label": "Visibility", "from_value": "workspace", "to_value": "invited_only"},
    ]}


def test_prjm_sv_02__member_makes_workspace_visible(db, S):
    """PRJM-SV-02 — a project member makes a private project workspace-visible.
    Rules: set_visibility R1, R4."""
    P = proj(db, S, "Secret", private=True)
    pmem(db, S, P, S.UG)
    result = PM.set_visibility(db, project_id=P.id, visibility=ProjectVisibilityEnum.WORKSPACE,
                               workspace_id=S.W1.id, user_id=S.UG.id)
    # Then 1
    assert result.id == P.id
    row = reread(db, Project, P.id)
    # Then 2
    assert row.visibility == "workspace"
    assert row.updated_by == S.UG.id
    (e,) = events_of(db, P)
    # Then 3
    assert e.description == "Changed visibility from invited_only to workspace"
    assert e.performed_by == S.UG.id
    # Then 4
    assert e.metadata_json == {"changes": [
        {"field": "visibility", "label": "Visibility", "from_value": "invited_only", "to_value": "workspace"},
    ]}


def test_prjm_sv_03__same_visibility_no_change(db, S):
    """PRJM-SV-03 — the same visibility returns the project unchanged, no stamp, no event.
    Rules: set_visibility R3."""
    P = proj(db, S, "Secret", private=True)
    before = snap(db, P)
    result = PM.set_visibility(db, project_id=P.id, visibility=ProjectVisibilityEnum.INVITED_ONLY,
                               workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 1
    assert result.id == P.id
    # Then 2
    assert unchanged(db, P, before)
    row = reread(db, Project, P.id)
    # Then 3
    assert row.updated_by is None
    assert row.updated_at is None
    # Then 4
    assert len(events_of(db, P)) == 0


def test_prjm_sv_04__deleted_project_400(db, S):
    """PRJM-SV-04 — a soft-deleted project is 400.
    Rules: set_visibility R2."""
    P = proj(db, S, "Gone", deleted=True)
    before_p = snap(db, P)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.set_visibility(db, project_id=P.id, visibility=ProjectVisibilityEnum.INVITED_ONLY,
                          workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update deleted project"
    # Then 4
    assert P not in db.dirty and not db.new
    # Then 5
    assert unchanged(db, P, before_p)
    # Then 6
    assert counts(db) == before


def test_prjm_sv_05__deleted_project_400_same_visibility(db, S):
    """PRJM-SV-05 — a soft-deleted project is 400 even when the visibility would not change.
    Rules: set_visibility R2."""
    P = proj(db, S, "Gone", deleted=True)
    before_p = snap(db, P)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.set_visibility(db, project_id=P.id, visibility=ProjectVisibilityEnum.WORKSPACE,
                          workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update deleted project"
    # Then 4
    assert P not in db.dirty and not db.new
    # Then 5
    assert unchanged(db, P, before_p)


def test_prjm_sv_06__caller_without_access_403(db, S):
    """PRJM-SV-06 — a caller who may not open the private project is 403.
    Rules: set_visibility R1."""
    P = proj(db, S, "Secret", private=True)
    before_p = snap(db, P)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.set_visibility(db, project_id=P.id, visibility=ProjectVisibilityEnum.WORKSPACE,
                          workspace_id=S.W1.id, user_id=S.UG.id)
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == "You do not have access to this project"
    # Then 4
    assert unchanged(db, P, before_p)
    # Then 5
    assert counts(db) == before


def test_prjm_sv_07__other_workspace_404(db, S):
    """PRJM-SV-07 — another workspace's project is 404.
    Rules: set_visibility R1."""
    P9 = proj(db, S, "Nine", where="W2")
    before_p9 = snap(db, P9)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.set_visibility(db, project_id=P9.id, visibility=ProjectVisibilityEnum.INVITED_ONLY,
                          workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project with ID {P9.id} not found"
    # Then 4
    assert unchanged(db, P9, before_p9)


def test_prjm_sv_08__does_not_commit(db, S):
    """PRJM-SV-08 — set_visibility does not commit.
    Rules: set_visibility R4."""
    P = proj(db, S, "Roof job")
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        PM.set_visibility(db, project_id=P.id, visibility=ProjectVisibilityEnum.INVITED_ONLY,
                          workspace_id=S.W1.id, user_id=S.U2.id)
        sp.rollback()
    # Then 1
    assert cm.call_count == 0
    # Then 2
    assert reread(db, Project, P.id).visibility == "workspace"
    # Then 3
    assert len(events_of(db, P)) == 0


# =========================================================================== #
# create_project
# =========================================================================== #

def n_rows(db, model, ws):
    """count: `<table>` rows with `workspace_id == ws.id`."""
    db.expire_all()
    return db.execute(select(func.count()).select_from(model).where(model.workspace_id == ws.id)).scalar_one()


def create(db, S, **fields):
    """The When of the create cards: ProjectCreate(factory_id=F1.id, **fields), in W1, by U2."""
    data = {"factory_id": S.F1.id, **fields}
    return PM.create_project(db, project_data=ProjectCreate(**data), workspace_id=S.W1.id, user_id=S.U2.id)


def test_prjm_c_01__stores_every_field(db, S):
    """PRJM-C-01 — create stores every sent field, in the caller's workspace, by the caller.
    Rules: create_project R3, Returns."""
    result = create(db, S, name="Line 3 refit", description="New press line", budget=Decimal("2500.50"),
                    deadline=datetime(2026, 6, 30, 17, 0, 0))  # noqa: DTZ001
    # Then 1
    assert isinstance(result, Project)
    # Then 2
    assert result.id is not None
    row = reread(db, Project, result.id)
    # Then 3
    assert row.factory_id == S.F1.id
    assert row.name == "Line 3 refit"
    assert row.description == "New press line"
    # Then 4
    assert row.budget == Decimal("2500.50")
    assert row.deadline == datetime(2026, 6, 30, 17, 0, 0)  # noqa: DTZ001
    # Then 5
    assert row.workspace_id == S.W1.id
    assert row.created_by == S.U2.id
    assert row.created_at is not None
    # Then 6
    assert n_rows(db, Project, S.W1) == 1


def test_prjm_c_02__new_project_defaults(db, S):
    """PRJM-C-02 — a new project is live, workspace-visible, planning, low priority, with no other stamps.
    Rules: create_project R3."""
    result = create(db, S, name="Roof job", description="Main")
    # Then 1
    assert result.id is not None
    row = reread(db, Project, result.id)
    # Then 2
    assert row.is_active is True
    assert row.is_deleted is False
    assert row.visibility == "workspace"
    # Then 3
    assert val(row.status) == "PLANNING"
    assert val(row.priority) == "LOW"
    # Then 4
    assert row.budget is None
    assert row.deadline is None
    assert row.start_date is None
    assert row.end_date is None
    # Then 5
    assert row.updated_by is None
    assert row.updated_at is None
    # Then 6
    assert row.deleted_by is None
    assert row.deleted_at is None


def test_prjm_c_03__creator_member_and_created_event(db, S):
    """PRJM-C-03 — the creator becomes a member and a created event is logged.
    Rules: create_project R3a."""
    result = create(db, S, name="Roof job", description="Main")
    # Then 1
    assert result.id is not None
    # Then 2
    mems = members_of(db, result)
    assert len(mems) == 1
    m = mems[0]
    # Then 3
    assert m.user_id == S.U2.id
    assert m.assigned_by == S.U2.id
    assert m.workspace_id == S.W1.id
    # Then 4
    evs = events_of(db, result)
    assert len(evs) == 1
    e = evs[0]
    # Then 5
    assert e.event_type == "created"
    assert e.description == 'Created project "Roof job"'
    assert e.performed_by == S.U2.id
    assert e.workspace_id == S.W1.id
    # Then 6
    assert e.metadata_json is None


def test_prjm_c_04__any_status_at_creation(db, S):
    """PRJM-C-04 — any status may be given at creation, COMPLETED included.
    Rules: create_project R3."""
    result = create(db, S, name="Roof job", description="Main", status=COMPLETED)
    # Then 1
    assert result.id is not None
    # Then 2
    assert val(reread(db, Project, result.id).status) == "COMPLETED"


def test_prjm_c_05__inactive_factory_accepted(db, S):
    """PRJM-C-05 — an inactive but live factory is accepted.
    Rules: create_project R2."""
    result = PM.create_project(db, project_data=ProjectCreate(factory_id=S.FI.id, name="Roof job", description="Main"),
                               workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, Project, result.id).factory_id == S.FI.id


def test_prjm_c_06__deleted_factory_400(db, S):
    """PRJM-C-06 — a soft-deleted factory is 400.
    Rules: create_project R2."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.create_project(db, project_data=ProjectCreate(factory_id=S.FD.id, name="Roof job", description="Main"),
                          workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot create project for deleted factory"
    # Then 4
    assert not db.new
    # Then 5
    assert counts(db) == before


def test_prjm_c_07__unknown_factory_404(db, S):
    """PRJM-C-07 — an unknown factory is 404.
    Rules: create_project R1."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.create_project(db, project_data=ProjectCreate(factory_id=MISSING, name="Roof job", description="Main"),
                          workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory with ID 999999999 not found"
    # Then 4
    assert counts(db) == before


def test_prjm_c_08__factory_zero_404(db, S):
    """PRJM-C-08 — factory id 0 is 404.
    Rules: create_project R1."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.create_project(db, project_data=ProjectCreate(factory_id=0, name="Roof job", description="Main"),
                          workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory with ID 0 not found"
    # Then 4
    assert counts(db) == before


def test_prjm_c_09__w0_factory_404(db, S):
    """PRJM-C-09 — a W0 factory (lower id) is 404 in W1.
    Rules: create_project R1 (HR-16)."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.create_project(db, project_data=ProjectCreate(factory_id=S.F0.id, name="Roof job", description="Main"),
                          workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory with ID {S.F0.id} not found"
    # Then 4
    assert not db.new
    # Then 5
    assert counts(db) == before


def test_prjm_c_10__w2_factory_404(db, S):
    """PRJM-C-10 — a W2 factory (higher id) is 404 in W1.
    Rules: create_project R1 (HR-16)."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.create_project(db, project_data=ProjectCreate(factory_id=S.F9.id, name="Roof job", description="Main"),
                          workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory with ID {S.F9.id} not found"
    # Then 4
    assert not db.new
    # Then 5
    assert counts(db) == before


def test_prjm_c_11__inner_spaces_and_case_kept(db, S):
    """PRJM-C-11 — the name's inner spaces and case are kept.
    Rules: create_project R4 (HR-1)."""
    result = create(db, S, name="Line  3 REFIT", description="Main")
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, Project, result.id).name == "Line  3 REFIT"


@pytest.mark.xfail(strict=True, reason="BUG-1951: project names are stored untrimmed and blank names are accepted")
def test_prjm_c_12__name_stored_trimmed(db, S):
    """PRJM-C-12 — the name is stored trimmed, also in the created event.
    Rules: create_project R4 [BUG-1951]."""
    result = create(db, S, name="  Line 3 refit ", description="Main")
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, Project, result.id).name == "Line 3 refit"
    # Then 3
    (e,) = events_of(db, result)
    assert e.description == 'Created project "Line 3 refit"'


@pytest.mark.xfail(strict=True, reason="BUG-1951: project names are stored untrimmed and blank names are accepted")
@pytest.mark.parametrize("name", [
    pytest.param("", id="PRJM-C-13"),
    pytest.param("   ", id="PRJM-C-14"),
])
def test_prjm_c_13_14__blank_name_refused(S, name):
    """PRJM-C-13, C-14 — an empty name, or one of only spaces, is refused by the schema.
    Rules: create_project R4 [BUG-1951]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        ProjectCreate(factory_id=S.F1.id, name=name, description="Main")
    # Then 2
    assert "name" in str(exc.value)


def test_prjm_c_15__one_letter_name_accepted(S):
    """PRJM-C-15 — a one-letter name is accepted by the schema.
    Rules: create_project R4 (other side of the blank boundary)."""
    result = ProjectCreate(factory_id=S.F1.id, name="A", description="Main")
    # Then 1
    assert result.name == "A"


@pytest.mark.parametrize("description", [
    pytest.param(" two coats ", id="PRJM-C-16"),
    pytest.param("", id="PRJM-C-17"),
])
def test_prjm_c_16_17__description_kept_as_typed(db, S, description):
    """PRJM-C-16, C-17 — the description is kept as typed, padded or empty.
    Rules: create_project R4."""
    result = create(db, S, name="Roof job", description=description)
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, Project, result.id).description == description


def test_prjm_c_18__budget_zero(db, S):
    """PRJM-C-18 — a budget of 0 is accepted.
    Rules: create_project R5."""
    result = create(db, S, name="Roof job", description="Main", budget=Decimal("0"))
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, Project, result.id).budget == Decimal("0.00")


def test_prjm_c_19__budget_null(db, S):
    """PRJM-C-19 — a budget of null is accepted.
    Rules: create_project R5."""
    result = create(db, S, name="Roof job", description="Main", budget=None)
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, Project, result.id).budget is None


@pytest.mark.parametrize("budget", [
    pytest.param(Decimal("1000.01"), id="PRJM-C-20"),
    pytest.param(Decimal("9999999999999.99"), id="PRJM-C-21"),
])
def test_prjm_c_20_21__budget_stored_exactly(db, S, budget):
    """PRJM-C-20, C-21 — a budget with two decimals, or 13 integer digits, is stored exactly.
    Rules: create_project R5 (HR-15)."""
    result = create(db, S, name="Roof job", description="Main", budget=budget)
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, Project, result.id).budget == budget


@pytest.mark.xfail(strict=True, reason="BUG-1962: a negative budget is accepted")
@pytest.mark.parametrize("budget", [
    pytest.param(Decimal("-5"), id="PRJM-C-22"),
    pytest.param(Decimal("-0.01"), id="PRJM-C-23"),
])
def test_prjm_c_22_23__negative_budget_refused(S, budget):
    """PRJM-C-22, C-23 — a negative budget is refused by the schema.
    Rules: create_project R5 [BUG-1962]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        ProjectCreate(factory_id=S.F1.id, name="Roof job", description="Main", budget=budget)
    # Then 2
    assert "budget" in str(exc.value)


@pytest.mark.xfail(strict=True, reason="BUG-1963: a budget with more than 2 decimals or 13 integer digits is accepted")
@pytest.mark.parametrize("budget", [
    pytest.param(Decimal("1000.005"), id="PRJM-C-24"),
    pytest.param(Decimal("10000000000000.00"), id="PRJM-C-25"),
])
def test_prjm_c_24_25__budget_precision_refused(S, budget):
    """PRJM-C-24, C-25 — a budget with three decimals, or 14 integer digits, is refused by the schema.
    Rules: create_project R5 [BUG-1963]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        ProjectCreate(factory_id=S.F1.id, name="Roof job", description="Main", budget=budget)
    # Then 2
    assert "budget" in str(exc.value)


def test_prjm_c_26__plan_limit_not_checked(db, S):
    """PRJM-C-26 — the plan's project limit is not checked.
    Rules: create_project R6."""
    plan = db.get(SubscriptionPlan, S.W1.subscription_plan_id)
    plan.max_projects = 1
    db.flush()
    proj(db, S, "First job")
    result = create(db, S, name="Second job", description="Main")
    # Then 1
    assert result.id is not None
    # Then 2
    assert n_rows(db, Project, S.W1) == 2


def test_prjm_c_27__does_not_commit(db, S):
    """PRJM-C-27 — create_project does not commit.
    Rules: create_project R3a."""
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        create(db, S, name="Roof job", description="Main")
        sp.rollback()
    # Then 1
    assert cm.call_count == 0
    # Then 2
    assert n_rows(db, Project, S.W1) == 0
    # Then 3
    assert n_rows(db, ProjectEvent, S.W1) == 0


# =========================================================================== #
# get_project
# =========================================================================== #

def test_prjm_g_01__returned_to_plain_member(db, S):
    """PRJM-G-01 — returns the project to a plain member.
    Rules: get_project R1."""
    proj(db, S, "Zero", where="W0")
    P = proj(db, S, "Roof job")
    proj(db, S, "Nine", where="W2")
    result = PM.get_project(db, project_id=P.id, workspace_id=S.W1.id, user_id=S.UG.id)
    # Then 1
    assert result.id == P.id
    # Then 2
    assert result.name == "Roof job"


def test_prjm_g_02__private_returned_to_creator(db, S):
    """PRJM-G-02 — a private project is returned to its creator.
    Rules: get_project R1."""
    P = proj(db, S, "Secret", private=True, created_by=S.UG.id)
    result = PM.get_project(db, project_id=P.id, workspace_id=S.W1.id, user_id=S.UG.id)
    # Then 1
    assert result.id == P.id


def test_prjm_g_03__private_403(db, S):
    """PRJM-G-03 — a private project the caller may not open is 403.
    Rules: get_project R1."""
    P = proj(db, S, "Secret", private=True)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.get_project(db, project_id=P.id, workspace_id=S.W1.id, user_id=S.UG.id)
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == "You do not have access to this project"


def test_prjm_g_04__unknown_404(db, S):
    """PRJM-G-04 — an unknown id is 404.
    Rules: get_project R1."""
    proj(db, S, "Roof job")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.get_project(db, project_id=MISSING, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Project with ID 999999999 not found"


def test_prjm_g_05__w2_project_404(db, S):
    """PRJM-G-05 — a W2 project is 404 in W1.
    Rules: get_project R1."""
    proj(db, S, "Roof job")
    P9 = proj(db, S, "Nine", where="W2")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.get_project(db, project_id=P9.id, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project with ID {P9.id} not found"


@pytest.mark.xfail(strict=True, reason="BUG-1954: get_project returns a soft-deleted project")
def test_prjm_g_06__deleted_404_by_default(db, S):
    """PRJM-G-06 — a soft-deleted project is 404 by default.
    Rules: get_project R2 [BUG-1954]; require_project_access R3."""
    P = proj(db, S, "Gone", deleted=True)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.get_project(db, project_id=P.id, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project with ID {P.id} not found"


@pytest.mark.xfail(strict=True, reason="BUG-1954: get_project has no include_deleted option")
def test_prjm_g_07__include_deleted_returns_it(db, S):
    """PRJM-G-07 — include_deleted=True returns a soft-deleted project.
    Rules: get_project R2 [BUG-1954]."""
    P = proj(db, S, "Gone", deleted=True)
    # Then 1 (the call itself raises TypeError today: no include_deleted parameter)
    result = PM.get_project(db, project_id=P.id, workspace_id=S.W1.id, user_id=S.U2.id, include_deleted=True)
    assert result.id == P.id
    # Then 2
    assert result.is_deleted is True


# =========================================================================== #
# delete_project
# =========================================================================== #

def test_prjm_d_01__soft_deletes_and_logs(db, S):
    """PRJM-D-01 — soft-deletes the project, stamps it, logs deleted, returns it.
    Rules: delete_project R3."""
    P = proj(db, S, "Roof job")
    result = PM.delete_project(db, project_id=P.id, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 1
    assert result.id == P.id
    row = reread(db, Project, P.id)
    # Then 2
    assert row.is_deleted is True
    assert row.deleted_at == NOW
    assert row.deleted_by == S.U2.id
    # Then 3
    assert row.is_active is True
    # Then 4
    evs = events_of(db, P)
    assert len(evs) == 1
    e = evs[0]
    # Then 5
    assert e.event_type == "deleted"
    assert e.description == 'Deactivated project "Roof job"'
    assert e.performed_by == S.U2.id
    assert e.workspace_id == S.W1.id
    # Then 6
    assert e.metadata_json is None


def test_prjm_d_02__inactive_stays_inactive(db, S):
    """PRJM-D-02 — an inactive project stays inactive when deleted.
    Rules: delete_project R3."""
    P = proj(db, S, "Roof job", is_active=False)
    result = PM.delete_project(db, project_id=P.id, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 1
    assert result.id == P.id
    row = reread(db, Project, P.id)
    # Then 2
    assert row.is_deleted is True
    assert row.is_active is False


def test_prjm_d_03__members_components_events_untouched(db, S):
    """PRJM-D-03 — members, components and earlier events are untouched; nothing blocks the delete.
    Rules: delete_project R3."""
    P = proj(db, S, "Roof job")
    MG = pmem(db, S, P, S.UG)
    C = comp(db, P, "Roof")
    E1 = ev(db, P, "created", T1, S.U1.id)
    b_mg, b_c, b_e1 = snap(db, MG), snap(db, C), snap(db, E1)
    result = PM.delete_project(db, project_id=P.id, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 1
    assert result.id == P.id
    # Then 2
    assert unchanged(db, MG, b_mg)
    # Then 3
    assert unchanged(db, C, b_c)
    # Then 4
    assert unchanged(db, E1, b_e1)
    # Then 5
    assert len(events_of(db, P)) == 2


def test_prjm_d_04__plain_member_deletes(db, S):
    """PRJM-D-04 — a plain member may delete a workspace-visible project.
    Rules: delete_project R1."""
    P = proj(db, S, "Roof job")
    result = PM.delete_project(db, project_id=P.id, workspace_id=S.W1.id, user_id=S.UG.id)
    # Then 1
    assert result.id == P.id
    row = reread(db, Project, P.id)
    # Then 2
    assert row.is_deleted is True
    assert row.deleted_by == S.UG.id


def test_prjm_d_05__already_deleted_400(db, S):
    """PRJM-D-05 — an already deleted project is 400.
    Rules: delete_project R2."""
    P = proj(db, S, "Gone", deleted=True)
    before_p = snap(db, P)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.delete_project(db, project_id=P.id, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Project is already deleted"
    # Then 4
    assert P not in db.dirty and not db.new
    # Then 5
    assert unchanged(db, P, before_p)
    # Then 6
    assert counts(db) == before


def test_prjm_d_06__caller_without_access_403(db, S):
    """PRJM-D-06 — a caller who may not open the private project is 403.
    Rules: delete_project R1."""
    P = proj(db, S, "Secret", private=True)
    before_p = snap(db, P)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.delete_project(db, project_id=P.id, workspace_id=S.W1.id, user_id=S.UG.id)
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == "You do not have access to this project"
    # Then 4
    assert unchanged(db, P, before_p)
    # Then 5
    assert counts(db) == before


def test_prjm_d_07__other_workspace_404(db, S):
    """PRJM-D-07 — another workspace's project is 404.
    Rules: delete_project R1."""
    P0 = proj(db, S, "Zero", where="W0")
    before_p0 = snap(db, P0)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        PM.delete_project(db, project_id=P0.id, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project with ID {P0.id} not found"
    # Then 4
    assert unchanged(db, P0, before_p0)
    # Then 5
    assert counts(db) == before


def test_prjm_d_08__does_not_commit(db, S):
    """PRJM-D-08 — delete_project does not commit.
    Rules: delete_project R3."""
    P = proj(db, S, "Roof job")
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        PM.delete_project(db, project_id=P.id, workspace_id=S.W1.id, user_id=S.U2.id)
        sp.rollback()
    # Then 1
    assert cm.call_count == 0
    # Then 2
    assert reread(db, Project, P.id).is_deleted is False
    # Then 3
    assert len(events_of(db, P)) == 0


# =========================================================================== #
# list_projects
# =========================================================================== #

def test_prjm_l_01__privileged_gets_private_too(db, S):
    """PRJM-L-01 — a privileged caller gets every live project of the workspace, private ones included.
    Rules: list_projects R6, Returns."""
    proj(db, S, "Zero", where="W0")
    PA = proj(db, S, "Alpha")
    PV = proj(db, S, "Vault", private=True)
    proj(db, S, "Nine", where="W2")
    result = PM.list_projects(db, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert idset(result) == {PA.id, PV.id}


def test_prjm_l_02__plain_caller_sees_what_they_may_open(db, S):
    """PRJM-L-02 — a plain caller gets workspace projects and the private ones they may open.
    Rules: list_projects R7."""
    PA = proj(db, S, "Alpha")
    proj(db, S, "Vault", private=True)
    PM1 = proj(db, S, "Member Job", private=True)
    PC = proj(db, S, "Own Job", private=True, created_by=S.UG.id)
    pmem(db, S, PM1, S.UG)
    result = PM.list_projects(db, workspace_id=S.W1.id, user_id=S.UG.id)
    # Then 1
    assert idset(result) == {PA.id, PM1.id, PC.id}


def test_prjm_l_03__workspace_owner_sees_private(db, S):
    """PRJM-L-03 — the workspace owner with no membership gets private projects too.
    Rules: list_projects R6; _is_privileged R1."""
    UX = make_profile(db, name="Omar Ali")
    set_owner(db, S.W1, UX)
    PA = proj(db, S, "Alpha")
    PV = proj(db, S, "Vault", private=True)
    result = PM.list_projects(db, workspace_id=S.W1.id, user_id=UX.id)
    # Then 1
    assert idset(result) == {PA.id, PV.id}


def test_prjm_l_04__owning_w0_no_private(db, S):
    """PRJM-L-04 — owning W0 does not show W1's private projects.
    Rules: list_projects R7."""
    set_owner(db, S.W0, S.UG)
    PA = proj(db, S, "Alpha")
    proj(db, S, "Vault", private=True)
    result = PM.list_projects(db, workspace_id=S.W1.id, user_id=S.UG.id)
    # Then 1
    assert idset(result) == {PA.id}


def test_prjm_l_05__owner_role_in_w2_no_private(db, S):
    """PRJM-L-05 — role owner in W2 (row built before the W1 row) does not show W1's private projects.
    Rules: list_projects R7."""
    UX = make_profile(db, name="Omar Ali")
    member(db, S, UX, "owner", ws=S.W2)
    member(db, S, UX, "ground-team")
    PA = proj(db, S, "Alpha")
    proj(db, S, "Vault", private=True)
    result = PM.list_projects(db, workspace_id=S.W1.id, user_id=UX.id)
    # Then 1
    assert idset(result) == {PA.id}


def test_prjm_l_06__suspended_owner_sees_plain(db, S):
    """PRJM-L-06 — a suspended member with role owner sees only what a plain member sees.
    Rules: list_projects R6, R7."""
    UX = make_profile(db, name="Omar Ali")
    member(db, S, UX, "owner", status="suspended")
    PA = proj(db, S, "Alpha")
    proj(db, S, "Vault", private=True)
    result = PM.list_projects(db, workspace_id=S.W1.id, user_id=UX.id)
    # Then 1
    assert idset(result) == {PA.id}


def _hidden_then_visible(db, S):
    """Given of L-07, L-09, L-10, L-11: H1..H3 private ("Aa", "Ab", "Ac"), then V1 "Ba", V2 "Bb"."""
    H1 = proj(db, S, "Aa", private=True)
    H2 = proj(db, S, "Ab", private=True)
    proj(db, S, "Ac", private=True)
    V1 = proj(db, S, "Ba")
    V2 = proj(db, S, "Bb")
    return H1, H2, V1, V2


@pytest.mark.xfail(strict=True, reason="BUG-1958: private projects are filtered after paging")
def test_prjm_l_07__hidden_rows_do_not_use_page(db, S):
    """PRJM-L-07 — hidden private projects ahead of the page do not use its places.
    Rules: list_projects R7 [BUG-1958]."""
    _, _, V1, V2 = _hidden_then_visible(db, S)
    result = PM.list_projects(db, workspace_id=S.W1.id, user_id=S.UG.id, skip=0, limit=2)
    # Then 1
    assert idset(result) == {V1.id, V2.id}


@pytest.mark.xfail(strict=True, reason="BUG-1958: private projects are filtered after paging")
def test_prjm_l_08__hidden_row_not_counted_by_skip(db, S):
    """PRJM-L-08 — a hidden private project ahead of the skipped row is not counted by skip.
    Rules: list_projects R7 [BUG-1958]."""
    proj(db, S, "Aa", private=True)
    proj(db, S, "Ba")
    V2 = proj(db, S, "Bb")
    result = PM.list_projects(db, workspace_id=S.W1.id, user_id=S.UG.id, skip=1, limit=10)
    # Then 1
    assert idset(result) == {V2.id}


@pytest.mark.xfail(strict=False, reason="BUG-1958: private projects are filtered after paging (factory read has no order today)")
def test_prjm_l_09__factory_filter_hidden_rows(db, S):
    """PRJM-L-09 — with a factory filter, hidden private projects do not use the page's places.
    Rules: list_projects R1, R7 [BUG-1958]."""
    # [claude] PRJM-L-09
    _, _, V1, V2 = _hidden_then_visible(db, S)
    result = PM.list_projects(db, workspace_id=S.W1.id, user_id=S.UG.id, factory_id=S.F1.id, skip=0, limit=2)
    # Then 1
    assert idset(result) == {V1.id, V2.id}


@pytest.mark.xfail(strict=False, reason="BUG-1958: private projects are filtered after paging (status read has no order today)")
def test_prjm_l_10__status_filter_hidden_rows(db, S):
    """PRJM-L-10 — with a status filter, hidden private projects do not use the page's places.
    Rules: list_projects R2, R7 [BUG-1958]."""
    # [claude] PRJM-L-10
    _, _, V1, V2 = _hidden_then_visible(db, S)
    result = PM.list_projects(db, workspace_id=S.W1.id, user_id=S.UG.id, status="PLANNING", skip=0, limit=2)
    # Then 1
    assert idset(result) == {V1.id, V2.id}


def test_prjm_l_11__privileged_page_as_read(db, S):
    """PRJM-L-11 — a privileged caller's page is read as is, private projects in it.
    Rules: list_projects R6."""
    H1, H2, _, _ = _hidden_then_visible(db, S)
    result = PM.list_projects(db, workspace_id=S.W1.id, user_id=S.U2.id, skip=0, limit=2)
    # Then 1
    assert idset(result) == {H1.id, H2.id}


def test_prjm_l_12__factory_filter(db, S):
    """PRJM-L-12 — factory_id filters to that factory of the workspace.
    Rules: list_projects R1."""
    proj(db, S, "Zero", where="W0")
    A = proj(db, S, "Alpha")
    proj(db, S, "Beta", factory_id=S.F2.id)
    C = proj(db, S, "Gamma")
    proj(db, S, "Nine", where="W2")
    result = PM.list_projects(db, workspace_id=S.W1.id, user_id=S.U2.id, factory_id=S.F1.id)
    # Then 1
    assert idset(result) == {A.id, C.id}


@pytest.mark.xfail(strict=True, reason="BUG-1959: factory_id=0 is taken as no filter")
def test_prjm_l_13__factory_zero_returns_nothing(db, S):
    """PRJM-L-13 — factory_id 0 filters and returns nothing.
    Rules: list_projects R1 [BUG-1959]."""
    proj(db, S, "Alpha")
    proj(db, S, "Beta", factory_id=S.F2.id)
    result = PM.list_projects(db, workspace_id=S.W1.id, user_id=S.U2.id, factory_id=0)
    # Then 1
    assert result == []


@pytest.mark.xfail(strict=True, reason="BUG-1960: with a factory filter the status filter is ignored")
def test_prjm_l_14__factory_and_status_both_apply(db, S):
    """PRJM-L-14 — factory and status together apply both.
    Rules: list_projects R1a [BUG-1960]."""
    AP = proj(db, S, "Alpha")
    proj(db, S, "Beta", status=COMPLETED)
    proj(db, S, "Gamma", factory_id=S.F2.id)
    result = PM.list_projects(db, workspace_id=S.W1.id, user_id=S.U2.id, factory_id=S.F1.id, status="PLANNING")
    # Then 1
    assert idset(result) == {AP.id}


def test_prjm_l_15__factory_still_filters_with_status(db, S):
    """PRJM-L-15 — factory and status together: the factory still filters.
    Rules: list_projects R1, R1a."""
    AP = proj(db, S, "Alpha")
    proj(db, S, "Gamma", factory_id=S.F2.id)
    result = PM.list_projects(db, workspace_id=S.W1.id, user_id=S.U2.id, factory_id=S.F1.id, status="PLANNING")
    # Then 1
    assert idset(result) == {AP.id}


def test_prjm_l_16__status_filter_across_factories(db, S):
    """PRJM-L-16 — a status filter alone returns that status across factories.
    Rules: list_projects R2."""
    AP = proj(db, S, "Alpha")
    proj(db, S, "Beta", status=COMPLETED)
    BP = proj(db, S, "Gamma", factory_id=S.F2.id)
    proj(db, S, "Nine", where="W2")
    result = PM.list_projects(db, workspace_id=S.W1.id, user_id=S.U2.id, status="PLANNING")
    # Then 1
    assert idset(result) == {AP.id, BP.id}


def test_prjm_l_17__empty_status_no_filter(db, S):
    """PRJM-L-17 — an empty status means no filter.
    Rules: list_projects R2."""
    AP = proj(db, S, "Alpha")
    AC = proj(db, S, "Beta", status=COMPLETED)
    result = PM.list_projects(db, workspace_id=S.W1.id, user_id=S.U2.id, status="")
    # Then 1
    assert idset(result) == {AP.id, AC.id}


def test_prjm_l_18__non_enum_status_value_error(db, S):
    """PRJM-L-18 — a status that is not an enum value raises ValueError in the manager.
    Rules: list_projects R2 (BUG-1961 is fixed at the endpoint; the manager keeps its conversion)."""
    proj(db, S, "Alpha")
    # Then 1
    with pytest.raises(ValueError):
        PM.list_projects(db, workspace_id=S.W1.id, user_id=S.U2.id, status="planning")


@pytest.mark.xfail(strict=True, reason="BUG-1955: the unfiltered list includes soft-deleted projects")
def test_prjm_l_19__deleted_not_listed(db, S):
    """PRJM-L-19 — without filters a soft-deleted project is not listed.
    Rules: list_projects R3 [BUG-1955]."""
    A = proj(db, S, "Alpha")
    proj(db, S, "Old", deleted=True)
    result = PM.list_projects(db, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 1
    assert idset(result) == {A.id}


@pytest.mark.xfail(strict=True, reason="BUG-1955: the unfiltered list includes soft-deleted projects")
def test_prjm_l_20__deleted_takes_no_place(db, S):
    """PRJM-L-20 — without filters a soft-deleted project takes no place on the page.
    Rules: list_projects R3 [BUG-1955]."""
    proj(db, S, "Aa", deleted=True)
    proj(db, S, "Ba")
    V2 = proj(db, S, "Bb")
    result = PM.list_projects(db, workspace_id=S.W1.id, user_id=S.U2.id, skip=1, limit=10)
    # Then 1
    assert idset(result) == {V2.id}


def test_prjm_l_21__inactive_listed(db, S):
    """PRJM-L-21 — without filters an inactive project is listed.
    Rules: list_projects R3."""
    A = proj(db, S, "Alpha")
    I = proj(db, S, "Idle", is_active=False)
    result = PM.list_projects(db, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 1
    assert idset(result) == {A.id, I.id}


@pytest.mark.xfail(strict=True, reason="BUG-1956: the unfiltered list includes projects of soft-deleted factories")
def test_prjm_l_22__deleted_factory_projects_not_listed(db, S):
    """PRJM-L-22 — without filters projects of a soft-deleted factory are not listed.
    Rules: list_projects R4 [BUG-1956]."""
    A = proj(db, S, "Alpha")
    proj(db, S, "Kiln job", factory_id=S.FD.id)
    result = PM.list_projects(db, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 1
    assert idset(result) == {A.id}


def test_prjm_l_23__inactive_factory_projects_listed(db, S):
    """PRJM-L-23 — without filters projects of an inactive factory are listed.
    Rules: list_projects R4."""
    A = proj(db, S, "Alpha")
    K = proj(db, S, "Idle job", factory_id=S.FI.id)
    result = PM.list_projects(db, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 1
    assert idset(result) == {A.id, K.id}


@pytest.mark.xfail(strict=True, reason="BUG-1957: the unfiltered list is ordered by id, not by name")
def test_prjm_l_24__ordered_by_name_ci(db, S):
    """PRJM-L-24 — without filters the list is ordered by name, case-insensitive.
    Rules: list_projects R5 [BUG-1957]."""
    proj(db, S, "Zulu")
    proj(db, S, "apple")
    proj(db, S, "Banana")
    result = PM.list_projects(db, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 1
    assert names(result) == ["apple", "Banana", "Zulu"]


@pytest.mark.xfail(strict=True, reason="BUG-1957: the unfiltered list is ordered by id, not by name")
def test_prjm_l_25__case_equal_names_by_id(db, S):
    """PRJM-L-25 — names equal but for case are ordered by id.
    Rules: list_projects R5 [BUG-1957]."""
    B1 = proj(db, S, "beta")
    B2 = proj(db, S, "Beta")
    A = proj(db, S, "Alpha")
    result = PM.list_projects(db, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 1
    assert [r.id for r in result] == [A.id, B1.id, B2.id]


def test_prjm_l_26__default_limit_100(db, S):
    """PRJM-L-26 — the default limit is 100.
    Rules: list_projects R5."""
    bulk(db, S, 101, "P")
    result = PM.list_projects(db, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 1
    assert len(result) == 100


def test_prjm_l_27__limit_1000_all(db, S):
    """PRJM-L-27 — limit 1000 returns all 101.
    Rules: list_projects R5."""
    bulk(db, S, 101, "P")
    result = PM.list_projects(db, workspace_id=S.W1.id, user_id=S.U2.id, limit=1000)
    # Then 1
    assert len(result) == 101


def test_prjm_l_28__skip_100_of_101(db, S):
    """PRJM-L-28 — skip 100 of 101 leaves one.
    Rules: list_projects R5."""
    bulk(db, S, 101, "P")
    result = PM.list_projects(db, workspace_id=S.W1.id, user_id=S.U2.id, skip=100, limit=1000)
    # Then 1
    assert len(result) == 1


def test_prjm_l_29__negative_skip_data_error(db, S):
    """PRJM-L-29 — a negative skip fails in the database.
    Rules: list_projects R5."""
    proj(db, S, "Alpha")
    # Then 1
    with pytest.raises(DataError):
        with db.begin_nested():
            PM.list_projects(db, workspace_id=S.W1.id, user_id=S.U2.id, skip=-1)


def test_prjm_l_30__unflushed_edit_kept(db, S):
    """PRJM-L-30 — listing leaves the caller's unflushed edit in place.
    Rules: list_projects R7 (reads only)."""
    A = proj(db, S, "Alpha")
    proj(db, S, "Vault", private=True)
    A.description = "Edited"
    result = PM.list_projects(db, workspace_id=S.W1.id, user_id=S.UG.id)
    # Then 1
    assert idset(result) == {A.id}
    # Then 2
    assert A in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert not db.new and not db.deleted


# =========================================================================== #
# update_project
# =========================================================================== #

def update(db, S, P, user=None, **fields):
    """The When of the update cards: ProjectUpdate(**fields) on P, in W1, by U2 unless given."""
    user = user or S.U2
    return PM.update_project(db, project_id=P.id, project_data=ProjectUpdate(**fields),
                             workspace_id=S.W1.id, user_id=user.id)


def test_prjm_u_01__changes_stamps_logs(db, S):
    """PRJM-U-01 — changes the sent fields, stamps, and logs one updated event in field order.
    Rules: update_project R2, R4, R6, R9."""
    P = proj(db, S, "Roof job", budget=Decimal("1000.00"))
    result = update(db, S, P, budget=Decimal("1250.75"), description="Two coats", name="Roof refit")
    # Then 1
    assert result.id == P.id
    # Then 2
    assert result.name == "Roof refit"
    row = reread(db, Project, P.id)
    # Then 3
    assert row.name == "Roof refit"
    assert row.description == "Two coats"
    assert row.budget == Decimal("1250.75")
    # Then 4
    assert row.updated_by == S.U2.id
    assert row.updated_at == NOW
    # Then 5
    evs = events_of(db, P)
    assert len(evs) == 1
    e = evs[0]
    # Then 6
    assert e.event_type == "updated"
    assert e.description == "Updated project details"
    assert e.performed_by == S.U2.id
    assert e.workspace_id == S.W1.id
    # Then 7
    assert e.metadata_json == {"changes": [
        {"field": "name", "label": "Name", "from_value": "Roof job", "to_value": "Roof refit"},
        {"field": "description", "label": "Description", "from_value": "Main", "to_value": "Two coats"},
        {"field": "budget", "label": "Budget", "from_value": "1000.00", "to_value": "1250.75"},
    ]}


def test_prjm_u_02__status_alone_one_event(db, S):
    """PRJM-U-02 — a status change alone logs one status_updated event.
    Rules: update_project R4."""
    P = proj(db, S, "Roof job")
    result = update(db, S, P, status=IN_PROGRESS)
    # Then 1
    assert val(result.status) == "IN_PROGRESS"
    # Then 2
    evs = events_of(db, P)
    assert len(evs) == 1
    e = evs[0]
    # Then 3
    assert e.event_type == "status_updated"
    assert e.description == "Changed project status"
    assert e.performed_by == S.U2.id
    # Then 4
    assert e.metadata_json == {"changes": [
        {"field": "status", "label": "Status", "from_value": "PLANNING", "to_value": "IN_PROGRESS"},
    ]}


def test_prjm_u_03__status_and_other_two_events(db, S):
    """PRJM-U-03 — status and another field changed: two events, status first.
    Rules: update_project R4."""
    P = proj(db, S, "Roof job")
    result = update(db, S, P, name="Roof refit", status=ON_HOLD)
    # Then 1
    assert result.id == P.id
    evs = events_of(db, P)
    # Then 2
    assert [e.event_type for e in evs] == ["status_updated", "updated"]
    # Then 3
    assert evs[0].metadata_json == {"changes": [
        {"field": "status", "label": "Status", "from_value": "PLANNING", "to_value": "ON_HOLD"},
    ]}
    # Then 4
    assert evs[1].metadata_json == {"changes": [
        {"field": "name", "label": "Name", "from_value": "Roof job", "to_value": "Roof refit"},
    ]}


def test_prjm_u_04__fields_not_sent_unchanged(db, S):
    """PRJM-U-04 — fields not sent are unchanged.
    Rules: update_project R2."""
    P = proj(db, S, "Roof job", budget=Decimal("1000.00"), deadline=datetime(2026, 6, 30, 17, 0, 0))  # noqa: DTZ001
    result = update(db, S, P, description="Two coats")
    # Then 1
    assert result.id == P.id
    row = reread(db, Project, P.id)
    # Then 2
    assert row.name == "Roof job"
    assert row.budget == Decimal("1000.00")
    assert row.deadline == datetime(2026, 6, 30, 17, 0, 0)  # noqa: DTZ001
    # Then 3
    assert val(row.status) == "PLANNING"
    assert row.factory_id == S.F1.id
    assert row.visibility == "workspace"


def test_prjm_u_05__same_values_no_event(db, S):
    """PRJM-U-05 — the same values: no event.
    Rules: update_project R4."""
    P = proj(db, S, "Roof job", budget=Decimal("1000.00"))
    result = update(db, S, P, name="Roof job", description="Main", budget=Decimal("1000"))
    # Then 1
    assert result.id == P.id
    # Then 2
    assert len(events_of(db, P)) == 0
    row = reread(db, Project, P.id)
    # Then 3
    assert row.name == "Roof job"
    assert row.budget == Decimal("1000.00")


@pytest.mark.xfail(strict=True, reason="BUG-1952: update_project stamps updated_by/updated_at when nothing changes")
def test_prjm_u_06__same_values_no_stamp(db, S):
    """PRJM-U-06 — the same values do not stamp the project.
    Rules: update_project R9 [BUG-1952]."""
    P = proj(db, S, "Roof job")
    result = update(db, S, P, name="Roof job", description="Main")
    # Then 1
    assert result.id == P.id
    row = reread(db, Project, P.id)
    # Then 2
    assert row.updated_by is None
    assert row.updated_at is None


def test_prjm_u_07__empty_update_no_event(db, S):
    """PRJM-U-07 — an empty update: no event.
    Rules: update_project R4."""
    P = proj(db, S, "Roof job")
    result = update(db, S, P)
    # Then 1
    assert result.id == P.id
    # Then 2
    assert len(events_of(db, P)) == 0


@pytest.mark.xfail(strict=True, reason="BUG-1952: update_project stamps updated_by/updated_at when nothing changes")
def test_prjm_u_08__empty_update_no_stamp(db, S):
    """PRJM-U-08 — an empty update does not stamp the project.
    Rules: update_project R9 [BUG-1952]."""
    P = proj(db, S, "Roof job")
    result = update(db, S, P)
    # Then 1
    assert result.id == P.id
    row = reread(db, Project, P.id)
    # Then 2
    assert row.updated_by is None
    assert row.updated_at is None


def test_prjm_u_09__deadline_moved_by_hours(db, S):
    """PRJM-U-09 — a deadline moved by hours in one day is logged with the same date twice.
    Rules: update_project R4; _collect_field_changes R2."""
    P = proj(db, S, "Roof job", deadline=datetime(2026, 3, 1, 9, 0, 0))  # noqa: DTZ001
    result = update(db, S, P, deadline=datetime(2026, 3, 1, 17, 0, 0))  # noqa: DTZ001
    # Then 1
    assert result.id == P.id
    # Then 2
    assert reread(db, Project, P.id).deadline == datetime(2026, 3, 1, 17, 0, 0)  # noqa: DTZ001
    (e,) = events_of(db, P)
    # Then 3
    assert e.event_type == "updated"
    # Then 4
    assert e.metadata_json == {"changes": [
        {"field": "deadline", "label": "Deadline", "from_value": "2026-03-01", "to_value": "2026-03-01"},
    ]}


def test_prjm_u_10__start_end_set_and_logged(db, S):
    """PRJM-U-10 — start and end dates are set and logged, end before start accepted.
    Rules: update_project R3, R4."""
    P = proj(db, S, "Roof job")
    result = update(db, S, P, start_date=datetime(2026, 5, 10, 8, 0, 0), end_date=datetime(2026, 5, 1, 8, 0, 0))  # noqa: DTZ001
    # Then 1
    assert result.id == P.id
    row = reread(db, Project, P.id)
    # Then 2
    assert row.start_date == datetime(2026, 5, 10, 8, 0, 0)  # noqa: DTZ001
    assert row.end_date == datetime(2026, 5, 1, 8, 0, 0)  # noqa: DTZ001
    (e,) = events_of(db, P)
    # Then 3
    assert e.metadata_json == {"changes": [
        {"field": "start_date", "label": "Start date", "from_value": None, "to_value": "2026-05-10"},
        {"field": "end_date", "label": "End date", "from_value": None, "to_value": "2026-05-01"},
    ]}


def test_prjm_u_11__cancelled_to_in_progress(db, S):
    """PRJM-U-11 — any status may follow any status: CANCELLED to IN_PROGRESS.
    Rules: update_project R3."""
    P = proj(db, S, "Roof job", status=CANCELLED)
    result = update(db, S, P, status=IN_PROGRESS)
    # Then 1
    assert val(result.status) == "IN_PROGRESS"
    # Then 2
    assert val(reread(db, Project, P.id).status) == "IN_PROGRESS"
    (e,) = events_of(db, P)
    # Then 3
    assert e.metadata_json == {"changes": [
        {"field": "status", "label": "Status", "from_value": "CANCELLED", "to_value": "IN_PROGRESS"},
    ]}


def test_prjm_u_12__no_factory_or_visibility_field():
    """PRJM-U-12 — ProjectUpdate has no factory or visibility field.
    Rules: update_project R5."""
    result = set(ProjectUpdate.model_fields)
    # Then 1
    assert "factory_id" not in result
    # Then 2
    assert "visibility" not in result


def test_prjm_u_13__plain_member_edits(db, S):
    """PRJM-U-13 — a plain member may edit a workspace-visible project.
    Rules: update_project R1."""
    P = proj(db, S, "Roof job")
    result = update(db, S, P, user=S.UG, description="Two coats")
    # Then 1
    assert result.description == "Two coats"
    # Then 2
    assert reread(db, Project, P.id).updated_by == S.UG.id
    (e,) = events_of(db, P)
    # Then 3
    assert e.performed_by == S.UG.id


def test_prjm_u_14__deleted_project_400(db, S):
    """PRJM-U-14 — a soft-deleted project is 400, nothing written.
    Rules: update_project R1."""
    P = proj(db, S, "Gone", deleted=True)
    before_p = snap(db, P)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        update(db, S, P, name="Back")
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update deleted project"
    # Then 4
    assert P not in db.dirty
    # Then 5
    assert unchanged(db, P, before_p)
    # Then 6
    assert counts(db) == before


def test_prjm_u_15__caller_without_access_403(db, S):
    """PRJM-U-15 — a caller who may not open the private project is 403.
    Rules: update_project R1."""
    P = proj(db, S, "Secret", private=True)
    before_p = snap(db, P)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        update(db, S, P, user=S.UG, name="Mine")
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == "You do not have access to this project"
    # Then 4
    assert unchanged(db, P, before_p)
    # Then 5
    assert counts(db) == before


def test_prjm_u_16__other_workspace_404(db, S):
    """PRJM-U-16 — another workspace's project is 404.
    Rules: update_project R1."""
    P9 = proj(db, S, "Nine", where="W2")
    before_p9 = snap(db, P9)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        update(db, S, P9, name="Mine")
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project with ID {P9.id} not found"
    # Then 4
    assert unchanged(db, P9, before_p9)
    # Then 5
    assert counts(db) == before


@pytest.mark.xfail(strict=True, reason="BUG-1953: an explicit null cannot clear budget, deadline, start or end date")
@pytest.mark.parametrize(("field", "old"), [
    pytest.param("budget", Decimal("1000.00"), id="PRJM-U-17"),
    pytest.param("deadline", datetime(2026, 6, 30, 17, 0, 0), id="PRJM-U-18"),  # noqa: DTZ001
    pytest.param("start_date", datetime(2026, 5, 1, 8, 0, 0), id="PRJM-U-19"),  # noqa: DTZ001
    pytest.param("end_date", datetime(2026, 5, 31, 17, 0, 0), id="PRJM-U-20"),  # noqa: DTZ001
])
def test_prjm_u_17_20__explicit_null_clears(db, S, field, old):
    """PRJM-U-17 … U-20 — an explicit null clears the budget, deadline, start date, end date.
    Rules: update_project R2a [BUG-1953]."""
    P = proj(db, S, "Roof job", **{field: old})
    result = update(db, S, P, **{field: None})
    # Then 1
    assert result.id == P.id
    # Then 2
    assert getattr(reread(db, Project, P.id), field) is None


@pytest.mark.xfail(strict=True, reason="BUG-1953: ProjectUpdate accepts null for name, description, priority, status")
@pytest.mark.parametrize("field", [
    pytest.param("name", id="PRJM-U-21"),
    pytest.param("description", id="PRJM-U-22"),
    pytest.param("priority", id="PRJM-U-23"),
    pytest.param("status", id="PRJM-U-24"),
])
def test_prjm_u_21_24__null_refused(field):
    """PRJM-U-21 … U-24 — null for name, description, priority or status is refused by ProjectUpdate.
    Rules: update_project R2a [BUG-1953]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        ProjectUpdate(**{field: None})
    # Then 2
    assert field in str(exc.value)


def test_prjm_u_25__inner_spaces_and_case_kept(db, S):
    """PRJM-U-25 — the name's inner spaces and case are kept.
    Rules: update_project R7 (HR-1)."""
    P = proj(db, S, "Roof job")
    result = update(db, S, P, name="Roof  JOB 2")
    # Then 1
    assert result.id == P.id
    # Then 2
    assert reread(db, Project, P.id).name == "Roof  JOB 2"


@pytest.mark.xfail(strict=True, reason="BUG-1951: project names are stored untrimmed and blank names are accepted")
def test_prjm_u_26__sent_name_trimmed(db, S):
    """PRJM-U-26 — a sent name is stored trimmed.
    Rules: update_project R7 [BUG-1951]."""
    P = proj(db, S, "Roof job")
    result = update(db, S, P, name="  Roof refit ")
    # Then 1
    assert result.id == P.id
    # Then 2
    assert reread(db, Project, P.id).name == "Roof refit"


@pytest.mark.xfail(strict=True, reason="BUG-1951: project names are stored untrimmed and blank names are accepted")
def test_prjm_u_27__spaces_name_refused():
    """PRJM-U-27 — a name of only spaces is refused by ProjectUpdate.
    Rules: update_project R7 [BUG-1951]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        ProjectUpdate(name="  ")
    # Then 2
    assert "name" in str(exc.value)


def test_prjm_u_28__budget_zero_on_update(db, S):
    """PRJM-U-28 — a budget of 0 is accepted on update.
    Rules: update_project R8."""
    P = proj(db, S, "Roof job", budget=Decimal("1000.00"))
    result = update(db, S, P, budget=Decimal("0"))
    # Then 1
    assert result.id == P.id
    # Then 2
    assert reread(db, Project, P.id).budget == Decimal("0.00")


@pytest.mark.xfail(strict=True, reason="BUG-1962: a negative budget is accepted")
def test_prjm_u_29__negative_budget_refused():
    """PRJM-U-29 — a negative budget is refused by ProjectUpdate.
    Rules: update_project R8 [BUG-1962]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        ProjectUpdate(budget=Decimal("-0.01"))
    # Then 2
    assert "budget" in str(exc.value)


@pytest.mark.xfail(strict=True, reason="BUG-1963: a budget with more than 2 decimals or 13 integer digits is accepted")
@pytest.mark.parametrize("budget", [
    pytest.param(Decimal("1000.005"), id="PRJM-U-30"),
    pytest.param(Decimal("10000000000000.00"), id="PRJM-U-31"),
])
def test_prjm_u_30_31__budget_precision_refused(budget):
    """PRJM-U-30, U-31 — a budget with three decimals, or 14 integer digits, is refused by ProjectUpdate.
    Rules: update_project R8 [BUG-1963]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        ProjectUpdate(budget=budget)
    # Then 2
    assert "budget" in str(exc.value)


@pytest.mark.xfail(strict=True, reason="BUG-1963: the budget change entry records the typed form, not the stored one")
def test_prjm_u_32__budget_logged_stored_form(db, S):
    """PRJM-U-32 — a one-decimal budget is logged in its stored two-decimal form.
    Rules: update_project R8 [BUG-1963]."""
    P = proj(db, S, "Roof job", budget=Decimal("1000.00"))
    result = update(db, S, P, budget=Decimal("1000.5"))
    # Then 1
    assert result.id == P.id
    # Then 2
    assert reread(db, Project, P.id).budget == Decimal("1000.50")
    (e,) = events_of(db, P)
    # Then 3
    assert e.metadata_json == {"changes": [
        {"field": "budget", "label": "Budget", "from_value": "1000.00", "to_value": "1000.50"},
    ]}


def test_prjm_u_33__does_not_commit(db, S):
    """PRJM-U-33 — update_project does not commit.
    Rules: update_project R6."""
    P = proj(db, S, "Roof job")
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        update(db, S, P, name="Roof refit")
        sp.rollback()
    # Then 1
    assert cm.call_count == 0
    # Then 2
    assert reread(db, Project, P.id).name == "Roof job"
    # Then 3
    assert len(events_of(db, P)) == 0


def test_prjm_u_34__one_decimal_budget_stored_two(db, S):
    """PRJM-U-34 — a one-decimal budget is stored with two decimals.
    Rules: update_project R8 (column keeps 2 decimals; HR-15)."""
    P = proj(db, S, "Roof job", budget=Decimal("1000.00"))
    result = update(db, S, P, budget=Decimal("1000.5"))
    # Then 1
    assert result.id == P.id
    # Then 2
    assert reread(db, Project, P.id).budget == Decimal("1000.50")
    # Then 3
    assert len(events_of(db, P)) == 1
