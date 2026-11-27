"""Unit tests for app/services/project_component_note_service.py.

Implements tests/unit/services/project_component_note_service.cases.md
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

from app.models.factory import Factory
from app.models.project import Project
from app.models.project_component import ProjectComponent
from app.models.project_component_task import ProjectComponentTask
from app.models.project_event import ProjectEvent
from app.models.project_member import ProjectMember
from app.models.workspace_member import WorkspaceMember
from app.schemas.project_component_note import (
    ProjectComponentNoteCreate,
    ProjectComponentNoteUpdate,
)
from app.services.project_component_note_service import (
    project_component_note_service,
)
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

svc = project_component_note_service

MISSING = 999999999
T0 = datetime(2025, 12, 1, 8, 0, 0)
NOCOMP = "Project component not found"
NOACCESS = "You do not have access to this project"

BUG_1278 = "BUG-1278: The members and components of a deleted project stay open"
BUG_2290 = "BUG-2290: Blank or untrimmed note names accepted"
BUG_2291 = "BUG-2291: The note pages open, rename and delete tasks"
BUG_2292 = "BUG-2292: Workspace-wide note list has no sort order"
BUG_2293 = "BUG-2293: Workspace-wide note list drops hidden notes after paging"
BUG_2294 = "BUG-2294: Notes of a deleted project stay on the workspace-wide list"
BUG_2295 = 'BUG-2295: Saving a note unchanged writes "Updated note"'


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


# Given row "note(C, "N")"; `over` = the columns after "but"
def note(db, c, name, **over):
    fields = {
        "workspace_id": c.workspace_id,
        "project_component_id": c.id,
        "name": name,
        "description": "Text",
        "is_note": True,
    }
    fields.update(over)
    return _add(db, ProjectComponentTask(**fields))


# Given row "task(C, "N")"
def task(db, c, name, **over):
    return note(db, c, name, **{"is_note": False, **over})


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
            is_note=True,
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
        is_note=True,
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
# ProjectComponentNoteService.get_notes
# =========================================================================== #


# [claude] PCNS-L-01
def test_pcns_l_01__with_a_component_its_notes_only(db, S):
    """PCNS-L-01 — with a component: that component's notes only, no tasks.
    Rules: `get_notes` R1; `_guard_component` R1"""
    NA = note(db, S.C1, "Alpha")
    task(db, S.C1, "Beta")
    note(db, S.C2, "Wall note")
    result = svc.get_notes(
        db,
        workspace_id=S.W1.id,
        user_id=S.UG.id,
        project_component_id=S.C1.id,
        limit=1000,
    )
    # Then 1
    assert idset(result) == {NA.id}
    # Then 2
    assert all(x.is_note is True for x in result)


# [claude] PCNS-L-02
def test_pcns_l_02__component_id_0_is_404_no_commit_no_rollback(db, S):
    """PCNS-L-02 — component id 0 is 404, and the read neither commits nor rolls back.
    Rules: `get_notes` R1, R7; N-TC6"""
    note(db, S.C1, "Alpha")
    commit_point(db)
    w1_id, ug_id = S.W1.id, S.UG.id
    P = pending_p(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (cm, rb):
            svc.get_notes(db, workspace_id=w1_id, user_id=ug_id, project_component_id=0)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NOCOMP
    # Then 4
    assert rb.call_count == 0
    # Then 5
    assert cm.call_count == 0
    # Then 6
    assert P in db.new


# [claude] PCNS-L-03
def test_pcns_l_03__private_component_is_403(db, S):
    """PCNS-L-03 — a component of a private project the caller may not open is 403.
    Rules: `get_notes` R1; `_guard_component` R1"""
    note(db, S.CP, "Plan")
    commit_point(db)
    w1_id, ug_id, cp_id = S.W1.id, S.UG.id, S.CP.id
    P = pending_p(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_notes(db, workspace_id=w1_id, user_id=ug_id, project_component_id=cp_id)
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == NOACCESS
    # Then 4
    assert P in db.new


# [claude] PCNS-L-04
def test_pcns_l_04__w0_component_is_404_in_w1(db, S):
    """PCNS-L-04 — a W0 component is 404 in W1.
    Rules: `get_notes` R1; `_guard_component` R1"""
    note(db, S.C0, "Zero")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_notes(
            db, workspace_id=S.W1.id, user_id=S.U2.id, project_component_id=S.C0.id
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NOCOMP


# [claude] PCNS-L-05
@pytest.mark.xfail(strict=True, reason=BUG_1278)
def test_pcns_l_05__deleted_projects_component_is_404(db, S):
    """PCNS-L-05 — a component of a deleted project is 404 for the project (pass-through).
    Rules: `get_notes` R1; `_guard_component` R1 (manager `require_component_access` R2 [BUG-1278])"""
    note(db, S.CD, "Gone note")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_notes(
            db, workspace_id=S.W1.id, user_id=S.U2.id, project_component_id=S.CD.id
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project with ID {S.PJD.id} not found"


# [claude] PCNS-L-06
def test_pcns_l_06__workspace_wide_privileged_caller(db, S):
    """PCNS-L-06 — without a component: every W1 note a privileged caller may open, no tasks, no other workspace.
    Rules: `get_notes` R2; `_filter_accessible_notes` R2"""
    note(db, S.C0, "Zero")
    NA = note(db, S.C1, "Alpha")
    NP = note(db, S.CP, "Plan")
    task(db, S.C1, "Beta")
    note(db, S.C9, "Nine")
    result = svc.get_notes(db, workspace_id=S.W1.id, user_id=S.U2.id, limit=1000)
    # Then 1
    assert idset(result) == {NA.id, NP.id}


# [claude] PCNS-L-07
def test_pcns_l_07__plain_caller_does_not_see_private_notes(db, S):
    """PCNS-L-07 — without a component: a plain caller does not see a private project's notes.
    Rules: `get_notes` R2; `_filter_accessible_notes` R2"""
    note(db, S.CP, "Plan")
    NA = note(db, S.C1, "Alpha")
    result = svc.get_notes(db, workspace_id=S.W1.id, user_id=S.UG.id, limit=1000)
    # Then 1
    assert idset(result) == {NA.id}


# [claude] PCNS-L-08
def test_pcns_l_08__other_private_membership_does_not_open_this_one(db, S):
    """PCNS-L-08 — membership of another private project does not open this one.
    Rules: `_filter_accessible_notes` R2"""
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
    NQ = note(db, CQ, "Annex note")
    note(db, S.CP, "Plan")
    result = svc.get_notes(db, workspace_id=S.W1.id, user_id=S.UG.id, limit=1000)
    # Then 1
    assert idset(result) == {NQ.id}


# [claude] PCNS-L-09
def test_pcns_l_09__w1_note_on_w2_component_left_out(db, S):
    """PCNS-L-09 — a W1 note on a W2 component is left out.
    Rules: `_filter_accessible_notes` R1"""
    NA = note(db, S.C1, "Alpha")
    note(db, S.C9, "Cross", workspace_id=S.W1.id)
    result = svc.get_notes(db, workspace_id=S.W1.id, user_id=S.U2.id, limit=1000)
    # Then 1
    assert idset(result) == {NA.id}


# [claude] PCNS-L-10
def test_pcns_l_10__w1_component_with_w2_project_left_out(db, S):
    """PCNS-L-10 — a note on a W1 component whose project is in W2 is left out.
    Rules: `_filter_accessible_notes` R2"""
    CX = _add(
        db, ProjectComponent(workspace_id=S.W1.id, project_id=S.PJ9.id, name="Stray")
    )
    NA = note(db, S.C1, "Alpha")
    note(db, CX, "Odd")
    result = svc.get_notes(db, workspace_id=S.W1.id, user_id=S.U2.id, limit=1000)
    # Then 1
    assert idset(result) == {NA.id}


# [claude] PCNS-L-11
@pytest.mark.xfail(strict=True, reason=BUG_2294)
def test_pcns_l_11__deleted_projects_notes_not_listed(db, S):
    """PCNS-L-11 — notes of a deleted project are not listed.
    Rules: `get_notes` R5; `_filter_accessible_notes` R3 [BUG-2294]"""
    note(db, S.CD, "Gone note")
    NA = note(db, S.C1, "Alpha")
    result = svc.get_notes(db, workspace_id=S.W1.id, user_id=S.U2.id, limit=1000)
    # Then 1
    assert idset(result) == {NA.id}


# [claude] PCNS-L-12
@pytest.mark.xfail(strict=False, reason=BUG_2293) # physical order can put the filtered-out row off the page (order sweep 2026-11-27)
def test_pcns_l_12__hidden_notes_do_not_shorten_the_page(db, S):
    """PCNS-L-12 — hidden notes ahead of the page do not shorten it (limit).
    Rules: `get_notes` R4 [BUG-2293]"""
    note(db, S.CP, "Alpha")
    note(db, S.CP, "Bravo")
    note(db, S.CP, "Charlie")
    VD = note(db, S.C1, "Delta")
    VE = note(db, S.C1, "Echo")
    result = svc.get_notes(db, workspace_id=S.W1.id, user_id=S.UG.id, skip=0, limit=2)
    # Then 1
    assert idset(result) == {VD.id, VE.id}


# [claude] PCNS-L-13
@pytest.mark.xfail(strict=False, reason=BUG_2293)
def test_pcns_l_13__hidden_notes_do_not_shift_the_page(db, S):
    """PCNS-L-13 — hidden notes ahead of the page do not shift it (skip).
    Rules: `get_notes` R4 [BUG-2293]"""
    note(db, S.CP, "Alpha")
    note(db, S.CP, "Bravo")
    note(db, S.CP, "Charlie")
    note(db, S.C1, "Delta")
    VE = note(db, S.C1, "Echo")
    result = svc.get_notes(
        db, workspace_id=S.W1.id, user_id=S.UG.id, skip=1, limit=1000
    )
    # Then 1
    assert idset(result) == {VE.id}


# [claude] PCNS-L-14
@pytest.mark.xfail(strict=True, reason=BUG_2293)
def test_pcns_l_14__filter_does_not_read_one_component_per_row(db, S):
    """PCNS-L-14 — the access filter does not read one component per row.
    Rules: `get_notes` R4 [BUG-2293]"""
    ks = [
        _add(
            db,
            ProjectComponent(workspace_id=S.W1.id, project_id=S.PJ1.id, name=f"K{n}"),
        )
        for n in range(1, 6)
    ]
    for n, k in enumerate(ks, start=1):
        note(db, k, f"K{n} note")
    w1_id, ug_id = S.W1.id, S.UG.id
    stmts, stop = recorder(db)
    result = svc.get_notes(db, workspace_id=w1_id, user_id=ug_id, limit=1000)
    stop()
    # Then 1
    assert len(result) == 5
    # Then 2
    assert sum(1 for s in stmts if "project_components" in s) <= 1


# [claude] PCNS-L-15
@pytest.mark.xfail(strict=False, reason=BUG_2292)
def test_pcns_l_15__workspace_wide_list_ordered_by_name_any_case(db, S):
    """PCNS-L-15 — the workspace-wide list is ordered by name, any case.
    Rules: `get_notes` R3 [BUG-2292]"""
    note(db, S.C1, "Zulu")
    note(db, S.C2, "apple")
    note(db, S.C1, "Banana")
    result = svc.get_notes(db, workspace_id=S.W1.id, user_id=S.U2.id, limit=1000)
    # Then 1
    assert names(result) == ["apple", "Banana", "Zulu"]


# [claude] PCNS-L-16
@pytest.mark.xfail(strict=False, reason=BUG_2292)
def test_pcns_l_16__names_equal_but_for_case_tie_on_id(db, S):
    """PCNS-L-16 — names equal but for case tie on id.
    Rules: `get_notes` R3 [BUG-2292]"""
    NL = note(db, S.C1, "pump")
    NU = note(db, S.C1, "Pump")
    NA = note(db, S.C1, "Axle")
    result = svc.get_notes(db, workspace_id=S.W1.id, user_id=S.U2.id, limit=1000)
    # Then 1
    assert [x.id for x in result] == [NA.id, NL.id, NU.id]


# [claude] PCNS-L-17
@pytest.mark.xfail(strict=True, reason=BUG_2292)
def test_pcns_l_17__workspace_wide_query_orders_by_name(db, S):
    """PCNS-L-17 — the workspace-wide query orders by name.
    Rules: `get_notes` R3 [BUG-2292]"""
    NA = note(db, S.C1, "Alpha")
    w1_id, u2_id = S.W1.id, S.U2.id
    stmts, stop = recorder(db)
    result = svc.get_notes(db, workspace_id=w1_id, user_id=u2_id, limit=1000)
    stop()
    # Then 1
    assert idset(result) == {NA.id}
    # Then 2
    assert "name" in order_part(stmts)


# [claude] PCNS-L-18
def test_pcns_l_18__limit_0_gives_empty_list(db, S):
    """PCNS-L-18 — limit 0 gives an empty list.
    Rules: `get_notes` R6"""
    note(db, S.C1, "Alpha")
    result = svc.get_notes(db, workspace_id=S.W1.id, user_id=S.U2.id, limit=0)
    # Then 1
    assert result == []


# [claude] PCNS-L-19
def test_pcns_l_19__default_limit_is_100(db, S):
    """PCNS-L-19 — the default limit is 100.
    Rules: `get_notes` R6"""
    db.execute(
        insert(ProjectComponentTask),
        [
            dict(
                workspace_id=S.W1.id,
                project_component_id=S.C1.id,
                name=f"N{i:03d}",
                description="Text",
                is_note=True,
            )
            for i in range(101)
        ],
    )
    db.expire_all()
    result = svc.get_notes(db, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 1
    assert len(result) == 100


# [claude] PCNS-L-20
def test_pcns_l_20__negative_limit_fails_in_database(db, S):
    """PCNS-L-20 — a negative limit fails in the database.
    Rules: `get_notes` R6"""
    note(db, S.C1, "Alpha")
    # Then 1
    with pytest.raises(DataError):
        with db.begin_nested():
            svc.get_notes(db, workspace_id=S.W1.id, user_id=S.U2.id, limit=-1)


# [claude] PCNS-L-21
def test_pcns_l_21__workspace_wide_read_no_commit_no_rollback(db, S):
    """PCNS-L-21 — the workspace-wide read neither commits nor rolls back.
    Rules: `get_notes` R7; N-TC6"""
    NA = note(db, S.C1, "Alpha")
    commit_point(db)
    na_id, w1_id, u2_id = NA.id, S.W1.id, S.U2.id
    P = pending_p(db, S)
    with spies(db) as (cm, rb):
        result = svc.get_notes(db, workspace_id=w1_id, user_id=u2_id, limit=1000)
    # Then 1
    assert idset(result) == {na_id}
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert P in db.new


# [claude] PCNS-L-22
def test_pcns_l_22__one_component_read_no_commit_no_rollback(db, S):
    """PCNS-L-22 — a successful one-component read neither commits nor rolls back.
    Rules: `get_notes` R1, R7; N-TC6"""
    NA = note(db, S.C1, "Alpha")
    commit_point(db)
    na_id, w1_id, ug_id, c1_id = NA.id, S.W1.id, S.UG.id, S.C1.id
    P = pending_p(db, S)
    with spies(db) as (cm, rb):
        result = svc.get_notes(
            db,
            workspace_id=w1_id,
            user_id=ug_id,
            project_component_id=c1_id,
            limit=1000,
        )
    # Then 1
    assert idset(result) == {na_id}
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert P in db.new


# [claude] PCNS-L-23
def test_pcns_l_23__other_workspaces_notes_do_not_shorten_the_page(db, S):
    """PCNS-L-23 — other workspaces' notes ahead of the page do not shorten it.
    Rules: `get_notes` R2 ("`workspace_id` match")"""
    note(db, S.C0, "Aa zero")
    note(db, S.C9, "Ab nine")
    NC = note(db, S.C1, "Ca one")
    ND = note(db, S.C2, "Cb two")
    result = svc.get_notes(db, workspace_id=S.W1.id, user_id=S.U2.id, skip=0, limit=2)
    # Then 1
    assert idset(result) == {NC.id, ND.id}


# =========================================================================== #
# ProjectComponentNoteService.get_by_id_and_workspace
# =========================================================================== #


# [claude] PCNS-G-01
def test_pcns_g_01__openable_note_returned(db, S):
    """PCNS-G-01 — a note the caller may open is returned.
    Rules: `get_by_id_and_workspace` R3"""
    NA = note(db, S.C1, "Alpha")
    result = svc.get_by_id_and_workspace(
        db, note_id=NA.id, workspace_id=S.W1.id, user_id=S.UG.id
    )
    # Then 1
    assert result.id == NA.id
    # Then 2
    assert result.name == "Alpha"


# [claude] PCNS-G-02
def test_pcns_g_02__unknown_id_is_none_no_commit_no_rollback(db, S):
    """PCNS-G-02 — an unknown id is None, and the read neither commits nor rolls back.
    Rules: `get_by_id_and_workspace` R1, R4; N-TC6"""
    note(db, S.C1, "Alpha")
    commit_point(db)
    w1_id, ug_id = S.W1.id, S.UG.id
    P = pending_p(db, S)
    with spies(db) as (cm, rb):
        result = svc.get_by_id_and_workspace(
            db, note_id=MISSING, workspace_id=w1_id, user_id=ug_id
        )
    # Then 1
    assert result is None
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert P in db.new


# [claude] PCNS-G-03
def test_pcns_g_03__id_0_is_none(db, S):
    """PCNS-G-03 — id 0 is None.
    Rules: `get_by_id_and_workspace` R1"""
    note(db, S.C1, "Alpha")
    result = svc.get_by_id_and_workspace(
        db, note_id=0, workspace_id=S.W1.id, user_id=S.U2.id
    )
    # Then 1
    assert result is None


# [claude] PCNS-G-04
def test_pcns_g_04__w0_note_is_none_in_w1(db, S):
    """PCNS-G-04 — a W0 note (lower id) is None in W1.
    Rules: `get_by_id_and_workspace` R1"""
    N0 = note(db, S.C0, "Zero")
    note(db, S.C1, "Alpha")
    result = svc.get_by_id_and_workspace(
        db, note_id=N0.id, workspace_id=S.W1.id, user_id=S.U2.id
    )
    # Then 1
    assert result is None


# [claude] PCNS-G-05
def test_pcns_g_05__w2_note_is_none_in_w1(db, S):
    """PCNS-G-05 — a W2 note (higher id) is None in W1.
    Rules: `get_by_id_and_workspace` R1"""
    note(db, S.C1, "Alpha")
    N9 = note(db, S.C9, "Nine")
    result = svc.get_by_id_and_workspace(
        db, note_id=N9.id, workspace_id=S.W1.id, user_id=S.U2.id
    )
    # Then 1
    assert result is None


# [claude] PCNS-G-06
@pytest.mark.xfail(strict=True, reason=BUG_2291)
def test_pcns_g_06__task_id_is_not_a_note(db, S):
    """PCNS-G-06 — a task id is not a note.
    Rules: `get_by_id_and_workspace` R2 [BUG-2291]"""
    TB = task(db, S.C1, "Weld frame")
    result = svc.get_by_id_and_workspace(
        db, note_id=TB.id, workspace_id=S.W1.id, user_id=S.U2.id
    )
    # Then 1
    assert result is None


# [claude] PCNS-G-07
def test_pcns_g_07__private_note_is_403_no_rollback(db, S):
    """PCNS-G-07 — a note of a private project the caller may not open is 403, with no rollback.
    Rules: `get_by_id_and_workspace` R3, R4; N-TC6"""
    NP = note(db, S.CP, "Plan")
    commit_point(db)
    np_id, w1_id, ug_id = NP.id, S.W1.id, S.UG.id
    P = pending_p(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_by_id_and_workspace(
            db, note_id=np_id, workspace_id=w1_id, user_id=ug_id
        )
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == NOACCESS
    # Then 4
    assert P in db.new


# [claude] PCNS-G-08
def test_pcns_g_08__privileged_caller_opens_private_note(db, S):
    """PCNS-G-08 — a privileged caller opens a private project's note.
    Rules: `get_by_id_and_workspace` R3"""
    NP = note(db, S.CP, "Plan")
    result = svc.get_by_id_and_workspace(
        db, note_id=NP.id, workspace_id=S.W1.id, user_id=S.U2.id
    )
    # Then 1
    assert result.id == NP.id


# [claude] PCNS-G-09
@pytest.mark.xfail(strict=True, reason=BUG_1278)
def test_pcns_g_09__deleted_projects_note_is_404(db, S):
    """PCNS-G-09 — a note of a deleted project is 404 (pass-through).
    Rules: `get_by_id_and_workspace` R3 (manager `require_component_access` R2 [BUG-1278])"""
    ND = note(db, S.CD, "Gone note")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_by_id_and_workspace(
            db, note_id=ND.id, workspace_id=S.W1.id, user_id=S.U2.id
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project with ID {S.PJD.id} not found"


# [claude] PCNS-G-10
def test_pcns_g_10__one_row_read_no_commit_no_rollback(db, S):
    """PCNS-G-10 — a successful one-row read neither commits nor rolls back.
    Rules: `get_by_id_and_workspace` R3, R4; N-TC6"""
    NA = note(db, S.C1, "Alpha")
    commit_point(db)
    na_id, w1_id, ug_id = NA.id, S.W1.id, S.UG.id
    P = pending_p(db, S)
    with spies(db) as (cm, rb):
        result = svc.get_by_id_and_workspace(
            db, note_id=na_id, workspace_id=w1_id, user_id=ug_id
        )
    # Then 1
    assert result.id == na_id
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert P in db.new


# =========================================================================== #
# ProjectComponentNoteService.create_note
# =========================================================================== #


# [claude] PCNS-C-01
def test_pcns_c_01__note_stored_committed_once_returned(db, S):
    """PCNS-C-01 — the note is stored, committed once and returned re-read.
    Rules: `create_note` R3, R5; N-TC1, N-TC2"""
    commit_point(db)
    w1_id, c1_id, ug_id = S.W1.id, S.C1.id, S.UG.id
    with spies(db) as (cm, rb):
        result = svc.create_note(
            db,
            note_in=ProjectComponentNoteCreate(
                project_component_id=c1_id,
                name="Supplier call",
                description="Ring Monday",
            ),
            workspace_id=w1_id,
            user_id=ug_id,
        )
    # Then 1
    assert result.id is not None
    assert result.created_at is not None
    # Then 2
    assert result.is_note is True
    assert result.name == "Supplier call"
    # Then 3
    assert cm.call_count == 1
    # Then 4
    assert rb.call_count == 0
    # Then 5
    rid = result.id
    db.rollback()
    row = committed_row(db, rid)
    assert row.workspace_id == w1_id
    assert row.project_component_id == c1_id
    assert row.name == "Supplier call"
    assert row.description == "Ring Monday"
    # Then 6
    row = committed_row(db, rid)
    assert row.is_note is True
    assert row.is_completed is False
    assert row.task_priority is None


# [claude] PCNS-C-02
def test_pcns_c_02__create_logs_note_created(db, S):
    """PCNS-C-02 — creating a note logs note_created on the component's project.
    Rules: `create_note` R4"""
    commit_point(db)
    w1_id, c1_id, ug_id, pj1_id = S.W1.id, S.C1.id, S.UG.id, S.PJ1.id
    result = svc.create_note(
        db,
        note_in=ProjectComponentNoteCreate(
            project_component_id=c1_id, name="Supplier call", description="Ring Monday"
        ),
        workspace_id=w1_id,
        user_id=ug_id,
    )
    # Then 1
    rid = result.id
    assert rid is not None
    # Then 2
    evs = events(db, pj1_id, "note_created")
    assert len(evs) == 1
    # Then 3
    ev = evs[0]
    assert ev.workspace_id == w1_id
    assert ev.performed_by == ug_id
    assert ev.description == 'Added note "Supplier call"'
    # Then 4
    assert ev.metadata_json == {
        "note_id": rid,
        "note_name": "Supplier call",
        "component_id": c1_id,
        "component_name": "Roof",
    }
    # Then 5
    assert len(events(db, pj1_id)) == 1


# [claude] PCNS-C-03
def test_pcns_c_03__private_component_403_rolled_back_once(db, S):
    """PCNS-C-03 — a private component the caller may not open: 403, rolled back once, pending changes discarded.
    Rules: `create_note` R1; N-TC3"""
    commit_point(db)
    before = counts(db)
    w1_id, cp_id, ug_id = S.W1.id, S.CP.id, S.UG.id
    x_id = extra_x(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            svc.create_note(
                db,
                note_in=ProjectComponentNoteCreate(
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


# [claude] PCNS-C-04
def test_pcns_c_04__unknown_component_404_nothing_written(db, S):
    """PCNS-C-04 — an unknown component is 404, nothing written.
    Rules: `create_note` R1"""
    commit_point(db)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_note(
            db,
            note_in=ProjectComponentNoteCreate(
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


# [claude] PCNS-C-05
def test_pcns_c_05__w2_component_404_in_w1(db, S):
    """PCNS-C-05 — a W2 component is 404 in W1, nothing written.
    Rules: `create_note` R1"""
    commit_point(db)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_note(
            db,
            note_in=ProjectComponentNoteCreate(
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


# [claude] PCNS-C-06
@pytest.mark.xfail(strict=True, reason=BUG_1278)
def test_pcns_c_06__deleted_projects_component_404_nothing_written(db, S):
    """PCNS-C-06 — a deleted project's component is 404, nothing written (pass-through).
    Rules: `create_note` R1 (manager `require_component_access` R2 [BUG-1278])"""
    commit_point(db)
    before = counts(db)
    pjd_id = S.PJD.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_note(
            db,
            note_in=ProjectComponentNoteCreate(
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


# [claude] PCNS-C-07
@pytest.mark.xfail(strict=True, reason=BUG_2290)
def test_pcns_c_07__whitespace_name_refused_by_schema(S):
    """PCNS-C-07 — a whitespace-only name is refused by the schema.
    Rules: `create_note` R2 [BUG-2290]"""
    c1_id = S.C1.id
    # Then 1
    with pytest.raises(PydanticValidationError):
        ProjectComponentNoteCreate(
            project_component_id=c1_id, name="   ", description="Text"
        )


# [claude] PCNS-C-08
@pytest.mark.xfail(strict=True, reason=BUG_2290)
def test_pcns_c_08__empty_name_refused_by_schema(S):
    """PCNS-C-08 — an empty name is refused by the schema.
    Rules: `create_note` R2 [BUG-2290]"""
    c1_id = S.C1.id
    # Then 1
    with pytest.raises(PydanticValidationError):
        ProjectComponentNoteCreate(
            project_component_id=c1_id, name="", description="Text"
        )


# [claude] PCNS-C-09
@pytest.mark.xfail(strict=True, reason=BUG_2290)
def test_pcns_c_09__name_stored_trimmed(db, S):
    """PCNS-C-09 — the name is stored trimmed.
    Rules: `create_note` R2 [BUG-2290]"""
    commit_point(db)
    result = svc.create_note(
        db,
        note_in=ProjectComponentNoteCreate(
            project_component_id=S.C1.id, name="  Supplier  call  ", description="Text"
        ),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, ProjectComponentTask, result.id)
    assert row.name == "Supplier  call"


# [claude] PCNS-C-10
def test_pcns_c_10__description_kept_as_typed_empty_included(db, S):
    """PCNS-C-10 — the description is kept as typed, empty included.
    Rules: `create_note` R2"""
    commit_point(db)
    result = svc.create_note(
        db,
        note_in=ProjectComponentNoteCreate(
            project_component_id=S.C1.id, name="Call", description=""
        ),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.description == ""
    # Then 2
    row = reread(db, ProjectComponentTask, result.id)
    assert row.description == ""
    assert row.name == "Call"


# [claude] PCNS-C-11
def test_pcns_c_11__description_required_by_schema(S):
    """PCNS-C-11 — the description is required by the schema.
    Rules: `create_note` R2"""
    c1_id = S.C1.id
    # Then 1
    with pytest.raises(PydanticValidationError):
        ProjectComponentNoteCreate(project_component_id=c1_id, name="Call")


# [claude] PCNS-C-12
def test_pcns_c_12__failing_commit_rolls_back_once(db, S):
    """PCNS-C-12 — a failing commit rolls back once and nothing is saved.
    Rules: `create_note` R5; N-TC4"""
    commit_point(db)
    before = counts(db)
    w1_id, c1_id, ug_id = S.W1.id, S.C1.id, S.UG.id
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.create_note(
                db,
                note_in=ProjectComponentNoteCreate(
                    project_component_id=c1_id, name="Call", description="Text"
                ),
                workspace_id=w1_id,
                user_id=ug_id,
            )
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count == 1
    # Then 3
    assert counts(db) == before


# [claude] PCNS-C-13
def test_pcns_c_13__failing_refresh_leaves_note_and_event_saved(db, S):
    """PCNS-C-13 — a failing re-read after the commit leaves the note and its event saved.
    Rules: `create_note` R5; N-TC5"""
    commit_point(db)
    w1_id, c1_id, ug_id, pj1_id = S.W1.id, S.C1.id, S.UG.id, S.PJ1.id
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db):
            svc.create_note(
                db,
                note_in=ProjectComponentNoteCreate(
                    project_component_id=c1_id, name="Call", description="Text"
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
    assert rows[0].name == "Call"
    # Then 3
    assert len(events(db, pj1_id, "note_created")) == 1


# =========================================================================== #
# ProjectComponentNoteService.update_note
# =========================================================================== #


# [claude] PCNS-U-01
def test_pcns_u_01__rename_stored_committed_returned(db, S):
    """PCNS-U-01 — a rename is stored, committed and returned; the description stays.
    Rules: `update_note` R2, R5; N-TC1, N-TC2"""
    N = note(db, S.C1, "Old")
    commit_point(db)
    n_id, w1_id, c1_id, ug_id = N.id, S.W1.id, S.C1.id, S.UG.id
    with spies(db) as (cm, _rb):
        result = svc.update_note(
            db,
            note_id=n_id,
            note_in=ProjectComponentNoteUpdate(name="New"),
            workspace_id=w1_id,
            user_id=ug_id,
        )
    # Then 1
    assert result.id == n_id
    assert result.name == "New"
    # Then 2
    assert cm.call_count == 1
    # Then 3
    db.rollback()
    row = committed_row(db, n_id)
    assert row.name == "New"
    assert row.description == "Text"
    # Then 4
    row = committed_row(db, n_id)
    assert row.is_note is True
    assert row.project_component_id == c1_id


# [claude] PCNS-U-02
def test_pcns_u_02__update_logs_note_updated(db, S):
    """PCNS-U-02 — an update logs note_updated with the new name.
    Rules: `update_note` R4"""
    N = note(db, S.C1, "Old")
    commit_point(db)
    n_id, w1_id, c1_id, ug_id, pj1_id = N.id, S.W1.id, S.C1.id, S.UG.id, S.PJ1.id
    result = svc.update_note(
        db,
        note_id=n_id,
        note_in=ProjectComponentNoteUpdate(name="New"),
        workspace_id=w1_id,
        user_id=ug_id,
    )
    # Then 1
    assert result.name == "New"
    # Then 2
    evs = events(db, pj1_id, "note_updated")
    assert len(evs) == 1
    # Then 3
    assert evs[0].performed_by == ug_id
    assert evs[0].description == 'Updated note "New"'
    # Then 4
    assert evs[0].metadata_json == {
        "note_id": n_id,
        "note_name": "New",
        "component_id": c1_id,
        "component_name": "Roof",
    }


# [claude] PCNS-U-03
def test_pcns_u_03__null_name_leaves_name_description_changes(db, S):
    """PCNS-U-03 — a null name leaves the name; the description changes.
    Rules: `update_note` R2"""
    N = note(db, S.C1, "Old")
    commit_point(db)
    n_id = N.id
    result = svc.update_note(
        db,
        note_id=n_id,
        note_in=ProjectComponentNoteUpdate(name=None, description="Changed"),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.name == "Old"
    # Then 2
    row = reread(db, ProjectComponentTask, n_id)
    assert row.name == "Old"
    assert row.description == "Changed"


# [claude] PCNS-U-04
def test_pcns_u_04__unknown_id_none_no_commit_no_rollback(db, S):
    """PCNS-U-04 — an unknown id returns None with no commit and no rollback.
    Rules: `update_note` R1; N-TC6"""
    N = note(db, S.C1, "Old")
    commit_point(db)
    before_n = snap(db, N)
    w1_id, ug_id = S.W1.id, S.UG.id
    P = pending_p(db, S)
    with spies(db) as (cm, rb):
        result = svc.update_note(
            db,
            note_id=MISSING,
            note_in=ProjectComponentNoteUpdate(name="New"),
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
    assert unchanged(db, ProjectComponentTask, before_n)


# [claude] PCNS-U-05
@pytest.mark.xfail(strict=True, reason=BUG_2291)
def test_pcns_u_05__task_id_not_found_through_note_pages(db, S):
    """PCNS-U-05 — a task id is not found through the note pages.
    Rules: `update_note` R1 [BUG-2291]"""
    TB = task(db, S.C1, "Weld frame")
    commit_point(db)
    before_tb = snap(db, TB)
    before = counts(db)
    result = svc.update_note(
        db,
        note_id=TB.id,
        note_in=ProjectComponentNoteUpdate(name="New"),
        workspace_id=S.W1.id,
        user_id=S.U2.id,
    )
    # Then 1
    assert result is None
    # Then 2
    assert unchanged(db, ProjectComponentTask, before_tb)
    # Then 3
    assert counts(db) == before


# [claude] PCNS-U-06
def test_pcns_u_06__private_note_403_rolled_back_once(db, S):
    """PCNS-U-06 — a private project's note: 403, rolled back once, pending changes discarded.
    Rules: `update_note` R1; N-TC3"""
    NP = note(db, S.CP, "Plan")
    commit_point(db)
    before_np = snap(db, NP)
    before = counts(db)
    np_id, w1_id, ug_id = NP.id, S.W1.id, S.UG.id
    x_id = extra_x(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            svc.update_note(
                db,
                note_id=np_id,
                note_in=ProjectComponentNoteUpdate(name="New"),
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
    assert unchanged(db, ProjectComponentTask, before_np)
    # Then 8
    assert counts(db) == before


# [claude] PCNS-U-07
@pytest.mark.xfail(strict=True, reason=BUG_2295)
def test_pcns_u_07__empty_update_writes_no_event(db, S):
    """PCNS-U-07 — an empty update writes no event.
    Rules: `update_note` R4 [BUG-2295]"""
    N = note(db, S.C1, "Old")
    commit_point(db)
    n_id, pj1_id = N.id, S.PJ1.id
    result = svc.update_note(
        db,
        note_id=n_id,
        note_in=ProjectComponentNoteUpdate(),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.id == n_id
    # Then 2
    assert len(events(db, pj1_id)) == 0


# [claude] PCNS-U-08
@pytest.mark.xfail(strict=True, reason=BUG_2295)
def test_pcns_u_08__same_values_write_no_event(db, S):
    """PCNS-U-08 — sending the same values writes no event.
    Rules: `update_note` R4 [BUG-2295]"""
    N = note(db, S.C1, "Old")
    commit_point(db)
    pj1_id = S.PJ1.id
    result = svc.update_note(
        db,
        note_id=N.id,
        note_in=ProjectComponentNoteUpdate(name="Old", description="Text"),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.name == "Old"
    # Then 2
    assert len(events(db, pj1_id)) == 0


# [claude] PCNS-U-09
@pytest.mark.xfail(strict=True, reason=BUG_2290)
def test_pcns_u_09__sent_name_stored_trimmed(db, S):
    """PCNS-U-09 — a sent name is stored trimmed.
    Rules: `update_note` R3 [BUG-2290]"""
    N = note(db, S.C1, "Old")
    commit_point(db)
    n_id = N.id
    result = svc.update_note(
        db,
        note_id=n_id,
        note_in=ProjectComponentNoteUpdate(name="  New  "),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.id == n_id
    # Then 2
    row = reread(db, ProjectComponentTask, n_id)
    assert row.name == "New"


# [claude] PCNS-U-10
@pytest.mark.xfail(strict=True, reason=BUG_2290)
def test_pcns_u_10__blank_name_refused_by_update_schema():
    """PCNS-U-10 — a blank name is refused by the update schema.
    Rules: `update_note` R3 [BUG-2290]"""
    # Then 1
    with pytest.raises(PydanticValidationError):
        ProjectComponentNoteUpdate(name="  ")


# [claude] PCNS-U-11
def test_pcns_u_11__failing_commit_rolls_back_once_note_unchanged(db, S):
    """PCNS-U-11 — a failing commit rolls back once and the note is unchanged.
    Rules: `update_note` R5; N-TC4"""
    N = note(db, S.C1, "Old")
    commit_point(db)
    before_n = snap(db, N)
    before = counts(db)
    n_id, w1_id, ug_id = N.id, S.W1.id, S.UG.id
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.update_note(
                db,
                note_id=n_id,
                note_in=ProjectComponentNoteUpdate(name="New"),
                workspace_id=w1_id,
                user_id=ug_id,
            )
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count == 1
    # Then 3
    assert unchanged(db, ProjectComponentTask, before_n)
    # Then 4
    assert counts(db) == before


# [claude] PCNS-U-12
def test_pcns_u_12__failing_refresh_leaves_rename_saved(db, S):
    """PCNS-U-12 — a failing re-read after the commit leaves the rename saved.
    Rules: `update_note` R5; N-TC5"""
    N = note(db, S.C1, "Old")
    commit_point(db)
    n_id, w1_id, ug_id = N.id, S.W1.id, S.UG.id
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db):
            svc.update_note(
                db,
                note_id=n_id,
                note_in=ProjectComponentNoteUpdate(name="New"),
                workspace_id=w1_id,
                user_id=ug_id,
            )
    assert str(exc.value) == "boom"
    # Then 2
    db.rollback()
    assert committed_row(db, n_id).name == "New"


# [claude] PCNS-U-13
def test_pcns_u_13__w2_note_not_found_in_w1(db, S):
    """PCNS-U-13 — a W2 note is not found in W1.
    Rules: `update_note` R1"""
    N9 = note(db, S.C9, "Nine")
    commit_point(db)
    before_n9 = snap(db, N9)
    result = svc.update_note(
        db,
        note_id=N9.id,
        note_in=ProjectComponentNoteUpdate(name="New"),
        workspace_id=S.W1.id,
        user_id=S.U2.id,
    )
    # Then 1
    assert result is None
    # Then 2
    assert unchanged(db, ProjectComponentTask, before_n9)


# =========================================================================== #
# ProjectComponentNoteService.delete_note
# =========================================================================== #


# [claude] PCNS-D-01
def test_pcns_d_01__note_deleted_after_event_committed_true(db, S):
    """PCNS-D-01 — the note is deleted after its note_deleted event, committed, True.
    Rules: `delete_note` R2, R3; N-TC1"""
    N = note(db, S.C1, "Old")
    NK = note(db, S.C1, "Keep")
    commit_point(db)
    n_id, nk_id, w1_id, c1_id, ug_id, pj1_id = (
        N.id,
        NK.id,
        S.W1.id,
        S.C1.id,
        S.UG.id,
        S.PJ1.id,
    )
    with spies(db) as (cm, _rb):
        result = svc.delete_note(db, note_id=n_id, workspace_id=w1_id, user_id=ug_id)
    # Then 1
    assert result is True
    # Then 2
    assert cm.call_count == 1
    # Then 3
    db.rollback()
    assert committed_row(db, n_id) is None
    # Then 4
    assert committed_row(db, nk_id) is not None
    # Then 5
    evs = events(db, pj1_id, "note_deleted")
    assert len(evs) == 1
    assert evs[0].performed_by == ug_id
    assert evs[0].description == 'Deleted note "Old"'
    # Then 6
    assert evs[0].metadata_json == {
        "note_id": n_id,
        "note_name": "Old",
        "component_id": c1_id,
        "component_name": "Roof",
    }


# [claude] PCNS-D-02
def test_pcns_d_02__unknown_id_false_no_commit_no_rollback(db, S):
    """PCNS-D-02 — an unknown id returns False with no commit and no rollback.
    Rules: `delete_note` R1; N-TC6"""
    N = note(db, S.C1, "Old")
    commit_point(db)
    before_n = snap(db, N)
    w1_id, ug_id = S.W1.id, S.UG.id
    P = pending_p(db, S)
    with spies(db) as (cm, rb):
        result = svc.delete_note(db, note_id=MISSING, workspace_id=w1_id, user_id=ug_id)
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
    assert unchanged(db, ProjectComponentTask, before_n)


# [claude] PCNS-D-03
@pytest.mark.xfail(strict=True, reason=BUG_2291)
def test_pcns_d_03__task_id_not_deleted_through_note_pages(db, S):
    """PCNS-D-03 — a task id is not deleted through the note pages.
    Rules: `delete_note` R1 [BUG-2291]"""
    TB = task(db, S.C1, "Weld frame")
    commit_point(db)
    before_tb = snap(db, TB)
    before = counts(db)
    result = svc.delete_note(db, note_id=TB.id, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 1
    assert result is False
    # Then 2
    assert unchanged(db, ProjectComponentTask, before_tb)
    # Then 3
    assert counts(db) == before


# [claude] PCNS-D-04
def test_pcns_d_04__private_note_403_rolled_back_once_note_stays(db, S):
    """PCNS-D-04 — a private project's note: 403, rolled back once, the note stays.
    Rules: `delete_note` R1; N-TC3"""
    NP = note(db, S.CP, "Plan")
    commit_point(db)
    before_np = snap(db, NP)
    before = counts(db)
    np_id, w1_id, ug_id = NP.id, S.W1.id, S.UG.id
    x_id = extra_x(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            svc.delete_note(db, note_id=np_id, workspace_id=w1_id, user_id=ug_id)
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
    assert unchanged(db, ProjectComponentTask, before_np)
    # Then 8
    assert counts(db) == before


# [claude] PCNS-D-05
def test_pcns_d_05__failing_commit_rolls_back_once_note_remains(db, S):
    """PCNS-D-05 — a failing commit rolls back once; the note and no event remain.
    Rules: `delete_note` R3; N-TC4"""
    N = note(db, S.C1, "Old")
    commit_point(db)
    before_n = snap(db, N)
    before = counts(db)
    n_id, w1_id, ug_id = N.id, S.W1.id, S.UG.id
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.delete_note(db, note_id=n_id, workspace_id=w1_id, user_id=ug_id)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count == 1
    # Then 3
    assert unchanged(db, ProjectComponentTask, before_n)
    # Then 4
    assert counts(db) == before
