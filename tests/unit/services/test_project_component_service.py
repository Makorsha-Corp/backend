"""Unit tests for app/services/project_component_service.py.

Implements tests/unit/services/project_component_service.cases.md (revision 4),
one test per card, in card order. Real Postgres session (`db` fixture): a
`commit()` only releases a savepoint, so the service's commits are safe and the
fixture's outer rollback discards everything. Nothing is mocked except the
spies, failing commit and failing refresh of the Conventions.

Every test builds the Standing rows (autouse fixture `S`, attributes named as in
the cards: `S.W1`, `S.UG`, `S.PA` ...). Given rows are built by the helpers below
(`comp`, `member`, `pmem`, `proj`, `wo`, `line`, `task`, `act`, `ledger`, `misc`,
`att`, `pev`, `bulk`), one flush per row; components carry explicit ids XID(k).
`# [claude] <ID>` sits above each test; `# Then N` marks the checks of the
card's Then line N.
"""

# ruff: noqa: SIM117, DTZ001  (Conventions prescribe the nested `with` and naive datetimes)
import os
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import event, func, insert, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import DataError

from app.core.exceptions import ValidationError
from app.models.attachment import Attachment
from app.models.enums import ProjectStatusEnum
from app.models.factory import Factory
from app.models.item import Item
from app.models.miscellaneous_project_cost import MiscellaneousProjectCost
from app.models.project import Project
from app.models.project_component import ProjectComponent
from app.models.project_component_activity_event import ProjectComponentActivityEvent
from app.models.project_component_attachment import ProjectComponentAttachment
from app.models.project_component_item import ProjectComponentItem
from app.models.project_component_item_ledger import ProjectComponentItemLedger
from app.models.project_component_task import ProjectComponentTask
from app.models.project_event import ProjectEvent
from app.models.project_member import ProjectMember
from app.models.work_order import WorkOrder
from app.models.work_order_type import WorkOrderType
from app.models.workspace_member import WorkspaceMember
from app.schemas.project_component import ProjectComponentCreate, ProjectComponentUpdate
from app.services.project_component_service import project_component_service
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

svc = project_component_service
MISSING = 999999999
T0 = datetime(2025, 12, 1, 8, 0, 0)
T1 = datetime(2026, 1, 1, 9, 0, 0)
NOACCESS = "You do not have access to this project"
NOCOMP = "Project component not found"


def NOPROJ(x):
    return f"Project with ID {x} not found"


# Convention "XID(k)": an explicit row id no sequence gives
def XID(k):
    return 800_000_000 + (os.getpid() % 1_000_000) * 10 + k


def xfail(bug, strict=True):
    return pytest.mark.xfail(strict=strict, reason=bug)


def idset(rows):
    return {c.id for c in rows}


def names(rows):
    return [c.name for c in rows]


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
    return _add(
        db, WorkspaceMember(workspace_id=ws.id, user_id=u.id, role=role, status=status)
    )


@pytest.fixture(autouse=True)
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
    s.F0 = _add(
        db, Factory(workspace_id=s.W0.id, name="Factory Zero", abbreviation="F0")
    )
    s.F1 = _add(
        db, Factory(workspace_id=s.W1.id, name="Factory One", abbreviation="F1")
    )
    s.F9 = _add(
        db, Factory(workspace_id=s.W2.id, name="Factory Nine", abbreviation="F9")
    )

    def _p(ws, f, name, vis):
        return _add(
            db,
            Project(
                workspace_id=ws.id,
                factory_id=f.id,
                name=name,
                description="Main",
                created_by=s.U1.id,
                visibility=vis,
            ),
        )

    s.P0 = _p(s.W0, s.F0, "Zero", "workspace")
    s.PA = _p(s.W1, s.F1, "Alpha", "workspace")
    s.PB = _p(s.W1, s.F1, "Bravo", "invited_only")
    s.P9 = _p(s.W2, s.F9, "Nine", "workspace")
    return s


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #


def comp(db, p, name, k, **but):
    fields = {
        "id": XID(k),
        "workspace_id": p.workspace_id,
        "project_id": p.id,
        "name": name,
    }
    fields.update(but)
    return _add(db, ProjectComponent(**fields))


# Section convention "CR" (update_component: description "Top", budget 100, PLANNING)
def cr_upd(db, S, **but):
    fields = {"description": "Top", "budget": 100, "status": ProjectStatusEnum.PLANNING}
    fields.update(but)
    return comp(db, S.PA, "Roof", 12, **fields)


# Section convention "CR" (delete_component)
def cr_del(db, S):
    return comp(db, S.PA, "Roof", 12)


def um(db):
    return make_profile(db, name="Omar Ali")


def pmem(db, S, p, u):
    return _add(
        db,
        ProjectMember(
            workspace_id=p.workspace_id,
            project_id=p.id,
            user_id=u.id,
            assigned_by=S.U1.id,
        ),
    )


def set_owner(db, ws, u):
    ws.owner_user_id = u.id
    db.flush()


def proj(db, S, name, private=False, deleted=False, **but):
    fields = {
        "workspace_id": S.W1.id,
        "factory_id": S.F1.id,
        "name": name,
        "description": "Main",
        "created_by": S.U1.id,
        "visibility": "workspace",
    }
    if private:
        fields["visibility"] = "invited_only"
    if deleted:
        fields.update(is_deleted=True, deleted_at=T0, deleted_by=S.U1.id)
    fields.update(but)
    return _add(db, Project(**fields))


def bulk(db, n, p):
    db.execute(
        insert(ProjectComponent),
        [
            {"workspace_id": p.workspace_id, "project_id": p.id, "name": f"C{i:05d}"}
            for i in range(n)
        ],
    )
    db.expire_all()


def wt1(db, S):
    return _add(db, WorkOrderType(workspace_id=S.W1.id, name="Repair"))


def wo(db, S, c, number, wt, deleted=False):
    fields = {
        "workspace_id": S.W1.id,
        "work_order_number": number,
        "title": "Fix press",
        "factory_id": S.F1.id,
        "work_order_type_id": wt.id,
        "created_by": S.U1.id,
        "project_component_id": c.id,
    }
    if deleted:
        fields.update(
            is_deleted=True, is_active=False, deleted_at=T0, deleted_by=S.U1.id
        )
    return _add(db, WorkOrder(**fields))


def i1(db, S):
    return _add(
        db, Item(workspace_id=S.W1.id, name="Bolt", name_normalized="bolt", unit="pcs")
    )


def line(db, S, c, item):
    return _add(
        db,
        ProjectComponentItem(
            workspace_id=S.W1.id, project_component_id=c.id, item_id=item.id, qty=1
        ),
    )


def task(db, S, c, name, note=False, **but):
    fields = {
        "workspace_id": S.W1.id,
        "project_component_id": c.id,
        "name": name,
        "description": "Do it",
    }
    if note:
        fields["is_note"] = True
    fields.update(but)
    return _add(db, ProjectComponentTask(**fields))


def act(db, S, c, t):
    return _add(
        db,
        ProjectComponentActivityEvent(
            workspace_id=S.W1.id,
            project_component_id=c.id,
            event_type=t,
            description="Logged",
            created_at=T1,
        ),
    )


def ledger(db, S, c, item):
    return _add(
        db,
        ProjectComponentItemLedger(
            workspace_id=S.W1.id,
            project_component_id=c.id,
            item_id=item.id,
            transaction_type="consume",
            quantity=1,
            unit_cost=5,
            total_cost=5,
            qty_before=1,
            qty_after=0,
            source_type="manual",
            performed_by=S.U1.id,
        ),
    )


def misc(db, S, c):
    return _add(
        db,
        MiscellaneousProjectCost(
            workspace_id=S.W1.id,
            name="Crane hire",
            amount=50,
            project_id=S.PA.id,
            project_component_id=c.id,
        ),
    )


def at0(db, S):
    return _add(
        db,
        Attachment(
            workspace_id=S.W1.id,
            file_name="file.png",
            mime_type="image/png",
            file_size=100,
            uploaded_by=S.U1.id,
            upload_status="ready",
        ),
    )


def att(db, S, c, a):
    return _add(
        db,
        ProjectComponentAttachment(
            workspace_id=S.W1.id,
            project_component_id=c.id,
            attachment_id=a.id,
            attached_by=S.U1.id,
        ),
    )


def pev(db, S, p):
    return _add(
        db,
        ProjectEvent(
            workspace_id=p.workspace_id,
            project_id=p.id,
            event_type="project_updated",
            description="seed",
            performed_by=S.U1.id,
            created_at=T1,
            metadata_json=None,
        ),
    )


# Convention "commit point"
def commit_point(db):
    db.commit()


# Convention "extra row X" (after the commit point); returns X_ID
def extra_x(db, S):
    x = _add(
        db, ProjectComponent(workspace_id=S.W2.id, project_id=S.P9.id, name="Extra")
    )
    return x.id


# Convention "pending Q" (after the commit point), not flushed
def pending_q(db, S):
    q = ProjectComponent(workspace_id=S.W2.id, project_id=S.P9.id, name="Pending")
    db.add(q)
    return q


# Convention "edit E(C)"
def edit_e(c):
    c.name = "Edited"


# --------------------------------------------------------------------------- #
# Named checks
# --------------------------------------------------------------------------- #


def _columns(model):
    return [c.key for c in sa_inspect(model).mapper.column_attrs]


def snap(db, row):
    """Snapshot for unchanged(X), taken at the commit point."""
    db.refresh(row)
    return {k: getattr(row, k) for k in _columns(type(row))}


def unchanged(db, model, before):
    db.expire_all()
    fresh = db.get(model, before["id"])
    return (
        fresh is not None and {k: getattr(fresh, k) for k in _columns(model)} == before
    )


def reread(db, model, row_id):
    db.expire_all()
    return db.get(model, row_id)


def counts(db):
    """'nothing written': row counts of project_components and project_events."""
    return tuple(
        db.scalar(select(func.count()).select_from(m))
        for m in (ProjectComponent, ProjectEvent)
    )


def x_count(db, x_id):
    return db.scalar(
        select(func.count())
        .select_from(ProjectComponent)
        .where(ProjectComponent.id == x_id)
    )


def evs(db, p_id, t):
    db.expire_all()
    return (
        db.execute(
            select(ProjectEvent)
            .where(ProjectEvent.project_id == p_id, ProjectEvent.event_type == t)
            .order_by(ProjectEvent.id)
        )
        .scalars()
        .all()
    )


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
    with (
        patch.object(db, "refresh", side_effect=RuntimeError("boom")),
        patch.object(db, "rollback", wraps=db.rollback) as rb,
    ):
        yield rb


# Convention "recorder"
@contextmanager
def recorder(db):
    stmts = []

    def rec(conn, cursor, statement, params, context, executemany):
        stmts.append(statement)

    conn = db.connection()
    event.listen(conn, "before_cursor_execute", rec)
    try:
        yield stmts
    finally:
        event.remove(conn, "before_cursor_execute", rec)


# =========================================================================== #
# get_components — workspace-wide
# =========================================================================== #


# [claude] PCS-L-01
def test_pcs_l_01__privileged_sees_all_of_w1(db, S):
    """PCS-L-01 — a privileged member sees every component of W1, private projects included.
    Rules: get_components R3, R7."""
    comp(db, S.P0, "Zero part", 11)
    ca = comp(db, S.PA, "Arm", 12)
    cb = comp(db, S.PB, "Base", 13)
    comp(db, S.P9, "Nine part", 14)
    commit_point(db)
    result = svc.get_components(db, workspace_id=S.W1.id, user_id=S.U2.id, limit=1000)
    # Then 1
    assert all(isinstance(c, ProjectComponent) for c in result)
    # Then 2
    assert idset(result) == {ca.id, cb.id}


