"""Unit tests for app/services/project_component_item_service.py.

Implements tests/unit/services/project_component_item_service.cases.md
(revision 2), one test per card, in card order. Real Postgres session (`db`
fixture): a `commit()` only releases a savepoint, so the service's commits are
safe and the fixture's outer rollback discards everything. Nothing is patched
except the commit / rollback spies and the failing commit / failing refresh of
the cards that name them (Conventions, Named checks).

Normal mode: every test is written from its card and carries a `# [claude] <ID>`
comment. Standing rows live on fixture `S` (`S.W1`, `S.UG`, `S.C1`, `S.I1` ...);
`# Then N` marks the checks of the card's Then line N.
"""

# ruff: noqa: SIM117, DTZ001, C408  (Conventions prescribe nested `with` blocks and naive datetimes; the bulk-insert Given step is written as the card writes it)
import os
from contextlib import contextmanager
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import event, func, insert, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import DataError

from app.models.factory import Factory
from app.models.item import Item
from app.models.project import Project
from app.models.project_component import ProjectComponent
from app.models.project_component_item import ProjectComponentItem
from app.models.project_event import ProjectEvent
from app.models.project_member import ProjectMember
from app.models.workspace_member import WorkspaceMember
from app.schemas.project_component_item import (
    ProjectComponentItemCreate,
    ProjectComponentItemUpdate,
)
from app.services.project_component_item_service import (
    project_component_item_service,
)
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

svc = project_component_item_service

MISSING = 999999999
T0 = datetime(2025, 12, 1, 8, 0, 0)
MAXQ = 2147483647
NOCOMP = "Project component not found"
NOACCESS = "You do not have access to this project"

BUG_1012 = "BUG-1012: Project component accepts another workspace's item"
BUG_1278 = "BUG-1278: The members and components of a deleted project stay open"
BUG_2306 = "BUG-2306: A deleted item can be planned on a project component"
BUG_2307 = "BUG-2307: Planned item quantity can be zero, negative or out of range"
BUG_2308 = "BUG-2308: Workspace-wide component item list drops hidden rows after paging"
BUG_2309 = (
    "BUG-2309: `project_component_id=0` lists every planned item of the workspace"
)
BUG_2310 = 'BUG-2310: Saving an item line unchanged writes "Updated component item"'


# Convention "XID(k)"
def XID(k):
    return 800_000_000 + (os.getpid() % 1_000_000) * 10 + k


def _add(db, row):
    db.add(row)
    db.flush()
    return row


# --------------------------------------------------------------------------- #
# Conventions -> standing rows (every test, in this order)
# --------------------------------------------------------------------------- #


@pytest.fixture
def S(db):
    s = SimpleNamespace()
    s.W0 = make_workspace(db)
    s.W1 = make_workspace(db)
    s.W2 = make_workspace(db)
    s.U1 = make_profile(db, name="Ana Rahman")
    s.U2 = make_profile(db, name="Bilal Khan")
    s.UG = make_profile(db, name="Mia Khan")
    for u, role in ((s.U1, "ground-team"), (s.U2, "owner"), (s.UG, "ground-team")):
        _add(
            db,
            WorkspaceMember(
                workspace_id=s.W1.id, user_id=u.id, role=role, status="active"
            ),
        )
    s.F0 = _add(
        db, Factory(workspace_id=s.W0.id, name="Factory Zero", abbreviation="F0")
    )
    s.F1 = _add(
        db, Factory(workspace_id=s.W1.id, name="Factory One", abbreviation="F1")
    )
    s.F9 = _add(
        db, Factory(workspace_id=s.W2.id, name="Factory Nine", abbreviation="F9")
    )

    def proj(ws, f, name, **over):
        return _add(
            db,
            Project(
                workspace_id=ws.id,
                factory_id=f.id,
                name=name,
                description="Main",
                created_by=s.U1.id,
                **over,
            ),
        )

    s.PJ0 = proj(s.W0, s.F0, "Project Zero")
    s.PJ1 = proj(s.W1, s.F1, "Project One", id=XID(1))
    s.PJP = proj(s.W1, s.F1, "Secret", visibility="invited_only")
    s.PJD = proj(s.W1, s.F1, "Gone", is_deleted=True, deleted_at=T0, deleted_by=s.U1.id)
    s.PJ9 = proj(s.W2, s.F9, "Project Nine")

    def comp(ws, p, name, **over):
        return _add(
            db,
            ProjectComponent(workspace_id=ws.id, project_id=p.id, name=name, **over),
        )

    s.C0 = comp(s.W0, s.PJ0, "Cellar")
    s.C1 = comp(s.W1, s.PJ1, "Roof", id=XID(5))
    s.C2 = comp(s.W1, s.PJ1, "Wall")
    s.CP = comp(s.W1, s.PJP, "Vault")
    s.CD = comp(s.W1, s.PJD, "Floor")
    s.C9 = comp(s.W2, s.PJ9, "Deck")

    def item(ws, name, norm, **over):
        return _add(
            db,
            Item(
                workspace_id=ws.id, name=name, name_normalized=norm, unit="pcs", **over
            ),
        )

    s.I0 = item(s.W0, "Nut", "nut")
    s.I1 = item(s.W1, "Bolt", "bolt", id=XID(8))
    s.I9 = item(s.W2, "Washer", "washer")
    s.IDL = item(s.W1, "Old bolt", "old bolt", is_active=False)
    return s


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #


# Given row "line(C, q)"; `over` = the columns after "but"
def line(db, S, c, q, **over):
    fields = {
        "workspace_id": c.workspace_id,
        "project_component_id": c.id,
        "item_id": S.I1.id,
        "qty": q,
    }
    fields.update(over)
    return _add(db, ProjectComponentItem(**fields))


# Given row "L0" (W0 line on C0 with I0; qty 1, or the card's qty)
def line0(db, S, qty=1):
    return _add(
        db,
        ProjectComponentItem(
            workspace_id=S.W0.id, project_component_id=S.C0.id, item_id=S.I0.id, qty=qty
        ),
    )


# Given row "L9" (W2 line on C9 with I9; qty 1, or the card's qty)
def line9(db, S, qty=1):
    return _add(
        db,
        ProjectComponentItem(
            workspace_id=S.W2.id, project_component_id=S.C9.id, item_id=S.I9.id, qty=qty
        ),
    )


# Given row "pmem(P, U)"
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


# Convention "commit point"
def commit_point(db):
    db.commit()


# Convention "extra row X" (after the commit point, flushed, not committed)
def extra_x(db, S):
    x = _add(
        db,
        ProjectComponentItem(
            workspace_id=S.W2.id, project_component_id=S.C9.id, item_id=S.I9.id, qty=1
        ),
    )
    return x.id


# Convention "pending P" (after the commit point, no flush)
def pending_p(db, S):
    p = ProjectComponentItem(
        workspace_id=S.W2.id, project_component_id=S.C9.id, item_id=S.I9.id, qty=2
    )
    db.add(p)
    return p


