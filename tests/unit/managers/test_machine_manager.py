"""Unit tests for app/managers/machine_manager.py.

Implements tests/unit/managers/machine_manager.cases.md, one test per case, in
card order. Real Postgres session (`db` fixture). The only thing patched in
every test is the clock: `app.dao.machine.utcnow` returns NOW (Conventions,
Externals). The race-simulation cards MCM-C-41 and MCM-U-51 additionally patch
`MachineManager._check_name_exists_in_factory`, as Conventions allow. `date` is
never patched.

Normal mode: every test is written from its card and carries a `# [claude] <ID>`
comment. Row names of the cards are the lower-case names here (M1 -> m1, `F1.id`
-> `f1.id`); `# Then N` marks the checks of the card's Then line N.
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`)
import re
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from psycopg2.errors import ForeignKeyViolation
from pydantic import ValidationError
from sqlalchemy import event, func, insert, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import DataError, IntegrityError

from app.managers.machine_manager import MachineManager, machine_manager
from app.models.enums import (
    InventoryTypeEnum,
    MachineEventTypeEnum,
    MaintenanceTypeEnum,
)
from app.models.factory import Factory
from app.models.factory_section import FactorySection
from app.models.inventory_ledger import InventoryLedger
from app.models.item import Item
from app.models.machine import Machine
from app.models.machine_activity_event import MachineActivityEvent
from app.models.machine_item import MachineItem
from app.models.machine_item_ledger import MachineItemLedger
from app.models.machine_maintenance_log import MachineMaintenanceLog
from app.models.machine_section_assignment import MachineSectionAssignment
from app.models.production_formula import ProductionFormula
from app.models.production_formula_stage import ProductionFormulaStage
from app.models.production_line import ProductionLine
from app.models.purchase_order import PurchaseOrder
from app.models.status import Status
from app.models.transfer_order import TransferOrder
from app.models.work_order import WorkOrder
from app.models.work_order_approver import WorkOrderApprover
from app.models.work_order_assignee import WorkOrderAssignee
from app.models.work_order_event import WorkOrderEvent
from app.models.work_order_item import WorkOrderItem
from app.models.work_order_template import WorkOrderTemplate
from app.models.work_order_type import WorkOrderType
from app.schemas.machine import MachineCreate, MachineUpdate
from app.schemas.machine_event import MachineEventCreate, MachineEventResponse
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "M = the singleton machine_manager" (a module-level name, not a fixture)
M = machine_manager

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999

# Conventions "T0", "T1", "T2", "NOW" (all naive)
T0 = datetime(2025, 12, 1, 8, 0, 0)  # noqa: DTZ001
T1 = datetime(2026, 1, 1, 9, 0, 0)  # noqa: DTZ001
T2 = datetime(2026, 1, 1, 10, 0, 0)  # noqa: DTZ001
NOW = datetime(2026, 3, 1, 10, 0, 0)  # noqa: DTZ001

# Convention "IDLE, RUNNING, OFF, MAINTENANCE = members of MachineEventTypeEnum"
IDLE = MachineEventTypeEnum.IDLE
RUNNING = MachineEventTypeEnum.RUNNING
OFF = MachineEventTypeEnum.OFF
MAINTENANCE = MachineEventTypeEnum.MAINTENANCE


# Convention "D(n) = date.today() + timedelta(days=n), read in the test"
def D(n):
    return date.today() + timedelta(days=n)  # noqa: DTZ011


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


# U1 = created_by of every Given row; U2 = the acting user of the calls
@pytest.fixture
def u1(db, w2):
    return make_profile(db)


@pytest.fixture
def u2(db, u1):
    return make_profile(db)


def _factory(db, ws, name, abbreviation, is_active=True, is_deleted=False):
    return _add(db, Factory(
        workspace_id=ws.id, name=name, abbreviation=abbreviation, is_active=is_active, is_deleted=is_deleted,
    ))


@pytest.fixture
def f1(db, w1, u2):
    return _factory(db, w1, "Main Plant", "MP")


@pytest.fixture
def f2(db, w1, f1):
    return _factory(db, w1, "North Yard", "NY")


@pytest.fixture
def f9(db, w2, f2):
    return _factory(db, w2, "Far Depot", "FR")


# Convention: FD has is_deleted True, is_active stays True
@pytest.fixture
def fd(db, w1, f9):
    return _factory(db, w1, "Closed Mill", "CM", is_deleted=True)


@pytest.fixture
def fi(db, w1, fd):
    return _factory(db, w1, "Idle Plant", "IP", is_active=False)


def _section(db, factory, name, is_deleted=False):
    return _add(db, FactorySection(
        workspace_id=factory.workspace_id, factory_id=factory.id, name=name, is_active=True, is_deleted=is_deleted,
    ))


@pytest.fixture
def s1(db, f1, fi):
    return _section(db, f1, "Cutting")


@pytest.fixture
def s2(db, f1, s1):
    return _section(db, f1, "Paint")


@pytest.fixture
def s3(db, f2, s2):
    return _section(db, f2, "Welding")


@pytest.fixture
def sx(db, f1, s3):
    return _section(db, f1, "Old Line", is_deleted=True)


@pytest.fixture
def s9(db, f9, sx):
    return _section(db, f9, "Packing")


@pytest.fixture
def wt1(db, w1, s9):
    return _add(db, WorkOrderType(workspace_id=w1.id, name="Repair"))


@pytest.fixture
def wt9(db, w2, wt1):
    return _add(db, WorkOrderType(workspace_id=w2.id, name="Far Repair"))


@pytest.fixture
def i1(db, w1, u1, wt9):
    return _add(db, Item(workspace_id=w1.id, name="Bolt M8", name_normalized="bolt m8", unit="pcs", created_by=u1.id))


@pytest.fixture
def i2(db, w1, u1, i1):
    return _add(db, Item(workspace_id=w1.id, name="Washer Ten", name_normalized="washer ten", unit="pcs", created_by=u1.id))


@pytest.fixture
def std(db, w1, i2):
    return _add(db, Status(workspace_id=w1.id, name="Draft", comment="stage"))


@pytest.fixture
def stc(db, w1, std):
    return _add(db, Status(workspace_id=w1.id, name="Complete", comment="stage"))


# Conventions "These exist in every test" and
# Externals "app.dao.machine.utcnow is patched to NOW in every test"
@pytest.fixture(autouse=True)
def standing_rows(monkeypatch, stc):
    monkeypatch.setattr("app.dao.machine.utcnow", lambda: NOW)


# --------------------------------------------------------------------------- #
# Conventions -> "Parents of W2" (only where a Given line names them)
# --------------------------------------------------------------------------- #

@pytest.fixture
def mk_i9(db, w2, u1):
    def _mk():
        return _add(db, Item(workspace_id=w2.id, name="Far Spring", name_normalized="far spring", unit="pcs", created_by=u1.id))
    return _mk


# Convention "IX (W1)": an inactive item of W1
@pytest.fixture
def mk_ix(db, w1, u1):
    def _mk():
        return _add(db, Item(
            workspace_id=w1.id, name="Old Rivet", name_normalized="old rivet", unit="pcs", is_active=False, created_by=u1.id,
        ))
    return _mk


@pytest.fixture
def mk_st9(db, w2):
    def _mk():
        return _add(db, Status(workspace_id=w2.id, name="Draft", comment="stage"))
    return _mk


@pytest.fixture
def mk_stc9(db, w2):
    def _mk():
        return _add(db, Status(workspace_id=w2.id, name="Complete", comment="stage"))
    return _mk


# --------------------------------------------------------------------------- #
# Conventions -> "Given rows" (each builder inserts ONE row and flushes, so ids
# rise in the order the Given lines are written)
# --------------------------------------------------------------------------- #

@pytest.fixture
def mk_machine(db, w1, w2, u1, f1, f2, f9, fd, fi):
    """mk_machine("M1", **but) builds a Machine recipe; mk_machine(name=..., **but) a plain "machine"."""
    recipes = {
        "M1": {"name": "Lathe"},
        "M2": {"name": "Press"},
        "M3": {"name": "Drill", "factory_id": f2.id},
        "MX": {"name": "Old Saw", "is_deleted": True, "is_active": False, "deleted_at": T0, "deleted_by": u1.id},
        "MF": {"name": "Kiln", "factory_id": fd.id},
        "MI": {"name": "Mixer", "factory_id": fi.id},
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
            "model_number": None, "manufacturer": None, "note": None,
            "created_by": u1.id, "updated_by": None, "updated_at": None,
            "is_active": True, "is_deleted": False,
        }
        if recipe is not None:
            fields.update(recipes[recipe])
        fields.update(but)
        return _add(db, Machine(**fields))
    return _mk


@pytest.fixture
def bulk(db, w1, u1, f1):
    """bulk(n, p, **but): n live machines of F1 in one bulk insert; returns their names."""
    def _bulk(n, p, **but):
        bulk_names = [f"{p}{i:05d}" for i in range(n)]
        fields = {
            "workspace_id": w1.id, "factory_id": f1.id, "is_active": True,
            "is_deleted": False, "is_running": False, "created_by": u1.id,
        }
        fields.update(but)
        db.execute(insert(Machine), [{**fields, "name": name} for name in bulk_names])
        return bulk_names
    return _bulk


def machine_named(db, name):
    """The machine with that name, for Given lines that say "the machine named ..."."""
    return db.execute(select(Machine).where(Machine.name == name)).scalar_one()


# Convention "link of M to S"
@pytest.fixture
def mk_link(db, u1):
    def _mk(machine, section):
        row = _add(db, MachineSectionAssignment(
            workspace_id=machine.workspace_id, machine_id=machine.id, factory_section_id=section.id, created_by=u1.id,
        ))
        db.expire_all()
        return row
    return _mk


# Convention "status row of M at T, "X""; a card's "but" replaces any column
@pytest.fixture
def mk_status_row(db, u1):
    def _mk(machine, at, status=None, **but):
        fields = {
            "workspace_id": machine.workspace_id, "machine_id": machine.id, "event_type": "status_updated",
            "description": "seed", "performed_by": u1.id, "created_at": at, "metadata_json": {"status": status},
        }
        fields.update(but)
        return _add(db, MachineActivityEvent(**fields))
    return _mk


# Convention "order of M": `given_name` is the row's Given name (O1 -> "WO-O1")
@pytest.fixture
def mk_order(db, w1, wt1, f1):
    def _mk(machine, given_name, **but):
        fields = {
            "workspace_id": w1.id, "work_order_number": f"WO-{given_name}", "work_order_type_id": wt1.id,
            "title": "Service", "factory_id": f1.id, "machine_id": machine.id, "planned_date": None,
            "is_deleted": False, "updated_by": None, "updated_at": None,
        }
        fields.update(but)
        return _add(db, WorkOrder(**fields))
    return _mk


# Convention "line of O"
@pytest.fixture
def mk_line(db, w1, i1):
    def _mk(order, **but):
        fields = {
            "workspace_id": w1.id, "work_order_id": order.id, "item_id": i1.id, "quantity": 2,
            "uses_inventory": True, "consumed_at": None, "is_deleted": False,
        }
        fields.update(but)
        return _add(db, WorkOrderItem(**fields))
    return _mk


# Convention "approver of O, U"
@pytest.fixture
def mk_approver(db, w1):
    def _mk(order, user, **but):
        return _add(db, WorkOrderApprover(workspace_id=w1.id, work_order_id=order.id, user_id=user.id, **but))
    return _mk


# Convention "assignee of O, U"
@pytest.fixture
def mk_assignee(db, w1):
    def _mk(order, user):
        return _add(db, WorkOrderAssignee(workspace_id=w1.id, work_order_id=order.id, user_id=user.id))
    return _mk


# Convention "stock of M, item I"
@pytest.fixture
def mk_stock(db):
    def _mk(machine, item, **but):
        fields = {
            "workspace_id": machine.workspace_id, "machine_id": machine.id, "item_id": item.id,
            "req_qty": None, "defective_qty": None,
        }
        fields.update(but)
        return _add(db, MachineItem(**fields))
    return _mk


# Convention "purchase order": `given_name` is the row's Given name (PO1 -> "PO-PO1")
@pytest.fixture
def mk_po(db, w1, u1):
    def _mk(given_name, **but):
        fields = {
            "workspace_id": w1.id, "po_number": f"PO-{given_name}", "destination_type": "machine",
            "created_by": u1.id, "voided": False,
        }
        fields.update(but)
        return _add(db, PurchaseOrder(**fields))
    return _mk


# Convention "transfer order": `given_name` is the row's Given name (TO1 -> "TR-TO1")
@pytest.fixture
def mk_to(db, w1, u1, f1, f2, std):
    def _mk(given_name, **but):
        fields = {
            "workspace_id": w1.id, "transfer_number": f"TR-{given_name}",
            "source_location_type": "storage", "source_location_id": f1.id,
            "destination_location_type": "storage", "destination_location_id": f2.id,
            "current_status_id": std.id, "created_by": u1.id, "completed_at": None,
        }
        fields.update(but)
        return _add(db, TransferOrder(**fields))
    return _mk


# Convention "stock movement row of I1 in F1"
@pytest.fixture
def mk_stock_movement(db, w1, f1, i1):
    def _mk():
        return _add(db, InventoryLedger(
            workspace_id=w1.id, inventory_type=InventoryTypeEnum.STORAGE, factory_id=f1.id, item_id=i1.id,
            transaction_type="manual_add", quantity=2, qty_before=0, qty_after=2,
        ))
    return _mk


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (plain functions; no expected values inside)
# --------------------------------------------------------------------------- #

_TABLES = {
    model.__tablename__: model.__table__
    for model in (
        Machine, MachineSectionAssignment, MachineActivityEvent, WorkOrder, WorkOrderEvent, WorkOrderAssignee,
    )
}
_NOTHING_WRITTEN_TABLES = (
    "machines", "machine_section_assignments", "machine_activity_events", "work_orders", "work_order_events",
)


def _id_of(row):
    """Primary key of a row, without touching its (possibly expired) attributes."""
    return sa_inspect(row).identity[0]


# Convention "re-read X": expire_all, then SELECT X by id
def reread(db, row):
    model, row_id = type(row), _id_of(row)
    db.expire_all()
    return db.execute(select(model).where(model.id == row_id)).scalar_one_or_none()


def _columns_of(db, row):
    table = type(row).__table__
    found = db.execute(select(table).where(table.c.id == _id_of(row))).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "unchanged(X)": snapshot after db.refresh(X), before the call
def snap_before(db, row):
    db.refresh(row)
    return _columns_of(db, row)


# Convention "unchanged(X)": after re-read, every column of X
def snap(db, row):
    db.expire_all()
    return _columns_of(db, row)


# Convention "count:" lines: rows of the named table in all workspaces, with the filter stated
def count_rows(db, table_name, **filters):
    table = _TABLES[table_name]
    query = select(func.count()).select_from(table)
    for column, value in filters.items():
        query = query.where(table.c[column] == value)
    return db.execute(query).scalar_one()


# Convention "nothing written"
def written(db):
    return {name: count_rows(db, name) for name in _NOTHING_WRITTEN_TABLES}


# Convention "links_of(M)"
def links_of(db, machine):
    machine_id = _id_of(machine)
    db.expire_all()
    query = select(MachineSectionAssignment).where(MachineSectionAssignment.machine_id == machine_id)
    return list(db.execute(query.order_by(MachineSectionAssignment.id)).scalars())


# Convention "events_of(M)": a fresh SELECT
def events_of(db, machine):
    machine_id = _id_of(machine)
    db.expire_all()
    query = select(MachineActivityEvent).where(MachineActivityEvent.machine_id == machine_id)
    return list(db.execute(query.order_by(MachineActivityEvent.id)).scalars())


# Convention "wo_events(O)": the same on work_order_events
def wo_events(db, order):
    order_id = _id_of(order)
    db.expire_all()
    query = select(WorkOrderEvent).where(WorkOrderEvent.work_order_id == order_id)
    return list(db.execute(query.order_by(WorkOrderEvent.id)).scalars())


# Convention "names(x)": order is part of the check
def names(rows):
    return [row.name for row in rows]


# Convention "ids(x)": sorted, used where today's order is undefined
def ids(rows):
    return sorted(row.id for row in rows)


# Convention "rolled back": a spy that wraps db.commit (still callable, records calls)
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


# --------------------------------------------------------------------------- #
# create_machine
# --------------------------------------------------------------------------- #

# [claude] MCM-C-01
def test_mcm_c_01__create_stores_the_machine_with_the_values_sent_in_the_caller_s(db, w1, u2, f1):
    """MCM-C-01 — create stores the machine with the values sent, in the caller's workspace, by the caller.
    Rules: `create_machine` R5, Returns"""
    result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=f1.id, model_number="L-200", manufacturer="Haas", note="Bay 3"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert isinstance(result, Machine)
    # Then 2
    assert result.id is not None
    # Then 3
    row = reread(db, result)
    assert row.name == "Lathe"
    assert row.factory_id == f1.id
    # Then 4
    row = reread(db, result)
    assert row.model_number == "L-200"
    assert row.manufacturer == "Haas"
    assert row.note == "Bay 3"
    # Then 5
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.created_by == u2.id
    # Then 6
    assert count_rows(db, "machines") == 1


# [claude] MCM-C-02
def test_mcm_c_02__a_new_machine_is_stopped_live_and_carries_no_update_or_deletion_stamp(db, w1, u2, f1):
    """MCM-C-02 — a new machine is stopped, live and carries no update or deletion stamp.
    Rules: `create_machine` R5"""
    result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=f1.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.is_running is False
    assert row.is_active is True
    assert row.is_deleted is False
    # Then 3
    row = reread(db, result)
    assert row.created_at is not None
    # Then 4
    row = reread(db, result)
    assert row.updated_at is None
    assert row.updated_by is None
    # Then 5
    row = reread(db, result)
    assert row.deleted_at is None
    assert row.deleted_by is None


# [claude] MCM-C-03
def test_mcm_c_03__optional_fields_not_sent_are_stored_as_none(db, w1, u2, f1):
    """MCM-C-03 — optional fields not sent are stored as None.
    Rules: `create_machine` R5"""
    result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=f1.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.model_number is None
    assert row.manufacturer is None
    assert row.note is None


# [claude] MCM-C-04
def test_mcm_c_04__an_is_running_in_the_request_is_ignored(db, w1, u2, f1):
    """MCM-C-04 — an is_running in the request is ignored.
    Rules: `create_machine` R5"""
    result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=f1.id, is_running=True), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.is_running is False


# [claude] MCM-C-05
def test_mcm_c_05__the_note_is_stored_as_typed_padding_kept(db, w1, u2, f1):
    """MCM-C-05 — the note is stored as typed, padding kept.
    Rules: `create_machine` R7"""
    result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=f1.id, note="  awaiting belt "), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.note == "  awaiting belt "


# [claude] MCM-C-06
def test_mcm_c_06__an_empty_note_is_stored_as_an_empty_string(db, w1, u2, f1):
    """MCM-C-06 — an empty note is stored as an empty string.
    Rules: `create_machine` R7"""
    result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=f1.id, note=""), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.note == ""


# [claude] MCM-C-07
def test_mcm_c_07__inner_spaces_of_model_number_and_manufacturer_are_kept(db, w1, u2, f1):
    """MCM-C-07 — inner spaces of model number and manufacturer are kept.
    Rules: `create_machine` R7"""
    result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=f1.id, model_number="L  200", manufacturer="Haas  Works"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.model_number == "L  200"
    assert row.manufacturer == "Haas  Works"


# [claude] MCM-C-08
@pytest.mark.xfail(strict=True, reason="BUG-967: Model number and manufacturer stored untrimmed; blank counts as a value")
def test_mcm_c_08__a_padded_model_number_is_stored_trimmed(db, w1, u2, f1):
    """MCM-C-08 — a padded model number is stored trimmed.
    Rules: `create_machine` R7 [BUG-967]"""
    result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=f1.id, model_number=" L-200 "), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.model_number == "L-200"


# [claude] MCM-C-09
@pytest.mark.xfail(strict=True, reason="BUG-967: Model number and manufacturer stored untrimmed; blank counts as a value")
def test_mcm_c_09__a_padded_manufacturer_is_stored_trimmed(db, w1, u2, f1):
    """MCM-C-09 — a padded manufacturer is stored trimmed.
    Rules: `create_machine` R7 [BUG-967]"""
    result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=f1.id, manufacturer=" Haas "), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.manufacturer == "Haas"


# [claude] MCM-C-10
@pytest.mark.xfail(strict=True, reason="BUG-967: Model number and manufacturer stored untrimmed; blank counts as a value")
def test_mcm_c_10__an_empty_model_number_is_stored_as_none(db, w1, u2, f1):
    """MCM-C-10 — an empty model number is stored as None.
    Rules: `create_machine` R7 [BUG-967]"""
    result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=f1.id, model_number=""), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.model_number is None


# [claude] MCM-C-11
@pytest.mark.xfail(strict=True, reason="BUG-967: Model number and manufacturer stored untrimmed; blank counts as a value")
def test_mcm_c_11__a_whitespace_only_model_number_is_stored_as_none(db, w1, u2, f1):
    """MCM-C-11 — a whitespace-only model number is stored as None.
    Rules: `create_machine` R7 [BUG-967]"""
    result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=f1.id, model_number="   "), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.model_number is None


# [claude] MCM-C-12
@pytest.mark.xfail(strict=True, reason="BUG-967: Model number and manufacturer stored untrimmed; blank counts as a value")
def test_mcm_c_12__an_empty_manufacturer_is_stored_as_none(db, w1, u2, f1):
    """MCM-C-12 — an empty manufacturer is stored as None.
    Rules: `create_machine` R7 [BUG-967]"""
    result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=f1.id, manufacturer=""), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.manufacturer is None


# [claude] MCM-C-13
@pytest.mark.xfail(strict=True, reason="BUG-967: Model number and manufacturer stored untrimmed; blank counts as a value")
def test_mcm_c_13__a_whitespace_only_manufacturer_is_stored_as_none(db, w1, u2, f1):
    """MCM-C-13 — a whitespace-only manufacturer is stored as None.
    Rules: `create_machine` R7 [BUG-967]"""
    result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=f1.id, manufacturer="\t"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.manufacturer is None


# [claude] MCM-C-14
@pytest.mark.xfail(strict=True, reason="BUG-950: Blank / whitespace-only machine names accepted; names stored untrimmed")
def test_mcm_c_14__the_name_is_stored_trimmed_inner_spaces_and_case_kept(db, w1, u2, f1):
    """MCM-C-14 — the name is stored trimmed, inner spaces and case kept.
    Rules: `create_machine` R6 [BUG-950]"""
    result = M.create_machine(db, machine_data=MachineCreate(name="  Big  PRESS ", factory_id=f1.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.name == "Big  PRESS"


# [claude] MCM-C-15
def test_mcm_c_15__inner_whitespace_and_case_of_the_name_are_kept(db, w1, u2, f1):
    """MCM-C-15 — inner whitespace and case of the name are kept.
    Rules: `create_machine` R6"""
    result = M.create_machine(db, machine_data=MachineCreate(name="big  PRESS", factory_id=f1.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.name == "big  PRESS"


# [claude] MCM-C-16
@pytest.mark.xfail(strict=True, reason="BUG-950: Blank / whitespace-only machine names accepted; names stored untrimmed")
def test_mcm_c_16__an_empty_name_is_rejected_by_machinecreate(db, f1):
    """MCM-C-16 — an empty name is rejected by MachineCreate.
    Rules: `create_machine` R6 [BUG-950], Errors row 5"""
    # Then 1
    with pytest.raises(ValidationError):
        MachineCreate(name="", factory_id=f1.id)
    # Then 2
    assert count_rows(db, "machines") == 0


# [claude] MCM-C-17
@pytest.mark.xfail(strict=True, reason="BUG-950: Blank / whitespace-only machine names accepted; names stored untrimmed")
def test_mcm_c_17__a_name_of_three_spaces_is_rejected_by_machinecreate(db, f1):
    """MCM-C-17 — a name of three spaces is rejected by MachineCreate.
    Rules: `create_machine` R6 [BUG-950], Errors row 5"""
    # Then 1
    with pytest.raises(ValidationError):
        MachineCreate(name="   ", factory_id=f1.id)
    # Then 2
    assert count_rows(db, "machines") == 0


# [claude] MCM-C-18
@pytest.mark.xfail(strict=True, reason="BUG-950: Blank / whitespace-only machine names accepted; names stored untrimmed")
def test_mcm_c_18__a_name_of_one_tab_is_rejected_by_machinecreate(db, f1):
    """MCM-C-18 — a name of one tab is rejected by MachineCreate.
    Rules: `create_machine` R6 [BUG-950], Errors row 5"""
    # Then 1
    with pytest.raises(ValidationError):
        MachineCreate(name="\t", factory_id=f1.id)
    # Then 2
    assert count_rows(db, "machines") == 0


# [claude] MCM-C-19
def test_mcm_c_19__a_one_character_name_is_accepted_by_machinecreate(db, f1):
    """MCM-C-19 — a one-character name is accepted by MachineCreate.
    Rules: `create_machine` R6"""
    result = MachineCreate(name="a", factory_id=f1.id)

    # Then 1
    assert result.name == "a"


# [claude] MCM-C-20
@pytest.mark.xfail(strict=True, reason="BUG-972: Over-long model number or manufacturer crashes")
def test_mcm_c_20__a_model_number_of_201_characters_is_rejected_by_machinecreate(db, f1):
    """MCM-C-20 — a model_number of 201 characters is rejected by MachineCreate.
    Rules: `create_machine` R8 [BUG-972], Errors row 5"""
    # Then 1
    with pytest.raises(ValidationError):
        MachineCreate(name="Lathe", factory_id=f1.id, model_number="x" * 201)
    # Then 2
    assert count_rows(db, "machines") == 0


# [claude] MCM-C-21
def test_mcm_c_21__a_model_number_of_exactly_200_characters_is_accepted_and_stored(db, w1, u2, f1):
    """MCM-C-21 — a model_number of exactly 200 characters is accepted and stored.
    Rules: `create_machine` R8"""
    result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=f1.id, model_number="x" * 200), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.model_number == "x" * 200


# [claude] MCM-C-22
@pytest.mark.xfail(strict=True, reason="BUG-972: Over-long model number or manufacturer crashes")
def test_mcm_c_22__a_manufacturer_of_201_characters_is_rejected_by_machinecreate(db, f1):
    """MCM-C-22 — a manufacturer of 201 characters is rejected by MachineCreate.
    Rules: `create_machine` R8 [BUG-972], Errors row 5"""
    # Then 1
    with pytest.raises(ValidationError):
        MachineCreate(name="Lathe", factory_id=f1.id, manufacturer="x" * 201)
    # Then 2
    assert count_rows(db, "machines") == 0


# [claude] MCM-C-23
def test_mcm_c_23__a_manufacturer_of_exactly_200_characters_is_accepted_and_stored(db, w1, u2, f1):
    """MCM-C-23 — a manufacturer of exactly 200 characters is accepted and stored.
    Rules: `create_machine` R8"""
    result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=f1.id, manufacturer="x" * 200), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.manufacturer == "x" * 200


# [claude] MCM-C-24
def test_mcm_c_24__a_factory_id_that_does_not_exist_is_refused(db, w1, u2):
    """MCM-C-24 — a factory id that does not exist is refused.
    Rules: `create_machine` R1, Errors row 1"""
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=MISSING), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory with ID 999999999 not found"
    # Then 4
    assert written(db) == before


# [claude] MCM-C-25
def test_mcm_c_25__factory_id_0_is_refused_as_not_found(db, w1, u2):
    """MCM-C-25 — factory id 0 is refused as not found.
    Rules: `create_machine` R1, Errors row 1"""
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=0), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory with ID 0 not found"
    # Then 4
    assert written(db) == before


# [claude] MCM-C-26
def test_mcm_c_26__a_factory_of_another_workspace_is_refused_as_not_found(db, w1, u2, f9):
    """MCM-C-26 — a factory of another workspace is refused as not found.
    Rules: `create_machine` R1, Errors row 1"""
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=f9.id), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory with ID {f9.id} not found"
    # Then 4
    assert written(db) == before


# [claude] MCM-C-27
def test_mcm_c_27__an_unknown_workspace_id_ends_at_the_factory_check(db, u2, f1):
    """MCM-C-27 — an unknown workspace id ends at the factory check.
    Rules: `create_machine` R1, Errors row 1"""
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=f1.id), workspace_id=MISSING, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory with ID {f1.id} not found"
    # Then 4
    assert written(db) == before


# [claude] MCM-C-28
@pytest.mark.xfail(strict=True, reason="BUG-963: A machine can be created in, or moved to, a soft-deleted factory")
def test_mcm_c_28__a_soft_deleted_factory_is_refused(db, w1, u2, fd):
    """MCM-C-28 — a soft-deleted factory is refused.
    Rules: `create_machine` R2 [BUG-963], Errors row 2"""
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=fd.id), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot create machine for deleted factory"
    # Then 4
    assert written(db) == before


# [claude] MCM-C-29
@pytest.mark.xfail(strict=True, reason="BUG-963: A machine can be created in, or moved to, a soft-deleted factory")
def test_mcm_c_29__the_deleted_factory_refusal_comes_before_the_name_check(db, w1, u2, fd, mk_machine):
    """MCM-C-29 — the deleted-factory refusal comes before the name check.
    Rules: `create_machine` R2 [BUG-963], Errors row 2"""
    mf = mk_machine("MF")
    before_mf = snap_before(db, mf)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine(db, machine_data=MachineCreate(name="Kiln", factory_id=fd.id), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot create machine for deleted factory"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, mf) == before_mf


# [claude] MCM-C-30
def test_mcm_c_30__a_live_but_inactive_factory_is_accepted(db, w1, u2, fi):
    """MCM-C-30 — a live but inactive factory is accepted.
    Rules: `create_machine` R2"""
    result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=fi.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.factory_id == fi.id
    # Then 3
    assert count_rows(db, "machines") == 1


# [claude] MCM-C-31
def test_mcm_c_31__a_live_machine_of_the_factory_with_the_same_name_is_refused(db, w1, u2, f1, mk_machine):
    """MCM-C-31 — a live machine of the factory with the same name is refused.
    Rules: `create_machine` R3, Errors row 3"""
    m1 = mk_machine("M1")
    before_m1 = snap_before(db, m1)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=f1.id), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Machine with name 'Lathe' already exists in this factory"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, m1) == before_m1


# [claude] MCM-C-32
@pytest.mark.xfail(strict=True, reason="BUG-952: Machine duplicate-name check is case- and whitespace-sensitive")
def test_mcm_c_32__a_name_that_differs_only_in_case_is_refused_with_the_name_as_submitted(db, w1, u2, f1, mk_machine):
    """MCM-C-32 — a name that differs only in case is refused, with the name as submitted.
    Rules: `create_machine` R3 [BUG-952], Errors row 3; `_check_name_exists_in_factory` R4"""
    mk_machine("M1")
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine(db, machine_data=MachineCreate(name="LATHE", factory_id=f1.id), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Machine with name 'LATHE' already exists in this factory"
    # Then 4
    assert written(db) == before


# [claude] MCM-C-33
@pytest.mark.xfail(strict=True, reason="BUG-952: Machine duplicate-name check is case- and whitespace-sensitive")
def test_mcm_c_33__a_name_that_differs_only_in_outer_spaces_is_refused(db, w1, u2, f1, mk_machine):
    """MCM-C-33 — a name that differs only in outer spaces is refused.
    Rules: `create_machine` R3 [BUG-952], Errors row 3; `_check_name_exists_in_factory` R4"""
    mk_machine("M1")
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine(db, machine_data=MachineCreate(name=" Lathe ", factory_id=f1.id), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Machine with name 'Lathe' already exists in this factory"
    # Then 4
    assert written(db) == before


# [claude] MCM-C-34
def test_mcm_c_34__the_same_name_in_another_factory_does_not_block(db, w1, u2, f2, mk_machine):
    """MCM-C-34 — the same name in another factory does not block.
    Rules: `create_machine` R4"""
    m1 = mk_machine("M1")
    before_m1 = snap_before(db, m1)
    result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.factory_id == f2.id
    # Then 3
    assert snap(db, m1) == before_m1


# [claude] MCM-C-35
def test_mcm_c_35__the_same_name_in_another_workspace_does_not_block(db, w1, u2, f1, mk_machine):
    """MCM-C-35 — the same name in another workspace does not block.
    Rules: `create_machine` R4"""
    m9 = mk_machine("M9", name="Lathe")
    before_m9 = snap_before(db, m9)
    result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=f1.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    # Then 3
    assert snap(db, m9) == before_m9


# [claude] MCM-C-36
def test_mcm_c_36__the_name_of_a_soft_deleted_machine_can_be_used_again(db, w1, u2, f1, mk_machine):
    """MCM-C-36 — the name of a soft-deleted machine can be used again.
    Rules: `create_machine` R4"""
    mx = mk_machine("MX")
    before_mx = snap_before(db, mx)
    result = M.create_machine(db, machine_data=MachineCreate(name="Old Saw", factory_id=f1.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.is_deleted is False
    # Then 3
    assert snap(db, mx) == before_mx


# [claude] MCM-C-37
@pytest.mark.xfail(strict=True, reason="BUG-953: Machine name uniqueness per factory not enforced by the database")
def test_mcm_c_37__the_database_refuses_a_second_live_machine_with_the_same_name_in_a(db, w1, f1, mk_machine):
    """MCM-C-37 — the database refuses a second live machine with the same name in a factory.
    Rules: `create_machine` R9 [BUG-953]"""
    mk_machine("M1")

    # Then 1
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(Machine(workspace_id=w1.id, factory_id=f1.id, name="Lathe"))
            db.flush()
    # Then 2
    assert count_rows(db, "machines", name="Lathe") == 1


# [claude] MCM-C-38
@pytest.mark.xfail(strict=True, reason="BUG-953: Machine name uniqueness per factory not enforced by the database")
def test_mcm_c_38__the_database_refuses_a_second_live_machine_whose_name_differs_only_in(db, w1, f1, mk_machine):
    """MCM-C-38 — the database refuses a second live machine whose name differs only in case and outer spaces.
    Rules: `create_machine` R9 [BUG-953]"""
    mk_machine("M1")

    # Then 1
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(Machine(workspace_id=w1.id, factory_id=f1.id, name=" LATHE "))
            db.flush()
    # Then 2
    assert count_rows(db, "machines") == 1


# [claude] MCM-C-39
def test_mcm_c_39__the_database_accepts_a_soft_deleted_machine_with_the_name_of_a_live(db, w1, f1, mk_machine):
    """MCM-C-39 — the database accepts a soft-deleted machine with the name of a live one.
    Rules: `create_machine` R9"""
    m1 = mk_machine("M1")
    before_m1 = snap_before(db, m1)
    db.add(Machine(workspace_id=w1.id, factory_id=f1.id, name="Lathe", is_deleted=True, is_active=False))
    db.flush()

    # Then 1
    assert count_rows(db, "machines") == 2
    # Then 2
    assert snap(db, m1) == before_m1


# [claude] MCM-C-40
def test_mcm_c_40__the_database_accepts_the_same_name_in_another_factory(db, w1, f2, mk_machine):
    """MCM-C-40 — the database accepts the same name in another factory.
    Rules: `create_machine` R9"""
    m1 = mk_machine("M1")
    before_m1 = snap_before(db, m1)
    db.add(Machine(workspace_id=w1.id, factory_id=f2.id, name="Lathe"))
    db.flush()

    # Then 1
    assert count_rows(db, "machines") == 2
    # Then 2
    assert snap(db, m1) == before_m1


# [claude] MCM-C-41
@pytest.mark.xfail(strict=True, reason="BUG-953: Machine name uniqueness per factory not enforced by the database")
def test_mcm_c_41__a_duplicate_that_passed_the_python_check_gets_the_409_not_a_database(db, w1, u2, f1, mk_machine, monkeypatch):
    """MCM-C-41 — a duplicate that passed the Python check gets the 409, not a database error.
    Rules: `create_machine` R9 [BUG-953], Errors row 3"""
    mk_machine("M1")
    monkeypatch.setattr(MachineManager, "_check_name_exists_in_factory", lambda *args, **kwargs: False)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with db.begin_nested():
            M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=f1.id), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Machine with name 'Lathe' already exists in this factory"
    # Then 4
    assert count_rows(db, "machines", name="Lathe") == 1
    # Then 5
    assert count_rows(db, "machine_activity_events") == 0


# [claude] MCM-C-42
def test_mcm_c_42__a_section_sent_gives_the_machine_a_link_and_the_returned_machine(db, w1, u2, f1, s1):
    """MCM-C-42 — a section sent gives the machine a link and the returned machine reads it.
    Rules: `create_machine` R10, Returns"""
    result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=f1.id, factory_section_id=s1.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert result.factory_section_id == s1.id
    # Then 3
    assert result.factory_section_name == "Cutting"
    # Then 4
    assert count_rows(db, "machine_section_assignments") == 1
    # Then 5
    [row] = links_of(db, result)
    assert row.factory_section_id == s1.id
    assert row.workspace_id == w1.id
    assert row.created_by == u2.id


# [claude] MCM-C-43
def test_mcm_c_43__without_a_section_no_link_exists_and_both_section_values_read_none(db, w1, u2, f1):
    """MCM-C-43 — without a section no link exists and both section values read None.
    Rules: `create_machine` R10"""
    result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=f1.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert result.factory_section_id is None
    # Then 3
    assert result.factory_section_name is None
    # Then 4
    assert count_rows(db, "machine_section_assignments") == 0


# [claude] MCM-C-44
def test_mcm_c_44__a_section_id_that_does_not_exist_refuses_the_create_the_machine_stays(db, w1, u2, f1):
    """MCM-C-44 — a section id that does not exist refuses the create; the machine stays flushed until the rollback.
    Rules: `create_machine` R11, R12, Errors row 4"""
    sp = db.begin_nested()

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=f1.id, factory_section_id=MISSING), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory section with ID 999999999 not found"
    # Then 4
    assert count_rows(db, "machines") == 1
    # Then 5
    assert count_rows(db, "machine_section_assignments") == 0
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    sp.rollback()
    assert count_rows(db, "machines") == 0


# [claude] MCM-C-45
def test_mcm_c_45__section_id_0_refuses_the_create_the_machine_stays_flushed_until_the(db, w1, u2, f1):
    """MCM-C-45 — section id 0 refuses the create; the machine stays flushed until the rollback.
    Rules: `create_machine` R11, R12, Errors row 4"""
    sp = db.begin_nested()

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=f1.id, factory_section_id=0), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory section with ID 0 not found"
    # Then 4
    assert count_rows(db, "machines") == 1
    # Then 5
    assert count_rows(db, "machine_section_assignments") == 0
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    sp.rollback()
    assert count_rows(db, "machines") == 0


# [claude] MCM-C-46
def test_mcm_c_46__a_soft_deleted_section_refuses_the_create_the_machine_stays_flushed(db, w1, u2, f1, sx):
    """MCM-C-46 — a soft-deleted section refuses the create; the machine stays flushed until the rollback.
    Rules: `create_machine` R11, R12, Errors row 4"""
    sp = db.begin_nested()

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=f1.id, factory_section_id=sx.id), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot assign a machine to a deleted factory section"
    # Then 4
    assert count_rows(db, "machines") == 1
    # Then 5
    assert count_rows(db, "machine_section_assignments") == 0
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    sp.rollback()
    assert count_rows(db, "machines") == 0


# [claude] MCM-C-47
def test_mcm_c_47__a_section_of_another_factory_refuses_the_create_the_machine_stays(db, w1, u2, f1, s3):
    """MCM-C-47 — a section of another factory refuses the create; the machine stays flushed until the rollback.
    Rules: `create_machine` R11, R12, Errors row 4"""
    sp = db.begin_nested()

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=f1.id, factory_section_id=s3.id), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Factory section does not belong to this machine's factory"
    # Then 4
    assert count_rows(db, "machines") == 1
    # Then 5
    assert count_rows(db, "machine_section_assignments") == 0
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    sp.rollback()
    assert count_rows(db, "machines") == 0


# [claude] MCM-C-48
def test_mcm_c_48__a_section_of_another_workspace_refuses_the_create_the_machine_stays(db, w1, u2, f1, s9):
    """MCM-C-48 — a section of another workspace refuses the create; the machine stays flushed until the rollback.
    Rules: `create_machine` R11, R12, Errors row 4"""
    sp = db.begin_nested()

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=f1.id, factory_section_id=s9.id), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory section with ID {s9.id} not found"
    # Then 4
    assert count_rows(db, "machines") == 1
    # Then 5
    assert count_rows(db, "machine_section_assignments") == 0
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    sp.rollback()
    assert count_rows(db, "machines") == 0


# [claude] MCM-C-49
def test_mcm_c_49__one_created_event_is_written(db, w1, u2, f1):
    """MCM-C-49 — one created event is written.
    Rules: `create_machine` R13"""
    result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=f1.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    rows = events_of(db, result)
    assert len(rows) == 1
    # Then 3
    assert rows[0].event_type == "created"
    assert rows[0].description == "Machine created: Lathe"
    # Then 4
    assert rows[0].performed_by == u2.id
    assert rows[0].workspace_id == w1.id
    # Then 5
    assert rows[0].metadata_json is None
    # Then 6
    assert rows[0].created_at is not None


# [claude] MCM-C-50
def test_mcm_c_50__an_unknown_user_fails_on_flush_and_nothing_is_saved(db, w1, f1):
    """MCM-C-50 — an unknown user fails on flush and nothing is saved.
    Rules: `create_machine` R14, Errors row 6"""
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=f1.id), workspace_id=w1.id, user_id=MISSING)
    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert "machines_created_by_fkey" in str(exc.value.orig)
    # Then 4
    assert written(db) == before


# [claude] MCM-C-51
def test_mcm_c_51__the_create_is_flushed_but_not_committed_a_rollback_removes_machine(db, w1, u2, f1, s1, monkeypatch):
    """MCM-C-51 — the create is flushed but not committed: a rollback removes machine, link and event.
    Rules: `create_machine` R15, Returns"""
    sp = db.begin_nested()
    spy = commit_spy(db, monkeypatch)
    result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=f1.id, factory_section_id=s1.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert count_rows(db, "machines") == 1
    # Then 3
    assert count_rows(db, "machine_section_assignments") == 1
    # Then 4
    assert count_rows(db, "machine_activity_events") == 1
    # Then 5
    sp.rollback()
    assert count_rows(db, "machines") == 0
    # Then 6
    assert count_rows(db, "machine_section_assignments") == 0
    # Then 7
    assert count_rows(db, "machine_activity_events") == 0
    # Then 8
    spy.assert_not_called()



# --------------------------------------------------------------------------- #
# update_machine
# --------------------------------------------------------------------------- #

# [claude] MCM-U-01
def test_mcm_u_01__the_fields_sent_are_stored_the_editor_recorded_and_the_same_instance(db, w1, u2, mk_machine):
    """MCM-U-01 — the fields sent are stored, the editor recorded and the same instance returned.
    Rules: `update_machine` R4, R23, R24, Returns"""
    m1 = mk_machine("M1")
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(name="Big Lathe", model_number="L-300", manufacturer="Haas", note="Bay 4"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.name == "Big Lathe"
    # Then 3
    row = reread(db, m1)
    assert row.model_number == "L-300"
    assert row.manufacturer == "Haas"
    assert row.note == "Bay 4"
    # Then 4
    row = reread(db, m1)
    assert row.updated_by == u2.id
    # Then 5
    row = reread(db, m1)
    assert row.updated_at is not None
    # Then 6
    assert count_rows(db, "machines") == 1


# [claude] MCM-U-02
def test_mcm_u_02__fields_not_sent_and_the_columns_nobody_edits_keep_their_values(db, w1, u1, u2, f1, mk_machine):
    """MCM-U-02 — fields not sent and the columns nobody edits keep their values.
    Rules: `update_machine` R4, R22"""
    m1 = mk_machine("M1", model_number="L-200", manufacturer="Haas", is_running=True)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(note="Bay 4"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.note == "Bay 4"
    # Then 3
    row = reread(db, m1)
    assert row.name == "Lathe"
    assert row.model_number == "L-200"
    assert row.manufacturer == "Haas"
    # Then 4
    row = reread(db, m1)
    assert row.workspace_id == w1.id
    assert row.factory_id == f1.id
    assert row.created_by == u1.id
    assert row.created_at is not None
    # Then 5
    row = reread(db, m1)
    assert row.is_running is True
    assert row.is_active is True
    assert row.is_deleted is False
    # Then 6
    row = reread(db, m1)
    assert row.deleted_at is None
    assert row.deleted_by is None


# [claude] MCM-U-03
def test_mcm_u_03__an_is_running_in_the_request_is_ignored(db, w1, u2, mk_machine):
    """MCM-U-03 — an is_running in the request is ignored.
    Rules: `update_machine` R22"""
    m1 = mk_machine("M1")
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(note="Bay 4", is_running=True), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.is_running is False


# [claude] MCM-U-04
def test_mcm_u_04__an_id_that_no_machine_has_is_refused(db, w1, u2, mk_machine):
    """MCM-U-04 — an id that no machine has is refused.
    Rules: `update_machine` R1, Errors row 1"""
    m1 = mk_machine("M1")
    before_m1 = snap_before(db, m1)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine(db, machine_id=MISSING, machine_data=MachineUpdate(name="Big Lathe"), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine with ID 999999999 not found"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, m1) == before_m1


# [claude] MCM-U-05
def test_mcm_u_05__a_machine_of_another_workspace_is_refused_and_not_changed(db, w1, u2, mk_machine):
    """MCM-U-05 — a machine of another workspace is refused and not changed.
    Rules: `update_machine` R1, Errors row 1"""
    m9 = mk_machine("M9")
    before_m9 = snap_before(db, m9)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine(db, machine_id=m9.id, machine_data=MachineUpdate(name="Big Grinder"), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Machine with ID {m9.id} not found"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, m9) == before_m9


# [claude] MCM-U-06
def test_mcm_u_06__a_soft_deleted_machine_is_refused(db, w1, u2, mk_machine):
    """MCM-U-06 — a soft-deleted machine is refused.
    Rules: `update_machine` R2, Errors row 2"""
    mx = mk_machine("MX")
    before_mx = snap_before(db, mx)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine(db, machine_id=mx.id, machine_data=MachineUpdate(note="Bay 4"), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update a deleted machine"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, mx) == before_mx


# [claude] MCM-U-07
def test_mcm_u_07__a_soft_deleted_machine_is_refused_also_with_an_empty_request(db, w1, u2, mk_machine):
    """MCM-U-07 — a soft-deleted machine is refused also with an empty request.
    Rules: `update_machine` R2, Errors row 2"""
    mx = mk_machine("MX")
    before_mx = snap_before(db, mx)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine(db, machine_id=mx.id, machine_data=MachineUpdate(), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update a deleted machine"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, mx) == before_mx


# [claude] MCM-U-08
def test_mcm_u_08__the_deleted_machine_refusal_comes_before_the_factory_check(db, w1, u2, mk_machine):
    """MCM-U-08 — the deleted-machine refusal comes before the factory check.
    Rules: `update_machine` R2, R15, Errors row 2"""
    mx = mk_machine("MX")
    before_mx = snap_before(db, mx)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine(db, machine_id=mx.id, machine_data=MachineUpdate(factory_id=MISSING), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update a deleted machine"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, mx) == before_mx


# [claude] MCM-U-09
def test_mcm_u_09__the_deleted_machine_refusal_comes_before_the_name_check(db, w1, u2, mk_machine):
    """MCM-U-09 — the deleted-machine refusal comes before the name check.
    Rules: `update_machine` R2, R15, Errors row 2"""
    mk_machine("M1")
    mx = mk_machine("MX")
    before_mx = snap_before(db, mx)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine(db, machine_id=mx.id, machine_data=MachineUpdate(name="Lathe"), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update a deleted machine"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, mx) == before_mx


# [claude] MCM-U-10
@pytest.mark.xfail(strict=True, reason="BUG-964: A machine inside a soft-deleted factory can still be edited or moved out")
def test_mcm_u_10__a_rename_of_a_machine_in_a_soft_deleted_factory_is_refused(db, w1, u2, mk_machine):
    """MCM-U-10 — a rename of a machine in a soft-deleted factory is refused.
    Rules: `update_machine` R3 [BUG-964], Errors row 2"""
    mf = mk_machine("MF")
    before_mf = snap_before(db, mf)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine(db, machine_id=mf.id, machine_data=MachineUpdate(name="Big Kiln"), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update a deleted machine"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, mf) == before_mf


# [claude] MCM-U-11
@pytest.mark.xfail(strict=True, reason="BUG-964: A machine inside a soft-deleted factory can still be edited or moved out")
def test_mcm_u_11__an_edit_of_a_machine_in_a_soft_deleted_factory_is_refused(db, w1, u2, mk_machine):
    """MCM-U-11 — an edit of a machine in a soft-deleted factory is refused.
    Rules: `update_machine` R3 [BUG-964], Errors row 2"""
    mf = mk_machine("MF")
    before_mf = snap_before(db, mf)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine(db, machine_id=mf.id, machine_data=MachineUpdate(note="Bay 4"), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update a deleted machine"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, mf) == before_mf


# [claude] MCM-U-12
@pytest.mark.xfail(strict=True, reason="BUG-964: A machine inside a soft-deleted factory can still be edited or moved out")
def test_mcm_u_12__a_move_out_of_a_machine_in_a_soft_deleted_factory_is_refused(db, w1, u2, f2, mk_machine):
    """MCM-U-12 — a move out of a machine in a soft-deleted factory is refused.
    Rules: `update_machine` R3 [BUG-964], Errors row 2"""
    mf = mk_machine("MF")
    before_mf = snap_before(db, mf)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine(db, machine_id=mf.id, machine_data=MachineUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update a deleted machine"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, mf) == before_mf


# [claude] MCM-U-13
@pytest.mark.xfail(strict=True, reason="BUG-964: A machine inside a soft-deleted factory can still be edited or moved out")
def test_mcm_u_13__the_deleted_factory_refusal_comes_before_the_target_factory_check(db, w1, u2, mk_machine):
    """MCM-U-13 — the deleted-factory refusal comes before the target factory check.
    Rules: `update_machine` R3 [BUG-964], R15, Errors row 2"""
    mf = mk_machine("MF")
    before_mf = snap_before(db, mf)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine(db, machine_id=mf.id, machine_data=MachineUpdate(factory_id=MISSING), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update a deleted machine"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, mf) == before_mf


# [claude] MCM-U-14
def test_mcm_u_14__a_machine_in_a_live_but_inactive_factory_can_be_edited(db, w1, u2, mk_machine):
    """MCM-U-14 — a machine in a live but inactive factory can be edited.
    Rules: `update_machine` R3"""
    mi = mk_machine("MI")
    result = M.update_machine(db, machine_id=mi.id, machine_data=MachineUpdate(note="Bay 4"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is mi
    # Then 2
    row = reread(db, mi)
    assert row.note == "Bay 4"


# [claude] MCM-U-15
@pytest.mark.xfail(strict=True, reason="BUG-962: Machine model number, manufacturer and note cannot be cleared")
def test_mcm_u_15__an_explicit_null_clears_model_number(db, w1, u2, mk_machine):
    """MCM-U-15 — an explicit null clears model_number.
    Rules: `update_machine` R5 [BUG-962]"""
    m1 = mk_machine("M1", model_number="L-200")
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(model_number=None), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.model_number is None
    # Then 3
    row = reread(db, m1)
    assert row.updated_by == u2.id
    # Then 4
    assert events_of(db, m1)[0].metadata_json == {"changes": [{"field": "model_number", "label": "Model number", "from_value": "L-200", "to_value": None}]}


# [claude] MCM-U-16
@pytest.mark.xfail(strict=True, reason="BUG-962: Machine model number, manufacturer and note cannot be cleared")
def test_mcm_u_16__an_explicit_null_clears_manufacturer(db, w1, u2, mk_machine):
    """MCM-U-16 — an explicit null clears manufacturer.
    Rules: `update_machine` R5 [BUG-962]"""
    m1 = mk_machine("M1", manufacturer="Haas")
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(manufacturer=None), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.manufacturer is None
    # Then 3
    row = reread(db, m1)
    assert row.updated_by == u2.id
    # Then 4
    assert events_of(db, m1)[0].metadata_json == {"changes": [{"field": "manufacturer", "label": "Manufacturer", "from_value": "Haas", "to_value": None}]}


# [claude] MCM-U-17
@pytest.mark.xfail(strict=True, reason="BUG-962: Machine model number, manufacturer and note cannot be cleared")
def test_mcm_u_17__an_explicit_null_clears_note(db, w1, u2, mk_machine):
    """MCM-U-17 — an explicit null clears note.
    Rules: `update_machine` R5 [BUG-962]"""
    m1 = mk_machine("M1", note="Bay 3")
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(note=None), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.note is None
    # Then 3
    row = reread(db, m1)
    assert row.updated_by == u2.id
    # Then 4
    assert events_of(db, m1)[0].metadata_json == {"changes": [{"field": "note", "label": "Note", "from_value": "Bay 3", "to_value": None}]}


# [claude] MCM-U-18
def test_mcm_u_18__a_sent_null_keeps_meaning_clear_the_section_and_leaves_omitted_fields(db, w1, u2, s1, mk_machine, mk_link):
    """MCM-U-18 — a sent null keeps meaning clear-the-section and leaves omitted fields.
    Rules: `update_machine` R4, R5, R17"""
    m1 = mk_machine("M1", note="Bay 3")
    mk_link(m1, s1)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_section_id=None), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    assert links_of(db, m1) == []
    # Then 3
    row = reread(db, m1)
    assert row.note == "Bay 3"
    # Then 4
    row = reread(db, m1)
    assert row.name == "Lathe"


# [claude] MCM-U-19
@pytest.mark.xfail(strict=True, reason="BUG-962: Machine model number, manufacturer and note cannot be cleared")
def test_mcm_u_19__a_null_name_is_rejected_by_machineupdate(db, mk_machine):
    """MCM-U-19 — a null name is rejected by MachineUpdate.
    Rules: `update_machine` R5 [BUG-962], Errors row 7"""
    m1 = mk_machine("M1")
    before_m1 = snap_before(db, m1)

    # Then 1
    with pytest.raises(ValidationError):
        MachineUpdate(name=None)
    # Then 2
    assert snap(db, m1) == before_m1


# [claude] MCM-U-20
@pytest.mark.xfail(strict=True, reason="BUG-962: Machine model number, manufacturer and note cannot be cleared")
def test_mcm_u_20__a_null_factory_id_is_rejected_by_machineupdate(db, mk_machine):
    """MCM-U-20 — a null factory_id is rejected by MachineUpdate.
    Rules: `update_machine` R5 [BUG-962], Errors row 7"""
    m1 = mk_machine("M1")
    before_m1 = snap_before(db, m1)

    # Then 1
    with pytest.raises(ValidationError):
        MachineUpdate(factory_id=None)
    # Then 2
    assert snap(db, m1) == before_m1


# [claude] MCM-U-21
@pytest.mark.xfail(strict=True, reason="BUG-967: Model number and manufacturer stored untrimmed; blank counts as a value")
def test_mcm_u_21__a_padded_model_number_is_stored_trimmed(db, w1, u2, mk_machine):
    """MCM-U-21 — a padded model number is stored trimmed.
    Rules: `update_machine` R6 [BUG-967]"""
    m1 = mk_machine("M1", model_number="L-200", manufacturer="Acme")
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(model_number=" L-300 "), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.model_number == "L-300"


# [claude] MCM-U-22
@pytest.mark.xfail(strict=True, reason="BUG-967: Model number and manufacturer stored untrimmed; blank counts as a value")
def test_mcm_u_22__a_padded_manufacturer_is_stored_trimmed(db, w1, u2, mk_machine):
    """MCM-U-22 — a padded manufacturer is stored trimmed.
    Rules: `update_machine` R6 [BUG-967]"""
    m1 = mk_machine("M1", model_number="L-200", manufacturer="Acme")
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(manufacturer=" Haas "), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.manufacturer == "Haas"


# [claude] MCM-U-23
@pytest.mark.xfail(strict=True, reason="BUG-967: Model number and manufacturer stored untrimmed; blank counts as a value")
def test_mcm_u_23__an_empty_model_number_is_stored_as_none(db, w1, u2, mk_machine):
    """MCM-U-23 — an empty model number is stored as None.
    Rules: `update_machine` R6 [BUG-967]"""
    m1 = mk_machine("M1", model_number="L-200", manufacturer="Acme")
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(model_number=""), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.model_number is None


# [claude] MCM-U-24
@pytest.mark.xfail(strict=True, reason="BUG-967: Model number and manufacturer stored untrimmed; blank counts as a value")
def test_mcm_u_24__an_empty_manufacturer_is_stored_as_none(db, w1, u2, mk_machine):
    """MCM-U-24 — an empty manufacturer is stored as None.
    Rules: `update_machine` R6 [BUG-967]"""
    m1 = mk_machine("M1", model_number="L-200", manufacturer="Acme")
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(manufacturer=""), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.manufacturer is None


# [claude] MCM-U-25
@pytest.mark.xfail(strict=True, reason="BUG-967: Model number and manufacturer stored untrimmed; blank counts as a value")
def test_mcm_u_25__a_whitespace_only_model_number_is_stored_as_none(db, w1, u2, mk_machine):
    """MCM-U-25 — a whitespace-only model number is stored as None.
    Rules: `update_machine` R6 [BUG-967]"""
    m1 = mk_machine("M1", model_number="L-200", manufacturer="Acme")
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(model_number="   "), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.model_number is None


# [claude] MCM-U-26
@pytest.mark.xfail(strict=True, reason="BUG-967: Model number and manufacturer stored untrimmed; blank counts as a value")
def test_mcm_u_26__a_whitespace_only_manufacturer_is_stored_as_none(db, w1, u2, mk_machine):
    """MCM-U-26 — a whitespace-only manufacturer is stored as None.
    Rules: `update_machine` R6 [BUG-967]"""
    m1 = mk_machine("M1", model_number="L-200", manufacturer="Acme")
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(manufacturer="\t"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.manufacturer is None


# [claude] MCM-U-27
def test_mcm_u_27__a_note_is_stored_as_sent_padding_kept(db, w1, u2, mk_machine):
    """MCM-U-27 — a note is stored as sent, padding kept.
    Rules: `update_machine` R6"""
    m1 = mk_machine("M1")
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(note="  Bay 4 "), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.note == "  Bay 4 "


# [claude] MCM-U-28
def test_mcm_u_28__an_empty_note_is_stored_as_an_empty_string(db, w1, u2, mk_machine):
    """MCM-U-28 — an empty note is stored as an empty string.
    Rules: `update_machine` R6"""
    m1 = mk_machine("M1", note="Bay 3")
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(note=""), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.note == ""


# [claude] MCM-U-29
@pytest.mark.xfail(strict=True, reason="BUG-972: Over-long model number or manufacturer crashes")
def test_mcm_u_29__a_model_number_of_201_characters_is_rejected_by_machineupdate(db, mk_machine):
    """MCM-U-29 — a model_number of 201 characters is rejected by MachineUpdate.
    Rules: `update_machine` R6a [BUG-972], Errors row 7"""
    m1 = mk_machine("M1")
    before_m1 = snap_before(db, m1)

    # Then 1
    with pytest.raises(ValidationError):
        MachineUpdate(model_number="x" * 201)
    # Then 2
    assert snap(db, m1) == before_m1


# [claude] MCM-U-30
def test_mcm_u_30__a_model_number_of_exactly_200_characters_is_accepted_and_stored(db, w1, u2, mk_machine):
    """MCM-U-30 — a model_number of exactly 200 characters is accepted and stored.
    Rules: `update_machine` R6a"""
    m1 = mk_machine("M1")
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(model_number="x" * 200), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.model_number == "x" * 200


# [claude] MCM-U-31
@pytest.mark.xfail(strict=True, reason="BUG-972: Over-long model number or manufacturer crashes")
def test_mcm_u_31__a_manufacturer_of_201_characters_is_rejected_by_machineupdate(db, mk_machine):
    """MCM-U-31 — a manufacturer of 201 characters is rejected by MachineUpdate.
    Rules: `update_machine` R6a [BUG-972], Errors row 7"""
    m1 = mk_machine("M1")
    before_m1 = snap_before(db, m1)

    # Then 1
    with pytest.raises(ValidationError):
        MachineUpdate(manufacturer="x" * 201)
    # Then 2
    assert snap(db, m1) == before_m1


# [claude] MCM-U-32
def test_mcm_u_32__a_manufacturer_of_exactly_200_characters_is_accepted_and_stored(db, w1, u2, mk_machine):
    """MCM-U-32 — a manufacturer of exactly 200 characters is accepted and stored.
    Rules: `update_machine` R6a"""
    m1 = mk_machine("M1")
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(manufacturer="x" * 200), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.manufacturer == "x" * 200


# [claude] MCM-U-33
@pytest.mark.xfail(strict=True, reason="BUG-950: Blank / whitespace-only machine names accepted; names stored untrimmed")
def test_mcm_u_33__a_sent_name_is_stored_trimmed(db, w1, u2, mk_machine):
    """MCM-U-33 — a sent name is stored trimmed.
    Rules: `update_machine` R7 [BUG-950]"""
    m1 = mk_machine("M1")
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(name="  Big  Lathe "), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.name == "Big  Lathe"


# [claude] MCM-U-34
@pytest.mark.xfail(strict=True, reason="BUG-950: Blank / whitespace-only machine names accepted; names stored untrimmed")
def test_mcm_u_34__the_own_name_with_outer_spaces_counts_as_equal_nothing_changes(db, w1, u2, mk_machine):
    """MCM-U-34 — the own name with outer spaces counts as equal: nothing changes.
    Rules: `update_machine` R7 [BUG-950], R9"""
    m1 = mk_machine("M1")
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(name=" Lathe "), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.name == "Lathe"
    # Then 3
    rows = events_of(db, m1)
    assert len(rows) == 0


# [claude] MCM-U-35
@pytest.mark.xfail(strict=True, reason="BUG-950: Blank / whitespace-only machine names accepted; names stored untrimmed")
def test_mcm_u_35__an_empty_name_is_rejected_by_machineupdate(db, mk_machine):
    """MCM-U-35 — an empty name is rejected by MachineUpdate.
    Rules: `update_machine` R7 [BUG-950], Errors row 7"""
    m1 = mk_machine("M1")
    before_m1 = snap_before(db, m1)

    # Then 1
    with pytest.raises(ValidationError):
        MachineUpdate(name="")
    # Then 2
    assert snap(db, m1) == before_m1


# [claude] MCM-U-36
@pytest.mark.xfail(strict=True, reason="BUG-950: Blank / whitespace-only machine names accepted; names stored untrimmed")
def test_mcm_u_36__a_name_of_three_spaces_is_rejected_by_machineupdate(db, mk_machine):
    """MCM-U-36 — a name of three spaces is rejected by MachineUpdate.
    Rules: `update_machine` R7 [BUG-950], Errors row 7"""
    m1 = mk_machine("M1")
    before_m1 = snap_before(db, m1)

    # Then 1
    with pytest.raises(ValidationError):
        MachineUpdate(name="   ")
    # Then 2
    assert snap(db, m1) == before_m1


# [claude] MCM-U-37
@pytest.mark.xfail(strict=True, reason="BUG-950: Blank / whitespace-only machine names accepted; names stored untrimmed")
def test_mcm_u_37__a_name_of_one_tab_is_rejected_by_machineupdate(db, mk_machine):
    """MCM-U-37 — a name of one tab is rejected by MachineUpdate.
    Rules: `update_machine` R7 [BUG-950], Errors row 7"""
    m1 = mk_machine("M1")
    before_m1 = snap_before(db, m1)

    # Then 1
    with pytest.raises(ValidationError):
        MachineUpdate(name="\t")
    # Then 2
    assert snap(db, m1) == before_m1


# [claude] MCM-U-38
def test_mcm_u_38__a_one_character_name_is_accepted_by_machineupdate(db, mk_machine):
    """MCM-U-38 — a one-character name is accepted by MachineUpdate.
    Rules: `update_machine` R7"""
    mk_machine("M1")
    result = MachineUpdate(name="a")

    # Then 1
    assert result.name == "a"


# [claude] MCM-U-39
def test_mcm_u_39__a_name_used_by_another_live_machine_of_the_factory_is_refused_and_the(db, w1, u2, mk_machine):
    """MCM-U-39 — a name used by another live machine of the factory is refused and the other fields are not applied.
    Rules: `update_machine` R8, Errors row 5"""
    m1 = mk_machine("M1")
    m2 = mk_machine("M2")
    before_m1 = snap_before(db, m1)
    before_m2 = snap_before(db, m2)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(name="Press", note="Bay 4"), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Machine with name 'Press' already exists in this factory"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, m1) == before_m1
    # Then 6
    assert snap(db, m2) == before_m2


# [claude] MCM-U-40
@pytest.mark.xfail(strict=True, reason="BUG-952: Machine duplicate-name check is case- and whitespace-sensitive")
def test_mcm_u_40__a_name_that_differs_only_in_case_from_another_machine_s_is_refused(db, w1, u2, mk_machine):
    """MCM-U-40 — a name that differs only in case from another machine's is refused.
    Rules: `update_machine` R8 [BUG-952], Errors row 5"""
    m1 = mk_machine("M1")
    mk_machine("M2")
    before_m1 = snap_before(db, m1)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(name="PRESS"), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Machine with name 'PRESS' already exists in this factory"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, m1) == before_m1


# [claude] MCM-U-41
def test_mcm_u_41__a_name_used_only_by_a_soft_deleted_machine_is_free(db, w1, u2, mk_machine):
    """MCM-U-41 — a name used only by a soft-deleted machine is free.
    Rules: `update_machine` R8"""
    m1 = mk_machine("M1")
    mx = mk_machine("MX")
    before_mx = snap_before(db, mx)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(name="Old Saw"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.name == "Old Saw"
    # Then 3
    assert snap(db, mx) == before_mx


# [claude] MCM-U-42
def test_mcm_u_42__a_name_used_only_in_another_factory_is_free(db, w1, u2, mk_machine):
    """MCM-U-42 — a name used only in another factory is free.
    Rules: `update_machine` R8"""
    m1 = mk_machine("M1")
    m3 = mk_machine("M3")
    before_m3 = snap_before(db, m3)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(name="Drill"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.name == "Drill"
    # Then 3
    assert snap(db, m3) == before_m3


# [claude] MCM-U-43
def test_mcm_u_43__the_name_is_checked_in_the_resulting_factory_on_a_move_with_a_new_name(db, w1, u2, f2, mk_machine):
    """MCM-U-43 — the name is checked in the resulting factory on a move with a new name.
    Rules: `update_machine` R8, R10, Errors row 5"""
    m1 = mk_machine("M1")
    mk_machine("M3")
    before_m1 = snap_before(db, m1)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(name="Drill", factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Machine with name 'Drill' already exists in this factory"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, m1) == before_m1


# [claude] MCM-U-44
def test_mcm_u_44__the_own_name_sent_unchanged_succeeds_and_writes_no_event(db, w1, u2, mk_machine):
    """MCM-U-44 — the own name sent unchanged succeeds and writes no event.
    Rules: `update_machine` R9, R27"""
    m1 = mk_machine("M1")
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(name="Lathe"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.name == "Lathe"
    # Then 3
    rows = events_of(db, m1)
    assert len(rows) == 0


# [claude] MCM-U-45
def test_mcm_u_45__changing_only_the_case_of_the_own_name_succeeds(db, w1, u2, mk_machine):
    """MCM-U-45 — changing only the case of the own name succeeds.
    Rules: `update_machine` R9"""
    m1 = mk_machine("M1")
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(name="LATHE"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.name == "LATHE"
    # Then 3
    rows = events_of(db, m1)
    assert len(rows) == 1
    # Then 4
    assert events_of(db, m1)[0].metadata_json == {"changes": [{"field": "name", "label": "Name", "from_value": "Lathe", "to_value": "LATHE"}]}


# [claude] MCM-U-46
@pytest.mark.xfail(strict=True, reason="BUG-954: Moving a machine into a factory where its name is taken is not checked")
def test_mcm_u_46__a_plain_move_into_a_factory_with_a_live_machine_of_that_name_is(db, w1, u2, f2, mk_machine):
    """MCM-U-46 — a plain move into a factory with a live machine of that name is refused.
    Rules: `update_machine` R10 [BUG-954], Errors row 5"""
    m1 = mk_machine("M1")
    mk_machine("M3", name="Lathe")
    before_m1 = snap_before(db, m1)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Machine with name 'Lathe' already exists in this factory"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, m1) == before_m1


# [claude] MCM-U-47
@pytest.mark.xfail(strict=True, reason="BUG-954: Moving a machine into a factory where its name is taken is not checked")
def test_mcm_u_47__a_move_re_sending_the_same_name_into_a_factory_with_a_live_machine_of(db, w1, u2, f2, mk_machine):
    """MCM-U-47 — a move re-sending the same name into a factory with a live machine of that name is refused.
    Rules: `update_machine` R10 [BUG-954], Errors row 5"""
    m1 = mk_machine("M1")
    mk_machine("M3", name="Lathe")
    before_m1 = snap_before(db, m1)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f2.id, name="Lathe"), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Machine with name 'Lathe' already exists in this factory"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, m1) == before_m1


# [claude] MCM-U-48
def test_mcm_u_48__a_plain_move_into_a_factory_where_the_name_is_free_succeeds(db, w1, u2, f2, mk_machine):
    """MCM-U-48 — a plain move into a factory where the name is free succeeds.
    Rules: `update_machine` R10, R11"""
    m1 = mk_machine("M1")
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.factory_id == f2.id
    # Then 3
    row = reread(db, m1)
    assert row.name == "Lathe"
    # Then 4
    row = reread(db, m1)
    assert row.updated_by == u2.id


# [claude] MCM-U-49
def test_mcm_u_49__a_plain_move_next_to_a_soft_deleted_machine_of_that_name_succeeds(db, w1, u2, f2, mk_machine):
    """MCM-U-49 — a plain move next to a soft-deleted machine of that name succeeds.
    Rules: `update_machine` R10"""
    m1 = mk_machine("M1")
    mx = mk_machine("MX", name="Lathe", factory_id=f2.id)
    before_mx = snap_before(db, mx)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.factory_id == f2.id
    # Then 3
    assert snap(db, mx) == before_mx


# [claude] MCM-U-50
def test_mcm_u_50__a_move_with_a_new_name_free_in_the_target_succeeds_even_if_taken_in(db, w1, u2, f2, mk_machine):
    """MCM-U-50 — a move with a new name free in the target succeeds, even if taken in the old factory.
    Rules: `update_machine` R10"""
    m1 = mk_machine("M1")
    m2 = mk_machine("M2")
    before_m2 = snap_before(db, m2)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(name="Press", factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.name == "Press"
    assert row.factory_id == f2.id
    # Then 3
    assert snap(db, m2) == before_m2


# [claude] MCM-U-51
@pytest.mark.xfail(strict=True, reason="BUG-953: Machine name uniqueness per factory not enforced by the database")
def test_mcm_u_51__a_duplicate_that_reaches_the_flush_gets_the_409_not_a_database_error(db, w1, u2, mk_machine, monkeypatch):
    """MCM-U-51 — a duplicate that reaches the flush gets the 409, not a database error.
    Rules: `update_machine` R10a [BUG-953], Errors row 5"""
    m1 = mk_machine("M1")
    mk_machine("M2")
    monkeypatch.setattr(MachineManager, "_check_name_exists_in_factory", lambda *args, **kwargs: False)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with db.begin_nested():
            M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(name="Press"), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Machine with name 'Press' already exists in this factory"
    # Then 4
    row = reread(db, m1)
    assert row.name == "Lathe"
    # Then 5
    assert count_rows(db, "machines", name="Press") == 1


# [claude] MCM-U-52
def test_mcm_u_52__a_target_factory_that_does_not_exist_is_refused(db, w1, u2, mk_machine):
    """MCM-U-52 — a target factory that does not exist is refused.
    Rules: `update_machine` R11, Errors row 3"""
    m1 = mk_machine("M1")
    before_m1 = snap_before(db, m1)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=MISSING), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory with ID 999999999 not found"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, m1) == before_m1


# [claude] MCM-U-53
def test_mcm_u_53__a_target_factory_of_another_workspace_is_refused_as_not_found(db, w1, u2, f9, mk_machine):
    """MCM-U-53 — a target factory of another workspace is refused as not found.
    Rules: `update_machine` R11, Errors row 3"""
    m1 = mk_machine("M1")
    before_m1 = snap_before(db, m1)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f9.id), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory with ID {f9.id} not found"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, m1) == before_m1


# [claude] MCM-U-54
@pytest.mark.xfail(strict=True, reason="BUG-963: A machine can be created in, or moved to, a soft-deleted factory")
def test_mcm_u_54__a_soft_deleted_target_factory_is_refused(db, w1, u2, fd, mk_machine):
    """MCM-U-54 — a soft-deleted target factory is refused.
    Rules: `update_machine` R12 [BUG-963], Errors row 4"""
    m1 = mk_machine("M1")
    before_m1 = snap_before(db, m1)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=fd.id), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot move machine to deleted factory"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, m1) == before_m1


# [claude] MCM-U-55
@pytest.mark.xfail(strict=True, reason="BUG-963: A machine can be created in, or moved to, a soft-deleted factory")
def test_mcm_u_55__the_deleted_target_refusal_comes_before_the_name_check(db, w1, u2, fd, mk_machine):
    """MCM-U-55 — the deleted-target refusal comes before the name check.
    Rules: `update_machine` R12 [BUG-963], R15, Errors row 4"""
    m1 = mk_machine("M1")
    mk_machine("MF")
    before_m1 = snap_before(db, m1)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(name="Kiln", factory_id=fd.id), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot move machine to deleted factory"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, m1) == before_m1


# [claude] MCM-U-56
def test_mcm_u_56__a_live_but_inactive_target_factory_is_accepted(db, w1, u2, fi, mk_machine):
    """MCM-U-56 — a live but inactive target factory is accepted.
    Rules: `update_machine` R12"""
    m1 = mk_machine("M1")
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=fi.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.factory_id == fi.id


# [claude] MCM-U-57
@pytest.mark.xfail(strict=True, reason="BUG-961: Updating a machine with `factory_id=0` crashes instead of 404")
def test_mcm_u_57__factory_id_0_is_checked_like_any_id(db, w1, u2, mk_machine):
    """MCM-U-57 — factory id 0 is checked like any id.
    Rules: `update_machine` R13 [BUG-961], Errors row 3"""
    m1 = mk_machine("M1")
    before_m1 = snap_before(db, m1)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=0), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory with ID 0 not found"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, m1) == before_m1


# [claude] MCM-U-58
def test_mcm_u_58__the_current_factory_id_sent_changes_nothing_for_that_field_and_writes(db, w1, u2, f1, mk_machine):
    """MCM-U-58 — the current factory id sent changes nothing for that field and writes no event.
    Rules: `update_machine` R14, R27"""
    m1 = mk_machine("M1")
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f1.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.factory_id == f1.id
    # Then 3
    rows = events_of(db, m1)
    assert len(rows) == 0


# [claude] MCM-U-59
def test_mcm_u_59__the_target_factory_is_checked_before_the_name(db, w1, u2, mk_machine):
    """MCM-U-59 — the target factory is checked before the name.
    Rules: `update_machine` R15, Errors row 3"""
    m1 = mk_machine("M1")
    mk_machine("M2")
    before_m1 = snap_before(db, m1)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(name="Press", factory_id=MISSING), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory with ID 999999999 not found"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, m1) == before_m1


# [claude] MCM-U-60
def test_mcm_u_60__the_name_is_checked_before_the_section(db, w1, u2, mk_machine):
    """MCM-U-60 — the name is checked before the section.
    Rules: `update_machine` R15, Errors row 5"""
    m1 = mk_machine("M1")
    mk_machine("M2")
    before_m1 = snap_before(db, m1)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(name="Press", factory_section_id=MISSING), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Machine with name 'Press' already exists in this factory"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, m1) == before_m1


# [claude] MCM-U-61
def test_mcm_u_61__a_section_not_sent_leaves_the_link_untouched(db, w1, u2, s1, mk_machine, mk_link):
    """MCM-U-61 — a section not sent leaves the link untouched.
    Rules: `update_machine` R16"""
    m1 = mk_machine("M1")
    l1 = mk_link(m1, s1)
    before_l1 = snap_before(db, l1)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(note="Bay 4"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    assert snap(db, l1) == before_l1
    # Then 3
    assert result.factory_section_id == s1.id


# [claude] MCM-U-62
def test_mcm_u_62__a_section_is_set_on_a_machine_without_one(db, w1, u2, s1, mk_machine):
    """MCM-U-62 — a section is set on a machine without one.
    Rules: `update_machine` R17, R24, R23"""
    m1 = mk_machine("M1")
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_section_id=s1.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    assert result.factory_section_id == s1.id
    # Then 3
    assert result.factory_section_name == "Cutting"
    # Then 4
    assert count_rows(db, "machine_section_assignments") == 1
    # Then 5
    [row] = links_of(db, m1)
    assert row.factory_section_id == s1.id
    assert row.created_by == u2.id
    # Then 6
    row = reread(db, m1)
    assert row.updated_by == u2.id
    # Then 7
    row = reread(db, m1)
    assert row.updated_at is not None


# [claude] MCM-U-63
def test_mcm_u_63__a_section_is_moved_and_the_returned_machine_reads_the_new_value(db, w1, u2, s1, s2, mk_machine, mk_link):
    """MCM-U-63 — a section is moved and the returned machine reads the new value although the link was loaded.
    Rules: `update_machine` R17"""
    m1 = mk_machine("M1")
    mk_link(m1, s1)
    loaded = m1.factory_section_id  # noqa: F841
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_section_id=s2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    assert result.factory_section_id == s2.id
    # Then 3
    assert result.factory_section_name == "Paint"
    # Then 4
    assert count_rows(db, "machine_section_assignments") == 1


# [claude] MCM-U-64
def test_mcm_u_64__a_section_is_cleared_and_the_returned_machine_reads_none_although_the(db, w1, u2, s1, mk_machine, mk_link):
    """MCM-U-64 — a section is cleared and the returned machine reads None although the link was loaded.
    Rules: `update_machine` R17"""
    m1 = mk_machine("M1")
    mk_link(m1, s1)
    loaded = m1.factory_section_id  # noqa: F841
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_section_id=None), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    assert result.factory_section_id is None
    # Then 3
    assert result.factory_section_name is None
    # Then 4
    assert links_of(db, m1) == []


# [claude] MCM-U-65
def test_mcm_u_65__clearing_a_section_the_machine_does_not_have_changes_nothing(db, w1, u2, mk_machine):
    """MCM-U-65 — clearing a section the machine does not have changes nothing.
    Rules: `update_machine` R17, R27"""
    m1 = mk_machine("M1")
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_section_id=None), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    assert links_of(db, m1) == []
    # Then 3
    rows = events_of(db, m1)
    assert len(rows) == 0


# [claude] MCM-U-66
def test_mcm_u_66__a_move_with_a_section_of_the_new_factory_links_it_and_both_changes(db, w1, u2, f1, f2, s1, s3, mk_machine, mk_link):
    """MCM-U-66 — a move with a section of the new factory links it, and both changes are logged in order.
    Rules: `update_machine` R17, R26"""
    m1 = mk_machine("M1")
    mk_link(m1, s1)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f2.id, factory_section_id=s3.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    assert result.factory_section_id == s3.id
    # Then 3
    assert result.factory_section_name == "Welding"
    # Then 4
    row = reread(db, m1)
    assert row.factory_id == f2.id
    # Then 5
    assert events_of(db, m1)[0].metadata_json == {"changes": [{"field": "factory_id", "label": "Factory", "from_value": str(f1.id), "to_value": str(f2.id)}, {"field": "factory_section_id", "label": "Section", "from_value": str(s1.id), "to_value": str(s3.id)}]}


# [claude] MCM-U-67
def test_mcm_u_67__a_section_id_that_does_not_exist_is_refused_the_field_changes_stay(db, w1, u2, mk_machine):
    """MCM-U-67 — a section id that does not exist is refused; the field changes stay flushed until the rollback.
    Rules: `update_machine` R17, R21, Errors row 6"""
    m1 = mk_machine("M1")
    before_m1 = snap_before(db, m1)
    sp = db.begin_nested()

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(note="Bay 4", factory_section_id=MISSING), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory section with ID 999999999 not found"
    # Then 4
    row = reread(db, m1)
    assert row.note == "Bay 4"
    assert row.updated_by == u2.id
    # Then 5
    assert links_of(db, m1) == []
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    sp.rollback()
    assert snap(db, m1) == before_m1


# [claude] MCM-U-68
def test_mcm_u_68__section_id_0_is_refused_the_field_changes_stay_flushed_until_the(db, w1, u2, mk_machine):
    """MCM-U-68 — section id 0 is refused; the field changes stay flushed until the rollback.
    Rules: `update_machine` R17, R21, Errors row 6"""
    m1 = mk_machine("M1")
    before_m1 = snap_before(db, m1)
    sp = db.begin_nested()

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(note="Bay 4", factory_section_id=0), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory section with ID 0 not found"
    # Then 4
    row = reread(db, m1)
    assert row.note == "Bay 4"
    assert row.updated_by == u2.id
    # Then 5
    assert links_of(db, m1) == []
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    sp.rollback()
    assert snap(db, m1) == before_m1


# [claude] MCM-U-69
def test_mcm_u_69__a_soft_deleted_section_is_refused_the_field_changes_stay_flushed(db, w1, u2, sx, mk_machine):
    """MCM-U-69 — a soft-deleted section is refused; the field changes stay flushed until the rollback.
    Rules: `update_machine` R17, R21, Errors row 6"""
    m1 = mk_machine("M1")
    before_m1 = snap_before(db, m1)
    sp = db.begin_nested()

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(note="Bay 4", factory_section_id=sx.id), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot assign a machine to a deleted factory section"
    # Then 4
    row = reread(db, m1)
    assert row.note == "Bay 4"
    assert row.updated_by == u2.id
    # Then 5
    assert links_of(db, m1) == []
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    sp.rollback()
    assert snap(db, m1) == before_m1


# [claude] MCM-U-70
def test_mcm_u_70__a_section_of_another_factory_is_refused_the_field_changes_stay(db, w1, u2, s3, mk_machine):
    """MCM-U-70 — a section of another factory is refused; the field changes stay flushed until the rollback.
    Rules: `update_machine` R17, R21, Errors row 6"""
    m1 = mk_machine("M1")
    before_m1 = snap_before(db, m1)
    sp = db.begin_nested()

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(note="Bay 4", factory_section_id=s3.id), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Factory section does not belong to this machine's factory"
    # Then 4
    row = reread(db, m1)
    assert row.note == "Bay 4"
    assert row.updated_by == u2.id
    # Then 5
    assert links_of(db, m1) == []
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    sp.rollback()
    assert snap(db, m1) == before_m1


# [claude] MCM-U-71
def test_mcm_u_71__a_section_of_another_workspace_is_refused_the_field_changes_stay(db, w1, u2, s9, mk_machine):
    """MCM-U-71 — a section of another workspace is refused; the field changes stay flushed until the rollback.
    Rules: `update_machine` R17, R21, Errors row 6"""
    m1 = mk_machine("M1")
    before_m1 = snap_before(db, m1)
    sp = db.begin_nested()

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(note="Bay 4", factory_section_id=s9.id), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory section with ID {s9.id} not found"
    # Then 4
    row = reread(db, m1)
    assert row.note == "Bay 4"
    assert row.updated_by == u2.id
    # Then 5
    assert links_of(db, m1) == []
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    sp.rollback()
    assert snap(db, m1) == before_m1


# [claude] MCM-U-72
def test_mcm_u_72__a_section_of_the_old_factory_sent_with_a_move_is_refused(db, w1, u2, f2, s1, mk_machine, mk_link):
    """MCM-U-72 — a section of the old factory sent with a move is refused.
    Rules: `update_machine` R17, R21, Errors row 6"""
    m1 = mk_machine("M1")
    l1 = mk_link(m1, s1)
    before_m1 = snap_before(db, m1)
    before_l1 = snap_before(db, l1)
    sp = db.begin_nested()

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f2.id, factory_section_id=s1.id), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Factory section does not belong to this machine's factory"
    # Then 4
    assert count_rows(db, "machine_activity_events") == 0
    # Then 5
    sp.rollback()
    assert snap(db, m1) == before_m1
    # Then 6
    assert snap(db, l1) == before_l1


# [claude] MCM-U-73
@pytest.mark.xfail(strict=True, reason="BUG-909: Re-saving a machine's current section deletes and re-creates its assignment")
def test_mcm_u_73__re_sending_the_current_section_keeps_the_link_row(db, w1, u1, u2, s1, mk_machine, mk_link):
    """MCM-U-73 — re-sending the current section keeps the link row.
    Rules: `update_machine` R18 [BUG-909]"""
    m1 = mk_machine("M1")
    l1 = mk_link(m1, s1)
    l1_id = l1.id
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_section_id=s1.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    assert count_rows(db, "machine_section_assignments") == 1
    # Then 3
    assert links_of(db, m1)[0].id == l1_id
    # Then 4
    assert links_of(db, m1)[0].created_by == u1.id


# [claude] MCM-U-74
def test_mcm_u_74__re_sending_the_current_section_leaves_one_link_to_it_and_no_event(db, w1, u2, s1, mk_machine, mk_link):
    """MCM-U-74 — re-sending the current section leaves one link to it and no event.
    Rules: `update_machine` R18, R27"""
    m1 = mk_machine("M1")
    mk_link(m1, s1)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_section_id=s1.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    assert count_rows(db, "machine_section_assignments") == 1
    # Then 3
    assert links_of(db, m1)[0].factory_section_id == s1.id
    # Then 4
    rows = events_of(db, m1)
    assert len(rows) == 0


# [claude] MCM-U-75
@pytest.mark.xfail(strict=True, reason="BUG-971: Editing a machine fails when its section was deleted")
def test_mcm_u_75__an_edit_re_sending_a_left_over_link_to_a_deleted_section_succeeds_and(db, w1, u2, sx, mk_machine, mk_link):
    """MCM-U-75 — an edit re-sending a left-over link to a deleted section succeeds and keeps the link.
    Rules: `update_machine` R19 [BUG-971]"""
    m1 = mk_machine("M1")
    mk_link(m1, sx)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(note="Bay 4", factory_section_id=sx.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.note == "Bay 4"
    # Then 3
    assert links_of(db, m1)[0].factory_section_id == sx.id


# [claude] MCM-U-76
def test_mcm_u_76__a_left_over_link_to_a_deleted_section_can_be_cleared(db, w1, u2, sx, mk_machine, mk_link):
    """MCM-U-76 — a left-over link to a deleted section can be cleared.
    Rules: `update_machine` R19"""
    m1 = mk_machine("M1")
    mk_link(m1, sx)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_section_id=None), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    assert links_of(db, m1) == []


# [claude] MCM-U-77
def test_mcm_u_77__an_edit_that_omits_a_left_over_link_to_a_deleted_section_works(db, w1, u2, sx, mk_machine, mk_link):
    """MCM-U-77 — an edit that omits a left-over link to a deleted section works.
    Rules: `update_machine` R19, R16"""
    m1 = mk_machine("M1")
    l1 = mk_link(m1, sx)
    before_l1 = snap_before(db, l1)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(note="Bay 4"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.note == "Bay 4"
    # Then 3
    assert snap(db, l1) == before_l1


# [claude] MCM-U-78
def test_mcm_u_78__a_deleted_section_re_sent_with_a_move_is_still_validated(db, w1, u2, f2, sx, mk_machine, mk_link):
    """MCM-U-78 — a deleted section re-sent with a move is still validated.
    Rules: `update_machine` R19, R17, Errors row 6"""
    m1 = mk_machine("M1")
    l1 = mk_link(m1, sx)
    before_m1 = snap_before(db, m1)
    before_l1 = snap_before(db, l1)
    sp = db.begin_nested()

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f2.id, factory_section_id=sx.id), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot assign a machine to a deleted factory section"
    # Then 4
    assert count_rows(db, "machine_activity_events") == 0
    # Then 5
    sp.rollback()
    assert snap(db, m1) == before_m1
    # Then 6
    assert snap(db, l1) == before_l1


# [claude] MCM-U-79
@pytest.mark.xfail(strict=True, reason="BUG-970: A moved machine keeps its old factory's section")
def test_mcm_u_79__a_move_without_a_section_clears_the_old_factory_s_section(db, w1, u2, f2, s1, mk_machine, mk_link):
    """MCM-U-79 — a move without a section clears the old factory's section.
    Rules: `update_machine` R20 [BUG-970]"""
    m1 = mk_machine("M1")
    mk_link(m1, s1)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.factory_id == f2.id
    # Then 3
    assert links_of(db, m1) == []
    # Then 4
    assert result.factory_section_id is None


# [claude] MCM-U-80
@pytest.mark.xfail(strict=True, reason="BUG-970: A moved machine keeps its old factory's section")
def test_mcm_u_80__the_log_of_such_a_move_records_the_section_change(db, w1, u2, f1, f2, s1, mk_machine, mk_link):
    """MCM-U-80 — the log of such a move records the section change.
    Rules: `update_machine` R20 [BUG-970], R26"""
    m1 = mk_machine("M1")
    mk_link(m1, s1)
    s1_id = s1.id
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    rows = events_of(db, m1)
    assert len(rows) == 1
    # Then 3
    assert events_of(db, m1)[0].metadata_json == {"changes": [{"field": "factory_id", "label": "Factory", "from_value": str(f1.id), "to_value": str(f2.id)}, {"field": "factory_section_id", "label": "Section", "from_value": str(s1_id), "to_value": None}]}


# [claude] MCM-U-81
def test_mcm_u_81__a_move_of_a_machine_without_a_section_logs_only_the_factory(db, w1, u2, f1, f2, mk_machine):
    """MCM-U-81 — a move of a machine without a section logs only the factory.
    Rules: `update_machine` R20, R26, R11"""
    m1 = mk_machine("M1")
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    rows = events_of(db, m1)
    assert len(rows) == 1
    # Then 3
    assert rows[0].event_type == "updated"
    assert rows[0].description == "Machine details updated"
    # Then 4
    assert rows[0].performed_by == u2.id
    assert rows[0].workspace_id == w1.id
    # Then 5
    assert rows[0].metadata_json == {"changes": [{"field": "factory_id", "label": "Factory", "from_value": str(f1.id), "to_value": str(f2.id)}]}


# [claude] MCM-U-82
def test_mcm_u_82__a_move_with_an_explicit_null_clears_the_link_and_logs_both(db, w1, u2, f1, f2, s1, mk_machine, mk_link):
    """MCM-U-82 — a move with an explicit null clears the link and logs both.
    Rules: `update_machine` R17, R26"""
    m1 = mk_machine("M1")
    mk_link(m1, s1)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f2.id, factory_section_id=None), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    assert links_of(db, m1) == []
    # Then 3
    assert events_of(db, m1)[0].metadata_json == {"changes": [{"field": "factory_id", "label": "Factory", "from_value": str(f1.id), "to_value": str(f2.id)}, {"field": "factory_section_id", "label": "Section", "from_value": str(s1.id), "to_value": None}]}


# [claude] MCM-U-83
def test_mcm_u_83__the_current_factory_id_sent_without_a_section_keeps_the_link(db, w1, u2, f1, s1, mk_machine, mk_link):
    """MCM-U-83 — the current factory id sent without a section keeps the link.
    Rules: `update_machine` R20, R16, R14"""
    m1 = mk_machine("M1")
    l1 = mk_link(m1, s1)
    before_l1 = snap_before(db, l1)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f1.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    assert snap(db, l1) == before_l1


# [claude] MCM-U-84
@pytest.mark.xfail(strict=True, reason="BUG-959: `updated_by` stamped on no-op machine updates")
def test_mcm_u_84__an_empty_request_leaves_the_audit_stamp_alone(db, w1, u2, mk_machine):
    """MCM-U-84 — an empty request leaves the audit stamp alone.
    Rules: `update_machine` R24 [BUG-959]"""
    m1 = mk_machine("M1", note="Bay 3", updated_by=None, updated_at=None)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.updated_by is None
    # Then 3
    row = reread(db, m1)
    assert row.updated_at is None


# [claude] MCM-U-85
@pytest.mark.xfail(strict=True, reason="BUG-959: `updated_by` stamped on no-op machine updates")
def test_mcm_u_85__values_equal_to_the_current_ones_leaves_the_audit_stamp_alone(db, w1, u2, mk_machine):
    """MCM-U-85 — values equal to the current ones leaves the audit stamp alone.
    Rules: `update_machine` R24 [BUG-959]"""
    m1 = mk_machine("M1", note="Bay 3", updated_by=None, updated_at=None)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(name="Lathe", note="Bay 3"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.updated_by is None
    # Then 3
    row = reread(db, m1)
    assert row.updated_at is None


# [claude] MCM-U-86
@pytest.mark.xfail(strict=True, reason="BUG-959: `updated_by` stamped on no-op machine updates")
def test_mcm_u_86__clearing_an_empty_section_leaves_the_audit_stamp_alone(db, w1, u2, mk_machine):
    """MCM-U-86 — clearing an empty section leaves the audit stamp alone.
    Rules: `update_machine` R24 [BUG-959]"""
    m1 = mk_machine("M1", note="Bay 3", updated_by=None, updated_at=None)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_section_id=None), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.updated_by is None
    # Then 3
    row = reread(db, m1)
    assert row.updated_at is None


# [claude] MCM-U-87
@pytest.mark.xfail(strict=True, reason="BUG-959: `updated_by` stamped on no-op machine updates")
def test_mcm_u_87__the_current_factory_id_leaves_the_audit_stamp_alone(db, w1, u2, f1, mk_machine):
    """MCM-U-87 — the current factory id leaves the audit stamp alone.
    Rules: `update_machine` R24 [BUG-959]"""
    m1 = mk_machine("M1", note="Bay 3", updated_by=None, updated_at=None)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f1.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.updated_by is None
    # Then 3
    row = reread(db, m1)
    assert row.updated_at is None


# [claude] MCM-U-88
@pytest.mark.xfail(strict=True, reason="BUG-959: `updated_by` stamped on no-op machine updates")
def test_mcm_u_88__a_no_op_keeps_another_user_s_stamp(db, w1, u1, u2, mk_machine):
    """MCM-U-88 — a no-op keeps another user's stamp.
    Rules: `update_machine` R24 [BUG-959]"""
    m1 = mk_machine("M1", updated_by=u1.id, updated_at=T0)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.updated_by == u1.id
    # Then 3
    row = reread(db, m1)
    assert row.updated_at == T0


# [claude] MCM-U-89
@pytest.mark.xfail(strict=True, reason="BUG-959: `updated_by` stamped on no-op machine updates")
def test_mcm_u_89__re_sending_the_section_leaves_the_audit_stamp_alone(db, w1, u2, s1, mk_machine, mk_link):
    """MCM-U-89 — re-sending the section leaves the audit stamp alone.
    Rules: `update_machine` R24 [BUG-959]"""
    m1 = mk_machine("M1")
    mk_link(m1, s1)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_section_id=s1.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.updated_by is None


# [claude] MCM-U-90
def test_mcm_u_90__a_no_op_by_the_user_already_stamped_writes_nothing(db, w1, u2, mk_machine):
    """MCM-U-90 — a no-op by the user already stamped writes nothing.
    Rules: `update_machine` R24, R27"""
    m1 = mk_machine("M1", updated_by=u2.id, updated_at=T0)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.updated_by == u2.id
    # Then 3
    row = reread(db, m1)
    assert row.updated_at == T0
    # Then 4
    rows = events_of(db, m1)
    assert len(rows) == 0


# [claude] MCM-U-91
def test_mcm_u_91__an_empty_request_writes_no_event(db, w1, u2, mk_machine):
    """MCM-U-91 — an empty request writes no event.
    Rules: `update_machine` R27"""
    m1 = mk_machine("M1")
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    rows = events_of(db, m1)
    assert len(rows) == 0


# [claude] MCM-U-92
def test_mcm_u_92__values_equal_to_the_current_ones_write_no_event(db, w1, u2, mk_machine):
    """MCM-U-92 — values equal to the current ones write no event.
    Rules: `update_machine` R27"""
    m1 = mk_machine("M1", note="Bay 3", model_number="L-200")
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(name="Lathe", note="Bay 3", model_number="L-200"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    rows = events_of(db, m1)
    assert len(rows) == 0


# [claude] MCM-U-93
def test_mcm_u_93__one_updated_event_lists_every_changed_field_in_the_fixed_order(db, w1, u2, f1, f2, s1, s3, mk_machine, mk_link):
    """MCM-U-93 — one updated event lists every changed field in the fixed order.
    Rules: `update_machine` R25, R26"""
    m1 = mk_machine("M1", model_number="L-200", manufacturer="Acme", note="Bay 3")
    mk_link(m1, s1)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(note="Bay 4", manufacturer="Haas", model_number="L-300", factory_section_id=s3.id, factory_id=f2.id, name="Big Lathe"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    rows = events_of(db, m1)
    assert len(rows) == 1
    # Then 3
    assert rows[0].event_type == "updated"
    assert rows[0].description == "Machine details updated"
    # Then 4
    assert rows[0].performed_by == u2.id
    assert rows[0].workspace_id == w1.id
    # Then 5
    assert rows[0].metadata_json == {"changes": [{"field": "name", "label": "Name", "from_value": "Lathe", "to_value": "Big Lathe"}, {"field": "factory_id", "label": "Factory", "from_value": str(f1.id), "to_value": str(f2.id)}, {"field": "factory_section_id", "label": "Section", "from_value": str(s1.id), "to_value": str(s3.id)}, {"field": "model_number", "label": "Model number", "from_value": "L-200", "to_value": "L-300"}, {"field": "manufacturer", "label": "Manufacturer", "from_value": "Acme", "to_value": "Haas"}, {"field": "note", "label": "Note", "from_value": "Bay 3", "to_value": "Bay 4"}]}


# [claude] MCM-U-94
def test_mcm_u_94__a_field_that_did_not_change_is_left_out_of_the_log(db, w1, u2, mk_machine):
    """MCM-U-94 — a field that did not change is left out of the log.
    Rules: `update_machine` R26"""
    m1 = mk_machine("M1", note="Bay 3")
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(name="Lathe", note="Bay 4"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    rows = events_of(db, m1)
    assert len(rows) == 1
    # Then 3
    assert rows[0].event_type == "updated"
    assert rows[0].description == "Machine details updated"
    # Then 4
    assert rows[0].performed_by == u2.id
    assert rows[0].workspace_id == w1.id
    # Then 5
    assert rows[0].metadata_json == {"changes": [{"field": "note", "label": "Note", "from_value": "Bay 3", "to_value": "Bay 4"}]}


# [claude] MCM-U-95
def test_mcm_u_95__a_section_set_from_none_is_logged_from_none(db, w1, u2, s1, mk_machine):
    """MCM-U-95 — a section set from none is logged from None.
    Rules: `update_machine` R26"""
    m1 = mk_machine("M1")
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_section_id=s1.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    rows = events_of(db, m1)
    assert len(rows) == 1
    # Then 3
    assert rows[0].event_type == "updated"
    assert rows[0].description == "Machine details updated"
    # Then 4
    assert rows[0].performed_by == u2.id
    assert rows[0].workspace_id == w1.id
    # Then 5
    assert rows[0].metadata_json == {"changes": [{"field": "factory_section_id", "label": "Section", "from_value": None, "to_value": str(s1.id)}]}


# [claude] MCM-U-96
def test_mcm_u_96__a_cleared_section_is_logged_to_none(db, w1, u2, s1, mk_machine, mk_link):
    """MCM-U-96 — a cleared section is logged to None.
    Rules: `update_machine` R26"""
    m1 = mk_machine("M1")
    mk_link(m1, s1)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_section_id=None), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    rows = events_of(db, m1)
    assert len(rows) == 1
    # Then 3
    assert rows[0].event_type == "updated"
    assert rows[0].description == "Machine details updated"
    # Then 4
    assert rows[0].performed_by == u2.id
    assert rows[0].workspace_id == w1.id
    # Then 5
    assert rows[0].metadata_json == {"changes": [{"field": "factory_section_id", "label": "Section", "from_value": str(s1.id), "to_value": None}]}


# [claude] MCM-U-97
def test_mcm_u_97__a_value_set_on_an_empty_field_is_logged_from_none(db, w1, u2, mk_machine):
    """MCM-U-97 — a value set on an empty field is logged from None.
    Rules: `update_machine` R26"""
    m1 = mk_machine("M1")
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(model_number="L-200"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    rows = events_of(db, m1)
    assert len(rows) == 1
    # Then 3
    assert rows[0].event_type == "updated"
    assert rows[0].description == "Machine details updated"
    # Then 4
    assert rows[0].performed_by == u2.id
    assert rows[0].workspace_id == w1.id
    # Then 5
    assert rows[0].metadata_json == {"changes": [{"field": "model_number", "label": "Model number", "from_value": None, "to_value": "L-200"}]}


# [claude] MCM-U-98
@pytest.mark.xfail(strict=True, reason="BUG-975: Open work orders stay in the old factory when their machine moves")
def test_mcm_u_98__an_open_draft_order_follows_the_moved_machine(db, w1, u2, f2, mk_machine, mk_order):
    """MCM-U-98 — an open DRAFT order follows the moved machine.
    Rules: `update_machine` R28 [BUG-975]"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="DRAFT")
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.factory_id == f2.id
    # Then 3
    row = reread(db, o1)
    assert row.factory_id == f2.id
    # Then 4
    row = reread(db, o1)
    assert row.updated_by == u2.id
    # Then 5
    row = reread(db, o1)
    assert row.updated_at is not None


