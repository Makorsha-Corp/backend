"""Unit tests for app/dao/project_component_activity_event.py.

Implements tests/unit/dao/project_component_activity_event.cases.md, one test per case, in card
order. Real Postgres session (`db` fixture). Nothing is mocked and no clock
is patched (Conventions, Externals: None).

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117, DTZ001  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`, and naive datetimes)
from datetime import datetime, timedelta

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import DataError

from app.dao.project_component_activity_event import (
    project_component_activity_event_dao,
)
from app.models.factory import Factory
from app.models.project import Project
from app.models.project_component import ProjectComponent
from app.models.project_component_activity_event import ProjectComponentActivityEvent
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton project_component_activity_event_dao" (a module-level name, not a fixture)
dao = project_component_activity_event_dao

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999

# Convention "T1, T2, T3"
T1 = datetime(2026, 3, 4, 10, 0, 0)
T2 = datetime(2026, 3, 5, 10, 0, 0)
T3 = datetime(2026, 3, 6, 10, 0, 0)


# --------------------------------------------------------------------------- #
# Conventions -> the rows that exist in every test
# --------------------------------------------------------------------------- #

def _add(db, row):
    db.add(row)
    db.flush()
    return row


# Convention "W1, W2 = two workspaces rows". w2 depends on w1, so the ids rise in
# the order the Conventions list them.
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


# Convention "U1 = a profiles row"
@pytest.fixture
def u1(db):
    return make_profile(db)


# Convention "F1"
@pytest.fixture
def f1(db, w1):
    return _add(db, Factory(workspace_id=w1.id, name="Factory One", abbreviation="F1"))


# Convention "F9"
@pytest.fixture
def f9(db, w2):
    return _add(db, Factory(workspace_id=w2.id, name="Factory Nine", abbreviation="F9"))


# Convention "PJ1"
@pytest.fixture
def pj1(db, w1, f1):
    return _add(db, Project(workspace_id=w1.id, factory_id=f1.id, name="Project One", description="Main"))


# Convention "PJ9"
@pytest.fixture
def pj9(db, w2, f9):
    return _add(db, Project(workspace_id=w2.id, factory_id=f9.id, name="Project Nine", description="Main"))


# Convention "CP1"
@pytest.fixture
def cp1(db, w1, pj1):
    return _add(db, ProjectComponent(workspace_id=w1.id, project_id=pj1.id, name="Roof"))


# Convention "CP2"
@pytest.fixture
def cp2(db, w1, pj1):
    return _add(db, ProjectComponent(workspace_id=w1.id, project_id=pj1.id, name="Wall"))


# Convention "CP9"
@pytest.fixture
def cp9(db, w2, pj9):
    return _add(db, ProjectComponent(workspace_id=w2.id, project_id=pj9.id, name="Floor"))


# Convention "These rows exist in every test and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2, u1, f1, f9, pj1, pj9, cp1, cp2, cp9):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builders (fixtures; each flushes before it returns)
# --------------------------------------------------------------------------- #

# Convention "event": W1, CP1, attachment_added, "Logged"; metadata_json and performed_by not passed
@pytest.fixture
def mk_event(db, w1, cp1):
    """mk_event(created_at=..., **columns) -> ProjectComponentActivityEvent. Keywords only."""
    def _mk(*, created_at, **columns):
        fields = {"workspace_id": w1.id, "project_component_id": cp1.id, "event_type": "attachment_added",
                  "description": "Logged", "created_at": created_at}
        fields.update(columns)
        return _add(db, ProjectComponentActivityEvent(**fields))
    return _mk


# The "101 events E1 ... E101, built with add_all" Given
@pytest.fixture
def mk_log(db, w1, cp1):
    """mk_log(count) -> `newest_first`: the ids of Ecount ... E1, Ek at T1 + k minutes."""
    def _mk(count):
        rows = [ProjectComponentActivityEvent(workspace_id=w1.id, project_component_id=cp1.id, event_type="attachment_added",
                                              description="Logged", created_at=T1 + timedelta(minutes=k))
                for k in range(1, count + 1)]
        db.add_all(rows)
        db.flush()
        return [row.id for row in reversed(rows)]
    return _mk


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (plain functions; no expected values inside)
# --------------------------------------------------------------------------- #

# Convention "ids(result)": in the order returned
def ids(result):
    return [row.id for row in result]


# Convention "unchanged(X)": every column of X, straight from the table
def snap(db, row):
    """Dict column -> database value of `row`, or None if it is gone."""
    table = type(row).__table__
    found = db.execute(select(table).where(table.c.id == sa_inspect(row).identity[0])).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "nothing written": the number of project_component_activity_events rows stored (all workspaces)
def stored_count(db):
    return db.execute(select(func.count()).select_from(ProjectComponentActivityEvent.__table__)).scalar_one()


# Convention "stored_json(X)": the stored text; None for SQL NULL, "null" for JSON null
def stored_json(db, row):
    return db.scalar(text("SELECT metadata::text FROM project_component_activity_events WHERE id = :i"), {"i": row.id})


# Convention "Statement recorder": the SQL text of every statement the session's
# connection sends while the block runs.
class StatementRecorder:
    def __init__(self, db):
        self.bind = db.get_bind()
        self.statements = []

    def _record(self, conn, cursor, statement, parameters, context, executemany):
        self.statements.append(statement)

    def __enter__(self):
        event.listen(self.bind, "before_cursor_execute", self._record)
        return self

    def __exit__(self, *exc_info):
        event.remove(self.bind, "before_cursor_execute", self._record)
        return False

    def selects(self):
        return [s for s in self.statements if s.lstrip().upper().startswith("SELECT")]

    def written(self):
        return [s for s in self.statements if s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]

    def sql(self):
        """The one SELECT from project_component_activity_events; fails loudly unless there is exactly one."""
        [statement] = [s for s in self.selects() if "project_component_activity_events" in s]
        return statement


# --------------------------------------------------------------------------- #
# ProjectComponentActivityEventDAO.get_by_component
# --------------------------------------------------------------------------- #


# [claude] PCE-G-01
def test_pce_g_01__returns_a_list_of_the_project_component_s_rows_of_every_event_type(db, w1, cp1, mk_event):
    """PCE-G-01 — returns a list of the project component's rows of every event type.
    Rules: `get_by_component` R1, Returns"""
    a = mk_event(created_at=T1, event_type="attachment_added")
    b = mk_event(created_at=T2, event_type="work_order_item_used")
    c = mk_event(created_at=T3, event_type="work_order_completed")

    result = dao.get_by_component(db, project_component_id=cp1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [c.id, b.id, a.id]
    # Then 3
    assert isinstance(result[0], ProjectComponentActivityEvent)


# [claude] PCE-G-02
def test_pce_g_02__a_newer_row_of_another_project_component_is_not_returned_and_takes_no_p(db, w1, cp1, cp2, mk_event):
    """PCE-G-02 — a newer row of another project component is not returned and takes no place in the page.
    Rules: `get_by_component` R1"""
    a = mk_event(created_at=T1)
    mk_event(created_at=T2, project_component_id=cp2.id)

    result = dao.get_by_component(db, project_component_id=cp1.id, workspace_id=w1.id, limit=1)

    # Then 1
    assert ids(result) == [a.id]


# [claude] PCE-G-03
def test_pce_g_03__the_right_project_component_under_another_workspace_returns_an_empty_li(db, w2, cp1, mk_event):
    """PCE-G-03 — the right project component under another workspace returns an empty list.
    Rules: `get_by_component` R2"""
    mk_event(created_at=T1)

    result = dao.get_by_component(db, project_component_id=cp1.id, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] PCE-G-04
def test_pce_g_04__a_newer_w2_row_on_the_same_project_component_is_not_returned_and_takes(db, w1, w2, cp1, mk_event):
    """PCE-G-04 — a newer W2 row on the same project component is not returned and takes no place in the page.
    Rules: `get_by_component` R2"""
    a = mk_event(created_at=T1)
    mk_event(created_at=T2, workspace_id=w2.id)

    result = dao.get_by_component(db, project_component_id=cp1.id, workspace_id=w1.id, limit=1)

    # Then 1
    assert ids(result) == [a.id]


# [claude] PCE-G-05
def test_pce_g_05__a_w2_row_on_a_project_component_of_w1_is_returned_for_w2_only_the_row_s(db, w2, cp1, mk_event):
    """PCE-G-05 — a W2 row on a project component of W1 is returned for W2: only the row's workspace is compared.
    Rules: `get_by_component` R2"""
    z = mk_event(created_at=T1, workspace_id=w2.id)

    result = dao.get_by_component(db, project_component_id=cp1.id, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [z.id]


# [claude] PCE-G-06
def test_pce_g_06__a_w2_row_on_a_project_component_of_w1_is_not_returned_for_w1(db, w1, w2, cp1, mk_event):
    """PCE-G-06 — a W2 row on a project component of W1 is not returned for W1.
    Rules: `get_by_component` R2"""
    mk_event(created_at=T1, workspace_id=w2.id)

    result = dao.get_by_component(db, project_component_id=cp1.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PCE-G-07
def test_pce_g_07__an_unknown_project_component_id_returns_an_empty_list(db, w1, mk_event):
    """PCE-G-07 — an unknown project component id returns an empty list.
    Rules: `get_by_component` R3"""
    mk_event(created_at=T1)

    result = dao.get_by_component(db, project_component_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PCE-G-08
def test_pce_g_08__project_component_id_0_returns_an_empty_list(db, w1, mk_event):
    """PCE-G-08 — project_component_id=0 returns an empty list.
    Rules: `get_by_component` R3"""
    mk_event(created_at=T1)

    result = dao.get_by_component(db, project_component_id=0, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PCE-G-09
def test_pce_g_09__an_unknown_workspace_returns_an_empty_list(db, cp1, mk_event):
    """PCE-G-09 — an unknown workspace returns an empty list.
    Rules: `get_by_component` R3"""
    mk_event(created_at=T1)

    result = dao.get_by_component(db, project_component_id=cp1.id, workspace_id=MISSING)

    # Then 1
    assert result == []


# [claude] PCE-G-10
def test_pce_g_10__a_project_component_with_no_events_returns_an_empty_list(db, w1, cp2, mk_event):
    """PCE-G-10 — a project component with no events returns an empty list.
    Rules: `get_by_component` R3"""
    mk_event(created_at=T1)

    result = dao.get_by_component(db, project_component_id=cp2.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PCE-G-11
def test_pce_g_11__after_a_hard_delete_of_the_project_component_its_rows_are_gone_and_the(db, w1, cp1, cp2, mk_event):
    """PCE-G-11 — after a hard delete of the project component its rows are gone and the call returns an empty list.
    Rules: `get_by_component` R4"""
    mk_event(created_at=T1)
    mk_event(created_at=T2)
    mk_event(created_at=T3, project_component_id=cp2.id)
    db.execute(text("DELETE FROM project_components WHERE id = :i"), {"i": cp1.id})

    result = dao.get_by_component(db, project_component_id=cp1.id, workspace_id=w1.id)

    # Then 1
    assert result == []
    # Then 2
    assert db.scalar(text("SELECT count(*) FROM project_component_activity_events WHERE project_component_id = :i"), {"i": cp1.id}) == 0
    # Then 3
    assert db.scalar(text("SELECT count(*) FROM project_component_activity_events WHERE project_component_id = :i"), {"i": cp2.id}) == 1


# [claude] PCE-G-12
def test_pce_g_12__rows_are_ordered_by_created_at_descending_then_id_descending(db, w1, cp1, mk_event):
    """PCE-G-12 — rows are ordered by created_at descending, then id descending.
    Rules: `get_by_component` R5"""
    a = mk_event(created_at=T2)
    b = mk_event(created_at=T3)
    c = mk_event(created_at=T1)
    d = mk_event(created_at=T3)

    result = dao.get_by_component(db, project_component_id=cp1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [d.id, b.id, a.id, c.id]


# [claude] PCE-G-13
def test_pce_g_13__on_a_created_at_tie_with_no_update_the_higher_id_comes_first(db, w1, cp1, mk_event):
    """PCE-G-13 — on a created_at tie with no update the higher id comes first.
    Rules: `get_by_component` R5"""
    a = mk_event(created_at=T2)
    b = mk_event(created_at=T2)

    result = dao.get_by_component(db, project_component_id=cp1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] PCE-G-14
def test_pce_g_14__on_a_created_at_tie_the_higher_id_still_comes_first_after_the_lower_row(db, w1, cp1, mk_event):
    """PCE-G-14 — on a created_at tie the higher id still comes first after the lower row is updated.
    Rules: `get_by_component` R5"""
    a = mk_event(created_at=T2)
    b = mk_event(created_at=T2)
    a.description = "Edited"
    db.flush()
    db.expire_all()

    result = dao.get_by_component(db, project_component_id=cp1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] PCE-G-15
def test_pce_g_15__a_row_of_another_component_ahead_of_the_skipped_row_does_not_count_as_s(db, w1, cp1, cp2, mk_event):
    """PCE-G-15 — a row of another component ahead of the skipped row does not count as skipped.
    Rules: `get_by_component` R1, R6"""
    a = mk_event(created_at=T1)
    mk_event(created_at=T2)
    mk_event(created_at=T3, project_component_id=cp2.id)

    result = dao.get_by_component(db, project_component_id=cp1.id, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [a.id]


# [claude] PCE-G-16
def test_pce_g_16__a_w2_row_ahead_of_the_skipped_row_does_not_count_as_skipped(db, w1, w2, cp1, mk_event):
    """PCE-G-16 — a W2 row ahead of the skipped row does not count as skipped.
    Rules: `get_by_component` R2, R6"""
    a = mk_event(created_at=T1)
    mk_event(created_at=T2)
    mk_event(created_at=T3, workspace_id=w2.id)

    result = dao.get_by_component(db, project_component_id=cp1.id, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [a.id]


# [claude] PCE-G-17
def test_pce_g_17__with_the_default_limit_101_rows_give_the_newest_100(db, w1, cp1, mk_log):
    """PCE-G-17 — with the default limit 101 rows give the newest 100.
    Rules: `get_by_component` R6"""
    newest_first = mk_log(101)

    result = dao.get_by_component(db, project_component_id=cp1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert ids(result) == newest_first[:100]


# [claude] PCE-G-18
def test_pce_g_18__limit_1000_returns_all_101_rows(db, w1, cp1, mk_log):
    """PCE-G-18 — limit=1000 returns all 101 rows.
    Rules: `get_by_component` R6"""
    newest_first = mk_log(101)

    result = dao.get_by_component(db, project_component_id=cp1.id, workspace_id=w1.id, limit=1000)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert ids(result) == newest_first


# [claude] PCE-G-19
def test_pce_g_19__the_first_window_holds_the_two_newest_rows_sorted_before_paging(db, w1, cp1, mk_event):
    """PCE-G-19 — the first window holds the two newest rows, sorted before paging.
    Rules: `get_by_component` R6, R5"""
    mk_event(created_at=T2)
    b = mk_event(created_at=T3)
    mk_event(created_at=T1)
    d = mk_event(created_at=T3)

    result = dao.get_by_component(db, project_component_id=cp1.id, workspace_id=w1.id, skip=0, limit=2)

    # Then 1
    assert ids(result) == [d.id, b.id]


# [claude] PCE-G-20
def test_pce_g_20__the_next_window_holds_the_two_other_rows_no_repeat_no_gap(db, w1, cp1, mk_event):
    """PCE-G-20 — the next window holds the two other rows: no repeat, no gap.
    Rules: `get_by_component` R6, R5"""
    a = mk_event(created_at=T2)
    mk_event(created_at=T3)
    c = mk_event(created_at=T1)
    mk_event(created_at=T3)

    result = dao.get_by_component(db, project_component_id=cp1.id, workspace_id=w1.id, skip=2, limit=2)

    # Then 1
    assert ids(result) == [a.id, c.id]


# [claude] PCE-G-21
def test_pce_g_21__limit_0_returns_an_empty_list(db, w1, cp1, mk_event):
    """PCE-G-21 — limit=0 returns an empty list.
    Rules: `get_by_component` R7"""
    mk_event(created_at=T1)
    mk_event(created_at=T2)

    result = dao.get_by_component(db, project_component_id=cp1.id, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [claude] PCE-G-22
def test_pce_g_22__limit_1_returns_the_newest_row(db, w1, cp1, mk_event):
    """PCE-G-22 — limit=1 returns the newest row.
    Rules: `get_by_component` R7, R6"""
    mk_event(created_at=T1)
    b = mk_event(created_at=T2)

    result = dao.get_by_component(db, project_component_id=cp1.id, workspace_id=w1.id, limit=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] PCE-G-23
def test_pce_g_23__skip_equal_to_the_number_of_rows_returns_an_empty_list(db, w1, cp1, mk_event):
    """PCE-G-23 — skip equal to the number of rows returns an empty list.
    Rules: `get_by_component` R7"""
    mk_event(created_at=T1)
    mk_event(created_at=T2)

    result = dao.get_by_component(db, project_component_id=cp1.id, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [claude] PCE-G-24
def test_pce_g_24__skip_past_the_number_of_rows_returns_an_empty_list(db, w1, cp1, mk_event):
    """PCE-G-24 — skip past the number of rows returns an empty list.
    Rules: `get_by_component` R7"""
    mk_event(created_at=T1)
    mk_event(created_at=T2)

    result = dao.get_by_component(db, project_component_id=cp1.id, workspace_id=w1.id, skip=3)

    # Then 1
    assert result == []


# [claude] PCE-G-25
def test_pce_g_25__skip_one_below_the_number_of_rows_returns_the_oldest_row(db, w1, cp1, mk_event):
    """PCE-G-25 — skip one below the number of rows returns the oldest row.
    Rules: `get_by_component` R7, R6"""
    a = mk_event(created_at=T1)
    mk_event(created_at=T2)

    result = dao.get_by_component(db, project_component_id=cp1.id, workspace_id=w1.id, skip=1)

    # Then 1
    assert ids(result) == [a.id]


# [claude] PCE-G-26
def test_pce_g_26__a_negative_limit_is_rejected_by_postgres(db, w1, cp1, mk_event):
    """PCE-G-26 — a negative limit is rejected by Postgres.
    Rules: `get_by_component` R8, Errors row 1"""
    mk_event(created_at=T1)
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_component(db, project_component_id=cp1.id, workspace_id=w1.id, limit=-1)
    # Then 2
    assert exc.value.orig.pgcode == "2201W"
    # Then 3
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 4
    assert stored_count(db) == before


# [claude] PCE-G-27
def test_pce_g_27__a_negative_skip_is_rejected_by_postgres(db, w1, cp1, mk_event):
    """PCE-G-27 — a negative skip is rejected by Postgres.
    Rules: `get_by_component` R8, Errors row 2"""
    mk_event(created_at=T1)
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_component(db, project_component_id=cp1.id, workspace_id=w1.id, skip=-1)
    # Then 2
    assert exc.value.orig.pgcode == "2201X"
    # Then 3
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 4
    assert stored_count(db) == before


# [claude] PCE-G-28
def test_pce_g_28__a_row_comes_back_as_stored_with_its_performer(db, w1, u1, cp1, mk_event):
    """PCE-G-28 — a row comes back as stored, with its performer.
    Rules: `get_by_component` R9"""
    a = mk_event(created_at=T2, event_type="work_order_item_used", description="Step done", metadata_json={"status": "DONE", "note": "Shift 1"}, performed_by=u1.id)

    result = dao.get_by_component(db, project_component_id=cp1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert result[0].workspace_id == w1.id
    assert result[0].project_component_id == cp1.id
    assert result[0].event_type == "work_order_item_used"
    # Then 3
    assert result[0].description == "Step done"
    assert result[0].created_at == T2
    # Then 4
    assert result[0].metadata_json == {"status": "DONE", "note": "Shift 1"}
    # Then 5
    assert result[0].performer.id == u1.id


# [claude] PCE-G-29
def test_pce_g_29__sql_null_and_json_null_metadata_both_read_back_as_none_and_no_performer(db, w1, cp1, mk_event):
    """PCE-G-29 — SQL NULL and JSON null metadata both read back as None, and no performer gives None.
    Rules: `get_by_component` R9"""
    a = mk_event(created_at=T1)
    b = mk_event(created_at=T2, metadata_json=None)

    result = dao.get_by_component(db, project_component_id=cp1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [b.id, a.id]
    # Then 2
    assert result[0].metadata_json is None
    # Then 3
    assert result[1].metadata_json is None
    # Then 4
    db.expire_all()
    assert stored_json(db, a) is None
    # Then 5
    db.expire_all()
    assert stored_json(db, b) == "null"
    # Then 6
    assert result[0].performer is None


# [claude] PCE-G-30
def test_pce_g_30__writes_nothing_a_newer_pending_row_stays_pending_and_is_not_returned(db, w1, cp1, mk_event):
    """PCE-G-30 — writes nothing: a newer pending row stays pending and is not returned.
    Rules: `get_by_component` R9, Side effects, Overview, R1, Branch map"""
    a = mk_event(created_at=T1)
    p = ProjectComponentActivityEvent(workspace_id=w1.id, project_component_id=cp1.id, event_type="attachment_added", description="Pending", created_at=T2)
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_component(db, project_component_id=cp1.id, workspace_id=w1.id)
    written = recorder.written()
    sql = recorder.sql()

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert p in db.new
    # Then 3
    assert p.id is None
    # Then 4
    assert stored_count(db) == before
    # Then 5
    assert len(db.new) == 1
    # Then 6
    assert not db.dirty and not db.deleted
    # Then 7
    db.expire_all()
    assert snap(db, a) == before_a
    # Then 8
    assert written == []
    # Then 9
    assert "FOR" not in sql.upper().split()
    # Then 10
    assert "project_components" not in sql


# [claude] PCE-G-31
def test_pce_g_31__on_a_created_at_tie_id_decides_not_event_type_description_or_performer(db, w1, u1, cp1, mk_event):
    """PCE-G-31 — on a created_at tie id decides, not event_type, description or performer.
    Rules: `get_by_component` R5"""
    u2 = make_profile(db)
    u3 = make_profile(db)
    a = mk_event(created_at=T2, event_type="b", description="b", performed_by=u2.id)
    b = mk_event(created_at=T2, event_type="a", description="a", performed_by=u1.id)
    c = mk_event(created_at=T2, event_type="c", description="c", performed_by=u3.id)
    db.expire_all()

    result = dao.get_by_component(db, project_component_id=cp1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [c.id, b.id, a.id]


# [claude] PCE-G-32
def test_pce_g_32__one_microsecond_inside_one_day_decides_the_order_against_id(db, w1, cp1, mk_event):
    """PCE-G-32 — one microsecond inside one day decides the order, against id.
    Rules: `get_by_component` R5"""
    a = mk_event(created_at=T2 + timedelta(microseconds=1))
    b = mk_event(created_at=T2)

    result = dao.get_by_component(db, project_component_id=cp1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id, b.id]


# [claude] PCE-G-33
def test_pce_g_33__writes_nothing_with_an_empty_result_the_pending_row_is_still_alone_in_t(db, w1, cp1, cp2, mk_event):
    """PCE-G-33 — writes nothing: with an empty result the pending row is still alone in the session.
    Rules: `get_by_component` R9, Side effects"""
    mk_event(created_at=T1)
    p = ProjectComponentActivityEvent(workspace_id=w1.id, project_component_id=cp1.id, event_type="attachment_added", description="Pending", created_at=T2)
    db.add(p)

    result = dao.get_by_component(db, project_component_id=cp2.id, workspace_id=w1.id)

    # Then 1
    assert result == []
    # Then 2
    assert len(db.new) == 1