# --------------------------------------------------------------------------- #
# Conventions -> named checks
# --------------------------------------------------------------------------- #


def _columns(model):
    return [c.key for c in sa_inspect(model).mapper.column_attrs]


# Convention "re-read X"
def reread(db, model, row_id):
    db.expire_all()
    return db.get(model, row_id)


# Convention "unchanged(X)": snapshot at the commit point
def snap(db, row):
    db.refresh(row)
    return {k: getattr(row, k) for k in _columns(type(row))}


def unchanged(db, model, before):
    fresh = reread(db, model, before["id"])
    return (
        fresh is not None and {k: getattr(fresh, k) for k in _columns(model)} == before
    )


# Convention "nothing written": project_component_items and project_events rows
def counts(db):
    return tuple(
        db.scalar(select(func.count()).select_from(m))
        for m in (ProjectComponentItem, ProjectEvent)
    )


# Convention "no stock": inventory, machine_items, project_component_item_ledger rows
def stock(db):
    return tuple(
        db.execute(text(f"SELECT count(*) FROM {t}")).scalar()
        for t in ("inventory", "machine_items", "project_component_item_ledger")
    )


# Convention "x_gone"
def x_gone(db, x_id):
    return (
        db.scalar(
            select(func.count())
            .select_from(ProjectComponentItem)
            .where(ProjectComponentItem.id == x_id)
        )
        == 0
    )


# Convention "events(P, t)" / "all_events(P)"
def events(db, p_id, t=None):
    db.expire_all()
    q = select(ProjectEvent).where(ProjectEvent.project_id == p_id)
    if t is not None:
        q = q.where(ProjectEvent.event_type == t)
    return db.execute(q.order_by(ProjectEvent.id)).scalars().all()


# Convention "idset(r)"
def idset(rows):
    return {x.id for x in rows}


# Convention "committed:" lines: fresh query (after the one test rollback)
def committed_row(db, row_id):
    return db.execute(
        select(ProjectComponentItem).where(ProjectComponentItem.id == row_id)
    ).scalar_one_or_none()


def committed_lines_of(db, c_id):
    return (
        db.execute(
            select(ProjectComponentItem).where(
                ProjectComponentItem.project_component_id == c_id
            )
        )
        .scalars()
        .all()
    )


# Convention "spies"
@contextmanager
def spies(db):
    with (
        patch.object(db, "commit", wraps=db.commit) as cm,
        patch.object(db, "rollback", wraps=db.rollback) as rb,
    ):
        yield cm, rb


# Convention "failing commit" (inside the test's pytest.raises(RuntimeError))
@contextmanager
def failing_commit(db):
    with (
        patch.object(db, "commit", side_effect=RuntimeError("boom")),
        patch.object(db, "rollback", wraps=db.rollback) as rb,
    ):
        yield rb


# Convention "failing refresh" (inside the test's pytest.raises(RuntimeError))
@contextmanager
def failing_refresh(db):
    with patch.object(db, "refresh", side_effect=RuntimeError("boom")):
        yield


# Given step "recorder"
def recorder(db):
    stmts = []

    def rec(conn, cursor, statement, params, context, executemany):
        stmts.append(statement)

    conn = db.connection()
    event.listen(conn, "before_cursor_execute", rec)
    return stmts, lambda: event.remove(conn, "before_cursor_execute", rec)


# =========================================================================== #
# ProjectComponentItemService.get_items
# =========================================================================== #


# [claude] PCIS-L-01
def test_pcis_l_01__component_lines_only(db, S):
    """PCIS-L-01 — with a component: that component's lines only.
    Rules: `get_items` R1; `_guard_component` R1"""
    LA = line(db, S, S.C1, 5)
    LB = line(db, S, S.C1, 2)
    line(db, S, S.C2, 7)
    result = svc.get_items(
        db,
        workspace_id=S.W1.id,
        user_id=S.UG.id,
        project_component_id=S.C1.id,
        limit=1000,
    )
    # Then 1
    assert idset(result) == {LA.id, LB.id}


# [claude] PCIS-L-02
@pytest.mark.xfail(strict=True, reason=BUG_2309)
def test_pcis_l_02__component_id_0_is_404(db, S):
    """PCIS-L-02 — component id 0 is a component id: 404.
    Rules: `get_items` R1 [BUG-2309]"""
    line(db, S, S.C1, 5)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_items(db, workspace_id=S.W1.id, user_id=S.U2.id, project_component_id=0)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NOCOMP