# [claude] MCM-U-99
@pytest.mark.xfail(strict=True, reason="BUG-975: Open work orders stay in the old factory when their machine moves")
def test_mcm_u_99__every_open_order_of_the_machine_follows_whatever_its_state(db, w1, u2, f2, mk_machine, mk_order):
    """MCM-U-99 — every open order of the machine follows, whatever its state.
    Rules: `update_machine` R28 [BUG-975], R28f"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="DRAFT")
    o2 = mk_order(m1, "O2", status="IN_PROGRESS")
    o3 = mk_order(m1, "O3", status="DRAFT")
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, o1)
    assert row.factory_id == f2.id
    # Then 3
    row = reread(db, o2)
    assert row.factory_id == f2.id
    # Then 4
    row = reread(db, o3)
    assert row.factory_id == f2.id


# [claude] MCM-U-100
def test_mcm_u_100__the_columns_of_a_moved_order_other_than_factory_and_update_stamp_stay(db, w1, u2, f2, wt1, mk_machine, mk_order):
    """MCM-U-100 — the columns of a moved order other than factory and update stamp stay.
    Rules: `update_machine` R28"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="DRAFT", planned_date=D(3), required_approvals=2)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, o1)
    assert row.title == "Service"
    assert row.status == "DRAFT"
    assert row.work_order_number == "WO-O1"
    # Then 3
    row = reread(db, o1)
    assert row.planned_date == D(3)
    assert row.machine_id == m1.id
    assert row.workspace_id == w1.id
    # Then 4
    row = reread(db, o1)
    assert row.required_approvals == 2
    assert row.is_deleted is False
    assert row.work_order_type_id == wt1.id