# [claude] PCS-L-02
def test_pcs_l_02__plain_member_not_private(db, S):
    """PCS-L-02 — a plain member does not see a private project's components.
    Rules: get_components R3."""
    comp(db, S.P0, "Zero part", 11)
    ca = comp(db, S.PA, "Arm", 12)
    comp(db, S.PB, "Base", 13)
    comp(db, S.P9, "Nine part", 14)
    commit_point(db)
    result = svc.get_components(db, workspace_id=S.W1.id, user_id=S.UG.id, limit=1000)
    # Then 1
    assert idset(result) == {ca.id}


# [claude] PCS-L-03
def test_pcs_l_03__workspace_owner_sees_private(db, S):
    """PCS-L-03 — the workspace owner (owner_user_id) sees the private components.
    Rules: get_components R3."""
    set_owner(db, S.W1, S.UG)
    ca = comp(db, S.PA, "Arm", 12)
    cb = comp(db, S.PB, "Base", 13)
    commit_point(db)
    result = svc.get_components(db, workspace_id=S.W1.id, user_id=S.UG.id, limit=1000)
    # Then 1
    assert idset(result) == {ca.id, cb.id}


# [claude] PCS-L-04
def test_pcs_l_04__active_gtm_sees_private(db, S):
    """PCS-L-04 — an active ground-team-manager sees the private components.
    Rules: get_components R3."""
    u = um(db)
    member(db, S, u, "ground-team-manager")
    ca = comp(db, S.PA, "Arm", 12)
    cb = comp(db, S.PB, "Base", 13)
    commit_point(db)
    result = svc.get_components(db, workspace_id=S.W1.id, user_id=u.id, limit=1000)
    # Then 1
    assert idset(result) == {ca.id, cb.id}


# [claude] PCS-L-05
def test_pcs_l_05__creator_sees_private(db, S):
    """PCS-L-05 — the private project's creator sees its components.
    Rules: get_components R3."""
    ca = comp(db, S.PA, "Arm", 12)
    cb = comp(db, S.PB, "Base", 13)
    commit_point(db)
    result = svc.get_components(db, workspace_id=S.W1.id, user_id=S.U1.id, limit=1000)
    # Then 1
    assert idset(result) == {ca.id, cb.id}


# [claude] PCS-L-06
def test_pcs_l_06__project_member_sees_private(db, S):
    """PCS-L-06 — a project member sees the private project's components.
    Rules: get_components R3."""
    pmem(db, S, S.PB, S.UG)
    ca = comp(db, S.PA, "Arm", 12)
    cb = comp(db, S.PB, "Base", 13)
    commit_point(db)
    result = svc.get_components(db, workspace_id=S.W1.id, user_id=S.UG.id, limit=1000)
    # Then 1
    assert idset(result) == {ca.id, cb.id}


# [claude] PCS-L-07
def test_pcs_l_07__later_membership_does_not_open_earlier(db, S):
    """PCS-L-07 — membership of a later private project does not open an earlier one.
    Rules: get_components R3."""
    pc = proj(db, S, "Charlie", private=True)
    pmem(db, S, pc, S.UG)
    ca = comp(db, S.PA, "Arm", 12)
    comp(db, S.PB, "Base", 13)
    cc = comp(db, pc, "Cap", 14)
    commit_point(db)
    result = svc.get_components(db, workspace_id=S.W1.id, user_id=S.UG.id, limit=1000)
    # Then 1
    assert idset(result) == {ca.id, cc.id}


# [claude] PCS-L-08
def test_pcs_l_08__earlier_membership_does_not_open_later(db, S):
    """PCS-L-08 — membership of an earlier private project does not open a later one.
    Rules: get_components R3."""
    pc = proj(db, S, "Charlie", private=True)
    pmem(db, S, S.PB, S.UG)
    ca = comp(db, S.PA, "Arm", 12)
    cb = comp(db, S.PB, "Base", 13)
    comp(db, pc, "Cap", 14)
    commit_point(db)
    result = svc.get_components(db, workspace_id=S.W1.id, user_id=S.UG.id, limit=1000)
    # Then 1
    assert idset(result) == {ca.id, cb.id}


# [claude] PCS-L-09
def test_pcs_l_09__owning_w0_opens_nothing(db, S):
    """PCS-L-09 — owning W0 opens nothing private in W1.
    Rules: get_components R3."""
    set_owner(db, S.W0, S.UG)
    ca = comp(db, S.PA, "Arm", 12)
    comp(db, S.PB, "Base", 13)
    commit_point(db)
    result = svc.get_components(db, workspace_id=S.W1.id, user_id=S.UG.id, limit=1000)
    # Then 1
    assert idset(result) == {ca.id}


# [claude] PCS-L-10
def test_pcs_l_10__owning_w2_opens_nothing(db, S):
    """PCS-L-10 — owning W2 opens nothing private in W1.
    Rules: get_components R3."""
    set_owner(db, S.W2, S.UG)
    ca = comp(db, S.PA, "Arm", 12)
    comp(db, S.PB, "Base", 13)
    commit_point(db)
    result = svc.get_components(db, workspace_id=S.W1.id, user_id=S.UG.id, limit=1000)
    # Then 1
    assert idset(result) == {ca.id}


# [claude] PCS-L-11
def test_pcs_l_11__owner_role_in_w0_opens_nothing(db, S):
    """PCS-L-11 — the owner role in W0 opens nothing private in W1.
    Rules: get_components R3."""
    member(db, S, S.UG, "owner", ws=S.W0)
    ca = comp(db, S.PA, "Arm", 12)
    comp(db, S.PB, "Base", 13)
    commit_point(db)
    result = svc.get_components(db, workspace_id=S.W1.id, user_id=S.UG.id, limit=1000)
    # Then 1
    assert idset(result) == {ca.id}


# [claude] PCS-L-12
def test_pcs_l_12__gtm_in_w2_opens_nothing(db, S):
    """PCS-L-12 — ground-team-manager in W2 opens nothing private in W1.
    Rules: get_components R3."""
    member(db, S, S.UG, "ground-team-manager", ws=S.W2)
    ca = comp(db, S.PA, "Arm", 12)
    comp(db, S.PB, "Base", 13)
    commit_point(db)
    result = svc.get_components(db, workspace_id=S.W1.id, user_id=S.UG.id, limit=1000)
    # Then 1
    assert idset(result) == {ca.id}


# [claude] PCS-L-13
def test_pcs_l_13__member_row_under_w2_does_not_open(db, S):
    """PCS-L-13 — a project-member row filed under W2 does not open the W1 project.
    Rules: get_components R3."""
    _add(
        db,
        ProjectMember(
            workspace_id=S.W2.id,
            project_id=S.PB.id,
            user_id=S.UG.id,
            assigned_by=S.U1.id,
        ),
    )
    ca = comp(db, S.PA, "Arm", 12)
    comp(db, S.PB, "Base", 13)
    commit_point(db)
    result = svc.get_components(db, workspace_id=S.W1.id, user_id=S.UG.id, limit=1000)
    # Then 1
    assert idset(result) == {ca.id}


# [claude] PCS-L-14
def test_pcs_l_14__no_creator_private_not_opened(db, S):
    """PCS-L-14 — a private project with no creator is not opened by another project's creator.
    Rules: get_components R3."""
    pn = proj(db, S, "November", private=True, created_by=None)
    ca = comp(db, S.PA, "Arm", 12)
    cb = comp(db, S.PB, "Base", 13)
    comp(db, pn, "Nut", 14)
    commit_point(db)
    result = svc.get_components(db, workspace_id=S.W1.id, user_id=S.U1.id, limit=1000)
    # Then 1
    assert idset(result) == {ca.id, cb.id}


# [claude] PCS-L-15
def test_pcs_l_15__inactive_gtm_not_privileged(db, S):
    """PCS-L-15 — an inactive ground-team-manager is not privileged (pass-through).
    Rules: get_components R3."""
    u = um(db)
    member(db, S, u, "ground-team-manager", status="inactive")
    ca = comp(db, S.PA, "Arm", 12)
    comp(db, S.PB, "Base", 13)
    commit_point(db)
    result = svc.get_components(db, workspace_id=S.W1.id, user_id=u.id, limit=1000)
    # Then 1
    assert idset(result) == {ca.id}


# [claude] PCS-L-16
def test_pcs_l_16__role_manager_not_privileged(db, S):
    """PCS-L-16 — role "manager" is not privileged (pass-through).
    Rules: get_components R3."""
    u = um(db)
    member(db, S, u, "manager")
    ca = comp(db, S.PA, "Arm", 12)
    comp(db, S.PB, "Base", 13)
    commit_point(db)
    result = svc.get_components(db, workspace_id=S.W1.id, user_id=u.id, limit=1000)
    # Then 1
    assert idset(result) == {ca.id}


# [claude] PCS-L-17
def test_pcs_l_17__w1_component_of_w2_project_left_out(db, S):
    """PCS-L-17 — a W1 component whose project is in W2 is left out (HR-16).
    Rules: get_components R3."""
    ca = comp(db, S.PA, "Arm", 12)
    cb = comp(db, S.PB, "Base", 13)
    comp(db, S.P9, "Stray", 14, workspace_id=S.W1.id)
    commit_point(db)
    result = svc.get_components(db, workspace_id=S.W1.id, user_id=S.U2.id, limit=1000)
    # Then 1
    assert idset(result) == {ca.id, cb.id}


# [claude] PCS-L-18
def test_pcs_l_18__w1_component_of_w0_project_left_out(db, S):
    """PCS-L-18 — a W1 component whose project is in W0 is left out (HR-16).
    Rules: get_components R3."""
    comp(db, S.P0, "Stray", 11, workspace_id=S.W1.id)
    ca = comp(db, S.PA, "Arm", 12)
    cb = comp(db, S.PB, "Base", 13)
    commit_point(db)
    result = svc.get_components(db, workspace_id=S.W1.id, user_id=S.U2.id, limit=1000)
    # Then 1
    assert idset(result) == {ca.id, cb.id}


# [claude] PCS-L-19
@xfail("BUG-1278")
def test_pcs_l_19__deleted_project_components_left_out(db, S):
    """PCS-L-19 — components of a soft-deleted project are left out.
    Rules: get_components R4 [BUG-1278]."""
    pd = proj(db, S, "Delta", deleted=True)
    ca = comp(db, S.PA, "Arm", 12)
    comp(db, pd, "Door", 13)
    commit_point(db)
    result = svc.get_components(db, workspace_id=S.W1.id, user_id=S.U2.id, limit=1000)
    # Then 1
    assert idset(result) == {ca.id}


# [claude] PCS-L-20
@xfail("BUG-2277")
def test_pcs_l_20__hidden_rows_do_not_empty_page(db, S):
    """PCS-L-20 — hidden components ahead of the page do not empty it.
    Rules: get_components R5 [BUG-2277]."""
    comp(db, S.PB, "Aa", 11)
    comp(db, S.PB, "Ab", 12)
    comp(db, S.PB, "Ac", 13)
    v1 = comp(db, S.PA, "Ba", 14)
    v2 = comp(db, S.PA, "Bb", 15)
    commit_point(db)
    result = svc.get_components(
        db, workspace_id=S.W1.id, user_id=S.UG.id, skip=0, limit=2
    )
    # Then 1
    assert idset(result) == {v1.id, v2.id}


# [claude] PCS-L-21
@xfail("BUG-2277")
def test_pcs_l_21__hidden_row_not_skipped(db, S):
    """PCS-L-21 — a hidden component does not take the place of the skipped one.
    Rules: get_components R5 [BUG-2277]."""
    comp(db, S.PB, "Aa", 11)
    comp(db, S.PA, "Ba", 12)
    v2 = comp(db, S.PA, "Bb", 13)
    commit_point(db)
    result = svc.get_components(
        db, workspace_id=S.W1.id, user_id=S.UG.id, skip=1, limit=1000
    )
    # Then 1
    assert idset(result) == {v2.id}


