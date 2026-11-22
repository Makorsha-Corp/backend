"""Unit tests for app/services/machine_service.py.

Implements tests/unit/services/machine_service.cases.md (revision 2), one test
per case, in card order. Real Postgres session (`db` fixture): a `commit()` only
releases a savepoint, so the service's commits are safe and the fixture's outer
rollback discards everything. Nothing is patched except what Conventions name:
the failing commit / failing refresh wraps, the shaping patch (MCS-C-08), the
manager patch (MCS-D-04) and the race simulation (MCS-C-12).

Normal mode: every test is written from its card and carries a `# [claude] <ID>`
comment. Row names of the cards are the lower-case names here (M1 -> m1 built
by `mk_machine("M1")`, `W1.id` -> `w1.id`); `# Then N` marks the checks of the
card's Then line N.
"""
# ruff: noqa: SIM117, DTZ001, DTZ011  (Conventions prescribe `with pytest.raises(...)` around `with patch.object(...)`, naive T0 ... T3 and date.today())
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import event, func, insert, inspect, select, text
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import ValidationError as AppValidationError
from app.models.enums import MachineEventTypeEnum
from app.models.factory import Factory
from app.models.factory_section import FactorySection
from app.models.item import Item
from app.models.machine import Machine
from app.models.machine_activity_event import MachineActivityEvent
from app.models.machine_item import MachineItem
from app.models.machine_section_assignment import MachineSectionAssignment
from app.models.work_order import WorkOrder
from app.models.work_order_event import WorkOrderEvent
from app.models.work_order_type import WorkOrderType
from app.schemas.machine import MachineCreate, MachineResponse, MachineUpdate
from app.schemas.machine_activity_event import MachineActivityEventResponse
from app.schemas.machine_event import MachineEventCreate, MachineEventResponse
from app.schemas.machine_work import MachineUpcomingWorkRow
from app.services.machine_service import machine_service
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "svc = the singleton machine_service"
svc = machine_service

MISSING = 999999999
T0 = datetime(2025, 12, 1, 8, 0, 0)
T1 = datetime(2026, 1, 1, 9, 0, 0)
T2 = datetime(2026, 1, 1, 10, 0, 0)
T3 = datetime(2026, 1, 1, 11, 0, 0)

IDLE = MachineEventTypeEnum.IDLE
RUNNING = MachineEventTypeEnum.RUNNING
OFF = MachineEventTypeEnum.OFF
MAINTENANCE = MachineEventTypeEnum.MAINTENANCE


# Convention "D(n) = date.today() + timedelta(days=n), read in the test"
def D(n):
    return date.today() + timedelta(days=n)


# Convention "manager patch" (MCS-D-04)
BLOCKERS = [{"type": "machine_stock", "id": 3}, {"type": "other_workspace"}]


def _add(db, row):
    db.add(row)
    db.flush()
    return row


# --------------------------------------------------------------------------- #
# Conventions -> actors and standing rows, in Conventions order
# --------------------------------------------------------------------------- #

@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


# U1 created every Given row; U2 = the acting user
@pytest.fixture
def u1(db, w2):
    return make_profile(db)


@pytest.fixture
def u2(db, u1):
    return make_profile(db)


def _factory(db, ws, u1, name, abbreviation, **but):
    return _add(db, Factory(workspace_id=ws.id, name=name, abbreviation=abbreviation, created_by=u1.id, **but))


@pytest.fixture
def f1(db, w1, u1, u2):
    return _factory(db, w1, u1, "Main Plant", "MP")


@pytest.fixture
def f2(db, w1, u1, f1):
    return _factory(db, w1, u1, "North Yard", "NY")


@pytest.fixture
def fd(db, w1, u1, f2):
    return _factory(db, w1, u1, "Closed Mill", "CM", is_deleted=True)


@pytest.fixture
def f9(db, w2, u1, fd):
    return _factory(db, w2, u1, "Far Depot", "FR")


def _section(db, ws, factory, u1, name, **but):
    return _add(db, FactorySection(workspace_id=ws.id, factory_id=factory.id, name=name, created_by=u1.id, **but))


@pytest.fixture
def s1(db, w1, f1, u1, f9):
    return _section(db, w1, f1, u1, "Cutting")


@pytest.fixture
def s2(db, w1, f1, u1, s1):
    return _section(db, w1, f1, u1, "Paint")


@pytest.fixture
def sx(db, w1, f1, u1, s2):
    return _section(db, w1, f1, u1, "Old Line", is_deleted=True)


@pytest.fixture
def wt1(db, w1, u1, sx):
    return _add(db, WorkOrderType(workspace_id=w1.id, name="Repair", created_by=u1.id))


@pytest.fixture
def i1(db, w1, u1, wt1):
    return _add(db, Item(workspace_id=w1.id, name="Bolt M8", name_normalized="bolt m8", unit="pcs", created_by=u1.id))


# Conventions "Standing rows": in every test, in this order, no Given line needed
@pytest.fixture(autouse=True)
def standing_rows(i1):
    pass


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #

# Convention "machine" and its recipes M1 ... MZ; keywords = the columns after "but"
@pytest.fixture
def mk_machine(db, w1, w2, u1, f1, f2, fd, f9):
    recipes = {
        "M1": {"name": "Lathe"},
        "M2": {"name": "Press"},
        "M3": {"name": "Drill", "factory_id": f2.id},
        "MX": {"name": "Old Saw", "is_deleted": True, "is_active": False, "deleted_at": T0, "deleted_by": u1.id},
        "MF": {"name": "Kiln", "factory_id": fd.id},
        "M9": {"name": "Grinder", "workspace_id": w2.id, "factory_id": f9.id},
        "MA": {"name": "Alpha"},
        "MB": {"name": "Beryl"},
        "MC": {"name": "Cobalt"},
        "MK": {"name": "Krypton"},
        "MQ": {"name": "Quartz"},
        "MZ": {"name": "Zenith"},
    }

    def _mk(recipe=None, **but):
        fields = {
            "workspace_id": w1.id, "factory_id": f1.id, "is_running": False,
            "model_number": None, "manufacturer": None, "note": None, "created_by": u1.id,
        }
        if recipe is not None:
            fields.update(recipes[recipe])
        fields.update(but)
        return _add(db, Machine(**fields))
    return _mk


# Convention "bulk(n, p)": one insert(Machine)
@pytest.fixture
def bulk(db, w1, f1, u1):
    def _bulk(n, p):
        db.execute(insert(Machine), [
            {"workspace_id": w1.id, "factory_id": f1.id, "name": f"{p}{k:05d}", "is_running": False, "created_by": u1.id}
            for k in range(n)
        ])
        return [f"{p}{k:05d}" for k in range(n)]
    return _bulk


# Convention "link of M to S"
@pytest.fixture
def mk_link(db, w1, u1):
    def _mk(machine, section):
        row = _add(db, MachineSectionAssignment(
            workspace_id=w1.id, machine_id=machine.id, factory_section_id=section.id, created_by=u1.id,
        ))
        db.expire_all()
        return row
    return _mk


# Convention "status row of M at T, "X""
@pytest.fixture
def mk_status(db, u1):
    def _mk(machine, at, status):
        return _add(db, MachineActivityEvent(
            workspace_id=machine.workspace_id, machine_id=machine.id, event_type="status_updated",
            description="seed", performed_by=u1.id, created_at=at, metadata_json={"status": status},
        ))
    return _mk


# Convention "event of M at T"; keywords = performed_by, metadata_json, event_type after "but"
@pytest.fixture
def mk_event(db):
    def _mk(machine, at, **but):
        fields = {
            "workspace_id": machine.workspace_id, "machine_id": machine.id, "event_type": "item_added",
            "description": "Logged", "created_at": at,
        }
        fields.update(but)
        return _add(db, MachineActivityEvent(**fields))
    return _mk


# Convention "order of M"; given_name = the row's label or the line's `name`
@pytest.fixture
def mk_order(db, w1, wt1, f1):
    def _mk(machine, given_name, status, planned_date, **but):
        fields = {
            "workspace_id": w1.id, "work_order_number": "WO-" + given_name, "work_order_type_id": wt1.id,
            "title": "Service", "factory_id": f1.id, "machine_id": machine.id if machine is not None else None,
            "is_deleted": False, "status": status, "planned_date": planned_date,
        }
        fields.update(but)
        return _add(db, WorkOrder(**fields))
    return _mk


# Convention "stock of M"
@pytest.fixture
def mk_stock(db, w1, i1):
    def _mk(machine, qty):
        return _add(db, MachineItem(
            workspace_id=w1.id, machine_id=machine.id, item_id=i1.id, qty=qty, req_qty=None, defective_qty=None,
        ))
    return _mk


# Convention "commit point"
def commit_point(db):
    db.commit()


# Convention "extra" = machine, but name "Extra", factory_id F2.id (after the commit point)
@pytest.fixture
def extra(mk_machine, f2):
    def _mk():
        return mk_machine(name="Extra", factory_id=f2.id)
    return _mk


# --------------------------------------------------------------------------- #
# Conventions -> named checks
# --------------------------------------------------------------------------- #

def _id_of(row):
    return inspect(row).identity[0]


# Convention "re-read X"
def reread(db, row):
    model, row_id = type(row), _id_of(row)
    db.expire_all()
    return db.execute(select(model).where(model.id == row_id)).scalar_one_or_none()


def _columns(db, row):
    table = type(row).__table__
    found = db.execute(select(table).where(table.c.id == _id_of(row))).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "unchanged(X)": every column at the commit point (snap right after it) and after a re-read
def snap(db, row):
    db.expire_all()
    return _columns(db, row)


# Convention "count:" lines: rows of the model (all workspaces), with the filter stated
def count_rows(db, model, **filters):
    query = select(func.count()).select_from(model)
    for column, value in filters.items():
        query = query.where(getattr(model, column) == value)
    return db.execute(query).scalar_one()


_WRITTEN = (Machine, MachineSectionAssignment, MachineActivityEvent, WorkOrder, WorkOrderEvent)


# Convention "nothing written"
def written(db):
    return {model.__tablename__: count_rows(db, model) for model in _WRITTEN}


# Convention "events_of(M)"
def events_of(db, machine):
    machine_id = _id_of(machine)
    query = select(MachineActivityEvent).where(MachineActivityEvent.machine_id == machine_id)
    return list(db.execute(query.order_by(MachineActivityEvent.id)).scalars())


# Convention "names(x)", order checked
def names(rows):
    return [r.name for r in rows]


# Convention "ids(x)"
def ids(rows):
    return sorted(r.id for r in rows)


# Convention "session: usable"
def usable(db):
    return db.execute(text("SELECT 1")).scalar() == 1


# Convention "sql_log": a before_cursor_execute listener on db.connection(),
# started after the commit point (so the savepoint release is not in it) and
# removed after the call
@contextmanager
def sql_logging(db):
    sql_log = []
    connection = db.connection()

    def _record(conn, cursor, statement, parameters, context, executemany):
        sql_log.append(statement)

    event.listen(connection, "before_cursor_execute", _record)
    try:
        yield sql_log
    finally:
        event.remove(connection, "before_cursor_execute", _record)


# --------------------------------------------------------------------------- #
# MachineService._to_machine_response
# --------------------------------------------------------------------------- #

# [claude] MCS-R-01
def test_mcs_r_01__every_column_and_the_section_come_from_the_machine_no_status_row_gives_no_status(
    db, w1, u1, f1, s1, mk_machine, mk_link,
):
    """MCS-R-01 — every column and the section come from the machine; no status row gives no status.
    Rules: `_to_machine_response` R1, R2, R4"""
    m1 = mk_machine("M1", model_number="L-200", manufacturer="Haas", note="Bay 3", is_running=True)
    mk_link(m1, s1)
    commit_point(db)
    result = svc._to_machine_response(db, machine=m1)

    # Then 1
    assert isinstance(result, MachineResponse)
    # Then 2
    assert result.id == m1.id
    assert result.workspace_id == w1.id
    assert result.name == "Lathe"
    assert result.is_running is True
    # Then 3
    assert result.factory_id == f1.id
    assert result.factory_section_id == s1.id
    assert result.factory_section_name == "Cutting"
    # Then 4
    assert result.model_number == "L-200"
    assert result.manufacturer == "Haas"
    assert result.note == "Bay 3"
    # Then 5
    assert result.created_by == u1.id
    assert result.is_active is True
    assert result.is_deleted is False
    assert result.deleted_at is None
    assert result.deleted_by is None
    # Then 6
    assert result.latest_status_type is None
    assert result.latest_status_at is None