# [claude] PCIS-L-03
def test_pcis_l_03__private_component_403_no_rollback(db, S):
    """PCIS-L-03 — a private component the caller may not open is 403, with no rollback.
    Rules: `get_items` R1, R5; I-TC6"""
    line(db, S, S.CP, 3)
    commit_point(db)
    w1_id, ug_id, cp_id = S.W1.id, S.UG.id, S.CP.id
    P = pending_p(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            svc.get_items(
                db, workspace_id=w1_id, user_id=ug_id, project_component_id=cp_id
            )
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == NOACCESS
    # Then 4
    assert rb.call_count == 0
    # Then 5
    assert P in db.new


# [claude] PCIS-L-04
def test_pcis_l_04__w0_component_404_in_w1(db, S):
    """PCIS-L-04 — a W0 component is 404 in W1.
    Rules: `get_items` R1"""
    line0(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_items(
            db, workspace_id=S.W1.id, user_id=S.U2.id, project_component_id=S.C0.id
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NOCOMP


# [claude] PCIS-L-05
@pytest.mark.xfail(strict=True, reason=BUG_1278)
def test_pcis_l_05__deleted_projects_component_404(db, S):
    """PCIS-L-05 — a deleted project's component is 404 for the project (pass-through).
    Rules: `get_items` R1 (manager `require_component_access` R2 [BUG-1278])"""
    line(db, S, S.CD, 4)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_items(
            db, workspace_id=S.W1.id, user_id=S.U2.id, project_component_id=S.CD.id
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project with ID {S.PJD.id} not found"


# [claude] PCIS-L-06
def test_pcis_l_06__workspace_wide_privileged_caller(db, S):
    """PCIS-L-06 — without a component: every W1 line a privileged caller may open, no other workspace.
    Rules: `get_items` R2; `_filter_accessible_items` R1"""
    line0(db, S)
    LA = line(db, S, S.C1, 5)
    LP = line(db, S, S.CP, 3)
    line9(db, S)
    result = svc.get_items(db, workspace_id=S.W1.id, user_id=S.U2.id, limit=1000)
    # Then 1
    assert idset(result) == {LA.id, LP.id}


# [claude] PCIS-L-07
def test_pcis_l_07__plain_caller_does_not_see_private_lines(db, S):
    """PCIS-L-07 — without a component: a plain caller does not see a private project's lines.
    Rules: `_filter_accessible_items` R1"""
    line(db, S, S.CP, 3)
    LA = line(db, S, S.C1, 5)
    result = svc.get_items(db, workspace_id=S.W1.id, user_id=S.UG.id, limit=1000)
    # Then 1
    assert idset(result) == {LA.id}


# [claude] PCIS-L-08
def test_pcis_l_08__other_private_membership_does_not_open_this_one(db, S):
    """PCIS-L-08 — membership of another private project does not open this one.
    Rules: `_filter_accessible_items` R1"""
    PJQ = _add(
        db,
        Project(
            workspace_id=S.W1.id,
            factory_id=S.F1.id,
            name="Other secret",
            description="Main",
            created_by=S.U1.id,
            visibility="invited_only",
        ),
    )
    CQ = _add(
        db, ProjectComponent(workspace_id=S.W1.id, project_id=PJQ.id, name="Annex")
    )
    pmem(db, S, PJQ, S.UG)
    LQ = line(db, S, CQ, 6)
    line(db, S, S.CP, 3)
    result = svc.get_items(db, workspace_id=S.W1.id, user_id=S.UG.id, limit=1000)
    # Then 1
    assert idset(result) == {LQ.id}


# [claude] PCIS-L-09
def test_pcis_l_09__w1_line_on_w2_component_left_out(db, S):
    """PCIS-L-09 — a W1 line on a W2 component is left out.
    Rules: `get_items` R6; `_filter_accessible_items` R1"""
    LA = line(db, S, S.C1, 5)
    line(db, S, S.C9, 1, workspace_id=S.W1.id)
    result = svc.get_items(db, workspace_id=S.W1.id, user_id=S.U2.id, limit=1000)
    # Then 1
    assert idset(result) == {LA.id}


# [claude] PCIS-L-10
def test_pcis_l_10__w1_component_with_w2_project_left_out(db, S):
    """PCIS-L-10 — a line on a W1 component whose project is in W2 is left out.
    Rules: `_filter_accessible_items` R1"""
    CX = _add(
        db, ProjectComponent(workspace_id=S.W1.id, project_id=S.PJ9.id, name="Stray")
    )
    LA = line(db, S, S.C1, 5)
    line(db, S, CX, 1)
    result = svc.get_items(db, workspace_id=S.W1.id, user_id=S.U2.id, limit=1000)
    # Then 1
    assert idset(result) == {LA.id}


# [claude] PCIS-L-11
@pytest.mark.xfail(strict=True, reason=BUG_1278)
def test_pcis_l_11__deleted_projects_lines_not_listed(db, S):
    """PCIS-L-11 — lines of a deleted project are not listed.
    Rules: `get_items` R3; `_filter_accessible_items` R2 [BUG-1278]"""
    line(db, S, S.CD, 4)
    LA = line(db, S, S.C1, 5)
    result = svc.get_items(db, workspace_id=S.W1.id, user_id=S.U2.id, limit=1000)
    # Then 1
    assert idset(result) == {LA.id}


# [claude] PCIS-L-12
@pytest.mark.xfail(strict=False, reason=BUG_2308) # physical order can put the filtered-out row off the page (order sweep 2026-11-27)
def test_pcis_l_12__hidden_lines_do_not_shorten_the_page(db, S):
    """PCIS-L-12 — hidden lines ahead of the page do not shorten it (limit).
    Rules: `get_items` R4 [BUG-2308]"""
    line(db, S, S.CP, 1)
    line(db, S, S.CP, 2)
    line(db, S, S.CP, 3)
    VD = line(db, S, S.C1, 4)
    VE = line(db, S, S.C1, 5)
    result = svc.get_items(db, workspace_id=S.W1.id, user_id=S.UG.id, skip=0, limit=2)
    # Then 1
    assert idset(result) == {VD.id, VE.id}


# [claude] PCIS-L-13
@pytest.mark.xfail(strict=False, reason=BUG_2308)
def test_pcis_l_13__hidden_lines_do_not_shift_the_page(db, S):
    """PCIS-L-13 — hidden lines ahead of the page do not shift it (skip).
    Rules: `get_items` R4 [BUG-2308]"""
    line(db, S, S.CP, 1)
    line(db, S, S.CP, 2)
    line(db, S, S.CP, 3)
    line(db, S, S.C1, 4)
    VE = line(db, S, S.C1, 5)
    result = svc.get_items(
        db, workspace_id=S.W1.id, user_id=S.UG.id, skip=1, limit=1000
    )
    # Then 1
    assert idset(result) == {VE.id}


# [claude] PCIS-L-14
@pytest.mark.xfail(strict=True, reason=BUG_2308)
def test_pcis_l_14__filter_does_not_read_one_component_per_row(db, S):
    """PCIS-L-14 — the access filter does not read one component per row.
    Rules: `get_items` R4 [BUG-2308]"""
    ks = [
        _add(
            db,
            ProjectComponent(workspace_id=S.W1.id, project_id=S.PJ1.id, name=f"K{n}"),
        )
        for n in range(1, 6)
    ]
    for k in ks:
        line(db, S, k, 1)
    w1_id, ug_id = S.W1.id, S.UG.id
    stmts, stop = recorder(db)
    result = svc.get_items(db, workspace_id=w1_id, user_id=ug_id, limit=1000)
    stop()
    # Then 1
    assert len(result) == 5
    # Then 2
    assert sum(1 for s in stmts if "project_components" in s) <= 1


# [claude] PCIS-L-15
def test_pcis_l_15__limit_0_gives_empty_list(db, S):
    """PCIS-L-15 — limit 0 gives an empty list.
    Rules: `get_items` R7"""
    line(db, S, S.C1, 5)
    result = svc.get_items(db, workspace_id=S.W1.id, user_id=S.U2.id, limit=0)
    # Then 1
    assert result == []


# [claude] PCIS-L-16
def test_pcis_l_16__default_limit_is_100(db, S):
    """PCIS-L-16 — the default limit is 100.
    Rules: `get_items` R7"""
    db.execute(
        insert(ProjectComponentItem),
        [
            dict(
                workspace_id=S.W1.id,
                project_component_id=S.C1.id,
                item_id=S.I1.id,
                qty=1,
            )
            for i in range(101)
        ],
    )
    db.expire_all()
    result = svc.get_items(db, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 1
    assert len(result) == 100


# [claude] PCIS-L-17
def test_pcis_l_17__negative_limit_fails_in_database(db, S):
    """PCIS-L-17 — a negative limit fails in the database.
    Rules: `get_items` R7"""
    line(db, S, S.C1, 5)
    # Then 1
    with pytest.raises(DataError):
        with db.begin_nested():
            svc.get_items(db, workspace_id=S.W1.id, user_id=S.U2.id, limit=-1)


# [claude] PCIS-L-18
def test_pcis_l_18__negative_skip_fails_in_database(db, S):
    """PCIS-L-18 — a negative skip fails in the database.
    Rules: `get_items` R7"""
    line(db, S, S.C1, 5)
    # Then 1
    with pytest.raises(DataError):
        with db.begin_nested():
            svc.get_items(db, workspace_id=S.W1.id, user_id=S.U2.id, skip=-1)


# [claude] PCIS-L-19
def test_pcis_l_19__workspace_wide_read_no_commit_no_rollback(db, S):
    """PCIS-L-19 — the workspace-wide read neither commits nor rolls back.
    Rules: `get_items` R5; I-TC6"""
    LA = line(db, S, S.C1, 5)
    commit_point(db)
    la_id, w1_id, u2_id = LA.id, S.W1.id, S.U2.id
    P = pending_p(db, S)
    with spies(db) as (cm, rb):
        result = svc.get_items(db, workspace_id=w1_id, user_id=u2_id, limit=1000)
    # Then 1
    assert idset(result) == {la_id}
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert P in db.new


# [claude] PCIS-L-20
def test_pcis_l_20__one_component_read_no_commit_no_rollback(db, S):
    """PCIS-L-20 — a successful one-component read neither commits nor rolls back.
    Rules: `get_items` R1, R5; I-TC6"""
    LA = line(db, S, S.C1, 5)
    commit_point(db)
    la_id, w1_id, ug_id, c1_id = LA.id, S.W1.id, S.UG.id, S.C1.id
    P = pending_p(db, S)
    with spies(db) as (cm, rb):
        result = svc.get_items(
            db,
            workspace_id=w1_id,
            user_id=ug_id,
            project_component_id=c1_id,
            limit=1000,
        )
    # Then 1
    assert idset(result) == {la_id}
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert P in db.new


# =========================================================================== #
# ProjectComponentItemService.get_by_id
# =========================================================================== #


# [claude] PCIS-G-01
def test_pcis_g_01__openable_line_returned(db, S):
    """PCIS-G-01 — a line the caller may open is returned.
    Rules: `get_by_id` R2"""
    LA = line(db, S, S.C1, 5)
    result = svc.get_by_id(db, item_id=LA.id, workspace_id=S.W1.id, user_id=S.UG.id)
    # Then 1
    assert result.id == LA.id
    assert result.qty == 5


# [claude] PCIS-G-02
def test_pcis_g_02__unknown_id_none_no_commit_no_rollback(db, S):
    """PCIS-G-02 — an unknown id is None, with no commit and no rollback.
    Rules: `get_by_id` R1, R3; I-TC6"""
    line(db, S, S.C1, 5)
    commit_point(db)
    w1_id, ug_id = S.W1.id, S.UG.id
    P = pending_p(db, S)
    with spies(db) as (cm, rb):
        result = svc.get_by_id(db, item_id=MISSING, workspace_id=w1_id, user_id=ug_id)
    # Then 1
    assert result is None
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert P in db.new


# [claude] PCIS-G-03
def test_pcis_g_03__id_0_is_none(db, S):
    """PCIS-G-03 — id 0 is None.
    Rules: `get_by_id` R1"""
    line(db, S, S.C1, 5)
    result = svc.get_by_id(db, item_id=0, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 1
    assert result is None


# [claude] PCIS-G-04
def test_pcis_g_04__w0_line_none_in_w1(db, S):
    """PCIS-G-04 — a W0 line (lower id) is None in W1.
    Rules: `get_by_id` R1"""
    L0 = line0(db, S)
    line(db, S, S.C1, 5)
    result = svc.get_by_id(db, item_id=L0.id, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 1
    assert result is None


# [claude] PCIS-G-05
def test_pcis_g_05__w2_line_none_in_w1(db, S):
    """PCIS-G-05 — a W2 line (higher id) is None in W1.
    Rules: `get_by_id` R1"""
    line(db, S, S.C1, 5)
    L9 = line9(db, S)
    result = svc.get_by_id(db, item_id=L9.id, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 1
    assert result is None


# [claude] PCIS-G-06
def test_pcis_g_06__private_line_403_no_rollback(db, S):
    """PCIS-G-06 — a private project's line is 403 for a plain caller, with no rollback.
    Rules: `get_by_id` R2, R3"""
    LP = line(db, S, S.CP, 3)
    commit_point(db)
    lp_id, w1_id, ug_id = LP.id, S.W1.id, S.UG.id
    P = pending_p(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_by_id(db, item_id=lp_id, workspace_id=w1_id, user_id=ug_id)
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == NOACCESS
    # Then 4
    assert P in db.new


# [claude] PCIS-G-07
def test_pcis_g_07__privileged_caller_opens_private_line(db, S):
    """PCIS-G-07 — a privileged caller opens a private project's line.
    Rules: `get_by_id` R2"""
    LP = line(db, S, S.CP, 3)
    result = svc.get_by_id(db, item_id=LP.id, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 1
    assert result.id == LP.id


# [claude] PCIS-G-08
@pytest.mark.xfail(strict=True, reason=BUG_1278)
def test_pcis_g_08__deleted_projects_line_404(db, S):
    """PCIS-G-08 — a deleted project's line is 404 (pass-through).
    Rules: `get_by_id` R2 (manager `require_component_access` R2 [BUG-1278])"""
    LD = line(db, S, S.CD, 4)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_by_id(db, item_id=LD.id, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project with ID {S.PJD.id} not found"


# [claude] PCIS-G-09
def test_pcis_g_09__one_row_read_no_commit_no_rollback(db, S):
    """PCIS-G-09 — a successful one-row read neither commits nor rolls back.
    Rules: `get_by_id` R2, R3; I-TC6"""
    LA = line(db, S, S.C1, 5)
    commit_point(db)
    la_id, w1_id, ug_id = LA.id, S.W1.id, S.UG.id
    P = pending_p(db, S)
    with spies(db) as (cm, rb):
        result = svc.get_by_id(db, item_id=la_id, workspace_id=w1_id, user_id=ug_id)
    # Then 1
    assert result.id == la_id
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert P in db.new


# =========================================================================== #
# ProjectComponentItemService.create_component_item
# =========================================================================== #


def _create_in(component_id, item_id, qty):
    return ProjectComponentItemCreate(
        project_component_id=component_id, item_id=item_id, qty=qty
    )


# [claude] PCIS-C-01
def test_pcis_c_01__line_stored_committed_once_no_stock_moves(db, S):
    """PCIS-C-01 — the line is stored, committed once and returned re-read; no stock moves.
    Rules: `create_component_item` R5, R7; I-TC1, I-TC2"""
    commit_point(db)
    before_stock = stock(db)
    w1_id, c1_id, i1_id, ug_id = S.W1.id, S.C1.id, S.I1.id, S.UG.id
    with spies(db) as (cm, rb):
        result = svc.create_component_item(
            db,
            item_in=ProjectComponentItemCreate(
                project_component_id=c1_id, item_id=i1_id, qty=5
            ),
            workspace_id=w1_id,
            user_id=ug_id,
        )
    # Then 1
    assert result.id is not None
    assert result.qty == 5
    # Then 2
    assert cm.call_count == 1
    # Then 3
    assert rb.call_count == 0
    # Then 4
    rid = result.id
    db.rollback()
    row = committed_row(db, rid)
    assert row.workspace_id == w1_id
    assert row.project_component_id == c1_id
    assert row.item_id == i1_id
    assert row.qty == 5
    # Then 5
    assert stock(db) == before_stock


# [claude] PCIS-C-02
def test_pcis_c_02__create_logs_item_added_with_catalog_id(db, S):
    """PCIS-C-02 — creating a line logs item_added with the catalog item id.
    Rules: `create_component_item` R6"""
    commit_point(db)
    w1_id, c1_id, i1_id, ug_id, pj1_id = S.W1.id, S.C1.id, S.I1.id, S.UG.id, S.PJ1.id
    result = svc.create_component_item(
        db,
        item_in=ProjectComponentItemCreate(
            project_component_id=c1_id, item_id=i1_id, qty=5
        ),
        workspace_id=w1_id,
        user_id=ug_id,
    )
    # Then 1
    assert result.id is not None
    # Then 2
    evs = events(db, pj1_id, "item_added")
    assert len(evs) == 1
    # Then 3
    assert evs[0].workspace_id == w1_id
    assert evs[0].performed_by == ug_id
    assert evs[0].description == "Added item to component (qty 5)"
    # Then 4
    assert evs[0].metadata_json == {
        "item_id": i1_id,
        "qty": "5",
        "component_id": c1_id,
        "component_name": "Roof",
    }
    # Then 5
    assert len(events(db, pj1_id)) == 1


# [claude] PCIS-C-03
def test_pcis_c_03__same_item_planned_twice(db, S):
    """PCIS-C-03 — the same item may be planned twice on one component.
    Rules: `create_component_item` R5 (D2)"""
    LA = line(db, S, S.C1, 5)
    commit_point(db)
    la_id, c1_id, i1_id = LA.id, S.C1.id, S.I1.id
    result = svc.create_component_item(
        db,
        item_in=ProjectComponentItemCreate(
            project_component_id=c1_id, item_id=i1_id, qty=2
        ),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.id != la_id
    # Then 2
    db.rollback()
    rows = committed_lines_of(db, c1_id)
    assert len([r for r in rows if r.item_id == i1_id]) == 2


# [claude] PCIS-C-04
def test_pcis_c_04__private_component_403_rolled_back_once(db, S):
    """PCIS-C-04 — a private component: 403, rolled back once, pending changes discarded.
    Rules: `create_component_item` R1; I-TC3"""
    commit_point(db)
    before = counts(db)
    w1_id, cp_id, i1_id, ug_id = S.W1.id, S.CP.id, S.I1.id, S.UG.id
    x_id = extra_x(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            svc.create_component_item(
                db,
                item_in=ProjectComponentItemCreate(
                    project_component_id=cp_id, item_id=i1_id, qty=5
                ),
                workspace_id=w1_id,
                user_id=ug_id,
            )
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == NOACCESS
    # Then 4
    assert rb.call_count == 1
    # Then 5
    assert not db.new
    # Then 6
    assert x_gone(db, x_id)
    # Then 7
    assert counts(db) == before


# [claude] PCIS-C-05
def test_pcis_c_05__private_component_with_foreign_item_403(db, S):
    """PCIS-C-05 — a private component with a foreign item answers 403: the guard runs first.
    Rules: `create_component_item` R2"""
    commit_point(db)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_component_item(
            db,
            item_in=_create_in(S.CP.id, S.I9.id, 5),
            workspace_id=S.W1.id,
            user_id=S.UG.id,
        )
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == NOACCESS
    # Then 4
    assert counts(db) == before


# [claude] PCIS-C-06
def test_pcis_c_06__unknown_component_404_nothing_written(db, S):
    """PCIS-C-06 — an unknown component is 404, nothing written.
    Rules: `create_component_item` R1"""
    commit_point(db)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_component_item(
            db,
            item_in=_create_in(MISSING, S.I1.id, 5),
            workspace_id=S.W1.id,
            user_id=S.U2.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NOCOMP
    # Then 4
    assert not db.new
    # Then 5
    assert counts(db) == before


# [claude] PCIS-C-07
def test_pcis_c_07__w2_component_404_in_w1(db, S):
    """PCIS-C-07 — a W2 component is 404 in W1.
    Rules: `create_component_item` R1"""
    commit_point(db)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_component_item(
            db,
            item_in=_create_in(S.C9.id, S.I1.id, 5),
            workspace_id=S.W1.id,
            user_id=S.U2.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NOCOMP
    # Then 4
    assert counts(db) == before


# [claude] PCIS-C-08
@pytest.mark.xfail(strict=True, reason=BUG_1278)
def test_pcis_c_08__deleted_projects_component_404_nothing_written(db, S):
    """PCIS-C-08 — a deleted project's component is 404, nothing written (pass-through).
    Rules: `create_component_item` R1 (manager `require_component_access` R2 [BUG-1278])"""
    commit_point(db)
    before = counts(db)
    pjd_id = S.PJD.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_component_item(
            db,
            item_in=_create_in(S.CD.id, S.I1.id, 5),
            workspace_id=S.W1.id,
            user_id=S.U2.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project with ID {pjd_id} not found"
    # Then 4
    assert counts(db) == before


# [claude] PCIS-C-09
@pytest.mark.xfail(strict=True, reason=BUG_1012)
def test_pcis_c_09__w2_item_404_nothing_written(db, S):
    """PCIS-C-09 — a W2 item (higher id) is 404, nothing written.
    Rules: `create_component_item` R3 [BUG-1012]"""
    commit_point(db)
    before = counts(db)
    i9_id = S.I9.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_component_item(
            db,
            item_in=_create_in(S.C1.id, i9_id, 5),
            workspace_id=S.W1.id,
            user_id=S.U2.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Item with ID {i9_id} not found"
    # Then 4
    assert not db.new
    # Then 5
    assert counts(db) == before


# [claude] PCIS-C-10
@pytest.mark.xfail(strict=True, reason=BUG_1012)
def test_pcis_c_10__w0_item_404_nothing_written(db, S):
    """PCIS-C-10 — a W0 item (lower id) is 404, nothing written.
    Rules: `create_component_item` R3 [BUG-1012]"""
    commit_point(db)
    before = counts(db)
    i0_id = S.I0.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_component_item(
            db,
            item_in=_create_in(S.C1.id, i0_id, 5),
            workspace_id=S.W1.id,
            user_id=S.U2.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Item with ID {i0_id} not found"
    # Then 4
    assert counts(db) == before


# [claude] PCIS-C-11
@pytest.mark.xfail(strict=True, reason=BUG_1012)
def test_pcis_c_11__unknown_item_id_404_not_database_error(db, S):
    """PCIS-C-11 — an unknown item id is 404, not a database error.
    Rules: `create_component_item` R3 [BUG-1012]"""
    commit_point(db)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_component_item(
            db,
            item_in=_create_in(S.C1.id, MISSING, 5),
            workspace_id=S.W1.id,
            user_id=S.U2.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Item with ID {MISSING} not found"
    # Then 4
    assert counts(db) == before


# [claude] PCIS-C-12
def test_pcis_c_12__unknown_item_id_rolls_back_nothing_saved(db, S):
    """PCIS-C-12 — an unknown item id today rolls back and nothing is saved.
    Rules: `create_component_item` R7; I-TC3"""
    commit_point(db)
    before = counts(db)
    w1_id, c1_id, u2_id = S.W1.id, S.C1.id, S.U2.id
    x_id = extra_x(db, S)
    # Then 1
    with pytest.raises(Exception):  # noqa: B017  (card: any exception; IntegrityError today, HTTPException after BUG-1012)
        with spies(db) as (_cm, rb):
            svc.create_component_item(
                db,
                item_in=_create_in(c1_id, MISSING, 5),
                workspace_id=w1_id,
                user_id=u2_id,
            )
    # Then 2
    assert rb.call_count == 1
    # Then 3
    assert x_gone(db, x_id)
    # Then 4
    assert counts(db) == before


# [claude] PCIS-C-13
@pytest.mark.xfail(strict=True, reason=BUG_2306)
def test_pcis_c_13__deleted_catalog_item_404(db, S):
    """PCIS-C-13 — a deleted catalog item is 404, nothing written.
    Rules: `create_component_item` R3a [BUG-2306]"""
    commit_point(db)
    before = counts(db)
    idl_id = S.IDL.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_component_item(
            db,
            item_in=_create_in(S.C1.id, idl_id, 5),
            workspace_id=S.W1.id,
            user_id=S.U2.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Item with ID {idl_id} not found"
    # Then 4
    assert counts(db) == before


# [claude] PCIS-C-14
@pytest.mark.xfail(strict=True, reason=BUG_2307)
def test_pcis_c_14__qty_0_refused_by_schema(S):
    """PCIS-C-14 — qty 0 is refused by the schema.
    Rules: `create_component_item` R4 [BUG-2307]"""
    c1_id, i1_id = S.C1.id, S.I1.id
    # Then 1
    with pytest.raises(PydanticValidationError):
        ProjectComponentItemCreate(project_component_id=c1_id, item_id=i1_id, qty=0)


# [claude] PCIS-C-15
@pytest.mark.xfail(strict=True, reason=BUG_2307)
def test_pcis_c_15__negative_qty_refused_by_schema(S):
    """PCIS-C-15 — a negative qty is refused by the schema.
    Rules: `create_component_item` R4 [BUG-2307]"""
    c1_id, i1_id = S.C1.id, S.I1.id
    # Then 1
    with pytest.raises(PydanticValidationError):
        ProjectComponentItemCreate(project_component_id=c1_id, item_id=i1_id, qty=-3)


# [claude] PCIS-C-16
@pytest.mark.xfail(strict=True, reason=BUG_2307)
def test_pcis_c_16__qty_above_integer_range_refused_by_schema(S):
    """PCIS-C-16 — qty above the integer range is refused by the schema.
    Rules: `create_component_item` R4 [BUG-2307]"""
    c1_id, i1_id = S.C1.id, S.I1.id
    # Then 1
    with pytest.raises(PydanticValidationError):
        ProjectComponentItemCreate(
            project_component_id=c1_id, item_id=i1_id, qty=2147483648
        )


# [claude] PCIS-C-17
def test_pcis_c_17__qty_1_stored(db, S):
    """PCIS-C-17 — qty 1 is stored.
    Rules: `create_component_item` R4"""
    commit_point(db)
    result = svc.create_component_item(
        db,
        item_in=_create_in(S.C1.id, S.I1.id, 1),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.qty == 1
    # Then 2
    assert reread(db, ProjectComponentItem, result.id).qty == 1


# [claude] PCIS-C-18
def test_pcis_c_18__qty_max_stored(db, S):
    """PCIS-C-18 — qty 2147483647 is stored.
    Rules: `create_component_item` R4"""
    commit_point(db)
    result = svc.create_component_item(
        db,
        item_in=_create_in(S.C1.id, S.I1.id, MAXQ),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.qty == 2147483647
    # Then 2
    assert reread(db, ProjectComponentItem, result.id).qty == 2147483647


# [claude] PCIS-C-19
def test_pcis_c_19__failing_commit_rolls_back_once(db, S):
    """PCIS-C-19 — a failing commit rolls back once and nothing is saved.
    Rules: `create_component_item` R7; I-TC4"""
    commit_point(db)
    before = counts(db)
    w1_id, c1_id, i1_id, ug_id = S.W1.id, S.C1.id, S.I1.id, S.UG.id
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.create_component_item(
                db,
                item_in=_create_in(c1_id, i1_id, 5),
                workspace_id=w1_id,
                user_id=ug_id,
            )
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count == 1
    # Then 3
    assert counts(db) == before


# [claude] PCIS-C-20
def test_pcis_c_20__failing_refresh_leaves_line_and_event_saved(db, S):
    """PCIS-C-20 — a failing re-read after the commit leaves the line and its event saved.
    Rules: `create_component_item` R7; I-TC5"""
    commit_point(db)
    w1_id, c1_id, i1_id, ug_id, pj1_id = S.W1.id, S.C1.id, S.I1.id, S.UG.id, S.PJ1.id
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db):
            svc.create_component_item(
                db,
                item_in=_create_in(c1_id, i1_id, 5),
                workspace_id=w1_id,
                user_id=ug_id,
            )
    assert str(exc.value) == "boom"
    # Then 2
    db.rollback()
    rows = committed_lines_of(db, c1_id)
    assert len(rows) == 1
    assert rows[0].qty == 5
    # Then 3
    assert len(events(db, pj1_id, "item_added")) == 1


# [claude] PCIS-C-21
def test_pcis_c_21__w1_item_on_private_component_of_privileged_caller(db, S):
    """PCIS-C-21 — a W1 item planned on a W1 component of a privileged caller's private project is stored.
    Rules: `create_component_item` R1, R3"""
    commit_point(db)
    cp_id, i1_id, pjp_id = S.CP.id, S.I1.id, S.PJP.id
    result = svc.create_component_item(
        db,
        item_in=_create_in(cp_id, i1_id, 3),
        workspace_id=S.W1.id,
        user_id=S.U2.id,
    )
    # Then 1
    assert result.item_id == i1_id
    # Then 2
    rid = result.id
    db.rollback()
    row = committed_row(db, rid)
    assert row.project_component_id == cp_id
    assert row.qty == 3
    # Then 3
    assert len(events(db, pjp_id, "item_added")) == 1


# =========================================================================== #
# ProjectComponentItemService.update_component_item
# =========================================================================== #


# [claude] PCIS-U-01
def test_pcis_u_01__new_qty_stored_committed_returned(db, S):
    """PCIS-U-01 — a new qty is stored, committed and returned; component and item stay.
    Rules: `update_component_item` R2, R4; I-TC1, I-TC2"""
    LA = line(db, S, S.C1, 5)
    commit_point(db)
    before_stock = stock(db)
    la_id, w1_id, c1_id, i1_id, ug_id = LA.id, S.W1.id, S.C1.id, S.I1.id, S.UG.id
    with spies(db) as (cm, _rb):
        result = svc.update_component_item(
            db,
            item_id=la_id,
            item_in=ProjectComponentItemUpdate(qty=7),
            workspace_id=w1_id,
            user_id=ug_id,
        )
    # Then 1
    assert result.id == la_id
    assert result.qty == 7
    # Then 2
    assert cm.call_count == 1
    # Then 3
    db.rollback()
    row = committed_row(db, la_id)
    assert row.qty == 7
    assert row.item_id == i1_id
    assert row.project_component_id == c1_id
    # Then 4
    assert stock(db) == before_stock


# [claude] PCIS-U-02
def test_pcis_u_02__qty_change_logs_item_updated(db, S):
    """PCIS-U-02 — a qty change logs item_updated.
    Rules: `update_component_item` R3"""
    LA = line(db, S, S.C1, 5)
    commit_point(db)
    c1_id, i1_id, ug_id, pj1_id = S.C1.id, S.I1.id, S.UG.id, S.PJ1.id
    result = svc.update_component_item(
        db,
        item_id=LA.id,
        item_in=ProjectComponentItemUpdate(qty=7),
        workspace_id=S.W1.id,
        user_id=ug_id,
    )
    # Then 1
    assert result.qty == 7
    # Then 2
    evs = events(db, pj1_id, "item_updated")
    assert len(evs) == 1
    # Then 3
    assert evs[0].performed_by == ug_id
    assert evs[0].description == "Updated component item (qty 7)"
    # Then 4
    assert evs[0].metadata_json == {
        "item_id": i1_id,
        "qty": "7",
        "component_id": c1_id,
        "component_name": "Roof",
    }


# [claude] PCIS-U-03
def test_pcis_u_03__null_qty_leaves_qty(db, S):
    """PCIS-U-03 — a null qty leaves the qty.
    Rules: `update_component_item` R2"""
    LA = line(db, S, S.C1, 5)
    commit_point(db)
    la_id = LA.id
    result = svc.update_component_item(
        db,
        item_id=la_id,
        item_in=ProjectComponentItemUpdate(qty=None),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.qty == 5
    # Then 2
    assert reread(db, ProjectComponentItem, la_id).qty == 5


# [claude] PCIS-U-04
@pytest.mark.xfail(strict=True, reason=BUG_2310)
def test_pcis_u_04__same_qty_writes_no_event(db, S):
    """PCIS-U-04 — the same qty writes no event.
    Rules: `update_component_item` R3 [BUG-2310]"""
    LA = line(db, S, S.C1, 5)
    commit_point(db)
    pj1_id = S.PJ1.id
    result = svc.update_component_item(
        db,
        item_id=LA.id,
        item_in=ProjectComponentItemUpdate(qty=5),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.qty == 5
    # Then 2
    assert len(events(db, pj1_id)) == 0


# [claude] PCIS-U-05
@pytest.mark.xfail(strict=True, reason=BUG_2310)
def test_pcis_u_05__empty_update_writes_no_event(db, S):
    """PCIS-U-05 — an empty update writes no event.
    Rules: `update_component_item` R3 [BUG-2310]"""
    LA = line(db, S, S.C1, 5)
    commit_point(db)
    la_id, pj1_id = LA.id, S.PJ1.id
    result = svc.update_component_item(
        db,
        item_id=la_id,
        item_in=ProjectComponentItemUpdate(),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.id == la_id
    # Then 2
    assert len(events(db, pj1_id)) == 0


# [claude] PCIS-U-06
def test_pcis_u_06__unknown_id_none_no_commit_no_rollback(db, S):
    """PCIS-U-06 — an unknown id returns None with no commit and no rollback.
    Rules: `update_component_item` R1; I-TC6"""
    LA = line(db, S, S.C1, 5)
    commit_point(db)
    before_la = snap(db, LA)
    w1_id, ug_id = S.W1.id, S.UG.id
    P = pending_p(db, S)
    with spies(db) as (cm, rb):
        result = svc.update_component_item(
            db,
            item_id=MISSING,
            item_in=ProjectComponentItemUpdate(qty=7),
            workspace_id=w1_id,
            user_id=ug_id,
        )
    # Then 1
    assert result is None
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert P in db.new
    # Then 5
    assert not db.dirty
    # Then 6
    assert unchanged(db, ProjectComponentItem, before_la)


# [claude] PCIS-U-07
def test_pcis_u_07__private_line_403_rolled_back_once(db, S):
    """PCIS-U-07 — a private project's line: 403, rolled back once, pending changes discarded.
    Rules: `update_component_item` R1; I-TC3"""
    LP = line(db, S, S.CP, 3)
    commit_point(db)
    before_lp = snap(db, LP)
    before = counts(db)
    lp_id, w1_id, ug_id = LP.id, S.W1.id, S.UG.id
    x_id = extra_x(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            svc.update_component_item(
                db,
                item_id=lp_id,
                item_in=ProjectComponentItemUpdate(qty=7),
                workspace_id=w1_id,
                user_id=ug_id,
            )
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == NOACCESS
    # Then 4
    assert rb.call_count == 1
    # Then 5
    assert not db.dirty
    # Then 6
    assert x_gone(db, x_id)
    # Then 7
    assert unchanged(db, ProjectComponentItem, before_lp)
    # Then 8
    assert counts(db) == before


# [claude] PCIS-U-08
@pytest.mark.xfail(strict=True, reason=BUG_2307)
def test_pcis_u_08__qty_0_refused_by_update_schema():
    """PCIS-U-08 — qty 0 is refused by the update schema.
    Rules: `update_component_item` R2 [BUG-2307]"""
    # Then 1
    with pytest.raises(PydanticValidationError):
        ProjectComponentItemUpdate(qty=0)


# [claude] PCIS-U-09
@pytest.mark.xfail(strict=True, reason=BUG_2307)
def test_pcis_u_09__qty_above_integer_range_refused_by_update_schema():
    """PCIS-U-09 — qty above the integer range is refused by the update schema.
    Rules: `update_component_item` R2 [BUG-2307]"""
    # Then 1
    with pytest.raises(PydanticValidationError):
        ProjectComponentItemUpdate(qty=2147483648)


# [claude] PCIS-U-10
def test_pcis_u_10__qty_1_stored_on_update(db, S):
    """PCIS-U-10 — qty 1 is stored on update.
    Rules: `update_component_item` R2"""
    LA = line(db, S, S.C1, 5)
    commit_point(db)
    la_id = LA.id
    result = svc.update_component_item(
        db,
        item_id=la_id,
        item_in=ProjectComponentItemUpdate(qty=1),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.qty == 1
    # Then 2
    assert reread(db, ProjectComponentItem, la_id).qty == 1


# [claude] PCIS-U-11
def test_pcis_u_11__failing_commit_rolls_back_once_line_unchanged(db, S):
    """PCIS-U-11 — a failing commit rolls back once and the line is unchanged.
    Rules: `update_component_item` R4; I-TC4"""
    LA = line(db, S, S.C1, 5)
    commit_point(db)
    before_la = snap(db, LA)
    before = counts(db)
    la_id, w1_id, ug_id = LA.id, S.W1.id, S.UG.id
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.update_component_item(
                db,
                item_id=la_id,
                item_in=ProjectComponentItemUpdate(qty=7),
                workspace_id=w1_id,
                user_id=ug_id,
            )
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count == 1
    # Then 3
    assert unchanged(db, ProjectComponentItem, before_la)
    # Then 4
    assert counts(db) == before


# [claude] PCIS-U-12
def test_pcis_u_12__failing_refresh_leaves_change_saved(db, S):
    """PCIS-U-12 — a failing re-read after the commit leaves the change saved.
    Rules: `update_component_item` R4; I-TC5"""
    LA = line(db, S, S.C1, 5)
    commit_point(db)
    la_id, w1_id, ug_id = LA.id, S.W1.id, S.UG.id
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db):
            svc.update_component_item(
                db,
                item_id=la_id,
                item_in=ProjectComponentItemUpdate(qty=7),
                workspace_id=w1_id,
                user_id=ug_id,
            )
    assert str(exc.value) == "boom"
    # Then 2
    db.rollback()
    assert committed_row(db, la_id).qty == 7


# [claude] PCIS-U-13
def test_pcis_u_13__w0_line_not_found_in_w1(db, S):
    """PCIS-U-13 — a W0 line (lower id) is not found in W1.
    Rules: `update_component_item` R1"""
    L0 = line0(db, S, qty=4)
    line(db, S, S.C1, 5)
    commit_point(db)
    before_l0 = snap(db, L0)
    before = counts(db)
    l0_id, w1_id, u2_id = L0.id, S.W1.id, S.U2.id
    with spies(db) as (cm, rb):
        result = svc.update_component_item(
            db,
            item_id=l0_id,
            item_in=ProjectComponentItemUpdate(qty=7),
            workspace_id=w1_id,
            user_id=u2_id,
        )
    # Then 1
    assert result is None
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert not db.dirty
    # Then 5
    assert unchanged(db, ProjectComponentItem, before_l0)
    # Then 6
    assert counts(db) == before


# =========================================================================== #
# ProjectComponentItemService.delete_component_item
# =========================================================================== #


# [claude] PCIS-D-01
def test_pcis_d_01__line_deleted_after_event_committed_true(db, S):
    """PCIS-D-01 — the line is deleted after its item_removed event, committed, True.
    Rules: `delete_component_item` R2, R3; I-TC1"""
    LA = line(db, S, S.C1, 5)
    LK = line(db, S, S.C1, 2)
    commit_point(db)
    before_stock = stock(db)
    la_id, lk_id, w1_id, c1_id, i1_id, ug_id, pj1_id = (
        LA.id,
        LK.id,
        S.W1.id,
        S.C1.id,
        S.I1.id,
        S.UG.id,
        S.PJ1.id,
    )
    with spies(db) as (cm, _rb):
        result = svc.delete_component_item(
            db, item_id=la_id, workspace_id=w1_id, user_id=ug_id
        )
    # Then 1
    assert result is True
    # Then 2
    assert cm.call_count == 1
    # Then 3
    db.rollback()
    assert committed_row(db, la_id) is None
    # Then 4
    assert committed_row(db, lk_id) is not None
    # Then 5
    evs = events(db, pj1_id, "item_removed")
    assert len(evs) == 1
    assert evs[0].performed_by == ug_id
    assert evs[0].description == "Removed item from component"
    # Then 6
    assert evs[0].metadata_json == {
        "item_id": i1_id,
        "component_id": c1_id,
        "component_name": "Roof",
    }
    # Then 7
    assert stock(db) == before_stock


# [claude] PCIS-D-02
def test_pcis_d_02__unknown_id_false_no_commit_no_rollback(db, S):
    """PCIS-D-02 — an unknown id returns False with no commit and no rollback.
    Rules: `delete_component_item` R1; I-TC6"""
    LA = line(db, S, S.C1, 5)
    commit_point(db)
    before_la = snap(db, LA)
    w1_id, ug_id = S.W1.id, S.UG.id
    P = pending_p(db, S)
    with spies(db) as (cm, rb):
        result = svc.delete_component_item(
            db, item_id=MISSING, workspace_id=w1_id, user_id=ug_id
        )
    # Then 1
    assert result is False
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert P in db.new
    # Then 5
    assert not db.deleted
    # Then 6
    assert unchanged(db, ProjectComponentItem, before_la)


# [claude] PCIS-D-03
def test_pcis_d_03__private_line_403_rolled_back_once_line_stays(db, S):
    """PCIS-D-03 — a private project's line: 403, rolled back once, the line stays.
    Rules: `delete_component_item` R1; I-TC3"""
    LP = line(db, S, S.CP, 3)
    commit_point(db)
    before_lp = snap(db, LP)
    before = counts(db)
    lp_id, w1_id, ug_id = LP.id, S.W1.id, S.UG.id
    x_id = extra_x(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            svc.delete_component_item(
                db, item_id=lp_id, workspace_id=w1_id, user_id=ug_id
            )
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == NOACCESS
    # Then 4
    assert rb.call_count == 1
    # Then 5
    assert not db.deleted
    # Then 6
    assert x_gone(db, x_id)
    # Then 7
    assert unchanged(db, ProjectComponentItem, before_lp)
    # Then 8
    assert counts(db) == before


# [claude] PCIS-D-04
def test_pcis_d_04__failing_commit_rolls_back_once_line_remains(db, S):
    """PCIS-D-04 — a failing commit rolls back once; the line and no event remain.
    Rules: `delete_component_item` R3; I-TC4"""
    LA = line(db, S, S.C1, 5)
    commit_point(db)
    before_la = snap(db, LA)
    before = counts(db)
    la_id, w1_id, ug_id = LA.id, S.W1.id, S.UG.id
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.delete_component_item(
                db, item_id=la_id, workspace_id=w1_id, user_id=ug_id
            )
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count == 1
    # Then 3
    assert unchanged(db, ProjectComponentItem, before_la)
    # Then 4
    assert counts(db) == before


# [claude] PCIS-D-05
def test_pcis_d_05__w2_line_not_found_in_w1(db, S):
    """PCIS-D-05 — a W2 line (higher id) is not found in W1.
    Rules: `delete_component_item` R1"""
    line(db, S, S.C1, 5)
    L9 = line9(db, S, qty=4)
    commit_point(db)
    before_l9 = snap(db, L9)
    before = counts(db)
    l9_id, w1_id, u2_id = L9.id, S.W1.id, S.U2.id
    with spies(db) as (cm, rb):
        result = svc.delete_component_item(
            db, item_id=l9_id, workspace_id=w1_id, user_id=u2_id
        )
    # Then 1
    assert result is False
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert not db.deleted
    # Then 5
    assert unchanged(db, ProjectComponentItem, before_l9)
    # Then 6
    assert counts(db) == before
