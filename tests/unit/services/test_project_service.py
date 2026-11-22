"""Unit tests for app/services/project_service.py.

Implements tests/unit/services/project_service.cases.md (revision 4), one test
per card, in card order. Real Postgres session (`db` fixture): a `commit()`
only releases a savepoint, so the service's commits are safe and the fixture's
outer rollback discards everything. Patched in every test: the manager's clock
`app.managers.project_manager.utcnow` (Conventions, Externals); per card the
spies, failing commit and failing refresh of the Conventions.

Every test builds the Standing rows (fixture `S`, attributes named as in the
cards: `S.W1`, `S.UG`, `S.F1` ...). Given rows are built by the helpers below
(`proj`, `member`, `pmem`, `ev`, `bulk`), one flush per row. `# [claude] <ID>`
sits above each test; `# Then N` marks the checks of the card's Then line N.
"""

# ruff: noqa: SIM117, DTZ001, FURB157  (Conventions prescribe the nested `with` and naive
# datetimes; Decimals are written as the cards write them)
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from inspect import signature
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import event, func, insert, inspect, select
from sqlalchemy.exc import DataError

from app.api.v1.endpoints.projects import list_project_members
from app.models.enums import ProjectStatusEnum, ProjectVisibilityEnum
from app.models.factory import Factory
from app.models.project import Project
from app.models.project_event import ProjectEvent
from app.models.project_member import ProjectMember
from app.models.workspace_member import WorkspaceMember
from app.schemas.project import (
    ProjectCreate,
    ProjectMembersListResponse,
    ProjectUpdate,
)
from app.services.project_service import project_service
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

svc = project_service
MISSING = 999999999
T1 = datetime(2026, 1, 1, 9, 0, 0)
T2 = datetime(2026, 1, 1, 10, 0, 0)
T3 = datetime(2026, 1, 1, 11, 0, 0)
NOW = datetime(2026, 3, 1, 10, 0, 0)
DENIED = "You do not have access to this project"


def xfail(bug):
    # Convention "xfail BUG-n": strict
    return pytest.mark.xfail(strict=True, reason=bug)


def idset(rows):
    return {r.id for r in rows}


def names(rows):
    return [r.name for r in rows]


def val(x):
    return getattr(x, "value", x)


# --------------------------------------------------------------------------- #
# Externals: the manager's clock, in every test
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