# [claude] MCM-U-101
@pytest.mark.xfail(strict=True, reason="BUG-975: Open work orders stay in the old factory when their machine moves")
def test_mcm_u_101__each_state_that_is_not_open_and_every_other_order_stays_when_one(db, w1, u2, f2, mk_machine, mk_order, mk_line):
    """MCM-U-101 — each state that is not open, and every other order, stays when one order per state exists.
    Rules: `update_machine` R28 [BUG-975], R28a, R28f"""
    m1 = mk_machine("M1")
    m2 = mk_machine("M2")
    o1 = mk_order(m1, "O1", status="DRAFT")
    o2 = mk_order(m1, "O2", status="IN_PROGRESS")
    o3 = mk_order(m1, "O3", status="COMPLETED")
    o4 = mk_order(m1, "O4", status="VOIDED")
    o5 = mk_order(m1, "O5", status="DRAFT", is_deleted=True)
    o6 = mk_order(m2, "O6", status="DRAFT")
    mk_line(o6, source_location_type="machine", source_location_id=m1.id)
    before_o3 = snap_before(db, o3)
    before_o4 = snap_before(db, o4)
    before_o5 = snap_before(db, o5)
    before_o6 = snap_before(db, o6)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, o1)
    assert row.factory_id == f2.id
    # Then 3
    row = reread(db, o2)
    assert row.factory_id == f2.id
    # Then 4
    assert snap(db, o3) == before_o3
    # Then 5
    assert snap(db, o4) == before_o4
    # Then 6
    assert snap(db, o5) == before_o5
    # Then 7
    assert snap(db, o6) == before_o6
    # Then 8
    assert count_rows(db, "work_order_events") == 2


# [claude] MCM-U-102
def test_mcm_u_102__a_completed_order_stays_in_the_old_factory(db, w1, u2, f2, mk_machine, mk_order):
    """MCM-U-102 — a completed order stays in the old factory.
    Rules: `update_machine` R28a"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="COMPLETED")
    before_o1 = snap_before(db, o1)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.factory_id == f2.id
    # Then 3
    assert snap(db, o1) == before_o1
    # Then 4
    assert count_rows(db, "work_order_events") == 0


# [claude] MCM-U-103
def test_mcm_u_103__a_voided_order_stays_in_the_old_factory(db, w1, u2, f2, mk_machine, mk_order):
    """MCM-U-103 — a voided order stays in the old factory.
    Rules: `update_machine` R28a"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="VOIDED")
    before_o1 = snap_before(db, o1)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.factory_id == f2.id
    # Then 3
    assert snap(db, o1) == before_o1
    # Then 4
    assert count_rows(db, "work_order_events") == 0


# [claude] MCM-U-104
def test_mcm_u_104__a_soft_deleted_order_stays_in_the_old_factory(db, w1, u2, f2, mk_machine, mk_order):
    """MCM-U-104 — a soft-deleted order stays in the old factory.
    Rules: `update_machine` R28a"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="DRAFT", is_deleted=True)
    before_o1 = snap_before(db, o1)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.factory_id == f2.id
    # Then 3
    assert snap(db, o1) == before_o1
    # Then 4
    assert count_rows(db, "work_order_events") == 0


# [claude] MCM-U-105
def test_mcm_u_105__an_order_of_another_machine_with_a_line_sourcing_from_this_machine(db, w1, u2, f2, mk_machine, mk_order, mk_line):
    """MCM-U-105 — an order of another machine with a line sourcing from this machine stays.
    Rules: `update_machine` R28a"""
    m1 = mk_machine("M1")
    m2 = mk_machine("M2")
    o1 = mk_order(m2, "O1", status="DRAFT")
    l1 = mk_line(o1, source_location_type="machine", source_location_id=m1.id)
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    assert snap(db, o1) == before_o1
    # Then 3
    assert snap(db, l1) == before_l1
    # Then 4
    assert count_rows(db, "work_order_events") == 0


# [claude] MCM-U-106
def test_mcm_u_106__an_order_with_this_machine_id_in_another_workspace_stays(db, w1, w2, u2, f2, f9, wt9, mk_machine, mk_order):
    """MCM-U-106 — an order with this machine id in another workspace stays.
    Rules: `update_machine` R28a"""
    m1 = mk_machine("M1")
    o9 = mk_order(m1, "O9", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    before_o9 = snap_before(db, o9)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    assert snap(db, o9) == before_o9
    # Then 3
    assert count_rows(db, "work_order_events") == 0


# [claude] MCM-U-107
def test_mcm_u_107__the_current_factory_id_sent_changes_no_order_and_writes_no_order_event(db, w1, u2, f1, mk_machine, mk_order):
    """MCM-U-107 — the current factory id sent changes no order and writes no order event.
    Rules: `update_machine` R28b"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="DRAFT")
    before_o1 = snap_before(db, o1)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f1.id, note="Bay 4"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.note == "Bay 4"
    # Then 3
    assert snap(db, o1) == before_o1
    # Then 4
    assert count_rows(db, "work_order_events") == 0


# [claude] MCM-U-108
def test_mcm_u_108__an_edit_without_a_factory_changes_no_order_and_writes_no_order_event(db, w1, u2, mk_machine, mk_order):
    """MCM-U-108 — an edit without a factory changes no order and writes no order event.
    Rules: `update_machine` R28b"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="DRAFT")
    before_o1 = snap_before(db, o1)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(name="Big Lathe"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.name == "Big Lathe"
    # Then 3
    assert snap(db, o1) == before_o1
    # Then 4
    assert count_rows(db, "work_order_events") == 0


# [claude] MCM-U-109
def test_mcm_u_109__a_move_of_a_machine_without_open_orders_writes_no_order_event(db, w1, u2, f2, mk_machine):
    """MCM-U-109 — a move of a machine without open orders writes no order event.
    Rules: `update_machine` R28b"""
    m1 = mk_machine("M1")
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.factory_id == f2.id
    # Then 3
    assert count_rows(db, "work_order_events") == 0


# [claude] MCM-U-110
def test_mcm_u_110__a_refused_move_of_a_machine_of_another_workspace_changes_no_order(db, w1, w2, u2, f2, f9, wt9, mk_machine, mk_order):
    """MCM-U-110 — a refused move of a machine of another workspace changes no order.
    Rules: `update_machine` R28b, R1"""
    m9 = mk_machine("M9")
    o9 = mk_order(m9, "O9", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    before_o9 = snap_before(db, o9)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine(db, machine_id=m9.id, machine_data=MachineUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Machine with ID {m9.id} not found"
    # Then 4
    assert snap(db, o9) == before_o9
    # Then 5
    assert count_rows(db, "work_order_events") == 0


# [claude] MCM-U-111
def test_mcm_u_111__a_refused_move_of_a_soft_deleted_machine_changes_no_order(db, w1, u2, f2, mk_machine, mk_order):
    """MCM-U-111 — a refused move of a soft-deleted machine changes no order.
    Rules: `update_machine` R28b, R2"""
    mx = mk_machine("MX")
    o1 = mk_order(mx, "O1", status="DRAFT")
    before_o1 = snap_before(db, o1)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine(db, machine_id=mx.id, machine_data=MachineUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update a deleted machine"
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert count_rows(db, "work_order_events") == 0


# [claude] MCM-U-112
@pytest.mark.xfail(strict=True, reason="BUG-964: A machine inside a soft-deleted factory can still be edited or moved out")
def test_mcm_u_112__a_refused_move_out_of_a_soft_deleted_factory_changes_no_order(db, w1, u2, f2, fd, mk_machine, mk_order):
    """MCM-U-112 — a refused move out of a soft-deleted factory changes no order.
    Rules: `update_machine` R28b, R3 [BUG-964]"""
    mf = mk_machine("MF")
    o1 = mk_order(mf, "O1", status="DRAFT", factory_id=fd.id)
    before_o1 = snap_before(db, o1)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine(db, machine_id=mf.id, machine_data=MachineUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update a deleted machine"
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert count_rows(db, "work_order_events") == 0


# [claude] MCM-U-113
def test_mcm_u_113__a_move_with_a_taken_new_name_is_refused_and_changes_no_order(db, w1, u2, f2, mk_machine, mk_order):
    """MCM-U-113 — a move with a taken new name is refused and changes no order.
    Rules: `update_machine` R28b, R8"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="DRAFT")
    mk_machine("M3")
    before_o1 = snap_before(db, o1)
    before_m1 = snap_before(db, m1)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(name="Drill", factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Machine with name 'Drill' already exists in this factory"
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert count_rows(db, "work_order_events") == 0
    # Then 6
    assert snap(db, m1) == before_m1


# [claude] MCM-U-114
@pytest.mark.xfail(strict=True, reason="BUG-954: Moving a machine into a factory where its name is taken is not checked")
def test_mcm_u_114__a_plain_move_into_a_taken_name_is_refused_and_changes_no_order(db, w1, u2, f2, mk_machine, mk_order):
    """MCM-U-114 — a plain move into a taken name is refused and changes no order.
    Rules: `update_machine` R28b, R10 [BUG-954]"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="DRAFT")
    mk_machine("M3", name="Lathe")
    before_o1 = snap_before(db, o1)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Machine with name 'Lathe' already exists in this factory"
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert count_rows(db, "work_order_events") == 0


# [claude] MCM-U-115
def test_mcm_u_115__a_move_to_a_missing_factory_changes_no_order(db, w1, u2, mk_machine, mk_order):
    """MCM-U-115 — a move to a missing factory changes no order.
    Rules: `update_machine` R28b, R11"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="DRAFT")
    before_o1 = snap_before(db, o1)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=MISSING), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory with ID 999999999 not found"
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert count_rows(db, "work_order_events") == 0


