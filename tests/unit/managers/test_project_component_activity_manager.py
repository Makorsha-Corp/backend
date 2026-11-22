"""Unit tests for app/managers/project_component_activity_manager.py.

Implements tests/unit/managers/project_component_activity_manager.cases.md, one
test per case, in card order. Real Postgres session (`db` fixture). Nothing is
patched (the cases have no externals and no race simulation); the one spy is the
commit spy the Conventions name under "Rolled back".

Normal mode: every test is written from its card and carries a `# [claude] <ID>`
comment. Row names of the cards are the lower-case names here (CP1 -> cp1,
`A.id` -> `a.id`); `# Then N` marks the checks of the card's Then line N.
"""
# ruff: noqa: SIM117, DTZ001  (Conventions prescribe the nested `with` and naive datetimes)
from contextlib import contextmanager
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from psycopg2.errors import (
    ForeignKeyViolation,
    InvalidRowCountInLimitClause,
    InvalidRowCountInResultOffsetClause,
    NotNullViolation,
    StringDataRightTruncation,
)
from sqlalchemy import event, func, select, text
from sqlalchemy.exc import DataError, IntegrityError, StatementError

from app.managers.project_component_activity_manager import (
    project_component_activity_manager,
)
from app.models.factory import Factory
from app.models.project import Project
from app.models.project_component import ProjectComponent
from app.models.project_component_activity_event import ProjectComponentActivityEvent
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "M = the singleton project_component_activity_manager"
M = project_component_activity_manager

# Convention "MISSING": an id no row of any table has
MISSING = 999999999

# Conventions "T1 .. T4"
T1 = datetime(2026, 3, 4, 10, 0, 0)
T2 = datetime(2026, 3, 5, 10, 0, 0)
T3 = datetime(2026, 3, 6, 10, 0, 0)
T4 = datetime(2026, 3, 7, 10, 0, 0)

BUG_1192 = "BUG-1192: Activity row can be written for another workspace's order, project or component"
BUG_1712 = "BUG-1712: One page of project component activity makes one extra read per entry"


# --------------------------------------------------------------------------- #
# Conventions -> fixtures (the standing rows). Each fixture depends on the one
# before it, so the rows are inserted in the order Conventions list them:
# W1, W2, U1, U2, F1, F9, PJ1, PJD, PJ9, CP8, CP1, CP2, CPD, CP9.
# `standing_rows` builds all of them in every test.
# --------------------------------------------------------------------------- #

def _add(db, row):
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


@pytest.fixture
def u1(db, w2):
    return make_profile(db)


@pytest.fixture
def u2(db, u1):
    return make_profile(db)


@pytest.fixture
def f1(db, w1, u2):
    return _add(db, Factory(workspace_id=w1.id, name="Factory One", abbreviation="F1"))


@pytest.fixture
def f9(db, w2, f1):
    return _add(db, Factory(workspace_id=w2.id, name="Factory Nine", abbreviation="F9"))


@pytest.fixture
def pj1(db, w1, f1, f9):
    return _add(db, Project(workspace_id=w1.id, factory_id=f1.id, name="Project One", description="Main"))


# Convention: PJD is soft-deleted (is_deleted, deleted_at T3, deleted_by U1); is_active not passed
@pytest.fixture
def pjd(db, w1, u1, f1, pj1):
    return _add(db, Project(
        workspace_id=w1.id, factory_id=f1.id, name="Old Project", description="Main",
        is_deleted=True, deleted_at=T3, deleted_by=u1.id,
    ))


@pytest.fixture
def pj9(db, w2, f9, pjd):
    return _add(db, Project(workspace_id=w2.id, factory_id=f9.id, name="Project Nine", description="Main"))


@pytest.fixture
def cp8(db, w2, pj9):
    return _add(db, ProjectComponent(workspace_id=w2.id, project_id=pj9.id, name="Cellar"))


@pytest.fixture
def cp1(db, w1, pj1, cp8):
    return _add(db, ProjectComponent(workspace_id=w1.id, project_id=pj1.id, name="Roof"))


@pytest.fixture
def cp2(db, w1, pj1, cp1):
    return _add(db, ProjectComponent(workspace_id=w1.id, project_id=pj1.id, name="Wall"))


@pytest.fixture
def cpd(db, w1, pjd, cp2):
    return _add(db, ProjectComponent(workspace_id=w1.id, project_id=pjd.id, name="Shed"))


@pytest.fixture
def cp9(db, w2, pj9, cpd):
    return _add(db, ProjectComponent(workspace_id=w2.id, project_id=pj9.id, name="Floor"))


# Convention "Standing rows": in every test, in this order. CP9 is the last of the chain.
@pytest.fixture(autouse=True)
def standing_rows(cp9):
    return cp9


# --------------------------------------------------------------------------- #
# Conventions -> Given rows. Each builder inserts and flushes one row, so ids
# rise in the order written. `metadata_json` and `performed_by` are not passed
# unless the card gives them (metadata_json=None is passed as a keyword).
# --------------------------------------------------------------------------- #

def mk_event(db, workspace, component, created_at, **columns):
    """Convention "event"."""
    fields = {"event_type": "attachment_added", "description": "Logged", **columns}
    return _add(db, ProjectComponentActivityEvent(
        workspace_id=workspace.id, project_component_id=component.id, created_at=created_at, **fields,
    ))