# [claude] MCS-R-02
def test_mcs_r_02__a_machine_without_a_section_shows_none_for_both_section_fields(db, mk_machine):
    """MCS-R-02 — a machine without a section shows None for both section fields.
    Rules: `_to_machine_response` R1"""
    m1 = mk_machine("M1")
    commit_point(db)
    result = svc._to_machine_response(db, machine=m1)

    # Then 1
    assert result.factory_section_id is None
    # Then 2
    assert result.factory_section_name is None


# [claude] MCS-R-03
def test_mcs_r_03__the_newest_status_row_decides_a_newer_row_of_another_type_is_ignored(
    db, mk_machine, mk_status, mk_event,
):
    """MCS-R-03 — the newest status row decides; a newer row of another type is ignored.
    Rules: `_to_machine_response` R2, R4"""
    m1 = mk_machine("M1")
    mk_status(m1, T2, "RUNNING")
    mk_status(m1, T1, "IDLE")
    mk_event(m1, T3, event_type="maintenance_logged", metadata_json={"status": "OFF"})
    commit_point(db)
    result = svc._to_machine_response(db, machine=m1)

    # Then 1
    assert result.latest_status_type == RUNNING
    # Then 2
    assert result.latest_status_at == T2


# [claude] MCS-R-04
def test_mcs_r_04__with_a_map_the_maps_row_is_used_and_no_status_is_read(db, mk_machine, mk_status):
    """MCS-R-04 — with a map the map's row is used and no status is read.
    Rules: `_to_machine_response` R3, R4"""
    m1 = mk_machine("M1")
    x = mk_status(m1, T1, "OFF")
    mk_status(m1, T2, "RUNNING")
    commit_point(db)
    # the map holds a loaded row, as get_latest_status_map gives it (the commit expired X)
    db.refresh(x)
    status_map = {m1.id: x}
    with sql_logging(db) as sql_log:
        result = svc._to_machine_response(db, machine=m1, status_map=status_map)

    # Then 1
    assert result.latest_status_type == OFF
    # Then 2
    assert result.latest_status_at == T1
    # Then 3
    assert not any("machine_activity_events" in s for s in sql_log)


# [claude] MCS-R-05
def test_mcs_r_05__a_machine_missing_from_the_map_has_no_status_even_with_a_status_row_stored(
    db, mk_machine, mk_status,
):
    """MCS-R-05 — a machine missing from the map has no status, even with a status row stored.
    Rules: `_to_machine_response` R3"""
    m1 = mk_machine("M1")
    m2 = mk_machine("M2")
    mk_status(m1, T1, "RUNNING")
    y = mk_status(m2, T1, "IDLE")
    commit_point(db)
    result = svc._to_machine_response(db, machine=m1, status_map={m2.id: y})

    # Then 1
    assert result.latest_status_type is None
    # Then 2
    assert result.latest_status_at is None


# [claude] MCS-R-06
def test_mcs_r_06__an_empty_stored_status_shows_the_time_with_no_type(db, mk_machine, mk_status):
    """MCS-R-06 — an empty stored status shows the time with no type.
    Rules: `_to_machine_response` R4"""
    m1 = mk_machine("M1")
    mk_status(m1, T1, "")
    commit_point(db)
    result = svc._to_machine_response(db, machine=m1)

    # Then 1
    assert result.latest_status_type is None
    # Then 2
    assert result.latest_status_at == T1


# [claude] MCS-R-07
def test_mcs_r_07__a_status_row_without_metadata_shows_the_time_with_no_type(db, mk_machine, mk_event):
    """MCS-R-07 — a status row without metadata shows the time with no type.
    Rules: `_to_machine_response` R4"""
    m1 = mk_machine("M1")
    mk_event(m1, T1, event_type="status_updated", metadata_json=None)
    commit_point(db)
    result = svc._to_machine_response(db, machine=m1)

    # Then 1
    assert result.latest_status_type is None
    # Then 2
    assert result.latest_status_at == T1