# [claude] MCM-U-116
def test_mcm_u_116__a_move_to_a_factory_of_another_workspace_changes_no_order(db, w1, u2, f9, mk_machine, mk_order):
    """MCM-U-116 — a move to a factory of another workspace changes no order.
    Rules: `update_machine` R28b, R11"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="DRAFT")
    before_o1 = snap_before(db, o1)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f9.id), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory with ID {f9.id} not found"
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert count_rows(db, "work_order_events") == 0


# [claude] MCM-U-117
@pytest.mark.xfail(strict=True, reason="BUG-963: A machine can be created in, or moved to, a soft-deleted factory")
def test_mcm_u_117__a_move_to_a_soft_deleted_factory_changes_no_order(db, w1, u2, fd, mk_machine, mk_order):
    """MCM-U-117 — a move to a soft-deleted factory changes no order.
    Rules: `update_machine` R28b, R12 [BUG-963]"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="DRAFT")
    before_o1 = snap_before(db, o1)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=fd.id), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot move machine to deleted factory"
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert count_rows(db, "work_order_events") == 0


# [claude] MCM-U-118
@pytest.mark.xfail(strict=True, reason="BUG-961: Updating a machine with `factory_id=0` crashes instead of 404")
def test_mcm_u_118__factory_id_0_changes_no_order(db, w1, u2, mk_machine, mk_order):
    """MCM-U-118 — factory id 0 changes no order.
    Rules: `update_machine` R28b, R13 [BUG-961]"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="DRAFT")
    before_o1 = snap_before(db, o1)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=0), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory with ID 0 not found"
    # Then 4
    assert snap(db, o1) == before_o1
    # Then 5
    assert count_rows(db, "work_order_events") == 0


# [claude] MCM-U-119
@pytest.mark.xfail(strict=True, reason="BUG-975: Open work orders stay in the old factory when their machine moves")
def test_mcm_u_119__a_section_refused_after_a_move_leaves_the_orders_moved_and_their(db, w1, u2, f1, f2, s1, mk_machine, mk_order):
    """MCM-U-119 — a section refused after a move leaves the orders moved and their events written until the rollback.
    Rules: `update_machine` R28b [BUG-975], R21, Errors row 6"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="DRAFT")
    sp = db.begin_nested()

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f2.id, factory_section_id=s1.id), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Factory section does not belong to this machine's factory"
    # Then 4
    row = reread(db, m1)
    assert row.factory_id == f2.id
    # Then 5
    row = reread(db, o1)
    assert row.factory_id == f2.id
    # Then 6
    assert count_rows(db, "work_order_events") == 1
    # Then 7
    sp.rollback()
    row = reread(db, o1)
    assert row.factory_id == f1.id
    # Then 8
    assert count_rows(db, "work_order_events") == 0


# [claude] MCM-U-120
def test_mcm_u_120__the_rollback_after_a_refused_section_leaves_the_order_and_the_machine(db, w1, u2, f2, s1, mk_machine, mk_order):
    """MCM-U-120 — the rollback after a refused section leaves the order and the machine as they were.
    Rules: `update_machine` R28b, R21"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="DRAFT")
    before_m1 = snap_before(db, m1)
    before_o1 = snap_before(db, o1)
    sp = db.begin_nested()

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f2.id, factory_section_id=s1.id), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Factory section does not belong to this machine's factory"
    # Then 4
    assert count_rows(db, "machine_activity_events") == 0
    # Then 5
    sp.rollback()
    assert snap(db, m1) == before_m1
    # Then 6
    assert snap(db, o1) == before_o1
    # Then 7
    assert count_rows(db, "work_order_events") == 0


# [claude] MCM-U-121
@pytest.mark.xfail(strict=True, reason="BUG-975: Open work orders stay in the old factory when their machine moves")
def test_mcm_u_121__a_rollback_restores_moved_orders_and_removes_their_events(db, w1, u2, f1, f2, mk_machine, mk_order):
    """MCM-U-121 — a rollback restores moved orders and removes their events.
    Rules: `update_machine` R28b [BUG-975], R28e"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="DRAFT")
    sp = db.begin_nested()
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, o1)
    assert row.factory_id == f2.id
    # Then 3
    assert count_rows(db, "work_order_events") == 1
    # Then 4
    sp.rollback()
    row = reread(db, o1)
    assert row.factory_id == f1.id
    # Then 5
    assert count_rows(db, "work_order_events") == 0


# [claude] MCM-U-122
def test_mcm_u_122__a_consumed_line_keeps_its_source_when_its_order_moves(db, w1, u2, f1, f2, mk_machine, mk_order, mk_line):
    """MCM-U-122 — a consumed line keeps its source when its order moves.
    Rules: `update_machine` R28c"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="IN_PROGRESS")
    l1 = mk_line(o1, source_location_type="storage", source_location_id=f1.id, consumed_at=T0)
    before_l1 = snap_before(db, l1)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    assert snap(db, l1) == before_l1
    # Then 3
    row = reread(db, l1)
    assert row.source_location_type == "storage"
    assert row.source_location_id == f1.id
    assert row.consumed_at == T0


# [claude] MCM-U-123
def test_mcm_u_123__a_consumed_line_sourced_from_a_machine_keeps_its_source(db, w1, u2, f2, mk_machine, mk_order, mk_line):
    """MCM-U-123 — a consumed line sourced from a machine keeps its source.
    Rules: `update_machine` R28c"""
    m1 = mk_machine("M1")
    m2 = mk_machine("M2")
    o1 = mk_order(m1, "O1", status="IN_PROGRESS")
    l1 = mk_line(o1, source_location_type="machine", source_location_id=m2.id, consumed_at=T0)
    before_l1 = snap_before(db, l1)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    assert snap(db, l1) == before_l1


# [claude] MCM-U-124
def test_mcm_u_124__an_unconsumed_line_keeps_the_old_factory_s_store_as_its_source(db, w1, u2, f1, f2, mk_machine, mk_order, mk_line):
    """MCM-U-124 — an unconsumed line keeps the old factory's store as its source.
    Rules: `update_machine` R28d"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="DRAFT")
    l1 = mk_line(o1, source_location_type="storage", source_location_id=f1.id)
    before_l1 = snap_before(db, l1)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    assert snap(db, l1) == before_l1
    # Then 3
    row = reread(db, l1)
    assert row.source_location_type == "storage"
    assert row.source_location_id == f1.id
    assert row.consumed_at is None


# [claude] MCM-U-125
def test_mcm_u_125__an_unconsumed_line_sourced_from_a_machine_is_unaffected(db, w1, u2, f2, mk_machine, mk_order, mk_line):
    """MCM-U-125 — an unconsumed line sourced from a machine is unaffected.
    Rules: `update_machine` R28d"""
    m1 = mk_machine("M1")
    m2 = mk_machine("M2")
    o1 = mk_order(m1, "O1", status="DRAFT")
    l1 = mk_line(o1, source_location_type="machine", source_location_id=m2.id)
    before_l1 = snap_before(db, l1)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    assert snap(db, l1) == before_l1


# [claude] MCM-U-126
def test_mcm_u_126__a_move_keeps_recorded_approvals_approver_rows_and_required_approvals(db, w1, u1, u2, f2, mk_machine, mk_order, mk_approver):
    """MCM-U-126 — a move keeps recorded approvals, approver rows and required approvals of a moved DRAFT.
    Rules: `update_machine` R28d"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="DRAFT", required_approvals=2, approved_by=u1.id, approved_at=T0)
    ap1 = mk_approver(o1, u1, approved=True, approved_at=T0)
    approvers_before = db.execute(text("select * from work_order_approvers where work_order_id = :i order by id"), {"i": o1.id}).all()
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    assert db.execute(text("select * from work_order_approvers where work_order_id = :i order by id"), {"i": o1.id}).all() == approvers_before
    # Then 3
    row = reread(db, ap1)
    assert row.approved is True
    assert row.approved_at == T0
    # Then 4
    row = reread(db, o1)
    assert row.required_approvals == 2
    assert row.approved_by == u1.id
    assert row.approved_at == T0


# [claude] MCM-U-127
@pytest.mark.xfail(strict=True, reason="BUG-975: Open work orders stay in the old factory when their machine moves")
def test_mcm_u_127__each_moved_order_gets_one_updated_event_with_the_factory_change(db, w1, u2, f1, f2, mk_machine, mk_order):
    """MCM-U-127 — each moved order gets one updated event with the factory change.
    Rules: `update_machine` R28e [BUG-975], Side effects"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="DRAFT")
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    rows = wo_events(db, o1)
    assert len(rows) == 1
    # Then 3
    assert rows[0].work_order_id == o1.id
    assert rows[0].workspace_id == w1.id
    assert rows[0].event_type == "updated"
    # Then 4
    assert rows[0].description == "Order details updated"
    assert rows[0].performed_by == u2.id
    assert rows[0].created_at is not None
    # Then 5
    assert rows[0].metadata_json == {"changes": [{"field": "factory_id", "label": "Factory", "from_value": str(f1.id), "to_value": str(f2.id)}]}


# [claude] MCM-U-128
@pytest.mark.xfail(strict=True, reason="BUG-975: Open work orders stay in the old factory when their machine moves")
def test_mcm_u_128__two_moved_orders_get_one_event_each(db, w1, u2, f2, mk_machine, mk_order):
    """MCM-U-128 — two moved orders get one event each.
    Rules: `update_machine` R28e [BUG-975]"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="DRAFT")
    o2 = mk_order(m1, "O2", status="IN_PROGRESS")
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    rows = wo_events(db, o1)
    assert len(rows) == 1
    # Then 3
    rows = wo_events(db, o2)
    assert len(rows) == 1
    # Then 4
    assert count_rows(db, "work_order_events") == 2


# [claude] MCM-U-129
@pytest.mark.xfail(strict=True, reason="BUG-975: Open work orders stay in the old factory when their machine moves")
def test_mcm_u_129__the_order_s_event_holds_only_the_factory_also_when_the_machine_is(db, w1, u2, f1, f2, mk_machine, mk_order):
    """MCM-U-129 — the order's event holds only the factory, also when the machine is renamed in the same call.
    Rules: `update_machine` R28e [BUG-975]"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="DRAFT")
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f2.id, name="Big Lathe", note="Bay 4"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.name == "Big Lathe"
    # Then 3
    rows = wo_events(db, o1)
    assert len(rows) == 1
    # Then 4
    assert wo_events(db, o1)[0].metadata_json == {"changes": [{"field": "factory_id", "label": "Factory", "from_value": str(f1.id), "to_value": str(f2.id)}]}


# [claude] MCM-U-130
def test_mcm_u_130__the_machine_s_own_log_records_a_move_with_open_orders_as_usual(db, w1, u2, f1, f2, mk_machine, mk_order):
    """MCM-U-130 — the machine's own log records a move with open orders as usual.
    Rules: `update_machine` R28e, R25"""
    m1 = mk_machine("M1")
    mk_order(m1, "O1", status="DRAFT")
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    rows = events_of(db, m1)
    assert len(rows) == 1
    # Then 3
    assert rows[0].event_type == "updated"
    assert rows[0].description == "Machine details updated"
    # Then 4
    assert rows[0].performed_by == u2.id
    assert rows[0].workspace_id == w1.id
    # Then 5
    assert rows[0].metadata_json == {"changes": [{"field": "factory_id", "label": "Factory", "from_value": str(f1.id), "to_value": str(f2.id)}]}


# [claude] MCM-U-131
@pytest.mark.xfail(strict=True, reason="BUG-975: Open work orders stay in the old factory when their machine moves")
def test_mcm_u_131__an_in_progress_order_moves_like_a_draft(db, w1, u2, f2, mk_machine, mk_order):
    """MCM-U-131 — an IN_PROGRESS order moves like a draft.
    Rules: `update_machine` R28f [BUG-975]"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="IN_PROGRESS")
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, o1)
    assert row.factory_id == f2.id
    # Then 3
    row = reread(db, o1)
    assert row.status == "IN_PROGRESS"
    # Then 4
    row = reread(db, o1)
    assert row.updated_by == u2.id


# [claude] MCM-U-132
def test_mcm_u_132__consumed_parts_of_an_in_progress_order_stay_booked_out_of_the_old(db, w1, u2, f1, f2, mk_machine, mk_order, mk_line, mk_stock_movement):
    """MCM-U-132 — consumed parts of an IN_PROGRESS order stay booked out of the old factory.
    Rules: `update_machine` R28f, R28c"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="IN_PROGRESS")
    l1 = mk_line(o1, source_location_type="storage", source_location_id=f1.id, consumed_at=T0)
    lg = mk_stock_movement()
    before_lg = snap_before(db, lg)
    before_l1 = snap_before(db, l1)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    assert snap(db, lg) == before_lg
    # Then 3
    assert snap(db, l1) == before_l1
    # Then 4
    row = reread(db, lg)
    assert row.factory_id == f1.id


# [claude] MCM-U-133
def test_mcm_u_133__an_unknown_user_fails_on_flush_and_nothing_is_saved(db, w1, mk_machine):
    """MCM-U-133 — an unknown user fails on flush and nothing is saved.
    Rules: `update_machine` R29, Errors row 8"""
    m1 = mk_machine("M1")
    before_m1 = snap_before(db, m1)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(note="Bay 4"), workspace_id=w1.id, user_id=MISSING)
    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert "machines_updated_by_fkey" in str(exc.value.orig)
    # Then 4
    assert count_rows(db, "machine_activity_events") == 0
    # Then 5
    assert snap(db, m1) == before_m1


# [claude] MCM-U-134
@pytest.mark.xfail(strict=True, reason="BUG-959: `updated_by` stamped on no-op machine updates")
def test_mcm_u_134__an_empty_request_by_an_unknown_user_succeeds_because_nothing_is(db, w1, mk_machine):
    """MCM-U-134 — an empty request by an unknown user succeeds, because nothing is written.
    Rules: `update_machine` R29 [BUG-959]"""
    m1 = mk_machine("M1")
    before_m1 = snap_before(db, m1)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(), workspace_id=w1.id, user_id=MISSING)

    # Then 1
    assert result is m1
    # Then 2
    assert snap(db, m1) == before_m1


# [claude] MCM-U-135
def test_mcm_u_135__the_update_is_flushed_but_not_committed_a_rollback_restores_the_row(db, w1, u2, f2, mk_machine, mk_order, monkeypatch):
    """MCM-U-135 — the update is flushed but not committed: a rollback restores the row and removes the event.
    Rules: `update_machine` R30, R28b, Returns"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="DRAFT")
    before_m1 = snap_before(db, m1)
    before_o1 = snap_before(db, o1)
    sp = db.begin_nested()
    spy = commit_spy(db, monkeypatch)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(name="Big Lathe", factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.name == "Big Lathe"
    assert row.factory_id == f2.id
    # Then 3
    rows = events_of(db, m1)
    assert len(rows) == 1
    # Then 4
    sp.rollback()
    assert snap(db, m1) == before_m1
    # Then 5
    assert snap(db, o1) == before_o1
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    assert count_rows(db, "work_order_events") == 0
    # Then 8
    spy.assert_not_called()


# [claude] MCM-U-136
def test_mcm_u_136__a_move_keeps_the_assignee_rows_and_the_assigned_to_text_of_a_moved(db, w1, u1, u2, f2, mk_machine, mk_order, mk_assignee):
    """MCM-U-136 — a move keeps the assignee rows and the assigned_to text of a moved order.
    Rules: `update_machine` R28"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="DRAFT", assigned_to="Rahim Uddin")
    as1 = mk_assignee(o1, u1)
    before_as1 = snap_before(db, as1)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    assert snap(db, as1) == before_as1
    # Then 3
    assert count_rows(db, "work_order_assignees") == 1
    # Then 4
    row = reread(db, o1)
    assert row.assigned_to == "Rahim Uddin"


# [claude] MCM-U-137
def test_mcm_u_137__a_section_only_change_by_the_user_already_stamped_writes_no_column_of(db, w1, u2, s1, s2, mk_machine, mk_link):
    """MCM-U-137 — a section-only change by the user already stamped writes no column of the machine, but the link and the event.
    Rules: `update_machine` R23, R24, R25"""
    m1 = mk_machine("M1", updated_by=u2.id, updated_at=T0)
    mk_link(m1, s1)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_section_id=s2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    assert result.factory_section_id == s2.id
    # Then 3
    row = reread(db, m1)
    assert row.updated_by == u2.id
    # Then 4
    row = reread(db, m1)
    assert row.updated_at == T0
    # Then 5
    rows = events_of(db, m1)
    assert len(rows) == 1
    # Then 6
    assert rows[0].event_type == "updated"
    assert rows[0].description == "Machine details updated"
    # Then 7
    assert rows[0].performed_by == u2.id
    assert rows[0].workspace_id == w1.id
    # Then 8
    assert rows[0].metadata_json == {"changes": [{"field": "factory_section_id", "label": "Section", "from_value": str(s1.id), "to_value": str(s2.id)}]}


