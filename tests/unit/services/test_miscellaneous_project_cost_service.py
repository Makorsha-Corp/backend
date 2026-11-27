"""Unit tests for app/services/miscellaneous_project_cost_service.py.

Implements tests/unit/services/miscellaneous_project_cost_service.cases.md
(revision 2), one test per card, in card order. Real Postgres session (`db`
fixture): a `commit()` only releases a savepoint, so the service's commits are
safe and the fixture's outer rollback discards everything. Nothing is patched
except the commit / rollback / refresh spies and failures the Conventions name
(the spec lists no externals).

Normal mode: every test is written from its card and carries a `# [claude] <ID>`
comment. Standing rows live on fixture `S` (`S.W1`, `S.UG`, `S.C1` ...);
`# Then N` marks the checks of the card's Then line N.
"""

# ruff: noqa: SIM117, DTZ001  (Conventions prescribe nested `with` blocks and naive datetimes)
import os
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import event, func, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import DataError

from app.models.factory import Factory
from app.models.miscellaneous_project_cost import MiscellaneousProjectCost
from app.models.project import Project
from app.models.project_component import ProjectComponent
from app.models.project_event import ProjectEvent
from app.models.workspace_member import WorkspaceMember
from app.schemas.miscellaneous_project_cost import (
    MiscellaneousProjectCostCreate,
    MiscellaneousProjectCostUpdate,
)
from app.services.miscellaneous_project_cost_service import (
    miscellaneous_project_cost_service,
)
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

svc = miscellaneous_project_cost_service

MISSING = 999999999
T0 = datetime(2025, 12, 1, 8, 0, 0)
NOCOMP = "Project component not found"
NOACCESS = "You do not have access to this project"
NOTPART = "Project component does not belong to this project"

REVISIT = "revisit after launch"
BUG_100 = "BUG-100: BaseDAO list methods have no sort order"
BUG_1013 = "BUG-1013: Project cost accepts another workspace's component next to an own project"
BUG_1192 = "BUG-1192: Activity row can be written for another workspace's order, project or component"
BUG_1278 = "BUG-1278: The members and components of a deleted project stay open"
BUG_2611 = f"BUG-2611: Workspace-wide misc cost list drops hidden costs after paging ({REVISIT})"
BUG_2612 = (
    f"BUG-2612: Costs of a deleted project stay on the workspace-wide list ({REVISIT})"
)
BUG_2613 = f"BUG-2613: Blank or untrimmed misc cost names accepted ({REVISIT})"
BUG_2614 = f'BUG-2614: An id of `0` is treated as "not given" ({REVISIT})'
BUG_2615 = f"BUG-2615: A cost can name a component of another project, bypassing that project's privacy ({REVISIT})"
BUG_2616 = f"BUG-2616: A stored cost linked to another workspace's component opens for any member ({REVISIT})"
BUG_2617 = f'BUG-2617: Saving a cost unchanged writes "Updated cost" ({REVISIT})'
BUG_2618 = (
    f"BUG-2618: A misc cost amount too large for the column gives a 500 ({REVISIT})"
)


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
    s.PJ2 = proj(s.W1, s.F1, "Yard")
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
    s.C2 = comp(s.W1, s.PJ2, "Gate")
    s.CP = comp(s.W1, s.PJP, "Vault")
    s.CD = comp(s.W1, s.PJD, "Floor")
    s.C9 = comp(s.W2, s.PJ9, "Deck")
    return s


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #


# Given row "cost"; `over` = the columns after "but"
def cost(db, S, **over):
    fields = {
        "workspace_id": S.W1.id,
        "project_id": S.PJ1.id,
        "project_component_id": None,
        "name": "Crane",
        "description": None,
        "amount": Decimal("100.00"),
    }
    fields.update(over)
    return _add(db, MiscellaneousProjectCost(**fields))


# Given row "cost on C only"
def cost_on(db, S, c, **over):
    return cost(db, S, project_id=None, project_component_id=c.id, **over)


# Given row "cost unlinked"
def cost_unlinked(db, S, **over):
    return cost(db, S, project_id=None, **over)


# Convention "commit point"
def commit_point(db):
    db.commit()


# Convention "extra row X" (after the commit point, flushed, not committed)
def extra_x(db, S):
    x = _add(
        db,
        MiscellaneousProjectCost(
            workspace_id=S.W2.id,
            project_id=S.PJ9.id,
            name="Extra",
            amount=Decimal("1.00"),
        ),
    )
    return x, x.id


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


def unchanged(db, before):
    fresh = reread(db, MiscellaneousProjectCost, before["id"])
    return (
        fresh is not None
        and {k: getattr(fresh, k) for k in _columns(MiscellaneousProjectCost)} == before
    )


# Convention "nothing written": miscellaneous_project_costs and project_events rows
def counts(db):
    return tuple(
        db.scalar(select(func.count()).select_from(m))
        for m in (MiscellaneousProjectCost, ProjectEvent)
    )


# Convention "x_kept" / "x_gone" (count of the extra row)
def x_count(db, x_id):
    return db.scalar(
        select(func.count())
        .select_from(MiscellaneousProjectCost)
        .where(MiscellaneousProjectCost.id == x_id)
    )


# Convention "events(P, t)"
def events(db, p_id, t):
    db.expire_all()
    q = (
        select(ProjectEvent)
        .where(ProjectEvent.project_id == p_id, ProjectEvent.event_type == t)
        .order_by(ProjectEvent.id)
    )
    return db.execute(q).scalars().all()


# Convention "all_events()": every ProjectEvent row in W1
def all_events(db, w1_id):
    db.expire_all()
    q = select(ProjectEvent).where(ProjectEvent.workspace_id == w1_id)
    return db.execute(q.order_by(ProjectEvent.id)).scalars().all()


# Convention "idset(r)"
def idset(rows):
    return {x.id for x in rows}


# Convention "ids(r)" (order is part of the check)
def ids(rows):
    return [x.id for x in rows]


# Convention "committed:" lines: fresh query (after the one test rollback)
def committed_row(db, row_id):
    return db.execute(
        select(MiscellaneousProjectCost).where(MiscellaneousProjectCost.id == row_id)
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
        and "FROM miscellaneous_project_costs" in s
    )
    if "ORDER BY" not in sql:
        return ""
    return sql.split("ORDER BY", 1)[1].split("LIMIT", 1)[0]


def _log(db, S, K):
    return svc._log_cost_activity(
        db,
        cost=K,
        workspace_id=S.W1.id,
        user_id=S.UG.id,
        event_type="cost_added",
        description='Added cost "Crane"',
    )


# =========================================================================== #
# MiscellaneousProjectCostService._log_cost_activity
# =========================================================================== #


# [claude] MPCSV-LA-01
def test_mpcsv_la_01__component_logs_on_components_project(db, S):
    """MPCSV-LA-01 — a cost with a component logs on the component's project, even with another project_id.
    Rules: `_log_cost_activity` R1"""
    K = cost(db, S, project_id=S.PJ2.id, project_component_id=S.C1.id)
    result = _log(db, S, K)
    # Then 1
    assert result is None
    # Then 2
    evs = events(db, S.PJ1.id, "cost_added")
    assert len(evs) == 1
    # Then 3
    assert evs[0].performed_by == S.UG.id
    assert evs[0].description == 'Added cost "Crane"'
    assert evs[0].metadata_json == {
        "cost_id": K.id,
        "cost_name": "Crane",
        "component_id": S.C1.id,
        "component_name": "Roof",
    }
    # Then 4
    assert len(events(db, S.PJ2.id, "cost_added")) == 0


# [claude] MPCSV-LA-02
def test_mpcsv_la_02__foreign_component_writes_nothing(db, S):
    """MPCSV-LA-02 — a component outside the workspace writes nothing and raises nothing.
    Rules: `_log_cost_activity` R1"""
    K = cost_on(db, S, S.C9)
    result = _log(db, S, K)
    # Then 1
    assert result is None
    # Then 2
    assert db.scalar(select(func.count()).select_from(ProjectEvent)) == 0