# [claude] MCS-R-08
def test_mcs_r_08__a_stored_status_that_is_not_a_member_value_fails_the_read_with_valueerror(
    db, w1, mk_machine, mk_status,
):
    """MCS-R-08 — a stored status that is not a member value fails the read with ValueError.
    Rules: `_to_machine_response` R5; `get_machine` Errors row 2"""
    m1 = mk_machine("M1")
    mk_status(m1, T1, "running")
    commit_point(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        svc.get_machine(db, machine_id=m1.id, workspace_id=w1.id)
    # Then 2
    assert type(exc.value) is ValueError


# --------------------------------------------------------------------------- #
# MachineService._to_machine_responses
# --------------------------------------------------------------------------- #

# [claude] MCS-RS-01
def test_mcs_rs_01__an_empty_list_gives_empty_with_no_read(db, w1):
    """MCS-RS-01 — an empty list gives [] with no read.
    Rules: `_to_machine_responses` R1"""
    commit_point(db)
    w1_id = w1.id
    with sql_logging(db) as sql_log:
        result = svc._to_machine_responses(db, machines=[], workspace_id=w1_id)

    # Then 1
    assert result == []
    # Then 2
    assert len(sql_log) == 0


# [claude] MCS-RS-02
def test_mcs_rs_02__one_status_read_for_all_one_response_per_machine_in_the_input_order(
    db, w1, mk_machine, mk_status,
):
    """MCS-RS-02 — one status read for all, one response per machine in the input order.
    Rules: `_to_machine_responses` R2"""
    m1 = mk_machine("M1")
    m2 = mk_machine("M2")
    m3 = mk_machine("M3")
    mk_status(m1, T1, "RUNNING")
    mk_status(m2, T2, "OFF")
    commit_point(db)
    with sql_logging(db) as sql_log:
        result = svc._to_machine_responses(db, machines=[m2, m3, m1], workspace_id=w1.id)

    # Then 1
    assert [r.id for r in result] == [m2.id, m3.id, m1.id]
    # Then 2
    assert [r.latest_status_type for r in result] == [OFF, None, RUNNING]
    # Then 3
    assert [r.latest_status_at for r in result] == [T2, None, T1]
    # Then 4
    assert len([s for s in sql_log if "FROM machine_activity_events" in s]) == 1


# --------------------------------------------------------------------------- #
# MachineService.create_machine
# --------------------------------------------------------------------------- #

# [claude] MCS-C-01
def test_mcs_c_01__a_new_machine_and_its_created_entry_are_committed_the_answer_has_no_status(
    db, w1, u2, f1, s1,
):
    """MCS-C-01 — a new machine and its created entry are committed; the answer has no status.
    Rules: `create_machine` R1; TC1, TC2"""
    commit_point(db)
    result = svc.create_machine(
        db, machine_in=MachineCreate(name="Lathe", factory_id=f1.id, factory_section_id=s1.id, model_number="L-200"),
        workspace_id=w1.id, user_id=u2.id,
    )

    # Then 1
    assert isinstance(result, MachineResponse)
    # Then 2
    assert result.id is not None
    assert result.created_at is not None
    # Then 3
    assert result.name == "Lathe"
    assert result.factory_section_id == s1.id
    assert result.created_by == u2.id
    # Then 4
    assert result.latest_status_type is None
    assert result.latest_status_at is None
    db.rollback()
    # Then 5
    db.expire_all()
    row = db.execute(select(Machine).where(Machine.id == result.id)).scalar_one()
    assert row.name == "Lathe"
    assert row.model_number == "L-200"
    assert row.workspace_id == w1.id
    # Then 6
    assert count_rows(db, MachineSectionAssignment, machine_id=result.id) == 1
    # Then 7
    assert count_rows(db, MachineActivityEvent, machine_id=result.id, event_type="created") == 1


# [claude] MCS-C-02
def test_mcs_c_02__a_duplicate_name_the_409_passes_unchanged_and_the_session_is_rolled_back(
    db, w1, u2, f1, mk_machine, extra,
):
    """MCS-C-02 — a duplicate name: the 409 passes unchanged and the session is rolled back.
    Rules: `create_machine` R2; TC3"""
    a = mk_machine("M1")
    commit_point(db)
    before = written(db)
    before_a = snap(db, a)
    extra()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_machine(db, machine_in=MachineCreate(name="Lathe", factory_id=f1.id), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Machine with name 'Lathe' already exists in this factory"
    # Then 4
    assert count_rows(db, Machine, name="Extra") == 0
    # Then 5
    assert written(db) == before
    # Then 6
    assert snap(db, a) == before_a
    # Then 7
    assert usable(db)


# [claude] MCS-C-03
def test_mcs_c_03__an_unknown_factory_the_404_passes_unchanged(db, w1, u2):
    """MCS-C-03 — an unknown factory: the 404 passes unchanged.
    Rules: `create_machine` R2"""
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_machine(db, machine_in=MachineCreate(name="Lathe", factory_id=MISSING), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory with ID 999999999 not found"
    # Then 4
    assert written(db) == before


# [claude] MCS-C-04
def test_mcs_c_04__a_section_refused_after_the_machine_was_flushed_the_400_passes_and_the_machine_is_not_saved(
    db, w1, u2, f1, sx,
):
    """MCS-C-04 — a section refused after the machine was flushed: the 400 passes and the machine is not saved.
    Rules: `create_machine` R2"""
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_machine(
            db, machine_in=MachineCreate(name="Lathe", factory_id=f1.id, factory_section_id=sx.id),
            workspace_id=w1.id, user_id=u2.id,
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot assign a machine to a deleted factory section"
    # Then 4
    assert count_rows(db, Machine, name="Lathe") == 0
    # Then 5
    assert written(db) == before


# [claude] MCS-C-05
def test_mcs_c_05__an_unknown_user_the_integrityerror_passes_unchanged_nothing_saved_the_session_is_usable(
    db, w1, f1, mk_machine, extra,
):
    """MCS-C-05 — an unknown user: the IntegrityError passes unchanged; nothing saved; the session is usable.
    Rules: `create_machine` R2 (database errors); TC3"""
    mk_machine("M2")
    commit_point(db)
    before = written(db)
    extra()
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        svc.create_machine(db, machine_in=MachineCreate(name="Lathe", factory_id=f1.id), workspace_id=w1.id, user_id=MISSING)
    # Then 2
    assert exc.value.orig.pgcode == "23503"
    # Then 3
    assert count_rows(db, Machine, name="Lathe") == 0
    # Then 4
    assert count_rows(db, Machine, name="Extra") == 0
    # Then 5
    assert written(db) == before
    # Then 6
    assert usable(db)


# [claude] MCS-C-06
def test_mcs_c_06__a_failing_commit_is_rolled_back_and_re_raised_nothing_is_saved(db, w1, u2, f1):
    """MCS-C-06 — a failing commit is rolled back and re-raised; nothing is saved.
    Rules: `create_machine` R3; TC4"""
    commit_point(db)
    before = written(db)
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "commit", side_effect=RuntimeError("boom")), \
                patch.object(db, "rollback", wraps=db.rollback) as rb:
            svc.create_machine(db, machine_in=MachineCreate(name="Lathe", factory_id=f1.id), workspace_id=w1.id, user_id=u2.id)
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert count_rows(db, Machine) == 0
    # Then 4
    assert written(db) == before


# [claude] MCS-C-07
def test_mcs_c_07__a_failing_re_read_after_the_commit_leaves_the_machine_saved(db, w1, u2, f1):
    """MCS-C-07 — a failing re-read after the commit leaves the machine saved.
    Rules: `create_machine` R3; TC5, TC2"""
    commit_point(db)
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "refresh", side_effect=RuntimeError("boom")):
            svc.create_machine(db, machine_in=MachineCreate(name="Lathe", factory_id=f1.id), workspace_id=w1.id, user_id=u2.id)
    # Then 1
    assert str(exc.value) == "boom"
    db.rollback()
    # Then 2
    assert count_rows(db, Machine, name="Lathe") == 1
    # Then 3
    assert count_rows(db, MachineActivityEvent, event_type="created") == 1


# [claude] MCS-C-08
def test_mcs_c_08__a_failure_while_shaping_the_answer_reaches_the_caller_the_machine_stays_saved(db, w1, u2, f1):
    """MCS-C-08 — a failure while shaping the answer reaches the caller; the machine stays saved.
    Rules: `create_machine` R3"""
    commit_point(db)
    with pytest.raises(RuntimeError) as exc:
        with patch.object(svc.activity_manager, "get_latest_status", side_effect=RuntimeError("boom")):
            svc.create_machine(db, machine_in=MachineCreate(name="Lathe", factory_id=f1.id), workspace_id=w1.id, user_id=u2.id)
    # Then 1
    assert str(exc.value) == "boom"
    db.rollback()
    # Then 2
    assert count_rows(db, Machine, name="Lathe") == 1


# [claude] MCS-C-09
@pytest.mark.xfail(strict=True, reason="BUG-950: Blank / whitespace-only machine names accepted; names stored untrimmed")
def test_mcs_c_09__pass_through_bug_950_the_name_is_stored_trimmed(db, w1, u2, f1):
    """MCS-C-09 — pass-through BUG-950: the name is stored trimmed.
    Rules: `create_machine` R1 [BUG-950]"""
    commit_point(db)
    result = svc.create_machine(
        db, machine_in=MachineCreate(name="  Big  PRESS ", factory_id=f1.id), workspace_id=w1.id, user_id=u2.id,
    )

    # Then 1
    assert result.id is not None
    db.rollback()
    # Then 2
    db.expire_all()
    row = db.execute(select(Machine).where(Machine.id == result.id)).scalar_one()
    assert row.name == "Big  PRESS"


# [claude] MCS-C-10
@pytest.mark.xfail(strict=True, reason="BUG-952: Machine duplicate-name check is case- and whitespace-sensitive")
def test_mcs_c_10__pass_through_bug_952_a_name_that_differs_only_in_case_is_refused(db, w1, u2, f1, mk_machine):
    """MCS-C-10 — pass-through BUG-952: a name that differs only in case is refused.
    Rules: `create_machine` R1, R2 [BUG-952]"""
    mk_machine("M1")
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_machine(db, machine_in=MachineCreate(name="LATHE", factory_id=f1.id), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Machine with name 'LATHE' already exists in this factory"
    # Then 4
    assert written(db) == before


# [claude] MCS-C-11
@pytest.mark.xfail(strict=True, reason="BUG-967: Model number and manufacturer stored untrimmed; blank counts as a value")
def test_mcs_c_11__pass_through_bug_967_a_padded_model_number_is_stored_trimmed(db, w1, u2, f1):
    """MCS-C-11 — pass-through BUG-967: a padded model number is stored trimmed.
    Rules: `create_machine` R1 [BUG-967]"""
    commit_point(db)
    result = svc.create_machine(
        db, machine_in=MachineCreate(name="Lathe", factory_id=f1.id, model_number=" L-200 "),
        workspace_id=w1.id, user_id=u2.id,
    )

    # Then 1
    assert result.id is not None
    db.rollback()
    # Then 2
    db.expire_all()
    row = db.execute(select(Machine).where(Machine.id == result.id)).scalar_one()
    assert row.model_number == "L-200"


# [claude] MCS-C-12
@pytest.mark.xfail(strict=True, reason="BUG-953: Machine name uniqueness per factory not enforced by the database")
def test_mcs_c_12__pass_through_bug_953_a_create_that_loses_the_race_gets_the_409_nothing_saved(
    db, w1, u2, f1, mk_machine,
):
    """MCS-C-12 — pass-through BUG-953: a create that loses the race gets the 409, nothing saved.
    Rules: `create_machine` R1, R2 [BUG-953]"""
    mk_machine("M1")
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with patch.object(svc.machine_manager, "_check_name_exists_in_factory", return_value=False):
            svc.create_machine(db, machine_in=MachineCreate(name="Lathe", factory_id=f1.id), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Machine with name 'Lathe' already exists in this factory"
    # Then 4
    assert count_rows(db, Machine, name="Lathe") == 1
    # Then 5
    assert usable(db)


# [claude] MCS-C-13
@pytest.mark.xfail(strict=True, reason="BUG-963: A machine can be created in, or moved to, a soft-deleted factory")
def test_mcs_c_13__pass_through_bug_963_a_soft_deleted_factory_is_refused(db, w1, u2, fd):
    """MCS-C-13 — pass-through BUG-963: a soft-deleted factory is refused.
    Rules: `create_machine` R2 [BUG-963]"""
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_machine(db, machine_in=MachineCreate(name="Lathe", factory_id=fd.id), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot create machine for deleted factory"
    # Then 4
    assert written(db) == before


# [claude] MCS-C-14
@pytest.mark.xfail(strict=True, reason="BUG-972: Over-long model number or manufacturer crashes")
def test_mcs_c_14__pass_through_bug_972_a_model_number_of_201_characters_is_refused_by_the_schema(db, f1):
    """MCS-C-14 — pass-through BUG-972: a model_number of 201 characters is refused by the schema.
    Rules: `create_machine` R1 [BUG-972]"""
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(PydanticValidationError):
        MachineCreate(name="Lathe", factory_id=f1.id, model_number="x" * 201)
    # Then 2
    assert written(db) == before


# [claude] MCS-C-15
@pytest.mark.xfail(strict=True, reason="BUG-951: Machine duplicate-name check only scans 100 machines of the factory")
def test_mcs_c_15__pass_through_bug_951_among_101_machines_every_name_is_refused_as_taken(db, w1, u2, f1, bulk):
    """MCS-C-15 — pass-through BUG-951: among 101 machines every name is refused as taken.
    Rules: `create_machine` R1, R2 [BUG-951]"""
    names_ = bulk(101, "P")
    commit_point(db)
    f1_id = f1.id
    refused = 0
    for n in names_:
        try:
            svc.create_machine(db, machine_in=MachineCreate(name=n, factory_id=f1_id), workspace_id=w1.id, user_id=u2.id)
        except HTTPException as e:
            refused += (e.status_code == 409)

    # Then 1
    assert refused == 101
    # Then 2
    assert count_rows(db, Machine, factory_id=f1_id) == 101


# --------------------------------------------------------------------------- #
# MachineService.get_machine
# --------------------------------------------------------------------------- #

# [claude] MCS-G-01
def test_mcs_g_01__a_live_machine_is_returned_with_its_current_status(db, w1, mk_machine, mk_status):
    """MCS-G-01 — a live machine is returned with its current status.
    Rules: `get_machine` R1"""
    mk_machine("M9")
    m1 = mk_machine("M1")
    mk_status(m1, T1, "RUNNING")
    commit_point(db)
    result = svc.get_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, MachineResponse)
    # Then 2
    assert result.id == m1.id
    assert result.name == "Lathe"
    # Then 3
    assert result.latest_status_type == RUNNING
    assert result.latest_status_at == T1


# [claude] MCS-G-02
def test_mcs_g_02__another_workspaces_id_the_404_passes_unchanged(db, w1, mk_machine):
    """MCS-G-02 — another workspace's id: the 404 passes unchanged.
    Rules: `get_machine` R5, Errors row 1"""
    mk_machine("M1")
    m9 = mk_machine("M9")
    commit_point(db)
    before_m9 = snap(db, m9)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_machine(db, machine_id=m9.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Machine with ID {m9.id} not found"
    # Then 4
    assert snap(db, m9) == before_m9


# [claude] MCS-G-03
def test_mcs_g_03__an_unknown_id_the_404_passes_unchanged(db, w1, mk_machine):
    """MCS-G-03 — an unknown id: the 404 passes unchanged.
    Rules: `get_machine` R5, Errors row 1"""
    mk_machine("M1")
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_machine(db, machine_id=MISSING, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine with ID 999999999 not found"


# [claude] MCS-G-04
@pytest.mark.xfail(strict=True, reason="BUG-955: `get_machine` returns soft-deleted machines")
def test_mcs_g_04__a_soft_deleted_machine_is_hidden_by_default(db, w1, mk_machine):
    """MCS-G-04 — a soft-deleted machine is hidden by default.
    Rules: `get_machine` R2 [BUG-955], Errors row 1"""
    mx = mk_machine("MX")
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_machine(db, machine_id=mx.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Machine with ID {mx.id} not found"


# [claude] MCS-G-05
@pytest.mark.xfail(strict=True, reason="BUG-955: `get_machine` returns soft-deleted machines")
def test_mcs_g_05__include_deleted_true_returns_a_soft_deleted_machine_with_its_last_status(
    db, w1, mk_machine, mk_status,
):
    """MCS-G-05 — include_deleted=True returns a soft-deleted machine with its last status.
    Rules: `get_machine` R3 [BUG-955]"""
    mx = mk_machine("MX")
    mk_status(mx, T1, "OFF")
    commit_point(db)
    result = svc.get_machine(db, machine_id=mx.id, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert result.id == mx.id
    assert result.is_deleted is True
    # Then 2
    assert result.latest_status_type == OFF
    assert result.latest_status_at == T1


# [claude] MCS-G-06
@pytest.mark.xfail(strict=True, reason="BUG-955: `get_machine` returns soft-deleted machines")
def test_mcs_g_06__include_deleted_true_does_not_reach_another_workspace(db, w1, u1, mk_machine):
    """MCS-G-06 — include_deleted=True does not reach another workspace.
    Rules: `get_machine` R3 [BUG-955], Errors row 1"""
    m9 = mk_machine("M9", is_deleted=True, is_active=False, deleted_at=T0, deleted_by=u1.id)
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_machine(db, machine_id=m9.id, workspace_id=w1.id, include_deleted=True)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Machine with ID {m9.id} not found"


# [claude] MCS-G-07
@pytest.mark.xfail(strict=True, reason="BUG-966: A machine of a soft-deleted factory can still be opened by id")
def test_mcs_g_07__a_live_machine_of_a_soft_deleted_factory_is_hidden_by_default(db, w1, mk_machine):
    """MCS-G-07 — a live machine of a soft-deleted factory is hidden by default.
    Rules: `get_machine` R4 [BUG-966], Errors row 1"""
    mf = mk_machine("MF")
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_machine(db, machine_id=mf.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Machine with ID {mf.id} not found"


# [claude] MCS-G-08
@pytest.mark.xfail(strict=True, reason="BUG-966: A machine of a soft-deleted factory can still be opened by id")
def test_mcs_g_08__include_deleted_true_returns_a_machine_of_a_soft_deleted_factory(db, w1, fd, mk_machine):
    """MCS-G-08 — include_deleted=True returns a machine of a soft-deleted factory.
    Rules: `get_machine` R4 [BUG-966]"""
    mf = mk_machine("MF")
    commit_point(db)
    result = svc.get_machine(db, machine_id=mf.id, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert result.id == mf.id
    assert result.factory_id == fd.id
    assert result.is_deleted is False


# [claude] MCS-G-09
def test_mcs_g_09__the_read_neither_commits_nor_rolls_back(db, w1, mk_machine):
    """MCS-G-09 — the read neither commits nor rolls back.
    Rules: `get_machine` R5; TC6"""
    a = mk_machine("M1")
    b = mk_machine("M2")
    commit_point(db)
    mk_machine(name="Pending")
    b.note = "Edited"
    result = svc.get_machine(db, machine_id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert count_rows(db, Machine, name="Pending") == 1
    db.rollback()
    # Then 5
    assert count_rows(db, Machine, name="Pending") == 0
    # Then 6
    assert reread(db, b).note is None


# --------------------------------------------------------------------------- #
# MachineService.get_machines
# --------------------------------------------------------------------------- #

# [claude] MCS-L-01
def test_mcs_l_01__factory_id_reaches_the_manager_and_each_machine_carries_its_status(
    db, w1, f1, mk_machine, mk_status,
):
    """MCS-L-01 — factory_id reaches the manager and each machine carries its status.
    Rules: `get_machines` R1"""
    m1 = mk_machine("M1")
    mk_machine("M3")
    mk_status(m1, T1, "RUNNING")
    commit_point(db)
    result = svc.get_machines(db, workspace_id=w1.id, factory_id=f1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert [r.id for r in result] == [m1.id]
    # Then 3
    assert isinstance(result[0], MachineResponse)
    # Then 4
    assert result[0].latest_status_type == RUNNING
    assert result[0].latest_status_at == T1


# [claude] MCS-L-02
def test_mcs_l_02__a_workspace_without_machines_gives_empty(db, w1, mk_machine):
    """MCS-L-02 — a workspace without machines gives [].
    Rules: `get_machines` R1"""
    mk_machine("M9")
    commit_point(db)
    result = svc.get_machines(db, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] MCS-L-03
def test_mcs_l_03__with_the_defaults_101_machines_give_100(db, w1, bulk):
    """MCS-L-03 — with the defaults 101 machines give 100.
    Rules: `get_machines` R1"""
    bulk(101, "P")
    commit_point(db)
    result = svc.get_machines(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100


# [claude] MCS-L-04
def test_mcs_l_04__limit_1000_reaches_the_manager_and_gives_all_101(db, w1, bulk):
    """MCS-L-04 — limit=1000 reaches the manager and gives all 101.
    Rules: `get_machines` R1"""
    bulk(101, "P")
    commit_point(db)
    result = svc.get_machines(db, workspace_id=w1.id, limit=1000)

    # Then 1
    assert len(result) == 101


# [claude] MCS-L-05
def test_mcs_l_05__skip_reaches_the_manager(db, w1, bulk):
    """MCS-L-05 — skip reaches the manager.
    Rules: `get_machines` R1"""
    bulk(101, "P")
    commit_point(db)
    result = svc.get_machines(db, workspace_id=w1.id, skip=100)

    # Then 1
    assert len(result) == 1


# [claude] MCS-L-06
def test_mcs_l_06__every_list_filter_reaches_the_manager_each_wrong_machine_failing_exactly_one(
    db, w1, f1, f2, s1, mk_machine, mk_link,
):
    """MCS-L-06 — every list filter reaches the manager, each wrong machine failing exactly one.
    Rules: `get_machines` R1"""
    ma = mk_machine("MA", is_running=True, model_number="L-200", manufacturer="Haas")
    mb = mk_machine(
        "MB", name="Basalt", factory_id=f2.id, is_running=True, model_number="L-200", manufacturer="Haas",
    )
    mc = mk_machine("MC", model_number="L-200", manufacturer="Haas")
    mz = mk_machine("MZ", name="Zara", is_running=True, manufacturer="Haas")
    mq = mk_machine("MQ", is_running=True, model_number="L-200")
    mk = mk_machine("MK", is_running=True, model_number="L-200", manufacturer="Bosch")
    mk_machine(name="Salsa", is_running=True, model_number="L-200", manufacturer="Haas")
    mk_link(ma, s1)
    mk_link(mb, s1)
    mk_link(mc, s1)
    mk_link(mz, s1)
    mk_link(mq, s1)
    mk_link(mk, s1)
    commit_point(db)
    result = svc.get_machines(
        db, workspace_id=w1.id, factory_id=f1.id, factory_section_id=s1.id, is_running=True, search="a",
        has_model_number=True, has_manufacturer=True,
    )

    # Then 1
    assert names(result) == ["Alpha"]


# [claude] MCS-L-07
def test_mcs_l_07__maintenance_window_reaches_the_manager(db, w1, mk_machine, mk_order):
    """MCS-L-07 — maintenance_window reaches the manager.
    Rules: `get_machines` R1"""
    ma = mk_machine("MA")
    mk_machine("MZ")
    mk_order(ma, "O1", status="IN_PROGRESS", planned_date=D(-1))
    commit_point(db)
    result = svc.get_machines(db, workspace_id=w1.id, maintenance_window="overdue")

    # Then 1
    assert names(result) == ["Alpha"]


# [claude] MCS-L-08
def test_mcs_l_08__sort_by_and_sort_dir_reach_the_manager(db, w1, mk_machine):
    """MCS-L-08 — sort_by and sort_dir reach the manager.
    Rules: `get_machines` R1"""
    mk_machine("MA", created_at=T1)
    mk_machine("MB", created_at=T2)
    mk_machine("MC", created_at=T0)
    commit_point(db)
    result = svc.get_machines(db, workspace_id=w1.id, sort_by="created_at", sort_dir="desc")

    # Then 1
    assert names(result) == ["Beryl", "Alpha", "Cobalt"]


# [claude] MCS-L-09
def test_mcs_l_09__by_default_a_soft_deleted_machine_is_left_out(db, w1, mk_machine):
    """MCS-L-09 — by default a soft-deleted machine is left out.
    Rules: `get_machines` R2"""
    ma = mk_machine("MA")
    mk_machine("MX")
    commit_point(db)
    result = svc.get_machines(db, workspace_id=w1.id)

    # Then 1
    assert [r.id for r in result] == [ma.id]


# [claude] MCS-L-10
@pytest.mark.xfail(strict=True, reason="BUG-956: Machine list `include_deleted` flag is not reachable from the API")
def test_mcs_l_10__include_deleted_true_lists_soft_deleted_machines_too(db, w1, mk_machine):
    """MCS-L-10 — include_deleted=True lists soft-deleted machines too.
    Rules: `get_machines` R2 [BUG-956]"""
    ma = mk_machine("MA")
    mx = mk_machine("MX")
    commit_point(db)
    result = svc.get_machines(db, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert ids(result) == [ma.id, mx.id]
    # Then 2
    assert [r.is_deleted for r in result if r.id == mx.id] == [True]


# [claude] MCS-L-11
def test_mcs_l_11__the_list_neither_commits_nor_rolls_back(db, w1, w2, f9, mk_machine):
    """MCS-L-11 — the list neither commits nor rolls back.
    Rules: `get_machines` R3; TC6"""
    a = mk_machine("M1")
    b = mk_machine("M2", workspace_id=w2.id, factory_id=f9.id)
    commit_point(db)
    p = mk_machine(name="Pending")
    b.note = "Edited"
    result = svc.get_machines(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == ids([a, p])
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    db.rollback()
    # Then 4
    assert count_rows(db, Machine, name="Pending") == 0
    # Then 5
    assert reread(db, b).note is None


# [claude] MCS-L-12
@pytest.mark.xfail(strict=True, reason="BUG-886: Filtering the machines page by latest status always crashes")
def test_mcs_l_12__pass_through_bug_886_latest_event_type_filters_the_list(db, w1, mk_machine, mk_status):
    """MCS-L-12 — pass-through BUG-886: latest_event_type filters the list.
    Rules: `get_machines` R1 [BUG-886]"""
    ma = mk_machine("MA")
    mz = mk_machine("MZ")
    mk_status(ma, T1, "IDLE")
    mk_status(mz, T1, "RUNNING")
    commit_point(db)
    result = svc.get_machines(db, workspace_id=w1.id, latest_event_type="IDLE")

    # Then 1
    assert names(result) == ["Alpha"]


# [claude] MCS-L-13
@pytest.mark.xfail(strict=False, reason="BUG-887: Machine list name sort is collation-dependent on case-only ties")
def test_mcs_l_13__pass_through_bug_887_a_case_only_tie_on_the_maintenance_sort_falls_to_id(
    db, w1, f2, mk_machine,
):
    """MCS-L-13 — pass-through BUG-887: a case-only tie on the maintenance sort falls to id.
    Rules: `get_machines` R1 [BUG-887]"""
    mk_machine(name="Bolt")
    mk_machine(name="bolt", factory_id=f2.id)
    commit_point(db)
    result = svc.get_machines(db, workspace_id=w1.id, sort_by="maintenance_date")

    # Then 1
    assert names(result) == ["Bolt", "bolt"]


# [claude] MCS-L-14
@pytest.mark.xfail(strict=True, reason="BUG-888: `%` and `_` in machine search act as wildcards")
def test_mcs_l_14__pass_through_bug_888_search_text_is_literal(db, w1, mk_machine):
    """MCS-L-14 — pass-through BUG-888: search text is literal.
    Rules: `get_machines` R1 [BUG-888]"""
    mk_machine("MA", model_number="50%")
    mk_machine("MZ")
    commit_point(db)
    result = svc.get_machines(db, workspace_id=w1.id, search="%")

    # Then 1
    assert names(result) == ["Alpha"]


# [claude] MCS-L-15
@pytest.mark.xfail(strict=True, reason="BUG-889: Filtering machines by a soft-deleted section still returns its machines")
def test_mcs_l_15__pass_through_bug_889_the_id_of_a_soft_deleted_section_finds_nothing(
    db, w1, sx, mk_machine, mk_link,
):
    """MCS-L-15 — pass-through BUG-889: the id of a soft-deleted section finds nothing.
    Rules: `get_machines` R1 [BUG-889]"""
    ma = mk_machine("MA")
    mk_link(ma, sx)
    commit_point(db)
    result = svc.get_machines(db, workspace_id=w1.id, factory_section_id=sx.id)

    # Then 1
    assert result == []


# [claude] MCS-L-16
@pytest.mark.xfail(strict=True, reason="BUG-890: Machines of a soft-deleted factory still appear on the machines page")
def test_mcs_l_16__pass_through_bug_890_a_machine_of_a_soft_deleted_factory_is_not_listed(db, w1, mk_machine):
    """MCS-L-16 — pass-through BUG-890: a machine of a soft-deleted factory is not listed.
    Rules: `get_machines` R1 [BUG-890]"""
    mk_machine("MA")
    mk_machine("MF")
    commit_point(db)
    result = svc.get_machines(db, workspace_id=w1.id)

    # Then 1
    assert names(result) == ["Alpha"]


# [claude] MCS-L-17
@pytest.mark.xfail(strict=True, reason="BUG-892: Machine search text is not trimmed")
def test_mcs_l_17__pass_through_bug_892_search_text_is_trimmed(db, w1, mk_machine):
    """MCS-L-17 — pass-through BUG-892: search text is trimmed.
    Rules: `get_machines` R1 [BUG-892]"""
    mk_machine("MA")
    mk_machine("MZ")
    commit_point(db)
    result = svc.get_machines(db, workspace_id=w1.id, search=" alpha ")

    # Then 1
    assert names(result) == ["Alpha"]


# [claude] MCS-L-18
@pytest.mark.xfail(strict=True, reason="BUG-958: Maintenance filter and sort only look at the first 10 000 machines")
def test_mcs_l_18__pass_through_bug_958_the_window_filter_finds_a_machine_past_the_first_10_000(
    db, w1, bulk, mk_order,
):
    """MCS-L-18 — pass-through BUG-958: the window filter finds a machine past the first 10 000.
    Rules: `get_machines` R1 [BUG-958]"""
    bulk(10001, "B")
    b10000 = db.execute(select(Machine).where(Machine.workspace_id == w1.id, Machine.name == "B10000")).scalar_one()
    mk_order(b10000, "O1", status="DRAFT", planned_date=D(1))
    commit_point(db)
    result = svc.get_machines(db, workspace_id=w1.id, maintenance_window="next_7_days")

    # Then 1
    assert names(result) == ["B10000"]


# [claude] MCS-L-19
@pytest.mark.xfail(strict=True, reason="BUG-973: Maintenance filter only sees 10 years back and 1 year ahead")
def test_mcs_l_19__pass_through_bug_973_work_at_today_plus_366_counts_as_scheduled(db, w1, mk_machine, mk_order):
    """MCS-L-19 — pass-through BUG-973: work at today + 366 counts as scheduled.
    Rules: `get_machines` R1 [BUG-973]"""
    ma = mk_machine("MA")
    mk_machine("MZ")
    mk_order(ma, "O1", status="DRAFT", planned_date=D(366))
    commit_point(db)
    result = svc.get_machines(db, workspace_id=w1.id, maintenance_window="none_scheduled")

    # Then 1
    assert names(result) == ["Zenith"]


# [claude] MCS-L-20
@pytest.mark.xfail(
    strict=True,
    reason="BUG-956: Machine list `include_deleted` flag is not reachable from the API; "
    "BUG-957: Machine list with deleted rows pages first, filters afterwards and ignores most parameters",
)
def test_mcs_l_20__pass_through_bug_957_include_deleted_applies_has_model_number(db, w1, mk_machine):
    """MCS-L-20 — pass-through BUG-957: include_deleted applies has_model_number.
    Rules: `get_machines` R1, R2 [BUG-956, BUG-957]"""
    ma = mk_machine("MA", model_number="L-200")
    mk_machine("MZ")
    commit_point(db)
    result = svc.get_machines(db, workspace_id=w1.id, include_deleted=True, has_model_number=True)

    # Then 1
    assert ids(result) == [ma.id]


# [claude] MCS-L-21
@pytest.mark.xfail(
    strict=False, reason="BUG-1090: Machine list and machine page can show different statuses on a timestamp tie",
)
def test_mcs_l_21__pass_through_bug_1090_on_a_status_tie_the_row_with_the_higher_id_is_shown(
    db, w1, mk_machine, mk_status,
):
    """MCS-L-21 — pass-through BUG-1090: on a status tie the row with the higher id is shown.
    Rules: `get_machines` R1; `_to_machine_responses` R2 [BUG-1090]"""
    m1 = mk_machine("M1")
    mk_status(m1, T2, "RUNNING")
    mk_status(m1, T2, "OFF")
    commit_point(db)
    result = svc.get_machines(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].latest_status_type == OFF


# [claude] MCS-L-22
def test_mcs_l_22__an_empty_page_shapes_nothing_and_reads_no_status(db, w1, mk_machine, mk_status):
    """MCS-L-22 — an empty page shapes nothing and reads no status.
    Rules: `get_machines` R1; `_to_machine_responses` R1"""
    m1 = mk_machine("M1")
    mk_status(m1, T1, "RUNNING")
    commit_point(db)
    w1_id = w1.id
    with sql_logging(db) as sql_log:
        result = svc.get_machines(db, workspace_id=w1_id, skip=5)

    # Then 1
    assert result == []
    # Then 2
    assert not any("FROM machine_activity_events" in s for s in sql_log)


# [claude] MCS-L-23
def test_mcs_l_23__a_page_of_machines_makes_one_status_read_the_default_window_reads_no_work_orders(
    db, w1, mk_machine, mk_status,
):
    """MCS-L-23 — a page of machines makes one status read; the default window reads no work orders.
    Rules: `get_machines` R1 (default `maintenance_window="all"`); `_to_machine_responses` R2"""
    ma = mk_machine("MA")
    mk_machine("MB")
    mc = mk_machine("MC")
    mk_status(ma, T1, "RUNNING")
    mk_status(mc, T1, "IDLE")
    commit_point(db)
    w1_id = w1.id
    with sql_logging(db) as sql_log:
        result = svc.get_machines(db, workspace_id=w1_id)

    # Then 1
    assert names(result) == ["Alpha", "Beryl", "Cobalt"]
    # Then 2
    assert [r.latest_status_type for r in result] == [RUNNING, None, IDLE]
    # Then 3
    assert len([s for s in sql_log if "FROM machine_activity_events" in s]) == 1
    # Then 4
    assert not any("work_orders" in s for s in sql_log)


# --------------------------------------------------------------------------- #
# MachineService.get_upcoming_work
# --------------------------------------------------------------------------- #

# [claude] MCS-W-01
def test_mcs_w_01__the_default_window_is_today_to_today_plus_7_both_ends_included(db, w1, mk_machine, mk_order):
    """MCS-W-01 — the default window is today to today + 7, both ends included.
    Rules: `get_upcoming_work` R1, R2"""
    m1 = mk_machine("M1")
    mk_order(m1, "O1", status="DRAFT", planned_date=D(-1))
    o2 = mk_order(m1, "O2", status="DRAFT", planned_date=D(0))
    o3 = mk_order(m1, "O3", status="DRAFT", planned_date=D(7))
    mk_order(m1, "O4", status="DRAFT", planned_date=D(8))
    commit_point(db)
    result = svc.get_upcoming_work(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert isinstance(result[0], MachineUpcomingWorkRow)
    # Then 3
    assert [i.source_id for i in result[0].items] == [o2.id, o3.id]
    # Then 4
    assert result[0].earliest_date == D(0)
    assert result[0].count == 2


# [claude] MCS-W-02
def test_mcs_w_02__within_days_0_keeps_only_today(db, w1, mk_machine, mk_order):
    """MCS-W-02 — within_days=0 keeps only today.
    Rules: `get_upcoming_work` R1"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="DRAFT", planned_date=D(0))
    mk_order(m1, "O2", status="DRAFT", planned_date=D(1))
    commit_point(db)
    result = svc.get_upcoming_work(db, workspace_id=w1.id, within_days=0)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert [i.source_id for i in result[0].items] == [o1.id]


# [claude] MCS-W-03
def test_mcs_w_03__a_negative_within_days_gives_empty(db, w1, mk_machine, mk_order):
    """MCS-W-03 — a negative within_days gives [].
    Rules: `get_upcoming_work` R1"""
    m1 = mk_machine("M1")
    mk_order(m1, "O1", status="DRAFT", planned_date=D(0))
    commit_point(db)
    result = svc.get_upcoming_work(db, workspace_id=w1.id, within_days=-1)

    # Then 1
    assert result == []


# [claude] MCS-W-04
def test_mcs_w_04__include_overdue_adds_overdue_orders_of_both_open_statuses(db, w1, mk_machine, mk_order):
    """MCS-W-04 — include_overdue adds overdue orders of both open statuses.
    Rules: `get_upcoming_work` R1, R2"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="IN_PROGRESS", planned_date=D(-1))
    o2 = mk_order(m1, "O2", status="DRAFT", planned_date=D(-30))
    mk_order(m1, "O3", status="DRAFT", planned_date=D(8))
    commit_point(db)
    result = svc.get_upcoming_work(db, workspace_id=w1.id, include_overdue=True)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert [i.source_id for i in result[0].items] == [o2.id, o1.id]
    # Then 3
    assert result[0].earliest_date == D(-30)


# [claude] MCS-W-05
def test_mcs_w_05__with_include_overdue_the_window_starts_on_1_january_1970(db, w1, mk_machine, mk_order):
    """MCS-W-05 — with include_overdue the window starts on 1 January 1970.
    Rules: `get_upcoming_work` R1"""
    m1 = mk_machine("M1")
    mk_order(m1, "O1", status="DRAFT", planned_date=date(1969, 12, 31))
    o2 = mk_order(m1, "O2", status="DRAFT", planned_date=date(1970, 1, 1))
    commit_point(db)
    result = svc.get_upcoming_work(db, workspace_id=w1.id, include_overdue=True)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert [i.source_id for i in result[0].items] == [o2.id]


# [claude] MCS-W-06
def test_mcs_w_06__only_open_live_dated_orders_with_a_machine_count(db, w1, mk_machine, mk_order):
    """MCS-W-06 — only open, live, dated orders with a machine count.
    Rules: `get_upcoming_work` R2"""
    m1 = mk_machine("M1")
    od = mk_order(m1, "OD", status="DRAFT", planned_date=D(1))
    op = mk_order(m1, "OP", status="IN_PROGRESS", planned_date=D(1))
    mk_order(m1, "OC", status="COMPLETED", planned_date=D(1))
    mk_order(m1, "OV", status="VOIDED", planned_date=D(1))
    mk_order(m1, "OX", status="DRAFT", planned_date=D(1), is_deleted=True)
    mk_order(m1, "ON", status="DRAFT", planned_date=None)
    mk_order(m1, "OM", status="DRAFT", planned_date=D(1), machine_id=None)
    commit_point(db)
    result = svc.get_upcoming_work(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert sorted(i.source_id for i in result[0].items) == [od.id, op.id]
    # Then 3
    assert result[0].count == 2


# [claude] MCS-W-07
def test_mcs_w_07__another_workspaces_orders_never_count_lower_or_higher_id(
    db, w1, w2, f9, mk_machine, mk_order,
):
    """MCS-W-07 — another workspace's orders never count, lower or higher id.
    Rules: `get_upcoming_work` R2"""
    wt9 = _add(db, WorkOrderType(workspace_id=w2.id, name="Far Repair"))
    m9 = mk_machine("M9")
    m1 = mk_machine("M1")
    mk_order(m9, "Z1", status="DRAFT", planned_date=D(1), workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    o1 = mk_order(m1, "O1", status="DRAFT", planned_date=D(1))
    mk_order(m9, "Z2", status="DRAFT", planned_date=D(1), workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    commit_point(db)
    result = svc.get_upcoming_work(db, workspace_id=w1.id)

    # Then 1
    assert [r.machine_id for r in result] == [m1.id]
    # Then 2
    assert [i.source_id for i in result[0].items] == [o1.id]


# [claude] MCS-W-08
def test_mcs_w_08__orders_on_a_soft_deleted_machine_never_count(db, w1, mk_machine, mk_order):
    """MCS-W-08 — orders on a soft-deleted machine never count.
    Rules: `get_upcoming_work` R3"""
    mx = mk_machine("MX")
    m1 = mk_machine("M1")
    mk_order(mx, "OX", status="DRAFT", planned_date=D(1))
    mk_order(m1, "O1", status="DRAFT", planned_date=D(2))
    commit_point(db)
    result = svc.get_upcoming_work(db, workspace_id=w1.id)

    # Then 1
    assert [r.machine_id for r in result] == [m1.id]


# [claude] MCS-W-09
def test_mcs_w_09__factory_id_is_compared_with_the_orders_factory_not_the_machines(
    db, w1, f1, f2, mk_machine, mk_order,
):
    """MCS-W-09 — factory_id is compared with the order's factory, not the machine's.
    Rules: `get_upcoming_work` R3"""
    m1 = mk_machine("M1")
    m3 = mk_machine("M3")
    o1 = mk_order(m1, "O1", status="DRAFT", planned_date=D(1), factory_id=f2.id)
    mk_order(m3, "O3", status="DRAFT", planned_date=D(1), factory_id=f1.id)
    commit_point(db)
    result = svc.get_upcoming_work(db, workspace_id=w1.id, factory_id=f2.id)

    # Then 1
    assert [r.machine_id for r in result] == [m1.id]
    # Then 2
    assert [i.source_id for i in result[0].items] == [o1.id]


# [claude] MCS-W-10
def test_mcs_w_10__a_row_carries_the_machine_its_section_the_count_and_the_items_by_date_then_id(
    db, w1, f1, s1, mk_machine, mk_link, mk_order,
):
    """MCS-W-10 — a row carries the machine, its section, the count and the items by date then id.
    Rules: `get_upcoming_work` R4"""
    m1 = mk_machine("M1")
    mk_link(m1, s1)
    o1 = mk_order(m1, "O1", status="DRAFT", planned_date=D(2))
    o2 = mk_order(m1, "O2", status="IN_PROGRESS", planned_date=D(1), title="")
    o3 = mk_order(m1, "O3", status="DRAFT", planned_date=D(1))
    commit_point(db)
    result = svc.get_upcoming_work(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].machine_id == m1.id
    assert result[0].name == "Lathe"
    assert result[0].factory_id == f1.id
    # Then 3
    assert result[0].factory_section_id == s1.id
    assert result[0].section_name == "Cutting"
    # Then 4
    assert result[0].earliest_date == D(1)
    assert result[0].count == 3
    assert result[0].sources.work_orders == 3
    # Then 5
    assert [i.source_id for i in result[0].items] == [o2.id, o3.id, o1.id]
    # Then 6
    assert [i.kind for i in result[0].items] == ["work_order", "work_order", "work_order"]
    # Then 7
    assert [i.title for i in result[0].items] == ["WO-O2", "Service", "Service"]
    # Then 8
    assert [i.date for i in result[0].items] == [D(1), D(1), D(2)]
    # Then 9
    assert [i.status for i in result[0].items] == ["IN_PROGRESS", "DRAFT", "DRAFT"]
    # Then 10
    assert [i.work_order_type_name for i in result[0].items] == ["Repair", "Repair", "Repair"]


# [claude] MCS-W-11
def test_mcs_w_11__rows_sort_by_earliest_date_then_name_ignoring_case_then_machine_id(
    db, w1, f2, mk_machine, mk_order,
):
    """MCS-W-11 — rows sort by earliest date, then name ignoring case, then machine id.
    Rules: `get_upcoming_work` R4, R5"""
    x1 = mk_machine(name="gamma")
    x2 = mk_machine(name="Beta")
    x3 = mk_machine(name="Gamma", factory_id=f2.id)
    x4 = mk_machine(name="alpha")
    x5 = mk_machine(name="Zed")
    mk_order(x1, "A1", status="DRAFT", planned_date=D(3))
    mk_order(x2, "A2", status="DRAFT", planned_date=D(1))
    mk_order(x3, "A3", status="DRAFT", planned_date=D(3))
    mk_order(x4, "A4", status="DRAFT", planned_date=D(1))
    mk_order(x5, "A5", status="DRAFT", planned_date=D(0))
    commit_point(db)
    result = svc.get_upcoming_work(db, workspace_id=w1.id)

    # Then 1
    assert [r.name for r in result] == ["Zed", "alpha", "Beta", "gamma", "Gamma"]
    # Then 2
    assert [r.machine_id for r in result][3:] == [x1.id, x3.id]
    # Then 3
    assert result[0].factory_section_id is None
    assert result[0].section_name is None


# [claude] MCS-W-12
@pytest.mark.xfail(strict=True, reason="BUG-1571: Upcoming machine work shows another workspace's machine")
def test_mcs_w_12__bug_1571_a_w1_order_on_another_workspaces_machine_is_left_out_nothing_of_w2_shown(
    db, w1, f9, mk_machine, mk_order,
):
    """MCS-W-12 — BUG-1571: a W1 order on another workspace's machine is left out, nothing of W2 shown.
    Rules: `get_upcoming_work` R6 [BUG-1571]"""
    m9 = mk_machine("M9")
    m1 = mk_machine("M1")
    mk_order(m9, "OS", status="DRAFT", planned_date=D(1))
    mk_order(m1, "O1", status="DRAFT", planned_date=D(2))
    commit_point(db)
    result = svc.get_upcoming_work(db, workspace_id=w1.id)

    # Then 1
    assert [r.machine_id for r in result] == [m1.id]
    # Then 2
    assert "Grinder" not in [r.name for r in result]
    # Then 3
    assert f9.id not in [r.factory_id for r in result]


# [claude] MCS-W-13
@pytest.mark.xfail(strict=True, reason="BUG-1572: Upcoming machine work lists machines of a deleted factory")
def test_mcs_w_13__bug_1572_a_live_machine_of_a_soft_deleted_factory_is_left_out(
    db, w1, fd, mk_machine, mk_order,
):
    """MCS-W-13 — BUG-1572: a live machine of a soft-deleted factory is left out.
    Rules: `get_upcoming_work` R7 [BUG-1572]"""
    mf = mk_machine("MF")
    m1 = mk_machine("M1")
    mk_order(mf, "OK", status="DRAFT", planned_date=D(1), factory_id=fd.id)
    mk_order(m1, "O1", status="DRAFT", planned_date=D(1))
    commit_point(db)
    result = svc.get_upcoming_work(db, workspace_id=w1.id)

    # Then 1
    assert [r.machine_id for r in result] == [m1.id]


# [claude] MCS-W-14
def test_mcs_w_14__upcoming_work_neither_commits_nor_rolls_back(db, w1, mk_machine, mk_order):
    """MCS-W-14 — upcoming work neither commits nor rolls back.
    Rules: `get_upcoming_work` R8; TC6"""
    a = mk_machine("M1")
    b = mk_machine("M2")
    mk_order(a, "O1", status="DRAFT", planned_date=D(1))
    commit_point(db)
    mk_machine(name="Pending")
    b.note = "Edited"
    result = svc.get_upcoming_work(db, workspace_id=w1.id)

    # Then 1
    assert [r.machine_id for r in result] == [a.id]
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    db.rollback()
    # Then 4
    assert count_rows(db, Machine, name="Pending") == 0
    # Then 5
    assert reread(db, b).note is None


# --------------------------------------------------------------------------- #
# MachineService.update_machine
# --------------------------------------------------------------------------- #

# [claude] MCS-U-01
def test_mcs_u_01__a_rename_is_committed_with_its_entry_the_answer_keeps_the_current_status(
    db, w1, u2, mk_machine, mk_status,
):
    """MCS-U-01 — a rename is committed with its entry; the answer keeps the current status.
    Rules: `update_machine` R1; TC1, TC2"""
    m1 = mk_machine("M1")
    mk_status(m1, T1, "RUNNING")
    commit_point(db)
    result = svc.update_machine(
        db, machine_id=m1.id, machine_in=MachineUpdate(name="Big Lathe"), workspace_id=w1.id, user_id=u2.id,
    )

    # Then 1
    assert isinstance(result, MachineResponse)
    # Then 2
    assert result.id == m1.id
    assert result.name == "Big Lathe"
    assert result.updated_by == u2.id
    assert result.updated_at is not None
    # Then 3
    assert result.latest_status_type == RUNNING
    assert result.latest_status_at == T1
    db.rollback()
    # Then 4
    row = reread(db, m1)
    assert row.name == "Big Lathe"
    assert row.updated_by == u2.id
    # Then 5
    assert count_rows(db, MachineActivityEvent, machine_id=m1.id, event_type="updated") == 1


# [claude] MCS-U-02
def test_mcs_u_02__another_workspaces_id_the_404_passes_unchanged_and_the_session_is_rolled_back(
    db, w1, u2, mk_machine, extra,
):
    """MCS-U-02 — another workspace's id: the 404 passes unchanged and the session is rolled back.
    Rules: `update_machine` R2; TC3"""
    mk_machine("M1")
    z = mk_machine("M9")
    commit_point(db)
    before = written(db)
    before_z = snap(db, z)
    extra()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_machine(
            db, machine_id=z.id, machine_in=MachineUpdate(name="Hacked"), workspace_id=w1.id, user_id=u2.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Machine with ID {z.id} not found"
    # Then 4
    assert count_rows(db, Machine, name="Extra") == 0
    # Then 5
    assert snap(db, z) == before_z
    # Then 6
    assert written(db) == before
    # Then 7
    assert usable(db)


# [claude] MCS-U-03
def test_mcs_u_03__a_deleted_machine_the_400_passes_unchanged(db, w1, u2, mk_machine):
    """MCS-U-03 — a deleted machine: the 400 passes unchanged.
    Rules: `update_machine` R2"""
    mx = mk_machine("MX")
    commit_point(db)
    before_mx = snap(db, mx)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_machine(
            db, machine_id=mx.id, machine_in=MachineUpdate(name="Revived"), workspace_id=w1.id, user_id=u2.id,
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update a deleted machine"
    # Then 4
    assert snap(db, mx) == before_mx


# [claude] MCS-U-04
def test_mcs_u_04__a_name_taken_the_409_passes_unchanged(db, w1, u2, mk_machine):
    """MCS-U-04 — a name taken: the 409 passes unchanged.
    Rules: `update_machine` R2"""
    mk_machine("M1")
    b = mk_machine("M2")
    commit_point(db)
    before = written(db)
    before_b = snap(db, b)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_machine(
            db, machine_id=b.id, machine_in=MachineUpdate(name="Lathe"), workspace_id=w1.id, user_id=u2.id,
        )
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Machine with name 'Lathe' already exists in this factory"
    # Then 4
    assert snap(db, b) == before_b
    # Then 5
    assert written(db) == before


# [claude] MCS-U-05
def test_mcs_u_05__an_unknown_target_factory_the_404_passes_unchanged(db, w1, u2, mk_machine):
    """MCS-U-05 — an unknown target factory: the 404 passes unchanged.
    Rules: `update_machine` R2"""
    a = mk_machine("M1")
    commit_point(db)
    before_a = snap(db, a)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_machine(
            db, machine_id=a.id, machine_in=MachineUpdate(factory_id=MISSING), workspace_id=w1.id, user_id=u2.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory with ID 999999999 not found"
    # Then 4
    assert snap(db, a) == before_a


# [claude] MCS-U-06
def test_mcs_u_06__a_section_refused_after_the_manager_flushed_the_rename_nothing_is_saved(
    db, w1, u2, sx, mk_machine,
):
    """MCS-U-06 — a section refused after the manager flushed the rename: nothing is saved.
    Rules: `update_machine` R2"""
    a = mk_machine("M1")
    commit_point(db)
    before = written(db)
    before_a = snap(db, a)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_machine(
            db, machine_id=a.id, machine_in=MachineUpdate(name="Big Lathe", factory_section_id=sx.id),
            workspace_id=w1.id, user_id=u2.id,
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot assign a machine to a deleted factory section"
    # Then 4
    assert snap(db, a) == before_a
    # Then 5
    assert written(db) == before


# [claude] MCS-U-07
def test_mcs_u_07__a_valueerror_while_shaping_after_the_commit_reaches_the_caller_unchanged_the_edit_stays_saved(
    db, w1, u2, mk_machine, mk_status,
):
    """MCS-U-07 — a ValueError while shaping after the commit reaches the caller unchanged; the edit stays saved.
    Rules: `update_machine` R3; `delete_machine` R3 (another method)"""
    a = mk_machine("M1")
    mk_status(a, T1, "running")
    commit_point(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        svc.update_machine(
            db, machine_id=a.id, machine_in=MachineUpdate(note="Bay 4"), workspace_id=w1.id, user_id=u2.id,
        )
    # Then 2
    assert type(exc.value) is ValueError
    db.rollback()
    # Then 3
    assert reread(db, a).note == "Bay 4"


# [claude] MCS-U-08
@pytest.mark.xfail(strict=True, reason="BUG-954: Moving a machine into a factory where its name is taken is not checked")
def test_mcs_u_08__pass_through_bug_954_a_move_into_a_taken_name_is_refused(db, w1, u2, f2, mk_machine):
    """MCS-U-08 — pass-through BUG-954: a move into a taken name is refused.
    Rules: `update_machine` R2 [BUG-954]"""
    a = mk_machine("M1")
    mk_machine("M3", name="Lathe")
    commit_point(db)
    before_a = snap(db, a)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_machine(
            db, machine_id=a.id, machine_in=MachineUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id,
        )
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Machine with name 'Lathe' already exists in this factory"
    # Then 4
    assert snap(db, a) == before_a


# [claude] MCS-U-09
@pytest.mark.xfail(strict=True, reason="BUG-959: `updated_by` stamped on no-op machine updates")
def test_mcs_u_09__pass_through_bug_959_an_empty_update_by_an_unknown_user_succeeds_and_writes_nothing(
    db, w1, mk_machine,
):
    """MCS-U-09 — pass-through BUG-959: an empty update by an unknown user succeeds and writes nothing.
    Rules: `update_machine` R1 [BUG-959]"""
    a = mk_machine("M1")
    commit_point(db)
    before_a = snap(db, a)
    result = svc.update_machine(db, machine_id=a.id, machine_in=MachineUpdate(), workspace_id=w1.id, user_id=MISSING)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert snap(db, a) == before_a


# [claude] MCS-U-10
@pytest.mark.xfail(strict=True, reason="BUG-961: Updating a machine with `factory_id=0` crashes instead of 404")
def test_mcs_u_10__pass_through_bug_961_factory_id_0_gets_the_404(db, w1, u2, mk_machine):
    """MCS-U-10 — pass-through BUG-961: factory id 0 gets the 404.
    Rules: `update_machine` R2 [BUG-961]"""
    a = mk_machine("M1")
    commit_point(db)
    before_a = snap(db, a)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_machine(db, machine_id=a.id, machine_in=MachineUpdate(factory_id=0), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory with ID 0 not found"
    # Then 4
    assert snap(db, a) == before_a


# [claude] MCS-U-11
@pytest.mark.xfail(strict=True, reason="BUG-962: Machine model number, manufacturer and note cannot be cleared")
def test_mcs_u_11__pass_through_bug_962_an_explicit_null_clears_model_number(db, w1, u2, mk_machine):
    """MCS-U-11 — pass-through BUG-962: an explicit null clears model_number.
    Rules: `update_machine` R1 [BUG-962]"""
    a = mk_machine("M1", model_number="L-200")
    commit_point(db)
    result = svc.update_machine(
        db, machine_id=a.id, machine_in=MachineUpdate(model_number=None), workspace_id=w1.id, user_id=u2.id,
    )

    # Then 1
    assert result.id == a.id
    db.rollback()
    # Then 2
    assert reread(db, a).model_number is None


# [claude] MCS-U-12
@pytest.mark.xfail(strict=True, reason="BUG-964: A machine inside a soft-deleted factory can still be edited or moved out")
def test_mcs_u_12__pass_through_bug_964_an_edit_of_a_machine_in_a_soft_deleted_factory_is_refused(
    db, w1, u2, mk_machine,
):
    """MCS-U-12 — pass-through BUG-964: an edit of a machine in a soft-deleted factory is refused.
    Rules: `update_machine` R2 [BUG-964]"""
    a = mk_machine("MF")
    commit_point(db)
    before = written(db)
    before_a = snap(db, a)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_machine(
            db, machine_id=a.id, machine_in=MachineUpdate(name="Big Kiln"), workspace_id=w1.id, user_id=u2.id,
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update a deleted machine"
    # Then 4
    assert snap(db, a) == before_a
    # Then 5
    assert written(db) == before


# [claude] MCS-U-13
@pytest.mark.xfail(strict=True, reason="BUG-970: A moved machine keeps its old factory's section")
def test_mcs_u_13__pass_through_bug_970_a_move_without_a_section_clears_the_old_factorys_section(
    db, w1, u2, f2, s1, mk_machine, mk_link,
):
    """MCS-U-13 — pass-through BUG-970: a move without a section clears the old factory's section.
    Rules: `update_machine` R1 [BUG-970]"""
    a = mk_machine("M1")
    mk_link(a, s1)
    commit_point(db)
    result = svc.update_machine(
        db, machine_id=a.id, machine_in=MachineUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id,
    )

    # Then 1
    assert result.factory_id == f2.id
    db.rollback()
    # Then 2
    assert reread(db, a).factory_id == f2.id
    # Then 3
    assert count_rows(db, MachineSectionAssignment, machine_id=a.id) == 0


# [claude] MCS-U-14
@pytest.mark.xfail(strict=True, reason="BUG-971: Editing a machine fails when its section was deleted")
def test_mcs_u_14__pass_through_bug_971_an_edit_re_sending_a_left_over_link_to_a_deleted_section_succeeds(
    db, w1, u2, sx, mk_machine, mk_link,
):
    """MCS-U-14 — pass-through BUG-971: an edit re-sending a left-over link to a deleted section succeeds.
    Rules: `update_machine` R1 [BUG-971]"""
    a = mk_machine("M1")
    mk_link(a, sx)
    commit_point(db)
    result = svc.update_machine(
        db, machine_id=a.id, machine_in=MachineUpdate(note="Bay 4", factory_section_id=sx.id),
        workspace_id=w1.id, user_id=u2.id,
    )

    # Then 1
    assert result.id == a.id
    db.rollback()
    # Then 2
    assert reread(db, a).note == "Bay 4"
    # Then 3
    assert count_rows(db, MachineSectionAssignment, machine_id=a.id, factory_section_id=sx.id) == 1


# [claude] MCS-U-15
@pytest.mark.xfail(strict=True, reason="BUG-975: Open work orders stay in the old factory when their machine moves")
def test_mcs_u_15__pass_through_bug_975_an_open_order_follows_the_moved_machine(
    db, w1, u2, f2, mk_machine, mk_order,
):
    """MCS-U-15 — pass-through BUG-975: an open order follows the moved machine.
    Rules: `update_machine` R1 [BUG-975]"""
    a = mk_machine("M1")
    o1 = mk_order(a, "O1", status="DRAFT", planned_date=None)
    commit_point(db)
    result = svc.update_machine(
        db, machine_id=a.id, machine_in=MachineUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id,
    )

    # Then 1
    assert result.factory_id == f2.id
    db.rollback()
    # Then 2
    assert reread(db, a).factory_id == f2.id
    # Then 3
    assert reread(db, o1).factory_id == f2.id


# --------------------------------------------------------------------------- #
# MachineService.delete_machine
# --------------------------------------------------------------------------- #

# [claude] MCS-D-01
def test_mcs_d_01__a_soft_delete_and_its_entry_are_committed_the_answer_keeps_the_last_status(
    db, w1, u2, mk_machine, mk_status,
):
    """MCS-D-01 — a soft delete and its entry are committed; the answer keeps the last status.
    Rules: `delete_machine` R1; TC1"""
    a = mk_machine("M1")
    mk_status(a, T1, "RUNNING")
    commit_point(db)
    result = svc.delete_machine(db, machine_id=a.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert isinstance(result, MachineResponse)
    # Then 2
    assert result.id == a.id
    assert result.is_deleted is True
    assert result.is_active is False
    assert result.deleted_by == u2.id
    assert result.deleted_at is not None
    # Then 3
    assert result.latest_status_type == RUNNING
    assert result.latest_status_at == T1
    db.rollback()
    # Then 4
    row = reread(db, a)
    assert row.is_deleted is True
    assert row.is_active is False
    assert row.deleted_by == u2.id
    assert row.deleted_at is not None
    # Then 5
    assert count_rows(db, MachineActivityEvent, machine_id=a.id, event_type="deactivated") == 1


# [claude] MCS-D-02
def test_mcs_d_02__an_already_deleted_machine_the_400_passes_unchanged_and_the_session_is_rolled_back(
    db, w1, u2, mk_machine, extra,
):
    """MCS-D-02 — an already deleted machine: the 400 passes unchanged and the session is rolled back.
    Rules: `delete_machine` R1, Errors row 2; TC3"""
    a = mk_machine("MX")
    commit_point(db)
    before_a = snap(db, a)
    extra()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_machine(db, machine_id=a.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Machine is already deleted"
    # Then 4
    assert count_rows(db, Machine, name="Extra") == 0
    # Then 5
    assert snap(db, a) == before_a
    # Then 6
    assert usable(db)


# [claude] MCS-D-03
def test_mcs_d_03__an_unknown_id_the_404_passes_unchanged(db, w1, u2, mk_machine):
    """MCS-D-03 — an unknown id: the 404 passes unchanged.
    Rules: `delete_machine` R1, Errors row 1"""
    a = mk_machine("M1")
    commit_point(db)
    before_a = snap(db, a)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_machine(db, machine_id=MISSING, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine with ID 999999999 not found"
    # Then 4
    assert snap(db, a) == before_a


# [claude] MCS-D-04
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcs_d_04__the_managers_in_use_valueerror_becomes_the_400_with_the_blockers_as_given_after_a_rollback(
    db, w1, u2, mk_machine, extra,
):
    """MCS-D-04 — the manager's in-use ValueError becomes the 400 with the blockers as given, after a rollback.
    Rules: `delete_machine` R2 [BUG-968], Errors row 4"""
    a = mk_machine("M1")
    commit_point(db)
    before_a = snap(db, a)
    extra()
    # Then 1
    with pytest.raises(AppValidationError) as exc:
        with patch.object(
            svc.machine_manager, "delete_machine",
            side_effect=ValueError("Machine has stock or open orders", [{"type": "machine_stock", "id": 3}, {"type": "other_workspace"}]),
        ):
            svc.delete_machine(db, machine_id=a.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Machine has stock or open orders"
    # Then 4
    assert exc.value.errors == [{"type": "machine_stock", "id": 3}, {"type": "other_workspace"}]
    # Then 5
    assert count_rows(db, Machine, name="Extra") == 0
    # Then 6
    assert snap(db, a) == before_a


# [claude] MCS-D-05
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcs_d_05__end_to_end_stock_on_the_machine_blocks_the_delete_with_a_400_that_lists_it(
    db, w1, u2, mk_machine, mk_stock,
):
    """MCS-D-05 — end to end: stock on the machine blocks the delete with a 400 that lists it.
    Rules: `delete_machine` R2 [BUG-968], Errors row 4"""
    a = mk_machine("M1")
    st1 = mk_stock(a, qty=5)
    commit_point(db)
    before = written(db)
    before_a = snap(db, a)
    # Then 1
    with pytest.raises(AppValidationError) as exc:
        svc.delete_machine(db, machine_id=a.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Machine has stock or open orders"
    # Then 4
    assert exc.value.errors == [{"type": "machine_stock", "id": st1.id}]
    # Then 5
    assert snap(db, a) == before_a
    # Then 6
    assert written(db) == before


# [claude] MCS-D-06
def test_mcs_d_06__a_valueerror_while_shaping_after_the_delete_is_not_translated_the_delete_stays_saved(
    db, w1, u2, mk_machine, mk_status,
):
    """MCS-D-06 — a ValueError while shaping after the delete is not translated; the delete stays saved.
    Rules: `delete_machine` R3, R4"""
    a = mk_machine("M1")
    mk_status(a, T1, "running")
    commit_point(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        svc.delete_machine(db, machine_id=a.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert type(exc.value) is ValueError
    db.rollback()
    # Then 3
    assert reread(db, a).is_deleted is True


# [claude] MCS-D-07
@pytest.mark.xfail(strict=True, reason="BUG-965: A machine inside a soft-deleted factory can still be deleted")
def test_mcs_d_07__pass_through_bug_965_a_machine_of_a_soft_deleted_factory_is_refused(db, w1, u2, mk_machine):
    """MCS-D-07 — pass-through BUG-965: a machine of a soft-deleted factory is refused.
    Rules: `delete_machine` R1 [BUG-965], Errors row 3"""
    a = mk_machine("MF")
    commit_point(db)
    before = written(db)
    before_a = snap(db, a)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_machine(db, machine_id=a.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot delete a machine of a deleted factory"
    # Then 4
    assert snap(db, a) == before_a
    # Then 5
    assert written(db) == before


# --------------------------------------------------------------------------- #
# MachineService.create_machine_event
# --------------------------------------------------------------------------- #

# [claude] MCS-E-01
def test_mcs_e_01__a_status_change_is_committed_and_the_managers_response_returned(db, w1, u2, mk_machine):
    """MCS-E-01 — a status change is committed and the manager's response returned.
    Rules: `create_machine_event` R1; TC1"""
    a = mk_machine("M1")
    commit_point(db)
    result = svc.create_machine_event(
        db, event_in=MachineEventCreate(machine_id=a.id, event_type=RUNNING), workspace_id=w1.id, user_id=u2.id,
    )

    # Then 1
    assert isinstance(result, MachineEventResponse)
    # Then 2
    assert result.id is not None
    db.rollback()
    # Then 3
    assert count_rows(db, MachineActivityEvent, machine_id=a.id, event_type="status_updated") == 1
    # Then 4
    [row] = db.execute(select(MachineActivityEvent).where(
        MachineActivityEvent.machine_id == a.id, MachineActivityEvent.event_type == "status_updated",
    )).scalars().all()
    assert row.id == result.id
    assert row.performed_by == u2.id
    assert row.metadata_json["status"] == "RUNNING"
    # Then 5
    assert reread(db, a).is_running is True


# [claude] MCS-E-02
def test_mcs_e_02__another_workspaces_machine_the_404_passes_unchanged_and_the_session_is_rolled_back(
    db, w1, u2, mk_machine, extra,
):
    """MCS-E-02 — another workspace's machine: the 404 passes unchanged and the session is rolled back.
    Rules: `create_machine_event` R2; TC3"""
    z = mk_machine("M9")
    commit_point(db)
    before = written(db)
    before_z = snap(db, z)
    extra()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_machine_event(
            db, event_in=MachineEventCreate(machine_id=z.id, event_type=RUNNING), workspace_id=w1.id, user_id=u2.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Machine with ID {z.id} not found"
    # Then 4
    assert count_rows(db, Machine, name="Extra") == 0
    # Then 5
    assert snap(db, z) == before_z
    # Then 6
    assert written(db) == before
    # Then 7
    assert usable(db)


# [claude] MCS-E-03
def test_mcs_e_03__a_deleted_machine_the_400_passes_unchanged(db, w1, u2, mk_machine):
    """MCS-E-03 — a deleted machine: the 400 passes unchanged.
    Rules: `create_machine_event` R2"""
    a = mk_machine("MX")
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_machine_event(
            db, event_in=MachineEventCreate(machine_id=a.id, event_type=RUNNING), workspace_id=w1.id, user_id=u2.id,
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot create event for a deleted machine"
    # Then 4
    assert written(db) == before


# [claude] MCS-E-04
def test_mcs_e_04__the_same_status_again_the_400_passes_unchanged(db, w1, u2, mk_machine, mk_status):
    """MCS-E-04 — the same status again: the 400 passes unchanged.
    Rules: `create_machine_event` R2"""
    a = mk_machine("M1", is_running=True)
    mk_status(a, T1, "RUNNING")
    commit_point(db)
    before_a = snap(db, a)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_machine_event(
            db, event_in=MachineEventCreate(machine_id=a.id, event_type=RUNNING), workspace_id=w1.id, user_id=u2.id,
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Machine is already in 'RUNNING' state"
    # Then 4
    assert count_rows(db, MachineActivityEvent, machine_id=a.id) == 1
    # Then 5
    assert snap(db, a) == before_a


# [claude] MCS-E-05
@pytest.mark.xfail(strict=True, reason="BUG-960: Machine status change does not lock the row")
def test_mcs_e_05__pass_through_bug_960_the_machine_row_is_read_for_update_before_the_current_status(
    db, w1, u2, mk_machine,
):
    """MCS-E-05 — pass-through BUG-960: the machine row is read FOR UPDATE before the current status.
    Rules: `create_machine_event` R1 [BUG-960]"""
    a = mk_machine("M1")
    commit_point(db)
    event_in = MachineEventCreate(machine_id=a.id, event_type=RUNNING)
    w1_id, u2_id = w1.id, u2.id
    with sql_logging(db) as sql_log:
        result = svc.create_machine_event(db, event_in=event_in, workspace_id=w1_id, user_id=u2_id)

    # Then 1
    assert result.id is not None
    # Then 2
    lock = [i for i, s in enumerate(sql_log) if "FROM machines" in s and "FOR UPDATE" in s]
    assert len(lock) >= 1
    # Then 3
    assert lock[0] < min(i for i, s in enumerate(sql_log) if "FROM machine_activity_events" in s)


# [claude] MCS-E-06
@pytest.mark.xfail(strict=True, reason="BUG-974: Manual status change accepted on a machine of a soft-deleted factory")
def test_mcs_e_06__pass_through_bug_974_a_change_on_a_machine_of_a_soft_deleted_factory_is_refused(
    db, w1, u2, mk_machine,
):
    """MCS-E-06 — pass-through BUG-974: a change on a machine of a soft-deleted factory is refused.
    Rules: `create_machine_event` R2 [BUG-974]"""
    a = mk_machine("MF")
    commit_point(db)
    before = written(db)
    before_a = snap(db, a)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_machine_event(
            db, event_in=MachineEventCreate(machine_id=a.id, event_type=RUNNING), workspace_id=w1.id, user_id=u2.id,
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot create event for a machine of a deleted factory"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, a) == before_a


# --------------------------------------------------------------------------- #
# MachineService.get_machine_activity
# --------------------------------------------------------------------------- #

# [claude] MCS-A-01
def test_mcs_a_01__entries_come_newest_first_each_with_its_columns_and_performer_name(
    db, w1, u1, mk_machine, mk_event,
):
    """MCS-A-01 — entries come newest first, each with its columns and performer name.
    Rules: `get_machine_activity` R1, R3"""
    m1 = mk_machine("M1")
    a = mk_event(m1, T1, performed_by=u1.id)
    b = mk_event(m1, T2)
    commit_point(db)
    result = svc.get_machine_activity(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert [r.id for r in result] == [b.id, a.id]
    # Then 2
    assert isinstance(result[0], MachineActivityEventResponse)
    # Then 3
    assert result[1].workspace_id == w1.id
    assert result[1].machine_id == m1.id
    assert result[1].event_type == "item_added"
    assert result[1].description == "Logged"
    # Then 4
    assert result[1].performed_by == u1.id
    assert result[1].created_at == T1
    assert result[1].performer_name == u1.name
    # Then 5
    assert result[0].performed_by is None
    assert result[0].performer_name is None


# [claude] MCS-A-02
def test_mcs_a_02__from_date_to_date_and_event_type_reach_the_manager(db, w1, mk_machine, mk_event):
    """MCS-A-02 — from_date, to_date and event_type reach the manager.
    Rules: `get_machine_activity` R1"""
    m1 = mk_machine("M1")
    mk_event(m1, datetime(2026, 3, 4, 10, 0, 0), event_type="status_updated")
    mk_event(m1, datetime(2026, 3, 5, 10, 0, 0))
    c = mk_event(m1, datetime(2026, 3, 5, 10, 0, 0), event_type="status_updated")
    mk_event(m1, datetime(2026, 3, 6, 10, 0, 0), event_type="status_updated")
    commit_point(db)
    result = svc.get_machine_activity(
        db, machine_id=m1.id, workspace_id=w1.id, from_date=date(2026, 3, 5), to_date=date(2026, 3, 5),
        event_type="status_updated",
    )

    # Then 1
    assert [r.id for r in result] == [c.id]


# [claude] MCS-A-03
def test_mcs_a_03__skip_and_limit_reach_the_manager(db, w1, mk_machine, mk_event):
    """MCS-A-03 — skip and limit reach the manager.
    Rules: `get_machine_activity` R1"""
    m1 = mk_machine("M1")
    mk_event(m1, T0)
    b = mk_event(m1, T1)
    c = mk_event(m1, T2)
    mk_event(m1, T3)
    commit_point(db)
    result = svc.get_machine_activity(db, machine_id=m1.id, workspace_id=w1.id, skip=1, limit=2)

    # Then 1
    assert [r.id for r in result] == [c.id, b.id]


# [claude] MCS-A-04
def test_mcs_a_04__another_workspaces_machine_the_404_passes_unchanged(db, w1, mk_machine, mk_event):
    """MCS-A-04 — another workspace's machine: the 404 passes unchanged.
    Rules: `get_machine_activity` R2"""
    m9 = mk_machine("M9")
    mk_event(m9, T1)
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_machine_activity(db, machine_id=m9.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Machine with ID {m9.id} not found"


# [claude] MCS-A-05
def test_mcs_a_05__a_soft_deleted_machines_activity_is_returned(db, w1, mk_machine, mk_event):
    """MCS-A-05 — a soft-deleted machine's activity is returned.
    Rules: `get_machine_activity` R2"""
    mx = mk_machine("MX")
    a = mk_event(mx, T1)
    commit_point(db)
    result = svc.get_machine_activity(db, machine_id=mx.id, workspace_id=w1.id)

    # Then 1
    assert [r.id for r in result] == [a.id]


# [claude] MCS-A-06
def test_mcs_a_06__metadata_empty_dict_reads_as_none(db, w1, mk_machine, mk_event):
    """MCS-A-06 — metadata {} reads as None.
    Rules: `get_machine_activity` R4"""
    m1 = mk_machine("M1")
    a = mk_event(m1, T1, metadata_json={})
    commit_point(db)
    result = svc.get_machine_activity(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert [r.id for r in result] == [a.id]
    # Then 2
    assert result[0].metadata is None


# [claude] MCS-A-07
def test_mcs_a_07__metadata_none_reads_as_none(db, w1, mk_machine, mk_event):
    """MCS-A-07 — metadata None reads as None.
    Rules: `get_machine_activity` R4"""
    m1 = mk_machine("M1")
    mk_event(m1, T1, metadata_json=None)
    commit_point(db)
    result = svc.get_machine_activity(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert result[0].metadata is None


# [claude] MCS-A-08
def test_mcs_a_08__listed_keys_are_kept_absent_ones_are_none_others_are_dropped_the_row_is_not_changed(
    db, w1, mk_machine, mk_event,
):
    """MCS-A-08 — listed keys are kept, absent ones are None, others are dropped; the row is not changed.
    Rules: `get_machine_activity` R4"""
    m1 = mk_machine("M1")
    a = mk_event(m1, T1, metadata_json={"quantity": 3, "status": "RUNNING", "item_id": 5, "note": "x"})
    commit_point(db)
    result = svc.get_machine_activity(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert result[0].metadata.quantity == 3
    assert result[0].metadata.status == "RUNNING"
    assert result[0].metadata.item_id == 5
    # Then 2
    assert result[0].metadata.changes is None
    assert result[0].metadata.work_order_id is None
    # Then 3
    assert "note" not in result[0].metadata.model_dump()
    # Then 4
    assert reread(db, a).metadata_json == {"quantity": 3, "status": "RUNNING", "item_id": 5, "note": "x"}


# [claude] MCS-A-09
def test_mcs_a_09__a_single_key_alone_is_enough_to_build_metadata(db, w1, mk_machine, mk_event):
    """MCS-A-09 — a single key alone is enough to build metadata.
    Rules: `get_machine_activity` R4"""
    m1 = mk_machine("M1")
    mk_event(m1, T1, metadata_json={"note": "x"})
    commit_point(db)
    result = svc.get_machine_activity(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert result[0].metadata is not None
    # Then 2
    assert result[0].metadata.status is None
    assert result[0].metadata.quantity is None


# [claude] MCS-A-10
def test_mcs_a_10__a_metadata_the_schema_cannot_read_fails_the_whole_call(db, w1, mk_machine, mk_event):
    """MCS-A-10 — a metadata the schema cannot read fails the whole call.
    Rules: `get_machine_activity` R5"""
    m1 = mk_machine("M1")
    mk_event(m1, T1)
    mk_event(m1, T2, metadata_json={"quantity": 2.5})
    commit_point(db)
    # Then 1
    with pytest.raises(PydanticValidationError):
        svc.get_machine_activity(db, machine_id=m1.id, workspace_id=w1.id)


# [claude] MCS-A-11
def test_mcs_a_11__the_activity_read_neither_commits_nor_rolls_back(db, w1, mk_machine, mk_event):
    """MCS-A-11 — the activity read neither commits nor rolls back.
    Rules: `get_machine_activity` R6; TC6"""
    a = mk_machine("M1")
    b = mk_machine("M2")
    e = mk_event(a, T1)
    commit_point(db)
    mk_machine(name="Pending")
    b.note = "Edited"
    result = svc.get_machine_activity(db, machine_id=a.id, workspace_id=w1.id)

    # Then 1
    assert [r.id for r in result] == [e.id]
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    db.rollback()
    # Then 4
    assert count_rows(db, Machine, name="Pending") == 0
    # Then 5
    assert reread(db, b).note is None


# [claude] MCS-A-12
def test_mcs_a_12__an_unknown_machine_the_404_passes_unchanged(db, w1, mk_machine):
    """MCS-A-12 — an unknown machine: the 404 passes unchanged.
    Rules: `get_machine_activity` R2"""
    mk_machine("M1")
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_machine_activity(db, machine_id=MISSING, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine with ID 999999999 not found"


# [claude] MCS-A-13
@pytest.mark.xfail(strict=True, reason="BUG-1141: One page of machine activity makes one extra read per entry")
def test_mcs_a_13__pass_through_bug_1141_five_entries_by_one_person_make_at_most_three_reads(
    db, w1, u1, mk_machine, mk_event,
):
    """MCS-A-13 — pass-through BUG-1141: five entries by one person make at most three reads.
    Rules: `get_machine_activity` R1 [BUG-1141]"""
    m1 = mk_machine("M1")
    for k in range(1, 6):
        mk_event(m1, datetime(2026, 3, k, 10, 0, 0), performed_by=u1.id)
    commit_point(db)
    m1_id, w1_id, u1_name = m1.id, w1.id, u1.name
    with sql_logging(db) as sql_log:
        result = svc.get_machine_activity(db, machine_id=m1_id, workspace_id=w1_id)

    # Then 1
    assert [r.performer_name for r in result] == [u1_name] * 5
    # Then 2
    assert len(sql_log) <= 3


# [claude] MCS-A-14
def test_mcs_a_14__without_skip_or_limit_101_entries_give_the_100_newest(db, w1, mk_machine, mk_event):
    """MCS-A-14 — without skip or limit, 101 entries give the 100 newest.
    Rules: `get_machine_activity` R1a"""
    m1 = mk_machine("M1")
    for k in range(1, 101):
        mk_event(m1, T0 + timedelta(minutes=k))
    o = mk_event(m1, T0)
    commit_point(db)
    result = svc.get_machine_activity(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert o.id not in [r.id for r in result]
    # Then 3
    assert min(r.created_at for r in result) == T0 + timedelta(minutes=1)
