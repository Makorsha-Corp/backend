"""Unit tests for app/services/project_component_task_service.py.

Implements tests/unit/services/project_component_task_service.cases.md
(revision 2), one test per card, in card order. Real Postgres session (`db`
fixture): a `commit()` only releases a savepoint, so the service's commits are
safe and the fixture's outer rollback discards everything. Nothing is patched
except the commit / rollback spies and the failing commit / failing refresh of
the cards that name them (Conventions, Named checks).

Normal mode: every test is written from its card and carries a `# [claude] <ID>`
comment. Standing rows live on fixture `S` (`S.W1`, `S.UG`, `S.C1` ...);
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
from sqlalchemy import event, func, insert, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import DataError

from app.models.enums import TaskPriorityEnum
from app.models.factory import Factory
from app.models.project import Project
from app.models.project_component import ProjectComponent
from app.models.project_component_task import ProjectComponentTask
from app.models.project_event import ProjectEvent
from app.models.project_member import ProjectMember
from app.models.workspace_member import WorkspaceMember
from app.schemas.project_component_task import (
    ProjectComponentTaskCreate,
    ProjectComponentTaskUpdate,
)
from app.services.project_component_task_service import (
    project_component_task_service,
)
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

svc = project_component_task_service

MISSING = 999999999
T0 = datetime(2025, 12, 1, 8, 0, 0)
NOCOMP = "Project component not found"
NOACCESS = "You do not have access to this project"
HIGH = TaskPriorityEnum.HIGH
URGENT = TaskPriorityEnum.URGENT

BUG_1278 = "BUG-1278: The members and components of a deleted project stay open"
BUG_2297 = "BUG-2297: Blank or untrimmed task names accepted"
BUG_2298 = "BUG-2298: Workspace-wide task list drops hidden rows after paging"
BUG_2299 = "BUG-2299: Workspace-wide task list not in name order"
BUG_2300 = (
    'BUG-2300: "Open only" and "tasks / notes" filters ignored without a component'
)
BUG_2301 = "BUG-2301: `project_component_id=0` lists every task of the workspace"
BUG_2302 = "BUG-2302: Tasks of a deleted project stay on the workspace-wide list"
BUG_2303 = 'BUG-2303: Saving a task unchanged writes "Updated task"'
BUG_2304 = "BUG-2304: A task's priority cannot be cleared"
BUG_2305 = "BUG-2305: Turning a task into a note leaves no activity entry"


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
    return s


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #


# Given row "task(C, "N")"; `over` = the columns after "but"
def task(db, c, name, **over):
    fields = {
        "workspace_id": c.workspace_id,
        "project_component_id": c.id,
        "name": name,
        "description": "Text",
        "is_note": False,
    }
    fields.update(over)
    return _add(db, ProjectComponentTask(**fields))


# Given row "note(C, "N")"
def note(db, c, name, **over):
    return task(db, c, name, **{"is_note": True, **over})


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
        ProjectComponentTask(
            workspace_id=S.W2.id,
            project_component_id=S.C9.id,
            name="Extra",
            description="Extra",
        ),
    )
    return x.id


# Convention "pending P" (after the commit point, no flush)
def pending_p(db, S):
    p = ProjectComponentTask(
        workspace_id=S.W2.id,
        project_component_id=S.C9.id,
        name="Pending",
        description="Pending",
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


# Convention "nothing written": project_component_tasks and project_events rows
def counts(db):
    return tuple(
        db.scalar(select(func.count()).select_from(m))
        for m in (ProjectComponentTask, ProjectEvent)
    )


# Convention "x_gone"
def x_gone(db, x_id):
    return (
        db.scalar(
            select(func.count())
            .select_from(ProjectComponentTask)
            .where(ProjectComponentTask.id == x_id)
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


# Convention "META(T, "n")"
def META(S, t_id, n):
    return {
        "task_id": t_id,
        "task_name": n,
        "component_id": S.C1.id,
        "component_name": "Roof",
    }


# Convention "idset(r)"
def idset(rows):
    return {x.id for x in rows}


# Convention "names(r)" (order is part of the check)
def names(rows):
    return [x.name for x in rows]


# Convention "committed:" lines: fresh query (after the one test rollback)
def committed_row(db, row_id):
    return db.execute(
        select(ProjectComponentTask).where(ProjectComponentTask.id == row_id)
    ).scalar_one_or_none()


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


# Convention "order_part" of `sql`
def order_part(stmts):
    sql = next(
        s
        for s in stmts
        if s.lstrip().upper().startswith("SELECT")
        and "FROM project_component_tasks" in s
    )
    if "ORDER BY" not in sql:
        return ""
    return sql.split("ORDER BY", 1)[1].split("LIMIT", 1)[0]


# =========================================================================== #
# ProjectComponentTaskService.get_tasks
# =========================================================================== #


# [claude] PCTS-L-01
def test_pcts_l_01__component_no_filter_tasks_and_notes(db, S):
    """PCTS-L-01 — with a component and no filter: its tasks and notes, open and done.
    Rules: `get_tasks` R1, R2; `_guard_component` R1"""
    TA = task(db, S.C1, "Alpha")
    TD = task(db, S.C1, "Done", is_completed=True)
    NN = note(db, S.C1, "Remark")
    task(db, S.C2, "Wall task")
    result = svc.get_tasks(
        db,
        workspace_id=S.W1.id,
        user_id=S.UG.id,
        project_component_id=S.C1.id,
        limit=1000,
    )
    # Then 1
    assert idset(result) == {TA.id, TD.id, NN.id}


# [claude] PCTS-L-02
def test_pcts_l_02__component_is_note_false_tasks_only(db, S):
    """PCTS-L-02 — with a component and is_note False: tasks only.
    Rules: `get_tasks` R2"""
    TA = task(db, S.C1, "Alpha")
    TD = task(db, S.C1, "Done", is_completed=True)
    note(db, S.C1, "Remark")
    result = svc.get_tasks(
        db,
        workspace_id=S.W1.id,
        user_id=S.UG.id,
        project_component_id=S.C1.id,
        is_note=False,
        limit=1000,
    )
    # Then 1
    assert idset(result) == {TA.id, TD.id}


# [claude] PCTS-L-03
def test_pcts_l_03__open_only_kind_not_given(db, S):
    """PCTS-L-03 — open only, kind not given: open tasks, no notes.
    Rules: `get_tasks` R2"""
    TA = task(db, S.C1, "Alpha")
    task(db, S.C1, "Done", is_completed=True)
    note(db, S.C1, "Remark")
    result = svc.get_tasks(
        db,
        workspace_id=S.W1.id,
        user_id=S.UG.id,
        project_component_id=S.C1.id,
        incomplete_only=True,
        limit=1000,
    )
    # Then 1
    assert idset(result) == {TA.id}


# [claude] PCTS-L-04
def test_pcts_l_04__open_only_with_is_note_true(db, S):
    """PCTS-L-04 — open only with is_note True: open notes.
    Rules: `get_tasks` R2"""
    task(db, S.C1, "Alpha")
    NN = note(db, S.C1, "Remark")
    note(db, S.C1, "Closed remark", is_completed=True)
    result = svc.get_tasks(
        db,
        workspace_id=S.W1.id,
        user_id=S.UG.id,
        project_component_id=S.C1.id,
        incomplete_only=True,
        is_note=True,
        limit=1000,
    )
    # Then 1
    assert idset(result) == {NN.id}


# [claude] PCTS-L-05
@pytest.mark.xfail(strict=True, reason=BUG_2301)
def test_pcts_l_05__component_id_0_is_404(db, S):
    """PCTS-L-05 — component id 0 is a component id: 404.
    Rules: `get_tasks` R1 [BUG-2301]"""
    task(db, S.C1, "Alpha")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_tasks(db, workspace_id=S.W1.id, user_id=S.U2.id, project_component_id=0)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NOCOMP


# [claude] PCTS-L-06
def test_pcts_l_06__private_component_403_no_rollback(db, S):
    """PCTS-L-06 — a private component the caller may not open is 403, with no rollback.
    Rules: `get_tasks` R1, R7; T-TC6"""
    task(db, S.CP, "Plan")
    commit_point(db)
    w1_id, ug_id, cp_id = S.W1.id, S.UG.id, S.CP.id
    P = pending_p(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            svc.get_tasks(
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


# [claude] PCTS-L-07
def test_pcts_l_07__w0_component_404_in_w1(db, S):
    """PCTS-L-07 — a W0 component is 404 in W1.
    Rules: `get_tasks` R1"""
    task(db, S.C0, "Zero")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_tasks(
            db, workspace_id=S.W1.id, user_id=S.U2.id, project_component_id=S.C0.id
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NOCOMP


# [claude] PCTS-L-08
@pytest.mark.xfail(strict=True, reason=BUG_1278)
def test_pcts_l_08__deleted_projects_component_404(db, S):
    """PCTS-L-08 — a deleted project's component is 404 for the project (pass-through).
    Rules: `get_tasks` R1 (manager `require_component_access` R2 [BUG-1278])"""
    task(db, S.CD, "Gone task")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_tasks(
            db, workspace_id=S.W1.id, user_id=S.U2.id, project_component_id=S.CD.id
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project with ID {S.PJD.id} not found"


# [claude] PCTS-L-09
def test_pcts_l_09__workspace_wide_privileged_caller(db, S):
    """PCTS-L-09 — without a component: every W1 task and note a privileged caller may open.
    Rules: `get_tasks` R3; `_filter_accessible_tasks` R1"""
    task(db, S.C0, "Zero")
    TA = task(db, S.C1, "Alpha")
    NN = note(db, S.C2, "Remark")
    TP = task(db, S.CP, "Plan")
    task(db, S.C9, "Nine")
    result = svc.get_tasks(db, workspace_id=S.W1.id, user_id=S.U2.id, limit=1000)
    # Then 1
    assert idset(result) == {TA.id, NN.id, TP.id}


# [claude] PCTS-L-10
def test_pcts_l_10__plain_caller_does_not_see_private_tasks(db, S):
    """PCTS-L-10 — without a component: a plain caller does not see a private project's tasks.
    Rules: `_filter_accessible_tasks` R1"""
    task(db, S.CP, "Plan")
    TA = task(db, S.C1, "Alpha")
    result = svc.get_tasks(db, workspace_id=S.W1.id, user_id=S.UG.id, limit=1000)
    # Then 1
    assert idset(result) == {TA.id}


# [claude] PCTS-L-11
def test_pcts_l_11__other_private_membership_does_not_open_this_one(db, S):
    """PCTS-L-11 — membership of another private project does not open this one.
    Rules: `_filter_accessible_tasks` R1"""
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
    TQ = task(db, CQ, "Annex task")
    task(db, S.CP, "Plan")
    result = svc.get_tasks(db, workspace_id=S.W1.id, user_id=S.UG.id, limit=1000)
    # Then 1
    assert idset(result) == {TQ.id}


# [claude] PCTS-L-12
def test_pcts_l_12__w1_task_on_w2_component_left_out(db, S):
    """PCTS-L-12 — a W1 task on a W2 component is left out.
    Rules: `_filter_accessible_tasks` R1"""
    TA = task(db, S.C1, "Alpha")
    task(db, S.C9, "Cross", workspace_id=S.W1.id)
    result = svc.get_tasks(db, workspace_id=S.W1.id, user_id=S.U2.id, limit=1000)
    # Then 1
    assert idset(result) == {TA.id}


# [claude] PCTS-L-13
def test_pcts_l_13__w1_component_with_w2_project_left_out(db, S):
    """PCTS-L-13 — a task on a W1 component whose project is in W2 is left out.
    Rules: `_filter_accessible_tasks` R1"""
    CX = _add(
        db, ProjectComponent(workspace_id=S.W1.id, project_id=S.PJ9.id, name="Stray")
    )
    TA = task(db, S.C1, "Alpha")
    task(db, CX, "Odd")
    result = svc.get_tasks(db, workspace_id=S.W1.id, user_id=S.U2.id, limit=1000)
    # Then 1
    assert idset(result) == {TA.id}


# [claude] PCTS-L-14
@pytest.mark.xfail(strict=True, reason=BUG_2302)
def test_pcts_l_14__deleted_projects_tasks_not_listed(db, S):
    """PCTS-L-14 — tasks of a deleted project are not listed.
    Rules: `get_tasks` R6; `_filter_accessible_tasks` R2 [BUG-2302]"""
    task(db, S.CD, "Gone task")
    TA = task(db, S.C1, "Alpha")
    result = svc.get_tasks(db, workspace_id=S.W1.id, user_id=S.U2.id, limit=1000)
    # Then 1
    assert idset(result) == {TA.id}


# [claude] PCTS-L-15
@pytest.mark.xfail(strict=True, reason=BUG_2300)
def test_pcts_l_15__without_component_is_note_false_leaves_notes_out(db, S):
    """PCTS-L-15 — without a component, is_note False leaves notes out.
    Rules: `get_tasks` R3 [BUG-2300]"""
    note(db, S.C1, "Remark")
    TA = task(db, S.C1, "Alpha")
    result = svc.get_tasks(
        db, workspace_id=S.W1.id, user_id=S.U2.id, is_note=False, limit=1000
    )
    # Then 1
    assert idset(result) == {TA.id}


# [claude] PCTS-L-16
@pytest.mark.xfail(strict=True, reason=BUG_2300)
def test_pcts_l_16__without_component_open_only(db, S):
    """PCTS-L-16 — without a component, open only leaves done tasks and notes out.
    Rules: `get_tasks` R3 [BUG-2300]"""
    task(db, S.C1, "Done", is_completed=True)
    note(db, S.C1, "Remark")
    TA = task(db, S.C1, "Alpha")
    result = svc.get_tasks(
        db, workspace_id=S.W1.id, user_id=S.U2.id, incomplete_only=True, limit=1000
    )
    # Then 1
    assert idset(result) == {TA.id}


# [claude] PCTS-L-17
@pytest.mark.xfail(strict=False, reason=BUG_2298) # physical order can put the filtered-out row off the page (order sweep 2026-11-27)
def test_pcts_l_17__hidden_tasks_do_not_shorten_the_page(db, S):
    """PCTS-L-17 — hidden tasks ahead of the page do not shorten it (limit).
    Rules: `get_tasks` R5 [BUG-2298]"""
    task(db, S.CP, "Alpha")
    task(db, S.CP, "Bravo")
    task(db, S.CP, "Charlie")
    VD = task(db, S.C1, "Delta")
    VE = task(db, S.C1, "Echo")
    result = svc.get_tasks(db, workspace_id=S.W1.id, user_id=S.UG.id, skip=0, limit=2)
    # Then 1
    assert idset(result) == {VD.id, VE.id}


# [claude] PCTS-L-18
@pytest.mark.xfail(strict=False, reason=BUG_2298)
def test_pcts_l_18__hidden_tasks_do_not_shift_the_page(db, S):
    """PCTS-L-18 — hidden tasks ahead of the page do not shift it (skip).
    Rules: `get_tasks` R5 [BUG-2298]"""
    task(db, S.CP, "Alpha")
    task(db, S.CP, "Bravo")
    task(db, S.CP, "Charlie")
    task(db, S.C1, "Delta")
    VE = task(db, S.C1, "Echo")
    result = svc.get_tasks(
        db, workspace_id=S.W1.id, user_id=S.UG.id, skip=1, limit=1000
    )
    # Then 1
    assert idset(result) == {VE.id}


# [claude] PCTS-L-19
@pytest.mark.xfail(strict=True, reason=BUG_2298)
def test_pcts_l_19__filter_does_not_read_one_component_per_row(db, S):
    """PCTS-L-19 — the access filter does not read one component per row.
    Rules: `get_tasks` R5 [BUG-2298]"""
    ks = [
        _add(
            db,
            ProjectComponent(workspace_id=S.W1.id, project_id=S.PJ1.id, name=f"K{n}"),
        )
        for n in range(1, 6)
    ]
    for n, k in enumerate(ks, start=1):
        task(db, k, f"K{n} task")
    w1_id, ug_id = S.W1.id, S.UG.id
    stmts, stop = recorder(db)
    result = svc.get_tasks(db, workspace_id=w1_id, user_id=ug_id, limit=1000)
    stop()
    # Then 1
    assert len(result) == 5
    # Then 2
    assert sum(1 for s in stmts if "project_components" in s) <= 1


# [claude] PCTS-L-20
@pytest.mark.xfail(strict=False, reason=BUG_2299)
def test_pcts_l_20__workspace_wide_list_ordered_by_name_any_case(db, S):
    """PCTS-L-20 — the workspace-wide list is ordered by name, any case.
    Rules: `get_tasks` R4 [BUG-2299]"""
    task(db, S.C1, "Zulu")
    task(db, S.C2, "apple")
    task(db, S.C1, "Banana")
    result = svc.get_tasks(db, workspace_id=S.W1.id, user_id=S.U2.id, limit=1000)
    # Then 1
    assert names(result) == ["apple", "Banana", "Zulu"]


# [claude] PCTS-L-21
@pytest.mark.xfail(strict=False, reason=BUG_2299)
def test_pcts_l_21__names_equal_but_for_case_tie_on_id(db, S):
    """PCTS-L-21 — names equal but for case tie on id.
    Rules: `get_tasks` R4 [BUG-2299]"""
    TL = task(db, S.C1, "pump")
    TU = task(db, S.C1, "Pump")
    TA = task(db, S.C1, "Axle")
    result = svc.get_tasks(db, workspace_id=S.W1.id, user_id=S.U2.id, limit=1000)
    # Then 1
    assert [x.id for x in result] == [TA.id, TL.id, TU.id]


# [claude] PCTS-L-22
@pytest.mark.xfail(strict=True, reason=BUG_2299)
def test_pcts_l_22__workspace_wide_query_orders_by_name(db, S):
    """PCTS-L-22 — the workspace-wide query orders by name.
    Rules: `get_tasks` R4 [BUG-2299]"""
    TA = task(db, S.C1, "Alpha")
    w1_id, u2_id = S.W1.id, S.U2.id
    stmts, stop = recorder(db)
    result = svc.get_tasks(db, workspace_id=w1_id, user_id=u2_id, limit=1000)
    stop()
    # Then 1
    assert idset(result) == {TA.id}
    # Then 2
    assert "name" in order_part(stmts)


# [claude] PCTS-L-23
def test_pcts_l_23__limit_0_gives_empty_list(db, S):
    """PCTS-L-23 — limit 0 gives an empty list.
    Rules: `get_tasks` R8"""
    task(db, S.C1, "Alpha")
    result = svc.get_tasks(db, workspace_id=S.W1.id, user_id=S.U2.id, limit=0)
    # Then 1
    assert result == []


# [claude] PCTS-L-24
def test_pcts_l_24__default_limit_is_100(db, S):
    """PCTS-L-24 — the default limit is 100.
    Rules: `get_tasks` R8"""
    db.execute(
        insert(ProjectComponentTask),
        [
            dict(
                workspace_id=S.W1.id,
                project_component_id=S.C1.id,
                name=f"T{i:03d}",
                description="Text",
                is_note=False,
            )
            for i in range(101)
        ],
    )
    db.expire_all()
    result = svc.get_tasks(db, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 1
    assert len(result) == 100


# [claude] PCTS-L-25
def test_pcts_l_25__negative_limit_fails_in_database(db, S):
    """PCTS-L-25 — a negative limit fails in the database.
    Rules: `get_tasks` R8"""
    task(db, S.C1, "Alpha")
    # Then 1
    with pytest.raises(DataError):
        with db.begin_nested():
            svc.get_tasks(db, workspace_id=S.W1.id, user_id=S.U2.id, limit=-1)


# [claude] PCTS-L-26
def test_pcts_l_26__negative_skip_fails_in_database(db, S):
    """PCTS-L-26 — a negative skip fails in the database.
    Rules: `get_tasks` R8"""
    task(db, S.C1, "Alpha")
    # Then 1
    with pytest.raises(DataError):
        with db.begin_nested():
            svc.get_tasks(db, workspace_id=S.W1.id, user_id=S.U2.id, skip=-1)


# [claude] PCTS-L-27
def test_pcts_l_27__workspace_wide_read_no_commit_no_rollback(db, S):
    """PCTS-L-27 — the workspace-wide read neither commits nor rolls back.
    Rules: `get_tasks` R7; T-TC6"""
    TA = task(db, S.C1, "Alpha")
    commit_point(db)
    ta_id, w1_id, u2_id = TA.id, S.W1.id, S.U2.id
    P = pending_p(db, S)
    with spies(db) as (cm, rb):
        result = svc.get_tasks(db, workspace_id=w1_id, user_id=u2_id, limit=1000)
    # Then 1
    assert idset(result) == {ta_id}
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert P in db.new


# [claude] PCTS-L-28
def test_pcts_l_28__project_member_opens_private_tasks(db, S):
    """PCTS-L-28 — a project member opens a private project's tasks.
    Rules: `_filter_accessible_tasks` R1"""
    pmem(db, S, S.PJP, S.UG)
    TP = task(db, S.CP, "Plan")
    result = svc.get_tasks(db, workspace_id=S.W1.id, user_id=S.UG.id, limit=1000)
    # Then 1
    assert idset(result) == {TP.id}


# [claude] PCTS-L-29
def test_pcts_l_29__one_component_read_no_commit_no_rollback(db, S):
    """PCTS-L-29 — a successful one-component read neither commits nor rolls back.
    Rules: `get_tasks` R2, R7; T-TC6"""
    TA = task(db, S.C1, "Alpha")
    commit_point(db)
    ta_id, w1_id, ug_id, c1_id = TA.id, S.W1.id, S.UG.id, S.C1.id
    P = pending_p(db, S)
    with spies(db) as (cm, rb):
        result = svc.get_tasks(
            db,
            workspace_id=w1_id,
            user_id=ug_id,
            project_component_id=c1_id,
            limit=1000,
        )
    # Then 1
    assert idset(result) == {ta_id}
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert P in db.new


# =========================================================================== #
# ProjectComponentTaskService.get_by_id
# =========================================================================== #


# [claude] PCTS-G-01
def test_pcts_g_01__openable_task_returned(db, S):
    """PCTS-G-01 — a task the caller may open is returned.
    Rules: `get_by_id` R2"""
    TA = task(db, S.C1, "Alpha")
    result = svc.get_by_id(db, task_id=TA.id, workspace_id=S.W1.id, user_id=S.UG.id)
    # Then 1
    assert result.id == TA.id


# [claude] PCTS-G-02
def test_pcts_g_02__note_id_returned_too(db, S):
    """PCTS-G-02 — a note id is returned too.
    Rules: `get_by_id` R2"""
    NN = note(db, S.C1, "Remark")
    result = svc.get_by_id(db, task_id=NN.id, workspace_id=S.W1.id, user_id=S.UG.id)
    # Then 1
    assert result.id == NN.id
    # Then 2
    assert result.is_note is True


# [claude] PCTS-G-03
def test_pcts_g_03__unknown_id_none_no_commit_no_rollback(db, S):
    """PCTS-G-03 — an unknown id is None, with no commit and no rollback.
    Rules: `get_by_id` R1, R3; T-TC6"""
    task(db, S.C1, "Alpha")
    commit_point(db)
    w1_id, ug_id = S.W1.id, S.UG.id
    P = pending_p(db, S)
    with spies(db) as (cm, rb):
        result = svc.get_by_id(db, task_id=MISSING, workspace_id=w1_id, user_id=ug_id)
    # Then 1
    assert result is None
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert P in db.new


# [claude] PCTS-G-04
def test_pcts_g_04__id_0_is_none(db, S):
    """PCTS-G-04 — id 0 is None.
    Rules: `get_by_id` R1"""
    task(db, S.C1, "Alpha")
    result = svc.get_by_id(db, task_id=0, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 1
    assert result is None


# [claude] PCTS-G-05
def test_pcts_g_05__w0_task_none_in_w1(db, S):
    """PCTS-G-05 — a W0 task (lower id) is None in W1.
    Rules: `get_by_id` R1"""
    TK0 = task(db, S.C0, "Zero")
    task(db, S.C1, "Alpha")
    result = svc.get_by_id(db, task_id=TK0.id, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 1
    assert result is None


# [claude] PCTS-G-06
def test_pcts_g_06__w2_task_none_in_w1(db, S):
    """PCTS-G-06 — a W2 task (higher id) is None in W1.
    Rules: `get_by_id` R1"""
    task(db, S.C1, "Alpha")
    T9 = task(db, S.C9, "Nine")
    result = svc.get_by_id(db, task_id=T9.id, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 1
    assert result is None


# [claude] PCTS-G-07
def test_pcts_g_07__private_task_403_no_rollback(db, S):
    """PCTS-G-07 — a private project's task is 403 for a plain caller, with no rollback.
    Rules: `get_by_id` R2, R3"""
    TP = task(db, S.CP, "Plan")
    commit_point(db)
    tp_id, w1_id, ug_id = TP.id, S.W1.id, S.UG.id
    P = pending_p(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_by_id(db, task_id=tp_id, workspace_id=w1_id, user_id=ug_id)
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == NOACCESS
    # Then 4
    assert P in db.new


# [claude] PCTS-G-08
def test_pcts_g_08__privileged_caller_opens_private_task(db, S):
    """PCTS-G-08 — a privileged caller opens a private project's task.
    Rules: `get_by_id` R2"""
    TP = task(db, S.CP, "Plan")
    result = svc.get_by_id(db, task_id=TP.id, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 1
    assert result.id == TP.id


# [claude] PCTS-G-09
@pytest.mark.xfail(strict=True, reason=BUG_1278)
def test_pcts_g_09__deleted_projects_task_404(db, S):
    """PCTS-G-09 — a deleted project's task is 404 (pass-through).
    Rules: `get_by_id` R2 (manager `require_component_access` R2 [BUG-1278])"""
    TG = task(db, S.CD, "Gone task")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_by_id(db, task_id=TG.id, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project with ID {S.PJD.id} not found"


# [claude] PCTS-G-10
def test_pcts_g_10__one_row_read_no_commit_no_rollback(db, S):
    """PCTS-G-10 — a successful one-row read neither commits nor rolls back.
    Rules: `get_by_id` R2, R3; T-TC6"""
    TA = task(db, S.C1, "Alpha")
    commit_point(db)
    ta_id, w1_id, ug_id = TA.id, S.W1.id, S.UG.id
    P = pending_p(db, S)
    with spies(db) as (cm, rb):
        result = svc.get_by_id(db, task_id=ta_id, workspace_id=w1_id, user_id=ug_id)
    # Then 1
    assert result.id == ta_id
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert P in db.new


# =========================================================================== #
# ProjectComponentTaskService.create_task
# =========================================================================== #


# [claude] PCTS-C-01
def test_pcts_c_01__task_stored_with_defaults_committed_once(db, S):
    """PCTS-C-01 — the task is stored with its defaults, committed once and returned re-read.
    Rules: `create_task` R3, R5; T-TC1, T-TC2"""
    commit_point(db)
    w1_id, c1_id, ug_id = S.W1.id, S.C1.id, S.UG.id
    with spies(db) as (cm, rb):
        result = svc.create_task(
            db,
            task_in=ProjectComponentTaskCreate(
                project_component_id=c1_id, name="Weld frame", description="Do it"
            ),
            workspace_id=w1_id,
            user_id=ug_id,
        )
    # Then 1
    assert result.id is not None
    assert result.created_at is not None
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
    assert row.name == "Weld frame"
    assert row.description == "Do it"
    # Then 5
    row = committed_row(db, rid)
    assert row.is_note is False
    assert row.is_completed is False
    assert row.task_priority is None


# [claude] PCTS-C-02
def test_pcts_c_02__create_logs_task_created(db, S):
    """PCTS-C-02 — creating a task logs task_created.
    Rules: `create_task` R4"""
    commit_point(db)
    w1_id, c1_id, ug_id, pj1_id = S.W1.id, S.C1.id, S.UG.id, S.PJ1.id
    result = svc.create_task(
        db,
        task_in=ProjectComponentTaskCreate(
            project_component_id=c1_id, name="Weld frame", description="Do it"
        ),
        workspace_id=w1_id,
        user_id=ug_id,
    )
    # Then 1
    rid = result.id
    assert rid is not None
    # Then 2
    evs = events(db, pj1_id, "task_created")
    assert len(evs) == 1
    # Then 3
    assert evs[0].workspace_id == w1_id
    assert evs[0].performed_by == ug_id
    assert evs[0].description == 'Added task "Weld frame"'
    # Then 4
    assert evs[0].metadata_json == {
        "task_id": rid,
        "task_name": "Weld frame",
        "component_id": c1_id,
        "component_name": "Roof",
    }


# [claude] PCTS-C-03
def test_pcts_c_03__priority_sent_is_stored(db, S):
    """PCTS-C-03 — a priority sent is stored.
    Rules: `create_task` R3"""
    commit_point(db)
    result = svc.create_task(
        db,
        task_in=ProjectComponentTaskCreate(
            project_component_id=S.C1.id,
            name="Order bolts",
            description="Do it",
            task_priority=HIGH,
        ),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.task_priority == HIGH
    # Then 2
    assert reread(db, ProjectComponentTask, result.id).task_priority == HIGH


# [claude] PCTS-C-04
def test_pcts_c_04__note_created_on_task_pages_writes_no_event(db, S):
    """PCTS-C-04 — a note created on the task pages writes no event.
    Rules: `create_task` R3, R4 (D3)"""
    commit_point(db)
    pj1_id = S.PJ1.id
    result = svc.create_task(
        db,
        task_in=ProjectComponentTaskCreate(
            project_component_id=S.C1.id,
            name="Remark",
            description="Text",
            is_note=True,
        ),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.is_note is True
    # Then 2
    rid = result.id
    db.rollback()
    row = committed_row(db, rid)
    assert row is not None
    assert row.is_note is True
    # Then 3
    assert len(events(db, pj1_id)) == 0


# [claude] PCTS-C-05
def test_pcts_c_05__private_component_403_rolled_back_once(db, S):
    """PCTS-C-05 — a private component: 403, rolled back once, pending changes discarded.
    Rules: `create_task` R1; T-TC3"""
    commit_point(db)
    before = counts(db)
    w1_id, cp_id, ug_id = S.W1.id, S.CP.id, S.UG.id
    x_id = extra_x(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            svc.create_task(
                db,
                task_in=ProjectComponentTaskCreate(
                    project_component_id=cp_id, name="Plan", description="Text"
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


# [claude] PCTS-C-06
def test_pcts_c_06__unknown_component_404_nothing_written(db, S):
    """PCTS-C-06 — an unknown component is 404, nothing written.
    Rules: `create_task` R1"""
    commit_point(db)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_task(
            db,
            task_in=ProjectComponentTaskCreate(
                project_component_id=MISSING, name="Plan", description="Text"
            ),
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


# [claude] PCTS-C-07
def test_pcts_c_07__w2_component_404_in_w1(db, S):
    """PCTS-C-07 — a W2 component is 404 in W1.
    Rules: `create_task` R1"""
    commit_point(db)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_task(
            db,
            task_in=ProjectComponentTaskCreate(
                project_component_id=S.C9.id, name="Plan", description="Text"
            ),
            workspace_id=S.W1.id,
            user_id=S.U2.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NOCOMP
    # Then 4
    assert counts(db) == before


# [claude] PCTS-C-08
@pytest.mark.xfail(strict=True, reason=BUG_1278)
def test_pcts_c_08__deleted_projects_component_404_nothing_written(db, S):
    """PCTS-C-08 — a deleted project's component is 404, nothing written (pass-through).
    Rules: `create_task` R1 (manager `require_component_access` R2 [BUG-1278])"""
    commit_point(db)
    before = counts(db)
    pjd_id = S.PJD.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_task(
            db,
            task_in=ProjectComponentTaskCreate(
                project_component_id=S.CD.id, name="Plan", description="Text"
            ),
            workspace_id=S.W1.id,
            user_id=S.U2.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project with ID {pjd_id} not found"
    # Then 4
    assert counts(db) == before


# [claude] PCTS-C-09
@pytest.mark.xfail(strict=True, reason=BUG_2297)
def test_pcts_c_09__whitespace_name_refused_by_schema(S):
    """PCTS-C-09 — a whitespace-only name is refused by the schema.
    Rules: `create_task` R2 [BUG-2297]"""
    c1_id = S.C1.id
    # Then 1
    with pytest.raises(PydanticValidationError):
        ProjectComponentTaskCreate(
            project_component_id=c1_id, name="  ", description="Text"
        )


# [claude] PCTS-C-10
@pytest.mark.xfail(strict=True, reason=BUG_2297)
def test_pcts_c_10__empty_name_refused_by_schema(S):
    """PCTS-C-10 — an empty name is refused by the schema.
    Rules: `create_task` R2 [BUG-2297]"""
    c1_id = S.C1.id
    # Then 1
    with pytest.raises(PydanticValidationError):
        ProjectComponentTaskCreate(
            project_component_id=c1_id, name="", description="Text"
        )


# [claude] PCTS-C-11
@pytest.mark.xfail(strict=True, reason=BUG_2297)
def test_pcts_c_11__name_stored_trimmed(db, S):
    """PCTS-C-11 — the name is stored trimmed.
    Rules: `create_task` R2 [BUG-2297]"""
    commit_point(db)
    result = svc.create_task(
        db,
        task_in=ProjectComponentTaskCreate(
            project_component_id=S.C1.id, name="  Weld  frame  ", description="Do it"
        ),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, ProjectComponentTask, result.id).name == "Weld  frame"


# [claude] PCTS-C-12
def test_pcts_c_12__description_kept_as_typed_empty_included(db, S):
    """PCTS-C-12 — the description is kept as typed, empty included.
    Rules: `create_task` R2"""
    commit_point(db)
    result = svc.create_task(
        db,
        task_in=ProjectComponentTaskCreate(
            project_component_id=S.C1.id, name="Weld", description=""
        ),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.description == ""
    # Then 2
    row = reread(db, ProjectComponentTask, result.id)
    assert row.description == ""
    assert row.name == "Weld"


# [claude] PCTS-C-13
def test_pcts_c_13__description_required_by_schema(S):
    """PCTS-C-13 — the description is required by the schema.
    Rules: `create_task` R2"""
    c1_id = S.C1.id
    # Then 1
    with pytest.raises(PydanticValidationError):
        ProjectComponentTaskCreate(project_component_id=c1_id, name="Weld")


# [claude] PCTS-C-14
def test_pcts_c_14__failing_commit_rolls_back_once(db, S):
    """PCTS-C-14 — a failing commit rolls back once and nothing is saved.
    Rules: `create_task` R5; T-TC4"""
    commit_point(db)
    before = counts(db)
    w1_id, c1_id, ug_id = S.W1.id, S.C1.id, S.UG.id
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.create_task(
                db,
                task_in=ProjectComponentTaskCreate(
                    project_component_id=c1_id, name="Weld", description="Do it"
                ),
                workspace_id=w1_id,
                user_id=ug_id,
            )
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count == 1
    # Then 3
    assert counts(db) == before


# [claude] PCTS-C-15
def test_pcts_c_15__failing_refresh_leaves_task_and_event_saved(db, S):
    """PCTS-C-15 — a failing re-read after the commit leaves the task and its event saved.
    Rules: `create_task` R5; T-TC5"""
    commit_point(db)
    w1_id, c1_id, ug_id, pj1_id = S.W1.id, S.C1.id, S.UG.id, S.PJ1.id
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db):
            svc.create_task(
                db,
                task_in=ProjectComponentTaskCreate(
                    project_component_id=c1_id, name="Weld", description="Do it"
                ),
                workspace_id=w1_id,
                user_id=ug_id,
            )
    assert str(exc.value) == "boom"
    # Then 2
    db.rollback()
    rows = (
        db.execute(
            select(ProjectComponentTask).where(
                ProjectComponentTask.project_component_id == c1_id
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].name == "Weld"
    # Then 3
    assert len(events(db, pj1_id, "task_created")) == 1


# =========================================================================== #
# ProjectComponentTaskService.update_task
# =========================================================================== #


# [claude] PCTS-U-01
def test_pcts_u_01__rename_stored_committed_returned(db, S):
    """PCTS-U-01 — a rename is stored, committed and returned.
    Rules: `update_task` R2, R7; T-TC1, T-TC2"""
    T = task(db, S.C1, "Weld frame")
    commit_point(db)
    t_id, w1_id, c1_id, ug_id = T.id, S.W1.id, S.C1.id, S.UG.id
    with spies(db) as (cm, _rb):
        result = svc.update_task(
            db,
            task_id=t_id,
            task_in=ProjectComponentTaskUpdate(name="Weld base"),
            workspace_id=w1_id,
            user_id=ug_id,
        )
    # Then 1
    assert result.id == t_id
    assert result.name == "Weld base"
    # Then 2
    assert cm.call_count == 1
    # Then 3
    db.rollback()
    row = committed_row(db, t_id)
    assert row.name == "Weld base"
    assert row.description == "Text"
    assert row.project_component_id == c1_id
    # Then 4
    row = committed_row(db, t_id)
    assert row.is_completed is False
    assert row.is_note is False
    assert row.task_priority is None


# [claude] PCTS-U-02
def test_pcts_u_02__rename_logs_task_updated(db, S):
    """PCTS-U-02 — a rename logs task_updated with the new name.
    Rules: `update_task` R4"""
    T = task(db, S.C1, "Weld frame")
    commit_point(db)
    t_id, ug_id, pj1_id = T.id, S.UG.id, S.PJ1.id
    result = svc.update_task(
        db,
        task_id=t_id,
        task_in=ProjectComponentTaskUpdate(name="Weld base"),
        workspace_id=S.W1.id,
        user_id=ug_id,
    )
    # Then 1
    assert result.name == "Weld base"
    # Then 2
    evs = events(db, pj1_id, "task_updated")
    assert len(evs) == 1
    # Then 3
    assert evs[0].performed_by == ug_id
    assert evs[0].description == 'Updated task "Weld base"'
    # Then 4
    assert evs[0].metadata_json == META(S, t_id, "Weld base")
    # Then 5
    assert len(events(db, pj1_id)) == 1


# [claude] PCTS-U-03
def test_pcts_u_03__completing_open_task_logs_task_completed(db, S):
    """PCTS-U-03 — completing an open task logs task_completed.
    Rules: `update_task` R4"""
    T = task(db, S.C1, "Weld frame")
    commit_point(db)
    t_id, pj1_id = T.id, S.PJ1.id
    result = svc.update_task(
        db,
        task_id=t_id,
        task_in=ProjectComponentTaskUpdate(is_completed=True),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.is_completed is True
    # Then 2
    assert reread(db, ProjectComponentTask, t_id).is_completed is True
    # Then 3
    evs = events(db, pj1_id, "task_completed")
    assert len(evs) == 1
    assert evs[0].description == 'Completed task "Weld frame"'
    assert evs[0].metadata_json == META(S, t_id, "Weld frame")
    # Then 4
    assert len(events(db, pj1_id)) == 1


# [claude] PCTS-U-04
def test_pcts_u_04__complete_and_rename_logs_only_task_completed(db, S):
    """PCTS-U-04 — completing and renaming at once logs only task_completed, with the new name.
    Rules: `update_task` R4"""
    T = task(db, S.C1, "Weld frame")
    commit_point(db)
    pj1_id = S.PJ1.id
    result = svc.update_task(
        db,
        task_id=T.id,
        task_in=ProjectComponentTaskUpdate(name="Weld base", is_completed=True),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.name == "Weld base"
    # Then 2
    evs = events(db, pj1_id, "task_completed")
    assert len(evs) == 1
    assert evs[0].description == 'Completed task "Weld base"'
    # Then 3
    assert len(events(db, pj1_id)) == 1


# [claude] PCTS-U-05
def test_pcts_u_05__reopening_done_task_logs_task_reopened(db, S):
    """PCTS-U-05 — reopening a done task logs task_reopened.
    Rules: `update_task` R4"""
    T = task(db, S.C1, "Weld frame", is_completed=True)
    commit_point(db)
    pj1_id = S.PJ1.id
    result = svc.update_task(
        db,
        task_id=T.id,
        task_in=ProjectComponentTaskUpdate(is_completed=False),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.is_completed is False
    # Then 2
    evs = events(db, pj1_id, "task_reopened")
    assert len(evs) == 1
    assert evs[0].description == 'Reopened task "Weld frame"'
    # Then 3
    assert len(events(db, pj1_id)) == 1


# [claude] PCTS-U-06
def test_pcts_u_06__completion_sent_unchanged_with_rename_logs_task_updated(db, S):
    """PCTS-U-06 — completion sent but unchanged, with a rename, logs task_updated.
    Rules: `update_task` R4"""
    T = task(db, S.C1, "Weld frame", is_completed=True)
    commit_point(db)
    pj1_id = S.PJ1.id
    result = svc.update_task(
        db,
        task_id=T.id,
        task_in=ProjectComponentTaskUpdate(name="Weld base", is_completed=True),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.name == "Weld base"
    # Then 2
    evs = events(db, pj1_id, "task_updated")
    assert len(evs) == 1
    assert evs[0].description == 'Updated task "Weld base"'
    # Then 3
    assert len(events(db, pj1_id)) == 1


# [claude] PCTS-U-07
def test_pcts_u_07__priority_sent_is_stored(db, S):
    """PCTS-U-07 — a priority sent is stored.
    Rules: `update_task` R2"""
    T = task(db, S.C1, "Order bolts")
    commit_point(db)
    t_id = T.id
    result = svc.update_task(
        db,
        task_id=t_id,
        task_in=ProjectComponentTaskUpdate(task_priority=HIGH),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.task_priority == HIGH
    # Then 2
    assert reread(db, ProjectComponentTask, t_id).task_priority == HIGH


# [claude] PCTS-U-08
@pytest.mark.xfail(strict=True, reason=BUG_2304)
def test_pcts_u_08__explicit_null_clears_priority(db, S):
    """PCTS-U-08 — an explicit null clears the priority.
    Rules: `update_task` R2a [BUG-2304]"""
    T = task(db, S.C1, "Order bolts", task_priority=HIGH)
    commit_point(db)
    t_id = T.id
    result = svc.update_task(
        db,
        task_id=t_id,
        task_in=ProjectComponentTaskUpdate(task_priority=None),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.id == t_id
    # Then 2
    assert reread(db, ProjectComponentTask, t_id).task_priority is None


# [claude] PCTS-U-09
def test_pcts_u_09__omitted_priority_left_as_is(db, S):
    """PCTS-U-09 — an omitted priority is left as it is.
    Rules: `update_task` R2, R2a"""
    T = task(db, S.C1, "Order bolts", task_priority=HIGH)
    commit_point(db)
    t_id = T.id
    result = svc.update_task(
        db,
        task_id=t_id,
        task_in=ProjectComponentTaskUpdate(name="Order nuts"),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.name == "Order nuts"
    # Then 2
    assert reread(db, ProjectComponentTask, t_id).task_priority == HIGH


# [claude] PCTS-U-10
@pytest.mark.xfail(strict=True, reason=BUG_2304)
def test_pcts_u_10__null_name_refused_by_update_schema():
    """PCTS-U-10 — a null name is refused by the update schema.
    Rules: `update_task` R2a [BUG-2304]"""
    # Then 1
    with pytest.raises(PydanticValidationError):
        ProjectComponentTaskUpdate(name=None)


# [claude] PCTS-U-11
@pytest.mark.xfail(strict=True, reason=BUG_2304)
def test_pcts_u_11__null_completion_refused_by_update_schema():
    """PCTS-U-11 — a null completion flag is refused by the update schema.
    Rules: `update_task` R2a [BUG-2304]"""
    # Then 1
    with pytest.raises(PydanticValidationError):
        ProjectComponentTaskUpdate(is_completed=None)


# [claude] PCTS-U-12
@pytest.mark.xfail(strict=True, reason=BUG_2303)
def test_pcts_u_12__empty_update_writes_no_event(db, S):
    """PCTS-U-12 — an empty update writes no event.
    Rules: `update_task` R6 [BUG-2303]"""
    T = task(db, S.C1, "Weld frame")
    commit_point(db)
    t_id, pj1_id = T.id, S.PJ1.id
    result = svc.update_task(
        db,
        task_id=t_id,
        task_in=ProjectComponentTaskUpdate(),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.id == t_id
    # Then 2
    assert len(events(db, pj1_id)) == 0


# [claude] PCTS-U-13
@pytest.mark.xfail(strict=True, reason=BUG_2303)
def test_pcts_u_13__same_values_write_no_event(db, S):
    """PCTS-U-13 — sending the same values writes no event.
    Rules: `update_task` R6 [BUG-2303]"""
    T = task(db, S.C1, "Weld frame")
    commit_point(db)
    pj1_id = S.PJ1.id
    result = svc.update_task(
        db,
        task_id=T.id,
        task_in=ProjectComponentTaskUpdate(name="Weld frame", is_completed=False),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.name == "Weld frame"
    # Then 2
    assert len(events(db, pj1_id)) == 0


# [claude] PCTS-U-14
def test_pcts_u_14__task_turned_into_note_stored_as_note(db, S):
    """PCTS-U-14 — a task turned into a note is stored as a note.
    Rules: `update_task` R2, R5"""
    T = task(db, S.C1, "Inspect weld")
    commit_point(db)
    t_id = T.id
    result = svc.update_task(
        db,
        task_id=t_id,
        task_in=ProjectComponentTaskUpdate(is_note=True),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.is_note is True
    # Then 2
    db.rollback()
    assert committed_row(db, t_id).is_note is True


# [claude] PCTS-U-15
@pytest.mark.xfail(strict=True, reason=BUG_2305)
def test_pcts_u_15__task_turned_into_note_logged_as_task_update(db, S):
    """PCTS-U-15 — a task turned into a note is logged as a task update.
    Rules: `update_task` R5 [BUG-2305]"""
    T = task(db, S.C1, "Inspect weld")
    commit_point(db)
    pj1_id = S.PJ1.id
    result = svc.update_task(
        db,
        task_id=T.id,
        task_in=ProjectComponentTaskUpdate(is_note=True),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.is_note is True
    # Then 2
    evs = events(db, pj1_id, "task_updated")
    assert len(evs) == 1
    assert evs[0].description == 'Updated task "Inspect weld"'
    # Then 3
    assert len(events(db, pj1_id)) == 1


# [claude] PCTS-U-16
def test_pcts_u_16__note_that_stays_note_writes_no_event(db, S):
    """PCTS-U-16 — a note that stays a note writes no event.
    Rules: `update_task` R5"""
    N = note(db, S.C1, "Remark")
    commit_point(db)
    n_id, pj1_id = N.id, S.PJ1.id
    result = svc.update_task(
        db,
        task_id=n_id,
        task_in=ProjectComponentTaskUpdate(name="Remark two"),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.name == "Remark two"
    # Then 2
    row = reread(db, ProjectComponentTask, n_id)
    assert row.name == "Remark two"
    assert row.is_note is True
    # Then 3
    assert len(events(db, pj1_id)) == 0


# [claude] PCTS-U-17
def test_pcts_u_17__note_turned_into_task_logs_task_updated(db, S):
    """PCTS-U-17 — a note turned into a task logs task_updated.
    Rules: `update_task` R4, R5"""
    N = note(db, S.C1, "Remark")
    commit_point(db)
    n_id, pj1_id = N.id, S.PJ1.id
    result = svc.update_task(
        db,
        task_id=n_id,
        task_in=ProjectComponentTaskUpdate(is_note=False),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.is_note is False
    # Then 2
    evs = events(db, pj1_id, "task_updated")
    assert len(evs) == 1
    assert evs[0].description == 'Updated task "Remark"'
    assert evs[0].metadata_json == META(S, n_id, "Remark")


# [claude] PCTS-U-18
def test_pcts_u_18__unknown_id_none_no_commit_no_rollback(db, S):
    """PCTS-U-18 — an unknown id returns None with no commit and no rollback.
    Rules: `update_task` R1; T-TC6"""
    T = task(db, S.C1, "Weld frame")
    commit_point(db)
    before_t = snap(db, T)
    w1_id, ug_id = S.W1.id, S.UG.id
    P = pending_p(db, S)
    with spies(db) as (cm, rb):
        result = svc.update_task(
            db,
            task_id=MISSING,
            task_in=ProjectComponentTaskUpdate(name="New"),
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
    assert unchanged(db, ProjectComponentTask, before_t)


# [claude] PCTS-U-19
def test_pcts_u_19__private_task_403_rolled_back_once(db, S):
    """PCTS-U-19 — a private project's task: 403, rolled back once, pending changes discarded.
    Rules: `update_task` R1; T-TC3"""
    TP = task(db, S.CP, "Plan")
    commit_point(db)
    before_tp = snap(db, TP)
    before = counts(db)
    tp_id, w1_id, ug_id = TP.id, S.W1.id, S.UG.id
    x_id = extra_x(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            svc.update_task(
                db,
                task_id=tp_id,
                task_in=ProjectComponentTaskUpdate(is_completed=True),
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
    assert unchanged(db, ProjectComponentTask, before_tp)
    # Then 8
    assert counts(db) == before


# [claude] PCTS-U-20
def test_pcts_u_20__w2_task_not_found_in_w1(db, S):
    """PCTS-U-20 — a W2 task is not found in W1.
    Rules: `update_task` R1"""
    T9 = task(db, S.C9, "Nine")
    commit_point(db)
    before_t9 = snap(db, T9)
    result = svc.update_task(
        db,
        task_id=T9.id,
        task_in=ProjectComponentTaskUpdate(name="New"),
        workspace_id=S.W1.id,
        user_id=S.U2.id,
    )
    # Then 1
    assert result is None
    # Then 2
    assert unchanged(db, ProjectComponentTask, before_t9)


# [claude] PCTS-U-21
@pytest.mark.xfail(strict=True, reason=BUG_2297)
def test_pcts_u_21__sent_name_stored_trimmed(db, S):
    """PCTS-U-21 — a sent name is stored trimmed.
    Rules: `update_task` R3 [BUG-2297]"""
    T = task(db, S.C1, "Weld frame")
    commit_point(db)
    t_id = T.id
    result = svc.update_task(
        db,
        task_id=t_id,
        task_in=ProjectComponentTaskUpdate(name="  Weld base  "),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.id == t_id
    # Then 2
    assert reread(db, ProjectComponentTask, t_id).name == "Weld base"


# [claude] PCTS-U-22
@pytest.mark.xfail(strict=True, reason=BUG_2297)
def test_pcts_u_22__blank_name_refused_by_update_schema():
    """PCTS-U-22 — a blank name is refused by the update schema.
    Rules: `update_task` R3 [BUG-2297]"""
    # Then 1
    with pytest.raises(PydanticValidationError):
        ProjectComponentTaskUpdate(name="  ")


# [claude] PCTS-U-23
def test_pcts_u_23__failing_commit_rolls_back_once_task_unchanged(db, S):
    """PCTS-U-23 — a failing commit rolls back once and the task is unchanged.
    Rules: `update_task` R7; T-TC4"""
    T = task(db, S.C1, "Weld frame")
    commit_point(db)
    before_t = snap(db, T)
    before = counts(db)
    t_id, w1_id, ug_id = T.id, S.W1.id, S.UG.id
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.update_task(
                db,
                task_id=t_id,
                task_in=ProjectComponentTaskUpdate(is_completed=True),
                workspace_id=w1_id,
                user_id=ug_id,
            )
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count == 1
    # Then 3
    assert unchanged(db, ProjectComponentTask, before_t)
    # Then 4
    assert counts(db) == before


# [claude] PCTS-U-24
def test_pcts_u_24__failing_refresh_leaves_change_saved(db, S):
    """PCTS-U-24 — a failing re-read after the commit leaves the change saved.
    Rules: `update_task` R7; T-TC5"""
    T = task(db, S.C1, "Weld frame")
    commit_point(db)
    t_id, w1_id, ug_id, pj1_id = T.id, S.W1.id, S.UG.id, S.PJ1.id
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db):
            svc.update_task(
                db,
                task_id=t_id,
                task_in=ProjectComponentTaskUpdate(is_completed=True),
                workspace_id=w1_id,
                user_id=ug_id,
            )
    assert str(exc.value) == "boom"
    # Then 2
    db.rollback()
    assert committed_row(db, t_id).is_completed is True
    # Then 3
    assert len(events(db, pj1_id, "task_completed")) == 1


# [claude] PCTS-U-25
@pytest.mark.xfail(strict=True, reason=BUG_1278)
def test_pcts_u_25__deleted_projects_task_404_unchanged(db, S):
    """PCTS-U-25 — a deleted project's task is 404 and unchanged (pass-through).
    Rules: `update_task` R1 (manager `require_component_access` R2 [BUG-1278])"""
    TG = task(db, S.CD, "Gone task")
    commit_point(db)
    before_tg = snap(db, TG)
    tg_id, w1_id, u2_id, pjd_id = TG.id, S.W1.id, S.U2.id, S.PJD.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_task(
            db,
            task_id=tg_id,
            task_in=ProjectComponentTaskUpdate(name="New"),
            workspace_id=w1_id,
            user_id=u2_id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project with ID {pjd_id} not found"
    # Then 4
    assert unchanged(db, ProjectComponentTask, before_tg)


# [claude] PCTS-U-26
def test_pcts_u_26__description_change_alone_logs_task_updated(db, S):
    """PCTS-U-26 — a description change alone logs task_updated.
    Rules: `update_task` R2, R4"""
    T = task(db, S.C1, "Weld frame")
    commit_point(db)
    t_id, pj1_id = T.id, S.PJ1.id
    result = svc.update_task(
        db,
        task_id=t_id,
        task_in=ProjectComponentTaskUpdate(description="Use 6 mm rod"),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.description == "Use 6 mm rod"
    # Then 2
    row = reread(db, ProjectComponentTask, t_id)
    assert row.description == "Use 6 mm rod"
    assert row.name == "Weld frame"
    # Then 3
    assert len(events(db, pj1_id, "task_updated")) == 1


# [claude] PCTS-U-27
@pytest.mark.xfail(strict=True, reason=BUG_2305)
def test_pcts_u_27__done_task_turned_into_note_while_reopened_logs_reopened(db, S):
    """PCTS-U-27 — a done task turned into a note while reopened logs task_reopened.
    Rules: `update_task` R5 [BUG-2305]"""
    T = task(db, S.C1, "Inspect weld", is_completed=True)
    commit_point(db)
    pj1_id = S.PJ1.id
    result = svc.update_task(
        db,
        task_id=T.id,
        task_in=ProjectComponentTaskUpdate(is_note=True, is_completed=False),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.is_note is True
    # Then 2
    assert len(events(db, pj1_id, "task_reopened")) == 1
    # Then 3
    assert len(events(db, pj1_id)) == 1


# [claude] PCTS-U-28
def test_pcts_u_28__priority_changes_from_one_set_value_to_another(db, S):
    """PCTS-U-28 — a priority changes from one set value to another.
    Rules: `update_task` R2, R4"""
    T = task(db, S.C1, "Order bolts", task_priority=HIGH)
    commit_point(db)
    t_id, pj1_id = T.id, S.PJ1.id
    result = svc.update_task(
        db,
        task_id=t_id,
        task_in=ProjectComponentTaskUpdate(task_priority=URGENT),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.task_priority == URGENT
    # Then 2
    row = reread(db, ProjectComponentTask, t_id)
    assert row.task_priority == URGENT
    assert row.name == "Order bolts"
    # Then 3
    evs = events(db, pj1_id, "task_updated")
    assert len(evs) == 1
    assert evs[0].description == 'Updated task "Order bolts"'
    # Then 4
    assert len(events(db, pj1_id)) == 1


# =========================================================================== #
# ProjectComponentTaskService.delete_task
# =========================================================================== #


# [claude] PCTS-D-01
def test_pcts_d_01__task_deleted_after_event_committed_true(db, S):
    """PCTS-D-01 — a task is deleted after its task_deleted event, committed, True.
    Rules: `delete_task` R2, R3; T-TC1"""
    T = task(db, S.C1, "Weld frame")
    TK = task(db, S.C1, "Keep")
    commit_point(db)
    t_id, tk_id, w1_id, ug_id, pj1_id = T.id, TK.id, S.W1.id, S.UG.id, S.PJ1.id
    meta = META(S, t_id, "Weld frame")
    with spies(db) as (cm, _rb):
        result = svc.delete_task(db, task_id=t_id, workspace_id=w1_id, user_id=ug_id)
    # Then 1
    assert result is True
    # Then 2
    assert cm.call_count == 1
    # Then 3
    db.rollback()
    assert committed_row(db, t_id) is None
    # Then 4
    assert committed_row(db, tk_id) is not None
    # Then 5
    evs = events(db, pj1_id, "task_deleted")
    assert len(evs) == 1
    assert evs[0].performed_by == ug_id
    assert evs[0].description == 'Deleted task "Weld frame"'
    # Then 6
    assert evs[0].metadata_json == meta


# [claude] PCTS-D-02
def test_pcts_d_02__note_deleted_through_task_pages_writes_no_event(db, S):
    """PCTS-D-02 — a note deleted through the task pages writes no event.
    Rules: `delete_task` R2 (D3)"""
    N = note(db, S.C1, "Remark")
    commit_point(db)
    n_id, pj1_id = N.id, S.PJ1.id
    result = svc.delete_task(db, task_id=n_id, workspace_id=S.W1.id, user_id=S.UG.id)
    # Then 1
    assert result is True
    # Then 2
    db.rollback()
    assert committed_row(db, n_id) is None
    # Then 3
    assert len(events(db, pj1_id)) == 0


# [claude] PCTS-D-03
def test_pcts_d_03__unknown_id_false_no_commit_no_rollback(db, S):
    """PCTS-D-03 — an unknown id returns False with no commit and no rollback.
    Rules: `delete_task` R1; T-TC6"""
    T = task(db, S.C1, "Weld frame")
    commit_point(db)
    before_t = snap(db, T)
    w1_id, ug_id = S.W1.id, S.UG.id
    P = pending_p(db, S)
    with spies(db) as (cm, rb):
        result = svc.delete_task(db, task_id=MISSING, workspace_id=w1_id, user_id=ug_id)
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
    assert unchanged(db, ProjectComponentTask, before_t)


# [claude] PCTS-D-04
def test_pcts_d_04__private_task_403_rolled_back_once_task_stays(db, S):
    """PCTS-D-04 — a private project's task: 403, rolled back once, the task stays.
    Rules: `delete_task` R1; T-TC3"""
    TP = task(db, S.CP, "Plan")
    commit_point(db)
    before_tp = snap(db, TP)
    before = counts(db)
    tp_id, w1_id, ug_id = TP.id, S.W1.id, S.UG.id
    x_id = extra_x(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            svc.delete_task(db, task_id=tp_id, workspace_id=w1_id, user_id=ug_id)
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
    assert unchanged(db, ProjectComponentTask, before_tp)
    # Then 8
    assert counts(db) == before


# [claude] PCTS-D-05
def test_pcts_d_05__failing_commit_rolls_back_once_task_remains(db, S):
    """PCTS-D-05 — a failing commit rolls back once; the task and no event remain.
    Rules: `delete_task` R3; T-TC4"""
    T = task(db, S.C1, "Weld frame")
    commit_point(db)
    before_t = snap(db, T)
    before = counts(db)
    t_id, w1_id, ug_id = T.id, S.W1.id, S.UG.id
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.delete_task(db, task_id=t_id, workspace_id=w1_id, user_id=ug_id)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count == 1
    # Then 3
    assert unchanged(db, ProjectComponentTask, before_t)
    # Then 4
    assert counts(db) == before


# [claude] PCTS-D-06
@pytest.mark.xfail(strict=True, reason=BUG_1278)
def test_pcts_d_06__deleted_projects_task_404_stays(db, S):
    """PCTS-D-06 — a deleted project's task is 404 and stays (pass-through).
    Rules: `delete_task` R1 (manager `require_component_access` R2 [BUG-1278])"""
    TG = task(db, S.CD, "Gone task")
    commit_point(db)
    before_tg = snap(db, TG)
    tg_id, w1_id, u2_id, pjd_id = TG.id, S.W1.id, S.U2.id, S.PJD.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_task(db, task_id=tg_id, workspace_id=w1_id, user_id=u2_id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project with ID {pjd_id} not found"
    # Then 4
    assert unchanged(db, ProjectComponentTask, before_tg)