# [claude] PCS-L-22
@xfail("BUG-1278")
def test_pcs_l_22__deleted_project_takes_no_place(db, S):
    """PCS-L-22 — a deleted project's components take no place on the page.
    Rules: get_components R4, R5 [BUG-1278]."""
    pd = proj(db, S, "Delta", deleted=True)
    comp(db, pd, "Aa", 11)
    v1 = comp(db, S.PA, "Ba", 12)
    v2 = comp(db, S.PA, "Bb", 13)
    commit_point(db)
    result = svc.get_components(
        db, workspace_id=S.W1.id, user_id=S.U2.id, skip=0, limit=2
    )
    # Then 1
    assert idset(result) == {v1.id, v2.id}


# [claude] PCS-L-23
@xfail("BUG-2277")
def test_pcs_l_23__statements_do_not_grow(db, S):
    """PCS-L-23 — the number of statements does not grow with the components.
    Rules: get_components R5 [BUG-2277]."""
    comp(db, S.PB, "Aa", 11)
    comp(db, S.PB, "Ab", 12)
    comp(db, S.PA, "Ba", 13)
    comp(db, S.PA, "Bb", 14)
    comp(db, S.PA, "Bc", 15)
    w1_id, ug_id = S.W1.id, S.UG.id
    commit_point(db)
    with recorder(db) as stmts:
        result = svc.get_components(db, workspace_id=w1_id, user_id=ug_id, limit=1000)
    # Then 1
    assert len(result) == 3
    # Then 2
    assert len(stmts) <= 3