# [claude] MCM-U-138
@pytest.mark.xfail(strict=True, reason="BUG-975: Open work orders stay in the old factory when their machine moves")
def test_mcm_u_138__an_open_order_not_in_the_machine_s_old_factory_still_moves(db, w1, u2, f2, fi, mk_machine, mk_order):
    """MCM-U-138 — an open order not in the machine's old factory still moves.
    Rules: `update_machine` R28 [BUG-975], R28e"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="DRAFT", factory_id=fi.id)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, o1)
    assert row.factory_id == f2.id
    # Then 3
    row = reread(db, o1)
    assert row.updated_by == u2.id
    # Then 4
    rows = wo_events(db, o1)
    assert len(rows) == 1
    # Then 5
    assert wo_events(db, o1)[0].metadata_json["changes"][0]["to_value"] == str(f2.id)
    # Then 6
    assert wo_events(db, o1)[0].metadata_json["changes"][0]["from_value"] == str(fi.id)


# [claude] MCM-U-139
def test_mcm_u_139__a_production_line_keeps_its_factory_when_its_machine_moves(db, w1, u2, f1, f2, mk_machine):
    """MCM-U-139 — a production line keeps its factory when its machine moves.
    Rules: `update_machine` Side effects"""
    m1 = mk_machine("M1")
    pl1 = _add(db, ProductionLine(workspace_id=w1.id, factory_id=f1.id, name="Line One", machine_id=m1.id))
    before_pl1 = snap_before(db, pl1)
    result = M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.factory_id == f2.id
    # Then 3
    assert snap(db, pl1) == before_pl1
    # Then 4
    row = reread(db, pl1)
    assert row.factory_id == f1.id



# --------------------------------------------------------------------------- #
# get_machine
# --------------------------------------------------------------------------- #

# [claude] MCM-G-01
def test_mcm_g_01__a_live_machine_of_the_workspace_in_a_live_factory_is_returned(db, w1, mk_machine):
    """MCM-G-01 — a live machine of the workspace in a live factory is returned.
    Rules: `get_machine` R1, Returns"""
    m1 = mk_machine("M1")
    result = M.get_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == m1.id
    # Then 2
    assert result.name == "Lathe"


# [claude] MCM-G-02
def test_mcm_g_02__is_active_and_is_running_are_not_consulted(db, w1, mk_machine):
    """MCM-G-02 — is_active and is_running are not consulted.
    Rules: `get_machine` R1"""
    m1 = mk_machine("M1", is_active=False, is_running=True)
    result = M.get_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == m1.id
    # Then 2
    assert result.is_running is True


# [claude] MCM-G-03
def test_mcm_g_03__an_id_that_no_machine_has_gives_404(db, w1, mk_machine):
    """MCM-G-03 — an id that no machine has gives 404.
    Rules: `get_machine` R2, Errors row 1"""
    mk_machine("M1")

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_machine(db, machine_id=MISSING, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine with ID 999999999 not found"


# [claude] MCM-G-04
def test_mcm_g_04__a_machine_of_another_workspace_gives_404(db, w1, mk_machine):
    """MCM-G-04 — a machine of another workspace gives 404.
    Rules: `get_machine` R2, Errors row 1"""
    m9 = mk_machine("M9")

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_machine(db, machine_id=m9.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Machine with ID {m9.id} not found"


# [claude] MCM-G-05
@pytest.mark.xfail(strict=True, reason="BUG-955: `get_machine` returns soft-deleted machines")
def test_mcm_g_05__a_soft_deleted_machine_gives_404_by_default(db, w1, mk_machine):
    """MCM-G-05 — a soft-deleted machine gives 404 by default.
    Rules: `get_machine` R3 [BUG-955], Errors row 1"""
    mx = mk_machine("MX")

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_machine(db, machine_id=mx.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Machine with ID {mx.id} not found"


# [claude] MCM-G-06
@pytest.mark.xfail(strict=True, reason="BUG-955: `get_machine` returns soft-deleted machines")
def test_mcm_g_06__with_include_deleted_a_soft_deleted_machine_is_returned(db, w1, mk_machine):
    """MCM-G-06 — with include_deleted a soft-deleted machine is returned.
    Rules: `get_machine` R4 [BUG-955]"""
    mx = mk_machine("MX")
    result = M.get_machine(db, machine_id=mx.id, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert result.id == mx.id


# [claude] MCM-G-07
@pytest.mark.xfail(strict=True, reason="BUG-955: `get_machine` returns soft-deleted machines")
def test_mcm_g_07__with_include_deleted_a_soft_deleted_machine_of_another_workspace(db, w1, mk_machine):
    """MCM-G-07 — with include_deleted a soft-deleted machine of another workspace still gives 404.
    Rules: `get_machine` R4 [BUG-955], Errors row 1"""
    m9 = mk_machine("M9", is_deleted=True, is_active=False)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_machine(db, machine_id=m9.id, workspace_id=w1.id, include_deleted=True)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Machine with ID {m9.id} not found"


# [claude] MCM-G-08
@pytest.mark.xfail(strict=True, reason="BUG-966: A machine of a soft-deleted factory can still be opened by id")
def test_mcm_g_08__a_live_machine_of_a_soft_deleted_factory_gives_404_by_default(db, w1, mk_machine):
    """MCM-G-08 — a live machine of a soft-deleted factory gives 404 by default.
    Rules: `get_machine` R5 [BUG-966], Errors row 1"""
    mf = mk_machine("MF")

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_machine(db, machine_id=mf.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Machine with ID {mf.id} not found"


# [claude] MCM-G-09
@pytest.mark.xfail(strict=True, reason="BUG-966: A machine of a soft-deleted factory can still be opened by id")
def test_mcm_g_09__with_include_deleted_a_machine_of_a_soft_deleted_factory_is_returned(db, w1, mk_machine):
    """MCM-G-09 — with include_deleted a machine of a soft-deleted factory is returned.
    Rules: `get_machine` R5 [BUG-966]"""
    mf = mk_machine("MF")
    result = M.get_machine(db, machine_id=mf.id, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert result.id == mf.id


# [claude] MCM-G-10
def test_mcm_g_10__a_live_but_inactive_factory_hides_nothing(db, w1, mk_machine):
    """MCM-G-10 — a live but inactive factory hides nothing.
    Rules: `get_machine` R5"""
    mi = mk_machine("MI")
    result = M.get_machine(db, machine_id=mi.id, workspace_id=w1.id)

    # Then 1
    assert result.id == mi.id



# --------------------------------------------------------------------------- #
# search_machines
# --------------------------------------------------------------------------- #

# [claude] MCM-S-01
def test_mcm_s_01__with_defaults_the_list_holds_the_workspace_s_machines_in_name_order(db, w1, mk_machine):
    """MCM-S-01 — with defaults the list holds the workspace's machines in name order.
    Rules: `search_machines` R1, Returns"""
    mk_machine("MC")
    mk_machine("MA")
    mk_machine("MZ")
    result = M.search_machines(db, workspace_id=w1.id)

    # Then 1
    assert names(result) == ["Alpha", "Cobalt", "Zenith"]
    # Then 2
    assert isinstance(result, list)


# [claude] MCM-S-02
def test_mcm_s_02__factory_id_is_handed_to_the_list(db, w1, f2, mk_machine):
    """MCM-S-02 — factory_id is handed to the list.
    Rules: `search_machines` R1"""
    mk_machine("MA")
    mk_machine("MZ", factory_id=f2.id)
    result = M.search_machines(db, workspace_id=w1.id, factory_id=f2.id)

    # Then 1
    assert names(result) == ["Zenith"]


# [claude] MCM-S-03
def test_mcm_s_03__factory_section_id_is_handed_to_the_list_and_each_machine_reads_its(db, w1, s1, mk_machine, mk_link):
    """MCM-S-03 — factory_section_id is handed to the list, and each machine reads its section.
    Rules: `search_machines` R1, Returns"""
    ma = mk_machine("MA")
    mk_machine("MZ")
    mk_link(ma, s1)
    result = M.search_machines(db, workspace_id=w1.id, factory_section_id=s1.id)

    # Then 1
    assert names(result) == ["Alpha"]
    # Then 2
    assert result[0].factory_section_id == s1.id
    # Then 3
    assert result[0].factory_section_name == "Cutting"


# [claude] MCM-S-04
def test_mcm_s_04__is_running_is_handed_to_the_list(db, w1, mk_machine):
    """MCM-S-04 — is_running is handed to the list.
    Rules: `search_machines` R1"""
    mk_machine("MA", is_running=True)
    mk_machine("MZ")
    result = M.search_machines(db, workspace_id=w1.id, is_running=True)

    # Then 1
    assert names(result) == ["Alpha"]


# [claude] MCM-S-05
def test_mcm_s_05__search_is_handed_to_the_list(db, w1, mk_machine):
    """MCM-S-05 — search is handed to the list.
    Rules: `search_machines` R1"""
    mk_machine("MA")
    mk_machine("MZ")
    result = M.search_machines(db, workspace_id=w1.id, search="lph")

    # Then 1
    assert names(result) == ["Alpha"]


# [claude] MCM-S-06
def test_mcm_s_06__has_model_number_is_handed_to_the_list(db, w1, mk_machine):
    """MCM-S-06 — has_model_number is handed to the list.
    Rules: `search_machines` R1"""
    mk_machine("MA", model_number="L-200")
    mk_machine("MZ")
    result = M.search_machines(db, workspace_id=w1.id, has_model_number=True)

    # Then 1
    assert names(result) == ["Alpha"]


# [claude] MCM-S-07
def test_mcm_s_07__has_manufacturer_is_handed_to_the_list(db, w1, mk_machine):
    """MCM-S-07 — has_manufacturer is handed to the list.
    Rules: `search_machines` R1"""
    mk_machine("MA", manufacturer="Haas")
    mk_machine("MZ")
    result = M.search_machines(db, workspace_id=w1.id, has_manufacturer=False)

    # Then 1
    assert names(result) == ["Zenith"]


# [claude] MCM-S-08
def test_mcm_s_08__sort_by_created_at_is_handed_to_the_list(db, w1, mk_machine):
    """MCM-S-08 — sort_by created_at is handed to the list.
    Rules: `search_machines` R1"""
    mk_machine("MZ", created_at=T0)
    mk_machine("MA", created_at=T1)
    result = M.search_machines(db, workspace_id=w1.id, sort_by="created_at")

    # Then 1
    assert names(result) == ["Zenith", "Alpha"]


# [claude] MCM-S-09
def test_mcm_s_09__sort_dir_desc_is_handed_to_the_list(db, w1, mk_machine):
    """MCM-S-09 — sort_dir desc is handed to the list.
    Rules: `search_machines` R1"""
    mk_machine("MC")
    mk_machine("MA")
    mk_machine("MZ")
    result = M.search_machines(db, workspace_id=w1.id, sort_dir="desc")

    # Then 1
    assert names(result) == ["Zenith", "Cobalt", "Alpha"]


# [claude] MCM-S-10
def test_mcm_s_10__skip_and_limit_are_handed_to_the_list(db, w1, mk_machine):
    """MCM-S-10 — skip and limit are handed to the list.
    Rules: `search_machines` R1"""
    mk_machine("MC")
    mk_machine("MA")
    mk_machine("MZ")
    result = M.search_machines(db, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert names(result) == ["Cobalt"]


# [claude] MCM-S-11
def test_mcm_s_11__the_default_limit_on_the_list_path_is_100(db, w1, bulk):
    """MCM-S-11 — the default limit on the list path is 100.
    Rules: `search_machines` R1"""
    bulk(101, "P")
    result = M.search_machines(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100


# [claude] MCM-S-12
def test_mcm_s_12__latest_event_type_is_handed_to_the_list(db, w1, mk_machine, mk_status_row):
    """MCM-S-12 — latest_event_type is handed to the list.
    Rules: `search_machines` R1 [BUG-886]"""
    ma = mk_machine("MA")
    mz = mk_machine("MZ")
    mk_status_row(ma, T1, "IDLE")
    mk_status_row(mz, T1, "RUNNING")
    result = M.search_machines(db, workspace_id=w1.id, latest_event_type=IDLE)

    # Then 1
    assert names(result) == ["Alpha"]


# [claude] MCM-S-13
def test_mcm_s_13__search_text_is_literal_through_the_list(db, w1, mk_machine):
    """MCM-S-13 — search text is literal through the list.
    Rules: `search_machines` R1 [BUG-888]"""
    mk_machine("MA", model_number="50%")
    mk_machine("MZ")
    result = M.search_machines(db, workspace_id=w1.id, search="%")

    # Then 1
    assert names(result) == ["Alpha"]


# [claude] MCM-S-14
def test_mcm_s_14__search_text_is_trimmed_through_the_list(db, w1, mk_machine):
    """MCM-S-14 — search text is trimmed through the list.
    Rules: `search_machines` R1 [BUG-892]"""
    mk_machine("MA")
    mk_machine("MZ")
    result = M.search_machines(db, workspace_id=w1.id, search=" alpha ")

    # Then 1
    assert names(result) == ["Alpha"]


# [claude] MCM-S-15
def test_mcm_s_15__a_negative_limit_fails_in_the_database_on_the_list_path(db, w1, mk_machine):
    """MCM-S-15 — a negative limit fails in the database on the list path.
    Rules: `search_machines` R2, Errors row 1"""
    mk_machine("MA")

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            M.search_machines(db, workspace_id=w1.id, limit=-1)
    # Then 2
    assert "LIMIT must not be negative" in str(exc.value.orig)


# [claude] MCM-S-16
def test_mcm_s_16__a_negative_skip_fails_in_the_database_on_the_list_path(db, w1, mk_machine):
    """MCM-S-16 — a negative skip fails in the database on the list path.
    Rules: `search_machines` R2, Errors row 1"""
    mk_machine("MA")

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            M.search_machines(db, workspace_id=w1.id, skip=-1)
    # Then 2
    assert "OFFSET must not be negative" in str(exc.value.orig)


# [claude] MCM-S-17
def test_mcm_s_17__another_workspace_s_machines_are_never_returned_on_the_list_path(db, w1, mk_machine):
    """MCM-S-17 — another workspace's machines are never returned on the list path.
    Rules: `search_machines` R3, R4"""
    mk_machine("MA")
    mk_machine("M9")
    result = M.search_machines(db, workspace_id=w1.id)

    # Then 1
    assert names(result) == ["Alpha"]


# [claude] MCM-S-18
def test_mcm_s_18__soft_deleted_machines_are_never_returned_on_the_list_path(db, w1, mk_machine):
    """MCM-S-18 — soft-deleted machines are never returned on the list path.
    Rules: `search_machines` R3"""
    mk_machine("MA")
    mk_machine("MX")
    result = M.search_machines(db, workspace_id=w1.id)

    # Then 1
    assert names(result) == ["Alpha"]


# [claude] MCM-S-19
def test_mcm_s_19__a_machine_of_a_soft_deleted_factory_is_hidden_on_the_list_path(db, w1, mk_machine):
    """MCM-S-19 — a machine of a soft-deleted factory is hidden on the list path.
    Rules: `search_machines` R3 [BUG-890]"""
    mk_machine("MA")
    mk_machine("MF")
    result = M.search_machines(db, workspace_id=w1.id)

    # Then 1
    assert names(result) == ["Alpha"]


# [claude] MCM-S-20
def test_mcm_s_20__a_machine_of_a_live_but_inactive_factory_is_listed_on_the_list_path(db, w1, mk_machine):
    """MCM-S-20 — a machine of a live but inactive factory is listed on the list path.
    Rules: `search_machines` R3"""
    mk_machine("MA")
    mk_machine("MI")
    result = M.search_machines(db, workspace_id=w1.id)

    # Then 1
    assert names(result) == ["Alpha", "Mixer"]


# [claude] MCM-S-21
def test_mcm_s_21__an_unknown_workspace_gives_an_empty_list_on_the_list_path(db, mk_machine):
    """MCM-S-21 — an unknown workspace gives an empty list on the list path.
    Rules: `search_machines` R4"""
    mk_machine("MA")
    result = M.search_machines(db, workspace_id=MISSING)

    # Then 1
    assert result == []


# [claude] MCM-S-22
def test_mcm_s_22__a_workspace_without_machines_gives_an_empty_list_on_the_list_path(db, w2, mk_machine):
    """MCM-S-22 — a workspace without machines gives an empty list on the list path.
    Rules: `search_machines` R4"""
    mk_machine("MA")
    result = M.search_machines(db, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] MCM-S-23
def test_mcm_s_23__is_active_is_not_consulted_on_the_list_path(db, w1, mk_machine):
    """MCM-S-23 — is_active is not consulted on the list path.
    Rules: `search_machines` R4"""
    mk_machine("MA", is_active=False)
    mk_machine("MZ", is_running=True)
    result = M.search_machines(db, workspace_id=w1.id)

    # Then 1
    assert names(result) == ["Alpha", "Zenith"]


# [claude] MCM-S-24
def test_mcm_s_24__another_workspace_s_machines_are_never_returned_on_the_maintenance(db, w1, mk_machine):
    """MCM-S-24 — another workspace's machines are never returned on the maintenance path.
    Rules: `search_machines` R3, R4, R14"""
    mk_machine("MA")
    mk_machine("M9")
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="bogus")

    # Then 1
    assert names(result) == ["Alpha"]


# [claude] MCM-S-25
def test_mcm_s_25__soft_deleted_machines_are_never_returned_on_the_maintenance_path(db, w1, mk_machine):
    """MCM-S-25 — soft-deleted machines are never returned on the maintenance path.
    Rules: `search_machines` R3, R14"""
    mk_machine("MA")
    mk_machine("MX")
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="bogus")

    # Then 1
    assert names(result) == ["Alpha"]


# [claude] MCM-S-26
def test_mcm_s_26__a_machine_of_a_soft_deleted_factory_is_hidden_on_the_maintenance_path(db, w1, mk_machine):
    """MCM-S-26 — a machine of a soft-deleted factory is hidden on the maintenance path.
    Rules: `search_machines` R3 [BUG-890]"""
    mk_machine("MA")
    mk_machine("MF")
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="bogus")

    # Then 1
    assert names(result) == ["Alpha"]


# [claude] MCM-S-27
def test_mcm_s_27__a_machine_of_a_live_but_inactive_factory_is_listed_on_the_maintenance(db, w1, mk_machine):
    """MCM-S-27 — a machine of a live but inactive factory is listed on the maintenance path.
    Rules: `search_machines` R3, R14"""
    mk_machine("MA")
    mk_machine("MI")
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="bogus")

    # Then 1
    assert names(result) == ["Alpha", "Mixer"]


# [claude] MCM-S-28
def test_mcm_s_28__an_unknown_workspace_gives_an_empty_list_on_the_maintenance_path(db, mk_machine):
    """MCM-S-28 — an unknown workspace gives an empty list on the maintenance path.
    Rules: `search_machines` R4, R5"""
    mk_machine("MA")
    result = M.search_machines(db, workspace_id=MISSING, maintenance_window="bogus")

    # Then 1
    assert result == []


# [claude] MCM-S-29
def test_mcm_s_29__a_workspace_without_machines_gives_an_empty_list_on_the_maintenance(db, w2, mk_machine):
    """MCM-S-29 — a workspace without machines gives an empty list on the maintenance path.
    Rules: `search_machines` R4, R5"""
    mk_machine("MA")
    result = M.search_machines(db, workspace_id=w2.id, maintenance_window="bogus")

    # Then 1
    assert result == []


# [claude] MCM-S-30
def test_mcm_s_30__is_active_is_not_consulted_on_the_maintenance_path(db, w1, mk_machine):
    """MCM-S-30 — is_active is not consulted on the maintenance path.
    Rules: `search_machines` R4, R14"""
    mk_machine("MA", is_active=False)
    mk_machine("MZ", is_running=True)
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="bogus")

    # Then 1
    assert names(result) == ["Alpha", "Zenith"]


# [claude] MCM-S-31
def test_mcm_s_31__a_machine_with_a_left_over_link_to_a_deleted_section_stays_listed(db, w1, sx, mk_machine, mk_link):
    """MCM-S-31 — a machine with a left-over link to a deleted section stays listed without a section filter.
    Rules: `search_machines` R3"""
    ma = mk_machine("MA")
    mk_link(ma, sx)
    result = M.search_machines(db, workspace_id=w1.id)

    # Then 1
    assert names(result) == ["Alpha"]


# [claude] MCM-S-32
def test_mcm_s_32__the_id_of_a_soft_deleted_section_finds_nothing(db, w1, sx, mk_machine, mk_link):
    """MCM-S-32 — the id of a soft-deleted section finds nothing.
    Rules: `search_machines` R3 [BUG-889]"""
    ma = mk_machine("MA")
    mk_link(ma, sx)
    result = M.search_machines(db, workspace_id=w1.id, factory_section_id=sx.id)

    # Then 1
    assert result == []


# [claude] MCM-S-33
def test_mcm_s_33__window_all_with_the_maintenance_sort_filters_nothing(db, w1, mk_machine, mk_order):
    """MCM-S-33 — window "all" with the maintenance sort filters nothing.
    Rules: `search_machines` R5, R16"""
    mk_machine("MA")
    mz = mk_machine("MZ")
    mk_order(mz, "O1", status="DRAFT", planned_date=D(3))
    result = M.search_machines(db, workspace_id=w1.id, sort_by="maintenance_date")

    # Then 1
    assert names(result) == ["Zenith", "Alpha"]


# [claude] MCM-S-34
def test_mcm_s_34__filters_are_applied_before_the_window(db, w1, f2, mk_machine, mk_order):
    """MCM-S-34 — filters are applied before the window.
    Rules: `search_machines` R5"""
    ma = mk_machine("MA")
    mz = mk_machine("MZ", factory_id=f2.id)
    mk_order(ma, "O1", status="DRAFT", planned_date=D(3))
    mk_order(mz, "O2", status="DRAFT", planned_date=D(3), factory_id=f2.id)
    result = M.search_machines(db, workspace_id=w1.id, factory_id=f2.id, maintenance_window="next_7_days")

    # Then 1
    assert names(result) == ["Zenith"]


# [claude] MCM-S-35
def test_mcm_s_35__every_list_filter_holds_on_the_maintenance_path_each_wrong_machine(db, w1, f1, f2, s1, mk_machine, mk_link):
    """MCM-S-35 — every list filter holds on the maintenance path, each wrong machine failing exactly one.
    Rules: `search_machines` R5"""
    ma = mk_machine("MA", is_running=True, model_number="L-200", manufacturer="Haas")
    mb = mk_machine("MB", name="Basalt", factory_id=f2.id, is_running=True, model_number="L-200", manufacturer="Haas")
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
    result = M.search_machines(db, workspace_id=w1.id, factory_id=f1.id, factory_section_id=s1.id, is_running=True, search="a", has_model_number=True, has_manufacturer=True, maintenance_window="bogus")

    # Then 1
    assert names(result) == ["Alpha"]


# [claude] MCM-S-36
def test_mcm_s_36__the_list_order_by_name_is_kept_on_the_maintenance_path(db, w1, mk_machine):
    """MCM-S-36 — the list order by name is kept on the maintenance path.
    Rules: `search_machines` R6, R14"""
    mk_machine("MC")
    mk_machine("MA")
    mk_machine("MZ")
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="bogus")

    # Then 1
    assert names(result) == ["Alpha", "Cobalt", "Zenith"]


# [claude] MCM-S-37
def test_mcm_s_37__descending_name_order_is_kept_on_the_maintenance_path(db, w1, mk_machine):
    """MCM-S-37 — descending name order is kept on the maintenance path.
    Rules: `search_machines` R6, R14"""
    mk_machine("MC")
    mk_machine("MA")
    mk_machine("MZ")
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="bogus", sort_dir="desc")

    # Then 1
    assert names(result) == ["Zenith", "Cobalt", "Alpha"]


# [claude] MCM-S-38
def test_mcm_s_38__created_at_order_is_kept_on_the_maintenance_path(db, w1, mk_machine):
    """MCM-S-38 — created_at order is kept on the maintenance path.
    Rules: `search_machines` R6, R14"""
    mk_machine("MZ", created_at=T0)
    mk_machine("MA", created_at=T1)
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="bogus", sort_by="created_at")

    # Then 1
    assert names(result) == ["Zenith", "Alpha"]


# [claude] MCM-S-39
def test_mcm_s_39__latest_event_type_works_on_the_maintenance_path(db, w1, mk_machine, mk_status_row):
    """MCM-S-39 — latest_event_type works on the maintenance path.
    Rules: `search_machines` R6 [BUG-886], Errors row 2"""
    ma = mk_machine("MA")
    mz = mk_machine("MZ")
    mk_status_row(ma, T1, "IDLE")
    mk_status_row(mz, T1, "RUNNING")
    result = M.search_machines(db, workspace_id=w1.id, latest_event_type=IDLE, maintenance_window="bogus")

    # Then 1
    assert names(result) == ["Alpha"]


# [claude] MCM-S-40
@pytest.mark.xfail(strict=True, reason="BUG-958: Maintenance filter and sort only look at the first 10 000 machines")
def test_mcm_s_40__the_filter_finds_a_machine_past_the_first_10_000(db, w1, bulk, mk_order):
    """MCM-S-40 — the filter finds a machine past the first 10 000.
    Rules: `search_machines` R7 [BUG-958]"""
    bulk(10001, "B")
    mk_order(machine_named(db, "B10000"), "O1", status="DRAFT", planned_date=D(1))
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="next_7_days")

    # Then 1
    assert names(result) == ["B10000"]


# [claude] MCM-S-41
@pytest.mark.xfail(strict=True, reason="BUG-958: Maintenance filter and sort only look at the first 10 000 machines")
def test_mcm_s_41__the_maintenance_sort_sees_a_machine_past_the_first_10_000(db, w1, bulk, mk_order):
    """MCM-S-41 — the maintenance sort sees a machine past the first 10 000.
    Rules: `search_machines` R7 [BUG-958]"""
    bulk(10001, "B")
    mk_order(machine_named(db, "B10000"), "O1", status="DRAFT", planned_date=D(1))
    result = M.search_machines(db, workspace_id=w1.id, sort_by="maintenance_date", limit=1)

    # Then 1
    assert names(result) == ["B10000"]


# [claude] MCM-S-42
def test_mcm_s_42__the_machine_at_place_10_000_is_found(db, w1, bulk, mk_order):
    """MCM-S-42 — the machine at place 10 000 is found.
    Rules: `search_machines` R7"""
    bulk(10000, "B")
    mk_order(machine_named(db, "B09999"), "O1", status="DRAFT", planned_date=D(1))
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="next_7_days")

    # Then 1
    assert names(result) == ["B09999"]


# [claude] MCM-S-43
def test_mcm_s_43__a_completed_order_gives_no_work_date(db, w1, mk_machine, mk_order):
    """MCM-S-43 — a completed order gives no work date.
    Rules: `search_machines` R8"""
    ma = mk_machine("MA")
    mk_machine("MZ")
    mk_order(ma, "O1", status="COMPLETED", planned_date=D(3))
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="next_7_days")

    # Then 1
    assert names(result) == []


# [claude] MCM-S-44
def test_mcm_s_44__a_voided_order_gives_no_work_date(db, w1, mk_machine, mk_order):
    """MCM-S-44 — a voided order gives no work date.
    Rules: `search_machines` R8"""
    ma = mk_machine("MA")
    mk_machine("MZ")
    mk_order(ma, "O1", status="VOIDED", planned_date=D(3))
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="next_7_days")

    # Then 1
    assert names(result) == []


# [claude] MCM-S-45
def test_mcm_s_45__a_soft_deleted_order_gives_no_work_date(db, w1, mk_machine, mk_order):
    """MCM-S-45 — a soft-deleted order gives no work date.
    Rules: `search_machines` R8"""
    ma = mk_machine("MA")
    mk_machine("MZ")
    mk_order(ma, "O1", status="DRAFT", planned_date=D(3), is_deleted=True)
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="next_7_days")

    # Then 1
    assert names(result) == []


# [claude] MCM-S-46
def test_mcm_s_46__an_order_without_a_date_gives_no_work_date(db, w1, mk_machine, mk_order):
    """MCM-S-46 — an order without a date gives no work date.
    Rules: `search_machines` R8, R13"""
    ma = mk_machine("MA")
    mk_machine("MZ")
    mk_order(ma, "O1", status="DRAFT")
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="none_scheduled")

    # Then 1
    assert names(result) == ["Alpha", "Zenith"]


# [claude] MCM-S-47
def test_mcm_s_47__another_workspace_s_order_gives_no_work_date(db, w1, w2, f9, wt9, mk_machine, mk_order):
    """MCM-S-47 — another workspace's order gives no work date.
    Rules: `search_machines` R8"""
    ma = mk_machine("MA")
    mk_machine("MZ")
    mk_order(ma, "O1", status="DRAFT", planned_date=D(3), workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="next_7_days")

    # Then 1
    assert names(result) == []


# [claude] MCM-S-48
def test_mcm_s_48__work_at_today_365_counts_as_scheduled(db, w1, mk_machine, mk_order):
    """MCM-S-48 — work at today + 365 counts as scheduled.
    Rules: `search_machines` R9, R13"""
    ma = mk_machine("MA")
    mk_machine("MZ")
    mk_order(ma, "O1", status="DRAFT", planned_date=D(365))
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="none_scheduled")

    # Then 1
    assert names(result) == ["Zenith"]


# [claude] MCM-S-49
@pytest.mark.xfail(strict=True, reason="BUG-973: Maintenance filter only sees 10 years back and 1 year ahead")
def test_mcm_s_49__work_at_today_366_counts_as_scheduled(db, w1, mk_machine, mk_order):
    """MCM-S-49 — work at today + 366 counts as scheduled.
    Rules: `search_machines` R9 [BUG-973], R13"""
    ma = mk_machine("MA")
    mk_machine("MZ")
    mk_order(ma, "O1", status="DRAFT", planned_date=D(366))
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="none_scheduled")

    # Then 1
    assert names(result) == ["Zenith"]


# [claude] MCM-S-50
@pytest.mark.xfail(strict=True, reason="BUG-973: Maintenance filter only sees 10 years back and 1 year ahead")
def test_mcm_s_50__work_at_today_800_counts_as_scheduled(db, w1, mk_machine, mk_order):
    """MCM-S-50 — work at today + 800 counts as scheduled.
    Rules: `search_machines` R9 [BUG-973], R13"""
    ma = mk_machine("MA")
    mk_machine("MZ")
    mk_order(ma, "O1", status="DRAFT", planned_date=D(800))
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="none_scheduled")

    # Then 1
    assert names(result) == ["Zenith"]


# [claude] MCM-S-51
def test_mcm_s_51__in_progress_work_at_today_3650_is_overdue(db, w1, mk_machine, mk_order):
    """MCM-S-51 — in-progress work at today - 3650 is overdue.
    Rules: `search_machines` R9, R10"""
    ma = mk_machine("MA")
    mk_machine("MZ")
    mk_order(ma, "O1", status="IN_PROGRESS", planned_date=D(-3650))
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="overdue")

    # Then 1
    assert names(result) == ["Alpha"]


# [claude] MCM-S-52
@pytest.mark.xfail(strict=True, reason="BUG-973: Maintenance filter only sees 10 years back and 1 year ahead")
def test_mcm_s_52__in_progress_work_at_today_3651_is_overdue(db, w1, mk_machine, mk_order):
    """MCM-S-52 — in-progress work at today - 3651 is overdue.
    Rules: `search_machines` R9 [BUG-973], R10"""
    ma = mk_machine("MA")
    mk_machine("MZ")
    mk_order(ma, "O1", status="IN_PROGRESS", planned_date=D(-3651))
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="overdue")

    # Then 1
    assert names(result) == ["Alpha"]


# [claude] MCM-S-53
def test_mcm_s_53__the_maintenance_sort_uses_a_date_at_today_365(db, w1, mk_machine, mk_order):
    """MCM-S-53 — the maintenance sort uses a date at today + 365.
    Rules: `search_machines` R9, R16"""
    mk_machine("MA")
    mz = mk_machine("MZ")
    mk_order(mz, "O1", status="DRAFT", planned_date=D(365))
    result = M.search_machines(db, workspace_id=w1.id, sort_by="maintenance_date")

    # Then 1
    assert names(result) == ["Zenith", "Alpha"]


# [claude] MCM-S-54
@pytest.mark.xfail(strict=True, reason="BUG-973: Maintenance filter only sees 10 years back and 1 year ahead")
def test_mcm_s_54__the_maintenance_sort_uses_a_date_at_today_366(db, w1, mk_machine, mk_order):
    """MCM-S-54 — the maintenance sort uses a date at today + 366.
    Rules: `search_machines` R9 [BUG-973], R16"""
    mk_machine("MA")
    mz = mk_machine("MZ")
    mk_order(mz, "O1", status="DRAFT", planned_date=D(366))
    result = M.search_machines(db, workspace_id=w1.id, sort_by="maintenance_date")

    # Then 1
    assert names(result) == ["Zenith", "Alpha"]


# [claude] MCM-S-55
def test_mcm_s_55__an_in_progress_order_dated_yesterday_is_overdue(db, w1, mk_machine, mk_order):
    """MCM-S-55 — an IN_PROGRESS order dated yesterday is overdue.
    Rules: `search_machines` R10, R15"""
    ma = mk_machine("MA")
    mk_machine("MZ")
    mk_order(ma, "O1", status="IN_PROGRESS", planned_date=D(-1))
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="overdue")

    # Then 1
    assert names(result) == ["Alpha"]


# [claude] MCM-S-56
def test_mcm_s_56__a_draft_dated_yesterday_is_not_overdue(db, w1, mk_machine, mk_order):
    """MCM-S-56 — a DRAFT dated yesterday is not overdue.
    Rules: `search_machines` R10"""
    ma = mk_machine("MA")
    mk_machine("MZ")
    mk_order(ma, "O1", status="DRAFT", planned_date=D(-1))
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="overdue")

    # Then 1
    assert names(result) == []


# [claude] MCM-S-57
def test_mcm_s_57__an_in_progress_order_dated_today_is_not_overdue(db, w1, mk_machine, mk_order):
    """MCM-S-57 — an IN_PROGRESS order dated today is not overdue.
    Rules: `search_machines` R10, R15"""
    ma = mk_machine("MA")
    mk_machine("MZ")
    mk_order(ma, "O1", status="IN_PROGRESS", planned_date=D(0))
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="overdue")

    # Then 1
    assert names(result) == []


# [claude] MCM-S-58
def test_mcm_s_58__an_in_progress_order_dated_tomorrow_is_not_overdue(db, w1, mk_machine, mk_order):
    """MCM-S-58 — an IN_PROGRESS order dated tomorrow is not overdue.
    Rules: `search_machines` R10"""
    ma = mk_machine("MA")
    mk_machine("MZ")
    mk_order(ma, "O1", status="IN_PROGRESS", planned_date=D(1))
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="overdue")

    # Then 1
    assert names(result) == []


# [claude] MCM-S-59
def test_mcm_s_59__work_dated_today_is_in_next_7_days(db, w1, mk_machine, mk_order):
    """MCM-S-59 — work dated today is in next_7_days.
    Rules: `search_machines` R11, R15"""
    ma = mk_machine("MA")
    mk_machine("MZ")
    mk_order(ma, "O1", status="DRAFT", planned_date=D(0))
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="next_7_days")

    # Then 1
    assert names(result) == ["Alpha"]


# [claude] MCM-S-60
def test_mcm_s_60__work_dated_today_7_is_in_next_7_days(db, w1, mk_machine, mk_order):
    """MCM-S-60 — work dated today + 7 is in next_7_days.
    Rules: `search_machines` R11"""
    ma = mk_machine("MA")
    mk_machine("MZ")
    mk_order(ma, "O1", status="DRAFT", planned_date=D(7))
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="next_7_days")

    # Then 1
    assert names(result) == ["Alpha"]


# [claude] MCM-S-61
def test_mcm_s_61__work_dated_today_8_is_not_in_next_7_days(db, w1, mk_machine, mk_order):
    """MCM-S-61 — work dated today + 8 is not in next_7_days.
    Rules: `search_machines` R11"""
    ma = mk_machine("MA")
    mk_machine("MZ")
    mk_order(ma, "O1", status="DRAFT", planned_date=D(8))
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="next_7_days")

    # Then 1
    assert names(result) == []


# [claude] MCM-S-62
def test_mcm_s_62__work_dated_yesterday_is_not_in_next_7_days(db, w1, mk_machine, mk_order):
    """MCM-S-62 — work dated yesterday is not in next_7_days.
    Rules: `search_machines` R11"""
    ma = mk_machine("MA")
    mk_machine("MZ")
    mk_order(ma, "O1", status="DRAFT", planned_date=D(-1))
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="next_7_days")

    # Then 1
    assert names(result) == []


# [claude] MCM-S-63
def test_mcm_s_63__in_progress_work_dated_today_3_is_in_next_7_days(db, w1, mk_machine, mk_order):
    """MCM-S-63 — IN_PROGRESS work dated today + 3 is in next_7_days.
    Rules: `search_machines` R11, R8"""
    ma = mk_machine("MA")
    mk_machine("MZ")
    mk_order(ma, "O1", status="IN_PROGRESS", planned_date=D(3))
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="next_7_days")

    # Then 1
    assert names(result) == ["Alpha"]


# [claude] MCM-S-64
def test_mcm_s_64__work_dated_today_is_in_next_30_days(db, w1, mk_machine, mk_order):
    """MCM-S-64 — work dated today is in next_30_days.
    Rules: `search_machines` R12, R15"""
    ma = mk_machine("MA")
    mk_machine("MZ")
    mk_order(ma, "O1", status="DRAFT", planned_date=D(0))
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="next_30_days")

    # Then 1
    assert names(result) == ["Alpha"]


# [claude] MCM-S-65
def test_mcm_s_65__work_dated_today_30_is_in_next_30_days(db, w1, mk_machine, mk_order):
    """MCM-S-65 — work dated today + 30 is in next_30_days.
    Rules: `search_machines` R12"""
    ma = mk_machine("MA")
    mk_machine("MZ")
    mk_order(ma, "O1", status="DRAFT", planned_date=D(30))
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="next_30_days")

    # Then 1
    assert names(result) == ["Alpha"]


# [claude] MCM-S-66
def test_mcm_s_66__work_dated_today_31_is_not_in_next_30_days(db, w1, mk_machine, mk_order):
    """MCM-S-66 — work dated today + 31 is not in next_30_days.
    Rules: `search_machines` R12"""
    ma = mk_machine("MA")
    mk_machine("MZ")
    mk_order(ma, "O1", status="DRAFT", planned_date=D(31))
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="next_30_days")

    # Then 1
    assert names(result) == []


# [claude] MCM-S-67
def test_mcm_s_67__work_dated_yesterday_is_not_in_next_30_days(db, w1, mk_machine, mk_order):
    """MCM-S-67 — work dated yesterday is not in next_30_days.
    Rules: `search_machines` R12"""
    ma = mk_machine("MA")
    mk_machine("MZ")
    mk_order(ma, "O1", status="DRAFT", planned_date=D(-1))
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="next_30_days")

    # Then 1
    assert names(result) == []


# [claude] MCM-S-68
def test_mcm_s_68__in_progress_work_dated_today_3_is_in_next_30_days(db, w1, mk_machine, mk_order):
    """MCM-S-68 — IN_PROGRESS work dated today + 3 is in next_30_days.
    Rules: `search_machines` R12, R8"""
    ma = mk_machine("MA")
    mk_machine("MZ")
    mk_order(ma, "O1", status="IN_PROGRESS", planned_date=D(3))
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="next_30_days")

    # Then 1
    assert names(result) == ["Alpha"]


# [claude] MCM-S-69
def test_mcm_s_69__an_overdue_machine_with_a_date_in_the_window_qualifies(db, w1, mk_machine, mk_order):
    """MCM-S-69 — an overdue machine with a date in the window qualifies.
    Rules: `search_machines` R11"""
    ma = mk_machine("MA")
    mk_machine("MZ")
    mk_order(ma, "O1", status="IN_PROGRESS", planned_date=D(-5))
    mk_order(ma, "O2", status="DRAFT", planned_date=D(3))
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="next_7_days")

    # Then 1
    assert names(result) == ["Alpha"]


# [claude] MCM-S-70
def test_mcm_s_70__a_machine_with_work_tomorrow_is_not_without_schedule(db, w1, mk_machine, mk_order):
    """MCM-S-70 — a machine with work tomorrow is not without schedule.
    Rules: `search_machines` R13"""
    ma = mk_machine("MA")
    mk_machine("MZ")
    mk_order(ma, "O1", status="DRAFT", planned_date=D(1))
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="none_scheduled")

    # Then 1
    assert names(result) == ["Zenith"]


# [claude] MCM-S-71
def test_mcm_s_71__a_machine_with_work_today_is_not_without_schedule(db, w1, mk_machine, mk_order):
    """MCM-S-71 — a machine with work today is not without schedule.
    Rules: `search_machines` R13, R15"""
    ma = mk_machine("MA")
    mk_machine("MZ")
    mk_order(ma, "O1", status="DRAFT", planned_date=D(0))
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="none_scheduled")

    # Then 1
    assert names(result) == ["Zenith"]


# [claude] MCM-S-72
def test_mcm_s_72__a_machine_with_only_past_open_work_is_without_schedule(db, w1, mk_machine, mk_order):
    """MCM-S-72 — a machine with only past open work is without schedule.
    Rules: `search_machines` R13"""
    ma = mk_machine("MA")
    mk_machine("MZ")
    mk_order(ma, "O1", status="DRAFT", planned_date=D(-1))
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="none_scheduled")

    # Then 1
    assert names(result) == ["Alpha", "Zenith"]


# [claude] MCM-S-73
def test_mcm_s_73__a_machine_with_past_and_future_work_is_scheduled(db, w1, mk_machine, mk_order):
    """MCM-S-73 — a machine with past and future work is scheduled.
    Rules: `search_machines` R13"""
    ma = mk_machine("MA")
    mk_machine("MZ")
    mk_order(ma, "O1", status="IN_PROGRESS", planned_date=D(-5))
    mk_order(ma, "O2", status="DRAFT", planned_date=D(2))
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="none_scheduled")

    # Then 1
    assert names(result) == ["Zenith"]


# [claude] MCM-S-74
def test_mcm_s_74__a_machine_without_any_order_is_without_schedule(db, w1, mk_machine):
    """MCM-S-74 — a machine without any order is without schedule.
    Rules: `search_machines` R13"""
    mk_machine("MA")
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="none_scheduled")

    # Then 1
    assert names(result) == ["Alpha"]


# [claude] MCM-S-75
def test_mcm_s_75__window_bogus_filters_nothing(db, w1, mk_machine, mk_order):
    """MCM-S-75 — window "bogus" filters nothing.
    Rules: `search_machines` R14"""
    ma = mk_machine("MA")
    mk_machine("MZ")
    mk_order(ma, "O1", status="DRAFT", planned_date=D(100))
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="bogus")

    # Then 1
    assert names(result) == ["Alpha", "Zenith"]


# [claude] MCM-S-76
def test_mcm_s_76__window_overdue_filters_nothing(db, w1, mk_machine, mk_order):
    """MCM-S-76 — window "OVERDUE" filters nothing.
    Rules: `search_machines` R14"""
    ma = mk_machine("MA")
    mk_machine("MZ")
    mk_order(ma, "O1", status="DRAFT", planned_date=D(100))
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="OVERDUE")

    # Then 1
    assert names(result) == ["Alpha", "Zenith"]


# [claude] MCM-S-77
def test_mcm_s_77__window_filters_nothing(db, w1, mk_machine, mk_order):
    """MCM-S-77 — window "" filters nothing.
    Rules: `search_machines` R14"""
    ma = mk_machine("MA")
    mk_machine("MZ")
    mk_order(ma, "O1", status="DRAFT", planned_date=D(100))
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="")

    # Then 1
    assert names(result) == ["Alpha", "Zenith"]


# [claude] MCM-S-78
def test_mcm_s_78__an_unknown_window_is_still_paged(db, w1, mk_machine):
    """MCM-S-78 — an unknown window is still paged.
    Rules: `search_machines` R14, R19"""
    mk_machine("MC")
    mk_machine("MA")
    mk_machine("MZ")
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="bogus", skip=1, limit=1)

    # Then 1
    assert names(result) == ["Cobalt"]


# [claude] MCM-S-79
def test_mcm_s_79__the_maintenance_sort_puts_the_earliest_date_first_and_machines(db, w1, mk_machine, mk_order):
    """MCM-S-79 — the maintenance sort puts the earliest date first and machines without one last.
    Rules: `search_machines` R16"""
    mk_machine("MA")
    mc = mk_machine("MC")
    mz = mk_machine("MZ")
    mk_order(mz, "O1", status="DRAFT", planned_date=D(2))
    mk_order(mc, "O2", status="IN_PROGRESS", planned_date=D(9))
    result = M.search_machines(db, workspace_id=w1.id, sort_by="maintenance_date")

    # Then 1
    assert names(result) == ["Zenith", "Cobalt", "Alpha"]


# [claude] MCM-S-80
def test_mcm_s_80__a_machine_s_earliest_future_date_decides(db, w1, mk_machine, mk_order):
    """MCM-S-80 — a machine's earliest future date decides.
    Rules: `search_machines` R16"""
    ma = mk_machine("MA")
    mz = mk_machine("MZ")
    mk_order(ma, "O1", status="DRAFT", planned_date=D(5))
    mk_order(mz, "O2", status="DRAFT", planned_date=D(9))
    mk_order(mz, "O3", status="DRAFT", planned_date=D(2))
    result = M.search_machines(db, workspace_id=w1.id, sort_by="maintenance_date")

    # Then 1
    assert names(result) == ["Zenith", "Alpha"]


# [claude] MCM-S-81
def test_mcm_s_81__past_dates_are_ignored_by_the_maintenance_sort(db, w1, mk_machine, mk_order):
    """MCM-S-81 — past dates are ignored by the maintenance sort.
    Rules: `search_machines` R16"""
    ma = mk_machine("MA")
    mz = mk_machine("MZ")
    mk_order(ma, "O1", status="DRAFT", planned_date=D(5))
    mk_order(mz, "O2", status="IN_PROGRESS", planned_date=D(-5))
    result = M.search_machines(db, workspace_id=w1.id, sort_by="maintenance_date")

    # Then 1
    assert names(result) == ["Alpha", "Zenith"]


# [claude] MCM-S-82
def test_mcm_s_82__a_date_equal_to_today_counts_for_the_maintenance_sort(db, w1, mk_machine, mk_order):
    """MCM-S-82 — a date equal to today counts for the maintenance sort.
    Rules: `search_machines` R16, R15"""
    ma = mk_machine("MA")
    mz = mk_machine("MZ")
    mk_order(ma, "O1", status="DRAFT", planned_date=D(1))
    mk_order(mz, "O2", status="DRAFT", planned_date=D(0))
    result = M.search_machines(db, workspace_id=w1.id, sort_by="maintenance_date")

    # Then 1
    assert names(result) == ["Zenith", "Alpha"]


# [claude] MCM-S-83
def test_mcm_s_83__ties_keep_name_order(db, w1, mk_machine, mk_order):
    """MCM-S-83 — ties keep name order.
    Rules: `search_machines` R16"""
    mz = mk_machine("MZ")
    ma = mk_machine("MA")
    mk_order(mz, "O1", status="DRAFT", planned_date=D(4))
    mk_order(ma, "O2", status="DRAFT", planned_date=D(4))
    result = M.search_machines(db, workspace_id=w1.id, sort_by="maintenance_date")

    # Then 1
    assert names(result) == ["Alpha", "Zenith"]


# [claude] MCM-S-84
def test_mcm_s_84__descending_puts_the_latest_first_and_machines_without_a_date_still(db, w1, mk_machine, mk_order):
    """MCM-S-84 — descending puts the latest first and machines without a date still last.
    Rules: `search_machines` R17"""
    mk_machine("MA")
    mc = mk_machine("MC")
    mz = mk_machine("MZ")
    mk_order(mz, "O1", status="DRAFT", planned_date=D(2))
    mk_order(mc, "O2", status="IN_PROGRESS", planned_date=D(9))
    result = M.search_machines(db, workspace_id=w1.id, sort_by="maintenance_date", sort_dir="desc")

    # Then 1
    assert names(result) == ["Cobalt", "Zenith", "Alpha"]


# [claude] MCM-S-85
def test_mcm_s_85__descending_ties_keep_name_order_ascending(db, w1, mk_machine, mk_order):
    """MCM-S-85 — descending ties keep name order ascending.
    Rules: `search_machines` R17"""
    mz = mk_machine("MZ")
    ma = mk_machine("MA")
    mk_machine("MC")
    mk_order(mz, "O1", status="DRAFT", planned_date=D(4))
    mk_order(ma, "O2", status="DRAFT", planned_date=D(4))
    result = M.search_machines(db, workspace_id=w1.id, sort_by="maintenance_date", sort_dir="desc")

    # Then 1
    assert names(result) == ["Alpha", "Zenith", "Cobalt"]


# [claude] MCM-S-86
def test_mcm_s_86__sort_dir_desc_sorts_ascending(db, w1, mk_machine, mk_order):
    """MCM-S-86 — sort_dir "DESC" sorts ascending.
    Rules: `search_machines` R17"""
    mk_machine("MA")
    mc = mk_machine("MC")
    mz = mk_machine("MZ")
    mk_order(mz, "O1", status="DRAFT", planned_date=D(2))
    mk_order(mc, "O2", status="IN_PROGRESS", planned_date=D(9))
    result = M.search_machines(db, workspace_id=w1.id, sort_by="maintenance_date", sort_dir="DESC")

    # Then 1
    assert names(result) == ["Zenith", "Cobalt", "Alpha"]


# [claude] MCM-S-87
def test_mcm_s_87__the_maintenance_sort_is_combined_with_a_window(db, w1, mk_machine, mk_order):
    """MCM-S-87 — the maintenance sort is combined with a window.
    Rules: `search_machines` R5, R16"""
    mk_machine("MA")
    mc = mk_machine("MC")
    mz = mk_machine("MZ")
    mk_order(mz, "O1", status="DRAFT", planned_date=D(2))
    mk_order(mc, "O2", status="IN_PROGRESS", planned_date=D(9))
    result = M.search_machines(db, workspace_id=w1.id, sort_by="maintenance_date", maintenance_window="next_7_days")

    # Then 1
    assert names(result) == ["Zenith"]


# [claude] MCM-S-88
def test_mcm_s_88__a_case_only_tie_on_the_maintenance_sort_falls_to_id(db, w1, f2, mk_machine):
    """MCM-S-88 — a case-only tie on the maintenance sort falls to id.
    Rules: `search_machines` R18 [BUG-887]"""
    mk_machine(name="Bolt")
    mk_machine(name="bolt", factory_id=f2.id)
    result = M.search_machines(db, workspace_id=w1.id, sort_by="maintenance_date")

    # Then 1
    assert names(result) == ["Bolt", "bolt"]


# [claude] MCM-S-89
def test_mcm_s_89__skip_and_limit_are_applied_last_on_the_maintenance_path(db, w1, mk_machine, mk_order):
    """MCM-S-89 — skip and limit are applied last on the maintenance path.
    Rules: `search_machines` R19"""
    ma = mk_machine("MA")
    mc = mk_machine("MC")
    mz = mk_machine("MZ")
    mb = mk_machine("MB")
    mk_order(ma, "O1", status="DRAFT", planned_date=D(3))
    mk_order(mc, "O2", status="DRAFT", planned_date=D(3))
    mk_order(mz, "O3", status="DRAFT", planned_date=D(3))
    mk_order(mb, "O4", status="DRAFT", planned_date=D(3))
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="next_7_days", skip=1, limit=2)

    # Then 1
    assert names(result) == ["Beryl", "Cobalt"]


# [claude] MCM-S-90
def test_mcm_s_90__limit_0_gives_an_empty_list_on_the_maintenance_path(db, w1, mk_machine):
    """MCM-S-90 — limit 0 gives an empty list on the maintenance path.
    Rules: `search_machines` R19"""
    mk_machine("MA")
    mk_machine("MZ")
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="bogus", limit=0)

    # Then 1
    assert result == []


# [claude] MCM-S-91
def test_mcm_s_91__limit_1_gives_one_row_on_the_maintenance_path(db, w1, mk_machine):
    """MCM-S-91 — limit 1 gives one row on the maintenance path.
    Rules: `search_machines` R19"""
    mk_machine("MA")
    mk_machine("MZ")
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="bogus", limit=1)

    # Then 1
    assert names(result) == ["Alpha"]


# [claude] MCM-S-92
def test_mcm_s_92__skip_at_the_end_gives_an_empty_list_on_the_maintenance_path(db, w1, mk_machine):
    """MCM-S-92 — skip at the end gives an empty list on the maintenance path.
    Rules: `search_machines` R19"""
    mk_machine("MA")
    mk_machine("MZ")
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="bogus", skip=2)

    # Then 1
    assert result == []


# [claude] MCM-S-93
def test_mcm_s_93__skip_one_before_the_end_gives_the_last_row(db, w1, mk_machine):
    """MCM-S-93 — skip one before the end gives the last row.
    Rules: `search_machines` R19"""
    mk_machine("MA")
    mk_machine("MZ")
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="bogus", skip=1)

    # Then 1
    assert names(result) == ["Zenith"]


# [claude] MCM-S-94
def test_mcm_s_94__the_default_limit_on_the_maintenance_path_is_100(db, w1, bulk):
    """MCM-S-94 — the default limit on the maintenance path is 100.
    Rules: `search_machines` R19"""
    bulk(101, "P")
    result = M.search_machines(db, workspace_id=w1.id, maintenance_window="bogus")

    # Then 1
    assert len(result) == 100


# [claude] MCM-S-95
def test_mcm_s_95__include_deleted_lists_deleted_machines_and_machines_of_deleted(db, w1, mk_machine):
    """MCM-S-95 — include_deleted lists deleted machines and machines of deleted factories with the live ones.
    Rules: `search_machines` R21"""
    ma = mk_machine("MA")
    mx = mk_machine("MX")
    mf = mk_machine("MF")
    result = M.search_machines(db, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert ids(result) == [ma.id, mx.id, mf.id]


# [claude] MCM-S-96
def test_mcm_s_96__include_deleted_stays_inside_the_workspace(db, w1, mk_machine):
    """MCM-S-96 — include_deleted stays inside the workspace.
    Rules: `search_machines` R21"""
    ma = mk_machine("MA")
    mk_machine("M9")
    result = M.search_machines(db, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert ids(result) == [ma.id]


# [claude] MCM-S-97
def test_mcm_s_97__include_deleted_applies_factory_id(db, w1, f2, mk_machine):
    """MCM-S-97 — include_deleted applies factory_id.
    Rules: `search_machines` R21"""
    mk_machine("MA")
    mx = mk_machine("MX", factory_id=f2.id)
    mz = mk_machine("MZ", factory_id=f2.id)
    result = M.search_machines(db, workspace_id=w1.id, include_deleted=True, factory_id=f2.id)

    # Then 1
    assert ids(result) == [mx.id, mz.id]


# [claude] MCM-S-98
def test_mcm_s_98__include_deleted_applies_factory_section_id(db, w1, s1, mk_machine, mk_link):
    """MCM-S-98 — include_deleted applies factory_section_id.
    Rules: `search_machines` R21"""
    mk_machine("MA")
    mz = mk_machine("MZ")
    mk_link(mz, s1)
    result = M.search_machines(db, workspace_id=w1.id, include_deleted=True, factory_section_id=s1.id)

    # Then 1
    assert ids(result) == [mz.id]


# [claude] MCM-S-99
def test_mcm_s_99__include_deleted_applies_is_running(db, w1, mk_machine):
    """MCM-S-99 — include_deleted applies is_running.
    Rules: `search_machines` R21"""
    mk_machine("MA")
    mz = mk_machine("MZ", is_running=True)
    result = M.search_machines(db, workspace_id=w1.id, include_deleted=True, is_running=True)

    # Then 1
    assert ids(result) == [mz.id]


# [claude] MCM-S-100
def test_mcm_s_100__include_deleted_applies_search(db, w1, mk_machine):
    """MCM-S-100 — include_deleted applies search.
    Rules: `search_machines` R21"""
    ma = mk_machine("MA")
    mk_machine("MZ")
    result = M.search_machines(db, workspace_id=w1.id, include_deleted=True, search="Alpha")

    # Then 1
    assert ids(result) == [ma.id]


# [claude] MCM-S-101
@pytest.mark.xfail(strict=True, reason="BUG-957: Machine list with deleted rows pages first, filters afterwards and ignores most parameters")
def test_mcm_s_101__include_deleted_applies_has_model_number(db, w1, mk_machine):
    """MCM-S-101 — include_deleted applies has_model_number.
    Rules: `search_machines` R21 [BUG-957]"""
    ma = mk_machine("MA", model_number="L-200")
    mk_machine("MZ")
    result = M.search_machines(db, workspace_id=w1.id, include_deleted=True, has_model_number=True)

    # Then 1
    assert ids(result) == [ma.id]


# [claude] MCM-S-102
@pytest.mark.xfail(strict=True, reason="BUG-957: Machine list with deleted rows pages first, filters afterwards and ignores most parameters")
def test_mcm_s_102__include_deleted_applies_has_manufacturer(db, w1, mk_machine):
    """MCM-S-102 — include_deleted applies has_manufacturer.
    Rules: `search_machines` R21 [BUG-957]"""
    ma = mk_machine("MA", manufacturer="Haas")
    mk_machine("MZ")
    result = M.search_machines(db, workspace_id=w1.id, include_deleted=True, has_manufacturer=True)

    # Then 1
    assert ids(result) == [ma.id]


# [claude] MCM-S-103
@pytest.mark.xfail(strict=True, reason="BUG-957: Machine list with deleted rows pages first, filters afterwards and ignores most parameters")
def test_mcm_s_103__include_deleted_applies_latest_event_type(db, w1, mk_machine, mk_status_row):
    """MCM-S-103 — include_deleted applies latest_event_type.
    Rules: `search_machines` R21 [BUG-957]"""
    ma = mk_machine("MA")
    mz = mk_machine("MZ")
    mk_status_row(ma, T1, "IDLE")
    mk_status_row(mz, T1, "RUNNING")
    result = M.search_machines(db, workspace_id=w1.id, include_deleted=True, latest_event_type="IDLE")

    # Then 1
    assert ids(result) == [ma.id]


# [claude] MCM-S-104
@pytest.mark.xfail(strict=True, reason="BUG-957: Machine list with deleted rows pages first, filters afterwards and ignores most parameters")
def test_mcm_s_104__include_deleted_applies_the_maintenance_window(db, w1, mk_machine, mk_order):
    """MCM-S-104 — include_deleted applies the maintenance window.
    Rules: `search_machines` R21 [BUG-957]"""
    ma = mk_machine("MA")
    mk_machine("MZ")
    mk_order(ma, "O1", status="DRAFT", planned_date=D(3))
    result = M.search_machines(db, workspace_id=w1.id, include_deleted=True, maintenance_window="next_7_days")

    # Then 1
    assert ids(result) == [ma.id]


# [claude] MCM-S-105
@pytest.mark.xfail(strict=True, reason="BUG-957: Machine list with deleted rows pages first, filters afterwards and ignores most parameters")
def test_mcm_s_105__with_include_deleted_a_deleted_machine_has_no_work_dates_in_a_window(db, w1, mk_machine, mk_order):
    """MCM-S-105 — with include_deleted a deleted machine has no work dates in a window.
    Rules: `search_machines` R21 [BUG-957], R8"""
    ma = mk_machine("MA")
    mx = mk_machine("MX")
    mk_order(ma, "O1", status="DRAFT", planned_date=D(3))
    mk_order(mx, "O2", status="DRAFT", planned_date=D(3))
    result = M.search_machines(db, workspace_id=w1.id, include_deleted=True, maintenance_window="next_7_days")

    # Then 1
    assert ids(result) == [ma.id]


# [claude] MCM-S-106
@pytest.mark.xfail(strict=True, reason="BUG-957: Machine list with deleted rows pages first, filters afterwards and ignores most parameters")
def test_mcm_s_106__with_include_deleted_a_deleted_machine_counts_as_without_schedule(db, w1, mk_machine, mk_order):
    """MCM-S-106 — with include_deleted a deleted machine counts as without schedule.
    Rules: `search_machines` R21 [BUG-957], R8"""
    ma = mk_machine("MA")
    mx = mk_machine("MX")
    mk_order(ma, "O1", status="DRAFT", planned_date=D(3))
    mk_order(mx, "O2", status="DRAFT", planned_date=D(3))
    result = M.search_machines(db, workspace_id=w1.id, include_deleted=True, maintenance_window="none_scheduled")

    # Then 1
    assert ids(result) == [mx.id]


# [claude] MCM-S-107
@pytest.mark.xfail(strict=False, reason="BUG-957: Machine list with deleted rows pages first, filters afterwards and ignores most parameters")
def test_mcm_s_107__include_deleted_sorts_by_name(db, w1, mk_machine):
    """MCM-S-107 — include_deleted sorts by name.
    Rules: `search_machines` R21 [BUG-957]"""
    mk_machine("MZ")
    mk_machine("MA")
    result = M.search_machines(db, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert names(result) == ["Alpha", "Zenith"]


# [claude] MCM-S-108
@pytest.mark.xfail(strict=False, reason="BUG-957: Machine list with deleted rows pages first, filters afterwards and ignores most parameters")
def test_mcm_s_108__include_deleted_honours_sort_dir(db, w1, mk_machine):
    """MCM-S-108 — include_deleted honours sort_dir.
    Rules: `search_machines` R21 [BUG-957]"""
    mk_machine("MA")
    mk_machine("MZ")
    result = M.search_machines(db, workspace_id=w1.id, include_deleted=True, sort_dir="desc")

    # Then 1
    assert names(result) == ["Zenith", "Alpha"]


# [claude] MCM-S-109
@pytest.mark.xfail(strict=False, reason="BUG-957: Machine list with deleted rows pages first, filters afterwards and ignores most parameters")
def test_mcm_s_109__include_deleted_honours_sort_by_created_at(db, w1, mk_machine):
    """MCM-S-109 — include_deleted honours sort_by created_at.
    Rules: `search_machines` R21 [BUG-957]"""
    mk_machine("MA", created_at=T1)
    mk_machine("MZ", created_at=T0)
    result = M.search_machines(db, workspace_id=w1.id, include_deleted=True, sort_by="created_at")

    # Then 1
    assert names(result) == ["Zenith", "Alpha"]


# [claude] MCM-S-110
@pytest.mark.xfail(strict=False, reason="BUG-957: Machine list with deleted rows pages first, filters afterwards and ignores most parameters")
def test_mcm_s_110__include_deleted_honours_the_maintenance_sort(db, w1, mk_machine, mk_order):
    """MCM-S-110 — include_deleted honours the maintenance sort.
    Rules: `search_machines` R21 [BUG-957]"""
    mk_machine("MA")
    mz = mk_machine("MZ")
    mk_order(mz, "O1", status="DRAFT", planned_date=D(3))
    result = M.search_machines(db, workspace_id=w1.id, include_deleted=True, sort_by="maintenance_date")

    # Then 1
    assert names(result) == ["Zenith", "Alpha"]


# [claude] MCM-S-111
@pytest.mark.xfail(strict=False, reason="BUG-957: Machine list with deleted rows pages first, filters afterwards and ignores most parameters")
def test_mcm_s_111__include_deleted_pages_after_filtering(db, w1, f2, mk_machine):
    """MCM-S-111 — include_deleted pages after filtering.
    Rules: `search_machines` R21 [BUG-957]"""
    mk_machine("MA")
    mk_machine("MB")
    mk_machine("MZ", factory_id=f2.id)
    result = M.search_machines(db, workspace_id=w1.id, include_deleted=True, factory_id=f2.id, limit=2)

    # Then 1
    assert names(result) == ["Zenith"]


# [claude] MCM-S-112
@pytest.mark.xfail(strict=True, reason="BUG-957: Machine list with deleted rows pages first, filters afterwards and ignores most parameters")
def test_mcm_s_112__the_include_deleted_query_orders_by_name_in_sql(db, w1, mk_machine):
    """MCM-S-112 — the include_deleted query orders by name in SQL.
    Rules: `search_machines` R21 [BUG-957]"""
    ma = mk_machine("MA")
    mx = mk_machine("MX")
    with record_sql(db) as sql_log:
        result = M.search_machines(db, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert ids(result) == [ma.id, mx.id]
    # Then 2
    assert any(re.search(r"FROM machines\b.*ORDER BY .*\bname\b", s, re.S) for s in sql_log)  # noqa: FURB167


# [claude] MCM-S-113
@pytest.mark.xfail(strict=True, reason="BUG-957: Machine list with deleted rows pages first, filters afterwards and ignores most parameters")
def test_mcm_s_113__with_include_deleted_a_live_machine_of_a_soft_deleted_factory_keeps(db, w1, fd, mk_machine, mk_order):
    """MCM-S-113 — with include_deleted a live machine of a soft-deleted factory keeps its work dates.
    Rules: `search_machines` R21 [BUG-957], R8"""
    mk_machine("MZ")
    mf = mk_machine("MF")
    mk_order(mf, "O1", status="DRAFT", planned_date=D(3), factory_id=fd.id)
    result = M.search_machines(db, workspace_id=w1.id, include_deleted=True, maintenance_window="next_7_days")

    # Then 1
    assert ids(result) == [mf.id]


# [claude] MCM-S-114
def test_mcm_s_114__include_deleted_applies_search_to_the_model_number(db, w1, mk_machine):
    """MCM-S-114 — include_deleted applies search to the model number.
    Rules: `search_machines` R21"""
    ma = mk_machine("MA", model_number="L-200")
    mk_machine("MZ")
    result = M.search_machines(db, workspace_id=w1.id, include_deleted=True, search="L-2")

    # Then 1
    assert ids(result) == [ma.id]


# [claude] MCM-S-115
def test_mcm_s_115__include_deleted_applies_search_to_the_manufacturer(db, w1, mk_machine):
    """MCM-S-115 — include_deleted applies search to the manufacturer.
    Rules: `search_machines` R21"""
    ma = mk_machine("MA", manufacturer="Haas")
    mk_machine("MZ")
    result = M.search_machines(db, workspace_id=w1.id, include_deleted=True, search="haa")

    # Then 1
    assert ids(result) == [ma.id]



# --------------------------------------------------------------------------- #
# delete_machine
# --------------------------------------------------------------------------- #

# [claude] MCM-D-01
def test_mcm_d_01__a_live_machine_not_in_use_is_soft_deleted_with_stamp_and_the_same(db, w1, u2, mk_machine):
    """MCM-D-01 — a live machine not in use is soft-deleted with stamp and the same instance returned.
    Rules: `delete_machine` R5, Returns"""
    m1 = mk_machine("M1")
    result = M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.is_deleted is True
    assert row.is_active is False
    # Then 3
    row = reread(db, m1)
    assert row.deleted_at == NOW
    assert row.deleted_by == u2.id
    # Then 4
    row = reread(db, m1)
    assert row.updated_at is not None


# [claude] MCM-D-02
def test_mcm_d_02__no_other_column_is_changed_by_the_delete(db, w1, u1, u2, f1, mk_machine):
    """MCM-D-02 — no other column is changed by the delete.
    Rules: `delete_machine` R5"""
    m1 = mk_machine("M1", model_number="L-200", note="Bay 3", updated_by=u1.id)
    result = M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.name == "Lathe"
    assert row.factory_id == f1.id
    assert row.workspace_id == w1.id
    # Then 3
    row = reread(db, m1)
    assert row.model_number == "L-200"
    assert row.note == "Bay 3"
    # Then 4
    row = reread(db, m1)
    assert row.created_by == u1.id
    assert row.updated_by == u1.id


# [claude] MCM-D-03
def test_mcm_d_03__a_section_link_is_kept_and_still_read(db, w1, u2, s1, mk_machine, mk_link):
    """MCM-D-03 — a section link is kept and still read.
    Rules: `delete_machine` R6, R4b"""
    m1 = mk_machine("M1")
    l1 = mk_link(m1, s1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    assert snap(db, l1) == before_l1
    # Then 3
    row = reread(db, m1)
    assert row.factory_section_id == s1.id


# [claude] MCM-D-04
def test_mcm_d_04__a_running_machine_stays_running_and_is_not_in_use_for_that(db, w1, u2, mk_machine):
    """MCM-D-04 — a running machine stays running and is not in use for that.
    Rules: `delete_machine` R6, R4b"""
    m1 = mk_machine("M1", is_running=True)
    result = M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.is_deleted is True
    # Then 3
    row = reread(db, m1)
    assert row.is_running is True


# [claude] MCM-D-05
def test_mcm_d_05__one_deactivated_event_is_written(db, w1, u2, mk_machine):
    """MCM-D-05 — one deactivated event is written.
    Rules: `delete_machine` R7"""
    m1 = mk_machine("M1")
    result = M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    rows = events_of(db, m1)
    assert len(rows) == 1
    # Then 3
    assert rows[0].event_type == "deactivated"
    assert rows[0].description == "Machine deactivated: Lathe"
    # Then 4
    assert rows[0].performed_by == u2.id
    assert rows[0].metadata_json is None
    # Then 5
    assert rows[0].workspace_id == w1.id


# [claude] MCM-D-06
def test_mcm_d_06__an_id_that_no_machine_has_is_refused(db, w1, u2, mk_machine):
    """MCM-D-06 — an id that no machine has is refused.
    Rules: `delete_machine` R1, Errors row 1"""
    m1 = mk_machine("M1")
    before_m1 = snap_before(db, m1)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_machine(db, machine_id=MISSING, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine with ID 999999999 not found"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, m1) == before_m1


# [claude] MCM-D-07
def test_mcm_d_07__a_machine_of_another_workspace_is_refused_and_not_changed(db, w1, u2, mk_machine):
    """MCM-D-07 — a machine of another workspace is refused and not changed.
    Rules: `delete_machine` R1, Errors row 1"""
    m9 = mk_machine("M9")
    before_m9 = snap_before(db, m9)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_machine(db, machine_id=m9.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Machine with ID {m9.id} not found"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, m9) == before_m9


# [claude] MCM-D-08
def test_mcm_d_08__an_already_deleted_machine_is_refused_the_stamp_stays_and_no_event_is(db, w1, u1, u2, mk_machine):
    """MCM-D-08 — an already deleted machine is refused, the stamp stays and no event is written.
    Rules: `delete_machine` R2, Errors row 2"""
    mx = mk_machine("MX")
    before_mx = snap_before(db, mx)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_machine(db, machine_id=mx.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Machine is already deleted"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, mx) == before_mx
    # Then 6
    row = reread(db, mx)
    assert row.deleted_at == T0
    assert row.deleted_by == u1.id


# [claude] MCM-D-09
def test_mcm_d_09__already_deleted_wins_over_in_use(db, w1, u2, i1, mk_machine, mk_stock):
    """MCM-D-09 — already deleted wins over in use.
    Rules: `delete_machine` R2, R4"""
    mx = mk_machine("MX")
    mk_stock(mx, i1, qty=5)
    before_mx = snap_before(db, mx)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_machine(db, machine_id=mx.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Machine is already deleted"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, mx) == before_mx


# [claude] MCM-D-10
@pytest.mark.xfail(strict=True, reason="BUG-965: A machine inside a soft-deleted factory can still be deleted")
def test_mcm_d_10__a_live_machine_of_a_soft_deleted_factory_is_refused(db, w1, u2, mk_machine):
    """MCM-D-10 — a live machine of a soft-deleted factory is refused.
    Rules: `delete_machine` R3 [BUG-965], Errors row 3"""
    mf = mk_machine("MF")
    before_mf = snap_before(db, mf)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_machine(db, machine_id=mf.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot delete a machine of a deleted factory"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, mf) == before_mf


# [claude] MCM-D-11
@pytest.mark.xfail(strict=True, reason="BUG-965: A machine inside a soft-deleted factory can still be deleted")
def test_mcm_d_11__the_deleted_factory_refusal_wins_over_in_use(db, w1, u2, i1, mk_machine, mk_stock):
    """MCM-D-11 — the deleted-factory refusal wins over in use.
    Rules: `delete_machine` R3 [BUG-965], R4"""
    mf = mk_machine("MF")
    mk_stock(mf, i1, qty=5)
    before_mf = snap_before(db, mf)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_machine(db, machine_id=mf.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot delete a machine of a deleted factory"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, mf) == before_mf


# [claude] MCM-D-12
def test_mcm_d_12__a_machine_of_a_live_but_inactive_factory_is_deleted(db, w1, u2, mk_machine):
    """MCM-D-12 — a machine of a live but inactive factory is deleted.
    Rules: `delete_machine` R3"""
    mi = mk_machine("MI")
    result = M.delete_machine(db, machine_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is mi
    # Then 2
    row = reread(db, mi)
    assert row.is_deleted is True


# [claude] MCM-D-13
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_13__stock_on_the_machine_blocks_the_delete(db, w1, u2, i1, mk_machine, mk_stock):
    """MCM-D-13 — stock on the machine blocks the delete.
    Rules: `delete_machine` R4 (a) [BUG-968], R4a, Errors row 4"""
    m1 = mk_machine("M1")
    st1 = mk_stock(m1, i1, qty=5)
    before_st1 = snap_before(db, st1)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "machine_stock", "id": st1.id}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    assert snap(db, st1) == before_st1


# [claude] MCM-D-14
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_14__negative_stock_blocks_the_delete(db, w1, u2, i1, mk_machine, mk_stock):
    """MCM-D-14 — negative stock blocks the delete.
    Rules: `delete_machine` R4 (a) [BUG-968], R4a, Errors row 4"""
    m1 = mk_machine("M1")
    st1 = mk_stock(m1, i1, qty=-1)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "machine_stock", "id": st1.id}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0


# [claude] MCM-D-15
def test_mcm_d_15__stock_0_does_not_block_whatever_req_qty_and_defective_qty_hold(db, w1, u2, i1, mk_machine, mk_stock):
    """MCM-D-15 — stock 0 does not block, whatever req_qty and defective_qty hold.
    Rules: `delete_machine` R4 (a)"""
    m1 = mk_machine("M1")
    st1 = mk_stock(m1, i1, qty=0, req_qty=4, defective_qty=2)
    before_st1 = snap_before(db, st1)
    result = M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.is_deleted is True
    # Then 3
    assert snap(db, st1) == before_st1


# [claude] MCM-D-16
def test_mcm_d_16__stock_of_another_machine_does_not_block(db, w1, u2, i1, mk_machine, mk_stock):
    """MCM-D-16 — stock of another machine does not block.
    Rules: `delete_machine` R4 (a)"""
    m1 = mk_machine("M1")
    m2 = mk_machine("M2")
    st1 = mk_stock(m2, i1, qty=5)
    before_st1 = snap_before(db, st1)
    before_m2 = snap_before(db, m2)
    result = M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.is_deleted is True
    # Then 3
    assert snap(db, st1) == before_st1
    # Then 4
    assert snap(db, m2) == before_m2


# [claude] MCM-D-17
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_17__a_purchase_order_to_the_machine_blocks_the_delete(db, w1, u2, std, mk_machine, mk_po):
    """MCM-D-17 — a purchase order to the machine blocks the delete.
    Rules: `delete_machine` R4 (b) [BUG-968], R4a, Errors row 4"""
    m1 = mk_machine("M1")
    po1 = mk_po("PO1", destination_id=m1.id, current_status_id=std.id)
    before_po1 = snap_before(db, po1)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "purchase_order", "id": po1.id}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    assert snap(db, po1) == before_po1


# [claude] MCM-D-18
def test_mcm_d_18__a_purchase_order_at_stage_complete_does_not_block(db, w1, u2, stc, mk_machine, mk_po):
    """MCM-D-18 — a purchase order at stage Complete does not block.
    Rules: `delete_machine` R4 (b)"""
    m1 = mk_machine("M1")
    po1 = mk_po("PO1", destination_id=m1.id, current_status_id=stc.id)
    before_po1 = snap_before(db, po1)
    result = M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.is_deleted is True
    # Then 3
    assert snap(db, po1) == before_po1


# [claude] MCM-D-19
def test_mcm_d_19__a_voided_purchase_order_does_not_block(db, w1, u2, std, mk_machine, mk_po):
    """MCM-D-19 — a voided purchase order does not block.
    Rules: `delete_machine` R4 (b)"""
    m1 = mk_machine("M1")
    po1 = mk_po("PO1", destination_id=m1.id, current_status_id=std.id, voided=True)
    before_po1 = snap_before(db, po1)
    result = M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.is_deleted is True
    # Then 3
    assert snap(db, po1) == before_po1


# [claude] MCM-D-20
def test_mcm_d_20__a_purchase_order_to_a_store_with_the_same_id_does_not_block(db, w1, u2, std, mk_machine, mk_po):
    """MCM-D-20 — a purchase order to a store with the same id does not block.
    Rules: `delete_machine` R4 (b)"""
    m1 = mk_machine("M1")
    po1 = mk_po("PO1", destination_type="storage", destination_id=m1.id, current_status_id=std.id)
    before_po1 = snap_before(db, po1)
    result = M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.is_deleted is True
    # Then 3
    assert snap(db, po1) == before_po1


# [claude] MCM-D-21
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_21__an_open_draft_work_order_on_the_machine_blocks_the_delete(db, w1, u2, mk_machine, mk_order):
    """MCM-D-21 — an open DRAFT work order on the machine blocks the delete.
    Rules: `delete_machine` R4 (c) [BUG-968], R4a, Errors row 4"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="DRAFT")
    before_o1 = snap_before(db, o1)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    assert snap(db, o1) == before_o1


