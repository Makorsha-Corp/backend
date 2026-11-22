"""Unit tests for app/managers/machine_activity_manager.py.

Implements tests/unit/managers/machine_activity_manager.cases.md, one test per
case, in card order. Real Postgres session (`db` fixture). Nothing is patched
(the cases have no externals and no race simulation); the one spy is the commit
spy the Conventions name under "Rolled back".

Normal mode: every test is written from its card and carries a `# [claude] <ID>`
comment. Row names of the cards are the lower-case names here (M1 -> m1, `A.id`
-> `a.id`); `# Then N` marks the checks of the card's Then line N.
"""
# ruff: noqa: SIM117, DTZ001, FURB157  (Conventions prescribe the nested `with`, naive datetimes, Decimal("100"))
import enum
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
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

from app.managers.machine_activity_manager import (
    MACHINE_ITEM_LOG_FIELDS,
    MACHINE_LOG_FIELDS,
    MachineActivityManager,
    machine_activity_manager,
)
from app.models.enums import MaintenanceTypeEnum
from app.models.factory import Factory
from app.models.machine import Machine
from app.models.machine_activity_event import MachineActivityEvent
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "M = the singleton machine_activity_manager"
M = machine_activity_manager

# Convention "MISSING": an id no row of any table has
MISSING = 999999999

# Conventions "T1, T2, T3"
T1 = datetime(2026, 3, 4, 10, 0, 0)
T2 = datetime(2026, 3, 5, 10, 0, 0)
T3 = datetime(2026, 3, 6, 10, 0, 0)

# Convention "FIELDS", in that order
FIELDS = {"a": "Alpha", "b": "Beta", "c": "Gamma"}


# Convention "Kind": a plain enum of the test file
class Kind(enum.Enum):
    A = 1
    B = 2


# --------------------------------------------------------------------------- #
# Conventions -> fixtures (the standing rows). Each fixture depends on the one
# before it, so the rows are inserted in the order Conventions list them.
# `standing_rows` builds all of them in every test that uses `db`; pure cards
# (no `db`) build none.
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


def _factory(db, ws, name, abbreviation, is_deleted=False):
    return _add(db, Factory(workspace_id=ws.id, name=name, abbreviation=abbreviation, is_deleted=is_deleted))


@pytest.fixture
def f1(db, w1, u2):
    return _factory(db, w1, "Factory One", "F1")


# Convention: FD has is_deleted True, is_active stays True
@pytest.fixture
def fd(db, w1, f1):
    return _factory(db, w1, "Old Plant", "OP", is_deleted=True)


@pytest.fixture
def f9(db, w2, fd):
    return _factory(db, w2, "Factory Nine", "F9")


def _machine(db, ws, factory, name, is_active=True, is_deleted=False):
    return _add(db, Machine(
        workspace_id=ws.id, factory_id=factory.id, name=name, is_active=is_active, is_deleted=is_deleted,
    ))


@pytest.fixture
def m1(db, w1, f1, f9):
    return _machine(db, w1, f1, "Press 1")


@pytest.fixture
def m2(db, w1, f1, m1):
    return _machine(db, w1, f1, "Press 2")


@pytest.fixture
def md(db, w1, f1, m2):
    return _machine(db, w1, f1, "Press 4", is_active=False, is_deleted=True)


# MF is live, in a soft-deleted factory
@pytest.fixture
def mf(db, w1, fd, md):
    return _machine(db, w1, fd, "Lost Press")


@pytest.fixture
def ma(db, w1, f1, mf):
    return _machine(db, w1, f1, "Idle Press", is_active=False)


@pytest.fixture
def m9(db, w2, f9, ma):
    return _machine(db, w2, f9, "Far Press")


# Convention "Standing rows": in every test, in this order. M9 is the last of the chain.
@pytest.fixture(autouse=True)
def standing_rows(request):
    if "db" in request.fixturenames:
        request.getfixturevalue("m9")


# --------------------------------------------------------------------------- #
# Conventions -> Given rows. Each builder inserts and flushes one row, so ids
# rise in the order written. `metadata_json` and `performed_by` are not passed
# unless the card gives them (metadata_json=None is passed as a keyword).
# --------------------------------------------------------------------------- #

def mk_event(db, workspace, machine, created_at, **columns):
    """Convention "event"."""
    fields = {"event_type": "item_added", "description": "Logged", **columns}
    return _add(db, MachineActivityEvent(
        workspace_id=workspace.id, machine_id=machine.id, created_at=created_at, **fields,
    ))


def mk_status(db, workspace, machine, created_at, **columns):
    """Convention "status row"."""
    fields = {"event_type": "status_updated", "metadata_json": {"status": "RUNNING"}, **columns}
    return mk_event(db, workspace, machine, created_at, **fields)