def mk_log(db, workspace, component, n):
    """Convention "log(n)": n events by one add_all and one flush."""
    db.add_all([
        ProjectComponentActivityEvent(
            workspace_id=workspace.id, project_component_id=component.id, event_type="attachment_added",
            description=f"E{i}", created_at=T1 + timedelta(seconds=i),
        )
        for i in range(n)
    ])
    db.flush()


# --------------------------------------------------------------------------- #
# Conventions -> named checks
# --------------------------------------------------------------------------- #

def snap(db, row):
    """Every column of `row`, from the database, without touching the session's objects."""
    table = row.__table__
    return dict(db.execute(select(table).where(table.c.id == row.id)).mappings().one())


def reread_snap(db, row):
    """Convention "unchanged(X)": the database values after a re-read."""
    row_id = row.id
    db.expire_all()
    table = row.__table__
    return dict(db.execute(select(table).where(table.c.id == row_id)).mappings().one())


def reread_event(db, event_id):
    """Convention "re-read X": expire, then SELECT by id."""
    db.expire_all()
    return db.execute(
        select(ProjectComponentActivityEvent).where(ProjectComponentActivityEvent.id == event_id)
    ).scalar_one()


def event_count(db):
    """Convention "nothing written": the row count of project_component_activity_events, all workspaces."""
    return db.execute(select(func.count()).select_from(ProjectComponentActivityEvent)).scalar_one()


def count_events(db, **filters):
    """Convention "count:": rows in all workspaces, with the filter stated."""
    return db.execute(
        select(func.count()).select_from(ProjectComponentActivityEvent).filter_by(**filters)
    ).scalar_one()


def ids(x):
    """Convention "ids(x)"."""
    return [pair[0].id for pair in x]


def stored_meta(db, row):
    """Convention "stored_meta(X)"."""
    return tuple(db.execute(
        text("SELECT metadata::text, metadata IS NULL FROM project_component_activity_events WHERE id = :i"),
        {"i": row.id},
    ).one())


# Convention "sql_log": a before_cursor_execute listener on db.connection(); removed after the call
@contextmanager
def sql_recorder(db):
    sql_log = []

    def _record(conn, cursor, statement, parameters, context, executemany):
        sql_log.append(statement)

    connection = db.connection()
    event.listen(connection, "before_cursor_execute", _record)
    try:
        yield sql_log
    finally:
        event.remove(connection, "before_cursor_execute", _record)


def written(sql_log):
    """Convention "written(sql_log)"."""
    return [s for s in sql_log if s.strip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]


def locked(sql_log):
    """Convention "locked(sql_log)"."""
    return [s for s in sql_log if "FOR UPDATE" in s.upper()]


# --------------------------------------------------------------------------- #
# ProjectComponentActivityManager.log_event
# --------------------------------------------------------------------------- #

# [claude] PCAM-LE-01
def test_pcam_le_01__one_row_is_stored_with_every_value_given(db, w1, u2, cp1):
    """PCAM-LE-01 — one row is stored with every value given.
    Rules: `log_event` R1, Returns."""
    result = M.log_event(db, project_component_id=cp1.id, workspace_id=w1.id, event_type="work_order_item_used", description="Used 40 Bolt", performed_by=u2.id, metadata={"quantity": 40})
    # Then 1
    assert isinstance(result, ProjectComponentActivityEvent)
    # Then 2
    assert result.id is not None
    # Then 3
    row = reread_event(db, result.id)
    assert row.workspace_id == w1.id
    assert row.project_component_id == cp1.id
    assert row.event_type == "work_order_item_used"
    assert row.description == "Used 40 Bolt"
    assert row.performed_by == u2.id
    # Then 4
    row = reread_event(db, result.id)
    assert row.metadata_json == {"quantity": 40}
    # Then 5
    assert count_events(db, project_component_id=cp1.id) == 1


# [claude] PCAM-LE-02
def test_pcam_le_02__positional_arguments_work_in_the_order_of_the_signature(db, w1, u2, cp1):
    """PCAM-LE-02 — positional arguments work, in the order of the signature.
    Rules: `log_event` R1, Facts (positional-or-keyword)."""
    result = M.log_event(db, cp1.id, w1.id, "attachment_added", "Attached a.png", u2.id, {"attachment_id": 7})
    # Then 1
    row = reread_event(db, result.id)
    assert row.project_component_id == cp1.id
    assert row.workspace_id == w1.id
    assert row.event_type == "attachment_added"
    assert row.description == "Attached a.png"
    assert row.performed_by == u2.id
    # Then 2
    row = reread_event(db, result.id)
    assert row.metadata_json == {"attachment_id": 7}


# [claude] PCAM-LE-03
def test_pcam_le_03__two_identical_calls_give_two_rows(db, w1, cp1):
    """PCAM-LE-03 — two identical calls give two rows.
    Rules: `log_event` R1."""
    first = M.log_event(db, project_component_id=cp1.id, workspace_id=w1.id, event_type="work_order_completed", description="Same")
    result = M.log_event(db, project_component_id=cp1.id, workspace_id=w1.id, event_type="work_order_completed", description="Same")
    # Then 1
    assert result.id != first.id
    # Then 2
    assert count_events(db, project_component_id=cp1.id, description="Same") == 2