# [claude] PCS-L-24
def test_pcs_l_24__default_page_is_100(db, S):
    """PCS-L-24 — the default page is 100.
    Rules: get_components R6."""
    bulk(db, 101, S.PA)
    commit_point(db)
    result = svc.get_components(db, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 1
    assert len(result) == 100


# [claude] PCS-L-25
@xfail("BUG-2279")
def test_pcs_l_25__ordered_by_name_case_insensitive(db, S):
    """PCS-L-25 — the list is ordered by name, case-insensitive.
    Rules: get_components R6 [BUG-2279]."""
    comp(db, S.PA, "Zulu", 11)
    comp(db, S.PA, "apple", 12)
    comp(db, S.PB, "Banana", 13)
    commit_point(db)
    result = svc.get_components(db, workspace_id=S.W1.id, user_id=S.U2.id, limit=1000)
    # Then 1
    assert names(result) == ["apple", "Banana", "Zulu"]


# [claude] PCS-L-26
@xfail("BUG-2279")
def test_pcs_l_26__order_before_paging(db, S):
    """PCS-L-26 — the order is applied before paging.
    Rules: get_components R6 [BUG-2279]."""
    comp(db, S.PA, "Zulu", 11)
    comp(db, S.PA, "apple", 12)
    comp(db, S.PA, "Banana", 13)
    commit_point(db)
    result = svc.get_components(
        db, workspace_id=S.W1.id, user_id=S.U2.id, skip=0, limit=1
    )
    # Then 1
    assert names(result) == ["apple"]


# [claude] PCS-L-27
@xfail("BUG-2279", strict=False)
def test_pcs_l_27__case_only_tie_ordered_by_id(db, S):
    """PCS-L-27 — names equal but for case are ordered by id.
    Rules: get_components R6 [BUG-2279]."""
    gh = comp(db, S.PA, "gear", 12)
    gl = comp(db, S.PA, "Gear", 11)
    commit_point(db)
    result = svc.get_components(db, workspace_id=S.W1.id, user_id=S.U2.id, limit=1000)
    # Then 1
    assert [c.id for c in result] == [gl.id, gh.id]


# [claude] PCS-L-28
@xfail("BUG-2279")
def test_pcs_l_28__query_orders_by_name(db, S):
    """PCS-L-28 — the component query orders by name (recorder).
    Rules: get_components R6 [BUG-2279]."""
    comp(db, S.PA, "Arm", 12)
    w1_id, u2_id = S.W1.id, S.U2.id
    commit_point(db)
    with recorder(db) as stmts:
        result = svc.get_components(db, workspace_id=w1_id, user_id=u2_id, limit=1000)
    # Then 1
    assert len(result) == 1
    # Then 2
    assert (
        any(
            "FROM project_components" in s
            and "ORDER BY" in s
            and "project_components.name" in s.split("ORDER BY", 1)[1]
            for s in stmts
        )
        is True
    )


# =========================================================================== #
# get_components — one project
# =========================================================================== #


# [claude] PCS-L-29
def test_pcs_l_29__one_projects_components_only(db, S):
    """PCS-L-29 — a project's components only, not another project's or workspace's.
    Rules: get_components R1."""
    pc = proj(db, S, "Charlie")
    comp(db, S.P0, "Zero part", 10)
    comp(db, S.PB, "Base", 11)
    ca1 = comp(db, S.PA, "Arm", 12)
    ca2 = comp(db, S.PA, "Axle", 13)
    comp(db, pc, "Cap", 14)
    comp(db, S.P9, "Nine part", 15)
    commit_point(db)
    result = svc.get_components(
        db, workspace_id=S.W1.id, user_id=S.UG.id, project_id=S.PA.id, limit=1000
    )
    # Then 1
    assert all(isinstance(c, ProjectComponent) for c in result)
    # Then 2
    assert idset(result) == {ca1.id, ca2.id}


# [claude] PCS-L-30
def test_pcs_l_30__unknown_project_404(db, S):
    """PCS-L-30 — an unknown project answers 404.
    Rules: get_components R1, Errors."""
    comp(db, S.PA, "Arm", 12)
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_components(
            db, workspace_id=S.W1.id, user_id=S.U2.id, project_id=MISSING
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Project with ID 999999999 not found"


# [claude] PCS-L-31
def test_pcs_l_31__w0_project_404(db, S):
    """PCS-L-31 — W0's project answers 404 as missing.
    Rules: get_components R1."""
    comp(db, S.P0, "Zero part", 11)
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_components(
            db, workspace_id=S.W1.id, user_id=S.U2.id, project_id=S.P0.id
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NOPROJ(S.P0.id)


# [claude] PCS-L-32
def test_pcs_l_32__w2_project_404(db, S):
    """PCS-L-32 — W2's project answers 404 as missing.
    Rules: get_components R1."""
    comp(db, S.P9, "Nine part", 11)
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_components(
            db, workspace_id=S.W1.id, user_id=S.U2.id, project_id=S.P9.id
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NOPROJ(S.P9.id)


# [claude] PCS-L-33
def test_pcs_l_33__private_project_403(db, S):
    """PCS-L-33 — a private project the caller may not open answers 403.
    Rules: get_components R1."""
    comp(db, S.PB, "Base", 11)
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_components(
            db, workspace_id=S.W1.id, user_id=S.UG.id, project_id=S.PB.id
        )
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == NOACCESS


# [claude] PCS-L-34
def test_pcs_l_34__member_lists_private_project(db, S):
    """PCS-L-34 — a project member lists the private project's components.
    Rules: get_components R1."""
    pmem(db, S, S.PB, S.UG)
    cb = comp(db, S.PB, "Base", 11)
    commit_point(db)
    result = svc.get_components(
        db, workspace_id=S.W1.id, user_id=S.UG.id, project_id=S.PB.id, limit=1000
    )
    # Then 1
    assert idset(result) == {cb.id}


# [claude] PCS-L-35
@xfail("BUG-1278")
def test_pcs_l_35__deleted_project_404(db, S):
    """PCS-L-35 — a soft-deleted project answers 404.
    Rules: get_components R2 [BUG-1278]."""
    pd = proj(db, S, "Delta", deleted=True)
    comp(db, pd, "Door", 11)
    pd_id = pd.id
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_components(db, workspace_id=S.W1.id, user_id=S.U2.id, project_id=pd_id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NOPROJ(pd_id)


# [claude] PCS-L-36
@xfail("BUG-2278")
def test_pcs_l_36__project_id_zero_looked_up(db, S):
    """PCS-L-36 — project_id 0 is looked up, not "no filter".
    Rules: get_components R1 [BUG-2278]."""
    comp(db, S.PA, "Arm", 12)
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_components(db, workspace_id=S.W1.id, user_id=S.U2.id, project_id=0)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Project with ID 0 not found"


# [claude] PCS-L-37
def test_pcs_l_37__default_page_of_one_project_is_100(db, S):
    """PCS-L-37 — the default page of one project is 100.
    Rules: get_components R1."""
    bulk(db, 101, S.PA)
    commit_point(db)
    result = svc.get_components(
        db, workspace_id=S.W1.id, user_id=S.U2.id, project_id=S.PA.id
    )
    # Then 1
    assert len(result) == 100


# [claude] PCS-L-38
def test_pcs_l_38__skip_and_limit_reach_project_read(db, S):
    """PCS-L-38 — skip and limit reach the project read.
    Rules: get_components R1."""
    ca1 = comp(db, S.PA, "Arm", 12)
    ca2 = comp(db, S.PA, "Axle", 13)
    ca3 = comp(db, S.PA, "Axis", 14)
    commit_point(db)
    result = svc.get_components(
        db, workspace_id=S.W1.id, user_id=S.U2.id, project_id=S.PA.id, skip=1, limit=1
    )
    # Then 1
    assert len(result) == 1
    # Then 2
    assert idset(result) <= {ca1.id, ca2.id, ca3.id}


# [claude] PCS-L-39
@xfail("BUG-1275")
def test_pcs_l_39__one_project_ordered_by_name(db, S):
    """PCS-L-39 — one project's list is ordered by name (pass-through).
    Rules: get_components R1 (DAO get_by_project R3 [BUG-1275])."""
    comp(db, S.PA, "Beta", 11)
    comp(db, S.PA, "alpha", 12)
    comp(db, S.PA, "Gamma", 13)
    commit_point(db)
    result = svc.get_components(
        db, workspace_id=S.W1.id, user_id=S.U2.id, project_id=S.PA.id, limit=1000
    )
    # Then 1
    assert names(result) == ["alpha", "Beta", "Gamma"]


# [claude] PCS-L-40
def test_pcs_l_40__negative_skip_database_error(db, S):
    """PCS-L-40 — a negative skip is a database error.
    Rules: get_components Errors."""
    comp(db, S.PA, "Arm", 12)
    commit_point(db)
    # Then 1
    with pytest.raises(DataError):
        with db.begin_nested():
            svc.get_components(
                db,
                workspace_id=S.W1.id,
                user_id=S.U2.id,
                project_id=S.PA.id,
                skip=-1,
                limit=10,
            )
    # Then 2
    assert db.execute(select(1)).scalar() == 1


# [claude] PCS-L-41
def test_pcs_l_41__read_keeps_pending_changes(db, S):
    """PCS-L-41 — a read keeps the caller's pending changes and neither commits nor rolls back.
    Rules: get_components R7 (CT6)."""
    ca = comp(db, S.PA, "Arm", 12)
    commit_point(db)
    q = pending_q(db, S)
    edit_e(ca)
    with spies(db) as (cm, rb):
        result = svc.get_components(
            db, workspace_id=S.W1.id, user_id=S.U2.id, limit=1000
        )
    # Then 1
    assert ca.id in idset(result)
    # Then 2
    assert q in db.new and len(db.new) == 1
    # Then 3
    assert ca in db.dirty and len(db.dirty) == 1
    # Then 4
    assert not db.deleted
    # Then 5
    assert cm.call_count == 0
    assert rb.call_count == 0


# [claude] PCS-L-42
def test_pcs_l_42__refused_read_keeps_pending_changes(db, S):
    """PCS-L-42 — a refused read keeps the caller's pending changes.
    Rules: get_components R7 (CT6)."""
    ca = comp(db, S.PA, "Arm", 12)
    commit_point(db)
    q = pending_q(db, S)
    edit_e(ca)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (cm, rb):
            svc.get_components(
                db, workspace_id=S.W1.id, user_id=S.UG.id, project_id=S.PB.id
            )
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert q in db.new and len(db.new) == 1
    # Then 4
    assert ca in db.dirty
    # Then 5
    assert cm.call_count == 0
    assert rb.call_count == 0


# [claude] PCS-L-43
def test_pcs_l_43__project_list_keeps_pending_changes(db, S):
    """PCS-L-43 — one project's list keeps pending changes and neither commits nor rolls back.
    Rules: get_components R1, R7 (CT6)."""
    ca = comp(db, S.PA, "Arm", 12)
    commit_point(db)
    q = pending_q(db, S)
    edit_e(ca)
    with spies(db) as (cm, rb):
        result = svc.get_components(
            db, workspace_id=S.W1.id, user_id=S.U2.id, project_id=S.PA.id, limit=1000
        )
    # Then 1
    assert idset(result) == {ca.id}
    # Then 2
    assert q in db.new and len(db.new) == 1
    # Then 3
    assert ca in db.dirty and len(db.dirty) == 1
    # Then 4
    assert not db.deleted
    # Then 5
    assert cm.call_count == 0
    assert rb.call_count == 0


# =========================================================================== #
# get_by_id
# =========================================================================== #


# [claude] PCS-G-01
def test_pcs_g_01__returns_asked_component(db, S):
    """PCS-G-01 — returns the asked component among lower and higher ids.
    Rules: get_by_id R1."""
    comp(db, S.PA, "Arm", 11)
    c2 = comp(db, S.PA, "Axle", 12)
    comp(db, S.PA, "Axis", 13)
    commit_point(db)
    result = svc.get_by_id(
        db, component_id=c2.id, workspace_id=S.W1.id, user_id=S.UG.id
    )
    # Then 1
    assert isinstance(result, ProjectComponent)
    # Then 2
    assert result.id == c2.id
    assert result.name == "Axle"
    assert result.project_id == S.PA.id


# [claude] PCS-G-02
def test_pcs_g_02__unknown_id_404(db, S):
    """PCS-G-02 — an unknown id answers 404.
    Rules: get_by_id R1."""
    comp(db, S.PA, "Arm", 11)
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_by_id(db, component_id=MISSING, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NOCOMP


# [claude] PCS-G-03
def test_pcs_g_03__id_zero_404(db, S):
    """PCS-G-03 — id 0 answers 404.
    Rules: get_by_id R1."""
    comp(db, S.PA, "Arm", 11)
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_by_id(db, component_id=0, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NOCOMP


# [claude] PCS-G-04
def test_pcs_g_04__w0_component_404(db, S):
    """PCS-G-04 — W0's component answers 404.
    Rules: get_by_id R1."""
    c0 = comp(db, S.P0, "Zero part", 11)
    comp(db, S.PA, "Arm", 12)
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_by_id(db, component_id=c0.id, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NOCOMP


# [claude] PCS-G-05
def test_pcs_g_05__w2_component_404(db, S):
    """PCS-G-05 — W2's component answers 404.
    Rules: get_by_id R1."""
    comp(db, S.PA, "Arm", 11)
    c9 = comp(db, S.P9, "Nine part", 12)
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_by_id(db, component_id=c9.id, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NOCOMP


# [claude] PCS-G-06
def test_pcs_g_06__private_component_403(db, S):
    """PCS-G-06 — a component of a private project the caller may not open answers 403.
    Rules: get_by_id R1."""
    cb = comp(db, S.PB, "Base", 11)
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_by_id(db, component_id=cb.id, workspace_id=S.W1.id, user_id=S.UG.id)
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == NOACCESS


# [claude] PCS-G-07
def test_pcs_g_07__creator_opens_private_component(db, S):
    """PCS-G-07 — the private project's creator opens its component.
    Rules: get_by_id R1."""
    cb = comp(db, S.PB, "Base", 11)
    commit_point(db)
    result = svc.get_by_id(
        db, component_id=cb.id, workspace_id=S.W1.id, user_id=S.U1.id
    )
    # Then 1
    assert result.id == cb.id


# [claude] PCS-G-08
@xfail("BUG-1278")
def test_pcs_g_08__deleted_project_component_404(db, S):
    """PCS-G-08 — a component of a soft-deleted project answers 404.
    Rules: get_by_id R2 [BUG-1278]."""
    pd = proj(db, S, "Delta", deleted=True)
    cd = comp(db, pd, "Door", 11)
    pd_id, cd_id = pd.id, cd.id
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_by_id(db, component_id=cd_id, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NOPROJ(pd_id)


# [claude] PCS-G-09
def test_pcs_g_09__stray_component_projects_404(db, S):
    """PCS-G-09 — a W1 component whose project is in W2 answers the project's 404 (pass-through).
    Rules: get_by_id R1 (manager require_component_access R4)."""
    cx = comp(db, S.P9, "Stray", 11, workspace_id=S.W1.id)
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_by_id(db, component_id=cx.id, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NOPROJ(S.P9.id)


# [claude] PCS-G-10
def test_pcs_g_10__read_keeps_pending_changes(db, S):
    """PCS-G-10 — a read keeps the caller's pending changes and neither commits nor rolls back.
    Rules: get_by_id R3 (CT6)."""
    ca = comp(db, S.PA, "Arm", 12)
    commit_point(db)
    q = pending_q(db, S)
    edit_e(ca)
    with spies(db) as (cm, rb):
        result = svc.get_by_id(
            db, component_id=ca.id, workspace_id=S.W1.id, user_id=S.U2.id
        )
    # Then 1
    assert result.id == ca.id
    # Then 2
    assert q in db.new and len(db.new) == 1
    # Then 3
    assert ca in db.dirty and len(db.dirty) == 1
    # Then 4
    assert cm.call_count == 0
    assert rb.call_count == 0


# [claude] PCS-G-11
def test_pcs_g_11__refused_read_keeps_pending_changes(db, S):
    """PCS-G-11 — a refused read keeps the caller's pending changes.
    Rules: get_by_id R3 (CT6)."""
    comp(db, S.PA, "Arm", 12)
    commit_point(db)
    q = pending_q(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (cm, rb):
            svc.get_by_id(
                db, component_id=MISSING, workspace_id=S.W1.id, user_id=S.U2.id
            )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert q in db.new and len(db.new) == 1
    # Then 4
    assert cm.call_count == 0
    assert rb.call_count == 0


# =========================================================================== #
# create_component
# =========================================================================== #


# [claude] PCS-C-01
def test_pcs_c_01__created_committed_reread(db, S):
    """PCS-C-01 — the component is created, committed and returned re-read.
    Rules: create_component R3, CT1, CT2."""
    commit_point(db)
    with spies(db) as (cm, rb):
        result = svc.create_component(
            db,
            component_in=ProjectComponentCreate(
                project_id=S.PA.id, name="Roof", description="Top part", budget=1500.5
            ),
            workspace_id=S.W1.id,
            user_id=S.UG.id,
        )
    # Then 1
    assert isinstance(result, ProjectComponent)
    assert result.id is not None
    # Then 2
    assert result.created_at is not None
    assert result.status == ProjectStatusEnum.PLANNING
    # Then 3
    assert cm.call_count == 1
    assert rb.call_count == 0
    rid = result.id
    db.rollback()
    # Then 4
    row = reread(db, ProjectComponent, rid)
    assert row.workspace_id == S.W1.id
    assert row.project_id == S.PA.id
    assert row.name == "Roof"
    assert row.description == "Top part"
    # Then 5
    row = reread(db, ProjectComponent, rid)
    assert row.budget == Decimal("1500.50")
    assert row.start_date is None
    assert row.end_date is None
    assert row.deadline is None


# [claude] PCS-C-02
def test_pcs_c_02__one_component_created_event(db, S):
    """PCS-C-02 — creating writes one component_created project event, committed.
    Rules: create_component R3."""
    commit_point(db)
    result = svc.create_component(
        db,
        component_in=ProjectComponentCreate(project_id=S.PA.id, name="Roof"),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.id is not None
    rid = result.id
    db.rollback()
    # Then 2
    rows = evs(db, S.PA.id, "component_created")
    assert len(rows) == 1
    # Then 3
    assert rows[0].workspace_id == S.W1.id
    assert rows[0].performed_by == S.UG.id
    assert rows[0].description == 'Added component "Roof"'
    # Then 4
    assert rows[0].metadata_json == {"component_id": rid, "component_name": "Roof"}
    assert rows[0].created_at is not None


# [claude] PCS-C-03
def test_pcs_c_03__any_status_at_creation(db, S):
    """PCS-C-03 — any status may be given at creation.
    Rules: create_component R4."""
    commit_point(db)
    result = svc.create_component(
        db,
        component_in=ProjectComponentCreate(
            project_id=S.PA.id, name="Roof", status=ProjectStatusEnum.COMPLETED
        ),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.status == ProjectStatusEnum.COMPLETED
    rid = result.id
    db.rollback()
    # Then 2
    assert reread(db, ProjectComponent, rid).status == ProjectStatusEnum.COMPLETED


# [claude] PCS-C-04
def test_pcs_c_04__unknown_project_404_rolled_back_once(db, S):
    """PCS-C-04 — an unknown project answers 404, rolled back once, nothing written.
    Rules: create_component R1, Errors, CT3."""
    commit_point(db)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (cm, rb):
            svc.create_component(
                db,
                component_in=ProjectComponentCreate(project_id=MISSING, name="Roof"),
                workspace_id=S.W1.id,
                user_id=S.UG.id,
            )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Project with ID 999999999 not found"
    # Then 4
    assert not db.new and not db.dirty
    # Then 5
    assert rb.call_count == 1
    assert cm.call_count == 0
    # Then 6
    assert counts(db) == before


# [claude] PCS-C-05
def test_pcs_c_05__project_id_zero_404(db, S):
    """PCS-C-05 — project_id 0 answers 404.
    Rules: create_component R1."""
    commit_point(db)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_component(
            db,
            component_in=ProjectComponentCreate(project_id=0, name="Roof"),
            workspace_id=S.W1.id,
            user_id=S.UG.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Project with ID 0 not found"
    # Then 4
    assert not db.new and not db.dirty
    # Then 5
    assert counts(db) == before


# [claude] PCS-C-06
def test_pcs_c_06__w0_project_404(db, S):
    """PCS-C-06 — W0's project answers 404 as missing.
    Rules: create_component R1 (HR-16)."""
    p0_id = S.P0.id
    commit_point(db)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_component(
            db,
            component_in=ProjectComponentCreate(project_id=p0_id, name="Roof"),
            workspace_id=S.W1.id,
            user_id=S.U2.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NOPROJ(p0_id)
    # Then 4
    assert not db.new and not db.dirty
    # Then 5
    assert counts(db) == before


# [claude] PCS-C-07
def test_pcs_c_07__w2_project_404_extra_row_discarded(db, S):
    """PCS-C-07 — W2's project answers 404 and an uncommitted row of the session is discarded.
    Rules: create_component R1 (HR-16), CT3."""
    p9_id = S.P9.id
    commit_point(db)
    before = counts(db)
    x_id = extra_x(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_component(
            db,
            component_in=ProjectComponentCreate(project_id=p9_id, name="Roof"),
            workspace_id=S.W1.id,
            user_id=S.U2.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NOPROJ(p9_id)
    # Then 4
    assert not db.new and not db.dirty
    # Then 5
    assert x_count(db, x_id) == 0
    # Then 6
    assert counts(db) == before


# [claude] PCS-C-08
def test_pcs_c_08__private_project_403(db, S):
    """PCS-C-08 — a private project the caller may not open answers 403, nothing written.
    Rules: create_component R1, Errors."""
    commit_point(db)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_component(
            db,
            component_in=ProjectComponentCreate(project_id=S.PB.id, name="Roof"),
            workspace_id=S.W1.id,
            user_id=S.UG.id,
        )
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == NOACCESS
    # Then 4
    assert not db.new and not db.dirty
    # Then 5
    assert counts(db) == before


# [claude] PCS-C-09
def test_pcs_c_09__member_adds_to_private_project(db, S):
    """PCS-C-09 — a project member may add to a private project.
    Rules: create_component R1, R3."""
    pmem(db, S, S.PB, S.UG)
    commit_point(db)
    result = svc.create_component(
        db,
        component_in=ProjectComponentCreate(project_id=S.PB.id, name="Roof"),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.project_id == S.PB.id
    rid = result.id
    db.rollback()
    # Then 2
    row = reread(db, ProjectComponent, rid)
    assert row is not None
    assert row.project_id == S.PB.id


# [claude] PCS-C-10
@xfail("BUG-1278")
def test_pcs_c_10__deleted_project_404(db, S):
    """PCS-C-10 — a soft-deleted project answers 404, nothing written.
    Rules: create_component R2 [BUG-1278]."""
    pd = proj(db, S, "Delta", deleted=True)
    pd_id = pd.id
    commit_point(db)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_component(
            db,
            component_in=ProjectComponentCreate(project_id=pd_id, name="Roof"),
            workspace_id=S.W1.id,
            user_id=S.U2.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NOPROJ(pd_id)
    # Then 4
    assert counts(db) == before


# [claude] PCS-C-11
@xfail("BUG-2272")
def test_pcs_c_11__name_stored_trimmed(db, S):
    """PCS-C-11 — the name is stored trimmed.
    Rules: create_component R5 [BUG-2272]."""
    commit_point(db)
    result = svc.create_component(
        db,
        component_in=ProjectComponentCreate(project_id=S.PA.id, name="  Roof  "),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, ProjectComponent, result.id).name == "Roof"


# [claude] PCS-C-12
@xfail("BUG-2272")
def test_pcs_c_12__empty_name_refused(db, S):
    """PCS-C-12 — an empty name is refused by the schema.
    Rules: create_component R5 [BUG-2272]."""
    # Then 1
    with pytest.raises(PydanticValidationError):
        ProjectComponentCreate(project_id=S.PA.id, name="")


# [claude] PCS-C-13
@xfail("BUG-2272")
def test_pcs_c_13__whitespace_name_refused(db, S):
    """PCS-C-13 — a whitespace-only name is refused by the schema.
    Rules: create_component R5 [BUG-2272]."""
    # Then 1
    with pytest.raises(PydanticValidationError):
        ProjectComponentCreate(project_id=S.PA.id, name="   ")


# [claude] PCS-C-14
def test_pcs_c_14__inner_spaces_and_description_kept(db, S):
    """PCS-C-14 — inner spaces and capitals are kept; the description is kept as typed.
    Rules: create_component R5."""
    commit_point(db)
    result = svc.create_component(
        db,
        component_in=ProjectComponentCreate(
            project_id=S.PA.id, name="Roof  DECK", description="  Top part  "
        ),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.name == "Roof  DECK"
    # Then 2
    row = reread(db, ProjectComponent, result.id)
    assert row.name == "Roof  DECK"
    assert row.description == "  Top part  "


# [claude] PCS-C-15
def test_pcs_c_15__budget_zero_accepted(db, S):
    """PCS-C-15 — a budget of 0 is accepted.
    Rules: create_component R6."""
    commit_point(db)
    result = svc.create_component(
        db,
        component_in=ProjectComponentCreate(project_id=S.PA.id, name="Roof", budget=0),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, ProjectComponent, result.id).budget == Decimal("0.00")


# [claude] PCS-C-16
def test_pcs_c_16__no_budget_accepted(db, S):
    """PCS-C-16 — no budget is accepted.
    Rules: create_component R6."""
    commit_point(db)
    result = svc.create_component(
        db,
        component_in=ProjectComponentCreate(
            project_id=S.PA.id, name="Roof", budget=None
        ),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, ProjectComponent, result.id).budget is None


# [claude] PCS-C-17
def test_pcs_c_17__thirteen_digits_two_decimals_accepted(db, S):
    """PCS-C-17 — 13 integer digits and 2 decimals are accepted.
    Rules: create_component R6."""
    commit_point(db)
    result = svc.create_component(
        db,
        component_in=ProjectComponentCreate(
            project_id=S.PA.id, name="Roof", budget=9999999999999.99
        ),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, ProjectComponent, result.id).budget == Decimal("9999999999999.99")


# [claude] PCS-C-18
@xfail("BUG-2273")
def test_pcs_c_18__negative_budget_refused(db, S):
    """PCS-C-18 — a negative budget is refused by the schema.
    Rules: create_component R6 [BUG-2273]."""
    # Then 1
    with pytest.raises(PydanticValidationError):
        ProjectComponentCreate(project_id=S.PA.id, name="Roof", budget=-0.01)


# [claude] PCS-C-19
@xfail("BUG-2274")
def test_pcs_c_19__three_decimals_refused(db, S):
    """PCS-C-19 — a budget with three decimals is refused by the schema.
    Rules: create_component R6 [BUG-2274]."""
    # Then 1
    with pytest.raises(PydanticValidationError):
        ProjectComponentCreate(project_id=S.PA.id, name="Roof", budget=1000.005)


# [claude] PCS-C-20
@xfail("BUG-2274")
def test_pcs_c_20__fourteen_digits_refused(db, S):
    """PCS-C-20 — a budget with 14 integer digits is refused by the schema.
    Rules: create_component R6 [BUG-2274]."""
    # Then 1
    with pytest.raises(PydanticValidationError):
        ProjectComponentCreate(project_id=S.PA.id, name="Roof", budget=10000000000000)


# [claude] PCS-C-21
def test_pcs_c_21__failing_commit_rolls_back_once(db, S):
    """PCS-C-21 — a failing commit rolls back once and nothing is saved.
    Rules: create_component R7, CT4."""
    commit_point(db)
    before = counts(db)
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.create_component(
                db,
                component_in=ProjectComponentCreate(project_id=S.PA.id, name="Roof"),
                workspace_id=S.W1.id,
                user_id=S.UG.id,
            )
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count == 1
    # Then 3
    assert counts(db) == before


# [claude] PCS-C-22
def test_pcs_c_22__failing_refresh_leaves_saved(db, S):
    """PCS-C-22 — a failing re-read leaves the component and its event saved.
    Rules: create_component R7, CT5."""
    pa_id = S.PA.id
    commit_point(db)
    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db):
            svc.create_component(
                db,
                component_in=ProjectComponentCreate(project_id=pa_id, name="Roof"),
                workspace_id=S.W1.id,
                user_id=S.UG.id,
            )
    # Then 1
    assert str(exc.value) == "boom"
    db.rollback()
    # Then 2
    assert (
        db.scalar(
            select(func.count())
            .select_from(ProjectComponent)
            .where(
                ProjectComponent.project_id == pa_id, ProjectComponent.name == "Roof"
            )
        )
        == 1
    )
    # Then 3
    assert len(evs(db, pa_id, "component_created")) == 1


# =========================================================================== #
# update_component
# =========================================================================== #


# [claude] PCS-U-01
def test_pcs_u_01__sent_field_changed_others_stay(db, S):
    """PCS-U-01 — a sent field is changed, the others stay, committed and re-read.
    Rules: update_component R3, R7, CT1, CT2."""
    cr = cr_upd(db, S)
    cr_id = cr.id
    commit_point(db)
    with spies(db) as (cm, rb):
        result = svc.update_component(
            db,
            component_id=cr_id,
            component_in=ProjectComponentUpdate(name="Roof deck"),
            workspace_id=S.W1.id,
            user_id=S.UG.id,
        )
    # Then 1
    assert isinstance(result, ProjectComponent)
    assert result.id == cr_id
    assert result.name == "Roof deck"
    # Then 2
    assert cm.call_count == 1
    assert rb.call_count == 0
    db.rollback()
    # Then 3
    row = reread(db, ProjectComponent, cr_id)
    assert row.name == "Roof deck"
    assert row.description == "Top"
    assert row.budget == Decimal("100.00")
    # Then 4
    row = reread(db, ProjectComponent, cr_id)
    assert row.project_id == S.PA.id
    assert row.workspace_id == S.W1.id
    assert row.status == ProjectStatusEnum.PLANNING


# [claude] PCS-U-02
def test_pcs_u_02__one_component_updated_event(db, S):
    """PCS-U-02 — a change writes one component_updated event with the new name.
    Rules: update_component R4."""
    cr = cr_upd(db, S)
    cr_id = cr.id
    commit_point(db)
    result = svc.update_component(
        db,
        component_id=cr_id,
        component_in=ProjectComponentUpdate(name="Roof deck"),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.name == "Roof deck"
    db.rollback()
    # Then 2
    rows = evs(db, S.PA.id, "component_updated")
    assert len(rows) == 1
    # Then 3
    assert rows[0].workspace_id == S.W1.id
    assert rows[0].performed_by == S.UG.id
    assert rows[0].description == 'Updated component "Roof deck"'
    # Then 4
    assert rows[0].metadata_json == {
        "component_id": cr_id,
        "component_name": "Roof deck",
    }


# [claude] PCS-U-03
def test_pcs_u_03__budget_only_change_logs_current_name(db, S):
    """PCS-U-03 — a budget-only change logs the current name.
    Rules: update_component R4."""
    cr = cr_upd(db, S)
    cr_id = cr.id
    commit_point(db)
    result = svc.update_component(
        db,
        component_id=cr_id,
        component_in=ProjectComponentUpdate(budget=250.5),
        workspace_id=S.W1.id,
        user_id=S.U2.id,
    )
    # Then 1
    assert result.budget == Decimal("250.50")
    db.rollback()
    # Then 2
    rows = evs(db, S.PA.id, "component_updated")
    assert len(rows) == 1
    # Then 3
    assert rows[0].description == 'Updated component "Roof"'
    assert rows[0].performed_by == S.U2.id


# [claude] PCS-U-04
def test_pcs_u_04__any_status_dates_not_compared(db, S):
    """PCS-U-04 — any status may follow any status; dates are not compared.
    Rules: update_component R3."""
    cr = cr_upd(db, S, status=ProjectStatusEnum.COMPLETED)
    cr_id = cr.id
    commit_point(db)
    result = svc.update_component(
        db,
        component_id=cr_id,
        component_in=ProjectComponentUpdate(
            status=ProjectStatusEnum.PLANNING,
            start_date=datetime(2026, 5, 1, 0, 0),
            end_date=datetime(2026, 4, 1, 0, 0),
        ),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.status == ProjectStatusEnum.PLANNING
    db.rollback()
    # Then 2
    row = reread(db, ProjectComponent, cr_id)
    assert row.status == ProjectStatusEnum.PLANNING
    # Then 3
    assert row.start_date == datetime(2026, 5, 1, 0, 0)
    assert row.end_date == datetime(2026, 4, 1, 0, 0)


# [claude] PCS-U-05
def test_pcs_u_05__unknown_id_404_rolled_back_once(db, S):
    """PCS-U-05 — an unknown id answers 404, rolled back once, nothing written.
    Rules: update_component R1, CT3."""
    cr = cr_upd(db, S)
    commit_point(db)
    before_cr = snap(db, cr)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (cm, rb):
            svc.update_component(
                db,
                component_id=MISSING,
                component_in=ProjectComponentUpdate(name="New"),
                workspace_id=S.W1.id,
                user_id=S.U2.id,
            )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NOCOMP
    # Then 4
    assert not db.new and not db.dirty
    # Then 5
    assert rb.call_count == 1
    assert cm.call_count == 0
    # Then 6
    assert unchanged(db, ProjectComponent, before_cr)
    # Then 7
    assert counts(db) == before


# [claude] PCS-U-06
def test_pcs_u_06__w0_component_404(db, S):
    """PCS-U-06 — W0's component answers 404.
    Rules: update_component R1."""
    c0 = comp(db, S.P0, "Zero part", 11)
    cr_upd(db, S)
    commit_point(db)
    before_c0 = snap(db, c0)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_component(
            db,
            component_id=before_c0["id"],
            component_in=ProjectComponentUpdate(name="New"),
            workspace_id=S.W1.id,
            user_id=S.U2.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NOCOMP
    # Then 4
    assert not db.dirty
    # Then 5
    assert unchanged(db, ProjectComponent, before_c0)
    # Then 6
    assert counts(db) == before


# [claude] PCS-U-07
def test_pcs_u_07__w2_component_404_extra_row_discarded(db, S):
    """PCS-U-07 — W2's component answers 404 and an uncommitted row of the session is discarded.
    Rules: update_component R1, CT3."""
    cr_upd(db, S)
    c9 = comp(db, S.P9, "Nine part", 13)
    commit_point(db)
    before_c9 = snap(db, c9)
    before = counts(db)
    x_id = extra_x(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_component(
            db,
            component_id=before_c9["id"],
            component_in=ProjectComponentUpdate(name="New"),
            workspace_id=S.W1.id,
            user_id=S.U2.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NOCOMP
    # Then 4
    assert not db.new and not db.dirty
    # Then 5
    assert x_count(db, x_id) == 0
    # Then 6
    assert unchanged(db, ProjectComponent, before_c9)
    # Then 7
    assert counts(db) == before


# [claude] PCS-U-08
def test_pcs_u_08__private_component_403(db, S):
    """PCS-U-08 — a component of a private project the caller may not open answers 403.
    Rules: update_component R1."""
    cb = comp(db, S.PB, "Base", 11)
    commit_point(db)
    before_cb = snap(db, cb)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_component(
            db,
            component_id=before_cb["id"],
            component_in=ProjectComponentUpdate(name="New"),
            workspace_id=S.W1.id,
            user_id=S.UG.id,
        )
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == NOACCESS
    # Then 4
    assert not db.dirty
    # Then 5
    assert unchanged(db, ProjectComponent, before_cb)
    # Then 6
    assert counts(db) == before


# [claude] PCS-U-09
@xfail("BUG-1278")
def test_pcs_u_09__deleted_project_component_404(db, S):
    """PCS-U-09 — a component of a soft-deleted project answers 404, nothing written.
    Rules: update_component R2 [BUG-1278]."""
    pd = proj(db, S, "Delta", deleted=True)
    cd = comp(db, pd, "Door", 11)
    pd_id = pd.id
    commit_point(db)
    before_cd = snap(db, cd)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_component(
            db,
            component_id=before_cd["id"],
            component_in=ProjectComponentUpdate(name="New"),
            workspace_id=S.W1.id,
            user_id=S.U2.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NOPROJ(pd_id)
    # Then 4
    assert unchanged(db, ProjectComponent, before_cd)
    # Then 5
    assert counts(db) == before


# [claude] PCS-U-10
@xfail("BUG-2275")
def test_pcs_u_10__null_clears_description(db, S):
    """PCS-U-10 — an explicit null clears the description.
    Rules: update_component R3a [BUG-2275]."""
    cr = cr_upd(db, S)
    cr_id = cr.id
    commit_point(db)
    result = svc.update_component(
        db,
        component_id=cr_id,
        component_in=ProjectComponentUpdate(description=None),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.id == cr_id
    # Then 2
    row = reread(db, ProjectComponent, cr_id)
    assert row.description is None
    # Then 3
    assert row.name == "Roof"
    assert row.budget == Decimal("100.00")


# [claude] PCS-U-11
@xfail("BUG-2275")
def test_pcs_u_11__null_clears_budget(db, S):
    """PCS-U-11 — an explicit null clears the budget.
    Rules: update_component R3a [BUG-2275]."""
    cr = cr_upd(db, S)
    cr_id = cr.id
    commit_point(db)
    result = svc.update_component(
        db,
        component_id=cr_id,
        component_in=ProjectComponentUpdate(budget=None),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.id == cr_id
    # Then 2
    assert reread(db, ProjectComponent, cr_id).budget is None


# [claude] PCS-U-12
@xfail("BUG-2275")
def test_pcs_u_12__nulls_clear_deadline_and_dates(db, S):
    """PCS-U-12 — explicit nulls clear the deadline and the dates.
    Rules: update_component R3a [BUG-2275]."""
    cr = cr_upd(
        db,
        S,
        deadline=datetime(2026, 6, 1, 0, 0),
        start_date=datetime(2026, 5, 1, 0, 0),
        end_date=datetime(2026, 7, 1, 0, 0),
    )
    cr_id = cr.id
    commit_point(db)
    result = svc.update_component(
        db,
        component_id=cr_id,
        component_in=ProjectComponentUpdate(
            deadline=None, start_date=None, end_date=None
        ),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.id == cr_id
    # Then 2
    row = reread(db, ProjectComponent, cr_id)
    assert row.deadline is None
    # Then 3
    assert row.start_date is None
    # Then 4
    assert row.end_date is None


# [claude] PCS-U-13
@xfail("BUG-2275")
def test_pcs_u_13__null_name_refused(db, S):
    """PCS-U-13 — a null name is refused by the schema.
    Rules: update_component R3a [BUG-2275]."""
    # Then 1
    with pytest.raises(PydanticValidationError):
        ProjectComponentUpdate(name=None)


# [claude] PCS-U-14
@xfail("BUG-2275")
def test_pcs_u_14__null_status_refused(db, S):
    """PCS-U-14 — a null status is refused by the schema.
    Rules: update_component R3a [BUG-2275]."""
    # Then 1
    with pytest.raises(PydanticValidationError):
        ProjectComponentUpdate(status=None)


# [claude] PCS-U-15
def test_pcs_u_15__empty_update_unchanged(db, S):
    """PCS-U-15 — an empty update returns the component unchanged.
    Rules: update_component R3, R7."""
    cr = cr_upd(db, S)
    commit_point(db)
    before_cr = snap(db, cr)
    result = svc.update_component(
        db,
        component_id=before_cr["id"],
        component_in=ProjectComponentUpdate(),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.id == before_cr["id"]
    assert result.name == "Roof"
    # Then 2
    assert unchanged(db, ProjectComponent, before_cr)


# [claude] PCS-U-16
@xfail("BUG-2276")
def test_pcs_u_16__empty_update_no_event(db, S):
    """PCS-U-16 — an empty update writes no event.
    Rules: update_component R4 [BUG-2276]."""
    cr = cr_upd(db, S)
    cr_id = cr.id
    commit_point(db)
    result = svc.update_component(
        db,
        component_id=cr_id,
        component_in=ProjectComponentUpdate(),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.id == cr_id
    # Then 2
    assert len(evs(db, S.PA.id, "component_updated")) == 0


# [claude] PCS-U-17
@xfail("BUG-2276")
def test_pcs_u_17__same_values_no_event(db, S):
    """PCS-U-17 — sending the same values writes no event.
    Rules: update_component R4 [BUG-2276]."""
    cr = cr_upd(db, S)
    cr_id = cr.id
    commit_point(db)
    result = svc.update_component(
        db,
        component_id=cr_id,
        component_in=ProjectComponentUpdate(name="Roof", description="Top", budget=100),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.id == cr_id
    # Then 2
    assert len(evs(db, S.PA.id, "component_updated")) == 0


# [claude] PCS-U-18
@xfail("BUG-2272")
def test_pcs_u_18__sent_name_stored_trimmed(db, S):
    """PCS-U-18 — a sent name is stored trimmed.
    Rules: update_component R5 [BUG-2272]."""
    cr = cr_upd(db, S)
    cr_id = cr.id
    commit_point(db)
    result = svc.update_component(
        db,
        component_id=cr_id,
        component_in=ProjectComponentUpdate(name="  Roof deck  "),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.id == cr_id
    # Then 2
    assert reread(db, ProjectComponent, cr_id).name == "Roof deck"


# [claude] PCS-U-19
@xfail("BUG-2272")
def test_pcs_u_19__whitespace_name_refused_on_update(db, S):
    """PCS-U-19 — a whitespace-only name is refused by the update schema.
    Rules: update_component R5 [BUG-2272]."""
    # Then 1
    with pytest.raises(PydanticValidationError):
        ProjectComponentUpdate(name="   ")


# [claude] PCS-U-20
def test_pcs_u_20__budget_zero_on_update(db, S):
    """PCS-U-20 — a budget of 0 is accepted on update.
    Rules: update_component R6."""
    cr = cr_upd(db, S)
    cr_id = cr.id
    commit_point(db)
    result = svc.update_component(
        db,
        component_id=cr_id,
        component_in=ProjectComponentUpdate(budget=0),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.id == cr_id
    # Then 2
    assert reread(db, ProjectComponent, cr_id).budget == Decimal("0.00")


# [claude] PCS-U-21
@xfail("BUG-2273")
def test_pcs_u_21__negative_budget_refused_on_update(db, S):
    """PCS-U-21 — a negative budget is refused by the update schema.
    Rules: update_component R6 [BUG-2273]."""
    # Then 1
    with pytest.raises(PydanticValidationError):
        ProjectComponentUpdate(budget=-0.01)


# [claude] PCS-U-22
@xfail("BUG-2274")
def test_pcs_u_22__three_decimals_refused_on_update(db, S):
    """PCS-U-22 — a budget with three decimals is refused by the update schema.
    Rules: update_component R6 [BUG-2274]."""
    # Then 1
    with pytest.raises(PydanticValidationError):
        ProjectComponentUpdate(budget=1000.005)


# [claude] PCS-U-23
def test_pcs_u_23__failing_commit_rolls_back_once(db, S):
    """PCS-U-23 — a failing commit rolls back once and nothing is saved.
    Rules: update_component R7, CT4."""
    cr = cr_upd(db, S)
    commit_point(db)
    before_cr = snap(db, cr)
    before = counts(db)
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.update_component(
                db,
                component_id=before_cr["id"],
                component_in=ProjectComponentUpdate(name="Roof deck"),
                workspace_id=S.W1.id,
                user_id=S.UG.id,
            )
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count == 1
    # Then 3
    assert unchanged(db, ProjectComponent, before_cr)
    # Then 4
    assert counts(db) == before


# [claude] PCS-U-24
def test_pcs_u_24__failing_refresh_leaves_change_saved(db, S):
    """PCS-U-24 — a failing re-read leaves the change saved.
    Rules: update_component R7, CT5."""
    cr = cr_upd(db, S)
    cr_id = cr.id
    commit_point(db)
    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db):
            svc.update_component(
                db,
                component_id=cr_id,
                component_in=ProjectComponentUpdate(name="Roof deck"),
                workspace_id=S.W1.id,
                user_id=S.UG.id,
            )
    # Then 1
    assert str(exc.value) == "boom"
    db.rollback()
    # Then 2
    assert reread(db, ProjectComponent, cr_id).name == "Roof deck"


# [claude] PCS-U-25
def test_pcs_u_25__sent_project_id_ignored(db, S):
    """PCS-U-25 — a sent project_id is ignored; the other fields are applied.
    Rules: update_component R3b."""
    cr = cr_upd(db, S)
    cr_id = cr.id
    pa_id, pb_id = S.PA.id, S.PB.id
    commit_point(db)
    result = svc.update_component(
        db,
        component_id=cr_id,
        component_in=ProjectComponentUpdate(
            project_id=pb_id, name="Roof deck", deadline=datetime(2026, 6, 1, 14, 30)
        ),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.project_id == pa_id
    assert result.name == "Roof deck"
    db.rollback()
    # Then 2
    row = reread(db, ProjectComponent, cr_id)
    assert row.project_id == pa_id
    # Then 3
    assert row.name == "Roof deck"
    assert row.deadline == datetime(2026, 6, 1, 14, 30)
    # Then 4
    assert len(evs(db, pb_id, "component_updated")) == 0


# =========================================================================== #
# delete_component
# =========================================================================== #


# [claude] PCS-D-01
def test_pcs_d_01__deleted_committed_true(db, S):
    """PCS-D-01 — a component without history is deleted, committed, and True is returned.
    Rules: delete_component R6a, CT1."""
    cr = cr_del(db, S)
    c2 = comp(db, S.PA, "Axle", 13)
    cr_id, c2_id = cr.id, c2.id
    commit_point(db)
    with spies(db) as (cm, rb):
        result = svc.delete_component(
            db, component_id=cr_id, workspace_id=S.W1.id, user_id=S.UG.id
        )
    # Then 1
    assert result is True
    # Then 2
    assert cm.call_count == 1
    assert rb.call_count == 0
    db.rollback()
    # Then 3
    assert reread(db, ProjectComponent, cr_id) is None
    # Then 4
    assert reread(db, ProjectComponent, c2_id) is not None


# [claude] PCS-D-02
def test_pcs_d_02__one_component_deleted_event_stays(db, S):
    """PCS-D-02 — deleting writes one component_deleted event that stays.
    Rules: delete_component R6a."""
    cr = cr_del(db, S)
    cr_id = cr.id
    commit_point(db)
    result = svc.delete_component(
        db, component_id=cr_id, workspace_id=S.W1.id, user_id=S.UG.id
    )
    # Then 1
    assert result is True
    db.rollback()
    # Then 2
    rows = evs(db, S.PA.id, "component_deleted")
    assert len(rows) == 1
    # Then 3
    assert rows[0].workspace_id == S.W1.id
    assert rows[0].performed_by == S.UG.id
    assert rows[0].description == 'Deleted component "Roof"'
    # Then 4
    assert rows[0].metadata_json == {"component_id": cr_id, "component_name": "Roof"}


# [claude] PCS-D-03
def test_pcs_d_03__attachment_added_log_does_not_block(db, S):
    """PCS-D-03 — an attachment_added log row does not block and goes with the component.
    Rules: delete_component R5, R6a."""
    cr = cr_del(db, S)
    a1 = act(db, S, cr, "attachment_added")
    cr_id, a1_id = cr.id, a1.id
    commit_point(db)
    result = svc.delete_component(
        db, component_id=cr_id, workspace_id=S.W1.id, user_id=S.UG.id
    )
    # Then 1
    assert result is True
    db.rollback()
    # Then 2
    assert reread(db, ProjectComponent, cr_id) is None
    # Then 3
    assert reread(db, ProjectComponentActivityEvent, a1_id) is None


# [claude] PCS-D-04
def test_pcs_d_04__attachment_removed_log_does_not_block(db, S):
    """PCS-D-04 — an attachment_removed log row does not block and goes with the component.
    Rules: delete_component R5, R6a."""
    cr = cr_del(db, S)
    a1 = act(db, S, cr, "attachment_removed")
    cr_id, a1_id = cr.id, a1.id
    commit_point(db)
    result = svc.delete_component(
        db, component_id=cr_id, workspace_id=S.W1.id, user_id=S.UG.id
    )
    # Then 1
    assert result is True
    db.rollback()
    # Then 2
    assert reread(db, ProjectComponent, cr_id) is None
    # Then 3
    assert reread(db, ProjectComponentActivityEvent, a1_id) is None


# [claude] PCS-D-05
def test_pcs_d_05__project_events_do_not_block(db, S):
    """PCS-D-05 — the project's own events do not block and stay.
    Rules: delete_component R5."""
    cr = cr_del(db, S)
    e1 = pev(db, S, S.PA)
    cr_id, e1_id = cr.id, e1.id
    commit_point(db)
    result = svc.delete_component(
        db, component_id=cr_id, workspace_id=S.W1.id, user_id=S.UG.id
    )
    # Then 1
    assert result is True
    db.rollback()
    # Then 2
    assert reread(db, ProjectComponent, cr_id) is None
    # Then 3
    assert reread(db, ProjectEvent, e1_id) is not None


# [claude] PCS-D-06
@xfail("BUG-2262")
def test_pcs_d_06__attachment_links_go_with_component(db, S):
    """PCS-D-06 — attachment-link rows do not block and are removed with the component.
    Rules: delete_component R5a [BUG-2262], R6a."""
    cr = cr_del(db, S)
    c2 = comp(db, S.PA, "Axle", 13)
    a = at0(db, S)
    lk = att(db, S, cr, a)
    lk2 = att(db, S, c2, a)
    cr_id, c2_id, a_id, lk_id, lk2_id = cr.id, c2.id, a.id, lk.id, lk2.id
    commit_point(db)
    # Then 1 (today the call itself raises IntegrityError)
    result = svc.delete_component(
        db, component_id=cr_id, workspace_id=S.W1.id, user_id=S.UG.id
    )
    assert result is True
    db.rollback()
    # Then 2
    assert reread(db, ProjectComponent, cr_id) is None
    # Then 3
    assert reread(db, ProjectComponentAttachment, lk_id) is None
    # Then 4
    assert reread(db, Attachment, a_id) is not None
    # Then 5
    row = reread(db, ProjectComponentAttachment, lk2_id)
    assert row is not None
    assert row.project_component_id == c2_id
    # Then 6
    assert reread(db, ProjectComponent, c2_id) is not None
    # Then 7
    rows = evs(db, S.PA.id, "component_deleted")
    assert len(rows) == 1
    # Then 8
    assert rows[0].description == 'Deleted component "Roof"'
    assert rows[0].metadata_json == {"component_id": cr_id, "component_name": "Roof"}


# [claude] PCS-D-07
def test_pcs_d_07__unknown_id_404_rolled_back_once(db, S):
    """PCS-D-07 — an unknown id answers 404, rolled back once.
    Rules: delete_component R1, Errors, CT3."""
    cr_del(db, S)
    commit_point(db)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (cm, rb):
            svc.delete_component(
                db, component_id=MISSING, workspace_id=S.W1.id, user_id=S.U2.id
            )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NOCOMP
    # Then 4
    assert not db.deleted and not db.new
    # Then 5
    assert rb.call_count == 1
    assert cm.call_count == 0
    # Then 6
    assert counts(db) == before


# [claude] PCS-D-08
def test_pcs_d_08__w0_component_404_stays(db, S):
    """PCS-D-08 — W0's component answers 404 and stays.
    Rules: delete_component R1."""
    c0 = comp(db, S.P0, "Zero part", 11)
    cr_del(db, S)
    c0_id = c0.id
    commit_point(db)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_component(
            db, component_id=c0_id, workspace_id=S.W1.id, user_id=S.U2.id
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NOCOMP
    # Then 4
    assert not db.deleted and not db.new
    # Then 5
    assert counts(db) == before


# [claude] PCS-D-09
def test_pcs_d_09__w2_component_404_extra_row_discarded(db, S):
    """PCS-D-09 — W2's component answers 404 and an uncommitted row of the session is discarded.
    Rules: delete_component R1, CT3."""
    cr_del(db, S)
    c9 = comp(db, S.P9, "Nine part", 13)
    c9_id = c9.id
    commit_point(db)
    before = counts(db)
    x_id = extra_x(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_component(
            db, component_id=c9_id, workspace_id=S.W1.id, user_id=S.U2.id
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NOCOMP
    # Then 4
    assert not db.deleted and not db.new
    # Then 5
    assert x_count(db, x_id) == 0
    # Then 6
    assert counts(db) == before


# [claude] PCS-D-10
def test_pcs_d_10__private_component_403(db, S):
    """PCS-D-10 — a component of a private project the caller may not open answers 403.
    Rules: delete_component R1, Errors."""
    cb = comp(db, S.PB, "Base", 11)
    cb_id = cb.id
    commit_point(db)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_component(
            db, component_id=cb_id, workspace_id=S.W1.id, user_id=S.UG.id
        )
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == NOACCESS
    # Then 4
    assert not db.deleted and not db.new
    # Then 5
    assert counts(db) == before


# [claude] PCS-D-11
@xfail("BUG-1278")
def test_pcs_d_11__deleted_project_component_404(db, S):
    """PCS-D-11 — a component of a soft-deleted project answers 404 and stays.
    Rules: delete_component R1 [BUG-1278], Errors."""
    pd = proj(db, S, "Delta", deleted=True)
    cd = comp(db, pd, "Door", 11)
    pd_id, cd_id = pd.id, cd.id
    commit_point(db)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_component(
            db, component_id=cd_id, workspace_id=S.W1.id, user_id=S.U2.id
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NOPROJ(pd_id)
    # Then 4
    assert counts(db) == before


# [claude] PCS-D-12
def test_pcs_d_12__stray_component_projects_404(db, S):
    """PCS-D-12 — a W1 component whose project is in W2 answers the project's 404 (pass-through).
    Rules: delete_component R1 (manager require_component_access R4)."""
    cx = comp(db, S.P9, "Stray", 11, workspace_id=S.W1.id)
    cx_id, p9_id = cx.id, S.P9.id
    commit_point(db)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_component(
            db, component_id=cx_id, workspace_id=S.W1.id, user_id=S.U2.id
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NOPROJ(p9_id)
    # Then 4
    assert counts(db) == before


# [claude] PCS-D-13
@xfail("BUG-1196")
def test_pcs_d_13__live_work_order_blocks(db, S):
    """PCS-D-13 — a live work order blocks the delete.
    Rules: delete_component R2, R3 [BUG-1196]."""
    cr = cr_del(db, S)
    wt = wt1(db, S)
    o1 = wo(db, S, cr, "WO-1", wt)
    o1_id = o1.id
    commit_point(db)
    before_cr = snap(db, cr)
    # Then 1
    with pytest.raises(ValidationError) as exc:
        svc.delete_component(
            db, component_id=before_cr["id"], workspace_id=S.W1.id, user_id=S.UG.id
        )
    # Then 2
    assert exc.value.status_code == 400
    assert exc.value.detail == "Component has history"
    # Then 3
    assert exc.value.errors == [{"type": "work_order", "id": o1_id}]
    # Then 4
    assert not db.deleted and not db.dirty
    # Then 5
    assert reread(db, WorkOrder, o1_id).project_component_id == before_cr["id"]
    # Then 6
    assert unchanged(db, ProjectComponent, before_cr)
    # Then 7
    assert len(evs(db, S.PA.id, "component_deleted")) == 0


# [claude] PCS-D-14
@xfail("BUG-1196")
def test_pcs_d_14__deleted_work_order_still_blocks(db, S):
    """PCS-D-14 — a soft-deleted work order still blocks.
    Rules: delete_component R3 [BUG-1196]."""
    cr = cr_del(db, S)
    wt = wt1(db, S)
    o1 = wo(db, S, cr, "WO-1", wt, deleted=True)
    o1_id = o1.id
    commit_point(db)
    before_cr = snap(db, cr)
    # Then 1
    with pytest.raises(ValidationError) as exc:
        svc.delete_component(
            db, component_id=before_cr["id"], workspace_id=S.W1.id, user_id=S.UG.id
        )
    # Then 2
    assert exc.value.errors == [{"type": "work_order", "id": o1_id}]
    # Then 3
    assert not db.deleted and not db.dirty
    # Then 4
    assert unchanged(db, ProjectComponent, before_cr)
    # Then 5
    assert len(evs(db, S.PA.id, "component_deleted")) == 0


# [claude] PCS-D-15
@xfail("BUG-1196")
def test_pcs_d_15__ledger_row_blocks(db, S):
    """PCS-D-15 — a ledger row blocks the delete.
    Rules: delete_component R3 [BUG-1196]."""
    cr = cr_del(db, S)
    item = i1(db, S)
    lg = ledger(db, S, cr, item)
    lg_id = lg.id
    commit_point(db)
    before_cr = snap(db, cr)
    # Then 1
    with pytest.raises(ValidationError) as exc:
        svc.delete_component(
            db, component_id=before_cr["id"], workspace_id=S.W1.id, user_id=S.UG.id
        )
    # Then 2
    assert exc.value.errors == [{"type": "ledger_entry", "id": lg_id}]
    # Then 3
    assert not db.deleted and not db.dirty
    # Then 4
    assert (
        reread(db, ProjectComponentItemLedger, lg_id).project_component_id
        == before_cr["id"]
    )
    # Then 5
    assert unchanged(db, ProjectComponent, before_cr)
    # Then 6
    assert len(evs(db, S.PA.id, "component_deleted")) == 0


# [claude] PCS-D-16
@xfail("BUG-1196")
def test_pcs_d_16__item_line_blocks(db, S):
    """PCS-D-16 — an item line blocks the delete.
    Rules: delete_component R3 [BUG-1196]."""
    cr = cr_del(db, S)
    item = i1(db, S)
    l1 = line(db, S, cr, item)
    l1_id = l1.id
    commit_point(db)
    before_cr = snap(db, cr)
    # Then 1
    with pytest.raises(ValidationError) as exc:
        svc.delete_component(
            db, component_id=before_cr["id"], workspace_id=S.W1.id, user_id=S.UG.id
        )
    # Then 2
    assert exc.value.errors == [{"type": "component_item", "id": l1_id}]
    # Then 3
    assert not db.deleted and not db.dirty
    # Then 4
    assert (
        reread(db, ProjectComponentItem, l1_id).project_component_id == before_cr["id"]
    )
    # Then 5
    assert unchanged(db, ProjectComponent, before_cr)


# [claude] PCS-D-17
@xfail("BUG-1196")
def test_pcs_d_17__task_blocks(db, S):
    """PCS-D-17 — a task blocks the delete.
    Rules: delete_component R3 [BUG-1196]."""
    cr = cr_del(db, S)
    t1 = task(db, S, cr, "Paint")
    t1_id = t1.id
    commit_point(db)
    before_cr = snap(db, cr)
    # Then 1
    with pytest.raises(ValidationError) as exc:
        svc.delete_component(
            db, component_id=before_cr["id"], workspace_id=S.W1.id, user_id=S.UG.id
        )
    # Then 2
    assert exc.value.errors == [{"type": "task", "id": t1_id}]
    # Then 3
    assert not db.deleted and not db.dirty
    # Then 4
    assert (
        reread(db, ProjectComponentTask, t1_id).project_component_id == before_cr["id"]
    )
    # Then 5
    assert unchanged(db, ProjectComponent, before_cr)


# [claude] PCS-D-18
@xfail("BUG-1196")
def test_pcs_d_18__note_blocks_as_task(db, S):
    """PCS-D-18 — a note blocks the delete as a task.
    Rules: delete_component R3 [BUG-1196]."""
    cr = cr_del(db, S)
    n1 = task(db, S, cr, "Remember", note=True)
    n1_id = n1.id
    commit_point(db)
    before_cr = snap(db, cr)
    # Then 1
    with pytest.raises(ValidationError) as exc:
        svc.delete_component(
            db, component_id=before_cr["id"], workspace_id=S.W1.id, user_id=S.UG.id
        )
    # Then 2
    assert exc.value.errors == [{"type": "task", "id": n1_id}]
    # Then 3
    assert not db.deleted and not db.dirty
    # Then 4
    assert unchanged(db, ProjectComponent, before_cr)


# [claude] PCS-D-19
@xfail("BUG-1196")
def test_pcs_d_19__misc_cost_blocks(db, S):
    """PCS-D-19 — a miscellaneous cost blocks the delete.
    Rules: delete_component R3 [BUG-1196]."""
    cr = cr_del(db, S)
    mc = misc(db, S, cr)
    mc_id = mc.id
    commit_point(db)
    before_cr = snap(db, cr)
    # Then 1
    with pytest.raises(ValidationError) as exc:
        svc.delete_component(
            db, component_id=before_cr["id"], workspace_id=S.W1.id, user_id=S.UG.id
        )
    # Then 2
    assert exc.value.errors == [{"type": "misc_cost", "id": mc_id}]
    # Then 3
    assert not db.deleted and not db.dirty
    # Then 4
    assert (
        reread(db, MiscellaneousProjectCost, mc_id).project_component_id
        == before_cr["id"]
    )
    # Then 5
    assert unchanged(db, ProjectComponent, before_cr)


# [claude] PCS-D-20
@xfail("BUG-1196")
def test_pcs_d_20__other_activity_event_blocks(db, S):
    """PCS-D-20 — an activity event other than an attachment one blocks the delete.
    Rules: delete_component R3 [BUG-1196]."""
    cr = cr_del(db, S)
    a1 = act(db, S, cr, "work_order_item_used")
    act(db, S, cr, "attachment_added")
    a1_id = a1.id
    commit_point(db)
    before_cr = snap(db, cr)
    # Then 1
    with pytest.raises(ValidationError) as exc:
        svc.delete_component(
            db, component_id=before_cr["id"], workspace_id=S.W1.id, user_id=S.UG.id
        )
    # Then 2
    assert exc.value.errors == [{"type": "activity_event", "id": a1_id}]
    # Then 3
    assert not db.deleted and not db.dirty
    # Then 4
    assert (
        reread(db, ProjectComponentActivityEvent, a1_id).project_component_id
        == before_cr["id"]
    )
    # Then 5
    assert unchanged(db, ProjectComponent, before_cr)


# [claude] PCS-D-21
@xfail("BUG-1196")
def test_pcs_d_21__blockers_sorted_by_type_then_id(db, S):
    """PCS-D-21 — blockers are sorted by type, then id.
    Rules: delete_component R3 [BUG-1196]."""
    cr = cr_del(db, S)
    a1 = act(db, S, cr, "work_order_item_used")
    tb = task(db, S, cr, "Sand", id=XID(2))
    ta = task(db, S, cr, "Paint", id=XID(1))
    wt = wt1(db, S)
    o1 = wo(db, S, cr, "WO-1", wt)
    a1_id, ta_id, tb_id, o1_id = a1.id, ta.id, tb.id, o1.id
    commit_point(db)
    before_cr = snap(db, cr)
    # Then 1
    with pytest.raises(ValidationError) as exc:
        svc.delete_component(
            db, component_id=before_cr["id"], workspace_id=S.W1.id, user_id=S.UG.id
        )
    # Then 2
    assert exc.value.errors == [
        {"type": "work_order", "id": o1_id},
        {"type": "task", "id": ta_id},
        {"type": "task", "id": tb_id},
        {"type": "activity_event", "id": a1_id},
    ]
    # Then 3
    assert unchanged(db, ProjectComponent, before_cr)


# [claude] PCS-D-22
@xfail("BUG-1196")
def test_pcs_d_22__other_workspace_row_alone_refuses(db, S):
    """PCS-D-22 — a linked row of another workspace alone refuses, shown as one generic entry.
    Rules: delete_component R4 [BUG-1196]."""
    cr = cr_del(db, S)
    task(db, S, cr, "Paint", workspace_id=S.W2.id)
    commit_point(db)
    before_cr = snap(db, cr)
    # Then 1
    with pytest.raises(ValidationError) as exc:
        svc.delete_component(
            db, component_id=before_cr["id"], workspace_id=S.W1.id, user_id=S.UG.id
        )
    # Then 2
    assert exc.value.errors == [{"type": "other_workspace"}]
    # Then 3
    assert not db.deleted and not db.dirty
    # Then 4
    assert unchanged(db, ProjectComponent, before_cr)


# [claude] PCS-D-23
@xfail("BUG-1196")
def test_pcs_d_23__w0_and_w2_rows_one_entry_last(db, S):
    """PCS-D-23 — rows of W0 and W2 give one other_workspace entry, last.
    Rules: delete_component R3, R4 [BUG-1196]."""
    cr = cr_del(db, S)
    task(db, S, cr, "Prime", workspace_id=S.W0.id)
    t1 = task(db, S, cr, "Paint")
    task(db, S, cr, "Sand", workspace_id=S.W2.id)
    t1_id = t1.id
    commit_point(db)
    before_cr = snap(db, cr)
    # Then 1
    with pytest.raises(ValidationError) as exc:
        svc.delete_component(
            db, component_id=before_cr["id"], workspace_id=S.W1.id, user_id=S.UG.id
        )
    # Then 2
    assert exc.value.errors == [
        {"type": "task", "id": t1_id},
        {"type": "other_workspace"},
    ]
    # Then 3
    assert unchanged(db, ProjectComponent, before_cr)


# [claude] PCS-D-24
@xfail("BUG-1196")
def test_pcs_d_24__refused_delete_rolls_back_once(db, S):
    """PCS-D-24 — a refused delete rolls back once and discards the session's other changes.
    Rules: delete_component R2 [BUG-1196], CT3."""
    cr = cr_del(db, S)
    task(db, S, cr, "Paint")
    commit_point(db)
    before_cr = snap(db, cr)
    before = counts(db)
    x_id = extra_x(db, S)
    # Then 1
    with pytest.raises(ValidationError):
        with spies(db) as (cm, rb):
            svc.delete_component(
                db, component_id=before_cr["id"], workspace_id=S.W1.id, user_id=S.UG.id
            )
    # Then 2
    assert rb.call_count == 1
    assert cm.call_count == 0
    # Then 3
    assert x_count(db, x_id) == 0
    # Then 4
    assert unchanged(db, ProjectComponent, before_cr)
    # Then 5
    assert counts(db) == before


# [claude] PCS-D-25
def test_pcs_d_25__failing_commit_component_stays(db, S):
    """PCS-D-25 — a failing commit rolls back once and the component stays.
    Rules: delete_component R7, CT4."""
    cr = cr_del(db, S)
    commit_point(db)
    before_cr = snap(db, cr)
    before = counts(db)
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.delete_component(
                db, component_id=before_cr["id"], workspace_id=S.W1.id, user_id=S.UG.id
            )
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count == 1
    # Then 3
    assert unchanged(db, ProjectComponent, before_cr)
    # Then 4
    assert counts(db) == before


# [claude] PCS-D-26
@xfail("BUG-1196")
def test_pcs_d_26__capitalised_attachment_added_blocks(db, S):
    """PCS-D-26 — an activity event spelled "Attachment_added" blocks (exact compare).
    Rules: delete_component R3 [BUG-1196]."""
    cr = cr_del(db, S)
    a1 = act(db, S, cr, "Attachment_added")
    a1_id = a1.id
    commit_point(db)
    before_cr = snap(db, cr)
    # Then 1
    with pytest.raises(ValidationError) as exc:
        svc.delete_component(
            db, component_id=before_cr["id"], workspace_id=S.W1.id, user_id=S.UG.id
        )
    # Then 2
    assert exc.value.errors == [{"type": "activity_event", "id": a1_id}]
    # Then 3
    assert not db.deleted and not db.dirty
    # Then 4
    assert (
        reread(db, ProjectComponentActivityEvent, a1_id).event_type
        == "Attachment_added"
    )
    # Then 5
    assert unchanged(db, ProjectComponent, before_cr)


# [claude] PCS-D-27
@xfail("BUG-1196")
def test_pcs_d_27__trailing_space_attachment_added_blocks(db, S):
    """PCS-D-27 — an activity event spelled "attachment_added " (trailing space) blocks (exact compare).
    Rules: delete_component R3 [BUG-1196]."""
    cr = cr_del(db, S)
    a1 = act(db, S, cr, "attachment_added ")
    a1_id = a1.id
    commit_point(db)
    before_cr = snap(db, cr)
    # Then 1
    with pytest.raises(ValidationError) as exc:
        svc.delete_component(
            db, component_id=before_cr["id"], workspace_id=S.W1.id, user_id=S.UG.id
        )
    # Then 2
    assert exc.value.errors == [{"type": "activity_event", "id": a1_id}]
    # Then 3
    assert not db.deleted and not db.dirty
    # Then 4
    assert (
        reread(db, ProjectComponentActivityEvent, a1_id).event_type
        == "attachment_added "
    )
    # Then 5
    assert unchanged(db, ProjectComponent, before_cr)


# [claude] PCS-D-28
@xfail("BUG-1196")
def test_pcs_d_28__attachment_add_blocks(db, S):
    """PCS-D-28 — an activity event spelled "attachment_add" blocks (exact compare).
    Rules: delete_component R3 [BUG-1196]."""
    cr = cr_del(db, S)
    a1 = act(db, S, cr, "attachment_add")
    a1_id = a1.id
    commit_point(db)
    before_cr = snap(db, cr)
    # Then 1
    with pytest.raises(ValidationError) as exc:
        svc.delete_component(
            db, component_id=before_cr["id"], workspace_id=S.W1.id, user_id=S.UG.id
        )
    # Then 2
    assert exc.value.errors == [{"type": "activity_event", "id": a1_id}]
    # Then 3
    assert not db.deleted and not db.dirty
    # Then 4
    assert (
        reread(db, ProjectComponentActivityEvent, a1_id).event_type == "attachment_add"
    )
    # Then 5
    assert unchanged(db, ProjectComponent, before_cr)
