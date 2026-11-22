"""Unit tests for app/dao/machine_activity_event.py.

Implements tests/unit/dao/machine_activity_event.cases.md, one test per case, in
card order. Real Postgres session (`db` fixture). Nothing is mocked and no clock
is patched (Conventions, Externals: None).

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117, DTZ001  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`, and naive datetimes)
from datetime import date, datetime, timedelta

import pytest
from psycopg2.errors import (
    InvalidRowCountInLimitClause,
    InvalidRowCountInResultOffsetClause,
)
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import DataError

from app.dao.machine_activity_event import machine_activity_event_dao
from app.models.factory import Factory
from app.models.machine import Machine
from app.models.machine_activity_event import MachineActivityEvent
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton machine_activity_event_dao" (a module-level name, not a fixture)
dao = machine_activity_event_dao

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


def _factory(db, workspace, name, abbreviation, **columns):
    fields = {"workspace_id": workspace.id, "name": name, "abbreviation": abbreviation,
              "is_active": True, "is_deleted": False}
    fields.update(columns)
    return _add(db, Factory(**fields))


def _machine(db, workspace, factory, name, **columns):
    fields = {"workspace_id": workspace.id, "factory_id": factory.id, "name": name,
              "is_active": True, "is_deleted": False}
    fields.update(columns)
    return _add(db, Machine(**fields))


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
    return _factory(db, w1, "Factory One", "F1")


# Convention "FD": soft-deleted; is_active stays True
@pytest.fixture
def fd(db, w1):
    return _factory(db, w1, "Old Plant", "OP", is_deleted=True)


# Convention "F9"
@pytest.fixture
def f9(db, w2):
    return _factory(db, w2, "Factory Nine", "F9")


# Convention "M1, M2"
@pytest.fixture
def m1(db, w1, f1):
    return _machine(db, w1, f1, "Press 1")


@pytest.fixture
def m2(db, w1, f1):
    return _machine(db, w1, f1, "Press 2")


# Convention "MD": soft-deleted
@pytest.fixture
def md(db, w1, f1):
    return _machine(db, w1, f1, "Press 4", is_active=False, is_deleted=True)


# Convention "MF": live, in a soft-deleted factory
@pytest.fixture
def mf(db, w1, fd):
    return _machine(db, w1, fd, "Lost Press")


# Convention "M9"
@pytest.fixture
def m9(db, w2, f9):
    return _machine(db, w2, f9, "Far Press")


# Convention "These rows exist in every test and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2, u1, f1, fd, f9, m1, m2, md, mf, m9):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builders (fixtures; each flushes before it returns)
# --------------------------------------------------------------------------- #

# Convention "event": W1, M1, item_added, "Logged"; metadata_json and performed_by not passed
@pytest.fixture
def mk_event(db, w1, m1):
    """mk_event(created_at=..., **columns) -> MachineActivityEvent. Keywords only."""
    def _mk(*, created_at, **columns):
        fields = {"workspace_id": w1.id, "machine_id": m1.id, "event_type": "item_added",
                  "description": "Logged", "created_at": created_at}
        fields.update(columns)
        return _add(db, MachineActivityEvent(**fields))
    return _mk


# Convention "status row": an event, but event_type status_updated, metadata {"status": "RUNNING"}
@pytest.fixture
def mk_status(mk_event):
    """mk_status(created_at=..., **columns) -> MachineActivityEvent. Keywords only."""
    def _mk(*, created_at, **columns):
        fields = {"event_type": "status_updated", "metadata_json": {"status": "RUNNING"}}
        fields.update(columns)
        return mk_event(created_at=created_at, **fields)
    return _mk


# The "101 events E1 ... E101, built with add_all" Given of MAE-GM-14 and MAE-GM-15
@pytest.fixture
def mk_log(db, w1, m1):
    """mk_log(count) -> `newest_first`: the ids of Ecount ... E1, Ek at T1 + k minutes."""
    def _mk(count):
        rows = [MachineActivityEvent(workspace_id=w1.id, machine_id=m1.id, event_type="item_added",
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


# Convention "nothing written": the number of machine_activity_events rows stored (all workspaces)
def stored_count(db):
    return db.execute(select(func.count()).select_from(MachineActivityEvent.__table__)).scalar_one()


# Convention "stored_json(X)": the stored text; None for SQL NULL, "null" for JSON null
def stored_json(db, row):
    return db.scalar(text("SELECT metadata::text FROM machine_activity_events WHERE id = :i"), {"i": row.id})


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
        """The one SELECT from machine_activity_events; fails loudly unless there is exactly one."""
        [statement] = [s for s in self.selects() if "machine_activity_events" in s]
        return statement


# Convention "order_part": the text of `sql` after its first ORDER BY ("" when there is none)
def order_part_of(sql):
    return sql.split("ORDER BY", 1)[1] if "ORDER BY" in sql else ""


# --------------------------------------------------------------------------- #
# MachineActivityEventDAO.get_by_machine
# --------------------------------------------------------------------------- #


# [claude] MAE-GM-01
def test_mae_gm_01__returns_a_list_of_the_machine_s_rows_of_every_event_type(db, w1, m1, mk_event, mk_status):
    """MAE-GM-01 — returns a list of the machine's rows of every event type.
    Rules: `get_by_machine` R1, Returns"""
    a = mk_event(created_at=T1, event_type="created")
    b = mk_status(created_at=T2)
    c = mk_event(created_at=T3, event_type="deactivated")

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [c.id, b.id, a.id]
    # Then 3
    assert isinstance(result[0], MachineActivityEvent)


# [claude] MAE-GM-02
def test_mae_gm_02__a_newer_row_of_another_machine_is_not_returned_and_takes_no_place_in_t(db, w1, m1, m2, mk_event):
    """MAE-GM-02 — a newer row of another machine is not returned and takes no place in the page.
    Rules: `get_by_machine` R1"""
    a = mk_event(created_at=T1)
    mk_event(created_at=T2, machine_id=m2.id)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, limit=1)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MAE-GM-03
def test_mae_gm_03__the_right_machine_under_another_workspace_returns_an_empty_list(db, w2, m1, mk_event):
    """MAE-GM-03 — the right machine under another workspace returns an empty list.
    Rules: `get_by_machine` R2"""
    mk_event(created_at=T1)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] MAE-GM-04
def test_mae_gm_04__a_newer_w2_row_on_the_same_machine_is_not_returned_and_takes_no_place(db, w1, w2, m1, mk_event):
    """MAE-GM-04 — a newer W2 row on the same machine is not returned and takes no place in the page.
    Rules: `get_by_machine` R2"""
    a = mk_event(created_at=T1)
    mk_event(created_at=T2, workspace_id=w2.id)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, limit=1)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MAE-GM-05
def test_mae_gm_05__a_w1_row_on_a_machine_of_w2_is_returned_for_w1_only_the_row_s_workspac(db, w1, m9, mk_event):
    """MAE-GM-05 — a W1 row on a machine of W2 is returned for W1: only the row's workspace is compared.
    Rules: `get_by_machine` R2"""
    a = mk_event(created_at=T1, machine_id=m9.id)

    result = dao.get_by_machine(db, machine_id=m9.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MAE-GM-06
def test_mae_gm_06__a_w1_row_on_a_machine_of_w2_is_not_returned_for_w2(db, w2, m9, mk_event):
    """MAE-GM-06 — a W1 row on a machine of W2 is not returned for W2.
    Rules: `get_by_machine` R2"""
    mk_event(created_at=T1, machine_id=m9.id)

    result = dao.get_by_machine(db, machine_id=m9.id, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] MAE-GM-07
def test_mae_gm_07__an_unknown_machine_id_returns_an_empty_list(db, w1, mk_event):
    """MAE-GM-07 — an unknown machine id returns an empty list.
    Rules: `get_by_machine` R3"""
    mk_event(created_at=T1)

    result = dao.get_by_machine(db, machine_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] MAE-GM-08
def test_mae_gm_08__machine_id_0_returns_an_empty_list(db, w1, mk_event):
    """MAE-GM-08 — machine_id=0 returns an empty list.
    Rules: `get_by_machine` R3"""
    mk_event(created_at=T1)

    result = dao.get_by_machine(db, machine_id=0, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] MAE-GM-09
def test_mae_gm_09__an_unknown_workspace_returns_an_empty_list(db, m1, mk_event):
    """MAE-GM-09 — an unknown workspace returns an empty list.
    Rules: `get_by_machine` R3"""
    mk_event(created_at=T1)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=MISSING)

    # Then 1
    assert result == []


# [claude] MAE-GM-10
def test_mae_gm_10__a_machine_with_no_events_returns_an_empty_list(db, w1, m2, mk_event):
    """MAE-GM-10 — a machine with no events returns an empty list.
    Rules: `get_by_machine` R3"""
    mk_event(created_at=T1)

    result = dao.get_by_machine(db, machine_id=m2.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] MAE-GM-11
def test_mae_gm_11__every_event_of_a_soft_deleted_machine_is_returned(db, w1, md, mk_event):
    """MAE-GM-11 — every event of a soft-deleted machine is returned.
    Rules: `get_by_machine` R4"""
    a = mk_event(created_at=T1, machine_id=md.id, event_type="created")
    b = mk_event(created_at=T2, machine_id=md.id, event_type="deactivated")

    result = dao.get_by_machine(db, machine_id=md.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] MAE-GM-12
def test_mae_gm_12__every_event_of_a_live_machine_in_a_soft_deleted_factory_is_returned(db, w1, mf, mk_event):
    """MAE-GM-12 — every event of a live machine in a soft-deleted factory is returned.
    Rules: `get_by_machine` R4"""
    a = mk_event(created_at=T1, machine_id=mf.id, event_type="created")
    b = mk_event(created_at=T2, machine_id=mf.id, event_type="item_added")

    result = dao.get_by_machine(db, machine_id=mf.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] MAE-GM-13
def test_mae_gm_13__rows_are_ordered_by_created_at_descending_then_id_descending(db, w1, m1, mk_event):
    """MAE-GM-13 — rows are ordered by created_at descending, then id descending.
    Rules: `get_by_machine` R5"""
    a = mk_event(created_at=T2)
    b = mk_event(created_at=T3)
    c = mk_event(created_at=T1)
    d = mk_event(created_at=T3)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [d.id, b.id, a.id, c.id]


# [claude] MAE-GM-14
def test_mae_gm_14__with_the_default_limit_101_rows_give_the_newest_100(db, w1, m1, mk_log):
    """MAE-GM-14 — with the default limit 101 rows give the newest 100.
    Rules: `get_by_machine` R6"""
    newest_first = mk_log(101)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert ids(result) == newest_first[:100]


# [claude] MAE-GM-15
def test_mae_gm_15__limit_1000_returns_all_101_rows(db, w1, m1, mk_log):
    """MAE-GM-15 — limit=1000 returns all 101 rows.
    Rules: `get_by_machine` R6"""
    newest_first = mk_log(101)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, limit=1000)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert ids(result) == newest_first


# [claude] MAE-GM-16
def test_mae_gm_16__the_first_window_holds_the_two_newest_rows_sorted_before_paging(db, w1, m1, mk_event):
    """MAE-GM-16 — the first window holds the two newest rows, sorted before paging.
    Rules: `get_by_machine` R6, R5"""
    mk_event(created_at=T2)
    b = mk_event(created_at=T3)
    mk_event(created_at=T1)
    d = mk_event(created_at=T3)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, skip=0, limit=2)

    # Then 1
    assert ids(result) == [d.id, b.id]


# [claude] MAE-GM-17
def test_mae_gm_17__the_next_window_holds_the_two_other_rows_no_repeat_no_gap(db, w1, m1, mk_event):
    """MAE-GM-17 — the next window holds the two other rows: no repeat, no gap.
    Rules: `get_by_machine` R6, R5"""
    a = mk_event(created_at=T2)
    mk_event(created_at=T3)
    c = mk_event(created_at=T1)
    mk_event(created_at=T3)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, skip=2, limit=2)

    # Then 1
    assert ids(result) == [a.id, c.id]


# [claude] MAE-GM-18
def test_mae_gm_18__limit_0_returns_an_empty_list(db, w1, m1, mk_event):
    """MAE-GM-18 — limit=0 returns an empty list.
    Rules: `get_by_machine` R7"""
    mk_event(created_at=T1)
    mk_event(created_at=T2)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [claude] MAE-GM-19
def test_mae_gm_19__limit_1_returns_the_newest_row(db, w1, m1, mk_event):
    """MAE-GM-19 — limit=1 returns the newest row.
    Rules: `get_by_machine` R7, R6"""
    mk_event(created_at=T1)
    b = mk_event(created_at=T2)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, limit=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] MAE-GM-20
def test_mae_gm_20__skip_equal_to_the_number_of_rows_returns_an_empty_list(db, w1, m1, mk_event):
    """MAE-GM-20 — skip equal to the number of rows returns an empty list.
    Rules: `get_by_machine` R7"""
    mk_event(created_at=T1)
    mk_event(created_at=T2)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [claude] MAE-GM-21
def test_mae_gm_21__skip_past_the_number_of_rows_returns_an_empty_list(db, w1, m1, mk_event):
    """MAE-GM-21 — skip past the number of rows returns an empty list.
    Rules: `get_by_machine` R7"""
    mk_event(created_at=T1)
    mk_event(created_at=T2)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, skip=3)

    # Then 1
    assert result == []


# [claude] MAE-GM-22
def test_mae_gm_22__skip_one_below_the_number_of_rows_returns_the_oldest_row(db, w1, m1, mk_event):
    """MAE-GM-22 — skip one below the number of rows returns the oldest row.
    Rules: `get_by_machine` R7, R6"""
    a = mk_event(created_at=T1)
    mk_event(created_at=T2)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, skip=1)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MAE-GM-23
def test_mae_gm_23__a_negative_limit_is_rejected_by_postgres(db, w1, m1, mk_event):
    """MAE-GM-23 — a negative limit is rejected by Postgres.
    Rules: `get_by_machine` R8, Errors row 1"""
    mk_event(created_at=T1)
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, limit=-1)
    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInLimitClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201W"
    # Then 4
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 5
    assert stored_count(db) == before


# [claude] MAE-GM-24
def test_mae_gm_24__a_negative_skip_is_rejected_by_postgres(db, w1, m1, mk_event):
    """MAE-GM-24 — a negative skip is rejected by Postgres.
    Rules: `get_by_machine` R8, Errors row 2"""
    mk_event(created_at=T1)
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, skip=-1)
    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201X"
    # Then 4
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 5
    assert stored_count(db) == before


# [claude] MAE-GM-25
def test_mae_gm_25__from_date_keeps_the_first_microsecond_of_the_day_not_the_last_of_the_d(db, w1, m1, mk_event):
    """MAE-GM-25 — from_date keeps the first microsecond of the day, not the last of the day before.
    Rules: `get_by_machine` R9"""
    mk_event(created_at=datetime(2026, 3, 4, 23, 59, 59, 999999))
    b = mk_event(created_at=datetime(2026, 3, 5, 0, 0, 0))

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, from_date=date(2026, 3, 5))

    # Then 1
    assert ids(result) == [b.id]


# [claude] MAE-GM-26
def test_mae_gm_26__to_date_keeps_the_last_microsecond_of_the_day_not_the_first_of_the_nex(db, w1, m1, mk_event):
    """MAE-GM-26 — to_date keeps the last microsecond of the day, not the first of the next day.
    Rules: `get_by_machine` R10"""
    a = mk_event(created_at=datetime(2026, 3, 5, 23, 59, 59, 999999))
    mk_event(created_at=datetime(2026, 3, 6, 0, 0, 0))

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, to_date=date(2026, 3, 5))

    # Then 1
    assert ids(result) == [a.id]


# [claude] MAE-GM-27
def test_mae_gm_27__both_dates_keep_the_inclusive_range(db, w1, m1, mk_event):
    """MAE-GM-27 — both dates keep the inclusive range.
    Rules: `get_by_machine` R11"""
    mk_event(created_at=datetime(2026, 3, 3, 23, 59, 59, 999999))
    b = mk_event(created_at=datetime(2026, 3, 4, 0, 0, 0))
    c = mk_event(created_at=datetime(2026, 3, 5, 12, 0, 0))
    d = mk_event(created_at=datetime(2026, 3, 6, 23, 59, 59, 999999))
    mk_event(created_at=datetime(2026, 3, 7, 0, 0, 0))

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, from_date=date(2026, 3, 4), to_date=date(2026, 3, 6))

    # Then 1
    assert ids(result) == [d.id, c.id, b.id]


# [claude] MAE-GM-28
def test_mae_gm_28__from_date_equal_to_to_date_covers_that_whole_day(db, w1, m1, mk_event):
    """MAE-GM-28 — from_date equal to to_date covers that whole day.
    Rules: `get_by_machine` R11"""
    mk_event(created_at=datetime(2026, 3, 4, 23, 59, 59, 999999))
    b = mk_event(created_at=datetime(2026, 3, 5, 0, 0, 0))
    c = mk_event(created_at=datetime(2026, 3, 5, 23, 59, 59, 999999))
    mk_event(created_at=datetime(2026, 3, 6, 0, 0, 0))

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, from_date=date(2026, 3, 5), to_date=date(2026, 3, 5))

    # Then 1
    assert ids(result) == [c.id, b.id]


# [claude] MAE-GM-29
def test_mae_gm_29__from_date_after_to_date_returns_an_empty_list_with_no_error(db, w1, m1, mk_event):
    """MAE-GM-29 — from_date after to_date returns an empty list, with no error.
    Rules: `get_by_machine` R11"""
    mk_event(created_at=datetime(2026, 3, 4, 12, 0, 0))
    mk_event(created_at=datetime(2026, 3, 5, 12, 0, 0))
    mk_event(created_at=datetime(2026, 3, 6, 12, 0, 0))

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, from_date=date(2026, 3, 6), to_date=date(2026, 3, 4))

    # Then 1
    assert result == []


# [claude] MAE-GM-30
def test_mae_gm_30__a_day_is_a_utc_day_also_under_a_session_in_another_time_zone(db, w1, m1, mk_event):
    """MAE-GM-30 — a day is a UTC day, also under a session in another time zone.
    Rules: `get_by_machine` R12"""
    db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))
    mk_event(created_at=datetime(2026, 3, 4, 19, 0, 0))
    b = mk_event(created_at=datetime(2026, 3, 5, 19, 0, 0))

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, from_date=date(2026, 3, 5), to_date=date(2026, 3, 5))

    # Then 1
    assert ids(result) == [b.id]


# [claude] MAE-GM-31
def test_mae_gm_31__a_datetime_passed_as_a_date_counts_by_its_date_only(db, w1, m1, mk_event):
    """MAE-GM-31 — a datetime passed as a date counts by its date only.
    Rules: `get_by_machine` Inputs"""
    a = mk_event(created_at=datetime(2026, 3, 5, 0, 0, 0))
    b = mk_event(created_at=datetime(2026, 3, 5, 23, 59, 59, 999999))

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, from_date=datetime(2026, 3, 5, 15, 30, 0), to_date=datetime(2026, 3, 5, 9, 0, 0))

    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] MAE-GM-32
def test_mae_gm_32__event_type_keeps_only_the_rows_of_that_type(db, w1, m1, mk_event, mk_status):
    """MAE-GM-32 — event_type keeps only the rows of that type.
    Rules: `get_by_machine` R13"""
    a = mk_event(created_at=T1)
    mk_status(created_at=T2)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, event_type="item_added")

    # Then 1
    assert ids(result) == [a.id]


# [claude] MAE-GM-33
def test_mae_gm_33__event_type_another_case_does_not_match(db, w1, m1, mk_event):
    """MAE-GM-33 — event_type: another case does not match.
    Rules: `get_by_machine` R13"""
    mk_event(created_at=T1)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, event_type="ITEM_ADDED")

    # Then 1
    assert result == []


# [claude] MAE-GM-34
def test_mae_gm_34__event_type_trailing_space_does_not_match(db, w1, m1, mk_event):
    """MAE-GM-34 — event_type: trailing space does not match.
    Rules: `get_by_machine` R13"""
    mk_event(created_at=T1)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, event_type="item_added ")

    # Then 1
    assert result == []


# [claude] MAE-GM-35
def test_mae_gm_35__event_type_a_single_space_is_a_filter_and_matches_nothing(db, w1, m1, mk_event):
    """MAE-GM-35 — event_type: a single space is a filter and matches nothing.
    Rules: `get_by_machine` R13"""
    mk_event(created_at=T1)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, event_type=" ")

    # Then 1
    assert result == []


# [claude] MAE-GM-36
def test_mae_gm_36__event_type_a_wildcard_does_not_match(db, w1, m1, mk_event):
    """MAE-GM-36 — event_type: a wildcard does not match.
    Rules: `get_by_machine` R13"""
    mk_event(created_at=T1)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, event_type="item%")

    # Then 1
    assert result == []


# [claude] MAE-GM-37
def test_mae_gm_37__event_type_an_unknown_type_matches_nothing(db, w1, m1, mk_event):
    """MAE-GM-37 — event_type: an unknown type matches nothing.
    Rules: `get_by_machine` R13"""
    mk_event(created_at=T1)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, event_type="scrapped")

    # Then 1
    assert result == []


# [claude] MAE-GM-38
def test_mae_gm_38__event_type_none_applies_no_filter(db, w1, m1, mk_event, mk_status):
    """MAE-GM-38 — event_type=None applies no filter.
    Rules: `get_by_machine` R14"""
    a = mk_event(created_at=T1)
    b = mk_status(created_at=T2)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, event_type=None)

    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] MAE-GM-39
def test_mae_gm_39__an_empty_event_type_applies_no_filter(db, w1, m1, mk_event, mk_status):
    """MAE-GM-39 — an empty event_type applies no filter.
    Rules: `get_by_machine` R14"""
    a = mk_event(created_at=T1)
    b = mk_status(created_at=T2)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, event_type="")

    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] MAE-GM-40
def test_mae_gm_40__the_type_filter_applies_before_limit(db, w1, m1, mk_event, mk_status):
    """MAE-GM-40 — the type filter applies before limit.
    Rules: `get_by_machine` R15"""
    a = mk_status(created_at=T1)
    mk_event(created_at=T2)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, event_type="status_updated", limit=1)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MAE-GM-41
def test_mae_gm_41__all_filters_combine_and_apply_before_skip_and_limit(db, w1, w2, m1, m2, mk_event, mk_status):
    """MAE-GM-41 — all filters combine and apply before skip and limit.
    Rules: `get_by_machine` R15"""
    a = mk_status(created_at=T1)
    mk_status(created_at=T2)
    mk_status(created_at=T2, machine_id=m2.id)
    mk_status(created_at=T2, workspace_id=w2.id)
    mk_event(created_at=T2)
    mk_status(created_at=T3)
    mk_status(created_at=datetime(2026, 3, 3, 10, 0, 0))

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, from_date=date(2026, 3, 4), to_date=date(2026, 3, 5), event_type="status_updated", skip=1, limit=2)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MAE-GM-42
def test_mae_gm_42__a_row_comes_back_as_stored_with_its_performer(db, w1, u1, m1, mk_status):
    """MAE-GM-42 — a row comes back as stored, with its performer.
    Rules: `get_by_machine` R16"""
    a = mk_status(created_at=T2, description="Press started", metadata_json={"status": "RUNNING", "note": "Shift 1"}, performed_by=u1.id)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert result[0].workspace_id == w1.id
    assert result[0].machine_id == m1.id
    assert result[0].event_type == "status_updated"
    # Then 3
    assert result[0].description == "Press started"
    assert result[0].created_at == T2
    # Then 4
    assert result[0].metadata_json == {"status": "RUNNING", "note": "Shift 1"}
    # Then 5
    assert result[0].performer.id == u1.id


# [claude] MAE-GM-43
def test_mae_gm_43__sql_null_and_json_null_metadata_both_read_back_as_none_and_no_performe(db, w1, m1, mk_event):
    """MAE-GM-43 — SQL NULL and JSON null metadata both read back as None, and no performer gives None.
    Rules: `get_by_machine` R16"""
    a = mk_event(created_at=T1)
    b = mk_event(created_at=T2, metadata_json=None)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

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


# [claude] MAE-GM-44
def test_mae_gm_44__writes_nothing_a_pending_row_stays_pending_and_is_not_returned(db, w1, m1, mk_event):
    """MAE-GM-44 — writes nothing: a pending row stays pending and is not returned.
    Rules: `get_by_machine` R16, Side effects, Overview"""
    a = mk_event(created_at=T1)
    p = MachineActivityEvent(workspace_id=w1.id, machine_id=m1.id, event_type="item_added", description="Pending", created_at=T2)
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id)
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
    db.expire_all()
    assert snap(db, a) == before_a
    # Then 6
    assert written == []
    # Then 7
    assert "FOR UPDATE" not in sql.upper()


# [claude] MAE-GM-45
def test_mae_gm_45__event_type_a_stored_type_that_ends_with_the_filter_does_not_match(db, w1, m1, mk_event, mk_status):
    """MAE-GM-45 — event_type: a stored type that ends with the filter does not match.
    Rules: `get_by_machine` R13"""
    a = mk_event(created_at=T1, event_type="updated")
    mk_status(created_at=T2)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, event_type="updated")

    # Then 1
    assert ids(result) == [a.id]


# [claude] MAE-GM-46
def test_mae_gm_46__event_type_a_stored_type_that_starts_with_the_filter_does_not_match(db, w1, m1, mk_event):
    """MAE-GM-46 — event_type: a stored type that starts with the filter does not match.
    Rules: `get_by_machine` R13"""
    mk_event(created_at=T1)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, event_type="item")

    # Then 1
    assert result == []


# --------------------------------------------------------------------------- #
# MachineActivityEventDAO.get_latest_status_by_machine
# --------------------------------------------------------------------------- #


# [claude] MAE-LS-01
def test_mae_ls_01__returns_the_status_row_with_the_newest_created_at_whatever_its_id(db, w1, m1, mk_status):
    """MAE-LS-01 — returns the status row with the newest created_at, whatever its id.
    Rules: `get_latest_status_by_machine` R1, Returns"""
    mk_status(created_at=T2)
    b = mk_status(created_at=T3)
    mk_status(created_at=T1)

    result = dao.get_latest_status_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == b.id
    # Then 2
    assert isinstance(result, MachineActivityEvent)


# [claude] MAE-LS-02
def test_mae_ls_02__a_newer_status_row_of_another_machine_is_not_returned(db, w1, m1, m2, mk_status):
    """MAE-LS-02 — a newer status row of another machine is not returned.
    Rules: `get_latest_status_by_machine` R1"""
    a = mk_status(created_at=T1)
    mk_status(created_at=T2, machine_id=m2.id)

    result = dao.get_latest_status_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id


# [claude] MAE-LS-03
def test_mae_ls_03__on_a_created_at_tie_the_highest_id_is_returned(db, w1, m1, mk_status):
    """MAE-LS-03 — on a created_at tie the highest id is returned.
    Rules: `get_latest_status_by_machine` R2"""
    a = mk_status(created_at=T2)
    b = mk_status(created_at=T2)
    a.description = "Edited"
    db.flush()
    db.expire_all()

    result = dao.get_latest_status_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == b.id


# [claude] MAE-LS-04
def test_mae_ls_04__newer_rows_of_other_types_are_ignored_even_with_a_status_key(db, w1, m1, mk_event, mk_status):
    """MAE-LS-04 — newer rows of other types are ignored, even with a status key.
    Rules: `get_latest_status_by_machine` R3"""
    a = mk_status(created_at=T1)
    mk_event(created_at=T2)
    mk_event(created_at=T3, event_type="updated", metadata_json={"status": "OFF"})
    mk_event(created_at=T3, event_type="STATUS_UPDATED", metadata_json={"status": "OFF"})

    result = dao.get_latest_status_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id


# [claude] MAE-LS-05
def test_mae_ls_05__a_machine_with_only_rows_of_other_types_returns_none_and_nothing_is_cr(db, w1, m1, mk_event):
    """MAE-LS-05 — a machine with only rows of other types returns None and nothing is created.
    Rules: `get_latest_status_by_machine` R4"""
    mk_event(created_at=T1, metadata_json={"status": "OFF"})
    before = stored_count(db)

    result = dao.get_latest_status_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    assert stored_count(db) == before


# [claude] MAE-LS-06
def test_mae_ls_06__an_unknown_machine_id_returns_none(db, w1, mk_status):
    """MAE-LS-06 — an unknown machine id returns None.
    Rules: `get_latest_status_by_machine` R4"""
    mk_status(created_at=T1)

    result = dao.get_latest_status_by_machine(db, machine_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] MAE-LS-07
def test_mae_ls_07__machine_id_0_returns_none(db, w1, mk_status):
    """MAE-LS-07 — machine_id=0 returns None.
    Rules: `get_latest_status_by_machine` R4"""
    mk_status(created_at=T1)

    result = dao.get_latest_status_by_machine(db, machine_id=0, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] MAE-LS-08
def test_mae_ls_08__a_newer_status_row_of_another_workspace_on_the_same_machine_is_ignored(db, w1, w2, m1, mk_status):
    """MAE-LS-08 — a newer status row of another workspace on the same machine is ignored.
    Rules: `get_latest_status_by_machine` R5"""
    a = mk_status(created_at=T1)
    mk_status(created_at=T2, workspace_id=w2.id, metadata_json={"status": "OFF"})

    result = dao.get_latest_status_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id


# [claude] MAE-LS-09
def test_mae_ls_09__the_right_machine_under_another_workspace_returns_none(db, w2, m1, mk_status):
    """MAE-LS-09 — the right machine under another workspace returns None.
    Rules: `get_latest_status_by_machine` R5"""
    mk_status(created_at=T1)

    result = dao.get_latest_status_by_machine(db, machine_id=m1.id, workspace_id=w2.id)

    # Then 1
    assert result is None


# [claude] MAE-LS-10
def test_mae_ls_10__a_w1_status_row_on_a_machine_of_w2_is_returned_for_w1_only_the_row_s_w(db, w1, m9, mk_status):
    """MAE-LS-10 — a W1 status row on a machine of W2 is returned for W1: only the row's workspace is compared.
    Rules: `get_latest_status_by_machine` R5"""
    a = mk_status(created_at=T1, machine_id=m9.id)

    result = dao.get_latest_status_by_machine(db, machine_id=m9.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id


# [claude] MAE-LS-11
def test_mae_ls_11__the_status_row_of_a_soft_deleted_machine_is_returned(db, w1, md, mk_status):
    """MAE-LS-11 — the status row of a soft-deleted machine is returned.
    Rules: `get_latest_status_by_machine` R6"""
    a = mk_status(created_at=T1, machine_id=md.id)

    result = dao.get_latest_status_by_machine(db, machine_id=md.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id


# [claude] MAE-LS-12
def test_mae_ls_12__the_status_row_of_a_live_machine_in_a_soft_deleted_factory_is_returned(db, w1, mf, mk_status):
    """MAE-LS-12 — the status row of a live machine in a soft-deleted factory is returned.
    Rules: `get_latest_status_by_machine` R6"""
    a = mk_status(created_at=T1, machine_id=mf.id)

    result = dao.get_latest_status_by_machine(db, machine_id=mf.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id


# [claude] MAE-LS-13
def test_mae_ls_13__a_newest_status_row_with_no_metadata_is_returned_older_rows_are_not_co(db, w1, m1, mk_event, mk_status):
    """MAE-LS-13 — a newest status row with no metadata is returned, older rows are not consulted.
    Rules: `get_latest_status_by_machine` R7"""
    mk_status(created_at=T1)
    b = mk_event(created_at=T2, event_type="status_updated")

    result = dao.get_latest_status_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == b.id


# [claude] MAE-LS-14
def test_mae_ls_14__a_newest_status_row_with_no_status_key_is_returned_older_rows_are_not(db, w1, m1, mk_status):
    """MAE-LS-14 — a newest status row with no status key is returned, older rows are not consulted.
    Rules: `get_latest_status_by_machine` R7"""
    mk_status(created_at=T1)
    b = mk_status(created_at=T2, metadata_json={"note": "Shift 1"})

    result = dao.get_latest_status_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == b.id


# [claude] MAE-LS-15
def test_mae_ls_15__writes_nothing_a_newer_pending_row_stays_pending_and_is_not_returned(db, w1, m1, mk_status):
    """MAE-LS-15 — writes nothing: a newer pending row stays pending and is not returned.
    Rules: `get_latest_status_by_machine` Side effects, Overview"""
    a = mk_status(created_at=T1)
    p = MachineActivityEvent(workspace_id=w1.id, machine_id=m1.id, event_type="status_updated", description="Pending", created_at=T2)
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    with StatementRecorder(db) as recorder:
        result = dao.get_latest_status_by_machine(db, machine_id=m1.id, workspace_id=w1.id)
    written = recorder.written()
    sql = recorder.sql()

    # Then 1
    assert result.id == a.id
    # Then 2
    assert p in db.new
    # Then 3
    assert p.id is None
    # Then 4
    assert stored_count(db) == before
    # Then 5
    db.expire_all()
    assert snap(db, a) == before_a
    # Then 6
    assert written == []
    # Then 7
    assert "FOR UPDATE" not in sql.upper()


# [claude] MAE-LS-16
def test_mae_ls_16__on_a_created_at_tie_with_no_update_the_highest_id_is_returned(db, w1, m1, mk_status):
    """MAE-LS-16 — on a created_at tie with no update the highest id is returned.
    Rules: `get_latest_status_by_machine` R2"""
    mk_status(created_at=T2)
    b = mk_status(created_at=T2)

    result = dao.get_latest_status_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == b.id


# --------------------------------------------------------------------------- #
# MachineActivityEventDAO.get_latest_status_map
# --------------------------------------------------------------------------- #


# [claude] MAE-LM-01
def test_mae_lm_01__an_empty_list_returns_an_empty_dict(db, w1, mk_status):
    """MAE-LM-01 — an empty list returns an empty dict.
    Rules: `get_latest_status_map` R1"""
    mk_status(created_at=T1)

    result = dao.get_latest_status_map(db, workspace_id=w1.id, machine_ids=[])

    # Then 1
    assert result == {}


# [claude] MAE-LM-02
def test_mae_lm_02__none_returns_an_empty_dict(db, w1, mk_status):
    """MAE-LM-02 — None returns an empty dict.
    Rules: `get_latest_status_map` R1"""
    mk_status(created_at=T1)

    result = dao.get_latest_status_map(db, workspace_id=w1.id, machine_ids=None)

    # Then 1
    assert result == {}


# [claude] MAE-LM-03
def test_mae_lm_03__each_machine_asked_for_gets_its_newest_status_row(db, w1, m1, m2, mk_status):
    """MAE-LM-03 — each machine asked for gets its newest status row.
    Rules: `get_latest_status_map` R2, Returns"""
    b = mk_status(created_at=T3)
    mk_status(created_at=T2)
    d = mk_status(created_at=T2, machine_id=m2.id)
    mk_status(created_at=T1, machine_id=m2.id)

    result = dao.get_latest_status_map(db, workspace_id=w1.id, machine_ids=[m1.id, m2.id])

    # Then 1
    assert isinstance(result, dict)
    # Then 2
    assert set(result) == {m1.id, m2.id}
    # Then 3
    assert result[m1.id].id == b.id
    # Then 4
    assert result[m2.id].id == d.id
    # Then 5
    assert isinstance(result[m1.id], MachineActivityEvent)


# [claude] MAE-LM-04
def test_mae_lm_04__no_status_row_an_unknown_id_and_0_give_no_entry(db, w1, m1, m2, mk_event, mk_status):
    """MAE-LM-04 — no status row, an unknown id and 0 give no entry.
    Rules: `get_latest_status_map` R3"""
    a = mk_status(created_at=T1)
    mk_event(created_at=T2, machine_id=m2.id, metadata_json={"status": "OFF"})

    result = dao.get_latest_status_map(db, workspace_id=w1.id, machine_ids=[m1.id, m2.id, MISSING, 0])

    # Then 1
    assert set(result) == {m1.id}
    # Then 2
    assert result[m1.id].id == a.id


# [claude] MAE-LM-05
def test_mae_lm_05__a_machine_not_asked_for_has_no_entry(db, w1, m1, m2, mk_status):
    """MAE-LM-05 — a machine not asked for has no entry.
    Rules: `get_latest_status_map` R3"""
    a = mk_status(created_at=T1)
    mk_status(created_at=T2, machine_id=m2.id)

    result = dao.get_latest_status_map(db, workspace_id=w1.id, machine_ids=[m1.id])

    # Then 1
    assert set(result) == {m1.id}
    # Then 2
    assert result[m1.id].id == a.id


# [claude] MAE-LM-06
def test_mae_lm_06__an_id_listed_twice_gives_one_entry(db, w1, m1, mk_status):
    """MAE-LM-06 — an id listed twice gives one entry.
    Rules: `get_latest_status_map` R3"""
    a = mk_status(created_at=T1)

    result = dao.get_latest_status_map(db, workspace_id=w1.id, machine_ids=[m1.id, m1.id])

    # Then 1
    assert set(result) == {m1.id}
    # Then 2
    assert result[m1.id].id == a.id


# [claude] MAE-LM-07
def test_mae_lm_07__newer_rows_of_other_types_are_ignored_even_with_a_status_key(db, w1, m1, mk_event, mk_status):
    """MAE-LM-07 — newer rows of other types are ignored, even with a status key.
    Rules: `get_latest_status_map` R4"""
    a = mk_status(created_at=T1)
    mk_event(created_at=T2, event_type="updated", metadata_json={"status": "OFF"})

    result = dao.get_latest_status_map(db, workspace_id=w1.id, machine_ids=[m1.id])

    # Then 1
    assert set(result) == {m1.id}
    # Then 2
    assert result[m1.id].id == a.id


# [claude] MAE-LM-08
def test_mae_lm_08__a_later_row_of_another_type_with_the_same_created_at_is_ignored(db, w1, m1, mk_event, mk_status):
    """MAE-LM-08 — a later row of another type with the same created_at is ignored.
    Rules: `get_latest_status_map` R4"""
    a = mk_status(created_at=T1)
    mk_event(created_at=T1, event_type="updated", metadata_json={"status": "OFF"})

    result = dao.get_latest_status_map(db, workspace_id=w1.id, machine_ids=[m1.id])

    # Then 1
    assert set(result) == {m1.id}
    # Then 2
    assert result[m1.id].id == a.id


# [claude] MAE-LM-09
def test_mae_lm_09__a_newer_status_row_of_another_workspace_on_the_same_machine_is_ignored(db, w1, w2, m1, mk_status):
    """MAE-LM-09 — a newer status row of another workspace on the same machine is ignored.
    Rules: `get_latest_status_map` R5"""
    a = mk_status(created_at=T1)
    mk_status(created_at=T2, workspace_id=w2.id, metadata_json={"status": "OFF"})

    result = dao.get_latest_status_map(db, workspace_id=w1.id, machine_ids=[m1.id])

    # Then 1
    assert set(result) == {m1.id}
    # Then 2
    assert result[m1.id].id == a.id


# [claude] MAE-LM-10
def test_mae_lm_10__a_later_status_row_of_another_workspace_with_the_same_created_at_is_ig(db, w1, w2, m1, mk_status):
    """MAE-LM-10 — a later status row of another workspace with the same created_at is ignored.
    Rules: `get_latest_status_map` R5"""
    a = mk_status(created_at=T1)
    mk_status(created_at=T1, workspace_id=w2.id, metadata_json={"status": "OFF"})

    result = dao.get_latest_status_map(db, workspace_id=w1.id, machine_ids=[m1.id])

    # Then 1
    assert set(result) == {m1.id}
    # Then 2
    assert result[m1.id].id == a.id


# [claude] MAE-LM-11
def test_mae_lm_11__the_right_machine_under_another_workspace_gives_no_entry(db, w2, m1, mk_status):
    """MAE-LM-11 — the right machine under another workspace gives no entry.
    Rules: `get_latest_status_map` R5"""
    mk_status(created_at=T1)

    result = dao.get_latest_status_map(db, workspace_id=w2.id, machine_ids=[m1.id])

    # Then 1
    assert result == {}


# [claude] MAE-LM-12
def test_mae_lm_12__a_w1_status_row_on_a_machine_of_w2_is_the_entry_for_w1_only_the_row_s(db, w1, m9, mk_status):
    """MAE-LM-12 — a W1 status row on a machine of W2 is the entry for W1: only the row's workspace is compared.
    Rules: `get_latest_status_map` R5"""
    a = mk_status(created_at=T1, machine_id=m9.id)

    result = dao.get_latest_status_map(db, workspace_id=w1.id, machine_ids=[m9.id])

    # Then 1
    assert set(result) == {m9.id}
    # Then 2
    assert result[m9.id].id == a.id


# [claude] MAE-LM-13
def test_mae_lm_13__on_a_tie_the_machine_gets_one_entry_one_of_the_tied_rows(db, w1, m1, mk_status):
    """MAE-LM-13 — on a tie the machine gets one entry, one of the tied rows.
    Rules: `get_latest_status_map` R6, R2"""
    a = mk_status(created_at=T2)
    b = mk_status(created_at=T2)
    mk_status(created_at=T1)
    a.description = "Edited"
    db.flush()
    db.expire_all()

    result = dao.get_latest_status_map(db, workspace_id=w1.id, machine_ids=[m1.id])

    # Then 1
    assert set(result) == {m1.id}
    # Then 2
    assert result[m1.id].id in {a.id, b.id}


# [claude] MAE-LM-14
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1090: Machine list and machine page can show different statuses on a timestamp tie "
    "(non-strict: the tied rows come back in physical order, which can match by accident)",
)
def test_mae_lm_14__on_a_tie_the_entry_is_the_highest_id_the_row_the_single_lookup_returns(db, w1, m1, mk_status):
    """MAE-LM-14 — on a tie the entry is the highest id, the row the single lookup returns.
    Rules: `get_latest_status_map` R6 [BUG-1090]"""
    a = mk_status(created_at=T2)
    b = mk_status(created_at=T2)
    a.description = "Edited"
    db.flush()
    db.expire_all()
    single = dao.get_latest_status_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    result = dao.get_latest_status_map(db, workspace_id=w1.id, machine_ids=[m1.id])

    # Then 1
    assert set(result) == {m1.id}
    # Then 2
    assert single.id == b.id
    # Then 3
    assert result[m1.id].id == b.id
    # Then 4
    assert result[m1.id].id == single.id


# [claude] MAE-LM-15
@pytest.mark.xfail(strict=True, reason="BUG-1090: Machine list and machine page can show different statuses on a timestamp tie")
def test_mae_lm_15__the_map_s_query_asks_the_database_for_an_order_that_includes_id(db, w1, m1, mk_status):
    """MAE-LM-15 — the map's query asks the database for an order that includes id.
    Rules: `get_latest_status_map` R6 [BUG-1090]"""
    a = mk_status(created_at=T1)

    with StatementRecorder(db) as recorder:
        result = dao.get_latest_status_map(db, workspace_id=w1.id, machine_ids=[m1.id])
    sql = recorder.sql()
    order_part = order_part_of(sql)

    # Then 1
    assert result[m1.id].id == a.id
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert ".id" in order_part


# [claude] MAE-LM-16
def test_mae_lm_16__the_status_rows_of_a_soft_deleted_machine_and_of_a_machine_in_a_soft_d(db, w1, md, mf, mk_status):
    """MAE-LM-16 — the status rows of a soft-deleted machine and of a machine in a soft-deleted factory are the entries.
    Rules: `get_latest_status_map` R7"""
    a = mk_status(created_at=T1, machine_id=md.id)
    b = mk_status(created_at=T1, machine_id=mf.id)

    result = dao.get_latest_status_map(db, workspace_id=w1.id, machine_ids=[md.id, mf.id])

    # Then 1
    assert set(result) == {md.id, mf.id}
    # Then 2
    assert result[md.id].id == a.id
    # Then 3
    assert result[mf.id].id == b.id


# [claude] MAE-LM-17
def test_mae_lm_17__a_newest_status_row_with_no_metadata_is_the_entry(db, w1, m1, mk_event, mk_status):
    """MAE-LM-17 — a newest status row with no metadata is the entry.
    Rules: `get_latest_status_map` R8"""
    mk_status(created_at=T1)
    b = mk_event(created_at=T2, event_type="status_updated")

    result = dao.get_latest_status_map(db, workspace_id=w1.id, machine_ids=[m1.id])

    # Then 1
    assert set(result) == {m1.id}
    # Then 2
    assert result[m1.id].id == b.id


# [claude] MAE-LM-18
def test_mae_lm_18__many_machines_are_answered_in_one_read(db, w1, m1, m2, mk_status):
    """MAE-LM-18 — many machines are answered in one read.
    Rules: `get_latest_status_map` Purpose"""
    mk_status(created_at=T1)
    mk_status(created_at=T1, machine_id=m2.id)

    with StatementRecorder(db) as recorder:
        result = dao.get_latest_status_map(db, workspace_id=w1.id, machine_ids=[m1.id, m2.id])
    selects = recorder.selects()

    # Then 1
    assert set(result) == {m1.id, m2.id}
    # Then 2
    assert len(selects) == 1


# [claude] MAE-LM-19
def test_mae_lm_19__writes_nothing_a_newer_pending_row_stays_pending_and_is_not_the_entry(db, w1, m1, mk_status):
    """MAE-LM-19 — writes nothing: a newer pending row stays pending and is not the entry.
    Rules: `get_latest_status_map` Side effects, Overview"""
    a = mk_status(created_at=T1)
    p = MachineActivityEvent(workspace_id=w1.id, machine_id=m1.id, event_type="status_updated", description="Pending", created_at=T2)
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    with StatementRecorder(db) as recorder:
        result = dao.get_latest_status_map(db, workspace_id=w1.id, machine_ids=[m1.id])
    written = recorder.written()
    sql = recorder.sql()

    # Then 1
    assert result[m1.id].id == a.id
    # Then 2
    assert p in db.new
    # Then 3
    assert p.id is None
    # Then 4
    assert stored_count(db) == before
    # Then 5
    db.expire_all()
    assert snap(db, a) == before_a
    # Then 6
    assert written == []
    # Then 7
    assert "FOR UPDATE" not in sql.upper()