# [claude] MCM-D-22
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_22__an_in_progress_work_order_on_the_machine_blocks_the_delete(db, w1, u2, mk_machine, mk_order):
    """MCM-D-22 — an IN_PROGRESS work order on the machine blocks the delete.
    Rules: `delete_machine` R4 (c) [BUG-968], R4a, Errors row 4"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="IN_PROGRESS")

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0


# [claude] MCM-D-23
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_23__an_open_order_of_another_machine_with_a_live_line_sourcing_from_this(db, w1, u2, mk_machine, mk_order, mk_line):
    """MCM-D-23 — an open order of another machine with a live line sourcing from this one blocks.
    Rules: `delete_machine` R4 (c) [BUG-968], R4a, Errors row 4"""
    m1 = mk_machine("M1")
    m2 = mk_machine("M2")
    o1 = mk_order(m2, "O1", status="DRAFT")
    mk_line(o1, source_location_type="machine", source_location_id=m1.id)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0


# [claude] MCM-D-24
def test_mcm_d_24__a_completed_work_order_on_the_machine_does_not_block(db, w1, u2, mk_machine, mk_order):
    """MCM-D-24 — a completed work order on the machine does not block.
    Rules: `delete_machine` R4 (c)"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="COMPLETED")
    before_o1 = snap_before(db, o1)
    result = M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.is_deleted is True
    # Then 3
    assert snap(db, o1) == before_o1


# [claude] MCM-D-25
def test_mcm_d_25__a_voided_work_order_on_the_machine_does_not_block(db, w1, u2, mk_machine, mk_order):
    """MCM-D-25 — a voided work order on the machine does not block.
    Rules: `delete_machine` R4 (c)"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="VOIDED")
    before_o1 = snap_before(db, o1)
    result = M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.is_deleted is True
    # Then 3
    assert snap(db, o1) == before_o1


# [claude] MCM-D-26
def test_mcm_d_26__a_soft_deleted_work_order_on_the_machine_does_not_block(db, w1, u2, mk_machine, mk_order):
    """MCM-D-26 — a soft-deleted work order on the machine does not block.
    Rules: `delete_machine` R4 (c)"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="DRAFT", is_deleted=True)
    before_o1 = snap_before(db, o1)
    result = M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.is_deleted is True
    # Then 3
    assert snap(db, o1) == before_o1


# [claude] MCM-D-27
def test_mcm_d_27__a_completed_order_with_a_line_sourcing_from_the_machine_does_not_block(db, w1, u2, mk_machine, mk_order, mk_line):
    """MCM-D-27 — a completed order with a line sourcing from the machine does not block.
    Rules: `delete_machine` R4 (c)"""
    m1 = mk_machine("M1")
    m2 = mk_machine("M2")
    o1 = mk_order(m2, "O1", status="COMPLETED")
    l1 = mk_line(o1, source_location_type="machine", source_location_id=m1.id)
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.is_deleted is True
    # Then 3
    assert snap(db, o1) == before_o1
    # Then 4
    assert snap(db, l1) == before_l1


# [claude] MCM-D-28
def test_mcm_d_28__a_soft_deleted_line_sourcing_from_the_machine_does_not_block(db, w1, u2, mk_machine, mk_order, mk_line):
    """MCM-D-28 — a soft-deleted line sourcing from the machine does not block.
    Rules: `delete_machine` R4 (c)"""
    m1 = mk_machine("M1")
    m2 = mk_machine("M2")
    o1 = mk_order(m2, "O1", status="DRAFT")
    l1 = mk_line(o1, source_location_type="machine", source_location_id=m1.id, is_deleted=True)
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.is_deleted is True
    # Then 3
    assert snap(db, o1) == before_o1
    # Then 4
    assert snap(db, l1) == before_l1


# [claude] MCM-D-29
def test_mcm_d_29__a_line_sourcing_from_a_store_with_the_same_id_does_not_block(db, w1, u2, mk_machine, mk_order, mk_line):
    """MCM-D-29 — a line sourcing from a store with the same id does not block.
    Rules: `delete_machine` R4 (c)"""
    m1 = mk_machine("M1")
    m2 = mk_machine("M2")
    o1 = mk_order(m2, "O1", status="DRAFT")
    l1 = mk_line(o1, source_location_type="storage", source_location_id=m1.id)
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.is_deleted is True
    # Then 3
    assert snap(db, o1) == before_o1
    # Then 4
    assert snap(db, l1) == before_l1


# [claude] MCM-D-30
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_30__a_transfer_order_from_the_machine_blocks_the_delete(db, w1, u2, mk_machine, mk_to):
    """MCM-D-30 — a transfer order from the machine blocks the delete.
    Rules: `delete_machine` R4 (d) [BUG-968], R4a, Errors row 4"""
    m1 = mk_machine("M1")
    to1 = mk_to("TO1", source_location_type="machine", source_location_id=m1.id)
    before_to1 = snap_before(db, to1)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "transfer_order", "id": to1.id}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    assert snap(db, to1) == before_to1


# [claude] MCM-D-31
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_31__a_transfer_order_to_the_machine_blocks_the_delete(db, w1, u2, mk_machine, mk_to):
    """MCM-D-31 — a transfer order to the machine blocks the delete.
    Rules: `delete_machine` R4 (d) [BUG-968], R4a, Errors row 4"""
    m1 = mk_machine("M1")
    to1 = mk_to("TO1", destination_location_type="machine", destination_location_id=m1.id)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "transfer_order", "id": to1.id}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0


# [claude] MCM-D-32
def test_mcm_d_32__a_completed_transfer_order_does_not_block(db, w1, u2, mk_machine, mk_to):
    """MCM-D-32 — a completed transfer order does not block.
    Rules: `delete_machine` R4 (d)"""
    m1 = mk_machine("M1")
    to1 = mk_to("TO1", source_location_type="machine", source_location_id=m1.id, completed_at=T0)
    before_to1 = snap_before(db, to1)
    result = M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.is_deleted is True
    # Then 3
    assert snap(db, to1) == before_to1


# [claude] MCM-D-33
def test_mcm_d_33__a_transfer_with_a_store_of_the_same_id_does_not_block(db, w1, u2, mk_machine, mk_to):
    """MCM-D-33 — a transfer with a store of the same id does not block.
    Rules: `delete_machine` R4 (d)"""
    m1 = mk_machine("M1")
    to1 = mk_to("TO1", source_location_id=m1.id, destination_location_id=m1.id)
    before_to1 = snap_before(db, to1)
    result = M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.is_deleted is True
    # Then 3
    assert snap(db, to1) == before_to1


# [claude] MCM-D-34
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_34__an_order_that_qualifies_twice_is_listed_once_work_order_on_the(db, w1, u2, mk_machine, mk_order, mk_line):
    """MCM-D-34 — an order that qualifies twice is listed once: work order on the machine and sourcing from it.
    Rules: `delete_machine` R4a [BUG-968]"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="DRAFT")
    mk_line(o1, source_location_type="machine", source_location_id=m1.id)
    mk_line(o1, source_location_type="machine", source_location_id=m1.id)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0


# [claude] MCM-D-35
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_35__a_transfer_from_and_to_the_machine_is_listed_once(db, w1, u2, mk_machine, mk_to):
    """MCM-D-35 — a transfer from and to the machine is listed once.
    Rules: `delete_machine` R4a [BUG-968]"""
    m1 = mk_machine("M1")
    to1 = mk_to("TO1", source_location_type="machine", source_location_id=m1.id, destination_location_type="machine", destination_location_id=m1.id)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "transfer_order", "id": to1.id}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0


# [claude] MCM-D-36
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_36__two_stock_rows_are_two_entries_by_id(db, w1, u2, i1, i2, mk_machine, mk_stock):
    """MCM-D-36 — two stock rows are two entries, by id.
    Rules: `delete_machine` R4a [BUG-968]"""
    m1 = mk_machine("M1")
    st1 = mk_stock(m1, i1, qty=5)
    st2 = mk_stock(m1, i2, qty=1)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "machine_stock", "id": st1.id}, {"type": "machine_stock", "id": st2.id}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0


# [claude] MCM-D-37
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_37__two_work_orders_are_sorted_by_id_ascending(db, w1, u2, mk_machine, mk_order):
    """MCM-D-37 — two work orders are sorted by id ascending.
    Rules: `delete_machine` R4a [BUG-968]"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="DRAFT")
    o2 = mk_order(m1, "O2", status="IN_PROGRESS")

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}, {"type": "work_order", "id": o2.id}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0


# [claude] MCM-D-38
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_38__the_four_types_come_in_the_fixed_order_however_they_were_built(db, w1, u2, i1, std, mk_machine, mk_order, mk_stock, mk_po, mk_to):
    """MCM-D-38 — the four types come in the fixed order, however they were built.
    Rules: `delete_machine` R4a [BUG-968]"""
    m1 = mk_machine("M1")
    to1 = mk_to("TO1", source_location_type="machine", source_location_id=m1.id)
    o1 = mk_order(m1, "O1", status="DRAFT")
    po1 = mk_po("PO1", destination_id=m1.id, current_status_id=std.id)
    st1 = mk_stock(m1, i1, qty=5)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "machine_stock", "id": st1.id}, {"type": "purchase_order", "id": po1.id}, {"type": "work_order", "id": o1.id}, {"type": "transfer_order", "id": to1.id}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0


# [claude] MCM-D-39
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_39__the_id_of_a_sourcing_line_is_the_order_s_never_the_line_s(db, w1, u2, f1, mk_machine, mk_order, mk_line):
    """MCM-D-39 — the id of a sourcing line is the order's, never the line's.
    Rules: `delete_machine` R4a [BUG-968]"""
    m1 = mk_machine("M1")
    m2 = mk_machine("M2")
    o1 = mk_order(m2, "O1", status="IN_PROGRESS")
    mk_line(o1, source_location_type="storage", source_location_id=f1.id)
    mk_line(o1, source_location_type="machine", source_location_id=m1.id)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0


# [claude] MCM-D-40
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_40__only_blocking_rows_are_listed(db, w1, u2, i1, i2, stc, mk_machine, mk_order, mk_stock, mk_po):
    """MCM-D-40 — only blocking rows are listed.
    Rules: `delete_machine` R4a [BUG-968]"""
    m1 = mk_machine("M1")
    st0 = mk_stock(m1, i1, qty=0)
    st1 = mk_stock(m1, i2, qty=5)
    po1 = mk_po("PO1", destination_id=m1.id, current_status_id=stc.id)
    o1 = mk_order(m1, "O1", status="COMPLETED")
    before_st0 = snap_before(db, st0)
    before_po1 = snap_before(db, po1)
    before_o1 = snap_before(db, o1)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "machine_stock", "id": st1.id}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    assert snap(db, st0) == before_st0
    # Then 8
    assert snap(db, po1) == before_po1
    # Then 9
    assert snap(db, o1) == before_o1


# [claude] MCM-D-41
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_41__a_machine_in_use_deleted_by_an_unknown_user_gets_the_refusal_not_a(db, w1, i1, mk_machine, mk_stock):
    """MCM-D-41 — a machine in use deleted by an unknown user gets the refusal, not a database error.
    Rules: `delete_machine` R4 [BUG-968], R9"""
    m1 = mk_machine("M1")
    st1 = mk_stock(m1, i1, qty=5)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=MISSING)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "machine_stock", "id": st1.id}]
    # Then 5
    assert m1 not in db.dirty
    # Then 6
    db.flush()
    # Then 7
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 8
    assert count_rows(db, "machine_activity_events") == 0


# [claude] MCM-D-42
def test_mcm_d_42__a_maintenance_log_does_not_block(db, w1, u2, mk_machine):
    """MCM-D-42 — a maintenance log does not block.
    Rules: `delete_machine` R4b"""
    m1 = mk_machine("M1")
    ml1 = _add(db, MachineMaintenanceLog(workspace_id=w1.id, machine_id=m1.id, maintenance_type=list(MaintenanceTypeEnum)[0], maintenance_date=D(0), summary="Belt changed"))  # noqa: RUF015
    before_ml1 = snap_before(db, ml1)
    result = M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.is_deleted is True
    # Then 3
    assert snap(db, ml1) == before_ml1


# [claude] MCM-D-43
def test_mcm_d_43__activity_events_do_not_block(db, w1, u2, mk_machine, mk_status_row):
    """MCM-D-43 — activity events do not block.
    Rules: `delete_machine` R4b"""
    m1 = mk_machine("M1")
    ev1 = mk_status_row(m1, T1, "RUNNING")
    before_ev1 = snap_before(db, ev1)
    result = M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.is_deleted is True
    # Then 3
    assert snap(db, ev1) == before_ev1


# [claude] MCM-D-44
def test_mcm_d_44__a_machine_item_ledger_row_does_not_block(db, w1, u1, u2, i1, mk_machine):
    """MCM-D-44 — a machine item ledger row does not block.
    Rules: `delete_machine` R4b"""
    m1 = mk_machine("M1")
    lg = _add(db, MachineItemLedger(workspace_id=w1.id, machine_id=m1.id, item_id=i1.id, transaction_type="manual_add", quantity=5, unit_cost=1, total_cost=5, qty_before=0, qty_after=5, source_type="manual", performed_by=u1.id))
    before_lg = snap_before(db, lg)
    result = M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.is_deleted is True
    # Then 3
    assert snap(db, lg) == before_lg


# [claude] MCM-D-45
def test_mcm_d_45__a_work_order_template_naming_the_machine_does_not_block(db, w1, u2, wt1, mk_machine):
    """MCM-D-45 — a work order template naming the machine does not block.
    Rules: `delete_machine` R4b"""
    m1 = mk_machine("M1")
    tp1 = _add(db, WorkOrderTemplate(workspace_id=w1.id, template_name="Monthly", work_order_type_id=wt1.id, default_machine_id=m1.id))
    before_tp1 = snap_before(db, tp1)
    result = M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.is_deleted is True
    # Then 3
    assert snap(db, tp1) == before_tp1


# [claude] MCM-D-46
def test_mcm_d_46__a_production_line_naming_the_machine_does_not_block(db, w1, u2, f1, mk_machine):
    """MCM-D-46 — a production line naming the machine does not block.
    Rules: `delete_machine` R4b"""
    m1 = mk_machine("M1")
    pl1 = _add(db, ProductionLine(workspace_id=w1.id, factory_id=f1.id, name="Line One", machine_id=m1.id))
    before_pl1 = snap_before(db, pl1)
    result = M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.is_deleted is True
    # Then 3
    assert snap(db, pl1) == before_pl1


# [claude] MCM-D-47
def test_mcm_d_47__a_formula_stage_naming_the_machine_does_not_block(db, w1, u2, mk_machine):
    """MCM-D-47 — a formula stage naming the machine does not block.
    Rules: `delete_machine` R4b"""
    m1 = mk_machine("M1")
    pf1 = _add(db, ProductionFormula(workspace_id=w1.id, formula_code="F-1", name="Mix"))
    fs1 = _add(db, ProductionFormulaStage(workspace_id=w1.id, formula_id=pf1.id, stage_order=1, name="Press", machine_id=m1.id))
    before_fs1 = snap_before(db, fs1)
    result = M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.is_deleted is True
    # Then 3
    assert snap(db, fs1) == before_fs1