# [claude] PCAM-LE-04
def test_pcam_le_04__the_call_is_one_insert_no_other_row_and_not_the_component(db, w1, cp1, cp2):
    """PCAM-LE-04 — the call is one INSERT: no other row and not the component change, no lock.
    Rules: `log_event` R1, Side effects, Overview."""
    a = mk_event(db, w1, cp1, T1)
    b = mk_event(db, w1, cp2, T2)
    before_a = snap(db, a)
    before_b = snap(db, b)
    before_cp1 = snap(db, cp1)
    with sql_recorder(db) as sql_log:
        result = M.log_event(db, project_component_id=cp1.id, workspace_id=w1.id, event_type="attachment_removed", description="Removed a.png")
    # Then 1
    assert result.id not in {a.id, b.id}
    # Then 2
    assert len(written(sql_log)) == 1
    # Then 3
    assert written(sql_log)[0].strip().upper().startswith("INSERT INTO PROJECT_COMPONENT_ACTIVITY_EVENTS")
    # Then 4
    assert locked(sql_log) == []
    # Then 5
    assert reread_snap(db, a) == before_a
    # Then 6
    assert reread_snap(db, b) == before_b
    # Then 7
    assert reread_snap(db, cp1) == before_cp1


# [claude] PCAM-LE-05
def test_pcam_le_05__left_out_metadata_is_json_null_and_performer_null(db, w1, cp1):
    """PCAM-LE-05 — left out, metadata is stored as JSON null and performer as NULL.
    Rules: `log_event` R2."""
    result = M.log_event(db, project_component_id=cp1.id, workspace_id=w1.id, event_type="attachment_added", description="Attached")
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread_event(db, result.id)
    assert row.metadata_json is None
    assert row.performed_by is None
    # Then 3
    db.expire_all()
    assert stored_meta(db, result) == ("null", False)


# [claude] PCAM-LE-06
def test_pcam_le_06__metadata_none_passed_explicitly_is_stored_as_json_null(db, w1, cp1):
    """PCAM-LE-06 — metadata None passed explicitly is stored as JSON null.
    Rules: `log_event` R2."""
    result = M.log_event(db, project_component_id=cp1.id, workspace_id=w1.id, event_type="attachment_added", description="Attached", metadata=None)
    # Then 1
    row = reread_event(db, result.id)
    assert row.metadata_json is None
    # Then 2
    db.expire_all()
    assert stored_meta(db, result) == ("null", False)


# [claude] PCAM-LE-07
def test_pcam_le_07__empty_metadata_is_stored_as_an_empty_object_not_as_null(db, w1, cp1):
    """PCAM-LE-07 — empty metadata is stored as an empty object, not as null.
    Rules: `log_event` R2."""
    result = M.log_event(db, project_component_id=cp1.id, workspace_id=w1.id, event_type="attachment_added", description="Attached", metadata={})
    # Then 1
    row = reread_event(db, result.id)
    assert row.metadata_json == {}
    # Then 2
    db.expire_all()
    assert stored_meta(db, result) == ("{}", False)


# [claude] PCAM-LE-08
def test_pcam_le_08__nested_metadata_with_none_and_a_float_comes_back_equal(db, w1, cp1):
    """PCAM-LE-08 — nested metadata with None and a float comes back equal.
    Rules: `log_event` R3."""
    result = M.log_event(db, project_component_id=cp1.id, workspace_id=w1.id, event_type="work_order_item_used", description="Used", metadata={"lines": [1, {"note": None}], "quantity": 2.5})
    # Then 1
    row = reread_event(db, result.id)
    assert row.metadata_json == {"lines": [1, {"note": None}], "quantity": 2.5}


# [claude] PCAM-LE-09
def test_pcam_le_09__an_empty_event_type_and_an_empty_description_are_stored(db, w1, cp1):
    """PCAM-LE-09 — an empty event type and an empty description are stored.
    Rules: `log_event` R4."""
    result = M.log_event(db, project_component_id=cp1.id, workspace_id=w1.id, event_type="", description="")
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread_event(db, result.id)
    assert row.event_type == ""
    assert row.description == ""


# [claude] PCAM-LE-10
def test_pcam_le_10__an_event_type_of_exactly_50_characters_is_stored(db, w1, cp1):
    """PCAM-LE-10 — an event type of exactly 50 characters is stored.
    Rules: `log_event` R4, Inputs."""
    result = M.log_event(db, project_component_id=cp1.id, workspace_id=w1.id, event_type="x" * 50, description="Attached")
    # Then 1
    row = reread_event(db, result.id)
    assert row.event_type == "x" * 50


# [claude] PCAM-LE-11
def test_pcam_le_11__an_event_type_of_51_characters_is_refused_no_row(db, w1, cp1):
    """PCAM-LE-11 — an event type of 51 characters is refused by the database, no row.
    Rules: `log_event` Errors row 5, Inputs."""
    before_count = event_count(db)
    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            M.log_event(db, project_component_id=cp1.id, workspace_id=w1.id, event_type="x" * 51, description="Attached")
    # Then 2
    assert isinstance(exc.value.orig, StringDataRightTruncation)
    # Then 3
    assert exc.value.orig.pgcode == "22001"
    # Then 4
    assert event_count(db) == before_count


# [claude] PCAM-LE-12
def test_pcam_le_12__created_at_is_set_on_the_row_with_no_time_zone(db, w1, cp1):
    """PCAM-LE-12 — created_at is set on the row, with no time zone.
    Rules: `log_event` R5."""
    result = M.log_event(db, project_component_id=cp1.id, workspace_id=w1.id, event_type="attachment_added", description="Attached")
    # Then 1
    assert result.created_at is not None
    # Then 2
    row = reread_event(db, result.id)
    assert row.created_at is not None
    assert row.created_at.tzinfo is None