def mk_log(db, workspace, machine, n):
    """Convention "log(n)": n events by one add_all and one flush."""
    db.add_all([
        MachineActivityEvent(
            workspace_id=workspace.id, machine_id=machine.id, event_type="item_added",
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
    return db.execute(select(MachineActivityEvent).where(MachineActivityEvent.id == event_id)).scalar_one()


def event_count(db):
    """Convention "nothing written": the row count of machine_activity_events, all workspaces."""
    return db.execute(select(func.count()).select_from(MachineActivityEvent)).scalar_one()


def count_events(db, **filters):
    """Convention "count:": rows in all workspaces, with the filter stated."""
    return db.execute(select(func.count()).select_from(MachineActivityEvent).filter_by(**filters)).scalar_one()


def ids(x):
    """Convention "ids(x)"."""
    return [pair[0].id for pair in x]


def stored_meta(db, row):
    """Convention "stored_meta(X)"."""
    return tuple(db.execute(
        text("SELECT metadata::text, metadata IS NULL FROM machine_activity_events WHERE id = :i"), {"i": row.id},
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
# MachineActivityManager.format_field_value
# --------------------------------------------------------------------------- #

# [claude] MAC-FV-01
def test_mac_fv_01__none_gives_none():
    """MAC-FV-01 — None gives None.
    Rules: `format_field_value` R1."""
    value = None
    result = M.format_field_value(value)
    # Then 1
    assert result is None


# [claude] MAC-FV-02
def test_mac_fv_02__a_str_enum_member_gives_its_value():
    """MAC-FV-02 — a str enum member gives its value.
    Rules: `format_field_value` R2."""
    value = MaintenanceTypeEnum.REPAIR
    result = M.format_field_value(value)
    # Then 1
    assert result == "REPAIR"


# [claude] MAC-FV-03
def test_mac_fv_03__a_plain_enum_member_gives_the_text_of_its_value():
    """MAC-FV-03 — a plain enum member gives the text of its value.
    Rules: `format_field_value` R2."""
    value = Kind.A
    result = M.format_field_value(value)
    # Then 1
    assert result == "1"


# [claude] MAC-FV-04
def test_mac_fv_04__any_object_with_a_value_attribute_gives_the_text_of_that_att():
    """MAC-FV-04 — any object with a value attribute gives the text of that attribute.
    Rules: `format_field_value` R2."""
    value = SimpleNamespace(value=7)
    result = M.format_field_value(value)
    # Then 1
    assert result == "7"


# [claude] MAC-FV-05
def test_mac_fv_05__the_value_attribute_is_checked_before_the_date_checks():
    """MAC-FV-05 — the value attribute is checked before the date checks.
    Rules: `format_field_value` R2."""
    class Stamp(date):
        value = 7
    value = Stamp(2026, 3, 5)
    result = M.format_field_value(value)
    # Then 1
    assert result == "7"


# [claude] MAC-FV-06
def test_mac_fv_06__a_datetime_drops_its_seconds():
    """MAC-FV-06 — a datetime drops its seconds.
    Rules: `format_field_value` R3."""
    value = datetime(2026, 3, 5, 7, 9, 59)
    result = M.format_field_value(value)
    # Then 1
    assert result == "2026-03-05 07:09"


# [claude] MAC-FV-07
def test_mac_fv_07__a_datetime_at_midnight_keeps_its_time():
    """MAC-FV-07 — a datetime at midnight keeps its time.
    Rules: `format_field_value` R3."""
    value = datetime(2026, 3, 5, 0, 0, 0)
    result = M.format_field_value(value)
    # Then 1
    assert result == "2026-03-05 00:00"


# [claude] MAC-FV-08
def test_mac_fv_08__a_datetime_with_a_time_zone_is_not_converted():
    """MAC-FV-08 — a datetime with a time zone is not converted.
    Rules: `format_field_value` R3."""
    value = datetime(2026, 3, 5, 7, 9, 59, tzinfo=timezone(timedelta(hours=6)))
    result = M.format_field_value(value)
    # Then 1
    assert result == "2026-03-05 07:09"


# [claude] MAC-FV-09
def test_mac_fv_09__a_date_gives_its_iso_form():
    """MAC-FV-09 — a date gives its ISO form.
    Rules: `format_field_value` R4."""
    value = date(2026, 3, 5)
    result = M.format_field_value(value)
    # Then 1
    assert result == "2026-03-05"


# [claude] MAC-FV-10
def test_mac_fv_10__a_decimal_keeps_its_scale():
    """MAC-FV-10 — a Decimal keeps its scale.
    Rules: `format_field_value` R5."""
    value = Decimal("1.50")
    result = M.format_field_value(value)
    # Then 1
    assert result == "1.50"


# [claude] MAC-FV-11
def test_mac_fv_11__a_whole_decimal_gains_no_decimals():
    """MAC-FV-11 — a whole Decimal gains no decimals.
    Rules: `format_field_value` R5."""
    value = Decimal("100")
    result = M.format_field_value(value)
    # Then 1
    assert result == "100"


# [claude] MAC-FV-12
def test_mac_fv_12__an_int_gives_its_text():
    """MAC-FV-12 — an int gives its text.
    Rules: `format_field_value` R5."""
    value = 5
    result = M.format_field_value(value)
    # Then 1
    assert result == "5"


# [claude] MAC-FV-13
def test_mac_fv_13__zero_gives_0_not_none():
    """MAC-FV-13 — zero gives "0", not None.
    Rules: `format_field_value` R5."""
    value = 0
    result = M.format_field_value(value)
    # Then 1
    assert result == "0"


# [claude] MAC-FV-14
def test_mac_fv_14__false_gives_false_not_none():
    """MAC-FV-14 — False gives "False", not None.
    Rules: `format_field_value` R5."""
    value = False
    result = M.format_field_value(value)
    # Then 1
    assert result == "False"


# [claude] MAC-FV-15
def test_mac_fv_15__an_empty_string_stays_an_empty_string():
    """MAC-FV-15 — an empty string stays an empty string.
    Rules: `format_field_value` R5."""
    value = ""
    result = M.format_field_value(value)
    # Then 1
    assert result == ""


# [claude] MAC-FV-16
def test_mac_fv_16__a_padded_string_is_not_trimmed():
    """MAC-FV-16 — a padded string is not trimmed.
    Rules: `format_field_value` R5."""
    value = " x "
    result = M.format_field_value(value)
    # Then 1
    assert result == " x "


# [claude] MAC-FV-17
def test_mac_fv_17__the_method_can_be_called_on_the_class():
    """MAC-FV-17 — the method can be called on the class.
    Rules: `format_field_value` R5, Facts (static)."""
    value = 5
    result = MachineActivityManager.format_field_value(value)
    # Then 1
    assert result == "5"


# --------------------------------------------------------------------------- #
# MachineActivityManager.collect_field_changes
# --------------------------------------------------------------------------- #

# [claude] MAC-CF-01
def test_mac_cf_01__a_changed_tracked_field_gives_one_entry_with_four_keys():
    """MAC-CF-01 — a changed tracked field gives one entry with four keys.
    Rules: `collect_field_changes` R1, Returns."""
    record = SimpleNamespace(a=1, b=2, c=3)
    result = M.collect_field_changes(record, {"a": 5}, FIELDS)
    # Then 1
    assert result == [{"field": "a", "label": "Alpha", "from_value": "1", "to_value": "5"}]


# [claude] MAC-CF-02
def test_mac_cf_02__both_sides_go_through_the_value_text():
    """MAC-CF-02 — both sides go through the value text.
    Rules: `collect_field_changes` R1."""
    record = SimpleNamespace(a=Kind.A, b=2, c=3)
    result = M.collect_field_changes(record, {"a": date(2026, 3, 6)}, FIELDS)
    # Then 1
    assert result == [{"field": "a", "label": "Alpha", "from_value": "1", "to_value": "2026-03-06"}]


# [claude] MAC-CF-03
def test_mac_cf_03__entries_follow_the_order_of_fields_not_of_the_update():
    """MAC-CF-03 — entries follow the order of fields, not of the update.
    Rules: `collect_field_changes` R2."""
    record = SimpleNamespace(a=1, b=5, c="x")
    result = M.collect_field_changes(record, {"c": "y", "a": 2}, FIELDS)
    # Then 1
    assert [entry["field"] for entry in result] == ["a", "c"]
    # Then 2
    assert result[0] == {"field": "a", "label": "Alpha", "from_value": "1", "to_value": "2"}
    # Then 3
    assert result[1] == {"field": "c", "label": "Gamma", "from_value": "x", "to_value": "y"}


# [claude] MAC-CF-04
def test_mac_cf_04__a_tracked_field_absent_from_the_update_is_not_read_on_the_re():
    """MAC-CF-04 — a tracked field absent from the update is not read on the record.
    Rules: `collect_field_changes` R3."""
    record = SimpleNamespace(a=1)
    result = M.collect_field_changes(record, {"a": 2}, FIELDS)
    # Then 1
    assert result == [{"field": "a", "label": "Alpha", "from_value": "1", "to_value": "2"}]


# [claude] MAC-CF-05
def test_mac_cf_05__a_key_that_is_not_tracked_is_ignored():
    """MAC-CF-05 — a key that is not tracked is ignored.
    Rules: `collect_field_changes` R4."""
    record = SimpleNamespace(a=1, b=2, c=3)
    result = M.collect_field_changes(record, {"updated_by": 9, "a": 2}, FIELDS)
    # Then 1
    assert result == [{"field": "a", "label": "Alpha", "from_value": "1", "to_value": "2"}]


# [claude] MAC-CF-06
def test_mac_cf_06__the_same_value_gives_no_entry():
    """MAC-CF-06 — the same value gives no entry.
    Rules: `collect_field_changes` R5."""
    record = SimpleNamespace(a=1, b=2, c=3)
    result = M.collect_field_changes(record, {"a": 1}, FIELDS)
    # Then 1
    assert result == []


# [claude] MAC-CF-07
def test_mac_cf_07__decimals_equal_in_value_give_no_entry_whatever_their_scale():
    """MAC-CF-07 — Decimals equal in value give no entry, whatever their scale.
    Rules: `collect_field_changes` R5."""
    record = SimpleNamespace(a=Decimal("100.00"), b=2, c=3)
    result = M.collect_field_changes(record, {"a": Decimal("100")}, FIELDS)
    # Then 1
    assert result == []


# [claude] MAC-CF-08
def test_mac_cf_08__a_str_enum_member_and_its_string_give_no_entry():
    """MAC-CF-08 — a str enum member and its string give no entry.
    Rules: `collect_field_changes` R5."""
    record = SimpleNamespace(a=MaintenanceTypeEnum.REPAIR, b=2, c=3)
    result = M.collect_field_changes(record, {"a": "REPAIR"}, FIELDS)
    # Then 1
    assert result == []


# [claude] MAC-CF-09
def test_mac_cf_09__1_and_true_are_equal_so_no_entry():
    """MAC-CF-09 — 1 and True are equal, so no entry.
    Rules: `collect_field_changes` R5."""
    record = SimpleNamespace(a=1, b=2, c=3)
    result = M.collect_field_changes(record, {"a": True}, FIELDS)
    # Then 1
    assert result == []


# [claude] MAC-CF-10
def test_mac_cf_10__none_and_none_give_no_entry():
    """MAC-CF-10 — None and None give no entry.
    Rules: `collect_field_changes` R5."""
    record = SimpleNamespace(a=None, b=2, c=3)
    result = M.collect_field_changes(record, {"a": None}, FIELDS)
    # Then 1
    assert result == []


# [claude] MAC-CF-11
def test_mac_cf_11__none_to_a_value_is_a_change():
    """MAC-CF-11 — None to a value is a change.
    Rules: `collect_field_changes` R6."""
    record = SimpleNamespace(a=None, b=2, c=3)
    result = M.collect_field_changes(record, {"a": 0}, FIELDS)
    # Then 1
    assert result == [{"field": "a", "label": "Alpha", "from_value": None, "to_value": "0"}]


# [claude] MAC-CF-12
def test_mac_cf_12__a_value_to_none_is_a_change():
    """MAC-CF-12 — a value to None is a change.
    Rules: `collect_field_changes` R6."""
    record = SimpleNamespace(a=0, b=2, c=3)
    result = M.collect_field_changes(record, {"a": None}, FIELDS)
    # Then 1
    assert result == [{"field": "a", "label": "Alpha", "from_value": "0", "to_value": None}]


# [claude] MAC-CF-13
def test_mac_cf_13__none_to_an_empty_string_is_a_change():
    """MAC-CF-13 — None to an empty string is a change.
    Rules: `collect_field_changes` R6."""
    record = SimpleNamespace(a=None, b=2, c=3)
    result = M.collect_field_changes(record, {"a": ""}, FIELDS)
    # Then 1
    assert result == [{"field": "a", "label": "Alpha", "from_value": None, "to_value": ""}]


# [claude] MAC-CF-14
def test_mac_cf_14__the_new_value_is_compared_as_given_not_as_the_column_would_s():
    """MAC-CF-14 — the new value is compared as given, not as the column would store it.
    Rules: `collect_field_changes` R7."""
    record = SimpleNamespace(a=Decimal("12.35"), b=2, c=3)
    result = M.collect_field_changes(record, {"a": Decimal("12.354")}, FIELDS)
    # Then 1
    assert result == [{"field": "a", "label": "Alpha", "from_value": "12.35", "to_value": "12.354"}]


# [claude] MAC-CF-15
def test_mac_cf_15__the_new_value_is_shown_as_given_its_scale_included():
    """MAC-CF-15 — the new value is shown as given, its scale included.
    Rules: `collect_field_changes` R7."""
    record = SimpleNamespace(a=Decimal("100.00"), b=2, c=3)
    result = M.collect_field_changes(record, {"a": Decimal("100.5")}, FIELDS)
    # Then 1
    assert result == [{"field": "a", "label": "Alpha", "from_value": "100.00", "to_value": "100.5"}]


# [claude] MAC-CF-16
def test_mac_cf_16__an_empty_update_gives_an_empty_list():
    """MAC-CF-16 — an empty update gives an empty list.
    Rules: `collect_field_changes` R8."""
    record = SimpleNamespace(a=1, b=2, c=3)
    result = M.collect_field_changes(record, {}, FIELDS)
    # Then 1
    assert result == []


# [claude] MAC-CF-17
def test_mac_cf_17__empty_fields_give_an_empty_list():
    """MAC-CF-17 — empty fields give an empty list.
    Rules: `collect_field_changes` R8."""
    record = SimpleNamespace(a=1, b=2, c=3)
    result = M.collect_field_changes(record, {"a": 2}, {})
    # Then 1
    assert result == []


# [claude] MAC-CF-18
def test_mac_cf_18__the_record_is_not_changed_and_nothing_touches_the_database(db, m1):
    """MAC-CF-18 — the record is not changed and nothing touches the database.
    Rules: `collect_field_changes` R9."""
    with sql_recorder(db) as sql_log:
        result = M.collect_field_changes(m1, {"name": "Changed"}, MACHINE_LOG_FIELDS)
    # Then 1
    assert result == [{"field": "name", "label": "Name", "from_value": "Press 1", "to_value": "Changed"}]
    # Then 2
    assert m1.name == "Press 1"
    # Then 3
    assert m1 not in db.dirty
    # Then 4
    assert sql_log == []


# [claude] MAC-CF-19
def test_mac_cf_19__a_tracked_field_the_record_lacks_raises_attributeerror():
    """MAC-CF-19 — a tracked field the record lacks raises AttributeError.
    Rules: `collect_field_changes` Errors row 1."""
    record = SimpleNamespace(a=1)
    # Then 1
    with pytest.raises(AttributeError):
        M.collect_field_changes(record, {"b": 2}, FIELDS)


# [claude] MAC-CF-20
def test_mac_cf_20__machine_log_fields_lists_the_machine_s_tracked_fields_in_ord():
    """MAC-CF-20 — MACHINE_LOG_FIELDS lists the machine's tracked fields in order.
    Rules: Facts (`MACHINE_LOG_FIELDS`)."""
    result = list(MACHINE_LOG_FIELDS.items())
    # Then 1
    assert result == [("name", "Name"), ("factory_id", "Factory"), ("factory_section_id", "Section"), ("model_number", "Model number"), ("manufacturer", "Manufacturer"), ("note", "Note")]


# [claude] MAC-CF-21
def test_mac_cf_21__machine_item_log_fields_lists_the_stock_row_s_tracked_fields():
    """MAC-CF-21 — MACHINE_ITEM_LOG_FIELDS lists the stock row's tracked fields in order.
    Rules: Facts (`MACHINE_ITEM_LOG_FIELDS`)."""
    result = list(MACHINE_ITEM_LOG_FIELDS.items())
    # Then 1
    assert result == [("qty", "Quantity"), ("req_qty", "Required quantity"), ("defective_qty", "Defective quantity")]


# --------------------------------------------------------------------------- #
# MachineActivityManager.log_event
# --------------------------------------------------------------------------- #

# [claude] MAC-LE-01
def test_mac_le_01__one_row_is_stored_with_every_value_given(db, w1, u2, m1):
    """MAC-LE-01 — one row is stored with every value given.
    Rules: `log_event` R1, Returns."""
    result = M.log_event(db, machine_id=m1.id, workspace_id=w1.id, event_type="item_added", description="Added Bolt", performed_by=u2.id, metadata={"quantity": 3})
    # Then 1
    assert isinstance(result, MachineActivityEvent)
    # Then 2
    assert result.id is not None
    # Then 3
    row = reread_event(db, result.id)
    assert row.workspace_id == w1.id
    assert row.machine_id == m1.id
    assert row.event_type == "item_added"
    assert row.description == "Added Bolt"
    assert row.performed_by == u2.id
    # Then 4
    row = reread_event(db, result.id)
    assert row.metadata_json == {"quantity": 3}
    # Then 5
    assert count_events(db, machine_id=m1.id) == 1


# [claude] MAC-LE-02
def test_mac_le_02__positional_arguments_work_in_the_order_of_the_signature(db, w1, u2, m1):
    """MAC-LE-02 — positional arguments work, in the order of the signature.
    Rules: `log_event` R1, Facts (positional-or-keyword)."""
    result = M.log_event(db, m1.id, w1.id, "item_added", "Added Bolt", u2.id, {"quantity": 3})
    # Then 1
    row = reread_event(db, result.id)
    assert row.machine_id == m1.id
    assert row.workspace_id == w1.id
    assert row.event_type == "item_added"
    assert row.description == "Added Bolt"
    assert row.performed_by == u2.id
    # Then 2
    row = reread_event(db, result.id)
    assert row.metadata_json == {"quantity": 3}


# [claude] MAC-LE-03
def test_mac_le_03__two_identical_calls_give_two_rows(db, w1, m1):
    """MAC-LE-03 — two identical calls give two rows.
    Rules: `log_event` R1."""
    first = M.log_event(db, machine_id=m1.id, workspace_id=w1.id, event_type="updated", description="Same")
    result = M.log_event(db, machine_id=m1.id, workspace_id=w1.id, event_type="updated", description="Same")
    # Then 1
    assert result.id != first.id
    # Then 2
    assert count_events(db, machine_id=m1.id, description="Same") == 2


# [claude] MAC-LE-04
def test_mac_le_04__the_call_is_one_insert_no_other_row_and_not_the_machine_chan(db, w1, m1, m2):
    """MAC-LE-04 — the call is one INSERT: no other row and not the machine change, no lock.
    Rules: `log_event` R1, Side effects, Overview."""
    a = mk_event(db, w1, m1, T1)
    b = mk_event(db, w1, m2, T2)
    before_a = snap(db, a)
    before_b = snap(db, b)
    before_m1 = snap(db, m1)
    with sql_recorder(db) as sql_log:
        result = M.log_event(db, machine_id=m1.id, workspace_id=w1.id, event_type="updated", description="Edited")
    # Then 1
    assert result.id not in {a.id, b.id}
    # Then 2
    assert len(written(sql_log)) == 1
    # Then 3
    assert written(sql_log)[0].strip().upper().startswith("INSERT INTO MACHINE_ACTIVITY_EVENTS")
    # Then 4
    assert locked(sql_log) == []
    # Then 5
    assert reread_snap(db, a) == before_a
    # Then 6
    assert reread_snap(db, b) == before_b
    # Then 7
    assert reread_snap(db, m1) == before_m1


# [claude] MAC-LE-05
def test_mac_le_05__left_out_metadata_is_stored_as_json_null_and_performer_as_nu(db, w1, m1):
    """MAC-LE-05 — left out, metadata is stored as JSON null and performer as NULL.
    Rules: `log_event` R2."""
    result = M.log_event(db, machine_id=m1.id, workspace_id=w1.id, event_type="updated", description="Edited")
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread_event(db, result.id)
    assert row.metadata_json is None
    assert row.performed_by is None
    # Then 3
    db.expire_all()
    assert stored_meta(db, result) == ("null", False)


# [claude] MAC-LE-06
def test_mac_le_06__metadata_none_passed_explicitly_is_stored_as_json_null(db, w1, m1):
    """MAC-LE-06 — metadata None passed explicitly is stored as JSON null.
    Rules: `log_event` R2."""
    result = M.log_event(db, machine_id=m1.id, workspace_id=w1.id, event_type="updated", description="Edited", metadata=None)
    # Then 1
    row = reread_event(db, result.id)
    assert row.metadata_json is None
    # Then 2
    db.expire_all()
    assert stored_meta(db, result) == ("null", False)


# [claude] MAC-LE-07
def test_mac_le_07__empty_metadata_is_stored_as_an_empty_object_not_as_null(db, w1, m1):
    """MAC-LE-07 — empty metadata is stored as an empty object, not as null.
    Rules: `log_event` R2."""
    result = M.log_event(db, machine_id=m1.id, workspace_id=w1.id, event_type="updated", description="Edited", metadata={})
    # Then 1
    row = reread_event(db, result.id)
    assert row.metadata_json == {}
    # Then 2
    db.expire_all()
    assert stored_meta(db, result) == ("{}", False)


# [claude] MAC-LE-08
def test_mac_le_08__nested_metadata_comes_back_equal_none_inside_it_included(db, w1, m1):
    """MAC-LE-08 — nested metadata comes back equal, None inside it included.
    Rules: `log_event` R3."""
    result = M.log_event(db, machine_id=m1.id, workspace_id=w1.id, event_type="updated", description="Edited", metadata={"a": [1, {"b": None}]})
    # Then 1
    row = reread_event(db, result.id)
    assert row.metadata_json == {"a": [1, {"b": None}]}


# [claude] MAC-LE-09
def test_mac_le_09__a_float_in_metadata_comes_back_equal(db, w1, m1):
    """MAC-LE-09 — a float in metadata comes back equal.
    Rules: `log_event` R3."""
    result = M.log_event(db, machine_id=m1.id, workspace_id=w1.id, event_type="item_added", description="Added", metadata={"quantity": 2.5})
    # Then 1
    row = reread_event(db, result.id)
    assert row.metadata_json == {"quantity": 2.5}


# [claude] MAC-LE-10
def test_mac_le_10__empty_values_inside_metadata_are_kept(db, w1, m1):
    """MAC-LE-10 — empty values inside metadata are kept.
    Rules: `log_event` R3."""
    result = M.log_event(db, machine_id=m1.id, workspace_id=w1.id, event_type="updated", description="Edited", metadata={"note": None, "changes": [], "flag": False, "qty": 0, "text": ""})
    # Then 1
    row = reread_event(db, result.id)
    assert row.metadata_json == {"note": None, "changes": [], "flag": False, "qty": 0, "text": ""}


# [claude] MAC-LE-11
def test_mac_le_11__an_empty_event_type_is_stored(db, w1, m1):
    """MAC-LE-11 — an empty event type is stored.
    Rules: `log_event` R4."""
    result = M.log_event(db, machine_id=m1.id, workspace_id=w1.id, event_type="", description="Edited")
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread_event(db, result.id)
    assert row.event_type == ""


# [claude] MAC-LE-12
def test_mac_le_12__a_type_on_no_list_is_stored(db, w1, m1):
    """MAC-LE-12 — a type on no list is stored.
    Rules: `log_event` R4."""
    result = M.log_event(db, machine_id=m1.id, workspace_id=w1.id, event_type="anything_goes", description="Edited")
    # Then 1
    row = reread_event(db, result.id)
    assert row.event_type == "anything_goes"


# [claude] MAC-LE-13
def test_mac_le_13__an_event_type_of_exactly_50_characters_is_stored(db, w1, m1):
    """MAC-LE-13 — an event type of exactly 50 characters is stored.
    Rules: `log_event` R4, Inputs."""
    result = M.log_event(db, machine_id=m1.id, workspace_id=w1.id, event_type="x" * 50, description="Edited")
    # Then 1
    row = reread_event(db, result.id)
    assert row.event_type == "x" * 50


# [claude] MAC-LE-14
def test_mac_le_14__an_event_type_of_51_characters_is_refused_by_the_database_no(db, w1, m1):
    """MAC-LE-14 — an event type of 51 characters is refused by the database, no row.
    Rules: `log_event` Errors row 6, Inputs."""
    before_count = event_count(db)
    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            M.log_event(db, machine_id=m1.id, workspace_id=w1.id, event_type="x" * 51, description="Edited")
    # Then 2
    assert isinstance(exc.value.orig, StringDataRightTruncation)
    # Then 3
    assert exc.value.orig.pgcode == "22001"
    # Then 4
    assert event_count(db) == before_count


# [claude] MAC-LE-15
def test_mac_le_15__an_empty_description_is_stored(db, w1, m1):
    """MAC-LE-15 — an empty description is stored.
    Rules: `log_event` R4."""
    result = M.log_event(db, machine_id=m1.id, workspace_id=w1.id, event_type="updated", description="")
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread_event(db, result.id)
    assert row.description == ""


# [claude] MAC-LE-16
def test_mac_le_16__event_type_and_description_are_stored_as_given_not_trimmed(db, w1, m1):
    """MAC-LE-16 — event type and description are stored as given, not trimmed.
    Rules: `log_event` R1."""
    result = M.log_event(db, machine_id=m1.id, workspace_id=w1.id, event_type=" Item_Added ", description="  Added  ")
    # Then 1
    row = reread_event(db, result.id)
    assert row.event_type == " Item_Added "
    assert row.description == "  Added  "


# [claude] MAC-LE-17
def test_mac_le_17__created_at_is_set_on_the_row_with_no_time_zone(db, w1, m1):
    """MAC-LE-17 — created_at is set on the row, with no time zone.
    Rules: `log_event` R5."""
    result = M.log_event(db, machine_id=m1.id, workspace_id=w1.id, event_type="updated", description="Edited")
    # Then 1
    assert result.created_at is not None
    # Then 2
    row = reread_event(db, result.id)
    assert row.created_at is not None
    assert row.created_at.tzinfo is None


# [claude] MAC-LE-18
@pytest.mark.xfail(strict=True, reason="BUG-1091: Activity row can be written for another workspace's machine")
def test_mac_le_18__another_workspace_s_machine_is_refused_like_an_unknown_one_n(db, w1, u1, m9):
    """MAC-LE-18 — another workspace's machine is refused like an unknown one, nothing written.
    Rules: `log_event` R6 [BUG-1091], Errors row 1, HR-16."""
    before_count = event_count(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.log_event(db, machine_id=m9.id, workspace_id=w1.id, event_type="attachment_added", description="Attached a.png", performed_by=u1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Machine with ID {m9.id} not found"
    # Then 4
    assert len(db.new) == 0
    # Then 5
    assert event_count(db) == before_count
    # Then 6
    assert count_events(db, machine_id=m9.id) == 0


# [claude] MAC-LE-19
@pytest.mark.xfail(strict=True, reason="BUG-1091: Activity row can be written for another workspace's machine")
def test_mac_le_19__another_workspace_s_soft_deleted_machine_is_refused_too(db, w1, w2, f9):
    """MAC-LE-19 — another workspace's soft-deleted machine is refused too.
    Rules: `log_event` R6 [BUG-1091], R7, Errors row 1, HR-16."""
    m8 = _machine(db, w2, f9, "Far Old Press", is_active=False, is_deleted=True)
    before_count = event_count(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.log_event(db, machine_id=m8.id, workspace_id=w1.id, event_type="deactivated", description="Removed")
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Machine with ID {m8.id} not found"
    # Then 4
    assert len(db.new) == 0
    # Then 5
    assert event_count(db) == before_count


# [claude] MAC-LE-20
@pytest.mark.xfail(strict=True, reason="BUG-1091: Activity row can be written for another workspace's machine")
def test_mac_le_20__an_unknown_machine_gets_the_same_404(db, w1):
    """MAC-LE-20 — an unknown machine gets the same 404.
    Rules: `log_event` R6 [BUG-1091], Errors rows 1, 2."""
    before_count = event_count(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with db.begin_nested():
            M.log_event(db, machine_id=MISSING, workspace_id=w1.id, event_type="updated", description="Edited")
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine with ID 999999999 not found"
    # Then 4
    assert event_count(db) == before_count


# [claude] MAC-LE-21
@pytest.mark.xfail(strict=True, reason="BUG-1091: Activity row can be written for another workspace's machine")
def test_mac_le_21__machine_id_0_gets_the_same_404(db, w1):
    """MAC-LE-21 — machine id 0 gets the same 404.
    Rules: `log_event` R6 [BUG-1091], Errors rows 1, 2."""
    before_count = event_count(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with db.begin_nested():
            M.log_event(db, machine_id=0, workspace_id=w1.id, event_type="updated", description="Edited")
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine with ID 0 not found"
    # Then 4
    assert event_count(db) == before_count


# [claude] MAC-LE-22
@pytest.mark.xfail(strict=True, reason="BUG-1091: Activity row can be written for another workspace's machine")
def test_mac_le_22__an_unknown_workspace_gets_the_same_404_naming_the_machine(db, m1):
    """MAC-LE-22 — an unknown workspace gets the same 404, naming the machine.
    Rules: `log_event` R6 [BUG-1091], Errors rows 1, 3."""
    before_count = event_count(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with db.begin_nested():
            M.log_event(db, machine_id=m1.id, workspace_id=MISSING, event_type="updated", description="Edited")
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Machine with ID {m1.id} not found"
    # Then 4
    assert event_count(db) == before_count


# [claude] MAC-LE-23
def test_mac_le_23__a_soft_deleted_machine_is_accepted(db, w1, u1, md):
    """MAC-LE-23 — a soft-deleted machine is accepted.
    Rules: `log_event` R7."""
    result = M.log_event(db, machine_id=md.id, workspace_id=w1.id, event_type="deactivated", description="Removed", performed_by=u1.id)
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread_event(db, result.id)
    assert row.machine_id == md.id
    assert row.workspace_id == w1.id
    assert row.event_type == "deactivated"
    # Then 3
    assert count_events(db, machine_id=md.id) == 1


# [claude] MAC-LE-24
def test_mac_le_24__a_machine_in_a_soft_deleted_factory_is_accepted(db, w1, mf):
    """MAC-LE-24 — a machine in a soft-deleted factory is accepted.
    Rules: `log_event` R7."""
    result = M.log_event(db, machine_id=mf.id, workspace_id=w1.id, event_type="updated", description="Edited")
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread_event(db, result.id)
    assert row.machine_id == mf.id
    assert row.workspace_id == w1.id
    # Then 3
    assert count_events(db, machine_id=mf.id) == 1


# [claude] MAC-LE-25
def test_mac_le_25__an_unknown_performer_is_refused_by_the_database_no_row(db, w1, m1):
    """MAC-LE-25 — an unknown performer is refused by the database, no row.
    Rules: `log_event` R8, Errors row 4."""
    before_count = event_count(db)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            M.log_event(db, machine_id=m1.id, workspace_id=w1.id, event_type="updated", description="Edited", performed_by=MISSING)
    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert exc.value.orig.pgcode == "23503"
    # Then 4
    assert "machine_activity_events_performed_by_fkey" in str(exc.value.orig)
    # Then 5
    assert event_count(db) == before_count


# [claude] MAC-LE-26
def test_mac_le_26__performer_0_is_refused_not_read_as_no_performer(db, w1, m1):
    """MAC-LE-26 — performer 0 is refused, not read as no performer.
    Rules: `log_event` R8, Errors row 4."""
    before_count = event_count(db)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            M.log_event(db, machine_id=m1.id, workspace_id=w1.id, event_type="updated", description="Edited", performed_by=0)
    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert exc.value.orig.pgcode == "23503"
    # Then 4
    assert "machine_activity_events_performed_by_fkey" in str(exc.value.orig)
    # Then 5
    assert event_count(db) == before_count


# [claude] MAC-LE-27
def test_mac_le_27__a_performer_is_not_checked_against_the_workspace(db, w1, m1):
    """MAC-LE-27 — a performer is not checked against the workspace.
    Rules: `log_event` R8."""
    outsider = make_profile(db)
    result = M.log_event(db, machine_id=m1.id, workspace_id=w1.id, event_type="updated", description="Edited", performed_by=outsider.id)
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread_event(db, result.id)
    assert row.performed_by == outsider.id


# [claude] MAC-LE-28
def test_mac_le_28__a_decimal_in_metadata_fails_at_the_flush_no_row(db, w1, m1):
    """MAC-LE-28 — a Decimal in metadata fails at the flush, no row.
    Rules: `log_event` R9, Errors row 7."""
    before_count = event_count(db)
    # Then 1
    with pytest.raises(StatementError) as exc:
        with db.begin_nested():
            M.log_event(db, machine_id=m1.id, workspace_id=w1.id, event_type="updated", description="Edited", metadata={"cost": Decimal("1.50")})
    # Then 2
    assert isinstance(exc.value.orig, TypeError)
    # Then 3
    assert getattr(exc.value.orig, "pgcode", None) is None
    # Then 4
    assert event_count(db) == before_count


# [claude] MAC-LE-29
def test_mac_le_29__a_datetime_in_metadata_fails_at_the_flush_no_row(db, w1, m1):
    """MAC-LE-29 — a datetime in metadata fails at the flush, no row.
    Rules: `log_event` R9, Errors row 7."""
    before_count = event_count(db)
    # Then 1
    with pytest.raises(StatementError) as exc:
        with db.begin_nested():
            M.log_event(db, machine_id=m1.id, workspace_id=w1.id, event_type="updated", description="Edited", metadata={"at": datetime(2026, 3, 5, 10, 0, 0)})
    # Then 2
    assert isinstance(exc.value.orig, TypeError)
    # Then 3
    assert getattr(exc.value.orig, "pgcode", None) is None
    # Then 4
    assert event_count(db) == before_count


# [claude] MAC-LE-30
def test_mac_le_30__event_type_none_is_refused_by_the_database_no_row(db, w1, m1):
    """MAC-LE-30 — event type None is refused by the database, no row.
    Rules: `log_event` Errors row 5."""
    before_count = event_count(db)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            M.log_event(db, machine_id=m1.id, workspace_id=w1.id, event_type=None, description="Edited")
    # Then 2
    assert isinstance(exc.value.orig, NotNullViolation)
    # Then 3
    assert exc.value.orig.pgcode == "23502"
    # Then 4
    assert event_count(db) == before_count


# [claude] MAC-LE-31
def test_mac_le_31__description_none_is_refused_by_the_database_no_row(db, w1, m1):
    """MAC-LE-31 — description None is refused by the database, no row.
    Rules: `log_event` Errors row 5."""
    before_count = event_count(db)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            M.log_event(db, machine_id=m1.id, workspace_id=w1.id, event_type="updated", description=None)
    # Then 2
    assert isinstance(exc.value.orig, NotNullViolation)
    # Then 3
    assert exc.value.orig.pgcode == "23502"
    # Then 4
    assert event_count(db) == before_count


# [claude] MAC-LE-32
def test_mac_le_32__flushed_not_committed_a_savepoint_s_rollback_removes_the_row(db, w1, m1):
    """MAC-LE-32 — flushed, not committed: a savepoint's rollback removes the row.
    Rules: `log_event` R10, Returns, Side effects."""
    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        result = M.log_event(db, machine_id=m1.id, workspace_id=w1.id, event_type="updated", description="Edited")
    # Then 1
    assert result.id is not None
    # Then 2
    assert count_events(db, machine_id=m1.id) == 1
    # Then 3
    commit_spy.assert_not_called()
    # Then 4
    sp.rollback()
    assert count_events(db, machine_id=m1.id) == 0


# [claude] MAC-LE-33
def test_mac_le_33__an_inactive_live_machine_is_accepted(db, w1, ma):
    """MAC-LE-33 — an inactive, live machine is accepted.
    Rules: `log_event` R1, R6."""
    result = M.log_event(db, machine_id=ma.id, workspace_id=w1.id, event_type="updated", description="Edited")
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread_event(db, result.id)
    assert row.machine_id == ma.id
    assert row.workspace_id == w1.id
    assert row.event_type == "updated"
    # Then 3
    assert count_events(db, machine_id=ma.id) == 1


# --------------------------------------------------------------------------- #
# MachineActivityManager.list_events
# --------------------------------------------------------------------------- #

# [claude] MAC-LI-01
def test_mac_li_01__the_machine_s_events_come_back_newest_first_as_2_tuples(db, w1, m1):
    """MAC-LI-01 — the machine's events come back newest first, as 2-tuples.
    Rules: `list_events` R1, Returns."""
    a = mk_event(db, w1, m1, T2)
    b = mk_status(db, w1, m1, T3)
    c = mk_event(db, w1, m1, T1, event_type="created")
    result = M.list_events(db, machine_id=m1.id, workspace_id=w1.id)
    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [b.id, a.id, c.id]
    # Then 3
    assert isinstance(result[0], tuple)
    assert len(result[0]) == 2
    # Then 4
    assert isinstance(result[0][0], MachineActivityEvent)


# [claude] MAC-LI-02
def test_mac_li_02__on_a_created_at_tie_the_higher_id_comes_first_physically_las(db, w1, m1):
    """MAC-LI-02 — on a created_at tie the higher id comes first, physically last.
    Rules: `list_events` R1 (DAO `get_by_machine` R5)."""
    a = mk_event(db, w1, m1, T2)
    b = mk_event(db, w1, m1, T2)
    result = M.list_events(db, machine_id=m1.id, workspace_id=w1.id)
    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] MAC-LI-03
def test_mac_li_03__on_a_created_at_tie_the_higher_id_comes_first_physically_fir(db, w1, m1):
    """MAC-LI-03 — on a created_at tie the higher id comes first, physically first.
    Rules: `list_events` R1 (DAO `get_by_machine` R5)."""
    a = mk_event(db, w1, m1, T2)
    b = mk_event(db, w1, m1, T2)
    a.description = "Edited"
    db.flush()
    db.expire_all()
    result = M.list_events(db, machine_id=m1.id, workspace_id=w1.id)
    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] MAC-LI-04
def test_mac_li_04__every_argument_reaches_the_read_by_position(db, w1, m1):
    """MAC-LI-04 — every argument reaches the read by position.
    Rules: `list_events` R1, Facts (positional-or-keyword)."""
    mk_event(db, w1, m1, T1)
    b = mk_event(db, w1, m1, T2)
    mk_event(db, w1, m1, T2, event_type="updated")
    d = mk_event(db, w1, m1, T3)
    mk_event(db, w1, m1, datetime(2026, 3, 6, 11, 0, 0))
    mk_event(db, w1, m1, datetime(2026, 3, 7, 10, 0, 0))
    result = M.list_events(db, m1.id, w1.id, 1, 2, date(2026, 3, 5), date(2026, 3, 6), "item_added")
    # Then 1
    assert ids(result) == [d.id, b.id]


# [claude] MAC-LI-05
def test_mac_li_05__skip_passes_over_the_newest_rows(db, w1, m1):
    """MAC-LI-05 — skip passes over the newest rows.
    Rules: `list_events` R1."""
    a = mk_event(db, w1, m1, T1)
    b = mk_event(db, w1, m1, T2)
    mk_event(db, w1, m1, T3)
    result = M.list_events(db, machine_id=m1.id, workspace_id=w1.id, skip=1)
    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] MAC-LI-06
def test_mac_li_06__limit_1_returns_the_newest_row_alone(db, w1, m1):
    """MAC-LI-06 — limit 1 returns the newest row alone.
    Rules: `list_events` R1, R8."""
    mk_event(db, w1, m1, T1)
    b = mk_event(db, w1, m1, T2)
    result = M.list_events(db, machine_id=m1.id, workspace_id=w1.id, limit=1)
    # Then 1
    assert ids(result) == [b.id]


# [claude] MAC-LI-07
def test_mac_li_07__from_date_keeps_the_first_moment_of_the_day(db, w1, m1):
    """MAC-LI-07 — from_date keeps the first moment of the day.
    Rules: `list_events` R1 (DAO `get_by_machine` R9)."""
    a = mk_event(db, w1, m1, datetime(2026, 3, 5, 0, 0, 0))
    result = M.list_events(db, machine_id=m1.id, workspace_id=w1.id, from_date=date(2026, 3, 5))
    # Then 1
    assert ids(result) == [a.id]


# [claude] MAC-LI-08
def test_mac_li_08__from_date_leaves_out_the_last_moment_of_the_day_before(db, w1, m1):
    """MAC-LI-08 — from_date leaves out the last moment of the day before.
    Rules: `list_events` R1 (DAO `get_by_machine` R9)."""
    mk_event(db, w1, m1, datetime(2026, 3, 4, 23, 59, 59, 999999))
    result = M.list_events(db, machine_id=m1.id, workspace_id=w1.id, from_date=date(2026, 3, 5))
    # Then 1
    assert result == []


# [claude] MAC-LI-09
def test_mac_li_09__to_date_keeps_the_last_moment_of_the_day(db, w1, m1):
    """MAC-LI-09 — to_date keeps the last moment of the day.
    Rules: `list_events` R1 (DAO `get_by_machine` R10)."""
    a = mk_event(db, w1, m1, datetime(2026, 3, 5, 23, 59, 59, 999999))
    result = M.list_events(db, machine_id=m1.id, workspace_id=w1.id, to_date=date(2026, 3, 5))
    # Then 1
    assert ids(result) == [a.id]


# [claude] MAC-LI-10
def test_mac_li_10__to_date_leaves_out_the_first_moment_of_the_next_day(db, w1, m1):
    """MAC-LI-10 — to_date leaves out the first moment of the next day.
    Rules: `list_events` R1 (DAO `get_by_machine` R10)."""
    mk_event(db, w1, m1, datetime(2026, 3, 6, 0, 0, 0))
    result = M.list_events(db, machine_id=m1.id, workspace_id=w1.id, to_date=date(2026, 3, 5))
    # Then 1
    assert result == []


# [claude] MAC-LI-11
def test_mac_li_11__event_type_keeps_its_own_type_and_leaves_out_another(db, w1, m1):
    """MAC-LI-11 — event_type keeps its own type and leaves out another.
    Rules: `list_events` R1 (DAO `get_by_machine` R13)."""
    a = mk_event(db, w1, m1, T1)
    mk_status(db, w1, m1, T2)
    result = M.list_events(db, machine_id=m1.id, workspace_id=w1.id, event_type="item_added")
    # Then 1
    assert ids(result) == [a.id]


# [claude] MAC-LI-12
def test_mac_li_12__event_type_updated_does_not_match_status_updated(db, w1, m1):
    """MAC-LI-12 — event_type "updated" does not match status_updated.
    Rules: `list_events` R1 (DAO `get_by_machine` R13)."""
    a = mk_event(db, w1, m1, T1, event_type="updated")
    mk_status(db, w1, m1, T2)
    result = M.list_events(db, machine_id=m1.id, workspace_id=w1.id, event_type="updated")
    # Then 1
    assert ids(result) == [a.id]


# [claude] MAC-LI-13
def test_mac_li_13__event_type_status_does_not_match_status_updated(db, w1, m1):
    """MAC-LI-13 — event_type "status" does not match status_updated.
    Rules: `list_events` R1 (DAO `get_by_machine` R13)."""
    mk_status(db, w1, m1, T1)
    result = M.list_events(db, machine_id=m1.id, workspace_id=w1.id, event_type="status")
    # Then 1
    assert result == []


# [claude] MAC-LI-14
def test_mac_li_14__event_type_status_updated_matches_neither_a_shorter_nor_a_lo(db, w1, m1):
    """MAC-LI-14 — event_type "status_updated" matches neither a shorter nor a longer type.
    Rules: `list_events` R1 (DAO `get_by_machine` R13)."""
    a = mk_status(db, w1, m1, T1)
    mk_event(db, w1, m1, T2, event_type="updated")
    mk_event(db, w1, m1, T3, event_type="status_updated_manual")
    result = M.list_events(db, machine_id=m1.id, workspace_id=w1.id, event_type="status_updated")
    # Then 1
    assert ids(result) == [a.id]


# [claude] MAC-LI-15
def test_mac_li_15__event_type_applies_no_filter(db, w1, m1):
    """MAC-LI-15 — event_type "" applies no filter.
    Rules: `list_events` R1 (DAO `get_by_machine` R14)."""
    a = mk_event(db, w1, m1, T1)
    b = mk_status(db, w1, m1, T2)
    result = M.list_events(db, machine_id=m1.id, workspace_id=w1.id, event_type="")
    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] MAC-LI-16
def test_mac_li_16__the_type_filter_runs_before_paging_a_hidden_row_ahead_of_the(db, w1, m1):
    """MAC-LI-16 — the type filter runs before paging: a hidden row ahead of the skipped row takes no place.
    Rules: `list_events` R1 (DAO `get_by_machine` R15), HR-5."""
    r = mk_status(db, w1, m1, T1)
    mk_status(db, w1, m1, T2)
    mk_event(db, w1, m1, T3)
    result = M.list_events(db, machine_id=m1.id, workspace_id=w1.id, skip=1, limit=1, event_type="status_updated")
    # Then 1
    assert ids(result) == [r.id]


# [claude] MAC-LI-17
def test_mac_li_17__the_date_filter_runs_before_paging_a_hidden_row_ahead_of_the(db, w1, m1):
    """MAC-LI-17 — the date filter runs before paging: a hidden row ahead of the skipped row takes no place.
    Rules: `list_events` R1 (DAO `get_by_machine` R15), HR-5."""
    r = mk_event(db, w1, m1, T1)
    mk_event(db, w1, m1, T2)
    mk_event(db, w1, m1, T3)
    result = M.list_events(db, machine_id=m1.id, workspace_id=w1.id, skip=1, limit=1, to_date=date(2026, 3, 5))
    # Then 1
    assert ids(result) == [r.id]


# [claude] MAC-LI-18
def test_mac_li_18__another_machine_s_row_ahead_of_the_skipped_row_takes_no_plac(db, w1, m1, m2):
    """MAC-LI-18 — another machine's row ahead of the skipped row takes no place.
    Rules: `list_events` R1 (DAO `get_by_machine` R1), HR-5."""
    r = mk_event(db, w1, m1, T1)
    mk_event(db, w1, m1, T2)
    mk_event(db, w1, m2, T3)
    result = M.list_events(db, machine_id=m1.id, workspace_id=w1.id, skip=1, limit=1)
    # Then 1
    assert ids(result) == [r.id]


# [claude] MAC-LI-19
def test_mac_li_19__all_filters_combine(db, w1, m1):
    """MAC-LI-19 — all filters combine.
    Rules: `list_events` R1 (DAO `get_by_machine` R15)."""
    mk_status(db, w1, m1, T1)
    mk_event(db, w1, m1, T2)
    c = mk_status(db, w1, m1, T2)
    mk_status(db, w1, m1, T3)
    result = M.list_events(db, machine_id=m1.id, workspace_id=w1.id, from_date=date(2026, 3, 5), to_date=date(2026, 3, 5), event_type="status_updated")
    # Then 1
    assert ids(result) == [c.id]


# [claude] MAC-LI-20
def test_mac_li_20__another_workspace_s_machine_gets_404_and_no_event_is_read(db, w1, w2, m9):
    """MAC-LI-20 — another workspace's machine gets 404, and no event is read.
    Rules: `list_events` R2, Errors row 1, HR-16."""
    mk_status(db, w2, m9, T1)
    before_count = event_count(db)
    with sql_recorder(db) as sql_log:
        # Then 1
        with pytest.raises(HTTPException) as exc:
            M.list_events(db, machine_id=m9.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Machine with ID {m9.id} not found"
    # Then 4
    assert len(sql_log) == 1
    # Then 5
    assert event_count(db) == before_count


# [claude] MAC-LI-21
def test_mac_li_21__an_unknown_machine_gets_the_same_404(db, w1):
    """MAC-LI-21 — an unknown machine gets the same 404.
    Rules: `list_events` R2, Errors row 1."""
    before_count = event_count(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.list_events(db, machine_id=MISSING, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine with ID 999999999 not found"
    # Then 4
    assert event_count(db) == before_count


# [claude] MAC-LI-22
def test_mac_li_22__machine_id_0_gets_the_same_404(db, w1):
    """MAC-LI-22 — machine id 0 gets the same 404.
    Rules: `list_events` R2, Errors row 1."""
    before_count = event_count(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.list_events(db, machine_id=0, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine with ID 0 not found"
    # Then 4
    assert event_count(db) == before_count


# [claude] MAC-LI-23
def test_mac_li_23__a_negative_machine_id_gets_the_same_404(db, w1):
    """MAC-LI-23 — a negative machine id gets the same 404.
    Rules: `list_events` R2, Errors row 1."""
    before_count = event_count(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.list_events(db, machine_id=-1, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine with ID -1 not found"
    # Then 4
    assert event_count(db) == before_count


# [claude] MAC-LI-24
def test_mac_li_24__a_w1_row_on_w2_s_machine_does_not_reach_w1_it_gets_the_404(db, w1, m9):
    """MAC-LI-24 — a W1 row on W2's machine does not reach W1: it gets the 404.
    Rules: `list_events` R3, HR-16."""
    a = mk_event(db, w1, m9, T1)
    before_a = snap(db, a)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.list_events(db, machine_id=m9.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Machine with ID {m9.id} not found"
    # Then 4
    assert reread_snap(db, a) == before_a


# [claude] MAC-LI-25
def test_mac_li_25__w2_s_list_leaves_out_the_w1_row_on_its_machine(db, w1, w2, m9):
    """MAC-LI-25 — W2's list leaves out the W1 row on its machine.
    Rules: `list_events` R3, HR-16."""
    a = mk_event(db, w2, m9, T1)
    mk_event(db, w1, m9, T2)
    result = M.list_events(db, machine_id=m9.id, workspace_id=w2.id)
    # Then 1
    assert ids(result) == [a.id]


# [claude] MAC-LI-26
def test_mac_li_26__the_w1_row_ahead_of_the_skipped_row_takes_no_place_in_w2_s_p(db, w1, w2, m9):
    """MAC-LI-26 — the W1 row ahead of the skipped row takes no place in W2's page.
    Rules: `list_events` R3, R1, HR-5."""
    r = mk_event(db, w2, m9, T1)
    mk_event(db, w2, m9, T2)
    mk_event(db, w1, m9, T3)
    result = M.list_events(db, machine_id=m9.id, workspace_id=w2.id, skip=1, limit=1)
    # Then 1
    assert ids(result) == [r.id]


# [claude] MAC-LI-27
def test_mac_li_27__a_soft_deleted_machine_returns_every_event(db, w1, md):
    """MAC-LI-27 — a soft-deleted machine returns every event.
    Rules: `list_events` R4."""
    a = mk_event(db, w1, md, T1)
    b = mk_event(db, w1, md, T2, event_type="deactivated")
    result = M.list_events(db, machine_id=md.id, workspace_id=w1.id)
    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] MAC-LI-28
def test_mac_li_28__a_machine_in_a_soft_deleted_factory_returns_every_event(db, w1, mf):
    """MAC-LI-28 — a machine in a soft-deleted factory returns every event.
    Rules: `list_events` R4."""
    a = mk_event(db, w1, mf, T1)
    b = mk_event(db, w1, mf, T2)
    result = M.list_events(db, machine_id=mf.id, workspace_id=w1.id)
    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] MAC-LI-29
def test_mac_li_29__an_inactive_machine_returns_every_event(db, w1, ma):
    """MAC-LI-29 — an inactive machine returns every event.
    Rules: `list_events` R4."""
    a = mk_event(db, w1, ma, T1)
    b = mk_event(db, w1, ma, T2)
    result = M.list_events(db, machine_id=ma.id, workspace_id=w1.id)
    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] MAC-LI-30
def test_mac_li_30__the_first_element_holds_the_stored_metadata_whole(db, w1, m1):
    """MAC-LI-30 — the first element holds the stored metadata whole.
    Rules: `list_events` R6."""
    a = mk_event(db, w1, m1, T1, description="Attached a.png", metadata_json={"note": "belt", "old_quantity": 3, "new_quantity": 5, "attachment_id": 7, "file_name": "a.png", "mime_type": "image/png", "file_size": 120})
    result = M.list_events(db, machine_id=m1.id, workspace_id=w1.id)
    # Then 1
    assert result[0][0].id == a.id
    # Then 2
    assert result[0][0].description == "Attached a.png"
    # Then 3
    assert result[0][0].metadata_json == {"note": "belt", "old_quantity": 3, "new_quantity": 5, "attachment_id": 7, "file_name": "a.png", "mime_type": "image/png", "file_size": 120}


# [claude] MAC-LI-31
def test_mac_li_31__a_row_with_empty_metadata_reads_back_as_none(db, w1, m1):
    """MAC-LI-31 — a row with empty metadata reads back as None.
    Rules: `list_events` R6."""
    a = mk_event(db, w1, m1, T1, metadata_json=None)
    result = M.list_events(db, machine_id=m1.id, workspace_id=w1.id)
    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert result[0][0].metadata_json is None


# [claude] MAC-LI-32
def test_mac_li_32__a_machine_with_no_events_gives_an_empty_list(db, w1, m1, m2):
    """MAC-LI-32 — a machine with no events gives an empty list.
    Rules: `list_events` R5."""
    mk_event(db, w1, m2, T1)
    result = M.list_events(db, machine_id=m1.id, workspace_id=w1.id)
    # Then 1
    assert result == []


# [claude] MAC-LI-33
def test_mac_li_33__each_entry_holds_its_own_performer_or_none(db, w1, u1, u2, m1):
    """MAC-LI-33 — each entry holds its own performer, or None.
    Rules: `list_events` R7."""
    a = mk_event(db, w1, m1, T1, performed_by=u2.id)
    b = mk_event(db, w1, m1, T2)
    c = mk_event(db, w1, m1, T3, performed_by=u1.id)
    result = M.list_events(db, machine_id=m1.id, workspace_id=w1.id)
    # Then 1
    assert ids(result) == [c.id, b.id, a.id]
    # Then 2
    assert result[0][1].id == u1.id
    # Then 3
    assert result[1][1] is None
    # Then 4
    assert result[2][1].id == u2.id


# [claude] MAC-LI-34
def test_mac_li_34__two_entries_by_one_person_hold_the_same_instance(db, w1, u1, m1):
    """MAC-LI-34 — two entries by one person hold the same instance.
    Rules: `list_events` R7."""
    mk_event(db, w1, m1, T1, performed_by=u1.id)
    mk_event(db, w1, m1, T2, performed_by=u1.id)
    result = M.list_events(db, machine_id=m1.id, workspace_id=w1.id)
    # Then 1
    assert result[0][1].id == u1.id
    # Then 2
    assert result[0][1] is result[1][1]


# [claude] MAC-LI-35
def test_mac_li_35__with_the_defaults_100_of_101_entries_come_back_the_newest(db, w1, m1):
    """MAC-LI-35 — with the defaults 100 of 101 entries come back, the newest.
    Rules: `list_events` R8."""
    mk_log(db, w1, m1, 101)
    result = M.list_events(db, machine_id=m1.id, workspace_id=w1.id)
    # Then 1
    assert len(result) == 100
    # Then 2
    assert result[0][0].description == "E100"
    # Then 3
    assert result[99][0].description == "E1"


# [claude] MAC-LI-36
def test_mac_li_36__limit_1000_gives_1000_of_1000(db, w1, m1):
    """MAC-LI-36 — limit 1000 gives 1000 of 1000.
    Rules: `list_events` R8."""
    mk_log(db, w1, m1, 1000)
    result = M.list_events(db, machine_id=m1.id, workspace_id=w1.id, limit=1000)
    # Then 1
    assert len(result) == 1000
    # Then 2
    assert result[0][0].description == "E999"
    # Then 3
    assert result[999][0].description == "E0"


# [claude] MAC-LI-37
def test_mac_li_37__limit_0_gives_an_empty_list(db, w1, m1):
    """MAC-LI-37 — limit 0 gives an empty list.
    Rules: `list_events` R8."""
    mk_event(db, w1, m1, T1)
    result = M.list_events(db, machine_id=m1.id, workspace_id=w1.id, limit=0)
    # Then 1
    assert result == []


# [claude] MAC-LI-38
def test_mac_li_38__skip_at_the_number_of_rows_gives_an_empty_list(db, w1, m1):
    """MAC-LI-38 — skip at the number of rows gives an empty list.
    Rules: `list_events` R8."""
    mk_event(db, w1, m1, T1)
    mk_event(db, w1, m1, T2)
    result = M.list_events(db, machine_id=m1.id, workspace_id=w1.id, skip=2)
    # Then 1
    assert result == []


# [claude] MAC-LI-39
def test_mac_li_39__skip_one_below_the_number_of_rows_gives_the_oldest_row(db, w1, m1):
    """MAC-LI-39 — skip one below the number of rows gives the oldest row.
    Rules: `list_events` R8."""
    a = mk_event(db, w1, m1, T1)
    mk_event(db, w1, m1, T2)
    result = M.list_events(db, machine_id=m1.id, workspace_id=w1.id, skip=1)
    # Then 1
    assert ids(result) == [a.id]


# [claude] MAC-LI-40
def test_mac_li_40__a_negative_limit_raises_dataerror(db, w1, m1):
    """MAC-LI-40 — a negative limit raises DataError.
    Rules: `list_events` R8, Errors row 2."""
    mk_event(db, w1, m1, T1)
    before_count = event_count(db)
    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            M.list_events(db, machine_id=m1.id, workspace_id=w1.id, limit=-1)
    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInLimitClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201W"
    # Then 4
    assert event_count(db) == before_count


# [claude] MAC-LI-41
def test_mac_li_41__a_negative_skip_raises_dataerror(db, w1, m1):
    """MAC-LI-41 — a negative skip raises DataError.
    Rules: `list_events` R8, Errors row 2."""
    mk_event(db, w1, m1, T1)
    before_count = event_count(db)
    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            M.list_events(db, machine_id=m1.id, workspace_id=w1.id, skip=-1)
    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201X"
    # Then 4
    assert event_count(db) == before_count


# [claude] MAC-LI-42
def test_mac_li_42__one_entry_with_a_performer_stays_within_three_reads(db, w1, u1, m1):
    """MAC-LI-42 — one entry with a performer stays within three reads.
    Rules: `list_events` R9, R7."""
    a = mk_event(db, w1, m1, T1, performed_by=u1.id)
    with sql_recorder(db) as sql_log:
        result = M.list_events(db, machine_id=m1.id, workspace_id=w1.id)
    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert result[0][1].id == u1.id
    # Then 3
    assert len(sql_log) <= 3


# [claude] MAC-LI-43
def test_mac_li_43__entries_with_no_performer_stay_within_three_reads(db, w1, m1):
    """MAC-LI-43 — entries with no performer stay within three reads.
    Rules: `list_events` R9, R7."""
    a = mk_event(db, w1, m1, T1)
    b = mk_event(db, w1, m1, T2)
    c = mk_event(db, w1, m1, T3)
    with sql_recorder(db) as sql_log:
        result = M.list_events(db, machine_id=m1.id, workspace_id=w1.id)
    # Then 1
    assert ids(result) == [c.id, b.id, a.id]
    # Then 2
    assert len(sql_log) <= 3


# [claude] MAC-LI-44
@pytest.mark.xfail(strict=True, reason="BUG-1141: One page of machine activity makes one extra read per entry")
def test_mac_li_44__five_entries_by_one_person_make_at_most_three_reads(db, w1, u1, m1):
    """MAC-LI-44 — five entries by one person make at most three reads.
    Rules: `list_events` R9 [BUG-1141], R7."""
    a = mk_event(db, w1, m1, datetime(2026, 3, 1, 10, 0, 0), performed_by=u1.id)
    b = mk_event(db, w1, m1, datetime(2026, 3, 2, 10, 0, 0), performed_by=u1.id)
    c = mk_event(db, w1, m1, datetime(2026, 3, 3, 10, 0, 0), performed_by=u1.id)
    d = mk_event(db, w1, m1, datetime(2026, 3, 4, 10, 0, 0), performed_by=u1.id)
    e = mk_event(db, w1, m1, datetime(2026, 3, 5, 10, 0, 0), performed_by=u1.id)
    with sql_recorder(db) as sql_log:
        result = M.list_events(db, machine_id=m1.id, workspace_id=w1.id)
    # Then 1
    assert ids(result) == [e.id, d.id, c.id, b.id, a.id]
    # Then 2
    assert [pair[1].id for pair in result] == [u1.id] * 5
    # Then 3
    assert len(sql_log) <= 3


# [claude] MAC-LI-45
@pytest.mark.xfail(strict=True, reason="BUG-1141: One page of machine activity makes one extra read per entry")
def test_mac_li_45__entries_by_two_people_and_by_nobody_make_at_most_three_reads(db, w1, u1, u2, m1):
    """MAC-LI-45 — entries by two people and by nobody make at most three reads.
    Rules: `list_events` R9 [BUG-1141], R7."""
    a = mk_event(db, w1, m1, datetime(2026, 3, 1, 10, 0, 0), performed_by=u1.id)
    b = mk_event(db, w1, m1, datetime(2026, 3, 2, 10, 0, 0), performed_by=u2.id)
    c = mk_event(db, w1, m1, datetime(2026, 3, 3, 10, 0, 0))
    d = mk_event(db, w1, m1, datetime(2026, 3, 4, 10, 0, 0), performed_by=u1.id)
    e = mk_event(db, w1, m1, datetime(2026, 3, 5, 10, 0, 0), performed_by=u2.id)
    with sql_recorder(db) as sql_log:
        result = M.list_events(db, machine_id=m1.id, workspace_id=w1.id)
    # Then 1
    assert ids(result) == [e.id, d.id, c.id, b.id, a.id]
    # Then 2
    assert [pair[1].id if pair[1] else None for pair in result] == [u2.id, u1.id, None, u2.id, u1.id]
    # Then 3
    assert len(sql_log) <= 3


# [claude] MAC-LI-46
def test_mac_li_46__five_entries_by_two_people_and_by_nobody_come_back_with_the(db, w1, u1, u2, m1):
    """MAC-LI-46 — five entries by two people and by nobody come back with the right performers.
    Rules: `list_events` R7, R9."""
    a = mk_event(db, w1, m1, datetime(2026, 3, 1, 10, 0, 0), performed_by=u1.id)
    b = mk_event(db, w1, m1, datetime(2026, 3, 2, 10, 0, 0), performed_by=u2.id)
    c = mk_event(db, w1, m1, datetime(2026, 3, 3, 10, 0, 0))
    d = mk_event(db, w1, m1, datetime(2026, 3, 4, 10, 0, 0), performed_by=u1.id)
    e = mk_event(db, w1, m1, datetime(2026, 3, 5, 10, 0, 0), performed_by=u2.id)
    result = M.list_events(db, machine_id=m1.id, workspace_id=w1.id)
    # Then 1
    assert ids(result) == [e.id, d.id, c.id, b.id, a.id]
    # Then 2
    assert [pair[1].id if pair[1] else None for pair in result] == [u2.id, u1.id, None, u2.id, u1.id]
    # Then 3
    assert result[1][1] is result[4][1]


# [claude] MAC-LI-47
def test_mac_li_47__writes_nothing_a_newer_pending_row_stays_pending_and_is_not(db, w1, m1):
    """MAC-LI-47 — writes nothing: a newer pending row stays pending and is not returned.
    Rules: `list_events` R10, Side effects, Overview."""
    a = mk_event(db, w1, m1, T1)
    p = MachineActivityEvent(workspace_id=w1.id, machine_id=m1.id, event_type="item_added", description="Pending", created_at=T2)
    db.add(p)
    before_count = event_count(db)
    before_a = snap(db, a)
    with sql_recorder(db) as sql_log:
        result = M.list_events(db, machine_id=m1.id, workspace_id=w1.id)
    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert p in db.new
    # Then 3
    assert p.id is None
    # Then 4
    assert event_count(db) == before_count
    # Then 5
    assert reread_snap(db, a) == before_a
    # Then 6
    assert written(sql_log) == []
    # Then 7
    assert locked(sql_log) == []


# --------------------------------------------------------------------------- #
# MachineActivityManager.get_latest_status
# --------------------------------------------------------------------------- #

# [claude] MAC-GS-01
def test_mac_gs_01__the_newest_status_row_is_returned(db, w1, m1):
    """MAC-GS-01 — the newest status row is returned.
    Rules: `get_latest_status` R1, Returns."""
    mk_status(db, w1, m1, T2)
    b = mk_status(db, w1, m1, T3, metadata_json={"status": "IDLE"})
    mk_status(db, w1, m1, T1)
    result = M.get_latest_status(db, machine_id=m1.id, workspace_id=w1.id)
    # Then 1
    assert isinstance(result, MachineActivityEvent)
    # Then 2
    assert result.id == b.id
    # Then 3
    assert result.metadata_json == {"status": "IDLE"}


# [claude] MAC-GS-02
def test_mac_gs_02__positional_arguments_work_as_the_callers_call_it(db, w1, m1):
    """MAC-GS-02 — positional arguments work, as the callers call it.
    Rules: `get_latest_status` R1, Visibility."""
    a = mk_status(db, w1, m1, T1)
    result = M.get_latest_status(db, m1.id, w1.id)
    # Then 1
    assert result.id == a.id


# [claude] MAC-GS-03
def test_mac_gs_03__a_newer_row_of_another_type_is_ignored_even_with_a_status_ke(db, w1, m1):
    """MAC-GS-03 — a newer row of another type is ignored, even with a status key.
    Rules: `get_latest_status` R1 (DAO R3)."""
    a = mk_status(db, w1, m1, T1)
    mk_event(db, w1, m1, T2, event_type="maintenance_logged", metadata_json={"status": "MAINTENANCE"})
    result = M.get_latest_status(db, machine_id=m1.id, workspace_id=w1.id)
    # Then 1
    assert result.id == a.id


# [claude] MAC-GS-04
def test_mac_gs_04__a_newer_row_of_type_updated_is_not_a_status_row(db, w1, m1):
    """MAC-GS-04 — a newer row of type "updated" is not a status row.
    Rules: `get_latest_status` R1 (DAO R3)."""
    a = mk_status(db, w1, m1, T1)
    mk_event(db, w1, m1, T2, event_type="updated", metadata_json={"status": "IDLE"})
    result = M.get_latest_status(db, machine_id=m1.id, workspace_id=w1.id)
    # Then 1
    assert result.id == a.id


# [claude] MAC-GS-05
def test_mac_gs_05__a_newer_row_of_type_status_updated_manual_is_not_a_status_ro(db, w1, m1):
    """MAC-GS-05 — a newer row of type "status_updated_manual" is not a status row.
    Rules: `get_latest_status` R1 (DAO R3)."""
    a = mk_status(db, w1, m1, T1)
    mk_event(db, w1, m1, T2, event_type="status_updated_manual", metadata_json={"status": "IDLE"})
    result = M.get_latest_status(db, machine_id=m1.id, workspace_id=w1.id)
    # Then 1
    assert result.id == a.id


# [claude] MAC-GS-06
def test_mac_gs_06__a_newer_status_row_of_another_machine_is_not_returned(db, w1, m1, m2):
    """MAC-GS-06 — a newer status row of another machine is not returned.
    Rules: `get_latest_status` R1."""
    a = mk_status(db, w1, m1, T1)
    mk_status(db, w1, m2, T2)
    result = M.get_latest_status(db, machine_id=m1.id, workspace_id=w1.id)
    # Then 1
    assert result.id == a.id


# [claude] MAC-GS-07
def test_mac_gs_07__on_a_created_at_tie_the_highest_id_is_returned_physically_la(db, w1, m1):
    """MAC-GS-07 — on a created_at tie the highest id is returned, physically last.
    Rules: `get_latest_status` R1 (DAO R2)."""
    mk_status(db, w1, m1, T2)
    b = mk_status(db, w1, m1, T2)
    result = M.get_latest_status(db, machine_id=m1.id, workspace_id=w1.id)
    # Then 1
    assert result.id == b.id


# [claude] MAC-GS-08
def test_mac_gs_08__on_a_created_at_tie_the_highest_id_is_returned_physically_fi(db, w1, m1):
    """MAC-GS-08 — on a created_at tie the highest id is returned, physically first.
    Rules: `get_latest_status` R1 (DAO R2)."""
    a = mk_status(db, w1, m1, T2)
    b = mk_status(db, w1, m1, T2)
    a.description = "Edited"
    db.flush()
    db.expire_all()
    result = M.get_latest_status(db, machine_id=m1.id, workspace_id=w1.id)
    # Then 1
    assert result.id == b.id


# [claude] MAC-GS-09
def test_mac_gs_09__a_newest_status_row_with_no_metadata_is_returned_older_rows(db, w1, m1):
    """MAC-GS-09 — a newest status row with no metadata is returned; older rows are not consulted.
    Rules: `get_latest_status` R1 (DAO R7)."""
    mk_status(db, w1, m1, T1)
    b = mk_status(db, w1, m1, T2, metadata_json=None)
    result = M.get_latest_status(db, machine_id=m1.id, workspace_id=w1.id)
    # Then 1
    assert result.id == b.id
    # Then 2
    assert result.metadata_json is None


# [claude] MAC-GS-10
def test_mac_gs_10__a_machine_of_the_workspace_with_only_other_rows_gives_none(db, w1, m1):
    """MAC-GS-10 — a machine of the workspace with only other rows gives None.
    Rules: `get_latest_status` R2."""
    mk_event(db, w1, m1, T1)
    result = M.get_latest_status(db, machine_id=m1.id, workspace_id=w1.id)
    # Then 1
    assert result is None


# [claude] MAC-GS-11
def test_mac_gs_11__a_machine_of_the_workspace_with_no_rows_gives_none(db, w1, m1):
    """MAC-GS-11 — a machine of the workspace with no rows gives None.
    Rules: `get_latest_status` R2."""
    result = M.get_latest_status(db, machine_id=m1.id, workspace_id=w1.id)
    # Then 1
    assert result is None


# [claude] MAC-GS-12
@pytest.mark.xfail(strict=True, reason='BUG-1140: get_latest_status says "404 if missing" and raises nothing')
def test_mac_gs_12__an_unknown_machine_gets_404(db, w1):
    """MAC-GS-12 — an unknown machine gets 404.
    Rules: `get_latest_status` R3 [BUG-1140], Errors row 1."""
    before_count = event_count(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_latest_status(db, machine_id=MISSING, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine with ID 999999999 not found"
    # Then 4
    assert event_count(db) == before_count


# [claude] MAC-GS-13
@pytest.mark.xfail(strict=True, reason='BUG-1140: get_latest_status says "404 if missing" and raises nothing')
def test_mac_gs_13__machine_id_0_gets_the_same_404(db, w1):
    """MAC-GS-13 — machine id 0 gets the same 404.
    Rules: `get_latest_status` R3 [BUG-1140], Errors row 1."""
    before_count = event_count(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_latest_status(db, machine_id=0, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine with ID 0 not found"
    # Then 4
    assert event_count(db) == before_count


# [claude] MAC-GS-14
@pytest.mark.xfail(strict=True, reason='BUG-1140: get_latest_status says "404 if missing" and raises nothing')
def test_mac_gs_14__another_workspace_s_machine_gets_the_same_404(db, w1, w2, m9):
    """MAC-GS-14 — another workspace's machine gets the same 404.
    Rules: `get_latest_status` R3 [BUG-1140], Errors row 1, HR-16."""
    mk_status(db, w2, m9, T1)
    before_count = event_count(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_latest_status(db, machine_id=m9.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Machine with ID {m9.id} not found"
    # Then 4
    assert event_count(db) == before_count


# [claude] MAC-GS-15
@pytest.mark.xfail(strict=True, reason='BUG-1140: get_latest_status says "404 if missing" and raises nothing')
def test_mac_gs_15__a_w1_status_row_on_w2_s_machine_does_not_reach_w1(db, w1, m9):
    """MAC-GS-15 — a W1 status row on W2's machine does not reach W1.
    Rules: `get_latest_status` R4 [BUG-1140], Errors row 1, HR-16."""
    a = mk_status(db, w1, m9, T1)
    before_a = snap(db, a)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_latest_status(db, machine_id=m9.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Machine with ID {m9.id} not found"
    # Then 4
    assert reread_snap(db, a) == before_a


# [claude] MAC-GS-16
def test_mac_gs_16__w2_s_answer_is_its_own_older_row_not_the_newer_w1_row_on_its(db, w1, w2, m9):
    """MAC-GS-16 — W2's answer is its own older row, not the newer W1 row on its machine.
    Rules: `get_latest_status` R4, HR-16."""
    a = mk_status(db, w2, m9, T1)
    mk_status(db, w1, m9, T2)
    result = M.get_latest_status(db, machine_id=m9.id, workspace_id=w2.id)
    # Then 1
    assert result.id == a.id


# [claude] MAC-GS-17
def test_mac_gs_17__w2_with_only_the_w1_row_on_its_machine_gets_none(db, w1, w2, m9):
    """MAC-GS-17 — W2 with only the W1 row on its machine gets None.
    Rules: `get_latest_status` R4, R2, HR-16."""
    mk_status(db, w1, m9, T1)
    result = M.get_latest_status(db, machine_id=m9.id, workspace_id=w2.id)
    # Then 1
    assert result is None


# [claude] MAC-GS-18
def test_mac_gs_18__the_status_row_of_a_soft_deleted_machine_is_returned(db, w1, md):
    """MAC-GS-18 — the status row of a soft-deleted machine is returned.
    Rules: `get_latest_status` R5."""
    a = mk_status(db, w1, md, T1)
    result = M.get_latest_status(db, machine_id=md.id, workspace_id=w1.id)
    # Then 1
    assert result.id == a.id


# [claude] MAC-GS-19
def test_mac_gs_19__the_status_row_of_a_machine_in_a_soft_deleted_factory_is_ret(db, w1, mf):
    """MAC-GS-19 — the status row of a machine in a soft-deleted factory is returned.
    Rules: `get_latest_status` R5."""
    a = mk_status(db, w1, mf, T1)
    result = M.get_latest_status(db, machine_id=mf.id, workspace_id=w1.id)
    # Then 1
    assert result.id == a.id


# [claude] MAC-GS-20
def test_mac_gs_20__writes_nothing_a_newer_pending_row_stays_pending_and_is_not(db, w1, m1):
    """MAC-GS-20 — writes nothing: a newer pending row stays pending and is not returned.
    Rules: `get_latest_status` R6, Side effects, Overview."""
    a = mk_status(db, w1, m1, T1)
    p = MachineActivityEvent(workspace_id=w1.id, machine_id=m1.id, event_type="status_updated", description="Pending", created_at=T2)
    db.add(p)
    before_count = event_count(db)
    before_a = snap(db, a)
    with sql_recorder(db) as sql_log:
        result = M.get_latest_status(db, machine_id=m1.id, workspace_id=w1.id)
    # Then 1
    assert result.id == a.id
    # Then 2
    assert p in db.new
    # Then 3
    assert p.id is None
    # Then 4
    assert event_count(db) == before_count
    # Then 5
    assert reread_snap(db, a) == before_a
    # Then 6
    assert written(sql_log) == []
    # Then 7
    assert locked(sql_log) == []


# [claude] MAC-GS-21
def test_mac_gs_21__the_status_row_of_an_inactive_live_machine_is_returned(db, w1, ma):
    """MAC-GS-21 — the status row of an inactive, live machine is returned.
    Rules: `get_latest_status` R1, R3."""
    a = mk_status(db, w1, ma, T1)
    result = M.get_latest_status(db, machine_id=ma.id, workspace_id=w1.id)
    # Then 1
    assert result.id == a.id


# --------------------------------------------------------------------------- #
# MachineActivityManager.get_latest_status_map
# --------------------------------------------------------------------------- #

# [claude] MAC-SM-01
def test_mac_sm_01__each_machine_with_a_status_row_gets_its_newest_row_a_machine(db, w1, m1, m2, ma):
    """MAC-SM-01 — each machine with a status row gets its newest row; a machine not asked for gets nothing.
    Rules: `get_latest_status_map` R1 (DAO R2, R3), Returns."""
    mk_status(db, w1, m1, T1)
    b = mk_status(db, w1, m1, T2)
    c = mk_status(db, w1, m2, T1)
    mk_status(db, w1, ma, T3)
    result = M.get_latest_status_map(db, workspace_id=w1.id, machine_ids=[m1.id, m2.id])
    # Then 1
    assert isinstance(result, dict)
    # Then 2
    assert set(result) == {m1.id, m2.id}
    # Then 3
    assert result[m1.id].id == b.id
    # Then 4
    assert result[m2.id].id == c.id


# [claude] MAC-SM-02
def test_mac_sm_02__an_empty_list_gives_an_empty_dict_with_no_read_at_all(db, w1, m1):
    """MAC-SM-02 — an empty list gives an empty dict with no read at all.
    Rules: `get_latest_status_map` R1."""
    mk_status(db, w1, m1, T1)
    with sql_recorder(db) as sql_log:
        result = M.get_latest_status_map(db, workspace_id=w1.id, machine_ids=[])
    # Then 1
    assert result == {}
    # Then 2
    assert sql_log == []


# [claude] MAC-SM-03
def test_mac_sm_03__none_gives_an_empty_dict_with_no_read_at_all(db, w1, m1):
    """MAC-SM-03 — None gives an empty dict with no read at all.
    Rules: `get_latest_status_map` R1."""
    mk_status(db, w1, m1, T1)
    with sql_recorder(db) as sql_log:
        result = M.get_latest_status_map(db, workspace_id=w1.id, machine_ids=None)
    # Then 1
    assert result == {}
    # Then 2
    assert sql_log == []


# [claude] MAC-SM-04
def test_mac_sm_04__three_machines_make_one_read(db, w1, m1, m2, ma):
    """MAC-SM-04 — three machines make one read.
    Rules: `get_latest_status_map` R1, Purpose."""
    mk_status(db, w1, m1, T1)
    mk_status(db, w1, m2, T1)
    mk_status(db, w1, ma, T1)
    with sql_recorder(db) as sql_log:
        result = M.get_latest_status_map(db, workspace_id=w1.id, machine_ids=[m1.id, m2.id, ma.id])
    # Then 1
    assert set(result) == {m1.id, m2.id, ma.id}
    # Then 2
    assert len(sql_log) == 1


# [claude] MAC-SM-05
def test_mac_sm_05__an_unknown_id_0_and_a_machine_with_no_status_row_have_no_ent(db, w1, m1, m2):
    """MAC-SM-05 — an unknown id, 0 and a machine with no status row have no entry.
    Rules: `get_latest_status_map` R1 (DAO R3)."""
    a = mk_status(db, w1, m1, T1)
    mk_event(db, w1, m2, T1)
    result = M.get_latest_status_map(db, workspace_id=w1.id, machine_ids=[m1.id, m2.id, MISSING, 0])
    # Then 1
    assert set(result) == {m1.id}
    # Then 2
    assert result[m1.id].id == a.id


# [claude] MAC-SM-06
def test_mac_sm_06__an_id_listed_twice_gives_one_entry(db, w1, m1):
    """MAC-SM-06 — an id listed twice gives one entry.
    Rules: `get_latest_status_map` R1 (DAO R3)."""
    a = mk_status(db, w1, m1, T1)
    result = M.get_latest_status_map(db, workspace_id=w1.id, machine_ids=[m1.id, m1.id])
    # Then 1
    assert set(result) == {m1.id}
    # Then 2
    assert result[m1.id].id == a.id


# [claude] MAC-SM-07
def test_mac_sm_07__a_newer_row_of_type_updated_is_not_a_status_row(db, w1, m1):
    """MAC-SM-07 — a newer row of type "updated" is not a status row.
    Rules: `get_latest_status_map` R1 (DAO R4)."""
    a = mk_status(db, w1, m1, T1)
    mk_event(db, w1, m1, T2, event_type="updated", metadata_json={"status": "IDLE"})
    result = M.get_latest_status_map(db, workspace_id=w1.id, machine_ids=[m1.id])
    # Then 1
    assert set(result) == {m1.id}
    # Then 2
    assert result[m1.id].id == a.id


# [claude] MAC-SM-08
def test_mac_sm_08__a_newer_row_of_type_status_updated_manual_is_not_a_status_ro(db, w1, m1):
    """MAC-SM-08 — a newer row of type "status_updated_manual" is not a status row.
    Rules: `get_latest_status_map` R1 (DAO R4)."""
    a = mk_status(db, w1, m1, T1)
    mk_event(db, w1, m1, T2, event_type="status_updated_manual", metadata_json={"status": "IDLE"})
    result = M.get_latest_status_map(db, workspace_id=w1.id, machine_ids=[m1.id])
    # Then 1
    assert set(result) == {m1.id}
    # Then 2
    assert result[m1.id].id == a.id


# [claude] MAC-SM-09
def test_mac_sm_09__a_newer_status_row_of_another_workspace_on_the_same_machine(db, w1, w2, m1):
    """MAC-SM-09 — a newer status row of another workspace on the same machine is ignored.
    Rules: `get_latest_status_map` R1 (DAO R5)."""
    a = mk_status(db, w1, m1, T1)
    mk_status(db, w2, m1, T2)
    result = M.get_latest_status_map(db, workspace_id=w1.id, machine_ids=[m1.id])
    # Then 1
    assert set(result) == {m1.id}
    # Then 2
    assert result[m1.id].id == a.id


# [claude] MAC-SM-10
def test_mac_sm_10__the_status_rows_of_a_soft_deleted_machine_and_of_a_machine_i(db, w1, m1, md, mf):
    """MAC-SM-10 — the status rows of a soft-deleted machine and of a machine in a soft-deleted factory are the entries; a newest row with no metadata is the value.
    Rules: `get_latest_status_map` R1 (DAO R7, R8)."""
    a = mk_status(db, w1, md, T1)
    b = mk_status(db, w1, mf, T1)
    mk_status(db, w1, m1, T1)
    d = mk_status(db, w1, m1, T2, metadata_json=None)
    result = M.get_latest_status_map(db, workspace_id=w1.id, machine_ids=[md.id, mf.id, m1.id])
    # Then 1
    assert set(result) == {md.id, mf.id, m1.id}
    # Then 2
    assert result[md.id].id == a.id
    # Then 3
    assert result[mf.id].id == b.id
    # Then 4
    assert result[m1.id].id == d.id


# [claude] MAC-SM-11
def test_mac_sm_11__on_a_tie_the_machine_gets_one_entry_one_of_the_tied_rows(db, w1, m1):
    """MAC-SM-11 — on a tie the machine gets one entry, one of the tied rows.
    Rules: `get_latest_status_map` R2, R1."""
    a = mk_status(db, w1, m1, T2)
    b = mk_status(db, w1, m1, T2)
    mk_status(db, w1, m1, T1)
    a.description = "Edited"
    db.flush()
    db.expire_all()
    result = M.get_latest_status_map(db, workspace_id=w1.id, machine_ids=[m1.id])
    # Then 1
    assert set(result) == {m1.id}
    # Then 2
    assert result[m1.id].id in {a.id, b.id}


# [claude] MAC-SM-12
@pytest.mark.xfail(strict=False, reason="BUG-1090: Machine list and machine page can show different statuses on a timestamp tie")
def test_mac_sm_12__on_a_tie_the_entry_is_the_highest_id_physically_first_the_ro(db, w1, m1):
    """MAC-SM-12 — on a tie the entry is the highest id, physically first, the row of get_latest_status.
    Rules: `get_latest_status_map` R2 [BUG-1090]."""
    a = mk_status(db, w1, m1, T2)
    b = mk_status(db, w1, m1, T2)
    a.description = "Edited"
    db.flush()
    db.expire_all()
    single = M.get_latest_status(db, machine_id=m1.id, workspace_id=w1.id)
    result = M.get_latest_status_map(db, workspace_id=w1.id, machine_ids=[m1.id])
    # Then 1
    assert set(result) == {m1.id}
    # Then 2
    assert single.id == b.id
    # Then 3
    assert result[m1.id].id == b.id
    # Then 4
    assert result[m1.id].id == single.id


# [claude] MAC-SM-13
@pytest.mark.xfail(strict=False, reason="BUG-1090: Machine list and machine page can show different statuses on a timestamp tie")
def test_mac_sm_13__on_a_tie_the_entry_is_the_highest_id_physically_last_the_row(db, w1, m1):
    """MAC-SM-13 — on a tie the entry is the highest id, physically last, the row of get_latest_status.
    Rules: `get_latest_status_map` R2 [BUG-1090]."""
    mk_status(db, w1, m1, T2)
    b = mk_status(db, w1, m1, T2)
    single = M.get_latest_status(db, machine_id=m1.id, workspace_id=w1.id)
    result = M.get_latest_status_map(db, workspace_id=w1.id, machine_ids=[m1.id])
    # Then 1
    assert set(result) == {m1.id}
    # Then 2
    assert single.id == b.id
    # Then 3
    assert result[m1.id].id == b.id
    # Then 4
    assert result[m1.id].id == single.id


# [claude] MAC-SM-14
@pytest.mark.xfail(strict=True, reason="BUG-1090: Machine list and machine page can show different statuses on a timestamp tie")
def test_mac_sm_14__the_map_s_query_asks_the_database_for_an_order_that_includes(db, w1, m1):
    """MAC-SM-14 — the map's query asks the database for an order that includes id.
    Rules: `get_latest_status_map` R2 [BUG-1090]."""
    a = mk_status(db, w1, m1, T1)
    with sql_recorder(db) as sql_log:
        result = M.get_latest_status_map(db, workspace_id=w1.id, machine_ids=[m1.id])
    # Then 1
    assert result[m1.id].id == a.id
    # Then 2
    assert len(sql_log) == 1
    # Then 3
    assert "ORDER BY" in sql_log[0]
    # Then 4
    assert ".id" in sql_log[0].split("ORDER BY", 1)[1]


# [claude] MAC-SM-15
def test_mac_sm_15__another_workspace_s_machine_simply_has_no_entry_and_nothing(db, w1, w2, m1, m9):
    """MAC-SM-15 — another workspace's machine simply has no entry, and nothing is refused.
    Rules: `get_latest_status_map` R3, HR-16."""
    a = mk_status(db, w1, m1, T1)
    mk_status(db, w2, m9, T2)
    result = M.get_latest_status_map(db, workspace_id=w1.id, machine_ids=[m1.id, m9.id])
    # Then 1
    assert set(result) == {m1.id}
    # Then 2
    assert result[m1.id].id == a.id


# [claude] MAC-SM-16
def test_mac_sm_16__a_w1_status_row_on_w2_s_machine_does_appear_for_w1(db, w1, m9):
    """MAC-SM-16 — a W1 status row on W2's machine does appear for W1.
    Rules: `get_latest_status_map` R3."""
    a = mk_status(db, w1, m9, T1)
    result = M.get_latest_status_map(db, workspace_id=w1.id, machine_ids=[m9.id])
    # Then 1
    assert set(result) == {m9.id}
    # Then 2
    assert result[m9.id].id == a.id


# [claude] MAC-SM-17
def test_mac_sm_17__writes_nothing_a_newer_pending_row_stays_pending_and_is_not(db, w1, m1):
    """MAC-SM-17 — writes nothing: a newer pending row stays pending and is not the entry.
    Rules: `get_latest_status_map` R4, Side effects, Overview."""
    a = mk_status(db, w1, m1, T1)
    p = MachineActivityEvent(workspace_id=w1.id, machine_id=m1.id, event_type="status_updated", description="Pending", created_at=T2)
    db.add(p)
    before_count = event_count(db)
    before_a = snap(db, a)
    with sql_recorder(db) as sql_log:
        result = M.get_latest_status_map(db, workspace_id=w1.id, machine_ids=[m1.id])
    # Then 1
    assert result[m1.id].id == a.id
    # Then 2
    assert p in db.new
    # Then 3
    assert p.id is None
    # Then 4
    assert event_count(db) == before_count
    # Then 5
    assert reread_snap(db, a) == before_a
    # Then 6
    assert written(sql_log) == []
    # Then 7
    assert locked(sql_log) == []


# [claude] MAC-SM-18
def test_mac_sm_18__positional_arguments_work_workspace_before_machine_ids(db, w1, m1):
    """MAC-SM-18 — positional arguments work, workspace before machine ids.
    Rules: `get_latest_status_map` R1, Facts (positional-or-keyword)."""
    a = mk_status(db, w1, m1, T1)
    result = M.get_latest_status_map(db, w1.id, [m1.id])
    # Then 1
    assert result[m1.id].id == a.id


# --------------------------------------------------------------------------- #
# MachineActivityManager.status_from_activity
# --------------------------------------------------------------------------- #

# [claude] MAC-SA-01
def test_mac_sa_01__none_gives_none():
    """MAC-SA-01 — None gives None.
    Rules: `status_from_activity` R1."""
    event = None
    result = M.status_from_activity(event)
    # Then 1
    assert result is None


# [claude] MAC-SA-02
def test_mac_sa_02__metadata_none_gives_none():
    """MAC-SA-02 — metadata None gives None.
    Rules: `status_from_activity` R2."""
    event = MachineActivityEvent(metadata_json=None)
    result = M.status_from_activity(event)
    # Then 1
    assert result is None


# [claude] MAC-SA-03
def test_mac_sa_03__empty_metadata_gives_none():
    """MAC-SA-03 — empty metadata gives None.
    Rules: `status_from_activity` R2."""
    event = MachineActivityEvent(metadata_json={})
    result = M.status_from_activity(event)
    # Then 1
    assert result is None


# [claude] MAC-SA-04
def test_mac_sa_04__metadata_with_no_status_key_gives_none():
    """MAC-SA-04 — metadata with no status key gives None.
    Rules: `status_from_activity` R3."""
    event = MachineActivityEvent(metadata_json={"note": "belt"})
    result = M.status_from_activity(event)
    # Then 1
    assert result is None


# [claude] MAC-SA-05
def test_mac_sa_05__a_stored_status_comes_back_unchanged():
    """MAC-SA-05 — a stored status comes back unchanged.
    Rules: `status_from_activity` R4."""
    event = MachineActivityEvent(metadata_json={"status": "IDLE"})
    result = M.status_from_activity(event)
    # Then 1
    assert result == "IDLE"


# [claude] MAC-SA-06
def test_mac_sa_06__a_stored_none_comes_back_as_none():
    """MAC-SA-06 — a stored None comes back as None.
    Rules: `status_from_activity` R4."""
    event = MachineActivityEvent(metadata_json={"status": None, "note": "belt"})
    result = M.status_from_activity(event)
    # Then 1
    assert result is None


# [claude] MAC-SA-07
def test_mac_sa_07__a_stored_empty_string_stays_an_empty_string():
    """MAC-SA-07 — a stored empty string stays an empty string.
    Rules: `status_from_activity` R4."""
    event = MachineActivityEvent(metadata_json={"status": ""})
    result = M.status_from_activity(event)
    # Then 1
    assert result == ""


# [claude] MAC-SA-08
def test_mac_sa_08__a_stored_number_stays_a_number():
    """MAC-SA-08 — a stored number stays a number.
    Rules: `status_from_activity` R4."""
    event = MachineActivityEvent(metadata_json={"status": 5})
    result = M.status_from_activity(event)
    # Then 1
    assert result == 5
    # Then 2
    assert isinstance(result, int)


# [claude] MAC-SA-09
def test_mac_sa_09__the_event_type_is_not_looked_at():
    """MAC-SA-09 — the event type is not looked at.
    Rules: `status_from_activity` R5."""
    event = MachineActivityEvent(event_type="maintenance_logged", metadata_json={"status": "MAINTENANCE"})
    result = M.status_from_activity(event)
    # Then 1
    assert result == "MAINTENANCE"


# [claude] MAC-SA-10
def test_mac_sa_10__a_saved_row_works_like_an_unsaved_one(db, w1, m1):
    """MAC-SA-10 — a saved row works like an unsaved one.
    Rules: `status_from_activity` R4, Inputs."""
    a = mk_status(db, w1, m1, T1, metadata_json={"status": "OFF"})
    result = M.status_from_activity(a)
    # Then 1
    assert result == "OFF"


# [claude] MAC-SA-11
def test_mac_sa_11__a_non_empty_list_as_metadata_raises_attributeerror():
    """MAC-SA-11 — a non-empty list as metadata raises AttributeError.
    Rules: `status_from_activity` Errors row 1."""
    event = MachineActivityEvent(metadata_json=["status"])
    # Then 1
    with pytest.raises(AttributeError):
        M.status_from_activity(event)


# [claude] MAC-SA-12
def test_mac_sa_12__a_non_empty_string_as_metadata_raises_attributeerror():
    """MAC-SA-12 — a non-empty string as metadata raises AttributeError.
    Rules: `status_from_activity` Errors row 1."""
    event = MachineActivityEvent(metadata_json="status")
    # Then 1
    with pytest.raises(AttributeError):
        M.status_from_activity(event)


# [claude] MAC-SA-13
def test_mac_sa_13__the_method_can_be_called_on_the_class():
    """MAC-SA-13 — the method can be called on the class.
    Rules: `status_from_activity` R4, Facts (static)."""
    event = MachineActivityEvent(metadata_json={"status": "IDLE"})
    result = MachineActivityManager.status_from_activity(event)
    # Then 1
    assert result == "IDLE"