# [claude] MPCSV-LA-03
def test_mpcsv_la_03__project_only_logs_with_component_id_none(db, S):
    """MPCSV-LA-03 — a project-only cost logs on that project with component_id None.
    Rules: `_log_cost_activity` R2"""
    K = cost(db, S)
    result = _log(db, S, K)
    # Then 1
    assert result is None
    # Then 2
    evs = events(db, S.PJ1.id, "cost_added")
    assert len(evs) == 1
    # Then 3
    assert evs[0].performed_by == S.UG.id
    assert evs[0].metadata_json == {
        "cost_id": K.id,
        "cost_name": "Crane",
        "component_id": None,
    }


# [claude] MPCSV-LA-04
@pytest.mark.xfail(strict=True, reason=BUG_1192)
def test_mpcsv_la_04__foreign_project_refused_as_not_found(db, S):
    """MPCSV-LA-04 — a project of another workspace is refused as not found.
    Rules: `_log_cost_activity` R2 (BUG-1192 of the project manager)"""
    K = cost(db, S, project_id=S.PJ9.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _log(db, S, K)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Project with ID {S.PJ9.id} not found"
    # Then 2
    assert len(events(db, S.PJ9.id, "cost_added")) == 0


# [claude] MPCSV-LA-05
def test_mpcsv_la_05__unlinked_logs_nothing(db, S):
    """MPCSV-LA-05 — a cost with neither link logs nothing; revisit after launch (owner 2026-11-10).
    Rules: `_log_cost_activity` R3"""
    K = cost_unlinked(db, S)
    result = _log(db, S, K)
    # Then 1
    assert result is None
    # Then 2
    assert db.scalar(select(func.count()).select_from(ProjectEvent)) == 0


# [claude] MPCSV-LA-06
def test_mpcsv_la_06__event_flushed_never_committed(db, S):
    """MPCSV-LA-06 — the event is flushed, never committed.
    Rules: `_log_cost_activity` R4"""
    K = cost(db, S)
    commit_point(db)
    pj1_id = S.PJ1.id
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        _log(db, S, K)
        # Then 1
        assert len(events(db, pj1_id, "cost_added")) == 1
        # Then 2
        assert cm.call_count == 0
    sp.rollback()
    # Then 3
    assert len(events(db, pj1_id, "cost_added")) == 0


# =========================================================================== #
# MiscellaneousProjectCostService._filter_accessible_costs
# =========================================================================== #


# [claude] MPCSV-FA-01
def test_mpcsv_fa_01__plain_caller_keeps_open_costs_in_order(db, S):
    """MPCSV-FA-01 — a plain caller keeps open-project costs, in input order.
    Rules: `_filter_accessible_costs` R1, R2, R4"""
    KA = cost(db, S)
    KP = cost(db, S, project_id=S.PJP.id)
    KC = cost_on(db, S, S.C2)
    KU = cost_unlinked(db, S)
    K9 = cost_on(db, S, S.C9)
    result = svc._filter_accessible_costs(
        db, costs=[KC, K9, KU, KP, KA], workspace_id=S.W1.id, user_id=S.UG.id
    )
    # Then 1
    assert ids(result) == [KC.id, KA.id]


# [claude] MPCSV-FA-02
def test_mpcsv_fa_02__privileged_caller_keeps_private_cost(db, S):
    """MPCSV-FA-02 — a privileged caller keeps the private project's cost too.
    Rules: `_filter_accessible_costs` R4"""
    KA = cost(db, S)
    KP = cost(db, S, project_id=S.PJP.id)
    KU = cost_unlinked(db, S)
    result = svc._filter_accessible_costs(
        db, costs=[KP, KU, KA], workspace_id=S.W1.id, user_id=S.U2.id
    )
    # Then 1
    assert ids(result) == [KP.id, KA.id]


# [claude] MPCSV-FA-03
def test_mpcsv_fa_03__both_links_judged_by_project(db, S):
    """MPCSV-FA-03 — a cost with both links is judged by its project only.
    Rules: `_filter_accessible_costs` R4"""
    KB = cost(db, S, project_component_id=S.CP.id)
    result = svc._filter_accessible_costs(
        db, costs=[KB], workspace_id=S.W1.id, user_id=S.UG.id
    )
    # Then 1
    assert ids(result) == [KB.id]


# [claude] MPCSV-FA-04
def test_mpcsv_fa_04__foreign_project_cost_dropped(db, S):
    """MPCSV-FA-04 — a cost naming another workspace's project is dropped.
    Rules: `_filter_accessible_costs` R4 (project found in the workspace)"""
    K9 = cost(db, S, project_id=S.PJ9.id)
    KA = cost(db, S)
    result = svc._filter_accessible_costs(
        db, costs=[K9, KA], workspace_id=S.W1.id, user_id=S.U2.id
    )
    # Then 1
    assert ids(result) == [KA.id]


# [claude] MPCSV-FA-05
@pytest.mark.xfail(strict=True, reason=BUG_2612)
def test_mpcsv_fa_05__deleted_project_cost_dropped(db, S):
    """MPCSV-FA-05 — a deleted project's cost is dropped.
    Rules: `_filter_accessible_costs` R3 [BUG-2612]"""
    KD = cost(db, S, project_id=S.PJD.id)
    KA = cost(db, S)
    result = svc._filter_accessible_costs(
        db, costs=[KD, KA], workspace_id=S.W1.id, user_id=S.U2.id
    )
    # Then 1
    assert ids(result) == [KA.id]


# [claude] MPCSV-FA-06
def test_mpcsv_fa_06__empty_list(db, S):
    """MPCSV-FA-06 — an empty list gives an empty list.
    Rules: `_filter_accessible_costs` R5"""
    result = svc._filter_accessible_costs(
        db, costs=[], workspace_id=S.W1.id, user_id=S.UG.id
    )
    # Then 1
    assert result == []


# =========================================================================== #
# MiscellaneousProjectCostService.get_costs
# =========================================================================== #


# [claude] MPCSV-L-01
def test_mpcsv_l_01__with_project_its_costs_nothing_committed(db, S):
    """MPCSV-L-01 — with a project: that project's costs, the component ignored, nothing committed.
    Rules: `get_costs` R1, R6"""
    KA = cost(db, S)
    cost(db, S, project_id=S.PJ2.id)
    cost_on(db, S, S.C2)
    commit_point(db)
    w1_id, ug_id, pj1_id, c2_id = S.W1.id, S.UG.id, S.PJ1.id, S.C2.id
    X, _x_id = extra_x(db, S)
    with spies(db) as (cm, rb):
        result = svc.get_costs(
            db,
            workspace_id=w1_id,
            user_id=ug_id,
            project_id=pj1_id,
            project_component_id=c2_id,
            limit=1000,
        )
    # Then 1
    assert idset(result) == {KA.id}
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert X in db


# [claude] MPCSV-L-02
def test_mpcsv_l_02__private_project_403_no_rollback(db, S):
    """MPCSV-L-02 — a private project is 403 and nothing is rolled back.
    Rules: `get_costs` R1, R6"""
    cost(db, S, project_id=S.PJP.id)
    commit_point(db)
    w1_id, ug_id, pjp_id = S.W1.id, S.UG.id, S.PJP.id
    X, _x_id = extra_x(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            svc.get_costs(
                db, workspace_id=w1_id, user_id=ug_id, project_id=pjp_id, limit=1000
            )
    assert exc.value.status_code == 403
    assert exc.value.detail == NOACCESS
    # Then 2
    assert rb.call_count == 0
    # Then 3
    assert X in db


# [claude] MPCSV-L-03
def test_mpcsv_l_03__foreign_project_404(db, S):
    """MPCSV-L-03 — another workspace's project is 404.
    Rules: `get_costs` R1"""
    cost(db, S, workspace_id=S.W2.id, project_id=S.PJ9.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_costs(
            db, workspace_id=S.W1.id, user_id=S.U2.id, project_id=S.PJ9.id, limit=1000
        )
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Project with ID {S.PJ9.id} not found"


# [claude] MPCSV-L-04
@pytest.mark.xfail(strict=True, reason=BUG_1278)
def test_mpcsv_l_04__deleted_project_404(db, S):
    """MPCSV-L-04 — a deleted project is 404.
    Rules: `get_costs` R1 (BUG-1278)"""
    cost(db, S, project_id=S.PJD.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_costs(
            db, workspace_id=S.W1.id, user_id=S.U2.id, project_id=S.PJD.id, limit=1000
        )
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Project with ID {S.PJD.id} not found"


# [claude] MPCSV-L-05
@pytest.mark.xfail(strict=True, reason=BUG_2614)
def test_mpcsv_l_05__project_id_0_does_not_exist(db, S):
    """MPCSV-L-05 — project id 0 is a project that does not exist; revisit after launch (owner 2026-11-10).
    Rules: `get_costs` R1 [BUG-2614]"""
    cost(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_costs(
            db, workspace_id=S.W1.id, user_id=S.U2.id, project_id=0, limit=1000
        )
    assert exc.value.status_code == 404
    assert exc.value.detail == "Project with ID 0 not found"


# [claude] MPCSV-L-06
def test_mpcsv_l_06__with_component_its_costs_only(db, S):
    """MPCSV-L-06 — with a component: that component's costs only.
    Rules: `get_costs` R2"""
    KA = cost(db, S, project_component_id=S.C1.id)
    cost(db, S)
    cost_on(db, S, S.C2)
    result = svc.get_costs(
        db,
        workspace_id=S.W1.id,
        user_id=S.UG.id,
        project_component_id=S.C1.id,
        limit=1000,
    )
    # Then 1
    assert idset(result) == {KA.id}


# [claude] MPCSV-L-07
def test_mpcsv_l_07__private_component_403(db, S):
    """MPCSV-L-07 — a component of a private project is 403.
    Rules: `get_costs` R2"""
    cost_on(db, S, S.CP)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_costs(
            db,
            workspace_id=S.W1.id,
            user_id=S.UG.id,
            project_component_id=S.CP.id,
            limit=1000,
        )
    assert exc.value.status_code == 403
    assert exc.value.detail == NOACCESS


# [claude] MPCSV-L-08
def test_mpcsv_l_08__foreign_component_404(db, S):
    """MPCSV-L-08 — another workspace's component is 404.
    Rules: `get_costs` R2"""
    cost(db, S, workspace_id=S.W2.id, project_id=None, project_component_id=S.C9.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_costs(
            db,
            workspace_id=S.W1.id,
            user_id=S.U2.id,
            project_component_id=S.C9.id,
            limit=1000,
        )
    assert exc.value.status_code == 404
    assert exc.value.detail == NOCOMP


# [claude] MPCSV-L-09
@pytest.mark.xfail(strict=True, reason=BUG_2614)
def test_mpcsv_l_09__component_id_0_does_not_exist(db, S):
    """MPCSV-L-09 — component id 0 is a component that does not exist; revisit after launch (owner 2026-11-10).
    Rules: `get_costs` R2 [BUG-2614]"""
    cost(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_costs(
            db,
            workspace_id=S.W1.id,
            user_id=S.U2.id,
            project_component_id=0,
            limit=1000,
        )
    assert exc.value.status_code == 404
    assert exc.value.detail == NOCOMP


# [claude] MPCSV-L-10
def test_mpcsv_l_10__workspace_wide_only_visible_w1_costs(db, S):
    """MPCSV-L-10 — workspace-wide: only W1's costs the caller may see.
    Rules: `get_costs` R3; `_filter_accessible_costs` R2, R4"""
    cost(db, S, workspace_id=S.W0.id, project_id=S.PJ0.id)
    KA = cost(db, S)
    cost(db, S, project_id=S.PJP.id)
    KC = cost_on(db, S, S.C2)
    cost_unlinked(db, S)
    cost_on(db, S, S.C9)
    cost(db, S, workspace_id=S.W2.id, project_id=S.PJ9.id)
    result = svc.get_costs(db, workspace_id=S.W1.id, user_id=S.UG.id, limit=1000)
    # Then 1
    assert idset(result) == {KA.id, KC.id}


# [claude] MPCSV-L-11
@pytest.mark.xfail(strict=True, reason=BUG_2612)
def test_mpcsv_l_11__workspace_wide_leaves_out_deleted_project(db, S):
    """MPCSV-L-11 — workspace-wide leaves out a deleted project's costs.
    Rules: `get_costs` R5 [BUG-2612]"""
    cost(db, S, project_id=S.PJD.id)
    KA = cost(db, S)
    result = svc.get_costs(db, workspace_id=S.W1.id, user_id=S.U2.id, limit=1000)
    # Then 1
    assert idset(result) == {KA.id}


# [claude] MPCSV-L-12
@pytest.mark.xfail(strict=False, reason=BUG_2611) # physical order can put the filtered-out row off the page (order sweep 2026-11-27)
def test_mpcsv_l_12__hidden_costs_take_no_place_on_page(db, S):
    """MPCSV-L-12 — hidden costs take no place on the page.
    Rules: `get_costs` R4 [BUG-2611]"""
    for _ in range(3):
        cost(db, S, project_id=S.PJP.id, name="Hidden")
    KA = cost(db, S, name="Open one")
    KB = cost(db, S, project_id=S.PJ2.id, name="Open two")
    result = svc.get_costs(db, workspace_id=S.W1.id, user_id=S.UG.id, skip=0, limit=2)
    # Then 1
    assert idset(result) == {KA.id, KB.id}


# [claude] MPCSV-L-13
@pytest.mark.xfail(strict=True, reason=BUG_2611)
def test_mpcsv_l_13__statements_do_not_grow_with_rows(db, S):
    """MPCSV-L-13 — the statements do not grow with the rows.
    Rules: `get_costs` R4 [BUG-2611]"""
    new_comps = []
    for k in range(5):
        c = ProjectComponent(
            workspace_id=S.W1.id, project_id=S.PJ2.id, name=f"Part {k}"
        )
        db.add(c)
        db.flush()
        new_comps.append(c)
    for c in new_comps:
        cost_on(db, S, c)
    commit_point(db)
    w1_id, ug_id = S.W1.id, S.UG.id
    stmts, stop = recorder(db)
    result = svc.get_costs(db, workspace_id=w1_id, user_id=ug_id, limit=1000)
    stop()
    # Then 1
    assert len(result) == 5
    # Then 2
    assert sum("FROM project_components" in s for s in stmts) <= 1


# [claude] MPCSV-L-14
@pytest.mark.xfail(strict=True, reason=BUG_100)
def test_mpcsv_l_14__workspace_query_orders_by_id(db, S):
    """MPCSV-L-14 — the workspace-wide query orders by id.
    Rules: `get_costs` R3 [BUG-100]"""
    KA = cost(db, S)
    w1_id, u2_id = S.W1.id, S.U2.id
    stmts, stop = recorder(db)
    result = svc.get_costs(db, workspace_id=w1_id, user_id=u2_id, limit=1000)
    stop()
    # Then 1
    assert idset(result) == {KA.id}
    # Then 2
    assert "id" in order_part(stmts)


# [claude] MPCSV-L-15
@pytest.mark.xfail(strict=False, reason=BUG_100)
def test_mpcsv_l_15__workspace_list_in_id_order(db, S):
    """MPCSV-L-15 — the workspace-wide list comes in id order.
    Rules: `get_costs` R3 [BUG-100]"""
    KA = cost(db, S, name="Aa")
    KB = cost(db, S, name="Bb")
    KC = cost(db, S, name="Cc")
    KA.name = "Zz"
    db.flush()
    result = svc.get_costs(db, workspace_id=S.W1.id, user_id=S.U2.id, limit=1000)
    # Then 1
    assert ids(result) == [KA.id, KB.id, KC.id]


# [claude] MPCSV-L-16
def test_mpcsv_l_16__limit_0_empty(db, S):
    """MPCSV-L-16 — limit 0 gives an empty list.
    Rules: `get_costs` R7"""
    cost(db, S)
    result = svc.get_costs(db, workspace_id=S.W1.id, user_id=S.U2.id, limit=0)
    # Then 1
    assert result == []


# [claude] MPCSV-L-17
def test_mpcsv_l_17__negative_limit_database_error(db, S):
    """MPCSV-L-17 — a negative limit is a database error.
    Rules: `get_costs` R7"""
    cost(db, S)
    # Then 1
    with pytest.raises(DataError):
        with db.begin_nested():
            svc.get_costs(db, workspace_id=S.W1.id, user_id=S.U2.id, limit=-1)


# [claude] MPCSV-L-18
def test_mpcsv_l_18__default_limit_100(db, S):
    """MPCSV-L-18 — the default limit is 100.
    Rules: `get_costs` R7"""
    for k in range(101):
        db.add(
            MiscellaneousProjectCost(
                workspace_id=S.W1.id,
                project_id=S.PJ1.id,
                name=f"Cost {k}",
                amount=Decimal("1.00"),
            )
        )
    db.flush()
    result = svc.get_costs(db, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 1
    assert len(result) == 100


# [claude] MPCSV-L-19
def test_mpcsv_l_19__skip_and_limit_page(db, S):
    """MPCSV-L-19 — skip and limit page the visible costs.
    Rules: `get_costs` R7"""
    KA = cost(db, S, name="A")
    KB = cost(db, S, name="B")
    KC = cost(db, S, name="C")
    KD = cost(db, S, name="D")
    result = svc.get_costs(db, workspace_id=S.W1.id, user_id=S.U2.id, skip=1, limit=2)
    # Then 1
    assert len(result) == 2
    # Then 2
    assert idset(result) <= {KA.id, KB.id, KC.id, KD.id}


# =========================================================================== #
# MiscellaneousProjectCostService.get_by_id
# =========================================================================== #


# [claude] MPCSV-G-01
def test_mpcsv_g_01__open_project_cost_returned_nothing_committed(db, S):
    """MPCSV-G-01 — a cost on an open project is returned, nothing committed.
    Rules: `get_by_id` R2, R5"""
    KA = cost(db, S)
    commit_point(db)
    ka_id, w1_id, ug_id = KA.id, S.W1.id, S.UG.id
    X, _x_id = extra_x(db, S)
    with spies(db) as (cm, rb):
        result = svc.get_by_id(db, cost_id=ka_id, workspace_id=w1_id, user_id=ug_id)
    # Then 1
    assert result.id == ka_id
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert X in db


# [claude] MPCSV-G-02
def test_mpcsv_g_02__unknown_id_none(db, S):
    """MPCSV-G-02 — an unknown id gives None.
    Rules: `get_by_id` R1"""
    cost(db, S)
    result = svc.get_by_id(db, cost_id=MISSING, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 1
    assert result is None


# [claude] MPCSV-G-03
def test_mpcsv_g_03__id_0_none(db, S):
    """MPCSV-G-03 — id 0 gives None.
    Rules: `get_by_id` R1"""
    cost(db, S)
    result = svc.get_by_id(db, cost_id=0, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 1
    assert result is None


# [claude] MPCSV-G-04
def test_mpcsv_g_04__w0_cost_not_found_in_w1(db, S):
    """MPCSV-G-04 — a W0 cost (lower id) is not found in W1.
    Rules: `get_by_id` R1"""
    K0 = cost(db, S, workspace_id=S.W0.id, project_id=S.PJ0.id)
    cost(db, S)
    result = svc.get_by_id(db, cost_id=K0.id, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 1
    assert result is None


# [claude] MPCSV-G-05
def test_mpcsv_g_05__w2_cost_not_found_in_w1(db, S):
    """MPCSV-G-05 — a W2 cost (higher id) is not found in W1.
    Rules: `get_by_id` R1"""
    cost(db, S)
    K9 = cost(db, S, workspace_id=S.W2.id, project_id=S.PJ9.id)
    result = svc.get_by_id(db, cost_id=K9.id, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 1
    assert result is None


# [claude] MPCSV-G-06
def test_mpcsv_g_06__private_project_cost_403_no_rollback(db, S):
    """MPCSV-G-06 — a private project's cost is 403, no rollback.
    Rules: `get_by_id` R2, R5"""
    KP = cost(db, S, project_id=S.PJP.id)
    commit_point(db)
    kp_id, w1_id, ug_id = KP.id, S.W1.id, S.UG.id
    X, _x_id = extra_x(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            svc.get_by_id(db, cost_id=kp_id, workspace_id=w1_id, user_id=ug_id)
    assert exc.value.status_code == 403
    assert exc.value.detail == NOACCESS
    # Then 2
    assert rb.call_count == 0
    # Then 3
    assert X in db


# [claude] MPCSV-G-07
def test_mpcsv_g_07__component_cost_checked_against_components_project(db, S):
    """MPCSV-G-07 — a component-only cost is checked against the component's project.
    Rules: `get_by_id` R2"""
    KC = cost_on(db, S, S.C1)
    result = svc.get_by_id(db, cost_id=KC.id, workspace_id=S.W1.id, user_id=S.UG.id)
    # Then 1
    assert result.id == KC.id


# [claude] MPCSV-G-08
def test_mpcsv_g_08__component_cost_on_private_project_403(db, S):
    """MPCSV-G-08 — a component-only cost on a private project is 403.
    Rules: `get_by_id` R2"""
    KC = cost_on(db, S, S.CP)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_by_id(db, cost_id=KC.id, workspace_id=S.W1.id, user_id=S.UG.id)
    assert exc.value.status_code == 403
    assert exc.value.detail == NOACCESS


# [claude] MPCSV-G-09
def test_mpcsv_g_09__both_links_checked_against_project(db, S):
    """MPCSV-G-09 — a cost with both links is checked against its project only.
    Rules: `get_by_id` R2"""
    KB = cost(db, S, project_component_id=S.CP.id)
    result = svc.get_by_id(db, cost_id=KB.id, workspace_id=S.W1.id, user_id=S.UG.id)
    # Then 1
    assert result.id == KB.id


# [claude] MPCSV-G-10
@pytest.mark.xfail(strict=True, reason=BUG_1278)
def test_mpcsv_g_10__deleted_project_cost_404(db, S):
    """MPCSV-G-10 — a deleted project's cost is 404.
    Rules: `get_by_id` R2 (BUG-1278)"""
    KD = cost(db, S, project_id=S.PJD.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_by_id(db, cost_id=KD.id, workspace_id=S.W1.id, user_id=S.U2.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Project with ID {S.PJD.id} not found"


# [claude] MPCSV-G-11
@pytest.mark.xfail(strict=True, reason=BUG_2616)
def test_mpcsv_g_11__foreign_component_cost_not_found(db, S):
    """MPCSV-G-11 — a stored cost naming another workspace's component is not found.
    Rules: `get_by_id` R3 [BUG-2616]"""
    KX = cost_on(db, S, S.C9)
    result = svc.get_by_id(db, cost_id=KX.id, workspace_id=S.W1.id, user_id=S.UG.id)
    # Then 1
    assert result is None


# [claude] MPCSV-G-12
def test_mpcsv_g_12__unlinked_cost_returned_to_any_member(db, S):
    """MPCSV-G-12 — an unlinked cost is returned to any member; revisit after launch (owner 2026-11-10).
    Rules: `get_by_id` R4"""
    KU = cost_unlinked(db, S)
    result = svc.get_by_id(db, cost_id=KU.id, workspace_id=S.W1.id, user_id=S.UG.id)
    # Then 1
    assert result.id == KU.id


# =========================================================================== #
# MiscellaneousProjectCostService.create_cost
# =========================================================================== #


def _create(db, w1_id, user_id, **fields):
    return svc.create_cost(
        db,
        cost_in=MiscellaneousProjectCostCreate(**fields),
        workspace_id=w1_id,
        user_id=user_id,
    )


# [claude] MPCSV-C-01
def test_mpcsv_c_01__project_cost_stored_committed_reread(db, S):
    """MPCSV-C-01 — a cost on a project is stored, committed once and re-read.
    Rules: `create_cost` R1, R6, R8 (M-TC1, M-TC2)"""
    commit_point(db)
    w1_id, ug_id, pj1_id = S.W1.id, S.UG.id, S.PJ1.id
    with spies(db) as (cm, rb):
        result = svc.create_cost(
            db,
            cost_in=MiscellaneousProjectCostCreate(
                project_id=pj1_id,
                name="Crane hire",
                description="Two days",
                amount=50.0,
            ),
            workspace_id=w1_id,
            user_id=ug_id,
        )
    # Then 1
    assert result.id is not None
    assert result.created_at is not None
    rid = result.id
    # Then 2
    assert cm.call_count == 1
    # Then 3
    assert rb.call_count == 0
    # Then 4
    db.rollback()
    row = committed_row(db, rid)
    assert row.workspace_id == w1_id
    assert row.project_id == pj1_id
    assert row.project_component_id is None
    # Then 5
    row = committed_row(db, rid)
    assert row.name == "Crane hire"
    assert row.description == "Two days"
    assert row.amount == Decimal("50.00")


# [claude] MPCSV-C-02
def test_mpcsv_c_02__project_create_logs_cost_added(db, S):
    """MPCSV-C-02 — creating on a project logs cost_added with component_id None.
    Rules: `create_cost` R7; `_log_cost_activity` R2"""
    commit_point(db)
    result = svc.create_cost(
        db,
        cost_in=MiscellaneousProjectCostCreate(
            project_id=S.PJ1.id, name="Crane hire", amount=50.0
        ),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.id is not None
    # Then 2
    evs = events(db, S.PJ1.id, "cost_added")
    assert len(evs) == 1
    # Then 3
    assert evs[0].workspace_id == S.W1.id
    assert evs[0].performed_by == S.UG.id
    assert evs[0].description == 'Added cost "Crane hire"'
    # Then 4
    assert evs[0].metadata_json == {
        "cost_id": result.id,
        "cost_name": "Crane hire",
        "component_id": None,
    }


# [claude] MPCSV-C-03
def test_mpcsv_c_03__component_create_logs_on_components_project(db, S):
    """MPCSV-C-03 — creating on a component logs on the component's project.
    Rules: `create_cost` R1, R7; `_log_cost_activity` R1"""
    commit_point(db)
    result = svc.create_cost(
        db,
        cost_in=MiscellaneousProjectCostCreate(
            project_component_id=S.C1.id, name="Scaffold", amount=20.0
        ),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.project_component_id == S.C1.id
    assert result.project_id is None
    # Then 2
    evs = events(db, S.PJ1.id, "cost_added")
    assert len(evs) == 1
    # Then 3
    assert evs[0].metadata_json == {
        "cost_id": result.id,
        "cost_name": "Scaffold",
        "component_id": S.C1.id,
        "component_name": "Roof",
    }


# [claude] MPCSV-C-04
def test_mpcsv_c_04__component_of_named_project_accepted(db, S):
    """MPCSV-C-04 — a component of the named project is accepted with both ids.
    Rules: `create_cost` R2 (the side that holds today and after BUG-2615)"""
    commit_point(db)
    result = svc.create_cost(
        db,
        cost_in=MiscellaneousProjectCostCreate(
            project_id=S.PJ1.id,
            project_component_id=S.C1.id,
            name="Scaffold",
            amount=20.0,
        ),
        workspace_id=S.W1.id,
        user_id=S.UG.id,
    )
    # Then 1
    assert result.project_id == S.PJ1.id
    assert result.project_component_id == S.C1.id
    # Then 2
    assert len(events(db, S.PJ1.id, "cost_added")) == 1


# [claude] MPCSV-C-05
def test_mpcsv_c_05__private_project_403_rolled_back_once(db, S):
    """MPCSV-C-05 — a private project is 403, rolled back once, pending changes discarded.
    Rules: `create_cost` R1, R8 (M-TC3)"""
    commit_point(db)
    w1_id, ug_id, pjp_id = S.W1.id, S.UG.id, S.PJP.id
    before = counts(db)
    _X, x_id = extra_x(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            _create(db, w1_id, ug_id, project_id=pjp_id, name="Crane hire", amount=50.0)
    assert exc.value.status_code == 403
    assert exc.value.detail == NOACCESS
    # Then 2
    assert rb.call_count == 1
    # Then 3
    assert x_count(db, x_id) == 0
    # Then 4
    assert counts(db) == before


# [claude] MPCSV-C-06
def test_mpcsv_c_06__private_component_403(db, S):
    """MPCSV-C-06 — a component of a private project is 403.
    Rules: `create_cost` R1"""
    commit_point(db)
    w1_id, ug_id, cp_id = S.W1.id, S.UG.id, S.CP.id
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _create(
            db, w1_id, ug_id, project_component_id=cp_id, name="Crane hire", amount=50.0
        )
    assert exc.value.status_code == 403
    assert exc.value.detail == NOACCESS
    # Then 2
    assert counts(db) == before


# [claude] MPCSV-C-07
def test_mpcsv_c_07__foreign_project_404(db, S):
    """MPCSV-C-07 — another workspace's project is 404.
    Rules: `create_cost` R1 (HR-16)"""
    commit_point(db)
    w1_id, u2_id, pj9_id = S.W1.id, S.U2.id, S.PJ9.id
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _create(db, w1_id, u2_id, project_id=pj9_id, name="Crane hire", amount=50.0)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Project with ID {pj9_id} not found"
    # Then 2
    assert counts(db) == before


# [claude] MPCSV-C-08
def test_mpcsv_c_08__foreign_component_alone_404(db, S):
    """MPCSV-C-08 — another workspace's component alone is 404.
    Rules: `create_cost` R1 (HR-16)"""
    commit_point(db)
    w1_id, u2_id, c9_id = S.W1.id, S.U2.id, S.C9.id
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _create(
            db, w1_id, u2_id, project_component_id=c9_id, name="Crane hire", amount=50.0
        )
    assert exc.value.status_code == 404
    assert exc.value.detail == NOCOMP
    # Then 2
    assert counts(db) == before


# [claude] MPCSV-C-09
@pytest.mark.xfail(strict=True, reason=BUG_1278)
def test_mpcsv_c_09__deleted_project_404(db, S):
    """MPCSV-C-09 — a deleted project is 404.
    Rules: `create_cost` R1 (BUG-1278)"""
    commit_point(db)
    w1_id, u2_id, pjd_id = S.W1.id, S.U2.id, S.PJD.id
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _create(db, w1_id, u2_id, project_id=pjd_id, name="Crane hire", amount=50.0)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Project with ID {pjd_id} not found"
    # Then 2
    assert counts(db) == before


# [claude] MPCSV-C-10
@pytest.mark.xfail(strict=True, reason=BUG_2614)
def test_mpcsv_c_10__project_id_0_refused_as_not_found(db, S):
    """MPCSV-C-10 — project id 0 is refused as not found; revisit after launch (owner 2026-11-10).
    Rules: `create_cost` R1 [BUG-2614]"""
    commit_point(db)
    w1_id, u2_id = S.W1.id, S.U2.id
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _create(db, w1_id, u2_id, project_id=0, name="Crane hire", amount=50.0)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Project with ID 0 not found"
    # Then 2
    assert counts(db) == before


# [claude] MPCSV-C-11
@pytest.mark.xfail(strict=True, reason=BUG_2614)
def test_mpcsv_c_11__component_id_0_refused_as_not_found(db, S):
    """MPCSV-C-11 — component id 0 is refused as not found; revisit after launch (owner 2026-11-10).
    Rules: `create_cost` R1 [BUG-2614]"""
    commit_point(db)
    w1_id, u2_id = S.W1.id, S.U2.id
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _create(
            db, w1_id, u2_id, project_component_id=0, name="Crane hire", amount=50.0
        )
    assert exc.value.status_code == 404
    assert exc.value.detail == NOCOMP
    # Then 2
    assert counts(db) == before


# [claude] MPCSV-C-12
@pytest.mark.xfail(strict=True, reason=BUG_2615)
def test_mpcsv_c_12__component_of_other_open_project_refused(db, S):
    """MPCSV-C-12 — a component of another open project is refused.
    Rules: `create_cost` R2 [BUG-2615]"""
    commit_point(db)
    w1_id, ug_id, pj2_id, c1_id = S.W1.id, S.UG.id, S.PJ2.id, S.C1.id
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _create(
            db,
            w1_id,
            ug_id,
            project_id=pj2_id,
            project_component_id=c1_id,
            name="Crane hire",
            amount=50.0,
        )
    assert exc.value.status_code == 400
    assert exc.value.detail == NOTPART
    # Then 2
    assert counts(db) == before


# [claude] MPCSV-C-13
@pytest.mark.xfail(strict=True, reason=BUG_2615)
def test_mpcsv_c_13__private_component_with_open_project_403(db, S):
    """MPCSV-C-13 — a private project's component named with an open project is 403, never 400.
    Rules: `create_cost` R2 [BUG-2615]"""
    commit_point(db)
    w1_id, ug_id, pj2_id, cp_id = S.W1.id, S.UG.id, S.PJ2.id, S.CP.id
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _create(
            db,
            w1_id,
            ug_id,
            project_id=pj2_id,
            project_component_id=cp_id,
            name="Crane hire",
            amount=50.0,
        )
    assert exc.value.status_code == 403
    assert exc.value.detail == NOACCESS
    # Then 2
    assert counts(db) == before


# [claude] MPCSV-C-14
@pytest.mark.xfail(strict=True, reason=BUG_1013)
def test_mpcsv_c_14__foreign_component_with_own_project_404(db, S):
    """MPCSV-C-14 — another workspace's component named with an own project is 404.
    Rules: `create_cost` R2 [BUG-1013]"""
    commit_point(db)
    w1_id, u2_id, pj1_id, c9_id = S.W1.id, S.U2.id, S.PJ1.id, S.C9.id
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _create(
            db,
            w1_id,
            u2_id,
            project_id=pj1_id,
            project_component_id=c9_id,
            name="Crane hire",
            amount=50.0,
        )
    assert exc.value.status_code == 404
    assert exc.value.detail == NOCOMP
    # Then 2
    assert counts(db) == before


# [claude] MPCSV-C-15
def test_mpcsv_c_15__neither_id_stored_unlinked_no_event(db, S):
    """MPCSV-C-15 — neither id: stored unlinked, no event; revisit after launch (owner 2026-11-10).
    Rules: `create_cost` R3"""
    commit_point(db)
    w1_id, ug_id = S.W1.id, S.UG.id
    result = _create(db, w1_id, ug_id, name="Crane hire", amount=50.0)
    # Then 1
    assert result.project_id is None
    assert result.project_component_id is None
    rid = result.id
    # Then 2
    db.rollback()
    row = committed_row(db, rid)
    assert row is not None
    assert row.workspace_id == w1_id
    # Then 3
    assert len(all_events(db, w1_id)) == 0


# [claude] MPCSV-C-16
@pytest.mark.xfail(strict=True, reason=BUG_2613)
def test_mpcsv_c_16__whitespace_name_refused_by_schema(S):
    """MPCSV-C-16 — a whitespace-only name is refused by the schema.
    Rules: `create_cost` R4 [BUG-2613]"""
    # Then 1
    with pytest.raises(PydanticValidationError):
        MiscellaneousProjectCostCreate(project_id=S.PJ1.id, name="  ", amount=50.0)


# [claude] MPCSV-C-17
@pytest.mark.xfail(strict=True, reason=BUG_2613)
def test_mpcsv_c_17__empty_name_refused_by_schema(S):
    """MPCSV-C-17 — an empty name is refused by the schema.
    Rules: `create_cost` R4 [BUG-2613]"""
    # Then 1
    with pytest.raises(PydanticValidationError):
        MiscellaneousProjectCostCreate(project_id=S.PJ1.id, name="", amount=50.0)


# [claude] MPCSV-C-18
@pytest.mark.xfail(strict=True, reason=BUG_2613)
def test_mpcsv_c_18__name_stored_trimmed(db, S):
    """MPCSV-C-18 — the name is stored trimmed.
    Rules: `create_cost` R4 [BUG-2613]"""
    commit_point(db)
    w1_id, ug_id, pj1_id = S.W1.id, S.UG.id, S.PJ1.id
    result = _create(
        db, w1_id, ug_id, project_id=pj1_id, name="  Crane  hire ", amount=50.0
    )
    # Then 1
    assert result.id is not None
    rid = result.id
    # Then 2
    db.rollback()
    assert committed_row(db, rid).name == "Crane  hire"


# [claude] MPCSV-C-19
def test_mpcsv_c_19__amount_rounded_half_up(db, S):
    """MPCSV-C-19 — the amount is rounded half up to 2 places; revisit after launch (owner 2026-11-10).
    Rules: `create_cost` R5"""
    commit_point(db)
    w1_id, ug_id, pj1_id = S.W1.id, S.UG.id, S.PJ1.id
    result = _create(
        db, w1_id, ug_id, project_id=pj1_id, name="Crane hire", amount=10.125
    )
    # Then 1
    assert result.amount == Decimal("10.13")
    rid = result.id
    # Then 2
    db.rollback()
    assert committed_row(db, rid).amount == Decimal("10.13")


# [claude] MPCSV-C-20
def test_mpcsv_c_20__negative_amount_stored(db, S):
    """MPCSV-C-20 — a negative amount is stored; revisit after launch (owner 2026-11-10).
    Rules: `create_cost` R5 (OQ-28)"""
    commit_point(db)
    w1_id, ug_id, pj1_id = S.W1.id, S.UG.id, S.PJ1.id
    result = _create(db, w1_id, ug_id, project_id=pj1_id, name="Refund", amount=-5)
    # Then 1
    assert result.amount == Decimal("-5.00")
    rid = result.id
    # Then 2
    db.rollback()
    assert committed_row(db, rid).amount == Decimal("-5.00")


# [claude] MPCSV-C-21
def test_mpcsv_c_21__13_integer_digits_fit(db, S):
    """MPCSV-C-21 — 13 integer digits fit.
    Rules: `create_cost` R5 [BUG-2618] (the side that holds today)"""
    commit_point(db)
    w1_id, ug_id, pj1_id = S.W1.id, S.UG.id, S.PJ1.id
    result = _create(
        db, w1_id, ug_id, project_id=pj1_id, name="Big", amount=9999999999999.0
    )
    # Then 1
    assert result.id is not None
    rid = result.id
    # Then 2
    db.rollback()
    assert committed_row(db, rid).amount == Decimal("9999999999999.00")


# [claude] MPCSV-C-22
@pytest.mark.xfail(strict=True, reason=BUG_2618)
def test_mpcsv_c_22__14_integer_digits_refused_by_schema(S):
    """MPCSV-C-22 — 14 integer digits are refused by the schema.
    Rules: `create_cost` R5 [BUG-2618]"""
    # Then 1
    with pytest.raises(PydanticValidationError):
        MiscellaneousProjectCostCreate(
            project_id=S.PJ1.id, name="Big", amount=10000000000000.0
        )


# [claude] MPCSV-C-23
def test_mpcsv_c_23__failing_commit_rolls_back_once(db, S):
    """MPCSV-C-23 — a failing commit rolls back once and saves nothing.
    Rules: `create_cost` R8 (M-TC4)"""
    commit_point(db)
    w1_id, ug_id, pj1_id = S.W1.id, S.UG.id, S.PJ1.id
    before = counts(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            _create(db, w1_id, ug_id, project_id=pj1_id, name="Crane hire", amount=50.0)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count == 1
    # Then 3
    assert counts(db) == before


# [claude] MPCSV-C-24
def test_mpcsv_c_24__failing_reread_keeps_cost(db, S):
    """MPCSV-C-24 — a failing re-read after the commit keeps the cost.
    Rules: `create_cost` R8 (M-TC5)"""
    commit_point(db)
    w1_id, ug_id, pj1_id = S.W1.id, S.UG.id, S.PJ1.id
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db):
            _create(db, w1_id, ug_id, project_id=pj1_id, name="Crane hire", amount=50.0)
    assert str(exc.value) == "boom"
    # Then 2
    db.rollback()
    n = db.scalar(
        select(func.count())
        .select_from(MiscellaneousProjectCost)
        .where(
            MiscellaneousProjectCost.workspace_id == w1_id,
            MiscellaneousProjectCost.name == "Crane hire",
        )
    )
    assert n == 1


# =========================================================================== #
# MiscellaneousProjectCostService.update_cost
# =========================================================================== #


def _update(db, cost_id, w1_id, user_id, cost_in):
    return svc.update_cost(
        db, cost_id=cost_id, cost_in=cost_in, workspace_id=w1_id, user_id=user_id
    )


# [claude] MPCSV-U-01
def test_mpcsv_u_01__rename_saved_committed_logged(db, S):
    """MPCSV-U-01 — a rename is saved, committed once, and logged.
    Rules: `update_cost` R2, R5, R6 (M-TC1, M-TC2)"""
    K = cost(db, S, description="Old")
    commit_point(db)
    k_id, w1_id, ug_id, pj1_id = K.id, S.W1.id, S.UG.id, S.PJ1.id
    with spies(db) as (cm, _rb):
        result = _update(
            db, k_id, w1_id, ug_id, MiscellaneousProjectCostUpdate(name="Crane hire")
        )
    # Then 1
    assert result.id == k_id
    assert result.name == "Crane hire"
    assert result.created_at is not None
    # Then 2
    assert cm.call_count == 1
    # Then 3
    db.rollback()
    row = committed_row(db, k_id)
    assert row.name == "Crane hire"
    assert row.description == "Old"
    assert row.amount == Decimal("100.00")
    # Then 4
    evs = events(db, pj1_id, "cost_updated")
    assert len(evs) == 1
    # Then 5
    assert evs[0].performed_by == ug_id
    assert evs[0].description == 'Updated cost "Crane hire"'
    assert evs[0].metadata_json == {
        "cost_id": k_id,
        "cost_name": "Crane hire",
        "component_id": None,
    }


# [claude] MPCSV-U-02
def test_mpcsv_u_02__null_fields_stay_amount_applied(db, S):
    """MPCSV-U-02 — null fields stay, a sent amount is applied.
    Rules: `update_cost` R2, R4"""
    K = cost(db, S, description="Old")
    commit_point(db)
    k_id, w1_id, ug_id = K.id, S.W1.id, S.UG.id
    result = _update(
        db,
        k_id,
        w1_id,
        ug_id,
        MiscellaneousProjectCostUpdate(name=None, description=None, amount=7.5),
    )
    # Then 1
    assert result.amount == Decimal("7.50")
    # Then 2
    db.rollback()
    row = committed_row(db, k_id)
    assert row.name == "Crane"
    assert row.description == "Old"
    assert row.amount == Decimal("7.50")


# [claude] MPCSV-U-03
def test_mpcsv_u_03__unknown_id_none_no_commit_no_rollback(db, S):
    """MPCSV-U-03 — an unknown id gives None, no commit, no rollback.
    Rules: `update_cost` R1 (M-TC6)"""
    K = cost(db, S)
    commit_point(db)
    before = snap(db, K)
    w1_id, u2_id = S.W1.id, S.U2.id
    X, _x_id = extra_x(db, S)
    with spies(db) as (cm, rb):
        result = _update(
            db, MISSING, w1_id, u2_id, MiscellaneousProjectCostUpdate(name="New")
        )
    # Then 1
    assert result is None
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert X in db
    # Then 5
    assert unchanged(db, before)


# [claude] MPCSV-U-04
def test_mpcsv_u_04__w2_cost_not_found_in_w1(db, S):
    """MPCSV-U-04 — a W2 cost is not found in W1.
    Rules: `update_cost` R1"""
    K9 = cost(db, S, workspace_id=S.W2.id, project_id=S.PJ9.id)
    commit_point(db)
    before = snap(db, K9)
    result = _update(
        db, K9.id, S.W1.id, S.U2.id, MiscellaneousProjectCostUpdate(name="New")
    )
    # Then 1
    assert result is None
    # Then 2
    assert unchanged(db, before)


# [claude] MPCSV-U-05
def test_mpcsv_u_05__private_project_cost_403_rolled_back(db, S):
    """MPCSV-U-05 — a private project's cost is 403, rolled back, unchanged.
    Rules: `update_cost` R1 (M-TC3)"""
    KP = cost(db, S, project_id=S.PJP.id)
    commit_point(db)
    before = snap(db, KP)
    kp_id, w1_id, ug_id = KP.id, S.W1.id, S.UG.id
    _X, x_id = extra_x(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            _update(db, kp_id, w1_id, ug_id, MiscellaneousProjectCostUpdate(name="New"))
    assert exc.value.status_code == 403
    assert exc.value.detail == NOACCESS
    # Then 2
    assert rb.call_count == 1
    # Then 3
    assert x_count(db, x_id) == 0
    # Then 4
    assert unchanged(db, before)


# [claude] MPCSV-U-06
@pytest.mark.xfail(strict=True, reason=BUG_2616)
def test_mpcsv_u_06__foreign_component_cost_not_found(db, S):
    """MPCSV-U-06 — a stored cost naming another workspace's component is not found.
    Rules: `update_cost` R1 [BUG-2616]"""
    KX = cost_on(db, S, S.C9)
    commit_point(db)
    before = snap(db, KX)
    result = _update(
        db, KX.id, S.W1.id, S.UG.id, MiscellaneousProjectCostUpdate(name="New")
    )
    # Then 1
    assert result is None
    # Then 2
    assert unchanged(db, before)


# [claude] MPCSV-U-07
def test_mpcsv_u_07__empty_update_returns_cost_unchanged(db, S):
    """MPCSV-U-07 — an empty update returns the cost unchanged.
    Rules: `update_cost` R2, R6 (the side independent of BUG-2617)"""
    K = cost(db, S)
    commit_point(db)
    before = snap(db, K)
    k_id = K.id
    result = _update(db, k_id, S.W1.id, S.UG.id, MiscellaneousProjectCostUpdate())
    # Then 1
    assert result.id == k_id
    # Then 2
    assert unchanged(db, before)


# [claude] MPCSV-U-08
@pytest.mark.xfail(strict=True, reason=BUG_2617)
def test_mpcsv_u_08__empty_update_writes_no_event(db, S):
    """MPCSV-U-08 — an empty update writes no event.
    Rules: `update_cost` R5 [BUG-2617]"""
    K = cost(db, S)
    commit_point(db)
    k_id = K.id
    result = _update(db, k_id, S.W1.id, S.UG.id, MiscellaneousProjectCostUpdate())
    # Then 1
    assert result.id == k_id
    # Then 2
    assert len(events(db, S.PJ1.id, "cost_updated")) == 0


# [claude] MPCSV-U-09
@pytest.mark.xfail(strict=True, reason=BUG_2617)
def test_mpcsv_u_09__same_values_write_no_event(db, S):
    """MPCSV-U-09 — the same values again write no event.
    Rules: `update_cost` R5 [BUG-2617]"""
    K = cost(db, S)
    commit_point(db)
    result = _update(
        db,
        K.id,
        S.W1.id,
        S.UG.id,
        MiscellaneousProjectCostUpdate(name="Crane", amount=100.0),
    )
    # Then 1
    assert result.name == "Crane"
    # Then 2
    assert len(events(db, S.PJ1.id, "cost_updated")) == 0


# [claude] MPCSV-U-10
def test_mpcsv_u_10__component_cost_update_logs_on_components_project(db, S):
    """MPCSV-U-10 — a component cost's update logs on the component's project.
    Rules: `update_cost` R5; `_log_cost_activity` R1"""
    K = cost_on(db, S, S.C1)
    commit_point(db)
    k_id = K.id
    result = _update(
        db, k_id, S.W1.id, S.UG.id, MiscellaneousProjectCostUpdate(name="Scaffold")
    )
    # Then 1
    assert result.name == "Scaffold"
    # Then 2
    evs = events(db, S.PJ1.id, "cost_updated")
    assert len(evs) == 1
    # Then 3
    assert evs[0].metadata_json == {
        "cost_id": k_id,
        "cost_name": "Scaffold",
        "component_id": S.C1.id,
        "component_name": "Roof",
    }


# [claude] MPCSV-U-11
def test_mpcsv_u_11__unlinked_update_writes_no_event(db, S):
    """MPCSV-U-11 — an unlinked cost's update writes no event; revisit after launch (owner 2026-11-10).
    Rules: `update_cost` R5"""
    KU = cost_unlinked(db, S)
    commit_point(db)
    w1_id = S.W1.id
    result = _update(
        db, KU.id, w1_id, S.UG.id, MiscellaneousProjectCostUpdate(name="Scaffold")
    )
    # Then 1
    assert result.name == "Scaffold"
    # Then 2
    assert len(all_events(db, w1_id)) == 0


# [claude] MPCSV-U-12
@pytest.mark.xfail(strict=True, reason=BUG_2613)
def test_mpcsv_u_12__blank_name_refused_by_update_schema():
    """MPCSV-U-12 — a blank name is refused by the update schema.
    Rules: `update_cost` R3 [BUG-2613]"""
    # Then 1
    with pytest.raises(PydanticValidationError):
        MiscellaneousProjectCostUpdate(name="  ")


# [claude] MPCSV-U-13
@pytest.mark.xfail(strict=True, reason=BUG_2618)
def test_mpcsv_u_13__14_integer_digits_refused_by_update_schema():
    """MPCSV-U-13 — 14 integer digits are refused by the update schema.
    Rules: `update_cost` R4 [BUG-2618]"""
    # Then 1
    with pytest.raises(PydanticValidationError):
        MiscellaneousProjectCostUpdate(amount=10000000000000.0)


# [claude] MPCSV-U-14
def test_mpcsv_u_14__failing_commit_rolls_back_cost_unchanged(db, S):
    """MPCSV-U-14 — a failing commit rolls back once and the cost is unchanged.
    Rules: `update_cost` R6 (M-TC4)"""
    K = cost(db, S)
    commit_point(db)
    before = snap(db, K)
    before_counts = counts(db)
    k_id, w1_id, ug_id = K.id, S.W1.id, S.UG.id
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            _update(db, k_id, w1_id, ug_id, MiscellaneousProjectCostUpdate(name="New"))
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count == 1
    # Then 3
    assert unchanged(db, before)
    # Then 4
    assert counts(db) == before_counts


# [claude] MPCSV-U-15
def test_mpcsv_u_15__failing_reread_keeps_rename(db, S):
    """MPCSV-U-15 — a failing re-read after the commit keeps the rename.
    Rules: `update_cost` R6 (M-TC5)"""
    K = cost(db, S)
    commit_point(db)
    k_id, w1_id, ug_id = K.id, S.W1.id, S.UG.id
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db):
            _update(db, k_id, w1_id, ug_id, MiscellaneousProjectCostUpdate(name="New"))
    assert str(exc.value) == "boom"
    # Then 2
    db.rollback()
    assert committed_row(db, k_id).name == "New"


# =========================================================================== #
# MiscellaneousProjectCostService.delete_cost
# =========================================================================== #


# [claude] MPCSV-D-01
def test_mpcsv_d_01__delete_removes_row_keeps_event(db, S):
    """MPCSV-D-01 — delete removes the row, keeps the event, commits once.
    Rules: `delete_cost` R2, R3 (M-TC1)"""
    K = cost(db, S)
    commit_point(db)
    k_id, w1_id, ug_id, pj1_id = K.id, S.W1.id, S.UG.id, S.PJ1.id
    with spies(db) as (cm, _rb):
        result = svc.delete_cost(db, cost_id=k_id, workspace_id=w1_id, user_id=ug_id)
    # Then 1
    assert result is True
    # Then 2
    assert cm.call_count == 1
    # Then 3
    db.rollback()
    assert committed_row(db, k_id) is None
    # Then 4
    evs = events(db, pj1_id, "cost_deleted")
    assert len(evs) == 1
    # Then 5
    assert evs[0].performed_by == ug_id
    assert evs[0].description == 'Deleted cost "Crane"'
    assert evs[0].metadata_json == {
        "cost_id": k_id,
        "cost_name": "Crane",
        "component_id": None,
    }


# [claude] MPCSV-D-02
def test_mpcsv_d_02__unknown_id_false_no_commit_no_rollback(db, S):
    """MPCSV-D-02 — an unknown id gives False, no commit, no rollback.
    Rules: `delete_cost` R1"""
    K = cost(db, S)
    commit_point(db)
    before = snap(db, K)
    w1_id, u2_id = S.W1.id, S.U2.id
    X, _x_id = extra_x(db, S)
    with spies(db) as (cm, rb):
        result = svc.delete_cost(db, cost_id=MISSING, workspace_id=w1_id, user_id=u2_id)
    # Then 1
    assert result is False
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert X in db
    # Then 5
    assert unchanged(db, before)


# [claude] MPCSV-D-03
def test_mpcsv_d_03__w0_cost_not_found_in_w1(db, S):
    """MPCSV-D-03 — a W0 cost is not found in W1.
    Rules: `delete_cost` R1"""
    K0 = cost(db, S, workspace_id=S.W0.id, project_id=S.PJ0.id)
    commit_point(db)
    before = snap(db, K0)
    result = svc.delete_cost(db, cost_id=K0.id, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 1
    assert result is False
    # Then 2
    assert unchanged(db, before)


# [claude] MPCSV-D-04
def test_mpcsv_d_04__private_project_cost_403_rolled_back_kept(db, S):
    """MPCSV-D-04 — a private project's cost is 403, rolled back, kept.
    Rules: `delete_cost` R1, R3 (M-TC3)"""
    KP = cost(db, S, project_id=S.PJP.id)
    commit_point(db)
    before = snap(db, KP)
    kp_id, w1_id, ug_id = KP.id, S.W1.id, S.UG.id
    _X, x_id = extra_x(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            svc.delete_cost(db, cost_id=kp_id, workspace_id=w1_id, user_id=ug_id)
    assert exc.value.status_code == 403
    assert exc.value.detail == NOACCESS
    # Then 2
    assert rb.call_count == 1
    # Then 3
    assert x_count(db, x_id) == 0
    # Then 4
    assert unchanged(db, before)


# [claude] MPCSV-D-05
@pytest.mark.xfail(strict=True, reason=BUG_2616)
def test_mpcsv_d_05__foreign_component_cost_not_found(db, S):
    """MPCSV-D-05 — a stored cost naming another workspace's component is not found.
    Rules: `delete_cost` R1 [BUG-2616]"""
    KX = cost_on(db, S, S.C9)
    commit_point(db)
    before = snap(db, KX)
    result = svc.delete_cost(db, cost_id=KX.id, workspace_id=S.W1.id, user_id=S.UG.id)
    # Then 1
    assert result is False
    # Then 2
    assert unchanged(db, before)


# [claude] MPCSV-D-06
def test_mpcsv_d_06__unlinked_cost_deleted_no_event(db, S):
    """MPCSV-D-06 — an unlinked cost is deleted with no event; revisit after launch (owner 2026-11-10).
    Rules: `delete_cost` R2"""
    KU = cost_unlinked(db, S)
    commit_point(db)
    ku_id, w1_id = KU.id, S.W1.id
    result = svc.delete_cost(db, cost_id=ku_id, workspace_id=w1_id, user_id=S.UG.id)
    # Then 1
    assert result is True
    # Then 2
    db.rollback()
    assert committed_row(db, ku_id) is None
    # Then 3
    assert len(all_events(db, w1_id)) == 0


# [claude] MPCSV-D-07
def test_mpcsv_d_07__failing_commit_keeps_cost_no_event(db, S):
    """MPCSV-D-07 — a failing commit keeps the cost and writes no event.
    Rules: `delete_cost` R3 (M-TC4)"""
    K = cost(db, S)
    commit_point(db)
    before = snap(db, K)
    before_counts = counts(db)
    k_id, w1_id, ug_id = K.id, S.W1.id, S.UG.id
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.delete_cost(db, cost_id=k_id, workspace_id=w1_id, user_id=ug_id)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count == 1
    # Then 3
    assert unchanged(db, before)
    # Then 4
    assert counts(db) == before_counts