# [claude] PCAM-LE-13
@pytest.mark.xfail(strict=True, reason=BUG_1192)
def test_pcam_le_13__another_workspace_s_component_with_a_lower_id_is_refused(db, w1, u1, cp8):
    """PCAM-LE-13 — another workspace's component with a lower id is refused, nothing written.
    Rules: `log_event` R6 [BUG-1192], Errors row 1, HR-16."""
    before_count = event_count(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.log_event(db, project_component_id=cp8.id, workspace_id=w1.id, event_type="attachment_added", description="Attached a.png", performed_by=u1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project component with ID {cp8.id} not found"
    # Then 4
    assert len(db.new) == 0
    # Then 5
    assert event_count(db) == before_count
    # Then 6
    assert count_events(db, project_component_id=cp8.id) == 0


# [claude] PCAM-LE-14
@pytest.mark.xfail(strict=True, reason=BUG_1192)
def test_pcam_le_14__another_workspace_s_component_with_a_higher_id_is_refused(db, w1, u1, cp9):
    """PCAM-LE-14 — another workspace's component with a higher id is refused, nothing written.
    Rules: `log_event` R6 [BUG-1192], Errors row 1, HR-16."""
    before_count = event_count(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.log_event(db, project_component_id=cp9.id, workspace_id=w1.id, event_type="work_order_completed", description="Completed WO-1", performed_by=u1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project component with ID {cp9.id} not found"
    # Then 4
    assert len(db.new) == 0
    # Then 5
    assert event_count(db) == before_count
    # Then 6
    assert count_events(db, project_component_id=cp9.id) == 0


# [claude] PCAM-LE-15
@pytest.mark.xfail(strict=True, reason=BUG_1192)
def test_pcam_le_15__an_unknown_component_gets_the_same_404(db, w1):
    """PCAM-LE-15 — an unknown component gets the same 404.
    Rules: `log_event` R6 [BUG-1192], Errors rows 1, 2."""
    before_count = event_count(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with db.begin_nested():
            M.log_event(db, project_component_id=MISSING, workspace_id=w1.id, event_type="attachment_added", description="Attached")
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Project component with ID 999999999 not found"
    # Then 4
    assert event_count(db) == before_count


# [claude] PCAM-LE-16
@pytest.mark.xfail(strict=True, reason=BUG_1192)
def test_pcam_le_16__component_id_0_gets_the_same_404(db, w1):
    """PCAM-LE-16 — component id 0 gets the same 404.
    Rules: `log_event` R6 [BUG-1192], Errors rows 1, 2."""
    before_count = event_count(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with db.begin_nested():
            M.log_event(db, project_component_id=0, workspace_id=w1.id, event_type="attachment_added", description="Attached")
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Project component with ID 0 not found"
    # Then 4
    assert event_count(db) == before_count


# [claude] PCAM-LE-17
@pytest.mark.xfail(strict=True, reason=BUG_1192)
def test_pcam_le_17__an_unknown_workspace_gets_the_same_404_naming_the_component(db, cp1):
    """PCAM-LE-17 — an unknown workspace gets the same 404, naming the component.
    Rules: `log_event` R6 [BUG-1192], Errors rows 1, 2."""
    before_count = event_count(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with db.begin_nested():
            M.log_event(db, project_component_id=cp1.id, workspace_id=MISSING, event_type="attachment_added", description="Attached")
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project component with ID {cp1.id} not found"
    # Then 4
    assert event_count(db) == before_count


# [claude] PCAM-LE-18
def test_pcam_le_18__w2_s_own_component_is_accepted_from_w2(db, w2, cp9):
    """PCAM-LE-18 — W2's own component is accepted from W2.
    Rules: `log_event` R1, R6."""
    result = M.log_event(db, project_component_id=cp9.id, workspace_id=w2.id, event_type="attachment_added", description="Attached b.png")
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread_event(db, result.id)
    assert row.project_component_id == cp9.id
    assert row.workspace_id == w2.id
    assert row.description == "Attached b.png"
    # Then 3
    assert count_events(db, project_component_id=cp9.id) == 1


# [claude] PCAM-LE-19
def test_pcam_le_19__a_component_of_a_soft_deleted_project_is_accepted(db, w1, u1, cpd):
    """PCAM-LE-19 — a component of a soft-deleted project is accepted.
    Rules: `log_event` R7."""
    result = M.log_event(db, project_component_id=cpd.id, workspace_id=w1.id, event_type="attachment_removed", description="Removed a.png", performed_by=u1.id)
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread_event(db, result.id)
    assert row.project_component_id == cpd.id
    assert row.workspace_id == w1.id
    assert row.event_type == "attachment_removed"
    # Then 3
    assert count_events(db, project_component_id=cpd.id) == 1


# [claude] PCAM-LE-20
def test_pcam_le_20__an_unknown_performer_is_refused_by_the_database_no_row(db, w1, cp1):
    """PCAM-LE-20 — an unknown performer is refused by the database, no row.
    Rules: `log_event` R8, Errors row 3."""
    before_count = event_count(db)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            M.log_event(db, project_component_id=cp1.id, workspace_id=w1.id, event_type="attachment_added", description="Attached", performed_by=MISSING)
    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert exc.value.orig.pgcode == "23503"
    # Then 4
    assert event_count(db) == before_count


# [claude] PCAM-LE-21
def test_pcam_le_21__performer_0_is_refused_not_read_as_no_performer(db, w1, cp1):
    """PCAM-LE-21 — performer 0 is refused, not read as no performer.
    Rules: `log_event` R8, Errors row 3."""
    before_count = event_count(db)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            M.log_event(db, project_component_id=cp1.id, workspace_id=w1.id, event_type="attachment_added", description="Attached", performed_by=0)
    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert exc.value.orig.pgcode == "23503"
    # Then 4
    assert event_count(db) == before_count


# [claude] PCAM-LE-22
def test_pcam_le_22__a_performer_is_not_checked_against_the_workspace(db, w1, cp1):
    """PCAM-LE-22 — a performer is not checked against the workspace.
    Rules: `log_event` R8."""
    outsider = make_profile(db)
    result = M.log_event(db, project_component_id=cp1.id, workspace_id=w1.id, event_type="attachment_added", description="Attached", performed_by=outsider.id)
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread_event(db, result.id)
    assert row.performed_by == outsider.id


# [claude] PCAM-LE-23
def test_pcam_le_23__a_decimal_in_metadata_fails_at_the_flush_no_row(db, w1, cp1):
    """PCAM-LE-23 — a Decimal in metadata fails at the flush, no row.
    Rules: `log_event` R9, Errors row 6."""
    before_count = event_count(db)
    # Then 1
    with pytest.raises(StatementError) as exc:
        with db.begin_nested():
            M.log_event(db, project_component_id=cp1.id, workspace_id=w1.id, event_type="work_order_item_used", description="Used", metadata={"quantity": Decimal("1.50")})
    # Then 2
    assert isinstance(exc.value.orig, TypeError)
    # Then 3
    assert getattr(exc.value.orig, "pgcode", None) is None
    # Then 4
    assert event_count(db) == before_count


# [claude] PCAM-LE-24
def test_pcam_le_24__event_type_none_is_refused_by_the_database_no_row(db, w1, cp1):
    """PCAM-LE-24 — event type None is refused by the database, no row.
    Rules: `log_event` Errors row 4."""
    before_count = event_count(db)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            M.log_event(db, project_component_id=cp1.id, workspace_id=w1.id, event_type=None, description="Attached")
    # Then 2
    assert isinstance(exc.value.orig, NotNullViolation)
    # Then 3
    assert exc.value.orig.pgcode == "23502"
    # Then 4
    assert event_count(db) == before_count


# [claude] PCAM-LE-25
def test_pcam_le_25__flushed_not_committed_a_savepoint_rollback_removes_the_row(db, w1, cp1):
    """PCAM-LE-25 — flushed, not committed: a savepoint's rollback removes the row.
    Rules: `log_event` R10, Returns, Side effects."""
    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        result = M.log_event(db, project_component_id=cp1.id, workspace_id=w1.id, event_type="attachment_added", description="Attached")
    # Then 1
    assert result.id is not None
    # Then 2
    assert count_events(db, project_component_id=cp1.id) == 1
    # Then 3
    commit_spy.assert_not_called()
    # Then 4
    sp.rollback()
    assert count_events(db, project_component_id=cp1.id) == 0


# --------------------------------------------------------------------------- #
# ProjectComponentActivityManager.list_events
# --------------------------------------------------------------------------- #

# [claude] PCAM-LI-01
def test_pcam_li_01__the_component_s_events_come_back_newest_first_as_2_tuples(db, w1, cp1):
    """PCAM-LI-01 — the component's events come back newest first, as 2-tuples.
    Rules: `list_events` R1, Returns."""
    a = mk_event(db, w1, cp1, T2)
    b = mk_event(db, w1, cp1, T3, event_type="work_order_completed")
    c = mk_event(db, w1, cp1, T1, event_type="work_order_item_used")
    result = M.list_events(db, project_component_id=cp1.id, workspace_id=w1.id)
    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [b.id, a.id, c.id]
    # Then 3
    assert isinstance(result[0], tuple)
    assert len(result[0]) == 2
    # Then 4
    assert isinstance(result[0][0], ProjectComponentActivityEvent)


# [claude] PCAM-LI-02
def test_pcam_li_02__created_at_decides_first_then_the_higher_id(db, w1, u1, u2, cp1):
    """PCAM-LI-02 — created_at decides first, then the higher id; no other column does.
    Rules: `list_events` R1 (DAO `get_by_component` R5)."""
    a = mk_event(db, w1, cp1, T2, event_type="work_order_completed", description="Zeta", performed_by=u2.id)
    b = mk_event(db, w1, cp1, datetime(2026, 3, 5, 9, 0, 0), event_type="attachment_added", description="Alpha", performed_by=u1.id)
    c = mk_event(db, w1, cp1, T2, event_type="work_order_item_used", description="Mid")
    result = M.list_events(db, project_component_id=cp1.id, workspace_id=w1.id)
    # Then 1
    assert ids(result) == [c.id, a.id, b.id]


# [claude] PCAM-LI-03
def test_pcam_li_03__skip_and_limit_reach_the_read_by_position_not_swapped(db, w1, cp1):
    """PCAM-LI-03 — skip and limit reach the read by position, not swapped.
    Rules: `list_events` R1, Facts (positional-or-keyword)."""
    mk_event(db, w1, cp1, T1)
    b = mk_event(db, w1, cp1, T2)
    c = mk_event(db, w1, cp1, T3)
    mk_event(db, w1, cp1, T4)
    result = M.list_events(db, cp1.id, w1.id, 1, 2)
    # Then 1
    assert ids(result) == [c.id, b.id]


# [claude] PCAM-LI-04
def test_pcam_li_04__another_component_s_row_ahead_of_the_skipped_row_takes_no(db, w1, cp1, cp2):
    """PCAM-LI-04 — another component's row ahead of the skipped row takes no place.
    Rules: `list_events` R1 (DAO `get_by_component` R1), HR-5."""
    r = mk_event(db, w1, cp1, T1)
    mk_event(db, w1, cp1, T2)
    mk_event(db, w1, cp2, T3)
    result = M.list_events(db, project_component_id=cp1.id, workspace_id=w1.id, skip=1, limit=1)
    # Then 1
    assert ids(result) == [r.id]


# [claude] PCAM-LI-05
def test_pcam_li_05__another_workspace_s_component_with_a_lower_id_gets_404(db, w1, w2, cp8):
    """PCAM-LI-05 — another workspace's component with a lower id gets 404, and no event is read.
    Rules: `list_events` R2, Errors row 1, HR-16."""
    mk_event(db, w2, cp8, T1)
    before_count = event_count(db)
    with sql_recorder(db) as sql_log:
        # Then 1
        with pytest.raises(HTTPException) as exc:
            M.list_events(db, project_component_id=cp8.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project component with ID {cp8.id} not found"
    # Then 4
    assert len(sql_log) == 1
    # Then 5
    assert event_count(db) == before_count


# [claude] PCAM-LI-06
def test_pcam_li_06__another_workspace_s_component_with_a_higher_id_gets_404(db, w1, w2, cp9):
    """PCAM-LI-06 — another workspace's component with a higher id gets 404, and no event is read.
    Rules: `list_events` R2, Errors row 1, HR-16."""
    mk_event(db, w2, cp9, T1)
    before_count = event_count(db)
    with sql_recorder(db) as sql_log:
        # Then 1
        with pytest.raises(HTTPException) as exc:
            M.list_events(db, project_component_id=cp9.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project component with ID {cp9.id} not found"
    # Then 4
    assert len(sql_log) == 1
    # Then 5
    assert event_count(db) == before_count


# [claude] PCAM-LI-07
def test_pcam_li_07__an_unknown_component_gets_the_same_404(db, w1):
    """PCAM-LI-07 — an unknown component gets the same 404.
    Rules: `list_events` R2, Errors row 1."""
    before_count = event_count(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.list_events(db, project_component_id=MISSING, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Project component with ID 999999999 not found"
    # Then 4
    assert event_count(db) == before_count


# [claude] PCAM-LI-08
def test_pcam_li_08__component_id_0_gets_the_same_404(db, w1):
    """PCAM-LI-08 — component id 0 gets the same 404.
    Rules: `list_events` R2, Errors row 1."""
    before_count = event_count(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.list_events(db, project_component_id=0, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Project component with ID 0 not found"
    # Then 4
    assert event_count(db) == before_count


# [claude] PCAM-LI-09
def test_pcam_li_09__a_negative_component_id_gets_the_same_404(db, w1):
    """PCAM-LI-09 — a negative component id gets the same 404.
    Rules: `list_events` R2, Errors row 1."""
    before_count = event_count(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.list_events(db, project_component_id=-1, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Project component with ID -1 not found"
    # Then 4
    assert event_count(db) == before_count


# [claude] PCAM-LI-10
def test_pcam_li_10__the_component_check_comes_before_the_page(db, w1, w2, cp9):
    """PCAM-LI-10 — the component check comes before the page: a foreign component with a negative limit gets 404.
    Rules: `list_events` R2, R9, Errors rows 1, 2."""
    mk_event(db, w2, cp9, T1)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.list_events(db, project_component_id=cp9.id, workspace_id=w1.id, limit=-1)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project component with ID {cp9.id} not found"


# [claude] PCAM-LI-11
def test_pcam_li_11__a_w1_row_on_w2_s_component_does_not_reach_w1(db, w1, cp9):
    """PCAM-LI-11 — a W1 row on W2's component does not reach W1: it gets the 404.
    Rules: `list_events` R3, HR-16."""
    a = mk_event(db, w1, cp9, T1)
    before_a = snap(db, a)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.list_events(db, project_component_id=cp9.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project component with ID {cp9.id} not found"
    # Then 4
    assert reread_snap(db, a) == before_a


# [claude] PCAM-LI-12
def test_pcam_li_12__w2_s_page_leaves_out_the_w1_row_on_its_component(db, w1, w2, cp9):
    """PCAM-LI-12 — W2's page leaves out the W1 row on its component, and it takes no place.
    Rules: `list_events` R3, R1, HR-16, HR-5."""
    r = mk_event(db, w2, cp9, T1)
    mk_event(db, w2, cp9, T2)
    mk_event(db, w1, cp9, T3)
    result = M.list_events(db, project_component_id=cp9.id, workspace_id=w2.id, skip=1, limit=1)
    # Then 1
    assert ids(result) == [r.id]


# [claude] PCAM-LI-13
def test_pcam_li_13__a_component_of_a_soft_deleted_project_returns_every_event(db, w1, cpd):
    """PCAM-LI-13 — a component of a soft-deleted project returns every event.
    Rules: `list_events` R4."""
    a = mk_event(db, w1, cpd, T1)
    b = mk_event(db, w1, cpd, T2, event_type="work_order_completed")
    result = M.list_events(db, project_component_id=cpd.id, workspace_id=w1.id)
    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] PCAM-LI-14
def test_pcam_li_14__a_component_with_no_events_gives_an_empty_list(db, w1, cp1, cp2):
    """PCAM-LI-14 — a component with no events gives an empty list.
    Rules: `list_events` R5."""
    mk_event(db, w1, cp2, T1)
    result = M.list_events(db, project_component_id=cp1.id, workspace_id=w1.id)
    # Then 1
    assert result == []


# [claude] PCAM-LI-15
def test_pcam_li_15__the_first_element_holds_the_stored_metadata_whole_or_none(db, w1, cp1):
    """PCAM-LI-15 — the first element holds the stored metadata whole, or None.
    Rules: `list_events` R6."""
    a = mk_event(db, w1, cp1, T1, description="Attached a.png", metadata_json={"attachment_id": 7, "file_name": "a.png", "sizes": [1, 2.5], "note": None})
    b = mk_event(db, w1, cp1, T2, metadata_json=None)
    result = M.list_events(db, project_component_id=cp1.id, workspace_id=w1.id)
    # Then 1
    assert ids(result) == [b.id, a.id]
    # Then 2
    assert result[1][0].description == "Attached a.png"
    # Then 3
    assert result[1][0].metadata_json == {"attachment_id": 7, "file_name": "a.png", "sizes": [1, 2.5], "note": None}
    # Then 4
    assert result[0][0].metadata_json is None


# [claude] PCAM-LI-16
def test_pcam_li_16__each_entry_holds_its_own_performer_or_none(db, w1, u1, u2, cp1):
    """PCAM-LI-16 — each entry holds its own performer or None; one person is one instance.
    Rules: `list_events` R7."""
    a = mk_event(db, w1, cp1, T1, performed_by=u2.id)
    b = mk_event(db, w1, cp1, T2)
    c = mk_event(db, w1, cp1, T3, performed_by=u1.id)
    d = mk_event(db, w1, cp1, T4, performed_by=u1.id)
    result = M.list_events(db, project_component_id=cp1.id, workspace_id=w1.id)
    # Then 1
    assert ids(result) == [d.id, c.id, b.id, a.id]
    # Then 2
    assert result[0][1].id == u1.id
    # Then 3
    assert result[1][1] is result[0][1]
    # Then 4
    assert result[2][1] is None
    # Then 5
    assert result[3][1].id == u2.id


# [claude] PCAM-LI-17
def test_pcam_li_17__with_the_defaults_100_of_101_entries_come_back_the_newest(db, w1, cp1):
    """PCAM-LI-17 — with the defaults 100 of 101 entries come back, the newest.
    Rules: `list_events` R9."""
    mk_log(db, w1, cp1, 101)
    result = M.list_events(db, project_component_id=cp1.id, workspace_id=w1.id)
    # Then 1
    assert len(result) == 100
    # Then 2
    assert result[0][0].description == "E100"
    # Then 3
    assert result[99][0].description == "E1"


# [claude] PCAM-LI-18
def test_pcam_li_18__limit_1000_gives_1000_of_1000(db, w1, cp1):
    """PCAM-LI-18 — limit 1000 gives 1000 of 1000.
    Rules: `list_events` R9, R1."""
    mk_log(db, w1, cp1, 1000)
    result = M.list_events(db, project_component_id=cp1.id, workspace_id=w1.id, limit=1000)
    # Then 1
    assert len(result) == 1000
    # Then 2
    assert result[0][0].description == "E999"
    # Then 3
    assert result[999][0].description == "E0"


# [claude] PCAM-LI-19
def test_pcam_li_19__limit_0_gives_an_empty_list(db, w1, cp1):
    """PCAM-LI-19 — limit 0 gives an empty list.
    Rules: `list_events` R9."""
    mk_event(db, w1, cp1, T1)
    result = M.list_events(db, project_component_id=cp1.id, workspace_id=w1.id, limit=0)
    # Then 1
    assert result == []


# [claude] PCAM-LI-20
def test_pcam_li_20__skip_at_the_number_of_rows_gives_an_empty_list(db, w1, cp1):
    """PCAM-LI-20 — skip at the number of rows gives an empty list.
    Rules: `list_events` R9."""
    mk_event(db, w1, cp1, T1)
    mk_event(db, w1, cp1, T2)
    result = M.list_events(db, project_component_id=cp1.id, workspace_id=w1.id, skip=2)
    # Then 1
    assert result == []


# [claude] PCAM-LI-21
def test_pcam_li_21__skip_one_below_the_number_of_rows_gives_the_oldest_row(db, w1, cp1):
    """PCAM-LI-21 — skip one below the number of rows gives the oldest row.
    Rules: `list_events` R9."""
    a = mk_event(db, w1, cp1, T1)
    mk_event(db, w1, cp1, T2)
    result = M.list_events(db, project_component_id=cp1.id, workspace_id=w1.id, skip=1)
    # Then 1
    assert ids(result) == [a.id]


# [claude] PCAM-LI-22
def test_pcam_li_22__a_negative_limit_raises_dataerror(db, w1, cp1):
    """PCAM-LI-22 — a negative limit raises DataError.
    Rules: `list_events` R9, Errors row 2."""
    mk_event(db, w1, cp1, T1)
    before_count = event_count(db)
    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            M.list_events(db, project_component_id=cp1.id, workspace_id=w1.id, limit=-1)
    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInLimitClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201W"
    # Then 4
    assert event_count(db) == before_count


# [claude] PCAM-LI-23
def test_pcam_li_23__a_negative_skip_raises_dataerror(db, w1, cp1):
    """PCAM-LI-23 — a negative skip raises DataError.
    Rules: `list_events` R9, Errors row 2."""
    mk_event(db, w1, cp1, T1)
    before_count = event_count(db)
    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            M.list_events(db, project_component_id=cp1.id, workspace_id=w1.id, skip=-1)
    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201X"
    # Then 4
    assert event_count(db) == before_count


# [claude] PCAM-LI-24
def test_pcam_li_24__one_entry_with_a_performer_stays_within_three_reads(db, w1, u1, cp1):
    """PCAM-LI-24 — one entry with a performer stays within three reads.
    Rules: `list_events` R8, R7."""
    a = mk_event(db, w1, cp1, T1, performed_by=u1.id)
    with sql_recorder(db) as sql_log:
        result = M.list_events(db, project_component_id=cp1.id, workspace_id=w1.id)
    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert result[0][1].id == u1.id
    # Then 3
    assert len(sql_log) <= 3


# [claude] PCAM-LI-25
@pytest.mark.xfail(strict=True, reason=BUG_1712)
def test_pcam_li_25__five_entries_by_one_person_make_at_most_three_reads(db, w1, u1, cp1):
    """PCAM-LI-25 — five entries by one person make at most three reads.
    Rules: `list_events` R8 [BUG-1712], R7."""
    a = mk_event(db, w1, cp1, datetime(2026, 3, 1, 10, 0, 0), performed_by=u1.id)
    b = mk_event(db, w1, cp1, datetime(2026, 3, 2, 10, 0, 0), performed_by=u1.id)
    c = mk_event(db, w1, cp1, datetime(2026, 3, 3, 10, 0, 0), performed_by=u1.id)
    d = mk_event(db, w1, cp1, datetime(2026, 3, 4, 10, 0, 0), performed_by=u1.id)
    e = mk_event(db, w1, cp1, datetime(2026, 3, 5, 10, 0, 0), performed_by=u1.id)
    with sql_recorder(db) as sql_log:
        result = M.list_events(db, project_component_id=cp1.id, workspace_id=w1.id)
    # Then 1
    assert ids(result) == [e.id, d.id, c.id, b.id, a.id]
    # Then 2
    assert [pair[1].id for pair in result] == [u1.id] * 5
    # Then 3
    assert len(sql_log) <= 3


# [claude] PCAM-LI-26
@pytest.mark.xfail(strict=True, reason=BUG_1712)
def test_pcam_li_26__entries_by_two_people_and_by_nobody_make_at_most_three(db, w1, u1, u2, cp1):
    """PCAM-LI-26 — entries by two people and by nobody make at most three reads.
    Rules: `list_events` R8 [BUG-1712], R7."""
    a = mk_event(db, w1, cp1, datetime(2026, 3, 1, 10, 0, 0), performed_by=u1.id)
    b = mk_event(db, w1, cp1, datetime(2026, 3, 2, 10, 0, 0), performed_by=u2.id)
    c = mk_event(db, w1, cp1, datetime(2026, 3, 3, 10, 0, 0))
    d = mk_event(db, w1, cp1, datetime(2026, 3, 4, 10, 0, 0), performed_by=u1.id)
    e = mk_event(db, w1, cp1, datetime(2026, 3, 5, 10, 0, 0), performed_by=u2.id)
    with sql_recorder(db) as sql_log:
        result = M.list_events(db, project_component_id=cp1.id, workspace_id=w1.id)
    # Then 1
    assert ids(result) == [e.id, d.id, c.id, b.id, a.id]
    # Then 2
    assert [pair[1].id if pair[1] else None for pair in result] == [u2.id, u1.id, None, u2.id, u1.id]
    # Then 3
    assert len(sql_log) <= 3


# [claude] PCAM-LI-27
def test_pcam_li_27__writes_nothing_a_pending_row_stays_pending_an_edit_dirty(db, w1, cp1, cp2):
    """PCAM-LI-27 — writes nothing: a pending row stays pending, a caller's edit stays dirty.
    Rules: `list_events` R10, Side effects, Overview."""
    a = mk_event(db, w1, cp1, T1)
    p = ProjectComponentActivityEvent(workspace_id=w1.id, project_component_id=cp1.id, event_type="attachment_added", description="Pending", created_at=T2)
    db.add(p)
    cp2.name = "Wall 2"
    before_count = event_count(db)
    before_a = snap(db, a)
    with sql_recorder(db) as sql_log:
        result = M.list_events(db, project_component_id=cp1.id, workspace_id=w1.id)
    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert p.id is None
    # Then 5
    assert cp2 in db.dirty
    # Then 6
    assert len(db.dirty) == 1
    # Then 7
    assert not db.deleted
    # Then 8
    assert cp2.name == "Wall 2"
    # Then 9
    assert written(sql_log) == []
    # Then 10
    assert locked(sql_log) == []
    # Then 11
    assert event_count(db) == before_count
    # Then 12
    assert reread_snap(db, a) == before_a