# [claude] MCM-D-48
def test_mcm_d_48__after_the_delete_the_machine_is_not_listed(db, w1, u1, mk_machine):
    """MCM-D-48 — after the delete the machine is not listed.
    Rules: `delete_machine` R8"""
    mk_machine("MA")
    m1 = mk_machine("M1")
    M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u1.id)
    result = M.search_machines(db, workspace_id=w1.id)

    # Then 1
    assert names(result) == ["Alpha"]


# [claude] MCM-D-49
def test_mcm_d_49__after_the_delete_the_name_can_be_reused(db, w1, u1, u2, f1, mk_machine):
    """MCM-D-49 — after the delete the name can be reused.
    Rules: `delete_machine` R8; `create_machine` R4"""
    m1 = mk_machine("M1")
    M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u1.id)
    result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=f1.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id != m1.id
    # Then 2
    row = reread(db, result)
    assert row.name == "Lathe"
    assert row.is_deleted is False


# [claude] MCM-D-50
def test_mcm_d_50__after_the_delete_an_update_answers_400(db, w1, u1, u2, mk_machine):
    """MCM-D-50 — after the delete an update answers 400.
    Rules: `delete_machine` R8"""
    m1 = mk_machine("M1")
    M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u1.id)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_machine(db, machine_id=m1.id, machine_data=MachineUpdate(note="Bay 4"), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update a deleted machine"
    # Then 4
    row = reread(db, m1)
    assert row.note is None


# [claude] MCM-D-51
def test_mcm_d_51__after_the_delete_a_second_delete_answers_400(db, w1, u1, u2, mk_machine):
    """MCM-D-51 — after the delete a second delete answers 400.
    Rules: `delete_machine` R8"""
    m1 = mk_machine("M1")
    M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u1.id)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Machine is already deleted"
    # Then 4
    row = reread(db, m1)
    assert row.deleted_by == u1.id


# [claude] MCM-D-52
@pytest.mark.xfail(strict=True, reason="BUG-955: `get_machine` returns soft-deleted machines")
def test_mcm_d_52__after_the_delete_get_machine_answers_404(db, w1, u1, mk_machine):
    """MCM-D-52 — after the delete get_machine answers 404.
    Rules: `delete_machine` R8; `get_machine` R3 [BUG-955]"""
    m1 = mk_machine("M1")
    M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u1.id)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_machine(db, machine_id=m1.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Machine with ID {m1.id} not found"


# [claude] MCM-D-53
def test_mcm_d_53__an_unknown_user_fails_on_flush_and_the_machine_stays_live(db, w1, mk_machine):
    """MCM-D-53 — an unknown user fails on flush and the machine stays live.
    Rules: `delete_machine` R9, Errors row 5"""
    m1 = mk_machine("M1")

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=MISSING)
    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert "machines_deleted_by_fkey" in str(exc.value.orig)
    # Then 4
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 5
    assert count_rows(db, "machine_activity_events") == 0


# [claude] MCM-D-54
def test_mcm_d_54__the_delete_is_flushed_but_not_committed_a_rollback_makes_the_machine(db, w1, u2, mk_machine, monkeypatch):
    """MCM-D-54 — the delete is flushed but not committed: a rollback makes the machine live and removes the event.
    Rules: `delete_machine` R10, Returns"""
    m1 = mk_machine("M1")
    sp = db.begin_nested()
    spy = commit_spy(db, monkeypatch)
    result = M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.is_deleted is True
    # Then 3
    rows = events_of(db, m1)
    assert len(rows) == 1
    # Then 4
    sp.rollback()
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 5
    assert count_rows(db, "machine_activity_events") == 0
    # Then 6
    spy.assert_not_called()


# [claude] MCM-D-55
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_55__stock_with_another_workspace_s_id_on_the_machine_is_shown_only_as_the(db, w1, w2, u2, mk_i9, mk_machine, mk_stock):
    """MCM-D-55 — stock with another workspace's id on the machine is shown only as the generic entry.
    Rules: `delete_machine` R4 (a) [BUG-968], R4a, Errors row 4"""
    m1 = mk_machine("M1")
    i9 = mk_i9()
    st1 = mk_stock(m1, i9, qty=5, workspace_id=w2.id)
    before_st1 = snap_before(db, st1)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    assert snap(db, st1) == before_st1


# [claude] MCM-D-56
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_56__a_purchase_order_of_another_workspace_to_the_machine_is_shown_only_as(db, w1, w2, u2, mk_st9, mk_machine, mk_po):
    """MCM-D-56 — a purchase order of another workspace to the machine is shown only as the generic entry.
    Rules: `delete_machine` R4 (b) [BUG-968], R4a, Errors row 4"""
    m1 = mk_machine("M1")
    st9 = mk_st9()
    po1 = mk_po("PO1", destination_id=m1.id, current_status_id=st9.id, workspace_id=w2.id)
    before_po1 = snap_before(db, po1)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    assert snap(db, po1) == before_po1


# [claude] MCM-D-57
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_57__a_transfer_order_of_another_workspace_from_the_machine_is_shown_only(db, w1, w2, u2, f9, mk_st9, mk_machine, mk_to):
    """MCM-D-57 — a transfer order of another workspace from the machine is shown only as the generic entry.
    Rules: `delete_machine` R4 (d) [BUG-968], R4a, Errors row 4"""
    m1 = mk_machine("M1")
    st9 = mk_st9()
    to1 = mk_to("TO1", source_location_type="machine", source_location_id=m1.id, workspace_id=w2.id, destination_location_id=f9.id, current_status_id=st9.id)
    before_to1 = snap_before(db, to1)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    assert snap(db, to1) == before_to1


# [claude] MCM-D-58
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_58__a_work_order_of_another_workspace_with_this_machine_id_is_shown_only(db, w1, w2, u2, f9, wt9, mk_machine, mk_order):
    """MCM-D-58 — a work order of another workspace with this machine id is shown only as the generic entry.
    Rules: `delete_machine` R4 (c) [BUG-968], R4a, Errors row 4"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    before_o1 = snap_before(db, o1)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    assert snap(db, o1) == before_o1


# [claude] MCM-D-59
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_59__a_work_order_of_another_workspace_with_a_line_sourcing_from_the(db, w1, w2, u2, f9, wt9, mk_i9, mk_machine, mk_order, mk_line):
    """MCM-D-59 — a work order of another workspace with a line sourcing from the machine is shown only as the generic entry.
    Rules: `delete_machine` R4 (c) [BUG-968], R4a, Errors row 4"""
    m1 = mk_machine("M1")
    m9 = mk_machine("M9")
    i9 = mk_i9()
    o1 = mk_order(m9, "O1", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    l1 = mk_line(o1, source_location_type="machine", source_location_id=m1.id, workspace_id=w2.id, item_id=i9.id)
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    assert snap(db, o1) == before_o1
    # Then 8
    assert snap(db, l1) == before_l1


# [claude] MCM-D-60
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_60__blockers_of_both_workspaces_own_rows_listed_by_type_then_id_the_rest(db, w1, w2, u2, f9, i1, mk_i9, mk_st9, mk_machine, mk_order, mk_stock, mk_to):
    """MCM-D-60 — blockers of both workspaces: own rows listed by type then id, the rest one generic entry, last.
    Rules: `delete_machine` R4 (a) [BUG-968], R4a, Errors row 4"""
    m1 = mk_machine("M1")
    i9 = mk_i9()
    st1 = mk_stock(m1, i9, qty=5, workspace_id=w2.id)
    st2 = mk_stock(m1, i1, qty=1)
    o1 = mk_order(m1, "O1", status="DRAFT")
    st9 = mk_st9()
    to1 = mk_to("TO1", source_location_type="machine", source_location_id=m1.id, workspace_id=w2.id, destination_location_id=f9.id, current_status_id=st9.id)
    before_st1 = snap_before(db, st1)
    before_st2 = snap_before(db, st2)
    before_o1 = snap_before(db, o1)
    before_to1 = snap_before(db, to1)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "machine_stock", "id": st2.id}, {"type": "work_order", "id": o1.id}, {"type": "other_workspace"}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    assert snap(db, st1) == before_st1
    # Then 8
    assert snap(db, st2) == before_st2
    # Then 9
    assert snap(db, o1) == before_o1
    # Then 10
    assert snap(db, to1) == before_to1


# [claude] MCM-D-61
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_61__a_stock_row_of_another_workspace_with_an_item_of_this_one_is_shown(db, w1, w2, u2, i1, mk_machine, mk_stock):
    """MCM-D-61 — a stock row of another workspace with an item of this one is shown only as the generic entry.
    Rules: `delete_machine` R4 (a) [BUG-968], R4a, Errors row 4"""
    m1 = mk_machine("M1")
    st1 = mk_stock(m1, i1, qty=5, workspace_id=w2.id)
    before_st1 = snap_before(db, st1)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    assert snap(db, st1) == before_st1


# [claude] MCM-D-62
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_62__a_line_of_another_workspace_on_an_open_order_of_this_one_is_shown(db, w1, w2, u2, mk_machine, mk_order, mk_line):
    """MCM-D-62 — a line of another workspace on an open order of this one is shown only as the generic entry.
    Rules: `delete_machine` R4 (c) [BUG-968], R4a, Errors row 4"""
    m1 = mk_machine("M1")
    m2 = mk_machine("M2")
    o1 = mk_order(m2, "O1", status="DRAFT")
    l1 = mk_line(o1, source_location_type="machine", source_location_id=m1.id, workspace_id=w2.id)
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    assert snap(db, o1) == before_o1
    # Then 8
    assert snap(db, l1) == before_l1


# [claude] MCM-D-63
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_63__a_line_of_this_workspace_on_an_open_order_of_another_one_is_shown(db, w1, w2, u2, f9, wt9, mk_machine, mk_order, mk_line):
    """MCM-D-63 — a line of this workspace on an open order of another one is shown only as the generic entry.
    Rules: `delete_machine` R4 (c) [BUG-968], R4a, Errors row 4"""
    m1 = mk_machine("M1")
    m9 = mk_machine("M9")
    o1 = mk_order(m9, "O1", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    l1 = mk_line(o1, source_location_type="machine", source_location_id=m1.id)
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    assert snap(db, o1) == before_o1
    # Then 8
    assert snap(db, l1) == before_l1


# [claude] MCM-D-64
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_64__a_purchase_order_of_this_workspace_on_a_stage_of_another_one_not(db, w1, u2, mk_st9, mk_machine, mk_po):
    """MCM-D-64 — a purchase order of this workspace on a stage of another one, not Complete, blocks.
    Rules: `delete_machine` R4 (b) [BUG-968], R4a, Errors row 4"""
    m1 = mk_machine("M1")
    st9 = mk_st9()
    po1 = mk_po("PO1", destination_id=m1.id, current_status_id=st9.id)
    before_po1 = snap_before(db, po1)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "purchase_order", "id": po1.id}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    assert snap(db, po1) == before_po1


# [claude] MCM-D-65
def test_mcm_d_65__a_purchase_order_of_this_workspace_on_a_stage_complete_of_another_one(db, w1, u2, mk_stc9, mk_machine, mk_po):
    """MCM-D-65 — a purchase order of this workspace on a stage Complete of another one does not block.
    Rules: `delete_machine` R4 (b)"""
    m1 = mk_machine("M1")
    stc9 = mk_stc9()
    po1 = mk_po("PO1", destination_id=m1.id, current_status_id=stc9.id)
    before_po1 = snap_before(db, po1)
    result = M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.is_deleted is True
    # Then 3
    assert snap(db, po1) == before_po1


# [claude] MCM-D-66
def test_mcm_d_66__a_purchase_order_of_another_workspace_at_its_own_stage_complete_does(db, w1, w2, u2, mk_stc9, mk_machine, mk_po):
    """MCM-D-66 — a purchase order of another workspace at its own stage Complete does not block.
    Rules: `delete_machine` R4 (b)"""
    m1 = mk_machine("M1")
    stc9 = mk_stc9()
    po1 = mk_po("PO1", destination_id=m1.id, current_status_id=stc9.id, workspace_id=w2.id)
    before_po1 = snap_before(db, po1)
    result = M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.is_deleted is True
    # Then 3
    assert snap(db, po1) == before_po1


# [claude] MCM-D-67
def test_mcm_d_67__a_machine_of_another_workspace_that_is_in_use_gets_not_found_with_no(db, w1, w2, u2, f9, wt9, mk_i9, mk_machine, mk_order, mk_stock):
    """MCM-D-67 — a machine of another workspace that is in use gets not found, with no blocker ids.
    Rules: `delete_machine` R1, R4, Errors row 1"""
    m9 = mk_machine("M9")
    i9 = mk_i9()
    st1 = mk_stock(m9, i9, qty=5)
    o1 = mk_order(m9, "O1", status="IN_PROGRESS", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    before_m9 = snap_before(db, m9)
    before_st1 = snap_before(db, st1)
    before_o1 = snap_before(db, o1)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_machine(db, machine_id=m9.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Machine with ID {m9.id} not found"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, m9) == before_m9
    # Then 6
    assert snap(db, st1) == before_st1
    # Then 7
    assert snap(db, o1) == before_o1


# [claude] MCM-D-68
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_68__a_machine_of_a_live_but_inactive_factory_is_still_refused_when_in_use(db, w1, u2, i1, mk_machine, mk_stock):
    """MCM-D-68 — a machine of a live but inactive factory is still refused when in use.
    Rules: `delete_machine` R3, R4 (a) [BUG-968], R4a, Errors row 4"""
    mi = mk_machine("MI")
    st1 = mk_stock(mi, i1, qty=5)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "machine_stock", "id": st1.id}]
    # Then 4
    row = reread(db, mi)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_by is None
    # Then 5
    assert count_rows(db, "machine_activity_events") == 0


# [claude] MCM-D-69
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_69__a_work_order_on_the_machine_whose_own_factory_is_soft_deleted_blocks(db, w1, u2, fd, mk_machine, mk_order):
    """MCM-D-69 — a work order on the machine whose own factory is soft-deleted blocks.
    Rules: `delete_machine` R4 (c) [BUG-968], R4a, Errors row 4"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="DRAFT", factory_id=fd.id)
    before_o1 = snap_before(db, o1)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    assert snap(db, o1) == before_o1


# [claude] MCM-D-70
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_70__a_transfer_whose_other_end_is_a_soft_deleted_factory_blocks(db, w1, u2, fd, mk_machine, mk_to):
    """MCM-D-70 — a transfer whose other end is a soft-deleted factory blocks.
    Rules: `delete_machine` R4 (d) [BUG-968], R4a, Errors row 4"""
    m1 = mk_machine("M1")
    to1 = mk_to("TO1", source_location_type="machine", source_location_id=m1.id, destination_location_id=fd.id)
    before_to1 = snap_before(db, to1)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "transfer_order", "id": to1.id}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    assert snap(db, to1) == before_to1


# [claude] MCM-D-71
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_71__a_transfer_whose_other_end_is_a_soft_deleted_machine_blocks(db, w1, u2, mk_machine, mk_to):
    """MCM-D-71 — a transfer whose other end is a soft-deleted machine blocks.
    Rules: `delete_machine` R4 (d) [BUG-968], R4a, Errors row 4"""
    m1 = mk_machine("M1")
    mx = mk_machine("MX")
    to1 = mk_to("TO1", source_location_type="machine", source_location_id=m1.id, destination_location_type="machine", destination_location_id=mx.id)
    before_to1 = snap_before(db, to1)
    before_mx = snap_before(db, mx)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "transfer_order", "id": to1.id}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    assert snap(db, to1) == before_to1
    # Then 8
    assert snap(db, mx) == before_mx


# [claude] MCM-D-72
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_72__a_sourcing_line_on_an_open_order_of_a_soft_deleted_machine_blocks(db, w1, u2, mk_machine, mk_order, mk_line):
    """MCM-D-72 — a sourcing line on an open order of a soft-deleted machine blocks.
    Rules: `delete_machine` R4 (c) [BUG-968], R4a, Errors row 4"""
    m1 = mk_machine("M1")
    mx = mk_machine("MX")
    o1 = mk_order(mx, "O1", status="DRAFT")
    l1 = mk_line(o1, source_location_type="machine", source_location_id=m1.id)
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    before_mx = snap_before(db, mx)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    assert snap(db, o1) == before_o1
    # Then 8
    assert snap(db, l1) == before_l1
    # Then 9
    assert snap(db, mx) == before_mx


# [claude] MCM-D-73
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_73__an_order_on_the_machine_with_only_a_consumed_sourcing_line_blocks(db, w1, u2, mk_machine, mk_order, mk_line):
    """MCM-D-73 — an order on the machine with only a consumed sourcing line blocks through machine_id, listed once.
    Rules: `delete_machine` R4 (c) [BUG-968], R4a, Errors row 4"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="IN_PROGRESS")
    l1 = mk_line(o1, source_location_type="machine", source_location_id=m1.id, consumed_at=T0)
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    assert snap(db, o1) == before_o1
    # Then 8
    assert snap(db, l1) == before_l1


# [claude] MCM-D-74
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_74__an_order_of_another_machine_with_one_consumed_and_one_unconsumed(db, w1, u2, mk_machine, mk_order, mk_line):
    """MCM-D-74 — an order of another machine with one consumed and one unconsumed sourcing line blocks, order id once.
    Rules: `delete_machine` R4 (c) [BUG-968], R4a, Errors row 4"""
    m1 = mk_machine("M1")
    m2 = mk_machine("M2")
    o1 = mk_order(m2, "O1", status="IN_PROGRESS")
    l1 = mk_line(o1, source_location_type="machine", source_location_id=m1.id, consumed_at=T0)
    l2 = mk_line(o1, source_location_type="machine", source_location_id=m1.id)
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    before_l2 = snap_before(db, l2)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    assert snap(db, o1) == before_o1
    # Then 8
    assert snap(db, l1) == before_l1
    # Then 9
    assert snap(db, l2) == before_l2


# [claude] MCM-D-75
def test_mcm_d_75__a_consumed_sourcing_line_on_an_open_order_of_another_machine_does_not(db, w1, u2, mk_machine, mk_order, mk_line):
    """MCM-D-75 — a consumed sourcing line on an open order of another machine does not block.
    Rules: `delete_machine` R4 (c), R4a, R4b"""
    m1 = mk_machine("M1")
    m2 = mk_machine("M2")
    o1 = mk_order(m2, "O1", status="IN_PROGRESS")
    l1 = mk_line(o1, source_location_type="machine", source_location_id=m1.id, consumed_at=T0)
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.is_deleted is True
    # Then 3
    assert snap(db, o1) == before_o1
    # Then 4
    assert snap(db, l1) == before_l1


# [claude] MCM-D-76
def test_mcm_d_76__a_sourcing_line_with_uses_inventory_false_on_an_open_order_of_another(db, w1, u2, mk_machine, mk_order, mk_line):
    """MCM-D-76 — a sourcing line with uses_inventory False on an open order of another machine does not block.
    Rules: `delete_machine` R4 (c), R4a, R4b"""
    m1 = mk_machine("M1")
    m2 = mk_machine("M2")
    o1 = mk_order(m2, "O1", status="IN_PROGRESS")
    l1 = mk_line(o1, source_location_type="machine", source_location_id=m1.id, uses_inventory=False)
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.is_deleted is True
    # Then 3
    assert snap(db, o1) == before_o1
    # Then 4
    assert snap(db, l1) == before_l1


# [claude] MCM-D-77
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_77__a_sourcing_line_on_an_open_order_with_no_machine_blocks(db, w1, u2, mk_machine, mk_order, mk_line):
    """MCM-D-77 — a sourcing line on an open order with no machine blocks.
    Rules: `delete_machine` R4 (c) [BUG-968], R4a, Errors row 4"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="DRAFT", machine_id=None)
    l1 = mk_line(o1, source_location_type="machine", source_location_id=m1.id)
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    assert snap(db, o1) == before_o1
    # Then 8
    assert snap(db, l1) == before_l1


# [claude] MCM-D-78
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_78__several_foreign_rows_of_different_types_give_one_generic_entry(db, w1, w2, u2, f9, wt9, mk_i9, mk_st9, mk_machine, mk_order, mk_stock, mk_po, mk_to):
    """MCM-D-78 — several foreign rows of different types give one generic entry.
    Rules: `delete_machine` R4 (a) [BUG-968], R4a, Errors row 4"""
    m1 = mk_machine("M1")
    i9 = mk_i9()
    st9 = mk_st9()
    st1 = mk_stock(m1, i9, qty=5, workspace_id=w2.id)
    po1 = mk_po("PO1", destination_id=m1.id, current_status_id=st9.id, workspace_id=w2.id)
    to1 = mk_to("TO1", source_location_type="machine", source_location_id=m1.id, workspace_id=w2.id, destination_location_id=f9.id, current_status_id=st9.id)
    o1 = mk_order(m1, "O1", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    before_st1 = snap_before(db, st1)
    before_po1 = snap_before(db, po1)
    before_to1 = snap_before(db, to1)
    before_o1 = snap_before(db, o1)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    assert snap(db, st1) == before_st1
    # Then 8
    assert snap(db, po1) == before_po1
    # Then 9
    assert snap(db, to1) == before_to1
    # Then 10
    assert snap(db, o1) == before_o1


# [claude] MCM-D-79
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_79__an_order_of_this_workspace_through_machine_id_with_a_foreign_line(db, w1, w2, u2, mk_machine, mk_order, mk_line):
    """MCM-D-79 — an order of this workspace through machine_id with a foreign line keeps its entry, and the line adds the generic one.
    Rules: `delete_machine` R4 (c) [BUG-968], R4a, Errors row 4"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="DRAFT")
    l1 = mk_line(o1, source_location_type="machine", source_location_id=m1.id, workspace_id=w2.id)
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}, {"type": "other_workspace"}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    assert snap(db, o1) == before_o1
    # Then 8
    assert snap(db, l1) == before_l1


# [claude] MCM-D-80
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_80__no_id_or_text_of_the_other_workspace_appears_anywhere_in_the_refusal(db, w1, w2, u2, f9, wt9, i1, mk_i9, mk_st9, mk_machine, mk_order, mk_stock, mk_po, mk_to):
    """MCM-D-80 — no id or text of the other workspace appears anywhere in the refusal.
    Rules: `delete_machine` R4a [BUG-968], Errors row 4"""
    m1 = mk_machine("M1")
    i9 = mk_i9()
    st9 = mk_st9()
    st1 = mk_stock(m1, i9, qty=5, workspace_id=w2.id)
    po1 = mk_po("PO1", destination_id=m1.id, current_status_id=st9.id, workspace_id=w2.id)
    to1 = mk_to("TO1", source_location_type="machine", source_location_id=m1.id, workspace_id=w2.id, destination_location_id=f9.id, current_status_id=st9.id)
    o1 = mk_order(m1, "O1", status="DRAFT", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    st2 = mk_stock(m1, i1, qty=1)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "machine_stock", "id": st2.id}, {"type": "other_workspace"}]
    # Then 5
    assert {(e["type"], e.get("id")) for e in exc.value.args[1]}.isdisjoint({("machine_stock", st1.id), ("purchase_order", po1.id), ("transfer_order", to1.id), ("work_order", o1.id)})
    # Then 6
    assert all(text not in repr(exc.value.args) for text in ("PO-PO1", "TR-TO1", "WO-O1", "Far Spring", "Far Depot"))
    # Then 7
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 8
    assert count_rows(db, "machine_activity_events") == 0


# [claude] MCM-D-81
def test_mcm_d_81__a_line_sourcing_from_a_third_machine_does_not_block(db, w1, u2, mk_machine, mk_order, mk_line):
    """MCM-D-81 — a line sourcing from a third machine does not block.
    Rules: `delete_machine` R4 (c), R4b"""
    m1 = mk_machine("M1")
    m2 = mk_machine("M2")
    m3 = mk_machine("M3")
    o1 = mk_order(m2, "O1", status="DRAFT")
    l1 = mk_line(o1, source_location_type="machine", source_location_id=m3.id)
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.is_deleted is True
    # Then 3
    assert snap(db, o1) == before_o1
    # Then 4
    assert snap(db, l1) == before_l1


# [claude] MCM-D-82
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_82__a_transfer_to_the_machine_from_a_soft_deleted_factory_blocks(db, w1, u2, fd, mk_machine, mk_to):
    """MCM-D-82 — a transfer to the machine from a soft-deleted factory blocks.
    Rules: `delete_machine` R4 (d) [BUG-968], R4a, Errors row 4"""
    m1 = mk_machine("M1")
    to1 = mk_to("TO1", source_location_id=fd.id, destination_location_type="machine", destination_location_id=m1.id)
    before_to1 = snap_before(db, to1)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "transfer_order", "id": to1.id}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    assert snap(db, to1) == before_to1


# [claude] MCM-D-83
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_83__a_transfer_to_the_machine_from_a_soft_deleted_machine_blocks(db, w1, u2, mk_machine, mk_to):
    """MCM-D-83 — a transfer to the machine from a soft-deleted machine blocks.
    Rules: `delete_machine` R4 (d) [BUG-968], R4a, Errors row 4"""
    m1 = mk_machine("M1")
    mx = mk_machine("MX")
    to1 = mk_to("TO1", source_location_type="machine", source_location_id=mx.id, destination_location_type="machine", destination_location_id=m1.id)
    before_to1 = snap_before(db, to1)
    before_mx = snap_before(db, mx)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "transfer_order", "id": to1.id}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    assert snap(db, to1) == before_to1
    # Then 8
    assert snap(db, mx) == before_mx


# [claude] MCM-D-84
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_84__a_transfer_at_stage_complete_with_completed_at_null_blocks(db, w1, u2, stc, mk_machine, mk_to):
    """MCM-D-84 — a transfer at stage Complete with completed_at NULL blocks.
    Rules: `delete_machine` R4 (d) [BUG-968], R4a, Errors row 4"""
    m1 = mk_machine("M1")
    to1 = mk_to("TO1", source_location_type="machine", source_location_id=m1.id, current_status_id=stc.id)
    before_to1 = snap_before(db, to1)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "transfer_order", "id": to1.id}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    assert snap(db, to1) == before_to1


# [claude] MCM-D-85
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_85__a_transfer_of_this_workspace_on_a_stage_of_another_one_has_its_normal(db, w1, u2, mk_st9, mk_machine, mk_to):
    """MCM-D-85 — a transfer of this workspace on a stage of another one has its normal entry.
    Rules: `delete_machine` R4 (d) [BUG-968], R4a, Errors row 4"""
    m1 = mk_machine("M1")
    st9 = mk_st9()
    to1 = mk_to("TO1", source_location_type="machine", source_location_id=m1.id, current_status_id=st9.id)
    before_to1 = snap_before(db, to1)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "transfer_order", "id": to1.id}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    assert snap(db, to1) == before_to1


# [claude] MCM-D-86
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_86__two_purchase_orders_are_sorted_by_id_ascending(db, w1, u2, std, mk_machine, mk_po):
    """MCM-D-86 — two purchase orders are sorted by id ascending.
    Rules: `delete_machine` R4 (b) [BUG-968], R4a, Errors row 4"""
    m1 = mk_machine("M1")
    po1 = mk_po("PO1", destination_id=m1.id, current_status_id=std.id)
    po2 = mk_po("PO2", destination_id=m1.id, current_status_id=std.id)
    before_po1 = snap_before(db, po1)
    before_po2 = snap_before(db, po2)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "purchase_order", "id": po1.id}, {"type": "purchase_order", "id": po2.id}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    assert snap(db, po1) == before_po1
    # Then 8
    assert snap(db, po2) == before_po2


# [claude] MCM-D-87
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_87__two_transfers_are_sorted_by_id_ascending(db, w1, u2, mk_machine, mk_to):
    """MCM-D-87 — two transfers are sorted by id ascending.
    Rules: `delete_machine` R4 (d) [BUG-968], R4a, Errors row 4"""
    m1 = mk_machine("M1")
    to1 = mk_to("TO1", source_location_type="machine", source_location_id=m1.id)
    to2 = mk_to("TO2", destination_location_type="machine", destination_location_id=m1.id)
    before_to1 = snap_before(db, to1)
    before_to2 = snap_before(db, to2)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "transfer_order", "id": to1.id}, {"type": "transfer_order", "id": to2.id}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    assert snap(db, to1) == before_to1
    # Then 8
    assert snap(db, to2) == before_to2


# [claude] MCM-D-88
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_88__stock_of_an_inactive_item_blocks(db, w1, u2, mk_ix, mk_machine, mk_stock):
    """MCM-D-88 — stock of an inactive item blocks.
    Rules: `delete_machine` R4 (a) [BUG-968], R4a, Errors row 4"""
    m1 = mk_machine("M1")
    ix = mk_ix()
    st1 = mk_stock(m1, ix, qty=5)
    before_st1 = snap_before(db, st1)
    before_ix = snap_before(db, ix)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "machine_stock", "id": st1.id}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    assert snap(db, st1) == before_st1
    # Then 8
    assert snap(db, ix) == before_ix


# [claude] MCM-D-89
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_89__a_sourcing_line_of_an_inactive_item_blocks(db, w1, u2, mk_ix, mk_machine, mk_order, mk_line):
    """MCM-D-89 — a sourcing line of an inactive item blocks.
    Rules: `delete_machine` R4 (c) [BUG-968], R4a, Errors row 4"""
    m1 = mk_machine("M1")
    m2 = mk_machine("M2")
    ix = mk_ix()
    o1 = mk_order(m2, "O1", status="DRAFT")
    l1 = mk_line(o1, source_location_type="machine", source_location_id=m1.id, item_id=ix.id)
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    before_ix = snap_before(db, ix)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    assert snap(db, o1) == before_o1
    # Then 8
    assert snap(db, l1) == before_l1
    # Then 9
    assert snap(db, ix) == before_ix


# [claude] MCM-D-90
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_90__a_work_order_on_the_machine_in_an_inactive_factory_blocks(db, w1, u2, fi, mk_machine, mk_order):
    """MCM-D-90 — a work order on the machine in an inactive factory blocks.
    Rules: `delete_machine` R4 (c) [BUG-968], R4a, Errors row 4"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="DRAFT", factory_id=fi.id)
    before_o1 = snap_before(db, o1)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    assert snap(db, o1) == before_o1


# [claude] MCM-D-91
def test_mcm_d_91__foreign_stock_at_quantity_0_meets_no_condition_and_does_not_block(db, w1, w2, u2, i1, mk_machine, mk_stock):
    """MCM-D-91 — foreign stock at quantity 0 meets no condition and does not block.
    Rules: `delete_machine` R4"""
    m1 = mk_machine("M1")
    st1 = mk_stock(m1, i1, qty=0, workspace_id=w2.id)
    before_st1 = snap_before(db, st1)
    result = M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.is_deleted is True
    # Then 3
    assert snap(db, st1) == before_st1


# [claude] MCM-D-92
def test_mcm_d_92__a_completed_transfer_of_another_workspace_meets_no_condition_and_does(db, w1, w2, u2, f9, mk_st9, mk_machine, mk_to):
    """MCM-D-92 — a completed transfer of another workspace meets no condition and does not block.
    Rules: `delete_machine` R4"""
    m1 = mk_machine("M1")
    st9 = mk_st9()
    to1 = mk_to("TO1", source_location_type="machine", source_location_id=m1.id, workspace_id=w2.id, destination_location_id=f9.id, current_status_id=st9.id, completed_at=T0)
    before_to1 = snap_before(db, to1)
    result = M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.is_deleted is True
    # Then 3
    assert snap(db, to1) == before_to1


# [claude] MCM-D-93
def test_mcm_d_93__a_completed_order_of_another_workspace_meets_no_condition_and_does(db, w1, w2, u2, f9, wt9, mk_machine, mk_order):
    """MCM-D-93 — a COMPLETED order of another workspace meets no condition and does not block.
    Rules: `delete_machine` R4"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="COMPLETED", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    before_o1 = snap_before(db, o1)
    result = M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.is_deleted is True
    # Then 3
    assert snap(db, o1) == before_o1


# [claude] MCM-D-94
def test_mcm_d_94__a_consumed_line_of_another_workspace_meets_no_condition_and_does_not(db, w1, w2, u2, mk_machine, mk_order, mk_line):
    """MCM-D-94 — a consumed line of another workspace meets no condition and does not block.
    Rules: `delete_machine` R4"""
    m1 = mk_machine("M1")
    m2 = mk_machine("M2")
    o1 = mk_order(m2, "O1", status="DRAFT")
    l1 = mk_line(o1, source_location_type="machine", source_location_id=m1.id, workspace_id=w2.id, consumed_at=T0)
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    result = M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.is_deleted is True
    # Then 3
    assert snap(db, o1) == before_o1
    # Then 4
    assert snap(db, l1) == before_l1


# [claude] MCM-D-95
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_95__stock_of_this_workspace_with_an_item_of_another_one_keeps_its_normal(db, w1, u2, mk_i9, mk_machine, mk_stock):
    """MCM-D-95 — stock of this workspace with an item of another one keeps its normal entry.
    Rules: `delete_machine` R4 (a) [BUG-968], R4a, Errors row 4"""
    m1 = mk_machine("M1")
    i9 = mk_i9()
    st1 = mk_stock(m1, i9, qty=5)
    before_st1 = snap_before(db, st1)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "machine_stock", "id": st1.id}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    assert snap(db, st1) == before_st1


# [claude] MCM-D-96
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_96__a_work_order_of_this_workspace_with_a_factory_and_a_type_of_another(db, w1, u2, f9, wt9, mk_machine, mk_order):
    """MCM-D-96 — a work order of this workspace with a factory and a type of another one keeps its normal entry.
    Rules: `delete_machine` R4 (c) [BUG-968], R4a, Errors row 4"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="DRAFT", factory_id=f9.id, work_order_type_id=wt9.id)
    before_o1 = snap_before(db, o1)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    assert snap(db, o1) == before_o1


# [claude] MCM-D-97
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_97__a_transfer_of_this_workspace_with_an_end_in_another_one_keeps_its(db, w1, u2, f9, mk_machine, mk_to):
    """MCM-D-97 — a transfer of this workspace with an end in another one keeps its normal entry.
    Rules: `delete_machine` R4 (d) [BUG-968], R4a, Errors row 4"""
    m1 = mk_machine("M1")
    to1 = mk_to("TO1", source_location_type="machine", source_location_id=m1.id, destination_location_id=f9.id)
    before_to1 = snap_before(db, to1)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "transfer_order", "id": to1.id}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    assert snap(db, to1) == before_to1


# [claude] MCM-D-98
@pytest.mark.xfail(strict=True, reason="BUG-968: Machine with stock or open orders can be deleted")
def test_mcm_d_98__an_own_order_through_its_own_line_keeps_its_entry_and_a_foreign_line(db, w1, w2, u2, mk_machine, mk_order, mk_line):
    """MCM-D-98 — an own order through its own line keeps its entry, and a foreign line adds the generic one.
    Rules: `delete_machine` R4 (c) [BUG-968], R4a, Errors row 4"""
    m1 = mk_machine("M1")
    m2 = mk_machine("M2")
    o1 = mk_order(m2, "O1", status="DRAFT")
    l1 = mk_line(o1, source_location_type="machine", source_location_id=m1.id)
    l2 = mk_line(o1, source_location_type="machine", source_location_id=m1.id, workspace_id=w2.id)
    before_o1 = snap_before(db, o1)
    before_l1 = snap_before(db, l1)
    before_l2 = snap_before(db, l2)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_machine(db, machine_id=m1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[0] == "Machine has stock or open orders"
    # Then 4
    assert exc.value.args[1] == [{"type": "work_order", "id": o1.id}, {"type": "other_workspace"}]
    # Then 5
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machine_activity_events") == 0
    # Then 7
    assert snap(db, o1) == before_o1
    # Then 8
    assert snap(db, l1) == before_l1
    # Then 9
    assert snap(db, l2) == before_l2



# --------------------------------------------------------------------------- #
# create_machine_event
# --------------------------------------------------------------------------- #

# [claude] MCM-E-01
def test_mcm_e_01__a_first_status_is_recorded_and_is_running_follows(db, w1, u2, mk_machine):
    """MCM-E-01 — a first status is recorded and is_running follows.
    Rules: `create_machine_event` R8, R10, R6, Returns"""
    m1 = mk_machine("M1")
    result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=m1.id, event_type=RUNNING), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert isinstance(result, MachineEventResponse)
    # Then 2
    assert result.id is not None
    # Then 3
    rows = events_of(db, m1)
    assert len(rows) == 1
    # Then 4
    assert rows[0].event_type == "status_updated"
    assert rows[0].performed_by == u2.id
    assert rows[0].workspace_id == w1.id
    # Then 5
    assert rows[0].metadata_json == {"status": "RUNNING", "note": None, "changes": [{"field": "status", "label": "Status", "from_value": None, "to_value": "RUNNING"}]}
    # Then 6
    row = reread(db, m1)
    assert row.is_running is True


