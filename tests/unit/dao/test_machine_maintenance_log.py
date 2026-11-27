"""Unit tests for app/dao/machine_maintenance_log.py.

Implements tests/unit/dao/machine_maintenance_log.cases.md, one test per case,
in card order. Real Postgres session (`db` fixture). The only patch is the clock
of the Conventions, `app.dao.machine_maintenance_log.utcnow` (autouse fixture
`clock`, `create=True` because the module does not import it today); the commit
spy of the "rolled back" cards wraps the real `db.commit`.

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`)
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from psycopg2.errors import (
    ForeignKeyViolation,
    InvalidRowCountInLimitClause,
    InvalidRowCountInResultOffsetClause,
    InvalidTextRepresentation,
    NotNullViolation,
    NumericValueOutOfRange,
    StringDataRightTruncation,
)
from pydantic import ValidationError
from sqlalchemy import event, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import DataError, IntegrityError

from app.dao.machine_maintenance_log import machine_maintenance_log_dao
from app.models.enums import MaintenanceTypeEnum
from app.models.factory import Factory
from app.models.machine import Machine
from app.models.machine_maintenance_log import MachineMaintenanceLog
from app.schemas.machine_maintenance_log import (
    MachineMaintenanceLogCreate,
    MachineMaintenanceLogUpdate,
)
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton machine_maintenance_log_dao" (a module-level name, not a fixture)
dao = machine_maintenance_log_dao

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999

# Convention "D1 ... D5, T0, NOW"
D1 = date(2026, 3, 1)
D2 = date(2026, 3, 2)
D3 = date(2026, 3, 3)
D4 = date(2026, 3, 4)
D5 = date(2026, 3, 5)
T0 = datetime(2020, 1, 2, 3, 4, 5)  # noqa: DTZ001
NOW = datetime(2031, 5, 6, 7, 8, 9)  # noqa: DTZ001


# Convention "Externals": the clock is patched in every test, a card never patches anything
@pytest.fixture(autouse=True)
def clock():
    with patch("app.dao.machine_maintenance_log.utcnow", create=True, return_value=NOW):
        yield


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


# Convention "P1, P2 = two profiles rows"
@pytest.fixture
def p1(db):
    return make_profile(db)


@pytest.fixture
def p2(db, p1):
    return make_profile(db)


# Convention "F1"
@pytest.fixture
def f1(db, w1):
    return _factory(db, w1, "Factory One", "F1")


# Convention "FD": soft-deleted; is_active stays True
@pytest.fixture
def fd(db, w1):
    return _factory(db, w1, "Old Plant", "OP", is_deleted=True)


# Convention "FI": inactive but live
@pytest.fixture
def fi(db, w1):
    return _factory(db, w1, "Idle Plant", "IP", is_active=False)


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


# Convention "MI": inactive but live
@pytest.fixture
def mi(db, w1, f1):
    return _machine(db, w1, f1, "Idle Press", is_active=False)


# Convention "MF": live, in a soft-deleted factory
@pytest.fixture
def mf(db, w1, fd):
    return _machine(db, w1, fd, "Lost Press")


# Convention "MG": live, in an inactive factory
@pytest.fixture
def mg(db, w1, fi):
    return _machine(db, w1, fi, "Quiet Press")


# Convention "M9"
@pytest.fixture
def m9(db, w2, f9):
    return _machine(db, w2, f9, "Far Press")


# Convention "These rows exist in every test and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2, p1, p2, f1, fd, fi, f9, m1, m2, md, mi, mf, mg, m9):
    return None


# Convention "NEW": the dict the create cards start from
@pytest.fixture
def new(w1, m1):
    return {"workspace_id": w1.id, "machine_id": m1.id, "maintenance_type": MaintenanceTypeEnum.REPAIR,
            "maintenance_date": D1, "summary": "Bearing change"}


# --------------------------------------------------------------------------- #
# Conventions -> row builders (fixtures; each flushes before it returns)
# --------------------------------------------------------------------------- #

# Convention "log", and "gone" after "but": a column named beside gone replaces that value
@pytest.fixture
def mk_log(db, w1, m1, p1):
    """mk_log(gone=False, **columns) -> MachineMaintenanceLog. Keywords only."""
    def _mk(*, gone=False, **columns):
        fields = {"workspace_id": w1.id, "machine_id": m1.id, "maintenance_type": MaintenanceTypeEnum.REPAIR,
                  "maintenance_date": D1, "summary": "Bearing change"}
        if gone:
            fields.update(is_deleted=True, is_active=False, deleted_at=T0, deleted_by=p1.id)
        fields.update(columns)
        return _add(db, MachineMaintenanceLog(**fields))
    return _mk


# The "`rows` = 101 logs built with add_all" Given of the page-size cards
@pytest.fixture
def mk_dated_logs(db, w1, m1):
    """mk_dated_logs(count) -> `count` logs, row k with date(2025, 1, 1) + k days, built with add_all."""
    def _mk(count):
        rows = [MachineMaintenanceLog(workspace_id=w1.id, machine_id=m1.id, maintenance_type=MaintenanceTypeEnum.REPAIR,
                                      maintenance_date=date(2025, 1, 1) + timedelta(days=k), summary="Bearing change")
                for k in range(count)]
        db.add_all(rows)
        db.flush()
        return rows
    return _mk


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (plain functions; no expected values inside)
# --------------------------------------------------------------------------- #

def _id_of(row):
    """Primary key of a row, without touching its (possibly expired) attributes."""
    return sa_inspect(row).identity[0]


# Convention "ids(result)": in the order returned
def ids(result):
    return [row.id for row in result]


# Convention "re-read X": expire_all, then SELECT X by id
def reread(db, row):
    """Fresh copy of the log `row` from the database, or None if it is gone."""
    row_id = _id_of(row)
    db.expire_all()
    return db.execute(select(MachineMaintenanceLog).where(MachineMaintenanceLog.id == row_id)).scalar_one_or_none()


# Convention "unchanged(X)": every column of X (of any table), straight from the table
def snap(db, row):
    """Dict column -> database value of `row`, or None if it is gone."""
    table = type(row).__table__
    found = db.execute(select(table).where(table.c.id == _id_of(row))).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "unchanged(X) except c, ...": the same, leaving out the columns named
def without(snapshot, *columns):
    return {column: value for column, value in snapshot.items() if column not in columns}


# Convention "(raw query)" and "count:" lines: SELECT count(*) through db.scalar(text(...)), with the filter stated
def count_rows(db, where, **params):
    return db.scalar(text(f"SELECT count(*) FROM machine_maintenance_logs WHERE {where}"), params)


# Convention "nothing written": the number of machine_maintenance_logs rows (all workspaces)
def written(db):
    return db.scalar(text("SELECT count(*) FROM machine_maintenance_logs"))


# The "count:" lines on machine_activity_events: the same raw count on that table
def count_activity(db, where, **params):
    return db.scalar(text(f"SELECT count(*) FROM machine_activity_events WHERE {where}"), params)


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


# Convention "order_part": the text of `sql` after `ORDER BY` ("" when there is none)
def order_part_of(sql):
    return sql.split("ORDER BY", 1)[1] if "ORDER BY" in sql else ""


# --------------------------------------------------------------------------- #
# MachineMaintenanceLogDAO.get_by_workspace
# --------------------------------------------------------------------------- #


# [claude] MML-GW-01
def test_mml_gw_01__returns_a_list_of_the_workspace_s_live_logs(db, w1, m2, mk_log):
    """MML-GW-01 — returns a list of the workspace's live logs.
    Rules: `get_by_workspace` R1, Returns"""
    a = mk_log()
    b = mk_log(machine_id=m2.id, maintenance_type=MaintenanceTypeEnum.INSPECTION)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 3
    assert isinstance(result[0], MachineMaintenanceLog)


# [claude] MML-GW-02
def test_mml_gw_02__reading_writes_nothing_and_leaves_a_pending_row_pending(db, w1, m1, m9, mk_log):
    """MML-GW-02 — reading writes nothing and leaves a pending row pending.
    Rules: `get_by_workspace` Side effects"""
    a = mk_log()
    x = mk_log(machine_id=m9.id)
    q = MachineMaintenanceLog(workspace_id=w1.id, machine_id=m1.id, maintenance_type=MaintenanceTypeEnum.REPAIR, maintenance_date=D1, summary="Pending")
    db.add(q)
    before_a = snap(db, a)
    before_x = snap(db, x)
    before = written(db)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert a.id in ids(result)
    # Then 2
    assert q not in result
    # Then 3
    assert q in db.new
    # Then 4
    assert written(db) == before
    # Then 5
    assert count_rows(db, "summary = :summary", summary="Pending") == 0
    # Then 6
    assert snap(db, a) == before_a
    # Then 7
    assert snap(db, x) == before_x
    # Then 8
    assert count_rows(db, "id = :id", id=x.id) == 1


# [claude] MML-GW-03
def test_mml_gw_03__a_log_of_another_workspace_does_not_appear_although_it_would_fit_on_the(db, w1, w2, m9, mk_log):
    """MML-GW-03 — a log of another workspace does not appear, although it would fit on the page.
    Rules: `get_by_workspace` R1"""
    a = mk_log()
    z = mk_log(workspace_id=w2.id, machine_id=m9.id)
    before_z = snap(db, z)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert snap(db, z) == before_z


# [claude] MML-GW-04
def test_mml_gw_04__a_soft_deleted_log_is_not_returned_an_inactive_live_log_is(db, w1, mk_log):
    """MML-GW-04 — a soft-deleted log is not returned, an inactive live log is.
    Rules: `get_by_workspace` R2"""
    a = mk_log()
    b = mk_log(is_active=False)
    c = mk_log(gone=True)
    before_c = snap(db, c)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 2
    assert snap(db, c) == before_c


# [claude] MML-GW-05
def test_mml_gw_05__a_soft_deleted_log_takes_no_place_in_the_page(db, w1, mk_log):
    """MML-GW-05 — a soft-deleted log takes no place in the page.
    Rules: `get_by_workspace` R2"""
    mk_log(maintenance_date=D3)
    mk_log(gone=True, maintenance_date=D2)
    c = mk_log(maintenance_date=D1)

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=1)

    # Then 1
    assert ids(result) == [c.id]


# [claude] MML-GW-06
def test_mml_gw_06__logs_of_deleted_and_inactive_parents_are_returned(db, w1, md, mf, mi, mg, mk_log):
    """MML-GW-06 — logs of deleted and inactive parents are returned.
    Rules: `get_by_workspace` R3"""
    a = mk_log(machine_id=md.id)
    b = mk_log(machine_id=mf.id)
    c = mk_log(machine_id=mi.id)
    e = mk_log(machine_id=mg.id)
    g = mk_log()

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id, c.id, e.id, g.id]


# [claude] MML-GW-07
def test_mml_gw_07__logs_of_deleted_and_inactive_parents_take_a_place_in_the_page(db, w1, md, mf, mi, mg, mk_log):
    """MML-GW-07 — logs of deleted and inactive parents take a place in the page.
    Rules: `get_by_workspace` R3"""
    mk_log(machine_id=md.id, maintenance_date=D5)
    mk_log(machine_id=mf.id, maintenance_date=D4)
    mk_log(machine_id=mi.id, maintenance_date=D3)
    mk_log(machine_id=mg.id, maintenance_date=D2)
    g = mk_log(maintenance_date=D1)

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=4)

    # Then 1
    assert ids(result) == [g.id]


# [claude] MML-GW-08
def test_mml_gw_08__logs_with_different_dates_come_back_latest_date_first_whatever_their_ids(db, w1, mk_log):
    """MML-GW-08 — logs with different dates come back latest date first, whatever their ids.
    Rules: `get_by_workspace` R4"""
    a = mk_log(maintenance_date=D2)
    b = mk_log(maintenance_date=D3)
    c = mk_log(maintenance_date=D1)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [b.id, a.id, c.id]


# [claude] MML-GW-09
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1100: Maintenance logs on the same date have no order (non-strict: with no tie-break the plan and the heap decide the order of ties)",
)
def test_mml_gw_09__logs_on_one_date_come_back_highest_id_first(db, w1, mk_log):
    """MML-GW-09 — logs on one date come back highest id first.
    Rules: `get_by_workspace` R4a [BUG-1100]"""
    a = mk_log()
    b = mk_log()
    c = mk_log()
    a.summary = "Edited"
    db.flush()

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id, c.id]
    # Then 2
    assert ids(result) == [c.id, b.id, a.id]


# [claude] MML-GW-10
@pytest.mark.xfail(strict=True, reason="BUG-1100: Maintenance logs on the same date have no order")
def test_mml_gw_10__the_query_asks_for_date_descending_then_id_descending(db, w1, mk_log):
    """MML-GW-10 — the query asks for date descending, then id descending.
    Rules: `get_by_workspace` R4a [BUG-1100]"""
    a = mk_log()

    with StatementRecorder(db) as recorder:
        result = dao.get_by_workspace(db, workspace_id=w1.id)
    [sql] = recorder.selects()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "maintenance_date DESC" in order_part
    # Then 4
    assert "machine_maintenance_logs.id DESC" in order_part
    # Then 5
    assert order_part.index("maintenance_date DESC") < order_part.index("machine_maintenance_logs.id DESC")


# [claude] MML-GW-11
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1100: Maintenance logs on the same date have no order (non-strict: with no tie-break the plan and the heap decide the order of ties)",
)
def test_mml_gw_11__paging_one_log_at_a_time_over_one_date_shows_each_log_once(db, w1, mk_log):
    """MML-GW-11 — paging one log at a time over one date shows each log once.
    Rules: `get_by_workspace` R4a [BUG-1100], R5"""
    a = mk_log()
    b = mk_log()
    c = mk_log()
    e = mk_log()
    g = mk_log()
    a.summary = "Edited"
    db.flush()

    pages = [ids(dao.get_by_workspace(db, workspace_id=w1.id, skip=k, limit=1)) for k in range(5)]

    # Then 1
    assert [len(p) for p in pages] == [1, 1, 1, 1, 1]
    # Then 2
    assert sorted(sum(pages, [])) == [a.id, b.id, c.id, e.id, g.id]  # noqa: RUF017
    # Then 3
    assert pages == [[g.id], [e.id], [c.id], [b.id], [a.id]]


# [claude] MML-GW-12
def test_mml_gw_12__with_the_default_limit_101_logs_give_the_latest_100(db, w1, mk_dated_logs):
    """MML-GW-12 — with the default limit, 101 logs give the latest 100.
    Rules: `get_by_workspace` R5"""
    rows = mk_dated_logs(101)
    all_ids = [r.id for r in rows]

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert set(ids(result)) == set(all_ids[1:])


# [claude] MML-GW-13
def test_mml_gw_13__limit_1000_gives_all_101_logs(db, w1, mk_dated_logs):
    """MML-GW-13 — limit=1000 gives all 101 logs.
    Rules: `get_by_workspace` R5"""
    rows = mk_dated_logs(101)
    all_ids = [r.id for r in rows]

    result = dao.get_by_workspace(db, workspace_id=w1.id, limit=1000)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert set(ids(result)) == set(all_ids)


# [claude] MML-GW-14
def test_mml_gw_14__skip_1_and_limit_2_give_the_second_and_third_log_by_date(db, w1, mk_log):
    """MML-GW-14 — skip=1 and limit=2 give the second and third log by date.
    Rules: `get_by_workspace` R5"""
    mk_log(maintenance_date=D4)
    b = mk_log(maintenance_date=D3)
    c = mk_log(maintenance_date=D2)
    mk_log(maintenance_date=D1)

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=1, limit=2)

    # Then 1
    assert ids(result) == [b.id, c.id]


# [claude] MML-GW-15
def test_mml_gw_15__limit_1_returns_only_the_latest_log(db, w1, mk_log):
    """MML-GW-15 — limit=1 returns only the latest log.
    Rules: `get_by_workspace` R5, R6"""
    a = mk_log(maintenance_date=D2)
    mk_log(maintenance_date=D1)

    result = dao.get_by_workspace(db, workspace_id=w1.id, limit=1)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MML-GW-16
def test_mml_gw_16__an_unknown_workspace_returns_an_empty_list(db, mk_log):
    """MML-GW-16 — an unknown workspace returns an empty list.
    Rules: `get_by_workspace` R6"""
    mk_log()

    result = dao.get_by_workspace(db, workspace_id=MISSING)

    # Then 1
    assert result == []


# [claude] MML-GW-17
def test_mml_gw_17__a_workspace_with_no_logs_returns_an_empty_list(db, w2, mk_log):
    """MML-GW-17 — a workspace with no logs returns an empty list.
    Rules: `get_by_workspace` R6"""
    mk_log()

    result = dao.get_by_workspace(db, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] MML-GW-18
def test_mml_gw_18__skip_equal_to_the_number_of_rows_returns_an_empty_list(db, w1, mk_log):
    """MML-GW-18 — skip equal to the number of rows returns an empty list.
    Rules: `get_by_workspace` R6"""
    mk_log()
    mk_log()

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [claude] MML-GW-19
def test_mml_gw_19__limit_0_returns_an_empty_list(db, w1, mk_log):
    """MML-GW-19 — limit=0 returns an empty list.
    Rules: `get_by_workspace` R6"""
    mk_log()
    mk_log()

    result = dao.get_by_workspace(db, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [claude] MML-GW-20
def test_mml_gw_20__skip_past_the_number_of_rows_returns_an_empty_list(db, w1, mk_log):
    """MML-GW-20 — skip past the number of rows returns an empty list.
    Rules: `get_by_workspace` R6"""
    mk_log()
    mk_log()

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=3)

    # Then 1
    assert result == []


# [claude] MML-GW-21
def test_mml_gw_21__skip_one_below_the_number_of_rows_returns_the_oldest_log(db, w1, mk_log):
    """MML-GW-21 — skip one below the number of rows returns the oldest log.
    Rules: `get_by_workspace` R5, R6"""
    mk_log(maintenance_date=D2)
    b = mk_log(maintenance_date=D1)

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] MML-GW-22
def test_mml_gw_22__a_negative_limit_is_rejected_by_postgres(db, w1, mk_log):
    """MML-GW-22 — a negative limit is rejected by Postgres.
    Rules: `get_by_workspace` R7, Errors row 1"""
    mk_log()
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_workspace(db, workspace_id=w1.id, limit=-1)
    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInLimitClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201W"
    # Then 4
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 5
    assert written(db) == before


# [claude] MML-GW-23
def test_mml_gw_23__a_negative_skip_is_rejected_by_postgres(db, w1, mk_log):
    """MML-GW-23 — a negative skip is rejected by Postgres.
    Rules: `get_by_workspace` R7, Errors row 2"""
    mk_log()
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_workspace(db, workspace_id=w1.id, skip=-1)
    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201X"
    # Then 4
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 5
    assert written(db) == before


# [claude] MML-GW-24
@pytest.mark.xfail(strict=True, reason="BUG-1101: A stored maintenance log linked to another workspace's machine shows that machine's id")
def test_mml_gw_24__a_log_linked_to_another_workspace_s_machine_is_not_returned(db, w1, m9, mk_log):
    """MML-GW-24 — a log linked to another workspace's machine is not returned.
    Rules: `get_by_workspace` R8 [BUG-1101]"""
    a = mk_log()
    x = mk_log(machine_id=m9.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert a.id in ids(result)
    # Then 2
    assert count_rows(db, "id = :id", id=x.id) == 1
    # Then 3
    assert sorted(ids(result)) == [a.id]


# [claude] MML-GW-25
@pytest.mark.xfail(strict=True, reason="BUG-1101: A stored maintenance log linked to another workspace's machine shows that machine's id")
def test_mml_gw_25__a_log_linked_to_another_workspace_s_machine_takes_no_place_in_the_page(db, w1, m9, mk_log):
    """MML-GW-25 — a log linked to another workspace's machine takes no place in the page.
    Rules: `get_by_workspace` R8 [BUG-1101]"""
    mk_log(maintenance_date=D1)
    x = mk_log(machine_id=m9.id, maintenance_date=D3)

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=1)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert count_rows(db, "id = :id", id=x.id) == 1
    # Then 3
    assert result == []


# [claude] MML-GW-26
def test_mml_gw_26__a_soft_deleted_log_ahead_of_the_skipped_row_uses_up_no_skip_the_filter_r(db, w1, mk_log):
    """MML-GW-26 — a soft-deleted log ahead of the skipped row uses up no skip: the filter runs before paging.
    Rules: `get_by_workspace` R2"""
    mk_log(gone=True, maintenance_date=D3)
    mk_log(maintenance_date=D2)
    c = mk_log(maintenance_date=D1)

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=1)

    # Then 1
    assert ids(result) == [c.id]


# --------------------------------------------------------------------------- #
# MachineMaintenanceLogDAO.get_by_id_and_workspace
# --------------------------------------------------------------------------- #


# [claude] MML-GI-01
def test_mml_gi_01__returns_the_session_s_log_with_that_id(db, w1, mk_log):
    """MML-GI-01 — returns the session's log with that id.
    Rules: `get_by_id_and_workspace` R1, Returns"""
    mk_log()
    b = mk_log()

    result = dao.get_by_id_and_workspace(db, id=b.id, workspace_id=w1.id)

    # Then 1
    assert result is b
    # Then 2
    assert isinstance(result, MachineMaintenanceLog)


# [claude] MML-GI-02
def test_mml_gi_02__reading_writes_nothing_and_leaves_a_pending_row_pending(db, w1, m1, m9, mk_log):
    """MML-GI-02 — reading writes nothing and leaves a pending row pending.
    Rules: `get_by_id_and_workspace` Side effects"""
    a = mk_log()
    x = mk_log(machine_id=m9.id)
    q = MachineMaintenanceLog(workspace_id=w1.id, machine_id=m1.id, maintenance_type=MaintenanceTypeEnum.REPAIR, maintenance_date=D1, summary="Pending")
    db.add(q)
    before_a = snap(db, a)
    before_x = snap(db, x)
    before = written(db)

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result is a
    # Then 2
    assert q in db.new
    # Then 3
    assert written(db) == before
    # Then 4
    assert count_rows(db, "summary = :summary", summary="Pending") == 0
    # Then 5
    assert snap(db, a) == before_a
    # Then 6
    assert snap(db, x) == before_x
    # Then 7
    assert count_rows(db, "id = :id", id=x.id) == 1


# [claude] MML-GI-03
def test_mml_gi_03__a_log_of_another_workspace_is_not_found(db, w1, w2, m9, mk_log):
    """MML-GI-03 — a log of another workspace is not found.
    Rules: `get_by_id_and_workspace` R2"""
    z = mk_log(workspace_id=w2.id, machine_id=m9.id)
    before_z = snap(db, z)

    result = dao.get_by_id_and_workspace(db, id=z.id, workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    assert snap(db, z) == before_z


# [claude] MML-GI-04
def test_mml_gi_04__an_unknown_id_returns_none(db, w1, mk_log):
    """MML-GI-04 — an unknown id returns None.
    Rules: `get_by_id_and_workspace` R3"""
    mk_log()

    result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] MML-GI-05
def test_mml_gi_05__id_0_returns_none(db, w1, mk_log):
    """MML-GI-05 — id=0 returns None.
    Rules: `get_by_id_and_workspace` R3"""
    mk_log()

    result = dao.get_by_id_and_workspace(db, id=0, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] MML-GI-06
def test_mml_gi_06__a_soft_deleted_log_is_found(db, w1, mk_log):
    """MML-GI-06 — a soft-deleted log is found.
    Rules: `get_by_id_and_workspace` R4"""
    a = mk_log(gone=True)
    before_a = snap(db, a)

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result is a
    # Then 2
    assert result.is_deleted is True
    # Then 3
    assert snap(db, a) == before_a


# [claude] MML-GI-07
def test_mml_gi_07__a_log_of_a_soft_deleted_machine_is_found(db, w1, md, mk_log):
    """MML-GI-07 — a log of a soft-deleted machine is found.
    Rules: `get_by_id_and_workspace` R5"""
    a = mk_log(machine_id=md.id)

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result is a


# [claude] MML-GI-08
def test_mml_gi_08__a_log_of_a_machine_in_a_soft_deleted_factory_is_found(db, w1, mf, mk_log):
    """MML-GI-08 — a log of a machine in a soft-deleted factory is found.
    Rules: `get_by_id_and_workspace` R5"""
    a = mk_log(machine_id=mf.id)

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result is a


# [claude] MML-GI-09
@pytest.mark.xfail(strict=True, reason="BUG-1101: A stored maintenance log linked to another workspace's machine shows that machine's id")
def test_mml_gi_09__a_log_linked_to_another_workspace_s_machine_is_not_found(db, w1, m9, mk_log):
    """MML-GI-09 — a log linked to another workspace's machine is not found.
    Rules: `get_by_id_and_workspace` R6 [BUG-1101]"""
    x = mk_log(machine_id=m9.id)

    result = dao.get_by_id_and_workspace(db, id=x.id, workspace_id=w1.id)

    # Then 1
    assert count_rows(db, "id = :id", id=x.id) == 1
    # Then 2
    assert result is None


# [claude] MML-GI-10
def test_mml_gi_10__a_log_of_a_machine_in_an_inactive_factory_is_found(db, w1, mg, mk_log):
    """MML-GI-10 — a log of a machine in an inactive factory is found.
    Rules: `get_by_id_and_workspace` R5"""
    a = mk_log(machine_id=mg.id)

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result is a


# --------------------------------------------------------------------------- #
# MachineMaintenanceLogDAO.get_by_machine
# --------------------------------------------------------------------------- #


# [claude] MML-GM-01
def test_mml_gm_01__returns_a_list_of_the_machine_s_live_logs(db, w1, m1, mk_log):
    """MML-GM-01 — returns a list of the machine's live logs.
    Rules: `get_by_machine` R1, Returns"""
    a = mk_log()
    b = mk_log()

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 3
    assert isinstance(result[0], MachineMaintenanceLog)


# [claude] MML-GM-02
def test_mml_gm_02__reading_writes_nothing_and_leaves_a_pending_row_pending(db, w1, m1, m9, mk_log):
    """MML-GM-02 — reading writes nothing and leaves a pending row pending.
    Rules: `get_by_machine` Side effects"""
    a = mk_log()
    x = mk_log(machine_id=m9.id)
    q = MachineMaintenanceLog(workspace_id=w1.id, machine_id=m1.id, maintenance_type=MaintenanceTypeEnum.REPAIR, maintenance_date=D1, summary="Pending")
    db.add(q)
    before_a = snap(db, a)
    before_x = snap(db, x)
    before = written(db)

    result = dao.get_by_machine(db, m1.id, workspace_id=w1.id)

    # Then 1
    assert a.id in ids(result)
    # Then 2
    assert q not in result
    # Then 3
    assert q in db.new
    # Then 4
    assert written(db) == before
    # Then 5
    assert count_rows(db, "summary = :summary", summary="Pending") == 0
    # Then 6
    assert snap(db, a) == before_a
    # Then 7
    assert snap(db, x) == before_x
    # Then 8
    assert count_rows(db, "id = :id", id=x.id) == 1


# [claude] MML-GM-03
def test_mml_gm_03__a_log_of_another_machine_is_not_returned(db, w1, m1, m2, mk_log):
    """MML-GM-03 — a log of another machine is not returned.
    Rules: `get_by_machine` R1"""
    a = mk_log()
    c = mk_log(machine_id=m2.id)
    before_c = snap(db, c)

    result = dao.get_by_machine(db, m1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert snap(db, c) == before_c


# [claude] MML-GM-04
def test_mml_gm_04__the_right_machine_under_another_workspace_returns_an_empty_list(db, w2, m1, mk_log):
    """MML-GM-04 — the right machine under another workspace returns an empty list.
    Rules: `get_by_machine` R2"""
    mk_log()

    result = dao.get_by_machine(db, m1.id, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] MML-GM-05
def test_mml_gm_05__a_soft_deleted_log_is_not_returned_an_inactive_live_log_is(db, w1, m1, mk_log):
    """MML-GM-05 — a soft-deleted log is not returned, an inactive live log is.
    Rules: `get_by_machine` R3"""
    a = mk_log()
    b = mk_log(is_active=False)
    c = mk_log(gone=True)
    before_c = snap(db, c)

    result = dao.get_by_machine(db, m1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 2
    assert snap(db, c) == before_c


# [claude] MML-GM-06
def test_mml_gm_06__a_soft_deleted_log_takes_no_place_in_the_page(db, w1, m1, mk_log):
    """MML-GM-06 — a soft-deleted log takes no place in the page.
    Rules: `get_by_machine` R3"""
    mk_log(maintenance_date=D3)
    mk_log(gone=True, maintenance_date=D2)
    c = mk_log(maintenance_date=D1)

    result = dao.get_by_machine(db, m1.id, workspace_id=w1.id, skip=1)

    # Then 1
    assert ids(result) == [c.id]


# [claude] MML-GM-07
def test_mml_gm_07__asked_for_a_soft_deleted_machine_its_logs_are_returned(db, w1, md, mk_log):
    """MML-GM-07 — asked for a soft-deleted machine, its logs are returned.
    Rules: `get_by_machine` R4"""
    a = mk_log(machine_id=md.id)

    result = dao.get_by_machine(db, md.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MML-GM-08
def test_mml_gm_08__asked_for_a_machine_in_a_soft_deleted_factory_its_logs_are_returned(db, w1, mf, mk_log):
    """MML-GM-08 — asked for a machine in a soft-deleted factory, its logs are returned.
    Rules: `get_by_machine` R4"""
    a = mk_log(machine_id=mf.id)

    result = dao.get_by_machine(db, mf.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MML-GM-09
def test_mml_gm_09__logs_with_different_dates_come_back_latest_date_first_whatever_their_ids(db, w1, m1, mk_log):
    """MML-GM-09 — logs with different dates come back latest date first, whatever their ids.
    Rules: `get_by_machine` R5 [BUG-1100]"""
    a = mk_log(maintenance_date=D2)
    b = mk_log(maintenance_date=D3)
    c = mk_log(maintenance_date=D1)

    result = dao.get_by_machine(db, m1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [b.id, a.id, c.id]


# [claude] MML-GM-10
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1100: Maintenance logs on the same date have no order (non-strict: with no tie-break the plan and the heap decide the order of ties)",
)
def test_mml_gm_10__logs_on_one_date_come_back_highest_id_first(db, w1, m1, mk_log):
    """MML-GM-10 — logs on one date come back highest id first.
    Rules: `get_by_machine` R5 [BUG-1100]"""
    a = mk_log()
    b = mk_log()
    c = mk_log()
    a.summary = "Edited"
    db.flush()

    result = dao.get_by_machine(db, m1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id, c.id]
    # Then 2
    assert ids(result) == [c.id, b.id, a.id]


# [claude] MML-GM-11
@pytest.mark.xfail(strict=True, reason="BUG-1100: Maintenance logs on the same date have no order")
def test_mml_gm_11__the_query_asks_for_date_descending_then_id_descending(db, w1, m1, mk_log):
    """MML-GM-11 — the query asks for date descending, then id descending.
    Rules: `get_by_machine` R5 [BUG-1100]"""
    a = mk_log()

    with StatementRecorder(db) as recorder:
        result = dao.get_by_machine(db, m1.id, workspace_id=w1.id)
    [sql] = recorder.selects()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "maintenance_date DESC" in order_part
    # Then 4
    assert "machine_maintenance_logs.id DESC" in order_part
    # Then 5
    assert order_part.index("maintenance_date DESC") < order_part.index("machine_maintenance_logs.id DESC")


# [claude] MML-GM-12
def test_mml_gm_12__with_the_default_limit_101_logs_give_the_latest_100(db, w1, m1, mk_dated_logs):
    """MML-GM-12 — with the default limit, 101 logs give the latest 100.
    Rules: `get_by_machine` R6"""
    rows = mk_dated_logs(101)
    all_ids = [r.id for r in rows]

    result = dao.get_by_machine(db, m1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert set(ids(result)) == set(all_ids[1:])


# [claude] MML-GM-13
def test_mml_gm_13__skip_1_and_limit_2_give_the_second_and_third_log_by_date(db, w1, m1, mk_log):
    """MML-GM-13 — skip=1 and limit=2 give the second and third log by date.
    Rules: `get_by_machine` R6"""
    mk_log(maintenance_date=D4)
    b = mk_log(maintenance_date=D3)
    c = mk_log(maintenance_date=D2)
    mk_log(maintenance_date=D1)

    result = dao.get_by_machine(db, m1.id, workspace_id=w1.id, skip=1, limit=2)

    # Then 1
    assert ids(result) == [b.id, c.id]


# [claude] MML-GM-14
def test_mml_gm_14__an_unknown_machine_id_returns_an_empty_list(db, w1, mk_log):
    """MML-GM-14 — an unknown machine id returns an empty list.
    Rules: `get_by_machine` R7"""
    mk_log()

    result = dao.get_by_machine(db, MISSING, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] MML-GM-15
def test_mml_gm_15__machine_id_0_returns_an_empty_list(db, w1, mk_log):
    """MML-GM-15 — machine_id=0 returns an empty list.
    Rules: `get_by_machine` R7"""
    mk_log()

    result = dao.get_by_machine(db, 0, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] MML-GM-16
def test_mml_gm_16__machine_id_none_returns_an_empty_list(db, w1, mk_log):
    """MML-GM-16 — machine_id=None returns an empty list.
    Rules: `get_by_machine` R7"""
    mk_log()

    result = dao.get_by_machine(db, None, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] MML-GM-17
def test_mml_gm_17__a_machine_with_no_logs_returns_an_empty_list(db, w1, m2, mk_log):
    """MML-GM-17 — a machine with no logs returns an empty list.
    Rules: `get_by_machine` R7"""
    mk_log()

    result = dao.get_by_machine(db, m2.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] MML-GM-18
def test_mml_gm_18__skip_equal_to_the_number_of_rows_returns_an_empty_list(db, w1, m1, mk_log):
    """MML-GM-18 — skip equal to the number of rows returns an empty list.
    Rules: `get_by_machine` R7"""
    mk_log()
    mk_log()

    result = dao.get_by_machine(db, m1.id, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [claude] MML-GM-19
def test_mml_gm_19__limit_0_returns_an_empty_list(db, w1, m1, mk_log):
    """MML-GM-19 — limit=0 returns an empty list.
    Rules: `get_by_machine` R7"""
    mk_log()
    mk_log()

    result = dao.get_by_machine(db, m1.id, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [claude] MML-GM-20
@pytest.mark.xfail(strict=True, reason="BUG-1101: A stored maintenance log linked to another workspace's machine shows that machine's id")
def test_mml_gm_20__a_log_linked_to_another_workspace_s_machine_is_not_returned(db, w1, m9, mk_log):
    """MML-GM-20 — a log linked to another workspace's machine is not returned.
    Rules: `get_by_machine` R8 [BUG-1101]"""
    x = mk_log(machine_id=m9.id)

    result = dao.get_by_machine(db, m9.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert count_rows(db, "id = :id", id=x.id) == 1
    # Then 3
    assert result == []


# [claude] MML-GM-21
def test_mml_gm_21__asked_under_the_machine_s_own_workspace_the_linked_log_is_not_returned(db, w2, m9, mk_log):
    """MML-GM-21 — asked under the machine's own workspace, the linked log is not returned.
    Rules: `get_by_machine` R8 [BUG-1101], R2"""
    mk_log(machine_id=m9.id)

    result = dao.get_by_machine(db, m9.id, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] MML-GM-22
def test_mml_gm_22__a_negative_limit_is_rejected_by_postgres(db, w1, m1, mk_log):
    """MML-GM-22 — a negative limit is rejected by Postgres.
    Rules: `get_by_machine` R9, Errors row 1"""
    mk_log()
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_machine(db, m1.id, workspace_id=w1.id, limit=-1)
    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInLimitClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201W"
    # Then 4
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 5
    assert written(db) == before


# [claude] MML-GM-23
def test_mml_gm_23__a_negative_skip_is_rejected_by_postgres(db, w1, m1, mk_log):
    """MML-GM-23 — a negative skip is rejected by Postgres.
    Rules: `get_by_machine` R9, Errors row 2"""
    mk_log()
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_machine(db, m1.id, workspace_id=w1.id, skip=-1)
    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201X"
    # Then 4
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 5
    assert written(db) == before


# [claude] MML-GM-24
def test_mml_gm_24__a_soft_deleted_log_ahead_of_the_skipped_row_uses_up_no_skip_the_filter_r(db, w1, m1, mk_log):
    """MML-GM-24 — a soft-deleted log ahead of the skipped row uses up no skip: the filter runs before paging.
    Rules: `get_by_machine` R3"""
    mk_log(gone=True, maintenance_date=D3)
    mk_log(maintenance_date=D2)
    c = mk_log(maintenance_date=D1)

    result = dao.get_by_machine(db, m1.id, workspace_id=w1.id, skip=1)

    # Then 1
    assert ids(result) == [c.id]


# [claude] MML-GM-25
def test_mml_gm_25__limit_1000_gives_all_101_logs(db, w1, m1, mk_dated_logs):
    """MML-GM-25 — limit=1000 gives all 101 logs.
    Rules: `get_by_machine` R6"""
    rows = mk_dated_logs(101)
    all_ids = [r.id for r in rows]

    result = dao.get_by_machine(db, m1.id, workspace_id=w1.id, limit=1000)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert set(ids(result)) == set(all_ids)


# [claude] MML-GM-26
def test_mml_gm_26__asked_for_a_machine_in_an_inactive_factory_its_logs_are_returned(db, w1, mg, mk_log):
    """MML-GM-26 — asked for a machine in an inactive factory, its logs are returned.
    Rules: `get_by_machine` R4"""
    a = mk_log(machine_id=mg.id)

    result = dao.get_by_machine(db, mg.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# --------------------------------------------------------------------------- #
# MachineMaintenanceLogDAO.get_by_type
# --------------------------------------------------------------------------- #


# [claude] MML-GT-01
def test_mml_gt_01__returns_a_list_of_the_workspace_s_live_logs_of_that_type(db, w1, m2, mk_log):
    """MML-GT-01 — returns a list of the workspace's live logs of that type.
    Rules: `get_by_type` R1, Returns"""
    a = mk_log()
    b = mk_log(machine_id=m2.id)

    result = dao.get_by_type(db, maintenance_type=MaintenanceTypeEnum.REPAIR, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 3
    assert isinstance(result[0], MachineMaintenanceLog)


# [claude] MML-GT-02
def test_mml_gt_02__reading_writes_nothing_and_leaves_a_pending_row_pending(db, w1, m1, m9, mk_log):
    """MML-GT-02 — reading writes nothing and leaves a pending row pending.
    Rules: `get_by_type` Side effects"""
    a = mk_log()
    x = mk_log(machine_id=m9.id)
    q = MachineMaintenanceLog(workspace_id=w1.id, machine_id=m1.id, maintenance_type=MaintenanceTypeEnum.REPAIR, maintenance_date=D1, summary="Pending")
    db.add(q)
    before_a = snap(db, a)
    before_x = snap(db, x)
    before = written(db)

    result = dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id)

    # Then 1
    assert a.id in ids(result)
    # Then 2
    assert q not in result
    # Then 3
    assert q in db.new
    # Then 4
    assert written(db) == before
    # Then 5
    assert count_rows(db, "summary = :summary", summary="Pending") == 0
    # Then 6
    assert snap(db, a) == before_a
    # Then 7
    assert snap(db, x) == before_x
    # Then 8
    assert count_rows(db, "id = :id", id=x.id) == 1


# [claude] MML-GT-03
def test_mml_gt_03__a_log_of_another_type_is_not_returned(db, w1, mk_log):
    """MML-GT-03 — a log of another type is not returned.
    Rules: `get_by_type` R1"""
    a = mk_log()
    c = mk_log(maintenance_type=MaintenanceTypeEnum.INSPECTION)
    before_c = snap(db, c)

    result = dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert snap(db, c) == before_c


# [claude] MML-GT-04
def test_mml_gt_04__a_log_of_that_type_in_another_workspace_is_not_returned(db, w1, w2, m9, mk_log):
    """MML-GT-04 — a log of that type in another workspace is not returned.
    Rules: `get_by_type` R1"""
    a = mk_log()
    z = mk_log(workspace_id=w2.id, machine_id=m9.id)
    before_z = snap(db, z)

    result = dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert snap(db, z) == before_z


# [claude] MML-GT-05
def test_mml_gt_05__a_soft_deleted_log_is_not_returned_an_inactive_live_log_is(db, w1, mk_log):
    """MML-GT-05 — a soft-deleted log is not returned, an inactive live log is.
    Rules: `get_by_type` R1"""
    a = mk_log()
    b = mk_log(is_active=False)
    c = mk_log(gone=True)
    before_c = snap(db, c)

    result = dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 2
    assert snap(db, c) == before_c


# [claude] MML-GT-06
def test_mml_gt_06__a_soft_deleted_log_takes_no_place_in_the_page(db, w1, mk_log):
    """MML-GT-06 — a soft-deleted log takes no place in the page.
    Rules: `get_by_type` R1"""
    mk_log(maintenance_date=D3)
    mk_log(gone=True, maintenance_date=D2)
    c = mk_log(maintenance_date=D1)

    result = dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id, skip=1)

    # Then 1
    assert ids(result) == [c.id]


# [claude] MML-GT-07
def test_mml_gt_07__a_plain_string_equal_to_a_member_s_value_works_like_the_member(db, w1, mk_log):
    """MML-GT-07 — a plain string equal to a member's value works like the member.
    Rules: `get_by_type` R2"""
    a = mk_log()
    mk_log(maintenance_type=MaintenanceTypeEnum.INSPECTION)

    result = dao.get_by_type(db, "REPAIR", workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MML-GT-08
def test_mml_gt_08__maintenance_type_none_returns_an_empty_list(db, w1, mk_log):
    """MML-GT-08 — maintenance_type=None returns an empty list.
    Rules: `get_by_type` R2"""
    mk_log()

    result = dao.get_by_type(db, None, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] MML-GT-09
def test_mml_gt_09__a_string_that_is_no_member_is_rejected_by_postgres(db, w1, mk_log):
    """MML-GT-09 — a string that is no member is rejected by Postgres.
    Rules: `get_by_type` R2, Errors row 3"""
    mk_log()
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_type(db, "BOGUS", workspace_id=w1.id)
    # Then 2
    assert isinstance(exc.value.orig, InvalidTextRepresentation)
    # Then 3
    assert exc.value.orig.pgcode == "22P02"
    # Then 4
    assert written(db) == before


# [claude] MML-GT-10
def test_mml_gt_10__a_member_s_value_in_lower_case_is_rejected_by_postgres(db, w1, mk_log):
    """MML-GT-10 — a member's value in lower case is rejected by Postgres.
    Rules: `get_by_type` R2, Errors row 3"""
    mk_log()
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_type(db, "repair", workspace_id=w1.id)
    # Then 2
    assert isinstance(exc.value.orig, InvalidTextRepresentation)
    # Then 3
    assert exc.value.orig.pgcode == "22P02"
    # Then 4
    assert written(db) == before


# [claude] MML-GT-11
def test_mml_gt_11__logs_with_different_dates_come_back_latest_date_first_whatever_their_ids(db, w1, mk_log):
    """MML-GT-11 — logs with different dates come back latest date first, whatever their ids.
    Rules: `get_by_type` R3 [BUG-1100]"""
    a = mk_log(maintenance_date=D2)
    b = mk_log(maintenance_date=D3)
    c = mk_log(maintenance_date=D1)

    result = dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [b.id, a.id, c.id]


# [claude] MML-GT-12
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1100: Maintenance logs on the same date have no order (non-strict: with no tie-break the plan and the heap decide the order of ties)",
)
def test_mml_gt_12__logs_on_one_date_come_back_highest_id_first(db, w1, mk_log):
    """MML-GT-12 — logs on one date come back highest id first.
    Rules: `get_by_type` R3 [BUG-1100]"""
    a = mk_log()
    b = mk_log()
    c = mk_log()
    a.summary = "Edited"
    db.flush()

    result = dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id, c.id]
    # Then 2
    assert ids(result) == [c.id, b.id, a.id]


# [claude] MML-GT-13
@pytest.mark.xfail(strict=True, reason="BUG-1100: Maintenance logs on the same date have no order")
def test_mml_gt_13__the_query_asks_for_date_descending_then_id_descending(db, w1, mk_log):
    """MML-GT-13 — the query asks for date descending, then id descending.
    Rules: `get_by_type` R3 [BUG-1100]"""
    a = mk_log()

    with StatementRecorder(db) as recorder:
        result = dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id)
    [sql] = recorder.selects()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "maintenance_date DESC" in order_part
    # Then 4
    assert "machine_maintenance_logs.id DESC" in order_part
    # Then 5
    assert order_part.index("maintenance_date DESC") < order_part.index("machine_maintenance_logs.id DESC")


# [claude] MML-GT-14
def test_mml_gt_14__logs_of_deleted_and_inactive_parents_are_returned(db, w1, md, mf, mi, mg, mk_log):
    """MML-GT-14 — logs of deleted and inactive parents are returned.
    Rules: `get_by_type` R3a"""
    a = mk_log(machine_id=md.id)
    b = mk_log(machine_id=mf.id)
    c = mk_log(machine_id=mi.id)
    e = mk_log(machine_id=mg.id)
    g = mk_log()

    result = dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id, c.id, e.id, g.id]


# [claude] MML-GT-15
def test_mml_gt_15__with_the_default_limit_101_logs_give_the_latest_100(db, w1, mk_dated_logs):
    """MML-GT-15 — with the default limit, 101 logs give the latest 100.
    Rules: `get_by_type` R4"""
    rows = mk_dated_logs(101)
    all_ids = [r.id for r in rows]

    result = dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert set(ids(result)) == set(all_ids[1:])


# [claude] MML-GT-16
def test_mml_gt_16__skip_1_and_limit_2_give_the_second_and_third_log_by_date(db, w1, mk_log):
    """MML-GT-16 — skip=1 and limit=2 give the second and third log by date.
    Rules: `get_by_type` R4"""
    mk_log(maintenance_date=D4)
    b = mk_log(maintenance_date=D3)
    c = mk_log(maintenance_date=D2)
    mk_log(maintenance_date=D1)

    result = dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id, skip=1, limit=2)

    # Then 1
    assert ids(result) == [b.id, c.id]


# [claude] MML-GT-17
def test_mml_gt_17__an_unknown_workspace_returns_an_empty_list(db, mk_log):
    """MML-GT-17 — an unknown workspace returns an empty list.
    Rules: `get_by_type` R4"""
    mk_log()

    result = dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=MISSING)

    # Then 1
    assert result == []


# [claude] MML-GT-18
def test_mml_gt_18__skip_equal_to_the_number_of_rows_returns_an_empty_list(db, w1, mk_log):
    """MML-GT-18 — skip equal to the number of rows returns an empty list.
    Rules: `get_by_type` R4"""
    mk_log()
    mk_log()

    result = dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [claude] MML-GT-19
def test_mml_gt_19__limit_0_returns_an_empty_list(db, w1, mk_log):
    """MML-GT-19 — limit=0 returns an empty list.
    Rules: `get_by_type` R4"""
    mk_log()
    mk_log()

    result = dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [claude] MML-GT-20
def test_mml_gt_20__a_negative_limit_is_rejected_by_postgres(db, w1, mk_log):
    """MML-GT-20 — a negative limit is rejected by Postgres.
    Rules: `get_by_type` R4, Errors row 1"""
    mk_log()
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id, limit=-1)
    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInLimitClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201W"
    # Then 4
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 5
    assert written(db) == before


# [claude] MML-GT-21
def test_mml_gt_21__a_negative_skip_is_rejected_by_postgres(db, w1, mk_log):
    """MML-GT-21 — a negative skip is rejected by Postgres.
    Rules: `get_by_type` R4, Errors row 2"""
    mk_log()
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id, skip=-1)
    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201X"
    # Then 4
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 5
    assert written(db) == before


# [claude] MML-GT-22
@pytest.mark.xfail(strict=True, reason="BUG-1101: A stored maintenance log linked to another workspace's machine shows that machine's id")
def test_mml_gt_22__a_log_linked_to_another_workspace_s_machine_is_not_returned(db, w1, m9, mk_log):
    """MML-GT-22 — a log linked to another workspace's machine is not returned.
    Rules: `get_by_type` R5 [BUG-1101]"""
    a = mk_log()
    x = mk_log(machine_id=m9.id)

    result = dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id)

    # Then 1
    assert a.id in ids(result)
    # Then 2
    assert count_rows(db, "id = :id", id=x.id) == 1
    # Then 3
    assert sorted(ids(result)) == [a.id]


# [claude] MML-GT-23
def test_mml_gt_23__a_soft_deleted_log_ahead_of_the_skipped_row_uses_up_no_skip_the_filter_r(db, w1, mk_log):
    """MML-GT-23 — a soft-deleted log ahead of the skipped row uses up no skip: the filter runs before paging.
    Rules: `get_by_type` R1"""
    mk_log(gone=True, maintenance_date=D3)
    mk_log(maintenance_date=D2)
    c = mk_log(maintenance_date=D1)

    result = dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id, skip=1)

    # Then 1
    assert ids(result) == [c.id]


# [claude] MML-GT-24
def test_mml_gt_24__limit_1000_gives_all_101_logs(db, w1, mk_dated_logs):
    """MML-GT-24 — limit=1000 gives all 101 logs.
    Rules: `get_by_type` R4"""
    rows = mk_dated_logs(101)
    all_ids = [r.id for r in rows]

    result = dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id, limit=1000)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert set(ids(result)) == set(all_ids)


# [claude] MML-GT-25
@pytest.mark.xfail(strict=True, reason="BUG-1101: A stored maintenance log linked to another workspace's machine shows that machine's id")
def test_mml_gt_25__a_log_linked_to_another_workspace_s_machine_takes_no_place_in_the_page(db, w1, m9, mk_log):
    """MML-GT-25 — a log linked to another workspace's machine takes no place in the page.
    Rules: `get_by_type` R5 [BUG-1101]"""
    mk_log(maintenance_date=D1)
    x = mk_log(machine_id=m9.id, maintenance_date=D3)

    result = dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id, skip=1)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert count_rows(db, "id = :id", id=x.id) == 1
    # Then 3
    assert result == []


# --------------------------------------------------------------------------- #
# MachineMaintenanceLogDAO.get_by_machine_and_type
# --------------------------------------------------------------------------- #


# [claude] MML-GP-01
def test_mml_gp_01__returns_a_list_of_the_live_logs_of_that_machine_and_type(db, w1, m1, mk_log):
    """MML-GP-01 — returns a list of the live logs of that machine and type.
    Rules: `get_by_machine_and_type` R1, Returns"""
    a = mk_log()
    b = mk_log()

    result = dao.get_by_machine_and_type(db, machine_id=m1.id, maintenance_type=MaintenanceTypeEnum.REPAIR, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 3
    assert isinstance(result[0], MachineMaintenanceLog)


# [claude] MML-GP-02
def test_mml_gp_02__reading_writes_nothing_and_leaves_a_pending_row_pending(db, w1, m1, m9, mk_log):
    """MML-GP-02 — reading writes nothing and leaves a pending row pending.
    Rules: `get_by_machine_and_type` Side effects"""
    a = mk_log()
    x = mk_log(machine_id=m9.id)
    q = MachineMaintenanceLog(workspace_id=w1.id, machine_id=m1.id, maintenance_type=MaintenanceTypeEnum.REPAIR, maintenance_date=D1, summary="Pending")
    db.add(q)
    before_a = snap(db, a)
    before_x = snap(db, x)
    before = written(db)

    result = dao.get_by_machine_and_type(db, m1.id, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id)

    # Then 1
    assert a.id in ids(result)
    # Then 2
    assert q not in result
    # Then 3
    assert q in db.new
    # Then 4
    assert written(db) == before
    # Then 5
    assert count_rows(db, "summary = :summary", summary="Pending") == 0
    # Then 6
    assert snap(db, a) == before_a
    # Then 7
    assert snap(db, x) == before_x
    # Then 8
    assert count_rows(db, "id = :id", id=x.id) == 1


# [claude] MML-GP-03
def test_mml_gp_03__another_type_on_that_machine_is_not_returned(db, w1, m1, mk_log):
    """MML-GP-03 — another type on that machine is not returned.
    Rules: `get_by_machine_and_type` R1"""
    a = mk_log()
    mk_log(maintenance_type=MaintenanceTypeEnum.INSPECTION)

    result = dao.get_by_machine_and_type(db, m1.id, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MML-GP-04
def test_mml_gp_04__that_type_on_another_machine_is_not_returned(db, w1, m1, m2, mk_log):
    """MML-GP-04 — that type on another machine is not returned.
    Rules: `get_by_machine_and_type` R1"""
    a = mk_log()
    mk_log(machine_id=m2.id)

    result = dao.get_by_machine_and_type(db, m1.id, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MML-GP-05
def test_mml_gp_05__the_same_machine_and_type_under_another_workspace_returns_an_empty_list(db, w2, m1, mk_log):
    """MML-GP-05 — the same machine and type under another workspace returns an empty list.
    Rules: `get_by_machine_and_type` R1"""
    mk_log()

    result = dao.get_by_machine_and_type(db, m1.id, MaintenanceTypeEnum.REPAIR, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] MML-GP-06
def test_mml_gp_06__a_soft_deleted_log_is_not_returned_an_inactive_live_log_is(db, w1, m1, mk_log):
    """MML-GP-06 — a soft-deleted log is not returned, an inactive live log is.
    Rules: `get_by_machine_and_type` R1"""
    a = mk_log()
    b = mk_log(is_active=False)
    c = mk_log(gone=True)
    before_c = snap(db, c)

    result = dao.get_by_machine_and_type(db, m1.id, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 2
    assert snap(db, c) == before_c


# [claude] MML-GP-07
def test_mml_gp_07__a_soft_deleted_log_takes_no_place_in_the_page(db, w1, m1, mk_log):
    """MML-GP-07 — a soft-deleted log takes no place in the page.
    Rules: `get_by_machine_and_type` R1"""
    mk_log(maintenance_date=D3)
    mk_log(gone=True, maintenance_date=D2)
    c = mk_log(maintenance_date=D1)

    result = dao.get_by_machine_and_type(db, m1.id, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id, skip=1)

    # Then 1
    assert ids(result) == [c.id]


# [claude] MML-GP-08
def test_mml_gp_08__a_plain_string_equal_to_a_member_s_value_works_like_the_member(db, w1, m1, mk_log):
    """MML-GP-08 — a plain string equal to a member's value works like the member.
    Rules: `get_by_machine_and_type` R2"""
    a = mk_log()
    mk_log(maintenance_type=MaintenanceTypeEnum.INSPECTION)

    result = dao.get_by_machine_and_type(db, m1.id, "REPAIR", workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MML-GP-09
def test_mml_gp_09__maintenance_type_none_returns_an_empty_list(db, w1, m1, mk_log):
    """MML-GP-09 — maintenance_type=None returns an empty list.
    Rules: `get_by_machine_and_type` R2"""
    mk_log()

    result = dao.get_by_machine_and_type(db, m1.id, None, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] MML-GP-10
def test_mml_gp_10__a_string_that_is_no_member_is_rejected_by_postgres(db, w1, m1, mk_log):
    """MML-GP-10 — a string that is no member is rejected by Postgres.
    Rules: `get_by_machine_and_type` R2, Errors row 3"""
    mk_log()
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_machine_and_type(db, m1.id, "BOGUS", workspace_id=w1.id)
    # Then 2
    assert isinstance(exc.value.orig, InvalidTextRepresentation)
    # Then 3
    assert exc.value.orig.pgcode == "22P02"
    # Then 4
    assert written(db) == before


# [claude] MML-GP-11
def test_mml_gp_11__an_unknown_machine_id_returns_an_empty_list(db, w1, mk_log):
    """MML-GP-11 — an unknown machine id returns an empty list.
    Rules: `get_by_machine_and_type` R2"""
    mk_log()

    result = dao.get_by_machine_and_type(db, MISSING, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] MML-GP-12
def test_mml_gp_12__machine_id_0_returns_an_empty_list(db, w1, mk_log):
    """MML-GP-12 — machine_id=0 returns an empty list.
    Rules: `get_by_machine_and_type` R2"""
    mk_log()

    result = dao.get_by_machine_and_type(db, 0, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] MML-GP-13
def test_mml_gp_13__machine_id_none_returns_an_empty_list(db, w1, mk_log):
    """MML-GP-13 — machine_id=None returns an empty list.
    Rules: `get_by_machine_and_type` R2"""
    mk_log()

    result = dao.get_by_machine_and_type(db, None, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] MML-GP-14
def test_mml_gp_14__logs_with_different_dates_come_back_latest_date_first_whatever_their_ids(db, w1, m1, mk_log):
    """MML-GP-14 — logs with different dates come back latest date first, whatever their ids.
    Rules: `get_by_machine_and_type` R3 [BUG-1100]"""
    a = mk_log(maintenance_date=D2)
    b = mk_log(maintenance_date=D3)
    c = mk_log(maintenance_date=D1)

    result = dao.get_by_machine_and_type(db, m1.id, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [b.id, a.id, c.id]


# [claude] MML-GP-15
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1100: Maintenance logs on the same date have no order (non-strict: with no tie-break the plan and the heap decide the order of ties)",
)
def test_mml_gp_15__logs_on_one_date_come_back_highest_id_first(db, w1, m1, mk_log):
    """MML-GP-15 — logs on one date come back highest id first.
    Rules: `get_by_machine_and_type` R3 [BUG-1100]"""
    a = mk_log()
    b = mk_log()
    c = mk_log()
    a.summary = "Edited"
    db.flush()

    result = dao.get_by_machine_and_type(db, m1.id, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id, c.id]
    # Then 2
    assert ids(result) == [c.id, b.id, a.id]


# [claude] MML-GP-16
@pytest.mark.xfail(strict=True, reason="BUG-1100: Maintenance logs on the same date have no order")
def test_mml_gp_16__the_query_asks_for_date_descending_then_id_descending(db, w1, m1, mk_log):
    """MML-GP-16 — the query asks for date descending, then id descending.
    Rules: `get_by_machine_and_type` R3 [BUG-1100]"""
    a = mk_log()

    with StatementRecorder(db) as recorder:
        result = dao.get_by_machine_and_type(db, m1.id, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id)
    [sql] = recorder.selects()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "maintenance_date DESC" in order_part
    # Then 4
    assert "machine_maintenance_logs.id DESC" in order_part
    # Then 5
    assert order_part.index("maintenance_date DESC") < order_part.index("machine_maintenance_logs.id DESC")


# [claude] MML-GP-17
def test_mml_gp_17__asked_for_a_soft_deleted_machine_its_logs_are_returned(db, w1, md, mk_log):
    """MML-GP-17 — asked for a soft-deleted machine, its logs are returned.
    Rules: `get_by_machine_and_type` R3a"""
    a = mk_log(machine_id=md.id)

    result = dao.get_by_machine_and_type(db, md.id, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MML-GP-18
def test_mml_gp_18__asked_for_a_machine_in_a_soft_deleted_factory_its_logs_are_returned(db, w1, mf, mk_log):
    """MML-GP-18 — asked for a machine in a soft-deleted factory, its logs are returned.
    Rules: `get_by_machine_and_type` R3a"""
    a = mk_log(machine_id=mf.id)

    result = dao.get_by_machine_and_type(db, mf.id, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MML-GP-19
def test_mml_gp_19__with_the_default_limit_101_logs_give_the_latest_100(db, w1, m1, mk_dated_logs):
    """MML-GP-19 — with the default limit, 101 logs give the latest 100.
    Rules: `get_by_machine_and_type` R4"""
    rows = mk_dated_logs(101)
    all_ids = [r.id for r in rows]

    result = dao.get_by_machine_and_type(db, m1.id, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert set(ids(result)) == set(all_ids[1:])


# [claude] MML-GP-20
def test_mml_gp_20__skip_1_and_limit_2_give_the_second_and_third_log_by_date(db, w1, m1, mk_log):
    """MML-GP-20 — skip=1 and limit=2 give the second and third log by date.
    Rules: `get_by_machine_and_type` R4"""
    mk_log(maintenance_date=D4)
    b = mk_log(maintenance_date=D3)
    c = mk_log(maintenance_date=D2)
    mk_log(maintenance_date=D1)

    result = dao.get_by_machine_and_type(db, m1.id, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id, skip=1, limit=2)

    # Then 1
    assert ids(result) == [b.id, c.id]


# [claude] MML-GP-21
def test_mml_gp_21__skip_equal_to_the_number_of_rows_returns_an_empty_list(db, w1, m1, mk_log):
    """MML-GP-21 — skip equal to the number of rows returns an empty list.
    Rules: `get_by_machine_and_type` R4"""
    mk_log()
    mk_log()

    result = dao.get_by_machine_and_type(db, m1.id, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [claude] MML-GP-22
def test_mml_gp_22__limit_0_returns_an_empty_list(db, w1, m1, mk_log):
    """MML-GP-22 — limit=0 returns an empty list.
    Rules: `get_by_machine_and_type` R4"""
    mk_log()
    mk_log()

    result = dao.get_by_machine_and_type(db, m1.id, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [claude] MML-GP-23
def test_mml_gp_23__a_negative_limit_is_rejected_by_postgres(db, w1, m1, mk_log):
    """MML-GP-23 — a negative limit is rejected by Postgres.
    Rules: `get_by_machine_and_type` R4, Errors row 1"""
    mk_log()
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_machine_and_type(db, m1.id, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id, limit=-1)
    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInLimitClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201W"
    # Then 4
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 5
    assert written(db) == before


# [claude] MML-GP-24
def test_mml_gp_24__a_negative_skip_is_rejected_by_postgres(db, w1, m1, mk_log):
    """MML-GP-24 — a negative skip is rejected by Postgres.
    Rules: `get_by_machine_and_type` R4, Errors row 2"""
    mk_log()
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_machine_and_type(db, m1.id, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id, skip=-1)
    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201X"
    # Then 4
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 5
    assert written(db) == before


# [claude] MML-GP-25
@pytest.mark.xfail(strict=True, reason="BUG-1101: A stored maintenance log linked to another workspace's machine shows that machine's id")
def test_mml_gp_25__a_log_linked_to_another_workspace_s_machine_is_not_returned(db, w1, m9, mk_log):
    """MML-GP-25 — a log linked to another workspace's machine is not returned.
    Rules: `get_by_machine_and_type` R5 [BUG-1101]"""
    x = mk_log(machine_id=m9.id)

    result = dao.get_by_machine_and_type(db, m9.id, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert count_rows(db, "id = :id", id=x.id) == 1
    # Then 3
    assert result == []


# [claude] MML-GP-26
def test_mml_gp_26__a_soft_deleted_log_ahead_of_the_skipped_row_uses_up_no_skip_the_filter_r(db, w1, m1, mk_log):
    """MML-GP-26 — a soft-deleted log ahead of the skipped row uses up no skip: the filter runs before paging.
    Rules: `get_by_machine_and_type` R1"""
    mk_log(gone=True, maintenance_date=D3)
    mk_log(maintenance_date=D2)
    c = mk_log(maintenance_date=D1)

    result = dao.get_by_machine_and_type(db, m1.id, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id, skip=1)

    # Then 1
    assert ids(result) == [c.id]


# [claude] MML-GP-27
def test_mml_gp_27__limit_1000_gives_all_101_logs(db, w1, m1, mk_dated_logs):
    """MML-GP-27 — limit=1000 gives all 101 logs.
    Rules: `get_by_machine_and_type` R4"""
    rows = mk_dated_logs(101)
    all_ids = [r.id for r in rows]

    result = dao.get_by_machine_and_type(db, m1.id, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id, limit=1000)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert set(ids(result)) == set(all_ids)


# [claude] MML-GP-28
def test_mml_gp_28__asked_for_a_machine_in_an_inactive_factory_its_logs_are_returned(db, w1, mg, mk_log):
    """MML-GP-28 — asked for a machine in an inactive factory, its logs are returned.
    Rules: `get_by_machine_and_type` R3a"""
    a = mk_log(machine_id=mg.id)

    result = dao.get_by_machine_and_type(db, mg.id, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# --------------------------------------------------------------------------- #
# MachineMaintenanceLogDAO.soft_delete
# --------------------------------------------------------------------------- #


# [claude] MML-SD-01
def test_mml_sd_01__a_live_log_is_marked_deleted_by_the_given_user(db, p1, mk_log):
    """MML-SD-01 — a live log is marked deleted by the given user.
    Rules: `soft_delete` R1, Returns"""
    a = mk_log()

    result = dao.soft_delete(db, db_obj=a, deleted_by=p1.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.is_deleted is True
    assert row.is_active is False
    # Then 3
    row = reread(db, a)
    assert row.deleted_by == p1.id
    # Then 4
    row = reread(db, a)
    assert row.deleted_at is not None


# [claude] MML-SD-02
@pytest.mark.xfail(strict=True, reason="BUG-1102: A maintenance log's delete time depends on the database's time zone")
def test_mml_sd_02__deleted_at_comes_from_utcnow_not_the_database_clock(db, p1, mk_log):
    """MML-SD-02 — deleted_at comes from utcnow, not the database clock.
    Rules: `soft_delete` R1a [BUG-1102]"""
    a = mk_log()

    result = dao.soft_delete(db, db_obj=a, deleted_by=p1.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.is_deleted is True
    # Then 3
    row = reread(db, a)
    assert row.deleted_at == NOW


# [claude] MML-SD-03
def test_mml_sd_03__no_other_column_changes(db, p1, p2, mk_log):
    """MML-SD-03 — no other column changes.
    Rules: `soft_delete` R2, Side effects"""
    a = mk_log(cost=Decimal("12.50"), performed_by="Rahim", created_by=p1.id, updated_by=p2.id)
    before_a = snap(db, a)

    result = dao.soft_delete(db, db_obj=a, deleted_by=p2.id)

    # Then 1
    assert result is a
    # Then 2
    assert without(snap(db, a), "is_deleted", "is_active", "deleted_at", "deleted_by", "updated_at") == without(before_a, "is_deleted", "is_active", "deleted_at", "deleted_by", "updated_at")
    # Then 3
    row = reread(db, a)
    assert row.cost == Decimal("12.50")
    assert row.performed_by == "Rahim"
    assert row.summary == "Bearing change"
    # Then 4
    row = reread(db, a)
    assert row.created_by == p1.id
    assert row.updated_by == p2.id
    # Then 5
    row = reread(db, a)
    assert row.updated_at is not None


# [claude] MML-SD-04
def test_mml_sd_04__an_already_deleted_log_is_stamped_again_with_no_error(db, p2, mk_log):
    """MML-SD-04 — an already deleted log is stamped again, with no error.
    Rules: `soft_delete` R3"""
    a = mk_log(gone=True)

    result = dao.soft_delete(db, db_obj=a, deleted_by=p2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.is_deleted is True
    assert row.is_active is False
    # Then 3
    row = reread(db, a)
    assert row.deleted_by == p2.id
    # Then 4
    row = reread(db, a)
    assert row.deleted_at is not None
    assert row.deleted_at != T0


# [claude] MML-SD-05
@pytest.mark.xfail(strict=True, reason="BUG-1102: A maintenance log's delete time depends on the database's time zone")
def test_mml_sd_05__an_already_deleted_log_gets_deleted_at_from_utcnow(db, p2, mk_log):
    """MML-SD-05 — an already deleted log gets deleted_at from utcnow.
    Rules: `soft_delete` R3, R1a [BUG-1102]"""
    a = mk_log(gone=True)

    result = dao.soft_delete(db, db_obj=a, deleted_by=p2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.deleted_by == p2.id
    # Then 3
    row = reread(db, a)
    assert row.deleted_at == NOW


# [claude] MML-SD-06
def test_mml_sd_06__the_delete_is_flushed_not_committed_a_rollback_brings_the_log_back(db, p1, mk_log):
    """MML-SD-06 — the delete is flushed, not committed: a rollback brings the log back.
    Rules: `soft_delete` R4, Overview (never commits)"""
    a = mk_log()

    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        sp = db.begin_nested()
        result = dao.soft_delete(db, db_obj=a, deleted_by=p1.id)

        # Then 1
        assert result is a
        # Then 2
        assert count_rows(db, "id = :id AND is_deleted = true", id=a.id) == 1
        # Then 3
        sp.rollback()
        db.refresh(a)
        row = reread(db, a)
        assert row.is_deleted is False
        assert row.is_active is True
        # Then 4
        row = reread(db, a)
        assert row.deleted_at is None
        assert row.deleted_by is None
        # Then 5
        assert commit_spy.call_count == 0


# [claude] MML-SD-07
def test_mml_sd_07__in_the_same_session_the_log_leaves_the_four_lists_and_stays_readable_by(db, w1, m1, p1, mk_log):
    """MML-SD-07 — in the same session the log leaves the four lists and stays readable by id.
    Rules: `soft_delete` R4"""
    a = mk_log()

    result = dao.soft_delete(db, db_obj=a, deleted_by=p1.id)

    # Then 1
    assert result is a
    # Then 2
    assert dao.get_by_workspace(db, workspace_id=w1.id) == []
    # Then 3
    assert dao.get_by_machine(db, m1.id, workspace_id=w1.id) == []
    # Then 4
    assert dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id) == []
    # Then 5
    assert dao.get_by_machine_and_type(db, m1.id, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id) == []
    # Then 6
    assert dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id) is a


# [claude] MML-SD-08
def test_mml_sd_08__a_log_of_another_workspace_is_deleted_like_any_other(db, w2, m9, p1, mk_log):
    """MML-SD-08 — a log of another workspace is deleted like any other.
    Rules: `soft_delete` R5"""
    z = mk_log(workspace_id=w2.id, machine_id=m9.id)

    result = dao.soft_delete(db, db_obj=z, deleted_by=p1.id)

    # Then 1
    assert result is z
    # Then 2
    row = reread(db, z)
    assert row.is_deleted is True
    assert row.deleted_by == p1.id


# [claude] MML-SD-09
def test_mml_sd_09__only_that_row_changes_the_machine_s_other_log_and_the_machine_stay_as_th(db, m1, p1, mk_log):
    """MML-SD-09 — only that row changes: the machine's other log and the machine stay as they were.
    Rules: `soft_delete` R5, Side effects"""
    a = mk_log()
    b = mk_log()
    before_b = snap(db, b)
    before_m1 = snap(db, m1)
    before = written(db)

    result = dao.soft_delete(db, db_obj=a, deleted_by=p1.id)

    # Then 1
    assert result is a
    # Then 2
    assert snap(db, b) == before_b
    # Then 3
    assert snap(db, m1) == before_m1
    # Then 4
    assert written(db) == before


# [claude] MML-SD-10
def test_mml_sd_10__an_unknown_profile_fails_on_flush_and_nothing_is_saved(db, mk_log):
    """MML-SD-10 — an unknown profile fails on flush and nothing is saved.
    Rules: `soft_delete` R6, Errors row 1"""
    a = mk_log()
    before_a = snap(db, a)
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.soft_delete(db, db_obj=a, deleted_by=MISSING)
    db.refresh(a)
    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert exc.value.orig.pgcode == "23503"
    # Then 4
    assert "machine_maintenance_logs_deleted_by_fkey" in str(exc.value.orig)
    # Then 5
    row = reread(db, a)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert snap(db, a) == before_a
    # Then 7
    assert written(db) == before


# [claude] MML-SD-11
def test_mml_sd_11__deleted_by_none_deletes_the_log_with_an_empty_stamp(db, mk_log):
    """MML-SD-11 — deleted_by=None deletes the log with an empty stamp.
    Rules: `soft_delete` R7"""
    a = mk_log()

    result = dao.soft_delete(db, db_obj=a, deleted_by=None)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.is_deleted is True
    assert row.is_active is False
    # Then 3
    row = reread(db, a)
    assert row.deleted_by is None
    assert row.deleted_at is not None


# [claude] MML-SD-12
def test_mml_sd_12__a_delete_by_another_profile_leaves_updated_by_as_it_was(db, p1, p2, mk_log):
    """MML-SD-12 — a delete by another profile leaves updated_by as it was.
    Rules: `soft_delete` R2"""
    a = mk_log(updated_by=p2.id)

    result = dao.soft_delete(db, db_obj=a, deleted_by=p1.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.deleted_by == p1.id
    # Then 3
    row = reread(db, a)
    assert row.updated_by == p2.id


# [claude] MML-SD-13
def test_mml_sd_13__a_delete_adds_no_machine_activity_row(db, m1, p1, mk_log):
    """MML-SD-13 — a delete adds no machine activity row.
    Rules: `soft_delete` Side effects"""
    a = mk_log()

    result = dao.soft_delete(db, db_obj=a, deleted_by=p1.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.is_deleted is True
    # Then 3
    assert count_activity(db, "machine_id = :id", id=m1.id) == 0


# --------------------------------------------------------------------------- #
# MachineMaintenanceLogDAO.restore
# --------------------------------------------------------------------------- #


# [claude] MML-RS-01
def test_mml_rs_01__a_soft_deleted_log_is_live_again_in_the_database(db, mk_log):
    """MML-RS-01 — a soft-deleted log is live again, in the database.
    Rules: `restore` R1, Returns"""
    a = mk_log(gone=True)

    result = dao.restore(db, db_obj=a)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.is_deleted is False
    assert row.is_active is True
    # Then 3
    row = reread(db, a)
    assert row.deleted_at is None
    assert row.deleted_by is None


# [claude] MML-RS-02
def test_mml_rs_02__no_other_column_changes_and_nobody_is_recorded(db, p1, p2, mk_log):
    """MML-RS-02 — no other column changes and nobody is recorded.
    Rules: `restore` R2, Side effects"""
    a = mk_log(gone=True, cost=Decimal("12.50"), performed_by="Rahim", created_by=p1.id, updated_by=p2.id)
    before_a = snap(db, a)

    result = dao.restore(db, db_obj=a)

    # Then 1
    assert result is a
    # Then 2
    assert without(snap(db, a), "is_deleted", "is_active", "deleted_at", "deleted_by", "updated_at") == without(before_a, "is_deleted", "is_active", "deleted_at", "deleted_by", "updated_at")
    # Then 3
    row = reread(db, a)
    assert row.cost == Decimal("12.50")
    assert row.performed_by == "Rahim"
    # Then 4
    row = reread(db, a)
    assert row.created_by == p1.id
    assert row.updated_by == p2.id
    # Then 5
    row = reread(db, a)
    assert row.updated_at is not None


# [claude] MML-RS-03
def test_mml_rs_03__a_live_active_log_nothing_changes_and_no_update_is_issued(db, mk_log):
    """MML-RS-03 — a live, active log: nothing changes and no UPDATE is issued.
    Rules: `restore` R3, Side effects"""
    a = mk_log()
    db.refresh(a)
    before_a = snap(db, a)

    with StatementRecorder(db) as recorder:
        result = dao.restore(db, db_obj=a)

    # Then 1
    assert result is a
    # Then 2
    assert not [s for s in recorder.statements if s.lstrip().startswith("UPDATE")]
    # Then 3
    row = reread(db, a)
    assert row.updated_at is None
    # Then 4
    assert snap(db, a) == before_a


# [claude] MML-RS-04
def test_mml_rs_04__a_live_inactive_log_becomes_active(db, mk_log):
    """MML-RS-04 — a live, inactive log becomes active.
    Rules: `restore` R4"""
    a = mk_log(is_active=False)

    result = dao.restore(db, db_obj=a)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.is_active is True
    assert row.is_deleted is False


# [claude] MML-RS-05
def test_mml_rs_05__the_restore_is_flushed_not_committed_a_rollback_brings_the_delete_back(db, p1, mk_log):
    """MML-RS-05 — the restore is flushed, not committed: a rollback brings the delete back.
    Rules: `restore` R5, Overview (never commits)"""
    a = mk_log(gone=True)

    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        sp = db.begin_nested()
        result = dao.restore(db, db_obj=a)

        # Then 1
        assert result is a
        # Then 2
        assert count_rows(db, "id = :id AND is_deleted = false", id=a.id) == 1
        # Then 3
        sp.rollback()
        db.refresh(a)
        row = reread(db, a)
        assert row.is_deleted is True
        assert row.is_active is False
        # Then 4
        row = reread(db, a)
        assert row.deleted_at == T0
        assert row.deleted_by == p1.id
        # Then 5
        assert commit_spy.call_count == 0


# [claude] MML-RS-06
def test_mml_rs_06__in_the_same_session_the_log_is_back_in_the_four_lists(db, w1, m1, mk_log):
    """MML-RS-06 — in the same session the log is back in the four lists.
    Rules: `restore` R5"""
    a = mk_log(gone=True)

    result = dao.restore(db, db_obj=a)

    # Then 1
    assert result is a
    # Then 2
    assert ids(dao.get_by_workspace(db, workspace_id=w1.id)) == [a.id]
    # Then 3
    assert ids(dao.get_by_machine(db, m1.id, workspace_id=w1.id)) == [a.id]
    # Then 4
    assert ids(dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id)) == [a.id]
    # Then 5
    assert ids(dao.get_by_machine_and_type(db, m1.id, MaintenanceTypeEnum.REPAIR, workspace_id=w1.id)) == [a.id]


# [claude] MML-RS-07
def test_mml_rs_07__a_log_of_a_soft_deleted_machine_is_restored_the_machine_and_other_logs_s(db, md, mk_log):
    """MML-RS-07 — a log of a soft-deleted machine is restored; the machine and other logs stay as they were.
    Rules: `restore` R6, Side effects"""
    a = mk_log(gone=True, machine_id=md.id)
    b = mk_log(gone=True, machine_id=md.id)
    before_md = snap(db, md)
    before_b = snap(db, b)

    result = dao.restore(db, db_obj=a)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.is_deleted is False
    assert row.is_active is True
    # Then 3
    assert snap(db, md) == before_md
    # Then 4
    assert snap(db, b) == before_b


# [claude] MML-RS-08
def test_mml_rs_08__a_log_of_another_workspace_is_restored_like_any_other(db, w2, m9, mk_log):
    """MML-RS-08 — a log of another workspace is restored like any other.
    Rules: `restore` R6"""
    z = mk_log(gone=True, workspace_id=w2.id, machine_id=m9.id)

    result = dao.restore(db, db_obj=z)

    # Then 1
    assert result is z
    # Then 2
    row = reread(db, z)
    assert row.is_deleted is False
    assert row.is_active is True


# [claude] MML-RS-09
def test_mml_rs_09__delete_then_restore_gives_every_column_back_except_updated_at(db, p1, p2, mk_log):
    """MML-RS-09 — delete then restore gives every column back except updated_at.
    Rules: `restore` R7"""
    a = mk_log(cost=Decimal("12.50"), performed_by="Rahim", created_by=p1.id, updated_by=p2.id)
    before_a = snap(db, a)
    dao.soft_delete(db, db_obj=a, deleted_by=p2.id)

    result = dao.restore(db, db_obj=a)

    # Then 1
    assert result is a
    # Then 2
    assert without(snap(db, a), "updated_at") == without(before_a, "updated_at")
    # Then 3
    row = reread(db, a)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 4
    row = reread(db, a)
    assert row.updated_at is not None


# [claude] MML-RS-10
def test_mml_rs_10__a_restore_adds_no_machine_activity_row(db, m1, mk_log):
    """MML-RS-10 — a restore adds no machine activity row.
    Rules: `restore` R2, Side effects"""
    a = mk_log(gone=True)

    result = dao.restore(db, db_obj=a)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.is_deleted is False
    # Then 3
    assert count_activity(db, "machine_id = :id", id=m1.id) == 0


# --------------------------------------------------------------------------- #
# Inherited BaseDAO methods on MachineMaintenanceLog
# --------------------------------------------------------------------------- #


# [claude] MML-INH-01
def test_mml_inh_01__create_with_a_dict_stores_a_row_with_the_defaults(db, w1, m1, new):
    """MML-INH-01 — create with a dict stores a row with the defaults.
    Rules: `inherited` R1"""
    result = dao.create(db, obj_in=new)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.machine_id == m1.id
    assert row.maintenance_type == MaintenanceTypeEnum.REPAIR
    # Then 3
    row = reread(db, result)
    assert row.maintenance_date == D1
    assert row.summary == "Bearing change"
    # Then 4
    row = reread(db, result)
    assert row.is_active is True
    assert row.is_deleted is False
    assert row.created_at is not None
    # Then 5
    row = reread(db, result)
    assert row.cost is None
    assert row.performed_by is None
    assert row.created_by is None
    # Then 6
    row = reread(db, result)
    assert row.updated_at is None
    assert row.updated_by is None
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 7
    assert count_rows(db, "workspace_id = :id", id=w1.id) == 1


# [claude] MML-INH-02
def test_mml_inh_02__create_is_flushed_not_committed_a_rollback_removes_the_row(db, w1, new):
    """MML-INH-02 — create is flushed, not committed: a rollback removes the row.
    Rules: `inherited` R1, Overview (never commits)"""
    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        sp = db.begin_nested()
        result = dao.create(db, obj_in=new)

        # Then 1
        assert result.id is not None
        # Then 2
        assert count_rows(db, "workspace_id = :id", id=w1.id) == 1
        # Then 3
        sp.rollback()
        assert count_rows(db, "workspace_id = :id", id=w1.id) == 0
        # Then 4
        assert commit_spy.call_count == 0


# [claude] MML-INH-03
def test_mml_inh_03__create_with_a_machinemaintenancelogcreate_fails_on_flush_and_saves_nothi(db, w1, m1):
    """MML-INH-03 — create with a MachineMaintenanceLogCreate fails on flush and saves nothing.
    Rules: `inherited` R2, Errors row 1"""
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in=MachineMaintenanceLogCreate(machine_id=m1.id, maintenance_type=MaintenanceTypeEnum.REPAIR, maintenance_date=D1, summary="Bearing change"))
    # Then 2
    assert isinstance(exc.value.orig, NotNullViolation)
    # Then 3
    assert exc.value.orig.pgcode == "23502"
    # Then 4
    assert "workspace_id" in str(exc.value.orig)
    # Then 5
    assert count_rows(db, "workspace_id = :id", id=w1.id) == 0
    # Then 6
    assert written(db) == before


# [claude] MML-INH-04
def test_mml_inh_04__create_with_a_required_column_none_fails_on_flush_and_saves_nothing(db, w1, new):
    """MML-INH-04 — create with a required column None fails on flush and saves nothing.
    Rules: `inherited` R2, Errors row 1"""
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={**new, "summary": None})
    # Then 2
    assert isinstance(exc.value.orig, NotNullViolation)
    # Then 3
    assert exc.value.orig.pgcode == "23502"
    # Then 4
    assert count_rows(db, "workspace_id = :id", id=w1.id) == 0
    # Then 5
    assert written(db) == before


# [claude] MML-INH-05
def test_mml_inh_05__create_with_an_unknown_machine_fails_on_flush_and_saves_nothing(db, w1, new):
    """MML-INH-05 — create with an unknown machine fails on flush and saves nothing.
    Rules: `inherited` R3, Errors row 2"""
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={**new, "machine_id": MISSING})
    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert exc.value.orig.pgcode == "23503"
    # Then 4
    assert "machine_maintenance_logs_machine_id_fkey" in str(exc.value.orig)
    # Then 5
    assert count_rows(db, "workspace_id = :id", id=w1.id) == 0
    # Then 6
    assert written(db) == before


# [claude] MML-INH-06
def test_mml_inh_06__create_with_a_key_the_model_does_not_have_raises_typeerror(db, w1, new):
    """MML-INH-06 — create with a key the model does not have raises TypeError.
    Rules: `inherited` R3, Errors row 6"""
    before = written(db)

    # Then 1
    with pytest.raises(TypeError):
        dao.create(db, obj_in={**new, "nonsense": 1})
    # Then 2
    assert not db.new
    # Then 3
    assert count_rows(db, "workspace_id = :id", id=w1.id) == 0
    # Then 4
    assert written(db) == before


# [claude] MML-INH-07
def test_mml_inh_07__create_with_a_maintenance_type_string_that_is_no_member_fails_on_flush(db, w1, new):
    """MML-INH-07 — create with a maintenance_type string that is no member fails on flush.
    Rules: `inherited` R3, Errors row 3"""
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={**new, "maintenance_type": "BOGUS"})
    # Then 2
    assert isinstance(exc.value.orig, InvalidTextRepresentation)
    # Then 3
    assert exc.value.orig.pgcode == "22P02"
    # Then 4
    assert count_rows(db, "workspace_id = :id", id=w1.id) == 0
    # Then 5
    assert written(db) == before


# [claude] MML-INH-08
def test_mml_inh_08__hr_15_cost_0_125_is_stored_as_0_13_half_rounds_up(db, new):
    """MML-INH-08 — HR-15: cost 0.125 is stored as 0.13 (half rounds up).
    Rules: `inherited` R4"""
    result = dao.create(db, obj_in={**new, "cost": Decimal("0.125")})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.cost == Decimal("0.13")


# [claude] MML-INH-09
def test_mml_inh_09__hr_15_cost_0_135_is_stored_as_0_14_half_rounds_up(db, new):
    """MML-INH-09 — HR-15: cost 0.135 is stored as 0.14 (half rounds up).
    Rules: `inherited` R4"""
    result = dao.create(db, obj_in={**new, "cost": Decimal("0.135")})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.cost == Decimal("0.14")


# [claude] MML-INH-10
def test_mml_inh_10__hr_15_cost_2_675_is_stored_as_2_68_half_rounds_up(db, new):
    """MML-INH-10 — HR-15: cost 2.675 is stored as 2.68 (half rounds up).
    Rules: `inherited` R4"""
    result = dao.create(db, obj_in={**new, "cost": Decimal("2.675")})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.cost == Decimal("2.68")


# [claude] MML-INH-11
def test_mml_inh_11__hr_15_cost_1_005_is_stored_as_1_01_half_rounds_away_from_zero(db, new):
    """MML-INH-11 — HR-15: cost -1.005 is stored as -1.01 (half rounds away from zero).
    Rules: `inherited` R4"""
    result = dao.create(db, obj_in={**new, "cost": Decimal("-1.005")})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.cost == Decimal("-1.01")


# [claude] MML-INH-12
def test_mml_inh_12__hr_15_cost_0_124_is_stored_as_0_12_just_below_the_half_rounds_down(db, new):
    """MML-INH-12 — HR-15: cost 0.124 is stored as 0.12 (just below the half rounds down).
    Rules: `inherited` R4"""
    result = dao.create(db, obj_in={**new, "cost": Decimal("0.124")})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.cost == Decimal("0.12")


# [claude] MML-INH-13
def test_mml_inh_13__hr_15_a_float_cost_1_005_is_stored_as_1_01(db, new):
    """MML-INH-13 — HR-15: a float cost 1.005 is stored as 1.01.
    Rules: `inherited` R4"""
    result = dao.create(db, obj_in={**new, "cost": 1.005})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.cost == Decimal("1.01")


# [claude] MML-INH-14
def test_mml_inh_14__hr_15_the_object_keeps_the_value_as_given_until_a_refresh(db, new):
    """MML-INH-14 — HR-15: the object keeps the value as given until a refresh.
    Rules: `inherited` R4"""
    result = dao.create(db, obj_in={**new, "cost": Decimal("0.125")})

    # Then 1
    assert result.cost == Decimal("0.125")
    # Then 2
    db.refresh(result)
    assert result.cost == Decimal("0.13")


# [claude] MML-INH-15
def test_mml_inh_15__hr_15_update_rounds_the_same_way(db, mk_log):
    """MML-INH-15 — HR-15: update rounds the same way.
    Rules: `inherited` R4"""
    a = mk_log(cost=Decimal("5.00"))

    result = dao.update(db, db_obj=a, obj_in={"cost": Decimal("0.125")})

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.cost == Decimal("0.13")


# [claude] MML-INH-16
def test_mml_inh_16__cost_at_the_top_of_the_column_is_stored(db, new):
    """MML-INH-16 — cost at the top of the column is stored.
    Rules: `inherited` R5"""
    result = dao.create(db, obj_in={**new, "cost": Decimal("9999999999999.99")})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.cost == Decimal("9999999999999.99")


# [claude] MML-INH-17
def test_mml_inh_17__cost_that_rounds_down_to_the_top_of_the_column_is_stored_as_99(db, new):
    """MML-INH-17 — cost that rounds down to the top of the column is stored as .99.
    Rules: `inherited` R5"""
    result = dao.create(db, obj_in={**new, "cost": Decimal("9999999999999.994")})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.cost == Decimal("9999999999999.99")


# [claude] MML-INH-18
def test_mml_inh_18__cost_that_rounds_past_the_top_of_the_column_is_rejected(db, w1, new):
    """MML-INH-18 — cost that rounds past the top of the column is rejected.
    Rules: `inherited` R5, Errors row 4"""
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={**new, "cost": Decimal("9999999999999.995")})
    # Then 2
    assert isinstance(exc.value.orig, NumericValueOutOfRange)
    # Then 3
    assert exc.value.orig.pgcode == "22003"
    # Then 4
    assert count_rows(db, "workspace_id = :id", id=w1.id) == 0
    # Then 5
    assert written(db) == before


# [claude] MML-INH-19
def test_mml_inh_19__cost_one_digit_too_long_is_rejected(db, w1, new):
    """MML-INH-19 — cost one digit too long is rejected.
    Rules: `inherited` R5, Errors row 4"""
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={**new, "cost": Decimal("10000000000000")})  # noqa: FURB157
    # Then 2
    assert isinstance(exc.value.orig, NumericValueOutOfRange)
    # Then 3
    assert exc.value.orig.pgcode == "22003"
    # Then 4
    assert count_rows(db, "workspace_id = :id", id=w1.id) == 0
    # Then 5
    assert written(db) == before


# [claude] MML-INH-20
def test_mml_inh_20__decimal_nan_is_not_checked_here_and_is_stored_as_nan(db, new):
    """MML-INH-20 — Decimal NaN is not checked here and is stored as NaN.
    Rules: `inherited` R5"""
    result = dao.create(db, obj_in={**new, "cost": Decimal("NaN")})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.cost.is_nan()


# [claude] MML-INH-21
def test_mml_inh_21__the_schema_refuses_a_nan_cost(db, w1, m1):
    """MML-INH-21 — the schema refuses a NaN cost.
    Rules: `inherited` R5"""
    # Then 1
    with pytest.raises(ValidationError):
        MachineMaintenanceLogCreate(machine_id=m1.id, maintenance_type=MaintenanceTypeEnum.REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("NaN"))
    # Then 2
    assert count_rows(db, "workspace_id = :id", id=w1.id) == 0


# [claude] MML-INH-22
def test_mml_inh_22__a_negative_cost_is_stored(db, new):
    """MML-INH-22 — a negative cost is stored.
    Rules: `inherited` R6"""
    result = dao.create(db, obj_in={**new, "cost": Decimal("-3.50")})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.cost == Decimal("-3.50")


# [claude] MML-INH-23
def test_mml_inh_23__cost_0_is_stored_not_treated_as_empty(db, new):
    """MML-INH-23 — cost 0 is stored, not treated as empty.
    Rules: `inherited` R6"""
    result = dao.create(db, obj_in={**new, "cost": Decimal("0")})  # noqa: FURB157

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.cost == Decimal("0.00")
    assert row.cost is not None


# [claude] MML-INH-24
def test_mml_inh_24__an_empty_summary_and_a_date_of_1900_are_stored(db, new):
    """MML-INH-24 — an empty summary and a date of 1900 are stored.
    Rules: `inherited` R6"""
    result = dao.create(db, obj_in={**new, "summary": "", "maintenance_date": date(1900, 1, 1)})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.summary == ""
    assert row.maintenance_date == date(1900, 1, 1)


# [claude] MML-INH-25
def test_mml_inh_25__a_summary_with_surrounding_spaces_and_a_date_of_2099_are_stored_as_given(db, new):
    """MML-INH-25 — a summary with surrounding spaces and a date of 2099 are stored as given.
    Rules: `inherited` R6"""
    result = dao.create(db, obj_in={**new, "summary": "  Pump  ", "maintenance_date": date(2099, 12, 31)})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.summary == "  Pump  "
    assert row.maintenance_date == date(2099, 12, 31)


# [claude] MML-INH-26
def test_mml_inh_26__a_summary_of_100_000_characters_is_stored(db, new):
    """MML-INH-26 — a summary of 100 000 characters is stored.
    Rules: `inherited` R6"""
    result = dao.create(db, obj_in={**new, "summary": "a" * 100000})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert len(row.summary) == 100000


# [claude] MML-INH-27
def test_mml_inh_27__performed_by_of_255_characters_is_stored(db, new):
    """MML-INH-27 — performed_by of 255 characters is stored.
    Rules: `inherited` R7"""
    result = dao.create(db, obj_in={**new, "performed_by": "p" * 255})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert len(row.performed_by) == 255


# [claude] MML-INH-28
def test_mml_inh_28__performed_by_of_256_characters_is_rejected(db, w1, new):
    """MML-INH-28 — performed_by of 256 characters is rejected.
    Rules: `inherited` R7, Errors row 5"""
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={**new, "performed_by": "p" * 256})
    # Then 2
    assert isinstance(exc.value.orig, StringDataRightTruncation)
    # Then 3
    assert exc.value.orig.pgcode == "22001"
    # Then 4
    assert count_rows(db, "workspace_id = :id", id=w1.id) == 0
    # Then 5
    assert written(db) == before


# [claude] MML-INH-29
def test_mml_inh_29__create_saves_a_log_for_a_soft_deleted_machine(db, md, new):
    """MML-INH-29 — create saves a log for a soft-deleted machine.
    Rules: `inherited` R8"""
    before_md = snap(db, md)

    result = dao.create(db, obj_in={**new, "machine_id": md.id})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.machine_id == md.id
    # Then 3
    assert snap(db, md) == before_md


# [claude] MML-INH-30
def test_mml_inh_30__create_saves_a_log_for_another_workspace_s_machine(db, w1, m9, new):
    """MML-INH-30 — create saves a log for another workspace's machine.
    Rules: `inherited` R8"""
    result = dao.create(db, obj_in={**new, "machine_id": m9.id})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.machine_id == m9.id


# [claude] MML-INH-31
def test_mml_inh_31__update_with_the_schema_applies_a_value_and_drops_an_explicit_none(db, mk_log):
    """MML-INH-31 — update with the schema applies a value and drops an explicit None.
    Rules: `inherited` R9"""
    a = mk_log(cost=Decimal("12.50"))

    result = dao.update(db, db_obj=a, obj_in=MachineMaintenanceLogUpdate(summary="new", cost=None))

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.summary == "new"
    # Then 3
    row = reread(db, a)
    assert row.cost == Decimal("12.50")


# [claude] MML-INH-32
def test_mml_inh_32__update_with_the_schema_applies_cost_0(db, mk_log):
    """MML-INH-32 — update with the schema applies cost=0.
    Rules: `inherited` R9"""
    a = mk_log(cost=Decimal("12.50"))

    result = dao.update(db, db_obj=a, obj_in=MachineMaintenanceLogUpdate(cost=0))

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.cost == Decimal("0.00")


# [claude] MML-INH-33
def test_mml_inh_33__update_with_a_dict_clears_cost_and_performed_by(db, mk_log):
    """MML-INH-33 — update with a dict clears cost and performed_by.
    Rules: `inherited` R10"""
    a = mk_log(cost=Decimal("12.50"), performed_by="Rahim")

    result = dao.update(db, db_obj=a, obj_in={"cost": None, "performed_by": None})

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.cost is None
    assert row.performed_by is None


# [claude] MML-INH-34
def test_mml_inh_34__update_with_a_dict_moves_the_log_to_another_machine_and_skips_an_unknown(db, m2, mk_log):
    """MML-INH-34 — update with a dict moves the log to another machine and skips an unknown key.
    Rules: `inherited` R10"""
    a = mk_log()

    result = dao.update(db, db_obj=a, obj_in={"machine_id": m2.id, "nonsense": 1})

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.machine_id == m2.id
    # Then 3
    assert not hasattr(a, "nonsense")


# [claude] MML-INH-35
def test_mml_inh_35__update_with_summary_none_fails_on_flush_and_changes_nothing(db, mk_log):
    """MML-INH-35 — update with summary None fails on flush and changes nothing.
    Rules: `inherited` R10, Errors row 1"""
    a = mk_log()
    before_a = snap(db, a)
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.update(db, db_obj=a, obj_in={"summary": None})
    db.refresh(a)
    # Then 2
    assert isinstance(exc.value.orig, NotNullViolation)
    # Then 3
    assert exc.value.orig.pgcode == "23502"
    # Then 4
    row = reread(db, a)
    assert row.summary == "Bearing change"
    # Then 5
    assert snap(db, a) == before_a
    # Then 6
    assert written(db) == before


# [claude] MML-INH-36
def test_mml_inh_36__an_update_sets_updated_at_and_does_not_stamp_updated_by(db, mk_log):
    """MML-INH-36 — an update sets updated_at and does not stamp updated_by.
    Rules: `inherited` R11"""
    a = mk_log()

    result = dao.update(db, db_obj=a, obj_in={"summary": "new"})

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.summary == "new"
    # Then 3
    row = reread(db, a)
    assert row.updated_at is not None
    # Then 4
    row = reread(db, a)
    assert row.updated_by is None


# [claude] MML-INH-37
def test_mml_inh_37__an_update_to_the_current_values_issues_no_update(db, mk_log):
    """MML-INH-37 — an update to the current values issues no UPDATE.
    Rules: `inherited` R11"""
    a = mk_log(cost=Decimal("12.50"))
    before_a = snap(db, a)

    result = dao.update(db, db_obj=a, obj_in={"summary": "Bearing change", "cost": Decimal("12.50")})

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.updated_at is None
    # Then 3
    assert snap(db, a) == before_a


# [claude] MML-INH-38
def test_mml_inh_38__update_is_flushed_not_committed_a_rollback_restores_the_old_value(db, mk_log):
    """MML-INH-38 — update is flushed, not committed: a rollback restores the old value.
    Rules: `inherited` Overview (never commits)"""
    a = mk_log()

    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        sp = db.begin_nested()
        result = dao.update(db, db_obj=a, obj_in={"summary": "new"})

        # Then 1
        assert result is a
        # Then 2
        assert count_rows(db, "id = :id AND summary = :summary", id=a.id, summary="new") == 1
        # Then 3
        sp.rollback()
        db.refresh(a)
        row = reread(db, a)
        assert row.summary == "Bearing change"
        # Then 4
        assert commit_spy.call_count == 0


# [claude] MML-INH-39
def test_mml_inh_39__remove_hard_deletes_the_row_and_nothing_else(db, m1, mk_log):
    """MML-INH-39 — remove hard-deletes the row and nothing else.
    Rules: `inherited` R12"""
    a = mk_log()
    a_id = a.id
    b = mk_log()
    before_b = snap(db, b)
    before_m1 = snap(db, m1)

    result = dao.remove(db, id=a_id)

    # Then 1
    assert result is a
    # Then 2
    assert count_rows(db, "id = :id", id=a_id) == 0
    # Then 3
    assert snap(db, b) == before_b
    # Then 4
    assert snap(db, m1) == before_m1


# [claude] MML-INH-40
def test_mml_inh_40__remove_is_flushed_not_committed_a_rollback_brings_the_row_back(db, mk_log):
    """MML-INH-40 — remove is flushed, not committed: a rollback brings the row back.
    Rules: `inherited` R12, Overview (never commits)"""
    a = mk_log()
    a_id = a.id

    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        sp = db.begin_nested()
        result = dao.remove(db, id=a_id)

        # Then 1
        assert result is a
        # Then 2
        assert count_rows(db, "id = :id", id=a_id) == 0
        # Then 3
        sp.rollback()
        db.refresh(a)
        assert count_rows(db, "id = :id", id=a_id) == 1
        # Then 4
        assert commit_spy.call_count == 0


# [claude] MML-INH-41
def test_mml_inh_41__a_hard_delete_of_a_machine_with_a_log_is_refused(db, m2, mk_log):
    """MML-INH-41 — a hard delete of a machine with a log is refused.
    Rules: `inherited` R14"""
    a = mk_log(machine_id=m2.id)
    before_a = snap(db, a)
    before_m2 = snap(db, m2)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            db.execute(text("DELETE FROM machines WHERE id = :id"), {"id": m2.id})
    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert "machine_maintenance_logs_machine_id_fkey" in str(exc.value.orig)
    # Then 4
    assert snap(db, a) == before_a
    # Then 5
    assert snap(db, m2) == before_m2


# [claude] MML-INH-42
def test_mml_inh_42__a_hard_delete_of_a_machine_with_only_a_soft_deleted_log_is_refused_too(db, m2, mk_log):
    """MML-INH-42 — a hard delete of a machine with only a soft-deleted log is refused too.
    Rules: `inherited` R14"""
    a = mk_log(gone=True, machine_id=m2.id)
    before_a = snap(db, a)
    before_m2 = snap(db, m2)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            db.execute(text("DELETE FROM machines WHERE id = :id"), {"id": m2.id})
    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert snap(db, a) == before_a
    # Then 4
    assert snap(db, m2) == before_m2


# [claude] MML-INH-43
def test_mml_inh_43__a_hard_delete_of_a_profile_named_on_a_log_is_refused(db, p2, mk_log):
    """MML-INH-43 — a hard delete of a profile named on a log is refused.
    Rules: `inherited` R14"""
    a = mk_log(gone=True, deleted_by=p2.id)
    before_a = snap(db, a)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            db.execute(text("DELETE FROM profiles WHERE id = :id"), {"id": p2.id})
    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert "machine_maintenance_logs_deleted_by_fkey" in str(exc.value.orig)
    # Then 4
    assert snap(db, a) == before_a


# [claude] MML-INH-44
def test_mml_inh_44__a_hard_delete_of_the_workspace_removes_its_logs(db, m1, mk_log):
    """MML-INH-44 — a hard delete of the workspace removes its logs.
    Rules: `inherited` R14"""
    w3 = make_workspace(db)
    a = mk_log(workspace_id=w3.id)
    a_id = a.id
    b = mk_log()
    before_b = snap(db, b)
    before_m1 = snap(db, m1)

    db.execute(text("DELETE FROM workspaces WHERE id = :id"), {"id": w3.id})

    # Then 1
    assert count_rows(db, "id = :id", id=a_id) == 0
    # Then 2
    assert snap(db, b) == before_b
    # Then 3
    assert snap(db, m1) == before_m1


# [claude] MML-INH-45
def test_mml_inh_45__hr_15_update_keeps_the_value_as_given_until_a_refresh(db, mk_log):
    """MML-INH-45 — HR-15: update keeps the value as given until a refresh.
    Rules: `inherited` R4"""
    a = mk_log(cost=Decimal("5.00"))

    result = dao.update(db, db_obj=a, obj_in={"cost": Decimal("0.125")})

    # Then 1
    assert result is a
    # Then 2
    assert result.cost == Decimal("0.125")
    # Then 3
    db.refresh(result)
    assert result.cost == Decimal("0.13")