# Given row "member(U, role, status="active")" (W1)
def member(db, S, u, role, status="active"):
    return _add(
        db,
        WorkspaceMember(workspace_id=S.W1.id, user_id=u.id, role=role, status=status),
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
    s.F2 = _add(
        db, Factory(workspace_id=s.W1.id, name="Factory Two", abbreviation="F2")
    )
    s.FD = _add(
        db,
        Factory(
            workspace_id=s.W1.id, name="Old Plant", abbreviation="OP", is_deleted=True
        ),
    )
    s.F9 = _add(
        db, Factory(workspace_id=s.W2.id, name="Factory Nine", abbreviation="F9")
    )
    return s


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #


def proj(db, S, name, where="W1", private=False, deleted=False, **but):
    """proj / W0 proj / W2 proj; `private`, `deleted` as Conventions; `but` = the columns after "but"."""
    ws = getattr(S, where)
    factory = {"W0": S.F0, "W1": S.F1, "W2": S.F9}[where]
    fields = {
        "workspace_id": ws.id,
        "factory_id": factory.id,
        "name": name,
        "description": "Main",
        "created_by": S.U1.id,
    }
    if private:
        fields["visibility"] = "invited_only"
    if deleted:
        fields.update(is_deleted=True, deleted_at=T1, deleted_by=S.U1.id)
    fields.update(but)
    return _add(db, Project(**fields))


def pmem(db, S, p, u, **but):
    fields = {
        "workspace_id": p.workspace_id,
        "project_id": p.id,
        "user_id": u.id,
        "assigned_by": S.U1.id,
    }
    fields.update(but)
    return _add(db, ProjectMember(**fields))


def ev(db, p, event_type, at, by):
    return _add(
        db,
        ProjectEvent(
            workspace_id=p.workspace_id,
            project_id=p.id,
            event_type=event_type,
            description="seed",
            performed_by=by,
            created_at=at,
            metadata_json=None,
        ),
    )


def bulk(db, S, n):
    db.execute(
        insert(Project),
        [
            {
                "workspace_id": S.W1.id,
                "factory_id": S.F1.id,
                "name": f"P{i:05d}",
                "description": "Main",
                "created_by": S.U1.id,
                "visibility": "workspace",
            }
            for i in range(n)
        ],
    )
    db.expire_all()


# Convention "commit point"
def commit_point(db):
    db.commit()


# Convention "extra row X" (after the commit point); returns X_ID
def extra_x(db, S):
    x = _add(
        db,
        Project(
            workspace_id=S.W2.id,
            factory_id=S.F9.id,
            name="Extra",
            description="Extra",
            created_by=S.U2.id,
        ),
    )
    return x.id


def x_count(db, x_id):
    """x_gone: == 0; x_kept: == 1."""
    return db.scalar(
        select(func.count()).select_from(Project).where(Project.id == x_id)
    )


# Convention "edit A"
def edit(row):
    row.description = "Edited"


# --------------------------------------------------------------------------- #
# Named checks
# --------------------------------------------------------------------------- #


def _columns(model):
    return [c.key for c in inspect(model).mapper.column_attrs]


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
    """'nothing written': row counts of projects, project_members, project_events."""
    return tuple(
        db.scalar(select(func.count()).select_from(m))
        for m in (Project, ProjectMember, ProjectEvent)
    )


def events_of(db, p_id):
    db.expire_all()
    return (
        db.execute(
            select(ProjectEvent)
            .where(ProjectEvent.project_id == p_id)
            .order_by(ProjectEvent.id)
        )
        .scalars()
        .all()
    )


def members_of(db, p_id):
    db.expire_all()
    return (
        db.execute(
            select(ProjectMember)
            .where(ProjectMember.project_id == p_id)
            .order_by(ProjectMember.id)
        )
        .scalars()
        .all()
    )


def w1_projects(db, S):
    return (
        db.execute(select(Project).where(Project.workspace_id == S.W1.id))
        .scalars()
        .all()
    )


@contextmanager
def spies(db):
    with (
        patch.object(db, "commit", wraps=db.commit) as cm,
        patch.object(db, "rollback", wraps=db.rollback) as rb,
        patch.object(db, "refresh", wraps=db.refresh) as rf,
    ):
        yield cm, rb, rf


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
# create_project
# =========================================================================== #


# [claude] PJS-C-01
def test_pjs_c_01__project_member_and_event_committed(db, S):
    """PJS-C-01 — the project, its creator's membership and the created event are committed; returned re-read.
    Rules: create_project R1; TC1, TC2."""
    commit_point(db)
    result = svc.create_project(
        db,
        project_in=ProjectCreate(
            factory_id=S.F1.id, name="Roof job", description="Main"
        ),
        workspace_id=S.W1.id,
        user_id=S.U2.id,
    )
    # Then 1
    assert isinstance(result, Project)
    # Then 2
    assert result.id is not None
    assert result.created_at is not None
    # Then 3
    assert not (
        {c.key for c in inspect(result).mapper.column_attrs}
        & inspect(result).expired_attributes
    )
    rid = result.id
    db.rollback()
    # Then 4
    row = reread(db, Project, rid)
    assert row is not None
    assert row.name == "Roof job"
    assert row.workspace_id == S.W1.id
    assert row.created_by == S.U2.id
    # Then 5
    mems = members_of(db, rid)
    assert len(mems) == 1
    assert mems[0].user_id == S.U2.id
    # Then 6
    evs = events_of(db, rid)
    assert len(evs) == 1
    assert evs[0].event_type == "created"


# [claude] PJS-C-02
def test_pjs_c_02__unknown_factory_404_rolled_back(db, S):
    """PJS-C-02 — an unknown factory is 404, rolled back with every pending change.
    Rules: create_project R2; TC3."""
    commit_point(db)
    before = counts(db)
    x_id = extra_x(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_project(
            db,
            project_in=ProjectCreate(
                factory_id=MISSING, name="Roof job", description="Main"
            ),
            workspace_id=S.W1.id,
            user_id=S.U2.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory with ID 999999999 not found"
    # Then 4
    assert not db.new and not db.dirty
    # Then 5
    assert x_count(db, x_id) == 0
    # Then 6
    assert counts(db) == before


# [claude] PJS-C-03
def test_pjs_c_03__deleted_factory_400_rolled_back(db, S):
    """PJS-C-03 — a soft-deleted factory is 400, rolled back with every pending change.
    Rules: create_project R2; TC3."""
    commit_point(db)
    before = counts(db)
    x_id = extra_x(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_project(
            db,
            project_in=ProjectCreate(
                factory_id=S.FD.id, name="Roof job", description="Main"
            ),
            workspace_id=S.W1.id,
            user_id=S.U2.id,
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot create project for deleted factory"
    # Then 4
    assert not db.new and not db.dirty
    # Then 5
    assert x_count(db, x_id) == 0
    # Then 6
    assert counts(db) == before


# [claude] PJS-C-04
def test_pjs_c_04__database_error_passes_rolled_back(db, S):
    """PJS-C-04 — a database error passes unchanged, rolled back, and the session stays usable.
    Rules: create_project R3, R4; TC3."""
    commit_point(db)
    before = counts(db)
    x_id = extra_x(db, S)
    # Then 1
    with pytest.raises(DataError):
        svc.create_project(
            db,
            project_in=ProjectCreate.model_construct(
                factory_id=S.F1.id,
                name="Roof job",
                description="Main",
                budget=Decimal("100000000000000000000"),
            ),
            workspace_id=S.W1.id,
            user_id=S.U2.id,
        )
    # Then 2
    assert x_count(db, x_id) == 0
    # Then 3
    assert counts(db) == before
    # Then 4
    assert (
        db.scalar(
            select(func.count())
            .select_from(Project)
            .where(Project.workspace_id == S.W1.id)
        )
        == 0
    )


# [claude] PJS-C-05
def test_pjs_c_05__failing_commit_rolls_back(db, S):
    """PJS-C-05 — a failing commit rolls back and nothing is saved.
    Rules: create_project R3; TC4."""
    commit_point(db)
    before = counts(db)
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.create_project(
                db,
                project_in=ProjectCreate(
                    factory_id=S.F1.id, name="Roof job", description="Main"
                ),
                workspace_id=S.W1.id,
                user_id=S.U2.id,
            )
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert counts(db) == before


# [claude] PJS-C-06
def test_pjs_c_06__failing_refresh_leaves_all_saved(db, S):
    """PJS-C-06 — a failing re-read after the commit leaves the project, member and event saved.
    Rules: create_project R3; TC5."""
    commit_point(db)
    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db):
            svc.create_project(
                db,
                project_in=ProjectCreate(
                    factory_id=S.F1.id, name="Roof job", description="Main"
                ),
                workspace_id=S.W1.id,
                user_id=S.U2.id,
            )
    # Then 1
    assert str(exc.value) == "boom"
    db.rollback()
    # Then 2
    rows = w1_projects(db, S)
    assert len(rows) == 1
    assert rows[0].name == "Roof job"
    # Then 3
    assert len(members_of(db, rows[0].id)) == 1
    assert len(events_of(db, rows[0].id)) == 1


# [claude] PJS-C-07
@xfail("BUG-1951")
def test_pjs_c_07__name_stored_trimmed(db, S):
    """PJS-C-07 — the name is stored trimmed (pass-through).
    Rules: create_project R1 (manager R4 [BUG-1951])."""
    commit_point(db)
    result = svc.create_project(
        db,
        project_in=ProjectCreate(
            factory_id=S.F1.id, name="  Line 3 refit ", description="Main"
        ),
        workspace_id=S.W1.id,
        user_id=S.U2.id,
    )
    # Then 1
    assert result.id is not None
    rid = result.id
    db.rollback()
    # Then 2
    assert reread(db, Project, rid).name == "Line 3 refit"


# =========================================================================== #
# get_project
# =========================================================================== #


# [claude] PJS-G-01
def test_pjs_g_01__returns_workspace_project(db, S):
    """PJS-G-01 — returns the workspace's project.
    Rules: get_project R1."""
    proj(db, S, "Zero", where="W0")
    p = proj(db, S, "Roof job")
    proj(db, S, "Nine", where="W2")
    result = svc.get_project(db, project_id=p.id, workspace_id=S.W1.id, user_id=S.UG.id)
    # Then 1
    assert result.id == p.id
    # Then 2
    assert result.name == "Roof job"


# [claude] PJS-G-02
def test_pjs_g_02__private_project_403_passes(db, S):
    """PJS-G-02 — a private project the caller may not open: the manager's 403 passes unchanged.
    Rules: get_project R1."""
    p = proj(db, S, "Secret", private=True)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_project(db, project_id=p.id, workspace_id=S.W1.id, user_id=S.UG.id)
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == DENIED


# [claude] PJS-G-03
def test_pjs_g_03__other_workspace_404_no_rollback(db, S):
    """PJS-G-03 — another workspace's project is 404, and a pending change survives (no rollback).
    Rules: get_project R1, R2; TC6."""
    proj(db, S, "Roof job")
    p9 = proj(db, S, "Nine", where="W2")
    p9_id = p9.id
    commit_point(db)
    x_id = extra_x(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb, _rf):
            svc.get_project(db, project_id=p9_id, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project with ID {p9_id} not found"
    # Then 4
    assert rb.call_count == 0
    # Then 5
    assert x_count(db, x_id) == 1


# [claude] PJS-G-04
@xfail("BUG-1954")
def test_pjs_g_04__deleted_project_404(db, S):
    """PJS-G-04 — a soft-deleted project is 404 (pass-through).
    Rules: get_project R1 [BUG-1954]."""
    p = proj(db, S, "Gone", deleted=True)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_project(db, project_id=p.id, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project with ID {p.id} not found"


# [claude] PJS-G-05
def test_pjs_g_05__get_neither_commits_nor_rolls_back(db, S):
    """PJS-G-05 — a get neither commits nor rolls back; the caller's edit stays.
    Rules: get_project R2; TC6."""
    a = proj(db, S, "Alpha")
    edit(a)
    with spies(db) as (cm, rb, _rf):
        result = svc.get_project(
            db, project_id=a.id, workspace_id=S.W1.id, user_id=S.U2.id
        )
    # Then 1
    assert result.id == a.id
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert a in db.dirty
    # Then 5
    assert a.description == "Edited"


# [claude] PJS-G-06
def test_pjs_g_06__no_include_deleted_argument(db):
    """PJS-G-06 — the service takes no include_deleted argument.
    Rules: get_project R2."""
    params = signature(svc.get_project).parameters
    # Then 1
    assert "include_deleted" not in params
    # Then 2
    assert list(params) == ["db", "project_id", "workspace_id", "user_id"]


# [claude] PJS-G-07
def test_pjs_g_07__w0_project_404_in_w1(db, S):
    """PJS-G-07 — a W0 project (lower id) is 404 in W1.
    Rules: get_project R1."""
    p0 = proj(db, S, "Zero", where="W0")
    proj(db, S, "Roof job")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_project(db, project_id=p0.id, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project with ID {p0.id} not found"


# =========================================================================== #
# list_projects
# =========================================================================== #


# [claude] PJS-L-01
def test_pjs_l_01__privileged_sees_private_too(db, S):
    """PJS-L-01 — a privileged caller gets the workspace's live projects, private ones included.
    Rules: list_projects R1."""
    proj(db, S, "Zero", where="W0")
    pa = proj(db, S, "Alpha")
    pv = proj(db, S, "Vault", private=True)
    proj(db, S, "Nine", where="W2")
    result = svc.list_projects(db, workspace_id=S.W1.id, user_id=S.U2.id, limit=1000)
    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert idset(result) == {pa.id, pv.id}


# [claude] PJS-L-02
def test_pjs_l_02__default_page_holds_100(db, S):
    """PJS-L-02 — with nothing after user_id the page holds 100.
    Rules: list_projects R1 (default limit=100, skip=0)."""
    bulk(db, S, 101)
    result = svc.list_projects(db, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 1
    assert len(result) == 100


# [claude] PJS-L-03
def test_pjs_l_03__limit_1000_returns_all(db, S):
    """PJS-L-03 — limit 1000 returns all 101.
    Rules: list_projects R1."""
    bulk(db, S, 101)
    result = svc.list_projects(db, workspace_id=S.W1.id, user_id=S.U2.id, limit=1000)
    # Then 1
    assert len(result) == 101


# [claude] PJS-L-04
def test_pjs_l_04__skip_passed_on(db, S):
    """PJS-L-04 — skip is passed on: 100 of 101 leaves one.
    Rules: list_projects R1."""
    bulk(db, S, 101)
    result = svc.list_projects(
        db, workspace_id=S.W1.id, user_id=S.U2.id, skip=100, limit=1000
    )
    # Then 1
    assert len(result) == 1


# [claude] PJS-L-05
def test_pjs_l_05__factory_id_passed_on(db, S):
    """PJS-L-05 — factory_id is passed on.
    Rules: list_projects R1."""
    proj(db, S, "Alpha")
    b = proj(db, S, "Beta", factory_id=S.F2.id)
    result = svc.list_projects(
        db, workspace_id=S.W1.id, user_id=S.U2.id, factory_id=S.F2.id, limit=1000
    )
    # Then 1
    assert idset(result) == {b.id}


# [claude] PJS-L-06
def test_pjs_l_06__status_passed_on(db, S):
    """PJS-L-06 — status is passed on.
    Rules: list_projects R1."""
    proj(db, S, "Alpha")
    ac = proj(db, S, "Beta", status=ProjectStatusEnum.COMPLETED)
    result = svc.list_projects(
        db, workspace_id=S.W1.id, user_id=S.U2.id, status="COMPLETED", limit=1000
    )
    # Then 1
    assert idset(result) == {ac.id}


# [claude] PJS-L-07
@xfail("BUG-1958")
def test_pjs_l_07__hidden_rows_take_no_page_places(db, S):
    """PJS-L-07 — hidden private projects ahead of the page do not use its places (pass-through).
    Rules: list_projects R1 (manager R7 [BUG-1958])."""
    proj(db, S, "Aa", private=True)
    proj(db, S, "Ab", private=True)
    proj(db, S, "Ac", private=True)
    v1 = proj(db, S, "Ba")
    v2 = proj(db, S, "Bb")
    result = svc.list_projects(
        db, workspace_id=S.W1.id, user_id=S.UG.id, skip=0, limit=2
    )
    # Then 1
    assert idset(result) == {v1.id, v2.id}


# [claude] PJS-L-08
@xfail("BUG-1958")
def test_pjs_l_08__hidden_row_not_counted_by_skip(db, S):
    """PJS-L-08 — a hidden private project ahead of the skipped row is not counted by skip (pass-through).
    Rules: list_projects R1 (manager R7 [BUG-1958])."""
    proj(db, S, "Aa", private=True)
    proj(db, S, "Ba")
    v2 = proj(db, S, "Bb")
    result = svc.list_projects(
        db, workspace_id=S.W1.id, user_id=S.UG.id, skip=1, limit=10
    )
    # Then 1
    assert idset(result) == {v2.id}


# [claude] PJS-L-09
@xfail("BUG-1955")
def test_pjs_l_09__deleted_row_takes_no_place(db, S):
    """PJS-L-09 — a soft-deleted project ahead of the skipped row takes no place (pass-through).
    Rules: list_projects R1 (manager R3 [BUG-1955])."""
    proj(db, S, "Aa", deleted=True)
    proj(db, S, "Ba")
    v2 = proj(db, S, "Bb")
    result = svc.list_projects(
        db, workspace_id=S.W1.id, user_id=S.U2.id, skip=1, limit=10
    )
    # Then 1
    assert idset(result) == {v2.id}


# [claude] PJS-L-10
@xfail("BUG-1957")
def test_pjs_l_10__ordered_by_name_case_insensitive(db, S):
    """PJS-L-10 — without filters the list is ordered by name, case-insensitive (pass-through).
    Rules: list_projects R1 (manager R5 [BUG-1957])."""
    proj(db, S, "Zulu")
    proj(db, S, "apple")
    proj(db, S, "Banana")
    result = svc.list_projects(db, workspace_id=S.W1.id, user_id=S.U2.id, limit=1000)
    # Then 1
    assert names(result) == ["apple", "Banana", "Zulu"]


# [claude] PJS-L-11
@xfail("BUG-1959")
def test_pjs_l_11__factory_id_zero_filters(db, S):
    """PJS-L-11 — factory_id 0 filters and returns nothing (pass-through).
    Rules: list_projects R1 (manager R1 [BUG-1959])."""
    proj(db, S, "Alpha")
    proj(db, S, "Beta", factory_id=S.F2.id)
    result = svc.list_projects(
        db, workspace_id=S.W1.id, user_id=S.U2.id, factory_id=0, limit=1000
    )
    # Then 1
    assert result == []


# [claude] PJS-L-12
@xfail("BUG-1960")
def test_pjs_l_12__factory_and_status_together(db, S):
    """PJS-L-12 — factory and status together apply both (pass-through).
    Rules: list_projects R1 (manager R1a [BUG-1960])."""
    ap = proj(db, S, "Alpha")
    proj(db, S, "Beta", status=ProjectStatusEnum.COMPLETED)
    proj(db, S, "Gamma", factory_id=S.F2.id)
    result = svc.list_projects(
        db,
        workspace_id=S.W1.id,
        user_id=S.U2.id,
        factory_id=S.F1.id,
        status="PLANNING",
        limit=1000,
    )
    # Then 1
    assert idset(result) == {ap.id}


# [claude] PJS-L-13
def test_pjs_l_13__unknown_status_value_error_no_rollback(db, S):
    """PJS-L-13 — an unknown status: the manager's ValueError passes unchanged, no rollback.
    Rules: list_projects R2; TC6."""
    proj(db, S, "Alpha")
    commit_point(db)
    x_id = extra_x(db, S)
    # Then 1
    with pytest.raises(ValueError):
        with spies(db) as (cm, rb, _rf):
            svc.list_projects(
                db, workspace_id=S.W1.id, user_id=S.U2.id, status="planning"
            )
    # Then 2
    assert rb.call_count == 0
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert x_count(db, x_id) == 1


# [claude] PJS-L-14
def test_pjs_l_14__list_neither_commits_nor_rolls_back(db, S):
    """PJS-L-14 — a list neither commits nor rolls back; the caller's edit stays.
    Rules: list_projects R2; TC6."""
    a = proj(db, S, "Alpha")
    edit(a)
    with spies(db) as (cm, rb, _rf):
        result = svc.list_projects(
            db, workspace_id=S.W1.id, user_id=S.U2.id, limit=1000
        )
    # Then 1
    assert idset(result) == {a.id}
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert a in db.dirty
    # Then 5
    assert len(db.dirty) == 1


# [claude] PJS-L-15
def test_pjs_l_15__status_filter_before_paging(db, S):
    """PJS-L-15 — a status filter with paging: rows of another status ahead of the page take no place.
    Rules: list_projects R1 (filter passed on, applied before paging, HR-5)."""
    proj(db, S, "Aa")
    proj(db, S, "Ab")
    ac1 = proj(db, S, "Ca", status=ProjectStatusEnum.COMPLETED)
    ac2 = proj(db, S, "Cb", status=ProjectStatusEnum.COMPLETED)
    result = svc.list_projects(
        db, workspace_id=S.W1.id, user_id=S.U2.id, status="COMPLETED", skip=0, limit=2
    )
    # Then 1
    assert len(result) == 2
    # Then 2
    assert idset(result) == {ac1.id, ac2.id}


# [claude] PJS-L-16
def test_pjs_l_16__factory_filter_before_paging(db, S):
    """PJS-L-16 — a factory filter with paging: rows of another factory ahead of the page take no place.
    Rules: list_projects R1 (filter passed on, applied before paging, HR-5)."""
    proj(db, S, "Aa")
    proj(db, S, "Ab")
    b1 = proj(db, S, "Ba", factory_id=S.F2.id)
    b2 = proj(db, S, "Bb", factory_id=S.F2.id)
    result = svc.list_projects(
        db, workspace_id=S.W1.id, user_id=S.U2.id, factory_id=S.F2.id, skip=0, limit=2
    )
    # Then 1
    assert len(result) == 2
    # Then 2
    assert idset(result) == {b1.id, b2.id}


# =========================================================================== #
# update_project
# =========================================================================== #


# [claude] PJS-U-01
def test_pjs_u_01__changes_logs_commits_rereads(db, S):
    """PJS-U-01 — changes the fields, logs the event, commits, returns the row re-read.
    Rules: update_project R1; TC1, TC2."""
    p = proj(db, S, "Roof job")
    p_id = p.id
    commit_point(db)
    result = svc.update_project(
        db,
        project_id=p_id,
        project_in=ProjectUpdate(name="Roof refit"),
        workspace_id=S.W1.id,
        user_id=S.U2.id,
    )
    # Then 1
    assert result.id == p_id
    # Then 2
    assert not (
        {c.key for c in inspect(result).mapper.column_attrs}
        & inspect(result).expired_attributes
    )
    # Then 3
    assert result.updated_at == NOW
    db.rollback()
    # Then 4
    row = reread(db, Project, p_id)
    assert row.name == "Roof refit"
    assert row.updated_by == S.U2.id
    # Then 5
    evs = events_of(db, p_id)
    assert len(evs) == 1
    assert evs[0].event_type == "updated"
    assert evs[0].performed_by == S.U2.id


# [claude] PJS-U-02
def test_pjs_u_02__deleted_project_400_rolled_back(db, S):
    """PJS-U-02 — a soft-deleted project is 400, rolled back with every pending change.
    Rules: update_project R2; TC3."""
    p = proj(db, S, "Gone", deleted=True)
    commit_point(db)
    before_p = snap(db, p)
    before = counts(db)
    x_id = extra_x(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_project(
            db,
            project_id=before_p["id"],
            project_in=ProjectUpdate(name="Back"),
            workspace_id=S.W1.id,
            user_id=S.U2.id,
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update deleted project"
    # Then 4
    assert not db.new and not db.dirty
    # Then 5
    assert x_count(db, x_id) == 0
    # Then 6
    assert unchanged(db, Project, before_p)
    # Then 7
    assert counts(db) == before


# [claude] PJS-U-03
def test_pjs_u_03__private_project_403_rolled_back(db, S):
    """PJS-U-03 — a private project the caller may not open is 403, rolled back.
    Rules: update_project R2; TC3."""
    p = proj(db, S, "Secret", private=True)
    commit_point(db)
    before_p = snap(db, p)
    x_id = extra_x(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_project(
            db,
            project_id=before_p["id"],
            project_in=ProjectUpdate(name="Mine"),
            workspace_id=S.W1.id,
            user_id=S.UG.id,
        )
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == DENIED
    # Then 4
    assert not db.new and not db.dirty
    # Then 5
    assert x_count(db, x_id) == 0
    # Then 6
    assert unchanged(db, Project, before_p)


# [claude] PJS-U-04
def test_pjs_u_04__w0_project_404_rolled_back(db, S):
    """PJS-U-04 — a W0 project (lower id) is 404 in W1, rolled back.
    Rules: update_project R2; TC3."""
    p0 = proj(db, S, "Zero", where="W0")
    proj(db, S, "Roof job")
    commit_point(db)
    before_p0 = snap(db, p0)
    x_id = extra_x(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_project(
            db,
            project_id=before_p0["id"],
            project_in=ProjectUpdate(name="Mine"),
            workspace_id=S.W1.id,
            user_id=S.U2.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project with ID {before_p0['id']} not found"
    # Then 4
    assert not db.new and not db.dirty
    # Then 5
    assert x_count(db, x_id) == 0
    # Then 6
    assert unchanged(db, Project, before_p0)


# [claude] PJS-U-05
def test_pjs_u_05__failing_commit_rolls_back(db, S):
    """PJS-U-05 — a failing commit rolls back and nothing is saved.
    Rules: update_project R3; TC4."""
    p = proj(db, S, "Roof job")
    commit_point(db)
    before_p = snap(db, p)
    before = counts(db)
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.update_project(
                db,
                project_id=before_p["id"],
                project_in=ProjectUpdate(name="Roof refit"),
                workspace_id=S.W1.id,
                user_id=S.U2.id,
            )
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert unchanged(db, Project, before_p)
    # Then 4
    assert counts(db) == before


# [claude] PJS-U-06
def test_pjs_u_06__failing_refresh_leaves_change_saved(db, S):
    """PJS-U-06 — a failing re-read after the commit leaves the change saved.
    Rules: update_project R3; TC5."""
    p = proj(db, S, "Roof job")
    p_id = p.id
    commit_point(db)
    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db):
            svc.update_project(
                db,
                project_id=p_id,
                project_in=ProjectUpdate(name="Roof refit"),
                workspace_id=S.W1.id,
                user_id=S.U2.id,
            )
    # Then 1
    assert str(exc.value) == "boom"
    db.rollback()
    # Then 2
    assert reread(db, Project, p_id).name == "Roof refit"
    # Then 3
    assert len(events_of(db, p_id)) == 1


# [claude] PJS-U-07
def test_pjs_u_07__same_values_no_event(db, S):
    """PJS-U-07 — the same values: no event (pass-through).
    Rules: update_project R1 (manager R4)."""
    p = proj(db, S, "Roof job")
    p_id = p.id
    commit_point(db)
    result = svc.update_project(
        db,
        project_id=p_id,
        project_in=ProjectUpdate(name="Roof job", description="Main"),
        workspace_id=S.W1.id,
        user_id=S.U2.id,
    )
    # Then 1
    assert result.id == p_id
    db.rollback()
    # Then 2
    assert len(events_of(db, p_id)) == 0


# [claude] PJS-U-08
@xfail("BUG-1952")
def test_pjs_u_08__same_values_no_stamp(db, S):
    """PJS-U-08 — the same values do not stamp the project (pass-through).
    Rules: update_project R1 (manager R9 [BUG-1952])."""
    p = proj(db, S, "Roof job")
    p_id = p.id
    commit_point(db)
    result = svc.update_project(
        db,
        project_id=p_id,
        project_in=ProjectUpdate(name="Roof job", description="Main"),
        workspace_id=S.W1.id,
        user_id=S.U2.id,
    )
    # Then 1
    assert result.id == p_id
    db.rollback()
    # Then 2
    row = reread(db, Project, p_id)
    assert row.updated_by is None
    assert row.updated_at is None


# [claude] PJS-U-09
@xfail("BUG-1953")
def test_pjs_u_09__explicit_null_clears_budget(db, S):
    """PJS-U-09 — an explicit null clears the budget (pass-through).
    Rules: update_project R1 (manager R2a [BUG-1953])."""
    p = proj(db, S, "Roof job", budget=Decimal("1000.00"))
    p_id = p.id
    commit_point(db)
    result = svc.update_project(
        db,
        project_id=p_id,
        project_in=ProjectUpdate(budget=None),
        workspace_id=S.W1.id,
        user_id=S.U2.id,
    )
    # Then 1
    assert result.id == p_id
    db.rollback()
    # Then 2
    assert reread(db, Project, p_id).budget is None


# =========================================================================== #
# delete_project
# =========================================================================== #


# [claude] PJS-D-01
def test_pjs_d_01__soft_deletes_logs_commits(db, S):
    """PJS-D-01 — soft-deletes, logs deleted, commits, returns the row re-read.
    Rules: delete_project R1; TC1, TC2."""
    p = proj(db, S, "Roof job")
    p_id = p.id
    commit_point(db)
    result = svc.delete_project(
        db, project_id=p_id, workspace_id=S.W1.id, user_id=S.U2.id
    )
    # Then 1
    assert result.id == p_id
    # Then 2
    assert not (
        {c.key for c in inspect(result).mapper.column_attrs}
        & inspect(result).expired_attributes
    )
    # Then 3
    assert result.is_deleted is True
    assert result.deleted_at == NOW
    assert result.deleted_by == S.U2.id
    db.rollback()
    # Then 4
    row = reread(db, Project, p_id)
    assert row.is_deleted is True
    assert row.deleted_by == S.U2.id
    # Then 5
    evs = events_of(db, p_id)
    assert len(evs) == 1
    assert evs[0].event_type == "deleted"


# [claude] PJS-D-02
def test_pjs_d_02__already_deleted_400_rolled_back(db, S):
    """PJS-D-02 — an already deleted project is 400, rolled back with every pending change.
    Rules: delete_project R2; TC3."""
    p = proj(db, S, "Gone", deleted=True)
    commit_point(db)
    before_p = snap(db, p)
    before = counts(db)
    x_id = extra_x(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_project(
            db, project_id=before_p["id"], workspace_id=S.W1.id, user_id=S.U2.id
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Project is already deleted"
    # Then 4
    assert not db.new and not db.dirty
    # Then 5
    assert x_count(db, x_id) == 0
    # Then 6
    assert unchanged(db, Project, before_p)
    # Then 7
    assert counts(db) == before


# [claude] PJS-D-03
def test_pjs_d_03__private_project_403_rolled_back(db, S):
    """PJS-D-03 — a private project the caller may not open is 403, rolled back.
    Rules: delete_project R2; TC3."""
    p = proj(db, S, "Secret", private=True)
    commit_point(db)
    before_p = snap(db, p)
    x_id = extra_x(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_project(
            db, project_id=before_p["id"], workspace_id=S.W1.id, user_id=S.UG.id
        )
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == DENIED
    # Then 4
    assert not db.new and not db.dirty
    # Then 5
    assert x_count(db, x_id) == 0
    # Then 6
    assert unchanged(db, Project, before_p)


# [claude] PJS-D-04
def test_pjs_d_04__w2_project_404_rolled_back(db, S):
    """PJS-D-04 — a W2 project (higher id) is 404 in W1, rolled back.
    Rules: delete_project R2; TC3."""
    proj(db, S, "Roof job")
    p9 = proj(db, S, "Nine", where="W2")
    commit_point(db)
    before_p9 = snap(db, p9)
    x_id = extra_x(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_project(
            db, project_id=before_p9["id"], workspace_id=S.W1.id, user_id=S.U2.id
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project with ID {before_p9['id']} not found"
    # Then 4
    assert not db.new and not db.dirty
    # Then 5
    assert x_count(db, x_id) == 0
    # Then 6
    assert unchanged(db, Project, before_p9)


# [claude] PJS-D-05
def test_pjs_d_05__failing_commit_rolls_back(db, S):
    """PJS-D-05 — a failing commit rolls back and nothing is saved.
    Rules: delete_project R3; TC4."""
    p = proj(db, S, "Roof job")
    p_id = p.id
    commit_point(db)
    before = counts(db)
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.delete_project(
                db, project_id=p_id, workspace_id=S.W1.id, user_id=S.U2.id
            )
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert reread(db, Project, p_id).is_deleted is False
    # Then 4
    assert counts(db) == before


# [claude] PJS-D-06
def test_pjs_d_06__failing_refresh_leaves_delete_saved(db, S):
    """PJS-D-06 — a failing re-read after the commit leaves the delete saved.
    Rules: delete_project R3; TC5."""
    p = proj(db, S, "Roof job")
    p_id = p.id
    commit_point(db)
    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db):
            svc.delete_project(
                db, project_id=p_id, workspace_id=S.W1.id, user_id=S.U2.id
            )
    # Then 1
    assert str(exc.value) == "boom"
    db.rollback()
    # Then 2
    assert reread(db, Project, p_id).is_deleted is True
    # Then 3
    assert len(events_of(db, p_id)) == 1


# =========================================================================== #
# list_events
# =========================================================================== #


# [claude] PJS-EV-01
def test_pjs_ev_01__log_newest_first_with_performers(db, S):
    """PJS-EV-01 — the manager's log, newest first with each performer's profile.
    Rules: list_events R1."""
    p = proj(db, S, "Roof job")
    ea = ev(db, p, "a", T1, S.U1.id)
    eb = ev(db, p, "b", T3, None)
    ec = ev(db, p, "c", T2, S.U2.id)
    result = svc.list_events(db, project_id=p.id, workspace_id=S.W1.id, user_id=S.UG.id)
    # Then 1
    assert [e.id for e, _ in result] == [eb.id, ec.id, ea.id]
    # Then 2
    assert [(pr.id if pr is not None else None) for _, pr in result] == [
        None,
        S.U2.id,
        S.U1.id,
    ]


# [claude] PJS-EV-02
def test_pjs_ev_02__deleted_project_log_answered(db, S):
    """PJS-EV-02 — a soft-deleted project's log is still answered.
    Rules: list_events R1."""
    p = proj(db, S, "Gone", deleted=True)
    e1 = ev(db, p, "deleted", T1, S.U1.id)
    result = svc.list_events(db, project_id=p.id, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 1
    assert [e.id for e, _ in result] == [e1.id]


# [claude] PJS-EV-03
def test_pjs_ev_03__private_log_403_no_rollback(db, S):
    """PJS-EV-03 — a private project's log: the 403 passes unchanged, no rollback.
    Rules: list_events R1, R2; TC6."""
    p = proj(db, S, "Secret", private=True)
    p_id = p.id
    commit_point(db)
    x_id = extra_x(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb, _rf):
            svc.list_events(db, project_id=p_id, workspace_id=S.W1.id, user_id=S.UG.id)
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == DENIED
    # Then 4
    assert rb.call_count == 0
    # Then 5
    assert x_count(db, x_id) == 1


# [claude] PJS-EV-04
def test_pjs_ev_04__read_neither_commits_nor_rolls_back(db, S):
    """PJS-EV-04 — a read neither commits nor rolls back; the caller's edit stays.
    Rules: list_events R2; TC6."""
    p = proj(db, S, "Roof job")
    ev(db, p, "a", T1, S.U1.id)
    edit(p)
    with spies(db) as (cm, rb, _rf):
        result = svc.list_events(
            db, project_id=p.id, workspace_id=S.W1.id, user_id=S.U2.id
        )
    # Then 1
    assert len(result) == 1
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert p in db.dirty


# [claude] PJS-EV-05
@xfail("BUG-1964")
def test_pjs_ev_05__performers_read_together(db, S):
    """PJS-EV-05 — performers are read together (pass-through).
    Rules: list_events R1 (manager R4 [BUG-1964])."""
    p = proj(db, S, "Roof job")
    ux = make_profile(db, name="Omar Ali")
    uy = make_profile(db, name="Rina Das")
    ev(db, p, "a", T1, S.U1.id)
    ev(db, p, "b", T1, S.U2.id)
    ev(db, p, "c", T2, S.UG.id)
    ev(db, p, "d", T2, ux.id)
    ev(db, p, "e", T3, uy.id)
    p_id, w1_id, ug_id = p.id, S.W1.id, S.UG.id
    db.expire_all()
    with recorder(db) as stmts:
        result = svc.list_events(db, project_id=p_id, workspace_id=w1_id, user_id=ug_id)
    # Then 1
    assert len(result) == 5
    # Then 2
    assert len([s for s in stmts if "FROM projects" not in s]) <= 3


# =========================================================================== #
# list_members
# =========================================================================== #


# [claude] PJS-LM-01
def test_pjs_lm_01__members_in_assigned_order(db, S):
    """PJS-LM-01 — the manager's members, in order of assigned_at.
    Rules: list_members R1."""
    p = proj(db, S, "Roof job")
    ma = pmem(db, S, p, S.U1, assigned_at=T2)
    mb = pmem(db, S, p, S.U2, assigned_at=T1)
    mc = pmem(db, S, p, S.UG, assigned_at=T3)
    result = svc.list_members(
        db, project_id=p.id, workspace_id=S.W1.id, user_id=S.UG.id
    )
    # Then 1
    assert [m.id for m in result] == [mb.id, ma.id, mc.id]


# [claude] PJS-LM-02
@xfail("BUG-1278")
def test_pjs_lm_02__deleted_project_members_404(db, S):
    """PJS-LM-02 — a soft-deleted project's members are 404 (pass-through).
    Rules: list_members R1 [BUG-1278]."""
    p = proj(db, S, "Gone", deleted=True)
    pmem(db, S, p, S.U1)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.list_members(db, project_id=p.id, workspace_id=S.W1.id, user_id=S.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project with ID {p.id} not found"


# [claude] PJS-LM-03
def test_pjs_lm_03__other_workspace_404_no_rollback(db, S):
    """PJS-LM-03 — another workspace's project is 404, no rollback.
    Rules: list_members R1, R2; TC6."""
    p9 = proj(db, S, "Nine", where="W2")
    p9_id = p9.id
    commit_point(db)
    x_id = extra_x(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb, _rf):
            svc.list_members(
                db, project_id=p9_id, workspace_id=S.W1.id, user_id=S.U2.id
            )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project with ID {p9_id} not found"
    # Then 4
    assert rb.call_count == 0
    # Then 5
    assert x_count(db, x_id) == 1


# [claude] PJS-LM-04
def test_pjs_lm_04__read_neither_commits_nor_rolls_back(db, S):
    """PJS-LM-04 — a read neither commits nor rolls back; the caller's edit stays.
    Rules: list_members R2; TC6."""
    p = proj(db, S, "Roof job")
    m = pmem(db, S, p, S.UG)
    edit(p)
    with spies(db) as (cm, rb, _rf):
        result = svc.list_members(
            db, project_id=p.id, workspace_id=S.W1.id, user_id=S.U2.id
        )
    # Then 1
    assert [r.id for r in result] == [m.id]
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert p in db.dirty


# [claude] PJS-LM-05
@xfail("BUG-2271")
def test_pjs_lm_05__endpoint_reads_profiles_together(db, S):
    """PJS-LM-05 — the members endpoint reads profiles and positions together: at most two statements after the member list.
    Rules: list_members R3 [BUG-2271]."""
    ua = make_profile(db, name="Omar Ali")
    ub = make_profile(db, name="Rina Das")
    uc = make_profile(db, name="Sami Haq")
    ud = make_profile(db, name="Tania Roy")
    ue = make_profile(db, name="Uma Sen")
    member(db, S, ua, "ground-team")
    member(db, S, ub, "ground-team")
    member(db, S, uc, "finance")
    member(db, S, ud, "ground-team")
    member(db, S, ue, "ground-team")
    p = proj(db, S, "Roof job")
    pmem(db, S, p, ua, assigned_at=T1)
    pmem(db, S, p, ub, assigned_at=T1)
    pmem(db, S, p, uc, assigned_at=T2)
    pmem(db, S, p, ud, assigned_at=T2)
    pmem(db, S, p, ue, assigned_at=T3)
    p_id = p.id
    db.expire_all()
    with recorder(db) as stmts:
        result = list_project_members(
            project_id=p_id, workspace=S.W1, current_user=S.U2, db=db
        )
    # Then 1
    assert len(result.members) == 5
    # Then 2
    assert (
        len(stmts)
        - 1
        - max(i for i, s in enumerate(stmts) if "FROM project_members" in s)
        <= 2
    )


# [claude] PJS-LM-06
def test_pjs_lm_06__endpoint_answers_name_email_position(db, S):
    """PJS-LM-06 — the members endpoint answers each member's name, email and workspace position.
    Rules: list_members R3 (the response the fix must keep)."""
    m1 = db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == S.W1.id, WorkspaceMember.user_id == S.U1.id
        )
    )
    m1.position = "Foreman"
    db.flush()
    ux = make_profile(db, name="Omar Ali")
    p = proj(db, S, "Roof job")
    ma = pmem(db, S, p, S.U1, assigned_at=T1)
    mx = pmem(db, S, p, ux, assigned_at=T2)
    result = list_project_members(
        project_id=p.id, workspace=S.W1, current_user=S.U2, db=db
    )
    # Then 1
    assert isinstance(result, ProjectMembersListResponse)
    # Then 2
    assert [m.id for m in result.members] == [ma.id, mx.id]
    # Then 3
    assert result.members[0].user_id == S.U1.id
    assert result.members[0].user_name == "Ana Rahman"
    assert result.members[0].user_email == S.U1.email
    assert result.members[0].user_position == "Foreman"
    # Then 4
    assert result.members[1].user_name == "Omar Ali"
    assert result.members[1].user_email == ux.email
    assert result.members[1].user_position is None
    # Then 5
    assert result.members[0].project_id == p.id
    assert result.members[0].workspace_id == S.W1.id
    assert result.members[0].assigned_by == S.U1.id
    assert result.members[0].assigned_at == T1


# [claude] PJS-LM-07
def test_pjs_lm_07__endpoint_passes_403(db, S):
    """PJS-LM-07 — the members endpoint passes the service's 403 on unchanged.
    Rules: list_members R1, R3 (endpoint errors pass unchanged)."""
    p = proj(db, S, "Secret", private=True)
    pmem(db, S, p, S.U1)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        list_project_members(project_id=p.id, workspace=S.W1, current_user=S.UG, db=db)
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == DENIED


# =========================================================================== #
# add_member
# =========================================================================== #


# [claude] PJS-AM-01
def test_pjs_am_01__adds_logs_commits_rereads(db, S):
    """PJS-AM-01 — adds the member, logs member_added, commits, returns the row re-read.
    Rules: add_member R1; TC1, TC2."""
    ux = make_profile(db, name="Omar Ali")
    member(db, S, ux, "ground-team")
    p = proj(db, S, "Roof job")
    p_id, ux_id = p.id, ux.id
    commit_point(db)
    result = svc.add_member(
        db,
        project_id=p_id,
        member_user_id=ux_id,
        workspace_id=S.W1.id,
        assigned_by=S.U2.id,
    )
    # Then 1
    assert isinstance(result, ProjectMember)
    # Then 2
    assert result.assigned_at is not None
    # Then 3
    assert not (
        {c.key for c in inspect(result).mapper.column_attrs}
        & inspect(result).expired_attributes
    )
    db.rollback()
    # Then 4
    mems = members_of(db, p_id)
    assert len(mems) == 1
    assert mems[0].user_id == ux_id
    assert mems[0].assigned_by == S.U2.id
    # Then 5
    evs = events_of(db, p_id)
    assert len(evs) == 1
    assert evs[0].event_type == "member_added"
    assert evs[0].description == "Added Omar Ali to the project"


# [claude] PJS-AM-02
def test_pjs_am_02__inactive_workspace_member_400(db, S):
    """PJS-AM-02 — a person who is not an active member of the workspace is 400, rolled back.
    Rules: add_member R2; TC3."""
    ux = make_profile(db, name="Omar Ali")
    member(db, S, ux, "ground-team", status="suspended")
    p = proj(db, S, "Roof job")
    p_id, ux_id = p.id, ux.id
    commit_point(db)
    before = counts(db)
    x_id = extra_x(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.add_member(
            db,
            project_id=p_id,
            member_user_id=ux_id,
            workspace_id=S.W1.id,
            assigned_by=S.U2.id,
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "User is not an active member of this workspace"
    # Then 4
    assert not db.new
    # Then 5
    assert x_count(db, x_id) == 0
    # Then 6
    assert counts(db) == before


# [claude] PJS-AM-03
def test_pjs_am_03__already_member_409(db, S):
    """PJS-AM-03 — someone already a member is 409, rolled back.
    Rules: add_member R2; TC3."""
    ux = make_profile(db, name="Omar Ali")
    member(db, S, ux, "ground-team")
    p = proj(db, S, "Roof job")
    mx = pmem(db, S, p, ux)
    p_id, ux_id = p.id, ux.id
    commit_point(db)
    before_mx = snap(db, mx)
    before = counts(db)
    x_id = extra_x(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.add_member(
            db,
            project_id=p_id,
            member_user_id=ux_id,
            workspace_id=S.W1.id,
            assigned_by=S.U2.id,
        )
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "User is already a member of this project"
    # Then 4
    assert not db.new
    # Then 5
    assert x_count(db, x_id) == 0
    # Then 6
    assert unchanged(db, ProjectMember, before_mx)
    # Then 7
    assert counts(db) == before


# [claude] PJS-AM-04
def test_pjs_am_04__private_project_403(db, S):
    """PJS-AM-04 — a caller who may not open the private project is 403, rolled back.
    Rules: add_member R2; TC3."""
    ux = make_profile(db, name="Omar Ali")
    member(db, S, ux, "ground-team")
    p = proj(db, S, "Secret", private=True)
    p_id, ux_id = p.id, ux.id
    commit_point(db)
    before = counts(db)
    x_id = extra_x(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.add_member(
            db,
            project_id=p_id,
            member_user_id=ux_id,
            workspace_id=S.W1.id,
            assigned_by=S.UG.id,
        )
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == DENIED
    # Then 4
    assert not db.new
    # Then 5
    assert x_count(db, x_id) == 0
    # Then 6
    assert counts(db) == before


# [claude] PJS-AM-05
def test_pjs_am_05__w0_project_404(db, S):
    """PJS-AM-05 — a W0 project (lower id) is 404 in W1, rolled back.
    Rules: add_member R2; TC3."""
    ux = make_profile(db, name="Omar Ali")
    member(db, S, ux, "ground-team")
    p0 = proj(db, S, "Zero", where="W0")
    p0_id, ux_id = p0.id, ux.id
    commit_point(db)
    before = counts(db)
    x_id = extra_x(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.add_member(
            db,
            project_id=p0_id,
            member_user_id=ux_id,
            workspace_id=S.W1.id,
            assigned_by=S.U2.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project with ID {p0_id} not found"
    # Then 4
    assert not db.new
    # Then 5
    assert x_count(db, x_id) == 0
    # Then 6
    assert counts(db) == before


# [claude] PJS-AM-06
@xfail("BUG-1278")
def test_pjs_am_06__deleted_project_404_nobody_added(db, S):
    """PJS-AM-06 — a soft-deleted project is 404 and nobody is added (pass-through).
    Rules: add_member R2 [BUG-1278]."""
    ux = make_profile(db, name="Omar Ali")
    member(db, S, ux, "ground-team")
    p = proj(db, S, "Gone", deleted=True)
    p_id, ux_id = p.id, ux.id
    commit_point(db)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.add_member(
            db,
            project_id=p_id,
            member_user_id=ux_id,
            workspace_id=S.W1.id,
            assigned_by=S.U2.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project with ID {p_id} not found"
    # Then 4
    assert not db.new
    # Then 5
    assert counts(db) == before


# [claude] PJS-AM-07
def test_pjs_am_07__failing_commit_nobody_added(db, S):
    """PJS-AM-07 — a failing commit rolls back and nobody is added.
    Rules: add_member R3; TC4."""
    ux = make_profile(db, name="Omar Ali")
    member(db, S, ux, "ground-team")
    p = proj(db, S, "Roof job")
    p_id, ux_id = p.id, ux.id
    commit_point(db)
    before = counts(db)
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.add_member(
                db,
                project_id=p_id,
                member_user_id=ux_id,
                workspace_id=S.W1.id,
                assigned_by=S.U2.id,
            )
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert counts(db) == before


# [claude] PJS-AM-08
def test_pjs_am_08__failing_refresh_leaves_member_saved(db, S):
    """PJS-AM-08 — a failing re-read after the commit leaves the member saved.
    Rules: add_member R3; TC5."""
    ux = make_profile(db, name="Omar Ali")
    member(db, S, ux, "ground-team")
    p = proj(db, S, "Roof job")
    p_id, ux_id = p.id, ux.id
    commit_point(db)
    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db):
            svc.add_member(
                db,
                project_id=p_id,
                member_user_id=ux_id,
                workspace_id=S.W1.id,
                assigned_by=S.U2.id,
            )
    # Then 1
    assert str(exc.value) == "boom"
    db.rollback()
    # Then 2
    mems = members_of(db, p_id)
    assert len(mems) == 1
    assert mems[0].user_id == ux_id
    # Then 3
    assert len(events_of(db, p_id)) == 1


# =========================================================================== #
# remove_member
# =========================================================================== #


# [claude] PJS-RM-01
def test_pjs_rm_01__removes_logs_commits_no_reread(db, S):
    """PJS-RM-01 — removes the member, logs member_removed, commits, returns None without a re-read.
    Rules: remove_member R1; TC1."""
    ux = make_profile(db, name="Omar Ali")
    member(db, S, ux, "ground-team")
    p = proj(db, S, "Roof job")
    mu = pmem(db, S, p, S.U2)
    pmem(db, S, p, ux)
    p_id, ux_id, mu_id = p.id, ux.id, mu.id
    commit_point(db)
    with spies(db) as (cm, _rb, rf):
        result = svc.remove_member(
            db,
            project_id=p_id,
            member_user_id=ux_id,
            workspace_id=S.W1.id,
            performed_by=S.U2.id,
        )
    # Then 1
    assert result is None
    # Then 2
    assert cm.call_count >= 1
    # Then 3
    assert rf.call_count == 0
    db.rollback()
    # Then 4
    assert [m.id for m in members_of(db, p_id)] == [mu_id]
    # Then 5
    evs = events_of(db, p_id)
    assert len(evs) == 1
    assert evs[0].event_type == "member_removed"
    assert evs[0].description == "Removed Omar Ali from the project"


# [claude] PJS-RM-02
def test_pjs_rm_02__removing_creator_400(db, S):
    """PJS-RM-02 — removing the creator is 400, rolled back.
    Rules: remove_member R2; TC3."""
    p = proj(db, S, "Roof job")
    m1 = pmem(db, S, p, S.U1)
    p_id = p.id
    commit_point(db)
    before_m1 = snap(db, m1)
    before = counts(db)
    x_id = extra_x(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.remove_member(
            db,
            project_id=p_id,
            member_user_id=S.U1.id,
            workspace_id=S.W1.id,
            performed_by=S.U2.id,
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot remove the project creator from members"
    # Then 4
    assert not db.deleted and not db.new
    # Then 5
    assert x_count(db, x_id) == 0
    # Then 6
    assert unchanged(db, ProjectMember, before_m1)
    # Then 7
    assert counts(db) == before


# [claude] PJS-RM-03
def test_pjs_rm_03__not_on_project_404(db, S):
    """PJS-RM-03 — someone not on the project is 404 "Project member not found", rolled back.
    Rules: remove_member R2; TC3."""
    p = proj(db, S, "Roof job")
    m2 = pmem(db, S, p, S.U2)
    p_id = p.id
    commit_point(db)
    before_m2 = snap(db, m2)
    x_id = extra_x(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.remove_member(
            db,
            project_id=p_id,
            member_user_id=S.UG.id,
            workspace_id=S.W1.id,
            performed_by=S.U2.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Project member not found"
    # Then 4
    assert not db.deleted and not db.new
    # Then 5
    assert x_count(db, x_id) == 0
    # Then 6
    assert unchanged(db, ProjectMember, before_m2)


# [claude] PJS-RM-04
def test_pjs_rm_04__private_project_403(db, S):
    """PJS-RM-04 — a caller who may not open the private project is 403, rolled back.
    Rules: remove_member R2; TC3."""
    p = proj(db, S, "Secret", private=True)
    m2 = pmem(db, S, p, S.U2)
    p_id = p.id
    commit_point(db)
    before_m2 = snap(db, m2)
    x_id = extra_x(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.remove_member(
            db,
            project_id=p_id,
            member_user_id=S.U2.id,
            workspace_id=S.W1.id,
            performed_by=S.UG.id,
        )
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == DENIED
    # Then 4
    assert not db.deleted and not db.new
    # Then 5
    assert x_count(db, x_id) == 0
    # Then 6
    assert unchanged(db, ProjectMember, before_m2)


# [claude] PJS-RM-05
def test_pjs_rm_05__w2_project_404(db, S):
    """PJS-RM-05 — a W2 project (higher id) is 404 in W1, rolled back.
    Rules: remove_member R2; TC3."""
    p9 = proj(db, S, "Nine", where="W2")
    m9 = pmem(db, S, p9, S.U2)
    p9_id = p9.id
    commit_point(db)
    before_m9 = snap(db, m9)
    x_id = extra_x(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.remove_member(
            db,
            project_id=p9_id,
            member_user_id=S.U2.id,
            workspace_id=S.W1.id,
            performed_by=S.U2.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project with ID {p9_id} not found"
    # Then 4
    assert not db.deleted and not db.new
    # Then 5
    assert x_count(db, x_id) == 0
    # Then 6
    assert unchanged(db, ProjectMember, before_m9)


# [claude] PJS-RM-06
@xfail("BUG-1278")
def test_pjs_rm_06__deleted_project_404_nobody_removed(db, S):
    """PJS-RM-06 — a soft-deleted project is 404 and nobody is removed (pass-through).
    Rules: remove_member R2 [BUG-1278]."""
    p = proj(db, S, "Gone", deleted=True)
    mg = pmem(db, S, p, S.UG)
    p_id = p.id
    commit_point(db)
    before_mg = snap(db, mg)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.remove_member(
            db,
            project_id=p_id,
            member_user_id=S.UG.id,
            workspace_id=S.W1.id,
            performed_by=S.U2.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project with ID {p_id} not found"
    # Then 4
    assert not db.deleted
    # Then 5
    assert unchanged(db, ProjectMember, before_mg)
    # Then 6
    assert counts(db) == before


# [claude] PJS-RM-07
def test_pjs_rm_07__failing_commit_member_stays(db, S):
    """PJS-RM-07 — a failing commit rolls back and the member stays.
    Rules: remove_member R3; TC4."""
    p = proj(db, S, "Roof job")
    mg = pmem(db, S, p, S.UG)
    p_id = p.id
    commit_point(db)
    before_mg = snap(db, mg)
    before = counts(db)
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.remove_member(
                db,
                project_id=p_id,
                member_user_id=S.UG.id,
                workspace_id=S.W1.id,
                performed_by=S.U2.id,
            )
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert unchanged(db, ProjectMember, before_mg)
    # Then 4
    assert counts(db) == before


# =========================================================================== #
# set_visibility
# =========================================================================== #


# [claude] PJS-SV-01
def test_pjs_sv_01__makes_private_logs_commits(db, S):
    """PJS-SV-01 — makes the project private, logs the change, commits, returns the row re-read.
    Rules: set_visibility R1; TC1, TC2."""
    p = proj(db, S, "Roof job")
    p_id = p.id
    commit_point(db)
    result = svc.set_visibility(
        db,
        project_id=p_id,
        visibility=ProjectVisibilityEnum.INVITED_ONLY,
        workspace_id=S.W1.id,
        user_id=S.U2.id,
    )
    # Then 1
    assert result.id == p_id
    # Then 2
    assert not (
        {c.key for c in inspect(result).mapper.column_attrs}
        & inspect(result).expired_attributes
    )
    db.rollback()
    # Then 3
    row = reread(db, Project, p_id)
    assert row.visibility == "invited_only"
    assert row.updated_by == S.U2.id
    # Then 4
    evs = events_of(db, p_id)
    assert len(evs) == 1
    assert evs[0].event_type == "visibility_updated"


# [claude] PJS-SV-02
def test_pjs_sv_02__same_visibility_no_event_commit_runs(db, S):
    """PJS-SV-02 — the same visibility: no event, no stamp, the commit still runs.
    Rules: set_visibility R1."""
    p = proj(db, S, "Secret", private=True)
    commit_point(db)
    before_p = snap(db, p)
    with spies(db) as (cm, _rb, _rf):
        result = svc.set_visibility(
            db,
            project_id=before_p["id"],
            visibility=ProjectVisibilityEnum.INVITED_ONLY,
            workspace_id=S.W1.id,
            user_id=S.U2.id,
        )
    # Then 1
    assert result.id == before_p["id"]
    # Then 2
    assert cm.call_count >= 1
    # Then 3
    assert unchanged(db, Project, before_p)
    # Then 4
    assert len(events_of(db, before_p["id"])) == 0


# [claude] PJS-SV-03
def test_pjs_sv_03__deleted_project_400(db, S):
    """PJS-SV-03 — a soft-deleted project is 400, rolled back.
    Rules: set_visibility R2; TC3."""
    p = proj(db, S, "Gone", deleted=True)
    commit_point(db)
    before_p = snap(db, p)
    before = counts(db)
    x_id = extra_x(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.set_visibility(
            db,
            project_id=before_p["id"],
            visibility=ProjectVisibilityEnum.INVITED_ONLY,
            workspace_id=S.W1.id,
            user_id=S.U2.id,
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update deleted project"
    # Then 4
    assert not db.new and not db.dirty
    # Then 5
    assert x_count(db, x_id) == 0
    # Then 6
    assert unchanged(db, Project, before_p)
    # Then 7
    assert counts(db) == before


# [claude] PJS-SV-04
def test_pjs_sv_04__private_project_403(db, S):
    """PJS-SV-04 — a caller who may not open the private project is 403, rolled back.
    Rules: set_visibility R2; TC3."""
    p = proj(db, S, "Secret", private=True)
    commit_point(db)
    before_p = snap(db, p)
    x_id = extra_x(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.set_visibility(
            db,
            project_id=before_p["id"],
            visibility=ProjectVisibilityEnum.WORKSPACE,
            workspace_id=S.W1.id,
            user_id=S.UG.id,
        )
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == DENIED
    # Then 4
    assert not db.new and not db.dirty
    # Then 5
    assert x_count(db, x_id) == 0
    # Then 6
    assert unchanged(db, Project, before_p)


# [claude] PJS-SV-05
def test_pjs_sv_05__w0_project_404(db, S):
    """PJS-SV-05 — a W0 project (lower id) is 404 in W1, rolled back.
    Rules: set_visibility R2; TC3."""
    p0 = proj(db, S, "Zero", where="W0")
    proj(db, S, "Roof job")
    commit_point(db)
    before_p0 = snap(db, p0)
    x_id = extra_x(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.set_visibility(
            db,
            project_id=before_p0["id"],
            visibility=ProjectVisibilityEnum.INVITED_ONLY,
            workspace_id=S.W1.id,
            user_id=S.U2.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project with ID {before_p0['id']} not found"
    # Then 4
    assert not db.new and not db.dirty
    # Then 5
    assert x_count(db, x_id) == 0
    # Then 6
    assert unchanged(db, Project, before_p0)


# [claude] PJS-SV-06
def test_pjs_sv_06__failing_commit_visibility_not_saved(db, S):
    """PJS-SV-06 — a failing commit rolls back and the visibility is not saved.
    Rules: set_visibility R3; TC4."""
    p = proj(db, S, "Roof job")
    p_id = p.id
    commit_point(db)
    before = counts(db)
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.set_visibility(
                db,
                project_id=p_id,
                visibility=ProjectVisibilityEnum.INVITED_ONLY,
                workspace_id=S.W1.id,
                user_id=S.U2.id,
            )
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert reread(db, Project, p_id).visibility == "workspace"
    # Then 4
    assert counts(db) == before


# [claude] PJS-SV-07
def test_pjs_sv_07__failing_refresh_leaves_change_saved(db, S):
    """PJS-SV-07 — a failing re-read after the commit leaves the change saved.
    Rules: set_visibility R3; TC5."""
    p = proj(db, S, "Roof job")
    p_id = p.id
    commit_point(db)
    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db):
            svc.set_visibility(
                db,
                project_id=p_id,
                visibility=ProjectVisibilityEnum.INVITED_ONLY,
                workspace_id=S.W1.id,
                user_id=S.U2.id,
            )
    # Then 1
    assert str(exc.value) == "boom"
    db.rollback()
    # Then 2
    assert reread(db, Project, p_id).visibility == "invited_only"
    # Then 3
    assert len(events_of(db, p_id)) == 1