# [claude] MCM-E-02
def test_mcm_e_02__an_id_that_no_machine_has_is_refused(db, w1, u2, mk_machine):
    """MCM-E-02 — an id that no machine has is refused.
    Rules: `create_machine_event` R1, Errors row 1"""
    m1 = mk_machine("M1")
    before_m1 = snap_before(db, m1)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine_event(db, event_data=MachineEventCreate(machine_id=MISSING, event_type=IDLE), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine with ID 999999999 not found"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, m1) == before_m1


# [claude] MCM-E-03
def test_mcm_e_03__a_machine_of_another_workspace_is_refused(db, w1, u2, mk_machine):
    """MCM-E-03 — a machine of another workspace is refused.
    Rules: `create_machine_event` R1, Errors row 1"""
    m9 = mk_machine("M9")
    before_m9 = snap_before(db, m9)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine_event(db, event_data=MachineEventCreate(machine_id=m9.id, event_type=IDLE), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Machine with ID {m9.id} not found"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, m9) == before_m9


# [claude] MCM-E-04
def test_mcm_e_04__a_soft_deleted_machine_is_refused(db, w1, u2, mk_machine):
    """MCM-E-04 — a soft-deleted machine is refused.
    Rules: `create_machine_event` R2, Errors row 2"""
    mx = mk_machine("MX")
    before_mx = snap_before(db, mx)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine_event(db, event_data=MachineEventCreate(machine_id=mx.id, event_type=IDLE), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot create event for a deleted machine"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, mx) == before_mx


# [claude] MCM-E-05
def test_mcm_e_05__a_soft_deleted_machine_is_refused_also_when_a_work_order_drives_it(db, w1, u2, mk_machine):
    """MCM-E-05 — a soft-deleted machine is refused also when a work order drives it.
    Rules: `create_machine_event` R2, Errors row 2"""
    mx = mk_machine("MX")
    before_mx = snap_before(db, mx)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine_event(db, event_data=MachineEventCreate(machine_id=mx.id, event_type=IDLE), workspace_id=w1.id, user_id=u2.id, work_order_id=77)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot create event for a deleted machine"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, mx) == before_mx


# [claude] MCM-E-06
def test_mcm_e_06__a_deleted_machine_in_a_deleted_factory_gets_the_deleted_machine(db, w1, u2, fd, mk_machine):
    """MCM-E-06 — a deleted machine in a deleted factory gets the deleted-machine message.
    Rules: `create_machine_event` R2, R3"""
    mx = mk_machine("MX", factory_id=fd.id)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine_event(db, event_data=MachineEventCreate(machine_id=mx.id, event_type=IDLE), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot create event for a deleted machine"
    # Then 4
    assert written(db) == before


# [claude] MCM-E-07
@pytest.mark.xfail(strict=True, reason="BUG-974: Manual status change accepted on a machine of a soft-deleted factory")
def test_mcm_e_07__a_manual_change_on_a_machine_of_a_soft_deleted_factory_is_refused(db, w1, u2, mk_machine):
    """MCM-E-07 — a manual change on a machine of a soft-deleted factory is refused.
    Rules: `create_machine_event` R3 [BUG-974], Errors row 4"""
    mf = mk_machine("MF")
    before_mf = snap_before(db, mf)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine_event(db, event_data=MachineEventCreate(machine_id=mf.id, event_type=RUNNING), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot create event for a machine of a deleted factory"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, mf) == before_mf


# [claude] MCM-E-08
@pytest.mark.xfail(strict=True, reason="BUG-974: Manual status change accepted on a machine of a soft-deleted factory")
def test_mcm_e_08__the_deleted_factory_refusal_comes_before_the_current_status(db, w1, u2, mk_machine, mk_status_row):
    """MCM-E-08 — the deleted-factory refusal comes before the current status.
    Rules: `create_machine_event` R3 [BUG-974], Errors row 4"""
    mf = mk_machine("MF")
    mk_status_row(mf, T1, "IDLE")
    before_mf = snap_before(db, mf)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine_event(db, event_data=MachineEventCreate(machine_id=mf.id, event_type=IDLE), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot create event for a machine of a deleted factory"
    # Then 4
    assert count_rows(db, "machine_activity_events") == 1
    # Then 5
    assert snap(db, mf) == before_mf


# [claude] MCM-E-09
def test_mcm_e_09__a_machine_of_a_live_but_inactive_factory_is_accepted(db, w1, u2, mk_machine):
    """MCM-E-09 — a machine of a live but inactive factory is accepted.
    Rules: `create_machine_event` R3"""
    mi = mk_machine("MI")
    result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=mi.id, event_type=RUNNING), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, mi)
    assert row.is_running is True


# [claude] MCM-E-10
def test_mcm_e_10__a_work_order_may_drive_a_machine_of_a_soft_deleted_factory(db, w1, u2, fd, mk_machine, mk_order):
    """MCM-E-10 — a work order may drive a machine of a soft-deleted factory.
    Rules: `create_machine_event` R3a, R9"""
    mf = mk_machine("MF")
    o1 = mk_order(mf, "O1", status="IN_PROGRESS", factory_id=fd.id)
    result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=mf.id, event_type=RUNNING), workspace_id=w1.id, user_id=u2.id, work_order_id=o1.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, mf)
    assert row.is_running is True
    # Then 3
    rows = events_of(db, mf)
    assert len(rows) == 1
    # Then 4
    assert events_of(db, mf)[0].metadata_json["work_order_id"] == o1.id


# [claude] MCM-E-11
@pytest.mark.xfail(strict=True, reason="BUG-1000: Status event stores a work order id without checking its workspace")
def test_mcm_e_11__work_order_id_0_names_no_order_also_on_a_machine_of_a_soft_deleted(db, w1, u2, mk_machine):
    """MCM-E-11 — work order id 0 names no order, also on a machine of a soft-deleted factory.
    Rules: `create_machine_event` R2a [BUG-1000], Errors row 3"""
    mf = mk_machine("MF")
    before_mf = snap_before(db, mf)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine_event(db, event_data=MachineEventCreate(machine_id=mf.id, event_type=RUNNING), workspace_id=w1.id, user_id=u2.id, work_order_id=0)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Work order with ID 0 not found"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, mf) == before_mf


# [claude] MCM-E-12
def test_mcm_e_12__the_newest_status_row_decides_not_the_last_inserted(db, w1, u2, mk_machine, mk_status_row):
    """MCM-E-12 — the newest status row decides, not the last inserted.
    Rules: `create_machine_event` R4, R5"""
    m1 = mk_machine("M1")
    mk_status_row(m1, T2, "RUNNING")
    mk_status_row(m1, T1, "IDLE")

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine_event(db, event_data=MachineEventCreate(machine_id=m1.id, event_type=RUNNING), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Machine is already in 'RUNNING' state"
    # Then 4
    assert count_rows(db, "machine_activity_events") == 2


# [claude] MCM-E-13
def test_mcm_e_13__on_a_created_at_tie_the_highest_id_decides(db, w1, u2, mk_machine, mk_status_row):
    """MCM-E-13 — on a created_at tie the highest id decides.
    Rules: `create_machine_event` R4, R5"""
    m1 = mk_machine("M1")
    mk_status_row(m1, T2, "RUNNING")
    mk_status_row(m1, T2, "IDLE")

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine_event(db, event_data=MachineEventCreate(machine_id=m1.id, event_type=IDLE), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Machine is already in 'IDLE' state"
    # Then 4
    assert count_rows(db, "machine_activity_events") == 2


# [claude] MCM-E-14
def test_mcm_e_14__another_event_type_is_ignored_even_when_newer_and_carrying_a_status(db, w1, u2, mk_machine, mk_status_row):
    """MCM-E-14 — another event type is ignored even when newer and carrying a status.
    Rules: `create_machine_event` R4"""
    m1 = mk_machine("M1")
    mk_status_row(m1, T1, "IDLE")
    mk_status_row(m1, T2, "OFF", event_type="updated")
    result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=m1.id, event_type=OFF), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert events_of(db, m1)[-1].metadata_json["changes"][0]["from_value"] == "IDLE"


# [claude] MCM-E-15
def test_mcm_e_15__a_status_row_of_another_workspace_is_ignored(db, w1, w2, u2, mk_machine, mk_status_row):
    """MCM-E-15 — a status row of another workspace is ignored.
    Rules: `create_machine_event` R4"""
    m1 = mk_machine("M1")
    mk_status_row(m1, T1, "IDLE")
    mk_status_row(m1, T2, "OFF", workspace_id=w2.id)
    result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=m1.id, event_type=OFF), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert events_of(db, m1)[-1].metadata_json["changes"][0]["from_value"] == "IDLE"


# [claude] MCM-E-16
def test_mcm_e_16__a_new_status_equal_to_the_current_one_is_refused_in_upper_case(db, w1, u2, mk_machine, mk_status_row):
    """MCM-E-16 — a new status equal to the current one is refused, in upper case.
    Rules: `create_machine_event` R5, Errors row 5"""
    m1 = mk_machine("M1")
    mk_status_row(m1, T1, "MAINTENANCE")
    before_m1 = snap_before(db, m1)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine_event(db, event_data=MachineEventCreate(machine_id=m1.id, event_type=MAINTENANCE), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Machine is already in 'MAINTENANCE' state"
    # Then 4
    assert count_rows(db, "machine_activity_events") == 1
    # Then 5
    assert snap(db, m1) == before_m1


# [claude] MCM-E-17
def test_mcm_e_17__the_same_status_is_refused_also_when_a_work_order_drives_it(db, w1, u2, mk_machine, mk_status_row, mk_order):
    """MCM-E-17 — the same status is refused also when a work order drives it.
    Rules: `create_machine_event` R5, Errors row 5"""
    m1 = mk_machine("M1")
    mk_status_row(m1, T1, "RUNNING")
    o1 = mk_order(m1, "O1", status="IN_PROGRESS")

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine_event(db, event_data=MachineEventCreate(machine_id=m1.id, event_type=RUNNING), workspace_id=w1.id, user_id=u2.id, work_order_id=o1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Machine is already in 'RUNNING' state"
    # Then 4
    assert count_rows(db, "machine_activity_events") == 1


# [claude] MCM-E-18
def test_mcm_e_18__a_different_status_is_accepted_and_from_value_is_the_current_one(db, w1, u2, mk_machine, mk_status_row):
    """MCM-E-18 — a different status is accepted and from_value is the current one.
    Rules: `create_machine_event` R8"""
    m1 = mk_machine("M1")
    mk_status_row(m1, T1, "RUNNING")
    result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=m1.id, event_type=IDLE), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert events_of(db, m1)[-1].metadata_json == {"status": "IDLE", "note": None, "changes": [{"field": "status", "label": "Status", "from_value": "RUNNING", "to_value": "IDLE"}]}


# [claude] MCM-E-19
def test_mcm_e_19__a_newest_row_with_null_metadata_means_no_current_status_older_rows(db, w1, u2, mk_machine, mk_status_row):
    """MCM-E-19 — a newest row with NULL metadata means no current status; older rows are not consulted.
    Rules: `create_machine_event` R6"""
    m1 = mk_machine("M1")
    mk_status_row(m1, T1, "IDLE")
    mk_status_row(m1, T2, metadata_json=None)
    result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=m1.id, event_type=IDLE), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert events_of(db, m1)[-1].metadata_json["changes"][0]["from_value"] is None


# [claude] MCM-E-20
def test_mcm_e_20__a_newest_row_without_a_status_key_means_no_current_status(db, w1, u2, mk_machine, mk_status_row):
    """MCM-E-20 — a newest row without a status key means no current status.
    Rules: `create_machine_event` R6"""
    m1 = mk_machine("M1")
    mk_status_row(m1, T1, "IDLE")
    mk_status_row(m1, T2, metadata_json={"note": "x"})
    result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=m1.id, event_type=IDLE), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert events_of(db, m1)[-1].metadata_json["changes"][0]["from_value"] is None


# [claude] MCM-E-21
def test_mcm_e_21__the_description_without_a_note(db, w1, u2, mk_machine):
    """MCM-E-21 — the description without a note.
    Rules: `create_machine_event` R7"""
    m1 = mk_machine("M1")
    result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=m1.id, event_type=IDLE), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert events_of(db, m1)[0].description == "Status set to idle"


# [claude] MCM-E-22
def test_mcm_e_22__the_description_with_a_note(db, w1, u2, mk_machine):
    """MCM-E-22 — the description with a note.
    Rules: `create_machine_event` R7"""
    m1 = mk_machine("M1")
    result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=m1.id, event_type=IDLE, note="Belt"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert events_of(db, m1)[0].description == "Status set to idle (Belt)"


# [claude] MCM-E-23
def test_mcm_e_23__the_description_with_an_empty_note(db, w1, u2, mk_machine):
    """MCM-E-23 — the description with an empty note.
    Rules: `create_machine_event` R7"""
    m1 = mk_machine("M1")
    result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=m1.id, event_type=IDLE, note=""), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert events_of(db, m1)[0].description == "Status set to idle"


# [claude] MCM-E-24
def test_mcm_e_24__the_description_with_a_whitespace_note(db, w1, u2, mk_machine):
    """MCM-E-24 — the description with a whitespace note.
    Rules: `create_machine_event` R7"""
    m1 = mk_machine("M1")
    result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=m1.id, event_type=IDLE, note="   "), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert events_of(db, m1)[0].description == "Status set to idle (   )"


# [claude] MCM-E-25
def test_mcm_e_25__the_metadata_keeps_the_note_as_sent(db, w1, u2, mk_machine):
    """MCM-E-25 — the metadata keeps the note as sent.
    Rules: `create_machine_event` R8"""
    m1 = mk_machine("M1")
    result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=m1.id, event_type=OFF, note="  Belt "), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert events_of(db, m1)[0].metadata_json == {"status": "OFF", "note": "  Belt ", "changes": [{"field": "status", "label": "Status", "from_value": None, "to_value": "OFF"}]}


# [claude] MCM-E-26
def test_mcm_e_26__the_metadata_keeps_an_empty_note(db, w1, u2, mk_machine):
    """MCM-E-26 — the metadata keeps an empty note.
    Rules: `create_machine_event` R8"""
    m1 = mk_machine("M1")
    result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=m1.id, event_type=OFF, note=""), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert events_of(db, m1)[0].metadata_json["note"] == ""


# [claude] MCM-E-27
def test_mcm_e_27__the_id_of_a_work_order_of_the_workspace_is_stored_in_the_metadata(db, w1, u2, mk_machine, mk_order):
    """MCM-E-27 — the id of a work order of the workspace is stored in the metadata.
    Rules: `create_machine_event` R9"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="IN_PROGRESS")
    before_o1 = snap_before(db, o1)
    result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=m1.id, event_type=IDLE), workspace_id=w1.id, user_id=u2.id, work_order_id=o1.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert events_of(db, m1)[0].metadata_json["work_order_id"] == o1.id
    # Then 3
    assert snap(db, o1) == before_o1


# [claude] MCM-E-28
@pytest.mark.xfail(strict=True, reason="BUG-1000: Status event stores a work order id without checking its workspace")
def test_mcm_e_28__work_order_id_0_is_refused_and_nothing_is_stored(db, w1, u2, mk_machine):
    """MCM-E-28 — work order id 0 is refused and nothing is stored.
    Rules: `create_machine_event` R2a [BUG-1000], Errors row 3"""
    m1 = mk_machine("M1")
    before_m1 = snap_before(db, m1)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine_event(db, event_data=MachineEventCreate(machine_id=m1.id, event_type=IDLE), workspace_id=w1.id, user_id=u2.id, work_order_id=0)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Work order with ID 0 not found"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, m1) == before_m1


# [claude] MCM-E-29
def test_mcm_e_29__no_work_order_id_adds_no_key(db, w1, u2, mk_machine):
    """MCM-E-29 — no work order id adds no key.
    Rules: `create_machine_event` R9"""
    m1 = mk_machine("M1")
    result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=m1.id, event_type=IDLE), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert "work_order_id" not in events_of(db, m1)[0].metadata_json


# [claude] MCM-E-30
def test_mcm_e_30__idle_stops_a_running_machine_and_stamps_it(db, w1, u2, mk_machine):
    """MCM-E-30 — IDLE stops a running machine and stamps it.
    Rules: `create_machine_event` R10, R11"""
    m1 = mk_machine("M1", is_running=True)
    result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=m1.id, event_type=IDLE), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, m1)
    assert row.is_running is False
    # Then 3
    row = reread(db, m1)
    assert row.updated_by == u2.id
    # Then 4
    row = reread(db, m1)
    assert row.updated_at is not None


# [claude] MCM-E-31
def test_mcm_e_31__off_stops_a_running_machine_and_stamps_it(db, w1, u2, mk_machine):
    """MCM-E-31 — OFF stops a running machine and stamps it.
    Rules: `create_machine_event` R10, R11"""
    m1 = mk_machine("M1", is_running=True)
    result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=m1.id, event_type=OFF), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, m1)
    assert row.is_running is False
    # Then 3
    row = reread(db, m1)
    assert row.updated_by == u2.id
    # Then 4
    row = reread(db, m1)
    assert row.updated_at is not None


# [claude] MCM-E-32
def test_mcm_e_32__maintenance_stops_a_running_machine_and_stamps_it(db, w1, u2, mk_machine):
    """MCM-E-32 — MAINTENANCE stops a running machine and stamps it.
    Rules: `create_machine_event` R10, R11"""
    m1 = mk_machine("M1", is_running=True)
    result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=m1.id, event_type=MAINTENANCE), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, m1)
    assert row.is_running is False
    # Then 3
    row = reread(db, m1)
    assert row.updated_by == u2.id
    # Then 4
    row = reread(db, m1)
    assert row.updated_at is not None


# [claude] MCM-E-33
def test_mcm_e_33__running_on_a_stopped_machine_stamps_it(db, w1, u2, mk_machine):
    """MCM-E-33 — RUNNING on a stopped machine stamps it.
    Rules: `create_machine_event` R10, R11"""
    m1 = mk_machine("M1")
    result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=m1.id, event_type=RUNNING), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, m1)
    assert row.is_running is True
    # Then 3
    row = reread(db, m1)
    assert row.updated_by == u2.id
    # Then 4
    row = reread(db, m1)
    assert row.updated_at is not None


# [claude] MCM-E-34
def test_mcm_e_34__a_first_idle_on_a_stopped_machine_writes_the_event_not_the_stamp(db, w1, u2, mk_machine):
    """MCM-E-34 — a first IDLE on a stopped machine writes the event, not the stamp.
    Rules: `create_machine_event` R12"""
    m1 = mk_machine("M1")
    result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=m1.id, event_type=IDLE), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    rows = events_of(db, m1)
    assert len(rows) == 1
    # Then 3
    row = reread(db, m1)
    assert row.updated_by is None
    # Then 4
    row = reread(db, m1)
    assert row.updated_at is None


# [claude] MCM-E-35
def test_mcm_e_35__off_after_maintenance_writes_the_event_not_the_stamp(db, w1, u2, mk_machine, mk_status_row):
    """MCM-E-35 — OFF after MAINTENANCE writes the event, not the stamp.
    Rules: `create_machine_event` R12"""
    m1 = mk_machine("M1")
    mk_status_row(m1, T1, "MAINTENANCE")
    result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=m1.id, event_type=OFF), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    rows = events_of(db, m1)
    assert len(rows) == 2
    # Then 3
    row = reread(db, m1)
    assert row.updated_by is None
    # Then 4
    row = reread(db, m1)
    assert row.updated_at is None


# [claude] MCM-E-36
def test_mcm_e_36__a_first_running_on_a_machine_already_running_writes_the_event_not_the(db, w1, u2, mk_machine):
    """MCM-E-36 — a first RUNNING on a machine already running writes the event, not the stamp.
    Rules: `create_machine_event` R12"""
    m1 = mk_machine("M1", is_running=True)
    result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=m1.id, event_type=RUNNING), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    rows = events_of(db, m1)
    assert len(rows) == 1
    # Then 3
    row = reread(db, m1)
    assert row.is_running is True
    # Then 4
    row = reread(db, m1)
    assert row.updated_by is None
    # Then 5
    row = reread(db, m1)
    assert row.updated_at is None


# [claude] MCM-E-37
def test_mcm_e_37__the_response_carries_the_event_s_values(db, w1, u2, mk_machine):
    """MCM-E-37 — the response carries the event's values.
    Rules: `create_machine_event` R13"""
    m1 = mk_machine("M1")
    result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=m1.id, event_type=IDLE, note="Belt"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == events_of(db, m1)[0].id
    # Then 2
    assert result.workspace_id == w1.id
    assert result.machine_id == m1.id
    # Then 3
    assert result.event_type == IDLE
    # Then 4
    assert result.note == "Belt"
    # Then 5
    assert result.started_at == events_of(db, m1)[0].created_at
    # Then 6
    assert result.created_at == events_of(db, m1)[0].created_at
    # Then 7
    assert result.initiated_by == u2.id
    assert result.created_by == u2.id


# [claude] MCM-E-38
@pytest.mark.xfail(strict=True, reason="BUG-960: Machine status change does not lock the row")
def test_mcm_e_38__the_machine_row_is_read_for_update_before_the_current_status(db, w1, u2, mk_machine):
    """MCM-E-38 — the machine row is read FOR UPDATE before the current status.
    Rules: `create_machine_event` R14 [BUG-960]"""
    m1 = mk_machine("M1")
    with record_sql(db) as sql_log:
        result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=m1.id, event_type=RUNNING), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    lock = [i for i, s in enumerate(sql_log) if "FROM machines" in s and "FOR UPDATE" in s]
    assert len(lock) >= 1
    # Then 3
    assert lock[0] < min(i for i, s in enumerate(sql_log) if "FROM machine_activity_events" in s)


# [claude] MCM-E-39
def test_mcm_e_39__an_unknown_user_fails_on_flush_is_running_unchanged_and_no_event(db, w1, mk_machine):
    """MCM-E-39 — an unknown user fails on flush, is_running unchanged and no event.
    Rules: `create_machine_event` R15, Errors row 6"""
    m1 = mk_machine("M1")

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            M.create_machine_event(db, event_data=MachineEventCreate(machine_id=m1.id, event_type=RUNNING), workspace_id=w1.id, user_id=MISSING)
    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert "machine_activity_events_performed_by_fkey" in str(exc.value.orig)
    # Then 4
    row = reread(db, m1)
    assert row.is_running is False
    # Then 5
    assert count_rows(db, "machine_activity_events") == 0


# [claude] MCM-E-40
def test_mcm_e_40__the_change_is_flushed_but_not_committed_a_rollback_removes_the_event(db, w1, u2, mk_machine, monkeypatch):
    """MCM-E-40 — the change is flushed but not committed: a rollback removes the event and restores the machine.
    Rules: `create_machine_event` R16"""
    m1 = mk_machine("M1")
    sp = db.begin_nested()
    spy = commit_spy(db, monkeypatch)
    result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=m1.id, event_type=RUNNING), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, m1)
    assert row.is_running is True
    assert row.updated_by == u2.id
    # Then 3
    rows = events_of(db, m1)
    assert len(rows) == 1
    # Then 4
    sp.rollback()
    row = reread(db, m1)
    assert row.is_running is False
    assert row.updated_by is None
    # Then 5
    assert count_rows(db, "machine_activity_events") == 0
    # Then 6
    spy.assert_not_called()


# [claude] MCM-E-41
@pytest.mark.xfail(strict=True, reason="BUG-1000: Status event stores a work order id without checking its workspace")
def test_mcm_e_41__a_work_order_of_another_workspace_gives_404_and_nothing_is_written(db, w1, w2, u2, f9, wt9, mk_machine, mk_order):
    """MCM-E-41 — a work order of another workspace gives 404 and nothing is written.
    Rules: `create_machine_event` R2a [BUG-1000], Errors row 3"""
    m1 = mk_machine("M1")
    m9 = mk_machine("M9")
    o9 = mk_order(m9, "O9", status="IN_PROGRESS", workspace_id=w2.id, work_order_type_id=wt9.id, factory_id=f9.id)
    before_m1 = snap_before(db, m1)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine_event(db, event_data=MachineEventCreate(machine_id=m1.id, event_type=IDLE), workspace_id=w1.id, user_id=u2.id, work_order_id=o9.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Work order with ID {o9.id} not found"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, m1) == before_m1


# [claude] MCM-E-42
@pytest.mark.xfail(strict=True, reason="BUG-1000: Status event stores a work order id without checking its workspace")
def test_mcm_e_42__an_unknown_work_order_id_gives_404_and_nothing_is_written(db, w1, u2, mk_machine):
    """MCM-E-42 — an unknown work order id gives 404 and nothing is written.
    Rules: `create_machine_event` R2a [BUG-1000], Errors row 3"""
    m1 = mk_machine("M1")
    before_m1 = snap_before(db, m1)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine_event(db, event_data=MachineEventCreate(machine_id=m1.id, event_type=IDLE), workspace_id=w1.id, user_id=u2.id, work_order_id=MISSING)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Work order with ID 999999999 not found"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, m1) == before_m1


# [claude] MCM-E-43
@pytest.mark.xfail(strict=True, reason="BUG-1000: Status event stores a work order id without checking its workspace")
def test_mcm_e_43__the_work_order_404_fires_before_the_same_status_check(db, w1, u2, mk_machine, mk_status_row):
    """MCM-E-43 — the work order 404 fires before the same-status check.
    Rules: `create_machine_event` R2a [BUG-1000], R5, Errors row 3"""
    m1 = mk_machine("M1")
    mk_status_row(m1, T1, "RUNNING")
    before_m1 = snap_before(db, m1)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine_event(db, event_data=MachineEventCreate(machine_id=m1.id, event_type=RUNNING), workspace_id=w1.id, user_id=u2.id, work_order_id=MISSING)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Work order with ID 999999999 not found"
    # Then 4
    assert count_rows(db, "machine_activity_events") == 1
    # Then 5
    assert snap(db, m1) == before_m1


# [claude] MCM-E-44
def test_mcm_e_44__the_order_s_state_and_machine_are_not_looked_at_a_completed_order_of(db, w1, u2, mk_machine, mk_order):
    """MCM-E-44 — the order's state and machine are not looked at: a completed order of another machine is accepted.
    Rules: `create_machine_event` R2a, R9"""
    m1 = mk_machine("M1")
    m2 = mk_machine("M2")
    o1 = mk_order(m2, "O1", status="COMPLETED")
    before_o1 = snap_before(db, o1)
    result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=m1.id, event_type=IDLE), workspace_id=w1.id, user_id=u2.id, work_order_id=o1.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert events_of(db, m1)[0].metadata_json["work_order_id"] == o1.id
    # Then 3
    assert snap(db, o1) == before_o1


# [claude] MCM-E-45
@pytest.mark.xfail(strict=True, reason="BUG-1000: Status event stores a work order id without checking its workspace")
def test_mcm_e_45__a_soft_deleted_work_order_of_the_workspace_gives_404_and_nothing_is(db, w1, u2, mk_machine, mk_order):
    """MCM-E-45 — a soft-deleted work order of the workspace gives 404 and nothing is written.
    Rules: `create_machine_event` R2a [BUG-1000], Errors row 3"""
    m1 = mk_machine("M1")
    o1 = mk_order(m1, "O1", status="IN_PROGRESS", is_deleted=True)
    before_m1 = snap_before(db, m1)
    before_o1 = snap_before(db, o1)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_machine_event(db, event_data=MachineEventCreate(machine_id=m1.id, event_type=IDLE), workspace_id=w1.id, user_id=u2.id, work_order_id=o1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Work order with ID {o1.id} not found"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, m1) == before_m1
    # Then 6
    assert snap(db, o1) == before_o1



# --------------------------------------------------------------------------- #
# _check_name_exists_in_factory
# --------------------------------------------------------------------------- #

# [claude] MCM-N-01
def test_mcm_n_01__a_live_machine_of_that_factory_and_name_is_found(db, w1, f1, mk_machine):
    """MCM-N-01 — a live machine of that factory and name is found.
    Rules: `_check_name_exists_in_factory` R1, R4"""
    mk_machine("M2")
    result = M._check_name_exists_in_factory(db, workspace_id=w1.id, factory_id=f1.id, name="Press")

    # Then 1
    assert result is True


# [claude] MCM-N-02
def test_mcm_n_02__a_machine_of_another_factory_is_not_found(db, w1, f2, mk_machine):
    """MCM-N-02 — a machine of another factory is not found.
    Rules: `_check_name_exists_in_factory` R2"""
    mk_machine("M2")
    result = M._check_name_exists_in_factory(db, workspace_id=w1.id, factory_id=f2.id, name="Press")

    # Then 1
    assert result is False


# [claude] MCM-N-03
def test_mcm_n_03__the_factory_id_seen_from_another_workspace_is_not_found(db, w2, f1, mk_machine):
    """MCM-N-03 — the factory id seen from another workspace is not found.
    Rules: `_check_name_exists_in_factory` R2"""
    mk_machine("M2")
    result = M._check_name_exists_in_factory(db, workspace_id=w2.id, factory_id=f1.id, name="Press")

    # Then 1
    assert result is False


# [claude] MCM-N-04
def test_mcm_n_04__a_soft_deleted_machine_is_ignored(db, w1, f1, mk_machine):
    """MCM-N-04 — a soft-deleted machine is ignored.
    Rules: `_check_name_exists_in_factory` R3"""
    mk_machine("MX")
    result = M._check_name_exists_in_factory(db, workspace_id=w1.id, factory_id=f1.id, name="Old Saw")

    # Then 1
    assert result is False


# [claude] MCM-N-05
@pytest.mark.xfail(strict=True, reason="BUG-952: Machine duplicate-name check is case- and whitespace-sensitive")
def test_mcm_n_05__name_press_matches_a_live_press(db, w1, f1, mk_machine):
    """MCM-N-05 — name "press" matches a live "Press".
    Rules: `_check_name_exists_in_factory` R4 [BUG-952]"""
    mk_machine("M2")
    result = M._check_name_exists_in_factory(db, workspace_id=w1.id, factory_id=f1.id, name="press")

    # Then 1
    assert result is True


# [claude] MCM-N-06
@pytest.mark.xfail(strict=True, reason="BUG-952: Machine duplicate-name check is case- and whitespace-sensitive")
def test_mcm_n_06__name_press_matches_a_live_press(db, w1, f1, mk_machine):
    """MCM-N-06 — name "PRESS" matches a live "Press".
    Rules: `_check_name_exists_in_factory` R4 [BUG-952]"""
    mk_machine("M2")
    result = M._check_name_exists_in_factory(db, workspace_id=w1.id, factory_id=f1.id, name="PRESS")

    # Then 1
    assert result is True


# [claude] MCM-N-07
@pytest.mark.xfail(strict=True, reason="BUG-952: Machine duplicate-name check is case- and whitespace-sensitive")
def test_mcm_n_07__name_press_matches_a_live_press(db, w1, f1, mk_machine):
    """MCM-N-07 — name "Press " matches a live "Press".
    Rules: `_check_name_exists_in_factory` R4 [BUG-952]"""
    mk_machine("M2")
    result = M._check_name_exists_in_factory(db, workspace_id=w1.id, factory_id=f1.id, name="Press ")

    # Then 1
    assert result is True


# [claude] MCM-N-08
@pytest.mark.xfail(strict=True, reason="BUG-952: Machine duplicate-name check is case- and whitespace-sensitive")
def test_mcm_n_08__name_tpress_matches_a_live_press(db, w1, f1, mk_machine):
    """MCM-N-08 — name "\\tPress" matches a live "Press".
    Rules: `_check_name_exists_in_factory` R4 [BUG-952]"""
    mk_machine("M2")
    result = M._check_name_exists_in_factory(db, workspace_id=w1.id, factory_id=f1.id, name="\tPress")

    # Then 1
    assert result is True


# [claude] MCM-N-09
def test_mcm_n_09__name_press_2_does_not_match_a_live_press(db, w1, f1, mk_machine):
    """MCM-N-09 — name "Press  2" does not match a live "Press".
    Rules: `_check_name_exists_in_factory` R4"""
    mk_machine("M2")
    result = M._check_name_exists_in_factory(db, workspace_id=w1.id, factory_id=f1.id, name="Press  2")

    # Then 1
    assert result is False


# [claude] MCM-N-10
def test_mcm_n_10__name_pres_does_not_match_a_live_press(db, w1, f1, mk_machine):
    """MCM-N-10 — name "Pres" does not match a live "Press".
    Rules: `_check_name_exists_in_factory` R4"""
    mk_machine("M2")
    result = M._check_name_exists_in_factory(db, workspace_id=w1.id, factory_id=f1.id, name="Pres")

    # Then 1
    assert result is False


# [claude] MCM-N-11
@pytest.mark.xfail(strict=True, reason="BUG-951: Machine duplicate-name check only scans 100 machines of the factory")
def test_mcm_n_11__every_one_of_101_live_machines_is_found_no_name_is_missed(db, w1, f1, bulk):
    """MCM-N-11 — every one of 101 live machines is found: no name is missed.
    Rules: `_check_name_exists_in_factory` R5 [BUG-951]"""
    names = bulk(101, "P")
    found = [M._check_name_exists_in_factory(db, workspace_id=w1.id, factory_id=f1.id, name=n) for n in names]

    # Then 1
    assert len(found) == 101
    # Then 2
    assert found.count(False) == 0


# [claude] MCM-N-12
@pytest.mark.xfail(strict=True, reason="BUG-951: Machine duplicate-name check only scans 100 machines of the factory")
def test_mcm_n_12__every_one_of_150_live_machines_is_found(db, w1, f1, bulk):
    """MCM-N-12 — every one of 150 live machines is found.
    Rules: `_check_name_exists_in_factory` R5 [BUG-951]"""
    names = bulk(150, "P")
    found = [M._check_name_exists_in_factory(db, workspace_id=w1.id, factory_id=f1.id, name=n) for n in names]

    # Then 1
    assert len(found) == 150
    # Then 2
    assert found.count(False) == 0


# [claude] MCM-N-13
def test_mcm_n_13__every_one_of_exactly_100_live_machines_is_found(db, w1, f1, bulk):
    """MCM-N-13 — every one of exactly 100 live machines is found.
    Rules: `_check_name_exists_in_factory` R5"""
    names = bulk(100, "P")
    found = [M._check_name_exists_in_factory(db, workspace_id=w1.id, factory_id=f1.id, name=n) for n in names]

    # Then 1
    assert len(found) == 100
    # Then 2
    assert found.count(False) == 0


# [claude] MCM-N-14
def test_mcm_n_14__soft_deleted_machines_do_not_use_up_a_place(db, w1, f1, mk_machine, bulk):
    """MCM-N-14 — soft-deleted machines do not use up a place.
    Rules: `_check_name_exists_in_factory` R5, R3"""
    bulk(100, "P", is_deleted=True, is_active=False)
    mk_machine(name="Zeta")
    result = M._check_name_exists_in_factory(db, workspace_id=w1.id, factory_id=f1.id, name="Zeta")

    # Then 1
    assert result is True


# [claude] MCM-N-15
def test_mcm_n_15__the_excluded_machine_is_ignored(db, w1, f1, mk_machine):
    """MCM-N-15 — the excluded machine is ignored.
    Rules: `_check_name_exists_in_factory` R6"""
    m2 = mk_machine("M2")
    result = M._check_name_exists_in_factory(db, workspace_id=w1.id, factory_id=f1.id, name="Press", exclude_id=m2.id)

    # Then 1
    assert result is False


# [claude] MCM-N-16
def test_mcm_n_16__excluding_another_machine_still_finds_the_match(db, w1, f1, mk_machine):
    """MCM-N-16 — excluding another machine still finds the match.
    Rules: `_check_name_exists_in_factory` R6"""
    m1 = mk_machine("M1")
    mk_machine("M2")
    result = M._check_name_exists_in_factory(db, workspace_id=w1.id, factory_id=f1.id, name="Press", exclude_id=m1.id)

    # Then 1
    assert result is True


# [claude] MCM-N-17
def test_mcm_n_17__a_same_named_machine_in_another_factory_is_not_rescued_by_exclude_id(db, w1, f1, mk_machine):
    """MCM-N-17 — a same-named machine in another factory is not rescued by exclude_id.
    Rules: `_check_name_exists_in_factory` R6, R2"""
    m2 = mk_machine("M2")
    mk_machine("M3", name="Press")
    result = M._check_name_exists_in_factory(db, workspace_id=w1.id, factory_id=f1.id, name="Press", exclude_id=m2.id)

    # Then 1
    assert result is False


# [claude] MCM-N-18
def test_mcm_n_18__a_factory_without_machines_gives_false(db, w1, f2, mk_machine):
    """MCM-N-18 — a factory without machines gives False.
    Rules: `_check_name_exists_in_factory` R7"""
    mk_machine("M2")
    result = M._check_name_exists_in_factory(db, workspace_id=w1.id, factory_id=f2.id, name="Press")

    # Then 1
    assert result is False


# [claude] MCM-N-19
def test_mcm_n_19__an_unknown_factory_gives_false(db, w1, mk_machine):
    """MCM-N-19 — an unknown factory gives False.
    Rules: `_check_name_exists_in_factory` R7"""
    mk_machine("M2")
    result = M._check_name_exists_in_factory(db, workspace_id=w1.id, factory_id=MISSING, name="Press")

    # Then 1
    assert result is False


# [claude] MCM-N-20
def test_mcm_n_20__in_a_soft_deleted_factory_the_answer_is_false(db, w1, fd, mk_machine):
    """MCM-N-20 — in a soft-deleted factory the answer is False.
    Rules: `_check_name_exists_in_factory` R8 [BUG-891]"""
    mk_machine("MF")
    result = M._check_name_exists_in_factory(db, workspace_id=w1.id, factory_id=fd.id, name="Kiln")

    # Then 1
    assert result is False
