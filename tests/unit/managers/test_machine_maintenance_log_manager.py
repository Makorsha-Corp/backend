"""Unit tests for app/managers/machine_maintenance_log_manager.py.

Implements tests/unit/managers/machine_maintenance_log_manager.cases.md, one test
per case, in card order. Real Postgres session (`db` fixture). Nothing is patched
except the clock of MMLM-D-19, as Conventions allow.

Normal mode: every test is written from its card and carries a `# [claude] <ID>`
comment. Row names of the cards are the lower-case names here (M1 -> m1, `F1.id`
-> `f1.id`, A -> a); `# Then N` marks the checks of the card's Then line N.
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`)
import warnings
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException
from psycopg2.errors import ForeignKeyViolation
from pydantic import ValidationError
from sqlalchemy import event, func, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import DataError, IntegrityError

from app.managers.machine_maintenance_log_manager import (
    machine_maintenance_log_manager,
)
from app.models.enums import MaintenanceTypeEnum
from app.models.factory import Factory
from app.models.machine import Machine
from app.models.machine_activity_event import MachineActivityEvent
from app.models.machine_maintenance_log import MachineMaintenanceLog
from app.schemas.machine_maintenance_log import (
    MachineMaintenanceLogCreate,
    MachineMaintenanceLogResponse,
    MachineMaintenanceLogUpdate,
)
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "M = the singleton machine_maintenance_log_manager" (a module-level name, not a fixture)
M = machine_maintenance_log_manager

# Convention "LC, LU, LR"
LC = MachineMaintenanceLogCreate
LU = MachineMaintenanceLogUpdate
LR = MachineMaintenanceLogResponse

REPAIR = MaintenanceTypeEnum.REPAIR

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999

D1 = date(2026, 3, 1)
D2 = date(2026, 3, 2)
D3 = date(2026, 3, 3)
T0 = datetime(2020, 1, 2, 3, 4, 5)  # noqa: DTZ001
NOW = datetime(2031, 5, 6, 7, 8, 9)  # noqa: DTZ001


def _add(db, row):
    db.add(row)
    db.flush()
    return row


# --------------------------------------------------------------------------- #
# Conventions -> fixtures (the standing rows). Each fixture depends on the one
# before it, so the rows are inserted in the order Conventions list them.
# --------------------------------------------------------------------------- #

@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


# U1 = created_by of every Given log; U2 = the acting user; U3 = an earlier editor
@pytest.fixture
def u1(db, w2):
    return make_profile(db)


@pytest.fixture
def u2(db, u1):
    return make_profile(db)


@pytest.fixture
def u3(db, u2):
    return make_profile(db)


def _factory(db, ws, name, abbreviation, **but):
    return _add(db, Factory(workspace_id=ws.id, name=name, abbreviation=abbreviation, **but))


@pytest.fixture
def f1(db, w1, u3):
    return _factory(db, w1, "Factory One", "F1")


# Convention: FD has is_deleted True, is_active stays True
@pytest.fixture
def fd(db, w1, f1):
    return _factory(db, w1, "Old Plant", "OP", is_deleted=True)


@pytest.fixture
def fi(db, w1, fd):
    return _factory(db, w1, "Idle Plant", "IP", is_active=False)


@pytest.fixture
def f9(db, w2, fi):
    return _factory(db, w2, "Factory Nine", "F9")


def _machine(db, ws, factory, name, **but):
    return _add(db, Machine(workspace_id=ws.id, factory_id=factory.id, name=name, is_running=False, **but))


@pytest.fixture
def m1(db, w1, f1, f9):
    return _machine(db, w1, f1, "Press 1")


@pytest.fixture
def m2(db, w1, f1, m1):
    return _machine(db, w1, f1, "Press 2")


# Convention: MD is soft-deleted
@pytest.fixture
def md(db, w1, f1, m2):
    return _machine(db, w1, f1, "Press 4", is_deleted=True, is_active=False)


# Convention: MA is only deactivated
@pytest.fixture
def ma(db, w1, f1, md):
    return _machine(db, w1, f1, "Idle Press", is_active=False)


# Convention: MF is live, in a soft-deleted factory
@pytest.fixture
def mf(db, w1, fd, ma):
    return _machine(db, w1, fd, "Lost Press")


# Convention: MG is live, in an only deactivated factory
@pytest.fixture
def mg(db, w1, fi, mf):
    return _machine(db, w1, fi, "Quiet Press")


@pytest.fixture
def m9(db, w2, f9, mg):
    return _machine(db, w2, f9, "Far Press")


# Conventions "Standing rows": in every test, no Given line needed
@pytest.fixture(autouse=True)
def standing_rows(m9):
    pass


# --------------------------------------------------------------------------- #
# Conventions -> "Given rows" (each builder inserts ONE row and flushes, so ids
# rise in the order the Given lines are written; keyword arguments are the
# columns a card's "but" changes)
# --------------------------------------------------------------------------- #

# Convention "The same as M1 / M9, but ...": workspace and factory of that machine, then the columns named
def same_machine(db, base, name, **but):
    fields = {"workspace_id": base.workspace_id, "factory_id": base.factory_id, "name": name, "is_running": False}
    fields.update(but)
    return _add(db, Machine(**fields))


# Convention "The same as F1, but ..."
def same_factory(db, base, name, abbreviation, **but):
    return _add(db, Factory(workspace_id=base.workspace_id, name=name, abbreviation=abbreviation, **but))


# Convention "log", with `gone=True` for the card word "gone"; refreshed, so cost holds the stored form
@pytest.fixture
def mk_log(db, w1, m1, u1):
    def _mk(gone=False, **but):
        fields = {
            "workspace_id": w1.id, "machine_id": m1.id, "maintenance_type": REPAIR,
            "maintenance_date": D1, "summary": "Bearing change", "created_by": u1.id,
        }
        if gone:
            fields.update(is_deleted=True, is_active=False, deleted_at=T0, deleted_by=u1.id)
        fields.update(but)
        row = _add(db, MachineMaintenanceLog(**fields))
        db.refresh(row)
        return row
    return _mk


# Convention "pending log": added, never flushed
@pytest.fixture
def mk_pending(db, w1, m1):
    def _mk():
        q = MachineMaintenanceLog(
            workspace_id=w1.id, machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Pending",
        )
        db.add(q)
        return q
    return _mk


# Convention "bulk101": 101 logs built with add_all
@pytest.fixture
def bulk101(db, w1, m1, u1):
    def _mk():
        rows = [
            MachineMaintenanceLog(
                workspace_id=w1.id, machine_id=m1.id, maintenance_type=REPAIR,
                maintenance_date=date(2025, 1, 1) + timedelta(days=k), summary="Bearing change", created_by=u1.id,
            )
            for k in range(101)
        ]
        db.add_all(rows)
        db.flush()
        return rows
    return _mk


# --------------------------------------------------------------------------- #
# Conventions -> "Named checks"
# --------------------------------------------------------------------------- #

_TABLES = {
    "machine_maintenance_logs": MachineMaintenanceLog.__table__,
    "machine_activity_events": MachineActivityEvent.__table__,
}


def _id_of(row):
    """Primary key of a row, without touching its (possibly expired) attributes."""
    return sa_inspect(row).identity[0]


# Convention "re-read X"
def reread(db, row):
    model, row_id = type(row), _id_of(row)
    db.expire_all()
    return db.execute(select(model).where(model.id == row_id)).scalar_one()


def _columns_of(db, row, leave_out):
    table = type(row).__table__
    found = db.execute(select(table).where(table.c.id == _id_of(row))).mappings().one()
    return {column: value for column, value in found.items() if column not in leave_out}


# Convention "unchanged(X)": the snapshot, read from the table, leaves the instance as it is
def snap_before(db, row, *leave_out):
    return _columns_of(db, row, leave_out)


# Convention "unchanged(X)": after re-read, every column of X; leave_out = "except c, ..."
def snap(db, row, *leave_out):
    db.expire_all()
    return _columns_of(db, row, leave_out)


# Convention "count:" lines: rows of the named table in all workspaces, with the filter stated
def count_rows(db, table_name, **filters):
    table = _TABLES[table_name]
    query = select(func.count()).select_from(table)
    for column, value in filters.items():
        query = query.where(table.c[column] == value)
    return db.execute(query).scalar_one()


# Convention "nothing written"
def written(db):
    return {name: count_rows(db, name) for name in _TABLES}


# Convention "events_of(M)": a fresh SELECT, ordered by id
def events_of(db, machine):
    machine_id = _id_of(machine)
    db.expire_all()
    query = select(MachineActivityEvent).where(MachineActivityEvent.machine_id == machine_id)
    return list(db.execute(query.order_by(MachineActivityEvent.id)).scalars())


# Convention "ids(x)": in the order returned
def ids(rows):
    return [r.id for r in rows]


# Convention "Rolled back": a spy wrapping db.commit, still callable, records calls
def commit_spy(db, monkeypatch):
    spy = Mock(wraps=db.commit)
    monkeypatch.setattr(db, "commit", spy)
    return spy


# Convention "sql_log": a before_cursor_execute listener on db.connection(); removed after the call
@contextmanager
def record_sql(db):
    connection = db.connection()
    sql_log = []

    def _record(conn, cursor, statement, parameters, context, executemany):
        sql_log.append(statement)

    event.listen(connection, "before_cursor_execute", _record)
    try:
        yield sql_log
    finally:
        event.remove(connection, "before_cursor_execute", _record)


# Convention "sql": the last entry containing `FROM machine_maintenance_logs`
def last_sql(sql_log):
    return [statement for statement in sql_log if "FROM machine_maintenance_logs" in statement][-1]


# Convention "order_part": the text of sql after ORDER BY, "" when there is none
def order_part_of(sql):
    return sql.split("ORDER BY", 1)[1] if "ORDER BY" in sql else ""


# --------------------------------------------------------------------------- #
# The cases
# --------------------------------------------------------------------------- #

# [claude] MMLM-C-01
def test_mmlm_c_01__a_log_with_all_six_fields_is_stored(db, w1, u2, m1):
    """MMLM-C-01 — a log with all six fields is stored.
    Rules: `create_log` R5, `create_log` Returns"""
    result = M.create_log(db, log_data=LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("4000.50"), performed_by="Rahim"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert isinstance(result, MachineMaintenanceLog)
    # Then 2
    assert result.id is not None
    # Then 3
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.machine_id == m1.id
    assert row.maintenance_type == REPAIR
    assert row.maintenance_date == D1
    # Then 4
    row = reread(db, result)
    assert row.summary == "Bearing change"
    assert row.cost == Decimal("4000.50")
    assert row.performed_by == "Rahim"
    # Then 5
    row = reread(db, result)
    assert row.created_by == u2.id
    assert row.created_at is not None
    # Then 6
    row = reread(db, result)
    assert row.is_active is True
    assert row.is_deleted is False
    # Then 7
    row = reread(db, result)
    assert row.updated_at is None
    assert row.updated_by is None
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 8
    assert count_rows(db, "machine_maintenance_logs") == 1


# [claude] MMLM-C-02
def test_mmlm_c_02__cost_and_performed_by_omitted_are_null(db, w1, u2, m1):
    """MMLM-C-02 — cost and performed_by omitted are NULL.
    Rules: `create_log` R5"""
    result = M.create_log(db, log_data=LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.cost is None
    assert row.performed_by is None


# [claude] MMLM-C-03
def test_mmlm_c_03__the_service_s_keyword_call_works(db, w1, u2, m1):
    """MMLM-C-03 — the service's keyword call works.
    Rules: `create_log` R5"""
    result = M.create_log(session=db, log_data=LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.created_by == u2.id
    assert row.workspace_id == w1.id


# [claude] MMLM-C-04
def test_mmlm_c_04__workspace_comes_from_the_argument_keys_in_the_body_are_dropped(db, w1, w2, u2, u3, m1):
    """MMLM-C-04 — workspace comes from the argument: keys in the body are dropped.
    Rules: `create_log` R5, `create_log` Inputs"""
    result = M.create_log(db, log_data=LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", workspace_id=w2.id, created_by=u3.id, is_deleted=True), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.created_by == u2.id
    assert row.is_deleted is False
    # Then 3
    assert count_rows(db, "machine_maintenance_logs", workspace_id=w2.id) == 0


# [claude] MMLM-C-05
def test_mmlm_c_05__a_second_log_on_the_same_machine_date_and_type_is_stored_no_duplicate(db, w1, u2, m1, mk_log):
    """MMLM-C-05 — a second log on the same machine, date and type is stored: no duplicate check.
    Rules: `create_log` R6"""
    a = mk_log()
    before_a = snap_before(db, a)
    result = M.create_log(db, log_data=LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id != a.id
    # Then 2
    assert count_rows(db, "machine_maintenance_logs", machine_id=m1.id) == 2
    # Then 3
    assert snap(db, a) == before_a


# [claude] MMLM-C-06
def test_mmlm_c_06__an_unknown_machine_gets_the_404(db, w1, u2):
    """MMLM-C-06 — an unknown machine gets the 404.
    Rules: `create_log` R1, `create_log` Errors row 1"""
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_log(db, log_data=LC(machine_id=MISSING, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine with ID 999999999 not found"
    # Then 4
    assert written(db) == before


# [claude] MMLM-C-07
def test_mmlm_c_07__machine_id_0_gets_the_404(db, w1, u2):
    """MMLM-C-07 — machine id 0 gets the 404.
    Rules: `create_log` R1, `create_log` Errors row 1"""
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_log(db, log_data=LC(machine_id=0, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine with ID 0 not found"
    # Then 4
    assert written(db) == before


# [claude] MMLM-C-08
def test_mmlm_c_08__a_negative_machine_id_gets_the_404(db, w1, u2):
    """MMLM-C-08 — a negative machine id gets the 404.
    Rules: `create_log` R1, `create_log` Errors row 1"""
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_log(db, log_data=LC(machine_id=-1, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine with ID -1 not found"
    # Then 4
    assert written(db) == before


# [claude] MMLM-C-09
def test_mmlm_c_09__another_workspace_s_machine_gets_the_same_404_and_no_write_in_either_w(db, w1, u2, m9):
    """MMLM-C-09 — another workspace's machine gets the same 404 and no write in either workspace.
    Rules: `create_log` R1, `create_log` Errors row 1"""
    before_m9 = snap_before(db, m9)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_log(db, log_data=LC(machine_id=m9.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Machine with ID {m9.id} not found"
    # Then 4
    assert written(db) == before
    # Then 5
    assert len(events_of(db, m9)) == 0
    # Then 6
    assert snap(db, m9) == before_m9


# [claude] MMLM-C-10
def test_mmlm_c_10__a_machine_of_w1_asked_for_from_w2_gets_the_same_404(db, w2, u2, m1):
    """MMLM-C-10 — a machine of W1 asked for from W2 gets the same 404.
    Rules: `create_log` R1, `create_log` Errors row 1"""
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_log(db, log_data=LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=w2.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Machine with ID {m1.id} not found"
    # Then 4
    assert written(db) == before


# [claude] MMLM-C-11
def test_mmlm_c_11__a_soft_deleted_machine_of_another_workspace_cannot_be_told_from_a_miss(db, w1, u2, m9):
    """MMLM-C-11 — a soft-deleted machine of another workspace cannot be told from a missing one: 404, not 400.
    Rules: `create_log` R1, `create_log` Errors row 1"""
    m9d = same_machine(db, m9, "Far Gone", is_deleted=True, is_active=False)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_log(db, log_data=LC(machine_id=m9d.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Machine with ID {m9d.id} not found"
    # Then 4
    assert written(db) == before


# [claude] MMLM-C-12
def test_mmlm_c_12__a_soft_deleted_machine_is_refused(db, w1, u2, md):
    """MMLM-C-12 — a soft-deleted machine is refused.
    Rules: `create_log` R2, `create_log` Errors row 2"""
    before_md = snap_before(db, md)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_log(db, log_data=LC(machine_id=md.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot create maintenance log for a deleted machine"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, md) == before_md


# [claude] MMLM-C-13
def test_mmlm_c_13__a_soft_deleted_machine_still_marked_active_is_refused(db, w1, u2, m1):
    """MMLM-C-13 — a soft-deleted machine still marked active is refused.
    Rules: `create_log` R2, `create_log` Errors row 2"""
    mda = same_machine(db, m1, "Half Gone", is_deleted=True, is_active=True)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_log(db, log_data=LC(machine_id=mda.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot create maintenance log for a deleted machine"
    # Then 4
    assert written(db) == before


# [claude] MMLM-C-14
def test_mmlm_c_14__a_soft_deleted_machine_in_a_soft_deleted_factory_gets_the_same_refusal(db, w1, u2, fd, m1):
    """MMLM-C-14 — a soft-deleted machine in a soft-deleted factory gets the same refusal.
    Rules: `create_log` R2, `create_log` Errors row 2"""
    mdf = same_machine(db, m1, "Both Gone", factory_id=fd.id, is_deleted=True, is_active=False)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_log(db, log_data=LC(machine_id=mdf.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot create maintenance log for a deleted machine"
    # Then 4
    assert written(db) == before


# [claude] MMLM-C-15
@pytest.mark.xfail(strict=True, reason="BUG-1154: A maintenance log can be added to a machine of a soft-deleted factory")
def test_mmlm_c_15__a_live_machine_in_a_soft_deleted_factory_is_refused_like_a_deleted_mac(db, w1, u2, mf):
    """MMLM-C-15 — a live machine in a soft-deleted factory is refused like a deleted machine.
    Rules: `create_log` R3 [BUG-1154], `create_log` Errors row 2"""
    before_mf = snap_before(db, mf)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_log(db, log_data=LC(machine_id=mf.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot create maintenance log for a deleted machine"
    # Then 4
    assert written(db) == before
    # Then 5
    assert len(events_of(db, mf)) == 0
    # Then 6
    assert snap(db, mf) == before_mf


# [claude] MMLM-C-16
@pytest.mark.xfail(strict=True, reason="BUG-1154: A maintenance log can be added to a machine of a soft-deleted factory")
def test_mmlm_c_16__a_machine_marked_inactive_in_a_soft_deleted_factory_is_refused_too(db, w1, u2, fd, m1):
    """MMLM-C-16 — a machine marked inactive in a soft-deleted factory is refused too.
    Rules: `create_log` R3 [BUG-1154], `create_log` Errors row 2"""
    mfi = same_machine(db, m1, "Dim Press", factory_id=fd.id, is_active=False)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_log(db, log_data=LC(machine_id=mfi.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot create maintenance log for a deleted machine"
    # Then 4
    assert written(db) == before


# [claude] MMLM-C-17
@pytest.mark.xfail(strict=True, reason="BUG-1154: A maintenance log can be added to a machine of a soft-deleted factory")
def test_mmlm_c_17__a_soft_deleted_factory_also_marked_inactive_refuses_too(db, w1, u2, f1, m1):
    """MMLM-C-17 — a soft-deleted factory also marked inactive refuses too.
    Rules: `create_log` R3 [BUG-1154], `create_log` Errors row 2"""
    fx = same_factory(db, f1, "Shut Plant", "SP", is_deleted=True, is_active=False)
    mx = same_machine(db, m1, "Shut Press", factory_id=fx.id)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_log(db, log_data=LC(machine_id=mx.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot create maintenance log for a deleted machine"
    # Then 4
    assert written(db) == before


# [claude] MMLM-C-18
def test_mmlm_c_18__an_inactive_machine_is_accepted_with_its_entry(db, w1, u2, ma):
    """MMLM-C-18 — an inactive machine is accepted, with its entry.
    Rules: `create_log` R4"""
    before_ma = snap_before(db, ma)
    result = M.create_log(db, log_data=LC(machine_id=ma.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.machine_id == ma.id
    assert row.is_active is True
    assert row.is_deleted is False
    # Then 3
    evs = events_of(db, ma)
    assert len(evs) == 1
    # Then 4
    assert evs[0].event_type == "maintenance_logged"
    assert evs[0].description == "Maintenance logged: Bearing change"
    assert evs[0].performed_by == u2.id
    assert evs[0].workspace_id == w1.id
    assert evs[0].machine_id == ma.id
    # Then 5
    assert snap(db, ma) == before_ma


# [claude] MMLM-C-19
def test_mmlm_c_19__a_machine_in_an_inactive_factory_is_accepted_with_its_entry(db, w1, u2, mg):
    """MMLM-C-19 — a machine in an inactive factory is accepted, with its entry.
    Rules: `create_log` R4"""
    before_mg = snap_before(db, mg)
    result = M.create_log(db, log_data=LC(machine_id=mg.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.machine_id == mg.id
    assert row.is_active is True
    assert row.is_deleted is False
    # Then 3
    evs = events_of(db, mg)
    assert len(evs) == 1
    # Then 4
    assert evs[0].event_type == "maintenance_logged"
    assert evs[0].description == "Maintenance logged: Bearing change"
    assert evs[0].performed_by == u2.id
    assert evs[0].workspace_id == w1.id
    assert evs[0].machine_id == mg.id
    # Then 5
    assert snap(db, mg) == before_mg


# [claude] MMLM-C-20
def test_mmlm_c_20__an_inactive_machine_in_an_inactive_factory_is_accepted(db, w1, u2, fi, m1):
    """MMLM-C-20 — an inactive machine in an inactive factory is accepted.
    Rules: `create_log` R4"""
    mag = same_machine(db, m1, "Dim Quiet", factory_id=fi.id, is_active=False)
    result = M.create_log(db, log_data=LC(machine_id=mag.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.machine_id == mag.id
    # Then 3
    evs = events_of(db, mag)
    assert len(evs) == 1


# [claude] MMLM-C-21
def test_mmlm_c_21__the_returned_object_keeps_cost_as_given_until_a_refresh(db, w1, u2, m1):
    """MMLM-C-21 — the returned object keeps cost as given until a refresh.
    Rules: `create_log` R7"""
    result = M.create_log(db, log_data=LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("5.000")), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert str(result.cost) == "5.000"
    # Then 2
    db.refresh(result)
    # Then 3
    assert str(result.cost) == "5.00"


# [claude] MMLM-C-22
@pytest.mark.xfail(strict=True, reason="BUG-1155: Blank maintenance log summaries accepted; stored untrimmed")
def test_mmlm_c_22__a_padded_summary_is_stored_and_repeated_trimmed(db, w1, u2, m1):
    """MMLM-C-22 — a padded summary is stored and repeated trimmed.
    Rules: `create_log` R8 [BUG-1155]"""
    result = M.create_log(db, log_data=LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="  pad  "), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.summary == "pad"
    # Then 3
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 4
    assert evs[0].event_type == "maintenance_logged"
    assert evs[0].description == "Maintenance logged: pad"
    assert evs[0].performed_by == u2.id
    assert evs[0].workspace_id == w1.id
    assert evs[0].machine_id == m1.id


# [claude] MMLM-C-23
@pytest.mark.xfail(strict=True, reason="BUG-1155: Blank maintenance log summaries accepted; stored untrimmed")
def test_mmlm_c_23__trimming_keeps_inner_whitespace(db, w1, u2, m1):
    """MMLM-C-23 — trimming keeps inner whitespace.
    Rules: `create_log` R8 [BUG-1155]"""
    result = M.create_log(db, log_data=LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="  pad  line  "), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.summary == "pad  line"


# [claude] MMLM-C-24
@pytest.mark.xfail(strict=True, reason="BUG-1155: Blank maintenance log summaries accepted; stored untrimmed")
def test_mmlm_c_24__tabs_and_new_lines_around_a_summary_are_trimmed_too(db, w1, u2, m1):
    """MMLM-C-24 — tabs and new lines around a summary are trimmed too.
    Rules: `create_log` R8 [BUG-1155]"""
    result = M.create_log(db, log_data=LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="\tpad\n"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.summary == "pad"


# [claude] MMLM-C-25
def test_mmlm_c_25__inner_whitespace_of_a_summary_with_no_padding_is_kept_as_typed(db, w1, u2, m1):
    """MMLM-C-25 — inner whitespace of a summary with no padding is kept as typed.
    Rules: `create_log` R8"""
    result = M.create_log(db, log_data=LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing  change"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    row = reread(db, result)
    assert row.summary == "Bearing  change"
    # Then 2
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 3
    assert evs[0].event_type == "maintenance_logged"
    assert evs[0].description == "Maintenance logged: Bearing  change"
    assert evs[0].performed_by == u2.id
    assert evs[0].workspace_id == w1.id
    assert evs[0].machine_id == m1.id


# [claude] MMLM-C-26
def test_mmlm_c_26__a_one_character_summary_is_accepted_the_other_side_of_empty(db, w1, u2, m1):
    """MMLM-C-26 — a one-character summary is accepted: the other side of empty.
    Rules: `create_log` R8"""
    result = M.create_log(db, log_data=LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="a"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    row = reread(db, result)
    assert row.summary == "a"


# [claude] MMLM-C-27
@pytest.mark.xfail(strict=True, reason="BUG-1155: Blank maintenance log summaries accepted; stored untrimmed")
def test_mmlm_c_27__an_empty_summary_is_refused_by_the_schema(db, m1):
    """MMLM-C-27 — an empty summary is refused by the schema.
    Rules: `create_log` R8 [BUG-1155], `create_log` Errors row 3"""
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="")

    # Then 2
    assert written(db) == before


# [claude] MMLM-C-28
@pytest.mark.xfail(strict=True, reason="BUG-1155: Blank maintenance log summaries accepted; stored untrimmed")
def test_mmlm_c_28__a_whitespace_only_summary_is_refused_by_the_schema(db, m1):
    """MMLM-C-28 — a whitespace-only summary is refused by the schema.
    Rules: `create_log` R8 [BUG-1155], `create_log` Errors row 3"""
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="   ")

    # Then 2
    assert written(db) == before


# [claude] MMLM-C-29
@pytest.mark.xfail(strict=True, reason="BUG-1155: Blank maintenance log summaries accepted; stored untrimmed")
def test_mmlm_c_29__a_summary_of_tabs_and_new_lines_is_refused_by_the_schema(db, m1):
    """MMLM-C-29 — a summary of tabs and new lines is refused by the schema.
    Rules: `create_log` R8 [BUG-1155], `create_log` Errors row 3"""
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="\t\n ")

    # Then 2
    assert written(db) == before


# [claude] MMLM-C-30
def test_mmlm_c_30__a_summary_of_100_000_characters_is_stored_and_copied_into_the_entry(db, w1, u2, m1):
    """MMLM-C-30 — a summary of 100 000 characters is stored and copied into the entry.
    Rules: `create_log` R8b"""
    result = M.create_log(db, log_data=LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="S" * 100000), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    row = reread(db, result)
    assert row.summary == "S" * 100000
    # Then 2
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 3
    assert evs[0].description == "Maintenance logged: " + "S" * 100000


# [claude] MMLM-C-31
@pytest.mark.xfail(strict=True, reason="BUG-1156: Maintenance log performed_by untrimmed, blank counts as a value, over-long crashes")
def test_mmlm_c_31__a_padded_performed_by_is_stored_trimmed(db, w1, u2, m1):
    """MMLM-C-31 — a padded performed_by is stored trimmed.
    Rules: `create_log` R8a [BUG-1156]"""
    result = M.create_log(db, log_data=LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", performed_by="  Rahim  "), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.performed_by == "Rahim"


# [claude] MMLM-C-32
@pytest.mark.xfail(strict=True, reason="BUG-1156: Maintenance log performed_by untrimmed, blank counts as a value, over-long crashes")
def test_mmlm_c_32__an_empty_performed_by_is_stored_as_null(db, w1, u2, m1):
    """MMLM-C-32 — an empty performed_by is stored as NULL.
    Rules: `create_log` R8a [BUG-1156]"""
    result = M.create_log(db, log_data=LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", performed_by=""), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.performed_by is None


# [claude] MMLM-C-33
@pytest.mark.xfail(strict=True, reason="BUG-1156: Maintenance log performed_by untrimmed, blank counts as a value, over-long crashes")
def test_mmlm_c_33__a_whitespace_only_performed_by_is_stored_as_null(db, w1, u2, m1):
    """MMLM-C-33 — a whitespace-only performed_by is stored as NULL.
    Rules: `create_log` R8a [BUG-1156]"""
    result = M.create_log(db, log_data=LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", performed_by="   "), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.performed_by is None


# [claude] MMLM-C-34
def test_mmlm_c_34__a_plain_performed_by_is_stored_as_typed_inner_whitespace_kept(db, w1, u2, m1):
    """MMLM-C-34 — a plain performed_by is stored as typed, inner whitespace kept.
    Rules: `create_log` R8a"""
    result = M.create_log(db, log_data=LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", performed_by="Rahim  Uddin"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    row = reread(db, result)
    assert row.performed_by == "Rahim  Uddin"


# [claude] MMLM-C-35
def test_mmlm_c_35__performed_by_of_255_characters_is_stored(db, w1, u2, m1):
    """MMLM-C-35 — performed_by of 255 characters is stored.
    Rules: `create_log` R9"""
    result = M.create_log(db, log_data=LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", performed_by="x" * 255), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    row = reread(db, result)
    assert row.performed_by == "x" * 255


# [claude] MMLM-C-36
@pytest.mark.xfail(strict=True, reason="BUG-1156: Maintenance log performed_by untrimmed, blank counts as a value, over-long crashes")
def test_mmlm_c_36__performed_by_of_256_characters_is_refused_by_the_schema(db, m1):
    """MMLM-C-36 — performed_by of 256 characters is refused by the schema.
    Rules: `create_log` R9a [BUG-1156], `create_log` Errors row 3"""
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", performed_by="x" * 256)

    # Then 2
    assert written(db) == before


# [claude] MMLM-C-37
@pytest.mark.xfail(strict=True, reason="BUG-1156: Maintenance log performed_by untrimmed, blank counts as a value, over-long crashes")
def test_mmlm_c_37__256_characters_inside_surrounding_spaces_are_refused_the_limit_is_on_t(db, m1):
    """MMLM-C-37 — 256 characters inside surrounding spaces are refused: the limit is on the trimmed value.
    Rules: `create_log` R9a [BUG-1156], `create_log` Errors row 3"""
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", performed_by=" " + "x" * 256 + " ")

    # Then 2
    assert written(db) == before


# [claude] MMLM-C-38
@pytest.mark.xfail(strict=True, reason="BUG-1156: Maintenance log performed_by untrimmed, blank counts as a value, over-long crashes")
def test_mmlm_c_38__255_characters_inside_surrounding_spaces_are_accepted_and_stored_trimm(db, w1, u2, m1):
    """MMLM-C-38 — 255 characters inside surrounding spaces are accepted and stored trimmed.
    Rules: `create_log` R9a [BUG-1156]"""
    result = M.create_log(db, log_data=LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", performed_by=" " + "x" * 255 + " "), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.performed_by == "x" * 255


# [claude] MMLM-C-39
def test_mmlm_c_39__cost_0_is_accepted_and_stored_as_0_00_zero_is_a_value_not_an_empty_fie(db, w1, u2, m1):
    """MMLM-C-39 — cost 0 is accepted and stored as 0.00: zero is a value, not an empty field.
    Rules: `create_log` R11"""
    result = M.create_log(db, log_data=LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=0), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert str(row.cost) == "0.00"


# [claude] MMLM-C-40
def test_mmlm_c_40__cost_0_is_accepted_and_stored_as_0_00_minus_zero_passes_the_minimum(db, w1, u2, m1):
    """MMLM-C-40 — cost -0 is accepted and stored as 0.00: minus zero passes the minimum.
    Rules: `create_log` R11"""
    result = M.create_log(db, log_data=LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("-0")), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert str(row.cost) == "0.00"


# [claude] MMLM-C-41
def test_mmlm_c_41__cost_0_01_is_accepted_and_stored_as_0_01_the_smallest_cost_above_zero(db, w1, u2, m1):
    """MMLM-C-41 — cost 0.01 is accepted and stored as 0.01: the smallest cost above zero.
    Rules: `create_log` R11"""
    result = M.create_log(db, log_data=LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("0.01")), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert str(row.cost) == "0.01"


# [claude] MMLM-C-42
def test_mmlm_c_42__cost_5_is_accepted_and_stored_as_5_00_no_decimals(db, w1, u2, m1):
    """MMLM-C-42 — cost 5 is accepted and stored as 5.00: no decimals.
    Rules: `create_log` R12"""
    result = M.create_log(db, log_data=LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=5), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert str(row.cost) == "5.00"


# [claude] MMLM-C-43
def test_mmlm_c_43__cost_5_1_is_accepted_and_stored_as_5_10_one_decimal_as_a_json_number(db, w1, u2, m1):
    """MMLM-C-43 — cost 5.1 is accepted and stored as 5.10: one decimal, as a JSON number.
    Rules: `create_log` R12"""
    result = M.create_log(db, log_data=LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=5.1), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert str(row.cost) == "5.10"


# [claude] MMLM-C-44
def test_mmlm_c_44__cost_5_00_is_accepted_and_stored_as_5_00_two_decimals(db, w1, u2, m1):
    """MMLM-C-44 — cost 5.00 is accepted and stored as 5.00: two decimals.
    Rules: `create_log` R12"""
    result = M.create_log(db, log_data=LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("5.00")), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert str(row.cost) == "5.00"


# [claude] MMLM-C-45
def test_mmlm_c_45__cost_5_000_is_accepted_and_stored_as_5_00_a_trailing_zero_does_not_cou(db, w1, u2, m1):
    """MMLM-C-45 — cost 5.000 is accepted and stored as 5.00: a trailing zero does not count.
    Rules: `create_log` R12"""
    result = M.create_log(db, log_data=LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("5.000")), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert str(row.cost) == "5.00"


# [claude] MMLM-C-46
def test_mmlm_c_46__cost_9999999999999_is_accepted_and_stored_as_9999999999999_00_13_integ(db, w1, u2, m1):
    """MMLM-C-46 — cost 9999999999999 is accepted and stored as 9999999999999.00: 13 integer digits.
    Rules: `create_log` R10"""
    result = M.create_log(db, log_data=LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("9999999999999")), workspace_id=w1.id, user_id=u2.id)  # noqa: FURB157

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert str(row.cost) == "9999999999999.00"


# [claude] MMLM-C-47
def test_mmlm_c_47__cost_9999999999999_99_is_accepted_and_stored_as_9999999999999_99_the_c(db, w1, u2, m1):
    """MMLM-C-47 — cost 9999999999999.99 is accepted and stored as 9999999999999.99: the column's limit.
    Rules: `create_log` R10"""
    result = M.create_log(db, log_data=LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("9999999999999.99")), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert str(row.cost) == "9999999999999.99"


# [claude] MMLM-C-48
def test_mmlm_c_48__cost_9999999999999_990_is_accepted_and_stored_as_9999999999999_99_the(db, w1, u2, m1):
    """MMLM-C-48 — cost 9999999999999.990 is accepted and stored as 9999999999999.99: the limit with a trailing zero.
    Rules: `create_log` R10"""
    result = M.create_log(db, log_data=LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("9999999999999.990")), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert str(row.cost) == "9999999999999.99"


# [claude] MMLM-C-49
@pytest.mark.xfail(strict=True, reason="BUG-1158: Negative maintenance log cost accepted")
def test_mmlm_c_49__cost_5_is_refused_by_the_schema(db, m1):
    """MMLM-C-49 — cost -5 is refused by the schema.
    Rules: `create_log` R11a [BUG-1158], `create_log` Errors row 3"""
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("-5"))  # noqa: FURB157

    # Then 2
    assert written(db) == before


# [claude] MMLM-C-50
@pytest.mark.xfail(strict=True, reason="BUG-1158: Negative maintenance log cost accepted")
def test_mmlm_c_50__cost_0_01_is_refused_by_the_schema(db, m1):
    """MMLM-C-50 — cost -0.01 is refused by the schema.
    Rules: `create_log` R11a [BUG-1158], `create_log` Errors row 3"""
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("-0.01"))

    # Then 2
    assert written(db) == before


# [claude] MMLM-C-51
@pytest.mark.xfail(strict=True, reason="BUG-1157: Maintenance log cost with too many digits or decimals accepted; the activity entry records it as typed")
def test_mmlm_c_51__cost_10000000000000_is_refused_by_the_schema(db, m1):
    """MMLM-C-51 — cost 10000000000000 is refused by the schema.
    Rules: `create_log` R10a [BUG-1157], `create_log` Errors row 3"""
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("10000000000000"))  # noqa: FURB157

    # Then 2
    assert written(db) == before


# [claude] MMLM-C-52
@pytest.mark.xfail(strict=True, reason="BUG-1157: Maintenance log cost with too many digits or decimals accepted; the activity entry records it as typed")
def test_mmlm_c_52__cost_10000000000000_00_is_refused_by_the_schema(db, m1):
    """MMLM-C-52 — cost 10000000000000.00 is refused by the schema.
    Rules: `create_log` R10a [BUG-1157], `create_log` Errors row 3"""
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("10000000000000.00"))

    # Then 2
    assert written(db) == before


# [claude] MMLM-C-53
@pytest.mark.xfail(strict=True, reason="BUG-1157: Maintenance log cost with too many digits or decimals accepted; the activity entry records it as typed")
def test_mmlm_c_53__cost_1e_13_is_refused_by_the_schema(db, m1):
    """MMLM-C-53 — cost 1E+13 is refused by the schema.
    Rules: `create_log` R10a [BUG-1157], `create_log` Errors row 3"""
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("1E+13"))

    # Then 2
    assert written(db) == before


# [claude] MMLM-C-54
@pytest.mark.xfail(strict=True, reason="BUG-1157: Maintenance log cost with too many digits or decimals accepted; the activity entry records it as typed")
def test_mmlm_c_54__cost_1e20_is_refused_by_the_schema(db, m1):
    """MMLM-C-54 — cost 1e20 is refused by the schema.
    Rules: `create_log` R10a [BUG-1157], `create_log` Errors row 3"""
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("1e20"))

    # Then 2
    assert written(db) == before


# [claude] MMLM-C-55
@pytest.mark.xfail(strict=True, reason="BUG-1157: Maintenance log cost with too many digits or decimals accepted; the activity entry records it as typed")
def test_mmlm_c_55__cost_5_001_is_refused_by_the_schema(db, m1):
    """MMLM-C-55 — cost 5.001 is refused by the schema.
    Rules: `create_log` R12 [BUG-1157], `create_log` Errors row 3"""
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("5.001"))

    # Then 2
    assert written(db) == before


# [claude] MMLM-C-56
@pytest.mark.xfail(strict=True, reason="BUG-1157: Maintenance log cost with too many digits or decimals accepted; the activity entry records it as typed")
def test_mmlm_c_56__cost_5_0010_is_refused_by_the_schema(db, m1):
    """MMLM-C-56 — cost 5.0010 is refused by the schema.
    Rules: `create_log` R12 [BUG-1157], `create_log` Errors row 3"""
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("5.0010"))

    # Then 2
    assert written(db) == before


# [claude] MMLM-C-57
@pytest.mark.xfail(strict=True, reason="BUG-1157: Maintenance log cost with too many digits or decimals accepted; the activity entry records it as typed")
def test_mmlm_c_57__cost_0_125_is_refused_by_the_schema(db, m1):
    """MMLM-C-57 — cost 0.125 is refused by the schema.
    Rules: `create_log` R12 [BUG-1157], `create_log` Errors row 3"""
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("0.125"))

    # Then 2
    assert written(db) == before


# [claude] MMLM-C-58
@pytest.mark.xfail(strict=True, reason="BUG-1157: Maintenance log cost with too many digits or decimals accepted; the activity entry records it as typed")
def test_mmlm_c_58__cost_1e_7_is_refused_by_the_schema(db, m1):
    """MMLM-C-58 — cost 1E-7 is refused by the schema.
    Rules: `create_log` R12 [BUG-1157], `create_log` Errors row 3"""
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("1E-7"))

    # Then 2
    assert written(db) == before


# [claude] MMLM-C-59
@pytest.mark.xfail(strict=True, reason="BUG-1157: Maintenance log cost with too many digits or decimals accepted; the activity entry records it as typed")
def test_mmlm_c_59__cost_9999999999999_995_is_refused_by_the_schema(db, m1):
    """MMLM-C-59 — cost 9999999999999.995 is refused by the schema.
    Rules: `create_log` R12 [BUG-1157], `create_log` Errors row 3"""
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("9999999999999.995"))

    # Then 2
    assert written(db) == before


# [claude] MMLM-C-60
def test_mmlm_c_60__a_row_already_negative_stays_readable_through_the_response_schema(db, mk_log):
    """MMLM-C-60 — a row already negative stays readable through the response schema.
    Rules: `create_log` R11a"""
    a = mk_log(cost=Decimal("-5.00"))
    before_a = snap_before(db, a)
    result = LR.model_validate(a, from_attributes=True)

    # Then 1
    assert result.cost == Decimal("-5.00")
    # Then 2
    assert snap(db, a) == before_a


# [claude] MMLM-C-61
def test_mmlm_c_61__a_row_already_blank_or_padded_stays_readable_through_the_response_sche(db, mk_log):
    """MMLM-C-61 — a row already blank or padded stays readable through the response schema.
    Rules: `create_log` FU-2"""
    a = mk_log(summary="   ", performed_by="  Rahim  ")
    result = LR.model_validate(a, from_attributes=True)

    # Then 1
    assert result.summary == "   "
    # Then 2
    assert result.performed_by == "  Rahim  "


# [claude] MMLM-C-62
def test_mmlm_c_62__a_date_in_1900_is_stored_no_bound(db, w1, u2, m1):
    """MMLM-C-62 — a date in 1900 is stored: no bound.
    Rules: `create_log` R13"""
    result = M.create_log(db, log_data=LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=date(1900, 1, 1), summary="Bearing change"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    row = reread(db, result)
    assert row.maintenance_date == date(1900, 1, 1)
    # Then 2
    evs = events_of(db, m1)
    assert len(evs) == 1


# [claude] MMLM-C-63
def test_mmlm_c_63__a_date_in_2099_is_stored_no_bound(db, w1, u2, m1):
    """MMLM-C-63 — a date in 2099 is stored: no bound.
    Rules: `create_log` R13"""
    result = M.create_log(db, log_data=LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=date(2099, 1, 1), summary="Bearing change"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    row = reread(db, result)
    assert row.maintenance_date == date(2099, 1, 1)
    # Then 2
    evs = events_of(db, m1)
    assert len(evs) == 1


# [claude] MMLM-C-64
def test_mmlm_c_64__cost_nan_is_refused_by_the_schema_not_a_number(db, m1):
    """MMLM-C-64 — cost NaN is refused by the schema: not a number.
    Rules: `create_log` Inputs"""
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("NaN"))

    # Then 2
    assert written(db) == before


# [claude] MMLM-C-65
def test_mmlm_c_65__cost_infinity_is_refused_by_the_schema_infinity(db, m1):
    """MMLM-C-65 — cost Infinity is refused by the schema: infinity.
    Rules: `create_log` Inputs"""
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("Infinity"))

    # Then 2
    assert written(db) == before


# [claude] MMLM-C-66
def test_mmlm_c_66__a_type_name_that_is_no_member_is_refused_by_the_schema(db, m1):
    """MMLM-C-66 — a type name that is no member is refused by the schema.
    Rules: `create_log` Inputs"""
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LC(machine_id=m1.id, maintenance_type="BOGUS", maintenance_date=D1, summary="Bearing change")

    # Then 2
    assert written(db) == before


# [claude] MMLM-C-67
def test_mmlm_c_67__machine_id_is_required_by_the_schema(db):
    """MMLM-C-67 — machine_id is required by the schema.
    Rules: `create_log` Inputs"""
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LC(maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change")

    # Then 2
    assert written(db) == before


# [claude] MMLM-C-68
def test_mmlm_c_68__maintenance_type_is_required_by_the_schema(db, m1):
    """MMLM-C-68 — maintenance_type is required by the schema.
    Rules: `create_log` Inputs"""
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LC(machine_id=m1.id, maintenance_date=D1, summary="Bearing change")

    # Then 2
    assert written(db) == before


# [claude] MMLM-C-69
def test_mmlm_c_69__maintenance_date_is_required_by_the_schema(db, m1):
    """MMLM-C-69 — maintenance_date is required by the schema.
    Rules: `create_log` Inputs"""
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LC(machine_id=m1.id, maintenance_type=REPAIR, summary="Bearing change")

    # Then 2
    assert written(db) == before


# [claude] MMLM-C-70
def test_mmlm_c_70__summary_is_required_by_the_schema(db, m1):
    """MMLM-C-70 — summary is required by the schema.
    Rules: `create_log` Inputs"""
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1)

    # Then 2
    assert written(db) == before


# [claude] MMLM-C-71
def test_mmlm_c_71__one_maintenance_logged_entry_with_every_field_cost_and_the_free_text_n(db, w1, u2, m1, m2):
    """MMLM-C-71 — one maintenance_logged entry with every field; cost and the free-text name are not in it.
    Rules: `create_log` R14, `create_log` Side effects"""
    result = M.create_log(db, log_data=LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("4000.50"), performed_by="Rahim"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 3
    assert evs[0].event_type == "maintenance_logged"
    assert evs[0].description == "Maintenance logged: Bearing change"
    assert evs[0].performed_by == u2.id
    assert evs[0].workspace_id == w1.id
    assert evs[0].machine_id == m1.id
    # Then 4
    assert evs[0].metadata_json == {"maintenance_log_id": result.id, "status": "REPAIR"}
    # Then 5
    assert evs[0].created_at is not None
    # Then 6
    assert len(events_of(db, m2)) == 0


# [claude] MMLM-C-72
def test_mmlm_c_72__the_entry_s_performed_by_is_the_acting_user_never_the_free_text_name(db, w1, u3, m1):
    """MMLM-C-72 — the entry's performed_by is the acting user, never the free-text name.
    Rules: `create_log` R14"""
    result = M.create_log(db, log_data=LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", performed_by="Rahim"), workspace_id=w1.id, user_id=u3.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.performed_by == "Rahim"
    assert row.created_by == u3.id
    # Then 3
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 4
    assert evs[0].performed_by == u3.id


# [claude] MMLM-C-73
def test_mmlm_c_73__the_machine_row_is_not_touched(db, w1, u2, m1):
    """MMLM-C-73 — the machine row is not touched.
    Rules: `create_log` Side effects"""
    before_m1 = snap_before(db, m1)
    result = M.create_log(db, log_data=LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert snap(db, m1) == before_m1


# [claude] MMLM-C-74
def test_mmlm_c_74__metadata_status_holds_preventive(db, w1, u2, m1):
    """MMLM-C-74 — metadata status holds PREVENTIVE.
    Rules: `create_log` R15"""
    result = M.create_log(db, log_data=LC(machine_id=m1.id, maintenance_type=MaintenanceTypeEnum.PREVENTIVE, maintenance_date=D1, summary="Bearing change"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 3
    assert evs[0].metadata_json == {"maintenance_log_id": result.id, "status": "PREVENTIVE"}


# [claude] MMLM-C-75
def test_mmlm_c_75__metadata_status_holds_repair(db, w1, u2, m1):
    """MMLM-C-75 — metadata status holds REPAIR.
    Rules: `create_log` R15"""
    result = M.create_log(db, log_data=LC(machine_id=m1.id, maintenance_type=MaintenanceTypeEnum.REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 3
    assert evs[0].metadata_json == {"maintenance_log_id": result.id, "status": "REPAIR"}


# [claude] MMLM-C-76
def test_mmlm_c_76__metadata_status_holds_emergency(db, w1, u2, m1):
    """MMLM-C-76 — metadata status holds EMERGENCY.
    Rules: `create_log` R15"""
    result = M.create_log(db, log_data=LC(machine_id=m1.id, maintenance_type=MaintenanceTypeEnum.EMERGENCY, maintenance_date=D1, summary="Bearing change"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 3
    assert evs[0].metadata_json == {"maintenance_log_id": result.id, "status": "EMERGENCY"}


# [claude] MMLM-C-77
def test_mmlm_c_77__metadata_status_holds_inspection(db, w1, u2, m1):
    """MMLM-C-77 — metadata status holds INSPECTION.
    Rules: `create_log` R15"""
    result = M.create_log(db, log_data=LC(machine_id=m1.id, maintenance_type=MaintenanceTypeEnum.INSPECTION, maintenance_date=D1, summary="Bearing change"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 3
    assert evs[0].metadata_json == {"maintenance_log_id": result.id, "status": "INSPECTION"}


# [claude] MMLM-C-78
def test_mmlm_c_78__a_plain_string_type_gives_the_same_text(db, w1, u2, m1):
    """MMLM-C-78 — a plain string type gives the same text.
    Rules: `create_log` R15"""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        result = M.create_log(db, log_data=LC.model_construct(machine_id=m1.id, maintenance_type="REPAIR", maintenance_date=D1, summary="Bearing change", cost=None, performed_by=None), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    row = reread(db, result)
    assert row.maintenance_type == REPAIR
    # Then 2
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 3
    assert evs[0].metadata_json == {"maintenance_log_id": result.id, "status": "REPAIR"}


# [claude] MMLM-C-79
def test_mmlm_c_79__metadata_status_is_no_machine_status_no_status_event_machine_as_it_was(db, w1, u2, m1):
    """MMLM-C-79 — metadata status is no machine status: no status event, machine as it was.
    Rules: `create_log` R15"""
    before_m1 = snap_before(db, m1)
    result = M.create_log(db, log_data=LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert count_rows(db, "machine_activity_events", event_type="status_updated") == 0
    # Then 3
    assert snap(db, m1) == before_m1


# [claude] MMLM-C-80
def test_mmlm_c_80__an_unknown_user_foreign_key_error_no_log_and_no_entry(db, w1, m1):
    """MMLM-C-80 — an unknown user: foreign key error, no log and no entry.
    Rules: `create_log` R16, `create_log` Errors row 4"""
    before = written(db)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            M.create_log(db, log_data=LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=w1.id, user_id=MISSING)

    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert exc.value.orig.diag.constraint_name == "machine_maintenance_logs_created_by_fkey"
    # Then 4
    assert written(db) == before


# [claude] MMLM-C-81
def test_mmlm_c_81__flushed_never_committed(db, w1, u2, m1, monkeypatch):
    """MMLM-C-81 — flushed, never committed.
    Rules: `create_log` R17, `create_log` Side effects"""
    sp = db.begin_nested()
    spy = commit_spy(db, monkeypatch)
    result = M.create_log(db, log_data=LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert count_rows(db, "machine_maintenance_logs") == 1
    # Then 3
    assert count_rows(db, "machine_activity_events") == 1
    # Then 4
    sp.rollback()
    assert count_rows(db, "machine_maintenance_logs") == 0
    # Then 5
    assert count_rows(db, "machine_activity_events") == 0
    # Then 6
    assert not spy.called


# [claude] MMLM-U-01
def test_mmlm_u_01__a_changed_summary_is_written_stamped_and_recorded(db, w1, u2, m1, mk_log):
    """MMLM-U-01 — a changed summary is written, stamped and recorded.
    Rules: `update_log` R6, `update_log` R10, `update_log` R11, `update_log` Returns"""
    a = mk_log()
    result = M.update_log(db, log_id=a.id, log_data=LU(summary="New text"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.summary == "New text"
    # Then 3
    row = reread(db, a)
    assert row.updated_by == u2.id
    assert row.updated_at is not None
    # Then 4
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 5
    assert evs[0].event_type == "maintenance_updated"
    assert evs[0].description == "Maintenance log updated: New text"
    assert evs[0].performed_by == u2.id
    assert evs[0].workspace_id == w1.id
    assert evs[0].machine_id == m1.id
    # Then 6
    assert evs[0].metadata_json == {"maintenance_log_id": a.id, "changes": [{"field": "summary", "label": "Summary", "from_value": "Bearing change", "to_value": "New text"}]}
    # Then 7
    assert evs[0].created_at is not None


# [claude] MMLM-U-02
def test_mmlm_u_02__the_service_s_keyword_call_works(db, w1, u2, mk_log):
    """MMLM-U-02 — the service's keyword call works.
    Rules: `update_log` R6"""
    a = mk_log()
    result = M.update_log(session=db, log_id=a.id, log_data=LU(summary="New text"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.summary == "New text"


# [claude] MMLM-U-03
def test_mmlm_u_03__a_log_of_another_workspace_gets_the_404_and_nothing_is_written(db, w2, u2, m1, mk_log):
    """MMLM-U-03 — a log of another workspace gets the 404 and nothing is written.
    Rules: `update_log` R1, `update_log` Errors row 1"""
    a = mk_log()
    before_a = snap_before(db, a)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_log(db, log_id=a.id, log_data=LU(summary="New text"), workspace_id=w2.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Maintenance log with ID {a.id} not found"
    # Then 4
    assert snap(db, a) == before_a
    # Then 5
    assert written(db) == before
    # Then 6
    assert len(events_of(db, m1)) == 0


# [claude] MMLM-U-04
def test_mmlm_u_04__a_soft_deleted_log_of_another_workspace_gets_the_same_404_not_the_400(db, w2, u2, mk_log):
    """MMLM-U-04 — a soft-deleted log of another workspace gets the same 404, not the 400.
    Rules: `update_log` R1, `update_log` Errors row 1"""
    a = mk_log(gone=True)
    before_a = snap_before(db, a)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_log(db, log_id=a.id, log_data=LU(summary="New text"), workspace_id=w2.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Maintenance log with ID {a.id} not found"
    # Then 4
    assert snap(db, a) == before_a
    # Then 5
    assert written(db) == before


# [claude] MMLM-U-05
def test_mmlm_u_05__an_unknown_id_gets_the_same_404(db, w1, u2, mk_log):
    """MMLM-U-05 — an unknown id gets the same 404.
    Rules: `update_log` R1, `update_log` Errors row 1"""
    a = mk_log()
    before_a = snap_before(db, a)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_log(db, log_id=MISSING, log_data=LU(summary="New text"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Maintenance log with ID 999999999 not found"
    # Then 4
    assert snap(db, a) == before_a
    # Then 5
    assert written(db) == before


# [claude] MMLM-U-06
def test_mmlm_u_06__id_0_gets_the_same_404(db, w1, u2, mk_log):
    """MMLM-U-06 — id 0 gets the same 404.
    Rules: `update_log` R1, `update_log` Errors row 1"""
    a = mk_log()
    before_a = snap_before(db, a)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_log(db, log_id=0, log_data=LU(summary="New text"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Maintenance log with ID 0 not found"
    # Then 4
    assert snap(db, a) == before_a
    # Then 5
    assert written(db) == before


# [claude] MMLM-U-07
def test_mmlm_u_07__a_soft_deleted_log_is_refused_with_a_change(db, w1, u2, m1, mk_log):
    """MMLM-U-07 — a soft-deleted log is refused with a change.
    Rules: `update_log` R2, `update_log` Errors row 2"""
    a = mk_log(gone=True)
    before_a = snap_before(db, a)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_log(db, log_id=a.id, log_data=LU(summary="New text"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update a deleted maintenance log"
    # Then 4
    assert snap(db, a) == before_a
    # Then 5
    assert written(db) == before
    # Then 6
    assert len(events_of(db, m1)) == 0


# [claude] MMLM-U-08
def test_mmlm_u_08__a_soft_deleted_log_is_refused_with_an_empty_body_too(db, w1, u2, mk_log):
    """MMLM-U-08 — a soft-deleted log is refused with an empty body too.
    Rules: `update_log` R2, `update_log` Errors row 2"""
    a = mk_log(gone=True)
    before_a = snap_before(db, a)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_log(db, log_id=a.id, log_data=LU(), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update a deleted maintenance log"
    # Then 4
    assert snap(db, a) == before_a
    # Then 5
    assert written(db) == before


# [claude] MMLM-U-09
@pytest.mark.xfail(strict=True, reason="BUG-1101: A stored maintenance log linked to another workspace's machine shows that machine's id")
def test_mmlm_u_09__a_log_on_another_workspace_s_machine_gets_the_404_and_that_machine_no(db, w1, u2, m9, mk_log):
    """MMLM-U-09 — a log on another workspace's machine gets the 404 and that machine no entry.
    Rules: `update_log` R3 [BUG-1101], `update_log` Errors row 1"""
    # A row of W1 on a W2 machine, invalid data.
    x = mk_log(machine_id=m9.id)
    before_x = snap_before(db, x)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_log(db, log_id=x.id, log_data=LU(summary="New text"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Maintenance log with ID {x.id} not found"
    # Then 4
    assert snap(db, x) == before_x
    # Then 5
    assert written(db) == before
    # Then 6
    assert len(events_of(db, m9)) == 0


# [claude] MMLM-U-10
@pytest.mark.xfail(strict=True, reason="BUG-1101: A stored maintenance log linked to another workspace's machine shows that machine's id")
def test_mmlm_u_10__the_same_row_with_an_empty_body_gets_the_404_too(db, w1, u2, m9, mk_log):
    """MMLM-U-10 — the same row with an empty body gets the 404 too.
    Rules: `update_log` R3 [BUG-1101], `update_log` Errors row 1"""
    # A row of W1 on a W2 machine, invalid data.
    x = mk_log(machine_id=m9.id)
    before_x = snap_before(db, x)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_log(db, log_id=x.id, log_data=LU(), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Maintenance log with ID {x.id} not found"
    # Then 4
    assert snap(db, x) == before_x
    # Then 5
    assert written(db) == before


# [claude] MMLM-U-11
@pytest.mark.xfail(strict=True, reason="BUG-1101: A stored maintenance log linked to another workspace's machine shows that machine's id")
def test_mmlm_u_11__a_soft_deleted_log_on_another_workspace_s_machine_answers_404_not_400(db, w1, u2, m9, mk_log):
    """MMLM-U-11 — a soft-deleted log on another workspace's machine answers 404, not 400.
    Rules: `update_log` R3 [BUG-1101], `update_log` Errors row 1"""
    x = mk_log(machine_id=m9.id, gone=True)
    before_x = snap_before(db, x)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_log(db, log_id=x.id, log_data=LU(summary="New text"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Maintenance log with ID {x.id} not found"
    # Then 4
    assert snap(db, x) == before_x
    # Then 5
    assert written(db) == before


# [claude] MMLM-U-12
def test_mmlm_u_12__the_same_row_asked_for_from_the_machine_s_workspace_gets_the_404(db, w2, u2, m9, mk_log):
    """MMLM-U-12 — the same row asked for from the machine's workspace gets the 404.
    Rules: `update_log` R3, `update_log` R1, `update_log` Errors row 1"""
    # A row of W1 on a W2 machine, invalid data.
    x = mk_log(machine_id=m9.id)
    before_x = snap_before(db, x)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_log(db, log_id=x.id, log_data=LU(summary="New text"), workspace_id=w2.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Maintenance log with ID {x.id} not found"
    # Then 4
    assert snap(db, x) == before_x
    # Then 5
    assert written(db) == before
    # Then 6
    assert len(events_of(db, m9)) == 0


# [claude] MMLM-U-13
def test_mmlm_u_13__an_inactive_log_is_updated_and_stays_inactive(db, w1, u2, m1, mk_log):
    """MMLM-U-13 — an inactive log is updated and stays inactive.
    Rules: `update_log` R4"""
    a = mk_log(is_active=False)
    result = M.update_log(db, log_id=a.id, log_data=LU(summary="New text"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.summary == "New text"
    assert row.is_active is False
    assert row.is_deleted is False
    # Then 3
    evs = events_of(db, m1)
    assert len(evs) == 1


# [claude] MMLM-U-14
def test_mmlm_u_14__a_log_of_a_soft_deleted_machine_is_updated_and_the_entry_goes_to_that(db, w1, u2, md, mk_log):
    """MMLM-U-14 — a log of a soft-deleted machine is updated, and the entry goes to that machine.
    Rules: `update_log` R5"""
    a = mk_log(machine_id=md.id)
    before_md = snap_before(db, md)
    result = M.update_log(db, log_id=a.id, log_data=LU(summary="New text"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.summary == "New text"
    # Then 3
    evs = events_of(db, md)
    assert len(evs) == 1
    # Then 4
    assert evs[0].event_type == "maintenance_updated"
    assert evs[0].description == "Maintenance log updated: New text"
    assert evs[0].performed_by == u2.id
    assert evs[0].workspace_id == w1.id
    assert evs[0].machine_id == md.id
    # Then 5
    assert snap(db, md) == before_md


# [claude] MMLM-U-15
def test_mmlm_u_15__a_log_of_a_machine_in_a_soft_deleted_factory_is_updated_and_the_entry(db, w1, u2, mf, mk_log):
    """MMLM-U-15 — a log of a machine in a soft-deleted factory is updated, and the entry goes to that machine.
    Rules: `update_log` R5"""
    a = mk_log(machine_id=mf.id)
    before_mf = snap_before(db, mf)
    result = M.update_log(db, log_id=a.id, log_data=LU(summary="New text"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.summary == "New text"
    # Then 3
    evs = events_of(db, mf)
    assert len(evs) == 1
    # Then 4
    assert evs[0].event_type == "maintenance_updated"
    assert evs[0].description == "Maintenance log updated: New text"
    assert evs[0].performed_by == u2.id
    assert evs[0].workspace_id == w1.id
    assert evs[0].machine_id == mf.id
    # Then 5
    assert snap(db, mf) == before_mf


# [claude] MMLM-U-16
def test_mmlm_u_16__a_log_of_an_inactive_machine_is_updated_and_the_entry_goes_to_that_mac(db, w1, u2, ma, mk_log):
    """MMLM-U-16 — a log of an inactive machine is updated, and the entry goes to that machine.
    Rules: `update_log` R5"""
    a = mk_log(machine_id=ma.id)
    before_ma = snap_before(db, ma)
    result = M.update_log(db, log_id=a.id, log_data=LU(summary="New text"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.summary == "New text"
    # Then 3
    evs = events_of(db, ma)
    assert len(evs) == 1
    # Then 4
    assert evs[0].event_type == "maintenance_updated"
    assert evs[0].description == "Maintenance log updated: New text"
    assert evs[0].performed_by == u2.id
    assert evs[0].workspace_id == w1.id
    assert evs[0].machine_id == ma.id
    # Then 5
    assert snap(db, ma) == before_ma


# [claude] MMLM-U-17
def test_mmlm_u_17__a_log_of_a_machine_in_an_inactive_factory_is_updated_and_the_entry_goe(db, w1, u2, mg, mk_log):
    """MMLM-U-17 — a log of a machine in an inactive factory is updated, and the entry goes to that machine.
    Rules: `update_log` R5"""
    a = mk_log(machine_id=mg.id)
    before_mg = snap_before(db, mg)
    result = M.update_log(db, log_id=a.id, log_data=LU(summary="New text"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.summary == "New text"
    # Then 3
    evs = events_of(db, mg)
    assert len(evs) == 1
    # Then 4
    assert evs[0].event_type == "maintenance_updated"
    assert evs[0].description == "Maintenance log updated: New text"
    assert evs[0].performed_by == u2.id
    assert evs[0].workspace_id == w1.id
    assert evs[0].machine_id == mg.id
    # Then 5
    assert snap(db, mg) == before_mg


# [claude] MMLM-U-18
def test_mmlm_u_18__maintenance_type_alone_is_written_and_listed_the_entry_s_text_keeps_th(db, w1, u2, m1, mk_log):
    """MMLM-U-18 — maintenance_type alone is written and listed; the entry's text keeps the stored summary.
    Rules: `update_log` R6, `update_log` R11, `update_log` R12"""
    a = mk_log()
    result = M.update_log(db, log_id=a.id, log_data=LU(maintenance_type=MaintenanceTypeEnum.EMERGENCY), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.maintenance_type == MaintenanceTypeEnum.EMERGENCY
    # Then 3
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 4
    assert evs[0].event_type == "maintenance_updated"
    assert evs[0].description == "Maintenance log updated: Bearing change"
    assert evs[0].performed_by == u2.id
    assert evs[0].workspace_id == w1.id
    assert evs[0].machine_id == m1.id
    # Then 5
    assert evs[0].metadata_json == {"maintenance_log_id": a.id, "changes": [{"field": "maintenance_type", "label": "Maintenance type", "from_value": "REPAIR", "to_value": "EMERGENCY"}]}


# [claude] MMLM-U-19
def test_mmlm_u_19__maintenance_date_alone_is_written_and_listed_the_entry_s_text_keeps_th(db, w1, u2, m1, mk_log):
    """MMLM-U-19 — maintenance_date alone is written and listed; the entry's text keeps the stored summary.
    Rules: `update_log` R6, `update_log` R11, `update_log` R12"""
    a = mk_log()
    result = M.update_log(db, log_id=a.id, log_data=LU(maintenance_date=D2), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.maintenance_date == D2
    # Then 3
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 4
    assert evs[0].event_type == "maintenance_updated"
    assert evs[0].description == "Maintenance log updated: Bearing change"
    assert evs[0].performed_by == u2.id
    assert evs[0].workspace_id == w1.id
    assert evs[0].machine_id == m1.id
    # Then 5
    assert evs[0].metadata_json == {"maintenance_log_id": a.id, "changes": [{"field": "maintenance_date", "label": "Maintenance date", "from_value": "2026-03-01", "to_value": "2026-03-02"}]}


# [claude] MMLM-U-20
def test_mmlm_u_20__cost_alone_is_written_and_listed_the_entry_s_text_keeps_the_stored_sum(db, w1, u2, m1, mk_log):
    """MMLM-U-20 — cost alone is written and listed; the entry's text keeps the stored summary.
    Rules: `update_log` R6, `update_log` R11, `update_log` R12"""
    a = mk_log(cost=Decimal("5.00"))
    result = M.update_log(db, log_id=a.id, log_data=LU(cost=Decimal("7.50")), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.cost == Decimal("7.50")
    # Then 3
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 4
    assert evs[0].event_type == "maintenance_updated"
    assert evs[0].description == "Maintenance log updated: Bearing change"
    assert evs[0].performed_by == u2.id
    assert evs[0].workspace_id == w1.id
    assert evs[0].machine_id == m1.id
    # Then 5
    assert evs[0].metadata_json == {"maintenance_log_id": a.id, "changes": [{"field": "cost", "label": "Cost", "from_value": "5.00", "to_value": "7.50"}]}


# [claude] MMLM-U-21
def test_mmlm_u_21__performed_by_alone_is_written_and_listed_the_entry_s_text_keeps_the_st(db, w1, u2, m1, mk_log):
    """MMLM-U-21 — performed_by alone is written and listed; the entry's text keeps the stored summary.
    Rules: `update_log` R6, `update_log` R11, `update_log` R12"""
    a = mk_log(performed_by="Rahim")
    result = M.update_log(db, log_id=a.id, log_data=LU(performed_by="Karim"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.performed_by == "Karim"
    # Then 3
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 4
    assert evs[0].event_type == "maintenance_updated"
    assert evs[0].description == "Maintenance log updated: Bearing change"
    assert evs[0].performed_by == u2.id
    assert evs[0].workspace_id == w1.id
    assert evs[0].machine_id == m1.id
    # Then 5
    assert evs[0].metadata_json == {"maintenance_log_id": a.id, "changes": [{"field": "performed_by", "label": "Performed by", "from_value": "Rahim", "to_value": "Karim"}]}


# [claude] MMLM-U-22
def test_mmlm_u_22__a_field_omitted_stays_as_it_was(db, w1, u1, u2, m1, mk_log):
    """MMLM-U-22 — a field omitted stays as it was.
    Rules: `update_log` R6"""
    a = mk_log(cost=Decimal("5.00"), performed_by="Rahim")
    result = M.update_log(db, log_id=a.id, log_data=LU(summary="New text"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.maintenance_type == REPAIR
    assert row.maintenance_date == D1
    assert row.cost == Decimal("5.00")
    assert row.performed_by == "Rahim"
    # Then 3
    row = reread(db, a)
    assert row.machine_id == m1.id
    assert row.workspace_id == w1.id
    assert row.created_by == u1.id
    # Then 4
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 5
    assert evs[0].metadata_json == {"maintenance_log_id": a.id, "changes": [{"field": "summary", "label": "Summary", "from_value": "Bearing change", "to_value": "New text"}]}


# [claude] MMLM-U-23
def test_mmlm_u_23__all_five_fields_change_one_entry_listed_in_field_order_whatever_order(db, w1, u2, m1, mk_log):
    """MMLM-U-23 — all five fields change: one entry, listed in field order whatever order they were sent in.
    Rules: `update_log` R6, `update_log` R10, `update_log` R12"""
    a = mk_log(cost=Decimal("5.00"), performed_by="Rahim")
    result = M.update_log(db, log_id=a.id, log_data=LU(performed_by="Karim", cost=Decimal("7.50"), summary="New text", maintenance_date=D2, maintenance_type=MaintenanceTypeEnum.EMERGENCY), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.summary == "New text"
    assert row.cost == Decimal("7.50")
    assert row.performed_by == "Karim"
    # Then 3
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 4
    assert evs[0].event_type == "maintenance_updated"
    assert evs[0].description == "Maintenance log updated: New text"
    assert evs[0].performed_by == u2.id
    assert evs[0].workspace_id == w1.id
    assert evs[0].machine_id == m1.id
    # Then 5
    assert evs[0].metadata_json == {"maintenance_log_id": a.id, "changes": [{"field": "maintenance_type", "label": "Maintenance type", "from_value": "REPAIR", "to_value": "EMERGENCY"}, {"field": "maintenance_date", "label": "Maintenance date", "from_value": "2026-03-01", "to_value": "2026-03-02"}, {"field": "summary", "label": "Summary", "from_value": "Bearing change", "to_value": "New text"}, {"field": "cost", "label": "Cost", "from_value": "5.00", "to_value": "7.50"}, {"field": "performed_by", "label": "Performed by", "from_value": "Rahim", "to_value": "Karim"}]}


# [claude] MMLM-U-24
def test_mmlm_u_24__fields_sent_with_their_stored_value_are_left_out_of_changes(db, w1, u2, m1, mk_log):
    """MMLM-U-24 — fields sent with their stored value are left out of changes.
    Rules: `update_log` R12, `update_log` R10"""
    a = mk_log(cost=Decimal("5.00"), performed_by="Rahim")
    result = M.update_log(db, log_id=a.id, log_data=LU(maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("7.50"), performed_by="Rahim"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 3
    assert evs[0].metadata_json == {"maintenance_log_id": a.id, "changes": [{"field": "cost", "label": "Cost", "from_value": "5.00", "to_value": "7.50"}]}


# [claude] MMLM-U-25
def test_mmlm_u_25__the_entry_records_empty_old_values_as_none(db, w1, u2, m1, mk_log):
    """MMLM-U-25 — the entry records empty old values as None.
    Rules: `update_log` R12"""
    a = mk_log()
    result = M.update_log(db, log_id=a.id, log_data=LU(cost=Decimal("7.50"), performed_by="Rahim"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 3
    assert evs[0].metadata_json == {"maintenance_log_id": a.id, "changes": [{"field": "cost", "label": "Cost", "from_value": None, "to_value": "7.50"}, {"field": "performed_by", "label": "Performed by", "from_value": None, "to_value": "Rahim"}]}


# [claude] MMLM-U-26
def test_mmlm_u_26__the_entry_shows_the_machine_and_workspace_of_the_log_and_the_acting_us(db, w1, u1, u3, m1, m2, mk_log):
    """MMLM-U-26 — the entry shows the machine and workspace of the log, and the acting user.
    Rules: `update_log` R11"""
    a = mk_log(machine_id=m2.id, created_by=u1.id)
    result = M.update_log(db, log_id=a.id, log_data=LU(summary="New text"), workspace_id=w1.id, user_id=u3.id)

    # Then 1
    assert result is a
    # Then 2
    evs = events_of(db, m2)
    assert len(evs) == 1
    # Then 3
    assert evs[0].event_type == "maintenance_updated"
    assert evs[0].description == "Maintenance log updated: New text"
    assert evs[0].performed_by == u3.id
    assert evs[0].workspace_id == w1.id
    assert evs[0].machine_id == m2.id
    # Then 4
    assert len(events_of(db, m1)) == 0


# [claude] MMLM-U-27
def test_mmlm_u_27__the_machine_is_not_touched_when_the_date_changes(db, w1, u2, m1, mk_log):
    """MMLM-U-27 — the machine is not touched when the date changes.
    Rules: `update_log` Side effects"""
    a = mk_log()
    before_m1 = snap_before(db, m1)
    result = M.update_log(db, log_id=a.id, log_data=LU(maintenance_date=D2), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    assert snap(db, m1) == before_m1


# [claude] MMLM-U-28
def test_mmlm_u_28__unaffected_columns_stay(db, w1, u2, mk_log):
    """MMLM-U-28 — unaffected columns stay.
    Rules: `update_log` Side effects"""
    a = mk_log(is_active=False)
    before_a = snap_before(db, a, "summary", "updated_by", "updated_at")
    result = M.update_log(db, log_id=a.id, log_data=LU(summary="New text"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    assert snap(db, a, "summary", "updated_by", "updated_at") == before_a


# [claude] MMLM-U-29
def test_mmlm_u_29__cost_0_on_a_log_at_5_00_is_a_value_and_is_applied(db, w1, u2, m1, mk_log):
    """MMLM-U-29 — cost 0 on a log at 5.00 is a value and is applied.
    Rules: `update_log` R6"""
    a = mk_log(cost=Decimal("5.00"))
    result = M.update_log(db, log_id=a.id, log_data=LU(cost=0), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert str(row.cost) == "0.00"
    # Then 3
    row = reread(db, a)
    assert row.updated_by == u2.id
    # Then 4
    evs = events_of(db, m1)
    assert len(evs) == 1


# [claude] MMLM-U-30
def test_mmlm_u_30__cost_0_00_on_a_log_with_no_cost_is_a_change_listed_from_none(db, w1, u2, m1, mk_log):
    """MMLM-U-30 — cost 0.00 on a log with no cost is a change, listed from None.
    Rules: `update_log` R6, `update_log` R12"""
    a = mk_log()
    result = M.update_log(db, log_id=a.id, log_data=LU(cost=Decimal("0.00")), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert str(row.cost) == "0.00"
    # Then 3
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 4
    assert evs[0].metadata_json == {"maintenance_log_id": a.id, "changes": [{"field": "cost", "label": "Cost", "from_value": None, "to_value": "0.00"}]}


# [claude] MMLM-U-31
@pytest.mark.xfail(strict=True, reason="BUG-1153: A maintenance log's cost and performer cannot be cleared")
def test_mmlm_u_31__null_clears_cost_and_the_entry_says_none(db, w1, u2, m1, mk_log):
    """MMLM-U-31 — null clears cost and the entry says None.
    Rules: `update_log` R7 [BUG-1153]"""
    a = mk_log(cost=Decimal("5.00"))
    result = M.update_log(db, log_id=a.id, log_data=LU(cost=None), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.cost is None
    # Then 3
    row = reread(db, a)
    assert row.updated_by == u2.id
    # Then 4
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 5
    assert evs[0].metadata_json == {"maintenance_log_id": a.id, "changes": [{"field": "cost", "label": "Cost", "from_value": "5.00", "to_value": None}]}


# [claude] MMLM-U-32
@pytest.mark.xfail(strict=True, reason="BUG-1153: A maintenance log's cost and performer cannot be cleared")
def test_mmlm_u_32__null_clears_performed_by_and_the_entry_says_none(db, w1, u2, m1, mk_log):
    """MMLM-U-32 — null clears performed_by and the entry says None.
    Rules: `update_log` R7 [BUG-1153]"""
    a = mk_log(performed_by="Rahim")
    result = M.update_log(db, log_id=a.id, log_data=LU(performed_by=None), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.performed_by is None
    # Then 3
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 4
    assert evs[0].metadata_json == {"maintenance_log_id": a.id, "changes": [{"field": "performed_by", "label": "Performed by", "from_value": "Rahim", "to_value": None}]}


# [claude] MMLM-U-33
@pytest.mark.xfail(strict=True, reason="BUG-1153: A maintenance log's cost and performer cannot be cleared")
def test_mmlm_u_33__null_on_both_clears_both_one_entry(db, w1, u2, m1, mk_log):
    """MMLM-U-33 — null on both clears both, one entry.
    Rules: `update_log` R7 [BUG-1153]"""
    a = mk_log(cost=Decimal("5.00"), performed_by="Rahim")
    result = M.update_log(db, log_id=a.id, log_data=LU(cost=None, performed_by=None), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.cost is None
    assert row.performed_by is None
    # Then 3
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 4
    assert evs[0].metadata_json == {"maintenance_log_id": a.id, "changes": [{"field": "cost", "label": "Cost", "from_value": "5.00", "to_value": None}, {"field": "performed_by", "label": "Performed by", "from_value": "Rahim", "to_value": None}]}


# [claude] MMLM-U-34
@pytest.mark.xfail(strict=True, reason="BUG-1153: A maintenance log's cost and performer cannot be cleared")
def test_mmlm_u_34__null_beside_a_changed_field_both_apply_listed_in_field_order(db, w1, u2, m1, mk_log):
    """MMLM-U-34 — null beside a changed field: both apply, listed in field order.
    Rules: `update_log` R7 [BUG-1153]"""
    a = mk_log(cost=Decimal("5.00"))
    result = M.update_log(db, log_id=a.id, log_data=LU(cost=None, summary="New text"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.cost is None
    # Then 3
    row = reread(db, a)
    assert row.summary == "New text"
    # Then 4
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 5
    assert evs[0].metadata_json == {"maintenance_log_id": a.id, "changes": [{"field": "summary", "label": "Summary", "from_value": "Bearing change", "to_value": "New text"}, {"field": "cost", "label": "Cost", "from_value": "5.00", "to_value": None}]}


# [claude] MMLM-U-35
@pytest.mark.xfail(strict=True, reason="BUG-1153: A maintenance log's cost and performer cannot be cleared")
def test_mmlm_u_35__null_for_maintenance_type_is_refused_by_the_schema(db, mk_log):
    """MMLM-U-35 — null for maintenance_type is refused by the schema.
    Rules: `update_log` R7a [BUG-1153], `update_log` Errors row 3"""
    a = mk_log()
    before_a = snap_before(db, a)
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LU(maintenance_type=None)

    # Then 2
    assert snap(db, a) == before_a
    # Then 3
    assert written(db) == before


# [claude] MMLM-U-36
@pytest.mark.xfail(strict=True, reason="BUG-1153: A maintenance log's cost and performer cannot be cleared")
def test_mmlm_u_36__null_for_maintenance_date_is_refused_by_the_schema(db, mk_log):
    """MMLM-U-36 — null for maintenance_date is refused by the schema.
    Rules: `update_log` R7a [BUG-1153], `update_log` Errors row 3"""
    a = mk_log()
    before_a = snap_before(db, a)
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LU(maintenance_date=None)

    # Then 2
    assert snap(db, a) == before_a
    # Then 3
    assert written(db) == before


# [claude] MMLM-U-37
@pytest.mark.xfail(strict=True, reason="BUG-1153: A maintenance log's cost and performer cannot be cleared")
def test_mmlm_u_37__null_for_summary_is_refused_by_the_schema(db, mk_log):
    """MMLM-U-37 — null for summary is refused by the schema.
    Rules: `update_log` R7a [BUG-1153], `update_log` Errors row 3"""
    a = mk_log()
    before_a = snap_before(db, a)
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LU(summary=None)

    # Then 2
    assert snap(db, a) == before_a
    # Then 3
    assert written(db) == before


# [claude] MMLM-U-38
def test_mmlm_u_38__an_empty_body_no_entry(db, w1, u2, m1, mk_log):
    """MMLM-U-38 — an empty body: no entry.
    Rules: `update_log` R8"""
    a = mk_log()
    result = M.update_log(db, log_id=a.id, log_data=LU(), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    assert len(events_of(db, m1)) == 0


# [claude] MMLM-U-39
@pytest.mark.xfail(strict=True, reason="BUG-1151: updated_by stamped on no-op maintenance log updates")
def test_mmlm_u_39__an_empty_body_on_a_never_stamped_log_no_stamp(db, w1, u2, mk_log):
    """MMLM-U-39 — an empty body on a never-stamped log: no stamp.
    Rules: `update_log` R8a [BUG-1151]"""
    a = mk_log()
    before_a = snap_before(db, a)
    result = M.update_log(db, log_id=a.id, log_data=LU(), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.updated_by is None
    # Then 3
    row = reread(db, a)
    assert row.updated_at is None
    # Then 4
    assert snap(db, a) == before_a


# [claude] MMLM-U-40
def test_mmlm_u_40__an_empty_body_by_the_user_already_stamped_both_stamps_stay(db, w1, u3, m1, mk_log):
    """MMLM-U-40 — an empty body by the user already stamped: both stamps stay.
    Rules: `update_log` R8a"""
    a = mk_log(updated_by=u3.id, updated_at=T0)
    before_a = snap_before(db, a)
    result = M.update_log(db, log_id=a.id, log_data=LU(), workspace_id=w1.id, user_id=u3.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.updated_by == u3.id
    # Then 3
    row = reread(db, a)
    assert row.updated_at == T0
    # Then 4
    assert len(events_of(db, m1)) == 0
    # Then 5
    assert snap(db, a) == before_a


# [claude] MMLM-U-41
@pytest.mark.xfail(strict=True, reason="BUG-1151: updated_by stamped on no-op maintenance log updates")
def test_mmlm_u_41__an_empty_body_by_another_user_the_stamps_of_the_earlier_user_stay(db, w1, u2, u3, mk_log):
    """MMLM-U-41 — an empty body by another user: the stamps of the earlier user stay.
    Rules: `update_log` R8a [BUG-1151]"""
    a = mk_log(updated_by=u3.id, updated_at=T0)
    before_a = snap_before(db, a)
    result = M.update_log(db, log_id=a.id, log_data=LU(), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.updated_by == u3.id
    # Then 3
    row = reread(db, a)
    assert row.updated_at == T0
    # Then 4
    assert snap(db, a) == before_a


# [claude] MMLM-U-42
def test_mmlm_u_42__the_same_five_values_no_entry(db, w1, u2, m1, mk_log):
    """MMLM-U-42 — the same five values: no entry.
    Rules: `update_log` R8"""
    a = mk_log(cost=Decimal("5.00"), performed_by="Rahim")
    result = M.update_log(db, log_id=a.id, log_data=LU(maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("5.00"), performed_by="Rahim"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    assert len(events_of(db, m1)) == 0


# [claude] MMLM-U-43
@pytest.mark.xfail(strict=True, reason="BUG-1151: updated_by stamped on no-op maintenance log updates")
def test_mmlm_u_43__the_same_five_values_on_a_never_stamped_log_no_stamp(db, w1, u2, mk_log):
    """MMLM-U-43 — the same five values on a never-stamped log: no stamp.
    Rules: `update_log` R8a [BUG-1151]"""
    a = mk_log(cost=Decimal("5.00"), performed_by="Rahim")
    before_a = snap_before(db, a)
    result = M.update_log(db, log_id=a.id, log_data=LU(maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("5.00"), performed_by="Rahim"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.updated_by is None
    # Then 3
    row = reread(db, a)
    assert row.updated_at is None
    # Then 4
    assert snap(db, a) == before_a


# [claude] MMLM-U-44
def test_mmlm_u_44__the_same_five_values_by_the_user_already_stamped_both_stamps_stay(db, w1, u3, m1, mk_log):
    """MMLM-U-44 — the same five values by the user already stamped: both stamps stay.
    Rules: `update_log` R8a"""
    a = mk_log(cost=Decimal("5.00"), performed_by="Rahim", updated_by=u3.id, updated_at=T0)
    before_a = snap_before(db, a)
    result = M.update_log(db, log_id=a.id, log_data=LU(maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("5.00"), performed_by="Rahim"), workspace_id=w1.id, user_id=u3.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.updated_by == u3.id
    # Then 3
    row = reread(db, a)
    assert row.updated_at == T0
    # Then 4
    assert len(events_of(db, m1)) == 0
    # Then 5
    assert snap(db, a) == before_a


# [claude] MMLM-U-45
@pytest.mark.xfail(strict=True, reason="BUG-1151: updated_by stamped on no-op maintenance log updates")
def test_mmlm_u_45__the_same_five_values_by_another_user_the_stamps_of_the_earlier_user_st(db, w1, u2, u3, mk_log):
    """MMLM-U-45 — the same five values by another user: the stamps of the earlier user stay.
    Rules: `update_log` R8a [BUG-1151]"""
    a = mk_log(cost=Decimal("5.00"), performed_by="Rahim", updated_by=u3.id, updated_at=T0)
    before_a = snap_before(db, a)
    result = M.update_log(db, log_id=a.id, log_data=LU(maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("5.00"), performed_by="Rahim"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.updated_by == u3.id
    # Then 3
    row = reread(db, a)
    assert row.updated_at == T0
    # Then 4
    assert snap(db, a) == before_a


# [claude] MMLM-U-46
def test_mmlm_u_46__null_on_empty_fields_no_entry(db, w1, u2, m1, mk_log):
    """MMLM-U-46 — null on empty fields: no entry.
    Rules: `update_log` R8"""
    a = mk_log()
    result = M.update_log(db, log_id=a.id, log_data=LU(cost=None, performed_by=None), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    assert len(events_of(db, m1)) == 0


# [claude] MMLM-U-47
@pytest.mark.xfail(strict=True, reason="BUG-1151: updated_by stamped on no-op maintenance log updates")
def test_mmlm_u_47__null_on_empty_fields_on_a_never_stamped_log_no_stamp(db, w1, u2, mk_log):
    """MMLM-U-47 — null on empty fields on a never-stamped log: no stamp.
    Rules: `update_log` R8a [BUG-1151]"""
    a = mk_log()
    before_a = snap_before(db, a)
    result = M.update_log(db, log_id=a.id, log_data=LU(cost=None, performed_by=None), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.updated_by is None
    # Then 3
    row = reread(db, a)
    assert row.updated_at is None
    # Then 4
    assert snap(db, a) == before_a


# [claude] MMLM-U-48
def test_mmlm_u_48__null_on_empty_fields_by_the_user_already_stamped_both_stamps_stay(db, w1, u3, m1, mk_log):
    """MMLM-U-48 — null on empty fields by the user already stamped: both stamps stay.
    Rules: `update_log` R8a"""
    a = mk_log(updated_by=u3.id, updated_at=T0)
    before_a = snap_before(db, a)
    result = M.update_log(db, log_id=a.id, log_data=LU(cost=None, performed_by=None), workspace_id=w1.id, user_id=u3.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.updated_by == u3.id
    # Then 3
    row = reread(db, a)
    assert row.updated_at == T0
    # Then 4
    assert len(events_of(db, m1)) == 0
    # Then 5
    assert snap(db, a) == before_a


# [claude] MMLM-U-49
@pytest.mark.xfail(strict=True, reason="BUG-1151: updated_by stamped on no-op maintenance log updates")
def test_mmlm_u_49__null_on_empty_fields_by_another_user_the_stamps_of_the_earlier_user_st(db, w1, u2, u3, mk_log):
    """MMLM-U-49 — null on empty fields by another user: the stamps of the earlier user stay.
    Rules: `update_log` R8a [BUG-1151]"""
    a = mk_log(updated_by=u3.id, updated_at=T0)
    before_a = snap_before(db, a)
    result = M.update_log(db, log_id=a.id, log_data=LU(cost=None, performed_by=None), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.updated_by == u3.id
    # Then 3
    row = reread(db, a)
    assert row.updated_at == T0
    # Then 4
    assert snap(db, a) == before_a


# [claude] MMLM-U-50
def test_mmlm_u_50__cost_5_000_on_5_00_no_entry(db, w1, u2, m1, mk_log):
    """MMLM-U-50 — cost 5.000 on 5.00: no entry.
    Rules: `update_log` R8"""
    a = mk_log(cost=Decimal("5.00"))
    result = M.update_log(db, log_id=a.id, log_data=LU(cost=Decimal("5.000")), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    assert len(events_of(db, m1)) == 0


# [claude] MMLM-U-51
@pytest.mark.xfail(strict=True, reason="BUG-1151: updated_by stamped on no-op maintenance log updates")
def test_mmlm_u_51__cost_5_000_on_5_00_on_a_never_stamped_log_no_stamp(db, w1, u2, mk_log):
    """MMLM-U-51 — cost 5.000 on 5.00 on a never-stamped log: no stamp.
    Rules: `update_log` R8a [BUG-1151]"""
    a = mk_log(cost=Decimal("5.00"))
    before_a = snap_before(db, a)
    result = M.update_log(db, log_id=a.id, log_data=LU(cost=Decimal("5.000")), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.updated_by is None
    # Then 3
    row = reread(db, a)
    assert row.updated_at is None
    # Then 4
    assert snap(db, a) == before_a


# [claude] MMLM-U-52
def test_mmlm_u_52__cost_5_000_on_5_00_by_the_user_already_stamped_both_stamps_stay(db, w1, u3, m1, mk_log):
    """MMLM-U-52 — cost 5.000 on 5.00 by the user already stamped: both stamps stay.
    Rules: `update_log` R8a"""
    a = mk_log(cost=Decimal("5.00"), updated_by=u3.id, updated_at=T0)
    before_a = snap_before(db, a)
    result = M.update_log(db, log_id=a.id, log_data=LU(cost=Decimal("5.000")), workspace_id=w1.id, user_id=u3.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.updated_by == u3.id
    # Then 3
    row = reread(db, a)
    assert row.updated_at == T0
    # Then 4
    assert len(events_of(db, m1)) == 0
    # Then 5
    assert snap(db, a) == before_a


# [claude] MMLM-U-53
@pytest.mark.xfail(strict=True, reason="BUG-1151: updated_by stamped on no-op maintenance log updates")
def test_mmlm_u_53__cost_5_000_on_5_00_by_another_user_the_stamps_of_the_earlier_user_stay(db, w1, u2, u3, mk_log):
    """MMLM-U-53 — cost 5.000 on 5.00 by another user: the stamps of the earlier user stay.
    Rules: `update_log` R8a [BUG-1151]"""
    a = mk_log(cost=Decimal("5.00"), updated_by=u3.id, updated_at=T0)
    before_a = snap_before(db, a)
    result = M.update_log(db, log_id=a.id, log_data=LU(cost=Decimal("5.000")), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.updated_by == u3.id
    # Then 3
    row = reread(db, a)
    assert row.updated_at == T0
    # Then 4
    assert snap(db, a) == before_a


# [claude] MMLM-U-54
@pytest.mark.xfail(strict=True, reason="BUG-1151: updated_by stamped on no-op maintenance log updates")
def test_mmlm_u_54__an_empty_body_by_an_unknown_user_raises_nothing(db, w1, m1, mk_log):
    """MMLM-U-54 — an empty body by an unknown user raises nothing.
    Rules: `update_log` R8a [BUG-1151]"""
    a = mk_log()
    result = M.update_log(db, log_id=a.id, log_data=LU(), workspace_id=w1.id, user_id=MISSING)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.updated_by is None
    # Then 3
    assert len(events_of(db, m1)) == 0


# [claude] MMLM-U-55
@pytest.mark.xfail(strict=True, reason="BUG-1151: updated_by stamped on no-op maintenance log updates")
def test_mmlm_u_55__the_same_values_by_an_unknown_user_raises_nothing(db, w1, m1, mk_log):
    """MMLM-U-55 — the same values by an unknown user raises nothing.
    Rules: `update_log` R8a [BUG-1151]"""
    a = mk_log()
    result = M.update_log(db, log_id=a.id, log_data=LU(summary="Bearing change"), workspace_id=w1.id, user_id=MISSING)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.updated_by is None
    # Then 3
    assert len(events_of(db, m1)) == 0


# [claude] MMLM-U-56
def test_mmlm_u_56__cost_5_on_5_00_is_no_change_compared_by_value(db, w1, u2, m1, mk_log):
    """MMLM-U-56 — cost 5 on 5.00 is no change: compared by value.
    Rules: `update_log` R9"""
    a = mk_log(cost=Decimal("5.00"))
    result = M.update_log(db, log_id=a.id, log_data=LU(cost=5), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    assert len(events_of(db, m1)) == 0
    # Then 3
    row = reread(db, a)
    assert str(row.cost) == "5.00"


# [claude] MMLM-U-57
def test_mmlm_u_57__cost_5_0_on_5_00_is_no_change_compared_by_value(db, w1, u2, m1, mk_log):
    """MMLM-U-57 — cost 5.0 on 5.00 is no change: compared by value.
    Rules: `update_log` R9"""
    a = mk_log(cost=Decimal("5.00"))
    result = M.update_log(db, log_id=a.id, log_data=LU(cost=Decimal("5.0")), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    assert len(events_of(db, m1)) == 0
    # Then 3
    row = reread(db, a)
    assert str(row.cost) == "5.00"


# [claude] MMLM-U-58
def test_mmlm_u_58__cost_5_00_on_5_00_is_no_change_compared_by_value(db, w1, u2, m1, mk_log):
    """MMLM-U-58 — cost 5.00 on 5.00 is no change: compared by value.
    Rules: `update_log` R9"""
    a = mk_log(cost=Decimal("5.00"))
    result = M.update_log(db, log_id=a.id, log_data=LU(cost=Decimal("5.00")), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    assert len(events_of(db, m1)) == 0
    # Then 3
    row = reread(db, a)
    assert str(row.cost) == "5.00"


# [claude] MMLM-U-59
def test_mmlm_u_59__cost_0_on_0_00_is_no_change_compared_by_value(db, w1, u2, m1, mk_log):
    """MMLM-U-59 — cost -0 on 0.00 is no change: compared by value.
    Rules: `update_log` R9, `update_log` R8"""
    a = mk_log(cost=Decimal("0.00"))
    result = M.update_log(db, log_id=a.id, log_data=LU(cost=Decimal("-0")), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    assert len(events_of(db, m1)) == 0
    # Then 3
    row = reread(db, a)
    assert str(row.cost) == "0.00"


# [claude] MMLM-U-60
@pytest.mark.xfail(strict=True, reason="BUG-1151: updated_by stamped on no-op maintenance log updates")
def test_mmlm_u_60__cost_5_on_5_00_by_another_user_leaves_the_stamps(db, w1, u2, u3, mk_log):
    """MMLM-U-60 — cost 5 on 5.00 by another user leaves the stamps.
    Rules: `update_log` R9, `update_log` R8a [BUG-1151]"""
    a = mk_log(cost=Decimal("5.00"), updated_by=u3.id, updated_at=T0)
    result = M.update_log(db, log_id=a.id, log_data=LU(cost=5), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.updated_by == u3.id
    # Then 3
    row = reread(db, a)
    assert row.updated_at == T0


# [claude] MMLM-U-61
def test_mmlm_u_61__a_real_change_by_the_user_already_stamped_issues_the_update(db, w1, u3, m1, mk_log):
    """MMLM-U-61 — a real change by the user already stamped issues the update.
    Rules: `update_log` R10"""
    a = mk_log(updated_by=u3.id, updated_at=T0)
    result = M.update_log(db, log_id=a.id, log_data=LU(summary="New text"), workspace_id=w1.id, user_id=u3.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.updated_by == u3.id
    # Then 3
    row = reread(db, a)
    assert row.updated_at != T0
    # Then 4
    row = reread(db, a)
    assert row.updated_at is not None
    # Then 5
    evs = events_of(db, m1)
    assert len(evs) == 1


# [claude] MMLM-U-62
def test_mmlm_u_62__a_real_change_by_another_user_moves_both_stamps(db, w1, u2, u3, m1, mk_log):
    """MMLM-U-62 — a real change by another user moves both stamps.
    Rules: `update_log` R10"""
    a = mk_log(updated_by=u3.id, updated_at=T0)
    result = M.update_log(db, log_id=a.id, log_data=LU(summary="New text"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.updated_by == u2.id
    # Then 3
    row = reread(db, a)
    assert row.updated_at != T0
    # Then 4
    evs = events_of(db, m1)
    assert len(evs) == 1


# [claude] MMLM-U-63
def test_mmlm_u_63__the_same_change_sent_again_after_a_refresh_writes_no_second_entry(db, w1, u2, m1, mk_log):
    """MMLM-U-63 — the same change sent again after a refresh writes no second entry.
    Rules: `update_log` R8, `update_log` R10"""
    a = mk_log(cost=Decimal("5.00"))
    M.update_log(db, log_id=a.id, log_data=LU(cost=Decimal("7.50")), workspace_id=w1.id, user_id=u2.id)
    db.refresh(a)
    result = M.update_log(db, log_id=a.id, log_data=LU(cost=Decimal("7.50")), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 3
    assert evs[0].metadata_json == {"maintenance_log_id": a.id, "changes": [{"field": "cost", "label": "Cost", "from_value": "5.00", "to_value": "7.50"}]}


# [claude] MMLM-U-64
def test_mmlm_u_64__two_real_changes_write_two_entries_one_each(db, w1, u2, m1, mk_log):
    """MMLM-U-64 — two real changes write two entries, one each.
    Rules: `update_log` R10, `update_log` R11"""
    a = mk_log(cost=Decimal("5.00"))
    M.update_log(db, log_id=a.id, log_data=LU(cost=Decimal("7.50")), workspace_id=w1.id, user_id=u2.id)
    db.refresh(a)
    result = M.update_log(db, log_id=a.id, log_data=LU(cost=Decimal("8.25")), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    assert len(events_of(db, m1)) == 2
    # Then 3
    assert events_of(db, m1)[0].metadata_json["changes"][0]["to_value"] == "7.50"
    # Then 4
    assert events_of(db, m1)[1].metadata_json["changes"] == [{"field": "cost", "label": "Cost", "from_value": "7.50", "to_value": "8.25"}]


# [claude] MMLM-U-65
@pytest.mark.xfail(strict=True, reason="BUG-1157: Maintenance log cost with too many digits or decimals accepted; the activity entry records it as typed")
def test_mmlm_u_65__cost_7_on_5_00_the_entry_shows_the_stored_form(db, w1, u2, m1, mk_log):
    """MMLM-U-65 — cost 7 on 5.00: the entry shows the stored form.
    Rules: `update_log` R12a [BUG-1157]"""
    a = mk_log(cost=Decimal("5.00"))
    result = M.update_log(db, log_id=a.id, log_data=LU(cost=7), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert str(row.cost) == "7.00"
    # Then 3
    assert events_of(db, m1)[0].metadata_json["changes"][0]["to_value"] == "7.00"
    # Then 4
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 5
    assert evs[0].metadata_json == {"maintenance_log_id": a.id, "changes": [{"field": "cost", "label": "Cost", "from_value": "5.00", "to_value": "7.00"}]}


# [claude] MMLM-U-66
@pytest.mark.xfail(strict=True, reason="BUG-1157: Maintenance log cost with too many digits or decimals accepted; the activity entry records it as typed")
def test_mmlm_u_66__cost_7_1_on_5_00_the_entry_shows_the_stored_form(db, w1, u2, m1, mk_log):
    """MMLM-U-66 — cost 7.1 on 5.00: the entry shows the stored form.
    Rules: `update_log` R12a [BUG-1157]"""
    a = mk_log(cost=Decimal("5.00"))
    result = M.update_log(db, log_id=a.id, log_data=LU(cost=Decimal("7.1")), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert str(row.cost) == "7.10"
    # Then 3
    assert events_of(db, m1)[0].metadata_json["changes"][0]["to_value"] == "7.10"
    # Then 4
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 5
    assert evs[0].metadata_json == {"maintenance_log_id": a.id, "changes": [{"field": "cost", "label": "Cost", "from_value": "5.00", "to_value": "7.10"}]}


# [claude] MMLM-U-67
@pytest.mark.xfail(strict=True, reason="BUG-1157: Maintenance log cost with too many digits or decimals accepted; the activity entry records it as typed")
def test_mmlm_u_67__cost_1e_3_on_0_13_the_entry_shows_the_stored_form(db, w1, u2, m1, mk_log):
    """MMLM-U-67 — cost 1E+3 on 0.13: the entry shows the stored form.
    Rules: `update_log` R12a [BUG-1157]"""
    a = mk_log(cost=Decimal("0.13"))
    result = M.update_log(db, log_id=a.id, log_data=LU(cost=Decimal("1E+3")), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert str(row.cost) == "1000.00"
    # Then 3
    assert events_of(db, m1)[0].metadata_json["changes"][0]["to_value"] == "1000.00"
    # Then 4
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 5
    assert evs[0].metadata_json == {"maintenance_log_id": a.id, "changes": [{"field": "cost", "label": "Cost", "from_value": "0.13", "to_value": "1000.00"}]}


# [claude] MMLM-U-68
@pytest.mark.xfail(strict=True, reason="BUG-1157: Maintenance log cost with too many digits or decimals accepted; the activity entry records it as typed")
def test_mmlm_u_68__cost_5_000_on_7_00_the_entry_shows_the_stored_form(db, w1, u2, m1, mk_log):
    """MMLM-U-68 — cost 5.000 on 7.00: the entry shows the stored form.
    Rules: `update_log` R12a [BUG-1157]"""
    a = mk_log(cost=Decimal("7.00"))
    result = M.update_log(db, log_id=a.id, log_data=LU(cost=Decimal("5.000")), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert str(row.cost) == "5.00"
    # Then 3
    assert events_of(db, m1)[0].metadata_json["changes"][0]["to_value"] == "5.00"
    # Then 4
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 5
    assert evs[0].metadata_json == {"maintenance_log_id": a.id, "changes": [{"field": "cost", "label": "Cost", "from_value": "7.00", "to_value": "5.00"}]}


# [claude] MMLM-U-69
@pytest.mark.xfail(strict=True, reason="BUG-1157: Maintenance log cost with too many digits or decimals accepted; the activity entry records it as typed")
def test_mmlm_u_69__cost_0_on_5_00_the_entry_shows_the_stored_form(db, w1, u2, m1, mk_log):
    """MMLM-U-69 — cost 0 on 5.00: the entry shows the stored form.
    Rules: `update_log` R12a [BUG-1157]"""
    a = mk_log(cost=Decimal("5.00"))
    result = M.update_log(db, log_id=a.id, log_data=LU(cost=0), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert str(row.cost) == "0.00"
    # Then 3
    assert events_of(db, m1)[0].metadata_json["changes"][0]["to_value"] == "0.00"
    # Then 4
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 5
    assert evs[0].metadata_json == {"maintenance_log_id": a.id, "changes": [{"field": "cost", "label": "Cost", "from_value": "5.00", "to_value": "0.00"}]}


# [claude] MMLM-U-70
@pytest.mark.xfail(strict=True, reason="BUG-1157: Maintenance log cost with too many digits or decimals accepted; the activity entry records it as typed")
def test_mmlm_u_70__cost_0_on_5_00_the_entry_shows_the_stored_form(db, w1, u2, m1, mk_log):
    """MMLM-U-70 — cost -0 on 5.00: the entry shows the stored form.
    Rules: `update_log` R12a [BUG-1157]"""
    a = mk_log(cost=Decimal("5.00"))
    result = M.update_log(db, log_id=a.id, log_data=LU(cost=Decimal("-0")), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert str(row.cost) == "0.00"
    # Then 3
    assert events_of(db, m1)[0].metadata_json["changes"][0]["to_value"] == "0.00"
    # Then 4
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 5
    assert evs[0].metadata_json == {"maintenance_log_id": a.id, "changes": [{"field": "cost", "label": "Cost", "from_value": "5.00", "to_value": "0.00"}]}


# [claude] MMLM-U-71
@pytest.mark.xfail(strict=True, reason="BUG-1157: Maintenance log cost with too many digits or decimals accepted; the activity entry records it as typed")
def test_mmlm_u_71__cost_7_on_a_log_with_no_cost_the_entry_shows_the_stored_form(db, w1, u2, m1, mk_log):
    """MMLM-U-71 — cost 7 on a log with no cost: the entry shows the stored form.
    Rules: `update_log` R12a [BUG-1157]"""
    a = mk_log()
    result = M.update_log(db, log_id=a.id, log_data=LU(cost=7), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert str(row.cost) == "7.00"
    # Then 3
    assert events_of(db, m1)[0].metadata_json["changes"][0]["to_value"] == "7.00"
    # Then 4
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 5
    assert evs[0].metadata_json == {"maintenance_log_id": a.id, "changes": [{"field": "cost", "label": "Cost", "from_value": None, "to_value": "7.00"}]}


# [claude] MMLM-U-72
@pytest.mark.xfail(strict=True, reason="BUG-1157: Maintenance log cost with too many digits or decimals accepted; the activity entry records it as typed")
def test_mmlm_u_72__cost_7_on_a_log_already_negative_the_entry_shows_the_stored_form(db, w1, u2, m1, mk_log):
    """MMLM-U-72 — cost 7 on a log already negative: the entry shows the stored form.
    Rules: `update_log` R12a [BUG-1157]"""
    a = mk_log(cost=Decimal("-5.00"))
    result = M.update_log(db, log_id=a.id, log_data=LU(cost=7), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert str(row.cost) == "7.00"
    # Then 3
    assert events_of(db, m1)[0].metadata_json["changes"][0]["to_value"] == "7.00"
    # Then 4
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 5
    assert evs[0].metadata_json == {"maintenance_log_id": a.id, "changes": [{"field": "cost", "label": "Cost", "from_value": "-5.00", "to_value": "7.00"}]}


# [claude] MMLM-U-73
def test_mmlm_u_73__cost_7_on_5_00_the_log_its_stamp_and_the_entry_s_old_value_hold_whatev(db, w1, u2, m1, mk_log):
    """MMLM-U-73 — cost 7 on 5.00: the log, its stamp and the entry's old value hold whatever the form.
    Rules: `update_log` R12a, `update_log` R10"""
    a = mk_log(cost=Decimal("5.00"))
    result = M.update_log(db, log_id=a.id, log_data=LU(cost=7), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert str(row.cost) == "7.00"
    # Then 3
    row = reread(db, a)
    assert row.updated_by == u2.id
    # Then 4
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 5
    assert events_of(db, m1)[0].metadata_json["changes"][0]["from_value"] == "5.00"


# [claude] MMLM-U-74
def test_mmlm_u_74__the_limit_in_two_decimal_form_is_recorded_as_it_stands(db, w1, u2, m1, mk_log):
    """MMLM-U-74 — the limit in two-decimal form is recorded as it stands.
    Rules: `update_log` R12a"""
    a = mk_log(cost=Decimal("5.00"))
    result = M.update_log(db, log_id=a.id, log_data=LU(cost=Decimal("9999999999999.99")), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert str(row.cost) == "9999999999999.99"
    # Then 3
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 4
    assert evs[0].metadata_json == {"maintenance_log_id": a.id, "changes": [{"field": "cost", "label": "Cost", "from_value": "5.00", "to_value": "9999999999999.99"}]}


# [claude] MMLM-U-75
def test_mmlm_u_75__cost_0_01_is_accepted_and_stored_as_0_01(db, w1, u2, m1, mk_log):
    """MMLM-U-75 — cost 0.01 is accepted and stored as 0.01.
    Rules: `update_log` R14, `update_log` R6"""
    a = mk_log(cost=Decimal("1.00"))
    result = M.update_log(db, log_id=a.id, log_data=LU(cost=Decimal("0.01")), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert str(row.cost) == "0.01"
    # Then 3
    evs = events_of(db, m1)
    assert len(evs) == 1


# [claude] MMLM-U-76
def test_mmlm_u_76__cost_5_is_accepted_and_stored_as_5_00(db, w1, u2, m1, mk_log):
    """MMLM-U-76 — cost 5 is accepted and stored as 5.00.
    Rules: `update_log` R14, `update_log` R6"""
    a = mk_log(cost=Decimal("1.00"))
    result = M.update_log(db, log_id=a.id, log_data=LU(cost=5), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert str(row.cost) == "5.00"
    # Then 3
    evs = events_of(db, m1)
    assert len(evs) == 1


# [claude] MMLM-U-77
def test_mmlm_u_77__cost_5_1_is_accepted_and_stored_as_5_10(db, w1, u2, m1, mk_log):
    """MMLM-U-77 — cost 5.1 is accepted and stored as 5.10.
    Rules: `update_log` R14, `update_log` R6"""
    a = mk_log(cost=Decimal("1.00"))
    result = M.update_log(db, log_id=a.id, log_data=LU(cost=5.1), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert str(row.cost) == "5.10"
    # Then 3
    evs = events_of(db, m1)
    assert len(evs) == 1


# [claude] MMLM-U-78
def test_mmlm_u_78__cost_5_00_is_accepted_and_stored_as_5_00(db, w1, u2, m1, mk_log):
    """MMLM-U-78 — cost 5.00 is accepted and stored as 5.00.
    Rules: `update_log` R14, `update_log` R6"""
    a = mk_log(cost=Decimal("1.00"))
    result = M.update_log(db, log_id=a.id, log_data=LU(cost=Decimal("5.00")), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert str(row.cost) == "5.00"
    # Then 3
    evs = events_of(db, m1)
    assert len(evs) == 1


# [claude] MMLM-U-79
def test_mmlm_u_79__cost_5_000_is_accepted_and_stored_as_5_00(db, w1, u2, m1, mk_log):
    """MMLM-U-79 — cost 5.000 is accepted and stored as 5.00.
    Rules: `update_log` R14, `update_log` R6"""
    a = mk_log(cost=Decimal("1.00"))
    result = M.update_log(db, log_id=a.id, log_data=LU(cost=Decimal("5.000")), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert str(row.cost) == "5.00"
    # Then 3
    evs = events_of(db, m1)
    assert len(evs) == 1


# [claude] MMLM-U-80
def test_mmlm_u_80__cost_0_is_accepted_and_stored_as_0_00(db, w1, u2, m1, mk_log):
    """MMLM-U-80 — cost -0 is accepted and stored as 0.00.
    Rules: `update_log` R14, `update_log` R6"""
    a = mk_log(cost=Decimal("1.00"))
    result = M.update_log(db, log_id=a.id, log_data=LU(cost=Decimal("-0")), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert str(row.cost) == "0.00"
    # Then 3
    evs = events_of(db, m1)
    assert len(evs) == 1


# [claude] MMLM-U-81
def test_mmlm_u_81__cost_9999999999999_is_accepted_and_stored_as_9999999999999_00(db, w1, u2, m1, mk_log):
    """MMLM-U-81 — cost 9999999999999 is accepted and stored as 9999999999999.00.
    Rules: `update_log` R14, `update_log` R6"""
    a = mk_log(cost=Decimal("1.00"))
    result = M.update_log(db, log_id=a.id, log_data=LU(cost=Decimal("9999999999999")), workspace_id=w1.id, user_id=u2.id)  # noqa: FURB157

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert str(row.cost) == "9999999999999.00"
    # Then 3
    evs = events_of(db, m1)
    assert len(evs) == 1


# [claude] MMLM-U-82
def test_mmlm_u_82__cost_9999999999999_990_is_accepted_and_stored_as_9999999999999_99(db, w1, u2, m1, mk_log):
    """MMLM-U-82 — cost 9999999999999.990 is accepted and stored as 9999999999999.99.
    Rules: `update_log` R14, `update_log` R6"""
    a = mk_log(cost=Decimal("1.00"))
    result = M.update_log(db, log_id=a.id, log_data=LU(cost=Decimal("9999999999999.990")), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert str(row.cost) == "9999999999999.99"
    # Then 3
    evs = events_of(db, m1)
    assert len(evs) == 1


# [claude] MMLM-U-83
@pytest.mark.xfail(strict=True, reason="BUG-1158: Negative maintenance log cost accepted")
def test_mmlm_u_83__cost_5_is_refused_by_the_schema(db, m1, mk_log):
    """MMLM-U-83 — cost -5 is refused by the schema.
    Rules: `update_log` R13b [BUG-1158], `update_log` Errors row 3"""
    a = mk_log(cost=Decimal("5.00"))
    before_a = snap_before(db, a)
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LU(cost=Decimal("-5"))  # noqa: FURB157

    # Then 2
    assert snap(db, a) == before_a
    # Then 3
    assert written(db) == before
    # Then 4
    assert len(events_of(db, m1)) == 0


# [claude] MMLM-U-84
@pytest.mark.xfail(strict=True, reason="BUG-1158: Negative maintenance log cost accepted")
def test_mmlm_u_84__cost_0_01_is_refused_by_the_schema(db, m1, mk_log):
    """MMLM-U-84 — cost -0.01 is refused by the schema.
    Rules: `update_log` R13b [BUG-1158], `update_log` Errors row 3"""
    a = mk_log(cost=Decimal("5.00"))
    before_a = snap_before(db, a)
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LU(cost=Decimal("-0.01"))

    # Then 2
    assert snap(db, a) == before_a
    # Then 3
    assert written(db) == before
    # Then 4
    assert len(events_of(db, m1)) == 0


# [claude] MMLM-U-85
@pytest.mark.xfail(strict=True, reason="BUG-1157: Maintenance log cost with too many digits or decimals accepted; the activity entry records it as typed")
def test_mmlm_u_85__cost_10000000000000_is_refused_by_the_schema(db, m1, mk_log):
    """MMLM-U-85 — cost 10000000000000 is refused by the schema.
    Rules: `update_log` R14 [BUG-1157], `update_log` Errors row 3"""
    a = mk_log(cost=Decimal("5.00"))
    before_a = snap_before(db, a)
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LU(cost=Decimal("10000000000000"))  # noqa: FURB157

    # Then 2
    assert snap(db, a) == before_a
    # Then 3
    assert written(db) == before
    # Then 4
    assert len(events_of(db, m1)) == 0


# [claude] MMLM-U-86
@pytest.mark.xfail(strict=True, reason="BUG-1157: Maintenance log cost with too many digits or decimals accepted; the activity entry records it as typed")
def test_mmlm_u_86__cost_10000000000000_00_is_refused_by_the_schema(db, m1, mk_log):
    """MMLM-U-86 — cost 10000000000000.00 is refused by the schema.
    Rules: `update_log` R14 [BUG-1157], `update_log` Errors row 3"""
    a = mk_log(cost=Decimal("5.00"))
    before_a = snap_before(db, a)
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LU(cost=Decimal("10000000000000.00"))

    # Then 2
    assert snap(db, a) == before_a
    # Then 3
    assert written(db) == before
    # Then 4
    assert len(events_of(db, m1)) == 0


# [claude] MMLM-U-87
@pytest.mark.xfail(strict=True, reason="BUG-1157: Maintenance log cost with too many digits or decimals accepted; the activity entry records it as typed")
def test_mmlm_u_87__cost_1e_13_is_refused_by_the_schema(db, m1, mk_log):
    """MMLM-U-87 — cost 1E+13 is refused by the schema.
    Rules: `update_log` R14 [BUG-1157], `update_log` Errors row 3"""
    a = mk_log(cost=Decimal("5.00"))
    before_a = snap_before(db, a)
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LU(cost=Decimal("1E+13"))

    # Then 2
    assert snap(db, a) == before_a
    # Then 3
    assert written(db) == before
    # Then 4
    assert len(events_of(db, m1)) == 0


# [claude] MMLM-U-88
@pytest.mark.xfail(strict=True, reason="BUG-1157: Maintenance log cost with too many digits or decimals accepted; the activity entry records it as typed")
def test_mmlm_u_88__cost_1e20_is_refused_by_the_schema(db, m1, mk_log):
    """MMLM-U-88 — cost 1e20 is refused by the schema.
    Rules: `update_log` R14 [BUG-1157], `update_log` Errors row 3"""
    a = mk_log(cost=Decimal("5.00"))
    before_a = snap_before(db, a)
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LU(cost=Decimal("1e20"))

    # Then 2
    assert snap(db, a) == before_a
    # Then 3
    assert written(db) == before
    # Then 4
    assert len(events_of(db, m1)) == 0


# [claude] MMLM-U-89
@pytest.mark.xfail(strict=True, reason="BUG-1157: Maintenance log cost with too many digits or decimals accepted; the activity entry records it as typed")
def test_mmlm_u_89__cost_5_001_is_refused_by_the_schema(db, m1, mk_log):
    """MMLM-U-89 — cost 5.001 is refused by the schema.
    Rules: `update_log` R14 [BUG-1157], `update_log` Errors row 3"""
    a = mk_log(cost=Decimal("5.00"))
    before_a = snap_before(db, a)
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LU(cost=Decimal("5.001"))

    # Then 2
    assert snap(db, a) == before_a
    # Then 3
    assert written(db) == before
    # Then 4
    assert len(events_of(db, m1)) == 0


# [claude] MMLM-U-90
@pytest.mark.xfail(strict=True, reason="BUG-1157: Maintenance log cost with too many digits or decimals accepted; the activity entry records it as typed")
def test_mmlm_u_90__cost_5_0010_is_refused_by_the_schema(db, m1, mk_log):
    """MMLM-U-90 — cost 5.0010 is refused by the schema.
    Rules: `update_log` R14 [BUG-1157], `update_log` Errors row 3"""
    a = mk_log(cost=Decimal("5.00"))
    before_a = snap_before(db, a)
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LU(cost=Decimal("5.0010"))

    # Then 2
    assert snap(db, a) == before_a
    # Then 3
    assert written(db) == before
    # Then 4
    assert len(events_of(db, m1)) == 0


# [claude] MMLM-U-91
@pytest.mark.xfail(strict=True, reason="BUG-1157: Maintenance log cost with too many digits or decimals accepted; the activity entry records it as typed")
def test_mmlm_u_91__cost_0_125_is_refused_by_the_schema(db, m1, mk_log):
    """MMLM-U-91 — cost 0.125 is refused by the schema.
    Rules: `update_log` R14 [BUG-1157], `update_log` Errors row 3"""
    a = mk_log(cost=Decimal("5.00"))
    before_a = snap_before(db, a)
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LU(cost=Decimal("0.125"))

    # Then 2
    assert snap(db, a) == before_a
    # Then 3
    assert written(db) == before
    # Then 4
    assert len(events_of(db, m1)) == 0


# [claude] MMLM-U-92
@pytest.mark.xfail(strict=True, reason="BUG-1157: Maintenance log cost with too many digits or decimals accepted; the activity entry records it as typed")
def test_mmlm_u_92__cost_1e_7_is_refused_by_the_schema(db, m1, mk_log):
    """MMLM-U-92 — cost 1E-7 is refused by the schema.
    Rules: `update_log` R14 [BUG-1157], `update_log` Errors row 3"""
    a = mk_log(cost=Decimal("5.00"))
    before_a = snap_before(db, a)
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LU(cost=Decimal("1E-7"))

    # Then 2
    assert snap(db, a) == before_a
    # Then 3
    assert written(db) == before
    # Then 4
    assert len(events_of(db, m1)) == 0


# [claude] MMLM-U-93
@pytest.mark.xfail(strict=True, reason="BUG-1157: Maintenance log cost with too many digits or decimals accepted; the activity entry records it as typed")
def test_mmlm_u_93__cost_9999999999999_995_is_refused_by_the_schema(db, m1, mk_log):
    """MMLM-U-93 — cost 9999999999999.995 is refused by the schema.
    Rules: `update_log` R14 [BUG-1157], `update_log` Errors row 3"""
    a = mk_log(cost=Decimal("5.00"))
    before_a = snap_before(db, a)
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LU(cost=Decimal("9999999999999.995"))

    # Then 2
    assert snap(db, a) == before_a
    # Then 3
    assert written(db) == before
    # Then 4
    assert len(events_of(db, m1)) == 0


# [claude] MMLM-U-94
def test_mmlm_u_94__a_log_already_negative_is_edited_to_0_00_like_any_other_change(db, w1, u2, m1, mk_log):
    """MMLM-U-94 — a log already negative is edited to 0.00 like any other change.
    Rules: `update_log` R13b"""
    a = mk_log(cost=Decimal("-5.00"))
    result = M.update_log(db, log_id=a.id, log_data=LU(cost=Decimal("0.00")), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert str(row.cost) == "0.00"
    # Then 3
    row = reread(db, a)
    assert row.updated_by == u2.id
    # Then 4
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 5
    assert evs[0].metadata_json == {"maintenance_log_id": a.id, "changes": [{"field": "cost", "label": "Cost", "from_value": "-5.00", "to_value": "0.00"}]}


# [claude] MMLM-U-95
def test_mmlm_u_95__a_log_already_negative_is_edited_to_7_50_like_any_other_change(db, w1, u2, m1, mk_log):
    """MMLM-U-95 — a log already negative is edited to 7.50 like any other change.
    Rules: `update_log` R13b"""
    a = mk_log(cost=Decimal("-5.00"))
    result = M.update_log(db, log_id=a.id, log_data=LU(cost=Decimal("7.50")), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert str(row.cost) == "7.50"
    # Then 3
    row = reread(db, a)
    assert row.updated_by == u2.id
    # Then 4
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 5
    assert evs[0].metadata_json == {"maintenance_log_id": a.id, "changes": [{"field": "cost", "label": "Cost", "from_value": "-5.00", "to_value": "7.50"}]}


# [claude] MMLM-U-96
def test_mmlm_u_96__a_log_already_negative_can_have_another_field_edited_its_cost_stays(db, w1, u2, m1, mk_log):
    """MMLM-U-96 — a log already negative can have another field edited: its cost stays.
    Rules: `update_log` R13b, `update_log` R6"""
    a = mk_log(cost=Decimal("-5.00"))
    result = M.update_log(db, log_id=a.id, log_data=LU(summary="New text"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.summary == "New text"
    # Then 3
    row = reread(db, a)
    assert str(row.cost) == "-5.00"
    # Then 4
    evs = events_of(db, m1)
    assert len(evs) == 1


# [claude] MMLM-U-97
def test_mmlm_u_97__cost_nan_is_refused_by_the_schema(db, mk_log):
    """MMLM-U-97 — cost NaN is refused by the schema.
    Rules: `update_log` Inputs"""
    a = mk_log()
    before_a = snap_before(db, a)
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LU(cost=Decimal("NaN"))

    # Then 2
    assert snap(db, a) == before_a
    # Then 3
    assert written(db) == before


# [claude] MMLM-U-98
def test_mmlm_u_98__cost_infinity_is_refused_by_the_schema(db, mk_log):
    """MMLM-U-98 — cost Infinity is refused by the schema.
    Rules: `update_log` Inputs"""
    a = mk_log()
    before_a = snap_before(db, a)
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LU(cost=Decimal("Infinity"))

    # Then 2
    assert snap(db, a) == before_a
    # Then 3
    assert written(db) == before


# [claude] MMLM-U-99
def test_mmlm_u_99__a_type_name_that_is_no_member_is_refused_by_the_schema(db, mk_log):
    """MMLM-U-99 — a type name that is no member is refused by the schema.
    Rules: `update_log` Inputs"""
    a = mk_log()
    before_a = snap_before(db, a)
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LU(maintenance_type="BOGUS")

    # Then 2
    assert snap(db, a) == before_a
    # Then 3
    assert written(db) == before


# [claude] MMLM-U-100
def test_mmlm_u_100__machine_id_and_updated_by_in_the_body_are_dropped_the_log_s_machine_ca(db, w1, u2, u3, m1, m2, mk_log):
    """MMLM-U-100 — machine_id and updated_by in the body are dropped: the log's machine cannot change.
    Rules: `update_log` Inputs"""
    a = mk_log()
    result = M.update_log(db, log_id=a.id, log_data=LU(machine_id=m2.id, updated_by=u3.id, summary="New text"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.machine_id == m1.id
    assert row.updated_by == u2.id
    # Then 3
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 4
    assert len(events_of(db, m2)) == 0


# [claude] MMLM-U-101
@pytest.mark.xfail(strict=True, reason="BUG-1155: Blank maintenance log summaries accepted; stored untrimmed")
def test_mmlm_u_101__a_padded_summary_is_stored_trimmed_in_the_entry_s_to_value_and_descrip(db, w1, u2, m1, mk_log):
    """MMLM-U-101 — a padded summary is stored trimmed, in the entry's to_value and description too.
    Rules: `update_log` R13 [BUG-1155]"""
    a = mk_log()
    result = M.update_log(db, log_id=a.id, log_data=LU(summary="  pad  "), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.summary == "pad"
    # Then 3
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 4
    assert evs[0].event_type == "maintenance_updated"
    assert evs[0].description == "Maintenance log updated: pad"
    assert evs[0].performed_by == u2.id
    assert evs[0].workspace_id == w1.id
    assert evs[0].machine_id == m1.id
    # Then 5
    assert evs[0].metadata_json == {"maintenance_log_id": a.id, "changes": [{"field": "summary", "label": "Summary", "from_value": "Bearing change", "to_value": "pad"}]}


# [claude] MMLM-U-102
@pytest.mark.xfail(strict=True, reason="BUG-1155: Blank maintenance log summaries accepted; stored untrimmed")
def test_mmlm_u_102__the_stored_summary_sent_with_padding_is_no_change(db, w1, u2, m1, mk_log):
    """MMLM-U-102 — the stored summary sent with padding is no change.
    Rules: `update_log` R13 [BUG-1155], `update_log` R8"""
    a = mk_log()
    result = M.update_log(db, log_id=a.id, log_data=LU(summary="  Bearing change  "), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.summary == "Bearing change"
    # Then 3
    assert len(events_of(db, m1)) == 0


# [claude] MMLM-U-103
def test_mmlm_u_103__inner_whitespace_of_a_summary_is_kept_as_typed(db, w1, u2, m1, mk_log):
    """MMLM-U-103 — inner whitespace of a summary is kept as typed.
    Rules: `update_log` R13"""
    a = mk_log()
    result = M.update_log(db, log_id=a.id, log_data=LU(summary="Bearing  change"), workspace_id=w1.id, user_id=u2.id)  # noqa: F841

    # Then 1
    row = reread(db, a)
    assert row.summary == "Bearing  change"
    # Then 2
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 3
    assert evs[0].event_type == "maintenance_updated"
    assert evs[0].description == "Maintenance log updated: Bearing  change"
    assert evs[0].performed_by == u2.id
    assert evs[0].workspace_id == w1.id
    assert evs[0].machine_id == m1.id


# [claude] MMLM-U-104
@pytest.mark.xfail(strict=True, reason="BUG-1155: Blank maintenance log summaries accepted; stored untrimmed")
def test_mmlm_u_104__an_empty_summary_is_refused_by_the_schema(db, mk_log):
    """MMLM-U-104 — an empty summary is refused by the schema.
    Rules: `update_log` R13 [BUG-1155], `update_log` Errors row 3"""
    a = mk_log()
    before_a = snap_before(db, a)
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LU(summary="")

    # Then 2
    assert snap(db, a) == before_a
    # Then 3
    assert written(db) == before


# [claude] MMLM-U-105
@pytest.mark.xfail(strict=True, reason="BUG-1155: Blank maintenance log summaries accepted; stored untrimmed")
def test_mmlm_u_105__a_whitespace_only_summary_is_refused_by_the_schema(db, mk_log):
    """MMLM-U-105 — a whitespace-only summary is refused by the schema.
    Rules: `update_log` R13 [BUG-1155], `update_log` Errors row 3"""
    a = mk_log()
    before_a = snap_before(db, a)
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LU(summary="   ")

    # Then 2
    assert snap(db, a) == before_a
    # Then 3
    assert written(db) == before


# [claude] MMLM-U-106
def test_mmlm_u_106__a_one_character_summary_is_accepted_the_other_side_of_empty(db, w1, u2, mk_log):
    """MMLM-U-106 — a one-character summary is accepted: the other side of empty.
    Rules: `update_log` R13"""
    a = mk_log()
    result = M.update_log(db, log_id=a.id, log_data=LU(summary="a"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.summary == "a"


# [claude] MMLM-U-107
@pytest.mark.xfail(strict=True, reason="BUG-1156: Maintenance log performed_by untrimmed, blank counts as a value, over-long crashes")
def test_mmlm_u_107__a_padded_performed_by_is_stored_trimmed(db, w1, u2, m1, mk_log):
    """MMLM-U-107 — a padded performed_by is stored trimmed.
    Rules: `update_log` R13a [BUG-1156]"""
    a = mk_log()
    result = M.update_log(db, log_id=a.id, log_data=LU(performed_by="  Rahim  "), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.performed_by == "Rahim"
    # Then 3
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 4
    assert evs[0].metadata_json == {"maintenance_log_id": a.id, "changes": [{"field": "performed_by", "label": "Performed by", "from_value": None, "to_value": "Rahim"}]}


# [claude] MMLM-U-108
@pytest.mark.xfail(strict=True, reason="BUG-1156: Maintenance log performed_by untrimmed, blank counts as a value, over-long crashes")
def test_mmlm_u_108__an_empty_performed_by_clears_the_stored_name(db, w1, u2, m1, mk_log):
    """MMLM-U-108 — an empty performed_by clears the stored name.
    Rules: `update_log` R13a [BUG-1156]"""
    a = mk_log(performed_by="Rahim")
    result = M.update_log(db, log_id=a.id, log_data=LU(performed_by=""), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.performed_by is None
    # Then 3
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 4
    assert evs[0].metadata_json == {"maintenance_log_id": a.id, "changes": [{"field": "performed_by", "label": "Performed by", "from_value": "Rahim", "to_value": None}]}


# [claude] MMLM-U-109
@pytest.mark.xfail(strict=True, reason="BUG-1156: Maintenance log performed_by untrimmed, blank counts as a value, over-long crashes")
def test_mmlm_u_109__a_whitespace_only_performed_by_clears_the_stored_name(db, w1, u2, m1, mk_log):
    """MMLM-U-109 — a whitespace-only performed_by clears the stored name.
    Rules: `update_log` R13a [BUG-1156]"""
    a = mk_log(performed_by="Rahim")
    result = M.update_log(db, log_id=a.id, log_data=LU(performed_by="   "), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.performed_by is None
    # Then 3
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 4
    assert evs[0].metadata_json == {"maintenance_log_id": a.id, "changes": [{"field": "performed_by", "label": "Performed by", "from_value": "Rahim", "to_value": None}]}


# [claude] MMLM-U-110
@pytest.mark.xfail(strict=True, reason="BUG-1156: Maintenance log performed_by untrimmed, blank counts as a value, over-long crashes")
def test_mmlm_u_110__an_empty_performed_by_on_an_empty_field_is_no_change(db, w1, u2, m1, mk_log):
    """MMLM-U-110 — an empty performed_by on an empty field is no change.
    Rules: `update_log` R13a [BUG-1156], `update_log` R8"""
    a = mk_log()
    result = M.update_log(db, log_id=a.id, log_data=LU(performed_by=""), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.performed_by is None
    # Then 3
    assert len(events_of(db, m1)) == 0


# [claude] MMLM-U-111
@pytest.mark.xfail(strict=True, reason="BUG-1156: Maintenance log performed_by untrimmed, blank counts as a value, over-long crashes")
def test_mmlm_u_111__the_stored_name_sent_with_padding_is_no_change(db, w1, u2, m1, mk_log):
    """MMLM-U-111 — the stored name sent with padding is no change.
    Rules: `update_log` R13a [BUG-1156], `update_log` R8"""
    a = mk_log(performed_by="Rahim")
    result = M.update_log(db, log_id=a.id, log_data=LU(performed_by="  Rahim  "), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.performed_by == "Rahim"
    # Then 3
    assert len(events_of(db, m1)) == 0


# [claude] MMLM-U-112
def test_mmlm_u_112__performed_by_of_255_characters_is_stored(db, w1, u2, mk_log):
    """MMLM-U-112 — performed_by of 255 characters is stored.
    Rules: `update_log` R14"""
    a = mk_log()
    result = M.update_log(db, log_id=a.id, log_data=LU(performed_by="x" * 255), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.performed_by == "x" * 255


# [claude] MMLM-U-113
@pytest.mark.xfail(strict=True, reason="BUG-1156: Maintenance log performed_by untrimmed, blank counts as a value, over-long crashes")
def test_mmlm_u_113__255_characters_inside_surrounding_spaces_are_accepted_and_stored_trimm(db, w1, u2, mk_log):
    """MMLM-U-113 — 255 characters inside surrounding spaces are accepted and stored trimmed.
    Rules: `update_log` R14 [BUG-1156]"""
    a = mk_log()
    result = M.update_log(db, log_id=a.id, log_data=LU(performed_by=" " + "x" * 255 + " "), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.performed_by == "x" * 255


# [claude] MMLM-U-114
@pytest.mark.xfail(strict=True, reason="BUG-1156: Maintenance log performed_by untrimmed, blank counts as a value, over-long crashes")
def test_mmlm_u_114__256_characters_are_refused_by_the_schema(db, m1, mk_log):
    """MMLM-U-114 — 256 characters are refused by the schema.
    Rules: `update_log` R14 [BUG-1156], `update_log` Errors row 3"""
    a = mk_log(performed_by="Rahim")
    before_a = snap_before(db, a)
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LU(performed_by="x" * 256)

    # Then 2
    assert snap(db, a) == before_a
    # Then 3
    assert written(db) == before
    # Then 4
    assert len(events_of(db, m1)) == 0


# [claude] MMLM-U-115
@pytest.mark.xfail(strict=True, reason="BUG-1156: Maintenance log performed_by untrimmed, blank counts as a value, over-long crashes")
def test_mmlm_u_115__256_characters_inside_surrounding_spaces_are_refused_by_the_schema(db, m1, mk_log):
    """MMLM-U-115 — 256 characters inside surrounding spaces are refused by the schema.
    Rules: `update_log` R14 [BUG-1156], `update_log` Errors row 3"""
    a = mk_log(performed_by="Rahim")
    before_a = snap_before(db, a)
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LU(performed_by=" " + "x" * 256 + " ")

    # Then 2
    assert snap(db, a) == before_a
    # Then 3
    assert written(db) == before
    # Then 4
    assert len(events_of(db, m1)) == 0


# [claude] MMLM-U-116
def test_mmlm_u_116__a_date_in_1900_is_stored_and_listed_no_bound(db, w1, u2, m1, mk_log):
    """MMLM-U-116 — a date in 1900 is stored and listed: no bound.
    Rules: `update_log` R13c"""
    a = mk_log()
    result = M.update_log(db, log_id=a.id, log_data=LU(maintenance_date=date(1900, 1, 1)), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.maintenance_date == date(1900, 1, 1)
    # Then 3
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 4
    assert evs[0].metadata_json == {"maintenance_log_id": a.id, "changes": [{"field": "maintenance_date", "label": "Maintenance date", "from_value": "2026-03-01", "to_value": "1900-01-01"}]}


# [claude] MMLM-U-117
def test_mmlm_u_117__a_date_in_2099_is_stored_and_listed_no_bound(db, w1, u2, m1, mk_log):
    """MMLM-U-117 — a date in 2099 is stored and listed: no bound.
    Rules: `update_log` R13c"""
    a = mk_log()
    result = M.update_log(db, log_id=a.id, log_data=LU(maintenance_date=date(2099, 1, 1)), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.maintenance_date == date(2099, 1, 1)
    # Then 3
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 4
    assert evs[0].metadata_json == {"maintenance_log_id": a.id, "changes": [{"field": "maintenance_date", "label": "Maintenance date", "from_value": "2026-03-01", "to_value": "2099-01-01"}]}


# [claude] MMLM-U-118
def test_mmlm_u_118__an_unknown_user_with_a_change_foreign_key_error_log_as_it_was_no_entry(db, w1, mk_log):
    """MMLM-U-118 — an unknown user with a change: foreign key error, log as it was, no entry.
    Rules: `update_log` R15, `update_log` Errors row 4"""
    a = mk_log()
    before_a = snap_before(db, a)
    before = written(db)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            M.update_log(db, log_id=a.id, log_data=LU(summary="New text"), workspace_id=w1.id, user_id=MISSING)

    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert exc.value.orig.diag.constraint_name == "machine_maintenance_logs_updated_by_fkey"
    # Then 4
    assert snap(db, a) == before_a
    # Then 5
    assert written(db) == before


# [claude] MMLM-U-119
def test_mmlm_u_119__the_returned_object_is_the_instance_read_and_keeps_cost_as_given_until(db, w1, u2, mk_log):
    """MMLM-U-119 — the returned object is the instance read and keeps cost as given until a refresh.
    Rules: `update_log` R16"""
    a = mk_log(cost=Decimal("5.00"))
    result = M.update_log(db, log_id=a.id, log_data=LU(cost=Decimal("7.000")), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    assert str(result.cost) == "7.000"
    # Then 3
    db.refresh(result)
    # Then 4
    assert str(result.cost) == "7.00"


# [claude] MMLM-U-120
def test_mmlm_u_120__flushed_never_committed(db, w1, u2, m1, mk_log, monkeypatch):
    """MMLM-U-120 — flushed, never committed.
    Rules: `update_log` R17, `update_log` Side effects"""
    a = mk_log()
    sp = db.begin_nested()
    spy = commit_spy(db, monkeypatch)
    result = M.update_log(db, log_id=a.id, log_data=LU(summary="New text"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.summary == "New text"
    # Then 3
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 4
    sp.rollback()
    row = reread(db, a)
    assert row.summary == "Bearing change"
    assert row.updated_by is None
    assert row.updated_at is None
    # Then 5
    assert len(events_of(db, m1)) == 0
    # Then 6
    assert not spy.called


# [claude] MMLM-U-121
def test_mmlm_u_121__a_summary_of_100_000_characters_is_stored_and_copied_into_the_entry_no(db, w1, u2, m1, mk_log):
    """MMLM-U-121 — a summary of 100 000 characters is stored and copied into the entry: no length limit.
    Rules: `update_log` R6, `update_log` Inputs"""
    a = mk_log()
    result = M.update_log(db, log_id=a.id, log_data=LU(summary="S" * 100000), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.summary == "S" * 100000
    # Then 3
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 4
    assert evs[0].description == "Maintenance log updated: " + "S" * 100000


# [claude] MMLM-G-01
def test_mmlm_g_01__a_live_log_of_the_workspace_is_returned(db, w1, mk_log):
    """MMLM-G-01 — a live log of the workspace is returned.
    Rules: `get_log` R1, `get_log` Returns"""
    a = mk_log(cost=Decimal("5.00"), performed_by="Rahim")
    result = M.get_log(db, log_id=a.id, workspace_id=w1.id)

    # Then 1
    assert result is a
    # Then 2
    assert isinstance(result, MachineMaintenanceLog)
    # Then 3
    assert result.summary == "Bearing change"
    assert result.cost == Decimal("5.00")
    assert result.performed_by == "Rahim"


# [claude] MMLM-G-02
def test_mmlm_g_02__positional_arguments_work_as_the_service_calls_it(db, w1, mk_log):
    """MMLM-G-02 — positional arguments work, as the service calls it.
    Rules: `get_log` R1"""
    a = mk_log()
    result = M.get_log(db, a.id, w1.id)

    # Then 1
    assert result is a


# [claude] MMLM-G-03
def test_mmlm_g_03__a_log_of_another_workspace_gets_the_404(db, w2, mk_log):
    """MMLM-G-03 — a log of another workspace gets the 404.
    Rules: `get_log` R2, `get_log` Errors row 1"""
    a = mk_log()
    before_a = snap_before(db, a)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_log(db, log_id=a.id, workspace_id=w2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Maintenance log with ID {a.id} not found"
    # Then 4
    assert snap(db, a) == before_a
    # Then 5
    assert written(db) == before


# [claude] MMLM-G-04
def test_mmlm_g_04__a_soft_deleted_log_of_another_workspace_gets_the_same_404(db, w2, mk_log):
    """MMLM-G-04 — a soft-deleted log of another workspace gets the same 404.
    Rules: `get_log` R2, `get_log` Errors row 1"""
    a = mk_log(gone=True)
    before_a = snap_before(db, a)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_log(db, log_id=a.id, workspace_id=w2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Maintenance log with ID {a.id} not found"
    # Then 4
    assert snap(db, a) == before_a
    # Then 5
    assert written(db) == before


# [claude] MMLM-G-05
def test_mmlm_g_05__an_unknown_id_gets_the_same_404(db, w1, mk_log):
    """MMLM-G-05 — an unknown id gets the same 404.
    Rules: `get_log` R2, `get_log` Errors row 1"""
    mk_log()
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_log(db, log_id=MISSING, workspace_id=w1.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Maintenance log with ID 999999999 not found"
    # Then 4
    assert written(db) == before


# [claude] MMLM-G-06
def test_mmlm_g_06__id_0_gets_the_same_404(db, w1, mk_log):
    """MMLM-G-06 — id 0 gets the same 404.
    Rules: `get_log` R2, `get_log` Errors row 1"""
    mk_log()
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_log(db, log_id=0, workspace_id=w1.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Maintenance log with ID 0 not found"
    # Then 4
    assert written(db) == before


# [claude] MMLM-G-07
def test_mmlm_g_07__a_negative_id_gets_the_same_404(db, w1, mk_log):
    """MMLM-G-07 — a negative id gets the same 404.
    Rules: `get_log` R2, `get_log` Errors row 1"""
    mk_log()
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_log(db, log_id=-1, workspace_id=w1.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Maintenance log with ID -1 not found"
    # Then 4
    assert written(db) == before


# [claude] MMLM-G-08
@pytest.mark.xfail(strict=True, reason="BUG-1150: get_log returns soft-deleted maintenance logs")
def test_mmlm_g_08__a_soft_deleted_log_is_hidden_by_default(db, w1, mk_log):
    """MMLM-G-08 — a soft-deleted log is hidden by default.
    Rules: `get_log` R3 [BUG-1150], `get_log` Errors row 1"""
    a = mk_log(gone=True)
    before_a = snap_before(db, a)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_log(db, log_id=a.id, workspace_id=w1.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Maintenance log with ID {a.id} not found"
    # Then 4
    assert snap(db, a) == before_a
    # Then 5
    assert written(db) == before


# [claude] MMLM-G-09
@pytest.mark.xfail(strict=True, reason="BUG-1150: get_log returns soft-deleted maintenance logs")
def test_mmlm_g_09__a_soft_deleted_log_of_a_soft_deleted_machine_is_hidden_too_the_log_s_o(db, w1, md, mk_log):
    """MMLM-G-09 — a soft-deleted log of a soft-deleted machine is hidden too: the log's own flag decides.
    Rules: `get_log` R3 [BUG-1150], `get_log` Errors row 1"""
    a = mk_log(machine_id=md.id, gone=True)
    before_a = snap_before(db, a)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_log(db, log_id=a.id, workspace_id=w1.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Maintenance log with ID {a.id} not found"
    # Then 4
    assert snap(db, a) == before_a


# [claude] MMLM-G-10
@pytest.mark.xfail(strict=True, reason="BUG-1150: get_log returns soft-deleted maintenance logs")
def test_mmlm_g_10__include_deleted_false_hides_it_as_the_default_does(db, w1, mk_log):
    """MMLM-G-10 — include_deleted=False hides it as the default does.
    Rules: `get_log` R3 [BUG-1150], `get_log` Errors row 1"""
    a = mk_log(gone=True)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_log(db, log_id=a.id, workspace_id=w1.id, include_deleted=False)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Maintenance log with ID {a.id} not found"


# [claude] MMLM-G-11
@pytest.mark.xfail(strict=True, reason="BUG-1150: get_log returns soft-deleted maintenance logs")
def test_mmlm_g_11__include_deleted_true_returns_a_soft_deleted_log(db, w1, mk_log):
    """MMLM-G-11 — include_deleted=True returns a soft-deleted log.
    Rules: `get_log` R3a [BUG-1150]"""
    a = mk_log(gone=True)
    before_a = snap_before(db, a)
    result = M.get_log(db, log_id=a.id, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert result is a
    # Then 2
    assert result.is_deleted is True
    # Then 3
    assert snap(db, a) == before_a


# [claude] MMLM-G-12
@pytest.mark.xfail(strict=True, reason="BUG-1150: get_log returns soft-deleted maintenance logs")
def test_mmlm_g_12__include_deleted_true_returns_a_live_log_as_well(db, w1, mk_log):
    """MMLM-G-12 — include_deleted=True returns a live log as well.
    Rules: `get_log` R3a [BUG-1150]"""
    a = mk_log()
    result = M.get_log(db, log_id=a.id, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert result is a


# [claude] MMLM-G-13
@pytest.mark.xfail(strict=True, reason="BUG-1150: get_log returns soft-deleted maintenance logs")
def test_mmlm_g_13__include_deleted_true_does_not_reach_another_workspace(db, w2, mk_log):
    """MMLM-G-13 — include_deleted=True does not reach another workspace.
    Rules: `get_log` R3a [BUG-1150], `get_log` R2, `get_log` Errors row 1"""
    a = mk_log(gone=True)
    before_a = snap_before(db, a)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_log(db, log_id=a.id, workspace_id=w2.id, include_deleted=True)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Maintenance log with ID {a.id} not found"
    # Then 4
    assert snap(db, a) == before_a


# [claude] MMLM-G-14
@pytest.mark.xfail(strict=True, reason="BUG-1150: get_log returns soft-deleted maintenance logs")
def test_mmlm_g_14__include_deleted_true_on_an_unknown_id_gets_the_404(db, w1, mk_log):
    """MMLM-G-14 — include_deleted=True on an unknown id gets the 404.
    Rules: `get_log` R3a [BUG-1150], `get_log` R2, `get_log` Errors row 1"""
    mk_log()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_log(db, log_id=MISSING, workspace_id=w1.id, include_deleted=True)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Maintenance log with ID 999999999 not found"


# [claude] MMLM-G-15
def test_mmlm_g_15__an_inactive_log_is_returned(db, w1, mk_log):
    """MMLM-G-15 — an inactive log is returned.
    Rules: `get_log` R4"""
    a = mk_log(is_active=False)
    result = M.get_log(db, log_id=a.id, workspace_id=w1.id)

    # Then 1
    assert result is a


# [claude] MMLM-G-16
def test_mmlm_g_16__a_log_of_a_soft_deleted_machine_is_returned_history_stays_readable(db, w1, md, mk_log):
    """MMLM-G-16 — a log of a soft-deleted machine is returned: history stays readable.
    Rules: `get_log` R5"""
    a = mk_log(machine_id=md.id)
    before = written(db)
    result = M.get_log(db, log_id=a.id, workspace_id=w1.id)

    # Then 1
    assert result is a
    # Then 2
    assert written(db) == before


# [claude] MMLM-G-17
def test_mmlm_g_17__a_log_of_a_machine_in_a_soft_deleted_factory_is_returned_history_stays(db, w1, mf, mk_log):
    """MMLM-G-17 — a log of a machine in a soft-deleted factory is returned: history stays readable.
    Rules: `get_log` R5"""
    a = mk_log(machine_id=mf.id)
    before = written(db)
    result = M.get_log(db, log_id=a.id, workspace_id=w1.id)

    # Then 1
    assert result is a
    # Then 2
    assert written(db) == before


# [claude] MMLM-G-18
def test_mmlm_g_18__a_log_of_an_inactive_machine_is_returned_history_stays_readable(db, w1, ma, mk_log):
    """MMLM-G-18 — a log of an inactive machine is returned: history stays readable.
    Rules: `get_log` R5"""
    a = mk_log(machine_id=ma.id)
    before = written(db)
    result = M.get_log(db, log_id=a.id, workspace_id=w1.id)

    # Then 1
    assert result is a
    # Then 2
    assert written(db) == before


# [claude] MMLM-G-19
def test_mmlm_g_19__a_log_of_a_machine_in_an_inactive_factory_is_returned_history_stays_re(db, w1, mg, mk_log):
    """MMLM-G-19 — a log of a machine in an inactive factory is returned: history stays readable.
    Rules: `get_log` R5"""
    a = mk_log(machine_id=mg.id)
    before = written(db)
    result = M.get_log(db, log_id=a.id, workspace_id=w1.id)

    # Then 1
    assert result is a
    # Then 2
    assert written(db) == before


# [claude] MMLM-G-20
@pytest.mark.xfail(strict=True, reason="BUG-1101: A stored maintenance log linked to another workspace's machine shows that machine's id")
def test_mmlm_g_20__a_log_on_another_workspace_s_machine_gets_the_404(db, w1, m9, mk_log):
    """MMLM-G-20 — a log on another workspace's machine gets the 404.
    Rules: `get_log` R6 [BUG-1101], `get_log` Errors row 1"""
    # A row of W1 on a W2 machine, invalid data.
    x = mk_log(machine_id=m9.id)
    before_x = snap_before(db, x)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_log(db, log_id=x.id, workspace_id=w1.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Maintenance log with ID {x.id} not found"
    # Then 4
    assert snap(db, x) == before_x
    # Then 5
    assert written(db) == before


# [claude] MMLM-G-21
@pytest.mark.xfail(strict=True, reason="BUG-1101, BUG-1150: needs both fixes. BUG-1150 adds include_deleted to get_log; BUG-1101 hides a log on another workspace's machine")
def test_mmlm_g_21__the_same_row_gets_the_404_with_include_deleted_true_too(db, w1, m9, mk_log):
    """MMLM-G-21 — the same row gets the 404 with include_deleted=True too.
    Rules: `get_log` R6 [BUG-1101], `get_log` Errors row 1"""
    # A row of W1 on a W2 machine, invalid data.
    x = mk_log(machine_id=m9.id)
    before_x = snap_before(db, x)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_log(db, log_id=x.id, workspace_id=w1.id, include_deleted=True)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Maintenance log with ID {x.id} not found"
    # Then 4
    assert snap(db, x) == before_x


# [claude] MMLM-G-22
@pytest.mark.xfail(strict=True, reason="BUG-1101, BUG-1150: needs both fixes. BUG-1150 adds include_deleted to get_log; BUG-1101 hides a log on another workspace's machine")
def test_mmlm_g_22__a_soft_deleted_log_on_another_workspace_s_machine_gets_the_404_with_in(db, w1, m9, mk_log):
    """MMLM-G-22 — a soft-deleted log on another workspace's machine gets the 404 with include_deleted=True.
    Rules: `get_log` R6 [BUG-1101], `get_log` Errors row 1"""
    x = mk_log(machine_id=m9.id, gone=True)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_log(db, log_id=x.id, workspace_id=w1.id, include_deleted=True)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Maintenance log with ID {x.id} not found"


# [claude] MMLM-G-23
def test_mmlm_g_23__the_same_row_asked_for_from_the_machine_s_workspace_gets_the_404(db, w2, m9, mk_log):
    """MMLM-G-23 — the same row asked for from the machine's workspace gets the 404.
    Rules: `get_log` R6, `get_log` Errors row 1"""
    # A row of W1 on a W2 machine, invalid data.
    x = mk_log(machine_id=m9.id)
    before_x = snap_before(db, x)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_log(db, log_id=x.id, workspace_id=w2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Maintenance log with ID {x.id} not found"
    # Then 4
    assert snap(db, x) == before_x


# [claude] MMLM-G-24
def test_mmlm_g_24__the_read_writes_nothing_and_leaves_a_pending_row_pending(db, w1, m1, mk_log, mk_pending):
    """MMLM-G-24 — the read writes nothing and leaves a pending row pending.
    Rules: `get_log` R7, `get_log` Side effects"""
    a = mk_log()
    before_a = snap_before(db, a)
    before = written(db)
    q = mk_pending()
    result = M.get_log(db, log_id=a.id, workspace_id=w1.id)

    # Then 1
    assert result is a
    # Then 2
    assert q in db.new
    # Then 3
    assert a not in db.dirty
    # Then 4
    assert count_rows(db, "machine_maintenance_logs", summary="Pending") == 0
    # Then 5
    assert snap(db, a) == before_a
    # Then 6
    assert written(db) == before
    # Then 7
    assert len(events_of(db, m1)) == 0


# [claude] MMLM-L-01
def test_mmlm_l_01__no_filter_a_list_of_the_live_logs(db, w1, mk_log):
    """MMLM-L-01 — no filter: a list of the live logs.
    Rules: `list_logs` R1, `list_logs` Returns"""
    a = mk_log(maintenance_date=D2)
    b = mk_log()
    result = M.list_logs(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert sorted(ids(result)) == [a.id, b.id]


# [claude] MMLM-L-02
def test_mmlm_l_02__by_machine_a_list_of_the_live_logs(db, w1, m1, mk_log):
    """MMLM-L-02 — by machine: a list of the live logs.
    Rules: `list_logs` R2, `list_logs` Returns"""
    a = mk_log(maintenance_date=D2)
    b = mk_log()
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert sorted(ids(result)) == [a.id, b.id]


# [claude] MMLM-L-03
def test_mmlm_l_03__by_type_a_list_of_the_live_logs(db, w1, mk_log):
    """MMLM-L-03 — by type: a list of the live logs.
    Rules: `list_logs` R3, `list_logs` Returns"""
    a = mk_log(maintenance_date=D2)
    b = mk_log()
    result = M.list_logs(db, workspace_id=w1.id, maintenance_type=REPAIR)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert sorted(ids(result)) == [a.id, b.id]


# [claude] MMLM-L-04
def test_mmlm_l_04__by_machine_and_type_a_list_of_the_live_logs(db, w1, m1, mk_log):
    """MMLM-L-04 — by machine and type: a list of the live logs.
    Rules: `list_logs` R4, `list_logs` Returns"""
    a = mk_log(maintenance_date=D2)
    b = mk_log()
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id, maintenance_type=REPAIR)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert sorted(ids(result)) == [a.id, b.id]


# [claude] MMLM-L-05
def test_mmlm_l_05__the_service_s_keyword_call_works(db, w1, mk_log):
    """MMLM-L-05 — the service's keyword call works.
    Rules: `list_logs` R1"""
    a = mk_log()
    result = M.list_logs(session=db, workspace_id=w1.id, machine_id=None, maintenance_type=None, skip=0, limit=100)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MMLM-L-06
def test_mmlm_l_06__no_filter_spans_machines_and_types(db, w1, m2, mk_log):
    """MMLM-L-06 — no filter spans machines and types.
    Rules: `list_logs` R1"""
    a = mk_log()
    b = mk_log(machine_id=m2.id, maintenance_type=MaintenanceTypeEnum.EMERGENCY)
    result = M.list_logs(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]


# [claude] MMLM-L-07
def test_mmlm_l_07__by_machine_spans_types(db, w1, m1, mk_log):
    """MMLM-L-07 — by machine spans types.
    Rules: `list_logs` R2"""
    a = mk_log()
    b = mk_log(maintenance_type=MaintenanceTypeEnum.EMERGENCY)
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]


# [claude] MMLM-L-08
def test_mmlm_l_08__by_type_spans_machines(db, w1, m2, mk_log):
    """MMLM-L-08 — by type spans machines.
    Rules: `list_logs` R3"""
    a = mk_log()
    b = mk_log(machine_id=m2.id)
    result = M.list_logs(db, workspace_id=w1.id, maintenance_type=REPAIR)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]


# [claude] MMLM-L-09
def test_mmlm_l_09__explicit_none_on_both_means_no_filter(db, w1, m2, mk_log):
    """MMLM-L-09 — explicit None on both means no filter.
    Rules: `list_logs` R1, `list_logs` R5"""
    a = mk_log()
    b = mk_log(machine_id=m2.id, maintenance_type=MaintenanceTypeEnum.EMERGENCY)
    result = M.list_logs(db, workspace_id=w1.id, machine_id=None, maintenance_type=None)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]


# [claude] MMLM-L-10
def test_mmlm_l_10__no_filter_another_workspace_s_log_does_not_appear_although_it_fits_the(db, w1, w2, m9, mk_log):
    """MMLM-L-10 — no filter: another workspace's log does not appear, although it fits the page.
    Rules: `list_logs` R1"""
    a = mk_log()
    mk_log(workspace_id=w2.id, machine_id=m9.id)
    result = M.list_logs(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MMLM-L-11
def test_mmlm_l_11__by_type_another_workspace_s_log_of_that_type_does_not_appear(db, w1, w2, m9, mk_log):
    """MMLM-L-11 — by type: another workspace's log of that type does not appear.
    Rules: `list_logs` R3"""
    a = mk_log()
    mk_log(workspace_id=w2.id, machine_id=m9.id)
    result = M.list_logs(db, workspace_id=w1.id, maintenance_type=REPAIR)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MMLM-L-12
def test_mmlm_l_12__by_machine_a_w2_row_on_that_machine_id_does_not_appear(db, w1, w2, m1, mk_log):
    """MMLM-L-12 — by machine: a W2 row on that machine id does not appear.
    Rules: `list_logs` R2"""
    a = mk_log()
    # A row of W2 on a W1 machine, invalid data.
    mk_log(workspace_id=w2.id)
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MMLM-L-13
def test_mmlm_l_13__by_machine_and_type_a_w2_row_on_that_pair_does_not_appear(db, w1, w2, m1, mk_log):
    """MMLM-L-13 — by machine and type: a W2 row on that pair does not appear.
    Rules: `list_logs` R4"""
    a = mk_log()
    # A row of W2 on a W1 machine, invalid data.
    mk_log(workspace_id=w2.id)
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id, maintenance_type=REPAIR)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MMLM-L-14
def test_mmlm_l_14__by_machine_another_machine_s_log_does_not_appear(db, w1, m1, m2, mk_log):
    """MMLM-L-14 — by machine: another machine's log does not appear.
    Rules: `list_logs` R2"""
    a = mk_log()
    mk_log(machine_id=m2.id)
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MMLM-L-15
def test_mmlm_l_15__by_machine_and_type_that_type_on_another_machine_does_not_appear(db, w1, m1, m2, mk_log):
    """MMLM-L-15 — by machine and type: that type on another machine does not appear.
    Rules: `list_logs` R4"""
    a = mk_log()
    mk_log(machine_id=m2.id)
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id, maintenance_type=REPAIR)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MMLM-L-16
def test_mmlm_l_16__by_type_another_type_does_not_appear(db, w1, mk_log):
    """MMLM-L-16 — by type: another type does not appear.
    Rules: `list_logs` R3"""
    a = mk_log()
    mk_log(maintenance_type=MaintenanceTypeEnum.EMERGENCY)
    result = M.list_logs(db, workspace_id=w1.id, maintenance_type=REPAIR)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MMLM-L-17
def test_mmlm_l_17__by_machine_and_type_another_type_on_that_machine_does_not_appear(db, w1, m1, mk_log):
    """MMLM-L-17 — by machine and type: another type on that machine does not appear.
    Rules: `list_logs` R4"""
    a = mk_log()
    mk_log(maintenance_type=MaintenanceTypeEnum.EMERGENCY)
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id, maintenance_type=REPAIR)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MMLM-L-18
def test_mmlm_l_18__no_filter_a_soft_deleted_log_is_not_returned(db, w1, mk_log):
    """MMLM-L-18 — no filter: a soft-deleted log is not returned.
    Rules: `list_logs` R11"""
    a = mk_log()
    mk_log(gone=True)
    result = M.list_logs(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MMLM-L-19
def test_mmlm_l_19__by_machine_a_soft_deleted_log_is_not_returned(db, w1, m1, mk_log):
    """MMLM-L-19 — by machine: a soft-deleted log is not returned.
    Rules: `list_logs` R11"""
    a = mk_log()
    mk_log(gone=True)
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MMLM-L-20
def test_mmlm_l_20__by_type_a_soft_deleted_log_is_not_returned(db, w1, mk_log):
    """MMLM-L-20 — by type: a soft-deleted log is not returned.
    Rules: `list_logs` R11"""
    a = mk_log()
    mk_log(gone=True)
    result = M.list_logs(db, workspace_id=w1.id, maintenance_type=REPAIR)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MMLM-L-21
def test_mmlm_l_21__by_machine_and_type_a_soft_deleted_log_is_not_returned(db, w1, m1, mk_log):
    """MMLM-L-21 — by machine and type: a soft-deleted log is not returned.
    Rules: `list_logs` R11"""
    a = mk_log()
    mk_log(gone=True)
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id, maintenance_type=REPAIR)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MMLM-L-22
def test_mmlm_l_22__no_filter_a_soft_deleted_log_ahead_of_the_skipped_row_uses_up_no_skip(db, w1, mk_log):
    """MMLM-L-22 — no filter: a soft-deleted log ahead of the skipped row uses up no skip.
    Rules: `list_logs` R11"""
    mk_log(maintenance_date=D3, gone=True)
    mk_log(maintenance_date=D2)
    c = mk_log(maintenance_date=D1)
    result = M.list_logs(db, workspace_id=w1.id, skip=1)

    # Then 1
    assert ids(result) == [c.id]


# [claude] MMLM-L-23
def test_mmlm_l_23__by_machine_a_soft_deleted_log_ahead_of_the_skipped_row_uses_up_no_skip(db, w1, m1, mk_log):
    """MMLM-L-23 — by machine: a soft-deleted log ahead of the skipped row uses up no skip.
    Rules: `list_logs` R11"""
    mk_log(maintenance_date=D3, gone=True)
    mk_log(maintenance_date=D2)
    c = mk_log(maintenance_date=D1)
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id, skip=1)

    # Then 1
    assert ids(result) == [c.id]


# [claude] MMLM-L-24
def test_mmlm_l_24__by_type_a_soft_deleted_log_ahead_of_the_skipped_row_uses_up_no_skip(db, w1, mk_log):
    """MMLM-L-24 — by type: a soft-deleted log ahead of the skipped row uses up no skip.
    Rules: `list_logs` R11"""
    mk_log(maintenance_date=D3, gone=True)
    mk_log(maintenance_date=D2)
    c = mk_log(maintenance_date=D1)
    result = M.list_logs(db, workspace_id=w1.id, maintenance_type=REPAIR, skip=1)

    # Then 1
    assert ids(result) == [c.id]


# [claude] MMLM-L-25
def test_mmlm_l_25__by_machine_and_type_a_soft_deleted_log_ahead_of_the_skipped_row_uses_u(db, w1, m1, mk_log):
    """MMLM-L-25 — by machine and type: a soft-deleted log ahead of the skipped row uses up no skip.
    Rules: `list_logs` R11"""
    mk_log(maintenance_date=D3, gone=True)
    mk_log(maintenance_date=D2)
    c = mk_log(maintenance_date=D1)
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id, maintenance_type=REPAIR, skip=1)

    # Then 1
    assert ids(result) == [c.id]


# [claude] MMLM-L-26
def test_mmlm_l_26__no_filter_a_soft_deleted_log_ahead_of_the_page_uses_up_no_limit(db, w1, mk_log):
    """MMLM-L-26 — no filter: a soft-deleted log ahead of the page uses up no limit.
    Rules: `list_logs` R11"""
    mk_log(maintenance_date=D3, gone=True)
    b = mk_log(maintenance_date=D2)
    mk_log(maintenance_date=D1)
    result = M.list_logs(db, workspace_id=w1.id, limit=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] MMLM-L-27
def test_mmlm_l_27__by_machine_a_soft_deleted_log_ahead_of_the_page_uses_up_no_limit(db, w1, m1, mk_log):
    """MMLM-L-27 — by machine: a soft-deleted log ahead of the page uses up no limit.
    Rules: `list_logs` R11"""
    mk_log(maintenance_date=D3, gone=True)
    b = mk_log(maintenance_date=D2)
    mk_log(maintenance_date=D1)
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id, limit=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] MMLM-L-28
def test_mmlm_l_28__by_type_a_soft_deleted_log_ahead_of_the_page_uses_up_no_limit(db, w1, mk_log):
    """MMLM-L-28 — by type: a soft-deleted log ahead of the page uses up no limit.
    Rules: `list_logs` R11"""
    mk_log(maintenance_date=D3, gone=True)
    b = mk_log(maintenance_date=D2)
    mk_log(maintenance_date=D1)
    result = M.list_logs(db, workspace_id=w1.id, maintenance_type=REPAIR, limit=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] MMLM-L-29
def test_mmlm_l_29__by_machine_and_type_a_soft_deleted_log_ahead_of_the_page_uses_up_no_li(db, w1, m1, mk_log):
    """MMLM-L-29 — by machine and type: a soft-deleted log ahead of the page uses up no limit.
    Rules: `list_logs` R11"""
    mk_log(maintenance_date=D3, gone=True)
    b = mk_log(maintenance_date=D2)
    mk_log(maintenance_date=D1)
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id, maintenance_type=REPAIR, limit=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] MMLM-L-30
def test_mmlm_l_30__no_filter_a_log_with_is_active_false_is_returned(db, w1, mk_log):
    """MMLM-L-30 — no filter: a log with is_active False is returned.
    Rules: `list_logs` R11"""
    a = mk_log(is_active=False)
    result = M.list_logs(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MMLM-L-31
def test_mmlm_l_31__by_machine_a_log_with_is_active_false_is_returned(db, w1, m1, mk_log):
    """MMLM-L-31 — by machine: a log with is_active False is returned.
    Rules: `list_logs` R11"""
    a = mk_log(is_active=False)
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MMLM-L-32
def test_mmlm_l_32__by_type_a_log_with_is_active_false_is_returned(db, w1, mk_log):
    """MMLM-L-32 — by type: a log with is_active False is returned.
    Rules: `list_logs` R11"""
    a = mk_log(is_active=False)
    result = M.list_logs(db, workspace_id=w1.id, maintenance_type=REPAIR)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MMLM-L-33
def test_mmlm_l_33__by_machine_and_type_a_log_with_is_active_false_is_returned(db, w1, m1, mk_log):
    """MMLM-L-33 — by machine and type: a log with is_active False is returned.
    Rules: `list_logs` R11"""
    a = mk_log(is_active=False)
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id, maintenance_type=REPAIR)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MMLM-L-34
def test_mmlm_l_34__no_filter_logs_of_deleted_and_of_inactive_parents_are_all_listed(db, w1, md, ma, mf, mg, mk_log):
    """MMLM-L-34 — no filter: logs of deleted and of inactive parents are all listed.
    Rules: `list_logs` R11"""
    a = mk_log(machine_id=md.id)
    b = mk_log(machine_id=mf.id)
    c = mk_log(machine_id=ma.id)
    e = mk_log(machine_id=mg.id)
    result = M.list_logs(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id, c.id, e.id]


# [claude] MMLM-L-35
def test_mmlm_l_35__by_type_logs_of_deleted_and_of_inactive_parents_are_all_listed(db, w1, md, ma, mf, mg, mk_log):
    """MMLM-L-35 — by type: logs of deleted and of inactive parents are all listed.
    Rules: `list_logs` R11"""
    a = mk_log(machine_id=md.id)
    b = mk_log(machine_id=mf.id)
    c = mk_log(machine_id=ma.id)
    e = mk_log(machine_id=mg.id)
    result = M.list_logs(db, workspace_id=w1.id, maintenance_type=REPAIR)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id, c.id, e.id]


# [claude] MMLM-L-36
def test_mmlm_l_36__by_machine_asked_for_a_soft_deleted_machine_its_logs_are_returned(db, w1, md, mk_log):
    """MMLM-L-36 — by machine, asked for a soft-deleted machine: its logs are returned.
    Rules: `list_logs` R11"""
    a = mk_log(machine_id=md.id)
    result = M.list_logs(db, workspace_id=w1.id, machine_id=md.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MMLM-L-37
def test_mmlm_l_37__by_machine_and_type_asked_for_a_soft_deleted_machine_its_logs_are_retu(db, w1, md, mk_log):
    """MMLM-L-37 — by machine and type, asked for a soft-deleted machine: its logs are returned.
    Rules: `list_logs` R11"""
    a = mk_log(machine_id=md.id)
    result = M.list_logs(db, workspace_id=w1.id, machine_id=md.id, maintenance_type=REPAIR)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MMLM-L-38
def test_mmlm_l_38__by_machine_asked_for_a_machine_in_a_soft_deleted_factory_its_logs_are(db, w1, mf, mk_log):
    """MMLM-L-38 — by machine, asked for a machine in a soft-deleted factory: its logs are returned.
    Rules: `list_logs` R11"""
    a = mk_log(machine_id=mf.id)
    result = M.list_logs(db, workspace_id=w1.id, machine_id=mf.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MMLM-L-39
def test_mmlm_l_39__by_machine_and_type_asked_for_a_machine_in_a_soft_deleted_factory_its(db, w1, mf, mk_log):
    """MMLM-L-39 — by machine and type, asked for a machine in a soft-deleted factory: its logs are returned.
    Rules: `list_logs` R11"""
    a = mk_log(machine_id=mf.id)
    result = M.list_logs(db, workspace_id=w1.id, machine_id=mf.id, maintenance_type=REPAIR)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MMLM-L-40
def test_mmlm_l_40__by_machine_asked_for_an_inactive_machine_its_logs_are_returned(db, w1, ma, mk_log):
    """MMLM-L-40 — by machine, asked for an inactive machine: its logs are returned.
    Rules: `list_logs` R11"""
    a = mk_log(machine_id=ma.id)
    result = M.list_logs(db, workspace_id=w1.id, machine_id=ma.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MMLM-L-41
def test_mmlm_l_41__by_machine_and_type_asked_for_an_inactive_machine_its_logs_are_returne(db, w1, ma, mk_log):
    """MMLM-L-41 — by machine and type, asked for an inactive machine: its logs are returned.
    Rules: `list_logs` R11"""
    a = mk_log(machine_id=ma.id)
    result = M.list_logs(db, workspace_id=w1.id, machine_id=ma.id, maintenance_type=REPAIR)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MMLM-L-42
def test_mmlm_l_42__by_machine_asked_for_a_machine_in_an_inactive_factory_its_logs_are_ret(db, w1, mg, mk_log):
    """MMLM-L-42 — by machine, asked for a machine in an inactive factory: its logs are returned.
    Rules: `list_logs` R11"""
    a = mk_log(machine_id=mg.id)
    result = M.list_logs(db, workspace_id=w1.id, machine_id=mg.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MMLM-L-43
def test_mmlm_l_43__by_machine_and_type_asked_for_a_machine_in_an_inactive_factory_its_log(db, w1, mg, mk_log):
    """MMLM-L-43 — by machine and type, asked for a machine in an inactive factory: its logs are returned.
    Rules: `list_logs` R11"""
    a = mk_log(machine_id=mg.id)
    result = M.list_logs(db, workspace_id=w1.id, machine_id=mg.id, maintenance_type=REPAIR)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MMLM-L-44
def test_mmlm_l_44__a_log_of_a_soft_deleted_machine_that_is_itself_deleted_stays_hidden(db, w1, md, mk_log):
    """MMLM-L-44 — a log of a soft-deleted machine that is itself deleted stays hidden.
    Rules: `list_logs` R11"""
    a = mk_log(machine_id=md.id)
    mk_log(machine_id=md.id, gone=True)
    result = M.list_logs(db, workspace_id=w1.id, machine_id=md.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MMLM-L-45
def test_mmlm_l_45__a_log_of_a_soft_deleted_machine_takes_its_place_in_the_page(db, w1, md, mk_log):
    """MMLM-L-45 — a log of a soft-deleted machine takes its place in the page.
    Rules: `list_logs` R11"""
    mk_log(machine_id=md.id, maintenance_date=D3)
    b = mk_log(maintenance_date=D2)
    c = mk_log(maintenance_date=D1)
    result = M.list_logs(db, workspace_id=w1.id, skip=1)

    # Then 1
    assert ids(result) == [b.id, c.id]


# [claude] MMLM-L-46
@pytest.mark.xfail(strict=True, reason="BUG-1101: A stored maintenance log linked to another workspace's machine shows that machine's id")
def test_mmlm_l_46__no_filter_a_log_on_another_workspace_s_machine_is_left_out(db, w1, m9, mk_log):
    """MMLM-L-46 — no filter: a log on another workspace's machine is left out.
    Rules: `list_logs` R12 [BUG-1101]"""
    a = mk_log()
    # A row of W1 on a W2 machine, invalid data.
    x = mk_log(machine_id=m9.id)
    result = M.list_logs(db, workspace_id=w1.id)

    # Then 1
    assert a.id in ids(result)
    # Then 2
    assert count_rows(db, "machine_maintenance_logs", id=x.id) == 1
    # Then 3
    assert ids(result) == [a.id]


# [claude] MMLM-L-47
@pytest.mark.xfail(strict=True, reason="BUG-1101: A stored maintenance log linked to another workspace's machine shows that machine's id")
def test_mmlm_l_47__by_type_a_log_on_another_workspace_s_machine_is_left_out(db, w1, m9, mk_log):
    """MMLM-L-47 — by type: a log on another workspace's machine is left out.
    Rules: `list_logs` R12 [BUG-1101]"""
    a = mk_log()
    # A row of W1 on a W2 machine, invalid data.
    x = mk_log(machine_id=m9.id)
    result = M.list_logs(db, workspace_id=w1.id, maintenance_type=REPAIR)

    # Then 1
    assert a.id in ids(result)
    # Then 2
    assert count_rows(db, "machine_maintenance_logs", id=x.id) == 1
    # Then 3
    assert ids(result) == [a.id]


# [claude] MMLM-L-48
@pytest.mark.xfail(strict=True, reason="BUG-1101: A stored maintenance log linked to another workspace's machine shows that machine's id")
def test_mmlm_l_48__by_machine_asked_for_that_machine_nothing_comes_back(db, w1, m9, mk_log):
    """MMLM-L-48 — by machine: asked for that machine, nothing comes back.
    Rules: `list_logs` R12 [BUG-1101]"""
    # A row of W1 on a W2 machine, invalid data.
    x = mk_log(machine_id=m9.id)
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m9.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert count_rows(db, "machine_maintenance_logs", id=x.id) == 1
    # Then 3
    assert result == []


# [claude] MMLM-L-49
@pytest.mark.xfail(strict=True, reason="BUG-1101: A stored maintenance log linked to another workspace's machine shows that machine's id")
def test_mmlm_l_49__by_machine_and_type_asked_for_that_machine_nothing_comes_back(db, w1, m9, mk_log):
    """MMLM-L-49 — by machine and type: asked for that machine, nothing comes back.
    Rules: `list_logs` R12 [BUG-1101]"""
    # A row of W1 on a W2 machine, invalid data.
    x = mk_log(machine_id=m9.id)
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m9.id, maintenance_type=REPAIR)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert count_rows(db, "machine_maintenance_logs", id=x.id) == 1
    # Then 3
    assert result == []


# [claude] MMLM-L-50
@pytest.mark.xfail(strict=True, reason="BUG-1101: A stored maintenance log linked to another workspace's machine shows that machine's id")
def test_mmlm_l_50__no_filter_a_log_on_another_workspace_s_machine_ahead_of_the_skipped_ro(db, w1, m9, mk_log):
    """MMLM-L-50 — no filter: a log on another workspace's machine ahead of the skipped row uses up no skip.
    Rules: `list_logs` R12 [BUG-1101]"""
    x = mk_log(machine_id=m9.id, maintenance_date=D3)
    mk_log(maintenance_date=D2)
    c = mk_log(maintenance_date=D1)
    result = M.list_logs(db, workspace_id=w1.id, skip=1)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert count_rows(db, "machine_maintenance_logs", id=x.id) == 1
    # Then 3
    assert ids(result) == [c.id]


# [claude] MMLM-L-51
@pytest.mark.xfail(strict=True, reason="BUG-1101: A stored maintenance log linked to another workspace's machine shows that machine's id")
def test_mmlm_l_51__by_type_a_log_on_another_workspace_s_machine_ahead_of_the_skipped_row(db, w1, m9, mk_log):
    """MMLM-L-51 — by type: a log on another workspace's machine ahead of the skipped row uses up no skip.
    Rules: `list_logs` R12 [BUG-1101]"""
    x = mk_log(machine_id=m9.id, maintenance_date=D3)
    mk_log(maintenance_date=D2)
    c = mk_log(maintenance_date=D1)
    result = M.list_logs(db, workspace_id=w1.id, maintenance_type=REPAIR, skip=1)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert count_rows(db, "machine_maintenance_logs", id=x.id) == 1
    # Then 3
    assert ids(result) == [c.id]


# [claude] MMLM-L-52
def test_mmlm_l_52__from_the_machine_s_own_workspace_the_row_is_not_listed(db, w2, m9, mk_log):
    """MMLM-L-52 — from the machine's own workspace the row is not listed.
    Rules: `list_logs` R12, `list_logs` R6"""
    # A row of W1 on a W2 machine, invalid data.
    mk_log(machine_id=m9.id)
    result = M.list_logs(db, workspace_id=w2.id, machine_id=m9.id)

    # Then 1
    assert result == []


# [claude] MMLM-L-53
@pytest.mark.xfail(strict=True, reason="BUG-1152: machine_id=0 lists the whole workspace's maintenance logs")
def test_mmlm_l_53__machine_id_0_alone_returns_nothing(db, w1, mk_log):
    """MMLM-L-53 — machine_id=0 alone returns nothing.
    Rules: `list_logs` R5 [BUG-1152]"""
    mk_log()
    result = M.list_logs(db, workspace_id=w1.id, machine_id=0)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert result == []


# [claude] MMLM-L-54
@pytest.mark.xfail(strict=True, reason="BUG-1152: machine_id=0 lists the whole workspace's maintenance logs")
def test_mmlm_l_54__machine_id_0_with_a_type_returns_nothing(db, w1, mk_log):
    """MMLM-L-54 — machine_id=0 with a type returns nothing.
    Rules: `list_logs` R5 [BUG-1152]"""
    mk_log()
    result = M.list_logs(db, workspace_id=w1.id, machine_id=0, maintenance_type=REPAIR)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert result == []


# [claude] MMLM-L-55
@pytest.mark.xfail(strict=True, reason="BUG-1152: machine_id=0 lists the whole workspace's maintenance logs")
def test_mmlm_l_55__machine_id_0_with_an_empty_type_string_returns_nothing(db, w1, mk_log):
    """MMLM-L-55 — machine_id=0 with an empty type string returns nothing.
    Rules: `list_logs` R5 [BUG-1152], `list_logs` R7"""
    mk_log()
    result = M.list_logs(db, workspace_id=w1.id, machine_id=0, maintenance_type="")

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert result == []


# [claude] MMLM-L-56
def test_mmlm_l_56__an_unknown_machine_returns_an_empty_list_with_no_404(db, w1, mk_log):
    """MMLM-L-56 — an unknown machine returns an empty list, with no 404.
    Rules: `list_logs` R6"""
    mk_log()
    result = M.list_logs(db, workspace_id=w1.id, machine_id=MISSING)

    # Then 1
    assert result == []


# [claude] MMLM-L-57
def test_mmlm_l_57__an_unknown_machine_with_a_type_returns_an_empty_list_with_no_404(db, w1, mk_log):
    """MMLM-L-57 — an unknown machine with a type returns an empty list, with no 404.
    Rules: `list_logs` R6"""
    mk_log()
    result = M.list_logs(db, workspace_id=w1.id, machine_id=MISSING, maintenance_type=REPAIR)

    # Then 1
    assert result == []


# [claude] MMLM-L-58
def test_mmlm_l_58__a_negative_machine_id_returns_an_empty_list_with_no_404(db, w1, mk_log):
    """MMLM-L-58 — a negative machine id returns an empty list, with no 404.
    Rules: `list_logs` R6"""
    mk_log()
    result = M.list_logs(db, workspace_id=w1.id, machine_id=-1)

    # Then 1
    assert result == []


# [claude] MMLM-L-59
def test_mmlm_l_59__a_negative_machine_id_with_a_type_returns_an_empty_list_with_no_404(db, w1, mk_log):
    """MMLM-L-59 — a negative machine id with a type returns an empty list, with no 404.
    Rules: `list_logs` R6"""
    mk_log()
    result = M.list_logs(db, workspace_id=w1.id, machine_id=-1, maintenance_type=REPAIR)

    # Then 1
    assert result == []


# [claude] MMLM-L-60
def test_mmlm_l_60__a_machine_of_another_workspace_returns_an_empty_list_with_no_404(db, w1, w2, m9, mk_log):
    """MMLM-L-60 — a machine of another workspace returns an empty list, with no 404.
    Rules: `list_logs` R6"""
    mk_log()
    mk_log(workspace_id=w2.id, machine_id=m9.id)
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m9.id)

    # Then 1
    assert result == []


# [claude] MMLM-L-61
def test_mmlm_l_61__a_machine_of_another_workspace_with_a_type_returns_an_empty_list_with(db, w1, w2, m9, mk_log):
    """MMLM-L-61 — a machine of another workspace with a type returns an empty list, with no 404.
    Rules: `list_logs` R6"""
    mk_log()
    mk_log(workspace_id=w2.id, machine_id=m9.id)
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m9.id, maintenance_type=REPAIR)

    # Then 1
    assert result == []


# [claude] MMLM-L-62
def test_mmlm_l_62__a_machine_with_no_logs_returns_an_empty_list_with_no_404(db, w1, m2, mk_log):
    """MMLM-L-62 — a machine with no logs returns an empty list, with no 404.
    Rules: `list_logs` R6"""
    mk_log()
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m2.id)

    # Then 1
    assert result == []


# [claude] MMLM-L-63
def test_mmlm_l_63__a_machine_with_no_logs_with_a_type_returns_an_empty_list_with_no_404(db, w1, m2, mk_log):
    """MMLM-L-63 — a machine with no logs with a type returns an empty list, with no 404.
    Rules: `list_logs` R6"""
    mk_log()
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m2.id, maintenance_type=REPAIR)

    # Then 1
    assert result == []


# [claude] MMLM-L-64
def test_mmlm_l_64__a_type_no_log_has_returns_an_empty_list(db, w1, mk_log):
    """MMLM-L-64 — a type no log has returns an empty list.
    Rules: `list_logs` R6"""
    mk_log()
    result = M.list_logs(db, workspace_id=w1.id, maintenance_type=MaintenanceTypeEnum.EMERGENCY)

    # Then 1
    assert result == []


# [claude] MMLM-L-65
def test_mmlm_l_65__a_type_the_machine_has_no_log_of_returns_an_empty_list(db, w1, m1, mk_log):
    """MMLM-L-65 — a type the machine has no log of returns an empty list.
    Rules: `list_logs` R6"""
    mk_log()
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id, maintenance_type=MaintenanceTypeEnum.EMERGENCY)

    # Then 1
    assert result == []


# [claude] MMLM-L-66
def test_mmlm_l_66__no_filter_an_unknown_workspace_returns_an_empty_list(db, mk_log):
    """MMLM-L-66 — no filter: an unknown workspace returns an empty list.
    Rules: `list_logs` R6"""
    mk_log()
    result = M.list_logs(db, workspace_id=MISSING)

    # Then 1
    assert result == []


# [claude] MMLM-L-67
def test_mmlm_l_67__by_machine_an_unknown_workspace_returns_an_empty_list(db, m1, mk_log):
    """MMLM-L-67 — by machine: an unknown workspace returns an empty list.
    Rules: `list_logs` R6"""
    mk_log()
    result = M.list_logs(db, workspace_id=MISSING, machine_id=m1.id)

    # Then 1
    assert result == []


# [claude] MMLM-L-68
def test_mmlm_l_68__by_type_an_unknown_workspace_returns_an_empty_list(db, mk_log):
    """MMLM-L-68 — by type: an unknown workspace returns an empty list.
    Rules: `list_logs` R6"""
    mk_log()
    result = M.list_logs(db, workspace_id=MISSING, maintenance_type=REPAIR)

    # Then 1
    assert result == []


# [claude] MMLM-L-69
def test_mmlm_l_69__by_machine_and_type_an_unknown_workspace_returns_an_empty_list(db, m1, mk_log):
    """MMLM-L-69 — by machine and type: an unknown workspace returns an empty list.
    Rules: `list_logs` R6"""
    mk_log()
    result = M.list_logs(db, workspace_id=MISSING, machine_id=m1.id, maintenance_type=REPAIR)

    # Then 1
    assert result == []


# [claude] MMLM-L-70
def test_mmlm_l_70__no_filter_a_workspace_with_no_logs_returns_an_empty_list(db, w2, mk_log):
    """MMLM-L-70 — no filter: a workspace with no logs returns an empty list.
    Rules: `list_logs` R6"""
    mk_log()
    result = M.list_logs(db, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] MMLM-L-71
def test_mmlm_l_71__by_machine_a_w1_machine_asked_for_from_w2_returns_an_empty_list(db, w2, m1, mk_log):
    """MMLM-L-71 — by machine: a W1 machine asked for from W2 returns an empty list.
    Rules: `list_logs` R6"""
    mk_log()
    result = M.list_logs(db, workspace_id=w2.id, machine_id=m1.id)

    # Then 1
    assert result == []


# [claude] MMLM-L-72
def test_mmlm_l_72__by_machine_and_type_a_w1_machine_asked_for_from_w2_returns_an_empty_li(db, w2, m1, mk_log):
    """MMLM-L-72 — by machine and type: a W1 machine asked for from W2 returns an empty list.
    Rules: `list_logs` R6"""
    mk_log()
    result = M.list_logs(db, workspace_id=w2.id, machine_id=m1.id, maintenance_type=REPAIR)

    # Then 1
    assert result == []


# [claude] MMLM-L-73
def test_mmlm_l_73__by_type_the_string_repair_works_like_the_member(db, w1, mk_log):
    """MMLM-L-73 — by type: the string 'REPAIR' works like the member.
    Rules: `list_logs` R7"""
    a = mk_log()
    mk_log(maintenance_type=MaintenanceTypeEnum.EMERGENCY)
    result = M.list_logs(db, workspace_id=w1.id, maintenance_type="REPAIR")

    # Then 1
    assert ids(result) == [a.id]


# [claude] MMLM-L-74
def test_mmlm_l_74__by_machine_and_type_the_string_repair_works_like_the_member(db, w1, m1, mk_log):
    """MMLM-L-74 — by machine and type: the string 'REPAIR' works like the member.
    Rules: `list_logs` R7"""
    a = mk_log()
    mk_log(maintenance_type=MaintenanceTypeEnum.EMERGENCY)
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id, maintenance_type="REPAIR")

    # Then 1
    assert ids(result) == [a.id]


# [claude] MMLM-L-75
def test_mmlm_l_75__an_empty_type_string_means_no_filter(db, w1, mk_log):
    """MMLM-L-75 — an empty type string means no filter.
    Rules: `list_logs` R7"""
    a = mk_log()
    b = mk_log(maintenance_type=MaintenanceTypeEnum.EMERGENCY)
    result = M.list_logs(db, workspace_id=w1.id, maintenance_type="")

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]


# [claude] MMLM-L-76
def test_mmlm_l_76__an_empty_type_string_with_a_machine_filters_by_the_machine_alone(db, w1, m1, m2, mk_log):
    """MMLM-L-76 — an empty type string with a machine filters by the machine alone.
    Rules: `list_logs` R7"""
    a = mk_log()
    b = mk_log(maintenance_type=MaintenanceTypeEnum.EMERGENCY)
    mk_log(machine_id=m2.id)
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id, maintenance_type="")

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]


# [claude] MMLM-L-77
def test_mmlm_l_77__by_type_a_string_that_is_no_member_is_a_database_error(db, w1, mk_log):
    """MMLM-L-77 — by type: a string that is no member is a database error.
    Rules: `list_logs` R7, `list_logs` Errors row 3"""
    mk_log()
    before = written(db)
    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            M.list_logs(db, workspace_id=w1.id, maintenance_type="BOGUS")

    # Then 2
    assert exc.value.orig.pgcode == "22P02"
    # Then 3
    assert written(db) == before


# [claude] MMLM-L-78
def test_mmlm_l_78__by_machine_and_type_a_string_that_is_no_member_is_a_database_error(db, w1, m1, mk_log):
    """MMLM-L-78 — by machine and type: a string that is no member is a database error.
    Rules: `list_logs` R7, `list_logs` Errors row 3"""
    mk_log()
    before = written(db)
    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            M.list_logs(db, workspace_id=w1.id, machine_id=m1.id, maintenance_type="BOGUS")

    # Then 2
    assert exc.value.orig.pgcode == "22P02"
    # Then 3
    assert written(db) == before


# [claude] MMLM-L-79
def test_mmlm_l_79__no_filter_limit_1_gives_the_first_row_of_the_page(db, w1, mk_log):
    """MMLM-L-79 — no filter: limit=1 gives the first row of the page.
    Rules: `list_logs` R8"""
    a = mk_log(maintenance_date=D2)
    mk_log()
    result = M.list_logs(db, workspace_id=w1.id, limit=1)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MMLM-L-80
def test_mmlm_l_80__no_filter_skip_1_gives_the_rest(db, w1, mk_log):
    """MMLM-L-80 — no filter: skip=1 gives the rest.
    Rules: `list_logs` R8"""
    mk_log(maintenance_date=D2)
    b = mk_log()
    result = M.list_logs(db, workspace_id=w1.id, skip=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] MMLM-L-81
def test_mmlm_l_81__no_filter_skip_1_limit_1_gives_the_middle_row(db, w1, mk_log):
    """MMLM-L-81 — no filter: skip=1, limit=1 gives the middle row.
    Rules: `list_logs` R8"""
    mk_log(maintenance_date=D3)
    b = mk_log(maintenance_date=D2)
    mk_log(maintenance_date=D1)
    result = M.list_logs(db, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] MMLM-L-82
def test_mmlm_l_82__no_filter_the_defaults_give_the_latest_100_of_101(db, w1, bulk101):
    """MMLM-L-82 — no filter: the defaults give the latest 100 of 101.
    Rules: `list_logs` R8"""
    rows = bulk101()
    result = M.list_logs(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert rows[0].id not in ids(result)


# [claude] MMLM-L-83
def test_mmlm_l_83__no_filter_limit_1000_gives_all_101(db, w1, bulk101):
    """MMLM-L-83 — no filter: limit=1000 gives all 101.
    Rules: `list_logs` R8"""
    rows = bulk101()
    all_ids = [r.id for r in rows]
    result = M.list_logs(db, workspace_id=w1.id, limit=1000)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert sorted(ids(result)) == sorted(all_ids)


# [claude] MMLM-L-84
def test_mmlm_l_84__no_filter_limit_0_returns_an_empty_list(db, w1, mk_log):
    """MMLM-L-84 — no filter: limit=0 returns an empty list.
    Rules: `list_logs` R8"""
    mk_log()
    result = M.list_logs(db, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [claude] MMLM-L-85
def test_mmlm_l_85__no_filter_skip_at_the_end_returns_an_empty_list(db, w1, mk_log):
    """MMLM-L-85 — no filter: skip at the end returns an empty list.
    Rules: `list_logs` R8"""
    mk_log(maintenance_date=D2)
    mk_log()
    result = M.list_logs(db, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [claude] MMLM-L-86
def test_mmlm_l_86__by_machine_limit_1_gives_the_first_row_of_the_page(db, w1, m1, mk_log):
    """MMLM-L-86 — by machine: limit=1 gives the first row of the page.
    Rules: `list_logs` R8"""
    a = mk_log(maintenance_date=D2)
    mk_log()
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id, limit=1)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MMLM-L-87
def test_mmlm_l_87__by_machine_skip_1_gives_the_rest(db, w1, m1, mk_log):
    """MMLM-L-87 — by machine: skip=1 gives the rest.
    Rules: `list_logs` R8"""
    mk_log(maintenance_date=D2)
    b = mk_log()
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id, skip=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] MMLM-L-88
def test_mmlm_l_88__by_machine_skip_1_limit_1_gives_the_middle_row(db, w1, m1, mk_log):
    """MMLM-L-88 — by machine: skip=1, limit=1 gives the middle row.
    Rules: `list_logs` R8"""
    mk_log(maintenance_date=D3)
    b = mk_log(maintenance_date=D2)
    mk_log(maintenance_date=D1)
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] MMLM-L-89
def test_mmlm_l_89__by_machine_the_defaults_give_the_latest_100_of_101(db, w1, m1, bulk101):
    """MMLM-L-89 — by machine: the defaults give the latest 100 of 101.
    Rules: `list_logs` R8"""
    rows = bulk101()
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert rows[0].id not in ids(result)


# [claude] MMLM-L-90
def test_mmlm_l_90__by_machine_limit_1000_gives_all_101(db, w1, m1, bulk101):
    """MMLM-L-90 — by machine: limit=1000 gives all 101.
    Rules: `list_logs` R8"""
    rows = bulk101()
    all_ids = [r.id for r in rows]
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id, limit=1000)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert sorted(ids(result)) == sorted(all_ids)


# [claude] MMLM-L-91
def test_mmlm_l_91__by_machine_limit_0_returns_an_empty_list(db, w1, m1, mk_log):
    """MMLM-L-91 — by machine: limit=0 returns an empty list.
    Rules: `list_logs` R8"""
    mk_log()
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id, limit=0)

    # Then 1
    assert result == []


# [claude] MMLM-L-92
def test_mmlm_l_92__by_machine_skip_at_the_end_returns_an_empty_list(db, w1, m1, mk_log):
    """MMLM-L-92 — by machine: skip at the end returns an empty list.
    Rules: `list_logs` R8"""
    mk_log(maintenance_date=D2)
    mk_log()
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id, skip=2)

    # Then 1
    assert result == []


# [claude] MMLM-L-93
def test_mmlm_l_93__by_type_limit_1_gives_the_first_row_of_the_page(db, w1, mk_log):
    """MMLM-L-93 — by type: limit=1 gives the first row of the page.
    Rules: `list_logs` R8"""
    a = mk_log(maintenance_date=D2)
    mk_log()
    result = M.list_logs(db, workspace_id=w1.id, maintenance_type=REPAIR, limit=1)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MMLM-L-94
def test_mmlm_l_94__by_type_skip_1_gives_the_rest(db, w1, mk_log):
    """MMLM-L-94 — by type: skip=1 gives the rest.
    Rules: `list_logs` R8"""
    mk_log(maintenance_date=D2)
    b = mk_log()
    result = M.list_logs(db, workspace_id=w1.id, maintenance_type=REPAIR, skip=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] MMLM-L-95
def test_mmlm_l_95__by_type_skip_1_limit_1_gives_the_middle_row(db, w1, mk_log):
    """MMLM-L-95 — by type: skip=1, limit=1 gives the middle row.
    Rules: `list_logs` R8"""
    mk_log(maintenance_date=D3)
    b = mk_log(maintenance_date=D2)
    mk_log(maintenance_date=D1)
    result = M.list_logs(db, workspace_id=w1.id, maintenance_type=REPAIR, skip=1, limit=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] MMLM-L-96
def test_mmlm_l_96__by_type_the_defaults_give_the_latest_100_of_101(db, w1, bulk101):
    """MMLM-L-96 — by type: the defaults give the latest 100 of 101.
    Rules: `list_logs` R8"""
    rows = bulk101()
    result = M.list_logs(db, workspace_id=w1.id, maintenance_type=REPAIR)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert rows[0].id not in ids(result)


# [claude] MMLM-L-97
def test_mmlm_l_97__by_type_limit_1000_gives_all_101(db, w1, bulk101):
    """MMLM-L-97 — by type: limit=1000 gives all 101.
    Rules: `list_logs` R8"""
    rows = bulk101()
    all_ids = [r.id for r in rows]
    result = M.list_logs(db, workspace_id=w1.id, maintenance_type=REPAIR, limit=1000)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert sorted(ids(result)) == sorted(all_ids)


# [claude] MMLM-L-98
def test_mmlm_l_98__by_type_limit_0_returns_an_empty_list(db, w1, mk_log):
    """MMLM-L-98 — by type: limit=0 returns an empty list.
    Rules: `list_logs` R8"""
    mk_log()
    result = M.list_logs(db, workspace_id=w1.id, maintenance_type=REPAIR, limit=0)

    # Then 1
    assert result == []


# [claude] MMLM-L-99
def test_mmlm_l_99__by_type_skip_at_the_end_returns_an_empty_list(db, w1, mk_log):
    """MMLM-L-99 — by type: skip at the end returns an empty list.
    Rules: `list_logs` R8"""
    mk_log(maintenance_date=D2)
    mk_log()
    result = M.list_logs(db, workspace_id=w1.id, maintenance_type=REPAIR, skip=2)

    # Then 1
    assert result == []


# [claude] MMLM-L-100
def test_mmlm_l_100__by_machine_and_type_limit_1_gives_the_first_row_of_the_page(db, w1, m1, mk_log):
    """MMLM-L-100 — by machine and type: limit=1 gives the first row of the page.
    Rules: `list_logs` R8"""
    a = mk_log(maintenance_date=D2)
    mk_log()
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id, maintenance_type=REPAIR, limit=1)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MMLM-L-101
def test_mmlm_l_101__by_machine_and_type_skip_1_gives_the_rest(db, w1, m1, mk_log):
    """MMLM-L-101 — by machine and type: skip=1 gives the rest.
    Rules: `list_logs` R8"""
    mk_log(maintenance_date=D2)
    b = mk_log()
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id, maintenance_type=REPAIR, skip=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] MMLM-L-102
def test_mmlm_l_102__by_machine_and_type_skip_1_limit_1_gives_the_middle_row(db, w1, m1, mk_log):
    """MMLM-L-102 — by machine and type: skip=1, limit=1 gives the middle row.
    Rules: `list_logs` R8"""
    mk_log(maintenance_date=D3)
    b = mk_log(maintenance_date=D2)
    mk_log(maintenance_date=D1)
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id, maintenance_type=REPAIR, skip=1, limit=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] MMLM-L-103
def test_mmlm_l_103__by_machine_and_type_the_defaults_give_the_latest_100_of_101(db, w1, m1, bulk101):
    """MMLM-L-103 — by machine and type: the defaults give the latest 100 of 101.
    Rules: `list_logs` R8"""
    rows = bulk101()
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id, maintenance_type=REPAIR)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert rows[0].id not in ids(result)


# [claude] MMLM-L-104
def test_mmlm_l_104__by_machine_and_type_limit_1000_gives_all_101(db, w1, m1, bulk101):
    """MMLM-L-104 — by machine and type: limit=1000 gives all 101.
    Rules: `list_logs` R8"""
    rows = bulk101()
    all_ids = [r.id for r in rows]
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id, maintenance_type=REPAIR, limit=1000)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert sorted(ids(result)) == sorted(all_ids)


# [claude] MMLM-L-105
def test_mmlm_l_105__by_machine_and_type_limit_0_returns_an_empty_list(db, w1, m1, mk_log):
    """MMLM-L-105 — by machine and type: limit=0 returns an empty list.
    Rules: `list_logs` R8"""
    mk_log()
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id, maintenance_type=REPAIR, limit=0)

    # Then 1
    assert result == []


# [claude] MMLM-L-106
def test_mmlm_l_106__by_machine_and_type_skip_at_the_end_returns_an_empty_list(db, w1, m1, mk_log):
    """MMLM-L-106 — by machine and type: skip at the end returns an empty list.
    Rules: `list_logs` R8"""
    mk_log(maintenance_date=D2)
    mk_log()
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id, maintenance_type=REPAIR, skip=2)

    # Then 1
    assert result == []


# [claude] MMLM-L-107
def test_mmlm_l_107__skip_past_the_end_returns_an_empty_list(db, w1, mk_log):
    """MMLM-L-107 — skip past the end returns an empty list.
    Rules: `list_logs` R8"""
    mk_log()
    result = M.list_logs(db, workspace_id=w1.id, skip=5)

    # Then 1
    assert result == []


# [claude] MMLM-L-108
def test_mmlm_l_108__no_filter_a_negative_limit_is_a_database_error(db, w1, mk_log):
    """MMLM-L-108 — no filter: a negative limit is a database error.
    Rules: `list_logs` R9, `list_logs` Errors row 1"""
    mk_log()
    before = written(db)
    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            M.list_logs(db, workspace_id=w1.id, limit=-1)

    # Then 2
    assert exc.value.orig.pgcode == "2201W"
    # Then 3
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 4
    assert written(db) == before


# [claude] MMLM-L-109
def test_mmlm_l_109__no_filter_a_negative_skip_is_a_database_error(db, w1, mk_log):
    """MMLM-L-109 — no filter: a negative skip is a database error.
    Rules: `list_logs` R9, `list_logs` Errors row 2"""
    mk_log()
    before = written(db)
    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            M.list_logs(db, workspace_id=w1.id, skip=-1)

    # Then 2
    assert exc.value.orig.pgcode == "2201X"
    # Then 3
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 4
    assert written(db) == before


# [claude] MMLM-L-110
def test_mmlm_l_110__by_machine_a_negative_limit_is_a_database_error(db, w1, m1, mk_log):
    """MMLM-L-110 — by machine: a negative limit is a database error.
    Rules: `list_logs` R9, `list_logs` Errors row 1"""
    mk_log()
    before = written(db)
    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            M.list_logs(db, workspace_id=w1.id, machine_id=m1.id, limit=-1)

    # Then 2
    assert exc.value.orig.pgcode == "2201W"
    # Then 3
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 4
    assert written(db) == before


# [claude] MMLM-L-111
def test_mmlm_l_111__by_machine_a_negative_skip_is_a_database_error(db, w1, m1, mk_log):
    """MMLM-L-111 — by machine: a negative skip is a database error.
    Rules: `list_logs` R9, `list_logs` Errors row 2"""
    mk_log()
    before = written(db)
    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            M.list_logs(db, workspace_id=w1.id, machine_id=m1.id, skip=-1)

    # Then 2
    assert exc.value.orig.pgcode == "2201X"
    # Then 3
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 4
    assert written(db) == before


# [claude] MMLM-L-112
def test_mmlm_l_112__by_type_a_negative_limit_is_a_database_error(db, w1, mk_log):
    """MMLM-L-112 — by type: a negative limit is a database error.
    Rules: `list_logs` R9, `list_logs` Errors row 1"""
    mk_log()
    before = written(db)
    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            M.list_logs(db, workspace_id=w1.id, maintenance_type=REPAIR, limit=-1)

    # Then 2
    assert exc.value.orig.pgcode == "2201W"
    # Then 3
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 4
    assert written(db) == before


# [claude] MMLM-L-113
def test_mmlm_l_113__by_type_a_negative_skip_is_a_database_error(db, w1, mk_log):
    """MMLM-L-113 — by type: a negative skip is a database error.
    Rules: `list_logs` R9, `list_logs` Errors row 2"""
    mk_log()
    before = written(db)
    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            M.list_logs(db, workspace_id=w1.id, maintenance_type=REPAIR, skip=-1)

    # Then 2
    assert exc.value.orig.pgcode == "2201X"
    # Then 3
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 4
    assert written(db) == before


# [claude] MMLM-L-114
def test_mmlm_l_114__by_machine_and_type_a_negative_limit_is_a_database_error(db, w1, m1, mk_log):
    """MMLM-L-114 — by machine and type: a negative limit is a database error.
    Rules: `list_logs` R9, `list_logs` Errors row 1"""
    mk_log()
    before = written(db)
    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            M.list_logs(db, workspace_id=w1.id, machine_id=m1.id, maintenance_type=REPAIR, limit=-1)

    # Then 2
    assert exc.value.orig.pgcode == "2201W"
    # Then 3
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 4
    assert written(db) == before


# [claude] MMLM-L-115
def test_mmlm_l_115__by_machine_and_type_a_negative_skip_is_a_database_error(db, w1, m1, mk_log):
    """MMLM-L-115 — by machine and type: a negative skip is a database error.
    Rules: `list_logs` R9, `list_logs` Errors row 2"""
    mk_log()
    before = written(db)
    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            M.list_logs(db, workspace_id=w1.id, machine_id=m1.id, maintenance_type=REPAIR, skip=-1)

    # Then 2
    assert exc.value.orig.pgcode == "2201X"
    # Then 3
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 4
    assert written(db) == before


# [claude] MMLM-L-116
def test_mmlm_l_116__no_filter_different_dates_come_back_latest_first(db, w1, mk_log):
    """MMLM-L-116 — no filter: different dates come back latest first.
    Rules: `list_logs` R10"""
    a = mk_log(maintenance_date=D2)
    b = mk_log(maintenance_date=D3)
    c = mk_log(maintenance_date=D1)
    result = M.list_logs(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [b.id, a.id, c.id]


# [claude] MMLM-L-117
def test_mmlm_l_117__by_machine_different_dates_come_back_latest_first(db, w1, m1, mk_log):
    """MMLM-L-117 — by machine: different dates come back latest first.
    Rules: `list_logs` R10"""
    a = mk_log(maintenance_date=D2)
    b = mk_log(maintenance_date=D3)
    c = mk_log(maintenance_date=D1)
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id)

    # Then 1
    assert ids(result) == [b.id, a.id, c.id]


# [claude] MMLM-L-118
def test_mmlm_l_118__by_type_different_dates_come_back_latest_first(db, w1, mk_log):
    """MMLM-L-118 — by type: different dates come back latest first.
    Rules: `list_logs` R10"""
    a = mk_log(maintenance_date=D2)
    b = mk_log(maintenance_date=D3)
    c = mk_log(maintenance_date=D1)
    result = M.list_logs(db, workspace_id=w1.id, maintenance_type=REPAIR)

    # Then 1
    assert ids(result) == [b.id, a.id, c.id]


# [claude] MMLM-L-119
def test_mmlm_l_119__by_machine_and_type_different_dates_come_back_latest_first(db, w1, m1, mk_log):
    """MMLM-L-119 — by machine and type: different dates come back latest first.
    Rules: `list_logs` R10"""
    a = mk_log(maintenance_date=D2)
    b = mk_log(maintenance_date=D3)
    c = mk_log(maintenance_date=D1)
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id, maintenance_type=REPAIR)

    # Then 1
    assert ids(result) == [b.id, a.id, c.id]


# [claude] MMLM-L-120
@pytest.mark.xfail(strict=False, reason="BUG-1100: Maintenance logs on the same date have no order")
def test_mmlm_l_120__no_filter_logs_on_one_date_come_back_highest_id_first(db, w1, mk_log):
    """MMLM-L-120 — no filter: logs on one date come back highest id first.
    Rules: `list_logs` R10 [BUG-1100]"""
    a = mk_log()
    b = mk_log()
    c = mk_log()
    # A is changed after the later rows exist: this usually moves it physically behind them.
    a.summary = "Edited"
    db.flush()
    result = M.list_logs(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id, c.id]
    # Then 2
    assert ids(result) == [c.id, b.id, a.id]


# [claude] MMLM-L-121
@pytest.mark.xfail(strict=False, reason="BUG-1100: Maintenance logs on the same date have no order")
def test_mmlm_l_121__by_machine_logs_on_one_date_come_back_highest_id_first(db, w1, m1, mk_log):
    """MMLM-L-121 — by machine: logs on one date come back highest id first.
    Rules: `list_logs` R10 [BUG-1100]"""
    a = mk_log()
    b = mk_log()
    c = mk_log()
    # A is changed after the later rows exist: this usually moves it physically behind them.
    a.summary = "Edited"
    db.flush()
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id, c.id]
    # Then 2
    assert ids(result) == [c.id, b.id, a.id]


# [claude] MMLM-L-122
@pytest.mark.xfail(strict=False, reason="BUG-1100: Maintenance logs on the same date have no order")
def test_mmlm_l_122__by_type_logs_on_one_date_come_back_highest_id_first(db, w1, mk_log):
    """MMLM-L-122 — by type: logs on one date come back highest id first.
    Rules: `list_logs` R10 [BUG-1100]"""
    a = mk_log()
    b = mk_log()
    c = mk_log()
    # A is changed after the later rows exist: this usually moves it physically behind them.
    a.summary = "Edited"
    db.flush()
    result = M.list_logs(db, workspace_id=w1.id, maintenance_type=REPAIR)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id, c.id]
    # Then 2
    assert ids(result) == [c.id, b.id, a.id]


# [claude] MMLM-L-123
@pytest.mark.xfail(strict=False, reason="BUG-1100: Maintenance logs on the same date have no order")
def test_mmlm_l_123__by_machine_and_type_logs_on_one_date_come_back_highest_id_first(db, w1, m1, mk_log):
    """MMLM-L-123 — by machine and type: logs on one date come back highest id first.
    Rules: `list_logs` R10 [BUG-1100]"""
    a = mk_log()
    b = mk_log()
    c = mk_log()
    # A is changed after the later rows exist: this usually moves it physically behind them.
    a.summary = "Edited"
    db.flush()
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id, maintenance_type=REPAIR)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id, c.id]
    # Then 2
    assert ids(result) == [c.id, b.id, a.id]


# [claude] MMLM-L-124
@pytest.mark.xfail(strict=False, reason="BUG-1100: Maintenance logs on the same date have no order")
def test_mmlm_l_124__no_filter_the_tie_break_applies_before_skip_and_limit(db, w1, mk_log):
    """MMLM-L-124 — no filter: the tie-break applies before skip and limit.
    Rules: `list_logs` R10 [BUG-1100]"""
    a = mk_log()
    b = mk_log()
    mk_log()
    # A is changed after the later rows exist: this usually moves it physically behind them.
    a.summary = "Edited"
    db.flush()
    result = M.list_logs(db, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert ids(result) == [b.id]


# [claude] MMLM-L-125
@pytest.mark.xfail(strict=False, reason="BUG-1100: Maintenance logs on the same date have no order")
def test_mmlm_l_125__by_machine_the_tie_break_applies_before_skip_and_limit(db, w1, m1, mk_log):
    """MMLM-L-125 — by machine: the tie-break applies before skip and limit.
    Rules: `list_logs` R10 [BUG-1100]"""
    a = mk_log()
    b = mk_log()
    mk_log()
    # A is changed after the later rows exist: this usually moves it physically behind them.
    a.summary = "Edited"
    db.flush()
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id, skip=1, limit=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert ids(result) == [b.id]


# [claude] MMLM-L-126
@pytest.mark.xfail(strict=False, reason="BUG-1100: Maintenance logs on the same date have no order")
def test_mmlm_l_126__by_type_the_tie_break_applies_before_skip_and_limit(db, w1, mk_log):
    """MMLM-L-126 — by type: the tie-break applies before skip and limit.
    Rules: `list_logs` R10 [BUG-1100]"""
    a = mk_log()
    b = mk_log()
    mk_log()
    # A is changed after the later rows exist: this usually moves it physically behind them.
    a.summary = "Edited"
    db.flush()
    result = M.list_logs(db, workspace_id=w1.id, maintenance_type=REPAIR, skip=1, limit=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert ids(result) == [b.id]


# [claude] MMLM-L-127
@pytest.mark.xfail(strict=False, reason="BUG-1100: Maintenance logs on the same date have no order")
def test_mmlm_l_127__by_machine_and_type_the_tie_break_applies_before_skip_and_limit(db, w1, m1, mk_log):
    """MMLM-L-127 — by machine and type: the tie-break applies before skip and limit.
    Rules: `list_logs` R10 [BUG-1100]"""
    a = mk_log()
    b = mk_log()
    mk_log()
    # A is changed after the later rows exist: this usually moves it physically behind them.
    a.summary = "Edited"
    db.flush()
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id, maintenance_type=REPAIR, skip=1, limit=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert ids(result) == [b.id]


# [claude] MMLM-L-128
@pytest.mark.xfail(strict=True, reason="BUG-1100: Maintenance logs on the same date have no order")
def test_mmlm_l_128__no_filter_the_query_asks_for_date_descending_then_id_descending(db, w1, mk_log):
    """MMLM-L-128 — no filter: the query asks for date descending, then id descending.
    Rules: `list_logs` R10 [BUG-1100]"""
    a = mk_log()
    with record_sql(db) as sql_log:
        result = M.list_logs(db, workspace_id=w1.id)
    sql = last_sql(sql_log)
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


# [claude] MMLM-L-129
@pytest.mark.xfail(strict=True, reason="BUG-1100: Maintenance logs on the same date have no order")
def test_mmlm_l_129__by_machine_the_query_asks_for_date_descending_then_id_descending(db, w1, m1, mk_log):
    """MMLM-L-129 — by machine: the query asks for date descending, then id descending.
    Rules: `list_logs` R10 [BUG-1100]"""
    a = mk_log()
    with record_sql(db) as sql_log:
        result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id)
    sql = last_sql(sql_log)
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


# [claude] MMLM-L-130
@pytest.mark.xfail(strict=True, reason="BUG-1100: Maintenance logs on the same date have no order")
def test_mmlm_l_130__by_type_the_query_asks_for_date_descending_then_id_descending(db, w1, mk_log):
    """MMLM-L-130 — by type: the query asks for date descending, then id descending.
    Rules: `list_logs` R10 [BUG-1100]"""
    a = mk_log()
    with record_sql(db) as sql_log:
        result = M.list_logs(db, workspace_id=w1.id, maintenance_type=REPAIR)
    sql = last_sql(sql_log)
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


# [claude] MMLM-L-131
@pytest.mark.xfail(strict=True, reason="BUG-1100: Maintenance logs on the same date have no order")
def test_mmlm_l_131__by_machine_and_type_the_query_asks_for_date_descending_then_id_descend(db, w1, m1, mk_log):
    """MMLM-L-131 — by machine and type: the query asks for date descending, then id descending.
    Rules: `list_logs` R10 [BUG-1100]"""
    a = mk_log()
    with record_sql(db) as sql_log:
        result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id, maintenance_type=REPAIR)
    sql = last_sql(sql_log)
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


# [claude] MMLM-L-132
def test_mmlm_l_132__no_filter_the_read_writes_nothing_and_leaves_a_pending_row_pending(db, w1, m1, mk_log, mk_pending):
    """MMLM-L-132 — no filter: the read writes nothing and leaves a pending row pending.
    Rules: `list_logs` R13, `list_logs` Side effects"""
    a = mk_log()
    before_a = snap_before(db, a)
    before = written(db)
    q = mk_pending()
    result = M.list_logs(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert q in db.new
    # Then 3
    assert a not in db.dirty
    # Then 4
    assert count_rows(db, "machine_maintenance_logs", summary="Pending") == 0
    # Then 5
    assert snap(db, a) == before_a
    # Then 6
    assert written(db) == before
    # Then 7
    assert len(events_of(db, m1)) == 0


# [claude] MMLM-L-133
def test_mmlm_l_133__by_machine_the_read_writes_nothing_and_leaves_a_pending_row_pending(db, w1, m1, mk_log, mk_pending):
    """MMLM-L-133 — by machine: the read writes nothing and leaves a pending row pending.
    Rules: `list_logs` R13, `list_logs` Side effects"""
    a = mk_log()
    before_a = snap_before(db, a)
    before = written(db)
    q = mk_pending()
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert q in db.new
    # Then 3
    assert a not in db.dirty
    # Then 4
    assert count_rows(db, "machine_maintenance_logs", summary="Pending") == 0
    # Then 5
    assert snap(db, a) == before_a
    # Then 6
    assert written(db) == before
    # Then 7
    assert len(events_of(db, m1)) == 0


# [claude] MMLM-L-134
def test_mmlm_l_134__by_type_the_read_writes_nothing_and_leaves_a_pending_row_pending(db, w1, m1, mk_log, mk_pending):
    """MMLM-L-134 — by type: the read writes nothing and leaves a pending row pending.
    Rules: `list_logs` R13, `list_logs` Side effects"""
    a = mk_log()
    before_a = snap_before(db, a)
    before = written(db)
    q = mk_pending()
    result = M.list_logs(db, workspace_id=w1.id, maintenance_type=REPAIR)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert q in db.new
    # Then 3
    assert a not in db.dirty
    # Then 4
    assert count_rows(db, "machine_maintenance_logs", summary="Pending") == 0
    # Then 5
    assert snap(db, a) == before_a
    # Then 6
    assert written(db) == before
    # Then 7
    assert len(events_of(db, m1)) == 0


# [claude] MMLM-L-135
def test_mmlm_l_135__by_machine_and_type_the_read_writes_nothing_and_leaves_a_pending_row_p(db, w1, m1, mk_log, mk_pending):
    """MMLM-L-135 — by machine and type: the read writes nothing and leaves a pending row pending.
    Rules: `list_logs` R13, `list_logs` Side effects"""
    a = mk_log()
    before_a = snap_before(db, a)
    before = written(db)
    q = mk_pending()
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id, maintenance_type=REPAIR)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert q in db.new
    # Then 3
    assert a not in db.dirty
    # Then 4
    assert count_rows(db, "machine_maintenance_logs", summary="Pending") == 0
    # Then 5
    assert snap(db, a) == before_a
    # Then 6
    assert written(db) == before
    # Then 7
    assert len(events_of(db, m1)) == 0


# [claude] MMLM-L-136
def test_mmlm_l_136__no_filter_a_w2_row_on_a_w1_machine_does_not_appear(db, w1, w2, mk_log):
    """MMLM-L-136 — no filter: a W2 row on a W1 machine does not appear.
    Rules: `list_logs` R1"""
    a = mk_log()
    # A row of W2 on a W1 machine, invalid data.
    mk_log(workspace_id=w2.id)
    result = M.list_logs(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MMLM-L-137
def test_mmlm_l_137__by_type_a_w2_row_on_a_w1_machine_does_not_appear(db, w1, w2, mk_log):
    """MMLM-L-137 — by type: a W2 row on a W1 machine does not appear.
    Rules: `list_logs` R3"""
    a = mk_log()
    # A row of W2 on a W1 machine, invalid data.
    mk_log(workspace_id=w2.id)
    result = M.list_logs(db, workspace_id=w1.id, maintenance_type=REPAIR)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MMLM-D-01
def test_mmlm_d_01__a_live_log_is_soft_deleted(db, w1, u2, mk_log):
    """MMLM-D-01 — a live log is soft-deleted.
    Rules: `delete_log` R6, `delete_log` Returns, `delete_log` Side effects"""
    a = mk_log(cost=Decimal("5.00"), performed_by="Rahim")
    before_a = snap_before(db, a, "is_deleted", "is_active", "deleted_at", "deleted_by", "updated_at")
    result = M.delete_log(db, log_id=a.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.is_deleted is True
    assert row.is_active is False
    # Then 3
    row = reread(db, a)
    assert row.deleted_by == u2.id
    assert row.deleted_at is not None
    # Then 4
    row = reread(db, a)
    assert row.summary == "Bearing change"
    assert row.cost == Decimal("5.00")
    assert row.performed_by == "Rahim"
    # Then 5
    row = reread(db, a)
    assert row.updated_at is not None
    # Then 6
    assert snap(db, a, "is_deleted", "is_active", "deleted_at", "deleted_by", "updated_at") == before_a
    # Then 7
    assert count_rows(db, "machine_maintenance_logs", id=a.id) == 1


# [claude] MMLM-D-02
def test_mmlm_d_02__the_service_s_keyword_call_works(db, w1, u2, mk_log):
    """MMLM-D-02 — the service's keyword call works.
    Rules: `delete_log` R6"""
    a = mk_log()
    result = M.delete_log(session=db, log_id=a.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.is_deleted is True


# [claude] MMLM-D-03
def test_mmlm_d_03__a_log_of_another_workspace_gets_the_404_and_nothing_is_written(db, w2, u2, m1, mk_log):
    """MMLM-D-03 — a log of another workspace gets the 404 and nothing is written.
    Rules: `delete_log` R1, `delete_log` Errors row 1"""
    a = mk_log()
    before_a = snap_before(db, a)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_log(db, log_id=a.id, workspace_id=w2.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Maintenance log with ID {a.id} not found"
    # Then 4
    assert snap(db, a) == before_a
    # Then 5
    assert written(db) == before
    # Then 6
    assert len(events_of(db, m1)) == 0


# [claude] MMLM-D-04
def test_mmlm_d_04__a_soft_deleted_log_of_another_workspace_gets_the_same_404_not_the_400(db, w2, u2, mk_log):
    """MMLM-D-04 — a soft-deleted log of another workspace gets the same 404, not the 400.
    Rules: `delete_log` R1, `delete_log` Errors row 1"""
    a = mk_log(gone=True)
    before_a = snap_before(db, a)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_log(db, log_id=a.id, workspace_id=w2.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Maintenance log with ID {a.id} not found"
    # Then 4
    assert snap(db, a) == before_a
    # Then 5
    assert written(db) == before


# [claude] MMLM-D-05
def test_mmlm_d_05__an_unknown_id_gets_the_same_404(db, w1, u2, mk_log):
    """MMLM-D-05 — an unknown id gets the same 404.
    Rules: `delete_log` R1, `delete_log` Errors row 1"""
    a = mk_log()
    before_a = snap_before(db, a)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_log(db, log_id=MISSING, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Maintenance log with ID 999999999 not found"
    # Then 4
    assert snap(db, a) == before_a
    # Then 5
    assert written(db) == before


# [claude] MMLM-D-06
def test_mmlm_d_06__id_0_gets_the_same_404(db, w1, u2, mk_log):
    """MMLM-D-06 — id 0 gets the same 404.
    Rules: `delete_log` R1, `delete_log` Errors row 1"""
    a = mk_log()
    before_a = snap_before(db, a)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_log(db, log_id=0, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Maintenance log with ID 0 not found"
    # Then 4
    assert snap(db, a) == before_a
    # Then 5
    assert written(db) == before


# [claude] MMLM-D-07
def test_mmlm_d_07__an_already_deleted_log_is_refused_the_first_stamps_stay_no_entry(db, w1, u1, u2, m1, mk_log):
    """MMLM-D-07 — an already deleted log is refused: the first stamps stay, no entry.
    Rules: `delete_log` R2, `delete_log` Errors row 2"""
    a = mk_log(gone=True)
    before_a = snap_before(db, a)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_log(db, log_id=a.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Maintenance log is already deleted"
    # Then 4
    row = reread(db, a)
    assert row.deleted_by == u1.id
    assert row.deleted_at == T0
    # Then 5
    assert snap(db, a) == before_a
    # Then 6
    assert written(db) == before
    # Then 7
    assert len(events_of(db, m1)) == 0


# [claude] MMLM-D-08
@pytest.mark.xfail(strict=True, reason="BUG-1101: A stored maintenance log linked to another workspace's machine shows that machine's id")
def test_mmlm_d_08__a_log_on_another_workspace_s_machine_gets_the_404_and_stays_live(db, w1, u2, m9, mk_log):
    """MMLM-D-08 — a log on another workspace's machine gets the 404 and stays live.
    Rules: `delete_log` R3 [BUG-1101], `delete_log` Errors row 1"""
    # A row of W1 on a W2 machine, invalid data.
    x = mk_log(machine_id=m9.id)
    before_x = snap_before(db, x)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_log(db, log_id=x.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Maintenance log with ID {x.id} not found"
    # Then 4
    assert snap(db, x) == before_x
    # Then 5
    assert written(db) == before
    # Then 6
    assert len(events_of(db, m9)) == 0


# [claude] MMLM-D-09
@pytest.mark.xfail(strict=True, reason="BUG-1101: A stored maintenance log linked to another workspace's machine shows that machine's id")
def test_mmlm_d_09__a_soft_deleted_log_on_another_workspace_s_machine_answers_404_not_400(db, w1, u2, m9, mk_log):
    """MMLM-D-09 — a soft-deleted log on another workspace's machine answers 404, not 400.
    Rules: `delete_log` R3 [BUG-1101], `delete_log` Errors row 1"""
    x = mk_log(machine_id=m9.id, gone=True)
    before_x = snap_before(db, x)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_log(db, log_id=x.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Maintenance log with ID {x.id} not found"
    # Then 4
    assert snap(db, x) == before_x
    # Then 5
    assert written(db) == before


# [claude] MMLM-D-10
def test_mmlm_d_10__the_same_row_asked_for_from_the_machine_s_workspace_gets_the_404(db, w2, u2, m9, mk_log):
    """MMLM-D-10 — the same row asked for from the machine's workspace gets the 404.
    Rules: `delete_log` R3, `delete_log` R1, `delete_log` Errors row 1"""
    # A row of W1 on a W2 machine, invalid data.
    x = mk_log(machine_id=m9.id)
    before_x = snap_before(db, x)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_log(db, log_id=x.id, workspace_id=w2.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Maintenance log with ID {x.id} not found"
    # Then 4
    assert snap(db, x) == before_x
    # Then 5
    assert written(db) == before
    # Then 6
    assert len(events_of(db, m9)) == 0


# [claude] MMLM-D-11
def test_mmlm_d_11__an_inactive_log_is_deleted_like_any_other(db, w1, u2, m1, mk_log):
    """MMLM-D-11 — an inactive log is deleted like any other.
    Rules: `delete_log` R4"""
    a = mk_log(is_active=False)
    result = M.delete_log(db, log_id=a.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.is_deleted is True
    assert row.is_active is False
    assert row.deleted_by == u2.id
    # Then 3
    evs = events_of(db, m1)
    assert len(evs) == 1


# [claude] MMLM-D-12
def test_mmlm_d_12__a_log_of_a_soft_deleted_machine_is_deleted_and_the_entry_goes_to_that(db, w1, u2, md, mk_log):
    """MMLM-D-12 — a log of a soft-deleted machine is deleted, and the entry goes to that machine.
    Rules: `delete_log` R5"""
    a = mk_log(machine_id=md.id)
    before_md = snap_before(db, md)
    result = M.delete_log(db, log_id=a.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.is_deleted is True
    # Then 3
    evs = events_of(db, md)
    assert len(evs) == 1
    # Then 4
    assert evs[0].event_type == "maintenance_removed"
    assert evs[0].description == "Maintenance log removed: Bearing change"
    assert evs[0].performed_by == u2.id
    assert evs[0].workspace_id == w1.id
    assert evs[0].machine_id == md.id
    # Then 5
    assert snap(db, md) == before_md


# [claude] MMLM-D-13
def test_mmlm_d_13__a_log_of_a_machine_in_a_soft_deleted_factory_is_deleted_and_the_entry(db, w1, u2, mf, mk_log):
    """MMLM-D-13 — a log of a machine in a soft-deleted factory is deleted, and the entry goes to that machine.
    Rules: `delete_log` R5"""
    a = mk_log(machine_id=mf.id)
    before_mf = snap_before(db, mf)
    result = M.delete_log(db, log_id=a.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.is_deleted is True
    # Then 3
    evs = events_of(db, mf)
    assert len(evs) == 1
    # Then 4
    assert evs[0].event_type == "maintenance_removed"
    assert evs[0].description == "Maintenance log removed: Bearing change"
    assert evs[0].performed_by == u2.id
    assert evs[0].workspace_id == w1.id
    assert evs[0].machine_id == mf.id
    # Then 5
    assert snap(db, mf) == before_mf


# [claude] MMLM-D-14
def test_mmlm_d_14__a_log_of_an_inactive_machine_is_deleted_and_the_entry_goes_to_that_mac(db, w1, u2, ma, mk_log):
    """MMLM-D-14 — a log of an inactive machine is deleted, and the entry goes to that machine.
    Rules: `delete_log` R5"""
    a = mk_log(machine_id=ma.id)
    before_ma = snap_before(db, ma)
    result = M.delete_log(db, log_id=a.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.is_deleted is True
    # Then 3
    evs = events_of(db, ma)
    assert len(evs) == 1
    # Then 4
    assert evs[0].event_type == "maintenance_removed"
    assert evs[0].description == "Maintenance log removed: Bearing change"
    assert evs[0].performed_by == u2.id
    assert evs[0].workspace_id == w1.id
    assert evs[0].machine_id == ma.id
    # Then 5
    assert snap(db, ma) == before_ma


# [claude] MMLM-D-15
def test_mmlm_d_15__a_log_of_a_machine_in_an_inactive_factory_is_deleted_and_the_entry_goe(db, w1, u2, mg, mk_log):
    """MMLM-D-15 — a log of a machine in an inactive factory is deleted, and the entry goes to that machine.
    Rules: `delete_log` R5"""
    a = mk_log(machine_id=mg.id)
    before_mg = snap_before(db, mg)
    result = M.delete_log(db, log_id=a.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.is_deleted is True
    # Then 3
    evs = events_of(db, mg)
    assert len(evs) == 1
    # Then 4
    assert evs[0].event_type == "maintenance_removed"
    assert evs[0].description == "Maintenance log removed: Bearing change"
    assert evs[0].performed_by == u2.id
    assert evs[0].workspace_id == w1.id
    assert evs[0].machine_id == mg.id
    # Then 5
    assert snap(db, mg) == before_mg


# [claude] MMLM-D-16
def test_mmlm_d_16__a_delete_leaves_an_empty_updated_by_empty(db, w1, u2, mk_log):
    """MMLM-D-16 — a delete leaves an empty updated_by empty.
    Rules: `delete_log` R6"""
    a = mk_log()
    result = M.delete_log(db, log_id=a.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.deleted_by == u2.id
    # Then 3
    row = reread(db, a)
    assert row.updated_by is None


# [claude] MMLM-D-17
def test_mmlm_d_17__a_delete_by_another_user_leaves_updated_by_as_it_was(db, w1, u2, u3, mk_log):
    """MMLM-D-17 — a delete by another user leaves updated_by as it was.
    Rules: `delete_log` R6"""
    a = mk_log(updated_by=u3.id, updated_at=T0)
    result = M.delete_log(db, log_id=a.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.deleted_by == u2.id
    # Then 3
    row = reread(db, a)
    assert row.updated_by == u3.id


# [claude] MMLM-D-18
def test_mmlm_d_18__a_delete_by_the_user_already_in_updated_by_stamps_deleted_by_only(db, w1, u3, mk_log):
    """MMLM-D-18 — a delete by the user already in updated_by stamps deleted_by only.
    Rules: `delete_log` R6"""
    a = mk_log(updated_by=u3.id)
    result = M.delete_log(db, log_id=a.id, workspace_id=w1.id, user_id=u3.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.deleted_by == u3.id
    # Then 3
    row = reread(db, a)
    assert row.updated_by == u3.id


# [claude] MMLM-D-19
@pytest.mark.xfail(strict=True, reason="BUG-1102: A maintenance log's delete time depends on the database's time zone")
def test_mmlm_d_19__deleted_at_is_the_application_clock(db, w1, u2, mk_log):
    """MMLM-D-19 — deleted_at is the application clock.
    Rules: `delete_log` R6a [BUG-1102]"""
    a = mk_log()
    with patch("app.dao.machine_maintenance_log.utcnow", create=True, return_value=NOW):
        result = M.delete_log(db, log_id=a.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.is_deleted is True
    assert row.deleted_by == u2.id
    # Then 3
    row = reread(db, a)
    assert row.deleted_at == NOW


# [claude] MMLM-D-20
def test_mmlm_d_20__one_maintenance_removed_entry_with_every_field(db, w1, u2, m1, m2, mk_log):
    """MMLM-D-20 — one maintenance_removed entry with every field.
    Rules: `delete_log` R7, `delete_log` Side effects"""
    a = mk_log()
    result = M.delete_log(db, log_id=a.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 3
    assert evs[0].event_type == "maintenance_removed"
    assert evs[0].description == "Maintenance log removed: Bearing change"
    assert evs[0].performed_by == u2.id
    assert evs[0].workspace_id == w1.id
    assert evs[0].machine_id == m1.id
    # Then 4
    assert evs[0].metadata_json == {"maintenance_log_id": a.id}
    # Then 5
    assert evs[0].created_at is not None
    # Then 6
    assert len(events_of(db, m2)) == 0


# [claude] MMLM-D-21
def test_mmlm_d_21__the_entry_s_text_is_the_log_s_summary_the_entry_shows_the_acting_user(db, w1, u3, m1, mk_log):
    """MMLM-D-21 — the entry's text is the log's summary; the entry shows the acting user.
    Rules: `delete_log` R7"""
    a = mk_log(summary="Oil top-up")
    result = M.delete_log(db, log_id=a.id, workspace_id=w1.id, user_id=u3.id)

    # Then 1
    assert result is a
    # Then 2
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 3
    assert evs[0].event_type == "maintenance_removed"
    assert evs[0].description == "Maintenance log removed: Oil top-up"
    assert evs[0].performed_by == u3.id
    assert evs[0].workspace_id == w1.id
    assert evs[0].machine_id == m1.id


# [claude] MMLM-D-22
def test_mmlm_d_22__the_earlier_maintenance_logged_entry_stays(db, w1, u1, u2, m1, mk_log):
    """MMLM-D-22 — the earlier maintenance_logged entry stays.
    Rules: `delete_log` R7"""
    a = mk_log()
    e1 = _add(db, MachineActivityEvent(workspace_id=w1.id, machine_id=m1.id, event_type="maintenance_logged", description="Maintenance logged: Bearing change", performed_by=u1.id))
    before_e1 = snap_before(db, e1)
    result = M.delete_log(db, log_id=a.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    assert len(events_of(db, m1)) == 2
    # Then 3
    assert snap(db, e1) == before_e1
    # Then 4
    assert events_of(db, m1)[1].event_type == "maintenance_removed"


# [claude] MMLM-D-23
def test_mmlm_d_23__one_entry_per_real_change_across_a_log_s_whole_life(db, w1, u2, m1):
    """MMLM-D-23 — one entry per real change across a log's whole life.
    Rules: `delete_log` R7"""
    a = M.create_log(db, log_data=LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=w1.id, user_id=u2.id)
    M.update_log(db, log_id=a.id, log_data=LU(summary="New text"), workspace_id=w1.id, user_id=u2.id)
    result = M.delete_log(db, log_id=a.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    assert len(events_of(db, m1)) == 3
    # Then 3
    assert [e.event_type for e in events_of(db, m1)] == ["maintenance_logged", "maintenance_updated", "maintenance_removed"]
    # Then 4
    assert events_of(db, m1)[2].description == "Maintenance log removed: New text"


# [claude] MMLM-D-24
def test_mmlm_d_24__only_that_log_and_nothing_else_changes(db, w1, u2, m1, mk_log):
    """MMLM-D-24 — only that log and nothing else changes.
    Rules: `delete_log` R8"""
    a = mk_log()
    b = mk_log()
    before_b = snap_before(db, b)
    before_m1 = snap_before(db, m1)
    result = M.delete_log(db, log_id=a.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    assert snap(db, b) == before_b
    # Then 3
    assert snap(db, m1) == before_m1
    # Then 4
    assert count_rows(db, "machine_maintenance_logs", is_deleted=True) == 1


# [claude] MMLM-D-25
def test_mmlm_d_25__after_a_delete_no_filter_the_log_is_in_no_list(db, w1, u2, mk_log):
    """MMLM-D-25 — after a delete, no filter: the log is in no list.
    Rules: `delete_log` R9"""
    a = mk_log()
    b = mk_log()
    M.delete_log(db, log_id=a.id, workspace_id=w1.id, user_id=u2.id)
    result = M.list_logs(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [b.id]


# [claude] MMLM-D-26
def test_mmlm_d_26__after_a_delete_by_machine_the_log_is_in_no_list(db, w1, u2, m1, mk_log):
    """MMLM-D-26 — after a delete, by machine: the log is in no list.
    Rules: `delete_log` R9"""
    a = mk_log()
    b = mk_log()
    M.delete_log(db, log_id=a.id, workspace_id=w1.id, user_id=u2.id)
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id)

    # Then 1
    assert ids(result) == [b.id]


# [claude] MMLM-D-27
def test_mmlm_d_27__after_a_delete_by_type_the_log_is_in_no_list(db, w1, u2, mk_log):
    """MMLM-D-27 — after a delete, by type: the log is in no list.
    Rules: `delete_log` R9"""
    a = mk_log()
    b = mk_log()
    M.delete_log(db, log_id=a.id, workspace_id=w1.id, user_id=u2.id)
    result = M.list_logs(db, workspace_id=w1.id, maintenance_type=REPAIR)

    # Then 1
    assert ids(result) == [b.id]


# [claude] MMLM-D-28
def test_mmlm_d_28__after_a_delete_by_machine_and_type_the_log_is_in_no_list(db, w1, u2, m1, mk_log):
    """MMLM-D-28 — after a delete, by machine and type: the log is in no list.
    Rules: `delete_log` R9"""
    a = mk_log()
    b = mk_log()
    M.delete_log(db, log_id=a.id, workspace_id=w1.id, user_id=u2.id)
    result = M.list_logs(db, workspace_id=w1.id, machine_id=m1.id, maintenance_type=REPAIR)

    # Then 1
    assert ids(result) == [b.id]


# [claude] MMLM-D-29
def test_mmlm_d_29__after_a_delete_update_log_answers_the_400(db, w1, u2, m1, mk_log):
    """MMLM-D-29 — after a delete, update_log answers the 400.
    Rules: `delete_log` R9"""
    a = mk_log()
    M.delete_log(db, log_id=a.id, workspace_id=w1.id, user_id=u2.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_log(db, log_id=a.id, log_data=LU(summary="New text"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update a deleted maintenance log"
    # Then 4
    row = reread(db, a)
    assert row.summary == "Bearing change"
    # Then 5
    evs = events_of(db, m1)
    assert len(evs) == 1


# [claude] MMLM-D-30
def test_mmlm_d_30__a_second_delete_answers_the_400_with_the_first_stamps_kept_and_one_ent(db, w1, u2, u3, m1, mk_log):
    """MMLM-D-30 — a second delete answers the 400, with the first stamps kept and one entry.
    Rules: `delete_log` R9, `delete_log` R2, `delete_log` Errors row 2"""
    a = mk_log()
    M.delete_log(db, log_id=a.id, workspace_id=w1.id, user_id=u2.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_log(db, log_id=a.id, workspace_id=w1.id, user_id=u3.id)

    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Maintenance log is already deleted"
    # Then 4
    row = reread(db, a)
    assert row.deleted_by == u2.id
    # Then 5
    evs = events_of(db, m1)
    assert len(evs) == 1


# [claude] MMLM-D-31
@pytest.mark.xfail(strict=True, reason="BUG-1150: get_log returns soft-deleted maintenance logs")
def test_mmlm_d_31__after_a_delete_get_log_answers_the_404(db, w1, u2, mk_log):
    """MMLM-D-31 — after a delete, get_log answers the 404.
    Rules: `delete_log` R9, `get_log` R3 [BUG-1150]"""
    a = mk_log()
    M.delete_log(db, log_id=a.id, workspace_id=w1.id, user_id=u2.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_log(db, log_id=a.id, workspace_id=w1.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Maintenance log with ID {a.id} not found"


# [claude] MMLM-D-32
@pytest.mark.xfail(strict=True, reason="BUG-1150: get_log returns soft-deleted maintenance logs")
def test_mmlm_d_32__after_a_delete_get_log_with_include_deleted_true_returns_it(db, w1, u2, mk_log):
    """MMLM-D-32 — after a delete, get_log with include_deleted=True returns it.
    Rules: `delete_log` R9, `get_log` R3a [BUG-1150]"""
    a = mk_log()
    M.delete_log(db, log_id=a.id, workspace_id=w1.id, user_id=u2.id)
    result = M.get_log(db, log_id=a.id, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert result is a


# [claude] MMLM-D-33
def test_mmlm_d_33__an_unknown_user_foreign_key_error_the_log_stays_live_no_entry(db, w1, mk_log):
    """MMLM-D-33 — an unknown user: foreign key error, the log stays live, no entry.
    Rules: `delete_log` R10, `delete_log` Errors row 3"""
    a = mk_log()
    before_a = snap_before(db, a)
    before = written(db)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            M.delete_log(db, log_id=a.id, workspace_id=w1.id, user_id=MISSING)

    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert exc.value.orig.diag.constraint_name == "machine_maintenance_logs_deleted_by_fkey"
    # Then 4
    assert snap(db, a) == before_a
    # Then 5
    assert written(db) == before


# [claude] MMLM-D-34
def test_mmlm_d_34__flushed_never_committed(db, w1, u2, m1, mk_log, monkeypatch):
    """MMLM-D-34 — flushed, never committed.
    Rules: `delete_log` R11, `delete_log` Side effects"""
    a = mk_log()
    sp = db.begin_nested()
    spy = commit_spy(db, monkeypatch)
    result = M.delete_log(db, log_id=a.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.is_deleted is True
    # Then 3
    evs = events_of(db, m1)
    assert len(evs) == 1
    # Then 4
    sp.rollback()
    row = reread(db, a)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_by is None
    assert row.deleted_at is None
    # Then 5
    assert len(events_of(db, m1)) == 0
    # Then 6
    assert not spy.called
